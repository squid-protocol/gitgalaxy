# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Graded archetype validation (#4100): per-level trust state, withholding of
INVALID levels, the shipped validation record, and the drift harness's math.

Corpus-free. The corpus-backed measurement runs in the golden-crucible job
(tests/test_golden_crucible.py::test_archetype_drift_report) and in
archetype-validation.yml on main.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

from gitgalaxy.metrics import archetype_classifier as ac
from gitgalaxy.metrics import archetype_parity as ap
from gitgalaxy.standards import analysis_lens

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import archetype_drift  # noqa: E402

RECORD = analysis_lens.ARCHETYPE_VALIDATION


def _brains():
    return copy.deepcopy(ac.loaded_brains())


def _consistent_brains():
    """The shipped brains with every cross-level label mismatch repaired."""
    b = _brains()
    b["composition_file"]["stoich_archetypes"] = list(b["function"]["cluster_names"])
    comp = list(b["composition_file"]["centroids"])
    # Keep the repo brain's width (its centroids are fixed); every input a real label.
    b["composition_repo"]["comp_archetypes"] = [
        comp[i % len(comp)] for i in range(len(b["composition_repo"]["comp_archetypes"]))
    ]
    return _rebake(b)


def _rebake(b):
    """What a refreeze would bake: provenance shas for the edited contracts."""
    for lvl, kind in (("composition_file", "file"), ("composition_repo", "repo")):
        b[lvl]["provenance"]["feature_contract_sha"] = ap.feature_contract_sha(b[lvl], kind)
    return b


def _severities(problems, level):
    return [sev for sev, _ in problems[level]]


# ------------------------------------------------------------------ shipped record
def test_record_ships_and_covers_the_loaded_brains():
    """A retrain that lands new brains must re-anchor the record
    (archetype_drift.py rebaseline) -- otherwise every level reads UNVALIDATED."""
    assert RECORD, "archetype_validation.json failed to load"
    fps = RECORD["trained"]["brain_fingerprints"]
    for lvl, brain in ac.loaded_brains().items():
        assert fps.get(lvl) == ap.brain_fingerprint(brain), (
            f"{lvl} brain changed since the validation record was cut -- run "
            "`tests/tools/archetype_drift.py rebaseline` against the engine the new brains were trained on"
        )


def test_record_has_trained_block_and_thresholds():
    t = RECORD["trained"]
    for key in ("engine_version", "engine_commit", "trained_at", "corpus"):
        assert t.get(key), f"trained.{key} missing"
    assert 0 < RECORD["thresholds"]["degraded"] < RECORD["thresholds"]["validated"] <= 1


def test_trained_baseline_exists_for_the_record():
    base = json.loads(archetype_drift.BASELINE_PATH.read_text(encoding="utf-8"))
    assert base["trained_against"]["engine_commit"] == RECORD["trained"]["engine_commit"]
    assert len(base["files"]) > 1000


def test_shipped_status_is_honest_today():
    """Pins the known state of the v2.9.0-corpus brains so a fix (or a new break)
    shows up here: the composition brain reads stale function labels (DEGRADED),
    and the repo brain reads labels the composition brain never emits (INVALID)."""
    levels = ac.validation_status()["levels"]
    assert levels["composition_repo"]["state"] == "INVALID"
    assert levels["composition_repo"]["withheld"]
    assert levels["composition_file"]["state"] == "DEGRADED"
    assert not levels["composition_file"]["withheld"]


# ------------------------------------------------------------------ structural checks
def test_consistent_brains_have_no_structural_problems():
    probs = ap.structural_problems(_consistent_brains())
    for lvl in ap.LEVELS:
        assert not [s for s in _severities(probs, lvl) if s in ("INVALID", "DEGRADED")], probs[lvl]


