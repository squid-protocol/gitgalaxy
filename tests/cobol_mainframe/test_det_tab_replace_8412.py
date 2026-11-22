"""#8412: the REPLACE statement (not COPY ... REPLACING) is refused by name by the det
reader, never translated unreplaced; tabs are pinned as read. Authored programs, invented names."""

import pytest

from gitgalaxy.tools.cobol_to_java.det import source as SRC

HEAD = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
TAIL = "       PROCEDURE DIVISION.\n           GOBACK.\n"


def _lines(tmp_path, body):
    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(HEAD + body + TAIL)
    return SRC.program_lines(p, [])


@pytest.mark.parametrize(
    "stmt",
    [
        "       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n",
        "       replace ==FAKEOLD== by ==FAKENEW==.\n",
        "       REPLACE OFF.\n",
        "       REPLACE\n           ==FAKEOLD== BY ==FAKENEW==.\n",
    ],
)
def test_a_replace_statement_is_refused_by_name(tmp_path, stmt):
    with pytest.raises(SRC.ReplaceStatementRefused, match="REPLACE statement"):
        _lines(tmp_path, stmt + "       01  FAKEOLD PIC X(4).\n")


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


@pytest.mark.parametrize("lead", ["\t\t   05 FAKE-ITEM PIC X(4).\n", "\t05 FAKE-ITEM PIC X(4).\n", "  \t  FAKE-ITEM PIC X(4).\n"])
def test_a_tab_with_program_text_inside_columns_1_to_7_is_refused_by_name(tmp_path, lead):
    """The sequence area and indicator are cut at column 7, so `05` (or `FAKE-ITEM`'s head) would be lost: refused."""
    with pytest.raises(SRC.TabInSequenceAreaRefused, match=r"FAKEPGM\.cbl:6: a tab in columns 1-7"):
        _lines(tmp_path, "       01  FAKE-LIST.\n" + lead)


def test_a_tab_in_a_copybook_is_read_when_blank_after_it_and_refused_when_text_follows(tmp_path):
    (tmp_path / "FAKECPY.cpy").write_text("\t\t       05 FAKE-A PIC X(4).\n       01  FAKE-B\tPIC X(4).\n")
    p = tmp_path / "FAKEPGM.cbl"
    p.write_text(HEAD + "       COPY FAKECPY.\n" + TAIL)
    assert [ln.text.strip() for ln in SRC.program_lines(p, [tmp_path])][4:6] == ["05 FAKE-A PIC X(4).", "01  FAKE-B\tPIC X(4)."]
    (tmp_path / "FAKECPY.cpy").write_text("\t\t   05 FAKE-A PIC X(4).\n")
    with pytest.raises(SRC.TabInSequenceAreaRefused, match=r"FAKECPY\.cpy:1: a tab in columns 1-7"):
        SRC.program_lines(p, [tmp_path])
