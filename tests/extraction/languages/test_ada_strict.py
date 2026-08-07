"""
Ada/SPARK strict structural-signature coverage (issue #76, epic #75). See
gitgalaxy/standards/how_to_add_a_language.md's Strict Testing & Crucible
Verification Framework for the methodology -- this is a separate adversarial
pass against the signatures registered in language_standards.py, not a
continuation of the generation work itself.
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

ADA = LANGUAGE_DEFINITIONS["ada"]
ADA_RULES = ADA["rules"]

# ==============================================================================
# TEST 1: PER-SIGNATURE POSITIVE/NEGATIVE COVERAGE
# One entry per non-None rule key, using realistic Ada/SPARK snippets.
# ==============================================================================
_ADA_SIMPLE_CASES = [
    ("branch", "if X > 0 then", "X := 5;"),
    ("branch", "X := A and then B;", "X := 5;"),  # two-word short-circuit form
    ("args", "procedure Foo (X : Integer) is", "X := 5;"),
    ("structural_boundaries", "begin", "X := 5;"),
    ("structural_boundaries", "package Foo is", "X := 5;"),
    ("func_start", "procedure Foo is", "procedure Foo is abstract;"),
    ("class_start", "type Foo is tagged record", "type Foo is range 1 .. 10;"),
    ("safety", "exception", "X := 5;"),
    ("safety", "type Celsius is range -273 .. 1000;", "X := 5;"),  # #76's own "type ... is range" ask
    ("safety", "pragma Assert (X > 0);", "pragma Pack;"),  # scoped safety-pragma vocabulary, not bare "pragma"
    ("safety_bypasses", "Unchecked_Conversion", "X := 5;"),
    ("high_risk_execution", "OS_Exit (1);", "X := 5;"),
    ("io", 'Ada.Text_IO.Open (F, In_File, "data.txt");', "X := 5;"),
    ("api", "package Foo is", "package body Foo is"),
    ("state_mutation", "X := 5;", "X = 5"),
    ("dead_code", "-- if X > 0 then", "-- just a note"),
    ("doc", "-- @param X the input value", "-- just a note"),
    ("test", 'AUnit.Assertions.Assert (X = 5, "msg");', "X := 5;"),
    ("concurrency", "task Foo is", "X := 5;"),
    ("globals", "with Global => (Input => X);", "X := 5;"),
    ("decorators", "with Pre => X > 0", "with Ada.Text_IO;"),
    ("decorators", "with Refined_Global => null", "with Ada.Text_IO;"),  # SPARK refinement aspect
    ("decorators", "pragma SPARK_Mode (On);", "X := 5;"),  # pragma form, distinct from `with SPARK_Mode`
    ("generics", "generic", "X := 5;"),
    ("generics", "package Stacks is new Generic_Stack (Integer);", "type Dog is new Animal with record"),
    ("comprehensions", "for all X in 1 .. 10 => X > 0", "X := 5;"),
    ("scientific", "Ada.Numerics.Elementary_Functions", "X := 5;"),
    ("reflection_metaprogramming", "Obj'Class", "X := 5;"),
    ("import", "with Ada.Text_IO;", "with Pre => X > 0;"),
    ("ownership", "-- Author: Jane Doe", "-- just a note"),
    ("planned_debt", "-- TODO: fix this", "-- done"),
    ("fragile_debt", "-- HACK: workaround", "-- clean"),
    ("hardcoded_secrets", 'Password : constant String := "hunter2xyz123";', "X := 5;"),
    ("spec_exposure", "[SPEC-123]", "-- just a note"),
    ("events", "accept Foo do", "X := 5;"),
    ("macros", "#if DEBUG", "X := 5;"),
    ("pointers", "Foo'Access", "X := 5;"),
    ("pointers", "type Ptr is access Integer;", "X := 5;"),
    ("memory_alloc", "X := new Integer;", "X := 5;"),
    ("inline_asm", 'System.Machine_Code.Asm ("nop");', "X := 5;"),
    ("telemetry", 'GNATCOLL.Traces.Trace (Handle, "msg");', "X := 5;"),
    ("debug_prints", 'Put_Line ("hello");', "X := 5;"),
    ("explicit_casts", "Integer'(X)", "X := 5;"),
    ("panics_and_aborts", "raise Constraint_Error;", "X := 5;"),
    ("panics_and_aborts", "abort Worker_Task;", "X := 5;"),
    ("thread_sleeps", "delay 1.0;", "X := 5;"),
    ("bitwise_ops", "Shift_Left (X, 2)", "X := 5;"),
    ("bitwise_ops", "X := A xor B;", "X := 5;"),
    ("sync_locks", "protected Foo is", "X := 5;"),
    ("immutability_locks", "X : constant Integer := 5;", "X : Integer := 5;"),
    ("cleanup", "Ada.Unchecked_Deallocation", "X := 5;"),
    ("cleanup", "Finalize (Obj);", "X := 5;"),
    ("encapsulation", "private", "X := 5;"),
    ("listeners", "entry Foo;", "X := 5;"),
    ("test_skip", "-- SKIP: flaky on hardware-in-the-loop rig", "-- just a note"),
    ("serialization_parsing", "GNATCOLL.JSON.Create", "X := 5;"),
    ("regex_execution", "GNAT.Regpat.Match (Pattern, Data)", "X := 5;"),
    ("time_date_logic", "Ada.Calendar.Clock", "X := 5;"),
    ("ipc_rpc_bridges", "pragma Remote_Call_Interface;", "X := 5;"),
]


@pytest.mark.parametrize("signature,positive,negative", _ADA_SIMPLE_CASES)
def test_ada_signature_positive_and_negative(signature, positive, negative):
    pattern = ADA_RULES[signature]
    assert pattern is not None, f"ada's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"ada {signature!r} failed to match its own documented positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), f"ada {signature!r} incorrectly matched an excluded case: {negative!r}"


# ==============================================================================
# TEST 2: SCHEMA COMPLETENESS (Rule 4 / how_to_add_a_language.md Step 4 item 9)
# Every baseline key from the OUTPUT SCHEMA must be present -- either a real
# pattern or an explicit None -- never silently absent.
# ==============================================================================
_BASELINE_KEYS = [
    "branch", "args", "structural_boundaries", "func_start", "class_start",
    "safety", "safety_bypasses", "high_risk_execution", "io", "api",
    "state_mutation", "dead_code", "doc", "test",
    "concurrency", "ui_framework", "closures", "globals", "decorators",
    "generics", "comprehensions", "scientific", "reflection_metaprogramming",
    "import", "_dependency_capture", "ownership",
    "planned_debt", "fragile_debt", "hardcoded_secrets", "spec_exposure",
    "tabs_vs_spaces", "ssr_boundaries", "events", "dependency_injection",
    "macros", "pointers", "memory_alloc", "inline_asm",
    "telemetry", "debug_prints", "explicit_casts", "panics_and_aborts",
    "thread_sleeps", "bitwise_ops", "sync_locks", "immutability_locks",
    "cleanup", "encapsulation", "listeners", "test_skip",
    "serialization_parsing", "regex_execution", "time_date_logic", "ipc_rpc_bridges",
]  # fmt: skip

_EXPECTED_NONE_KEYS = {"ui_framework", "closures", "tabs_vs_spaces", "ssr_boundaries", "dependency_injection"}


def test_ada_schema_completeness():
    missing = set(_BASELINE_KEYS) - set(ADA_RULES.keys())
    assert not missing, f"ada rules dict is missing baseline keys entirely (not even None): {missing}"
    extra = set(ADA_RULES.keys()) - set(_BASELINE_KEYS)
    assert not extra, f"ada rules dict has unexpected keys not in the baseline schema: {extra}"


def test_ada_none_keys_are_genuinely_inapplicable_not_accidental():
    """
    Strict Feature Parity (Rule 4): every None key should be an intentional
    "this doesn't exist in Ada" call, not an accidental gap. Cross-checked
    against the rationale comments left in the dict itself.
    """
    actual_none = {k for k, v in ADA_RULES.items() if v is None}
    assert actual_none == _EXPECTED_NONE_KEYS, f"unexpected set of None keys: {actual_none ^ _EXPECTED_NONE_KEYS}"


def test_ada_spark_refinement_aspects_register_as_decorators_not_silently_invisible():
    """
    Coverage gap found and fixed before merging #1140: the "& SPARK" half of
    #76's title wasn't fully honored -- the aspect-mark vocabulary shared by
    decorators/import/_dependency_capture only covered the foundational
    SPARK contract aspects (Pre/Post/Global/Depends/SPARK_Mode), not the
    data-flow *refinement* aspects (Abstract_State/Initializes/
    Refined_Global/Refined_Post/Refined_State/Refined_Depends) used to
    formally model a package's private state for the prover -- common in
    real SPARK code. These didn't misfire as false imports (the `=>` breaks
    import's required trailing-`;` grammar shape either way), they were
    just invisible to every signature. Also covers the `pragma SPARK_Mode
    (On);` form, structurally distinct from the `with SPARK_Mode => On`
    aspect form -- both are real and common.
    """
    decorators = ADA_RULES["decorators"]
    import_rule = ADA_RULES["import"]

    for aspect in (
        "Abstract_State",
        "Initializes",
        "Refined_Global",
        "Refined_Post",
        "Refined_State",
        "Refined_Depends",
    ):
        payload = f"with {aspect} => null"
        assert decorators.search(payload), f"decorators failed to recognize SPARK refinement aspect: {aspect!r}"
        assert not import_rule.search(payload + ";"), f"import incorrectly matched refinement aspect: {aspect!r}"

    assert decorators.search("pragma SPARK_Mode (On);"), "decorators must recognize the pragma form of SPARK_Mode"
    assert decorators.search("pragma SPARK_Mode (Off);")


# ==============================================================================
# TEST 3: LEXICAL-FAMILY SANITY CHECK (Step 4 item 8)
# Ada has no block-comment form; confirm Prism.split_streams() actually
# strips `--` comments and leaves real code (including string literals that
# themselves contain `--`) intact, using the real engine end-to-end rather
# than trusting the family label alone.
# ==============================================================================
def test_ada_lexical_family_is_correctly_wired_not_just_labeled():
    """
    Regression guard for a real pipeline-level bug this addition avoided:
    epic #75/#76 both label Ada's family "hybrid_dash", but that name was
    never registered anywhere in gitgalaxy_config.py's
    LEXICAL_FAMILY_HEURISTICS or prism.py's family-dispatch logic. Using it
    verbatim would have silently produced a family with NO delimiters wired
    up at all -- Prism's generic stripper falls through with an empty
    pattern and returns the text completely unstripped, corrupting every
    downstream signature count with comment noise. Registered
    "line_exclusive_dash" instead (single `--` delimiter, no block form)
    and wired it into prism.py's _compile_regex_matrix -- this test proves
    the wiring actually works end-to-end, not just that the config key
    exists.
    """
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as LANG_DEFS

    assert ADA["lexical_family"] == "line_exclusive_dash"
    assert "line_exclusive_dash" in LEXICAL_FAMILY_HEURISTICS["lexical_families"]
    assert LEXICAL_FAMILY_HEURISTICS["lexical_families"]["line_exclusive_dash"]["delimiters"] == ["--"]

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANG_DEFS)
    sample = (
        "with Ada.Text_IO; use Ada.Text_IO;\n\n"
        "procedure Demo is\n"
        "begin\n"
        "   --  A header comment describing the call below\n"
        '   Put_Line ("Use -- for comments in Ada");  -- trailing comment\n'
        "end Demo;\n"
    )
    result = prism.split_streams(sample, "ada")

    assert "A header comment describing the call below" in result["comment_stream"]
    assert "trailing comment" in result["comment_stream"]
    # the real comment lines must be gone from the code stream...
    assert "A header comment describing the call below" not in result["code_stream"]
    # ...but a string literal that merely *contains* "--" must survive intact.
    assert 'Put_Line ("Use -- for comments in Ada");' in result["code_stream"]
    assert "with Ada.Text_IO; use Ada.Text_IO;" in result["code_stream"]


def test_ada_line_exclusive_dash_does_not_leak_into_shared_line_exclusive_family():
    """
    The new family must be additive, not a mutation of the pre-existing
    shared "line_exclusive" family several other languages (Perl, Assembly,
    ...) already depend on -- confirms `--` was never added to that shared
    delimiter list (which would silently truncate any of those languages'
    real code containing a literal `--`, e.g. Perl's `$x--;`).
    """
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    shared = LEXICAL_FAMILY_HEURISTICS["lexical_families"]["line_exclusive"]["delimiters"]
    assert "--" not in shared, "`--` leaked into the shared line_exclusive delimiter list"


# ==============================================================================
# TEST 4: SYMBOLIC-BOUNDARY AUDIT (Rule 9/10)
# Ada attributes are written as IDENTIFIER'ATTRIBUTE (a leading apostrophe,
# a non-word character) -- confirm the realistic attached form matches, not
# just an artificially spaced-out synthetic string.
# ==============================================================================
def test_ada_attribute_forms_match_realistic_attached_syntax():
    reflection = ADA_RULES["reflection_metaprogramming"]
    pointers = ADA_RULES["pointers"]
    explicit_casts = ADA_RULES["explicit_casts"]

    assert reflection.search("Some_Object'Class"), "'Class attribute must match directly attached to its prefix"
    assert reflection.search("Some_Type'Tag"), "'Tag attribute must match directly attached to its prefix"
    assert pointers.search("Handler'Access"), "'Access attribute must match directly attached to its prefix"
    assert pointers.search("Handler'Unchecked_Access")
    assert explicit_casts.search("Integer'(Compute (X))"), "qualified expression must match attached, no space"


# ==============================================================================
# TEST 5: NESTED-DELIMITER AUDIT (Rule 11)
# func_start/args allow one level of nested parens in default expressions.
# ==============================================================================
def test_ada_func_start_and_args_handle_one_level_of_nested_parens():
    func_start = ADA_RULES["func_start"]
    args = ADA_RULES["args"]

    nested = "procedure Foo (X : Integer := Compute (A, (B + C))) is"
    m = func_start.search(nested)
    assert m and m.group(1) == "Foo", "func_start choked on a one-level-nested default expression"

    m2 = args.search(nested)
    assert m2 and "X" in m2.group(1), "args choked on a one-level-nested default expression"


# ==============================================================================
# TEST 6: RE.M COMPLETENESS AUDIT (Rule 13)
# Every rule using a literal `^` outside a character class must set re.M.
# ==============================================================================
def test_ada_caret_anchored_rules_all_set_multiline_flag():
    caret_using_keys = []
    for key, pattern in ADA_RULES.items():
        if pattern is None or key.startswith("_"):
            continue
        # Excludes `^` immediately after `[` (negated-class opener, e.g.
        # `[^()]` in args/func_start's nested-paren capture) -- that's not a
        # line-start anchor, it's the negation operator inside a bracket
        # expression, and Rule 13 only concerns the former.
        if isinstance(pattern, re.Pattern) and re.search(r"(?<!\\)(?<!\[)\^", pattern.pattern):
            caret_using_keys.append(key)

    assert caret_using_keys, (
        "expected at least one ^-anchored rule (import/ownership/macros) -- audit is a no-op otherwise"
    )
    for key in caret_using_keys:
        assert ADA_RULES[key].flags & re.M, f"ada {key!r} uses ^ but doesn't set re.M -- can only match the first line"


# ==============================================================================
# TEST 7: AMBIGUITY SWEEP (Rule 6 category)
# Documents genuine, intentional double-classifications (same design already
# established for COBOL's EXEC CICS ENQ/DELAY dual-mapping) and confirms the
# deliberately-avoided false collisions actually stay separated.
# ==============================================================================
def test_ada_intentional_double_classification_sweep():
    task_decl = "task Worker is"
    assert ADA_RULES["concurrency"].search(task_decl)

    protected_decl = "protected Guard is"
    assert ADA_RULES["concurrency"].search(protected_decl)
    assert ADA_RULES["sync_locks"].search(protected_decl)

    delay_stmt = "delay 1.0;"
    assert ADA_RULES["concurrency"].search(delay_stmt)
    assert ADA_RULES["thread_sleeps"].search(delay_stmt)

    accept_stmt = "accept Foo do"
    assert ADA_RULES["concurrency"].search(accept_stmt)
    assert ADA_RULES["events"].search(accept_stmt)

    entry_decl = "entry Foo;"
    assert ADA_RULES["concurrency"].search(entry_decl)
    assert ADA_RULES["listeners"].search(entry_decl)

    unchecked_dealloc = "procedure Free is new Ada.Unchecked_Deallocation (Object => T, Name => T_Ptr);"
    assert ADA_RULES["cleanup"].search(unchecked_dealloc)
    assert ADA_RULES["generics"].search(unchecked_dealloc), (
        "generic instantiation form should also register as generics"
    )

    range_type = "type Celsius is range -273 .. 1000;"
    assert ADA_RULES["safety"].search(range_type)
    assert ADA_RULES["class_start"] and not ADA_RULES["class_start"].search(range_type), (
        "a plain range type is not a tagged type -- must not double up on class_start"
    )


def test_ada_generics_instantiation_does_not_collide_with_tagged_type_derivation():
    """
    Both generic instantiation (`package X is new Y (...)`) and tagged-type
    derivation (`type Dog is new Animal with ...`) share the two words
    "is new", but are structurally different constructs. generics is scoped
    to `package|procedure|function NAME is new` specifically so it does NOT
    fire on a tagged-type derivation, and class_start's tagged-type pattern
    does NOT fire on a generic instantiation.
    """
    instantiation = "package Integer_Stack is new Stacks (Integer);"
    derivation = "type Dog is new Animal with record"

    assert ADA_RULES["generics"].search(instantiation)
    assert not ADA_RULES["generics"].search(derivation), "generics incorrectly fired on tagged-type derivation"

    assert ADA_RULES["class_start"].search(derivation)
    assert not ADA_RULES["class_start"].search(instantiation), "class_start incorrectly fired on generic instantiation"


def test_ada_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). Ada's
    explicit_casts uses the qualified-expression `Type'(Expr)` form and
    pointers uses access-type/`'Access` syntax -- structurally distinct.
    """
    explicit_casts = ADA_RULES["explicit_casts"]
    pointers = ADA_RULES["pointers"]

    qualified = "Integer'(X)"
    assert explicit_casts.search(qualified)
    assert not pointers.search(qualified)

    access_attr = "Handler'Access"
    assert pointers.search(access_attr)
    assert not explicit_casts.search(access_attr)


def test_ada_import_and_decorators_share_exclusion_vocabulary_without_collision():
    """
    import/_dependency_capture and decorators are two sides of the same
    lexical fork (both start with the `with` keyword) -- confirm they
    partition realistically, not just that each individually passes its own
    simple case.
    """
    plain_import = "with Ada.Text_IO;"
    aspect_clause = "with Pre => X > 0"

    assert ADA_RULES["import"].search(plain_import)
    assert not ADA_RULES["decorators"].search(plain_import)

    assert ADA_RULES["decorators"].search(aspect_clause)
    assert not ADA_RULES["import"].search(aspect_clause)


# ==============================================================================
# TEST 8: REDOS ADVERSARIAL SWEEP (Rule 5/14), scaling-verified
# ==============================================================================
def test_ada_redos_immunity_sweep():
    assert_redos_immune(ADA_RULES["func_start"], "procedure Foo (" + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["func_start"], "procedure Foo with " + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["class_start"], "type Foo is new " + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["args"], "procedure Foo (" + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["import"], "with " + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["_dependency_capture"], "with " + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["decorators"], "with " + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(
        ADA_RULES["hardcoded_secrets"], "password : constant String := " + "A" * 200000, timeout_sec=3.0
    )
    assert_redos_immune(ADA_RULES["macros"], "#if " + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["ownership"], "-- Author:" + " " * 200000, timeout_sec=3.0)
    assert_redos_immune(ADA_RULES["dead_code"], "--" + " " * 200000, timeout_sec=3.0)

    # sanity: everything still matches its real positive case after the sweep
    assert ADA_RULES["func_start"].search("procedure Foo is")
    assert ADA_RULES["class_start"].search("type Foo is tagged record")
    assert ADA_RULES["import"].search("with Ada.Text_IO;")


def test_ada_func_start_scaling_is_linear_not_quadratic():
    """
    Explicit geometric-scaling proof (Rule 5, not a single timing) for the
    bounded `with`-aspect segment between the profile and "is" -- the one
    genuinely payload-shaped quantifier in func_start.
    """
    import time

    func_start = ADA_RULES["func_start"]
    timings = []
    for n in (2000, 4000, 8000):
        payload = "procedure Foo with " + "A" * n
        start = time.perf_counter()
        func_start.search(payload)
        timings.append(time.perf_counter() - start)

    # A roughly-2x-per-doubling ratio is linear; anything approaching 4x
    # would indicate real quadratic backtracking. Generous margin for CI
    # scheduling noise.
    assert timings[-1] < timings[0] * 8 + 0.05, f"suspicious scaling: {timings}"
