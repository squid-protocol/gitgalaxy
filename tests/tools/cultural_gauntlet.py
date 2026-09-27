#!/usr/bin/env python3
"""
The Cultural Gauntlet, part 1 (#3834, epic #3819): the cultural counterpart of the Unicode Gauntlet.

One small COBOL seed -- a VSAM file whose FD record holds a signed zoned field, a packed field, a date and
an edited money field, a COMPUTE ... ROUNDED and an INTEGER-OF-DATE -- is templated into source DIALECTS
(plain, DECIMAL-POINT IS COMMA, CURRENCY SIGN '£', 'EUR ' WITH PICTURE SYMBOL 'U', a '€' sign, ROUNDED MODE
NEAREST-EVEN, CBL INTDATE(LILIAN)) and written in each data CODE PAGE (cp037, cp273, cp277, cp278, cp285,
cp297) as a raw fixed-block EBCDIC download: 80-byte card images, no line ends, as a binary transfer of a
PDS member arrives (the Unicode Gauntlet's writer, #3899). The estate declares its page, and runs through
the production path: galaxyscope scans it (`--source-encoding`), the refractor builds the clean room from
the scan, the COBOL-to-Java controller generates the project with `data.code_page` set to the page, as a
real conversion does. A `utf8` column is the control: the same seed as UTF-8, data page cp037.

Nothing is executed (no GnuCOBOL, no JVM): each cell is checked STATICALLY against the declared PRODUCTION
behaviour, written below as literals next to each dialect -- never recomputed by the code under test:

  facts      the source decodes back from its EBCDIC bytes; the scan's SPECIAL-NAMES, CBL options,
             record layout (offsets and widths) and VALUE literal are the declared ones
  schema     the clean room's schema and the Spring entity read the edited field with the declared
             decimal point (DECIMAL-POINT IS COMMA: `ZZZ.ZZ9,99` is DECIMAL(8, 2))
  records    the generated CobolRecords overpunches +0..+9 / -0..-9 as the page's bytes 0xC0-0xC9 /
             0xD0-0xD9 decode (IBM's sign bytes are fixed; the characters move: `{` is `ä` in cp273), and
             each AcctRec field is read at its declared offset and width
  decoder    the generated EbcdicDecoderUtil decodes with the declared page
  ticket     the port ticket carries the declared rounding (ROUNDED -> HALF_UP, NEAREST-EVEN -> HALF_EVEN),
             the CBL options and their rules, and a readable source listing
  refractor  the refractor read the program's every line
  runtime-static  (part 2) the generated Java never reads the JVM's defaults -- no Locale.getDefault(), no
             locale-less String.format / toUpperCase / toLowerCase / NumberFormat, no DecimalFormat without
             its symbols, no ZoneId.systemDefault() / TimeZone.getDefault() / LocalDate.now() without a zone
             -- and carries what #3823 (Locale.ROOT) and #3824 (the declared zone) generate

A CELL is one (dialect, page, group); it passes when nothing differs. A dialect whose characters a page
cannot hold (the euro sign in the pre-euro pages) is skipped there, and counted.

    python tests/tools/cultural_gauntlet.py --out DIR           # results.json + report.md (the matrix)
    python tests/tools/cultural_gauntlet.py --ci                # fail on a failing cell not in the baseline
    python tests/tools/cultural_gauntlet.py --full --update-baseline   # record today's failing cells

The default plan is sampled (CI runs it in under a minute): '£' in every page, every other dialect in
the control and one page (rotating); --full runs every dialect in every page. The baseline
(tests/cultural_gauntlet/baseline.txt) is the Unicode Gauntlet's ratchet: known failing cells with their
first difference, a new failing cell fails --ci, a fixed cell is reported as "lower the baseline", and git
merges the file as a union (.gitattributes). Record it with --full, so it covers every cell.

Part 2, the India slice: the page cp1140 (cp037 with the euro sign; no single-byte EBCDIC page holds '₹'),
the rupee dialects ('INR ' and 'Rs' through a PICTURE SYMBOL, lakh-grouped `KK,KK,KK9.99`, a '₹' sign in
the control only), the mainframe zone Asia/Kolkata (UTC+05:30) for every India cell, the runtime-static
group above, and an opt-in executed layer (`--run`, a JDK): the generated CobolRecords / CobolEdit /
MainframeClock compiled with javac and driven under the JVM environments hi-IN and en-IN in Asia/Kolkata
and the en-US / UTC reference (#3821's): a zoned and a packed amount, edited money fields, the mainframe
date, an upper-cased key -- byte-identical across them and equal to the declared literals (COBOL groups
`ZZ,ZZ,ZZ9.99` as 12,34,567.89 and `ZZZ,ZZZ,ZZ9.99` as 1,234,567.89 whatever the JVM's locale).

    python tests/tools/cultural_gauntlet.py --run --only currency_inr --pages cp1140   # + the JVM layer

Later parts of #3834: the target database collation (D), the input-data cases (E), and executing the
cells under GnuCOBOL.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unicode_gauntlet import fixed_block  # #3899: the one FB80 EBCDIC writer

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = REPO_ROOT / "tests" / "cultural_gauntlet"
BASELINE = HERE / "baseline.txt"
_BASELINE_HEADER = (
    "# #3834: the Cultural Gauntlet's known failing cells -- a ratchet. CI fails on a failing cell not listed\n"
    "# here; a fix removes cells (--full --update-baseline). One `cell<TAB>first difference` per line, sorted;\n"
    "# git merges this file as a union, so a stale line is possible and harmless.\n"
)

WESTERN_PAGES = ["cp037", "cp273", "cp277", "cp278", "cp285", "cp297"]
INDIA_PAGES = ["cp1140"]  # part 2: an Indian bank's page -- cp037 with the euro sign at 0x9F
PAGES = [*WESTERN_PAGES, *INDIA_PAGES]
CONTROL = "utf8"  # the seed as UTF-8, data page cp037: the dialect checks without EBCDIC in the way
COLUMNS = [CONTROL, *PAGES]
GROUPS = ["facts", "schema", "records", "decoder", "ticket", "refractor", "runtime-static"]
RUN_GROUP = "runtime-run"  # the executed JVM layer: only with --run (a JDK)

# IBM's zoned-decimal overpunch BYTES are fixed in every EBCDIC page: +0..+9 are 0xC0-0xC9, -0..-9 are
# 0xD0-0xD9 (unsigned 0xF0-0xF9). The characters they show as are the page's: the oracle decodes the
# bytes with the page's codec, never asks the converter.
POSITIVE_BYTES = bytes(range(0xC0, 0xCA))
NEGATIVE_BYTES = bytes(range(0xD0, 0xDA))
# The zero signs (0xC0 / 0xD0) by IBM CDRA, pinned here so the codecs themselves are checked too
# (tests/cultural_gauntlet/): the one pair that moves between the Western European pages.
CDRA_ZERO_SIGNS = {"cp037": "{}", "cp273": "äü", "cp277": "æå", "cp278": "äå", "cp285": "{}", "cp297": "éè",
                   "cp1140": "{}"}  # fmt: skip

# #3824: the zone the mainframe runs in (the target's culture.zone): an India cell -- an India dialect, or
# the India page -- is an Indian estate, whose clock is IST: UTC+05:30, a half-hour offset, no DST.
INDIA_ZONE = "Asia/Kolkata"

# ---- the seed and its dialects ------------------------------------------------------------------
SEED = """\
{card}       IDENTIFICATION DIVISION.
       PROGRAM-ID. CULTSEED.
       ENVIRONMENT DIVISION.
{special}       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCT-FILE ASSIGN TO ACCTDD
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS ACCT-ID.
       DATA DIVISION.
       FILE SECTION.
       FD  ACCT-FILE.
       01  ACCT-REC.
           05 ACCT-ID          PIC 9(8).
           05 ACCT-BAL         PIC S9(7)V99.
           05 ACCT-LIMIT       PIC S9(7)V99 COMP-3.
           05 ACCT-OPENED      PIC 9(8).
           05 ACCT-DUE-ED      PIC {edited}.
       WORKING-STORAGE SECTION.
       01  WS-RATE             PIC 9V9(4) VALUE {rate}.
       01  WS-LIMIT            PIC 9(5)V99 VALUE {limit}.
       01  WS-INT              PIC S9(7)V99.
       01  WS-DAYS             PIC 9(8).
       PROCEDURE DIVISION.
           OPEN I-O ACCT-FILE
           MOVE 1 TO ACCT-ID
           READ ACCT-FILE
           COMPUTE WS-INT {rounded} = ACCT-BAL * WS-RATE
           MOVE WS-LIMIT TO ACCT-LIMIT
           COMPUTE WS-DAYS = FUNCTION INTEGER-OF-DATE(ACCT-OPENED)
           MOVE WS-INT TO ACCT-DUE-ED
           REWRITE ACCT-REC
           CLOSE ACCT-FILE
           GOBACK.
