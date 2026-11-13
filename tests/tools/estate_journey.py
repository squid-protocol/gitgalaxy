#!/usr/bin/env python3
"""Render the estate journey page: each estate's first contact, then the climb, measured in merged PRs.

    python tests/tools/estate_journey.py           # write docs/language_status/estate_journey.md and its charts
    python tests/tools/estate_journey.py --check   # exit 1 when the committed page or a chart is stale

The data is docs/language_status/estate_journey/journey.json (hand-kept, every number with a source). The cycle it
records is the one docs/language_status/estate_trial_methodology.md locks in: scan an estate, post the evidence,
reflect and close the error classes it exposed, then try the next estate. Development estates are measured at L2
(executed equivalent); trials on estates that are not burned are measured at L1 (translated whole) and accounted,
because rule 2 forbids cases on them. The two measures are never drawn on one axis.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "docs" / "language_status" / "estate_journey" / "journey.json"
PAGE = REPO / "docs" / "language_status" / "estate_journey.md"
CHARTS = REPO / "docs" / "language_status" / "estate_journey"
COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")  # trial.py's
OTHER = "#9a9a95"
MEASURE = {
    "L2": "programs at L2 or better (executed equivalent)",
    "L1": "programs translated whole (L1)",
}
XLAB = {
    "L2": "merged PRs to main since first contact (all work; the fleet worked several estates at once)",
    "L1": "merged PRs on the trial since first contact",
}


def _esc(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def load(path: Path = DATA) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def problems(data: dict[str, Any]) -> list[str]:
    """Every series point and headline number needs a source; a series uses one measure only."""
    out = []
    for e in data["estates"]:
        if e["measure"] not in MEASURE:
            out.append(f"{e['key']}: measure {e['measure']!r} is not L1 or L2")
        fc = e.get("first_contact") or {}
        if fc and not fc.get("source"):
            out.append(f"{e['key']}: first_contact has no source")
        for p in e.get("series", []):
            if not p.get("source"):
                out.append(f"{e['key']}: series point {p.get('date')} has no source")
            if p.get("value") is not None and p.get("total") and p["value"] > p["total"]:
                out.append(f"{e['key']}: series point {p.get('date')} value > total")
    return out


def _axes(p: list[str], x0: int, y0: int, w: int, h: int, xmax: int, ylab: str, xlab: str) -> None:
    for k in range(5):
        y = y0 + h - h * k / 4
        p.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" stroke="#eeede9"/>')
        p.append(f'<text x="{x0 - 6}" y="{y + 3:.1f}" class="a" text-anchor="end">{25 * k}%</text>')
    for k in range(5):
        x = x0 + w * k / 4
        p.append(f'<text x="{x:.1f}" y="{y0 + h + 14}" class="a" text-anchor="middle">{xmax * k // 4:,}</text>')
    p.append(f'<text x="{x0 + w / 2}" y="{y0 + h + 30}" class="a" text-anchor="middle">{_esc(xlab)}</text>')
    p.append(f'<text x="12" y="{y0 + h / 2}" class="a" transform="rotate(-90 12 {y0 + h / 2})" '
             f'text-anchor="middle">{_esc(ylab)}</text>')  # fmt: skip


def _line(p: list[str], pts: list[tuple[float, float]], color: str, dash: str = "") -> None:
    if not pts:
        return
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    p.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"{extra}/>')
    for x, y in pts if len(pts) <= 8 else pts[:1] + pts[-1:]:  # markers: every point, or the two ends of a long run
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="#fcfcfb" stroke-width="2"/>')


def _without_blips(run: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Drop a one-reading dip: a point below both neighbours when the neighbours agree (a report regenerated or marked
    stale for one run, restored by the next). A drop that lasts more than one reading stays: levels do go down."""
    keep = [run[i] for i in range(len(run))
            if not (0 < i < len(run) - 1 and run[i - 1][1] == run[i + 1][1] and run[i][1] < run[i - 1][1])]  # fmt: skip
    return keep


def _nice(n: int) -> int:
    """The smallest round axis end at or above n whose quarters are round too (4, 8, 20, 40, 100, 200, 400, 1000, ...)."""
    for mag in (1, 10, 100, 1000, 10000):
        for base in (1, 2, 5):
            if base * 4 * mag >= n:
                return base * 4 * mag
    return n


