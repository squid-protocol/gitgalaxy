"""#3828: CBL / PROCESS compiler options and the DB2 subsystem's DATE / TIME format.

A German, Nordic or French shop may compile with INTDATE(LILIAN) and run DB2 with DATE format EUR.
Neither was read: FUNCTION INTEGER-OF-DATE counts from 1601-01-01 (ANSI) or 1582-10-15 (LILIAN), and
a DB2 DATE fetched into a PIC X(10) on an EUR subsystem reads `26.09.2026`, while the generated Java
assumed ISO. The engine now records each CBL / PROCESS option (compiler_options_data); the port
tickets carry them with a rule per option that changes results; `culture.db2_date_format` drives the
generated Db2Dates; and the equivalence harness turns the options into cobc flags, or refuses a case
GnuCOBOL cannot honour (it has no INTDATE).
"""

import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.compiler_options import cards, compiler_options, effective, intdate, parse_options
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_db2_forge import db2_dates_source
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import (
    PORTING_RULES,
    build_ticket,
    option_rules,
    ticket_markdown,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_common as common  # noqa: E402

_JDK = Path("/usr/lib/jvm/java-17-openjdk-amd64/bin")

LILIAN = (
    "000100 CBL INTDATE(LILIAN),TRUNC(BIN) AR(E)                               LILIAN01\n"
    "      * a comment between the cards\n"
    "       PROCESS NUMPROC(PFD) YW(1950),NOSQL\n"
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. LILIAN.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-DAYS PIC 9(8).\n"
    "       PROCEDURE DIVISION.\n"
    "           COMPUTE WS-DAYS = FUNCTION INTEGER-OF-DATE(20260926)\n"
    "           PERFORM\n"
    "           PROCESS THRU PROCESS-EXIT.\n"
    "           GOBACK.\n"
    "       PROCESS.\n"
    "       PROCESS-EXIT.\n"
    "           EXIT.\n"
    "       END PROGRAM LILIAN.\n"
    "       CBL INTDATE(ANSI)\n"
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. SECOND.\n"
)


# ---- the fact -------------------------------------------------------------------------
def test_the_cards_are_read_with_abbreviations_spelled_out():
    rows = compiler_options(LILIAN)
    assert [(r["option"], r["value"], r["written"], r["line"]) for r in rows] == [
        ("INTDATE", "LILIAN", "INTDATE(LILIAN)", 1),
        ("TRUNC", "BIN", "TRUNC(BIN)", 1),
        ("ARITH", "EXTEND", "AR(E)", 1),  # AR(E) is ARITH(EXTEND); columns 73-80 are not the card
        ("NUMPROC", "PFD", "NUMPROC(PFD)", 3),
        ("YEARWINDOW", "1950", "YW(1950)", 3),
        ("NOSQL", None, "NOSQL", 3),
        ("INTDATE", "ANSI", "INTDATE(ANSI)", 18),  # a batch compile: the next program's card
    ]
    # `PROCESS THRU ...` continuing a PERFORM, and the paragraph `PROCESS.`, are not cards
    assert [n for n, _ in cards(LILIAN)] == [1, 3, 18]


def test_a_value_keeps_its_quotes_and_nested_parentheses():
    assert parse_options(" CICS('SP,EDF'), SQL(\"A(B)\") NODYNAM") == [
        ("CICS", "'SP,EDF'", "CICS('SP,EDF')"),
        ("SQL", '"A(B)"', 'SQL("A(B)")'),
        ("NODYNAM", None, "NODYNAM"),
    ]
    assert parse_options("NOCURR,CP(1141) Q") == [("NOCURRENCY", None, "NOCURR"), ("CODEPAGE", "1141", "CP(1141)"),
                                                  ("QUOTE", None, "Q")]  # fmt: skip


def test_the_last_card_wins_and_a_no_form_cancels():
    rows = compiler_options(LILIAN)
    assert intdate(rows) == "ANSI"  # the second program's card comes last
    assert intdate(rows[:6]) == "LILIAN"
    assert intdate([]) == "ANSI"  # the IBM default
    now = effective([{"option": "SQL", "value": None}, {"option": "NOSQL", "value": None}])
    assert now == {"NOSQL": None}


def test_no_cards_no_rows():
    assert compiler_options("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. X.\n") == []
    assert compiler_options("") == []
    # a copybook that starts with a paragraph named PROCESS-RECORD holds no card
    assert compiler_options("       PROCESS-RECORD.\n           EXIT.\n") == []


def test_extract_boundary_carries_the_options():
    assert extract_boundary("cobol", LILIAN)["compiler_options"][0]["option"] == "INTDATE"


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("regional")
    repo = base / "estate"
    (repo / "cbl").mkdir(parents=True)
    (repo / "cbl" / "LILIAN.cbl").write_text(LILIAN, encoding="utf-8")
    (repo / "cbl" / "PLAIN.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. PLAIN.\n       PROCEDURE DIVISION.\n           GOBACK.\n",
        encoding="utf-8",
    )
    return scan_to_db(repo, base / "scan")


def test_the_scan_records_and_the_ir_reads_the_options(scanned):
    ir = load_galaxy_ir(scanned)
    lilian = ir.files["cbl/LILIAN.cbl"]
    assert [(o.option, o.value, o.line) for o in lilian.compiler_options][:2] == [
        ("INTDATE", "LILIAN", 1),
        ("TRUNC", "BIN", 1),
    ]
    assert lilian.compiler_option("TRUNC") == "BIN"
    assert ir.files["cbl/PLAIN.cbl"].compiler_options == []
    assert ir.files["cbl/PLAIN.cbl"].compiler_option("INTDATE", "ANSI") == "ANSI"
    with sqlite3.connect(scanned) as conn:
        assert conn.execute("SELECT COUNT(*) FROM compiler_options_data").fetchone()[0] == 7


def test_a_pre_3828_db_loads(scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(scanned, old)
    with sqlite3.connect(old) as conn:
        conn.execute("DROP TABLE compiler_options_data")
    assert load_galaxy_ir(old).files["cbl/LILIAN.cbl"].compiler_options == []


# ---- INTDATE --------------------------------------------------------------------------
def test_the_intdate_rule_counts_as_ibm_does():
    """The rule's day zeros give IBM's documented day 1 and the 6653-day offset between the two."""
    date = datetime.date(2026, 9, 26)
    ansi = (date - datetime.date(1600, 12, 31)).days
    lilian = (date - datetime.date(1582, 10, 14)).days
    assert ansi == 155497  # what GnuCOBOL (ANSI) returns for INTEGER-OF-DATE(20260926)
    assert lilian - ansi == 6653
    rule = next(r for r in PORTING_RULES if "INTDATE(LILIAN)" in r)
    assert "1600-12-31" in rule and "1582-10-14" in rule and "6653" in rule


def test_the_ticket_carries_the_options_and_their_rules(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "LILIAN.cbl").write_text(LILIAN.replace("       CBL INTDATE(ANSI)\n", ""), encoding="utf-8")
    skeleton = {"program": {"file": "LILIAN.cbl", "language": "cobol", "program_ids": ["LILIAN"]}, "sections": {}}
    t = build_ticket("LILIAN", skeleton, tmp_path, "com.acme", tmp_path / "src", None, [], {}, None)
    assert t["compiler_options"][0] == {"option": "INTDATE", "value": "LILIAN", "written": "INTDATE(LILIAN)",
                                        "line": 1}  # fmt: skip
    extra = t["rules"][len(PORTING_RULES) :]
    assert any(r.startswith("This program's CBL / PROCESS card (line 1) sets INTDATE(LILIAN)") for r in extra)
    assert any("TRUNC(BIN)" in r for r in extra) and any("ARITH(EXTEND)" in r for r in extra)
    assert any("NUMPROC(PFD)" in r for r in extra)
    md = ticket_markdown(t)
    assert "## Compiler options (CBL / PROCESS cards)" in md and "| 1 | INTDATE(LILIAN) | `INTDATE(LILIAN)` |" in md
    json.dumps(t)


def test_default_options_add_no_rules():
    assert option_rules([]) == []
    assert option_rules([{"option": "INTDATE", "value": "ANSI", "line": 1}]) == []


# ---- DB2 DATE / TIME formats ------------------------------------------------------------
def test_the_db2_rule_names_every_format():
    rule = next(r for r in PORTING_RULES if "db2_date_format" in r)
    assert "26.09.2026" in rule and "09/26/2026" in rule and "Db2Dates" in rule


def test_db2_dates_carries_the_configured_format():
    eur = db2_dates_source("com.acme", "eur")
    assert eur.startswith("package com.acme.repository.db2;")
    assert 'FORMAT = "EUR"' in eur and 'ofPattern("dd.MM.uuuu", Locale.US)' in eur and "reads 26.09.2026" in eur
    assert "TODO" not in eur
    local = db2_dates_source("com.acme", "local")
    assert "TODO(#3828)" in local and "DATE = LOCAL_DATE;" in local


_RUNNER = """package t;
import java.time.*;
import t.repository.db2.Db2Dates;
public class Runner {
    public static void main(String[] a) {
        try {
            run();
        } catch (IllegalStateException e) {
            System.out.println("LOCAL");
        }
    }

    static void run() {
        System.out.println(Db2Dates.date(java.sql.Date.valueOf("2026-09-26")));
        System.out.println(Db2Dates.time(java.sql.Time.valueOf("14:30:05")));
        System.out.println(Db2Dates.timestamp(java.sql.Timestamp.valueOf("2026-09-26 14:30:05.123456")));
        System.out.println(Db2Dates.parseDate("26.09.2026") + " " + Db2Dates.parseDate("09/26/2026")
            + " " + Db2Dates.parseDate("2026-09-26") + " " + Db2Dates.parseDate("1.2.2026"));
        System.out.println(Db2Dates.parseTime("14.30.05") + " " + Db2Dates.parseTime("14:30:05") + " "
            + Db2Dates.parseTime("02:30 PM") + " " + Db2Dates.parseTime("2 pm"));
        System.out.println(Db2Dates.parseTimestamp("2026-09-26-14.30.05.123456"));
        System.out.println(Db2Dates.date(Db2Dates.parseDate(Db2Dates.date(LocalDate.of(2026, 9, 26)))));
        try {
            Db2Dates.parseDate("31.02.2026");
            System.out.println("accepted");
        } catch (RuntimeException e) {
            System.out.println("rejected");
        }
        System.out.println(Db2Dates.date(null) + " " + Db2Dates.date("2026-09-26"));
    }
}
"""


@pytest.mark.skipif(not (_JDK / "javac").exists(), reason="no JDK 17")
@pytest.mark.parametrize(
    "fmt, date, time",
    [("eur", "26.09.2026", "14.30.05"), ("usa", "09/26/2026", "02:30 PM"), ("iso", "2026-09-26", "14.30.05"),
     ("jis", "2026-09-26", "14:30:05"), ("local", None, None)],
)  # fmt: skip
def test_db2_dates_formats_and_parses_as_db2(tmp_path, fmt, date, time):
    pkg = tmp_path / "t" / "repository" / "db2"
    pkg.mkdir(parents=True)
    (pkg / "Db2Dates.java").write_text(db2_dates_source("t", fmt), encoding="utf-8")
    (tmp_path / "t" / "Runner.java").write_text(_RUNNER, encoding="utf-8")
    sources = [str(p) for p in tmp_path.rglob("*.java")]
    subprocess.run([str(_JDK / "javac"), "-d", str(tmp_path / "out"), *sources], check=True)  # noqa: S603
    out = subprocess.run([str(_JDK / "java"), "-cp", str(tmp_path / "out"), "t.Runner"],  # noqa: S603
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert out.returncode == 0, out.stderr
    lines = out.stdout.splitlines()
    if fmt == "local":  # no exit patterns set yet: formatting refuses rather than guess
        assert lines == ["LOCAL"]
        return
    assert lines[0] == date and lines[1] == time
    assert lines[2] == "2026-09-26-14.30.05.123456"
    assert lines[3] == "2026-09-26 2026-09-26 2026-09-26 2026-02-01"  # DB2 reads every format on input
    assert lines[4] == "14:30:05 14:30:05 14:30 14:00"
    assert lines[5] == "2026-09-26T14:30:05.123456"
    assert lines[6] == date
    assert lines[7] == "rejected"
    assert lines[8] == f"null {date}"


# ---- the equivalence harness ------------------------------------------------------------
PLAIN = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"


def test_the_harness_default_is_ibms():
    """#4102: no option named is IBM's defaults -- TRUNC(STD) is GnuCOBOL's -fbinary-truncate (`-std=ibm` alone keeps a
    binary item's bytes, TRUNC(BIN)); the other defaults are GnuCOBOL's own behaviour."""
    assert common.compile_options({}, PLAIN) == (PLAIN, ["-fbinary-truncate"])


def test_the_harness_maps_what_gnucobol_can_honour():
    text, flags = common.compile_options({"compiler_options": ["TRUNC(BIN)"]}, PLAIN)
    assert text == PLAIN and flags == ["-fnotrunc"]
    # the program's own cards are blanked (GnuCOBOL rejects CBL) and override the case's PARM
    src = "       CBL TRUNC(STD),APOST,CICS('SP,EDF')\n" + PLAIN
    text, flags = common.compile_options({"compiler_options": ["TRUNC(BIN)"]}, src)
    assert text == "\n" + PLAIN and flags == ["-fbinary-truncate"]


@pytest.mark.parametrize("option", ["INTDATE(LILIAN)", "ARITH(EXTEND)"])  # TRUNC(OPT): test_trunc_opt.py (#4706)
def test_the_harness_refuses_what_gnucobol_cannot_honour(option):
    with pytest.raises(common.UnsupportedOption, match="GnuCOBOL 3.1 has no equivalent"):
        common.compile_options({"compiler_options": [option]}, PLAIN)
    with pytest.raises(common.UnsupportedOption):
        common.compile_options({}, f"       PROCESS {option}\n" + PLAIN)


PROBE = """       CBL TRUNC(BIN)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROBE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DAYS PIC 9(8).
       01  WS-BIN  PIC S9(4) COMP.
       PROCEDURE DIVISION.
           COMPUTE WS-DAYS = FUNCTION INTEGER-OF-DATE(20260926)
           DISPLAY WS-DAYS
           MOVE 9999 TO WS-BIN
           ADD 1 TO WS-BIN
           DISPLAY WS-BIN
           GOBACK.
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL)")
def test_gnucobol_runs_the_cards_as_flags(tmp_path):
    """GnuCOBOL's INTEGER-OF-DATE is ANSI (the rule's count), and TRUNC(BIN) reaches it as -fnotrunc."""
    text, flags = common.compile_options({}, PROBE)
    assert flags == ["-fnotrunc"]
    (tmp_path / "PROBE.cbl").write_text(text, encoding="ascii")
    out = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", common.IMAGE,  # noqa: S603, S607
                          "sh", "-c", f"cobc -x -std=ibm {' '.join(flags)} -o probe PROBE.cbl && ./probe"],
                         capture_output=True, text=True, check=True).stdout.split()  # fmt: skip
    assert int(out[0]) == 155497
    assert int(out[1].rstrip("+")) == 10000  # TRUNC(BIN): the halfword holds 10000, not 0000
