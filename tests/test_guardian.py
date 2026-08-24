"""
Tests for the ArciTEK.AI Guardian 24/7 bot and its subsystems.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arcitek_core.guardian.bot import GuardianBot
from arcitek_core.guardian.config import GuardianConfig
from arcitek_core.guardian.emergency import EmergencyPatcher
from arcitek_core.guardian.fixer import AutoFixer
from arcitek_core.guardian.monitor import RuntimeMonitor, SystemSnapshot
from arcitek_core.guardian.researcher import CodeResearcher, ResearchFinding
from arcitek_core.guardian.security import SecuritySystem
from arcitek_core.guardian.updater import UpdateManager


@pytest.fixture()
def workspace(tmp_path):
    """A minimal fake ArciTEK.AI tree for the Guardian to watch."""
    (tmp_path / "arcitek_core").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "VERSION").write_text("1.0.0")
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\nflask\n")

    clean = tmp_path / "arcitek_core" / "clean.py"
    clean.write_text('"""Clean module."""\n\n\ndef add(a, b):\n    return a + b\n')

    buggy = tmp_path / "scripts" / "buggy.py"
    buggy.write_text(
        'import subprocess\n'
        '\n'
        'password = "supersecretvalue123"\n'
        '\n'
        'def run(cmd):\n'
        '    subprocess.call(cmd, shell=True)\n'
        '\n'
        'def broken(items=[]):\n'
        '    return items\n'
        '\n'
        'try:\n'
        '    run("ls")\n'
        'except:\n'
        '    pass  # TODO: handle errors\n'
    )
    return tmp_path


@pytest.fixture()
def config(workspace):
    cfg = GuardianConfig(root_dir=workspace)
    cfg.scan_directories = ["arcitek_core", "scripts"]
    cfg.threshold_samples = 2
    cfg.ensure_state_dir()
    return cfg


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
class TestGuardianConfig:
    def test_defaults(self, config):
        assert config.research_interval == 3600
        assert config.monitor_interval == 60
        assert config.update_interval == 86400
        assert config.auto_fix_enabled is False
        assert config.emergency_patching_enabled is True

    def test_state_paths(self, config):
        assert config.state_dir.name == ".guardian"
        assert config.log_file.parent == config.state_dir
        assert config.state_dir.exists()

    def test_env_overrides(self, workspace, monkeypatch):
        monkeypatch.setenv("GUARDIAN_CPU_THRESHOLD", "55.5")
        monkeypatch.setenv("GUARDIAN_AUTO_FIX", "true")
        monkeypatch.setenv("GUARDIAN_MONITOR_INTERVAL", "5")
        cfg = GuardianConfig.load(root_dir=workspace)
        assert cfg.cpu_threshold == 55.5
        assert cfg.auto_fix_enabled is True
        assert cfg.monitor_interval == 5

    def test_json_config_file(self, workspace):
        (workspace / "config").mkdir()
        (workspace / "config" / "guardian.json").write_text(
            json.dumps({"research_interval": 12, "cpu_threshold": 42.0})
        )
        cfg = GuardianConfig.load(root_dir=workspace)
        assert cfg.research_interval == 12
        assert cfg.cpu_threshold == 42.0


# ----------------------------------------------------------------------
# Researcher
# ----------------------------------------------------------------------
class TestCodeResearcher:
    def test_scan_finds_issues(self, config):
        researcher = CodeResearcher(config)
        findings = researcher.scan_codebase()

        pattern_ids = {f.pattern_id for f in findings}
        assert "hardcoded-secret" in pattern_ids
        assert "shell-true" in pattern_ids
        assert "mutable-default-arg" in pattern_ids
        assert "bare-except" in pattern_ids
        assert "todo-marker" in pattern_ids

    def test_findings_have_stable_ids(self, config):
        researcher = CodeResearcher(config)
        findings = researcher.scan_codebase()
        ids = [f.id for f in findings]
        assert len(ids) == len(set(ids))
        assert all(len(i) == 16 for i in ids)

    def test_deduplication_on_rescan(self, config):
        researcher = CodeResearcher(config)
        first = researcher.scan_codebase()
        second = researcher.scan_codebase()
        assert len(first) > 0
        assert second == []  # already known

    def test_findings_persisted(self, config):
        researcher = CodeResearcher(config)
        researcher.scan_codebase()
        data = json.loads(config.findings_file.read_text())
        assert data["total"] > 0

    def test_syntax_error_detection(self, config, workspace):
        bad = workspace / "scripts" / "bad.py"
        bad.write_text("def broken(:\n")
        researcher = CodeResearcher(config)
        findings = researcher.scan_codebase()
        assert any(f.pattern_id == "syntax-error" for f in findings)

    def test_dependency_research(self, config):
        researcher = CodeResearcher(config)
        report = researcher.research_dependencies()
        assert report["packages"] == 2
        # "flask" is not pinned -> low severity issue reported
        assert any(i["package"] == "flask" for i in report["issues"])


# ----------------------------------------------------------------------
# Fixer / Patcher
# ----------------------------------------------------------------------
class TestAutoFixer:
    def _finding(self, file_path, line_number, pattern_id):
        return ResearchFinding(
            pattern_id=pattern_id,
            severity="medium",
            description="test finding",
            file_path=file_path,
            line_number=line_number,
            line_content="",
        )

    def test_fix_skipped_when_disabled(self, config):
        fixer = AutoFixer(config)
        finding = self._finding("scripts/buggy.py", 12, "bare-except")
        results = fixer.fix_findings([finding])
        assert results[0].success is False
        assert "auto_fix_enabled" in results[0].message

    def test_bare_except_fixed_when_enabled(self, config, workspace):
        config.auto_fix_enabled = True
        fixer = AutoFixer(config)
        target = workspace / "scripts" / "buggy.py"
        lines = target.read_text().splitlines()
        lineno = next(i for i, l in enumerate(lines, 1) if l.strip() == "except:")

        finding = self._finding("scripts/buggy.py", lineno, "bare-except")
        result = fixer.apply_fix(finding)

        assert result.success is True
        assert "except Exception:" in target.read_text()

    def test_backup_created_and_revertible(self, config, workspace):
        config.auto_fix_enabled = True
        fixer = AutoFixer(config)
        target = workspace / "scripts" / "buggy.py"
        original = target.read_text()
        lines = original.splitlines()
        lineno = next(i for i, l in enumerate(lines, 1) if l.strip() == "except:")

        result = fixer.apply_fix(self._finding("scripts/buggy.py", lineno, "bare-except"))
        assert result.success
        assert result.patch_id

        assert fixer.revert_patch(result.patch_id) is True
        assert target.read_text() == original

    def test_unfixable_pattern_ignored(self, config):
        config.auto_fix_enabled = True
        fixer = AutoFixer(config)
        finding = self._finding("scripts/buggy.py", 3, "hardcoded-secret")
        assert fixer.fix_findings([finding]) == []

    def test_patch_record_keeps_original_line(self, config, workspace):
        """Regression: patch history must store the pre-fix line."""
        config.auto_fix_enabled = True
        fixer = AutoFixer(config)
        target = workspace / "scripts" / "buggy.py"
        lines = target.read_text().splitlines()
        lineno = next(i for i, l in enumerate(lines, 1) if l.strip() == "except:")

        result = fixer.apply_fix(self._finding("scripts/buggy.py", lineno, "bare-except"))
        assert result.success

        record = next(p for p in fixer.get_patch_history() if p["patch_id"] == result.patch_id)
        assert record["original_line"].strip() == "except:"
        assert record["fixed_line"].strip() == "except Exception:"
        assert record["original_line"] != record["fixed_line"]


# ----------------------------------------------------------------------
# Runtime Monitor
# ----------------------------------------------------------------------
class TestRuntimeMonitor:
    def test_collect_metrics(self, config):
        monitor = RuntimeMonitor(config)
        snapshot = monitor.collect_metrics()
        assert 0.0 <= snapshot.cpu_percent <= 100.0
        assert 0.0 <= snapshot.memory_percent <= 100.0
        assert 0.0 <= snapshot.disk_percent <= 100.0

    def test_threshold_breach_after_consecutive_samples(self, config):
        monitor = RuntimeMonitor(config)
        hot = SystemSnapshot(cpu_percent=99.0, memory_percent=10.0, disk_percent=10.0)

        assert monitor.check_thresholds(hot) == []  # 1st breach: streak < samples
        alerts = monitor.check_thresholds(hot)      # 2nd breach: alert
        assert len(alerts) == 1
        assert alerts[0]["resource"] == "cpu"
        assert alerts[0]["severity"] == "critical"

    def test_streak_resets_below_threshold(self, config):
        monitor = RuntimeMonitor(config)
        hot = SystemSnapshot(cpu_percent=99.0, memory_percent=10.0, disk_percent=10.0)
        cool = SystemSnapshot(cpu_percent=10.0, memory_percent=10.0, disk_percent=10.0)

        monitor.check_thresholds(hot)
        monitor.check_thresholds(cool)  # resets streak
        assert monitor.check_thresholds(hot) == []

    def test_health_report(self, config):
        monitor = RuntimeMonitor(config)
        monitor.collect_metrics()
        report = monitor.get_health_report()
        assert report["samples_collected"] == 1
        assert report["latest"] is not None
        assert "thresholds" in report


# ----------------------------------------------------------------------
# Emergency Patcher
# ----------------------------------------------------------------------
class TestEmergencyPatcher:
    def test_detects_critical_alerts(self, config):
        patcher = EmergencyPatcher(config)
        assert patcher.detect_emergency({"severity": "critical"}) is True
        assert patcher.detect_emergency({"severity": "high"}) is True
        assert patcher.detect_emergency({"severity": "low"}) is False
        assert patcher.detect_emergency({"severity": "info"}) is False

    def test_respond_creates_incident(self, config):
        patcher = EmergencyPatcher(config)
        alert = {
            "severity": "critical",
            "resource": "memory",
            "message": "MEMORY at 99%",
        }
        incident = patcher.respond(alert)
        assert incident is not None
        assert any(a.startswith("gc-collect") for a in incident.actions)
        assert len(patcher.open_incidents()) == 1

    def test_disabled_patching_records_nothing(self, config):
        config.emergency_patching_enabled = False
        patcher = EmergencyPatcher(config)
        assert patcher.respond({"severity": "critical", "resource": "cpu"}) is None

    def test_disk_mitigation_cleans_caches(self, config, workspace):
        cache = workspace / "arcitek_core" / "__pycache__"
        cache.mkdir()
        (cache / "junk.pyc").write_bytes(b"x" * 100)

        patcher = EmergencyPatcher(config)
        incident = patcher.respond({"severity": "critical", "resource": "disk"})
        assert any(a.startswith("cache-cleanup") for a in incident.actions)
        assert not cache.exists()

    def test_mark_resolved(self, config):
        patcher = EmergencyPatcher(config)
        incident = patcher.respond({"severity": "critical", "resource": "cpu"})
        assert patcher.mark_resolved(incident.id) is True
        assert patcher.open_incidents() == []

    def test_incidents_persisted(self, config):
        patcher = EmergencyPatcher(config)
        patcher.respond({"severity": "critical", "resource": "cpu"})
        reloaded = EmergencyPatcher(config)
        assert len(reloaded.incidents) == 1


# ----------------------------------------------------------------------
# Security System
# ----------------------------------------------------------------------
class TestSecuritySystem:
    def test_secret_detection(self, config):
        security = SecuritySystem(config)
        findings = security.scan_for_secrets()
        assert any(f.kind == "generic-secret" for f in findings)
        assert all(f.severity == "critical" for f in findings)

    def test_placeholders_ignored(self, config, workspace):
        example = workspace / "scripts" / "example.py"
        example.write_text('api_key = "your-api-key-here"  # example placeholder\n')
        security = SecuritySystem(config)
        findings = security.scan_for_secrets()
        assert not any(f.file_path == "scripts/example.py" for f in findings)

    def test_dangerous_function_detection(self, config):
        security = SecuritySystem(config)
        findings = security.check_dangerous_functions()
        kinds = {f.kind for f in findings}
        assert "shell-true" in kinds

    def test_full_scan_writes_report(self, config):
        security = SecuritySystem(config)
        report = security.run_security_scan()
        assert report["total_findings"] > 0
        report_file = config.state_dir / "security_report.json"
        assert report_file.exists()
        saved = json.loads(report_file.read_text())
        assert saved["total_findings"] == report["total_findings"]


# ----------------------------------------------------------------------
# Updater
# ----------------------------------------------------------------------
class TestUpdateManager:
    def test_current_version(self, config):
        updater = UpdateManager(config)
        assert updater._current_version() == "1.0.0"

    def test_version_comparison(self):
        assert UpdateManager._is_newer("1.1.0", "1.0.0") is True
        assert UpdateManager._is_newer("2.0.0", "1.9.9") is True
        assert UpdateManager._is_newer("1.0.0", "1.0.0") is False
        assert UpdateManager._is_newer("0.9.9", "1.0.0") is False

    def test_version_comparison_with_prerelease(self):
        """Regression: pre-release suffixes must not crash comparison."""
        assert UpdateManager._is_newer("1.1.0", "1.0.0-rc1") is True
        assert UpdateManager._is_newer("1.0.0-rc1", "1.0.0") is False

    def test_check_handles_network_failure(self, config):
        updater = UpdateManager(config)
        with patch.dict(sys.modules, {"requests": None}):
            report = updater.check_for_updates()
        assert report["update_available"] is False
        assert report["error"] is not None

    def test_check_with_mocked_release(self, config):
        updater = UpdateManager(config)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v2.0.0",
            "name": "v2",
            "published_at": "2026-01-01",
        }
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            report = updater.check_for_updates()

        assert report["update_available"] is True
        assert report["latest_version"] == "2.0.0"

    def test_apply_update_requires_opt_in(self, config):
        updater = UpdateManager(config)
        result = updater.apply_update()
        assert result["success"] is False
        assert "auto_update_enabled" in result["message"]


# ----------------------------------------------------------------------
# Guardian Bot (orchestrator)
# ----------------------------------------------------------------------
class TestGuardianBot:
    def test_run_once(self, config):
        bot = GuardianBot(config)
        results = bot.run_once()

        assert "research" in results
        assert "monitor" in results
        assert "security" in results
        assert "update" in results
        assert results["research"]["new_findings"] > 0

    def test_status_report(self, config):
        bot = GuardianBot(config)
        bot.run_once()
        status = bot.get_status()

        assert status["platform_version"] == "1.0.0"
        assert status["monitor"]["samples_collected"] >= 1
        assert status["config"]["emergency_patching_enabled"] is True

    def test_event_log_written(self, config):
        bot = GuardianBot(config)
        bot.run_once()
        events = config.events_file.read_text().strip().splitlines()
        assert len(events) > 0
        parsed = [json.loads(e) for e in events]
        assert any(e["type"] == "run-once" for e in parsed)

    def test_duty_failure_does_not_crash(self, config):
        bot = GuardianBot(config)
        bot.researcher.scan_codebase = MagicMock(side_effect=RuntimeError("boom"))
        results = bot.run_once()
        assert results["research"]["error"] == "boom"

    def test_stop(self, config):
        bot = GuardianBot(config)
        bot.stop()
        assert bot._running is False

    def test_alerting_incident_not_prematurely_resolved(self, config):
        """Regression: an incident must stay open while its resource alerts."""
        bot = GuardianBot(config)
        hot = SystemSnapshot(cpu_percent=99.0, memory_percent=10.0, disk_percent=10.0)

        # Trigger a CPU alert (threshold_samples = 2 in fixture config).
        bot.monitor.check_thresholds(hot)
        bot.monitor.check_thresholds(hot)
        bot._duty_monitor = lambda: None  # not needed; call pieces directly

        alert = {"severity": "critical", "resource": "cpu", "message": "CPU hot"}
        incident = bot.emergency.respond(alert)
        assert incident is not None

        # CPU still above threshold but no new alert: excluded set protects it.
        bot._resolve_calm_incidents(hot, exclude={"cpu"})
        assert bot.emergency.open_incidents() != []

        # CPU calmed down: incident resolves.
        cool = SystemSnapshot(cpu_percent=10.0, memory_percent=10.0, disk_percent=10.0)
        bot._resolve_calm_incidents(cool)
        assert bot.emergency.open_incidents() == []
