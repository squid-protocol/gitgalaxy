"""#4718: the cobolrt public API contract (docs/cobolrt_api_contract.md) against the real sources and every committed port.

The real manifest must match the sources both ways, and no committed port, generator string or live translation may use
an internal member. Each failure class of the checker is shown on a synthetic runtime, so a checker gone blind fails too.
Scanning a translate-only work directory of every case needs the corpora and runs from the command line
(cobolrt_api.py --check --generated DIR); here one small program goes through the real translator.
"""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))
sys.path.insert(0, str(ROOT))

import cobolrt_api as api  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: E402

RUNTIME = """package __PACKAGE__.cobolrt;

import java.util.List;

public final class Cobol {
    public static final int LIMIT = 9;
    static int hidden;
    private Cobol() {}

    public static Item item(String name) { return new Item(); }
    public static Item item(int at) { return new Item(); }
    public static List<Item> items() { return List.of(); }
    public static void plumbing(int a) {}
    static void packagePrivate() {}
    private static void secret() {}

    public static final class Item {
        public int value() { return 1; }
        public void set(int v) {}
    }
    public enum Mode { FIRST, ALL }
    public record Part(String text, int size) {}
    public interface Sink { void event(String what); default void flush() {} }
}
"""
SECOND = """package __PACKAGE__.cobolrt.standalone;

public final class Sysout {
    public static void display(String a) {}
}
"""
BATCH = """package __PACKAGE__.batch;

public final class Sysout {
    public static void display(String a, String b) {}
    public static class Abend extends RuntimeException {
        public Abend(String m) { super(m); }
        public String code() { return ""; }
    }
}
"""
INTERNAL_ONLY = ("cobolrt.Cobol.plumbing(int)",)


def surface() -> api.Surface:
    units = [api.Unit(f"rt/{i}.java", t, ("det-batch",)) for i, t in enumerate((RUNTIME, SECOND, BATCH))]
    return api.Surface(units)


def manifest(s: api.Surface, *internal: str) -> dict:
    """Everything public but the named ids."""
    m = api.build(s, None, None, False)
    for t in m["types"]:
        t["visibility"] = api.PUBLIC
        for row in t["members"]:
            row["visibility"] = api.INTERNAL if row["id"] in internal else api.PUBLIC
    m["summary"] = api.summary_of(m)
    return m


def problems(s: api.Surface, java: str, *internal: str) -> list[str]:
    refs, broken = api.scan(s, [(api.DET_PORT, "p.java", java)])
    assert not broken
    return api.check_callers(manifest(s, *internal), api.resolve(s, refs))


def port(body: str, imports: str = "import com.acme.cobolrt.Cobol;") -> str:
    return f"package com.acme.service;\n{imports}\nclass P {{\n{body}\n}}\n"


# ---- the real thing ---------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real():
    units = api.runtime_units()
    return units, api.Surface(units), api.load()


@pytest.fixture(scope="module")
def committed(real):
    units, s, _ = real
    return api.scan_tree(s, units, [])


def test_the_manifest_is_the_sources_surface(real):
    _, s, m = real
    assert api.check_surface(s, m) == []
    assert api.check_shape(s, m) == []
    assert m["schema"] == api.SCHEMA
    assert api.MANIFEST.read_text(encoding="utf-8") == api.dumps(m), "regenerate it: cobolrt_api.py generate"


def test_no_committed_port_or_generator_string_uses_an_internal_member(real, committed):
    usage, gaps = committed
    assert gaps == []
    assert api.check_callers(real[2], usage) == []


def test_the_scan_saw_the_ports_it_claims_to(committed):
    """A blind scan passes every other test here: the ports' everyday calls and the forge classes must be in it."""
    usage, _ = committed
    for used in ("cobolrt.Cobol.move(String,Field,Charset)", "cics.CicsTask.commarea(Class)", "batch.CobolFiles.Read.status()",
                 "cobolrt.cics.DetCics"):  # fmt: skip
        assert used in usage.used, used
    assert api.DET_PORT in usage.used["cobolrt.Hole"] and api.MODEL_PORT in usage.used["cics.CicsTask"]


