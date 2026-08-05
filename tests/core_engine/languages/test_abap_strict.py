"""abap strict structural-signature coverage.

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


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
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


def test_abap_odata_publish_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["abap"]["rules"]
    assert r["api"].search("@OData.publish: true")


# ==============================================================================
# ABAP: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #571, part of epic #518)
# ==============================================================================
ABAP_RULES = LANGUAGE_DEFINITIONS["abap"]["rules"]

_ABAP_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "IF lv_x = 1.", "DATA lv_x TYPE i."),
    ("args", "IMPORTING iv_x TYPE i", "DATA lv_x TYPE i."),
    ("structural_boundaries", "DATA lv_x TYPE i.", "IF lv_x = 1."),
    ("func_start", "METHOD do_thing.", "DATA lv_x TYPE i."),
    ("class_start", "CLASS zcl_foo DEFINITION.", "METHOD do_thing."),
    ("safety", "TRY.", "DATA lv_x TYPE i."),
    ("safety_bypasses", "DATA lr_data TYPE REF TO DATA.", "DATA lv_x TYPE i."),
    ("high_risk_execution", "EXEC SQL.", "DATA lv_x TYPE i."),
    ("io", "SELECT * FROM zfoo INTO TABLE @DATA(lt_foo).", "DATA lv_x TYPE i."),
    ("api", "@OData.publish: true", "DATA lv_x TYPE i."),
    ("state_mutation", "MOVE lv_a TO lv_b.", "DATA lv_x TYPE i."),
    ("dead_code", "* DATA lv_old TYPE i.", "* just a note"),
    ("doc", "* AUTHOR: Jane Doe", "* just a note"),
    ("test", "METHOD foo FOR TESTING.", "DATA lv_x TYPE i."),
    ("concurrency", "CALL FUNCTION 'ENQUEUE_FOO'.", "DATA lv_x TYPE i."),
    ("ui_framework", "CALL SCREEN 100.", "DATA lv_x TYPE i."),
    ("globals", "IF sy-subrc = 0.", "DATA lv_x TYPE i."),
    ("decorators", "@AbapCatalog.sqlViewName: 'ZFOO'", "DATA lv_x TYPE i."),
    ("generics", "DATA lr_data TYPE REF TO DATA.", "DATA lv_x TYPE i."),
    ("comprehensions", "DATA(lt_result) = VALUE #( ).", "DATA lv_x TYPE i."),
    ("scientific", "lv_result = ABS( lv_x ).", "DATA lv_x TYPE i."),
    ("reflection_metaprogramming", "cl_abap_typedescr=>describe_by_data( lv_x ).", "DATA lv_x TYPE i."),
    ("import", "INCLUDE zxyz_top.", "DATA lv_x TYPE i."),
    ("ownership", "AUTHOR: Jane Doe", "DATA lv_x TYPE i."),
    ("planned_debt", "* TODO: fix this", "* done"),
    ("fragile_debt", "* HACK: workaround", "* clean"),
    ("spec_exposure", "[SPEC-123]", "* just a note"),
    ("ssr_boundaries", "METHOD if_http_extension~handle_request.", "DATA lv_x TYPE i."),
    ("events", "RAISE EVENT my_event.", "DATA lv_x TYPE i."),
    ("dependency_injection", "GET BADI lo_badi.", "DATA lv_x TYPE i."),
    ("macros", "DEFINE my_macro.", "DATA lv_x TYPE i."),
    ("pointers", "<fs_table>", "DATA lv_x TYPE i."),
    ("memory_alloc", "CREATE OBJECT lo_obj.", "DATA lv_x TYPE i."),
    ("telemetry", "CALL METHOD cl_bali_log=>create.", "DATA lv_x TYPE i."),
    ("debug_prints", "WRITE: 'hello'.", "DATA lv_x TYPE i."),
    ("explicit_casts", "DATA(lv_x) = CAST i( lv_ref ).", "DATA lv_x TYPE i."),
    ("panics_and_aborts", "RAISE EXCEPTION TYPE zcx_foo.", "DATA lv_x TYPE i."),
    ("thread_sleeps", "WAIT UP TO 5 SECONDS.", "DATA lv_x TYPE i."),
    ("bitwise_ops", "lv_result = lv_a BIT-AND lv_b.", "DATA lv_x TYPE i."),
    ("sync_locks", "CALL FUNCTION 'ENQUEUE_FOO'.", "DATA lv_x TYPE i."),
    ("immutability_locks", "CONSTANTS: lc_max TYPE i VALUE 10.", "DATA lv_x TYPE i."),
    ("cleanup", "FREE lo_obj.", "DATA lv_x TYPE i."),
    ("encapsulation", "PRIVATE SECTION.", "PUBLIC SECTION."),
    ("listeners", "METHODS handle_event FOR EVENT my_event OF cl_foo.", "DATA lv_x TYPE i."),
    ("test_skip", "IGNORE.", "DATA lv_x TYPE i."),
]


@pytest.mark.parametrize("signature,positive,negative", _ABAP_SIMPLE_CASES)
def test_abap_signature_positive_and_negative(signature, positive, negative):
    pattern = ABAP_RULES[signature]
    assert pattern is not None, f"abap's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"abap {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"abap {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_abap_dependency_capture_extracts_include_and_type_pool():
    pattern = ABAP_RULES["_dependency_capture"]
    m = pattern.search("INCLUDE zxyz_top.")
    assert m and m.group(1) == "zxyz_top"
    m2 = pattern.search("TYPE-POOLS abap.")
    assert m2 and m2.group(1) == "abap"


def test_abap_func_start_excludes_structural_headers_and_requires_line_start():
    """
    func_start's negative lookahead excludes CLASS/INTERFACE/DATA/TYPES/
    CONSTANTS headers, and (positional_anchored family) the match must
    anchor at the physical start of the line -- a keyword appearing after
    other code on the same line must not count.
    """
    func_start = ABAP_RULES["func_start"]
    assert not func_start.search("CLASS zcl_foo DEFINITION.")
    assert not func_start.search("DATA lv_x TYPE i.")
    assert not func_start.search("TYPES ty_foo TYPE i.")
    assert not func_start.search("CONSTANTS lc_max TYPE i VALUE 10.")

    # column accuracy: METHOD appearing after other code on the same physical
    # line is not a real declaration and must not match
    assert not func_start.search("ENDIF. METHOD foo.")

    # leading whitespace must still be tolerated (real ABAP is often indented)
    m = func_start.search("\tMETHOD do_thing.")
    assert m and m.group(1) == "do_thing"


def test_abap_class_start_view_entity_capture_regression():
    """
    Regression test for a real bug: `VIEW` and `ENTITY` were mutually
    exclusive alternatives in the CDS branch, but the standard modern RAP
    syntax is `DEFINE VIEW ENTITY <name>` (both words together -- exactly
    what this dict's _meta target_version claims to cover: "ABAP Cloud /
    RAP / Modern 7.5x+ Syntax"). The old pattern matched `VIEW` as the
    keyword and then captured the literal word `ENTITY` as if it were the
    entity name, instead of the real name that follows it.
    """
    old_pattern = re.compile(
        r"^[ \t]*(?:CLASS|INTERFACE)\s+([a-zA-Z0-9_-]+)(?=[ \t]+DEFINITION|[ \t\n\.]|$)"
        r"|^[ \t]*DEFINE\s+(?:ROOT[ \t]+)?(?:VIEW|ENTITY|PROJECTION\s+VIEW|BEHAVIOR)\s+([a-zA-Z0-9_-]+)",
        re.I | re.M,
    )
    realistic = "DEFINE VIEW ENTITY zi_foo AS SELECT FROM zfoo"
    old_m = old_pattern.search(realistic)
    assert old_m and old_m.group(2) == "ENTITY", "sanity check: bug must reproduce against the old pattern"

    class_start = ABAP_RULES["class_start"]
    m = class_start.search(realistic)
    assert m and m.group(2) == "zi_foo", "modern RAP 'VIEW ENTITY' form should capture the real entity name"

    m2 = class_start.search("DEFINE ROOT VIEW ENTITY zi_root AS SELECT FROM zbar")
    assert m2 and m2.group(2) == "zi_root", "ROOT VIEW ENTITY form regressed"

    m3 = class_start.search("DEFINE PROJECTION VIEW ENTITY zc_proj AS PROJECTION ON zi_foo")
    assert m3 and m3.group(2) == "zc_proj", "PROJECTION VIEW ENTITY form regressed"

    # legacy classic-CDS form (no ENTITY keyword) must still work
    m4 = class_start.search("DEFINE VIEW zi_legacy AS SELECT FROM zfoo")
    assert m4 and m4.group(2) == "zi_legacy", "legacy 'DEFINE VIEW <name>' form regressed"


def test_abap_doc_trailing_colon_boundary_regression():
    """
    Regression test for a real bug (Rule 9, mirror case): the pattern was
    `...\\b(?:AUTHOR|DESCRIPTION|PURPOSE|REMARKS):\\b`. A trailing `\\b`
    placed directly after a literal `:` can never fire when the colon is
    followed by whitespace (both sides of that position are non-word) --
    and real ABAP headers are always written as "AUTHOR: Jane Doe" (space
    after the colon), so the realistic form never matched under the old
    pattern. `:` is already self-delimiting; the trailing `\\b` was dropped.
    """
    old_pattern = re.compile(
        r'^"!\s*@(?:parameter|raising|return)|\b(?:AUTHOR|DESCRIPTION|PURPOSE|REMARKS):\b',
        re.I | re.M,
    )
    realistic = "* AUTHOR: Jane Doe"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    doc = ABAP_RULES["doc"]
    assert doc.search(realistic), "realistic space-after-colon AUTHOR header still didn't match"
    assert doc.search('"! @parameter iv_x | The input'), "ABAPDoc form regressed"


def test_abap_concurrency_and_sync_locks_enqueue_boundary_regression():
    """
    Regression test for a real bug (Rule 9, mirror case) shared by
    `concurrency` and `sync_locks`: both had `ENQUEUE_`/`DEQUEUE_` inside a
    shared `\\b(...)\\b` group. Since `_` is a word character and real
    function-module names always continue with more word characters right
    after (`ENQUEUE_FOO`), the trailing `\\b` could never fire -- both sides
    of that position are word chars. Confirmed the realistic call
    `"CALL FUNCTION 'ENQUEUE_FOO'."` never matched under the old patterns.
    """
    old_concurrency = re.compile(
        r"\b(STARTING\s+NEW\s+TASK|ENQUEUE_|DEQUEUE_|WAIT\s+UP\s+TO)\b|CALL\s+FUNCTION\s+[^\n;]+\s+IN\s+BACKGROUND\s+TASK",
        re.I,
    )
    old_sync_locks = re.compile(r"\b(ENQUEUE_|DEQUEUE_)\b", re.I)
    realistic = "CALL FUNCTION 'ENQUEUE_FOO'."

    assert not old_concurrency.search(realistic), "sanity check: concurrency bug must reproduce"
    assert not old_sync_locks.search(realistic), "sanity check: sync_locks bug must reproduce"

    assert ABAP_RULES["concurrency"].search(realistic)
    assert ABAP_RULES["sync_locks"].search(realistic)
    assert ABAP_RULES["concurrency"].search("CALL FUNCTION 'DEQUEUE_FOO'.")
    assert ABAP_RULES["sync_locks"].search("CALL FUNCTION 'DEQUEUE_FOO'.")

    # the other concurrency alternatives must still work after restructuring
    assert ABAP_RULES["concurrency"].search("STARTING NEW TASK 'TASK1'.")
    assert ABAP_RULES["concurrency"].search("WAIT UP TO 5 SECONDS.")


def test_abap_dead_code_requires_column_anchor_not_just_token_presence():
    """
    Positional-family accuracy check (this language's lexical family is
    `positional_anchored`): dead_code's `*`-comment alternative requires
    the asterisk at the true start of the line, not merely present
    somewhere in the text. A stray `*` used as a multiplication operator
    earlier in a line, even one that happens to be followed by the word
    "DATA" later on the same physical line, must not count -- only a
    genuine column-anchored comment line does.
    """
    dead_code = ABAP_RULES["dead_code"]
    assert not dead_code.search("lv_x = 5 * 2.  DATA lv_new TYPE i."), (
        "a non-column-1 '*' followed by DATA later on the same line must not count as dead_code"
    )
    assert dead_code.search("* DATA lv_old TYPE i."), "a genuine column-1 comment line must still match"

    multi_line = "lv_x = 5.  * not at column 1, mentions DATA\n* DATA lv_old TYPE i."
    matches = dead_code.findall(multi_line)
    assert matches == ["* DATA"], f"only the real column-1 comment line should match, got {matches!r}"


def test_abap_doc_vs_ownership_overlap_is_intentional():
    """
    Ambiguity sweep finding: `doc` and `ownership` both fire on an
    "AUTHOR: Jane Doe" header line. Confirmed intentional, not a bug --
    both signatures are legitimately about traceability/metadata, and
    `ownership` additionally captures the specific author name (group 1)
    for downstream attribution, which `doc` does not attempt.
    """
    header = "* AUTHOR: Jane Doe"
    assert ABAP_RULES["doc"].search(header)
    m = ABAP_RULES["ownership"].search(header)
    assert m and m.group(1) == "Jane Doe"


def test_abap_explicit_casts_vs_pointers_intentional_double_classification():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). Here the two
    signatures genuinely overlap: `ASSIGNING <fs> CASTING` is
    simultaneously an explicit unsafe cast (explicit_casts) AND a
    field-symbol pointer dereference (pointers) -- both true at once, an
    intentional double-classification (Rule 1: semantic intent over
    keyword matching), not a false collision to fix.
    """
    explicit_casts = ABAP_RULES["explicit_casts"]
    pointers = ABAP_RULES["pointers"]

    combined = "ASSIGNING <fs_foo> CASTING"
    assert explicit_casts.search(combined)
    assert pointers.search(combined)

    # a plain field-symbol dereference with no casting is pointers-only
    plain = "<fs_foo> = 5."
    assert pointers.search(plain)
    assert not explicit_casts.search(plain)


def test_abap_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). abap's macros
    keyword is `DEFINE`/`END-OF-DEFINITION`, structurally distinct from
    func_start's `METHOD`/`FORM`/`FUNCTION`/`MODULE` -- no realistic
    overlap.
    """
    func_start = ABAP_RULES["func_start"]
    macros = ABAP_RULES["macros"]

    for macro_line in ("DEFINE my_macro.", "END-OF-DEFINITION."):
        assert macros.search(macro_line), f"macros should match {macro_line!r}"
        assert not func_start.search(macro_line), f"func_start should not match macro directive {macro_line!r}"

    labeled = "METHOD do_thing."
    assert func_start.search(labeled)
    assert not macros.search(labeled)


def test_abap_func_start_vs_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C#'s deeply nested
    generic return types triggering catastrophic backtracking on
    func_start). abap's generics maps to `TYPE ANY`/`TYPE REF TO DATA`
    -style declarations, structurally distinct from func_start's
    `METHOD`/`FORM`/`FUNCTION`/`MODULE` keywords -- no realistic overlap,
    and func_start doesn't attempt to parse type parameters at all so a
    long generic-like type chain poses no backtracking risk to it either.
    """
    func_start = ABAP_RULES["func_start"]
    generics = ABAP_RULES["generics"]

    type_decl = "DATA lr_data TYPE REF TO DATA."
    assert generics.search(type_decl)
    assert not func_start.search(type_decl)

    method_decl = "METHOD do_thing."
    assert func_start.search(method_decl)
    assert not generics.search(method_decl)

    assert_redos_immune(func_start, "DATA lr TYPE REF TO " + "data " * 50000, timeout_sec=3.0)


