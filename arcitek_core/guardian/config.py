"""
Guardian configuration management.

Configuration is resolved in this order (later sources win):
    1. Defaults defined on :class:`GuardianConfig`
    2. ``config/guardian.json`` (if present)
    3. Environment variables prefixed with ``GUARDIAN_``
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("guardian.config")

DEFAULT_SCAN_DIRS = ["arcitek_core", "scripts", "quantum", "ai_models", "tools"]
DEFAULT_EXCLUDE_DIRS = [
    ".git",
    ".backups",
    ".versions",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".guardian",
    "docs",
]
DEFAULT_SCAN_EXTENSIONS = [".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".json", ".yml", ".yaml"]


@dataclass
class GuardianConfig:
    """Configuration for the Guardian 24/7 bot."""

    root_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    state_dir_name: str = ".guardian"

    # Intervals (seconds) between duty cycles in daemon mode.
    research_interval: int = 3600
    monitor_interval: int = 60
    security_interval: int = 3600
    update_interval: int = 86400

    # Runtime monitor thresholds (percent).
    cpu_threshold: float = 90.0
    memory_threshold: float = 85.0
    disk_threshold: float = 90.0
    # Consecutive samples above threshold required before an alert is raised.
    threshold_samples: int = 3

    # Codebase scanning behaviour.
    scan_directories: List[str] = field(default_factory=lambda: list(DEFAULT_SCAN_DIRS))
    exclude_directories: List[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_DIRS))
    scan_extensions: List[str] = field(default_factory=lambda: list(DEFAULT_SCAN_EXTENSIONS))
    max_file_size: int = 1024 * 1024  # bytes

    # Safety switches.
    auto_fix_enabled: bool = False
    emergency_patching_enabled: bool = True
    auto_update_enabled: bool = False

    # Logging.
    log_level: str = "INFO"

    def __post_init__(self):
        self.root_dir = Path(self.root_dir)

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    @property
    def state_dir(self) -> Path:
        return self.root_dir / self.state_dir_name

    @property
    def log_file(self) -> Path:
        return self.state_dir / "guardian.log"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def findings_file(self) -> Path:
        return self.state_dir / "findings.json"

    @property
    def patch_history_file(self) -> Path:
        return self.state_dir / "patch_history.json"

    @property
    def events_file(self) -> Path:
        return self.state_dir / "events.jsonl"

    def ensure_state_dir(self) -> Path:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return self.state_dir

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, root_dir: Path = None) -> "GuardianConfig":
        """Build a config from defaults, ``config/guardian.json`` and env vars."""
        config = cls(root_dir=Path(root_dir)) if root_dir else cls()

        json_path = config.root_dir / "config" / "guardian.json"
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                config._apply_dict(data)
                logger.info("Loaded Guardian config from %s", json_path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load %s: %s", json_path, exc)

        config._apply_env()
        return config

    def _apply_dict(self, data: Dict[str, Any]):
        for key, value in data.items():
            if hasattr(self, key) and not key.startswith("_"):
                if key in ("scan_directories", "exclude_directories", "scan_extensions"):
                    value = list(value)
                setattr(self, key, value)

    def _apply_env(self):
        mapping = {
            "GUARDIAN_RESEARCH_INTERVAL": ("research_interval", int),
            "GUARDIAN_MONITOR_INTERVAL": ("monitor_interval", int),
            "GUARDIAN_SECURITY_INTERVAL": ("security_interval", int),
            "GUARDIAN_UPDATE_INTERVAL": ("update_interval", int),
            "GUARDIAN_CPU_THRESHOLD": ("cpu_threshold", float),
            "GUARDIAN_MEMORY_THRESHOLD": ("memory_threshold", float),
            "GUARDIAN_DISK_THRESHOLD": ("disk_threshold", float),
            "GUARDIAN_AUTO_FIX": ("auto_fix_enabled", _to_bool),
            "GUARDIAN_EMERGENCY_PATCHING": ("emergency_patching_enabled", _to_bool),
            "GUARDIAN_AUTO_UPDATE": ("auto_update_enabled", _to_bool),
            "GUARDIAN_LOG_LEVEL": ("log_level", str),
        }
        for env_var, (attr, caster) in mapping.items():
            raw = os.environ.get(env_var)
            if raw is not None:
                try:
                    setattr(self, attr, caster(raw))
                except (ValueError, TypeError):
                    logger.warning("Invalid value for %s: %r", env_var, raw)


def _to_bool(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")
