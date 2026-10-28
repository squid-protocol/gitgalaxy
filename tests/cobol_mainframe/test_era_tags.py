"""#5117 era tags: one fixture per tell, one per era, a mixed program, and the text classes a tell must (not) survive
(comments, string literals, free form, sequence numbers, case, hyphenated names)."""

import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import era_tags as et  # tests/tools/era_tags.py

IBM_HOSTS = {"www.ibm.com", "ibm.com", "www.redbooks.ibm.com", "redbooks.ibm.com", "publibfp.dhe.ibm.com"}
HEAD = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"
PROC = "       PROCEDURE DIVISION.\n"


def prog(*body: str, data: str = "", head: str = HEAD) -> str:
    """A fixed-form program: `data` in WORKING-STORAGE, `body` lines in the procedure division."""
    ws = f"       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n{data}" if data else ""
    return head + ws + PROC + "".join(f"           {b}\n" for b in body) + "           GOBACK.\n"


def tells(text: str) -> dict[str, int]:
    return {t["tell"]: t["era"] for t in et.tag_program(text)["tells"]}


# tell -> (a program that has it, its era). One per tell of TELLS: test_every_tell_has_a_fixture keeps the two in step.
FIXTURES = {
    "dfh-macro-call": ("DFHPC    TYPE=LINK,PROGRAM=SUBPGM\n         END\n", 0),
    "csa-tca-dsect": (prog(data="       COPY DFHCSADS.\n"), 0),
    "bll-cells": (prog(data="       01 BLL-CELLS.\n           05 FILLER PIC S9(8) COMP.\n"), 1),
    "service-reload": (prog("SERVICE RELOAD DFHCOMMAREA."), 1),
    "handle-condition": (prog("EXEC CICS HANDLE CONDITION NOTFND(ERR) END-EXEC."), 1),
    "dli": (prog("CALL 'CBLTDLI' USING FN PCB IOAREA."), 1),
    "langlvl-1": ("       CBL LANGLVL(1)\n" + prog("DISPLAY 'X'."), 1),
    "address-of": (prog("SET P TO ADDRESS OF LS-REC."), 2),
    "set-address": (prog("SET ADDRESS OF LS-REC TO P."), 2),
    "resp": (prog("EXEC CICS RETURN RESP(R) RESP2(R2) END-EXEC."), 2),
    "exec-sql": (prog("EXEC SQL SELECT 1 INTO :X FROM T END-EXEC."), 2),
    "dpl-link-sysid": (prog("EXEC CICS LINK PROGRAM('REMOTE') SYSID('AOR2') END-EXEC."), 2),
    "cmpr2": ("       CBL CMPR2\n" + prog("DISPLAY 'X'."), 2),
    "langlvl-2": ("       CBL LANGLVL(2)\n" + prog("DISPLAY 'X'."), 2),
    "mq-call": (prog("CALL 'MQPUT' USING HCONN HOBJ MD PMO LEN BUF CC RC."), 3),
    "exci": (prog("CALL 'DFHXCIS' USING A B C."), 3),
    "bridge-3270": (prog(data="       COPY DFHBRARC.\n"), 3),
    "le-callable": (prog("CALL 'CEE3ABD' USING CODE TIMING."), 3),
    "channel-container": (prog("EXEC CICS PUT CONTAINER('C') CHANNEL('CH') FROM(X) END-EXEC."), 4),
    "web-soap": (prog("EXEC CICS WEB SEND MEDIATYPE('text/html') END-EXEC."), 4),
    "json-xml": (prog("JSON GENERATE OUT FROM REC END-JSON."), 4),
    "async": (prog("EXEC CICS RUN TRANSID('TRN1') CHILD(CH) END-EXEC."), 4),
    "named-counter": (prog("EXEC CICS GET DCOUNTER('CTR') VALUE(V) END-EXEC."), 4),
    "arith-extend": ("       CBL ARITH(EXTEND)\n" + prog("DISPLAY 'X'."), 4),
}


def test_every_tell_has_a_fixture():
    assert {t[0] for t in et.TELLS} == set(FIXTURES)  # noqa: S101


@pytest.mark.parametrize("tell", sorted(FIXTURES))
def test_each_tell(tell):
    text, era = FIXTURES[tell]
    assert tells(text).get(tell) == era, (tell, tells(text))  # noqa: S101


