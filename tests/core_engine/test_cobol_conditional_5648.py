"""#5648: >>DEFINE / >>IF / >>ELSE / >>END-IF live in core.cobol_conditional; the translator's reader consumes them."""

from __future__ import annotations

from decimal import Decimal

import pytest

from gitgalaxy.core.cobol_conditional import Conditional, ConditionalCompilation, active_source, options_defines
from gitgalaxy.core.compiler_options import compiler_options
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_java.det.source import logical_lines, program_lines


def kept(lines, defines=None):
    c = Conditional(defines)
    out = [ln for ln in lines if c.feed(ln)]
    c.finish()
    return out


@pytest.mark.parametrize(
    ("cond", "expect"),
    [
        ("DEBUG IS DEFINED", True),
        ("DEBUG DEFINED", True),
        ("NOPE IS NOT DEFINED", True),
        ("NOPE DEFINED", False),
        ("VER = 2", True),
        ("VER > 1 AND VER <= 2", True),
        ("VER GREATER THAN OR EQUAL TO 3", False),
        ("VER NOT = 2", False),
        ("VER <> 2", False),
        ("VER IS EQUAL TO 2.0", True),
        ("NAME = 'ABC'", True),
        ("NAME = 'ABC   '", True),  # the shorter operand is padded with spaces
        ("NOT (VER LESS THAN 2 OR NAME = 'X')", True),
        ("NOPE DEFINED OR DEBUG DEFINED", True),
    ],
)
def test_conditions(cond, expect):
    src = ["      >>DEFINE DEBUG AS 1", "      >>DEFINE VER AS 2", "      >>DEFINE NAME AS 'ABC'",
           f"      >>IF {cond}", "       A", "      >>ELSE", "       B", "      >>END-IF"]  # fmt: skip
    assert kept(src) == (["       A"] if expect else ["       B"])


def test_nesting_and_directives_in_an_inactive_branch_are_ignored():
    src = [
        ">>IF X DEFINED",
        ">>DEFINE Y AS 1",
        "a",
        ">>ELSE",
        ">>IF Y DEFINED",
        "b",
        ">>ELSE",
        "c",
        ">>END-IF",
        "d",
        ">>END-IF",
        "e",
    ]
    assert kept(src) == ["c", "d", "e"]  # Y was defined only in the branch not taken
    assert kept([">>DEFINE X AS 1", *src]) == ["a", "e"]


def test_an_option_is_read_only_through_as_parameter():
    # IBM (DEFINE option): an option no `>>DEFINE name AS PARAMETER` asks for is ignored; the source literal stands
    opts = {"V": Decimal(9), "P": "Z"}
    assert kept([">>IF V DEFINED", "yes", ">>ELSE", "no", ">>END-IF"], opts) == ["no"]
    assert kept([">>DEFINE V AS 1", ">>IF V = 1", "one", ">>END-IF"], opts) == ["one"]
    assert kept([">>DEFINE P AS PARAMETER", ">>IF P = 'Z'", "z", ">>END-IF"], opts) == ["z"]
    # AS PARAMETER with no option: the name is not defined (IBM), not an error
    assert kept([">>DEFINE Q AS PARAMETER", ">>IF Q IS NOT DEFINED", "none", ">>END-IF"], opts) == ["none"]


def test_redefinition_needs_override_unless_the_value_is_the_same():
    assert kept(
        [">>DEFINE W AS 1", ">>DEFINE W AS 1", ">>DEFINE W AS 2 OVERRIDE", ">>IF W = 2", "two", ">>END-IF"]
    ) == ["two"]


@pytest.mark.parametrize(
    "src",
    [
        [">>ELSE"],
        [">>END-IF"],
        [">>IF A DEFINED", "x"],  # left open
        [">>IF A = 1", ">>END-IF"],  # relation on an undefined name
        [">>DEFINE A AS 1", ">>IF A = 'x'", ">>END-IF"],  # numeric against alphanumeric
        [">>DEFINE A AS 1", ">>DEFINE A AS 2"],  # another value without OVERRIDE
        [">>DEFINE A AS 'X'", ">>IF A < 'Y'", ">>END-IF"],  # ordering on alphanumerics
        [">>DEFINE A AS 1 2"],
        [">>DEFINE A OFF"],
        [">>DEFINE A AS TRUE"],
        [">>EVALUATE X"],
        [">>IF A DEFINED", ">>ELSE", ">>ELSE", ">>END-IF"],
        [">>IF A DEFINED OR", ">>END-IF"],
    ],
)
def test_refused_by_name(src):
    with pytest.raises(ConditionalCompilation):
        kept(src)


def test_options_defines_from_cbl_cards():
    rows = compiler_options("       CBL DEFINE(DEBUG=1),DEFINE(MODE='X')\n       IDENTIFICATION DIVISION.\n")
    assert options_defines(rows) == {"DEBUG": Decimal(1), "MODE": "X"}
    with pytest.raises(ConditionalCompilation):
        options_defines([{"option": "DEFINE", "value": "BARE"}])


