# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Algorithmic parity + provenance gate for the composition archetype brains
(#3124 provenance, #3125 parity).

These tests fail a build if a committed brain drifts from the engine that
consumes it -- the class of bug that shipped in v2.8.0 (engine/model/trainer in
three feature spaces -> Unclassified flood). They validate the shipped brains,
not a live retrain: cheap, deterministic, no corpus required.
"""

import json
import logging

import pytest

from gitgalaxy.metrics import archetype_classifier as ac
from gitgalaxy.metrics import archetype_parity as ap
from gitgalaxy.standards import analysis_lens

# Pinned feature-contract shas: the exact feature space the engine at THIS commit
# was written against. A refrozen brain that changes the contract (feature names,
# order, weights, k, ...) changes these, and this test fails -- forcing the
# refreeze to be paired with a deliberate engine update rather than silently
# reinterpreting every classification (#3125, mechanism e). Never update these
# blindly to make the test pass.
EXPECTED_CONTRACT_SHA = {
    "file": "92c0b8a801d69bb0",
    "repo": "5858e2d9914677a1",
}

REQUIRED_PROVENANCE_KEYS = {
    "corpus",
    "corpus_sha256",
    "trainer_commit",
    "trainer_version",
    "engine_commit",
    "trained_at",
    "k",
    "feature_contract",
    "feature_contract_sha",
}

BRAINS = [
    ("file", analysis_lens.FILE_ARCHETYPE_BRAIN),
    ("repo", analysis_lens.REPO_ARCHETYPE_BRAIN),
]


@pytest.mark.parametrize("level,brain", BRAINS)
def test_brain_loads(level, brain):
    assert brain, f"{level} composition brain failed to load from archetype_brains/"


# ------------------------------------------------------------------ provenance (#3124)
@pytest.mark.parametrize("level,brain", BRAINS)
def test_provenance_present_and_nonempty(level, brain):
    prov = brain.get("provenance")
    assert prov, f"{level} brain ships with no provenance block (#3124)"
    missing = REQUIRED_PROVENANCE_KEYS - set(prov)
    assert not missing, f"{level} provenance missing required keys: {sorted(missing)}"
    # The parity-critical fields must be real, even on a backfilled brain.
    assert prov["feature_contract_sha"], f"{level} provenance has empty feature_contract_sha"
    assert prov["engine_commit"], f"{level} provenance has empty engine_commit"
    assert prov["trainer_version"], f"{level} provenance has empty trainer_version"


# ------------------------------------------------------------------ parity gate (#3125)
@pytest.mark.parametrize("level,brain", BRAINS)
def test_check_brain_clean(level, brain):
    problems = ap.check_brain(brain, level)
    assert problems == [], f"{level} brain fails engine parity: {problems}"


@pytest.mark.parametrize("level,brain", BRAINS)
def test_contract_sha_matches_pinned(level, brain):
    live = ap.feature_contract_sha(brain, level)
    assert live == EXPECTED_CONTRACT_SHA[level], (
        f"{level} feature contract changed (live {live} != pinned {EXPECTED_CONTRACT_SHA[level]}). "
        "If a refreeze intentionally changed the feature space, pair it with an engine review and "
        "update EXPECTED_CONTRACT_SHA deliberately."
    )
    # The trainer-baked sha must agree with the engine's live recomputation.
    assert brain["provenance"]["feature_contract_sha"] == live, (
        f"{level} brain's baked provenance sha disagrees with its live feature fields -- "
        "the brain was edited after freezing"
    )


def test_engine_aux_matches_shipped_file_brain():
    """The engine's declared computable aux set must equal the shipped file brain's
    aux_features -- otherwise the engine either can't score a declared feature or
    silently drops one it computes."""
    assert tuple(analysis_lens.FILE_ARCHETYPE_BRAIN["aux_features"]) == ap.ENGINE_FILE_AUX_FEATURES


# ------------------------------------------------------------------ runtime guards
def _synthetic_code_file():
    """A minimal file payload that clears classify_file's non-code gate."""
    return {
        "lang_id": "python",
        "coding_loc": 500,
        "doc_loc": 10,
        "functions": [{}] * 5,
        "classes": [{}],
        "raw_imports": ["os"],
        "telemetry": {
            "function_archetype_mix": {"Compute Cores": 3, "Defensive Guards": 1},
            "encapsulation_ratio": 0.5,
            "control_flow_ratio": 0.3,
            "network_metrics": {"pagerank_score": 0.1, "normalized_blast_radius": 0.2},
        },
    }


def test_unknown_aux_feature_degrades_not_crashes(monkeypatch, caplog):
    """A brain declaring an aux feature the engine can't compute must degrade to
    unclassified with a named warning -- never a KeyError crash mid-scan, never a
    silent 0.0 column."""
    b = json.loads(json.dumps(analysis_lens.FILE_ARCHETYPE_BRAIN))  # deep copy
    b["aux_features"] = list(b["aux_features"]) + ["nonexistent_feature_xyz"]
    monkeypatch.setattr(analysis_lens, "FILE_ARCHETYPE_BRAIN", b)
    ac._logged_parity_warnings.clear()
    with caplog.at_level(logging.WARNING):
        result = ac.classify_file(_synthetic_code_file())
    assert result == (None, None)
    assert any("cannot compute" in r.getMessage() for r in caplog.records), (
        "expected a named parity warning naming the uncomputable feature"
    )


def test_classify_file_accumulates_drift():
    drift: dict = {}
    ac.classify_file(_synthetic_code_file(), drift=drift)
    assert drift, "expected the drift accumulator to record aux observations"
    assert set(drift).issubset(set(ap.ENGINE_FILE_AUX_FEATURES))


# ------------------------------------------------------------------ quantile canary (#3125c)
def test_drift_flags_systematic_out_of_range():
    ref = [float(i) for i in range(101)]  # trained range 0..100
    drift: dict = {}
    for _ in range(100):
        ac._record_drift(drift, "log_coding_loc", 500.0, ref)  # every value above max
    diags = ac.quantile_drift_diagnostics(drift)
    assert any("log_coding_loc" in d for d in diags), diags


def test_drift_quiet_when_in_range():
    ref = [float(i) for i in range(101)]
    drift: dict = {}
    for i in range(100):
        ac._record_drift(drift, "x", float(i), ref)
    assert ac.quantile_drift_diagnostics(drift) == []


def test_drift_ignores_small_sample():
    ref = [0.0, 1.0]
    drift: dict = {}
    for _ in range(5):  # below _DRIFT_MIN_SAMPLES
        ac._record_drift(drift, "x", 99.0, ref)
    assert ac.quantile_drift_diagnostics(drift) == []
