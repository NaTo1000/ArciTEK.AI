"""
Guardian Security System - 24/7 defensive security watch.

Duties:
- Scan tracked source files for hardcoded secrets (API keys, tokens,
  private keys, passwords).
- Detect dangerous function usage (eval/exec, subprocess shell=True,
  unsafe deserialization).
- Audit dependencies against the OSV vulnerability database (optional,
  network-dependent) with strict query validation.
- Produce a consolidated security report persisted to the Guardian state
  directory.

This system only ever *detects and reports* defensive issues; it contains
no offensive capability.
"""

import io
import json
import logging
import re
import tokenize
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger("guardian.security")

# Accepted by OSV for the ecosystems we use.
_ALLOWED_ECOSYSTEMS = {"PyPI", "npm"}
_OSV_API_URL = "https://api.osv.dev/v1/query"

SECRET_PATTERNS = [
    (
        "generic-secret",
        re.compile(
            r"""(?i)(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)"""
            r"""\s*[:=]\s*['"][^'"\s]{8,}['"]"""
        ),
        "critical",
    ),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}"), "critical"),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "critical"),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "critical"),
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
        "critical",
    ),
    ("jwt-token", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "high"),
]

DANGEROUS_FUNCTIONS = [
    ("eval", re.compile(r"\beval\s*\("), "high"),
    ("exec", re.compile(r"\bexec\s*\("), "high"),
    ("shell-true", re.compile(r"shell\s*=\s*True"), "high"),
    ("pickle", re.compile(r"\bpickle\.loads?\s*\("), "medium"),
    ("yaml-load-unsafe", re.compile(r"\byaml\.load\s*\((?![^)]*Loader)"), "medium"),
    ("os-system", re.compile(r"\bos\.system\s*\("), "high"),
]




class SecurityFinding:
    """A security-relevant observation."""

    def __init__(self, kind: str, severity: str, message: str, file_path: str = None,
                 line_number: int = None):
        self.kind = kind
        self.severity = severity
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "timestamp": self.timestamp,
        }


