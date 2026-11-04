from __future__ import annotations

import hashlib
import pathlib
import tempfile
import unittest

import helpers

from flmint.errors import InstallerError
from flmint.installer import display_path_for, validate_installer


class InstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_fake_pe(self) -> None:
        path = helpers.write_fake_pe(self.home / "fl studio_installer.exe")
        info = validate_installer(path, home=self.home)
        self.assertEqual(info.pe_arch, "x86-64")
        self.assertEqual(info.installer_engine, "unknown")
        self.assertEqual(info.display_path, "~/" + path.name)
        self.assertEqual(info.sha256, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue(any("Authenticode" in warning for warning in info.warnings))
        self.assertTrue(any("truncated" in warning for warning in info.warnings))

    def test_32bit_pe_warns(self) -> None:
        path = helpers.write_fake_pe(self.home / "flstudio_32.exe", machine=0x014C)
        info = validate_installer(path, home=self.home)
        self.assertEqual(info.pe_arch, "x86")
        self.assertTrue(any("32-bit" in warning for warning in info.warnings))

    def test_nsis_stub_explains_expected_32bit_arch(self) -> None:
        path = helpers.write_fake_nsis_pe(self.home / "flstudio_win64_26.1.7.5654.exe")
        info = validate_installer(path, home=self.home)
        self.assertEqual(info.installer_engine, "nsis")
        self.assertEqual(info.pe_arch, "x86")
        self.assertTrue(any("NSIS installer stub" in warning for warning in info.warnings))
        self.assertFalse(any("requires a 64-bit Windows installer" in warning for warning in info.warnings))

    def test_missing_installer_has_next_action(self) -> None:
        with self.assertRaises(InstallerError) as ctx:
            validate_installer(self.home / "missing.exe", home=self.home)
        self.assertIn("installer not found", ctx.exception.message)
        self.assertTrue(any("image-line.com" in action for action in ctx.exception.next_actions))

    def test_directory_installer_rejected(self) -> None:
        with self.assertRaises(InstallerError) as ctx:
            validate_installer(self.home, home=self.home)
        self.assertIn("not a regular file", ctx.exception.message)

    def test_non_exe_rejected(self) -> None:
        path = self.home / "flstudio.bin"
        path.write_bytes(b"MZ")
        with self.assertRaises(InstallerError):
            validate_installer(path, home=self.home)

    def test_empty_exe_rejected(self) -> None:
        path = self.home / "flstudio.exe"
        path.write_bytes(b"")
        with self.assertRaises(InstallerError):
            validate_installer(path, home=self.home)

    def test_non_pe_rejected(self) -> None:
        path = self.home / "flstudio.exe"
        path.write_text("not a PE", encoding="utf-8")
        with self.assertRaises(InstallerError):
            validate_installer(path, home=self.home)

    def test_display_path_for_outside_home(self) -> None:
        self.assertEqual(
            display_path_for(pathlib.Path("/opt/flstudio.exe"), home=self.home), "/opt/flstudio.exe"
        )


if __name__ == "__main__":
    unittest.main()
