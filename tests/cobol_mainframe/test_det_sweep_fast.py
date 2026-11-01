"""#4463 follow-up: the det sweep's shards and its plan; #4476: --reuse runs a step the earlier run did not run."""

from __future__ import annotations

import json
import shutil
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
    assert sorted(ps.merge_sweeps([tmp_path / "0", tmp_path / "0"])["det"]) == [
        "a",
        "b",
    ]  # a repeat is not a conflict (#5107)


def _shard_file(tmp_path, name, sweeps):
    d = tmp_path / name
    d.mkdir()
    (d / "sweep.json").write_text(json.dumps(sweeps), encoding="utf-8")
    return d


_ROW = {
    "proved": True,
    "coverage": "9/10",
    "called_holes": 0,
    "translated": "10/10",
    "seconds": 1.0,
    "uncovered": [],
    "linked": [],
}


def test_a_case_in_two_shards_with_the_same_result_merges_once(tmp_path):
    """#5107: two shards that split on different durations both prove a case; only the timing differs."""
    a = _shard_file(tmp_path, "a", {"det": {"x": _ROW}, "model": {"m": _ROW}})
    b = _shard_file(tmp_path, "b", {"det": {"x": {**_ROW, "seconds": 99.0}}, "model": {"m": _ROW}})
    merged = ps.merge_sweeps([a, b])
    assert merged == {"det": {"x": _ROW}, "model": {"m": _ROW}}  # the first copy is kept, in every sweep


@pytest.mark.parametrize(
    ("field", "other"),
    [
        ("proved", False),
        ("coverage", "5/10"),
        ("called_holes", 2),
        ("translated", "9/10"),
        ("uncovered", ["L1"]),
        ("linked", ["P"]),
        ("brand_new_field", 1),
    ],
)
def test_a_case_in_two_shards_with_different_results_still_fails(tmp_path, field, other):
    a = _shard_file(tmp_path, "a", {"det": {"x": _ROW}})
    b = _shard_file(tmp_path, "b", {"det": {"x": {**_ROW, field: other}}})
    with pytest.raises(ValueError, match=rf"det x: in two shards with conflicting results.*{field}"):
        ps.merge_sweeps([a, b])


def test_shards_split_on_different_durations_merge_and_a_gap_is_still_named(tmp_path):
    """The #5107 scenario: shard 3 split on a newer durations file than shards 1 and 2, so it re-proves shard 1's cases
    and the cases only it should have run are never proven. The merge accepts the repeat; missing_cases names the gap."""
    cases = [f"c{i}" for i in range(9)]
    early = {c: float(i + 1) for i, c in enumerate(cases)}
    late = {c: float(9 - i) for i, c in enumerate(cases)}
    runs = [
        ps.shard_cases(cases, (1, 3), early),
        ps.shard_cases(cases, (2, 3), early),
        ps.shard_cases(cases, (3, 3), late),
    ]
    proved = sorted(set(sum(runs, [])))
    assert len(sum(runs, [])) > len(proved)  # the premise: two shards proved a case
    files = [_shard_file(tmp_path, str(i), {"det": {c: _ROW for c in run}}) for i, run in enumerate(runs)]
    merged = ps.merge_sweeps(files)
    assert sorted(merged["det"]) == proved
    assert ps.missing_cases(merged, cases) == [
        f"det {c}: no result (its shard did not report)" for c in cases if c not in proved
    ]
    assert ps.missing_cases(merged, proved) == []


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
    assert n["db2_cases"] == ["dbcase"] and n["carried"] == 0
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
    assert p["db2_cases"] == ["dbcase"] and plan.db2_shards_for(p) == ["1/1"]  # #4901: the db2 job proves it
    assert plan.shards_for({"mode": "narrow", "cases": ["a"]}) == ["1/1"]
    assert plan.shards_for({"mode": "narrow", "cases": list("abcdefg")}) == ["1/3", "2/3", "3/3"]
    assert plan.shards_for({"mode": "full", "cases": "all"}) == [f"{i}/6" for i in range(1, 7)]  # #4814, #5135


