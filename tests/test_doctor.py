from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import helpers

from flmint.doctor import collect_facts, compare_facts, parse_os_release, render_compare, render_text


class DoctorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self._tmp.name)
        self.os_release = helpers.FIXTURES / "os-release-ubuntu2610.txt"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def collect(self, i386_loader=None, **overrides):
        prober = helpers.make_prober(**overrides)
        return collect_facts(
            prober,
            home=self.home,
            os_release_file=self.os_release,
            env={"XDG_SESSION_TYPE": "x11", "XDG_CURRENT_DESKTOP": "XFCE"},
            i386_loader_file=i386_loader or pathlib.Path(self._tmp.name) / "absent-ld-linux.so.2",
        )

    def test_compare_facts_detects_material_drift(self) -> None:
        facts = self.collect()
        baseline = json.loads(facts.to_json())
        baseline["hostname"] = "old-host"
        baseline["capabilities"]["flmint_runner_installed"] = True
        baseline["blockers"] = ["missing runner"]
        comparison = compare_facts(facts, json.dumps(baseline))
        self.assertTrue(comparison["changed"])
        paths = {change["path"] for change in comparison["changes"]}
        self.assertEqual(paths, {"hostname", "capabilities", "blockers"})
        text = render_compare(comparison)
        self.assertIn("changed hostname:", text)
        self.assertIn("baseline: old-host", text)

    def test_compare_facts_no_drift_ignores_generated_at(self) -> None:
        facts = self.collect()
        baseline = json.loads(facts.to_json())
        baseline["generated_at"] = "2000-01-01T00:00:00+00:00"
        baseline["probes"] = [{"name": "stale", "status": "timeout"}]
        comparison = compare_facts(facts, json.dumps(baseline))
        self.assertFalse(comparison["changed"])
        self.assertIn("no material host/capability drift", render_compare(comparison))

    def test_i386_loader_fact_and_capability(self) -> None:
        loader = pathlib.Path(self._tmp.name) / "ld-linux.so.2"
        loader.write_bytes(b"elf")
        facts = self.collect(i386_loader=loader)
        self.assertTrue(facts.i386_loader_present)
        self.assertTrue(facts.capabilities["i386_loader_present"])
        self.assertIn("i386 loader /lib/ld-linux.so.2: True", render_text(facts))
        self.assertFalse(self.collect().i386_loader_present)

    def test_managed_runner_is_detected_and_clears_the_runtime_blocker(self) -> None:
        wine = (
            self.home / ".local" / "opt" / "flmint" / "daw-ge-proton" / "V" / "V" / "files" / "bin" / "wine"
        )
        wine.parent.mkdir(parents=True)
        wine.write_bytes(b"#!/bin/sh\n")
        facts = self.collect()
        self.assertEqual(facts.managed_runners, ["daw-ge-proton/V/V"])
        self.assertTrue(facts.capabilities["flmint_runner_installed"])
        self.assertFalse(any("no Wine/Bottles runtime present" in b for b in facts.blockers))
        self.assertTrue(any("flmint-managed runner" in w for w in facts.warnings))
        self.assertIn("daw-ge-proton/V/V", render_text(facts))

    def test_healthy_host_facts(self) -> None:
        installer_dir = self.home / "Downloads"
        installer_dir.mkdir()
        (installer_dir / "flstudio_win64_26.1.7.5654.exe").write_bytes(b"MZfake")
        facts = self.collect()
        self.assertEqual(facts.os["NAME"], "Ubuntu")
        self.assertEqual(facts.kernel_release, "7.3.0-10-generic")
        self.assertEqual(facts.machine_arch, "x86_64")
        self.assertEqual(facts.logical_cpus, 16)
        self.assertEqual(facts.physical_cores, 8)
        self.assertEqual(facts.memory_available_bytes, 12000000000)
        self.assertEqual(facts.disk_free_bytes, 188544667648)
        self.assertEqual(facts.disk_free_inodes, 14694355)
        self.assertEqual(facts.nvidia["name"], "NVIDIA GeForce RTX 3090")
        self.assertEqual(facts.cuda["version"], "12.4")
        self.assertEqual(facts.pipewire["version"], [1, 6, 8])
        self.assertTrue(facts.capabilities["pipewire_meets_pipeasio_min"])
        self.assertTrue(facts.capabilities["nvidia_gpu_present"])
        self.assertEqual(len(facts.audio_devices), 4)
        self.assertEqual(facts.wine["version"], "9.0")
        self.assertFalse(facts.bottles_installed)
        self.assertTrue(facts.installer["found"])
        self.assertEqual(
            facts.installer["candidates"][0]["display_path"],
            "~/Downloads/flstudio_win64_26.1.7.5654.exe",
        )

    def test_missing_optional_components_do_not_crash(self) -> None:
        facts = self.collect(
            absent="nvidia-smi,nvcc,pipewire,pipewire-pulse,wpctl,wine,flatpak,flatpak-list,docker"
        )
        self.assertFalse(facts.capabilities["nvidia_gpu_present"])
        self.assertFalse(facts.capabilities["pipewire_present"])
        self.assertIsNone(facts.capabilities["pipewire_meets_pipeasio_min"])
        self.assertTrue(any("PipeWire not detected" in blocker for blocker in facts.blockers))
        json.loads(facts.to_json())

    def test_outdated_pipewire_blocks_pipeasio_gate(self) -> None:
        facts = self.collect(
            outputs={
                "pipewire": (0, helpers.fixture_text("pipewire-100.txt")),
                "pipewire-pulse": (0, helpers.fixture_text("pipewire-100.txt")),
            }
        )
        self.assertFalse(facts.capabilities["pipewire_meets_pipeasio_min"])
        self.assertTrue(any("older than 1.4.2" in blocker for blocker in facts.blockers))

    def test_timeout_probe_is_reported_not_used(self) -> None:
        facts = self.collect(timeout="lscpu")
        self.assertIsNone(facts.cpu_model)
        statuses = {probe["name"]: probe["status"] for probe in facts.probes}
        self.assertEqual(statuses["lscpu"], "timeout")

    def test_json_and_text_rendering(self) -> None:
        facts = self.collect()
        data = json.loads(facts.to_json())
        self.assertEqual(data["schema_version"], 1)
        text = render_text(facts)
        self.assertIn("flmint doctor", text)
        self.assertIn("probes:", text)

    def test_parse_os_release_fixture(self) -> None:
        facts = parse_os_release(self.os_release.read_text(encoding="utf-8"))
        self.assertEqual(facts["ID"], "ubuntu")
        self.assertEqual(facts["VERSION_ID"], "26.10")


if __name__ == "__main__":
    unittest.main()
