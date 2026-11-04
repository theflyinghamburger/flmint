"""Diagnostics packaging (Phase 2+). Stub refuses until sanitization is implemented."""

from __future__ import annotations

from .errors import NotYetImplementedError


def collect_diagnostics(profile: str, output: str) -> None:
    raise NotYetImplementedError(
        f"diagnose for profile '{profile}' -> {output} is not implemented (Phase 2+)",
        next_actions=(
            "implementation must sanitize usernames, tokens, serials, and private paths before packaging",
        ),
    )
