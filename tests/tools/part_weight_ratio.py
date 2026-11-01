#!/usr/bin/env python3
"""Per full-suite part, actual seconds over the balance weights it was split by (#5162 "durations weight").

    python tests/tools/part_weight_ratio.py RUN_ID [RUN_ID ...]
    python tests/tools/part_weight_ratio.py --dir DIR [DIR ...]

Each full-suite part uploads `times-part-N.json` (what its tests took) and `restored-durations-part-N.json` (the weights
`least_duration` balanced by) in its `test-times-part-N` artifact. The ratio per part is the sum of actual seconds over
the sum of the weights, for the test ids present in both. Read it across 5+ push runs (docs/ci.md): a ratio that is stable
per part means the weights mis-rank that part's composition (retune the calibration); one that flips between parts from
run to run is runner noise (leave the weights). Needs the `gh` CLI for run ids; `--dir` reads already downloaded
artifacts (a directory holding the two files per part). Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_test_durations import seconds_of  # noqa: E402 -- one reader for both file shapes

REPO = "squid-protocol/gitgalaxy"
_TIMES = re.compile(r"^times-part-(\d+)\.json$")


def ratio(actual: dict[str, float], weights: dict[str, float]) -> tuple[float, int, int] | None:
    """(actual / weight over the shared ids, shared count, ids with no weight), None when nothing is shared."""
    shared = [k for k in actual if k in weights]
    weight = sum(weights[k] for k in shared)
    if not shared or not weight > 0:
        return None
    return sum(actual[k] for k in shared) / weight, len(shared), len(actual) - len(shared)


def read_parts(directory: Path) -> dict[int, tuple[float, int, int]]:
    """{part: ratio} for every part in `directory` that has both files and a shared id."""
    found: dict[int, tuple[float, int, int]] = {}
    for times in sorted(directory.rglob("times-part-*.json")):
        m = _TIMES.match(times.name)
        weights = times.with_name(f"restored-durations-part-{m.group(1)}.json") if m else None
        if not m or weights is None or not weights.is_file():
            continue
        got = ratio(
            seconds_of(json.loads(times.read_text(encoding="utf-8"))),  # type: ignore[arg-type]
            seconds_of(json.loads(weights.read_text(encoding="utf-8"))),  # type: ignore[arg-type]
        )
        if got:
            found[int(m.group(1))] = got
    return found


def summarize(runs: dict[str, dict[int, tuple[float, int, int]]]) -> list[str]:
    """Table lines: one row per run, then per part the mean ratio and its spread across runs."""
    lines = ["run          part  actual/weight  scored  unweighted"]
    per_part: dict[int, list[float]] = {}
    for run, parts in runs.items():
        for part in sorted(parts):
            r, scored, missing = parts[part]
            per_part.setdefault(part, []).append(r)
            lines.append(f"{run:<12} {part:>4}  {r:13.2f}  {scored:6d}  {missing:10d}")
    for part in sorted(per_part):
        rs = per_part[part]
        spread = statistics.pstdev(rs) if len(rs) > 1 else 0.0
        lines.append(f"part {part}: mean {statistics.mean(rs):.2f}, stdev {spread:.2f} over {len(rs)} runs")
    if not per_part:
        lines.append("no run had a part with both times and restored durations")
    return lines


def _download(run: str, into: Path) -> None:
    subprocess.run(  # noqa: S603, S607
        ["gh", "run", "download", run, "-R", REPO, "-p", "test-times-part-*", "-D", str(into)],
        check=True,
        capture_output=True,
        text=True,
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="*", help="smoke-test.yml run ids")
    ap.add_argument("--dir", nargs="*", type=Path, default=[], help="downloaded artifact directories instead of run ids")
    args = ap.parse_args(argv)
    if not args.runs and not args.dir:
        ap.error("give run ids or --dir")
    runs = {d.name: read_parts(d) for d in args.dir}
    for run in args.runs:
        with tempfile.TemporaryDirectory() as tmp:
            _download(run, Path(tmp))
            runs[run] = read_parts(Path(tmp))
    print("\n".join(summarize(runs)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
