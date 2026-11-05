"""#7646 (register C7): a case declaring comp5_byte_order is ported with COMP-5 held big-endian (translate(zos_comp5=True)),
and an undeclared one is not. The three IMS batch cases (CALL 'CBLTDLI') carry the declaration and translate whole."""

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


def test_the_declaration_selects_the_zos_byte_order():
    assert det_port._zos_comp5({"declared_differences": ["comp5_byte_order"]})
    assert not det_port._zos_comp5({})
    assert not det_port._zos_comp5({"declared_differences": []})


def test_the_ims_and_async_cases_declare_it():
    import equivalence as eq

    for name in IMS_CASES + ASYNC_CASES:
        assert det_port._zos_comp5(eq.load_case(name)), name


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


def _cics_translate(tmp_path, data, proc):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. ZC5.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", *data]
    lines += ["PROCEDURE DIVISION.", *[f"    {x}" for x in proc], "    EXEC CICS RETURN END-EXEC."]
    (tmp_path / "ZC5.cbl").write_text("\n".join(f"       {x}" for x in lines) + "\n")
    (tmp_path / "project").mkdir(exist_ok=True)
    return P.translate(tmp_path / "ZC5.cbl", [], CICS_STUB, "p", None, tmp_path / "project", zos_comp5=True)


def test_a_channel_link_and_a_container_of_text_translate_under_the_switch(tmp_path):
    proc = [*LINK_CHANNEL, "EXEC CICS PUT CONTAINER('C') CHANNEL('CH') FROM(ACCT) END-EXEC",
            "EXEC CICS GET CONTAINER('C') CHANNEL('CH') INTO(ACCT) END-EXEC"]  # fmt: skip
    assert "Cobol.swapZosComp5(true)" in _cics_translate(tmp_path, DATA_TEXT, proc).java


def test_a_commarea_link_is_refused_under_the_switch(tmp_path):
    with pytest.raises(ValueError, match="COMMAREA"):
        _cics_translate(tmp_path, DATA_TEXT, LINK_COMMAREA)


@pytest.mark.parametrize("verb", ["PUT CONTAINER('C') CHANNEL('CH') FROM(REC)", "GET CONTAINER('C') CHANNEL('CH') INTO(REC)"])
def test_a_container_area_holding_a_comp5_item_is_refused_under_the_switch(verb, tmp_path):
    with pytest.raises(ValueError, match=r"CONTAINER: the area holds LEN COMP-5"):
        _cics_translate(tmp_path, DATA_GROUP, [*LINK_CHANNEL, f"EXEC CICS {verb} END-EXEC"])
