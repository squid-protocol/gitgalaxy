"""#4894: the level fixture for VSAM beyond KSDS, second variant: an alternate index and its path (ALTERNATE RECORD KEY).

`tests/equivalence/vsam/fixture/AIXLVL.cbl` drives an indexed file with `ALTERNATE RECORD KEY ... WITH DUPLICATES` (and
one without) through READ by path, READ NEXT along a path, START, WRITE, REWRITE and DELETE, with every file status IBM
tabulates for them. `expected_aix.txt` was written from IBM's documentation (Enterprise COBOL for z/OS Language
Reference, register F1's table) BEFORE either runtime ran it (policy 5: level estates first).

* The oracle half (EQUIVALENCE_E2E=1, Docker) runs the program under GnuCOBOL and must print expected_aix.txt, except at
  the pinned steps where GnuCOBOL 3.1.2 differs from IBM.
* The det half pins today's state: no det model of a duplicate-key path is claimed by this fixture. The slice that lands
  one runs the Java side too and drops the deviations from the oracle half.
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

# the statuses IBM's file status table gives an indexed file's statements, by the step that reaches each (register F1)
IBM_STATUSES = {"00", "02", "10", "22", "23", "35", "48"}

# steps where GnuCOBOL 3.1.2 (the oracle) differs from IBM: a READ whose key of reference value is also in the NEXT
# record. IBM gives 02 (LRM, file status key: "the key value for the current key of reference was equal to the value of
# the same key in the next record"); GnuCOBOL answers 00.
KNOWN_ORACLE_DEVIATIONS = ["10", "11", "18", "21"]


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


def _expected() -> list[str]:
    return _lines((FIXTURE / "expected_aix.txt").read_text(encoding="latin-1"))


def test_expected_is_a_numbered_run_of_ibm_statuses_that_covers_the_table():
    lines = _expected()
    steps = _steps(lines)
    assert [n for n, _, _ in steps] == [f"{i:02d}" for i in range(1, len(steps) + 1)]
    assert lines[-1] == "END AIXLVL"
    assert {st for _, _, st in steps} == IBM_STATUSES
    # a record line follows a step only when its status is 00 or 02 and it reads a record
    for i, ln in enumerate(lines[:-1]):
        if ln.startswith("   K="):
            assert re.match(r"\d\d READ-\S+\s+\[0[02]\]$", lines[i - 1]), (i, ln)


def test_duplicate_alternate_key_rows_follow_ibms_order_of_entry():
    lines = _expected()
    status = {n: st for n, _, st in _steps(lines)}
    keys = {
        ln[:2]: lines[i + 1].split()[0]
        for i, ln in enumerate(lines)
        if ln[:2].isdigit() and lines[i + 1].startswith("   K=")
    }
    # RED was written 0001, 0003, 0005: a path walk returns them in that order, 02 until the last one
    assert [keys[n] for n in ("10", "11", "12")] == ["K=0001", "K=0003", "K=0005"]
    assert [status[n] for n in ("10", "11", "12")] == ["02", "02", "00"]


def test_every_step_of_the_program_is_in_expected_in_order():
    src = (FIXTURE / "AIXLVL.cbl").read_text(encoding="latin-1")
    ops = re.findall(r"MOVE '(\S+)\s*' TO W-OP", src)
    assert ops == [op for _, op, _ in _steps(_expected())]


def test_every_line_of_the_program_is_fixed_format():
    for n, ln in enumerate((FIXTURE / "AIXLVL.cbl").read_text(encoding="latin-1").splitlines(), 1):
        assert len(ln) <= 72, (n, ln)
        assert ln[:6].strip() == "", (n, ln)


@E2E
def test_the_oracle_prints_what_ibm_documents(tmp_path):
    expected = _expected()
    shutil.copy(FIXTURE / "AIXLVL.cbl", tmp_path / "AIXLVL.cbl")
    script = "cobc -x -std=ibm -fsign=EBCDIC -o prog AIXLVL.cbl && ./prog"
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
    # first run, 2026-11-21: 40 steps, 36 match IBM's text; GnuCOBOL 3.1.2 answers 00 where IBM says 02 for a READ whose
    # alternate key repeats in the next record. Pinned, not loosened: expected_aix.txt stays IBM's text.
    assert sorted(e.split()[0] for e, _ in diffs.values()) == KNOWN_ORACLE_DEVIATIONS
    for e, g in diffs.values():
        assert e.split()[:2] == g.split()[:2]
        assert e.endswith("[02]") and g.endswith("[00]")
