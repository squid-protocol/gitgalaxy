# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL Arithmetic, Rounding, Intermediate Precision, and Size Error rule family (#4712, epic #4710).

Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
Chapters:
  - "Arithmetic statements" (ADD, SUBTRACT, MULTIPLY, DIVIDE, COMPUTE)
  - "Common phrases and concepts for arithmetic statements":
    - "ROUNDED phrase" (including ROUNDED MODE IS ...)
    - "ON SIZE ERROR and NOT ON SIZE ERROR phrases"
    - "Intermediate results in arithmetic statements"
    - "DIVIDE statement" (including REMAINDER phrase)
    - "COMPUTE statement" (arithmetic expressions and exponentiation `**`)

Defines:
  ROUNDING_MODES         The 7 rounding modes supported by standard / IBM COBOL
  SIZE_ERROR_CONDITIONS  Trigger conditions and receiver invariants under ON SIZE ERROR
  ARITH_RULES            Catalogue rule metadata for 10 arithmetic & store rules
  ARITH_VECTORS          Deterministic test vectors executed directly in CI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Decimal,
)

# -------------------------------------------------------------------------------------- rounding modes

ROUND_TRUNCATION = 0
ROUND_NEAREST_AWAY_FROM_ZERO = 1
ROUND_NEAREST_EVEN = 2
ROUND_NEAREST_TOWARD_ZERO = 3
ROUND_TOWARD_GREATER = 4
ROUND_TOWARD_LESSER = 5
ROUND_PROHIBITED = 6

NAN_SCALE = -32768


@dataclass(frozen=True)
class RoundingModeSpec:
    mode_id: int
    name: str
    java_mode: str
    python_mode: str | None
    description: str
    ibm_clause: str


ROUNDING_MODES: dict[int, RoundingModeSpec] = {
    ROUND_TRUNCATION: RoundingModeSpec(
        mode_id=ROUND_TRUNCATION,
        name="TRUNCATION",
        java_mode="DOWN",
        python_mode=ROUND_DOWN,
        description="Truncation toward zero; excess fractional digits are dropped.",
        ibm_clause="ROUNDED MODE IS TRUNCATION (or omitted ROUNDED phrase)",
    ),
    ROUND_NEAREST_AWAY_FROM_ZERO: RoundingModeSpec(
        mode_id=ROUND_NEAREST_AWAY_FROM_ZERO,
        name="NEAREST-AWAY-FROM-ZERO",
        java_mode="HALF_UP",
        python_mode=ROUND_HALF_UP,
        description="Round half away from zero (COBOL default ROUNDED phrase).",
        ibm_clause="ROUNDED (default) or ROUNDED MODE IS NEAREST-AWAY-FROM-ZERO",
    ),
    ROUND_NEAREST_EVEN: RoundingModeSpec(
        mode_id=ROUND_NEAREST_EVEN,
        name="NEAREST-EVEN",
        java_mode="HALF_EVEN",
        python_mode=ROUND_HALF_EVEN,
        description="Round half to nearest even digit (banker's rounding).",
        ibm_clause="ROUNDED MODE IS NEAREST-EVEN",
    ),
    ROUND_NEAREST_TOWARD_ZERO: RoundingModeSpec(
        mode_id=ROUND_NEAREST_TOWARD_ZERO,
        name="NEAREST-TOWARD-ZERO",
        java_mode="HALF_DOWN",
        python_mode=ROUND_HALF_DOWN,
        description="Round half toward zero.",
        ibm_clause="ROUNDED MODE IS NEAREST-TOWARD-ZERO",
    ),
    ROUND_TOWARD_GREATER: RoundingModeSpec(
        mode_id=ROUND_TOWARD_GREATER,
        name="TOWARD-GREATER",
        java_mode="CEILING",
        python_mode=ROUND_CEILING,
        description="Round toward positive infinity.",
        ibm_clause="ROUNDED MODE IS TOWARD-GREATER",
    ),
    ROUND_TOWARD_LESSER: RoundingModeSpec(
        mode_id=ROUND_TOWARD_LESSER,
        name="TOWARD-LESSER",
        java_mode="FLOOR",
        python_mode=ROUND_FLOOR,
        description="Round toward negative infinity.",
        ibm_clause="ROUNDED MODE IS TOWARD-LESSER",
    ),
    ROUND_PROHIBITED: RoundingModeSpec(
        mode_id=ROUND_PROHIBITED,
        name="PROHIBITED",
        java_mode="UNNECESSARY",
        python_mode=None,
        description="No rounding permitted; if non-zero fractional digits are lost, ON SIZE ERROR is raised.",
        ibm_clause="ROUNDED MODE IS PROHIBITED",
    ),
}

