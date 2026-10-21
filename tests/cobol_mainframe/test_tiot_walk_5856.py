"""#5856 (register A2): CardDemo CBSTM03A's PSA -> TCB -> TIOT walk, in a batch program.

The program reads its own job, step and DD names: SET ADDRESS OF a LINKAGE record TO a NULL pointer (the PSA, at
address 0), then TO the pointers it finds there (PSATNEW -> the TCB, TCBTIO -> the TIOT), and steps through the TIOT's
20-byte DD entries with `COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF ...`, where `TIOT-INDEX REDEFINES BUMP-TIOT POINTER`.
The det runtime lays the three blocks from the job step the run states (DetMvs, `gitgalaxy.mvs.step`), at IBM's
offsets; with no step stated, or a walk past what it lays, the run is refused by name, never guessed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

PKG = "p"

# CBSTM03A l.235-288, verbatim but for PROGRAM-ID and the GOBACK
DATA = """\
       01  PSAPTR                  POINTER.
       01  BUMP-TIOT               PIC S9(08) BINARY VALUE ZERO.
       01  TIOT-INDEX              REDEFINES BUMP-TIOT POINTER.
       LINKAGE SECTION.
       01  ALIGN-PSA        PIC 9(16) BINARY.
       01  PSA-BLOCK.
           05  FILLER       PIC X(536).
           05  TCB-POINT    POINTER.
       01  TCB-BLOCK.
           05  FILLER       PIC X(12).
           05  TIOT-POINT   POINTER.
       01  TIOT-BLOCK.
           05  TIOTNJOB     PIC X(08).
           05  TIOTJSTP     PIC X(08).
           05  TIOTPSTP     PIC X(08).
       01  TIOT-ENTRY.
           05  TIOT-SEG.
               10  TIO-LEN  PIC X(01).
               10  FILLER   PIC X(03).
               10  TIOCDDNM PIC X(08).
               10  FILLER   PIC X(05).
               10  UCB-ADDR PIC X(03).
                   88 NULL-UCB    VALUES LOW-VALUES.
           05  FILLER       PIC X(04).
             88  END-OF-TIOT      VALUE LOW-VALUES.
"""

PROC = """\
           SET ADDRESS OF PSA-BLOCK   TO PSAPTR.
           SET ADDRESS OF TCB-BLOCK   TO TCB-POINT.
           SET ADDRESS OF TIOT-BLOCK  TO TIOT-POINT.
           SET TIOT-INDEX             TO TIOT-POINT.
           DISPLAY 'Running JCL : ' TIOTNJOB ' Step ' TIOTJSTP.

           COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-BLOCK.
           SET ADDRESS OF TIOT-ENTRY  TO TIOT-INDEX.

           DISPLAY 'DD Names from TIOT: '.
           PERFORM UNTIL END-OF-TIOT
                      OR TIO-LEN = LOW-VALUES
               IF NOT NULL-UCB
                   DISPLAY ': ' TIOCDDNM ' -- valid UCB'
               ELSE
                   DISPLAY ': ' TIOCDDNM ' --  null UCB'
               END-IF
               COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-SEG
               SET ADDRESS OF TIOT-ENTRY TO TIOT-INDEX
           END-PERFORM.

           IF NOT NULL-UCB
               DISPLAY ': ' TIOCDDNM ' -- valid UCB'
           ELSE
               DISPLAY ': ' TIOCDDNM ' -- null  UCB'
           END-IF.
