#!/usr/bin/env python3
"""#5054: ingest a customer's anonymized blocker report as rows of a customer-side blocker ledger.

    python tests/tools/blocker_ingest.py REPORT.anon.json --ledger FILE [--signatures FILE]

Each blocker becomes one row shaped like a #5051 port-blocker row (`estate: customer:<EST hash>`, `side`, `class`),
linked to an existing issue when its construct signature matches the catalogue
(tests/cobol_mainframe/blocker_signatures.json) and otherwise left `issue: null` with a drafted issue body printed
for the tick to file. Rows go to --ledger, never to the committed port_blockers.json (that one is burned estates only).
The report is checked against the published schema first: an unknown field, an identifier that is not a hash, or a
signature word outside the allow-listed vocabulary refuses the file. Re-ingesting a report changes nothing; a report
from a later engine version appends to the row's `seen_in`, which is how "still open after 3 releases" shows.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TOOLS))
import blocker_report as br  # noqa: E402

SIGNATURES = REPO / "tests" / "cobol_mainframe" / "blocker_signatures.json"
SUPPORTED = ("1.1", "1.2")

# blocker_report category -> (#5051 side, class). Every CATEGORIES value has one.
CATEGORY_CLASS = {
    "unresolved-link": ("det", "data-layout"),
    "refusal": ("det", "cobol-dialect"),
    "cics-command": ("det", "cics-command"),
    "runtime-fact": ("runtime", "eib-fact"),
    "no-case": ("harness", "ci-gate"),
    "known-unproven": ("harness", "oracle-model"),
    "scenario-differs": ("det", "control-flow"),
    "coverage": ("harness", "control-flow"),
    "environment": ("harness", "ci-gate"),
    "other": ("det", "cobol-dialect"),
}
_ANY_HASH = re.compile(r"\b[A-Z]{3}_[0-9a-f]{%d}\b" % br.HASH_HEX)


def check_report(rep: dict[str, Any]) -> list[str]:
    """Why a report is refused (empty when it is a well-formed anonymized report)."""
    errors: list[str] = []
    if rep.get("kind") != "anonymized":
        return [f"kind must be 'anonymized', got {rep.get('kind')!r}"]
    if rep.get("schema_version") not in SUPPORTED:
        errors.append(f"unsupported schema_version {rep.get('schema_version')!r} (supported: {', '.join(SUPPORTED)})")
    for k in rep:
        if k not in br.ANON_REPORT_FIELDS:
            errors.append(f"unknown report field {k!r}")
    if not re.fullmatch(r"EST_[0-9a-f]{%d}" % br.HASH_HEX, str(rep.get("estate"))):
        errors.append("estate must be a salted EST_xxxxxx hash")
    vocab = br.vocabulary()
    for i, b in enumerate(rep.get("blockers", [])):
        where = f"blockers[{i}]"
        for k in b:
            if k not in br.ANON_BLOCKER_FIELDS:
                errors.append(f"{where}: unknown field {k!r}")
        if b.get("category") not in br.CATEGORIES:
            errors.append(f"{where}: unknown category {b.get('category')!r}")
        if not re.fullmatch(r"BLK_[0-9a-f]{%d}" % br.HASH_HEX, str(b.get("id"))):
            errors.append(f"{where}: id must be a BLK_xxxxxx hash")
        if "construct" in b and (_ANY_HASH.search(str(b["construct"])) or len(str(b["construct"])) > 160):
            errors.append(f"{where}: construct is not a ranking key")
        for word in re.split(r"\s+", str(b.get("signature", ""))):
            if not (_ANY_HASH.fullmatch(word) or word in vocab or _public_word(word)):
                errors.append(f"{where}: signature word outside the allow-list: {word!r}")
    return errors


def _public_word(word: str) -> bool:
    """Words the classifier itself emits from fixed phrases (not CICS vocabulary): gap phrases, refusal classes."""
    fixed = {w for g in br._FIXED for w in re.sub(r"[:(),]", " ", g).split()}
    fixed |= {"missing", "copybook", "ambiguous", "refused", "fact", "known", "unproven", "scenario", "differs",
              "LINKed", "program", "paragraphs", "branches", "unclassified", "unknown", "macro-level", "Assembler",
              "reason", "given", "output", "java", "side", "failed", "report", "kept", "diff", "recorded"}  # fmt: skip
    return word.strip(":(),") in fixed or bool(re.fullmatch(r"[A-Z][A-Za-z]*(?:Error|Exception|Refusal)|#\d+", word))


def normalise(sig: str) -> str:
    """Replace each KIND_xxxxxx by KIND_*, so the same construct matches whatever the customer's salt."""
    return _ANY_HASH.sub(lambda m: m.group(0)[:3] + "_*", sig)