"""
# the file the seed's program reads: an IDCAMS DEFINE (the VSAM store the Java entity comes from) and a step
JOB = """\
//CULTJOB  JOB CLASS=A
//DEFINE   EXEC PGM=IDCAMS
//SYSIN    DD *
   DEFINE CLUSTER (NAME(APP.ACCT.KSDS) INDEXED -
          KEYS(8 0) RECORDSIZE({size} {size}))
/*
//STEP1    EXEC PGM=CULTSEED
//ACCTDD   DD DSN=APP.ACCT.KSDS,DISP=OLD
"""


def _special(*clauses: str) -> str:
    body = "".join(f"           {c}\n" for c in clauses[:-1]) + f"           {clauses[-1]}.\n"
    return "       CONFIGURATION SECTION.\n       SPECIAL-NAMES.\n" + body


def _layout(edited_bytes: int) -> list[tuple[str, int, int]]:
    """ACCT-REC's fields: (name, offset, bytes). Only the edited field's width varies by dialect."""
    return [("ACCT-ID", 0, 8), ("ACCT-BAL", 8, 9), ("ACCT-LIMIT", 17, 5), ("ACCT-OPENED", 22, 8),
            ("ACCT-DUE-ED", 30, edited_bytes)]  # fmt: skip


def _codec(edited_bytes: int) -> list[str]:
    """AcctRec.fromRecord: each field read at its declared offset and width (S9(7)V99 COMP-3 is 5 bytes)."""
    return [
        f"CobolRecords.blank({30 + edited_bytes}, text)",
        "r.acctId = CobolRecords.toInteger(CobolRecords.zoned(rec, 0, 8, 0, text));",
        "r.acctBal = CobolRecords.zoned(rec, 8, 9, 2, text);",
        "r.acctLimit = CobolRecords.packed(rec, 17, 5, 2);",
        "r.acctOpened = CobolRecords.toInteger(CobolRecords.zoned(rec, 22, 8, 0, text));",
        f"r.acctDueEd = CobolRecords.text(rec, 30, {edited_bytes}, text);",
    ]


HALF_UP = [("COMPUTE", "WS-INT", "HALF_UP")]  # #3825: plain ROUNDED is half AWAY from zero
_CARD_RULE = "This program's CBL / PROCESS card"  # #3828: the rule a program's own card adds, and only then


def _dialect(expect: dict[str, Any], **source: str) -> dict[str, Any]:
    """A dialect: the plain seed's template values with `source` changed, and what production must do
    with it -- the plain expectations with `expect` changed."""
    plain = {"card": "", "special": "", "edited": "$$$,$$9.99", "rate": "0.0125", "limit": "12345.67",
             "rounded": "ROUNDED"}  # fmt: skip
    want = {
        "special_names": [],  # (clause, value, symbol) of SPECIAL-NAMES
        "compiler_options": [],  # (option, value) of the CBL / PROCESS card
        "layout": _layout(10),
        "record_bytes": 40,
        "limit_literal": "12345.67",  # WS-LIMIT's VALUE, as written
        "decimal_comma": False,
        "due_sql": "DECIMAL(7, 2)",  # the edited field: 4 floating currency positions + 9.99
        "due_entity": 'name = "ACCT_DUE_ED", precision = 7, scale = 2',
        "codec": _codec(10),
        "rounding": HALF_UP,  # (verb, target, java.math.RoundingMode) in the port ticket
        "rules": [],  # porting rules the ticket must carry
        "no_rules": [_CARD_RULE],  # ... and must not
        # --run: CobolEdit.format(edited, 1234.50) as COBOL edits it (GnuCOBOL 3 prints ` $1,234.50`); None
        # where no oracle is at hand -- GnuCOBOL does not implement a multi-character currency string
        "edited": " $1,234.50",
    }
    return {**plain, **source, "expect": {**want, **expect}}


# Each dialect's template values, and what production must do with it -- literals, declared once here.
DIALECTS: dict[str, dict[str, Any]] = {
    "plain": _dialect({}),
    # #3827: the comma is the decimal point, the period an insertion character: ZZZ.ZZ9,99 is 6 + 2 digits
    "decimal_comma": _dialect(
        {
            "special_names": [("DECIMAL-POINT", "COMMA", None)],
            "limit_literal": "12345,67",
            "decimal_comma": True,
            "edited": "  1.234,50",  # GnuCOBOL 3
            "due_sql": "DECIMAL(8, 2)",
            "due_entity": 'name = "ACCT_DUE_ED", precision = 8, scale = 2',
        },
        special=_special("DECIMAL-POINT IS COMMA"),
        edited="ZZZ.ZZ9,99",
        rate="0,0125",
        limit="12345,67",
    ),
    # #3857: '£' is the currency symbol, one byte a position
    "currency_pound": _dialect(
        {"special_names": [("CURRENCY", "£", "£")], "edited": " £1,234.50"},
        special=_special("CURRENCY SIGN IS '£'"),
        edited="£££,££9.99",
    ),
    # #3857: the symbol U stands for the 4-character 'EUR ': its first position takes 4 bytes
    "currency_eur_u": _dialect(
        {
            "special_names": [("CURRENCY", "EUR ", "U")],
            "layout": _layout(13),
            "record_bytes": 43,
            "codec": _codec(13),
            "edited": None,
        },
        special=_special("CURRENCY SIGN IS 'EUR ' WITH PICTURE SYMBOL 'U'"),
        edited="UUU,UU9.99",
    ),
    # a '€' sign: none of the pre-euro pages holds it (their euro twins are cp1140-cp1149; cp1140 runs it)
    "currency_euro": _dialect(
        {"special_names": [("CURRENCY", "€", "€")], "edited": " €1,234.50"},
        special=_special("CURRENCY SIGN IS '€'"),
        edited="€€€,€€9.99",
    ),
    # #3825: ROUNDED MODE NEAREST-EVEN is Java's HALF_EVEN
    "rounded_nearest_even": _dialect(
        {"rounding": [("COMPUTE", "WS-INT", "HALF_EVEN")]}, rounded="ROUNDED MODE NEAREST-EVEN"
    ),
    # #3828: INTEGER-OF-DATE counts from 1582-10-15 (day zero 1582-10-14), not 1601-01-01
    "intdate_lilian": _dialect(
        {
            "compiler_options": [("INTDATE", "LILIAN")],
            "rules": ["sets INTDATE(LILIAN)", "dayZero 1582-10-14"],
            "no_rules": [],
        },
        card="       CBL INTDATE(LILIAN)\n",
    ),
    # ---- part 2, the India slice: the rupee as Indian COBOL shops write it. A multi-character sign needs a
    # PICTURE SYMBOL, and the symbol cannot be R (IBM and GnuCOBOL reserve A B C D E G N P R S V X Z: `CR`
    # is a PICTURE symbol; GnuCOBOL 3: "invalid character 'R' in currency symbol"), nor can 'Rs' stand
    # alone (a sign without PICTURE SYMBOL is one character; GnuCOBOL reads `RsRs` as R and S).
    # #3857: 'INR ' through the symbol I -- its first position takes 4 bytes, as 'EUR ' / U does
    "currency_inr": _dialect(
        {
            "special_names": [("CURRENCY", "INR ", "I")],
            "layout": _layout(13),
            "record_bytes": 43,
            "codec": _codec(13),
            "edited": None,
        },
        special=_special("CURRENCY SIGN IS 'INR ' WITH PICTURE SYMBOL 'I'"),
        edited="III,II9.99",
    ),
    # 'Rs' through the symbol K, lakh-grouped (12,34,567.89): 6 floating K are 5 digits + the sign, then 9,
    # so 6 integer digits; the first K takes 2 bytes, 12 + 1 = 13
    "currency_rs_lakh": _dialect(
        {
            "special_names": [("CURRENCY", "Rs", "K")],
            "layout": _layout(13),
            "record_bytes": 43,
            "codec": _codec(13),
            "due_sql": "DECIMAL(8, 2)",
            "due_entity": 'name = "ACCT_DUE_ED", precision = 8, scale = 2',
            "edited": None,
        },
        special=_special("CURRENCY SIGN IS 'Rs' WITH PICTURE SYMBOL 'K'"),
        edited="KK,KK,KK9.99",
    ),
    # a '₹' sign: no single-byte EBCDIC page holds it (cp1140 included), so it runs in the control only
    "currency_rupee": _dialect(
        {"special_names": [("CURRENCY", "₹", "₹")], "edited": " ₹1,234.50"},
        special=_special("CURRENCY SIGN IS '₹'"),
        edited="₹₹₹,₹₹9.99",
    ),
}
INDIA_DIALECTS = ["currency_inr", "currency_rs_lakh", "currency_rupee"]


def india_cell(dialect: str, column: str) -> bool:
    """Part 2: an Indian estate -- a rupee dialect, or any dialect in the India page."""
    return dialect in INDIA_DIALECTS or column in INDIA_PAGES


def cell_zone(dialect: str, column: str) -> str:
    """#3824: the target's culture.zone for the cell -- the mainframe's zone, which the generated clock keeps."""
    return INDIA_ZONE if india_cell(dialect, column) else "UTC"


def seed_text(dialect: str) -> str:
    d = DIALECTS[dialect]
    return SEED.format(**{k: d[k] for k in ("card", "special", "edited", "rate", "limit", "rounded")})


def estate_files(dialect: str) -> dict[str, str]:
    size = DIALECTS[dialect]["expect"]["record_bytes"]
    return {"cbl/CULTSEED.cbl": seed_text(dialect), "jcl/CULTJOB.jcl": JOB.format(size=size)}


def encode(text: str, column: str) -> bytes | None:
    """The file's bytes: UTF-8 in the control, else a fixed-block download in the page (None when a
    character is not in the page, or a line is longer than a card)."""
    return text.encode("utf-8") if column == CONTROL else fixed_block(text, column)


def data_page(column: str) -> str:
    return "cp037" if column == CONTROL else column


# ---- one cell's pipeline (run in its own process: the scan is process-global) -------------------
def _java_file(root: Path, rel: str) -> str | None:
    hits = sorted(root.glob(f"*_gitgalaxy_java_spring_*/src/main/java/com/gitgalaxy/modernized/{rel}"))
    return hits[0].read_text(encoding="utf-8") if hits else None


