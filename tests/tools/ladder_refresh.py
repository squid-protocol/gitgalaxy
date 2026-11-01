#!/usr/bin/env python3
"""#6072: the post-edit chain a ladder slice runs by hand, as one command.

    python tests/tools/ladder_refresh.py CASE [CASE ...] [--work DIR] [--dry-run] [--skip-tests]

For the burned-estate equivalence cases named (tests/equivalence/<CASE>/), in order:
  1. record the ledger's paragraph / net-branch coverage (the BEFORE of the table);
  2. proof_sweep.py --det-only --cases ... --faults all: the sweep CI's det-sweep compares, SQL-fault tasks included;
  3. det_coverage_ledger.py update on that sweep (only when every case proved: a case that did not stops the chain);
  4. evidence.py prove CASE, for each case that has an evidence.json record (never approve, never hand-edit);
  5. the pin tests that name the case or its program (grep of tests/, bar tests/equivalence), plus the
     test_harness_report STATED_RULES check and the coverage-ledger tests;
  6. print before / after paragraph and net-branch coverage as the PR-body table.

Burned estates only (estate4_draw.BURNED_NAMES): a case of any other corpus is refused. Heavy steps run under
tests/tools/box/heavy-run.sh. Run it again after every `git merge origin/main`: a merge can move the inputs the ledger
fingerprints and the numbers the table reports.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

from gitgalaxy.core.source_text import read_source  # noqa: E402

EQUIVALENCE = REPO / "tests" / "equivalence"
HEAVY = TOOLS / "box" / "heavy-run.sh"
ALWAYS_TESTS = ("tests/tools/test_harness_report.py", "tests/tools/test_det_coverage_ledger.py")

Runner = Callable[[list[str]], int]


def run(argv: list[str]) -> int:
    return subprocess.run(argv, cwd=REPO, check=False).returncode  # noqa: S603


def case_problems(cases: list[str]) -> list[str]:
    """Why a CASE cannot be refreshed: no such case, or a corpus that is not a burned estate."""
    from estate4_draw import BURNED_NAMES  # noqa: PLC0415 -- heavy import, only when cases are checked

    # owner OK 2026-10-31 (#6072): cics-crucible counts as a burned estate for the ladder (BURNED_NAMES is unchanged)
    ladder_estates = BURNED_NAMES | {"cics-crucible"}
    out = []
    for c in cases:
        f = EQUIVALENCE / c / "case.json"
        if not f.is_file():
            out.append(f"{c}: no such case (tests/equivalence/{c}/case.json)")
            continue
        corpus = str(json.loads(f.read_text(encoding="utf-8")).get("corpus", "")).lower()
        if corpus not in ladder_estates:
            out.append(f"{c}: corpus {corpus!r} is not a burned estate (mainframe-evidence-policy.md section 2)")
    return out


def program_of(case: str) -> str:
    return str(json.loads((EQUIVALENCE / case / "case.json").read_text(encoding="utf-8")).get("program", ""))


def pin_tests(cases: list[str], root: Path | None = None) -> list[str]:
    """Repo-relative test files (bar tests/equivalence) that name a case or its program, as whole words."""
    root = root or REPO
    names = {n for c in cases for n in (c, program_of(c)) if n}
    pat = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in sorted(names)) + r")(?![\w-])", re.I)
    out = []
    for f in sorted((root / "tests").rglob("*.py")):
        rel = f.relative_to(root)
        if "equivalence" in rel.parts or f.name == Path(__file__).name or f.name == "test_ladder_refresh.py":
            continue
        if pat.search(read_source(f).text):
            out.append(rel.as_posix())
    return out


def numbers(entry: dict[str, Any] | None) -> tuple[int, int, int, int] | None:
    """A ledger entry (or a ledger.parse_line result) -> (paragraphs covered, live, branches covered, total)."""
    if not entry:
        return None
    p, b = entry["paragraphs"], entry["branches"]
    return p["covered"], p["live"], b["covered"], b["total"]


def _pct(covered: int, total: int) -> str:
    return "n/a" if not total else f"{100 * covered / total:.1f}"


def _cell(n: tuple[int, int, int, int] | None, i: int) -> str:
    return "-" if n is None else f"{_pct(n[i], n[i + 1])} ({n[i]}/{n[i + 1]})"


def table(rows: list[tuple[str, Any, Any, str]]) -> str:
    """The PR-body table: (case, before, after, verdict) -> markdown. before / after are numbers() tuples or None."""
    out = ["| case | paragraphs before | paragraphs after | net branches before | net branches after | proof |",
           "|---|---|---|---|---|---|"]  # fmt: skip
    for case, before, after, verdict in rows:
        out.append(
            f"| {case} | {_cell(before, 0)} | {_cell(after, 0)} | {_cell(before, 2)} | {_cell(after, 2)} | {verdict} |"
        )
    return "\n".join(out)


def has_record(case: str) -> bool:
    return (EQUIVALENCE / case / "evidence.json").is_file()


def chain(cases: list[str], work: Path, *, skip_tests: bool = False, runner: Runner = run,
          python: str = sys.executable) -> tuple[int, list[tuple[str, Any, Any, str]]]:  # fmt: skip
    """Run the chain; (exit code, table rows). The sweep result is read from work/sweep.json."""
    import det_coverage_ledger as dcl  # noqa: PLC0415

    ledger = dcl.load()
    before = {c: numbers(ledger.get(c)) for c in cases}
    heavy = [str(HEAVY)]
    sweep = [*heavy, python, str(TOOLS / "proof_sweep.py"), "--det-only", "--faults", "all", "--no-ratchet",
             "--work", str(work), "--cases", ",".join(cases)]  # fmt: skip
    runner(sweep)
    try:
        det = json.loads((work / "sweep.json").read_text(encoding="utf-8")).get("det", {})
    except (OSError, ValueError):
        print("ladder_refresh: the sweep wrote no sweep.json", file=sys.stderr)
        return 1, [(c, before[c], None, "no sweep") for c in cases]
    after, verdicts, unproven = {}, {}, []
    for c in cases:
        row = det.get(c) or {}
        after[c] = numbers(dcl.parse_line(row.get("coverage", "")))
        verdicts[c] = "proven" if row.get("proved") else "NOT PROVEN"
        if not row.get("proved"):
            unproven.append(c)
    rows = [(c, before[c], after[c], verdicts[c]) for c in cases]
    if unproven:
        print(
            f"ladder_refresh: not proven: {', '.join(unproven)}; the ledger, evidence and tests are not run",
            file=sys.stderr,
        )
        return 1, rows
    rc = runner([python, str(TOOLS / "det_coverage_ledger.py"), "update", str(work)])
    for c in cases:
        if has_record(c):
            rc = runner([*heavy, python, str(TOOLS / "evidence.py"), "prove", c]) or rc
    if not skip_tests:
        tests = [*ALWAYS_TESTS, *pin_tests(cases)]
        rc = runner([python, "-m", "pytest", "-q", *dict.fromkeys(tests)]) or rc
    return rc, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="+", metavar="CASE")
    ap.add_argument("--work", type=Path, help="the sweep's work directory (default: a fresh one under /tmp)")
    ap.add_argument("--dry-run", action="store_true", help="print the chain's steps and the pin tests, run nothing")
    ap.add_argument("--skip-tests", action="store_true", help="leave out the pin tests")
    args = ap.parse_args(argv)
    if bad := case_problems(args.cases):
        print("\n".join(bad), file=sys.stderr)
        return 2
    if args.dry_run:
        print("sweep:", ",".join(args.cases))
        print("evidence prove:", ", ".join(c for c in args.cases if has_record(c)) or "(no record)")
        print("tests:", *dict.fromkeys([*ALWAYS_TESTS, *pin_tests(args.cases)]), sep="\n  ")
        return 0
    work = args.work or Path(tempfile.mkdtemp(prefix="ladder-refresh-", dir="/tmp"))
    rc, rows = chain(args.cases, work, skip_tests=args.skip_tests)
    print("\n" + table(rows))
    return rc


if __name__ == "__main__":
    sys.exit(main())
