"""#5561: GnuCOBOL's IBM dialect reserves TIMESTAMP, Enterprise COBOL does not (CBSA's BANKDATA performs a paragraph
named TIMESTAMP), so a program that uses the word as its own name is compiled with it un-reserved."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_common as common  # noqa: E402


def test_a_paragraph_named_timestamp_is_unreserved():
    source = "       PROCEDURE DIVISION.\n           PERFORM TIMESTAMP.\n       TIMESTAMP SECTION.\n"
    assert common.not_reserved_flags(source) == ["-fnot-reserved=TIMESTAMP"]


def test_a_program_without_the_word_gets_no_flag():
    assert common.not_reserved_flags("           MOVE WS-TIMESTAMP-X TO WS-OUT.\n") == []


def test_compile_options_carry_the_flag():
    _, flags = common.compile_options({"program": "P"}, "           PERFORM TIMESTAMP.\n")
    assert "-fnot-reserved=TIMESTAMP" in flags
