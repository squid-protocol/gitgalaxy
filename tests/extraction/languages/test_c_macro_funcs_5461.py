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
    ("src", "expected"),
    [
        # The identifier is the FIRST argument (the second is a type, a value or a class).
        ("DEFINE_PROPERTY(accuracy, I, Actor)\n{\n}\n", ["accuracy"]),
        ("DEFINE_PROPERTY(skip_super, 0, Actor) {\n}\n", ["skip_super"]),
        ("DEFINE_CLASS_PROPERTY(ammogive, I, Weapon)\n{\n}\n", ["ammogive"]),
        ("DEFINE_INFO_PROPERTY(game, S, Actor) {\n}\n", ["game"]),
        ("DEFINE_MAP_OPTION(aircontrol, true)\n{\n}\n", ["aircontrol"]),
        ("DEFINE_MAP_OPTION(brightfog, false) { }\n", ["brightfog"]),
        # A prefix form is `prefix, name, Type, Class`: the general rule (the second) is already right.
        ("DEFINE_CLASS_PROPERTY_PREFIX(armor, maxbonus, I, BasicArmorBonus)\n{\n}\n", ["maxbonus"]),
        # Neighbours of the first-argument names keep the general rule.
        ("DEFINE_ACTION_FUNCTION_NATIVE(_CVar, SaveConfig, SaveConfig) {\n}\n", ["SaveConfig"]),
        ("DEFINE_PROPERTYKEY(SDL_KEY, 0X3F8A, 0X7C5, 10);\n", []),
    ],
)
def test_macros_that_name_their_first_argument(lang, src, expected):
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


def _sliced_names(lang: str, code: str) -> list[str]:
    from gitgalaxy.core.detector import StructuralExtractor

    detector = StructuralExtractor(lang_id=lang, language_definitions=LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS[lang]["rules"]
    satellites, _ = detector._slice_by_braces(code=code, lang_id=lang, rules=rules, offset=0, spatial_map={})
    return [s["name"] if isinstance(s, dict) else s.name for s in satellites]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize(
    "define",
    [
        "#define FUNC(a) static bool a(line_t *ln, int arg0)",  # odamex
        "#define FUNC(a) \\\n\tstatic bool a(line_t *ln, \\\n\t\tint arg0)",  # continued lines
        "#define FUNC(a) bool Handler_##a(int x)",  # token-pasted name
    ],
)
def test_define_that_expands_to_a_signature_makes_the_invocation_a_function(lang, define):
    code = define + "\n\nFUNC(LS_Door_Open)\n{\n\tint x = 1;\n}\n"
    assert any(n.endswith("LS_Door_Open") for n in _sliced_names(lang, code))


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize(
    "define",
    [
        "#define FUNC(a) do { a; } while (0)",
        "#define FUNC(a) case a:",
        "#define FUNC(a) while (a)",
        "#define FUNC(a) ((a) > 0)",
        "#define FUNC(a) \\\n\tdo { \\\n\t\ta; \\\n\t} while (0)",
    ],
)
def test_define_that_expands_to_a_statement_or_expression_is_not_a_function(lang, define):
    code = define + "\n\nFUNC(LS_Door_Open)\n{\n\tint x = 1;\n}\n"
    assert not any("LS_Door_Open" in n for n in _sliced_names(lang, code))


@pytest.mark.parametrize("lang", LANGS)
def test_macro_without_an_in_tree_define_keeps_the_invocation_rule(lang):
    code = "CCMD(map)\n{\n\tint x = 1;\n}\n"
    assert any("map" in n for n in _sliced_names(lang, code))


@pytest.mark.parametrize("lang", LANGS)
def test_one_signature_variant_among_several_defines_keeps_the_function(lang):
    code = (
        "#if USE_STMT\n#define FUNC(a) do { a; } while (0)\n#else\n#define FUNC(a) static bool a(int x)\n#endif\n"
        "FUNC(LS_Door_Open)\n{\n\tint x = 1;\n}\n"
    )
    assert any("LS_Door_Open" in n for n in _sliced_names(lang, code))
