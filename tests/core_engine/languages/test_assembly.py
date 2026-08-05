"""assembly strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py as part of
splitting that file into tests/core_engine/languages/, one file per language,
mirroring tests/extraction/languages/. See that file's git history for the
original single-file layout and section banners (Issue references, etc).
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


# ==============================================================================
# ASSEMBLY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #574, part of epic #518)
# ==============================================================================
ASM_RULES = LANGUAGE_DEFINITIONS["assembly"]["rules"]

_ASM_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "\tjmp foo", "\tmov eax, ebx"),
    ("args", "\tmov edi, 5", "\tmov eax, ebx"),
    ("structural_boundaries", "\tmov rax, rbx", "\tjmp foo"),
    ("func_start", "myFunc:\n\tret", "\tret"),
    ("class_start", "\tstruc Point", "\tmov eax, ebx"),
    ("safety", "\tendbr64", "\tmov eax, ebx"),
    ("safety_bypasses", "\tjmp rax", "\tjmp foo"),
    ("high_risk_execution", "\thlt", "\tmov eax, ebx"),
    ("io", "\tsyscall", "\tmov eax, ebx"),
    ("api", "\tglobal main", "\tmov eax, ebx"),
    ("state_mutation", "\txchg eax, ebx", "\tmov eax, ebx"),
    ("dead_code", "; mov eax, 5", "; just a note"),
    ("doc", "; @param x", "; just a note"),
    ("test", "\tassert eax", "\tmov eax, ebx"),
    ("concurrency", "\tlock xadd eax, ebx", "\tmov eax, ebx"),
    ("globals", "\t.data", "\tmov eax, ebx"),
    ("comprehensions", "\trep movsb", "\tmov eax, ebx"),
    ("scientific", "\tfadd st0, st1", "\tmov eax, ebx"),
    ("reflection_metaprogramming", "[eax + ebx * 4]", "mov eax, ebx"),
    ("import", '%include "foo.inc"', "\tmov eax, ebx"),
    ("ownership", "; Author: Jane Doe", "; just a note"),
    ("planned_debt", "; TODO: fix", "; done"),
    ("fragile_debt", "; HACK: workaround", "; clean"),
    ("spec_exposure", "[SPEC-123]", "; just a note"),
    ("events", "\tint 0x21", "\tmov eax, ebx"),
    ("macros", "%macro foo 2", "\tmov eax, ebx"),
    ("pointers", "\tmov eax, [ebx]", "\tmov eax, ebx"),
    ("memory_alloc", "\tcall malloc", "\tcall free"),
    ("telemetry", "\tcall log_info", "\tcall malloc"),
    ("debug_prints", "\tcall printf", "\tcall malloc"),
    ("explicit_casts", "\tmovzx eax, byte ptr [ebx]", "\tmov eax, ebx"),
    ("panics_and_aborts", "\thlt", "\tmov eax, ebx"),
    ("thread_sleeps", "\tpause", "\tmov eax, ebx"),
    ("bitwise_ops", "\txor eax, eax", "\tmov eax, ebx"),
    ("sync_locks", "\tlock cmpxchg", "\tmov eax, ebx"),
    ("immutability_locks", "FOO equ 5", "\tmov eax, ebx"),
    ("cleanup", "\tcall free", "\tcall malloc"),
    ("encapsulation", "\t.local myVar", "\t.global myVar"),
    ("regex_execution", "\tcall regexec", "\tcall malloc"),
    ("time_date_logic", "\trdtsc", "\tmov eax, ebx"),
    ("ipc_rpc_bridges", "\tcall execve", "\tcall malloc"),
]


@pytest.mark.parametrize("signature,positive,negative", _ASM_SIMPLE_CASES)
def test_assembly_signature_positive_and_negative(signature, positive, negative):
    pattern = ASM_RULES[signature]
    assert pattern is not None, f"assembly's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"assembly {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"assembly {signature!r} incorrectly matched an excluded case: {negative!r}"
        )


def test_assembly_serialization_parsing_is_none_by_strict_feature_parity():
    """
    Regression test for a real bug: `serialization_parsing`,
    `regex_execution`, `time_date_logic`, and `ipc_rpc_bridges` were all
    leftover Lua signatures (`string.match`, `os.execute`, `cjson.decode`,
    etc. -- the section was even labeled "(Lua Specifics)" in a comment),
    copy-pasted from Lua's dict and never adapted. None of them can ever
    fire against real assembly source. `serialization_parsing` has no
    native or universal-libc equivalent (unlike malloc/free/printf) so it
    is now explicitly `None` per Strict Feature Parity (Rule 4).
    """
    assert ASM_RULES["serialization_parsing"] is None


def test_assembly_regex_execution_time_date_ipc_use_real_constructs_not_lua():
    """
    The other three hybrid sensors do have realistic native/libc
    equivalents in assembly and were rewired to them (see previous test
    for the bug this fixes).
    """
    old_regex_execution = re.compile(r"\b(string\.match|string\.gmatch|string\.find|string\.gsub)\b")
    old_time_date_logic = re.compile(r"\b(os\.time|os\.clock|os\.date|os\.difftime)\b")
    old_ipc_rpc_bridges = re.compile(
        r"\b(os\.execute|io\.popen|coroutine\.create|coroutine\.resume|coroutine\.yield)\b"
    )

    real_regex_call = "\tcall regexec"
    real_time_call = "\trdtsc"
    real_ipc_call = "\tcall execve"

    # sanity: the old Lua-shaped patterns never matched real assembly
    assert not old_regex_execution.search(real_regex_call)
    assert not old_time_date_logic.search(real_time_call)
    assert not old_ipc_rpc_bridges.search(real_ipc_call)

    # the fixed patterns do
    assert ASM_RULES["regex_execution"].search(real_regex_call)
    assert ASM_RULES["time_date_logic"].search(real_time_call)
    assert ASM_RULES["ipc_rpc_bridges"].search(real_ipc_call)

    # and stay disjoint from `io`'s generic syscall tokens
    assert not ASM_RULES["ipc_rpc_bridges"].search("\tsyscall")


def test_assembly_dependency_capture_extracts_include_path():
    pattern = ASM_RULES["_dependency_capture"]
    m = pattern.search('%include "foo.inc"')
    assert m and m.group(1) == "foo.inc"
    m2 = pattern.search("\t.incbin bar.bin")
    assert m2 and m2.group(2) == "bar.bin"


def test_assembly_func_start_cross_line_false_match_regression():
    """
    Regression test for a real bug: the lookahead used `(?=\\s*:)`, and in
    `re.M` mode `\\s` matches newlines (Rule 5). A bare label with nothing
    else on its own line, followed by blank lines and then a stray colon
    far away, got falsely bound to that distant colon. Real assembly
    label+colon pairs are always on the same physical line. Bounded to
    `[ \\t]*`.
    """
    old_pattern = re.compile(
        r"^[ \t]*(?!\.L|\.LC|\d|\.text|\.data|\.bss)([a-zA-Z_][a-zA-Z0-9_.$]*)(?=\s*:)",
        re.M,
    )
    cross_line = "FOO\n\n\n:"
    old_m = old_pattern.search(cross_line)
    assert old_m and old_m.group(1) == "FOO", "sanity check: bug must reproduce against the old pattern"

    func_start = ASM_RULES["func_start"]
    assert not func_start.search(cross_line), "cross-line false attribution still occurs"

    m = func_start.search("myFunc:\n\tret")
    assert m and m.group(1) == "myFunc", "real same-line label form regressed"

    m2 = func_start.search("myFunc :\n\tret")
    assert m2 and m2.group(1) == "myFunc", "same-line label with space before colon should still match"


def test_assembly_func_start_excludes_local_labels_and_sections():
    func_start = ASM_RULES["func_start"]
    assert not func_start.search(".L1:\n\tret"), "GCC-style local label should be excluded"
    assert not func_start.search(".text\n"), "section directive should not be treated as a func_start label"


def test_assembly_encapsulation_symbolic_boundary_regression():
    """
    Regression test for a real bug (Rule 9): the old pattern was
    `\\b(?:\\.local|\\.private)\\b`. A leading `\\b` placed directly before a
    literal `.` can never fire when the directive is preceded by
    whitespace or line-start (both non-word), which is how `.local`/
    `.private` are always written in real assembly -- confirmed the
    realistic form `"\\t.local myVar"` never matched under the old pattern.
    Fixed by anchoring to line-start instead (`.` is already
    self-delimiting, per the doc's Rule 9 guidance), matching the same
    convention already used by `class_start`/`globals`/`api`/`macros`.
    """
    old_pattern = re.compile(r"\b(?:\.local|\.private)\b", re.I)
    realistic = "\t.local myVar"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    encapsulation = ASM_RULES["encapsulation"]
    assert encapsulation.search(realistic), "realistic whitespace-preceded .local directive still didn't match"
    assert encapsulation.search("\t.private myVar")
    assert not encapsulation.search("\t.global myVar")


def test_assembly_explicit_casts_vs_pointers_intentional_double_classification():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). Here the two
    signatures DO genuinely overlap on the same substring -- an x86 size
    specifier like `byte ptr [ebx]` is simultaneously an explicit type-size
    cast (explicit_casts) AND a memory pointer dereference (pointers).
    This is an intentional, correct double-classification (Rule 1:
    semantic intent over keyword matching) since the token really does
    carry both meanings at once, not a false collision to fix.
    """
    explicit_casts = ASM_RULES["explicit_casts"]
    pointers = ASM_RULES["pointers"]

    combined = "\tmovzx eax, byte ptr [ebx]"
    assert explicit_casts.search(combined)
    assert pointers.search(combined)

    # a plain bracketed dereference with no size specifier is pointers-only
    plain_deref = "\tmov eax, [ebx]"
    assert pointers.search(plain_deref)
    assert not explicit_casts.search(plain_deref)


def test_assembly_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). assembly's
    macros keywords all start with `%`, `.`, or `#`, none of which satisfy
    func_start's `[a-zA-Z_]` leading-character requirement -- structurally
    disjoint by construction, verified against every macros alternative.
    """
    func_start = ASM_RULES["func_start"]
    macros = ASM_RULES["macros"]

    for macro_line in ("%macro foo 2", ".macro foo", "%define FOO 5", ".equ FOO, 5", "#define FOO 5"):
        assert macros.search(macro_line), f"macros should match {macro_line!r}"
        assert not func_start.search(macro_line), f"func_start should not match macro directive {macro_line!r}"

    labeled_opcode = "myFunc:\n\tret"
    assert func_start.search(labeled_opcode)
    assert not macros.search(labeled_opcode)


def test_assembly_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with `test`). assembly's `test` maps to
    describe/expect/assert/TestCase/`it(`; `regex_execution` maps to
    `call`/`bl` into POSIX regex functions -- disjoint token vocabularies,
    no realistic overlap.
    """
    test_rule = ASM_RULES["test"]
    regex_execution = ASM_RULES["regex_execution"]

    assertion = "\tassert eax"
    assert test_rule.search(assertion)
    assert not regex_execution.search(assertion)

    regex_call = "\tcall regexec"
    assert regex_execution.search(regex_call)
    assert not test_rule.search(regex_call)


