#!/usr/bin/env python3
"""Render "One game, many languages" from the DOOM port study's REAL published data.

Reads `docs/wiki/museum-of-code/doom-dna/data.json` (the data behind "DOOM's DNA", engine 6c7c6c1bc; the tables are in
`docs/research/doom-port-study.md` Appendix A). Every port's functions sit in the original (linuxdoom)'s 16 subsystems;
`ports[].lines` are the calls between them, `cross_wiring` is how closely the calls *between* subsystems match
linuxdoom's (cosine), `cross_null` is the same program with its functions shuffled between subsystems (chance), and
`gap` = cross_wiring - cross_null is the design that survived.

The animation: title, linuxdoom's wiring map, then five descendants beside it (a C fork, the Scheme and Go
translations, the Java and C# translations) with their score against chance, then the whole wiring table.

    python scripts/media/doom_explainer.py --out docs/media/doom-ports

Needs Pillow, numpy and ffmpeg (docs tooling only). No scan is run.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # scripts/media helpers
from _brand import brand  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/wiki/museum-of-code/doom-dna/data.json"
W, H, FPS = 1280, 720, 12
FD = pathlib.Path("/usr/share/fonts/truetype/dejavu")


def font(size, bold=False, mono=False):
    name = "DejaVuSansMono.ttf" if mono else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    return ImageFont.truetype(str(FD / name), size)


f_title, f_sub, f_bar, f_leg, f_stat = font(40, True), font(21), font(20, True), font(18), font(19)
f_node, f_panel, f_panel_s, f_row, f_rowb, f_num = (
    font(14),
    font(22, True),
    font(17),
    font(16),
    font(16, True),
    font(15),
)
INK, INK2, MUTED = (240, 239, 236), (195, 194, 183), (143, 142, 134)
# One colour per kind (same meanings as the other explainers): functions blue, calls red.
C_FN, C_CALL, C_GHOST, C_NULL = (96, 165, 250), (239, 83, 80), (150, 156, 178), (170, 172, 184)

LANG = {"c": "C", "scheme": "Scheme", "go": "Go", "dart": "Dart", "fortran": "Fortran", "java": "Java",
        "kotlin": "Kotlin", "csharp": "C#", "rust": "Rust"}  # fmt: skip
SHOWCASE = [  # (port, one-line reading of its numbers)
    ("chocolate-doom", "a C fork of the original (the sanity check)"),
    ("doom-scheme", "a translation to Scheme: every line rewritten"),
    ("gore", "a translation to Go: every line rewritten"),
    ("mochadoom", "a translation to Java"),
    ("managed-doom", "a translation to C#"),
]
TABLE = [  # the wiring table of "DOOM's DNA" (teardown-of-doom.md), same rows and order
    ("C copies", ["chocolate-doom", "crispy-doom", "doom-wasm"]),
    ("translations", ["doom-scheme", "gore", "dartdoom", "doomf77", "mochadoom", "kocoa-doom", "managed-doom"]),
    ("written from scratch", ["rust-doom", "room4doom", "helion"]),
    ("not DOOM", ["Quake II", "WinQuake", "Lua"]),
]
# Unrelated controls are not in data.json: cross wiring and cross null from doom-port-study.md Appendix H; the gap
# from the wiring table of teardown-of-doom.md (computed before rounding, so WinQuake reads -0.03, not -0.02).
CONTROLS = {"Quake II": ("C", 0.11, 0.09, 0.02), "WinQuake": ("C", 0.05, 0.07, -0.03), "Lua": ("C", 0.00, 0.00, 0.00)}


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def make_sky():
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2).clip(0, 1)
    sky = np.stack([14 - 10 * rr, 20 - 14 * rr, 48 - 32 * rr, np.full_like(rr, 255)], -1).astype(np.uint8)
    im = Image.fromarray(sky, "RGBA")
    sd = ImageDraw.Draw(im)
    srng = np.random.default_rng(11)
    for _ in range(220):
        x, y, b = srng.uniform(0, W), srng.uniform(0, H), int(srng.uniform(50, 130))
        sd.point((x, y), fill=(b, b, min(255, b + 30), 255))
    return im


SKY = make_sky()
BAR = (10, 14, 32, 215)


def undirected_cross(lines):
    """Calls between two different subsystems, both directions summed, as shares of the program's cross calls."""
    acc = {}
    for ln in lines:
        if ln["from"] == ln["to"]:
            continue
        k = tuple(sorted((ln["from"], ln["to"])))
        acc[k] = acc.get(k, 0) + ln["calls"]
    tot = sum(acc.values()) or 1
    return {k: v / tot for k, v in acc.items()}, sum(acc.values())


