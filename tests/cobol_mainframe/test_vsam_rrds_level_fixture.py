"""#4894: the level fixture for VSAM beyond KSDS, first variant: ORGANIZATION IS RELATIVE (RRDS).

`tests/equivalence/vsam/fixture/RRDLVL.cbl` drives a relative file through sequential and dynamic access: every READ /
WRITE / REWRITE / DELETE / START outcome and every file status IBM tabulates for relative files. `expected.txt` was
written from IBM's documentation (Enterprise COBOL for z/OS Language Reference, register F1's table) BEFORE either
runtime ran it (policy 5: level estates first); each step's comment in the program cites the rule.

* The oracle half (EQUIVALENCE_E2E=1, Docker) runs the program under GnuCOBOL and must print expected.txt line for line.
* The det half pins today's state: the translator refuses the RELATIVE file by name (no runtime model yet), so the
  program is not translated. The slice that lands the runtime model flips this test to run the Java side too.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "equivalence" / "vsam" / "fixture"
IMAGE = "gitgalaxy-gnucobol:3"

E2E = pytest.mark.skipif(
    os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
    reason="needs EQUIVALENCE_E2E=1 and Docker",
)

# the statuses IBM's file status table gives a relative file's statements (register F1), by the step that reaches each
IBM_STATUSES = {"00", "10", "22", "23", "35", "41", "42", "43", "46", "47", "48", "49"}


# steps where GnuCOBOL 3.1.2 (the oracle) differs from IBM: 49 REWRITE of an empty slot, 51 DELETE of an empty slot
KNOWN_ORACLE_DEVIATIONS = ["49", "51"]


def _lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.splitlines() if ln.strip()]


def _steps(lines: list[str]) -> list[tuple[str, str, str]]:
    """(step number, operation, status) of each step line of an output."""
    out = []
    for ln in lines:
        m = re.match(r"(\d\d) (\S+)\s+\[(..)\]$", ln)
        if m:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def test_expected_is_a_numbered_run_of_ibm_statuses_that_covers_the_whole_table():
    lines = _lines((FIXTURE / "expected.txt").read_text(encoding="latin-1"))
    steps = _steps(lines)
    assert [n for n, _, _ in steps] == [f"{i:02d}" for i in range(1, len(steps) + 1)]
    assert lines[-1] == "END RRDLVL"
    assert {st for _, _, st in steps} == IBM_STATUSES
    # a record line follows a step only when its status is 00 and it reads or writes a record
    for i, ln in enumerate(lines[:-1]):
        if ln.startswith("   K="):
            assert re.match(r"\d\d \S+\s+\[00\]$", lines[i - 1]), (i, ln)


def test_every_step_of_the_program_is_in_expected_in_order():
    src = (FIXTURE / "RRDLVL.cbl").read_text(encoding="latin-1")
    ops = re.findall(r"MOVE '(\S+)\s*' TO W-OP", src)
    expected = _steps(_lines((FIXTURE / "expected.txt").read_text(encoding="latin-1")))
    assert ops == [op for _, op, _ in expected]


def test_every_line_of_the_program_is_fixed_format():
    for n, ln in enumerate((FIXTURE / "RRDLVL.cbl").read_text(encoding="latin-1").splitlines(), 1):
        assert len(ln) <= 72, (n, ln)
        assert ln[:6].strip() == "", (n, ln)


def test_the_det_translator_refuses_the_relative_file_by_name_until_the_runtime_models_it(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    import sys

    sys.path.insert(0, str(ROOT / "tests" / "cobol_mainframe"))
    import test_det_programs as tdp

    tdp._batch_package(tmp_path / "src/main/java")
    r = P.translate(FIXTURE / "RRDLVL.cbl", [], "public class RrdlvlService {\n}\n", "p", None, tmp_path)
    assert r.stats["holes"], "the relative file translated: replace this pin with the Java half of the fixture"
    assert any("ORGANIZATION RELATIVE" in str(h) for h in r.stats["holes"]), r.stats["holes"]


@E2E
def test_the_oracle_prints_what_ibm_documents(tmp_path):
    expected = _lines((FIXTURE / "expected.txt").read_text(encoding="latin-1"))
    shutil.copy(FIXTURE / "RRDLVL.cbl", tmp_path / "RRDLVL.cbl")
    script = "cobc -x -std=ibm -fsign=EBCDIC -o prog RRDLVL.cbl && ./prog"
    run = subprocess.run(  # noqa: S603
        ["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", IMAGE, "sh", "-c", script],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    got = _lines(run.stdout)
    assert len(got) == len(expected)
    diffs = {i: (e, g) for i, (e, g) in enumerate(zip(expected, got, strict=True)) if e != g}
    # first run, 2026-11-02: 64 of 66 steps match IBM's text; GnuCOBOL 3.1.2 answers 00 where IBM says 23 for a REWRITE /
    # DELETE of an EMPTY slot inside the file's extent (past the extent it answers 23). Pinned, not loosened: expected.txt
    # stays IBM's text, and the det runtime model must print IBM's 23 (register F1, "Relative files").
    assert sorted(e.split()[0] for e, _ in diffs.values()) == KNOWN_ORACLE_DEVIATIONS
    for e, g in diffs.values():
        assert e.split()[:2] == g.split()[:2]
        assert e.endswith("[23]") and g.endswith("[00]")
