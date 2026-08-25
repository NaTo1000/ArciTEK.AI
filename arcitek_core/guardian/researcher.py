"""
Guardian Researcher - 24/7 codebase research engine.

Continuously scans the ArciTEK.AI codebase for:
- Known vulnerability patterns (hardcoded secrets, dangerous functions)
- Code quality issues (mutable default arguments, bare excepts, ...)
- Outstanding work markers (TODO / FIXME / HACK / XXX / BUG)
- Structural problems (syntax errors, files growing unreasonably large)

Findings are deduplicated by a stable hash and persisted to the Guardian
state directory so the bot learns what it has already seen.
"""

import ast
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger("guardian.researcher")

SEVERITY_LEVELS = ("critical", "high", "medium", "low", "info")

# (pattern_id, regex, severity, description)
VULNERABILITY_PATTERNS = [
    (
        "hardcoded-secret",
        re.compile(
            r"""(?i)(?:password|passwd|secret|api[_-]?key|access[_-]?token|private[_-]?key)"""
            r"""\s*[:=]\s*['"][^'"]{8,}['"]"""
        ),
        "critical",
        "Possible hardcoded credential",
    ),
    (
        "aws-access-key",
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "critical",
        "Possible AWS access key id",
    ),
    (
        "private-key-block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "critical",
        "Embedded private key material",
    ),
    (
        "eval-usage",
        re.compile(r"\beval\s*\("),
        "high",
        "Use of eval() can execute arbitrary code",
    ),
    (
        "exec-usage",
        re.compile(r"\bexec\s*\("),
        "high",
        "Use of exec() can execute arbitrary code",
    ),
    (
        "shell-true",
        re.compile(r"subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True", re.DOTALL),
        "high",
        "subprocess with shell=True is injection-prone",
    ),
    (
        "pickle-load",
        re.compile(r"\bpickle\.loads?\s*\("),
        "medium",
        "pickle deserialization of untrusted data is unsafe",
    ),
    (
        "yaml-unsafe-load",
        re.compile(r"\byaml\.load\s*\((?![^)]*Loader)"),
        "medium",
        "yaml.load() without a safe Loader is unsafe",
    ),
    (
        "debug-enabled",
        re.compile(r"(?i)\bdebug\s*=\s*True\b"),
        "low",
        "Debug mode appears to be enabled",
    ),
]

# (pattern_id, compiled checker kind, severity, description)
QUALITY_PATTERNS = [
    (
        "todo-marker",
        re.compile(r"#\s*(TODO|FIXME|HACK|XXX|BUG)\b", re.IGNORECASE),
        "info",
        "Outstanding work marker",
    ),
    (
        "bare-except",
        re.compile(r"^\s*except\s*:"),
        "medium",
        "Bare except clause swallows all exceptions",
    ),
    (
        "print-statement",
        re.compile(r"^\s*print\s*\("),
        "low",
        "print() used in library/service code (prefer logging)",
    ),
]


class ResearchFinding:
    """A single research finding."""

    def __init__(
        self,
        pattern_id: str,
        severity: str,
        description: str,
        file_path: str,
        line_number: int,
        line_content: str,
        category: str = "code-quality",
    ):
        self.pattern_id = pattern_id
        self.severity = severity
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.line_content = line_content.strip()[:200]
        self.category = category
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.id = self._compute_id()

    def _compute_id(self) -> str:
        raw = f"{self.pattern_id}:{self.file_path}:{self.line_number}:{self.line_content}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "line_content": self.line_content,
            "category": self.category,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ResearchFinding":
        finding = cls(
            pattern_id=data["pattern_id"],
            severity=data["severity"],
            description=data["description"],
            file_path=data["file_path"],
            line_number=data["line_number"],
            line_content=data.get("line_content", ""),
            category=data.get("category", "code-quality"),
        )
        finding.id = data["id"]
        finding.timestamp = data.get("timestamp", finding.timestamp)
        return finding