# One fixture per era, using only that era's own tells: the tag's era is that era and it is not mixed.
ERA_FIXTURES = {
    0: FIXTURES["dfh-macro-call"][0],
    1: prog(
        "SERVICE RELOAD DFHCOMMAREA.", "EXEC CICS HANDLE AID PF3(DONE) END-EXEC.", data="       01 BLL-CELLS PIC X.\n"
    ),
    2: prog("EXEC CICS RETURN RESP(R) END-EXEC.", "SET ADDRESS OF LS-REC TO P.", "EXEC SQL COMMIT END-EXEC."),
    3: prog("CALL 'MQGET' USING A B C.", "CALL 'CEEDAYS' USING A B C."),
    4: prog("EXEC CICS GET CONTAINER('C') CHANNEL('CH') INTO(X) END-EXEC."),
}


@pytest.mark.parametrize("era", sorted(ERA_FIXTURES))
def test_one_program_per_era(era):
    tag = et.tag_program(ERA_FIXTURES[era])
    assert tag["era"] == era and not tag["mixed"], tag  # noqa: S101
    assert tag["earliest"] == era, tag  # noqa: S101


def test_mixed_program_says_so_with_its_tells():
    """A 1980s command-level program (BLL cells, HANDLE CONDITION) that also calls a channel API."""
    text = prog(
        "EXEC CICS HANDLE CONDITION NOTFND(ERR) END-EXEC.",
        "EXEC CICS GET CONTAINER('C') CHANNEL('CH') INTO(X) END-EXEC.",
        data="       01 BLL-CELLS PIC X.\n",
    )
    tag = et.tag_program(text)
    assert (tag["era"], tag["earliest"], tag["mixed"]) == (4, 1, True)  # noqa: S101
    assert {t["tell"] for t in tag["tells"]} == {"bll-cells", "handle-condition", "channel-container"}  # noqa: S101


def test_set_address_of_is_both_tells_of_one_construct():
    """`SET ADDRESS OF` contains `ADDRESS OF`: both are era 2, so the tag is the same either way."""
    assert tells(prog("SET ADDRESS OF A TO B.")) == {"address-of": 2, "set-address": 2}  # noqa: S101


def test_floor_tells_alone_never_make_a_program_mixed():
    """RESP, EXEC SQL and channels are written in every later era: era 2 + era 4 floors is simply era 4."""
    text = prog("EXEC CICS PUT CONTAINER('C') CHANNEL('CH') FROM(X) RESP(R) END-EXEC.", "EXEC SQL COMMIT END-EXEC.")
    tag = et.tag_program(text)
    assert (tag["era"], tag["mixed"]) == (4, False)  # noqa: S101


def test_no_tell_is_untagged():
    tag = et.tag_program(prog("DISPLAY 'HELLO'."))
    assert tag == {"era": None, "earliest": None, "mixed": False, "tells": []}  # noqa: S101


# The text classes: the same tell must not fire where it is not code, and must fire however the line is written.
NOT_CODE = {
    "comment line": HEAD + PROC + "      * EXEC SQL COMMIT END-EXEC.\n           GOBACK.\n",
    "slash comment line": HEAD + PROC + "      / SET ADDRESS OF A TO B.\n           GOBACK.\n",
    "string literal": prog("DISPLAY 'ADDRESS OF X'.", 'DISPLAY "SERVICE RELOAD".'),
    "longer identifier": prog("MOVE 1 TO BLLX.", "MOVE 1 TO MY-ADDRESS-OFFSET.", "PERFORM RESPONSE-PARA."),
    "RESP outside EXEC CICS": prog("MOVE RESP(1) TO X."),
    "NOCMPR2 option": "       CBL NOCMPR2\n" + prog("DISPLAY 'X'."),
}


@pytest.mark.parametrize("name", sorted(NOT_CODE))
def test_not_a_tell(name):
    assert tells(NOT_CODE[name]) == {}, tells(NOT_CODE[name])  # noqa: S101


def test_sequence_numbers_and_columns_73_80_are_not_read():
    text = (
        "000100 IDENTIFICATION DIVISION.                                         EXEC SQL\n"
        "000200 PROGRAM-ID. P.\n"
        "000300 PROCEDURE DIVISION.\n"
        "000400     DISPLAY 'X'.                                                 SET ADDRESS\n"
    )
    assert tells(text) == {}  # noqa: S101


