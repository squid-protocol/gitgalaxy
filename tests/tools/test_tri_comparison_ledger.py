"""Unit tests for tri_comparison_ledger.apply_verified_adjustments' geometry guard.

Regression coverage for the chart bug where a `debit_tools` entry naming a tool that never
earned cross-tool corroboration on a shape (a lone claimant, or a tool on the dissenting/absent
side) drove GitGalaxy-vs-ctags precision numerators negative -- m4 rendered `-73/79`, scheme
`-42/92` -- and the mirror-image bad `credit_tools` that gave zig an impossible 100.27% class
precision.

Per this repo's testing conventions (tests/ has no __init__.py anywhere): the sibling tool
directory is put on sys.path and the modules are imported as bare top-level names, never as
`tests.tools.x`.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tri_comparison_ledger as ledger_mod  # noqa: E402
from tri_comparison_reconcile import DiscrepancyGroup, MetricScore  # noqa: E402


def _group(agreeing, dissenting, *, occ=10, metric="existence", symbol_type="function", lang="lang"):
    return DiscrepancyGroup(
        language=lang,
        symbol_type=symbol_type,
        metric=metric,
        agreeing_tools=frozenset(agreeing),
        dissenting_tools=frozenset(dissenting),
        total_occurrences=occ,
    )


def _write_ledger(tmp_path, shape_key, *, credit=(), debit=(), status="validated"):
    ledger = {
        "entries": {
            shape_key: {
                "language": "lang",
                "symbol_type": "function",
                "metric": "existence",
                "status": status,
                "still_reproduces": True,
                "credit_tools": list(credit),
                "debit_tools": list(debit),
            }
        }
    }
    path = tmp_path / "ledger.json"
    ledger_mod.save_ledger(ledger, path)
    return path


def _scores(**kw):
    return {t: MetricScore(tool=t, matched_consensus=mc, total_slots=ts) for t, (mc, ts) in kw.items()}


def test_valid_credit_on_lone_claimant_bumps_numerator(tmp_path):
    g = _group(["gitgalaxy"], ["ctags", "tree_sitter"], occ=4)
    path = _write_ledger(tmp_path, g.shape_key, credit=["gitgalaxy"])
    scores = _scores(gitgalaxy=(1726, 1730))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["gitgalaxy"].matched_consensus == 1730  # 1726 + 4


def test_valid_debit_on_two_tool_agreement_lowers_numerator(tmp_path):
    g = _group(["ctags", "tree_sitter"], ["gitgalaxy"], occ=3)
    path = _write_ledger(tmp_path, g.shape_key, debit=["ctags", "tree_sitter"])
    scores = _scores(ctags=(100, 100), tree_sitter=(200, 200))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["ctags"].matched_consensus == 97
    assert scores["tree_sitter"].matched_consensus == 197


def test_debit_on_lone_claimant_is_skipped_not_applied(tmp_path, capsys):
    # The m4 shape: ctags claims 76 functions gitgalaxy rejects; a human validates ctags wrong.
    # ctags was never corroborated on those slots, so its numerator must not move (and must not
    # go negative).
    g = _group(["ctags"], ["gitgalaxy"], occ=76)
    path = _write_ledger(tmp_path, g.shape_key, debit=["ctags"])
    scores = _scores(ctags=(3, 79))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["ctags"].matched_consensus == 3
    assert scores["ctags"].rate_pct == pytest.approx(3.797, abs=1e-3)
    assert "ignoring malformed debit_tools=[ctags]" in capsys.readouterr().err


def test_debit_on_dissenting_side_tool_is_skipped(tmp_path, capsys):
    # The scheme shape: agree[gitgalaxy]_vs[ctags], someone put ctags in debit_tools even though
    # ctags made no claim on this shape at all.
    g = _group(["gitgalaxy"], ["ctags"], occ=50)
    path = _write_ledger(tmp_path, g.shape_key, credit=["gitgalaxy"], debit=["ctags"])
    scores = _scores(gitgalaxy=(8, 58), ctags=(8, 92))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["gitgalaxy"].matched_consensus == 58  # valid lone-claimant credit still applied
    assert scores["ctags"].matched_consensus == 8  # bad debit skipped -- not -42
    assert "ignoring malformed debit_tools=[ctags]" in capsys.readouterr().err


def test_credit_on_two_tool_agreement_is_skipped(tmp_path, capsys):
    # Crediting a tool that already shares a 2+-tool agreement would double-count -- reconcile
    # already put those occurrences in its numerator.
    g = _group(["ctags", "tree_sitter"], ["gitgalaxy"], occ=3)
    path = _write_ledger(tmp_path, g.shape_key, credit=["ctags", "tree_sitter"])
    scores = _scores(ctags=(100, 100), tree_sitter=(200, 200))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["ctags"].matched_consensus == 100
    assert scores["tree_sitter"].matched_consensus == 200
    assert "ignoring malformed credit_tools" in capsys.readouterr().err


def test_credit_on_absent_tool_is_skipped(tmp_path, capsys):
    # The zig class shape: agree[tree_sitter]_vs[gitgalaxy] with credit_tools=[gitgalaxy] gave
    # gitgalaxy matched_consensus > total_slots (the impossible 100.27%).
    g = _group(["tree_sitter"], ["gitgalaxy"], occ=2, symbol_type="class")
    path = _write_ledger(tmp_path, g.shape_key, credit=["gitgalaxy"])
    scores = _scores(gitgalaxy=(728, 729))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["gitgalaxy"].matched_consensus == 728
    assert scores["gitgalaxy"].rate_pct <= 100.0
    assert "ignoring malformed credit_tools=[gitgalaxy]" in capsys.readouterr().err


def test_non_existence_group_is_ignored(tmp_path):
    g = _group(["gitgalaxy"], ["ctags"], occ=5, metric="args")
    path = _write_ledger(tmp_path, g.shape_key, credit=["gitgalaxy"])
    scores = _scores(gitgalaxy=(10, 20))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["gitgalaxy"].matched_consensus == 10


def test_unvalidated_entry_is_ignored(tmp_path):
    g = _group(["gitgalaxy"], ["ctags"], occ=5)
    path = _write_ledger(tmp_path, g.shape_key, credit=["gitgalaxy"], status="pending")
    scores = _scores(gitgalaxy=(10, 20))

    ledger_mod.apply_verified_adjustments(scores, [g], path=path)

    assert scores["gitgalaxy"].matched_consensus == 10
