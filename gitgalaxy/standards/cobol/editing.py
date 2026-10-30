# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL Numeric Editing rule family as declarative data (#4712, epic #4710).

Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
Chapters:
  - "PICTURE clause" (Editing rules, Simple insertion, Special insertion,
    Fixed insertion, Floating insertion, Zero suppression and replacement)
  - "SPECIAL-NAMES paragraph" (CURRENCY SIGN clause, DECIMAL-POINT IS COMMA clause)

Defines:
  EDITING_SYMBOLS        The editing symbols, categories, and behaviors
  EDITING_RULES          Catalogue rule metadata for the 5 RT-EDIT-* rules
  EDITING_VECTORS        Deterministic test vectors executed directly in CI
  execute_editing        Pure-Python simulation of COBOL numeric editing
  execute_shape          Pure-Python simulation of PICTURE shape calculation
  expand_picture         PICTURE expansion with repetition removal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# -------------------------------------------------------------------------------------- categories and symbols

EDIT_CATEGORY_SIMPLE_INSERTION = 0
EDIT_CATEGORY_SPECIAL_INSERTION = 1
EDIT_CATEGORY_FIXED_INSERTION = 2
EDIT_CATEGORY_FLOATING_INSERTION = 3
EDIT_CATEGORY_ZERO_SUPPRESSION = 4
EDIT_CATEGORY_DIGIT = 5
EDIT_CATEGORY_IMPLICIT = 6

EDIT_CATEGORY_NAMES = {
    EDIT_CATEGORY_SIMPLE_INSERTION: "SIMPLE_INSERTION",
    EDIT_CATEGORY_SPECIAL_INSERTION: "SPECIAL_INSERTION",
    EDIT_CATEGORY_FIXED_INSERTION: "FIXED_INSERTION",
    EDIT_CATEGORY_FLOATING_INSERTION: "FLOATING_INSERTION",
    EDIT_CATEGORY_ZERO_SUPPRESSION: "ZERO_SUPPRESSION",
    EDIT_CATEGORY_DIGIT: "DIGIT",
    EDIT_CATEGORY_IMPLICIT: "IMPLICIT",
}

EDITING_SYMBOLS_STRING = "9Z*.,+-CRDBV0/$"


@dataclass(frozen=True)
class EditingSymbolSpec:
    symbol: str
    category: int
    occupies_position: bool
    description: str
    ibm_clause: str


EDITING_SYMBOLS: dict[str, EditingSymbolSpec] = {
    "9": EditingSymbolSpec(
        "9", EDIT_CATEGORY_DIGIT, True, "Numeric digit position, always displayed as digit", "PICTURE 9"
    ),
    "Z": EditingSymbolSpec(
        "Z", EDIT_CATEGORY_ZERO_SUPPRESSION, True, "Leading zero suppression replaced by space", "PICTURE Z"
    ),
    "*": EditingSymbolSpec(
        "*", EDIT_CATEGORY_ZERO_SUPPRESSION, True, "Check protection zero suppression replaced by asterisk", "PICTURE *"
    ),
    ".": EditingSymbolSpec(
        ".", EDIT_CATEGORY_SPECIAL_INSERTION, True, "Actual decimal point; cancels zero suppression", "PICTURE ."
    ),
    ",": EditingSymbolSpec(
        ",",
        EDIT_CATEGORY_SIMPLE_INSERTION,
        True,
        "Comma simple insertion; suppressed if preceding positions zero-suppressed",
        "PICTURE ,",
    ),
    "+": EditingSymbolSpec(
        "+", EDIT_CATEGORY_FIXED_INSERTION, True, "Fixed or floating plus sign (+ for >= 0, - for < 0)", "PICTURE +"
    ),
    "-": EditingSymbolSpec(
        "-",
        EDIT_CATEGORY_FIXED_INSERTION,
        True,
        "Fixed or floating minus sign (space for >= 0, - for < 0)",
        "PICTURE -",
    ),
    "CR": EditingSymbolSpec(
        "CR", EDIT_CATEGORY_FIXED_INSERTION, True, "Credit sign (CR if < 0, 2 spaces if >= 0)", "PICTURE CR"
    ),
    "DB": EditingSymbolSpec(
        "DB", EDIT_CATEGORY_FIXED_INSERTION, True, "Debit sign (DB if < 0, 2 spaces if >= 0)", "PICTURE DB"
    ),
    "$": EditingSymbolSpec(
        "$",
        EDIT_CATEGORY_FIXED_INSERTION,
        True,
        "Fixed or floating currency symbol replaced by currency string",
        "PICTURE $",
    ),
    "B": EditingSymbolSpec("B", EDIT_CATEGORY_SIMPLE_INSERTION, True, "Blank insertion (space)", "PICTURE B"),
    "0": EditingSymbolSpec("0", EDIT_CATEGORY_SIMPLE_INSERTION, True, "Zero insertion (0 character)", "PICTURE 0"),
    "/": EditingSymbolSpec("/", EDIT_CATEGORY_SIMPLE_INSERTION, True, "Slash / stroke insertion", "PICTURE /"),
    "V": EditingSymbolSpec(
        "V", EDIT_CATEGORY_IMPLICIT, False, "Assumed decimal point (occupies no character position)", "PICTURE V"
    ),
}


