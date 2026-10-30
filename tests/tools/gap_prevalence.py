#!/usr/bin/env python3
"""#5865: gap prevalence -- which unmodelled or refused constructs show up in how many estates and programs, by era.

    python tests/tools/gap_prevalence.py --survey DIR [--label before] [--write] [--top 10 25]

Measurement only: it orders later work, it builds no feature. DIR is a `cics_census.py survey --out DIR --label before
--no-census` run (the burned corpora). Each program's gap classes are `cics_census.gap_classes` (the vocabulary the
readiness blocker report #5054 speaks); its era is the committed feature inventory's era tag (#5117,
tests/fixtures/feature_inventory/<corpus>.json). Per gap: estates, programs, programs per era, status (refused by
name / not modelled / unknown), the issue or epic that owns it; highest estate coverage first. "Coverage if closed":
for the top N gaps, the share of surveyed programs that would translate whole (a program stays out while any gap of
its own is left; a refusal that stops the whole program makes it an upper bound).

`--survey` is BURNED ESTATES ONLY (.claude/rules/mainframe-evidence-policy.md section 2): a survey row of a corpus that
is not burned is refused there. The census half is `--census-survey DIR --census-corpora DIR`: the non-burned estates
are counted by tools only, as AGGREGATES under opaque `census-<hash>` labels (like era_distribution.py): no program
name, no per-program row, no source line is kept; eras are computed in memory by `feature_inventory.scan_estate`; every
gap key is passed through `scrub_key`, which keeps only the engine's own vocabulary and collapses anything that could
carry a name from a census repo. Writes tests/fixtures/gap_prevalence/summary.json and census_summary.json (counts and
gap keys, no source) and docs/language_status/gap_prevalence.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import cics_census as cc  # noqa: E402

INVENTORY = REPO / "tests" / "fixtures" / "feature_inventory"
SUMMARY = REPO / "tests" / "fixtures" / "gap_prevalence" / "summary.json"
CENSUS_SUMMARY = SUMMARY.with_name("census_summary.json")
PAGE = REPO / "docs" / "language_status" / "gap_prevalence.md"
ERA_KEYS = ("0", "1", "2", "3", "4", "none")
TOP_N = (1, 3, 5, 10, 25)
FORMAT = "gap-prevalence/1"

# gap-key pattern -> the issue or epic that owns the work (first match wins; a pointer, not a status)
OWNERS: tuple[tuple[str, str], ...] = (
    (r"^missing copybook: CICS system", "#4270 (cics-command-slice)"),
    (r"^missing copybook: Db2 system", "#4098 (Db2 det-port)"),
    (r"^missing copybook: IMS system", "#4893"),
    (r"^refused: (macro-level CICS|CICS Assembler)", "#5121"),
    (r"^refused: LayoutDisagrees", "#6926"),
    (r"^EXEC DLI|CBLTDLI|\bDLI\b", "#4893"),
    (r"\bMQ[A-Z]*\b", "#4892"),
    (r"^EXEC SQL", "#4098 (Db2 det-port)"),
    (r"^EXEC CICS WEB\b", "#4767"),
    (r"^EXEC CICS", "#4270 (cics-command-slice)"),
    (r"^grammar:", "#4462"),
    (r"^CEE(?:HDL[RU]|MGET|SGL|NCOD|MRCE|3SRP):", "#5106 (le-condition-handling)"),
    (r"OS/VS COBOL BLL addressing", "#5119"),
    (r"the PICTURE N \(", "#4272"),
    (r"^SET TO ENTRY:", "#5106"),
    (r"is not defined in a record of file", "#5866"),
    (r"ADDRESS OF .*: not an item of ", "#5042"),
    (r"^missing copybook: estate-owned", "none (the estate's own copybook is not in the clone)"),
    (r"^missing copybook", "unowned (copybook family)"),
)


def owner_of(gap: str) -> str:
    return next((o for pat, o in OWNERS if re.search(pat, gap)), "unowned")


def reowner(res: dict[str, Any]) -> dict[str, Any]:
    """Re-apply `owner_of` to a committed summary: owners are pointers, so a re-render refreshes them with no survey."""
    for g in res.get("gaps", []):
        g["owner"] = owner_of(g["gap"])
    return res


def status_of(gap: str) -> str:
    if gap.startswith("refused"):
        return "refused by name"
    if gap.startswith("missing copybook"):
        return "unknown"
    return "not modelled"


def eras_of(corpus: str, inventory_dir: Path = INVENTORY) -> dict[str, str]:
    """program -> era key ('0'..'4' or 'none') from the committed inventory; empty when the corpus has none."""
    path = inventory_dir / f"{corpus}.json"
    if not path.is_file():
        return {}
    progs = json.loads(path.read_text(encoding="utf-8")).get("eras", {}).get("programs", {})
    return {p: "none" if v.get("era") is None else str(v["era"]) for p, v in progs.items()}


def measure(rows: dict[tuple[str, str], dict[str, Any]], inventory_dir: Path = INVENTORY,
            top: tuple[int, ...] = TOP_N) -> dict[str, Any]:  # fmt: skip
    """Rank the gap classes of the surveyed burned programs. A non-burned corpus in `rows` is refused."""
    burned = cc.burned_names()
    bad = sorted({c for c, _ in rows if not cc.is_burned(c, burned)})
    if bad:
        raise ValueError(f"not burned estates (use measure_census for census estates): {', '.join(bad)}")
    era_by: dict[str, dict[str, str]] = {}
    progs: list[tuple[str, str, set[str]]] = []  # (corpus, era, gap classes)
    for (corpus, prog), r in sorted(rows.items()):
        era = era_by.setdefault(corpus, eras_of(corpus, inventory_dir)).get(prog, "none")
        progs.append((corpus, era, cc.gap_classes(r)))
    return rank(progs, "burned estates", top)


def rank(progs: list[tuple[str, str, set[str]]], scope: str, top: tuple[int, ...] = TOP_N) -> dict[str, Any]:
    """(estate, era, gap classes) per program -> the ranked gaps and the coverage-if-closed table."""
    estates: dict[str, set[str]] = defaultdict(set)
    count: dict[str, int] = defaultdict(int)
    by_era: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(ERA_KEYS, 0))
    era_estates: dict[str, dict[str, set[str]]] = defaultdict(lambda: {e: set() for e in ERA_KEYS})
    for corpus, era, classes in progs:
        for g in classes:
            estates[g].add(corpus)
            count[g] += 1
            by_era[g][era] += 1
            era_estates[g][era].add(corpus)
    gaps = [
        {"gap": g, "estates": len(estates[g]), "programs": count[g],
         "by_era": by_era[g], "estates_by_era": {e: len(s) for e, s in era_estates[g].items()},
         "status": status_of(g), "owner": owner_of(g), "refuses_program": g.startswith(cc.REFUSES)}
        for g in estates
    ]  # fmt: skip
    gaps.sort(key=lambda d: (-d["estates"], -d["programs"], d["gap"]))
    total = len(progs)
    whole_now = sum(not c for _, _, c in progs)
    closed = []
    for n in top:
        if n > len(gaps):
            break
        picked = {g["gap"] for g in gaps[:n]}
        whole = sum(c <= picked for _, _, c in progs)
        closed.append({"top": n, "whole": whole, "share": round(whole / total, 4) if total else 0.0,
                       "upper_bound": any(g["refuses_program"] for g in gaps[:n])})  # fmt: skip
    res = {
        "format": FORMAT,
        "scope": scope,
        "estates": sorted({c for c, _, _ in progs}),
        "programs": total,
        "whole_now": whole_now,
        "by_era_programs": {e: sum(era == e for _, era, _ in progs) for e in ERA_KEYS},
        "gaps": gaps,
        "coverage_if_closed": closed,
    }
    order = close_next(progs, gaps)
    if order:
        res["close_next"] = order
    return res


CLOSE_NEXT_STEPS = 10


def close_next(progs: list[tuple[str, str, set[str]]], gaps: list[dict[str, Any]],
               steps: int = CLOSE_NEXT_STEPS) -> list[dict[str, Any]]:  # fmt: skip
    """Greedy work order: each step closes the gap that makes the most further programs whole (ties: more estates,
    more programs, then name), given the gaps closed before it. A step gaining nothing alone ends the list (the rest
    only help in combination). `upper_bound`: a closed gap refuses the whole program, so `whole` is an upper bound."""
    rank_of = {g["gap"]: (-g["estates"], -g["programs"], g["gap"]) for g in gaps}
    refuses = {g["gap"] for g in gaps if g["refuses_program"]}
    left = [(era, set(c)) for _, era, c in progs]
    total = len(progs)
    closed: set[str] = set()
    whole = sum(not c for _, c in left)
    out: list[dict[str, Any]] = []
    while len(out) < steps:
        gain: dict[str, int] = defaultdict(int)
        for _, c in left:
            if len(c) == 1:
                gain[next(iter(c))] += 1  # the only gap this program has left
        if not gain:
            break
        pick = min(gain, key=lambda g: (-gain[g], rank_of[g]))
        closed.add(pick)
        by_era = dict.fromkeys(ERA_KEYS, 0)
        for era, c in left:
            if c == {pick}:
                by_era[era] += 1
        left = [(era, c - {pick}) for era, c in left]
        whole += gain[pick]
        out.append({"gap": pick, "gained": gain[pick], "gained_by_era": by_era, "whole": whole,
                    "share": round(whole / total, 4) if total else 0.0,
                    "upper_bound": bool(closed & refuses)})  # fmt: skip
    return out


# ---- the census half: aggregates only, nothing that names a census repo or program ---------------------------------
_SQL_WORDS = frozenset(
    "ALTER CLOSE COMMIT CONNECT CREATE CURSOR DECLARE DELETE DESCRIBE EXECUTE FETCH FOR FREE HOLD INCLUDE INSERT LOCK "
    "OPEN PREPARE RELEASE ROLLBACK SAVEPOINT SELECT SET TABLE UPDATE WHENEVER WITH WITHOUT RETURN CALL".split()
)
_STATEMENT_WORDS = frozenset(
    "ADDRESS ANNUITY BY CALL COMPUTE ENTRY EXEC FUNCTION IN INTO OF ON POINTER SET SIZE TO USING WITH ERROR".split()
)
_VERB = re.compile(r"[A-Z][A-Z-]*")
# #5865 slice 2: the engine's own refusal / hole texts as fixed, name-free construct keys. A closed vocabulary: the key is
# the table's string, never a slice of the source, so it cannot carry a census name. First match wins.
_CONSTRUCTS: tuple[tuple[str, str], ...] = (
    (r"^WRITE AFTER without ADVANCING", "WRITE: AFTER without ADVANCING"),
    (r"^WRITE AFTER ADVANCING .*carriage control", "WRITE: carriage control (mnemonic-name) not modelled"),
    (r"variable-length records without RECORD VARYING", "FD: variable-length records without RECORD VARYING"),
    (r"no program of that name with a CALL entry", "CALL: target without a CALL entry in the estate"),
    (r"^CALL <name>$", "CALL: other non-IBM target"),
    (r"^JSON (PARSE|GENERATE)\b", r"JSON \1: not modelled"),
    (r"^(MOVE|STRING) .*beyond the single-byte code page", r"\1: literal beyond the single-byte code page"),
    (r"^STRING sender .*numeric item with a P or a decimal place", "STRING: numeric sender with P or a decimal place"),
    (r"its bytes hold ", "<name>: bytes overlap another item"),
    (r"^ACCEPT from SYSIN", "ACCEPT: from SYSIN / console"),
    (r"^PERFORM .*undeclared paragraph", "PERFORM: undeclared paragraph"),
    (r"^[A-Z0-9]+: undeclared item", "<name>: undeclared item"),
    (r"^[A-Z0-9]+: no FD record", "FD: no record description"),
    (r"^EXEC CICS map <name>: no ", "EXEC CICS map: no <name> field"),
    (r"^STOP literal", "STOP: literal"),
    (r"^EXHIBIT NAMED", "EXHIBIT NAMED: only plain names and literals"),
    (r"^MOVE CORRESPONDING", "MOVE CORRESPONDING"),
)
# #5865 slice 5: the translator's own refusal texts (det/layout.py, expr.py, engine_layout.py, source.py) as name-free keys,
# matched on the message after `refused: <Class>: `. Same closed-vocabulary rule; no match keeps the bare class.
_REFUSALS: tuple[tuple[str, str], ...] = (
    (r"^LayoutError: .*VALUE .*not modelled", "refused: LayoutError: VALUE not modelled"),
    (r"^LayoutError: .*VALUE .*not a number", "refused: LayoutError: VALUE not a number"),
    (r"^LayoutError: .*REDEFINES .*no 01 of that name", "refused: LayoutError: REDEFINES target not found"),
    (r"^LayoutError: .*REDEFINES .*not a sibling", "refused: LayoutError: REDEFINES target not a sibling"),
    (r"^LayoutError: .*has no 01 above it", "refused: LayoutError: level without an 01 above it"),
    (r"^LayoutError: DATA DIVISION does not parse", "refused: LayoutError: DATA DIVISION does not parse"),
    (r"^LayoutDisagrees: .*layout differs", "refused: LayoutDisagrees: layout differs from the engine's"),
    (r"^LayoutDisagrees: .*do not pair", "refused: LayoutDisagrees: fields do not pair with the record's"),
    (r"^LayoutDisagrees: .*record's width", "refused: LayoutDisagrees: record width unknown to the engine"),
    (r"^UnitRefused: .*text after END PROGRAM", "refused: UnitRefused: text after END PROGRAM"),
    (r"^UnitRefused: .*END PROGRAM .*closes no open", "refused: UnitRefused: END PROGRAM closes no open program"),
    (r"^UnitRefused: .*no PROGRAM-ID", "refused: UnitRefused: no PROGRAM-ID (a member to be copied)"),
    (r"^UnitRefused: .*is nested in", "refused: UnitRefused: nested program"),
    (r"^UnitRefused: no program .* in the source", "refused: UnitRefused: requested program not in the source"),
    (r"^ExprError: .*reference modification", "refused: ExprError: reference modification form"),
    (r"^ExprError: .*NULL", "refused: ExprError: NULL compared with a non-pointer"),
    (r"^ExprError: .*ADDRESS OF", "refused: ExprError: ADDRESS OF"),
    (r"^ExprError: .*DFHRESP", "refused: ExprError: DFHRESP condition not documented"),
    (r"^ExprError: .*DFHVALUE", "refused: ExprError: DFHVALUE CVDA not documented"),
    (r"^ExprError: .*unbalanced parenthesis", "refused: ExprError: unbalanced parenthesis"),
    (
        r"^ExprError: .*(?:left over in|unexpected end of|missing operand)",
        "refused: ExprError: expression does not parse",
    ),
    (r"^ExprError: .*(?:not a condition|not a relation)", "refused: ExprError: not a condition / relation"),
    (r"^ExprError: .*not a data name", "refused: ExprError: not a data name"),
    (r"^ExprError: ALL\b", "refused: ExprError: ALL form"),
)


# #5865 slice 4: the copybook family. IBM-supplied member prefixes -> the system whose copybook it is; a closed vocabulary,
# so the key is the table's string and never the member name. Anything else is the estate's own.
_COPYBOOK_FAMILIES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("DFH",), "CICS system"),
    (("SQLCA", "SQLDA", "DSN"), "Db2 system"),
    (("CMQ",), "MQ system"),
    (("DLI", "AIB"), "IMS system"),
    (("CEE", "IGZ"), "LE system"),
)


def copybook_family(member: str) -> str:
    """`missing copybook PAYREC (ambiguous)` -> `missing copybook: estate-owned`; no member name survives."""
    name = member.removeprefix("missing copybook").replace("(ambiguous)", "").strip().upper()
    fam = next((f for prefixes, f in _COPYBOOK_FAMILIES if name.startswith(prefixes)), "estate-owned")
    return f"missing copybook: {fam}"


_ROUTINE = re.compile(r"(?:CEE|CBLTDLI|CEETDLI|AIBTDLI|MQ|DFH|ILBO|IGZ|CKM|DSN)[A-Z0-9]*")


def scrub_key(gap: str) -> str:
    """A gap key that cannot name a census repo, program, table or copybook: the engine's own vocabulary (CICS command
    and option, SQL keywords, IBM routines, refusal families, statement forms whose words are all COBOL words) is kept,
    anything else collapses to its class. Applied to census rows only; the burned page keeps the full keys."""
    if re.fullmatch(r"EXEC CICS [A-Z]+(?: [A-Z]+){0,3}", gap):
        return gap
    if m := re.fullmatch(r"EXEC SQL: ([A-Z]+(?: [A-Z]+)*)", gap):
        return gap if set(m.group(1).split()) <= _SQL_WORDS else "EXEC SQL: other"
    if gap.startswith("EXEC SQL"):
        return "EXEC SQL: other"
    if gap.startswith("EXEC DLI"):
        return "EXEC DLI"
    if gap.startswith("missing copybook"):
        return copybook_family(gap)
    if gap.startswith("grammar:"):
        return "grammar: does not parse" if "does not parse" in gap else "grammar: other"
    if m := re.match(r"refused: (macro-level CICS|CICS Assembler)$", gap):
        return gap
    if gap.startswith("refused: "):
        for pat, key in _REFUSALS:
            if re.search(pat, gap[len("refused: ") :]):
                return key
    if m := re.match(r"refused: ([A-Za-z]+)", gap):
        return f"refused: {m.group(1)}"
    if m := re.fullmatch(r"<name>: (no such item|undeclared item)", gap):
        return gap
    if m := re.match(r"CALL ([A-Z0-9]+)", gap):
        return f"CALL {m.group(1)}" if _ROUTINE.fullmatch(m.group(1)) else "CALL other"
    for pat, key in _CONSTRUCTS:
        if m2 := re.search(pat, gap):
            return m2.expand(key)
    verb = _VERB.match(gap)
    if verb and verb.group(0) in _STATEMENT_WORDS:
        words = set(re.findall(r"\b[A-Z][A-Z-]+\b", gap))
        if words <= _STATEMENT_WORDS and "<name>" not in gap:
            return gap
        return f"{verb.group(0)}: other"
    return "other"


def census_label(name: str) -> str:
    return "census-" + hashlib.sha256(name.encode()).hexdigest()[:6]


def measure_census(rows: dict[tuple[str, str], dict[str, Any]], eras: dict[str, dict[str, str]],
                   top: tuple[int, ...] = TOP_N) -> dict[str, Any]:  # fmt: skip
    """Rank the scrubbed gap classes of non-burned programs. `eras`: corpus -> program -> era key, held in memory only.
    The result carries opaque labels and counts: no corpus or program name. A burned corpus in `rows` is refused."""
    burned = cc.burned_names()
    bad = sorted({c for c, _ in rows if cc.is_burned(c, burned)})
    if bad:
        raise ValueError(f"burned estates belong to measure(): {', '.join(bad)}")
    progs = [
        (census_label(corpus), eras.get(corpus, {}).get(prog, "none"), {scrub_key(g) for g in cc.gap_classes(r)})
        for (corpus, prog), r in sorted(rows.items())
    ]
    return rank(progs, "census estates (aggregate, opaque labels)", top)


def census_eras(corpora: Path, names: set[str]) -> dict[str, dict[str, str]]:
    """corpus -> program -> era key, by `feature_inventory.scan_estate` (the burned estates' own tagger), in memory."""
    from tests.tools.feature_inventory import scan_estate

    out: dict[str, dict[str, str]] = {}
    for corpus, path in cc.corpus_dirs([corpora]):
        if corpus in names:
            progs = scan_estate(path, Path(tempfile.mkdtemp(prefix="gap-prevalence-")))["eras"]["programs"]
            out[corpus] = {p: "none" if v.get("era") is None else str(v["era"]) for p, v in progs.items()}
    return out


def table(res: dict[str, Any]) -> list[str]:
    out = [
        "| gap | estates | programs | e0 | e1 | e2 | e3 | e4 | none | status | owner |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in res["gaps"]:
        eras = " | ".join(str(g["by_era"][e]) for e in ERA_KEYS)
        out.append(
            f"| `{g['gap'].replace('|', '/')}` | {g['estates']} | {g['programs']} | {eras} | {g['status']} "
            f"| {g['owner']} |"
        )
    out += [
        "",
        "| top N gaps closed | programs whole | share | bound |",
        "|---|---|---|---|",
    ]
    for c in res["coverage_if_closed"]:
        out.append(f"| {c['top']} | {c['whole']} / {res['programs']} | {c['share']:.1%} | "
                   f"{'upper' if c['upper_bound'] else 'exact'} |")  # fmt: skip
    if res.get("close_next"):
        out += [
            "",
            "Close-next order (greedy: each step closes the gap that makes the most further programs whole, "
            "given the steps before it):",
            "",
            "| step | gap closed | newly whole | e0 | e1 | e2 | e3 | e4 | none | whole | share | bound |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for i, c in enumerate(res["close_next"], 1):
            eras = " | ".join(str(c["gained_by_era"][e]) for e in ERA_KEYS)
            out.append(f"| {i} | `{c['gap'].replace('|', '/')}` | {c['gained']} | {eras} | {c['whole']} / "
                       f"{res['programs']} | {c['share']:.1%} | {'upper' if c['upper_bound'] else 'exact'} |")  # fmt: skip
    return out


def combine(burned: dict[str, Any], census: dict[str, Any]) -> list[dict[str, Any]]:
    """One ranking over both scopes: estate labels never overlap, so estates, programs and eras add per gap key."""
    merged: dict[str, dict[str, Any]] = {}
    for scope, res in (("B", burned), ("C", census)):
        for g in res["gaps"]:
            m = merged.setdefault(
                g["gap"],
                {"gap": g["gap"], "scope": "", "estates": 0, "programs": 0, "by_era": dict.fromkeys(ERA_KEYS, 0)},
            )
            m["scope"] += ("+" if m["scope"] else "") + scope
            m["estates"] += g["estates"]
            m["programs"] += g["programs"]
            for e in ERA_KEYS:
                m["by_era"][e] += g["by_era"][e]
    for m in merged.values():
        m["status"], m["owner"] = status_of(m["gap"]), owner_of(m["gap"])
    return sorted(merged.values(), key=lambda d: (-d["estates"], -d["programs"], d["gap"]))


def combined_table(gaps: list[dict[str, Any]]) -> list[str]:
    out = [
        "| gap | scope | estates | programs | e0 | e1 | e2 | e3 | e4 | none | status | owner |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in gaps:
        eras = " | ".join(str(g["by_era"][e]) for e in ERA_KEYS)
        out.append(
            f"| `{g['gap'].replace('|', '/')}` | {g['scope']} | {g['estates']} | {g['programs']} | {eras} "
            f"| {g['status']} | {g['owner']} |"
        )
    return out


def render(res: dict[str, Any], census: dict[str, Any] | None = None) -> str:
    out = [
        "---",
        'description: "Gap prevalence (#5865): which unmodelled or refused constructs the burned and census estates '
        'use, in how many estates and programs, by era."',
        "---",
        "",
        "# Gap prevalence",
        "",
        "Generated by `tests/tools/gap_prevalence.py` (#5865); do not edit. Measurement only: it orders later work. "
        "Gap keys are `cics_census.gap_key` classes, the vocabulary of the readiness blocker report (#5054). Era is "
        "the inventory's era tag (#5117); `none` = no tell. A status of *refused by name* stops the whole program, so "
        "its coverage is an upper bound; the owner is a pointer to the issue or epic, not a status.",
        "",
        *(
            [
                f"## All estates ({len(res['estates']) + len(census['estates'])} estates: burned B, census C)",
                "",
                "One ranking over both scopes, highest estate coverage first; estates and programs add across scopes. "
                "Coverage if closed is per scope below.",
                "",
                *combined_table(combine(res, census)),
                "",
            ]
            if census
            else []
        ),
        f"## Burned estates ({len(res['estates'])} estates, {res['programs']} programs, {res['whole_now']} "
        "translate whole today)",
        "",
        *table(res),
    ]
    if census:
        out += [
            "",
            f"## Census estates ({len(census['estates'])} estates, {census['programs']} programs, "
            f"{census['whole_now']} translate whole today)",
            "",
            "Counted by tools only; non-burned estates keep their first-contact numbers. Aggregates under opaque "
            "`census-*` labels: no program, table or copybook name is kept, and a gap key that could carry one is "
            "collapsed to its class (`scrub_key`).",
            "",
            *table(census),
        ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--survey", type=Path, help="cics_census survey DIR (burned corpora)")
    ap.add_argument("--census-survey", type=Path, help="cics_census survey DIR of the non-burned census corpora")
    ap.add_argument("--census-corpora", type=Path, help="the census clones (for the era tags; read in memory only)")
    ap.add_argument("--label", default="before")
    ap.add_argument("--top", type=int, nargs="*", default=list(TOP_N))
    ap.add_argument("--write", action="store_true", help="write the summary JSON and the docs page")
    args = ap.parse_args(argv)
    census = None
    if args.census_survey:
        crows = {k: r for k, r in cc.load_surveys(args.census_survey, args.label).items() if not cc.is_burned(k[0])}
        if not crows or not args.census_corpora:
            raise SystemExit("--census-survey needs non-burned rows and --census-corpora")
        census = measure_census(crows, census_eras(args.census_corpora, {c for c, _ in crows}), tuple(args.top))
    if args.survey:
        rows = cc.load_surveys(args.survey, args.label)
        if not rows:
            raise SystemExit(f"no {args.label}-*/survey.json under {args.survey}")
        res = measure({k: r for k, r in rows.items() if cc.is_burned(k[0])}, top=tuple(args.top))
    elif SUMMARY.is_file():
        res = reowner(json.loads(SUMMARY.read_text(encoding="utf-8")))
    else:
        raise SystemExit("--survey DIR is needed (no committed burned summary yet)")
    if census is None and CENSUS_SUMMARY.is_file():
        census = reowner(json.loads(CENSUS_SUMMARY.read_text(encoding="utf-8")))
        if args.write:
            CENSUS_SUMMARY.write_text(json.dumps(census, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.write:
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        if args.survey or SUMMARY.is_file():
            SUMMARY.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        if args.census_survey and census:
            CENSUS_SUMMARY.write_text(json.dumps(census, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        PAGE.write_text(render(res, census), encoding="utf-8")
    else:
        print(render(res, census))
    return 0


if __name__ == "__main__":
    sys.exit(main())
