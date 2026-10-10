"""#4463 follow-up: the det sweep's shards and its plan; #4476: --reuse runs a step the earlier run did not run."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import det_sweep_plan as plan  # noqa: E402
import equivalence_common as common  # noqa: E402
import proof_sweep as ps  # noqa: E402

# ---- --shard -----------------------------------------------------------------------------------------------


def test_shards_partition_the_cases_exactly_once_and_deterministically():
    cases = [f"c{i:02d}" for i in range(37)]
    dur = {c: float(1 + (i * 7) % 23) for i, c in enumerate(cases)}
    for durations in (None, dur, {"c03": 99.0}):
        for n in (1, 2, 3, 6):
            slices = ps.split_cases(cases, n, durations)
            assert len(slices) == n
            assert sorted(sum(slices, [])) == cases  # every case once, none twice
            assert slices == ps.split_cases(list(reversed(cases)), n, durations)  # input order does not matter
            for i in range(1, n + 1):
                assert ps.shard_cases(cases, (i, n), durations) == slices[i - 1]


def test_shards_balance_by_recorded_duration_else_by_name():
    assert ps.split_cases(["d", "a", "c", "b"], 2) == [["a", "c"], ["b", "d"]]  # no records: round-robin by name
    dur = {"big": 100.0, "s1": 30.0, "s2": 30.0, "s3": 30.0, "s4": 10.0}
    slices = ps.split_cases(list(dur), 2, dur)
    assert ["big"] in slices  # the long case is alone with the lightest remainder... 100 vs 100
    loads = sorted(sum(dur[c] for c in s) for s in slices)
    assert loads == [100.0, 100.0]


def test_shard_argument_is_validated():
    assert ps.parse_shard("2/4") == (2, 4)
    for bad in ("0/4", "5/4", "x", "1/0", "1"):
        with pytest.raises(Exception):  # noqa: B017, PT011 -- argparse.ArgumentTypeError
            ps.parse_shard(bad)


def test_the_committed_durations_name_real_cases():
    for case in ps.load_durations():
        assert (ps.CASES / case / "case.json").is_file()


def test_merge_names_a_case_with_no_result(tmp_path):
    for i, names in enumerate((["a", "b"], ["c"])):
        d = tmp_path / str(i)
        d.mkdir()
        (d / "sweep.json").write_text(json.dumps({"det": {n: {"proved": True} for n in names}}), encoding="utf-8")
    merged = ps.merge_sweeps([tmp_path / "0", tmp_path / "1"])
    assert sorted(merged["det"]) == ["a", "b", "c"]
    assert ps.missing_cases(merged, ["a", "b", "c"]) == []
    assert ps.missing_cases(merged, ["a", "z"]) == ["det z: no result (its shard did not report)"]
    with pytest.raises(ValueError, match="in two shards"):
        ps.merge_sweeps([tmp_path / "0", tmp_path / "0"])


# ---- the plan ----------------------------------------------------------------------------------------------

CASES = {
    "alpha": {},
    "beta": {"port_from": "alpha"},
    "gamma": {"uses_ports": ["beta"]},
    "delta": {},
    "dbcase": {"db2": {}},
}


def test_a_change_inside_one_case_proves_that_case_only():
    p = plan.plan(
        ["tests/equivalence/delta/port/service/X.java", "tests/equivalence/delta/case.json"], "pull_request", CASES
    )
    assert (p["mode"], p["cases"]) == ("narrow", ["delta"])


def test_a_cases_coverage_ledger_file_proves_that_case():
    """#4789: a case PR's own ledger file (tests/equivalence/det_sweep_coverage/<case>.json) keeps the sweep narrow: the
    sweep of that case is what checks the entry."""
    p = plan.plan(["tests/equivalence/delta/case.json", "tests/equivalence/det_sweep_coverage/delta.json",
                   "tests/equivalence/det_sweep_coverage/alpha.json"], "pull_request", CASES)  # fmt: skip
    assert (p["mode"], p["cases"]) == ("narrow", ["alpha", "beta", "delta", "gamma"])


def test_dependents_of_a_changed_port_are_proven_too():
    p = plan.plan(["tests/equivalence/alpha/port/A.java"], "pull_request", CASES)
    assert p["cases"] == ["alpha", "beta", "gamma"]  # port_from, then uses_ports of that (transitively)


@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/tools/cobol_to_java/proof_reach.py",  # moves verdicts without moving a port byte
        "tests/tools/equivalence.py",  # the harness / tools
        "tests/equivalence/det_sweep_baseline.json",  # the ratchet itself
        "tests/equivalence/gnucobol.Dockerfile",  # the oracle
        "tests/equivalence/faults/ggfault.c",  # a shared stub
        "tests/equivalence/newcase/case.json",  # a case that does not exist yet / removed
        "tests/equivalence/det_sweep_coverage/newcase.json",  # #4789: the ledger file of no such case
        "tests/equivalence/det_sweep_coverage.json",  # the retired single-file ledger
        "tests/cobol_mainframe/corpora.json",
        ".github/workflows/det-sweep.yml",
    ],
)
def test_anything_but_case_files_is_a_full_sweep(path):
    assert plan.plan(["tests/equivalence/delta/case.json", path], "pull_request", CASES)["mode"] == "full"


@pytest.mark.parametrize("path", ["README.md", "docs/x/y.md", "gitgalaxy/core/detector.py", "tests/tools/pr_check.py",
                                  "gitgalaxy/tools/cobol_to_java/det/NOTES.md"])  # fmt: skip
def test_a_pr_that_changes_no_det_input_proves_nothing(path):
    """#4825: det-sweep runs on every PR (`det` is a required check); the planner proves nothing when no changed file
    is something a det proof reads -- and such a file never widens a case-only plan to a full sweep."""
    p = plan.plan([path], "pull_request", CASES)
    assert p["mode"] == "none" and p["cases"] == [] and plan.shards_for(p) == []
    assert plan.plan([path, "tests/equivalence/delta/case.json"], "pull_request", CASES)["mode"] == "narrow"


def test_a_translator_only_change_is_planned_from_its_port_diff(tmp_path):
    """#4814: det/ (translator + runtime) changes are narrowed to the ports they move; the rest is carried forward."""
    p = plan.plan(
        ["gitgalaxy/tools/cobol_to_java/det/gen.py", "tests/equivalence/delta/case.json"], "pull_request", CASES
    )
    assert p["mode"] == "ports" and p["cases"] == ["delta"] and plan.shards_for(p) == []
    check = tmp_path / "check.json"
    check.write_text(json.dumps([{"case": "alpha", "status": "changed", "files": ["X.java"]},
                                 {"case": "beta", "status": "unchanged", "files": []},
                                 {"case": "dbcase", "status": "changed", "files": ["Y.java"]},
                                 {"case": "delta", "status": "unchanged", "files": []}]), encoding="utf-8")  # fmt: skip
    n = plan.narrow_by_ports(check, ["delta"], CASES)
    assert n["mode"] == "narrow" and n["cases"] == ["alpha", "beta", "delta", "gamma"]  # alpha's port moved: dependents
    assert n["db2_not_swept"] == ["dbcase"] and n["carried"] == 0
    assert plan.shards_for(n) == ["1/2", "2/2"]


