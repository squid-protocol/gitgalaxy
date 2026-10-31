"""#5286: the COBOL-to-Java "where we stand" slide as one self-contained SVG (light and dark), a generated page.

Every number comes from the progress report (`progress_report.gather()` -> progress.json), so the slide cannot drift
from the page; the GitHub parts (milestones, title-search counts, Open World epic states) read "not measured" when the
issues cache is absent and no token is set -- never a number. The design is the owner-reviewed prototype (two rounds),
with its hand-typed runtime rows replaced by the capability ledger: every state there is computed, and the zeros stay.

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

W = 1280
PAD = 40
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

# Ladder: L0 neutral (inventoried only), L1-L5 one blue ramp light->dark (dataviz validator: ordinal, both modes PASS)
# L1-L5: categorical slots yellow, magenta, violet, aqua, blue (searched: passes adjacent CVD + normal-vision both modes)
LADDER_LIGHT = ["#a3a29b", "#eda100", "#e87ba4", "#6250d6", "#1baf7a", "#2a78d6"]
LADDER_DARK = ["#6b6a64", "#c98500", "#d55181", "#9085e9", "#199e70", "#3987e5"]
# cobolrt status: categorical slots 1-4 in validated order (blue, orange, aqua, yellow)
STATUS_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
STATUS_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500"]
STATUSES = ["MATCHED", "DIFFERS", "ASSUMED", "REFUSED"]

LEVELS = [
    ("L0", "Inventoried", "parsed, not yet translated"),
    ("L1", "Translated", "whole program compiles as Java"),
    ("L2", "Runs equal", "same outputs as the oracle"),
    ("L3", "Every paragraph", "tests run every paragraph"),
    ("L4", "Every branch", "tests take every branch"),
    ("L5", "Mutants accounted", "every planted bug caught or explained"),
]
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
TEST_ESTATE_NAMES = {"cics-crucible": "CICS crucible (test)"}
# Mainframe milestones shown, in story order
MILESTONES = [10, 13, 15, 20, 24, 18, 27, 28, 19, 29, 30]
NOT_MEASURED = "not measured"
MS_SHORT = {
    15: "World Tour (GG goes multicultural)",
    10: "Enter the Mainframe",
    13: "Scorekeeper",
    20: "Nightmare Mode (crucibles)",
    24: "Class Change (COBOL to Java)",
    18: "Run Verified",
    27: "Save Integrity",
    28: "Training Montage (core)",
    19: "New Challenger (fresh estates)",
    29: "Open World (MQ, IMS, JCL, VSAM)",
    30: "Gap Atlas (mapped, not built)",
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


def stacked(svg: Svg, x, y, w, h, values, classes, titles, label_min=26, label_cls=None, names=None) -> None:
    """A 100%-width stacked bar with 2px surface gaps and in-segment counts where they fit."""
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
    cx = x
    for i, (v, c, t, lc, nm) in enumerate(segs):
        sw = usable * v / total
        rx = 4 if i in (0, len(segs) - 1) else 0
        svg.rect(cx, y, sw, h, c, rx=rx, title=t)
        lab = f"{nm} · {v}" if nm and sw >= 64 else (v if sw >= label_min else None)
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
    total = lad["total"]["levels"]
    n_prog = lad["total"]["programs"]
    l2p = lad["total"]["l2_plus"]

    s = Svg()
    y = PAD
    det = comp["det_mutation"]
    caps = comp["capabilities"]
    # ---------------------------------------------------------------- header
    s.text(PAD, y + 24, "COBOL to Java: where we stand", cls="t1", size=30, weight=700)
    s.text(
        PAD,
        y + 52,
        f"{len(estates)} burned estates, {n_prog} programs. Generated from main {prog['commit'][:9]}"
        f"{' on ' + iss['as_of'][:10] if measured else '; GitHub counts ' + NOT_MEASURED}. Oracle: GnuCOBOL plus IBM documentation (not yet measured on z/OS).",
        cls="t3",
        size=14,
    )
    y += 80

    # ---------------------------------------------------------------- hero tiles
    tw, th, gap = (W - 2 * PAD - 3 * 16) / 4, 112, 16
    tiles = [
        (
            f"{comp['translator']['whole']} / {comp['translator']['of']}",
            pct(comp["translator"]["whole"], comp["translator"]["of"]),
            "programs translated whole",
            "Java with no holes (L1 or above)",
        ),
        (
            f"{l2p} / {n_prog}",
            pct(l2p, n_prog),
            "programs run equal to the oracle",
            "same outputs on their cases (L2 or above)",
        ),
        (
            f"{comp['cics']['modelled_both_runtimes']} / {comp['cics']['burned_commands']}",
            pct(comp["cics"]["modelled_both_runtimes"], comp["cics"]["burned_commands"]),
            "CICS commands the estates use",
            "modelled on both runtimes",
        ),
        (
            f"{total['L5']} / {n_prog}",
            pct(total["L5"], n_prog),
            "programs at L5",
            f"{det['total']['ready']} more pass, awaiting a refresh",
        ),
    ]
    for i, (big, p, lab, sub) in enumerate(tiles):
        x = PAD + i * (tw + gap)
        s.rect(x, y, tw, th, "card", rx=10)
        s.text(x + 18, y + 44, big, cls="t1", size=32, weight=700)
        if p:
            s.text(x + tw - 18, y + 44, p, cls="t2", size=22, weight=600, anchor="end")
        s.text(x + 18, y + 72, lab, cls="t1", size=15, weight=600)
        s.text(x + 18, y + 94, sub, cls="t3", size=13)
    y += th + 36

    # ---------------------------------------------------------------- ladder
    s.text(PAD, y, "Evidence ladder: where each program stands", cls="t1", size=20, weight=700)
    s.text(
        PAD,
        y + 22,
        "Each program sits at the highest level it has reached. Levels from definition_of_done.md.",
        cls="t3",
        size=13,
    )
    y += 40
    lw = (W - 2 * PAD) / 3
    for i, (lv, name, desc) in enumerate(LEVELS):
        x, yy = PAD + (i % 3) * lw, y + (i // 3) * 26
        s.rect(x, yy, 14, 14, f"lv{i}", rx=3)
        s.text(x + 22, yy + 12, f"{lv} {name}:", cls="t1", size=13.5, weight=600)
        s.text(x + 22 + 7.6 * len(f"{lv} {name}:") + 6, yy + 12, desc, cls="t3", size=12.5)
    y += 62
    name_w, cnt_w, row_h, bar_h = 190, 6 * 46 + 70, 34, 22
    bar_x, bar_w = PAD + name_w, W - 2 * PAD - name_w - cnt_w - 20
    cx0 = bar_x + bar_w + 20
    s.text(PAD, y + 4, "Estate", cls="t3", size=12, weight=600)
    s.text(
        bar_x,
        y + 4,
        "Share of the estate's programs at each level (segments: level · programs)",
        cls="t3",
        size=12,
        weight=600,
    )
    for j, (lv, _, _) in enumerate(LEVELS):
        s.text(cx0 + 46 * j + 30, y + 4, lv, cls="t3", size=12, weight=600, anchor="end")
    s.text(cx0 + 46 * 6 + 60, y + 4, "Programs", cls="t3", size=12, weight=600, anchor="end")
    y += 14
    rows = sorted(estates.items(), key=lambda kv: -kv[1]["programs"]) + [
        ("__total__", {"levels": total, "programs": n_prog})
    ]
    rows += list(lad.get("test_estates", {}).items())  # below the total: never part of it
    for key, e in rows:
        is_total = key == "__total__"
        nm = "All estates" if is_total else ESTATE_NAMES.get(key) or TEST_ESTATE_NAMES.get(key, key)
        if is_total:
            s.add(f'<line x1="{PAD}" x2="{W - PAD}" y1="{y + 4}" y2="{y + 4}" class="rule"/>')
            y += 8
        vals = [e["levels"][k] for k in ["L0", "L1", "L2", "L3", "L4", "L5"]]
        s.text(PAD, y + 20, nm, cls="t1", size=14, weight=700 if is_total else 500)
        stacked(
            s,
            bar_x,
            y + 4,
            bar_w,
            bar_h,
            vals,
            [f"lv{i}" for i in range(6)],
            [f"{nm}: {v} at {LEVELS[i][0]} {LEVELS[i][1]}" for i, v in enumerate(vals)],
            label_cls=["on-light", "on-light", "on-light", "on-dark", "on-light", "on-dark"],
            names=[lv for lv, _, _ in LEVELS],
        )
        for j, v in enumerate(vals):
            s.text(
                cx0 + 46 * j + 30,
                y + 20,
                v if v else "·",
                cls="t1" if v else "t3",
                size=14,
                weight=700 if is_total else 400,
                anchor="end",
            )
        s.text(cx0 + 46 * 6 + 60, y + 20, e["programs"], cls="t1", size=14, weight=700, anchor="end")
        y += row_h
    if lad.get("test_estates"):
        s.text(
            PAD,
            y + 8,
            "A test estate is written to break the translator, so it stays out of the totals above.",
            cls="t3",
            size=12,
        )
        y += 18
    y += 30

    # ---------------------------------------------------------------- L5
    s.text(PAD, y, "L5: what it rests on", cls="t1", size=20, weight=700)
    s.text(
        PAD,
        y + 22,
        "L5 has no score bar: every surviving mutant of the sample must be caught or explained, on current inputs. "
        "Raw score and sample stay beside it.",
        cls="t3",
        size=13,
    )
    y += 44
    cols = [(PAD + 200, "L5"), (PAD + 250, "Ready"), (PAD + 346, "Not measured")]
    raw_x, smp_x, claim_x, mbw = PAD + 386, PAD + 640, W - PAD, 130
    for cx, lab in cols:
        s.text(cx, y, lab, cls="t3", size=12, weight=600, anchor="end")
    s.text(PAD, y, "Estate", cls="t3", size=12, weight=600)
    s.text(raw_x, y, "Raw: caught, of those judged", cls="t3", size=12, weight=600)
    s.text(smp_x, y, "Sample: judged, of all mutants", cls="t3", size=12, weight=600)
    s.text(claim_x, y, "Survivor claims", cls="t3", size=12, weight=600, anchor="end")
    y += 10
    mrows = sorted(det["estates"].items(), key=lambda kv: -kv[1]["programs"]) + [("__total__", det["total"])]
    for key, e in mrows:
        is_total = key == "__total__"
        if is_total:
            s.add(f'<line x1="{PAD}" x2="{W - PAD}" y1="{y + 4}" y2="{y + 4}" class="rule"/>')
            y += 8
        nm = "All estates" if is_total else ESTATE_NAMES.get(key, key)
        wt = 700 if is_total else 400
        s.text(PAD, y + 18, nm, cls="t1", size=14, weight=700 if is_total else 500)
        for (cx, _), v in zip(cols, (e["l5"], e["ready"], e["programs"] - e["measured"])):
            s.text(cx, y + 18, v if v else "·", cls="t1" if v else "t3", size=14, weight=wt, anchor="end")
        if e["measured"]:
            s.rect(raw_x, y + 8, mbw, 10, "track", rx=4)
            s.rect(raw_x, y + 8, mbw * (e["raw_pct"] or 0) / 100, 10, "lv5", rx=4, title=f"{nm}: raw {e['raw_pct']}%")
            s.text(raw_x + mbw + 8, y + 18, f"{e['raw_pct']:.0f}%", cls="t1", size=13, weight=600)
            s.rect(smp_x, y + 8, mbw, 10, "track", rx=4)
            if e["mutants"]:
                sw = mbw * e["sampled"] / e["mutants"]
                s.rect(smp_x, y + 8, sw, 10, "lv3", rx=4, title=f"{nm}: {e['sampled']} of {e['mutants']} mutants")
                s.text(smp_x + mbw + 8, y + 18, f"{e['sampled_pct']:.0f}%", cls="t1", size=13, weight=600)
            n = e["equivalent"] + e["unreachable"]
            s.text(claim_x, y + 18, n if n else "none needed", cls="t1" if n else "t3", size=13, anchor="end",
                   title=f"{e['equivalent']} equivalent, {e['unreachable']} unreachable")  # fmt: skip
        else:
            s.text(raw_x, y + 18, NOT_MEASURED, cls="t3", size=12.5)
            s.text(smp_x, y + 18, NOT_MEASURED, cls="t3", size=12.5)
        y += 28
    m = comp["mutation"]
    s.text(
        PAD,
        y + 12,
        f"Separate from these: hand-written ports, not the translator, score {m['adjusted_kill_pct']:.1f}% adjusted and "
        f"{m['raw_kill_pct']:.1f}% raw over {m['ports']} ports. They feed no level.",
        cls="t3",
        size=12,
    )
    y += 50

    # ---------------------------------------------------------------- capability ledger
    s.text(PAD, y, "Capability ledger: everything the translator can do, zeros included", cls="t1", size=20, weight=700)
    s.text(
        PAD,
        y + 22,
        "Counted from the code on every run. A bar needs a list to measure against; where IBM publishes none, the row "
        "says what exists instead of inventing a percentage.",
        cls="t3",
        size=13,
    )
    y += 44
    lx = PAD
    for st in capability_ledger.STATES:
        state_icon(s, lx + 8, y - 4, st)
        s.text(lx + 22, y, capability_ledger.STATE_LABEL[st], cls="t2", size=13, weight=600)
        lx += 120
    y += 26
    for group in caps["groups"]:
        s.text(PAD, y + 4, group, cls="t1", size=14.5, weight=700)
        s.add(f'<line x1="{PAD}" x2="{W - PAD}" y1="{y + 11}" y2="{y + 11}" class="rule"/>')
        y += 32
        for r in (r for r in caps["rows"] if r["group"] == group):
            state_icon(s, PAD + 8, y - 4, r["state"])
            s.text(PAD + 22, y, capability_ledger.STATE_LABEL[r["state"]], cls="t3", size=12)
            s.text(PAD + 104, y, r["name"], cls="t1", size=13.5, weight=600)
            s.text(PAD + 306, y, r["have"], cls="t3", size=12)
            if not r["of"]:
                s.text(W - PAD, y, "no list to count against", cls="t3", size=11.5, anchor="end")
            else:
                bx, bw = W - PAD - 280, 110
                s.rect(bx, y - 10, bw, 10, "track", rx=4)
                s.rect(
                    bx,
                    y - 10,
                    bw * r["done"] / r["of"],
                    10,
                    "prog",
                    rx=4,
                    title=f"{r['name']}: {r['done']} of {r['of']}",
                )
                s.text(bx + bw + 10, y, f"{r['done']} / {r['of']}", cls="t1", size=13.5, weight=700)
                s.text(W - PAD, y, r["unit"].replace("modelled on both runtimes", "modelled").replace(
                    "modelled; the rest refused by name", "modelled"), cls="t3", size=11.5, anchor="end")  # fmt: skip
            if r["note"]:
                s.text(PAD + 306, y + 16, r["note"], cls="t3", size=11.5)
                y += 16
            y += 26
        y += 8
    z = caps["zos"]
    s.text(
        PAD,
        y + 4,
        f"Every match above means IBM's documentation. Measured on z/OS: {z['measured']} of {z['of']} rules; "
        f"{z['probes']} probes written, none run yet (#4702). "
        f"{caps['register']['entries']} named limits in the register, {caps['register']['refused']} refuse by name.",
        cls="t2",
        size=13,
        weight=600,
    )
    y += 44

    # ---------------------------------------------------------------- cobolrt rules
    right_x, right_w = PAD, W - 2 * PAD
    fams = rules.get("families", {})
    allst = rules["status"]
    n_rules = rules["rules"]
    st_all = allst
    s.text(right_x, y, f"Runtime rules, every family: {n_rules} catalogued", cls="t1", size=20, weight=700)
    s.text(
        right_x,
        y + 22,
        "Every semantic rule of the Java runtime, judged against IBM's documentation",
        cls="t3",
        size=13,
    )
    y += 40
    defs = [
        ("MATCHED", "implements IBM's documented rule"),
        ("DIFFERS", "follows the oracle where z/OS differs"),
        ("ASSUMED", "IBM leaves it open; the choice is named"),
        ("REFUSED", "the runtime stops by name"),
    ]
    dw = right_w / 2
    for i, (k, desc) in enumerate(defs):
        x, yy = right_x + (i % 2) * dw, y + (i // 2) * 34
        s.rect(x, yy, 14, 14, f"s{i}", rx=3)
        s.text(
            x + 22,
            yy + 12,
            f"{k}  {st_all.get(k, 0)} ({pct(st_all.get(k, 0), n_rules)})",
            cls="t1",
            size=13.5,
            weight=600,
        )
        s.text(x + 22, yy + 28, desc, cls="t3", size=11.5)
    y += 80
    fw = 66
    full = right_w - fw - 70
    s.text(right_x, y + 15, "Total", cls="t1", size=12.5, weight=700)
    s.text(right_x + fw - 8, y + 15, n_rules, cls="t1", size=12, weight=700, anchor="end")
    stacked(
        s,
        right_x + fw,
        y,
        full,
        20,
        [st_all.get(k, 0) for k in STATUSES],
        [f"s{i}" for i in range(4)],
        [f"{st_all.get(k, 0)} {k}" for k in STATUSES],
        label_cls=["on-dark", "on-dark", "on-dark", "on-light"],
    )
    s.text(
        right_x + fw + full + 8,
        y + 15,
        f"{pct(st_all.get('MATCHED', 0), n_rules)} match",
        cls="t2",
        size=11.5,
        weight=600,
    )
    s.add(f'<line x1="{right_x}" x2="{right_x + right_w}" y1="{y + 30}" y2="{y + 30}" class="rule"/>')
    y += 40
    order = sorted(fams.items(), key=lambda kv: -sum(kv[1].values()))  # stable: ties keep the catalogue order
    for name, c in order:
        n = sum(c.values())
        s.text(right_x, y + 13, name, cls="t1", size=12.5, weight=600)
        s.text(right_x + fw - 8, y + 13, n, cls="t3", size=12, anchor="end")
        bw = full * n / max(sum(v.values()) for v in fams.values())
        stacked(
            s,
            right_x + fw,
            y + 2,
            bw,
            14,
            [c.get(k, 0) for k in STATUSES],
            [f"s{i}" for i in range(4)],
            [f"{name}: {c.get(k, 0)} {k}" for k in STATUSES],
            label_min=10_000,
        )
        s.text(right_x + fw + bw + 8, y + 13, f"{pct(c.get('MATCHED', 0), n)} match", cls="t3", size=11.5)
        y += 22
    s.text(
        right_x,
        y + 14,
        f"Measured on z/OS: {rules['measured_on_zos']} of {n_rules}. Every rule is "
        "uncalibrated until a z/OS run backs it (#4702).",
        cls="t3",
        size=12,
    )
    y += 60

    # ---------------------------------------------------------------- eras
    s.text(PAD, y, "By era: the CICS and COBOL generations in the estates", cls="t1", size=20, weight=700)
    s.text(
        PAD,
        y + 22,
        "Real estates are layered: 1980s programs LINK 1990s ones that call 2010s Db2 code. "
        f"Era from the code's tells (era_tags.py); {eras.get('none', {}).get('programs', 0)} programs carry no tell.",
        cls="t3",
        size=13,
    )
    y += 40
    ew, eh, egap = (W - 2 * PAD - 4 * 14) / 5, 196, 14
    for i, (num, when, cics, cobol, tells) in enumerate(ERAS):
        x = PAD + i * (ew + egap)
        e = eras.get(num, {"programs": 0, "l2_plus": 0, "l4_plus": 0})
        s.rect(x, y, ew, eh, "card", rx=10)
        s.text(x + 16, y + 28, f"Era {num}", cls="t1", size=18, weight=700)
        s.text(x + ew - 16, y + 28, when, cls="t3", size=13, anchor="end")
        s.text(x + 16, y + 52, cics, cls="t1", size=13.5, weight=600)
        s.text(x + 16, y + 70, cobol, cls="t2", size=12.5)
        s.text(x + 16, y + 88, tells, cls="t3", size=12)
        if e["programs"]:
            s.text(x + 16, y + 118, f"{e['programs']} programs", cls="t1", size=15, weight=700)
            for k, (lab, v) in enumerate([("run equal (L2+)", e["l2_plus"]), ("every branch (L4+)", e["l4_plus"])]):
                yy = y + 134 + k * 30
                s.rect(x + 16, yy, ew - 32, 8, "track", rx=4)
                s.rect(
                    x + 16,
                    yy,
                    (ew - 32) * v / e["programs"],
                    8,
                    "lv2" if k == 0 else "lv4",
                    rx=4,
                    title=f"Era {num}: {v} of {e['programs']} {lab}",
                )
                s.text(x + 16, yy + 24, f"{lab}: {v} ({pct(v, e['programs'])})", cls="t2", size=12)
        else:
            s.text(x + 16, y + 118, "No burned program", cls="t1", size=15, weight=700)
            s.text(x + 16, y + 140, "refused by name (#5121);", cls="t3", size=12)
            s.text(x + 16, y + 158, "mapped in the Gap Atlas", cls="t3", size=12)
    y += eh + 40

    # ---------------------------------------------------------------- milestones + issues
    s.text(PAD, y, "Mainframe milestones and issues", cls="t1", size=20, weight=700)
    s.text(
        PAD,
        y + 22,
        "Share of each milestone's issues closed. Gap Atlas holds discoveries: mapped, built only when promoted.",
        cls="t3",
        size=13,
    )
    y += 44
    mlw = (W - 2 * PAD - 30) * 0.62
    mx_name, mbar_x = PAD, PAD + 240
    mbar_w = mlw - 240 - 110
    my = y
    if not ms:
        s.text(mx_name, my + 13, f"Milestones: {NOT_MEASURED} (no issues cache and no token)", cls="t3", size=13)
        my += 26 * 4
    for n in MILESTONES:
        m = ms.get(n)
        if not m:
            continue
        c, t = m["closed"], m["total"]
        s.text(mx_name, my + 13, MS_SHORT.get(n, m["title"]), cls="t1", size=13, weight=500)
        s.rect(mbar_x, my + 2, mbar_w, 14, "track", rx=4)
        s.rect(mbar_x, my + 2, mbar_w * c / t if t else 0, 14, "prog", rx=4, title=f"{m['title']}: {c} of {t} closed")
        s.text(mbar_x + mbar_w + 10, my + 14, f"{pct(c, t)}  ({c}/{t})", cls="t2", size=12.5)
        my += 26
    ix = PAD + mlw + 30
    iw = W - PAD - ix
    iy = y

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
        (
            f"{iss['core']['closed']} / {iss['core']['total']}",
            "",
            "core issues closed",
            f"{iss['core']['open']} open: the burned-estate finish line",
        )
        if measured
        else (NOT_MEASURED, "", "core issues closed", "the burned-estate finish line"),
        (
            f"{iss['frontier']['total']}",
            "",
            "gaps mapped (Gap Atlas)",
            f"{iss['frontier']['found_last_window']} found in the last {iss['window_days']} days",
        )
        if measured
        else (NOT_MEASURED, "", "gaps mapped (Gap Atlas)", "Gap Atlas"),
    ]
    bh = (my - y - 3 * 10) / 4
    for k, (big, p, lab, sub) in enumerate(boxes):
        by = iy + k * (bh + 10)
        s.rect(ix, by, iw, bh, "card", rx=10)
        s.text(ix + 16, by + bh / 2 + 2, big, cls="t1", size=22, weight=700)
        if p:
            s.text(ix + iw - 16, by + bh / 2 + 2, p, cls="t2", size=18, weight=600, anchor="end")
        s.text(ix + 160, by + bh / 2 - 6, lab, cls="t1", size=13, weight=600)
        s.text(ix + 160, by + bh / 2 + 12, sub, cls="t3", size=11.5)
    y = my + 24
    s.text(
        PAD,
        y,
        "Sources: progress.json (progress_report.py, which reads cobolrt_rules.json), GitHub milestones and issue search. "
        "Regenerated on every docs run; never hand-edited.",
        cls="t3",
        size=12,
    )
    H = y + PAD - 10

    style = f"""
  <style>
    svg {{ font-family: {FONT}; }}
    .bg {{ fill: #fcfcfb; }}
    .card {{ fill: #f3f2ef; }}
    .track {{ fill: #e6e5e0; }}
    .rule {{ stroke: #c3c2b7; stroke-width: 1; }}
    .t1 {{ fill: #0b0b0b; }} .t2 {{ fill: #3a3936; }} .t3 {{ fill: #52514e; }}
    .on-dark {{ fill: #ffffff; }} .on-light {{ fill: #0b0b0b; }}
    {"".join(f".lv{i} {{ fill: {c}; }} " for i, c in enumerate(LADDER_LIGHT))}
    {"".join(f".s{i} {{ fill: {c}; }} " for i, c in enumerate(STATUS_LIGHT))}
    .prog {{ fill: #2a78d6; }}
    .st-good {{ fill: #0ca30c; }} .st-warn {{ fill: none; stroke: #c98500; stroke-width: 2; }}
    .st-warn-fill {{ fill: #c98500; }} .st-none {{ fill: none; stroke: #8a8984; stroke-width: 2; }}
    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #1a1a19; }} .card {{ fill: #242422; }} .track {{ fill: #383835; }} .rule {{ stroke: #52514e; }}
      .t1 {{ fill: #f0efec; }} .t2 {{ fill: #dddcd6; }} .t3 {{ fill: #c3c2b7; }}
      .on-light {{ fill: #0b0b0b; }} .prog {{ fill: #3987e5; }}
      {"".join(f".lv{i} {{ fill: {c}; }} " for i, c in enumerate(LADDER_DARK))}
      {"".join(f".s{i} {{ fill: {c}; }} " for i, c in enumerate(STATUS_DARK))}
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
