#!/usr/bin/env python3
"""Render the estate journey page: each estate's first contact, then the climb, measured in merged PRs.

    python tests/tools/estate_journey.py           # write docs/language_status/estate_journey.md and its charts
    python tests/tools/estate_journey.py --check   # exit 1 when the committed page or a chart is stale

Recording a blind draw (estate_trial_methodology.md, "Recording a draw"): `add-draw` at T0, `point` after each
re-measure (L1; L2 only once an owner amendment allows cases), `l2-from-prs` to rebuild an L2 series from the merged
case PRs. Each refuses an unsourced number, a PR count that goes back, or a draw already recorded; the progress slide
reads the result with no code change.

The data is docs/language_status/estate_journey/journey.json (hand-kept, every number with a source). The cycle it
records is the one docs/language_status/estate_trial_methodology.md locks in: scan an estate, post the evidence,
reflect and close the error classes it exposed, then try the next estate. Development estates are measured at L2
(executed equivalent); trials on estates that are not burned are measured at L1 (translated whole) and accounted,
because rule 2 forbids cases on them. The two measures are never drawn on one axis.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "docs" / "language_status" / "estate_journey" / "journey.json"
PAGE = REPO / "docs" / "language_status" / "estate_journey.md"
CHARTS = REPO / "docs" / "language_status" / "estate_journey"
CANDIDATES = REPO / "docs" / "language_status" / "estate4_candidates.json"
TRIALS = REPO / "tests" / "cobol_mainframe" / "trials.json"
REPO_SLUG = "squid-protocol/gitgalaxy"
REMAIN = re.compile(r"\b(\d+) draws (?:remain|left)\b")
CASE_TITLE = re.compile(r"\bcases?\b", re.I)
COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")  # trial.py's
OTHER = "#9a9a95"
MEASURE = {
    "L2": "programs at L2 or better (executed equivalent)",
    "L1": "programs translated whole (L1)",
}
XLAB = {
    "L2": "merged PRs to main since first contact (all work; the fleet worked several estates at once)",
    "L1": "merged PRs on the trial since first contact",
    "L2-trial": "merged PRs on the trial since first contact (the same count as its L1 chart)",
}


def _esc(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def load(path: Path = DATA) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def planned_draws() -> int:
    """The pre-registered blind draws: the committed candidate list's length (names are never read here)."""
    return len(json.loads(CANDIDATES.read_text(encoding="utf-8")).get("candidates", [])) if CANDIDATES.is_file() else 0


def _points(e: dict[str, Any], field: str, out: list[str]) -> None:
    last = -1
    for p in e.get(field, []):
        if not p.get("source"):
            out.append(f"{e['key']}: {field} point {p.get('date')} has no source")
        if p.get("value") is not None and p.get("total") and p["value"] > p["total"]:
            out.append(f"{e['key']}: {field} point {p.get('date')} value > total")
        prs = int(p.get("prs") or 0)
        if prs < last:
            out.append(f"{e['key']}: {field} point {p.get('date')} goes back in PRs ({prs} after {last})")
        last = prs


def problems(data: dict[str, Any], planned: int | None = None) -> list[str]:
    """Every series point and headline number needs a source; a series uses one measure only; PR counts never go back.
    A blind draw names its draw number and estate; an L2 series on a blind draw needs the owner amendment that allowed
    cases (`l2_measure_note`). With `planned`, every "N draws remain / left" in the prose matches the draws made."""
    out: list[str] = []
    draws: list[int] = []
    for e in data["estates"]:
        if e["measure"] not in MEASURE:
            out.append(f"{e['key']}: measure {e['measure']!r} is not L1 or L2")
        fc = e.get("first_contact") or {}
        if fc and not fc.get("source"):
            out.append(f"{e['key']}: first_contact has no source")
        _points(e, "series", out)
        _points(e, "l2_series", out)
        if e.get("kind") == "blind":
            if not isinstance(e.get("draw"), int) or not e.get("estate"):
                out.append(f"{e['key']}: a blind draw needs its draw number and estate")
            else:
                draws.append(e["draw"])
            if e.get("l2_series") and not e.get("l2_measure_note"):
                out.append(f"{e['key']}: an L2 series on a blind draw needs l2_measure_note (the owner amendment)")
    if len(draws) != len(set(draws)):
        out.append(f"blind draw numbers repeat: {sorted(draws)}")
    if planned:
        if any(d > planned for d in draws):
            out.append(f"a draw number is above the {planned} pre-registered draws")
        left = planned - len(draws)
        texts = [data.get("intro", "")] + [c.get("title", "") + " " + c.get("text", "") for c in data["chapters"]]
        for n in {int(m) for t in texts for m in REMAIN.findall(t)}:
            if n != left:
                out.append(f"the prose says {n} draws remain; {len(draws)} of {planned} made leaves {left}")
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


