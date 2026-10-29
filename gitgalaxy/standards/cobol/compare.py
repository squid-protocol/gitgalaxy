# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL relation condition and comparison rule family as declarative data (#4712, epic #4710).

Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
Chapter "Conditional expressions" -> "Relation conditions"
(Comparison of numeric operands, Comparison of nonnumeric operands,
 Comparison of numeric and nonnumeric operands, Figurative constants in comparisons).

Defines:
  COMPARE_MODES     The 5 evaluation modes for relational comparisons
  COMPARE_RULES     Catalogue rule metadata for the 8 comparison rules
  COMPARE_MATRIX    The full 9x9 relation condition matrix with rule and mode dispatch
  COMPARE_VECTORS   Deterministic test vectors executed directly in CI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.standards.cobol.move import KIND_CATEGORY, KINDS, NUMERIC

# -------------------------------------------------------------------------------------- comparison modes

MODE_NUMERIC = 0
MODE_FLOAT = 1
MODE_NONNUMERIC = 2
MODE_NUMERIC_WITH_NONNUMERIC = 3
MODE_FLOAT_REFUSED = 4

COMPARE_MODES = {
    "NUMERIC": MODE_NUMERIC,
    "FLOAT": MODE_FLOAT,
    "NONNUMERIC": MODE_NONNUMERIC,
    "NUMERIC_WITH_NONNUMERIC": MODE_NUMERIC_WITH_NONNUMERIC,
    "FLOAT_REFUSED": MODE_FLOAT_REFUSED,
}

MODE_NAMES = {
    MODE_NUMERIC: "NUMERIC",
    MODE_FLOAT: "FLOAT",
    MODE_NONNUMERIC: "NONNUMERIC",
    MODE_NUMERIC_WITH_NONNUMERIC: "NUMERIC_WITH_NONNUMERIC",
    MODE_FLOAT_REFUSED: "FLOAT_REFUSED",
}


# -------------------------------------------------------------------------------------- rule catalogue metadata


@dataclass(frozen=True)
class CompareRuleMeta:
    id: str
    title: str
    status: str  # MATCHED / DIFFERS / REFUSED / ASSUMED
    ibm: dict[str, str] | None
    ibm_note: str | None = None
    options: list[str] = field(default_factory=list)
    register: list[str] = field(default_factory=list)
    description: str = ""


COMPARE_RULES: dict[str, CompareRuleMeta] = {
    "RT-CBL-COMPARE-NUMERIC": CompareRuleMeta(
        id="RT-CBL-COMPARE-NUMERIC",
        title="Numeric operands compared by value, whatever their usage and the collating sequence",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Comparison of numeric operands"},
        description="Algebraic comparison by value; usage (display, packed, binary) and collating sequence ignored.",
    ),
    "RT-CBL-COMPARE-FLOAT": CompareRuleMeta(
        id="RT-CBL-COMPARE-FLOAT",
        title="A comparison with a floating-point comparand is made in floating point",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Comparison of numeric operands"},
        register=["C6"],
        description="Fixed-point operand converted to long HFP and compared algebraically.",
    ),
    "RT-CBL-COMPARE-NONNUMERIC": CompareRuleMeta(
        id="RT-CBL-COMPARE-NONNUMERIC",
        title="Nonnumeric operands compared byte by byte, the shorter padded with spaces",
        status="DIFFERS",
        ibm={"doc": "cobol-lr", "section": "Comparison of alphanumeric operands"},
        options=["PROGRAM-COLLATING-SEQUENCE"],
        register=["D1"],
        description="Compared byte by byte in character code order or under PROGRAM COLLATING SEQUENCE.",
    ),
    "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC": CompareRuleMeta(
        id="RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC",
        title="A numeric item against a nonnumeric one is its digits as characters, the sign dropped",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "General relation conditions: Alphanumeric comparisons"},
        register=["C13"],
        description="Numeric item treated as if moved to alphanumeric of as many characters as digits, sign dropped.",
    ),
    "RT-CBL-COMPARE-NONDIGIT": CompareRuleMeta(
        id="RT-CBL-COMPARE-NONDIGIT",
        title="A numeric item's value in a comparison: a zoned item holding a non-digit as the oracle compares it",
        status="DIFFERS",
        ibm=None,
        ibm_note="IBM documents no result; oracle uses Zoned.compareValue",
        register=["C11"],
        description="Zoned non-digit comparand evaluated through oracle signed integer calculation.",
    ),
    "RT-CBL-COMPARE-ALL-LITERAL": CompareRuleMeta(
        id="RT-CBL-COMPARE-ALL-LITERAL",
        title="An item against an ALL literal: the literal repeated or cut to the item's length",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Figurative constants: ALL literal"},
        options=["PROGRAM-COLLATING-SEQUENCE"],
        description="Literal repeated or truncated to length of other comparand, compared byte by byte.",
    ),
    "RT-CBL-COMPARE-FIGURATIVE": CompareRuleMeta(
        id="RT-CBL-COMPARE-FIGURATIVE",
        title="An item against a figurative constant: constant character repeated (ZERO against numeric by value)",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Figurative constants"},
        options=["PROGRAM-COLLATING-SEQUENCE"],
        description="ZERO against numeric compares by value; other figuratives repeat byte to comparand length.",
    ),
    "RT-NUM-NONDIGIT-COMPARE": CompareRuleMeta(
        id="RT-NUM-NONDIGIT-COMPARE",
        title="A zoned comparand holding a non-digit: every digit position counts in a signed 64-bit integer",
        status="DIFFERS",
        ibm=None,
        ibm_note="Oracle GnuCOBOL cob_cmp_numdisp behavior",
        options=["NUMPROC"],
        register=["C11"],
        description="NUM runtime rule evaluating dirty zoned digits in numeric comparison.",
    ),
}


