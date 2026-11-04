from __future__ import annotations

import unittest

import helpers

from flmint.errors import ManifestError
from flmint.manifest import load_profile_file, load_profile_text


class ManifestTest(unittest.TestCase):
    def test_stable_example_profile(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "stable.example.yaml")
        self.assertEqual(profile.name, "stable")
        self.assertTrue(profile.installer_required)
        self.assertEqual(profile.min_disk_mib, 12288)
        self.assertEqual(len(profile.components), 2)
        self.assertEqual(profile.gates, ())
        self.assertTrue(profile.human_checklist)

    def test_experimental_example_profile(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "experimental.example.yaml")
        self.assertEqual(profile.name, "experimental")
        self.assertEqual(
            {c.id for c in profile.components}, {"bottles", "daw-ge-proton", "pipeasio", "wineasio"}
        )
        self.assertEqual(len(profile.gates), 1)
        gate = profile.gates[0]
        self.assertEqual(gate.kind, "pipewire_min")
        self.assertEqual(gate.min_version, (1, 4, 2))
        self.assertEqual(gate.applies_to, "pipeasio")

    def test_pinned_stable_profile_matches_approved_decisions(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "stable.yaml")
        self.assertEqual(profile.name, "stable")
        self.assertEqual({c.id for c in profile.components}, {"daw-ge-proton"})
        for component in profile.components:
            self.assertIsNotNone(component.version, f"{component.id} version must be pinned")
            if component.kind in {"download", "build"}:
                self.assertIsNotNone(component.sha256, f"{component.id} sha256 must be pinned")
        runner = next(c for c in profile.components if c.id == "daw-ge-proton")
        self.assertEqual(runner.version, "DAW-GE-Proton11-6c")
        self.assertEqual(
            runner.sha256,
            "aecf59518c1137028f6c47afc8e497064d6c5d0f206df6ea6d385dd0766f02d5",
        )
        self.assertTrue(any("D4" in item for item in profile.human_checklist))

    def test_profile_rejects_missing_name(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            load_profile_text("title: x", "bad.yaml")
        self.assertIn("name", ctx.exception.message)

    def test_profile_rejects_tabs(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            load_profile_text("name: x\ncomponents:\n\t- id: a\n", "bad.yaml")
        self.assertIn("tab", ctx.exception.message)

    def test_profile_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            load_profile_text("name: x\nbogus_key: 1", "bad.yaml")
        self.assertIn("bogus_key", ctx.exception.message)

    def test_component_kind_validation(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            load_profile_text("name: x\ncomponents:\n  - id: aptpkg\n    kind: apt\n", "bad.yaml")
        self.assertIn("kind", ctx.exception.message)

    def test_sha256_validation(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            load_profile_text(
                "name: x\ncomponents:\n  - id: a\n    kind: download\n    sha256: deadbeef\n",
                "bad.yaml",
            )
        self.assertIn("sha256", ctx.exception.message)

    def test_component_keys_for_fetch_are_validated(self) -> None:
        profile = load_profile_text(
            "name: x\ncomponents:\n  - id: a\n    kind: download\n    version: 1.2.3\n"
            "    asset: a-1.2.3.tar.gz\n    size_bytes: 42\n"
            "    download_url: https://example.invalid/a-1.2.3.tar.gz\n"
            f"    sha256: {'ab' * 32}\n",
            "good.yaml",
        )
        component = profile.components[0]
        self.assertEqual(component.asset, "a-1.2.3.tar.gz")
        self.assertEqual(component.size_bytes, 42)
        self.assertTrue(component.download_url.startswith("https://"))

    def test_component_rejects_bad_fetch_keys(self) -> None:
        cases = {
            "url": "    download_url: http://example.invalid/a.tar.gz\n",
            "asset": "    asset: ../a.tar.gz\n",
            "size": "    size_bytes: -4\n",
            "unknown": "    mirror_url: https://example.invalid/x\n",
        }
        for label, extra in cases.items():
            with self.subTest(label), self.assertRaises(ManifestError) as ctx:
                load_profile_text(
                    "name: x\ncomponents:\n  - id: a\n    kind: download\n" + extra,
                    "bad.yaml",
                )
            self.assertIn("components[0] (a)", ctx.exception.message)

    def test_gate_validation(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            load_profile_text(
                "name: x\ncomponents:\n  - id: known\n    kind: build\n"
                "gates:\n  - id: g\n    kind: pipewire_min\n    min_version: 1.4.2\n"
                "    applies_to: missing\n",
                "bad.yaml",
            )
        self.assertIn("applies_to", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
