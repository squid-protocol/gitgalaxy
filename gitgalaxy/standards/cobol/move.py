# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL MOVE rule family as declarative data (#4712, epic #4710).

Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
Chapter "MOVE statement" (Elementary moves, De-editing, Permissible moves).

Defines:
  CATEGORIES     The 5 runtime categories (GROUP, ALNUM, NUMERIC, NUM_EDITED, ALNUM_EDITED)
  KINDS          The 9 Field.Kind enum names
  ACTIONS        The runtime movement actions
  MOVE_RULES     Catalogue rule metadata for the 11 RT-CBL-MOVE-* rules
  MOVE_MATRIX    The full 9x9 permissible move matrix with rule and action dispatch
  FIGURATIVE_MOVES  Rules for Figurative constant movements
  MOVE_VECTORS   Deterministic test vectors executed directly in CI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# -------------------------------------------------------------------------------------- categories and kinds

# Matches Cobol.java / MoveSpec.java category constants
GROUP = 0
ALNUM = 1
NUMERIC = 2
NUM_EDITED = 3
ALNUM_EDITED = 4

CATEGORIES = {
    "GROUP": GROUP,
    "ALNUM": ALNUM,
    "NUMERIC": NUMERIC,
    "NUM_EDITED": NUM_EDITED,
    "ALNUM_EDITED": ALNUM_EDITED,
}

CATEGORY_NAMES = {
    GROUP: "GROUP",
    ALNUM: "ALNUM",
    NUMERIC: "NUMERIC",
    NUM_EDITED: "NUM_EDITED",
    ALNUM_EDITED: "ALNUM_EDITED",
}

KINDS = (
    "GROUP",
    "ALPHANUMERIC",
    "ALPHABETIC",
    "NUMERIC_DISPLAY",
    "NUMERIC_PACKED",
    "NUMERIC_BINARY",
    "NUMERIC_EDITED",
    "ALPHANUMERIC_EDITED",
    "NUMERIC_FLOAT",
)

KIND_CATEGORY: dict[str, int] = {
    "GROUP": GROUP,
    "ALPHANUMERIC": ALNUM,
    "ALPHABETIC": ALNUM,
    "NUMERIC_DISPLAY": NUMERIC,
    "NUMERIC_PACKED": NUMERIC,
    "NUMERIC_BINARY": NUMERIC,
    "NUMERIC_FLOAT": NUMERIC,
    "NUMERIC_EDITED": NUM_EDITED,
    "ALPHANUMERIC_EDITED": ALNUM_EDITED,
}

ACTIONS = (
    "GROUP_COPY",
    "SAME_SHAPE_COPY",
    "ALNUM_STORE",
    "ALNUM_EDIT_INSERT",
    "NUMERIC_STORE",
    "NUMERIC_EDIT",
    "FLOAT_CONVERT",
    "FLOAT_REFUSED",
    "DEEDIT_NUMERIC",
    "ALNUM_TO_NUMERIC",
    "NUMERIC_TO_ALNUM",
    "NONDIGIT_BINARY",
    "NONDIGIT_MOVE",
    "ILLEGAL",
)


# -------------------------------------------------------------------------------------- rule catalogue metadata


@dataclass(frozen=True)
class MoveRuleMeta:
    id: str
    title: str
    status: str  # MATCHED / DIFFERS / REFUSED / ASSUMED
    ibm: dict[str, str] | None
    ibm_note: str | None = None
    options: list[str] = field(default_factory=list)
    register: list[str] = field(default_factory=list)
    description: str = ""


