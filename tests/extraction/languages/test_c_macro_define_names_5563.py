"""#5563: a C/C++ macro-defined function is named from its `#define` -- the parameter pasted into the expanded
declarator (`Handler_ ## name` -> `name`), qualified by any other pasted parameter (`AF_##cls##_##name` ->
`cls::name`) -- whether the define is in the same file or in one of the scan's headers (the repo-wide table)."""

import contextlib
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from gitgalaxy.core import detector as det
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

LANGS = ("c", "cpp")

# eternity source/c_runcmd.h (shape only): the name is the FIRST argument, the second a flag or a variable.
CONSOLE_DEFINES = (
    "#define CONSOLE_COMMAND(name, flags) \\\n"
    "    static void Handler_ ## name(void); \\\n"
    "    static command_t Cmd_ ## name = { # name, ct_command, flags, nullptr, Handler_ ## name }; \\\n"
    "    static void Handler_ ## name(void)\n"
    "#define CONSOLE_VARIABLE(name, variable, flags) \\\n"
    "    static void Handler_ ## name(void); \\\n"
    "    static command_t Cmd_ ## name = { # name, ct_variable, flags, &var_ ## variable }; \\\n"
    "    static void Handler_ ## name(void)\n"
    "#define CONSOLE_NETVAR(name, variable, flags, netcmd) \\\n"
    "    static void Handler_ ## name(void); \\\n"
    "    static void Handler_ ## name(void)\n"
    "#define CONSOLE_CONST(name, variable) \\\n"
    "    static command_t Cmd_ ## name = { # name, ct_constant, 0, &var_ ## variable };\n"
)
CONSOLE_USES = (
    "CONSOLE_COMMAND(mn_episode, cf_notnet)\n{\n\tint x = 1;\n}\n"
    "CONSOLE_VARIABLE(sens_combined, mouseSensitivity_c, 0)\n{\n\tint x = 1;\n}\n"
    "CONSOLE_NETVAR(map, mapname, cf_server, netcmd_map)\n{\n\tint x = 1;\n}\n"
)
# gzdoom src/common/scripting/vm/vm.h (shape only): `cls` qualifies, `name` names.
ACTION_DEFINE = (
    "#define DEFINE_ACTION_FUNCTION(cls, name) \\\n"
    "\tstatic int AF_##cls##_##name(VM_ARGS); \\\n"
    "\tstatic const AFuncDesc cls##_##name##_Hook = { #cls, #name, AF_##cls##_##name }; \\\n"
    "\tstatic int AF_##cls##_##name(VM_ARGS)\n"
)
ACTION_USES = (
    "DEFINE_ACTION_FUNCTION(FCanvas, Clear)\n{\n\treturn 0;\n}\n"
    "DEFINE_ACTION_FUNCTION(DShape2D, Clear)\n{\n\treturn 0;\n}\n"
)


@contextlib.contextmanager
def _repo_table(header: str):
    saved = det._C_REPO_MACRO_ARGS
    det.set_c_repo_macro_args(det.c_repo_macro_name_args([header]))
    try:
        yield
    finally:
        det._C_REPO_MACRO_ARGS = saved


