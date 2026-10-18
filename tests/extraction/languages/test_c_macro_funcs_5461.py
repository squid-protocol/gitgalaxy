"""#5461: C/C++ function-defining macros (`CCMD(map) {`, `DEFINE_ACTION_FUNCTION(AActor, A_Look) {`,
gtest `TEST(Suite, Name) {`, odamex `FUNC(LS_Door_Open) {`) are recorded as functions named by the
identifier argument: the only argument, or the second of several."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

LANGS = ("c", "cpp")


def _names(lang: str, src: str) -> list[str]:
    rule = LANGUAGE_DEFINITIONS[lang]["rules"]["func_start"]
    return [m.group(m.lastindex) for m in rule.finditer(src)]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("DEFINE_ACTION_FUNCTION(AActor, A_Look)\n{\n}\n", ["A_Look"]),
        ("DEFINE_ACTION_FUNCTION_NATIVE(AActor, A_Chase, AF_Chase) {\n}\n", ["A_Chase"]),
        ("CCMD(map) {\n}\n", ["map"]),
        ("CUSTOM_CVAR(Int, sv_x, 0, CVAR_ARCHIVE | CVAR_NOSET) { }\n", ["sv_x"]),
        ("TEST(Suite, Name) { }\nTEST_F(Fixture, Case) { }\n", ["Name", "Case"]),
        ("FUNC(LS_Door_Open)\n{\n}\n", ["LS_Door_Open"]),
        ("BEGIN_COMMAND(kill)\n{\n}\n", ["kill"]),
    ],
)
def test_macro_defined_function_is_named_by_its_identifier_argument(lang, src, expected):
    assert _names(lang, src) == expected


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize(
    "src",
    [
        "IF(x) {\n}\n",
        "BEGIN(a) {\n",
        "ASSERT(a) {\n",
        "EXPECT_EQ(f(1), 2) {\n",  # nested call: not a plain identifier argument
        "FOO(a + b) {\n",
        "FOO(a);\n{\n}\n",  # a statement, not a definition
        "if (X(y)) {\n}\n",
    ],
)
def test_macro_branch_does_not_fire_on_control_flow_or_calls(lang, src):
    assert not [n for n in _names(lang, src) if n in ("a", "y", "x", "b")]


@pytest.mark.parametrize("lang", LANGS)
def test_ordinary_function_still_named_by_the_generic_branch(lang):
    assert _names(lang, "static int real_fn(int a) {\n}\n") == ["real_fn"]


def test_class_like_macro_keeps_out_of_the_macro_branch():
    assert _names("c", "DE_PIMPL(Foo)\n{\n};\nDE_PIMPL_NOREF(Bar) {\n};\n") == []


@pytest.mark.parametrize("lang", LANGS)
def test_macro_branch_is_redos_immune(lang):
    rule = LANGUAGE_DEFINITIONS[lang]["rules"]["func_start"]
    assert_redos_immune(rule, "MACRO(" + "a, " * 5000 + "\n", timeout_sec=3.0)
    assert_redos_immune(rule, "MACRO(" + "a" * 20000, timeout_sec=3.0)
    assert_redos_immune(rule, "FOO(a)" + " \n" * 20000, timeout_sec=3.0)


@pytest.mark.parametrize("lang", LANGS)
def test_module_binder_macro_does_not_name_its_variable(lang):
    # `NB_MODULE(name, m) {`: `m` is the module variable, not the function's name.
    assert "m" not in _names(lang, "NB_MODULE(stablehlo_extension, m) { f(m); }\n")


@pytest.mark.parametrize("lang", LANGS)
def test_indented_statement_macro_inside_a_body_is_not_a_function(lang):
    # godot gdscript_vm.cpp: `OPCODE(m_op)` expands to `case m_op:`, `OPCODE_WHILE(m_test)` to `while`.
    src = "void run() {\n\tOPCODE_WHILE(true) {\n\t\tOPCODE(OPCODE_JUMP) {\n\t\t}\n\t}\n}\n"
    names = _names(lang, src)
    assert "true" not in names and "OPCODE_JUMP" not in names
