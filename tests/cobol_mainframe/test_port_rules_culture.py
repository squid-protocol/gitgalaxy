"""#3833: porting rules for calendars, and LINE SEQUENTIAL files.

Calendars: `Calendar.getInstance()`, `new GregorianCalendar()`, `SimpleDateFormat` and
`WeekFields.of(Locale.getDefault())` follow the JVM's default locale -- Buddhist-era years under th_TH,
the Japanese imperial calendar under ja_JP_JP, Sunday-first weeks in the US -- while COBOL's
DAY-OF-WEEK is Monday = 1. Every ticket carries a rule: java.time, ISO, Locale.ROOT.

LINE SEQUENTIAL: the sequential-dataset rule says RECFM=FB (records back to back, no separators), which
is wrong for a Micro Focus / GnuCOBOL / Windows program whose SELECT is ORGANIZATION IS LINE SEQUENTIAL:
one record per line, short lines padded, trailing spaces stripped on write. A real scan of a small
estate through the refractor and cobol-to-java (as tests/cobol_mainframe/test_port_tickets.py does)
pins that such a program's ticket names its LINE SEQUENTIAL files with that rule, and that a program
with only SEQUENTIAL / INDEXED files keeps exactly today's rules.
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES, line_sequential_rules

# Today's sequential-dataset rule, word for word: a program without LINE SEQUENTIAL files keeps it.
FB_RULE = (
    "A sequential dataset is fixed-length records (RECFM=FB): write each record's toRecord(...) bytes "
    "back to back, with no line separators, to the file DatasetResolver.path(dd) names; read it the same "
    "way."
)

POSTIT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. POSTIT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT TRANS-FILE ASSIGN TO TRANS.
           SELECT ACCT-FILE ASSIGN TO ACCTS
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS AC-ID.
       DATA DIVISION.
       FILE SECTION.
       FD  TRANS-FILE.
       01  TRANS-REC.
           COPY TRANREC.
       FD  ACCT-FILE.
       01  ACCT-REC.
           05  AC-ID            PIC X(8).
           05  AC-BAL           PIC S9(9)V99.
       WORKING-STORAGE SECTION.
       01  WS-TOTAL          PIC S9(9)V99 VALUE 0.
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT TRANS-FILE
           OPEN I-O ACCT-FILE
           PERFORM 100-READ
           CLOSE TRANS-FILE ACCT-FILE
           GOBACK.
       100-READ.
           READ TRANS-FILE
           ADD TR-AMT TO WS-TOTAL.
"""
LINESEQ = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LINESEQ.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CSV-IN ASSIGN TO 'payments.csv'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT RPT-OUT ASSIGN TO 'report.txt'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT TRANS-FILE ASSIGN TO TRANS.
       DATA DIVISION.
       FILE SECTION.
       FD  CSV-IN.
       01  CSV-LINE          PIC X(80).
       FD  RPT-OUT.
       01  RPT-LINE          PIC X(132).
       FD  TRANS-FILE.
       01  TRANS-REC.
           COPY TRANREC.
       WORKING-STORAGE SECTION.
       01  WS-COUNT          PIC 9(7) VALUE 0.
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT CSV-IN TRANS-FILE OUTPUT RPT-OUT
           READ CSV-IN
           ADD 1 TO WS-COUNT
           MOVE CSV-LINE TO RPT-LINE
           WRITE RPT-LINE
           CLOSE CSV-IN TRANS-FILE RPT-OUT
           GOBACK.
"""
TRANREC = """\
           05  TR-ID            PIC X(8).
           05  TR-AMT           PIC S9(7)V99.
