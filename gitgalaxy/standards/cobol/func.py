# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL Intrinsic Functions rule family as declarative data (#4712, epic #4710).

Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
Chapter "Intrinsic functions":
  - String manipulation functions: UPPER-CASE, LOWER-CASE, REVERSE, TRIM
  - Mathematical & numeric functions: MOD, REM, INTEGER, INTEGER-PART, ABS, MIN, MAX, RANDOM
  - Conversion and validation functions: NUMVAL, NUMVAL-C, TEST-NUMVAL, TEST-NUMVAL-C
  - Date and time functions: CURRENT-DATE, INTEGER-OF-DATE, DATE-OF-INTEGER
  - ACCEPT statement system interfaces: ACCEPT FROM DATE/TIME, ACCEPT FROM SYSIN

Defines:
  FUNC_CATEGORIES    The 5 functional groupings of intrinsic routines
  FUNC_SPECS         Specification records for all supported intrinsic functions
  FUNC_RULES         Catalogue rule metadata for the 12 FUNC rules
  FUNC_VECTORS       Deterministic test vectors executed directly in CI
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_FLOOR, Decimal
from typing import Any

# -------------------------------------------------------------------------------------- categories

CATEGORY_STRING = 0
CATEGORY_MATH = 1
CATEGORY_PARSING = 2
CATEGORY_DATE_TIME = 3
CATEGORY_IO = 4

FUNC_CATEGORIES: dict[int, str] = {
    CATEGORY_STRING: "STRING",
    CATEGORY_MATH: "MATH",
    CATEGORY_PARSING: "PARSING",
    CATEGORY_DATE_TIME: "DATE_TIME",
    CATEGORY_IO: "IO",
}

CATEGORY_BY_NAME = {v: k for k, v in FUNC_CATEGORIES.items()}


# -------------------------------------------------------------------------------------- function specifications


@dataclass(frozen=True)
class FuncSpecRecord:
    name: str
    rule_id: str
    category: str
    return_type: str  # ALPHANUMERIC / NUMERIC / INTEGER
    ibm_section: str
    description: str


