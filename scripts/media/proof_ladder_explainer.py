#!/usr/bin/env python3
"""Render "From COBOL to Java, level by level" from ONE program's REAL evidence record.

CardDemo COUSR01C (add user): a COBOL excerpt, the Java the deterministic translator writes for it (no model), and the
evidence ladder L0..L5 lighting up with the numbers the evidence report publishes for the program. Every number shown
is read at render time, never typed in:

* the per-estate evidence report on the `generated` branch
  (`docs/language_status/evidence_report/aws-mainframe-modernization-carddemo/report.json`): level, translation,
  det-port equality, paragraph / branch coverage, mutation;
* `tests/equivalence/det_mutation/carddemo-useradd.json` (the det-port mutation entry: date, commit, stillborn) and
  `tests/equivalence/det_mutation_survivors/carddemo-useradd.json` (each survivor's reviewed verdict);
* `tests/equivalence/infeasible_outcomes/carddemo-useradd.json` (the one reviewed infeasible branch outcome).

The report and the ledgers are cross-checked; a mismatch, or an excerpt line that no longer reads as expected,
aborts. The Java is the det port written by `det_port.py run carddemo-useradd --translate-only --work DIR`.

    git fetch origin generated
    GITGALAXY_MAINFRAME_CORPORA=... python tests/tools/det_port.py run carddemo-useradd --translate-only --work /tmp/dp
    python scripts/media/proof_ladder_explainer.py --work /tmp/dp --corpora .mainframe_corpora \\
        --out docs/media/proof-ladder

Needs Pillow and ffmpeg (docs tooling only). No proof is run.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # scripts/media helpers
from _brand import brand  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
ESTATE, CASE, PROGRAM = "aws-mainframe-modernization-carddemo", "carddemo-useradd", "app/cbl/COUSR01C.cbl"
REPORT = f"docs/language_status/evidence_report/{ESTATE}/report.json"
W, H, FPS = 1280, 720, 12
FD = pathlib.Path("/usr/share/fonts/truetype/dejavu")


def font(size, bold=False, mono=False):
    name = "DejaVuSansMono.ttf" if mono else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    return ImageFont.truetype(str(FD / name), size)


f_title, f_sub, f_bar, f_leg, f_stat, f_stat2 = font(40, True), font(20), font(20, True), font(18), font(18), font(14)
f_code, f_gut, f_hdr = font(14, mono=True), font(13, mono=True), font(15)
f_badge, f_rname, f_cond, f_ev, f_lhdr = font(19, True), font(17, True), font(12), font(15, True), font(15, True)
f_tiny = font(11)
BG, TERM, BAR, LINE = (15, 17, 23), (20, 21, 26), (34, 35, 42), (60, 61, 70)
INK, INK2, MUTED, DIM = (240, 239, 236), (195, 194, 183), (143, 142, 134), (88, 89, 98)
C_COBOL, C_JAVA, C_HELD, C_MUT, C_OFF = (232, 160, 32), (96, 165, 250), (52, 211, 153), (239, 83, 80), (58, 59, 68)

# The excerpt: WRITE-USER-SEC-FILE in COBOL (corpus line numbers) and in the det port (port line numbers). Each line
# must start with the text given (after stripping), or the render refuses: the frames would no longer show the source.
COBOL_LINES = [
    (238, "WRITE-USER-SEC-FILE."),
    (240, "EXEC CICS WRITE"),
    (241, "DATASET   (WS-USRSEC-FILE)"),
    (246, "RESP      (WS-RESP-CD)"),
    (248, "END-EXEC."),
    (250, "EVALUATE WS-RESP-CD"),
    (251, "WHEN DFHRESP(NORMAL)"),
    (252, "PERFORM INITIALIZE-ALL-FIELDS"),
    (260, "WHEN DFHRESP(DUPKEY)"),
    (261, "WHEN DFHRESP(DUPREC)"),
    (262, "MOVE 'Y'     TO WS-ERR-FLG"),
    (263, "MOVE 'User ID already exist...' TO"),
    (264, "WS-MESSAGE"),
]
JAVA_LINES = [
    (1103, "/** WRITE-USER-SEC-FILE. */"),
    (1104, "private int p6() {"),
    (1105, "// EXEC CICS WRITE DATASET (WS-USRSEC-FILE)"),
    (1106, "int resp10 = task.write("),
    (1107, "Cobol.store(f368_EIBRESP, BigDecimal.valueOf(resp10), false, CS);"),
    (1109, "f7_WS_RESP_CD = Cobol.binary(BigDecimal.valueOf(resp10)"),
    (1111, "// EVALUATE WS-RESP-CD"),
    (1112, "if ((f7_WS_RESP_CD == 0L)) {"),
    (1113, "// PERFORM INITIALIZE-ALL-FIELDS"),
    (1114, "perform(8, 8);"),
    (1123, "} else if ((f7_WS_RESP_CD == 15L) || (f7_WS_RESP_CD == 14L)) {"),
    (1124, "// MOVE 'Y' TO WS-ERR-FLG"),
    (1125, 'f6_WS_ERR_FLG = "Y";'),
]
# COBOL statement → the Java the translator writes for it (indices into the two excerpts), shown pair by pair.
PAIRS = [
    ([0], [0, 1], "paragraph → method"),
    ([1, 2, 3, 4], [2, 3, 4, 5], "EXEC CICS WRITE → the CICS task model, RESP stored"),
    ([5, 6], [6, 7], "WHEN DFHRESP(NORMAL) → RESP code 0"),
    ([7], [8, 9], "PERFORM → perform(range)"),
    ([8, 9], [10], "DUPKEY / DUPREC → RESP codes 15 / 14"),
    ([10], [11, 12], "MOVE → assignment, statement for statement"),
]
MUTANT_LINE = 1107  # the survivor shown at L5 must sit on a line of the excerpt


def need(ok, msg):
    """refuse to render (an assert would vanish under python -O)"""
    if not ok:
        raise SystemExit(msg)


def git_show(ref, path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"], capture_output=True, text=True, check=True)


def load(args):
    rep_ref = args.report_ref
    report = json.loads(git_show(rep_ref, REPORT).stdout)
    rep_commit = subprocess.run(
        ["git", "-C", str(ROOT), "log", "-1", "--format=%h %cs", rep_ref], capture_output=True, text=True, check=True
    ).stdout.split()
    prog = next(p for p in report["programs"] if p["program"] == PROGRAM)
    mut = json.loads((ROOT / f"tests/equivalence/det_mutation/{CASE}.json").read_text())["entry"]
    surv = json.loads((ROOT / f"tests/equivalence/det_mutation_survivors/{CASE}.json").read_text())["survivors"]
    infeas = json.loads((ROOT / f"tests/equivalence/infeasible_outcomes/{CASE}.json").read_text())["entries"]
    verdicts = collections.Counter(s["verdict"] for s in surv)
    m, cov, tr = prog["mutation"], prog["coverage"], prog["translation"]
    eq = prog["equivalence"]["chosen"]
    c = mut["counts"]
    checks = [
        (m["killed"], c["killed"]),
        (m["survived"], c["survived"], len(surv), sum(verdicts.values())),
        (m["mutants"], mut["mutants"], c["killed"] + c["survived"] + c["stillborn"] + c["timeout"] + c["error"]),
        (m["unaccounted"], 0),
        (len(infeas), len(cov["infeasible_netted"])),
    ]
    for vals in checks:
        if len(set(vals)) != 1:
            raise SystemExit(f"report and ledgers disagree: {vals}; refusing to render")
    if prog["level"] != "L5" or not prog["level_current"]:
        raise SystemExit(f"{PROGRAM} reads {prog['level']} (current={prog['level_current']}); storyboard expects L5")
    if eq["det"]["state"] != "equal":
        raise SystemExit("det port not equal on its case")
    example = next(s for s in surv if s["line"] == MUTANT_LINE and s["op"] == "DEL")
    return dict(
        report=report,
        rep_commit=rep_commit,
        prog=prog,
        mut=mut,
        verdicts=verdicts,
        infeas=infeas,
        example=example,
        survey_n=report["summary"].get("programs") or len(report["programs"]),
    )


def excerpt(path, spec, strip_cols):
    src = path.read_text(encoding="utf-8", errors="replace").split("\n")
    rows = []
    for no, want in spec:
        ln = src[no - 1].rstrip()
        if not ln.strip().startswith(want):
            raise SystemExit(f"{path.name}:{no} reads {ln.strip()!r}, expected {want!r}; refusing to render")
        rows.append((no, ln[strip_cols:]))
    ind = min(len(t) - len(t.lstrip()) for _, t in rows)
    return [(no, t[ind:]) for no, t in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="det_port.py run carddemo-useradd --translate-only --work DIR")
    ap.add_argument("--corpora", default=str(ROOT / ".mainframe_corpora"))
    ap.add_argument("--report-ref", default="origin/generated")
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep-frames", action="store_true", help="keep the PNG frames (for review) and print where")
    a = ap.parse_args()
    D = load(a)
    prog, mut, rep = D["prog"], D["mut"], D["report"]
    cobol_path = pathlib.Path(a.corpora) / ESTATE / PROGRAM
    java_path = pathlib.Path(a.work) / CASE / "port/service/Cousr01cService.java"
    if not java_path.read_text().startswith("// gitgalaxy-det-port: COBOL COUSR01C"):
        raise SystemExit(f"{java_path} is not the det port of COUSR01C")
    cobol = excerpt(cobol_path, COBOL_LINES, 7)  # columns 1-6 are the sequence area, 7 the indicator
    java = excerpt(java_path, JAVA_LINES, 0)
    corpus_ref = rep["reproducibility"]["corpus_ref"][:7]

    tr, cov, m, eq = prog["translation"], prog["coverage"], prog["mutation"], prog["equivalence"]["chosen"]
    lv = {x["level"]: x["name"] for x in rep["levels"]}
    inf = D["infeas"][0]
    v = D["verdicts"]
    # README "the program..." column, word for word (the report's `levels` carry the long form).
    COND = {
        "L0": "is in the estate's survey; nothing more is claimed",
        "L1": "translates with no hole and no refusal",
        "L2": "is equal to the COBOL oracle on every scenario of its case",
        "L3": "L2, and the scenarios run every live paragraph",
        "L4": "L3, and every branch outcome, net of reviewed infeasible ones",
        "L5": "L4, and every surviving mutant of the port accounted for",
    }
    bn, br = cov["branches_net"], cov["branches"]
    EVID = {
        "L0": f"in the survey of {D['survey_n']} CardDemo programs",
        "L1": f"{tr['translated']}/{tr['statements']} statements, {tr['hole_count']} holes, not refused",
        "L2": f"det port equal on {eq['case_scenarios']}/{eq['case_scenarios']} scenarios",
        "L3": f"{cov['paragraphs']['covered']}/{cov['paragraphs']['live']} live paragraphs run",
        "L4": f"{bn['covered']}/{bn['total']} branch outcomes net ({br['covered']}/{br['total']} raw)",
        "L5": f"{m['accounted']}/{m['survived']} survivors accounted for",
    }
    o = rep["oracle"]["compiler"].replace(" (GnuCOBOL)", "")
    STATUS = {
        "L0": (
            f"L0 inventoried: COUSR01C is one of {D['survey_n']} programs in the CardDemo survey",
            "the survey lists every program; nothing more is claimed at L0",
        ),
        "L1": (
            f"L1 translated whole: {tr['translated']} of {tr['statements']} statements translated, "
            f"{tr['hole_count']} holes, no refusal",
            "the det translator, by rule, statement for statement; no model is involved",
        ),
        "L2": (
            f"L2 executed equivalent: det port equal to the COBOL on all {eq['case_scenarios']} scenarios "
            f"of case {eq['case']}",
            f"oracle: GnuCOBOL ({o}) + the gitgalaxy CICS stub and models, not z/OS; CI det-sweep ratchet on main",
        ),
        "L3": (
            f"L3 paragraph coverage: the scenarios run {cov['paragraphs']['covered']} of "
            f"{cov['paragraphs']['live']} live paragraphs (100%)",
            "measured on the traced COBOL runs (det-sweep coverage ledger)",
        ),
        "L4": (
            f"L4 branch coverage: {bn['covered']}/{bn['total']} outcomes net, {br['covered']}/{br['total']} raw; "
            f"1 reviewed infeasible",
            f"line {inf['line']} {inf['kind']} {inf['outcome']} ({inf['unit']}): every PERFORM of it follows a MOVE "
            "of a non-blank program name",
        ),
        "L5": (
            f"L5 mutants accounted for: {m['mutants']:,} mutants of the det port, {m['killed']} killed, "
            f"{m['survived']} survived, {mut['counts']['stillborn']} stillborn",
            f"every survivor reviewed: {v['equivalent']} equivalent, {v['unreachable']} unreachable, 0 unaccounted "
            f"(det-mutation ledger, {mut['date']})",
        ),
    }
    ex = D["example"]
    FINAL = (
        f"COUSR01C: {prog['level']} {lv[prog['level']]} · {eq['case_scenarios']} scenarios equal · "
        f"{cov['paragraphs']['covered']}/{cov['paragraphs']['live']} paragraphs · "
        f"{bn['covered']}/{bn['total']} branches net · {m['accounted']}/{m['survived']} survivors accounted",
        f"{m['mutants']:,} mutants (record {mut['date']}) · evidence report {D['rep_commit'][1]} "
        f"(generated {D['rep_commit'][0][:9]}) · burned (development) estate · oracle GnuCOBOL + models, not z/OS",
    )
    attribution = (
        f"COBOL: AWS CardDemo {PROGRAM} @{corpus_ref} (Apache-2.0, (c) Amazon.com, Inc. or its affiliates)  ·  "
        "Java: GitGalaxy det translator  ·  numbers: evidence report, det-mutation ledgers"
    )
    need(f_tiny.getlength(attribution) < W - 150, "attribution would run into the GitGalaxy mark")

    # ---------------------------------------------------------------- layout
    CX0, CX1 = 16, 770  # code column
    PC = (CX0, 78, CX1, 352)  # COBOL panel
    PJ = (CX0, 362, CX1, 636)  # Java panel
    LX0, LX1, LY0, LY1 = 782, 1264, 78, 636  # ladder panel
    LH, GUT = 17.8, 56
    CW = f_code.getlength("M")
    MAXC = int((CX1 - CX0 - GUT - 14) / CW)
    LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5"]
    RUNG_H = (LY1 - LY0 - 38) / 6

    def rung_box(lvl):
        k = 5 - LEVELS.index(lvl)  # L5 at the top
        y = LY0 + 34 + k * RUNG_H
        return (LX0 + 52, y + 2, LX1 - 12, y + RUNG_H - 2)

    def wrap(text, fnt, width):
        out, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if fnt.getlength(t) <= width:
                cur = t
            else:
                out.append(cur)
                cur = w
        return out + [cur]

    def fit(text, fnt, width):
        if fnt.getlength(text) <= width:
            return text
        while fnt.getlength(text + "…") > width:
            text = text[:-1]
        return text + "…"

    legend = [("COBOL source", C_COBOL), ("det-translated Java", C_JAVA), ("level held", C_HELD), ("mutant", C_MUT)]
    title_bar = "COUSR01C (CardDemo, add user): COBOL to Java"

    def chrome(d, status=None):
        d.rectangle((0, 0, W, H), fill=BG)
        d.rounded_rectangle((16, 12, W - 16, 66), 12, fill=BAR)
        d.text((34, 26), title_bar, font=f_bar, fill=INK)
        x0 = W - 16 - sum(int(f_leg.getlength(t)) + 50 for t, _ in legend) - 4
        need(x0 > 34 + f_bar.getlength(title_bar) + 20, "legend collides with the title")
        for t, cl in legend:
            d.rounded_rectangle((x0, 29, x0 + 20, 49), 5, fill=cl)
            d.text((x0 + 28, 27), t, font=f_leg, fill=INK)
            x0 += int(f_leg.getlength(t)) + 50
        d.rounded_rectangle((16, H - 76, W - 16, H - 22), 12, fill=BAR)
        if status:
            s1, s2 = status
            need(f_stat.getlength(s1) <= W - 80 and f_stat2.getlength(s2) <= W - 80, f"status too long: {s1} / {s2}")
            d.text((34, H - 70), s1, font=f_stat, fill=INK)
            if s2:
                d.text((34, H - 45), s2, font=f_stat2, fill=INK2)
        d.text((18, H - 17), attribution, font=f_tiny, fill=MUTED)

    def panel(d, box, label, sub, colour):
        x0, y0, x1, _ = box
        d.rounded_rectangle(box, 12, fill=TERM, outline=LINE)
        d.rounded_rectangle((x0, y0, x1, y0 + 30), 12, fill=BAR)
        d.rectangle((x0, y0 + 18, x1, y0 + 30), fill=BAR)
        for i, cl in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse((x0 + 14 + i * 20, y0 + 10, x0 + 25 + i * 20, y0 + 21), fill=cl)
        d.rounded_rectangle((x0 + 84, y0 + 9, x0 + 98, y0 + 23), 3, fill=colour)
        d.text((x0 + 106, y0 + 6), label, font=f_hdr, fill=INK)
        d.text((x1 - 14, y0 + 6), sub, font=f_hdr, fill=MUTED, anchor="ra")

    def line_y(box, i):
        return box[1] + 38 + i * LH

    def code(d, box, rows, n, colour, hl=(), dim=False, strike=None):
        for i, (no, t) in enumerate(rows[:n]):
            y = line_y(box, i)
            on = i in hl
            if on:
                d.rounded_rectangle((box[0] + GUT - 6, y - 2, box[2] - 10, y + LH - 3), 4, fill=colour + (60,))
                d.rectangle((box[0] + GUT - 6, y - 2, box[0] + GUT - 3, y + LH - 3), fill=colour)
            d.text((box[0] + 10, y + 1), f"{no:>5}", font=f_gut, fill=(110, 111, 122) if not on else colour)
            txt = t if len(t) <= MAXC else t[: MAXC - 1] + "…"
            fill = INK if (on or not dim) else (150, 150, 146)
            if t.lstrip().startswith(("//", "/**")) and box is PJ:
                fill = (125, 160, 125) if not dim or on else (100, 118, 100)
            d.text((box[0] + GUT, y), txt, font=f_code, fill=fill)

    def ladder(d, upto, glow=None, glow_t=1.0):
        """upto: index of the highest lit level (-1 none); glow: level being lit now, glow_t 0..1"""
        d.rounded_rectangle((LX0, LY0, LX1, LY1), 12, fill=(22, 23, 30), outline=LINE)
        d.text((LX0 + 16, LY0 + 11), "evidence ladder", font=f_lhdr, fill=INK)
        d.text((LX1 - 16, LY0 + 12), "levels are cumulative", font=f_cond, fill=MUTED, anchor="ra")
        rx = LX0 + 28
        ybot = rung_box("L0")[3] - RUNG_H / 2 + 3
        ytop = rung_box("L5")[1] + RUNG_H / 2 - 3
        d.line((rx, ytop, rx, ybot), fill=C_OFF, width=6)
        if upto >= 0 or glow:
            hi = upto + (glow_t if glow else 0)
            yh = ybot - (ybot - ytop) * min(hi, 5) / 5
            d.line((rx, ybot, rx, yh), fill=C_HELD, width=6)
        for j, lvl in enumerate(LEVELS):
            b = rung_box(lvl)
            cy = (b[1] + b[3]) / 2
            held = j <= upto or (glow == lvl and glow_t >= 1)
            lighting = glow == lvl
            a = 1.0 if held else (glow_t if lighting else 0.0)
            node = tuple(int(C_OFF[k] + (C_HELD[k] - C_OFF[k]) * a) for k in range(3))
            d.ellipse((rx - 11, cy - 11, rx + 11, cy + 11), fill=node, outline=BG, width=2)
            d.line((rx + 11, cy, b[0], cy), fill=node, width=2)
            fill_bg = (30, 52, 46) if a >= 1 else (28, 29, 36)
            d.rounded_rectangle(b, 9, fill=fill_bg, outline=node if a > 0 else LINE, width=2 if a > 0 else 1)
            name_col = INK if a > 0 else (120, 121, 128)
            d.text((b[0] + 12, b[1] + 6), lvl, font=f_badge, fill=C_HELD if a > 0 else (120, 121, 128))
            d.text((b[0] + 50, b[1] + 8), lv[lvl], font=f_rname, fill=name_col)
            cl = wrap("the program " + COND[lvl], f_cond, b[2] - b[0] - 24)
            need(len(cl) <= 2, f"{lvl} condition needs {len(cl)} lines")
            for k, t in enumerate(cl):
                d.text((b[0] + 12, b[1] + 31 + k * 14), t, font=f_cond, fill=INK2 if a > 0 else DIM)
            if a > 0:
                ea = int(255 * min(1, a))
                need(f_ev.getlength(EVID[lvl]) <= b[2] - b[0] - 24, f"{lvl} evidence does not fit")
                ev = EVID[lvl]
                d.text((b[0] + 12, b[3] - 23), ev, font=f_ev, fill=C_HELD + (ea,))

    def frame(n_c, n_j, status, upto=-1, glow=None, glow_t=1.0, hl_c=(), hl_j=(), dim=False, strike=None, tag=None):
        im = Image.new("RGBA", (W, H), BG)
        d = ImageDraw.Draw(im)
        chrome(d, status)
        panel(d, PC, "COUSR01C.cbl  ·  COBOL (CardDemo)", f"WRITE-USER-SEC-FILE  ·  lines {cobol[0][0]}-{cobol[-1][0]}",
              C_COBOL)  # fmt: skip
        panel(d, PJ, "Cousr01cService.java  ·  det port", "deterministic translation, by rule, no model", C_JAVA)
        ladder(d, upto, glow, glow_t)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        code(od, PC, cobol, n_c, C_COBOL, hl_c, dim)
        code(od, PJ, java, n_j, C_JAVA, hl_j, dim, strike)
        if strike is not None:  # the mutant replaces the line in place
            i, txt = strike
            y = line_y(PJ, i)
            bx = (PJ[0] + GUT - 6, y - 2, PJ[2] - 10, y + LH - 3)
            od.rounded_rectangle(bx, 4, fill=(60, 24, 26, 255), outline=C_MUT)
            od.text((PJ[0] + GUT, y), fit(txt, f_code, bx[2] - bx[0] - 12), font=f_code, fill=(255, 190, 186))
        if tag:
            tx, ty = PJ[2] - 14, PJ[1] + 40
            tw = f_stat2.getlength(tag) + 20
            od.rounded_rectangle((tx - tw, ty - 4, tx, ty + 22), 6, fill=(34, 35, 42, 235), outline=C_JAVA)
            od.text((tx - 10, ty), tag, font=f_stat2, fill=INK, anchor="ra")
        return Image.alpha_composite(im, ov)

    # ---------------------------------------------------------------- timeline
    fr = []
    for i in range(0):  # no intro title card (owner 2026-11-07)
        im = Image.new("RGBA", (W, H), BG)
        d = ImageDraw.Draw(im)
        al = int(255 * min(1, i / 8))
        d.text((W // 2, 286), "From COBOL to Java, level by level", font=f_title, fill=INK + (al,), anchor="mm")
        d.text(
            (W // 2, 338),
            "one CardDemo program (COUSR01C, add user) · deterministic translation, no model",
            font=f_sub,
            fill=INK2 + (al,),
            anchor="mm",
        )
        d.text(
            (W // 2, 370),
            "and its real evidence record, L0 to L5, numbers from the published evidence report",
            font=f_sub,
            fill=INK2 + (al,),
            anchor="mm",
        )
        d.text((W // 2, 420), "a burned (development) estate · the oracle is GnuCOBOL + CICS models, not z/OS",
               font=f_stat2, fill=MUTED + (al,), anchor="mm")  # fmt: skip
        fr.append(im)
    s_cobol = ("COBOL: the paragraph that writes the new user to the USRSEC file and checks the CICS response", "")
    for n in range(1, len(cobol) + 1):
        fr += [frame(n, 0, s_cobol)] * 2
    fr += [frame(len(cobol), 0, s_cobol)] * 8
    s_java = (
        "Java: written by the det translator, by rule, statement for statement; no model is involved",
        "each COBOL statement is kept above its Java as a comment",
    )
    for n in range(1, len(java) + 1):
        fr += [frame(len(cobol), n, s_java)] * 2
    fr += [frame(len(cobol), len(java), s_java)] * 6
    for hc, hj, what in PAIRS:
        st = (f"COBOL → Java: {what}", "")
        fr += [frame(len(cobol), len(java), st, hl_c=hc, hl_j=hj, dim=True)] * 9
    NC, NJ = len(cobol), len(java)
    for j, lvl in enumerate(LEVELS):
        hl_c, hl_j = (), ()
        if lvl == "L1":
            hl_j = tuple(range(NJ))
        elif lvl == "L3":
            hl_c, hl_j = (0,), (0, 1)
        elif lvl == "L4":
            hl_c, hl_j = (6, 8, 9), (7, 10)
        for t in range(7):
            fr.append(frame(NC, NJ, STATUS[lvl], upto=j - 1, glow=lvl, glow_t=(t + 1) / 7, hl_c=hl_c, hl_j=hl_j,
                            dim=bool(hl_c or hl_j)))  # fmt: skip
        fr += [frame(NC, NJ, STATUS[lvl], upto=j, hl_c=hl_c, hl_j=hl_j, dim=bool(hl_c or hl_j))] * 17
        if lvl == "L5":
            mi = next(i for i, (no, _) in enumerate(java) if no == ex["line"])
            ind = java[mi][1][: len(java[mi][1]) - len(java[mi][1].lstrip())]
            st = (
                f"one survivor, {ex['id']}: deleting the EIBRESP store changes nothing the program shows",
                f"verdict `{ex['verdict']}`: COUSR01C never reads EIBRESP (det_mutation_survivors/{CASE}.json)",
            )
            st0 = (
                f"mutation: the det port is changed one line at a time and the scenarios re-run "
                f"({m['mutants']:,} mutants)",
                f"a mutant the scenarios do not catch must be accounted for; this one is {ex['id']}, on line {ex['line']}",
            )
            tag = f"mutant {ex['id']} · {ex['op']}"
            for _ in range(14):
                fr.append(frame(NC, NJ, st0, upto=j, hl_j=(mi,), dim=True, tag=tag))
            for _ in range(34):
                fr.append(frame(NC, NJ, st, upto=j, hl_j=(mi,), dim=True, strike=(mi, ind + ex["after"].strip()),
                                tag=tag))  # fmt: skip
    fin = frame(NC, NJ, FINAL, upto=5)
    fr += [fin] * 48

    # ---------------------------------------------------------------- encode
    out = pathlib.Path(a.out)
    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-frames-"))
    for i, im in enumerate(fr):
        brand(im).convert("RGB").save(fdir / f"f{i:04d}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fdir / "f%04d.png")]
    subprocess.run(enc + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out) + ".mp4"], check=True)
    pal = (
        "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:diff_mode=rectangle"
    )
    subprocess.run(enc + ["-vf", pal, str(out) + ".gif"], check=True)
    shutil.copy(fdir / f"f{len(fr) - 1:04d}.png", str(out) + ".png")
    if a.keep_frames:
        print(f"frames kept in {fdir}")
    else:
        shutil.rmtree(fdir, ignore_errors=True)
    print(f"{out}: {len(fr)} frames ({len(fr) / FPS:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
