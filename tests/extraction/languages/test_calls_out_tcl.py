"""
Regression tests for Tcl call-graph extraction and namespace-qualified call resolution,
audited across the full `language-crucible/data/tcl` corpus.
"""

import sys
from pathlib import Path

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _func(code: str, fn_name: str) -> dict:
    units = StructuralExtractor("tcl", LANGUAGE_DEFINITIONS).splice(code, "test.tcl")["functions"]
    return next(u for u in units if u["name"] == fn_name or u["name"].rsplit("::", 1)[-1] == fn_name)


def _calls(code: str, fn_name: str = "run") -> list[str]:
    return _func(code, fn_name)["calls_out_to"]


def test_tcl_namespace_qualified_calls_emit_leaf_and_qualifier():
    code = (
        "proc run {p type} {\n"
        '    set msg [msgcat::mc "hello"]\n'
        "    portfetch::fetchfiles $p\n"
        "    set path [::fileutil::jail /tmp $p]\n"
        "    if {![::file exists $path]} {\n"
        "        set sum [portchecksum::calc_$type $path]\n"
        "    }\n"
        "}\n"
    )
    fn = _func(code, "run")
    calls = set(fn["calls_out_to"])
    assert {"mc", "fetchfiles", "jail", "file", "set"} <= calls
    assert not {"msgcat::mc", "portfetch::fetchfiles", "calc_"} & calls
    assert fn["calls_out_qualifiers"]["mc"] == ["::msgcat"]
    assert fn["calls_out_qualifiers"]["fetchfiles"] == ["::portfetch"]
    assert fn["calls_out_qualifiers"]["jail"] == ["::fileutil"]
    assert fn["calls_out_qualifiers"]["file"] == [""]
    assert _calls("proc probe_globals {} {\n    global region\n    ::env\n}\n", "probe_globals") == []


def test_tcl_quoted_command_substitutions_and_escapes():
    code = (
        "proc run {site distfile} {\n"
        '    ui_warn "[format [msgcat::mc "No mirror for %s"] $distfile]"\n'
        '    ui_msg "\\[$distfile\\] [file join /tmp $distfile]"\n'
        '    return "${site}[percent_encode ${distfile}]"\n'
        "}\n"
    )
    calls = set(_calls(code))
    assert {"ui_warn", "format", "mc", "ui_msg", "file", "percent_encode"} <= calls
    assert "distfile" not in calls


def test_tcl_multiline_quoted_string_with_escaped_brackets_is_shielded():
    code = (
        "proc test_eq {stmt val} {\n"
        '    uplevel 1 "\\\n'
        "        puts -nonewline {checking $stmt}\n"
        "        if {\\[catch {set actual $stmt}\\]} {\\n\\\n"
        '            puts \\"failed\\"\\n\\\n'
        "            exit 1\\n\\\n"
        '        }"\n'
        "}\n"
    )
    assert _calls(code, "test_eq") == ["uplevel"]


def test_tcl_proc_param_defaults_and_digit_names_are_not_calls():
    code = (
        'proc deactivate {name {version ""} {revision ""} {variants 0} {options ""}} {\n'
        "    ui_msg $name\n"
        "}\n"
        "proc portchecksum::calc_md5 {file} {\n"
        "    return [md5 file $file]\n"
        "}\n"
        "proc faultsim_save {args} { uplevel db_save $args }\n"
    )
    assert _calls(code, "deactivate") == ["ui_msg"]
    assert _calls(code, "portchecksum::calc_md5") == ["md5"]
    assert _calls(code, "faultsim_save") == ["uplevel"]


def test_tcl_backslash_line_continuations_and_semicolons():
    code = (
        "proc run {x} {\n"
        "    global UI_PREFIX destroot \\\n"
        "        applications_dir frameworks_dir \\\n"
        "        macportsuser\n"
        "    set a 1; helper_one $a; helper_two [get_val]\n"
        "}\n"
    )
    calls = set(_calls(code))
    assert {"set", "helper_one", "helper_two", "get_val"} <= calls
    assert not {"applications_dir", "macportsuser", "frameworks_dir"} & calls