def chrome(im, title, legend, stats, stats2=""):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 12, W - 16, 66), 12, fill=BAR)
    d.text((34, 26), title, font=f_bar, fill=INK)
    x0 = W - 16 - sum(int(f_leg.getlength(t)) + 50 for t, _, _ in legend) - 8
    assert 34 + f_bar.getlength(title) + 24 < x0, f"title collides with legend: {title!r}"
    for t, col, kind in legend:
        if kind == "dot":
            d.ellipse((x0, 29, x0 + 20, 49), fill=col)
        elif kind == "ring":
            d.ellipse((x0, 29, x0 + 20, 49), outline=col, width=3)
        elif kind == "dash":
            for k in range(0, 20, 6):
                d.line((x0 + k, 39, x0 + k + 3, 39), fill=col, width=4)
        else:
            d.rounded_rectangle((x0, 35, x0 + 20, 43), 3, fill=col)
        d.text((x0 + 28, 27), t, font=f_leg, fill=INK)
        x0 += int(f_leg.getlength(t)) + 50
    top = H - 74 if not stats2 else H - 98
    d.rounded_rectangle((16, top, W - 16, H - 26), 12, fill=BAR)
    if stats:
        d.text((34, top + 12), stats, font=f_stat, fill=INK)
    if stats2:
        d.text((34, top + 40), stats2, font=f_stat, fill=INK2)
    d.text(
        (18, H - 20),
        "Data: docs/wiki/museum-of-code/doom-dna/data.json (DOOM's DNA, GitGalaxy 6c7c6c1bc) · measurements only, no source shown",
        font=font(11),
        fill=MUTED,
    )
    return im