# -------------------------------------------------------------------------------------- rule catalogue metadata


@dataclass(frozen=True)
class EditingRuleMeta:
    id: str
    title: str
    status: str  # MATCHED / DIFFERS / REFUSED / ASSUMED
    ibm: dict[str, str] | None
    ibm_note: str | None = None
    options: list[str] = field(default_factory=list)
    register: list[str] = field(default_factory=list)
    description: str = ""


EDITING_RULES: dict[str, EditingRuleMeta] = {
    "RT-EDIT-NUMERIC-EDITING": EditingRuleMeta(
        id="RT-EDIT-NUMERIC-EDITING",
        title="A number through a numeric-edited PICTURE: 9, Z / * zero suppression, the . and , insertion characters, fixed + / -, CR / DB, B 0 /, and a zero value of an all-suppression PICTURE",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "PICTURE clause: editing rules"},
        options=["DECIMAL-POINT-COMMA"],
        description="Core numeric editing with digit placement, simple insertion, fixed sign indicators, and Z/* suppression.",
    ),
    "RT-EDIT-FLOATING-INSERTION": EditingRuleMeta(
        id="RT-EDIT-FLOATING-INSERTION",
        title="A floating insertion string ($$$,$$9.99, +++9, ---9) floats the sign or currency string to just left of the first significant digit; every digit position in the string and a zero value: all spaces",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "PICTURE clause: floating insertion editing"},
        options=[],
        description="Floating currency or sign strings float immediately preceding the first significant digit or decimal point.",
    ),
    "RT-EDIT-CURRENCY-SIGN": EditingRuleMeta(
        id="RT-EDIT-CURRENCY-SIGN",
        title="The currency symbol ($ or the declared PICTURE SYMBOL) stands for the program's CURRENCY SIGN string",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "SPECIAL-NAMES paragraph: CURRENCY SIGN clause"},
        options=["CURRENCY-SIGN"],
        description="The currency symbol ($ or custom declared PICTURE symbol) is substituted by the configured CURRENCY string.",
    ),
    "RT-EDIT-NONDIGIT-SENDER": EditingRuleMeta(
        id="RT-EDIT-NONDIGIT-SENDER",
        title="A zoned sender holding non-digits: its bytes are the PICTURE's digits as they are, only a '0' suppressed",
        status="DIFFERS",
        ibm=None,
        ibm_note="IBM documents no result for non-digit data in a numeric item; the oracle's (GnuCOBOL 3.1.2) rule is modelled (cob_move_display_to_edited)",
        register=["C11"],
        options=[],
        description="When non-digit data from a zoned sender is moved to edited, raw bytes are placed directly into digit slots.",
    ),
    "RT-EDIT-PICTURE-SHAPE": EditingRuleMeta(
        id="RT-EDIT-PICTURE-SHAPE",
        title="An edit PICTURE's integer and decimal digit positions (floating insertion included); under DECIMAL-POINT IS COMMA the , is its decimal point",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "PICTURE clause"},
        options=["DECIMAL-POINT-COMMA"],
        description="Calculates integer and decimal digit positions for an edit PICTURE, accounting for floating strings and DECIMAL-POINT IS COMMA.",
    ),
}


