"""`cics_census.py check` (#7961): HEAD vs the cached baseline, counts only. Fixtures only: invented corpus names, no
census path, no real survey (det_survey, box_status and git are stubbed)."""

import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import census_check as ck
import census_nightly as cn
import cics_census as cc

SHA = "b" * 40
HOLE = "line 4: EXEC EXEC CICS: EXEC CICS GETMAIN not modelled"
HOLE2 = "line 9: EXEC EXEC CICS: EXEC CICS XCTL not modelled"
CUT = "ExprError: P.cbl:7: source defect: source text past column 72 (`x'`) cuts a literal open: fixed-form COBOL reads columns 8-72 only"


def row(name, *holes, error=None):
    if error:
        return {"program": name, "error": error}
    return {"program": name, "statements": 3, "translated": 3 - bool(holes), "holes": list(holes)}


# burned: cics-genapp (one program A, B); census-like: zzcensus-alpha / zzcensus-beta (invented names)
KEYS = [("cics-genapp", "A.cbl"), ("cics-genapp", "B.cbl"), ("zzcensus-alpha", "Pone.cbl"),
        ("zzcensus-alpha", "Ptwo.cbl"), ("zzcensus-beta", "Qone.cbl")]  # fmt: skip


def rows(**by):
    base = {("cics-genapp", "A.cbl"): row("A.cbl"), ("cics-genapp", "B.cbl"): row("B.cbl", HOLE),
            ("zzcensus-alpha", "Pone.cbl"): row("Pone.cbl", HOLE),
            ("zzcensus-alpha", "Ptwo.cbl"): row("Ptwo.cbl", error=CUT),
            ("zzcensus-beta", "Qone.cbl"): row("Qone.cbl", HOLE, HOLE2)}  # fmt: skip
    for k, v in by.items():
        base[KEYS[int(k[1:])]] = v
    return base


def test_measure_counts_whole_split_and_accounted():
    m = ck.measure(rows(), set(KEYS))
    assert (m["programs"], m["whole"], m["whole_burned"], m["whole_census"]) == (5, 1, 1, 0)
    assert m["gaps"]["EXEC CICS GETMAIN"] == 3
    assert m["gaps"]["EXEC CICS XCTL"] == 1
    assert m["accounted"] >= m["whole"]


def test_compare_whole_and_gap_rows_gone_and_new():
    after = rows(
        k4=row("Qone.cbl", HOLE2),
        k2=row("Pone.cbl"),
        k1=row("B.cbl", "line 1: EXEC EXEC CICS: EXEC CICS ASKTIME not modelled"),
    )
    res = ck.compare(ck.measure(rows(), set(KEYS)), ck.measure(after, set(KEYS)))
    assert (res["head"]["whole"], res["head"]["whole_census"]) == (2, 1)
    assert ("EXEC CICS GETMAIN", 3) in res["gone"]
    assert [g for g, _ in res["new"]] == ["EXEC CICS ASKTIME"]
    text = ck.format_check(res, SHA)
    assert "whole 1 -> 2 (census 0 -> 1, burned 1 -> 1)" in text
    assert text.splitlines()[0].startswith("census check: HEAD (worktree) vs origin/main bbbbbbbbbbbb")


def test_missing_head_row_counts_as_no_row_not_a_name():
    head = rows()
    del head[KEYS[2]]
    m = ck.measure(head, set(KEYS))
    assert m["gaps"][ck.NO_ROW] == 1 and m["whole"] == 1


def test_census_program_error_text_is_scrubbed_in_the_output():
    leaky = rows(k3=row("Ptwo.cbl", error="ExprError: Ptwo.cbl:1: no such thing zzcensus-alpha_secret"))
    res = ck.compare(ck.measure(rows(), set(KEYS)), ck.measure(leaky, set(KEYS)))
    assert "zzcensus" not in ck.format_check(res, SHA) and "Ptwo" not in ck.format_check(res, SHA)


def test_names_a_census_matches_whole_tokens_only(tmp_path):
    forbidden = ck.forbidden_names(rows(), tmp_path)
    assert ck.names_a_census("gap row: zzcensus-alpha", forbidden)
    assert ck.names_a_census("see Pone", forbidden)
    assert not ck.names_a_census("whole 1 -> 2 (census 0 -> 1, burned 1 -> 1) cics-genapp-free", forbidden)
    assert not ck.names_a_census("anything", [])


def test_counts_only_of_the_nightly_still_refuses_names():
    line = json.dumps({"pr": 0, "note": "from /x/Census-Repo"})
    assert cn.counts_only(line, ["census-repo"]) == "the line names a census path or repo"
    assert cn.counts_only(json.dumps({"pr": 0}), ["census-repo"]) is None


