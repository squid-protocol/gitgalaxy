"""#8161 (X4): C and C++ calls see what the translation unit includes, transitively, and a C `static`
function is visible only to its own file (and files that #include it). A header's paired source file
(`api.h` -> `api.c` beside it; in C++ also the repo's only `format.cc` for `include/fmt/format.h`) is
visible one hop past the header, so a call through the header reaches the body."""

import pytest

from gitgalaxy.core.call_resolver import C_STATIC_SHAPE, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _sites(lang: str, files: dict[str, str], includes: list[tuple[str, str]]):
    parsed_files = []
    for path, code in files.items():
        parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
        parsed_files.append({"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": []})
    sites, _ = resolve_calls(parsed_files, [{"src": a, "dst": b} for a, b in includes])
    return {(s["src_name"], s["callee"]): (s["step"], s["dst_path"]) for s in sites}


@pytest.mark.parametrize(
    ("code", "static"),
    [
        ("static int f(void) {\n  return 1;\n}\n", True),
        ("static inline void *\nf(int n) {\n  return 0;\n}\n", True),
        ("static\nint f(int x)\n{\n  return x;\n}\n", True),
        ("int f(void) {\n  return 1;\n}\n", False),
        ("int f(void) {\n  static int n = 0;\n  return n;\n}\n", False),
    ],
)
def test_a_static_definition_is_marked(code, static):
    (unit,) = StructuralExtractor("c", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert (unit.get("def_shape") == C_STATIC_SHAPE) is static


def test_another_files_static_is_no_candidate():
    files = {
        "a.c": "static int helper(void) {\n  return 1;\n}\nint caller_a(void) {\n  return helper();\n}\n",
        "b.c": "static int helper(void) {\n  return 2;\n}\n",
        "c.c": "int caller_c(void) {\n  return helper();\n}\n",
        "d.c": "int helper(void) {\n  return 3;\n}\n",
    }
    sites = _sites("c", files, [])
    assert sites[("caller_c", "helper")] == ("unique", "d.c")
    assert sites[("caller_a", "helper")] == ("file", "a.c")


def test_a_static_inline_through_a_header_chain_is_visible():
    files = {
        "alloc.h": "static inline void *hi_malloc(int n) {\n  return 0;\n}\n",
        "alloc.c": "void *hi_malloc(int n) {\n  return 0;\n}\n",
        "hiredis.h": '#include "alloc.h"\n',
        "net.c": '#include "hiredis.h"\nint net_connect(void) {\n  hi_malloc(1);\n  return 0;\n}\n',
    }
    sites = _sites("c", files, [("hiredis.h", "alloc.h"), ("net.c", "hiredis.h")])
    assert sites[("net_connect", "hi_malloc")] == ("import", "alloc.h")


def test_the_included_header_wins_over_one_nobody_includes():
    files = {
        "include/proj/detail.h": "static inline int detail_fn(void) {\n  return 1;\n}\n",
        "alt/detail.h": "static inline int detail_fn(void) {\n  return 2;\n}\n",
        "include/proj/api.h": '#include "detail.h"\n',
        "src/user.c": "#include <proj/api.h>\nint user_fn(void) {\n  return detail_fn();\n}\n",
    }
    includes = [("include/proj/api.h", "include/proj/detail.h"), ("src/user.c", "include/proj/api.h")]
    assert _sites("c", files, includes)[("user_fn", "detail_fn")] == ("import", "include/proj/detail.h")


def test_a_header_makes_its_paired_source_visible():
    files = {
        "src/api.h": "int api_fn(void);\n",
        "src/api.c": "int api_fn(void) {\n  return 1;\n}\n",
        "other/api.c": "int api_fn(void) {\n  return 2;\n}\n",
        "src/user.c": '#include "api.h"\nint user_fn(void) {\n  return api_fn();\n}\n',
    }
    assert _sites("c", files, [("src/user.c", "src/api.h")])[("user_fn", "api_fn")] == ("import", "src/api.c")


def test_cpp_pairs_a_header_with_the_only_source_of_its_stem():
    files = {
        "include/fmt/format.h": "namespace fmt {\nint vformat(int x);\n}\n",
        "src/format.cc": "namespace fmt {\nint vformat(int x) {\n  return x;\n}\n}\n",
        "test/other/format.h": "int unrelated();\n",
        "test/t.cc": "int vformat(int x) {\n  return 0;\n}\n",
        "app/main.cc": '#include "fmt/format.h"\nint run() {\n  return vformat(1);\n}\n',
    }
    sites = _sites("cpp", files, [("app/main.cc", "include/fmt/format.h")])
    assert sites[("run", "vformat")] == ("import", "src/format.cc")
