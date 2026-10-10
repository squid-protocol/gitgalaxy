"""det-port intrinsic functions (det/cobolrt/Funcs.java) against GnuCOBOL's own (`cobc -x -std=ibm`, the harness's
oracle): each input in a PIC X(24), the function's result DISPLAYed by COBOL and computed by the runtime."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FUNCS = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/Funcs.java"
IMAGE = "gitgalaxy-gnucobol:3"

# TEST-NUMVAL / TEST-NUMVAL-C: valid forms, each kind of invalid character, incomplete arguments
NUMVAL_CASES = ["123", "  123  ", "-123", "123-", "+12.5", " 12.5 ", "12.5CR", "12.5 DB", "1.2.3", "12A", "", "- 12",
                "12 -", "--1", "1 2", ".5", "5.", "$12.50", "1,234.56", "$ 1,234.56-", "12,34", "CR12", "+", "-",
                "1,2,3.4", ".", "12.5cr", "  -  12.5", "12.5-CR", "A", "0", "00012345678901234567890", "+ 1.5 CR",
                "$-12", "-$12", "12$", "1,", ",1", "12.5 CR X", "DB", "  1  .5"]  # fmt: skip


def _java() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
def test_test_numval_is_gnucobols(tmp_path):
    cob = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. TN.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", "       01 S PIC X(24).", "       PROCEDURE DIVISION."]  # fmt: skip
    for c in NUMVAL_CASES:
        cob += [f"           MOVE '{c}' TO S" if c else "           MOVE SPACES TO S",
                "           DISPLAY FUNCTION TEST-NUMVAL(S) ' ' FUNCTION TEST-NUMVAL-C(S)"]  # fmt: skip
    cob.append("           STOP RUN.")
    (tmp_path / "tn.cbl").write_text("\n".join(cob) + "\n")
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          "cobc -x -std=ibm tn.cbl -o tn 2>/dev/null && ./tn"], capture_output=True, text=True,
                         check=True)  # fmt: skip
    want = run.stdout.splitlines()
    src = tmp_path / "p/cobolrt"
    src.mkdir(parents=True)
    (src / "Funcs.java").write_text(FUNCS.read_text().replace("__PACKAGE__", "p"))
    (tmp_path / "cases.txt").write_text("\n".join(NUMVAL_CASES) + "\n")
    (tmp_path / "TN.java").write_text(
        "import java.nio.file.*;\npublic class TN { public static void main(String[] a) throws Exception {\n"
        '  for (String c : Files.readAllLines(Path.of("cases.txt"))) { String s = String.format("%-24s", c);\n'
        '    System.out.printf("%010d %010d%n", p.cobolrt.Funcs.testNumval(s).intValue(),\n'
        "        p.cobolrt.Funcs.testNumvalC(s).intValue()); } } }\n"
    )
    java = _java()
    subprocess.run([str(java / "javac"), "-d", "out", "p/cobolrt/Funcs.java", "TN.java"], cwd=tmp_path, check=True)
    got = subprocess.run([str(java / "java"), "-cp", "out", "TN"], cwd=tmp_path, capture_output=True, text=True,
                         check=True).stdout.splitlines()  # fmt: skip
    diffs = [(c, w, g) for c, w, g in zip(NUMVAL_CASES, want, got, strict=False) if w != g]  # reason: length may differ
    assert len(want) == len(NUMVAL_CASES) and not diffs, diffs


# glibc's rand() after srand(seed) (GnuCOBOL 3.1.2's FUNCTION RANDOM, libcob intrinsic.c), measured with ctypes on
# glibc 2.36: seed 0 is seed 1, and a run unit's first reference with no seed is seed zero (IBM)
RANDOM_SEQUENCES = {0: [1804289383, 846930886, 1681692777], 1: [1804289383, 846930886, 1681692777],
                    42: [71876166, 708592740, 1483128881], 1234567: [1595124304, 1356573642, 254066959],
                    2147483647: [1065668062, 2142264300, 1066566375]}  # fmt: skip


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_random_is_the_oracles_sequence_and_refuses_what_ibm_does_not_allow(tmp_path):
    """Funcs.Random: RANDOM(seed) then RANDOM with no argument give glibc's rand() / RAND_MAX as the exact value of
    a double (what GnuCOBOL's COMPUTE takes); reset() is an unseeded run unit. Not z/OS's numbers (C12)."""
    src = tmp_path / "p/cobolrt"
    src.mkdir(parents=True)
    (src / "Funcs.java").write_text(FUNCS.read_text().replace("__PACKAGE__", "p"))
    seeds = list(RANDOM_SEQUENCES)
    (tmp_path / "RN.java").write_text(
        "import java.math.BigDecimal;\npublic class RN { public static void main(String[] a) {\n"
        "  p.cobolrt.Funcs.Random r = new p.cobolrt.Funcs.Random();\n"
        "  System.out.println(r.next().toPlainString() + ' ' + r.next().toPlainString());\n"
        f"  for (long s : new long[] {{{', '.join(f'{s}L' for s in seeds)}}}) {{\n"
        "    System.out.println(r.next(BigDecimal.valueOf(s)).toPlainString() + ' ' + r.next().toPlainString() + ' '"
        " + r.next().toPlainString()); }\n"
        '  for (String bad : new String[] {"-1", "2147483648", "1.5"}) {\n'
        '    try { r.next(new BigDecimal(bad)); System.out.println("taken " + bad); }\n'
        '    catch (IllegalArgumentException e) { System.out.println("refused " + bad); } } } }\n'
    )
    java = _java()
    subprocess.run([str(java / "javac"), "-d", "out", "p/cobolrt/Funcs.java", "RN.java"], cwd=tmp_path, check=True)
    got = subprocess.run([str(java / "java"), "-cp", "out", "RN"], cwd=tmp_path, capture_output=True, text=True,
                         check=True).stdout.splitlines()  # fmt: skip

    def exact(n: int) -> str:
        from decimal import Decimal

        return format(Decimal(n / 2147483647), "f")

    want = [" ".join(exact(n) for n in RANDOM_SEQUENCES[0][:2])]
    want += [" ".join(exact(n) for n in RANDOM_SEQUENCES[s]) for s in seeds]
    want += ["refused -1", "refused 2147483648", "refused 1.5"]
    assert got == want
