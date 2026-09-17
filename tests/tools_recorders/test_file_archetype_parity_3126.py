# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""FILE archetype brain parity gate (#3126).

`_classify_file_archetype` is the Phase 12.0 path #3061 made the primary file
archetype classifier. It masked brain/engine mismatches two ways -- a distance
loop over `range(min(len(vec), len(cen)))`, and scaler lookups of the form
`med[i] if i < len(med) else 0.0` -- so a brain whose centroids or scaler
arrays disagreed with its own FEATURE_NAMES produced a *confident* label off a
partial vector. `signal_processor` does the opposite for its own archetype
paths (warn once, return "Unclassified"), a posture established by #1157/#1158
after the v2.8.0 three-way feature-space incident; this path did not inherit
it. A renamed trainer feature was worse still: it hit a bare `else: v = 0.0`,
kept the vector length correct, and so evaded every length check as an
invisible dead input.

The fix validates the brain's internal consistency once in `_prep_file_brain`
and refuses an inconsistent brain outright. These tests pin both halves: the
shipped brain must pass, and each way of corrupting it must be refused rather
than classified.
"""

import copy
import logging

import pytest

from gitgalaxy.recorders.record_keeper import RecordKeeper, _file_feature_kind
from gitgalaxy.standards.analysis_lens import GENERAL_FILE_INFERENCE_MODEL, RECORDING_SCHEMAS

_SIGNAL_SCHEMA = RECORDING_SCHEMAS.get("SIGNAL_SCHEMA", [])


def _archetype_key(brain):
    return next(k for k in brain if k.startswith("ARCHETYPES_K"))


def _keeper():
    """A RecordKeeper with just enough state for the archetype path."""
    keeper = RecordKeeper.__new__(RecordKeeper)
    keeper.logger = logging.getLogger("test-record-keeper")
    keeper.SIGNAL_SCHEMA = _SIGNAL_SCHEMA
    return keeper


def _prep_with(monkeypatch, brain):
    keeper = _keeper()
    monkeypatch.setattr("gitgalaxy.recorders.record_keeper.GENERAL_FILE_INFERENCE_MODEL", brain)
    keeper._prep_file_brain()
    return keeper


# ==============================================================================
# The shipped brain must be internally consistent -- this is the regression
# guard for the artifact itself, not just the code that reads it.
# ==============================================================================
def test_shipped_file_brain_is_internally_consistent():
    b = GENERAL_FILE_INFERENCE_MODEL
    n = len(b["FEATURE_NAMES"])
    assert n > 0
    assert len(b["SCALER_MEDIANS"]) == n
    assert len(b["SCALER_IQRS"]) == n
    assert len(b.get("FEATURE_WEIGHTS", [1.0] * n)) == n
    centroids = list(b[_archetype_key(b)].values())
    assert {len(c) for c in centroids} == {n}, "every centroid must span FEATURE_NAMES exactly"


def test_shipped_file_brain_features_are_all_computable():
    """No FEATURE_NAME may fall through to what used to be a silent 0.0."""
    unknown = [fn for fn in GENERAL_FILE_INFERENCE_MODEL["FEATURE_NAMES"] if _file_feature_kind(fn) is None]
    assert unknown == [], f"the engine cannot compute these features: {unknown}"


def test_shipped_file_brain_loads(monkeypatch):
    keeper = _prep_with(monkeypatch, GENERAL_FILE_INFERENCE_MODEL)
    assert keeper._file_brain is not None, "the shipped brain must still classify"
    assert len(keeper._file_brain["FEATURE_NAMES"]) == len(GENERAL_FILE_INFERENCE_MODEL["FEATURE_NAMES"])


# ==============================================================================
# Each corruption must be REFUSED, not classified over the overlap.
# ==============================================================================
@pytest.mark.parametrize(
    "corrupt",
    [
        pytest.param(lambda b: b.__setitem__("SCALER_MEDIANS", b["SCALER_MEDIANS"][:-3]), id="short-medians"),
        pytest.param(lambda b: b.__setitem__("SCALER_IQRS", b["SCALER_IQRS"][:-1]), id="short-iqrs"),
        pytest.param(
            lambda b: b.__setitem__("FEATURE_WEIGHTS", [1.0] * (len(b["FEATURE_NAMES"]) - 5)),
            id="short-weights",
        ),
        pytest.param(
            lambda b: b["FEATURE_NAMES"].append("log_density_a_feature_the_trainer_invented"),
            id="extra-feature-name-without-scaler-growth",
        ),
        pytest.param(
            lambda b: b["FEATURE_NAMES"].__setitem__(0, "some_renamed_feature"),
            id="renamed-feature-the-engine-cannot-compute",
        ),
    ],
)
def test_inconsistent_brain_is_refused(monkeypatch, caplog, corrupt):
    brain = copy.deepcopy(dict(GENERAL_FILE_INFERENCE_MODEL))
    brain["FEATURE_NAMES"] = list(brain["FEATURE_NAMES"])
    corrupt(brain)
    with caplog.at_level(logging.WARNING):
        keeper = _prep_with(monkeypatch, brain)
    assert keeper._file_brain is None, "an inconsistent brain must not classify"
    assert any("#3126" in r.message or "inconsistent" in r.message for r in caplog.records), (
        "refusal must be diagnosed, not silent"
    )


def test_truncated_centroid_is_refused(monkeypatch, caplog):
    brain = copy.deepcopy(dict(GENERAL_FILE_INFERENCE_MODEL))
    ak = _archetype_key(brain)
    brain[ak] = dict(brain[ak])
    first = next(iter(brain[ak]))
    brain[ak][first] = brain[ak][first][:-4]
    with caplog.at_level(logging.WARNING):
        keeper = _prep_with(monkeypatch, brain)
    assert keeper._file_brain is None, "a centroid shorter than FEATURE_NAMES must not classify"
    assert any("centroid dims" in r.message for r in caplog.records)


def test_refused_brain_yields_no_label_rather_than_a_wrong_one(monkeypatch):
    """The caller keeps its fallback label -- honest absence, the
    signal_processor posture -- instead of a confident partial-vector answer."""
    brain = copy.deepcopy(dict(GENERAL_FILE_INFERENCE_MODEL))
    brain["SCALER_MEDIANS"] = brain["SCALER_MEDIANS"][:-3]
    keeper = _prep_with(monkeypatch, brain)
    ctx = {"coding_loc": 120.0, "micro": {}, "precalc": {}}
    assert keeper._classify_file_archetype(ctx, [0] * len(_SIGNAL_SCHEMA)) is None


def test_consistent_brain_still_classifies(monkeypatch):
    """The fix must not change behaviour for the brain that actually ships."""
    keeper = _prep_with(monkeypatch, GENERAL_FILE_INFERENCE_MODEL)
    keeper._file_sig_idx = {s: i for i, s in enumerate(_SIGNAL_SCHEMA)}
    ctx = {"coding_loc": 240.0, "micro": {1: 40.0}, "precalc": {"function_count": 12.0}}
    label = keeper._classify_file_archetype(ctx, [3] * len(_SIGNAL_SCHEMA))
    assert label in GENERAL_FILE_INFERENCE_MODEL[_archetype_key(GENERAL_FILE_INFERENCE_MODEL)]


@pytest.mark.parametrize(
    ("feature", "kind"),
    [
        ("log_coding_loc", "coding_loc"),
        ("func_z_max", "zstat"),
        ("pct_z_above_15", "zstat"),
        ("log_micro_7_pct", "micro"),
        ("log_density_branch", "density"),
        ("log_function_count", "precalc"),
        ("log_micro_notanumber_pct", None),
        ("encapsulation_ratio", None),
        ("", None),
    ],
)
def test_feature_kind_classification(feature, kind):
    assert _file_feature_kind(feature) == kind
