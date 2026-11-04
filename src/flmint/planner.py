"""Deterministic, side-effect-free install planning against profile gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .audio import PIPEWIRE_PIPEASIO_MIN
from .doctor import HostFacts
from .errors import FlmintUsageError
from .installer import InstallerInfo
from .manifest import Component, Gate, Profile
from .runtime import CANDIDATE_VERSIONS, MANAGED_STATE_DIRS

GATE_PASS = "pass"
GATE_FAIL = "fail"
GATE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class GateResult:
    id: str
    status: str
    detail: str


@dataclass(frozen=True)
class Step:
    seq: int
    kind: str
    action: str
    approval_required: bool
    blocked: bool
    depends_on: tuple[int, ...]
    notes: str


@dataclass
class Plan:
    profile: str
    host_summary: str
    installer_lines: list[str]
    estimated_disk_mib: int
    managed_dirs: list[str]
    gates: list[GateResult]
    steps: list[Step]
    blockers: list[str]
    warnings: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_gates(host: HostFacts, profile: Profile) -> list[GateResult]:
    results: list[GateResult] = []
    for gate in profile.gates:
        results.append(_evaluate_gate(host, gate))
    return results


def _evaluate_gate(host: HostFacts, gate: Gate) -> GateResult:
    if gate.kind == "pipewire_min":
        minimum = gate.min_version or PIPEWIRE_PIPEASIO_MIN
        raw = host.pipewire.get("version")
        current = tuple(raw) if raw else None
        minimum_text = ".".join(str(part) for part in minimum)
        if current is None:
            return GateResult(gate.id, GATE_UNKNOWN, "PipeWire version not detected on this host")
        current_text = ".".join(str(part) for part in current)
        if current >= minimum:
            return GateResult(gate.id, GATE_PASS, f"PipeWire {current_text} >= {minimum_text}")
        return GateResult(
            gate.id,
            GATE_FAIL,
            f"PipeWire {current_text} < {minimum_text}: PipeASIO build prerequisite unmet on this host",
        )
    raise FlmintUsageError(f"unsupported gate kind '{gate.kind}'")  # guarded by manifest validation


def _pin_warnings(component: Component, warnings: list[str]) -> None:
    if component.version is None:
        warnings.append(
            f"component '{component.id}' version is unpinned: "
            "pin exact release + SHA-256 after manual review"
        )
    if component.sha256 is None and component.kind in {"download", "build"}:
        warnings.append(f"component '{component.id}' has no SHA-256 pinned yet")
    if component.kind == "download" and (component.asset is None or component.download_url is None):
        warnings.append(
            f"component '{component.id}' is not fetchable by flmint: pin asset + download_url "
            "(+ size_bytes) so a digest-gated fetch is possible"
        )


def _component_plan(
    component: Component,
    gate_result: GateResult | None,
    warnings: list[str],
    blockers: list[str],
) -> tuple[str, str, bool]:
    blocked = gate_result is not None and gate_result.status in (GATE_FAIL, GATE_UNKNOWN)
    candidate = CANDIDATE_VERSIONS.get(component.id)
    pinned = component.version or (candidate.version if candidate is not None else None)
    _pin_warnings(component, warnings)

    notes = component.notes or ""
    if blocked and gate_result is not None:
        note_suffix = f"blocked by gate {gate_result.id}: {gate_result.detail}"
        notes = f"{notes} | {note_suffix}".strip(" |")
    if blocked:
        blocker_detail = gate_result.detail if gate_result else "gate"
        blockers.append(f"component '{component.id}' blocked by gate ({blocker_detail})")

    if component.source_url:
        source = component.source_url
    elif candidate is not None:
        source = candidate.source_url
    else:
        source = component.name

    version = pinned or "<VERSION-TO-PIN>"
    if component.kind == "build":
        version = pinned or "<COMMIT-TO-PIN>"

    if component.kind == "flatpak":
        action = f"flatpak --user install {component.name} {version}"
    elif component.kind == "download":
        action = (
            f"Download {component.name} {version} from {source} "
            "and verify SHA-256 before any use"
        )
    else:
        action = (
            f"Build {component.name} {version} from {source} "
            "into ~/.local/opt/flmint/<component>/<version>"
        )

    return action, notes, blocked


def build_plan(host: HostFacts, profile: Profile, installer: InstallerInfo | None) -> Plan:
    gates = evaluate_gates(host, profile)
    gate_by_component: dict[str, GateResult] = {}
    for gate, result in zip(profile.gates, gates, strict=True):
        if gate.applies_to:
            gate_by_component[gate.applies_to] = result

    blockers: list[str] = list(host.blockers)
    warnings: list[str] = list(host.warnings)
    if installer is None and profile.installer_required:
        blockers.append(
            "no --installer supplied and none found in checked dirs: "
            "the official FL Studio .exe is a Phase 2 gate"
        )

    steps: list[Step] = []

    def add(kind: str, action: str, *, approval: bool, notes: str = "", blocked: bool = False) -> None:
        depends_on = tuple(step.seq for step in steps) if steps else ()
        steps.append(
            Step(
                seq=len(steps) + 1,
                kind=kind,
                action=action,
                approval_required=approval,
                blocked=blocked,
                depends_on=depends_on,
                notes=notes,
            )
        )

    add(
        "managed-dir",
        "Create project-managed state dirs: " + ", ".join(MANAGED_STATE_DIRS),
        approval=False,
        notes="project-managed user paths only; never ~/.wine or system locations",
    )

    if installer is not None:
        installer_sha = installer.sha256[:16]
        action = (
            f"Verify installer {installer.display_path} "
            f"(SHA-256 {installer_sha}..., PE {installer.pe_arch})"
        )
        add(
            "verify",
            action,
            approval=False,
            notes="already computed read-only; hash must match the Image-Line published checksum",
        )
    else:
        add(
            "verify",
            "Obtain official FL Studio Windows installer from image-line.com and record its SHA-256",
            approval=True,
            notes="human download step; flmint never downloads or executes installers without approval",
            blocked=True,
        )

    for component in profile.components:
        action, notes, blocked = _component_plan(
            component,
            gate_by_component.get(component.id),
            warnings,
            blockers,
        )
        add(component.kind, action, approval=True, notes=notes, blocked=blocked)

    add(
        "create-prefix",
        f"Create isolated Windows prefix under ~/.local/share/flmint/profiles/{profile.name}/prefix",
        approval=True,
        notes=(
            "explicit WINEPREFIX per invocation; no global Wine environment leakage; "
            "prefix creation is an explicit human approval gate, taken after the pinned plan sign-off"
        ),
    )
    add(
        "snapshot",
        f"Baseline snapshot of the new prefix "
        f"(flmint snapshot create --profile {profile.name} --name baseline)",
        approval=False,
        blocked=True,
        notes=(
            "snapshot module is implemented and tested, but refuses until the prefix exists; "
            "prefix creation is still an approval-gated Phase 2 step"
        ),
    )
    add(
        "run-installer",
        "Run the official FL Studio installer inside the isolated prefix, human-supervised",
        approval=True,
        notes="Phase 2 approval gate: flmint refuses this automatically",
        blocked=installer is None,
    )
    add(
        "activation",
        "Legitimate Image-Line account activation inside the prefix (document failure modes; no bypassing)",
        approval=True,
        notes="WebView2/login issues are logged, not circumvented",
    )
    add(
        "audio-baseline",
        "Configure FL Studio built-in ASIO/Wine audio as the initial baseline (Phase 3 starts)",
        approval=True,
        notes="no PipeASIO/WineASIO until measured on the experimental prefix",
    )
    for item in profile.human_checklist:
        add("human-checklist", item, approval=True, notes=f"from {profile.source_file}")

    host_summary = _host_summary(host)
    next_actions = ["Review this plan with a human; approve or reject each approval-gated step."]
    if any("unpinned" in warning or "no SHA-256" in warning for warning in warnings):
        next_actions.append(
            "Pin exact component versions + SHA-256 in the profile before any install step runs."
        )
    next_actions.append("Confirm the installer SHA-256 against the Image-Line download page.")
    if installer is None:
        next_actions.insert(0, "Supply the official FL Studio installer path via --installer.")

    installer_lines = (
        installer.summary_lines()
        if installer is not None
        else ["installer: absent (Phase 2 prerequisite)"]
    )
    return Plan(
        profile=profile.name,
        host_summary=host_summary,
        installer_lines=installer_lines,
        estimated_disk_mib=profile.min_disk_mib,
        managed_dirs=list(MANAGED_STATE_DIRS),
        gates=gates,
        steps=steps,
        blockers=blockers,
        warnings=warnings,
        next_actions=next_actions,
    )


def _host_summary(host: HostFacts) -> str:
    os_name = host.os.get("NAME", "?")
    version = host.os.get("VERSION_ID", "")
    kernel = host.kernel_release or "?"
    pipewire = host.pipewire.get("raw_version") or "absent"
    gpu = "nvidia ok" if host.capabilities.get("nvidia_gpu_present") else "no NVIDIA detected"
    return f"{os_name} {version} / kernel {kernel} / PipeWire {pipewire} / {gpu}"


def render_plan(plan: Plan) -> str:
    lines = [f"flmint plan — profile: {plan.profile} (dry, nothing executed)", "=" * 60]
    lines.append(f"host: {plan.host_summary}")
    lines.append(f"estimated disk: {plan.estimated_disk_mib} MiB on $HOME mount")
    lines.append("managed dirs (writes are limited to these):")
    lines.extend(f"  - {d}" for d in plan.managed_dirs)
    lines.append("installer:")
    lines.extend(f"  {line}" for line in plan.installer_lines)
    if plan.gates:
        lines.append("gates:")
        for gate in plan.gates:
            lines.append(f"  {gate.id}: {gate.status} — {gate.detail}")
    lines.append("steps:")
    for step in plan.steps:
        flag = "[approval]" if step.approval_required else "[auto]"
        blocked = " [BLOCKED]" if step.blocked else ""
        lines.append(f"  {step.seq:2d}. {flag}{blocked} ({step.kind}) {step.action}")
        if step.notes:
            lines.append(f"      notes: {step.notes}")
        if step.depends_on:
            lines.append(f"      depends on: {', '.join(str(dep) for dep in step.depends_on)}")
    if plan.blockers:
        lines.append("blockers:")
        lines.extend(f"  - {b}" for b in plan.blockers)
    if plan.warnings:
        lines.append("warnings:")
        lines.extend(f"  - {w}" for w in plan.warnings)
    lines.append("next actions:")
    lines.extend(f"  - {a}" for a in plan.next_actions)
    lines.append("(plan is side-effect-free: no downloads, prefixes, packages, or installer execution)")
    return "\n".join(lines)