def load_catalogue(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or SIGNATURES
    entries = json.loads(path.read_text(encoding="utf-8"))["signatures"]
    return sorted(entries, key=lambda e: -len(e["prefix"]))


def match_issue(category: str, signature: str, catalogue: list[dict[str, Any]]) -> int | None:
    norm = normalise(signature)
    if category == "known-unproven" and (m := re.fullmatch(r"known unproven: #(\d+)", norm)):
        return int(m.group(1))
    for e in catalogue:
        if e["category"] == category and (norm == e["prefix"] or norm.startswith(e["prefix"] + " ")):
            return int(e["issue"])
    return None


def row_id(estate: str, blk: str) -> str:
    return f"C-{estate[4:]}-{blk[4:]}"


def ingest(rep: dict[str, Any], ledger: dict[str, Any], catalogue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge the report's blockers into `ledger["rows"]`; return the rows that are new and match no issue."""
    errors = check_report(rep)
    if errors:
        raise ValueError("refused: " + "; ".join(errors))
    rows = {r["id"]: r for r in ledger.setdefault("rows", [])}
    estate, version = f"customer:{rep['estate']}", rep["engine_version"]
    fresh: list[dict[str, Any]] = []
    for b in rep["blockers"]:
        rid = row_id(rep["estate"], b["id"])
        side, cls = CATEGORY_CLASS[b["category"]]
        issue = match_issue(b["category"], b["signature"], catalogue)
        row = rows.get(rid)
        if row is None:
            row = {"id": rid, "estate": estate, "side": side, "class": cls, "category": b["category"],
                   "signature": b["signature"], "issue": issue, "seen_in": []}  # fmt: skip
            for k in ("subclass", "construct", "repro"):
                if k in b:
                    row[k] = b[k]
            rows[rid] = row
            if issue is None:
                fresh.append(row)
        if version not in row["seen_in"]:
            row["seen_in"].append(version)
        row["issue"] = row["issue"] or issue
        for k in ("programs_blocked", "programs_only_gap", "programs_one_away"):
            if k in b:
                row[k] = b[k]  # the latest report's counts
    ledger["rows"] = sorted(rows.values(), key=lambda r: r["id"])
    return fresh


def draft_issue(row: dict[str, Any]) -> str:
    out = [f"### Customer blocker {row['id']} ({row['category']}, {row['class']})", "",
           f"- signature: `{row['signature']}`",
           f"- programs blocked: {row.get('programs_blocked', 'redacted')}; only gap: {row.get('programs_only_gap', 'redacted')}",
           f"- seen in engine: {', '.join(row['seen_in'])}"]  # fmt: skip
    if row.get("repro"):
        out += ["", "```cobol", row["repro"].rstrip(), "```"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", type=Path, help="blocker_report.anon.json")
    ap.add_argument("--ledger", type=Path, required=True, help="customer-side ledger (created when missing)")
    ap.add_argument("--signatures", type=Path, help="signature catalogue (default: the committed one)")
    args = ap.parse_args(argv)
    rep = json.loads(args.report.read_text(encoding="utf-8"))
    ledger = json.loads(args.ledger.read_text(encoding="utf-8")) if args.ledger.is_file() else {}
    try:
        fresh = ingest(rep, ledger, load_catalogue(args.signatures))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    args.ledger.write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8")
    linked = sum(1 for r in ledger["rows"] if r["issue"])
    print(f"{len(ledger['rows'])} rows, {linked} linked to an issue, {len(fresh)} new without one")
    for r in fresh:
        print(draft_issue(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
