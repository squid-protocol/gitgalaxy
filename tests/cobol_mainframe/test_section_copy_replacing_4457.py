"""#4457: a section-level `COPY member REPLACING ...` (one that copies whole 01 records) is applied.

#4265 applied REPLACING inside a group (`01 WS-EMP. COPY TPL REPLACING ...`). A COPY at section level --
after a section header or an FD, or after an entry whose record it does not belong to -- brings records of
its own into the program: CBSA `COPY INQACC REPLACING INQACC-COMMAREA BY DFHCOMMAREA.` (the word form),
zopeneditor SAM1 `COPY CUSTCOPY REPLACING ==:TAG:== BY ==CUST==.` over a pseudo-text template. The
program's records are the copybook's with the REPLACING applied; the copybook's own names are not the
program's. Facts a COPY brings in stay out of `data_items`, the text the program itself holds.
"""

import json
import sqlite3

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

PROG = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SECREP.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-IN ASSIGN TO CUSTIN.
           SELECT CUST-OUT ASSIGN TO CUSTOUT.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-IN
           RECORDING MODE IS F.
       COPY CUSTCOPY REPLACING ==:TAG:== BY ==CUST==.
       FD  CUST-OUT
           RECORDING MODE IS F.
       COPY CUSTCOPY REPLACING ==:TAG:== BY ==CSTOUT==.
       WORKING-STORAGE SECTION.
       COPY SORTCODE REPLACING ==SORTCODE== BY ==LITERAL-SORTCODE==.
       01  WS-AFTER            PIC X(4).
       COPY PLAINREC.
       01  WS-MOVED            PIC X(2).
       COPY AREA01 REPLACING AREA-ID BY ZONE-ID.
       LINKAGE SECTION.
       COPY INQACC REPLACING INQACC-COMMAREA BY DFHCOMMAREA.
       PROCEDURE DIVISION USING DFHCOMMAREA.
           MOVE ZONE-ID TO LITERAL-SORTCODE
           GOBACK.
