"""#5618: a quoted GnuCOBOL copybook literal with an extension (`COPY "sprstate.cpy".`) is recorded.

The member name class stops at `.`, so the `IN|OF` library and `REPLACING` phrase after
`"m.cpy"` were never read, and a plain COPY that follows no entry (before a section's first entry) had
no `copy_statement_data` row at all.
"""

import pytest

from gitgalaxy.core.mainframe_boundary import _cobol_records

HEAD = "WORKING-STORAGE SECTION.\n"


def _scan(body: str):
    copies: list = []
    records = _cobol_records(HEAD + body, None, copies)
    return records, copies


@pytest.mark.parametrize(
    "literal",
    ['"sprstate.cpy"', "'sprstate.cpy'", '"sprstate"', "sprstate", '"SPRSTATE.CPY"'],
)
def test_member_is_the_stem_for_every_literal_shape(literal):
    records, copies = _scan(f"01 G.\n    COPY {literal}.\n    05 X PIC 9.\n")
    assert records[0]["copy_members"] == "SPRSTATE"


def test_plain_copy_before_first_entry_is_recorded_with_no_replacing():
    _, copies = _scan("COPY \"sprstate.cpy\".\nCOPY 'playstate.cpy'.\n01 G.\n    05 X PIC 9.\n")
    assert [(c["member"], c["replacing"], c["library"]) for c in copies] == [
        ("SPRSTATE", "", ""),
        ("PLAYSTATE", "", ""),
    ]


def test_library_and_replacing_after_an_extension_literal():
    records, copies = _scan('01 G.\n    COPY "m.cpy" OF lib REPLACING ==A== BY ==B==.\n    05 X PIC 9.\n')
    assert records[0]["copy_members"] == "M"
    assert records[0]["copy_libraries"] == "LIB"
    assert records[0]["copy_replacing"] == '[[["A", "B"]]]'


def test_section_level_replacing_with_extension_literal():
    _, copies = _scan('COPY "r.cpy" REPLACING ==A== BY ==B==.\n01 G.\n    05 X PIC 9.\n')
    assert copies[0]["member"] == "R"
    assert copies[0]["replacing"] == '[["A", "B"]]'


def test_extension_not_swallowed_without_closing_quote():
    records, _ = _scan("01 G.\n    COPY plain.\n    05 X PIC 9.\n")
    assert records[0]["copy_members"] == "PLAIN"
