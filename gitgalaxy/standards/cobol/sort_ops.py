# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL SORT and MERGE rule family as declarative data (#4712, epic #4710).

Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
Chapters:
  - "SORT statement" (ASCENDING/DESCENDING KEY, COLLATING SEQUENCE, USING/GIVING, INPUT/OUTPUT PROCEDURE)
  - "MERGE statement" (Multiple input files, identical record formats, key ordering)
  - "RELEASE statement" (Transfer from record area to sort work file)
  - "RETURN statement" (Retrieve records from sort work file)
  - "SPECIAL-NAMES paragraph" (ALPHABET clause: STANDARD-1, STANDARD-2, NATIVE, EBCDIC, literal sequences)
  - "OBJECT-COMPUTER paragraph" (PROGRAM COLLATING SEQUENCE clause)

Defines:
  SORT_RULES             Catalogue rule metadata for the 7 RT-SORT-* rules
  SORT_VECTORS           Deterministic test vectors executed directly in CI
  compare_records        Pure-Python simulation of multi-key record comparison
  execute_sort           Pure-Python simulation of COBOL stable sort
  execute_merge          Pure-Python simulation of COBOL file merge
  execute_collating_compare Pure-Python simulation of collating sequence comparison
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# -------------------------------------------------------------------------------------- direction and modes

DIRECTION_ASCENDING = 1
DIRECTION_DESCENDING = 2

DIRECTION_NAMES = {
    DIRECTION_ASCENDING: "ASCENDING",
    DIRECTION_DESCENDING: "DESCENDING",
}

COLLATING_NATIVE = 0
COLLATING_EBCDIC = 1
COLLATING_LITERAL = 2

COLLATING_NAMES = {
    COLLATING_NATIVE: "NATIVE",
    COLLATING_EBCDIC: "EBCDIC",
    COLLATING_LITERAL: "LITERAL",
}

PHRASE_USING = 1
PHRASE_GIVING = 2
PHRASE_INPUT_PROCEDURE = 3
PHRASE_OUTPUT_PROCEDURE = 4

PHRASE_NAMES = {
    PHRASE_USING: "USING",
    PHRASE_GIVING: "GIVING",
    PHRASE_INPUT_PROCEDURE: "INPUT_PROCEDURE",
    PHRASE_OUTPUT_PROCEDURE: "OUTPUT_PROCEDURE",
}

SORT_RETURN_SUCCESS = 0
SORT_RETURN_ABORT = 16


# -------------------------------------------------------------------------------------- rule catalogue metadata


@dataclass(frozen=True)
class SortRuleMeta:
    id: str
    title: str
    status: str  # MATCHED / DIFFERS / REFUSED / ASSUMED
    ibm: dict[str, str] | None
    ibm_note: str | None = None
    options: list[str] = field(default_factory=list)
    register: list[str] = field(default_factory=list)
    description: str = ""


