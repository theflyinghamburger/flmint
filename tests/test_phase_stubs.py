from __future__ import annotations

import unittest

from flmint.benchmarks import bench_ai, bench_audio
from flmint.diagnostics import collect_diagnostics
from flmint.errors import ApprovalRequiredError, NotYetImplementedError
from flmint.installer_runner import perform_install, render_dry_run
from flmint.planner import GateResult, Plan, Step
from flmint.runtime import CANDIDATE_STATUS, CANDIDATE_VERSIONS
from flmint.runtime_launcher import launch


def empty_plan() -> Plan:
    return Plan(
        profile="stable",
        host_summary="test host",
        installer_lines=["installer: absent"],
        estimated_disk_mib=1,
        managed_dirs=[],
        gates=[],
        steps=[Step(1, "verify", "verify", True, True, (), "")],
        blockers=["no installer"],
        warnings=["unpinned"],
        next_actions=["review"],
    )


class PhaseStubsTest(unittest.TestCase):
    def test_all_future_phase_commands_refuse(self) -> None:
        calls = (
            lambda: launch("stable"),
            lambda: collect_diagnostics("stable", "reports/x.tar.gz"),
            lambda: bench_audio("stable", 48000, "1024,512"),
            lambda: bench_ai(None, "llamacpp"),
            lambda: bench_ai("/home/user/model.gguf", "llamacpp"),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(NotYetImplementedError):
                call()

    def test_install_refuses_without_dry_run(self) -> None:
        with self.assertRaises(ApprovalRequiredError):
            perform_install(empty_plan())

    def test_dry_run_renders_no_mutations(self) -> None:
        rendered = render_dry_run(empty_plan())
        self.assertIn("flmint install --dry-run", rendered)
        self.assertIn("no mutations performed", rendered)

    def test_gate_result_shape(self) -> None:
        gate = GateResult("gate", "pass", "ok")
        self.assertEqual(gate.id, "gate")
        self.assertEqual(gate.status, "pass")

    def test_candidates_are_unverified(self) -> None:
        self.assertTrue(CANDIDATE_VERSIONS)
        for candidate in CANDIDATE_VERSIONS.values():
            self.assertEqual(candidate.status, CANDIDATE_STATUS)
            self.assertIsNone(candidate.version)
            self.assertTrue(candidate.source_url.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
