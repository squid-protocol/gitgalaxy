"""#4652 (oracle_assumptions.md C11): a zoned item holding non-digits -- spaces, a letter -- MOVEd to a binary item.

GenApp LGTESTP4's add leaves CA-BROKERID PIC 9(10) / CA-PAYMENT PIC 9(6) as spaces and LGAPDB01 MOVEs them to
S9(9) COMP host variables: the oracle (GnuCOBOL 3.1.2, `-std=ibm -fbinary-truncate`, cob_move_display_to_binary)
counts each byte as its character minus '0' (a space -16) in an unsigned 64-bit integer, keeps the receiver's digits
under TRUNC(STD), and INSERTs 931773840 / 707773840; the det runtime read the spaces as 0. IBM documents no result
for non-digit data in a numeric DISPLAY item, so the det runtime models the oracle (Cobol.nonDigitToBinary).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "gitgalaxy-gnucobol:3"
PKG = "p"

DATA = ["01 G1.", "   05 A10 PIC 9(10).", "   05 A6 PIC 9(6).", "   05 S4 PIC S9(4).", "   05 V2 PIC 9(4)V99.",
        "01 X4 PIC X(4).", "01 S5 REDEFINES X4 PIC S9(4).", "01 X5 PIC X(5).",
        "01 S6 REDEFINES X5 PIC S9(4) SIGN LEADING SEPARATE.", "01 X3 PIC X(3).", "01 A3 REDEFINES X3 PIC 9(3).",
        "01 B9 PIC S9(9) COMP.", "01 B4 PIC S9(4) COMP.", "01 BU9 PIC 9(9) COMP.", "01 B18 PIC S9(18) COMP.",
        "01 B5 PIC S9(9) COMP-5.", "01 B2V PIC S9(7)V99 COMP.", "01 BV0 PIC S9(7) COMP.",
        "01 E PIC -9(20).", "01 EV PIC -9(18).99."]  # fmt: skip
# (sender, receiver, label): each result shown through a numeric-edited item, which both sides DISPLAY alike (C8)
MOVES = [("A10", "B9", "A10>B9"), ("A6", "B9", "A6>B9"), ("A10", "B4", "A10>B4"), ("A10", "BU9", "A10>BU9"),
         ("A10", "B18", "A10>B18"), ("A10", "B5", "A10>B5"), ("A6", "B2V", "A6>B2V"), ("S4", "B9", "S4>B9"),
         ("V2", "BV0", "V2>BV0")]  # fmt: skip
SETS = [("X3", "1A3", "A3", ["B9"]), ("X4", "12 J", "S5", ["B9"]), ("X4", "1 3}", "S5", ["B9", "BU9"]),
        ("X4", "1 3 ", "S5", ["B9"]), ("X5", "-1 3 ", "S6", ["B9"]), ("X5", " 1 3 ", "S6", ["B9"]),
        ("X4", "1 34", "S5", ["B9"])]  # fmt: skip


def _proc() -> list[str]:
    out = ["MOVE SPACES TO G1"]
    for s, r, label in MOVES:
        e = "EV" if r == "B2V" else "E"
        out += [f"MOVE {s} TO {r}", f"MOVE {r} TO {e}", f"DISPLAY '{label} ' {e}"]
    out.append("DISPLAY 'G1 [' G1 ']'")  # the oracle rewrote S4's space sign as '{'
    for x, text, s, rs in SETS:
        out.append(f"MOVE '{text}' TO {x}")
        for r in rs:
            out += [f"MOVE {s} TO {r}", f"MOVE {r} TO E", f"DISPLAY '{text}>{r} ' E ' [' {x} ']'"]
    return out


PROC = _proc()

# GnuCOBOL 3.1.2 (gitgalaxy-gnucobol:3, -std=ibm -fsign=EBCDIC), measured 2026-10-07
WANT = {
    "STD": [
        "A10>B9  00000000000931773840",
        "A6>B9  00000000000707773840",
        "A10>B4  00000000000000003840",
        "A10>BU9  00000000000931773840",
        "A10>B18  00446744055931773840",
        "A10>B5 -00000000000597908592",
        "A6>B2V  000000000005317740.16",
        "S4>B9  00000000000709533840",
        "V2>BV0  00000000000009533840",
        "G1 [                   {      ]",
        "1A3>B9  00000000000000000273 [1A3]",
        "12 J>B9 -00000000000000001041 [12 J]",
        "1 3}>B9 -00000000000709551046 [1 3}]",
        "1 3}>BU9  00000000000709551046 [1 3}]",
        "1 3 >B9  00000000000709551030 [1 3{]",
        "-1 3 >B9 -00000000000709551030 [-1 3 ]",
        " 1 3 >B9  00000000000709551030 [+1 3 ]",
        "1 34>B9  00000000000709551050 [1 3D]",
    ],
    "BIN": [
        "A10>B9 -00000000000597908592",
        "A6>B9 -00000000000001777776",
        "A10>B4 -00000000000000023664",
        "A10>BU9  00000000003697058704",
        "A10>B18 -00000000017777777776",
        "A10>B5 -00000000000597908592",
        "A6>B2V -000000000001777776.00",
        "S4>B9 -00000000000000017776",
        "V2>BV0 -00000000000000017776",
        "G1 [                   {      ]",
        "1A3>B9  00000000000000000273 [1A3]",
        "12 J>B9 -00000000000000001041 [12 J]",
        "1 3}>B9  00000000000000000570 [1 3}]",
        "1 3}>BU9  00000000004294966726 [1 3}]",
        "1 3 >B9 -00000000000000000586 [1 3{]",
        "-1 3 >B9  00000000000000000586 [-1 3 ]",
        " 1 3 >B9 -00000000000000000586 [+1 3 ]",
        "1 34>B9 -00000000000000000566 [1 3D]",
    ],
}
FLAGS = {"STD": "-fbinary-truncate", "BIN": ""}


def _src() -> str:
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION."]  # fmt: skip
    lines += [f"       {x}" for x in DATA]
    lines += ["       PROCEDURE DIVISION."] + [f"           {x}" for x in PROC] + ["           GOBACK."]
    return "\n".join(lines) + "\n"


def _java() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _det(src: str, work: Path, trunc: str) -> subprocess.CompletedProcess:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / "NDB.cbl").write_text(src)
    project = work / "project"
    project.mkdir()
    r = P.translate(work / "NDB.cbl", [], "public class NdbService {\n}\n", PKG, None, project)
    assert not r.stats["holes"], r.stats["holes"]
    srcdir = work / "java"
    java = r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", "")
    runtime = {k: v for k, v in P.runtime_files(PKG, batch=False).items() if not k.startswith("cobolrt/cics/")}
    for rel, text in [(f"service/{r.service}.java", java), *runtime.items()]:
        (srcdir / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (srcdir / PKG / rel).write_text(text)
    rec = srcdir / PKG / "entity/vsam/CobolRecords.java"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset."
                   "Charset charset() {\n        return java.nio.charset.StandardCharsets.ISO_8859_1;\n    }\n}\n")  # fmt: skip
    # runProgram (the standalone entry) runs under the runtime's TRUNC as set: the oracle's flag, stated
    std = "true" if trunc == "STD" else "false"
    (srcdir / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ "
                                      f"{PKG}.cobolrt.Cobol.swapTruncBinary({std}); "
                                      f"new {PKG}.service.{r.service}().runProgram(); }} }}\n")  # fmt: skip
    jdk = _java()
    files = [str(f) for f in srcdir.rglob("*.java")]
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(work / "classes"), *files], check=True)  # noqa: S603
    return subprocess.run([str(jdk / "java"), "-cp", str(work / "classes"), "Main"], capture_output=True, text=True,  # noqa: S603
                          check=False)  # fmt: skip


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("trunc", ["STD", "BIN"])
def test_nondigit_zoned_to_binary_is_the_oracles(trunc, tmp_path):
    """LGAPDB01's MOVE CA-BROKERID (PIC 9(10), spaces) TO DB2-BROKERID-INT (S9(9) COMP): 931773840, not 0."""
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(_src(), tmp_path, trunc)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == WANT[trunc]


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("x, text, item", [("X5", "*1 3 ", "S6")])
def test_a_sign_byte_that_is_no_sign_is_refused_by_name(x, text, item, tmp_path):
    """A SEPARATE sign that is neither + nor - nor a space: IBM documents nothing and the oracle's reading is not
    measured -- refused, never guessed. (A trailing / leading overpunch position holding another byte is modelled
    since #4662: '!' is +1, X'FF' +0, test_det_nondigit_zoned.py.)"""
    pytest.importorskip("tree_sitter_language_pack")
    src = _src().replace(
        "           MOVE SPACES TO G1\n", f"           MOVE '{text}' TO {x}\n           MOVE {item} TO B9\n", 1
    )
    run = _det(src, tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr and "is not modelled" in run.stderr, run.stderr


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("trunc", ["STD", "BIN"])
def test_the_measured_values_are_the_oracles(trunc, tmp_path):
    (tmp_path / "ndb.cbl").write_text(_src())
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          f"cobc -x -std=ibm -fsign=EBCDIC {FLAGS[trunc]} ndb.cbl -o ndb 2>&1 && ./ndb"],
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.splitlines() == WANT[trunc]
