"""#5867 slice 2: the oracle stand-in that computes DBB EPSMPMT's `**` and ANNUITY COMPUTEs in IEEE binary64 (register C6).

`equivalence_binary64.lower` swaps the two ruled statements for CALLs of `faults/ggb64.c`; it must be faithful or
refuse. The stub's rate is the port's short HFP rate (det/hfp.py) and its payment is the one-double-operation
formula the port evaluates, so both are held to the port's own model here.
"""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import equivalence_binary64 as b64  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import hfp as H  # noqa: E402

STUB = ROOT / "tests" / "equivalence" / "faults" / b64.STUB

SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EPSMPMT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  W.
           03 WS-NUMBER-OF-MONTHS    PIC 9(9)V99   COMP.
           03 WS-CALC-INTEREST       COMP-1.
           03 LOAN        PIC 9(9)V99.
           03 PAYMENT     PIC 9(9)V99.
           03 INTEREST    PIC 9(9)V9999.
           03 NUMBER-PERIODS PIC 999.
       PROCEDURE DIVISION.
           COMPUTE WS-CALC-INTEREST =
                              (EPSPDATA-QUOTED-INTEREST-RATE / 100) / 12
           .
       A200-CALULATE-MONTH-PAYMENT.
           COMPUTE EPSPDATA-RETURN-MONTH-PAYMENT
                   = EPSPDATA-PRINCIPLE-DATA *
                     (WS-CALC-INTEREST *
                     (1 + WS-CALC-INTEREST) ** WS-NUMBER-OF-MONTHS) /
                     (((1 + WS-CALC-INTEREST )
                                            ** WS-NUMBER-OF-MONTHS) - 1)
           .
           COMPUTE PAYMENT = LOAN * FUNCTION ANNUITY((INTEREST / 12)
                                              NUMBER-PERIODS)
           DISPLAY 'Verify Payment = ' Payment.
