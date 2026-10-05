"""#4265 (estate-crucible H-0016): COPY ... REPLACING in record_layout.

`01 WS-EMP. COPY PAYTPL REPLACING ==:TAG:== BY ==EMP==.` over a template copybook whose entries
are `05 :TAG:-ID PIC X(6).` ... : the program's record holds EMP-ID / EMP-NAME / EMP-RATE (40 bytes).
The extractor keeps each COPY's REPLACING operands (record_data.copy_replacing) and the template's
tagged names as written; GalaxyIR applies the REPLACING when it lays the record out. The template's
own tagged entries are not data-names (the key's reading): they are kept apart, never data_items.
"""

import json
import sqlite3

import pytest

from gitgalaxy.core.mainframe_boundary import _copy_replacing, extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import _replace_text, load_galaxy_ir, scan_to_db

PAYMAIN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYMAIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-EMP.
           COPY PAYTPL REPLACING ==:TAG:== BY ==EMP==.
       01  WS-MGR.
           COPY PAYTPL REPLACING ==:TAG:== BY ==MGR==.
       01  WS-PLAIN.
           COPY PLAIN REPLACING ==AMT-X== BY ==AMT-Y==
                                LEADING ==PFX== BY ==NEW==.
       01  WS-RAW.
           COPY PLAIN.
       PROCEDURE DIVISION.
           GOBACK.
"""
PAYTPL = (
    "           05  :TAG:-ID               PIC X(6).\n"
    "           05  :TAG:-NAME             PIC X(30).\n"
    "           05  :TAG:-RATE             PIC S9(5)V99 COMP-3.\n"
)
PLAIN = "           05  AMT-X   PIC 9(4).\n           05  AMT-XX  PIC 9(2).\n           05  PFX-CODE PIC X(3).\n"


def test_the_extractor_keeps_each_copys_replacing_operands():
    rows = {r["name"]: r for r in extract_boundary("cobol", PAYMAIN)["records"]}
    assert "copy_replacing" not in rows["WS-RAW"]  # presence-keyed: a plain COPY keeps its old shape
    assert json.loads(rows["WS-EMP"]["copy_replacing"]) == [[[":TAG:", "EMP"]]]
    assert json.loads(rows["WS-PLAIN"]["copy_replacing"]) == [[["AMT-X", "AMT-Y"], ["PFX", "NEW", "LEADING"]]]


def test_the_template_keeps_its_tagged_names():
    assert [r["name"] for r in extract_boundary("cobol", PAYTPL)["records"]] == [":TAG:-ID", ":TAG:-NAME", ":TAG:-RATE"]


def test_operand_forms():
    window = "    COPY X REPLACING ==A B== BY ==C==  'x' BY 'y'  TRAILING ==-IN== BY ==-OUT==."
    assert _copy_replacing(window, window.index("X") + 1) == [["A B", "C"], ["'x'", "'y'"], ["-IN", "-OUT", "TRAILING"]]
    assert _copy_replacing("    COPY X.", 10) is None
    # a whole-word operand never replaces part of a longer word; a tag does
    assert _replace_text("AMT-XX", [["AMT-X", "AMT-Y"]]) == "AMT-XX"
    assert _replace_text("AMT-X", [["AMT-X", "AMT-Y"]]) == "AMT-Y"
    assert _replace_text(":TAG:-ID", [[":TAG:", "EMP"]]) == "EMP-ID"
    # one left-to-right pass: replaced text is not matched again, and the first matching pair wins
    assert _replace_text("A-1 B-1", [["A-1", "B-1"], ["B-1", "C-1"]]) == "B-1 C-1"


@pytest.fixture(scope="module")
def ir(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy_replacing")
    repo = base / "estate"
    for rel, text in {"cbl/PAYMAIN.cbl": PAYMAIN, "cpy/PAYTPL.cpy": PAYTPL, "cpy/PLAIN.cpy": PLAIN}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    db = scan_to_db(repo, base / "scan")
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM record_data WHERE copy_replacing IS NOT NULL").fetchone() == (3,)
    return load_galaxy_ir(db)


def _layout(ir, record):
    ef = ir.files["cbl/PAYMAIN.cbl"]
    return ir.record_layout(ef, next(r for r in ef.records if r.name == record))


def test_the_layout_applies_the_replacing(ir):
    emp = _layout(ir, "WS-EMP")
    assert emp["bytes"] == 40
    assert [(f["name"], f["bytes"]) for f in emp["fields"] if f.get("pic")] == [
        ("EMP-ID", 6), ("EMP-NAME", 30), ("EMP-RATE", 4)
    ]  # fmt: skip
    # the same template, another tag: its own names, the template untouched
    assert [f["name"] for f in _layout(ir, "WS-MGR")["fields"] if f.get("pic")] == ["MGR-ID", "MGR-NAME", "MGR-RATE"]
    plain = _layout(ir, "WS-PLAIN")
    assert [f["name"] for f in plain["fields"] if f.get("pic")] == ["AMT-Y", "AMT-XX", "NEW-CODE"]


def test_the_template_entries_are_not_data_names(ir):
    tpl = ir.files["cpy/PAYTPL.cpy"]
    assert tpl.data_items == [] and tpl.records == []
    assert [r.name for r in tpl.template_records] == [":TAG:-ID", ":TAG:-NAME", ":TAG:-RATE"]


def test_a_copy_without_replacing_is_unchanged(ir):
    # the nearest negative: the same copybook copied plainly keeps its own names, and stays data_items
    assert [f["name"] for f in _layout(ir, "WS-RAW")["fields"] if f.get("pic")] == ["AMT-X", "AMT-XX", "PFX-CODE"]
    assert [it.name for it in ir.files["cpy/PLAIN.cpy"].data_items] == ["AMT-X", "AMT-XX", "PFX-CODE"]
