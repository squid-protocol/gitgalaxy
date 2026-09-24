"""
Semantic diff of the mainframe ground truth between two git revisions: the
answer keys (tests/cobol_mainframe/answer_key/) and the ground-truth ledger.

    python tests/tools/ground_truth_diff.py [--base origin/main] [--head HEAD] [--summary out.md]

What a reviewer needs to see, and what a raw JSON diff buries:

- **Key truth changes**, per program: dead verdicts added or removed, units,
  PROGRAM-ID, copybooks, calls and files. The key is the oracle, so every change
  to it needs the source evidence in the PR.
- **Truth changed after census**: a program whose answers changed while its
  `verification.census` stamp did not. The census vouched for the OLD answers;
  re-census it (cross_verify.py census, then grade, then sign).
- **Ledger causes** added or removed, with the entry count behind each.
- **A cause whose kind went defect → deliberate.** This is the one way to turn a
  real defect green without fixing it, so it is flagged as a warning every time.
- **Scoreboard movement**: P/R per corpus, field and side, before → after.

Exit status is always 0. It reports; the ledger check and the census test gate.
Warnings are printed as GitHub `::warning` annotations when running in Actions.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
KEY_DIR = "tests/cobol_mainframe/answer_key"
LEDGER = "tests/cobol_mainframe/ground_truth_ledger.json"
TRUTH_KEYS = ("program_id", "units", "dead", "copybooks", "calls", "files")


def _show(rev: str, path: str) -> Optional[dict[str, Any]]:
    """The JSON at `path` in `rev`, or None if it does not exist there."""
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "show", f"{rev}:{path}"],  # noqa: S607
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    return json.loads(out)


def _keys_at(rev: str) -> dict[str, str]:
    out = subprocess.run(  # noqa: S603
        ["git", "ls-tree", "--name-only", f"{rev}", f"{KEY_DIR}/"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return {Path(p).stem: p for p in out.split() if p.endswith(".json")}


def _names(value: Any) -> set[str]:
    """A comparable set for one truth field."""
    if isinstance(value, dict):
        return set(value)
    if isinstance(value, list):
        return {json.dumps(v, sort_keys=True) if not isinstance(v, str) else v for v in value}
    return {str(value)}


def _unit_names(units: list[dict[str, Any]]) -> set[str]:
    return {u["name"] for u in units}


def diff_keys(base: dict[str, Any], head: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(report lines, warnings) for one corpus key."""
    lines: list[str] = []
    warnings: list[str] = []
    bp, hp = base.get("programs", {}), head.get("programs", {})
    for rel in sorted(set(bp) | set(hp)):
        if rel not in bp:
            lines.append(f"- `{rel}`: **new program**")
            continue
        if rel not in hp:
            lines.append(f"- `{rel}`: **removed**")
            continue
        b, h = bp[rel], hp[rel]
        moved = []
        for k in TRUTH_KEYS:
            if b.get(k) == h.get(k):
                continue
            if k == "units":
                bs, hs = _unit_names(b.get(k, [])), _unit_names(h.get(k, []))
            elif k in ("copybooks", "calls", "files"):
                ident = {"copybooks": ("name", "resolves_to"), "calls": ("verb", "operand"), "files": ("dd", "modes")}[
                    k
                ]
                bs = {json.dumps([x.get(i) for i in ident]) for x in b.get(k, [])}
                hs = {json.dumps([x.get(i) for i in ident]) for x in h.get(k, [])}
            else:
                bs, hs = _names(b.get(k)), _names(h.get(k))
            added, removed = sorted(hs - bs), sorted(bs - hs)
            if added or removed:
                moved.append(f"{k}: +{added[:4]} -{removed[:4]}" + (" …" if len(added) > 4 or len(removed) > 4 else ""))
            else:
                moved.append(f"{k}: reordered or re-annotated")
        tier_b, tier_h = b["verification"].get("tier"), h["verification"].get("tier")
        if tier_b != tier_h:
            moved.append(f"tier: {tier_b} → {tier_h}")
        if moved:
            lines.append(f"- `{rel}`: " + "; ".join(moved))
            truth_changed = any(b.get(k) != h.get(k) for k in TRUTH_KEYS)
            census_b, census_h = b["verification"].get("census"), h["verification"].get("census")
            if truth_changed and census_h and census_h == census_b:
                warnings.append(
                    f"{head.get('corpus')}:{rel}: truth changed but its census stamp did not; re-census it "
                    "(cross_verify.py census, then grade, then sign)"
                )
    return lines, warnings


