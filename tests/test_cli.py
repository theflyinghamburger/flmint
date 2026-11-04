from __future__ import annotations

import io
import json
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import helpers

from flmint import cli


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_cli(self, argv: list[str], **prober_overrides) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        env = {
            "HOME": str(self.home),
            "XDG_SESSION_TYPE": "x11",
            "XDG_CURRENT_DESKTOP": "XFCE",
            "FLMINT_OS_RELEASE": str(helpers.FIXTURES / "os-release-ubuntu2610.txt"),
            "XDG_DATA_HOME": str(self.home / "xdg-data"),
        }
        with (
            mock.patch.dict("os.environ", env, clear=False),
            mock.patch.object(
                cli, "CommandProber", lambda *args, **kwargs: helpers.make_prober(**prober_overrides)
            ),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_doctor_json_exit_zero(self) -> None:
        code, out, _ = self.run_cli(["doctor", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["os"]["VERSION_ID"], "26.10")
        self.assertEqual(data["pipewire"]["raw_version"], "1.6.8")
        self.assertTrue(data["capabilities"]["pipewire_meets_pipeasio_min"])

    def test_doctor_save_uses_safe_relative_path(self) -> None:
        target = helpers.REPO_ROOT / "reports" / "tmp-test-audit.json"
        old_cwd = os.getcwd()
        try:
            os.chdir(helpers.REPO_ROOT)
            code, _, _ = self.run_cli(["doctor", "--format", "json", "--save", "reports/tmp-test-audit.json"])
            self.assertEqual(code, 0)
            self.assertTrue(target.is_file())
            json.loads(target.read_text(encoding="utf-8"))
        finally:
            if target.is_file():
                target.unlink()
            os.chdir(old_cwd)

    def test_plan_without_installer_renders_blocker(self) -> None:
        code, out, _ = self.run_cli(["plan", "--profile", "stable", "--format", "json"])
        self.assertEqual(code, 0)
        plan = json.loads(out)
        self.assertEqual(plan["profile"], "stable")
        self.assertTrue(any("no --installer" in blocker for blocker in plan["blockers"]))
        self.assertTrue(any(step["kind"] == "verify" and step["blocked"] for step in plan["steps"]))

    def test_install_without_dry_run_refuses(self) -> None:
        installer = self.home / "Downloads" / "flstudio_win64_26.1.7.5654.exe"
        installer.parent.mkdir(parents=True, exist_ok=True)
        helpers.write_fake_pe(installer)
        code, out, err = self.run_cli(["install", "--installer", str(installer), "--profile", "stable"])
        self.assertEqual(code, 2)
        self.assertIn("Phase 2 requires explicit human approval", err)
        self.assertIn("dry-run", err)

    def test_install_dry_run_no_mutations(self) -> None:
        installer = self.home / "Downloads" / "flstudio_win64_26.1.7.5654.exe"
        installer.parent.mkdir(parents=True, exist_ok=True)
        helpers.write_fake_pe(installer)
        code, out, err = self.run_cli(
            ["install", "--installer", str(installer), "--profile", "stable", "--dry-run"]
        )
        self.assertEqual(code, 0)
        self.assertIn("flmint install --dry-run", out)
        self.assertIn("no mutations performed", out)
        self.assertEqual(err, "")

    def test_launch_stub_refuses(self) -> None:
        code, _, err = self.run_cli(["launch", "--profile", "stable"])
        self.assertEqual(code, 2)
        self.assertIn("not implemented", err)
        self.assertIn("WINEPREFIX", err)

    def test_snapshot_create_refuses_without_prefix(self) -> None:
        code, _, err = self.run_cli(["snapshot", "create", "--profile", "stable", "--name", "before-install"])
        self.assertEqual(code, 2)
        self.assertIn("no prefix to snapshot", err)
        self.assertFalse((self.home / "xdg-data" / "flmint").exists())

    def test_snapshot_list_reports_none(self) -> None:
        code, out, _ = self.run_cli(["snapshot", "list", "--profile", "stable"])
        self.assertEqual(code, 0)
        self.assertIn("no snapshots", out)

    def test_snapshot_traversal_name_refuses(self) -> None:
        code, _, err = self.run_cli(["snapshot", "create", "--profile", "../evil", "--name", "x"])
        self.assertEqual(code, 2)
        self.assertIn("invalid profile", err)

    def test_bench_stub_refuses_without_model(self) -> None:
        code, _, err = self.run_cli(["bench", "ai"])
        self.assertEqual(code, 2)
        self.assertIn("no model supplied", err)

    def test_find_profile_uses_repo_example_profile(self) -> None:
        profile = cli.find_profile("stable", None)
        self.assertEqual(profile.name, "stable")


if __name__ == "__main__":
    unittest.main()
