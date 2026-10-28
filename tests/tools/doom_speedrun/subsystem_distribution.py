#!/usr/bin/env python3
"""DOOM study, per-subsystem complexity distributions (#6097, slices 1-2; family of #5620's ``distribution.py``).

    python tests/tools/doom_speedrun/subsystem_distribution.py [--only a,b] [--work DIR] [--sha SHA] [--min-functions N]

Splits each licensed port's code functions by linuxdoom subsystem (``lineage.subsystem``: file directory and file-name
prefix, ``r_`` renderer, ``p_`` playsim, ...) and summarises every metric of ``distribution.FIELDS`` (complexity, loc,
fan-out, token mass, args): function count, median, 90th percentile (complexity also the share >= 10) and the ratio of
the port's subsystem median to linuxdoom's in the same subsystem. Vendored code is dropped as in ``distribution.py``.
Reads the scans ``doom_speedrun.py`` leaves and the port clone (only to tell vendored code).

A function is placed by lineage (slice 3): the subsystem of its linuxdoom namesake (``P_UseSpecialLine``, or
``UseSpecialLine`` / ``use_special_line`` with the prefix dropped; ``lineage.name_index``), so a port that renamed its
files (``Renderer.cs``, ``game/play.rs``) keeps its renderer functions in ``renderer``. A function with no namesake falls
back to its file-name prefix (``--assign prefix`` uses that alone). ``other`` is what neither can place, and ``other_pct``
per port says how much that is. Ports under ``--min-functions`` code functions are skipped; a subsystem under ``--min-subsystem`` functions
keeps its count but no ratio.

Outputs ``<work>/results/<sha>/distribution/``: subsystem_distribution.csv and .md. Licensed ports
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
import doom_scorer  # noqa: E402
import doom_speedrun  # noqa: E402
import lineage  # noqa: E402

BASE = lineage.BASE
LICENSED = lineage.LICENSED
FIELDS = distribution.FIELDS
MIN_SUBSYSTEM = 5  # below this a subsystem's median is not compared


def load_by_subsystem(db, vendored=None, index=None):
    """Metrics of every code function of one scan, grouped: {subsystem: {field: [values]}}; None when it has none.

    ``vendored`` (see ``doom_scorer._engine_vendor_test``) drops vendored code, as ``distribution.load_metrics`` does.
    ``index`` (``lineage.name_index``) places a function by the linuxdoom function it descends from; without it a
    function is placed by its file name alone."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select fn.func_name, f.file_path, f.language, fn.complexity, fn.loc, fn.func_fan_out, fn.token_mass, fn.args "
            "from function_data fn join file_data f on f.id = fn.file_id"
        ).fetchall()
    finally:
        con.close()
    out = {}
    for name, path, language, *vals in rows:
        path = (path or "").replace("\\", "/")
        if language not in distribution.CODE_LANGUAGES or (vendored and vendored(path)):
            continue
        vals[-1] = distribution._count(vals[-1])
        bucket = out.setdefault(
            lineage.assign_subsystem(name, path, index) if index else lineage.subsystem(path), {f: [] for f in FIELDS}
        )
        for f, v in zip(FIELDS, vals):
            bucket[f].append(float(v or 0))
    return out or None


def size(by_sub):
    return sum(len(v["complexity"]) for v in by_sub.values())


def summarise(by_sub, base, min_subsystem=MIN_SUBSYSTEM):
    """Rows (one per subsystem the port has) and the port's ``other`` share; ``base`` is linuxdoom's by_sub.

    Each metric gives ``<f>_med``, ``<f>_p90`` and, against linuxdoom's same subsystem, ``<f>_vs_linuxdoom``."""
    total = size(by_sub)
    rows = []
    for sub, vals in sorted(by_sub.items()):
        n = len(vals["complexity"])
        row = dict(subsystem=sub, n=n, share=100 * n / total)
        ref = base.get(sub)
        comparable = (
            base is not by_sub and n >= min_subsystem and ref is not None and len(ref["complexity"]) >= min_subsystem
        )
        for f in FIELDS:
            row[f + "_med"] = statistics.median(vals[f])
            row[f + "_p90"] = distribution.quantile(vals[f], 0.9)
            if comparable:
                med = statistics.median(ref[f])
                row[f + "_vs_linuxdoom"] = row[f + "_med"] / med if med else None
        row["cx10"] = 100 * sum(c >= 10 for c in vals["complexity"]) / n
        rows.append(row)
    other = by_sub.get("other")
    return rows, 100 * len(other["complexity"]) / total if other else 0.0


