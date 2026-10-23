"""#5053: a det port's COMMAREA bytes are in the runtime's ASCII page, the expected logs in CCSID 037 (`PC-STEP` X'31'
against X'F1'). The crucible converts the answered bytes by the page before it compares; a port whose bytes are taken
as EBCDIC already, or a page that is not the runtime's, must fail the comparison rather than pass it."""

import base64
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402

LAYOUT = [
    {"name": "PC-STEP", "offset": 0, "bytes": 1, "pic": "X", "class": "X", "usage": None},
    {"name": "PC-AMT", "offset": 1, "bytes": 2, "pic": "S9(4)", "class": "9", "usage": "COMP"},
]
EXPECTED = b"\xf1\x01\x02"  # the log: '1' as X'F1', the COMP bytes untouched


def _area():
    return cc.FieldArea({"PC-STEP": "1", "PC-AMT": 258}, 3, b"\x00" * 3, 3)


def _answer(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def test_the_runtime_page_is_ascii_compatible_and_matches_the_java_property():
    assert runner.RUNTIME_PAGE == "latin-1"
    assert runner._with_answered_bytes(_area(), _answer(b"1\x01\x02"), runner.RUNTIME_PAGE, LAYOUT).data == EXPECTED


def test_ascii_page_bytes_equal_the_ebcdic_log_only_through_the_page():
    ok = runner._with_answered_bytes(_area(), _answer(b"1\x01\x02"), runner.RUNTIME_PAGE, LAYOUT)
    unconverted = cc.RawArea(b"1\x01\x02", cc.EBCDIC)  # what skipping the conversion would compare
    assert ok.data == EXPECTED and unconverted.data != EXPECTED  # X'31' is not X'F1'


def test_a_wrong_digit_or_a_wrong_binary_byte_still_differs_after_conversion():
    wrong_text = runner._with_answered_bytes(_area(), _answer(b"2\x01\x02"), runner.RUNTIME_PAGE, LAYOUT)
    wrong_bin = runner._with_answered_bytes(_area(), _answer(b"1\x01\x03"), runner.RUNTIME_PAGE, LAYOUT)
    assert wrong_text.data == b"\xf2\x01\x02" and wrong_bin.data == b"\xf1\x01\x03"
    assert EXPECTED not in (wrong_text.data, wrong_bin.data)


def test_an_ebcdic_page_hands_the_bytes_back_as_the_log_has_them():
    got = runner._with_answered_bytes(_area(), _answer(b"\xf1\x01\x02"), cc.EBCDIC, LAYOUT)
    assert got.data == EXPECTED
