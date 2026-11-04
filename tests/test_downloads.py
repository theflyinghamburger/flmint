from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from flmint import cli
from flmint.downloads import (
    Artifact,
    FetchOutcome,
    artifact_from_component,
    build_record,
    extract_archive,
    fetch_artifact,
    opt_root,
    outcome_from_local,
    sanitize_url,
    verify_local,
    write_provenance,
)
from flmint.errors import DownloadError
from flmint.manifest import load_profile_text


class FakeResponse:
    def __init__(self, data: bytes, url: str, status: int = 200) -> None:
        self._data = data
        self._pos = 0
        self.status = status
        self._url = url

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def make_artifact(data: bytes, *, sha256: str | None = None) -> Artifact:
    return Artifact(
        component_id="fake-runner",
        name="Fake Runner",
        version="1.2.3",
        asset="fake-1.2.3.tar.gz",
        download_url="https://example.invalid/fake-1.2.3.tar.gz",
        expected_sha256=sha256 or hashlib.sha256(data).hexdigest(),
        expected_bytes=len(data),
        license="GPL-3.0",
    )


class DownloadsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self._tmp.name) / "opt" / "fake-runner"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fetch(self, payload: bytes, artifact: Artifact) -> FetchOutcome:
        with mock.patch(
            "flmint.downloads.urllib.request.urlopen",
            return_value=FakeResponse(payload, artifact.download_url),
        ):
            return fetch_artifact(artifact, self.dest)

    def test_fetch_verifies_digest_and_keeps_no_partials(self) -> None:
        payload = b"runner-bytes" * 4096
        outcome = self._fetch(payload, make_artifact(payload))
        self.assertEqual(outcome.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(outcome.size_bytes, len(payload))
        self.assertEqual(outcome.target.read_bytes(), payload)
        leftovers = [p.name for p in self.dest.iterdir()]
        self.assertEqual(leftovers, [outcome.target.name])

    def test_digest_mismatch_is_fatal_and_quarantined(self) -> None:
        payload = b"tampered-payload"
        artifact = make_artifact(payload, sha256="0" * 64)
        with self.assertRaises(DownloadError) as ctx:
            self._fetch(payload, artifact)
        self.assertIn("SHA-256 mismatch", ctx.exception.message)
        names = sorted(p.name for p in self.dest.iterdir())
        self.assertFalse(any(name.endswith(".tar.gz") and "mismatch" not in name for name in names))
        self.assertTrue(any("digest-mismatch" in name for name in names))

    def test_size_mismatch_refuses_and_leaves_nothing(self) -> None:
        payload = b"x" * 5000
        artifact = make_artifact(payload)
        smaller = Artifact(
            component_id=artifact.component_id,
            name=artifact.name,
            version=artifact.version,
            asset=artifact.asset,
            download_url=artifact.download_url,
            expected_sha256=artifact.expected_sha256,
            expected_bytes=1000,
            license=artifact.license,
        )
        with self.assertRaises(DownloadError):
            self._fetch(payload, smaller)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_unpinned_component_is_not_fetchable(self) -> None:
        profile = load_profile_text(
            "name: x\ncomponents:\n  - id: runner\n    kind: download\n    sha256: null\n",
            "x.yaml",
        )
        with self.assertRaises(DownloadError) as ctx:
            artifact_from_component(profile.components[0])
        for key in ("version", "download_url", "asset", "size_bytes"):
            self.assertIn(key, ctx.exception.message)

    def test_local_reverify_accepts_and_rejects(self) -> None:
        payload = b"already-downloaded"
        path = self.dest / "already.tar.gz"
        self.dest.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        sha256, _, total = verify_local(path, hashlib.sha256(payload).hexdigest())
        self.assertEqual((sha256[:8], total), (hashlib.sha256(payload).hexdigest()[:8], len(payload)))
        with self.assertRaises(DownloadError):
            verify_local(path, "1" * 64)

    def test_extract_rejects_unsafe_member(self) -> None:
        archive = Path(self._tmp.name) / "bad.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo(name="evil/../../escape.txt")
            data = b"nope"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        with self.assertRaises(DownloadError) as ctx:
            extract_archive(archive, Path(self._tmp.name) / "out")
        self.assertIn("extraction", ctx.exception.message.lower())
        self.assertFalse((Path(self._tmp.name) / "escape.txt").exists())

    def test_extract_refuses_non_empty_destination(self) -> None:
        archive = Path(self._tmp.name) / "good.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            data = b"payload"
            info = tarfile.TarInfo(name="files/wine64")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        out = Path(self._tmp.name) / "out"
        out.mkdir()
        (out / "existing").write_bytes(b"keep me")
        with self.assertRaises(DownloadError):
            extract_archive(archive, out)
        self.assertEqual((out / "existing").read_bytes(), b"keep me")
        self.assertEqual(extract_archive(archive, Path(self._tmp.name) / "fresh"), 1)

    def test_provenance_record_is_written_relative(self) -> None:
        payload = b"record-me"
        artifact = make_artifact(payload)
        outcome = self._fetch(payload, artifact)
        old_cwd = os.getcwd()
        try:
            os.chdir(self._tmp.name)
            saved = write_provenance(build_record(outcome, None), "reports/provenance-fake.json")
            self.assertTrue(saved.is_file())
        finally:
            os.chdir(old_cwd)


    def test_signed_redirect_url_is_sanitized_in_records(self) -> None:
        payload = b"signed-redirect"
        artifact = make_artifact(payload)
        signed = "https://cdn.example.invalid/fake-1.2.3.tar.gz?sig=secret&jwt=token"
        with mock.patch(
            "flmint.downloads.urllib.request.urlopen",
            return_value=FakeResponse(payload, signed),
        ):
            outcome = fetch_artifact(artifact, self.dest)
        self.assertEqual(outcome.final_url, "https://cdn.example.invalid/fake-1.2.3.tar.gz")
        record = json.dumps(build_record(outcome, None).to_dict())
        self.assertNotIn("sig=", record)
        self.assertNotIn("jwt=", record)
        self.assertEqual(sanitize_url("https://a.invalid/x?q=1#frag"), "https://a.invalid/x")

    def test_outcome_from_local_rehashes_without_network(self) -> None:
        payload = b"stored-already"
        artifact = make_artifact(payload)
        self.dest.mkdir(parents=True)
        (self.dest / artifact.asset).write_bytes(payload)
        (self.dest / artifact.version).mkdir()
        with mock.patch(
            "flmint.downloads.urllib.request.urlopen",
            side_effect=AssertionError("verify must not touch the network"),
        ):
            outcome = outcome_from_local(artifact, self.dest)
        self.assertEqual(outcome.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(outcome.extracted_to, self.dest / artifact.version)
        self.assertIn("re-verified locally", outcome.final_url)

    def test_outcome_from_local_refuses_tampered_or_missing_files(self) -> None:
        artifact = make_artifact(b"expected")
        with self.assertRaises(DownloadError):
            outcome_from_local(artifact, self.dest)
        self.dest.mkdir(parents=True)
        (self.dest / artifact.asset).write_bytes(b"different")
        with self.assertRaises(DownloadError) as ctx:
            outcome_from_local(artifact, self.dest)
        self.assertIn("pinned digest", ctx.exception.message)


class FetchCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _profile_text(self, payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        return (
            "name: fakelab\n"
            "components:\n"
            "  - id: fake-runner\n"
            "    kind: download\n"
            "    name: Fake Runner\n"
            "    version: 1.2.3\n"
            "    source_url: https://example.invalid/releases\n"
            "    download_url: https://example.invalid/fake-1.2.3.tar.gz\n"
            "    asset: fake-1.2.3.tar.gz\n"
            f"    size_bytes: {len(payload)}\n"
            f"    sha256: {digest}\n"
            "    license: GPL-3.0\n"
        )

    def _tar_payload(self) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            data = b"#!/bin/sh\necho wine\n"
            info = tarfile.TarInfo(name="files/bin/wine64")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def test_fetch_without_approval_refuses(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            code = cli.main(
                ["fetch", "--profile", "stable", "--component", "daw-ge-proton"]
            )
        self.assertEqual(code, 2)
        self.assertIn("refused without --approve", err.getvalue())
        self.assertFalse(opt_root(self.home).exists())

    def test_fetch_with_approval_verifies_extracts_and_records(self) -> None:
        payload = self._tar_payload()
        profile_path = Path(self._tmp.name) / "fakelab.yaml"
        profile_path.write_text(self._profile_text(payload), encoding="utf-8")
        reports_dir = Path(self._tmp.name) / "reports"
        reports_dir.mkdir()
        out = io.StringIO()
        old_cwd = os.getcwd()
        try:
            os.chdir(reports_dir.parent)
            with (
                mock.patch.dict("os.environ", {"HOME": str(self.home)}, clear=False),
                mock.patch(
                    "flmint.downloads.urllib.request.urlopen",
                    return_value=FakeResponse(payload, "https://example.invalid/fake-1.2.3.tar.gz"),
                ),
                redirect_stdout(out),
            ):
                code = cli.main(
                    [
                        "fetch",
                        "--profile-file",
                        str(profile_path),
                        "--component",
                        "fake-runner",
                        "--approve",
                        "--extract",
                    ]
                )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 0)
        self.assertIn("status: verified", out.getvalue())
        stored = opt_root(self.home) / "fake-runner" / "fake-1.2.3.tar.gz"
        self.assertEqual(stored.read_bytes(), payload)
        runner_bin = opt_root(self.home) / "fake-runner" / "1.2.3" / "files" / "bin" / "wine64"
        self.assertTrue(runner_bin.is_file())
        record_path = reports_dir / "provenance-fake-runner.json"
        record = record_path.read_text(encoding="utf-8")
        self.assertIn('"status": "verified"', record)

    def test_verify_command_rehashes_and_rewrites_provenance(self) -> None:
        payload = self._tar_payload()
        profile_path = Path(self._tmp.name) / "fakelab.yaml"
        profile_path.write_text(self._profile_text(payload), encoding="utf-8")
        reports_dir = Path(self._tmp.name) / "reports"
        reports_dir.mkdir()
        stored = opt_root(self.home) / "fake-runner"
        stored.mkdir(parents=True)
        (stored / "fake-1.2.3.tar.gz").write_bytes(payload)
        (stored / "1.2.3").mkdir()
        out = io.StringIO()
        old_cwd = os.getcwd()
        try:
            os.chdir(reports_dir.parent)
            with (
                mock.patch.dict("os.environ", {"HOME": str(self.home)}, clear=False),
                mock.patch(
                    "flmint.downloads.urllib.request.urlopen",
                    side_effect=AssertionError("verify must not touch the network"),
                ),
                redirect_stdout(out),
            ):
                code = cli.main(
                    ["verify", "--profile-file", str(profile_path), "--component", "fake-runner"]
                )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 0)
        self.assertIn("re-verified locally", out.getvalue())
        data = json.loads((reports_dir / "provenance-fake-runner.json").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "verified")
        self.assertEqual(data["extracted_to"], str(stored / "1.2.3"))
        self.assertEqual(data["sha256"], hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
