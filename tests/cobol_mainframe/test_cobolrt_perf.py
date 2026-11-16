"""A/B parity test for cobolrt fast paths (#4717, #8423).

Verifies that the fast-path numeric codecs and charset tables produce byte-identical
results to the BigInteger/String reference implementation across 5,000 fuzzed fields,
without asserting on wall-clock timing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobolrt_bench


def test_cobolrt_codec_fast_path_parity():
    res = cobolrt_bench.run(mode="parity", fuzz=5000)
    if res.returncode != 0:
        raise AssertionError(res.stderr or res.stdout)
    if "PARITY OK: 5000 fuzzed cases + charset tables" not in res.stdout:
        raise AssertionError(res.stdout)
