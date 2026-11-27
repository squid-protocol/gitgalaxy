"""SOP-002-v1 gap-cell decoy suite for Lua (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers the code-stream families that had no decoy row before this suite: immutability_locks,
import, scientific (positive controls, comment forms, boundaries, negatives). `decorators` and
`generics` also had none but their rules only read EmmyLua `---@` lines, which are comments, so
they cannot fire on authentic code (#9450): they get no baseline row and a strict-xfail control.
Every check runs through the real Prism.split_streams() + StructuralExtractor.splice() pipeline.
Measurement only: no rule or engine change.

Lua comment forms (Lua 5.4 manual, 3.1): `--` line comment (own line, trailing, `---` doc form),
`--[[ ... ]]` long comment, and leveled long comments `--[=[ ... ]=]`, `--[==[ ... ]==]`: a
closer only closes a comment of the same level, and long comments do not nest. A `[[ ... ]]`
long string is a string, so a keyword inside it counts today (strings count by design, #2535).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import family_decoy_runner as fdr
import family_validity_chart as fvc

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor("lua", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
_ISSUES = "https://github.com/squid-protocol/gitgalaxy/issues/"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "lua")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


def _xf(issue: int | None) -> list:
    """A strict xfail naming the issue, or no mark when the behaviour is correct."""
    if issue is None:
        return []
    return [pytest.mark.xfail(strict=True, reason=f"{_ISSUES}{issue}")]


ISSUE_LEVELED_LONG_COMMENT = 9449  # multi-line --[=[ ... ]=] comments leak
ISSUE_EMMY_DEAD = 9450  # decorators / generics only read ---@ lines, which are comments

# Authentic positive control per family (Req C).
LUA_FAMILIES: dict[str, str] = {
    "immutability_locks": "local max_retries <const> = 3",
    "import": "local json = require('json')",
    "scientific": "local rounded = math.floor(value)",
}

# decorators / generics: no authentic snippet fires the rule (#9450), so no baseline row.
DEAD_CELLS: dict[str, str] = {
    "decorators": "---@class Account",
    "generics": "---@generic T",
}

BRANCH_POSITIVES: dict[str, dict[str, str]] = {
    "immutability_locks": {"<const>": "local max_retries <const> = 3"},
    "import": {
        "require": "local json = require('json')",
        "dofile": "dofile('setup.lua')",
    },
    "scientific": {
        "math.x": "local rounded = math.floor(value)",
        "bit32.x": "local masked = bit32.band(flags, 0xff)",
        "<<": "local shifted = flags << 2",
        ">>": "local shifted = flags >> 2",
        "//": "local half = total // 2",
    },
}


def test_lua_covers_the_gap_families_and_they_are_defined():
    families, _, defined = fvc.engine_grid()
    code_stream = (defined["lua"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(LUA_FAMILIES) | set(DEAD_CELLS) <= code_stream
    assert set(BRANCH_POSITIVES) == set(LUA_FAMILIES)


def test_lua_baseline_has_a_sop002_row_for_every_covered_family_and_none_for_dead_cells():
    rows = json.loads(_BASELINE.read_text())["decoys"]["lua"]
    for family in LUA_FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family
        assert rows[family]["corpus"] == "decoy-spec", family
    for family in DEAD_CELLS:
        assert family not in rows


@pytest.mark.parametrize(("family", "src"), sorted(LUA_FAMILIES.items()))
def test_lua_positive_control_fires(family: str, src: str):
    # G1 (Req C)
    assert _hits(family, src + "\n") >= 1, f"G1 positive control failed for lua.{family}: {src!r}"


@pytest.mark.parametrize(
    ("family", "branch", "src"),
    [(f, b, s) for f, branches in sorted(BRANCH_POSITIVES.items()) for b, s in branches.items()],
)
def test_lua_every_rule_branch_fires(family: str, branch: str, src: str):
    assert _hits(family, src + "\n") >= 1, f"lua.{family} branch {branch!r} is dead for {src!r}"


@pytest.mark.xfail(strict=True, reason=f"{_ISSUES}{ISSUE_EMMY_DEAD}")
@pytest.mark.parametrize(("family", "src"), sorted(DEAD_CELLS.items()))
def test_lua_emmylua_annotation_positive_control_is_dead(family: str, src: str):
    """Req C: an authentic EmmyLua annotation must fire decorators / generics; it cannot today (#9450)."""
    assert _hits(family, src + "\n") >= 1


# ---------------------------------------------------------------------------------------------
# G2 (Req A): every Lua comment form. {s} is the family's positive-control snippet.
# ---------------------------------------------------------------------------------------------
_COMMENT_FORMS: list[tuple[str, str, int | None]] = [
    ("line_comment", "-- {s}\n", None),
    ("indented_line_comment", "    -- {s}\n", None),
    ("trailing_comment", "local a = 1 -- {s}\n", None),
    ("doc_comment_three_dashes", "--- {s}\n", None),
    ("line_comment_after_bracket", "--[ {s}\n", None),
    ("long_comment_single_line", "--[[ {s} ]]\n", None),
    ("long_comment_multi_line", "--[[\n{s}\n]]\n", None),
    ("long_comment_inline_in_code", "local a = --[[ {s} ]] 1\n", None),
    ("long_comment_then_code", "--[[\nnote\n{s}\n]]\nlocal a = 1\n", None),
    ("level1_single_line", "--[=[ {s} ]=]\n", None),
    ("level2_single_line", "--[==[ {s} ]==]\n", None),
    ("level1_multi_line", "--[=[\n{s}\n]=]\n", ISSUE_LEVELED_LONG_COMMENT),
    ("level2_multi_line", "--[==[\n{s}\n]==]\n", ISSUE_LEVELED_LONG_COMMENT),
    ("level3_multi_line", "--[===[\n{s}\n]===]\n", ISSUE_LEVELED_LONG_COMMENT),
    ("level2_with_short_closer_inside", "--[==[\n]] {s}\n]==]\n", ISSUE_LEVELED_LONG_COMMENT),
    ("level1_after_code", "local a = 1 --[=[\n{s}\n]=]\nlocal b = 2\n", ISSUE_LEVELED_LONG_COMMENT),
]


def _comment_params():
    for family in sorted(LUA_FAMILIES):
        for form, template, issue in _COMMENT_FORMS:
            yield pytest.param(family, form, template, marks=_xf(issue), id=f"{family}-{form}")


@pytest.mark.parametrize(("family", "form", "template"), list(_comment_params()))
def test_lua_comment_forms_hide_the_keyword(family: str, form: str, template: str):
    assert _hits(family, template.format(s=LUA_FAMILIES[family])) == 0, f"{form} leak for lua.{family}"


@pytest.mark.parametrize("family", sorted(LUA_FAMILIES))
def test_lua_long_comments_do_not_nest(family: str):
    """Spec: the first `]]` closes the comment, so text after it is code again (no nesting)."""
    assert _hits(family, "--[[ outer --[[ inner ]] " + LUA_FAMILIES[family] + " ]]\n") >= 1


@pytest.mark.parametrize("family", sorted(LUA_FAMILIES))
def test_lua_long_string_body_is_a_string_and_counts_today(family: str):
    """A `[[ ... ]]` long string is a string, not a comment (strings count by design, #2535). Recorded only."""
    assert _hits(family, "local s = [[\n" + LUA_FAMILIES[family] + "\n]]\n") >= 1


# ---------------------------------------------------------------------------------------------
# G6: strings.
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("family", sorted(LUA_FAMILIES))
def test_lua_keyword_in_a_string_counts_today(family: str):
    assert _hits(family, 'local s = "' + LUA_FAMILIES[family] + '"\n') >= 1


_STRING_PREFIXES = [
    ('local u = "x:y"', "plain"),
    ('local u = "a \\" b"', "escaped_dq"),
    ("local u = 'it\\'s'", "escaped_sq"),
    ('local u = "a -- b"', "dashes_in_string"),
    ('local u = "[[ not a long string"', "bracket_in_string"),
]


@pytest.mark.parametrize("family", sorted(LUA_FAMILIES))
@pytest.mark.parametrize(("prefix", "case"), _STRING_PREFIXES, ids=[c for _, c in _STRING_PREFIXES])
def test_lua_string_then_comment_boundary(family: str, prefix: str, case: str):
    assert _hits(family, f"{prefix} -- {LUA_FAMILIES[family]}\n") == 0


@pytest.mark.parametrize("family", ["immutability_locks", "import"])
def test_lua_url_string_then_comment_boundary(family: str):
    assert _hits(family, 'local u = "http://x" -- ' + LUA_FAMILIES[family] + "\n") == 0


def test_lua_scientific_url_double_slash_in_a_string_counts_today():
    """`//` is a scientific branch (floor division); inside a URL string it counts today (#2535)."""
    assert _hits("scientific", 'local u = "http://x"\n') >= 1
    assert _hits("scientific", 'local u = "http://x" -- note\n') == 1


@pytest.mark.parametrize("family", sorted(LUA_FAMILIES))
def test_lua_dashes_inside_a_string_do_not_start_a_comment(family: str):
    assert _hits(family, 'local u = "a -- b"; ' + LUA_FAMILIES[family] + "\n") >= 1


# ---------------------------------------------------------------------------------------------
# G5 (Req B): every alternation branch embedded in a longer identifier must not count.
# ---------------------------------------------------------------------------------------------
_BOUNDARY: list[tuple[str, str]] = [
    ("immutability_locks", "local max_retries <consts> = 3"),
    ("immutability_locks", "local max_retries <my_const> = 3"),
    ("immutability_locks", "local max_retries <constant> = 3"),
    ("import", "local json = my_require('json')"),
    ("import", "local json = requires('json')"),
    ("import", "local json = required_module('json')"),
    ("import", "my_dofile('setup.lua')"),
    ("import", "dofiles('setup.lua')"),
    ("scientific", "local rounded = mymath.floor(value)"),
    ("scientific", "local rounded = my_math.floor(value)"),
    ("scientific", "local rounded = mathx.floor(value)"),
    ("scientific", "local masked = mybit32.band(flags, 255)"),
    ("scientific", "local masked = my_bit32.band(flags, 255)"),
    ("scientific", "local masked = bit32x.band(flags, 255)"),
]


@pytest.mark.parametrize(("family", "src"), _BOUNDARY)
def test_lua_identifier_boundaries(family: str, src: str):
    assert _hits(family, src + "\n") == 0


# ---------------------------------------------------------------------------------------------
# Req D: negative controls from the contracts and the validity checklist.
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("family", "src"),
    [
        # immutability_locks: only a `<const>` attribute locks a binding; `<close>` and a plain local do not
        ("immutability_locks", "local handle <close> = io.open('data.txt')"),
        ("immutability_locks", "local max_retries = 3"),
        ("immutability_locks", "if a < b and c > d then end"),
        # import: a computed path, a rebinding of `require`, and a path setting are not a literal import
        ("import", "local mod = require(name)"),
        ("import", "local require = require"),
        ("import", "package.path = 'lib/?.lua;' .. package.path"),
        # scientific: other standard libraries, ordinary division and comparison are not numeric-library calls
        ("scientific", "local m = math"),
        ("scientific", "local label = string.format('%d', value)"),
        ("scientific", "local joined = table.concat(parts)"),
        ("scientific", "local ratio = total / count"),
        ("scientific", "if a <= b and c >= d then end"),
    ],
)
def test_lua_cross_family_negative_controls(family: str, src: str):
    assert _hits(family, src + "\n") == 0
