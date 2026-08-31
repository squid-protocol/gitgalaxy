"""cobol strict structural-signature coverage.

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
# TEST 5: COBOL GHOST SATELLITE HALLUCINATIONS
# Reference: language_standards.py (Line ~2470)
# ==============================================================================
def test_cobol_ghost_satellite_prevention():
    """
    Proves that heavily indented SQL queries or data divisions are explicitly
    blocked from being hallucinated as executable paragraphs.
    """
    cobol_func = LANGUAGE_DEFINITIONS["cobol"]["rules"]["func_start"]

    # 1. The SQL Ghost (Indented table column with a period)
    sql_ghost = "           POLICY.CUSTOMERNUMBER."
    assert len(list(cobol_func.finditer(sql_ghost))) == 0, "Hallucinated an SQL column as a paragraph!"

    # 2. The Data Ghost (01 Level)
    data_ghost = "       01  WS-POLICY-RECORD."
    assert len(list(cobol_func.finditer(data_ghost))) == 0, "Hallucinated a Data Division struct as a paragraph!"

    # 3. The Valid Paragraph
    valid_para = "       100-PROCESS-RECORDS SECTION."
    matches = list(cobol_func.finditer(valid_para))
    assert len(matches) == 1
    assert matches[0].group(1) == "100-PROCESS-RECORDS"


# ==============================================================================
# COBOL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #776, part of epic #518)
# ==============================================================================
# NOTE: filed as one of 6 new sub-issues (#773-778) after auditing and
# rejecting the epic's founding premise that C/C++/C#/COBOL/Rust/TypeScript
# already had adequate coverage -- see #518's updated "Why" section. This
# language previously had only one isolated regression test
# (test_cobol_ghost_satellite_prevention, covering func_start false-positive
# prevention against SQL columns and data-division structs), not the full
# per-signature template.
COBOL_RULES = LANGUAGE_DEFINITIONS["cobol"]["rules"]

_COBOL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "IF X > 0", "MOVE X TO Y."),
    ("args", "USING BY REFERENCE WS-INPUT", "MOVE X TO Y."),
    ("structural_boundaries", "PROCEDURE DIVISION.", "MOVE X TO Y."),
    ("func_start", "       100-PROCESS-RECORDS SECTION.", "       01  WS-POLICY-RECORD."),
    ("class_start", "       PROGRAM-ID. MYPROG.", "       100-PROCESS-RECORDS SECTION."),
    ("safety", "END-IF", "MOVE X TO Y."),
    ("safety_bypasses", "GO TO PARA-X", "MOVE X TO Y."),
    ("high_risk_execution", "STOP RUN.", "MOVE X TO Y."),
    ("io", "READ CUSTOMER-FILE", "MOVE X TO Y."),
    ("api", "LINKAGE SECTION.", "MOVE X TO Y."),
    ("state_mutation", "MOVE X TO Y.", "IF X > 0"),
    ("dead_code", "      * MOVE X TO Y.", "      * just a note"),
    ("doc", "       AUTHOR. Jane Doe.", "      * just a note"),
    ("test", "ASSERT X = Y", "MOVE X TO Y."),
    ("concurrency", "EXEC CICS ENQ END-EXEC", "MOVE X TO Y."),
    ("ui_framework", "SCREEN SECTION.", "MOVE X TO Y."),
    ("globals", "WORKING-STORAGE SECTION.", "MOVE X TO Y."),
    ("decorators", "      >>DEFINE VAR", "MOVE X TO Y."),
    ("generics", "CLASS-ID. FOO USING BAR", "MOVE X TO Y."),
    ("scientific", "FUNCTION SQRT(X)", "MOVE X TO Y."),
    ("reflection_metaprogramming", "05 WS-ALT REDEFINES WS-ORIG.", "MOVE X TO Y."),
    ("import", "       COPY CUSTREC.", "MOVE X TO Y."),
    ("ownership", "       AUTHOR. Jane Doe.", "      * just a note"),
    ("planned_debt", "      * TODO: fix this", "      * done"),
    ("fragile_debt", "      * HACK: workaround", "      * clean"),
    ("spec_exposure", "[SPEC-123]", "      * just a note"),
    ("ssr_boundaries", "EXEC CICS WEB SEND END-EXEC", "MOVE X TO Y."),
    ("events", "CALL 'MQPUT' USING X.", "MOVE X TO Y."),
    ("macros", "      DEFINE VAR-NAME.", "MOVE X TO Y."),
    ("pointers", "01 WS-PTR USAGE POINTER.", "MOVE X TO Y."),
    ("memory_alloc", "ALLOCATE WS-BUFFER.", "MOVE X TO Y."),
    ("telemetry", "EXEC CICS WRITEQ TD END-EXEC", "MOVE X TO Y."),
    ("debug_prints", "DISPLAY X.", "MOVE X TO Y."),
    ("explicit_casts", "05 WS-ALT REDEFINES WS-ORIG.", "MOVE X TO Y."),
    ("panics_and_aborts", "GOBACK.", "MOVE X TO Y."),
    ("thread_sleeps", "EXEC CICS DELAY END-EXEC", "MOVE X TO Y."),
    ("bitwise_ops", "FUNCTION BIT-AND(X, Y)", "MOVE X TO Y."),
    ("sync_locks", "EXEC CICS ENQ END-EXEC", "MOVE X TO Y."),
    ("immutability_locks", "01 WS-X CONSTANT AS 5.", "MOVE X TO Y."),
    ("cleanup", "CLOSE CUSTOMER-FILE.", "MOVE X TO Y."),
    ("encapsulation", "LOCAL-STORAGE SECTION.", "MOVE X TO Y."),
    ("listeners", "EXEC CICS RECEIVE END-EXEC", "MOVE X TO Y."),
    ("test_skip", "IGNORE.", "MOVE X TO Y."),
    ("serialization_parsing", "STRING A B INTO C.", "MOVE X TO Y."),
    ("regex_execution", "INSPECT X TALLYING Y.", "MOVE X TO Y."),
    ("time_date_logic", "ACCEPT WS-DATE FROM DATE.", "MOVE X TO Y."),
    ("ipc_rpc_bridges", "CALL 'SUBPROG' USING X.", "MOVE X TO Y."),

    # --- DEEP ADVERSARIAL CASES ---
    # args: multiline parsing and commas
    ("args", "USING \n BY REFERENCE WS-A \n BY CONTENT WS-B", "MOVE X TO Y."),
    ("args", "RETURNING \n WS-STATUS", "MOVE X TO Y."),
    ("args", "USING WS-A, WS-B, WS-C", "MOVE X TO Y."),
    ("args", "USING \n WS-A \n WS-B \n WS-C", "MOVE X TO Y."),
    ("args", "USING BY VALUE WS-A", "MOVE X TO Y."),

    # branch: edge cases, multi-word, line-wrapped
    ("branch", "DEPENDING \n ON", "MOVE X TO Y."),
    ("branch", "ON \n SIZE ERROR", "MOVE X TO Y."),
    ("branch", "INVALID \n KEY", "MOVE X TO Y."),
    ("branch", "AT \n END", "MOVE X TO Y."),
    ("branch", "NOT AT END", None),

    # func_start: reserved words shouldn't match, edge margins
    ("func_start", "       MY-FUNC SECTION 12.", "       DIVISION."),
    ("func_start", "       1234-VALID-PARA.", "       SECTION."),
    ("func_start", "       SOME-PARA.", "       PROCEDURE DIVISION."),
    ("func_start", "000100 VALID-FUNC-WITH-MARGIN.", "000100 WORKING-STORAGE SECTION."),
    ("func_start", "      -VALID-WITH-DASH.", "      *COMMENT-SHOULD-NOT-MATCH."),

    # class_start: trailing clauses, optional names
    ("class_start", "       PROGRAM-ID. MYPROG IS INITIAL.", "       100-PROCESS-RECORDS SECTION."),
    ("class_start", "       CLASS-ID. FOO INHERITS BASE.", "       01 WS-DATA."),


    ("class_start", "000100 PROGRAM-ID. P1.", "       PROCEDURE DIVISION."),

    # structural_boundaries:
    ("structural_boundaries", "PROCEDURE DIVISION", "MOVE X TO Y."),
    ("structural_boundaries", "XML PARSE", "MOVE X TO Y."),
    ("structural_boundaries", "JSON GENERATE", "MOVE X TO Y."),
    ("structural_boundaries", "STOP RUN", "MOVE X TO Y."),
    ("structural_boundaries", "EXIT PROGRAM", "MOVE X TO Y."),
]



@pytest.mark.parametrize("signature,positive,negative", _COBOL_SIMPLE_CASES)
def test_cobol_signature_positive_and_negative(signature, positive, negative):
    pattern = COBOL_RULES[signature]
    assert pattern is not None, f"cobol's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"cobol {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"cobol {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_cobol_import_key_completeness_regression():
    """
    Real bug found and fixed (Strict Feature Parity, Rule 4): the `import`
    key was missing entirely from cobol's rules dict (not even explicitly
    `None`), despite COBOL clearly having a real dependency-inclusion
    mechanism (COPY/INCLUDE copybooks) -- confirmed by `_dependency_capture`
    already correctly extracting these same targets. A silently absent key
    is a schema-completeness gap, not an intentional None.
    """
    assert "import" in COBOL_RULES
    assert COBOL_RULES["import"] is not None
    assert COBOL_RULES["import"].search("       COPY CUSTREC.")
    assert COBOL_RULES["import"].search("       INCLUDE CUSTREC.")
    assert not COBOL_RULES["import"].search("       MOVE X TO Y.")


def test_cobol_dependency_capture_extracts_copy_and_include_targets():
    dep = COBOL_RULES["_dependency_capture"]
    m = dep.search("       COPY CUSTREC.")
    assert m and m.group(1) == "CUSTREC"

    m2 = dep.search("       INCLUDE ORDERREC.")
    assert m2 and m2.group(1) == "ORDERREC"


def test_cobol_func_start_ghost_hallucination_prevention():
    """
    Known ambiguity pattern from the issue template (already found in
    COBOL itself: heavily indented SQL columns and 01-level data-division
    structs hallucinated as executable paragraphs) -- already covered by
    an existing standalone regression test (`test_cobol_ghost_satellite_
    prevention`); confirmed it's absorbed into this full per-signature
    suite too.
    """
    func_start = COBOL_RULES["func_start"]
    assert not func_start.search("           POLICY.CUSTOMERNUMBER."), "hallucinated an SQL column as a paragraph"
    assert not func_start.search("       01  WS-POLICY-RECORD."), "hallucinated a Data Division struct as a paragraph"
    m = func_start.search("       100-PROCESS-RECORDS SECTION.")
    assert m and m.group(1) == "100-PROCESS-RECORDS"


def test_cobol_class_start_and_ownership_capture():
    cs = COBOL_RULES["class_start"]
    m = cs.search("       PROGRAM-ID. MYPROG.")
    assert m and m.group(1) == "MYPROG"

    own = COBOL_RULES["ownership"]
    m2 = own.search("       AUTHOR. Jane Doe.")
    assert m2 and m2.group(1).strip().rstrip(".") == "Jane Doe"


def test_cobol_events_quoted_mqput_boundary_regression():
    """
    Real bug found and fixed: the `CALL 'MQPUT'`/`CALL 'MQGET'` alternative
    shared a trailing `\\b` with the word-ending EXEC CICS alternative, but
    ends in a literal `'` (non-word) -- `\\b` right after can only fire if
    the next char is a word character, never true for the realistic form
    (`CALL 'MQPUT' USING queue-name.`, whitespace after the closing quote).
    """
    old_pattern = re.compile(r"\b(?:EXEC\s+CICS\s+(?:SIGNAL|HANDLE\s+CONDITION)|CALL\s+'(?:MQPUT|MQGET)')\b", re.I)
    realistic = "CALL 'MQPUT' USING queue-name."
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    events = COBOL_RULES["events"]
    assert events.search(realistic)
    assert events.search("EXEC CICS SIGNAL EVENT(x) END-EXEC"), "the already-working EXEC CICS form must still work"
    assert events.search("CALL 'MQGET' USING queue-name.")


def test_cobol_ipc_rpc_bridges_call_whitespace_boundary_regression():
    """
    Real bug found and fixed: `CALL\\s+` shared a trailing `\\b` with
    word-ending siblings, but ends in whitespace (non-word) -- broke on
    the dominant realistic call form, a quoted program-name literal
    (`CALL 'SUBPROGRAM' USING ...`), where a quote (non-word) follows the
    consumed whitespace. Only the less-common unquoted data-name form
    (`CALL WS-PROGRAM-NAME`) happened to work.
    """
    old_pattern = re.compile(r"\b(CALL\s+|EXEC\s+CICS\s+(?:LINK|XCTL|START|RETURN)|EXEC\s+SQL)\b", re.I)
    realistic = "CALL 'SUBPROGRAM' USING x."
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    ipc = COBOL_RULES["ipc_rpc_bridges"]
    assert ipc.search(realistic)
    assert ipc.search("CALL WS-PROGRAM-NAME USING x."), "the already-working unquoted form must still work"
    assert ipc.search("EXEC CICS LINK PROGRAM('X') END-EXEC")
    assert ipc.search("EXEC SQL SELECT 1 END-EXEC")


def test_cobol_time_date_logic_severe_redos_regression():
    """
    Real bug found and fixed: `\\s+.*\\s+FROM` has three adjacent
    quantifiers whose character sets overlap (`.` matches whitespace too),
    so the engine could partition the space between the receiving-
    identifier and the two `\\s+`s in exponentially many ways before
    finding `FROM` -- confirmed 9+ seconds at just n=2000 (far worse than
    the typical ~4x/doubling shape most ReDoS findings in this epic show).
    Real COBOL syntax only ever has a single identifier there; replaced
    the unbounded `.*` with a real identifier character class.
    """
    assert_redos_immune(COBOL_RULES["time_date_logic"], "ACCEPT " + " " * 100000, timeout_sec=3.0)
    assert COBOL_RULES["time_date_logic"].search("ACCEPT WS-DATE FROM DATE.")
    assert COBOL_RULES["time_date_logic"].search("ACCEPT WS-TIME FROM TIME.")
    assert COBOL_RULES["time_date_logic"].search("MOVE FUNCTION CURRENT-DATE TO WS-DATE.")


def test_cobol_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). COBOL's
    explicit_casts uses the REDEFINES clause (memory reinterpretation) and
    pointers uses the POINTER/ADDRESS OF keywords, structurally distinct
    -- no realistic overlap.
    """
    explicit_casts = COBOL_RULES["explicit_casts"]
    pointers = COBOL_RULES["pointers"]

    redefines = "05 WS-ALT REDEFINES WS-ORIG."
    assert explicit_casts.search(redefines)
    assert not pointers.search(redefines)

    ptr_decl = "01 WS-PTR USAGE POINTER."
    assert pointers.search(ptr_decl)
    assert not explicit_casts.search(ptr_decl)


