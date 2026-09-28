"""#3930: a port ticket references, rather than inlines, a record layout the generated code already carries.

#3863 found the COACTVWC ticket (CardDemo's account view) too large to port; #3919 trims its BMS field
inventories when a ticket is over budget. This goes further, always: `facts.interface`'s COMMAREA (and
each container layout) is a field list the generated contract class carries field for field, so the
ticket points at the class instead. The estate below has COACTVWC's shape -- a CICS account view with
CardDemo's style of COMMAREA, two CICS file reads and one BMS map.
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import _carrying_class, count_tokens

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTVIEW.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RESP            PIC S9(8) COMP.
       01  WS-ACCT-ID         PIC 9(11).
       COPY ACCTREC.
       COPY CUSTREC.
       COPY ACTVMAP.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           COPY CARDCOMM.
       PROCEDURE DIVISION.
       0000-MAIN.
           MOVE CC-ACCT-ID TO WS-ACCT-ID
           EXEC CICS RECEIVE MAP('ACTVW1A') MAPSET('ACTVMAP')
                INTO(ACTVW1AI) RESP(WS-RESP) END-EXEC
           MOVE ACCTSIDI OF ACTVW1AI TO WS-ACCT-ID
           EXEC CICS READ DATASET('ACCTDAT') INTO(ACCOUNT-RECORD)
                RIDFLD(WS-ACCT-ID) RESP(WS-RESP) END-EXEC
           MOVE ACCT-CUST-ID TO CUST-ID
           EXEC CICS READ DATASET('CUSTDAT') INTO(CUSTOMER-RECORD)
                RIDFLD(CUST-ID) RESP(WS-RESP) END-EXEC
           MOVE ACCT-CURR-BAL TO ACURBALO OF ACTVW1AO
           MOVE CUST-FIRST-NAME TO ACSFNAMO OF ACTVW1AO
           EXEC CICS SEND MAP('ACTVW1A') MAPSET('ACTVMAP')
                FROM(ACTVW1AO) ERASE END-EXEC
           EXEC CICS RETURN TRANSID('CAVW') COMMAREA(DFHCOMMAREA)
                END-EXEC.
"""
# CardDemo's style of COMMAREA: routing, user, customer, account and map context
CARDCOMM = """\
           05  CC-FROM-TRANID      PIC X(4).
           05  CC-FROM-PROGRAM     PIC X(8).
           05  CC-TO-TRANID        PIC X(4).
           05  CC-TO-PROGRAM       PIC X(8).
           05  CC-USER-ID          PIC X(8).
           05  CC-USER-TYPE        PIC X.
               88 CC-ADMIN         VALUE 'A'.
               88 CC-USER          VALUE 'U'.
           05  CC-PGM-CONTEXT      PIC 9.
           05  CC-CUST-ID          PIC 9(9).
           05  CC-CUST-FNAME       PIC X(25).
           05  CC-CUST-MNAME       PIC X(25).
           05  CC-CUST-LNAME       PIC X(25).
           05  CC-ACCT-ID          PIC 9(11).
           05  CC-ACCT-STATUS      PIC X.
           05  CC-CARD-NUM         PIC 9(16).
           05  CC-LAST-MAP         PIC X(7).
           05  CC-LAST-MAPSET      PIC X(7).
"""
ACCTREC = """\
       01  ACCOUNT-RECORD.
           05  ACCT-ID                PIC 9(11).
           05  ACCT-ACTIVE-STATUS     PIC X.
           05  ACCT-CURR-BAL          PIC S9(10)V99.
           05  ACCT-CREDIT-LIMIT      PIC S9(10)V99.
           05  ACCT-CUST-ID           PIC 9(9).
"""
CUSTREC = """\
       01  CUSTOMER-RECORD.
           05  CUST-ID                PIC 9(9).
           05  CUST-FIRST-NAME        PIC X(25).
           05  CUST-LAST-NAME         PIC X(25).
"""
BMS = """\
ACTVMAP  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,TIOAPFX=YES
ACTVW1A  DFHMDI SIZE=(24,80),LINE=1,COLUMN=1
TITLE    DFHMDF POS=(1,20),LENGTH=20,ATTRB=(ASKIP,BRT),INITIAL='ACCOUNT VIEW'
ACCTSID  DFHMDF POS=(3,20),LENGTH=11,ATTRB=(UNPROT,IC)
ACURBAL  DFHMDF POS=(5,20),LENGTH=15,ATTRB=(ASKIP)
ACSFNAM  DFHMDF POS=(7,20),LENGTH=25,ATTRB=(ASKIP)
         DFHMSD TYPE=FINAL
         END
"""
ACTVMAP_CPY = """\
       01  ACTVW1AI.
           02  FILLER          PIC X(12).
           02  ACCTSIDL        COMP PIC S9(4).
           02  ACCTSIDF        PIC X.
           02  ACCTSIDI        PIC X(11).
           02  ACURBALL        COMP PIC S9(4).
           02  ACURBALF        PIC X.
           02  ACURBALI        PIC X(15).
           02  ACSFNAML        COMP PIC S9(4).
           02  ACSFNAMF        PIC X.
           02  ACSFNAMI        PIC X(25).
       01  ACTVW1AO REDEFINES ACTVW1AI.
           02  FILLER          PIC X(12).
           02  FILLER          PIC X(3).
           02  ACCTSIDO        PIC X(11).
           02  FILLER          PIC X(3).
           02  ACURBALO        PIC X(15).
           02  FILLER          PIC X(3).
           02  ACSFNAMO        PIC X(25).
"""
CSD = """\
DEFINE PROGRAM(ACCTVIEW) GROUP(CARDDEMO) LANGUAGE(COBOL)
DEFINE TRANSACTION(CAVW) GROUP(CARDDEMO) PROGRAM(ACCTVIEW)
DEFINE MAPSET(ACTVMAP) GROUP(CARDDEMO)
DEFINE FILE(ACCTDAT) GROUP(CARDDEMO) DSNAME(CARD.ACCTDATA.VSAM.KSDS) KEYLENGTH(11)
DEFINE FILE(CUSTDAT) GROUP(CARDDEMO) DSNAME(CARD.CUSTDATA.VSAM.KSDS) KEYLENGTH(9)
"""
FILES = {
    "cbl/ACCTVIEW.cbl": PROGRAM,
    "cpy/CARDCOMM.cpy": CARDCOMM,
    "cpy/ACCTREC.cpy": ACCTREC,
    "cpy/CUSTREC.cpy": CUSTREC,
    "cpy/ACTVMAP.cpy": ACTVMAP_CPY,
    "bms/ACTVMAP.bms": BMS,
    "csd/CARD.csd": CSD,
}


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    base = tmp_path_factory.mktemp("port_ticket_refs")
    repo = base / "src_estate"
    for rel, text in FILES.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    work = base / "estate"
    shutil.copytree(repo, work)
    db = scan_to_db(repo, base / "scan")
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = base.glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(base / "none.txt")]):
        java_controller.main()
    (java,) = base.glob("estate_gitgalaxy_java_spring_*")
    ticket = json.loads((java / "ai_agent_jobs/ACCTVIEW_port_ticket.json").read_text(encoding="utf-8"))
    skeleton = json.loads(next(clean.glob("06_skeleton/*ACCTVIEW*_skeleton.json")).read_text(encoding="utf-8"))
    return java, ticket, skeleton