def l2_chart(e: dict[str, Any], color: str) -> str:
    """A blind draw's L2 climb, its own chart: cases came after first contact (an owner amendment), so it never shares
    the L1 chart's axis."""
    sub = f"{e['program_basis']} programs · {MEASURE['L2']} · cases written after first contact"
    return chart([("L2 or better", color, e["l2_series"], "value")], f"{e['name']}: L2", sub, "share of programs",
                 XLAB["L2-trial"])  # fmt: skip


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
            if f"{key}-l2" in charts:
                out += [e["l2_measure_note"], "", f"![{_esc(e['name'])}: L2](estate_journey/{charts[f'{key}-l2']})", ""]
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
        if e.get("l2_series"):
            name = f"{e['key']}-l2.svg"
            files[f"estate_journey/{name}"] = l2_chart(e, colors[e["key"]])
            charts[f"{e['key']}-l2"] = name
    for m in ("L2", "L1"):
        if any(e["measure"] == m and e.get("series") for e in data["estates"]):
            name = f"overlay_{m.lower()}.svg"
            files[f"estate_journey/{name}"] = overlay(data["estates"], m, colors)
            charts[f"overlay_{m.lower()}"] = name
    files["estate_journey.md"] = render_page(data, charts)
    return files


# ---- recording a draw (the intake workflow: add-draw at T0, point after each re-measure, l2-from-prs) ---------------


def _set_remaining(text: str, left: int) -> str:
    return REMAIN.sub(lambda m: m.group(0).replace(m.group(1), str(left), 1), text)


def add_draw(data: dict[str, Any], *, draw: int, repo: str, issue: int, estate: str, basis: int, date: str, whole: int,
             source: str, planned: int, accounted: int | None = None, trial: str | None = None,
             trial_issues: list[int] | None = None) -> dict[str, Any]:  # fmt: skip
    """Record a blind draw's first contact: a new estate entry, its own chapter (before the "Next" chapter), and the
    "N draws remain" prose recounted. First contact is the T0 number and is never revised upward."""
    key = f"blind-trial-{draw}"
    if any(e.get("draw") == draw or e["key"] == key for e in data["estates"]):
        raise ValueError(f"draw {draw} is already recorded")
    if not 1 <= draw <= planned:
        raise ValueError(f"draw {draw} is outside the {planned} pre-registered draws")
    if not source:
        raise ValueError("first contact needs a source (the T0 comment on the trial issue)")
    point = {"date": date, "prs": 0, "value": whole, "accounted": accounted, "total": basis, "source": source}
    data["estates"].append({
        "key": key, "name": f"Blind estate {draw} of {planned}: {repo} (#{issue})", "kind": "blind", "draw": draw,
        "estate": estate, "trial": trial, "trial_issues": sorted({issue, *(trial_issues or [])}), "measure": "L1",
        "program_basis": basis, "first_contact": {"date": date, "value": whole, "total": basis, "source": source},
        "milestones": [], "series": [point], "learned": [],
    })  # fmt: skip
    chapter = {"title": f"Blind estate {draw} of {planned} (drawn {date[:10]})", "estates": [key],
               "text": "Drawn at T0 from the pre-registered candidates, after the preflight passed and main was frozen."}
    nxt = next((i for i, c in enumerate(data["chapters"]) if c.get("title", "").startswith("Next")), None)
    data["chapters"].insert(len(data["chapters"]) if nxt is None else nxt, chapter)
    left = planned - sum(1 for e in data["estates"] if e.get("kind") == "blind")
    data["intro"] = _set_remaining(data["intro"], left)
    for c in data["chapters"]:
        c["title"] = _set_remaining(c.get("title", ""), left)
        if c.get("text"):
            c["text"] = _set_remaining(c["text"], left)
    return data


