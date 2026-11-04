"""flmint: non-destructive FL Studio on Linux compatibility toolkit (Phase 0/1)."""

from __future__ import annotations

from .errors import (
    ApprovalRequiredError,
    FlmintError,
    FlmintUsageError,
    InstallerError,
    ManifestError,
    NotYetImplementedError,
    SnapshotError,
)

__version__ = "0.1.0"

__all__ = [
    "ApprovalRequiredError",
    "FlmintError",
    "FlmintUsageError",
    "InstallerError",
    "ManifestError",
    "NotYetImplementedError",
    "SnapshotError",
    "__version__",
]
