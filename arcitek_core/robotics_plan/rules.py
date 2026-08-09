"""Rule-based flaw detection for robotics engineering data.

This module never claims perfect or complete coverage. Every finding carries
an explicit ``confidence`` (0-1, capped below 1.0) and a ``tolerance``
description of the numerical margin used, so downstream consumers can judge
how much to trust an automated result. Detection is limited to what is
representable in the supplied metadata (positions/dimensions for clearance,
simple electrical ratings for wiring, and pressure/flow ratings for
hydraulics) -- it is not a substitute for certified engineering analysis.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

# Never claim certainty: cap confidence for any automated rule finding.
MAX_CONFIDENCE = 0.95

SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")

# Simple, published-order-of-magnitude ampacity table (amps) for copper
# conductors in free air, used only as an illustrative bound -- not a
# substitute for a full derating calculation (insulation, bundling, ambient
# temperature, etc.).
_AWG_AMPACITY = {
    24: 3.5,
    22: 5.0,
    20: 7.5,
    18: 10.0,
    16: 13.0,
    14: 17.0,
    12: 23.0,
    10: 33.0,
    8: 46.0,
    6: 60.0,
    4: 80.0,
    2: 100.0,
    0: 125.0,
}

# Approximate copper resistance in ohm/meter per AWG, used only for a rough
# voltage-drop estimate.
_AWG_OHM_PER_M = {
    24: 0.0842,
    22: 0.0530,
    20: 0.0333,
    18: 0.0209,
    16: 0.0132,
    14: 0.00828,
    12: 0.00521,
    10: 0.00328,
    8: 0.00206,
    6: 0.00130,
    4: 0.000815,
    2: 0.000513,
    0: 0.000323,
}


def _new_finding(
    rule: str,
    severity: str,
    message: str,
    evidence: dict[str, Any],
    *,
    confidence: float,
    tolerance: str,
) -> dict[str, Any]:
    if severity not in SEVERITY_ORDER:
        severity = "info"
    return {
        "rule": rule,
        "severity": severity,
        "message": message,
        "evidence": evidence,
        "confidence": round(min(confidence, MAX_CONFIDENCE), 3),
        "tolerance": tolerance,
    }


def _nearest_awg_key(gauge: float, table: dict[int, float]) -> int:
    return min(table, key=lambda key: abs(key - gauge))


def check_clearances(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect bounding-box overlaps/clearance violations between parts.

    Each part is treated as an axis-aligned box centered at ``position``
    with full extents ``dimensions``. This is a coarse approximation --
    real geometry (rotations, non-box shapes) is not modeled in the MVP.
    """

    findings: list[dict[str, Any]] = []
    usable = [
        part
        for part in parts
        if isinstance(part.get("position"), list) and isinstance(part.get("dimensions"), list)
    ]
    for part_a, part_b in itertools.combinations(usable, 2):
        pos_a, dim_a = part_a["position"], part_a["dimensions"]
        pos_b, dim_b = part_b["position"], part_b["dimensions"]
        min_clearance = max(
            float(part_a.get("min_clearance_mm") or 0.0),
            float(part_b.get("min_clearance_mm") or 0.0),
        )
        gaps = []
        overlapping = True
        for axis in range(3):
            half_a = dim_a[axis] / 2.0
            half_b = dim_b[axis] / 2.0
            center_gap = abs(pos_a[axis] - pos_b[axis])
            axis_gap = center_gap - half_a - half_b
            gaps.append(axis_gap)
            if axis_gap > 0:
                overlapping = False
        gap_mm = max(gaps) if not overlapping else min(gaps)
        if overlapping:
            findings.append(
                _new_finding(
                    "geometry.collision",
                    "critical",
                    f"Parts '{part_a.get('id')}' and '{part_b.get('id')}' "
                    "bounding boxes overlap.",
                    {
                        "part_a": part_a.get("id"),
                        "part_b": part_b.get("id"),
                        "overlap_mm": round(-gap_mm, 3),
                    },
                    confidence=0.85,
                    tolerance="axis-aligned bounding box approximation, ±0 mm margin",
                )
            )
        elif min_clearance and gap_mm < min_clearance:
            findings.append(
                _new_finding(
                    "geometry.clearance",
                    "high",
                    f"Clearance between '{part_a.get('id')}' and "
                    f"'{part_b.get('id')}' is below the required minimum.",
                    {
                        "part_a": part_a.get("id"),
                        "part_b": part_b.get("id"),
                        "gap_mm": round(gap_mm, 3),
                        "required_min_clearance_mm": round(min_clearance, 3),
                    },
                    confidence=0.8,
                    tolerance="axis-aligned bounding box approximation",
                )
            )
    return findings


