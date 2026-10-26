#!/usr/bin/env python3
"""DOOM study, per-subsystem complexity distributions (#6097, slice 1; family of #5620's ``distribution.py``).

    python tests/tools/doom_speedrun/subsystem_distribution.py [--only a,b] [--work DIR] [--sha SHA] [--min-functions N]

Splits each licensed port's code functions by linuxdoom subsystem (``lineage.subsystem``: file directory and file-name
prefix, ``r_`` renderer, ``p_`` playsim, ...) and summarises ONE metric family, cyclomatic complexity: function count,
median, 90th percentile and the share of functions with complexity >= 10, plus the ratio of the port's subsystem median
to linuxdoom's median in the same subsystem. Reads only the scans ``doom_speedrun.py`` leaves.

A port that renamed its files (``Renderer.cs``, ``game/play.rs``) puts those functions under ``other``: the table
reports ``other`` like any subsystem, and ``other_pct`` per port says how much of the port the file-prefix split could
not place. Ports under ``--min-functions`` code functions are skipped; a subsystem under ``--min-subsystem`` functions
keeps its count but no ratio.

Outputs ``<work>/results/<sha>/distribution/``: subsystem_distribution.csv and subsystem_distribution.md. Licensed ports
only (owner ruling 2026-10-19); ``assets`` projects skipped.
"""

import argparse
import csv
import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import callgraph_oracle  # noqa: E402
import distribution  # noqa: E402
import doom_speedrun  # noqa: E402
import lineage  # noqa: E402

BASE = lineage.BASE
LICENSED = lineage.LICENSED
MIN_SUBSYSTEM = 5  # below this a subsystem's median is not compared


def load_by_subsystem(db):
    """Complexity of every code function of one scan, grouped: {subsystem: [complexity]}; None when it has none."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select d.file_path, d.language, f.complexity from function_data f join file_data d on d.id = f.file_id"
        ).fetchall()
    finally:
        con.close()
    out = {}
    for path, language, complexity in rows:
        if language in distribution.CODE_LANGUAGES:
            out.setdefault(lineage.subsystem((path or "").replace("\\", "/")), []).append(float(complexity or 0))
    return out or None


def summarise(by_sub, base, min_subsystem=MIN_SUBSYSTEM):
    """Rows (one per subsystem the port has) and the port's ``other`` share; ``base`` is linuxdoom's by_sub."""
    total = sum(len(v) for v in by_sub.values())
    rows = []
    for sub, vals in sorted(by_sub.items()):
        row = dict(
            subsystem=sub, n=len(vals), share=100 * len(vals) / total, complexity_med=statistics.median(vals),
            complexity_p90=distribution.quantile(vals, 0.9), cx10=100 * sum(c >= 10 for c in vals) / len(vals),
        )  # fmt: skip
        ref = base.get(sub, [])
        if base is not by_sub and len(vals) >= min_subsystem and len(ref) >= min_subsystem:
            med = statistics.median(ref)
            row["med_vs_linuxdoom"] = row["complexity_med"] / med if med else None
        rows.append(row)
    return rows, 100 * len(by_sub.get("other", [])) / total


def run(rows, work, sha, min_functions=distribution.MIN_FUNCTIONS, min_subsystem=MIN_SUBSYSTEM):
    """{port: (subsystem rows, other_pct)} for every usable port in manifest ``rows`` (BASE among them), and the skipped."""
    loaded, skipped = {}, []
    for row in rows:
        name = row["name"]
        if row.get("class") == "assets":
            continue
        db = callgraph_oracle.find_db(work / "scans" / sha / name)
        got = load_by_subsystem(db) if db else None
        if got is None or sum(len(v) for v in got.values()) < min_functions:
            skipped.append(name)
            continue
        loaded[name] = got
    if BASE not in loaded:
        raise SystemExit(f"subsystem_distribution: no usable scan of {BASE} under {work} at {sha}")
    return {n: summarise(v, loaded[BASE], min_subsystem) for n, v in loaded.items()}, skipped


def render(result, sha):
    lines = [
        f"# DOOM per-subsystem complexity vs linuxdoom: engine `{sha}`", "",
        "Subsystem by file-name prefix (`lineage.subsystem`). `vs linuxdoom` is the port's subsystem median divided by "
        "linuxdoom's in the same subsystem (blank under the minimum count). `other` holds files the prefix split "
        "cannot place, so a port that renamed its files is mostly `other`.", "",
        "| port | other % | subsystem | functions | complexity med | complexity p90 | % complexity >= 10 | vs linuxdoom |",
        "|---|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for port, (rows, other) in sorted(result.items()):
        for r in rows:
            ratio = r.get("med_vs_linuxdoom")
            lines.append(
                f"| {port} | {other:.0f} | {r['subsystem']} | {r['n']} | {r['complexity_med']:.0f} | "
                f"{r['complexity_p90']:.0f} | {r['cx10']:.1f} | {'' if ratio is None else f'{ratio:.2f}'} |"
            )
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help=f"comma-separated ports ({BASE} is always added; default: every licensed port)")
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--sha", help="engine SHA of the scans to read (default: this checkout's HEAD)")
    ap.add_argument("--manifest", type=Path, help="alternate manifest CSV")
    ap.add_argument("--min-functions", type=int, default=distribution.MIN_FUNCTIONS, help="skip a port below this")
    ap.add_argument("--min-subsystem", type=int, default=MIN_SUBSYSTEM, help="no ratio for a subsystem below this")
    args = ap.parse_args(argv)
    only = [n for n in (args.only or "").split(",") if n]
    if bad := sorted(set(only) - LICENSED):
        raise SystemExit(f"subsystem_distribution: not in the licensed port set: {', '.join(bad)}")
    wanted = set(only or LICENSED) | {BASE}
    manifest = [r for r in doom_speedrun.read_manifest(args.manifest, None) if r["name"] in wanted & LICENSED]
    work, sha = args.work.resolve(), args.sha or doom_speedrun.engine_sha()
    result, skipped = run(manifest, work, sha, args.min_functions, args.min_subsystem)
    for name in skipped:
        print(f"subsystem_distribution: no scan, or under {args.min_functions} code functions, for {name} at {sha}")
    dest = work / "results" / sha / "distribution"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "subsystem_distribution.md").write_text(render(result, sha))
    fields = [
        "port",
        "other_pct",
        "subsystem",
        "n",
        "share",
        "complexity_med",
        "complexity_p90",
        "cx10",
        "med_vs_linuxdoom",
    ]
    with open(dest / "subsystem_distribution.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for port, (rows, other) in sorted(result.items()):
            for r in rows:
                rec = dict(port=port, other_pct=other, **r)
                w.writerow({k: round(v, 3) if isinstance(v, float) else v for k, v in rec.items()})
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
