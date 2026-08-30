"""Unit tests for tri_comparison_chart._ledger_credited_lone_claimant_winner.

Regression coverage for the badge gap this closes: a language whose non-gitgalaxy tools are
"available" (they cover OTHER panels for the same language) but structurally have zero real
claims for THIS specific panel -- ctags is available for sqlite (it covers the class panel) but
SQLite has no CREATE FUNCTION/PROCEDURE syntax, so ctags's function-kind claim count is always 0.
`_winner_or_tie` needs 2+ tools with real (non-None) `rate_pct` data and returns None here;
`_manual_verification_winner`'s bypass is deliberately restricted to whole-language 1-tool cases
(func/class precision's real 0/N must otherwise stay visible, per that function's own docstring)
and doesn't apply either. This function is the narrow, ledger-validated-only third path -- gated
on an actual investigated `credit_tools` verdict, not a static per-language flag, so it clears
the same "we know who's actually right" bar a real cross-tool win or a full manual verification
already clears.

Per this repo's testing conventions (tests/ has no __init__.py anywhere): the sibling tool
directory is put on sys.path and the modules are imported as bare top-level names, never as
`tests.tools.x`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tri_comparison_ledger as ledger_mod  # noqa: E402
from tri_comparison_chart import _ledger_credited_lone_claimant_winner  # noqa: E402
from tri_comparison_reconcile import MetricScore  # noqa: E402


def _write_ledger(tmp_path, shape_key, *, status="validated", credit=(), agreeing=("gitgalaxy",)):
    ledger = {
        "entries": {
            shape_key: {
                "language": "sqlite",
                "symbol_type": "function",
                "metric": "existence",
                "status": status,
                "agreeing_tools": list(agreeing),
                "dissenting_tools": ["ctags"],
                "still_reproduces": True,
                "credit_tools": list(credit),
                "debit_tools": [],
            }
        }
    }
    path = tmp_path / "ledger.json"
    ledger_mod.save_ledger(ledger, path)
    return path


def _scores(**kw):
    """kw maps tool -> (matched_consensus, total_slots). A tool with total_slots=0 gets a None
    rate_pct (MetricScore.rate_pct returns None on a 0 denominator) -- the exact shape a tool
    with zero real claims produces."""
    return {t: MetricScore(tool=t, matched_consensus=mc, total_slots=ts) for t, (mc, ts) in kw.items()}


def test_awards_gitgalaxy_when_sole_real_data_and_credited(tmp_path):
    """The confirmed sqlite case: gitgalaxy has real data (734/734), ctags is "available" for
    the language but made zero function claims at all (total_slots=0 -> rate_pct is None)."""
    path = _write_ledger(tmp_path, "sqlite/function/existence/agree[gitgalaxy]_vs[ctags]", credit=["gitgalaxy"])
    scores = _scores(gitgalaxy=(734, 734), ctags=(0, 0))
    winner = _ledger_credited_lone_claimant_winner(
        scores, ("gitgalaxy", "ctags"), "sqlite", "function", "existence", ledger_path=path
    )
    assert winner == "gitgalaxy"


def test_no_award_without_a_credit(tmp_path):
    """A validated shape with NO credit (a genuine 'different question, nobody's right or
    wrong' verdict) must not earn a badge -- validated alone isn't the same claim as credited."""
    path = _write_ledger(tmp_path, "sqlite/function/existence/agree[gitgalaxy]_vs[ctags]", credit=[])
    scores = _scores(gitgalaxy=(734, 734), ctags=(0, 0))
    winner = _ledger_credited_lone_claimant_winner(
        scores, ("gitgalaxy", "ctags"), "sqlite", "function", "existence", ledger_path=path
    )
    assert winner is None


def test_no_award_when_shape_still_unvalidated(tmp_path):
    """A credit on an unvalidated shape shouldn't be possible in a real ledger, but this
    function must not trust `credit_tools` without also checking `status == "validated"`."""
    path = _write_ledger(
        tmp_path, "sqlite/function/existence/agree[gitgalaxy]_vs[ctags]", status="unvalidated", credit=["gitgalaxy"]
    )
    scores = _scores(gitgalaxy=(734, 734), ctags=(0, 0))
    winner = _ledger_credited_lone_claimant_winner(
        scores, ("gitgalaxy", "ctags"), "sqlite", "function", "existence", ledger_path=path
    )
    assert winner is None


def test_no_award_when_a_second_tool_has_real_data(tmp_path):
    """This path only ever applies when GitGalaxy is the ONE tool with real data -- if ctags
    also has real claims (even a small number), that's a genuine 2-tool comparison
    `_winner_or_tie` should resolve on its own; this function must defer to it, not race it."""
    path = _write_ledger(tmp_path, "sqlite/function/existence/agree[gitgalaxy]_vs[ctags]", credit=["gitgalaxy"])
    scores = _scores(gitgalaxy=(734, 734), ctags=(5, 5))
    winner = _ledger_credited_lone_claimant_winner(
        scores, ("gitgalaxy", "ctags"), "sqlite", "function", "existence", ledger_path=path
    )
    assert winner is None


def test_no_award_when_gitgalaxy_itself_lacks_real_data(tmp_path):
    """The lone real-data tool must be GITGALAXY specifically -- this mechanism only ever
    awards GitGalaxy's own badge (mirrors _manual_verification_winner's own contract)."""
    path = _write_ledger(
        tmp_path,
        "sqlite/function/existence/agree[ctags]_vs[gitgalaxy]",
        credit=["ctags"],
        agreeing=["ctags"],
    )
    scores = _scores(gitgalaxy=(0, 0), ctags=(12, 12))
    winner = _ledger_credited_lone_claimant_winner(
        scores, ("gitgalaxy", "ctags"), "sqlite", "function", "existence", ledger_path=path
    )
    assert winner is None


def test_no_award_when_credited_shape_is_a_different_language_or_metric(tmp_path):
    """A credited shape for a DIFFERENT (language, symbol_type, metric) triple must not leak
    into this one -- e.g. sqlite's class shape being credited shouldn't award the function
    panel's badge too."""
    path = _write_ledger(tmp_path, "sqlite/class/existence/agree[gitgalaxy]_vs[ctags]", credit=["gitgalaxy"])
    ledger = ledger_mod.load_ledger(path)
    ledger["entries"]["sqlite/class/existence/agree[gitgalaxy]_vs[ctags]"]["symbol_type"] = "class"
    ledger_mod.save_ledger(ledger, path)
    scores = _scores(gitgalaxy=(734, 734), ctags=(0, 0))
    winner = _ledger_credited_lone_claimant_winner(
        scores, ("gitgalaxy", "ctags"), "sqlite", "function", "existence", ledger_path=path
    )
    assert winner is None


def test_no_award_when_credited_shape_has_a_second_agreeing_tool(tmp_path):
    """`agreeing_tools` must be EXACTLY ["gitgalaxy"] -- a credited shape where gitgalaxy shares
    agreement with another tool doesn't establish that gitgalaxy's claims are the sqlite corpus's
    complete, sole answer for this panel (there could be a real second tool with data elsewhere
    this function never sees)."""
    path = _write_ledger(
        tmp_path,
        "sqlite/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]",
        credit=["gitgalaxy"],
        agreeing=["gitgalaxy", "tree_sitter"],
    )
    scores = _scores(gitgalaxy=(734, 734), ctags=(0, 0))
    winner = _ledger_credited_lone_claimant_winner(
        scores, ("gitgalaxy", "ctags"), "sqlite", "function", "existence", ledger_path=path
    )
    assert winner is None