def test_the_cli_reads_the_diff_and_falls_back_to_full(tmp_path):
    out = tmp_path / "out"
    run = [sys.executable, str(ROOT / "tests" / "tools" / "det_sweep_plan.py"), "--github-output", str(out)]
    proc = subprocess.run(
        [*run, "--files", "tests/equivalence/carddemo-menu/case.json"], capture_output=True, text=True, check=True
    )  # noqa: S603
    # the case and the cases that take its port (`port_from`: carddemo-menu-generated, #4506)
    assert json.loads(proc.stdout)["cases"] == ["carddemo-menu", "carddemo-menu-generated"]
    assert "cases=carddemo-menu,carddemo-menu-generated" in out.read_text(encoding="utf-8")
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


# ---- #4901: the Db2 cases the PR moves are proven by the db2 job ---------------------------------------------


def test_db2_cases_are_split_off_and_none_means_no_db2_job():
    p = plan.plan(["tests/equivalence/delta/case.json"], "pull_request", CASES)
    assert p["db2_cases"] == [] and plan.db2_shards_for(p) == []  # nothing Db2 moved: the job is skipped
    none = plan.plan(["README.md"], "pull_request", CASES)
    assert none["mode"] == "none" and plan.db2_shards_for(none) == []
    p = plan.plan(["tests/equivalence/dbcase/case.json", "tests/equivalence/delta/case.json"], "pull_request", CASES)
    assert p["cases"] == ["delta"] and p["db2_cases"] == ["dbcase"]


def test_db2_cases_follow_their_dependents():
    cases = {**CASES, "dbdep": {"db2": {}, "port_from": "alpha"}}
    p = plan.plan(["tests/equivalence/alpha/port/A.java"], "pull_request", cases)
    assert p["cases"] == ["alpha", "beta", "gamma"] and p["db2_cases"] == ["dbdep"]


def test_a_translator_change_waits_for_the_port_diff_for_db2_too():
    p = plan.plan(["gitgalaxy/tools/cobol_to_java/det/emit.py"], "pull_request", CASES)
    assert p["mode"] == "ports" and plan.db2_shards_for(p) == []