def _observe(cell_dir: Path, dialect: str, column: str) -> dict[str, Any]:
    """Build the estate, run scan -> refractor -> COBOL-to-Java, and collect what the checks read."""
    from unittest.mock import patch

    from gitgalaxy import cobol_refractor_controller as refractor
    from gitgalaxy import cobol_to_java_controller
    from gitgalaxy.core.source_text import decode_source
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

    obs: dict[str, Any] = {}
    estate = cell_dir / "estate"
    for rel, text in estate_files(dialect).items():
        data = encode(text, column)
        if data is None:
            return {"skipped": f"{rel} does not fit {column}"}
        (estate / rel).parent.mkdir(parents=True, exist_ok=True)
        (estate / rel).write_bytes(data)
        if rel.endswith(".cbl"):  # the read every scan makes of it
            decoded = decode_source(data, declared=None if column == CONTROL else column)
            obs["decoded"] = [line.rstrip() for line in decoded.text.splitlines()]
            obs["decoded_how"] = decoded.how
    declared = () if column == CONTROL else ("--source-encoding", column)
    db = scan_to_db(estate, cell_dir / "scan", extra_args=declared)
    ir = load_galaxy_ir(db)
    ef = ir.files["cbl/CULTSEED.cbl"]
    obs["special_names"] = [(s.clause, s.value, s.symbol or None) for s in ef.special_names]
    obs["compiler_options"] = [(o.option, o.value) for o in ef.compiler_options]
    roots = [r for r in ef.records if r.name == "ACCT-REC"]
    layout = ir.record_layout(ef, roots[0]) if roots else {"fields": [], "bytes": None}
    obs["layout"] = [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]]
    obs["record_bytes"] = layout["bytes"]
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT value_literal FROM record_data WHERE item_name = 'WS-LIMIT'").fetchone()
    obs["limit_literal"] = row[0] if row else None

    config = cell_dir / "target.json"
    culture = {"zone": cell_zone(dialect, column)}  # #3824: an India cell's mainframe runs in IST
    config.write_text(json.dumps({"data": {"code_page": data_page(column)}, "culture": culture}), encoding="utf-8")
    with open(cell_dir / "pipeline.log", "w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        with patch("sys.argv", ["cobol-refractor", str(estate), "--galaxy-db", str(db)]):
            refractor.main()
        (clean,) = cell_dir.glob("estate_gitgalaxy_clean_*")
        argv = ["cobol-to-java", str(clean), "--header", str(cell_dir / "no-header.txt"), "--config", str(config)]
        with patch("sys.argv", argv):
            cobol_to_java_controller.main()
    schema = clean / "02_cloud_schemas" / "CULTSEED_schema"
    obs["schema_json"] = json.loads(schema.with_suffix(".json").read_text(encoding="utf-8"))
    obs["schema_sql"] = schema.with_suffix(".sql").read_text(encoding="utf-8")
    ir_dump = json.loads((clean / "04_ir_state_dumps" / "CULTSEED_ir.json").read_text(encoding="utf-8"))
    obs["refractor_loc"] = ir_dump["metadata"].get("loc")
    for key, rel in (("entity", "entity/CultseedAcctRec.java"), ("acct_rec", "entity/vsam/AcctRec.java"),
                     ("cobol_records", "entity/vsam/CobolRecords.java"), ("decoder", "util/EbcdicDecoderUtil.java")):  # fmt: skip
        obs[key] = _java_file(cell_dir, rel)
    (java,) = cell_dir.glob("estate_gitgalaxy_java_spring_*")
    ticket = json.loads((java / "ai_agent_jobs" / "CULTSEED_port_ticket.json").read_text(encoding="utf-8"))
    obs["ticket_rounding"] = [(r["verb"], t["target"], t["java"]) for r in ticket["rounding"] for t in r["targets"]]
    obs["ticket_options"] = [(o["option"], o["value"]) for o in ticket["compiler_options"]]
    obs["ticket_rules"] = ticket["rules"]
    listing = java / "ai_agent_jobs" / "sources" / "cbl" / "CULTSEED.cbl.lst"
    obs["listing"] = listing.read_text(encoding="utf-8") if listing.is_file() else None
    modernized = java / "src" / "main" / "java" / "com" / "gitgalaxy" / "modernized"
    obs["java_sources"] = {f.relative_to(modernized).as_posix(): f.read_text(encoding="utf-8")
                           for f in sorted(modernized.rglob("*.java"))}  # fmt: skip
    return obs


def _run_cell(args: tuple[Any, ...]) -> dict[str, Any]:
    dialect, column, work, *execute = args
    os.environ.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")  # a pool process of its own
    os.environ["GITGALAXY_DISABLE_GIT_HISTORY"] = "1"
    cell_dir = Path(work) / f"{dialect}__{column}"
    try:
        obs = _observe(cell_dir, dialect, column)
    except Exception:  # a crash is the cell's finding, not the gauntlet's end
        return {"error": traceback.format_exc(limit=4).strip().splitlines()[-1]}
    if execute and execute[0] and "skipped" not in obs:
        try:
            obs["runtime_run"] = execute_cell(cell_dir, dialect, column, obs["java_sources"])
        except Exception:
            obs["runtime_run"] = {"error": traceback.format_exc(limit=4).strip().splitlines()[-1]}
    return obs


# ---- the executed layer (--run): the generated runtime under the JVM environments -----------------
# #3821's environments (tests/tools/equivalence_java.py): hi-IN and en-IN in Asia/Kolkata, and the reference
# en-US / UTC. The generated classes that need no Spring context -- CobolRecords, CobolEdit and MainframeClock
# (its two Spring annotations stubbed, annotation-only) -- are compiled with a small driver and run in each.
JVM_ENVIRONMENTS = ["hindi", "en-IN/Asia/Kolkata", "default"]
REFERENCE_ENVIRONMENT = "default"
RUN_SOURCES = ["entity/vsam/CobolRecords.java", "entity/vsam/CobolEdit.java", "batch/MainframeClock.java"]
PINNED_CLOCK = "2026-03-29T02:30:00.00"  # gitgalaxy.clock, as the equivalence harness pins it
# What the driver must print in EVERY environment -- literals, never the converter's: IBM zoned -1234567.89
# (0xD9, the -9 overpunch) and packed (sign nibble D), COBOL's edited PICTUREs (GnuCOBOL 3 prints the lakh
# grouping `ZZ,ZZ,ZZ9.99` as 12,34,567.89 and `ZZZ,ZZZ,ZZ9.99` as 1,234,567.89: the PICTURE groups, never
# the locale), an invariant key in its EBCDIC order bytes, NUMVAL's lower-case `cr`, and FUNCTION
# CURRENT-DATE of the pinned local time with the zone's offset.
RUN_EXPECT = {
    "zoned": "F1F2F3F4F5F6F7F8D9 -1234567.89",
    "packed": "123456789D -1234567.89",
    "lakh": "12,34,567.89",
    "thousands": "  1,234,567.89",
    "key": "818383A3608995F0F1 -1234.50",
}
RUN_DATE = {"UTC": "2026032902300000+0000", INDIA_ZONE: "2026032902300000+0530"}
_SPRING_STUBS = {
    "org/springframework/beans/factory/annotation/Value.java":
        "package org.springframework.beans.factory.annotation;\npublic @interface Value { String value(); }\n",
    "org/springframework/stereotype/Component.java":
        "package org.springframework.stereotype;\npublic @interface Component {}\n",
}  # fmt: skip
_DRIVER = """\
import com.gitgalaxy.modernized.batch.MainframeClock;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.NumberFormat;
import java.time.ZoneId;
import java.util.Locale;

/** #3834: the generated runtime's culture-sensitive outputs, one `name<TAB>value` line each. */
public class CulturalGauntletDriver {
    public static void main(String[] argv) throws Exception {
        // the arguments as UTF-8 lines: a command line's encoding is the platform's, and '₹' must survive it
        String[] a = Files.readAllLines(Path.of(argv[0]), StandardCharsets.UTF_8).toArray(new String[0]);
        String page = a[0], pic = a[1], currency = a[3].isEmpty() ? null : a[3];
        Charset text = Charset.forName(page);
        BigDecimal amount = new BigDecimal("-1234567.89");
        // the environment itself: this line must DIFFER between environments, or the run proves nothing
        out("canary", Locale.getDefault().toLanguageTag() + " " + ZoneId.systemDefault() + " "
                + NumberFormat.getCurrencyInstance().format(1234567.89));
        byte[] zoned = new byte[9];
        CobolRecords.putZoned(zoned, 0, 9, 2, true, amount, text);
        out("zoned", hex(zoned) + " " + CobolRecords.zoned(zoned, 0, 9, 2, text).toPlainString());
        byte[] packed = new byte[5];
        CobolRecords.putPacked(packed, 0, 5, 2, true, amount);
        out("packed", hex(packed) + " " + CobolRecords.packed(packed, 0, 5, 2).toPlainString());
        out("edited", CobolEdit.format(pic, new BigDecimal("1234.5"), Boolean.parseBoolean(a[2]), currency));
        out("lakh", CobolEdit.format("ZZ,ZZ,ZZ9.99", amount.negate(), false, null));
        out("thousands", CobolEdit.format("ZZZ,ZZZ,ZZ9.99", amount.negate(), false, null));
        out("key", CobolRecords.sortKey("acct-in01", page) + " " + CobolRecords.numval("1234.50cr").toPlainString());
        out("date", new MainframeClock(a[4], a[5]).currentDate());
    }

    private static void out(String name, String value) {
        System.out.println(name + "\t" + value);
    }

    private static String hex(byte[] b) {
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format(Locale.ROOT, "%02X", x & 0xFF));
        return s.toString();
    }
}
"""
_ZONE_PROPERTY = re.compile(r'@Value\("\$\{gitgalaxy\.zone:([^}"]{0,64})\}"\)')


def jdk() -> tuple[str, str] | None:
    """(javac, java) of $JAVA_HOME, else of the PATH; None without a JDK."""
    home = os.environ.get("JAVA_HOME")
    tools = (
        [str(Path(home) / "bin" / t) for t in ("javac", "java")]
        if home
        else [shutil.which("javac"), shutil.which("java")]
    )
    return (tools[0], tools[1]) if all(t and os.access(t, os.X_OK) for t in tools) else None


def jvm_flags(name: str) -> list[str]:
    """#3821's environment `name` as the JVM's own defaults: -Duser.language / -Duser.country / -Duser.timezone."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from equivalence_java import environment

    env = environment(name)
    language, _, country = env["locale"].partition("-")
    flags = [f"-Duser.language={language}", f"-Duser.timezone={env['tz']}"]
    return flags + ([f"-Duser.country={country.split('-')[0]}"] if country else [])


def _java_charset(page: str) -> str:
    n = _page_number(page)
    return f"IBM{n:03d}" if n is not None and n < 1000 else f"IBM0{n}"


def execute_cell(cell_dir: Path, dialect: str, column: str, sources: dict[str, str]) -> dict[str, Any]:
    """Compile the generated runtime classes with the driver and run it in each JVM environment:
    {"envs": {environment: {name: value}}}, or {"skipped": why} without a JDK."""
    tools = jdk()
    if tools is None:
        return {"skipped": "no JDK (javac + java): the executed layer needs one"}
    missing = [rel for rel in RUN_SOURCES if rel not in sources]
    if missing:
        return {"error": f"not generated: {', '.join(missing)}"}
    root = cell_dir / "jvm"
    src, classes = root / "src", root / "classes"
    files = {f"com/gitgalaxy/modernized/{rel}": sources[rel] for rel in RUN_SOURCES}
    files.update(_SPRING_STUBS)
    files["CulturalGauntletDriver.java"] = _DRIVER
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    classes.mkdir(parents=True, exist_ok=True)
    javac, java = tools
    built = subprocess.run(  # noqa: S603 -- fixed argv: the local JDK over files this run wrote
        [javac, "-encoding", "UTF-8", "-d", str(classes), *(str(src / f) for f in files)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if built.returncode:
        return {"error": f"javac: {(built.stderr or built.stdout).strip().splitlines()[:1]}"}
    d = DIALECTS[dialect]
    currency = next((v for c, v, _ in d["expect"]["special_names"] if c == "CURRENCY"), "")
    zone = _ZONE_PROPERTY.search(sources["batch/MainframeClock.java"])  # the @Value default Spring would inject
    args = [_java_charset(data_page(column)), d["edited"], str(d["expect"]["decimal_comma"]).lower(), currency,
            PINNED_CLOCK, zone.group(1) if zone else ""]  # fmt: skip
    (root / "args.txt").write_text("".join(f"{a}\n" for a in args), encoding="utf-8")
    envs: dict[str, dict[str, str]] = {}
    for name in JVM_ENVIRONMENTS:
        ran = subprocess.run(  # noqa: S603 -- fixed argv: the local JDK, #3821's environment flags
            [
                java,
                *jvm_flags(name),
                "-Dfile.encoding=UTF-8",
                "-Dstdout.encoding=UTF-8",
                "-cp",
                str(classes),
                "CulturalGauntletDriver",
                str(root / "args.txt"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
        if ran.returncode:
            return {"error": f"java ({name}): {(ran.stderr or ran.stdout).strip().splitlines()[-1:]}"}
        envs[name] = dict(line.split("\t", 1) for line in ran.stdout.splitlines() if "\t" in line)
    return {"envs": envs}


# ---- the oracle -----------------------------------------------------------------------------------
_JAVA_STRING = re.compile(r'\b(POSITIVE|NEGATIVE) = "((?:[^"\\]|\\.){1,60})";')
_CHARSET = re.compile(r'Charset\.forName\("([^"]{1,40})"\)')


def _java_unescape(s: str) -> str:
    return re.sub(r"\\u([0-9a-fA-F]{4})|\\(.)", lambda m: chr(int(m.group(1), 16)) if m.group(1) else m.group(2), s)


def _page_number(name: str) -> int | None:
    """cp285 / IBM285 / IBM-285 / Cp037 / x-IBM1047 -> the IBM code page number."""
    m = re.search(r"(?:cp|ibm)[-_]?0*(\d{1,5})$", name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _sign_diffs(java: str | None, column: str) -> list[str]:
    if java is None:
        return ["CobolRecords.java: not generated"]
    found = {k: _java_unescape(v) for k, v in _JAVA_STRING.findall(java)}
    page = data_page(column)
    out = []
    for sign, raw in (("POSITIVE", POSITIVE_BYTES), ("NEGATIVE", NEGATIVE_BYTES)):
        want, got = raw.decode(page), found.get(sign, "")
        for digit in range(10):
            g = got[digit] if digit < len(got) else None
            if g != want[digit]:
                value = f"{'+' if sign == 'POSITIVE' else '-'}{digit}"
                out.append(f"CobolRecords {value}: {page} byte 0x{raw[digit]:02X} is {want[digit]!r}, "
                           f"the codec overpunches {g!r}")  # fmt: skip
    return out


# #3834 (C, runtime): generated Java that reads the JVM's defaults behaves differently on an Indian (or
# Turkish, or Thai) JVM. With culture.format_locale ROOT (the gauntlet's config, and the default) none of
# these may appear: (what, pattern) -- bounded, over the source without its comments.
JVM_DEFAULTS = [
    ("Locale.getDefault()", re.compile(r"\bLocale\.getDefault\(")),
    ("String.format without a Locale", re.compile(r"\bString\.format\(\s{0,8}(?!(?:java\.util\.)?Locale\.)")),
    ("String.formatted (the default locale)", re.compile(r"\.formatted\(")),
    ("toUpperCase() / toLowerCase() without a Locale", re.compile(r"\.to(?:Upper|Lower)Case\(\s{0,8}\)")),
    ("NumberFormat without a Locale", re.compile(r"\bNumberFormat\.get\w{0,20}Instance\(\s{0,8}\)")),
    ("DecimalFormat without its symbols",
     re.compile(r'\bnew\s{1,8}DecimalFormat\(\s{0,8}(?:"(?:[^"\\\n]|\\.){0,80}"|[\w.]{1,60})?\s{0,8}\)')),
    ("ZoneId.systemDefault()", re.compile(r"\bZoneId\.systemDefault\(")),
    ("TimeZone.getDefault()", re.compile(r"\bTimeZone\.getDefault\(")),
    ("Clock.systemDefaultZone()", re.compile(r"\bClock\.systemDefaultZone\(")),
    ("now() without a zone",
     re.compile(r"\b(?:LocalDate|LocalDateTime|LocalTime|ZonedDateTime|OffsetDateTime|YearMonth|Year)"
                r"\.now\(\s{0,8}\)")),
    ("a calendar without a zone",
     re.compile(r"\bCalendar\.getInstance\(\s{0,8}\)|\bnew\s{1,8}GregorianCalendar\(\s{0,8}\)")),
    ("new Date() (the JVM's zone when shown)", re.compile(r"\bnew\s{1,8}(?:java\.util\.)?Date\(\s{0,8}\)")),
    ("the default charset", re.compile(r"\.getBytes\(\s{0,8}\)|\bCharset\.defaultCharset\(")),
]  # fmt: skip
_JAVA_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def required_java(zone: str) -> list[tuple[str, str]]:
    """(file, text) the generated runtime must carry: #3824's clock in the declared zone (the default Spring
    injects, and the constructor's own fallback), and #3823's Locale.ROOT where it upper-cases and formats."""
    return [
        ("batch/MainframeClock.java", f'@Value("${{gitgalaxy.zone:{zone}}}")'),
        ("batch/MainframeClock.java", f'? "{zone}" : zoneId.trim()'),
        ("batch/MainframeClock.java", "ZonedDateTime.now(zone)"),
        ("entity/vsam/CobolRecords.java", "s.toUpperCase(Locale.ROOT)"),
        ("batch/DatasetResolver.java", 'String.format(Locale.ROOT, "G%04dV00"'),
        ("batch/JclConditions.java", "cond.toUpperCase(Locale.ROOT)"),
    ]


def runtime_static_diffs(sources: dict[str, str], zone: str) -> list[str]:
    """Each JVM-default read in the generated Java (file:line), then each #3823 / #3824 construct missing."""
    out = []
    for rel, text in sorted(sources.items()):
        code = _JAVA_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)  # keep the line numbers
        for what, pattern in JVM_DEFAULTS:
            for m in pattern.finditer(code):
                line = code.count("\n", 0, m.start()) + 1
                snippet = code.splitlines()[line - 1].strip()[:80]
                out.append(f"{rel}:{line}: {what}: `{snippet}`")
    for rel, text in required_java(zone):
        if rel not in sources:
            out.append(f"{rel}: not generated (want `{text}`)")
        elif text not in sources[rel]:
            out.append(f"{rel}: missing `{text}`")
    return out


