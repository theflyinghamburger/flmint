"""Managed-state path helpers and atomic writes."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import FlmintUsageError


def safe_relative_path(relative: str) -> Path:
    """Reject traversal/absolute/NUL paths before writing managed state."""
    if not relative or "\x00" in relative:
        raise FlmintUsageError(
            "path is empty or contains NUL byte", next_actions=("use a plain relative path",)
        )
    path = Path(relative)
    if path.is_absolute():
        raise FlmintUsageError(
            f"absolute path not allowed here: {relative}", next_actions=("use a relative path",)
        )
    if any(part == ".." for part in path.parts):
        raise FlmintUsageError(
            f"path traversal not allowed: {relative}",
            next_actions=("keep writes inside the repository or ~/.local/share/flmint",),
        )
    return path


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp-{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
