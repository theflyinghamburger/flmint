from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flmint.errors import FlmintUsageError
from flmint.state import atomic_write_text, safe_relative_path


class StateTest(unittest.TestCase):
    def test_safe_relative_path_rejects_unsafe_inputs(self) -> None:
        for bad in ("", "a\x00b", "/absolute/path", "../escape", "reports/../../escape"):
            with self.subTest(bad=bad), self.assertRaises(FlmintUsageError):
                safe_relative_path(bad)

    def test_atomic_write_creates_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "reports" / "audit.json"
            atomic_write_text(target, "ok\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "ok\n")
            self.assertFalse((target.parent / f".{target.name}.tmp-{__import__('os').getpid()}").exists())


if __name__ == "__main__":
    unittest.main()
