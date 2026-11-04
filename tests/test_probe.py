from __future__ import annotations

import pathlib
import unittest

import helpers

from flmint.probe import ABSENT, ERROR, OK, CommandProber, ProbeResult, sanitize


class ProbeTest(unittest.TestCase):
    def test_absent_command_is_not_shell_executed(self) -> None:
        result = CommandProber(timeout=1).run("missing", ["definitely-not-a-real-command-9182736451"])
        self.assertEqual(result.status, ABSENT)
        self.assertIsNone(result.exit_code)
        self.assertFalse(result.usable)

    def test_invalid_argv_rejected(self) -> None:
        result = CommandProber().run("bad", [""])
        self.assertEqual(result.status, ERROR)

    def test_command_prober_true_ok(self) -> None:
        if pathlib.Path("/bin/true").is_file():
            result = CommandProber(timeout=1).run("true", ["/bin/true"])
            self.assertEqual(result.status, OK)
            self.assertTrue(result.usable)

    def test_probe_result_usable_only_for_zero_exit_ok(self) -> None:
        ok = ProbeResult("x", ("x",), OK, 0, "", "")
        nonzero = ProbeResult("x", ("x",), "nonzero", 1, "", "")
        absent = ProbeResult("x", ("x",), ABSENT, None, "", "")
        self.assertTrue(ok.usable)
        self.assertFalse(nonzero.usable)
        self.assertFalse(absent.usable)

    def test_sanitize_redacts_common_secrets(self) -> None:
        text = sanitize("password=hunter2 token: abc123 cookie:xyz\x00")
        self.assertIn("password=[redacted]", text)
        self.assertIn("token=[redacted]", text)
        self.assertIn("cookie:[redacted]", text)
        self.assertNotIn("hunter2", text)

    def test_sanitize_truncates_long_output(self) -> None:
        text = sanitize("a" * 9000)
        self.assertTrue(text.endswith(" ...[truncated]"))
        self.assertLess(len(text), 5000)

    def test_fake_prober_used_by_doctor_tests(self) -> None:
        prober = helpers.make_prober(absent="wine")
        result = prober.run("wine", ["wine", "--version"])
        self.assertEqual(result.status, ABSENT)


if __name__ == "__main__":
    unittest.main()
