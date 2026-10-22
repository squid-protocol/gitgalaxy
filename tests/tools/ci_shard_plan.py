#!/usr/bin/env python3
"""Shard counts and job timeouts from measured durations (#5919, generalizing #5882), for the `plan` job of a sharded
workflow. Stdlib only: a plan job runs before anything is installed.

    shards   the fewest shards (1..cap) whose slowest shard, `setup_s` + its work over `jobs` parallel proofs, fits the
             target job length; the cap when none does. A fixed setup cost (Db2's start) is paid per shard, so it is
             part of the model: more shards are not free.
    timeout  the slowest planned shard x a margin, rounded up to whole minutes, between a floor and a ceiling: emitted by
             the plan, never typed into the YAML.
    cap      the workflow's share of the 20-job pool; `pool_cap` halves it while PR jobs queue (as ci_layout does).

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
BUSY_ABOVE = 8  # queued PR jobs; the same signal as ci_layout.BUSY_ABOVE


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


def slowest_shard(weight: Mapping[str, float], n: int) -> float:
    """Seconds of work in the slowest of `n` shards, longest case first into the lightest shard (what the sweep does)."""
    loads = [0.0] * max(1, n)
    for w in sorted(weight.values(), reverse=True):
        loads[loads.index(min(loads))] += w
    return max(loads)


def shards_for(weight: Mapping[str, float], setup_s: float, jobs: int, target_s: float, cap: int) -> int:
    """The fewest shards in 1..cap whose slowest takes setup + work / jobs <= target_s; `cap` when none does."""
    cap = max(1, cap)
    if not weight:
        return 0
    for n in range(1, min(cap, len(weight)) + 1):
        if setup_s + slowest_shard(weight, n) / max(1, jobs) <= target_s:
            return n
    return min(cap, len(weight))


def timeout_minutes(weight: Mapping[str, float], n: int, setup_s: float, jobs: int, floor: int, ceiling: int,
                    margin: float = MARGIN) -> int:  # fmt: skip
    """The job timeout for `n` shards of `weight`: the slowest shard's planned seconds x `margin`, whole minutes."""
    planned = setup_s + (slowest_shard(weight, n) / max(1, jobs) if weight else 0.0)
    return int(max(floor, min(ceiling, math.ceil(planned * margin / 60))))


def pool_cap(cap: int, waiting: int | None, busy_above: int = BUSY_ABOVE) -> int:
    """The workflow's shard cap: halved (at least 1) while more than `busy_above` PR jobs wait; unreadable = calm."""
    if waiting is not None and waiting > busy_above:
        return max(1, cap // 2)
    return cap