FUNC_SPECS: dict[str, FuncSpecRecord] = {
    "UPPER-CASE": FuncSpecRecord(
        name="UPPER-CASE",
        rule_id="RT-FUNC-CASE",
        category="STRING",
        return_type="ALPHANUMERIC",
        ibm_section="UPPER-CASE function",
        description="Converts single-byte lowercase letters to uppercase.",
    ),
    "LOWER-CASE": FuncSpecRecord(
        name="LOWER-CASE",
        rule_id="RT-FUNC-CASE",
        category="STRING",
        return_type="ALPHANUMERIC",
        ibm_section="LOWER-CASE function",
        description="Converts single-byte uppercase letters to lowercase.",
    ),
    "REVERSE": FuncSpecRecord(
        name="REVERSE",
        rule_id="RT-FUNC-REVERSE",
        category="STRING",
        return_type="ALPHANUMERIC",
        ibm_section="REVERSE function",
        description="Reverses the character sequence of the argument.",
    ),
    "TRIM": FuncSpecRecord(
        name="TRIM",
        rule_id="RT-FUNC-TRIM",
        category="STRING",
        return_type="ALPHANUMERIC",
        ibm_section="TRIM function",
        description="Removes leading and/or trailing spaces only (low-values stay); all-spaces gives zero length.",
    ),
    "MOD": FuncSpecRecord(
        name="MOD",
        rule_id="RT-FUNC-MOD-REM",
        category="MATH",
        return_type="NUMERIC",
        ibm_section="MOD function",
        description="Modulus: a - b * FLOOR(a / b); zero divisor yields 0 with no size error.",
    ),
    "REM": FuncSpecRecord(
        name="REM",
        rule_id="RT-FUNC-MOD-REM",
        category="MATH",
        return_type="NUMERIC",
        ibm_section="REM function",
        description="Remainder: a - b * INTEGER-PART(a / b); zero divisor yields 0 with no size error.",
    ),
    "INTEGER": FuncSpecRecord(
        name="INTEGER",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        category="MATH",
        return_type="INTEGER",
        ibm_section="INTEGER function",
        description="Greatest integer less than or equal to argument (floor).",
    ),
    "INTEGER-PART": FuncSpecRecord(
        name="INTEGER-PART",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        category="MATH",
        return_type="INTEGER",
        ibm_section="INTEGER-PART function",
        description="Integer portion of argument (truncation toward zero).",
    ),
    "ABS": FuncSpecRecord(
        name="ABS",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        category="MATH",
        return_type="NUMERIC",
        ibm_section="ABS function",
        description="Absolute value of argument.",
    ),
    "MIN": FuncSpecRecord(
        name="MIN",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        category="MATH",
        return_type="NUMERIC",
        ibm_section="MIN function",
        description="Minimum value among provided arguments.",
    ),
    "MAX": FuncSpecRecord(
        name="MAX",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        category="MATH",
        return_type="NUMERIC",
        ibm_section="MAX function",
        description="Maximum value among provided arguments.",
    ),
    "NUMVAL": FuncSpecRecord(
        name="NUMVAL",
        rule_id="RT-FUNC-NUMVAL",
        category="PARSING",
        return_type="NUMERIC",
        ibm_section="NUMVAL function",
        description="Parses numeric value from string (spaces, + - CR DB sign, decimal point).",
    ),
    "NUMVAL-C": FuncSpecRecord(
        name="NUMVAL-C",
        rule_id="RT-FUNC-NUMVAL",
        category="PARSING",
        return_type="NUMERIC",
        ibm_section="NUMVAL-C function",
        description="Parses monetary value from string with optional currency sign ($) and commas.",
    ),
    "TEST-NUMVAL": FuncSpecRecord(
        name="TEST-NUMVAL",
        rule_id="RT-FUNC-TEST-NUMVAL",
        category="PARSING",
        return_type="INTEGER",
        ibm_section="TEST-NUMVAL function",
        description="Returns 0 if valid for NUMVAL, else 1-based position of first invalid character.",
    ),
    "TEST-NUMVAL-C": FuncSpecRecord(
        name="TEST-NUMVAL-C",
        rule_id="RT-FUNC-TEST-NUMVAL",
        category="PARSING",
        return_type="INTEGER",
        ibm_section="TEST-NUMVAL-C function",
        description="Returns 0 if valid for NUMVAL-C, else 1-based position of first invalid character.",
    ),
    "CURRENT-DATE": FuncSpecRecord(
        name="CURRENT-DATE",
        rule_id="RT-FUNC-CURRENT-DATE",
        category="DATE_TIME",
        return_type="ALPHANUMERIC",
        ibm_section="CURRENT-DATE function",
        description="Returns 21-character timestamp YYYYMMDDHHMMSShh+0000.",
    ),
    "RANDOM": FuncSpecRecord(
        name="RANDOM",
        rule_id="RT-FUNC-RANDOM",
        category="MATH",
        return_type="NUMERIC",
        ibm_section="RANDOM function",
        description="Generates pseudo-random float sequence; initial call or explicit seed parameter.",
    ),
    "INTEGER-OF-DATE": FuncSpecRecord(
        name="INTEGER-OF-DATE",
        rule_id="RT-FUNC-DATE-INTEGER",
        category="DATE_TIME",
        return_type="INTEGER",
        ibm_section="INTEGER-OF-DATE function",
        description="Converts YYYYMMDD to days count (day 1 is 1601-01-01 ANSI or 1582-10-15 LILIAN).",
    ),
    "DATE-OF-INTEGER": FuncSpecRecord(
        name="DATE-OF-INTEGER",
        rule_id="RT-FUNC-DATE-INTEGER",
        category="DATE_TIME",
        return_type="INTEGER",
        ibm_section="DATE-OF-INTEGER function",
        description="Converts day count back to YYYYMMDD.",
    ),
    "ACCEPT-DATE": FuncSpecRecord(
        name="ACCEPT-DATE",
        rule_id="RT-FUNC-ACCEPT-DATE",
        category="DATE_TIME",
        return_type="NUMERIC",
        ibm_section="ACCEPT statement",
        description="Moves system clock fields (DATE, DATE YYYYMMDD, DAY, DAY YYYYDDD, TIME) to target.",
    ),
    "ACCEPT-SYSIN": FuncSpecRecord(
        name="ACCEPT-SYSIN",
        rule_id="RT-FUNC-ACCEPT-SYSIN",
        category="IO",
        return_type="ALPHANUMERIC",
        ibm_section="ACCEPT statement",
        description="Reads next record from SYSIN standard input stream with space padding / truncation.",
    ),
}


# -------------------------------------------------------------------------------------- rule catalogue metadata


@dataclass(frozen=True)
class FuncRuleMeta:
    id: str
    title: str
    status: str  # MATCHED / DIFFERS / REFUSED / ASSUMED
    ibm: dict[str, str] | None
    ibm_note: str | None = None
    options: list[str] = field(default_factory=list)
    register: list[str] = field(default_factory=list)
    description: str = ""