def runtime_run_diffs(run: dict[str, Any], zone: str, edited: str | None = None) -> list[str]:
    """The executed layer: every environment prints what the reference prints, that is the declared
    literals; and the canary proves each environment really was a different JVM default."""
    if "error" in run:
        return [f"executed layer failed: {run['error']}"]
    envs = run["envs"]
    ref = envs[REFERENCE_ENVIRONMENT]
    out = []
    want = {**RUN_EXPECT, "date": RUN_DATE[zone], **({"edited": edited} if edited is not None else {})}
    out += [
        f"{k} ({REFERENCE_ENVIRONMENT}): want {v!r}, got {ref.get(k)!r}" for k, v in want.items() if ref.get(k) != v
    ]
    for name, got in envs.items():
        if name == REFERENCE_ENVIRONMENT:
            continue
        if got.get("canary") == ref.get("canary"):
            out.append(f"{name}: the JVM environment did not apply (canary {got.get('canary')!r})")
        out += [f"{k} differs in {name}: {ref.get(k)!r} ({REFERENCE_ENVIRONMENT}) vs {got.get(k)!r}"
                for k in sorted(set(ref) | set(got)) if k != "canary" and got.get(k) != ref.get(k)]  # fmt: skip
    return out


def check(dialect: str, column: str, obs: dict[str, Any]) -> dict[str, list[str]]:
    """{group: its differences} of one (dialect, column) against the dialect's declared behaviour."""
    if "error" in obs:
        return {g: [f"pipeline failed: {obs['error']}"] for g in GROUPS}
    want = DIALECTS[dialect]["expect"]
    out: dict[str, list[str]] = {g: [] for g in GROUPS}

    def same(group: str, what: str, expected: Any, got: Any) -> None:
        if expected != got:
            out[group].append(f"{what}: want {expected!r}, got {got!r}")

    seed = seed_text(dialect).splitlines()
    decoded = obs["decoded"]
    bad = next((i for i, (a, b) in enumerate(zip(seed, decoded)) if a.rstrip() != b), None)
    if bad is not None or len(seed) != len(decoded):
        n = bad if bad is not None else min(len(seed), len(decoded))
        was, now = [*seed, ""][n].strip(), [*decoded, ""][n].strip()
        out["facts"].append(f"source read back ({obs['decoded_how']}) differs at line {n + 1}: {was!r} -> {now!r}")
    same("facts", "SPECIAL-NAMES", want["special_names"], [tuple(s) for s in obs["special_names"]])
    same("facts", "CBL options", want["compiler_options"], [tuple(o) for o in obs["compiler_options"]])
    same("facts", "ACCT-REC layout", want["layout"], [tuple(f) for f in obs["layout"]])
    same("facts", "ACCT-REC bytes", want["record_bytes"], obs["record_bytes"])
    same("facts", "WS-LIMIT VALUE", want["limit_literal"], obs["limit_literal"])

    same("schema", "schema decimal_comma", want["decimal_comma"], bool(obs["schema_json"].get("decimal_comma")))
    sql = re.search(r"^\s*ACCT_DUE_ED\s+(\S+(?: \d+\))?)", obs["schema_sql"], re.M)
    same("schema", "ACCT_DUE_ED column", want["due_sql"], sql.group(1).rstrip(",") if sql else None)
    entity = obs["entity"] or ""
    if f"@Column({want['due_entity']})" not in entity:
        got = re.search(r'@Column\((name = "ACCT_DUE_ED"[^)]{0,80})\)', entity)
        out["schema"].append(f"CultseedAcctRec: want @Column({want['due_entity']}), got {got and got.group(1)!r}")

    out["records"] += _sign_diffs(obs["cobol_records"], column)
    acct = obs["acct_rec"] or ""
    out["records"] += [f"AcctRec: missing `{line}`" for line in want["codec"] if line not in acct]

    names = _CHARSET.findall(obs["decoder"] or "")
    if [_page_number(n) for n in names] != [_page_number(data_page(column))]:
        out["decoder"].append(f"EbcdicDecoderUtil decodes with {names}, the data is {data_page(column)}")

    same("ticket", "ticket rounding", want["rounding"], [tuple(r) for r in obs["ticket_rounding"]])
    same("ticket", "ticket CBL options", want["compiler_options"], [tuple(o) for o in obs["ticket_options"]])
    rules = " ".join(obs["ticket_rules"])
    out["ticket"] += [f"ticket rules: no {r!r}" for r in want["rules"] if r not in rules]
    out["ticket"] += [f"ticket rules: unexpected {r!r}" for r in want["no_rules"] if r in rules]
    if "PROGRAM-ID. CULTSEED." not in (obs["listing"] or ""):
        out["ticket"].append(f"source listing unreadable: {(obs['listing'] or '')[:60]!r}")

    same("refractor", "refractor read lines", len(seed), obs["refractor_loc"])

    out["runtime-static"] += runtime_static_diffs(obs.get("java_sources") or {}, cell_zone(dialect, column))
    if "runtime_run" in obs and "skipped" not in obs["runtime_run"]:
        out[RUN_GROUP] = runtime_run_diffs(obs["runtime_run"], cell_zone(dialect, column), want["edited"])
    return out


