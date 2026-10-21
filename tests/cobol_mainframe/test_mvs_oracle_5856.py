"""#5856 slice 2 (register A2): the oracle's PSA -> TCB -> TIOT, tests/equivalence/le/ggtiot.c + equivalence_mvs.py.

Three checks over the input class (the stated step, the uses of the walk's pointers, what is refused):

1. **The C blocks are the det runtime's, byte for byte**: every step in `STEPS` through ggtiot.c and through
   DetMvs.build, the PSA, TCB and TIOT equal (a pointer compared as the block it addresses), or both refused.
2. **The lowering** (`equivalence_mvs.lower`): CBSTM03A's walk, the ADD / SUBTRACT / COMPUTE forms, every other use of
   the numeric view refused by name (the translator's holes), no step refused, a program that walks no block untouched.
3. **End to end** (needs docker and the oracle image): the lowered program on GnuCOBOL + ggtiot.c prints what the det
   port prints for the same step, and refuses where it refuses.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence_mvs as M  # noqa: E402
import test_tiot_walk_5856 as W  # noqa: E402

GGTIOT_C = ROOT / "tests/equivalence/le/ggtiot.c"
RT = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
REFUSED = "REFUSED"
IMAGE = "gitgalaxy-gnucobol:3"

STEPS = [
    W.CREASTMT,
    "J;S;P;A:UCB",
    "J;S;P;A:NOUCB",
    "J;S;P;A:NOUCB,B:UCB,C:NOUCB,D:UCB",
    "J1;S1;P1;IN:NOUCB",
    "J;S;;",  # no DD: laid, a record past it is the walk's refusal
    "J;S;P;",
    ";;;A:UCB",  # empty names: blanks
    "JOBNAME8;STEPNAME;PROCSTEP;DDNAME08:UCB",
    "J;S;P;A:UCB,",  # a trailing comma ends the list
    "J;S;P;,",
    "J;S;P;" + ",".join(f"D{i}:UCB" for i in range(40)),
    "",  # no step
    "J;S",
    "J;S;P",
    "J;S;P;A:UCB;X",  # a fifth field
    "J;S;P;A:TAPE",
    "J;S;P;A",
    "J;S;P;A:B:UCB",
    "J;S;P;a:ucb",
    "J;S;P;A:UCB,,B:UCB",
    "J;S;P;123456789:UCB",  # a DD name longer than 8
    "TOOLONGNAME;S;P;A:UCB",  # a header name longer than 8
]

C_DRIVER = r"""
#include <stdio.h>
#include <string.h>
const unsigned char *GGMVSBLK(int i, long *len);
int main(void) {
    for (int i = 0; i < 3; i++) {
        long n;
        unsigned char b[4096];
        const unsigned char *src = GGMVSBLK(i, &n);
        memcpy(b, src, (size_t)n);
        long at = i == 0 ? 0x218 : i == 1 ? 0x0C : -1;
        if (at >= 0) { /* the pointer field as the block it addresses (a handle: block in the high word) */
            memset(b + at, 0, 8);
            b[at + 3] = (unsigned char)(i + 1);
        }
        for (long k = 0; k < n; k++) printf("%02X", b[k]);
        printf("\n");
    }
    return 0;
}
"""

JAVA_PROBE = """
package p.cobolrt;
import java.io.*;
import java.nio.charset.StandardCharsets;
public class MvsProbe {
    public static void main(String[] a) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        for (String step; (step = in.readLine()) != null; ) {
            try {
                StringBuilder sb = new StringBuilder();
                for (byte[] b : DetMvs.build(step, StandardCharsets.ISO_8859_1)) {
                    for (byte x : b) sb.append(String.format("%02X", x));
                    sb.append('/');
                }
                System.out.println(sb);
            } catch (UnsupportedOperationException e) {
                System.out.println("REFUSED");
            }
        }
    }
}
"""


def _jdk() -> Path | None:
    return W._java()


@pytest.fixture(scope="module")
def c_driver(tmp_path_factory):
    if not shutil.which("gcc"):
        pytest.skip("needs a C compiler")
    d = tmp_path_factory.mktemp("ggtiot_c")
    (d / "driver.c").write_text(C_DRIVER, newline="\n")
    for flags in (["-fsanitize=address"], []):
        run = subprocess.run(  # noqa: S603
            ["gcc", "-O0", *flags, "-o", str(d / "t"), str(d / "driver.c"), str(GGTIOT_C)],
            capture_output=True,
            text=True,
            check=False,
        )
        if run.returncode == 0:
            break
    assert run.returncode == 0, run.stderr
    return d / "t"


def _run_c(exe: Path, step: str) -> str:
    env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=0", "GGMVS_STEP": step}
    run = subprocess.run([str(exe)], capture_output=True, text=True, check=False, env=env)  # noqa: S603
    if run.returncode == 98:
        assert "GGTIOT: " in run.stderr and run.stderr.rstrip().endswith("is not modelled"), run.stderr
        return REFUSED
    assert run.returncode == 0, run.stderr
    return "/".join(run.stdout.split()) + "/"


def test_no_step_at_all_is_refused_by_name(c_driver):
    env = {k: v for k, v in os.environ.items() if k != "GGMVS_STEP"}
    run = subprocess.run([str(c_driver)], capture_output=True, text=True, check=False, env=env)  # noqa: S603
    assert run.returncode == 98 and "no job step stated" in run.stderr, run.stderr


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_c_blocks_are_the_det_runtime_blocks_byte_for_byte(c_driver, tmp_path):
    out = tmp_path / "src/p/cobolrt"
    (out / "le").mkdir(parents=True)
    for f in RT.glob("*.java"):
        (out / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    for f in (RT / "le").glob("*.java"):
        (out / "le" / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    (out / "MvsProbe.java").write_text(JAVA_PROBE)
    files = [str(f) for f in (tmp_path / "src").rglob("*.java")]
    subprocess.run(  # noqa: S603
        [str(_jdk() / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"), *files], check=True
    )
    got = subprocess.run(  # noqa: S603
        [
            str(_jdk() / "java"),
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-cp",
            str(tmp_path / "classes"),
            "p.cobolrt.MvsProbe",
        ],
        input="\n".join(STEPS) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.splitlines()
    assert len(got) == len(STEPS)
    bad = []
    for step, java in zip(STEPS, got, strict=True):
        c = _run_c(c_driver, step)
        if java != c:
            bad.append(f"{step!r}\n  java {java}\n  c    {c}")
    assert not bad, "\n".join(bad)
    assert sum(g == REFUSED for g in got) >= 10 and sum(g != REFUSED for g in got) >= 10


# ---- the lowering


def _code_lines(text: str) -> list[str]:
    return [x for x in text.split("\n") if x[6:7] != "*"]


def test_cbstm03a_walk_is_lowered_to_the_blocks_calls():
    out = M.lower(W._src(), W.CREASTMT)
    assert "BUMP-TIOT" not in "\n".join(_code_lines(out))
    assert all(len(x) <= 72 for x in out.split("\n")), [x for x in out.split("\n") if len(x) > 72]
    assert out.count('CALL "GGPSAPTR" USING PSAPTR') == 1
    assert out.count('CALL "GGMVSCHK"') == 5  # every SET ADDRESS OF a pointer
    assert out.count('CALL "GGTIOTADV" USING TIOT-INDEX BY VALUE LENGTH OF') == 2
    assert "01  TIOT-INDEX POINTER." in out
    # the original's SET ADDRESS OF statements are all still there, in order
    assert [x.strip() for x in out.replace("\n", " ").split("SET ADDRESS OF")][1:].__len__() == 5


def test_add_subtract_and_signed_forms_become_advance_and_retreat_calls():
    proc = W.PROC.replace(
        "COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-BLOCK.",
        "ADD 30 TO BUMP-TIOT.\n           SUBTRACT 6 FROM BUMP-TIOT.\n"
        "           SUBTRACT LENGTH OF TIOT-SEG FROM BUMP-TIOT.",
    ).replace("COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-SEG", "COMPUTE BUMP-TIOT = BUMP-TIOT - -20")
    out = M.lower(W._src(W.DATA, proc), "J;S;;A:UCB")
    flat = " ".join(out.split())
    assert 'CALL "GGTIOTADV" USING TIOT-INDEX BY VALUE 30' in flat
    assert 'CALL "GGTIOTSUB" USING TIOT-INDEX BY VALUE 6' in flat
    assert 'CALL "GGTIOTSUB" USING TIOT-INDEX BY VALUE LENGTH OF TIOT-SEG' in flat
    assert 'CALL "GGTIOTSUB" USING TIOT-INDEX BY VALUE -20' in flat  # view - -20


@pytest.mark.parametrize(
    "statement",
    [
        "COMPUTE BUMP-TIOT = BUMP-TIOT * 2.",
        "COMPUTE BUMP-TIOT = 20 + BUMP-TIOT.",
        "COMPUTE BUMP-TIOT ROUNDED = BUMP-TIOT + 20.",
        "COMPUTE BUMP-TIOT = BUMP-TIOT + 20 + 4.",
        "COMPUTE BUMP-TIOT = BUMP-TIOT + 20 ON SIZE ERROR DISPLAY 'X' END-COMPUTE.",
        "ADD 20 TO BUMP-TIOT ON SIZE ERROR DISPLAY 'X'.",
        "ADD 20 TO BUMP-TIOT GIVING OTHER-NUM.",
        "MOVE BUMP-TIOT TO OTHER-NUM.",
        "MOVE 4 TO BUMP-TIOT.",
        "IF BUMP-TIOT = 0 DISPLAY 'X' END-IF.",
        "DISPLAY BUMP-TIOT.",
    ],
)
def test_every_other_use_of_the_numeric_view_is_refused_by_name(statement):
    data = W.DATA.replace(
        "       LINKAGE SECTION.\n", "       01  OTHER-NUM PIC S9(08) BINARY.\n       LINKAGE SECTION.\n"
    )
    with pytest.raises(M.Unsupported):
        M.lower(W._src(data, f"           {statement}\n" + W.PROC), W.CREASTMT)


def test_a_second_redefines_of_the_numeric_item_is_refused():
    data = W.DATA.replace(
        "       LINKAGE SECTION.\n",
        "       01  BUMP-BYTES              REDEFINES BUMP-TIOT PIC X(04).\n       LINKAGE SECTION.\n",
    )
    with pytest.raises(M.Unsupported):
        M.lower(W._src(data), W.CREASTMT)


@pytest.mark.parametrize("step", [None, "bad'step", "bad\nstep"])
def test_no_step_or_an_unquotable_one_is_refused(step):
    with pytest.raises(M.Unsupported):
        M.lower(W._src(), step)


def test_a_program_that_walks_no_block_is_left_as_it_is():
    plain = _plain_program("           SET P TO ADDRESS OF REC.\n           CALL 'X' USING P.\n")
    assert M.lower(plain, None) == plain
    assert M.lower(plain, "J;S;;A:UCB") == plain
    # a pointer something else writes is not the PSA's: its SET ADDRESS OF is another lane's, not lowered
    written = _plain_program("           CALL 'X' USING P.\n           SET ADDRESS OF REC TO P.\n")
    assert M.lower(written, "J;S;;A:UCB") == written


def _plain_program(proc: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. PLAIN.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  P   POINTER.\n       LINKAGE SECTION.\n"
        "       01  REC PIC X(4).\n       PROCEDURE DIVISION.\n" + proc + "           GOBACK.\n"
    )


# ---- end to end on the oracle


def _docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False).returncode == 0  # noqa: S603, S607


E2E = [
    (W.CREASTMT, W.PROC),
    ("J1;S1;P1;IN:NOUCB", W.PROC),
    (
        "J;S;;A:UCB,B:NOUCB",
        W.PROC.replace(
            "COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-BLOCK.",
            "ADD 30 TO BUMP-TIOT.\n           SUBTRACT 6 FROM BUMP-TIOT.",
        ).replace("COMPUTE BUMP-TIOT = BUMP-TIOT + LENGTH OF TIOT-SEG", "COMPUTE BUMP-TIOT = BUMP-TIOT - -20"),
    ),
]
E2E_REFUSED = [
    ("J;S;;", W.PROC),  # TIOT-ENTRY past the TIOT's end
    ("J;S;;A:UCB", W.PROC.replace("+ LENGTH OF TIOT-BLOCK.", "- 100.")),  # leaves the block
    (
        "J;S;;A:UCB",
        W.PROC.replace("SET ADDRESS OF TIOT-BLOCK  TO TIOT-POINT.", "SET ADDRESS OF PSA-BLOCK TO TIOT-POINT."),
    ),
]


@pytest.mark.skipif(_jdk() is None or not _docker_ready(), reason="needs a JDK 17 and the oracle image (docker)")
def test_the_lowered_walk_prints_what_the_det_port_prints_on_gnucobol(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    shutil.copy(GGTIOT_C, work / "ggtiot.c")
    script = ["set -e", "cd /work"]
    cases = [(s, p, False) for s, p in E2E] + [(s, p, True) for s, p in E2E_REFUSED]
    for i, (step, proc, _) in enumerate(cases):
        (work / f"P{i}.cbl").write_text(M.lower(W._src(W.DATA, proc).replace("TIOTW", f"P{i}"), step))
        script.append(f"cobc -x -std=ibm -fsign=EBCDIC -o p{i} P{i}.cbl ggtiot.c")
        script.append(f"set +e; GGMVS_STEP='{step}' ./p{i} > out{i}.txt 2> err{i}.txt; echo $? > rc{i}; set -e")
    (work / "run.sh").write_text("\n".join(script) + "\n")
    run = subprocess.run(  # noqa: S603
        ["docker", "run", "--rm", "-v", f"{work}:/work", IMAGE, "sh", "/work/run.sh"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    for i, (step, proc, refused) in enumerate(cases):
        java = W._run(step, W._src(W.DATA, proc))
        rc = int((work / f"rc{i}").read_text())
        if refused:
            assert java.returncode != 0 and rc == 98, (step, java.stderr, rc)
            assert "is not modelled" in (work / f"err{i}.txt").read_text()
        else:
            assert java.returncode == 0 and rc == 0, (step, java.stderr, rc)
            assert (work / f"out{i}.txt").read_text().splitlines() == java.stdout.splitlines(), step
