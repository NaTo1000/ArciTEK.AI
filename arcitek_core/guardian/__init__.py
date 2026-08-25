"""
ArciTEK.AI Guardian - 24/7 Autonomous Bot

Guardian is the platform's always-on agent whose only job is to keep
ArciTEK.AI healthy, current, and secure:

- **Researcher**       - continuously scans the codebase for bugs, code smells,
                         TODO/FIXME debt, and known vulnerability patterns.
- **Fixer / Patcher**  - safely applies rule-based automatic patches and keeps
                         a revertible history of every fix.
- **Runtime Monitor**  - watches CPU, memory, and disk usage and evaluates
                         thresholds with a sliding observation window.
- **Emergency Patcher**- detects spikes/critical conditions and applies
                         immediate hot-fixes, then tracks their resolution.
- **Security System**  - scans for hardcoded secrets and dangerous function
                         usage, and audits dependencies for CVEs.
- **Updater**          - keeps the platform current via the existing
                         ``scripts/upgrade.py`` system.

Usage:
    python3 -m arcitek_core.guardian.main --daemon        # 24/7 mode
    python3 -m arcitek_core.guardian.main --once          # single cycle
    python3 -m arcitek_core.guardian.main --report        # status report
    ./startup.sh guardian                                 # via startup script
"""

from .config import GuardianConfig
from .bot import GuardianBot

__all__ = ["GuardianConfig", "GuardianBot"]
__version__ = "1.0.0"