def add_point(data: dict[str, Any], *, key: str, measure: str, prs: int, value: int, total: int, source: str,
              date: str, accounted: int | None = None, l2_note: str | None = None) -> dict[str, Any]:  # fmt: skip
    """Append one re-measure to an entry: L1 (translated whole, plus accounted) to `series`; L2 to `l2_series`, which a
    blind draw allows only with the owner amendment recorded (`--l2-note` the first time)."""
    e = next((x for x in data["estates"] if x["key"] == key), None)
    if e is None:
        raise ValueError(f"no estate {key!r} in the journey")
    if not source:
        raise ValueError("every point needs a source")
    if value > total:
        raise ValueError(f"value {value} > total {total}")
    field = "series" if measure == "L1" else "l2_series"
    if measure == "L2" and e.get("kind") == "blind":
        if l2_note:
            e["l2_measure_note"] = l2_note
        if not e.get("l2_measure_note"):
            raise ValueError("L2 on a blind draw needs the owner amendment that allowed cases: pass --l2-note")
        if not e.get("l2_series"):
            e["l2_series"] = [{"date": e["first_contact"]["date"], "prs": 0, "value": 0, "total": total,
                               "source": "first contact: no case exists for a blind estate at T0 (rule 2)"}]  # fmt: skip
    pts = e.setdefault(field, [])
    if pts and prs < int(pts[-1].get("prs") or 0):
        raise ValueError(f"prs {prs} goes back (last point is at {pts[-1]['prs']})")
    p: dict[str, Any] = {"date": date, "prs": prs, "value": value, "total": total, "source": source}
    if measure == "L1":
        p["accounted"] = accounted
    pts.append(p)
    return data


def trial_prs(rows: list[tuple[str, int, str]], since_utc: str, trial_issues: list[int], estate: str,
              causes: list[int] | None = None) -> list[tuple[str, int, str]]:  # fmt: skip
    """The trial's merged PRs since first contact, in merge order: a title citing one of the trial's issues, naming the
    estate, or a fix the trial booked as a cause. `rows` are (merged_at UTC ISO, number, title)."""
    issues = {str(n) for n in trial_issues}
    keep = []
    for ts, n, title in sorted(set(rows)):
        if ts < since_utc:
            continue
        if set(re.findall(r"#(\d+)", title)) & issues or estate.lower() in title.lower() or n in (causes or []):
            keep.append((ts, n, title))
    return keep


def l2_series_from_prs(prs: list[tuple[str, int, str]], eligible: list[str], basis: int,
                       first_contact_date: str) -> list[dict[str, Any]]:  # fmt: skip
    """L2 after each case PR: a PR whose title says "case(s)" and names eligible programs adds those it names first
    (the CI det-sweep ratchet holds a merged case's det port equal on every scenario). x = the PR's index in `prs`."""
    names = re.compile(r"\b(" + "|".join(map(re.escape, sorted(eligible, key=len, reverse=True))) + r")\b")
    seen: set[str] = set()
    out = [{"date": first_contact_date, "prs": 0, "value": 0, "total": basis,
            "source": "first contact: no case exists for a blind estate at T0 (rule 2)"}]  # fmt: skip
    for i, (ts, n, title) in enumerate(prs, 1):
        if not CASE_TITLE.search(title):
            continue
        new = [p for p in dict.fromkeys(names.findall(title)) if p not in seen]
        if not new:
            continue
        seen.update(new)
        out.append({"date": ts.replace("T", " ").replace("Z", " UTC"), "prs": i, "value": len(seen), "total": basis,
                    "source": f"PR #{n} merged, case added (det port equal, CI det-sweep ratchet): {', '.join(new)}"})
    return out


def fetch_prs(trial_issues: list[int], estate: str, since_day: str) -> list[tuple[str, int, str]]:
    """Merged PRs mentioning any of the trial's issues or the estate, via `gh` (needs auth; never run in CI)."""
    rows = []
    for q in [*map(str, trial_issues), estate]:
        out = subprocess.run(
            ["gh", "pr", "list", "-R", REPO_SLUG, "--state", "merged", "--limit", "200", "--search",
             f"{q} merged:>={since_day}", "--json", "number,mergedAt,title",
             "-q", '.[] | "\\(.mergedAt)\\t\\(.number)\\t\\(.title)"'],
            capture_output=True, text=True, check=True,
        ).stdout  # fmt: skip
        for line in out.splitlines():
            ts, n, title = line.split("\t", 2)
            rows.append((ts, int(n), title))
    return rows


