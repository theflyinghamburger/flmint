"""Structured flmint errors: message + concrete next actions, no stack traces."""

from __future__ import annotations


class FlmintError(Exception):
    def __init__(self, message: str, *, next_actions: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.next_actions = next_actions


class FlmintUsageError(FlmintError):
    pass


class ManifestError(FlmintError):
    pass


class InstallerError(FlmintError):
    pass


class ApprovalRequiredError(FlmintError):
    pass


class NotYetImplementedError(FlmintError):
    pass


class SnapshotError(FlmintError):
    pass


class DownloadError(FlmintError):
    pass