def test_abap_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: abap is `positional_anchored` -- there is no
    native multi-line block-comment syntax (only column-1 `*` full-line
    comments and, in the real pipeline, ABAP's own `"` inline marker --
    see #746 for the separate prism-level gap around that). No rule
    tracks open/close block-comment state; confirms a stray comment-like
    line doesn't fool a structural rule into a false match.
    """
    branch = ABAP_RULES["branch"]
    stray = "* not real code, just a note\nIF lv_x = 1."
    assert branch.search(stray), "branch should still see IF regardless of the preceding comment line"


def test_abap_redos_immunity_sweep():
    """
    ReDoS immunity sweep across abap's rules with unbounded-looking
    quantifiers. Verified via a systematic scaling sweep before writing
    this test (adversarial "never closes" payloads at n=2000/8000/32000
    against every non-None rule): nothing exceeded 0.3s at n=32000.
    """
    assert_redos_immune(ABAP_RULES["func_start"], "METHOD " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["class_start"], "DEFINE VIEW ENTITY " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["args"], "IMPORTING VALUE(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["safety_bypasses"], "ASSIGN " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["concurrency"], "CALL FUNCTION " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["state_mutation"], "INSERT " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["events"], "FOR EVENT " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["decorators"], "@" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["dead_code"], "*" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["ownership"], "AUTHOR: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["_dependency_capture"], "INCLUDE " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(ABAP_RULES["reflection_metaprogramming"], "ASSIGN (" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert ABAP_RULES["func_start"].search("METHOD do_thing.")
    assert ABAP_RULES["class_start"].search("CLASS zcl_foo DEFINITION.")
    assert ABAP_RULES["concurrency"].search("CALL FUNCTION 'ENQUEUE_FOO'.")