def test_assembly_hlt_triple_classification_is_intentional():
    """
    Ambiguity sweep finding: `hlt` appears in three separate Phase 2/5
    sensors -- high_risk_execution, panics_and_aborts, and thread_sleeps.
    Confirmed intentional, not a bug: the HLT instruction genuinely halts
    the CPU (a process-killing/high-risk act), forcefully destroys the
    current execution context (a panic/abort), and is also the idiomatic
    idle-wait instruction in interrupt-driven code (a thread sleep) --
    a static regex can't disambiguate which real-world intent applies, so
    all three sensors firing together is the documented, deliberate
    tradeoff (Rule 1: semantic intent over keyword matching), not
    duplicate counting to collapse.
    """
    halt = "\thlt"
    assert ASM_RULES["high_risk_execution"].search(halt)
    assert ASM_RULES["panics_and_aborts"].search(halt)
    assert ASM_RULES["thread_sleeps"].search(halt)


def test_assembly_inc_dec_structural_boundaries_vs_state_mutation_is_intentional():
    """
    Ambiguity sweep finding: `inc`/`dec` appear in both
    structural_boundaries and state_mutation. Confirmed intentional: an
    increment instruction is simultaneously a straight-line sequential
    operation and a mutation of register/memory state -- both true at
    once, not a false collision.
    """
    incr = "\tinc eax"
    assert ASM_RULES["structural_boundaries"].search(incr)
    assert ASM_RULES["state_mutation"].search(incr)