MOVE_RULES: dict[str, MoveRuleMeta] = {
    "RT-CBL-MOVE-SAME-ZONED-SHAPE": MoveRuleMeta(
        id="RT-CBL-MOVE-SAME-ZONED-SHAPE",
        title="A MOVE between zoned items of one shape (digits, scale, sign, sign position, size) copies the bytes",
        status="DIFFERS",
        ibm=None,
        ibm_note="cobc compiles as memcpy (cb_build_move_copy); sign rewrite and store_common_region never run",
        register=["C11"],
        description="A space or non-digit in a digit position travels as-is when sender and receiver shapes match.",
    ),
    "RT-CBL-MOVE-ELEMENTARY": MoveRuleMeta(
        id="RT-CBL-MOVE-ELEMENTARY",
        title="MOVE by receiver category: alphanumeric padded/truncated, numeric aligned on decimal point, etc.",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "MOVE statement: elementary moves"},
        options=["DECIMAL-POINT-COMMA"],
        description="Core elementary move: aligns on decimal point, pads/truncates according to picture clauses.",
    ),
    "RT-CBL-MOVE-NONDIGIT-TO-BINARY": MoveRuleMeta(
        id="RT-CBL-MOVE-NONDIGIT-TO-BINARY",
        title="A zoned sender holding a non-digit MOVEd to a binary item",
        status="DIFFERS",
        ibm=None,
        ibm_note="IBM documents no result; oracle/libcob counts each byte as char - '0' mod 2^64",
        options=["TRUNC"],
        register=["C11"],
        description="Zoned non-digit bytes evaluated as char - '0' in 64-bit unsigned accumulator with TRUNC.",
    ),
    "RT-CBL-MOVE-NONDIGIT-SIGN-REFUSED": MoveRuleMeta(
        id="RT-CBL-MOVE-NONDIGIT-SIGN-REFUSED",
        title="A signed zoned sender whose sign byte is neither digit, overpunch, sign nor space: refused",
        status="REFUSED",
        ibm=None,
        ibm_note="Undefined data; IBM documents no result",
        register=["C11"],
        description="Refuses MOVE of dirty sign byte by name when converting to binary or alphanumeric.",
    ),
    "RT-CBL-MOVE-NONDIGIT": MoveRuleMeta(
        id="RT-CBL-MOVE-NONDIGIT",
        title="A zoned sender holding a non-digit MOVEd to a zoned, packed or numeric-edited receiver",
        status="DIFFERS",
        ibm=None,
        ibm_note="IBM documents no result; oracle uses Zoned byte conversion rules",
        register=["C11"],
        description="Non-digit byte conversion rules for zoned/packed/edited destinations.",
    ),
    "RT-CBL-MOVE-FLOAT": MoveRuleMeta(
        id="RT-CBL-MOVE-FLOAT",
        title="A MOVE with a COMP-1 / COMP-2 sender or receiver",
        status="MATCHED",
        ibm={"doc": "cobol-pg", "section": "Conversions and precision"},
        register=["C6"],
        description="Converts between fixed and float precision (9 digits for single, 18 for double HFP).",
    ),
    "RT-CBL-MOVE-FIGURATIVE": MoveRuleMeta(
        id="RT-CBL-MOVE-FIGURATIVE",
        title="MOVE of a figurative constant: ZERO stored as numeric 0, others byte repeated",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Figurative constants"},
        options=["QUOTE"],
        register=["C6"],
        description="ZERO/ZEROS stored as value 0 in numeric fields; SPACE/LOW/HIGH/QUOTE filled as byte sequences.",
    ),
    "RT-CBL-MOVE-ALL-LITERAL": MoveRuleMeta(
        id="RT-CBL-MOVE-ALL-LITERAL",
        title="MOVE ALL literal: the literal repeated to the receiver's size",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "Figurative constants: ALL literal"},
        description="Repeats pattern to fill receiver; numeric receivers align pattern at the right edge.",
    ),
    "RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC": MoveRuleMeta(
        id="RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC",
        title="A numeric sender MOVEd to an alphanumeric receiver as its unsigned digits",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "MOVE statement: elementary moves"},
        description="Overpunched sign removed, separate sign dropped, right-P scaling emitted as zeros.",
    ),
    "RT-CBL-MOVE-DEEDIT": MoveRuleMeta(
        id="RT-CBL-MOVE-DEEDIT",
        title="A numeric-edited sender MOVEd to a numeric receiver is de-edited",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "MOVE statement: de-editing"},
        options=["DECIMAL-POINT-COMMA"],
        description="Extracts digits, sets negative sign when '-', 'CR' or 'DB' symbol is present.",
    ),
    "RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC": MoveRuleMeta(
        id="RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC",
        title="An alphanumeric sender MOVEd to a numeric receiver read as libcob does",
        status="ASSUMED",
        ibm={"doc": "cobol-lr", "section": "MOVE statement: elementary moves"},
        options=["DECIMAL-POINT-COMMA"],
        description="Leading spaces and sign skipped; digits aligned on first decimal point; stray chars yield 0.",
    ),
}


# -------------------------------------------------------------------------------------- 9x9 permissible move matrix


