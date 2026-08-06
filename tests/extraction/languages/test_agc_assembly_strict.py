"""agc_assembly strict structural-signature coverage.

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


# ==============================================================================
# AGC_ASSEMBLY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #572, part of epic #518)
# ==============================================================================
AGC_RULES = LANGUAGE_DEFINITIONS["agc_assembly"]["rules"]

_AGC_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- DEEP CASES: branch ---
    ("branch", "\tTCF\tFOO", "\tCA\tBAR"),
    ("branch", "  tcf  LBL", "TC_ALARM"),
    ("branch", "BZF\tTARGET", "BATCH_TCF"),
    ("branch", "\tRESUME\t", "MYCALL"),
    ("branch", "  CALL  ", "RETURN_VAL"),
    ("branch", "GOTO\tLBL", "GOTOO"),
    ("branch", "\tBZMF\tFOO", "BZMF_VAR"),
    ("branch", "BMI\tBAR", "BMIS"),

    # --- DEEP CASES: args ---
    ("args", "\tCA\tA", "\tCA\tBAR"),
    ("args", "\tEBANK= 4", "XEBANK="),
    ("args", "FBANK=", "CA_A"),
    ("args", "CA\t\t\tQ", "\tAUG\tA_BAR"),
    ("args", "MULT L", "ZBANK="),
    ("args", "AUG Q", "CA\tB"),
    ("args", "\tDIM\tL", "AD \n A"),
    ("args", "INCR Z", "AD_Z"),
    ("args", "\tCCS\tA", "CCS_A"),
    ("args", "DXCH\tZ", "DXCH_ZZ"),

    # --- DEEP CASES: structural_boundaries ---
    ("structural_boundaries", "\tCA\tBAR", "\tTCF\tFOO"),
    ("structural_boundaries", "  2OCT  ", "2OCTAL"),
    ("structural_boundaries", "XCH", "DECIMAL"),
    ("structural_boundaries", "COUNT\t", "MY_CA"),
    ("structural_boundaries", "SETLOC", "SETLOC_VAR"),
    ("structural_boundaries", "ERASE", "ERASED"),
    ("structural_boundaries", "\tCAF\tFOO", "CAFFEIN"),
    ("structural_boundaries", "CCS\tBAR", "CCSS"),
    ("structural_boundaries", "DXCH\tFOO", "DXCH_VAR"),

    # --- DEEP CASES: func_start ---
    ("func_start", "MYLABEL\tTC\tFOO", "\tTC\tFOO"),
    ("func_start", "MY_SUB1\tCAF\tFOO", "LBL\n\tTC"),
    ("func_start", "LABEL-123\tSTORE\tBAR", " LBL\tTC"),
    ("func_start", "LBL\t\t\tRVQ", "LBL\tFOO"),
    ("func_start", "SUB\tAD\t1", "LBL\tTCR_BAR"),
    ("func_start", "label\tdas", "LBL\t"),
    ("func_start", "ROUTINE2\tINDEX\tA", "ROUTINE\n\tCA\tA"),
    ("func_start", "FUNC_NAME\tINHINT", "FUNC\tCA_FOO"),
    ("safety", "\tINHINT", "\tCA\tBAR"),
    ("safety_bypasses", "\tTC\tJOBSLEEP", "\tCA\tBAR"),
    ("high_risk_execution", "\tTC\tCURTAINS", "\tCA\tBAR"),
    ("io", "\tCHANNEL\t7", "\tCA\tBAR"),
    ("api", "MYLABEL\tEQUALS\t5", "MYLABEL\tCA\tBAR"),
    ("state_mutation", "\tTS\tBAR", "\tCA\tBAR"),
    ("dead_code", "# CA BAR", "# just a note"),
    ("doc", "# SUBROUTINE FOO", "# just a note"),
    ("test", "\tSELFCHECK", "\tCA\tBAR"),
    ("concurrency", "\tEXEC", "\tCA\tBAR"),
    ("ui_framework", "\tVERB\t37", "\tCA\tBAR"),
    ("globals", "\tERASABLE MEMORY", "\tCA\tBAR"),
    ("scientific", "\tVAD\tVEC1", "\tCA\tBAR"),
    ("reflection_metaprogramming", "\tINDEX\tA", "\tCA\tBAR"),
    ("import", "\tSETLOC\tFOO", "\tCA\tBAR"),
    ("ownership", "# AUTHOR: Margaret Hamilton", "# just a note"),
    ("planned_debt", "# TODO: fix this", "# done"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# LUMINARY 099", "# just a note"),
    ("events", "\tKEYRUPT", "\tCA\tBAR"),
    ("macros", "MACRO", "\tCA\tBAR"),
    ("pointers", "\tINDEX\tA", "\tCA\tBAR"),
    ("memory_alloc", "\tERASABLE", "\tCA\tBAR"),
    ("telemetry", "\tDOWNLINK", "\tCA\tBAR"),
    ("debug_prints", "\tFLASH", "\tCA\tBAR"),
    ("explicit_casts", "\tEXTEND", "\tCA\tBAR"),
    ("panics_and_aborts", "\tTC\tBAILOUT", "\tCA\tBAR"),
    ("thread_sleeps", "\tVARDELAY", "\tCA\tBAR"),
    ("bitwise_ops", "\tMASK\tBAR", "\tTC\tBAR"),
    ("sync_locks", "\tINHINT", "\tCA\tBAR"),
    ("immutability_locks", "\tFIXED MEMORY", "\tCA\tBAR"),
    ("cleanup", "\tENDOFJOB", "\tCA\tBAR"),
    ("encapsulation", "MYLABEL\tCA\tBAR", "# just a comment line"),
    ("listeners", "\tEVENT WAIT", "\tCA\tBAR"),
]


@pytest.mark.parametrize("signature,positive,negative", _AGC_SIMPLE_CASES)
def test_agc_assembly_signature_positive_and_negative(signature, positive, negative):
    pattern = AGC_RULES[signature]
    assert pattern is not None, f"agc_assembly's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"agc_assembly {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"agc_assembly {signature!r} incorrectly matched an excluded case: {negative!r}"
        )


def test_agc_assembly_dependency_capture_extracts_bank_and_setloc():
    pattern = AGC_RULES["_dependency_capture"]
    m = pattern.search("\tSETLOC\tFOO")
    assert m and m.group(1) == "FOO"
    m2 = pattern.search("\tBANK\t27")
    assert m2 and m2.group(1) == "27"


def test_agc_assembly_func_start_cross_line_false_match_regression():
    """
    Regression test for a real bug: the lookahead's `\\s+` can cross a
    newline (Rule 5). A bare label with nothing else on its own line,
    followed by several blank lines and then an unrelated opcode, got
    falsely bound to that distant opcode -- confirmed
    "MYLABEL\\n\\n\\n\\tTC INTERNAL\\n" incorrectly captured MYLABEL. Real
    AGC label+opcode pairs are always on the same physical line
    (fixed-column YUL/GAP format).
    """
    old_pattern = re.compile(
        r"^([A-Z0-9_-]+)(?=\s+(?:TC|CA|CS|TS|DXCH|CCS|DLOAD|STORE|CALL|INDEX|EXTEND|INHINT|BZF|BZMF|BPL|BMI)\b)",
        re.M | re.I,
    )
    cross_line = "MYLABEL\n\n\n\tTC INTERNAL\n"
    old_m = old_pattern.search(cross_line)
    assert old_m and old_m.group(1) == "MYLABEL", "sanity check: bug must reproduce against the old pattern"

    func_start = AGC_RULES["func_start"]
    assert not func_start.search(cross_line), "cross-line false attribution still occurs"
    m = func_start.search("MYLABEL\tTC\tFOO")
    assert m and m.group(1) == "MYLABEL", "real same-line label form regressed"


def test_agc_assembly_encapsulation_case_regression():
    """
    Regression test for a real bug: `encapsulation` required a
    lowercase-starting label, but authentic AGC assembly source is
    uppercase-only -- every other rule in this language section uses
    `re.I`, and func_start's own capture class is `[A-Z0-9_-]+`, so the
    lowercase-only requirement here was a clear outlier. Confirmed a
    realistic label ("MYLABEL") never matched at all under the old pattern.
    """
    old_pattern = re.compile(r"^[ \t]*[a-z0-9_][a-zA-Z0-9_.]*", re.M)
    realistic = "MYLABEL\tCA\tBAR"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    encapsulation = AGC_RULES["encapsulation"]
    assert encapsulation.search(realistic), "uppercase AGC label still didn't match"


def test_agc_assembly_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). agc_assembly's
    func_start requires a label followed by a real opcode; macros maps to
    the `MACRO`/`ENDMAC`/`DEFINE` directive keywords -- structurally
    distinct, no realistic overlap.
    """
    func_start = AGC_RULES["func_start"]
    macros = AGC_RULES["macros"]

    macro_directive = "MACRO"
    assert macros.search(macro_directive)
    assert not func_start.search(macro_directive)

    labeled_opcode = "MYLABEL\tTC\tFOO"
    assert func_start.search(labeled_opcode)
    assert not macros.search(labeled_opcode)