def test_db2_runner_count_and_full_sweeps():
    names = [f"d{i}" for i in range(13)]
    assert plan.db2_shards_for({"mode": "narrow", "db2_cases": names[:6]}) == ["1/1"]
    assert plan.db2_shards_for({"mode": "narrow", "db2_cases": names[:7]}) == ["1/2", "2/2"]
    assert len(plan.db2_shards_for({"mode": "narrow", "db2_cases": names})) == 3
    assert len(plan.db2_shards_for({"mode": "narrow", "db2_cases": names * 3})) == plan.DB2_MAX_SHARDS
    # #5882: a full sweep scales with the Db2 cases, one runner per DB2_FULL_PER_SHARD, at most DB2_MAX_SHARDS
    full = {"mode": "full", "db2_cases": "all"}
    assert plan.db2_shards_for(full, 1) == ["1/1"]
    assert plan.db2_shards_for(full, 24) == ["1/2", "2/2"]
    assert len(plan.db2_shards_for(full, 25)) == 3
    assert len(plan.db2_shards_for(full, 1000)) == plan.DB2_MAX_SHARDS
    # the whole input class: the per-runner boundary, the 70-case sweep that timed out (#5882), 100+ cases, the cap
    for n_cases in range(1, 151):
        want = max(1, min(plan.DB2_MAX_SHARDS, -(-n_cases // plan.DB2_FULL_PER_SHARD)))
        got = plan.db2_shards_for(full, n_cases)
        assert got == [f"{i}/{want}" for i in range(1, want + 1)], n_cases
    assert len(plan.db2_shards_for(full, plan.DB2_FULL_PER_SHARD)) == 1
    assert len(plan.db2_shards_for(full, plan.DB2_FULL_PER_SHARD + 1)) == 2
    assert len(plan.db2_shards_for(full, 70)) == 6 and len(plan.db2_shards_for(full, 100)) == 6
    assert len(plan.db2_shards_for(full, plan.DB2_MAX_SHARDS * plan.DB2_FULL_PER_SHARD + 1)) == plan.DB2_MAX_SHARDS
    on_disk = sum(plan.is_db2(c) for c in plan.case_dirs().values())
    assert plan.db2_shards_for(full) == plan.db2_shards_for(full, on_disk)
    # every full sweep proves the Db2 cases, except the nightly: Evidence Refresh's Db2 job does that
    assert plan.plan([], "workflow_dispatch", CASES)["db2_cases"] == "all"
    assert (
        plan.plan(["tests/equivalence/delta/case.json"], "pull_request", CASES, ["shepherd:full"])["db2_cases"] == "all"
    )
    assert plan.plan([], "schedule", CASES)["db2_cases"] == []


def test_the_cli_writes_the_db2_outputs(tmp_path):
    out = tmp_path / "out"
    run = [sys.executable, str(ROOT / "tests" / "tools" / "det_sweep_plan.py"), "--github-output", str(out)]
    subprocess.run([*run, "--files", "README.md"], capture_output=True, text=True, check=True)  # noqa: S603
    text = out.read_text(encoding="utf-8")
    assert "db2_shards=0" in text and "db2_cases=\n" in text and "db2_matrix=[]" in text


# ---- #4847: a generator (forge) change is judged by the port diff, like a translator change -------------------

FORGE = "gitgalaxy/tools/cobol_to_java/cobol_to_java_transaction_forge.py"


def _check(tmp_path, moved, all_cases=("alpha", "beta", "gamma", "delta", "dbcase")):
    rows = [{"case": c, "status": "changed" if c in moved else "unchanged", "files": []} for c in all_cases]
    (tmp_path / "check.json").write_text(json.dumps(rows), encoding="utf-8")
    return tmp_path / "check.json"


def test_a_generator_only_change_with_a_port_diff_narrows_to_the_moved_cases(tmp_path):
    p = plan.plan([FORGE], "pull_request", CASES)
    assert p["mode"] == "ports" and p["cases"] == [] and plan.shards_for(p) == [] and plan.db2_shards_for(p) == []
    n = plan.narrow_by_ports(_check(tmp_path, {"delta", "dbcase"}), [], CASES)
    assert n["mode"] == "narrow" and n["cases"] == ["delta"] and n["db2_cases"] == ["dbcase"]  # K moved cases
    assert n["carried"] == 3 and plan.db2_shards_for(n) == ["1/1"]


def test_a_generator_change_whose_port_diff_fails_is_a_full_sweep(tmp_path):
    n = plan.narrow_by_ports(tmp_path / "no-check.json", [], CASES)  # det_port.py check crashed: no check.json
    assert n["mode"] == "full" and n["cases"] == "all" and n["db2_cases"] == "all"


def test_a_runtime_change_that_moves_every_port_proves_all_of_them(tmp_path):
    n = plan.narrow_by_ports(_check(tmp_path, set(CASES)), [], CASES)
    assert n["mode"] == "narrow" and n["cases"] == ["alpha", "beta", "delta", "gamma"] and n["db2_cases"] == ["dbcase"]
    assert n["carried"] == 0


def test_only_the_project_writing_forges_are_generator_inputs():
    """The build / test / compare forges, the agent and the harness can move a verdict without moving a generated
    byte: they stay a full sweep."""
    for f in ("cobol_to_java_build_forge", "cobol_to_java_test_forge", "cobol_to_java_compare_forge",
              "cobol_to_java_agent_forge", "proof_reach", "port_runner"):  # fmt: skip
        p = plan.plan([f"gitgalaxy/tools/cobol_to_java/{f}.py"], "pull_request", CASES)
        assert p["mode"] == "full", f
    for f in plan.GENERATOR:
        assert (ROOT / f).is_file(), f"{f} is not a file: the generator list is stale"
    p = plan.plan([FORGE, "tests/equivalence/delta/case.json"], "pull_request", CASES)
    assert p["mode"] == "ports" and p["cases"] == ["delta"]


def test_a_generator_class_a_port_names_moves_that_port(tmp_path):
    """det_port.compare sees the generated classes a port is proven against (generated/): a forge change to a DTO the
    port names moves the port; one to a class it never names moves nothing."""
    sys.path.insert(0, str(ROOT / "tests" / "tools"))
    import det_port

    def tree(root, dto):
        for name, text in {"port/service/AService.java": "class AService { CustDto d; }",
                           "generated/dto/CustDto.java": dto,
                           "generated/service/AService.java": "stub"}.items():  # fmt: skip
            f = root / "a" / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")

    tree(tmp_path / "base", "class CustDto {}")
    tree(tmp_path / "same", "class CustDto {}")
    tree(tmp_path / "new", "class CustDto { int x; }")
    assert det_port.compare(tmp_path / "base", tmp_path / "same")[0]["status"] == "unchanged"
    (row,) = det_port.compare(tmp_path / "base", tmp_path / "new")
    assert row["status"] == "changed" and row["files"][0]["file"] == "generated/dto/CustDto.java"
    # a base translated before the snapshot existed has no generated/: only the port itself is compared
    shutil.rmtree(tmp_path / "base" / "a" / "generated")
    assert det_port.compare(tmp_path / "base", tmp_path / "new")[0]["status"] == "unchanged"


def test_the_split_is_a_partition_whatever_the_plan_and_shard_count():
    """#5135 / #5114: with every case in exactly one shard (the real 110 cases, durations known or not), a smaller
    shard count cannot leave one unproved (`missing_cases`) or prove one twice."""
    names = sorted(plan.case_dirs())
    assert len(names) > plan.MAX_SHARDS * plan.PER_SHARD
    recorded = ps.load_durations()
    for durations in (recorded, {}, {n: float(i % 7) for i, n in enumerate(names)}):
        for p in (
            {"mode": "full", "cases": "all"},
            {"mode": "narrow", "cases": names[:5]},
            {"mode": "narrow", "cases": names},
        ):
            matrix = plan.shards_for(p)
            assert len(matrix) <= plan.MAX_SHARDS
            want = names if p["cases"] == "all" else p["cases"]
            got = [c for lab in matrix for c in ps.shard_cases(want, ps.parse_shard(lab), durations)]
            assert sorted(got) == sorted(want)  # none missing, none twice
            assert got == [c for lab in matrix for c in ps.shard_cases(want, ps.parse_shard(lab), durations)]  # stable


def _synthetic(n: int) -> dict[str, float]:
    """n cases shaped like the recorded ones: a ~30 s body and a tail of a few multi-minute cases."""
    return {f"c{i:03d}": 20.0 + (i * 37) % 41 + (180.0 if i % 23 == 0 else 0.0) for i in range(n)}


@pytest.mark.parametrize("count", [45, 70, 140])
def test_shard_count_comes_from_durations_and_balances_within_1_3(count, monkeypatch):
    """#5919: slowest/fastest planned shard <= 1.3 at 45, 70 and 140 cases, inside the pool cap, a partition."""
    dur = _synthetic(count)
    p = {"mode": "narrow", "cases": sorted(dur)}
    matrix = plan.shards_for(p, dur)
    w = {c: dur[c] for c in dur}
    assert 1 <= len(matrix) <= plan.MAX_SHARDS
    ratio = plan.planned_ratio(w, len(matrix))
    assert ratio is None or ratio <= plan.MAX_RATIO
    got = [c for lab in matrix for c in ps.shard_cases(p["cases"], ps.parse_shard(lab), dur)]
    assert sorted(got) == sorted(p["cases"])
    busy = plan.shards_for(p, dur, waiting=99)
    assert len(busy) <= max(1, plan.MAX_SHARDS // 2) and len(busy) <= len(matrix)
    assert plan.shards_for(p, dur, waiting=None) == matrix  # an unreadable queue plans calm
    assert len(plan.shards_for({"mode": "ports"}, dur)) == 0


def test_shard_count_grows_with_the_work_and_falls_back_without_durations():
    small, big = _synthetic(20), _synthetic(140)
    k_small = len(plan.shards_for({"mode": "narrow", "cases": sorted(small)}, small))
    k_big = len(plan.shards_for({"mode": "narrow", "cases": sorted(big)}, big))
    assert k_small < k_big <= plan.MAX_SHARDS
    assert len(plan.shards_for({"mode": "narrow", "cases": sorted(big)})) == plan.MAX_SHARDS  # fixed fallback
    p = {"mode": "full", "cases": "all"}
    real = plan.load_durations()
    assert real and 1 <= len(plan.shards_for(p, real)) <= plan.MAX_SHARDS
    with pytest.raises(Exception, match="no measured duration"):
        plan.shards_for({"mode": "narrow", "cases": sorted(big)}, {"c000": 1.0})


def test_a_full_sweep_plus_db2_fits_the_job_pool():
    """#5135: a full run is shards + db2 jobs (+ plan + det), which must not exceed the 20-job pool."""
    full = {"mode": "full", "cases": "all", "db2_cases": "all"}
    assert len(plan.shards_for(full)) + len(plan.db2_shards_for(full)) + 2 <= 20


# ---- #5885: shared files are narrowed to the cases they can move -----------------------------------------------


def _texts(**sides):
    """texts(path) for plan(): {path: (base, head)} as JSON values (None: that side is absent)."""
    m = {p.replace("__", "/").replace("_DOT_", "."): tuple(None if v is None else json.dumps(v) for v in pair)
         for p, pair in sides.items()}  # fmt: skip
    return lambda path: m.get(path, (None, None))


BASELINE = "tests/equivalence/det_sweep_baseline.json"
INFEASIBLE = "tests/equivalence/infeasible_outcomes.json"


def _keyed(path, base, head):
    return lambda p: (json.dumps(base), json.dumps(head)) if p == path else (None, None)


@pytest.mark.parametrize("path", ["tests/equivalence/det_mutation/carddemo-cardview.json",
                                  "tests/equivalence/det_mutation_survivors/carddemo-cardview.json"])  # fmt: skip
def test_mutation_scores_are_no_det_input(path):
    """No det proof reads the mutation scores (det_mutation.py and evidence_report.py do): nothing to prove."""
    assert plan.plan([path], "pull_request", CASES)["mode"] == "none"
    assert plan.plan([path, "tests/equivalence/delta/case.json"], "pull_request", CASES)["cases"] == ["delta"]


def test_a_baseline_change_proves_the_cases_whose_entries_changed():
    base = {"format": "f/1", "about": "a", "det": {"alpha": "why (#1)", "delta": "why (#2)"}, "model": {}}
    head = {**base, "about": "reworded", "det": {"alpha": "why (#1)"}}  # delta's entry dropped: delta now proves
    p = plan.plan([BASELINE], "pull_request", CASES, texts=_keyed(BASELINE, base, head))
    assert (p["mode"], p["cases"]) == ("narrow", ["delta"])


@pytest.mark.parametrize("head", [
    {"format": "f/2", "about": "a", "det": {}, "model": {}},  # another top-level key changed
    {"format": "f/1", "about": "a", "det": {"newcase": "why (#3)"}, "model": {}},  # an entry of no case
])  # fmt: skip
def test_a_baseline_change_outside_case_entries_is_a_full_sweep(head):
    base = {"format": "f/1", "about": "a", "det": {}, "model": {}}
    assert plan.plan([BASELINE], "pull_request", CASES, texts=_keyed(BASELINE, base, head))["mode"] == "full"
    assert plan.plan([BASELINE], "pull_request", CASES)["mode"] == "full"  # no texts: cannot tell
    assert plan.plan([BASELINE], "pull_request", CASES, texts=lambda p: ("{", None))["mode"] == "full"


def test_an_infeasible_outcome_change_proves_its_cases_and_the_cases_citing_a_changed_family():
    e = {"line": 1, "outcome": "true"}
    base = {"format": "i/1", "issue": "#4602", "about": "a", "families": {"G": "x", "C": "y"},
            "cases": {"alpha": [{**e, "family": "G"}], "delta": [{**e, "family": "C"}]}}  # fmt: skip
    head = {**base, "cases": {"alpha": [{**e, "family": "G"}], "delta": [{**e, "family": "C"}, {**e, "line": 2}]}}
    p = plan.plan([INFEASIBLE], "pull_request", CASES, texts=_keyed(INFEASIBLE, base, head))
    assert (p["mode"], p["cases"]) == ("narrow", ["delta"])
    head = {**base, "families": {"G": "x, reworded", "C": "y"}}
    p = plan.plan([INFEASIBLE], "pull_request", CASES, texts=_keyed(INFEASIBLE, base, head))
    assert p["cases"] == ["alpha", "beta", "gamma"]  # alpha cites G; its port's dependents follow


def test_a_corpus_pin_change_proves_the_cases_on_that_corpus():
    cases = {"a1": {"corpus": "carddemo"}, "a2": {"corpus": "carddemo", "db2": {}}, "b1": {"corpus": "genapp"}}
    base = {"corpora": [{"name": "carddemo", "ref": "r1"}, {"name": "genapp", "ref": "g1"}]}
    head = {"corpora": [{"name": "carddemo", "ref": "r2"}, {"name": "genapp", "ref": "g1"}]}
    p = plan.plan([plan.CORPORA], "pull_request", cases, texts=_keyed(plan.CORPORA, base, head))
    assert (p["mode"], p["cases"], p["db2_cases"]) == ("narrow", ["a1"], ["a2"])
    head = {**head, "about": "new top-level key"}
    assert plan.plan([plan.CORPORA], "pull_request", cases, texts=_keyed(plan.CORPORA, base, head))["mode"] == "full"


COMPONENT_CASES = {"batch1": {}, "db2batch": {"db2": {}}, "imsbatch": {"ims": {}}, "online": {"kind": "cics"},
                   "linker": {"kind": "call"}}  # fmt: skip


@pytest.mark.parametrize(("path", "want"), [
    ("tests/equivalence/db2/ggsql.c", {"db2batch"}),  # oracle:db2
    ("tests/equivalence/db2/dynsql/cbl/DYNDEMO.cbl", {"db2batch"}),
    ("tests/tools/equivalence_db2.py", {"db2batch"}),  # harness:db2
    ("tests/equivalence/ims/ggdli.c", {"imsbatch"}),  # oracle:ims
    ("tests/tools/equivalence_ims.py", {"imsbatch"}),  # harness:ims
    ("tests/equivalence/cics/ggcics.c", {"online"}),  # oracle:cics-stub
    ("tests/tools/equivalence_cics.py", {"db2batch", "online", "linker"}),  # harness:cics (cics_harness)
    ("tests/tools/equivalence_call.py", {"linker"}),  # harness:call
])  # fmt: skip
def test_a_harness_or_oracle_component_proves_the_cases_that_use_it(path, want):
    """#4731's component map (evidence.COMPONENTS) decides which cases a harness / oracle file can move."""
    p = plan.plan([path], "pull_request", COMPONENT_CASES)
    assert p["mode"] == "narrow" and set(p["cases"]) | set(p["db2_cases"]) == want, p


@pytest.mark.parametrize("path", [
    "tests/tools/equivalence.py",  # harness:core: every case
    "tests/equivalence/le/ceedays.c",  # oracle:le: linked into every program
    "tests/equivalence/faults/ggabend.c",  # oracle:core
    "tests/equivalence/gnucobol.Dockerfile",  # oracle:core
])  # fmt: skip
def test_a_harness_or_oracle_file_every_case_uses_is_a_full_sweep(path):
    assert plan.plan([path], "pull_request", COMPONENT_CASES)["mode"] == "full"


def test_every_cics_task_module_the_transaction_forge_splices_in_is_a_generator_input():
    """#5885: #5448 split cics_task_filecontrol.py out of the transaction forge but left it off GENERATOR, so a change to
    it was a full sweep instead of a port diff. Every cics_task_* module the forge imports is listed."""
    import re

    forge = (ROOT / FORGE).read_text(encoding="utf-8")
    split = {
        f"gitgalaxy/tools/cobol_to_java/{m}.py" for m in re.findall(r"cobol_to_java\.(cics_task_\w+) import", forge)
    }
    assert split and split <= set(plan.GENERATOR), split - set(plan.GENERATOR)


def test_a_db2_start_that_never_finishes_is_retried_once_on_a_fresh_container(monkeypatch):  # #5602
    import equivalence_db2 as d

    starts, waits = [], iter([False, True])
    monkeypatch.setattr(d, "_CONTAINER_READY", False)
    monkeypatch.setattr(d, "READY_MARK", Path("/nonexistent/db2-ready-mark"))
    monkeypatch.setattr(d, "_docker", lambda *a, **k: "image-id")
    monkeypatch.setattr(d, "_container_identity", lambda: "")
    monkeypatch.setattr(d, "_start_container", lambda *, replace=False: starts.append(replace))
    monkeypatch.setattr(d, "_await_ready", lambda: next(waits))
    d._ensure_container()
    assert starts == [False, True]
    assert d._CONTAINER_READY


def test_a_failed_docker_run_is_retried_once_on_a_fresh_container(monkeypatch):  # #5604
    import equivalence_db2 as d

    starts = []

    def start(*, replace=False):
        starts.append(replace)
        if not replace:
            raise RuntimeError("docker run: port is already allocated")

    monkeypatch.setattr(d, "_CONTAINER_READY", False)
    monkeypatch.setattr(d, "READY_MARK", Path("/nonexistent/db2-ready-mark"))
    monkeypatch.setattr(d, "_docker", lambda *a, **k: "image-id")
    monkeypatch.setattr(d, "_container_identity", lambda: "")
    monkeypatch.setattr(d, "_start_container", start)
    monkeypatch.setattr(d, "_await_ready", lambda: True)
    d._ensure_container()
    assert starts == [False, True]


def test_an_image_pull_failure_is_not_retried_here(monkeypatch):  # #5604: pull_image has its own 4 attempts
    import equivalence_db2 as d

    def start(*, replace=False):
        raise d.Db2ImagePullError("INFRASTRUCTURE")

    monkeypatch.setattr(d, "_CONTAINER_READY", False)
    monkeypatch.setattr(d, "READY_MARK", Path("/nonexistent/db2-ready-mark"))
    monkeypatch.setattr(d, "_docker", lambda *a, **k: "image-id")
    monkeypatch.setattr(d, "_start_container", start)
    with pytest.raises(d.Db2ImagePullError):
        d._ensure_container()


def test_a_container_that_exited_ends_the_ready_wait_at_once(monkeypatch):  # #5604
    import equivalence_db2 as d

    monkeypatch.setattr(d, "_docker", lambda *a, **k: "false" if a[0] == "inspect" else "")
    monkeypatch.setattr(d.time, "sleep", lambda s: pytest.fail("polled a dead container"))
    assert d._await_ready() is False


def test_a_db2_start_that_fails_twice_raises(monkeypatch):  # #5602
    import equivalence_db2 as d

    monkeypatch.setattr(d, "_CONTAINER_READY", False)
    monkeypatch.setattr(d, "READY_MARK", Path("/nonexistent/db2-ready-mark"))
    monkeypatch.setattr(d, "_docker", lambda *a, **k: "image-id")
    monkeypatch.setattr(d, "_start_container", lambda *, replace=False: None)
    monkeypatch.setattr(d, "_await_ready", lambda: False)
    with pytest.raises(RuntimeError, match="did not come up"):
        d._ensure_container()
    assert not d._CONTAINER_READY


# ---- #5862: the PR-time det_mutation stale-check ------------------------------------------------------------


def _det_sweep_jobs() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8"))["jobs"]


def _runs(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job["steps"])


def test_detmut_job_runs_the_stale_check_against_main_on_ready_prs_only():
    job = _det_sweep_jobs()["detmut"]
    assert "det_mutation.py stale-check --vs origin/main" in _runs(job)
    for part in ("github.event_name == 'pull_request'", "draft == false"):
        assert part in job["if"]
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["fetch-depth"] == 0  # the merge base the --vs scope diffs against


def test_detmut_job_fetches_its_own_corpora_before_the_check():
    job = _det_sweep_jobs()["detmut"]
    runs = [s.get("run", "") for s in job["steps"]]
    fetch = next(i for i, r in enumerate(runs) if "mainframe_corpus.py fetch" in r)
    check = next(i for i, r in enumerate(runs) if "stale-check" in r)
    assert fetch < check
    assert "GITGALAXY_MAINFRAME_CORPORA" in job["env"]
    assert "plan" not in job.get("needs", [])  # no diff-plan dependency: it only fingerprints


def test_the_required_det_check_waits_for_detmut_and_fails_on_its_failure_only():
    jobs = _det_sweep_jobs()
    det = jobs["det"]
    assert "detmut" in det["needs"]
    assert "!cancelled()" in det["if"]  # a skipped detmut (draft, nightly, dispatch) must not skip `det`
    gate = next(s for s in det["steps"] if "detmut.result" in str(s.get("if", "")))
    assert gate["if"].strip() == "needs.detmut.result == 'failure'"
    assert "exit 1" in gate["run"]
