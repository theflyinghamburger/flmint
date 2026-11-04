"""Pinned-artifact fetch + digest verification (approval-gated, managed paths only).

Design contract (docs/plan.md 2.2, HANDOFF.md section 10.4): flmint never fetches anything that is
not pinned in the profile with an exact version, asset filename, https download URL, expected SHA-256
and expected size. A digest mismatch is fatal, the partial download is removed, and nothing is
extracted. Every fetch writes a provenance record so later steps can prove what was verified.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .errors import DownloadError
from .manifest import Component
from .state import atomic_write_text, safe_relative_path

CHUNK = 1024 * 1024
TIMEOUT_SECONDS = 60
USER_AGENT = f"flmint/{__version__} pinned-artifact-fetch"

STATUS_VERIFIED = "verified"
STATUS_MISMATCH = "digest-mismatch"


@dataclass(frozen=True)
class Artifact:
    component_id: str
    name: str
    version: str
    asset: str
    download_url: str
    expected_sha256: str
    expected_bytes: int
    license: str | None


@dataclass(frozen=True)
class FetchOutcome:
    artifact: Artifact
    target: Path
    final_url: str
    sha256: str
    sha512: str
    size_bytes: int
    extracted_to: Path | None


@dataclass(frozen=True)
class ProvenanceRecord:
    component_id: str
    name: str
    version: str
    asset: str
    download_url: str
    final_url: str
    fetched_at: str
    expected_sha256: str
    sha256: str
    sha512: str
    expected_bytes: int
    bytes: int
    status: str
    target_path: str
    extracted_to: str | None
    license: str | None
    flmint_version: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def opt_root(home: Path | None = None) -> Path:
    """Runner/artifact install root: ~/.local/opt/flmint (project-managed)."""
    return (home or Path.home()) / ".local" / "opt" / "flmint"


def sanitize_url(url: str) -> str:
    """Drop query/fragment: signed CDN redirect URLs must never be recorded verbatim."""
    return url.split("?", 1)[0].split("#", 1)[0]


def artifact_from_component(component: Component) -> Artifact:
    missing = [
        key
        for key, value in (
            ("version", component.version),
            ("sha256", component.sha256),
            ("download_url", component.download_url),
            ("asset", component.asset),
            ("size_bytes", component.size_bytes),
        )
        if value is None
    ]
    if missing:
        raise DownloadError(
            f"component '{component.id}' is not fetchable: pins missing for {', '.join(missing)}",
            next_actions=(
                "pin version + sha256 + download_url + asset + size_bytes in the profile",
                "review candidates in reports/upstream-candidates.json and reports/decisions.md",
            ),
        )
    assert component.version is not None
    assert component.sha256 is not None
    assert component.download_url is not None
    assert component.asset is not None
    assert component.size_bytes is not None
    return Artifact(
        component_id=component.id,
        name=component.name,
        version=component.version,
        asset=component.asset,
        download_url=component.download_url,
        expected_sha256=component.sha256.lower(),
        expected_bytes=component.size_bytes,
        license=component.license,
    )


def _stream_digests(path: Path) -> tuple[str, str, int]:
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    total = 0
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            total += len(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
    return sha256.hexdigest(), sha512.hexdigest(), total


def fetch_artifact(artifact: Artifact, dest_dir: Path) -> FetchOutcome:
    """Download to a managed path, hashing while streaming; refuse on any size/digest mismatch."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    part = dest_dir / f".{artifact.asset}.part-{os.getpid()}"
    request = urllib.request.Request(
        artifact.download_url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
    )
    final_url = artifact.download_url
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            if not final_url.startswith("https://"):
                raise DownloadError(
                    f"refusing non-HTTPS final URL for '{artifact.component_id}': {final_url}"
                )
            status = getattr(response, "status", 200)
            if status != 200:
                raise DownloadError(
                    f"unexpected HTTP status {status} for '{artifact.component_id}' from {final_url}"
                )
            written = 0
            with open(part, "wb") as out:
                while chunk := response.read(CHUNK):
                    written += len(chunk)
                    if written > artifact.expected_bytes:
                        raise DownloadError(
                            f"download for '{artifact.component_id}' exceeded the pinned size "
                            f"{artifact.expected_bytes} bytes"
                        )
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
    except DownloadError:
        part.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise DownloadError(
            f"fetch failed for '{artifact.component_id}': {exc}",
            next_actions=("check connectivity and the pinned download_url, then retry",),
        ) from exc

    sha256, sha512, total = _stream_digests(part)
    if total != artifact.expected_bytes:
        part.unlink(missing_ok=True)
        raise DownloadError(
            f"size mismatch for '{artifact.component_id}': expected {artifact.expected_bytes} "
            f"bytes, got {total}"
        )
    if sha256 != artifact.expected_sha256:
        quarantine = dest_dir / f"{artifact.asset}.digest-mismatch-{os.getpid()}"
        os.replace(part, quarantine)
        raise DownloadError(
            f"SHA-256 mismatch for '{artifact.component_id}': the pinned digest is not what "
            f"this URL served, so nothing was extracted",
            next_actions=(
                f"expected {artifact.expected_sha256}",
                f"actual   {sha256} (kept unparsed at {quarantine} for inspection only)",
                "stop Phase 2, re-review upstream pins in reports/decisions.md before retrying",
            ),
        )
    target = dest_dir / artifact.asset
    os.replace(part, target)
    return FetchOutcome(
        artifact=artifact,
        target=target,
        final_url=sanitize_url(final_url),
        sha256=sha256,
        sha512=sha512,
        size_bytes=total,
        extracted_to=None,
    )