def test_partial_label_mismatch_degrades():
    b = _consistent_brains()
    b["composition_file"]["stoich_archetypes"][0] = "Renamed By A Retrain"
    _rebake(b)
    probs = ap.structural_problems(b)
    assert "DEGRADED" in _severities(probs, "composition_file")
    assert "INVALID" not in _severities(probs, "composition_file")


def test_disjoint_labels_invalidate():
    b = _consistent_brains()
    b["composition_repo"]["comp_archetypes"] = [f"file_cluster_{i}" for i in range(20)]
    _rebake(b)
    assert "INVALID" in _severities(ap.structural_problems(b), "composition_repo")


def test_invalid_propagates_up_the_tower():
    b = _consistent_brains()
    b["file"]["FEATURE_NAMES"] = [f for f in b["file"]["FEATURE_NAMES"] if f != "log_micro_0_pct"]
    probs = ap.structural_problems(b)
    assert "INVALID" in _severities(probs, "file")
    assert "INVALID" in _severities(probs, "composition_file")
    assert "INVALID" in _severities(probs, "composition_repo")
    assert ap.withheld_levels(b) == {"file", "composition_file", "composition_repo"}


def test_unnamed_clusters_are_a_note_not_a_downgrade():
    probs = ap.structural_problems(_consistent_brains())
    assert _severities(probs, "file") == ["NOTE"]  # shipped k=18 model is file_cluster_N


# ------------------------------------------------------------------ states
@pytest.mark.parametrize(
    "agreement,state",
    [(None, "UNVALIDATED"), (1.0, "VALIDATED"), (0.98, "VALIDATED"), (0.97, "DRIFTING"), (0.90, "DEGRADED")],
)
def test_measured_state(agreement, state):
    assert ap.measured_state(agreement, ap.DEFAULT_THRESHOLDS) == state


def _record_for(brains, agreements):
    return {
        "thresholds": dict(ap.DEFAULT_THRESHOLDS),
        "trained": {"brain_fingerprints": {k: ap.brain_fingerprint(v) for k, v in brains.items()}},
        "levels": {
            **{k: {"agreement": a} for k, a in agreements.items()},
            "composition_repo": {"inherits": "composition_file"},
        },
    }


def test_status_grades_each_level_independently():
    b = _consistent_brains()
    st = ap.validation_status(b, _record_for(b, {"function": 0.99, "file": 0.97, "composition_file": 0.90}))
    states = {k: v["state"] for k, v in st["levels"].items()}
    assert states == {
        "function": "VALIDATED",
        "file": "DRIFTING",
        "composition_file": "DEGRADED",
        "composition_repo": "DEGRADED",  # inherits composition_file
    }
    assert ap.needs_retrain(st)


def test_all_clear_needs_no_retrain():
    b = _consistent_brains()
    st = ap.validation_status(b, _record_for(b, {"function": 0.99, "file": 0.99, "composition_file": 0.97}))
    assert not ap.needs_retrain(st)


def test_changed_brain_is_unvalidated():
    b = _consistent_brains()
    rec = _record_for(b, {"function": 0.99, "file": 0.99, "composition_file": 0.99})
    b["function"]["SCALER_MEDIANS"] = [m + 1 for m in b["function"]["SCALER_MEDIANS"]]
    assert ap.validation_status(b, rec)["levels"]["function"]["state"] == "UNVALIDATED"


def test_no_record_is_unvalidated():
    st = ap.validation_status(_consistent_brains(), {})
    assert {v["state"] for v in st["levels"].values()} == {"UNVALIDATED"}


def test_provenance_edits_do_not_change_fingerprint():
    b = _brains()["composition_file"]
    fp = ap.brain_fingerprint(b)
    b["provenance"] = {"note": "edited"}
    assert ap.brain_fingerprint(b) == fp


# ------------------------------------------------------------------ withholding
def _repo_files(n=60):
    return [
        {
            "coding_loc": 200,
            "telemetry": {
                "composition_file_archetype": "Compute Cores Files",
                "network_metrics": {"pagerank_score": 0.1},
            },
        }
        for _ in range(n)
    ]


