"""
Guardian Bot - the 24/7 orchestrator.

Runs every Guardian duty on its own schedule, forever:

==================  ============================  ======================
Duty                Subsystem                     Default interval
==================  ============================  ======================
Research            CodeResearcher                1 hour
Fix/Patch           AutoFixer                     after each research run
Runtime monitoring  RuntimeMonitor                1 minute
Emergency patching  EmergencyPatcher              on critical alerts
Security            SecuritySystem                1 hour
Updates             UpdateManager                 24 hours
==================  ============================  ======================

The bot is intentionally dependency-light, handles its own exceptions so a
single failing duty can never kill the daemon, and persists an event log
(JSONL) plus structured state for later inspection.
"""

import json
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from .config import GuardianConfig
from .emergency import EmergencyPatcher
from .fixer import AutoFixer
from .monitor import RuntimeMonitor
from .researcher import CodeResearcher
from .security import SecuritySystem
from .updater import UpdateManager

logger = logging.getLogger("guardian.bot")


class GuardianBot:
    """The 24/7 researcher / fixer / patcher / monitor / emergency
    patcher / security system / updater bot for ArciTEK.AI."""

    def __init__(self, config: Optional[GuardianConfig] = None):
        self.config = config or GuardianConfig.load()
        self.config.ensure_state_dir()
        self._configure_logging()

        self.researcher = CodeResearcher(self.config)
        self.fixer = AutoFixer(self.config)
        self.monitor = RuntimeMonitor(self.config)
        self.emergency = EmergencyPatcher(self.config)
        self.security = SecuritySystem(self.config)
        self.updater = UpdateManager(self.config)

        self._running = False
        self._started_at: Optional[str] = None
        self._last_run: Dict[str, float] = {
            "research": 0.0,
            "security": 0.0,
            "update": 0.0,
        }
        self.cycle_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        """Start the 24/7 duty loop. Blocks until stopped."""
        self._running = True
        self._started_at = datetime.now(timezone.utc).isoformat()

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._log_event("bot-start", {"version": self._platform_version()})
        logger.info("Guardian bot started - 24/7 duty loop active")

        try:
            while self._running:
                self._run_due_duties()
                time.sleep(max(1, min(self.config.monitor_interval, 60)))
        finally:
            self._log_event("bot-stop", {"cycles": self.cycle_count})
            logger.info("Guardian bot stopped after %d cycle(s)", self.cycle_count)

    def stop(self):
        """Request the duty loop to stop."""
        self._running = False

    def run_once(self) -> Dict:
        """Run every duty exactly once (useful for smoke tests and CI)."""
        logger.info("Guardian running a single full cycle")
        results = {
            "research": self._safe_duty("research", self._duty_research),
            "monitor": self._safe_duty("monitor", self._duty_monitor),
            "security": self._safe_duty("security", self._duty_security),
            "update": self._safe_duty("update", self._duty_update_check),
        }
        self._log_event("run-once", {"duties": list(results)})
        return results

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------
    def _run_due_duties(self):
        now = time.monotonic()
        self.cycle_count += 1

        # Runtime monitoring runs every cycle (bounded by monitor_interval).
        self._safe_duty("monitor", self._duty_monitor)

        if now - self._last_run["research"] >= self.config.research_interval:
            self._last_run["research"] = now
            self._safe_duty("research", self._duty_research)

        if now - self._last_run["security"] >= self.config.security_interval:
            self._last_run["security"] = now
            self._safe_duty("security", self._duty_security)

        if now - self._last_run["update"] >= self.config.update_interval:
            self._last_run["update"] = now
            self._safe_duty("update", self._duty_update_check)

    # ------------------------------------------------------------------
    # Duties
    # ------------------------------------------------------------------
    def _duty_research(self) -> Dict:
        findings = self.researcher.scan_codebase()
        fix_results = self.fixer.fix_findings(findings)
        summary = {
            "new_findings": len(findings),
            "by_severity": self._count_by(findings, "severity"),
            "fixes_attempted": len(fix_results),
            "fixes_applied": sum(1 for r in fix_results if r.success),
        }
        self._log_event("research-cycle", summary)
        return summary

    def _duty_monitor(self) -> Dict:
        snapshot = self.monitor.collect_metrics()
        alerts = self.monitor.check_thresholds(snapshot)

        alerting_resources = set()
        for alert in alerts:
            self._log_event("monitor-alert", alert)
            self.emergency.respond(alert)
            alerting_resources.add(alert.get("resource"))

        # Close incidents whose resource has calmed down and is not
        # currently alerting again.
        self._resolve_calm_incidents(snapshot, exclude=alerting_resources)

        return snapshot.to_dict()

    def _duty_security(self) -> Dict:
        report = self.security.run_security_scan(include_dependency_audit=False)
        summary = {
            "total_findings": report["total_findings"],
            "secrets": report["secrets"],
            "dangerous_functions": report["dangerous_functions"],
        }
        self._log_event("security-scan", summary)
        return summary

    def _duty_update_check(self) -> Dict:
        report = self.updater.check_for_updates()
        self._log_event(
            "update-check",
            {
                "current": report.get("current_version"),
                "latest": report.get("latest_version"),
                "update_available": report.get("update_available"),
            },
        )
        if report.get("update_available"):
            self.updater.apply_update()
        return report

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def get_status(self) -> Dict:
        """Full status report for CLI / dashboards."""
        return {
            "running": self._running,
            "started_at": self._started_at,
            "cycles": self.cycle_count,
            "platform_version": self._platform_version(),
            "monitor": self.monitor.get_health_report(),
            "open_incidents": [i.to_dict() for i in self.emergency.open_incidents()],
            "patches_applied": len(
                [p for p in self.fixer.get_patch_history() if not p.get("reverted_at")]
            ),
            "updater": self.updater.get_status(),
            "config": {
                "research_interval": self.config.research_interval,
                "monitor_interval": self.config.monitor_interval,
                "security_interval": self.config.security_interval,
                "update_interval": self.config.update_interval,
                "auto_fix_enabled": self.config.auto_fix_enabled,
                "emergency_patching_enabled": self.config.emergency_patching_enabled,
                "auto_update_enabled": self.config.auto_update_enabled,
            },
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _safe_duty(self, name: str, duty):
        """Run a duty, logging (never propagating) failures."""
        try:
            return duty()
        except Exception as exc:  # the daemon must never die
            logger.exception("Guardian duty '%s' failed: %s", name, exc)
            self._log_event("duty-error", {"duty": name, "error": str(exc)})
            return {"error": str(exc)}

    def _resolve_calm_incidents(self, snapshot, exclude=frozenset()):
        """Close open incidents whose resource is back under threshold."""
        thresholds = {
            "cpu": (snapshot.cpu_percent, self.config.cpu_threshold),
            "memory": (snapshot.memory_percent, self.config.memory_threshold),
            "disk": (snapshot.disk_percent, self.config.disk_threshold),
        }
        for incident in self.emergency.open_incidents():
            resource = incident.trigger.get("resource")
            if resource in exclude:
                continue
            if resource in thresholds:
                value, threshold = thresholds[resource]
                if value < threshold:
                    self.emergency.mark_resolved(incident.id)
                    self._log_event(
                        "incident-resolved", {"incident": incident.id, "resource": resource}
                    )

    def _handle_signal(self, signum, _frame):
        logger.info("Received signal %s; shutting down gracefully", signum)
        self.stop()

    def _log_event(self, event_type: str, data: Dict):
        self.config.ensure_state_dir()
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "data": data,
        }
        try:
            with self.config.events_file.open("a") as fh:
                fh.write(json.dumps(event) + "\n")
        except OSError as exc:
            logger.debug("Could not write event log: %s", exc)

    def _platform_version(self) -> str:
        version_file = self.config.root_dir / "VERSION"
        return version_file.read_text().strip() if version_file.exists() else "unknown"

    @staticmethod
    def _count_by(items, attr) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in items:
            key = getattr(item, attr, "unknown")
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _configure_logging(self):
        level = getattr(logging, str(self.config.log_level).upper(), logging.INFO)
        root = logging.getLogger("guardian")
        root.setLevel(level)

        if not root.handlers:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )

            console = logging.StreamHandler()
            console.setFormatter(formatter)
            root.addHandler(console)

            try:
                self.config.ensure_state_dir()
                file_handler = logging.FileHandler(self.config.log_file)
                file_handler.setFormatter(formatter)
                root.addHandler(file_handler)
            except OSError:
                pass
