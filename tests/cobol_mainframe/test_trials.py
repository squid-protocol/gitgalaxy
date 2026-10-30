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
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source
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


@pytest.mark.slow(reason="rehearses a whole estate trial (10.5s on a CI runner, limit 15s)")
def test_preview_rehearses_any_estate_and_writes_no_ledger(started, tmp_path, capsys):
    ledger_path = started["ledger"]
    before = ledger_path.read_bytes()
    out_json = tmp_path / "decl.json"
    # a burned estate id and an already trialled one are both accepted: a rehearsal is never first-try
    for estate in ("aws-mainframe-modernization-carddemo", "tiny-estate"):
        rc = trial.main(["--ledger", str(ledger_path), "preview", estate, "--estate-path", str(started["estate"]),
                         "--work", str(tmp_path / f"w-{estate}"), "--json", str(out_json)])  # fmt: skip
        assert rc == 0
    text = capsys.readouterr().out
    assert "eligible: 2  out of scope: 1" in text and "online (EXEC CICS)" in text
    decl = json.loads(out_json.read_text(encoding="utf-8"))
    assert decl["eligible"] == ["FIXPGM", "GOODPGM"] and list(decl["out_of_scope"]) == ["ONLINE1"]
    assert ledger_path.read_bytes() == before  # no trial, no status change
    ledger = trial.load(ledger_path)
    assert (
        next(e for e in ledger["estates"] if e["id"] == "aws-mainframe-modernization-carddemo")["status"]
        == "development"
    )


def test_preview_honours_declared_exclusions(started, tmp_path, capsys, monkeypatch):
    # Both calls scan the same estate: run the scan once (it is the whole cost; the declaration is what is under test).
    import java_target_matrix as jtm

    cache: dict[str, object] = {}
    for name in ("refactor", "generate"):
        real = getattr(jtm, name)

        def once(*a, _real=real, _name=name, **kw):
            if _name not in cache:
                cache[_name] = _real(*a, **kw)
            return cache[_name]

        monkeypatch.setattr(jtm, name, once)
    rc = trial.main(["--ledger", str(started["ledger"]), "preview", "x", "--estate-path", str(started["estate"]),
                     "--work", str(tmp_path / "w"), "--exclude", "FIXPGM=too hard"])  # fmt: skip
    assert rc == 0
    assert "declared: too hard" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="did not find"):
        trial.main(["--ledger", str(started["ledger"]), "preview", "x", "--estate-path", str(started["estate"]),
                    "--work", str(tmp_path / "w2"), "--exclude", "NOPE=why"])  # fmt: skip


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


def _proc(body: str, data: str = "") -> str:
    return (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P1.\n       DATA DIVISION.\n"
        f"       WORKING-STORAGE SECTION.\n{data}       PROCEDURE DIVISION.\n{body}"
    )


def test_display_is_an_output_channel_but_only_as_a_statement():
    """#3806: SYSOUT is compared (#4056), so a program that only DISPLAYs is eligible; a USAGE DISPLAY clause,
    a DISPLAY-... name, a comment or a data-division mention is not a statement."""
    sk = {"program": {"language": "cobol"}}
    shows = _proc("           DISPLAY 'HELLO'\n           GOBACK.\n")
    assert trial.out_of_scope_reason(sk, shows, False) is None
    for text in (
        _proc("           GOBACK.\n", "       01  WS-A PIC 9 USAGE DISPLAY.\n"),
        _proc("           MOVE 1 TO DISPLAY-COUNT\n           GOBACK.\n"),
        _proc("      * DISPLAY 'NOT A STATEMENT'\n           GOBACK.\n"),
        _proc("           MOVE 1 TO X *> DISPLAY 'x'\n           GOBACK.\n"),
    ):
        assert "sets no RETURN-CODE" in trial.out_of_scope_reason(sk, text, False)
    writes = {"sections": {"datasets": {"facts": [{"internal_name": "O", "modes": ["OUTPUT"]}]}}, **sk}
    assert trial.out_of_scope_reason(writes, _proc("           GOBACK.\n"), False) is None


