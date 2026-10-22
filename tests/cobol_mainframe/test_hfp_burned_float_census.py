"""#4271 / #4050: every COMP-1 / COMP-2 item in a burned estate is asked by the HFP capture table.

`zos_captures/hfp.json` is what a z/OS run will settle. Each burned shape is pinned by a hand-written test in
test_hfp_zos_captures.py, but nothing stopped a float item from appearing in (or a statement from changing in) a burned
program with no record asking it. This census reads the burned programs, lists their float items and every line that
names one, and requires each item to be claimed by records that exist in the table and each claim to pin the lines
it covers. A new float item, or a moved or added statement, fails here until a record asks the shape.

Burned estates only (`estate4_draw.BURNED_NAMES`): the census never opens a non-burned repo.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TABLE = Path(__file__).parent / "zos_captures" / "hfp.json"
CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
CBSA = "cics-banking-sample-application-cbsa/src/base/cobol_src"
DBB = "dbb-mortgage-application/zBuilder/MortgageApplication/cobol"

# a level number, a name, then (maybe on later lines) USAGE [IS] COMP-1 / COMP-2 / COMPUTATIONAL-1 / COMPUTATIONAL-2
DECL = re.compile(
    r"(?<![A-Z0-9-])\d\d\s+([A-Z][A-Z0-9-]*)\s+(?:USAGE\s+(?:IS\s+)?)?COMP(?:UTATIONAL)?-[12]\s*[.\s]", re.IGNORECASE
)

LE_SECONDS = ("asm-enc-13987654321-long", "asm-fixed-13987654321-long-0")
LE_SECONDS_FRAC = ("asm-enc-13987654321.6-long", "asm-fixed-13987654321.6-long-0")
RATE = (
    "asm-enc-0.7-short",
    "asm-fixed-0.7-short-2",
    "asm-enc-9999.99-short",
    "asm-fixed-9999.99-short-2",
    "asm-enc-9999.99-long",
    "asm-cmp-9999.99-short-long",
)
AMOUNT = (
    "asm-enc-12.34-long",
    "asm-fixed-12.34-long-2",
    "asm-enc-0.01-long",
    "asm-fixed-0.01-long-2",
    "asm-enc-9999999999.99-long",
    "asm-fixed-9999999999.99-long-2",
)
NEGATED_AMOUNT = (
    "mul-long-12.34-neg1",
    "cmp-long-12.34-zero",
    "cmp-long-neg-12.34-zero",
    "asm-fixed-neg-12.34-long-2",
)
EPSMPMT = (
    "asm-enc-eps-5pct-monthly-short",
    "asm-fixed-eps-5pct-monthly-short-8",
    "asm-enc-eps-6.5pct-monthly-short",
    "asm-fixed-eps-6.5pct-monthly-short-8",
    "asm-add-1-eps-5pct-monthly-long",
    "asm-pow-eps-5pct-monthly-360",
    "asm-pow-eps-5pct-monthly-12",
    "asm-pow-eps-5pct-monthly-2.5",
    "asm-pow-eps-5pct-monthly-neg12",
    "asm-pow-eps-6.5pct-monthly-360",
)

# (source, item) -> (the lines naming the item, declaration included; the records that ask its shapes)
CLAIMS = {
    (f"{CBSA}/BANKDATA.cbl", "GMT-SECONDS"): ((296, 1443, 1450), LE_SECONDS + LE_SECONDS_FRAC),
    (f"{CBSA}/BANKDATA.cbl", "PERIOD-NEXT"): (
        (293, 1451, 1458),
        ("asm-enc-99999999999999-long", "asm-fixed-99999999999999-long-0"),
    ),
    (f"{CBSA}/CRECUST.cbl", "WS-TODAY-SECONDS"): ((316, 1394), LE_SECONDS + LE_SECONDS_FRAC),
    (f"{CBSA}/BNK1CAC.cbl", "INTRTI-COMP-1"): ((96, 658, 663, 673, 763, 765), RATE),
    (f"{CBSA}/BNK1UAC.cbl", "INTRTI-COMP-1"): ((138, 644, 646, 656, 899, 900), RATE),
    (f"{CBSA}/BNK1CRA.cbl", "WS-AMOUNT-AS-FLOAT"): (
        (72, 495, 498, 962, 974, 1130, 1133),
        AMOUNT + NEGATED_AMOUNT,
    ),
    (f"{CBSA}/BNK1TFN.cbl", "WS-AMOUNT-AS-FLOAT"): ((72, 494, 1003, 1006, 1187, 1190), AMOUNT),
    (f"{DBB}/epsmpmt.cbl", "WS-CALC-INTEREST"): ((67, 120, 127, 128, 129), EPSMPMT),
}


def float_items(text: str) -> set[str]:
    """The names declared COMP-1 / COMP-2 (either spelling, USAGE [IS] or not, the clause on a later line or not)."""
    kept = "\n".join(line for line in text.splitlines() if not (len(line) > 6 and line[6] in "*/"))
    return {m.group(1).upper() for m in DECL.finditer(kept)}


def uses(text: str, item: str) -> tuple[int, ...]:
    """The numbers of the lines (comment lines excluded) that name `item`."""
    pat = re.compile(r"(?<![A-Z0-9-])" + re.escape(item) + r"(?![A-Z0-9-])", re.IGNORECASE)
    return tuple(
        n for n, line in enumerate(text.splitlines(), 1) if pat.search(line) and not (len(line) > 6 and line[6] in "*/")
    )


def table_ids() -> set[str]:
    return {r["id"] for r in json.loads(TABLE.read_text(encoding="utf-8"))["records"]}


def read(rel: str) -> str:
    from gitgalaxy.core.source_text import read_source

    path = CORPORA / rel
    if not path.is_file():
        pytest.skip(f"{rel} is not available (GITGALAXY_MAINFRAME_CORPORA)")
    return read_source(path).text


# ---- the detector, on every spelling (no corpus needed) ----


def test_the_detector_finds_every_float_spelling_and_skips_comments_and_fixed_items():
    src = "\n".join(
        [
            "       01 A COMP-1.",
            "       01 B USAGE COMP-2.",
            "       01 C USAGE IS COMPUTATIONAL-1.",
            "       05 D",
            "           COMPUTATIONAL-2.",
            "       05 E PIC S9(4) COMP.",
            "       01 F COMP-3.",
            "      * 01 G COMP-1.",
            "       01 H-COMP-1 PIC X.",
        ]
    )
    assert float_items(src) == {"A", "B", "C", "D"}


def test_a_use_is_a_whole_name_on_a_live_line():
    src = "\n".join(
        [
            "       01 X COMP-2.",
            "       MOVE X TO Y.",
            "      * MOVE X TO Z.",
            "       MOVE X-2 TO Q.",
            "       ADD 1 TO x.",
        ]
    )
    assert uses(src, "X") == (1, 2, 5)


# ---- the census (burned corpora) ----


@pytest.mark.parametrize(("rel", "item"), sorted(CLAIMS))
def test_a_burned_float_item_is_claimed_with_the_lines_that_use_it(rel, item):
    lines, ids = CLAIMS[(rel, item)]
    text = read(rel)
    assert item in float_items(text)
    assert uses(text, item) == lines, f"{rel}: a statement naming {item} moved or was added; ask its shape in hfp.json"
    assert not set(ids) - table_ids(), sorted(set(ids) - table_ids())


@pytest.mark.parametrize("rel", sorted({r for r, _ in CLAIMS}))
def test_a_burned_program_declares_no_float_item_the_census_does_not_claim(rel):
    claimed = {i for r, i in CLAIMS if r == rel}
    assert float_items(read(rel)) == claimed


def test_no_other_burned_cbsa_or_dbb_source_declares_a_float_item():
    claimed = {r for r, _ in CLAIMS}
    seen = 0
    for rel in (
        CBSA,
        DBB,
        "dbb-mortgage-application/zBuilder/MortgageApplication/copybook",
        CBSA.replace("cobol_src", "cobol_copy"),
    ):
        base = CORPORA / rel
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if path.suffix.lower() not in (".cbl", ".cob", ".cpy") or f"{rel}/{path.name}" in claimed:
                continue
            seen += 1
            assert not float_items(read(f"{rel}/{path.name}")), f"{rel}/{path.name} declares a float item"
    if not seen:
        pytest.skip("no burned CBSA / DBB sources available (GITGALAXY_MAINFRAME_CORPORA)")