def test_assembly_concurrency_vs_sync_locks_overlap_is_intentional():
    """
    Ambiguity sweep finding: concurrency and sync_locks share several
    literal tokens (lock, dmb, dsb, isb, stxr, ldxr). Confirmed
    intentional: hardware memory-barrier/atomic instructions are
    simultaneously concurrency-domain (Phase 3) and synchronization-domain
    (Phase 5) by definition -- there is no real assembly instruction that
    is "concurrency" without also being "synchronization" at the hardware
    level, so co-firing is correct, not duplicate counting.
    """
    barrier = "\tdmb sy"
    assert ASM_RULES["concurrency"].search(barrier)
    assert ASM_RULES["sync_locks"].search(barrier)


def test_assembly_pointers_no_realistic_nested_bracket_construct():
    """
    Nested-delimiter audit (Rule 11): `pointers` uses the flat negated
    class `\\[[^\\]]+\\]`, which cannot represent one level of bracket
    nesting. Confirmed this is not applicable here -- neither x86 SIB
    addressing (`[rax+rbx*4]`) nor ARM addressing (`[x0, x1, lsl #2]`) has
    any legitimate construct where `[` nests inside another `[...]`
    operand (unlike a generic return type or indexer in a higher-level
    language) -- so the flat class is correct as written, not a gap.
    """
    pointers = ASM_RULES["pointers"]
    assert pointers.search("\tmov eax, [rax+rbx*4]")
    assert pointers.search("\tldr x0, [x1, x2, lsl #2]")