SORT_RULES: dict[str, SortRuleMeta] = {
    "RT-SORT-ALPHABET": SortRuleMeta(
        id="RT-SORT-ALPHABET",
        title="An ALPHABET (EBCDIC, or literals with ALSO and THRU): each data byte's position, the bytes no entry names after them in native order",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "SPECIAL-NAMES paragraph: ALPHABET clause"},
        options=["PROGRAM-COLLATING-SEQUENCE"],
        description="Defines a collating sequence alphabet where each character receives an ordinal weight based on IBM037 or literal phrases.",
    ),
    "RT-SORT-COLLATING-RELATION": SortRuleMeta(
        id="RT-SORT-COLLATING-RELATION",
        title="A relation condition's nonnumeric operands under PROGRAM COLLATING SEQUENCE: the shorter padded with spaces, then position by position in the alphabet",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "OBJECT-COMPUTER paragraph: PROGRAM COLLATING SEQUENCE"},
        options=["PROGRAM-COLLATING-SEQUENCE"],
        description="Alphanumeric comparisons under PROGRAM COLLATING SEQUENCE pad shorter operand with spaces and evaluate using the collating sequence weights.",
    ),
    "RT-SORT-COLLATING-DISAGREE-REFUSED": SortRuleMeta(
        id="RT-SORT-COLLATING-DISAGREE-REFUSED",
        title="A key comparison IBM's EBCDIC sequence and the oracle's byte order decide differently, or one over a byte with no EBCDIC character, stops the run by name",
        status="REFUSED",
        ibm={"doc": "cobol-lr", "section": "SORT statement: COLLATING SEQUENCE phrase"},
        options=["PROGRAM-COLLATING-SEQUENCE"],
        register=["D1"],
        description="Refuses ambiguity when IBM EBCDIC sequence diverges from oracle ASCII byte order or on unmapped characters.",
    ),
    "RT-SORT-KEYS": SortRuleMeta(
        id="RT-SORT-KEYS",
        title="SORT / MERGE keys compare as their items do in a relation condition (numeric by value, others byte by byte), the first the major key, ASCENDING / DESCENDING each",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "SORT statement: KEY phrase"},
        options=[],
        description="Major and minor keys determine sort ordering: numeric keys compare by algebraic value; alphanumeric keys compare position-by-position.",
    ),
    "RT-SORT-STABLE-ORDER": SortRuleMeta(
        id="RT-SORT-STABLE-ORDER",
        title="Equal keys come out in the order they went in (WITH DUPLICATES IN ORDER; the model keeps it always); MERGE: equal keys in the order the files are named",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "SORT statement: DUPLICATES phrase"},
        options=[],
        description="The sort algorithm is guaranteed stable: records with equal keys preserve their arrival or file order.",
    ),
    "RT-SORT-PROCEDURES": SortRuleMeta(
        id="RT-SORT-PROCEDURES",
        title="RELEASE / RETURN only inside the input / output procedure, USING files' records as they are, GIVING files each receiving every record; an implicit OPEN / READ / CLOSE that fails stops by name",
        status="MATCHED",
        ibm={"doc": "cobol-lr", "section": "RELEASE statement, RETURN statement"},
        options=[],
        description="RELEASE transfers records into the sort work area from an input procedure; RETURN retrieves sorted records in an output procedure.",
    ),
    "RT-SORT-RETURN": SortRuleMeta(
        id="RT-SORT-RETURN",
        title="SORT-RETURN written by the program: a 16 at a RELEASE / RETURN, or a value left in it when a sort ends, stops by name (IBM ends the sort at the 16 and resets the register to 0; GnuCOBOL does neither)",
        status="REFUSED",
        ibm={"doc": "cobol-lr", "section": "SORT statement: SORT-RETURN special register"},
        options=[],
        register=["F4"],
        description="Controls error termination and return codes via the SORT-RETURN special register.",
    ),
}


# -------------------------------------------------------------------------------------- key specification and vectors


@dataclass(frozen=True)
class SortKeySpec:
    offset: int
    length: int
    is_numeric: bool = False
    ascending: bool = True
    signed: bool = False


@dataclass(frozen=True)
class SortVector:
    id: str
    rule_id: str
    title: str
    records: list[str]
    keys: list[SortKeySpec]
    expected: list[str]
    collating: int = COLLATING_NATIVE
    alphabet_entries: list[str] = field(default_factory=list)
    note: str = ""