# -------------------------------------------------------------------------------------- 9x9 relation condition matrix


@dataclass(frozen=True)
class CompareMatrixEntry:
    left_kind: str
    right_kind: str
    mode: str
    rule_id: str
    ibm_section: str
    note: str = ""


def _build_compare_matrix() -> dict[tuple[str, str], CompareMatrixEntry]:
    m: dict[tuple[str, str], CompareMatrixEntry] = {}

    for lk in KINDS:
        for rk in KINDS:
            lc = KIND_CATEGORY[lk]
            rc = KIND_CATEGORY[rk]

            # Float comparisons
            if lk == "NUMERIC_FLOAT" or rk == "NUMERIC_FLOAT":
                if lc == NUMERIC and rc == NUMERIC:
                    m[(lk, rk)] = CompareMatrixEntry(
                        left_kind=lk,
                        right_kind=rk,
                        mode="FLOAT",
                        rule_id="RT-CBL-COMPARE-FLOAT",
                        ibm_section="Comparison of numeric operands",
                        note="Evaluated in floating-point; fixed-point comparand converted to long HFP",
                    )
                else:
                    m[(lk, rk)] = CompareMatrixEntry(
                        left_kind=lk,
                        right_kind=rk,
                        mode="FLOAT_REFUSED",
                        rule_id="RT-CBL-COMPARE-FLOAT",
                        ibm_section="Comparison of numeric operands",
                        note="Comparison of COMP-1/COMP-2 raw bytes with nonnumeric operand is refused (register C6)",
                    )
                continue

            # Both numeric
            if lc == NUMERIC and rc == NUMERIC:
                m[(lk, rk)] = CompareMatrixEntry(
                    left_kind=lk,
                    right_kind=rk,
                    mode="NUMERIC",
                    rule_id="RT-CBL-COMPARE-NUMERIC",
                    ibm_section="Comparison of numeric operands",
                    note="Compared algebraically by value regardless of usage or collating sequence",
                )
                continue

            # Both nonnumeric or groups
            if lc != NUMERIC and rc != NUMERIC:
                m[(lk, rk)] = CompareMatrixEntry(
                    left_kind=lk,
                    right_kind=rk,
                    mode="NONNUMERIC",
                    rule_id="RT-CBL-COMPARE-NONNUMERIC",
                    ibm_section="Comparison of alphanumeric operands",
                    note="Compared byte by byte, shorter operand padded with spaces",
                )
                continue

            # Numeric with nonnumeric
            m[(lk, rk)] = CompareMatrixEntry(
                left_kind=lk,
                right_kind=rk,
                mode="NUMERIC_WITH_NONNUMERIC",
                rule_id="RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC",
                ibm_section="General relation conditions: Alphanumeric comparisons",
                note="Numeric operand treated as unsigned digits string, compared byte by byte with space padding",
            )

    return m


COMPARE_MATRIX = _build_compare_matrix()


# -------------------------------------------------------------------------------------- test vectors


