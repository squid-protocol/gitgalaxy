"""#8076: a program's channel DTO (`<Program>ChannelIn`) is no COMMAREA contract.

A program with no DFHCOMMAREA that reads a channel is generated as `handleLink(ChnretChannelIn request)`: the class has
one property per container, typed by the container's record DTO (a comment with no PIC, no offset, no `->` part).
`Generated.contract` read it as the COMMAREA layout, and the first RETURN / LINK / XCTL COMMAREA the program ran
(`dto_for`) refused "a property the port cannot convert (<record DTO>)" -- three blind-trial programs. IBM: the COMMAREA
operand is the bytes of the area named, whatever channel the program also holds (CICS TS 6.x, EXEC CICS RETURN).
"""

from __future__ import annotations

from pathlib import Path

import pytest

CHANNEL_IN = """\
package com.x.dto.contract;

/**
 * The containers Chnret reads (CICS resources field testing: untested).
 */
public class ChnretChannelIn {

    // GET CONTAINER(REQ) at line 9 on the current channel, INTO WS-REQ
    private ChnretWsReq req;

    // GET CONTAINER(NOTE) at line 10 on the current channel
    // TODO: the layout of WS-NOTE was not found; carried as text.
    private String note;
}
"""
WS_REQ = """\
package com.x.dto.contract;

/**
 * COBOL record WS-REQ (CHNRET.cbl), 8 bytes, from GitGalaxy's verified skeleton.
 */
public class ChnretWsReq {

    // RQ-KEY: PIC X(8), offset 0, 8 bytes (CHNRET.cbl)
    private String rqKey;
}
"""
COMMAREA = """\
package com.x.dto.contract;

/**
 * COBOL record DFHCOMMAREA (CALLEE.cbl), 5 bytes, from GitGalaxy's verified skeleton.
 */
public class CalleeDfhcommarea {

    // CA-TAIL: PIC X(5), offset 0, 5 bytes (CALLEE.cbl)
    private String caTail;
}
"""
STUB = (
    "package com.x.service;\nimport com.x.cics.CicsTask;\n"
    "public class ChnretService {\n"
    "    public ChnretChannelIn handleLink(ChnretChannelIn request) { return request; }\n"
    "    public ChnretChannelIn linkCallee(CalleeDfhcommarea request) { return null; }\n"
    "    public void xctlChnchan(ChnretChannelIn request) {}\n"
    "    public void runTask(CicsTask task) {}\n}\n"
)
CHNRET = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CHNRET.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-REQ.
          05 RQ-KEY                 PIC X(8).
       01 WS-AREA                   PIC X(5).
       PROCEDURE DIVISION.
           EXEC CICS GET CONTAINER('REQ') INTO(WS-REQ) END-EXEC
           MOVE 'abcde' TO WS-AREA
           EXEC CICS RETURN COMMAREA(WS-AREA) LENGTH(5) END-EXEC.
"""


def _project(tmp_path: Path, channel: str = CHANNEL_IN) -> Path:
    contract = tmp_path / "proj/src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    for name, text in (("ChnretChannelIn", channel), ("ChnretWsReq", WS_REQ), ("CalleeDfhcommarea", COMMAREA)):
        (contract / f"{name}.java").write_text(text, encoding="utf-8")
    return tmp_path / "proj"


def test_a_channel_dto_is_not_the_programs_commarea_contract(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    g = C.Generated(_project(tmp_path), STUB)
    assert g.contract is None  # handleLink takes the channel DTO
    assert g.xctl == {}  # nor is a channel callee's DTO a COMMAREA a XCTL could be typed by
    assert g.links == {"CALLEE": "CalleeDfhcommarea"}  # a real COMMAREA DTO still types its LINK


def test_the_channels_record_dto_is_still_a_record_dto(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    g = C.Generated(_project(tmp_path), STUB)
    assert g.records["WS-REQ"] == "ChnretWsReq"
    assert [(x.var, x.size) for x in g.dto("ChnretWsReq").leaves] == [("rqKey", 8)]


def test_a_commarea_contract_stays_the_contract(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    stub = "public Calleedfhcommarea x;\n    public CalleeDfhcommarea handleLink(CalleeDfhcommarea request) {}\n"
    assert C.Generated(_project(tmp_path), stub).contract == "CalleeDfhcommarea"


def test_a_commarea_dto_that_merely_names_containers_is_not_taken_for_a_channel(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    other = COMMAREA.replace("CA-TAIL: PIC X(5)", "CA-TAIL (the containers Chnret reads): PIC X(5)")
    proj = _project(tmp_path)
    (proj / "src/main/java/com/x/dto/contract/CalleeDfhcommarea.java").write_text(other, encoding="utf-8")
    assert C.Generated(proj, STUB).links == {"CALLEE": "CalleeDfhcommarea"}


def test_a_return_commarea_in_a_channel_program_translates_without_a_hole(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    proj = _project(tmp_path)
    (tmp_path / "CHNRET.cbl").write_text(CHNRET, encoding="utf-8")
    vsam = proj / "src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    r = P.translate(tmp_path / "CHNRET.cbl", [tmp_path], STUB, "com.x", {}, proj)
    assert not any("cannot convert" in h for h in r.stats["holes"]), r.stats["holes"]
