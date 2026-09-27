"""#3933: the generated CobolEdit.format floats a `$` / currency symbol / `+` / `-` insertion string, and
substitutes the PICTURE SYMBOL with the whole currency string. Compiled and run with the JDK, as the Cultural
Gauntlet's --run layer does (its `jdk()`)."""

import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import cobol_edit_source

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from cultural_gauntlet import jdk  # noqa: E402

# (PICTURE, value, currency, COBOL's edited result). The single-character rows are GnuCOBOL 3 (-std=ibm)
# output, MOVE of an S9(9)V99 to the edited item; every row but the first is a case #3933's table lacked.
GNUCOBOL = [
    ("$$$,$$9.99", "1234.50", None, " $1,234.50"),
    ("$$$,$$9.99", "34.50", None, "    $34.50"),
    ("$$$,$$9.99", "234.50", None, "   $234.50"),  # the symbol takes the blanked comma's position
    ("$$$,$$9.99", "0", None, "     $0.00"),
    ("$$$,$$9.99", "-1234.5", None, " $1,234.50"),  # no sign position: unsigned
    ("$$$,$$$.$$", "0", None, "          "),  # every digit position floats: zero is all spaces
    ("$$$,$$$.$$", "0.05", None, "      $.05"),  # the decimal point stops the float
    ("$$$,$$$.$$", "12.34", None, "    $12.34"),
    ("$$$,$$$.99", "0", None, "      $.00"),
    ("$$$9.99-", "-12.3", None, " $12.30-"),
    ("+++,++9.99", "-1234.5", None, " -1,234.50"),
    ("+++,++9.99", "1234.5", None, " +1,234.50"),
    ("---,--9.99", "-34.5", None, "    -34.50"),
    ("---,--9.99", "34.5", None, "     34.50"),
    ("$$$$$", "123", None, " $123"),
    ("$$$$$", "0", None, "     "),
    ("$$$$$", "9999", None, "$9999"),
    ("$$B$$9", "1234", None, "$1 234"),
    ("$$B$$9", "12", None, "   $12"),
    ("---.--", "-0.05", None, "  -.05"),
    ("+ZZ9.99", "5", None, "+  5.00"),  # a single + or $ stays a fixed insertion
    ("$ZZ9.99", "5", None, "$  5.00"),
    ("$(3),$$9.99", "1234.5", None, " $1,234.50"),
    ("$$,$$$,$$9.99", "1234567.89", None, "$1,234,567.89"),
    ("--,--,--9.99", "-123456.78", None, "-1,23,456.78"),
    ("£££,££9.99", "1234.50", "£", " £1,234.50"),  # CURRENCY SIGN IS '£': the rule for one character
    ("₹₹₹,₹₹9.99", "1234.50", "₹", " ₹1,234.50"),
    ("£££,££9.99", "1234.50", None, " £1,234.50"),  # no currency passed: the PICTURE's own character
]
# Multi-character strings (CURRENCY SIGN IS 'INR ' WITH PICTURE SYMBOL 'I'): GnuCOBOL has none, so these are
# IBM Enterprise COBOL's rule -- the string floats as a unit into the one symbol position just left of the
# first significant digit; every other position of the PICTURE is one character (the field is wider by
# len(string) - 1, the 13 bytes the record layout gives `UUU,UU9.99` with 'EUR ').
IBM_MULTI = [
    ("UUU,UU9.99", "1234.50", "EUR ", " EUR 1,234.50"),
    ("III,II9.99", "1234.50", "INR ", " INR 1,234.50"),
    ("III,II9.99", "34.5", "INR ", "    INR 34.50"),
    ("KK,KK,KK9.99", "1234.50", "Rs", "   Rs1,234.50"),
    ("KK,KK,KK9.99", "123456.78", "Rs", "Rs1,23,456.78"),
    ("KKK,KK,KK9.99", "1234567.89", "Rs", "Rs12,34,567.89"),  # the lakh / crore grouping, 7 integer digits
    ("K(3),KK,KK9.99", "1234567.89", "Rs", "Rs12,34,567.89"),
    ("U9.99", "5", "EUR ", "EUR 5.00"),  # a single symbol is a fixed insertion of the whole string
]


def _java(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


@pytest.mark.skipif(jdk() is None, reason="no JDK (javac + java)")
def test_cobol_edit_floats_the_insertion_string_as_cobol(tmp_path):
    javac, java = jdk()  # type: ignore[misc]
    (tmp_path / "CobolEdit.java").write_text(cobol_edit_source("com.test"), encoding="utf-8")
    checks = "\n".join(
        f"        check({_java(pic)}, CobolEdit.format({_java(pic)}, new BigDecimal({_java(v)}), false, "
        f"{_java(cur) if cur is not None else 'null'}), {_java(want)});"
        for pic, v, cur, want in GNUCOBOL + IBM_MULTI
    )
    (tmp_path / "Runner.java").write_text(
        "package com.test.entity.vsam;\nimport java.math.BigDecimal;\npublic class Runner {\n"
        "    static int bad = 0;\n"
        "    static void check(String pic, String got, String want) {\n"
        '        if (!want.equals(got)) { bad++; System.out.println(pic + " got [" + got + "] want [" + want + "]"); }\n'
        "    }\n    public static void main(String[] a) {\n" + checks + "\n        System.exit(bad);\n    }\n}\n",
        encoding="utf-8",
    )
    subprocess.run([javac, "-encoding", "UTF-8", "-d", str(tmp_path), *map(str, tmp_path.glob("*.java"))],
                   check=True)  # fmt: skip
    run = subprocess.run([java, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path),
                          "com.test.entity.vsam.Runner"], capture_output=True, text=True, encoding="utf-8")  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.skipif(jdk() is None, reason="no JDK (javac + java)")
def test_decimal_comma_floats_across_the_period(tmp_path):
    """#3827 + #3933: under DECIMAL-POINT IS COMMA the `.` is the insertion character the float blanks."""
    javac, java = jdk()  # type: ignore[misc]
    (tmp_path / "CobolEdit.java").write_text(cobol_edit_source("com.test"), encoding="utf-8")
    (tmp_path / "Runner.java").write_text(
        "package com.test.entity.vsam;\nimport java.math.BigDecimal;\npublic class Runner {\n"
        "    public static void main(String[] a) {\n"
        '        System.out.println("[" + CobolEdit.format("$$$.$$9,99", new BigDecimal("1234.5"), true, "$") + "]");\n'
        '        System.out.println("[" + CobolEdit.format("$$$.$$9,99", new BigDecimal("34.5"), true, "$") + "]");\n'
        "    }\n}\n",
        encoding="utf-8",
    )
    subprocess.run([javac, "-encoding", "UTF-8", "-d", str(tmp_path), *map(str, tmp_path.glob("*.java"))],
                   check=True)  # fmt: skip
    run = subprocess.run([java, "-cp", str(tmp_path), "com.test.entity.vsam.Runner"], capture_output=True,
                         text=True, check=True)  # fmt: skip
    assert run.stdout.splitlines() == ["[ $1.234,50]", "[    $34,50]"]