"""
JOB = """\
//NIGHTLY  JOB (ACCT),'POST'
//RUN      EXEC PGM=POSTIT,PARM='20260926'
//TRANS    DD DSN=APP.TRANS,DISP=SHR
//ACCTS    DD DSN=APP.ACCTS,DISP=SHR
//RUN2     EXEC PGM=LINESEQ
//TRANS    DD DSN=APP.TRANS,DISP=SHR
"""


@pytest.fixture(scope="module")
def jobs(tmp_path_factory):
    """ai_agent_jobs/ of the estate's generated project (the pipeline of test_port_tickets.py)."""
    base = tmp_path_factory.mktemp("port_rules_culture")
    repo = base / "src_estate"
    files = {"cbl/POSTIT.cbl": POSTIT, "cbl/LINESEQ.cbl": LINESEQ, "cpy/TRANREC.cpy": TRANREC, "jcl/NIGHTLY.jcl": JOB}
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    out = base / "run"
    out.mkdir()
    work = out / "estate"
    shutil.copytree(repo, work)
    db = scan_to_db(repo, out / "scan")
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = out.glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(out / "none.txt")]):
        java_controller.main()
    (java,) = out.glob("estate_gitgalaxy_java_spring_*")
    return java / "ai_agent_jobs"


def _ticket(jobs, key):
    return json.loads((jobs / f"{key}_port_ticket.json").read_text(encoding="utf-8"))


# ---- calendars --------------------------------------------------------------------------
def test_the_calendar_rule_names_java_time_locale_root_and_monday_one():
    rule = next(r for r in PORTING_RULES if "GregorianCalendar" in r)
    assert "java.time" in rule and "Locale.ROOT" in rule and "Monday = 1" in rule
    assert "DayOfWeek.getValue()" in rule and "SimpleDateFormat" in rule and "WeekFields" in rule
    assert "#3833" in rule


def test_every_ticket_carries_the_calendar_rule(jobs):
    for key in ("POSTIT", "LINESEQ"):
        assert any("Monday = 1" in r for r in _ticket(jobs, key)["rules"])


# ---- LINE SEQUENTIAL ----------------------------------------------------------------------
def test_a_line_sequential_program_gets_the_line_sequential_rule(jobs):
    t = _ticket(jobs, "LINESEQ")
    organizations = {f["select_name"]: f["organization"] for f in t["facts"]["sections"]["file_control"]["facts"]}
    assert organizations == {"CSV-IN": "LINE SEQUENTIAL", "RPT-OUT": "LINE SEQUENTIAL", "TRANS-FILE": None}
    extra = t["rules"][len(PORTING_RULES) :]
    assert len(extra) == 1
    (rule,) = extra
    assert rule.startswith("This program's CSV-IN, RPT-OUT are ORGANIZATION LINE SEQUENTIAL")
    assert "one record per line" in rule and "pad a short line with spaces" in rule
    assert "strip the record's trailing spaces" in rule and "\\n" in rule and "Windows" in rule
    assert FB_RULE in t["rules"]  # TRANS-FILE is still RECFM=FB
    md = (jobs / "LINESEQ_port_ticket.md").read_text(encoding="utf-8")
    assert "## Files (FILE-CONTROL)" in md
    assert "| CSV-IN | payments.csv | LINE SEQUENTIAL |" in md
    assert "| TRANS-FILE | TRANS | SEQUENTIAL (default) |" in md


def test_a_program_without_line_sequential_files_keeps_todays_rules(jobs):
    t = _ticket(jobs, "POSTIT")
    organizations = {f["select_name"]: f["organization"] for f in t["facts"]["sections"]["file_control"]["facts"]}
    assert organizations == {"TRANS-FILE": None, "ACCT-FILE": "INDEXED"}
    assert t["rules"] == PORTING_RULES
    assert FB_RULE in t["rules"]
    assert not any("LINE SEQUENTIAL" in r for r in t["rules"])
    assert "## Files (FILE-CONTROL)" not in (jobs / "POSTIT_port_ticket.md").read_text(encoding="utf-8")


def test_line_sequential_rules_of_one_file_and_of_none():
    (rule,) = line_sequential_rules([{"select_name": "IN", "organization": "LINE SEQUENTIAL"}])
    assert rule.startswith("This program's IN is ORGANIZATION LINE SEQUENTIAL") and "apply to it:" in rule
    assert line_sequential_rules([{"select_name": "A", "organization": "SEQUENTIAL"}, {"select_name": "B"}]) == []
    assert line_sequential_rules([]) == []
