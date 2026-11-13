"""#5286: the COBOL-to-Java "where we stand" slide as one self-contained SVG (light and dark), a generated page.

Every number comes from the progress report (`progress_report.gather()` -> progress.json), so the slide cannot drift
from the page; the GitHub parts (milestones, title-search counts, Open World epic states) read "not measured" when the
issues cache is absent and no token is set -- never a number. The design is the owner-reviewed prototype (two rounds),
with its hand-typed runtime rows replaced by the capability ledger: every state there is computed, and the zeros stay.
Round three (owner, 2026-11-04, after a designer / buyer / auditor / editor review): one story top to bottom --
how to read it, results on real code (with our own test estates beside them, never in a total), results by age,
the planted-bug test, what the translator can do, how faithful its runtime is, and the work behind it.

    python tests/tools/progress_slide.py [--out FILE]      # default: stdout
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

import capability_ledger  # noqa: E402
import ladder_exclusions  # noqa: E402
import progress_report  # noqa: E402

W = 1280
PAD = 40
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

# Ladder: L0 neutral (inventoried only), then categorical slots yellow, magenta, violet, aqua, blue (searched: passes
# adjacent CVD + normal-vision both modes). These hues mean a ladder level and nothing else on the slide.
# L5's swatch is the L5 bar's "pass" shade, so L5 is one colour everywhere on the slide
LADDER_LIGHT = ["#a3a29b", "#eda100", "#e87ba4", "#6250d6", "#1baf7a", "#1d3f6e"]
LADDER_DARK = ["#6b6a64", "#c98500", "#d55181", "#9085e9", "#199e70", "#2f5e9e"]
# Runtime rule status, most settled to least: slate, light slate, brick, sand -- none a ladder hue, and the two warm
# statuses are no longer neighbours (round-three review: DIFFERS orange next to REFUSED amber failed the ΔE floor)
STATUSES = ["MATCHED", "ASSUMED", "DIFFERS", "REFUSED"]
STATUS_LIGHT = ["#2e4a62", "#9aa9b7", "#b4533a", "#e3c9a8"]
STATUS_DARK = ["#3f6584", "#a9b6c2", "#c0624a", "#d9bf9c"]
STATUS_LABEL_CLS = ["on-dark", "on-light", "on-dark", "on-light"]

# L5 is a different kind of test (planted bugs, not coverage), so its states get their own single-hue ramp, darkest =
# passing; "not yet tested" is the neutral track
L5_STATES = [
    ("pass", "pass L5"),
    ("not yet counted", "pass, not yet counted"),
    ("bugs open", "tested, planted bugs still open"),
    ("not yet tested", "not yet tested"),
]
L5_LIGHT = ["#1d3f6e", "#4f78ad", "#a9bdd8"]
SURFACE = "#0f1117"  # the README films' background
L5_DARK = ["#2f5e9e", "#5a82b8", "#a9bdd8"]

LEVELS = [
    ("L0", "Read", "scanned, not yet translated"),
    ("L1", "Translates whole", "every line becomes Java"),
    ("L2", "Same output", "equal on every test case"),
    ("L3", "Every paragraph", "tests run every paragraph"),
    ("L4", "Every branch", "tests take every branch"),
    ("L5", "Catches planted bugs", "planted bugs caught"),
]
LEVELS_IDX = {lv: i for i, (lv, _, _) in enumerate(LEVELS)}
ERAS = [
    ("0", "~1969-80", "Macro-level CICS", "ANS 68 COBOL", "DFHxx macros, CSA/TCA"),
    ("1", "~1978-88", "CICS/VS command level", "OS/VS COBOL (74)", "BLL cells, HANDLE CONDITION"),
    ("2", "~1988-96", "CICS/MVS, CICS/ESA", "VS COBOL II / COBOL 85", "RESP/RESP2, EXEC SQL, DPL"),
    ("3", "~1996-2005", "CICS TS 1-2", "COBOL for OS/390, LE", "MQ, EXCI, 3270 bridge, web"),
    ("4", "2005+", "CICS TS 3+", "Enterprise COBOL", "channels, JSON, async, counters"),
]
ESTATE_NAMES = {
    "aws-mainframe-modernization-carddemo": "CardDemo",
    "cics-async-api-credit-card-application-example": "Async credit card",
    "cics-banking-sample-application-cbsa": "CBSA (banking)",
    "cics-genapp": "GenApp (insurance)",
    "dbb-mortgage-application": "DBB Mortgage",
    "zecs": "zECS",
}
TEST_ESTATE_NAMES = {"cics-crucible": "CICS test suite"}
# The runtime rule families, spelled out once (the codes are cobolrt_rules.json's)
FAMILY_NAMES = {
    "CBL": "COBOL core",
    "NUM": "numbers",
    "FUNC": "built-in functions",
    "LE": "LE date / time",
    "HFP": "hex floating point",
    "MVS": "OS calls",
    "DLI": "IMS database",
    "SQL": "Db2 SQL",
    "MQ": "IBM MQ",
    "CICS": "CICS",
    "FILE": "files",
    "SORT": "sort",
    "EDIT": "editing",
    "DATA": "data items",
    "SYS": "system",
}
# Mainframe milestones shown, in story order, by plain name (the milestone titles are the project's own)
MILESTONES = [10, 13, 15, 20, 24, 18, 27, 28, 19, 29, 30]
NOT_MEASURED = "not measured"
MS_SHORT = {
    10: "Read mainframe code",
    13: "Score the evidence",
    15: "Many languages and code pages",
    20: "Our own test estates",
    24: "COBOL-to-Java translator",
    18: "Verified runs",
    27: "Evidence integrity",
    28: "Core engine",
    19: "Fresh codebases",
    29: "Open World: MQ, IMS, JCL, VSAM",
    30: "Gap Atlas: found, not yet built",
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


class Svg:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, cls="t2", size=14, weight=400, anchor="start", title=None) -> None:
        t = f"<title>{esc(title)}</title>" if title else ""
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{t}{esc(s)}</text>'
        )

    def rect(self, x, y, w, h, cls, rx=0, title=None) -> None:
        if w <= 0:
            return
        t = f"<title>{esc(title)}</title>" if title else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" class="{cls}">{t}</rect>')


def stacked(svg: Svg, x, y, w, h, values, classes, titles, label_min=26, label_cls=None, names=None, min_w=0) -> None:
    """A 100%-width stacked bar with 2px surface gaps and in-segment counts where they fit. A non-zero segment is at
    least `min_w` wide (taken from the wider ones), so a single program never vanishes into a sliver."""
    total = sum(values)
    if not total:
        svg.rect(x, y, w, h, "track", rx=4)
        return
    segs = [
        (v, c, t, lc, nm)
        for v, c, t, lc, nm in zip(
            values, classes, titles, label_cls or [None] * len(values), names or [None] * len(values)
        )
        if v
    ]
    gap = 2
    usable = w - gap * (len(segs) - 1)
    widths = [usable * v / total for v, *_ in segs]
    if min_w:
        short = [i for i, sw in enumerate(widths) if sw < min_w]
        need = sum(min_w - widths[i] for i in short)
        room = sum(widths[i] for i in range(len(widths)) if i not in short)
        if short and room > need:
            widths = [min_w if i in short else sw - need * sw / room for i, sw in enumerate(widths)]
    cx = x
    for i, ((v, c, t, lc, nm), sw) in enumerate(zip(segs, widths)):
        rx = 4 if i in (0, len(segs) - 1) else 0
        svg.rect(cx, y, sw, h, c, rx=rx, title=t)
        long = f"{nm} · {v}" if nm else None
        if long and sw >= 7.4 * len(long) + 14:  # a named label only where it fits inside its segment
            lab = long
        else:
            lab = v if sw >= max(min(label_min, min_w or label_min), 7.4 * len(str(v)) + 8) else None
        if lab is not None:
            svg.text(cx + sw / 2, y + h / 2 + 5, lab, cls=lc or "on-dark", size=13, weight=600, anchor="middle")
        cx += sw + gap


def pct(a, b) -> str:
    return f"{100 * a / b:.0f}%" if b else "-"


def state_icon(s: Svg, cx: float, cy: float, state: str) -> None:
    """Each state has its own shape, so none rests on colour alone."""
    if state == "works":
        s.add(f'<circle cx="{cx}" cy="{cy}" r="6" class="st-good"/>')
    elif state == "partial":
        s.add(f'<circle cx="{cx}" cy="{cy}" r="6" class="st-warn"/>')
        s.add(f'<path d="M {cx} {cy - 6} A 6 6 0 0 1 {cx} {cy + 6} Z" class="st-warn-fill"/>')
    elif state == "extract":
        s.add(f'<circle cx="{cx}" cy="{cy}" r="6" class="st-warn"/>')
        s.add(f'<circle cx="{cx}" cy="{cy}" r="2.5" class="st-warn-fill"/>')
    elif state == "refused":
        s.add(f'<circle cx="{cx}" cy="{cy}" r="6" class="st-none"/>')
        s.add(f'<line x1="{cx - 4}" y1="{cy + 4}" x2="{cx + 4}" y2="{cy - 4}" class="st-none"/>')
    else:
        s.add(f'<circle cx="{cx}" cy="{cy}" r="6" class="st-none"/>')


def _nice_prs(n: int) -> int:
    """A round x-axis end for the trial-PR scale shared by every draw panel."""
    for step in (10, 20, 25, 50, 100, 200, 250, 500):
        if n <= step * 5:
            return max(step, -(-n // step) * step)
    return n


def fresh_section(s: Svg, y: float, fr: dict[str, Any]) -> float:
    """Code we had never seen: the census rehearsal and the blind draws, first contact then the climb. Each draw is one
    panel on a shared scale (x: trial PRs since first contact; y: share of its programs), one measure per panel (L2
    where cases were allowed, else L1), never both on one axis. The draws not yet made are empty slots, so the
    pre-registered count shows and none can be left out."""
    blind, census, planned = fr.get("blind") or [], fr.get("census") or [], fr.get("planned") or 0
    s.text(PAD, y, f"Code we had never seen: {len(blind)} of {planned} blind draws so far", cls="t1", size=21,
           weight=700)  # fmt: skip
    s.text(PAD, y + 24, "Measured from the first run on the estate, before any fix, then after each merged PR. Never in "
           "the totals above. Public code may be in a model's training data; the translator uses no model.",
           cls="t3", size=13.5)  # fmt: skip
    y += 46

    # three cards: the census rehearsal, then every blind draw summed (so they scale to all draws)
    def l1_sum(key: str) -> tuple[int, int]:
        rows = [r["l1"] for r in blind if r.get("l1")]
        if key == "first":
            return sum(c["first"] for c in rows), sum(c["first_total"] for c in rows)
        return sum(c["now"] for c in rows), sum(c["total"] for c in rows)

    cards = []
    for r in census:
        c, a = r["l1"], r.get("accounted")
        cards.append((
            "Census rehearsal (tools only, no cases)",
            f"{c['first']}/{c['first_total']} → {c['now']}/{c['total']}", "", "translate whole (L1)",
            (f"{a['now']} / {a['total']} accounted (whole, or a named source defect)" if a else ""),
            f"{c['prs_to_now']} trial PRs" + (f" · {r['days']} days" if r.get("days") else ""),
        ))  # fmt: skip
    if blind:
        f0, ft = l1_sum("first"), l1_sum("now")
        fast = [r["l1_milestone"] for r in blind if r.get("l1_milestone")]
        cards.append((
            f"Blind draws at first contact ({len(blind)} so far)",
            f"{f0[0]}/{f0[1]} → {ft[0]}/{ft[1]}", "", "translate whole (L1)",
            "; ".join(f"{m['value']} / {m['total']} after {m['prs']} trial PRs ({m['days']} days)" for m in fast[:2]),
            "first contact: the engine as it was, before any fix",
        ))  # fmt: skip
        tries = [r["first_try"] for r in blind if r.get("first_try")]
        if tries:
            p1, j, fin = (sum(t[k] for t in tries) for k in ("proven_first", "judged", "proven_final"))
            elig = sum(t["eligible"] for t in tries)
            cards.append((
                "First try: one attempt, frozen engine",
                f"{p1} / {j}", pct(p1, j), "same output on the first try",
                f"{fin} / {elig} same output after engine fixes (never first-try)",
                "deterministic port vs GnuCOBOL, every scenario",
            ))  # fmt: skip
    gap, ch = 16, 150
    cw = (W - 2 * PAD - gap * (len(cards) - 1)) / max(len(cards), 1)
    for i, (head, big, p, lab, sub, sub2) in enumerate(cards):
        x = PAD + i * (cw + gap)
        s.rect(x, y, cw, ch, "card", rx=10)
        s.text(x + 18, y + 26, head, cls="t3", size=13, weight=600)
        s.text(x + 18, y + 62, big, cls="t1", size=28, weight=700)
        if p:
            s.text(x + cw - 16, y + 62, p, cls="hi", size=20, weight=700, anchor="end")
        s.text(x + 18, y + 88, lab, cls="t1", size=15, weight=600)
        s.text(x + 18, y + 110, sub, cls="t2", size=12.5)
        s.text(x + 18, y + 130, sub2, cls="t3", size=12.5)
    y += ch + 22

    # the draw panels: 6 a row, every planned draw a slot, the last cell the key
    cols, pg, ph = 6, 12, 128
    pw = (W - 2 * PAD - pg * (cols - 1)) / cols
    by_draw = {r["draw"]: r for r in blind if r.get("draw")}
    xmax = _nice_prs(max([pt[0] for r in blind for c in (r.get("l2"), r.get("l1")) if c for pt in c["points"]] + [10]))
    n_slots = max(planned, len(blind))
    cells = [("draw", k) for k in range(1, n_slots + 1)] + [("key", 0)]
    for idx, (kind, k) in enumerate(cells):
        x = PAD + (idx % cols) * (pw + pg)
        yy = y + (idx // cols) * (ph + pg)
        if kind == "key":
            s.rect(x, yy, pw, ph, "card", rx=8)
            s.text(x + 12, yy + 22, "How to read a panel", cls="t1", size=13, weight=700)
            s.text(x + 12, yy + 42, f"across: trial PRs, 0 to {xmax}", cls="t3", size=11.5)
            s.text(x + 12, yy + 58, "up: share of its programs", cls="t3", size=11.5)
            s.add(f'<line x1="{x + 12}" x2="{x + 34}" y1="{yy + 78}" y2="{yy + 78}" class="ln2"/>')
            s.text(x + 40, yy + 82, "L2 same output", cls="t2", size=11.5)
            s.add(f'<line x1="{x + 12}" x2="{x + 34}" y1="{yy + 98}" y2="{yy + 98}" class="ln1"/>')
            s.text(x + 40, yy + 102, "L1 translates whole", cls="t2", size=11.5)
            s.text(x + 12, yy + 120, "one measure per panel", cls="t3", size=11.5)
            continue
        r = by_draw.get(k)
        if not r:
            s.add(f'<rect x="{x:.1f}" y="{yy:.1f}" width="{pw:.1f}" height="{ph}" rx="8" class="slot"/>')
            s.text(x + 12, yy + 22, f"Blind {k}", cls="t3", size=13, weight=700)
            s.text(x + pw / 2, yy + ph / 2 + 10, "not yet drawn", cls="t3", size=12, anchor="middle")
            continue
        c, lv = (r["l2"], "L2") if r.get("l2") else (r["l1"], "L1")
        s.rect(x, yy, pw, ph, "card", rx=8, title=f"Blind {k}: {r['name']}")
        s.text(x + 12, yy + 20, f"Blind {k}", cls="t1", size=13, weight=700)
        s.text(x + pw - 12, yy + 20, f"{r['basis']} programs", cls="t3", size=11.5, anchor="end")
        s.text(x + 12, yy + 36, r.get("estate") or "", cls="t3", size=11.5)
        x0, x1, top, bot = x + 14, x + pw - 14, yy + 50, yy + 96
        s.add(f'<line x1="{x0}" x2="{x1:.1f}" y1="{bot}" y2="{bot}" class="rule"/>')
        s.add(f'<line x1="{x0}" x2="{x1:.1f}" y1="{top}" y2="{top}" class="rule-soft"/>')
        pts = []
        for i, (px, pv) in enumerate(c["points"]):
            cx = x0 + (x1 - x0) * px / xmax
            cy = bot - (bot - top) * pv / c["total"]
            if i:
                pts.append(f"{cx:.1f},{pts[-1].split(',')[1]}")  # a step: the value holds until the PR that moves it
            pts.append(f"{cx:.1f},{cy:.1f}")
        tip = esc(f"Blind {k}: {lv} from {c['first']} to {c['now']} of {c['total']}")
        line_cls = "ln2" if lv == "L2" else "ln1"
        s.add(f'<polyline points="{" ".join(pts)}" class="{line_cls}"><title>{tip}</title></polyline>')
        fx, fy = (float(v) for v in pts[0].split(","))
        ex, ey = (float(v) for v in pts[-1].split(","))
        s.add(f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="3.5" class="lv{LEVELS_IDX[lv]}"/>')
        s.add(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" class="lv{LEVELS_IDX[lv]}"/>')
        s.text(ex - 4, ey - 7, f"{c['now']}/{c['total']}", cls="t1", size=11.5, weight=700, anchor="end")
        s.text(x + 12, yy + 114, f"{lv} {c['first']} → {c['now']}/{c['total']} in {c['prs_to_now']} PRs", cls="t2",
               size=11.5, weight=600)  # fmt: skip
    rows = -(-len(cells) // cols)
    y += rows * (ph + pg) + 6
    s.text(PAD, y + 8, "L2 needs cases, written only after first contact (owner amendment, blind 1). First try counts "
           "the frozen engine only: a later fix never turns a miss into a first-try pass.", cls="t3", size=13)  # fmt: skip
    return y + 60


def render(prog: dict[str, Any]) -> str:
    """The slide from a progress report (`progress_report.build()` / progress.json)."""
    lad, comp, eras, iss = prog["ladder"], prog["components"], prog["eras"], prog["issues"]
    measured = bool(iss.get("measured"))
    ms = {m["number"]: m for m in iss.get("milestones", [])}
    ic = iss.get("title_counts")
    rules = comp["cobolrt_rules"]
    estates = lad["estates"]
    tot = lad["total"]
    total = tot["levels"]
    n_prog = tot["programs"]
    l2p, l4p = tot["l2_plus"], tot["l4_plus"]
    det = comp["det_mutation"]
    caps = comp["capabilities"]
    fresh = prog.get("fresh") or {}

    s = Svg()
    y = PAD

    def section(title: str, sub: str, gap_after: int = 46) -> None:
        nonlocal y
        s.text(PAD, y, title, cls="t1", size=21, weight=700)
        s.text(PAD, y + 24, sub, cls="t3", size=13.5)
        y += gap_after

    # ---------------------------------------------------------------- header: what this is, in one breath
    s.text(PAD, y + 26, "COBOL to Java: where we stand", cls="t1", size=32, weight=700)
    s.text(
        PAD,
        y + 56,
        f"{n_prog} programs from {len(estates)} real mainframe codebases we did not write, translated to Java and "
        "checked one evidence step at a time.",
        cls="t2",
        size=15,
        weight=600,
    )
    s.text(
        PAD,
        y + 78,
        "'Same output' means equal to GnuCOBOL run under IBM's documented rules; not yet measured on a real IBM "
        f"mainframe (z/OS). Built from commit {prog['commit'][:9]}"
        + (f" on {iss['as_of'][:10]}." if measured else f"; GitHub counts {NOT_MEASURED}."),
        cls="t3",
        size=13.5,
    )
    y += 112

    # ---------------------------------------------------------------- headline: the four facts, real codebases first
    net = tot.get("netted") or {}
    n_net = sum(net.values())
    tests_ = lad.get("test_estates") or {}
    t_n = sum(e["programs"] for e in tests_.values())
    t_whole = sum(e["translated_whole"] for e in tests_.values())
    t_l2 = sum(e["l2_plus"] for e in tests_.values())
    t_l4 = sum(e["l4_plus"] for e in tests_.values())
    dt = det["total"]
    judged = dt["caught"] + dt["survived"]
    ours = (lambda v: f"Our test suite: {v} / {t_n}") if t_n else (lambda v: "")
    gap = 16
    tw, th = (W - 2 * PAD - 3 * gap) / 4, 140
    tiles = [
        (f"{comp['translator']['whole']} / {comp['translator']['of']}",
         pct(comp["translator"]["whole"], comp["translator"]["of"]), "programs translate whole",
         "every line becomes Java (L1+)", ours(t_whole), False),
        (f"{l2p} / {n_prog}", pct(l2p, n_prog), "give the same output", "equal on their test cases (L2+)", ours(t_l2),
         False),
        (f"{l4p} / {n_prog}", pct(l4p, n_prog), "take every branch",
         f"net of {n_net} reviewed outcomes (L4+)" if n_net else "every branch outcome run (L4+)", ours(t_l4), True),
        (f"{dt['caught']:,}", pct(dt["caught"], judged), "planted bugs caught by tests",
         f"of {judged:,} run; {total['L5']} programs pass L5", "Our test suite: L5 not yet started" if t_n else "",
         False),
    ]  # fmt: skip
    for i, (big, p, lab, sub, sub2, hi) in enumerate(tiles):
        x = PAD + i * (tw + gap)
        s.rect(x, y, tw, th, "card-hi" if hi else "card", rx=10)
        s.text(x + 18, y + 44, big, cls="t1", size=30, weight=700)
        s.text(x + tw - 16, y + 44, p, cls="hi" if hi else "t2", size=20, weight=700 if hi else 600, anchor="end")
        s.text(x + 18, y + 74, lab, cls="t1", size=16, weight=600)
        s.text(x + 18, y + 96, sub, cls="t3", size=13)
        if sub2:
            s.add(f'<line x1="{x + 18}" x2="{x + tw - 18}" y1="{y + 110}" y2="{y + 110}" class="rule-soft"/>')
            s.text(x + 18, y + 128, sub2, cls="t2", size=13, weight=600)
    y += th + 30

    # ---------------------------------------------------------------- how to read it: the six steps, defined once
    lw = (W - 2 * PAD) / len(LEVELS)
    for i, (lv, name, desc) in enumerate(LEVELS):
        x = PAD + i * lw
        s.rect(x, y - 2, 18, 18, f"lv{i}", rx=4)
        s.text(x + 26, y + 13, f"{lv} {name}", cls="t1", size=15, weight=700)
        s.text(x + 26, y + 33, desc, cls="t3", size=13)
    y += 92

    # ---------------------------------------------------------------- results: levels | L5, one row per estate
    section(
        f"Results: {l4p} of {n_prog} real programs take every branch; {total['L5']} pass the planted-bug test",
        "Each row is one codebase. Left: how far its programs have climbed (an L5 program counts at L4 here). "
        "Right: its planted-bug work (L5). Our own test estates sit below, never in a total.",
    )
    name_w, gutter, row_h, bar_h = 210, 28, 44, 26
    bar_x = PAD + name_w
    bar_w = (W - 2 * PAD - name_w - gutter) * 0.56
    r_x = bar_x + bar_w + gutter
    r_w = W - PAD - r_x
    m5 = {k: det["estates"].get(k) for k in estates}

    def l5_bar(e5: dict[str, Any] | None, nm: str) -> None:
        if not e5 or not e5.get("programs"):
            s.rect(r_x, y + 5, r_w, bar_h, "track", rx=4, title=f"{nm}: no planted-bug run yet")
            s.text(r_x + 12, y + 23, "L5 not yet started", cls="t2", size=13.5, weight=600)
            return
        opened = e5["measured"] - e5["l5"] - e5["ready"]
        vals = [e5["l5"], e5["ready"], opened, e5["programs"] - e5["measured"]]
        stacked(
            s,
            r_x,
            y + 5,
            r_w,
            bar_h,
            vals,
            ["m0", "m1", "m2", "track"],
            [f"{nm}: {v} {lab}" for v, (_, lab) in zip(vals, L5_STATES)],
            label_cls=["on-dark", "on-dark", "on-light", "t2"],
            names=[short for short, _ in L5_STATES],
            min_w=22,
        )

    def size_line(z: dict[str, Any] | None) -> str:
        if not z:
            return ""
        k = z["program_lines"] / 1000
        parts = [f"{k:.1f}k lines" if k < 10 else f"{k:.0f}k lines", f"{z['copybooks']} copybooks"]
        if z.get("jcl_jobs"):
            parts.append(f"{z['jcl_jobs']} jobs")
        return " · ".join(parts)

    def ladder_row(nm: str, e: dict[str, Any], e5: dict[str, Any] | None, bold: bool = False) -> None:
        nonlocal y
        lv = e["levels"]
        vals = [lv["L0"], lv["L1"], lv["L2"], lv["L3"], lv["L4"] + lv["L5"]]
        sub = size_line(e.get("size"))
        if sub:
            s.text(PAD, y + 18, nm, cls="t1", size=14.5, weight=700 if bold else 500)
            s.text(PAD, y + 35, sub, cls="t3", size=12)
        else:
            s.text(PAD, y + 23, nm, cls="t1", size=14.5, weight=700 if bold else 500)
        stacked(
            s,
            bar_x,
            y + 5,
            bar_w,
            bar_h,
            vals,
            [f"lv{i}" for i in range(5)],
            [
                f"{nm}: {v} at {LEVELS[i][0]} {LEVELS[i][1]}" + (" or above" if i == 4 else "")
                for i, v in enumerate(vals)
            ],
            label_cls=["on-light", "on-light", "on-light", "on-dark", "on-light"],
            names=[lv_ for lv_, _, _ in LEVELS[:5]],
            min_w=22,
        )
        l5_bar(e5, nm)
        y += row_h

    def band(num: int, title: str, sub: str) -> None:
        nonlocal y
        if num > 1:
            s.add(f'<line x1="{PAD}" x2="{W - PAD}" y1="{y}" y2="{y}" class="rule"/>')
            y += 16
        s.text(PAD, y + 15, f"{num}. {title}", cls="t1", size=16.5, weight=700)
        for k, line in enumerate(sub.split("\n")):  # a long subtitle is given as two lines
            s.text(PAD, y + 35 + 20 * k, line, cls="t3", size=13.5)
        y += 48 + 20 * sub.count("\n")

    # column heads, and the L5 legend (its own colours: L5 is a different kind of test)
    s.text(bar_x, y + 4, "Levels L0-L4: how far each program has climbed", cls="t2", size=13.5, weight=700)
    s.text(r_x, y + 4, "L5: the planted-bug test", cls="t2", size=13.5, weight=700)
    lx = r_x
    for i, (short, lab) in enumerate(L5_STATES):
        s.rect(lx, y + 14, 12, 12, ["m0", "m1", "m2", "track"][i], rx=2)
        s.text(lx + 17, y + 25, short, cls="t3", size=12.5)
        lx += 17 + 7.2 * len(short) + 14
    y += 40

    band(
        1,
        f"Real codebases we did not write: {len(estates)} IBM and AWS sample applications, {n_prog} programs",
        "We develop against these, so they are not blind tests; "
        + ("code we had never seen is measured apart, from first contact (below)."
           if fresh.get("blind") or fresh.get("census") else "no blind codebase has been measured yet."),
    )  # fmt: skip
    for key, e in sorted(estates.items(), key=lambda kv: -kv[1]["programs"]):
        ladder_row(ESTATE_NAMES.get(key, key), e, m5.get(key))
    s.add(f'<line x1="{PAD + name_w}" x2="{W - PAD}" y1="{y + 4}" y2="{y + 4}" class="rule-soft"/>')
    y += 8
    ladder_row("All real codebases", {"levels": total, "programs": n_prog, "size": tot.get("size")}, det["total"],
               bold=True)  # fmt: skip
    notes = []
    if n_net:
        parts = [f"{net[f]} {lab}" for f, lab in progress_report.NETTED_CLASSES if net.get(f)]
        notes.append(f"Every branch is net of {', '.join(parts)} outcomes, each named in its evidence report.")
    if tot.get("stale"):
        notes.append(f"{tot['stale']} levels carried while their inputs are stale (L*).")
    if dt["measured"]:
        notes.append(
            f"L5 so far: {dt['caught']:,} of the {judged:,} planted bugs run were caught by a test; "
            f"{dt['equivalent'] + dt['unreachable']:,} more are explained as harmless"
        )
        notes.append("(equivalent or unreachable: reviewed claims, not yet audited).")
        notes.append(f"{dt['sampled_pct']:.0f}% of the {dt['mutants']:,} possible planted bugs have been run.")
    # the hand-written ports' score, always beside the L5 work so it is never read as the translator's
    m = comp["mutation"]
    notes.append(
        f"Separate from these: hand-written ports, not the translator, score {m['adjusted_kill_pct']:.1f}% adjusted "
        f"and {m['raw_kill_pct']:.1f}% raw over {m['ports']} ports. They feed no level."
    )
    for t in notes:
        s.text(bar_x, y + 8, t, cls="t3", size=13)
        y += 20
    y += 14

    # the programs not at L4 yet, each named with its ruling, right under the bars they explain
    below = lad.get("below_l4") or []
    if below:
        groups: dict[tuple, list[str]] = {}
        for b in below:
            groups.setdefault((b["kind"], b["estate"], b["level"], b["why"], b["issue"]), []).append(b["program"])
        n_below = len(below)
        n_open = sum(1 for b in below if b["kind"] == "open")
        bh = 58 + 26 * len(groups)
        s.rect(PAD, y, W - 2 * PAD, bh, "card", rx=10)
        s.text(PAD + 18, y + 27, f"The {n_below} not at every branch yet, each named: none dropped", cls="t1",
               size=15.5, weight=700)  # fmt: skip
        s.text(
            PAD + 18,
            y + 47,
            f"All still count in the {n_prog}. {n_below - n_open} stop where a ruling stops them"
            + (f"; {n_open} still in progress." if n_open else "; every other program is at L4 or above."),
            cls="t3",
            size=13.5,
        )
        yy = y + 76
        for (kind, estate, lv, why, issue), progs in sorted(groups.items(), key=lambda kv: (kv[0][2], kv[0][1])):
            s.rect(PAD + 18, yy - 13, 32, 18, f"lv{LEVELS_IDX[lv]}", rx=3)
            s.text(PAD + 34, yy + 1, lv, cls="on-dark" if lv in ("L3", "L5") else "on-light", size=12, weight=700,
                   anchor="middle")  # fmt: skip
            s.text(PAD + 60, yy, f"{ESTATE_NAMES.get(estate, estate)} {', '.join(progs)}", cls="t1", size=14,
                   weight=600)  # fmt: skip
            s.text(PAD + 340, yy, ladder_exclusions.KIND_SHORT.get(kind, kind), cls="t2", size=13.5, weight=700)
            s.text(PAD + 460, yy, why, cls="t3", size=13)
            if issue:
                s.text(W - PAD - 18, yy, issue, cls="t2", size=13, weight=600, anchor="end")
            yy += 26
        y += bh + 22

    tests = lad.get("test_estates") or {}
    cc = (comp.get("crucibles") or {}).get("estate_crucible") or {}
    levels = cc.get("levels") or []
    if tests or levels:
        n_t = sum(e["programs"] for e in tests.values())
        lh = sum(lv["horrors"] for lv in levels)
        lp = sum(lv["pass"] for lv in levels)
        parts = []
        if tests:
            parts.append(f"{n_t} CICS test programs")
        if levels:
            parts.append(f"{len(levels)} Open World practice codebases (pinned {cc.get('ref')})")
        band(
            2,
            "Our internal test suites: " + " and ".join(parts),
            "Written by us to break the translator, never in a total. The CICS programs test one CICS behaviour each.\n"
            "The practice codebases come before translator support and are not translated yet by design (their first "
            f"run is measured once, rule 5); the scanner reads {lp} of their {lh} planted traps correctly.",
        )
        for key, e in tests.items():
            ladder_row(TEST_ESTATE_NAMES.get(key, key), e, det["estates"].get(key))
        for lv in levels:
            s.text(PAD, y + 18, lv["name"], cls="t1", size=14.5, weight=500)
            s.text(PAD, y + 35, f"Level {lv['region']} · {lv['about']}", cls="t3", size=12.5)
            n = lv["programs"]
            built = f"built {lv['built']} of {lv['constructs']} planned constructs ({lv['built_pct'] or 0:.0f}%)"
            if n:
                s.rect(bar_x, y + 5, bar_w, bar_h, "lv0", rx=4, title=f"{lv['name']}: {n} programs at L0")
                s.text(bar_x + 12, y + 23, f"L0 · {n} program{'s' * (n != 1)}, {lv['jobs']} job{'s' * (lv['jobs'] != 1)}",
                       cls="on-light", size=13.5, weight=700)  # fmt: skip
                s.text(bar_x + bar_w - 12, y + 23, built, cls="on-light", size=13, weight=600, anchor="end")
            else:
                s.rect(bar_x, y + 5, bar_w, bar_h, "track", rx=4, title=f"{lv['name']}: no program at the pin yet")
                s.text(bar_x + 12, y + 23, "no program yet", cls="t2", size=13.5, weight=600)
                s.text(bar_x + bar_w - 12, y + 23, built, cls="t2", size=13, weight=600, anchor="end")
            fr = lv.get("first_run")
            s.rect(r_x, y + 5, r_w, bar_h, "track", rx=4, title=f"{lv['name']}: translation first run pending")
            s.text(r_x + 12, y + 23, "L5 not yet started", cls="t2", size=13.5, weight=600)
            s.text(r_x + r_w - 12, y + 23, f"first run {fr['date']}" if fr else "first run pending", cls="t3", size=13,
                   anchor="end")  # fmt: skip
            y += 46
    y += 40

    # ---------------------------------------------------------------- code we had never seen
    if fresh.get("census") or fresh.get("blind"):
        y = fresh_section(s, y, fresh)

    # ---------------------------------------------------------------- results by age of code
    section(
        "Results by age of code: 1970s to today",
        "Real codebases mix decades: 1980s programs LINK 1990s ones that call 2010s Db2 code. Each program is dated by "
        f"the features it uses (era_tags.py); {eras.get('none', {}).get('programs', 0)} show no dating clue.",
        gap_after=42,
    )
    ew, eh, egap = (W - 2 * PAD - 4 * 14) / 5, 166, 14
    for i, (num_, when, cics, cobol, tells) in enumerate(ERAS):
        x = PAD + i * (ew + egap)
        e = eras.get(num_, {"programs": 0, "l2_plus": 0, "l4_plus": 0})
        s.rect(x, y, ew, eh, "card", rx=10)
        s.text(x + 16, y + 28, f"Era {num_}", cls="t1", size=18, weight=700)
        s.text(x + ew - 16, y + 28, when, cls="t3", size=13, anchor="end")
        s.text(x + 16, y + 50, cics, cls="t1", size=14, weight=600)
        s.text(x + 16, y + 68, cobol, cls="t3", size=13)
        if e["programs"]:
            s.text(x + 16, y + 96, f"{e['programs']} programs", cls="t1", size=15, weight=700)
            for k, (lab, v) in enumerate([("same output (L2+)", e["l2_plus"]), ("every branch (L4+)", e["l4_plus"])]):
                yy = y + 108 + k * 28
                s.rect(x + 16, yy, ew - 32, 7, "track", rx=3)
                s.rect(x + 16, yy, (ew - 32) * v / e["programs"], 7, "lv2" if k == 0 else "lv4", rx=3,
                       title=f"Era {num_}: {v} of {e['programs']} {lab}")  # fmt: skip
                s.text(x + 16, yy + 21, f"{lab}: {v} ({pct(v, e['programs'])})", cls="t2", size=13)
        else:
            s.text(x + 16, y + 96, "None in our codebases", cls="t1", size=15, weight=700)
            s.text(x + 16, y + 118, "refused by name (#5121);", cls="t3", size=13)
            s.text(x + 16, y + 136, "mapped in the Gap Atlas", cls="t3", size=13)
    y += eh + 50

    # ---------------------------------------------------------------- skills: what the translator can do
    rows = caps["rows"]
    counts = {st: sum(1 for r in rows if r["state"] == st) for st in capability_ledger.STATES}
    summary = ", ".join(f"{counts[st]} {capability_ledger.STATE_LABEL[st].lower()}" for st in capability_ledger.STATES
                        if counts[st])  # fmt: skip
    section(
        f"What the translator can do: {len(rows)} mainframe areas, gaps included",
        f"{summary[0].upper() + summary[1:]}. Counted from the code on every run; a bar appears only where IBM "
        "publishes a full list to count against.",
        gap_after=46,
    )
    lx = PAD
    for st in capability_ledger.STATES:
        state_icon(s, lx + 8, y - 4, st)
        s.text(lx + 22, y, capability_ledger.STATE_LABEL[st], cls="t2", size=13.5, weight=600)
        lx += 130
    y += 28
    for group in caps["groups"]:
        s.text(PAD, y + 4, group, cls="t1", size=15, weight=700)
        s.add(f'<line x1="{PAD}" x2="{W - PAD}" y1="{y + 11}" y2="{y + 11}" class="rule"/>')
        y += 32
        for r in (r for r in rows if r["group"] == group):
            state_icon(s, PAD + 8, y - 4, r["state"])
            s.text(PAD + 22, y, capability_ledger.STATE_LABEL[r["state"]], cls="t3", size=13)
            s.text(PAD + 110, y, r["name"], cls="t1", size=14, weight=600)
            s.text(PAD + 330, y, r["have"], cls="t3", size=13)
            if r["of"]:
                bx, bw = W - PAD - 290, 110
                s.rect(bx, y - 10, bw, 10, "track", rx=4)
                s.rect(bx, y - 10, bw * r["done"] / r["of"], 10, "meter", rx=4,
                       title=f"{r['name']}: {r['done']} of {r['of']}")  # fmt: skip
                s.text(bx + bw + 10, y, f"{r['done']} / {r['of']}", cls="t1", size=14, weight=700)
                s.text(W - PAD, y, r["unit"].replace("modelled on both runtimes", "modelled").replace(
                    "modelled; the rest refused by name", "modelled"), cls="t3", size=12.5, anchor="end")  # fmt: skip
            if r["note"]:
                s.text(PAD + 330, y + 17, r["note"], cls="t3", size=12.5)
                y += 17
            y += 27
        y += 8
    s.text(
        PAD,
        y + 4,
        f"{caps['register']['entries']} named limits in the register; {caps['register']['refused']} of them stop the "
        "run with a named error rather than guess.",
        cls="t2",
        size=13.5,
        weight=600,
    )
    y += 50

    # ---------------------------------------------------------------- how faithful the runtime is
    fams = rules.get("families", {})
    st_all = rules["status"]
    n_rules = rules["rules"]
    section(
        f"How faithful the Java runtime is: {st_all.get('MATCHED', 0)} of {n_rules} rules match IBM's manuals",
        "Each rule is one documented COBOL or CICS behaviour, judged against IBM's documentation. "
        f"Measured on z/OS: {rules['measured_on_zos']} of {n_rules} so far (#4702).",
        gap_after=42,
    )
    defs = [
        ("MATCHED", "Matches IBM", "implements IBM's documented rule"),
        ("ASSUMED", "IBM is silent", "our choice, written down by name"),
        ("DIFFERS", "Follows GnuCOBOL", "a known difference from z/OS"),
        ("REFUSED", "Stops the run", "with a named error, never a guess"),
    ]
    dw = (W - 2 * PAD) / 4
    for i, (k, lab, desc) in enumerate(defs):
        x = PAD + i * dw
        s.rect(x, y, 16, 16, f"s{i}", rx=3)
        s.text(x + 24, y + 13, f"{lab}: {st_all.get(k, 0)} ({pct(st_all.get(k, 0), n_rules)})", cls="t1", size=14,
               weight=600)  # fmt: skip
        s.text(x + 24, y + 31, desc, cls="t3", size=13)
    y += 52
    fw = 250
    full = W - 2 * PAD - fw - 90
    maxn = max(sum(v.values()) for v in fams.values()) if fams else 1
    order = sorted(fams.items(), key=lambda kv: -sum(kv[1].values()))  # stable: ties keep the catalogue order
    for name, c in order:
        n = sum(c.values())
        s.text(
            PAD,
            y + 14,
            (f"{FAMILY_NAMES[name]} ({name})" if FAMILY_NAMES.get(name, name).lower() != name.lower() else name),
            cls="t1",
            size=13.5,
            weight=600,
        )
        s.text(PAD + fw - 10, y + 14, n, cls="t3", size=13, anchor="end")
        bw = full * n / maxn
        stacked(s, PAD + fw, y + 3, bw, 15, [c.get(k, 0) for k in STATUSES], [f"s{i}" for i in range(4)],
                [f"{name}: {c.get(k, 0)} {k}" for k in STATUSES], label_min=10_000)  # fmt: skip
        s.text(PAD + fw + bw + 8, y + 14, f"{pct(c.get('MATCHED', 0), n)} match", cls="t3", size=13)
        y += 23
    y += 44

    # ---------------------------------------------------------------- the work behind it
    section(
        "Work done: issues closed per project stage",
        "Issue counts measure activity, not evidence. The Gap Atlas lists mainframe features found but not yet chosen "
        "to build.",
        gap_after=46,
    )
    mlw = (W - 2 * PAD - 30) * 0.62
    mx_name, mbar_x = PAD, PAD + 260
    mbar_w = mlw - 260 - 110
    my = y
    if not ms:
        s.text(mx_name, my + 13, f"Milestones: {NOT_MEASURED} (no issues cache and no token)", cls="t3", size=13.5)
        my += 26 * 4
    for n in MILESTONES:
        mm = ms.get(n)
        if not mm:
            continue
        c, t = mm["closed"], mm["total"]
        s.text(mx_name, my + 13, MS_SHORT.get(n, mm["title"]), cls="t1", size=13.5, weight=500, title=mm["title"])
        s.rect(mbar_x, my + 2, mbar_w, 14, "track", rx=4)
        s.rect(mbar_x, my + 2, mbar_w * c / t if t else 0, 14, "meter", rx=4, title=f"{mm['title']}: {c} of {t} closed")
        s.text(mbar_x + mbar_w + 10, my + 14, f"{pct(c, t)}  ({c}/{t})", cls="t2", size=13)
        my += 27
    ix = PAD + mlw + 30
    iw = W - PAD - ix

    def title_box(term: str, label: str) -> tuple[str, str, str, str]:
        c = (ic or {}).get(term)
        if not c:
            return NOT_MEASURED, "", label, f"issues with {term.upper()} in the title"
        return (
            f"{c['closed']} / {c['total']}",
            pct(c["closed"], c["total"]),
            label,
            f"issues with {term.upper()} in the title",
        )

    boxes = [
        title_box("cics", "CICS issues resolved"),
        title_box("cobol", "COBOL issues resolved"),
        (f"{iss['core']['closed']} / {iss['core']['total']}", "", "core issues closed", f"{iss['core']['open']} still open")
        if measured
        else (NOT_MEASURED, "", "core issues closed", "the core scope"),
        (f"{iss['frontier']['total']}", "", "gaps mapped (Gap Atlas)",
         f"{iss['frontier']['found_last_window']} found in the last {iss['window_days']} days")
        if measured
        else (NOT_MEASURED, "", "gaps mapped (Gap Atlas)", "Gap Atlas"),
    ]  # fmt: skip
    bh = (my - y - 3 * 10) / 4
    for k, (big, p, lab, sub) in enumerate(boxes):
        by = y + k * (bh + 10)
        s.rect(ix, by, iw, bh, "card", rx=10)
        s.text(ix + 16, by + bh / 2 + 3, big, cls="t1", size=22, weight=700)
        if p:
            s.text(ix + iw - 16, by + bh / 2 + 3, p, cls="t2", size=18, weight=600, anchor="end")
        s.text(ix + 150, by + bh / 2 - 6, lab, cls="t1", size=13.5, weight=600)
        s.text(ix + 150, by + bh / 2 + 13, sub, cls="t3", size=12.5)
    y = my + 26
    s.text(
        PAD,
        y,
        "Sources: progress.json (progress_report.py, which reads cobolrt_rules.json), GitHub milestones and issue search. "
        "Regenerated on every docs run; never hand-edited.",
        cls="t3",
        size=13,
    )
    H = y + PAD - 10

    # House style: dark, always (owner, 2026-11-08). GitHub shows this SVG through an <img>, where a
    # prefers-color-scheme switch follows the viewer's OS rather than GitHub's theme, so there is no light
    # variant to flip to. The surface matches the README films (#0f1117).
    style = f"""
  <style>
    svg {{ font-family: {FONT}; }}
    .bg {{ fill: {SURFACE}; }} .card {{ fill: #1b1e26; }} .track {{ fill: #2c2f38; }}
    .card-hi {{ fill: #1b1e26; stroke: {LADDER_DARK[4]}; stroke-width: 2.5; }} .hi {{ fill: #3ccf98; }}
    .meter {{ fill: #b5b4ad; }}
    .rule {{ stroke: #4a4b55; stroke-width: 1; }} .rule-soft {{ stroke: #2c2f38; stroke-width: 1; }}
    .t1 {{ fill: #f0efec; }} .t2 {{ fill: #dddcd6; }} .t3 {{ fill: #c3c2b7; }}
    .on-dark {{ fill: #ffffff; }} .on-light {{ fill: #0b0b0b; }}
    {"".join(f".lv{i} {{ fill: {c}; }} " for i, c in enumerate(LADDER_DARK))}
    {"".join(f".s{i} {{ fill: {c}; }} " for i, c in enumerate(STATUS_DARK))}
    {"".join(f".m{i} {{ fill: {c}; }} " for i, c in enumerate(L5_DARK))}
    .st-good {{ fill: #3ccf98; }} .st-warn {{ fill: none; stroke: #c98500; stroke-width: 2; }}
    .st-warn-fill {{ fill: #c98500; }} .st-none {{ fill: none; stroke: #8a8984; stroke-width: 2; }}
    .slot {{ fill: none; stroke: #3a3d47; stroke-width: 1.5; stroke-dasharray: 5 5; }}
    .ln2 {{ fill: none; stroke: {LADDER_DARK[2]}; stroke-width: 2.5; stroke-linejoin: round; }}
    .ln1 {{ fill: none; stroke: {LADDER_DARK[1]}; stroke-width: 2.5; stroke-dasharray: 6 4; }}
  </style>"""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}" '
        f'role="img" aria-labelledby="ttl"><title id="ttl">COBOL to Java: where we stand</title>{style}'
        f'<rect class="bg" width="{W}" height="{H:.0f}" rx="16"/>' + "".join(s.parts) + "</svg>"
    )


def render_page() -> str:
    import progress_report  # tests/tools/progress_report.py

    return render(progress_report.gather()) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    text = render_page()
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
