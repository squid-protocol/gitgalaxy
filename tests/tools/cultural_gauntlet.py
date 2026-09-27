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

Later parts of #3834: the Java runtime locale and time zone (C), the target database collation (D), the
input-data cases (E), and executing the cells under GnuCOBOL and the JVM.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sqlite3
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

PAGES = ["cp037", "cp273", "cp277", "cp278", "cp285", "cp297"]
CONTROL = "utf8"  # the seed as UTF-8, data page cp037: the dialect checks without EBCDIC in the way
COLUMNS = [CONTROL, *PAGES]
GROUPS = ["facts", "schema", "records", "decoder", "ticket", "refractor"]

# IBM's zoned-decimal overpunch BYTES are fixed in every EBCDIC page: +0..+9 are 0xC0-0xC9, -0..-9 are
# 0xD0-0xD9 (unsigned 0xF0-0xF9). The characters they show as are the page's: the oracle decodes the
# bytes with the page's codec, never asks the converter.
POSITIVE_BYTES = bytes(range(0xC0, 0xCA))
NEGATIVE_BYTES = bytes(range(0xD0, 0xDA))
# The zero signs (0xC0 / 0xD0) by IBM CDRA, pinned here so the codecs themselves are checked too
# (tests/cultural_gauntlet/): the one pair that moves between the Western European pages.
CDRA_ZERO_SIGNS = {"cp037": "{}", "cp273": "äü", "cp277": "æå", "cp278": "äå", "cp285": "{}", "cp297": "éè"}

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
        {"special_names": [("CURRENCY", "£", "£")]}, special=_special("CURRENCY SIGN IS '£'"), edited="£££,££9.99"
    ),
    # #3857: the symbol U stands for the 4-character 'EUR ': its first position takes 4 bytes
    "currency_eur_u": _dialect(
        {"special_names": [("CURRENCY", "EUR ", "U")], "layout": _layout(13), "record_bytes": 43, "codec": _codec(13)},
        special=_special("CURRENCY SIGN IS 'EUR ' WITH PICTURE SYMBOL 'U'"),
        edited="UUU,UU9.99",
    ),
    # a '€' sign: none of the pre-euro pages holds it (their euro twins are cp1140-cp1149)
    "currency_euro": _dialect(
        {"special_names": [("CURRENCY", "€", "€")]}, special=_special("CURRENCY SIGN IS '€'"), edited="€€€,€€9.99"
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
}


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
    config.write_text(json.dumps({"data": {"code_page": data_page(column)}}), encoding="utf-8")
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
    return obs


def _run_cell(args: tuple[str, str, str]) -> dict[str, Any]:
    dialect, column, work = args
    os.environ.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")  # a pool process of its own
    os.environ["GITGALAXY_DISABLE_GIT_HISTORY"] = "1"
    try:
        return _observe(Path(work) / f"{dialect}__{column}", dialect, column)
    except Exception:  # a crash is the cell's finding, not the gauntlet's end
        return {"error": traceback.format_exc(limit=4).strip().splitlines()[-1]}


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
    return out


# ---- the plan and the run -------------------------------------------------------------------------
def plan(full: bool, only: set[str] | None = None, pages: set[str] | None = None) -> list[tuple[str, str]]:
    """(dialect, column) pairs. Sampled: '£' (the dialect a page moves: `$` and `£` trade bytes) in every
    page, every other dialect in the control and one page, rotating so the pages meet different dialects."""
    out = []
    for i, dialect in enumerate(DIALECTS):
        cols = COLUMNS if full or dialect == "currency_pound" else [CONTROL, PAGES[i % len(PAGES)]]
        out += [(dialect, c) for c in cols]
    return [(d, c) for d, c in out if (not only or d in only) and (not pages or c in pages)]


def run(work: Path, full: bool = False, jobs: int = 4, only: set[str] | None = None,
        pages: set[str] | None = None) -> dict[str, Any]:  # fmt: skip
    from concurrent.futures import ProcessPoolExecutor

    pairs = plan(full, only, pages)
    with ProcessPoolExecutor(max_workers=max(1, jobs)) as pool:
        observed = list(pool.map(_run_cell, [(d, c, str(work)) for d, c in pairs]))
    results: dict[str, Any] = {}
    for (dialect, column), obs in zip(pairs, observed):
        if "skipped" in obs:
            for g in GROUPS:
                results[f"{dialect}|{column}|{g}"] = {"dialect": dialect, "page": column, "group": g,
                                                      "skipped": obs["skipped"], "diffs": []}  # fmt: skip
            continue
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
    args = ap.parse_args(argv)
    work = args.work or Path(tempfile.mkdtemp(prefix="cultural_gauntlet_"))
    results = run(work, args.full, args.jobs, set(args.only or ()), set(args.pages or ()))
    failing = {cid: r["diffs"][0] for cid, r in sorted(results.items()) if r["diffs"]}
    ran = sum("skipped" not in r for r in results.values())
    print(f"Cultural Gauntlet: {ran - len(failing)}/{ran} cells pass, {len(results) - ran} skipped")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "report.md").write_text(report_md(results), encoding="utf-8")
        (args.out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.update_baseline:
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
