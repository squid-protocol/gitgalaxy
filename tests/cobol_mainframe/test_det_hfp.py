"""#4271 slice 1: COMP-1 / COMP-2 as IBM hexadecimal floating point (HFP) in the det translator and runtime.

GnuCOBOL, the oracle, stores IEEE floats and evaluates a float expression in decimal (register C6), so it cannot decide
HFP bytes, HFP rounding, or IBM's DISPLAY of a float. The proof is in three parts:

1. **The byte layout and the arithmetic, by hand-computed vectors** (this file): IBM's own examples of the format
   (z/Architecture Principles of Operation, SA22-7832, "Hexadecimal-Floating-Point Number Representation"; the same
   values in Wikipedia's "IBM hexadecimal floating-point"), the guard digit ("1 - 16**-8 = 1" in short arithmetic),
   and the conversions IBM documents (Enterprise COBOL 6.4 Programming Guide, SC27-8714-03, "Conversions and
   precision"; Language Reference, DISPLAY statement).
2. **The runtime against the translator's model** (this file, needs a JDK): `cobolrt/Hfp.java` and `det/hfp.py` are
   two implementations of the same rules (BigInteger / exact Fractions); every conversion, operation, rounding and
   DISPLAY of a vector table must agree bit for bit.
3. **Behaviour against the oracle where it can decide** (test_det_programs.py FLOAT, bytes / typed / groups modes):
   values every format holds exactly, where IEEE-in-decimal and HFP must give the same numbers.

What the oracle cannot decide is refused by name (each a Hole), tested at the end of this file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import hfp as H  # noqa: E402


def _short(v) -> str:
    return H.encode(H.for_item(F(v), True), True).hex().upper()


def _long(v) -> str:
    return H.encode(H.for_item(F(v), False), False).hex().upper()


# ---- 1. hand-computed vectors -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, want",
    [
        ("1", "41100000"),  # +0.1 x 16**1 (Principles of Operation's examples of the format)
        ("0.5", "40800000"),  # +0.8 x 16**0
        ("0.015625", "3F400000"),  # 1/64 = +0.4 x 16**-1
        ("0", "00000000"),  # true zero
        ("-15", "C1F00000"),  # -0.F x 16**1
        ("-118.625", "C276A000"),  # -0.76A x 16**2 (Wikipedia, "IBM hexadecimal floating-point")
        ("0.1", "4019999A"),  # 0.1999999.. x 16**0, rounded to 6 digits: 21 significant bits
    ],
)
def test_short_layout_is_ibms(value, want):
    assert _short(value) == want


def test_the_range_ends_are_ibms():
    largest = (1 - F(16) ** -6) * F(16) ** 63  # ~ 7.2370051E+75
    smallest = F(16) ** -65  # ~ 5.397605E-79
    assert H.encode(largest, True).hex().upper() == "7FFFFFFF"
    assert H.encode(smallest, True).hex().upper() == "00100000"
    with pytest.raises(H.HfpRange):
        H.of(F(16) ** 63)  # exponent overflow: refused by name
    with pytest.raises(H.HfpRange):
        H.of(F(16) ** -66)  # underflow


def test_long_layout_and_the_fixed_point_conversion():
    assert _long("1") == "4110000000000000"
    assert _long("-118.625") == "C276A00000000000"
    # fixed point to long: truncated (ASSUMED, register C6) -- the conversion IBM generates is not documented
    assert _long("0.1") == "4019999999999999"
    assert H.decode(bytes.fromhex("4019999999999999")) < F(1, 10)


def test_arithmetic_truncates_with_one_guard_digit():
    one = F(1)
    # short: 16**-8 shifted past the guard digit is lost ("1 - 16**-8 = 1")
    assert H.sub(one, F(16) ** -8, long=False) == 1
    # 16**-6 sits in the guard digit: 1 - 16**-6 = 0.FFFFFF exactly
    assert H.sub(one, F(16) ** -6, long=False) == 1 - F(16) ** -6
    # 16**-7 is the digit after the guard digit: lost too
    assert H.sub(one, F(16) ** -7, long=False) == 1
    # a sum's carry shifts right, truncating: 0.FFFFFF + 0.000001 x 16**0 = 0.1 x 16**1
    assert H.add(1 - F(16) ** -6, F(16) ** -6, long=False) == 1
    # MULTIPLY / DIVIDE: the exact result truncated
    third = H.div(one, F(3), long=True)
    assert H.encode(third, False).hex().upper() == "4055555555555555"
    assert H.mul(third, F(3), long=True) == 1 - F(16) ** -14  # 0.FFFFFFFFFFFFFF
    assert H.encode(H.div(one, F(3), long=False), True).hex().upper() == "40555555"


def test_long_to_short_rounds_half_away():
    # LOAD ROUNDED: a one at the first discarded bit. 2/3 long = 0.AAAAAAAAAAAAAA -> 0.AAAAAB
    assert H.encode(H.to_short(H.div(F(2), F(3), long=True)), True).hex().upper() == "40AAAAAB"
    assert H.encode(H.to_short(-H.div(F(2), F(3), long=True)), True).hex().upper() == "C0AAAAAB"
    # 0.FFFFFF8 rounds up past the fraction: 0.1 x 16**1
    assert H.to_short(1 - F(16) ** -7 * 8) == 1


@pytest.mark.parametrize(
    "value, short, scale, want",
    [
        ("0.1", False, 4, "0.1000"),  # rounded in the low-order position (GnuCOBOL truncates: 0.0999)
        ("2", None, 2, "0.67"),  # 2/3 COMP-1 to V99: rounded
        # HFP short holds -1.005 as -0.10147B x 16**1 = -1.00500011..: -1.01 (IEEE single holds -1.00499999..)
        ("-1.005", True, 2, "-1.01"),
        ("123456789.123", True, 6, "123456784.000000"),  # COMP-1: 9 significant digits, the rest zero
        ("123456789.123", False, 6, "123456789.123000"),  # COMP-2: up to 18
    ],
)
def test_float_to_fixed_rounds_as_ibm_documents(value, short, scale, want):
    if short is None:  # 2/3 computed in long, stored in a COMP-1
        v = H.to_short(H.div(F(2), F(3), long=True))
        assert str(H.to_fixed(v, scale, 9)) == want
        return
    v = H.for_item(F(Decimal(value)), short)
    assert str(H.to_fixed(v, scale, 9 if short else 18)) == want


@pytest.mark.parametrize(
    "value, long, want",
    [
        ("12.5", False, " .12500000E 02"),
        ("-0.375", False, "-.37500000E 00"),
        ("0.05", False, " .50000001E-01"),  # COMP-1 0.05 = 0.0500000007..: 8 digits, rounded
        ("0", False, " .00000000E 00"),
        ("0", True, " .00000000000000000E 00"),
        ("-3", True, "-.30000000000000000E 01"),
        ("123456789.123", True, " .12345678912300000E 09"),
    ],
)
def test_display_is_ibms_external_floating_point(value, long, want):
    v = H.for_item(F(Decimal(value)), not long)
    assert H.display(v, long) == want
    assert len(want) == (23 if long else 14)  # sign . 8|17 digits E sign 2 digits


# ---- 2. the runtime against the model ---------------------------------------------------------------------------

VALUES = ["0", "1", "-1", "0.1", "-0.1", "2.5", "1024", "-118.625", "3.14159265358979", "0.000123", "99999.99",
          "-7.0625", "16777215", "16777217", "0.3333333333", "123456789.123", "1E-20", "6.02E+23"]  # fmt: skip
PAIRS = [("1", "3"), ("2", "3"), ("0.1", "0.2"), ("1024", "-0.000123"), ("-118.625", "3.14159265358979"),
         ("16777217", "1"), ("99999.99", "0.3333333333"), ("1E-20", "6.02E+23"), ("1", "-1"), ("0.1", "-0.1")]  # fmt: skip


def _plain(v: F) -> str:
    d = H._EXACT.normalize(H._dec(v))
    return "0" if d == 0 else format(d, "f")


def _model_lines() -> list[str]:
    out = []
    for v in VALUES:
        x = F(Decimal(v))
        s, lg = H.for_item(x, True), H.for_item(x, False)
        out.append(f"{v} {H.encode(s, True).hex()} {H.encode(lg, False).hex()} {H.display(s, False)}|"
                   f"{H.display(lg, True)} {H.to_fixed(s, 4, 9)} {H.to_fixed(lg, 4, 18)}")  # fmt: skip
    for a, b in PAIRS:
        for long in (False, True):
            x, y = H.for_item(F(Decimal(a)), not long), H.for_item(F(Decimal(b)), not long)
            r = [H.add(x, y, long), H.sub(x, y, long), H.mul(x, y, long), H.div(x, y, long)]
            out.append(f"{a} {b} {long} " + " ".join(_plain(z) for z in r))
    return out


PROBE = """
import p.cobolrt.*;
import java.math.BigDecimal;
import java.nio.charset.*;
public class Probe {
    static final Charset CS = StandardCharsets.ISO_8859_1;
    static Field item(String v, boolean lng) {
        Field f = Field.hfp(new Storage(8), 0, lng);
        Cobol.move(new BigDecimal(v), f, CS);
        return f;
    }
    static String hex(Field f) {
        StringBuilder b = new StringBuilder();
        for (byte x : f.raw()) b.append(String.format("%02x", x & 0xFF));
        return b.toString();
    }
    static String fixed(Field f) {
        Field z = Field.zoned(new Storage(41), 0, 40, 4, true, false, true);
        Cobol.move(f, z, CS);
        return Cobol.num(z, CS).toPlainString();
    }
    static String plain(BigDecimal v) {
        return v.signum() == 0 ? "0" : v.stripTrailingZeros().toPlainString();
    }
    public static void main(String[] a) {
        String[] values = {%VALUES%};
        for (String v : values) {
            Field s = item(v, false), l = item(v, true);
            System.out.println(v + " " + hex(s) + " " + hex(l) + " " + Cobol.displayText(s, CS) + "|"
                + Cobol.displayText(l, CS) + " " + fixed(s) + " " + fixed(l));
        }
        String[][] pairs = {%PAIRS%};
        for (String[] p : pairs) {
            for (boolean lng : new boolean[] {false, true}) {
                BigDecimal x = Cobol.num(item(p[0], lng), CS), y = Cobol.num(item(p[1], lng), CS);
                System.out.println(p[0] + " " + p[1] + " " + (lng ? "True" : "False") + " "
                    + plain(Hfp.add(x, y, lng)) + " " + plain(Hfp.subtract(x, y, lng)) + " "
                    + plain(Hfp.multiply(x, y, lng)) + " " + plain(Hfp.divide(x, y, lng)));
            }
        }
    }
}
"""


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_is_the_model_bit_for_bit(tmp_path):
    rt = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
    out = tmp_path / "src/p/cobolrt"
    out.mkdir(parents=True)
    for f in rt.glob("*.java"):
        (out / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    probe = PROBE.replace("%VALUES%", ", ".join(f'"{v}"' for v in VALUES))
    probe = probe.replace("%PAIRS%", ", ".join(f'{{"{a}", "{b}"}}' for a, b in PAIRS))
    (tmp_path / "src/Probe.java").write_text(probe)
    jdk = _jdk()
    files = [str(f) for f in (tmp_path / "src").rglob("*.java")]
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(tmp_path / "classes"), *files], check=True)  # noqa: S603
    got = subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "Probe"], capture_output=True,  # noqa: S603
                         text=True, check=True).stdout.splitlines()  # fmt: skip
    want = _model_lines()
    assert len(got) == len(want)
    bad = [f"java  {g}\nmodel {w}" for g, w in zip(got, want) if g != w]
    assert not bad, "\n".join(bad)


# ---- 3. what the oracle cannot decide: refused by name --------------------------------------------------------

FLOAT_DATA = """       01 S1 COMP-1 VALUE 1.5.
       01 L1 COMP-2.
       01 GRP.
          05 G-X PIC X(2).
          05 G-F COMP-2.
       01 GRX REDEFINES GRP PIC X(10).
       01 X4 PIC X(4).
       01 N  PIC 9(3)V99.
