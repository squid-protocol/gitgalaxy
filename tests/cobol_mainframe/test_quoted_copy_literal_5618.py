"""#5618: a quoted GnuCOBOL copybook literal with an extension (`COPY "ws-state.cpy".`) is recorded.

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
    ['"ws-state.cpy"', "'ws-state.cpy'", '"ws-state"', "ws-state", '"WS-STATE.CPY"'],
)
def test_member_is_the_stem_for_every_literal_shape(literal):
    records, copies = _scan(f"01 G.\n    COPY {literal}.\n    05 X PIC 9.\n")
    assert records[0]["copy_members"] == "WS-STATE"


def test_plain_copy_before_first_entry_is_recorded_with_no_replacing():
    _, copies = _scan("COPY \"ws-state.cpy\".\nCOPY 'ws-player.cpy'.\n01 G.\n    05 X PIC 9.\n")
    assert [(c["member"], c["replacing"], c["library"]) for c in copies] == [
        ("WS-STATE", "", ""),
        ("WS-PLAYER", "", ""),
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


def test_procedure_division_copy_is_recorded_with_its_section():
    copies: list = []
    code = (
        HEAD
        + "01 G.\n    05 X PIC 9.\nPROCEDURE DIVISION.\n    STOP RUN.\n"
        + '    COPY "pd-level.cpy".\n    COPY "pd-world.cpy".\n'
    )
    _cobol_records(code, None, copies)
    assert [(c["member"], c["section"], c["replacing"]) for c in copies] == [
        ("PD-LEVEL", "PROCEDURE", ""),
        ("PD-WORLD", "PROCEDURE", ""),
    ]
