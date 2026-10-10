"""#4806: after a LINK, the caller's COMMAREA holds the bytes the callee left there -- never its DTO written back.

IBM (EXEC CICS LINK, COMMAREA): the area is passed by address; the linked program reads and writes the caller's own
storage, so a byte it does not write keeps the caller's value, invalid numeric content included. The det port passed
the caller's area to the callee as the callee's DTO and, after the LINK, wrote that DTO back over the caller's bytes
(`in_<Dto>`): a PIC 9 field of the callee's layout holding the caller's spaces was read as a number and came back as
digits (CBSA BNK1UAC -> INQACC, an account not on file: COMM-CUSTNO / COMM-SCODE spaces became 0000000016 / 000016).

A det callee takes the bytes (task.linkArea()) and writes back what it left in them; CicsTask.linkAreaBack() tells the
caller so, and only a callee that took the object (a model port) has its DTO written back. An XCTL lost the same bytes
the other way (its target's DFHCOMMAREA was the DTO's reading of them): it passes them beside the DTO now, and a det
target takes them as a LINKed one does.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"

# the caller's layout is text (as BNK1UAC's COMM-CUSTNO PIC X(10)); the callee's is numeric there (INQACC-CUSTNO
# PIC 9(10)). The caller fills its area with spaces, LINKs, and gives back what it holds.
CALLER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LNKCALLR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CA.
          03 WS-CODE                 PIC X(4).
          03 WS-NUM                  PIC X(6).
          03 WS-CNT                  PIC X(2).
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          03 CA-CODE                 PIC X(4).
          03 CA-NUM                  PIC X(6).
          03 CA-CNT                  PIC X(2).
       PROCEDURE DIVISION.
           MOVE SPACES TO WS-CA
           EXEC CICS LINK PROGRAM('LNKCALEE') COMMAREA(WS-CA)
                LENGTH(12) END-EXEC
           MOVE WS-CA TO DFHCOMMAREA
           EXEC CICS RETURN END-EXEC.
"""
# the callee writes its code and its count; its number (the caller's spaces) it never writes
CALLEE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LNKCALEE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          03 LK-CODE                 PIC X(4).
          03 LK-NUM                  PIC 9(6).
          03 LK-CNT                  PIC 9(2).
       PROCEDURE DIVISION.
           MOVE 'DONE' TO LK-CODE
           MOVE 7 TO LK-CNT
           EXEC CICS RETURN END-EXEC.
"""


# #4806 (XCTL): the same area passed by XCTL -- its target's DFHCOMMAREA is the bytes, which it SENDs as they are.
# (The harness runs a task's XCTL target only below a LINK -- at level 1 the XCTL is the task's last event -- so the
# case's program LINKs to the one that XCTLs.)
XCTLR = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. XCTLR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          03 CA-CODE                 PIC X(4).
          03 CA-NUM                  PIC X(6).
          03 CA-CNT                  PIC X(2).
       PROCEDURE DIVISION.
           EXEC CICS LINK PROGRAM('XCTLMID') END-EXEC
           EXEC CICS RETURN END-EXEC.
"""
XCTLMID = CALLER.replace("LNKCALLR", "XCTLMID").replace(
    """           EXEC CICS LINK PROGRAM('LNKCALEE') COMMAREA(WS-CA)
                LENGTH(12) END-EXEC
           MOVE WS-CA TO DFHCOMMAREA
""",
    """           EXEC CICS XCTL PROGRAM('XCTLEE') COMMAREA(WS-CA) END-EXEC
""",
)
XCTLEE = CALLEE.replace("LNKCALEE", "XCTLEE").replace(
    "           EXEC CICS RETURN END-EXEC.\n",
    "           EXEC CICS SEND TEXT FROM(DFHCOMMAREA) LENGTH(12) ERASE\n"
    "                END-EXEC\n"
    "           EXEC CICS RETURN END-EXEC.\n",
)
PROGRAMS = {
    "link": {"LNKCALLR": CALLER, "LNKCALEE": CALLEE},
    "xctl": {"XCTLR": XCTLR, "XCTLMID": XCTLMID, "XCTLEE": XCTLEE},
}  # (the case's program first)


