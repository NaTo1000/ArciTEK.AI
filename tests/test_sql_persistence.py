"""Persistence and append-only guarantees for the SQLite control plane."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from arcitek_core.robotics_plan import (
    ExpertPlanOrchestrator,
    KnowledgeRepository,
    ProjectRepository,
)
from arcitek_core.robotics_plan.storage import SQLiteStore


class SQLitePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "arcitek.db"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_project_revision_approval_and_events_survive_restart(self):
        first = ProjectRepository(self.database)
        project = first.create_project(
            name="Persistent Arm",
            author="alice",
            requirements=["Retain history"],
        )
        first.create_revision(
            project["id"],
            author="bob",
            message="Add requirement",
            requirements=["Retain history", "Persist after restart"],
        )
        first.approve_revision(
            project["id"],
            2,
            approver="lead",
            decision="approved",
        )
        first.store.close()

        second = ProjectRepository(self.database)
        loaded = second.get_project(project["id"])
        self.assertEqual(loaded["current_revision"], 2)
        self.assertEqual(loaded["approval_status"], "approved")
        self.assertEqual(len(second.list_revisions(project["id"])), 2)
        self.assertEqual(len(second.list_approvals(project["id"])), 1)
        self.assertEqual(
            {event["action"] for event in second.list_events(project["id"])},
            {"project.created", "revision.created", "revision.approved"},
        )
        second.store.close()

    def test_database_triggers_reject_revision_and_audit_rewrites(self):
        repository = ProjectRepository(self.database)
        project = repository.create_project(name="Immutable", author="alice")
        with repository.store.transaction() as connection:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                connection.execute(
                    """
                    UPDATE revisions SET message = 'rewritten'
                    WHERE project_id = ? AND number = 1
                    """,
                    (project["id"],),
                )
        with repository.store.transaction() as connection:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                connection.execute(
                    "DELETE FROM audit_events WHERE project_id = ?",
                    (project["id"],),
                )
        repository.store.close()

    def test_concurrent_writers_allocate_sequential_revisions(self):
        first = ProjectRepository(self.database)
        project = first.create_project(name="Concurrent", author="alice")
        second = ProjectRepository(self.database)
        repositories = [first, second]

        def create_revision(index):
            return repositories[index % 2].create_revision(
                project["id"],
                author=f"writer-{index}",
                message=f"revision {index}",
            )["number"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            numbers = list(pool.map(create_revision, range(12)))

        self.assertEqual(sorted(numbers), list(range(2, 14)))
        self.assertEqual(len(first.list_revisions(project["id"])), 13)
        first.store.close()
        second.store.close()

    def test_plans_tasks_approvals_and_activity_survive_restart(self):
        store = SQLiteStore(self.database)
        repository = ProjectRepository(store=store)
        project = repository.create_project(name="Planned", author="alice")
        snapshot = repository.get_revision(project["id"], 1)
        orchestrator = ExpertPlanOrchestrator(workers=2, store=store)
        plan = orchestrator.create_plan(
            project_id=project["id"],
            revision=1,
            requested_by="operator",
            snapshot=snapshot,
        )
        orchestrator.approve_plan(
            plan["id"], approver="lead", decision="approved"
        )
        store.close()

        restarted_store = SQLiteStore(self.database)
        restarted = ExpertPlanOrchestrator(workers=2, store=restarted_store)
        loaded = restarted.get_plan(plan["id"])
        self.assertEqual(loaded["status"], "released")
        self.assertEqual(len(loaded["tasks"]), 7)
        self.assertTrue(
            all(task["status"] == "completed" for task in loaded["tasks"].values())
        )
        self.assertEqual(len(loaded["approvals"]), 1)
        self.assertIn(
            "plan.approved",
            {entry["action"] for entry in restarted.list_activity(plan["id"])},
        )
        restarted_store.close()


class TemporalKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "knowledge.db"
        self.store = SQLiteStore(self.database)
        self.projects = ProjectRepository(store=self.store)
        self.knowledge = KnowledgeRepository(store=self.store)
        self.project = self.projects.create_project(
            name="Knowledge Build", author="alice"
        )

    def tearDown(self):
        self.store.close()
        self.temporary_directory.cleanup()

    def test_version_links_tags_citations_and_conflicts_form_context(self):
        source = self.knowledge.add_source(
            source_type="paper",
            canonical_uri="https://example.test/paper/1",
            title="Verified research",
            metadata={"license": "open"},
        )
        original = self.knowledge.append_record(
            project_id=self.project["id"],
            actor="research-agent",
            reason="Initial discovery",
            record_type="claim",
            content={"claim": "Material A is suitable"},
            source_id=source["id"],
            confidence=0.7,
            tags=["Materials", "Build"],
        )
        revised = self.knowledge.append_record(
            project_id=self.project["id"],
            actor="evidence-reviewer",
            reason="New evidence",
            record_type="claim",
            content={"claim": "Material A needs heat shielding"},
            parent_id=original["id"],
            supersedes_id=original["id"],
            source_id=source["id"],
            confidence=0.9,
            tags=["materials"],
        )
        self.knowledge.add_citation(
            revised["id"],
            source_id=source["id"],
            locator="section 4",
            quote="Measured thermal result",
        )
        self.knowledge.add_relationship(
            revised["id"], original["id"], "contradicts"
        )

        timeline = self.knowledge.timeline(
            self.project["id"], tag="materials"
        )
        self.assertEqual([record["id"] for record in timeline], [original["id"], revised["id"]])
        self.assertEqual(timeline[1]["supersedes_id"], original["id"])
        self.assertEqual(len(timeline[1]["citations"]), 1)

        packet = self.knowledge.context_packet(
            self.project["id"], tags=["materials"], limit=10
        )
        self.assertEqual(packet["record_count"], 2)
        self.assertEqual(len(packet["conflicts"]), 1)

    def test_knowledge_records_are_immutable_and_persist(self):
        record = self.knowledge.append_record(
            project_id=self.project["id"],
            actor="architect",
            reason="Build constraint",
            record_type="requirement",
            content={"text": "Keep prior knowledge"},
            tags=["history"],
        )
        with self.store.transaction() as connection:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                connection.execute(
                    "UPDATE knowledge_records SET reason = 'changed' WHERE id = ?",
                    (record["id"],),
                )

        self.store.close()
        restarted_store = SQLiteStore(self.database)
        restarted = KnowledgeRepository(store=restarted_store)
        loaded = restarted.get_record(record["id"])
        self.assertEqual(loaded["content"], {"text": "Keep prior knowledge"})
        self.assertEqual(loaded["tags"], ["history"])
        restarted_store.close()
        self.store = SQLiteStore(":memory:")