def test_a_real_translation_uses_only_public_members(real, tmp_path):
    _, s, m = real
    source = tmp_path / "DEMO.cbl"
    source.write_text(
        """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  A PIC 9(4) VALUE 7.
       01  B PIC X(8).
       PROCEDURE DIVISION.
           ADD 1 TO A.
           MOVE 'TEXT' TO B.
           STRING 'A' 'B' DELIMITED BY SIZE INTO B.
           IF A > 3 DISPLAY B.
           GOBACK.
""",
        encoding="utf-8",
    )
    r = P.translate(source, [], "public class DemoService {\n}\n", "com.acme", None, None)
    refs, broken = api.scan(s, [(api.GENERATED, "DemoService.java", r.java)])
    assert not broken
    usage = api.resolve(s, refs)
    assert len(usage.used) > 5
    assert api.check_callers(m, usage) == []


def test_every_ported_runtime_file_is_in_the_variant_it_claims():
    """The variants the manifest states are program.runtime_files' choice and the sort job's filter."""
    batch, standalone = P.runtime_files("x", True), P.runtime_files("x", False)
    for rel in {*batch, *standalone}:
        variants = api._file_variants(rel.removeprefix("cobolrt/"))
        assert (api.DET_BATCH in variants) == (rel in batch), rel
        assert (api.DET_STANDALONE in variants) == (rel in standalone), rel
        assert (api.SORT_JOB in variants) == (rel in batch and not rel.startswith(("cobolrt/cics/", "cobolrt/sql/"))), (
            rel
        )


def test_every_committed_java_file_has_a_role():
    """A new home for ports is a decision, not a blind spot."""
    assert [p for p in api.tracked_java() if api.classify_java(p) is None] == []


# ---- what the surface is ----------------------------------------------------------------------------------------
def test_scope_follows_java_accessibility():
    s = surface()
    ids = {m.id for t in s.types.values() for m in t.members}
    assert "cobolrt.Cobol.LIMIT" in ids and "cobolrt.Cobol.item(String)" in ids
    assert not {x for x in ids if any(w in x for w in ("hidden", "packagePrivate", "secret"))}
    assert "cobolrt.Cobol.<init>()" not in ids  # a private constructor
    assert "cobolrt.Cobol.Item.<init>()" in ids  # the implicit default one
    assert {"cobolrt.Cobol.Mode.FIRST", "cobolrt.Cobol.Part.text()", "cobolrt.Cobol.Part.<init>(String,int)"} <= ids
    assert {"cobolrt.Cobol.Sink.event(String)", "cobolrt.Cobol.Sink.flush()"} <= ids  # an interface's implicit public


def test_a_forge_template_with_a_nul_or_a_comment_opener_in_a_literal_still_parses():
    """CicsTask carries a real NUL in a char literal: unmasked, the grammar drops the whole class."""
    text = "package __PACKAGE__.cics;\npublic class T {\n  public char z() { return '\0'; }\n"
    text += '  public String s() { return "text/*"; }\n}\n'
    s = api.Surface([api.Unit("t", text, ("forge-cics",))])
    assert {m.id for m in s.types["cics.T"].members} >= {"cics.T.z()", "cics.T.s()"}


def test_a_unit_that_does_not_parse_refuses_instead_of_shrinking_the_surface():
    with pytest.raises(ValueError, match="not parsable"):
        api.Surface([api.Unit("t", "package x;\npublic class T { void }\n", ("x",))])


# ---- (a) a surface change must reach the manifest ------------------------------------------------------------------
def test_a_new_public_member_or_type_fails_until_generated():
    s = surface()
    m = manifest(s)
    grown = api.Surface([api.Unit("rt/0.java", RUNTIME.replace("public enum Mode", "public static void added() {}\n    public enum Mode"), ("det-batch",)),
                         api.Unit("rt/1.java", SECOND, ("det-batch",)), api.Unit("rt/2.java", BATCH, ("det-batch",)),
                         api.Unit("rt/3.java", "package __PACKAGE__.cobolrt;\npublic class New {}\n", ("det-batch",))])  # fmt: skip
    found = "\n".join(api.check_surface(grown, m))
    assert "member cobolrt.Cobol.added() is in the sources" in found
    assert "type cobolrt.New is in the sources" in found