# ---- the plan and the run -------------------------------------------------------------------------
def plan(full: bool, only: set[str] | None = None, pages: set[str] | None = None) -> list[tuple[str, str]]:
    """(dialect, column) pairs. Sampled: '£' (the dialect a page moves: `$` and `£` trade bytes) in every
    page, every other dialect in the control and one page, rotating so the pages meet different dialects.
    Part 2's India slice: the rupee dialects in the control and the India page, and plain in the India page."""
    out = []
    for i, dialect in enumerate(DIALECTS):
        cols = COLUMNS if full or dialect == "currency_pound" else [CONTROL, WESTERN_PAGES[i % len(WESTERN_PAGES)]]
        if not full and dialect in INDIA_DIALECTS:
            cols = [CONTROL, *INDIA_PAGES]
        elif not full and dialect == "plain":
            cols += INDIA_PAGES
        out += [(dialect, c) for c in cols]
    return [(d, c) for d, c in out if (not only or d in only) and (not pages or c in pages)]


def run(work: Path, full: bool = False, jobs: int = 4, only: set[str] | None = None,
        pages: set[str] | None = None, execute: bool = False) -> dict[str, Any]:  # fmt: skip
    from concurrent.futures import ProcessPoolExecutor

    pairs = plan(full, only, pages)
    with ProcessPoolExecutor(max_workers=max(1, jobs)) as pool:
        observed = list(pool.map(_run_cell, [(d, c, str(work), execute) for d, c in pairs]))
    results: dict[str, Any] = {}
    for (dialect, column), obs in zip(pairs, observed):
        if "skipped" in obs:
            for g in GROUPS + ([RUN_GROUP] if execute else []):
                results[f"{dialect}|{column}|{g}"] = {"dialect": dialect, "page": column, "group": g,
                                                      "skipped": obs["skipped"], "diffs": []}  # fmt: skip
            continue
        if "skipped" in obs.get("runtime_run", {}):  # --run without a JDK: skipped and counted, never passed
            why = obs["runtime_run"]["skipped"]
            results[f"{dialect}|{column}|{RUN_GROUP}"] = {"dialect": dialect, "page": column, "group": RUN_GROUP,
                                                          "skipped": why, "diffs": []}  # fmt: skip
        for g, diffs in check(dialect, column, obs).items():
            results[f"{dialect}|{column}|{g}"] = {"dialect": dialect, "page": column, "group": g, "diffs": diffs}
    return results


