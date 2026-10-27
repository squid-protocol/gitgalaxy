"""The nightly referee-panel runner (#4438 item 4): corpus choice, preflight, the scratch-only rule and the
step orchestration, against a stub runner. No JVM and no referee is needed."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "referees"))

import facts as F
import run_panel as R


def test_panel_corpora_are_the_burned_keyed_ones():
    names = {c["name"] for c in R.panel_corpora()}
    assert "cics-genapp" in names and "zecs" in names
    # not burned (zopeneditor-sample, dsf): never part of the panel's nightly set
    assert not names & {"zopeneditor-sample", "dsf"}
    assert all((R.KEY_DIR / f"{n}.json").is_file() for n in names)


def test_unknown_or_unburned_corpus_is_refused():
    with pytest.raises(SystemExit, match="not a burned, keyed corpus"):
        R.panel_corpora(["dsf"])


def test_preflight_names_every_missing_referee(tmp_path):
    problems = R.preflight({})
    assert len(problems) == len(R.REFEREES)
    for var in R.REFEREE_ENV.values():
        assert any(var in p for p in problems)
    jar = tmp_path / "server.jar"
    jar.write_text("")
    env = {
        **{v: str(jar) for v in R.REFEREE_ENV.values()},
        "COBRIX_CLASSPATH": os.pathsep.join([str(jar), str(tmp_path / "gone.jar")]),
    }
    assert R.preflight(env) == [f"COBRIX_CLASSPATH: {tmp_path / 'gone.jar'} does not exist (cobrix)"]


def test_out_inside_the_checkout_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="inside the checkout"):
        R.check_out(R.REPO_ROOT / "tests" / "scratch_out")
    with pytest.raises(SystemExit, match="inside the checkout"):
        R.check_out(R.REPO_ROOT)
    assert R.check_out(tmp_path) == tmp_path.resolve()


def test_steps_run_scan_then_engine_then_each_referee_then_score(tmp_path):
    corpus = R.panel_corpora(["cics-genapp"])[0]
    labels = [label for label, _ in R.steps(corpus, tmp_path)]
    assert labels == [f"cics-genapp:{s}" for s in ("fetch", "scan", "engine", *R.REFEREES)]
    # every fact file lands under <out>/facts/<corpus>/, where score.py reads them
    outs = [Path(cmd[cmd.index("--out") + 1]) for label, cmd in R.steps(corpus, tmp_path) if "--out" in cmd]
    assert {o.parent for o in outs} == {tmp_path / "facts" / "cics-genapp"}
    assert R.score_step(tmp_path)[2:4] == ["--facts", str(tmp_path / "facts")]


def stub(fail: set[str] = frozenset(), unparsed: str | None = None):
    """A runner that writes a referee-facts document for every adapter step instead of running one."""
    seen: list[list[str]] = []

    def run(cmd, cwd):
        seen.append(list(cmd))
        if "--out" in cmd and "--corpus" in cmd:
            out = Path(cmd[cmd.index("--out") + 1])
            src = out.stem
            doc = F.new_doc(src, "stub", cmd[cmd.index("--corpus") + 1], [])
            F.add_file(doc, "A.cbl", {}, status="fail" if src == unparsed else "ok")
            F.dump(doc, out)
        return 3 if any(f in " ".join(cmd) for f in fail) else 0

    return run, seen


def test_a_clean_run_reports_every_source_and_exits_zero(tmp_path):
    corpora = R.panel_corpora(["cics-genapp", "zecs"])
    run, seen = stub()
    report, code = R.run_panel(corpora, tmp_path, run)
    assert code == 0 and report["problems"] == []
    assert set(report["corpora"]["zecs"]) == {"engine", *R.REFEREES}
    assert report["corpora"]["zecs"]["che4z"] == {"version": "stub", "members": 1, "status": {"ok": 1}}
    assert "score.py" in seen[-1][1]
    json.dumps(report)


def test_a_failing_step_does_not_stop_the_other_corpora(tmp_path):
    corpora = R.panel_corpora(["cics-genapp", "zecs"])
    run, seen = stub(fail={"treesitter_adapter.py"})
    report, code = R.run_panel(corpora, tmp_path, run)
    assert code == 1
    assert [p for p in report["problems"] if "treesitter" in p] == [
        "cics-genapp:treesitter exited 3",
        "zecs:treesitter exited 3",
    ]
    assert any("zecs" in " ".join(c) and "mapa_adapter.py" in c[1] for c in seen)


def test_a_referee_that_parsed_nothing_fails_the_run(tmp_path):
    run, _ = stub(unparsed="che4z")
    report, code = R.run_panel(R.panel_corpora(["zecs"]), tmp_path, run)
    assert code == 1 and report["problems"] == ["zecs: che4z parsed none of 1 members"]


def test_a_referee_that_parsed_one_corpus_but_not_another_is_a_note(tmp_path):
    """tree-sitter cannot read dbb's CBL cards, yet parses the other corpora: a finding, not a failed run."""

    def run(cmd, cwd):
        if "--out" in cmd and "--corpus" in cmd:
            out = Path(cmd[cmd.index("--out") + 1])
            corpus = cmd[cmd.index("--corpus") + 1]
            doc = F.new_doc(out.stem, "stub", corpus, [])
            bad = out.stem == "treesitter" and corpus == "zecs"
            F.add_file(doc, "A.cbl", {}, status="fail" if bad else "ok")
            F.dump(doc, out)
        return 0

    report, code = R.run_panel(R.panel_corpora(["cics-genapp", "zecs"]), tmp_path, run)
    assert code == 0 and report["problems"] == []
    assert report["notes"] == ["zecs: treesitter parsed none of 1 members"]


def test_a_referee_with_no_members_in_a_corpus_is_not_a_problem(tmp_path):
    def run(cmd, cwd):
        if "--out" in cmd and "--corpus" in cmd:
            out = Path(cmd[cmd.index("--out") + 1])
            F.dump(F.new_doc(out.stem, "stub", cmd[cmd.index("--corpus") + 1], []), out)
        return 0

    report, code = R.run_panel(R.panel_corpora(["zecs"]), tmp_path, run)
    assert code == 0 and report["problems"] == [] and "notes" not in report


def test_main_without_referees_exits_2_and_runs_nothing(tmp_path, capsys):
    assert R.main(["--out", str(tmp_path / "o")], env={}) == 2
    assert not (tmp_path / "o").exists()
    # a dry run needs no referee
    assert R.main(["--out", str(tmp_path / "o"), "--corpus", "zecs", "--dry-run"], env={}) == 0
    assert "zecs:che4z" in capsys.readouterr().out
    assert not (tmp_path / "o").exists()
