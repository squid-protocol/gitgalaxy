"""det-port statements end to end: small COBOL programs, each run by GnuCOBOL (`cobc -x -std=ibm -fsign=EBCDIC`, the
harness's oracle) and translated (gitgalaxy/tools/cobol_to_java/det) and run as Java -- their DISPLAY output equal.

Each program DISPLAYs alphanumeric and unsigned DISPLAY items only, whose external form is their bytes on both sides.
The port runs on its own (runProgram) with the standalone runtime; nothing of a generated project is needed."""

from __future__ import annotations

import os
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


def _java_run(name: str, src: str, work: Path) -> str:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / f"{name}.cbl").write_text(src)
    project = work / "project"  # no generated project: the standalone runtime
    project.mkdir()
    r = P.translate(work / f"{name}.cbl", [], f"public class {name.title()}Service {{\n}}\n", PKG, None, project)
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
@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_program_output_is_gnucobols(name, tmp_path):
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = _cobol(PROGRAMS[name], cob)
    got = _java_run(name, PROGRAMS[name], tmp_path)
    assert got == want, f"java {got!r} != cobol {want!r}"
