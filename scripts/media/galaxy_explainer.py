#!/usr/bin/env python3
"""Render "One function in a galaxy of millions" from REAL data.

Inputs (all measured, none drawn by hand):
- the population fingerprint lattice: the 200 commonest function shapes (exact keyword-family presence signatures)
  of 6.9M functions, their counts, repos and growth-tree parents (temporal-crucible docs/fingerprint_trees_exploratory.json);
- one function's present families (default: zlib gzeof, measured by docs/media/function-c);
- optionally, real week-to-week shape changes of GitGalaxy's own functions (weekly scan DBs), drawn as hops between shapes.

    python scripts/media/galaxy_explainer.py --trees <fingerprint_trees_exploratory.json> --gg <gg_weekly_scans dir> \\
        --out docs/media/galaxy

Needs Pillow, numpy, scipy and ffmpeg (docs tooling only).
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import shutil
import sqlite3
import subprocess
import tempfile
from collections import Counter, defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

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
        ("lab", "DejaVuSans-Bold.ttf", 17),
        ("small", "DejaVuSans.ttf", 14),
        ("tiny", "DejaVuSans.ttf", 11),
        ("mono", "DejaVuSansMono.ttf", 15),
    )
}
INK, INK2, MUTED = (240, 239, 236), (195, 194, 183), (143, 142, 134)
FAMC = {
    7: ((129, 140, 248), "public / general"),
    8: ((192, 132, 252), "private + state / pointers"),
    6: ((45, 212, 191), "bare one-step"),
}
OTHERC = ((120, 125, 150), "other families")
GZEOF = [
    "arch_api",
    "state_flux",
    "state_pointers",
    "struct_args",
    "struct_branch",
    "struct_func_start",
    "struct_linear",
]
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


def sky(seed=11):
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2).clip(0, 1)
    im = Image.fromarray(
        np.stack([14 - 10 * rr, 20 - 14 * rr, 48 - 32 * rr, np.full_like(rr, 255)], -1).astype(np.uint8), "RGBA"
    )
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(seed)
    for _ in range(300):
        b = int(r.uniform(40, 120))
        d.point((r.uniform(0, W), r.uniform(0, H)), fill=(b, b, min(255, b + 30), 255))
    return im


def gg_moves(gg_dir: pathlib.Path, sets):
    """Week-to-week shape changes of GitGalaxy's functions whose shapes, before and after, are among the 200."""
    weeks = json.loads((gg_dir / "weeks.json").read_text())
    U = sorted(set().union(*sets))
    rank = {frozenset(s): i for i, s in enumerate(sets)}
    prev, moves, steady, total = None, Counter(), 0, 0
    for wk in weeks:
        db = gg_dir / f"{wk['week']}_{wk['sha'][:9]}" / "gg_galaxy_master.db"
        if not db.exists():
            continue
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        have = {c[1] for c in con.execute("PRAGMA table_info(function_data)")}
        use = [c for c in U if c in have]
        cur = {}
        for r in con.execute(
            f"SELECT fd.file_path, f.func_name, {', '.join('COALESCE(f.' + c + ',0)' for c in use)} FROM function_data f "
            "JOIN file_data fd ON f.file_id = fd.id WHERE fd.language = 'python' AND f.loc >= 3"
        ):
            cur.setdefault((r[0], r[1]), frozenset(c for c, v in zip(use, r[2:]) if v))
        con.close()
        if prev is not None:
            for k, s in cur.items():
                if k in prev:
                    total += 1
                    a, b = rank.get(prev[k]), rank.get(s)
                    if prev[k] == s:
                        steady += 1
                    elif a is not None and b is not None:
                        moves[(a, b)] += 1
        prev = cur
    return moves, steady, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", required=True)
    ap.add_argument("--gg", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    D = json.loads(pathlib.Path(a.trees).read_text())
    shapes = D["shapes"]
    sets = [frozenset(s["signals"]) for s in shapes]
    n = len(sets)
    J = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            u = len(sets[i] | sets[j])
            J[i, j] = J[j, i] = 1 - (len(sets[i] & sets[j]) / u if u else 1)
    fam = fcluster(linkage(squareform(J, checks=False), method="average"), 14, criterion="maxclust")
    gi = next(i for i, s in enumerate(sets) if s == frozenset(GZEOF))
    # tidy tree layout: x = number of families present, y = DFS leaf order
    kids = defaultdict(list)
    roots = []
    for i, s in enumerate(shapes):
        (kids[s["parent"] - 1] if s["parent"] else roots).append(i)
    ypos, nxt = {}, [0]

    def place(i):
        ch = sorted(kids[i], key=lambda j: -shapes[j]["n"])
        for c in ch:
            place(c)
        ypos[i] = float(np.mean([ypos[c] for c in ch])) if ch else nxt[0]
        if not ch:
            nxt[0] += 1

    for r in roots:
        place(r)
    kmax = max(len(s) for s in sets)
    world = {i: np.array([len(sets[i]) / kmax, ypos[i] / max(nxt[0] - 1, 1)]) for i in range(n)}
    share = np.array([s["n"] for s in shapes], float) / D["total"]
    moves, steady, total = gg_moves(pathlib.Path(a.gg), sets) if a.gg else (Counter(), 0, 0)
    SKY = sky()
    MAP = (90, 140, W - 90, H - 128)

    def to_screen(p, cam):
        c, z = cam
        x = MAP[0] + (0.5 + (p[0] - c[0]) * z) * (MAP[2] - MAP[0])
        y = MAP[1] + (0.5 + (p[1] - c[1]) * z) * (MAP[3] - MAP[1])
        return x, y

    def colour(i):
        return FAMC.get(int(fam[i]), OTHERC)[0]

    def frame(cam, alpha_map, title, stats, hops=(), star_label=True, fp_grid=0.0, grid_collapse=0.0):
        im = SKY.copy()
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        if alpha_map > 0:
            for i, s in enumerate(shapes):
                if s["parent"]:
                    p, q = to_screen(world[s["parent"] - 1], cam), to_screen(world[i], cam)
                    d.line((p, q), fill=(110, 130, 200, int(70 * alpha_map)), width=1)
            for (u, v), cnt, t in hops:
                p, q = np.array(to_screen(world[u], cam)), np.array(to_screen(world[v], cam))
                mid = (p + q) / 2 + np.array([0, -30])
                pts = [tuple((1 - s_) ** 2 * p + 2 * (1 - s_) * s_ * mid + s_**2 * q) for s_ in np.linspace(0, 1, 18)]
                d.line(pts, fill=(250, 204, 21, 150), width=2)
                x, y = (1 - t) ** 2 * p + 2 * (1 - t) * t * mid + t**2 * q
                d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(250, 204, 21, 255))
            for i in range(n):
                x, y = to_screen(world[i], cam)
                r = 2.5 + 60 * math.sqrt(share[i]) * min(cam[1], 3) ** 0.5
                d.ellipse((x - r, y - r, x + r, y + r), fill=colour(i) + (int(230 * alpha_map),))
        glow = lay.filter(ImageFilter.GaussianBlur(5))
        im = Image.alpha_composite(Image.alpha_composite(Image.alpha_composite(im, glow), glow), lay)
        d = ImageDraw.Draw(im)
        if alpha_map > 0:
            x, y = to_screen(world[gi], cam)
            r = 2.5 + 60 * math.sqrt(share[gi]) * min(cam[1], 3) ** 0.5
            d.ellipse((x - r - 5, y - r - 5, x + r + 5, y + r + 5), outline=(255, 255, 255, 255), width=3)
            if star_label:
                d.text((x + r + 10, y - 22), "gzeof()'s shape", font=F["lab"], fill=INK)
                d.text(
                    (x + r + 10, y),
                    f"#{gi + 1} most common shape · {shapes[gi]['n']:,} functions",
                    font=F["small"],
                    fill=INK2,
                )
        if fp_grid > 0:  # gzeof's fingerprint grid, optionally collapsing into its star
            cx, cy = W / 2, H / 2 - 10
            for j, c in enumerate(FINGERPRINT):
                gx = cx + ((j % 14) - 6.5) * 36
                gy = cy + ((j // 14) - 0.5) * 36
                if grid_collapse > 0:
                    sx, sy = to_screen(world[gi], cam) if alpha_map > 0 else (cx, cy)
                    gx, gy = gx + (sx - gx) * grid_collapse, gy + (sy - gy) * grid_collapse
                on = c in GZEOF
                sz = 15 * (1 - grid_collapse) + 2
                al = int(255 * fp_grid)
                d.rounded_rectangle(
                    (gx - sz, gy - sz, gx + sz, gy + sz),
                    max(1, min(5, int(sz) - 1)),
                    fill=((57, 135, 229) if on else (48, 49, 56)) + (al,),
                )
                if grid_collapse < 0.3:
                    d.text(
                        (gx, gy), "1" if on else "0", font=F["small"], fill=(INK if on else MUTED) + (al,), anchor="mm"
                    )
            if grid_collapse < 0.3:
                d.text(
                    (W / 2, cy - 70),
                    "zlib gzeof(): which keyword families are present",
                    font=F["lab"],
                    fill=INK + (int(255 * fp_grid),),
                    anchor="mm",
                )
        bar = (10, 14, 32, 215)
        d.rounded_rectangle((16, 12, W - 16, 66), 12, fill=bar)
        d.text((34, 26), title, font=F["bar"], fill=INK)
        lg = [
            (FAMC[7][1], FAMC[7][0]),
            (FAMC[8][1], FAMC[8][0]),
            (FAMC[6][1], FAMC[6][0]),
            (OTHERC[1], OTHERC[0]),
            ("real move", (250, 204, 21)),
        ]
        x0 = 34
        d.rounded_rectangle((16, 72, 16 + sum(int(F["leg"].getlength(t)) + 44 for t, _ in lg) + 22, 108), 10, fill=bar)
        for t, c in lg:
            d.ellipse((x0, 80, x0 + 20, 100), fill=c)
            d.text((x0 + 26, 79), t, font=F["leg"], fill=INK)
            x0 += int(F["leg"].getlength(t)) + 44
        d.rounded_rectangle((16, H - 96, W - 16, H - 26), 12, fill=bar)
        for k, ln in enumerate(stats.split("\n")[:2]):
            d.text((34, H - 86 + k * 24), ln, font=F["stat"], fill=INK)
        if alpha_map > 0.5:
            d.text(
                (MAP[0], MAP[3] + 4),
                "fewer keyword families  →  more keyword families per function",
                font=F["small"],
                fill=MUTED,
            )
        d.text(
            (18, H - 20),
            "Population: 6,936,799 functions (745 scanned repositories, GitGalaxy v2.12.0). Star size = share of functions.",
            font=F["tiny"],
            fill=MUTED,
        )
        return im

    fr = []
    for i in range(22):
        im = SKY.copy()
        d = ImageDraw.Draw(im)
        al = int(255 * min(1, i / 8))
        d.text((W // 2, 300), "One function in a galaxy of millions", font=F["title"], fill=INK + (al,), anchor="mm")
        d.text(
            (W // 2, 352),
            "every function's keyword fingerprint is a point; common shapes are the bright stars",
            font=F["sub"],
            fill=INK2 + (al,),
            anchor="mm",
        )
        fr.append(im)
    close = (world[gi], 5.0)
    far = (np.array([0.5, 0.5]), 0.92)
    for t in range(26):
        fr.append(
            frame(
                close,
                0,
                "Start with one function's fingerprint",
                "zlib's gzeof(): 7 of 27 common keyword families present",
                fp_grid=min(1, t / 6),
            )
        )
    for t in range(20):
        u = t / 19
        fr.append(
            frame(
                close,
                u,
                "Its exact shape is a star shared by many functions",
                f"{shapes[gi]['n']:,} functions in {shapes[gi]['repos']} repositories share gzeof()'s exact shape\n"
                f"the #{gi + 1} most common shape (mostly C)",
                fp_grid=1 - u,
                grid_collapse=u,
                star_label=u > 0.8,
            )
        )
    for t in range(30):
        u = t / 29
        e = u * u * (3 - 2 * u)
        cam = (close[0] * (1 - e) + far[0] * e, close[1] * (1 - e) + far[1] * e)
        fr.append(
            frame(
                cam,
                1,
                "Zooming out: the 200 commonest shapes",
                f"{shapes[gi]['n']:,} functions share gzeof()'s shape",
                star_label=True,
            )
        )
    pop = (
        f"these 200 shapes hold {D['cover']:.1%} of all {D['total']:,} functions; the rest spread over ~315,000 rarer shapes\n"
        "lines: each shape grows from a shape with one family fewer (196 of 199 growth steps add exactly one)"
    )
    for t in range(40):
        fr.append(frame(far, 1, "The shape lattice of real code", pop))
    if moves:
        top = moves.most_common(14)
        nmove = sum(moves.values())
        for t in range(60):
            hops = [((u, v), c, ((t + 4 * k) % 30) / 29) for k, ((u, v), c) in enumerate(top)]
            fr.append(
                frame(
                    far,
                    1,
                    "How real functions move between shapes",
                    f"GitGalaxy's own functions, week to week: {steady / max(total, 1):.0%} of function-weeks keep their shape\n"
                    f"yellow: the {len(top)} commonest real moves between these shapes ({nmove:,} moves in all)",
                    hops=hops,
                )
            )
    fr += [fr[-1]] * 30
    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-galaxy-"))
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
    print(
        f"gzeof shape rank {gi + 1}, n {shapes[gi]['n']}; GG function-weeks {total}, steady {steady}, moves between top shapes {sum(moves.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
