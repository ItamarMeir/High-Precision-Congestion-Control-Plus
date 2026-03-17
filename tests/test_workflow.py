from __future__ import annotations

import unittest
from pathlib import Path

from hpcc_orchestrator.models import ResearchGoal, WorkflowStage
from hpcc_orchestrator.workflow import HPCCResearchWorkflow


class WorkflowTests(unittest.TestCase):
    def test_dry_run_halts_after_simulation_stage(self) -> None:
        workflow = HPCCResearchWorkflow(repo_root=Path(__file__).resolve().parents[1], dry_run=True)
        goal = ResearchGoal(
            prompt="Prototype a verifier-aware HPCC+ workflow",
            success_criteria="Dry-run reaches simulation evaluation cleanly",
            simulation_config="mix/configs/config_two_senders_per_node.txt",
        )

        state = workflow.run(goal)

        self.assertEqual(state.stage, WorkflowStage.HALT)
        self.assertIsNotNone(state.plan)
        self.assertIsNotNone(state.implementation)
        self.assertIsNotNone(state.verification)
        self.assertIsNotNone(state.review)
        self.assertIsNotNone(state.simulation)
        self.assertTrue(state.simulation.skipped)


if __name__ == "__main__":
    unittest.main()