ROUNDING_MODE_BY_NAME = {m.name: m for m in ROUNDING_MODES.values()}


# -------------------------------------------------------------------------------------- size error conditions


@dataclass(frozen=True)
class SizeErrorSpec:
    condition: str
    trigger: str
    receiver_action: str
    rule_id: str
    description: str


SIZE_ERROR_CONDITIONS: list[SizeErrorSpec] = [
    SizeErrorSpec(
        condition="DIVISION_BY_ZERO",
        trigger="Divisor evaluates to zero in DIVIDE or REMAINDER",
        receiver_action="Receiver unchanged; intermediate set to NaN",
        rule_id="RT-CBL-ZERO-DIVISOR-NAN",
        description="A zero divisor raises size error and makes intermediate NaN, leaving receiver unchanged.",
    ),
    SizeErrorSpec(
        condition="OVERFLOW_INTEGER_DIGITS",
        trigger="Magnitude of result exceeds PICTURE integer digits capacity",
        receiver_action="Receiver unchanged",
        rule_id="RT-CBL-SIZE-ERROR",
        description="When result does not fit integer digits, receiver is untouched and size error raised.",
    ),
    SizeErrorSpec(
        condition="EXPONENTIATION_ZERO_POW_ZERO",
        trigger="Base is zero and exponent is zero (0 ** 0)",
        receiver_action="Result yields 1; size error raised",
        rule_id="RT-CBL-EXPONENTIATION",
        description="0 ** 0 yields 1 with the size error raised under standard COBOL rules.",
    ),
    SizeErrorSpec(
        condition="EXPONENTIATION_NON_FINITE",
        trigger="Negative base with non-integer power or overflow to infinity",
        receiver_action="Result yields NaN; size error raised",
        rule_id="RT-CBL-EXPONENTIATION",
        description="Non-finite exponentiation results raise size error and yield NaN intermediate.",
    ),
    SizeErrorSpec(
        condition="PROHIBITED_ROUNDING_TRUNCATION",
        trigger="ROUNDED MODE IS PROHIBITED and non-zero fractional digits would be dropped",
        receiver_action="Receiver unchanged",
        rule_id="RT-CBL-SIZE-ERROR",
        description="Truncating non-zero digits under MODE PROHIBITED triggers size error.",
    ),
]


# -------------------------------------------------------------------------------------- rule catalogue metadata


@dataclass(frozen=True)
class ArithRuleMeta:
    id: str
    title: str
    status: str  # MATCHED / DIFFERS / REFUSED / ASSUMED
    ibm: dict[str, str] | None
    ibm_note: str | None = None
    options: list[str] = field(default_factory=list)
    register: list[str] = field(default_factory=list)
    description: str = ""


