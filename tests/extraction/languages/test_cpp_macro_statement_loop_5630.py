"""
#5630: a C++ macro-statement loop or observer dispatch is a statement inside its function, never a function.

doomsday's `DE_FOR_EACH*(T, i, c)`, `DE_FOR_OBSERVERS(i, audience)` and `DE_NOTIFY*(Name, i)` take a body (a brace
block or one statement) like `for`. They were read as functions named for the macro, and the enclosing function lost
their body's calls. Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(code: str) -> dict[str, dict]:
    found = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in found}


@pytest.mark.parametrize(
    "stmt",
    [
        "DE_FOR_EACH_CONST(Map::Elements, i, dict.elements())\n    {\n        hit(i);\n    }",
        "DE_FOR_EACH(Lines, i, lines) { hit(*i); }",
        "DE_FOR_EACH_CONST_REVERSE(Mapping, i, mapping)\n        hit(i);",
        "DE_FOR_EACH_REVERSE(Mapping, i, mapping)\n    {\n        hit(i);\n    }",
        "DE_FOR_OBSERVERS(i, wd->self().audience())\n    {\n        hit(i);\n    }",
        "DE_NOTIFY_PUBLIC(Swap, i) { hit(i); }",
        "DE_NOTIFY_PUBLIC(Resize, i)\n    {\n        hit(i);\n    }",
        "DE_NOTIFY_PUBLIC_VAR(Change, i)\n    {\n        hit(i);\n    }",
        "DE_NOTIFY(Change, i) { hit(i); }",
        "DE_NOTIFY_VAR(Change, i)\n        hit(i);",
    ],
)
def test_a_macro_statement_is_not_a_function_and_its_body_stays_in_the_caller(stmt):
    functions = _functions(f"void run(Dict &d)\n{{\n    {stmt}\n}}\n")
    assert list(functions) == ["run"]
    assert "hit" in functions["run"]["calls_out_to"]


def test_a_function_named_like_a_macro_prefix_is_still_a_function():
    functions = _functions("void DE_NOTIFYfoo(int x)\n{\n    go(x);\n}\nvoid DE_FOR_EACHx(int x)\n{\n    go(x);\n}\n")
    assert {"DE_NOTIFYfoo", "DE_FOR_EACHx"} <= set(functions)