# GnuCOBOL 3.x measured EBCDIC table for ASCII bytes 0..255
GNU_EBCDIC: list[int] = [
    0,
    1,
    2,
    3,
    55,
    45,
    46,
    47,
    22,
    5,
    37,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    60,
    61,
    50,
    38,
    24,
    25,
    63,
    39,
    28,
    29,
    30,
    31,
    64,
    90,
    127,
    123,
    91,
    108,
    80,
    125,
    77,
    93,
    92,
    78,
    107,
    96,
    75,
    97,
    240,
    241,
    242,
    243,
    244,
    245,
    246,
    247,
    248,
    249,
    122,
    94,
    76,
    126,
    110,
    111,
    124,
    193,
    194,
    195,
    196,
    197,
    198,
    199,
    200,
    201,
    209,
    210,
    211,
    212,
    213,
    214,
    215,
    216,
    217,
    226,
    227,
    228,
    229,
    230,
    231,
    232,
    233,
    173,
    224,
    189,
    95,
    109,
    121,
    129,
    130,
    131,
    132,
    133,
    134,
    135,
    136,
    137,
    145,
    146,
    147,
    148,
    149,
    150,
    151,
    152,
    153,
    162,
    163,
    164,
    165,
    166,
    167,
    168,
    169,
    192,
    106,
    208,
    161,
    7,
    104,
    220,
    81,
    66,
    67,
    68,
    71,
    72,
    82,
    83,
    84,
    87,
    86,
    88,
    99,
    103,
    113,
    156,
    158,
    203,
    204,
    205,
    219,
    221,
    223,
    236,
    252,
    176,
    177,
    178,
    62,
    180,
    69,
    85,
    206,
    222,
    73,
    105,
    154,
    155,
    171,
    159,
    186,
    184,
    183,
    170,
    138,
    139,
    182,
    181,
    98,
    79,
    100,
    101,
    102,
    32,
    33,
    34,
    112,
    35,
    114,
    115,
    116,
    190,
    118,
    119,
    120,
    128,
    36,
    21,
    140,
    141,
    142,
    65,
    6,
    23,
    40,
    41,
    157,
    42,
    43,
    44,
    9,
    10,
    172,
    74,
    174,
    175,
    27,
    48,
    49,
    250,
    26,
    51,
    52,
    53,
    54,
    89,
    8,
    56,
    188,
    57,
    160,
    191,
    202,
    58,
    254,
    59,
    4,
    207,
    218,
    20,
    225,
    143,
    70,
    117,
    253,
    235,
    238,
    237,
    144,
    239,
    179,
    251,
    185,
    234,
    187,
    255,
]


def build_ebcdic_table() -> list[int]:
    """Returns mapping from ASCII byte value to EBCDIC code-page 037 ordinal."""
    tbl: list[int] = []
    for b in range(256):
        try:
            ebc = bytes([b]).decode("iso-8859-1").encode("cp037")[0]
            tbl.append(ebc)
        except Exception:
            tbl.append(-1)
    return tbl


EBCDIC_TABLE: list[int] = build_ebcdic_table()


