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
Universal Exposure Framework evidence-mass floor (#2655): identical intent must score
identically regardless of file length.

The keyword-rosetta control corpus plants the same 12-probe program in 46 languages,
in files of 3-29 coding LOC. Before #2655 the per-file risk scores of those files were
decided by their length, not their content: six independent small-file guards
(the `loc < 15 -> 5.0` cognitive-load cliff, two `+20` paddings, a `loc/15` dampener,
an unbounded `irc/loc` floor, api's `max(total_loc, 10)`) each fired on a different
LOC range with a different shape. This module pins the replacement property:

  1. INVARIANCE  -- below ENGINE_CONSTANTS["EVIDENCE_MASS_FLOOR"], every per-file
                    equation returns the same score for the same signals at any LOC.
  2. CONTINUITY  -- the score at the floor equals the score just below it (no cliff).
  3. PARITY      -- at floor+1 and above, scores are byte-identical to the pre-#2655
                    engine (values pinned from origin/main before the change).
  4. TIER ORDER  -- tier1 <= tier2 <= tier3 still holds in the count regime, so the
                    floor did not invert the Irc direction audit_risk_equations.py guards.

The swept vectors are the corpus SPEC's own four probe files as the engine sees them,
so this is the engine-side regression fixture the issue asked for -- no scan, no
cross-repo checkout, deterministic.
"""

import pytest

from gitgalaxy.metrics.signal_processor import SignalProcessor

ROSETTA_VECTORS = {
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

EQUATIONS = ["cog", "safety", "debt", "doc", "verification", "api", "concurrency", "flux", "spec"]


@pytest.fixture(scope="module")
def processor():
    return SignalProcessor()


def score_all(p: SignalProcessor, sig: dict, loc: int, tier: str) -> dict[str, float]:
    tv = p.TIER_VARS[tier]
    fc, irc, ot = tv["fc"], tv["irc"], tv.get("ot", 1.0)
    return {
        "cog": p._calc_cog_load(loc, sig, irc, fc, 1.0, 0.0)[0],
        "safety": p._calc_safety(loc, sig, irc, fc, 1.0),
        "debt": p._calc_tech_debt(loc, sig, irc, 1.0),
        "doc": p._calc_documentation(loc, 2, sig, fc, irc, 1.0),
        "verification": p._calc_verification(
            loc, False, sig, ot, fc, 1.0, [{"name": "f", "impact": 60.0, "hit_vector": {}, "docstring": None}], {}
        ),
        "api": p._calc_api_exposure(sig, loc, 0),
        "concurrency": p._calc_concurrency(loc, {**sig, "concurrency": 2}, irc, 1.0),
        "flux": p._calc_state_flux(loc, sig, irc, 1.0),
        "spec": p._calc_spec_alignment(sig, 1.0),
    }


@pytest.mark.parametrize("fname", sorted(ROSETTA_VECTORS))
@pytest.mark.parametrize("tier", ["tier1", "tier2", "tier3"])
def test_identical_intent_scores_identically_below_the_floor(processor, fname, tier):
    floor = int(processor.EVIDENCE_MASS_FLOOR)
    sig = ROSETTA_VECTORS[fname]
    locs = [3, 5, 8, 10, 12, 14, 15, 16, 20, 25, 30, 40, floor - 1]
    scored = {loc: score_all(processor, sig, loc, tier) for loc in locs}
    for eq in EQUATIONS:
        values = {scored[loc][eq] for loc in locs}
        assert len(values) == 1, f"{fname}/{tier}/{eq} varies with length below the floor: {values}"


@pytest.mark.parametrize("fname", sorted(ROSETTA_VECTORS))
@pytest.mark.parametrize("tier", ["tier1", "tier2", "tier3"])
def test_no_cliff_at_the_floor(processor, fname, tier):
    floor = int(processor.EVIDENCE_MASS_FLOOR)
    sig = ROSETTA_VECTORS[fname]
    below, at, above = (score_all(processor, sig, loc, tier) for loc in (floor - 1, floor, floor + 1))
    for eq in EQUATIONS:
        assert below[eq] == at[eq], f"{fname}/{tier}/{eq}: {below[eq]} at {floor - 1} vs {at[eq]} at {floor}"
        # One line past the floor the density regime takes over by a sliver, never a
        # jump. The steepest observed step is tech debt's 1.2 points (its sigmoid
        # slope on a per-100-LOC density); the old <15 cliff moved cognitive load by
        # 30 points. Direction is not asserted: cognitive load can tick UP past the
        # floor because its per-LOC documentation cooling weakens faster than its
        # branch density falls -- pre-existing density-regime behaviour.
        assert abs(at[eq] - above[eq]) < 2.5, f"{fname}/{tier}/{eq} cliff at the floor: {at[eq]} -> {above[eq]}"


# Pinned from origin/main (pre-#2655 engine) at 51 coding LOC, popularity 0, doc_loc 2,
# mp 1.0 -- the density regime must not have moved by a single rounding step.
PRE_2655_AT_51 = {
    ("tier1", "main"): {
        "cog": 4.7642,
        "safety": 79.1701,
        "debt": 0.0,
        "doc": 48.7327,
        "api": 6.5172,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier1", "a"): {
        "cog": 0.0,
        "safety": 54.2153,
        "debt": 0.0,
        "doc": 78.3694,
        "api": 9.8496,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier1", "b"): {
        "cog": 0.0,
        "safety": 66.2858,
        "debt": 0.0,
        "doc": 78.3694,
        "api": 9.8496,
        "flux": 30.3355,
        "spec": 100.0,
    },
    ("tier1", "c"): {
        "cog": 0.0,
        "safety": 0.0,
        "debt": 80.5584,
        "doc": 78.3694,
        "api": 9.8496,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier3", "main"): {
        "cog": 7.5256,
        "safety": 83.7228,
        "debt": 0.0,
        "doc": 81.4487,
        "api": 6.5172,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier3", "a"): {
        "cog": 0.0,
        "safety": 69.7753,
        "debt": 0.0,
        "doc": 93.8944,
        "api": 9.8496,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier3", "b"): {
        "cog": 0.0,
        "safety": 75.7835,
        "debt": 0.0,
        "doc": 93.8944,
        "api": 9.8496,
        "flux": 37.0197,
        "spec": 100.0,
    },
    ("tier3", "c"): {
        "cog": 0.0,
        "safety": 0.0,
        "debt": 97.9619,
        "doc": 93.8944,
        "api": 9.8496,
        "flux": 0.0,
        "spec": 100.0,
    },
}


@pytest.mark.parametrize("key", sorted(PRE_2655_AT_51))
def test_density_regime_unchanged_above_the_floor(processor, key):
    tier, fname = key
    assert processor.EVIDENCE_MASS_FLOOR == 50, "pins below were taken at 51 LOC against a floor of 50"
    got = score_all(processor, ROSETTA_VECTORS[fname], 51, tier)
    for eq, expected in PRE_2655_AT_51[key].items():
        assert got[eq] == pytest.approx(expected, abs=5e-5), f"{tier}/{fname}/{eq}: {got[eq]} != pre-#2655 {expected}"


@pytest.mark.parametrize("fname", sorted(ROSETTA_VECTORS))
def test_tier_direction_holds_in_the_count_regime(processor, fname):
    """Irc is an additive opacity baseline and Fc discounts defense credit, so for
    identical evidence tier1 <= tier2 <= tier3 (the #1055 direction rule) must survive
    the floor -- the floor bounds Irc, it does not reorder it."""
    sig = ROSETTA_VECTORS[fname]
    t1, t2, t3 = (score_all(processor, sig, 10, t) for t in ("tier1", "tier2", "tier3"))
    # safety is deliberately absent: its tier2/tier3 systems_buffer_ratio (0.75, #1055)
    # can discount an attack term by more than irc adds, so tier2 < tier1 there is
    # pre-existing and length-independent -- audit_risk_equations.py owns that axis.
    for eq in ("cog", "debt", "doc", "concurrency", "flux"):
        assert t1[eq] <= t2[eq] + 1e-9 <= t3[eq] + 2e-9, (
            f"{fname}/{eq} tier order inverted: {t1[eq]}, {t2[eq]}, {t3[eq]}"
        )


def test_zero_evidence_scores_zero_regardless_of_tier(processor):
    """Irc corrects measured risk; it never creates it. A file with no public surface,
    no branches and no debt scores 0 on documentation, cognitive load and tech debt in
    every tier -- tier-3 files used to carry 19-42 documentation risk on irc alone."""
    for tier in ("tier1", "tier2", "tier3"):
        tv = processor.TIER_VARS[tier]
        for loc in (3, 10, 49, 50, 200):
            assert processor._calc_documentation(loc, 0, {}, tv["fc"], tv["irc"], 1.0) == 0.0
            assert processor._calc_cog_load(loc, {"state_mutation": 4}, tv["irc"], tv["fc"], 1.0)[0] == 0.0
            assert processor._calc_tech_debt(loc, {}, tv["irc"], 1.0) == 0.0


def test_spec_alignment_needs_entities(processor):
    """No functions or classes: nothing to specify, nothing misaligned (was a flat 100
    hidden by the loc/15 dampener for css/yaml-shaped files)."""
    assert processor._calc_spec_alignment({"func_start": 0, "class_start": 0, "spec_exposure": 0}, 1.0) == 0.0
    assert processor._calc_spec_alignment({"func_start": 2, "class_start": 0, "spec_exposure": 0}, 1.0) == 100.0
    assert processor._calc_spec_alignment({"func_start": 2, "class_start": 0, "spec_exposure": 1}, 1.0) == 50.0
