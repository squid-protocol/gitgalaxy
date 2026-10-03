"""det-port statements end to end: small COBOL programs, each run by GnuCOBOL (`cobc -x -std=ibm -fsign=EBCDIC`, the
harness's oracle) and translated (gitgalaxy/tools/cobol_to_java/det) and run as Java -- their DISPLAY output equal.

Each program DISPLAYs alphanumeric and unsigned DISPLAY items only, whose external form is their bytes on both sides.
The port runs on its own (runProgram) with the standalone runtime; nothing of a generated project is needed."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

IMAGE = "gitgalaxy-gnucobol:3"
PKG = "p"


def program(name: str, data: list[str], proc: list[str]) -> str:
    lines = ["       IDENTIFICATION DIVISION.", f"       PROGRAM-ID. {name}.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION."]  # fmt: skip
    lines += [f"       {x}" for x in data]
    lines += ["       PROCEDURE DIVISION."] + [f"           {x}" for x in proc] + ["           GOBACK."]
    return "\n".join(lines) + "\n"


PROGRAMS = {
    # FUNCTION TRIM: spaces only, an all-space argument zero-length (COACTUPC's alphabetic-field check)
    "TRIMS": program(
        "TRIMS",
        [
            "01 S PIC X(10) VALUE SPACES.",
            "01 A PIC X(10) VALUE '  AB  '.",
            "01 L PIC X(10) VALUE LOW-VALUES.",
            "01 N PIC 9(4) VALUE 0.",
        ],
        [
            "MOVE FUNCTION LENGTH(FUNCTION TRIM(S)) TO N",
            "DISPLAY N",
            "MOVE FUNCTION LENGTH(FUNCTION TRIM(A)) TO N",
            "DISPLAY N",
            "MOVE FUNCTION LENGTH(FUNCTION TRIM(L)) TO N",
            "DISPLAY N",
            "DISPLAY '[' FUNCTION TRIM(S) ']'",
            "DISPLAY '[' FUNCTION TRIM(A LEADING) ']'",
            "DISPLAY '[' FUNCTION TRIM(A TRAILING) ']'",
            "IF FUNCTION LENGTH(FUNCTION TRIM(S)) = 0",
            "    DISPLAY 'EMPTY'",
            "END-IF",
        ],
    ),
    # GO TO the end of an outer PERFORM's range from inside an inner one: the outer PERFORM returns
    "GOTOOUT": "\n".join(
        [
            "       IDENTIFICATION DIVISION.",
            "       PROGRAM-ID. GOTOOUT.",
            "       DATA DIVISION.",
            "       WORKING-STORAGE SECTION.",
            "       01 N PIC 9(3) VALUE 0.",
            "       PROCEDURE DIVISION.",
            "       MAIN-PARA.",
            "           PERFORM A THRU A-EXIT",
            "           DISPLAY 'BACK IN MAIN N=' N",
            "           GOBACK.",
            "       A.",
            "           DISPLAY 'IN A'",
            "           PERFORM B THRU B-EXIT",
            "           DISPLAY 'AFTER B'.",
            "       A-EXIT.",
            "           DISPLAY 'IN A-EXIT'",
            "           EXIT.",
            "       B.",
            "           ADD 1 TO N",
            "           DISPLAY 'IN B N=' N",
            "           IF N > 3",
            "              DISPLAY 'LOOPED'",
            "              GOBACK",
            "           END-IF",
            "           GO TO A-EXIT.",
            "       B-EXIT.",
            "           EXIT.",
            "",
        ]
    ),  # fmt: skip
    "UNSTR1": program(
        "UNSTR1",
        [
            "01 SRC PIC X(30) VALUE 'ALPHA,BETA,,GAMMA DELTA'.",
            "01 A PIC X(8) VALUE SPACES.",
            "01 B PIC X(8) VALUE SPACES.",
            "01 C PIC X(8) VALUE SPACES.",
            "01 D PIC X(8) VALUE SPACES.",
            "01 DA PIC X VALUE SPACE.",
            "01 DB PIC X VALUE SPACE.",
            "01 CA PIC 9(2) VALUE 0.",
            "01 CB PIC 9(2) VALUE 0.",
            "01 PTR PIC 9(2) VALUE 1.",
            "01 TAL PIC 9(2) VALUE 0.",
        ],
        [
            "UNSTRING SRC DELIMITED BY ',' OR SPACE",
            "    INTO A DELIMITER IN DA COUNT IN CA",
            "         B DELIMITER IN DB COUNT IN CB C D",
            "    WITH POINTER PTR TALLYING IN TAL",
            "END-UNSTRING",
            "DISPLAY '[' A '][' B '][' C '][' D ']'",
            "DISPLAY '[' DA '][' DB ']' CA ' ' CB ' ' PTR ' ' TAL",
        ],
    ),
    "UNSTR2": program(
        "UNSTR2",
        [
            "01 SRC PIC X(20) VALUE 'A--B---C'.",
            "01 A PIC X(4) VALUE SPACES.",
            "01 B PIC X(4) VALUE SPACES.",
            "01 FLAG PIC X(10) VALUE 'NONE'.",
        ],
        [
            "UNSTRING SRC DELIMITED BY ALL '-' INTO A B",
            "    ON OVERFLOW MOVE 'OVERFLOW' TO FLAG",
            "    NOT ON OVERFLOW MOVE 'NO-OVF' TO FLAG",
            "END-UNSTRING",
            "DISPLAY '[' A '][' B '] ' FLAG",
        ],
    ),
    "UNSTR3": program(
        "UNSTR3",
        [
            "01 SRC PIC X(12) VALUE 'ABCDEFGHIJKL'.",
            "01 A PIC X(5) VALUE SPACES.",
            "01 B PIC X(5) VALUE SPACES.",
        ],
        [
            "UNSTRING SRC INTO A B",
            "DISPLAY '[' A '][' B ']'",
        ],
    ),
    "STRNG1": program(
        "STRNG1",
        [
            "01 OUT PIC X(10) VALUE ALL '*'.",
            "01 PTR PIC 9(2) VALUE 3.",
            "01 FLAG PIC X(10) VALUE 'NONE'.",
            "01 W PIC X(6) VALUE 'AB CD'.",
        ],
        [
            "STRING W DELIMITED BY SPACE",
            "    'XYZ' DELIMITED BY SIZE",
            "    'LONGTAIL' DELIMITED BY SIZE",
            "    INTO OUT WITH POINTER PTR",
            "    ON OVERFLOW MOVE 'OVERFLOW' TO FLAG",
            "END-STRING",
            "DISPLAY '[' OUT '] ' PTR ' ' FLAG",
        ],
    ),
    # B3 typed state: lifted items (String / long / BigDecimal) and items a use keeps as bytes (refmod, group move)
    "TYPED": program(
        "TYPED",
        [
            "01 FLAG PIC X(3) VALUE 'N'.",
            "   88 FLAG-YES VALUE 'Y'.",
            "   88 FLAG-NO VALUE 'N'.",
            "01 NAME PIC X(8) VALUE SPACES.",
            "01 SRC PIC X(12) VALUE 'ABCDEFGHIJKL'.",
            "01 CNT PIC S9(4) COMP VALUE 0.",
            "01 WRAP PIC 9(4) COMP VALUE 0.",
            "01 AMT PIC S9(5)V99 VALUE 1.50.",
            "01 PAMT PIC S9(5)V99 COMP-3 VALUE -2.25.",
            "01 OUTN PIC 9(7)V99 VALUE 0.",
            "01 GRP.",
            "   05 G1 PIC X(2) VALUE 'AB'.",
            "   05 G2 PIC 9(3) VALUE 7.",
            "01 GCOPY PIC X(5) VALUE SPACES.",
        ],
        [
            "IF FLAG-NO DISPLAY 'NO' END-IF",
            "SET FLAG-YES TO TRUE",
            "IF FLAG = 'Y' DISPLAY 'YES [' FLAG ']' END-IF",
            "MOVE SRC TO NAME",
            "DISPLAY '[' NAME ']'",
            "MOVE 'XY' TO NAME",
            "IF NAME < 'XZ' DISPLAY 'LESS' END-IF",
            "MOVE NAME(2:1) TO FLAG",
            "DISPLAY '[' FLAG ']'",
            "PERFORM 70000 TIMES ADD 1 TO CNT END-PERFORM",
            # (not below zero: GnuCOBOL's ADD / SUBTRACT wrap an unsigned binary item there, its COMPUTE / MOVE
            # and IBM store the absolute value -- a declared difference, det_port_design.md)
            "ADD 70000 TO WRAP",
            "SUBTRACT 3 FROM WRAP",
            "MOVE CNT TO OUTN",
            "DISPLAY OUTN",
            "MOVE WRAP TO OUTN",
            "DISPLAY OUTN",
            "ADD 123456.789 TO AMT",
            "MOVE AMT TO OUTN",
            "DISPLAY OUTN",
            "COMPUTE PAMT ROUNDED = PAMT * 3 / 7",
            "MOVE PAMT TO OUTN",
            "DISPLAY OUTN",
            "IF PAMT < 0 DISPLAY 'NEGATIVE' END-IF",
            "ADD 5 TO G2",
            "MOVE GRP TO GCOPY",
            "DISPLAY '[' GCOPY ']'",
        ],
    ),
    # negative zero: a signed item can hold -0 (a MOVE keeps the sending sign through truncation), which a typed
    # BigDecimal cannot -- such an item must stay byte storage
    "NEGZERO": program(
        "NEGZERO",
        [
            "01 SRC PIC S9V99 VALUE -0.05.",
            "01 A PIC S9(3) VALUE 0.",
            "01 B PIC S9(3) VALUE 0.",
            "01 C PIC S9(3) VALUE 0.",
            "01 OUTA PIC X(3) VALUE SPACES.",
            "01 OUTB PIC X(3) VALUE SPACES.",
            "01 OUTC PIC X(3) VALUE SPACES.",
            "01 GA.",
            "   05 DA PIC S9(3) VALUE 0.",
            "01 GB.",
            "   05 DB PIC S9(3) VALUE 0.",
            "01 GC.",
            "   05 DC PIC S9(3) VALUE 0.",
            "01 E PIC S9(3) VALUE 5.",
            "01 GE.",
            "   05 XE PIC S9(3) VALUE 0.",
            "01 OUTE PIC X(3) VALUE SPACES.",
            "01 WIDE PIC S9(5)V99 VALUE 0.",
            "01 GW.",
            "   05 DW PIC S9(5)V99 VALUE 0.",
            "01 OUTW PIC X(7) VALUE SPACES.",
        ],
        [
            "MOVE SRC TO A",
            "COMPUTE B = SRC",
            "SUBTRACT 0.05 FROM C",
            "MOVE A TO DA",
            "MOVE B TO DB",
            "MOVE C TO DC",
            "MOVE GA TO OUTA",
            "MOVE GB TO OUTB",
            "MOVE GC TO OUTC",
            "DISPLAY '[' OUTA '][' OUTB '][' OUTC ']'",
            "IF A = 0 DISPLAY 'A ZERO' END-IF",
            "MOVE -1000 TO E",
            "MOVE E TO XE",
            "MOVE GE TO OUTE",
            "MOVE C TO WIDE",
            "SUBTRACT 1.25 FROM WIDE",
            "MOVE WIDE TO DW",
            "MOVE GW TO OUTW",
            "DISPLAY '[' OUTE '][' OUTW ']'",
        ],
    ),
    # typed groups: items inside groups used whole -- read whole (SRCG), written whole (DSTG, by MOVE and
    # INITIALIZE), and through a reference modification of the group
    "TGROUPS": program(
        "TGROUPS",
        [
            "01 SRCG.",
            "   05 S-NAME PIC X(6) VALUE 'ALPHA'.",
            "   05 S-CNT PIC S9(4) COMP VALUE 7.",
            "   05 S-AMT PIC S9(5)V99 VALUE 12.5.",
            "01 DSTG.",
            "   05 D-NAME PIC X(6) VALUE SPACES.",
            "   05 D-CNT PIC S9(4) COMP VALUE 0.",
            "   05 D-AMT PIC S9(5)V99 VALUE 0.",
            "01 RAW PIC X(15) VALUE SPACES.",
            "01 NSTG.",
            "   05 N-NAME PIC X(4) VALUE 'OLD '.",
            "   05 N-REST PIC X(4) VALUE SPACES.",
            "01 OUTN PIC 9(7)V99 VALUE 0.",
            "01 OUTC PIC 9(4) VALUE 0.",
        ],
        [
            "MOVE 'BETA' TO S-NAME",
            "ADD 5 TO S-CNT",
            "ADD 1.25 TO S-AMT",
            "MOVE SRCG TO RAW",
            "MOVE SRCG TO DSTG",
            "IF D-NAME = 'BETA' DISPLAY 'NAME ' D-NAME END-IF",
            "MOVE D-CNT TO OUTC",
            "MOVE D-AMT TO OUTN",
            "DISPLAY OUTC ' ' OUTN",
            "MOVE 'GAMMA!' TO D-NAME",
            "MOVE DSTG(1:3) TO RAW",
            "DISPLAY '[' RAW ']'",
            "INITIALIZE DSTG",
            "MOVE D-CNT TO OUTC",
            "DISPLAY '[' D-NAME '] ' OUTC",
            "MOVE SPACES TO DSTG",
            "MOVE 'Z' TO D-NAME",
            "DISPLAY '[' D-NAME ']'",
            "STRING 'NESTED' DELIMITED BY SIZE INTO NSTG",
            "    ON OVERFLOW DISPLAY 'OVF [' N-NAME ']'",
            "    NOT ON OVERFLOW DISPLAY 'OK [' N-NAME ']'",
            "END-STRING",
            "DISPLAY '[' N-NAME ']'",
        ],
    ),
}


def _java() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _cobol(src: str, work: Path) -> str:
    (work / "prog.cbl").write_text(src)
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          "cobc -x -std=ibm -fsign=EBCDIC prog.cbl -o prog 2>&1 && ./prog"], capture_output=True,
                         text=True, check=False)  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout


def _java_run(name: str, src: str, work: Path, typed: bool = False, groups: bool = False) -> str:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / f"{name}.cbl").write_text(src)
    project = work / "project"  # no generated project: the standalone runtime
    project.mkdir()
    r = P.translate(work / f"{name}.cbl", [], f"public class {name.title()}Service {{\n}}\n", PKG, None, project,
                    typed=typed, groups=groups)  # fmt: skip
    assert not r.stats["holes"], r.stats["holes"]
    srcdir = work / "java"
    java = r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", "")
    # the runtime without its CICS boundary (it needs a generated CicsTask)
    runtime = {k: v for k, v in P.runtime_files(PKG, batch=False).items() if not k.startswith("cobolrt/cics/")}
    for rel, text in [(f"service/{r.service}.java", java), *runtime.items()]:
        (srcdir / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (srcdir / PKG / rel).write_text(text)
    # the generated project's record charset, as the harness runs it: ISO-8859-1
    rec = srcdir / PKG / "entity/vsam/CobolRecords.java"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset."
                   "Charset charset() {\n        return java.nio.charset.StandardCharsets.ISO_8859_1;\n    }\n}\n")  # fmt: skip
    (srcdir / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ "
                                      f"new {PKG}.service.{r.service}().runProgram(); }} }}\n")  # fmt: skip
    jdk = _java()
    files = [str(f) for f in srcdir.rglob("*.java")]
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(work / "classes"), *files], check=True)  # noqa: S603
    return subprocess.run([str(jdk / "java"), "-cp", str(work / "classes"), "Main"], capture_output=True, text=True,  # noqa: S603
                          check=True).stdout  # fmt: skip


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed", "groups"])
@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_program_output_is_gnucobols(name, mode, tmp_path):
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = _cobol(PROGRAMS[name], cob)
    got = _java_run(name, PROGRAMS[name], tmp_path, mode != "bytes", mode == "groups")
    assert got == want, f"java {got!r} != cobol {want!r}"


def _byte_storage(java: str, name: str) -> bool:
    """`name` is held as bytes: declared as a Field bound to its storage (one line since #4202), never as a typed
    Java field."""
    bound = re.search(rf"^    private final Field {name} = Field\.\w+\(", java, re.M)
    typed = re.search(rf"^    private (?:String|long|BigDecimal) {name};", java, re.M)
    return bool(bound) and not typed


def test_typed_lifts_only_what_every_use_allows(tmp_path):
    """TYPED's lifts, without running anything: NAME is read by reference modification, G1 / G2 sit in a group that
    is moved whole and OUTN is DISPLAYed (a numeric item's external form), so they stay byte storage; the rest are
    typed fields."""
    pytest.importorskip("tree_sitter_language_pack")  # the translator's parser (not in every CI job)
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "TYPED.cbl").write_text(PROGRAMS["TYPED"])
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "TYPED.cbl", [], "public class TypedService {\n}\n", PKG, None, tmp_path / "project",
                    style="structured", typed=True)  # fmt: skip
    for decl in ("private String flag;", "private String src;", "private long cnt;", "private long wrap;",
                 "private BigDecimal amt;", "private BigDecimal pamt;", "private String gcopy;"):  # fmt: skip
        assert decl in r.java, decl
    for name in ("name", "g2", "g1", "outn"):
        assert _byte_storage(r.java, name), name


def test_a_move_that_can_leave_negative_zero_keeps_the_item_bytes(tmp_path):
    """NEGZERO's lifts: A (MOVEd -0.05) and E (MOVEd -1000) can hold negative zero, so they stay byte storage;
    B and C (arithmetic: +0) and WIDE (MOVEd C, whose digits all fit) are typed."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "NEGZERO.cbl").write_text(PROGRAMS["NEGZERO"])
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "NEGZERO.cbl", [], "public class NegzeroService {\n}\n", PKG, None,
                    tmp_path / "project", style="structured", typed=True)  # fmt: skip
    for name in ("a", "e"):
        assert _byte_storage(r.java, name), name
    for decl in ("private BigDecimal b;", "private BigDecimal c;", "private BigDecimal wide;"):
        assert decl in r.java, decl


def test_typed_groups_sync_a_groups_bytes_around_its_whole_uses(tmp_path):
    """TGROUPS with groups synced: the items in SRCG and DSTG are typed although both groups are used whole. A
    typed number stays only where its group is never written whole (S-AMT, not D-AMT: bytes MOVEd into DSTG may be
    no number). A simple statement packs once, before itself -- INITIALIZE's own element moves must not be undone by
    a second pack -- and a write is followed by the unpack."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "TGROUPS.cbl").write_text(PROGRAMS["TGROUPS"])
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "TGROUPS.cbl", [], "public class TgroupsService {\n}\n", PKG, None,
                    tmp_path / "project", style="structured", typed=True, groups=True)  # fmt: skip
    for decl in ("private String sName;", "private long sCnt;", "private BigDecimal sAmt;", "private String dName;",
                 "private long dCnt;"):  # fmt: skip
        assert decl in r.java, decl
    assert _byte_storage(r.java, "dAmt")  # a number in a group written whole stays bytes
    init = r.java[r.java.index("// INITIALIZE DSTG") :].split("// MOVE D-CNT", 1)[0]
    lines = [ln.strip() for ln in init.splitlines()]
    assert lines.count("pack_dstg();") == 1 and lines.count("unpack_dstg();") == 1
    assert "pack_dstg()." not in init  # inside the statement: the plain field, no second pack
    unpack_src = r.java[r.java.index("private void unpack_srcg()") :].split("    }", 1)[0]
    assert "sAmt" not in unpack_src  # a read-only group's number is never read back from bytes
