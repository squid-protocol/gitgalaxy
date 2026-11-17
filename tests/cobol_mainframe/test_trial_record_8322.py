"""#8322: `trial.py record` books a measured run whose port log was not kept (Blind 1, Run B) into the trial ledger."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import trial  # noqa: E402

AT = "2026-11-12T00:00:00+00:00"
SHA = "a" * 40


def _trial(progs):
    return {"id": "t", "programs": {k: {"attempts": [], "final": "open"} for k in progs}}


def _run(states):
    return {"programs": {k: {"state": s, "oracle": "compiled"} for k, s in states.items()}}


def test_proven_and_fixed_programs_get_their_finals():
    t = _trial(["A", "B"])
    changed = trial.record_run(t, _run({"A": "proven", "B": "not-proven"}), {"B": ("engine", SHA)}, AT)
    assert changed == {"A": 1, "B": 2}
    assert t["programs"]["A"]["final"] == "proven@1"
    assert t["programs"]["B"]["final"] == "proven@2(engine)"
    first = t["programs"]["B"]["attempts"][0]
    assert (first["outcome"], first["cause"], first["fix_commit"]) == ("failed", "engine", SHA)


def test_the_headline_counts_first_try_only():
    progs = [f"P{i}" for i in range(28)]
    t = _trial(progs)
    states = {k: ("not-proven" if i < 5 else "proven") for i, k in enumerate(progs)}
    trial.record_run(t, _run(states), {k: ("engine", SHA) for k in progs[:5]}, AT)
    t["closed"] = "2026-11-12"
    ledger = {"trials": [{**t, "estate": "e", "system": {"engine_version": "v"}}]}
    v = trial.summary(ledger)["v"]
    assert (v["first"], v["counted"]) == (23, 28)


def test_recording_twice_changes_nothing():
    t = _trial(["A", "B"])
    run, fixes = _run({"A": "proven", "B": "not-proven"}), {"B": ("engine", SHA)}
    trial.record_run(t, run, fixes, AT)
    before = copy.deepcopy(t)
    assert trial.record_run(t, run, fixes, AT) == {}
    assert t == before


@pytest.mark.parametrize(
    ("states", "fixes"),
    [
        ({"A": "not-proven", "B": "proven"}, {}),  # a failure with no fix
        ({"A": "not-judged", "B": "proven"}, {"A": ("harness", SHA)}),  # nothing judged it
        ({"A": "proven", "B": "proven"}, {"A": ("engine", SHA)}),  # a fix for a proven program
        ({"A": "proven"}, {}),  # the run misses an eligible program
        ({"A": "proven", "B": "proven", "C": "proven"}, {}),  # the run has a program that is not eligible
    ],
)
def test_an_unbookable_run_is_refused(states, fixes):
    with pytest.raises(SystemExit):
        trial.record_run(_trial(["A", "B"]), _run(states), fixes, AT)


def test_a_closed_trial_is_refused():
    t = _trial(["A"])
    t["closed"] = "2026-11-12"
    with pytest.raises(SystemExit):
        trial.record_run(t, _run({"A": "proven"}), {}, AT)


def test_run_a_is_never_booked_and_the_cli_checks_the_engine(tmp_path):
    summary = tmp_path / "s.json"
    summary.write_text(json.dumps({"engine_commit": "x", "runs": {"A": _run({"A": "proven"})}}), encoding="utf-8")
    ledger = tmp_path / "l.json"
    ledger.write_text(json.dumps({"trials": []}), encoding="utf-8")
    with pytest.raises(SystemExit):  # unknown trial, before anything is read
        trial.main(["--ledger", str(ledger), "record", "t", "--summary", str(summary), "--run", "A", "--at", AT])


def test_the_committed_ledger_books_run_b_as_the_owner_decided():
    t = next(x for x in trial.load()["trials"] if x["id"] == "trial-001")
    finals = [p["final"] for p in t["programs"].values()]
    assert finals.count("proven@1") == 23
    assert finals.count("proven@2(engine)") == 5
    assert all(a["fix_commit"] for p in t["programs"].values() for a in p["attempts"] if a["cause"])
