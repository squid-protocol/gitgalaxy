"""#6278 re-measure tool: runner-min rounding, idle runs, and the docs-only / code split."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier as cc  # noqa: E402
import pr_runner_cost as rc  # noqa: E402


def job(start, end, conclusion="success"):
    return {"conclusion": conclusion, "started_at": f"2026-10-28T{start}Z", "completed_at": f"2026-10-28T{end}Z"}


def test_a_started_minute_is_billed():
    assert rc.job_minutes(job("03:00:00", "03:00:20")) == 1
    assert rc.job_minutes(job("03:00:00", "03:01:00")) == 1
    assert rc.job_minutes(job("03:00:00", "03:01:01")) == 2


def test_skipped_and_unfinished_jobs_cost_nothing():
    assert rc.job_minutes(job("03:00:00", "03:09:00", "skipped")) == 0
    assert rc.job_minutes({"conclusion": None, "started_at": None, "completed_at": None}) == 0


def test_summarize_counts_idle_runs_and_groups_by_branch_and_kind():
    runs = [
        {"branch": "a", "workflow": "Smoke", "jobs": [job("03:00:00", "03:10:00"), job("03:00:00", "03:02:30")]},
        {"branch": "a", "workflow": "Ruff", "jobs": [job("03:00:00", "03:00:10", "skipped")]},
        {"branch": "b", "workflow": "Ruff", "jobs": [job("03:00:00", "03:00:40")]},
        {"branch": "c", "workflow": "Ruff", "jobs": []},
    ]
    s = rc.summarize(runs, {"a": "code", "b": "docs-only"})
    assert (s["runs"], s["idle_runs"], s["branches"], s["runner_min"]) == (4, 2, 3, 14)
    assert s["by_kind"]["code"] == {"branches": 1, "runner_min": 13, "per_branch": 13.0}
    assert s["by_kind"]["docs-only"]["runner_min"] == 1
    assert s["by_kind"]["unknown"]["branches"] == 1  # a branch with no kind is never docs-only
    assert s["top_workflows"][0] == ("Smoke", 13)


def test_kind_of_never_calls_an_unreadable_pr_docs_only():
    refs = cc.load()
    assert rc.kind_of(None, refs) == "unknown" and rc.kind_of([], refs) == "unknown"
    assert rc.kind_of(["README.md", ".claude/rules/ci-workflows.md"], refs) == "docs-only"
    assert rc.kind_of(["README.md", "gitgalaxy/galaxyscope.py"], refs) == "code"
    assert rc.kind_of(["tests/tools/test_zos_probes.py"], refs) == "code"


def test_record_only_is_the_fast_lane_allowlist_not_all_prose():
    refs = cc.load()
    base = "docs/" + "language_status/"  # built from parts: a literal would make this test a reader of the record
    rec = [base + "register/probe_a.md", base + "register/probe_b.md"]
    assert rc.kind_of(rec, refs) == "record-only"
    assert rc.kind_of([*rec, "gitgalaxy/galaxyscope.py"], refs) == "code"
    assert rc.kind_of([*rec, "README.md"], refs) == "docs-only"  # prose, but not on the allowlist
    s = rc.summarize([{"branch": "r", "workflow": "W", "jobs": [job("03:00:00", "03:05:00")]}], {"r": "record-only"})
    assert s["by_kind"] == {"record-only": {"branches": 1, "runner_min": 5, "per_branch": 5.0}}


def test_empty_window():
    assert rc.summarize([], {})["per_branch"] == 0.0


def test_pick_record_only_takes_the_first_n_after_the_lane():
    base = "docs/" + "language_status/"
    rec = [base + "register/probe_a.md"]
    prs = [
        {"number": 7960, "files": rec},  # before the lane: ran the full CI
        {"number": 7990, "files": rec},
        {"number": 7985, "files": [*rec, "gitgalaxy/galaxyscope.py"]},  # code in the diff
        {"number": 7970, "files": rec},
        {"number": 7971, "files": []},  # unreadable
        {"number": 7995, "files": rec},
    ]
    assert rc.pick_record_only(prs, 2) == [7970, 7990]
    assert rc.pick_record_only(prs, 10) == [7970, 7990, 7995]


def test_near_misses_name_the_files_that_kept_the_full_lane():
    base = "docs/" + "language_status/"
    rec = base + "register/probe_a.md"
    prs = [
        {"number": 7960, "files": [rec, "gitgalaxy/galaxyscope.py"]},  # before the lane
        {"number": 7970, "files": [rec]},  # record-only: not a near-miss
        {"number": 7971, "files": [rec, "gitgalaxy/galaxyscope.py"]},
        {"number": 7972, "files": ["gitgalaxy/galaxyscope.py"]},  # no record file at all
        {"number": 7973, "files": []},  # unreadable
    ]
    assert rc.near_misses(prs) == {7971: ["gitgalaxy/galaxyscope.py"]}


def test_replay_prices_the_shipped_allowlist_and_only_the_named_extra_globs():
    rec = "docs/" + "language_status/register/probe_a.md"
    mut = "tests/equivalence/det_mutation/probe.json"
    rows = [
        {"number": 7960, "files": [rec], "runner_min": 50},  # before the lane
        {"number": 7970, "files": [rec], "runner_min": 6},
        {"number": 7971, "files": [mut], "runner_min": 81},
        {"number": 7972, "files": [mut, "gitgalaxy/galaxyscope.py"], "runner_min": 200},  # code stays full
        {"number": 7973, "files": [], "runner_min": 3},  # unreadable
        {"number": 7974, "files": [mut, rec], "runner_min": None},  # no runs left to price
    ]
    none = rc.replay(rows, ())
    assert none["merged_after_lane"] == 5
    assert none["shipped_allowlist"] == {"prs": [7970], "runner_min": 6, "unpriced": 0}
    assert none["added_by_also"]["prs"] == []
    wide = rc.replay(rows, ("tests/equivalence/det_mutation/*.json",))
    assert wide["shipped_allowlist"] == none["shipped_allowlist"]
    assert wide["added_by_also"] == {"prs": [7971, 7974], "runner_min": 81, "unpriced": 1}


def test_branch_minutes_sums_per_head_branch():
    runs = [
        {"branch": "a", "jobs": [job("03:00:00", "03:02:00")]},
        {"branch": "a", "jobs": [job("03:00:00", "03:00:10")]},
        {"branch": "b", "jobs": []},
    ]
    assert rc.branch_minutes(runs) == {"a": 3, "b": 0}


def test_pick_lane_prs_counts_mutation_data_only_after_its_own_lane_pr():
    mut = ["tests/equivalence/det_mutation/x.json", "tests/equivalence/det_mutation_survivors/y.json"]
    prs = [
        {"number": 7981, "files": mut},  # before #8031: ran the full lane
        {"number": 8040, "files": mut},
        {"number": 8041, "files": [*mut, "gitgalaxy/core/detector.py"]},  # code file: full CI
        {"number": 8042, "files": ["docs/language_status/blockers_history.jsonl"]},
        {"number": 8043, "files": ["tests/equivalence/other/z.json"]},
    ]
    assert rc.pick_lane_prs(prs, 10) == [8040, 8042]
    assert rc.pick_lane_prs(prs, 1) == [8040]
    assert rc.pick_record_only(prs, 10) == [8042]  # the record-only picker is unchanged
    assert rc.pick_lane_prs([], 10) == []