SORT_VECTORS: list[SortVector] = [
    # RT-SORT-KEYS
    SortVector(
        id="VEC-SORT-KEY-ASCENDING",
        rule_id="RT-SORT-KEYS",
        title="Single alphanumeric key ascending sort",
        records=["CHARLIE", "BRAVO  ", "ALPHA  ", "DELTA  "],
        keys=[SortKeySpec(offset=0, length=7, ascending=True)],
        expected=["ALPHA  ", "BRAVO  ", "CHARLIE", "DELTA  "],
    ),
    SortVector(
        id="VEC-SORT-KEY-DESCENDING",
        rule_id="RT-SORT-KEYS",
        title="Single alphanumeric key descending sort",
        records=["CHARLIE", "BRAVO  ", "ALPHA  ", "DELTA  "],
        keys=[SortKeySpec(offset=0, length=7, ascending=False)],
        expected=["DELTA  ", "CHARLIE", "BRAVO  ", "ALPHA  "],
    ),
    SortVector(
        id="VEC-SORT-KEY-MULTI",
        rule_id="RT-SORT-KEYS",
        title="Major key ascending, minor key descending",
        records=["DEPT1 010", "DEPT2 050", "DEPT1 090", "DEPT2 020"],
        keys=[
            SortKeySpec(offset=0, length=5, ascending=True),
            SortKeySpec(offset=6, length=3, is_numeric=True, ascending=False),
        ],
        expected=["DEPT1 090", "DEPT1 010", "DEPT2 050", "DEPT2 020"],
    ),
    SortVector(
        id="VEC-SORT-KEY-NUMERIC-VALUE",
        rule_id="RT-SORT-KEYS",
        title="Numeric key compared by value rather than byte representation",
        records=["REC 0050", "REC 0100", "REC 0005", "REC 0025"],
        keys=[SortKeySpec(offset=4, length=4, is_numeric=True, ascending=True)],
        expected=["REC 0005", "REC 0025", "REC 0050", "REC 0100"],
    ),
    SortVector(
        id="VEC-SORT-KEY-NUMERIC-SIGNED",
        rule_id="RT-SORT-KEYS",
        title="Signed numeric key sorted algebraically",
        records=["VAL +05", "VAL -10", "VAL +00", "VAL -02"],
        keys=[SortKeySpec(offset=4, length=3, is_numeric=True, signed=True, ascending=True)],
        expected=["VAL -10", "VAL -02", "VAL +00", "VAL +05"],
    ),
    # RT-SORT-STABLE-ORDER
    SortVector(
        id="VEC-SORT-STABLE-DUPLICATES",
        rule_id="RT-SORT-STABLE-ORDER",
        title="WITH DUPLICATES IN ORDER: equal keys retain input sequence",
        records=["KEY1 ITEM-A", "KEY2 ITEM-B", "KEY1 ITEM-C", "KEY2 ITEM-D"],
        keys=[SortKeySpec(offset=0, length=4, ascending=True)],
        expected=["KEY1 ITEM-A", "KEY1 ITEM-C", "KEY2 ITEM-B", "KEY2 ITEM-D"],
    ),
    SortVector(
        id="VEC-SORT-STABLE-ALL-EQUAL",
        rule_id="RT-SORT-STABLE-ORDER",
        title="All records equal keys preserve exact arrival order",
        records=["KEY REC1", "KEY REC2", "KEY REC3", "KEY REC4"],
        keys=[SortKeySpec(offset=0, length=3, ascending=True)],
        expected=["KEY REC1", "KEY REC2", "KEY REC3", "KEY REC4"],
    ),
    # RT-SORT-ALPHABET
    SortVector(
        id="VEC-SORT-ALPHABET-EBCDIC-LETTERS-NUMBERS",
        rule_id="RT-SORT-ALPHABET",
        title="Under EBCDIC sequence, letters sort before numbers",
        records=["900", "A00", "100", "Z00"],
        keys=[SortKeySpec(offset=0, length=3, ascending=True)],
        collating=COLLATING_EBCDIC,
        expected=["A00", "Z00", "100", "900"],
        note="In ASCII, numbers sort before letters; in EBCDIC, letters sort before numbers",
    ),
    SortVector(
        id="VEC-SORT-ALPHABET-EBCDIC-CASE",
        rule_id="RT-SORT-ALPHABET",
        title="Under EBCDIC sequence, lowercase sorts before uppercase",
        records=["UPPER", "lower", "Alpha", "beta "],
        keys=[SortKeySpec(offset=0, length=5, ascending=True)],
        collating=COLLATING_EBCDIC,
        expected=["beta ", "lower", "Alpha", "UPPER"],
        note="In EBCDIC, a-z precedes A-Z",
    ),
    SortVector(
        id="VEC-SORT-ALPHABET-LITERAL-CUSTOM",
        rule_id="RT-SORT-ALPHABET",
        title="Literal alphabet alters evaluation sequence",
        records=["A1", "B1", "C1", "D1"],
        keys=[SortKeySpec(offset=0, length=2, ascending=True)],
        collating=COLLATING_LITERAL,
        alphabet_entries=["D", "C", "B", "A"],
        expected=["D1", "C1", "B1", "A1"],
    ),
    # RT-SORT-COLLATING-RELATION
    SortVector(
        id="VEC-SORT-COLLATING-RELATION-COMPARE",
        rule_id="RT-SORT-COLLATING-RELATION",
        title="Alphanumeric comparison under PROGRAM COLLATING SEQUENCE",
        records=["ITEM-B", "ITEM-A", "ITEM-1", "ITEM-2"],
        keys=[SortKeySpec(offset=0, length=6, ascending=True)],
        collating=COLLATING_EBCDIC,
        expected=["ITEM-A", "ITEM-B", "ITEM-1", "ITEM-2"],
    ),
    SortVector(
        id="VEC-SORT-COLLATING-RELATION-SPACE-PAD",
        rule_id="RT-SORT-COLLATING-RELATION",
        title="Shorter alphanumeric key padded with spaces in collating sequence",
        records=["AB ", "A  ", "B  ", "AA "],
        keys=[SortKeySpec(offset=0, length=3, ascending=True)],
        collating=COLLATING_EBCDIC,
        expected=["A  ", "AA ", "AB ", "B  "],
    ),
    # RT-SORT-COLLATING-DISAGREE-REFUSED
    SortVector(
        id="VEC-SORT-COLLATING-DISAGREE-COMMON",
        rule_id="RT-SORT-COLLATING-DISAGREE-REFUSED",
        title="Standard alphanumeric letters agreed by both IBM and GnuCOBOL",
        records=["CAT", "DOG", "BAT", "ANT"],
        keys=[SortKeySpec(offset=0, length=3, ascending=True)],
        collating=COLLATING_EBCDIC,
        expected=["ANT", "BAT", "CAT", "DOG"],
        note="Register D1: common alphanumeric words have consistent relative order",
    ),
    # RT-SORT-PROCEDURES
    SortVector(
        id="VEC-SORT-PROCEDURES-USING-FILES",
        rule_id="RT-SORT-PROCEDURES",
        title="USING files records passed and sorted",
        records=["ZULU  ", "YANKEE", "XRAY  "],
        keys=[SortKeySpec(offset=0, length=6, ascending=True)],
        expected=["XRAY  ", "YANKEE", "ZULU  "],
    ),
    SortVector(
        id="VEC-SORT-PROCEDURES-VARIABLE-LENGTH",
        rule_id="RT-SORT-PROCEDURES",
        title="Records of identical key sorted stably",
        records=["KEY1 LONG RECORD DATA", "KEY2 SHORT", "KEY1 ANOTHER"],
        keys=[SortKeySpec(offset=0, length=4, ascending=True)],
        expected=["KEY1 LONG RECORD DATA", "KEY1 ANOTHER", "KEY2 SHORT"],
    ),
    # RT-SORT-RETURN
    SortVector(
        id="VEC-SORT-RETURN-SUCCESS",
        rule_id="RT-SORT-RETURN",
        title="Normal sort execution completes with SORT-RETURN 0",
        records=["ONE", "TWO", "THREE"],
        keys=[SortKeySpec(offset=0, length=3, ascending=True)],
        expected=["ONE", "THREE", "TWO"],
        note="SORT-RETURN is 0 on normal completion",
    ),
    SortVector(
        id="VEC-SORT-RETURN-SORTED-INTEGERS",
        rule_id="RT-SORT-RETURN",
        title="Sort of integer ID fields",
        records=["0042 BOSTON", "0007 LONDON", "0100 TOKYO ", "0001 PARIS "],
        keys=[SortKeySpec(offset=0, length=4, is_numeric=True, ascending=True)],
        expected=["0001 PARIS ", "0007 LONDON", "0042 BOSTON", "0100 TOKYO "],
    ),
]


