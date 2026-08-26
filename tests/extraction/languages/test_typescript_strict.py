"""typescript strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

# ==============================================================================
# TYPESCRIPT: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #778, part of epic #518)
# ==============================================================================
# NOTE: filed as one of 6 new sub-issues (#773-778) after auditing and
# rejecting the epic's founding premise that C/C++/C#/COBOL/Rust/TypeScript
# already had adequate coverage -- see #518's updated "Why" section. This
# language previously had only one isolated regression test (the TypeScript
# half of `test_thermodynamic_operator_collisions`, covering `test` vs
# `regex_execution`), not the full per-signature template.
TYPESCRIPT_RULES = LANGUAGE_DEFINITIONS["typescript"]["rules"]

_TYPESCRIPT_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x > 0) {", "const x = 1;"),
    ("args", "function foo(x: number) {", "const x = 1;"),
    ("structural_boundaries", "export class Foo {}", "const x = 1;"),
    ("func_start", "function foo() {}", "class Foo {}"),
    ("class_start", "class Foo {}", "function foo() {}"),
    ("safety", "try {", "const x = 1;"),
    ("safety_bypasses", "@ts-ignore", "const x = 1;"),
    ("high_risk_execution", "eval(code)", "const x = 1;"),
    ("io", "fetch(url)", "const x = 1;"),
    ("api", "export function foo() {}", "const x = 1;"),
    ("state_mutation", "let x = 1;", "const x = 1;"),
    ("dead_code", "// if (x) foo();", "// just a note"),
    ("doc", "/** doc */", "// just a note"),
    ("test", "it('works', () => {})", "myRegex.test('x')"),
    ("concurrency", "await foo();", "const x = 1;"),
    ("ui_framework", "className='foo'", "const x = 1;"),
    ("closures", "() => {", "const x = 1;"),
    ("globals", "window.location", "const x = 1;"),
    ("decorators", "@Component", "const x = 1;"),
    ("generics", "Array<Foo>", "const x = 1;"),
    ("comprehensions", ".map(x => x)", "const x = 1;"),
    ("scientific", "Math.random()", "const x = 1;"),
    ("reflection_metaprogramming", "Reflect.get(obj, 'x')", "const x = 1;"),
    ("import", "import { foo } from 'bar';", "const x = 1;"),
    ("ownership", "@author Jane Doe", "const x = 1;"),
    ("planned_debt", "// TODO: fix this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "[SPEC-123]", "// just a note"),
    ("ssr_boundaries", "getServerSideProps", "const x = 1;"),
    ("events", "emit('event')", "const x = 1;"),
    ("dependency_injection", "@Injectable()", "const x = 1;"),
    ("memory_alloc", "new Foo()", "const x = 1;"),
    ("telemetry", "logger.info('msg')", "console.log('msg')"),
    ("debug_prints", "console.log('msg')", "logger.info('msg')"),
    ("explicit_casts", "x as Foo", "const x = 1;"),
    ("panics_and_aborts", "throw new Error('x')", "const x = 1;"),
    ("thread_sleeps", "setTimeout(fn, 100)", "const x = 1;"),
    ("bitwise_ops", "x << 2", "const x = 1;"),
    ("sync_locks", "mutex.lock()", "const x = 1;"),
    ("immutability_locks", "const x = 1;", "let x = 1;"),
    ("cleanup", "dispose()", "const x = 1;"),
    ("encapsulation", "private foo", "public foo"),
    ("listeners", "addEventListener('click', fn)", "const x = 1;"),
    ("test_skip", "test.skip('x', fn)", "const x = 1;"),
    ("lazy_evaluation", "function* gen() {}", "function foo() {}"),
    ("vectorized_math", "matmul(a, b)", "const x = 1;"),
    ("serialization_parsing", "JSON.parse(str)", "const x = 1;"),
    ("regex_execution", "new RegExp('x')", "const x = 1;"),
    ("time_date_logic", "Date.now()", "const x = 1;"),
    ("ipc_rpc_bridges", "postMessage(data)", "const x = 1;"),
    ("rce_funnel", "child_process.exec('bash script.sh')", "const x = 1;"),
    ("exfiltration_camouflage", "fetch(url, {telemetry: data})", "fetch(url, {body: data})"),
    ("llm_api", "import OpenAI from 'openai';", "const x = 1;"),
    ("llm_orchestrator", "import { Chain } from 'langchain';", "const x = 1;"),
    ("llm_vector_store", "import { Client } from 'chromadb';", "const x = 1;"),
    ("ml_traditional", "import x from 'sklearn';", "const x = 1;"),
    ("dl_frameworks", "import * as tf from 'tensorflow';", "const x = 1;"),

    # --- ADVERSARIAL CASES FOR HIGH-AMBIGUITY SIGNATURES ---
    ("branch", "const result = (a ?? b) || c && d ? e : f;", None),
    ("branch", "switch(x){case 1:break;default:}", None),
    ("branch", "try{await foo()}catch(e){finally{}}", None),
    ("branch", "}else if(x){", None),
    ("branch", "for  ( let i = 0 ; i < 10 ; i++ )", None),
    ("branch", "do{foo()}while(x);", None),

    ("args", "  #myPrivateMethod<T extends Record<string, any>>(a: T, b: number) {", "  return (a + b);"),
    ("args", "const f = (x: { a: string, b: number }): void => {", "  throw (a);"),
    ("args", "public get [Symbol.iterator]() {", "  yield (x);"),
    ("args", "public async *myGenerator<T>(arg: T) {", "  await (p);"),
    ("args", "  *gen(a: number) {", "  typeof (x);"),
    ("args", "export function foo \n <T> \n (x: T) {", "void (0);"),

    ("func_start", "export const myFunc: React.FC<Props> = (props) => {", "type MyFunc = (a: number) => void;"),
    ("func_start", "public async *myGenerator<T>(arg: T) {", "  return foo();"),
    ("func_start", "const f = function <T>(x: T) {", "  typeof foo();"),
    ("func_start", "  #myPrivateMethod(a: number) {", None),
    ("func_start", "  [Symbol.iterator]() {", None),
    ("func_start", "  *  myGenerator () {", None),

    ("structural_boundaries", "export const a = 1;", "const a = b >= c;"),
    ("structural_boundaries", "class Foo implements Bar {", None),
    ("structural_boundaries", "const a = b satisfies T;", None),
    ("structural_boundaries", "using a = new Disposable();", None),
    ("structural_boundaries", "declare module A {}", None),
    ("structural_boundaries", "import type { A } from 'b';", None),

    ("class_start", "export abstract class Foo<T extends U> extends Bar<T> {", None),
    ("class_start", "export class Foo<T extends Record<K, V>> extends Bar<T> {", None),
    ("class_start", "class Foo <T> implements A, B {", None),
    ("class_start", "class Foo<T=any> extends Bar {", None),
    ("class_start", "declare class Foo<T> {", None),
]


@pytest.mark.parametrize("signature,positive,negative", _TYPESCRIPT_SIMPLE_CASES)
def test_typescript_signature_positive_and_negative(signature, positive, negative):
    pattern = TYPESCRIPT_RULES[signature]
    assert pattern is not None, f"typescript's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"typescript {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"typescript {signature!r} incorrectly matched an excluded case: {negative!r}"
        )


def test_typescript_dependency_capture_extracts_import_require_and_dynamic_import():
    dep = TYPESCRIPT_RULES["_dependency_capture"]
    m = dep.search("import { foo } from 'bar';")
    assert m and m.group(1) == "bar" and m.group(2) is None

    m2 = dep.search("const x = require('lodash');")
    assert m2 and m2.group(2) == "lodash" and m2.group(1) is None

    m3 = dep.search("const x = await import('trojan');")
    assert m3 and m3.group(2) == "trojan"


def test_typescript_named_token_capture_extracts_destructured_imports():
    named = TYPESCRIPT_RULES["_named_token_capture"]
    m = named.search("import { foo, bar } from 'baz';")
    assert m and m.group(1).strip() == "foo, bar"


def test_typescript_func_start_excludes_control_flow_keywords():
    func_start = TYPESCRIPT_RULES["func_start"]
    for excluded in ("if (x) {", "for (;;) {", "while (x) {", "switch (x) {", "catch (e) {", "class Foo {"):
        assert not func_start.search(excluded), f"func_start incorrectly matched {excluded!r}"


def test_typescript_state_mutation_boundary_regression():
    """
    Real bug found and fixed: `.current =`, `.set(`, `.delete(`, and
    `.add(` shared a trailing `\\b` with word-ending siblings (push/pop/
    ...), but all four end in `(` or `=` (non-word) -- `\\b` right after can
    only fire if the next char happens to be a word character, never true
    for the realistic forms (`myRef.current = value` -- space after `=`;
    `myMap.set('key', v)` -- quote after `(`).
    """
    old_pattern = re.compile(
        r"\b(let|var|this\.|setState|push|pop|shift|unshift|splice|sort|reverse|\.current[ \t]*=|\.set\(|\.delete\(|\.add\()\b"
    )
    for realistic in ("myRef.current = value;", "myMap.set('key', val);", "mySet.delete('x');", "mySet.delete();"):
        assert not old_pattern.search(realistic), f"sanity check: bug must reproduce for {realistic!r}"

    state_mutation = TYPESCRIPT_RULES["state_mutation"]
    assert state_mutation.search("myRef.current = value;")
    assert state_mutation.search("myMap.set('key', val);")
    assert state_mutation.search("mySet.delete('x');")
    assert state_mutation.search("mySet.delete();")
    assert state_mutation.search("mySet.add(item);")
    # already-working forms must still work
    assert state_mutation.search("let x = 1;")
    assert state_mutation.search("myMap.set(1, 2);")


def test_typescript_dead_code_comment_style_completeness_regression():
    """
    Real bug found and fixed (Engine Rule 12): typescript is `standard_block`
    (both `//` and `/* */` are real comment styles), but dead_code only ever
    checked `//` -- a block-commented-out function/class was invisible.
    """
    old_pattern = re.compile(r"//[ \t]*(?:if|for|while|function|class|return|export|import)\b")
    realistic = "/* function foo() {} */"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    dead_code = TYPESCRIPT_RULES["dead_code"]
    assert dead_code.search(realistic)
    assert dead_code.search("// function foo() {}"), "the already-working // form must still work"
    assert not dead_code.search("// just a note")


def test_typescript_lazy_evaluation_function_star_boundary_regression():
    """
    Real bug found and fixed: `function\\s*\\*` shared a trailing `\\b`
    with word-ending siblings, but ends in a literal `*` -- `\\b` right
    after can only fire if the next char is a word character, never true
    for the canonical `function* foo()` generator syntax (space after the
    `*`). Unlike the co-located `yield\\s*\\*` (silently shadowed by the
    bare `yield` alternative earlier in the same group, so it happened to
    still "work" despite the same defect), nothing else in this pattern
    covered bare `function*` generator declarations -- a genuine, unmasked
    false negative.
    """
    old_pattern = re.compile(r"\b(yield|yield\s*\*|function\s*\*|Generator|AsyncGenerator|Iterable|AsyncIterable)\b")
    realistic = "function* foo() {}"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    lazy_evaluation = TYPESCRIPT_RULES["lazy_evaluation"]
    assert lazy_evaluation.search(realistic)
    assert lazy_evaluation.search("function *foo() {}"), "the less-common space-before-star form must still work"
    assert lazy_evaluation.search("yield x;")
    assert lazy_evaluation.search("yield* gen();")
    assert lazy_evaluation.search("const g: Generator<number> = foo();")


def test_typescript_reflection_metaprogramming_empty_call_boundary_regression():
    """
    Real bug found and fixed: `.bind(`, `.call(`, `.apply(` shared a
    trailing `\\b` with word-ending siblings, but end in a literal `(` --
    broke on the truly-empty-argument call form (`foo.bind()`), where the
    next char after `(` is `)`, not a word char.
    """
    old_pattern = re.compile(
        r"\b(arguments\.|prototype|__proto__|Object\.assign|Reflect|Proxy|Object\.defineProperty|\.bind\(|\.call\(|\.apply\()\b"
    )
    realistic = "foo.bind();"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    reflection = TYPESCRIPT_RULES["reflection_metaprogramming"]
    assert reflection.search(realistic)
    assert reflection.search("foo.call(this, x);"), "the already-working non-empty forms must still work"
    assert reflection.search("foo.apply(this, [1]);")


def test_typescript_class_start_generic_extends_regression():
    """
    Real bug found and fixed: the extends/implements capture required
    whitespace immediately after the class-name capture, but a generic
    class declaration (`class Foo<T> extends Bar<T>`) has `<T>` there
    instead -- the optional extends/implements group silently never fired
    for any generic class, a very common TypeScript pattern.
    """
    old_pattern = re.compile(
        r"^[ \t]*(?:(?:export|default|abstract|declare)[ \t\n]+){0,4}(?:class|enum|interface)[ \t\n]+([a-zA-Z_$][\w$]*)(?:[ \t\n]+(?:extends|implements)[ \t\n]+([a-zA-Z_$][\w_$, \t\n]*))?",
        re.M,
    )
    realistic = "class Foo<T> extends Bar<T> {"
    old_m = old_pattern.search(realistic)
    assert old_m and old_m.group(2) is None, "sanity check: bug must reproduce against the old pattern"

    class_start = TYPESCRIPT_RULES["class_start"]
    m = class_start.search(realistic)
    assert m and m.group(1) == "Foo" and m.group(2) == "Bar"

    m2 = class_start.search("class Foo<T extends Base> implements IFoo<T> {")
    assert m2 and m2.group(1) == "Foo" and m2.group(2) == "IFoo", (
        "generic constraint's own 'extends' must not be misread as the class's implements clause"
    )

    m3 = class_start.search("class Foo extends Bar<Baz> {")
    assert m3 and m3.group(1) == "Foo" and m3.group(2) == "Bar", "non-generic class must still work"


def test_typescript_exfiltration_camouflage_nested_paren_regression():
    """
    Real bug found and fixed (Rule 11, nested-delimiter coverage): the flat
    `[^)]*` broke on one level of nested parens before the camouflage
    keyword -- e.g. a URL built via a helper call (`fetch(buildUrl("x"),
    {telemetry: payload})`), a realistic evasion shape for exactly the
    kind of disguised-exfiltration traffic this security-relevant rule
    exists to catch.
    """
    old_pattern = re.compile(
        r"\b(fetch|axios\.post|https\.request)\s*\([^)]*(?:checkmarx|telemetry|metrics|audit|log)\b",
        re.I,
    )
    realistic = 'fetch(buildUrl("x"), {telemetry: payload})'
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    exfil = TYPESCRIPT_RULES["exfiltration_camouflage"]
    assert exfil.search(realistic)
    assert exfil.search("fetch(url, {telemetry: data})"), "the already-working non-nested form must still work"
    assert not exfil.search("fetch(url, {body: data})")


def test_typescript_spec_exposure_redos_regression():
    """
    Real bug found and fixed: adjacent unbounded quantifiers with
    overlapping character sets (`\\d+` immediately followed by `[^\\]]*`,
    which also matches digits) -- the same ReDoS shape already found and
    fixed independently in embedded_python, css, tcl, matlab, and scheme
    earlier in this epic (the 6th language now).
    """
    assert_redos_immune(TYPESCRIPT_RULES["spec_exposure"], "[SPEC-1" + "1" * 100000, timeout_sec=3.0)
    assert TYPESCRIPT_RULES["spec_exposure"].search("[SPEC-123]")


def test_typescript_func_start_whitespace_partition_redos_regression():
    """
    Real bug found and fixed: a severe ReDoS (~4x per doubling, ~1.9s at
    n=32000 before the fix). The trailing lookahead `\\s*(?:<[^>]*>)?\\s*\\(`
    (shared by the `function` branch and the class-member branch) had two
    adjacent unbounded `\\s*` quantifiers separated by an optional group --
    on a long run of pure whitespace with no `(` ever appearing, the engine
    could partition that whitespace between the two `\\s*` instances in
    exponentially many ways before failing.
    """
    func_start = TYPESCRIPT_RULES["func_start"]
    assert_redos_immune(func_start, "function foo" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(func_start, "myMethod" + " " * 100000, timeout_sec=3.0)
    assert func_start.search("function foo() {}")


def test_typescript_func_start_nested_generic_constraint_regression():
    """
    Real bug found and fixed (Rule 11 -- this is the issue's own flagged
    "func_start vs generics" known ambiguity pattern, already found in
    C#): the flat `[^>]*` generic step-over broke on even one level of
    nested angle brackets in a generic constraint
    (`function foo<T extends Array<number>>`), a common realistic
    TypeScript pattern -- func_start silently failed to match the WHOLE
    function, not just the generic part. Fixed by tolerating one level of
    self-nesting; also confirms func_start survives a long nested-generic
    payload without pathological backtracking.
    """
    func_start = TYPESCRIPT_RULES["func_start"]
    assert func_start.search("function foo<T extends Array<number>>(x: T) {")
    assert func_start.search("function foo<T extends Promise<User>>(x: T) {")
    m = func_start.search("class Foo {\n  bar<T extends Array<number>>(x: T) {}\n}")
    assert m and m.group(0).strip().startswith("bar")

    generics = TYPESCRIPT_RULES["generics"]
    assert generics.search("function foo<T extends Array<number>>(x: T) {")

    assert_redos_immune(func_start, "function foo<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(func_start, "myMethod<" + "a" * 100000, timeout_sec=3.0)


def test_typescript_bitwise_ops_vs_closures_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in Rust
    `|a| a + 1` and C++ `std::cout <<` -- confirmed with a dedicated
    regression test elsewhere in this file, `test_thermodynamic_operator_
    collisions`, for the C++/Rust cases). typescript's closures use `=>`
    arrow syntax and bitwise_ops uses `<<`/`>>`/`^`/`~`, structurally
    distinct -- no realistic overlap.
    """
    closures = TYPESCRIPT_RULES["closures"]
    bitwise_ops = TYPESCRIPT_RULES["bitwise_ops"]

    arrow = "const f = () => { return 1; };"
    assert closures.search(arrow)
    assert not bitwise_ops.search(arrow)

    shift = "x << 2"
    assert bitwise_ops.search(shift)
    assert not closures.search(shift)


def test_typescript_intentional_double_classification_sweep():
    """
    Ambiguity sweep finding: several typescript constructs legitimately
    fire two signatures representing different perspectives on the same
    underlying action -- intentional, not false collisions:
    - `clearTimeout(id)` -> cleanup (resource release) + time_date_logic
      (timer/clock API)
    - `setTimeout(fn, ms)` -> concurrency (async scheduling) + thread_sleeps
      (a delayed/blocking-shaped primitive) + time_date_logic
    - `fetch(url, {telemetry: data})` -> io (network call) + exfiltration_
      camouflage (disguised traffic) -- the whole point of the sensor
    - `Object.freeze(x)` -> immutability_locks + safety (defensive freezing)
    - `Atomics.wait(...)` -> sync_locks (coordination) + thread_sleeps
      (blocks the calling agent)
    - `new RegExp(x)` -> memory_alloc (object instantiation) + regex_execution
    - `mySet.delete(x)` -> cleanup (bare `delete` keyword) + state_mutation
      (`.delete(` method call) -- same token, two real signatures
    - `private foo() {}` -> args (captures the whole signature) +
      encapsulation (private modifier)
    """
    assert TYPESCRIPT_RULES["cleanup"].search("clearTimeout(id);")
    assert TYPESCRIPT_RULES["time_date_logic"].search("clearTimeout(id);")

    set_timeout = "setTimeout(fn, 100);"
    assert TYPESCRIPT_RULES["concurrency"].search(set_timeout)
    assert TYPESCRIPT_RULES["thread_sleeps"].search(set_timeout)
    assert TYPESCRIPT_RULES["time_date_logic"].search(set_timeout)

    fetch_camo = "fetch(url, {telemetry: data})"
    assert TYPESCRIPT_RULES["io"].search(fetch_camo)
    assert TYPESCRIPT_RULES["exfiltration_camouflage"].search(fetch_camo)

    freeze = "Object.freeze(x)"
    assert TYPESCRIPT_RULES["immutability_locks"].search(freeze)
    assert TYPESCRIPT_RULES["safety"].search(freeze)

    atomics_wait = "Atomics.wait(a, 0, 0)"
    assert TYPESCRIPT_RULES["sync_locks"].search(atomics_wait)
    assert TYPESCRIPT_RULES["thread_sleeps"].search(atomics_wait)

    new_regexp = "new RegExp(x)"
    assert TYPESCRIPT_RULES["memory_alloc"].search(new_regexp)
    assert TYPESCRIPT_RULES["regex_execution"].search(new_regexp)

    set_delete = "mySet.delete(x);"
    assert TYPESCRIPT_RULES["cleanup"].search(set_delete)
    assert TYPESCRIPT_RULES["state_mutation"].search(set_delete)

    private_method = "private foo(x: number) {"
    assert TYPESCRIPT_RULES["args"].search(private_method)
    assert TYPESCRIPT_RULES["encapsulation"].search(private_method)


def test_typescript_redos_immunity_sweep():
    """
    ReDoS immunity sweep across typescript's remaining rules with
    unbounded-looking quantifiers, verified via a systematic scaling sweep
    (n=2000/4000/8000/16000/32000) before writing this test.
    """
    assert_redos_immune(TYPESCRIPT_RULES["args"], "function foo(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["args"], "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["class_start"], "class Foo<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["generics"], "<Foo" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["decorators"], "@foo(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["_dependency_capture"], "import " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["_named_token_capture"], "import {" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["import"], "import " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["rce_funnel"], "child_process.exec(" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["doc"], "/**" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(TYPESCRIPT_RULES["ownership"], "@author " + " " * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert TYPESCRIPT_RULES["func_start"].search("function foo() {}")
    assert TYPESCRIPT_RULES["class_start"].search("class Foo {}")
    assert TYPESCRIPT_RULES["spec_exposure"].search("[SPEC-123]")
