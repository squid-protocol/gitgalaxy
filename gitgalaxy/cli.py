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
    gitgalaxy reach SCAN_DB [...]      who depends on a file, from a finished scan (gitgalaxy/tools/sensors/reach.py)
    gitgalaxy libsurface SCAN_DB [...] which libraries a repository leans on, and how that moves (gitgalaxy/tools/sensors/libsurface.py)
    gitgalaxy change REPO [...]        what a change did: repeated renames, debt markers, functions touched and who calls them (gitgalaxy/tools/sensors/change.py)

The scan engine itself stays `galaxyscope` / `blast`.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    from gitgalaxy.tools.readiness import assess
    from gitgalaxy.tools.sensors import change, libsurface, reach

    p = argparse.ArgumentParser(prog="gitgalaxy")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("assess", help="the offline, read-only readiness scan of a COBOL / CICS estate")
    assess.add_arguments(a)
    r = sub.add_parser("reach", help="who depends on a file: caller counts from a finished scan (read-only)")
    reach.add_arguments(r)
    ls = sub.add_parser(
        "libsurface", help="which libraries a repository leans on and how that surface changes (read-only)"
    )
    libsurface.add_arguments(ls)
    c = sub.add_parser(
        "change", help="what a git change did: repeated renames, debt markers, functions touched (read-only)"
    )
    change.add_arguments(c)
    args = p.parse_args(argv)
    if args.command == "reach":
        return reach.run(args)
    if args.command == "change":
        return change.run(args)
    return libsurface.run(args) if args.command == "libsurface" else assess.run(args)


if __name__ == "__main__":
    sys.exit(main())
