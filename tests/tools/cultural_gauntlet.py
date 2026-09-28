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

Part 3, the rest of #3834. C: the runtime locales tr-TR, ar-EG, th-TH-u-nu-thai and de-DE, each as the JVM's
default zone UTC, Asia/Kolkata and Europe/Berlin (on PINNED_CLOCK's day Berlin's clocks jump), join --run's
environments, and runtime-static traps their date formatters, collators and Unicode-digit tests. D, the
target database's collation: a KSDS keyed on PIC X(8) that a CICS program browses and a batch step reads,
generated for H2, PostgreSQL and MySQL (collation_* rows); `collation-static` checks #3822's contract (byte-wise
key columns, the code-page sort column, finders ordered by it, and a sequential READ in key order), and the
opt-in `--db` layer (`collation-db`) creates the generated table in each database this machine really has --
H2 from ~/.m2, a throwaway PostgreSQL cluster with a `C` and an `en_US.UTF-8` database; MySQL is skipped and
said so -- writes mixed-case, national-letter, digit, punctuation and trailing-space keys through the
generated CobolRecords, and reads them back through the generated finders' SQL against the mainframe's order:
the keys' bytes in the page, computed here. E, the input data (input_* rows, one per DB2 DATE format): fields
named DATUM / FECHA typed by their PICTURE and SQL type, the DB2 subsystem's EUR / USA / ISO forms, ROUNDED
ties, and full-width / Arabic-Indic / Thai / Devanagari digits in numeric input -- `input-static`, and under
--run the generated Db2Dates and CobolRecords against GnuCOBOL's (pinned) and DB2's answers in every
environment.

    python tests/tools/cultural_gauntlet.py --db --only collation_postgresql_en_us --pages cp277   # + a DB

Not yet: executing the seed cells under GnuCOBOL (the E answers are pinned from one GnuCOBOL run).
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
        # --run: CobolEdit.format(edited, 1234.50) as COBOL edits it (GnuCOBOL 3 prints ` $1,234.50`). #3933: a
        # multi-character currency string, which GnuCOBOL does not implement, is IBM Enterprise COBOL's rule
        # (Language Reference, PICTURE clause, floating insertion editing): the string floats as a unit into
        # the one symbol position left of the first significant digit, the other positions one character each
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
            "edited": " EUR 1,234.50",  # #3933: 13 characters, the record's 13 bytes
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
            "edited": " INR 1,234.50",  # #3933: the string's own space parts it from the amount
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
            "edited": "   Rs1,234.50",  # #3933: 'Rs' has no space of its own; the blanked lakh comma floats
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


def _write_estate(estate: Path, files: dict[str, str], column: str) -> str | None:
    """The estate's files in the column's encoding; the name of a file the page cannot hold, else None."""
    for rel, text in files.items():
        data = encode(text, column)
        if data is None:
            return rel
        (estate / rel).parent.mkdir(parents=True, exist_ok=True)
        (estate / rel).write_bytes(data)
    return None


def _convert(cell_dir: Path, estate: Path, db: Path, config: dict[str, Any]) -> tuple[Path, Path]:
    """The production path after the scan: the refractor's clean room, then COBOL-to-Java with `config`
    (target.json); (clean room, generated project)."""
    from unittest.mock import patch

    from gitgalaxy import cobol_refractor_controller as refractor
    from gitgalaxy import cobol_to_java_controller

    target = cell_dir / "target.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    with open(cell_dir / "pipeline.log", "w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        with patch("sys.argv", ["cobol-refractor", str(estate), "--galaxy-db", str(db)]):
            refractor.main()
        (clean,) = cell_dir.glob("estate_gitgalaxy_clean_*")
        argv = ["cobol-to-java", str(clean), "--header", str(cell_dir / "no-header.txt"), "--config", str(target)]
        with patch("sys.argv", argv):
            cobol_to_java_controller.main()
    (java,) = cell_dir.glob("estate_gitgalaxy_java_spring_*")
    return clean, java


def _java_sources(java: Path) -> dict[str, str]:
    modernized = java / "src" / "main" / "java" / "com" / "gitgalaxy" / "modernized"
    return {f.relative_to(modernized).as_posix(): f.read_text(encoding="utf-8")
            for f in sorted(modernized.rglob("*.java"))}  # fmt: skip


def _observe(cell_dir: Path, dialect: str, column: str) -> dict[str, Any]:
    """Build the estate, run scan -> refractor -> COBOL-to-Java, and collect what the checks read."""
    from gitgalaxy.core.source_text import decode_source
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

    obs: dict[str, Any] = {}
    estate = cell_dir / "estate"
    unfit = _write_estate(estate, estate_files(dialect), column)
    if unfit is not None:
        return {"skipped": f"{unfit} does not fit {column}"}
    data = (estate / "cbl" / "CULTSEED.cbl").read_bytes()  # the read every scan makes of it
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

    culture = {"zone": cell_zone(dialect, column)}  # #3824: an India cell's mainframe runs in IST
    clean, java = _convert(cell_dir, estate, db, {"data": {"code_page": data_page(column)}, "culture": culture})
    schema = clean / "02_cloud_schemas" / "CULTSEED_schema"
    obs["schema_json"] = json.loads(schema.with_suffix(".json").read_text(encoding="utf-8"))
    obs["schema_sql"] = schema.with_suffix(".sql").read_text(encoding="utf-8")
    ir_dump = json.loads((clean / "04_ir_state_dumps" / "CULTSEED_ir.json").read_text(encoding="utf-8"))
    obs["refractor_loc"] = ir_dump["metadata"].get("loc")
    for key, rel in (("entity", "entity/CultseedAcctRec.java"), ("acct_rec", "entity/vsam/AcctRec.java"),
                     ("cobol_records", "entity/vsam/CobolRecords.java"), ("decoder", "util/EbcdicDecoderUtil.java")):  # fmt: skip
        obs[key] = _java_file(cell_dir, rel)
    ticket = json.loads((java / "ai_agent_jobs" / "CULTSEED_port_ticket.json").read_text(encoding="utf-8"))
    obs["ticket_rounding"] = [(r["verb"], t["target"], t["java"]) for r in ticket["rounding"] for t in r["targets"]]
    obs["ticket_options"] = [(o["option"], o["value"]) for o in ticket["compiler_options"]]
    obs["ticket_rules"] = ticket["rules"]
    listing = java / "ai_agent_jobs" / "sources" / "cbl" / "CULTSEED.cbl.lst"
    obs["listing"] = listing.read_text(encoding="utf-8") if listing.is_file() else None
    obs["java_sources"] = _java_sources(java)
    return obs


def _run_cell(args: tuple[Any, ...]) -> dict[str, Any]:
    dialect, column, work, *layers = args
    execute = bool(layers and layers[0])
    dbs = layers[1] if len(layers) > 1 else None  # part 3 (D): --db's {target: spec}
    os.environ.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")  # a pool process of its own
    os.environ["GITGALAXY_DISABLE_GIT_HISTORY"] = "1"
    cell_dir = Path(work) / f"{dialect}__{column}"
    observe = _observe_collation if dialect in COLLATION_TARGETS else _observe_input if dialect in INPUT_FORMATS \
        else _observe  # fmt: skip
    try:
        obs = observe(cell_dir, dialect, column)
    except Exception:  # a crash is the cell's finding, not the gauntlet's end
        return {"error": traceback.format_exc(limit=4).strip().splitlines()[-1]}
    if "skipped" in obs:
        return obs
    key = "db_run" if dialect in COLLATION_TARGETS else "runtime_run"
    try:
        if dialect in COLLATION_TARGETS and dbs is not None:
            obs[key] = execute_db(cell_dir, dialect, column, obs["java_sources"], dbs[dialect])
        elif dialect in INPUT_FORMATS and execute:
            obs[key] = execute_input(cell_dir, column, obs["java_sources"], obs["ticket_rounding"])
        elif dialect in DIALECTS and execute:
            obs[key] = execute_cell(cell_dir, dialect, column, obs["java_sources"])
    except Exception:
        obs[key] = {"error": traceback.format_exc(limit=4).strip().splitlines()[-1]}
    return obs