# -------------------------------------------------------------------------------------- deterministic test vectors


@dataclass(frozen=True)
class EditingVector:
    id: str
    rule_id: str
    picture: str
    value: Decimal | None
    expected: str
    decimal_comma: bool = False
    currency: str | None = None
    raw_digits: str | None = None
    negative: bool = False
    title: str = ""
    note: str = ""


EDITING_VECTORS: list[EditingVector] = [
    # RT-EDIT-NUMERIC-EDITING
    EditingVector(
        id="VEC-EDIT-SIMPLE-COMMA",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="99,999",
        value=Decimal("12345"),
        expected="12,345",
        title="Simple comma insertion",
    ),
    EditingVector(
        id="VEC-EDIT-SIMPLE-BLANK",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999B999",
        value=Decimal("123456"),
        expected="123 456",
        title="Blank B simple insertion",
    ),
    EditingVector(
        id="VEC-EDIT-SIMPLE-ZERO",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999000",
        value=Decimal("123"),
        expected="123000",
        title="Zero 0 simple insertion",
    ),
    EditingVector(
        id="VEC-EDIT-SIMPLE-SLASH",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="99/99/99",
        value=Decimal("261030"),
        expected="26/10/30",
        title="Slash / simple insertion",
    ),
    EditingVector(
        id="VEC-EDIT-Z-SUPPRESS-LEADING",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="ZZ,ZZ9.99",
        value=Decimal("123.45"),
        expected="   123.45",
        title="Z zero suppression with leading spaces",
    ),
    EditingVector(
        id="VEC-EDIT-Z-SUPPRESS-ZERO-DECIMAL",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="ZZ,ZZ9.99",
        value=Decimal("0.00"),
        expected="     0.00",
        title="Z zero suppression preserving digit 9 before decimal",
    ),
    EditingVector(
        id="VEC-EDIT-Z-SUPPRESS-ALL-ZERO",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="ZZ,ZZZ.ZZ",
        value=Decimal("0.00"),
        expected="      .00",
        title="All-Z suppression with zero value; decimal point cancels suppression",
    ),
    EditingVector(
        id="VEC-EDIT-STAR-CHECK-PROTECT",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="**,**9.99",
        value=Decimal("123.45"),
        expected="***123.45",
        title="Asterisk check protect zero suppression",
    ),
    EditingVector(
        id="VEC-EDIT-STAR-ALL-ZERO",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="**,***.**",
        value=Decimal("0.00"),
        expected="******.00",
        title="All-* check protect with zero value; decimal point cancels suppression",
    ),
    EditingVector(
        id="VEC-EDIT-FIXED-PLUS-POS",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="+999.99",
        value=Decimal("12.34"),
        expected="+012.34",
        title="Fixed plus sign with positive value",
    ),
    EditingVector(
        id="VEC-EDIT-FIXED-PLUS-NEG",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="+999.99",
        value=Decimal("-12.34"),
        expected="-012.34",
        title="Fixed plus sign with negative value",
    ),
    EditingVector(
        id="VEC-EDIT-FIXED-MINUS-POS",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="-999.99",
        value=Decimal("12.34"),
        expected=" 012.34",
        title="Fixed minus sign with positive value displays space",
    ),
    EditingVector(
        id="VEC-EDIT-FIXED-MINUS-NEG",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="-999.99",
        value=Decimal("-12.34"),
        expected="-012.34",
        title="Fixed minus sign with negative value displays minus",
    ),
    EditingVector(
        id="VEC-EDIT-TRAILING-SIGN-NEG",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999.99-",
        value=Decimal("-5.50"),
        expected="005.50-",
        title="Trailing minus sign with negative value",
    ),
    EditingVector(
        id="VEC-EDIT-TRAILING-SIGN-POS",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999.99+",
        value=Decimal("5.50"),
        expected="005.50+",
        title="Trailing plus sign with positive value",
    ),
    EditingVector(
        id="VEC-EDIT-CREDIT-NEG",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999.99CR",
        value=Decimal("-150.00"),
        expected="150.00CR",
        title="Credit CR sign with negative value",
    ),
    EditingVector(
        id="VEC-EDIT-CREDIT-POS",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999.99CR",
        value=Decimal("150.00"),
        expected="150.00  ",
        title="Credit CR sign with positive value displays two spaces",
    ),
    EditingVector(
        id="VEC-EDIT-DEBIT-NEG",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999.99DB",
        value=Decimal("-75.25"),
        expected="075.25DB",
        title="Debit DB sign with negative value",
    ),
    EditingVector(
        id="VEC-EDIT-DEBIT-POS",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="999.99DB",
        value=Decimal("75.25"),
        expected="075.25  ",
        title="Debit DB sign with positive value displays two spaces",
    ),
    # RT-EDIT-FLOATING-INSERTION
    EditingVector(
        id="VEC-EDIT-FLOAT-DOLLAR",
        rule_id="RT-EDIT-FLOATING-INSERTION",
        picture="$$$,$$9.99",
        value=Decimal("123.45"),
        expected="   $123.45",
        title="Floating dollar sign string",
    ),
    EditingVector(
        id="VEC-EDIT-FLOAT-DOLLAR-SMALL",
        rule_id="RT-EDIT-FLOATING-INSERTION",
        picture="$$$,$$9.99",
        value=Decimal("0.05"),
        expected="     $0.05",
        title="Floating dollar sign floating to just left of 9",
    ),
    EditingVector(
        id="VEC-EDIT-FLOAT-DOLLAR-ALL-ZERO",
        rule_id="RT-EDIT-FLOATING-INSERTION",
        picture="$$$,$$$.$$",
        value=Decimal("0.00"),
        expected="          ",
        title="All-floating dollar sign string with zero value edits to all spaces",
    ),
    EditingVector(
        id="VEC-EDIT-FLOAT-PLUS-POS",
        rule_id="RT-EDIT-FLOATING-INSERTION",
        picture="+++,++9.99",
        value=Decimal("42.00"),
        expected="    +42.00",
        title="Floating plus sign with positive value",
    ),
    EditingVector(
        id="VEC-EDIT-FLOAT-PLUS-NEG",
        rule_id="RT-EDIT-FLOATING-INSERTION",
        picture="+++,++9.99",
        value=Decimal("-42.00"),
        expected="    -42.00",
        title="Floating plus sign with negative value",
    ),
    EditingVector(
        id="VEC-EDIT-FLOAT-MINUS-POS",
        rule_id="RT-EDIT-FLOATING-INSERTION",
        picture="---,--9.99",
        value=Decimal("42.00"),
        expected="     42.00",
        title="Floating minus sign with positive value blanks sign",
    ),
    EditingVector(
        id="VEC-EDIT-FLOAT-MINUS-NEG",
        rule_id="RT-EDIT-FLOATING-INSERTION",
        picture="---,--9.99",
        value=Decimal("-42.00"),
        expected="    -42.00",
        title="Floating minus sign with negative value",
    ),
    # RT-EDIT-CURRENCY-SIGN
    EditingVector(
        id="VEC-EDIT-CURRENCY-EUR",
        rule_id="RT-EDIT-CURRENCY-SIGN",
        picture="$$$,$$9.99",
        value=Decimal("10.50"),
        expected="    EUR 10.50",
        currency="EUR ",
        title="Custom currency string EUR",
    ),
    EditingVector(
        id="VEC-EDIT-CURRENCY-INR",
        rule_id="RT-EDIT-CURRENCY-SIGN",
        picture="$999.99",
        value=Decimal("25.00"),
        expected="Rs 025.00",
        currency="Rs ",
        title="Custom currency string Rs",
    ),
    # RT-EDIT-NONDIGIT-SENDER
    EditingVector(
        id="VEC-EDIT-NONDIGIT-RAW",
        rule_id="RT-EDIT-NONDIGIT-SENDER",
        picture="ZZ,ZZ9.99",
        value=Decimal("0"),
        expected="AB,CDE.FG",
        raw_digits="ABCDEFG",
        title="Non-digit characters from zoned sender preserved in digit positions",
    ),
    # RT-EDIT-PICTURE-SHAPE
    EditingVector(
        id="VEC-EDIT-SHAPE-BASIC",
        rule_id="RT-EDIT-PICTURE-SHAPE",
        picture="ZZ,ZZ9.99",
        value=Decimal("123.45"),
        expected="   123.45",
        title="Picture shape calculation: 5 integer digits, 2 decimals",
        note="shape=(5, 2)",
    ),
    EditingVector(
        id="VEC-EDIT-SHAPE-EXPAND",
        rule_id="RT-EDIT-PICTURE-SHAPE",
        picture="Z(4)9(2).9(3)",
        value=Decimal("12345.678"),
        expected=" 12345.678",
        title="Expanded repeat count picture shape: 6 integer digits, 3 decimals",
        note="shape=(6, 3)",
    ),
    EditingVector(
        id="VEC-EDIT-DECIMAL-COMMA",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="ZZ.ZZ9,99",
        value=Decimal("1234.56"),
        expected=" 1.234,56",
        decimal_comma=True,
        title="DECIMAL-POINT IS COMMA swaps comma and period",
    ),
    EditingVector(
        id="VEC-EDIT-IMPLICIT-V",
        rule_id="RT-EDIT-NUMERIC-EDITING",
        picture="ZZZV99",
        value=Decimal("5.25"),
        expected="  525",
        title="Assumed decimal point V occupies no character position",
    ),
]


