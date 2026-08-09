"""Dependency-aware, parallel expert-task orchestrator.

The orchestrator only ever produces **structured, deterministic plan data**.
There is no code/shell execution and no call out to any external AI
service -- every expert "role" is a small, fixed, pure Python function that
summarizes the already-validated project snapshot (and the rule-based
findings already attached to it). The role graph itself is a fixed,
built-in constant; callers cannot inject arbitrary roles, dependencies, or
executable behavior.

A plan only reaches a released/rejected terminal state through an explicit
human approval call (:meth:`ExpertPlanOrchestrator.approve_plan`) -- it is
never set automatically.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from . import simulation
from .storage import SQLiteStore
from .validation import ValidationError, validate_dict, validate_string

MAX_PLANS = 500

# Fixed, deterministic expert role graph. Keys are the only valid roles;
# values are the roles that must complete before this one may start. Python
# dicts preserve insertion order, which we rely on for a stable, readable
# default ordering (actual execution order is dependency-driven, not
# insertion-driven).
ROLE_GRAPH: dict[str, tuple[str, ...]] = {
    "systems_architect": (),
    "mechanical_engineer": ("systems_architect",),
    "electrical_engineer": ("systems_architect",),
    "hydraulics_engineer": ("systems_architect",),
    "pcb_engineer": ("systems_architect",),
    "simulation_engineer": (
        "mechanical_engineer",
        "electrical_engineer",
        "hydraulics_engineer",
        "pcb_engineer",
    ),
    "safety_reviewer": ("simulation_engineer",),
}

ROLE_LABELS = {
    "systems_architect": "Systems Architect",
    "mechanical_engineer": "Mechanical Engineer",
    "electrical_engineer": "Electrical Engineer",
    "hydraulics_engineer": "Hydraulics Engineer",
    "pcb_engineer": "PCB Engineer",
    "simulation_engineer": "Simulation Engineer",
    "safety_reviewer": "Safety Reviewer",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _run_systems_architect(snapshot: dict[str, Any]) -> dict[str, Any]:
    requirements = snapshot.get("requirements") or []
    parts = snapshot.get("parts") or []
    alignment = snapshot.get("intent_alignment")
    return {
        "summary": (
            f"{len(requirements)} requirement(s) and {len(parts)} part(s) "
            "reviewed at the system level."
        ),
        "requirement_count": len(requirements),
        "part_count": len(parts),
        "part_categories": _count_by(parts, "category"),
        "intent_alignment": alignment,
    }


def _run_mechanical_engineer(snapshot: dict[str, Any]) -> dict[str, Any]:
    parts = snapshot.get("parts") or []
    findings = [
        f for f in (snapshot.get("findings") or []) if f.get("rule", "").startswith("geometry.")
    ]
    missing_mass = [p.get("id") for p in parts if p.get("mass_kg") is None]
    return {
        "summary": f"{len(parts)} part(s) reviewed for fit and mass properties.",
        "geometry_findings": findings,
        "parts_missing_mass": missing_mass,
        "total_mass_kg": round(sum(p.get("mass_kg") or 0 for p in parts), 4),
    }


def _run_electrical_engineer(snapshot: dict[str, Any]) -> dict[str, Any]:
    wiring = snapshot.get("wiring") or []
    findings = [
        f for f in (snapshot.get("findings") or []) if f.get("rule", "").startswith("wiring.")
    ]
    return {
        "summary": f"{len(wiring)} wire(s)/circuit(s) reviewed.",
        "wiring_findings": findings,
        "circuits": _count_by(wiring, "circuit"),
    }


def _run_hydraulics_engineer(snapshot: dict[str, Any]) -> dict[str, Any]:
    hydraulics = snapshot.get("hydraulics") or []
    findings = [
        f for f in (snapshot.get("findings") or []) if f.get("rule", "").startswith("hydraulics.")
    ]
    return {
        "summary": f"{len(hydraulics)} hydraulic line(s) reviewed.",
        "hydraulics_findings": findings,
    }


def _run_pcb_engineer(snapshot: dict[str, Any]) -> dict[str, Any]:
    pcb = snapshot.get("pcb") or {}
    findings = [
        f for f in (snapshot.get("findings") or []) if f.get("rule", "").startswith("pcb.")
    ]
    return {
        "summary": (
            f"Board '{pcb.get('board_name', 'unspecified')}' with "
            f"{len(pcb.get('nets', []))} net(s) reviewed."
            if pcb
            else "No PCB data supplied for this revision."
        ),
        "pcb_findings": findings,
        "has_pcb_data": bool(pcb),
    }


def _run_simulation_engineer(snapshot: dict[str, Any]) -> dict[str, Any]:
    dry_runs = {
        tool_id: simulation.dry_run(tool_id, snapshot) for tool_id in simulation.SIM_TOOLS
    }
    blocked = [tool for tool, result in dry_runs.items() if result["status"] == "blocked"]
    return {
        "summary": (
            f"{len(blocked)} of {len(dry_runs)} simulation dry run(s) reported "
            "blocking findings."
        ),
        "dry_runs": dry_runs,
        "blocked_tools": blocked,
    }


def _run_safety_reviewer(snapshot: dict[str, Any], upstream: dict[str, Any]) -> dict[str, Any]:
    findings = snapshot.get("findings") or []
    severity_counts: dict[str, int] = {}
    for finding in findings:
        severity = finding.get("severity", "info")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    sim_blocked = upstream.get("simulation_engineer", {}).get("blocked_tools", [])
    alignment = snapshot.get("intent_alignment") or {}
    alignment_status = alignment.get("status")
    recommendation = (
        "block_release"
        if severity_counts.get("critical")
        or sim_blocked
        or alignment_status == "blocked"
        else (
            "review_required"
            if severity_counts.get("high")
            or alignment_status == "human_review_required"
            or alignment.get("drift_detected")
            or alignment.get("requires_human_review")
            else "no_blocking_issues"
        )
    )
    return {
        "summary": f"{len(findings)} finding(s) reviewed across all disciplines.",
        "severity_counts": severity_counts,
        "recommendation": recommendation,
        "simulation_blocked_tools": sim_blocked,
        "intent_alignment_status": alignment_status or "not_configured",
        "disclaimer": (
            "Automated review only; does not replace certified human safety "
            "sign-off."
        ),
    }


_ROLE_RUNNERS = {
    "systems_architect": lambda snapshot, upstream: _run_systems_architect(snapshot),
    "mechanical_engineer": lambda snapshot, upstream: _run_mechanical_engineer(snapshot),
    "electrical_engineer": lambda snapshot, upstream: _run_electrical_engineer(snapshot),
    "hydraulics_engineer": lambda snapshot, upstream: _run_hydraulics_engineer(snapshot),
    "pcb_engineer": lambda snapshot, upstream: _run_pcb_engineer(snapshot),
    "simulation_engineer": lambda snapshot, upstream: _run_simulation_engineer(snapshot),
    "safety_reviewer": lambda snapshot, upstream: _run_safety_reviewer(snapshot, upstream),
}


class ExpertPlanOrchestrator:
    """Builds and executes the fixed expert-role DAG for a project revision."""

    def __init__(
        self,
        workers: int = 4,
        *,
        store: SQLiteStore | None = None,
        database: str | Path | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._plans: dict[str, dict[str, Any]] = {}
        self._activity: list[dict[str, Any]] = []
        self.store = store or (SQLiteStore(database) if database is not None else None)
        workers = max(1, min(workers, 16))
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="arcitek-expert"
        )
        if self.store is not None:
            self._load_persisted_state()

    def _log(self, plan_id: str, action: str, details: dict[str, Any]) -> None:
        entry = {
            "id": _new_id("act"),
            "plan_id": plan_id,
            "timestamp": time.time(),
            "action": action,
            "details": details,
        }
        self._activity.append(entry)
        if len(self._activity) > 5_000:
            del self._activity[: len(self._activity) - 5_000]
        if self.store is not None:
            with self.store.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO plan_activity
                        (id, plan_id, timestamp, action, details_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        entry["id"],
                        plan_id,
                        entry["timestamp"],
                        action,
                        _json_dump(details),
                    ),
                )

    def _load_persisted_state(self) -> None:
        interrupted_plan_ids: list[str] = []
        with self.store.lock:
            connection = self.store.connection
            plan_rows = connection.execute(
                "SELECT * FROM plans ORDER BY created_at"
            ).fetchall()
            for row in plan_rows:
                task_rows = connection.execute(
                    "SELECT * FROM plan_tasks WHERE plan_id = ? ORDER BY rowid",
                    (row["id"],),
                ).fetchall()
                approval_rows = connection.execute(
                    """
                    SELECT id, approver, decision, comment, timestamp
                    FROM plan_approvals WHERE plan_id = ?
                    ORDER BY timestamp, rowid
                    """,
                    (row["id"],),
                ).fetchall()
                self._plans[row["id"]] = {
                    "id": row["id"],
                    "project_id": row["project_id"],
                    "revision": row["revision"],
                    "requested_by": row["requested_by"],
                    "created_at": row["created_at"],
                    "status": row["status"],
                    "tasks": {
                        task["role"]: {
                            "id": task["task_id"],
                            "role": task["role"],
                            "title": task["title"],
                            "depends_on": json.loads(task["depends_on_json"]),
                            "status": task["status"],
                            "output": (
                                json.loads(task["output_json"])
                                if task["output_json"] is not None
                                else None
                            ),
                            "started_at": task["started_at"],
                            "completed_at": task["completed_at"],
                        }
                        for task in task_rows
                    },
                    "approvals": [dict(approval) for approval in approval_rows],
                }
                if row["status"] == "running":
                    interrupted_plan_ids.append(row["id"])
            activity_rows = connection.execute(
                """
                SELECT id, plan_id, timestamp, action, details_json
                FROM plan_activity ORDER BY timestamp, rowid
                """
            ).fetchall()
        self._activity = [
            {
                "id": row["id"],
                "plan_id": row["plan_id"],
                "timestamp": row["timestamp"],
                "action": row["action"],
                "details": json.loads(row["details_json"]),
            }
            for row in activity_rows[-5_000:]
        ]
        for plan_id in interrupted_plan_ids:
            with self._lock:
                plan = self._plans[plan_id]
                plan["status"] = "failed"
                for task in plan["tasks"].values():
                    if task["status"] == "running":
                        task["status"] = "failed"
                        task["output"] = {
                            "error": "Interrupted by service restart"
                        }
                        task["completed_at"] = time.time()
                        self._persist_task(plan_id, task)
                self._persist_plan_status(plan_id, "failed")
            self._log(
                plan_id,
                "plan.failed",
                {"reason": "interrupted by service restart"},
            )

    def _persist_new_plan(self, plan: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.transaction() as connection:
            connection.execute(
                """
                INSERT INTO plans
                    (id, project_id, revision, requested_by, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan["id"],
                    plan["project_id"],
                    plan["revision"],
                    plan["requested_by"],
                    plan["created_at"],
                    plan["status"],
                ),
            )
            connection.executemany(
                """
                INSERT INTO plan_tasks
                    (plan_id, role, task_id, title, depends_on_json, status,
                     output_json, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                """,
                [
                    (
                        plan["id"],
                        task["role"],
                        task["id"],
                        task["title"],
                        _json_dump(task["depends_on"]),
                        task["status"],
                    )
                    for task in plan["tasks"].values()
                ],
            )

    def _persist_task(self, plan_id: str, task: dict[str, Any]) -> None:
        if self.store is None:
            return
        output = None if task["output"] is None else _json_dump(task["output"])
        with self.store.transaction() as connection:
            connection.execute(
                """
                UPDATE plan_tasks
                SET status = ?, output_json = ?, started_at = ?, completed_at = ?
                WHERE plan_id = ? AND role = ?
                """,
                (
                    task["status"],
                    output,
                    task["started_at"],
                    task["completed_at"],
                    plan_id,
                    task["role"],
                ),
            )

    def _persist_plan_status(self, plan_id: str, status: str) -> None:
        if self.store is None:
            return
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE plans SET status = ? WHERE id = ?", (status, plan_id)
            )

    def create_plan(
        self,
        *,
        project_id: str,
        revision: int,
        requested_by: str,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        project_id = validate_string(project_id, "project_id", max_len=120)
        requested_by = validate_string(requested_by, "requested_by", max_len=160)
        snapshot = validate_dict(snapshot, "snapshot")

        with self._lock:
            if len(self._plans) >= MAX_PLANS:
                raise ValidationError("Plan capacity reached")
            plan_id = _new_id("plan")
            tasks = {
                role: {
                    "id": f"{plan_id}-{role}",
                    "role": role,
                    "title": ROLE_LABELS[role],
                    "depends_on": list(ROLE_GRAPH[role]),
                    "status": "pending",
                    "output": None,
                    "started_at": None,
                    "completed_at": None,
                }
                for role in ROLE_GRAPH
            }
            plan = {
                "id": plan_id,
                "project_id": project_id,
                "revision": revision,
                "requested_by": requested_by,
                "created_at": time.time(),
                "status": "running",
                "tasks": tasks,
                "approvals": [],
            }
            self._plans[plan_id] = plan
            self._persist_new_plan(plan)
            self._log(plan_id, "plan.created", {"project_id": project_id, "revision": revision})

        self._execute(plan_id, snapshot)
        return self.get_plan(plan_id)

    def _execute(self, plan_id: str, snapshot: dict[str, Any]) -> None:
        outputs: dict[str, Any] = {}
        completed: set[str] = set()
        remaining = set(ROLE_GRAPH)

        while remaining:
            ready = [
                role
                for role in remaining
                if all(dep in completed for dep in ROLE_GRAPH[role])
            ]
            if not ready:
                # Defensive guard: the built-in graph is acyclic by
                # construction, so this should be unreachable.
                with self._lock:
                    self._plans[plan_id]["status"] = "failed"
                    self._persist_plan_status(plan_id, "failed")
                self._log(plan_id, "plan.failed", {"reason": "dependency cycle detected"})
                return

            with self._lock:
                for role in ready:
                    self._plans[plan_id]["tasks"][role]["status"] = "running"
                    self._plans[plan_id]["tasks"][role]["started_at"] = time.time()
                    self._persist_task(plan_id, self._plans[plan_id]["tasks"][role])
            self._log(plan_id, "tasks.started", {"roles": ready})

            futures = {
                role: self._executor.submit(_ROLE_RUNNERS[role], snapshot, dict(outputs))
                for role in ready
            }
            for role, future in futures.items():
                try:
                    output = future.result()
                    status = "completed"
                except Exception as exc:  # defensive: role runners are pure/deterministic
                    output = {"error": str(exc)}
                    status = "failed"
                outputs[role] = output
                with self._lock:
                    task = self._plans[plan_id]["tasks"][role]
                    task["status"] = status
                    task["output"] = output
                    task["completed_at"] = time.time()
                    self._persist_task(plan_id, task)
                self._log(plan_id, f"task.{status}", {"role": role})
                completed.add(role)
                remaining.discard(role)

        with self._lock:
            plan = self._plans[plan_id]
            any_failed = any(t["status"] == "failed" for t in plan["tasks"].values())
            plan["status"] = "failed" if any_failed else "completed"
            self._persist_plan_status(plan_id, plan["status"])
        self._log(plan_id, "plan.completed", {"status": self._plans[plan_id]["status"]})

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                raise KeyError(f"Unknown plan '{plan_id}'")
            return _deep_copy(plan)

    def list_plans(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            plans = [
                _deep_copy(plan)
                for plan in self._plans.values()
                if project_id is None or plan["project_id"] == project_id
            ]
        plans.sort(key=lambda p: p["created_at"], reverse=True)
        return plans

    def approve_plan(
        self, plan_id: str, *, approver: str, decision: str, comment: str = ""
    ) -> dict[str, Any]:
        approver = validate_string(approver, "approver", max_len=160)
        comment = validate_string(comment, "comment", max_len=4000, allow_empty=True, default="")
        if decision not in ("approved", "rejected"):
            raise ValidationError("decision must be 'approved' or 'rejected'")
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                raise KeyError(f"Unknown plan '{plan_id}'")
            if plan["status"] not in ("completed", "released", "rejected"):
                raise ValidationError(
                    "Plan must finish running (status 'completed') before it can "
                    "be approved or rejected"
                )
            event = {
                "id": _new_id("appr"),
                "approver": approver,
                "decision": decision,
                "comment": comment,
                "timestamp": time.time(),
            }
            plan["approvals"].append(event)
            plan["status"] = "released" if decision == "approved" else "rejected"
            if self.store is not None:
                with self.store.transaction() as connection:
                    connection.execute(
                        """
                        INSERT INTO plan_approvals
                            (id, plan_id, approver, decision, comment, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event["id"],
                            plan_id,
                            approver,
                            decision,
                            comment,
                            event["timestamp"],
                        ),
                    )
                    connection.execute(
                        "UPDATE plans SET status = ? WHERE id = ?",
                        (plan["status"], plan_id),
                    )
        self._log(plan_id, f"plan.{decision}", {"approver": approver})
        return self.get_plan(plan_id)

    def list_activity(self, plan_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            entries = [
                dict(entry)
                for entry in self._activity
                if plan_id is None or entry["plan_id"] == plan_id
            ]
        entries.sort(key=lambda e: e["timestamp"], reverse=True)
        return entries[: max(1, min(limit, 1000))]


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    if isinstance(value, set):
        return sorted(value)
    return value


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
