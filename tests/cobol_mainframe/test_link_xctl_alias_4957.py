"""#4957 (X39 sibling of #4816 / #4956): an XCTL of the LINK caller's COMMAREA reached under another name is refused too.

A LINKed program addresses its caller's COMMAREA; a CALLed subprogram's LINKAGE 01 record (CALL ... USING DFHCOMMAREA)
is that same storage, so an XCTL of it is the XCTL of the caller's area (IBM is silent on copy vs address, register X39).
`in_dfhcommarea` therefore marks any LINKAGE 01 record, not only DFHCOMMAREA; the runtime refuses only when the program
was LINKed with a COMMAREA. The SET ADDRESS OF forms (direct, through a pointer) stay translation holes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_link_xctl_commarea_4816 as prior  # noqa: E402

base = prior.base

MID = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. XCTLMID.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CA.
          03 WS-CODE                 PIC X(4).
          03 WS-NUM                  PIC X(6).
          03 WS-CNT                  PIC X(2).
       01 WS-PTR                     USAGE POINTER.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          03 CA-CODE                 PIC X(4).
          03 CA-NUM                  PIC X(6).
          03 CA-CNT                  PIC X(2).
       01 ALIAS-CA.
          03 AL-CODE                 PIC X(4).
          03 AL-NUM                  PIC X(6).
          03 AL-CNT                  PIC X(2).
       PROCEDURE DIVISION.
@BODY@
           EXEC CICS RETURN END-EXEC.
"""
BODIES = {
    # the caller's area handed to a CALLed subprogram's LINKAGE record, which the subprogram XCTLs
    "call-using": "           CALL 'XCTLSUB' USING DFHCOMMAREA",
    "set-address": "           SET ADDRESS OF ALIAS-CA TO ADDRESS OF DFHCOMMAREA\n"
    "           EXEC CICS XCTL PROGRAM('XCTLEE') COMMAREA(ALIAS-CA) END-EXEC",
    "pointer": "           SET WS-PTR TO ADDRESS OF DFHCOMMAREA\n"
    "           SET ADDRESS OF ALIAS-CA TO WS-PTR\n"
    "           EXEC CICS XCTL PROGRAM('XCTLEE') COMMAREA(ALIAS-CA) END-EXEC",
}
SUB = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. XCTLSUB.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CA                      PIC X(12).
       LINKAGE SECTION.
       01 SUB-AREA.
          03 SB-CODE                 PIC X(4).
          03 SB-NUM                  PIC X(6).
          03 SB-CNT                  PIC X(2).
       PROCEDURE DIVISION USING SUB-AREA.
@BODY@
           GOBACK.
"""
SUB_BODIES = {
    "whole": "           EXEC CICS XCTL PROGRAM('XCTLEE') COMMAREA(SUB-AREA) END-EXEC",
    "field": "           EXEC CICS XCTL PROGRAM('XCTLEE') COMMAREA(SB-NUM)\n                LENGTH(6) END-EXEC",
    "copy": "           MOVE SUB-AREA TO WS-CA\n           EXEC CICS XCTL PROGRAM('XCTLEE') COMMAREA(WS-CA) END-EXEC",
}


def _programs(mid_body: str, sub_body: str) -> dict[str, str]:
    return {
        "XCTLR": prior.CALLER,
        "XCTLMID": MID.replace("@BODY@", mid_body),
        "XCTLSUB": SUB.replace("@BODY@", sub_body),
        "XCTLEE": base.XCTLEE,
    }


def _translate(tmp_path, mid: str, sub: str):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(prior.TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    progs = _programs(BODIES[mid], SUB_BODIES[sub])
    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    for name, src in progs.items():
        (estate / "cbl" / f"{name}.cbl").write_text(src, encoding="ascii")
    import subprocess

    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    project = det_port.estate(estate, tmp_path / "translate")
    out = {}
    for prog in progs:
        svc = prog[0] + prog[1:].lower() + "Service"
        stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / f"{svc}.java").read_text("utf-8")
        out[prog] = P.translate(estate / "cbl" / f"{prog}.cbl", [estate / "cbl"], stub, det_port.PKG,
                                P.estate_files(project), project)  # fmt: skip
    return out


@pytest.mark.parametrize(("sub", "marked"), [("whole", True), ("field", True), ("copy", False)])
def test_a_called_subprograms_linkage_record_is_marked_like_dfhcommarea(tmp_path, sub, marked):
    """The CALLed subprogram's USING record (the whole, or a field of it) is the caller's storage: marked. A copy of it
    in WORKING-STORAGE is not."""
    r = _translate(tmp_path, "call-using", sub)
    assert r["XCTLSUB"].stats["holes"] == [], r["XCTLSUB"].stats["holes"]
    assert ("task.xctlOfLinkage();" in r["XCTLSUB"].java) is marked
    assert "xctlOfLinkage" not in r["XCTLR"].java + r["XCTLEE"].java


@pytest.mark.parametrize("mid", ["set-address", "pointer"])
def test_the_set_address_alias_forms_stay_translation_holes(tmp_path, mid):
    """SET ADDRESS OF (direct or through a pointer) is not translated, so an alias made that way is never run."""
    r = _translate(tmp_path, mid, "copy")
    assert any("SET ADDRESS OF" in str(h) for h in r["XCTLMID"].stats["holes"]), r["XCTLMID"].stats["holes"]
