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
Direct-invocation tier-parity audit for SignalProcessor's tier-aware _calc_*() risk
equations (epic #1056).

Methodology (matches the empirical proof that found #1055's systems_buffer bug): call
each _calc_*() method directly with synthetic, controlled `raw_signals` held IDENTICAL
across tier1/tier2/tier3, varying only the tier constants (fc/irc/ot) each equation
actually receives. No real files, repos, or scans are involved -- by the time a file
reaches SignalProcessor it has already been reduced to "tier + a dict of integer
signature counts", so synthetic dicts are the correct isolation technique, not a
shortcut.

This isn't just a "does tier move the score too much" magnitude check. Per the
documented Universal Exposure Framework philosophy (docs/08-01-methodology,
03-02-claim-2-explicitness, 08-03-transforming-regex-counts):
  - Irc (Implicit Risk Correction) is an ADDITIVE baseline representing structural
    opacity: implicit/tier3 languages should carry residual risk implicit languages
    "require baseline hidden-risk assumptions... to reflect structural opacity" even
    absent detected danger signals.
  - Fc (Fidelity Coefficient) discounts DEFENSE credit for implicit languages: "a
    'Safe' rating in Shell requires significantly more defensive effort than in Go."
  - Documented general shape: RiskExposure = (((RiskHits + Irc) x Weight) -
    (DefenseHits x Fc)) / LOC) x Mp.

The correctness bar this implies: for IDENTICAL risk-only evidence, tier1 should
score AT OR BELOW tier2/tier3 (never dramatically above -- that's exactly the
direction #1055's systems_buffer bug got backwards: Rust scored 52-66 while Python
scored 5-8 for the same attack evidence). For IDENTICAL defense-only evidence, tier1
should end up with the LOWER resulting risk (more credit for legible, explicit
defense). Each equation with an Fc-gated defense term gets both a "risk" and a
"defense" scenario; the DIRECTION check (monotonic tier1 <= tier2 <= tier3) is
therefore evaluated in both scenarios and is a distinct, more important flag than the
raw magnitude ratio -- a magnitude flag says "big swing"; a direction flag says
"swing points the wrong way, like #1055 did."

Equations are auto-classified as tier-parameterized (their signature accepts fc/irc/ot)
or not, via inspect.signature -- an equation that never receives a tier constant cannot
exhibit tier-driven distortion by construction, so it's reported as N/A rather than swept.

Usage:
    python tests/tools/audit_risk_equations.py                 # audit all in-scope equations
    python tests/tools/audit_risk_equations.py --equation cog_load
    python tests/tools/audit_risk_equations.py --ratio-flag 5.0
"""

from __future__ import annotations

import argparse
import inspect
from dataclasses import dataclass
from typing import Any, Callable

from gitgalaxy.metrics.signal_processor import SignalProcessor

TIER_PARAM_NAMES = {"fc", "irc", "ot"}
# Small LOC values (10, 20) are deliberately included: #1055's systems_buffer bug was a
# flat constant that dominated a small-file density denominator. Any equation with a
# flat-additive tier constant (irc) divided by LOC is most exposed to that exact
# mechanical shape right at the small end, not at the "typical file" 150-500 range.
LOC_SWEEP = [10, 20, 50, 150, 500]
HIT_SWEEP = [1, 3, 8]
DEFAULT_RATIO_FLAG = 5.0
DIRECTION_EPSILON = 1e-6  # float rounding tolerance for the monotonic tier1<=tier2<=tier3 check


@dataclass
class Scenario:
    """One synthetic-input scenario for an equation: which signal is swept and why."""

    kind: str  # "risk" or "defense"
    build_kwargs: Callable[[int, int, dict[str, Any]], dict[str, Any]]


@dataclass
class EquationCase:
    """One audit target: an equation name plus its scenario(s)."""

    name: str
    method_name: str
    scenarios: list[Scenario]
    notes: str = ""


def _mp1() -> float:
    """mp (locational multiplier) is path-derived, not tier-derived (_get_locational_multipliers
    keys off rel_path only) -- held constant at 1.0 across tiers so it can't contaminate the
    tier-distortion measurement."""
    return 1.0


# ==============================================================================
# Equation registry: the 11 equations epic #1056 lists as in-scope (excluding
# _calc_safety, already fixed via #1055/PR #1067). Each build_kwargs mirrors the real
# call site in SignalProcessor.calculate_risk_vector, using the signal keys that
# equation's body actually reads (raw_signals.get(...) calls), held identical across
# tiers. Equations whose body applies Fc to a defense-shaped term get a second
# "defense" scenario to check Fc's credit direction, not just Irc's risk direction.
# ==============================================================================

EQUATION_CASES: list[EquationCase] = [
    EquationCase(
        name="cog_load",
        method_name="_calc_cog_load",
        notes="irc adds to density (risk axis); fc gates doc-coverage cooling (defense axis). "
        "LOC<15 takes a flat-5.0 small-file floor that ignores fc/irc entirely by design.",
        scenarios=[
            Scenario(
                "risk",
                lambda loc, hits, tv: dict(
                    loc=loc,
                    raw_signals={
                        "branch": hits,
                        "state_mutation": 0,
                        "concurrency": 0,
                        "reflection_metaprogramming": 0,
                        "doc": 0,
                    },
                    irc=tv["irc"],
                    fc=tv["fc"],
                    mp=_mp1(),
                    func_gini=0.0,
                ),
            ),
            Scenario(
                "defense",
                # Ambient branch=10 keeps the file out of the "branches==0" early-exit so the
                # doc-coverage/fc cooling term actually executes.
                lambda loc, hits, tv: dict(
                    loc=loc,
                    raw_signals={
                        "branch": 10,
                        "state_mutation": 0,
                        "concurrency": 0,
                        "reflection_metaprogramming": 0,
                        "doc": hits,
                    },
                    irc=tv["irc"],
                    fc=tv["fc"],
                    mp=_mp1(),
                    func_gini=0.0,
                ),
            ),
        ],
    ),
    EquationCase(
        name="tech_debt",
        method_name="_calc_tech_debt",
        notes="irc adds to stress (risk axis only) -- no fc parameter, so no defense-credit "
        "direction to check.",
        scenarios=[
            Scenario(
                "risk",
                lambda loc, hits, tv: dict(
                    loc=loc,
                    raw_signals={"fragile_debt": hits, "planned_debt": 0, "orphaned_logic": 0, "duplicate_logic": 0},
                    irc=tv["irc"],
                    mp=_mp1(),
                ),
            ),
        ],
    ),
    EquationCase(
        name="documentation",
        method_name="_calc_documentation",
        notes="irc adds directly to risk_hits (risk axis); fc multiplies defense_hits (defense axis).",
        scenarios=[
            Scenario(
                "risk",
                lambda loc, hits, tv: dict(
                    loc=loc,
                    doc_loc=0,
                    raw_signals={"api": hits, "doc": 0, "ownership": 0},
                    fc=tv["fc"],
                    irc=tv["irc"],
                    mp=_mp1(),
                    functions=None,
                    doc_umbrella=0.0,
                    popularity=0,
                    silo_exposure=0.0,
                ),
            ),
            Scenario(
                "defense",
                lambda loc, hits, tv: dict(
                    loc=loc,
                    doc_loc=0,
                    raw_signals={"api": 0, "doc": hits, "ownership": 0},
                    fc=tv["fc"],
                    irc=tv["irc"],
                    mp=_mp1(),
                    functions=None,
                    doc_umbrella=0.0,
                    popularity=0,
                    silo_exposure=0.0,
                ),
            ),
        ],
    ),
    EquationCase(
        name="verification",
        method_name="_calc_verification",
        notes="ot (opacity tax) directly amplifies risk density (risk axis); fc gates "
        "internal_defenses credit inside a function's hit_vector (defense axis).",
        scenarios=[
            Scenario(
                "risk",
                lambda loc, hits, tv: dict(
                    loc=loc,
                    is_protected=False,
                    raw_signals={"high_risk_execution": 0},
                    ot=tv["ot"],
                    fc=tv["fc"],
                    mp=_mp1(),
                    functions=[{"name": "f", "impact": float(hits) * 10.0, "hit_vector": {}, "docstring": None}],
                    test_coverage_map={},
                    umbrella_bonus=0.0,
                    popularity=0,
                ),
            ),
            Scenario(
                "defense",
                # Fixed func_impact=50 with a swept internal "safety" hit_vector credit --
                # internal_defenses = (safety) * fc, so higher fc (tier1) should erase more
                # of base_impact for identical in-function defensive evidence.
                lambda loc, hits, tv: dict(
                    loc=loc,
                    is_protected=False,
                    raw_signals={"high_risk_execution": 0},
                    ot=tv["ot"],
                    fc=tv["fc"],
                    mp=_mp1(),
                    functions=[
                        {"name": "f", "impact": 50.0, "hit_vector": {"safety": hits}, "docstring": "documented"}
                    ],
                    test_coverage_map={},
                    umbrella_bonus=0.0,
                    popularity=0,
                ),
            ),
        ],
    ),
    EquationCase(
        name="concurrency",
        method_name="_calc_concurrency",
        notes="irc adds to density (risk axis only) -- sync_locks mitigation is flat-subtracted, "
        "not fc-weighted, so no defense-credit direction to check.",
        scenarios=[
            Scenario(
                "risk",
                lambda loc, hits, tv: dict(
                    loc=loc,
                    raw_signals={"concurrency": hits, "sync_locks": 0},
                    irc=tv["irc"],
                    mp=_mp1(),
                ),
            ),
        ],
    ),
    EquationCase(
        name="state_flux",
        method_name="_calc_state_flux",
        notes="irc adds to density (risk axis only) -- immutability_locks mitigation is "
        "flat-subtracted, not fc-weighted, so no defense-credit direction to check.",
        scenarios=[
            Scenario(
                "risk",
                lambda loc, hits, tv: dict(
                    loc=loc,
                    raw_signals={"state_mutation": hits, "immutability_locks": 0},
                    irc=tv["irc"],
                    mp=_mp1(),
                ),
            ),
        ],
    ),
    # --- Remaining in-scope equations take no fc/irc/ot at all (verified by reading
    # signal_processor.py directly, not assumed from the epic's approximate scope
    # table) -- auto-classified as N/A below rather than hand-listed here.
]

# Equations listed in epic #1056 whose *only* tier-shaped parameter is `mp`, which the
# audit above already establishes is NOT tier-derived (path-only). Included so the N/A
# classification is reported explicitly per-equation instead of just "everything else".
NOT_TIER_PARAMETERIZED = [
    "_calc_graveyard",
    "_calc_api_exposure",
    "_calc_spec_alignment",
    "_calc_civil_war",
    "_calc_secrets_risk",
]


def audit_scenario(processor: SignalProcessor, case: EquationCase, scenario: Scenario, ratio_flag: float) -> list[dict[str, Any]]:
    rows = []
    for loc in LOC_SWEEP:
        for hits in HIT_SWEEP:
            scores = {}
            for tier in ("tier1", "tier2", "tier3"):
                tier_vars = processor.TIER_VARS[tier]
                kwargs = scenario.build_kwargs(loc, hits, tier_vars)
                result = getattr(processor, case.method_name)(**kwargs)
                score = result[0] if isinstance(result, tuple) else result
                scores[tier] = round(float(score), 2)

            nonzero = [v for v in scores.values() if v > 0]
            if not nonzero:
                ratio = 1.0
            elif len(nonzero) < len(scores):
                ratio = float("inf")  # some tiers see signal, others see none: max distortion
            else:
                ratio = max(scores.values()) / min(scores.values())

            # DIRECTION: per the documented philosophy, tier1 (explicit) should never score
            # ABOVE tier2/tier3 for identical evidence -- neither in the risk scenario (Irc is
            # an additive opacity baseline that should only push implicit tiers UP) nor in the
            # defense scenario (Fc gives tier1 MORE credit, so tier1's resulting risk should be
            # the LOWEST). A violation here is the #1055 shape specifically: tier ordering
            # inverted, not just "moved a lot."
            direction_ok = (
                scores["tier1"] <= scores["tier2"] + DIRECTION_EPSILON
                and scores["tier2"] <= scores["tier3"] + DIRECTION_EPSILON
            )

            rows.append(
                {
                    "loc": loc,
                    "hits": hits,
                    **scores,
                    "ratio": ratio,
                    "magnitude_flag": ratio > ratio_flag,
                    "direction_violation": not direction_ok,
                }
            )
    return rows


def print_report(case: EquationCase, scenario: Scenario, rows: list[dict[str, Any]]) -> tuple[bool, bool]:
    any_magnitude = any(r["magnitude_flag"] for r in rows)
    any_direction = any(r["direction_violation"] for r in rows)
    print(f"## {case.name} ({case.method_name}) -- {scenario.kind} scenario")
    print(f"{'loc':>5} {'hits':>5} {'tier1':>8} {'tier2':>8} {'tier3':>8} {'ratio':>8}  flags")
    for r in rows:
        ratio_str = "inf" if r["ratio"] == float("inf") else f"{r['ratio']:.2f}"
        flags = []
        if r["direction_violation"]:
            flags.append("DIRECTION VIOLATION (#1055-shaped)")
        if r["magnitude_flag"]:
            flags.append("magnitude")
        flag_str = ", ".join(flags)
        print(f"{r['loc']:>5} {r['hits']:>5} {r['tier1']:>8} {r['tier2']:>8} {r['tier3']:>8} {ratio_str:>8}  {flag_str}")
    print()
    return any_magnitude, any_direction


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--equation", type=str, default=None, help="Audit only this equation name (e.g. cog_load)")
    parser.add_argument(
        "--ratio-flag",
        type=float,
        default=DEFAULT_RATIO_FLAG,
        help=f"Flag any (loc, hits) combo whose max/min tier score ratio exceeds this (default {DEFAULT_RATIO_FLAG})",
    )
    args = parser.parse_args()

    processor = SignalProcessor()

    cases = EQUATION_CASES
    if args.equation:
        cases = [c for c in cases if c.name == args.equation]
        if not cases:
            names = ", ".join(c.name for c in EQUATION_CASES)
            print(f"Unknown equation '{args.equation}'. Tier-parameterized options: {names}")
            return 1

    print("=" * 78)
    print("TIER-AWARE (fc/irc/ot in signature) -- synthetic sweep")
    print("=" * 78)
    any_magnitude_flagged = False
    any_direction_flagged = False
    for case in cases:
        method = getattr(processor, case.method_name)
        assert TIER_PARAM_NAMES & set(inspect.signature(method).parameters), (
            f"{case.method_name} no longer takes a tier parameter -- move it to NOT_TIER_PARAMETERIZED"
        )
        for scenario in case.scenarios:
            rows = audit_scenario(processor, case, scenario, args.ratio_flag)
            mag, direction = print_report(case, scenario, rows)
            any_magnitude_flagged |= mag
            any_direction_flagged |= direction

    if not args.equation:
        print("=" * 78)
        print("NOT TIER-PARAMETERIZED (fc/irc/ot absent from signature) -- N/A by construction")
        print("=" * 78)
        for method_name in NOT_TIER_PARAMETERIZED:
            method = getattr(processor, method_name)
            params = set(inspect.signature(method).parameters)
            overlap = TIER_PARAM_NAMES & params
            status = "OK: confirmed tier-blind" if not overlap else f"MISMATCH: now takes {overlap} -- re-audit needed"
            print(f"  {method_name}: {status}")
        print()

    if any_direction_flagged:
        print("RESULT: DIRECTION VIOLATION found -- tier ordering inverted for identical evidence (#1055-shaped bug).")
        return 1
    if any_magnitude_flagged:
        print(f"RESULT: no direction violations, but one or more equations exceeded the {args.ratio_flag}x magnitude flag.")
        return 1
    print("RESULT: no direction violations or magnitude flags raised for the swept ranges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
