"""fortran strict structural-signature coverage.

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
import re

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


def test_fortran_state_mutation_redos_immunity_and_kind_exclusion():
    """
    Two bugs, found together: the ReDoS sweep caught the quadratic blowup,
    and fixing it (adding a real \\b anchor) also fixed a pre-existing leak
    in the KIND=/LEN=/etc exclusion -- the original negative lookahead only
    blocked a match starting exactly at "KIND", not one starting mid-word
    ("KIND = 5" still matched "IND = " starting at its 2nd character, since
    \\bKIND doesn't apply there). Confirmed this leak existed before the
    ReDoS fix too, via the pattern's original (unbounded) form.
    """
    pattern = LANGUAGE_DEFINITIONS["fortran"]["rules"]["state_mutation"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("myvar = 5")
    assert pattern.search("mystruct%field = 1")
    assert not pattern.search("KIND = 5"), "Failed to exclude the KIND= false-positive trap"
    assert not pattern.search("LEN = 10"), "Failed to exclude the LEN= false-positive trap"


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


def test_fortran_pfunit_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["fortran"]["rules"]
    assert r["test"].search("@test")
    assert r["test"].search("@assertEqual(1, 1)")


# ==============================================================================
# FORTRAN: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #581, part of epic #518)
# ==============================================================================
FORTRAN_RULES = LANGUAGE_DEFINITIONS["fortran"]["rules"]

_FORTRAN_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "IF (x == 1) THEN", "X = 1"),
    ("args", "SUBROUTINE foo(x)", "X = 1"),
    ("structural_boundaries", "PROGRAM main", "CALL foo(x)"),
    ("func_start", "SUBROUTINE foo(x)", "END SUBROUTINE foo"),
    ("class_start", "MODULE mymod", "SUBROUTINE foo(x)"),
    ("safety", "IMPLICIT NONE", "X = 1"),
    ("safety_bypasses", "COMMON /blk/ x, y", "X = 1"),
    ("high_risk_execution", "GOTO 100", "X = 1"),
    ("io", "OPEN(10, FILE='x.txt')", "X = 1"),
    ("api", "SUBROUTINE foo()", "X = 1"),
    ("state_mutation", "X = 1", "CALL foo(x)"),
    ("dead_code", "C IF (x) THEN", "C just a note"),
    ("doc", "!> Doc comment", "! just a note"),
    ("test", "call assert_equal(x, y)", "X = 1"),
    ("concurrency", "SYNC ALL", "X = 1"),
    ("globals", "COMMON /blk/ x", "X = 1"),
    ("decorators", "!DIR$ SIMD", "! just a note"),
    ("generics", "GENERIC :: foo => bar", "X = 1"),
    ("comprehensions", "DO CONCURRENT (I=1:10)", "X = 1"),
    ("scientific", "SQRT(x)", "X = 1"),
    ("reflection_metaprogramming", "SELECT TYPE (x)", "X = 1"),
    ("import", "USE mymodule", "X = 1"),
    ("ownership", "! Author: Jane Doe", "X = 1"),
    ("planned_debt", "! TODO: fix this", "! done"),
    ("fragile_debt", "! HACK: workaround", "! clean"),
    ("spec_exposure", "[SPEC-123]", "! just a note"),
    ("events", "EVENT POST(x[1])", "X = 1"),
    ("macros", "#define FOO 1", "! just a note"),
    ("pointers", "POINTER :: p", "X = 1"),
    ("memory_alloc", "ALLOCATE(x(10))", "X = 1"),
    ("telemetry", "call log_info('msg')", "PRINT *, 'msg'"),
    ("debug_prints", "PRINT *, 'hi'", "call log_info('msg')"),
    ("explicit_casts", "INT(x)", "X = 1"),
    ("panics_and_aborts", "STOP", "X = 1"),
    ("thread_sleeps", "call sleep(5)", "X = 1"),
    ("bitwise_ops", "IAND(x, y)", "X = 1"),
    ("sync_locks", "LOCK(lock_var)", "X = 1"),
    ("immutability_locks", "PARAMETER (X = 1)", "X = 1"),
    ("cleanup", "DEALLOCATE(x)", "X = 1"),
    ("encapsulation", "PRIVATE", "PUBLIC"),
    ("serialization_parsing", "FORMAT(I5)", None),
    ("regex_execution", "INDEX(str, 'x')", "X = 1"),
    ("time_date_logic", "CALL DATE_AND_TIME(date, time)", "X = 1"),
    ("ipc_rpc_bridges", "CALL MPI_Send(buf, count, dtype)", "X = 1"),
]


@pytest.mark.parametrize("signature,positive,negative", _FORTRAN_SIMPLE_CASES)
def test_fortran_signature_positive_and_negative(signature, positive, negative):
    pattern = FORTRAN_RULES[signature]
    assert pattern is not None, f"fortran's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"fortran {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"fortran {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_fortran_dependency_capture_extracts_use_module_and_include_path():
    pattern = FORTRAN_RULES["_dependency_capture"]
    m = pattern.search("USE mymodule")
    assert m and m.group(1) == "mymodule" and m.group(2) is None

    m2 = pattern.search("INCLUDE 'foo.inc'")
    assert m2 and m2.group(2) == "foo.inc" and m2.group(1) is None


def test_fortran_func_start_excludes_end_and_requires_line_start():
    """
    func_start's negative lookahead excludes `END SUBROUTINE`/`END FUNCTION`
    ghosting, and (positional_anchored family) the match must anchor at the
    physical start of the line -- a FUNCTION/SUBROUTINE keyword appearing
    after other code on the same line must not count.
    """
    func_start = FORTRAN_RULES["func_start"]
    assert not func_start.search("END SUBROUTINE foo")
    assert not func_start.search("END FUNCTION foo")

    # column accuracy: SUBROUTINE appearing after other code on the same
    # physical line is not a real declaration and must not match
    assert not func_start.search("CALL bar()  SUBROUTINE foo(x)")

    # leading whitespace must still be tolerated (real Fortran is often indented)
    m = func_start.search("      SUBROUTINE foo(x)")
    assert m and m.group(1) == "foo"


def test_fortran_func_start_prefix_stacking_and_trailing_modifiers():
    """
    Real Fortran signatures stack prefixes (PURE RECURSIVE), legacy memory
    sizing (REAL*8), modern kinds (INTEGER(KIND=4)), derived types/classes
    (TYPE(x)/CLASS(x)), and trailing RESULT/BIND(C) modifiers. The bounded
    {0,5} groups and lookahead tail must tolerate all of these.
    """
    func_start = FORTRAN_RULES["func_start"]
    for line, name in [
        ("PURE RECURSIVE REAL FUNCTION foo(x)", "foo"),
        ("REAL*8 FUNCTION foo(x)", "foo"),
        ("INTEGER(KIND=4) FUNCTION foo(x)", "foo"),
        ("FUNCTION foo(x) RESULT(y)", "foo"),
        ("SUBROUTINE foo(x) BIND(C)", "foo"),
        ("TYPE(MyStruct) FUNCTION foo(x)", "foo"),
        ("CLASS(Obj) FUNCTION foo(x)", "foo"),
    ]:
        m = func_start.search(line)
        assert m and m.group(1) == name, f"func_start failed on {line!r}"


def test_fortran_class_start_type_form_with_and_without_extends():
    class_start = FORTRAN_RULES["class_start"]
    m = class_start.search("TYPE point")
    assert m and m.group(2) == "point"

    m2 = class_start.search("TYPE, EXTENDS(base) :: point")
    assert m2 and m2.group(2) == "point"


def test_fortran_decorators_dollar_boundary_regression():
    """
    Real bug found and fixed: `decorators`' shared trailing `\\b` broke the
    `!DIR$`/`cDEC$` alternatives (Rule 9 defect class -- a `\\b` right after
    a non-word literal like `$` can never fire when the next character is
    also non-word, and real compiler directives are always written with a
    space after the `$`, e.g. `!DIR$ SIMD`). Only the `!$OMP`/`!$ACC`
    alternatives (which end in a word character) ever matched under the old
    pattern.
    """
    old_pattern = re.compile(r"^[ \t]*(?:!DIR\$|cDEC\$|!\$OMP|!\$ACC)\b", re.I | re.M)
    realistic = "!DIR$ SIMD"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    decorators = FORTRAN_RULES["decorators"]
    assert decorators.search(realistic), "realistic space-after-$ directive still didn't match"
    assert decorators.search("cDEC$ ATTRIBUTES"), "legacy cDEC$ form regressed"
    assert decorators.search("!$OMP PARALLEL"), "OMP pragma form regressed"
    assert decorators.search("!$ACC KERNELS"), "ACC pragma form regressed"
    assert not decorators.search("! just a note")


def test_fortran_generics_trailing_boundary_regression():
    """
    Real bug found and fixed: `generics`' shared trailing `\\b` broke 3 of
    its 5 alternatives -- `GENERIC::`, `TYPE name(...)`, and `EXTENDS(...)`
    all end in a non-word character (`:` or `)`), so the boundary could
    only fire if the very next character happened to be a word character,
    never true for realistic code followed by whitespace/newline/EOF.
    """
    old_pattern = re.compile(
        r"\b(INTERFACE\s+ASSIGNMENT|INTERFACE\s+OPERATOR|GENERIC\s*::|"
        r"TYPE\s+[A-Za-z_]\w*\s*\([^)]*\)|EXTENDS\s*\([^)]*\))\b",
        re.I,
    )
    for realistic in ["GENERIC :: foo => bar", "TYPE point(k, n)", "EXTENDS(base)"]:
        assert not old_pattern.search(realistic), f"sanity check: bug must reproduce for {realistic!r}"

    generics = FORTRAN_RULES["generics"]
    assert generics.search("GENERIC :: foo => bar")
    assert generics.search("TYPE point(k, n)")
    assert generics.search("EXTENDS(base)")
    # alternatives that were already correct must still work
    assert generics.search("INTERFACE ASSIGNMENT (=)")
    assert generics.search("INTERFACE OPERATOR (+)")
    assert not generics.search("X = 1")


def test_fortran_io_write_trailing_comma_boundary_regression():
    """
    Real bug found and fixed: `io`'s WRITE alternative ends in a literal
    trailing comma (non-word) but shared a trailing `\\b` with the other,
    word-ending alternatives (OPEN/CLOSE/READ/...). A `\\b` right after
    that comma can only fire if the next character is a word character --
    never true for the overwhelmingly common realistic forms, where the
    comma is followed by `*`, a quote, or whitespace (`WRITE(10,*)`,
    `WRITE(10,'(I5)')`, `WRITE(10, x)`). This made file-unit WRITE
    detection almost never fire in practice, while the terminal-print
    exclusion (`WRITE(*,...)`/`WRITE(6,...)`) it was built around still
    worked correctly by not matching at all.
    """
    old_pattern = re.compile(
        r"\b(OPEN|CLOSE|READ|WRITE\s*\(\s*(?!\*|6\b)[^,]+,|INQUIRE|REWIND|BACKSPACE|ENDFILE|FLUSH|FORMAT)\b",
        re.I,
    )
    for realistic in ["WRITE(10,*) x", "WRITE(10, *) x", "WRITE(10,'(I5)') x"]:
        assert not old_pattern.search(realistic), f"sanity check: bug must reproduce for {realistic!r}"

    io = FORTRAN_RULES["io"]
    assert io.search("WRITE(10,*) x")
    assert io.search("WRITE(10, *) x")
    assert io.search("WRITE(10,'(I5)') x")
    # the terminal-print exclusion this rule is built around must still hold
    assert not io.search("WRITE(*,*) 'hi'")
    assert not io.search("WRITE(6,*) 'hi'")
    # other alternatives (already word-ending, never broken) must still work
    assert io.search("OPEN(10, FILE='x.txt')")


def test_fortran_safety_and_immutability_locks_intent_boundary_regression():
    """
    Real bug found and fixed in two separate rules sharing the same root
    cause: `safety`'s and `immutability_locks`'s `INTENT(...)` alternatives
    both end in a literal `)` (non-word), and both shared a trailing `\\b`
    with word-ending sibling alternatives. `INTENT(IN) :: x` (always
    followed by whitespace in real code) never matched under either rule.
    """
    old_safety = re.compile(
        r"\b(IMPLICIT\s+NONE|INTENT\s*\(\s*(?:IN|OUT|INOUT)\s*\)|ALLOCATABLE|SAVE|PARAMETER|VALUE|"
        r"ERROR\s+STOP|ASYNCHRONOUS|ASSOCIATED|ALLOCATED|PRESENT)\b",
        re.I,
    )
    old_immutability = re.compile(r"\b(?:parameter|intent[ \t]*\([ \t]*in[ \t]*\))\b", re.I)
    realistic = "INTENT(IN) :: x"

    assert not old_safety.search(realistic), "sanity check: safety bug must reproduce"
    assert not old_immutability.search(realistic), "sanity check: immutability_locks bug must reproduce"

    assert FORTRAN_RULES["safety"].search(realistic)
    assert FORTRAN_RULES["immutability_locks"].search(realistic)
    # sibling alternatives that were already correct must still work
    assert FORTRAN_RULES["safety"].search("IMPLICIT NONE")
    assert FORTRAN_RULES["immutability_locks"].search("PARAMETER (X = 1)")


def test_fortran_ipc_rpc_bridges_omp_prefix_boundary_regression():
    """
    Real bug found and fixed: `ipc_rpc_bridges`'s `OMP_` alternative ends
    in `_` (a word character), and was clearly intended as a prefix match
    for any OpenMP runtime call (`OMP_GET_THREAD_NUM`, `OMP_SET_NUM_THREADS`,
    etc). The shared trailing `\\b` requires the next character to be
    non-word, but real OMP runtime identifiers always continue with more
    word characters right after the prefix -- both sides being word
    characters, the boundary could never fire, making the alternative
    unreachable for its only realistic use case.
    """
    old_pattern = re.compile(
        r"(?i)\b(MPI_Init|MPI_Send|MPI_Recv|MPI_Bcast|EXECUTE_COMMAND_LINE|OMP_)\b",
    )
    realistic = "id = OMP_GET_THREAD_NUM()"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    ipc_rpc_bridges = FORTRAN_RULES["ipc_rpc_bridges"]
    assert ipc_rpc_bridges.search(realistic)
    assert ipc_rpc_bridges.search("CALL MPI_Send(buf, count, dtype)")
    assert ipc_rpc_bridges.search("CALL EXECUTE_COMMAND_LINE('ls')")
    assert not ipc_rpc_bridges.search("X = 1")


def test_fortran_state_mutation_kind_len_unit_exclusion():
    """
    state_mutation's negative lookahead excludes KIND=/LEN=/UNIT=/FMT=/
    FILE=/STATUS=/ACTION= from being misread as a real variable
    assignment (these are keyword-argument bindings inside a declaration
    or I/O statement, not state mutation).
    """
    state_mutation = FORTRAN_RULES["state_mutation"]
    assert not state_mutation.search("KIND = 4")
    assert not state_mutation.search("UNIT = 10")
    assert state_mutation.search("X = 1"), "a genuine assignment must still match"


def test_fortran_spec_exposure_strict_uppercase_only():
    """
    spec_exposure intentionally omits case-insensitivity to enforce strict
    uppercase [SPEC-XYZ]/[AUDIT-XYZ] tags and prevent prose collisions.
    """
    spec_exposure = FORTRAN_RULES["spec_exposure"]
    assert spec_exposure.search("[SPEC-123]")
    assert not spec_exposure.search("[spec-123]"), "lowercase must not match -- strict uppercase by design"


def test_fortran_dead_code_column_anchor_vs_free_form_inline_comment():
    """
    Lexical-family accuracy check (positional_anchored): the legacy
    `C`/`*` full-line comment alternative requires column-1 anchoring, but
    the modern `!` alternative is NOT column-anchored -- Fortran's `!`
    starts a comment anywhere on the line, so a stray `*` (multiplication)
    followed by code-like text elsewhere on the same line must not count,
    while a genuine trailing `!`-comment containing a structural keyword
    correctly does.
    """
    dead_code = FORTRAN_RULES["dead_code"]
    assert not dead_code.search("X = 5 * 2   CALL foo"), (
        "a non-column-1 '*' (multiplication) must not count as dead_code"
    )
    assert dead_code.search("X = 1  ! CALL something"), "a genuine trailing ! comment must still match"
    assert dead_code.search("C IF (x) THEN"), "column-1 legacy comment must still match"


def test_fortran_doc_vs_ownership_overlap_is_intentional():
    """
    Ambiguity sweep finding (mirrors the abap case): `doc` and `ownership`
    both fire on an "! Author: Jane Doe" header line -- both signatures
    are legitimately about traceability/metadata, and `ownership`
    additionally captures the specific author name (group 1) for
    downstream attribution, which `doc` does not attempt.
    """
    header = "! Author: Jane Doe"
    assert FORTRAN_RULES["doc"].search(header)
    m = FORTRAN_RULES["ownership"].search(header)
    assert m and m.group(1) == "Jane Doe"


def test_fortran_ownership_column_anchor_stricter_than_doc():
    """
    Positional-family accuracy check: `doc`'s Author/Description/Param/
    Return alternative tolerates leading whitespace before the `!`
    (`^[ \\t]*!`), but `ownership`'s equivalent alternative requires the
    comment character literally in column 1 (`^[cCdD*!]`, no leading
    whitespace group) -- an indented "! Author:" line matches `doc` but
    not `ownership`. Confirmed intentional column-strictness difference,
    not a bug: `ownership`'s docstring targets legacy fixed-form headers,
    which are always unindented at file/routine scope.
    """
    indented = "   ! Author: Jane Doe"
    assert FORTRAN_RULES["doc"].search(indented), "doc should tolerate leading whitespace before '!'"
    assert not FORTRAN_RULES["ownership"].search(indented), (
        "ownership requires column-1 anchoring -- indented form must not match"
    )


def test_fortran_globals_vs_safety_bypasses_common_intentional_double_classification():
    """
    Ambiguity sweep finding: `COMMON` blocks legitimately fire both
    `globals` (persistent shared state across scopes) and
    `safety_bypasses` (legacy unchecked memory sharing) -- both true at
    once, an intentional double-classification, not a false collision.
    """
    common_line = "COMMON /blk/ x, y"
    assert FORTRAN_RULES["globals"].search(common_line)
    assert FORTRAN_RULES["safety_bypasses"].search(common_line)


def test_fortran_concurrency_vs_sync_locks_intentional_double_classification():
    """
    Ambiguity sweep finding: Fortran 2018 coarray synchronization keywords
    (LOCK/UNLOCK/CRITICAL/SYNC ALL/SYNC IMAGES/SYNC MEMORY) legitimately
    fire both `concurrency` (parallel execution primitive) and
    `sync_locks` (explicit race-condition coordination) -- both
    perspectives on the same construct, intentional.
    """
    for line in ["LOCK(lock_var)", "CRITICAL", "SYNC ALL"]:
        assert FORTRAN_RULES["concurrency"].search(line), f"concurrency should match {line!r}"
        assert FORTRAN_RULES["sync_locks"].search(line), f"sync_locks should match {line!r}"


def test_fortran_reflection_vs_serialization_namelist_intentional_double_classification():
    """
    Ambiguity sweep finding: `NAMELIST` legitimately fires both
    `reflection_metaprogramming` (unstructured, name-based dynamic
    loading of variables) and `serialization_parsing` (a structured I/O
    format) -- both true simultaneously, intentional.
    """
    nml_line = "NAMELIST /nml/ x"
    assert FORTRAN_RULES["reflection_metaprogramming"].search(nml_line)
    assert FORTRAN_RULES["serialization_parsing"].search(nml_line)


def test_fortran_io_vs_debug_prints_terminal_write_no_false_collision():
    """
    io's WRITE alternative explicitly excludes terminal output
    (`WRITE(*,...)`/`WRITE(6,...)`), which is debug_prints' territory --
    the two must be mutually exclusive on the write-target axis, unlike
    the other intentional overlaps in this rule set.
    """
    io = FORTRAN_RULES["io"]
    debug_prints = FORTRAN_RULES["debug_prints"]

    terminal = "WRITE(*,*) 'hi'"
    assert debug_prints.search(terminal)
    assert not io.search(terminal)

    file_write = "WRITE(10,*) x"
    assert io.search(file_write)
    assert not debug_prints.search(file_write)


def test_fortran_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). Fortran's
    explicit_casts uses intrinsic conversion function-call syntax
    (`REAL(x)`, `INT(x)`) and pointers uses the `POINTER` keyword or `=>`
    assignment -- structurally distinct, no realistic overlap.
    """
    explicit_casts = FORTRAN_RULES["explicit_casts"]
    pointers = FORTRAN_RULES["pointers"]

    cast_line = "y = REAL(x)"
    assert explicit_casts.search(cast_line)
    assert not pointers.search(cast_line)

    ptr_line = "ptr => target"
    assert pointers.search(ptr_line)
    assert not explicit_casts.search(ptr_line)


def test_fortran_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). Fortran's
    macros are C-preprocessor directives (`#define`, `#ifdef`, ...),
    column-anchored on `#` -- structurally distinct from func_start's
    FUNCTION/SUBROUTINE/PROGRAM/ENTRY keywords, no realistic overlap. Also
    confirms func_start survives a long run of macro-shaped input without
    pathological backtracking.
    """
    func_start = FORTRAN_RULES["func_start"]
    macros = FORTRAN_RULES["macros"]

    macro_line = "#define FOO 1"
    assert macros.search(macro_line)
    assert not func_start.search(macro_line)

    labeled = "SUBROUTINE foo(x)"
    assert func_start.search(labeled)
    assert not macros.search(labeled)

    assert_redos_immune(func_start, "#define " + "a " * 50000, timeout_sec=3.0)


def test_fortran_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` miscounted as a test-framework call). Fortran's
    `test` signature is pFUnit annotations (`@test`) and `call assert_*`
    calls, structurally distinct from `regex_execution`'s intrinsic
    string-processing functions (SCAN/INDEX/VERIFY/ADJUSTL/ADJUSTR) --
    no realistic overlap.
    """
    test = FORTRAN_RULES["test"]
    regex_execution = FORTRAN_RULES["regex_execution"]

    test_line = "call assert_equal(x, y)"
    assert test.search(test_line)
    assert not regex_execution.search(test_line)

    regex_line = "pos = INDEX(str, 'x')"
    assert regex_execution.search(regex_line)
    assert not test.search(regex_line)


