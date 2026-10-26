"""
#5630: a C++ macro class head is one unit named for its first macro, and a base-class-list entry is never a function.

doomsday writes private implementations as `DE_PIMPL(X),\nDE_OBSERVES(A, B)\n{ ... }`. The unit started at the last
`DE_OBSERVES(...)` line, named for it (`Change`, `Deletion`), and a `class C : public B,\n    DE_OBSERVES(A, B)\n{` base
list was read as a function named `DE_OBSERVES`. Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(code: str) -> dict[str, dict]:
    found = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in found}


@pytest.mark.parametrize(
    "head",
    [
        "DE_PIMPL(W)",
        "DE_GUI_PIMPL(W),\nDE_OBSERVES(App, Start)",
        "DE_PIMPL(W),\nDE_OBSERVES(Variable, Deletion),\nDE_OBSERVES(Variable, Change  )",
        "DE_PIMPL_NOREF(W),\n    DE_OBSERVES(A, B)",
    ],
)
def test_a_macro_class_chain_is_one_unit_named_for_its_first_macro(head):
    functions = _functions(f"{head}\n{{\n    Impl(Public *i) : Base(i)\n    {{\n        first();\n    }}\n}}\n")
    macro = head.split("(")[0]
    assert macro in functions
    assert {"Change", "Deletion", "DE_OBSERVES"}.isdisjoint(functions)
    assert "first" in functions["Impl"]["calls_out_to"]


@pytest.mark.parametrize(
    "head",
    [
        "class RefValue : public Value,\n                  DE_OBSERVES(Variable, Deletion)",
        "struct Item : public Base,\n    DE_OBSERVES(A, B),\n    DE_OBSERVES(C, D)",
        "class G : public P<T>, \r\n    DE_OBSERVES(Atlas, Reposition)",
    ],
)
def test_a_base_list_entry_is_not_a_function(head):
    functions = _functions(f"{head}\n{{\npublic:\n    bool isValid() const;\n}};\n")
    assert "DE_OBSERVES" not in functions


def test_a_comma_expression_statement_before_a_definition_still_finds_it():
    functions = _functions("int a = f(1),\n    b = 2;\nvoid run()\n{\n    go();\n}\n")
    assert functions["run"]["calls_out_to"] == ["go"]