def test_invalid_repo_level_is_withheld():
    assert ac.classify_repo(_repo_files()) == (ap.WITHHELD_LABEL, 0.0)


def test_valid_repo_level_classifies(monkeypatch):
    b = _consistent_brains()
    monkeypatch.setattr(analysis_lens, "REPO_ARCHETYPE_BRAIN", b["composition_repo"])
    monkeypatch.setattr(analysis_lens, "FILE_ARCHETYPE_BRAIN", b["composition_file"])
    name, _ = ac.classify_repo(_repo_files())
    assert name not in (None, ap.WITHHELD_LABEL)


def test_withholding_ignores_the_drift_record(monkeypatch):
    """Scan output must not depend on when automation last refreshed the record."""
    before = ac.withheld_levels()
    monkeypatch.setattr(analysis_lens, "ARCHETYPE_VALIDATION", {})
    assert ac.withheld_levels() == before


# ------------------------------------------------------------------ drift harness
def _f(file, comp, funcs, z=0.0):
    return {"file": file, "composition": comp, "composition_z": z, "functions": funcs}


def test_measure_counts_relabels_not_count_changes():
    base = {
        "repo": "R",
        "files": {
            "a": _f("f1", "C1", {"X": 4}),
            "b": _f("f1", "C1", {"X": 2, "Y": 2}),
            "gone": _f("f1", "C1", {"X": 1}),
        },
    }
    cur = {
        "repo": "R2",
        "files": {
            "a": _f("f1", "C1", {"X": 6}),  # +2 extracted functions: not a relabel
            "b": _f("f2", "C2", {"X": 1, "Y": 3}),  # one function relabelled X -> Y
            "new": _f("f9", "C9", {"Z": 5}),
        },
    }
    r = archetype_drift.measure(base, cur, ap.DEFAULT_THRESHOLDS)
    assert r["coverage"] == pytest.approx(2 / 3, abs=1e-4)
    assert r["levels"]["function"]["agreement"] == pytest.approx(1 - 1 / 8, abs=1e-4)
    assert r["levels"]["file"]["agreement"] == 0.5
    assert r["levels"]["composition_file"]["agreement"] == 0.5
    assert r["levels"]["composition_repo"]["crucible_label"] == {"trained": "R", "current": "R2"}


def test_extract_skips_non_code_files():
    audit = {
        archetype_drift.PARSED: {
            "g": {
                "Files": {
                    "doc.md": {"3. Architectural Profile": {"Coding LOC": 0}},
                    "x.c": {
                        "3. Architectural Profile": {
                            "Coding LOC": 10,
                            "Repository Archetype": "f",
                            "Composition Archetype": "c",
                            "Function Archetype Mix": {"X": 1},
                        }
                    },
                }
            }
        },
        archetype_drift.GLOBAL: {archetype_drift.REPO_KEY: "R"},
    }
    out = archetype_drift.extract(audit)
    assert list(out["files"]) == ["x.c"] and out["repo"] == "R"


def test_record_only_moves_on_real_change():
    b = ac.loaded_brains()
    old = _record_for(b, {"function": 0.990, "file": 0.990, "composition_file": 0.990})
    old["measured"] = {"engine_commit": "x"}
    tiny = json.loads(json.dumps(old))
    tiny["levels"]["function"]["agreement"] = 0.989
    assert not archetype_drift.record_moved(old, tiny)
    big = json.loads(json.dumps(old))
    big["levels"]["function"]["agreement"] = 0.960
    assert archetype_drift.record_moved(old, big)


def test_reports_render():
    st = ac.validation_status()
    md = archetype_drift.render_status(st)
    assert "composition_repo" in md and "INVALID" in md
    assert "Clearing it" in archetype_drift.render_issue(st)
    assert len(ap.summary_lines(st)) == len(ap.LEVELS)
