"""#7170: a COBOL program's main line is a function_data row (def_shape 'main_line'),
named after its PROGRAM-ID -- and the readers that build a PARAGRAPH inventory from
function_data (GalaxyIR, so the translator and forges) leave it out, while the answer-key
scorer reads it as the program's main line with its real extent.

One real galaxyscope scan, so every reader is pinned against what the engine writes.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key  # noqa: E402
from scan_server import scan_to_db  # noqa: E402

MAINLN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MAINLN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-N  PIC 9(4) VALUE 0.
       01 WS-I  PIC 9(4) VALUE 0.
       PROCEDURE DIVISION.
           MOVE 0 TO WS-N
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 10
               IF WS-I > 5
                   ADD 1 TO WS-N
               END-IF
           END-PERFORM
           PERFORM SHOW-IT
           STOP RUN.
       SHOW-IT.
           DISPLAY WS-N.
"""

NOPARAS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NOPARAS.
       PROCEDURE DIVISION.
           DISPLAY "HELLO"
           IF 1 = 1
               DISPLAY "YES"
           END-IF
           GOBACK.
"""


@pytest.fixture(scope="module")
def db(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("main_line_7170")
    repo = base / "repo"
    repo.mkdir()
    (repo / "MAINLN.cbl").write_text(MAINLN)
    (repo / "NOPARAS.cbl").write_text(NOPARAS)
    return scan_to_db(repo, base / "scan")


def _rows(db: Path, sql: str) -> list[tuple]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_engine_writes_the_main_line_as_a_function(db):
    rows = _rows(
        db,
        "SELECT d.file_path, f.func_name, f.def_shape, f.start_line, f.loc, f.usage_status, f.calls_out_to "
        "FROM function_data f JOIN file_data d ON d.id = f.file_id ORDER BY d.file_path, f.start_line",
    )
    assert rows == [
        ("MAINLN.cbl", "MAINLN", "main_line", 7, 9, 0, '["SHOW-IT"]'),
        ("MAINLN.cbl", "SHOW-IT", None, 16, 2, 0, "[]"),
        ("NOPARAS.cbl", "NOPARAS", "main_line", 3, 6, 0, "[]"),
    ]
    # the #4302 calls-only bucket is gone where a PROGRAM-ID names the main line
    assert _rows(db, "SELECT unit_name FROM synthetic_unit_data") == []


def test_galaxy_ir_unit_inventory_stays_paragraphs_only(db):
    ir = load_galaxy_ir(db)
    assert [u.name for u in ir.files["MAINLN.cbl"].units] == ["SHOW-IT"]
    assert ir.files["NOPARAS.cbl"].units == []


def test_answer_key_scorer_reads_it_as_the_main_line_with_an_extent(db):
    ir = load_galaxy_ir(db)
    graph = cobol_answer_key.engine_unit_graph(db, ir.repo_name, ir.commit_hash)
    (main,) = [u for u in graph["MAINLN.cbl"] if u["name"] == cobol_answer_key.MAIN_LINE]
    assert (main["start"], main["end"], main["calls"], main["synthetic"]) == (7, 15, ["SHOW-IT"], False)
    assert [u["name"] for u in graph["NOPARAS.cbl"]] == [cobol_answer_key.MAIN_LINE]
