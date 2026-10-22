#!/usr/bin/env python3
"""The Db2 shard model's measured inputs and checks (#5919 slice 4), on top of ci_shard_plan. Stdlib only: a plan job
runs before anything is installed.

    measured_setup_s   a runner's setup cost (job start to the first proof: checkout, Db2 start or snapshot restore) as
                       the median of recent shards' `setup_s` from det_sweep_timing's rows, instead of a typed constant.
                       Too few rows, or none usable, keep the fallback; the result is clamped so a killed job or a
                       cold cache cannot swing the plan.
    predicted_ratio    the slowest / fastest shard's planned work for N shards, the number det_sweep_timing.report
                       checks after the fact (MAX_RATIO) -- here before the shards run.
    ratio_warning      a sentence when the prediction is over `limit`, else None.

det_sweep_plan.py calls these for the Db2 shards (Det Sweep) and the Db2 parts (Evidence Refresh).
"""

from __future__ import annotations

import statistics
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_shard_plan as sp  # noqa: E402
import det_sweep_timing as timing  # noqa: E402

MIN_ROWS = 3  # shards that must have reported a setup before it replaces the fallback
CLAMP = (0.5, 2.0)  # the measured setup stays within these multiples of the fallback


def timing_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    """det_sweep_timing's row for every shard directory (one holding a timing.json) under `paths`."""
    return [timing.row(d) for d in timing._shard_dirs([Path(p) for p in paths])]


def measured_setup_s(rows: Iterable[Mapping[str, Any]], kind: str, fallback: float) -> float:
    """Median `setup_s` of the `kind` shards that proved something, clamped to CLAMP x `fallback`; `fallback` when fewer
    than MIN_ROWS shards have one (a shard killed before its sweep started has no setup)."""
    seen = [
        float(r["setup_s"]) for r in rows if r.get("kind") == kind and r.get("setup_s") is not None and r.get("proven")
    ]
    if len(seen) < MIN_ROWS:
        return float(fallback)
    return min(fallback * CLAMP[1], max(fallback * CLAMP[0], statistics.median(seen)))


def shard_loads(weight: Mapping[str, float], n: int) -> list[float]:
    """Planned seconds of work in each of `n` shards, longest case first into the lightest (what the sweep does)."""
    loads = [0.0] * max(1, n)
    for w in sorted(weight.values(), reverse=True):
        loads[loads.index(min(loads))] += w
    return loads


def predicted_ratio(weight: Mapping[str, float], n: int) -> float | None:
    """Slowest / fastest shard's planned work; None when there is nothing to compare (no cases, one shard, or an idle shard)."""
    if not weight or n < 2:
        return None
    loads = shard_loads(weight, n)
    return max(loads) / min(loads) if min(loads) > 0 else None


def ratio_warning(ratio: float | None, limit: float = timing.MAX_RATIO) -> str | None:
    if ratio is not None and ratio > limit:
        return f"the planned slowest Db2 shard is {ratio:.2f}x the fastest (over {limit}x)"
    return None


def plan_check(names: Iterable[str], durations: Mapping[str, float], n: int) -> dict[str, Any]:
    """The prediction for `n` shards of `names`: {"ratio": float|None, "warning": str|None}; unmeasured cases take the
    median, as in the plan."""
    w, _ = sp.weights(names, durations)
    ratio = predicted_ratio(w, n)
    return {"ratio": None if ratio is None else round(ratio, 3), "warning": ratio_warning(ratio)}