ARITH_RULES: dict[str, ArithRuleMeta] = {
    "RT-CBL-STORE-RESULT": ArithRuleMeta(
        id="RT-CBL-STORE-RESULT",
        title="An arithmetic result stored: low-order digits past the scale dropped or ROUNDED (half away from zero), high-order digits past the PICTURE (or the bytes, TRUNC(BIN) / COMP-5) lost; the typed-layer readers return exactly what the store leaves",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "ROUNDED phrase"},
        description="Arithmetic store with low-order truncation or rounding and high-order PICTURE truncation.",
    ),
    "RT-CBL-SIZE-ERROR": ArithRuleMeta(
        id="RT-CBL-SIZE-ERROR",
        title="ON SIZE ERROR: the receiver unchanged, and the condition true, when the value does not fit or is NaN",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Common phrases: SIZE ERROR"},
        description="Receiver remains untouched when size error occurs due to overflow, zero divisor, or NaN.",
    ),
    "RT-CBL-ZERO-DIVISOR-NAN": ArithRuleMeta(
        id="RT-CBL-ZERO-DIVISOR-NAN",
        title="A zero divisor raises the size error and makes the intermediate libcob's NaN: NaN in, NaN out through + - * and unary minus, and a store of NaN leaves the receiver unchanged",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "DIVIDE statement"},
        register=["C14"],
        description="Zero divisor creates NaN intermediate that propagates through arithmetic and leaves receivers intact.",
    ),
    "RT-CBL-DIVIDE-INTERMEDIATE": ArithRuleMeta(
        id="RT-CBL-DIVIDE-INTERMEDIATE",
        title="An intermediate quotient as cob_decimal_div forms it: scale a.scale - b.scale, the dividend shifted 38 digits more, truncated (38 + max(scale, 0) decimal places)",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Intermediate results in arithmetic statements"},
        description="Intermediate quotient scale is 38 + max(scaleA - scaleB, 0) with DOWN rounding.",
    ),
    "RT-CBL-DIVIDE-REMAINDER": ArithRuleMeta(
        id="RT-CBL-DIVIDE-REMAINDER",
        title="DIVIDE ... REMAINDER: dividend less divisor times the quotient truncated to the first GIVING receiver's scale (not to its high-order digits); a NaN quotient leaves the remainder receiver unchanged",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "DIVIDE statement: REMAINDER phrase"},
        description="Remainder calculation truncates intermediate quotient to first GIVING scale before subtracting.",
    ),
    "RT-CBL-DIVIDE-IN-FUNCTION-ARGUMENT": ArithRuleMeta(
        id="RT-CBL-DIVIDE-IN-FUNCTION-ARGUMENT",
        title="A division inside an intrinsic function's argument (cob_intr_binop): a zero divisor gives 0 with the size error raised, never NaN",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Intrinsic functions"},
        description="Division by zero inside intrinsic function argument evaluates to 0 instead of NaN.",
    ),
    "RT-CBL-UNSIGNED-BINARY-ABSOLUTE": ArithRuleMeta(
        id="RT-CBL-UNSIGNED-BINARY-ABSOLUTE",
        title="ADD / SUBTRACT into an unsigned binary item where cobc compiles native arithmetic: the receiver takes the absolute value (1 - 3 is 2), as IBM; the oracle wraps (declared)",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "ADD and SUBTRACT statements"},
        register=["C4"],
        description="Unsigned binary receiver takes absolute value of arithmetic result under IBM semantics.",
    ),
    "RT-CBL-EXPONENTIATION": ArithRuleMeta(
        id="RT-CBL-EXPONENTIATION",
        title="a ** b as cob_decimal_pow: a whole exponent exactly, else through double; 0 ** 0 is 1 with the size error raised, a non-finite result NaN with the size error raised",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Arithmetic expressions: Exponentiation"},
        description="Integral exponents evaluated exactly; 0**0 yields 1 with size error; non-finite yields NaN.",
    ),
    "RT-CBL-OSVS-INTERMEDIATE-ALIGN": ArithRuleMeta(
        id="RT-CBL-OSVS-INTERMEDIATE-ALIGN",
        title="ARITHMETIC-OSVS: an intermediate truncated to the statement's decimal places as cob_decimal_align does it (fewer places than the scale lose as many low-order digits: 579 aligned to 2 places is 500)",
        status="MATCHED",
        ibm={"doc": "cobol-pg", "section": "ARITH(COMPAT|EXTEND)"},
        register=["C2"],
        description="Intermediate alignment under ARITHMETIC-OSVS truncates low-order digits when scale differs.",
    ),
    "RT-CBL-DECIMAL-CONSTANT-SCALE": ArithRuleMeta(
        id="RT-CBL-DECIMAL-CONSTANT-SCALE",
        title="A numeric literal in a decimal expression is libcob's decimal constant: an ADD / SUBTRACT raises its scale and an exponent trims it in place, and later uses of the same literal see the change; a program restart resets it",
        status="DIFFERS",
        ibm=None,
        ibm_note="GnuCOBOL dc_N decimal constant caching behavior",
        register=["C2"],
        description="Decimal literal constants cache scaled intermediate values across statement executions.",
    ),
}


