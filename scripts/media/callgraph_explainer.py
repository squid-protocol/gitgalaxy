#!/usr/bin/env python3
"""Render "From one function to the whole call graph" from REAL engine output.

Scans a source tree with this checkout's engine and reads its graph output (functions + calls_out_to, file-level
imports). The camera starts on one function and its calls, follows a second hop, zooms out to its file, then to the
whole codebase: every file as a cluster of function dots, cross-file call lines, then import (#include) lines.

    python scripts/media/callgraph_explainer.py --src <dir> --start gzread --label "zlib" --out docs/media/callgraph-c \\
        [--attribution "..."]

Needs Pillow, numpy and ffmpeg (docs tooling only).
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
W, H, FPS = 1280, 720, 12
FD = pathlib.Path("/usr/share/fonts/truetype/dejavu")
f_s = ImageFont.truetype(str(FD / "DejaVuSans.ttf"), 13)
f_m = ImageFont.truetype(str(FD / "DejaVuSans.ttf"), 16)
f_mb = ImageFont.truetype(str(FD / "DejaVuSans-Bold.ttf"), 16)
f_code = ImageFont.truetype(str(FD / "DejaVuSansMono.ttf"), 15)
f_big = ImageFont.truetype(str(FD / "DejaVuSans-Bold.ttf"), 22)
f_title = ImageFont.truetype(str(FD / "DejaVuSans-Bold.ttf"), 38)
f_sub = ImageFont.truetype(str(FD / "DejaVuSans.ttf"), 20)
BG, BAR, INK, INK2, MUTED, LINE = (
    (15, 17, 23),
    (34, 35, 42),
    (240, 239, 236),
    (195, 194, 183),
    (143, 142, 134),
    (60, 61, 70),
)
CALL, IMPORT, FOCUS, NODE = (57, 135, 229), (217, 89, 38), (201, 133, 0), (120, 121, 130)


def scan(src: pathlib.Path):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gg-graph-"))
    env = {
        "PYTHONPATH": str(ROOT),
        "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER",
        "GITGALAXY_DISABLE_GIT_HISTORY": "1",
        "PATH": "/usr/bin:/bin",
    }
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--output", str(tmp) + "/"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    g = sqlite3.connect(next(tmp.glob("*_galaxy_graph.sqlite")))
    files = {aid: (fn, lang) for aid, fn, lang in g.execute("SELECT id, filename, language FROM artifacts")}
    funcs = []
    for fid, aid, name, co in g.execute("SELECT id, artifact_id, name, calls_out_to FROM functions"):
        try:
            calls = json.loads(co) if co else []
        except ValueError:
            calls = []
        funcs.append((fid, aid, name, calls))
    imports = [(aid, p) for aid, p in g.execute("SELECT artifact_id, imported_path FROM outbound_dependencies")]
    g.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return files, funcs, imports


def layout(files, funcs, call_edges, imp_edges, rng):
    ids = sorted(files)
    idx = {a: i for i, a in enumerate(ids)}
    n = len(ids)
    A = np.zeros((n, n))
    for a, b in call_edges + imp_edges:
        if a != b:
            A[idx[a], idx[b]] += 1
            A[idx[b], idx[a]] += 1
    nf = np.array([max(1, sum(1 for f in funcs if f[1] == a)) for a in ids], float)
    rad = 14 + 9 * np.sqrt(nf)
    P = rng.normal(size=(n, 2)) * 200
    for it in range(600):
        d = P[:, None, :] - P[None, :, :]
        dist = np.sqrt((d**2).sum(-1)) + 1e-6
        minsep = rad[:, None] + rad[None, :] + 30
        rep = (minsep**2 / dist**2)[..., None] * d / dist[..., None]
        att = (A * dist / 300)[..., None] * d / dist[..., None]
        F = rep.sum(1) - att.sum(1) - P * 0.002
        P += np.clip(F, -20, 20) * (1 - it / 650)
    for _ in range(800):  # remove overlaps: push touching circles apart
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                dv = P[i] - P[j]
                dist = float(np.hypot(*dv)) + 1e-6
                need = rad[i] + rad[j] + 18
                if dist < need:
                    push = (need - dist) / 2 * dv / dist
                    P[i] += push
                    P[j] -= push
                    moved = True
        if not moved:
            break
    P -= P.mean(0)
    s = min((W - 120) / (np.ptp(P[:, 0]) + 2 * rad.max() + 40), (H - 170) / (np.ptp(P[:, 1]) + 2 * rad.max() + 40))
    P *= s
    rad *= s
    fpos = {}
    for a in ids:
        mine = [f for f in funcs if f[1] == a]
        c, r0 = P[idx[a]], rad[idx[a]]
        for k, f in enumerate(mine):  # sunflower inside the file circle
            r = r0 * 0.85 * math.sqrt((k + 0.5) / len(mine))
            th = k * 2.39996
            fpos[f[0]] = c + r * np.array([math.cos(th), math.sin(th)])
    return {a: P[idx[a]] for a in ids}, {a: rad[idx[a]] for a in ids}, fpos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--attribution", default="")
    a = ap.parse_args()
    rng = np.random.default_rng(7)
    files, funcs, imports = scan(pathlib.Path(a.src))
    by_name = defaultdict(list)
    for f in funcs:
        by_name[f[2]].append(f)
    fn_of = {f[0]: f for f in funcs}
    edges = []  # (caller fid, callee fid)
    for fid, aid, name, calls in funcs:
        for c in calls:
            cands = by_name.get(c, [])
            if cands:
                tgt = next((x for x in cands if x[1] == aid), cands[0])
                edges.append((fid, tgt[0]))
    by_file = {fn: aid for aid, (fn, _) in files.items()}
    imp = []
    for aid, p in imports:
        t = by_file.get(pathlib.Path(p).name)
        if t is not None and t != aid:
            imp.append((aid, t))
    call_files = [(fn_of[x][1], fn_of[y][1]) for x, y in edges]
    fc, fr_, fpos = layout(files, funcs, call_files, imp, rng)
    start = next(f for f in funcs if f[2] == a.start)
    hop1 = [y for x, y in edges if x == start[0]]
    hop2 = [y for x, y in edges if x in hop1 and y not in hop1 and y != start[0]]
    sfile = start[1]
    cross = [(x, y) for x, y in edges if fn_of[x][1] != fn_of[y][1]]
    intra = [(x, y) for x, y in edges if fn_of[x][1] == fn_of[y][1]]
    lang = files[sfile][1]

    def cam_for(points, pad=120, minspan=160):
        P = np.array(points)
        c = (P.max(0) + P.min(0)) / 2
        sx, sy = max(np.ptp(P[:, 0]) + pad, minspan), max(np.ptp(P[:, 1]) + pad, minspan)
        return c, min((W - 100) / sx, (H - 190) / sy)

    def circle_pts(aid):
        c, r = fc[aid], fr_[aid]
        return [c + np.array([r, 0]), c - np.array([r, 0]), c + np.array([0, r]), c - np.array([0, r])]

    cams = {
        "start": cam_for([fpos[start[0]]] + [fpos[y] for y in hop1]),
        "hop2": cam_for([fpos[start[0]]] + [fpos[y] for y in hop1 + hop2]),
        "file": cam_for(circle_pts(sfile), pad=40),
        "all": cam_for([p for aid in files for p in circle_pts(aid)], pad=60),
    }

    def ease(t):
        return t * t * (3 - 2 * t)

    def frame(
        cam, drawn_edges, drawn_imp, focus, labels_for, title_lines, stats="", file_labels=False, label_alpha=255
    ):
        c, s = cam
        T = lambda p: ((p[0] - c[0]) * s + W / 2, (p[1] - c[1]) * s + H / 2 - 20)  # noqa: E731
        im = Image.new("RGBA", (W, H), BG)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for aid in files:
            x, y = T(fc[aid])
            r = fr_[aid] * s
            d.ellipse((x - r, y - r, x + r, y + r), outline=LINE + (255,), width=1, fill=(24, 25, 32, 255))
        for (u, v), alpha in drawn_imp:
            p, q = T(fc[u]), T(fc[v])
            for k in range(0, 20, 2):
                a0, a1 = k / 20, (k + 1) / 20
                d.line(
                    (
                        p[0] + (q[0] - p[0]) * a0,
                        p[1] + (q[1] - p[1]) * a0,
                        p[0] + (q[0] - p[0]) * a1,
                        p[1] + (q[1] - p[1]) * a1,
                    ),
                    fill=IMPORT + (alpha,),
                    width=2,
                )
        for (u, v), alpha, col in drawn_edges:
            p, q = T(fpos[u]), T(fpos[v])
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            nx, ny = -(q[1] - p[1]) * 0.15, (q[0] - p[0]) * 0.15
            pts = [
                (
                    (1 - t) ** 2 * p[0] + 2 * (1 - t) * t * (mx + nx) + t * t * q[0],
                    (1 - t) ** 2 * p[1] + 2 * (1 - t) * t * (my + ny) + t * t * q[1],
                )
                for t in [k / 16 for k in range(17)]
            ]
            d.line(pts, fill=col + (alpha,), width=2 if alpha > 120 else 1)
        im = Image.alpha_composite(im, ov)
        d = ImageDraw.Draw(im)
        rdot = max(2.5, min(7, 2.2 * s**0.5 * 2))
        for f in funcs:
            x, y = T(fpos[f[0]])
            if -10 < x < W + 10 and -10 < y < H + 10:
                col = FOCUS if f[0] in focus else NODE
                r = rdot * (1.6 if f[0] in focus else 1)
                d.ellipse((x - r, y - r, x + r, y + r), fill=col)
                if f[0] in labels_for:
                    d.text((x + r + 4, y - 9), f[2] + "()", font=f_code, fill=INK + (label_alpha,))
        if file_labels:
            for aid, (fn, _) in files.items():
                x, y = T(fc[aid])
                d.text((x, y - fr_[aid] * s - 14), fn, font=f_s, fill=INK2, anchor="mm")
        d.rounded_rectangle((20, 14, W - 20, 50), 10, fill=BAR)
        d.text((36, 22), title_lines, font=f_mb, fill=INK)
        d.rounded_rectangle((20, H - 70, W - 20, H - 24), 10, fill=BAR)
        if stats:
            d.text((36, H - 58), stats, font=f_m, fill=INK)
        lg = [("function", NODE), ("call", CALL), ("import / #include", IMPORT)]
        x0 = W - 420
        for i, (t_, cl) in enumerate(lg):
            d.rounded_rectangle((x0 + i * 130, 26, x0 + i * 130 + 12, 38), 3, fill=cl)
            d.text((x0 + i * 130 + 18, 24), t_, font=f_s, fill=INK2)
        if a.attribution:
            d.text((20, H - 18), a.attribution, font=ImageFont.truetype(str(FD / "DejaVuSans.ttf"), 11), fill=MUTED)
        return im

    frames = []
    for i in range(22):
        im = Image.new("RGBA", (W, H), BG)
        d = ImageDraw.Draw(im)
        al = int(255 * min(1, i / 8))
        d.text((W // 2, 300), "From one function to the whole call graph", font=f_title, fill=INK + (al,), anchor="mm")
        d.text(
            (W // 2, 352),
            f"real engine output · {a.label} · {len(files)} files · {len(funcs)} functions",
            font=f_sub,
            fill=INK2 + (al,),
            anchor="mm",
        )
        frames.append(im)
    focus = {start[0]}
    title = f"{start[2]}() in {files[sfile][0]}: what does it call?"
    drawn = []
    for k, y in enumerate(hop1):
        for t in range(8):
            edges_now = drawn + [((start[0], y), int(255 * (t + 1) / 8), CALL)]
            frames.append(
                frame(
                    cams["start"],
                    edges_now,
                    [],
                    focus | {y},
                    focus | set(hop1[: k + 1]),
                    title,
                    f"{start[2]}() calls {', '.join(fn_of[h][2] + '()' for h in hop1[: k + 1])}",
                )
            )
        drawn.append(((start[0], y), 255, CALL))
        focus.add(y)
    frames += [frames[-1]] * 10
    for t in range(14):  # move to hop 2
        u = ease(t / 13)
        cam = (cams["start"][0] * (1 - u) + cams["hop2"][0] * u, cams["start"][1] * (1 - u) + cams["hop2"][1] * u)
        frames.append(frame(cam, drawn, [], focus, focus, "…and what those call (second hop)"))
    for k, (x, y) in enumerate([(x, y) for x, y in edges if x in hop1 and y in hop2]):
        drawn.append(((x, y), 220, CALL))
        focus.add(y)
        frames.append(
            frame(
                cams["hop2"],
                drawn,
                [],
                focus,
                focus,
                "…and what those call (second hop)",
                f"2 hops from {start[2]}(): {len(focus)} functions",
            )
        )
    frames += [frames[-1]] * 10
    in_file = [f[0] for f in funcs if f[1] == sfile]
    for t in range(16):  # zoom to the file
        u = ease(t / 15)
        cam = (cams["hop2"][0] * (1 - u) + cams["file"][0] * u, cams["hop2"][1] * (1 - u) + cams["file"][1] * u)
        frames.append(frame(cam, drawn, [], focus, focus, f"the whole file: {files[sfile][0]}"))
    fintra = [(x, y) for x, y in intra if fn_of[x][1] == sfile]
    for k in range(0, len(fintra), 2):
        es = drawn + [(e, 170, CALL) for e in fintra[: k + 2]]
        frames.append(
            frame(
                cams["file"],
                es,
                [],
                focus,
                focus,
                f"the whole file: {files[sfile][0]}",
                f"{files[sfile][0]}: {len(in_file)} functions · {len(fintra)} calls inside the file",
            )
        )
    frames += [frames[-1]] * 10
    for t in range(22):  # zoom out to everything
        u = ease(t / 21)
        cam = (cams["file"][0] * (1 - u) + cams["all"][0] * u, cams["file"][1] * (1 - u) + cams["all"][1] * u)
        frames.append(
            frame(
                cam,
                drawn + [(e, 170, CALL) for e in fintra],
                [],
                focus,
                set(),
                "zooming out: the whole codebase",
                file_labels=t > 14,
            )
        )
    base_edges = drawn + [(e, 170, CALL) for e in fintra]
    others = [e for e in intra if e not in fintra]
    allc = others + cross
    for k in range(0, len(allc), 8):
        es = base_edges + [(e, 140 if e in cross else 90, CALL) for e in allc[: k + 8]]
        frames.append(
            frame(
                cams["all"],
                es,
                [],
                focus,
                set(),
                "every call the engine resolved",
                f"{min(k + 8, len(allc)) + len(fintra) + len(drawn):,} of {len(edges):,} calls drawn · {len(cross)} cross file boundaries",
                file_labels=True,
            )
        )
    es = base_edges + [(e, 140 if e in cross else 90, CALL) for e in allc]
    for k in range(0, len(imp), 3):
        frames.append(
            frame(
                cams["all"],
                es,
                [(e, 230) for e in imp[: k + 3]],
                focus,
                set(),
                "…and every import (#include) between files",
                f"{min(k + 3, len(imp))} import links",
                file_labels=True,
            )
        )
    final = frame(
        cams["all"],
        es,
        [(e, 230) for e in imp],
        focus,
        set(),
        f"{a.label}: the call and import network GitGalaxy builds",
        f"{lang.upper() if len(lang) <= 3 else lang} · {len(files)} files · {len(funcs)} functions · {len(edges)} resolved calls "
        f"({len(cross)} across files) · {len(imp)} import links",
        file_labels=True,
    )
    frames += [final] * 48
    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-gframes-"))
    for i, im in enumerate(frames):
        im.convert("RGB").save(fdir / f"f{i:04d}.png")
    out = pathlib.Path(a.out)
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
    shutil.copy(fdir / f"f{len(frames) - 1:04d}.png", str(out) + ".png")
    shutil.rmtree(fdir, ignore_errors=True)
    print(
        f"{out}: {len(frames)} frames; {len(files)} files, {len(funcs)} functions, {len(edges)} calls ({len(cross)} cross-file), {len(imp)} imports"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
