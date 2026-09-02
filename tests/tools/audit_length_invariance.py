#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Direct-invocation LENGTH-invariance audit for SignalProcessor's per-file risk equations
(#2655) -- the length-axis twin of tests/tools/audit_risk_equations.py's tier-axis audit.

Methodology: call each per-file _calc_*() directly with a synthetic `raw_signals` dict
held IDENTICAL while only `loc` varies. By the time a file reaches SignalProcessor it
has already been reduced to "tier + a dict of integer signature counts + LOC", so a
synthetic dict is the correct isolation technique, not a shortcut (see the sibling
audit's docstring for the #1055 precedent).

The property under audit is the Universal Exposure Framework's evidence-mass floor:
below ENGINE_CONSTANTS["EVIDENCE_MASS_FLOOR"] coding lines, a file is scored on its
COUNTS, so identical planted intent must score identically at 3 LOC and at 49 LOC.
At or above the floor the density regime takes over, and scores are expected to fall
with length. Two flags:

  - INVARIANCE VIOLATION: two LOC values below the floor give different scores for
    identical signals. This is exactly the shape the keyword-rosetta control corpus
    (files of 3-29 coding LOC, identical plants in 46 languages) exposed: a new
    small-file guard that divides by raw LOC reintroduces it silently.
  - DISCONTINUITY: the score jumps by more than --jump-flag points between the floor
    and floor+1 -- a cliff like the old `loc < 15 -> 5.0` special path.

The swept signal vectors are the keyword-rosetta SPEC's own four planted probe files
(main/a/b/c), so the audit reads the same evidence the corpus does.

Usage:
    python tests/tools/audit_length_invariance.py
    python tests/tools/audit_length_invariance.py --equation state_flux
    python tests/tools/audit_length_invariance.py --jump-flag 2.0
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Callable

from gitgalaxy.metrics.signal_processor import SignalProcessor

# The keyword-rosetta SPEC probe files as the engine sees them after api inflation on
# imported files (a/b/c: api = defs x 2; main: api = defs) -- see the corpus SPEC.md.
ROSETTA_VECTORS: dict[str, dict[str, int]] = {
    "main": {
        "branch": 3,
        "io": 3,
        "high_risk_execution": 2,
        "doc": 1,
        "ownership": 1,
        "encapsulation": 1,
        "import": 1,
        "func_start": 4,
        "args": 4,
        "api": 4,
    },
    "a": {
        "import": 1,
        "func_start": 3,
        "args": 3,
        "api": 6,
        "globals": 2,
        "test": 2,
        "safety": 2,
        "high_risk_execution": 1,
    },
    "b": {"import": 1, "func_start": 3, "args": 3, "api": 6, "safety_bypasses": 2, "telemetry": 2, "state_mutation": 2},
    "c": {"func_start": 3, "args": 3, "api": 6, "cleanup": 2, "fragile_debt": 1, "planned_debt": 1},
}

INVARIANCE_EPSILON = 1e-9
# The steepest legitimate density-regime step at the boundary is tech debt's ~1.2
# points (sigmoid slope 0.5 on a per-100-LOC density); the old <15 cliff was ~30.
DEFAULT_JUMP_FLAG = 2.5


@dataclass
class EquationCase:
    name: str
    call: Callable[[SignalProcessor, int, dict[str, int], dict[str, Any]], float]


def _tv(p: SignalProcessor, tier: str) -> dict[str, Any]:
    return p.TIER_VARS[tier]


EQUATION_CASES: list[EquationCase] = [
    EquationCase("cog_load", lambda p, loc, s, tv: p._calc_cog_load(loc, s, tv["irc"], tv["fc"], 1.0, 0.0)[0]),
    EquationCase("safety", lambda p, loc, s, tv: p._calc_safety(loc, s, tv["irc"], tv["fc"], 1.0)),
    EquationCase("tech_debt", lambda p, loc, s, tv: p._calc_tech_debt(loc, s, tv["irc"], 1.0)),
    EquationCase("documentation", lambda p, loc, s, tv: p._calc_documentation(loc, 2, s, tv["fc"], tv["irc"], 1.0)),
    EquationCase(
        "verification",
        lambda p, loc, s, tv: p._calc_verification(
            loc,
            False,
            s,
            tv.get("ot", 1.0),
            tv["fc"],
            1.0,
            [{"name": "f", "impact": 60.0, "hit_vector": {}, "docstring": None}],
            {},
        ),
    ),
    # api reads total_loc, not coding_loc; the sweep feeds the same number to keep the
    # axis single-valued.
    EquationCase("api_exposure", lambda p, loc, s, tv: p._calc_api_exposure(s, loc, 0)),
    EquationCase(
        "concurrency", lambda p, loc, s, tv: p._calc_concurrency(loc, {**s, "concurrency": 2}, tv["irc"], 1.0)
    ),
    EquationCase("state_flux", lambda p, loc, s, tv: p._calc_state_flux(loc, s, tv["irc"], 1.0)),
]


def sweep_locs(floor: int) -> list[int]:
    below = sorted({3, 5, 8, 10, 12, 14, 15, 16, 20, 25, 30, 40, floor - 1})
    return [x for x in below if 0 < x < floor] + [floor, floor + 1, 100, 300]


def audit(processor: SignalProcessor, case: EquationCase, jump_flag: float) -> tuple[list[str], bool, bool]:
    floor = int(processor.EVIDENCE_MASS_FLOOR)
    locs = sweep_locs(floor)
    lines: list[str] = []
    any_invariance = False
    any_jump = False
    lines.append(f"## {case.name}")
    header = f"{'file':>5} {'tier':>6} | " + " ".join(f"{loc:>6}" for loc in locs) + "  flags"
    lines.append(header)
    for fname, sig in ROSETTA_VECTORS.items():
        for tier in ("tier1", "tier2", "tier3"):
            scores = [float(case.call(processor, loc, sig, _tv(processor, tier))) for loc in locs]
            below = [s for loc, s in zip(locs, scores) if loc < floor]
            flags = []
            if below and (max(below) - min(below)) > INVARIANCE_EPSILON:
                flags.append("INVARIANCE VIOLATION")
                any_invariance = True
            at_floor = scores[locs.index(floor)]
            past_floor = scores[locs.index(floor + 1)]
            if abs(at_floor - past_floor) > jump_flag:
                flags.append(f"DISCONTINUITY ({at_floor:.2f} -> {past_floor:.2f})")
                any_jump = True
            lines.append(f"{fname:>5} {tier:>6} | " + " ".join(f"{s:6.2f}" for s in scores) + "  " + ", ".join(flags))
    lines.append("")
    return lines, any_invariance, any_jump


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--equation", type=str, default=None, help="Audit only this equation (e.g. state_flux)")
    parser.add_argument(
        "--jump-flag",
        type=float,
        default=DEFAULT_JUMP_FLAG,
        help=f"Flag a score jump larger than this between floor and floor+1 LOC (default {DEFAULT_JUMP_FLAG})",
    )
    args = parser.parse_args()

    processor = SignalProcessor()
    cases = EQUATION_CASES
    if args.equation:
        cases = [c for c in cases if c.name == args.equation]
        if not cases:
            print(f"Unknown equation '{args.equation}'. Options: {', '.join(c.name for c in EQUATION_CASES)}")
            return 1

    print("=" * 78)
    print(f"LENGTH INVARIANCE -- evidence-mass floor = {int(processor.EVIDENCE_MASS_FLOOR)} coding LOC (#2655)")
    print("=" * 78)
    invariance_flagged = False
    jump_flagged = False
    for case in cases:
        lines, inv, jump = audit(processor, case, args.jump_flag)
        print("\n".join(lines))
        invariance_flagged |= inv
        jump_flagged |= jump

    if invariance_flagged:
        print("RESULT: INVARIANCE VIOLATION -- identical signals score differently below the floor.")
        return 1
    if jump_flagged:
        print(
            f"RESULT: no invariance violations, but a score jumps by more than {args.jump_flag} at the floor boundary."
        )
        return 1
    print("RESULT: identical intent scores identically below the floor; no cliff at the boundary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
