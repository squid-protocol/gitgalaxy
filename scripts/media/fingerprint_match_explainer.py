#!/usr/bin/env python3
"""Render "Did someone copy your function?": an ILLUSTRATION of fingerprint matching. No scan data is used.

Every function, file, repository and fingerprint here is made up (fixed random seed). The film shows the idea only:
a function becomes a fingerprint (one Yes / No cell per keyword family); the search compares that fingerprint with
the fingerprints of functions in other files and repositories, ignoring names, until one is identical, even though the
copy was renamed. For the measured version on real code (OpenSSL -> BoringSSL), see copyfinding_explainer.py.

    python scripts/media/fingerprint_match_explainer.py --out docs/media/fingerprint-match

Needs Pillow, numpy and ffmpeg (docs tooling only).
"""

from __future__ import annotations

import argparse
import math
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # scripts/media helpers
from _brand import brand  # noqa: E402

W, H, FPS = 1280, 720, 12
FD = pathlib.Path("/usr/share/fonts/truetype/dejavu")


def font(name, size):
    return ImageFont.truetype(str(FD / name), size)


f_head = font("DejaVuSans-Bold.ttf", 26)
f_bar = font("DejaVuSans-Bold.ttf", 20)
f_leg = font("DejaVuSans.ttf", 18)
f_code = font("DejaVuSansMono.ttf", 14)
f_hdr = font("DejaVuSans-Bold.ttf", 15)
f_small = font("DejaVuSans.ttf", 14)
f_cell = font("DejaVuSans-Bold.ttf", 11)
f_verdict = font("DejaVuSans-Bold.ttf", 22)
f_boom = font("DejaVuSans-Bold.ttf", 54)
f_card = font("DejaVuSansMono.ttf", 19)
f_cardb = font("DejaVuSans-Bold.ttf", 22)
f_tiny = font("DejaVuSans.ttf", 12)

BG, PANEL = (12, 15, 30), (22, 26, 46)
INK, INK2, MUTED = (240, 239, 236), (195, 194, 183), (130, 132, 150)
C_FN, C_FILE, C_REPO = (96, 165, 250), (34, 197, 94), (239, 83, 80)
YES, NO = (59, 130, 246), (44, 47, 64)
MISS, HIT = (248, 113, 113), (74, 222, 128)

CODE = [
    "def parse_invoice(lines, rate):",
    "    total = 0",
    "    for line in lines:",
    "        if not line.strip():",
    "            continue",
    '        qty, price = line.split(",")',
    "        total += int(qty) * float(price)",
    "    return round(total * (1 + rate), 2)",
]
NBITS = 16
CELL, CGAP = 21, 5
COL_Y0 = 112
COL_X = (392, 448)  # yours, candidate


