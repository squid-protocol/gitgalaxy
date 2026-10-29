# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL String Manipulation rule family: STRING, UNSTRING, INSPECT (#4712, epic #4710).

Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
Chapters:
  - "STRING statement" (DELIMITED BY, INTO, WITH POINTER, ON OVERFLOW)
  - "UNSTRING statement" (DELIMITED BY ALL, INTO, DELIMITER IN, COUNT IN, WITH POINTER, TALLYING IN, ON OVERFLOW)
  - "INSPECT statement" (TALLYING, REPLACING, CONVERTING, BEFORE/AFTER INITIAL)
  - "Common phrases and concepts for statements" (ON OVERFLOW and NOT ON OVERFLOW)
Programming Guide (SC26-4940-06):
  - "ZONEDATA (INVDATA in 6.4)" (dirty pointer and counter validation)

Defines:
  INSPECT_MODES        The 4 evaluation modes for INSPECT (CHARACTERS, ALL, LEADING, FIRST)
  PHRASE_TYPES         The 3 phrase types for INSPECT (TALLYING, REPLACING, CONVERTING)
  STRING_RULES         Catalogue rule metadata for the 4 string manipulation rules
  STRING_VECTORS       Deterministic test vectors executed directly in CI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# -------------------------------------------------------------------------------------- statement & phrase types

STATEMENT_STRING = 0
STATEMENT_UNSTRING = 1
STATEMENT_INSPECT = 2

INSPECT_CHARACTERS = 0
INSPECT_ALL = 1
INSPECT_LEADING = 2
INSPECT_FIRST = 3

PHRASE_TALLYING = 0
PHRASE_REPLACING = 1
PHRASE_CONVERTING = 2


@dataclass(frozen=True)
class InspectModeSpec:
    mode_id: int
    name: str
    description: str
    ibm_clause: str


INSPECT_MODES: dict[int, InspectModeSpec] = {
    INSPECT_CHARACTERS: InspectModeSpec(
        mode_id=INSPECT_CHARACTERS,
        name="CHARACTERS",
        description="Every character position within the specified bounds is examined.",
        ibm_clause="FOR CHARACTERS / CHARACTERS BY",
    ),
    INSPECT_ALL: InspectModeSpec(
        mode_id=INSPECT_ALL,
        name="ALL",
        description="All non-overlapping occurrences of the pattern are matched.",
        ibm_clause="FOR ALL pattern / ALL pattern BY by",
    ),
    INSPECT_LEADING: InspectModeSpec(
        mode_id=INSPECT_LEADING,
        name="LEADING",
        description="Matches occurrences of the pattern from the leftmost character until mismatch.",
        ibm_clause="FOR LEADING pattern / LEADING pattern BY by",
    ),
    INSPECT_FIRST: InspectModeSpec(
        mode_id=INSPECT_FIRST,
        name="FIRST",
        description="Only the first occurrence of the pattern is matched and replaced.",
        ibm_clause="FIRST pattern BY by",
    ),
}

INSPECT_MODE_BY_NAME = {m.name: m for m in INSPECT_MODES.values()}


@dataclass(frozen=True)
class PhraseTypeSpec:
    type_id: int
    name: str
    description: str


PHRASE_TYPES: dict[int, PhraseTypeSpec] = {
    PHRASE_TALLYING: PhraseTypeSpec(
        type_id=PHRASE_TALLYING,
        name="TALLYING",
        description="Counts occurrences of matched character patterns into a numeric counter.",
    ),
    PHRASE_REPLACING: PhraseTypeSpec(
        type_id=PHRASE_REPLACING,
        name="REPLACING",
        description="Substitutes matched character patterns with replacement characters.",
    ),
    PHRASE_CONVERTING: PhraseTypeSpec(
        type_id=PHRASE_CONVERTING,
        name="CONVERTING",
        description="Translates characters based on a 1:1 mapped alphabet substitution table.",
    ),
}


# -------------------------------------------------------------------------------------- rule catalogue metadata


@dataclass(frozen=True)
class StringRuleMeta:
    id: str
    title: str
    status: str  # MATCHED / DIFFERS / REFUSED / ASSUMED
    ibm: dict[str, str] | None
    ibm_note: str | None = None
    options: list[str] = field(default_factory=list)
    register: list[str] = field(default_factory=list)
    description: str = ""