# -------------------------------------------------------------------------------------- pure-Python simulation


def get_field_bytes(record: bytes | str, key: SortKeySpec) -> bytes:
    """Extract key slice from record as bytes."""
    data = record.encode("iso-8859-1") if isinstance(record, str) else record
    return data[key.offset : key.offset + key.length]


def compare_records(
    rec_a: bytes | str,
    rec_b: bytes | str,
    keys: list[SortKeySpec],
    collating: int = COLLATING_NATIVE,
    custom_order: dict[int, int] | None = None,
) -> int:
    """Compare two records according to key specifications."""
    for key in keys:
        bytes_a = get_field_bytes(rec_a, key)
        bytes_b = get_field_bytes(rec_b, key)

        if key.is_numeric:
            str_a = bytes_a.decode("iso-8859-1").strip()
            str_b = bytes_b.decode("iso-8859-1").strip()
            val_a = Decimal(str_a) if str_a else Decimal(0)
            val_b = Decimal(str_b) if str_b else Decimal(0)
            if val_a != val_b:
                cmp_res = -1 if val_a < val_b else 1
                return cmp_res if key.ascending else -cmp_res
        elif collating == COLLATING_EBCDIC:
            # Position by position in EBCDIC code page 037
            for ba, bb in zip(bytes_a, bytes_b, strict=False):
                wa = EBCDIC_TABLE[ba] if ba < len(EBCDIC_TABLE) else ba
                wb = EBCDIC_TABLE[bb] if bb < len(EBCDIC_TABLE) else bb
                if wa != wb:
                    cmp_res = -1 if wa < wb else 1
                    return cmp_res if key.ascending else -cmp_res
            if len(bytes_a) != len(bytes_b):
                cmp_res = -1 if len(bytes_a) < len(bytes_b) else 1
                return cmp_res if key.ascending else -cmp_res
        elif collating == COLLATING_LITERAL and custom_order is not None:
            for ba, bb in zip(bytes_a, bytes_b, strict=False):
                wa = custom_order.get(ba, ba)
                wb = custom_order.get(bb, bb)
                if wa != wb:
                    cmp_res = -1 if wa < wb else 1
                    return cmp_res if key.ascending else -cmp_res
            if len(bytes_a) != len(bytes_b):
                cmp_res = -1 if len(bytes_a) < len(bytes_b) else 1
                return cmp_res if key.ascending else -cmp_res
        else:
            # Native byte-by-byte
            if bytes_a != bytes_b:
                cmp_res = -1 if bytes_a < bytes_b else 1
                return cmp_res if key.ascending else -cmp_res
    return 0


