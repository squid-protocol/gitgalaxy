"""Shared doubling-ratio linearity check (#8097): robust to a noisy CI runner, still fails a real quadratic."""

import time


def best_of(fn, arg, runs: int = 5, timer=time.perf_counter) -> float:
    best = float("inf")
    for _ in range(runs):
        start = timer()
        fn(arg)
        best = min(best, timer() - start)
    return best


def assert_linear(fn, small_arg, large_arg, attempts: int = 3, floor: float = 0.5, timer=time.perf_counter) -> None:
    """`large_arg` is ~2x `small_arg`. Passes if any of `attempts` measurements keeps large < max(3.2 * small, floor).

    One noisy sample (a stalled runner during the large run) must not fail the suite (#7792, #8097); a genuinely
    quadratic function is ~4x on every attempt and so still fails.
    `timer` is injectable so the helper itself can be tested on a deterministic clock (#8132).
    """
    seen = []
    for _ in range(attempts):
        small, large = best_of(fn, small_arg, timer=timer), best_of(fn, large_arg, timer=timer)
        if large < max(small * 3.2, floor):
            return
        seen.append((round(small, 4), round(large, 4)))
    raise AssertionError(f"not linear: (small, large) seconds per attempt {seen}")
