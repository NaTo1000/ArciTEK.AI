"""Tests for HIAI intent memory and PECS move selection."""

import tempfile
import unittest
from pathlib import Path

from arcitek_core.robotics_plan import (
    IntentAlignmentEngine,
    KnowledgeRepository,
    ProjectRepository,
)
from arcitek_core.robotics_plan.intent import BUILT_IN_GUARDRAILS
from arcitek_core.robotics_plan.storage import SQLiteStore


class IntentAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "intent.db"
        self.store = SQLiteStore(self.database)
        self.projects = ProjectRepository(store=self.store)
        self.knowledge = KnowledgeRepository(store=self.store)
        self.engine = IntentAlignmentEngine(self.knowledge)
        self.project = self.projects.create_project(
            name="Aligned Build", author="operator"
        )

    def tearDown(self):
        self.store.close()
        self.temporary_directory.cleanup()

    def _capture(self):
        return self.engine.capture_intent(
            project_id=self.project["id"],
            actor="operator",
            reason="Define the build target",
            goal="Build a safe warehouse arm",
            success_criteria=["Lift 5kg", "Stop on obstruction"],
            constraints=["Remain within the work cell"],
            guardrails=["Never bypass the emergency stop"],
            out_of_scope=["Outdoor operation"],
        )

    def test_intent_versions_are_append_only_and_inherit_guardrails(self):
        first = self._capture()
        second = self.engine.capture_intent(
            project_id=self.project["id"],
            actor="operator",
            reason="Clarify payload",
            goal="Build a safe warehouse arm",
            success_criteria=["Lift 7kg", "Stop on obstruction"],
        )

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.engine.get_active_intent(self.project["id"])["id"], second["id"])
        self.assertEqual(len(self.engine.list_intents(self.project["id"])), 2)
        for guardrail in BUILT_IN_GUARDRAILS:
            self.assertIn(guardrail, first["guardrails"])
            self.assertIn(guardrail, second["guardrails"])

    def test_pecs_selects_highest_aligned_unblocked_move(self):
        self._capture()
        evaluation = self.engine.evaluate_moves(
            project_id=self.project["id"],
            actor="planner",
            reason="Choose the next build move",
            candidates=[
                {
                    "id": "unsafe-fast",
                    "description": "Skip interlocks to move quickly",
                    "satisfies": ["Lift 5kg", "Stop on obstruction"],
                    "guardrail_violations": ["Bypasses emergency stop"],
                    "confidence": 0.9,
                    "predicted_error": 0.1,
                },
                {
                    "id": "aligned",
                    "description": "Prototype with interlocks and load test",
                    "satisfies": ["Lift 5kg", "Stop on obstruction"],
                    "confidence": 0.8,
                    "predicted_error": 0.15,
                },
                {
                    "id": "partial",
                    "description": "Test only the lift",
                    "satisfies": ["Lift 5kg"],
                    "confidence": 0.9,
                    "predicted_error": 0.1,
                },
            ],
        )

        self.assertEqual(evaluation["selected_candidate_id"], "aligned")
        self.assertTrue(evaluation["requires_human_review"])
        unsafe = next(
            item for item in evaluation["candidates"] if item["id"] == "unsafe-fast"
        )
        self.assertTrue(unsafe["blocked"])
        partial = next(
            item for item in evaluation["candidates"] if item["id"] == "partial"
        )
        self.assertTrue(partial["drift_detected"])

    def test_outcome_memory_calibrates_later_predictions_and_persists(self):
        self._capture()
        first = self.engine.evaluate_moves(
            project_id=self.project["id"],
            actor="planner",
            reason="Initial prediction",
            candidates=[
                {
                    "id": "prototype",
                    "description": "Build a guarded prototype",
                    "satisfies": ["Lift 5kg", "Stop on obstruction"],
                    "confidence": 0.8,
                    "predicted_error": 0.1,
                }
            ],
        )
        self.engine.record_outcome(
            project_id=self.project["id"],
            actor="reviewer",
            reason="Observed test result",
            evaluation_id=first["id"],
            actual_error=0.4,
        )
        second = self.engine.evaluate_moves(
            project_id=self.project["id"],
            actor="planner",
            reason="Calibrated prediction",
            candidates=[
                {
                    "id": "prototype-v2",
                    "description": "Build another guarded prototype",
                    "satisfies": ["Lift 5kg", "Stop on obstruction"],
                    "confidence": 0.8,
                    "predicted_error": 0.1,
                }
            ],
        )
        self.assertAlmostEqual(second["calibration_error"], 0.3)
        self.assertAlmostEqual(second["candidates"][0]["adjusted_error"], 0.4)

        self.store.close()
        restarted_store = SQLiteStore(self.database)
        restarted = IntentAlignmentEngine(
            KnowledgeRepository(store=restarted_store)
        )
        self.assertEqual(
            restarted.get_active_intent(self.project["id"])["goal"],
            "Build a safe warehouse arm",
        )
        restarted_store.close()
        self.store = SQLiteStore(":memory:")


if __name__ == "__main__":
    unittest.main()
