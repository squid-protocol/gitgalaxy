#!/usr/bin/env python3
"""Render "Same job, three models" from REAL scan output of the agent-habits programs.

Three autonomous coding agents built the same program (e.g. the chess engine in Java) in the agent-habits study
(squid-protocol/agent-habits). Each program was scanned with GitGalaxy; this draws each one's real call graph side by
side (functions blue, calls red, files green), then the mix of its functions over the population function-shape
families, then the study-level identification result with its caveats.

    python scripts/media/agents_explainer.py --scans <dir with one scan output folder per run> \\
        --runs chess-java-claude-r1:Sonnet chess-java-haiku-r1:Haiku chess-java-codex-r1:Codex \\
        --trees <temporal-crucible docs/fingerprint_trees_exploratory.json> --out docs/media/agents-same-job

Needs Pillow, numpy, scipy and ffmpeg (docs tooling only).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sqlite3
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # scripts/media helpers
from _brand import brand  # noqa: E402
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
        ("model", "DejaVuSans-Bold.ttf", 24),
        ("stat", "DejaVuSans.ttf", 17),
        ("small", "DejaVuSans.ttf", 14),
        ("tiny", "DejaVuSans.ttf", 11),
    )
}
INK, INK2, MUTED = (240, 239, 236), (195, 194, 183), (143, 142, 134)
C_FN, C_FILE, C_CALL = (96, 165, 250), (34, 197, 94), (239, 83, 80)
FAM = {7: ("public / general", (129, 140, 248)), 8: ("private + state / pointers", (192, 132, 252))}
OTHER = ("other shapes", (110, 112, 125))


def sky():
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2).clip(0, 1)
    return Image.fromarray(
        np.stack([14 - 10 * rr, 20 - 14 * rr, 48 - 32 * rr, np.full_like(rr, 255)], -1).astype(np.uint8), "RGBA"
    )


def lattice(trees):
    D = json.loads(pathlib.Path(trees).read_text())
    sets = [frozenset(s["signals"]) for s in D["shapes"]]
    nn = np.array([s["n"] for s in D["shapes"]], float)
    n = len(sets)
    J = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            u = len(sets[i] | sets[j])
            J[i, j] = J[j, i] = 1 - (len(sets[i] & sets[j]) / u if u else 1)
    fam = fcluster(linkage(squareform(J, checks=False), method="average"), 14, criterion="maxclust")
    U = sorted(set().union(*sets))
    S = np.array([[c in s for c in U] for s in sets], np.int32)
    order = np.argsort(-nn, kind="stable")

    def assign(present_rows):
        X = np.array([[c in p for c in U] for p in present_rows], np.int32)
        inter = X @ S.T
        union = X.sum(1)[:, None] + S.sum(1)[None, :] - inter
        jac = np.where(union > 0, inter / np.maximum(union, 1), 1.0)
        return np.where(jac.max(1) > 0, fam[order[np.argmax(jac[:, order], axis=1)]], 0)

    return U, assign


def load(run_dir: pathlib.Path, U, assign):
    g = sqlite3.connect(next(run_dir.glob("*_galaxy_graph.sqlite")))
    files = {aid: fn for aid, fn in g.execute("SELECT id, filename FROM artifacts")}
    funcs = [
        (fid, aid, nm, json.loads(co) if co else [])
        for fid, aid, nm, co in g.execute("SELECT id, artifact_id, name, calls_out_to FROM functions")
    ]
    g.close()
    byname = {}
    for f in funcs:
        byname.setdefault(f[2], f)
    edges = [(f[0], byname[c][0]) for f in funcs for c in f[3] if c in byname and byname[c][0] != f[0]]
    m = sqlite3.connect(next(run_dir.glob("*_galaxy_master.db")))
    cols = [c[1] for c in m.execute("PRAGMA table_info(function_data)")]
    use = [c for c in U if c in cols]
    rows = m.execute(
        f"SELECT f.loc, {', '.join('COALESCE(f.' + c + ',0)' for c in use)} FROM function_data f WHERE f.loc >= 3"
    ).fetchall()
    m.close()
    fams = assign([{c for c, v in zip(use, r[1:]) if v} for r in rows]) if rows else np.array([])
    locs = [r[0] for r in rows]
    used_files = {f[1] for f in funcs}
    return {"files": {a: files[a] for a in used_files}, "funcs": funcs, "edges": edges, "fams": fams, "locs": locs}


def layout(prog, rng, box):
    x0, y0, x1, y1 = box
    ids = [f[0] for f in prog["funcs"]]
    idx = {i: k for k, i in enumerate(ids)}
    fa = np.array([f[1] for f in prog["funcs"]])
    files = sorted(prog["files"])
    cen = {
        a: np.array([np.cos(2 * np.pi * k / len(files)), np.sin(2 * np.pi * k / len(files))])
        * (0.9 if len(files) > 1 else 0)
        for k, a in enumerate(files)
    }
    P = np.array([cen[a] + rng.normal(scale=0.15, size=2) for a in fa])
    A = np.zeros((len(ids), len(ids)))
    for u, v in prog["edges"]:
        A[idx[u], idx[v]] = A[idx[v], idx[u]] = 1
    for it in range(400):
        d = P[:, None] - P[None]
        dist = np.sqrt((d**2).sum(-1)) + 1e-6
        rep = (0.004 / dist**2)[..., None] * d / dist[..., None]
        att = (A * dist)[..., None] * d / dist[..., None] * 0.05
        clus = np.array([cen[a] for a in fa]) - P
        P += np.clip(rep.sum(1) - att.sum(1) + clus * 0.06, -0.05, 0.05)
    for _ in range(300):  # move whole file clusters apart until their circles do not overlap
        cs = {
            a_: (P[fa == a_].mean(0), np.sqrt(((P[fa == a_] - P[fa == a_].mean(0)) ** 2).sum(1)).max() + 0.12)
            for a_ in files
        }
        moved = False
        for i, a1 in enumerate(files):
            for a2 in files[i + 1 :]:
                (c1, r1), (c2, r2) = cs[a1], cs[a2]
                dv = c1 - c2
                dist = float(np.hypot(*dv)) + 1e-6
                if dist < r1 + r2:
                    push = (r1 + r2 - dist) / 2 * dv / dist
                    P[fa == a1] += push
                    P[fa == a2] -= push
                    moved = True
        if not moved:
            break
    # fit whole file circles (not just dots) inside the panel, between the model name and the stats line
    circ = {}
    for a_ in files:
        pts = P[fa == a_]
        c = pts.mean(0)
        circ[a_] = (c, np.sqrt(((pts - c) ** 2).sum(1)).max() + 0.08)
    lo = np.min([c - r for c, r in circ.values()], 0)
    hi = np.max([c + r for c, r in circ.values()], 0)
    ix0, iy0, ix1, iy1 = x0 + 16, y0 + 44, x1 - 16, y1 - 44
    sc = min((ix1 - ix0) / (hi[0] - lo[0]), (iy1 - iy0) / (hi[1] - lo[1]))
    ox = ix0 + ((ix1 - ix0) - sc * (hi[0] - lo[0])) / 2 - lo[0] * sc
    oy = iy0 + ((iy1 - iy0) - sc * (hi[1] - lo[1])) / 2 - lo[1] * sc
    pos = {i: (ox + P[k, 0] * sc, oy + P[k, 1] * sc) for k, i in enumerate(ids)}
    # circles from the FINAL screen positions, so every file's circle contains all of its dots (min radius 14 px);
    # then push whole clusters apart in screen space (room for the file label) and re-fit into the panel.
    fid = {f[0]: f[1] for f in prog["funcs"]}
    PS = {i: np.array(p_, float) for i, p_ in pos.items()}

    def circles():
        out = {}
        for a_ in files:
            pts = np.array([PS[i] for i in PS if fid[i] == a_])
            c = pts.mean(0)
            out[a_] = (c, max(14.0, float(np.sqrt(((pts - c) ** 2).sum(1)).max()) + 12))
        return out

    inner = np.array([x0 + 16, y0 + 44, x1 - 16, y1 - 44], float)
    for _ in range(60):
        moved = False
        for _it in range(200):
            cs = circles()
            step = False
            for i, a1 in enumerate(files):
                for a2 in files[i + 1 :]:
                    (c1, r1), (c2, r2) = cs[a1], cs[a2]
                    dv = c1 - c2
                    dist = float(np.hypot(*dv)) + 1e-6
                    need = r1 + r2 + 22
                    if dist < need:
                        push = (need - dist) / 2 * dv / dist
                        for k in PS:
                            if fid[k] == a1:
                                PS[k] = PS[k] + push
                            elif fid[k] == a2:
                                PS[k] = PS[k] - push
                        step = moved = True
            if not step:
                break
        cs = circles()
        lo = np.min([c - r for c, r in cs.values()], 0)
        hi = np.max([c + r for c, r in cs.values()], 0) + np.array([0, 18])  # label below
        sc = min(1.0, (inner[2] - inner[0]) / (hi[0] - lo[0]), (inner[3] - inner[1]) / (hi[1] - lo[1]))
        mid_now, mid_box = (lo + hi) / 2, np.array([(inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2])
        for k in PS:
            PS[k] = mid_box + (PS[k] - mid_now) * sc
        if not moved and sc > 0.999:
            break
    return {i: tuple(p_) for i, p_ in PS.items()}, circles()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scans", required=True)
    ap.add_argument("--runs", nargs=3, required=True)
    ap.add_argument("--trees", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ident", default="42 of 50 (84%) · chance 28%")
    ap.add_argument("--job", default="a chess engine in Java")
    a = ap.parse_args()
    rng = np.random.default_rng(7)
    U, assign = lattice(a.trees)
    runs = [r.split(":") for r in a.runs]
    progs = [load(pathlib.Path(a.scans) / r, U, assign) for r, _ in runs]
    boxes = [(30 + k * 415, 120, 30 + k * 415 + 395, 470) for k in range(3)]
    lays = [layout(p, rng, b) for p, b in zip(progs, boxes)]
    SKY = sky()

    def frame(n_fn, n_edge, mix_a, title, stats, final_a=0):
        im = SKY.copy()
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for p, (pos, fc), b, (_, model) in zip(progs, lays, boxes, runs):
            d.rounded_rectangle(b, 14, fill=(10, 14, 32, 200), outline=(60, 70, 110, 255))
            for aid, (c, r) in fc.items():
                d.ellipse(
                    (c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=C_FILE + (40,), outline=C_FILE + (150,), width=2
                )
            for u, v in p["edges"][: int(len(p["edges"]) * n_edge)]:
                d.line((pos[u], pos[v]), fill=C_CALL + (190,), width=2)
        glow = lay.filter(ImageFilter.GaussianBlur(4))
        im = Image.alpha_composite(Image.alpha_composite(im, glow), lay)
        d = ImageDraw.Draw(im)
        for p, (pos, fc), b, (_, model) in zip(progs, lays, boxes, runs):
            k = int(len(p["funcs"]) * n_fn)
            for f in p["funcs"][:k]:
                x, y = pos[f[0]]
                d.ellipse((x - 4.5, y - 4.5, x + 4.5, y + 4.5), fill=C_FN)
            for aid, (c, r) in fc.items():
                d.text((c[0], c[1] + r + 9), p["files"][aid], font=F["small"], fill=(134, 239, 172), anchor="mm")
            d.text(((b[0] + b[2]) / 2, b[1] + 18), model, font=F["model"], fill=INK, anchor="mm")
            nfun, ncall = len(p["funcs"]), len(p["edges"])
            med = int(np.median(p["locs"])) if p["locs"] else 0
            d.text(
                ((b[0] + b[2]) / 2, b[3] - 20),
                f"{nfun} functions · {ncall} calls · median {med} lines",
                font=F["stat"],
                fill=INK2,
                anchor="mm",
            )
            if mix_a > 0:
                fams = p["fams"]
                y = b[3] + 18
                d.text(
                    (b[0], y),
                    f"shape families of its {len(fams)} functions ≥ 3 lines",
                    font=F["small"],
                    fill=INK2 + (int(255 * mix_a),),
                )
                x = b[0]
                wbar = b[2] - b[0]
                parts = [(np.mean(fams == f) if len(fams) else 0, FAM[f][1]) for f in (7, 8)]
                parts.append((1 - sum(v for v, _ in parts), OTHER[1]))
                for v, col in parts:
                    wv = wbar * v * mix_a
                    d.rectangle((x, y + 22, x + wv, y + 46), fill=col)
                    if v >= 0.12 and mix_a > 0.9:
                        d.text((x + wv / 2, y + 34), f"{v:.0%}", font=F["small"], fill=(15, 17, 23), anchor="mm")
                    x += wbar * v
        bar = (10, 14, 32, 215)
        d.rounded_rectangle((16, 12, W - 16, 66), 12, fill=bar)
        d.text((34, 26), title, font=F["bar"], fill=INK)
        lg = [("function", C_FN), ("file", C_FILE), ("call", C_CALL), (FAM[7][0], FAM[7][1]), (FAM[8][0], FAM[8][1])]
        x0 = W - 16 - sum(int(F["leg"].getlength(t)) + 44 for t, _ in lg) - 4
        for t, c in lg:
            d.rounded_rectangle((x0, 29, x0 + 20, 49), 5, fill=c)
            d.text((x0 + 26, 27), t, font=F["leg"], fill=INK)
            x0 += int(F["leg"].getlength(t)) + 44
        d.rounded_rectangle((16, H - 96, W - 16, H - 26), 12, fill=bar)
        words, lines_, cur = stats.split(" "), [], ""
        for w_ in words:
            if F["stat"].getlength(cur + " " + w_) > W - 80:
                lines_.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        lines_.append(cur)
        for k, ln in enumerate(lines_[:2]):
            d.text((34, H - 86 + k * 24), ln, font=F["stat"], fill=INK)
        d.text(
            (18, H - 20),
            "Programs: squid-protocol/agent-habits (autonomous runs, same prompt and checker). Scanned with GitGalaxy.",
            font=F["tiny"],
            fill=MUTED,
        )
        return im

    fr = []
    for i in range(0):  # no intro title card (owner 2026-11-07)
        im = SKY.copy()
        d = ImageDraw.Draw(im)
        al = int(255 * min(1, i / 8))
        d.text((W // 2, 300), "Same job, three AI models", font=F["title"], fill=INK + (al,), anchor="mm")
        d.text(
            (W // 2, 352),
            f"{a.job}, built autonomously by each · structure measured by GitGalaxy",
            font=F["sub"],
            fill=INK2 + (al,),
            anchor="mm",
        )
        fr.append(im)
    for t in range(30):
        fr.append(frame(min(1, t / 20), 0, 0, "Each model's functions…", "same prompt, same tests, no human steering"))
    for t in range(36):
        fr.append(frame(1, min(1, t / 28), 0, "…and how they call each other", "real call graphs from the scan"))
    for t in range(30):
        fr.append(
            frame(
                1,
                1,
                min(1, t / 16),
                "…and what kinds of functions they build",
                "shares of each program's functions per population shape family",
            )
        )
    fin = (
        f"Across all 10 jobs, a program's nearest same-job neighbour is by the same model {a.ident} "
        "(exploratory). Inside one shared codebase this mostly disappears."
    )
    for t in range(60):
        fr.append(frame(1, 1, 1, "Each model has a structural handwriting", fin))
    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-agents-"))
    for i, im in enumerate(fr):
        brand(im).convert("RGB").save(fdir / f"f{i:04d}.png")
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
    for (r, m), p in zip(runs, progs):
        print(
            m,
            r,
            len(p["funcs"]),
            "functions",
            len(p["edges"]),
            "calls",
            "families",
            {int(k): int(v) for k, v in zip(*np.unique(p["fams"], return_counts=True))},
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