# -------------------------------------------------------------------------------------- pure-Python simulation


def expand_picture(pic: str) -> str:
    """Expand repeat counts in PICTURE string, e.g. Z(3)9(2) -> ZZZ99."""
    ex: list[str] = []
    i = 0
    while i < len(pic):
        c = pic[i].upper()
        if c == "(" and ex:
            j = pic.find(")", i)
            n = int(pic[i + 1 : j].strip())
            r = ex[-1]
            ex.extend([r] * (n - 1))
            i = j + 1
        elif c not in ("S", "P"):
            ex.append(c)
            i += 1
        else:
            i += 1
    return "".join(ex)


def execute_shape(pic: str, decimal_comma: bool = False) -> tuple[int, int]:
    """Calculate integer and decimal digit positions for an edit PICTURE."""
    p = expand_picture(pic)
    symbol = "$"
    for ch in p:
        if ch not in EDITING_SYMBOLS_STRING:
            symbol = ch
            break
    p = p.replace(symbol, "$")
    dec_idx = p.find("V")
    if dec_idx == -1:
        dec_idx = p.find("," if decimal_comma else ".")
    if dec_idx == -1:
        dec_idx = len(p)

    floating = None
    float_start = -1
    float_end = -1
    for f in ("$", "+", "-"):
        a = p.find(f)
        if a == -1:
            continue
        b = a
        n = 1
        for idx in range(a + 1, len(p)):
            c = p[idx]
            if c == f:
                b = idx
                n += 1
            elif c not in ",.B0/":
                break
        if n >= 2:
            floating = f
            float_start = a
            float_end = b
            break

    ints = 0
    decs = 0
    for idx, c in enumerate(p):
        float_digit = floating is not None and c == floating and idx > float_start and idx <= float_end
        if c in ("9", "Z", "*") or float_digit:
            if idx > dec_idx:
                decs += 1
            else:
                ints += 1
    return ints, decs


