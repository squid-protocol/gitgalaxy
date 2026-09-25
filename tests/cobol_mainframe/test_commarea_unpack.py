"""#3655: CICS programs with several inbound COMMAREAs.

A program such as CardDemo's COACTUPC is entered with the shared CARDDEMO-COMMAREA
from the menu and, on re-entry, with a bigger area: that record followed by its own
state. It reads both from an OPAQUE DFHCOMMAREA (`PIC X OCCURS 1 TO 32767 DEPENDING
ON EIBCALEN`) by reference modification:

    MOVE DFHCOMMAREA (1:LENGTH OF SHARED-COMM) TO SHARED-COMM
    MOVE DFHCOMMAREA (LENGTH OF SHARED-COMM + 1:LENGTH OF WS-OWN) TO WS-OWN

A real scan of a small estate pins:
- the extractor keeping the refmod text;
- the IR reading those unpacks into segments (the layout the program reads), plus
  every inbound site, data-driven ones included;
- GENAPP's trap: a program with a declared DFHCOMMAREA that dumps
  `DFHCOMMAREA(1:EIBCALEN)` into an error-message `PIC X` is not unpacking anything;
- the Java: a composite COMMAREA DTO with `fromPrefix`, which the menu's dispatch uses
  instead of a mapping TODO.
"""

import shutil
import sqlite3
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
from gitgalaxy.core.data_moves import data_moves
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

SHARED = """\
       01  SHARED-COMM.
           05 SC-FROM-PGM     PIC X(8).
           05 SC-USER         PIC X(8).
"""

MENU = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENU.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY SHARED.
       01  WS-NEXT            PIC X(8).
       01  WS-OPT             PIC 9.
       PROCEDURE DIVISION.
       000-MAIN.
           IF WS-OPT = 1
               MOVE 'ACCTUPD' TO WS-NEXT
           ELSE
               MOVE 'ACCTVW' TO WS-NEXT
           END-IF.
           EXEC CICS XCTL PROGRAM(WS-NEXT) COMMAREA(SHARED-COMM) END-EXEC.
"""


def _screen(name: str) -> str:
    return f"""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. {name}.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY SHARED.
       01  WS-OWN.
           05 OWN-STATE       PIC X(10).
           05 OWN-COUNT       PIC 9(4).
       01  WS-COMMAREA        PIC X(100).
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05 LK-BYTE         PIC X OCCURS 1 TO 32767 TIMES
                              DEPENDING ON EIBCALEN.
       PROCEDURE DIVISION.
       000-MAIN.
           MOVE DFHCOMMAREA (1:LENGTH OF SHARED-COMM) TO SHARED-COMM
           MOVE DFHCOMMAREA (LENGTH OF SHARED-COMM + 1:
                             LENGTH OF WS-OWN) TO WS-OWN
           MOVE SHARED-COMM TO WS-COMMAREA
           MOVE WS-OWN TO WS-COMMAREA(LENGTH OF SHARED-COMM + 1:
                                      LENGTH OF WS-OWN)
           EXEC CICS RETURN TRANSID('{name[:4]}') COMMAREA(WS-COMMAREA)
                END-EXEC.
"""


ERRDUMP = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ERRDUMP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  CA-ERROR-MSG.
           03 FILLER          PIC X(9) VALUE 'COMMAREA='.
           03 CA-DATA         PIC X(90).
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05 CA-REQUEST-ID   PIC X(6).
           05 CA-RETURN-CODE  PIC 9(2).
       PROCEDURE DIVISION.
       000-MAIN.
           MOVE DFHCOMMAREA(1:EIBCALEN) TO CA-DATA.
           EXEC CICS RETURN END-EXEC.
"""

