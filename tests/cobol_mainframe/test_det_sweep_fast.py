"""#4463 follow-up: the det sweep's shards, its plan, and the COBOL-step cache key."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import det_sweep_plan as plan  # noqa: E402
import equivalence_cobol_cache as cc  # noqa: E402
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


def test_dependents_of_a_changed_port_are_proven_too():
    p = plan.plan(["tests/equivalence/alpha/port/A.java"], "pull_request", CASES)
    assert p["cases"] == ["alpha", "beta", "gamma"]  # port_from, then uses_ports of that (transitively)


@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/tools/cobol_to_java/det/x.py",  # the translator
        "tests/tools/equivalence.py",  # the harness / tools
        "tests/equivalence/det_sweep_baseline.json",  # the ratchet itself
        "tests/equivalence/gnucobol.Dockerfile",  # the oracle
        "tests/equivalence/faults/ggfault.c",  # a shared stub
        "tests/equivalence/newcase/case.json",  # a case that does not exist yet / removed
        "tests/cobol_mainframe/corpora.json",
        ".github/workflows/det-sweep.yml",
        "README.md",
    ],
)
def test_anything_but_case_files_is_a_full_sweep(path):
    assert plan.plan(["tests/equivalence/delta/case.json", path], "pull_request", CASES)["mode"] == "full"


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch", "push"])
def test_every_event_but_a_pull_request_is_full(event):
    assert plan.plan(["tests/equivalence/delta/case.json"], event, CASES)["cases"] == "all"


def test_db2_cases_are_not_planned_and_the_runner_count_follows_the_plan():
    p = plan.plan(["tests/equivalence/dbcase/case.json"], "pull_request", CASES)
    assert p["cases"] == [] and plan.shards_for(p) == []
    assert plan.shards_for({"mode": "narrow", "cases": ["a"]}) == ["1/1"]
    assert plan.shards_for({"mode": "narrow", "cases": list("abcdefg")}) == ["1/3", "2/3", "3/3"]
    assert plan.shards_for({"mode": "full", "cases": "all"}) == [f"{i}/6" for i in range(1, 7)]


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


# ---- the COBOL-step cache key ------------------------------------------------------------------------------

ORACLE = {"base": "debian@sha256:aaa", "gnucobol3": "3.1.2-5+b1", "cobc": "cobc (GnuCOBOL) 3.1.2.0"}


def _work(tmp_path: Path, **files: str) -> Path:
    work = tmp_path / "work"
    (work / "src").mkdir(parents=True, exist_ok=True)
    for name, text in {"run.sh": "cobc x\n", "src/PROGRAM.cbl": "A", "IN.in": "1", **files}.items():
        (work / name).write_text(text, encoding="utf-8")
    return work


def test_key_is_stable_and_a_changed_input_oracle_or_harness_misses(tmp_path):
    k = cc.step_key(cc.snapshot(_work(tmp_path)), ORACLE, "h1")
    assert k == cc.step_key(cc.snapshot(_work(tmp_path)), ORACLE, "h1")
    assert k != cc.step_key(cc.snapshot(_work(tmp_path, **{"IN.in": "2"})), ORACLE, "h1")  # a case input
    assert k != cc.step_key(cc.snapshot(_work(tmp_path, **{"src/PROGRAM.cbl": "B"})), ORACLE, "h1")  # the program
    assert k != cc.step_key(cc.snapshot(_work(tmp_path, **{"run.sh": "cobc y\n"})), ORACLE, "h1")  # the script
    work = _work(tmp_path)
    assert k != cc.step_key(cc.snapshot(work), {**ORACLE, "cobc": "cobc (GnuCOBOL) 3.2"}, "h1")  # the compiler
    assert k != cc.step_key(cc.snapshot(work), {**ORACLE, "gnucobol3": "3.1.2-6"}, "h1")  # the package
    assert k != cc.step_key(cc.snapshot(work), {**ORACLE, "base": "debian@sha256:bbb"}, "h1")  # the image digest
    assert k != cc.step_key(cc.snapshot(work), ORACLE, "h2")  # the harness version


def test_the_image_id_is_not_part_of_the_oracle_identity():
    fp = {"image": {"id": "sha256:1"}, **{k: v for k, v in ORACLE.items()}}
    assert cc.oracle_identity(fp) == cc.oracle_identity({**fp, "image": {"id": "sha256:2"}})


def test_harness_version_covers_the_harness_modules():
    assert len(cc.harness_version()) == 64
    assert all((cc.TOOLS / f).is_file() for f in cc.HARNESS_FILES)


def _stepper(monkeypatch, tmp_path, runs, oracle=ORACLE):
    import equivalence_oracle

    monkeypatch.setenv(cc.ENV, str(tmp_path / "cache"))
    monkeypatch.setattr(equivalence_oracle, "fingerprint", lambda image: {**oracle, "mismatches": []})

    def fake_docker(work, image, docker_args):
        runs.append(work)
        (work / "OUT.out").write_text("out:" + (work / "IN.in").read_text(), encoding="utf-8")
        (work / "program").write_bytes(b"\x7fELFxx")  # a compiled binary: not kept
        (work / "scen" / "out").mkdir(parents=True)
        return subprocess.CompletedProcess(["docker"], 0, "", "")

    monkeypatch.setattr(common, "_docker_run", fake_docker)


def test_a_step_is_cached_and_a_changed_input_or_oracle_runs_again(monkeypatch, tmp_path):
    runs: list[Path] = []
    _stepper(monkeypatch, tmp_path, runs)
    w1 = _work(tmp_path / "a")
    assert common.run_cobol_step(w1).args == ["docker"]  # miss: runs
    w2 = _work(tmp_path / "b")
    p = common.run_cobol_step(w2)
    assert p.args[0] == "cache" and len(runs) == 1  # hit: no run
    assert (w2 / "OUT.out").read_text(encoding="utf-8") == "out:1" and (w2 / "scen" / "out").is_dir()
    assert not (w2 / "program").exists()  # compiled binaries are not kept
    common.run_cobol_step(_work(tmp_path / "c", **{"IN.in": "2"}))
    assert len(runs) == 2  # a changed case input misses
    _stepper(monkeypatch, tmp_path, runs, {**ORACLE, "cobc": "cobc (GnuCOBOL) 3.2.0.0"})
    common.run_cobol_step(_work(tmp_path / "d"))
    assert len(runs) == 3  # a changed oracle misses
    monkeypatch.setenv(cc.ENV, "off")
    common.run_cobol_step(_work(tmp_path / "e"))
    assert len(runs) == 4  # off: never cached


def test_a_failed_step_is_not_cached(monkeypatch, tmp_path):
    import equivalence_oracle

    monkeypatch.setenv(cc.ENV, str(tmp_path / "cache"))
    monkeypatch.setattr(equivalence_oracle, "fingerprint", lambda image: {**ORACLE, "mismatches": []})
    monkeypatch.setattr(common, "_docker_run", lambda *a: subprocess.CompletedProcess(["docker"], 1, "", "boom"))
    common.run_cobol_step(_work(tmp_path / "a"))
    assert not list((tmp_path / "cache").glob("*/DONE"))


def test_reuse_falls_back_to_a_fresh_step_when_the_earlier_run_sh_differs(monkeypatch, tmp_path):
    """#4476: a CICS case's second pass overwrote the first pass's run.sh, so --reuse found none that matched."""
    runs: list[Path] = []
    _stepper(monkeypatch, tmp_path, runs)
    monkeypatch.setenv(cc.ENV, "off")
    earlier = _work(tmp_path / "earlier", **{"run.sh": "pass 2\n"})
    (earlier / "report.json").write_text("{}", encoding="utf-8")
    work = _work(tmp_path / "now")  # run.sh "cobc x\n": not the earlier run's
    monkeypatch.setattr(common, "_REUSE", (work.resolve(), earlier.resolve()))
    assert not common.step_reused(work)
    assert common.run_cobol_step(work).args == ["docker"]  # ran afresh instead of raising
    (work / "run.sh").write_text("pass 2\n", encoding="utf-8")
    assert common.step_reused(work) and common.run_cobol_step(work).args[0] == "reuse"
