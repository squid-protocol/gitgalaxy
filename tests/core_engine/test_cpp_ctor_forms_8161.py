"""#8161 (P3): C++ constructions the text does not write as a call (`T x;`, `T x{a, b}`, `T x = "lit";`,
`make_unique<T>(a)`) are `ctor` edges to the class's constructor, chosen by argument count; never `call` edges
(owner decision). A written construction (`T x(a)`, `T(a)`, `new T(a)`) stays a `call` (contract C3), and its
argument count is now read at the declarator's `(`."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.cpp_ctor_forms import ctor_sites
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

HEADER = (
    "#pragma once\n"
    "struct Point { Point(); Point(int x, int y); };\n"
    "struct Label { Label(const char* s); };\n"
    "struct Plain { int v; };\n"
)
SOURCE = (
    '#include "shapes.h"\n'
    "Point::Point() {}\n"  # 2
    "Point::Point(int x, int y) {}\n"  # 3
    "Label::Label(const char* s) {}\n"  # 4
    "void paren() { Point p(1, 2); }\n"
    "void brace() { Point p{1, 2}; }\n"
    "void plain() { Point p; }\n"
    'void copy_init() { Label l = "x"; }\n'
    "void made() { auto p = std::make_unique<Point>(7, 8); }\n"
    "void no_ctor() { Plain q; Plain* r; int n; }\n"
    "void pointers() { Point* p; Point& r = other(); return; }\n"
)


def _sites():
    files = []
    for path, code in (("src/shapes.h", HEADER), ("src/shapes.cpp", SOURCE)):
        p = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")
        files.append({"path": path, "lang_id": "cpp", "functions": p["functions"], "classes": p["classes"]})
    sites, stats = resolve_calls(files, [{"src": "src/shapes.cpp", "dst": "src/shapes.h"}])
    return {(s["src_name"], s["callee"], s["kind"]): s for s in sites}, stats


def test_unwritten_constructions_are_ctor_edges_chosen_by_count():
    sites, stats = _sites()
    assert sites[("brace", "Point", "ctor")]["dst_line"] == 3
    assert sites[("plain", "Point", "ctor")]["dst_line"] == 2
    assert sites[("copy_init", "Label", "ctor")]["dst_line"] == 4
    assert sites[("made", "Point", "ctor")]["dst_line"] == 3
    assert not any(k[0] in ("brace", "plain", "copy_init") and k[2] == "call" for k in sites)
    assert sum(stats["ctors_by_step"].values()) == 4


def test_a_written_construction_stays_a_call_with_its_count():
    sites, _ = _sites()
    assert sites[("paren", "Point", "call")]["dst_line"] == 3  # `Point p(1, 2)`: two arguments, at `p(`
    assert ("paren", "Point", "ctor") not in sites


def test_no_edge_without_a_repository_constructor_or_for_a_pointer():
    sites, _ = _sites()
    assert not any(k[0] in ("no_ctor", "pointers") and k[2] == "ctor" for k in sites)


def test_ctor_sites_read_the_body_only():
    text = "Point make(Point a) { Point p; ns::Box<int> b{1, 2, 3}; return p; }"
    assert ctor_sites(text) == [("Point", "", 0), ("Box", "ns", 3)]


def test_ctor_sites_are_linear():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction" / "languages"))
    from linear_assert import assert_linear

    def run(n):
        ctor_sites("void f() {" + "a::" * (n // 3) + " " * n + "T x" + " " * n + "{" * (n // 8))

    assert_linear(run, 6000, 12000)
