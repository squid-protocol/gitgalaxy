"""#4300: a PL/I unit with no labelled `END name;` ran to the next header and so took the lines that hold only a
columns 73-80 sequence number (navikt/DSF: 16 of 25 mis-ended procedures). It now ends at its last line with content.
Trailing comments stay with the unit: that is a separate question (the key ends a unit at its last code line)."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _seq(lines: list[str]) -> str:
    """Lines with an ISPF-style sequence number in columns 73-80."""
    return "\n".join(line.ljust(72) + f"{(i + 1) * 10:08d}" for i, line in enumerate(lines)) + "\n"


def _extents(src: str) -> list[tuple[str, int, int]]:
    result = StructuralExtractor("pli", LANGUAGE_DEFINITIONS).splice(src, "")
    return [(f["name"], f["start_line"], f["end_line"]) for f in result["functions"]]


def test_a_unit_closed_by_a_bare_end_stops_before_the_sequence_only_lines():
    src = _seq([" A: PROC;", "   X = 1;", "   RETURN;", " END;", "", "", "", " B: PROC;", "   Y = 2;", " END B;"])
    assert _extents(src) == [("A", 1, 4), ("B", 8, 10)]


def test_a_labelled_end_still_ends_the_unit_exactly_there():
    src = _seq([" A: PROC;", "   X = 1;", " END A;", "", "", " B: PROC;", "   Y = 2;", " END B;"])
    assert _extents(src) == [("A", 1, 3), ("B", 6, 8)]


def test_a_trailing_comment_stays_with_the_unit():
    src = _seq([" A: PROC;", "   X = 1;", " END;", "/* NOTE ON B */", "", " B: PROC;", "   Y = 2;", " END B;"])
    assert _extents(src) == [("A", 1, 4), ("B", 6, 8)]


def test_a_source_without_sequence_numbers_is_unchanged():
    src = "\n".join([" A: PROC;", "   X = 1;", " END;", "", " B: PROC;", "   Y = 2;", " END B;"]) + "\n"
    assert _extents(src) == [("A", 1, 3), ("B", 5, 7)]


def test_the_last_unit_of_a_file_also_drops_a_sequence_only_tail():
    src = _seq([" A: PROC;", "   X = 1;", " END;", "", ""])
    assert _extents(src) == [("A", 1, 3)]
