#!/usr/bin/env python3
"""Build validation coordinator for ArciTEK.AI.

The validator performs a lightweight pre-submission check across the repository:
- compiles Python source files
- validates package manifests (when present)
- verifies the core package imports cleanly
- produces a todo checklist and corrective prompt for any issues found
"""

from __future__ import annotations

import argparse
import json
import py_compile
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "htmlcov",
    ".mypy_cache",
}


@dataclass(frozen=True)
class ValidationFinding:
    severity: str
    category: str
    message: str
    file_path: Optional[Path] = None
    remediation: str = ""

    def to_todo_item(self) -> str:
        prefix = f"[{self.severity.upper()}]"
        return f"- [ ] {prefix} {self.message}"


class ValidationReport:
    def __init__(self, root: Path, findings: Sequence[ValidationFinding]):
        self.root = root
        self.findings = list(findings)

    def is_valid(self) -> bool:
        return not self.findings

    def todo_items(self) -> List[str]:
        return [finding.to_todo_item() for finding in self.findings]

    def corrective_prompt(self) -> str:
        if not self.findings:
            return "Repository validation passed. No corrective action required before submission."

        lines = [
            "Please address the following validation findings before resubmitting this build:",
        ]
        for finding in self.findings:
            detail = finding.message
            if finding.remediation:
                detail = f"{detail} ({finding.remediation})"
            lines.append(f"- {finding.category}: {detail}")
        lines.append(
            "Steering control: keep the repository aligned with the current build plan by resolving these issues and re-running the validator."
        )
        return "\n".join(lines)

    def render(self) -> str:
        status = "PASS" if self.is_valid() else "FAIL"
        lines = [
            f"ArciTEK.AI build validation for {self.root}",
            f"Status: {status}",
            "",
            "Todo checklist:",
        ]
        if self.findings:
            lines.extend(self.todo_items())
        else:
            lines.append("- [x] No validation issues detected")

        lines.extend(["", "Corrective prompt:"])
        lines.append(self.corrective_prompt())
        return "\n".join(lines)


def _should_skip(path: Path, root_path: Path) -> bool:
    try:
        relative_parts = path.relative_to(root_path).parts
    except ValueError:
        return False
    return any(part in SKIP_DIRS for part in relative_parts)


def validate_repository(root: Union[str, Path]) -> ValidationReport:
    root_path = Path(root).resolve()
    findings: List[ValidationFinding] = []

    if not root_path.exists():
        findings.append(
            ValidationFinding(
                severity="error",
                category="path",
                message=f"Repository path does not exist: {root_path}",
                file_path=root_path,
                remediation="Create or restore the repository directory before validation.",
            )
        )
        return ValidationReport(root_path, findings)

    python_files = sorted(
        path for path in root_path.rglob("*.py") if not _should_skip(path, root_path)
    )
    if not python_files:
        findings.append(
            ValidationFinding(
                severity="warning",
                category="scan",
                message="No Python source files were found to compile.",
                file_path=root_path,
                remediation="Add the primary Python sources before submission.",
            )
        )

    for file_path in python_files:
        try:
            py_compile.compile(str(file_path), doraise=True)
        except (py_compile.PyCompileError, SyntaxError, ValueError) as exc:
            findings.append(
                ValidationFinding(
                    severity="error",
                    category="syntax",
                    message=f"Python syntax check failed for {file_path.relative_to(root_path)}: {exc}",
                    file_path=file_path,
                    remediation="Fix syntax errors before resubmitting the build.",
                )
            )

    package_json = root_path / "package.json"
    if package_json.exists():
        try:
            with package_json.open("r", encoding="utf-8") as handle:
                json.load(handle)
        except json.JSONDecodeError as exc:
            findings.append(
                ValidationFinding(
                    severity="error",
                    category="manifest",
                    message=f"package.json is invalid JSON: {exc}",
                    file_path=package_json,
                    remediation="Repair the package.json syntax before submission.",
                )
            )

    core_package = root_path / "arcitek_core"
    import_check = [
        sys.executable,
        "-c",
        "import arcitek_core; import arcitek_core.precision_builder; print('import-ok')",
    ]
    try:
        subprocess.run(import_check, cwd=root_path, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        findings.append(
            ValidationFinding(
                severity="error",
                category="import",
                message=f"Core package import validation failed: {exc.stderr.strip() or exc.stdout.strip()}",
                file_path=core_package,
                remediation="Fix the package imports before submission.",
            )
        )

    return ValidationReport(root_path, findings)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a repository before build submission")
    parser.add_argument("--path", default=".", help="Repository root to validate")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = validate_repository(args.path)
    print(report.render())
    return 0 if report.is_valid() else 1


if __name__ == "__main__":
    raise SystemExit(main())