@dataclass(frozen=True)
class MoveMatrixEntry:
    from_kind: str
    to_kind: str
    permissible: bool
    rule_id: str
    action: str
    ibm_section: str
    note: str = ""


def _build_matrix() -> dict[tuple[str, str], MoveMatrixEntry]:
    m: dict[tuple[str, str], MoveMatrixEntry] = {}

    for fk in KINDS:
        for tk in KINDS:
            # Group rules
            if tk == "GROUP" or fk == "GROUP":
                m[(fk, tk)] = MoveMatrixEntry(
                    from_kind=fk,
                    to_kind=tk,
                    permissible=True,
                    rule_id="RT-CBL-MOVE-ELEMENTARY",
                    action="GROUP_COPY",
                    ibm_section="MOVE statement: group moves",
                    note="Treated as an alphanumeric move without conversion between elementary items",
                )
                continue

            # Float rules
            if fk == "NUMERIC_FLOAT" or tk == "NUMERIC_FLOAT":
                if fk == "NUMERIC_FLOAT" and tk == "NUMERIC_FLOAT":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-FLOAT",
                        action="FLOAT_CONVERT",
                        ibm_section="Conversions and precision",
                        note="Float to float copy/precision adjustment",
                    )
                elif fk == "NUMERIC_FLOAT" and tk in (
                    "NUMERIC_DISPLAY",
                    "NUMERIC_PACKED",
                    "NUMERIC_BINARY",
                    "NUMERIC_EDITED",
                ):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-FLOAT",
                        action="FLOAT_CONVERT",
                        ibm_section="Conversions and precision",
                        note="Float converted to fixed-point, rounded in low-order position",
                    )
                elif tk == "NUMERIC_FLOAT" and fk in (
                    "NUMERIC_DISPLAY",
                    "NUMERIC_PACKED",
                    "NUMERIC_BINARY",
                    "NUMERIC_EDITED",
                ):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-FLOAT",
                        action="FLOAT_CONVERT",
                        ibm_section="Conversions and precision",
                        note="Fixed-point converted to float precision",
                    )
                else:
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=False,
                        rule_id="RT-CBL-MOVE-FLOAT",
                        action="FLOAT_REFUSED",
                        ibm_section="Conversions and precision",
                        note="MOVE of COMP-1/COMP-2 raw bytes to non-numeric is refused (register C6)",
                    )
                continue

            # Alphabetic source
            if fk == "ALPHABETIC":
                if tk in ("ALPHABETIC", "ALPHANUMERIC"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ALNUM_STORE",
                        ibm_section="MOVE statement: elementary moves",
                        note="Left-aligned, space-padded or truncated",
                    )
                elif tk == "ALPHANUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ALNUM_EDIT_INSERT",
                        ibm_section="MOVE statement: elementary moves",
                        note="Formatted through insertion characters",
                    )
                else:
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=False,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ILLEGAL",
                        ibm_section="MOVE statement: Table 43 Permissible moves",
                        note="Illegal: Alphabetic cannot be moved to numeric or numeric-edited",
                    )
                continue

            # Alphanumeric source
            if fk == "ALPHANUMERIC":
                if tk in ("ALPHANUMERIC", "ALPHABETIC"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ALNUM_STORE",
                        ibm_section="MOVE statement: elementary moves",
                        note="Left-aligned, space-padded or truncated (JUSTIFIED RIGHT supported)",
                    )
                elif tk == "ALPHANUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ALNUM_EDIT_INSERT",
                        ibm_section="MOVE statement: elementary moves",
                        note="Formatted through insertion characters",
                    )
                elif tk == "NUMERIC_DISPLAY":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC",
                        action="ALNUM_TO_NUMERIC",
                        ibm_section="MOVE statement: elementary moves",
                        note="Alphanumeric to zoned display: leading spaces/sign skipped, decimal aligned",
                    )
                elif tk in ("NUMERIC_BINARY", "NUMERIC_PACKED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC",
                        action="ALNUM_TO_NUMERIC",
                        ibm_section="MOVE statement: elementary moves",
                        note="Alphanumeric parsed to number; stray character makes value zero",
                    )
                elif tk == "NUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="NUMERIC_EDIT",
                        ibm_section="MOVE statement: elementary moves",
                        note="Parsed as numeric value, then formatted according to numeric PICTURE",
                    )
                continue

            # Alphanumeric-edited source
            if fk == "ALPHANUMERIC_EDITED":
                if tk in ("ALPHANUMERIC", "ALPHABETIC"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ALNUM_STORE",
                        ibm_section="MOVE statement: elementary moves",
                        note="Treated as alphanumeric string",
                    )
                elif tk == "ALPHANUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ALNUM_EDIT_INSERT",
                        ibm_section="MOVE statement: elementary moves",
                        note="Source treated as string, moved into edited receiver",
                    )
                elif tk in ("NUMERIC_DISPLAY", "NUMERIC_BINARY", "NUMERIC_PACKED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC",
                        action="ALNUM_TO_NUMERIC",
                        ibm_section="MOVE statement: elementary moves",
                        note="De-edited as alphanumeric text into numeric",
                    )
                elif tk == "NUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="NUMERIC_EDIT",
                        ibm_section="MOVE statement: elementary moves",
                        note="Parsed as numeric value, then formatted",
                    )
                continue

            # Numeric display source
            if fk == "NUMERIC_DISPLAY":
                if tk in ("ALPHANUMERIC", "ALPHANUMERIC_EDITED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC",
                        action="NUMERIC_TO_ALNUM",
                        ibm_section="MOVE statement: elementary moves",
                        note="Overpunched sign unpunched, separate sign dropped, right-P as zeros",
                    )
                elif tk == "ALPHABETIC":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=False,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ILLEGAL",
                        ibm_section="MOVE statement: Table 43 Permissible moves",
                        note="Illegal: Numeric cannot be moved to alphabetic",
                    )
                elif tk == "NUMERIC_DISPLAY":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-SAME-ZONED-SHAPE",
                        action="SAME_SHAPE_COPY",
                        ibm_section="MOVE statement: elementary moves",
                        note="If shapes match: byte copy (C11). If shapes differ: decimal alignment",
                    )
                elif tk in ("NUMERIC_BINARY", "NUMERIC_PACKED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="NUMERIC_STORE",
                        ibm_section="MOVE statement: elementary moves",
                        note="Value aligned on decimal point; if dirty zoned byte, nonDigitToBinary or moveNonDigit",
                    )
                elif tk == "NUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="NUMERIC_EDIT",
                        ibm_section="MOVE statement: elementary moves",
                        note="Edited according to PICTURE, decimal point alignment, BLANK WHEN ZERO",
                    )
                continue

            # Numeric binary or packed source
            if fk in ("NUMERIC_BINARY", "NUMERIC_PACKED"):
                if tk in ("ALPHANUMERIC", "ALPHANUMERIC_EDITED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC",
                        action="NUMERIC_TO_ALNUM",
                        ibm_section="MOVE statement: elementary moves",
                        note="Unsigned digits as text, left-zero padded to picture width",
                    )
                elif tk == "ALPHABETIC":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=False,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ILLEGAL",
                        ibm_section="MOVE statement: Table 43 Permissible moves",
                        note="Illegal: Binary/Packed cannot be moved to alphabetic",
                    )
                elif tk in ("NUMERIC_DISPLAY", "NUMERIC_BINARY", "NUMERIC_PACKED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="NUMERIC_STORE",
                        ibm_section="MOVE statement: elementary moves",
                        note="Numeric value stored aligned on decimal point, truncated / zero-padded",
                    )
                elif tk == "NUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="NUMERIC_EDIT",
                        ibm_section="MOVE statement: elementary moves",
                        note="Formatted according to edited PICTURE",
                    )
                continue

            # Numeric edited source
            if fk == "NUMERIC_EDITED":
                if tk in ("ALPHANUMERIC", "ALPHANUMERIC_EDITED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ALNUM_STORE",
                        ibm_section="MOVE statement: elementary moves",
                        note="Edited field moved as raw character text",
                    )
                elif tk == "ALPHABETIC":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=False,
                        rule_id="RT-CBL-MOVE-ELEMENTARY",
                        action="ILLEGAL",
                        ibm_section="MOVE statement: Table 43 Permissible moves",
                        note="Illegal: Numeric-edited cannot be moved to alphabetic",
                    )
                elif tk in ("NUMERIC_DISPLAY", "NUMERIC_BINARY", "NUMERIC_PACKED"):
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-DEEDIT",
                        action="DEEDIT_NUMERIC",
                        ibm_section="MOVE statement: de-editing",
                        note="De-edited to digits, negative sign recognized from '-', 'CR', 'DB'",
                    )
                elif tk == "NUMERIC_EDITED":
                    m[(fk, tk)] = MoveMatrixEntry(
                        from_kind=fk,
                        to_kind=tk,
                        permissible=True,
                        rule_id="RT-CBL-MOVE-DEEDIT",
                        action="DEEDIT_NUMERIC",
                        ibm_section="MOVE statement: de-editing",
                        note="De-edited to numeric value, then formatted into target edited picture",
                    )
                continue

    return m


