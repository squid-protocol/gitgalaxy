"""galaxyscope extraction pool sizing (#4902)."""

import os

from gitgalaxy.galaxyscope import resolve_max_workers


def test_explicit_max_workers_wins():
    assert resolve_max_workers({"GALAXYSCOPE_MAX_WORKERS": "2", "GG_JOB_CORES": "6"}) == 2


def test_job_cores_sizes_pool_when_unset():
    assert resolve_max_workers({"GG_JOB_CORES": "6"}) == 6


def test_invalid_values_fall_through_to_cpu_count():
    default = max(1, (os.cpu_count() or 4) - 1)
    assert resolve_max_workers({}) == default
    assert resolve_max_workers({"GG_JOB_CORES": "0", "GALAXYSCOPE_MAX_WORKERS": "x"}) == default
