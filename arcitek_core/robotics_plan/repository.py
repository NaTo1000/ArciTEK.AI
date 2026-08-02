"""Thread-safe, SQLite-backed repository for the robotics engineering plan.

Design invariants:

* Revisions are immutable once created. Nothing in this module ever mutates
  a stored revision's engineering content (requirements/parts/wiring/
  hydraulics/pcb/findings) after creation.
* ``rollback`` never rewrites history -- it always appends a brand new
  revision whose content matches an earlier one.
* Every mutation records an append-only audit event so the full history of a
  project can be reconstructed.
* Approvals are tied to a specific, immutable revision number. Approval
  decisions are themselves append-only audit records; the latest decision
  determines the current status but earlier decisions are never discarded.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from . import rules
from .storage import SQLiteStore
from .validation import (
    MAX_LIST_ITEMS,
    MAX_NAME_LENGTH,
    MAX_TEXT_LENGTH,
    ValidationError,
    validate_dict,
    validate_list,
    validate_number,
    validate_string,
)

MAX_PROJECTS = 500
MAX_REVISIONS_PER_PROJECT = 1_000
APPROVAL_STATES = ("pending", "approved", "rejected")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _sanitize_requirement(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, str):
        item = {"text": item}
    item = validate_dict(item, f"requirements[{index}]")
    return {
        "id": validate_string(
            item.get("id") or f"REQ-{index + 1}",
            f"requirements[{index}].id",
            max_len=MAX_NAME_LENGTH,
        ),
        "text": validate_string(
            item.get("text"), f"requirements[{index}].text", max_len=MAX_TEXT_LENGTH
        ),
        "priority": validate_string(
            item.get("priority", "normal"),
            f"requirements[{index}].priority",
            max_len=40,
            allow_empty=True,
            default="normal",
        )
        or "normal",
    }


def _sanitize_vector(value: Any, field: str) -> list[float]:
    items = validate_list(value, field, max_items=3)
    if not items:
        return [0.0, 0.0, 0.0]
    if len(items) != 3:
        raise ValidationError(f"{field} must have exactly 3 components")
    return [validate_number(v, f"{field}[{i}]", minimum=-1e5, maximum=1e5) for i, v in enumerate(items)]


def _sanitize_part(item: Any, index: int) -> dict[str, Any]:
    item = validate_dict(item, f"parts[{index}]")
    return {
        "id": validate_string(item.get("id"), f"parts[{index}].id", max_len=MAX_NAME_LENGTH),
        "name": validate_string(
            item.get("name", item.get("id", "")),
            f"parts[{index}].name",
            max_len=MAX_NAME_LENGTH,
            allow_empty=True,
        ),
        "category": validate_string(
            item.get("category", "component"),
            f"parts[{index}].category",
            max_len=80,
            allow_empty=True,
            default="component",
        )
        or "component",
        "position": _sanitize_vector(item.get("position"), f"parts[{index}].position"),
        "dimensions": _sanitize_vector(
            item.get("dimensions") or [0, 0, 0], f"parts[{index}].dimensions"
        ),
        "mass_kg": validate_number(
            item.get("mass_kg"), f"parts[{index}].mass_kg", minimum=0, required=False
        ),
        "min_clearance_mm": validate_number(
            item.get("min_clearance_mm"),
            f"parts[{index}].min_clearance_mm",
            minimum=0,
            required=False,
            default=0.0,
        ),
        "material": validate_string(
            item.get("material", ""),
            f"parts[{index}].material",
            max_len=120,
            allow_empty=True,
            default="",
        ),
        "notes": validate_string(
            item.get("notes", ""),
            f"parts[{index}].notes",
            max_len=MAX_TEXT_LENGTH,
            allow_empty=True,
            default="",
        ),
    }


def _sanitize_wire(item: Any, index: int) -> dict[str, Any]:
    item = validate_dict(item, f"wiring[{index}]")
    return {
        "id": validate_string(item.get("id"), f"wiring[{index}].id", max_len=MAX_NAME_LENGTH),
        "from_part": validate_string(
            item.get("from_part"), f"wiring[{index}].from_part", max_len=MAX_NAME_LENGTH
        ),
        "to_part": validate_string(
            item.get("to_part"), f"wiring[{index}].to_part", max_len=MAX_NAME_LENGTH
        ),
        "voltage_v": validate_number(
            item.get("voltage_v"), f"wiring[{index}].voltage_v", minimum=0, required=False
        ),
        "current_a": validate_number(
            item.get("current_a"), f"wiring[{index}].current_a", minimum=0, required=False
        ),
        "gauge_awg": validate_number(
            item.get("gauge_awg"),
            f"wiring[{index}].gauge_awg",
            minimum=-10,
            maximum=40,
            required=False,
        ),
        "length_m": validate_number(
            item.get("length_m"), f"wiring[{index}].length_m", minimum=0, required=False
        ),
        "circuit": validate_string(
            item.get("circuit", ""),
            f"wiring[{index}].circuit",
            max_len=120,
            allow_empty=True,
            default="",
        ),
    }


def _sanitize_hydraulic(item: Any, index: int) -> dict[str, Any]:
    item = validate_dict(item, f"hydraulics[{index}]")
    return {
        "id": validate_string(item.get("id"), f"hydraulics[{index}].id", max_len=MAX_NAME_LENGTH),
        "name": validate_string(
            item.get("name", item.get("id", "")),
            f"hydraulics[{index}].name",
            max_len=MAX_NAME_LENGTH,
            allow_empty=True,
        ),
        "pressure_bar": validate_number(
            item.get("pressure_bar"),
            f"hydraulics[{index}].pressure_bar",
            minimum=0,
            required=False,
        ),
        "max_pressure_bar": validate_number(
            item.get("max_pressure_bar"),
            f"hydraulics[{index}].max_pressure_bar",
            minimum=0,
            required=False,
        ),
        "flow_lpm": validate_number(
            item.get("flow_lpm"), f"hydraulics[{index}].flow_lpm", minimum=0, required=False
        ),
        "max_flow_lpm": validate_number(
            item.get("max_flow_lpm"),
            f"hydraulics[{index}].max_flow_lpm",
            minimum=0,
            required=False,
        ),
        "diameter_mm": validate_number(
            item.get("diameter_mm"),
            f"hydraulics[{index}].diameter_mm",
            minimum=0,
            required=False,
        ),
        "fluid": validate_string(
            item.get("fluid", ""),
            f"hydraulics[{index}].fluid",
            max_len=80,
            allow_empty=True,
            default="",
        ),
    }


def _sanitize_pcb(value: Any) -> dict[str, Any]:
    value = validate_dict(value, "pcb")
    if not value:
        return {}
    nets = validate_list(value.get("nets"), "pcb.nets", max_items=MAX_LIST_ITEMS)
    components = validate_list(
        value.get("components"), "pcb.components", max_items=MAX_LIST_ITEMS
    )
    return {
        "board_name": validate_string(
            value.get("board_name", "board"),
            "pcb.board_name",
            max_len=MAX_NAME_LENGTH,
            allow_empty=True,
            default="board",
        ),
        "layer_count": validate_number(
            value.get("layer_count"), "pcb.layer_count", minimum=1, maximum=64, required=False
        ),
        "min_trace_width_mm": validate_number(
            value.get("min_trace_width_mm"),
            "pcb.min_trace_width_mm",
            minimum=0,
            required=False,
        ),
        "min_clearance_mm": validate_number(
            value.get("min_clearance_mm"),
            "pcb.min_clearance_mm",
            minimum=0,
            required=False,
        ),
        "nets": [validate_dict(net, "pcb.nets[]") for net in nets],
        "components": [validate_dict(comp, "pcb.components[]") for comp in components],
    }


def sanitize_revision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the mutable engineering content of a revision."""

    payload = validate_dict(payload, "payload")
    requirements = validate_list(payload.get("requirements"), "requirements")
    parts = validate_list(payload.get("parts"), "parts")
    wiring = validate_list(payload.get("wiring"), "wiring")
    hydraulics = validate_list(payload.get("hydraulics"), "hydraulics")
    return {
        "requirements": [
            _sanitize_requirement(item, i) for i, item in enumerate(requirements)
        ],
        "parts": [_sanitize_part(item, i) for i, item in enumerate(parts)],
        "wiring": [_sanitize_wire(item, i) for i, item in enumerate(wiring)],
        "hydraulics": [_sanitize_hydraulic(item, i) for i, item in enumerate(hydraulics)],
        "pcb": _sanitize_pcb(payload.get("pcb")),
    }