# ---- the executed layer (--run): the generated runtime under the JVM environments -----------------
# #3821's environments (tests/tools/equivalence_java.py): hi-IN and en-IN in Asia/Kolkata, and the reference
# en-US / UTC. The generated classes that need no Spring context -- CobolRecords, CobolEdit and MainframeClock
# (its two Spring annotations stubbed, annotation-only) -- are compiled with a small driver and run in each.
# Part 3 (C, the rest): tr-TR (dotless i: "i".toUpperCase() is "İ"), ar-EG (Arabic-Indic digits from
# String.format), th-TH-u-nu-thai (Thai digits, the Buddhist-era calendar: Calendar says 2569) and de-DE (the
# decimal comma), each as the JVM's default zone UTC, Asia/Kolkata and Europe/Berlin -- whose clocks jump on
# PINNED_CLOCK's day (2026-03-29 02:30 does not exist there: a clock on the JVM's zone reads 03:30+0200).
RUNTIME_LOCALES = ["tr-TR", "ar-EG", "th-TH-u-nu-thai", "de-DE"]
RUNTIME_ZONES = ["UTC", INDIA_ZONE, "Europe/Berlin"]
JVM_ENVIRONMENTS = ["hindi", "en-IN/Asia/Kolkata", *(f"{loc}/{tz}" for loc in RUNTIME_LOCALES for tz in RUNTIME_ZONES),
                    "default"]  # fmt: skip
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
                + NumberFormat.getCurrencyInstance().format(1234567.89) + " "
                + java.util.Calendar.getInstance().get(java.util.Calendar.YEAR));
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
    """#3821's environment `name` as the JVM's own defaults: -Duser.language / -Duser.country / -Duser.timezone,
    and -Duser.extensions for a BCP-47 extension (th-TH-u-nu-thai: Thai digits; without it the JVM is th-TH)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from equivalence_java import environment

    env = environment(name)
    base, _, extension = env["locale"].partition("-u-")
    language, _, country = base.partition("-")
    flags = [f"-Duser.language={language}", f"-Duser.timezone={env['tz']}"]
    flags += [f"-Duser.country={country.split('-')[0]}"] if country else []
    return flags + ([f"-Duser.extensions=u-{extension}"] if extension else [])


def _java_charset(page: str) -> str:
    n = _page_number(page)
    return f"IBM{n:03d}" if n is not None and n < 1000 else f"IBM0{n}"


def execute_cell(cell_dir: Path, dialect: str, column: str, sources: dict[str, str]) -> dict[str, Any]:
    """Compile the generated runtime classes with the driver and run it in each JVM environment:
    {"envs": {environment: {name: value}}}, or {"skipped": why} without a JDK."""
    if jdk() is None:
        return {"skipped": "no JDK (javac + java): the executed layer needs one"}
    missing = [rel for rel in RUN_SOURCES if rel not in sources]
    if missing:
        return {"error": f"not generated: {', '.join(missing)}"}
    d = DIALECTS[dialect]
    currency = next((v for c, v, _ in d["expect"]["special_names"] if c == "CURRENCY"), "")
    zone = _ZONE_PROPERTY.search(sources["batch/MainframeClock.java"])  # the @Value default Spring would inject
    args = [_java_charset(data_page(column)), d["edited"], str(d["expect"]["decimal_comma"]).lower(), currency,
            PINNED_CLOCK, zone.group(1) if zone else ""]  # fmt: skip
    return _run_driver(cell_dir / "jvm", {rel: sources[rel] for rel in RUN_SOURCES}, "CulturalGauntletDriver",
                       _DRIVER, args, JVM_ENVIRONMENTS)  # fmt: skip


def _compile(root: Path, generated: dict[str, str], driver: str, source: str, classpath: str = "") -> str | None:
    """javac the generated classes (`rel` under the modernized package), the Spring stubs and the driver
    into root/classes; the first error line, or None."""
    tools = jdk()
    if tools is None:
        return "no JDK"
    src, classes = root / "src", root / "classes"
    files = {f"com/gitgalaxy/modernized/{rel}": text for rel, text in generated.items()}
    files.update(_SPRING_STUBS)
    files[f"{driver}.java"] = source
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    classes.mkdir(parents=True, exist_ok=True)
    cp = ["-cp", classpath] if classpath else []
    built = subprocess.run(  # noqa: S603 -- fixed argv: the local JDK over files this run wrote
        [tools[0], "-encoding", "UTF-8", *cp, "-d", str(classes), *(str(src / f) for f in files)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return f"javac: {(built.stderr or built.stdout).strip().splitlines()[:1]}" if built.returncode else None


def _java(root: Path, driver: str, flags: list[str], classpath: str = "") -> tuple[int, str]:
    """Run the compiled driver over root/args.txt: (exit code, stdout -- or the last stderr line)."""
    tools = jdk()
    if tools is None:  # _compile ran first, so there is one
        return 1, "no JDK"
    cp = os.pathsep.join([str(root / "classes"), *([classpath] if classpath else [])])
    ran = subprocess.run(  # noqa: S603 -- fixed argv: the local JDK, #3821's environment flags
        [tools[1], *flags, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", cp, driver,
         str(root / "args.txt")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )  # fmt: skip
    return ran.returncode, (str((ran.stderr or ran.stdout).strip().splitlines()[-1:]) if ran.returncode else ran.stdout)


def _lines(stdout: str) -> dict[str, str]:
    return dict(line.split("\t", 1) for line in stdout.splitlines() if "\t" in line)


def _run_driver(root: Path, generated: dict[str, str], driver: str, source: str, args: list[str],
                environments: list[str]) -> dict[str, Any]:  # fmt: skip
    """Compile, then run the driver in each JVM environment: {"envs": {environment: {name: value}}}. The
    arguments go as UTF-8 lines: a command line's encoding is the platform's, and '₹' must survive it."""
    failed = _compile(root, generated, driver, source)
    if failed:
        return {"error": failed}
    (root / "args.txt").write_text("".join(f"{a}\n" for a in args), encoding="utf-8")
    envs: dict[str, dict[str, str]] = {}
    for name in environments:
        code, out = _java(root, driver, jvm_flags(name))
        if code:
            return {"error": f"java ({name}): {out}"}
        envs[name] = _lines(out)
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
    # part 3 (C, the rest): the traps of tr-TR, ar-EG, th-TH-u-nu-thai and de-DE beyond case and String.format
    # java.time formats digits and the calendar the same in every locale (DecimalStyle.STANDARD, the temporal's
    # own chronology -- the --run layer confirms it under th-TH-u-nu-thai and ar-EG); what a locale changes is
    # a TEXT field (MMM, E, a, G, a zone name) and the week-based ones (Y, w, W, e, c)
    ("DateTimeFormatter.ofPattern without a Locale (month, day and AM/PM names, week fields)",
     re.compile(r'\bDateTimeFormatter\.ofPattern\(\s{0,8}(?:"[^"\n]{0,80}?(?:MMM|LLL|QQQ|qqq|[EecaGBzOvYwW])'
                r'[^"\n]{0,80}"|[\w.]{1,60})\s{0,8}\)')),
    ("a localized DateTimeFormatter (the default locale's pattern)",
     re.compile(r"\bDateTimeFormatter\.ofLocalized(?:Date|Time|DateTime)\(")),
    ("SimpleDateFormat without a Locale (Thai digits, the Buddhist calendar)",
     re.compile(r'\bnew\s{1,8}SimpleDateFormat\(\s{0,8}(?:"(?:[^"\\\n]|\\.){0,80}"|[\w.]{1,60})?\s{0,8}\)')),
    ("Collator without a Locale", re.compile(r"\bCollator\.getInstance\(\s{0,8}\)")),
    ("Character.isDigit / digit / getNumericValue (any script's digits, #3831)",
     re.compile(r"\bCharacter\.(?:isDigit|digit|getNumericValue)\(")),
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
    ref = run["envs"][REFERENCE_ENVIRONMENT]
    want = {**RUN_EXPECT, "date": RUN_DATE[zone], **({"edited": edited} if edited is not None else {})}
    out = [f"{k} ({REFERENCE_ENVIRONMENT}): want {v!r}, got {ref.get(k)!r}" for k, v in want.items() if ref.get(k) != v]
    return out + _across_environments(run["envs"])


def _across_environments(envs: dict[str, dict[str, str]]) -> list[str]:
    """Every environment prints what the reference prints; its canary proves it really was another JVM."""
    ref, out = envs[REFERENCE_ENVIRONMENT], []
    for name, got in envs.items():
        if name == REFERENCE_ENVIRONMENT:
            continue
        if got.get("canary") == ref.get("canary"):
            out.append(f"{name}: the JVM environment did not apply (canary {got.get('canary')!r})")
        elif "-u-nu-thai" in name and not any("\u0e50" <= ch <= "\u0e59" for ch in got.get("canary", "")):
            out.append(f"{name}: the JVM prints no Thai digits (canary {got.get('canary')!r})")  # -u-nu-thai lost
        out += [f"{k} differs in {name}: {ref.get(k)!r} ({REFERENCE_ENVIRONMENT}) vs {got.get(k)!r}"
                for k in sorted(set(ref) | set(got)) if k != "canary" and got.get(k) != ref.get(k)]  # fmt: skip
    return out


def check(dialect: str, column: str, obs: dict[str, Any]) -> dict[str, list[str]]:
    """{group: its differences} of one (dialect, column) against the dialect's declared behaviour."""
    if "error" in obs:
        return {g: [f"pipeline failed: {obs['error']}"] for g in groups(dialect)}
    if dialect in COLLATION_TARGETS:  # part 3, D
        return check_collation(dialect, column, obs)
    if dialect in INPUT_FORMATS:  # part 3, E
        return check_input(dialect, column, obs)
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