# ---- report and baseline (the Unicode Gauntlet's ratchet, #3812) --------------------------------
def read_baseline() -> dict[str, str]:
    """{cell: its first difference} of the committed baseline (empty without one)."""
    if not BASELINE.is_file():
        return {}
    rows = (line.split("\t", 1) for line in BASELINE.read_text(encoding="utf-8").splitlines())
    return {r[0]: (r[1] if len(r) > 1 else "") for r in rows if r[0] and not r[0].startswith("#")}


def write_baseline(failing: dict[str, str]) -> None:
    def one_line(diff: str) -> str:
        return " ".join(diff.split())[:240]

    body = "".join(f"{cid}\t{one_line(d)}\n" for cid, d in sorted(failing.items()))
    BASELINE.write_text(_BASELINE_HEADER + body, encoding="utf-8")


def india_summary(results: dict[str, Any], known: dict[str, str]) -> str:
    """Part 2: the India row -- an India cell passes, fails as ledgered in the baseline, fails new, or is skipped."""
    cells = {cid: r for cid, r in results.items() if india_cell(r["dialect"], r["page"])}
    ran = {cid: r for cid, r in cells.items() if "skipped" not in r}
    failing = {cid for cid, r in ran.items() if r["diffs"]}
    ledgered = len(failing & set(known))
    return (f"India: {len(ran) - len(failing)}/{len(ran)} cells pass, {ledgered} ledgered, "
            f"{len(failing) - ledgered} new, {len(cells) - len(ran)} skipped")  # fmt: skip


