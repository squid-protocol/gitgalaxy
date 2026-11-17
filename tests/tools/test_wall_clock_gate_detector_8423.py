# ruff: noqa: S101
"""#8423: the wall-clock gate's detector, on synthetic text (a regex regression must not pass silently)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_no_raw_wall_clock_timing_8423 import wall_clock_calls


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("import time\na = time.perf_counter()\nb = time.perf_counter()\n", 2),
        ("import time\na = time.time()\n", 1),
        ("import time\na = time.monotonic_ns()\nb = time.time_ns()\n", 2),
        ("import time as t\nx = t.time()\ny = t.monotonic()\n", 2),
        ("from time import perf_counter\na = perf_counter()\nb = perf_counter()\n", 2),
        ("from time import monotonic as m, sleep\na = m()\nb = m()\nsleep(1)\n", 2),
        ("import time\na = time.thread_time()\nb = time.process_time()\ntime.sleep(1)\n", 0),
        ("from time import sleep\nsleep(1)\n", 0),
        ("import datetime\nx = datetime.datetime.now()\n", 0),
        ("def perf_counter():\n    pass\nperf_counter()\n", 0),
    ],
)
def test_wall_clock_calls(text, expected):
    assert wall_clock_calls(text) == expected
