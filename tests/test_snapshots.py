from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flmint.errors import SnapshotError
from flmint.snapshots import (
    create_snapshot,
    list_snapshots,
    prefix_path,
    render_created,
    render_list,
    render_restore,
    restore_snapshot,
    state_root,
)


def make_prefix(root: Path, profile: str = "stable") -> Path:
    prefix = prefix_path(profile, root)
    (prefix / "drive_c" / "Program Files" / "FL Studio").mkdir(parents=True)
    (prefix / "drive_c" / "Program Files" / "FL Studio" / "FL64.exe").write_bytes(b"MZ\x90\x00")
    (prefix / "drive_c" / "users" / "flmint").mkdir(parents=True)
    (prefix / "userregistry.dat").write_text("registry-placeholder\n", encoding="utf-8")
    return prefix


class SnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name) / "flmint-state"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_state_root_prefers_xdg(self) -> None:
        with mock.patch.dict("os.environ", {"XDG_DATA_HOME": "/custom/data"}, clear=False):
            self.assertEqual(state_root(), Path("/custom/data/flmint"))
        with mock.patch.dict("os.environ", {"HOME": "/home/tester"}, clear=True):
            self.assertEqual(state_root(), Path("/home/tester/.local/share/flmint"))

    def test_create_refuses_without_prefix(self) -> None:
        with self.assertRaises(SnapshotError) as ctx:
            create_snapshot("stable", "baseline", self.state)
        self.assertIn("does not exist", ctx.exception.message)
        self.assertTrue(any("--dry-run" in action for action in ctx.exception.next_actions))

    def test_create_then_list_and_metadata(self) -> None:
        prefix = make_prefix(self.state)
        record = create_snapshot("stable", "before-change", self.state)
        self.assertTrue(record.archive_sha256 and len(record.archive_sha256) == 64)
        archive = self.state / "profiles" / "stable" / "snapshots" / "before-change.tar.gz"
        self.assertTrue(archive.is_file())
        self.assertEqual(record.archive_bytes, archive.stat().st_size)
        self.assertEqual(record.archive_sha256, hashlib.sha256(archive.read_bytes()).hexdigest())
        meta = self.state / "profiles" / "stable" / "snapshots" / "before-change.json"
        payload = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual(payload["profile"], "stable")
        self.assertEqual(payload["entry_count"], record.entry_count)
        self.assertTrue(prefix.is_dir())

        records = list_snapshots("stable", self.state)
        self.assertEqual([item.name for item in records], ["before-change"])
        self.assertIn("before-change", render_list("stable", records))
        self.assertIn("no prefix files were modified", render_created(record))

    def test_list_is_empty_without_snapshots(self) -> None:
        self.assertEqual(list_snapshots("stable", self.state), [])
        self.assertIn("no snapshots", render_list("stable", []))

    def test_duplicate_snapshot_name_refuses(self) -> None:
        make_prefix(self.state)
        create_snapshot("stable", "baseline", self.state)
        with self.assertRaises(SnapshotError) as ctx:
            create_snapshot("stable", "baseline", self.state)
        self.assertIn("already exists", ctx.exception.message)
        self.assertTrue(any("never overwrites" in action for action in ctx.exception.next_actions))

    def test_traversal_names_rejected(self) -> None:
        make_prefix(self.state)
        for bad in ("../escape", "a/b", "/abs", ""):
            with self.subTest(name=bad), self.assertRaises(SnapshotError):
                create_snapshot("stable", bad, self.state)
        with self.assertRaises(SnapshotError):
            create_snapshot("../evil", "baseline", self.state)

    def test_restore_requires_existing_snapshot(self) -> None:
        with self.assertRaises(SnapshotError) as ctx:
            restore_snapshot("stable", "nope", self.state)
        self.assertIn("not found", ctx.exception.message)
        self.assertTrue(any("snapshot list" in action for action in ctx.exception.next_actions))

    def test_restore_detects_corrupted_archive(self) -> None:
        make_prefix(self.state)
        create_snapshot("stable", "baseline", self.state)
        archive = self.state / "profiles" / "stable" / "snapshots" / "baseline.tar.gz"
        archive.write_bytes(b"tampered")
        with self.assertRaises(SnapshotError) as ctx:
            restore_snapshot("stable", "baseline", self.state)
        self.assertIn("SHA-256 mismatch", ctx.exception.message)

    def test_restore_replaces_prefix_and_preserves_previous(self) -> None:
        prefix = make_prefix(self.state)
        marker = prefix / "drive_c" / "sentinel.txt"
        marker.write_text("new value\n", encoding="utf-8")
        create_snapshot("stable", "clean", self.state)
        marker.write_text("broken value\n", encoding="utf-8")
        (prefix / "drive_c" / "junk").mkdir()

        result = restore_snapshot("stable", "clean", self.state)
        self.assertEqual(render_restore(result).count("preserved"), 2)
        self.assertTrue(result.discarded_prefix is not None and result.discarded_prefix.is_dir())
        self.assertEqual(
            (result.discarded_prefix / "drive_c" / "sentinel.txt").read_text(encoding="utf-8"),
            "broken value\n",
        )
        restored = prefix_path("stable", self.state)
        self.assertFalse((restored / "drive_c" / "junk").exists())
        self.assertTrue((restored / "drive_c" / "Program Files" / "FL Studio" / "FL64.exe").is_file())
        self.assertEqual(
            (restored / "drive_c" / "sentinel.txt").read_text(encoding="utf-8"), "new value\n"
        )

    def test_restore_without_prior_prefix_creates_it(self) -> None:
        prefix = make_prefix(self.state)
        create_snapshot("stable", "clean", self.state)
        shutil.rmtree(prefix)
        self.assertFalse(prefix.exists())
        result = restore_snapshot("stable", "clean", self.state)
        self.assertIsNone(result.discarded_prefix)
        self.assertTrue((prefix / "userregistry.dat").is_file())

    def test_missing_archive_is_reported_not_deleted(self) -> None:
        make_prefix(self.state)
        create_snapshot("stable", "baseline", self.state)
        archive = self.state / "profiles" / "stable" / "snapshots" / "baseline.tar.gz"
        archive.unlink()
        records = list_snapshots("stable", self.state)
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0].archive_present)
        self.assertIn("MISSING ARCHIVE", render_list("stable", records))
        with self.assertRaises(SnapshotError):
            restore_snapshot("stable", "baseline", self.state)

    def test_disk_headroom_refusal(self) -> None:
        make_prefix(self.state)
        with mock.patch("flmint.snapshots.shutil.disk_usage") as usage:
            usage.return_value.total = 10**12
            usage.return_value.used = 10**12
            usage.return_value.free = 1024
            with self.assertRaises(SnapshotError) as ctx:
                create_snapshot("stable", "baseline", self.state)
        self.assertIn("insufficient disk headroom", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