def test_no_usable_port_diff_is_a_full_sweep(tmp_path):
    assert plan.narrow_by_ports(tmp_path / "missing.json", [], CASES)["mode"] == "full"
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert plan.narrow_by_ports(tmp_path / "bad.json", [], CASES)["mode"] == "full"


def test_the_port_diff_cli_writes_the_final_outputs(tmp_path):
    check, out = tmp_path / "check.json", tmp_path / "out"
    rows = [
        {"case": c, "status": "changed" if c == "carddemo-menu" else "unchanged", "files": []}
        for c in ["carddemo-menu"]
    ]
    check.write_text(json.dumps(rows), encoding="utf-8")
    run = [
        sys.executable,
        str(ROOT / "tests" / "tools" / "det_sweep_plan.py"),
        "--ports",
        str(check),
        "--github-output",
        str(out),
    ]
    proc = subprocess.run(run, capture_output=True, text=True, check=True)  # noqa: S603
    assert json.loads(proc.stdout)["mode"] == "narrow"
    assert "mode=narrow" in out.read_text(encoding="utf-8") and "shards=1" in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch", "push"])
def test_every_event_but_a_pull_request_is_full(event):
    assert plan.plan(["tests/equivalence/delta/case.json"], event, CASES)["cases"] == "all"


def test_db2_cases_are_not_planned_and_the_runner_count_follows_the_plan():
    p = plan.plan(["tests/equivalence/dbcase/case.json"], "pull_request", CASES)
    assert p["cases"] == [] and plan.shards_for(p) == []
    assert plan.shards_for({"mode": "narrow", "cases": ["a"]}) == ["1/1"]
    assert plan.shards_for({"mode": "narrow", "cases": list("abcdefg")}) == ["1/3", "2/3", "3/3"]
    assert plan.shards_for({"mode": "full", "cases": "all"}) == [f"{i}/20" for i in range(1, 21)]  # #4814


def test_the_cli_reads_the_diff_and_falls_back_to_full(tmp_path):
    out = tmp_path / "out"
    run = [sys.executable, str(ROOT / "tests" / "tools" / "det_sweep_plan.py"), "--github-output", str(out)]
    proc = subprocess.run(
        [*run, "--files", "tests/equivalence/carddemo-menu/case.json"], capture_output=True, text=True, check=True
    )  # noqa: S603
    assert json.loads(proc.stdout)["cases"] == ["carddemo-menu"]
    assert "cases=carddemo-menu" in out.read_text(encoding="utf-8")
    bad = subprocess.run([*run, "--base", "no-such-ref"], capture_output=True, text=True, check=True)  # noqa: S603
    assert json.loads(bad.stdout)["mode"] == "full"  # cannot diff: everything


# ---- #4476: --reuse falls back to a fresh COBOL step ---------------------------------------------------------


def _work(tmp_path: Path, **files: str) -> Path:
    work = tmp_path / "work"
    (work / "src").mkdir(parents=True, exist_ok=True)
    for name, text in {"run.sh": "cobc x\n", "src/PROGRAM.cbl": "A", "IN.in": "1", **files}.items():
        (work / name).write_text(text, encoding="utf-8")
    return work


def test_reuse_falls_back_to_a_fresh_step_when_the_earlier_run_sh_differs(monkeypatch, tmp_path):
    """#4476: a CICS case's second pass overwrote the first pass's run.sh, so --reuse found none that matched."""
    runs: list[Path] = []
    monkeypatch.setattr(
        common, "_docker_run", lambda work, *a: runs.append(work) or subprocess.CompletedProcess(["docker"], 0, "", "")
    )
    earlier = _work(tmp_path / "earlier", **{"run.sh": "pass 2\n"})
    (earlier / "report.json").write_text("{}", encoding="utf-8")
    work = _work(tmp_path / "now")  # run.sh "cobc x\n": not the earlier run's
    monkeypatch.setattr(common, "_REUSE", (work.resolve(), earlier.resolve()))
    assert not common.step_reused(work)
    assert common.run_cobol_step(work).args == ["docker"] and runs == [work]  # ran afresh instead of raising
    (work / "run.sh").write_text("pass 2\n", encoding="utf-8")
    assert common.step_reused(work) and common.run_cobol_step(work).args[0] == "reuse" and len(runs) == 1