def build_world(rng):
    """Repositories (red) holding files (green) holding functions (blue); every circle sits fully inside its parent."""
    names = [
        "acme-tools",
        "tiny-ledger",
        "open-forms",
        "quick-csv",
        "your_competitor",
        "data-pipes",
        "web-widgets",
        "net-utils",
    ]
    repos = []
    x0, y0, cw, ch = 490, 100, 770 / 4, 540 / 2
    for i, nm in enumerate(names):
        cx, cy = x0 + cw * (i % 4 + 0.5), y0 + ch * (i // 4 + 0.5)
        R = 88
        files = []
        for _ in range(400):
            if len(files) >= rng.randint(4, 6):
                break
            r = rng.uniform(22, 32)
            ang, dist = rng.uniform(0, 2 * math.pi), rng.uniform(0, R - r - 6)
            fx, fy = cx + dist * math.cos(ang), cy + dist * math.sin(ang)
            if all(math.hypot(fx - f["x"], fy - f["y"]) > r + f["r"] + 4 for f in files):
                files.append({"x": fx, "y": fy, "r": r, "fns": []})
        for f in files:
            for _ in range(300):
                if len(f["fns"]) >= int(f["r"] / 4):
                    break
                ang, dist = rng.uniform(0, 2 * math.pi), rng.uniform(0, f["r"] - 8)
                px, py = f["x"] + dist * math.cos(ang), f["y"] + dist * math.sin(ang)
                if all(math.hypot(px - q[0], py - q[1]) > 10 for q in f["fns"]):
                    f["fns"].append((px, py))
        repos.append({"name": nm, "x": cx, "y": cy, "r": R, "files": files})
    return repos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="docs/media/fingerprint-match")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--checks", type=int, default=50, help="functions checked before the match")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    repos = build_world(rng)
    ours = [1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1]
    assert len(ours) == NBITS

    # the search order: hop between repositories (never the competitor) for a.checks functions, then the match
    others = [
        (ri, fi, k)
        for ri, r in enumerate(repos)
        if r["name"] != "your_competitor"
        for fi, f in enumerate(r["files"])
        for k in range(len(f["fns"]))
    ]
    rng.shuffle(others)
    order, last = [], None
    while len(order) < a.checks and others:
        pick = next((o for o in others if o[0] != last), others[0])
        others.remove(pick)
        order.append(pick)
        last = pick[0]
    comp = next(i for i, r in enumerate(repos) if r["name"] == "your_competitor")
    cf = max(range(len(repos[comp]["files"])), key=lambda i: len(repos[comp]["files"][i]["fns"]))
    target = (comp, cf, 0)

    def cand_bits(i):
        """Made-up fingerprints: most differ in several cells; two late near misses differ in one."""
        if i in (a.checks - 9, a.checks - 3):
            b = list(ours)
            b[rng.randrange(NBITS)] ^= 1
            return b
        while True:
            b = [1 if rng.random() < 0.45 else 0 for _ in range(NBITS)]
            if sum(x != y for x, y in zip(b, ours)) >= 3:
                return b

    cands = [cand_bits(i) for i in range(len(order))]

    def fn_xy(o):
        return repos[o[0]]["files"][o[1]]["fns"][o[2]]

    SEA = Image.new("RGBA", (W, H), BG + (255,))
    sd = ImageDraw.Draw(SEA)
    for r in repos:
        sd.ellipse(
            (r["x"] - r["r"], r["y"] - r["r"], r["x"] + r["r"], r["y"] + r["r"]),
            fill=C_REPO + (28,),
            outline=C_REPO + (200,),
            width=2,
        )
        for f in r["files"]:
            sd.ellipse(
                (f["x"] - f["r"], f["y"] - f["r"], f["x"] + f["r"], f["y"] + f["r"]),
                fill=C_FILE + (30,),
                outline=C_FILE + (210,),
                width=2,
            )
            for px, py in f["fns"]:
                sd.ellipse((px - 4, py - 4, px + 4, py + 4), fill=C_FN + (235,))

    def column(d, x, bits, label, shown=NBITS, marks=None, alpha=255):
        d.text((x + CELL / 2, COL_Y0 - 16), label, font=f_hdr, fill=INK2 + (alpha,), anchor="mm")
        for j in range(NBITS):
            y = COL_Y0 + j * (CELL + CGAP)
            if j >= shown:
                d.rounded_rectangle((x, y, x + CELL, y + CELL), 4, outline=(60, 64, 84, alpha), width=1)
                continue
            on = bits[j]
            d.rounded_rectangle((x, y, x + CELL, y + CELL), 4, fill=(YES if on else NO) + (alpha,))
            d.text(
                (x + CELL / 2, y + CELL / 2),
                "1" if on else "0",
                font=f_cell,
                fill=(INK if on else MUTED) + (alpha,),
                anchor="mm",
            )
            if marks and marks[j]:
                d.rounded_rectangle((x - 3, y - 3, x + CELL + 3, y + CELL + 3), 6, outline=marks[j] + (alpha,), width=2)

    def frame(
        *,
        code_a=1.0,
        fp_shown=0,
        line_t=0.0,
        sea_a=0.0,
        cand=None,
        cand_marks=None,
        verdict=None,
        hl=None,
        checked=0,
        title="",
        boom=0.0,
        card=0.0,
        lines_to=None,
    ):
        im = Image.new("RGBA", (W, H), BG + (255,))
        if sea_a > 0:
            sea = SEA.copy()
            sea.putalpha(sea.getchannel("A").point(lambda v: int(v * sea_a)))
            im = Image.alpha_composite(im, sea)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.text((W / 2, 25), "Did someone copy your function?", font=f_head, fill=INK, anchor="mm")
        # your function
        al = int(255 * code_a)
        d.rounded_rectangle((24, 56, 372, 100 + len(CODE) * 19 + 14), 10, fill=PANEL + (al,))
        d.text((40, 66), "your_repo · billing.py", font=f_hdr, fill=INK2 + (al,))
        for i, ln in enumerate(CODE):
            d.text((40, 96 + i * 19), ln, font=f_code, fill=INK + (al,))
        if line_t > 0:  # one line: the function -> its fingerprint
            p, q = (372, 160), (COL_X[0] - 4, COL_Y0 + 4 * (CELL + CGAP))
            e = (p[0] + (q[0] - p[0]) * line_t, p[1] + (q[1] - p[1]) * line_t)
            d.line((p, e), fill=C_FN + (230,), width=3)
        if fp_shown:
            column(d, COL_X[0], ours, "yours", shown=fp_shown)
            if fp_shown >= NBITS and cand is None:
                d.text((40, 300), "its fingerprint:", font=f_small, fill=INK2)
                d.text((40, 322), "one Yes / No per", font=f_small, fill=INK2)
                d.text((40, 344), "keyword family", font=f_small, fill=INK2)
                d.text((40, 378), "no names, just shape", font=f_small, fill=MUTED)
        if cand is not None:
            column(d, COL_X[1], cand, "theirs", marks=cand_marks)
        if verdict:
            txt, colr = verdict
            d.text((40, 300), txt, font=f_verdict, fill=colr)
        if checked:
            d.text((40, 340), f"checked: {checked}", font=f_small, fill=INK2)
        if hl is not None:  # the function being compared: ringed, tied to the candidate column
            x, y = hl
            d.line(
                ((COL_X[1] + CELL + 8, COL_Y0 + NBITS * (CELL + CGAP) / 2), (x, y)), fill=(255, 255, 255, 110), width=1
            )
            d.ellipse((x - 9, y - 9, x + 9, y + 9), outline=(255, 255, 255, 255), width=3)
        if lines_to:
            for x, y in lines_to:
                d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255, 120))
        if boom > 0:
            x, y = fn_xy(target)
            if boom < 1:  # the expanding ring, on its own layer so it never erases what is under it
                ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                rr = 10 + 120 * boom
                ImageDraw.Draw(ring).ellipse(
                    (x - rr, y - rr, x + rr, y + rr), outline=HIT + (int(255 * (1 - boom)),), width=6
                )
                lay = Image.alpha_composite(lay, ring)
                d = ImageDraw.Draw(lay)
            d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=HIT + (255,))
        glow = lay.filter(ImageFilter.GaussianBlur(3))
        im = Image.alpha_composite(Image.alpha_composite(im, glow), lay)
        d = ImageDraw.Draw(im)
        if boom > 0:
            x, y = fn_xy(target)
            d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=HIT + (255,), outline=(255, 255, 255), width=2)
            r = repos[target[0]]
            d.text((r["x"], r["y"] + r["r"] + 14), r["name"], font=f_hdr, fill=INK, anchor="mm")
        if card > 0:
            ca = int(255 * min(1, card))
            bx = (500, 110, 1250, 360)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            od.rounded_rectangle(bx, 14, fill=(10, 30, 22, int(235 * min(1, card))), outline=HIT + (ca,), width=3)
            od.text((524, 128), "MATCH FOUND", font=f_boom, fill=HIT + (ca,))
            od.text((524, 204), "your_competitor / lib/money.py", font=f_card, fill=INK + (ca,))
            od.text((524, 236), "def stolen_ip(rows, rate):", font=f_card, fill=(253, 224, 71, ca))
            od.text((524, 278), "renamed, but the fingerprint is identical", font=f_cardb, fill=INK + (ca,))
            od.text(
                (524, 314),
                f"{a.checks} misses across {len(repos) - 1} other repositories, then this one",
                font=f_small,
                fill=INK2 + (ca,),
            )
            im = Image.alpha_composite(im, ov)
            d = ImageDraw.Draw(im)
        # legend + caption
        lg = [("function", C_FN), ("file", C_FILE), ("repository", C_REPO), ("Yes", YES), ("No", NO)]
        x0 = 490
        if sea_a > 0:
            for t, c in lg:
                d.rounded_rectangle((x0, 652, x0 + 18, 670), 5, fill=c)
                d.text((x0 + 24, 651), t, font=f_leg, fill=INK)
                x0 += int(f_leg.getlength(t)) + 46
        if title:
            d.text((24, 612), title, font=f_bar, fill=INK)
        d.text(
            (18, H - 22),
            "Illustration: made-up functions, files, repositories and fingerprints. "
            "Matching compares fingerprints only, never names.",
            font=f_tiny,
            fill=MUTED,
        )
        return im

    fr = []
    for t in range(14):
        fr.append(frame(code_a=min(1, (t + 1) / 6), title="Your function"))
    for t in range(10):
        fr.append(frame(line_t=(t + 1) / 10, title="GitGalaxy reads its shape..."))
    for j in range(NBITS):
        for _ in range(2):
            fr.append(frame(line_t=1, fp_shown=j + 1, title="...into a fingerprint"))
    for _ in range(14):
        fr.append(frame(line_t=1, fp_shown=NBITS, title="...into a fingerprint"))
    for t in range(18):
        fr.append(
            frame(
                line_t=1,
                fp_shown=NBITS,
                sea_a=min(1, (t + 1) / 12),
                title="Millions of functions, in files, in repositories",
            )
        )
    seen = []
    for i, (o, bits) in enumerate(zip(order, cands)):
        n = 10 if i < 4 else (4 if i < 14 else 2)
        if i in (a.checks - 9, a.checks - 3):
            n = 8  # near miss: one cell off
        marks = [MISS if b != c else None for b, c in zip(bits, ours)]
        for t in range(n):
            reveal = t >= n // 2 or n <= 2
            fr.append(
                frame(
                    line_t=1,
                    fp_shown=NBITS,
                    sea_a=1,
                    cand=bits,
                    cand_marks=marks if reveal else None,
                    verdict=(
                        ("so close: not a match" if sum(m is not None for m in marks) == 1 else "not a match"),
                        MISS,
                    )
                    if reveal
                    else None,
                    hl=fn_xy(o),
                    checked=i + 1,
                    lines_to=seen,
                    title="Searching every other function's fingerprint...",
                )
            )
        seen.append(fn_xy(o))
    # the match: compare cell by cell, every one agrees
    tx = fn_xy(target)
    for j in range(NBITS + 1):
        for _ in range(2):
            fr.append(
                frame(
                    line_t=1,
                    fp_shown=NBITS,
                    sea_a=1,
                    cand=ours,
                    cand_marks=[HIT if k < j else None for k in range(NBITS)],
                    hl=tx,
                    checked=a.checks + 1,
                    lines_to=seen,
                    title="This one... every cell agrees",
                )
            )
    full = [HIT] * NBITS
    for t in range(12):
        fr.append(
            frame(
                line_t=1,
                fp_shown=NBITS,
                sea_a=1,
                cand=ours,
                cand_marks=full,
                verdict=("MATCH", HIT),
                checked=a.checks + 1,
                boom=(t + 1) / 12,
                hl=tx,
                lines_to=seen,
                title="Boom.",
            )
        )
    for t in range(60):
        fr.append(
            frame(
                line_t=1,
                fp_shown=NBITS,
                sea_a=1,
                cand=ours,
                cand_marks=full,
                verdict=("MATCH", HIT),
                checked=a.checks + 1,
                boom=1.0,
                hl=tx,
                card=(t + 1) / 6,
                lines_to=seen,
                title="Found a copy, even with a new name",
            )
        )

    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-fpmatch-"))
    for i, im in enumerate(fr):
        brand(im).convert("RGB").save(fdir / f"f{i:04d}.png")
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fdir / "f%04d.png")]
    subprocess.run(ff + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out) + ".mp4"], check=True)
    subprocess.run(
        ff
        + [
            "-vf",
            "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer",
            str(out) + ".gif",
        ],
        check=True,
    )
    shutil.copy(fdir / f"f{len(fr) - 1:04d}.png", str(out) + ".png")
    shutil.copy(fdir / f"f{len(fr) // 2:04d}.png", str(fdir.parent / "gg-fpmatch-mid.png"))
    shutil.rmtree(fdir, ignore_errors=True)
    print(f"{out}: {len(fr)} frames; {sum(len(f['fns']) for r in repos for f in r['files'])} functions drawn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
