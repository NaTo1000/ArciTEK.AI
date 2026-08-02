"""Domain-level unittest coverage for the ``arcitek_core.robotics_plan`` package.

Covers: immutability/rollback semantics, human approval gating, the
dependency-aware parallel expert orchestrator, rule-based flaw detection
bounds, the neutral format registry, and the simulation adapter interfaces.
None of these tests start a real subprocess, call an external AI service, or
touch the network -- everything here is pure in-process Python.
"""

import inspect
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from arcitek_core.robotics_plan import formats, orchestrator, rules, simulation
from arcitek_core.robotics_plan.repository import ProjectRepository
from arcitek_core.robotics_plan.validation import (
    ValidationError,
    validate_dict,
    validate_identifier,
    validate_list,
    validate_number,
    validate_string,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_part(part_id, position, dimensions=(100, 100, 100), min_clearance_mm=0):
    return {
        "id": part_id,
        "position": list(position),
        "dimensions": list(dimensions),
        "min_clearance_mm": min_clearance_mm,
    }


OVERLAPPING_PARTS = [
    make_part("base", (0, 0, 0), (200, 200, 100)),
    make_part("arm1", (50, 0, 0), (200, 200, 100)),
]

CLEAN_PARTS = [
    make_part("base", (0, 0, 0), (200, 200, 100)),
    make_part("arm1", (5000, 0, 0), (200, 200, 100)),
]

OVERCURRENT_WIRING = [
    {"id": "w1", "from_part": "base", "to_part": "arm1", "gauge_awg": 24, "current_a": 20}
]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class ValidationHelperTests(unittest.TestCase):
    def test_validate_string_rejects_oversized(self):
        with self.assertRaises(ValidationError):
            validate_string("x" * 500, "name", max_len=10)

    def test_validate_string_rejects_wrong_type(self):
        with self.assertRaises(ValidationError):
            validate_string(123, "name")

    def test_validate_string_requires_non_empty_by_default(self):
        with self.assertRaises(ValidationError):
            validate_string("   ", "name")

    def test_validate_number_rejects_bool(self):
        with self.assertRaises(ValidationError):
            validate_number(True, "value")

    def test_validate_number_rejects_out_of_bounds_magnitude(self):
        with self.assertRaises(ValidationError):
            validate_number(1e12, "value")

    def test_validate_number_enforces_min_max(self):
        with self.assertRaises(ValidationError):
            validate_number(5, "value", minimum=10)
        with self.assertRaises(ValidationError):
            validate_number(5, "value", maximum=1)

    def test_validate_list_bounds_length(self):
        with self.assertRaises(ValidationError):
            validate_list(list(range(5)), "items", max_items=3)

    def test_validate_list_rejects_non_list(self):
        with self.assertRaises(ValidationError):
            validate_list("not-a-list", "items")

    def test_validate_dict_bounds_keys(self):
        with self.assertRaises(ValidationError):
            validate_dict({str(i): i for i in range(5)}, "obj", max_keys=2)

    def test_validate_identifier_rejects_bad_characters(self):
        with self.assertRaises(ValidationError):
            validate_identifier("bad id!", "id")
        self.assertEqual(validate_identifier("good-id_1.2", "id"), "good-id_1.2")


# ---------------------------------------------------------------------------
# Rule-based flaw detection
# ---------------------------------------------------------------------------

class RulesTests(unittest.TestCase):
    def test_overlapping_parts_flagged_critical_collision(self):
        findings = rules.check_clearances(OVERLAPPING_PARTS)
        self.assertTrue(any(f["rule"] == "geometry.collision" for f in findings))
        collision = next(f for f in findings if f["rule"] == "geometry.collision")
        self.assertEqual(collision["severity"], "critical")
        self.assertIn("part_a", collision["evidence"])
        self.assertIn("part_b", collision["evidence"])

    def test_clearance_violation_flagged_high(self):
        parts = [
            make_part("base", (0, 0, 0), (100, 100, 100), min_clearance_mm=50),
            make_part("arm1", (120, 0, 0), (100, 100, 100), min_clearance_mm=50),
        ]
        findings = rules.check_clearances(parts)
        self.assertTrue(any(f["rule"] == "geometry.clearance" for f in findings))
        clearance = next(f for f in findings if f["rule"] == "geometry.clearance")
        self.assertEqual(clearance["severity"], "high")

    def test_well_separated_parts_produce_no_findings(self):
        findings = rules.check_clearances(CLEAN_PARTS)
        self.assertEqual(findings, [])

    def test_wiring_unknown_endpoint_flagged(self):
        wiring = [{"id": "w1", "from_part": "ghost", "to_part": "arm1"}]
        findings = rules.check_wiring(wiring, [make_part("arm1", (0, 0, 0))])
        self.assertTrue(any(f["rule"] == "wiring.connectivity" for f in findings))

    def test_wiring_self_loop_flagged_medium(self):
        wiring = [{"id": "w1", "from_part": "base", "to_part": "base"}]
        findings = rules.check_wiring(wiring, [make_part("base", (0, 0, 0))])
        loop_finding = next(f for f in findings if "itself" in f["message"])
        self.assertEqual(loop_finding["severity"], "medium")

    def test_wiring_overcurrent_flagged_critical(self):
        findings = rules.check_wiring(
            OVERCURRENT_WIRING, [make_part("base", (0, 0, 0)), make_part("arm1", (0, 0, 0))]
        )
        overcurrent = next(f for f in findings if f["rule"] == "wiring.overcurrent")
        self.assertEqual(overcurrent["severity"], "critical")

    def test_wiring_voltage_drop_detected(self):
        wiring = [
            {
                "id": "w2",
                "from_part": "base",
                "to_part": "arm1",
                "gauge_awg": 24,
                "current_a": 2,
                "length_m": 50,
                "voltage_v": 5,
            }
        ]
        findings = rules.check_wiring(
            wiring, [make_part("base", (0, 0, 0)), make_part("arm1", (0, 0, 0))]
        )
        self.assertTrue(any(f["rule"] == "wiring.voltage_drop" for f in findings))

    def test_hydraulics_overpressure_flagged_critical(self):
        findings = rules.check_hydraulics(
            [{"id": "h1", "pressure_bar": 300, "max_pressure_bar": 200}]
        )
        overpressure = next(f for f in findings if f["rule"] == "hydraulics.overpressure")
        self.assertEqual(overpressure["severity"], "critical")

    def test_hydraulics_overflow_flagged_critical(self):
        findings = rules.check_hydraulics([{"id": "h1", "flow_lpm": 50, "max_flow_lpm": 20}])
        overflow = next(f for f in findings if f["rule"] == "hydraulics.overflow")
        self.assertEqual(overflow["severity"], "critical")

    def test_hydraulics_high_velocity_flagged(self):
        findings = rules.check_hydraulics([{"id": "h1", "flow_lpm": 200, "diameter_mm": 4}])
        self.assertTrue(any(f["rule"] == "hydraulics.velocity" for f in findings))

    def test_no_finding_claims_full_confidence(self):
        findings = rules.run_all(
            parts=OVERLAPPING_PARTS, wiring=OVERCURRENT_WIRING, hydraulics=[{"id": "h1", "pressure_bar": 300, "max_pressure_bar": 200}]
        )
        self.assertTrue(findings)
        for finding in findings:
            self.assertLessEqual(finding["confidence"], rules.MAX_CONFIDENCE)
            self.assertLess(finding["confidence"], 1.0)
            self.assertIn("tolerance", finding)
            self.assertTrue(finding["tolerance"])

    def test_run_all_sorts_by_severity(self):
        findings = rules.run_all(
            parts=OVERLAPPING_PARTS,
            wiring=OVERCURRENT_WIRING,
            hydraulics=[{"id": "h1", "pressure_bar": 190, "max_pressure_bar": 200}],
        )
        severities = [rules.SEVERITY_ORDER.index(f["severity"]) for f in findings]
        self.assertEqual(severities, sorted(severities))

    def test_pcb_trace_width_and_clearance_guidelines(self):
        findings = rules.run_all(pcb={"min_trace_width_mm": 0.1, "min_clearance_mm": 0.05})
        rule_names = {f["rule"] for f in findings}
        self.assertIn("pcb.trace_width", rule_names)
        self.assertIn("pcb.clearance", rule_names)


# ---------------------------------------------------------------------------
# ProjectRepository: immutability, rollback, approvals, audit
# ---------------------------------------------------------------------------

class ProjectRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = ProjectRepository()

    def test_create_project_produces_revision_one_pending(self):
        project = self.repo.create_project(name="Warehouse Arm", author="alice", parts=CLEAN_PARTS)
        self.assertEqual(project["current_revision"], 1)
        self.assertEqual(project["approval_status"], "pending")
        self.assertEqual(project["revision_count"], 1)

    def test_create_project_validates_bounded_name(self):
        with self.assertRaises(ValidationError):
            self.repo.create_project(name="x" * 500, author="alice")

    def test_get_project_unknown_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.repo.get_project("proj-does-not-exist")

    def test_revision_findings_computed_at_creation(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=OVERLAPPING_PARTS)
        revision = self.repo.get_revision(project["id"], 1)
        self.assertTrue(any(f["rule"] == "geometry.collision" for f in revision["findings"]))

    def test_get_revision_returns_a_deep_copy_not_the_stored_object(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        revision = self.repo.get_revision(project["id"], 1)
        # Mutate the returned view aggressively.
        revision["parts"].append({"id": "rogue", "position": [0, 0, 0], "dimensions": [1, 1, 1]})
        revision["requirements"].append({"id": "ROGUE", "text": "hack", "priority": "normal"})
        revision["findings"].clear()
        # Re-fetch: stored state must be untouched.
        fresh = self.repo.get_revision(project["id"], 1)
        self.assertEqual(len(fresh["parts"]), len(CLEAN_PARTS))
        self.assertEqual(fresh["requirements"], [])

    def test_create_revision_is_new_number_and_does_not_mutate_prior(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        pid = project["id"]
        rev1_before = self.repo.get_revision(pid, 1)
        rev2 = self.repo.create_revision(pid, author="bob", parts=OVERLAPPING_PARTS)
        self.assertEqual(rev2["number"], 2)
        self.assertEqual(rev2["parent"], 1)
        rev1_after = self.repo.get_revision(pid, 1)
        # Revision 1 content must remain byte-for-byte identical after
        # revision 2 is created -- creating a new revision must never
        # mutate an earlier, already-stored revision.
        self.assertEqual(rev1_before["parts"], rev1_after["parts"])
        self.assertEqual(rev1_before["findings"], rev1_after["findings"])
        self.assertFalse(any(f["rule"] == "geometry.collision" for f in rev1_after["findings"]))
        self.assertTrue(any(f["rule"] == "geometry.collision" for f in rev2["findings"]))

    def test_rollback_creates_new_revision_and_preserves_history(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        pid = project["id"]
        self.repo.create_revision(pid, author="bob", parts=OVERLAPPING_PARTS)  # revision 2
        rolled_back = self.repo.rollback(pid, 1, author="carol", message="undo bad change")
        self.assertEqual(rolled_back["number"], 3)
        # Rollback must point its parent at the *current* revision (2), not the target (1).
        self.assertEqual(rolled_back["parent"], 2)
        self.assertEqual(rolled_back["parts"], self.repo.get_revision(pid, 1)["parts"])
        # Original revisions 1 and 2 remain unchanged in the history.
        all_revisions = self.repo.list_revisions(pid)
        self.assertEqual([r["number"] for r in all_revisions], [1, 2, 3])
        self.assertTrue(any(f["rule"] == "geometry.collision" for f in all_revisions[1]["findings"]))

    def test_rollback_unknown_target_raises_validation_error(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        with self.assertRaises(ValidationError):
            self.repo.rollback(project["id"], 99, author="carol")

    def test_approval_requires_valid_decision(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        with self.assertRaises(ValidationError):
            self.repo.approve_revision(
                project["id"], 1, approver="carol", decision="maybe"
            )

    def test_approval_is_append_only_and_latest_wins(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        pid = project["id"]
        self.repo.approve_revision(pid, 1, approver="carol", decision="rejected")
        self.repo.approve_revision(pid, 1, approver="dave", decision="approved")
        history = self.repo.list_approvals(pid, 1)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["decision"], "rejected")
        self.assertEqual(history[1]["decision"], "approved")
        revision = self.repo.get_revision(pid, 1)
        self.assertEqual(revision["approval_status"], "approved")

    def test_approval_tied_to_immutable_revision_number(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        pid = project["id"]
        self.repo.create_revision(pid, author="bob", parts=OVERLAPPING_PARTS)  # revision 2
        self.repo.approve_revision(pid, 1, approver="carol", decision="approved")
        # Approving revision 1 must not affect revision 2's approval status.
        rev2 = self.repo.get_revision(pid, 2)
        self.assertEqual(rev2["approval_status"], "pending")

    def test_audit_events_recorded_for_lifecycle(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        pid = project["id"]
        self.repo.create_revision(pid, author="bob", parts=OVERLAPPING_PARTS)
        self.repo.approve_revision(pid, 1, approver="carol", decision="approved")
        events = self.repo.list_events(pid)
        actions = {event["action"] for event in events}
        self.assertIn("project.created", actions)
        self.assertIn("revision.created", actions)
        self.assertIn("revision.approved", actions)

    def test_thread_safe_concurrent_revision_creation(self):
        project = self.repo.create_project(name="Arm", author="alice", parts=CLEAN_PARTS)
        pid = project["id"]

        def create_one(i):
            return self.repo.create_revision(pid, author=f"worker-{i}", parts=CLEAN_PARTS)["number"]

        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(create_one, range(20)))

        # No lost updates: 20 concurrent revisions plus the initial one must
        # all be distinct sequential numbers with no duplicates or gaps.
        self.assertEqual(sorted(numbers), list(range(2, 22)))
        all_revisions = self.repo.list_revisions(pid)
        self.assertEqual(len(all_revisions), 21)


# ---------------------------------------------------------------------------
# ExpertPlanOrchestrator: dependency-aware, parallel, structured-plan-only
# ---------------------------------------------------------------------------

class ExpertPlanOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.repo = ProjectRepository()
        self.orchestrator = orchestrator.ExpertPlanOrchestrator(workers=4)

    def _make_snapshot(self, parts=None):
        project = self.repo.create_project(
            name="Arm", author="alice", parts=parts if parts is not None else CLEAN_PARTS
        )
        return project["id"], self.repo.get_revision(project["id"], 1)

    def test_plan_runs_all_expert_roles_to_completion(self):
        pid, snapshot = self._make_snapshot()
        plan = self.orchestrator.create_plan(
            project_id=pid, revision=1, requested_by="tester", snapshot=snapshot
        )
        self.assertEqual(plan["status"], "completed")
        self.assertEqual(set(plan["tasks"].keys()), set(orchestrator.ROLE_GRAPH.keys()))
        for role, task in plan["tasks"].items():
            self.assertEqual(task["status"], "completed", msg=role)
            self.assertIsNotNone(task["output"])

    def test_plan_respects_declared_dependencies(self):
        pid, snapshot = self._make_snapshot()
        plan = self.orchestrator.create_plan(
            project_id=pid, revision=1, requested_by="tester", snapshot=snapshot
        )
        for role, task in plan["tasks"].items():
            deps = task["depends_on"]
            for dep in deps:
                self.assertLessEqual(
                    plan["tasks"][dep]["completed_at"], task["started_at"] + 1e-3,
                    msg=f"{dep} must finish before {role} starts",
                )

    def test_role_graph_has_no_arbitrary_execution(self):
        source = inspect.getsource(orchestrator)
        for forbidden in ("subprocess", "os.system", "eval(", "exec(", "openai", "anthropic"):
            self.assertNotIn(forbidden, source)

    def test_approve_plan_requires_completed_status(self):
        pid, snapshot = self._make_snapshot()
        plan = self.orchestrator.create_plan(
            project_id=pid, revision=1, requested_by="tester", snapshot=snapshot
        )
        # Force the plan back into a non-terminal state to exercise the gate.
        with self.orchestrator._lock:  # noqa: SLF001 - white-box test of gating invariant
            self.orchestrator._plans[plan["id"]]["status"] = "running"
        with self.assertRaises(ValidationError):
            self.orchestrator.approve_plan(plan["id"], approver="lead", decision="approved")

    def test_approve_plan_rejects_bad_decision(self):
        pid, snapshot = self._make_snapshot()
        plan = self.orchestrator.create_plan(
            project_id=pid, revision=1, requested_by="tester", snapshot=snapshot
        )
        with self.assertRaises(ValidationError):
            self.orchestrator.approve_plan(plan["id"], approver="lead", decision="sure")

    def test_approve_plan_sets_released_status(self):
        pid, snapshot = self._make_snapshot()
        plan = self.orchestrator.create_plan(
            project_id=pid, revision=1, requested_by="tester", snapshot=snapshot
        )
        approved = self.orchestrator.approve_plan(
            plan["id"], approver="lead", decision="approved"
        )
        self.assertEqual(approved["status"], "released")
        self.assertEqual(len(approved["approvals"]), 1)

    def test_approve_plan_rejected_decision_sets_rejected_status(self):
        pid, snapshot = self._make_snapshot()
        plan = self.orchestrator.create_plan(
            project_id=pid, revision=1, requested_by="tester", snapshot=snapshot
        )
        rejected = self.orchestrator.approve_plan(
            plan["id"], approver="lead", decision="rejected"
        )
        self.assertEqual(rejected["status"], "rejected")

    def test_unknown_plan_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.orchestrator.get_plan("plan-does-not-exist")

    def test_activity_log_recorded_for_plan(self):
        pid, snapshot = self._make_snapshot()
        plan = self.orchestrator.create_plan(
            project_id=pid, revision=1, requested_by="tester", snapshot=snapshot
        )
        activity = self.orchestrator.list_activity(plan["id"])
        actions = {entry["action"] for entry in activity}
        self.assertIn("plan.created", actions)
        self.assertIn("plan.completed", actions)

    def test_concurrent_plans_execute_independently(self):
        pid, snapshot = self._make_snapshot()

        def run_one(i):
            return self.orchestrator.create_plan(
                project_id=pid, revision=1, requested_by=f"tester-{i}", snapshot=snapshot
            )["status"]

        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(run_one, range(6)))
        self.assertTrue(all(status == "completed" for status in statuses))


# ---------------------------------------------------------------------------
# Format registry / adapters (metadata-only, never real CAD/EDA conversion)
# ---------------------------------------------------------------------------

class FormatsTests(unittest.TestCase):
    def test_list_formats_includes_required_neutral_formats(self):
        ids = {spec["id"] for spec in formats.list_formats()}
        self.assertEqual(
            ids, {"step", "stl", "dxf", "urdf", "gerber", "ipc2581", "netlist"}
        )
        for spec in formats.list_formats():
            self.assertIn("disclaimer", spec)

    def test_validate_import_good_extension_and_metadata(self):
        manifest = formats.validate_import("step", "part.step", {"units": "mm"})
        self.assertTrue(manifest["ok"])
        self.assertTrue(manifest["extension_ok"])
        self.assertTrue(manifest["metadata_ok"])

    def test_validate_import_bad_extension_flagged(self):
        manifest = formats.validate_import("step", "part.txt", {"units": "mm"})
        self.assertFalse(manifest["ok"])
        self.assertFalse(manifest["extension_ok"])
        self.assertTrue(manifest["issues"])

    def test_validate_import_missing_metadata_flagged(self):
        manifest = formats.validate_import("urdf", "robot.urdf", {})
        self.assertFalse(manifest["ok"])
        self.assertFalse(manifest["metadata_ok"])

    def test_unsupported_format_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            formats.get_format("obj")

    def test_export_manifest_ready_when_metadata_present(self):
        manifest = formats.build_export_manifest("netlist", {"nets": []})
        self.assertTrue(manifest["ready"])

    def test_export_manifest_not_ready_when_metadata_missing(self):
        manifest = formats.build_export_manifest("netlist", {})
        self.assertFalse(manifest["ready"])
        self.assertTrue(manifest["issues"])

    def test_never_claims_native_conversion(self):
        for spec in formats.list_formats():
            self.assertIn("does not parse or convert", spec["disclaimer"])


# ---------------------------------------------------------------------------
# Simulation adapters (capability manifests + deterministic dry runs only)
# ---------------------------------------------------------------------------

class SimulationTests(unittest.TestCase):
    def test_list_tools_covers_freecad_kicad_ros2_gazebo(self):
        ids = {tool["id"] for tool in simulation.list_tools()}
        self.assertEqual(ids, {"freecad", "kicad", "ros2_gazebo"})
        for tool in simulation.list_tools():
            self.assertEqual(tool["execution_mode"], "dry_run_only")

    def test_never_executes_a_subprocess(self):
        source = inspect.getsource(simulation)
        for forbidden in ("import subprocess", "Popen(", "os.system(", "eval(", "exec("):
            self.assertNotIn(forbidden, source)

    def test_dry_run_unsupported_tool_raises(self):
        with self.assertRaises(ValidationError):
            simulation.dry_run("solidworks", {})

    def test_dry_run_clear_when_no_relevant_findings(self):
        snapshot = {"parts": CLEAN_PARTS, "wiring": [], "hydraulics": [], "pcb": {}}
        result = simulation.dry_run("freecad", snapshot)
        self.assertEqual(result["status"], "clear")
        self.assertTrue(result["verification_required"])
        self.assertLessEqual(result["confidence"], simulation.MAX_CONFIDENCE)

    def test_dry_run_blocked_when_critical_findings_relevant(self):
        snapshot = {"parts": OVERLAPPING_PARTS, "wiring": [], "hydraulics": [], "pcb": {}}
        result = simulation.dry_run("freecad", snapshot)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["relevant_findings"])

    def test_dry_run_always_flags_verification_required(self):
        for tool_id in ("freecad", "kicad", "ros2_gazebo"):
            result = simulation.dry_run(tool_id, {})
            self.assertTrue(result["verification_required"])
            self.assertEqual(result["execution_mode"], "dry_run_only")


if __name__ == "__main__":
    unittest.main()
