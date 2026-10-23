"""#5233 (register I5): a BMP entered USING its I/O PCB whose ENTRY 'DLITCBL' lists only the DB PCBs (PAUDBLOD, PSB
CMPAT=YES). IMS enters a BMP at the PROCEDURE DIVISION header, so the header's list is the I/O PCB then the ENTRY list.
Both runtimes (det/dli.py and tests/tools/equivalence_ims.py) must read the same program the same way:

* header USING = I/O PCB + exactly the ENTRY list, with EXEC DLI or CALL 'CBLTDLI': a BMP (the I/O PCB counts in PCB(n));
* ENTRY with no header USING, or a header that is not that shape: the DLITCBL batch path (PAUDBUNL, DBUNLDGS);
* the I/O PCB handed to CBLTDLI (an IMS TM message call) is refused by name."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_ims as ei  # noqa: E402

PKG = "p"
CORPUS = (
    Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    / "aws-mainframe-modernization-carddemo"
)
CBL = CORPUS / "app" / "app-authorization-ims-db2-mq" / "cbl"
WS = ["WORKING-STORAGE SECTION.", "01  FN PIC X(4) VALUE 'GU  '.", "01  IOA PIC X(20)."]
LINKAGE = ["LINKAGE SECTION.", "01  IO-PCB PIC X.", "01  DB-PCB PIC X(46)."]


def _src(using: str, entry: str | None, stmt: str) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. DLIT.", "DATA DIVISION.", *WS, *LINKAGE, f"PROCEDURE DIVISION{using}.",
             "MAIN-PARA.", *([f"    ENTRY 'DLITCBL' USING {entry}."] if entry else []), f"    {stmt}", "    GOBACK."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


CALL = "CALL 'CBLTDLI' USING FN DB-PCB IOA"
EXEC = "EXEC DLI GN USING PCB(2) SEGMENT(DEPT) INTO(IOA) END-EXEC"


def _translate(tmp_path: Path, src: str):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(ROOT / "tests" / "cobol_mainframe"))
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "DLIT.cbl").write_text(src)
    project = tmp_path / "project"
    tdp._batch_package(project / "src/main/java")
    return P.translate(tmp_path / "DLIT.cbl", [], "public class DlitService {\n}\n", PKG, None, project)


@pytest.mark.parametrize("stmt", [CALL, EXEC])
@pytest.mark.parametrize("entry", [None, "DB-PCB"])
def test_a_bmp_with_io_pcb_first_is_entered_at_its_header_whether_or_not_an_entry_repeats_the_db_pcbs(
    tmp_path, stmt, entry
):
    src = _src(" USING IO-PCB DB-PCB", entry, stmt)
    assert ei.bmp_using(src) == ["IO-PCB", "DB-PCB"]
    r = _translate(tmp_path, src)
    java = r.java
    assert re.search(r"DetDli\.enterBmp\(\w+, \w+\);", java), java
    assert "DetDli.enter(" not in java
    if stmt is CALL:
        assert not r.stats["holes"], r.stats["holes"]
        assert re.search(r"DetDli\.call\(", java), java


@pytest.mark.parametrize("stmt", [CALL, EXEC])
def test_an_entry_with_no_header_using_stays_the_batch_dlitcbl_path(tmp_path, stmt):
    src = _src("", "DB-PCB", stmt)
    assert ei.bmp_using(src) is None
    assert ei.entry_using(src) == ["DB-PCB"]
    java = _translate(tmp_path, src).java
    assert re.search(r"DetDli\.enter\(\w+\);", java), java
    assert "enterBmp" not in java


def test_an_entry_list_that_is_not_the_headers_minus_its_io_pcb_is_the_batch_list():
    src = _src(" USING IO-PCB DB-PCB", "IO-PCB DB-PCB", CALL)
    assert ei.bmp_using(src) is None and ei.entry_using(src) == ["IO-PCB", "DB-PCB"]
    assert ei.bmp_using(_src(" USING IO-PCB", None, CALL)) == ["IO-PCB"]  # one item: stage() refuses it (no DB PCB)


def test_the_io_pcb_given_to_cbltdli_is_refused_by_name(tmp_path):
    r = _translate(tmp_path, _src(" USING IO-PCB DB-PCB", "DB-PCB", "CALL 'CBLTDLI' USING FN IO-PCB IOA"))
    assert any("I/O PCB IO-PCB" in h and "CBLTDLI" in h for h in r.stats["holes"]), r.stats["holes"]


@pytest.mark.skipif(
    not (CBL / "PAUDBLOD.CBL").is_file(), reason="needs the CardDemo corpus (GITGALAXY_MAINFRAME_CORPORA)"
)
def test_paudblod_is_a_bmp_whose_entry_hides_the_io_pcb_and_translates_whole(tmp_path):
    source = (CBL / "PAUDBLOD.CBL").read_text(errors="replace")
    assert ei.entry_using(source) == ["PAUTBPCB"]
    assert ei.bmp_using(source) == ["IO-PCB-MASK", "PAUTBPCB"]
    # the unload program keeps the batch path: its ENTRY is the only list
    unl = (CBL / "PAUDBUNL.CBL").read_text(errors="replace")
    assert ei.bmp_using(unl) is None and ei.entry_using(unl)
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(ROOT / "tests" / "cobol_mainframe"))
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    project = tmp_path / "project"
    tdp._batch_package(project / "src/main/java")
    r = P.translate(CBL / "PAUDBLOD.CBL", [CORPUS / "app" / "app-authorization-ims-db2-mq" / "cpy"],
                    "public class PaudblodService {\n}\n", PKG, None, project)  # fmt: skip
    assert not r.stats["holes"], r.stats["holes"]
    assert re.search(r"DetDli\.enterBmp\(", r.java) and "DetDli.enter(" not in r.java
    assert len(re.findall(r"DetDli\.call\(", r.java)) == 3  # ISRT root, GU root, ISRT child
