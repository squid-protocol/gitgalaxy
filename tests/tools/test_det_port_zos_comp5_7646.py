"""#7646 slice 5 (#7709, register C7): translate() holds COMP-5 big-endian by default (owner ruling B). The declaration
`comp5_byte_order` is only the comparator's difference now. The default acts on a program that holds a COMP-5 item
(wrapper, refusals); a program without one is untouched. The three IMS batch cases translate whole."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

import det_port  # noqa: E402

IMS_CASES = ["carddemo-paudblod", "carddemo-paudbunl", "carddemo-dbunldgs"]
# the two async credit-card programs that hold a COMP-5 item (READ-INPUT-LENGTH, a SYNC halfword), re-proved under it
ASYNC_CASES = ["asynccc-seqpnt", "asynccc-asyncpnt"]


def test_the_ims_and_async_cases_still_declare_the_comparator_difference():
    import equivalence as eq

    for name in IMS_CASES + ASYNC_CASES:
        assert "comp5_byte_order" in eq.declared_differences(eq.load_case(name)), name


@pytest.mark.parametrize("name", IMS_CASES + ASYNC_CASES)
def test_the_declaring_cases_translate_whole_under_the_declaration(name, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    import equivalence as eq

    case = eq.load_case(name)
    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", TOOLS.parents[1] / ".mainframe_corpora"))
    corpus = root / case["corpus"]
    if not corpus.is_dir():
        pytest.skip(f"corpus {case['corpus']} not available")
    out = det_port.port_case(name, tmp_path, det_port.estate(corpus, tmp_path), corpus)
    assert out.get("translated", True), out
    assert out["holes"] == [], out
    assert "COMP-5" not in str(out.get("error", ""))


# -- the refusal of a program whose COMP-5 bytes cross to a program in the oracle's order: COMMAREA and container areas
CICS_STUB = "public class Zc5Service {\n    public void runTask(CicsTask task) {\n    }\n}\n"
LINK_CHANNEL = ["EXEC CICS LINK PROGRAM('CHILD') CHANNEL('CH') END-EXEC"]
LINK_COMMAREA = ["EXEC CICS LINK PROGRAM('CHILD') COMMAREA(ACCT) END-EXEC"]
# a COMP-5 length beside text, as SEQPNT's READ-INPUT-LENGTH: no container names it
DATA_TEXT = ["01 LEN PIC S9(4) COMP-5 VALUE 9.", "01 ACCT PIC X(9)."]
DATA_GROUP = ["01 REC.", "   05 LEN PIC S9(4) COMP-5 VALUE 9.", "   05 ACCT PIC X(9)."]


def _cics_translate(tmp_path, data, proc, **kw):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. ZC5.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", *data]
    lines += ["PROCEDURE DIVISION.", *[f"    {x}" for x in proc], "    EXEC CICS RETURN END-EXEC."]
    (tmp_path / "ZC5.cbl").write_text("\n".join(f"       {x}" for x in lines) + "\n")
    (tmp_path / "project").mkdir(exist_ok=True)
    return P.translate(tmp_path / "ZC5.cbl", [], CICS_STUB, "p", None, tmp_path / "project", **kw)


def test_a_channel_link_and_a_container_of_text_translate_under_the_switch(tmp_path):
    proc = [*LINK_CHANNEL, "EXEC CICS PUT CONTAINER('C') CHANNEL('CH') FROM(ACCT) END-EXEC",
            "EXEC CICS GET CONTAINER('C') CHANNEL('CH') INTO(ACCT) END-EXEC"]  # fmt: skip
    assert "Cobol.swapZosComp5(true)" in _cics_translate(tmp_path, DATA_TEXT, proc, zos_comp5=True).java


def test_a_commarea_of_text_translates_under_the_switch(tmp_path):
    # #7709: the COMMAREA covers no COMP-5 item (CBSA BNK1TFN's), so no COMP-5 byte crosses
    assert "Cobol.swapZosComp5(true)" in _cics_translate(tmp_path, DATA_TEXT, LINK_COMMAREA, zos_comp5=True).java


@pytest.mark.parametrize("verb", ["LINK", "XCTL"])
def test_a_commarea_covering_a_comp5_item_translates_under_the_switch(verb, tmp_path):
    # #7845: the runtime hands the COMMAREA's bytes over as the program holds them (big-endian under the switch)
    proc = [f"EXEC CICS {verb} PROGRAM('CHILD') COMMAREA(REC) END-EXEC"]
    java = _cics_translate(tmp_path, DATA_GROUP, proc, zos_comp5=True).java
    assert "Cobol.swapZosComp5(true)" in java


def test_burned_cbsa_xfrfun_and_bnk1tfn_translate_under_the_switch(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks

    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", TOOLS.parents[1] / ".mainframe_corpora"))
    cbsa = root / "cics-banking-sample-application-cbsa/src/base"
    if not cbsa.is_dir():
        pytest.skip("CBSA corpus not available")
    bms = tmp_path / "bms"
    bms.mkdir()
    bms_copybooks([p for p in cbsa.rglob("*.bms")], bms)
    for name in ("XFRFUN", "BNK1TFN"):
        r = P.translate(cbsa / "cobol_src" / f"{name}.cbl", [cbsa / "cobol_copy", bms],
                        CICS_STUB, "p", None, tmp_path, zos_comp5=True)  # fmt: skip
        assert "Cobol.swapZosComp5(true)" in r.java, name


AREAS = [  # (data, area): a group holding a COMP-5 item, the item itself, a qualified name, a REDEFINES overlay
    (DATA_GROUP, "REC"),
    (DATA_GROUP, "LEN"),
    (DATA_GROUP, "LEN OF REC"),
    (["01 REC.", "   05 LEN PIC S9(9) COMP-5 VALUE 9.", "   05 BIG PIC S9(18) COMP-5 VALUE 9."], "REC"),
    (
        ["01 REC.", "   05 LEN PIC S9(4) COMP-5 VALUE 9.", "   05 ACCT PIC X(9).", "01 RAW REDEFINES REC PIC X(11)."],
        "RAW",
    ),
]
CONTAINER_VERBS = ["PUT CONTAINER('C') CHANNEL('CH') FROM({a})", "GET CONTAINER('C') CHANNEL('CH') INTO({a})",
                   "PUT CONTAINER('C') FROM({a}) APPEND", "GET CONTAINER('C') INTO({a}) FLENGTH(LEN)"]  # fmt: skip


@pytest.mark.parametrize("verb", CONTAINER_VERBS)
@pytest.mark.parametrize(("data", "area"), AREAS)
def test_a_container_area_holding_a_comp5_item_translates_under_the_switch(verb, data, area, tmp_path):
    # #7845: PUT / GET copy the area's bytes unchanged, so the container carries the z/OS image end to end
    proc = [*LINK_CHANNEL, f"EXEC CICS {verb.format(a=area)} END-EXEC"]
    java = _cics_translate(tmp_path, data, proc, zos_comp5=True).java
    assert "Cobol.swapZosComp5(true)" in java


def test_the_default_serves_a_container_over_a_comp5_item_too(tmp_path):
    proc = [*LINK_CHANNEL, "EXEC CICS PUT CONTAINER('C') CHANNEL('CH') FROM(REC) END-EXEC"]
    default = _cics_translate(tmp_path, DATA_GROUP, proc).java
    assert default == _cics_translate(tmp_path, DATA_GROUP, proc, zos_comp5=True).java


@pytest.mark.parametrize("opt", ["FROMCCSID(37)", "DATATYPE(CHAR)"])
def test_a_put_container_that_converts_a_comp5_area_stays_refused_by_name(opt, tmp_path):
    proc = ["EXEC CICS PUT CONTAINER('C') CHANNEL('CH')", f"FROM(REC) {opt} END-EXEC"]
    with pytest.raises(ValueError, match=r"PUT CONTAINER: .* converts the bytes of an area holding COMP-5"):
        _cics_translate(tmp_path, DATA_GROUP, proc, zos_comp5=True)
    assert "swapZosComp5" not in _cics_translate(tmp_path, DATA_GROUP, proc).java  # the default keeps the oracle order


@pytest.mark.parametrize("opt", ["INTOCCSID(37)", "CONVERTST(DFHVALUE(NOCONVERT))"])
def test_a_get_container_that_converts_a_comp5_area_stays_refused_by_name(opt, tmp_path):
    proc = ["EXEC CICS GET CONTAINER('C') CHANNEL('CH')", f"INTO(REC) {opt} END-EXEC"]
    with pytest.raises(ValueError, match=r"GET CONTAINER: .* converts the bytes of an area holding COMP-5"):
        _cics_translate(tmp_path, DATA_GROUP, proc, zos_comp5=True)


def test_a_converting_container_over_text_translates(tmp_path):
    proc = ["EXEC CICS PUT CONTAINER('C') CHANNEL('CH')", "FROM(ACCT) DATATYPE(CHAR) END-EXEC"]
    assert "Cobol.swapZosComp5(true)" in _cics_translate(tmp_path, DATA_TEXT, proc, zos_comp5=True).java


# -- slice 5: the default (zos_comp5 left unset) --------------------------------------------------------------------
NO_COMP5 = ["01 LEN PIC S9(4) COMP VALUE 9.", "01 ACCT PIC X(9)."]


def test_the_default_is_the_zos_order_on_a_program_holding_comp5(tmp_path):
    default = _cics_translate(tmp_path, DATA_TEXT, LINK_CHANNEL).java
    assert default == _cics_translate(tmp_path, DATA_TEXT, LINK_CHANNEL, zos_comp5=True).java
    assert default != _cics_translate(tmp_path, DATA_TEXT, LINK_CHANNEL, zos_comp5=False).java


LINK_COMMAREA_REC = ["EXEC CICS LINK PROGRAM('CHILD') COMMAREA(REC) END-EXEC"]


@pytest.mark.parametrize("proc", [["CALL 'OTHERPGM' USING ACCT"]])
def test_the_default_keeps_the_oracle_order_for_a_comp5_program_it_cannot_serve(proc, tmp_path):
    # the bytes cross to the runtime (little-endian): the default does not refuse, it translates as before; True refuses
    default = _cics_translate(tmp_path, DATA_TEXT, proc)
    assert "swapZosComp5" not in default.java
    assert default.java == _cics_translate(tmp_path, DATA_TEXT, proc, zos_comp5=False).java
    with pytest.raises(ValueError, match="zos_comp5"):
        _cics_translate(tmp_path, DATA_TEXT, proc, zos_comp5=True)


@pytest.mark.parametrize("proc", [LINK_COMMAREA, ["CALL 'OTHERPGM' USING ACCT"], ["EXEC SQL COMMIT END-EXEC"]])
def test_the_default_leaves_a_program_without_comp5_untouched(proc, tmp_path):
    default = _cics_translate(tmp_path, NO_COMP5, proc)
    assert "swapZosComp5" not in default.java
    assert default.java == _cics_translate(tmp_path, NO_COMP5, proc, zos_comp5=False).java


def test_an_explicit_true_still_acts_on_every_program(tmp_path):
    assert "Cobol.swapZosComp5(true)" in _cics_translate(tmp_path, NO_COMP5, LINK_CHANNEL, zos_comp5=True).java


def test_the_default_holds_a_commarea_over_a_comp5_item_big_endian(tmp_path):
    default = _cics_translate(tmp_path, DATA_GROUP, LINK_COMMAREA_REC)  # #7845: no longer a fallback
    assert default.java == _cics_translate(tmp_path, DATA_GROUP, LINK_COMMAREA_REC, zos_comp5=True).java
    assert default.java != _cics_translate(tmp_path, DATA_GROUP, LINK_COMMAREA_REC, zos_comp5=False).java
