#!/usr/bin/env python3
"""Merge pytest-split duration files, one per part of the full suite, into one `.test_durations` (#4847).

    python tests/tools/merge_test_durations.py OUT PART [PART ...]

Each part runs `pytest --store-durations --clean-durations`, so its file holds the seconds of the tests that part ran
(pytest-split's format: {nodeid: seconds}). The parts are disjoint slices of one collection, so the merge is the union;
a nodeid in two parts with different seconds is refused, since it means the parts did not split one suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def merge(parts: list[dict[str, float]]) -> dict[str, float]:
    """The union of the parts' {nodeid: seconds}; a nodeid recorded twice must agree."""
    merged: dict[str, float] = {}
    for part in parts:
        for nodeid, seconds in part.items():
            if nodeid in merged and merged[nodeid] != seconds:
                raise ValueError(
                    f"{nodeid}: recorded in two parts with different seconds ({merged[nodeid]}, {seconds})"
                )
            merged[nodeid] = seconds
    return dict(sorted(merged.items()))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    out, *inputs = (Path(a) for a in argv)
    parts = [json.loads(p.read_text(encoding="utf-8")) for p in inputs]
    bad = [p for p, d in zip(inputs, parts, strict=True) if not isinstance(d, dict)]
    if bad:
        raise SystemExit(f"not a pytest-split durations file (a JSON object): {bad[0]}")
    merged = merge(parts)
    out.write_text(json.dumps(merged, sort_keys=True, indent=4) + "\n", encoding="utf-8")
    print(f"merged {len(merged)} test durations from {len(inputs)} parts into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