def test_fortran_func_start_vs_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C#:
    deeply nested generic return types triggering catastrophic
    backtracking on func_start). Fortran's generics maps to Parameterized
    Derived Types (`TYPE point(k, n)`) and `EXTENDS(...)`/`GENERIC ::`
    interfaces -- func_start requires an explicit FUNCTION/SUBROUTINE/
    PROGRAM/ENTRY keyword, so a bare TYPE declaration never triggers it,
    and func_start survives a long generic-shaped chain without
    pathological backtracking.
    """
    func_start = FORTRAN_RULES["func_start"]
    generics = FORTRAN_RULES["generics"]

    type_decl = "TYPE point(k, n)"
    assert generics.search(type_decl)
    assert not func_start.search(type_decl)

    method_decl = "SUBROUTINE foo(x)"
    assert func_start.search(method_decl)
    assert not generics.search(method_decl)

    assert_redos_immune(func_start, "TYPE point(" + "k, " * 50000, timeout_sec=3.0)


def test_fortran_redos_immunity_sweep():
    """
    ReDoS immunity sweep across fortran's rules with unbounded-looking
    quantifiers (adversarial "never closes" payloads at n=100000 against
    the rules whose quantifiers scale with input length).
    """
    assert_redos_immune(FORTRAN_RULES["func_start"], "PURE RECURSIVE " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["class_start"], "MODULE " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["args"], "SUBROUTINE foo(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["generics"], "TYPE point(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["generics"], "EXTENDS(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["state_mutation"], "a" * 100000 + " =", timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["io"], "WRITE(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["dead_code"], "!" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["macros"], "#define " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["decorators"], "!DIR$" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["scientific"], "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["comprehensions"], "[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["comprehensions"], "(/" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["_dependency_capture"], "USE " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["ownership"], "! Author: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["immutability_locks"], "intent(" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(FORTRAN_RULES["ipc_rpc_bridges"], "OMP_" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert FORTRAN_RULES["func_start"].search("SUBROUTINE foo(x)")
    assert FORTRAN_RULES["class_start"].search("MODULE mymod")
    assert FORTRAN_RULES["io"].search("WRITE(10,*) x")


_FORTRAN_DEEP_CASES = [
    # branch
    ("branch", "SELECT TYPE(a)", "SELECT_TYPE_VAR = 1"),
    ("branch", "SELECT  RANK (b)", "CASE_VAL = 1"),
    ("branch", "GO TO 10", "DO_SOMETHING(x)"),
    ("branch", "DO WHILE (x > 0)", "EXIT_CODE = 0"),
    ("branch", "IF (A .AND. B) THEN", "CYCLE_TIME = 5.0"),
    ("branch", "ELSEWHERE", "WHERE_AM_I = 'HERE'"),
    # args
    ("args", "INTENT( INOUT )", "VALUE_OF_X = 1"),
    ("args", "REAL, VALUE :: x", "OPTIONAL_ARG = .TRUE."),
    ("args", "INTEGER, OPTIONAL :: y", "ENTRY_POINT = 5"),
    ("args", "ENTRY my_entry(a, b)", "MY_SUBROUTINE = 10"),
    ("args", "FUNCTION foo ()", "FUNCTION_PTR = null()"),
    ("args", "SUBROUTINE bar( x, y, * )", "SUBROUTINE_NAME = 'bar'"),
    # func_start
    ("func_start", "PURE RECURSIVE INTEGER FUNCTION my_func()", "END SUBROUTINE foo"),
    ("func_start", "TYPE(MY_TYPE) FUNCTION get_type()", "END FUNCTION foo"),
    ("func_start", "DOUBLE PRECISION FUNCTION foo()", "END PROGRAM main"),
    ("func_start", "MODULE SUBROUTINE my_mod_sub ()", "x = FUNCTION_CALL()"),
    ("func_start", "ELEMENTAL IMPURE SUBROUTINE sub()", "TYPE(MY_TYPE) :: FUNCTION_NAME"),
    ("func_start", "PROGRAM main ! This is a comment", "INTEGER :: PROGRAM_ID"),
    ("func_start", "INTEGER(KIND=4), DIMENSION(:) FUNCTION foo()", "INTEGER :: FUNCTION_X"),
    ("func_start", "CLASS(*), POINTER :: FUNCTION poly_func()", "CLASS_NAME = 'abc'"),
    # class_start
    ("class_start", "SUBMODULE (parent:child) my_sub", "END MODULE my_module"),
    ("class_start", "BLOCK DATA my_data", "END TYPE my_type"),
    ("class_start", "INTERFACE my_intf", "TYPE(my_type) :: x"),
    ("class_start", "TYPE, ABSTRACT, EXTENDS(base) :: my_type", "TYPE(my_type) FUNCTION foo()"),
    ("class_start", "TYPE my_type", "SUBMODULE_NAME = 'abc'"),
    ("class_start", "TYPE :: my_type", "BLOCK_DATA_VAR = 1"),
    # structural_boundaries
    ("structural_boundaries", "END SUBROUTINE", "END IF"),
    ("structural_boundaries", "END TYPE", "END DO"),
    ("structural_boundaries", "DOUBLE PRECISION", "CLASS_NAME = 1"),
    ("structural_boundaries", "BLOCK DATA", "RETURN_CODE = 0"),
    ("structural_boundaries", "CONTAINS", "BLOCK_SIZE = 512"),
    ("structural_boundaries", "CLASS", "MODULE_VAR = 1"),
]


@pytest.mark.parametrize("signature,positive,negative", _FORTRAN_DEEP_CASES)
def test_fortran_signature_deep_cases(signature, positive, negative):
    pattern = FORTRAN_RULES[signature]
    assert pattern is not None, f"fortran's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"fortran {signature!r} failed to match deep positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), (
            f"fortran {signature!r} incorrectly matched deep excluded case: {negative!r}"
        )