FUNC_RULES: dict[str, FuncRuleMeta] = {
    "RT-FUNC-CASE": FuncRuleMeta(
        id="RT-FUNC-CASE",
        title="FUNCTION UPPER-CASE / LOWER-CASE of single-byte letters",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "UPPER-CASE and LOWER-CASE functions"},
        description="Converts character case for single-byte standard character sets.",
    ),
    "RT-FUNC-REVERSE": FuncRuleMeta(
        id="RT-FUNC-REVERSE",
        title="FUNCTION REVERSE",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "REVERSE function"},
        description="Reverses order of characters in argument.",
    ),
    "RT-FUNC-TRIM": FuncRuleMeta(
        id="RT-FUNC-TRIM",
        title="FUNCTION TRIM [LEADING / TRAILING]: spaces only removed (low-values stay); an all-space argument gives a zero-length result, as the oracle",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "TRIM function"},
        description="Strips space characters from start, end, or both; non-space controls preserved.",
    ),
    "RT-FUNC-MOD-REM": FuncRuleMeta(
        id="RT-FUNC-MOD-REM",
        title="FUNCTION MOD (a - b * FLOOR(a / b)) and REM (a - b * INTEGER-PART(a / b)); a zero b gives 0 with no size error, as the oracle",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "MOD and REM functions"},
        description="MOD uses floor division; REM uses truncation toward zero; zero divisor returns 0.",
    ),
    "RT-FUNC-INTEGER-ABS-MIN-MAX": FuncRuleMeta(
        id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        title="FUNCTION INTEGER (floor), INTEGER-PART (toward zero), ABS, MIN, MAX",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Mathematical intrinsic functions"},
        description="Basic arithmetic intrinsic functions evaluated algebraically.",
    ),
    "RT-FUNC-NUMVAL": FuncRuleMeta(
        id="RT-FUNC-NUMVAL",
        title="FUNCTION NUMVAL / NUMVAL-C: the number in a text (spaces, one sign + - CR DB, a decimal point; NUMVAL-C a currency sign and commas)",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "NUMVAL and NUMVAL-C functions"},
        description="Extracts numeric quantities from formatted character strings.",
    ),
    "RT-FUNC-TEST-NUMVAL": FuncRuleMeta(
        id="RT-FUNC-TEST-NUMVAL",
        title="FUNCTION TEST-NUMVAL / TEST-NUMVAL-C: 0 when valid, else the position of the first character that makes it invalid (the length + 1 when it ends early), as the oracle",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "TEST-NUMVAL and TEST-NUMVAL-C functions"},
        description="Validates numeric string syntax returning error character position or zero.",
    ),
    "RT-FUNC-CURRENT-DATE": FuncRuleMeta(
        id="RT-FUNC-CURRENT-DATE",
        title="FUNCTION CURRENT-DATE where the project has no clock bean: YYYYMMDDHHMMSShh and the UTC offset of the run's clock",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "CURRENT-DATE function"},
        description="Returns ISO-aligned current date and time with UTC offset representation.",
    ),
    "RT-FUNC-RANDOM": FuncRuleMeta(
        id="RT-FUNC-RANDOM",
        title="FUNCTION RANDOM: one run unit's sequence (glibc random_r TYPE_3, as the oracle); the numbers differ from z/OS's, the interface as IBM documents it",
        status="DIFFERS",
        ibm={"doc": "cobol-lr", "section": "RANDOM function"},
        ibm_note="Interface matches IBM; pseudo-random generator sequence follows oracle glibc random_r",
        register=["C12"],
        description="Pseudo-random numbers generated deterministically according to oracle assumptions.",
    ),
    "RT-FUNC-DATE-INTEGER": FuncRuleMeta(
        id="RT-FUNC-DATE-INTEGER",
        title="FUNCTION INTEGER-OF-DATE / DATE-OF-INTEGER: day 1 is 1 January 1601 (INTDATE(ANSI)) or 15 October 1582 (INTDATE(LILIAN))",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Date intrinsic functions"},
        options=["INTDATE"],
        description="Gregorian calendar day numbering under ANSI or Lilian day-zero configurations.",
    ),
    "RT-FUNC-ACCEPT-DATE": FuncRuleMeta(
        id="RT-FUNC-ACCEPT-DATE",
        title="ACCEPT FROM DATE / DATE YYYYMMDD / DAY / DAY YYYYDDD / TIME: the run's clock as the unsigned integer item IBM describes, moved as that item",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "ACCEPT statement: DATE/DAY/TIME"},
        description="System clock interrogation format options returned as zoned integer items.",
    ),
    "RT-FUNC-ACCEPT-SYSIN": FuncRuleMeta(
        id="RT-FUNC-ACCEPT-SYSIN",
        title="ACCEPT identifier FROM SYSIN: the next line of standard input moved to the target as an alphanumeric MOVE; no record left stops the run by name",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "ACCEPT statement: SYSIN"},
        description="Sequential standard input record retrieval with EOF refusal.",
    ),
}