# ---- part 3, D: the target database's collation (#3822) ---------------------------------------------
# A KSDS keyed on a PIC X(8) field: a CICS program browses it (STARTBR / READNEXT / READPREV) and a batch step
# reads it sequentially. VSAM hands both the records in the key's BYTE order in the data page -- lower case
# before upper, letters before digits (ASCII: the reverse), national letters where the page puts them -- and a
# key that differs only in trailing spaces is the same 8-byte key. The generated repository must keep that
# order on every target database, whatever its own collation (MySQL's utf8mb4_0900_ai_ci makes 'a' = 'A' = 'á').
COLL_REC = """\
       01  CUST-REC.
           05 CUST-KEY         PIC X(8).
           05 CUST-NAME        PIC X(20).
"""
COLL_CICS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUSTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY CUSTREC.
       PROCEDURE DIVISION.
           EXEC CICS READ FILE('CUSTF') INTO(CUST-REC)
                RIDFLD(CUST-KEY) END-EXEC.
           EXEC CICS WRITE FILE('CUSTF') FROM(CUST-REC)
                RIDFLD(CUST-KEY) END-EXEC.
           EXEC CICS STARTBR FILE('CUSTF') RIDFLD(CUST-KEY) END-EXEC.
           EXEC CICS READNEXT FILE('CUSTF') INTO(CUST-REC)
                RIDFLD(CUST-KEY) END-EXEC.
           EXEC CICS READPREV FILE('CUSTF') INTO(CUST-REC)
                RIDFLD(CUST-KEY) END-EXEC.
           EXEC CICS ENDBR FILE('CUSTF') END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""
COLL_BATCH = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUSTBAT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-FILE ASSIGN TO CUSTDD
               ORGANIZATION IS INDEXED
               ACCESS MODE IS SEQUENTIAL
               RECORD KEY IS CUST-KEY.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-FILE.
           COPY CUSTREC.
       PROCEDURE DIVISION.
           OPEN INPUT CUST-FILE.
           READ CUST-FILE.
           CLOSE CUST-FILE.
           STOP RUN.
"""
COLL_JOB = """\
//CUSTJOB  JOB CLASS=A
//DEFINE   EXEC PGM=IDCAMS
//SYSIN    DD *
   DEFINE CLUSTER (NAME(APP.CUST.KSDS) INDEXED -
          KEYS(8 0) RECORDSIZE(28 28))
