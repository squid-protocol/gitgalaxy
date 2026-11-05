"""#7646 (registers C6 / C7): a group MOVE over COMP-1 / COMP-2 / COMP-5 items, and the byte views that stay refused.

A group MOVE is a byte copy. Where the two groups lay their numbers alike (same offsets, same usage, same size, no
table) each number arrives with its own bytes -- HFP for a float, big-endian COMP-5 under `zos_comp5` in the port;
IEEE and little-endian in the oracle -- and no byte is read as anything else, so what both print afterwards agrees.
Any other use of those bytes (an alphanumeric REDEFINES, a group moved to a differently laid group or an X item, a
reference modification) is a named hole: IBM's bytes are not the oracle's, and the oracle cannot say what IBM's are.
Synthetic programs only. `EQUIVALENCE_E2E=1` (Docker) also checks the expected lines are what cobc prints.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_det_nondigit_binary import IMAGE, _det, _java  # noqa: E402

pytestmark = pytest.mark.slow(
    reason="the first java test of a CI split part pays the one-time javac of the cobolrt runtime: 12-17 s on a runner (#5668)"
)

HEAD = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION."]  # fmt: skip
SHOW = ["01 E PIC -9(14).9(4)."]  # every number is shown through a numeric-edited item, which both sides print alike

# name: (data, procedure, the lines both sides print)
PROGRAMS = {
    "float": (
        [
            "01 G1.",
            "   05 T1 PIC X(2).",
            "   05 F1 COMP-2.",
            "   05 S1 COMP-1.",
            "   05 N1 PIC S9(4) COMP-5.",
            "01 G2.",
            "   05 T2 PIC X(2).",
            "   05 F2 COMP-2.",
            "   05 S2 COMP-1.",
            "   05 N2 PIC S9(4) COMP-5.",
            "01 G3 REDEFINES G2.",
            "   05 T3 PIC X(2).",
            "   05 F3 COMP-2.",
            "   05 S3 COMP-1.",
            "   05 N3 PIC S9(4) COMP-5.",
        ],
        [
            "MOVE 'AB' TO T1",
            "COMPUTE F1 = 1.5",
            "COMPUTE S1 = 0.25",
            "MOVE -258 TO N1",
            "MOVE G1 TO G2",
            "MOVE F2 TO E",
            "DISPLAY 'F ' E",
            "MOVE S2 TO E",
            "DISPLAY 'S ' E",
            "MOVE N2 TO E",
            "DISPLAY 'N ' E",
            "DISPLAY 'T ' T2",
            "COMPUTE F1 = F1 + 1",
            "MOVE G2 TO G1",
            "MOVE F1 TO E",
            "DISPLAY 'back ' E",
            "MOVE F3 TO E",
            "DISPLAY 'F3 ' E",
        ],
        [
            "F  00000000000001.5000",
            "S  00000000000000.2500",
            "N -00000000000258.0000",
            "T AB",
            "back  00000000000001.5000",
            "F3  00000000000001.5000",
        ],
    ),
    "comp5": (
        [
            "01 H1.",
            "   05 A1 PIC S9(4) COMP-5.",
            "   05 B1 PIC S9(9) COMP-5.",
            "   05 C1 PIC 9(18) COMP-5.",
            "01 H2.",
            "   05 A2 PIC S9(4) COMP-5.",
            "   05 B2 PIC S9(9) COMP-5.",
            "   05 C2 PIC 9(18) COMP-5.",
        ],
        [
            "MOVE -2 TO A1",
            "MOVE 70000 TO B1",
            "MOVE 1234567890123 TO C1",
            "MOVE H1 TO H2",
            "MOVE A2 TO E",
            "DISPLAY 'A ' E",
            "MOVE B2 TO E",
            "DISPLAY 'B ' E",
            "MOVE C2 TO E",
            "DISPLAY 'C ' E",
        ],
        ["A -00000000000002.0000", "B  00000000070000.0000", "C  01234567890123.0000"],
    ),
}
# each: (data, statement, the hole's text)
REFUSED = {
    "float redefined as X": (
        ["01 F COMP-2.", "01 FX REDEFINES F PIC X(8)."],
        "MOVE FX TO T",
        "its bytes hold F COMP-2",
    ),
    "float group to X": (["01 G.", "   05 F COMP-2."], "MOVE G TO T", "its bytes hold F COMP-2"),
    "X to float group": (["01 G.", "   05 F COMP-2."], "MOVE T TO G", "its bytes hold F COMP-2"),
    "float group redefined as X": (
        ["01 G.", "   05 F COMP-1.", "01 GX REDEFINES G PIC X(4)."],
        "MOVE GX TO T",
        "its bytes hold F COMP-1",
    ),
    "float group to a group laid out differently": (
        ["01 G.", "   05 F COMP-2.", "   05 Q PIC X.", "01 H.", "   05 Q PIC X.", "   05 F COMP-2."],
        "MOVE G TO H",
        "its bytes hold F COMP-2",
    ),  # same size, the float at another offset
    "float group to a group of another size": (
        ["01 G.", "   05 F COMP-2.", "01 H.", "   05 F COMP-2.", "   05 Q PIC X."],
        "MOVE G TO H",
        "its bytes hold F COMP-2",
    ),
    "float group reference-modified": (
        ["01 G.", "   05 F COMP-2.", "01 H.", "   05 F COMP-2."],
        "MOVE G(1:4) TO H",
        "its bytes hold F COMP-2",
    ),
    "float group to a group of a COMP-1 for a COMP-2": (
        ["01 G.", "   05 F COMP-2.", "01 H.", "   05 F COMP-1.", "   05 Q PIC X(4)."],
        "MOVE G TO H",
        "its bytes hold F COMP-1",
    ),  # the hole names the receiver's float
    "float group to a table": (
        ["01 G.", "   05 F COMP-2.", "01 H.", "   05 F COMP-2 OCCURS 2."],
        "MOVE G TO H",
        "its bytes hold F COMP-2",
    ),
}


def _source(data: list[str], proc: list[str]) -> str:
    body = [f"       {x}" for x in [*data, *SHOW, "01 T PIC X(8)."]]
    return "\n".join([*HEAD, *body, "       PROCEDURE DIVISION.", *[f"           {x}" for x in proc],
                      "           GOBACK.", ""])  # fmt: skip


def _port(name: str, tmp_path, monkeypatch, zos_comp5: bool = True):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    monkeypatch.setattr(P, "translate", functools.partial(P.translate, zos_comp5=zos_comp5))
    data, proc, _ = PROGRAMS[name]
    return _det(_source(data, proc), tmp_path, "STD")


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("name", list(PROGRAMS))
def test_a_group_move_over_numbers_prints_what_the_oracle_prints(name, tmp_path, monkeypatch):
    pytest.importorskip("tree_sitter_language_pack")
    run = _port(name, tmp_path, monkeypatch)
    assert run.returncode == 0, run.stderr
    assert run.stdout.split("\n")[:-1] == PROGRAMS[name][2]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker (EQUIVALENCE_E2E=1)")  # fmt: skip
@pytest.mark.parametrize("name", list(PROGRAMS))
def test_the_expected_lines_are_cobcs(name, tmp_path):
    data, proc, want = PROGRAMS[name]
    (tmp_path / "ndb.cbl").write_text(_source(data, proc))
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          "cobc -x -std=ibm -fsign=EBCDIC -fbinary-truncate ndb.cbl -o ndb 2>&1 && ./ndb"],
                         capture_output=True, check=False)  # fmt: skip
    text = run.stdout.decode("latin-1")
    assert run.returncode == 0, text
    assert text.split("\n")[:-1] == want


@pytest.mark.parametrize("zos_comp5", [False, True])
@pytest.mark.parametrize("case", list(REFUSED))
def test_every_other_byte_use_stays_a_named_hole(case, zos_comp5, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    data, stmt, why = REFUSED[case]
    (tmp_path / "NDB.cbl").write_text(_source(data, [stmt]))
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "NDB.cbl", [], "public class NdbService {\n}\n", "p", None, tmp_path / "project",
                    zos_comp5=zos_comp5)  # fmt: skip
    assert len(r.stats["holes"]) == 1 and why in r.stats["holes"][0], r.stats["holes"]
    assert "oracle_assumptions.md C6" in r.stats["holes"][0]


def test_the_copy_is_translated_by_default_for_floats_and_under_the_switch_for_comp5(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    for name, switch, holes in [("float", False, 0), ("comp5", False, 0), ("comp5", True, 0)]:
        data, proc, _ = PROGRAMS[name]
        work = tmp_path / f"{name}{switch}"
        (work / "project").mkdir(parents=True)
        (work / "NDB.cbl").write_text(_source(data, proc))
        r = P.translate(work / "NDB.cbl", [], "public class NdbService {\n}\n", "p", None, work / "project",
                        zos_comp5=switch)  # fmt: skip
        got = [h for h in r.stats["holes"] if "MOVE G1 TO G2" in h or "MOVE H1 TO H2" in h]
        assert len(got) == holes, r.stats["holes"]
