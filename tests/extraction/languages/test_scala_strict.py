"""scala strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE SWEEP: `@`-PREFIXED LEADING-\b BOUNDARY BUGS
# ==============================================================================
# Found while investigating dart's `test_skip` (`@Ignore` never matched) and
# broadening the earlier find_symbolic_boundary_bugs.py-style sweep to also
# check the START of each \b(...)\b alternative, not just the end. `@` is a
# non-word character, so a shared LEADING \b before a `@`-prefixed
# alternative can only fire when a word character immediately precedes the
# `@` -- never true for how annotations/attributes/decorators are actually
# written (always preceded by whitespace or a line start). This silently
# blinded 10 already-"closed" or partially-fixed languages to nearly all of
# their annotation-based structural signatures. Each language's own
# dedicated closure PR already covers this signature; these are targeted
# regressions for the specific alternatives found broken, bundled together
# the same way the earlier ReDoS (#631) and symbolic-\b (#637) cross-language
# sweeps were.


def test_scala_at_prefixed_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["scala"]["rules"]
    assert r["safety_bypasses"].search("case x: String @unchecked => x")
    assert r["dependency_injection"].search("@Inject val service: FooService")


# ==============================================================================
# SCALA: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #608)
# ==============================================================================
SCALA_RULES = LANGUAGE_DEFINITIONS["scala"]["rules"]

_SCALA_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) then y else z", None),
    ("args", "def foo(x: Int, y: Int) = x + y", None),
    ("structural_boundaries", "import scala.util.Try", None),
    ("func_start", "def foo() = {}", None),
    ("class_start", "class Foo {", None),
    ("safety", "val x: Option[Int] = None", None),
    ("safety_bypasses", "x.asInstanceOf[String]", None),
    ("high_risk_execution", "System.exit(1)", None),
    ("io", "Source.fromFile(path)", None),
    ("api", "export Foo._", None),
    ("state_mutation", "var count = 0", None),
    ("dead_code", "// def foo() = {}", "// just a note"),
    ("doc", "/** A doc comment */", None),
    ("test", "assertEquals(1, 1)", None),
    ("concurrency", "Future { compute() }", None),
    ("ui_framework", 'dom.document.getElementById("x")', None),
    ("closures", "list.map(x => x * 2)", None),
    ("globals", 'sys.env("HOME")', None),
    ("decorators", "@deprecated", None),
    ("generics", "List[Int]", None),
    ("comprehensions", "for (x <- list) yield x * 2", None),
    ("scientific", "scala.math.sqrt(4)", None),
    ("reflection_metaprogramming", "implicit val x: Int = 5", None),
    ("import", "import scala.util.Try", None),
    ("ownership", "@author Jane Doe", None),
    ("planned_debt", "// TODO: refactor", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "class MyController extends Controller {", None),
    ("events", "val source: Source[Int, _] = ???", None),
    ("dependency_injection", "lazy val foo = wire[FooService]", None),
    ("macros", "inline def foo() = 1", None),
    ("pointers", "val p: Ptr[Int] = ???", None),
    ("memory_alloc", "val z = Zone", None),
    ("telemetry", 'logger.info("message")', None),
    ("debug_prints", 'println("debug")', None),
    ("explicit_casts", "x.toInt", None),
    ("panics_and_aborts", 'throw new Exception("err")', None),
    ("thread_sleeps", "Thread.sleep(1000)", None),
    ("bitwise_ops", "a ^ b", None),
    ("sync_locks", "synchronized { }", None),
    ("immutability_locks", "val x = 5", None),
    ("cleanup", "conn.close()", None),
    ("encapsulation", "private val x = 5", None),
    ("listeners", 'emitter.on("event", cb)', None),
    ("test_skip", 'ignore("not ready") { }', None),
    ("serialization_parsing", "decode[Foo](json)", None),
    ("regex_execution", '"[0-9]+".r', None),
    ("time_date_logic", "FiniteDuration(5, SECONDS)", None),
    ("ipc_rpc_bridges", "val sys = ActorSystem()", None),
]


@pytest.mark.parametrize("signature,positive,negative", _SCALA_SIMPLE_CASES)
def test_scala_signature_positive_and_negative(signature, positive, negative):
    pattern = SCALA_RULES[signature]
    assert pattern is not None, f"scala's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"scala {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"scala {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_scala_ownership_scaladoc_author_no_colon_regression():
    """
    Regression test: the Scaladoc `@author` tag was grouped with
    `Created by`/`Maintainer`/`Copyright`, all of which require a literal
    `:` -- but Scaladoc's actual convention (matching Javadoc, and java's
    own ownership rule) is `@author Jane Doe`, with no colon. The colon
    requirement meant the real tag never matched.
    """
    pattern = SCALA_RULES["ownership"]
    assert pattern.search("@author Jane Doe"), "the real, colon-less @author form still didn't match"
    assert pattern.search("Created by: Jane Doe")
    assert pattern.search("Copyright: 2026 Acme")


def test_scala_test_signature_boundary_regression():
    """Regression test: `test\\s*\\(` ends on `(`, so the shared trailing \\b never fired."""
    pattern = SCALA_RULES["test"]
    assert pattern.search('test("should work") { }'), "test(...) still didn't match"
    assert pattern.search("assertThrows[Exception] { }")


def test_scala_ssr_boundaries_play_result_boundary_regression():
    """
    Regression test: `Ok\\(`/`BadRequest\\(` both end on `(`, so the
    shared trailing \\b never fired for Play's two most common Result
    constructors.
    """
    pattern = SCALA_RULES["ssr_boundaries"]
    assert pattern.search('Ok("success")'), "Ok(...) still didn't match"
    assert pattern.search('BadRequest("error")')
    assert pattern.search("class MyController extends Controller {")


def test_scala_pointers_ptr_bracket_boundary_regression():
    """
    Regression test: `Ptr\\[[^\\]]+\\]` ends on the closing `]`, so the
    shared trailing \\b never fired (unlike `decode\\[` elsewhere, which
    is bounded only by the opening `[` and always followed by a word-char
    type name).
    """
    pattern = SCALA_RULES["pointers"]
    assert pattern.search("val p: Ptr[Int] = ???"), "Ptr[Int] still didn't match"
    assert pattern.search("ptr.isEmpty")


def test_scala_memory_alloc_zone_and_alloc_boundary_regression():
    """
    Regression test: `zone[ \\t]*\\{` ends on `{` and `alloc\\[[^\\]]+\\]`
    ends on the closing `]` -- both non-word, so the shared trailing \\b
    never fired for either.
    """
    pattern = SCALA_RULES["memory_alloc"]
    assert pattern.search("zone { implicit z => foo() }"), "zone { ... } still didn't match"
    assert pattern.search("val buf = alloc[Byte](10)"), "alloc[...] still didn't match"
    assert pattern.search("Zone.apply { }")


def test_scala_listeners_on_call_boundary_regression():
    pattern = SCALA_RULES["listeners"]
    assert pattern.search("emitter.on('data', cb)"), "on(...) still didn't match its most common form"
    assert pattern.search("stream.subscribe(observer)")


def test_scala_time_date_and_ipc_empty_args_boundary_regression():
    """
    Regression test: `Duration\\s*\\(` and `Process\\s*\\(` both end on
    `(`, so the shared trailing \\b only fired when a word char (e.g. a
    digit argument) immediately followed -- never true for the
    zero/quoted-argument forms (`Duration()`, `Process("cmd")`).
    """
    time_pattern = SCALA_RULES["time_date_logic"]
    ipc_pattern = SCALA_RULES["ipc_rpc_bridges"]
    assert time_pattern.search("val d = Duration()"), "Duration() still didn't match"
    assert time_pattern.search("val d = Duration(5, SECONDS)")
    assert ipc_pattern.search('val p = Process("ls")'), 'Process("cmd") still didn\'t match'
    assert ipc_pattern.search("val sys = ActorSystem()")


def test_scala_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 3 pairs the automated ambiguity sweep flagged for sharing
    literals: class_start<->dead_code ("class"/"object"/"trait"),
    class_start<->func_start ("final"/"open"/"transparent" modifiers),
    dead_code<->import ("import"). All confirmed false positives:
    dead_code's `//` comment-prefix requirement disambiguates it from
    both class_start and import, and class_start/func_start's shared
    modifiers correctly co-firing as mutually exclusive on the SAME
    declaration (one anchors a class, the other a def) is intentional,
    not a collision.

    Also documents a raw-regex-level collision the sweep didn't flag:
    `import`'s pattern has no comment-prefix exclusion, so
    `// import scala.util.Try` matches both `dead_code` AND `import` at
    the raw-regex level. This is expected and harmless in practice --
    comment text is stripped from the code stream by prism.py's
    lexical-family-based comment stripper before `import` ever
    evaluates it in the real pipeline (the same shape as ruby's
    doc-vs-panics_and_aborts YARD-tag collision, documented there too).
    """
    class_start = SCALA_RULES["class_start"]
    dead_code = SCALA_RULES["dead_code"]
    func_start = SCALA_RULES["func_start"]
    import_pattern = SCALA_RULES["import"]

    live_class = "class Foo {"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)

    commented_class = "// class Foo {"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    final_class = "final class Foo {"
    assert class_start.search(final_class) and not func_start.search(final_class)
    final_def = "final def foo() = {}"
    assert func_start.search(final_def) and not class_start.search(final_def)

    live_import = "import scala.util.Try"
    assert import_pattern.search(live_import)
    assert not dead_code.search(live_import)

    commented_import = "// import scala.util.Try"
    assert dead_code.search(commented_import) and import_pattern.search(commented_import), (
        "documented raw-regex collision changed shape -- update this test's rationale"
    )


def test_scala_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): scala's explicit_casts
    (`asInstanceOf[...]`/`.toInt`/etc.) and pointers (`Ptr[...]`/
    `scala.scalanative.unsafe`) don't share tokens and fire independently.
    """
    casts = SCALA_RULES["explicit_casts"]
    pointers = SCALA_RULES["pointers"]
    assert casts.search("x.toInt")
    assert not casts.search("val p: Ptr[Int] = ???"), "explicit_casts incorrectly matched a Scala Native pointer type"
    assert pointers.search("val p: Ptr[Int] = ???")
    assert not pointers.search("x.toInt"), "pointers incorrectly matched an explicit cast"
