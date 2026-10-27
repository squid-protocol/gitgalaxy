#!/usr/bin/env python3
"""DOOM study distributions (#5620): how each licensed port's per-function metrics compare with linuxdoom's.

    python tests/tools/doom_speedrun/distribution.py [--only a,b] [--work DIR] [--sha SHA] [--min-functions N]

Reads the scans ``doom_speedrun.py`` leaves (``<work>/scans/<sha>/<port>``, ``function_data`` joined to
``file_data``) and the port clone only to tell vendored code (dropped, #6097). For each port it takes the functions of code languages and summarises four
engine metrics plus the argument count: median and 90th percentile, the share of functions with complexity >= 10, and
a distance to linuxdoom: the 1-D Wasserstein distance between the two quantile curves (201 points), divided by
linuxdoom's standard deviation for that metric, averaged over the metrics. It is a shape comparison, not a claim that
either side is right: a port in another language shifts every metric by how the engine counts that language.
Also reports where linuxdoom's own median falls among the ports' medians.

Outputs ``<work>/results/<sha>/distribution/``: distribution.csv, distribution.json and distribution.md. Licensed
ports only (owner ruling 2026-10-19); ``assets`` projects and ports under ``--min-functions`` functions are skipped.
Port of the round-1 study script (dist.py), stdlib only.
"""

import argparse
import csv
import json
import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import callgraph_oracle  # noqa: E402
import doom_scorer  # noqa: E402
import doom_speedrun  # noqa: E402
import lineage  # noqa: E402

BASE = lineage.BASE
LICENSED = lineage.LICENSED
MIN_FUNCTIONS = 30  # below this a distribution is noise
POINTS = 201  # quantile grid of the Wasserstein distance
FIELDS = ("complexity", "loc", "func_fan_out", "token_mass", "args")
CODE_LANGUAGES = frozenset(
    "c cpp csharp java go rust objective-c kotlin dart scheme fortran javascript typescript cobol python zscript "
    "assembly crystal fsharp sql db2_sql sqlite".split()
)  # fmt: skip


def quantile(values, q):
    """Linear-interpolated quantile of a non-empty list (the usual definition, as numpy's default)."""
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def wasserstein(a, b):
    """1-D Wasserstein distance by the mean absolute gap between the two quantile curves."""
    grid = [i / (POINTS - 1) for i in range(POINTS)]
    return sum(abs(quantile(a, q) - quantile(b, q)) for q in grid) / POINTS


def _count(args):
    """``function_data.args`` is a count, but older scans stored the argument list as text."""
    if isinstance(args, str):
        return len([a for a in args.split(",") if a.strip()])
    return float(args or 0)