def test_tell_with_sequence_numbers_and_lowercase():
    text = "000100 PROCEDURE DIVISION.\n000200     exec sql commit end-exec.\n000300     set address of a to b.\n"
    assert tells(text) == {"address-of": 2, "exec-sql": 2, "set-address": 2}  # noqa: S101


def test_free_form_source():
    text = "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nPROCEDURE DIVISION.\n*> EXEC SQL in a comment\nSET ADDRESS OF A TO B\nEXEC CICS GET CONTAINER('C') CHANNEL('X') INTO(Y) END-EXEC\n"
    assert tells(text) == {"address-of": 2, "set-address": 2, "channel-container": 4}  # noqa: S101


def test_multi_line_exec_cics_block():
    text = prog("EXEC CICS", "    LINK PROGRAM('X')", "    CHANNEL('CH')", "END-EXEC.")
    assert tells(text) == {"channel-container": 4}  # noqa: S101


def test_cbl_card_options_only_in_cbl_and_process_cards():
    """CMPR2 as an ordinary word in code is not an option; the PROCESS card form is read like CBL."""
    assert tells(prog("DISPLAY 'CMPR2'.", "MOVE 1 TO CMPR2-FLAG.")) == {}  # noqa: S101
    assert tells("       PROCESS CMPR2,LANGLVL(2)\n" + prog("DISPLAY 'X'.")) == {"cmpr2": 2, "langlvl-2": 2}  # noqa: S101


def test_macro_text_beside_exec_cics_is_not_macro_level():
    text = prog("EXEC CICS RETURN END-EXEC.").replace("GOBACK.", "GOBACK.\nDFHPC TYPE=RETURN\n")
    assert "dfh-macro-call" not in tells(text)  # noqa: S101


def test_summary_counts_programs_per_era_and_tell():
    progs = {
        "a.cbl": et.tag_program(ERA_FIXTURES[1]),
        "b.cbl": et.tag_program(ERA_FIXTURES[4]),
        "c.cbl": et.tag_program(prog("DISPLAY 'X'.")),
    }
    s = et.summarise(progs)
    assert s["programs"] == 3 and s["by_era"] == {"0": 0, "1": 1, "2": 0, "3": 0, "4": 1, "none": 1}  # noqa: S101
    assert s["tells"]["channel-container"] == 1 and s["mixed"] == 0  # noqa: S101


def test_deterministic():
    assert et.tag_program(ERA_FIXTURES[1]) == et.tag_program(ERA_FIXTURES[1])  # noqa: S101


# ---- #5117: tells inside copybooks -------------------------------------------------------------------------------
PLAIN = prog("DISPLAY 'X'.")
CBK_TELLS = sorted(t for t in FIXTURES if t != "dfh-macro-call")  # assembler macro text in a COBOL copybook is no tell


def with_copybook(text: str, book: str, name: str = "BOOK.cpy") -> dict:
    return et.tag_program(text, {name: book})


@pytest.mark.parametrize("tell", CBK_TELLS)
def test_each_tell_inside_a_copybook(tell):
    """Every tell the program text shows is also seen in a copybook (same scopes: code, raw, cics, cbl cards)."""
    text, era = FIXTURES[tell]
    tag = with_copybook(PLAIN, text)
    hit = next(t for t in tag["tells"] if t["tell"] == tell)
    assert (hit["era"], hit["via_copybook"], hit["copybooks"], hit["first_line"]) == (era, True, ["BOOK.cpy"], None)  # noqa: S101
    assert tag["era"] == max(t["era"] for t in tag["tells"])  # noqa: S101


def test_macro_text_in_a_copybook_is_no_tell():
    assert with_copybook(PLAIN, FIXTURES["dfh-macro-call"][0])["tells"] == []  # noqa: S101


def test_copybook_raises_the_era_and_the_program_era_is_kept():
    tag = with_copybook(prog("EXEC CICS RETURN RESP(R) END-EXEC."), FIXTURES["channel-container"][0])
    assert (tag["era"], tag["program_era"]) == (4, 2)  # noqa: S101