def test_cobol_intentional_double_classification_sweep():
    """
    Ambiguity sweep finding: several COBOL constructs legitimately fire
    two signatures representing different perspectives on the same
    underlying action -- intentional, not false collisions:
    - `AUTHOR.` header -> doc + ownership (ownership additionally captures
      the name)
    - `REDEFINES` -> explicit_casts (memory reinterpretation) +
      reflection_metaprogramming (memory aliasing)
    - `EXEC CICS DELAY` -> concurrency (async primitive) + thread_sleeps
      (blocking wait)
    - `EXEC CICS ENQ` -> concurrency + sync_locks (both explicitly define
      ENQ as their own primitive)
    - `CALL 'MQGET'` -> events (pub/sub action) + listeners (bare MQGET
      substring, waiting to receive)
    - `FREE` -> cleanup (resource release) + memory_alloc (deallocation)
    - `STOP RUN`/`GOBACK` -> high_risk_execution + panics_and_aborts +
      structural_boundaries (program termination is simultaneously risky,
      an abort, and a sequential-boundary keyword)
    - `STRING ... INTO ...` -> serialization_parsing + state_mutation
    - `EXEC CICS`/`EXEC SQL` (any) -> reflection_metaprogramming's own
      bare catch-all alternative deliberately overlaps with every other
      CICS/SQL-specific signature (io, concurrency, events, memory_alloc,
      telemetry, sync_locks, listeners, ssr_boundaries, thread_sleeps,
      ipc_rpc_bridges, ui_framework) -- a broad "this touches CICS/SQL"
      signal layered on top of the specific ones, not a bug.
    """
    header = "       AUTHOR. Jane Doe."
    assert COBOL_RULES["doc"].search(header)
    assert COBOL_RULES["ownership"].search(header)

    redefines = "05 WS-ALT REDEFINES WS-ORIG."
    assert COBOL_RULES["explicit_casts"].search(redefines)
    assert COBOL_RULES["reflection_metaprogramming"].search(redefines)

    delay = "EXEC CICS DELAY END-EXEC"
    assert COBOL_RULES["concurrency"].search(delay)
    assert COBOL_RULES["thread_sleeps"].search(delay)

    enq = "EXEC CICS ENQ END-EXEC"
    assert COBOL_RULES["concurrency"].search(enq)
    assert COBOL_RULES["sync_locks"].search(enq)

    mqget = "CALL 'MQGET' USING queue-name."
    assert COBOL_RULES["events"].search(mqget)
    assert COBOL_RULES["listeners"].search(mqget)

    free_call = "FREE WS-BUFFER."
    assert COBOL_RULES["cleanup"].search(free_call)
    assert COBOL_RULES["memory_alloc"].search(free_call)

    stop_run = "STOP RUN."
    assert COBOL_RULES["high_risk_execution"].search(stop_run)
    assert COBOL_RULES["panics_and_aborts"].search(stop_run)
    assert COBOL_RULES["structural_boundaries"].search(stop_run)

    string_stmt = "STRING A B INTO C."
    assert COBOL_RULES["serialization_parsing"].search(string_stmt)
    assert COBOL_RULES["state_mutation"].search(string_stmt)

    for other_signal, text in [
        ("io", "EXEC CICS READ FILE(X) END-EXEC"),
        ("concurrency", "EXEC CICS WAIT EVENT(X) END-EXEC"),
        ("telemetry", "EXEC CICS WRITEQ TD END-EXEC"),
    ]:
        assert COBOL_RULES[other_signal].search(text)
        assert COBOL_RULES["reflection_metaprogramming"].search(text), (
            f"reflection_metaprogramming's bare EXEC CICS catch-all should also fire on {text!r}"
        )


