"""#5195 era tags for assembler members: the COPY / macro members a member pulls in are read for tells (nested ones too),
a missing COPY member or a refused expansion is marked on the tag, and a system macro name is no gap."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import era_tags as et  # tests/tools/era_tags.py

MACRO_CALL = "         DFHPC TYPE=LINK,PROGRAM=SUBPGM\n"
PLAIN = "MAIN     CSECT\n         LR    2,3\n         END\n"


def finder(members: dict[str, str]):
    return lambda name: (f"{name}.mac", members[name.upper()]) if name.upper() in members else None


def read(text: str, members: dict[str, str]):
    books, skip = et.asm_members(text, finder(members))
    return et.tag_program(text, books, asm=True), books, skip


def test_tell_inside_a_copy_member():
    tag, books, skip = read(PLAIN + "         COPY  BOOK1\n", {"BOOK1": MACRO_CALL})
    t = next(x for x in tag["tells"] if x["tell"] == "dfh-macro-call")
    assert (t["via_copybook"], t["copybooks"], skip) == (True, ["BOOK1.mac"], None)  # noqa: S101
    assert tag["era"] == 0 and "copybook_skipped" not in tag  # noqa: S101


def test_tell_inside_a_macro_member_called_by_name():
    tag, books, skip = read(PLAIN + "         MYMAC A,B\n", {"MYMAC": MACRO_CALL})
    assert list(books) == ["MYMAC.mac"] and skip is None  # noqa: S101
    assert [x["tell"] for x in tag["tells"]] == ["dfh-macro-call"]  # noqa: S101


@pytest.mark.parametrize("levels", [2, 3, 5])
def test_nested_copy_chain(levels):
    members = {f"B{i}": f"         COPY  B{i + 1}\n" for i in range(1, levels)}
    members[f"B{levels}"] = MACRO_CALL
    tag, books, skip = read(PLAIN + "         COPY  B1\n", members)
    assert len(books) == levels and skip is None  # noqa: S101
    assert tag["tells"][0]["copybooks"] == [f"B{levels}.mac"]  # noqa: S101  (the member that holds the tell)


def test_member_two_paths_reach_is_read_once():
    members = {"A": "         COPY  C\n", "B": "         COPY  C\n", "C": MACRO_CALL}
    tag, books, skip = read(PLAIN + "         COPY  A\n         COPY  B\n", members)
    assert sorted(books) == ["A.mac", "B.mac", "C.mac"] and skip is None  # noqa: S101
    assert tag["tells"][0]["count"] == 1  # noqa: S101


def test_missing_copy_member_is_marked():
    tag, books, skip = read(PLAIN + "         COPY  GONE\n         COPY  BOOK1\n", {"BOOK1": MACRO_CALL})
    assert skip == "CopyNotFound" and list(books) == ["BOOK1.mac"]  # noqa: S101  (the others are still read)
    assert et.mark_skipped(tag, skip)["copybook_skipped"] == "CopyNotFound"  # noqa: S101


def test_missing_member_nested_in_a_found_one_is_marked():
    _, books, skip = read(PLAIN + "         COPY  A\n", {"A": "         COPY  GONE\n"})
    assert skip == "CopyNotFound" and list(books) == ["A.mac"]  # noqa: S101


def test_system_macro_and_instruction_names_are_no_gap():
    text = PLAIN + MACRO_CALL + "         DFHEIENT CODEREG=3\n         EXEC  CICS RETURN\n"
    _, books, skip = read(text, {})
    assert books == {} and skip is None  # noqa: S101


def test_macro_call_to_a_missing_name_is_no_gap_but_copy_is():
    assert read(PLAIN + "         NOMAC X\n", {})[2] is None  # noqa: S101
    assert read(PLAIN + "         COPY  NOMAC\n", {})[2] == "CopyNotFound"  # noqa: S101


def test_copy_loop_is_refused_and_terminates():
    _, books, skip = read(PLAIN + "         COPY  A\n", {"A": "         COPY  B\n", "B": "         COPY  A\n"})
    assert skip == "CopyCycle" and sorted(books) == ["A.mac", "B.mac"]  # noqa: S101


def test_self_copy_is_a_cycle():
    assert read(PLAIN + "         COPY  A\n", {"A": "         COPY  A\n"})[2] == "CopyCycle"  # noqa: S101


def test_recursive_macro_is_not_a_cycle():
    members = {"REC": "         MACRO\n         REC\n         REC\n         MEND\n" + MACRO_CALL}
    tag, books, skip = read(PLAIN + "         REC\n", members)
    assert skip is None and list(books) == ["REC.mac"]  # noqa: S101


def test_depth_cap():
    members = {f"B{i}": f"         COPY  B{i + 1}\n" for i in range(1, 30)}
    members["B30"] = MACRO_CALL
    books, skip = et.asm_members(PLAIN + "         COPY  B1\n", finder(members))
    assert skip == "CopyDepth" and len(books) < 30  # noqa: S101


def test_macro_prototype_line_is_not_a_call():
    members = {"PROTO": "         MACRO\n&L       PROTO &A\n         MEND\n", "OTHER": MACRO_CALL}
    books, skip = et.asm_members("         PROTO X\n         OTHER\n", finder(members))
    assert sorted(books) == ["OTHER.mac", "PROTO.mac"] and skip is None  # noqa: S101


def test_comment_lines_are_not_expanded():
    members = {"BOOK1": MACRO_CALL}
    assert et.asm_members("* COPY BOOK1\n.* BOOK1\n" + PLAIN, finder(members)) == ({}, None)  # noqa: S101


def test_lowercase_and_label_before_copy():
    books, skip = et.asm_members("LBL      copy  book1\n", finder({"BOOK1": MACRO_CALL}))
    assert list(books) == ["book1.mac"] or list(books) == ["BOOK1.mac"]  # noqa: S101
    assert skip is None  # noqa: S101


def test_no_members_is_the_member_alone():
    tag, books, skip = read(PLAIN + MACRO_CALL, {})
    assert books == {} and skip is None  # noqa: S101
    assert tag == et.tag_program(PLAIN + MACRO_CALL)  # noqa: S101


def test_cobol_copybook_still_ignores_macro_text():
    assert et.tag_program("       PROGRAM-ID. P.\n", {"B.cpy": MACRO_CALL})["tells"] == []  # noqa: S101
