# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""Unit coverage for the detection-accuracy harness itself (#3117).

The harness's *measurement* runs in CI against the pinned language-crucible
corpus (detection-accuracy-audit.yml). These tests cover the parts that need
no corpus -- the labelling rules, which are the harness's own trustworthiness
-- plus a corpus-gated smoke test that skips when the checkout is absent.

A labelling bug here silently invalidates the number, so the label table gets
the same treatment as any other contract in this repo.
"""

import pathlib
import sys

import pytest

_TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import detection_accuracy_audit as audit  # noqa: E402

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG  # noqa: E402


def test_explicit_labels_only_cover_contested_extensions():
    """An explicit label for an UNcontested extension would be dead weight --
    the auto path already labels those, and a stale entry here would silently
    diverge from it."""
    contested = set(LENS_CONFIG["COLLISION_FREQUENCIES"])
    stray = sorted({ext for ext, _group in audit._EXPLICIT_LABELS if ext not in contested})
    assert stray == [], f"explicit labels for non-contested extensions: {stray}"


def test_explicit_labels_name_real_languages():
    """Every asserted label must be a language the registry can actually
    return, or the harness scores against an unreachable expectation."""
    bad = sorted(
        {lang for lang in audit._EXPLICIT_LABELS.values() if lang is not None and lang not in LANGUAGE_DEFINITIONS}
    )
    assert bad == [], f"explicit labels naming unknown languages: {bad}"


def test_single_claimant_map_excludes_contested_and_template_extensions():
    by_ext = audit._single_claimant_extensions()
    contested = set(LENS_CONFIG["COLLISION_FREQUENCIES"])
    assert not (set(by_ext) & contested), "a contested extension cannot be auto-labelled"
    assert not (set(by_ext) & audit._TEMPLATE_EXTENSIONS), "a template extension cannot be auto-labelled"
    # Sanity: the map must still be substantial, or the harness is measuring nothing.
    assert len(by_ext) > 40


def test_single_claimant_map_is_genuinely_single_claimant():
    by_ext = audit._single_claimant_extensions()
    for ext, lang in by_ext.items():
        claimants = [k for k, d in LANGUAGE_DEFINITIONS.items() if ext in d.get("extensions", [])]
        assert claimants == [lang], f"{ext} maps to {lang} but is claimed by {claimants}"


def test_unscored_labels_are_deliberate():
    """A None label means "no defensible answer exists", not "TODO". Each one
    should be rare and documented in the table's comments."""
    unscored = [key for key, lang in audit._EXPLICIT_LABELS.items() if lang is None]
    assert len(unscored) <= 5, f"too many unscored explicit labels to be deliberate: {unscored}"


@pytest.mark.parametrize("required", ["scored", "accuracy", "explicit_accuracy", "tier_5_conflicts", "languages"])
def test_committed_baseline_has_the_gated_fields(required):
    baseline = audit._load_baseline()
    if baseline is None:
        pytest.skip("no committed baseline yet")
    assert required in baseline, f"baseline is missing the gated field {required!r}"


def test_harness_runs_against_the_corpus_when_present():
    """Corpus-gated smoke test: the measurement must complete and stay at or
    above the committed baseline. CI runs the real gate; this catches a harness
    that crashes or silently scores nothing on a developer machine."""
    try:
        audit._corpus_root()
    except SystemExit:
        pytest.skip("language-crucible corpus not available")

    measured = audit.measure()
    assert measured["scored"] > 1000, "the harness scored implausibly few files"
    assert measured["explicit_scored"] > 100, "the independent-ground-truth subset is too small to mean anything"

    baseline = audit._load_baseline()
    if baseline is not None:
        assert audit._compare(measured, baseline) == []


# ==============================================================================
# THE OBJECTIVE: 1.0 on determinable files, 1.0 rejection of ambiguous ones
# ==============================================================================
def test_ambiguous_files_are_keyed_by_path_with_a_stated_reason():
    """Ambiguity is a property of the individual file, so the label is a path,
    not an extension or a directory -- and each carries why."""
    for rel, reason in audit._AMBIGUOUS_FILES.items():
        assert not rel.startswith("/"), f"{rel} must be corpus-relative"
        assert "." in rel.rsplit("/", 1)[-1] or "/" in rel, f"{rel} does not look like a file path"
        assert len(reason) > 20, f"{rel} needs a stated reason, got {reason!r}"


def test_ambiguous_class_is_small_and_deliberate():
    """A growing ambiguous set is how objective 1 gets gamed: reclassify an
    inconvenient file as 'ambiguous' and the determinable rate goes up. Keep it
    small enough that each addition is a visible, reviewable decision."""
    assert len(audit._AMBIGUOUS_FILES) <= 10, (
        f"{len(audit._AMBIGUOUS_FILES)} ambiguous files is enough to hide a real defect; "
        "each one must be a defended claim that NO single language is correct"
    )


def test_objective_metrics_are_present_and_gated():
    baseline = audit._load_baseline()
    if baseline is None:
        pytest.skip("no committed baseline yet")
    for key in ("determinable_accuracy", "determinable_scored", "ambiguous_rejection_rate", "ambiguous_total"):
        assert key in baseline, f"the objective metric {key!r} must be baselined so CI gates it"


def test_a_confident_verdict_on_an_ambiguous_file_is_a_failure():
    """The inverted scoring must actually invert: for an ambiguous file a
    refusal passes and a language verdict fails. Without this, the harness
    scores its own objective backwards -- it used to count the polyglot's
    correct refusal as an error."""
    try:
        audit._corpus_root()
    except SystemExit:
        pytest.skip("language-crucible corpus not available")

    measured = audit.measure()
    assert measured["ambiguous_total"] == len(audit._AMBIGUOUS_FILES)
    # Every ambiguous file the engine answered confidently appears as an error
    # whose expectation is a refusal, never as a silent pass.
    confident = [e for e in measured["_errors"] if e["expected"] == "(refusal)"]
    assert len(confident) == measured["ambiguous_total"] - measured["ambiguous_rejected"]


def test_determinable_denominator_excludes_ambiguous_files():
    """Otherwise the two objectives are not independent and one can be traded
    against the other."""
    try:
        audit._corpus_root()
    except SystemExit:
        pytest.skip("language-crucible corpus not available")

    measured = audit.measure()
    assert measured["determinable_scored"] == measured["scored"]
    assert measured["ambiguous_total"] not in (None,)
    # an ambiguous file is scored by neither the auto nor the explicit subset
    assert measured["auto_scored"] + measured["explicit_scored"] == measured["determinable_scored"]
