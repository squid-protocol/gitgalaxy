"""#8062 slice 2 (register L8): the GnuCOBOL frame source for the LE condition model, ggframes.c + ceecond.c.

Run on the oracle image (GnuCOBOL 3.1.2, docker): real COBOL programs register and signal through the model. Pinned:
one identity per ACTIVATION (a second CALL of the program a first returned from does not inherit its handlers, though
libcob hands both the same cob_module address), a handler of a caller's frame runs for a callee's CEESGL, a handler is
entered with cob_call_params 4 (the signalling CALL itself carried 3), and a recursive activation is refused by name
(exit 98). What z/OS does is not observed; the model is ASSUMED (IBM-documented), as L8 says."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tests/equivalence/le_conditions"
IMAGE = "gitgalaxy-gnucobol:3"


def _docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False).returncode == 0  # noqa: S603, S607


pytestmark = pytest.mark.skipif(not _docker_ready(), reason="needs docker and the oracle image")

_HEAD = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {name}{rec}.\n"

# REGP: mode 1 registers HAND for its own activation; mode 2 signals a severity-3 user condition with an fc.
REGP = """       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 HP USAGE PROCEDURE-POINTER.
       01 TOK PIC S9(9) COMP-5 VALUE 7.
       01 FC PIC X(12).
       01 COND PIC X(12).
       LINKAGE SECTION.
       01 MODE-IN PIC S9(9) COMP-5.
       PROCEDURE DIVISION USING MODE-IN.
           IF MODE-IN = 1 OR MODE-IN = 3
              SET HP TO ENTRY "HAND"
              CALL "CEEHDLR" USING HP TOK FC
              DISPLAY "registered"
           END-IF
           IF MODE-IN = 2 OR MODE-IN = 3
              MOVE LOW-VALUES TO COND
              MOVE X"03" TO COND(2:1)
              MOVE X"1B" TO COND(5:1)
              MOVE "USR" TO COND(6:3)
              CALL "CEESGL" USING COND OMITTED FC
              DISPLAY "fc msg=" FUNCTION ORD(FC(3:1))
                 "," FUNCTION ORD(FC(4:1))
           END-IF
           GOBACK.
"""
HAND = """       DATA DIVISION.
       LINKAGE SECTION.
       01 A PIC X(12).
       01 B PIC X(4).
       01 C PIC S9(9) COMP-5.
       01 D PIC X(12).
       PROCEDURE DIVISION USING A B C D.
           DISPLAY "handler params=" NUMBER-OF-CALL-PARAMETERS
           MOVE 10 TO C
           GOBACK.
"""
REC = """       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 HP USAGE PROCEDURE-POINTER.
       01 FC PIC X(12).
       01 N PIC S9(4) COMP-5 VALUE 0.
       PROCEDURE DIVISION.
           IF N = 0
              ADD 1 TO N
              CALL "RECP"
           ELSE
              SET HP TO ENTRY "HAND"
              CALL "CEEHDLR" USING HP OMITTED FC
              DISPLAY "not reached"
           END-IF
           GOBACK.
"""


BUILDS = [
    ("seq", "m_seq.cbl", "regp.cbl hand.cbl ceecond.c ggframes.c"),
    ("one", "m_one.cbl", "regp.cbl hand.cbl ceecond.c ggframes.c"),
    ("rec", "m_rec.cbl", "recp.cbl hand.cbl ceecond.c ggframes.c"),
]


def _main(name: str, modes: list[int]) -> str:
    calls = "".join(f'           MOVE {m} TO M\n           CALL "REGP" USING M\n' for m in modes)
    return (
        _HEAD.format(name=name, rec="")
        + "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01 M PIC S9(9) COMP-5.\n"
        + "       PROCEDURE DIVISION.\n"
        + calls
        + "           STOP RUN.\n"
    )


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    work = tmp_path_factory.mktemp("le_frames")
    for c in ("ceecond.c", "ggframes.c"):
        shutil.copy(SRC / c, work / c)
    files = {
        "regp.cbl": _HEAD.format(name="REGP", rec="") + REGP,
        "hand.cbl": _HEAD.format(name="HAND", rec="") + HAND,
        "recp.cbl": _HEAD.format(name="RECP", rec=" IS RECURSIVE") + REC,
        "m_seq.cbl": _main("MSEQ", [1, 2]),  # two activations of REGP: the second inherits nothing
        "m_one.cbl": _main("MONE", [3]),  # one activation registers and signals: the handler runs
        "m_rec.cbl": _HEAD.format(name="MREC", rec="")
        + '       PROCEDURE DIVISION.\n           CALL "RECP"\n           STOP RUN.\n',
    }
    for n, t in files.items():
        (work / n).write_text(t, encoding="utf-8")
    script = "".join(
        f"cobc -x -o {p} {m} {rest} -ldl 2>&1 | grep -v Wunfinished >> build.log\n" for p, m, rest in BUILDS
    )
    script += "for p in seq one rec; do ./$p > $p.out 2> $p.err; echo $? > $p.rc; done\n"
    (work / "run.sh").write_text(script, encoding="utf-8")
    r = subprocess.run(  # noqa: S603
        [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{work}:/work",
            "-w",
            "/work",
            IMAGE,
            "sh",
            "/work/run.sh",
        ],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert r.returncode == 0, r.stderr + (work / "build.log").read_text()
    return {
        p: ((work / f"{p}.out").read_text(), (work / f"{p}.err").read_text(), int((work / f"{p}.rc").read_text()))
        for p in ("seq", "one", "rec")
    }


def test_a_second_activation_of_the_same_program_inherits_no_handler(runs):
    """libcob gives both CALLs of REGP one cob_module address; the first registered HAND and returned, so the second's
    CEESGL finds no handler: the handler does not run and the fc is CEE069 (severity 0, message 201 = 0x00C9)."""
    out, err, rc = runs["seq"]
    assert rc == 0, err
    assert "handler params" not in out
    assert out.split("\n")[:-1] == ["registered", "fc msg=000000001,000000202"]  # ORD is one-based: 0x00, 0xC9


def test_a_handler_runs_in_the_activation_that_registered_it_with_four_parameters(runs):
    """The CEESGL CALL carried 3 arguments; the handler is entered with cob_call_params set to 4."""
    out, err, rc = runs["one"]
    assert rc == 0, err
    assert out.split("\n")[:-1] == ["registered", "handler params=+000000004", "fc msg=000000001,000000001"]  # CEE000


def test_a_recursive_activation_is_refused_by_name(runs):
    out, err, rc = runs["rec"]
    assert rc == 98
    assert "a recursive activation is not modelled" in err
    assert "not reached" not in out
