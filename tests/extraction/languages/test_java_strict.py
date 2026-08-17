"""java strict structural-signature coverage.

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
# CROSS-LANGUAGE REDOS SWEEP: "BARE IDENTIFIER BEFORE ARROW" FAMILY
# ==============================================================================
# All found by a systematic ReDoS sweep across every language's compiled
# patterns (not just the ones with an existing historical-bug comment):
# an unbounded identifier/word-run quantifier with no preceding \b anchor,
# immediately followed by a required-but-often-absent literal suffix
# (=>, ->, __c.getInstance, etc.). Because the leading character class has
# no boundary anchor, the engine retries the greedy-then-backtrack match at
# EVERY position in a long run of matching characters -- O(n^2) total, not
# exponential, but still a real DoS risk on a single pathologically long
# line (e.g. minified/obfuscated code). All bounded with numeric clamps
# instead of possessive quantifiers (`*+`), since those aren't available
# until Python 3.11 and this package supports 3.9+.


def test_java_args_lambda_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["java"]["rules"]["args"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("x -> x + 1")
    assert pattern.search("public void foo(int x) {")


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


def test_java_at_prefixed_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["java"]["rules"]
    assert r["ui_framework"].search("@ModelAttribute\npublic String foo() {}")
    assert r["ssr_boundaries"].search("@ResponseBody\npublic String foo() {}")
    assert r["ssr_boundaries"].search("@ResponseStatus(HttpStatus.OK)")
    assert r["events"].search("@EventListener\npublic void onEvent() {}")
    assert r["events"].search('@KafkaListener(topics = "x")')
    assert r["dependency_injection"].search("@Autowired\nprivate Foo foo;")
    assert r["dependency_injection"].search("@Component\npublic class Foo {}")
    assert r["listeners"].search('@KafkaListener(topics = "x")')


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE SWEEP: LITERAL `()` TRAILING-\b BOUNDARY BUGS
# ==============================================================================
# Found while writing go's time_date_logic test (`time.Now()` never
# matched). Broadened the sweep to check every `\b(...)\b`-wrapped
# alternative ending in a literal empty-parens function call, since `)` is
# non-word and whatever follows a function call (`;`, a newline, another
# `.method()`, end of string) is never a word character -- the shared
# trailing \b can never fire. Affects 8 languages; bundled the same way as
# the earlier ReDoS (#631), symbolic-\b (#637), and @-boundary (#645) sweeps.


def test_java_and_groovy_printstacktrace_boundary_regression():
    assert LANGUAGE_DEFINITIONS["java"]["rules"]["debug_prints"].search("e.printStackTrace();")
    assert LANGUAGE_DEFINITIONS["groovy"]["rules"]["debug_prints"].search("e.printStackTrace();")


# ==============================================================================
# JAVA: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #588)
# ==============================================================================
JAVA_RULES = LANGUAGE_DEFINITIONS["java"]["rules"]

_JAVA_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ('api', 'public void foo() {}', 'String result = compute();'),
    ('args', 'public void foo(int x) {', 'foo(x, y);'),
    ('bitwise_ops', 'a << 2', 'a < 2 && b > 2'),
    ('branch', 'if (x) { return; }', 'int x = 5;'),
    ('class_start', 'public class Foo {', 'Foo instance = new Foo();'),
    ('cleanup', 'conn.close();', 'closeable.markUsed();'),
    ('closures', 'list.forEach(x -> print(x));', 'int x = list.get(0);'),
    ('comprehensions', 'list.stream().map(x -> x);', 'list.size();'),
    ('concurrency', 'Thread t = new Thread(runnable);', 'Threading.configure();'),
    ('debug_prints', 'System.out.println("debug");', 'System.out.write(bytes);'),
    ('decorators', '@Override', 'final String email = "user@example.com";'),
    ('dependency_injection', '@Autowired\nprivate Foo foo;', '@Deprecated\npublic void foo() {}'),
    ('doc', '/** A doc comment */', '/* A regular block comment */'),
    ('encapsulation', 'private int x;', 'public int x;'),
    ('events', 'ApplicationEvent event = new FooEvent();', 'CustomEvent event = new FooEvent();'),
    ('explicit_casts', '(String) obj', 'int result = (x + y);'),
    ('fragile_debt', '// HACK: workaround', '// HACKATHON: team building event'),
    ('func_start', 'public void foo() {', 'public class Foo {'),
    ('generics', 'List<String> names;', 'a < 5 && b > 3;'),
    ('globals', 'public static final String FOO = "bar";', 'private int x = 5;'),
    ('high_risk_execution', 'System.exit(1);', 'long now = System.currentTimeMillis();'),
    ('immutability_locks', 'final int x = 5;', 'protected void finalize() {}'),
    ('import', 'import java.util.List;', '// import java.util.List;'),
    ('io', 'File f = new File(path);', 'String path = getPath();'),
    ('ipc_rpc_bridges', 'ProcessBuilder pb = new ProcessBuilder();', 'KafkaConsumer consumer = new KafkaConsumer();'),
    ('listeners', 'button.addEventListener(handler);', 'button.removeEventListener(handler);'),
    ('memory_alloc', 'Arena arena = Arena.ofConfined();', 'MemorySegment seg = allocator.allocate(8);'),
    ('ownership', '@author Jane Doe', '// Written by Jane Doe'),
    ('panics_and_aborts', 'throw new RuntimeException("err");', 'throwable.printStackTrace();'),
    ('planned_debt', '// TODO: refactor', '// TODONE: already implemented'),
    ('pointers', 'MemorySegment segment = arena.allocate(8);', 'MemoryMappedFile mmf = open(path);'),
    ('reflection_metaprogramming', 'Class.forName("Foo");', 'Class<?> clazz = obj.getClass();'),
    ('regex_execution', 'Pattern.compile(regex);', 'Pattern.quote(regex);'),
    ('safety', 'try { risky(); } catch (Exception e) {}', 'result = compute();'),
    ('safety_bypasses', 'Object x = null;', 'Object x = getValue();'),
    ('scientific', 'Math.sqrt(4);', 'double result = compute();'),
    ('serialization_parsing', 'ObjectMapper mapper = new ObjectMapper();', 'ObjectOutputStream oos = new ObjectOutputStream(fos);'),
    ('spec_exposure', '// [SPEC-123] implements the contract', '// see the spec sheet for details'),
    ('ssr_boundaries', 'ModelAndView mav = new ModelAndView();', 'HttpServletContext ctx = getContext();'),
    ('state_mutation', 'this.count = 5;', 'System.out.println(count);'),
    ('structural_boundaries', 'import java.util.List;', 'importedCount = 5;'),
    ('sync_locks', 'synchronized (lock) { }', 'unlocked = true;'),
    ('telemetry', 'logger.info("message");', 'logger.setLevel(Level.INFO);'),
    ('test', '@Test\npublic void testFoo() {}', 'public void testFoo() {}'),
    ('test_skip', '@Disabled', '@Deprecated'),
    ('thread_sleeps', 'Thread.sleep(1000);', 'Thread.currentThread();'),
    ('time_date_logic', 'LocalDate.now();', 'OffsetDateTime odt = OffsetDateTime.now();'),
    ('ui_framework', 'JFrame frame = new JFrame();', 'JTable table = new JTable();'),
    ('dead_code', '// public void foo() {}', '// just a note'),
]


@pytest.mark.parametrize("signature,positive,negative", _JAVA_SIMPLE_CASES)
def test_java_signature_positive_and_negative(signature, positive, negative):
    pattern = JAVA_RULES[signature]
    assert pattern is not None, f"java's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"java {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"java {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_java_globals_public_static_final_boundary_regression():
    """
    Regression test: the `public static final ... =` alternative ends on
    `=` (non-word), so the shared trailing \\b could never fire --
    whatever follows the `=` in a real declaration is never a word
    character. This extremely common Java constant-declaration idiom
    never matched at all.
    """
    pattern = JAVA_RULES["globals"]
    assert pattern.search('public static final String FOO = "bar";'), (
        "public static final CONSTANT = value still didn't match"
    )
    assert pattern.search("public static int COUNT = 0;")
    assert pattern.search('System.getenv("HOME")')
    assert not pattern.search("private int x = 5;"), "globals incorrectly matched a private field"


def test_java_state_mutation_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the unanchored
    `(?:\\w+\\.)?` before the method-name keywords greedily consumed a
    long run of plain word characters, failed to find the `.`, and
    backtracked one character at a time -- O(n) work at each of the O(n)
    positions re.search retries this unanchored alternative at. Confirmed
    genuine scaling (0.045s/0.18s/0.71s/2.85s/11.2s at n=5k/10k/20k/40k/
    80k, ~4x per doubling) before being bounded to `\\w{0,100}`.
    """
    pattern = JAVA_RULES["state_mutation"]
    poison = "x" * 80000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    # Correctness must survive the bound.
    assert pattern.search("obj.setValue(x);")
    assert pattern.search("list.add(item);")
    assert pattern.search("map.computeIfAbsent(k, f);")
    assert pattern.search("this.count = 5;")


