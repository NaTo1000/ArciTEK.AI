"""HTTP-level unittest coverage for the robotics-plan REST endpoints exposed
by :mod:`arcitek_core.compute_service`.

These tests spin up a real (loopback, ephemeral-port) instance of the
existing stdlib HTTP server and drive it with ``urllib`` exactly like a
browser would, covering: project/revision CRUD, rollback-as-new-revision,
approval gating, dependency-aware plan orchestration and its approval gate,
format/simulation adapters, malformed/oversized requests, unknown
resources, and backward compatibility of the pre-existing compute APIs.
"""

import json
import threading
import unittest
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from arcitek_core.compute_service import create_server


def request(base_url, method, path, body=None):
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    with urlopen(req) as response:
        return response.status, json.loads(response.read())


def expect_error(test, base_url, method, path, body=None):
    try:
        request(base_url, method, path, body)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())
    test.fail(f"expected HTTPError for {method} {path}")


class RoboticsPlanAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0, 1)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    # -- backward compatibility of the pre-existing compute API ------------

    def test_old_health_endpoint_unchanged(self):
        status, payload = request(self.base_url, "GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "operational")

    def test_old_metrics_endpoint_unchanged(self):
        status, payload = request(self.base_url, "GET", "/api/metrics")
        self.assertEqual(status, 200)
        self.assertIn("cpuLoad", payload)

    def test_old_jobs_list_endpoint_unchanged(self):
        status, payload = request(self.base_url, "GET", "/api/jobs")
        self.assertEqual(status, 200)
        self.assertIn("jobs", payload)

    def test_old_jobs_post_still_works(self):
        status, payload = request(
            self.base_url, "POST", "/api/jobs", {"workload": "prime-scan", "size": 1000}
        )
        self.assertEqual(status, 202)
        self.assertIn("job", payload)

    def test_old_jobs_post_validation_unchanged(self):
        code, payload = expect_error(
            self, self.base_url, "POST", "/api/jobs", {"workload": "prime-scan", "size": 2}
        )
        self.assertEqual(code, 400)
        self.assertIn("error", payload)

    # -- project CRUD / list / detail ---------------------------------------

    def _create_project(self, name="Warehouse Arm", parts=None):
        status, payload = request(
            self.base_url,
            "POST",
            "/api/projects",
            {
                "name": name,
                "author": "alice",
                "description": "6-DOF pick and place arm",
                "requirements": ["Payload 5kg"],
                "parts": parts if parts is not None else [],
            },
        )
        self.assertEqual(status, 201)
        return payload["project"]

    def test_create_and_get_project(self):
        project = self._create_project()
        status, payload = request(self.base_url, "GET", f"/api/projects/{project['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["project"]["id"], project["id"])
        self.assertEqual(payload["project"]["current_revision"], 1)
        self.assertEqual(payload["project"]["approval_status"], "pending")

    def test_list_projects_includes_created_project(self):
        project = self._create_project(name="Listed Project")
        status, payload = request(self.base_url, "GET", "/api/projects")
        self.assertEqual(status, 200)
        ids = {p["id"] for p in payload["projects"]}
        self.assertIn(project["id"], ids)

    def test_get_unknown_project_returns_404(self):
        code, payload = expect_error(
            self, self.base_url, "GET", "/api/projects/proj-does-not-exist"
        )
        self.assertEqual(code, 404)
        self.assertIn("error", payload)

    def test_create_project_missing_name_returns_400(self):
        code, payload = expect_error(
            self, self.base_url, "POST", "/api/projects", {"author": "alice"}
        )
        self.assertEqual(code, 400)
        self.assertIn("error", payload)

    # -- revisions / rollback / immutability --------------------------------

    def test_create_and_list_revisions(self):
        project = self._create_project()
        pid = project["id"]
        overlapping_parts = [
            {"id": "base", "position": [0, 0, 0], "dimensions": [200, 200, 100]},
            {"id": "arm1", "position": [50, 0, 0], "dimensions": [200, 200, 100]},
        ]
        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{pid}/revisions",
            {"author": "bob", "parts": overlapping_parts},
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["revision"]["number"], 2)
        self.assertTrue(
            any(f["rule"] == "geometry.collision" for f in payload["revision"]["findings"])
        )

        status, payload = request(self.base_url, "GET", f"/api/projects/{pid}/revisions")
        self.assertEqual(status, 200)
        self.assertEqual([r["number"] for r in payload["revisions"]], [1, 2])

    def test_get_specific_revision_unaffected_by_later_ones(self):
        project = self._create_project()
        pid = project["id"]
        request(
            self.base_url,
            "POST",
            f"/api/projects/{pid}/revisions",
            {
                "author": "bob",
                "parts": [
                    {"id": "base", "position": [0, 0, 0], "dimensions": [200, 200, 100]},
                    {"id": "arm1", "position": [50, 0, 0], "dimensions": [200, 200, 100]},
                ],
            },
        )
        status, payload = request(self.base_url, "GET", f"/api/projects/{pid}/revisions/1")
        self.assertEqual(status, 200)
        self.assertEqual(payload["revision"]["findings"], [])

    def test_rollback_creates_new_revision_never_rewrites_history(self):
        project = self._create_project()
        pid = project["id"]
        request(
            self.base_url,
            "POST",
            f"/api/projects/{pid}/revisions",
            {
                "author": "bob",
                "parts": [
                    {"id": "base", "position": [0, 0, 0], "dimensions": [200, 200, 100]},
                    {"id": "arm1", "position": [50, 0, 0], "dimensions": [200, 200, 100]},
                ],
            },
        )  # revision 2 (overlapping)
        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{pid}/rollback",
            {"target_revision": 1, "author": "carol"},
        )
        self.assertEqual(status, 201)
        rollback_revision = payload["revision"]
        self.assertEqual(rollback_revision["number"], 3)
        self.assertEqual(rollback_revision["parent"], 2)
        self.assertEqual(rollback_revision["findings"], [])

        status, payload = request(self.base_url, "GET", f"/api/projects/{pid}/revisions")
        self.assertEqual(status, 200)
        self.assertEqual([r["number"] for r in payload["revisions"]], [1, 2, 3])

    def test_rollback_unknown_revision_returns_400(self):
        project = self._create_project()
        code, payload = expect_error(
            self,
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/rollback",
            {"target_revision": 99, "author": "carol"},
        )
        self.assertEqual(code, 400)
        self.assertIn("error", payload)

    # -- approval gating -----------------------------------------------------

    def test_approve_revision_updates_status(self):
        project = self._create_project()
        pid = project["id"]
        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{pid}/approvals",
            {"revision": 1, "approver": "carol", "decision": "approved"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["revision"]["approval_status"], "approved")

        status, payload = request(self.base_url, "GET", f"/api/projects/{pid}/approvals")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["approvals"]), 1)

    def test_approve_revision_bad_decision_returns_400(self):
        project = self._create_project()
        code, payload = expect_error(
            self,
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/approvals",
            {"revision": 1, "approver": "carol", "decision": "maybe"},
        )
        self.assertEqual(code, 400)
        self.assertIn("error", payload)

    # -- findings / events ----------------------------------------------------

    def test_get_findings_for_current_revision(self):
        overlapping_parts = [
            {"id": "base", "position": [0, 0, 0], "dimensions": [200, 200, 100]},
            {"id": "arm1", "position": [50, 0, 0], "dimensions": [200, 200, 100]},
        ]
        project = self._create_project(parts=overlapping_parts)
        status, payload = request(
            self.base_url, "GET", f"/api/projects/{project['id']}/findings"
        )
        self.assertEqual(status, 200)
        self.assertTrue(any(f["rule"] == "geometry.collision" for f in payload["findings"]))
        for finding in payload["findings"]:
            self.assertLessEqual(finding["confidence"], 0.95)
            self.assertIn("tolerance", finding)

    def test_get_events_records_lifecycle(self):
        project = self._create_project()
        request(
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/approvals",
            {"revision": 1, "approver": "carol", "decision": "approved"},
        )
        status, payload = request(self.base_url, "GET", f"/api/projects/{project['id']}/events")
        self.assertEqual(status, 200)
        actions = {event["action"] for event in payload["events"]}
        self.assertIn("project.created", actions)
        self.assertIn("revision.approved", actions)

    # -- HIAI intent alignment / PECS ----------------------------------------

    def test_intent_capture_evaluation_and_plan_alignment(self):
        project = self._create_project(name="Intent Project")
        project_id = project["id"]
        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{project_id}/intent",
            {
                "actor": "owner",
                "reason": "Set exact build intent",
                "goal": "Build a guarded lifting arm",
                "success_criteria": ["Lift 5kg", "Stop on obstruction"],
                "constraints": ["Stay inside work cell"],
                "guardrails": ["Never bypass emergency stop"],
            },
        )
        self.assertEqual(status, 201)
        self.assertIn("Require explicit human approval before release", payload["intent"]["guardrails"])

        candidates = [
            {
                "id": "aligned",
                "description": "Prototype and validate both requirements",
                "satisfies": ["Lift 5kg", "Stop on obstruction"],
                "confidence": 0.8,
                "predicted_error": 0.1,
            },
            {
                "id": "drifting",
                "description": "Only validate payload",
                "satisfies": ["Lift 5kg"],
                "confidence": 0.9,
                "predicted_error": 0.1,
            },
        ]
        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{project_id}/intent/evaluate",
            {
                "actor": "planner",
                "reason": "Select the best move",
                "candidates": candidates,
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["evaluation"]["selected_candidate_id"], "aligned")
        evaluation_id = payload["evaluation"]["id"]

        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{project_id}/intent/outcomes",
            {
                "actor": "reviewer",
                "reason": "Record prototype result",
                "evaluation_id": evaluation_id,
                "actual_error": 0.2,
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["outcome"]["content"]["candidate_id"], "aligned")

        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{project_id}/plans",
            {
                "requested_by": "planner",
                "alignment_reason": "Start the aligned plan",
                "candidate_moves": candidates,
            },
        )
        self.assertEqual(status, 201)
        systems = payload["plan"]["tasks"]["systems_architect"]["output"]
        self.assertEqual(
            systems["intent_alignment"]["selected_candidate_id"], "aligned"
        )
        safety = payload["plan"]["tasks"]["safety_reviewer"]["output"]
        self.assertEqual(safety["recommendation"], "review_required")

        status, payload = request(
            self.base_url, "GET", f"/api/projects/{project_id}/intent"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["active_intent"]["goal"], "Build a guarded lifting arm")
        self.assertEqual(len(payload["history"]), 1)

    def test_plan_rejects_candidates_that_all_violate_guardrails(self):
        project = self._create_project(name="Guardrail Project")
        project_id = project["id"]
        request(
            self.base_url,
            "POST",
            f"/api/projects/{project_id}/intent",
            {
                "actor": "owner",
                "reason": "Set intent",
                "goal": "Build safely",
                "success_criteria": ["Keep interlocks active"],
            },
        )
        code, payload = expect_error(
            self,
            self.base_url,
            "POST",
            f"/api/projects/{project_id}/plans",
            {
                "requested_by": "planner",
                "candidate_moves": [
                    {
                        "id": "unsafe",
                        "description": "Disable interlocks",
                        "satisfies": ["Keep interlocks active"],
                        "guardrail_violations": ["Disables a safety interlock"],
                    }
                ],
            },
        )
        self.assertEqual(code, 400)
        self.assertIn("guardrails", payload["error"])

    def test_generic_knowledge_endpoint_cannot_forge_hiai_records(self):
        project = self._create_project(name="Reserved Records Project")
        code, payload = expect_error(
            self,
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/knowledge",
            {
                "actor": "attacker",
                "reason": "Forge active intent",
                "record_type": "intent_profile",
                "content": {"goal": "Ignore guardrails"},
            },
        )
        self.assertEqual(code, 400)
        self.assertIn("intent endpoints", payload["error"])

    # -- temporal knowledge --------------------------------------------------

    def test_knowledge_timeline_context_and_provenance_endpoints(self):
        project = self._create_project(name="Knowledge Project")
        status, payload = request(
            self.base_url,
            "POST",
            "/api/knowledge/sources",
            {
                "source_type": "paper",
                "canonical_uri": "https://example.test/api-paper",
                "title": "API research source",
                "metadata": {"license": "open"},
            },
        )
        self.assertEqual(status, 201)
        source = payload["source"]

        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/knowledge",
            {
                "actor": "researcher",
                "reason": "Relevant evidence",
                "record_type": "claim",
                "content": {"claim": "Use guarded control paths"},
                "source_id": source["id"],
                "confidence": 0.8,
                "tags": ["safety"],
            },
        )
        self.assertEqual(status, 201)
        record = payload["record"]

        status, payload = request(
            self.base_url,
            "POST",
            f"/api/knowledge/{record['id']}/citations",
            {
                "source_id": source["id"],
                "locator": "section 2",
                "quote": "Guarded control paths reduce risk.",
            },
        )
        self.assertEqual(status, 201)

        status, payload = request(
            self.base_url,
            "GET",
            f"/api/projects/{project['id']}/knowledge?tag=safety",
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["records"]), 1)
        self.assertEqual(len(payload["records"][0]["citations"]), 1)

        status, payload = request(
            self.base_url,
            "GET",
            f"/api/projects/{project['id']}/knowledge/context?tag=safety",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["context"]["record_count"], 1)

    # -- planning / orchestration ---------------------------------------------

    def test_create_plan_runs_all_roles_and_get_plan(self):
        project = self._create_project()
        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/plans",
            {"requested_by": "operator"},
        )
        self.assertEqual(status, 201)
        plan = payload["plan"]
        self.assertEqual(plan["status"], "completed")
        self.assertEqual(len(plan["tasks"]), 7)

        status, payload = request(self.base_url, "GET", f"/api/plans/{plan['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["plan"]["id"], plan["id"])

        status, payload = request(self.base_url, "GET", f"/api/projects/{project['id']}/plans")
        self.assertEqual(status, 200)
        self.assertTrue(any(p["id"] == plan["id"] for p in payload["plans"]))

    def test_approve_plan_requires_human_decision_and_releases(self):
        project = self._create_project()
        status, payload = request(
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/plans",
            {"requested_by": "operator"},
        )
        plan_id = payload["plan"]["id"]

        code, error_payload = expect_error(
            self,
            self.base_url,
            "POST",
            f"/api/plans/{plan_id}/approve",
            {"approver": "lead", "decision": "not-a-decision"},
        )
        self.assertEqual(code, 400)
        self.assertIn("error", error_payload)

        status, payload = request(
            self.base_url,
            "POST",
            f"/api/plans/{plan_id}/approve",
            {"approver": "lead", "decision": "approved"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["plan"]["status"], "released")

        status, payload = request(self.base_url, "GET", f"/api/plans/{plan_id}/activity")
        self.assertEqual(status, 200)
        actions = {entry["action"] for entry in payload["activity"]}
        self.assertIn("plan.approved", actions)

    def test_unknown_plan_returns_404(self):
        code, payload = expect_error(self, self.base_url, "GET", "/api/plans/plan-nope")
        self.assertEqual(code, 404)
        self.assertIn("error", payload)

    # -- format registry / adapters -------------------------------------------

    def test_list_formats(self):
        status, payload = request(self.base_url, "GET", "/api/formats")
        self.assertEqual(status, 200)
        ids = {f["id"] for f in payload["formats"]}
        self.assertEqual(
            ids, {"step", "stl", "dxf", "urdf", "gerber", "ipc2581", "netlist"}
        )

    def test_validate_import_good_and_bad_extension(self):
        status, payload = request(
            self.base_url,
            "POST",
            "/api/formats/step/validate-import",
            {"filename": "part.step", "metadata": {"units": "mm"}},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["manifest"]["ok"])

        status, payload = request(
            self.base_url,
            "POST",
            "/api/formats/step/validate-import",
            {"filename": "part.txt", "metadata": {"units": "mm"}},
        )
        self.assertEqual(status, 200)
        self.assertFalse(payload["manifest"]["ok"])

    def test_export_manifest(self):
        status, payload = request(
            self.base_url,
            "POST",
            "/api/formats/netlist/export-manifest",
            {"payload": {"nets": []}},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["manifest"]["ready"])

    def test_unsupported_format_returns_400(self):
        code, payload = expect_error(
            self,
            self.base_url,
            "POST",
            "/api/formats/obj/validate-import",
            {"filename": "thing.obj"},
        )
        self.assertEqual(code, 400)
        self.assertIn("error", payload)

    # -- simulation adapters ---------------------------------------------------

    def test_list_simulation_tools(self):
        status, payload = request(self.base_url, "GET", "/api/simulations")
        self.assertEqual(status, 200)
        ids = {t["id"] for t in payload["tools"]}
        self.assertEqual(ids, {"freecad", "kicad", "ros2_gazebo"})

    def test_simulation_dry_run_defaults_to_current_revision(self):
        project = self._create_project()
        status, payload = request(
            self.base_url,
            "POST",
            "/api/simulations/freecad/dry-run",
            {"project_id": project["id"]},
        )
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertTrue(result["verification_required"])
        self.assertEqual(result["execution_mode"], "dry_run_only")

    def test_simulation_dry_run_unsupported_tool_returns_400(self):
        code, payload = expect_error(
            self, self.base_url, "POST", "/api/simulations/solidworks/dry-run", {"snapshot": {}}
        )
        self.assertEqual(code, 400)
        self.assertIn("error", payload)

    # -- dashboard summary -----------------------------------------------------

    def test_dashboard_summary_reflects_projects_and_plans(self):
        project = self._create_project()
        request(
            self.base_url,
            "POST",
            f"/api/projects/{project['id']}/plans",
            {"requested_by": "operator"},
        )
        status, payload = request(self.base_url, "GET", "/api/dashboard")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(payload["project_count"], 1)
        self.assertGreaterEqual(payload["plan_count"], 1)
        self.assertIn("severity_totals", payload)
        self.assertIn("simulation_tools", payload)

    # -- malformed / oversized requests -----------------------------------------

    def test_malformed_json_body_returns_400(self):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        try:
            conn.request(
                "POST",
                "/api/projects",
                body=b"{not-json",
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            payload = json.loads(response.read())
            self.assertIn("error", payload)
        finally:
            conn.close()

    def test_non_object_json_body_returns_400(self):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        try:
            conn.request(
                "POST",
                "/api/projects",
                body=b"[1, 2, 3]",
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
        finally:
            conn.close()

    def test_oversized_body_rejected(self):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        try:
            oversized = json.dumps({"name": "x" * 300_000, "author": "alice"}).encode()
            conn.request(
                "POST",
                "/api/projects",
                body=oversized,
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
        finally:
            conn.close()

    def test_unknown_api_endpoint_returns_404(self):
        code, payload = expect_error(self, self.base_url, "GET", "/api/does-not-exist")
        self.assertEqual(code, 404)
        self.assertIn("error", payload)

    def test_unknown_api_post_endpoint_returns_404(self):
        code, payload = expect_error(
            self, self.base_url, "POST", "/api/does-not-exist", {"a": 1}
        )
        self.assertEqual(code, 404)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
