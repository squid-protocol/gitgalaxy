"""#5631: C# constructor initializers (`: base(...)` / `: this(...)`) never start a function."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FUNC_START = LANGUAGE_DEFINITIONS["csharp"]["rules"]["func_start"]


def _names(src):
    return [m.group(m.lastindex) for m in FUNC_START.finditer(src)]


SHAPES = {
    "continuation_base": "public Menu(IWindow w, int n) :\n    base(w, n, 6, true)\n{\n    Run();\n}\n",
    "continuation_this": "public Menu(IWindow w) :\n    this(w, 0)\n{\n    Run();\n}\n",
    "same_line_base": "public Menu(IWindow w) : base(w)\n{\n    Run();\n}\n",
    "same_line_this": "public Menu(IWindow w) : this(w, 0)\n{\n    Run();\n}\n",
    "colon_on_next_line": "public Menu(IWindow w)\n    : base(w)\n{\n    Run();\n}\n",
    "generic_args": "public Menu(IWindow w) :\n    base(new List<int>(), Foo<int, string>(w))\n{\n    Run();\n}\n",
    "named_args": "public Menu(IWindow w) :\n    base(window: w, count: 6)\n{\n    Run();\n}\n",
    "expression_body": "public Menu(IWindow w) :\n    base(w) => Run();\n",
    "indented_continuation": "    internal Menu(IWindow w, int n) :\n        this(w,\n             n)\n    {\n        Run();\n    }\n",
}


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_initializer_is_not_a_function(name):
    names = _names(SHAPES[name])
    assert "base" not in names and "this" not in names
    assert names == ["Menu"]


def test_constructor_keeps_body_and_neighbours():
    src = SHAPES["continuation_base"] + "public void Go()\n{\n    Run();\n}\n"
    assert _names(src) == ["Menu", "Go"]
    # the constructor match still ends at its own signature so the body belongs to it
    m = next(FUNC_START.finditer(src))
    assert m.group(m.lastindex) == "Menu" and src[m.end() :].lstrip().startswith("IWindow")


def test_real_function_named_with_base_prefix_still_matches():
    assert _names("public void baseline(int x)\n{\n}\n") == ["baseline"]
    assert _names("Foo()\n{\n}\n") == ["Foo"]
