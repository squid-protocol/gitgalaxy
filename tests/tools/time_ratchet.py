#!/usr/bin/env python3
"""Test-time ratchet: the suite must not get slower over time (#5166 part B).

    python tests/tools/time_ratchet.py check  [--times FILE]            # per-test gate (every PR): fails, warns
    python tests/tools/time_ratchet.py over   --times FILE... [--enforce]  # nightly: the tests over 10 s, for one issue
    python tests/tools/time_ratchet.py budget --times FILE... [--enforce]  # whole-suite budget
    python tests/tools/time_ratchet.py update --times FILE...           # shrink-only baseline + budget
    python tests/tools/time_ratchet.py seed   --times FILE... --budget SECONDS   # one time

A times file is either pytest-split's `.test_durations` ({nodeid: seconds}) or the file `tests/conftest.py` writes when
GITGALAXY_TEST_TIMES is set ({"seconds": {nodeid: s}, "slow": {nodeid: reason}}). `tests/test_time_baseline.json`
holds the tests over THRESHOLD_S with their recorded seconds and the suite budget.

Per test (runner noise is +-20-30%, so one timing at a hard 10 s edge was a coin flip, #5166): an unmarked, unbaselined
test fails only over 15 s (FAIL_S); between 10 s and 15 s it is a warning, written to the job summary. A baselined test
fails over 2.5x its recorded seconds. `slow` (with a reason) excuses an unbaselined test of any time. `over` lists every
test over 10 s that has neither (the nightly's one tracked issue). Suite: total over the budget by more than 10% fails
when --enforce (nightly main); a PR only reports.
Updates only lower: an entry drops to the new seconds, one at or under the threshold is removed, nothing is added or raised.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "tests" / "test_time_baseline.json"
DURATIONS = REPO / ".test_durations"
THRESHOLD_S = 10.0  # a test over this is tracked: warned about on a PR, listed by the nightly, baselined if it stays
FAIL_S = 15.0  # an unmarked, unbaselined test over this fails the PR check
FACTOR = 2.5
BUDGET_TOLERANCE = 0.10
# the full-suite parts ignore this file (mainframe-ground-truth.yml runs it, #5162), so it is not in the suite's time
IGNORED = ("tests/cobol_mainframe/test_evidence_components.py",)


def load_times(path: Path) -> tuple[dict[str, float], dict[str, str]]:
    """(seconds per nodeid, slow-marker reason per nodeid) from either file shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: not a times file (a JSON object)")
    slow: dict[str, str] = {}
    if isinstance(data.get("seconds"), dict):
        slow = dict(data.get("slow") or {})
        data = data["seconds"]
    return {k: float(v) for k, v in data.items() if not k.startswith(IGNORED)}, slow


def _is_slow_mark(node: ast.expr) -> bool:
    """`pytest.mark.slow` or `pytest.mark.slow(...)`, bare or called."""
    if isinstance(node, ast.Call):
        node = node.func
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "slow"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
    )


def slow_marks_from_source(nodeids: list[str], root: Path = REPO) -> dict[str, str]:
    """The slow marks `.test_durations` cannot carry: read from the test sources, as conftest.py reads them at run time.

    A test is slow when its function, its class or its module (`pytestmark`) has `pytest.mark.slow`. The reason is the
    marker's `reason=` text when it is a literal; conftest.py already refuses a mark without one.
    """
    found: dict[str, str] = {}
    trees: dict[str, ast.Module | None] = {}
    for nodeid in nodeids:
        rel, _, name = nodeid.partition("::")
        if rel not in trees:
            try:
                trees[rel] = ast.parse((root / rel).read_text(encoding="utf-8"))
            except (OSError, SyntaxError, ValueError):
                trees[rel] = None
        tree = trees[rel]
        if tree is None:
            continue
        func = name.split("[", 1)[0].split("::")[-1]
        module_slow = any(
            isinstance(n, ast.Assign)
            and any(getattr(t, "id", "") == "pytestmark" for t in n.targets)
            and any(
                _is_slow_mark(e) for e in (n.value.elts if isinstance(n.value, (ast.List, ast.Tuple)) else [n.value])
            )
            for n in tree.body
        )
        hit = module_slow
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and any(
                _is_slow_mark(d) for d in node.decorator_list
            ):
                if node.name == func or (
                    isinstance(node, ast.ClassDef) and "::" in name and node.name == name.split("::")[0]
                ):
                    hit = True
        if hit:
            found[nodeid] = "slow-marked in source"
    return found


def load_many(paths: list[Path]) -> tuple[dict[str, float], dict[str, str]]:
    """The union of several parts' times files; a nodeid in two parts keeps the larger seconds."""
    seconds: dict[str, float] = {}
    slow: dict[str, str] = {}
    for p in paths:
        s, sl = load_times(p)
        for k, v in s.items():
            seconds[k] = max(v, seconds.get(k, 0.0))
        slow.update(sl)
    return seconds, slow


def load_baseline(path: Path | None = None) -> dict:
    path = path or BASELINE
    return json.loads(path.read_text(encoding="utf-8"))


def check_tests(
    seconds: dict[str, float],
    baseline: dict[str, float],
    slow: dict[str, str] | None = None,
    fail_s: float = FAIL_S,
) -> list[str]:
    """Failures of the per-test gate. A baseline entry the run did not execute is ignored (a part runs a slice)."""
    slow = slow or {}
    out = []
    for nodeid, s in sorted(seconds.items()):
        if nodeid in baseline:
            if s > FACTOR * baseline[nodeid]:
                out.append(
                    f"{nodeid}: {s:.1f}s is over {FACTOR:g}x its baseline {baseline[nodeid]:.1f}s "
                    f"(make it faster, or mark it slow with a reason)"
                )
        elif s > fail_s and nodeid not in slow:
            out.append(
                f"{nodeid}: {s:.1f}s is over {fail_s:g}s and has no @pytest.mark.slow(reason=...) "
                f"and no entry in tests/test_time_baseline.json"
            )
    return out


