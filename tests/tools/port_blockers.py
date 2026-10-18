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


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads(LEDGER.read_text(encoding="utf-8")),
        json.loads(ESTATES.read_text(encoding="utf-8")),
    )


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


def render(ledger: dict[str, Any], registry: dict[str, Any], burned: set[str]) -> str:
    estates = [e for e in registry["estates"] if e["id"] in burned]
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
    out += [
        "",
        "## Discovery curve by round",
        "",
        "| after round | blockers | new classes |",
        "|---|---|---|",
    ]
    for r in sorted({b["after_round"] for b in bl}):
        at = [b for b in bl if b["after_round"] == r]
        out.append(f"| {r} | {len(at)} | {sum(1 for b in at if b['new_class'])} |")
    fresh = [b for b in bl if b["estate"] is not None]
    if fresh:
        mean = len(fresh) / len(estates)
        out += [
            "",
            "## Expected for the next estate",
            "",
            f"Mean logged blockers per burned estate: {mean:.1f} over {len(estates)} burned estates "
            f"({len(fresh)} blockers). This is a count of logged entries over a partial backfill, an "
            "indication of the order of magnitude; the issue's keyword count (~1.3 blockers per program on the first "
            "port falling to ~0.25 on the fifth, zECS excepted for new API areas) is the better prior until the "
            "backfill is complete.",
        ]
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