# -------------------------------------------------------------------------------------- test vectors


@dataclass(frozen=True)
class FuncVector:
    id: str
    title: str
    rule_id: str
    function: str
    args: list[Any]
    expected_result: Any
    note: str = ""


FUNC_VECTORS: list[FuncVector] = [
    FuncVector(
        id="FN01-upper-case",
        title="UPPER-CASE converts letters to uppercase",
        rule_id="RT-FUNC-CASE",
        function="UPPER-CASE",
        args=["hello world 123!"],
        expected_result="HELLO WORLD 123!",
        note="Letters converted to uppercase; numbers and symbols unaffected",
    ),
    FuncVector(
        id="FN02-lower-case",
        title="LOWER-CASE converts letters to lowercase",
        rule_id="RT-FUNC-CASE",
        function="LOWER-CASE",
        args=["HELLO WORLD 123!"],
        expected_result="hello world 123!",
        note="Letters converted to lowercase; numbers and symbols unaffected",
    ),
    FuncVector(
        id="FN03-reverse",
        title="REVERSE reverses character order",
        rule_id="RT-FUNC-REVERSE",
        function="REVERSE",
        args=["ABCDE"],
        expected_result="EDCBA",
        note="Reverses character string",
    ),
    FuncVector(
        id="FN04-trim-both",
        title="TRIM strips leading and trailing spaces",
        rule_id="RT-FUNC-TRIM",
        function="TRIM",
        args=["  HELLO WORLD  "],
        expected_result="HELLO WORLD",
        note="Removes both leading and trailing spaces",
    ),
    FuncVector(
        id="FN05-trim-leading",
        title="TRIM LEADING strips only prefix spaces",
        rule_id="RT-FUNC-TRIM",
        function="TRIM_LEADING",
        args=["   TEST   "],
        expected_result="TEST   ",
        note="Leaves trailing spaces intact",
    ),
    FuncVector(
        id="FN06-trim-trailing",
        title="TRIM TRAILING strips only suffix spaces",
        rule_id="RT-FUNC-TRIM",
        function="TRIM_TRAILING",
        args=["   TEST   "],
        expected_result="   TEST",
        note="Leaves leading spaces intact",
    ),
    FuncVector(
        id="FN07-trim-all-spaces",
        title="TRIM of all-space argument returns zero-length string",
        rule_id="RT-FUNC-TRIM",
        function="TRIM",
        args=["     "],
        expected_result="",
        note="Returns empty string",
    ),
    FuncVector(
        id="FN08-mod-floor",
        title="MOD computes modulus using floor division",
        rule_id="RT-FUNC-MOD-REM",
        function="MOD",
        args=["10", "3"],
        expected_result="1",
        note="10 - 3 * floor(10/3) = 10 - 9 = 1",
    ),
    FuncVector(
        id="FN09-mod-negative",
        title="MOD of negative dividend",
        rule_id="RT-FUNC-MOD-REM",
        function="MOD",
        args=["-10", "3"],
        expected_result="2",
        note="-10 - 3 * floor(-10/3) = -10 - 3 * (-4) = 2",
    ),
    FuncVector(
        id="FN10-mod-zero-divisor",
        title="MOD with zero divisor returns 0 without size error",
        rule_id="RT-FUNC-MOD-REM",
        function="MOD",
        args=["10", "0"],
        expected_result="0",
        note="Zero divisor in MOD returns 0",
    ),
    FuncVector(
        id="FN11-rem-down",
        title="REM computes remainder using truncation toward zero",
        rule_id="RT-FUNC-MOD-REM",
        function="REM",
        args=["-10", "3"],
        expected_result="-1",
        note="-10 - 3 * trunc(-10/3) = -10 - 3 * (-3) = -1",
    ),
    FuncVector(
        id="FN12-integer-floor",
        title="INTEGER rounds down to floor",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        function="INTEGER",
        args=["-1.5"],
        expected_result="-2",
        note="Floor of -1.5 is -2",
    ),
    FuncVector(
        id="FN13-integer-part-trunc",
        title="INTEGER-PART truncates toward zero",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        function="INTEGER-PART",
        args=["-1.5"],
        expected_result="-1",
        note="Truncation of -1.5 is -1",
    ),
    FuncVector(
        id="FN14-abs-negative",
        title="ABS returns absolute value",
        rule_id="RT-FUNC-INTEGER-ABS-MIN-MAX",
        function="ABS",
        args=["-42.5"],
        expected_result="42.5",
        note="|-42.5| = 42.5",
    ),
    FuncVector(
        id="FN15-numval-trailing-minus",
        title="NUMVAL parses number with trailing minus sign",
        rule_id="RT-FUNC-NUMVAL",
        function="NUMVAL",
        args=[" 123.45- "],
        expected_result="-123.45",
        note="Trailing minus sign negates value",
    ),
    FuncVector(
        id="FN16-numval-trailing-cr",
        title="NUMVAL parses number with CR credit notation",
        rule_id="RT-FUNC-NUMVAL",
        function="NUMVAL",
        args=[" 987.65CR "],
        expected_result="-987.65",
        note="CR suffix marks negative amount",
    ),
    FuncVector(
        id="FN17-numval-c-currency-comma",
        title="NUMVAL-C parses monetary amount with dollar sign and commas",
        rule_id="RT-FUNC-NUMVAL",
        function="NUMVAL-C",
        args=[" $1,234,567.89 "],
        expected_result="1234567.89",
        note="Dollar sign and thousand commas stripped",
    ),
    FuncVector(
        id="FN18-test-numval-valid",
        title="TEST-NUMVAL returns 0 for valid numeric string",
        rule_id="RT-FUNC-TEST-NUMVAL",
        function="TEST-NUMVAL",
        args=["123.45"],
        expected_result=0,
        note="Valid number returns 0",
    ),
    FuncVector(
        id="FN19-test-numval-invalid-char",
        title="TEST-NUMVAL returns 1-based index of invalid character",
        rule_id="RT-FUNC-TEST-NUMVAL",
        function="TEST-NUMVAL",
        args=["123.X5"],
        expected_result=5,
        note="'X' at position 5 is invalid",
    ),
    FuncVector(
        id="FN20-date-integer-ansi",
        title="INTEGER-OF-DATE converts 1601-01-01 to day 1 under ANSI",
        rule_id="RT-FUNC-DATE-INTEGER",
        function="INTEGER-OF-DATE",
        args=[16010101],
        expected_result=1,
        note="1601-01-01 is Day 1 under INTDATE(ANSI)",
    ),
    FuncVector(
        id="FN21-date-of-integer-ansi",
        title="DATE-OF-INTEGER converts day 1 back to 16010101 under ANSI",
        rule_id="RT-FUNC-DATE-INTEGER",
        function="DATE-OF-INTEGER",
        args=[1],
        expected_result=16010101,
        note="Day 1 maps back to 16010101",
    ),
]


