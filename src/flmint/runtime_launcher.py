"""Launch is Phase 2+: requires a pinned runner and an existing isolated prefix."""

from __future__ import annotations

from .errors import NotYetImplementedError


def launch(profile: str) -> None:
    raise NotYetImplementedError(
        f"launch --profile {profile} is not implemented (Phase 2)",
        next_actions=(
            "requires a pinned runner + created prefix recorded in the profile lock",
            "launch must set WINEPREFIX explicitly and never touch ~/.wine",
        ),
    )