def test_a_removed_or_retyped_member_fails_and_says_when_it_was_public():
    s = surface()
    m = manifest(s, "cobolrt.Cobol.item(int)")
    text = RUNTIME.replace("public static Item item(int at) { return new Item(); }\n", "")
    text = text.replace("public static void plumbing(int a) {}", "public static int plumbing(int a) { return 0; }")
    text = text.replace("public int value() { return 1; }\n", "")
    smaller = api.Surface([api.Unit("rt/0.java", text, ("det-batch",)), api.Unit("rt/1.java", SECOND, ("det-batch",)),
                           api.Unit("rt/2.java", BATCH, ("det-batch",))])  # fmt: skip
    found = "\n".join(api.check_surface(smaller, m))
    assert "PUBLIC member cobolrt.Cobol.Item.value() is in the manifest, not in the sources" in found
    assert (
        "member cobolrt.Cobol.item(int) is in the manifest" in found
        and "PUBLIC member cobolrt.Cobol.item(int)" not in found
    )
    assert "member cobolrt.Cobol.plumbing(int): returns changed: 'void' -> 'int'" in found


def test_a_visibility_outside_the_two_words_fails():
    s = surface()
    m = manifest(s)
    m["types"][0]["members"][0]["visibility"] = "maybe"
    m["summary"] = api.summary_of(m)
    assert any("neither public nor internal" in p for p in api.check_surface(s, m))


def test_a_stale_summary_fails():
    s = surface()
    m = manifest(s)
    m["summary"]["members"] += 1
    assert any("summary" in p for p in api.check_surface(s, m))


def test_generate_keeps_classifications_and_a_new_member_starts_internal():
    s = surface()
    old = manifest(s, "cobolrt.Cobol.plumbing(int)")
    mode = next(t for t in old["types"] if t["id"] == "cobolrt.Cobol.Mode")
    mode["members"] = [r for r in mode["members"] if r["id"] != "cobolrt.Cobol.Mode.ALL"]
    new = api.build(s, old, None, False)
    rows = {r["id"]: r["visibility"] for t in new["types"] for r in t["members"]}
    assert rows["cobolrt.Cobol.plumbing(int)"] == api.INTERNAL and rows["cobolrt.Cobol.LIMIT"] == api.PUBLIC
    assert rows["cobolrt.Cobol.Mode.ALL"] == api.INTERNAL


def test_only_promote_used_turns_a_used_member_public():
    s = surface()
    refs, _ = api.scan(s, [(api.DET_PORT, "p.java", port("int f() { return Cobol.LIMIT; }"))])
    usage = api.resolve(s, refs)
    row = lambda m: next(r for t in m["types"] for r in t["members"] if r["id"] == "cobolrt.Cobol.LIMIT")  # noqa: E731
    assert row(api.build(s, None, usage, False))["visibility"] == api.INTERNAL
    assert row(api.build(s, None, usage, True))["visibility"] == api.PUBLIC


def test_the_manifest_text_is_stable_json():
    s = surface()
    m = manifest(s)
    assert json.loads(api.dumps(m)) == json.loads(json.dumps(m))
    assert api.dumps(json.loads(api.dumps(m))) == api.dumps(m)


# ---- (b) callers must stay on the public side -------------------------------------------------------------------
def test_a_static_call_to_an_internal_member_fails():
    bad = port("void f() { Cobol.plumbing(1); }")
    assert problems(surface(), bad) == []
    assert problems(surface(), bad, *INTERNAL_ONLY) == [
        "cobolrt.Cobol.plumbing(int) is internal, and det-port code uses it"
    ]


def test_an_internal_type_named_anywhere_fails():
    s = surface()
    m = manifest(s)
    next(t for t in m["types"] if t["id"] == "cobolrt.Cobol.Part")["visibility"] = api.INTERNAL
    refs, _ = api.scan(s, [(api.DET_PORT, "p.java", port("Cobol.Part held;"))])
    assert api.check_callers(m, api.resolve(s, refs)) == ["cobolrt.Cobol.Part is internal, and det-port code uses it"]


