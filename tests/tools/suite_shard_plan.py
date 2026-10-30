#!/usr/bin/env python3
"""Parts and job timeouts for the Smoke full-suite parts (#5133) and the Full Suite Gate legs (#5156), from the measured
per-test seconds in `.test_durations` through ci_shard_plan (#5919 slice 3). Stdlib only: a plan job runs before
anything is installed.

    --smoke        emits `matrix` ({"group": [1..N]}), `splits` (N) and `timeout` (minutes of a part job)
    --gate         emits `matrix` (the leg `include` list: os, python-version, part, splits, [even], timeout,
                   step_timeout) for the Full Suite Gate
    --e2e          emits `matrix` ({"group": [1..N]}), `splits` (N) and `timeout` for the Equivalence E2E shards, from
                   tests/equivalence_e2e_durations.json (#5919)

The workflow's plan job calls this module, so adding tests moves the plan, not the YAML. The committed durations are
Linux CI seconds: a Windows or macOS leg multiplies them by its SPEED. The model constants were calibrated so the
durations reproduce the proven part counts (Smoke 3; Gate ubuntu 2, macOS 2, Windows 3.11 3 and
3.12 2); a durations refresh moves the plan (#6146's halved ground-truth seconds plan Smoke 2).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_shard_plan as sp

REPO_ROOT = Path(__file__).resolve().parents[2]
DURATIONS = REPO_ROOT / ".test_durations"

# Smoke: a part installs (SMOKE_SETUP_S), then runs its tests with pytest -n auto (about JOBS at once on a 4-core runner).
SMOKE_SETUP_S = 300
JOBS = 3
SMOKE_TARGET_S = 13 * 60
SMOKE_MAX_PARTS = 6  # this workflow's share of the 20-job pool
SMOKE_TIMEOUT_FLOOR, SMOKE_TIMEOUT_CEILING = 25, 30  # minutes

# Equivalence E2E: a shard installs, loads the GnuCOBOL image and warms Maven (E2E_SETUP_S), then runs pytest -n 2.
E2E_DURATIONS = REPO_ROOT / "tests" / "equivalence_e2e_durations.json"
E2E_SETUP_S = 600
E2E_JOBS = 2
E2E_TARGET_S = 20 * 60
E2E_MAX_SHARDS = 4  # this workflow's share of the 20-job pool
E2E_TIMEOUT_FLOOR, E2E_TIMEOUT_CEILING = 30, 45  # minutes

# Gate: every leg is (os, python, SPEED over the Linux seconds). A leg's parts share GATE_MAX_PARTS of the pool each.
GATE_SETUP_S = 480  # recalibrated #5919: Windows and macOS installs take ~8 min; 240 s planned one Ubuntu part and caps below the measured legs
GATE_TARGET_S = 20 * 60
GATE_MAX_PARTS = 4
GATE_TIMEOUT_FLOOR, GATE_TIMEOUT_CEILING = 20, 35
STEP_MARGIN_MIN = 3  # step_timeout = leg timeout - 3 (#5764): expressions have no arithmetic
# #5764: the slowest minutes seen per (os, python) part on the Gate's runs of 2026-10-14..20 (windows 3.11 was 25 min as 2
# parts; as 3 parts it is an estimate: re-measure). A leg's cap keeps SEEN_HEADROOM over it whatever the durations say: a
# cache on another basis than the committed file (2026-10-26: the wall-calibrated nightly planned every leg at the floor)
# must not plan a cap below a time a leg has actually taken.
SLOWEST_SEEN_MIN = {
    ("windows-latest", "3.11"): 18,
    ("windows-latest", "3.12"): 19,
    ("macos-latest", "3.11"): 16,
    ("macos-latest", "3.12"): 17,
}
SEEN_HEADROOM = 1.3
LEGS = (
    ("ubuntu-latest", "3.11", 1.0), ("ubuntu-latest", "3.12", 1.0),
    ("windows-latest", "3.11", 1.6), ("windows-latest", "3.12", 1.3),
    ("macos-latest", "3.11", 1.3), ("macos-latest", "3.12", 1.3),
)  # fmt: skip


def load_durations(path: Path | None = None) -> dict[str, float]:
    """{test id: seconds}; an unreadable or empty file is a PlanError (the durations cache is not being fed)."""
    path = Path(path) if path else DURATIONS
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise sp.PlanError(f"cannot read the durations file {path}: {e}") from e
    if not data:
        raise sp.PlanError(f"the durations file {path} is empty: the durations cache is not being fed")
    return {k: float(v) for k, v in data.items()}


def smoke_plan(durations: dict[str, float], waiting: int | None = None) -> dict:
    """{"matrix": {"group": [1..N]}, "splits": N, "timeout": minutes} for the Smoke full-suite parts."""
    cap = sp.pool_cap(SMOKE_MAX_PARTS, waiting)
    n = max(1, sp.shards_for(durations, SMOKE_SETUP_S, JOBS, SMOKE_TARGET_S, cap))
    t = sp.timeout_minutes(durations, n, SMOKE_SETUP_S, JOBS, SMOKE_TIMEOUT_FLOOR, SMOKE_TIMEOUT_CEILING)
    return {"matrix": {"group": list(range(1, n + 1))}, "splits": n, "timeout": t}


def e2e_plan(durations: dict[str, float], waiting: int | None = None) -> dict:
    """{"matrix": {"group": [1..N]}, "splits": N, "timeout": minutes} for the Equivalence E2E shards."""
    cap = sp.pool_cap(E2E_MAX_SHARDS, waiting)
    n = max(1, sp.shards_for(durations, E2E_SETUP_S, E2E_JOBS, E2E_TARGET_S, cap))
    t = sp.timeout_minutes(durations, n, E2E_SETUP_S, E2E_JOBS, E2E_TIMEOUT_FLOOR, E2E_TIMEOUT_CEILING)
    return {"matrix": {"group": list(range(1, n + 1))}, "splits": n, "timeout": t}


def gate_plan(durations: dict[str, float], waiting: int | None = None) -> dict:
    """{"matrix": [leg, ...]}: every leg of every part, the shape the Gate's `include` has today. A Windows leg runs
    `even` (the Linux seconds mislead there, #4906), so its tests weigh the same."""
    cap = sp.pool_cap(GATE_MAX_PARTS, waiting)
    mean = sum(durations.values()) / len(durations) if durations else 0.0
    legs: list[dict] = []
    for os_name, py, speed in LEGS:
        even = os_name.startswith("windows")
        weight = {k: (mean if even else v) * speed for k, v in durations.items()}
        n = max(1, sp.shards_for(weight, GATE_SETUP_S, JOBS, GATE_TARGET_S, cap))
        t = sp.timeout_minutes(weight, n, GATE_SETUP_S, JOBS, GATE_TIMEOUT_FLOOR, GATE_TIMEOUT_CEILING)
        t = min(GATE_TIMEOUT_CEILING, max(t, math.ceil(SLOWEST_SEEN_MIN.get((os_name, py), 0) * SEEN_HEADROOM)))
        for part in range(1, n + 1):
            leg = {"os": os_name, "python-version": py, "part": part, "splits": n}
            if even:
                leg["even"] = True
            legs.append({**leg, "timeout": t, "step_timeout": t - STEP_MARGIN_MIN})
    return {"matrix": legs}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--smoke", action="store_true", help="the Smoke full-suite parts")
    what.add_argument("--gate", action="store_true", help="the Full Suite Gate legs")
    what.add_argument("--e2e", action="store_true", help="the Equivalence E2E shards")
    ap.add_argument("--durations", type=Path, help="the durations file (default: .test_durations)")
    ap.add_argument("--waiting", type=int, help="queued PR jobs (halves the part cap past ci_shard_plan.BUSY_ABOVE)")
    args = ap.parse_args(argv)
    try:
        d = load_durations(args.durations or (E2E_DURATIONS if args.e2e else None))
        p = (smoke_plan if args.smoke else e2e_plan if args.e2e else gate_plan)(d, args.waiting)
    except sp.PlanError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    print("matrix=" + json.dumps(p["matrix"]))
    if args.smoke or args.e2e:
        print(f"splits={p['splits']}")
        print(f"timeout={p['timeout']}")
        print(f"plan: {p['splits']} part(s), {p['timeout']} min", file=sys.stderr)
    else:
        print(f"plan: {len(p['matrix'])} leg(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