class ProjectRepository:
    """SQLite-backed project store preserving immutable revision history."""

    def __init__(
        self,
        database: str | Path = ":memory:",
        *,
        store: SQLiteStore | None = None,
    ) -> None:
        self.store = store or SQLiteStore(database)

    # -- audit -----------------------------------------------------------
    @staticmethod
    def _record_event(
        connection: sqlite3.Connection,
        project_id: str,
        actor: str,
        action: str,
        details: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events
                (id, timestamp, project_id, actor, action, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("evt"),
                time.time(),
                project_id,
                actor,
                action,
                _json_dump(details),
            ),
        )

    def list_events(self, project_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 1000))
        sql = """
            SELECT id, timestamp, project_id, actor, action, details_json
            FROM audit_events
        """
        params: list[Any] = []
        if project_id is not None:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(bounded_limit)
        with self.store.lock:
            rows = self.store.connection.execute(sql, params).fetchall()
        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "project_id": row["project_id"],
                "actor": row["actor"],
                "action": row["action"],
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]

    # -- projects ----------------------------------------------------------
    def create_project(
        self,
        *,
        name: str,
        description: str = "",
        author: str,
        requirements=None,
        parts=None,
        wiring=None,
        hydraulics=None,
        pcb=None,
    ) -> dict[str, Any]:
        name = validate_string(name, "name", max_len=MAX_NAME_LENGTH)
        description = validate_string(
            description, "description", max_len=MAX_TEXT_LENGTH, allow_empty=True, default=""
        )
        author = validate_string(author, "author", max_len=MAX_NAME_LENGTH)
        content = sanitize_revision_payload(
            {
                "requirements": requirements,
                "parts": parts,
                "wiring": wiring,
                "hydraulics": hydraulics,
                "pcb": pcb,
            }
        )

        with self.store.transaction() as connection:
            count = connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            if count >= MAX_PROJECTS:
                raise ValidationError("Project capacity reached")
            project_id = _new_id("proj")
            revision = self._build_revision(
                number=1,
                parent=None,
                author=author,
                message="Initial revision",
                content=content,
            )
            created_at = time.time()
            connection.execute(
                """
                INSERT INTO projects
                    (id, name, description, created_at, current_revision, domain)
                VALUES (?, ?, ?, ?, 1, 'robotics')
                """,
                (project_id, name, description, created_at),
            )
            self._insert_revision(connection, project_id, revision)
            self._record_event(
                connection,
                project_id,
                author,
                "project.created",
                {"name": name, "revision": 1},
            )
        return self._project_view(project_id)

    @staticmethod
    def _build_revision(
        *, number: int, parent: int | None, author: str, message: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        findings = rules.run_all(
            parts=content["parts"],
            wiring=content["wiring"],
            hydraulics=content["hydraulics"],
            pcb=content["pcb"],
        )
        return {
            "number": number,
            "parent": parent,
            "created_at": time.time(),
            "author": author,
            "message": message,
            "requirements": content["requirements"],
            "parts": content["parts"],
            "wiring": content["wiring"],
            "hydraulics": content["hydraulics"],
            "pcb": content["pcb"],
            "findings": findings,
        }

    @staticmethod
    def _insert_revision(
        connection: sqlite3.Connection,
        project_id: str,
        revision: dict[str, Any],
    ) -> None:
        content = {
            key: revision[key]
            for key in ("requirements", "parts", "wiring", "hydraulics", "pcb", "findings")
        }
        serialized = _json_dump(content)
        connection.execute(
            """
            INSERT INTO revisions
                (project_id, number, parent, created_at, author, message,
                 content_json, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                revision["number"],
                revision["parent"],
                revision["created_at"],
                revision["author"],
                revision["message"],
                serialized,
                hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            ),
        )

    @staticmethod
    def _project_from_row(row: sqlite3.Row | None, project_id: str) -> dict[str, Any]:
        if row is None:
            raise KeyError(f"Unknown project '{project_id}'")
        return dict(row)

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self._project_view(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        with self.store.lock:
            ids = [
                row["id"]
                for row in self.store.connection.execute(
                    "SELECT id FROM projects ORDER BY created_at"
                ).fetchall()
            ]
        return [self._project_view(pid) for pid in ids]

    def _project_view(self, project_id: str) -> dict[str, Any]:
        with self.store.lock:
            connection = self.store.connection
            project = self._project_from_row(
                connection.execute(
                    "SELECT * FROM projects WHERE id = ?", (project_id,)
                ).fetchone(),
                project_id,
            )
            revision_row = connection.execute(
                """
                SELECT content_json FROM revisions
                WHERE project_id = ? AND number = ?
                """,
                (project_id, project["current_revision"]),
            ).fetchone()
            revision_count = connection.execute(
                "SELECT COUNT(*) FROM revisions WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
            approval = connection.execute(
                """
                SELECT decision FROM revision_approvals
                WHERE project_id = ? AND revision = ?
                ORDER BY timestamp DESC, rowid DESC LIMIT 1
                """,
                (project_id, project["current_revision"]),
            ).fetchone()
        content = json.loads(revision_row["content_json"])
        return {
            "id": project["id"],
            "name": project["name"],
            "description": project["description"],
            "created_at": project["created_at"],
            "current_revision": project["current_revision"],
            "revision_count": revision_count,
            "findings_summary": _summarize_findings(content["findings"]),
            "approval_status": approval["decision"] if approval else "pending",
            "domain": project["domain"],
        }

    # -- revisions -----------------------------------------------------
    def create_revision(
        self,
        project_id: str,
        *,
        author: str,
        message: str = "",
        requirements=None,
        parts=None,
        wiring=None,
        hydraulics=None,
        pcb=None,
        base_revision: int | None = None,
    ) -> dict[str, Any]:
        author = validate_string(author, "author", max_len=MAX_NAME_LENGTH)
        message = validate_string(
            message, "message", max_len=MAX_TEXT_LENGTH, allow_empty=True, default=""
        )
        with self.store.transaction() as connection:
            project = self._project_from_row(
                connection.execute(
                    "SELECT * FROM projects WHERE id = ?", (project_id,)
                ).fetchone(),
                project_id,
            )
            revision_count = connection.execute(
                "SELECT COUNT(*) FROM revisions WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
            if revision_count >= MAX_REVISIONS_PER_PROJECT:
                raise ValidationError("Revision capacity reached for this project")
            base_number = base_revision or project["current_revision"]
            base_row = connection.execute(
                """
                SELECT * FROM revisions
                WHERE project_id = ? AND number = ?
                """,
                (project_id, base_number),
            ).fetchone()
            if base_row is None:
                raise ValidationError(f"Unknown base revision {base_number}")
            base = self._revision_from_row(base_row)

            # Start from the base revision's content; only override fields the
            # caller explicitly supplied so unspecified sections carry over
            # verbatim (still validated fresh, never mutated in place).
            merged = {
                "requirements": requirements if requirements is not None else base["requirements"],
                "parts": parts if parts is not None else base["parts"],
                "wiring": wiring if wiring is not None else base["wiring"],
                "hydraulics": hydraulics if hydraulics is not None else base["hydraulics"],
                "pcb": pcb if pcb is not None else base["pcb"],
            }
            content = sanitize_revision_payload(merged)
            next_number = connection.execute(
                "SELECT COALESCE(MAX(number), 0) + 1 FROM revisions WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            revision = self._build_revision(
                number=next_number,
                parent=base_number,
                author=author,
                message=message or f"Revision {next_number}",
                content=content,
            )
            self._insert_revision(connection, project_id, revision)
            connection.execute(
                "UPDATE projects SET current_revision = ? WHERE id = ?",
                (next_number, project_id),
            )
            self._record_event(
                connection,
                project_id,
                author,
                "revision.created",
                {"revision": next_number, "parent": base_number},
            )
        return self.get_revision(project_id, next_number)

    def get_revision(self, project_id: str, revision_number: int) -> dict[str, Any]:
        with self.store.lock:
            connection = self.store.connection
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise KeyError(f"Unknown project '{project_id}'")
            row = connection.execute(
                """
                SELECT * FROM revisions
                WHERE project_id = ? AND number = ?
                """,
                (project_id, revision_number),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown revision {revision_number}")
            approvals = self._approval_rows(
                connection, project_id, revision_number
            )
        view = self._revision_from_row(row)
        view["approvals"] = approvals
        view["approval_status"] = approvals[-1]["decision"] if approvals else "pending"
        return view

    @staticmethod
    def _revision_from_row(row: sqlite3.Row) -> dict[str, Any]:
        content = json.loads(row["content_json"])
        return {
            "number": row["number"],
            "parent": row["parent"],
            "created_at": row["created_at"],
            "author": row["author"],
            "message": row["message"],
            **content,
        }

    def list_revisions(self, project_id: str) -> list[dict[str, Any]]:
        with self.store.lock:
            connection = self.store.connection
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise KeyError(f"Unknown project '{project_id}'")
            numbers = [
                row["number"]
                for row in connection.execute(
                    """
                    SELECT number FROM revisions
                    WHERE project_id = ? ORDER BY number
                    """,
                    (project_id,),
                ).fetchall()
            ]
        return [self.get_revision(project_id, number) for number in numbers]

    def rollback(self, project_id: str, target_revision: int, *, author: str, message: str = "") -> dict[str, Any]:
        """Create a new revision whose content matches ``target_revision``.

        History is never rewritten: the target revision remains unchanged
        and a new, higher-numbered revision is appended that duplicates its
        content.
        """

        try:
            target = self.get_revision(project_id, target_revision)
            current_revision = self.get_project(project_id)["current_revision"]
        except KeyError as exc:
            if "revision" in str(exc):
                raise ValidationError(f"Unknown target revision {target_revision}") from exc
            raise
        return self.create_revision(
            project_id,
            author=author,
            message=message or f"Rollback to revision {target_revision}",
            requirements=target["requirements"],
            parts=target["parts"],
            wiring=target["wiring"],
            hydraulics=target["hydraulics"],
            pcb=target["pcb"],
            base_revision=current_revision,
        )

    # -- approvals -------------------------------------------------------
    def approve_revision(
        self,
        project_id: str,
        revision_number: int,
        *,
        approver: str,
        decision: str,
        comment: str = "",
    ) -> dict[str, Any]:
        approver = validate_string(approver, "approver", max_len=MAX_NAME_LENGTH)
        comment = validate_string(
            comment, "comment", max_len=MAX_TEXT_LENGTH, allow_empty=True, default=""
        )
        if decision not in ("approved", "rejected"):
            raise ValidationError("decision must be 'approved' or 'rejected'")
        with self.store.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise KeyError(f"Unknown project '{project_id}'")
            if connection.execute(
                """
                SELECT 1 FROM revisions
                WHERE project_id = ? AND number = ?
                """,
                (project_id, revision_number),
            ).fetchone() is None:
                raise ValidationError(f"Unknown revision {revision_number}")
            event = {
                "id": _new_id("appr"),
                "revision": revision_number,
                "approver": approver,
                "decision": decision,
                "comment": comment,
                "timestamp": time.time(),
            }
            connection.execute(
                """
                INSERT INTO revision_approvals
                    (id, project_id, revision, approver, decision, comment, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    project_id,
                    revision_number,
                    approver,
                    decision,
                    comment,
                    event["timestamp"],
                ),
            )
            self._record_event(
                connection,
                project_id,
                approver,
                f"revision.{decision}",
                {"revision": revision_number, "comment": comment},
            )
        return self.get_revision(project_id, revision_number)

    def list_approvals(self, project_id: str, revision_number: int | None = None) -> list[dict[str, Any]]:
        with self.store.lock:
            connection = self.store.connection
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise KeyError(f"Unknown project '{project_id}'")
            return self._approval_rows(connection, project_id, revision_number)

    @staticmethod
    def _approval_rows(
        connection: sqlite3.Connection,
        project_id: str,
        revision_number: int | None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, revision, approver, decision, comment, timestamp
            FROM revision_approvals WHERE project_id = ?
        """
        params: list[Any] = [project_id]
        if revision_number is not None:
            sql += " AND revision = ?"
            params.append(revision_number)
        sql += " ORDER BY timestamp, rowid"
        return [dict(row) for row in connection.execute(sql, params).fetchall()]

    # -- findings ---------------------------------------------------------
    def get_findings(self, project_id: str, revision_number: int | None = None) -> list[dict[str, Any]]:
        if revision_number is None:
            revision_number = self.get_project(project_id)["current_revision"]
        try:
            return self.get_revision(project_id, revision_number)["findings"]
        except KeyError as exc:
            raise ValidationError(f"Unknown revision {revision_number}") from exc


def _summarize_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    summary = {severity: 0 for severity in rules.SEVERITY_ORDER}
    for finding in findings:
        severity = finding.get("severity", "info")
        summary[severity] = summary.get(severity, 0) + 1
    summary["total"] = len(findings)
    return summary


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
