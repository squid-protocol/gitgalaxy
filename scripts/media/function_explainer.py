#!/usr/bin/env python3
"""Render "What GitGalaxy reads in a function" from REAL engine output.

Scans one source file with this checkout's engine, takes the named function's row from the scan DB, locates every
keyword-rule match the engine counted (the engine's own per-language rules, comments excluded), and animates it: the
code, the detected language, each signal family lighting up and flowing into a function record, a size/comment pass,
and the presence fingerprint. The highlighted tokens are checked against the DB counts; a mismatch aborts.

    python scripts/media/function_explainer.py --file gitgalaxy/core/aperture.py --function _has_generator_banner \\
        --label "GitGalaxy · aperture.py" --out docs/media/function-python [--above 1]

Needs Pillow and ffmpeg (docs tooling only; not an engine dependency).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # scripts/media helpers
from _brand import brand  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

W, H, FPS = 1280, 720, 12
FONT_DIR = pathlib.Path("/usr/share/fonts/truetype/dejavu")
f_code = ImageFont.truetype(str(FONT_DIR / "DejaVuSansMono.ttf"), 17)
f_tiny = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 12)
f_small = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 15)
f_lab = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 16)
f_labb = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 16)
f_big = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 22)
f_leg = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 19)  # record-panel legend rows
f_legc = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 13)
f_cnt = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 28)
f_sec = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 15)
f_title = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 38)
f_headline = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 26)  # constant title on every frame
f_sub = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 20)
BG, PANEL, TERM, BAR = (15, 17, 23), (26, 26, 25), (20, 21, 26), (34, 35, 42)
INK, INK2, MUTED, LINE = (240, 239, 236), (195, 194, 183), (143, 142, 134), (60, 61, 70)
# Fixed family -> colour (validated dark-mode categorical palette, 8 slots); every family is also labelled by name.
ORDER = [
    "struct_func_start",
    "struct_branch",
    "struct_linear",
    "state_pointers",
    "state_flux",
    "arch_api",
    "def_safety",
    "def_encapsulation",
    "state_bailout_hits",
    "state_cast_hits",
    "struct_closures",
    "struct_decorators",
    "state_safety_neg",
    "arch_io",
    "def_freeze_hits",
    "struct_generics",
    "struct_class_start",
]
PALETTE = {
    "struct_func_start": "#3987e5",
    "struct_branch": "#d95926",
    "struct_linear": "#9085e9",
    "state_pointers": "#199e70",
    "state_flux": "#c98500",
    "arch_api": "#d55181",
    "def_safety": "#008300",
    "def_encapsulation": "#e66767",
}
OTHER = "#76756f"
RULE = {}  # column -> engine rule key, filled from RecordKeeper.SHORT_KEY_MAP
# Common function-level keyword signals: the presence grid shown at the end (27 columns of function_data).
FINGERPRINT = [
    "arch_api",
    "arch_concurrency",
    "arch_globals",
    "arch_io",
    "arch_regex",
    "arch_ui_framework",
    "bitwise_ops",
    "def_encapsulation",
    "def_freeze_hits",
    "def_safety",
    "def_test",
    "state_bailout_hits",
    "state_cast_hits",
    "state_flux",
    "state_heat_triggers",
    "state_memory_alloc",
    "state_pointers",
    "state_print_hits",
    "state_safety_neg",
    "struct_args",
    "struct_branch",
    "struct_class_start",
    "struct_closures",
    "struct_decorators",
    "struct_func_start",
    "struct_generics",
    "struct_linear",
]


def rgb(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def scan(path: pathlib.Path, function: str):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gg-media-"))
    (tmp / "src").mkdir()
    shutil.copy(path, tmp / "src" / path.name)
    env = {
        "PYTHONPATH": str(ROOT),
        "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER",
        "GITGALAXY_DISABLE_GIT_HISTORY": "1",
        "PATH": "/usr/bin:/bin",
    }
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(tmp / "src"), "--output", str(tmp / "out") + "/"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    db = next((tmp / "out").glob("*_galaxy_master.db"))
    con = sqlite3.connect(db)
    cols = [c[1] for c in con.execute("PRAGMA table_info(function_data)")]
    row = con.execute(
        "SELECT f.*, fd.language FROM function_data f JOIN file_data fd ON f.file_id = fd.id "
        "WHERE f.func_name = ? ORDER BY f.loc DESC LIMIT 1",
        (function,),
    ).fetchone()
    con.close()
    shutil.rmtree(tmp, ignore_errors=True)
    if row is None:
        sys.exit(f"{function} not found in the scan of {path}")
    return dict(zip(cols + ["language"], row))


def locate(lines, fn_offset, language, row):
    """Engine rule matches inside the function (comments excluded), per signal column present in the row."""
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.recorders.record_keeper import RecordKeeper
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as LD

    RULE.update({v: k for k, v in RecordKeeper().SHORT_KEY_MAP.items()})
    text = "\n".join(lines)
    pos = Prism(LEXICAL_FAMILY_HEURISTICS, LD).split_positional_comment_stream(text, language).split("\n")
    # The positional comment stream keeps LINE positions but not columns (comment text is moved to column 0), so
    # each comment is re-anchored at its text's position in the original line.
    cmask, comments = [], []
    for i, ln in enumerate(lines):
        c = (pos[i] if i < len(pos) else "").strip()
        row_mask = [False] * len(ln)
        if c:
            k = ln.rfind(c[:40])
            k = k if k >= 0 else len(ln) - len(ln.lstrip())
            end = min(len(ln), k + len(c))
            for j in range(k, end):
                row_mask[j] = True
            comments.append([i, k, end])
        cmask.append(row_mask)
    body = "\n".join(lines[fn_offset:])
    offs = [0]
    for ln in lines[fn_offset:]:
        offs.append(offs[-1] + len(ln) + 1)

    def at(o):
        li = max(i for i in range(len(offs) - 1) if offs[i] <= o)
        return li + fn_offset, o - offs[li]

    name = row["func_name"].split(".")[-1].split("::")[-1]
    rules = LD[language]["rules"]
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LD)
    code = prism.split_streams(body, language)["code_stream"]  # what the engine matches against
    masked = [False] * len(body)  # comments + docstrings / long strings in the original
    for i, ln in enumerate(lines[fn_offset:]):
        for c, on in enumerate(cmask[i + fn_offset]):
            if on and offs[i] + c < len(masked):
                masked[offs[i] + c] = True
    if language == "python":
        for m in re.finditer(r'("""|\'\'\')[\s\S]*?\1', body):
            for k in range(*m.span()):
                masked[k] = True

    def place(token, cursor):
        """the next unmasked occurrence of a code-stream match in the original body"""
        k = body.find(token, cursor)
        while k >= 0 and any(masked[k : k + len(token)]):
            k = body.find(token, k + 1)
        return k

    out = {}
    for col in ORDER + ["struct_args"]:
        if not row.get(col) or RULE.get(col) not in rules:
            continue
        spans = []
        cursor = 0
        for m in rules[RULE[col]].finditer(code):
            g = m.group(0).strip()
            if not g:
                continue
            k = place(g, cursor)
            if k < 0:
                continue
            cursor = k + len(g)
            s, e = k, k + len(g)
            if col in ("struct_func_start", "struct_args") and name in g:
                k = g.find(name)
                s, e = (s + k, s + k + len(name)) if col == "struct_func_start" else (s + k, e)
            elif col == "arch_api" and name in g and g.find(name) > 0:
                e = s + g.find(name)
            while s < e and body[s] in " \t\n":
                s += 1
            li, ci = at(s)
            li2, ci2 = at(max(e - 1, s))
            if li2 != li:
                ci2 = len(lines[li]) - 1
            spans.append([li, ci, ci2 + 1])
        out[col] = spans
    return out, comments