def report_md(results: dict[str, Any]) -> str:
    ran = [r for r in results.values() if "skipped" not in r]
    passed = sum(not r["diffs"] for r in ran)
    skipped = len(results) - len(ran)
    lines = ["# Cultural Gauntlet", "",
             f"{passed}/{len(ran)} cells pass, {len(ran) - passed} fail, {skipped} skipped (the page cannot hold "
             "the dialect's characters). A cell is one (dialect, code page, check group); each entry below is "
             "the groups that pass of those run.", "",
             "| dialect | " + " | ".join(COLUMNS) + " |", "|---|" + "---|" * len(COLUMNS)]  # fmt: skip
    for dialect in DIALECTS:
        row = []
        for col in COLUMNS:
            cells = [r for r in results.values() if r["dialect"] == dialect and r["page"] == col]
            if not cells:
                row.append("")
            elif all("skipped" in r for r in cells):
                row.append("skip")
            else:
                failed = [r["group"] for r in cells if r["diffs"]]
                row.append(f"{len(cells) - len(failed)}/{len(cells)}" + (f" ({', '.join(failed)})" if failed else ""))
        lines.append(f"| {dialect} | " + " | ".join(row) + " |")
    known = read_baseline()
    where = (f" (zone {INDIA_ZONE}; pages {', '.join(INDIA_PAGES)}; dialects {', '.join(INDIA_DIALECTS)};"
             f" every dialect in {', '.join(INDIA_PAGES)}).")  # fmt: skip
    lines += ["", "## India", "", india_summary(results, known) + where, ""]
    skipped = sorted({(r["dialect"], r["page"], r["skipped"]) for r in results.values() if "skipped" in r
                      and india_cell(r["dialect"], r["page"]) and r["group"] != RUN_GROUP})  # fmt: skip
    lines += [f"- `{d}|{c}` (skipped): {why}" for d, c, why in skipped]
    for cid, r in sorted(results.items()):
        if india_cell(r["dialect"], r["page"]) and r["diffs"]:
            lines.append(f"- `{cid}` ({'ledgered' if cid in known else 'NEW'}): {r['diffs'][0]}")
    lines += ["", "## Failing cells", ""]
    for cid, r in sorted(results.items()):
        if r["diffs"]:
            more = f" (+{len(r['diffs']) - 1} more)" if len(r["diffs"]) > 1 else ""
            lines.append(f"- `{cid}`: {r['diffs'][0]}{more}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="every dialect in every page (default: sampled)")
    ap.add_argument("--only", nargs="*", help="dialects to run (default: all)")
    ap.add_argument("--pages", nargs="*", help=f"columns to run, of {', '.join(COLUMNS)} (default: all)")
    ap.add_argument("--out", type=Path, help="write report.md and results.json here")
    ap.add_argument("--work", type=Path, help="keep the estates and the generated projects here")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4, help="cells run in parallel")
    ap.add_argument("--ci", action="store_true", help="fail when a cell fails that the baseline does not list")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--run", action="store_true", help="also execute the generated runtime under the JVM "
                    "environments (the runtime-run group; needs a JDK: javac + java)")  # fmt: skip
    args = ap.parse_args(argv)
    work = args.work or Path(tempfile.mkdtemp(prefix="cultural_gauntlet_"))
    results = run(work, args.full, args.jobs, set(args.only or ()), set(args.pages or ()), args.run)
    failing = {cid: r["diffs"][0] for cid, r in sorted(results.items()) if r["diffs"]}
    ran = sum("skipped" not in r for r in results.values())
    print(f"Cultural Gauntlet: {ran - len(failing)}/{ran} cells pass, {len(results) - ran} skipped")
    print(india_summary(results, read_baseline()))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "report.md").write_text(report_md(results), encoding="utf-8")
        (args.out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.update_baseline:
        if not args.run:  # a run without the JVM layer keeps its ledgered cells
            failing = {**{c: d for c, d in read_baseline().items() if c.endswith(f"|{RUN_GROUP}")}, **failing}
        write_baseline(failing)
        print(f"baseline: {len(failing)} failing cells recorded")
        return 0
    if args.ci:
        known = read_baseline()
        new = sorted(set(failing) - set(known))
        fixed = sorted((set(known) - set(failing)) & set(results))  # a cell this run did not run is not fixed
        for cid in new:
            print(f"NEW FAILING CELL {cid}: {failing[cid]}")
        if fixed:
            print(f"{len(fixed)} baseline cells now pass -- lower the baseline (--update-baseline): {fixed[:10]}")
        return 1 if new else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