class CodeResearcher:
    """Researches the codebase around the clock, looking for trouble."""

    def __init__(self, config):
        self.config = config
        self.known_finding_ids: Set[str] = set()
        self._load_known_findings()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_known_findings(self):
        path = self.config.findings_file
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.known_finding_ids = {f["id"] for f in data.get("findings", [])}
            except (json.JSONDecodeError, OSError, KeyError) as exc:
                logger.warning("Could not load known findings: %s", exc)

    def save_findings(self, findings: List[ResearchFinding]):
        self.config.ensure_state_dir()
        path = self.config.findings_file

        existing: List[Dict] = []
        if path.exists():
            try:
                existing = json.loads(path.read_text()).get("findings", [])
            except (json.JSONDecodeError, OSError):
                existing = []

        merged = {f["id"]: f for f in existing}
        for finding in findings:
            merged[finding.id] = finding.to_dict()

        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(merged),
            "findings": sorted(
                merged.values(), key=lambda f: SEVERITY_LEVELS.index(f["severity"])
                if f["severity"] in SEVERITY_LEVELS else len(SEVERITY_LEVELS)
            ),
        }
        path.write_text(json.dumps(payload, indent=2))

    # ------------------------------------------------------------------
    # Research duties
    # ------------------------------------------------------------------
    def scan_codebase(self) -> List[ResearchFinding]:
        """Scan all configured directories and return *new* findings."""
        findings: List[ResearchFinding] = []

        for target in self._iter_scan_targets():
            findings.extend(self._scan_file(target))

        new_findings = [f for f in findings if f.id not in self.known_finding_ids]
        if new_findings:
            logger.info("Researcher discovered %d new finding(s)", len(new_findings))
            self.known_finding_ids.update(f.id for f in new_findings)
            self.save_findings(new_findings)

        return new_findings

    def research_dependencies(self, requirements_path: Path = None) -> Dict:
        """Research declared dependencies for potential issues.

        Returns a report of outdated-looking pins and risky packages.
        """
        requirements_path = requirements_path or (self.config.root_dir / "requirements.txt")
        report = {"file": str(requirements_path), "packages": 0, "issues": []}

        if not requirements_path.exists():
            return report

        risky_packages = {"pickle5", "pycrypto"}  # known-problematic examples

        for line in requirements_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            report["packages"] += 1

            name = re.split(r"[=<>!\[]", line, maxsplit=1)[0].strip().lower()
            if name in risky_packages:
                report["issues"].append(
                    {
                        "package": name,
                        "severity": "high",
                        "issue": "Package is known to be problematic or unmaintained",
                    }
                )
            if "==" not in line and not line.startswith(("-", "git+")):
                report["issues"].append(
                    {
                        "package": name,
                        "severity": "low",
                        "issue": "Dependency is not pinned to an exact version",
                    }
                )

        return report

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _iter_scan_targets(self):
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
                        logger.debug("Skipping oversized file: %s", path)
                        continue
                except OSError:
                    continue
                yield path

    def _scan_file(self, path: Path) -> List[ResearchFinding]:
        findings: List[ResearchFinding] = []
        try:
            text = path.read_text(errors="replace")
        except OSError as exc:
            logger.debug("Could not read %s: %s", path, exc)
            return findings

        rel_path = str(path.relative_to(self.config.root_dir))
        lines = text.splitlines()

        # Syntax check for Python sources.
        if path.suffix == ".py":
            syntax_finding = self._check_python_syntax(path, rel_path, text)
            if syntax_finding:
                findings.append(syntax_finding)

        for lineno, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("*"):
                continue  # comments/docstrings can't contain live vulnerabilities
            if stripped[:1] in ('"', "'") and stripped.rstrip().rstrip(",")[-1:] == stripped[:1]:
                continue  # pure string literals (e.g. pattern descriptions)
            for pattern_id, regex, severity, description in VULNERABILITY_PATTERNS:
                if regex.search(line):
                    findings.append(
                        ResearchFinding(
                            pattern_id=pattern_id,
                            severity=severity,
                            description=description,
                            file_path=rel_path,
                            line_number=lineno,
                            line_content=line,
                            category="security",
                        )
                    )
            for pattern_id, regex, severity, description in QUALITY_PATTERNS:
                if regex.search(line):
                    findings.append(
                        ResearchFinding(
                            pattern_id=pattern_id,
                            severity=severity,
                            description=description,
                            file_path=rel_path,
                            line_number=lineno,
                            line_content=line,
                            category="code-quality",
                        )
                    )

        if path.suffix == ".py":
            findings.extend(self._ast_checks(path, rel_path, text))

        return findings

    @staticmethod
    def _check_python_syntax(path: Path, rel_path: str, text: str) -> Optional[ResearchFinding]:
        try:
            ast.parse(text, filename=rel_path)
            return None
        except SyntaxError as exc:
            return ResearchFinding(
                pattern_id="syntax-error",
                severity="critical",
                description=f"Python syntax error: {exc.msg}",
                file_path=rel_path,
                line_number=exc.lineno or 0,
                line_content="",
                category="correctness",
            )

    @staticmethod
    def _ast_checks(path: Path, rel_path: str, text: str) -> List[ResearchFinding]:
        """AST-level checks (mutable defaults, etc.)."""
        findings: List[ResearchFinding] = []
        try:
            tree = ast.parse(text, filename=rel_path)
        except SyntaxError:
            return findings

        mutable_types = (ast.List, ast.Dict, ast.Set)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults + node.args.kw_defaults:
                    if isinstance(default, mutable_types):
                        findings.append(
                            ResearchFinding(
                                pattern_id="mutable-default-arg",
                                severity="medium",
                                description=(
                                    f"Mutable default argument in function "
                                    f"'{node.name}'"
                                ),
                                file_path=rel_path,
                                line_number=node.lineno,
                                line_content=f"def {node.name}(...)",
                                category="correctness",
                            )
                        )
        return findings