@pytest.mark.parametrize("body", [
    "int f() { return new Cobol.Item().value(); }",  # new
    "int f(Cobol.Item i) { return i.value(); }",  # a parameter
    "Cobol.Item held; int f() { return held.value(); }",  # a field
    "Cobol.Item held; int f() { return this.held.value(); }",  # through this
    "int f() { Cobol.Item i = Cobol.item(1); return i.value(); }",  # a local
    "int f() { var i = Cobol.item(1); return i.value(); }",  # var, from the declared return type
    "int f() { return Cobol.item(1).value(); }",  # a chain
    "int f(Object o) { return ((Cobol.Item) o).value(); }",  # a cast
    "int f() { return Cobol.items().get(0).value(); }",  # a container's one type argument
    "int f() { int n = 0; for (var i : Cobol.items()) n += i.value(); return n; }",  # for over one
    "int f(boolean b) { return (b ? Cobol.item(1) : null).value(); }",  # parentheses and a ternary
    "int f(Cobol.Item[] a) { return a[0].value(); }",  # an element
    "int f() { return com.acme.cobolrt.Cobol.item(1).value(); }",  # package-qualified
    "java.util.function.ToIntFunction<Cobol.Item> f = Cobol.Item::value;",  # a method reference
])  # fmt: skip
def test_the_receiver_is_inferred_wherever_a_port_can_hold_it(body):
    assert problems(surface(), port(body), "cobolrt.Cobol.Item.value()") == [
        "cobolrt.Cobol.Item.value() is internal, and det-port code uses it"
    ]


def test_a_name_shadowing_a_typed_variable_is_not_that_variable():
    body = "void f(Cobol.Item i) { java.util.List.of(1).forEach(i2 -> g(i2)); }\nvoid h(java.util.List<Integer> i) { i.size(); }"
    assert problems(surface(), port(body), "cobolrt.Cobol.Item.value()") == []
    lam = "void f(java.util.List<String> l, Cobol.Item value) { l.forEach(value2 -> value2.length()); }"
    assert problems(surface(), port(lam)) == []


def test_two_classes_of_one_name_are_told_apart_by_the_import():
    """standalone.Sysout and batch.Sysout: each port gets the one its project has."""
    body = 'void f() { Sysout.display("a", "b"); }'
    assert problems(surface(), port(body, "import com.acme.batch.Sysout;")) == []
    assert problems(surface(), port(body, "import com.acme.cobolrt.standalone.Sysout;")) == [
        "p.java:4: cobolrt.standalone.Sysout has no in-scope member display"
    ]


def test_a_static_import_is_a_reference():
    java = port("", "import static com.acme.cobolrt.Cobol.plumbing;")
    assert problems(surface(), java, *INTERNAL_ONLY) == [
        "cobolrt.Cobol.plumbing(int) is internal, and det-port code uses it"
    ]


def test_a_name_the_runtime_does_not_expose_fails():
    assert problems(surface(), port("void f() { Cobol.packagePrivate(); }")) == [
        "p.java:4: cobolrt.Cobol has no in-scope member packagePrivate"
    ]


def test_what_the_jdk_gives_a_class_is_not_the_runtime_surface():
    body = "String f(Cobol.Mode m, Cobol.Item i, Exception e) { m.name(); Cobol.Mode.values(); i.hashCode(); return i.toString(); }"
    assert problems(surface(), port(body)) == []
    thrown = 'String f() { return new Sysout.Abend("x").getMessage(); }'
    assert problems(surface(), port(thrown, "import com.acme.batch.Sysout;")) == []


def test_a_comment_between_arguments_is_no_argument():
    body = 'void f() { Cobol.item("A"  // a comment\n ); }'
    assert problems(surface(), port(body)) == []


def test_a_class_of_the_port_hides_a_runtime_name():
    java = "package com.acme.service;\nclass Cobol { static void plumbing(int a) {} }\nclass P { void f() { Cobol.plumbing(1); } }\n"
    assert problems(surface(), java, *INTERNAL_ONLY) == []