class MapPainter:
    """Draws one program's wiring map on linuxdoom's 16 subsystem positions."""

    def __init__(self, subsystems):
        self.pos = {s["name"]: (s["x"], s["y"]) for s in subsystems}

    def draw(self, im, box, port, ghost=None, edge_frac=1.0, alpha=255, labels=True, min_share=0.006):
        x0, y0, x1, y1 = box
        T = lambda n: (x0 + self.pos[n][0] * (x1 - x0), y0 + self.pos[n][1] * (y1 - y0))  # noqa: E731
        scale = (x1 - x0) / 600
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        if ghost:
            gs, _ = undirected_cross(ghost["lines"])
            for (a, b), sh in gs.items():
                if sh < min_share:
                    continue
                p, q = T(a), T(b)
                w = max(1, int(round((1 + 60 * sh) * scale)))
                n = max(2, int(math.hypot(q[0] - p[0], q[1] - p[1]) / 9))
                for k in range(0, n, 2):  # dashed: the original's wiring, for comparison
                    a0, a1 = k / n, min(1, (k + 1) / n)
                    d.line(
                        (p[0] + (q[0] - p[0]) * a0, p[1] + (q[1] - p[1]) * a0,
                         p[0] + (q[0] - p[0]) * a1, p[1] + (q[1] - p[1]) * a1),
                        fill=C_GHOST + (int(150 * alpha / 255),), width=w,
                    )  # fmt: skip
        shares, _ = undirected_cross(port["lines"])
        ordered = sorted(((k, v) for k, v in shares.items() if v >= min_share), key=lambda kv: -kv[1])
        shown = ordered[: int(math.ceil(len(ordered) * edge_frac))]
        lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lines)
        for (a, b), sh in shown:
            p, q = T(a), T(b)
            w = max(1, int(round((1 + 60 * sh) * scale)))
            dl.line((p, q), fill=C_CALL + (int(min(255, 90 + 2400 * sh) * alpha / 255),), width=w)
        glow = lines.filter(ImageFilter.GaussianBlur(4))
        layer = Image.alpha_composite(layer, glow)
        layer = Image.alpha_composite(layer, lines)
        d = ImageDraw.Draw(layer)
        fn = {k: v["functions"] for k, v in port["stations"].items()}
        tot = sum(fn.values()) or 1
        placed = []
        for name in self.pos:
            x, y = T(name)
            r = (5 + 70 * math.sqrt(fn.get(name, 0) / tot)) * scale
            d.ellipse((x - r, y - r, x + r, y + r), fill=C_FN + (int(220 * alpha / 255),),
                      outline=(200, 225, 255, int(230 * alpha / 255)), width=2)  # fmt: skip
            placed.append((name, x, y, r))
        for name, x, y, r in placed if labels else []:  # labels last, with a dark halo, so nothing hides them
            d.text((x, y + r + 3), name, font=f_node, fill=INK2 + (int(240 * alpha / 255),), anchor="ma",
                   stroke_width=3, stroke_fill=(6, 9, 22, int(230 * alpha / 255)))  # fmt: skip
        return Image.alpha_composite(im, layer)


def meter(im, box, cw, cn, frac=1.0, label=True):
    """0-1 axis: hollow = same program shuffled (chance), filled = wiring match, bar between = the design kept."""
    x0, y, x1 = box
    d = ImageDraw.Draw(im)
    X = lambda v: x0 + v * (x1 - x0)  # noqa: E731
    d.line((x0, y, x1, y), fill=(70, 74, 92), width=2)
    for v in (0, 0.5, 1):
        d.line((X(v), y - 5, X(v), y + 5), fill=(90, 94, 112), width=2)
        d.text((X(v), y + 10), f"{v:g}", font=f_num, fill=MUTED, anchor="ma")
    cur = cn + (cw - cn) * frac
    if abs(cur - cn) > 0.003:
        d.line((X(cn), y, X(cur), y), fill=C_CALL + (200,), width=6)
    d.ellipse((X(cn) - 9, y - 9, X(cn) + 9, y + 9), outline=C_NULL, width=3)
    d.ellipse((X(cur) - 9, y - 9, X(cur) + 9, y + 9), fill=C_CALL)
    if label and frac >= 1:
        g = cw - cn
        txt = f"{g:+.2f} kept" if g > 0.05 else f"{g:+.2f}: none kept"
        d.text((x1 + 18, y - 11), txt, font=f_rowb, fill=INK)


LEG_MAP = [("a part of the game (size = functions)", C_FN, "dot"), ("calls between parts", C_CALL, "bar")]
LEG_CMP = [("part (size = functions)", C_FN, "dot"), ("calls between parts", C_CALL, "bar"),
           ("original's calls", C_GHOST, "dash")]  # fmt: skip
