"""The oracle applies no 30-digit cap to arithmetic intermediates (oracle_assumptions C2, #4702).

IBM (Enterprise COBOL 6.4 Programming Guide, Appendix A, "Truncated intermediate results") truncates an intermediate
of more than 30 digits under ARITH(COMPAT). `cobc -std=ibm` does not: the 36-digit product A * B below survives the
division that follows it, so the result is the exact one. A declared oracle-vs-IBM difference, measured here so the
register entry cannot go stale. Needs Docker and the pinned oracle image; it skips without them."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import equivalence_oracle

PROBE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. Q.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A PIC 9(18) VALUE 999999999999999999.
       01 B PIC 9(18) VALUE 999999999999999999.
       01 T PIC 9(2) VALUE 10.
       01 R PIC 9(18).
       01 S PIC 9(2).
       PROCEDURE DIVISION.
           COMPUTE R = A * B / A
           DISPLAY "R1=" R
           COMPUTE S = A * B / (A * B) * 7
           DISPLAY "S1=" S
           COMPUTE R = A * B / A * T / T
           DISPLAY "R2=" R
           COMPUTE R = (A + B) * T / (T * 2)
           DISPLAY "R3=" R
           STOP RUN.
"""

# measured 2026-10-18, GnuCOBOL 3.1.2 -std=ibm: exact results; IBM COMPAT would cut A * B (36 digits) to 30
EXPECTED = ["R1=999999999999999999", "S1=07", "R2=999999999999999999", "R3=999999999999999999"]


@pytest.mark.skipif(not shutil.which("docker") or os.environ.get("EQUIVALENCE_E2E") != "1",
                    reason="needs Docker and the oracle image (EQUIVALENCE_E2E=1)")  # fmt: skip
def test_a_36_digit_intermediate_is_kept_whole_by_the_oracle(tmp_path):
    image = equivalence_oracle.IMAGE
    if subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode:  # noqa: S603, S607
        pytest.skip(f"image {image} not built")
    (tmp_path / "Q.cbl").write_text(PROBE, encoding="utf-8")
    cmd = ["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", image,
           "sh", "-c", "cobc -x -std=ibm -o q Q.cbl && ./q"]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # noqa: S603
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == EXPECTED
