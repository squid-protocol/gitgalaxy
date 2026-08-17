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

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

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
    ("branch", "if (x) then y else z", "differentValue = compute()"),
    ("args", "def foo(x: Int, y: Int) = x + y", "if (x) doSomething()"),
    ("structural_boundaries", "import scala.util.Try", "extendedInfo = fetch()"),
    ("func_start", "def foo() = {}", "if (x) foo()"),
    ("class_start", "class Foo {", "Class.forName(name)"),
    ("safety", "val x: Option[Int] = None", "optional = true"),
    ("safety_bypasses", "x.asInstanceOf[String]", "x.getClass"),
    ("high_risk_execution", "System.exit(1)", "System.currentTimeMillis()"),
    ("io", "Source.fromFile(path)", "sourceMap = generate()"),
    ("api", "export Foo._", "private def foo() = {}"),
    ("state_mutation", "var count = 0", "println(count)"),
    ("dead_code", "// def foo() = {}", "// just a note"),
    ("doc", "/** A doc comment */", "/* regular block comment */"),
    ("test", "assertEquals(1, 1)", "musty_old_code = true"),
    ("concurrency", "Future { compute() }", "futureDate = LocalDate.now"),
    ("ui_framework", 'dom.document.getElementById("x")', "domainName = 'example.com'"),
    ("closures", "list.map(x => x * 2)", "my_var = 5"),
    ("globals", 'sys.env("HOME")', "sys.exit(1)"),
    ("decorators", "@deprecated", "case x @ Foo() =>"),
    ("generics", "List[Int]", "arr[i]"),
    ("comprehensions", "for (x <- list) yield x * 2", "dict.mapValues(f)"),
    ("scientific", "scala.math.sqrt(4)", "mathScore = compute()"),
    ("reflection_metaprogramming", "implicit val x: Int = 5", "implicitly[Ordering[Int]]"),
    ("import", "import scala.util.Try", "// important note here"),
    ("ownership", "@author Jane Doe", "@authors: Jane, John"),
    ("planned_debt", "// TODO: refactor", "// See our TODOS backlog for details"),
    ("fragile_debt", "// HACK: workaround", "// this approach is a bit hacky"),
    ("spec_exposure", "// [SPEC-123] implements the contract", "[specification]"),
    ("ssr_boundaries", "class MyController extends Controller {", "actionable_items = []"),
    ("events", "val source: Source[Int, _] = ???", "sourceCode = readFile()"),
    ("dependency_injection", "lazy val foo = wire[FooService]", "requirement = true"),
    ("macros", "inline def foo() = 1", "type Foo = Int"),
    ("pointers", "val p: Ptr[Int] = ???", "pointer = null"),
    ("memory_alloc", "val z = Zone", "freedom = true"),
    ("telemetry", 'logger.info("message")', "logger.setLevel(DEBUG)"),
    ("debug_prints", 'println("debug")', "printer.render(doc)"),
    ("explicit_casts", "x.toInt", "x.toString"),
    ("panics_and_aborts", 'throw new Exception("err")', "throwaway_value = 5"),
    ("thread_sleeps", "Thread.sleep(1000)", "delayedResult = compute()"),
    ("bitwise_ops", "a ^ b", "a && b"),
    ("sync_locks", "synchronized { }", "locked = true"),
    ("immutability_locks", "val x = 5", "evaluate(x)"),
    ("cleanup", "conn.close()", "closely_related = true"),
    ("encapsulation", "private val x = 5", "privately = true"),
    ("listeners", 'emitter.on("event", cb)', "button.onClick"),
    ("test_skip", 'ignore("not ready") { }', "ignorance_score = 0"),
    ("serialization_parsing", "decode[Foo](json)", "jsonPayload = fetch()"),
    ("regex_execution", '"[0-9]+".r', '"hello".toUpperCase'),
    ("time_date_logic", "FiniteDuration(5, SECONDS)", "durationInSeconds = 5"),
    ("ipc_rpc_bridges", "val sys = ActorSystem()", "processedCount += 1"),
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


