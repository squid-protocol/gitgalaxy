#!/usr/bin/env python3
"""#5882: where a det-sweep shard's time goes, planned against measured, so a shard drifting toward its timeout shows
before it is killed.

    python tests/tools/det_sweep_timing.py record --out DIR/timing.json --kind db2 --shard I/N \\
        --mark job_start=FILE [--mark NAME=FILE ...] [--prewarm FILE]
    python tests/tools/det_sweep_timing.py report SHARD_DIR [SHARD_DIR ...] [--json OUT] [--github-summary PATH]
    python tests/tools/det_sweep_timing.py merge-durations SRC DST

`record` (each shard, `if: always()`): the epoch second of each phase the workflow wrote to a file (`date +%s > FILE`;
a missing file -- a phase never reached, a job killed by its timeout -- is null) and the Db2 prewarm's own marks
(--prewarm: {"start": epoch, "container": s, "databases": {name: s}}), as timing.json beside the shard's shard.json
(proof_sweep.py --shard: its cases, planned seconds, unmeasured cases) and sweep.json (each case's measured seconds).

`report` (the `det` job): one row per shard -- cases, unmeasured, planned seconds, setup, Db2 ready, sweep, job --
then per kind the slowest / fastest sweep and job, with a ::warning when a job passes BUDGET_SECONDS or the slowest
sweep is more than MAX_RATIO times the fastest (#5882's acceptance: every db2 shard under 15 min, within 1.3x).
--json writes the rows for later runs to be read back (gh run download, then summarise a week of them).

`merge-durations` (det-sweep's plan): the "det" entries of SRC (the Db2 cases' seconds Evidence Refresh's Db2 merge
recorded, #5882) over DST's. Stdlib only: the plan job runs before anything is installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BUDGET_SECONDS = 15 * 60  # a shard's job, start to sweep end (#5882 acceptance)
MAX_RATIO = 1.3  # slowest shard's sweep over the fastest's


def _epoch(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return None


def record(kind: str, shard: str, marks: dict[str, Path], prewarm: Path | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"format": "det-sweep-timing/1", "kind": kind, "shard": shard,
                           "marks": {name: _epoch(p) for name, p in marks.items()}}  # fmt: skip
    if prewarm is not None:
        try:
            out["db2"] = json.loads(prewarm.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out["db2"] = None
    return out


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _shard_dirs(paths: list[Path]) -> list[Path]:
    """Every directory holding a timing.json under `paths` (download-artifact puts a lone artifact straight into its
    path, several each into a subdirectory: #5008)."""
    found = []
    for p in paths:
        found += sorted({f.parent for f in p.rglob("timing.json")} if p.is_dir() else set())
    return found


def _since(marks: dict[str, int | None], a: str, b: str) -> int | None:
    x, y = marks.get(a), marks.get(b)
    return y - x if x is not None and y is not None else None


def row(d: Path) -> dict[str, Any]:
    """One shard: its timing.json, shard.json and sweep.json read together."""
    timing = _load(d / "timing.json") or {}
    plan = _load(d / "shard.json") or {}
    sweep = (_load(d / "sweep.json") or {}).get("det", {})
    marks = timing.get("marks") or {}
    db2 = timing.get("db2") or {}
    db2_ready = None
    if db2.get("start") is not None and marks.get("job_start") is not None and db2.get("databases"):
        db2_ready = round(db2["start"] + max(db2["databases"].values()) - marks["job_start"])
    return {
        "kind": timing.get("kind", "?"),
        "shard": timing.get("shard") or plan.get("shard", "?"),
        "cases": len(plan.get("cases") or sweep),
        "proven": len(sweep),
        "unmeasured": len(plan.get("unmeasured") or []),
        "planned_s": plan.get("planned_seconds"),
        "case_s": round(sum(r.get("seconds") or 0 for r in sweep.values())),
        "setup_s": _since(marks, "job_start", "sweep_start"),
        "db2_container_s": round(db2["container"]) if db2.get("container") is not None else None,
        "db2_ready_s": db2_ready,
        "db2_databases": db2.get("databases"),
        "db2_snapshot": db2.get("snapshot"),  # #5882: True restored from the cache, False tried and fell back, None no try
        "sweep_s": _since(marks, "sweep_start", "sweep_end"),
        "job_s": _since(marks, "job_start", "sweep_end"),
        "slowest": sorted(((round(r.get("seconds") or 0), c) for c, r in sweep.items()), reverse=True)[:3],
        "phases": phase_totals(sweep),
    }


def phase_totals(sweep: dict[str, dict]) -> dict[str, float]:
    """#5882: each harness phase's seconds summed over a shard's cases (the rows' `phases`, equivalence_common.phase)."""
    out: dict[str, float] = {}
    for r in sweep.values():
        for name, v in (r.get("phases") or {}).items():
            out[name] = round(out.get(name, 0) + (v.get("seconds") or 0), 1)
    return out


def _fmt(v: Any) -> str:
    return "-" if v is None else str(v)


def report(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(markdown lines, warnings)."""
    lines = ["| kind | shard | cases | proven | unmeasured | planned s | sum of case s | setup s | Db2 ready s | sweep s | job s | slowest cases |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    warnings = []
    for r in sorted(rows, key=lambda r: (r["kind"], r["shard"])):
        slow = ", ".join(f"{c} {s}s" for s, c in r["slowest"])
        lines.append(f"| {r['kind']} | {r['shard']} | {r['cases']} | {r['proven']} | {r['unmeasured']} | "
                     f"{_fmt(r['planned_s'])} | {r['case_s']} | {_fmt(r['setup_s'])} | {_fmt(r['db2_ready_s'])} | "
                     f"{_fmt(r['sweep_s'])} | {_fmt(r['job_s'])} | {slow} |")  # fmt: skip
        if r["sweep_s"] is None and r["cases"]:
            warnings.append(f"{r['kind']} {r['shard']}: no sweep end recorded (killed by its timeout, or failed before)")
        elif r["job_s"] is not None and r["job_s"] > BUDGET_SECONDS:
            warnings.append(f"{r['kind']} {r['shard']}: job took {r['job_s'] / 60:.1f} min, over the {BUDGET_SECONDS // 60} min budget")
    lines.append("")
    for kind in sorted({r["kind"] for r in rows}):
        mine = [r for r in rows if r["kind"] == kind]
        totals: dict[str, float] = {}
        for r in mine:
            for name, v in (r.get("phases") or {}).items():
                totals[name] = totals.get(name, 0) + v
        case_s = sum(r["case_s"] for r in mine) or 1
        if totals:  # phases nest (java_cics holds java_maven): each is a share of the case seconds, not a partition
            lines.append(f"- **{kind}** case seconds by phase: " + ", ".join(
                f"{n} {v:.0f} s ({100 * v / case_s:.0f}%)" for n, v in sorted(totals.items(), key=lambda kv: -kv[1])))  # fmt: skip
        done = [r for r in mine if r["sweep_s"]]
        if len(done) < 2:
            continue
        slow, fast = max(done, key=lambda r: r["sweep_s"]), min(done, key=lambda r: r["sweep_s"])
        ratio = slow["sweep_s"] / fast["sweep_s"]
        unmeasured = sum(r["unmeasured"] for r in mine)
        lines.append(f"- **{kind}**: sweep {fast['sweep_s']}-{slow['sweep_s']} s ({ratio:.2f}x, slowest {slow['shard']}); "
                     f"job up to {_fmt(max((r['job_s'] for r in done if r['job_s'] is not None), default=None))} s; "
                     f"{unmeasured} case(s) had no recorded duration")  # fmt: skip
        if ratio > MAX_RATIO:
            warnings.append(f"{kind}: slowest sweep {slow['shard']} {slow['sweep_s']} s is {ratio:.2f}x the fastest "
                            f"{fast['shard']} {fast['sweep_s']} s (over {MAX_RATIO}x; {unmeasured} unmeasured)")  # fmt: skip
    return lines, warnings


def merge_durations(src: Path, dst: Path) -> int:
    """SRC's "det" seconds over DST's (DST keeps its other entries); how many were merged. A missing SRC merges none."""
    add = (_load(src) or {}).get("det") or {}
    if not add:
        return 0
    data = _load(dst) or {"format": "det-sweep-durations/1"}
    data.setdefault("det", {}).update(add)
    data["det"] = dict(sorted(data["det"].items()))
    dst.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return len(add)


def _mark(text: str) -> tuple[str, Path]:
    name, sep, path = text.partition("=")
    if not sep or not name:
        raise argparse.ArgumentTypeError(f"--mark wants NAME=FILE, not {text!r}")
    return name, Path(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--out", type=Path, required=True)
    rec.add_argument("--kind", required=True)
    rec.add_argument("--shard", required=True)
    rec.add_argument("--mark", type=_mark, action="append", default=[])
    rec.add_argument("--prewarm", type=Path)
    rep = sub.add_parser("report")
    rep.add_argument("dirs", type=Path, nargs="+")
    rep.add_argument("--json", type=Path)
    rep.add_argument("--github-summary", type=Path)
    mrg = sub.add_parser("merge-durations")
    mrg.add_argument("src", type=Path)
    mrg.add_argument("dst", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "record":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record(args.kind, args.shard, dict(args.mark), args.prewarm), indent=1) + "\n",
                            encoding="utf-8")  # fmt: skip
        return 0
    if args.cmd == "merge-durations":
        print(f"durations: {merge_durations(args.src, args.dst)} entr(ies) merged from {args.src}")
        return 0
    rows = [row(d) for d in _shard_dirs(args.dirs)]
    lines, warnings = report(rows)
    text = "\n".join(["## Det sweep shard timings (#5882)", "", *lines])
    print(text)
    for w in warnings:
        print(f"::warning title=Det sweep timing::{w}")
    if args.github_summary:
        with args.github_summary.open("a", encoding="utf-8") as fh:
            fh.write(text + "\n" + "".join(f"- warning: {w}\n" for w in warnings))
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