def base_index(db, vendored=None):
    """``lineage.name_index`` of linuxdoom's own scan (first-party code functions)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select fn.func_name, f.file_path, f.language from function_data fn join file_data f on f.id = fn.file_id"
        ).fetchall()
    finally:
        con.close()
    paths = [(n or "", (p or "").replace("\\", "/"), lang) for n, p, lang in rows]
    return lineage.name_index(
        [(n, p) for n, p, lang in paths if lang in distribution.CODE_LANGUAGES and not (vendored and vendored(p))]
    )


def run(rows, work, sha, min_functions=distribution.MIN_FUNCTIONS, min_subsystem=MIN_SUBSYSTEM, assign="lineage"):
    """{port: (subsystem rows, other_pct)} for every usable port in manifest ``rows`` (BASE among them), and the skipped.

    ``assign`` is ``lineage`` (a function goes to the subsystem of its linuxdoom namesake) or ``prefix`` (file name only)."""
    loaded, skipped, index = {}, [], None
    if assign == "lineage":
        for row in rows:
            if row["name"] == BASE:
                db, repo = callgraph_oracle.find_db(work / "scans" / sha / BASE), work / "repos" / BASE
                if db and repo.is_dir():
                    index = base_index(db, doom_scorer._engine_vendor_test(repo))
    for row in rows:
        name = row["name"]
        if row.get("class") == "assets":
            continue
        db = callgraph_oracle.find_db(work / "scans" / sha / name)
        repo = work / "repos" / name
        got = None
        if db and repo.is_dir():
            got = load_by_subsystem(db, doom_scorer._engine_vendor_test(repo), index if name != BASE else None)
        if got is None or size(got) < min_functions:
            skipped.append(name)
            continue
        loaded[name] = got
    if BASE not in loaded:
        raise SystemExit(f"subsystem_distribution: no usable scan of {BASE} under {work} at {sha}")
    return {n: summarise(v, loaded[BASE], min_subsystem) for n, v in loaded.items()}, skipped


def render(result, sha, assign="lineage"):
    placed = (
        "Subsystem of the linuxdoom function a function descends from (same name, prefix optional), else by file-name "
        "prefix (`lineage.assign_subsystem`)"
        if assign == "lineage"
        else "Subsystem by file-name prefix (`lineage.subsystem`)"
    )
    lines = [
        f"# DOOM per-subsystem metric distributions vs linuxdoom: engine `{sha}`", "",
        f"{placed}; vendored code dropped. `vs linuxdoom` is the port's "
        "subsystem median divided by linuxdoom's in the same subsystem (blank under the minimum count). `other` holds "
        "functions neither placement can place.", "",
    ]  # fmt: skip
    for f in FIELDS:
        extra = " | % complexity >= 10" if f == "complexity" else ""
        lines += [
            f"## {f}", "",
            f"| port | other % | subsystem | functions | {f} med | {f} p90{extra} | vs linuxdoom |",
            "|---|---|---|---|---|---|---|" + ("---|" if extra else ""),
        ]  # fmt: skip
        for port, (rows, other) in sorted(result.items()):
            for r in rows:
                ratio = r.get(f + "_vs_linuxdoom")
                cx = f" {r['cx10']:.1f} |" if extra else ""
                lines.append(
                    f"| {port} | {other:.0f} | {r['subsystem']} | {r['n']} | {r[f + '_med']:.0f} | "
                    f"{r[f + '_p90']:.0f} |{cx} {'' if ratio is None else f'{ratio:.2f}'} |"
                )
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help=f"comma-separated ports ({BASE} is always added; default: every licensed port)")
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--sha", help="engine SHA of the scans to read (default: this checkout's HEAD)")
    ap.add_argument("--manifest", type=Path, help="alternate manifest CSV")
    ap.add_argument("--min-functions", type=int, default=distribution.MIN_FUNCTIONS, help="skip a port below this")
    ap.add_argument(
        "--assign", choices=("lineage", "prefix"), default="lineage", help="how a function gets its subsystem"
    )
    ap.add_argument("--min-subsystem", type=int, default=MIN_SUBSYSTEM, help="no ratio for a subsystem below this")
    args = ap.parse_args(argv)
    only = [n for n in (args.only or "").split(",") if n]
    if bad := sorted(set(only) - LICENSED):
        raise SystemExit(f"subsystem_distribution: not in the licensed port set: {', '.join(bad)}")
    wanted = set(only or LICENSED) | {BASE}
    manifest = [r for r in doom_speedrun.read_manifest(args.manifest, None) if r["name"] in wanted & LICENSED]
    work, sha = args.work.resolve(), args.sha or doom_speedrun.engine_sha()
    result, skipped = run(manifest, work, sha, args.min_functions, args.min_subsystem, args.assign)
    for name in skipped:
        print(f"subsystem_distribution: no scan, or under {args.min_functions} code functions, for {name} at {sha}")
    dest = work / "results" / sha / "distribution"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "subsystem_distribution.md").write_text(render(result, sha, args.assign))
    fields = ["port", "other_pct", "subsystem", "n", "share", "cx10"] + [
        f"{f}_{k}" for f in FIELDS for k in ("med", "p90", "vs_linuxdoom")
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
