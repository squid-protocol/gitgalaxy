"""
#6266: a C# interpolated string's holes are code (helion: 45 call-graph misses, `DrawCounts -> Total` from
`$"Total: {counts.Total()}"`). The literal shield blanked the whole string, so no call in a hole reached `calls_out_to`.
"""

import pytest

from gitgalaxy.core.csharp_interpolation import expose_holes
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(body: str) -> list[str]:
    code = "class C\n{\n    void Run(int n)\n    {\n" + body + "\n    }\n}\n"
    functions = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == "Run")["calls_out_to"]


@pytest.mark.parametrize(
    "body, callee",
    [
        ('Log($"Total: {counts.Total()}");', "Total"),  # a member call in a hole
        ('Log($"x {GetPageCount()} y");', "GetPageCount"),  # a bare call in a hole
        ('Log($"{Math.Min(n, 9),4:####}");', "Min"),  # alignment and a format specifier after the call
        ('Log($"{ns.ToString().ToLower(Ci)}");', "ToLower"),  # a chain: every call in it
        ('Log($"a {{literal}} {Real()}");', "Real"),  # `{{` is a brace, the next hole is code
        ('Log($@"line one\n{Verbatim()}\nmore ""q"" {After()}");', "After"),  # verbatim interpolated
        ('Log(@$"{Verbatim()}");', "Verbatim"),  # `@$` order
        ('Log($"""\n  {Raw()}\n  """);', "Raw"),  # raw interpolated
        ('Log($"{Join(", ", xs)}");', "Join"),  # a plain string inside the hole
        ('Log($"{(n > 0 ? Pos() : Neg())}");', "Neg"),  # a ternary in parentheses: its `:` is not a format
        ('Log($"outer {Wrap($"inner {Deep()}")}");', "Deep"),  # an interpolated string inside a hole
        ("Log($\"{Pick('}')}\");", "Pick"),  # a `}` char literal does not close the hole
    ],
)
def test_call_in_an_interpolation_hole_is_a_call(body, callee):
    assert callee in _calls(body)


@pytest.mark.parametrize(
    "body, not_callee",
    [
        ('Log($"call Fake(x) here");', "Fake"),  # text outside a hole
        ('Log($"{{Fake()}}");', "Fake"),  # an escaped brace pair is text
        ('Log("{Fake()}");', "Fake"),  # a plain string has no holes
        ('Log($"{Real("Fake(x)")}");', "Fake"),  # a string inside a hole stays blanked
        ('Log(@"{Fake()}");', "Fake"),
        ('// $"{Fake()}"\n        Log(1);', "Fake"),  # a comment
        ('Log($"a" + "{Fake()}");', "Fake"),
    ],
)
def test_text_is_still_no_call(body, not_callee):
    assert not_callee not in _calls(body)


def test_expose_holes_leaves_text_without_interpolation_alone():
    src = 'var a = "x" + @"y" + \'$\'; // $"{f()}"\nint b = c$d;'
    assert expose_holes(src) == src


def test_expose_holes_keeps_the_newline_count():
    src = '$@"a\nb {f()}\nc"'
    assert expose_holes(src).count("\n") == src.count("\n")


def test_unterminated_string_does_not_hang():
    assert "f" in expose_holes('$"abc {f(')
    assert expose_holes('$"abc').startswith('""')


# `fixed (...) {` is a statement. It was read as a function named `fixed`, so every call after it (and the ones in its
# head) moved off the real method (helion: 14 misses, `Parse`, `UploadImage`, `GetWallVertices`).
def _units(code: str) -> dict[str, list[str]]:
    functions = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in functions}


@pytest.mark.parametrize(
    "stmt", ["fixed (uint* p = image.Pixels(1))", "fixed (byte* b = &a[0], c = &d[0])", "checked", "unchecked"]
)
def test_a_fixed_style_statement_is_no_function(stmt):
    body = f"        Before();\n        {stmt}\n        {{\n            Inside();\n        }}\n        After();\n"
    units = _units("class C\n{\n    public unsafe void Up(Image image)\n    {\n" + body + "    }\n}\n")
    assert list(units) == ["Up"]
    assert {"Before", "Inside", "After"} <= set(units["Up"])


def test_a_call_in_the_fixed_head_belongs_to_the_method():
    units = _units(
        "class C\n{\n    unsafe void Up()\n    {\n        fixed (uint* p = Pixels(1))\n        {\n        }\n    }\n}\n"
    )
    assert units == {"Up": ["Pixels"]}


def test_a_method_named_like_a_neighbour_of_fixed_still_matches():
    units = _units(
        "class C\n{\n    void Fixer()\n    {\n        Go();\n    }\n    void Checked2()\n    {\n        Go2();\n    }\n}\n"
    )
    assert list(units) == ["Fixer", "Checked2"]
