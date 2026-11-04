from __future__ import annotations

import io
import pathlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from flmint import cli
from flmint.errors import FlmintError, FlmintUsageError
from flmint.manifest import Component, Profile
from flmint.projects import list_templates, new_project, project_path
from flmint.runtime_launcher import (
    X11_DRIVER_SECTION,
    build_spec,
    prerequisite_warnings,
    running_pids,
    start,
    stop,
    windows_path,
    x11_hazards,
)

RUNNER = "DAW-GE-Proton11-6c"


def component(cid: str, version: str | None = RUNNER, sha: str | None = "a" * 64) -> Component:
    return Component(cid, "download", cid, version, "https://example.invalid", sha, "GPL-3.0", None)


def profile(name: str = "experimental", *, pipeasio: bool = True, pinned: bool = True) -> Profile:
    comps = [component("daw-ge-proton", RUNNER if pinned else None, "a" * 64 if pinned else None)]
    if pipeasio:
        comps.append(component("pipeasio", "v1.10.0"))
    return Profile(name, name, "", tuple(comps), (), True, 1, (), "test")


class LauncherTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self._tmp.name)
        self.env = {
            "HOME": str(self.home),
            "XDG_DATA_HOME": str(self.home / "data"),
            "XDG_STATE_HOME": str(self.home / "state"),
            "DISPLAY": ":0.0",
            "XAUTHORITY": str(self.home / ".Xauthority"),
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "LANG": "C.UTF-8",
            "SECRET_TOKEN": "must-not-leak",
            "LD_PRELOAD": "/evil.so",
        }
        self._patch = mock.patch.dict("os.environ", self.env, clear=True)
        self._patch.start()
        self.prefix = self.home / "data" / "flmint" / "profiles" / "experimental" / "prefix"
        fl = self.prefix / "drive_c" / "Program Files" / "Image-Line" / "FL Studio 2026"
        (fl / "Data" / "Templates" / "Minimal" / "Basic with limiter").mkdir(parents=True)
        (fl / "FL64.exe").write_bytes(b"MZ")
        tdir = fl / "Data" / "Templates" / "Minimal" / "Basic with limiter"
        (tdir / "Basic with limiter.flp").write_bytes(b"FLhd-template")
        (self.prefix / "user.reg").write_text(
            f'{X11_DRIVER_SECTION} 1\n"KeyboardLayoutList"="x"\n\n', encoding="utf-8"
        )
        self.runner = self.home / ".local" / "opt" / "flmint" / "daw-ge-proton" / RUNNER / RUNNER
        (self.runner / "files" / "bin").mkdir(parents=True)
        (self.runner / "files" / "bin" / "wine").write_text("#!/bin/sh\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def spec(self, **kwargs):  # type: ignore[no-untyped-def]
        return build_spec(kwargs.pop("prof", profile()), home=self.home, now=datetime(2026, 11, 5), **kwargs)

    def test_env_is_clean_and_explicit(self) -> None:
        spec = self.spec()
        self.assertEqual(spec.env["WINEPREFIX"], str(self.prefix))
        self.assertEqual(spec.env["WINEDLLPATH"], str(self.home / ".local" / "lib" / "wine"))
        self.assertEqual(spec.env["WINEDLLOVERRIDES"], "mscoree,mshtml=")
        self.assertEqual(spec.env["XDG_RUNTIME_DIR"], "/run/user/1000")
        self.assertEqual(spec.env["PATH"], "/usr/bin:/bin")
        self.assertEqual(spec.env["WINEDEBUG"], "-all")
        self.assertNotIn("SECRET_TOKEN", spec.env)
        self.assertNotIn("LD_PRELOAD", spec.env)
        self.assertNotIn("PIPEASIO_DEBUG", spec.env)
        self.assertNotIn(".wine", spec.env["WINEPREFIX"].split("/"))
        self.assertEqual(spec.argv[0], str(self.runner / "files" / "bin" / "wine"))
        self.assertTrue(spec.argv[1].endswith("FL Studio 2026/FL64.exe"))
        self.assertEqual(len(spec.argv), 2)
        logs = self.home / "state" / "flmint" / "logs"
        self.assertEqual(spec.log_path, logs / "2026-11-05-000000-experimental-launch.log")

    def test_no_pipeasio_means_no_winedllpath(self) -> None:
        self.assertNotIn("WINEDLLPATH", self.spec(prof=profile(pipeasio=False)).env)

    def test_project_passed_as_z_drive_path(self) -> None:
        flp = self.home / "My Songs" / "a.flp"
        flp.parent.mkdir()
        flp.write_bytes(b"x")
        spec = self.spec(project=flp)
        self.assertEqual(spec.argv[-1], "Z:" + str(flp).replace("/", "\\"))
        self.assertEqual(windows_path(pathlib.Path("/home/u/x.flp")), "Z:\\home\\u\\x.flp")

    def test_project_must_exist_and_be_flp(self) -> None:
        other = self.home / "notes.txt"
        other.write_text("x", encoding="utf-8")
        for bad in (self.home / "missing.flp", other):
            with self.subTest(bad=bad), self.assertRaises(FlmintUsageError):
                self.spec(project=bad)

    def test_refuses_xrandr_hazard(self) -> None:
        (self.prefix / "user.reg").write_text(
            f'{X11_DRIVER_SECTION} 1\n"UseXRandR"="N"\n"UseXVidMode"="N"\n', encoding="utf-8"
        )
        self.assertEqual(len(x11_hazards(self.prefix)), 2)
        with self.assertRaises(FlmintError) as ctx:
            self.spec()
        self.assertIn("crashed Xorg", ctx.exception.message)

    def test_hazard_only_counts_in_x11_section(self) -> None:
        (self.prefix / "user.reg").write_text('[Software\\\\Other] 1\n"UseXRandR"="N"\n', encoding="utf-8")
        self.assertEqual(x11_hazards(self.prefix), [])

    def test_refuses_unpinned_runner_and_missing_prefix(self) -> None:
        with self.assertRaises(FlmintError):
            self.spec(prof=profile(pinned=False))
        with self.assertRaises(FlmintError):
            self.spec(prof=profile(name="stable"))

    def test_rejects_bad_wine_debug(self) -> None:
        with self.assertRaises(FlmintUsageError):
            self.spec(wine_debug="-all; rm -rf ~")

    def test_prerequisite_warnings(self) -> None:
        self.assertEqual(len(prerequisite_warnings(self.prefix)), 3)
        windows = self.prefix / "drive_c" / "windows"
        for arch in ("system32", "syswow64"):
            (windows / arch).mkdir(parents=True)
            for dll in ("libvkd3d-1.dll", "libvkd3d-shader-1.dll", "libvkd3d-utils-1.dll"):
                (windows / arch / dll).write_bytes(b"MZ")
        (windows / "Fonts").mkdir()
        (windows / "Fonts" / "Verdana.ttf").write_bytes(b"\x00")
        self.assertEqual(prerequisite_warnings(self.prefix), [])

    def test_running_pids_matches_exact_prefix(self) -> None:
        proc = self.home / "proc"
        wine = self.runner / "files" / "bin" / "wine"
        good = f"A=1\x00WINEPREFIX={self.prefix}\x00"
        cases = (
            ("10", good, wine),  # Wine process in this prefix
            ("11", f"WINEPREFIX={self.prefix}x\x00", wine),  # different prefix
            ("12", good, pathlib.Path("/usr/lib/firefox/firefox")),  # Linux child that inherited WINEPREFIX
        )
        for pid, env, exe in cases:
            (proc / pid).mkdir(parents=True)
            (proc / pid / "environ").write_bytes(env.encode())
            (proc / pid / "exe").symlink_to(exe)
        (proc / "self").mkdir()
        self.assertEqual(running_pids(self.prefix, self.runner, proc), [10])

    def test_start_detaches_and_records_pid(self) -> None:
        spec = self.spec()
        popen = mock.Mock(return_value=SimpleNamespace(pid=4242))
        self.assertEqual(start(spec, popen=popen), 4242)
        _, kwargs = popen.call_args
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(kwargs["env"], spec.env)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(spec.pid_path.read_text(encoding="utf-8"), "4242\n")
        self.assertTrue(spec.log_path.is_file())

    def test_stop_uses_runner_wineserver_with_prefix(self) -> None:
        run = mock.Mock(return_value=SimpleNamespace(returncode=0))
        self.assertEqual(stop(profile(), run=run, home=self.home), 0)
        argv = run.call_args.args[0]
        self.assertEqual(argv, [str(self.runner / "files" / "bin" / "wineserver"), "-k"])
        self.assertEqual(run.call_args.kwargs["env"]["WINEPREFIX"], str(self.prefix))

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(cli, "find_profile", lambda *_: profile()),
            mock.patch.object(cli, "running_pids", lambda *_: []),
            mock.patch.object(cli, "start", side_effect=AssertionError("must not start")) as started,
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = cli.main(argv)
            self.assertFalse(started.called)
        return code, out.getvalue(), err.getvalue()

    def test_cli_dry_run_executes_nothing(self) -> None:
        code, out, _ = self.run_cli(["launch", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("--dry-run (nothing executed)", out)
        self.assertIn(f"WINEPREFIX={self.prefix}", out)

    def test_cli_refuses_without_approve_or_snapshot_choice(self) -> None:
        code, _, err = self.run_cli(["launch"])
        self.assertEqual(code, 2)
        self.assertIn("without --approve", err)
        code, _, err = self.run_cli(["launch", "--approve"])
        self.assertEqual(code, 2)
        self.assertIn("--snapshot NAME", err)


class ProjectsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.state = pathlib.Path(self._tmp.name) / "flmint"
        fl = self.state / "profiles" / "experimental" / "prefix" / "drive_c" / "Program Files" / "Image-Line"
        tdir = fl / "FL Studio 2026" / "Data" / "Templates"
        (fl / "FL Studio 2026" / "FL64.exe").parent.mkdir(parents=True)
        (fl / "FL Studio 2026" / "FL64.exe").write_bytes(b"MZ")
        for cat, name in (("Minimal", "Basic with limiter"), ("Genre", "Trap")):
            (tdir / cat / name).mkdir(parents=True)
            (tdir / cat / name / f"{name}.flp").write_bytes(f"FLhd-{name}".encode())
        (tdir / "Minimal" / "Basic with limiter" / "stray.flp").write_bytes(b"x")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_lists_templates(self) -> None:
        prefix = self.state / "profiles" / "experimental" / "prefix"
        self.assertEqual(list_templates(prefix), ["Genre/Trap", "Minimal/Basic with limiter"])

    def test_creates_copy_in_managed_projects_dir(self) -> None:
        result = new_project("experimental", "my-song", state=self.state)
        self.assertEqual(result.path, self.state / "projects" / "my-song.flp")
        self.assertEqual(result.path.read_bytes(), b"FLhd-Basic with limiter")
        other = new_project("experimental", "beat.flp", "Genre/Trap", state=self.state)
        self.assertEqual(other.path.name, "beat.flp")

    def test_never_overwrites(self) -> None:
        new_project("experimental", "song", state=self.state)
        (self.state / "projects" / "song.flp").write_bytes(b"user work")
        with self.assertRaises(FlmintUsageError):
            new_project("experimental", "song", state=self.state)
        self.assertEqual((self.state / "projects" / "song.flp").read_bytes(), b"user work")
        self.assertEqual([p.name for p in (self.state / "projects").iterdir()], ["song.flp"])

    def test_rejects_path_like_names_and_templates(self) -> None:
        for bad in ("../x", "a/b", ".hidden", "", ".flp", "..", "a\\b"):
            with self.subTest(bad=bad), self.assertRaises(FlmintUsageError):
                project_path(bad, self.state)
        for template in ("Minimal", "../Minimal/Basic with limiter", "Genre/Missing"):
            with self.subTest(template=template), self.assertRaises(FlmintUsageError):
                new_project("experimental", "x", template, state=self.state)


if __name__ == "__main__":
    unittest.main()