"""
CUSTCOPY = (
    "       01  :TAG:-REC.\n"
    "           05  :TAG:-ID            PIC X(5).\n"
    "           05  :TAG:-NAME          PIC X(15).\n"
    "       01  :TAG:-CONTACT-REC.\n"
    "           05  :TAG:-PHONE         PIC X(8).\n"
)
SORTCODE = "       01  SORTCODE            PIC 9(6).\n"
PLAINREC = "       01  PLAIN-RECORD.\n           05  PLAIN-KEY       PIC X(3).\n"
AREA01 = "       01  AREA-RECORD.\n           05  AREA-ID         PIC X(7).\n"
INQACC = "       01  INQACC-COMMAREA.\n           03  INQACC-CUSTNO    PIC 9(10).\n           03  INQACC-SCODE     PIC X(6).\n"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("section_copy")
    repo = base / "estate"
    files = {
        "cbl/SECREP.cbl": PROG,
        "cpy/CUSTCOPY.cpy": CUSTCOPY,
        "cpy/SORTCODE.cpy": SORTCODE,
        "cpy/PLAINREC.cpy": PLAINREC,
        "cpy/AREA01.cpy": AREA01,
        "cpy/INQACC.cpy": INQACC,
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    db = scan_to_db(repo, base / "scan")
    return db, load_galaxy_ir(db)


@pytest.fixture(scope="module")
def ir(built):
    return built[1]


def _records(ir):
    ef = ir.files["cbl/SECREP.cbl"]
    return ef, {r.name: r for r in ef.records}


def _fields(ir, name):
    ef, recs = _records(ir)
    lay = ir.record_layout(ef, recs[name])
    return lay["bytes"], [(f["name"], f["offset"], f["bytes"]) for f in lay["fields"] if f.get("pic")]


def test_the_extractor_records_a_copy_no_entry_carries():
    got = extract_boundary("cobol", PROG)["section_copies"]
    assert [(c["member"], c["section"], c["fd_name"], c["after_ordinal"]) for c in got] == [
        ("CUSTCOPY", "FILE", "CUST-IN", None),
        ("CUSTCOPY", "FILE", "CUST-OUT", None),
        ("SORTCODE", "WORKING-STORAGE", None, None),
        ("INQACC", "LINKAGE", None, 1),
    ]
    assert json.loads(got[0]["replacing"]) == [[":TAG:", "CUST"]]
    assert json.loads(got[2]["replacing"]) == [["SORTCODE", "LITERAL-SORTCODE"]]
    # a COPY an entry carries is that entry's (record_data.copy_replacing), not a section copy
    assert "AREA01" not in {c["member"] for c in got}
    assert any(r.get("copy_replacing") for r in extract_boundary("cobol", PROG)["records"] if r["name"] == "WS-MOVED")


def test_the_word_form_names_the_replaced_record(ir):
    # CBSA INQACC: the record is DFHCOMMAREA, the program's USING operand -- not INQACC-COMMAREA
    ef, recs = _records(ir)
    assert "DFHCOMMAREA" in recs and "INQACC-COMMAREA" not in recs
    assert recs["DFHCOMMAREA"].section == "LINKAGE"
    assert ir._dfhcommarea(ef) is recs["DFHCOMMAREA"]
    assert _fields(ir, "DFHCOMMAREA") == (16, [("INQACC-CUSTNO", 0, 10), ("INQACC-SCODE", 10, 6)])
    # CBSA GETSCODE: ==SORTCODE== BY ==LITERAL-SORTCODE==
    assert _fields(ir, "LITERAL-SORTCODE") == (6, [("LITERAL-SORTCODE", 0, 6)])
    assert "SORTCODE" not in recs


def test_a_pseudo_text_template_yields_its_records(ir):
    # zopeneditor SAM1: the template copybook has no data-names until replaced; two COPYs, two tags, in their FDs
    ef, recs = _records(ir)
    for tag, fd in (("CUST", "CUST-IN"), ("CSTOUT", "CUST-OUT")):
        assert recs[f"{tag}-REC"].fd_name == fd and recs[f"{tag}-CONTACT-REC"].section == "FILE"
        assert _fields(ir, f"{tag}-REC") == (20, [(f"{tag}-ID", 0, 5), (f"{tag}-NAME", 5, 15)])
        assert _fields(ir, f"{tag}-CONTACT-REC") == (8, [(f"{tag}-PHONE", 0, 8)])
    assert [it.name for it in ir.files["cpy/CUSTCOPY.cpy"].template_records][:1] == [":TAG:-REC"]  # untouched


def test_a_copy_after_an_entry_that_opens_its_own_01(ir):
    # `01 WS-MOVED` + `COPY AREA01 REPLACING ...`: AREA01 starts a record of its own, so it is a section COPY
    _, recs = _records(ir)
    assert _fields(ir, "AREA-RECORD") == (7, [("ZONE-ID", 0, 7)])


def test_the_records_stay_in_source_order(ir):
    ef, _ = _records(ir)
    assert [r.name for r in ef.records] == [
        "CUST-REC", "CUST-CONTACT-REC", "CSTOUT-REC", "CSTOUT-CONTACT-REC",
        "LITERAL-SORTCODE", "WS-AFTER", "WS-MOVED", "AREA-RECORD", "DFHCOMMAREA",
    ]  # fmt: skip


def test_data_items_stay_the_programs_own_text(ir):
    ef, _ = _records(ir)
    assert [it.name for it in ef.data_items] == ["WS-AFTER", "WS-MOVED"]


def test_names_resolve_to_the_replaced_record_not_the_copybooks(ir):
    ef, _ = _records(ir)
    assert [(i.name, e) for _, i, e in ir._find_item(ef, "LITERAL-SORTCODE", None)] == [("LITERAL-SORTCODE", None)]
    assert ir._find_item(ef, "SORTCODE", None) == []
    assert [i.name for _, i, _e in ir._find_item(ef, "CSTOUT-PHONE", None)] == ["CSTOUT-PHONE"]


def test_a_plain_section_copy_is_unchanged(ir):
    # the nearest negative: `COPY PLAINREC.` (no REPLACING) keeps the copybook's own record
    ef, recs = _records(ir)
    assert "PLAIN-RECORD" not in recs
    assert [i.name for _, i, _e in ir._find_item(ef, "PLAIN-RECORD", None)] == ["PLAIN-RECORD"]


def test_the_statements_persist(built):
    db, _ = built
    rows = (
        sqlite3.connect(db).execute("SELECT member, library, section FROM copy_statement_data ORDER BY id").fetchall()
    )
    assert [r[0] for r in rows] == ["CUSTCOPY", "CUSTCOPY", "SORTCODE", "INQACC"]