def load_metrics(db, vendored=None):
    """Per-function metrics of one scan, code languages only: (majority language, {field: [values]}) or None.

    ``vendored`` (a path -> bool test, see ``doom_scorer._engine_vendor_test``) drops functions of vendored code, so a
    port's distribution is its own first-party code (#6097)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select f.language, fn.complexity, fn.loc, fn.func_fan_out, fn.token_mass, fn.args, f.file_path "
            "from function_data fn join file_data f on f.id = fn.file_id"
        ).fetchall()
    finally:
        con.close()
    rows = [r for r in rows if r[0] in CODE_LANGUAGES and not (vendored and vendored(r[6]))]
    if not rows:
        return None
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    language = max(sorted(counts), key=counts.get)
    values = {f: [float(r[i + 1] or 0) for r in rows] for i, f in enumerate(FIELDS[:-1])}
    values["args"] = [_count(r[-1]) for r in rows]
    return language, values


def profile(language, values, base):
    """One port's summary row; ``base`` is linuxdoom's values (None leaves the distance out)."""
    row = {"lang": language, "n": len(values["complexity"])}
    for f in FIELDS:
        row[f + "_med"] = statistics.median(values[f])
        row[f + "_p90"] = quantile(values[f], 0.9)
        if base is not None:
            row[f + "_w1"] = wasserstein(values[f], base[f]) / (statistics.pstdev(base[f]) or 1)
    row["cx10"] = 100 * sum(c >= 10 for c in values["complexity"]) / row["n"]
    if base is not None:
        row["dist"] = statistics.fmean(row[f + "_w1"] for f in FIELDS)
    return row


def base_percentiles(summary):
    """Where linuxdoom's median of each metric falls among all the ports' medians (ties count half)."""
    out = {}
    for f in FIELDS:
        meds = [s[f + "_med"] for s in summary.values()]
        b = summary[BASE][f + "_med"]
        pct = 100 * sum(v < b for v in meds) / len(meds) + 50 * sum(v == b for v in meds) / len(meds)
        out[f] = dict(
            metric=f, linuxdoom=b, population_median=statistics.median(meds),
            q1=quantile(meds, 0.25), q3=quantile(meds, 0.75), linuxdoom_percentile=round(pct),
        )  # fmt: skip
    return out


def render(summary, percentiles, sha):
    ports = sorted(summary, key=lambda p: summary[p]["dist"])
    lines = [
        f"# DOOM per-function distributions vs linuxdoom: engine `{sha}`", "",
        f"{len(ports)} licensed code ports. `dist` is the mean normalised Wasserstein distance to linuxdoom over "
        f"{', '.join(FIELDS)}; the other columns are the port's own median / 90th percentile.", "",
        "| port | lang | functions | complexity med | complexity p90 | % complexity >= 10 | LOC med | fan-out med | args med | dist |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for p in ports:
        s = summary[p]
        lines.append(
            f"| {p} | {s['lang']} | {s['n']} | {s['complexity_med']:.0f} | {s['complexity_p90']:.0f} | "
            f"{s['cx10']:.1f} | {s['loc_med']:.0f} | {s['func_fan_out_med']:.0f} | {s['args_med']:.0f} | {s['dist']:.2f} |"
        )
    lines += ["", "| metric | linuxdoom median | population median | IQR of port medians | linuxdoom percentile |",
              "|---|---|---|---|---|"]  # fmt: skip
    for f, r in percentiles.items():
        lines.append(
            f"| {f} | {r['linuxdoom']:.1f} | {r['population_median']:.1f} | "
            f"{r['q1']:.1f} - {r['q3']:.1f} | {r['linuxdoom_percentile']} |"
        )
    return "\n".join(lines) + "\n"


def run(rows, work, sha, min_functions=MIN_FUNCTIONS):
    """Distributions of every port in ``rows`` (manifest rows, BASE among them). Returns (summary by port, skipped)."""
    loaded, skipped = {}, []
    for row in rows:
        name = row["name"]
        if row.get("class") == "assets":
            continue
        db = callgraph_oracle.find_db(work / "scans" / sha / name)
        repo = work / "repos" / name
        got = load_metrics(db, doom_scorer._engine_vendor_test(repo)) if db and repo.is_dir() else None
        if got is None or len(got[1]["complexity"]) < min_functions:
            skipped.append(name)
            continue
        loaded[name] = got
    if BASE not in loaded:
        raise SystemExit(f"distribution: no usable scan of {BASE} under {work} at {sha} (run doom_speedrun.py scan)")
    base = loaded[BASE][1]
    return {n: profile(lang, vals, base) for n, (lang, vals) in loaded.items()}, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help=f"comma-separated ports ({BASE} is always added; default: every licensed port)")
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--sha", help="engine SHA of the scans to read (default: this checkout's HEAD)")
    ap.add_argument("--manifest", type=Path, help="alternate manifest CSV")
    ap.add_argument("--min-functions", type=int, default=MIN_FUNCTIONS, help="skip a port with fewer code functions")
    args = ap.parse_args(argv)
    only = [n for n in (args.only or "").split(",") if n]
    if bad := sorted(set(only) - LICENSED):
        raise SystemExit(f"distribution: not in the licensed port set: {', '.join(bad)}")
    wanted = set(only or LICENSED) | {BASE}
    rows = [r for r in doom_speedrun.read_manifest(args.manifest, None) if r["name"] in wanted & LICENSED]
    work, sha = args.work.resolve(), args.sha or doom_speedrun.engine_sha()
    summary, skipped = run(rows, work, sha, args.min_functions)
    for name in skipped:
        print(f"distribution: no scan, or under {args.min_functions} code functions, for {name} at {sha}")
    dest = work / "results" / sha / "distribution"
    dest.mkdir(parents=True, exist_ok=True)
    percentiles = base_percentiles(summary)
    (dest / "distribution.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (dest / "distribution.md").write_text(render(summary, percentiles, sha))
    table = [dict(port=p, **s) for p, s in sorted(summary.items(), key=lambda kv: kv[1]["dist"])]
    with open(dest / "distribution.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]), lineterminator="\n")
        w.writeheader()
        w.writerows({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()} for r in table)
    for r in table:
        print(f"{r['port']:18}{r['lang']:12}{r['n']:7} functions  dist {r['dist']:.2f}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