def test_the_commarea_is_a_reference_to_the_class_that_carries_it(generated):
    java, ticket, skeleton = generated
    commarea = ticket["facts"]["sections"]["interface"]["facts"]["commarea"]
    full = skeleton["sections"]["interface"]["facts"]["commarea"]
    (ref,) = ticket["referenced"]
    assert ref["section"] == "facts.interface" and ref["item"] == "commarea" and ref["fields"] == 16
    assert (
        commarea["fields"].startswith(f"Reference: AcctviewDfhcommarea (16 fields")
        and ref["class"] in commarea["fields"]
    )
    # the fact's other keys stay as the skeleton has them
    assert {k: v for k, v in commarea.items() if k != "fields"} == {k: v for k, v in full.items() if k != "fields"}
    # the class carries every field the ticket no longer lists: name, PIC, offset, width, copybook
    source = (java / ref["class"]).read_text(encoding="utf-8")
    for f in full["fields"]:
        assert f"// {f['name']}: PIC {f['pic']}, offset {f['offset']}, {f['bytes']} bytes ({f['file']})" in source
    assert ref["bytes_after"] < ref["bytes_before"] / 5


def test_what_no_generated_class_carries_stays_inline(generated):
    """The CICS file lineage's CSD facts -- key length, group, the line of each READ -- are in no generated class."""
    _, ticket, skeleton = generated
    sections = ticket["facts"]["sections"]
    assert sections["cics_file_lineage"]["facts"] == skeleton["sections"]["cics_file_lineage"]["facts"]
    assert {d["key_length"] for f in sections["cics_file_lineage"]["facts"] for d in f["definitions"]} == {9, 11}
    assert "records" not in sections  # a bulk section: record layouts never reach a ticket (the *Record classes)


