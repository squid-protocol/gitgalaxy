#!/usr/bin/env python3
"""#4270: the det sweep's coverage, committed -- so main can see it.

    python tests/tools/det_coverage_ledger.py update SWEEP [SWEEP ...]   # write tests/equivalence/det_sweep_coverage.json
    python tests/tools/det_coverage_ledger.py check  SWEEP [SWEEP ...]   # the ratchet CI's det-sweep applies

SWEEP is a `proof_sweep.py --det-only` work directory (or its sweep.json): per case the proof's coverage line,
"proven on N scenarios, covering P/L paragraphs and B/T branches". The ledger keeps those numbers for each PROVEN
case, keyed to the fingerprints of the inputs the COBOL-side coverage depends on (tests/tools/evidence.py's: the case
directory, the corpus pin, the harness, the oracle -- not the Java generator, which cannot change what the COBOL runs):

  {"format": "det-sweep-coverage/1", "about": ..., "cases": {CASE: {"scenarios": N,
     "paragraphs": {"covered": P, "live": L}, "branches": {"covered": B, "total": T},
     "inputs": {"case": SHA, "corpus": SHA, "harness": SHA, "oracle": SHA}}}}

Every number in it is read off a sweep's coverage line, none is computed or written by hand. A reader
(proof_blockers.py) trusts an entry only while `fresh()`; a stale or missing entry is "unknown", as before.

The check (run by `proof_sweep.py --aggregate` in CI's det-sweep, after the verdict ratchet): for every proven case
in the sweep, the ledger must hold its numbers. It FAILS on a missing entry, on numbers the sweep disagrees with, and on
a stale case / corpus fingerprint (the change that moved them re-proves the case: refresh); a stale harness / oracle
fingerprint only warns (a scheduled refresh), as evidence records do. It also fails on an entry for a case that does
not exist. A case the sweep proved with no coverage line cannot be checked and is reported.
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
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

CASES = REPO / "tests" / "equivalence"
LEDGER = CASES / "det_sweep_coverage.json"
FORMAT = "det-sweep-coverage/1"
INPUTS = ("case", "corpus", "harness", "oracle")
BLOCKING = ("case", "corpus")  # stale here: the change re-proves the case, so the ledger is refreshed in the same PR
_LINE = re.compile(r"proven on (\d+) scenarios?, covering (\d+)/(\d+) paragraphs and (\d+)/(\d+) branches")
ABOUT = ("#4270: the paragraph / branch coverage of each det-proven case, as `proof_sweep.py --det-only` reported it; "
         "written only by `tests/tools/det_coverage_ledger.py update SWEEP_DIR...`, checked by CI's det-sweep. An entry is "
         "trusted only while its input fingerprints match the tree (proof_blockers.py); stale or missing stays unknown.")  # fmt: skip


def parse_line(line: str) -> dict[str, Any] | None:
    """A sweep row's coverage line -> the ledger's numbers (None for a case not proven or with no line)."""
    m = _LINE.search(line or "")
    if not m:
        return None
    n, pc, pl, bc, bt = (int(x) for x in m.groups())
    return {"scenarios": n, "paragraphs": {"covered": pc, "live": pl}, "branches": {"covered": bc, "total": bt}}


def fingerprints(case: str) -> dict[str, str]:
    """The case's input fingerprints in the tree now (tests/tools/evidence.py's scheme)."""
    import evidence as ev  # noqa: PLC0415 -- git-backed; only when a ledger is written / checked

    now = ev.compute_inputs(ev.equivalence_target(case))
    return {name: now[name]["sha256"] for name in INPUTS}


def load(path: Path = LEDGER) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")).get("cases", {}) if path.is_file() else {}


def stale(entry: dict[str, Any], now: dict[str, str]) -> list[str]:
    """The inputs whose fingerprint differs from the tree's."""
    return [n for n in INPUTS if (entry.get("inputs") or {}).get(n) != now.get(n)]