/*
//STEP1    EXEC PGM=CUSTBAT
//CUSTDD   DD DSN=APP.CUST.KSDS,DISP=SHR
"""
COLL_CSD = """\
 DEFINE TRANSACTION(CUST) GROUP(APP)
        PROGRAM(CUSTCICS)
 DEFINE FILE(CUSTF) GROUP(APP)
        DSNAME(APP.CUST.KSDS)
"""
COLLATION_ESTATE = {"cbl/CUSTCICS.cbl": COLL_CICS, "cbl/CUSTBAT.cbl": COLL_BATCH, "cpy/CUSTREC.cpy": COLL_REC,
                    "jcl/CUSTJOB.jcl": COLL_JOB, "csd/APP.csd": COLL_CSD}  # fmt: skip
# The targets: the generated project's database.engine, and the database's own collation (what an ORDER BY
# on the key column itself follows -- the canary: it must differ from the mainframe's order).
COLLATION_TARGETS: dict[str, dict[str, str]] = {
    "collation_h2": {"engine": "h2", "collation": "H2's default (code points)"},
    "collation_postgresql_c": {"engine": "postgresql", "collation": "C"},
    "collation_postgresql_en_us": {"engine": "postgresql", "collation": "en_US.UTF-8"},
    "collation_mysql_ai_ci": {"engine": "mysql", "collation": "utf8mb4_0900_ai_ci"},
}
COLLATION_GROUPS = ["collation-static", "runtime-static"]
DB_GROUP = "collation-db"  # the executed layer: only with --db, and only on a database this machine has
KEY_WIDTH = 8
# The keys, in the (scrambled) order the program WRITEs them: mixed case, national letters, digits and
# letters, punctuation, and `ABC ` -- the same 8-byte key as `ABC`, so VSAM rejects it as a duplicate.
COLLATION_KEYS = ["ZZ", "abc", "1A", "ÆBLE", "ABC", "A-1", "Abc", "ØRE", "123", "ÅS", "A 1", "ÄRGER", "aBC",
                  "ÑANDU", "NANDU", "A1", "A.1", "#1", "@1", "é1", "E1", "ABC "]  # fmt: skip
FROM_KEY = "A1"  # STARTBR / READPREV's RIDFLD
_COLLATION_WHAT = {
    "rejected": "WRITE duplicates (the same 8-byte key)",
    "browse": "STARTBR at LOW-VALUES + READNEXT (the generated finder)",
    "browse-from": f"STARTBR at {FROM_KEY!r} + READNEXT",
    "browse-back": f"STARTBR at {FROM_KEY!r} + READPREV",
    "read-all": "the batch step's sequential READ (the generated readAll: findAll())",
}


def collation_oracle(keys: list[str], page: str, start: str, width: int = KEY_WIDTH) -> dict[str, str]:
    """The mainframe's answers, computed independently of the converter: each key as the program's
    PIC X(8) holds it (space-padded) in the page's bytes; VSAM orders by those bytes and rejects a WRITE
    whose bytes an earlier record has. `|`-joined, trailing spaces dropped."""
    seen: dict[bytes, str] = {}
    rejected = []
    for key in keys:
        b = key.ljust(width).encode(page)
        if b in seen:
            rejected.append(key.rstrip())
        else:
            seen[b] = key.rstrip()
    order = sorted(seen)
    s = start.ljust(width).encode(page)
    return {
        "rejected": "|".join(rejected),
        "browse": "|".join(seen[b] for b in order),
        "browse-from": "|".join(seen[b] for b in order if b >= s),
        "browse-back": "|".join(seen[b] for b in reversed(order) if b <= s),
        "read-all": "|".join(seen[b] for b in order),  # a sequential READ of a KSDS is in key order too
    }


def collation_static_want(engine: str, page: str) -> list[tuple[str, str]]:
    """(file, text) #3822's contract generates for the engine: String key and sort columns compared byte by byte
    (COLLATE "C" on PostgreSQL, utf8mb4_bin on MySQL, H2's own code-point default), the sort column filled with
    the key's bytes in the declared page, and the browse finders ordered by it."""
    how = {"h2": None, "postgresql": 'COLLATE \\"C\\"', "mysql": "CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"}[engine]

    def column(name: str, width: int) -> str:
        spec = f"length = {width}" if how is None else f'columnDefinition = "varchar({width}) {how}"'
        return f'@Column(name = "{name}", {spec})'

    by = "CustKeySort"
    return [
        ("entity/vsam/CustRec.java", column("CUST_KEY", KEY_WIDTH)),
        ("entity/vsam/CustRec.java", column("CUST_KEY_SORT", 2 * KEY_WIDTH)),
        ("entity/vsam/CustRec.java", f'this.custKeySort = CobolRecords.sortKey(custKey, "{page}");'),
        ("repository/vsam/CustRecRepository.java",
         f"findBy{by}GreaterThanEqualOrderBy{by}Asc(String custKeySort, Pageable page);"),
        ("repository/vsam/CustRecRepository.java",
         f"findBy{by}LessThanEqualOrderBy{by}Desc(String custKeySort, Pageable page);"),
        ("service/CustcicsService.java", f'findBy{by}GreaterThanEqualOrderBy{by}Asc(CobolRecords.sortKey(from, "{page}"), '),
        ("service/CustcicsService.java", f'findBy{by}LessThanEqualOrderBy{by}Desc(CobolRecords.sortKey(from, "{page}"), '),
    ]  # fmt: skip


_READ_ALL = re.compile(r"public List<CustRec> readAllCustFile\(\) \{\s{1,40}return ([^;\n]{1,200});")


def collation_static_diffs(sources: dict[str, str], ticket_rules: list[str], engine: str, page: str) -> list[str]:
    out = []
    for rel, text in collation_static_want(engine, page):
        if rel not in sources:
            out.append(f"{rel}: not generated (want `{text}`)")
        elif text not in sources[rel]:
            out.append(f"{rel}: missing `{text}`")
    # a sequential READ of a KSDS is in key order: a repository call with no ORDER BY hands back the database's
    # heap order (insertion order on PostgreSQL), not the mainframe's
    read_all = _READ_ALL.search(sources.get("service/CustbatService.java", ""))
    if read_all is None:
        out.append("service/CustbatService.java: no readAllCustFile (the batch step's sequential READ)")
    elif "Sort" not in read_all.group(1):
        out.append(f"CustbatService.readAllCustFile: `return {read_all.group(1)};` has no ORDER BY -- a sequential "
                   f"READ of the KSDS returns its records in key order ({page} bytes, CUST_KEY_SORT)")  # fmt: skip
    if not any("Order and compare VSAM / DB2 keys by the source code page's bytes" in r for r in ticket_rules):
        out.append("CUSTCICS port ticket: no key-order rule (#3822)")
    return out


_TABLE = re.compile(r'@Table\(name = "(\w{1,64})"\)')
_FIELD = re.compile(r"(@Id\s{1,12})?@Column\(([^\n]{1,300})\)\s{1,12}private (\w{1,40}) \w{1,64};")
_ATTR = re.compile(r'(\w{1,20}) = ("(?:[^"\\]|\\.){0,200}"|\d{1,6})')


def entity_ddl(entity: str) -> tuple[str, str]:
    """(table, CREATE TABLE) of a generated entity as Hibernate's ddl-auto renders its @Column mappings: a
    columnDefinition verbatim, else the Java type's column (varchar(length), 255 by default)."""
    table = _TABLE.search(entity)
    if table is None:
        raise ValueError("no @Table in the entity")
    cols, key = [], None
    for m in _FIELD.finditer(entity):
        attrs = {k: _java_unescape(v[1:-1]) if v.startswith('"') else v for k, v in _ATTR.findall(m.group(2))}
        jtype = m.group(3)
        if "columnDefinition" in attrs:
            sql = attrs["columnDefinition"]
        elif jtype == "String":
            sql = f"varchar({attrs.get('length', 255)})"
        elif jtype in ("Integer", "Long", "BigDecimal"):
            sql = {"Integer": "integer", "Long": "bigint"}.get(jtype) or \
                f"numeric({attrs.get('precision', 38)}, {attrs.get('scale', 2)})"  # fmt: skip
        else:
            raise ValueError(f"no column type for {jtype} {attrs.get('name')}")
        if m.group(1):
            key = attrs["name"]
        cols.append(f"{attrs['name']} {sql}" + (" not null" if m.group(1) else ""))
    if key is None:
        raise ValueError("no @Id column in the entity")
    return table.group(1), f"CREATE TABLE {table.group(1)} ({', '.join(cols)}, PRIMARY KEY ({key}))"


_COLLATION_DRIVER = """\
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;

/** #3834 (D): the generated key mapping in a real database, one `name<TAB>value` line each. Each key goes in as
 *  the generated codec reads it (the record's space-padded bytes) with its sort column filled by the generated
 *  CobolRecords.sortKey, as @PrePersist fills it; then the generated finders' SQL, findAll()'s, and the
 *  database's own order of the key column. */
public class CollationDriver {
    public static void main(String[] argv) throws Exception {
        List<String> a = Files.readAllLines(Path.of(argv[0]), StandardCharsets.UTF_8);
        String url = a.get(0), user = a.get(1), page = a.get(2), from = a.get(4);
        String table = a.get(5), key = a.get(6), sort = a.get(7);
        int width = Integer.parseInt(a.get(3));
        Charset text = Charset.forName(page);
        try (Connection c = DriverManager.getConnection(url, user, "")) {
            try (Statement s = c.createStatement()) {
                for (String line : a) {
                    if (line.startsWith("SQL ")) {
                        s.execute(line.substring(4));
                    }
                }
            }
            List<String> rejected = new ArrayList<>();
            try (PreparedStatement p = c.prepareStatement(
                    "INSERT INTO " + table + " (" + key + ", " + sort + ") VALUES (?, ?)")) {
                for (String line : a) {
                    if (!line.startsWith("KEY ")) {
                        continue;
                    }
                    String k = record(line.substring(4), width, text);
                    p.setString(1, k);
                    p.setString(2, CobolRecords.sortKey(k, page));
                    try {
                        p.executeUpdate();
                    } catch (SQLException e) {
                        if (e.getSQLState() == null || !e.getSQLState().startsWith("23")) {
                            throw e;
                        }
                        rejected.add(k.stripTrailing());
                    }
                }
            }
            out("rejected", String.join("|", rejected));
            String next = "SELECT " + key + " FROM " + table + " WHERE " + sort + " >= ? ORDER BY " + sort + " ASC";
            String prev = "SELECT " + key + " FROM " + table + " WHERE " + sort + " <= ? ORDER BY " + sort + " DESC";
            String start = CobolRecords.sortKey(record(from, width, text), page);
            out("browse", keys(c, next, CobolRecords.sortKey(new String(new char[width]), page)));  // LOW-VALUES
            out("browse-from", keys(c, next, start));
            out("browse-back", keys(c, prev, start));
            out("read-all", keys(c, "SELECT " + key + " FROM " + table, null));
            out("db-order", keys(c, "SELECT " + key + " FROM " + table + " ORDER BY " + key, null));
            for (String line : a) {
                if (line.startsWith("INFO ")) {
                    out("collation", keys(c, line.substring(5), null));
                }
            }
        }
    }

    /** The key as the entity's codec reads it from its record: putText pads it, text reads it back. */
    private static String record(String value, int width, Charset text) {
        byte[] rec = CobolRecords.blank(width, text);
        CobolRecords.putText(rec, 0, width, value, text);
        return CobolRecords.text(rec, 0, width, text);
    }

    private static String keys(Connection c, String sql, String arg) throws SQLException {
        try (PreparedStatement p = c.prepareStatement(sql)) {
            if (arg != null) {
                p.setString(1, arg);
            }
            List<String> got = new ArrayList<>();
            try (ResultSet r = p.executeQuery()) {
                while (r.next()) {
                    got.add(r.getString(1).stripTrailing());
                }
            }
            return String.join("|", got);
        }
    }

