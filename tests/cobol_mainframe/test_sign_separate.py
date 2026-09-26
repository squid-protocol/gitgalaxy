"""#3694: `SIGN ... SEPARATE` -- a DISPLAY sign that takes a byte of its own.

Found by the blind census of copybook layouts (#3649): CBSA's ABNDINFO codes
`PIC S9(8) DISPLAY SIGN LEADING SEPARATE`, 9 bytes, which the engine sized as 8. The
extractor now records the clause (presence-keyed, like copy_members), record_data keeps
it as `sign_separate`, and GalaxyIR.record_layout adds the byte. A DB written before the
column existed still loads, sizing every sign as embedded.
"""

import shutil
import sqlite3

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

ABNDINFO = """\
       01  ABND-INFO.
           03 ABND-CODE          PIC X(4).
           03 ABND-RESPCODE      PIC S9(8) DISPLAY
                  SIGN LEADING SEPARATE.
           03 ABND-EMBEDDED      PIC S9(8).
           03 ABND-TRAILER       PIC S9(3) SIGN IS TRAILING SEPARATE CHARACTER.
           03 ABND-PACKED        PIC S9(7) COMP-3.
           03 ABND-TEXT          PIC X(10).
"""

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ABND.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY ABNDINFO.
       PROCEDURE DIVISION.
           GOBACK.
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("sign_separate")
    repo = base / "estate"
    for rel, text in {"cpy/ABNDINFO.cpy": ABNDINFO, "cbl/ABND.cbl": PROGRAM}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_the_extractor_records_only_a_separate_sign():
    rows = {r["name"]: r for r in extract_boundary("cobol", ABNDINFO)["records"]}
    assert rows["ABND-RESPCODE"]["sign_separate"] is True  # clause on the continuation line
    assert rows["ABND-TRAILER"]["sign_separate"] is True
    assert "sign_separate" not in rows["ABND-EMBEDDED"]  # presence-keyed: the pre-#3694 shape
    assert "sign_separate" not in rows["ABND-PACKED"]


def test_the_layout_gives_the_separate_sign_its_byte(scanned):
    ir = load_galaxy_ir(scanned)
    ef = ir.files["cpy/ABNDINFO.cpy"]
    (root,) = [r for r in ef.records if r.name == "ABND-INFO"]
    layout = ir.record_layout(ef, root)
    assert [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]] == [
        ("ABND-CODE", 0, 4),
        ("ABND-RESPCODE", 4, 9),  # 8 digits + the sign
        ("ABND-EMBEDDED", 13, 8),  # an embedded sign takes no byte
        ("ABND-TRAILER", 21, 4),
        ("ABND-PACKED", 25, 4),
        ("ABND-TEXT", 29, 10),  # everything after the separate sign moves up one
    ]
    assert layout["bytes"] == 39


def test_a_pre_3694_db_loads_and_sizes_every_sign_as_embedded(scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(scanned, old)
    with sqlite3.connect(old) as conn:
        conn.execute("ALTER TABLE record_data DROP COLUMN sign_separate")
    ir = load_galaxy_ir(old)
    ef = ir.files["cpy/ABNDINFO.cpy"]
    (root,) = [r for r in ef.records if r.name == "ABND-INFO"]
    assert ir.record_layout(ef, root)["bytes"] == 37