# ---- cmd_check: the whole flow with every outside thing stubbed ------------------------------------------------
@pytest.fixture
def flow(tmp_path, monkeypatch):
    root = tmp_path / "scratch"
    d = cc.cache_dir(root, SHA)
    for suffix, keys in (("b", KEYS[:2]), ("nb", KEYS[2:])):
        corp: dict[str, list] = {}
        for c, p in keys:
            corp.setdefault(c, []).append(rows()[(c, p)])
        (d / f"before-{suffix}").mkdir(parents=True)
        (d / f"before-{suffix}" / "survey.json").write_text(json.dumps(corp))
    (d / "cics_programs.json").write_text(json.dumps([list(k) for k in KEYS]))
    (d / "meta.json").write_text(json.dumps({"sha": SHA, "census": True, "scope": "x"}))
    state = {"verdict": "GREEN", "surveyed": 0, "head": rows(k2=row("Pone.cbl"))}

    def fake_run(out, label, runs, **kw):
        state["surveyed"] += 1
        state["jobs"] = kw.get("jobs")
        state["out"] = out
        corp: dict[str, list] = {}
        for (c, _p), r in state["head"].items():
            corp.setdefault(c, []).append(r)
        (out / "head-b").mkdir(parents=True, exist_ok=True)
        (out / "head-b" / "survey.json").write_text(json.dumps(corp))
        print(f"head-b: 2 corpora from {tmp_path}/census-secret-path")  # must never reach the terminal
        return state.get("rc", 0)

    monkeypatch.setattr(cn, "box_verdict", lambda: state["verdict"])
    monkeypatch.setattr(cc, "resolve_sha", lambda sha=None, fetch=False: sha or SHA)
    monkeypatch.setattr(cc, "mainframe_root", lambda arg: tmp_path)
    monkeypatch.setattr(cc, "baseline_census", lambda args, r: tmp_path / "census")
    monkeypatch.setattr(cc, "survey_runs", lambda *a, **k: [("b", tmp_path, ["x"])])
    monkeypatch.setattr(cc, "run_det_survey", fake_run)
    monkeypatch.setattr(ck.os, "nice", lambda n: 0, raising=False)
    args = argparse.Namespace(root=root, sha=None, jobs=2, force=False, corpora=None, census_corpora=None,
                              no_census=False)  # fmt: skip
    return state, args, d


def test_check_prints_counts_only_deletes_the_survey_and_uses_two_jobs(flow, capsys):
    state, args, _ = flow
    assert ck.cmd_check(args) == 0
    out = capsys.readouterr()
    assert "whole 1 -> 2 (census 0 -> 1, burned 1 -> 1)" in out.out
    assert "census-secret-path" not in out.out + out.err
    assert "zzcensus" not in out.out + out.err
    assert state["jobs"] == 2 and not state["out"].exists()


def test_check_is_gated_on_a_green_box(flow, capsys):
    state, args, _ = flow
    state["verdict"] = "YELLOW"
    assert ck.cmd_check(args) == ck.NOT_GREEN
    assert state["surveyed"] == 0 and "needs GREEN" in capsys.readouterr().out
    args.force = True
    assert ck.cmd_check(args) == 0 and state["surveyed"] == 1


def test_check_refuses_a_baseline_surveyed_without_the_census(flow):
    _, args, d = flow
    (d / "meta.json").write_text(json.dumps({"sha": SHA, "census": False}))
    with pytest.raises(SystemExit, match="without the census"):
        ck.cmd_check(args)


def test_check_without_a_cached_baseline_names_the_fix(flow):
    _, args, d = flow
    (d / "meta.json").unlink()
    with pytest.raises(SystemExit, match="survey --baseline"):
        ck.cmd_check(args)


def test_a_failed_head_survey_withholds_details(flow):
    state, args, _ = flow
    state["rc"] = 1
    with pytest.raises(SystemExit, match="details withheld") as e:
        ck.cmd_check(args)
    assert "census-secret-path" not in str(e.value)


def test_a_line_that_still_names_a_census_program_is_refused(flow, monkeypatch, capsys):
    _, args, _ = flow
    monkeypatch.setattr(ck, "format_check", lambda res, sha: "whole 1 -> 2 in zzcensus-alpha")
    assert ck.cmd_check(args) == 1
    out = capsys.readouterr()
    assert out.out == "" and "refused" in out.err and "zzcensus" not in out.err


def test_the_check_subcommand_is_wired_with_two_jobs_by_default(monkeypatch):
    seen = {}
    monkeypatch.setattr(ck, "cmd_check", lambda a: seen.update(jobs=a.jobs, force=a.force, nc=a.no_census) or 0)
    assert cc.main(["check"]) == 0
    assert seen == {"jobs": 2, "force": False, "nc": False}
