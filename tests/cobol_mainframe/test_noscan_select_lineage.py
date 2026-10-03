"""#3998: the refractor's no-scan lineage (cobol_dag_architect) reads SELECT ... ASSIGN
with the engine's own reader, so a program gets the same `analysis.lineage` with and
without `--scan`.

The no-scan reader was a second regex run over a literal-blanked view: `ASSIGN TO "x"`
read the DD as `TO`, `SELECT OPTIONAL f` took OPTIONAL as the file, and a Japanese /
full-width file name never matched, so those files dropped out of the lineage.
"""

import json
from pathlib import Path

import pytest

from gitgalaxy.core.mainframe_boundary import cobol_select_assigns
from gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect import extract_lineage

# One SELECT of each form: ASSIGN TO literal, OPTIONAL, a Japanese file name, a
# full-width-digit name, a literal with no TO, a UT-S- device prefix, and a plain DD.
PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ASGTO.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO "./IN-FILE"
                  ORGANIZATION LINE SEQUENTIAL.
           SELECT OPTIONAL OUT-FILE ASSIGN TO OUTDD.
           SELECT 顧客ファイル ASSIGN TO CUSTDD.
           SELECT 明細１ ASSIGN TO DTLDD.
           SELECT LIT-FILE ASSIGN 'LITDD'.
           SELECT TAPE-FILE ASSIGN TO UT-S-TAPEDD.
           SELECT PLAIN-FILE ASSIGN TO PLAINDD.
       DATA DIVISION.
       FILE SECTION.
       FD IN-FILE.
       01 IN-REC PIC X(10).
       FD OUT-FILE.
       01 OUT-REC PIC X(10).
       FD 顧客ファイル.
       01 顧客レコード PIC X(10).
       FD 明細１.
       01 明細レコード PIC X(10).
       FD LIT-FILE.
       01 LIT-REC PIC X(10).
       FD TAPE-FILE.
       01 TAPE-REC PIC X(10).
       FD PLAIN-FILE.
       01 PLAIN-REC PIC X(10).
       PROCEDURE DIVISION.
           OPEN INPUT IN-FILE 顧客ファイル LIT-FILE
                OUTPUT OUT-FILE 明細１
                I-O TAPE-FILE
                EXTEND PLAIN-FILE.
           READ IN-FILE.
           WRITE OUT-REC FROM IN-REC.
           CLOSE IN-FILE OUT-FILE 顧客ファイル 明細１ LIT-FILE TAPE-FILE PLAIN-FILE.
           STOP RUN.
"""

EXPECTED = {
    "inputs": ["./IN-FILE", "CUSTDD", "LITDD", "PLAINDD", "TAPEDD"],
    "outputs": ["DTLDD", "OUTDD", "PLAINDD", "TAPEDD"],
}


# ---- the reader ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("select", "internal", "dd"),
    [
        ('SELECT IN-FILE ASSIGN TO "./in-file".', "IN-FILE", "./IN-FILE"),
        ("SELECT IN-FILE ASSIGN TO 'INDD'.", "IN-FILE", "INDD"),
        ("SELECT IN-FILE ASSIGN 'INDD'.", "IN-FILE", "INDD"),
        ("SELECT IN-FILE ASSIGN TO INDD.", "IN-FILE", "INDD"),
        ("SELECT IN-FILE ASSIGN INDD.", "IN-FILE", "INDD"),
        ("SELECT OPTIONAL OUT-FILE ASSIGN TO OUTDD.", "OUT-FILE", "OUTDD"),
        ("SELECT 顧客ファイル ASSIGN TO CUSTDD.", "顧客ファイル", "CUSTDD"),
        ("SELECT 明細１ ASSIGN TO DTLDD.", "明細１", "DTLDD"),
        ("SELECT TAPE-FILE ASSIGN TO UT-S-TAPEDD.", "TAPE-FILE", "TAPEDD"),
        ("SELECT TAPE-FILE ASSIGN TO UR-S-TAPEDD.", "TAPE-FILE", "TAPEDD"),
        ("SELECT IN-FILE\n    ASSIGN\n    TO INDD\n    ORGANIZATION IS SEQUENTIAL.", "IN-FILE", "INDD"),
    ],
)
def test_the_reader_maps_each_select_form(select, internal, dd):
    assert cobol_select_assigns(f"       FILE-CONTROL.\n           {select}\n") == {internal: dd}


def test_the_reader_never_takes_to_or_optional_as_a_name():
    got = cobol_select_assigns('SELECT A ASSIGN TO "X".\nSELECT OPTIONAL B ASSIGN TO Y.\n')
    assert got == {"A": "X", "B": "Y"}
    assert "TO" not in got.values() and "OPTIONAL" not in got


def test_the_first_select_of_a_name_wins():
    assert cobol_select_assigns("SELECT A ASSIGN TO X.\nSELECT A ASSIGN TO Y.\n") == {"A": "X"}


# ---- the no-scan lineage --------------------------------------------------------------------
def test_the_noscan_lineage_reads_every_select_form(tmp_path):
    program = tmp_path / "ASGTO.cbl"
    program.write_text(PROGRAM, encoding="utf-8")
    lineage = extract_lineage(program)
    assert sorted(lineage["inputs"]) == EXPECTED["inputs"]
    assert sorted(lineage["outputs"]) == EXPECTED["outputs"]


def test_a_commented_select_is_still_not_read(tmp_path):
    """Keeping literals for the SELECT reader must not bring comment lines back (#3420)."""
    program = tmp_path / "CMT.cbl"
    program.write_text(
        "       PROGRAM-ID. CMT.\n"
        '      *    SELECT IN-FILE ASSIGN TO "GHOST".\n'
        "           SELECT IN-FILE ASSIGN TO REALDD.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN INPUT IN-FILE.\n",
        encoding="utf-8",
    )
    assert extract_lineage(program)["inputs"] == {"REALDD"}


# ---- parity: the refractor gives the same lineage with and without --scan -------------------
def _refractor_lineage(tmp_path: Path, monkeypatch, *flags: str) -> dict:
    from gitgalaxy import cobol_refractor_controller as refractor

    root = tmp_path / ("scan" if flags else "noscan")
    estate = root / "estate"
    estate.mkdir(parents=True)
    (estate / "ASGTO.cbl").write_text(PROGRAM, encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.setattr("sys.argv", ["cobol-refractor", str(estate), *flags])
    refractor.main()
    (clean,) = root.glob("estate_gitgalaxy_clean_*")
    dump = json.loads((clean / "04_ir_state_dumps" / "ASGTO_ir.json").read_text(encoding="utf-8"))
    return dump["analysis"]["lineage"]


def test_noscan_and_scan_lineage_agree(tmp_path, monkeypatch):
    monkeypatch.setenv("GITGALAXY_DISABLE_GIT_HISTORY", "1")
    noscan = _refractor_lineage(tmp_path, monkeypatch)
    scan = _refractor_lineage(tmp_path, monkeypatch, "--scan")
    assert noscan == scan
    assert {k: noscan[k] for k in EXPECTED} == EXPECTED
