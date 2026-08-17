"""cpp strict structural-signature coverage.

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

from _strict_harness import _best_of_timing, assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# TEST 3: THE C++ MACRO MULTI-LINE SPIRAL
# Reference: language_standards.py (Line ~1020)
# ==============================================================================
def test_cpp_macro_multiline_spiral():
    """
    Proves the C++ function spawner respects the (?![ \t]*#) negative lookaheads
    and does not cross into preprocessor directives to build hallucinated functions.
    """
    cpp_func = LANGUAGE_DEFINITIONS["cpp"]["rules"]["func_start"]

    # The Pathological String: A dangling return type that falls into a massive macro map.
    poison_cpp = "std::vector<int>\n" + "#define FOO 1\n" * 1000 + "myFunc() {"

    assert_redos_immune(cpp_func, poison_cpp)

    # Prove it actually stops at the macro and DOES NOT match the return type!
    # Instead of finding 0 matches, it will instantly skip the macros and find
    # "myFunc() {" as a valid, return-type-less constructor at the end of the file.
    matches = list(cpp_func.finditer(poison_cpp))
    assert len(matches) == 1, "Failed to safely skip the macros!"
    assert matches[0].group(1) == "myFunc", "Matched the wrong part of the string!"


# ==============================================================================
# CPP: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #774, part of epic #518)
# ==============================================================================
# NOTE: filed as one of 6 new sub-issues (#773-778) after auditing and
# rejecting the epic's founding premise that C/C++/C#/COBOL/Rust/TypeScript
# already had adequate coverage -- see #518's updated "Why" section. This
# language previously had only two isolated regression tests
# (test_cpp_macro_multiline_spiral covering func_start's macro-spiral ReDoS,
# and the cpp half of test_thermodynamic_operator_collisions covering
# bitwise_ops vs iostream `<<`), not the full per-signature template. Both
# are folded into this suite below rather than duplicated.
CPP_RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]

_CPP_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x > 0) {", "int x = 1;"),
    ("args", "int foo(int a, int b) {", "foo(a, b);"),
    ("structural_boundaries", "return x;", "x = 1;"),
    ("func_start", "int foo(int a) {", "if (x) {"),
    ("class_start", "class Foo {", "int x;"),
    ("safety", "std::unique_ptr<Foo> p;", "x = 1;"),
    ("safety_bypasses", "void* p;", "int* p;"),
    ("high_risk_execution", 'system("ls");', 'printf("hi");'),
    ("io", 'std::ifstream f("x");', "malloc(10);"),
    ("api", "public:\n    void foo();", "private:\n    void bar();"),
    ("state_mutation", "x = 5;", "if (x == 5)"),
    ("dead_code", "// if (x) foo();", "// just a note"),
    ("doc", "/** @brief does X */", "// just a note"),
    ("test", "TEST(Foo, Bar) {", "x = 1;"),
    ("concurrency", "std::thread t(f);", "x = 1;"),
    ("ui_framework", "Q_OBJECT", "x = 1;"),
    ("closures", "[x](int y) { return x + y; }", "int x;"),
    ("globals", "extern int x;", "int x;"),
    ("decorators", "[[nodiscard]] int foo();", "int foo();"),
    ("generics", "template<typename T> void foo();", "void foo();"),
    ("comprehensions", "std::ranges::sort(v);", "x = 1;"),
    ("scientific", "Eigen::MatrixXd m;", "int x;"),
    ("reflection_metaprogramming", "if constexpr (x) {}", "if (x) {}"),
    ("import", "#include <vector>", "#define FOO 1"),
    ("ownership", "// Author: Jane Doe", "// just a note"),
    ("planned_debt", "// TODO: fix this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "[SPEC-123]", "// just a note"),
    ("ssr_boundaries", "FCGI_Accept();", "x = 1;"),
    ("events", "emit signal();", "x = 1;"),
    ("dependency_injection", "IServiceCollection services;", "x = 1;"),
    ("macros", "#define FOO 1", "int x = 1;"),
    ("pointers", "int *p = &x;", "int x = 1;"),
    ("memory_alloc", "new Foo();", "x = 1;"),
    ("inline_asm", 'asm("nop");', "x = 1;"),
    ("telemetry", 'logger.info("msg");', "x = 1;"),
    ("debug_prints", "std::cout << x;", "x = 1;"),
    ("explicit_casts", "int x = (int*)ptr;", "int x;"),
    ("panics_and_aborts", 'throw std::runtime_error("x");', "return 0;"),
    ("thread_sleeps", "std::this_thread::sleep_for(1s);", "x = 1;"),
    ("bitwise_ops", "x ^= y;", "x = a + 2;"),
    ("sync_locks", "std::mutex m;", "x = 1;"),
    ("immutability_locks", "const int x = 1;", "int x = 1;"),
    ("cleanup", "delete p;\nfclose(f);", "new Foo();"),
    ("encapsulation", "private:\n    int x;", "public:\n    int x;"),
    ("listeners", "connect(a, b);", "x = 1;"),
    ("test_skip", "mock();", "test_run();"),
    ("serialization_parsing", "nlohmann::json j;", "x = 1;"),
    ("regex_execution", "std::regex_match(s, r);", "x = 1;"),
    ("time_date_logic", "std::chrono::system_clock::now();", "x = 1;"),
    ("ipc_rpc_bridges", "shm_open(name, 0, 0);", "x = 1;"),
]


@pytest.mark.parametrize("signature,positive,negative", _CPP_SIMPLE_CASES)
def test_cpp_signature_positive_and_negative(signature, positive, negative):
    pattern = CPP_RULES[signature]
    assert pattern is not None, f"cpp's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"cpp {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"cpp {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_cpp_dependency_capture_extracts_include_and_import_targets():
    dep = CPP_RULES["_dependency_capture"]
    m = dep.search('#include "myheader.hpp"')
    assert m and m.group(1) == "myheader.hpp"

    m2 = dep.search("#include <vector>")
    assert m2 and m2.group(1) == "vector"

    m3 = dep.search("import my.module;")
    assert m3 and m3.group(2) == "my.module"


def test_cpp_api_boundary_regression():
    """
    Real bug found and fixed (Rule 9): `public:`, `__declspec(dllexport)`,
    and `__attribute__((visibility("default")))` all end in non-word
    characters (`:`/`)`) but shared a trailing `\\b` with word-ending
    `export module`/`export import`/`export class` -- the boundary could
    never fire for the realistic forms (whitespace/newline always follows).
    """
    old_pattern = re.compile(
        r"\b(public:|export\s+module|export\s+import|export\s+class|__declspec\(dllexport\)|"
        r'__attribute__\(\(visibility\("default"\)\)\))\b|^[ \t]*export\b(?!\s*module)',
        re.M,
    )
    assert not old_pattern.search("public:\n    void foo();"), "sanity check: bug must reproduce (public:)"
    assert not old_pattern.search("__declspec(dllexport) void foo();"), "sanity check: bug must reproduce (declspec)"

    api = CPP_RULES["api"]
    assert api.search("public:\n    void foo();")
    assert api.search("__declspec(dllexport) void foo();")
    assert api.search('__attribute__((visibility("default"))) void foo();')
    assert api.search("export module foo;"), "the already-working export forms must still work"
    assert api.search("export class Foo {};")


def test_cpp_safety_bypasses_void_pointer_boundary_regression():
    """
    Real bug found and fixed (Rule 9): `void\\s*\\*` ends in `*` (non-word)
    but shared a trailing `\\b` with word-ending `std::any` -- only fired if
    a word char immediately followed the `*` with zero whitespace
    (`void *p`), breaking on the equally common `void* p`/`void * p` forms
    and any non-identifier continuation like a cast (`(void*)src`).
    """
    old_pattern = re.compile(r"\b(std::any|void\s*\*)\b|catch\s*\(\s*\.\.\.\s*\)")
    assert not old_pattern.search("void* generic_ptr;"), "sanity check: bug must reproduce"
    assert not old_pattern.search("(void*)src"), "sanity check: bug must reproduce"

    safety_bypasses = CPP_RULES["safety_bypasses"]
    assert safety_bypasses.search("void* generic_ptr;")
    assert safety_bypasses.search("void * generic_ptr;")
    assert safety_bypasses.search("(void*)src")
    assert safety_bypasses.search("void *generic_ptr;"), "the already-working zero-space form must still work"
    assert safety_bypasses.search("std::any x;"), "the already-working std::any form must still work"


def test_cpp_test_skip_empty_call_boundary_regression():
    """
    Real bug found and fixed (Rule 10): `mock\\(`/`fake\\(` end in a literal
    `(` but shared a trailing `\\b` with word-ending siblings -- broke on
    the truly-empty-argument call form (`mock()`), same shape already found
    and fixed in C (#773).
    """
    old_pattern = re.compile(r"\b(GTEST_SKIP|test\.skip|it\.skip|mock\(|fake\()\b")
    assert not old_pattern.search("mock();"), "sanity check: bug must reproduce"

    test_skip = CPP_RULES["test_skip"]
    assert test_skip.search("mock();")
    assert test_skip.search("fake();")
    assert test_skip.search("GTEST_SKIP();"), "the already-working GTEST_SKIP form must still work"


def test_cpp_encapsulation_total_breakage_regression():
    """
    Real bug found and fixed (Rule 9): ALL THREE alternatives
    (`private:`/`protected:`/`internal:`) end in `:` (non-word) and the
    group had no word-ending sibling at all -- the trailing `\\b` could
    never fire against the realistic form (always followed by whitespace or
    a newline, never a word character), meaning this rule never matched
    anything, ever.
    """
    old_pattern = re.compile(r"\b(private:|protected:|internal:)\b")
    assert not old_pattern.search("private:\n    int x;"), "sanity check: bug must reproduce"
    assert not old_pattern.search("protected:\n    int y;"), "sanity check: bug must reproduce"
    assert not old_pattern.search("internal:\n    int z;"), "sanity check: bug must reproduce"

    encapsulation = CPP_RULES["encapsulation"]
    assert encapsulation.search("private:\n    int x;")
    assert encapsulation.search("protected:\n    int y;")
    assert encapsulation.search("internal:\n    int z;")


def test_cpp_ui_framework_qt_boundary_regression():
    """
    Real bug found and fixed (Rule 9): `slots:`/`signals:` end in `:`
    (non-word) but shared a trailing `\\b` with word-ending siblings --
    broke on the realistic Qt form (always followed by a newline, never a
    word character). `ImGui::` also ends in non-word (`::`) but verified
    self-healing: real usage is always immediately followed by an
    identifier (`ImGui::Begin(...)`), so it was left alone.
    """
    old_pattern = re.compile(r"\b(Q_OBJECT|slots:|signals:|QWidget|wxFrame|ImGui::|Fl_Window)\b")
    assert not old_pattern.search("slots:\n    void onClick();"), "sanity check: bug must reproduce"
    assert not old_pattern.search("signals:\n    void clicked();"), "sanity check: bug must reproduce"

    ui_framework = CPP_RULES["ui_framework"]
    assert ui_framework.search("slots:\n    void onClick();")
    assert ui_framework.search("signals:\n    void clicked();")
    assert ui_framework.search('ImGui::Begin("Window");'), "the self-healing ImGui:: form must still work"
    assert ui_framework.search("Q_OBJECT"), "the already-working bare-keyword form must still work"


def test_cpp_reflection_metaprogramming_sizeof_ellipsis_boundary_regression():
    """
    Real bug found and fixed (Rule 9): `sizeof...` ends in `.` (non-word)
    but shared a trailing `\\b` with word-ending siblings -- the realistic
    form (`sizeof...(Args)`) is immediately followed by `(`, also non-word,
    so no boundary transition ever occurs and this alternative could never
    fire (unlike most Rule 9 findings, there is no realistic form where it
    would self-heal).
    """
    old_pattern = re.compile(
        r"\b(if\s+constexpr|if\s+consteval|std::enable_if|std::is_same|std::any_cast|std::bit_cast|decltype|sizeof\.\.\.)\b|#define\s+[a-zA-Z_]"
    )
    assert not old_pattern.search("sizeof...(Args)"), "sanity check: bug must reproduce"

    reflection = CPP_RULES["reflection_metaprogramming"]
    assert reflection.search("sizeof...(Args)")
    assert reflection.search("decltype(x)"), "the already-working decltype form must still work"


def test_cpp_dead_code_block_comment_completeness_regression():
    """
    Real bug found and fixed (Rule 12): only checked `//` line comments,
    entirely missing `/* */` block comments despite cpp being a
    `standard_block` language where both styles are equally idiomatic.
    """
    old_pattern = re.compile(
        r"//[ \t]*(?:if|for|while|auto|class|struct|std::cout|std::print|printf|void|int|return)\b"
    )
    assert not old_pattern.search("/* if (x) foo(); */"), "sanity check: bug must reproduce"

    dead_code = CPP_RULES["dead_code"]
    assert dead_code.search("/* if (x) foo(); */")
    assert dead_code.search("// if (x) foo();"), "the already-working line-comment form must still work"


def test_cpp_func_start_nested_template_return_type_regression():
    """
    Real bug found and fixed (Rule 11): the return-type's flat `<[^>]*>`
    broke on any nested template argument (`std::vector<std::pair<int,
    int>>`, `std::map<K, std::vector<V>>`) -- extremely common in real
    C++ -- causing the whole rule to never match at all, since no fallback
    path exists once the return type fails to consume correctly. Extended
    to a bounded 2-level nesting tolerance.
    """
    func_start = CPP_RULES["func_start"]
    m1 = func_start.search("std::vector<std::pair<int,int>> foo() {")
    assert m1 and m1.group(1) == "foo"
    m2 = func_start.search("std::map<std::string, std::vector<int>> bar() {")
    assert m2 and m2.group(1) == "bar"


def test_cpp_class_start_nested_template_default_arg_regression():
    """
    Real bug found and fixed (Rule 11): the template-skip's flat `<[^>]*>`
    broke on any nested default template argument (`template<typename T =
    std::vector<int>> class Foo`), truncating at the inner `>` and failing
    to match at all on the (very common) single-line form -- the multi-line
    form only appeared to "work" because the optional template group could
    be skipped entirely via backtracking, re-anchoring on a later line's
    bare `class Bar`.
    """
    class_start = CPP_RULES["class_start"]
    m1 = class_start.search("template<typename T = std::vector<int>> class Foo {")
    assert m1 and m1.group(1) == "Foo"
    m2 = class_start.search("template<typename T, typename U = std::pair<int,int>>\nclass Bar {")
    assert m2 and m2.group(1) == "Bar"


def test_cpp_func_start_if_constexpr_false_positive_regression():
    """
    Real bug found and fixed: the return-type loop never excluded
    control-flow keywords from being consumed as a generic return-type
    word -- only the later identifier-capture shield excluded them from
    being the FUNCTION NAME itself. This let a two-word control-flow form
    slip through: `if constexpr (x) {}` falsely matched with "constexpr"
    captured as the function name (`if` consumed by the loop, `constexpr`
    landing in the identifier position, which the old shield didn't
    reject). Found via the ambiguity sweep, not pre-derived.
    """
    func_start = CPP_RULES["func_start"]
    assert not func_start.search("if constexpr (x) {}"), "if-constexpr must never be captured as a function"
    assert not func_start.search("if consteval (x) {}"), "if-consteval must never be captured as a function"
    assert not func_start.search("if (x) {"), "the already-working plain if-exclusion must still hold"
    assert not func_start.search("for (int i = 0; i < 10; i++) {")
    assert not func_start.search("while (x) {")
    assert not func_start.search("switch (x) {")
    m = func_start.search("int myFunc() {")
    assert m and m.group(1) == "myFunc", "a real function must still match after the control-flow shield"


def test_cpp_explicit_casts_bare_template_false_positive_regression():
    """
    Real correctness bug found while writing the negative-case tests
    (per the epic's own discipline that test-writing is itself a
    bug-finding step): the bare `<\\s*[A-Za-z_]\\w*\\s*>` alternative had no
    requirement that this actually be used as a cast -- it fired on ANY
    single-identifier template instantiation (`std::vector<int>`,
    `std::unique_ptr<Foo>`, `Container<T>`), which is an ordinary
    declaration, not a cast. Since every modern C++ file is full of these,
    this was a major over-broad false-positive source.
    """
    old_pattern = re.compile(
        r"\b(?:static_cast|dynamic_cast|reinterpret_cast|const_cast|bit_cast)\b|<\s*[A-Za-z_]\w*\s*>|"
        r"\(\s*(?:int|float|double|char|bool|long|short|unsigned|signed)\s*\)\s*[a-zA-Z_]"
    )
    assert old_pattern.search("std::vector<int> v;"), "sanity check: false-positive bug must reproduce"
    assert old_pattern.search("std::unique_ptr<Foo> p;"), "sanity check: false-positive bug must reproduce"

    explicit_casts = CPP_RULES["explicit_casts"]
    assert not explicit_casts.search("std::vector<int> v;")
    assert not explicit_casts.search("std::unique_ptr<Foo> p;")
    assert not explicit_casts.search("Container<T> c;")
    assert explicit_casts.search("static_cast<int>(x);"), "the already-working named-cast form must still work"
    assert explicit_casts.search("gsl::narrow_cast<int>(x);"), "a real functional-cast-style template must still match"


def test_cpp_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template: already found in C
    (cast syntax overlapping pointer-asterisk repetition) -- check for the
    same overlap given C++'s shared C-style cast syntax. Found a real
    coverage gap: the C-style-cast alternative required a bare `(int)` with
    no asterisk, so it never matched C++'s equally valid, common C-style
    POINTER cast (`(int*)ptr`) at all. Extended to allow pointer asterisks
    (O(1) alternation per the same fix already applied in C), then verified
    no false collision with `pointers` on either a bare cast or a cast
    alongside a real pointer declaration.
    """
    old_pattern = re.compile(
        r"\b(?:static_cast|dynamic_cast|reinterpret_cast|const_cast|bit_cast)\b|"
        r"\b[a-zA-Z_]\w*<\s*[A-Za-z_]\w*\s*>\s*\(|"
        r"\(\s*(?:int|float|double|char|bool|long|short|unsigned|signed)\s*\)\s*[a-zA-Z_]"
    )
    assert not old_pattern.search("int x = (int*)ptr;"), "sanity check: coverage gap must reproduce"

    explicit_casts = CPP_RULES["explicit_casts"]
    pointers = CPP_RULES["pointers"]

    assert explicit_casts.search("int x = (int*)ptr;")

    bare_cast = "double val = (double)x;"
    assert explicit_casts.search(bare_cast)
    assert not pointers.search(bare_cast)

    cast_and_ptr = "int *y = (int*)malloc(10);"
    assert explicit_casts.search(cast_and_ptr)
    assert pointers.search(cast_and_ptr), "a real pointer declaration alongside a cast should still fire pointers"


def test_cpp_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template, and this language's
    own pre-existing regression test (test_cpp_macro_multiline_spiral),
    folded into this suite: a multi-line #define spiral must not hallucinate
    a function match by skipping past the macros to reach a later dangling
    identifier.
    """
    func_start = CPP_RULES["func_start"]
    macros = CPP_RULES["macros"]

    poison = "std::vector<int>\n" + "#define FOO 1\n" * 1000 + "myFunc() {"
    assert_redos_immune(func_start, poison, timeout_sec=3.0)
    matches = list(func_start.finditer(poison))
    assert len(matches) == 1, "func_start should skip the macro run, not hallucinate a match across it"
    assert matches[0].group(1) == "myFunc"
    assert macros.search("#define FOO 1")


def test_cpp_bitwise_ops_vs_iostream_no_false_collision():
    """
    Known ambiguity pattern from the issue template, and this language's
    own pre-existing regression test (the cpp half of
    test_thermodynamic_operator_collisions), folded into this suite:
    `bitwise_ops` deliberately excludes bare `<<`/`>>` (to avoid firing on
    `std::cout <<`/`std::cin >>` streams) while still catching the
    unambiguous compound-assignment forms.
    """
    bitwise_ops = CPP_RULES["bitwise_ops"]
    assert not bitwise_ops.search("std::cout << x << std::endl;")
    assert not bitwise_ops.search("std::cin >> x;")
    assert bitwise_ops.search("x <<= 2;")
    assert bitwise_ops.search("x >>= 2;")
    assert bitwise_ops.search("x &= mask;")


def test_cpp_intentional_double_classification_sweep():
    """
    Ambiguity sweep finding: several C++ constructs legitimately fire two
    signatures representing different perspectives on the same underlying
    action, or share a literal keyword between two independently-authored
    rule lists -- intentional, not false collisions:
    - `int foo(int a, int b) {` -> args + func_start (a real function
      signature is simultaneously a parameter block and a function start)
    - `TEST(Foo, Bar) {` -> test + func_start + args (GTest's TEST macro has
      the identical syntactic shape as a bare-return-type function
      definition/call at the regex level -- a real, accepted limitation)
    - `class Foo {` -> class_start + structural_boundaries (`class` is a
      literal keyword in both rules' own lists)
    - `void* p;` -> safety_bypasses + structural_boundaries (`void` is a
      literal keyword in both rules' own lists)
    - `// if (x) foo();` -> dead_code + branch (`if` is a literal keyword in
      both rules' own lists)
    - `template<typename T> void foo();` -> generics + structural_boundaries
      (`template`/`typename`/`void` are literal keywords in both)
    - `if constexpr (x) {}` -> reflection_metaprogramming + branch (`if`) +
      immutability_locks (`constexpr`) -- both explicitly list these
      keywords independently
    - `#define FOO 1` -> macros + reflection_metaprogramming (both
      explicitly define `#define` as their own signal)
    - `x ^= y;` -> bitwise_ops + state_mutation (both explicitly list `^=`
      in their own compound-assignment alternatives)
    - `std::mutex m;` -> sync_locks + concurrency (both explicitly list
      `std::mutex` in their own keyword lists)
    - `delete p; fclose(f);` -> cleanup + io (both explicitly list `fclose`
      in their own keyword lists)
    - `int *p = &x;` -> pointers + state_mutation (state_mutation's bare
      `&(?!\\s*const)` alternative treats any address-of/reference operator
      as a mutation signal, independent of pointers' own dedicated capture)
    """
    func_sig = "int foo(int a, int b) {"
    assert CPP_RULES["args"].search(func_sig)
    assert CPP_RULES["func_start"].search(func_sig)

    test_macro = "TEST(Foo, Bar) {"
    assert CPP_RULES["test"].search(test_macro)
    assert CPP_RULES["func_start"].search(test_macro)
    assert CPP_RULES["args"].search(test_macro)

    class_decl = "class Foo {"
    assert CPP_RULES["class_start"].search(class_decl)
    assert CPP_RULES["structural_boundaries"].search(class_decl)

    void_ptr = "void* p;"
    assert CPP_RULES["safety_bypasses"].search(void_ptr)
    assert CPP_RULES["structural_boundaries"].search(void_ptr)

    dead_if = "// if (x) foo();"
    assert CPP_RULES["dead_code"].search(dead_if)
    assert CPP_RULES["branch"].search(dead_if)

    tpl = "template<typename T> void foo();"
    assert CPP_RULES["generics"].search(tpl)
    assert CPP_RULES["structural_boundaries"].search(tpl)

    if_constexpr = "if constexpr (x) {}"
    assert CPP_RULES["reflection_metaprogramming"].search(if_constexpr)
    assert CPP_RULES["branch"].search(if_constexpr)
    assert CPP_RULES["immutability_locks"].search(if_constexpr)

    define_line = "#define FOO 1"
    assert CPP_RULES["macros"].search(define_line)
    assert CPP_RULES["reflection_metaprogramming"].search(define_line)

    xor_assign = "x ^= y;"
    assert CPP_RULES["bitwise_ops"].search(xor_assign)
    assert CPP_RULES["state_mutation"].search(xor_assign)

    mutex_decl = "std::mutex m;"
    assert CPP_RULES["sync_locks"].search(mutex_decl)
    assert CPP_RULES["concurrency"].search(mutex_decl)

    cleanup_call = "delete p;\nfclose(f);"
    assert CPP_RULES["cleanup"].search(cleanup_call)
    assert CPP_RULES["io"].search(cleanup_call)

    ptr_decl = "int *p = &x;"
    assert CPP_RULES["pointers"].search(ptr_decl)
    assert CPP_RULES["state_mutation"].search(ptr_decl)


def test_cpp_spec_exposure_redos_regression():
    """
    Real bug found and fixed (Rule 14): adjacent unbounded quantifiers with
    overlapping character sets (`\\d+` next to `[^\\]]*`) -- the same ReDoS
    shape already found and fixed independently in embedded_python, css,
    tcl, matlab, scheme, typescript, rust, and c earlier in this epic (the
    9th hit).
    """
    old_pattern = re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I)
    # Scale-relative sanity check (not an absolute wall-clock threshold,
    # which is flaky across CI hardware of varying speed): a payload-size
    # doubling should cost ~4x on the quadratic OLD pattern, vs ~2x for
    # linear.
    small_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 4000 + " " * 4000)
    large_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 8000 + " " * 8000)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: old pattern was expected to show quadratic (~4x) scaling on a payload "
        f"doubling, but only scaled {ratio:.2f}x ({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    spec_exposure = CPP_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + " " * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123]")
    assert spec_exposure.search("[audit]")


def test_cpp_func_start_redos_regression():
    """
    Real ReDoS bug found and fixed (Rule 14): the return-type loop's
    trailing `[ \\t\\n]+` and the parameter block's leading `[ \\t\\n]*` are
    two effectively-adjacent unbounded whitespace quantifiers -- once a real
    function never follows (no `(` anywhere), the engine must retry every
    possible split of the same trailing whitespace run across both gaps,
    O(n^2). Confirmed ~4x/doubling, 2.8s at n=32000 on a bare
    `"int foo" + " "*n` payload before the fix. Bounded both to `{1,200}`.
    """
    func_start = CPP_RULES["func_start"]
    assert_redos_immune(func_start, "int foo" + " " * 100000, timeout_sec=3.0)
    m = func_start.search("int myFunc() {")
    assert m and m.group(1) == "myFunc"


def test_cpp_redos_immunity_sweep():
    """
    ReDoS immunity sweep across cpp's remaining rules with unbounded-looking
    quantifiers, verified via a systematic scaling sweep (n=2000/4000/8000/
    16000/32000) before writing this test.
    """
    assert_redos_immune(CPP_RULES["args"], "foo(int " + "a," * 16000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["args"], "std::vector<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["func_start"], "std::vector<" + "a," * 16000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["func_start"], "__attribute__((" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["class_start"], "struct " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["class_start"], "template<" + "a," * 16000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["closures"], "[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["decorators"], "[[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["generics"], "template<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["explicit_casts"], "(int" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["explicit_casts"], "(int " + "* " * 16000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["_dependency_capture"], "#include <" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["import"], "#include <" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CPP_RULES["pointers"], "&" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert CPP_RULES["func_start"].search("int myFunc() {")
    assert CPP_RULES["class_start"].search("class Foo {")
    assert CPP_RULES["explicit_casts"].search("static_cast<int>(x);")

def test_cpp_branch_deep_cases():
    """Adversarial/Deep cases for branch."""
    p = CPP_RULES["branch"]
    # Positive
    assert p.search("co_yield 5;")
    assert p.search("co_await my_task();")
    assert p.search("if constexpr (sizeof(T) > 4)")
    assert p.search("for (auto&& x : v)")
    assert p.search("catch (...) {")
    assert p.search("x && y")
    assert p.search("a ? b : c")
    assert p.search("while(true)")
    assert p.search("do { } while(0);")
    assert p.search("else if(x)")
    # Negative
    assert not p.search("difftime()")
    assert not p.search("gator()")
    assert not p.search("a & b")
    assert not p.search("a | b")
    assert not p.search("catch_error()")
    assert not p.search("default_value = 1")

def test_cpp_args_deep_cases():
    """Adversarial/Deep cases for args."""
    p = CPP_RULES["args"]
    # Positive
    assert p.search("void Foo::bar(const std::vector<int>& v)")
    assert p.search("TargetClass::operator=(const TargetClass& other)")
    assert p.search("Foo::Bar<Baz<int>>(int x)")
    assert p.search("[a, &b](int x)")
    assert p.search("MyClass(std::string name)")
    assert p.search("void* operator new(size_t size)")
    assert p.search("Foo::operator==(const Foo& other)")
    assert p.search("auto my_func(auto&& x)")
    # Negative
    assert not p.search("if (int x = foo())")
    assert not p.search("(int)x")
    assert not p.search("std::vector<int> v(10);")
    assert not p.search("for (int i = 0; i < 10; ++i)")

def test_cpp_func_start_deep_cases():
    """Adversarial/Deep cases for func_start."""
    p = CPP_RULES["func_start"]
    # Positive
    assert p.search("std::vector<int>\nmyFunc() {")
    assert p.search("[[nodiscard]] constexpr int Foo::bar() const noexcept {")
    assert p.search("inline void* my_alloc(size_t size) {")
    assert p.search("TargetClass::operator=(const TargetClass& other) {")
    assert p.search("template <typename T> void foo() {")
    assert p.search("int \n main \n (int argc) {")
    assert p.search("__attribute__((always_inline)) void fast() {")
    # Negative
    assert not p.search("if (x == 1) {")
    assert not p.search("while (true) {")
    assert not p.search("struct MyStruct {")
    assert not p.search("class MyClass {")
    assert not p.search("else if (x) {")
    assert not p.search("try {")
    assert not p.search("catch (const std::exception& e) {")

def test_cpp_class_start_deep_cases():
    """Adversarial/Deep cases for class_start."""
    p = CPP_RULES["class_start"]
    # Positive
    assert p.search("class MyClass {")
    assert p.search("struct MyStruct : public Base {")
    assert p.search("template <typename T> class Foo {")
    assert p.search("enum class Color {")
    assert p.search("enum struct Shape {")
    assert p.search("class [[nodiscard]] MyClass {")
    assert p.search('class __attribute__((visibility("default"))) MyClass {')
    assert p.search("template <typename T = std::vector<int>>\nclass Bar {")
    # Negative
    assert not p.search("enum Color {")
    assert not p.search("class_name = 5;")
    assert not p.search("int x_class = 1;")

def test_cpp_structural_boundaries_deep_cases():
    """Adversarial/Deep cases for structural_boundaries."""
    p = CPP_RULES["structural_boundaries"]
    # Positive
    assert p.search("namespace my_ns {")
    assert p.search("class MyClass {")
    assert p.search("struct MyStruct {")
    assert p.search("return 0;")
    assert p.search("inline void foo();")
    assert p.search("export module foo;")
    assert p.search("using namespace std;")
    assert p.search("friend class Bar;")
    assert p.search("auto x = 5;")
    # Negative
    assert not p.search("x_namespace = 1;")
    assert not p.search("my_return = 0;")
    assert not p.search("int export_val = 5;")