STRING_RULES: dict[str, StringRuleMeta] = {
    "RT-CBL-STRING": StringRuleMeta(
        id="RT-CBL-STRING",
        title="STRING ... DELIMITED BY ... INTO ... [WITH POINTER]: bytes transferred in order, the receiver not padded; OVERFLOW when the pointer is outside the receiver or the data does not fit",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "STRING statement"},
        description="Concatenates substrings into receiver without space-padding unwritten positions; overflow on capacity or bounds.",
    ),
    "RT-CBL-UNSTRING": StringRuleMeta(
        id="RT-CBL-UNSTRING",
        title="UNSTRING ... DELIMITED BY ... INTO ... [DELIMITER IN] [COUNT IN] [WITH POINTER] [TALLYING]: the rest to the first INTO with no delimiter; OVERFLOW when the pointer is outside the source or characters remain",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "UNSTRING statement"},
        description="Disassembles source string into receiving fields by delimiter; tracks delimiters, counts, tallying, and overflow.",
    ),
    "RT-CBL-INSPECT": StringRuleMeta(
        id="RT-CBL-INSPECT",
        title="INSPECT TALLYING / REPLACING / CONVERTING with BEFORE / AFTER: the phrases act on the original text, the earlier clause takes the characters, TALLYING and REPLACING are separate passes",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "INSPECT statement"},
        description="Performs pattern tallying, replacement, and character conversion with non-overlapping clause precedence.",
    ),
    "RT-CBL-COUNTER-NONDIGIT-REFUSED": StringRuleMeta(
        id="RT-CBL-COUNTER-NONDIGIT-REFUSED",
        title="A STRING / UNSTRING POINTER, an UNSTRING TALLYING IN item and an INSPECT TALLYING counter are read before they store: a zoned one holding a non-digit is refused by name",
        status="REFUSED",
        ibm={"doc": "cobol-pg", "section": "ZONEDATA (replaced by INVDATA in 6.4)"},
        ibm_note="IBM documents no result (ZONEDATA(PFD) assumes valid zone bits); the same ground as the receiver of ADD",
        options=["ZONEDATA"],
        register=["C11"],
        description="A pointer or tallying item with non-digit zoned representation is refused by name before reading.",
    ),
}


# -------------------------------------------------------------------------------------- deterministic test vectors


@dataclass(frozen=True)
class StringVector:
    id: str
    title: str
    rule_id: str
    statement: str
    source_text: str
    pointer_init: int | None
    options: dict[str, Any]
    expected_output: str
    expected_pointer: int | None
    expected_overflow: bool
    note: str = ""


