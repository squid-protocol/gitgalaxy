"""libclang call-graph reference on the C ports (#5630 step 4): the comparison maths and one real parse.

Synthetic sources only (no DOOM code). The tool dirs go on sys.path and the modules are imported as bare names.
"""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS / "doom_speedrun"))
sys.path.insert(0, str(TOOLS))

pytest.importorskip("tree_sitter_language_pack")

import clang_callgraph  # noqa: E402
import doom_clang_calls as dcc  # noqa: E402


def contract(fatal=()):
    d = {
        "defs": [["a.c", "main", 1], ["a.c", "helper", 5], ["b.c", "other", 1], ["v/lib.c", "lib", 1]],
        "edges": [
            [["a.c", "main", 1], ["a.c", "helper", 5], 2],
            [["a.c", "main", 1], ["b.c", "other", 1], 3],
            [["v/lib.c", "lib", 1], ["a.c", "helper", 5], 2],
        ],
        "external": [],
        "files": 3,
    }
    if fatal:
        d["fatal"] = list(fatal)
    return d


def test_vendored_files_are_dropped_from_the_clang_side():
    edges, defined = dcc.clang_edges(contract(), vendored=lambda rel: rel.startswith("v/"))
    assert defined == {"main", "helper", "other"}
    assert dict(edges) == {("a.c", "main"): {"helper", "other"}, ("a.c", "helper"): set(), ("b.c", "other"): set()}


def test_recall_precision_and_disagreements_over_shared_callers():
    clang, defined = dcc.clang_edges(contract())
    engine = {
        ("a.c", "main"): {"helper", "memcpy", "main"},  # memcpy is not defined in the port, main is a self-edge
        ("a.c", "helper"): {"other"},  # clang has no such edge
        ("c.c", "extra"): {"main"},
    }
    res = dcc.compare(engine, clang, defined)
    assert (res["agree"], res["clang_edges"], res["engine_edges"]) == (1, 2, 2)
    assert res["recall"] == pytest.approx(1 / 2)
    assert res["precision"] == pytest.approx(1 / 2)
    assert res["missed"] == ["a.c: main -> other"]
    assert res["engine_only"] == ["a.c: helper -> other"]
    assert res["callers_engine_only"] == 1  # c.c: extra
    assert res["callers_clang_only"] == 2  # b.c: other, v/lib.c: lib (no vendored test given)


def test_a_disagreement_in_a_fatal_file_is_not_counted_as_clean():
    clang, defined = dcc.clang_edges(contract())
    engine = {("a.c", "main"): {"helper"}, ("a.c", "helper"): {"other"}}
    assert dcc.compare(engine, clang, defined)["disagreements_in_clean_files"] == 2
    res = dcc.compare(engine, clang, defined, {"a.c"})
    assert res["disagreements_in_clean_files"] == 0 and res["files_fatal"] == 1 and res["callers_compared"] == 2


@pytest.mark.skipif(clang_callgraph.libclang_version() is None, reason="libclang is not installed")
def test_a_fatal_include_is_reported(tmp_path):
    (tmp_path / "ok.c").write_text("static int f(void){return 1;}\nint g(void){return f();}\n")
    (tmp_path / "cut.c").write_text('#include "generated_config.h"\nint h(void){return 2;}\nint k(void){return h();}\n')
    out = clang_callgraph.build(tmp_path, "c")
    assert out["fatal"] == ["cut.c"]
    assert ["ok.c", "g", 2] in [e[0] for e in out["edges"]]


@pytest.mark.skipif(clang_callgraph.libclang_version() is None, reason="libclang is not installed")
def test_a_clean_tree_has_no_fatal_key(tmp_path):
    (tmp_path / "ok.c").write_text("int g(void){return 0;}\n")
    assert "fatal" not in clang_callgraph.build(tmp_path, "c")


needs_clang = pytest.mark.skipif(clang_callgraph.libclang_version() is None, reason="libclang is not installed")


