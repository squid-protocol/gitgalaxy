"""#4047 [c:0f9790f1]: fast mode (the session JVM) is the mutation default only where `mutation.py compare` has
judged it against `--full`. The comparison itself, and the scope that was never compared: entry runs."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mutation as mu

CASES = Path(__file__).resolve().parents[1] / "equivalence"


def _run(mode, verdicts):
    return {"mode": mode, "results": [{"id": i, "op": "ROR", "line": 1, "verdict": v, "seconds": 2}
                                      for i, v in verdicts.items()]}  # fmt: skip


def test_compare_counts_caught_and_timeout_as_one_verdict():
    full = _run("full", {"a": "killed", "b": "survived", "c": "timeout", "d": "stillborn"})
    fast = _run("fast+one-jvm", {"a": "timeout", "b": "survived", "c": "killed", "d": "stillborn"})
    r = mu.compare(full, fast)
    assert (r["judged_by_both"], r["agree"], r["differ"]) == (4, 4, [])
    assert r["survivor_proof_seconds"] == {"full": 2, "fast+one-jvm": 2}


def test_compare_reports_a_mutant_the_two_modes_judge_differently():
    r = mu.compare(_run("full", {"a": "killed", "b": "survived"}), _run("fast", {"a": "survived", "b": "survived"}))
    assert r["agree"] == 1 and [d["id"] for d in r["differ"]] == ["a"]
    assert r["by_operator"]["ROR"] == {"judged": 2, "differ": 1}


def test_compare_leaves_out_a_mutant_either_run_has_not_judged():
    r = mu.compare(_run("full", {"a": "killed", "b": "pending"}), _run("fast", {"a": "killed", "c": "killed"}))
    assert r["judged_by_both"] == 1


def test_the_gate_needs_enough_judged_and_no_difference():
    ok = {"judged_by_both": 40, "differ": []}
    assert mu.agreement_gate(ok, None) and mu.agreement_gate(ok, 40)
    assert not mu.agreement_gate(ok, 41)
    assert not mu.agreement_gate({"judged_by_both": 40, "differ": [{"id": "a"}]}, 10)


def test_no_burned_case_has_entry_runs_so_none_is_unvalidated():
    """The doc says entry runs in a session JVM have nothing burned to be validated on. A case that gains `entries`
    must be compared against `--full` (mutation.py compare) and recorded in docs/language_status/mutation_testing.md
    before this list changes."""
    with_entries = sorted(p.parent.name for p in CASES.glob("*/case.json") if json.loads(p.read_text()).get("entries"))
    assert with_entries == [], f"entry runs now exist ({with_entries}): validate --one-jvm on them against --full"