def diff_ledger(base: Optional[dict[str, Any]], head: Optional[dict[str, Any]]) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    warnings: list[str] = []
    base = base or {"causes": {}, "corpora": {}}
    head = head or {"causes": {}, "corpora": {}}

    def counts(led: dict[str, Any]) -> dict[str, int]:
        out: dict[str, int] = {}
        for rec in led.get("corpora", {}).values():
            for cause in rec.get("mismatches", {}).values():
                out[cause] = out.get(cause, 0) + 1
        return out

    cb, ch = counts(base), counts(head)
    rows = []
    for cause in sorted(set(cb) | set(ch) | set(base["causes"]) | set(head["causes"])):
        kb = base["causes"].get(cause, {}).get("kind")
        kh = head["causes"].get(cause, {}).get("kind")
        nb, nh = cb.get(cause, 0), ch.get(cause, 0)
        if (nb, kb) == (nh, kh):
            continue
        rows.append(f"| `{cause}` | {kb or '—'} → {kh or '—'} | {nb} → {nh} |")
        if kb == "defect" and kh == "deliberate":
            warnings.append(
                f"ledger cause {cause!r} changed kind defect → deliberate: justify it in the PR, or fix the defect"
            )
    if rows:
        lines += ["| cause | kind | mismatches |", "|---|---|---|", *rows, ""]

    sb_rows = []
    for corpus in sorted(set(base["corpora"]) | set(head["corpora"])):
        bsb = base["corpora"].get(corpus, {}).get("scoreboard", {})
        hsb = head["corpora"].get(corpus, {}).get("scoreboard", {})
        for field in sorted(set(bsb) | set(hsb)):
            for side in ("engine", "forge"):
                b = (bsb.get(field) or {}).get(side)
                h = (hsb.get(field) or {}).get(side)
                if b != h:

                    def fmt(x: Optional[dict[str, int]]) -> str:
                        return f"P {x['tp']}/{x['got']} R {x['tp']}/{x['truth']}" if x else "n/a"

                    sb_rows.append(f"| {corpus} | {field} | {side} | {fmt(b)} | {fmt(h)} |")
    if sb_rows:
        lines += ["| corpus | field | side | before | after |", "|---|---|---|---|---|", *sb_rows, ""]
    return lines, warnings


def report(base_rev: str, head_rev: str) -> tuple[str, list[str]]:
    md = [f"## Mainframe ground truth: {base_rev} → {head_rev}", ""]
    warnings: list[str] = []
    bk, hk = _keys_at(base_rev), _keys_at(head_rev)
    any_key = False
    for corpus in sorted(set(bk) | set(hk)):
        b = _show(base_rev, bk[corpus]) if corpus in bk else {"programs": {}}
        h = _show(head_rev, hk[corpus]) if corpus in hk else {"programs": {}}
        if b == h:
            continue
        lines, w = diff_keys(b or {"programs": {}}, h or {"programs": {}})
        warnings += w
        if lines:
            any_key = True
            md += [f"### Answer key: {corpus}", "", *lines, ""]
    if not any_key:
        md += ["No answer-key truth changed.", ""]
    lines, w = diff_ledger(_show(base_rev, LEDGER), _show(head_rev, LEDGER))
    warnings += w
    md += ["### Ledger", "", *(lines or ["No ledger change.", ""])]
    if warnings:
        md += ["### ⚠️ Needs attention", "", *[f"- {x}" for x in warnings], ""]
    return "\n".join(md) + "\n", warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--summary", type=Path)
    args = ap.parse_args()
    md, warnings = report(args.base, args.head)
    print(md)
    for w in warnings:
        print(f"::warning title=Ground truth::{w}" if os.environ.get("GITHUB_ACTIONS") else f"WARNING {w}")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as fh:
            fh.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
