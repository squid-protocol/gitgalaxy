"""#8412: a tab in the sequence area and the REPLACE statement (not COPY ... REPLACING) are refused by name by the det
reader, never translated with shifted columns or unreplaced text. Authored programs, invented names."""

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


@pytest.mark.parametrize("lead", ["\t01", "\t\t01", "   \t01", "12\t01"])
def test_a_tab_in_the_sequence_area_is_refused_by_name(tmp_path, lead):
    with pytest.raises(SRC.SourceFormatRefused, match="tab character in columns 1-7"):
        _lines(tmp_path, lead + "  FAKE-ITEM PIC X(4).\n")


def test_a_tab_between_tokens_past_column_7_and_in_a_comment_is_read(tmp_path):
    body = "      *\tcomment with a tab\n       01  FAKE-ITEM\tPIC X(4).\n"
    assert _lines(tmp_path, body)[4].text == "01  FAKE-ITEM\tPIC X(4)."