def test_return_code_is_an_output_channel_but_only_when_set():
    """#3806: the harness compares the step's RETURN-CODE, so a program that sets it is eligible; a read, a
    comment, a longer name or a data-division mention is not a set."""
    sk = {"program": {"language": "cobol"}}
    for body in (
        "           MOVE 4 TO RETURN-CODE\n           GOBACK.\n",
        "           ADD 1 TO RETURN-CODE\n           GOBACK.\n",
        "           COMPUTE RETURN-CODE = WS-A + 1\n           GOBACK.\n",
        "           ADD 1 TO WS-A GIVING RETURN-CODE\n           GOBACK.\n",
    ):
        assert trial.out_of_scope_reason(sk, _proc(body), False) is None, body
    for text in (
        _proc("           MOVE RETURN-CODE TO WS-A\n           GOBACK.\n"),
        _proc("      * MOVE 4 TO RETURN-CODE\n           GOBACK.\n"),
        _proc("           MOVE 4 TO WS-RETURN-CODE\n           GOBACK.\n"),
        _proc("           MOVE 4 TO RETURN-CODE-X\n           GOBACK.\n"),
        _proc("           GOBACK.\n", "       01  WS-A PIC 9.\n           MOVE 4 TO RETURN-CODE.\n"),
    ):
        assert "sets no RETURN-CODE" in trial.out_of_scope_reason(sk, text, False), text


def test_abend_is_an_output_channel_but_only_as_a_call_to_the_stub():
    """#3806: the harness records a CEE3ABD abend and a proof needs the same abend on both sides, so a program
    that calls the stub is eligible; a comment, a data-division mention, a variable target or ILBOABN0 (no stub)
    is not."""
    sk = {"program": {"language": "cobol"}}
    for body in (
        "           CALL 'CEE3ABD' USING WS-CODE WS-TIMING\n           GOBACK.\n",
        '           CALL "CEE3ABD" USING WS-CODE WS-TIMING\n           GOBACK.\n',
    ):
        assert trial.out_of_scope_reason(sk, _proc(body), False) is None, body
    for text in (
        _proc("      * CALL 'CEE3ABD' USING X\n           GOBACK.\n"),
        _proc("           CALL WS-CEE3ABD USING X\n           GOBACK.\n"),
        _proc("           CALL 'ILBOABN0' USING X\n           GOBACK.\n"),
        _proc("           GOBACK.\n", "       01  WS-A PIC X VALUE 'CEE3ABD'.\n           CALL 'CEE3ABD'.\n"),
    ):
        assert "does not abend" in trial.out_of_scope_reason(sk, text, False), text


def _fd_program(select_fd: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P1.\n       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n       FILE-CONTROL.\n           SELECT IN-FILE ASSIGN TO INFILE.\n"
        f"       DATA DIVISION.\n       FILE SECTION.\n{select_fd}"
        "       WORKING-STORAGE SECTION.\n       01  WS-A PIC X.\n       PROCEDURE DIVISION.\n"
        "           DISPLAY 'X'\n           GOBACK.\n"
    )


def test_an_inline_fd_record_is_a_layout_but_only_with_an_01_and_pictures():
    """#3806: layout_fields reads an FD record from the program itself, so an inline 01 with PICTURE items is a
    layout; an FD with no record, no picture or only a comment is not. A COPY in the FD still is."""
    sk = {
        "program": {"language": "cobol"},
        "sections": {
            "datasets": {"facts": [{"internal_name": "IN-FILE", "modes": ["INPUT"]}]},
            "file_control": {"facts": [{"select_name": "IN-FILE", "fd_copies": None}]},
        },
    }
    inline = (
        "       FD  IN-FILE.\n       01  IN-REC.\n           05 IN-ID  PIC 9(5).\n           05 IN-REST PIC X(10).\n"
    )
    assert trial.out_of_scope_reason(sk, _fd_program(inline), False) is None
    indexed = {
        **sk,
        "sections": {**sk["sections"], "datasets": {"facts": [{"internal_name": "IN-FILE", "modes": ["I-O"]}]}},
    }
    assert trial.out_of_scope_reason(indexed, _fd_program(inline), False) is None
    for fd in (
        "       FD  IN-FILE.\n",
        "       FD  IN-FILE\n           RECORD CONTAINS 80 CHARACTERS.\n       01  IN-REC.\n",
        "      * FD  IN-FILE.\n      * 01  IN-REC.\n      *     05 IN-ID PIC 9(5).\n",
        "       FD  OTHER-FILE.\n       01  O-REC.\n           05 O-ID PIC 9(5).\n",
    ):
        assert "no record layout" in trial.out_of_scope_reason(sk, _fd_program(fd), False), fd
    # the next FD's record is not this FD's layout
    two = "       FD  IN-FILE.\n       FD  OUT-FILE.\n       01  O-REC.\n           05 O-ID PIC 9(5).\n"
    assert "no record layout" in trial.out_of_scope_reason(sk, _fd_program(two), False)
    # shipped data needs no layout
    assert trial.out_of_scope_reason(sk, _fd_program("       FD  IN-FILE.\n"), True) is None


