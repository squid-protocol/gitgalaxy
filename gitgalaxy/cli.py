# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The `gitgalaxy` command: one entry point for the customer-facing subcommands (#4726).

    gitgalaxy assess ESTATE [...]      the offline readiness scan (gitgalaxy/tools/readiness/assess.py)

The scan engine itself stays `galaxyscope` / `blast`.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    from gitgalaxy.tools.readiness import assess

    p = argparse.ArgumentParser(prog="gitgalaxy")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("assess", help="the offline, read-only readiness scan of a COBOL / CICS estate")
    assess.add_arguments(a)
    args = p.parse_args(argv)
    return assess.run(args)


if __name__ == "__main__":
    sys.exit(main())
