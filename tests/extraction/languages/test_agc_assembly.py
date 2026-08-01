"""
AGC Assembly extraction hardening (epic #813, issue #857). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all extraction gauntlets for agc_assembly in one file: func_start,
args, _dependency_capture. (class_start is not applicable to AGC).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

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

AGC_RULES = LANGUAGE_DEFINITIONS["agc_assembly"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("MYLABEL\tTC INTERNAL", "MYLABEL"),
        ("START\tCA SOME_VAR", "START"),
        ("FUNC_NAME_1\tCS VAR", "FUNC_NAME_1"),
        ("FUNC-NAME\tTS VAR", "FUNC-NAME"),
        ("DUMMY\tDXCH VAR", "DUMMY"),
        ("L1\tCCS VAR", "L1"),
        ("L2\tDLOAD VAR", "L2"),
        ("L3\tSTORE VAR", "L3"),
        ("L4\tCALL VAR", "L4"),
        ("L5\tINDEX VAR", "L5"),
        ("L6\tEXTEND", "L6"),
        ("L7\tINHINT", "L7"),
        ("L8\tBZF VAR", "L8"),
        ("L9\tBZMF VAR", "L9"),
        ("L10\tBPL VAR", "L10"),
        ("L11\tBMI VAR", "L11"),
        ("LABEL123\tTC ROUTINE", "LABEL123"),
        ("P66-PROG\tTC ROUTINE", "P66-PROG"),
        ("V82CALL\tCA B", "V82CALL"),
        ("MIN-MAX\tCS B", "MIN-MAX"),
        ("123LABEL\tTC ROUTINE", "123LABEL"),
        ("LABEL_WITH_UNDERSCORE\tTC ROUTINE", "LABEL_WITH_UNDERSCORE"),
        # The following opcodes were missing from the whitelist entirely
        # (real bug, epic #813/#857 -- see the dedicated regression test
        # below): confirmed via the real Apollo 11 corpus in
        # language-crucible that CAF alone (94 occurrences) is one of the
        # single most common AGC instructions, on par with CA/CS/TS.
        ("CAFLABEL\tCAF SOMEVAR", "CAFLABEL"),
        ("TCFLABEL\tTCF ROUTINE", "TCFLABEL"),
        ("XCHLABEL\tXCH SOMEVAR", "XCHLABEL"),
        ("LXCHLABEL\tLXCH SOMEVAR", "LXCHLABEL"),
        ("ADLABEL\tAD SOMEVAR", "ADLABEL"),
        ("MASKLABEL\tMASK SOMEVAR", "MASKLABEL"),
        ("INCRLABEL\tINCR A", "INCRLABEL"),
        ("RELINTLABEL\tRELINT", "RELINTLABEL"),
    ],
    "invalid": [
        " MYLABEL\tTC INTERNAL",  # Not at true line start
        "\tMYLABEL\tTC INTERNAL",  # Not at true line start
        "MYLABEL\n\tTC INTERNAL",  # Newline between label and opcode
        "MYLABEL: TC INTERNAL",  # Colon not allowed in label
        "MYLABEL\tADD INTERNAL",  # ADD is not a real AGC opcode (AD is; ADD is not)
        "# MYLABEL\tTC INTERNAL",  # Comment
        "MYLABEL\t",  # No opcode
        "MYLABEL",  # Just the label
        "MYLABEL\tFOO INTERNAL",  # FOO is not an opcode
        "TC MYLABEL",  # TC is the opcode, no label
        "CA MYLABEL",  # CA is the opcode, no label
        "   TC MYLABEL",  # Indented opcode
        "MYLABEL\tOCT 12345",  # OCT is a data/constant pseudo-op, not a subroutine entry
        "MYLABEL\tEQUALS",  # EQUALS is a constant declaration (handled by the `api` rule instead)
        "MYLABEL\tDEC 5",  # DEC is a data/constant pseudo-op
        "MYLABEL\tADRES SOMEWHERE",  # ADRES is an address-constant pseudo-op
    ],
    "pathological": [
        ("LONG-LABEL-NAME-123\t\t\t\tTC INTERNAL", "LONG-LABEL-NAME-123"),
        ("A\tTC  B", "A"),
        ("A123-B_C\t   TC  \t  INTERNAL", "A123-B_C"),
        ("LABEL123 \t TC ", "LABEL123"),
        ("MY_LABEL\t\t\tCA\t\tA", "MY_LABEL"),
        ("X-Y-Z\t  CS  \t B", "X-Y-Z"),
        ("L123456789\t DXCH \t Q", "L123456789"),
        ("COMPLEX-LABEL_123\t  CCS \t Z", "COMPLEX-LABEL_123"),
        ("SHORT\t DLOAD \t M", "SHORT"),
        ("L\t STORE \t N", "L"),
        ("MY-LABEL\t CALL \t P", "MY-LABEL"),
        ("XYZ\t INDEX \t A", "XYZ"),
        ("A-B\t EXTEND", "A-B"),
        ("C_D\t INHINT", "C_D"),
        ("E1\t BZF \t L", "E1"),
        ("F2\t BZMF \t L", "F2"),
        ("G3\t BPL \t L", "G3"),
        ("H4\t BMI \t L", "H4"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_agc_assembly_func_start_valid(payload, expected_name):
    assert_valid_match(AGC_RULES["func_start"], payload, expected_name, "agc_assembly.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_agc_assembly_func_start_invalid(payload):
    assert_invalid_no_match(AGC_RULES["func_start"], payload, "agc_assembly.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_agc_assembly_func_start_pathological(payload, expected_name):
    assert_pathological_match(AGC_RULES["func_start"], payload, expected_name, "agc_assembly.func_start")


def test_agc_assembly_func_start_redos_immunity():
    assert_redos_immune(AGC_RULES["func_start"], "A" * 100000 + "\tTC", timeout_sec=1.0)


def test_agc_assembly_func_start_opcode_whitelist_regression():
    """
    Regression test for a real bug (epic #813/#857): the opcode whitelist
    was a small, ad hoc subset of the real AGC instruction set -- missing
    instructions this SAME file's own sibling rules already recognize as
    legitimate (`args`'s CA|CS|TS|AD|SU|MULT|DV|MASK|DXCH|LXCH|QXCH|XCH|
    INDEX, `branch`'s TCF|BZE|BMN|RESUME|RETURN|TCR|GOTO|OVSK|BVBZ,
    `safety`'s RELINT|EDRUPT, `state_mutation`'s INCR|AUG|DIM|DAS), so a
    label followed by ANY of these real, common opcodes was invisible as a
    subroutine entry.

    Confirmed empirically against the real Apollo 11 (Luminary/Comanche)
    source corpus in language-crucible: the old pattern matched 609
    label+opcode pairs across the corpus; the new pattern matches 812
    (+33%), with zero new false positives against data/constant pseudo-ops
    (verified via the `MYLABEL\tOCT 12345`-style invalid cases above --
    OCT/OCTAL/DEC/2DEC/ADRES/CADR/EQUALS all correctly stay excluded, since
    those mark data declarations, not subroutine entries). `CAF` alone
    (Clear and Add Fixed) is one of the single most common AGC instructions
    in the real corpus (94 occurrences, on par with CA/CS/TS) and was
    entirely missing before this fix.
    """
    func_start = AGC_RULES["func_start"]
    for opcode, operand in [
        ("CAF", "SOMEVAR"),
        ("TCF", "ROUTINE"),
        ("XCH", "SOMEVAR"),
        ("LXCH", "SOMEVAR"),
        ("QXCH", "SOMEVAR"),
        ("AD", "SOMEVAR"),
        ("ADS", "SOMEVAR"),
        ("SU", "SOMEVAR"),
        ("MULT", "SOMEVAR"),
        ("DV", "SOMEVAR"),
        ("MASK", "SOMEVAR"),
        ("INCR", "A"),
        ("AUG", "A"),
        ("DIM", "A"),
        ("DAS", "SOMEVAR"),
        ("RELINT", ""),
        ("EDRUPT", ""),
        ("BZE", "ROUTINE"),
        ("BMN", "ROUTINE"),
        ("RESUME", ""),
        ("RETURN", ""),
        ("TCR", "ROUTINE"),
        ("GOTO", "ROUTINE"),
        ("RVQ", ""),
    ]:
        payload = f"MYLABEL\t{opcode} {operand}".rstrip()
        m = func_start.search(payload)
        assert m and m.group(1) == "MYLABEL", f"opcode {opcode!r} still missing from func_start whitelist"

    # Data/constant pseudo-ops must stay excluded -- these mark data
    # declarations, not subroutine entries, and were never part of the gap.
    for pseudo_op, operand in [("OCT", "12345"), ("OCTAL", "12345"), ("DEC", "5"), ("2DEC", "5"), ("ADRES", "X")]:
        payload = f"MYLABEL\t{pseudo_op} {operand}"
        assert not func_start.search(payload), f"data pseudo-op {pseudo_op!r} incorrectly treated as a subroutine entry"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("EBANK=", "EBANK="),
        ("FBANK=", "FBANK="),
        ("BBANK=", "BBANK="),
        ("CA A", "CA A"),
        ("CS Q", "CS Q"),
        ("TS L", "TS L"),
        ("AD Z", "AD Z"),
        ("SU A", "SU A"),
        ("MULT Q", "MULT Q"),
        ("DV L", "DV L"),
        ("MASK Z", "MASK Z"),
        ("DXCH A", "DXCH A"),
        ("LXCH Q", "LXCH Q"),
        ("QXCH L", "QXCH L"),
        ("XCH Z", "XCH Z"),
        ("INDEX A", "INDEX A"),
        ("CA\tA", "CA\tA"),
        ("INDEX\tZ", "INDEX\tZ"),
        ("AD\tQ", "AD\tQ"),
        ("SU\tL", "SU\tL"),
        # AUG/DIM/INCR were missing entirely (real bug, epic #813/#857 --
        # see the dedicated regression test below), despite being real
        # register-mutating instructions this file's own `state_mutation`
        # rule already recognizes.
        ("AUG A", "AUG A"),
        ("DIM Q", "DIM Q"),
        ("INCR A", "INCR A"),
    ],
    "invalid": [
        "CA B",  # B is not a hardware register in the rule (A, Q, L, Z)
        "AD X",  # X is not a hardware register
        "EBANK",  # No =
        "TS  ",  # No register
        "INDEXA",  # No space
        "CAA",  # No space
        "CSB",  # No space
        "TSZ",  # No space
        "TC A",  # TC is not in the opcode list for args
        "DLOAD A",  # DLOAD not in the list
        "EBANK-",  # Not =
        "FBANK = ",  # Space not allowed in rule
        "BBANK  = ",  # Space not allowed
        "CA  123",  # Not a register
    ],
    "pathological": [
        ("\t\tEBANK=\t\t", "EBANK="),
        ("CA\t  \t A", "CA\t  \t A"),
        ("  CS \t\t Q  ", "CS \t\t Q"),
        ("\tTS\tL\t", "TS\tL"),
        (" \t AD \t Z \t ", "AD \t Z"),
        ("SU\t\t\t\tA", "SU\t\t\t\tA"),
        ("\t\tMULT\t \tQ", "MULT\t \tQ"),
        ("DV \t\t\t L", "DV \t\t\t L"),
        ("\t MASK \t Z \t", "MASK \t Z"),
        ("DXCH\t\t\tA", "DXCH\t\t\tA"),
        ("LXCH \t\t Q", "LXCH \t\t Q"),
        ("QXCH\t \t L", "QXCH\t \t L"),
        ("XCH \t \tZ", "XCH \t \tZ"),
        ("INDEX\t\t \tA", "INDEX\t\t \tA"),
        ("FBANK=", "FBANK="),
        ("BBANK=", "BBANK="),
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_agc_assembly_args_valid(payload, expected_name):
    assert_valid_match(AGC_RULES["args"], payload, expected_name, "agc_assembly.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_agc_assembly_args_invalid(payload):
    assert_invalid_no_match(AGC_RULES["args"], payload, "agc_assembly.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_agc_assembly_args_pathological(payload, expected_name):
    assert_pathological_match(AGC_RULES["args"], payload, expected_name, "agc_assembly.args")


def test_agc_assembly_args_redos_immunity():
    assert_redos_immune(AGC_RULES["args"], "CA" + " \t" * 50000 + "A", timeout_sec=1.0)


def test_agc_assembly_args_register_opcode_whitelist_regression():
    """
    Regression test for a real bug (epic #813/#857): AUG/DIM/INCR (real
    register-mutating instructions this file's own `state_mutation` rule
    already recognizes) were missing from the opcode list, so `AUG A`/
    `DIM Q`/`INCR A` -- real, common coupling of a hardware register to an
    instruction -- were invisible.
    """
    args = AGC_RULES["args"]
    for opcode, register in [("AUG", "A"), ("DIM", "Q"), ("INCR", "A")]:
        payload = f"{opcode} {register}"
        m = args.search(payload)
        assert m and m.group(0) == payload, f"opcode {opcode!r} coupled to a register still missing from args"


# ==============================================================================
# DEPENDENCY CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("BANK 43", "43"),
        ("SETLOC 43", "43"),
        ("EBANK= 43", "43"),
        ("BANK\t43", "43"),
        ("SETLOC\t43", "43"),
        ("EBANK=43", "43"),
        (" BANK\nMYBANK", "MYBANK"),
        ("\tSETLOC\n\tMYLOC", "MYLOC"),
        ("EBANK=MYBANK", "MYBANK"),
        ("BANK MY_BANK", "MY_BANK"),
        ("SETLOC MY_LOC", "MY_LOC"),
        ("EBANK= MY_EBANK", "MY_EBANK"),
    ],
    "invalid": [
        "BANK43",  # No space after BANK
        "SETLOC",  # No operand
        "TC BANK",  # TC before BANK, rule requires ^[ \t]*
        " EBANK",  # No =
        "BANK-43",  # No space, dash not allowed in operand
        "BANK",  # No operand
        "EBANK=",  # No operand
        "SETLOC_43",  # No space
        "MYBANK BANK",  # BANK not at start of line
        "BANK \n \n",  # No operand
        "BANK # comment",  # Hash not allowed in operand
    ],
    "pathological": [
        ("\t \t BANK \n\n \t MYBANK123", "MYBANK123"),
        ("\tSETLOC\t\t\t\n  \t MYLOC123", "MYLOC123"),
        ("   EBANK=\t\n\t \n MY_EBANK", "MY_EBANK"),
        ("BANK\n\n\n\n\n\n\nMYBANK", "MYBANK"),
        ("\t\t\t\tBANK\t\t\t\tMYBANK", "MYBANK"),
        ("    SETLOC    \t\t\n\nMYLOC", "MYLOC"),
        ("\t \tEBANK=\t \t \n\nMY_EBANK", "MY_EBANK"),
        ("BANK\t\n\t\n\t\nMYBANK", "MYBANK"),
        ("SETLOC\n\n\t\n\tMYLOC", "MYLOC"),
        ("EBANK=\n\n\nMYEBANK", "MYEBANK"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_CASES["valid"])
def test_agc_assembly_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(AGC_RULES["_dependency_capture"], payload, expected_name, "agc_assembly.dependency")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_agc_assembly_dependency_invalid(payload):
    assert_invalid_no_match(AGC_RULES["_dependency_capture"], payload, "agc_assembly.dependency")


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_CASES["pathological"])
def test_agc_assembly_dependency_pathological(payload, expected_name):
    assert_pathological_dependency_match(
        AGC_RULES["_dependency_capture"], payload, expected_name, "agc_assembly.dependency"
    )


def test_agc_assembly_dependency_redos_immunity():
    assert_redos_immune(
        AGC_RULES["_dependency_capture"], " \t" * 50000 + "BANK" + " \t\n" * 50000 + "A", timeout_sec=1.0
    )
