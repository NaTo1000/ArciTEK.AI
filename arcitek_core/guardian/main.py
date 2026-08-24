#!/usr/bin/env python3
"""
Guardian CLI - command line interface for the ArciTEK.AI Guardian bot.

Examples:
    python3 -m arcitek_core.guardian.main --daemon    # run 24/7
    python3 -m arcitek_core.guardian.main --once      # single full cycle
    python3 -m arcitek_core.guardian.main --report    # print status report
"""

import argparse
import json
import sys

from .bot import GuardianBot
from .config import GuardianConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guardian",
        description=(
            "ArciTEK.AI Guardian - 24/7 researcher, fixer/patcher, runtime "
            "monitor, emergency patcher, security system, and updater."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--daemon",
        action="store_true",
        help="run the Guardian duty loop forever (24/7 mode)",
    )
    mode.add_argument(
        "--once",
        action="store_true",
        help="run every duty exactly once and exit",
    )
    mode.add_argument(
        "--report",
        action="store_true",
        help="print a JSON status report and exit",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="repository root directory (defaults to auto-detection)",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    config = GuardianConfig.load(root_dir=args.root) if args.root else GuardianConfig.load()
    bot = GuardianBot(config)

    if args.report:
        print(json.dumps(bot.get_status(), indent=2))
        return 0

    if args.once:
        results = bot.run_once()
        print(json.dumps(results, indent=2, default=str))
        return 0

    # Default: 24/7 daemon mode.
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