# -------------------------------------------------------------------------------------- deterministic test vectors


@dataclass(frozen=True)
class ArithVector:
    id: str
    title: str
    rule_id: str
    operation: str
    operand_a: str
    operand_b: str | None
    scale: int
    digits: int
    signed: bool
    rounded_mode: int
    expected_result: str
    expected_size_error: bool
    note: str = ""


ARITH_VECTORS: list[ArithVector] = [
    ArithVector(
        id="AR01-store-truncation",
        title="Store with default truncation drops low-order fractional digits",
        rule_id="RT-CBL-STORE-RESULT",
        operation="STORE",
        operand_a="12.345",
        operand_b=None,
        scale=2,
        digits=4,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="12.34",
        expected_size_error=False,
        note="12.345 truncated to scale 2 is 12.34",
    ),
    ArithVector(
        id="AR02-store-rounded-half-up",
        title="Store with ROUNDED rounds half away from zero",
        rule_id="RT-CBL-STORE-RESULT",
        operation="STORE",
        operand_a="12.345",
        operand_b=None,
        scale=2,
        digits=4,
        signed=False,
        rounded_mode=ROUND_NEAREST_AWAY_FROM_ZERO,
        expected_result="12.35",
        expected_size_error=False,
        note="12.345 rounded to scale 2 is 12.35",
    ),
    ArithVector(
        id="AR03-store-negative-rounded-half-up",
        title="Negative store with ROUNDED rounds half away from zero",
        rule_id="RT-CBL-STORE-RESULT",
        operation="STORE",
        operand_a="-12.345",
        operand_b=None,
        scale=2,
        digits=4,
        signed=True,
        rounded_mode=ROUND_NEAREST_AWAY_FROM_ZERO,
        expected_result="-12.35",
        expected_size_error=False,
        note="-12.345 rounded half away from zero is -12.35",
    ),
    ArithVector(
        id="AR04-store-high-order-truncation",
        title="Store without size error truncates high-order digits past PICTURE",
        rule_id="RT-CBL-STORE-RESULT",
        operation="STORE",
        operand_a="1234.56",
        operand_b=None,
        scale=2,
        digits=4,  # PICTURE 99V99 has 2 integer digits; 1234.56 has 4 integer digits
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="34.56",
        expected_size_error=False,
        note="High-order digits '12' truncated, leaving '34.56'",
    ),
    ArithVector(
        id="AR05-store-checked-overflow",
        title="Store with ON SIZE ERROR detects overflow and leaves receiver untouched",
        rule_id="RT-CBL-SIZE-ERROR",
        operation="STORE_CHECKED",
        operand_a="1234.56",
        operand_b=None,
        scale=2,
        digits=4,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="00.00",  # Untouched receiver
        expected_size_error=True,
        note="1234.56 exceeds PIC 99V99; size error raised, receiver unchanged",
    ),
    ArithVector(
        id="AR06-divide-zero-size-error",
        title="Division by zero raises size error and yields NaN intermediate",
        rule_id="RT-CBL-ZERO-DIVISOR-NAN",
        operation="DIVIDE",
        operand_a="100.00",
        operand_b="0",
        scale=2,
        digits=6,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="NAN",
        expected_size_error=True,
        note="Zero divisor raises size error and produces NaN",
    ),
    ArithVector(
        id="AR07-store-nan-leaves-receiver-unchanged",
        title="Store of NaN intermediate leaves receiver untouched",
        rule_id="RT-CBL-ZERO-DIVISOR-NAN",
        operation="STORE_NAN",
        operand_a="NAN",
        operand_b=None,
        scale=2,
        digits=6,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="UNCHANGED",
        expected_size_error=True,
        note="NaN stored into receiver leaves receiver unchanged",
    ),
    ArithVector(
        id="AR08-divide-remainder-scale-truncation",
        title="DIVIDE REMAINDER truncates quotient to giving scale before multiplying",
        rule_id="RT-CBL-DIVIDE-REMAINDER",
        operation="REMAINDER",
        operand_a="100",  # Dividend
        operand_b="7",  # Divisor
        scale=1,  # GIVING scale
        digits=4,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="0.6",  # 100 - (14.2 * 7) = 100 - 99.4 = 0.6
        expected_size_error=False,
        note="Quotient 14.2857... truncated to scale 1 is 14.2; 100 - (14.2 * 7) = 0.6",
    ),
    ArithVector(
        id="AR09-unsigned-binary-native-absolute",
        title="ADD/SUBTRACT into unsigned binary receiver takes absolute value",
        rule_id="RT-CBL-UNSIGNED-BINARY-ABSOLUTE",
        operation="NATIVE_STORE",
        operand_a="-2",  # Result of 1 - 3
        operand_b=None,
        scale=0,
        digits=4,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="2",
        expected_size_error=False,
        note="|-2| = 2 stored in unsigned receiver",
    ),
    ArithVector(
        id="AR10-power-zero-pow-zero",
        title="0 ** 0 yields 1 and raises size error",
        rule_id="RT-CBL-EXPONENTIATION",
        operation="POWER",
        operand_a="0",
        operand_b="0",
        scale=0,
        digits=2,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="1",
        expected_size_error=True,
        note="0 ** 0 is 1 with size error raised",
    ),
    ArithVector(
        id="AR11-power-whole-exponent",
        title="Whole positive exponent evaluates exactly",
        rule_id="RT-CBL-EXPONENTIATION",
        operation="POWER",
        operand_a="2",
        operand_b="10",
        scale=0,
        digits=5,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="1024",
        expected_size_error=False,
        note="2 ** 10 = 1024 exact",
    ),
    ArithVector(
        id="AR12-osvs-align-scale-shift",
        title="ARITHMETIC-OSVS intermediate alignment shifts and drops low-order digits",
        rule_id="RT-CBL-OSVS-INTERMEDIATE-ALIGN",
        operation="ALIGN_OSVS",
        operand_a="579",
        operand_b=None,
        scale=2,  # Aligning to 2 decimal places when scale was 0
        digits=5,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="500",
        expected_size_error=False,
        note="579 aligned to 2 decimal places loses 2 low-order digits -> 500",
    ),
    ArithVector(
        id="AR13-divide-intr-zero-gives-zero",
        title="Division by zero in function argument yields 0, never NaN",
        rule_id="RT-CBL-DIVIDE-IN-FUNCTION-ARGUMENT",
        operation="DIVIDE_INTR",
        operand_a="10",
        operand_b="0",
        scale=0,
        digits=4,
        signed=False,
        rounded_mode=ROUND_TRUNCATION,
        expected_result="0",
        expected_size_error=True,
        note="divideIntr by zero returns 0 with size error raised",
    ),
]


# -------------------------------------------------------------------------------------- arithmetic helpers


def calculate_divide_intermediate_scale(scale_a: int, scale_b: int) -> int:
    """Formula: 38 + max(scale_a - scale_b, 0)."""
    return 38 + max(scale_a - scale_b, 0)


def calculate_divide_remainder(dividend: Decimal, divisor: Decimal, giving_scale: int) -> Decimal:
    """Dividend less divisor times quotient truncated to giving_scale."""
    if divisor == Decimal(0):
        raise ZeroDivisionError("division by zero")
    quotient = dividend / divisor
    q_trunc = quotient.quantize(Decimal(10) ** -giving_scale, rounding=ROUND_DOWN)
    return dividend - (q_trunc * divisor)


def is_picture_overflow(value: Decimal, total_digits: int, scale: int) -> bool:
    """True if unscaled integer digits exceed (total_digits - scale)."""
    int_digits = total_digits - scale
    v_abs = abs(value)
    int_part = int(v_abs)
    if int_part == 0:
        return False
    return len(str(int_part)) > int_digits