def _estate(tmp_path: Path, kind: str) -> Path:
    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    for name, src in PROGRAMS[kind].items():
        (estate / "cbl" / f"{name}.cbl").write_text(src, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    return estate


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
@pytest.mark.parametrize("kind", ["link", "xctl"])
def test_the_target_leaves_the_bytes_it_did_not_write(tmp_path, kind):
    """The det programs against GnuCOBOL: LINK -- the caller's COMMAREA after the LINK (the case's DFHCOMMAREA, which
    it copies there) is the callee's writes and the caller's spaces; XCTL -- the target's DFHCOMMAREA, as it SENDs
    it."""
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = _estate(tmp_path, kind)
    caller, *others = PROGRAMS[kind]
    case = {"kind": "cics", "corpus": "link-4806-synthetic", "program": caller, "program_source": f"cbl/{caller}.cbl",
            "copy_dirs": [], "transid": "LNK1", "clock": "2026/10/09 10:00:00.00", "datasets": {}, "screens": {},
            "programs": [{"program": p, "program_source": f"cbl/{p}.cbl"} for p in others],
            "scenarios": [{"name": "target-leaves-the-number", "commarea": None}]}  # fmt: skip
    if kind == "link":  # the caller's COMMAREA after the LINK, copied into its own: the case's result
        case.update({"commarea": {"segments": [{"copybook": f"cbl/{caller}.cbl", "record": "DFHCOMMAREA"}]},
                     "linked": True, "scenarios": [{"name": "target-leaves-the-number", "commarea": {}}]})  # fmt: skip
    else:  # (the layout the XCTL's COMMAREA event is read by: the area's, as XCTLR's DFHCOMMAREA lays it out)
        case["commarea"] = {"segments": [{"copybook": f"cbl/{caller}.cbl", "record": "DFHCOMMAREA"}]}
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    java = {}
    for prog in PROGRAMS[kind]:
        svc = prog[0] + prog[1:].lower() + "Service"
        stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / f"{svc}.java").read_text("utf-8")
        r = P.translate(estate / "cbl" / f"{prog}.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                        project)  # fmt: skip
        assert r.stats["holes"] == [], (prog, r.stats["holes"])
        (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
        java[prog] = r.java
    # the COMMAREA goes as the target's DTO (the path #4806 is about), with its bytes beside it
    assert ("task.linkAreaBack()" in java[caller]) if kind == "link" else (".bytes);" in java["XCTLMID"])
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "link-4806", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    # the oracle: the target's writes, and the caller's spaces where it wrote nothing
    if kind == "link":
        got = [p.read_bytes()[:12] for p in (keep / "cobol").rglob("commarea.out")]
    else:
        events = report["outputs"]["target-leaves-the-number"]["cobol"]
        got = [e["text"].encode("latin-1") for e in events if e.get("event") == "SEND-TEXT"]
    assert got and all(b == b"DONE      07" for b in got), got


TASK_MAIN = """package com.acme.cics;

public class Main {
    public static void main(String[] a) {
        CicsTask task = new CicsTask("T001", "ENTER", null, null, java.util.Map.of());
        task.withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return !p.equals("NONE");
            }

            public void run(String p, CicsTask t) {
                byte[] b = p.equals("BYTES") ? t.linkArea() : null;  // a det port takes the bytes, when passed
                if (b != null) {
                    b[0] = 'D';
                }
                t.returnTransid(null, null);
            }
        });
        task.withProgram("CALLER");
        byte[] area = "    ".getBytes();
        System.out.println(task.link("BYTES", new Object(), 4, area) + " " + task.linkAreaBack() + " " + (char) area[0]);
        System.out.println(task.link("OBJECT", new Object(), 4, area) + " " + task.linkAreaBack());
        task.link("BYTES", new Object(), 4, area);
        System.out.println(task.link("NONE", new Object(), 4, area) + " " + task.linkAreaBack());
        task.link("BYTES", new Object(), 4, area);
        System.out.println(task.link("BYTES", new Object(), 4) + " " + task.linkAreaBack());
    }
}
"""


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin" / "javac").is_file() else None


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_the_caller_learns_whether_the_linked_program_took_the_bytes(tmp_path):
    """CicsTask.linkAreaBack(): true only after a NORMAL LINK whose program took the area's bytes (task.linkArea()) --
    then the generated caller keeps them and writes no DTO over them; a program that took the object, a failed LINK
    or a LINK without bytes: false (the DTO is all the caller has back)."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    root = tmp_path / "src" / "com" / "acme" / "cics"
    root.mkdir(parents=True)
    (root / "CicsTask.java").write_text(CICS_TASK_JAVA.replace("__PACKAGE__", "com.acme").replace("__ZONE__", "UTC"),
                                        encoding="utf-8")  # fmt: skip
    (root / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "com.acme"), encoding="utf-8")
    (root / "Main.java").write_text(TASK_MAIN, encoding="utf-8")
    jdk = _jdk()
    built = subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, root.glob("*.java"))], capture_output=True, text=True, check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr[:3000]
    out = subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "com.acme.cics.Main"],  # noqa: S603
                         capture_output=True, text=True, check=True).stdout.splitlines()  # fmt: skip
    assert out == ["NORMAL true D", "NORMAL false", "PGMIDERR false", "NORMAL false"]