def save(data: dict[str, Any], path: Path = DATA) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _record(args: argparse.Namespace) -> int:
    data = load()
    planned = planned_draws()
    try:
        if args.cmd == "add-draw":
            add_draw(data, draw=args.draw, repo=args.repo, issue=args.issue, estate=args.estate, basis=args.basis,
                     date=args.date, whole=args.whole, accounted=args.accounted, source=args.source, planned=planned,
                     trial=args.trial, trial_issues=args.trial_issues)  # fmt: skip
        elif args.cmd == "point":
            add_point(data, key=args.key, measure=args.measure, prs=args.prs, value=args.value, total=args.total,
                      source=args.source, date=args.date, accounted=args.accounted, l2_note=args.l2_note)  # fmt: skip
        else:  # l2-from-prs
            e = next(x for x in data["estates"] if x["key"] == args.key)
            if not e.get("l2_measure_note"):
                raise ValueError("record the owner amendment first: point --measure L2 --l2-note ...")
            ledger = json.loads(TRIALS.read_text(encoding="utf-8"))
            tr = next(t for t in ledger["trials"] if t["id"] == e["trial"])
            rows = trial_prs(fetch_prs(e["trial_issues"], e["estate"], args.since[:10]), args.since,
                             e["trial_issues"], e["estate"], args.causes)  # fmt: skip
            series = l2_series_from_prs(rows, tr["eligible"], e["program_basis"], e["first_contact"]["date"])
            print(json.dumps(series, indent=1))
            print(f"{len(rows)} trial PRs; L2 {series[-1]['value']} / {e['program_basis']}", file=sys.stderr)
            if not args.write:
                return 0
            e["l2_series"] = series
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    bad = problems(data, planned)
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    save(data)
    print("journey.json updated; now run tests/tools/estate_journey.py to regenerate the page", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when the committed page or a chart is stale")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("add-draw", help="record a blind draw's first contact (T0)")
    a.add_argument("--draw", type=int, required=True)
    a.add_argument("--repo", required=True, help="owner/name, as the trial issue names it")
    a.add_argument("--issue", type=int, required=True, help="the trial issue")
    a.add_argument("--estate", required=True, help="the estate id (trials.json / corpus name)")
    a.add_argument("--basis", type=int, required=True, help="programs in the restated basis")
    a.add_argument("--date", required=True, help="T0, as 'YYYY-MM-DD h:mm PM' ET")
    a.add_argument("--whole", type=int, required=True, help="programs translated whole at T0")
    a.add_argument("--accounted", type=int)
    a.add_argument("--source", required=True, help="the T0 comment URL")
    a.add_argument("--trial", help="the trials.json id, once trial.py start has run")
    a.add_argument("--trial-issues", type=lambda s: [int(x) for x in s.split(",")], default=[],
                   help="comma-separated sub-issues whose PRs count as trial PRs")  # fmt: skip
    p = sub.add_parser("point", help="append one re-measure (L1 or L2) to an entry")
    p.add_argument("--key", required=True)
    p.add_argument("--measure", choices=("L1", "L2"), required=True)
    p.add_argument("--prs", type=int, required=True, help="merged trial PRs since first contact")
    p.add_argument("--value", type=int, required=True)
    p.add_argument("--total", type=int, required=True)
    p.add_argument("--accounted", type=int)
    p.add_argument("--date", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--l2-note", help="the owner amendment allowing cases on this blind draw (first L2 point)")
    r = sub.add_parser("l2-from-prs", help="rebuild a blind draw's L2 series from its merged case PRs (needs gh)")
    r.add_argument("--key", required=True)
    r.add_argument("--since", required=True, help="first contact, UTC ISO (e.g. 2026-11-08T03:32)")
    r.add_argument("--causes", type=lambda s: [int(x) for x in s.split(",")], default=[],
                   help="comma-separated fix PRs the trial booked as causes")  # fmt: skip
    r.add_argument("--write", action="store_true", help="replace l2_series (default: print it)")
    args = ap.parse_args(argv)
    if args.cmd:
        return _record(args)
    data = load()
    bad = problems(data, planned_draws())
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