    private static void out(String name, String value) {
        System.out.println(name + "\\t" + value);
    }
}
"""


def _maven_jar(group: str, artifact: str) -> str | None:
    """The newest `artifact` jar the local Maven repository (~/.m2) holds, or None."""
    root = Path.home() / ".m2" / "repository" / group.replace(".", "/") / artifact
    jars = [j for j in root.glob(f"*/{artifact}-*.jar") if not j.name.endswith(("-sources.jar", "-javadoc.jar"))]
    version = lambda j: [int(x) if x.isdigit() else -1 for x in re.split(r"[.-]", j.parent.name)]  # noqa: E731
    return str(max(jars, key=version)) if jars else None


def _pg_bin() -> Path | None:
    """The PostgreSQL server binaries (initdb, pg_ctl, psql): the PATH's, else Debian's newest."""
    found = shutil.which("initdb")
    if found:
        return Path(found).parent
    versions = [p for p in Path("/usr/lib/postgresql").glob("*/bin/initdb") if p.parts[-3].isdigit()]
    return max(versions, key=lambda p: int(p.parts[-3])).parent if versions else None


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextlib.contextmanager
def databases(work: Path) -> Any:
    """#3834 (D): the target databases this machine really has, {target: spec} or {target: {"skipped": why}}
    -- never faked. H2 in memory (its jar from ~/.m2); PostgreSQL as a throwaway cluster (initdb, trust
    auth, localhost on a free port, stopped on exit) holding a `C` and an `en_US.UTF-8` database; MySQL only
    where a server is at hand."""
    specs: dict[str, dict[str, Any]] = {}
    has_jdk = jdk() is not None
    h2 = _maven_jar("com.h2database", "h2")
    specs["collation_h2"] = (
        {"url": "jdbc:h2:mem:gauntlet", "user": "sa", "classpath": h2, "schema": False,
         "info": "SELECT 'H2 ' || H2VERSION()"}
        if h2 and has_jdk else {"skipped": "no JDK" if not has_jdk else "no H2 jar in ~/.m2"}
    )  # fmt: skip
    specs["collation_mysql_ai_ci"] = {"skipped": "no MySQL server on this machine (no docker image, no local "
                                                 "server): collation-static checks utf8mb4_bin"}  # fmt: skip
    pg_jar, pg_bin = _maven_jar("org.postgresql", "postgresql"), _pg_bin()
    pg_targets = [t for t, spec in COLLATION_TARGETS.items() if spec["engine"] == "postgresql"]
    data = work / "postgres"
    started = False
    try:
        why = ("no JDK" if not has_jdk else "no PostgreSQL JDBC jar in ~/.m2" if not pg_jar
               else "no PostgreSQL server binaries (initdb / pg_ctl)" if not pg_bin else None)  # fmt: skip
        if why is None and pg_bin is not None:
            port = _free_port()
            why = _start_postgres(pg_bin, data, port)
            started = why is None
        for target in pg_targets:
            locale = COLLATION_TARGETS[target]["collation"]
            if why is not None or pg_bin is None:
                specs[target] = {"skipped": why}
                continue
            name = "gauntlet_" + re.sub(r"\W", "_", locale.lower())
            made = subprocess.run(  # noqa: S603 -- the local psql, a CREATE DATABASE this run names
                [str(pg_bin / "psql"), "-h", "localhost", "-p", str(port), "-U", "gauntlet", "-d", "postgres", "-c",
                 f"CREATE DATABASE {name} TEMPLATE template0 ENCODING 'UTF8' LOCALE '{locale}'"],
                capture_output=True, text=True, timeout=60, check=False,
            )  # fmt: skip
            specs[target] = (
                {"skipped": f"PostgreSQL has no {locale} locale here: {made.stderr.strip()[:120]}"}
                if made.returncode
                else {"url": f"jdbc:postgresql://localhost:{port}/{name}", "user": "gauntlet", "classpath": pg_jar,
                      "schema": True, "info": "SELECT datcollate FROM pg_database WHERE datname = current_database()"}
            )  # fmt: skip
        yield specs
    finally:
        if started and pg_bin is not None:
            subprocess.run(  # noqa: S603 -- the local pg_ctl over the cluster this run made
                [str(pg_bin / "pg_ctl"), "-D", str(data), "-m", "immediate", "stop"],
                capture_output=True, timeout=60, check=False,
            )  # fmt: skip


def _start_postgres(pg_bin: Path, data: Path, port: int) -> str | None:
    """A throwaway cluster in `data` on localhost:port (no Unix socket: a work path can be too long for one);
    None when it runs, else why not."""
    init = subprocess.run(  # noqa: S603 -- the local initdb over a directory this run made
        [str(pg_bin / "initdb"), "-D", str(data), "-U", "gauntlet", "--auth=trust", "-E", "UTF8", "--locale=C"],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    if init.returncode:
        return f"initdb failed: {init.stderr.strip()[-120:]}"
    options = f"-p {port} -c listen_addresses=localhost -c unix_socket_directories=''"
    start = subprocess.run(  # noqa: S603 -- the local pg_ctl over the cluster this run made
        [str(pg_bin / "pg_ctl"), "-D", str(data), "-o", options, "-l", str(data / "server.log"), "-w", "-t", "60",
         "start"],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    return f"pg_ctl start failed: {(start.stderr or start.stdout).strip()[-120:]}" if start.returncode else None


def execute_db(cell_dir: Path, target: str, column: str, sources: dict[str, str], spec: dict[str, Any]) -> dict:
    """#3834 (D): the generated table (entity_ddl) in the target database, the keys written through the
    generated CobolRecords, and what the generated finders read back: {"db": {name: value}, "ddl": ...}."""
    if "skipped" in spec:
        return {"skipped": spec["skipped"]}
    missing = [rel for rel in ("entity/vsam/CustRec.java", "entity/vsam/CobolRecords.java") if rel not in sources]
    if missing:
        return {"error": f"not generated: {', '.join(missing)}"}
    table, ddl = entity_ddl(sources["entity/vsam/CustRec.java"])
    schema = "s_" + re.sub(r"\W", "_", f"{target}_{column}").lower()  # cells share a database, not a schema
    setup = [f"CREATE SCHEMA {schema}", f"SET search_path TO {schema}"] if spec["schema"] else []
    args = [spec["url"], spec["user"], data_page(column), str(KEY_WIDTH), FROM_KEY, table, "CUST_KEY",
            "CUST_KEY_SORT", *(f"SQL {s}" for s in [*setup, ddl]), *(f"KEY {k}" for k in COLLATION_KEYS),
            f"INFO {spec['info']}"]  # fmt: skip
    root = cell_dir / "db"
    classpath = spec["classpath"]
    failed = _compile(root, {"entity/vsam/CobolRecords.java": sources["entity/vsam/CobolRecords.java"]},
                      "CollationDriver", _COLLATION_DRIVER, classpath)  # fmt: skip
    if failed:
        return {"error": failed}
    (root / "args.txt").write_text("".join(f"{a}\n" for a in args), encoding="utf-8")
    code, out = _java(root, "CollationDriver", jvm_flags(REFERENCE_ENVIRONMENT), classpath)
    return {"error": f"java: {out}"} if code else {"db": _lines(out), "ddl": ddl}


def collation_db_diffs(run: dict[str, Any], column: str) -> list[str]:
    """The database's answers against the mainframe's; and the canary: the database's own order of the key
    column must differ from the mainframe's, or these keys could not have told a wrong order apart."""
    if "error" in run:
        return [f"executed layer failed: {run['error']}"]
    got, want = run["db"], collation_oracle(COLLATION_KEYS, data_page(column), FROM_KEY)
    out = [f"{name} [{_COLLATION_WHAT[name]}]: want {v!r}, got {got.get(name)!r}"
           for name, v in want.items() if got.get(name) != v]  # fmt: skip
    if got.get("db-order") == want["browse"]:
        out.append(f"canary: the database's own ORDER BY CUST_KEY is the mainframe's order ({got.get('db-order')!r})")
    return out


def _observe_collation(cell_dir: Path, target: str, column: str) -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    estate = cell_dir / "estate"
    unfit = _write_estate(estate, COLLATION_ESTATE, column)
    if unfit is not None:
        return {"skipped": f"{unfit} does not fit {column}"}
    declared = () if column == CONTROL else ("--source-encoding", column)
    db = scan_to_db(estate, cell_dir / "scan", extra_args=declared)
    config = {"data": {"code_page": data_page(column)}, "database": {"engine": COLLATION_TARGETS[target]["engine"]},
              "culture": {"zone": cell_zone(target, column)}}  # fmt: skip
    _, java = _convert(cell_dir, estate, db, config)
    ticket = json.loads((java / "ai_agent_jobs" / "CUSTCICS_port_ticket.json").read_text(encoding="utf-8"))
    return {"java_sources": _java_sources(java), "ticket_rules": ticket["rules"]}