CSD = """\
 DEFINE TRANSACTION(MENU) GROUP(APP)
        PROGRAM(MENU)
 DEFINE TRANSACTION(ACCT) GROUP(APP)
        PROGRAM(ACCTUPD)
 DEFINE TRANSACTION(ACCV) GROUP(APP)
        PROGRAM(ACCTVW)
 DEFINE TRANSACTION(ERRD) GROUP(APP)
        PROGRAM(ERRDUMP)
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("commarea_unpack")
    repo = base / "estate"
    files = {
        "cbl/MENU.cbl": MENU,
        "cbl/ACCTUPD.cbl": _screen("ACCTUPD"),
        "cbl/ACCTVW.cbl": _screen("ACCTVW"),
        "cbl/ERRDUMP.cbl": ERRDUMP,
        "cpy/SHARED.cpy": SHARED,
        "csd/APP.csd": CSD,
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_the_extractor_keeps_the_reference_modification_text():
    rows = [r for r in data_moves(_screen("ACCTUPD")) if r["source_refmod"] or r["target_refmod"]]
    assert [(r["source"], r["source_refmod_text"], r["target"], r["target_refmod_text"]) for r in rows] == [
        ("DFHCOMMAREA", "1:LENGTH OF SHARED-COMM", "SHARED-COMM", None),
        ("DFHCOMMAREA", "LENGTH OF SHARED-COMM + 1:LENGTH OF WS-OWN", "WS-OWN", None),
        ("WS-OWN", None, "WS-COMMAREA", "LENGTH OF SHARED-COMM + 1:LENGTH OF WS-OWN"),
    ]


def test_the_unpack_is_the_commarea_layout_and_every_inbound_site_is_listed(scanned):
    _, db = scanned
    ir = load_galaxy_ir(db)
    interfaces = ir.program_interfaces()
    acct = interfaces["cbl/ACCTUPD.cbl"]
    unpack = acct["commarea_unpack"]
    assert (unpack["tiled"], unpack["opaque"], unpack["bytes"]) == (True, True, 30)
    assert [(s["record"], s["offset"], s["bytes"]) for s in unpack["segments"]] == [
        ("SHARED-COMM", 0, 16),
        ("WS-OWN", 16, 14),
    ]
    commarea = acct["commarea"]
    assert commarea["basis"] == "unpack" and commarea["bytes"] == 30
    assert [(f["name"], f["offset"]) for f in commarea["fields"]] == [
        ("SC-FROM-PGM", 0),
        ("SC-USER", 8),
        ("OWN-STATE", 16),
        ("OWN-COUNT", 26),
    ]
    # the data-driven menu entry is an inbound site, with the record it passes
    assert ("cbl/MENU.cbl", "XCTL", "moves", "SHARED-COMM") in {
        (r["caller"], r["verb"], r["via"], r["passes"]) for r in acct["inbound"]
    }


def test_a_declared_commarea_dumped_into_a_pic_x_is_not_an_unpack(scanned):
    _, db = scanned
    err = load_galaxy_ir(db).program_interfaces()["cbl/ERRDUMP.cbl"]
    assert err["commarea_unpack"] is None  # CA-DATA is one PIC X(90): a copy, not a record
    assert err["commarea"]["basis"] == "dfhcommarea"  # the declared LINKAGE fields are the truth


def test_the_length_expression_reader(scanned):
    _, db = scanned
    ir = load_galaxy_ir(db)
    ef = ir.files["cbl/ACCTUPD.cbl"]
    assert ir._length_expr(ef, "LENGTH OF SHARED-COMM + 1") == 17
    assert ir._length_expr(ef, "LENGTH OF WS-OWN - 4") == 10
    assert ir._length_expr(ef, "3") == 3
    assert ir._length_expr(ef, "EIBCALEN") is None  # known only at run time
    assert ir._length_expr(ef, "LENGTH OF NO-SUCH") is None


def test_a_pre_3655_db_loads_without_the_refmod_texts(scanned, tmp_path):
    _, db = scanned
    old = tmp_path / "old.db"
    shutil.copy(db, old)
    with sqlite3.connect(old) as conn:
        conn.execute("ALTER TABLE data_move_data DROP COLUMN source_refmod_text")
        conn.execute("ALTER TABLE data_move_data DROP COLUMN target_refmod_text")
    ir = load_galaxy_ir(old)
    moves = ir.files["cbl/ACCTUPD.cbl"].data_moves
    assert moves and all(m.source_refmod_text is None and m.target_refmod_text is None for m in moves)
    # without the texts the unpack cannot be read, so the old rules apply
    assert ir.program_interfaces()["cbl/ACCTUPD.cbl"]["commarea"]["basis"] != "unpack"


def test_the_java_reads_the_unpacked_commarea_and_the_menu_builds_it(scanned, tmp_path):
    from gitgalaxy import cobol_to_java_controller

    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    with patch("sys.argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        cobol_to_java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    src = java / "src/main/java/com/gitgalaxy/modernized"
    dto = (src / "dto/contract/AcctupdCommarea.java").read_text(encoding="utf-8")
    assert "SHARED-COMM + WS-OWN = 30 bytes" in dto
    assert "private SharedComm sharedComm;" in dto and "private AcctupdWsOwn wsOwn;" in dto
    assert "public static AcctupdCommarea fromPrefix(SharedComm sharedComm) {" in dto
    menu = (src / "service/MenuService.java").read_text(encoding="utf-8")
    assert "acctupdService.getObject().handleLink(AcctupdCommarea.fromPrefix((SharedComm) request))" in menu
    assert "TODO: this site passes" not in menu  # the prefix is the documented entry, not a mismatch
