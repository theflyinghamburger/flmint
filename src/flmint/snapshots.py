"""Prefix snapshots: project-managed paths only, verified archives, preserved rollbacks.

Design contract (docs/rollback.md): snapshots are the safety prerequisite for every
Phase 2 prefix mutation. Writes are confined to ~/.local/share/flmint/profiles/<profile>/,
existing snapshots and discarded prefixes are never silently deleted, and restore verifies
the archive SHA-256 before swapping the prefix into place.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .errors import FlmintUsageError, SnapshotError
from .state import atomic_write_text, safe_relative_path

ARCHIVE_SUFFIX = ".tar.gz"
DISK_MARGIN_BYTES = 256 * 1024**2
CHUNK = 1024 * 1024


@dataclass(frozen=True)
class SnapshotRecord:
    name: str
    profile: str
    created_at: str
    archive_name: str
    archive_bytes: int
    archive_sha256: str
    prefix_bytes: int
    entry_count: int
    flmint_version: str
    archive_present: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RestoreResult:
    name: str
    profile: str
    prefix_path: Path
    discarded_prefix: Path | None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "profile": self.profile,
            "prefix_path": str(self.prefix_path),
            "discarded_prefix": str(self.discarded_prefix) if self.discarded_prefix else None,
        }


def state_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "flmint"


def _single_component(value: str, label: str) -> str:
    try:
        path = safe_relative_path(value)
    except FlmintUsageError as exc:
        raise SnapshotError(
            f"invalid {label} '{value}': {exc.message}",
            next_actions=(f"use a plain {label} name without '/', '..' or absolute paths",),
        ) from exc
    if len(path.parts) != 1:
        raise SnapshotError(
            f"{label} must be a single name without path separators: '{value}'",
            next_actions=(f"use a plain {label} name",),
        )
    return value


def profile_dir(profile: str, root: Path | None = None) -> Path:
    return state_root(root) / "profiles" / _single_component(profile, "profile")


def prefix_path(profile: str, root: Path | None = None) -> Path:
    return profile_dir(profile, root) / "prefix"


def snapshots_dir(profile: str, root: Path | None = None) -> Path:
    return profile_dir(profile, root) / "snapshots"


def _tree_size(path: Path) -> int:
    total = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        for _ in dirs:
            total += 4096
        for name in files:
            try:
                total += (Path(base) / name).lstat().st_size
            except OSError:
                continue
    return total


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _require_prefix(profile: str, root: Path | None) -> Path:
    prefix = prefix_path(profile, root)
    if not prefix.is_dir():
        raise SnapshotError(
            f"no prefix to snapshot for profile '{profile}': {prefix} does not exist",
            next_actions=(
                "prefix creation is an approved Phase 2 step (flmint install --dry-run only for now)",
                f"review: flmint plan --profile {profile} (side-effect-free)",
            ),
        )
    return prefix


def _check_disk_space(profile: str, prefix_bytes: int, dir_for_space: Path) -> int:
    free = shutil.disk_usage(dir_for_space).free
    needed = int(prefix_bytes * 1.2) + DISK_MARGIN_BYTES
    if free < needed:
        raise SnapshotError(
            f"insufficient disk headroom for profile '{profile}': "
            f"need ~{needed // 1024**2} MiB free, {free // 1024**2} MiB available",
            next_actions=("free space or choose another disk before snapshotting",),
        )
    return free


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def create_snapshot(profile: str, name: str, state: Path | None = None) -> SnapshotRecord:
    """Archive the profile prefix into a verified tar.gz inside project-managed state."""
    snapshot_name = _single_component(name, "snapshot name")
    prefix = _require_prefix(profile, state)
    directory = snapshots_dir(profile, state)
    archive = directory / f"{snapshot_name}{ARCHIVE_SUFFIX}"
    if archive.exists():
        raise SnapshotError(
            f"snapshot '{snapshot_name}' already exists for profile '{profile}'",
            next_actions=(
                "choose a new --name; flmint never overwrites or silently deletes snapshots",
                f"list them: flmint snapshot list --profile {profile}",
            ),
        )

    prefix_bytes = _tree_size(prefix)
    directory.mkdir(parents=True, exist_ok=True)
    _check_disk_space(profile, prefix_bytes, directory)

    tmp = directory / f".{snapshot_name}{ARCHIVE_SUFFIX}.tmp-{os.getpid()}"
    try:
        with tarfile.open(tmp, "w:gz", compresslevel=6) as tar:
            tar.add(prefix, arcname="prefix", recursive=True)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise SnapshotError(
            f"snapshot archive write failed for '{snapshot_name}': {exc.strerror or exc}",
            next_actions=("check filesystem permissions under the managed profile dir",),
        ) from exc

    with tarfile.open(tmp, "r:gz") as tar:
        entry_count = len(tar.getmembers())
    archive_sha = _stream_sha256(tmp)
    archive_bytes = tmp.stat().st_size
    os.replace(tmp, archive)

    record = SnapshotRecord(
        name=snapshot_name,
        profile=profile,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        archive_name=archive.name,
        archive_bytes=archive_bytes,
        archive_sha256=archive_sha,
        prefix_bytes=prefix_bytes,
        entry_count=entry_count,
        flmint_version=__version__,
    )
    atomic_write_text(directory / f"{snapshot_name}.json", json.dumps(record.to_dict(), indent=2) + "\n")
    return record


def list_snapshots(profile: str, state: Path | None = None) -> list[SnapshotRecord]:
    """List recorded snapshots; missing archives are reported, never deleted."""
    directory = snapshots_dir(profile, state)
    if not directory.is_dir():
        return []
    records: list[SnapshotRecord] = []
    for meta in sorted(directory.glob("*.json")):
        name = meta.stem
        if name.startswith("."):
            continue
        archive = directory / f"{name}{ARCHIVE_SUFFIX}"
        records.append(_read_record(meta, directory, archive, name, profile))
    return sorted(records, key=lambda item: item.created_at)


def _read_record(meta: Path, directory: Path, archive: Path, name: str, profile: str) -> SnapshotRecord:
    present = archive.is_file()
    try:
        raw = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SnapshotRecord(
            name=name,
            profile=profile,
            created_at="unknown",
            archive_name=archive.name,
            archive_bytes=archive.stat().st_size if present else 0,
            archive_sha256="unavailable (metadata missing)",
            prefix_bytes=0,
            entry_count=0,
            flmint_version="unknown",
            archive_present=present,
        )
    return SnapshotRecord(
        name=str(raw.get("name", name)),
        profile=str(raw.get("profile", profile)),
        created_at=str(raw.get("created_at", "unknown")),
        archive_name=str(raw.get("archive_name", archive.name)),
        archive_bytes=int(raw.get("archive_bytes", 0)),
        archive_sha256=str(raw.get("archive_sha256", "")),
        prefix_bytes=int(raw.get("prefix_bytes", 0)),
        entry_count=int(raw.get("entry_count", 0)),
        flmint_version=str(raw.get("flmint_version", "unknown")),
        archive_present=present,
    )


def _load_record(profile: str, name: str, state: Path | None) -> tuple[SnapshotRecord, Path]:
    snapshot_name = _single_component(name, "snapshot name")
    directory = snapshots_dir(profile, state)
    archive = directory / f"{snapshot_name}{ARCHIVE_SUFFIX}"
    meta = directory / f"{snapshot_name}.json"
    if not archive.is_file():
        raise SnapshotError(
            f"snapshot '{snapshot_name}' not found for profile '{profile}'",
            next_actions=(
                f"list available names: flmint snapshot list --profile {profile}",
                f"create one first: flmint snapshot create --profile {profile} --name <name>",
            ),
        )
    return _read_record(meta, directory, archive, snapshot_name, profile), archive


def restore_snapshot(profile: str, name: str, state: Path | None = None) -> RestoreResult:
    """Restore a verified archive; the previous prefix is preserved, never deleted."""
    record, archive = _load_record(profile, name, state)
    if not record.archive_sha256 or record.archive_sha256 == "unavailable (metadata missing)":
        raise SnapshotError(
            f"snapshot '{name}' has no usable SHA-256 metadata; refusing to restore",
            next_actions=("restore is refused so an unverified archive is never executed against a prefix",),
        )
    actual_sha = _stream_sha256(archive)
    if actual_sha != record.archive_sha256:
        raise SnapshotError(
            f"snapshot '{name}' SHA-256 mismatch: archive may be corrupted or tampered",
            next_actions=(
                f"expected {record.archive_sha256}",
                f"actual   {actual_sha}",
                "re-create the snapshot from a known-good prefix if the archive is damaged",
            ),
        )

    directory = profile_dir(profile, state)
    final_prefix = prefix_path(profile, state)
    needed = max(record.prefix_bytes, archive.stat().st_size)
    _check_disk_space(profile, needed, directory)

    staging = directory / f".restore-{name}-{_stamp()}"
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            if any(member.name.split("/")[0] != "prefix" for member in members):
                raise SnapshotError(
                    f"snapshot '{name}' archive layout is unexpected (expected a single 'prefix' tree)",
                    next_actions=("refusing extraction outside the managed prefix path",),
                )
            tar.extractall(staging, filter="tar")
    except SnapshotError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except (OSError, tarfile.TarError) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise SnapshotError(
            f"snapshot '{name}' extraction failed: {exc}",
            next_actions=("check the archive and disk space, then retry",),
        ) from exc

    extracted = staging / "prefix"
    discarded: Path | None = None
    if final_prefix.exists():
        discarded = directory / f"prefix.discarded-{_stamp()}"
        os.replace(final_prefix, discarded)
    os.replace(extracted, final_prefix)
    shutil.rmtree(staging, ignore_errors=True)
    return RestoreResult(name=name, profile=profile, prefix_path=final_prefix, discarded_prefix=discarded)


def render_created(record: SnapshotRecord) -> str:
    return "\n".join(
        [
            f"snapshot created: {record.name} (profile: {record.profile})",
            f"  archive: {record.archive_name} ({record.archive_bytes} bytes, gz)",
            f"  sha256: {record.archive_sha256}",
            f"  prefix entries: {record.entry_count}, prefix bytes: {record.prefix_bytes}",
            "  no prefix files were modified or deleted",
        ]
    )


def render_list(profile: str, records: list[SnapshotRecord]) -> str:
    if not records:
        return f"no snapshots for profile '{profile}'"
    lines = [f"snapshots for profile '{profile}':"]
    for record in records:
        status = "ok" if record.archive_present else "MISSING ARCHIVE"
        lines.append(
            f"  - {record.name}: {record.created_at} | {record.archive_bytes} bytes | "
            f"{record.entry_count} entries | {status}"
        )
    return "\n".join(lines)


def render_restore(result: RestoreResult) -> str:
    lines = [
        f"snapshot restored: {result.name} -> {result.prefix_path}",
        "  archive SHA-256 verified before extraction",
    ]
    if result.discarded_prefix is not None:
        lines.append(f"  previous prefix preserved at: {result.discarded_prefix}")
        lines.append("  delete preserved prefixes manually only after you confirm the restore is good")
    return "\n".join(lines)
