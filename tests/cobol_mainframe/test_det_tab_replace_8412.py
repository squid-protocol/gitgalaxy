"""#8412: the REPLACE statement (not COPY ... REPLACING) is applied by the det reader (det/replace.py), or refused by
name where it cannot be; tabs are pinned as read. Authored programs, invented names."""

import pytest

from gitgalaxy.tools.cobol_to_java.det import source as SRC

HEAD = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
TAIL = "       PROCEDURE DIVISION.\n           GOBACK.\n"


def _lines(tmp_path, body):
    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(HEAD + body + TAIL)
    return SRC.program_lines(p, [])


def _texts(tmp_path, body):
    return [ln.text.strip() for ln in _lines(tmp_path, body)][4:-2]


def test_the_replace_statement_is_applied_to_the_text_after_it_and_removed(tmp_path):
    """IBM: REPLACE rewrites the text that follows it (whole words, case-insensitive) and is not itself program text."""
    body = "       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n       01  FAKEOLD PIC X(4).\n       01  FAKEOLDER PIC X(4).\n"
    assert _texts(tmp_path, body) == ["01  FAKENEW PIC X(4).", "01  FAKEOLDER PIC X(4)."]
    assert _texts(tmp_path, body.replace("FAKEOLD ", "fakeold ", 1)) == [
        "01  FAKENEW PIC X(4).",
        "01  FAKEOLDER PIC X(4).",
    ]


def test_replace_off_and_a_second_replace_end_and_supersede_the_first(tmp_path):
    body = (
        "       REPLACE ==FAKEA== BY ==FAKEB==.\n       01  FAKEA PIC X.\n"
        "       REPLACE ==FAKEC== BY ==FAKED== ==FAKEA== BY ==FAKEE==.\n       01  FAKEA PIC X.\n       01  FAKEC PIC X.\n"
        "       REPLACE OFF.\n       01  FAKEA PIC X.\n"
    )
    assert _texts(tmp_path, body) == [
        "01  FAKEB PIC X.",
        "01  FAKEE PIC X.",
        "01  FAKED PIC X.",
        "01  FAKEA PIC X.",
    ]


def test_a_multi_line_statement_a_tail_after_its_period_and_a_literal(tmp_path):
    """The statement may span lines; text after its period is read under it; a literal is one text-word, never matched inside."""
    body = (
        "       REPLACE\n           ==FAKEOLD== BY ==FAKENEW==. 01  FAKEOLD PIC X(4).\n"
        "       01  FAKE-LIT PIC X(7) VALUE 'FAKEOLD'.\n"
    )
    assert _texts(tmp_path, body) == ["01  FAKENEW PIC X(4).", "01  FAKE-LIT PIC X(7) VALUE 'FAKEOLD'."]


def test_replace_applies_to_copy_member_text_and_comes_after_copy_replacing(tmp_path):
    """IBM orders COPY (with REPLACING) first, then REPLACE over the result, member text included."""
    (tmp_path / "FAKECPY.cpy").write_text("       01  FAKEOLD PIC X(4).\n       01  FAKEMID PIC X(4).\n")
    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(
        HEAD
        + "       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n       COPY FAKECPY REPLACING ==FAKEMID== BY ==FAKEOLD==.\n"
        + TAIL
    )
    assert [ln.text.strip() for ln in SRC.program_lines(p, [tmp_path])][4:6] == [
        "01  FAKENEW PIC X(4).",
        "01  FAKENEW PIC X(4).",
    ]


def test_a_replace_the_reader_cannot_apply_is_still_refused_by_name(tmp_path):
    for body, why in [
        ("       REPLACE ==FAKE OLD== BY ==FAKENEW==.\n       01  X PIC X.\n", "multi-word"),
        ("       REPLACE ==== BY ==FAKENEW==.\n       01  X PIC X.\n", "empty"),
        ("       REPLACE FAKEOLD BY FAKENEW.\n       01  X PIC X.\n", "not ==pseudo-text=="),
        ("       REPLACE ==FAKEOLD== BY ==FAKENEW==\n       01  X PIC X.\n", "refused"),
        ("       01  X PIC X. REPLACE ==FAKEOLD== BY ==FAKENEW==.\n", "does not start its line"),
    ]:
        with pytest.raises(SRC.ReplaceStatementRefused, match=why):
            _lines(tmp_path, body)


