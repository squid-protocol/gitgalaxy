"""
#6266: an MSVC structured-exception `__except (filter) {` / `__finally {` clause is no function.

srb2 `win_dbg.c` `RecordExceptionInfo` wraps its stack dump in `__try { ... __except(EXCEPTION_EXECUTE_HANDLER) { ... } }`.
The handler read as a nested function named `__except`, which cut the enclosing unit short and moved the handler's
calls (`FPrintf`) out of it. An MSVC `__asm { ... }` block inside the `__try` must not cut it either.
Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(lang: str, code: str) -> dict:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


_TRY = "void f(int *p)\n{\n  __try\n  {\n    before(p);\n  }\n  %s\n  {\n    handler(p);\n  }\n  after(p);\n}\n"


@pytest.mark.parametrize("lang", ["c", "cpp"])
@pytest.mark.parametrize("clause", ["__except(EXCEPTION_EXECUTE_HANDLER)", "__except (EXCEPTION_CONTINUE_SEARCH)", "__finally"])
def test_a_seh_clause_is_no_function_and_its_calls_stay_in_the_enclosing_one(lang, clause):
    units = _units(lang, _TRY % clause)
    assert list(units) == ["f"]
    assert units["f"]["calls_out_to"] == ["before", "handler", "after"]


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_an_msvc_asm_block_inside_a_try_does_not_cut_the_unit(lang):
    code = (
        "void f(int *p)\n{\n  __try\n  {\n    __asm\n    {\n      mov eax, fs:[4]\n      mov top, eax\n    }\n"
        "    inside(p);\n  }\n  __except(EXCEPTION_EXECUTE_HANDLER)\n  {\n    handler(p);\n  }\n}\n"
        "void g(void)\n{\n  other();\n}\n"
    )
    units = _units(lang, code)
    assert list(units) == ["f", "g"]
    assert units["f"]["calls_out_to"] == ["inside", "handler"]
    assert units["g"]["start_line"] == 17


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_a_function_named_like_a_seh_keyword_prefix_is_still_a_function(lang):
    units = _units(lang, "int __except_count(void)\n{\n  return 0;\n}\nint finally_done(void)\n{\n  return 1;\n}\n")
    assert list(units) == ["__except_count", "finally_done"]
