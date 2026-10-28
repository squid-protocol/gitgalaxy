#!/usr/bin/env python3
"""DOOM study, per-subsystem plots (#6097; reads the CSV of ``subsystem_distribution.py``).

    python tests/tools/doom_speedrun/subsystem_plot.py [--metric complexity] [--work DIR] [--sha SHA] [--csv FILE]

One SVG heatmap per metric: a row per port, a column per linuxdoom subsystem, each cell the port's subsystem median over
linuxdoom's median in the same subsystem (``<metric>_vs_linuxdoom``), on a log scale so 2x and 0.5x are the same
distance from 1. Blue is below linuxdoom, red above, white equal. A cell with no ratio (a subsystem under
``--min-subsystem`` functions on either side, or absent from the port) is grey and empty, never zero. The right-hand
column is the port's ``other`` share (functions no subsystem could place), so a port whose renderer sits under
``other`` is visible as such. Standard library only (no matplotlib): the SVG is written by hand.

Outputs ``<work>/results/<sha>/distribution/subsystem_<metric>.svg``.
"""

import argparse
import csv
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import distribution  # noqa: E402
import doom_speedrun  # noqa: E402

CELL_W, CELL_H, LEFT, TOP = 64, 22, 150, 90
SPAN = math.log(4)  # the colour saturates at 4x or 0.25x
GREY = "#e5e5e5"


def read_ratios(path, metric):
    """{port: {subsystem: ratio or None}} and {port: other_pct} from a ``subsystem_distribution.csv``."""
    col = f"{metric}_vs_linuxdoom"
    ratios, other = {}, {}
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        if col not in (reader.fieldnames or []):
            raise SystemExit(f"subsystem_plot: {path} has no column {col}")
        for r in reader:
            val = r[col]
            ratios.setdefault(r["port"], {})[r["subsystem"]] = float(val) if val else None
            other[r["port"]] = float(r["other_pct"])
    return ratios, other


def colour(ratio):
    """Fill of one cell: grey for no ratio, else white -> red (above 1) or blue (below 1) by log distance."""
    if ratio is None:
        return GREY
    if ratio <= 0:
        return "#2166ac"
    t = max(-1.0, min(1.0, math.log(ratio) / SPAN))
    fade = round(255 * (1 - abs(t)))
    return f"rgb(255,{fade},{fade})" if t > 0 else f"rgb({fade},{fade},255)"


def render(ratios, other, metric):
    """The heatmap as SVG text. Subsystems are columns in name order, ``other`` last; ports are rows in name order."""
    subs = sorted({s for row in ratios.values() for s in row} - {"other"}) + ["other"]
    ports = sorted(ratios)
    width = LEFT + CELL_W * (len(subs) + 1) + 20
    height = TOP + CELL_H * len(ports) + 40
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif" font-size="11">',
        f'<text x="8" y="18" font-size="14">{escape(metric)}: port median over linuxdoom median, per subsystem</text>',
        f'<text x="8" y="34">log scale, red above linuxdoom, blue below, grey = no ratio (under the minimum, or absent)</text>',
    ]  # fmt: skip
    for j, sub in enumerate(subs + ["other %"]):
        x = LEFT + CELL_W * j + CELL_W / 2
        out.append(f'<text x="{x}" y="{TOP - 6}" text-anchor="start" transform="rotate(-45 {x} {TOP - 6})">{escape(sub)}</text>')
    for i, port in enumerate(ports):
        y = TOP + CELL_H * i
        out.append(f'<text x="{LEFT - 6}" y="{y + 15}" text-anchor="end">{escape(port)}</text>')
        for j, sub in enumerate(subs):
            ratio = ratios[port].get(sub)
            x = LEFT + CELL_W * j
            label = "" if ratio is None else f"{ratio:.2f}"
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" fill="{colour(ratio)}" stroke="#fff">'
                f"<title>{escape(port)} / {escape(sub)}: {label or 'no ratio'}</title></rect>"
                f'<text x="{x + CELL_W / 2}" y="{y + 15}" text-anchor="middle">{label}</text>'
            )
        x = LEFT + CELL_W * len(subs)
        out.append(f'<text x="{x + CELL_W / 2}" y="{y + 15}" text-anchor="middle">{other[port]:.0f}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--metric", default="complexity", choices=distribution.FIELDS, help="metric to plot")
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--sha", help="engine SHA of the results to read (default: this checkout's HEAD)")
    ap.add_argument("--csv", type=Path, help="a subsystem_distribution.csv (default: the one under --work / --sha)")
    args = ap.parse_args(argv)
    dest = args.work.resolve() / "results" / (args.sha or doom_speedrun.engine_sha()) / "distribution"
    src = args.csv or dest / "subsystem_distribution.csv"
    if not src.is_file():
        raise SystemExit(f"subsystem_plot: {src} not found; run subsystem_distribution.py first")
    ratios, other = read_ratios(src, args.metric)
    if not ratios:
        raise SystemExit(f"subsystem_plot: {src} has no rows")
    dest = src.parent if args.csv else dest
    (dest / f"subsystem_{args.metric}.svg").write_text(render(ratios, other, args.metric))
    print(f"wrote {dest / f'subsystem_{args.metric}.svg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