STRING_VECTORS: list[StringVector] = [
    StringVector(
        id="ST01-string-delimited-by-size",
        title="STRING two senders delimited by size into receiver",
        rule_id="RT-CBL-STRING",
        statement="STRING",
        source_text="INITIAL   ",
        pointer_init=None,
        options={
            "parts": [("HELLO", None), ("WORLD", None)],
            "receiver_len": 10,
        },
        expected_output="HELLOWORLD",
        expected_pointer=None,
        expected_overflow=False,
        note="Both senders delimited by size fit receiver exactly without overflow",
    ),
    StringVector(
        id="ST02-string-delimited-by-space",
        title="STRING sender delimited by space stops transferring at first space",
        rule_id="RT-CBL-STRING",
        statement="STRING",
        source_text="ZZZZZZZZZZ",
        pointer_init=1,
        options={
            "parts": [("FIRST SECOND", " "), ("THIRD", None)],
            "receiver_len": 10,
        },
        expected_output="FIRSTTHIRD",
        expected_pointer=11,
        expected_overflow=False,
        note="Stops 'FIRST SECOND' at space, leaving 'FIRST', then appends 'THIRD'",
    ),
    StringVector(
        id="ST03-string-receiver-no-pad",
        title="STRING does not space-pad unreached receiver character positions",
        rule_id="RT-CBL-STRING",
        statement="STRING",
        source_text="ABCDEFGHIJ",
        pointer_init=1,
        options={
            "parts": [("123", None)],
            "receiver_len": 10,
        },
        expected_output="123DEFGHIJ",
        expected_pointer=4,
        expected_overflow=False,
        note="Only first 3 bytes modified; positions 4-10 retain original contents",
    ),
    StringVector(
        id="ST04-string-pointer-offset",
        title="STRING with pointer offset starts transfer at pointer position",
        rule_id="RT-CBL-STRING",
        statement="STRING",
        source_text="HELLO.....",
        pointer_init=6,
        options={
            "parts": [("WORLD", None)],
            "receiver_len": 10,
        },
        expected_output="HELLOWORLD",
        expected_pointer=11,
        expected_overflow=False,
        note="Pointer 6 writes to positions 6..10; updated pointer is 11",
    ),
    StringVector(
        id="ST05-string-overflow-truncated",
        title="STRING with data exceeding receiver capacity stores what fits and raises overflow",
        rule_id="RT-CBL-STRING",
        statement="STRING",
        source_text="..........",
        pointer_init=1,
        options={
            "parts": [("1234567890EXTRA", None)],
            "receiver_len": 10,
        },
        expected_output="1234567890",
        expected_pointer=11,
        expected_overflow=True,
        note="15 bytes into 10-byte receiver fills to capacity and raises overflow",
    ),
    StringVector(
        id="ST06-string-pointer-out-of-bounds",
        title="STRING with initial pointer out of bounds modifies nothing and raises overflow",
        rule_id="RT-CBL-STRING",
        statement="STRING",
        source_text="UNCHANGED.",
        pointer_init=0,  # 1-based indexing in COBOL: 0 is invalid
        options={
            "parts": [("DATA", None)],
            "receiver_len": 10,
        },
        expected_output="UNCHANGED.",
        expected_pointer=0,
        expected_overflow=True,
        note="Pointer < 1 immediately sets OVERFLOW with no bytes written",
    ),
    StringVector(
        id="ST07-unstring-basic-delimited",
        title="UNSTRING disassembles comma-delimited tokens into receiving fields",
        rule_id="RT-CBL-UNSTRING",
        statement="UNSTRING",
        source_text="ALPHA,BETA,GAMMA",
        pointer_init=1,
        options={
            "delims": [(",", False)],
            "intos": [5, 5, 5],
        },
        expected_output="ALPHA|BETA |GAMMA",
        expected_pointer=17,
        expected_overflow=False,
        note="Extracts three tokens padded with spaces into each receiving field",
    ),
    StringVector(
        id="ST08-unstring-delimited-by-all",
        title="UNSTRING DELIMITED BY ALL treats contiguous delimiters as one",
        rule_id="RT-CBL-UNSTRING",
        statement="UNSTRING",
        source_text="ONE    TWO   THREE",
        pointer_init=1,
        options={
            "delims": [(" ", True)],
            "intos": [5, 5, 5],
        },
        expected_output="ONE  |TWO  |THREE",
        expected_pointer=19,
        expected_overflow=False,
        note="Contiguous spaces collapsed into single delimiter step",
    ),
    StringVector(
        id="ST09-unstring-overflow-unexamined-characters",
        title="UNSTRING with unexamined characters remaining sets overflow",
        rule_id="RT-CBL-UNSTRING",
        statement="UNSTRING",
        source_text="ONE,TWO,THREE,FOUR",
        pointer_init=1,
        options={
            "delims": [(",", False)],
            "intos": [4, 4],  # Only 2 receivers for 4 tokens
        },
        expected_output="ONE |TWO ",
        expected_pointer=9,
        expected_overflow=True,
        note="Receivers exhausted before end of source text raises OVERFLOW",
    ),
    StringVector(
        id="ST10-inspect-tallying-all",
        title="INSPECT TALLYING FOR ALL counts total occurrences of pattern",
        rule_id="RT-CBL-INSPECT",
        statement="INSPECT_TALLY",
        source_text="ABRACADABRA",
        pointer_init=None,
        options={
            "mode": "ALL",
            "pattern": "A",
        },
        expected_output="5",
        expected_pointer=None,
        expected_overflow=False,
        note="Pattern 'A' appears 5 times in 'ABRACADABRA'",
    ),
    StringVector(
        id="ST11-inspect-replacing-all",
        title="INSPECT REPLACING ALL replaces all matching non-overlapping patterns",
        rule_id="RT-CBL-INSPECT",
        statement="INSPECT_REPLACE",
        source_text="BANANA",
        pointer_init=None,
        options={
            "mode": "ALL",
            "pattern": "A",
            "by": "O",
        },
        expected_output="BONONO",
        expected_pointer=None,
        expected_overflow=False,
        note="Every 'A' replaced with 'O'",
    ),
    StringVector(
        id="ST12-inspect-replacing-leading",
        title="INSPECT REPLACING LEADING replaces only prefix matches",
        rule_id="RT-CBL-INSPECT",
        statement="INSPECT_REPLACE",
        source_text="0004500",
        pointer_init=None,
        options={
            "mode": "LEADING",
            "pattern": "0",
            "by": " ",
        },
        expected_output="   4500",
        expected_pointer=None,
        expected_overflow=False,
        note="Leading zeros suppressed to spaces; trailing zeros untouched",
    ),
    StringVector(
        id="ST13-inspect-converting-substitution",
        title="INSPECT CONVERTING maps characters via substitution alphabet",
        rule_id="RT-CBL-INSPECT",
        statement="INSPECT_CONVERT",
        source_text="ABC-123",
        pointer_init=None,
        options={
            "from": "ABC",
            "to": "XYZ",
        },
        expected_output="XYZ-123",
        expected_pointer=None,
        expected_overflow=False,
        note="Translates A->X, B->Y, C->Z",
    ),
    StringVector(
        id="ST14-inspect-before-initial",
        title="INSPECT REPLACING with BEFORE INITIAL acts only on prior text",
        rule_id="RT-CBL-INSPECT",
        statement="INSPECT_REPLACE",
        source_text="A-B-C/D-E-F",
        pointer_init=None,
        options={
            "mode": "ALL",
            "pattern": "-",
            "by": "_",
            "before": "/",
        },
        expected_output="A_B_C/D-E-F",
        expected_pointer=None,
        expected_overflow=False,
        note="Hyphens replaced only before the '/' delimiter",
    ),
]


