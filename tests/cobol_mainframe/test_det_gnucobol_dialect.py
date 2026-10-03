"""The det translator's front end on GnuCOBOL-dialect source (docs/language_status/cobolcraft.md): COPY ...
REPLACING's general operand form, level-78 constants, GnuCOBOL's fixed-width native binaries, COMP-5 VALUE byte
order, named refusals instead of silent zero-size items, long literals past column 72, and the free-format
normalizer (tests/tools/free_format.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests" / "tools"), str(ROOT)]

import free_format as ff  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import layout as L  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import source as S  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.source import Line  # noqa: E402


def _program(*data: str) -> list[Line]:
    text = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", *data,
            "PROCEDURE DIVISION.", "GOBACK."]  # fmt: skip
    return [Line(t, "t", n) for n, t in enumerate(text, 1)]


def _records(*data: str) -> list[L.Item]:
    recs = L.parse(S.constants(_program(*data)))
    for r in recs:
        L.layout(r)
    return recs


# ---- COPY ... REPLACING -----------------------------------------------------------------------------------------
def test_replacing_mixes_pseudo_text_words_and_literals_in_order():
    stmt = 'COPY DD-PACKET REPLACING LEADING ==PACKET-== BY ==LOGIN-PACKET-==, IDENTIFIER BY "login/x:y".'
    assert S._replacing(stmt) == [("LEADING", "PACKET-", "LOGIN-PACKET-"), ("", "IDENTIFIER", '"login/x:y"')]
    assert S._replacing("COPY X REPLACING A BY B, C BY D.") == [("", "A", "B"), ("", "C", "D")]
    assert S._replacing("COPY X REPLACING ==:PFX:== BY ==WS==.") == [("", ":PFX:", "WS")]


def test_leading_and_trailing_replace_only_word_parts():
    text = "02 PACKET-ID. 02 XPACKET-ID. 02 PACKET-REFERENCE"
    assert S._replace(text, "PACKET-", "LOGIN-PACKET-", "LEADING") == (
        "02 LOGIN-PACKET-ID. 02 XPACKET-ID. 02 LOGIN-PACKET-REFERENCE")
    assert S._replace("05 A-IN PIC X. 05 IN-B. 05 X-IN-Y", "-IN", "-OUT", "TRAILING") == (
        "05 A-OUT PIC X. 05 IN-B. 05 X-IN-Y")


# ---- level-78 constants -----------------------------------------------------------------------------------------
def test_level_78_constants_are_substituted_outside_literals():
    lines = [Line(t, "t", n) for n, t in enumerate([
        "78 MAX-ENTRIES VALUE 3.", "78 GREETING VALUE \"hi\".", "01 T OCCURS MAX-ENTRIES TIMES PIC X.",
        "MOVE GREETING TO X", 'DISPLAY "MAX-ENTRIES"'], 1)]  # fmt: skip
    out = [ln.text for ln in S.constants(lines)]
    assert out == ["01 T OCCURS 3 TIMES PIC X.", 'MOVE "hi" TO X', 'DISPLAY "MAX-ENTRIES"']


# ---- GnuCOBOL native binaries; COMP-5 byte order ----------------------------------------------------------------
def test_native_binaries_have_exact_widths_and_little_endian_values():
    (rec,) = _records("01 A.", "05 L1 BINARY-LONG VALUE 1.", "05 C1 BINARY-CHAR UNSIGNED VALUE 200.",
                      "05 S1 BINARY-SHORT VALUE -2.", "05 D1 BINARY-DOUBLE UNSIGNED.", "05 K5 PIC S9(9) COMP-5 VALUE 1.",
                      "05 KB PIC S9(9) COMP VALUE 1.")  # fmt: skip
    sizes = {c.name: c.size for c in rec.children}
    assert sizes == {"L1": 4, "C1": 1, "S1": 2, "D1": 8, "K5": 4, "KB": 4}
    # GnuCOBOL 3.1 on x86 under the harness flags: 01000000 c8 feff 0000000000000000 01000000 00000001
    assert L.image(rec).hex() == "01000000" "c8" "feff" "0000000000000000" "01000000" "00000001"
    assert [c.signed for c in rec.children[:4]] == [True, False, True, False]


def test_binary_long_long_is_binary_double():
    (rec,) = _records("01 A.", "05 X BINARY-LONG-LONG VALUE 5.")
    assert rec.children[0].size == 8


# ---- named refusals ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(("entry", "why"), [
    ("01 F FLOAT-LONG.", "USAGE FLOAT-LONG not modelled"),
    ("01 W PIC X(4) EXTERNAL.", "EXTERNAL data not modelled"),
    ("01 P USAGE PROGRAM-POINTER.", "PROGRAM-POINTER not modelled"),
    ("01 N BINARY-CHAR UNSIGNED VALUE LENGTH OF W.", "VALUE LENGTH OF not modelled"),
])  # fmt: skip
def test_unmodelled_dialect_data_is_refused_by_name(entry, why):
    with pytest.raises(L.LayoutError, match=why):
        _records("01 W PIC X(4).", entry)


def test_an_elementary_item_with_neither_picture_nor_usage_is_refused_not_sized_zero():
    rec = L.Item(level=1, name="Z", section="WORKING-STORAGE")
    with pytest.raises(L.LayoutError, match="no PICTURE and no modelled USAGE"):
        L.layout(rec)


# ---- literals past column 72 ------------------------------------------------------------------------------------
@pytest.mark.parametrize("lit", ['"play/clientbound/minecraft:block_changed_ack"', "'" + "x" * 130 + "'",
                                 '"a""b' + "c" * 70 + '"', 'X"' + "ab" * 40 + '"'])  # fmt: skip
def test_a_long_literal_value_parses_exactly(lit):
    (w, _) = _records("01 W PIC X(10).", f"    02 R PIC X(255) VALUE {lit} .", "     88 IS-R VALUE " + lit + ".",
                      "01 Z PIC X.")  # fmt: skip
    exp = ("hex", bytes.fromhex(lit[2:-1])) if lit[0] in "xX" else ("lit", lit[1:-1].replace(lit[0] * 2, lit[0]))
    assert w.children[0].values == [exp]
    assert w.children[0].conditions[0].values == [exp]
    assert w.children[0].line == 6  # the expanded line the entry came from, not a physical row


# ---- the free-format normalizer ---------------------------------------------------------------------------------
def test_free_format_resolves_directives_drops_comments_and_splits_units():
    src = [">>IF GCVERSION >= 32", "  REPLACE ==X== BY ==Y==.", ">>ELSE", "*> old compilers", ">>END-IF",
           "IDENTIFICATION DIVISION.", "PROGRAM-ID. Alpha.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
           "    01 A PIC X(3) VALUE \"*>a\". *> trailing", "PROCEDURE DIVISION.", "    DISPLAY A", "    GOBACK.",
           "END PROGRAM Alpha.", "IDENTIFICATION DIVISION.", "PROGRAM-ID. Beta.", "PROCEDURE DIVISION.",
           "    GOBACK.", "END PROGRAM Beta."]  # fmt: skip
    resolved = ff.resolve(src, {"GCVERSION": 31}, "t")
    assert not any("REPLACE" in x or "old compilers" in x for x in resolved)
    units = ff.units(resolved)
    assert [(n, nested) for n, _, nested in units] == [("Alpha", False), ("Beta", False)]
    fixed = ff.layout(units[0][1])
    assert "       01 A PIC X(3) VALUE \"*>a\"." in fixed  # Area A, comment gone, the literal's *> kept
    assert "           DISPLAY A" in fixed  # Area B
    assert all(len(x) <= 72 for x in fixed)


def test_free_format_refuses_what_it_does_not_model():
    with pytest.raises(ff.FreeFormatError, match="REPLACE"):
        ff.resolve(["REPLACE ==A== BY ==B==."], {}, "t")
    with pytest.raises(ff.FreeFormatError, match="not defined"):
        ff.resolve([">>IF V > 1", ">>END-IF"], {}, "t")


def test_free_format_continues_a_literal_longer_than_a_line():
    fixed = ff.layout(["01 A PIC X(200) VALUE \"" + "z" * 150 + "\"."])
    assert all(len(x) <= 72 for x in fixed)
    assert any(x[6] == "-" for x in fixed)
    joined = " ".join(ln.text for ln in S.logical_lines(fixed, "t"))
    assert '"' + "z" * 150 + '"' in joined  # the continuation rejoins the literal whole
