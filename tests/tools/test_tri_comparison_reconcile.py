"""Unit tests for tri_comparison_reconcile.reconcile_symbols -- in particular the #2359
line-proximity function pairing that replaced rank pairing for repeated names.

tri_comparison_reconcile only ever reads .name/.line/.args off occurrence objects and
.gg_funcs/.ts_funcs/.ctags_funcs/.file_path off result objects (it duck-types on purpose so it
imports without tree-sitter-language-pack -- see its own module docstring), so these tests build
tiny stand-ins rather than importing tri_comparison_gatherer's real dataclasses.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tri_comparison_reconcile as R  # noqa: E402 # type: ignore


@dataclass
class Occ:
    name: str
    line: int | None
    args: int | None


@dataclass
class FR:
    file_path: str = "f"
    gg_funcs: list = field(default_factory=list)
    gg_classes: list = field(default_factory=list)
    ts_funcs: list = field(default_factory=list)
    ts_classes: list = field(default_factory=list)
    ctags_funcs: list = field(default_factory=list)
    ctags_classes: list = field(default_factory=list)


def _reconcile(gg, ts, ctags=None):
    tools = ("gitgalaxy", "tree_sitter") if ctags is None else ("gitgalaxy", "tree_sitter", "ctags")
    fr = FR(gg_funcs=gg, ts_funcs=ts, ctags_funcs=ctags or [])
    recall, precision, args, groups = R.reconcile_symbols([fr], "function", tools, "csharp")
    return recall, precision, args, groups


def _rates(scores):
    return {t: (m.matched_consensus, m.total_slots) for t, m in scores.items()}


def _force_rank_pairing(monkeypatch):
    monkeypatch.setattr(R, "_name_wants_line_pairing", lambda *a, **k: False)


# --------------------------------------------------------------------------------------------
# The #2359 regression: one tool missing an occurrence in the MIDDLE of a repeated name


def test_missing_middle_occurrence_produces_no_spurious_args_discrepancy():
    # gg finds foo x3 (1/2/3 args); ts misses the middle one, finds x2 (1/3 args).
    gg = [Occ("foo", 10, 1), Occ("foo", 50, 2), Occ("foo", 90, 3)]
    ts = [Occ("foo", 11, 1), Occ("foo", 91, 3)]
    _, _, args, groups = _reconcile(gg, ts)

    # existence: gg found one more than ts -- exactly one existence discrepancy, gg-only.
    assert [g.metric for g in groups] == ["existence"]
    assert groups[0].agreeing_tools == frozenset({"gitgalaxy"})
    assert groups[0].total_occurrences == 1
    # no args discrepancy at all -- the two real pairs (10<->11, 90<->91) agree.
    assert not [g for g in groups if g.metric == "args"]
    # both real pairs were actually compared and matched.
    assert _rates(args) == {"gitgalaxy": (2, 2), "tree_sitter": (2, 2)}


def test_missing_middle_leaves_existence_metrics_identical_to_rank_pairing(monkeypatch):
    gg = [Occ("foo", 10, 1), Occ("foo", 50, 2), Occ("foo", 90, 3)]
    ts = [Occ("foo", 11, 1), Occ("foo", 91, 3)]

    recall_line, precision_line, _, groups_line = _reconcile(gg, ts)

    _force_rank_pairing(monkeypatch)
    recall_rank, precision_rank, _, groups_rank = _reconcile(gg, ts)

    assert _rates(recall_line) == _rates(recall_rank)
    assert _rates(precision_line) == _rates(precision_rank)
    # same discrepancy SHAPE and count -- only the example line attribution differs.
    assert [(g.metric, g.agreeing_tools, g.total_occurrences) for g in groups_line] == [
        (g.metric, g.agreeing_tools, g.total_occurrences) for g in groups_rank
    ]


def test_overload_set_with_one_tool_missing_one_overload_pairs_cleanly():
    # 4 overloads, args 1/6/4/5. ctags misses the 2nd; its remaining reads are +1 line (its
    # usual anchor offset). Rank pairing would compare ctags overload#3 against gg overload#2.
    gg = [Occ("F", 10, 1), Occ("F", 30, 6), Occ("F", 50, 4), Occ("F", 70, 5)]
    ts = [Occ("F", 10, 1), Occ("F", 30, 6), Occ("F", 50, 4), Occ("F", 70, 5)]
    ctags = [Occ("F", 11, 1), Occ("F", 51, 4), Occ("F", 71, 5)]
    _, _, args, groups = _reconcile(gg, ts, ctags)

    assert not [g for g in groups if g.metric == "args"]
    assert [g.metric for g in groups] == ["existence"]
    assert groups[0].dissenting_tools == frozenset({"ctags"})
    assert _rates(args) == {"gitgalaxy": (3, 3), "tree_sitter": (3, 3), "ctags": (3, 3)}


# --------------------------------------------------------------------------------------------
# The belt-and-braces args line-spread guard


def test_far_apart_same_name_single_occurrence_skips_args_comparison():
    # one `g` each, 5000 lines apart, different arg counts. Both readers agree `g` exists
    # (as today), but they're plainly not the same function -- args must not be compared.
    gg = [Occ("g", 10, 1)]
    ts = [Occ("g", 5000, 2)]
    _, _, args, groups = _reconcile(gg, ts)

    assert groups == []  # existence consensus, unchanged from rank pairing
    assert _rates(args) == {"gitgalaxy": (0, 0), "tree_sitter": (0, 0)}


def test_close_occurrences_within_spread_still_compare_args():
    # a real +1 ctags-style offset must NOT trip the guard.
    gg = [Occ("k", 100, 2)]
    ts = [Occ("k", 101, 3)]
    _, _, args, groups = _reconcile(gg, ts)

    assert _rates(args) == {"gitgalaxy": (0, 1), "tree_sitter": (0, 1)}  # compared, disagreed
    assert [g.metric for g in groups] == ["args"]


# --------------------------------------------------------------------------------------------
# The common case must be untouched


def test_single_occurrence_name_unchanged(monkeypatch):
    gg = [Occ("h", 10, 2)]
    ts = [Occ("h", 10, 2)]
    line_result = _reconcile(gg, ts)

    _force_rank_pairing(monkeypatch)
    rank_result = _reconcile(gg, ts)

    for line_scores, rank_scores in zip(line_result[:3], rank_result[:3], strict=True):
        assert _rates(line_scores) == _rates(rank_scores)


def test_classes_never_use_line_pairing():
    # gg classes carry no line; class reconciliation must stay name-multiset (rank) only.
    occ_by_tool = {"gitgalaxy": [Occ("C", None, None), Occ("C", None, None)]}
    assert R._name_wants_line_pairing(occ_by_tool, "class") is False


def test_all_agree_no_discrepancies():
    gg = [Occ("a", 1, 0), Occ("b", 10, 2), Occ("b", 40, 2)]
    ts = [Occ("a", 1, 0), Occ("b", 10, 2), Occ("b", 41, 2)]
    recall, _, args, groups = _reconcile(gg, ts)

    assert groups == []
    assert _rates(recall) == {"gitgalaxy": (3, 3), "tree_sitter": (3, 3)}
    assert _rates(args) == {"gitgalaxy": (3, 3), "tree_sitter": (3, 3)}
