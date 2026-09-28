"""#3805: fresh-estate trials -- the ledger, `trial start` / `sync` / `close` / `report`.

The committed ledger (tests/cobol_mainframe/trials.json) must validate and its page and chart must be
current. A synthetic trial runs end to end on a tiny estate WITHOUT a real model: `trial start` scans,
refracts and converts it (the tickets), freezes the system and declares eligibility; the porting loop
(port_runner) runs with a stand-in `command` backend and a stand-in proof -- one program right at once,
one wrong until a `Trial-Cause: generator` commit lands in a temporary engine repo -- and `sync` shows
proven@1 and proven@2(generator), which the report bins. Start refuses a development estate and a late
exclusion; an exclusion edited into the ledger afterwards fails validation.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java import port_runner as pr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import trial  # noqa: E402


def test_the_ledger_is_valid_and_the_report_is_current():
    ledger = trial.load()
    assert trial.validate(ledger) == []
    assert {e["id"] for e in ledger["estates"] if e["status"] == "development"} >= {
        "aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "zopeneditor-sample",
        "cics-genapp", "zecs", "dsf"}  # fmt: skip
    assert trial.PAGE.read_text(encoding="utf-8") == trial.render(ledger), (
        "stale: python tests/tools/trial.py report --write"
    )
    assert trial.CHART.read_text(encoding="utf-8") == trial.render_svg(ledger), "stale: trial.py report --write"


def _batch(name: str) -> str:
    return f"""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. {name}.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO INFILE.
           SELECT OUT-FILE ASSIGN TO OUTFILE.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC.
           COPY INREC.
       FD  OUT-FILE.
       01  OUT-REC.
           COPY INREC.
       WORKING-STORAGE SECTION.
       01  WS-EOF            PIC X VALUE 'N'.
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT IN-FILE OUTPUT OUT-FILE
           PERFORM UNTIL WS-EOF = 'Y'
               READ IN-FILE AT END MOVE 'Y' TO WS-EOF
               NOT AT END
                   ADD 1 TO IN-AMT
                   WRITE OUT-REC FROM IN-REC
               END-READ
           END-PERFORM
           CLOSE IN-FILE OUT-FILE
           GOBACK.
"""


ONLINE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONLINE1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-MSG            PIC X(20) VALUE 'HELLO'.
       01  WS-TOTAL          PIC S9(7)V99 VALUE 0.
       PROCEDURE DIVISION.
       000-MAIN.
           ADD 1 TO WS-TOTAL
           EXEC CICS SEND TEXT FROM(WS-MSG) END-EXEC
           EXEC CICS RETURN END-EXEC.
"""
INREC = """\
           05  IN-ID            PIC X(8).
           05  IN-AMT           PIC S9(7)V99.
"""


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com"}  # fmt: skip
    argv = ["git", "-C", str(repo), *args]
    return subprocess.run(argv, check=True, capture_output=True, text=True, env=env).stdout  # noqa: S603


