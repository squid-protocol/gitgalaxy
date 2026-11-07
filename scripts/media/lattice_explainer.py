#!/usr/bin/env python3
"""Render "How function shapes are built" from the REAL population fingerprint lattice.

A function's fingerprint is a column of Yes/No: which keyword families it contains. The animation builds a real chain
from the growth tree one family at a time (each step is a real shape with its real function count and level), then
reveals the whole lattice of the 200 commonest shapes around it.

Data: temporal-crucible docs/fingerprint_trees_exploratory.json (the 200 commonest exact shapes of 6,936,799 functions,
v2.12.0 population scan, with growth-tree parents).

    python scripts/media/lattice_explainer.py --trees <fingerprint_trees_exploratory.json> --chain-end 26 --out docs/media/lattice

Needs Pillow, numpy and ffmpeg (docs tooling only).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
W, H, FPS = 1280, 720, 12
FD = pathlib.Path("/usr/share/fonts/truetype/dejavu")
F = {
    k: ImageFont.truetype(str(FD / f), s)
    for k, f, s in (
        ("title", "DejaVuSans-Bold.ttf", 38),
        ("sub", "DejaVuSans.ttf", 20),
        ("bar", "DejaVuSans-Bold.ttf", 20),
        ("leg", "DejaVuSans.ttf", 18),
        ("stat", "DejaVuSans.ttf", 18),
        ("row", "DejaVuSans.ttf", 13),
        ("cell", "DejaVuSans-Bold.ttf", 12),
        ("dot", "DejaVuSans-Bold.ttf", 15),
        ("dots", "DejaVuSans.ttf", 13),
        ("axis", "DejaVuSans.ttf", 13),
        ("tiny", "DejaVuSans.ttf", 11),
    )
}
INK, INK2, MUTED = (240, 239, 236), (195, 194, 183), (143, 142, 134)
YES, NO, DOT, LINK, OTHER = (59, 130, 246), (44, 47, 60), (96, 165, 250), (230, 232, 240), (95, 105, 140)
FAMILIES = [
    "struct_func_start",
    "struct_linear",
    "struct_args",
    "arch_api",
    "state_flux",
    "struct_branch",
    "state_pointers",
    "struct_class_start",
    "def_encapsulation",
    "def_safety",
    "def_test",
    "state_bailout_hits",
    "state_cast_hits",
    "def_freeze_hits",
    "struct_generics",
    "struct_closures",
    "struct_decorators",
    "arch_io",
    "arch_concurrency",
    "arch_globals",
    "arch_regex",
    "arch_ui_framework",
    "bitwise_ops",
    "state_heat_triggers",
    "state_memory_alloc",
    "state_print_hits",
    "state_safety_neg",
]


def sky():
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2).clip(0, 1)
    im = Image.fromarray(
        np.stack([14 - 10 * rr, 20 - 14 * rr, 48 - 32 * rr, np.full_like(rr, 255)], -1).astype(np.uint8), "RGBA"
    )
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(11)
    for _ in range(260):
        b = int(r.uniform(40, 110))
        d.point((r.uniform(0, W), r.uniform(0, H)), fill=(b, b, min(255, b + 30), 255))
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", required=True)
    ap.add_argument("--chain-end", type=int, default=26, help="rank of the shape the chain ends at")
    ap.add_argument(
        "--chain-start", type=int, default=14, help="rank of the first dot (declaration + structural keywords)"
    )
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from gitgalaxy.standards.analysis_lens import signal_display_name

    nice = {c: re.sub(r"\s*\(.*\)$", "", signal_display_name(c)) for c in FAMILIES}
    nice["struct_func_start"] = "Function declaration"
    D = json.loads(pathlib.Path(a.trees).read_text())
    shapes = D["shapes"]
    by = {s["rank"]: s for s in shapes}
    chain, r = [], a.chain_end
    while r:
        chain.append(by[r])
        if r == a.chain_start:
            break
        r = by[r]["parent"]
    chain = chain[::-1]
    if chain[0]["rank"] != a.chain_start:
        sys.exit("chain-start is not an ancestor of chain-end")
    for x, y in zip(chain, chain[1:]):
        if len(set(y["signals"]) - set(x["signals"])) != 1 or not set(x["signals"]) <= set(y["signals"]):
            sys.exit(f"step {x['rank']} -> {y['rank']} is not a one-family step; refusing")
    # tidy tree layout of the 200 shapes: x = level (families present), y = DFS leaf order
    kids, roots = defaultdict(list), []
    for s in shapes:
        (kids[s["parent"]] if s["parent"] else roots).append(s["rank"])
    ypos, nxt = {}, [0]

    def place(rk):
        ch = sorted(kids[rk], key=lambda j: -by[j]["n"])
        for c in ch:
            place(c)
        ypos[rk] = float(np.mean([ypos[c] for c in ch])) if ch else nxt[0]
        if not ch:
            nxt[0] += 1

    for rt in roots:
        place(rt)
    kmax = max(len(s["signals"]) for s in shapes)
    AX = (540, 140, W - 70, H - 150)

    def xy(rk):
        s = by[rk]
        x = AX[0] + len(s["signals"]) / kmax * (AX[2] - AX[0])
        y = AX[1] + ypos[rk] / max(nxt[0] - 1, 1) * (AX[3] - AX[1])
        return x, y

    maxn = max(s["n"] for s in shapes)

    def rad(n):
        return 3 + 15 * (n / maxn) ** 0.5

    SKY = sky()
    ROW0, ROWH = 136, 17
    VX = 40

    def frame(yes_now, slide, n_dots, link_t, all_a, title, stats, label_last=True):
        """yes_now: set of present families; slide: (family, 0..1) sliding in; n_dots: chain dots shown; link_t: newest link draw progress."""
        im = SKY.copy()
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        if all_a > 0:  # the full family of shapes
            for s in shapes:
                if s["parent"]:
                    d.line((xy(s["parent"]), xy(s["rank"])), fill=(120, 135, 190, int(70 * all_a)), width=1)
            for s in shapes:
                x, y = xy(s["rank"])
                rr = rad(s["n"])
                d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=OTHER + (int(200 * all_a),))
        for i in range(1, n_dots):
            t = 1.0 if i < n_dots - 1 else link_t
            p, q = np.array(xy(chain[i - 1]["rank"])), np.array(xy(chain[i]["rank"]))
            e = p + (q - p) * t
            d.line((tuple(p), tuple(e)), fill=LINK + (255,), width=3)
        glow = lay.filter(ImageFilter.GaussianBlur(4))
        im = Image.alpha_composite(Image.alpha_composite(im, glow), lay)
        d = ImageDraw.Draw(im)
        for i in range(n_dots):
            if i == n_dots - 1 and link_t < 1 and i > 0:
                continue
            s = chain[i]
            x, y = xy(s["rank"])
            rr = max(9, rad(s["n"]))
            d.ellipse((x - rr - 3, y - rr - 3, x + rr + 3, y + rr + 3), outline=(255, 255, 255, 230), width=2)
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=DOT)
            d.text((x, y), str(i + 1), font=F["dot"], fill=(10, 14, 32), anchor="mm")
            if all_a < 0.5 and label_last and i == n_dots - 1:
                added = (
                    sorted(set(s["signals"]) - set(chain[i - 1]["signals"]))
                    if i
                    else ["struct_func_start", "struct_linear"]
                )
                lab = ("+ " + nice.get(added[0], added[0])) if i else "declaration + structural keywords"
                sub = f"{s['n']:,} functions · level {len(s['signals'])}"
                left = x > W - 340
                lx = x - rr - 10 if left else x + rr + 8
                anc = "ra" if left else "la"
                d.text((lx, y - 17), lab, font=F["dot"], fill=INK, anchor=anc)
                d.text((lx, y + 2), sub, font=F["dots"], fill=INK2, anchor=anc)
        # the fingerprint column
        d.rounded_rectangle((24, 112, 488, H - 104), 12, fill=(10, 14, 32, 210))
        d.text((VX, 116), "fingerprint: one Yes / No per keyword family", font=F["row"], fill=INK2)
        for j, c in enumerate(FAMILIES):
            y = ROW0 + 8 + j * ROWH
            on = c in yes_now
            d.text((VX + 64, y), nice.get(c, c), font=F["row"], fill=INK if on else MUTED)
            cx = VX
            if slide and slide[0] == c:
                u = slide[1]
                cx = VX + (1 - u) * 420
                d.rounded_rectangle((VX, y - 1, VX + 52, y + 15), 4, fill=NO)
                d.text((VX + 26, y + 7), "No", font=F["cell"], fill=MUTED, anchor="mm")
                d.rounded_rectangle((cx, y - 1, cx + 52, y + 15), 4, fill=YES)
                d.text((cx + 26, y + 7), "Yes", font=F["cell"], fill=INK, anchor="mm")
                continue
            d.rounded_rectangle((VX, y - 1, VX + 52, y + 15), 4, fill=YES if on else NO)
            d.text((VX + 26, y + 7), "Yes" if on else "No", font=F["cell"], fill=INK if on else MUTED, anchor="mm")
        # level axis
        for k in range(0, kmax + 1, 2):
            x = AX[0] + k / kmax * (AX[2] - AX[0])
            d.text((x, AX[3] + 18), str(k), font=F["axis"], fill=MUTED, anchor="mm")
        d.text(
            ((AX[0] + AX[2]) / 2, AX[3] + 38),
            "level = number of keyword families present",
            font=F["axis"],
            fill=MUTED,
            anchor="mm",
        )
        bar = (10, 14, 32, 215)
        d.rounded_rectangle((16, 12, W - 16, 66), 12, fill=bar)
        d.text((34, 26), title, font=F["bar"], fill=INK)
        lg = [("Yes (family present)", YES), ("shape", DOT), ("one-family step", LINK), ("other common shapes", OTHER)]
        lw = sum(int(F["leg"].getlength(t)) + 44 for t, _ in lg) + 18
        x0 = W - 16 - lw + 14
        d.rounded_rectangle((W - 16 - lw, 72, W - 16, 106), 10, fill=bar)
        for t, c in lg:
            d.rounded_rectangle((x0, 79, x0 + 20, 99), 5, fill=c)
            d.text((x0 + 26, 77), t, font=F["leg"], fill=INK)
            x0 += int(F["leg"].getlength(t)) + 44
        d.rounded_rectangle((16, H - 96, W - 16, H - 26), 12, fill=bar)
        for k, ln in enumerate(stats.split("\n")[:2]):
            d.text((34, H - 86 + k * 24), ln, font=F["stat"], fill=INK)
        d.text(
            (18, H - 20),
            f"Population: {D['total']:,} functions from 745 scanned repositories (GitGalaxy v2.12.0). "
            "Dot size = how many functions share the exact shape.",
            font=F["tiny"],
            fill=MUTED,
        )
        return im

    fr = []
    for i in range(22):
        im = SKY.copy()
        d = ImageDraw.Draw(im)
        al = int(255 * min(1, i / 8))
        d.text((W // 2, 300), "How function shapes are built", font=F["title"], fill=INK + (al,), anchor="mm")
        d.text(
            (W // 2, 352),
            "one keyword family at a time · real shapes from 6.9 million functions",
            font=F["sub"],
            fill=INK2 + (al,),
            anchor="mm",
        )
        fr.append(im)
    for t in range(24):
        fr.append(frame(set(), None, 0, 1, 0, "A function's fingerprint", "every keyword family starts at No"))
    base = list(chain[0]["signals"])
    yes = set()
    for c in ("struct_func_start", "struct_linear"):
        for t in range(12):
            fr.append(
                frame(
                    yes,
                    (c, (t + 1) / 12),
                    0,
                    1,
                    0,
                    "The simplest shape: a declaration and its end",
                    "a function is declared, and returns or ends (structural keywords)",
                )
            )
        yes.add(c)
    s0 = chain[0]
    for t in range(18):
        fr.append(
            frame(
                yes,
                None,
                1,
                1,
                0,
                "Dot 1: the simplest common shape",
                f"{s0['n']:,} functions have exactly this shape · level {len(s0['signals'])}",
            )
        )
    for i in range(1, len(chain)):
        s = chain[i]
        added = sorted(set(s["signals"]) - set(chain[i - 1]["signals"]))[0]
        for t in range(12):
            fr.append(
                frame(
                    yes,
                    (added, (t + 1) / 12),
                    i,
                    1,
                    0,
                    f"Add one family: {nice.get(added, added)}",
                    f"slide in one Yes → the next shape (level {len(s['signals'])})",
                )
            )
        yes.add(added)
        for t in range(14):
            fr.append(
                frame(
                    yes,
                    None,
                    i + 1,
                    min(1, (t + 1) / 10),
                    0,
                    f"Dot {i + 1}: + {nice.get(added, added)}",
                    f"{s['n']:,} functions have exactly this shape · level {len(s['signals'])}\n"
                    f"each step adds exactly one keyword family",
                )
            )
    for t in range(14):
        fr.append(
            frame(
                yes,
                None,
                len(chain),
                1,
                0,
                f"A chain of {len(chain)} shapes, built one family at a time",
                " → ".join(f"{s['n'] // 1000}k" for s in chain) + " functions per shape",
            )
        )
    tot = sum(s["n"] for s in shapes)
    for t in range(40):
        fr.append(
            frame(
                yes,
                None,
                len(chain),
                1,
                min(1, (t + 1) / 16),
                "The whole family: the 200 commonest shapes",
                f"200 shapes · {tot:,} functions ({D['cover']:.1%} of {D['total']:,}) · levels 0–{kmax}\n"
                "196 of 199 growth steps add exactly one keyword family: code is built from simple parts, one family at a time",
                label_last=False,
            )
        )
    fr += [fr[-1]] * 36
    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-lattice-"))
    for i, im in enumerate(fr):
        im.convert("RGB").save(fdir / f"f{i:04d}.png")
    out = pathlib.Path(a.out)
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
            "fps=10,scale=880:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
            str(out) + ".gif",
        ],
        check=True,
    )
    shutil.copy(fdir / f"f{len(fr) - 1:04d}.png", str(out) + ".png")
    shutil.rmtree(fdir, ignore_errors=True)
    print("chain:", " -> ".join(f"#{s['rank']}({s['n']})" for s in chain), f"; {len(fr)} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
