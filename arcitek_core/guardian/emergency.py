"""
Guardian Emergency Patcher - immediate response to critical conditions.

When the Runtime Monitor raises critical alerts (resource spikes, sustained
threshold breaches), the Emergency Patcher springs into action:

1. Records an incident.
2. Applies safe, immediate mitigations (GC pressure relief, cache/temp
   cleanup, stale PID file removal, disk-space reclamation).
3. Tracks whether the mitigation resolved the condition.

All emergency actions are reversible or side-effect-free by design: the
patcher never deletes user data, only well-known caches and temp files
inside the repository state directories.
"""

import gc
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("guardian.emergency")

# Severity ranking for spike detection.
_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class EmergencyIncident:
    """A recorded emergency and its mitigation outcome."""

    def __init__(self, trigger: Dict, actions: List[str]):
        self.id = f"incident-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        self.trigger = trigger
        self.actions = actions
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.resolved_at: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "actions": self.actions,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


class EmergencyPatcher:
    """Detects emergencies and applies immediate hot-fixes."""

    def __init__(self, config):
        self.config = config
        self.incidents: List[EmergencyIncident] = []
        self._incidents_file = self.config.state_dir / "incidents.json"
        self._load_incidents()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect_emergency(self, alert: Dict) -> bool:
        """Decide whether an alert constitutes an emergency."""
        if not isinstance(alert, dict):
            return False
        severity = alert.get("severity", "info")
        return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK["high"]

    # ------------------------------------------------------------------
    # Response
    # ------------------------------------------------------------------
    def respond(self, alert: Dict) -> Optional[EmergencyIncident]:
        """Apply emergency mitigations for a critical alert."""
        if not self.config.emergency_patching_enabled:
            logger.warning("Emergency patching disabled; alert logged only: %s", alert)
            return None

        if not self.detect_emergency(alert):
            return None

        resource = alert.get("resource", "unknown")
        actions: List[str] = []

        logger.warning("EMERGENCY response triggered by: %s", alert.get("message", alert))

        if resource == "memory":
            actions.extend(self._mitigate_memory())
        elif resource == "disk":
            actions.extend(self._mitigate_disk())
        elif resource == "cpu":
            actions.extend(self._mitigate_cpu())
        else:
            actions.append("alert-recorded")

        incident = EmergencyIncident(trigger=alert, actions=actions)
        self.incidents.append(incident)
        self._save_incidents()

        logger.info(
            "Emergency incident %s handled with actions: %s",
            incident.id,
            ", ".join(actions) if actions else "none",
        )
        return incident

    # ------------------------------------------------------------------
    # Mitigations
    # ------------------------------------------------------------------
    @staticmethod
    def _mitigate_memory() -> List[str]:
        actions = []
        collected = gc.collect()
        actions.append(f"gc-collect:{collected}-objects")
        return actions

    def _mitigate_disk(self) -> List[str]:
        """Reclaim disk space from well-known caches inside the repo."""
        actions = []
        cache_targets = [
            self.config.root_dir / ".pytest_cache",
            self.config.root_dir / ".mypy_cache",
        ]
        # __pycache__ directories anywhere under scanned roots.
        for directory in self.config.scan_directories:
            base = self.config.root_dir / directory
            if base.exists():
                cache_targets.extend(base.rglob("__pycache__"))

        reclaimed = 0
        for target in cache_targets:
            try:
                if target.is_dir():
                    size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
                    shutil.rmtree(target, ignore_errors=True)
                    reclaimed += size
            except OSError:
                continue
        actions.append(f"cache-cleanup:{reclaimed}-bytes")

        # Remove stale PID file if the process is gone.
        pid_file = self.config.root_dir / ".arcitek.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                Path(f"/proc/{pid}").stat()
            except (OSError, ValueError):
                try:
                    pid_file.unlink()
                    actions.append("removed-stale-pid-file")
                except OSError:
                    pass

        return actions

    @staticmethod
    def _mitigate_cpu() -> List[str]:
        # CPU pressure: the bot itself backs off by lengthening its own sleep
        # (handled by the orchestrator reading the incident), plus GC to
        # release interpreter pressure.
        gc.collect()
        return ["cpu-backoff-advised", "gc-collect"]

    # ------------------------------------------------------------------
    # Resolution tracking
    # ------------------------------------------------------------------
    def mark_resolved(self, incident_id: str) -> bool:
        for incident in self.incidents:
            if incident.id == incident_id and incident.resolved_at is None:
                incident.resolved_at = datetime.now(timezone.utc).isoformat()
                self._save_incidents()
                return True
        return False

    def open_incidents(self) -> List[EmergencyIncident]:
        return [i for i in self.incidents if i.resolved_at is None]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_incidents(self):
        if self._incidents_file.exists():
            try:
                data = json.loads(self._incidents_file.read_text())
                for raw in data.get("incidents", []):
                    incident = EmergencyIncident(trigger=raw["trigger"], actions=raw["actions"])
                    incident.id = raw["id"]
                    incident.created_at = raw["created_at"]
                    incident.resolved_at = raw.get("resolved_at")
                    self.incidents.append(incident)
            except (json.JSONDecodeError, OSError, KeyError) as exc:
                logger.warning("Could not load incidents: %s", exc)

    def _save_incidents(self):
        self.config.ensure_state_dir()
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "incidents": [i.to_dict() for i in self.incidents[-200:]],
        }
        self.incidents = self.incidents[-200:]
        self._incidents_file.write_text(json.dumps(payload, indent=2))
