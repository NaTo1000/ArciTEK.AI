"""
Guardian Updater - keeps ArciTEK.AI current 24/7.

Wraps the existing ``scripts/upgrade.py`` version-management system:
- Checks GitHub releases for new platform versions.
- Optionally applies updates automatically (off by default; updates are
  applied with the upgrade system's own backup/rollback support).
- Records update activity in the Guardian state directory.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("guardian.updater")


class UpdateManager:
    """Manages platform update checks and (optional) auto-updates."""

    def __init__(self, config):
        self.config = config
        self.upgrade_script = self.config.root_dir / "scripts" / "upgrade.py"
        self.history_file = self.config.state_dir / "update_history.json"
        self.last_check: Optional[Dict] = None

    # ------------------------------------------------------------------
    # Duties
    # ------------------------------------------------------------------
    def check_for_updates(self, timeout: int = 60) -> Dict:
        """Check for a newer platform release.

        Returns a report dict; never raises on network failure.
        """
        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "current_version": self._current_version(),
            "update_available": False,
            "error": None,
        }

        try:
            import requests

            response = requests.get(
                "https://api.github.com/repos/NaTo1000/ArciTEK.AI/releases/latest",
                timeout=min(timeout, 15),
                headers={"Accept": "application/vnd.github+json"},
            )
            if response.status_code == 200:
                release = response.json()
                latest = str(release.get("tag_name", "")).lstrip("v")
                report["latest_version"] = latest
                report["update_available"] = self._is_newer(latest, report["current_version"])
                report["release_name"] = release.get("name")
                report["published_at"] = release.get("published_at")
            else:
                report["error"] = f"GitHub API returned {response.status_code}"
        except Exception as exc:
            report["error"] = str(exc)
            logger.debug("Update check failed: %s", exc)

        self.last_check = report
        self._record(report, applied=False)
        return report

    def apply_update(self, timeout: int = 300) -> Dict:
        """Apply the latest update via the platform upgrade system.

        The upgrade system creates a full backup before applying changes,
        so every auto-update is revertible with ``upgrade.py rollback``.
        """
        result = {
            "attempted_at": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "message": "",
        }

        if not self.config.auto_update_enabled:
            result["message"] = "auto_update_enabled is False; update not applied"
            return result

        if not self.upgrade_script.exists():
            result["message"] = "upgrade.py not found"
            return result

        try:
            completed = subprocess.run(
                [sys.executable, str(self.upgrade_script), "auto"],
                cwd=str(self.config.root_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result["success"] = completed.returncode == 0
            result["message"] = (
                "Update applied successfully"
                if completed.returncode == 0
                else f"upgrade.py exited with {completed.returncode}: {completed.stderr[-500:]}"
            )
        except subprocess.TimeoutExpired:
            result["message"] = f"update timed out after {timeout}s"
        except OSError as exc:
            result["message"] = f"update failed: {exc}"

        self._record(result, applied=result["success"])
        if result["success"]:
            logger.info("Guardian applied a platform update")
        else:
            logger.warning("Guardian update attempt: %s", result["message"])
        return result

    def get_status(self) -> Dict:
        return {
            "current_version": self._current_version(),
            "last_check": self.last_check,
            "auto_update_enabled": self.config.auto_update_enabled,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _current_version(self) -> str:
        version_file = self.config.root_dir / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "0.0.0"

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        def as_tuple(v: str):
            # Only purely numeric segments count; pre-release/build suffixes
            # (e.g. "1.0.0-rc1") are ignored rather than crashing.
            return tuple(int(part) for part in v.split(".") if part.isdigit())

        return as_tuple(latest) > as_tuple(current)

    def _record(self, entry: Dict, applied: bool):
        self.config.ensure_state_dir()
        history = []
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text()).get("history", [])
            except (json.JSONDecodeError, OSError):
                history = []
        entry = dict(entry)
        entry["applied"] = applied
        history.append(entry)
        self.history_file.write_text(
            json.dumps(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "history": history[-100:],
                },
                indent=2,
            )
        )
