"""Thread-safe, in-memory project repository for the robotics engineering plan.

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

import copy
import threading
import time
import uuid
from typing import Any

from . import rules
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
    """In-memory, thread-safe store for projects and their revision history."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._projects: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []

    # -- audit -----------------------------------------------------------
    def _record_event(self, project_id: str, actor: str, action: str, details: dict[str, Any]) -> None:
        event = {
            "id": _new_id("evt"),
            "timestamp": time.time(),
            "project_id": project_id,
            "actor": actor,
            "action": action,
            "details": details,
        }
        self._events.append(event)
        if len(self._events) > 10_000:
            del self._events[: len(self._events) - 10_000]

    def list_events(self, project_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            events = [
                copy.deepcopy(event)
                for event in self._events
                if project_id is None or event["project_id"] == project_id
            ]
        events.sort(key=lambda event: event["timestamp"], reverse=True)
        return events[: max(1, min(limit, 1000))]

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

        with self._lock:
            if len(self._projects) >= MAX_PROJECTS:
                raise ValidationError("Project capacity reached")
            project_id = _new_id("proj")
            revision = self._build_revision(
                number=1,
                parent=None,
                author=author,
                message="Initial revision",
                content=content,
            )
            project = {
                "id": project_id,
                "name": name,
                "description": description,
                "created_at": time.time(),
                "revisions": {1: revision},
                "current_revision": 1,
                "approvals": {},  # revision_number -> list[approval event]
                "domain": "robotics",
            }
            self._projects[project_id] = project
            self._record_event(
                project_id, author, "project.created", {"name": name, "revision": 1}
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

    def _get_project_locked(self, project_id: str) -> dict[str, Any]:
        project = self._projects.get(project_id)
        if project is None:
            raise KeyError(f"Unknown project '{project_id}'")
        return project

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            self._get_project_locked(project_id)
        return self._project_view(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(self._projects.keys())
        return [self._project_view(pid) for pid in ids]

    def _project_view(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._get_project_locked(project_id)
            current = project["revisions"][project["current_revision"]]
            approvals = project["approvals"].get(project["current_revision"], [])
            latest_approval = approvals[-1] if approvals else None
            return {
                "id": project["id"],
                "name": project["name"],
                "description": project["description"],
                "created_at": project["created_at"],
                "current_revision": project["current_revision"],
                "revision_count": len(project["revisions"]),
                "findings_summary": _summarize_findings(current["findings"]),
                "approval_status": (latest_approval or {}).get("decision", "pending"),
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
        with self._lock:
            project = self._get_project_locked(project_id)
            if len(project["revisions"]) >= MAX_REVISIONS_PER_PROJECT:
                raise ValidationError("Revision capacity reached for this project")
            base_number = base_revision or project["current_revision"]
            base = project["revisions"].get(base_number)
            if base is None:
                raise ValidationError(f"Unknown base revision {base_number}")

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
            next_number = max(project["revisions"]) + 1
            revision = self._build_revision(
                number=next_number,
                parent=base_number,
                author=author,
                message=message or f"Revision {next_number}",
                content=content,
            )
            project["revisions"][next_number] = revision
            project["current_revision"] = next_number
            self._record_event(
                project_id,
                author,
                "revision.created",
                {"revision": next_number, "parent": base_number},
            )
        return self.get_revision(project_id, next_number)

    def get_revision(self, project_id: str, revision_number: int) -> dict[str, Any]:
        with self._lock:
            project = self._get_project_locked(project_id)
            revision = project["revisions"].get(revision_number)
            if revision is None:
                raise KeyError(f"Unknown revision {revision_number}")
            approvals = project["approvals"].get(revision_number, [])
            view = copy.deepcopy(revision)
            view["approvals"] = copy.deepcopy(approvals)
            view["approval_status"] = (approvals[-1]["decision"] if approvals else "pending")
        return view

    def list_revisions(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            project = self._get_project_locked(project_id)
            numbers = sorted(project["revisions"].keys())
        return [self.get_revision(project_id, number) for number in numbers]

    def rollback(self, project_id: str, target_revision: int, *, author: str, message: str = "") -> dict[str, Any]:
        """Create a new revision whose content matches ``target_revision``.

        History is never rewritten: the target revision remains unchanged
        and a new, higher-numbered revision is appended that duplicates its
        content.
        """

        with self._lock:
            project = self._get_project_locked(project_id)
            target = project["revisions"].get(target_revision)
            if target is None:
                raise ValidationError(f"Unknown target revision {target_revision}")
        return self.create_revision(
            project_id,
            author=author,
            message=message or f"Rollback to revision {target_revision}",
            requirements=copy.deepcopy(target["requirements"]),
            parts=copy.deepcopy(target["parts"]),
            wiring=copy.deepcopy(target["wiring"]),
            hydraulics=copy.deepcopy(target["hydraulics"]),
            pcb=copy.deepcopy(target["pcb"]),
            base_revision=project["current_revision"],
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
        with self._lock:
            project = self._get_project_locked(project_id)
            if revision_number not in project["revisions"]:
                raise ValidationError(f"Unknown revision {revision_number}")
            event = {
                "id": _new_id("appr"),
                "revision": revision_number,
                "approver": approver,
                "decision": decision,
                "comment": comment,
                "timestamp": time.time(),
            }
            project["approvals"].setdefault(revision_number, []).append(event)
            self._record_event(
                project_id,
                approver,
                f"revision.{decision}",
                {"revision": revision_number, "comment": comment},
            )
        return self.get_revision(project_id, revision_number)

    def list_approvals(self, project_id: str, revision_number: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            project = self._get_project_locked(project_id)
            if revision_number is not None:
                return copy.deepcopy(project["approvals"].get(revision_number, []))
            merged: list[dict[str, Any]] = []
            for events in project["approvals"].values():
                merged.extend(events)
            return copy.deepcopy(sorted(merged, key=lambda e: e["timestamp"]))

    # -- findings ---------------------------------------------------------
    def get_findings(self, project_id: str, revision_number: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            project = self._get_project_locked(project_id)
            number = revision_number or project["current_revision"]
            revision = project["revisions"].get(number)
            if revision is None:
                raise ValidationError(f"Unknown revision {number}")
            return copy.deepcopy(revision["findings"])


def _summarize_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    summary = {severity: 0 for severity in rules.SEVERITY_ORDER}
    for finding in findings:
        severity = finding.get("severity", "info")
        summary[severity] = summary.get(severity, 0) + 1
    summary["total"] = len(findings)
    return summary