def test_the_interface_section_shrinks(generated):
    """#3930's measurement: the interface section's bytes and tokens, with the layout inlined and referenced."""
    _, ticket, skeleton = generated
    inline = json.dumps(skeleton["sections"]["interface"]["facts"], indent=2, sort_keys=True)
    referenced = json.dumps(ticket["facts"]["sections"]["interface"]["facts"], indent=2, sort_keys=True)
    b_in, t_in, _ = count_tokens(inline)
    b_ref, t_ref, _ = count_tokens(referenced)
    assert b_ref < b_in / 2 and t_ref < t_in / 2


# ---- the check that decides it -------------------------------------------------------------------
_FIELDS = [
    {"name": "CC-ACCT-ID", "pic": "9(11)", "usage": None, "offset": 0, "bytes": 11, "file": "cpy/C.cpy"},
    {"name": "FILLER", "pic": "X(3)", "usage": None, "offset": 11, "bytes": 3, "file": "cpy/C.cpy"},
    {"name": "CC-BAL", "pic": "S9(7)V99", "usage": "COMP-3", "offset": 14, "bytes": 5, "file": "cpy/C.cpy"},
]
_CLASS = (
    "/**\n * COBOL record DFHCOMMAREA (cbl/P.cbl), 19 bytes, from GitGalaxy's verified skeleton.\n */\n"
    "public class PDfhcommarea {\n\n"
    "    // CC-ACCT-ID: PIC 9(11), offset 0, 11 bytes (cpy/C.cpy)\n    private Long ccAcctId;\n\n"
    "    // CC-BAL: PIC S9(7)V99 COMP-3, offset 14, 5 bytes (cpy/C.cpy)\n    private BigDecimal ccBal;\n}\n"
)


def test_a_class_carrying_every_named_field_is_found():
    assert (
        _carrying_class("DFHCOMMAREA", "cbl/P.cbl", _FIELDS, {"dto/PDfhcommarea.java": _CLASS})
        == "dto/PDfhcommarea.java"
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.replace("offset 14", "offset 15"),  # a field moved
        lambda c: c.replace(" COMP-3", ""),  # the usage is not the layout's
        lambda c: c.replace(
            "    // CC-BAL: PIC S9(7)V99 COMP-3, offset 14, 5 bytes (cpy/C.cpy)\n", ""
        ),  # a field is missing
        lambda c: c.replace("(cbl/P.cbl)", "(cbl/Q.cbl)"),  # another program's record
    ],
)
def test_a_class_that_is_not_the_whole_layout_is_not_referenced(change):
    assert _carrying_class("DFHCOMMAREA", "cbl/P.cbl", _FIELDS, {"dto/PDfhcommarea.java": change(_CLASS)}) is None


def test_an_unknown_offset_is_never_referenced():
    fields = [dict(_FIELDS[0], offset=None)]
    assert _carrying_class("DFHCOMMAREA", "cbl/P.cbl", fields, {"dto/PDfhcommarea.java": _CLASS}) is None