def test_logical_lines_fixed_drops_branches_not_taken_with_their_continuations_and_comments():
    raw = [
        "       CBL DEFINE(PROD=1)",
        "       IDENTIFICATION DIVISION.",
        "      >>DEFINE PROD AS PARAMETER",
        "      >>IF PROD = 1",
        "       DISPLAY 'LIVE'.",
        "      >>ELSE",
        "      * a comment in the branch not taken",
        "       DISPLAY 'TEST ",
        "      -    'MORE'.",
        "      >>END-IF",
        "       STOP RUN.",
    ]
    assert [ln.text.strip() for ln in logical_lines(raw, "P.cbl")] == [
        "IDENTIFICATION DIVISION.", "DISPLAY 'LIVE'.", "STOP RUN."
    ]  # fmt: skip
    assert [ln.line for ln in logical_lines(raw, "P.cbl")] == [2, 5, 11]


def test_logical_lines_free_format_and_unterminated_if_names_its_file():
    raw = ["       >>SOURCE FORMAT FREE", ">>DEFINE A AS 1", ">>IF A = 2", "no", ">>ELSE", "yes", ">>END-IF"]
    assert [ln.text.strip() for ln in logical_lines(raw, "/x/P.cbl")] == ["yes"]
    with pytest.raises(ConditionalCompilation, match=r"P\.cbl"):
        logical_lines(["      >>IF A DEFINED", "       X."], "/x/P.cbl")


def test_a_directive_in_a_copy_member_is_refused_by_name(tmp_path):
    # the member is read alone: the program's >>DEFINE at the COPY is not known there, so `X IS DEFINED` cannot be
    # answered; a member without directives still expands
    prog = tmp_path / "P.cbl"
    prog.write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n      >>DEFINE X AS 1\n"
        "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       COPY M.\n"
    )
    (tmp_path / "M.cpy").write_text("       01 A PIC X.\n")
    assert [ln.text.strip() for ln in program_lines(prog, [])][-1] == "01 A PIC X."
    (tmp_path / "M.cpy").write_text("      >>IF X IS DEFINED\n       01 A PIC X.\n      >>END-IF\n")
    with pytest.raises(ConditionalCompilation, match=r"M\.cpy:1: >>IF: conditional compilation in a COPY member"):
        program_lines(prog, [])


# ---- the scanner reads >>IF too (#5648): a branch not taken is not source ----
_HEAD = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n"


def _program(*body: str) -> str:
    return _HEAD + "       WORKING-STORAGE SECTION.\n" + "\n".join(body) + "\n"


@pytest.mark.parametrize("free", [False, True])
def test_the_scanner_drops_a_copy_in_a_branch_not_taken(free):
    pad = "" if free else "       "
    src = _program(
        f"{pad}>>DEFINE TARGET AS 1",
        f"{pad}>>IF TARGET = 1",
        f"{pad}COPY ACTIVE.",
        f"{pad}>>ELSE",
        f"{pad}COPY DEAD.",
        f"{pad}>>END-IF",
        f"{pad}01 A PIC X.",
        f"{pad}COPY AFTER.",
    )
    out = extract_boundary("cobol", src)
    assert [c["member"] for c in out["section_copies"]] == ["ACTIVE"]
    # the line map is the identity: a fact keeps its line in the file
    assert [(r["name"], r["line"]) for r in out["records"]] == [("A", 11)]
    assert out["records"][0]["copy_members"] == "AFTER"


def test_the_scanner_drops_a_data_item_in_a_branch_not_taken_and_nesting_holds():
    src = _program(
        "       >>IF NOPE IS DEFINED",
        "       01 GONE PIC X.",
        "       >>IF NOPE IS NOT DEFINED",
        "       01 STILL-GONE PIC X.",
        "       >>END-IF",
        "       >>ELSE",
        "       01 KEPT PIC X.",
        "       >>END-IF",
    )
    assert [r["name"] for r in extract_boundary("cobol", src)["records"]] == ["KEPT"]


def test_active_source_keeps_offsets_and_is_unchanged_without_a_taken_decision():
    src = _program("       >>IF X IS DEFINED", "       01 A PIC X.", "       >>END-IF")
    out = active_source(src)
    assert len(out.split("\n")) == len(src.split("\n"))
    assert "01 A" not in out
    assert active_source("       01 A PIC X.\n") == "       01 A PIC X.\n"  # no directive
    # refused forms and a COPY member (no PROGRAM-ID) are returned whole: a scan never raises
    refused = _program("       >>IF X = 1", "       01 A PIC X.", "       >>END-IF")  # relation on an undefined name
    assert active_source(refused) == refused
    member = "      >>IF X IS DEFINED\n       01 A PIC X.\n      >>END-IF\n"
    assert active_source(member) == member
    assert [r["name"] for r in extract_boundary("cobol", member)["records"]] == ["A"]


def test_the_scanner_keeps_compiler_options_from_before_the_directives():
    src = "       CBL TRUNC(BIN)\n" + _program("       >>IF NOPE IS DEFINED", "       01 A PIC X.", "       >>END-IF")
    assert [r["option"] for r in extract_boundary("cobol", src)["compiler_options"]] == ["TRUNC"]
