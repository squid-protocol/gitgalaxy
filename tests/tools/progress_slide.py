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

    # ---------------------------------------------------------------- how to read it: the six steps, defined once
    lw = (W - 2 * PAD) / len(LEVELS)
    for i, (lv, name, desc) in enumerate(LEVELS):
        x = PAD + i * lw
        s.rect(x, y - 2, 18, 18, f"lv{i}", rx=4)
        s.text(x + 26, y + 13, f"{lv} {name}", cls="t1", size=15, weight=700)
        s.text(x + 26, y + 33, desc, cls="t3", size=13)
    y += 58

    # ---------------------------------------------------------------- headline: four program counts, L4 the hero
    net = tot.get("netted") or {}
    n_net = sum(net.values())
    gap = 16
    tw, th = (W - 2 * PAD - 3 * gap) / 4, 116
    ready = det["total"]["ready"]
    tiles = [
        (f"{comp['translator']['whole']} / {comp['translator']['of']}",
         pct(comp["translator"]["whole"], comp["translator"]["of"]), "translate whole", "every line becomes Java (L1+)",
         False),
        (f"{l2p} / {n_prog}", pct(l2p, n_prog), "give the same output", "equal on their test cases (L2+)", False),
        (f"{l4p} / {n_prog}", pct(l4p, n_prog), "take every branch",
         f"net of {n_net} reviewed outcomes (L4+)" if n_net else "every branch outcome run (L4+)", True),
        (f"{total['L5']} / {n_prog}", pct(total["L5"], n_prog), "catch planted bugs",
         f"+{ready} passing, not yet counted (L5)" if ready else "every planted bug caught (L5)", False),
    ]  # fmt: skip
    for i, (big, p, lab, sub, hi) in enumerate(tiles):
        x = PAD + i * (tw + gap)
        s.rect(x, y, tw, th, "card-hi" if hi else "card", rx=10)
        s.text(x + 18, y + 44, big, cls="t1", size=30, weight=700)
        s.text(x + tw - 16, y + 44, p, cls="hi" if hi else "t2", size=20, weight=700 if hi else 600, anchor="end")
        s.text(x + 18, y + 74, lab, cls="t1", size=16, weight=600)
        s.text(x + 18, y + 96, sub, cls="t3", size=13)
    y += th + 44

    # ---------------------------------------------------------------- results: levels | L5, one row per estate
    section(
        f"Results: {l4p} of {n_prog} real programs take every branch; {total['L5']} pass the planted-bug test",
        "Each row is one codebase. Left: how far its programs have climbed (an L5 program counts at L4 here). "
        "Right: its planted-bug work (L5). Our own test estates sit below, never in a total.",
    )
    name_w, gutter, row_h, bar_h = 210, 28, 38, 26
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

    def ladder_row(nm: str, e: dict[str, Any], e5: dict[str, Any] | None, bold: bool = False) -> None:
        nonlocal y
        lv = e["levels"]
        vals = [lv["L0"], lv["L1"], lv["L2"], lv["L3"], lv["L4"] + lv["L5"]]
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
        s.text(PAD, y + 35, sub, cls="t3", size=13.5)
        y += 48

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
        "We develop against these, so they are not blind tests; no blind codebase has been measured yet.",
    )
    for key, e in sorted(estates.items(), key=lambda kv: -kv[1]["programs"]):
        ladder_row(ESTATE_NAMES.get(key, key), e, m5.get(key))
    s.add(f'<line x1="{PAD + name_w}" x2="{W - PAD}" y1="{y + 4}" y2="{y + 4}" class="rule-soft"/>')
    y += 8
    ladder_row("All real codebases", {"levels": total, "programs": n_prog}, det["total"], bold=True)
    notes = []
    if n_net:
        parts = [f"{net[f]} {lab}" for f, lab in progress_report.NETTED_CLASSES if net.get(f)]
        notes.append(f"Every branch is net of {', '.join(parts)} outcomes, each named in its evidence report.")
    if tot.get("stale"):
        notes.append(f"{tot['stale']} levels carried while their inputs are stale (L*).")
    dt = det["total"]
    if dt["measured"]:
        notes.append(
            f"L5 so far: {dt['raw_pct']:.0f}% of the planted bugs checked are caught; {dt['sampled_pct']:.0f}% of all "
            "planted bugs have been checked."
        )
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
    num = 2
    if tests:
        n_t = sum(e["programs"] for e in tests.values())
        band(
            num,
            f"Our CICS test suite: {n_t} small programs, each exercising one CICS behaviour the codebases use",
            "Written by us to break the CICS translation. Kept out of every total.",
        )
        num += 1
        for key, e in tests.items():
            ladder_row(TEST_ESTATE_NAMES.get(key, key), e, det["estates"].get(key))
        y += 12
    if levels:
        lh = sum(lv["horrors"] for lv in levels)
        lp = sum(lv["pass"] for lv in levels)
        band(
            num,
            f"Our practice codebases for what comes next: {len(levels)} Open World levels (pinned {cc.get('ref')})",
            "Built before the translator supports them, and not translated yet by design: each level's first run is "
            f"measured once (rule 5). The scanner reads {lp} of their {lh} planted traps correctly.",
        )
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

    style = f"""
  <style>
    svg {{ font-family: {FONT}; }}
    .bg {{ fill: #fcfcfb; }}
    .card {{ fill: #f3f2ef; }}
    .card-hi {{ fill: #f3f2ef; stroke: {LADDER_LIGHT[4]}; stroke-width: 2.5; }} .hi {{ fill: #127a55; }}
    .track {{ fill: #e6e5e0; }} .meter {{ fill: #5d5c57; }}
    .rule {{ stroke: #c3c2b7; stroke-width: 1; }} .rule-soft {{ stroke: #e0dfd9; stroke-width: 1; }}
    .t1 {{ fill: #0b0b0b; }} .t2 {{ fill: #3a3936; }} .t3 {{ fill: #52514e; }}
    .on-dark {{ fill: #ffffff; }} .on-light {{ fill: #0b0b0b; }}
    {"".join(f".lv{i} {{ fill: {c}; }} " for i, c in enumerate(LADDER_LIGHT))}
    {"".join(f".s{i} {{ fill: {c}; }} " for i, c in enumerate(STATUS_LIGHT))}
    {"".join(f".m{i} {{ fill: {c}; }} " for i, c in enumerate(L5_LIGHT))}
    .st-good {{ fill: #0ca30c; }} .st-warn {{ fill: none; stroke: #c98500; stroke-width: 2; }}
    .st-warn-fill {{ fill: #c98500; }} .st-none {{ fill: none; stroke: #8a8984; stroke-width: 2; }}
    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #1a1a19; }} .card {{ fill: #242422; }} .track {{ fill: #383835; }} .rule {{ stroke: #52514e; }}
      .card-hi {{ fill: #242422; stroke: {LADDER_DARK[4]}; }} .hi {{ fill: #3ccf98; }} .meter {{ fill: #b5b4ad; }}
      .rule-soft {{ stroke: #383835; }}
      .t1 {{ fill: #f0efec; }} .t2 {{ fill: #dddcd6; }} .t3 {{ fill: #c3c2b7; }}
      .on-light {{ fill: #0b0b0b; }}
      {"".join(f".lv{i} {{ fill: {c}; }} " for i, c in enumerate(LADDER_DARK))}
      {"".join(f".s{i} {{ fill: {c}; }} " for i, c in enumerate(STATUS_DARK))}
      {"".join(f".m{i} {{ fill: {c}; }} " for i, c in enumerate(L5_DARK))}
    }}
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
