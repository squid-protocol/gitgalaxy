"""#4706: INTDATE(LILIAN) in the det port (oracle_assumptions.md C5).

IBM is the reference. INTDATE(LILIAN) moves day 1 of FUNCTION INTEGER-OF-DATE / DATE-OF-INTEGER from 1 January 1601
(ANSI, the default) to 15 October 1582, so a date is 6653 higher (Enterprise COBOL for z/OS 6.x Language Reference,
"INTEGER-OF-DATE"; Programming Guide, "INTDATE"). GnuCOBOL has no INTDATE, so the oracle still refuses the option by
name and a LILIAN program is not compared with cobc: the det port is checked here against IBM's documented day
numbers. The translator reads the option through the one resolver (CBL / PROCESS cards over the PARM over the default)
and picks `Funcs.*Lilian` at translation.

The runtime tests need a JDK 17 (JAVA_HOME / JDK_17)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# the epochs, a century year that is a leap year (1600) and one that is not (1700), a modern leap day, today, and the
# 1601 boundary where the two counts differ by exactly 6653
DATES = [15821015, 16000229, 16010101, 17000228, 20000229, 20261018]


def _expected():
    import datetime

    out = []
    for ymd in DATES:
        d = datetime.date(ymd // 10000, ymd // 100 % 100, ymd % 100)
        ansi = (d - datetime.date(1600, 12, 31)).days
        lilian = (d - datetime.date(1582, 10, 14)).days
        out.append((ymd, ansi, lilian))
    return out


def test_the_documented_anchors():
    rows = {ymd: (a, lil) for ymd, a, lil in _expected()}
    assert rows[15821015][1] == 1  # day 1 of LILIAN is 15 October 1582
    assert rows[16010101] == (1, 6654)  # day 1 of ANSI
    assert all(lil - a == 6653 for ymd, (a, lil) in rows.items() if ymd >= 16010101)


def _service(java: str) -> str:
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    return P.with_intdate_lilian(java)


def test_the_translator_swaps_both_functions_and_only_them():
    java = "a = Funcs.integerOfDate(x); b = Funcs.dateOfInteger(y); c = Funcs.integerPart(z);\n"
    out = _service(java)
    assert out == "a = Funcs.integerOfDateLilian(x); b = Funcs.dateOfIntegerLilian(y); c = Funcs.integerPart(z);\n"
    assert _service(out) == out  # idempotent: a swapped call is not swapped again


@pytest.mark.parametrize(
    ("options", "card", "lilian"),
    [
        ([], "", False),  # IBM's default
        (["INTDATE(LILIAN)"], "", True),  # the compile step's PARM
        ([], "       CBL INTDATE(LILIAN)", True),  # the program's own card
        (["INTDATE(LILIAN)"], "       CBL INTDATE(ANSI)", False),  # the card wins over the PARM
        ([], "       PROCESS INTDATE(LILIAN),TRUNC(BIN)", True),
    ],
)
def test_the_option_comes_through_the_one_resolver(options, card, lilian, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "p.cbl"
    src.write_text((card + "\n" if card else "") + "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n")
    assert P.intdate_lilian(src, options) is lilian


def _jdk_or_skip():
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    return T


def _program(name: str, dates: list[int], card: str) -> str:
    proc = []
    for ymd in dates:
        proc += [
            f"COMPUTE N = FUNCTION INTEGER-OF-DATE({ymd})",
            f"DISPLAY 'I {ymd} ' N",
            "COMPUTE D = FUNCTION DATE-OF-INTEGER(N)",
            f"DISPLAY 'D {ymd} ' D",
        ]
    src = [*([card] if card else []), "       IDENTIFICATION DIVISION.", f"       PROGRAM-ID. {name}.",
           "       DATA DIVISION.", "       WORKING-STORAGE SECTION.", "       01 N PIC 9(8).", "       01 D PIC 9(8).",
           "       PROCEDURE DIVISION.", *(f"           {x}" for x in proc), "           GOBACK."]  # fmt: skip
    assert all(len(x) <= 72 for x in src)
    return "\n".join(src) + "\n"


@pytest.mark.parametrize("typed", [False, True])
def test_the_port_counts_from_the_option_in_effect(typed, tmp_path):
    T = _jdk_or_skip()
    rows = _expected()
    dates = DATES
    for sub, card, col in (("lil", "       CBL INTDATE(LILIAN)", 2), ("ans", "", 1)):
        (tmp_path / sub).mkdir()
        out = T._java_run("intd", _program("INTD", dates, card), tmp_path / sub, typed)
        for row in rows:
            ymd, day = row[0], row[col]
            if day < 1:  # before day 1 of the count: IBM defines no integer for it (ANSI: before 1601)
                continue
            assert f"I {ymd} {day:08d}" in out, (sub, ymd, out)
            assert f"D {ymd} {ymd:08d}" in out, (sub, ymd, out)  # DATE-OF-INTEGER inverts it under the same option
