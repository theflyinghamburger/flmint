"""Candidate pinned runtime versions as of 2026-11-03.

Status of every entry is CANDIDATE / UNVERIFIED: nothing was downloaded, built, or
installed by the Phase 0/1 work order. Exact pins + SHA-256s are recorded only after
manual upstream review (HANDOFF.md section 4 and 10.4). See docs/upstream-research.md.

Approved pins live in the profiles (profiles/stable.yaml, reports/decisions.md D1-D3) and
take precedence here; these entries are only a fallback for unpinned profiles.
"""

from __future__ import annotations

from dataclasses import dataclass

CANDIDATE_STATUS = "candidate-unverified"


@dataclass(frozen=True)
class Candidate:
    version: str | None
    source_url: str
    status: str = CANDIDATE_STATUS


CANDIDATE_VERSIONS: dict[str, Candidate] = {
    "bottles": Candidate(
        version=None,
        source_url="https://flathub.org/apps/com.usebottles.bottles",
    ),
    "daw-ge-proton": Candidate(
        version=None,
        source_url="https://github.com/KitsuneDev/daw-proton-ge/releases",
    ),
    "pipeasio": Candidate(
        version=None,
        source_url="https://github.com/M0n7y5/pipeasio",
    ),
    "wineasio": Candidate(
        version=None,
        source_url="https://github.com/wineasio/wineasio",
    ),
}

MANAGED_STATE_DIRS = (
    "~/.local/share/flmint",
    "~/.local/state/flmint",
    "~/.local/opt/flmint",
)