@dataclass(frozen=True)
class CompareVector:
    id: str
    title: str
    rule_id: str
    left_spec: dict[str, Any]
    right_spec: dict[str, Any]
    left_bytes: bytes
    right_bytes: bytes
    expected_result: int  # -1 for <, 0 for ==, 1 for >
    note: str = ""


COMPARE_VECTORS: list[CompareVector] = [
    CompareVector(
        id="CP01-numeric-equal-different-scale",
        title="Numeric operands with different scales compare by value",
        rule_id="RT-CBL-COMPARE-NUMERIC",
        left_spec={"kind": "NUMERIC_DISPLAY", "digits": 4, "scale": 2},
        right_spec={"kind": "NUMERIC_DISPLAY", "digits": 3, "scale": 1},
        left_bytes=b"1230",  # 12.30
        right_bytes=b"123",  # 12.3
        expected_result=0,
        note="12.30 equals 12.3 algebraically",
    ),
    CompareVector(
        id="CP02-numeric-signed-less",
        title="Negative numeric compares less than positive",
        rule_id="RT-CBL-COMPARE-NUMERIC",
        left_spec={"kind": "NUMERIC_DISPLAY", "digits": 2, "scale": 0, "signed": True},
        right_spec={"kind": "NUMERIC_DISPLAY", "digits": 2, "scale": 0, "signed": True},
        left_bytes=b"0N",  # 05 with negative overpunch N = -05
        right_bytes=b"05",  # +05
        expected_result=-1,
        note="-5 < 5",
    ),
    CompareVector(
        id="CP03-nonnumeric-equal-space-pad",
        title="Alphanumeric shorter operand padded with spaces",
        rule_id="RT-CBL-COMPARE-NONNUMERIC",
        left_spec={"kind": "ALPHANUMERIC", "len": 3},
        right_spec={"kind": "ALPHANUMERIC", "len": 5},
        left_bytes=b"ABC",
        right_bytes=b"ABC  ",
        expected_result=0,
        note="'ABC' pads to 'ABC  ', equal",
    ),
    CompareVector(
        id="CP04-nonnumeric-lexicographic",
        title="Alphanumeric lexicographic byte ordering",
        rule_id="RT-CBL-COMPARE-NONNUMERIC",
        left_spec={"kind": "ALPHANUMERIC", "len": 3},
        right_spec={"kind": "ALPHANUMERIC", "len": 3},
        left_bytes=b"ABC",
        right_bytes=b"ABD",
        expected_result=-1,
        note="'ABC' < 'ABD'",
    ),
    CompareVector(
        id="CP05-numeric-with-nonnumeric-digits",
        title="Numeric against alphanumeric compares unsigned digits",
        rule_id="RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC",
        left_spec={"kind": "NUMERIC_DISPLAY", "digits": 3, "scale": 0, "signed": False},
        right_spec={"kind": "ALPHANUMERIC", "len": 3},
        left_bytes=b"123",
        right_bytes=b"123",
        expected_result=0,
        note="123 as digits matches '123'",
    ),
    CompareVector(
        id="CP06-numeric-signed-with-nonnumeric-unpunched",
        title="Signed numeric against alphanumeric de-punches sign",
        rule_id="RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC",
        left_spec={"kind": "NUMERIC_DISPLAY", "digits": 3, "scale": 0, "signed": True},
        right_spec={"kind": "ALPHANUMERIC", "len": 3},
        left_bytes=b"01B",  # 012 with positive overpunch B = +12
        right_bytes=b"012",
        expected_result=0,
        note="Sign is dropped; digits '012' compared against '012'",
    ),
    CompareVector(
        id="CP07-all-literal-comparison",
        title="Comparison against ALL literal repeats pattern",
        rule_id="RT-CBL-COMPARE-ALL-LITERAL",
        left_spec={"kind": "ALPHANUMERIC", "len": 4},
        right_spec={"kind": "ALL_LITERAL", "pattern": "XY"},
        left_bytes=b"XYXY",
        right_bytes=b"XY",
        expected_result=0,
        note="ALL 'XY' repeated to length 4 gives 'XYXY'",
    ),
    CompareVector(
        id="CP08-figurative-spaces-comparison",
        title="Comparison against SPACES figurative constant",
        rule_id="RT-CBL-COMPARE-FIGURATIVE",
        left_spec={"kind": "ALPHANUMERIC", "len": 4},
        right_spec={"kind": "FIGURATIVE", "constant": "SPACES"},
        left_bytes=b"    ",
        right_bytes=b" ",
        expected_result=0,
        note="All spaces matches SPACES",
    ),
]