def check_wiring(
    wiring: list[dict[str, Any]], parts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate wiring connectivity and simple electrical limits."""

    findings: list[dict[str, Any]] = []
    known_ids = {part.get("id") for part in parts if part.get("id")}
    for wire in wiring:
        wire_id = wire.get("id", "?")
        from_id = wire.get("from_part")
        to_id = wire.get("to_part")
        if known_ids:
            if from_id not in known_ids:
                findings.append(
                    _new_finding(
                        "wiring.connectivity",
                        "high",
                        f"Wire '{wire_id}' references unknown source part "
                        f"'{from_id}'.",
                        {"wire": wire_id, "from_part": from_id},
                        confidence=0.9,
                        tolerance="exact identifier match against known parts",
                    )
                )
            if to_id not in known_ids:
                findings.append(
                    _new_finding(
                        "wiring.connectivity",
                        "high",
                        f"Wire '{wire_id}' references unknown target part "
                        f"'{to_id}'.",
                        {"wire": wire_id, "to_part": to_id},
                        confidence=0.9,
                        tolerance="exact identifier match against known parts",
                    )
                )
        if from_id == to_id and from_id is not None:
            findings.append(
                _new_finding(
                    "wiring.connectivity",
                    "medium",
                    f"Wire '{wire_id}' connects part '{from_id}' to itself.",
                    {"wire": wire_id, "part": from_id},
                    confidence=0.9,
                    tolerance="topological check only",
                )
            )

        gauge = wire.get("gauge_awg")
        current = wire.get("current_a")
        voltage = wire.get("voltage_v")
        length = wire.get("length_m")
        if isinstance(gauge, (int, float)) and isinstance(current, (int, float)):
            key = _nearest_awg_key(gauge, _AWG_AMPACITY)
            ampacity = _AWG_AMPACITY[key]
            if current > ampacity:
                findings.append(
                    _new_finding(
                        "wiring.overcurrent",
                        "critical",
                        f"Wire '{wire_id}' carries {current}A, exceeding the "
                        f"approximate {ampacity}A ampacity for AWG {gauge}.",
                        {
                            "wire": wire_id,
                            "current_a": current,
                            "gauge_awg": gauge,
                            "approx_ampacity_a": ampacity,
                        },
                        confidence=0.75,
                        tolerance=(
                            "free-air copper ampacity table, no insulation/"
                            "derating factors applied; ±15% typical variance"
                        ),
                    )
                )
        if (
            isinstance(gauge, (int, float))
            and isinstance(current, (int, float))
            and isinstance(length, (int, float))
            and isinstance(voltage, (int, float))
            and voltage > 0
        ):
            key = _nearest_awg_key(gauge, _AWG_OHM_PER_M)
            ohm_per_m = _AWG_OHM_PER_M[key]
            drop_v = 2 * length * ohm_per_m * current
            drop_pct = (drop_v / voltage) * 100
            if drop_pct > 5.0:
                findings.append(
                    _new_finding(
                        "wiring.voltage_drop",
                        "medium" if drop_pct <= 10.0 else "high",
                        f"Wire '{wire_id}' has an estimated {drop_pct:.1f}% "
                        "voltage drop over its run length.",
                        {
                            "wire": wire_id,
                            "estimated_drop_v": round(drop_v, 3),
                            "estimated_drop_pct": round(drop_pct, 2),
                        },
                        confidence=0.6,
                        tolerance=(
                            "round-trip resistance estimate from AWG table, "
                            "excludes connector/termination resistance"
                        ),
                    )
                )
    return findings


def check_hydraulics(hydraulics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate hydraulic pressure/flow ratings against declared limits."""

    findings: list[dict[str, Any]] = []
    for line in hydraulics:
        line_id = line.get("id", "?")
        pressure = line.get("pressure_bar")
        max_pressure = line.get("max_pressure_bar")
        flow = line.get("flow_lpm")
        max_flow = line.get("max_flow_lpm")
        diameter = line.get("diameter_mm")

        if isinstance(pressure, (int, float)) and isinstance(max_pressure, (int, float)):
            if pressure > max_pressure:
                findings.append(
                    _new_finding(
                        "hydraulics.overpressure",
                        "critical",
                        f"Line '{line_id}' operating pressure {pressure} bar "
                        f"exceeds its rated {max_pressure} bar limit.",
                        {
                            "line": line_id,
                            "pressure_bar": pressure,
                            "max_pressure_bar": max_pressure,
                        },
                        confidence=0.85,
                        tolerance="declared rating comparison, ±0 bar margin",
                    )
                )
            elif pressure > 0.9 * max_pressure:
                findings.append(
                    _new_finding(
                        "hydraulics.pressure_margin",
                        "medium",
                        f"Line '{line_id}' is operating above 90% of its "
                        "rated pressure limit.",
                        {
                            "line": line_id,
                            "pressure_bar": pressure,
                            "max_pressure_bar": max_pressure,
                        },
                        confidence=0.7,
                        tolerance="10% margin heuristic",
                    )
                )
        if isinstance(flow, (int, float)) and isinstance(max_flow, (int, float)):
            if flow > max_flow:
                findings.append(
                    _new_finding(
                        "hydraulics.overflow",
                        "critical",
                        f"Line '{line_id}' flow {flow} L/min exceeds its "
                        f"rated {max_flow} L/min limit.",
                        {"line": line_id, "flow_lpm": flow, "max_flow_lpm": max_flow},
                        confidence=0.85,
                        tolerance="declared rating comparison, ±0 L/min margin",
                    )
                )
        if (
            isinstance(flow, (int, float))
            and isinstance(diameter, (int, float))
            and diameter > 0
        ):
            # Approximate mean fluid velocity from flow / cross-section.
            radius_m = (diameter / 1000.0) / 2.0
            area_m2 = math.pi * radius_m**2
            velocity_mps = (flow / 60000.0) / area_m2 if area_m2 > 0 else 0.0
            if velocity_mps > 6.0:
                findings.append(
                    _new_finding(
                        "hydraulics.velocity",
                        "medium",
                        f"Line '{line_id}' estimated fluid velocity "
                        f"{velocity_mps:.2f} m/s exceeds the common 6 m/s "
                        "guideline for pressure lines.",
                        {
                            "line": line_id,
                            "estimated_velocity_mps": round(velocity_mps, 2),
                            "diameter_mm": diameter,
                            "flow_lpm": flow,
                        },
                        confidence=0.65,
                        tolerance="idealized incompressible flow estimate",
                    )
                )
    return findings


def run_all(
    *,
    parts: list[dict[str, Any]] | None = None,
    wiring: list[dict[str, Any]] | None = None,
    hydraulics: list[dict[str, Any]] | None = None,
    pcb: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run every rule category and return a combined findings list.

    The returned list is deterministic for identical input and carries no
    claim of 100% accuracy or completeness -- see each finding's
    ``confidence`` and ``tolerance`` fields.
    """

    parts = parts or []
    wiring = wiring or []
    hydraulics = hydraulics or []
    findings: list[dict[str, Any]] = []
    findings.extend(check_clearances(parts))
    findings.extend(check_wiring(wiring, parts))
    findings.extend(check_hydraulics(hydraulics))
    if pcb:
        min_clearance = pcb.get("min_clearance_mm")
        min_trace = pcb.get("min_trace_width_mm")
        if isinstance(min_trace, (int, float)) and min_trace < 0.15:
            findings.append(
                _new_finding(
                    "pcb.trace_width",
                    "high",
                    "Declared minimum trace width is below the common "
                    "0.15 mm (6 mil) fabrication guideline.",
                    {"min_trace_width_mm": min_trace},
                    confidence=0.6,
                    tolerance="generic fabrication guideline, not "
                    "manufacturer-specific",
                )
            )
        if isinstance(min_clearance, (int, float)) and min_clearance < 0.15:
            findings.append(
                _new_finding(
                    "pcb.clearance",
                    "high",
                    "Declared minimum copper clearance is below the "
                    "common 0.15 mm (6 mil) fabrication guideline.",
                    {"min_clearance_mm": min_clearance},
                    confidence=0.6,
                    tolerance="generic fabrication guideline, not "
                    "manufacturer-specific",
                )
            )
    findings.sort(key=lambda item: SEVERITY_ORDER.index(item["severity"]))
    return findings
