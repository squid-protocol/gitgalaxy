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


@pytest.mark.parametrize("clause", ["RpcExcept(1)", "RpcFinally"])
def test_a_windows_rpc_clause_macro_is_no_function_and_no_call(clause):
    """eternity i_midirpc.cpp: `RpcTryExcept { .. } RpcExcept(1) { .. } RpcEndExcept` expands to `__try .. __except`."""
    units = _units("cpp", _TRY % clause)
    assert list(units) == ["f"]
    assert units["f"]["calls_out_to"] == ["before", "handler", "after"]


@pytest.mark.parametrize("call", ["DLList_Reverse<>(&chains[i])", "reverse<>(&head)", "f<> (x)"])
def test_a_call_with_an_empty_template_argument_list_is_a_call(call):
    """eternity `DLList_Reverse<>(&head)`: every template argument deduced."""
    units = _units("cpp", "void g(int *head)\n{\n  before(head);\n  %s;\n}\n" % call)
    assert units["g"]["calls_out_to"] == ["before", call.split("<")[0]]


@pytest.mark.parametrize("name", ["EE_PLATFORM_TEST", "EE_TEST", "SomeTEST"])
def test_a_function_whose_name_holds_test_keeps_its_name(name):
    """eternity hal/i_platform.h: `inline bool EE_PLATFORM_TEST(int flags)` was named `int` (the gtest-macro rename)."""
    units = _units("cpp", "inline bool %s(int flags)\n{\n  return check(flags);\n}\n" % name)
    assert list(units) == [name]


@pytest.mark.parametrize("macro, unit", [("TEST(Suite, Name)", "Name"), ("TEST_F(Fixture, Case)", "Case")])
def test_a_test_macro_at_the_start_of_a_line_still_names_the_test(macro, unit):
    assert list(_units("cpp", "%s\n{\n  check();\n}\n" % macro)) == [unit]


@pytest.mark.parametrize("lang", ["c", "cpp", "objective-c"])
@pytest.mark.parametrize(
    "stmt",
    [
        '__asm__("nop");',
        '__asm__ __volatile__("movl %%fs : 4, %%eax": "=a"(top));',
        '__asm__ volatile ("nop");',
        "__asm__(\n    \"nop\"\n    : \"=a\"(top));",
    ],
)
def test_a_line_leading_gcc_asm_statement_does_not_cut_the_unit(lang, stmt):
    code = f"long f(int *p)\n{{\n  before(p);\n  {stmt}\n  after(p);\n  return 0;\n}}\nvoid g(void)\n{{\n  other();\n}}\n"
    units = _units(lang, code)
    assert list(units) == ["f", "g"]
    # the qualifier word (`volatile`) can still read as a call: only the unit's extent is pinned here
    calls = units["f"]["calls_out_to"]
    assert calls[0] == "before" and calls[-1] == "after"
    assert units["g"]["calls_out_to"] == ["other"]
