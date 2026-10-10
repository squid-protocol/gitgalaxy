"""Load-independent performance assertions for tests (#4477).

A test that asserts "this took < 1.0 s" on a wall clock measures the CI runner, not the code: three
`pytest -n auto` parts on one 4-core runner stretch a 0.09 s call past 1 s. Two rules replace it:

1. Measure CPU time of the calling thread (`time.thread_time`), not wall time. Time spent descheduled
   while other workers run is not counted, which is most of the noise on a loaded machine.
2. Take the MINIMUM of several repeats. Noise only ever adds time, so the minimum converges on the
   cost of the code itself.

`assert_scales_linearly` then proves the property the tests care about, "no quadratic or catastrophic
growth", as a RATIO between a small and a large input of the same work (linear ~k, quadratic ~k^2 for
a k-times larger input), which is independent of the machine's absolute speed. `assert_cpu_below` is
for a single fixed pathological payload: the bound must sit far above the honest cost and far below
what a super-linear regression would cost on that payload (state both in the calling test).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

# Smallest CPU time we trust as a ratio denominator: below this the clock tick, not the code, dominates.
MIN_RELIABLE_S = 0.002


def best_cpu_seconds(work: Callable[[], Any], repeats: int = 5) -> float:
    """The minimum CPU time of `repeats` runs of `work` (see the module docstring for why)."""
    best = float("inf")
    for _ in range(repeats):
        start = time.thread_time()
        work()
        best = min(best, time.thread_time() - start)
    return best


def assert_scales_linearly(
    work: Callable[[int], Any],
    small: int,
    large: int,
    *,
    max_ratio: float | None = None,
    repeats: int = 5,
    what: str = "work",
) -> float:
    """Assert `work(large)` costs about `large/small` times `work(small)`, not its square.

    The default `max_ratio` is the geometric middle between linear (k) and quadratic (k*k), so a
    quadratic regression is caught at k >= 3 with room for noise on both sides. Pick `small` so that
    `work(small)` takes a few milliseconds of CPU at least (MIN_RELIABLE_S floors the denominator).
    Returns the measured ratio."""
    k = large / small
    limit = max_ratio if max_ratio is not None else k**1.5
    t_small = max(best_cpu_seconds(lambda: work(small), repeats), MIN_RELIABLE_S)
    t_large = best_cpu_seconds(lambda: work(large), repeats)
    ratio = t_large / t_small
    assert ratio < limit, (
        f"{what}: {large} units cost {ratio:.1f}x {small} units (CPU {t_large:.4f}s vs {t_small:.4f}s); "
        f"linear is ~{k:g}x, quadratic ~{k * k:g}x, limit {limit:g}x"
    )
    return ratio


def assert_cpu_below(work: Callable[[], Any], bound_s: float, *, repeats: int = 3, what: str = "work") -> float:
    """Assert the best-of-`repeats` CPU time of `work` is under `bound_s`. Returns that time."""
    best = best_cpu_seconds(work, repeats)
    assert best < bound_s, f"{what}: best CPU time {best:.3f}s of {repeats} runs, bound {bound_s}s"
    return best
