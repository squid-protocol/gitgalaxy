"""#5648: >>DEFINE / >>IF / >>ELSE / >>END-IF live in core.cobol_conditional; the translator's reader consumes them."""

from __future__ import annotations

from decimal import Decimal

import pytest

from gitgalaxy.core.cobol_conditional import Conditional, ConditionalCompilation, options_defines
from gitgalaxy.core.compiler_options import compiler_options
from gitgalaxy.tools.cobol_to_java.det.source import logical_lines


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
    assert kept(src, {"X": Decimal(1)}) == ["a", "e"]


def test_option_beats_the_directive_unless_override_and_parameter_reads_the_option():
    src = [
        ">>DEFINE V AS 1",
        ">>IF V = 9",
        "nine",
        ">>END-IF",
        ">>DEFINE W AS 1 OVERRIDE",
        ">>IF W = 1",
        "one",
        ">>END-IF",
    ]
    assert kept(src, {"V": Decimal(9), "W": Decimal(7)}) == ["nine", "one"]
    assert kept([">>DEFINE P AS PARAMETER", ">>IF P = 'Z'", "z", ">>END-IF"], {"P": "Z"}) == ["z"]


@pytest.mark.parametrize(
    "src",
    [
        [">>ELSE"],
        [">>END-IF"],
        [">>IF A DEFINED", "x"],  # left open
        [">>IF A = 1", ">>END-IF"],  # relation on an undefined name
        [">>DEFINE A AS 1", ">>IF A = 'x'", ">>END-IF"],  # numeric against alphanumeric
        [">>DEFINE A AS PARAMETER"],  # no option value
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
    assert [ln.line for ln in logical_lines(raw, "P.cbl")] == [2, 4, 10]


def test_logical_lines_free_format_and_unterminated_if_names_its_file():
    raw = ["       >>SOURCE FORMAT FREE", ">>DEFINE A AS 1", ">>IF A = 2", "no", ">>ELSE", "yes", ">>END-IF"]
    assert [ln.text.strip() for ln in logical_lines(raw, "/x/P.cbl")] == ["yes"]
    with pytest.raises(ConditionalCompilation, match=r"P\.cbl"):
        logical_lines(["      >>IF A DEFINED", "       X."], "/x/P.cbl")