def _names(out):
    """{(caller, callee)} over the edges, and {(caller, name)} over the external calls."""
    return {(a[1], b[1]) for a, b, _ in out["edges"]}, {(c[1], n) for c, n in out["external"]}


@needs_clang
@pytest.mark.skipif(clang_callgraph.builtin_include() is None, reason="no host compiler builtin headers")
def test_a_header_function_taking_a_builtin_header_type_keeps_its_calls(tmp_path):
    """#6770: `size_t` comes from <stddef.h>, which the pip wheel lacks; the callee's declaration was invalid and
    the call named no function, whichever way the header function is spelled."""
    (tmp_path / "h.h").write_text(
        "#include <stddef.h>\n"
        "#include <stdarg.h>\n"
        "int ext(int);\n"
        "inline static int chk(size_t n) { return n > 1; }\n"  # `inline static`, as p_saveg.h writes it
        "static inline void grow(size_t n) { if (chk(n)) return; ext((int)n); }\n"
        "static inline int vsum(va_list ap) { return chk(1) + ext(va_arg(ap, int)); }\n"
    )
    (tmp_path / "a.c").write_text(
        '#include "h.h"\nint ext(int x) { return x; }\nint main(void) { grow(2); return 0; }\n'
    )
    edges, _ = _names(clang_callgraph.build(tmp_path, "c"))
    assert {("grow", "chk"), ("grow", "ext"), ("vsum", "chk"), ("vsum", "ext"), ("main", "grow")} <= edges


@needs_clang
def test_a_header_function_is_the_union_of_its_includers_macros(tmp_path):
    """#6770: `M_ARRAY_MALLOC` expands to a different callee per includer; the first one parsed no longer wins."""
    (tmp_path / "arr.h").write_text(
        "#ifndef ARR_MALLOC\n#define ARR_MALLOC(n) malloc(n)\n#endif\n"
        "void *malloc(unsigned long);\n"
        "static inline void *grow(unsigned long n) { return ARR_MALLOC(n); }\n"
    )
    (tmp_path / "a.c").write_text('#include "arr.h"\nvoid *use_a(void) { return grow(1); }\n')
    (tmp_path / "b.c").write_text(
        '#define ARR_MALLOC(n) my_alloc(n)\nvoid *my_alloc(unsigned long);\n#include "arr.h"\n'
        "void *my_alloc(unsigned long n) { return 0; }\nvoid *use_b(void) { return grow(2); }\n"
    )
    edges, external = _names(clang_callgraph.build(tmp_path, "c"))
    assert ("grow", "my_alloc") in edges  # the second includer's expansion, a def in the repo
    assert ("grow", "malloc") in external  # the first includer's, a libc call
    assert {("use_a", "grow"), ("use_b", "grow")} <= edges


@needs_clang
def test_header_function_edges_to_static_inline_extern_and_external_callees(tmp_path):
    """The whole class: a header-defined function calling a sibling header `static inline`, a `.c` definition, an
    external, and a function called only from another header function."""
    (tmp_path / "h.h").write_text(
        "int ext(int);\nint puts(const char *);\n"
        "static inline int leaf(int x) { return x + 1; }\n"
        "static inline int mid(int x) { return leaf(x); }\n"
        'static inline int top(int x) { puts("x"); return mid(x) + ext(x); }\n'
        "static inline int unused(int x) { return top(x); }\n"  # no .c calls it
    )
    (tmp_path / "a.c").write_text('#include "h.h"\nint ext(int x) { return x; }\nint main(void) { return top(1); }\n')
    out = clang_callgraph.build(tmp_path, "c")
    edges, external = _names(out)
    assert {("top", "mid"), ("mid", "leaf"), ("top", "ext"), ("unused", "top"), ("main", "top")} <= edges
    assert ("top", "puts") in external
    assert ["h.h", "unused", 6] in out["defs"]
