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

BURNED ESTATES ONLY (.claude/rules/mainframe-evidence-policy.md section 2): a survey row of a corpus that is not burned
is refused here. The census half (non-burned estates, aggregate counts under opaque labels like era_distribution.py)
is a separate slice. Writes tests/fixtures/gap_prevalence/summary.json (counts and gap keys, no source) and
docs/language_status/gap_prevalence.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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
PAGE = REPO / "docs" / "language_status" / "gap_prevalence.md"
ERA_KEYS = ("0", "1", "2", "3", "4", "none")
TOP_N = (1, 3, 5, 10, 25)
FORMAT = "gap-prevalence/1"

# gap-key pattern -> the issue or epic that owns the work (first match wins; a pointer, not a status)
OWNERS: tuple[tuple[str, str], ...] = (
    (r"^refused: (macro-level CICS|CICS Assembler)", "#5121"),
    (r"^EXEC DLI|CBLTDLI|\bDLI\b", "#4893"),
    (r"\bMQ[A-Z]*\b", "#4892"),
    (r"^EXEC SQL", "#4098 (Db2 det-port)"),
    (r"^EXEC CICS", "#4270 (cics-command-slice)"),
    (r"^grammar:", "#4462"),
    (r"^CEE(?:HDL[RU]|MGET|SGL|NCOD|MRCE|3SRP):", "#5106 (le-condition-handling)"),
    (r"^missing copybook", "unowned (copybook family)"),
)


def owner_of(gap: str) -> str:
    return next((o for pat, o in OWNERS if re.search(pat, gap)), "unowned")


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
        raise ValueError(f"not burned estates (census work is a separate slice): {', '.join(bad)}")
    era_by: dict[str, dict[str, str]] = {}
    progs: list[tuple[str, str, set[str]]] = []  # (corpus, era, gap classes)
    for (corpus, prog), r in sorted(rows.items()):
        era = era_by.setdefault(corpus, eras_of(corpus, inventory_dir)).get(prog, "none")
        progs.append((corpus, era, cc.gap_classes(r)))
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
    return {
        "format": FORMAT,
        "scope": "burned estates",
        "estates": sorted({c for c, _, _ in progs}),
        "programs": total,
        "whole_now": whole_now,
        "by_era_programs": {e: sum(era == e for _, era, _ in progs) for e in ERA_KEYS},
        "gaps": gaps,
        "coverage_if_closed": closed,
    }


def render(res: dict[str, Any]) -> str:
    out = [
        "---",
        'description: "Gap prevalence (#5865): which unmodelled or refused constructs the burned estates use, '
        'in how many estates and programs, by era."',
        "---",
        "",
        "# Gap prevalence (burned estates)",
        "",
        "Generated by `tests/tools/gap_prevalence.py` (#5865); do not edit. Measurement only: it orders later work. "
        f"Scope: {res['scope']} ({len(res['estates'])} estates, {res['programs']} programs, {res['whole_now']} "
        "translate whole today). Gap keys are `cics_census.gap_key` classes, the vocabulary of the readiness blocker "
        "report (#5054). Era is the inventory's era tag (#5117); `none` = no tell. Non-burned census counts are a "
        "separate slice. A status of *refused by name* stops the whole program, so its coverage is an upper bound; "
        "the owner is a pointer to the issue or epic, not a status.",
        "",
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
        "## Coverage if closed",
        "",
        "| top N gaps closed | programs whole | share | bound |",
        "|---|---|---|---|",
    ]
    for c in res["coverage_if_closed"]:
        out.append(f"| {c['top']} | {c['whole']} / {res['programs']} | {c['share']:.1%} | "
                   f"{'upper' if c['upper_bound'] else 'exact'} |")  # fmt: skip
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--survey", type=Path, required=True, help="cics_census survey DIR (burned corpora)")
    ap.add_argument("--label", default="before")
    ap.add_argument("--top", type=int, nargs="*", default=list(TOP_N))
    ap.add_argument("--write", action="store_true", help="write the summary JSON and the docs page")
    args = ap.parse_args(argv)
    rows = cc.load_surveys(args.survey, args.label)
    if not rows:
        raise SystemExit(f"no {args.label}-*/survey.json under {args.survey}")
    rows = {k: r for k, r in rows.items() if cc.is_burned(k[0])}
    res = measure(rows, top=tuple(args.top))
    if args.write:
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        PAGE.write_text(render(res), encoding="utf-8")
    else:
        print(render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
