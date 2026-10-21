"""#5498: the CICS crucible CI job is cut into shards. Pinned here: the partition covers every case exactly once, the
ledgers cut to a shard's cases give the same verdict as the whole ledger, a merge refuses an incomplete or overlapping
set of shards, and the workflow's matrix is the N the job passes to --shard."""

import re
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import cics_crucible as runner  # noqa: E402

WORKFLOW = TESTS.parent / ".github" / "workflows" / "cics-crucible.yml"
CASES = sorted(runner.CASE_SECONDS) + ["a-new-case"]  # a case with no recorded seconds is still placed


@pytest.mark.parametrize("n", range(1, 9))
def test_every_case_lands_in_exactly_one_shard(n):
    plan = runner.shard_plan(CASES, n)
    flat = [c for shard in plan for c in shard]
    assert sorted(flat) == sorted(CASES) and len(flat) == len(set(flat))
    assert all(plan) or n > len(CASES)


def test_the_plan_is_deterministic_and_balanced():
    assert runner.shard_plan(CASES, 4) == runner.shard_plan(list(reversed(CASES)), 4)
    secs = [
        sum(runner.CASE_SECONDS.get(c, runner.DEFAULT_CASE_SECONDS) for c in s) for s in runner.shard_plan(CASES, 4)
    ]
    assert max(secs) - min(secs) <= max(runner.CASE_SECONDS.values())


@pytest.mark.parametrize("bad", ["0/4", "5/4", "x", "1-4", "1/"])
def test_a_malformed_shard_is_refused(bad):
    with pytest.raises(SystemExit):
        runner.parse_shard(bad)


def _cell(status):
    return {"side": "java", "status": status, "reason": "r"}


def _results(cells, coverage=None):
    return {"crucible_ref": "v", "oracle": None, "cells": cells, "coverage": coverage or {}}


def test_the_ledgers_cut_to_each_shard_hold_what_the_whole_ledger_holds():
    baseline = {"cells": {"a/s/java": {"status": "fail", "reason": "r"}, "b/s/java": {"status": "fail", "reason": "r"}}}
    results = _results({"a/s/java": _cell("pass"), "b/s/java": _cell("fail"), "c/s/java": _cell("fail")})
    whole, _ = runner.ratchet(results, baseline, True)
    plan = [{"a"}, {"b", "c"}]
    parts = []
    for cases in plan:
        base, _cov = runner.restrict(baseline, {"programs": {}}, cases)
        got = {k: v for k, v in results["cells"].items() if k.split("/")[0] in cases}
        parts += runner.ratchet(_results(got), base, True)[0]
    assert sorted(parts) == sorted(whole) and len(whole) == 2  # a NOW PASSES and c NEW FAIL


def test_restrict_cuts_coverage_by_case():
    _base, cov = runner.restrict({"cells": {}}, {"programs": {"a/P": 1, "ab/P": 2}}, {"a"})
    assert cov["programs"] == {"a/P": 1}


def _shard(i, n, cases, measured=None):
    cells = {f"{c}/s/java": _cell("pass") for c in (cases if measured is None else measured)}
    return {**_results(cells), "shard": {"index": i, "total": n, "cases": cases}}


def test_merge_of_a_complete_run_is_clean_and_whole():
    merged, errors = runner.merge_shards([_shard(2, 2, ["b"]), _shard(1, 2, ["a", "c"])], ["a", "b", "c"])
    assert errors == [] and sorted(merged["cells"]) == ["a/s/java", "b/s/java", "c/s/java"]


@pytest.mark.parametrize(
    ("parts", "needle"),
    [
        ([_shard(1, 2, ["a"])], "need 1..2"),
        ([_shard(1, 2, ["a"]), _shard(2, 2, ["a", "b"])], "case a is in shard 1 and shard 2"),
        ([_shard(1, 2, ["a"]), _shard(2, 2, ["b"])], "case c is in no shard"),
        ([_shard(1, 2, ["a", "c"], ["a"]), _shard(2, 2, ["b"])], "case c is in shard 1 but has no cells"),
        ([_shard(1, 2, ["a", "c"], ["a", "c", "b"]), _shard(2, 2, ["b"])], "measured b, which is not in its plan"),
        ([_shard(1, 3, ["a"]), _shard(2, 2, ["b"])], "not all from one sharded run"),
    ],
)
def test_merge_refuses_an_incomplete_or_overlapping_run(parts, needle):
    _merged, errors = runner.merge_shards(parts, ["a", "b", "c"])
    assert any(needle in e for e in errors), errors


def test_the_workflow_matrix_is_the_n_the_job_passes_to_shard():
    text = WORKFLOW.read_text(encoding="utf-8")
    matrix = re.search(r"shard: \[([\d, ]+)\]", text)
    assert matrix, "no shard matrix"
    shards = [int(x) for x in matrix.group(1).split(",")]
    totals = set(re.findall(r"--shard \$\{\{ matrix\.shard \}\}/(\d+)", text))
    assert shards == list(range(1, len(shards) + 1)) and totals == {str(len(shards))}
    assert f"shard ${{{{ matrix.shard }}}}/{len(shards)}" in text  # the job name carries the same N


def test_jobs_measure_the_cases_as_one_at_a_time_does(tmp_path):
    """#5882: --jobs N measures N cases at once, each in its own process; the cells and coverage are the
    sequential run's (engine-facts only: no Docker or Maven needed)."""
    fixture = TESTS / "cics_crucible" / "fixture"
    one = runner.measure(fixture, None, {"engine-facts"}, tmp_path / "one", offline=True)
    two = runner.measure(fixture, None, {"engine-facts"}, tmp_path / "two", offline=True, jobs=2)
    assert len({c["case"] for c in one["cells"].values()}) == 2
    assert two["cells"] == one["cells"] and two["coverage"] == one["coverage"]
