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
