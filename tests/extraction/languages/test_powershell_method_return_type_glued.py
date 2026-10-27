"""#3303: a PS class method whose return-type bracket is glued to the name.

`[string]ToString() {` (no space after `]`) is valid PowerShell and common in
build scripts; func_start and args required whitespace after the bracket and missed it.
The whole class: every return-type bracket shape x spacing x modifier.
"""

import pytest

from gitgalaxy.standards.language_standards.languages import powershell

_DEF = next(v for v in vars(powershell).values() if isinstance(v, dict) and "rules" in v)
FUNC_START = _DEF["rules"]["func_start"]
ARGS = _DEF["rules"]["args"]

TYPES = [
    "[string]",
    "[int]",
    "[array]",
    "[void]",
    "[System.Collections.Generic.List[string]]",
    "[Dictionary[string,int]]",
]
GAPS = ["", " ", "  ", "\t"]
MODS = ["", "hidden ", "static ", "hidden static "]


def _name(m):
    return next(g for g in m.groups() if g)


@pytest.mark.parametrize("mod", MODS)
@pytest.mark.parametrize("gap", GAPS)
@pytest.mark.parametrize("typ", TYPES)
def test_typed_method_found_with_any_gap(typ, gap, mod):
    src = f"class C {{\n    {mod}{typ}{gap}GetTests([string]$a) {{\n        return 1\n    }}\n}}\n"
    m = FUNC_START.search(src)
    assert m
    assert _name(m) == "GetTests"
    a = ARGS.search(src)
    assert a
    assert "([string]$a)" in a.group(0)


@pytest.mark.parametrize(
    "line", ["[int]$x = 1", "[string]$name", "[void]$null", "[Parameter(Mandatory)]", "[CmdletBinding()]\nparam("]
)
def test_glued_bracket_does_not_false_positive(line):
    assert [_name(m) for m in FUNC_START.finditer(line)] == []


@pytest.mark.parametrize("scope", ["global", "script", "local", "private"])
def test_scoped_functions_keep_bare_name(scope):
    m = FUNC_START.search(f"function {scope}:Write-Log\n{{\n}}\n")
    assert m
    assert _name(m) == "Write-Log"