_SCALA_DEEP_CASES = [
    # ------------------ branch ------------------
    ("branch", "if (x > 0) then \n  println(x)", "val mathScore = 100"),
    ("branch", "try { foo() } catch { case e: Exception => }", "catchThisException()"),
    ("branch", "for { x <- xs; if x > 0 } yield x", "val yieldAmount = 5"),
    ("branch", "while (true) do \n  println(1)", "val whileRunning = true"),
    ("branch", "x match { case Some(y) => y }", "case_sensitive = false"),
    ("branch", "throw new IllegalArgumentException()", "val throwaway = 0"),

    # ------------------ args ------------------
    ("args", "def `weird-name with spaces!`(x: Int, y: String): Int =", "val foo = 1"),
    ("args", "def foo[T <: List[Int]](x: T): Int = {", "val fooT = 1"),
    ("args", "(f: (Int) => String) => f(1)", "val lambdaString = 1"),
    ("args", "def foo(x: String = \"()\") = x", "val defaultParen = 1"),
    ("args", "def config(\n  host: String,\n  port: Int\n) = {}", "val configHost = 1"),
    ("args", "x => x * 2", "val x = 2"),

    # ------------------ func_start ------------------
    ("func_start", "@Target(Array(ElementType.METHOD))\n@Retention(RetentionPolicy.RUNTIME)\ndef foo() =", "val bar = 1"),
    ("func_start", "inline\ntransparent\nprivate[this]\ndef foo() =", "inline val x = 5"),
    ("func_start", "override def `do something`[T]() =", "val do_something = 1"),
    ("func_start", "open lazy def bar() = {}", "open class Bar"),
    ("func_start", "def f[A](x: Int) =", "val fX = 1"),

    # ------------------ class_start ------------------
    ("class_start", "@Entity\n@Table(name=\"users\")\nfinal case class User(id: Int)", "val classId = 1"),
    ("class_start", "sealed abstract class Foo[T] extends Bar", "val abstractClass = 5"),
    ("class_start", "transparent trait Foo", "transparent val x = 1"),
    ("class_start", "enum Color { case Red, Green, Blue }", "val enumColor = Red"),
    ("class_start", "private[this]\nfinal\nobject Singleton", "final val Singleton = 1"),
    ("class_start", "open class Base", "open val base = 1"),

    # ------------------ structural_boundaries ------------------
    ("structural_boundaries", "extension (s: String) def foo = 1", "val extensionData = 5"),
    ("structural_boundaries", "given intOrd: Ord[Int] with {", "val givenValue = 5"),
    ("structural_boundaries", "export myLib.utils.*", "val exportAmount = 10"),
    ("structural_boundaries", "opaque type Password = String", "val opaqueData = null"),
    ("structural_boundaries", "import scala.util.{Try => STry, Success => SSuccess}", "val importDuty = 0"),
    ("structural_boundaries", "enum Tree[T] derives CanEqual", "val derivesData = 1"),
]


@pytest.mark.parametrize("signature,positive,negative", _SCALA_DEEP_CASES)
def test_scala_signature_deep_cases(signature, positive, negative):
    pattern = SCALA_RULES[signature]
    assert pattern is not None, f"scala's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"scala {signature!r} failed to match its deep positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), (
            f"scala {signature!r} incorrectly matched an excluded deep negative case: {negative!r}"
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


def test_scala_redos_immunity_sweep():
    """
    Issue #1070: scala had zero per-language ReDoS regression coverage.
    `args`'s generic-parameter stepper `(?:\\[(?:[^\\[\\]]|\\[[^\\[\\]]*\\])*\\])?`
    uses the same 1-level-nesting-trick already proven for the square-
    bracket variant elsewhere (epic #813/#825); `func_start`/`class_start`
    both stack an unclosed-annotation-paren step-over. Diagnosed clean via
    `check_redos_scaling` (consistent ~2x-per-doubling ratios) before
    writing these as permanent regression pins.
    """
    assert_redos_immune(SCALA_RULES["args"], "def foo[" + "[" * 100000, timeout_sec=3.0)
    assert_redos_immune(SCALA_RULES["func_start"], "@a(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(SCALA_RULES["class_start"], "@a(" + "a" * 100000, timeout_sec=3.0)