# -------------------------------------------------------------------------------------- string simulation helpers


def execute_string(
    initial_receiver: str,
    parts: list[tuple[str, str | None]],
    pointer: int | None = None,
) -> tuple[str, int | None, bool]:
    """Simulate COBOL STRING statement semantics."""
    rec = list(initial_receiver)
    rec_len = len(rec)
    off = 0
    if pointer is not None:
        if pointer < 1 or pointer > rec_len:
            return initial_receiver, pointer, True
        off = pointer - 1

    overflow = False
    for text, delim in parts:
        chunk = text
        if delim is not None and delim != "":
            idx = text.find(delim)
            if idx >= 0:
                chunk = text[:idx]

        needed = len(chunk)
        room = rec_len - off
        if needed > room:
            rec[off : off + room] = list(chunk[:room])
            off = rec_len
            overflow = True
            break
        rec[off : off + needed] = list(chunk)
        off += needed

    updated_ptr = (off + 1) if pointer is not None else None
    return "".join(rec), updated_ptr, overflow


def execute_unstring(
    source: str,
    delims: list[tuple[str, bool]],
    into_lens: list[int],
    pointer: int | None = None,
) -> tuple[list[str], int | None, bool]:
    """Simulate COBOL UNSTRING statement semantics."""
    src_len = len(source)
    off = 0
    if pointer is not None:
        if pointer < 1 or pointer > src_len:
            return ["" * n for n in into_lens], pointer, True
        off = pointer - 1

    results: list[str] = []
    for needed_len in into_lens:
        if off >= src_len:
            results.append(" " * needed_len)
            continue

        end = src_len
        delim_len = 0
        hit_delim: tuple[str, bool] | None = None

        # Scan for earliest delimiter match
        for i in range(off, src_len):
            found = False
            for d_text, is_all in delims:
                if d_text and source[i : i + len(d_text)] == d_text:
                    end = i
                    delim_len = len(d_text)
                    hit_delim = (d_text, is_all)
                    found = True
                    break
            if found:
                break

        piece = source[off:end]
        padded = piece[:needed_len] + (" " * max(0, needed_len - len(piece)))
        results.append(padded)

        off = end + delim_len
        if hit_delim is not None and hit_delim[1]:
            d_pat = hit_delim[0]
            while off + len(d_pat) <= src_len and source[off : off + len(d_pat)] == d_pat:
                off += len(d_pat)

    overflow = off < src_len
    updated_ptr = (off + 1) if pointer is not None else None
    return results, updated_ptr, overflow
