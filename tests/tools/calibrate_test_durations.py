#!/usr/bin/env python3
"""Scale one part's pytest-split durations so they sum to the part's measured pytest wall seconds (#5133).

    python tests/tools/calibrate_test_durations.py IN OUT --wall SECONDS

`pytest --store-durations` under `-n auto` records each test's own seconds on a contended runner, and the contention differs
by part, so equal recorded sums are not equal wall times. The nightly parts scale their file to the wall of the pytest step
(`merge_test_durations.py` then merges the parts as before); relative weights inside a part are kept. The wall includes
collection and worker start-up, a per-part constant folded into the weights. Stdlib only: the workflow runs it as is.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def seconds_of(data: object) -> object:
    """The {nodeid: seconds} of either file shape: pytest-split's own, or what GITGALAXY_TEST_TIMES writes (#5166)."""
    if isinstance(data, dict) and isinstance(data.get("seconds"), dict):
        return data["seconds"]
    return data


def calibrate(durations: dict[str, float], wall: float) -> dict[str, float]:
    """`durations` scaled so they sum to `wall`; refuses a wall that is not positive or a part with no recorded seconds."""
    if not wall > 0:
        raise ValueError(f"wall seconds must be positive, got {wall}")
    total = sum(durations.values())
    if not total > 0:
        raise ValueError("no recorded seconds to scale")
    factor = wall / total
    return {nodeid: round(seconds * factor, 6) for nodeid, seconds in durations.items()}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--wall", type=float, required=True, help="the part's measured pytest wall seconds")
    args = ap.parse_args(argv)
    data = seconds_of(json.loads(args.src.read_text(encoding="utf-8")))
    if not isinstance(data, dict):
        raise SystemExit(f"not a pytest-split durations file (a JSON object): {args.src}")
    scaled = calibrate(data, args.wall)
    args.out.write_text(json.dumps(scaled, sort_keys=True, indent=4) + "\n", encoding="utf-8")
    print(
        f"calibrated {len(scaled)} test durations from {sum(data.values()):.0f} s to {args.wall:.0f} s wall into {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