def tests_over_threshold(
    seconds: dict[str, float], baseline: dict[str, float], slow: dict[str, str] | None = None
) -> list[tuple[str, float]]:
    """(nodeid, seconds) of the tests over THRESHOLD_S with neither a slow marker nor a baseline entry, slowest first."""
    slow = slow or {}
    rows = [(n, s) for n, s in seconds.items() if s > THRESHOLD_S and n not in baseline and n not in slow]
    return sorted(rows, key=lambda r: (-r[1], r[0]))


def shrink_tests(baseline: dict[str, float], seconds: dict[str, float]) -> dict[str, float]:
    """Lower each baseline entry to what was measured, drop those at or under the threshold; never raise or add."""
    out = {}
    for nodeid, old in baseline.items():
        new = min(old, seconds.get(nodeid, old))
        if new > THRESHOLD_S:
            out[nodeid] = round(new, 2)
    return out


def budget_delta(total: float, budget: float) -> float:
    """total / budget - 1 (positive: over budget)."""
    return total / budget - 1.0


def shrink_budget(budget: float, total: float) -> float:
    return round(min(budget, total), 1)


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_check(args: argparse.Namespace) -> int:
    seconds, slow = load_many(args.times or [DURATIONS])
    if not seconds:
        print("no test times read: refusing to pass on nothing", file=sys.stderr)
        return 2
    baseline = load_baseline()["tests"]
    if not args.times:  # the committed .test_durations has no slow marks; read them from the sources
        slow = {**slow_marks_from_source([n for n, s in seconds.items() if s > FAIL_S and n not in baseline]), **slow}
    bad = check_tests(seconds, baseline, slow)
    warned = [(n, s) for n, s in tests_over_threshold(seconds, baseline, slow) if s <= FAIL_S]
    for line in bad:
        print("FAIL " + line)
    for nodeid, s in warned:
        print(f"WARN {nodeid}: {s:.1f}s is over {THRESHOLD_S:g}s (fails over {FAIL_S:g}s; the nightly lists it)")
    print(f"{len(seconds)} tests checked, {len(bad)} over the per-test limit, {len(warned)} warned")
    _summary(
        "### Slow tests (warnings)",
        [f"- `{n}`: {s:.1f}s" for n, s in warned] or ["none between 10 s and 15 s"],
    )
    return 1 if bad else 0


def _summary(title: str, lines: list[str]) -> None:
    """Append a section to the GitHub job summary when running in Actions."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join([title, "", *lines, ""]) + "\n")


def cmd_over(args: argparse.Namespace) -> int:
    seconds, slow = load_many(args.times)
    if not seconds:
        print("no test times read: refusing to report on nothing", file=sys.stderr)
        return 2
    rows = tests_over_threshold(seconds, load_baseline()["tests"], slow)
    for nodeid, s in rows:
        print(f"{s:6.1f}s  {nodeid}")
    print(f"{len(rows)} tests over {THRESHOLD_S:g}s with no slow marker or baseline entry")
    return 1 if rows and args.enforce else 0


def cmd_budget(args: argparse.Namespace) -> int:
    seconds, _ = load_many(args.times)
    if not seconds:
        print("no test times read: refusing to report on nothing", file=sys.stderr)
        return 2
    budget = float(load_baseline()["suite_budget_s"])
    total = sum(seconds.values())
    delta = budget_delta(total, budget)
    over = total > budget * (1 + BUDGET_TOLERANCE) + 1e-9
    print(
        f"Suite serial test time: {total:.0f}s ({len(seconds)} tests) against a budget of {budget:.0f}s: "
        f"{delta:+.1%} (limit +{BUDGET_TOLERANCE:.0%}, {'enforced' if args.enforce else 'report-only'})"
    )
    if over and args.enforce:
        print("FAIL the suite is over its time budget")
        return 1
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    seconds, _ = load_many(args.times)
    if not seconds:
        print("no test times read: refusing to update from nothing", file=sys.stderr)
        return 2
    base = load_baseline()
    base["tests"] = shrink_tests(base["tests"], seconds)
    base["suite_budget_s"] = shrink_budget(float(base["suite_budget_s"]), sum(seconds.values()))
    _write(BASELINE, base)
    print(f"baseline: {len(base['tests'])} tests, budget {base['suite_budget_s']}s")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    seconds, _ = load_many(args.times)
    tests = {k: round(v, 2) for k, v in sorted(seconds.items()) if v > THRESHOLD_S}
    _write(
        BASELINE,
        {"threshold_s": THRESHOLD_S, "factor": FACTOR, "fail_s": FAIL_S, "suite_budget_s": args.budget, "tests": tests},
    )
    print(f"seeded {len(tests)} tests, budget {args.budget}s")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (
        ("check", cmd_check),
        ("over", cmd_over),
        ("budget", cmd_budget),
        ("update", cmd_update),
        ("seed", cmd_seed),
    ):
        p = sub.add_parser(name)
        p.add_argument("--times", nargs="+", type=Path)
        p.set_defaults(fn=fn)
        if name in ("budget", "over"):
            p.add_argument("--enforce", action="store_true")
        if name == "seed":
            p.add_argument("--budget", type=float, required=True)
    args = ap.parse_args(argv)
    if args.cmd in ("budget", "over", "update", "seed") and not args.times:
        ap.error(f"{args.cmd} needs --times")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