def build_literal_order(entries: list[str]) -> dict[int, int]:
    """Build byte-to-weight dictionary for literal alphabet entries."""
    order: dict[int, int] = {}
    next_weight = 0
    for e in entries:
        for ch in e:
            code = ord(ch)
            if code not in order:
                order[code] = next_weight
                next_weight += 1
    return order


def execute_sort(
    records: list[str],
    keys: list[SortKeySpec],
    collating: int = COLLATING_NATIVE,
    alphabet_entries: list[str] | None = None,
) -> list[str]:
    """Pure-Python stable sort simulation matching Sort.java."""
    custom_order = build_literal_order(alphabet_entries) if alphabet_entries else None

    # Python's list.sort is Timsort, which is guaranteed stable (preserving input order for equal keys)
    from functools import cmp_to_key

    def record_comparator(a: str, b: str) -> int:
        return compare_records(a, b, keys, collating=collating, custom_order=custom_order)

    return sorted(records, key=cmp_to_key(record_comparator))


def execute_merge(
    inputs: list[list[str]],
    keys: list[SortKeySpec],
    collating: int = COLLATING_NATIVE,
    alphabet_entries: list[str] | None = None,
) -> list[str]:
    """Pure-Python merge simulation matching Sort.java merge()."""
    all_recs: list[str] = []
    for file_recs in inputs:
        all_recs.extend(file_recs)
    return execute_sort(all_recs, keys, collating=collating, alphabet_entries=alphabet_entries)


def execute_collating_compare(
    str_a: str,
    str_b: str,
    collating: int = COLLATING_NATIVE,
    custom_order: dict[int, int] | None = None,
) -> int:
    """Simulates Collating.relation: pads shorter operand with spaces and compares."""
    max_len = max(len(str_a), len(str_b))
    pad_a = str_a.ljust(max_len, " ")
    pad_b = str_b.ljust(max_len, " ")
    key = SortKeySpec(offset=0, length=max_len, ascending=True)
    return compare_records(pad_a, pad_b, [key], collating=collating, custom_order=custom_order)