LEG_SCORE = [("wiring match", C_CALL, "dot"), ("same program, shuffled (chance)", C_NULL, "ring")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = json.loads(DATA.read_text())
    ports = {p["name"]: p for p in data["ports"]}
    ref = ports[data["reference"]]
    mp = MapPainter(data["subsystems"])
    n_desc = len(data["ports"]) - 1
    _, ref_cross = undirected_cross(ref["lines"])
    ref_total = sum(ln["calls"] for ln in ref["lines"])
    frames: list[Image.Image] = []

    # 1. title
    for i in range(0):  # no intro title card (owner 2026-11-07)
        im = SKY.copy()
        d = ImageDraw.Draw(im)
        al = int(255 * min(1, i / 8))
        d.text((W // 2, 290), "One game, many languages", font=f_title, fill=INK + (al,), anchor="mm")
        d.text((W // 2, 345), f"DOOM's 1997 source and {n_desc} programs measured against it, in about twenty languages",
               font=f_sub, fill=INK2 + (al,), anchor="mm")  # fmt: skip
        d.text((W // 2, 380), f"scanned by one engine at one version ({data['engine']}): what survives a translation?",
               font=f_sub, fill=INK2 + (al,), anchor="mm")  # fmt: skip
        frames.append(im)

    # 2. the original's wiring map, full size
    big = (300, 100, 980, 600)
    t_ref = "The original: linuxdoom (C, 1997)"
    s_ref = (f"linuxdoom · {ref['functions']} functions in 16 parts · {ref_total:,} calls, "
             f"{ref_cross} of them between parts")  # fmt: skip
    for i in range(30):
        im = mp.draw(SKY.copy(), big, ref, edge_frac=ease(i / 24), alpha=int(255 * min(1, 0.3 + i / 10)))
        frames.append(chrome(im, t_ref, LEG_MAP, s_ref))
    frames += [frames[-1]] * 14

    # 3. shrink to the left panel
    left, right = (40, 120, 600, 560), (680, 120, 1240, 560)
    for i in range(12):
        u = ease(i / 11)
        box = tuple(big[k] * (1 - u) + left[k] * u for k in range(4))
        im = mp.draw(SKY.copy(), box, ref)
        frames.append(chrome(im, "Now put a descendant beside it", LEG_CMP, s_ref))

    def comparison(name, note, phase):
        """phase in [0, 1]: 0-0.5 draw the port's map, 0.5-1 slide its score from chance to its value."""
        p = ports[name]
        im = SKY.copy()
        d = ImageDraw.Draw(im)
        d.text((left[0] + 10, 84), "linuxdoom · C · the original", font=f_panel, fill=INK)
        lang = LANG.get(p["language"], p["language"])
        d.text((right[0] + 10, 84), f"{name} · {lang}", font=f_panel, fill=INK)
        im = mp.draw(im, left, ref)
        im = mp.draw(im, right, p, ghost=ref, edge_frac=ease(phase * 2), alpha=int(255 * min(1, 0.3 + phase * 4)))
        d = ImageDraw.Draw(im)
        d.line((640, 110, 640, 560), fill=(50, 54, 74), width=2)
        if phase >= 0.5:
            d.text((right[0] + 10, 572), "wiring match", font=f_rowb, fill=INK)
            meter(im, (right[0] + 140, 582, right[0] + 380), p["cross_wiring"], p["cross_null"],
                  frac=ease((phase - 0.5) * 2.2))  # fmt: skip
        stats = (f"{name}: {p['functions']:,} functions · wiring match {p['cross_wiring']:.2f} · "
                 f"shuffled {p['cross_null']:.2f} · design kept {p['gap']:+.2f}")  # fmt: skip
        title = "Same 16 parts: wired like the original?"
        return chrome(im, title, LEG_CMP, stats if phase >= 0.5 else f"{name}: {p['functions']:,} functions · {note}")

    for name, note in SHOWCASE:
        n = 34
        for i in range(n):
            frames.append(comparison(name, note, i / (n - 1)))
        frames += [frames[-1]] * 14

    # 4. the whole table
    rows = []
    for group, names in TABLE:
        for nm in names:
            if nm in CONTROLS:
                lg, cw, cn, gap = CONTROLS[nm]
            else:
                p = ports[nm]
                lg, cw, cn, gap = LANG[p["language"]], p["cross_wiring"], p["cross_null"], p["gap"]
            rows.append((group, nm, lg, cw, cn, gap))
    title4 = "Wiring match against chance: 16 programs, one engine"
    s4a = "Scheme and Go kept DOOM's wiring as far above chance as a C fork (+0.51, +0.50 vs +0.51)."
    s4b = "Java, Kotlin and C# kept none; rewrites from scratch and unrelated programs sit at chance."
    gy0, rh = 104, 27
    ax0, ax1 = 490, 1010

    def table_frame(k_rows, frac_last):
        im = SKY.copy()
        d = ImageDraw.Draw(im)
        X = lambda v: ax0 + v * (ax1 - ax0)  # noqa: E731
        y = gy0
        last_group = None
        ypos = []
        for group, *_ in rows:
            if group != last_group:
                y += 4 if last_group else 0
                last_group = group
            ypos.append(y)
            y += rh
        last_group = None
        for i, (group, nm, lg, cw, cn, gap) in enumerate(rows):
            yy = ypos[i]
            if group != last_group:
                d.text((40, yy - 2), group, font=f_rowb, fill=MUTED)
                if last_group:
                    d.line((40, yy - 4, ax1 + 200, yy - 4), fill=(44, 48, 66), width=1)
                last_group = group
            if i >= k_rows:
                continue
            d.text((240, yy), nm, font=f_rowb if group != "not DOOM" else f_row, fill=INK)
            d.text((ax0 - 14, yy), lg, font=f_row, fill=INK2, anchor="ra")
            cy = yy + 10
            d.line((ax0, cy, ax1, cy), fill=(44, 48, 66), width=1)
            fr = frac_last if i == k_rows - 1 else 1
            cur = cn + (cw - cn) * fr
            if abs(cur - cn) > 0.003:
                d.line((X(cn), cy, X(cur), cy), fill=C_CALL + (200,), width=5)
            d.ellipse((X(cn) - 7, cy - 7, X(cn) + 7, cy + 7), outline=C_NULL, width=2)
            d.ellipse((X(cur) - 7, cy - 7, X(cur) + 7, cy + 7), fill=C_CALL)
            if fr >= 1:
                g = gap
                d.text((ax1 + 40, yy), f"{g:+.2f}" if abs(g) >= 0.005 else "0.00", font=f_rowb if g > 0.15 else f_row,
                       fill=INK if g > 0.15 else INK2)  # fmt: skip
        yb = ypos[-1] + rh + 2
        for v in (0, 0.25, 0.5, 0.75, 1):
            d.line((X(v), gy0 - 4, X(v), yb - 6), fill=(40, 44, 62), width=1)
            d.text((X(v), yb - 4), f"{v:g}", font=f_num, fill=MUTED, anchor="ma")
        d.text((ax1 + 40, gy0 - 24), "kept", font=f_row, fill=MUTED)
        d.text((ax0, gy0 - 24), "wiring match of the calls between parts, 0 to 1", font=f_row, fill=MUTED)
        return chrome(im, title4, LEG_SCORE, s4a if k_rows >= 8 else "", s4b if k_rows >= len(rows) else "")

    for k in range(1, len(rows) + 1):
        for j in range(4):
            frames.append(table_frame(k, (j + 1) / 4))
    final = table_frame(len(rows), 1)
    frames += [final] * 60

    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-doom-"))
    for i, im in enumerate(frames):
        brand(im).convert("RGB").save(fdir / f"f{i:04d}.png")
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fdir / "f%04d.png")]
    subprocess.run(ff + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out) + ".mp4"], check=True)
    subprocess.run(
        ff
        + [
            "-vf",
            "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
            "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
            str(out) + ".gif",
        ],
        check=True,
    )
    brand(final).convert("RGB").save(str(out) + ".png")
    keep = pathlib.Path(tempfile.gettempdir()) / "gg-doom-frames"
    shutil.rmtree(keep, ignore_errors=True)
    shutil.move(str(fdir), keep)  # kept for frame review
    print(f"{out}: {len(frames)} frames ({len(frames) / FPS:.1f} s); frames in {keep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
