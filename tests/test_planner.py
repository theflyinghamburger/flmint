from __future__ import annotations

import unittest

import helpers

from flmint.doctor import HostFacts
from flmint.manifest import load_profile_file
from flmint.planner import GATE_FAIL, GATE_PASS, GATE_UNKNOWN, build_plan, evaluate_gates, render_plan


def host(
    pipewire_version: tuple[int, int, int] | None = None, *, raw_version: str | None = None
) -> HostFacts:
    facts = HostFacts(
        os={"NAME": "Ubuntu", "VERSION_ID": "26.10", "VERSION_CODENAME": "stonking"},
        kernel_release="7.3.0-10-generic",
        pipewire={
            "present": pipewire_version is not None,
            "version": list(pipewire_version) if pipewire_version else None,
            "raw_version": raw_version,
        },
        capabilities={"nvidia_gpu_present": True},
    )
    return facts


class PlannerTest(unittest.TestCase):
    def test_plan_without_installer_is_blocked_but_side_effect_free(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "stable.example.yaml")
        plan = build_plan(host((1, 6, 8), raw_version="1.6.8"), profile, installer=None)
        self.assertTrue(any("no --installer" in blocker for blocker in plan.blockers))
        verify_steps = [step for step in plan.steps if step.kind == "verify"]
        self.assertTrue(any(step.blocked for step in verify_steps))
        rendered = render_plan(plan)
        self.assertIn("side-effect-free", rendered)

    def test_plan_is_deterministic(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "stable.example.yaml")
        first = render_plan(build_plan(host((1, 6, 8), raw_version="1.6.8"), profile, installer=None))
        second = render_plan(build_plan(host((1, 6, 8), raw_version="1.6.8"), profile, installer=None))
        self.assertEqual(first, second)

    def test_pipeasio_gate_passes_on_modern_pipewire(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "experimental.example.yaml")
        gates = evaluate_gates(host((1, 6, 8), raw_version="1.6.8"), profile)
        self.assertEqual(gates[0].status, GATE_PASS)
        plan = build_plan(host((1, 6, 8), raw_version="1.6.8"), profile, installer=None)
        pipeasio_step = next(
            step for step in plan.steps if step.kind == "build" and "PipeASIO" in step.action
        )
        self.assertFalse(pipeasio_step.blocked)

    def test_pipeasio_gate_fails_on_old_pipewire(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "experimental.example.yaml")
        plan = build_plan(host((1, 0, 0), raw_version="1.0.0"), profile, installer=None)
        gates = plan.gates
        self.assertEqual(gates[0].status, GATE_FAIL)
        self.assertTrue(any("pipeasio" in blocker for blocker in plan.blockers))

    def test_pinned_stable_profile_emits_no_unpinned_warnings(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "stable.yaml")
        plan = build_plan(host((1, 6, 8), raw_version="1.6.8"), profile, installer=None)
        unpinned = [w for w in plan.warnings if "unpinned" in w or "no SHA-256" in w]
        self.assertEqual(unpinned, [])
        self.assertIn("DAW-GE-Proton DAW-GE-Proton11-6c", render_plan(plan))

    def test_prefix_creation_is_approval_gated(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "stable.yaml")
        plan = build_plan(host((1, 6, 8), raw_version="1.6.8"), profile, installer=None)
        prefix_step = next(step for step in plan.steps if step.kind == "create-prefix")
        self.assertTrue(prefix_step.approval_required)
        auto_kinds = {step.kind for step in plan.steps if not step.approval_required}
        self.assertEqual(auto_kinds, {"managed-dir", "snapshot"})

    def test_next_actions_track_pinned_state(self) -> None:
        facts = host((1, 6, 8), raw_version="1.6.8")
        pinned = build_plan(
            facts, load_profile_file(helpers.REPO_ROOT / "profiles" / "stable.yaml"), installer=None
        )
        self.assertFalse(any("Pin exact component" in action for action in pinned.next_actions))
        unpinned = build_plan(
            facts,
            load_profile_file(helpers.REPO_ROOT / "profiles" / "experimental.example.yaml"),
            installer=None,
        )
        self.assertTrue(any("Pin exact component" in action for action in unpinned.next_actions))

    def test_gate_unknown_when_pipewire_absent(self) -> None:
        profile = load_profile_file(helpers.REPO_ROOT / "profiles" / "experimental.example.yaml")
        gates = evaluate_gates(host(None, raw_version=None), profile)
        self.assertEqual(gates[0].status, GATE_UNKNOWN)


if __name__ == "__main__":
    unittest.main()
