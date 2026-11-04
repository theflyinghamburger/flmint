"""Phase 1/2 boundary: real installs are refused until snapshots + human approval exist."""

from __future__ import annotations

from .errors import ApprovalRequiredError
from .planner import Plan, render_plan


def perform_install(plan: Plan) -> None:
    """Refuse to perform any mutation. Kept as the explicit approval boundary."""
    raise ApprovalRequiredError(
        "flmint install without --dry-run is not enabled: Phase 2 requires explicit human approval",
        next_actions=(
            "review: flmint plan --installer PATH --profile <name>",
            "review: flmint install --installer PATH --profile <name> --dry-run",
            "only after human approval, implement Phase 2 install steps behind snapshots",
        ),
    )


def render_dry_run(plan: Plan) -> str:
    rendered = render_plan(plan)
    return rendered.replace("flmint plan —", "flmint install --dry-run —") + "\n(no mutations performed)"
