"""#5498: the CICS crucible CI job is cut into shards. Pinned here: the partition covers every case exactly once, the
ledgers cut to a shard's cases give the same verdict as the whole ledger, a merge refuses an incomplete or overlapping
set of shards, and the workflow's matrix is the N the job passes to --shard."""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import crucible_shard_plan as plan  # noqa: E402

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
    """#5919: N comes from the `plan` job, so the matrix, the --shard total and the job name all read the plan."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "shard: [" not in text, "a hand-set shard list"
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in text
    assert "timeout-minutes: ${{ fromJSON(needs.plan.outputs.timeout) }}" in text
    assert "crucible_shard_plan.py --cics" in text
    assert "--shard ${{ matrix.shard }}/${{ matrix.total }}" in text
    assert "shard ${{ matrix.shard }}/${{ matrix.total }})" in text  # the job name carries the same N
    assert "needs: [plan, measure, runner-tests]" in text


def _cases(n):
    return [f"new-{i:03d}" for i in range(n)]


def test_cics_plan_today_is_two_shards():
    assert plan.cics_plan(sorted(runner.CASE_SECONDS))["matrix"]["include"] == [
        {"shard": 1, "total": 2},
        {"shard": 2, "total": 2},
    ]


def _grown(monkeypatch, n):
    """CASE_SECONDS grown to n measured cases (the existing ones cycled), in both modules that read it."""
    base = sorted(runner.CASE_SECONDS.items())
    grown = {f"{k}-{i}": v for i, (k, v) in ((i, base[i % len(base)]) for i in range(n))}
    monkeypatch.setattr(plan, "CASE_SECONDS", grown)
    monkeypatch.setattr(runner, "CASE_SECONDS", grown)
    return sorted(grown)


def test_cics_growth_needs_no_edit_and_stays_balanced(monkeypatch):
    """43 -> 90 -> 200 -> 400 cases: the count follows the work up to the pool share, every shard stays balanced (<= 1.3)."""
    prev = 0
    for n in (43, 90, 200, 400):
        ids = _grown(monkeypatch, n)
        p = plan.cics_plan(ids)
        assert prev <= p["shards"] <= plan.CICS_MAX_SHARDS and len(p["matrix"]["include"]) == p["shards"]
        assert plan.CICS_TIMEOUT_FLOOR <= p["timeout"] <= plan.CICS_TIMEOUT_CEILING
        prev = p["shards"]
        loads = [sum(plan.CASE_SECONDS[c] for c in s) for s in runner.shard_plan(ids, p["shards"])]
        assert max(loads) / min(loads) <= 1.3
    assert prev == plan.CICS_MAX_SHARDS


def test_cics_busy_queue_halves_the_cap(monkeypatch):
    ids = _grown(monkeypatch, 400)
    assert plan.cics_plan(ids)["shards"] == plan.CICS_MAX_SHARDS
    assert plan.cics_plan(ids, waiting=99)["shards"] == plan.CICS_MAX_SHARDS // 2


def test_cics_unmeasured_cases_are_a_grace_then_a_loud_failure():
    ids = sorted(runner.CASE_SECONDS)
    assert plan.cics_plan([*ids, "new-a", "new-b"])["shards"] >= 1  # a PR adding a couple of cases
    with pytest.raises(plan.sp.PlanError, match="no measured duration"):
        plan.cics_plan([*ids, *_cases(len(ids))])


def test_case_ids_are_the_discovered_case_directories(tmp_path):
    for trap, case in (("t1", "b-case"), ("t2", "a-case")):
        (tmp_path / "cases" / trap / case).mkdir(parents=True)
        (tmp_path / "cases" / trap / case / "case.json").write_text("{}")
    (tmp_path / "cases" / "t1" / "no-json").mkdir()
    assert plan.case_ids(tmp_path) == ["a-case", "b-case"]
    assert plan.case_ids(tmp_path) == [d.name for d in cc.discover(tmp_path)]


def _ports(n):
    return {f"p{i:02d}": 50_000 + (i * 7919 % 400_000) for i in range(n)}


def test_doom_plan_covers_every_port_once_balanced_and_deterministic():
    loc = _ports(44)
    p = plan.doom_plan(loc, sorted(loc))
    shards = [s["ports"].split(",") for s in p["matrix"]["include"]]
    assert sorted(x for s in shards for x in s) == sorted(loc) and p["shards"] == len(shards)
    loads = [sum(loc[x] for x in s) for s in shards]
    assert max(loads) / min(loads) <= 1.3
    assert p == plan.doom_plan(loc, list(reversed(sorted(loc))))
    assert plan.DOOM_TIMEOUT_FLOOR <= p["timeout"] <= plan.DOOM_TIMEOUT_CEILING


def test_doom_growth_adds_shards_up_to_the_cap_and_busy_halves_it():
    prev = 0
    for n in (44, 150, 600):
        loc = _ports(n)
        k = plan.doom_plan(loc, sorted(loc))["shards"]
        assert prev <= k <= plan.DOOM_MAX_SHARDS
        prev = k
    assert prev == plan.DOOM_MAX_SHARDS
    loc = _ports(600)
    assert plan.doom_plan(loc, sorted(loc), waiting=99)["shards"] == plan.DOOM_MAX_SHARDS // 2


def test_doom_port_without_a_golden_fails_loudly_past_the_grace():
    loc = _ports(10)
    assert plan.doom_plan(loc, [*sorted(loc), "extra"])["shards"] >= 1
    with pytest.raises(plan.sp.PlanError, match="port"):
        plan.doom_plan(loc, [*sorted(loc), *_cases(8)])


def test_the_real_doom_manifest_and_goldens_plan_cleanly():
    tests = TESTS
    ports = plan.manifest_ports(tests / "doom_rosetta" / "manifest.csv")
    p = plan.doom_plan(plan.golden_loc(tests / "golden_doom_rosetta"), ports)
    assert sorted(x for s in p["matrix"]["include"] for x in s["ports"].split(",")) == sorted(ports)


@pytest.mark.slow(
    reason="a spawn pool re-imports the engine and rescans both fixture cases, beside the sequential run (#5882)"
)
def test_jobs_measure_the_cases_as_one_at_a_time_does(tmp_path):
    """#5882: --jobs N measures N cases at once, each in its own process; the cells and coverage are the
    sequential run's (engine-facts only: no Docker or Maven needed)."""
    fixture = TESTS / "cics_crucible" / "fixture"
    one = runner.measure(fixture, None, {"engine-facts"}, tmp_path / "one", offline=True)
    two = runner.measure(fixture, None, {"engine-facts"}, tmp_path / "two", offline=True, jobs=2)
    assert len({c["case"] for c in one["cells"].values()}) == 2
    assert two["cells"] == one["cells"] and two["coverage"] == one["coverage"]


def test_the_measure_job_installs_the_parser_a_bll_program_needs():
    """#5119: the COBOL side lowers a BLL program through det/bll.py, which parses its records with tree-sitter; without
    the package ca-bll-cells raised ImportError, the shard wrote no results.json and the merge failed."""
    measure = WORKFLOW.read_text(encoding="utf-8").split("\n  measure:\n")[1].split("\n  runner-tests:\n")[0]
    assert "ci/requirements/treesitter.txt" in measure.split("- name: Setup JDK 17")[0]