def fresh_coverage(case: str, ledger: dict[str, dict[str, Any]]) -> tuple[int, int, int, int] | None:
    """(paragraphs covered, live, branches covered, total) of a case whose entry is fresh in the tree, else None."""
    entry = ledger.get(case)
    if not entry or not (CASES / case / "case.json").is_file():
        return None
    try:
        if stale(entry, fingerprints(case)):
            return None
    except (RuntimeError, KeyError, OSError):
        return None
    p, b = entry["paragraphs"], entry["branches"]
    return p["covered"], p["live"], b["covered"], b["total"]


def sweep_rows(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        f = d / "sweep.json" if d.is_dir() else d
        out.update(json.loads(f.read_text(encoding="utf-8")).get("det", {}))
    return out


def build(det: dict[str, dict[str, Any]], old: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """`old` with the entries of the sweep's proven cases rewritten (others kept; an entry for a case no longer
    in the tree dropped)."""
    cases = {c: e for c, e in old.items() if (CASES / c / "case.json").is_file()}
    for case, row in sorted(det.items()):
        nums = parse_line(row.get("coverage", "")) if row.get("proved") else None
        if nums is not None:
            cases[case] = {**nums, "inputs": fingerprints(case)}
    return dict(sorted(cases.items()))


def check(det: dict[str, dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(problems, warnings) of the sweep against the ledger."""
    problems, warnings = [], []
    if not LEDGER.is_file() or not _tracked(LEDGER):
        problems.append(f"coverage ledger: {LEDGER.name} is not a committed file (git-ignored?)")
    fix = "python tests/tools/det_coverage_ledger.py update <the sweep's DIR(s)>"
    for case in sorted(ledger):
        if not (CASES / case / "case.json").is_file():
            problems.append(f"coverage ledger: {case}: no such case any more -- {fix}")
    for case, row in sorted(det.items()):
        if not row.get("proved"):
            continue
        nums = parse_line(row.get("coverage", ""))
        if nums is None:
            warnings.append(f"coverage ledger: {case}: proven with no coverage line; cannot be checked")
            continue
        entry = ledger.get(case)
        if entry is None:
            problems.append(f"coverage ledger: {case}: no entry -- {fix}")
            continue
        got = {k: entry.get(k) for k in nums}
        if got != nums:
            problems.append(f"coverage ledger: {case}: the sweep covered {_show(nums)}, the ledger has {_show(got)} "
                            f"-- coverage moved: if intended, {fix}")  # fmt: skip
        now = fingerprints(case)
        bad = stale(entry, now)
        if [n for n in bad if n in BLOCKING]:
            problems.append(f"coverage ledger: {case}: stale ({', '.join(bad)} changed) -- {fix}")
        elif bad:
            warnings.append(f"coverage ledger: {case}: stale ({', '.join(bad)} changed); refresh when convenient")
    return problems, warnings


def _tracked(path: Path) -> bool:
    """The file is in git's index (an ignored, uncommitted ledger is not)."""
    import subprocess  # noqa: PLC0415

    return subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(path)],  # noqa: S603, S607
                          capture_output=True, check=False).returncode == 0  # fmt: skip


def _show(n: dict[str, Any]) -> str:
    try:
        return (f"{n['scenarios']} scenarios, {n['paragraphs']['covered']}/{n['paragraphs']['live']} paragraphs, "
                f"{n['branches']['covered']}/{n['branches']['total']} branches")  # fmt: skip
    except (KeyError, TypeError):
        return "?"


def write(cases: dict[str, dict[str, Any]], path: Path = LEDGER) -> None:
    path.write_text(json.dumps({"format": FORMAT, "about": ABOUT, "cases": cases}, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("update", "check"))
    ap.add_argument("sweep", type=Path, nargs="+", help="proof_sweep.py work directories (or sweep.json files)")
    args = ap.parse_args(argv)
    det = sweep_rows(args.sweep)
    if args.mode == "update":
        cases = build(det, load())
        write(cases)
        print(f"{LEDGER.relative_to(REPO)}: {len(cases)} cases")
        return 0
    problems, warnings = check(det, load())
    for w in warnings:
        print(f"warning: {w}")
    for p in problems:
        print(p)
    print("coverage ledger: as expected" if not problems else f"coverage ledger: {len(problems)} unexpected")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
