#!/usr/bin/env python3
"""Shard counts and job timeouts from measured durations (#5919, generalizing #5882), for the `plan` job of a sharded
workflow. Stdlib only: a plan job runs before anything is installed.

    shards   the fewest shards (1..cap) whose slowest shard, `setup_s` + its work over `jobs` parallel proofs (never
             less than its longest case: one case is not split across jobs), fits the target job length x `headroom`
             (run-to-run noise: a plan that just fits the target misses it in most runs, #5882); the cap when none does. A fixed setup cost (Db2's start) is paid per shard, so it is
             part of the model: more shards are not free.
    timeout  the slowest planned shard x a margin, rounded up to whole minutes, between a floor and a ceiling: emitted by
             the plan, never typed into the YAML.
    cap      the workflow's share of the 20-job pool; `pool_cap` halves it while PR jobs queue (as the ground-truth layout does).

A case with no measured seconds takes the median of the measured ones (it only unbalances the shards), but when more
than MAX_UNMEASURED of the cases have none the plan fails loudly (`PlanError`): the durations cache is not being fed.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping

MARGIN = 1.5  # timeout = the slowest planned shard x this
MAX_UNMEASURED = 0.25  # fraction of the cases that may lack a measurement ...
GRACE_CASES = 2  # ... and this many always may (a PR adding a couple of cases is no failure)
HEADROOM = 0.8  # the share of a target a noise-sensitive plan (the Db2 shards) aims at: case seconds move 30-50% run to run (#5882)
BUSY_ABOVE = 8  # queued PR jobs; the ground-truth layout's busy threshold


class PlanError(RuntimeError):
    """The plan cannot be sized from what was measured."""


def weights(cases: Iterable[str], durations: Mapping[str, float]) -> tuple[dict[str, float], list[str]]:
    """({case: planned seconds}, the cases with no measurement). Unmeasured cases take the measured median; with none
    measured at all every case weighs 1 (an even split by count)."""
    names = sorted(set(cases))
    known = sorted(float(durations[c]) for c in names if c in durations)
    fill = statistics.median(known) if known else 1.0
    return {c: float(durations.get(c, fill)) for c in names}, [c for c in names if c not in durations]


def check_measured(unmeasured: list[str], total: int, what: str = "case") -> None:
    """Fail the plan when too many of the `total` cases have no measured seconds (past the grace allowance)."""
    if len(unmeasured) > GRACE_CASES and len(unmeasured) > MAX_UNMEASURED * total:
        shown = ", ".join(unmeasured[:8]) + (" ..." if len(unmeasured) > 8 else "")
        raise PlanError(f"{len(unmeasured)} of {total} {what}s have no measured duration ({shown}): "
                        "the durations cache is not being fed; run the nightly sweep or update the durations file")  # fmt: skip


def _shard_loads(weight: Mapping[str, float], n: int) -> list[tuple[float, float]]:
    """(work, longest case) of each of `n` shards, longest case first into the lightest shard (what the sweep does)."""
    loads = [0.0] * max(1, n)
    longest = [0.0] * max(1, n)
    for w in sorted(weight.values(), reverse=True):
        k = loads.index(min(loads))
        loads[k] += w
        longest[k] = max(longest[k], w)
    return list(zip(loads, longest, strict=True))


def slowest_shard(weight: Mapping[str, float], n: int) -> float:
    """Seconds of work in the slowest of `n` shards, longest case first into the lightest shard (what the sweep does)."""
    return max(w for w, _ in _shard_loads(weight, n))


def shard_seconds(weight: Mapping[str, float], n: int, setup_s: float, jobs: int) -> float:
    """Planned start-to-end seconds of the slowest of `n` shards: `setup_s` + its work over `jobs` parallel proofs, but
    no less than its longest case (a long pole bounds the pool however many jobs it has)."""
    return setup_s + max(max(w / max(1, jobs), c) for w, c in _shard_loads(weight, n))


def shards_for(weight: Mapping[str, float], setup_s: float, jobs: int, target_s: float, cap: int,
               headroom: float = 1.0) -> int:  # fmt: skip
    """The fewest shards in 1..cap whose slowest takes <= `target_s` x `headroom`; `cap` when none does."""
    cap = max(1, cap)
    if not weight:
        return 0
    for n in range(1, min(cap, len(weight)) + 1):
        if shard_seconds(weight, n, setup_s, jobs) <= target_s * headroom:
            return n
    return min(cap, len(weight))


def timeout_minutes(weight: Mapping[str, float], n: int, setup_s: float, jobs: int, floor: int, ceiling: int,
                    margin: float = MARGIN) -> int:  # fmt: skip
    """The job timeout for `n` shards of `weight`: the slowest shard's planned seconds x `margin`, whole minutes."""
    planned = shard_seconds(weight, n, setup_s, jobs) if weight else setup_s
    return int(max(floor, min(ceiling, math.ceil(planned * margin / 60))))


def pool_cap(cap: int, waiting: int | None, busy_above: int = BUSY_ABOVE) -> int:
    """The workflow's shard cap: halved (at least 1) while more than `busy_above` PR jobs wait; unreadable = calm."""
    if waiting is not None and waiting > busy_above:
        return max(1, cap // 2)
    return cap
