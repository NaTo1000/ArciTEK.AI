"""
Guardian Runtime Monitor - 24/7 system health observation.

Samples CPU, memory, and disk utilisation (via psutil when available,
falling back to /proc and os.statvfs) and raises alerts whenever a
threshold is exceeded for a configurable number of consecutive samples.
"""

import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

logger = logging.getLogger("guardian.monitor")

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:  # pragma: no cover - depends on environment
    psutil = None
    HAS_PSUTIL = False


class SystemSnapshot:
    """A single point-in-time resource measurement."""

    def __init__(self, cpu_percent: float, memory_percent: float, disk_percent: float):
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent
        self.disk_percent = disk_percent
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
            "timestamp": self.timestamp,
        }


class RuntimeMonitor:
    """Monitors runtime resource usage and evaluates thresholds."""

    def __init__(self, config):
        self.config = config
        self.history: Deque[SystemSnapshot] = deque(maxlen=1000)
        self._breach_streaks: Dict[str, int] = {
            "cpu": 0,
            "memory": 0,
            "disk": 0,
        }
        self.alerts: List[Dict] = []

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------
    def collect_metrics(self) -> SystemSnapshot:
        """Collect a fresh snapshot of system metrics."""
        snapshot = SystemSnapshot(
            cpu_percent=self._cpu_percent(),
            memory_percent=self._memory_percent(),
            disk_percent=self._disk_percent(),
        )
        self.history.append(snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Threshold evaluation
    # ------------------------------------------------------------------
    def check_thresholds(self, snapshot: SystemSnapshot = None) -> List[Dict]:
        """Check the latest snapshot against configured thresholds.

        An alert is raised only after ``threshold_samples`` consecutive
        samples above the threshold, preventing flapping.
        """
        snapshot = snapshot or (self.history[-1] if self.history else self.collect_metrics())

        checks = {
            "cpu": (snapshot.cpu_percent, self.config.cpu_threshold),
            "memory": (snapshot.memory_percent, self.config.memory_threshold),
            "disk": (snapshot.disk_percent, self.config.disk_threshold),
        }

        new_alerts = []
        for resource, (value, threshold) in checks.items():
            if value >= threshold:
                self._breach_streaks[resource] += 1
                if self._breach_streaks[resource] == self.config.threshold_samples:
                    alert = {
                        "type": "threshold-breach",
                        "resource": resource,
                        "value": value,
                        "threshold": threshold,
                        "severity": "critical" if value >= threshold + 5 else "high",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": (
                            f"{resource.upper()} at {value:.1f}% "
                            f"(threshold {threshold:.1f}%) for "
                            f"{self.config.threshold_samples} consecutive samples"
                        ),
                    }
                    self.alerts.append(alert)
                    new_alerts.append(alert)
                    logger.warning(alert["message"])
            else:
                self._breach_streaks[resource] = 0

        return new_alerts

    def get_health_report(self) -> Dict:
        """Summarise current health for status reporting."""
        latest = self.history[-1] if self.history else None
        return {
            "psutil_available": HAS_PSUTIL,
            "samples_collected": len(self.history),
            "latest": latest.to_dict() if latest else None,
            "thresholds": {
                "cpu": self.config.cpu_threshold,
                "memory": self.config.memory_threshold,
                "disk": self.config.disk_threshold,
            },
            "active_alerts": self.alerts[-20:],
        }

    # ------------------------------------------------------------------
    # Metric providers
    # ------------------------------------------------------------------
    @staticmethod
    def _cpu_percent() -> float:
        if HAS_PSUTIL:
            return float(psutil.cpu_percent(interval=0.1))
        # Fallback: derive from load average (rough approximation).
        try:
            load1, _, _ = os.getloadavg()
            cpus = os.cpu_count() or 1
            return min(100.0, (load1 / cpus) * 100.0)
        except (OSError, AttributeError):
            return 0.0

    @staticmethod
    def _memory_percent() -> float:
        if HAS_PSUTIL:
            return float(psutil.virtual_memory().percent)
        # Fallback: parse /proc/meminfo on Linux.
        try:
            info = {}
            with open("/proc/meminfo") as fh:
                for line in fh:
                    key, _, rest = line.partition(":")
                    info[key.strip()] = int(rest.strip().split()[0])
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            if total > 0:
                return ((total - available) / total) * 100.0
        except (OSError, ValueError, KeyError):
            pass
        return 0.0

    def _disk_percent(self) -> float:
        if HAS_PSUTIL:
            return float(psutil.disk_usage(str(self.config.root_dir)).percent)
        try:
            stat = os.statvfs(str(self.config.root_dir))
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            if total > 0:
                return ((total - free) / total) * 100.0
        except OSError:
            pass
        return 0.0