def test_java_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 5 pairs/collisions the automated ambiguity sweep flagged:
    args<->dead_code ("private"/"protected"/"public"), class_start<->
    dead_code ("class"), class_start<->func_start ("class"/"enum"/
    "interface"/"record"), dead_code<->func_start ("class"/"for"/"if"/
    "return"/"while"), ssr_boundaries<->ui_framework ("ModelAndView").
    All confirmed non-bugs: dead_code's `//` prefix disambiguates it from
    args/class_start/func_start, and ModelAndView is genuinely dual-
    classified (it's both an SSR view-model construct and a UI-adjacent
    MVC class in this schema) -- intentional, not a false collision.
    """
    args = JAVA_RULES["args"]
    dead_code = JAVA_RULES["dead_code"]
    class_start = JAVA_RULES["class_start"]
    func_start = JAVA_RULES["func_start"]
    ssr_boundaries = JAVA_RULES["ssr_boundaries"]
    ui_framework = JAVA_RULES["ui_framework"]

    live_method = "public void foo() {"
    assert args.search(live_method)
    assert not dead_code.search(live_method)

    commented_method = "// public void foo() {"
    assert dead_code.search(commented_method)
    assert not args.search(commented_method)

    live_class = "public class Foo {"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)
    assert not func_start.search(live_class), "func_start incorrectly matched a class declaration"

    commented_class = "// public class Foo {"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    mav = 'ModelAndView mav = new ModelAndView("view");'
    assert ssr_boundaries.search(mav) and ui_framework.search(mav)


def test_java_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): java's explicit_casts
    (`(String) obj`) and pointers (`MemorySegment`/`MemoryLayout`) don't
    share tokens and fire independently.
    """
    casts = JAVA_RULES["explicit_casts"]
    pointers = JAVA_RULES["pointers"]
    assert casts.search("(String) obj")
    assert not casts.search("MemorySegment segment = arena.allocate(8);"), (
        "explicit_casts incorrectly matched a MemorySegment declaration"
    )
    assert pointers.search("MemorySegment segment = arena.allocate(8);")
    assert not pointers.search("(String) obj"), "pointers incorrectly matched an explicit cast"