"""

# CardDemo app/jcl/CREASTMT.JCL STEP040 (EXEC PGM=CBSTM03A): its DDs in order; SYSOUT DDs have no UCB
CREASTMT = (
    "CREASTMT;STEP040;;STEPLIB:UCB,SYSPRINT:NOUCB,SYSOUT:NOUCB,TRNXFILE:UCB,XREFFILE:UCB,"
    "ACCTFILE:UCB,CUSTFILE:UCB,STMTFILE:UCB,HTMLFILE:UCB"
)


def _src(data: str = DATA, proc: str = PROC) -> str:
    head = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. TIOTW.\n       DATA DIVISION.\n"
    return head + "       WORKING-STORAGE SECTION.\n" + data + "       PROCEDURE DIVISION.\n" + proc + "           GOBACK.\n"


def _translate(src: str):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    work = Path(tempfile.mkdtemp(prefix="t5856"))
    (work / "TIOTW.cbl").write_text(src)
    project = work / "project"
    project.mkdir()
    return P.translate(work / "TIOTW.cbl", [], "public class TiotwService {\n}\n", PKG, None, project), work


def _java() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


_BUILT: dict[str, tuple[Path, Path]] = {}


def _build(src: str) -> tuple[Path, Path]:
    """The translated program compiled against the shared standalone runtime: (its classes, the runtime's)."""
    if src not in _BUILT:
        from test_det_programs import _runtime_classes

        r, work = _translate(src)
        assert not r.stats["holes"], r.stats["holes"]
        rt = _runtime_classes(False, "ISO-8859-1")
        java = r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", "")
        svc = work / "java" / PKG / f"service/{r.service}.java"
        svc.parent.mkdir(parents=True, exist_ok=True)
        svc.write_text(java)
        main = work / "java/Main.java"
        main.write_text(f"public class Main {{ public static void main(String[] a) {{ new {PKG}.service.{r.service}().runProgram(); }} }}\n")
        classes = work / "classes"
        subprocess.run([str(_java() / "javac"), "-encoding", "UTF-8", "-nowarn", "-cp", str(rt), "-d", str(classes),  # noqa: S603
                        str(svc), str(main)], check=True)  # fmt: skip
        _BUILT[src] = (classes, rt)
    return _BUILT[src]


def _run(step: str | None, src: str | None = None) -> subprocess.CompletedProcess:
    classes, rt = _build(src or _src())
    props = [] if step is None else [f"-Dgitgalaxy.mvs.step={step}"]
    return subprocess.run([str(_java() / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", *props,  # noqa: S603
                           "-cp", os.pathsep.join([str(classes), str(rt)]), "Main"],
                          capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip


def test_the_walk_translates_whole_to_the_control_block_runtime():
    r, _ = _translate(_src())
    assert r.stats["holes"] == [], r.stats["holes"]
    assert r.java.count("DetMvs.setAddress(") == 5
    assert r.java.count("DetMvs.advancePointer(") == 2
    assert "DetCics" not in r.java


@pytest.mark.parametrize(
    ("statement", "why"),
    [
        ("SET ADDRESS OF TCB-BLOCK TO ADDRESS OF PSA-BLOCK.", "SET ADDRESS OF (pointers)"),
        ("COMPUTE BUMP-TIOT = BUMP-TIOT * 2.", "REDEFINES overlays a POINTER"),
        ("COMPUTE BUMP-TIOT = 20 + BUMP-TIOT.", "REDEFINES overlays a POINTER"),
        ("COMPUTE BUMP-TIOT ROUNDED = BUMP-TIOT + 20.", "REDEFINES overlays a POINTER"),
        ("MOVE BUMP-TIOT TO OTHER-NUM.", "REDEFINES overlays a POINTER"),
        ("IF BUMP-TIOT = 0 DISPLAY 'X' END-IF.", "REDEFINES overlays a POINTER"),
    ],
)
def test_what_the_batch_lane_cannot_model_is_a_hole(statement, why):
    """A handle is no number: only `view = view +|- n`, ADD / SUBTRACT n and MOVE view TO view move the pointer; any
    other use of the numeric item reads handle bytes and is refused, and `SET ADDRESS OF ... TO ADDRESS OF` stays
    CICS-only."""
    data = DATA.replace("       LINKAGE SECTION.\n", "       01  OTHER-NUM PIC S9(08) BINARY.\n       LINKAGE SECTION.\n")
    r, _ = _translate(_src(data, f"           {statement}\n"))
    assert any(why in h for h in r.stats["holes"]), r.stats["holes"]


def test_a_second_redefines_of_the_numeric_item_keeps_the_pointer_refused():
    data = DATA.replace(
        "       LINKAGE SECTION.\n", "       01  BUMP-BYTES              REDEFINES BUMP-TIOT PIC X(04).\n       LINKAGE SECTION.\n"
    )
    r, _ = _translate(_src(data))
    assert any("a pointer a REDEFINES overlays" in h for h in r.stats["holes"]), r.stats["holes"]


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_creastmt_step_reads_its_names_and_units():
    out = _run(CREASTMT)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "Running JCL : CREASTMT Step STEP040 ",
        "DD Names from TIOT: ",
        ": STEPLIB  -- valid UCB",
        ": SYSPRINT --  null UCB",
        ": SYSOUT   --  null UCB",
        ": TRNXFILE -- valid UCB",
        ": XREFFILE -- valid UCB",
        ": ACCTFILE -- valid UCB",
        ": CUSTFILE -- valid UCB",
        ": STMTFILE -- valid UCB",
        ": HTMLFILE -- valid UCB",  # (the last entry: shown after the loop, END-OF-TIOT ends it)
    ]


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_one_dd_step_and_the_add_subtract_forms():
    assert _run("J1;S1;P1;IN:NOUCB").stdout.splitlines() == ["Running JCL : J1       Step S1      ", "DD Names from TIOT: ",
                                                            ": IN       -- null  UCB"]  # fmt: skip
    proc = PROC.replace(
        "COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-BLOCK.",
        "ADD 30 TO BUMP-TIOT. SUBTRACT 6 FROM BUMP-TIOT.",
    ).replace("COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-SEG", "COMPUTE BUMP-TIOT = BUMP-TIOT - -20")
    out = _run("J;S;;A:UCB,B:NOUCB", _src(DATA, proc))
    assert out.stdout.splitlines()[2:] == [": A        -- valid UCB", ": B        -- null  UCB"], out.stderr


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize(
    ("step", "proc_edit", "why"),
    [
        (None, None, "no job step stated"),
        ("J;S;;", None, "past the fields the stand-in lays"),  # no DD: TIOT-ENTRY would run past the TIOT
        ("J;S;P", None, "no job step stated"),
        ("J;S;;A:TAPE", None, "a DD is NAME:UCB or NAME:NOUCB"),
        ("J;S;;A:UCB", ("+ LENGTH OF TIOT-BLOCK.", "- 100."), "pointer arithmetic leaves the control block"),
        ("J;S;;A:UCB", ("SET ADDRESS OF TIOT-BLOCK  TO TIOT-POINT.", "SET ADDRESS OF PSA-BLOCK TO TIOT-POINT."),
         "past the fields the stand-in lays"),  # (the PSA's 544 bytes over a 48-byte TIOT)
    ],
)
def test_what_the_stand_in_does_not_lay_is_refused_by_name(step, proc_edit, why):
    proc = PROC if proc_edit is None else PROC.replace(*proc_edit, 1)
    out = _run(step, _src(DATA, proc))
    assert out.returncode != 0 and why in out.stderr, (out.stdout, out.stderr)