def test_assembly_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: assembly is `line_exclusive` (NASM/MASM use `;`,
    GAS/ARM use `#`; there is no native multi-line block-comment syntax)
    -- no rule tracks open/close block-comment state. Confirms a stray
    comment-like line doesn't fool a structural rule into a false match.
    """
    branch = ASM_RULES["branch"]
    stray = "; not real code, just a note\n\tjmp foo"
    assert branch.search(stray), "branch should still see jmp regardless of the preceding comment line"


def test_assembly_dead_code_fires_under_both_native_comment_styles():
    """
    Comment-style audit (Rule 12): assembly's dead_code is wired to both
    real native comment markers for this lexical family -- `;`
    (NASM/Intel/MASM) and `#` (GAS/ARM) -- confirmed both independently
    fire on commented-out structural code.
    """
    dead_code = ASM_RULES["dead_code"]
    assert dead_code.search("; mov eax, 5"), "';' comment style should be recognized"
    assert dead_code.search("# mov eax, 5"), "'#' comment style should be recognized"


def test_assembly_redos_immunity_sweep():
    """
    ReDoS immunity sweep across assembly's rules with unbounded-looking
    quantifiers. Verified via a systematic scaling sweep before writing
    this test (adversarial "never closes" payloads at n=2000/8000/32000
    against every non-None rule): nothing exceeded 0.3s at n=32000.
    """
    assert_redos_immune(ASM_RULES["func_start"], "LABEL" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["api"], "global" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["pointers"], "[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["reflection_metaprogramming"], "[" + "a " * 50000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["doc"], ";" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["ownership"], "; Author: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["_dependency_capture"], "%include " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["spec_exposure"], "[SPEC-1" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["class_start"], "struc " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["encapsulation"], "." + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert ASM_RULES["func_start"].search("myFunc:\n\tret")
    assert ASM_RULES["api"].search("\tglobal main")
    assert ASM_RULES["encapsulation"].search("\t.local myVar")
