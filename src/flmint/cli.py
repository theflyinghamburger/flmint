"""flmint CLI: doctor | plan | install (--dry-run enforced) | stubs for later phases."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .benchmarks import bench_ai, bench_audio
from .diagnostics import collect_diagnostics
from .doctor import collect_facts, compare_facts, render_compare, render_text
from .downloads import (
    artifact_from_component,
    build_record,
    extract_archive,
    fetch_artifact,
    opt_root,
    outcome_from_local,
    render_provenance,
    write_provenance,
)
from .errors import ApprovalRequiredError, FlmintError, FlmintUsageError
from .installer import validate_installer
from .installer_runner import perform_install, render_dry_run
from .manifest import Component, Profile, load_profile_file
from .planner import Plan, build_plan, render_plan
from .probe import CommandProber
from .runtime_launcher import launch
from .snapshots import (
    create_snapshot,
    list_snapshots,
    render_created,
    render_list,
    render_restore,
    restore_snapshot,
)
from .state import atomic_write_text, safe_relative_path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _os_release_file() -> Path:
    # Test hook only; production uses the standard system file.
    return Path(os.environ.get("FLMINT_OS_RELEASE", "/etc/os-release"))


def _profiles_dir() -> Path:
    return REPO_ROOT / "profiles"


def find_profile(name: str, explicit_file: str | None) -> Profile:
    if explicit_file:
        return load_profile_file(Path(explicit_file))
    directory = _profiles_dir()
    for candidate in (directory / f"{name}.yaml", directory / f"{name}.example.yaml"):
        if candidate.is_file():
            return load_profile_file(candidate)
    available = sorted(p.name for p in directory.glob("*.yaml")) if directory.is_dir() else []
    raise FlmintError(
        f"profile '{name}' not found in {directory}",
        next_actions=(
            f"available profiles: {', '.join(available) or 'none'}",
            "use --profile-file /path/to/profile.yaml",
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flmint", description="FL Studio Linux compatibility toolkit (Phase 0/1)"
    )
    parser.add_argument("--version", action="version", version=f"flmint {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="read-only host inventory (never mutates anything)")
    doctor.add_argument("--format", choices=("text", "json"), default="text")
    doctor.add_argument("--save", help="also write the JSON audit to this repo-relative path")
    doctor.add_argument("--compare", help="compare current facts with a saved doctor JSON audit")

    plan = sub.add_parser("plan", help="deterministic side-effect-free install plan")
    plan.add_argument("--installer", help="path to the official FL Studio Windows .exe (optional)")
    plan.add_argument("--profile", default="stable")
    plan.add_argument("--profile-file", help="explicit profile YAML path")
    plan.add_argument("--format", choices=("text", "json"), default="text")

    install = sub.add_parser("install", help="planned install; --dry-run only until Phase 2 approval")
    install.add_argument("--installer")
    install.add_argument("--profile", default="stable")
    install.add_argument("--profile-file")
    install.add_argument("--dry-run", action="store_true")

    verify = sub.add_parser(
        "verify",
        help="re-hash an already stored pinned artifact and rewrite its provenance record",
    )
    verify.add_argument("--profile", default="stable")
    verify.add_argument("--profile-file")
    verify.add_argument("--component", required=True)
    verify.add_argument("--provenance", help="repo-relative provenance report path")

    fetch = sub.add_parser(
        "fetch",
        help="download one pinned artifact into ~/.local/opt/flmint; refuses without --approve",
    )
    fetch.add_argument("--profile", default="stable")
    fetch.add_argument("--profile-file")
    fetch.add_argument("--component", required=True)
    fetch.add_argument("--approve", action="store_true")
    fetch.add_argument("--extract", action="store_true")
    fetch.add_argument("--provenance", help="repo-relative provenance report path")

    launch_p = sub.add_parser("launch", help="Phase 2 stub")
    launch_p.add_argument("--profile", default="stable")

    snapshot_p = sub.add_parser(
        "snapshot", help="prefix snapshots (managed profile paths only; refuses until a prefix exists)"
    )
    snapshot_sub = snapshot_p.add_subparsers(dest="snapshot_command", required=True)
    for name in ("create", "list", "restore"):
        sp = snapshot_sub.add_parser(name)
        sp.add_argument("--profile", default="stable")
        if name != "list":
            sp.add_argument("--name", required=True)

    diagnose_p = sub.add_parser("diagnose", help="Phase 2+ stub")
    diagnose_p.add_argument("--profile", default="stable")
    diagnose_p.add_argument("--output", default="./reports/diagnostics.tar.gz")

    bench_p = sub.add_parser("bench", help="Phase 3/5 stubs")
    bench_sub = bench_p.add_subparsers(dest="bench_kind", required=True)
    audio_p = bench_sub.add_parser("audio")
    audio_p.add_argument("--profile", default="stable")
    audio_p.add_argument("--sample-rate", type=int, default=48000)
    audio_p.add_argument("--buffers", default="1024,512,256")
    ai_p = bench_sub.add_parser("ai")
    ai_p.add_argument("--model")
    ai_p.add_argument("--backend", default="llamacpp")

    return parser


def _make_plan(args: argparse.Namespace) -> Plan:
    profile = find_profile(args.profile, args.profile_file)
    prober = CommandProber()
    host = collect_facts(prober, home=Path.home(), os_release_file=_os_release_file())
    installer = None
    if args.installer:
        installer = validate_installer(Path(args.installer), home=Path.home())
    return build_plan(host, profile, installer)


def _run_doctor(args: argparse.Namespace) -> int:
    host = collect_facts(CommandProber(), home=Path.home(), os_release_file=_os_release_file())
    payload = host.to_json()
    exit_code = 0
    if args.compare:
        baseline = safe_relative_path(args.compare).read_text(encoding="utf-8")
        comparison = compare_facts(host, baseline)
        exit_code = 1 if comparison["changed"] else 0
        if args.format == "json":
            payload = json.dumps({"current": json.loads(payload), "comparison": comparison}, indent=2)
        else:
            payload = f"{render_text(host)}\n\n{render_compare(comparison)}"
    if args.format == "json":
        print(payload)
    else:
        print(payload)
    if args.save:
        target = safe_relative_path(args.save)
        saved = payload if args.compare and args.format == "json" else host.to_json()
        atomic_write_text(target, saved + "\n")
    return exit_code


def _run_plan(args: argparse.Namespace) -> int:
    plan = _make_plan(args)
    if args.format == "json":
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        print(render_plan(plan))
    return 0


def _run_install(args: argparse.Namespace) -> int:
    plan = _make_plan(args)
    if args.dry_run:
        print(render_dry_run(plan))
        return 0
    perform_install(plan)
    return 0


def _component_for(args: argparse.Namespace) -> Component:
    profile = find_profile(args.profile, args.profile_file)
    component = next((item for item in profile.components if item.id == args.component), None)
    if component is None:
        known = ", ".join(item.id for item in profile.components) or "none"
        raise FlmintUsageError(
            f"component '{args.component}' is not in profile '{profile.name}'",
            next_actions=(f"components in this profile: {known}",),
        )
    return component


def _run_fetch(args: argparse.Namespace) -> int:
    if not args.approve:
        raise ApprovalRequiredError(
            "fetch is refused without --approve: every download is an explicit human approval gate",
            next_actions=(
                f"review first: flmint plan --profile {args.profile}",
                f"then re-run: flmint fetch --profile {args.profile} --component {args.component} --approve",
            ),
        )
    component = _component_for(args)
    artifact = artifact_from_component(component)
    dest_dir = opt_root() / component.id
    report_relative = args.provenance or f"reports/provenance-{component.id}.json"

    if (dest_dir / artifact.asset).is_file():
        outcome = outcome_from_local(artifact, dest_dir)
    else:
        outcome = fetch_artifact(artifact, dest_dir)

    extracted: Path | None = None
    if args.extract:
        extracted = dest_dir / artifact.version
        extract_archive(outcome.target, extracted)
        outcome = replace(outcome, extracted_to=extracted)

    record = build_record(outcome, extracted)
    saved = write_provenance(record, report_relative)
    print(render_provenance(record))
    print(f"  provenance record: {saved}")
    return 0


def _run_verify(args: argparse.Namespace) -> int:
    component = _component_for(args)
    artifact = artifact_from_component(component)
    dest_dir = opt_root() / component.id
    outcome = outcome_from_local(artifact, dest_dir)
    record = build_record(outcome, outcome.extracted_to)
    saved = write_provenance(record, args.provenance or f"reports/provenance-{component.id}.json")
    print(render_provenance(record))
    print(f"  provenance record: {saved}")
    return 0


def _run_stub(args: argparse.Namespace) -> int:
    if args.command == "launch":
        launch(args.profile)
    elif args.command == "snapshot":
        if args.snapshot_command == "create":
            print(render_created(create_snapshot(args.profile, args.name)))
        elif args.snapshot_command == "list":
            print(render_list(args.profile, list_snapshots(args.profile)))
        else:
            print(render_restore(restore_snapshot(args.profile, args.name)))
    elif args.command == "diagnose":
        collect_diagnostics(args.profile, args.output)
    elif args.command == "bench":
        if args.bench_kind == "audio":
            bench_audio(args.profile, args.sample_rate, args.buffers)
        else:
            bench_ai(args.model, args.backend)
    return 0


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "plan":
        return _run_plan(args)
    if args.command == "install":
        return _run_install(args)
    if args.command == "verify":
        return _run_verify(args)
    if args.command == "fetch":
        return _run_fetch(args)
    if args.command in {"launch", "snapshot", "diagnose", "bench"}:
        return _run_stub(args)
    raise FlmintError(f"unhandled command '{args.command}'")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except FlmintError as exc:
        print(f"flmint error: {exc.message}", file=sys.stderr)
        for action in exc.next_actions:
            print(f"  next action: {action}", file=sys.stderr)
        return 2