# -------------------------------------------------------------------------------------- evaluation helpers


def evaluate_mod(a: Decimal, b: Decimal) -> Decimal:
    """MOD: a - b * FLOOR(a / b); 0 if b is zero."""
    if b == Decimal(0):
        return Decimal(0)
    q = (a / b).to_integral_value(rounding=ROUND_FLOOR)
    return a - (b * q)


def evaluate_rem(a: Decimal, b: Decimal) -> Decimal:
    """REM: a - b * TRUNC(a / b); 0 if b is zero."""
    if b == Decimal(0):
        return Decimal(0)
    q = (a / b).to_integral_value(rounding=ROUND_DOWN)
    return a - (b * q)


def evaluate_numval(s: str) -> Decimal:
    """Parse COBOL NUMVAL text."""
    t = s.strip().upper()
    neg = False
    if t.endswith("CR") or t.endswith("DB"):
        neg = True
        t = t[:-2].strip()
    if t.startswith("-") or t.endswith("-"):
        neg = True
        t = t.replace("-", "").strip()
    t = t.replace("+", "").strip()
    if not t or t == ".":
        return Decimal(0)
    v = Decimal(t)
    return -v if neg else v


def evaluate_numval_c(s: str) -> Decimal:
    """Parse COBOL NUMVAL-C text."""
    clean = s.replace("$", "").replace(",", "")
    return evaluate_numval(clean)


ANSI_DAY_ZERO = datetime.date(1600, 12, 31)


def evaluate_integer_of_date_ansi(yyyymmdd: int) -> int:
    """Days since 1600-12-31."""
    y = yyyymmdd // 10000
    m = (yyyymmdd // 100) % 100
    d = yyyymmdd % 100
    dt = datetime.date(y, m, d)
    return (dt - ANSI_DAY_ZERO).days


def evaluate_date_of_integer_ansi(days: int) -> int:
    """Date from days since 1600-12-31."""
    dt = ANSI_DAY_ZERO + datetime.timedelta(days=days)
    return dt.year * 10000 + dt.month * 100 + dt.day