_UNLOCKED = ("CBACT01C", "CBACT02C", "CBACT03C", "CBACT04C", "CBCUS01C", "CBIMPORT", "CBTRN01C", "CBTRN02C", "CBTRN03C")
_FD_RECORD = re.compile(r"^.{6}\s*FD\s+([A-Z0-9-]+)[^\n]*\n(?:[^\n]*\n)*?.{6}\s*01\s+([A-Z0-9-]+)", re.M)


def test_every_inline_fd_record_of_the_unlocked_carddemo_programs_lays_out():
    """#3806: the nine CardDemo programs #5551 made eligible declare their records inline. Eligibility only says
    a layout exists; the generator must read it. Each FD record lays out through layout_fields, using the estate's
    copy directories. CBIMPORT's input record is built from COPY members (resolved only through app/cpy) and
    holds a REDEFINES (CVEXPORT): the generator fills the first alternative only (harness_report's `redefines`
    blocker), so that program's generated inputs need a hand rule. Burned estate only."""
    import equivalence_common as common

    base = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", "")) / "aws-mainframe-modernization-carddemo"
    if not (base / "app" / "cbl").is_dir():
        pytest.skip("CardDemo corpus not checked out")
    dirs = [base / "app" / "cpy", base / "app" / "cbl"]
    for prog in _UNLOCKED:
        rel = f"app/cbl/{prog}.cbl"
        found = _FD_RECORD.findall(read_source(base / rel).text)
        assert found, f"{prog}: no FD record found"
        for fd, record in found:
            assert common.layout_fields(base, rel, record, copy_dirs=dirs), f"{prog} {fd}: {record} has no fields"
    # without the estate's copy directory the COPY members do not resolve: named, not silent
    with pytest.raises(common.LayoutError):
        common.layout_fields(base, "app/cbl/CBIMPORT.cbl", "EXPORT-INPUT-RECORD")


# ---- #4493: the per-estate harness page ---------------------------------------------------
def _synthetic_ledger(private: bool = False) -> dict:
    def prog(final, attempts):
        return {"final": final, "attempts": attempts}

    def att(n, outcome, cause):
        return {"n": n, "outcome": outcome, "cause": cause, "fix_commit": None, "at": "2026-10-25", "model": "m"}

    estate = {
        "id": "fresh-1",
        "kind": "private",
        "status": "development",
        "label": "pilot-A",
        "trialled_by": "trial-001",
    }
    if not private:
        estate = {"id": "fresh-1", "kind": "public", "status": "development", "repo": "https://example.com/r",
                  "ref": "a" * 40, "trialled_by": "trial-001"}  # fmt: skip
    trial = {
        "id": "trial-001", "estate": "fresh-1", "started": "2026-10-25", "closed": None,
        "system": {"engine_version": "v", "model_version": "m", "backend": "command"},
        "eligible": ["A", "B", "C", "D"], "out_of_scope": {"E": "online (CICS)", "F": "online (CICS)"},
        "programs": {
            "A": prog("proven@1", [att(1, "proven", None)]),
            "B": prog("open", [att(1, "failed", "generator")]),
            "C": prog("open", [att(1, "no-port", "generator")]),
            "D": prog("open", []),
        },
    }  # fmt: skip
    return {"estates": [estate], "trials": [trial]}


def test_the_estate_page_puts_each_program_under_one_status_and_one_blocker():
    ledger = _synthetic_ledger()
    page = trial.trial_page(ledger, ledger["trials"][0])
    assert "programs in the estate: 6" in page and "proven: 1 of 4 eligible (25%)" in page
    assert "| B | differs |" in page and "| C | couldn't run |" in page and "| D | not attempted |" in page
    assert "online (CICS) (2): E, F" in page
    blockers = trial.trial_blockers(ledger["trials"][0])
    assert [(b["cause"], b["programs"]) for b in blockers] == [("generator", ["B", "C"]), ("undiagnosed", ["D"])]
    listed = [p for b in blockers for p in b["programs"]]
    assert sorted(listed) == ["B", "C", "D"]  # exactly one blocker each, the proven one under none
    assert "unlocks 2" in page


