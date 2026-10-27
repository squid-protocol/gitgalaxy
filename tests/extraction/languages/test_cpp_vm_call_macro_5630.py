"""
#5630: a gzdoom scripting-call macro (`IFVM`, `IFVIRTUAL*`, `IFOVERRIDENVIRTUALPTRNAME`) opens a block like `if`: it is a
statement inside its function, never a function. It was read as a function named for the macro, and the enclosing
function lost the calls in the block (`VMCall`, `IntAt`, `Destroy`). Driven through `StructuralExtractor.splice()`.
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
        'IFVM(PlayerPawn, BringUpWeapon)\n    {\n        hit(1);\n    }',
        'IFVIRTUAL(DObject, Tick)\n    {\n        hit(1);\n    }',
        'IFVIRTUALPTR(act, AActor, Tick) { hit(1); }',
        'IFVIRTUALPTRNAME(act, "SectorAction", TriggerAction)\n        {\n            hit(1);\n        }',
        'IFOVERRIDENVIRTUALPTRNAME(act, NAME_Cls, Fn)\n    {\n        hit(1);\n    }',
    ],
)
def test_a_vm_call_macro_is_not_a_function_and_its_body_stays_in_the_caller(stmt):
    functions = _functions(f"bool run(AActor *act)\n{{\n    {stmt}\n    return false;\n}}\n")
    assert list(functions) == ["run"]
    assert "hit" in functions["run"]["calls_out_to"]


def test_a_function_named_like_a_vm_call_macro_prefix_is_still_a_function():
    functions = _functions("void IFVMx(int x)\n{\n    go(x);\n}\nvoid IFVIRTUALS(int x)\n{\n    go(x);\n}\n")
    assert {"IFVMx", "IFVIRTUALS"} <= set(functions)


@pytest.mark.parametrize(
    "stmt",
    [
        "MOODYCAMEL_CONSTEXPR_IF (N != 0) {\n        hit(1);\n    }",
        "MOODYCAMEL_CONSTEXPR_IF (N == 0) return hit(1);",
        "MOODYCAMEL_TRY {\n        a();\n    } MOODYCAMEL_CATCH (...) {\n        hit(1);\n    }",
    ],
)
def test_a_moodycamel_if_macro_is_not_a_function_and_its_body_stays_in_the_caller(stmt):
    functions = _functions(f"bool run(int x)\n{{\n    {stmt}\n    return false;\n}}\n")
    assert list(functions) == ["run"]
    assert "hit" in functions["run"]["calls_out_to"]