def check_collation(target: str, column: str, obs: dict[str, Any]) -> dict[str, list[str]]:
    sources = obs.get("java_sources") or {}
    engine = COLLATION_TARGETS[target]["engine"]
    out = {"collation-static": collation_static_diffs(sources, obs.get("ticket_rules") or [], engine,
                                                      data_page(column)),
           "runtime-static": runtime_static_diffs(sources, cell_zone(target, column))}  # fmt: skip
    if "db_run" in obs and "skipped" not in obs["db_run"]:
        out[DB_GROUP] = collation_db_diffs(obs["db_run"], column)
    return out


# ---- part 3, E: the input data -------------------------------------------------------------------------
# One program over a KSDS and a DB2 table: record fields named in German and Spanish (DATUM, FECHA) next to an
# English ACCT-DATE, DB2 DATE / TIME columns fetched into character host variables (the subsystem's DATE
# format EUR / USA / ISO, #3887's Db2Dates), rounding ties under ROUNDED and ROUNDED MODE NEAREST-EVEN (#3856),
# and FUNCTION NUMVAL over text that may hold full-width or Arabic-Indic digits (#3831).
INPUT_PROG = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INPTSEED.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT KUND-FILE ASSIGN TO KUNDDD
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS KUND-ID.
       DATA DIVISION.
       FILE SECTION.
       FD  KUND-FILE.
       01  KUND-REC.
           05 KUND-ID          PIC X(8).
           05 DATUM            PIC 9(8).
           05 FECHA            PIC X(10).
           05 ACCT-DATE        PIC 9(8).
           05 KUND-BAL         PIC S9(7)V99.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE DCLKUNDE END-EXEC.
       01  WS-RATE             PIC 9V9(4) VALUE 0.0125.
       01  WS-UP               PIC S9(7)V99.
       01  WS-EVEN             PIC S9(7)V99.
       01  WS-IN               PIC X(9).
       01  WS-NUM              PIC S9(7)V99.
       PROCEDURE DIVISION.
           OPEN I-O KUND-FILE
           READ KUND-FILE
           EXEC SQL SELECT DATUM, FECHA, ZEIT, ACCT_DATE
                INTO :K-DATUM, :K-FECHA, :K-ZEIT, :K-ACCT-DATE
                FROM KUNDE WHERE KUNDE_ID = :K-KUNDE-ID
           END-EXEC
           COMPUTE WS-UP ROUNDED = KUND-BAL * WS-RATE
           COMPUTE WS-EVEN ROUNDED MODE NEAREST-EVEN = KUND-BAL * WS-RATE
           COMPUTE WS-NUM = FUNCTION NUMVAL(WS-IN)
           REWRITE KUND-REC
           CLOSE KUND-FILE
           GOBACK.
"""
INPUT_DCL = """\
           EXEC SQL DECLARE KUNDE TABLE
           ( KUNDE_ID                       CHAR(8) NOT NULL,
             DATUM                          DATE,
             FECHA                          DATE,
             ZEIT                           TIME,
             ACCT_DATE                      CHAR(10)
           ) END-EXEC.
       01  DCLKUNDE.
           10 K-KUNDE-ID          PIC X(8).
           10 K-DATUM             PIC X(10).
           10 K-FECHA             PIC X(10).
           10 K-ZEIT              PIC X(8).
           10 K-ACCT-DATE         PIC X(10).
"""
INPUT_JOB = """\
//INPTJOB  JOB CLASS=A
//DEFINE   EXEC PGM=IDCAMS
//SYSIN    DD *
   DEFINE CLUSTER (NAME(APP.KUND.KSDS) INDEXED -
          KEYS(8 0) RECORDSIZE(43 43))
/*
//STEP1    EXEC PGM=INPTSEED
//KUNDDD   DD DSN=APP.KUND.KSDS,DISP=OLD
"""
INPUT_ESTATE = {"cbl/INPTSEED.cbl": INPUT_PROG, "cpy/DCLKUNDE.cpy": INPUT_DCL, "jcl/INPTJOB.jcl": INPUT_JOB}
# the DB2 subsystem's DATE / TIME format (culture.db2_date_format) of each input cell
INPUT_FORMATS = {"input_eur": "eur", "input_usa": "usa", "input_iso": "iso"}
INPUT_GROUPS = ["input-static", "runtime-static"]
# DB2 for z/OS SQL Reference, "Datetime values": DATE 2026-09-26 and TIME 14:30:05 as a character host
# variable holds them in each format (USA drops the seconds)
DB2_CHARACTER_FORMS = {"eur": ("26.09.2026", "14.30.05"), "usa": ("09/26/2026", "02:30 PM"),
                       "iso": ("2026-09-26", "14.30.05")}  # fmt: skip
# A field is what its PICTURE says, whatever its name's language: DATUM and ACCT-DATE are both PIC 9(8)
INPUT_CODEC = [
    "r.datum = CobolRecords.toInteger(CobolRecords.zoned(rec, 8, 8, 0, text));",
    "r.fecha = CobolRecords.text(rec, 16, 10, text);",
    "r.acctDate = CobolRecords.toInteger(CobolRecords.zoned(rec, 26, 8, 0, text));",
    "r.kundBal = CobolRecords.zoned(rec, 34, 9, 2, text);",
]
INPUT_SCHEMA = {"DATUM": "INTEGER", "FECHA": "VARCHAR(10)", "ACCT_DATE": "INTEGER"}  # the clean room's columns
INPUT_ROUNDING = [("COMPUTE", "WS-UP", "HALF_UP"), ("COMPUTE", "WS-EVEN", "HALF_EVEN")]
# Numeric text a screen or a file may carry. COBOL's answer, run under GnuCOBOL 3 -std=ibm (the harness's
# image): FUNCTION TEST-NUMVAL of full-width (U+FF11-U+FF13) and Arabic-Indic `١٢٣` is 1 (invalid at the first
# character), the NUMERIC class test is false, and arithmetic on such a zoned field is a data exception
# (-debug: "not numeric"; IBM: S0C7) -- invalid data, never 123. #3831: CobolRecords throws.
NUMVAL_INPUTS = [" 123.45 ", "\uff11\uff12\uff13", "١٢٣", "๑๒๓", "१२३", "12\uff13"]  # full-width U+FF11..
NUMVAL_WANT = "123.45|invalid|invalid|invalid|invalid|invalid"
# ROUNDED ties, KUND-BAL * WS-RATE for KUND-BAL 2.00 / -2.00 / 2.80 (0.025, -0.025, 0.035) and the integer
# ties 2.5 / -2.5 / 3.5, as GnuCOBOL 3 -std=ibm computes them: ROUNDED is half away from zero, NEAREST-EVEN
# half to even. The Java side applies the port ticket's RoundingMode for the target.
TIES_WANT = {"WS-UP": "0.03 -0.03 0.04 3 -3 4", "WS-EVEN": "0.02 -0.02 0.04 2 -2 4"}


def input_run_want(fmt: str) -> dict[str, str]:
    date, time = DB2_CHARACTER_FORMS[fmt]
    return {
        "date": f"{date} {time}",
        # DB2 reads a character DATE in any of its formats, whatever the subsystem's
        "parse": "2026-09-26 2026-09-26 2026-09-26 2026-09-26T14:30:05.123456",
        # ... and only in ASCII digits: DB2 rejects `٢٦.٠٩.٢٠٢٦` (SQLCODE -180), so must the port
        "parse-foreign": "invalid invalid invalid",
        "numval": NUMVAL_WANT,
        # a number a locale-bound formatter printed (Thai, Arabic digits) is no number to COBOL
        "numval-locale": "invalid invalid",
        # DATUM PIC 9(8): the page's own digits read; a UTF-8 record's full-width / Arabic-Indic digits are no
        # zoned digits (8 bytes, fewer characters)
        "zoned": "20260926 invalid invalid",
        **{f"ties {t}": v for t, v in TIES_WANT.items()},
    }


_INPUT_DRIVER = """\
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.repository.db2.Db2Dates;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.NumberFormat;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.Callable;

/** #3834 (E): the generated runtime over input data, one `name<TAB>value` line each. */
public class InputDriver {
    public static void main(String[] argv) throws Exception {
        List<String> a = Files.readAllLines(Path.of(argv[0]), StandardCharsets.UTF_8);
        Charset page = Charset.forName(a.get(0));
        out("canary", Locale.getDefault().toLanguageTag() + " " + ZoneId.systemDefault() + " "
                + NumberFormat.getCurrencyInstance().format(1234567.89));
        out("date", Db2Dates.date(java.sql.Date.valueOf("2026-09-26")) + " "
                + Db2Dates.time(java.sql.Time.valueOf("14:30:05")));
        out("parse", Db2Dates.parseDate("26.09.2026") + " " + Db2Dates.parseDate("09/26/2026") + " "
                + Db2Dates.parseDate("2026-09-26") + " " + Db2Dates.parseTimestamp("2026-09-26-14.30.05.123456"));
        out("parse-foreign", attempt(() -> Db2Dates.parseDate("\\u0662\\u0666.\\u0660\\u0669.\\u0662\\u0660\\u0662\\u0666"))
                + " " + attempt(() -> Db2Dates.parseDate("\\uff12\\uff10\\uff12\\uff16-09-26"))
                + " " + attempt(() -> Db2Dates.parseTimestamp("2026-09-26-\\u0661\\u0664.\\u0663\\u0660.05.000000")));
        List<String> numval = new ArrayList<>();
        for (String line : a) {
            if (line.startsWith("NUM ")) {
                numval.add(attempt(() -> CobolRecords.numval(line.substring(4)).toPlainString()));
            }
        }
        out("numval", String.join("|", numval));
        String thai = String.format(Locale.forLanguageTag("th-TH-u-nu-thai"), "%d", 123);
        String arabic = String.format(Locale.forLanguageTag("ar-EG"), "%.2f", new BigDecimal("123.45"));
        out("numval-locale", attempt(() -> CobolRecords.decimal(thai).toPlainString()) + " "
                + attempt(() -> CobolRecords.decimal(arabic).toPlainString()));
        byte[] own = "20260926".getBytes(page);
        byte[] wide = "\\uff12\\uff10\\uff12\\uff16".getBytes(StandardCharsets.UTF_8);
        byte[] indic = "\\u0662\\u0660\\u0662\\u0666".getBytes(StandardCharsets.UTF_8);
        out("zoned", attempt(() -> CobolRecords.zoned(own, 0, 8, 0, page).toPlainString()) + " "
                + attempt(() -> CobolRecords.zoned(wide, 0, 8, 0, StandardCharsets.UTF_8).toPlainString()) + " "
                + attempt(() -> CobolRecords.zoned(indic, 0, 8, 0, StandardCharsets.UTF_8).toPlainString()));
        BigDecimal rate = new BigDecimal("0.0125");
        for (String line : a) {
            if (line.startsWith("TIES ")) {  // TIES <target> <RoundingMode>: the port ticket's
                String[] t = line.split(" ");
                RoundingMode mode = RoundingMode.valueOf(t[2]);
                List<String> got = new ArrayList<>();
                for (String bal : new String[] {"2.00", "-2.00", "2.80"}) {
                    got.add(new BigDecimal(bal).multiply(rate).setScale(2, mode).toPlainString());
                }
                for (String tie : new String[] {"2.5", "-2.5", "3.5"}) {
                    got.add(new BigDecimal(tie).setScale(0, mode).toPlainString());
                }
                out("ties " + t[1], String.join(" ", got));
            }
        }
    }