def execute_editing(
    pic: str,
    value: Decimal | None,
    decimal_comma: bool = False,
    currency: str | None = None,
    raw_digits: str | None = None,
    negative: bool = False,
) -> str:
    """Pure-Python execution of COBOL numeric-edited formatting matching Editing.java."""
    p = expand_picture(pic)
    if value is None:
        import re

        return re.sub(r"[9Z*]", "0", p)

    symbol = "$"
    for ch in p:
        if ch not in EDITING_SYMBOLS_STRING:
            symbol = ch
            break
    cur = currency if currency is not None else symbol
    p = p.replace(symbol, "$")

    neg = negative if raw_digits is not None else (value < 0)
    abs_val = abs(value)

    dec_char = "," if decimal_comma else "."
    dec_idx = p.find("V")
    if dec_idx == -1:
        dec_idx = p.find(dec_char)
    if dec_idx == -1:
        dec_idx = len(p)

    floating = None
    float_start = -1
    float_end = -1
    for f in ("$", "+", "-"):
        a = p.find(f)
        if a == -1:
            continue
        b = a
        n = 1
        for idx in range(a + 1, len(p)):
            c = p[idx]
            if c == f:
                b = idx
                n += 1
            elif c not in ",.B0/":
                break
        if n >= 2:
            floating = f
            float_start = a
            float_end = b
            break

    all_floating = floating is not None
    digits = 0
    scale = 0
    for idx, c in enumerate(p):
        float_digit = floating is not None and c == floating and idx > float_start and idx <= float_end
        if c in ("9", "Z", "*") or float_digit:
            digits += 1
            if idx > dec_idx:
                scale += 1
            if not float_digit:
                all_floating = False

    if raw_digits is not None:
        raw = raw_digits
    else:
        # Quantize to scale
        scaled = abs_val.quantize(Decimal(10) ** -scale, rounding=ROUND_HALF_UP)
        raw = str(scaled).replace(".", "")
    while len(raw) < digits:
        raw = "0" + raw
    if len(raw) > digits:
        raw = raw[-digits:]

    cells: list[str] = [""] * len(p)
    float_text = cur if floating == "$" else ("-" if neg else "+") if floating == "+" else ("-" if neg else " ")
    float_suppression = floating is not None
    float_at = -1
    raw_idx = 0
    zero_suppression = True

    i = 0
    while i < len(p):
        c = p[i]
        if float_suppression and i > float_end:
            cells[float_at] = float_text
            float_suppression = False

        if floating is not None and i >= float_start and i <= float_end:
            if i == float_start:
                cells[i] = " "
                float_at = i
            elif c == floating:
                d = raw[raw_idx]
                raw_idx += 1
                if float_suppression and d == "0" and i < dec_idx:
                    cells[i] = " "
                    float_at = i
                else:
                    if float_suppression:
                        cells[float_at] = float_text
                    float_suppression = False
                    zero_suppression = False
                    cells[i] = d
            elif c == dec_char and i == dec_idx:
                if float_suppression:
                    cells[float_at] = float_text
                float_suppression = False
                zero_suppression = False
                cells[i] = c
            elif float_suppression:
                cells[i] = " "
                float_at = i
            else:
                cells[i] = " " if c == "B" else c
            i += 1
            continue

        if c in ("9", "Z", "*"):
            d = raw[raw_idx]
            raw_idx += 1
            if c == "Z":
                if d == "0" and zero_suppression:
                    cells[i] = " "
                else:
                    cells[i] = d
                    zero_suppression = False
            elif c == "*":
                if d == "0" and zero_suppression:
                    cells[i] = "*"
                else:
                    cells[i] = d
                    zero_suppression = False
            else:
                cells[i] = d
                zero_suppression = False
        elif c in (".", ","):
            if zero_suppression and ("Z" in p or "*" in p):
                if c == dec_char:
                    cells[i] = c
                    zero_suppression = False
                else:
                    cells[i] = "*" if "*" in p else " "
            else:
                cells[i] = c
        elif c == "-":
            cells[i] = "-" if neg else " "
        elif c == "+":
            cells[i] = "-" if neg else "+"
        elif c == "C" and i + 1 < len(p) and p[i + 1] == "R":
            cells[i] = "CR" if neg else "  "
            cells[i + 1] = ""
            i += 1
        elif c == "D" and i + 1 < len(p) and p[i + 1] == "B":
            cells[i] = "DB" if neg else "  "
            cells[i + 1] = ""
            i += 1
        elif c == "$":
            cells[i] = cur
        elif c == "B":
            cells[i] = " "
        elif c in ("0", "/"):
            if zero_suppression:
                cells[i] = "*" if "*" in p else " "
            else:
                cells[i] = c
        elif c == "V":
            cells[i] = ""
        else:
            cells[i] = c
        i += 1

    if float_suppression and float_at >= 0:
        cells[float_at] = float_text
    out = "".join(cells)
    if all_floating and all(ch == "0" for ch in raw):
        return " " * len(out)
    return out
