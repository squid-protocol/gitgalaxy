"""#7169 (translator sites): a PICTURE's repeat count is read as a run length, never expanded to that many characters.

The COBOL -> Java translator expanded `c(n)` into n characters in five places (det.layout.Item.picture and every
property on it, the transaction forge's layout partition, the repository forge's numeric codec, and
cobol_to_java_common's parse_pic_precision / _pli_java_type), so `PIC X(1073741824)` -- a GnuCOBOL caller-sized
LINKAGE buffer -- built a 1 GiB string per read. Each now counts from `pic_runs` / `pli_pic_runs`. The results are
the expansion's for every other picture (a differential run of 100,000 random pictures matched origin/main).
"""

import time
import tracemalloc

import pytest

from gitgalaxy.tools.cobol_to_java import cobol_to_java_common as C
from gitgalaxy.tools.cobol_to_java import cobol_to_java_repository_forge as R
from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as T
from gitgalaxy.tools.cobol_to_java.det import layout as L

# The size of the GnuCOBOL buffer is 1073741824; the bounded-memory tests use 2**27 -- still 2000 times their 64 KiB
# bound if a regression expands it, but a size any CI runner survives (a 1 GiB expansion read three times is 3 GB).
GIB = 2**27


def _item(pic, **kw):
    return L.Item(level=1, name="BUF", section="LINKAGE", pic=pic, **kw)


def _bounded(fn):
    """fn() in under 0.5 s and 64 KiB of allocation (the expansion: GIB bytes, and more)."""
    tracemalloc.start()
    started = time.perf_counter()
    try:
        out = fn()
    finally:
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    assert peak < 64 * 1024, peak
    assert elapsed < 0.5, elapsed
    return out


def test_a_huge_alphanumeric_item_is_read_without_its_expansion():
    it = _item(f"X({GIB})")
    got = _bounded(lambda: (it.runs(), it.symbols(), it.category, it.digits, it.scale, it.signed,
                            it.elementary_size()))  # fmt: skip
    assert got == ([("X", GIB)], {"X"}, "ALPHANUMERIC", 0, 0, False, GIB)


def test_a_huge_numeric_picture_in_every_forge_helper():
    pic = f"S9({GIB})V99"
    it = _item(pic)
    assert _bounded(lambda: (it.category, it.digits, it.scale, it.signed, it.elementary_size())) == (
        "NUMERIC", GIB + 2, 2, True, GIB + 2)  # fmt: skip
    assert _bounded(lambda: C.parse_pic_precision(pic, False)) == (GIB + 2, 2)
    assert _bounded(lambda: R._pic_numeric(pic)) == (True, GIB + 2, 2)
    assert _bounded(lambda: T._expanded_pic(f"X({GIB})")) == (("X", GIB),)
    assert _bounded(lambda: C._pli_java_type("9", f"({GIB})9V99", "")) == "BigDecimal"


def test_runs_read_as_the_old_expansion():
    assert C.pic_runs("S9(3)V99") == [("S", 1), ("9", 3), ("V", 1), ("9", 2)]
    assert C.pic_runs("X(08)") == C.pic_runs("XXXXXXXX") == [("X", 8)]  # equal expansions, equal runs
    assert C.pic_runs("9(0)X") == [("X", 1)]  # c(0) is no position
    assert C.pic_runs("X(A)") == [("X", 1), ("(", 1), ("A", 1), (")", 1)]  # not a count: literal characters
    assert C.pli_pic_runs("(5)9V99") == [("9", 5), ("V", 1), ("9", 2)]
    assert C.runs_partition(C.pic_runs("99VV9"), "V") == ([("9", 2)], [], [("V", 1), ("9", 1)])  # as str.split
    assert C.runs_partition(C.pic_runs("999"), "V") == ([("9", 3)], None, [])


@pytest.mark.parametrize(
    ("pic", "dc", "want"),
    [
        ("S9(7)V99", False, (9, 2)),
        ("ZZZ.ZZ9,99", True, (8, 2)),  # #3827: DECIMAL-POINT IS COMMA
        ("$$$,$$9.99", False, (7, 2)),  # a floating string: every symbol but the first is a digit
        ("+++9V99", False, (5, 2)),
        ("-(5)9.99", False, (7, 2)),
    ],
)
def test_parse_pic_precision_is_unchanged(pic, dc, want):
    assert C.parse_pic_precision(pic, dc) == want


def test_currency_symbols_still_count_as_digits():
    assert C.parse_pic_precision("UUU,UU9.99", False, ("U",)) == (7, 2)  # #3910
    assert C.parse_pic_precision("KK,KK,KK9.99", False, ("K",)) == (8, 2)


@pytest.mark.parametrize(
    ("pic", "kw", "want"),
    [
        ("S9(4)V99", {}, ("NUMERIC", 6, 2, True, 6)),
        ("S9(4)V99", {"sign_separate": True}, ("NUMERIC", 6, 2, True, 7)),
        ("99PP", {}, ("NUMERIC", 2, -2, False, 2)),
        ("SVPP999", {}, ("NUMERIC", 3, 5, True, 3)),
        ("ZZ,ZZ9.99CR", {}, ("NUMERIC-EDITED", 3, 2, False, 11)),  # an edited item's digits: its 9s and Ps
        ("ZZ.ZZ9,99", {"decimal_comma": True}, ("NUMERIC-EDITED", 3, 2, False, 9)),
        ("XX/XX", {}, ("ALPHANUMERIC-EDITED", 0, 0, False, 5)),
        ("A(3)", {}, ("ALPHABETIC", 0, 0, False, 3)),
    ],
)
def test_det_layout_properties_are_unchanged(pic, kw, want):
    it = _item(pic, **kw)
    assert (it.category, it.digits, it.scale, it.signed, it.elementary_size()) == want


def test_an_edited_mask_is_still_expanded_for_the_runtime():
    # Field.numericEdited takes the mask itself: an edited item is as long as its mask, so it stays a string
    assert _item("Z(3)9.9(2)").picture() == "ZZZ9.99"


def test_the_numeric_codec_and_pli_types_are_unchanged():
    assert R._pic_numeric("S9(10)V99") == (True, 12, 2)
    assert R._pic_numeric("X(4)") is None
    assert R._pic_numeric("9(0)") is None  # an empty expansion
    assert C._pli_java_type("9", "(5)9V99", "") == "BigDecimal"
    assert C._pli_java_type("9", "(5)9", "") == "Integer"
    assert C._pli_java_type("9", "ZZ9", "") == "String"