def test_cobol_func_start_excludes_reserved_verbs_and_headers():
    """
    Ambiguity sweep finding: func_start's own negative lookahead already
    structurally excludes every reserved COBOL verb/division header that
    a crude token-overlap sweep flagged as "shared" with other signatures
    (CALL, MOVE, COMPUTE, PERFORM, CLOSE, DELETE, OPEN, READ, REWRITE,
    WRITE, EXIT, GOBACK, STOP, DISPLAY, DIVISION, SECTION headers) -- these
    are false alarms from the sweep picking up func_start's own exclusion
    list text, not a real double-match risk.

    #2538 extends this same list: CEE3DMP/CEEMOUT/CEEDUMP (the `telemetry`
    rule's LE runtime diagnostic service names) share the same "bare
    token + period" shape as a paragraph header when indented into Area B,
    with nothing in the old shield to exclude them.
    """
    func_start = COBOL_RULES["func_start"]
    for reserved in (
        "       CALL 'X'.",
        "       MOVE A TO B.",
        "       PERFORM PARA-X.",
        "       DISPLAY A.",
        "       PROCEDURE DIVISION.",
        "       STOP RUN.",
        "       GOBACK.",
        "            CEE3DMP.",
        "            CEEMOUT.",
        "            CEEDUMP.",
    ):
        assert not func_start.search(reserved), f"func_start incorrectly matched reserved line {reserved!r}"


def test_cobol_redos_immunity_sweep():
    """
    ReDoS immunity sweep across cobol's remaining rules with unbounded-
    looking quantifiers, verified via a systematic scaling sweep
    (n=2000/4000/8000/16000) before writing this test.
    """
    assert_redos_immune(COBOL_RULES["args"], "USING " + "A," * 50000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["func_start"], "PARA-NAME" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["func_start"], "      " + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["class_start"], "PROGRAM-ID. " + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["decorators"], ">> " + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["macros"], "DEFINE " + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["_dependency_capture"], "COPY " + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["import"], "COPY " + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["doc"], "AUTHOR." + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["ownership"], "AUTHOR. " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["generics"], "CLASS-ID. FOO USING " + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["dead_code"], "      *" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["events"], "CALL '" + "A" * 100000, timeout_sec=3.0)
    assert_redos_immune(COBOL_RULES["ipc_rpc_bridges"], "CALL " + " " * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert COBOL_RULES["func_start"].search("       100-PROCESS-RECORDS SECTION.")
    assert COBOL_RULES["class_start"].search("       PROGRAM-ID. MYPROG.")
    assert COBOL_RULES["time_date_logic"].search("ACCEPT WS-DATE FROM DATE.")