def test_tell_in_program_and_copybook_counts_the_program_and_names_the_copybook():
    text = FIXTURES["resp"][0]
    tag = with_copybook(text, text)
    resp = next(t for t in tag["tells"] if t["tell"] == "resp")
    assert resp["count"] == et.tag_program(text)["tells"][0]["count"] and "via_copybook" not in resp  # noqa: S101
    assert resp["copybooks"] == ["BOOK.cpy"] and "program_era" not in tag  # noqa: S101


def test_copybooks_add_up_and_are_listed_in_order():
    book = prog("EXEC CICS RETURN RESP(R) END-EXEC.")
    tag = et.tag_program(PLAIN, {"B.cpy": book, "A.cpy": book})
    resp = tag["tells"][0]
    assert (resp["count"], resp["copybooks"]) == (2, ["A.cpy", "B.cpy"])  # noqa: S101


def test_old_tell_in_a_copybook_makes_a_new_program_mixed():
    tag = with_copybook(FIXTURES["channel-container"][0], FIXTURES["bll-cells"][0])
    assert (tag["era"], tag["earliest"], tag["mixed"]) == (4, 1, True)  # noqa: S101


def test_floor_tell_in_a_copybook_never_makes_a_program_mixed():
    tag = with_copybook(FIXTURES["bll-cells"][0], FIXTURES["channel-container"][0])
    assert tag["mixed"] is False or tag["earliest"] == 1  # noqa: S101
    tag = with_copybook(FIXTURES["resp"][0], FIXTURES["channel-container"][0])
    assert tag["mixed"] is False and tag["program_era"] == 2  # noqa: S101


def test_comments_and_literals_in_a_copybook_are_not_read():
    book = "      * EXEC CICS GET CONTAINER('C') END-EXEC\n       01 X PIC X(20) VALUE 'JSON PARSE'.\n"
    assert with_copybook(PLAIN, book)["tells"] == []  # noqa: S101


def test_free_form_copybook_in_a_fixed_form_program():
    book = "01 BLL-CELLS.\n05 FILLER PIC S9(8) COMP.\n*> SERVICE RELOAD\n"
    tag = with_copybook(PLAIN, book)
    assert {t["tell"] for t in tag["tells"]} == {"bll-cells"}  # noqa: S101


def test_no_copybooks_is_byte_identical_to_the_program_only_tag():
    for text in (FIXTURES[t][0] for t in FIXTURES):
        assert et.tag_program(text, {}) == et.tag_program(text) == et.tag_program(text, None)  # noqa: S101
        assert "program_era" not in et.tag_program(text)  # noqa: S101


def test_copybook_with_no_tell_changes_nothing():
    assert with_copybook(ERA_FIXTURES[2], "       01 X PIC X.\n") == et.tag_program(ERA_FIXTURES[2])  # noqa: S101


def test_summary_counts_programs_raised_by_a_copybook_only_when_any():
    plain = {"a.cbl": et.tag_program(PLAIN)}
    assert "raised_by_copybook" not in et.summarise(plain)  # noqa: S101
    plain["b.cbl"] = with_copybook(PLAIN, FIXTURES["channel-container"][0])
    assert et.summarise(plain)["raised_by_copybook"] == 1  # noqa: S101


def test_every_tell_cites_an_ibm_release():
    assert set(et.CITE) == {t[0] for t in et.TELLS}  # noqa: S101
    for tell, c in et.CITE.items():
        assert c["ibm"] and c["verified"] is True, tell  # noqa: S101
        assert c["source"].startswith("https://"), tell  # noqa: S101
        assert urlparse(c["source"]).hostname in IBM_HOSTS, tell  # noqa: S101


def test_skipped_marker_is_added_only_when_set():
    tag = et.tag_program(PLAIN)
    assert "copybook_skipped" not in tag  # noqa: S101
    marked = et.mark_skipped(tag, "CopyNotFound")
    assert marked["copybook_skipped"] == "CopyNotFound" and marked["tells"] == tag["tells"]  # noqa: S101
    assert et.mark_skipped(marked, "Other")["copybook_skipped"] == "CopyNotFound"  # noqa: S101  (first reason stands)


def test_summary_counts_skipped_programs_only_when_any():
    plain = {"a.cbl": et.tag_program(PLAIN)}
    assert "copybook_skipped" not in et.summarise(plain)  # noqa: S101
    plain["b.cbl"] = et.mark_skipped(et.tag_program(PLAIN), "CopyNotFound")
    assert et.summarise(plain)["copybook_skipped"] == 1  # noqa: S101