def test_a_replace_in_effect_at_end_program_is_refused(tmp_path):
    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(HEAD + "       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n" + TAIL + "       END PROGRAM FAKEPGM.\n")
    with pytest.raises(SRC.ReplaceStatementRefused, match="END PROGRAM"):
        SRC.program_lines(p, [])


def test_the_replaced_names_reach_the_layout(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import layout

    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(HEAD + "       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n       01  FAKEOLD PIC X(4).\n" + TAIL)
    assert [i.name for i in layout.records(p, [])] == ["FAKENEW"]


def test_replacing_and_names_that_start_with_replace_are_not_the_statement(tmp_path):
    body = "       01  REPLACE-FLAG PIC X(4).\n       01  REPLACER PIC X(4).\n"
    assert [ln.text for ln in _lines(tmp_path, body)][4:6] == ["01  REPLACE-FLAG PIC X(4).", "01  REPLACER PIC X(4)."]


def test_tab_led_value_lines_are_read_as_carddemo_ships_them(tmp_path):
    """CardDemo's CSLKPCDY.cpy leads continuation lines of a VALUE list with tabs (columns 1-2): burned, translated
    and proven today, so a tab in the sequence area is NOT refused (#8412: tab-stop expansion stays a sibling gap)."""
    body = "       01  FAKE-LIST.\n\t\t                            '202',\n"
    assert _lines(tmp_path, body)[4].text == "01  FAKE-LIST."


def test_a_tab_between_tokens_past_column_7_and_in_a_comment_is_read(tmp_path):
    body = "      *\tcomment with a tab\n       01  FAKE-ITEM\tPIC X(4).\n"
    assert _lines(tmp_path, body)[4].text == "01  FAKE-ITEM\tPIC X(4)."


def test_a_replace_statement_inside_a_copybook_is_refused_by_name_with_the_member_named(tmp_path):
    """The same refusal holds for a member pulled in by COPY: the program text never carries the statement, the
    member does, and the message names the member file, not the program."""
    (tmp_path / "FAKECPY.cpy").write_text("       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n       01  FAKEOLD PIC X(4).\n")
    body = "       COPY FAKECPY.\n"
    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(HEAD + body + TAIL)
    with pytest.raises(SRC.ReplaceStatementRefused, match=r"FAKECPY\.cpy:1: the REPLACE statement"):
        SRC.program_lines(p, [tmp_path])


@pytest.mark.parametrize(
    "lead", ["\t\t   05 FAKE-ITEM PIC X(4).\n", "\t05 FAKE-ITEM PIC X(4).\n", "  \t  FAKE-ITEM PIC X(4).\n"]
)
def test_a_tab_with_program_text_inside_columns_1_to_7_is_refused_by_name(tmp_path, lead):
    """The sequence area and indicator are cut at column 7, so `05` (or `FAKE-ITEM`'s head) would be lost: refused."""
    with pytest.raises(SRC.TabInSequenceAreaRefused, match=r"FAKEPGM\.cbl:6: a tab in columns 1-7"):
        _lines(tmp_path, "       01  FAKE-LIST.\n" + lead)


def test_a_tab_in_a_copybook_is_read_when_blank_after_it_and_refused_when_text_follows(tmp_path):
    (tmp_path / "FAKECPY.cpy").write_text("\t\t       05 FAKE-A PIC X(4).\n       01  FAKE-B\tPIC X(4).\n")
    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(HEAD + "       COPY FAKECPY.\n" + TAIL)
    assert [ln.text.strip() for ln in SRC.program_lines(p, [tmp_path])][4:6] == [
        "05 FAKE-A PIC X(4).",
        "01  FAKE-B\tPIC X(4).",
    ]
    (tmp_path / "FAKECPY.cpy").write_text("\t\t   05 FAKE-A PIC X(4).\n")
    with pytest.raises(SRC.TabInSequenceAreaRefused, match=r"FAKECPY\.cpy:1: a tab in columns 1-7"):
        SRC.program_lines(p, [tmp_path])
