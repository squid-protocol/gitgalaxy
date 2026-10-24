"""#3772: a Java constructor's `super(...)` is a call to the superclass constructor. The detector keeps
it (constructors only, with argument counts); the resolver names the in-repo parent and links the
overload the counts pick. A parent outside the repo leaves no call, and `super.m()` is unchanged."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

BASE = (
    "package p;\n"
    "public class Base {\n"
    "  public Base() { }\n"
    "  public Base(String a) { }\n"
    "  public Base(String a, int b) { }\n"
    "  public void hello() { }\n"
    "}\n"
)
SUB = (
    "package p;\n"
    "public class Sub extends Base {\n"
    "  public Sub() { super(); }\n"
    "  public Sub(String a) { super(a); }\n"
    "  public Sub(String a, int b) { super(a, b); }\n"
    "  public void bye() { super.hello(); }\n"
    "  static class Inner extends Base {\n"
    "    Inner(String a) { super(a); }\n"
    "  }\n"
    "}\n"
)
OUTSIDE = "package p;\npublic class Boom extends RuntimeException {\n  public Boom(String m) { super(m); }\n}\n"


def _parse(src, path):
    out = StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(src, "")
    classes = out.get("classes", [])
    for c in classes:
        c.setdefault("inheritance", [])
    return {"path": path, "lang_id": "java", "functions": out["functions"], "classes": classes}


def _resolve(*files):
    parsed = [_parse(src, path) for path, src in files]
    sites, _ = resolve_calls(parsed)
    return parsed, sites


def _fn(parsed, path, line):
    f = next(p for p in parsed if p["path"] == path)
    return next(fn for fn in f["functions"] if fn["start_line"] == line)


def test_detector_keeps_super_only_in_a_constructor():
    out = StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(SUB, "")
    by_line = {f["start_line"]: f for f in out["functions"]}
    assert by_line[4]["calls_out_to"] == ["super"]
    assert by_line[4]["calls_out_arities"] == {"super": [1]}
    assert "super" not in by_line[6]["calls_out_to"]  # super.hello(): the call is hello, as before
    assert by_line[6]["calls_out_to"] == ["hello"]


def test_super_chains_to_the_overload_the_counts_pick():
    parsed, sites = _resolve(("p/Base.java", BASE), ("p/Sub.java", SUB))
    edges = {
        (s["src_line"], s["dst_line"])
        for s in sites
        if s["dst_path"] == "p/Base.java" and s["src_path"] == "p/Sub.java"
    }
    assert (3, 3) in edges  # super() -> Base()
    assert (4, 4) in edges  # super(a) -> Base(String)
    assert (5, 5) in edges  # super(a, b) -> Base(String, int)
    assert (4, 3) not in edges
    assert (8, 4) in edges  # a nested class chains to its own parent
    assert _fn(parsed, "p/Sub.java", 4)["calls_out_to"] == ["Base"]


def test_super_method_call_is_unchanged():
    _, sites = _resolve(("p/Base.java", BASE), ("p/Sub.java", SUB))
    assert any(s["src_line"] == 6 and s["callee"] == "hello" for s in sites)


def test_super_to_a_parent_outside_the_repo_is_no_call():
    parsed, sites = _resolve(("p/Boom.java", OUTSIDE))
    assert not sites
    assert _fn(parsed, "p/Boom.java", 3)["calls_out_to"] == []


GENERIC = (
    "package p;\n"
    "class Red<T> {\n"
    "  protected Red(T t) { }\n"
    "}\n"
    "class Blue<T> extends Red<T> {\n"
    "  Blue(T v) {\n"
    "    super(v);\n"
    "  }\n"
    "}\n"
    "abstract class Ad<T, B> {\n"
    "  Ad(int x) { }\n"
    "}\n"
    "final class Fra<T> extends Ad<T, String> {\n"
    "  Fra(int f) {\n"
    "    super(f);\n"
    "  }\n"
    "}\n"
)


def test_a_generic_superclass_is_named_without_its_type_arguments():
    _, sites = _resolve(("p/G.java", GENERIC))
    edges = {(s["src_line"], s["dst_line"]) for s in sites if s["dst_line"]}
    assert (6, 3) in edges  # Blue -> Red<T>
    assert (14, 11) in edges  # Fra -> Ad<T, String>


def test_lowercase_class_and_a_header_broken_before_implements_still_chain():
    base = "package p;\npublic abstract class vertex_t {\n  public vertex_t() { }\n}\n"
    sub = (
        "package p;\npublic class z_vertex_t extends vertex_t implements\n    Aa, Bb {\n"
        "  public z_vertex_t() {\n    super();\n  }\n}\n"
    )
    parsed, _ = _resolve(("p/vertex_t.java", base), ("p/z_vertex_t.java", sub))
    assert _fn(parsed, "p/z_vertex_t.java", 4)["calls_out_to"] == ["vertex_t"]


def test_a_nested_class_name_repeated_across_files_uses_its_own_files_parent():
    mk = lambda outer, parent: (  # noqa: E731
        f"package p;\nclass {outer} {{\n  static class Inner extends {parent} {{\n    Inner() {{\n      super();\n    }}\n  }}\n}}\n"
    )
    files = [
        ("p/A.java", mk("A", "PA")),
        ("p/B.java", mk("B", "PB")),
        ("p/PA.java", "package p;\nclass PA {\n  PA() { }\n}\n"),
        ("p/PB.java", "package p;\nclass PB {\n  PB() { }\n}\n"),
    ]
    parsed, _ = _resolve(*files)
    assert _fn(parsed, "p/A.java", 4)["calls_out_to"] == ["PA"]
    assert _fn(parsed, "p/B.java", 4)["calls_out_to"] == ["PB"]