def chart(series: list[tuple[str, str, list[dict[str, Any]], str]], title: str, sub: str, ylab: str, xlab: str) -> str:
    """One chart: share of the program basis against merged PRs since first contact. series = (label, color, points,
    key): key "value" is the estate's measure (solid); "accounted" or "whole" is a second line of the same estate
    (dashed)."""
    width, height, x0, y0, w, h = 760, 360, 64, 92, 660, 200
    xmax = _nice(max([int(pt.get("prs") or 0) for _, _, pts, _ in series for pt in pts] + [1]))
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
         'font-family="system-ui, -apple-system, Segoe UI, sans-serif" role="img" '
         f'aria-label="{_esc(title)}">',
         "<style>.t{font-size:15px;font-weight:600;fill:#0b0b0b}.s{font-size:11px;fill:#52514e}"
         ".a{font-size:10px;fill:#706f6a}.l{font-size:11px;fill:#0b0b0b}</style>",
         f'<rect width="{width}" height="{height}" fill="#fcfcfb"/>',
         f'<text x="16" y="26" class="t">{_esc(title)}</text>',
         f'<text x="16" y="44" class="s">{_esc(sub)}</text>']  # fmt: skip
    _axes(p, x0, y0, w, h, xmax, ylab, xlab)
    lx = 16
    for label, color, pts, key in series:
        last: dict[int, dict[str, Any]] = {}  # one reading per PR count: the latest (several reports can share one)
        for pt in pts:
            if pt.get(key) is not None and pt.get("total"):
                last[int(pt.get("prs") or 0)] = pt
        run = [(x, pt[key] / pt["total"]) for x, pt in sorted(last.items())]
        run = _without_blips(run)
        xy = [(x0 + w * x / xmax, y0 + h - h * v) for x, v in run]
        _line(p, xy, color, "5 4" if key != "value" else "")
        dash = ' stroke-dasharray="5 4"' if key != "value" else ""
        p.append(f'<line x1="{lx}" y1="66" x2="{lx + 18}" y2="66" stroke="{color}" stroke-width="2"{dash}/>')
        p.append(f'<text x="{lx + 24}" y="70" class="l">{_esc(label)}</text>')
        lx += 40 + 6.5 * len(label)
    p.append("</svg>")
    return "\n".join(p) + "\n"


def estate_chart(e: dict[str, Any], color: str) -> str:
    pts = e.get("series", [])
    s = [(MEASURE[e["measure"]].split(" (")[0], color, pts, "value")]
    if any(pt.get("accounted") is not None for pt in pts):
        s.append(("accounted (whole + named source defects)", color, pts, "accounted"))
    if e["measure"] == "L2" and any(pt.get("whole") is not None for pt in pts):
        s.append(("translated whole (L1)", color, pts, "whole"))
    sub = f"{e['program_basis']} programs · solid: {MEASURE[e['measure']]}"
    return chart(s, e["name"], sub, "share of programs", XLAB[e["measure"]])


def overlay(estates: list[dict[str, Any]], measure: str, colors: dict[str, str]) -> str:
    s = [(e["name"], colors[e["key"]], e.get("series", []), "value") for e in estates if e["measure"] == measure]
    title = (
        "Development estates: the climb to equivalence" if measure == "L2" else "Trials: first contact, then the climb"
    )
    return chart(s, title, f"Share of each estate's programs: {MEASURE[measure]}", "share of programs", XLAB[measure])


def _num(fc: dict[str, Any] | None, key: str = "value") -> str:
    if not fc or fc.get(key) is None or not fc.get("total"):
        return "not recorded"
    return f"{fc[key]} / {fc['total']} ({fc[key] / fc['total']:.0%})"


def _refs(refs: list[str]) -> str:
    return (" (" + ", ".join(refs) + ")") if refs else ""