def test_agc_assembly_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition). agc_assembly's explicit_casts
    maps only to the bare `EXTEND` opcode; pointers maps to
    `INDEX`/`INDIRECT`/`POINTER`/`CADR`/etc. and a leading-`*` symbol form --
    structurally distinct token shapes, verified no overlap even though
    `EXTEND` and `INDEX` commonly co-occur in real code (`EXTEND` then
    `INDEX A` as a paired instruction sequence) -- they match disjoint
    substrings, not a false collision.
    """
    explicit_casts = AGC_RULES["explicit_casts"]
    pointers = AGC_RULES["pointers"]

    combined = "\tEXTEND\n\tINDEX\tA"
    cast_match = explicit_casts.search(combined)
    ptr_match = pointers.search(combined)
    assert cast_match and cast_match.group(0).upper() == "EXTEND"
    assert ptr_match and ptr_match.group(0).upper() == "INDEX"


def test_agc_assembly_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: agc_assembly is `line_exclusive` (digitized
    source uses `#` exclusively for comments, no block syntax) -- no rule
    tracks open/close block-comment state. Confirms a stray unmatched
    comment-like token doesn't fool any rule into a false structural match.
    """
    branch = AGC_RULES["branch"]
    stray = "some text # not real code\n\tTCF\tFOO"
    assert branch.search(stray), "branch should still see TCF regardless of the preceding comment line"


def test_agc_assembly_redos_immunity_sweep():
    """
    ReDoS immunity sweep across agc_assembly's rules. Verified via a
    systematic scaling sweep before writing this test (5 adversarial
    payload shapes at n=2000/8000/32000 against every non-None rule):
    nothing exceeded 0.3s at n=32000 against any shape.
    """
    assert_redos_immune(AGC_RULES["func_start"], "LABEL" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["api"], "LABEL" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["encapsulation"], "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["_dependency_capture"], "SETLOC" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["pointers"], "*" + "A" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert AGC_RULES["func_start"].search("MYLABEL\tTC\tFOO")
    assert AGC_RULES["api"].search("MYLABEL\tEQUALS\t5")