LANG_NAME = {
    "c": "C",
    "cpp": "C++",
    "python": "Python",
    "java": "Java",
    "cobol": "COBOL",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "rust": "Rust",
    "go": "Go",
    "csharp": "C#",
}


def render(lines, first_line, row, spans, comments, label, out, attribution):
    size = 17 if len(lines) <= 16 else max(11, int(17 * 16 / len(lines)))
    fc = ImageFont.truetype(str(FONT_DIR / "DejaVuSansMono.ttf"), size)
    X0, Y0, LH = 104, 118, int(round(27 * size / 17))
    CW = fc.getlength("M")
    MAXC = int((760 - X0) / CW)
    PX, PY0 = 812, 128
    n_rows = sum(1 for c in ORDER if c in spans and spans[c])
    ROWH = min(46, int(300 / max(n_rows, 1)))
    Y_SIZE = PY0 + n_rows * ROWH + 6  # size & comments band
    Y_FP = Y_SIZE + 58  # fingerprint band (never overlaps the size band)
    lang = row["language"]
    steps = [c for c in ORDER if c in spans and spans[c]]

    def box(li, c0, c1):
        c0, c1 = min(c0, MAXC), min(c1, MAXC)
        return (X0 + c0 * CW - 3, Y0 + li * LH - 3, X0 + c1 * CW + 3, Y0 + li * LH + LH - 6)

    def base(d, n, lang_a=0.0):
        d.rectangle((0, 0, W, H), fill=BG)
        d.text((W / 2, 25), "How GitGalaxy Reads a Function", font=f_headline, fill=INK, anchor="mm")
        d.rounded_rectangle((40, 50, 770, 560), 12, fill=TERM, outline=LINE)
        d.rounded_rectangle((40, 50, 770, 88), 12, fill=BAR)
        d.rectangle((40, 76, 770, 88), fill=BAR)
        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse((58 + i * 22, 62, 70 + i * 22, 74), fill=c)
        d.text((140, 60), label, font=f_small, fill=INK2)
        for i, ln in enumerate(lines[:n]):
            d.text((50, Y0 + i * LH), f"{first_line + i:>4}", font=fc, fill=(90, 91, 100))
            d.text((X0, Y0 + i * LH), ln.replace("\t", "    ")[:MAXC], font=fc, fill=INK)
        d.rounded_rectangle((790, 50, 1240, 560), 12, fill=PANEL, outline=LINE)
        d.text((812, 64), "function record", font=f_labb, fill=INK)
        d.text((812, 88), f"{row['func_name'][:28]}  @ line {row['start_line']}", font=f_code, fill=INK2)
        d.line((812, 118, 1218, 118), fill=LINE)
        d.rounded_rectangle((40, 584, 1240, 640), 10, fill=BAR)
        if lang_a > 0:
            a = int(255 * min(lang_a, 1))
            d.text((62, 600), "Language detected:", font=f_lab, fill=INK2 + (a,))
            d.text((232, 598), LANG_NAME.get(lang, lang), font=f_big, fill=(57, 135, 229, a))
        if attribution:
            d.text((40, 650), attribution, font=f_tiny, fill=MUTED)

    from gitgalaxy.standards.analysis_lens import signal_display_name

    nice = lambda c: re.sub(r"\s*\(.*\)$", "", signal_display_name(c))  # noqa: E731
    fr = []
    for i in range(0):  # no intro title card (owner 2026-11-07)
        im = Image.new("RGBA", (W, H), BG)
        d = ImageDraw.Draw(im)
        a = int(255 * min(1, i / 8))
        d.text((W // 2, 300), "What GitGalaxy reads in a function", font=f_title, fill=INK + (a,), anchor="mm")
        d.text(
            (W // 2, 352),
            f"real engine output · {LANG_NAME.get(lang, lang)} · structure only, names and comment text are not interpreted",
            font=f_sub,
            fill=INK2 + (a,),
            anchor="mm",
        )
        fr.append(im)
    for n in range(1, len(lines) + 1):
        for _ in range(2):
            im = Image.new("RGBA", (W, H), BG)
            base(ImageDraw.Draw(im), n)
            fr.append(im)
    for i in range(16):
        im = Image.new("RGBA", (W, H), BG)
        base(ImageDraw.Draw(im), len(lines), i / 6)
        fr.append(im)
    done_rows, done = [], []

    def scene(extra_ov=None, extra_rows=None):
        im = Image.new("RGBA", (W, H), BG)
        base(ImageDraw.Draw(im), len(lines), 1)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for sp, hue in done:
            od.rounded_rectangle(box(*sp), 4, fill=rgb(hue, 55))
        if extra_ov:
            extra_ov(od)
        im = Image.alpha_composite(im, ov)
        d = ImageDraw.Draw(im)
        for j, (lab, col, cnt, hue) in enumerate(done_rows + (extra_rows or [])):
            y = PY0 + j * ROWH
            d.rounded_rectangle((PX, y + 3, PX + 16, y + 23), 4, fill=rgb(hue))
            d.text((PX + 26, y), lab, font=f_leg, fill=INK)
            d.text((PX + 26, y + 23), col, font=f_legc, fill=MUTED)
            d.text((1218, y), str(cnt), font=f_cnt, fill=INK, anchor="ra")
        return im, d

    for col in steps:
        hue = PALETTE.get(col, OTHER)
        sp = spans[col]
        row_y = PY0 + len(done_rows) * ROWH
        lab = "Name · arguments" if col == "struct_func_start" else nice(col)
        cnt_final = (
            f"{row['struct_func_start']} · {row.get('struct_args', 0)}" if col == "struct_func_start" else row[col]
        )
        T = 10 + 3 * len(sp) + 12
        for t in range(T):
            shown = min(len(sp), max(0, (t - 4) // 3 + 1))

            def ov(od, shown=shown, t=t, T=T):
                for k in range(shown):
                    b = box(*sp[k])
                    od.rounded_rectangle(b, 4, fill=rgb(hue, 110), outline=rgb(hue), width=2)
                    if t < T - 4:
                        sx, sy, ex, ey = b[2], (b[1] + b[3]) / 2, PX - 6, row_y + 13
                        pts = [
                            (
                                (1 - u) ** 3 * sx
                                + 3 * (1 - u) ** 2 * u * (sx + (ex - sx) * 0.45)
                                + 3 * (1 - u) * u**2 * (sx + (ex - sx) * 0.55)
                                + u**3 * ex,
                                (1 - u) ** 3 * sy + 3 * (1 - u) ** 2 * u * sy + 3 * (1 - u) * u**2 * ey + u**3 * ey,
                            )
                            for u in [q / 24 for q in range(25)]
                        ]
                        od.line(pts, fill=rgb(hue, 150), width=2)

            cur = [(lab, col, shown if col != "struct_func_start" else cnt_final, hue)] if t >= 4 else []
            im, _ = scene(ov, cur)
            fr.append(im)
        done_rows.append((lab, col, cnt_final, hue))
        done += [(s, hue) for s in sp]

    def size_band(d, a=255):
        d.line((PX, Y_SIZE - 4, 1218, Y_SIZE - 4), fill=LINE)
        d.text((PX, Y_SIZE), "SIZE & COMMENTS", font=f_sec, fill=INK2 + (a,))
        doc = " · docstring" if row.get("docstring") else ""
        txt = (
            f"{row['loc']} lines · complexity {row.get('complexity', 0)} · {n_comment} comment"
            f"{'s' if n_comment != 1 else ''}{doc}"
        )
        d.text((PX, Y_SIZE + 22), txt, font=f_lab, fill=INK + (a,))

    fn_top = next(i for i in range(len(lines)) if any(s[0] == i for s in spans.get("struct_func_start", [])))
    n_comment = len(comments)
    for t in range(40):
        a = int(255 * min(1, t / 8))

        def ov(od, a=a):
            for li, c0, c1 in comments:
                b = box(li, c0, c1)
                for x in range(int(b[0]), int(b[2]), 10):
                    od.line((x, b[3], min(x + 5, b[2]), b[3]), fill=(200, 200, 190, a), width=2)
            top, bot = Y0 + fn_top * LH, Y0 + (len(lines) - 1) * LH + LH - 6
            od.line((96, top, 92, top, 92, bot, 96, bot), fill=INK2 + (a,), width=2)

        im, d = scene(ov)
        size_band(d, a)
        fr.append(im)
    present = [c for c in FINGERPRINT if row.get(c)]
    for t in range(70):

        def ov(od):
            for li, c0, c1 in comments:
                b = box(li, c0, c1)
                for x in range(int(b[0]), int(b[2]), 10):
                    od.line((x, b[3], min(x + 5, b[2]), b[3]), fill=(200, 200, 190), width=2)

        im, d = scene(ov)
        size_band(d)
        y = Y_FP
        d.line((PX, y - 4, 1218, y - 4), fill=LINE)
        d.text((PX, y), "FINGERPRINT · keyword families present", font=f_sec, fill=INK2)
        for j, c in enumerate(FINGERPRINT[: min(len(FINGERPRINT), t)]):
            x, yy = PX + (j % 14) * 29, y + 24 + (j // 14) * 27
            on = c in present
            d.rounded_rectangle((x, yy, x + 23, yy + 21), 4, fill=(57, 135, 229) if on else (48, 49, 56))
            d.text((x + 11, yy + 10), "1" if on else "0", font=f_tiny, fill=INK if on else MUTED, anchor="mm")
        if t > 30:
            a = int(255 * min(1, (t - 30) / 8))
            d.rounded_rectangle((40, 584, 1240, 640), 10, fill=BAR)
            ln_ = LANG_NAME.get(lang, lang)
            d.text((62, 600), ln_, font=f_big, fill=(57, 135, 229))
            d.text(
                (62 + f_big.getlength(ln_) + 14, 602),
                f"·  {len(present)} of {len(FINGERPRINT)} common keyword families present  ·  {row['loc']} lines  ·  "
                f"archetype: {row.get('func_archetype') or 'n/a'}",
                font=f_lab,
                fill=INK + (a,),
            )
        fr.append(im)
    fr += [fr[-1]] * 30
    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-frames-"))
    for i, im in enumerate(fr):
        brand(im).convert("RGB").save(fdir / f"f{i:04d}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            str(fdir / "f%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "20",
            str(out) + ".mp4",
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            str(fdir / "f%04d.png"),
            "-vf",
            "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer",
            str(out) + ".gif",
        ],
        check=True,
    )
    shutil.copy(fdir / f"f{len(fr) - 1:04d}.png", str(out) + ".png")
    shutil.rmtree(fdir, ignore_errors=True)
    return len(fr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--function", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--above", type=int, default=0, help="comment lines to show above the function")
    ap.add_argument("--attribution", default="")
    a = ap.parse_args()
    path = (ROOT / a.file) if not pathlib.Path(a.file).is_absolute() else pathlib.Path(a.file)
    row = scan(path, a.function)
    src = path.read_text(encoding="utf-8", errors="replace").split("\n")
    start = row["start_line"] - 1
    lines = src[start - a.above : start + row["loc"]]
    spans, comments = locate(lines, a.above, row["language"], row)
    for col, sp in spans.items():  # the animation must equal the engine's counts
        if col not in ("struct_func_start", "struct_args") and len(sp) != row[col]:
            sys.exit(f"{col}: located {len(sp)} matches but the engine counted {row[col]}; refusing to render")
    n = render(lines, start + 1 - a.above, row, spans, comments, a.label, pathlib.Path(a.out), a.attribution)
    print(f"{a.out}: {n} frames; signals {', '.join(f'{c} {len(s)}' for c, s in spans.items())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
