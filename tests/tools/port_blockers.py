"""
Port-side blocker ledger (#5051): the det port, transaction forge, facade, harness and runtime blockers that kept
a program from being translated whole or proven, tagged by the burned estate that exposed them.

It sits beside field_testing.json, which logs engine / forge FACT defects. Sources:
  tests/cobol_mainframe/port_blockers.json   the blockers (log one in the PR that finds or fixes it)
  tests/cobol_mainframe/field_testing.json   the estates and their rounds

Only burned estates (estate4_draw.BURNED_NAMES) are tagged; a census or blind-estate repo never appears.
The report counts blockers: it is a discovery curve, not a proof, and its estimate for the next estate says so.

    python tests/tools/port_blockers.py report [--write]   # print (or write) the report
    python tests/tools/port_blockers.py check              # validate the ledger; report up to date
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
LEDGER = REPO_ROOT / "tests" / "cobol_mainframe" / "port_blockers.json"
ESTATES = REPO_ROOT / "tests" / "cobol_mainframe" / "field_testing.json"
REPORT = REPO_ROOT / "docs" / "language_status" / "port_blockers.md"
ANSWER_KEYS = REPO_ROOT / "tests" / "cobol_mainframe" / "answer_key"


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads(LEDGER.read_text(encoding="utf-8")),
        json.loads(ESTATES.read_text(encoding="utf-8")),
    )


def estate_sizes(estates: list[str]) -> dict[str, int]:
    """Programs per estate, from its answer key (an estate with no key is left out)."""
    sizes: dict[str, int] = {}
    for eid in estates:
        key = ANSWER_KEYS / f"{eid}.json"
        if key.is_file():
            sizes[eid] = len(json.loads(key.read_text(encoding="utf-8"))["programs"])
    return sizes


def burned_names() -> set[str]:
    import estate4_draw  # lazy: it pulls the engine's source reader

    return {n.lower() for n in estate4_draw.BURNED_NAMES}


def validate(ledger: dict[str, Any], registry: dict[str, Any], burned: set[str]) -> list[str]:
    errors: list[str] = []
    rounds = {e["id"]: e["round"] for e in registry["estates"]}
    top = max(rounds.values(), default=0)
    seen: set[str] = set()
    first_of_class: dict[str, str] = {}
    # new_class is "first of its class" in discovery order (round, then id), not file order
    for b in sorted(
        ledger["blockers"],
        key=lambda x: (x.get("after_round") if isinstance(x.get("after_round"), int) else 0, str(x.get("id", ""))),
    ):
        where = b.get("id", "?")
        if where in seen:
            errors.append(f"{where}: duplicate blocker id")
        seen.add(where)
        estate = b.get("estate")
        if estate is None:
            if b.get("found_by") not in ledger["found_by"]:
                errors.append(f"{where}: a blocker with no estate needs found_by in {ledger['found_by']}")
            if not isinstance(b.get("after_round"), int) or not 0 <= b["after_round"] <= top:
                errors.append(f"{where}: needs after_round, the last round checked before it (0..{top})")
        else:
            if estate not in rounds:
                errors.append(f"{where}: unknown estate {estate}")
            elif estate not in burned:
                errors.append(f"{where}: {estate} is not a burned estate (estate4_draw.BURNED_NAMES)")
            elif b.get("after_round") != rounds[estate]:
                errors.append(f"{where}: after_round must be the estate's round {rounds[estate]}")
            if "found_by" in b:
                errors.append(f"{where}: found_by is only for a blocker with no estate")
        if b.get("side") not in ledger["sides"]:
            errors.append(f"{where}: side must be one of {ledger['sides']}")
        if b.get("class") not in ledger["classes"]:
            errors.append(f"{where}: class must be one of {ledger['classes']}")
        if not isinstance(b.get("programs"), list):
            errors.append(f"{where}: programs is a list (empty when the issue names none)")
        if not b.get("issue") and not b.get("fixed_by"):
            errors.append(f"{where}: cite an issue or a fixing PR")
        if b.get("fixed_by") is not None and not re.fullmatch(r"#\d+", str(b["fixed_by"])):
            errors.append(f"{where}: fixed_by is a PR reference like #1234")
        if not isinstance(b.get("refused_by_name"), bool):
            errors.append(f"{where}: refused_by_name is true or false")
        if not b.get("summary"):
            errors.append(f"{where}: summary is required")
        cls = b.get("class")
        is_new = cls not in first_of_class
        first_of_class.setdefault(cls, where)
        if b.get("new_class") is not is_new:
            errors.append(f"{where}: new_class must be {str(is_new).lower()} (first of {cls}: {first_of_class[cls]})")
    return errors


def _key(b: dict[str, Any]) -> tuple[int, str]:
    return (b["after_round"], b["id"])


def _curve(bl: list[dict[str, Any]], estates: list[dict[str, Any]], sizes: dict[str, int]) -> list[str]:
    """The discovery curve by round (one row per burned estate, in port order) and the next-estate estimate."""
    out = [
        "",
        "## Discovery curve by round",
        "",
        "A round is one burned estate. `programs` is the estate's program count from its answer key; the rate is",
        "logged blockers per program. A blocker with no estate is counted on its own row, not in any rate.",
        "",
        "| round | estate | programs | blockers | per program | cumulative blockers | new classes | classes seen | "
        "rounds since a new class |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    cumulative = seen = since = 0
    rates: list[tuple[int, int]] = []
    for e in estates:
        mine = [b for b in bl if b["estate"] == e["id"]]
        new = sum(1 for b in mine if b["new_class"])
        cumulative += len(mine)
        seen += new
        since = 0 if new else since + 1
        n = sizes.get(e["id"])
        if n:
            rates.append((len(mine), n))
        per = f"{len(mine) / n:.2f}" if n else "n/a"
        out.append(
            f"| {e['round']} | {e['id']} | {n if n else 'n/a'} | {len(mine)} | {per} | {cumulative} | {new} | "
            f"{seen} | {since} |"
        )
    for b in (x for x in bl if x["estate"] is None):
        cumulative += 1
        seen += 1 if b["new_class"] else 0
        out.append(
            f"| {b['after_round']} | none ({b['found_by']}, {b['id']}) | | 1 | | {cumulative} | "
            f"{1 if b['new_class'] else 0} | {seen} | |"
        )
    out += ["", "## Expected for the next estate", ""]
    if len(rates) < 2:
        return out + ["Fewer than two estates have a program count: no estimate."]
    last = rates[-3:]
    pooled = sum(k for k, _ in last) / sum(n for _, n in last)
    lo = min(k / n for k, n in last)
    hi = max(k / n for k, n in last)
    all_rate = sum(k for k, _ in rates) / sum(n for _, n in rates)
    out += [
        f"Logged blockers per program over the last {len(last)} estates: {pooled:.2f} pooled "
        f"(range {lo:.2f} to {hi:.2f}); over all {len(rates)} estates {all_rate:.2f}. For a next estate of N "
        f"programs that is about {pooled:.1f}*N logged blockers (between {lo:.1f}*N and {hi:.1f}*N): "
        f"{pooled * 10:.1f} per 10 programs, {pooled * 40:.0f} for 40.",
        "",
        f"New classes: {seen} of the {len(bl)} logged blockers opened a class, and the last {since} estate(s) "
        "opened none, so a next estate is expected to bring repeats of known classes, not a new one. The class "
        "vocabulary is coarse (zECS used unseen API areas and still logged only repeats), so read that as a "
        "floor on novelty, not a guarantee.",
        "",
        "Read this as an order of magnitude. The ledger is a partial backfill (the issue's keyword count is "
        "~1.3 blockers per program on the first port falling to ~0.25 on the fifth, zECS excepted for new API "
        "areas, which is higher than the logged rate here), so the logged rate is a lower bound. There are "
        f"{len(rates)} data points and no variance model: the range is the spread of the last {len(last)}, not a "
        "confidence interval.",
    ]
    return out


def render(
    ledger: dict[str, Any], registry: dict[str, Any], burned: set[str], sizes: dict[str, int] | None = None
) -> str:
    estates = [e for e in registry["estates"] if e["id"] in burned]
    if sizes is None:
        sizes = estate_sizes([e["id"] for e in estates])
    rounds = {e["id"]: e["round"] for e in estates}
    bl = sorted(ledger["blockers"], key=_key)
    out = [
        "# Port-side blockers by estate",
        "",
        "Generated by `python tests/tools/port_blockers.py report --write` from",
        "`tests/cobol_mainframe/port_blockers.json` and the estate rounds of `field_testing.json`. Do not edit by",
        "hand. `check` fails when this page is stale. A blocker is anything other than an engine / forge fact defect",
        "that kept a program from translating whole or proving (the det port, transaction forge, facade, harness,",
        "runtime). Only burned estates are tagged. A blocker found by review or across estates names no estate:",
        "`after_round` places it. Counts are of logged blockers: the ledger is being backfilled, so a low count is",
        "an unfinished log, not a clean estate.",
        "",
        "## By estate",
        "",
        "| round | estate | blockers | cumulative | new classes | repeats | programs named | blockers per program named | refused by name |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    cumulative = 0
    for e in estates:
        mine = [b for b in bl if b["estate"] == e["id"]]
        progs = {p for b in mine for p in b["programs"]}
        new = sum(1 for b in mine if b["new_class"])
        cumulative += len(mine)
        per = f"{len(mine) / len(progs):.2f}" if progs else "n/a"
        refused = sum(1 for b in mine if b["refused_by_name"])
        out.append(
            f"| {e['round']} | {e['id']} | {len(mine)} | {cumulative} | {new} | {len(mine) - new} | "
            f"{len(progs)} | {per} | {refused} |"
        )
    loose = [b for b in bl if b["estate"] is None]
    out += [
        "",
        f"No single estate: {len(loose)} ("
        + (", ".join(f"{b['id']} by {b['found_by']} after round {b['after_round']}" for b in loose) or "none")
        + ").",
        "",
        "## By side and class",
        "",
        "| side | blockers | | class | blockers | first seen |",
        "|---|---|---|---|---|---|",
    ]
    sides = ledger["sides"]
    classes = ledger["classes"]
    for i in range(max(len(sides), len(classes))):
        s = sides[i] if i < len(sides) else ""
        c = classes[i] if i < len(classes) else ""
        sn = str(sum(1 for b in bl if b["side"] == s)) if s else ""
        cb = [b for b in bl if b["class"] == c]
        cn = str(len(cb)) if c else ""
        first = next((b["id"] for b in cb if b["new_class"]), "") if c else ""
        out.append(f"| {s} | {sn} | | {c} | {cn} | {first} |")
    out += _curve(bl, estates, sizes)
    out += ["", "## Blocker log", "",
            "| id | after round | estate | side | class | new class | programs | issue / fix | refused by name | summary |",
            "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for b in bl:
        ref = " / ".join(x for x in (f"#{b['issue']}" if b.get("issue") else "", b.get("fixed_by") or "") if x)
        out.append(
            f"| {b['id']} | {b['after_round']} | {b['estate'] or 'none'} | {b['side']} | {b['class']} | "
            f"{'yes' if b['new_class'] else 'no'} | {', '.join(b['programs'])} | {ref} | "
            f"{'yes' if b['refused_by_name'] else 'no'} | {b['summary'].replace('|', '/')} |"
        )
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("report")
    rp.add_argument("--write", action="store_true", help=f"write {REPORT.relative_to(REPO_ROOT)}")
    sub.add_parser("check")
    args = ap.parse_args()
    ledger, registry = load()
    burned = burned_names()
    errors = validate(ledger, registry, burned)
    if errors:
        print("port_blockers.json is invalid:\n  " + "\n  ".join(errors))
        return 1
    text = render(ledger, registry, burned)
    if args.cmd == "report":
        if args.write:
            REPORT.write_text(text, encoding="utf-8")
            print(f"wrote {REPORT.relative_to(REPO_ROOT)}")
        else:
            sys.stdout.write(text)
        return 0
    if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != text:
        print(f"{REPORT.relative_to(REPO_ROOT)} is stale: run `python tests/tools/port_blockers.py report --write`")
        return 1
    print("port blockers ledger: valid, report up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