"""


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("MOVE GRP TO GRX", "its bytes hold G-F COMP-2"),  # a group holding a float, as bytes
        ("MOVE GRX TO X4", "its bytes hold G-F COMP-2"),  # a REDEFINES over one
        ("MOVE S1 TO X4", "MOVE S1 COMP-1 to a alphanumeric item"),
        ("MOVE X4 TO S1", "MOVE of a nonnumeric operand to S1 COMP-1"),
        ("MOVE S1(1:2) TO X4", "the bytes of a COMP-1 item"),
        ("COMPUTE L1 = S1 ** 2", "exponentiation in a floating-point expression"),
        ("COMPUTE L1 = FUNCTION SQRT(N)", "FUNCTION SQRT in a floating-point expression"),
        ("COMPUTE S1 ROUNDED = N / 3", "ROUNDED into S1"),
        ("IF S1 = 'AB' DISPLAY 'Y' END-IF", "compared with a nonnumeric operand"),
        ("IF S1 = SPACES DISPLAY 'Y' END-IF", "compared with a nonnumeric operand"),
        ("STRING S1 DELIMITED BY SIZE INTO X4 END-STRING", "the bytes of a COMP-1 item"),
        ("DIVIDE 3 INTO L1 GIVING N REMAINDER L1", "REMAINDER in floating point"),
    ],
)
def test_what_the_oracle_cannot_decide_is_a_named_hole(stmt, why, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")  # the translator's parser
    from gitgalaxy.tools.cobol_to_java.det import program as P

    cbl = tmp_path / "FLT.cbl"
    cbl.write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FLT.\n       DATA DIVISION.\n"
                   "       WORKING-STORAGE SECTION.\n" + FLOAT_DATA + "       PROCEDURE DIVISION.\n"
                   f"           {stmt}\n           GOBACK.\n", encoding="ascii")  # fmt: skip
    (tmp_path / "project").mkdir()
    r = P.translate(cbl, [], "public class FltService {\n}\n", "p", None, tmp_path / "project")
    assert len(r.stats["holes"]) == 1 and why in r.stats["holes"][0], r.stats["holes"]
    assert "oracle_assumptions.md C6" in r.stats["holes"][0] or "C6" in r.java


def test_ibm_dbb_epsmpmt_translates_but_its_float_exponentiation(tmp_path):
    """mortgage-mpmt's program: WS-CALC-INTEREST (COMP-1) is now computed in long HFP, and the payment's
    `(1 + C) ** N` with N's decimal places is the one hole (KNOWN_UNPROVEN's reason, proof_sweep.py)."""
    pytest.importorskip("tree_sitter_language_pack")
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    src = corpora / "dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epsmpmt.cbl"
    if not src.is_file():
        pytest.skip("needs the IBM DBB MortgageApplication corpus (GITGALAXY_MAINFRAME_CORPORA)")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "project").mkdir()
    r = P.translate(src, [src.parent.parent / "copybook"], "public class EpsmpmtService {\n}\n", "p", None,
                    tmp_path / "project")  # fmt: skip
    holes = r.stats["holes"]  # (and A300-TRY2's FUNCTION ANNUITY, dead code, as before)
    assert [h for h in holes if "C6" in h] == [h for h in holes if "line 125:" in h], holes
    assert any("line 125: COMPUTE exponentiation in a floating-point expression" in h for h in holes), holes
    assert "Hfp.divide(Hfp.divide(Hfp.of(" in r.java  # (rate / 100) / 12 into the COMP-1: long HFP


# ---- FUNCTION NUMVAL in a floating-point expression (#4270: CBSA BNK1CAC, BNK1TFN, BNK1CRA, BNK1UAC) --------------

NUMVAL_PROBE = """
import p.cobolrt.*;
import java.math.BigDecimal;
public class Probe {
    static String run(String s, boolean c) {
        try {
            BigDecimal v = Hfp.numval(s, c);
            return v.stripTrailingZeros().toPlainString() + " " + Hfp.toShort(v).stripTrailingZeros().toPlainString();
        } catch (UnsupportedOperationException e) {
            return "REFUSED " + e.getMessage();
        }
    }
    public static void main(String[] a) {
        String[][] cases = {%CASES%};
        for (String[] k : cases) System.out.println(run(k[0], k[1].equals("C")));
    }
}
"""


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_numval_is_a_long_hfp_operand_and_refuses_what_ibm_does_not_describe(tmp_path):
    """IBM: NUMVAL returns a long floating-point value under ARITH(COMPAT) (6.4 Programming Guide, "Converting to
    numbers"); the conversion is the model's fixed-point one (truncated to long, ASSUMED) and a COMP-1 receiver rounds
    it to short. More than 18 digits (invalid under ARITH(COMPAT)) or 15 significant digits (IBM: precision may be
    lost "in an unexpected manner") are refused by name."""
    cases = [("  12.5 ", ""), ("0.1", ""), ("-0.375", ""), ("3.25 CR", ""), ("$1,024.50", "C"), ("0.00", ""),
             ("123456789012345", ""), ("1234567890123456", ""), ("0000000000000000001", ""),
             ("12345678901234.50", ""), ("0012.50", "")]  # fmt: skip
    rt = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
    out = tmp_path / "src/p/cobolrt"
    out.mkdir(parents=True)
    for f in rt.glob("*.java"):
        (out / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    probe = NUMVAL_PROBE.replace("%CASES%", ", ".join(f'{{"{s}", "{c}"}}' for s, c in cases))
    (tmp_path / "src/Probe.java").write_text(probe)
    jdk = _jdk()
    files = [str(f) for f in (tmp_path / "src").rglob("*.java")]
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(tmp_path / "classes"), *files], check=True)  # noqa: S603
    got = subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "Probe"], capture_output=True,  # noqa: S603
                         text=True, check=True).stdout.splitlines()  # fmt: skip

    def model(v: str) -> str:
        x = H.of(F(Decimal(v)))
        return f"{_plain(x)} {_plain(H.to_short(x))}"

    assert got[0] == model("12.5") == "12.5 12.5"
    assert got[1] == model("0.1")  # long: truncated to 14 hex digits; short: rounded (4019999A)
    assert H.encode(H.to_short(H.of(F(Decimal("0.1")))), True).hex().upper() == "4019999A"
    assert H.encode(H.of(F(Decimal("0.1"))), False).hex().upper() == "4019999999999999"
    assert got[2] == model("-0.375")
    assert got[3] == model("-3.25")
    assert got[4] == model("1024.5")
    assert got[5] == "0 0"
    assert got[6] == model("123456789012345")  # 15 significant digits: IBM converts them accurately
    assert got[7].startswith("REFUSED") and "more than 15 significant digits" in got[7], got[7]
    assert got[8].startswith("REFUSED") and "19 digits" in got[8], got[8]
    assert got[9].startswith("REFUSED") and "more than 15 significant digits" in got[9], got[9]  # a written 0
    assert got[10] == model("12.5")  # leading zeros are not significant


def test_arith_extend_refuses_a_floating_point_expression(tmp_path):
    """Under ARITH(EXTEND) (a PROCESS card, resolved as TRUNC and NUMPROC are) NUMVAL returns extended-precision
    (128-bit) HFP and float expressions may be extended: not modelled, refused by name (register C5, C6)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    body = ("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FLT.\n       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n" + FLOAT_DATA + "       PROCEDURE DIVISION.\n"
            "           COMPUTE S1 = FUNCTION NUMVAL(X4)\n           GOBACK.\n")  # fmt: skip
    (tmp_path / "project").mkdir()
    for card, holes in (("", []), ("       PROCESS ARITH(EXTEND)\n", ["ARITH(EXTEND): a floating-point expression"])):
        cbl = tmp_path / "FLT.cbl"
        cbl.write_text(card + body, encoding="ascii")
        r = P.translate(cbl, [], "public class FltService {\n}\n", "p", None, tmp_path / "project")
        assert [h for h in r.stats["holes"] if not any(w in h for w in holes)] == [], r.stats["holes"]
        assert len(r.stats["holes"]) == len(holes), r.stats["holes"]
