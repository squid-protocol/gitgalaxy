"""
COBOL extraction hardening (epic #813, issue #854). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for cobol in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the two old
monolithic dict files that had cobol entries (test_function_extraction_
strict.py, test_dependency_extraction_strict.py -- test_args_extraction_
strict.py and test_class_extraction_strict.py had no cobol entry at all;
args and class_start had zero prior test coverage before this file).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo, so a dotted
# `tests.extraction._extraction_harness` import only works by accident
# locally (e.g. `python -m pytest` from the repo root happens to put the
# root on sys.path) and fails in CI, which invokes the `pytest` console
# script directly. Insert this file's parent (tests/extraction/) onto
# sys.path instead, so the harness imports as a plain top-level module.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

COBOL_RULES = LANGUAGE_DEFINITIONS["cobol"]["rules"]

# ==============================================================================
# FUNC_START (func_start) -- paragraphs and sections.
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("       TargetFunc.", "TargetFunc"),  # carried-forward: fixed-format paragraph
        ("       TargetFunc SECTION.", "TargetFunc"),  # carried-forward: fixed-format section
        ("AB.", "AB"),  # free-format short name
        ("ABCDEF.", "ABCDEF"),  # free-format, exactly 6 chars (the margin-width trap)
        ("MAIN-PARAGRAPH.", "MAIN-PARAGRAPH"),  # free-format long hyphenated name
        ("       0100-INITIALIZE.", "0100-INITIALIZE"),  # numeric-prefixed, common mainframe convention
        ("main-para.", "main-para"),  # lowercase (GnuCOBOL is case-insensitive)
        ("       MAIN-PARA SECTION 10.", "MAIN-PARA"),  # segment number -- was a real bug, now fixed
        ("       MAIN-PARA SECTION 1.", "MAIN-PARA"),  # single-digit segment number
    ],
    "invalid": [
        "       01 TargetFunc.",  # carried-forward: data-division level number
        "           PERFORM TargetFunc.",  # carried-forward: PERFORM invocation, same line
        "       END-TargetFunc.",  # carried-forward: scope-terminator lookalike
        "       PROCEDURE DIVISION.",  # division header
        "       01 WS-RECORD.",  # level 01
        "       77 WS-COUNTER.",  # level 77
        "       88 WS-FLAG-ON VALUE 1.",  # level 88
        "      * TargetFunc.",  # column-7 comment marker
        "123456* TargetFunc.",  # column-7 comment with real sequence numbers
        "      *> TargetFunc.",  # free-format inline comment marker
    ],
    "pathological": [
        ("TargetFunc \n           SECTION.", "TargetFunc"),  # carried-forward: margin-hugging + vertical split
        ("       MAIN-PARA \n SECTION \n 10.", "MAIN-PARA"),  # segment number, vertically split
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_cobol_func_start_valid(payload, expected_name):
    assert_valid_match(COBOL_RULES["func_start"], payload, expected_name, "cobol.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_cobol_func_start_invalid(payload):
    assert_invalid_no_match(COBOL_RULES["func_start"], payload, "cobol.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_cobol_func_start_pathological(payload, expected_name):
    assert_pathological_match(COBOL_RULES["func_start"], payload, expected_name, "cobol.func_start")


def test_cobol_func_start_segment_number_regression():
    """
    Regression test for a real bug (epic #813/#854): SECTION had no
    allowance for a trailing SEGMENT-NUMBER (`MAIN-PARA SECTION 10.`) -- a
    real COBOL-68/74-era feature (program segmentation/overlay structuring
    for early mainframes' limited memory) still accepted by modern
    compilers for legacy program support. Without it, any segmented
    section header was entirely invisible. Fixed with an optional 1-2-digit
    segment number after SECTION.
    """
    func_start = COBOL_RULES["func_start"]
    m = func_start.search("       MAIN-PARA SECTION 10.")
    assert m and m.group(1) == "MAIN-PARA", "segmented section header regressed"
    m2 = func_start.search("       TargetFunc SECTION.")
    assert m2 and m2.group(1) == "TargetFunc", "plain (non-segmented) section must still match"


def test_cobol_func_start_known_limitation_multiline_perform_target_still_matches():
    """
    Documents a known, NOT-fixed limitation: a multi-line PERFORM statement
    (`PERFORM\\n    TargetFunc.`, invoking an EXISTING paragraph split
    across two physical lines for readability) is structurally
    indistinguishable from a genuinely NEW paragraph declaration
    (`TargetFunc.` on its own line) -- this rule has no cross-line
    statement-context tracking (it can't know the previous line ended with
    "PERFORM" rather than a real period terminator). Fixing this would
    require real statement-boundary tracking this regex-only engine
    doesn't have -- documented as a known limitation, not attempted here.
    """
    func_start = COBOL_RULES["func_start"]
    multiline_perform = "       PERFORM\n       TargetFunc."
    assert func_start.search(multiline_perform), (
        "documents current (expected, architecturally-not-fixable) regex behavior"
    )


def test_cobol_func_start_redos_immunity():
    """ReDoS sweep for the widened SECTION segment-number lookahead."""
    func_start = COBOL_RULES["func_start"]
    assert_redos_immune(func_start, "a" * 200000 + " SECTION 1", timeout_sec=3.0)
    assert func_start.search("TargetFunc.")


# ==============================================================================
# CLASS_START (class_start) -- PROGRAM-ID/CLASS-ID/INTERFACE-ID/FACTORY/OBJECT.
# NOTE: test_class_extraction_strict.py had NO cobol entry at all --
# class_start had zero prior test coverage before this file.
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("PROGRAM-ID. MyProgram.", "MyProgram"),
        ("CLASS-ID. MyClass.", "MyClass"),
        ("INTERFACE-ID. MyInterface.", "MyInterface"),
        ("       PROGRAM-ID. MyProgram.", "MyProgram"),  # fixed-format
        ("PROGRAM-ID. MyProgram IS INITIAL PROGRAM.", "MyProgram"),  # was a real bug, now fixed
        ("PROGRAM-ID. MyProgram IS COMMON PROGRAM.", "MyProgram"),  # was a real bug, now fixed
        ("CLASS-ID. MyClass FINAL.", "MyClass"),  # was a real bug, now fixed
        ("CLASS-ID. MyClass INHERITS Base.", "MyClass"),  # was a real bug, now fixed
        ("INTERFACE-ID. MyInterface INHERITS BaseInterface.", "MyInterface"),  # was a real bug, now fixed
    ],
    "invalid": [
        "      * PROGRAM-ID. MyProgram.",  # commented-out declaration
        "       WORKING-STORAGE SECTION.",  # unrelated section, no class_start keyword
    ],
    "pathological": [
        ("PROGRAM-ID.\n    MyProgram.", "MyProgram"),  # vertical split
        ("PROGRAM-ID.\n    MyProgram\n    IS INITIAL PROGRAM.", "MyProgram"),  # vertical split + clause
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_cobol_class_start_valid(payload, expected_name):
    assert_valid_match(COBOL_RULES["class_start"], payload, expected_name, "cobol.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_cobol_class_start_invalid(payload):
    assert_invalid_no_match(COBOL_RULES["class_start"], payload, "cobol.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_cobol_class_start_pathological(payload, expected_name):
    assert_pathological_match(COBOL_RULES["class_start"], payload, expected_name, "cobol.class_start")


def test_cobol_class_start_trailing_clause_regression():
    """
    Regression test for a real bug (epic #813/#854): the lookahead required
    the entity name to be IMMEDIATELY followed by a period/newline/EOS,
    with no allowance for the standard trailing clauses these paragraphs
    actually support -- `PROGRAM-ID. Foo IS INITIAL PROGRAM.`, `PROGRAM-ID.
    Foo IS COMMON PROGRAM.`, `CLASS-ID. Foo FINAL.`, `CLASS-ID. Foo INHERITS
    Base.`, `INTERFACE-ID. Foo INHERITS Base.` -- all real, documented
    Enterprise COBOL syntax -- were entirely invisible. Fixed with a
    bounded (max 6) run of additional clause words between the captured
    name and the terminating period.
    """
    class_start = COBOL_RULES["class_start"]
    for payload, expected in [
        ("PROGRAM-ID. MyProgram IS INITIAL PROGRAM.", "MyProgram"),
        ("PROGRAM-ID. MyProgram IS COMMON PROGRAM.", "MyProgram"),
        ("CLASS-ID. MyClass FINAL.", "MyClass"),
        ("CLASS-ID. MyClass INHERITS Base.", "MyClass"),
        ("INTERFACE-ID. MyInterface INHERITS BaseInterface.", "MyInterface"),
    ]:
        m = class_start.search(payload)
        assert m and m.group(1) == expected, f"trailing-clause form regressed: {payload!r}"


def test_cobol_class_start_trailing_clause_fix_does_not_bleed_into_next_paragraph():
    """
    Regression test for the false-positive vector the trailing-clause fix
    above could have reopened: the bounded word-loop must stop at the real
    statement's own period and never bleed into an unrelated FOLLOWING
    paragraph (e.g. AUTHOR.) that happens to sit on the very next line.
    """
    class_start = COBOL_RULES["class_start"]
    payload = "PROGRAM-ID. MyProgram IS INITIAL PROGRAM.\n       AUTHOR. John Smith."
    m = class_start.search(payload)
    assert m and m.group(1) == "MyProgram", "trailing-clause loop bled into an unrelated following paragraph"
    assert "AUTHOR" not in m.group(0), "match consumed content past its own statement's terminating period"


def test_cobol_class_start_factory_object_division_header_no_false_capture_regression():
    """
    Regression test for a real bug the trailing-clause fix above (directly)
    introduced -- caught by this exact test before shipping, not found
    externally: FACTORY./OBJECT. are standalone structural markers in
    OO-COBOL (never followed by a real name the way PROGRAM-ID/CLASS-ID/
    INTERFACE-ID are), always immediately followed by a division header
    (`FACTORY.\\n    IDENTIFICATION DIVISION.`). Before the trailing-clause
    widening, this was safe by coincidence (the lookahead needed a bare
    period right after the first word, and "IDENTIFICATION DIVISION" has a
    second word in the way). Once the widening allowed up to 6 trailing
    words, "IDENTIFICATION"/"PROCEDURE" got miscaptured as the entity name
    with "DIVISION" swallowed as a trailing clause word. Fixed by excluding
    "DIVISION" from the trailing-clause loop specifically -- no real
    PROGRAM-ID/CLASS-ID/INTERFACE-ID clause ever legitimately contains that
    word.
    """
    class_start = COBOL_RULES["class_start"]
    assert not class_start.search("FACTORY.\n    IDENTIFICATION DIVISION."), (
        "FACTORY marker incorrectly treated IDENTIFICATION as an entity name"
    )
    assert not class_start.search("OBJECT.\n    PROCEDURE DIVISION."), (
        "OBJECT marker incorrectly treated PROCEDURE as an entity name"
    )


def test_cobol_class_start_redos_immunity():
    """ReDoS sweep for the widened bounded trailing-clause loop."""
    class_start = COBOL_RULES["class_start"]
    assert_redos_immune(class_start, "PROGRAM-ID. " + ("WORD " * 200000), timeout_sec=3.0)
    assert class_start.search("PROGRAM-ID. MyProgram.")


# ==============================================================================
# ARGS (args) -- PROCEDURE DIVISION / CALL USING and RETURNING signatures.
# NOTE: test_args_extraction_strict.py had no cobol entry at all -- args had
# zero prior test coverage before this file.
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("PROCEDURE DIVISION USING WS-PARAM1 WS-PARAM2.", "WS-PARAM1"),
        ("PROCEDURE DIVISION RETURNING WS-RESULT.", "WS-RESULT"),
        ("CALL 'SUBPROG' USING BY REFERENCE WS-PARAM1 BY VALUE WS-PARAM2.", "WS-PARAM1"),
        ("PROCEDURE DIVISION USING WS-A, WS-B, WS-C.", "WS-A"),
    ],
    "invalid": [
        "HOUSING-UNIT VALUE 5.",  # substring lookalike: "using" inside "HOUSING", no word boundary
        "CONTINUING-FLAG VALUE 1.",  # unrelated identifier, no USING/RETURNING keyword
    ],
    "pathological": [
        ("PROCEDURE DIVISION USING WS-A RETURNING WS-B.", "WS-A"),  # combined clause -- was a real bug, now fixed
        ("PROCEDURE DIVISION\n    USING WS-A\n    WS-B.", "WS-A"),  # multi-line split
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_cobol_args_valid(payload, expected_name):
    assert_valid_match(COBOL_RULES["args"], payload, expected_name, "cobol.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_cobol_args_invalid(payload):
    assert_invalid_no_match(COBOL_RULES["args"], payload, "cobol.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_cobol_args_pathological(payload, expected_name):
    assert_pathological_match(COBOL_RULES["args"], payload, expected_name, "cobol.args")


def test_cobol_args_using_returning_bleed_regression():
    """
    Regression test for a real bug (epic #813/#854): the parameter-name
    repetition had no exclusion for the literal word "RETURNING" -- so
    `PROCEDURE DIVISION USING WS-A RETURNING WS-B.` (declaring both a
    parameter AND a return value in one division header, extremely common
    real Enterprise COBOL/GnuCOBOL) had USING's own capture bleed straight
    through "RETURNING" and swallow WS-B too, instead of stopping at the
    clause boundary. Fixed with a negative lookahead excluding "RETURNING"
    from the parameter-name alternative -- `finditer` now correctly yields
    two separate matches.
    """
    args = COBOL_RULES["args"]
    matches = list(args.finditer("PROCEDURE DIVISION USING WS-A RETURNING WS-B."))
    assert len(matches) == 2, f"expected 2 separate USING/RETURNING matches, got {len(matches)}"
    assert "WS-A" in matches[0].group(1) and "RETURNING" not in matches[0].group(1), (
        "USING capture bled into the RETURNING clause"
    )
    assert "WS-B" in matches[1].group(1), "RETURNING capture regressed"


def test_cobol_args_redos_immunity():
    """ReDoS sweep for the new negative lookahead."""
    args = COBOL_RULES["args"]
    assert_redos_immune(args, "USING " + ("WORD " * 200000), timeout_sec=3.0)
    assert args.search("USING WS-A.")


# ==============================================================================
# DEPENDENCY (_dependency_capture) -- COPY/INCLUDE copybook statements.
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("COPY MYLIB.", "MYLIB"),  # carried-forward
        ("INCLUDE SQLCA.", "SQLCA"),  # carried-forward
        ("       COPY MYFILE.", "MYFILE"),  # fixed-format
        ('COPY "MYFILE".', "MYFILE"),  # quoted
        ("COPY MYFILE REPLACING ==OLD== BY ==NEW==.", "MYFILE"),  # REPLACING clause
        ("COPY MYFILE OF MYLIB.", "MYFILE"),  # OF library qualifier
        ("COPY MYFILE IN MYLIB.", "MYFILE"),  # IN library qualifier
    ],
    "invalid": [
        "01 COPY-FILE PIC X(10).",  # carried-forward: substring-of-keyword lookalike
        "      * COPY MYFILE.",  # commented-out copy (column-7 asterisk)
    ],
    "pathological": [
        ("COPY \n 'Z_MACROS'", "Z_MACROS"),  # carried-forward: vertical spacing
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_cobol_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(COBOL_RULES["_dependency_capture"], payload, expected_path, "cobol._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_cobol_dependency_capture_invalid(payload):
    assert_invalid_no_match(COBOL_RULES["_dependency_capture"], payload, "cobol._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_cobol_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        COBOL_RULES["_dependency_capture"], payload, expected_path, "cobol._dependency_capture"
    )


def test_cobol_dependency_capture_redos_immunity():
    """ReDoS sweep for the COPY/INCLUDE statement pattern."""
    dep = COBOL_RULES["_dependency_capture"]
    assert_redos_immune(dep, "COPY '" + "a" * 200000, timeout_sec=3.0)
    assert dep.search("COPY MYLIB.")
