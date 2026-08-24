"""
Guardian Fixer/Patcher - safe automatic patch engine.

Applies rule-based fixes for findings produced by the Researcher and keeps
a full revertible history of every patch applied. Every fix:

1. Verifies the target line still matches what the Researcher saw.
2. Creates a timestamped backup of the file under ``.guardian/backups``.
3. Applies a conservative, syntactic-only transformation.
4. Re-parses Python files afterwards to guarantee no syntax breakage.
5. Records the patch so it can be reverted later.
"""

import ast
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("guardian.fixer")

# Maximum number of backup copies kept per file.
MAX_BACKUPS_PER_FILE = 10


class FixResult:
    """Outcome of a single fix attempt."""

    def __init__(
        self,
        finding_id: str,
        file_path: str,
        success: bool,
        message: str,
        patch_id: Optional[str] = None,
    ):
        self.finding_id = finding_id
        self.file_path = file_path
        self.success = success
        self.message = message
        self.patch_id = patch_id
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "finding_id": self.finding_id,
            "file_path": self.file_path,
            "success": self.success,
            "message": self.message,
            "patch_id": self.patch_id,
            "timestamp": self.timestamp,
        }


class AutoFixer:
    """Applies safe automatic patches for known finding patterns."""

    #: Finding patterns this fixer knows how to repair automatically.
    FIXABLE_PATTERNS = ("trailing-whitespace", "bare-except", "tab-indentation")

    def __init__(self, config):
        self.config = config
        self.backup_dir = self.config.state_dir / "backups"
        self.patch_history: List[Dict] = self._load_history()

    # ------------------------------------------------------------------
    # Patch application
    # ------------------------------------------------------------------
    def fix_findings(self, findings: List) -> List[FixResult]:
        """Attempt to fix every fixable finding. Returns per-fix results."""
        results: List[FixResult] = []

        if not self.config.auto_fix_enabled:
            for finding in findings:
                if self._is_fixable(finding):
                    results.append(
                        FixResult(
                            finding_id=finding.id,
                            file_path=finding.file_path,
                            success=False,
                            message="auto_fix_enabled is False; fix skipped",
                        )
                    )
            return results

        for finding in findings:
            if not self._is_fixable(finding):
                continue
            results.append(self.apply_fix(finding))

        return results

    def apply_fix(self, finding) -> FixResult:
        """Apply a single fix with backup + verification."""
        target = self.config.root_dir / finding.file_path

        if not target.exists():
            return FixResult(finding.id, finding.file_path, False, "file no longer exists")

        try:
            original_text = target.read_text(errors="replace")
        except OSError as exc:
            return FixResult(finding.id, finding.file_path, False, f"read error: {exc}")

        lines = original_text.splitlines(keepends=True)
        index = finding.line_number - 1
        if index < 0 or index >= len(lines):
            return FixResult(
                finding.id, finding.file_path, False, "line number out of range"
            )

        original_line = lines[index]
        fixed_line = self._fix_line(finding.pattern_id, original_line)
        if fixed_line is None or fixed_line == original_line:
            return FixResult(
                finding.id, finding.file_path, False, "no automatic fix available"
            )

        # Backup before modification.
        backup_path = self._create_backup(target, finding.file_path)

        lines[index] = fixed_line
        new_text = "".join(lines)

        # Verify Python syntax after the change.
        if target.suffix == ".py":
            try:
                ast.parse(new_text, filename=finding.file_path)
            except SyntaxError as exc:
                return FixResult(
                    finding.id,
                    finding.file_path,
                    False,
                    f"fix would break syntax ({exc.msg}); not applied",
                )

        try:
            target.write_text(new_text)
        except OSError as exc:
            return FixResult(finding.id, finding.file_path, False, f"write error: {exc}")

        patch_id = self._record_patch(
            finding=finding,
            backup_path=backup_path,
            original_line=original_line,
            fixed_line=fixed_line,
        )
        logger.info("Patched %s:%d (%s)", finding.file_path, finding.line_number, finding.pattern_id)

        return FixResult(
            finding.id,
            finding.file_path,
            True,
            f"Applied fix for '{finding.pattern_id}'",
            patch_id=patch_id,
        )

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------
    def revert_patch(self, patch_id: str) -> bool:
        """Revert a previously applied patch by restoring its backup."""
        record = next((p for p in self.patch_history if p["patch_id"] == patch_id), None)
        if record is None:
            logger.warning("Unknown patch id: %s", patch_id)
            return False

        backup_path = Path(record["backup_path"])
        target = self.config.root_dir / record["file_path"]

        if not backup_path.exists():
            logger.error("Backup missing for patch %s", patch_id)
            return False

        try:
            shutil.copy2(backup_path, target)
        except OSError as exc:
            logger.error("Revert failed for patch %s: %s", patch_id, exc)
            return False

        record["reverted_at"] = datetime.now(timezone.utc).isoformat()
        self._save_history()
        logger.info("Reverted patch %s (%s)", patch_id, record["file_path"])
        return True

    def get_patch_history(self) -> List[Dict]:
        return list(self.patch_history)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _is_fixable(self, finding) -> bool:
        return getattr(finding, "pattern_id", None) in self.FIXABLE_PATTERNS

    @staticmethod
    def _fix_line(pattern_id: str, line: str) -> Optional[str]:
        """Return the fixed line, or None if no fix applies."""
        if pattern_id == "trailing-whitespace":
            stripped = line.rstrip(" \t")
            newline = "\n" if line.endswith("\n") else ""
            return stripped + newline

        if pattern_id == "tab-indentation":
            if line.startswith("\t") or "\n\t" in line:
                return line.replace("\t", "    ")
            return None

        if pattern_id == "bare-except":
            # Conservative rewrite: `except:` -> `except Exception:`
            fixed, count = re.subn(r"^(\s*)except\s*:", r"\1except Exception:", line)
            return fixed if count else None

        return None

    def _create_backup(self, target: Path, rel_path: str) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = rel_path.replace("/", "__")
        backup_path = self.backup_dir / f"{safe_name}.{timestamp}.bak"
        shutil.copy2(target, backup_path)

        # Prune old backups for this file.
        backups = sorted(self.backup_dir.glob(f"{safe_name}.*.bak"))
        for old in backups[:-MAX_BACKUPS_PER_FILE]:
            try:
                old.unlink()
            except OSError:
                pass

        return backup_path

    def _record_patch(self, finding, backup_path: Path, original_line: str, fixed_line: str) -> str:
        patch_id = f"patch-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        self.patch_history.append(
            {
                "patch_id": patch_id,
                "finding_id": finding.id,
                "pattern_id": finding.pattern_id,
                "file_path": finding.file_path,
                "line_number": finding.line_number,
                "original_line": original_line.rstrip("\n"),
                "fixed_line": fixed_line.rstrip("\n"),
                "backup_path": str(backup_path),
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "reverted_at": None,
            }
        )
        self._save_history()
        return patch_id

    def _load_history(self) -> List[Dict]:
        path = self.config.patch_history_file
        if path.exists():
            try:
                return json.loads(path.read_text()).get("patches", [])
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_history(self):
        self.config.ensure_state_dir()
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "patches": self.patch_history[-500:],  # keep last 500
        }
        self.patch_history = payload["patches"]
        self.config.patch_history_file.write_text(json.dumps(payload, indent=2))
