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
    body = "       01  FAKE-LIST.\n\t\t   05 FAKE-ITEM PIC X(4) VALUE '202'.\n"
    assert _lines(tmp_path, body)[4].text == "01  FAKE-LIST."


def test_a_tab_between_tokens_past_column_7_and_in_a_comment_is_read(tmp_path):
    body = "      *\tcomment with a tab\n       01  FAKE-ITEM\tPIC X(4).\n"
    assert _lines(tmp_path, body)[4].text == "01  FAKE-ITEM\tPIC X(4)."