def _ledger(path: Path) -> Path:
    """A fresh ledger holding the committed one's development estates (no trials)."""
    committed = trial.load()
    path.write_text(json.dumps({**committed, "trials": []}), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def started(tmp_path_factory):
    base = tmp_path_factory.mktemp("trial")
    estate = base / "estate"
    for rel, text in {"cbl/GOODPGM.cbl": _batch("GOODPGM"), "cbl/FIXPGM.cbl": _batch("FIXPGM"),
                      "cbl/ONLINE1.cbl": ONLINE, "cpy/INREC.cpy": INREC}.items():  # fmt: skip
        (estate / rel).parent.mkdir(parents=True, exist_ok=True)
        (estate / rel).write_text(text, encoding="utf-8")
    engine = base / "engine"  # stands in for the engine checkout: its commits are the fixes
    engine.mkdir()
    _git(engine, "init", "-q")
    (engine / "README").write_text("engine\n", encoding="utf-8")
    _git(engine, "add", "README")
    _git(engine, "commit", "-q", "-m", "the frozen system")
    ledger = _ledger(base / "trials.json")
    common = ["--ledger", str(ledger), "--repo", str(engine)]
    rc = trial.main([*common, "start", "tiny-estate", "--estate-path", str(estate), "--work", str(base / "work"),
                     "--model", "stand-in", "--backend", "command", "--repo-url", "https://example.com/tiny",
                     "--ref", "abc123"])  # fmt: skip
    assert rc == 0
    return {"base": base, "estate": estate, "engine": engine, "ledger": ledger, "common": common,
            "project": base / "work" / "java_h2"}  # fmt: skip


def test_start_freezes_the_system_and_declares_eligibility_up_front(started):
    ledger = trial.load(started["ledger"])
    (t,) = ledger["trials"]
    assert (
        t["estate"] == "tiny-estate"
        and t["system"]["engine_commit"] == _git(started["engine"], "rev-parse", "HEAD").strip()
    )
    assert t["system"]["porting_rules_hash"] == trial.porting_rules_hash()[0] and t["system"]["model"] == "stand-in"
    assert t["eligible"] == ["FIXPGM", "GOODPGM"]
    assert t["out_of_scope"]["ONLINE1"].startswith("online (EXEC CICS)")
    assert (started["project"] / "ai_agent_jobs" / "FIXPGM_port_ticket.json").is_file()
    estate = next(e for e in ledger["estates"] if e["id"] == "tiny-estate")
    assert (estate["status"], estate["trialled_by"], estate["repo"], estate["ref"]) == (
        "development", t["id"], "https://example.com/tiny", "abc123")  # fmt: skip


def test_start_refuses_a_development_estate_and_a_late_exclusion(started, tmp_path):
    common = started["common"]
    for estate in ("aws-mainframe-modernization-carddemo", "tiny-estate"):  # built against / already trialled
        with pytest.raises(SystemExit, match="development estate"):
            trial.main([*common, "start", estate, "--estate-path", str(started["estate"]), "--work", str(tmp_path),
                        "--model", "m", "--backend", "command", "--exclude", "FIXPGM=too hard"])  # fmt: skip
    ledger = trial.load(started["ledger"])
    t = ledger["trials"][0]
    t["out_of_scope"]["FIXPGM"] = "declared: too hard"  # hiding a failure after the fact
    t["eligible"].remove("FIXPGM")
    t["programs"].pop("FIXPGM")
    assert any("eligibility changed after start" in e for e in trial.validate(ledger))


def _backend(tmp_path: Path) -> str:
    """A stand-in model: GOODPGM right at once; FIXPGM right only once the engine repo has a FIXED marker."""
    script = tmp_path / "backend.py"
    script.write_text(
        "import sys, pathlib\n"
        "prompt = pathlib.Path(sys.argv[1]).read_text()\n"
        "right = 'port GOODPGM' in prompt or pathlib.Path(sys.argv[2], 'FIXED').is_file()\n"
        "print('```java\\npackage x;\\n// ' + ('RIGHT' if right else 'WRONG') + '\\n```')\n",
        encoding="utf-8",
    )
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))} {{prompt_file}} {shlex.quote(str(tmp_path))}"


def _proof(tmp_path: Path) -> str:
    """A stand-in harness: proven when the port says RIGHT."""
    script = tmp_path / "proof.py"
    script.write_text("import sys, pathlib\n"
                      "port = next(pathlib.Path(sys.argv[1]).rglob('*.java')).read_text()\n"
                      "sys.exit(0 if 'RIGHT' in port else 1)\n", encoding="utf-8")  # fmt: skip
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))} {{port_dir}} {{report_dir}}"


def _attempt(project: Path, key: str, backend: str, proof: str) -> None:
    assert pr.main(["run", str(project), "--ticket", key, "--backend", "command", "--model", "stand-in",
                    "--command", backend]) == 0  # fmt: skip
    pr.main(["prove", str(project), "--ticket", key, "--command", proof])