def test_a_call_binds_every_overload_of_its_argument_count():
    """The stated limit of a scan without argument types, on the safe side: `Cobol.item(1)` holds item(String) too."""
    assert problems(surface(), port("void f() { Cobol.item(1); }"), "cobolrt.Cobol.item(String)") == [
        "cobolrt.Cobol.item(String) is internal, and det-port code uses it"
    ]


def test_an_implementer_is_held_to_the_abstract_methods():
    java = port("class Mine implements Cobol.Sink { public void event(String w) {} }")
    assert problems(surface(), java, "cobolrt.Cobol.Sink.event(String)") == [
        "cobolrt.Cobol.Sink.event(String) is internal, and det-port code uses it"
    ]
    anon = port("Cobol.Sink s = new Cobol.Sink() { public void event(String w) {} };")
    assert problems(surface(), anon, "cobolrt.Cobol.Sink.event(String)") != []


def test_a_call_through_an_interface_binds_the_overrides():
    text = """package __PACKAGE__.cobolrt;
public final class D {
    public interface F { void close(); }
    public static class S implements F { public void close() {} public void extra() {} }
}
"""
    s = api.Surface([api.Unit("d", text, ("det-batch",))])
    java = "package com.acme.service;\nimport com.acme.cobolrt.D;\nclass P { void f(D.F x, D.S y) { x.close(); y.hashCode(); } }\n"
    used = api.resolve(s, api.scan(s, [(api.DET_PORT, "p.java", java)])[0]).used
    assert api.DET_PORT in used["cobolrt.D.S.close()"] and "cobolrt.D.S.extra()" not in used


def test_a_used_members_signature_types_enclosing_type_and_supertypes_are_reachable():
    s = surface()
    used = api.resolve(s, api.scan(s, [(api.DET_PORT, "p.java", port("void f() { Cobol.items(); }"))])[0]).used
    assert api.SIGNATURE in used["cobolrt.Cobol.Item"]
    deep = "class P { com.acme.batch.Sysout.Abend e; }"
    used = api.resolve(s, api.scan(s, [(api.DET_PORT, "p.java", "package com.acme.service;\n" + deep)])[0]).used
    assert api.SIGNATURE in used["batch.Sysout"]


def test_the_shape_of_the_public_side():
    s = surface()
    m = manifest(s)
    assert api.check_shape(s, m) == []
    item = next(t for t in m["types"] if t["id"] == "cobolrt.Cobol.Item")
    item["visibility"] = api.INTERNAL
    found = "\n".join(api.check_shape(s, m))
    assert "cobolrt.Cobol.Item.value() is public on the internal type cobolrt.Cobol.Item" in found
    assert "cobolrt.Cobol.item(int) is public but its signature names the internal type cobolrt.Cobol.Item" in found


# ---- the frozen copies and the file roles -----------------------------------------------------------------------
def test_a_frozen_runtime_copy_counts_only_for_its_calls_out_of_cobolrt():
    frozen = """package com.acme.cobolrt.cics;
import com.acme.batch.Sysout;
import com.acme.cobolrt.Cobol;
class Copy { void f() { Cobol.plumbing(1); Sysout.display("a", "b"); } }
"""
    s = surface()
    refs, _ = api.scan(s, [(api.FROZEN, "overlay/cobolrt/cics/Copy.java", frozen)])
    used = api.resolve(s, refs).used
    assert "cobolrt.Cobol.plumbing(int)" not in used
    assert used["batch.Sysout.display(String,String)"] == {api.FROZEN}