def test_java_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with its test-framework `.test(`):
    java's `test` signature only matches `@Test`-style annotations,
    `assert*(`, or `verify`/`expect`/`given`/`when` calls -- never a
    bare `.test(`-style method, so it doesn't collide with
    `regex_execution`'s `Pattern.compile`/`Matcher.find`/`.matches(`.
    """
    test_pattern = JAVA_RULES["test"]
    regex_pattern = JAVA_RULES["regex_execution"]
    assert regex_pattern.search("str.matches(regex)")
    assert not test_pattern.search("str.matches(regex)"), "test incorrectly matched a regex method call"

_JAVA_DEEP_CASES = [
    # --- branch ---
    ("branch", "if(x) {", "String shift = \"yes\";"),
    ("branch", "for (int i=0;i<10;i++)", "int form = 1;"),
    ("branch", "yield value;", "yields_value();"),
    ("branch", "when (true)", "whence();"),
    ("branch", "catch(Exception e)", "catch_it();"),

    # --- args ---
    ("args", "public void foo( @NonNull int x, String y) {", "foo(x, y);"),
    ("args", "@Override public <T extends List<String>> void genericMethod(T x) {", "genericMethod(x);"),
    ("args", "private static final void myMethod(int a) {", "myMethod(a);"),
    ("args", "public MyClass() throws Exception {", "new MyClass();"),
    ("args", "(int x, int y) -> x + y", "int x = y - z;"),
    ("args", "String::toLowerCase", "String toLowerCase;"),
    ("args", "public <T, U extends Comparable<U>> void multiGeneric(T a, U b) {", "return multiGeneric(a, b);"),

    # --- func_start ---
    ("func_start", "public void myFunc(int a) {", "new MyObject();"),
    ("func_start", "public static <T extends Comparable<T>> T genericFunc() {", "return genericFunc();"),
    ("func_start", "Map<String, List<Integer>> getComplexData() {", "return getComplexData();"),
    ("func_start", "@Annotation(value = \"x\")\npublic void annotatedFunc() {", "return annotatedFunc();"),
    ("func_start", "public java.util.List<String> fullyQualifiedReturn() {", "return fullyQualifiedReturn();"),
    ("func_start", "public <T, U extends Comparable<U>> T multiGeneric(T a, U b) {", "return multiGeneric(a, b);"),
    ("func_start", "public int[] returnArray() {", "return returnArray();"),
    ("func_start", "public Map.Entry<K, V> returnEntry() {", "return returnEntry();"),
    ("func_start", "@SuppressWarnings(\"unchecked\") public void foo() {", "return foo();"),
    ("func_start", "public void\nweirdSpacing() {", "return weirdSpacing();"),

    # --- class_start ---
    ("class_start", "public abstract class AbstractNode {", "AbstractNode node = new AbstractNode();"),
    ("class_start", "public sealed interface Expr permits Add, Mul {", "Expr expr = new Expr();"),
    ("class_start", "record Point(int x, int y) {}", "new Point(1, 2);"),
    ("class_start", "class Node<T extends Comparable<T>> extends BaseNode<T> implements Cloneable {", "Node<String> node;"),
    ("class_start", "enum Color { RED, GREEN }", "Color.RED;"),
    ("class_start", "public class MultiGeneric<T, U extends Comparable<U>> {", "MultiGeneric<String, Integer> mg;"),
    ("class_start", "@Entity @Table(name = \"users\")\npublic class User {", "User user = new User();"),

    # --- structural_boundaries ---
    ("structural_boundaries", "public sealed interface Foo permits Bar {", "permitted = true;"),
    ("structural_boundaries", "module com.example.foo {", "module_name = \"foo\";"),
    ("structural_boundaries", "requires java.base;", "required = true;"),
    ("structural_boundaries", "exports com.example.api;", "exported = true;"),
    ("structural_boundaries", "provides com.example.Service with com.example.ServiceImpl;", "provided = true;"),
]

@pytest.mark.parametrize("signature,positive,negative", _JAVA_DEEP_CASES)
def test_java_signature_deep_cases(signature, positive, negative):
    pattern = JAVA_RULES[signature]
    assert pattern is not None, f"java's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"java {signature!r} failed to match deep positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), (
            f"java {signature!r} incorrectly matched an excluded/negative deep case: {negative!r}"
        )
