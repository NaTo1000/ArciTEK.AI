# Guardian — The ArciTEK.AI 24/7 Bot

> "Every build is a work of art" — infinite♾2025

**Guardian** is ArciTEK.AI's always-on autonomous agent. Its only job is to keep
the platform healthy, current, and secure — around the clock.

## Duties

| Duty | Subsystem | Default interval | What it does |
|------|-----------|------------------|--------------|
| 🔬 Researcher | `CodeResearcher` | 1 hour | Scans the codebase for bugs, vulnerability patterns, syntax errors, mutable default arguments, TODO/FIXME debt, and unpinned dependencies. Findings are deduplicated and persisted. |
| 🔧 Fixer / Patcher | `AutoFixer` | after each research run | Applies safe, rule-based patches (e.g. bare `except:` → `except Exception:`). Every patch creates a timestamped backup and is fully revertible. |
| 📊 Runtime Monitor | `RuntimeMonitor` | 1 minute | Samples CPU / memory / disk (psutil, with /proc fallbacks) and raises alerts after consecutive threshold breaches — no flapping. |
| 🚨 Emergency Patcher | `EmergencyPatcher` | on critical alerts | Responds immediately to spikes: GC pressure relief, cache/temp cleanup, stale PID removal. Tracks incidents until resolved. |
| 🛡️ Security System | `SecuritySystem` | 1 hour | Detects hardcoded secrets (AWS/GitHub/Slack tokens, private keys, JWTs), dangerous function usage (eval/exec, `shell=True`, unsafe deserialization), and can audit dependencies against the OSV vulnerability database. |
| ⬆️ Updater | `UpdateManager` | 24 hours | Checks GitHub releases for new platform versions; optional auto-update through the existing backup/rollback-capable upgrade system. |

## Quick Start

```bash
# Run one full duty cycle (great for CI smoke tests)
python3 -m arcitek_core.guardian.main --once

# Print a JSON status report
python3 -m arcitek_core.guardian.main --report

# Start the 24/7 daemon
python3 -m arcitek_core.guardian.main --daemon
# or via the startup script:
./startup.sh guardian
```

The daemon handles `SIGINT`/`SIGTERM` gracefully and logs to both the console
and `.guardian/guardian.log`.

## Configuration

Guardian is configured by (in priority order):

1. **Environment variables** — e.g. `GUARDIAN_AUTO_FIX=true`
2. **`config/guardian.json`** — a JSON object of config keys
3. **Built-in defaults**

| Key | Env var | Default | Meaning |
|-----|---------|---------|---------|
| `research_interval` | `GUARDIAN_RESEARCH_INTERVAL` | `3600` | Seconds between codebase research cycles |
| `monitor_interval` | `GUARDIAN_MONITOR_INTERVAL` | `60` | Seconds between runtime samples |
| `security_interval` | `GUARDIAN_SECURITY_INTERVAL` | `3600` | Seconds between security scans |
| `update_interval` | `GUARDIAN_UPDATE_INTERVAL` | `86400` | Seconds between update checks |
| `cpu_threshold` | `GUARDIAN_CPU_THRESHOLD` | `90.0` | CPU % alert threshold |
| `memory_threshold` | `GUARDIAN_MEMORY_THRESHOLD` | `85.0` | Memory % alert threshold |
| `disk_threshold` | `GUARDIAN_DISK_THRESHOLD` | `90.0` | Disk % alert threshold |
| `threshold_samples` | — | `3` | Consecutive breaches before alerting |
| `auto_fix_enabled` | `GUARDIAN_AUTO_FIX` | `false` | Apply safe automatic patches |
| `emergency_patching_enabled` | `GUARDIAN_EMERGENCY_PATCHING` | `true` | Respond to critical alerts |
| `auto_update_enabled` | `GUARDIAN_AUTO_UPDATE` | `false` | Apply platform updates automatically |
| `log_level` | `GUARDIAN_LOG_LEVEL` | `INFO` | Logging verbosity |

## State & Artifacts

Guardian keeps all of its state under `.guardian/` (git-ignored):

```
.guardian/
├── guardian.log          # daemon log
├── events.jsonl          # structured event stream
├── findings.json         # deduplicated research findings
├── patch_history.json    # every patch, with backup path (revertible)
├── incidents.json        # emergency incidents and resolutions
├── security_report.json  # latest security sweep
├── update_history.json   # update checks and applications
└── backups/              # per-file backups taken before patching
```

## Safety Model

- **Auto-fix is opt-in** (`auto_fix_enabled=false` by default) and limited to
  conservative, syntax-verified transformations. Python files are re-parsed
  after every patch; a patch that would break syntax is never applied.
- **Every patch is revertible** via the recorded backup
  (`AutoFixer.revert_patch(patch_id)`).
- **Auto-update is opt-in** and always goes through `scripts/upgrade.py`,
  which creates a full installation backup before changing anything.
- **The daemon never dies from a failing duty** — each duty is isolated and
  its errors are logged and recorded as events.
- **The security system is defensive only** — it detects and reports; it
  contains no offensive capability.

## Programmatic Use

```python
from arcitek_core.guardian import GuardianBot, GuardianConfig

config = GuardianConfig.load()
config.auto_fix_enabled = True

bot = GuardianBot(config)
bot.run_once()          # single full cycle
print(bot.get_status()) # full status report
# bot.start()           # 24/7 daemon mode
```

## Testing

```bash
python3 -m pytest tests/test_guardian.py -v
```