@pytest.mark.parametrize("rel,head,role", [
    ("gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java", "", api.RUNTIME_ONLY),
    ("gitgalaxy/tools/cobol_to_java/CicsSpec.java", "", api.RUNTIME_ONLY),
    ("tests/cics_crucible/ports/pc-wizard/PCCONF/overlay/cobolrt/Cobol.java", "", api.FROZEN),
    ("tests/cics_crucible/ports/pc-wizard/PCCONF/overlay/service/P.java", "// gitgalaxy-det-port: x", api.DET_PORT),
    ("tests/equivalence/carddemo-menu/port/service/M.java", "// a model's port", api.MODEL_PORT),
    ("tests/cobol_mainframe/port_invariance/cics-genapp/java/L.java", "", api.MODEL_PORT),
    ("docs/benchmarks/det-refine-cbact02c/C.java", "// gitgalaxy-det-port", api.DET_PORT),
    ("tests/tools/devin/adapter/x/E.java", "", "external"),
    ("tests/somewhere_new/Port.java", "", None),
])  # fmt: skip
def test_the_role_of_a_committed_java_file(rel, head, role):
    assert api.classify_java(rel, head) == role


def test_generated_output_skips_runtime_copies_and_identical_files(tmp_path):
    s = surface()
    (tmp_path / "a" / "cobolrt").mkdir(parents=True)
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "cobolrt" / "Cobol.java").write_text(RUNTIME, encoding="utf-8")
    (tmp_path / "a" / "batch").mkdir()
    (tmp_path / "a" / "batch" / "Sysout.java").write_text(BATCH, encoding="utf-8")
    java = port("void f() { Cobol.plumbing(1); }")
    (tmp_path / "a" / "P.java").write_text(java, encoding="utf-8")
    (tmp_path / "b" / "P.java").write_text(java, encoding="utf-8")
    (tmp_path / "b" / "Dto.java").write_text("class Dto {}\n", encoding="utf-8")  # names no runtime class
    assert [rel for _, rel, _ in api.generated_callers(tmp_path, s)] == ["a/P.java"]


def test_a_broken_port_is_reported_not_passed():
    s = surface()
    assert api.scan(s, [(api.DET_PORT, "p.java", "class P { void }\n")])[1] == ["p.java"]


# ---- the generator's strings ------------------------------------------------------------------------------------
def emitted(tmp_path: Path, module: str) -> dict[str, list[api.Ref]]:
    tmp = tmp_path / "gen.py"
    tmp.write_text(module, encoding="utf-8")
    s = surface()
    real_rel = api._rel
    api._rel = lambda p: p.name
    try:
        return api.emitter_refs(s, [], [tmp])
    finally:
        api._rel = real_rel


def test_a_generator_string_naming_a_member_is_a_reference(tmp_path):
    refs = emitted(tmp_path, 'X = f"{ind}Cobol.plumbing({a});"\n')
    assert [(r.type, r.name) for r in refs[api.EMITTER]] == [("cobolrt.Cobol", "plumbing")]


def test_a_string_that_only_looks_like_a_reference_is_none(tmp_path):
    module = '"""Cobol.plumbing is documented here."""\nX = "see cobolrt/Cobol.java"\nY = "x.Cobol.plumbing(1)"\n'
    refs = emitted(tmp_path, module)
    assert refs[api.EMITTER] == [] and refs[api.EMITTER_DYNAMIC] == []


def test_a_computed_name_binds_the_modules_constants_that_name_members(tmp_path):
    refs = emitted(tmp_path, 'FN = "plumbing"\nOTHER = "nothing"\ndef f(fn): return f"Cobol.{fn}(x)"\n')
    assert [(r.type, r.name) for r in refs[api.EMITTER_DYNAMIC]] == [("cobolrt.Cobol", "plumbing")]
    refs = emitted(tmp_path, 'FN = "plumbing"\ndef f(fn): return "Cobol." + fn\n')
    assert [(r.type, r.name) for r in refs[api.EMITTER_DYNAMIC]] == [("cobolrt.Cobol", "plumbing")]


def test_a_computed_receiver_is_kept_only_for_a_method_of_a_reachable_type(tmp_path):
    refs = emitted(tmp_path, 'def f(v): return f"{v}.value()"\n')
    assert [(r.type, r.name) for r in refs[api.COMPUTED]] == [("cobolrt.Cobol.Item", "value")]


def test_a_cobol_function_name_reaches_its_camel_case_method():
    assert api._camel("CURRENT-DATE") == "currentDate"
    assert api._camel("MAX") == "max"