MOVE_MATRIX = _build_matrix()


# -------------------------------------------------------------------------------------- test vectors


@dataclass(frozen=True)
class MoveVector:
    id: str
    title: str
    rule_id: str
    from_spec: dict[str, Any]
    to_spec: dict[str, Any]
    input_bytes: bytes
    expected_bytes: bytes
    note: str = ""


# Concrete vectors covering all 11 rules and edge cases
MOVE_VECTORS: list[MoveVector] = [
    MoveVector(
        id="MV01-alnum-pad",
        title="Alphanumeric left-justified, space padded",
        rule_id="RT-CBL-MOVE-ELEMENTARY",
        from_spec={"kind": "ALPHANUMERIC", "len": 3},
        to_spec={"kind": "ALPHANUMERIC", "len": 5, "jr": False},
        input_bytes=b"ABC",
        expected_bytes=b"ABC  ",
        note="Space padding on right",
    ),
    MoveVector(
        id="MV02-alnum-trunc",
        title="Alphanumeric truncated on right",
        rule_id="RT-CBL-MOVE-ELEMENTARY",
        from_spec={"kind": "ALPHANUMERIC", "len": 5},
        to_spec={"kind": "ALPHANUMERIC", "len": 3, "jr": False},
        input_bytes=b"ABCDE",
        expected_bytes=b"ABC",
        note="Right truncation",
    ),
    MoveVector(
        id="MV03-justified-right-pad",
        title="JUSTIFIED RIGHT padded on left",
        rule_id="RT-CBL-MOVE-ELEMENTARY",
        from_spec={"kind": "ALPHANUMERIC", "len": 3},
        to_spec={"kind": "ALPHANUMERIC", "len": 5, "jr": True},
        input_bytes=b"XYZ",
        expected_bytes=b"  XYZ",
        note="Space padding on left due to JUSTIFIED RIGHT",
    ),
    MoveVector(
        id="MV04-justified-right-trunc",
        title="JUSTIFIED RIGHT low-order kept",
        rule_id="RT-CBL-MOVE-ELEMENTARY",
        from_spec={"kind": "ALPHANUMERIC", "len": 5},
        to_spec={"kind": "ALPHANUMERIC", "len": 3, "jr": True},
        input_bytes=b"12345",
        expected_bytes=b"345",
        note="High-order end truncated, low-order kept",
    ),
    MoveVector(
        id="MV05-group-copy-bytes",
        title="Group to group byte copy without conversion",
        rule_id="RT-CBL-MOVE-ELEMENTARY",
        from_spec={"kind": "GROUP", "len": 4},
        to_spec={"kind": "GROUP", "len": 6},
        input_bytes=b"ABCD",
        expected_bytes=b"ABCD  ",
        note="Padded with spaces to target length",
    ),
    MoveVector(
        id="MV06-same-zoned-shape-memcpy",
        title="Same zoned shape copies bytes directly",
        rule_id="RT-CBL-MOVE-SAME-ZONED-SHAPE",
        from_spec={"kind": "NUMERIC_DISPLAY", "digits": 5, "scale": 0, "signed": True, "len": 5},
        to_spec={"kind": "NUMERIC_DISPLAY", "digits": 5, "scale": 0, "signed": True, "len": 5},
        input_bytes=b"12 4K",  # non-digit space and negative overpunch K (-2)
        expected_bytes=b"12 4K",
        note="Non-digit byte travels as-is; sign rewrite never runs (register C11)",
    ),
    MoveVector(
        id="MV07-numeric-to-alnum-unpunch",
        title="Signed zoned to alphanumeric de-punches sign",
        rule_id="RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC",
        from_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 5,
            "scale": 0,
            "signed": True,
            "sign_leading": False,
            "sign_separate": False,
            "len": 5,
        },
        to_spec={"kind": "ALPHANUMERIC", "len": 5},
        input_bytes=b"0001K",  # K = -2
        expected_bytes=b"00012",
        note="Negative overpunch K turned into unsigned digit 2",
    ),
    MoveVector(
        id="MV08-numeric-to-alnum-positive-unpunch",
        title="Positive overpunch to alphanumeric",
        rule_id="RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC",
        from_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 4,
            "scale": 0,
            "signed": True,
            "sign_leading": False,
            "sign_separate": False,
            "len": 4,
        },
        to_spec={"kind": "ALPHANUMERIC", "len": 4},
        input_bytes=b"012B",  # B = +2
        expected_bytes=b"0122",
        note="Positive overpunch B turned into unsigned digit 2",
    ),
    MoveVector(
        id="MV09-numeric-separate-sign-dropped",
        title="Separate sign dropped when moving to alphanumeric",
        rule_id="RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC",
        from_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 4,
            "scale": 0,
            "signed": True,
            "sign_leading": True,
            "sign_separate": True,
            "len": 5,
        },
        to_spec={"kind": "ALPHANUMERIC", "len": 4},
        input_bytes=b"-1234",
        expected_bytes=b"1234",
        note="Leading separate sign dropped",
    ),
    MoveVector(
        id="MV10-alnum-to-numeric-display",
        title="Alphanumeric to zoned display with leading spaces skipped",
        rule_id="RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC",
        from_spec={"kind": "ALPHANUMERIC", "len": 6},
        to_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 4,
            "scale": 0,
            "signed": False,
            "len": 4,
        },
        input_bytes=b"   42 ",
        expected_bytes=b"0042",
        note="Leading spaces skipped, digits zero padded",
    ),
    MoveVector(
        id="MV11-alnum-to-numeric-invalid-char",
        title="Alphanumeric to numeric with stray char becomes 0",
        rule_id="RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC",
        from_spec={"kind": "ALPHANUMERIC", "len": 5},
        to_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 4,
            "scale": 0,
            "signed": False,
            "len": 4,
        },
        input_bytes=b"12X34",
        expected_bytes=b"0000",
        note="Stray non-digit before field full leaves destination ZERO",
    ),
    MoveVector(
        id="MV12-deedit-currency-comma",
        title="De-editing numeric edited with currency and comma",
        rule_id="RT-CBL-MOVE-DEEDIT",
        from_spec={"kind": "NUMERIC_EDITED", "digits": 6, "scale": 2, "len": 9},
        to_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 6,
            "scale": 2,
            "signed": False,
            "len": 6,
        },
        input_bytes=b"$1,234.56",
        expected_bytes=b"123456",
        note="Currency symbol and separators stripped, digits extracted",
    ),
    MoveVector(
        id="MV13-deedit-negative-cr",
        title="De-editing negative edited with CR",
        rule_id="RT-CBL-MOVE-DEEDIT",
        from_spec={"kind": "NUMERIC_EDITED", "digits": 4, "scale": 0, "len": 6},
        to_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 4,
            "scale": 0,
            "signed": True,
            "sign_leading": False,
            "sign_separate": False,
            "len": 4,
        },
        input_bytes=b"1234CR",
        expected_bytes=b"123M",  # 4 with negative overpunch is M
        note="CR sets negative sign, overpunched into last digit",
    ),
    MoveVector(
        id="MV14-all-literal-to-alnum",
        title="MOVE ALL literal to alphanumeric repeats pattern",
        rule_id="RT-CBL-MOVE-ALL-LITERAL",
        from_spec={"kind": "ALL_LITERAL", "pattern": "AB"},
        to_spec={"kind": "ALPHANUMERIC", "len": 5},
        input_bytes=b"AB",
        expected_bytes=b"ABABA",
        note="Pattern repeated from left edge",
    ),
    MoveVector(
        id="MV15-all-literal-to-numeric",
        title="MOVE ALL literal to numeric ends at right edge",
        rule_id="RT-CBL-MOVE-ALL-LITERAL",
        from_spec={"kind": "ALL_LITERAL", "pattern": "12"},
        to_spec={
            "kind": "NUMERIC_DISPLAY",
            "digits": 5,
            "scale": 0,
            "signed": False,
            "len": 5,
        },
        input_bytes=b"12",
        expected_bytes=b"21212",
        note="GnuCOBOL/IBM aligns ALL pattern at right edge for numeric target",
    ),
]