    private static String attempt(Callable<Object> f) {
        try {
            return String.valueOf(f.call());
        } catch (Exception e) {
            return "invalid";
        }
    }

    private static void out(String name, String value) {
        System.out.println(name + "\\t" + value);
    }
}
"""


def _observe_input(cell_dir: Path, name: str, column: str) -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    estate = cell_dir / "estate"
    unfit = _write_estate(estate, INPUT_ESTATE, column)
    if unfit is not None:
        return {"skipped": f"{unfit} does not fit {column}"}
    declared = () if column == CONTROL else ("--source-encoding", column)
    db = scan_to_db(estate, cell_dir / "scan", extra_args=declared)
    culture = {"zone": cell_zone(name, column), "db2_date_format": INPUT_FORMATS[name]}
    clean, java = _convert(cell_dir, estate, db, {"data": {"code_page": data_page(column)}, "culture": culture})
    ticket = json.loads((java / "ai_agent_jobs" / "INPTSEED_port_ticket.json").read_text(encoding="utf-8"))
    return {
        "java_sources": _java_sources(java),
        "schema_sql": (clean / "02_cloud_schemas" / "INPTSEED_schema.sql").read_text(encoding="utf-8"),
        "ticket_rounding": [(r["verb"], t["target"], t["java"]) for r in ticket["rounding"] for t in r["targets"]],
        "ticket_rules": ticket["rules"],
    }


def input_static_diffs(obs: dict[str, Any], fmt: str) -> list[str]:
    sources = obs.get("java_sources") or {}
    fmt_up = fmt.upper()
    want = [("entity/vsam/KundRec.java", line) for line in INPUT_CODEC] + [
        ("entity/vsam/KundRec.java", "private Integer datum;"),
        ("entity/vsam/KundRec.java", "private String fecha;"),
        ("entity/vsam/KundRec.java", "private Integer acctDate;"),
        # a DB2 DATE / TIME column is typed by its SQL type -- DATUM and FECHA are dates, ACCT_DATE a CHAR
        ("dto/db2/KundeRow.java", "private LocalDate datum;"),
        ("dto/db2/KundeRow.java", "private LocalDate fecha;"),
        ("dto/db2/KundeRow.java", "private LocalTime zeit;"),
        ("dto/db2/KundeRow.java", "private String acctDate;"),
        ("repository/db2/KundeRepository.java", " * DATUM, FECHA, ZEIT: into or from a character host variable, "
                                                f"convert with Db2Dates (DB2 {fmt_up} format)."),
        ("repository/db2/Db2Dates.java", f'public static final String FORMAT = "{fmt_up}";'),
    ]  # fmt: skip
    out = [f"{rel}: not generated (want `{text}`)" if rel not in sources else f"{rel}: missing `{text}`"
           for rel, text in want if text not in sources.get(rel, "")]  # fmt: skip
    for col, sql in INPUT_SCHEMA.items():
        got = re.search(rf"^\s*{col}\s+(\S+(?: \d+\))?)", obs.get("schema_sql") or "", re.M)
        if (got.group(1).rstrip(",") if got else None) != sql:
            out.append(f"clean-room schema {col}: want {sql!r}, got {got and got.group(1)!r}")
    if [tuple(r) for r in obs.get("ticket_rounding") or []] != INPUT_ROUNDING:
        out.append(f"ticket rounding: want {INPUT_ROUNDING!r}, got {obs.get('ticket_rounding')!r}")
    if not any("CobolRecords.numval(text, decimalPoint)" in r for r in obs.get("ticket_rules") or []):
        out.append("ticket rules: no NUMVAL rule (#3831)")
    return out


def execute_input(cell_dir: Path, column: str, sources: dict[str, str],
                  rounding: list[tuple[str, str, str]]) -> dict[str, Any]:  # fmt: skip
    if jdk() is None:
        return {"skipped": "no JDK (javac + java): the executed layer needs one"}
    rels = ["entity/vsam/CobolRecords.java", "repository/db2/Db2Dates.java"]
    missing = [rel for rel in rels if rel not in sources]
    if missing:
        return {"error": f"not generated: {', '.join(missing)}"}
    args = [_java_charset(data_page(column)), *(f"NUM {n}" for n in NUMVAL_INPUTS),
            *(f"TIES {target} {java}" for _, target, java in rounding)]  # fmt: skip
    return _run_driver(cell_dir / "jvm", {rel: sources[rel] for rel in rels}, "InputDriver", _INPUT_DRIVER, args,
                       JVM_ENVIRONMENTS)  # fmt: skip


def input_run_diffs(run: dict[str, Any], fmt: str) -> list[str]:
    if "error" in run:
        return [f"executed layer failed: {run['error']}"]
    ref = run["envs"][REFERENCE_ENVIRONMENT]
    out = [f"{k} ({REFERENCE_ENVIRONMENT}): want {v!r}, got {ref.get(k)!r}"
           for k, v in input_run_want(fmt).items() if ref.get(k) != v]  # fmt: skip
    return out + _across_environments(run["envs"])


def check_input(name: str, column: str, obs: dict[str, Any]) -> dict[str, list[str]]:
    sources = obs.get("java_sources") or {}
    out = {"input-static": input_static_diffs(obs, INPUT_FORMATS[name]),
           "runtime-static": runtime_static_diffs(sources, cell_zone(name, column))}  # fmt: skip
    if "runtime_run" in obs and "skipped" not in obs["runtime_run"]:
        out[RUN_GROUP] = input_run_diffs(obs["runtime_run"], INPUT_FORMATS[name])
    return out


def groups(dialect: str, execute: bool = False, db: bool = False) -> list[str]:
    """The check groups of a cell of `dialect`'s family, with the executed layers asked for."""
    if dialect in COLLATION_TARGETS:
        return COLLATION_GROUPS + ([DB_GROUP] if db else [])
    return (INPUT_GROUPS if dialect in INPUT_FORMATS else GROUPS) + ([RUN_GROUP] if execute else [])


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
    # part 3: each database target and each DB2 date format in every column with --full; sampled, each in one
    # page, so the sampled run meets a Danish, a German, a US and an Indian page and the UTF-8 control
    for name, sample in (*SAMPLED_COLLATION.items(), *SAMPLED_INPUT.items()):
        out += [(name, c) for c in (COLUMNS if full else [sample])]
    return [(d, c) for d, c in out if (not only or d in only) and (not pages or c in pages)]