class SecuritySystem:
    """The Guardian's defensive security subsystem."""

    def __init__(self, config):
        self.config = config
        self.last_report: Dict = {}

    # ------------------------------------------------------------------
    # Duties
    # ------------------------------------------------------------------
    def scan_for_secrets(self) -> List[SecurityFinding]:
        """Scan all configured source files for hardcoded secrets."""
        findings: List[SecurityFinding] = []

        for path in self._iter_source_files():
            rel_path = str(path.relative_to(self.config.root_dir))
            try:
                lines = path.read_text(errors="replace").splitlines()
            except OSError:
                continue

            for lineno, line in enumerate(lines, start=1):
                # Skip obvious placeholders/examples.
                lowered = line.lower()
                if any(token in lowered for token in ("example", "placeholder", "your-", "xxxx", "<")):
                    continue
                for name, pattern, severity in SECRET_PATTERNS:
                    if pattern.search(line):
                        findings.append(
                            SecurityFinding(
                                kind=name,
                                severity=severity,
                                message=f"Possible hardcoded secret ({name})",
                                file_path=rel_path,
                                line_number=lineno,
                            )
                        )

        if findings:
            logger.warning("Security scan found %d potential secret(s)", len(findings))
        return findings

    @staticmethod
    def _code_only_lines(text: str) -> List[tuple]:
        """Return (lineno, line) pairs with string-only/comment/docstring lines
        blanked, so pattern checks only fire on executable code."""
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return [(i, l) for i, l in enumerate(text.splitlines(), start=1)]

        blanked = set()
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                blanked.add(tok.start[0])
            elif tok.type == tokenize.STRING:
                # Blank every line the string spans except lines that also
                # contain code (i.e. the string opens/closes mid-statement).
                for ln in range(tok.start[0], tok.end[0] + 1):
                    blanked.add(ln)

        # A line is blanked only when no meaningful code token touches it.
        # Punctuation like a trailing comma after a string literal in a list
        # ("...",) does not make the line executable code.
        punctuation = {",", ")", "]", "}", ":"}
        code_tokens_by_line = set()
        for tok in tokens:
            if tok.type in (tokenize.STRING, tokenize.COMMENT, tokenize.NL,
                            tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                            tokenize.ENDMARKER):
                continue
            if tok.type == tokenize.OP and tok.string in punctuation:
                continue
            for ln in range(tok.start[0], tok.end[0] + 1):
                code_tokens_by_line.add(ln)

        code_lines = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            if lineno in blanked and lineno not in code_tokens_by_line:
                code_lines.append((lineno, ""))
            else:
                code_lines.append((lineno, line))
        return code_lines

    def check_dangerous_functions(self) -> List[SecurityFinding]:
        """Detect dangerous function usage in Python sources."""
        findings: List[SecurityFinding] = []

        for path in self._iter_source_files():
            if path.suffix != ".py":
                continue
            rel_path = str(path.relative_to(self.config.root_dir))
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue

            for lineno, line in self._code_only_lines(text):
                if not line.strip():
                    continue
                for name, pattern, severity in DANGEROUS_FUNCTIONS:
                    if pattern.search(line):
                        findings.append(
                            SecurityFinding(
                                kind=name,
                                severity=severity,
                                message=f"Dangerous function usage: {name}",
                                file_path=rel_path,
                                line_number=lineno,
                            )
                        )

        return findings

    def audit_dependencies(self, timeout: int = 10) -> List[SecurityFinding]:
        """Audit pinned dependencies against the OSV vulnerability database.

        Network failures are non-fatal: the duty simply reports that the
        audit could not be completed.
        """
        findings: List[SecurityFinding] = []

        try:
            import requests
        except ImportError:
            logger.info("requests not installed; dependency audit skipped")
            return findings

        for package, version, ecosystem in self._pinned_dependencies():
            if ecosystem not in _ALLOWED_ECOSYSTEMS:
                continue
            if not re.fullmatch(r"[A-Za-z0-9_.\-]+", package) or not re.fullmatch(
                r"[A-Za-z0-9_.\-+!]+", version
            ):
                continue  # strict validation before any network use

            try:
                response = requests.post(
                    _OSV_API_URL,
                    json={
                        "package": {"name": package, "ecosystem": ecosystem},
                        "version": version,
                    },
                    timeout=timeout,
                )
                if response.status_code != 200:
                    continue
                vulns = response.json().get("vulns", [])
                for vuln in vulns[:3]:
                    findings.append(
                        SecurityFinding(
                            kind="dependency-vulnerability",
                            severity="high",
                            message=(
                                f"{package}=={version} affected by "
                                f"{vuln.get('id', 'unknown')}: "
                                f"{vuln.get('summary', 'no summary')[:120]}"
                            ),
                            file_path="requirements.txt" if ecosystem == "PyPI" else "package.json",
                        )
                    )
            except Exception as exc:  # network is best-effort
                logger.debug("OSV query failed for %s: %s", package, exc)

        return findings

    def run_security_scan(self, include_dependency_audit: bool = False) -> Dict:
        """Run the full security sweep and persist a report."""
        secret_findings = self.scan_for_secrets()
        dangerous_findings = self.check_dangerous_functions()
        dependency_findings = (
            self.audit_dependencies() if include_dependency_audit else []
        )

        all_findings = secret_findings + dangerous_findings + dependency_findings
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_findings": len(all_findings),
            "secrets": len(secret_findings),
            "dangerous_functions": len(dangerous_findings),
            "dependency_vulnerabilities": len(dependency_findings),
            "findings": [f.to_dict() for f in all_findings],
        }

        self.last_report = report
        self.config.ensure_state_dir()
        report_path = self.config.state_dir / "security_report.json"
        report_path.write_text(json.dumps(report, indent=2))
        logger.info("Security report written: %d finding(s)", len(all_findings))
        return report

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _iter_source_files(self):
        for directory in self.config.scan_directories:
            base = self.config.root_dir / directory
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file():
                    continue
                if any(part in self.config.exclude_directories for part in path.parts):
                    continue
                if path.suffix.lower() not in self.config.scan_extensions:
                    continue
                try:
                    if path.stat().st_size > self.config.max_file_size:
                        continue
                except OSError:
                    continue
                yield path

    def _pinned_dependencies(self):
        """Yield (name, version, ecosystem) for exactly-pinned dependencies."""
        req = self.config.root_dir / "requirements.txt"
        if req.exists():
            for line in req.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "==" not in line:
                    continue
                name, _, version = line.partition("==")
                # Strip extras like package[extra]==1.0
                name = name.split("[")[0].strip()
                yield name, version.strip(), "PyPI"

        pkg = self.config.root_dir / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
            for section in ("dependencies", "devDependencies"):
                for name, spec in data.get(section, {}).items():
                    version = str(spec).lstrip("^~>=< ")
                    if version:
                        yield name, version, "npm"
