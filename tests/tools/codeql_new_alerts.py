#!/usr/bin/env python3
"""The CodeQL results a pull request adds, against main's latest analysis (the step after Analyze in codeql.yml).

    python tests/tools/codeql_new_alerts.py --sarif DIR_OR_FILE --baseline MAIN.sarif [--files FILE ...]
                                            [--summary PATH] [--enforce]

Open alerts went 34 -> 459 in five weeks while every PR's CodeQL check read "No new alerts": a PR's analysis held no
results at all (#6719 added alerts and its SARIF has 0, main's has 405). A result counts as new when its rule, file and
CodeQL's line-content hash are not in main's analysis, the same rule and hash aren't elsewhere on main (moved code), and
the file has more of that rule than main does (a hash also changes when a neighbouring line does). Only files the PR
changed count, so debt already on main is never blamed on it.

--enforce exits 1 on a new error or warning, leaving out ADVISORY_RULES; every new result is still reported. It also
exits 1 on a blind scan, under half of main's results: "no new results" from a scan that saw nothing is how this gate
went unnoticed for weeks. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HASH = "primaryLocationLineHash"
BLOCKING_LEVELS = ("error", "warning")  # owner 2026-10-30: notes are reported, never block
# Proven false on this code (#7153): language regexes compile with re.M through _lazy_re, which CodeQL can't see, and
# `...` stubs under TYPE_CHECKING declare a mixin's members.
ADVISORY_RULES = frozenset({"py/regex/unmatchable-caret", "py/regex/unmatchable-dollar", "py/ineffectual-statement"})


def rule_levels(run: dict) -> dict[str, str]:
    """Each rule's default level: results usually leave it out, and the rules sit in the tool's extensions."""
    tool = run.get("tool") or {}
    out = {}
    for part in [tool.get("driver") or {}, *(tool.get("extensions") or [])]:
        for rule in part.get("rules") or []:
            out[rule.get("id", "")] = (rule.get("defaultConfiguration") or {}).get("level", "warning")
    return out


def results(sarif: dict) -> list[dict]:
    """Every unsuppressed result as {rule, path, line, hash, level}."""
    out = []
    for run in sarif.get("runs") or []:
        levels = rule_levels(run)
        for r in run.get("results") or []:
            if r.get("suppressions"):
                continue
            loc = ((r.get("locations") or [{}])[0].get("physicalLocation") or {})
            rule = r.get("ruleId") or (r.get("rule") or {}).get("id", "")
            out.append({"rule": rule, "path": (loc.get("artifactLocation") or {}).get("uri", ""),
                        "line": (loc.get("region") or {}).get("startLine", 0),
                        "hash": (r.get("partialFingerprints") or {}).get(HASH, ""),
                        "level": r.get("level") or levels.get(rule, "warning")})
    return out


def new_results(pr: list[dict], main: list[dict], files: list[str] | None) -> list[dict]:
    """The PR's results that main doesn't have, in the files it changed (all of them when `files` is None)."""
    known = {(r["rule"], r["path"], r["hash"]) for r in main}
    moved = {(r["rule"], r["hash"]) for r in main}
    room = Counter((r["rule"], r["path"]) for r in pr)  # how many more of this rule the file has than main
    room.subtract(Counter((r["rule"], r["path"]) for r in main))
    wanted = None if files is None else set(files)
    out = []
    for r in pr:
        key = (r["rule"], r["path"])
        if (wanted is None or r["path"] in wanted) and (*key, r["hash"]) not in known and (r["rule"], r["hash"]) not in moved \
                and room[key] > 0:
            room[key] -= 1
            out.append(r)
    return out


def blocking(new: list[dict]) -> list[dict]:
    """The new results that fail an enforced run."""
    return [r for r in new if r["level"] in BLOCKING_LEVELS and r["rule"] not in ADVISORY_RULES]


def blind(scanned: int, baseline: int) -> bool:
    """The PR's scan saw too little to mean anything. A PR keeps nearly all of main's code, so its results stay close."""
    return scanned * 2 < baseline


def load(path: Path) -> list[dict]:
    """Results of one SARIF file, or of every .sarif file in a directory (codeql-action writes one per language)."""
    files = sorted(path.glob("*.sarif")) if path.is_dir() else [path]
    return [r for f in files for r in results(json.loads(f.read_text(encoding="utf-8")))]


def report(new: list[dict], scanned: int, baseline: int, enforce: bool) -> str:
    blocked = blocking(new)
    failing = enforce and (blocked or blind(scanned, baseline))
    verdict = "fails this PR" if failing else "reported, nothing blocks" if new else "clean"
    lines = [f"### CodeQL: {len(new)} new result(s), {len(blocked)} blocking ({verdict})", "",
             f"PR analysis {scanned} results, main's {baseline}. New means not on main, in a file this PR changed.", ""]
    if blind(scanned, baseline):
        lines += [f"**This scan looks blind: {scanned} results against main's {baseline}. It can't vouch for this PR.**", ""]
    if new:
        for rule, n in Counter(r["rule"] for r in new).most_common():
            lines.append(f"- `{rule}`: {n}")
        lines += ["", "| Level | Rule | Where |", "|---|---|---|"]
        lines += [f'| {r["level"]} | `{r["rule"]}` | `{r["path"]}:{r["line"]}` |' for r in new[:50]]
        if len(new) > 50:
            lines.append(f"\n...and {len(new) - 50} more.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sarif", type=Path, required=True)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--files", nargs="*", help="files the PR changed; left out, every result counts")
    p.add_argument("--summary", type=Path, help="append the report here (the job summary)")
    p.add_argument("--enforce", action="store_true", help="exit 1 on a new error or warning")
    a = p.parse_args(argv)
    pr, base = load(a.sarif), load(a.baseline)
    new = new_results(pr, base, a.files)
    text = report(new, len(pr), len(base), a.enforce)
    print(text)
    if a.summary:
        with a.summary.open("a", encoding="utf-8") as f:
            f.write(text)
    return 1 if a.enforce and (blocking(new) or blind(len(pr), len(base))) else 0


if __name__ == "__main__":
    sys.exit(main())
