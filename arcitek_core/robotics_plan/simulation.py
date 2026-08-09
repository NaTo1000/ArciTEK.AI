"""Simulation adapter interfaces for FreeCAD, KiCad and ROS 2/Gazebo.

The MVP never launches an external process. Availability is detected with a
read-only ``shutil.which`` lookup, and "dry runs" produce a deterministic,
structured result derived only from the supplied project snapshot and the
rule-based flaw detector -- they are explicitly not real physics/geometry
simulations. Every result carries ``verification_required: True`` and a
bounded confidence so callers do not mistake it for a certified simulation
outcome.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from typing import Any

from . import rules
from .validation import ValidationError, validate_dict, validate_string

MAX_CONFIDENCE = 0.9


@dataclass(frozen=True)
class SimTool:
    tool_id: str
    label: str
    binary_names: tuple[str, ...]
    capabilities: tuple[str, ...]
    supported_formats: tuple[str, ...]


SIM_TOOLS: dict[str, SimTool] = {
    spec.tool_id: spec
    for spec in (
        SimTool(
            "freecad",
            "FreeCAD",
            ("freecad", "freecadcmd", "FreeCAD"),
            ("geometry_check", "clearance_check", "assembly_review"),
            ("step", "stl", "dxf"),
        ),
        SimTool(
            "kicad",
            "KiCad",
            ("kicad", "kicad-cli"),
            ("drc", "erc", "netlist_review"),
            ("gerber", "ipc2581", "netlist"),
        ),
        SimTool(
            "ros2_gazebo",
            "ROS 2 / Gazebo",
            ("gz", "gazebo", "ros2"),
            ("urdf_validation", "physics_dry_run", "collision_dry_run"),
            ("urdf",),
        ),
    )
}


def list_tools() -> list[dict[str, Any]]:
    return [_capability_manifest(tool) for tool in SIM_TOOLS.values()]


def _capability_manifest(tool: SimTool) -> dict[str, Any]:
    available_path = None
    for binary in tool.binary_names:
        found = shutil.which(binary)
        if found:
            available_path = found
            break
    return {
        "id": tool.tool_id,
        "label": tool.label,
        "capabilities": list(tool.capabilities),
        "supported_formats": list(tool.supported_formats),
        "available": available_path is not None,
        "detected_path": available_path,
        "execution_mode": "dry_run_only",
        "note": (
            "Availability is a read-only PATH lookup only. This MVP never "
            "executes the external tool."
        ),
    }


def get_tool(tool_id: str) -> SimTool:
    tool_id = validate_string(tool_id, "tool_id", max_len=40)
    tool = SIM_TOOLS.get(tool_id.lower())
    if tool is None:
        raise ValidationError(f"Unsupported simulation tool '{tool_id}'")
    return tool


def dry_run(tool_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Produce a deterministic, structured dry-run result for ``tool_id``.

    ``snapshot`` is expected to look like a revision view (parts/wiring/
    hydraulics/pcb/findings). No subprocess is ever started.
    """

    tool = get_tool(tool_id)
    snapshot = validate_dict(snapshot, "snapshot")
    parts = snapshot.get("parts") or []
    wiring = snapshot.get("wiring") or []
    hydraulics = snapshot.get("hydraulics") or []
    pcb = snapshot.get("pcb") or {}
    findings = snapshot.get("findings")
    if findings is None:
        findings = rules.run_all(parts=parts, wiring=wiring, hydraulics=hydraulics, pcb=pcb)

    manifest = _capability_manifest(tool)
    relevant_rules = {
        "freecad": ("geometry.collision", "geometry.clearance"),
        "kicad": ("pcb.trace_width", "pcb.clearance", "wiring.connectivity"),
        "ros2_gazebo": ("geometry.collision", "wiring.overcurrent"),
    }[tool.tool_id]
    relevant_findings = [f for f in findings if f.get("rule") in relevant_rules]
    severity_blockers = [f for f in relevant_findings if f["severity"] in ("critical", "high")]

    status = "blocked" if severity_blockers else ("warning" if relevant_findings else "clear")
    return {
        "tool": tool.tool_id,
        "status": status,
        "generated_at": time.time(),
        "execution_mode": "dry_run_only",
        "verification_required": True,
        "confidence": MAX_CONFIDENCE if not relevant_findings else 0.6,
        "capability_manifest": manifest,
        "relevant_findings": relevant_findings,
        "part_count": len(parts),
        "wiring_count": len(wiring),
        "hydraulics_count": len(hydraulics),
        "note": (
            "Deterministic dry run derived from supplied metadata and rule-"
            "based findings; not an executed physics or geometry simulation."
        ),
    }