def _sliced_names(lang: str, code: str) -> list[str]:
    detector = det.StructuralExtractor(lang_id=lang, language_definitions=LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS[lang]["rules"]
    satellites, _ = detector._slice_by_braces(code=code, lang_id=lang, rules=rules, offset=0, spatial_map={})
    return [s["name"] if isinstance(s, dict) else s.name for s in satellites]


def test_the_define_table_reads_the_pasted_declarator():
    table = det.c_macro_name_args(CONSOLE_DEFINES + ACTION_DEFINE)
    assert table["CONSOLE_COMMAND"] == (0, ())
    assert table["CONSOLE_VARIABLE"] == (0, ())
    assert table["CONSOLE_NETVAR"] == (0, ())
    assert table["DEFINE_ACTION_FUNCTION"] == (1, (0,))
    assert "CONSOLE_CONST" not in table  # ends in `;`: a declaration, never followed by a body


@pytest.mark.parametrize(
    "define",
    [
        "#define F(a) do { a; } while (0)",  # a statement
        "#define F(a) ((a) > 0)",  # an expression
        "#define F(a) static void fixed_name(int a)",  # declarator pastes no parameter
        "#define F(a) static int x = a;",  # a declaration
    ],
)
def test_a_define_without_a_pasted_declarator_records_nothing(define):
    assert det.c_macro_name_args(define + "\n") == {}


def test_a_plain_parameter_declarator_names_the_function():
    assert det.c_macro_name_args("#define FUNC(a) static bool a(line_t *ln, int arg0)\n") == {"FUNC": (0, ())}


def test_disagreeing_variants_record_no_rule():
    ladder = "#if A\n#define F(a, b) void a(void)\n#else\n#define F(a, b) void b(void)\n#endif\n"
    assert det.c_macro_name_args(ladder) == {"F": None}
    assert det.c_repo_macro_name_args(["#define F(a, b) void a(void)\n", "#define F(a, b) void b(void)\n"]) == {
        "F": None
    }


@pytest.mark.parametrize("lang", LANGS)
def test_same_file_define_names_the_first_argument(lang):
    names = _sliced_names(lang, CONSOLE_DEFINES + CONSOLE_USES)
    assert {"mn_episode", "sens_combined", "map"} <= set(names)
    assert not {"cf_notnet", "mouseSensitivity_c", "mapname"} & set(names)


@pytest.mark.parametrize("lang", LANGS)
def test_header_define_names_a_definition_in_another_file(lang):
    with _repo_table(CONSOLE_DEFINES):
        names = _sliced_names(lang, CONSOLE_USES)
    assert {"mn_episode", "sens_combined", "map"} <= set(names)
    assert not {"cf_notnet", "mouseSensitivity_c", "mapname"} & set(names)


@pytest.mark.parametrize("lang", LANGS)
def test_the_class_qualifier_keeps_same_named_handlers_apart(lang):
    with _repo_table(ACTION_DEFINE):
        names = _sliced_names(lang, ACTION_USES)
    assert [n for n in names if n.endswith("Clear")] == ["FCanvas::Clear", "DShape2D::Clear"]


@pytest.mark.parametrize("lang", LANGS)
def test_this_files_define_wins_over_the_headers(lang):
    with _repo_table("#define CMD(a, b) void b(void)\n"):
        names = _sliced_names(lang, "#define CMD(a, b) void a(void)\nCMD(first, second)\n{\n\tint x = 1;\n}\n")
    assert "first" in names and "second" not in names


@pytest.mark.parametrize("lang", LANGS)
def test_no_define_keeps_the_invocation_rule(lang):
    with _repo_table(""):
        names = _sliced_names(lang, "CCMD(map)\n{\n\tint x = 1;\n}\nCUSTOM(Int, sv_x)\n{\n\tint x = 1;\n}\n")
    assert "map" in names and "sv_x" in names


@pytest.mark.parametrize("lang", LANGS)
def test_a_missing_naming_argument_keeps_the_invocation_rule(lang):
    with _repo_table("#define CMD(a, b, c) void Handler_##c(void)\n"):
        names = _sliced_names(lang, "CMD(first, second)\n{\n\tint x = 1;\n}\n")
    assert "second" in names


def test_the_scan_builds_the_table_from_its_headers_only(tmp_path):
    from gitgalaxy.galaxyscope import Orchestrator

    (tmp_path / "c_runcmd.h").write_text(CONSOLE_DEFINES)
    (tmp_path / "local.cpp").write_text("#define LOCAL(a, b) void a(void)\n")
    (tmp_path / "cached.hpp").write_text(ACTION_DEFINE)
    scope = SimpleNamespace(
        root=Path(tmp_path),
        stem_map={"c_runcmd.h": "c_runcmd.h", "local.cpp": "local.cpp", "gone.h": "gone.h"},
        ram_cache={"cached.hpp": {}},  # a delta scan's unchanged header still counts
        disk_paths={},
        _C_HEADER_EXTS=Orchestrator._C_HEADER_EXTS,
    )
    table = Orchestrator._c_repo_macro_args(scope)  # type: ignore[arg-type]
    assert table["CONSOLE_COMMAND"] == (0, ()) and table["DEFINE_ACTION_FUNCTION"] == (1, (0,))
    assert "LOCAL" not in table


def test_worker_init_installs_and_resets_the_table():
    from gitgalaxy.galaxyscope import _init_worker

    root_logger = logging.getLogger()
    saved, level = det._C_REPO_MACRO_ARGS, root_logger.level
    try:
        _init_worker(".", {}, {}, logging.WARNING, set(), set(), False, {"CMD": (0, ())})
        assert det._C_REPO_MACRO_ARGS == {"CMD": (0, ())}
        _init_worker(".", {}, {}, logging.WARNING, set(), set())
        assert det._C_REPO_MACRO_ARGS == {}
    finally:
        det._C_REPO_MACRO_ARGS = saved
        root_logger.setLevel(level)