def test_tcl_foreach_lmap_after_uplevel_set_and_regex_switch():
    code = (
        "proc run {items dep} {\n"
        "    foreach f [glob -nocomplain *.db] { forcedelete $f }\n"
        "    foreach op {\n"
        "        Seek SeekGE\n"
        "        NoConflict Next\n"
        "    } {\n"
        "        lappend ops $op\n"
        "    }\n"
        "    set cfg {\n"
        "        All-O0\n"
        "        All-Debug\n"
        "    }\n"
        "    set urls [lmap s $items {portfetch::assemble_url $s}]\n"
        "    after idle {bg_tick}\n"
        "    uplevel 1 {up_helper}\n"
        "    switch -regex $dep {\n"
        "        ^(lib|bin):([-A-Za-z0-9_/.]+):([-._A-Za-z0-9]+)$ {}\n"
        '        default { ui_error [format [msgcat::mc "bad: %s"] $dep] }\n'
        "    }\n"
        "}\n"
    )
    calls = set(_calls(code))
    assert {
        "glob",
        "forcedelete",
        "lappend",
        "set",
        "lmap",
        "assemble_url",
        "after",
        "bg_tick",
        "uplevel",
        "up_helper",
        "ui_error",
        "format",
        "mc",
    } <= calls
    assert not {"Seek", "NoConflict", "All-O0", "All-Debug", "default"} & calls


def test_tcl_namespace_qualified_call_resolution():
    ext = StructuralExtractor("tcl", LANGUAGE_DEFINITIONS)
    portfetch_code = "proc portfetch::fetchfiles {x} {\n    return $x\n}\n"
    receipt_flat_code = "proc installed {name} {\n    return $name\n}\n"
    receipt_sqlite_code = "proc installed {name} {\n    return $name\n}\n"
    reg_util_code = "namespace eval registry {\n    proc run_target {x} {\n        return $x\n    }\n}\n"
    caller_code = (
        "package require receipt_flat 1.0\n"
        "package require registry_util 2.0\n"
        "proc main {x} {\n"
        "    portfetch::fetchfiles $x\n"
        "    receipt_flat::installed $x\n"
        "    registry::run_target $x\n"
        "}\n"
    )
    files = {
        "portfetch.tcl": portfetch_code,
        "receipt_flat.tcl": receipt_flat_code,
        "receipt_sqlite.tcl": receipt_sqlite_code,
        "registry_util.tcl": reg_util_code,
        "caller.tcl": caller_code,
    }
    records = []
    for path, src in files.items():
        spliced = ext.splice(src, path)
        records.append(
            {
                "path": path,
                "lang_id": "tcl",
                "functions": spliced["functions"],
                "classes": spliced.get("classes", []),
            }
        )
    import_edges = [
        {"src": "caller.tcl", "dst": "receipt_flat.tcl", "edge_kind": "import"},
        {"src": "caller.tcl", "dst": "registry_util.tcl", "edge_kind": "import"},
    ]
    sites, _ = resolve_calls(records, import_edges)
    by_callee = {s["callee"]: s for s in sites if s["src_path"] == "caller.tcl"}
    assert by_callee["fetchfiles"]["dst_path"] == "portfetch.tcl"
    assert by_callee["fetchfiles"]["step"] == "qualified"
    assert by_callee["installed"]["dst_path"] == "receipt_flat.tcl"
    assert by_callee["installed"]["step"] == "import"
    assert by_callee["run_target"]["dst_path"] == "registry_util.tcl"
    assert by_callee["run_target"]["step"] == "import"


def test_tcl_calls_out_regex_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["tcl"]["rules"]["calls_out"]
    assert_redos_immune(pattern, "a::" * 10000 + "!")
    assert_redos_immune(pattern, "::" + "a-" * 10000 + ":")
    assert_redos_immune(pattern, "; " * 20000 + "x:")
