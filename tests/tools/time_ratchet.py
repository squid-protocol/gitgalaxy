#!/usr/bin/env python3
"""Test-time ratchet: the suite must not get slower over time (#5166 part B).

    python tests/tools/time_ratchet.py check  [--times FILE]            # per-test gate (every PR)
    python tests/tools/time_ratchet.py budget --times FILE... [--enforce]  # whole-suite budget
    python tests/tools/time_ratchet.py update --times FILE...           # shrink-only baseline + budget
    python tests/tools/time_ratchet.py seed   --times FILE... --budget SECONDS   # one time

A times file is either pytest-split's `.test_durations` ({nodeid: seconds}) or the file `tests/conftest.py` writes when
GITGALAXY_TEST_TIMES is set ({"seconds": {nodeid: s}, "slow": {nodeid: reason}}). `tests/test_time_baseline.json`
holds the tests over THRESHOLD_S with their recorded seconds and the suite budget.

Per test: over 10 s fails unless it has a `slow` marker (with a reason) or is baselined; a baselined test fails over 2x its
recorded seconds. Suite: total over the budget by more than 10% fails when --enforce (nightly main); a PR only reports.
Updates only lower: an entry drops to the new seconds, one at or under the threshold is removed, nothing is added or raised.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "tests" / "test_time_baseline.json"
DURATIONS = REPO / ".test_durations"
THRESHOLD_S = 10.0
FACTOR = 2.0
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


def check_tests(seconds: dict[str, float], baseline: dict[str, float], slow: dict[str, str] | None = None) -> list[str]:
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
        elif s > THRESHOLD_S and nodeid not in slow:
            out.append(
                f"{nodeid}: {s:.1f}s is over {THRESHOLD_S:g}s and has no @pytest.mark.slow(reason=...) "
                f"and no entry in tests/test_time_baseline.json"
            )
    return out


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
    bad = check_tests(seconds, load_baseline()["tests"], slow)
    for line in bad:
        print("FAIL " + line)
    print(f"{len(seconds)} tests checked, {len(bad)} over the per-test limit")
    return 1 if bad else 0


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
    _write(BASELINE, {"threshold_s": THRESHOLD_S, "factor": FACTOR, "suite_budget_s": args.budget, "tests": tests})
    print(f"seeded {len(tests)} tests, budget {args.budget}s")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("budget", cmd_budget), ("update", cmd_update), ("seed", cmd_seed)):
        p = sub.add_parser(name)
        p.add_argument("--times", nargs="+", type=Path)
        p.set_defaults(fn=fn)
        if name == "budget":
            p.add_argument("--enforce", action="store_true")
        if name == "seed":
            p.add_argument("--budget", type=float, required=True)
    args = ap.parse_args(argv)
    if args.cmd in ("budget", "update", "seed") and not args.times:
        ap.error(f"{args.cmd} needs --times")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
