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
  4. STRICTNESS ORDER -- more strictness gaps never score lower for identical evidence
                    in the count regime (#2718 replaced the three tiers with the
                    language-strictness table; the direction rule is the same one
                    audit_risk_equations.py guards, and since #2717 it holds for safety too).

The swept vectors are the corpus SPEC's own four probe files as the engine sees them,
so this is the engine-side regression fixture the issue asked for -- no scan, no
cross-repo checkout, deterministic.
"""

import pytest

from gitgalaxy.metrics.signal_processor import SignalProcessor
from gitgalaxy.standards import analysis_lens

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

# The pre-#2718 tier constants, kept ONLY so the pre-#2655 density-regime pins below stay
# reproducible: the equations are pure functions of (irc, ot, fc), and #2718 changed where
# those come from, not (except safety, #2717) what the equations do with them.
LEGACY_TIERS = {
    "tier1": {"fc": 1.0, "irc": 0, "ot": 1.00},
    "tier2": {"fc": 0.85, "irc": 2, "ot": 1.15},
    "tier3": {"fc": 0.60, "irc": 5, "ot": 1.40},
}


def uniform_fid(fc: float) -> dict[str, float]:
    return {"safety": fc, "test": fc, "doc": fc, "ownership": fc}


@pytest.fixture(scope="module")
def processor():
    return SignalProcessor()


def score_all(p: SignalProcessor, sig: dict, loc: int, tier: str) -> dict[str, float]:
    tv = LEGACY_TIERS[tier]
    fid, irc, ot = uniform_fid(tv["fc"]), tv["irc"], tv["ot"]
    return {
        "cog": p._calc_cog_load(loc, sig, irc, fid, 1.0, 0.0)[0],
        "safety": p._calc_safety(loc, sig, irc, fid, 1.0),
        "debt": p._calc_tech_debt(loc, sig, irc, 1.0),
        "doc": p._calc_documentation(loc, 2, sig, fid, 1.0),
        "verification": p._calc_verification(
            loc, False, sig, ot, fid, 1.0, [{"name": "f", "impact": 60.0, "hit_vector": {}, "docstring": None}], {}
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


# Pinned at 51 coding LOC, popularity 0, doc_loc 2, mp 1.0 -- one line past the
# evidence-mass floor, where the density regime must not move by a rounding step.
# Provenance: taken from origin/main before #2655; safety re-pinned in #2718 (the
# 0.75 systems buffer retired, #2717) and documentation in #2718/#2719 (rule hits
# alone carry fidelity; per-file dynamism replaced the language irc); cognitive
# load, concurrency and state flux re-pinned in #2719 (dynamism in heat_density,
# language irc term removed). Every other equation still equals the pre-#2655 engine.
PRE_2655_AT_51 = {
    ("tier1", "main"): {
        "cog": 4.7642,
        "safety": 79.1701,
        "debt": 0.0,
        "doc": 62.5434,
        "api": 6.5172,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier1", "a"): {
        "cog": 0.0,
        "safety": 54.2153,
        "debt": 0.0,
        "doc": 82.7643,
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
        "safety": 89.908,
        "debt": 0.0,
        "doc": 64.5012,
        "api": 6.5172,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier3", "a"): {
        "cog": 0.0,
        "safety": 77.1518,
        "debt": 0.0,
        "doc": 82.7643,
        "api": 9.8496,
        "flux": 0.0,
        "spec": 100.0,
    },
    ("tier3", "b"): {
        "cog": 0.0,
        "safety": 82.0704,
        "debt": 0.0,
        "doc": 78.3694,
        "api": 9.8496,
        "flux": 37.0197,
        "spec": 100.0,
    },
    ("tier3", "c"): {
        "cog": 0.0,
        "safety": 0.0,
        "debt": 97.9619,
        "doc": 78.3694,
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


def strict_profile(gaps: int) -> dict:
    """A strictness row with `gaps` False columns, at full fidelity -- the shape
    analysis_lens.strictness_constants() produces (#2718)."""
    irc = gaps * analysis_lens.STRICTNESS_IRC_PER_GAP
    return {"fc": 1.0, "irc": irc, "ot": 1.0 + gaps * analysis_lens.STRICTNESS_OT_PER_GAP}


def score_profile(p: SignalProcessor, sig: dict, loc: int, tv: dict) -> dict[str, float]:
    fid, irc, ot = uniform_fid(tv["fc"]), tv["irc"], tv["ot"]
    return {
        "cog": p._calc_cog_load(loc, sig, irc, fid, 1.0, 0.0)[0],
        "safety": p._calc_safety(loc, sig, irc, fid, 1.0),
        "debt": p._calc_tech_debt(loc, sig, irc, 1.0),
        "doc": p._calc_documentation(loc, 2, sig, fid, 1.0),
        "verification": p._calc_verification(
            loc, False, sig, ot, fid, 1.0, [{"name": "f", "impact": 60.0, "hit_vector": {}, "docstring": None}], {}
        ),
        "concurrency": p._calc_concurrency(loc, {**sig, "concurrency": 2}, irc, 1.0),
        "flux": p._calc_state_flux(loc, sig, irc, 1.0),
    }


@pytest.mark.parametrize("fname", sorted(ROSETTA_VECTORS))
def test_strictness_direction_holds_in_the_count_regime(processor, fname):
    """Irc is an additive correction for what a language lets you leave unsaid, so for
    identical evidence a language with more strictness gaps never scores LOWER. The
    floor bounds Irc, it does not reorder it. Safety is included since #2717: the
    retired systems_buffer_ratio was the one thing that used to invert it."""
    sig = ROSETTA_VECTORS[fname]
    s0, s2, s4 = (score_profile(processor, sig, 10, strict_profile(g)) for g in (0, 2, 4))
    for eq in ("cog", "safety", "debt", "doc", "verification", "concurrency", "flux"):
        assert s0[eq] <= s2[eq] + 1e-9 <= s4[eq] + 2e-9, (
            f"{fname}/{eq} strictness order inverted: {s0[eq]}, {s2[eq]}, {s4[eq]}"
        )


def test_safety_never_discounts_more_hits_into_a_lower_score(processor):
    """#2717 regression guard: with the systems buffer gone, identical attack evidence at
    zero defence scores monotonically in Irc at EVERY hit count -- the old buffer made
    tier 2 cross below tier 1 at 6 attack-weighted hits and tier 3 at 15."""
    fid = uniform_fid(1.0)
    for hits in (1, 2, 6, 10, 15, 20, 40):
        sig = {"safety_bypasses": hits}  # weight 1.5 -> attack_hits = 1.5 * hits
        scores = [processor._calc_safety(200, sig, irc, fid, 1.0) for irc in (0, 2, 4)]
        assert scores == sorted(scores), f"{hits} hits: {scores}"


def test_zero_evidence_scores_zero_regardless_of_language(processor):
    """Irc corrects measured risk; it never creates it. A file with no public surface,
    no branches and no debt scores 0 on documentation, cognitive load and tech debt in
    every language -- tier-3 files used to carry 19-42 documentation risk on irc alone."""
    for lang in ("rust", "python", "shell", "yacc", "yaml", "embedded_python", "not-a-language"):
        irc, _ot, fid = processor._language_constants(lang)
        for loc in (3, 10, 49, 50, 200):
            assert processor._calc_documentation(loc, 0, {}, fid, 1.0) == 0.0
            assert processor._calc_cog_load(loc, {"state_mutation": 4}, irc, fid, 1.0)[0] == 0.0
            assert processor._calc_tech_debt(loc, {}, irc, 1.0) == 0.0


def test_spec_alignment_needs_entities(processor):
    """No functions or classes: nothing to specify, nothing misaligned (was a flat 100
    hidden by the loc/15 dampener for css/yaml-shaped files)."""
    assert processor._calc_spec_alignment({"func_start": 0, "class_start": 0, "spec_exposure": 0}, 1.0) == 0.0
    assert processor._calc_spec_alignment({"func_start": 2, "class_start": 0, "spec_exposure": 0}, 1.0) == 100.0
    assert processor._calc_spec_alignment({"func_start": 2, "class_start": 0, "spec_exposure": 1}, 1.0) == 50.0