def test_fixing_a_blocker_drops_the_predicted_number_of_programs():
    ledger = _synthetic_ledger()
    t = ledger["trials"][0]
    before = trial.trial_blockers(t)[0]
    assert before["cause"] == "generator"
    predicted = len(before["programs"])
    for key in before["programs"]:  # the generator fix lands: both programs prove at attempt 2
        t["programs"][key]["attempts"].append(
            {"n": 2, "outcome": "proven", "cause": None, "fix_commit": None, "at": "2026-10-26", "model": "m"}
        )
        t["programs"][key]["final"] = "proven@2(generator)"  # fmt: skip
    after = trial.trial_blockers(t)
    assert [b["cause"] for b in after] == ["undiagnosed"]
    assert (
        sum(len(b["programs"]) for b in trial.trial_blockers(_synthetic_ledger()["trials"][0]))
        - sum(len(b["programs"]) for b in after)
        == predicted
    )


def test_a_private_estate_page_names_only_the_label():
    ledger = _synthetic_ledger(private=True)
    page = trial.trial_page(ledger, ledger["trials"][0])
    assert "pilot-A" in page and "fresh-1" not in page and "example.com" not in page
    assert list(trial.trial_pages(ledger)) == ["pilot-A.md"]


def test_the_estate_pages_are_checked_for_staleness_and_orphans(tmp_path):
    ledger = _synthetic_ledger()
    assert trial.stale_pages(ledger, tmp_path) == ["fresh-1.md"]
    trial.write_pages(ledger, tmp_path)
    assert trial.stale_pages(ledger, tmp_path) == []
    (tmp_path / "gone.md").write_text("x", encoding="utf-8")
    assert trial.stale_pages(ledger, tmp_path) == ["gone.md"]
    assert "[trial-001](trials/fresh-1.md)" in trial.render(ledger)


def test_preview_writes_a_rehearsal_page(started, tmp_path, capsys):
    page = tmp_path / "page.md"
    rc = trial.main([*started["common"], "preview", "tiny-estate", "--estate-path", str(started["estate"]),
                     "--work", str(tmp_path / "w"), "--page", str(page)])  # fmt: skip
    assert rc == 0
    text = page.read_text(encoding="utf-8")
    assert "(rehearsal)" in text and "not attempted" in text and "never first-try" in text


@pytest.mark.slow(reason="starts a whole estate trial (a scan and refract, 16s locally)")
def test_start_sync_close_regenerate_the_estate_pages(started, tmp_path, monkeypatch):
    """#4493: the page is part of the protocol -- no separate `report --write` between a step and `check`."""
    ledger_path = _ledger(tmp_path / "trials.json")
    pages = tmp_path / "pages"
    monkeypatch.setattr(trial, "LEDGER", ledger_path)
    monkeypatch.setattr(trial, "PAGE", tmp_path / "trials.md")
    monkeypatch.setattr(trial, "CHART", tmp_path / "trials.svg")
    monkeypatch.setattr(trial, "PAGES", pages)
    common = ["--ledger", str(ledger_path), "--repo", str(started["engine"])]
    rc = trial.main([*common, "start", "tiny-estate", "--estate-path", str(started["estate"]),
                     "--work", str(tmp_path / "work"), "--model", "stand-in", "--backend", "command",
                     "--repo-url", "https://example.com/tiny", "--ref", "abc123"])  # fmt: skip
    assert rc == 0
    ledger = trial.load(ledger_path)
    assert trial.stale_pages(ledger, pages) == [] and (tmp_path / "trials.md").is_file()
    page = (pages / "tiny-estate.md").read_text(encoding="utf-8")
    assert "proven: 0 of 2 eligible" in page and "not attempted: 2" in page
    assert trial.main([*common, "check"]) == 0
    causes = [f"--cause={k}=generator" for k in ledger["trials"][0]["eligible"]]
    assert trial.main([*common, "close", ledger["trials"][0]["id"], *causes]) == 0
    assert trial.stale_pages(trial.load(ledger_path), pages) == []
    assert "not attempted" in (pages / "tiny-estate.md").read_text(encoding="utf-8")
    assert trial.main([*common, "check"]) == 0


def test_a_step_on_another_ledger_writes_no_repo_pages(started, tmp_path):
    before = trial.PAGE.read_bytes()
    assert trial.refresh_outputs(trial.load(started["ledger"]), started["ledger"]) == 0
    assert trial.PAGE.read_bytes() == before