def extract_archive(archive: Path, dest: Path) -> int:
    """Extract a verified tar.gz into an empty managed directory using the safe 'data' filter."""
    if dest.exists() and any(dest.iterdir()):
        raise DownloadError(
            f"refusing to extract into a non-empty directory: {dest}",
            next_actions=("choose a fresh versioned directory, or restore from a snapshot",),
        )
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            tar.extractall(dest, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise DownloadError(
            f"extraction refused or failed for {archive}: {exc}",
            next_actions=(
                "the archive failed the safe-extraction filter; verify its digest again",
            ),
        ) from exc
    return len(members)


def verify_local(path: Path, expected_sha256: str) -> tuple[str, str, int]:
    """Hash an existing managed file and refuse on mismatch."""
    sha256, sha512, total = _stream_digests(path)
    if sha256 != expected_sha256.lower():
        raise DownloadError(
            f"local artifact {path} does not match its pinned digest",
            next_actions=(f"expected {expected_sha256}", f"actual   {sha256}"),
        )
    return sha256, sha512, total


def outcome_from_local(artifact: Artifact, dest_dir: Path) -> FetchOutcome:
    """Re-verify an already stored artifact (no network) and report its extraction if present."""
    stored = dest_dir / artifact.asset
    if not stored.is_file():
        raise DownloadError(
            f"no stored artifact for '{artifact.component_id}' at {stored}",
            next_actions=(f"flmint fetch --component {artifact.component_id} --approve",),
        )
    sha256, sha512, total = verify_local(stored, artifact.expected_sha256)
    extracted = dest_dir / artifact.version
    return FetchOutcome(
        artifact=artifact,
        target=stored,
        final_url="(re-verified locally from the stored file; not re-downloaded)",
        sha256=sha256,
        sha512=sha512,
        size_bytes=total,
        extracted_to=extracted if extracted.is_dir() else None,
    )


def write_provenance(record: ProvenanceRecord, relative_report: str) -> Path:
    target = safe_relative_path(relative_report)
    payload = json.dumps(record.to_dict(), indent=2) + "\n"
    atomic_write_text(target, payload)
    return target


def build_record(outcome: FetchOutcome, extracted_to: Path | None) -> ProvenanceRecord:
    artifact = outcome.artifact
    status = STATUS_VERIFIED if outcome.sha256 == artifact.expected_sha256 else STATUS_MISMATCH
    return ProvenanceRecord(
        component_id=artifact.component_id,
        name=artifact.name,
        version=artifact.version,
        asset=artifact.asset,
        download_url=artifact.download_url,
        final_url=outcome.final_url,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        expected_sha256=artifact.expected_sha256,
        sha256=outcome.sha256,
        sha512=outcome.sha512,
        expected_bytes=artifact.expected_bytes,
        bytes=outcome.size_bytes,
        status=status,
        target_path=str(outcome.target),
        extracted_to=str(extracted_to) if extracted_to else None,
        license=artifact.license,
        flmint_version=__version__,
    )


def render_provenance(record: ProvenanceRecord) -> str:
    lines = [
        f"fetched + verified: {record.component_id} {record.version}",
        f"  asset: {record.asset} ({record.bytes} bytes, expected {record.expected_bytes})",
        f"  sha256: {record.sha256}",
        f"  sha512: {record.sha512}",
        f"  source: {record.final_url}",
        f"  stored: {record.target_path}",
        f"  status: {record.status}",
    ]
    if record.extracted_to:
        lines.append(f"  extracted into: {record.extracted_to}")
    lines.append("  no checksum mismatch was tolerated; nothing outside managed paths was written")
    return "\n".join(lines)
