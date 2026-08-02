"""Neutral engineering format registry and metadata-level adapters.

This module deliberately does **not** parse or convert real CAD/EDA
geometry. It validates file extensions and declared metadata against a
known schema for each supported neutral exchange format and produces a
safe "manifest" describing what an import or export would contain. Any
consumer expecting native geometry conversion (e.g. actually reading a
STEP B-Rep or rendering Gerber apertures) must use a dedicated CAD/EDA
toolchain -- this is explicitly out of scope for the MVP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .validation import MAX_TEXT_LENGTH, ValidationError, validate_dict, validate_string

DISCLAIMER = (
    "Metadata/extension validation only. This adapter does not parse or "
    "convert native CAD/EDA geometry."
)


@dataclass(frozen=True)
class FormatSpec:
    format_id: str
    label: str
    kind: str
    extensions: tuple[str, ...]
    required_metadata: tuple[str, ...] = field(default_factory=tuple)


FORMAT_SPECS: dict[str, FormatSpec] = {
    spec.format_id: spec
    for spec in (
        FormatSpec("step", "STEP (ISO 10303-21)", "cad-solid", (".step", ".stp"), ("units",)),
        FormatSpec("stl", "STL mesh", "mesh", (".stl",), ("units",)),
        FormatSpec("dxf", "DXF 2D drawing", "drawing-2d", (".dxf",), ("units",)),
        FormatSpec(
            "urdf",
            "URDF robot description",
            "robot-description",
            (".urdf", ".xacro"),
            ("root_link",),
        ),
        FormatSpec(
            "gerber",
            "Gerber (RS-274X) PCB fabrication",
            "pcb-fab",
            (".gbr", ".ger", ".gtl", ".gbl", ".gto", ".gbo"),
            ("layer",),
        ),
        FormatSpec(
            "ipc2581",
            "IPC-2581 PCB design/fab exchange",
            "pcb-fab",
            (".xml", ".ipc"),
            ("revision",),
        ),
        FormatSpec(
            "netlist",
            "Electrical netlist",
            "electrical",
            (".net", ".cir", ".ckt"),
            ("nets",),
        ),
    )
}


def list_formats() -> list[dict[str, Any]]:
    return [
        {
            "id": spec.format_id,
            "label": spec.label,
            "kind": spec.kind,
            "extensions": list(spec.extensions),
            "required_metadata": list(spec.required_metadata),
            "disclaimer": DISCLAIMER,
        }
        for spec in FORMAT_SPECS.values()
    ]


def get_format(format_id: str) -> FormatSpec:
    format_id = validate_string(format_id, "format_id", max_len=40)
    spec = FORMAT_SPECS.get(format_id.lower())
    if spec is None:
        raise ValidationError(f"Unsupported format '{format_id}'")
    return spec


def validate_import(format_id: str, filename: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a proposed import's filename/metadata and return a manifest.

    Never touches file contents; this is a bounded, metadata-only check.
    """

    spec = get_format(format_id)
    filename = validate_string(filename, "filename", max_len=260)
    metadata = validate_dict(metadata, "metadata")

    issues: list[str] = []
    lowered = filename.lower()
    extension_ok = any(lowered.endswith(ext) for ext in spec.extensions)
    if not extension_ok:
        issues.append(
            f"Filename extension does not match expected extensions for "
            f"{spec.label}: {', '.join(spec.extensions)}"
        )
    missing = [key for key in spec.required_metadata if key not in metadata]
    if missing:
        issues.append(f"Missing required metadata fields: {', '.join(missing)}")

    return {
        "format": spec.format_id,
        "kind": spec.kind,
        "filename": filename,
        "extension_ok": extension_ok,
        "metadata_ok": not missing,
        "issues": issues,
        "ok": extension_ok and not missing,
        "disclaimer": DISCLAIMER,
    }


def build_export_manifest(format_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a safe manifest describing what an export *would* contain.

    This never writes real CAD/EDA files; it summarizes the declared
    payload against the format's expectations so callers can confirm
    readiness before invoking an actual external toolchain.
    """

    spec = get_format(format_id)
    payload = validate_dict(payload, "payload")
    present = {key: (key in payload) for key in spec.required_metadata}
    missing = [key for key, ok in present.items() if not ok]
    suggested_filename = f"export.{spec.extensions[0].lstrip('.')}"
    return {
        "format": spec.format_id,
        "kind": spec.kind,
        "suggested_filename": suggested_filename,
        "required_metadata_present": present,
        "ready": not missing,
        "issues": (
            [f"Missing required metadata fields: {', '.join(missing)}"] if missing else []
        ),
        "disclaimer": DISCLAIMER,
    }


def validate_bounded_note(note: Any) -> str:
    return validate_string(note, "note", max_len=MAX_TEXT_LENGTH, allow_empty=True, default="")
