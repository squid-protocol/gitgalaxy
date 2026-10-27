"""#3772: a Java unit's bare call to a DIFFERENT overload of its own name (`fromJson(a)` ->
`fromJson(a, b)`, constructor chaining `this(...)`) is a call, not recursion. The detector keeps it
with its argument counts; the resolver links it only when a count picks another overload, and prunes
it as recursion when it picks the unit itself."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

SRC = (
    "package p;\n"
    "public class G {\n"
    "  public G() { this(1, 2); }\n"
    "  public G(int a, int b) { init(a); }\n"
    "  public int f(int x) { return f(x, 1); }\n"
    "  public int f(int x, int y) { return x; }\n"
    "  public int r(int n) { return r(n - 1); }\n"
    "  public int mix(int n) { return mix(n - 1) + mix(n, 1); }\n"
    "  public int mix(int n, int m) { return n; }\n"
    "  public int viaThis(int n) { return this.viaThis(n, 1); }\n"
    "  public int viaThis(int n, int m) { return n; }\n"
    "}\n"
)


def _parsed():
    out = StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(SRC, "")
    return out["functions"], out.get("classes", [])


def _by_line(functions, line):
    return next(f for f in functions if f["start_line"] == line)


def test_detector_keeps_a_sibling_overload_call_with_its_counts():
    fns, _ = _parsed()
    f1 = _by_line(fns, 5)
    assert f1["calls_out_to"] == ["f"]
    assert f1["calls_out_qualifiers"] == {"f": [""]}
    assert f1["calls_out_arities"] == {"f": [2]}  # the header's own parameter list is not a call


def test_detector_maps_this_chaining_to_the_constructor_name():
    fns, _ = _parsed()
    ctor = _by_line(fns, 3)
    assert ctor["calls_out_to"] == ["G"]
    assert ctor["calls_out_arities"] == {"G": [2]}
    assert _by_line(fns, 4)["calls_out_to"] == ["init"]


def test_detector_keeps_all_counts_of_a_unit_calling_itself_and_a_sibling():
    fns, _ = _parsed()
    assert _by_line(fns, 8)["calls_out_arities"] == {"mix": [1, 2]}


def _resolved():
    fns, classes = _parsed()
    for c in classes:
        c.setdefault("inheritance", [])
    parsed = [{"path": "p/G.java", "lang_id": "java", "functions": fns, "classes": classes}]
    sites, _stats = resolve_calls(parsed)
    return fns, sites


def _edges(sites):
    return {(s["src_line"], s["dst_line"]) for s in sites if s["dst_line"]}


def test_resolver_links_the_other_overload_and_prunes_true_recursion():
    fns, sites = _resolved()
    edges = _edges(sites)
    assert (3, 4) in edges  # this(1, 2) -> G(int, int)
    assert (5, 6) in edges  # f(x, 1) -> f(int, int)
    assert (8, 9) in edges and (8, 8) not in edges  # mix: the 1-arg call is recursion, the 2-arg one is not
    assert not any(s["src_line"] == 7 for s in sites)
    assert _by_line(fns, 7)["calls_out_to"] == []  # r(n - 1): same count as the unit, still recursion
    assert _by_line(fns, 8)["calls_out_to"] == ["mix"]


def test_a_receiver_qualified_self_name_call_is_unchanged():
    fns, _ = _parsed()
    assert _by_line(fns, 10)["calls_out_to"] == []