SAMPLED_COLLATION = {"collation_h2": "cp037", "collation_postgresql_c": "cp277", "collation_postgresql_en_us": "cp273",
                     "collation_mysql_ai_ci": "cp1140"}  # fmt: skip
SAMPLED_INPUT = {"input_eur": "cp273", "input_usa": "cp037", "input_iso": CONTROL}


def run(work: Path, full: bool = False, jobs: int = 4, only: set[str] | None = None,
        pages: set[str] | None = None, execute: bool = False, db: bool = False) -> dict[str, Any]:  # fmt: skip
    from concurrent.futures import ProcessPoolExecutor

    pairs = plan(full, only, pages)
    with contextlib.ExitStack() as stack:
        dbs = stack.enter_context(databases(work)) if db and any(d in COLLATION_TARGETS for d, _ in pairs) else None
        with ProcessPoolExecutor(max_workers=max(1, jobs)) as pool:
            observed = list(pool.map(_run_cell, [(d, c, str(work), execute, dbs) for d, c in pairs]))
    results: dict[str, Any] = {}
    for (dialect, column), obs in zip(pairs, observed):
        if "skipped" in obs:
            for g in groups(dialect, execute, db):
                results[f"{dialect}|{column}|{g}"] = {"dialect": dialect, "page": column, "group": g,
                                                      "skipped": obs["skipped"], "diffs": []}  # fmt: skip
            continue
        for key, group in (("runtime_run", RUN_GROUP), ("db_run", DB_GROUP)):
            if "skipped" in obs.get(key, {}):  # no JDK / no such database here: skipped and counted, never passed
                results[f"{dialect}|{column}|{group}"] = {"dialect": dialect, "page": column, "group": group,
                                                          "skipped": obs[key]["skipped"], "diffs": []}  # fmt: skip
        for g, diffs in check(dialect, column, obs).items():
            results[f"{dialect}|{column}|{g}"] = {"dialect": dialect, "page": column, "group": g, "diffs": diffs}
        if "db" in obs.get("db_run", {}):  # the database the cell really ran in, as it names itself
            results[f"{dialect}|{column}|{DB_GROUP}"]["database"] = obs["db_run"]["db"].get("collation")
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
    return _summary("India", {cid: r for cid, r in results.items() if india_cell(r["dialect"], r["page"])}, known)


def _summary(label: str, cells: dict[str, Any], known: dict[str, str]) -> str:
    ran = {cid: r for cid, r in cells.items() if "skipped" not in r}
    failing = {cid for cid, r in ran.items() if r["diffs"]}
    ledgered = len(failing & set(known))
    return (f"{label}: {len(ran) - len(failing)}/{len(ran)} cells pass, {ledgered} ledgered, "
            f"{len(failing) - ledgered} new, {len(cells) - len(ran)} skipped")  # fmt: skip


PART3 = {"D, target database collation": COLLATION_TARGETS, "E, input data": INPUT_FORMATS}


def part3_summaries(results: dict[str, Any], known: dict[str, str]) -> list[str]:
    """Part 3: a row per dimension, as the India row."""
    return [_summary(label, {cid: r for cid, r in results.items() if r["dialect"] in names}, known)
            for label, names in PART3.items()]  # fmt: skip


def report_md(results: dict[str, Any]) -> str:
    ran = [r for r in results.values() if "skipped" not in r]
    passed = sum(not r["diffs"] for r in ran)
    skipped = len(results) - len(ran)
    lines = ["# Cultural Gauntlet", "",
             f"{passed}/{len(ran)} cells pass, {len(ran) - passed} fail, {skipped} skipped (the page cannot hold "
             "the dialect's characters). A cell is one (dialect, code page, check group); each entry below is "
             "the groups that pass of those run.", "",
             "| dialect | " + " | ".join(COLUMNS) + " |", "|---|" + "---|" * len(COLUMNS)]  # fmt: skip
    for dialect in [*DIALECTS, *COLLATION_TARGETS, *INPUT_FORMATS]:
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
    lines += ["", "## Part 3: target database collation (D) and input data (E)", ""]
    lines += [f"- {line}" for line in part3_summaries(results, known)]
    lines += [f"- `{d}` ({COLLATION_TARGETS[d]['collation']}): {g} skipped -- {why}"
              for d, g, why in sorted({(r["dialect"], r["group"], r["skipped"]) for r in results.values()
                                       if "skipped" in r and r["dialect"] in COLLATION_TARGETS})]  # fmt: skip
    for cid, r in sorted(results.items()):
        if r["diffs"] and (r["dialect"] in COLLATION_TARGETS or r["dialect"] in INPUT_FORMATS):
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
    ap.add_argument("--db", action="store_true", help="part 3 (D): also run the generated table and key order "
                    "in the target databases this machine has (the collation-db group: H2 from ~/.m2, a "
                    "throwaway PostgreSQL cluster; a database not here is skipped, never faked)")  # fmt: skip
    args = ap.parse_args(argv)
    work = args.work or Path(tempfile.mkdtemp(prefix="cultural_gauntlet_"))
    results = run(work, args.full, args.jobs, set(args.only or ()), set(args.pages or ()), args.run, args.db)
    failing = {cid: r["diffs"][0] for cid, r in sorted(results.items()) if r["diffs"]}
    ran = sum("skipped" not in r for r in results.values())
    print(f"Cultural Gauntlet: {ran - len(failing)}/{ran} cells pass, {len(results) - ran} skipped")
    print(india_summary(results, read_baseline()))
    print("\n".join(part3_summaries(results, read_baseline())))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "report.md").write_text(report_md(results), encoding="utf-8")
        (args.out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.update_baseline:
        kept = [g for g, layer in ((RUN_GROUP, args.run), (DB_GROUP, args.db)) if not layer]
        # a run without an executed layer keeps that layer's ledgered cells
        failing = {**{c: d for c, d in read_baseline().items() if c.rsplit("|", 1)[-1] in kept}, **failing}
        write_baseline(failing)
        print(f"baseline: {len(failing)} failing cells recorded")
        return 0
    if args.ci:
        known = read_baseline()
        new = sorted(set(failing) - set(known))
        ran_cells = {cid for cid, r in results.items() if "skipped" not in r}
        fixed = sorted((set(known) - set(failing)) & ran_cells)  # a cell this run did not run is not fixed
        for cid in new:
            print(f"NEW FAILING CELL {cid}: {failing[cid]}")
        if fixed:
            print(f"{len(fixed)} baseline cells now pass -- lower the baseline (--update-baseline): {fixed[:10]}")
        return 1 if new else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