def test_a_synthetic_trial_end_to_end(started, tmp_path):
    project, engine, common = started["project"], started["engine"], started["common"]
    trial_id = trial.load(started["ledger"])["trials"][0]["id"]
    backend, proof = _backend(tmp_path), _proof(tmp_path)
    _attempt(project, "GOODPGM", backend, proof)
    _attempt(project, "FIXPGM", backend, proof)
    assert trial.main([*common, "sync", trial_id, "--project", str(project)]) == 0
    progs = trial.load(started["ledger"])["trials"][0]["programs"]
    assert (progs["GOODPGM"]["final"], progs["FIXPGM"]["final"]) == ("proven@1", "open")
    assert progs["FIXPGM"]["attempts"][0]["cause"] is None  # nothing has happened since the failure yet

    (tmp_path / "FIXED").write_text("", encoding="utf-8")  # the fix: the generator now gives the model what it needs
    (engine / "gen.py").write_text("fixed\n", encoding="utf-8")
    _git(engine, "add", "gen.py")
    _git(engine, "commit", "-q", "-m", "generator: carry the record layout\n\nTrial-Cause: generator FIXPGM")
    fix = _git(engine, "rev-parse", "HEAD").strip()
    _attempt(project, "FIXPGM", backend, proof)
    for _ in range(2):  # idempotent
        assert trial.main([*common, "attempt", trial_id, "--project", str(project)]) == 0
    ledger = trial.load(started["ledger"])
    fixpgm = ledger["trials"][0]["programs"]["FIXPGM"]
    assert fixpgm["final"] == "proven@2(generator)"
    assert [(a["n"], a["outcome"], a["cause"], a["fix_commit"]) for a in fixpgm["attempts"]] == [
        (1, "failed", "generator", fix), (2, "proven", None, None)]  # fmt: skip

    s = trial.summary(ledger)[ledger["trials"][0]["system"]["engine_version"]]
    assert s["bins"] == {"@1": {"tiny-estate": 1}, "@2": {"tiny-estate": 1}} and (s["first"], s["counted"]) == (1, 2)
    assert trial.headline(ledger).startswith("first-try proof rate: 1/2 (50%) on 1 fresh estates at engine ")
    assert trial.fixes_per_estate(ledger)["tiny-estate"]["generator"] == 1
    page, svg = trial.render(ledger), trial.render_svg(ledger)
    assert "| trial-001 | FIXPGM | proven@2(generator) | 1:failed/generator" in page
    assert "out-of-scope(online (EXEC CICS)" in page
    assert "tiny-estate: 1 @2" in svg and "training data" in svg and "declared up front" in svg

    assert trial.main([*common, "close", trial_id]) == 0
    with pytest.raises(SystemExit, match="closed"):
        trial.main([*common, "sync", trial_id, "--project", str(project)])


def test_a_retry_with_no_fix_is_the_models_and_a_recorded_attempt_is_never_rewritten():
    ev = [{"event": "proposed", "ticket": "P", "attempt": 1, "started": "2026-09-28T10:00:00+00:00",
           "at": "2026-09-28T10:00:05+00:00", "model": "m"},
          {"event": "proof-failed", "ticket": "P", "attempt": 1, "at": "2026-09-28T10:01:00+00:00"},
          {"event": "no-port", "ticket": "P", "attempt": 2, "started": "2026-09-28T10:02:00+00:00",
           "at": "2026-09-28T10:03:00+00:00", "model": "m", "error": "timeout"},
          {"event": "proposed", "ticket": "P", "attempt": 2, "started": "2026-09-28T10:04:00+00:00",
           "at": "2026-09-28T10:05:00+00:00", "model": "m"},
          {"event": "proven", "ticket": "P", "attempt": 2, "at": "2026-09-28T10:06:00+00:00"}]  # fmt: skip
    got = trial.attempts_from_log(ev, "P", [])
    assert [(a["outcome"], a["cause"]) for a in got] == [("failed", "model"), ("error", "model"), ("proven", None)]
    assert trial.final_of(got) == "proven@3(model,model)"
    t = {"id": "t", "programs": {"P": {"attempts": [{**got[0], "outcome": "no-port"}], "final": "open"}}}
    with pytest.raises(SystemExit, match="never rewritten"):
        trial.sync(t, ev, [])
