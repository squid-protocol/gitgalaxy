"""#8412 (c:1e95fd31), engine scan side: tab characters and the REPLACE statement (not COPY ... REPLACING).

The det reader's side is pinned in test_det_tab_replace_8412.py (#8654). This pins what the extractor
(`extract_boundary`, the source of `record_data` / `data_move_data`) does with the same two inputs, on authored
programs with invented names:

* a tab in columns 1-7, a tab between tokens and a tab in a comment line do not hide, merge or rename a
  declaration, and the item keeps its source line number;
* a REPLACE statement is not a data item and does not hide its neighbours. The extractor does NOT apply it:
  names stay as written (`FAKEOLD`, not `FAKENEW`). That is the stated boundary, not a claim of correctness: a
  consumer that needs the replaced names must not read them from the scan (sibling gap in the PR that added this).
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary

HEAD = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
TAIL = "       PROCEDURE DIVISION.\n           GOBACK.\n"


def _boundary(body: str, tail: str = TAIL) -> dict:
    return extract_boundary("cobol", HEAD + body + tail)


def _items(body: str) -> list[tuple[str, int]]:
    return [(r["name"], r["line"]) for r in _boundary(body)["records"]]


def test_tab_in_the_sequence_area_does_not_hide_the_item():
    body = "       01  FAKE-FIRST PIC X(4).\n\t01  FAKE-TABBED PIC X(4).\n\t\t   05 FAKE-DEEP PIC X(4).\n       01  FAKE-LAST PIC X(4).\n"
    names = [n for n, _ in _items(body)]
    assert names == ["FAKE-FIRST", "FAKE-TABBED", "FAKE-DEEP", "FAKE-LAST"]


def test_tab_between_tokens_and_in_a_comment_line():
    body = "      *\tcomment with a tab 01 FAKE-NOT-AN-ITEM PIC X.\n       01  FAKE-ITEM\tPIC\tX(4).\n"
    got = {r["name"]: r for r in _boundary(body)["records"]}
    assert list(got) == ["FAKE-ITEM"]
    assert got["FAKE-ITEM"]["pic"] == "X(4)"


def test_tab_led_items_keep_their_line_numbers():
    body = "       01  FAKE-A PIC X(4).\n\t01  FAKE-B PIC X(4).\n       01  FAKE-C PIC X(4).\n"
    lines = dict(_items(body))
    assert lines["FAKE-C"] - lines["FAKE-B"] == lines["FAKE-B"] - lines["FAKE-A"] == 1


def test_tab_led_statement_in_the_procedure_division_is_a_data_move():
    tail = "       PROCEDURE DIVISION.\n\tMOVE 'A' TO FAKE-B\n           GOBACK.\n"
    b = _boundary("       01  FAKE-B PIC X(4).\n", tail)
    assert [m["target"] for m in b["data_moves"]] == ["FAKE-B"]


def test_replace_statement_is_not_an_item_and_hides_no_neighbour():
    for stmt in (
        "       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n",
        "       REPLACE\n           ==FAKEOLD== BY ==FAKENEW==.\n",
        "       REPLACE OFF.\n",
    ):
        body = (
            "       01  FAKE-BEFORE PIC X(4).\n"
            + stmt
            + "       01  FAKEOLD PIC X(4).\n       01  FAKE-AFTER PIC X(4).\n"
        )
        assert [n for n, _ in _items(body)] == ["FAKE-BEFORE", "FAKEOLD", "FAKE-AFTER"], stmt


def test_replace_statement_is_not_applied_by_the_extractor():
    """The boundary this PR records: the scan reports the names as written. The det reader refuses the same
    program by name (ReplaceStatementRefused) rather than translate it unreplaced."""
    body = "       REPLACE ==FAKEOLD== BY ==FAKENEW==.\n       01  FAKEOLD PIC X(4).\n"
    tail = "       PROCEDURE DIVISION.\n           MOVE 'A' TO FAKEOLD\n           GOBACK.\n"
    b = _boundary(body, tail)
    assert [r["name"] for r in b["records"]] == ["FAKEOLD"]
    assert [m["target"] for m in b["data_moves"]] == ["FAKEOLD"]


def test_names_that_start_with_replace_are_items():
    body = "       01  REPLACE-FLAG PIC X(4).\n       01  REPLACER PIC X(4).\n"
    assert [n for n, _ in _items(body)] == ["REPLACE-FLAG", "REPLACER"]