"""


def test_both_statements_become_calls_and_the_line_count_holds():
    out = b64.lower(SOURCE)
    assert out.count("\n") == SOURCE.count("\n")
    assert "CALL 'GGB64PAY' USING EPSPDATA-PRINCIPLE-DATA" in out
    assert "CALL 'GGB64ANN' USING LOAN INTEREST" in out
    assert "**" not in out and "ANNUITY" not in out
    assert all(len(ln) <= 72 for ln in out.split("\n"))
    # the period that ended the payment statement still ends it; the ANNUITY one had none, DISPLAY ends it
    assert re.search(r"EPSPDATA-RETURN-MONTH-PAYMENT\.\n", out)
    assert "NUMBER-PERIODS PAYMENT\n" in out


def test_other_programs_are_unchanged():
    other = SOURCE.replace("EPSMPMT", "OTHER")
    assert b64.lower(other) == other


@pytest.mark.parametrize(
    "edit",
    [
        ("(((1 + WS-CALC-INTEREST )", "(((2 + WS-CALC-INTEREST )"),
        ("(EPSPDATA-QUOTED-INTEREST-RATE / 100) / 12", "(EPSPDATA-QUOTED-INTEREST-RATE / 100) / 13"),
        ("FUNCTION ANNUITY((INTEREST / 12)", "FUNCTION ANNUITY((INTEREST / 11)"),
        ("WS-CALC-INTEREST       COMP-1", "WS-CALC-INTEREST       COMP-2"),
        ("PIC 9(9)V99   COMP.", "PIC 9(7)V99   COMP."),
    ],
)
def test_a_shape_the_stub_does_not_implement_is_refused(edit):
    with pytest.raises(b64.Unsupported):
        b64.lower(SOURCE.replace(*edit))


def test_a_ruled_program_without_the_ruled_statements_is_refused():
    with pytest.raises(b64.Unsupported):
        b64.lower(SOURCE.split("PROCEDURE DIVISION.")[0] + "PROCEDURE DIVISION.\n           GOBACK.\n")


@pytest.fixture(scope="module")
def stub(tmp_path_factory):
    if os.name == "nt":  # the stub is a posix oracle part; a mingw .so has no runtime DLLs to load (#6821)
        pytest.skip("posix oracle stub")
    cc = shutil.which("gcc") or shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    so = tmp_path_factory.mktemp("ggb64") / "ggb64.so"
    subprocess.run([cc, "-O2", "-shared", "-fPIC", "-DGGB64_TEST", str(STUB), "-o", str(so), "-lm"], check=True)
    lib = ctypes.CDLL(str(so))
    lib.ggb64_rate.restype = ctypes.c_double
    lib.ggb64_rate.argtypes = [ctypes.c_int64]
    return lib


def test_the_rate_is_the_ports_short_hfp_for_every_quoted_rate(stub):
    for q in range(-99999, 100000, 7):  # S9(2)V9(3): every 7th, and the edges below
        want = H.to_short(H.div(H.div(H.of(F(q, 1000)), H.of(100), True), H.of(12), True))
        assert stub.ggb64_rate(q) == float(want), q
    for q in (0, 1, 5250, 6000, 99999, -1, -99999):
        want = H.to_short(H.div(H.div(H.of(F(q, 1000)), H.of(100), True), H.of(12), True))
        assert stub.ggb64_rate(q) == float(want), q


def _pay(stub, principal_cents, quoted, months_hundredths):
    buf = (ctypes.c_ubyte * 4)()
    args = (
        (ctypes.c_ubyte * 8)(*principal_cents.to_bytes(8, "big", signed=True)),
        (ctypes.c_ubyte * 4)(*quoted.to_bytes(4, "big", signed=True)),
        (ctypes.c_ubyte * 8)(*months_hundredths.to_bytes(8, "big")),
        buf,
    )
    assert stub.GGB64PAY(*args) == 0
    return int.from_bytes(bytes(buf), "big", signed=True)


def test_the_payment_is_the_binary64_formula_truncated(stub):
    import math

    for principal, quoted, months in (
        (20000000, 5250, 36000),
        (10000000001, 6000, 36000),
        (20000000, 99999, 36000),
        (100, 4500, 1200),
        (15000000, 3875, 18000),
    ):
        c = float(H.to_short(H.div(H.div(H.of(F(quoted, 1000)), H.of(100), True), H.of(12), True)))
        n = months / 100
        pw = math.pow(1 + c, n)
        want = int(principal / 100 * (c * pw) / (pw - 1) * 100 + 1e-9)
        # glibc and fdlibm may differ in the last bit of pow: a cent can move only at a truncation boundary
        assert abs(_pay(stub, principal, quoted, months) - want) <= 1, (principal, quoted, months)


def test_the_annuity_of_a_zero_rate_is_one_over_n(stub):
    loan = (ctypes.c_ubyte * 11)(*b"00000010000")
    interest = (ctypes.c_ubyte * 13)(*b"0000000000000")
    periods = (ctypes.c_ubyte * 3)(*b"004")
    pay = (ctypes.c_ubyte * 11)()
    assert stub.GGB64ANN(loan, interest, periods, pay) == 0
    assert bytes(pay) == b"00000002500"  # 100.00 / 4


def test_the_stub_fails_loudly_where_binary64_has_no_fixed_point_value(stub, tmp_path):
    cc = shutil.which("gcc") or shutil.which("cc")
    driver = tmp_path / "d.c"
    driver.write_text(
        "int GGB64PAY(unsigned char*,unsigned char*,unsigned char*,unsigned char*);\n"
        "int main(void){unsigned char p[8]={0,0,0,0,0,0,0,100},q[4]={0,0,0,0},m[8]={0,0,0,0,0,0,0,0},o[4];"
        "return GGB64PAY(p,q,m,o);}\n"
    )
    exe = tmp_path / "d"
    subprocess.run([cc, str(driver), str(STUB), "-o", str(exe), "-lm"], check=True)
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    assert run.returncode == 1
    assert "GGB64" in run.stdout + run.stderr