def render_page(data: dict[str, Any], charts: dict[str, str]) -> str:
    out = [
        "---",
        'description: "How GitGalaxy meets an estate: the first translation attempt, then the climb, in merged PRs.'
        ' Generated by tests/tools/estate_journey.py; do not edit."',
        "---",
        "# Estate journey: first contact, then the climb",
        "",
        "*Generated by `tests/tools/estate_journey.py` from `docs/language_status/estate_journey/journey.json`; do not"
        " edit. Method: [estate trial methodology](estate_trial_methodology.md).*",
        "",
        data["intro"],
        "",
        "**How to read the numbers.** Development estates are measured at **L2, executed equivalent**: a case runs the"
        " program and the Java port equals the COBOL oracle on every scenario. Trials on estates we have not developed"
        " on are measured at **L1, translated whole**, plus **accounted** (whole, or every gap a named source defect"
        " with an IBM citation). Rule 2 forbids writing cases for them, so they can't reach L2. The two measures are"
        " never drawn on one axis. The oracle is GnuCOBOL with our CICS stub, not z/OS ([levels](definition_of_done.md)).",
        "",
    ]
    for ch in data["chapters"]:
        out += [f"## {ch['title']}", ""]
        if ch.get("text"):
            out += [ch["text"], ""]
        if ch.get("overlay"):
            out += [f"![{_esc(ch['title'])}](estate_journey/{charts[ch['overlay']]})", ""]
        for key in ch.get("estates", []):
            e = next(x for x in data["estates"] if x["key"] == key)
            out += [f"### {e['name']}", ""]
            if e.get("summary"):
                out += [e["summary"], ""]
            fc = e.get("first_contact")
            rows = [("First contact", f"{_num(fc)} {MEASURE['L1'].split(' (')[0] if fc else ''}".strip()
                     + (f", {fc['date']}" if fc and fc.get("date") else ""))]  # fmt: skip
            for m in e.get("milestones", []):
                bits = [m["label"], _num(m)]
                if m.get("prs") is not None:
                    bits.append(f"{m['prs']} " + ("PRs naming the estate" if e["measure"] == "L2" else "trial PRs"))
                if m.get("days") is not None:
                    bits.append(f"{m['days']} days")
                rows.append((m.get("when", m.get("date", "")), " · ".join(str(b) for b in bits)))
            out += ["| | |", "|---|---|", *[f"| {a} | {b} |" for a, b in rows], ""]
            if key in charts:
                out += [f"![{_esc(e['name'])}](estate_journey/{charts[key]})", ""]
            if e.get("learned"):
                out += ["**What we learned**", ""]
                out += [f"- {x['text']}{_refs(x.get('refs', []))}" for x in e["learned"]]
                out += [""]
    out += ["## Journal", "", "Dated notes: what we assumed, what turned out to be true, and corrections.", ""]
    for j in data.get("journal", []):
        out.append(f"- **{j['date']}**: {j['text']}{_refs(j.get('refs', []))}")
    out += ["", "## Caveats", ""] + [f"- {c}" for c in data.get("caveats", [])] + [""]
    return "\n".join(out)


def build(data: dict[str, Any]) -> dict[str, str]:
    """{relative path under docs/language_status: content} for the page and every chart."""
    keys = [e["key"] for e in data["estates"]]
    colors = {k: (COLORS[i] if i < len(COLORS) else OTHER) for i, k in enumerate(keys)}
    files, charts = {}, {}
    for e in data["estates"]:
        if e.get("series"):
            name = f"{e['key']}.svg"
            files[f"estate_journey/{name}"] = estate_chart(e, colors[e["key"]])
            charts[e["key"]] = name
    for m in ("L2", "L1"):
        if any(e["measure"] == m and e.get("series") for e in data["estates"]):
            name = f"overlay_{m.lower()}.svg"
            files[f"estate_journey/{name}"] = overlay(data["estates"], m, colors)
            charts[f"overlay_{m.lower()}"] = name
    files["estate_journey.md"] = render_page(data, charts)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when the committed page or a chart is stale")
    args = ap.parse_args(argv)
    data = load()
    bad = problems(data)
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    base = REPO / "docs" / "language_status"
    stale = []
    for rel, text in build(data).items():
        f = base / rel
        if args.check:
            if not f.is_file() or f.read_text(encoding="utf-8") != text:
                stale.append(rel)
        else:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
    if stale:
        print("stale (run tests/tools/estate_journey.py): " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
