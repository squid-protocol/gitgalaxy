#!/usr/bin/env python3
"""Render "One scan, every language" (the README hero) from a REAL scan.

Runs this checkout's engine on a source tree (or reads a scan it already wrote) and draws what happened to every
file: the terminal commands, the tree as one tile per file, then a flow from the files on disk, through each gate
that leaves a file out, into one band per language, and on to the reports the scan wrote.

Every number comes from the scan's own output:
- files on disk, files read and lines of code: the audit report's summary;
- each file left out and its reason: the audit report's "Unparsable Artifacts" queue, sorted into the gate that
  owns the reason (an unknown reason refuses to render);
- files per language: the audit report's composition, with each language's level (split into functions,
  structural rules, recognized only) read from the engine's language registry;
- the reports: the files in the output directory;
- the terminal lines: the scan's own log.

The script refuses to render if the flow does not balance (read + left out != files on disk).

    python scripts/media/scan_flow_explainer.py --src <dir> --label "language-crucible/data" --out docs/media/scan-flow
    python scripts/media/scan_flow_explainer.py --scan-dir <galaxyscope --output dir> --log <scan log> ...

Needs Pillow, numpy and ffmpeg (docs tooling only).
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # scripts/media helpers
from _brand import brand

ROOT = pathlib.Path(__file__).resolve().parents[2]
W, H, FPS = 1280, 720, 12
SS = 2  # supersampling for the static flow layer
FD = pathlib.Path("/usr/share/fonts/truetype/dejavu")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FD / name), size)


f_s = font("DejaVuSans.ttf", 14)
f_sb = font("DejaVuSans-Bold.ttf", 14)
f_m = font("DejaVuSans.ttf", 16)
f_mb = font("DejaVuSans-Bold.ttf", 17)
f_big = font("DejaVuSans-Bold.ttf", 24)
f_title = font("DejaVuSans-Bold.ttf", 30)
f_code = font("DejaVuSansMono.ttf", 17)
f_code_s = font("DejaVuSansMono.ttf", 14)

BG, BAR, INK, INK2, MUTED, LINE = (
    (15, 17, 23),
    (34, 35, 42),
    (240, 239, 236),
    (195, 194, 183),
    (143, 142, 134),
    (60, 61, 70),
)
GREY = (112, 113, 122)
BLUE = (92, 128, 220)
PROMPT = (126, 200, 120)
REPORT = (236, 190, 90)

# --- which gate owns each reason the engine records -------------------------------------------------------------
# Order = the order a file meets the gates (gitgalaxy/core/aperture.py: path gates, then the content gates, then the
# statistical auditor after parsing). A reason no rule claims stops the render: the picture must not guess.
GATES = [
    ("path", "Path rules", "name + extension"),
    ("content", "Content guards", "file contents"),
    ("audit", "Statistical audit", "after parsing"),
]
REASON_GATE = [
    # Gate 1 (aperture.evaluate_path_integrity + the census micro-mass quota): path and extension only
    (r"^CRITICAL LEAK", "path"),
    (r"^AI MODEL WEIGHTS", "path"),
    (r"^Blocked \(File size exceeds absolute", "path"),
    (r"^Blocked \(Explicitly Denied Extension", "path"),
    (r"^Blocked \(System Exclusion", "path"),
    (r"^Blocked \(Unsupported Extension", "path"),
    (r"^Excluded: Neighborhood Micro-Mass", "path"),
    # the worker: content gates (is_in_scope / _check_artifact_integrity), the ReDoS guard, language detection
    (r"^Blocked \(File size exceeds \d+MB limit", "content"),
    (r"^Blocked \(Binary Format", "content"),
    (r"^Blocked \(Monolithic Amalgamation", "content"),
    (r"^Blocked \((Massive )?Static Asset Blob", "content"),
    (r"^Blocked \(Embedded (Hex|Array)", "content"),
    (r"^Blocked \(Saturation", "content"),
    (r"^Blocked \(Machine-Generated", "content"),
    (r"^Blocked \(Lexical Monotony", "content"),
    (r"^Protocol Violation|^Internal Exception", "content"),
    (r"^Unparsable \(Structural Saturation|^Thread Timeout", "content"),
    (r"^Unsupported Format", "content"),
    # Phase 6, metrics/statistical_auditor.py: after a successful parse
    (
        r"^Unresolved Ambiguity|^Pre-filtered Noise|^Zero-Density Threshold|^Packed Payload Guard|^Statistical Anomaly",
        "audit",
    ),
]

# Finer families inside the gates, for the rainbow style's grey breakdown (first match wins; unmatched = "other").
REASON_FAMILY = [
    (r"^Blocked \(System Exclusion", "hidden, ignored, licence or vendored"),
    (r"^Blocked \(Unsupported Extension", "no language claims the extension"),
    (r"^Blocked \(Explicitly Denied Extension", "denied extension (archives, docs)"),
    (r"^CRITICAL LEAK", "exposed secret"),
    (r"^AI MODEL WEIGHTS", "model weights"),
    (r"^Blocked \(Saturation", "minified (very long lines)"),
    (r"^Blocked \(Machine-Generated", "machine-generated code"),
    (r"^Unsupported Format", "format not recognized"),
    (r"^Blocked \(.*(Static Asset Blob|Monolithic|File size)", "oversized data or blob"),
    (r"^Blocked \(Lexical Monotony", "repetitive layout"),
    (r"^Blocked \(Binary|^Blocked \(Embedded", "binary or embedded payload"),
    (r"^Zero-Density|^Unresolved Ambiguity|^Pre-filtered|^Packed Payload|^Statistical Anomaly", "no structural signal"),
]


def family_of(reason: str) -> str:
    for pat, fam in REASON_FAMILY:
        if re.search(pat, reason):
            return fam
    return "other"


REPORTS = [  # (output suffix, what it is)
    ("_galaxy_llm.md", "AI architecture brief", ".md"),
    ("_galaxy_graph.sqlite", "Knowledge graph", ".sqlite"),
    ("_galaxy_master.db", "Full scan database", ".db"),
    ("_galaxy_sarif.json", "SARIF findings", ".json"),
    ("_galaxy_sbom.json", "CycloneDX SBOM", ".json"),
    ("_galaxy_gpu.json", "3D visualizer data", ".json"),
    ("_galaxy_audit.json", "Forensic audit manifest", ".json"),
]

PRETTY = {
    "cobol": "COBOL",
    "jcl": "JCL",
    "php": "PHP",
    "html": "HTML",
    "css": "CSS",
    "sqlite": "SQLite",
    "yaml": "YAML",
    "cpp": "C++",
    "csharp": "C#",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "powershell": "PowerShell",
    "livecode": "LiveCode",
    "hlasm": "HLASM",
    "pli": "PL/I",
    "rexx": "REXX",
    "bms": "BMS",
    "agc_assembly": "AGC assembly",
    "db2_sql": "Db2 SQL",
    "embedded_python": "Embedded Python",
    "objective-c": "Objective-C",
    "matlab": "MATLAB",
    "abap": "ABAP",
    "csd": "CSD",
    "go": "Go",
    "hlo": "HLO",
    "mlir": "MLIR",
    "glsl": "GLSL",
    "nix": "Nix",
    "blp": "Blueprint",
    "td": "TableGen",
    "proto": "Protobuf",
    "m4": "M4",
    "tcl": "Tcl",
    "xml": "XML",
    "json": "JSON",
    "csv": "CSV",
}


def pretty(lang: str) -> str:
    return PRETTY.get(lang, lang.replace("_", " ").capitalize() if len(lang) > 2 else lang.upper())


# --- data ----------------------------------------------------------------------------------------------------------
def run_scan(src: pathlib.Path) -> tuple[pathlib.Path, str]:
    out = pathlib.Path(tempfile.mkdtemp(prefix="gg-flow-"))
    env = {
        "PYTHONPATH": str(ROOT),
        "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER",
        "GITGALAXY_DISABLE_GIT_HISTORY": "1",
        "PATH": "/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    p = subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--output", str(out) + "/"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return out, p.stdout + p.stderr


def language_levels() -> dict[str, str]:
    sys.path.insert(0, str(ROOT))
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    lv = {}
    for name, d in LANGUAGE_DEFINITIONS.items():
        rules = {k: v for k, v in (d.get("rules") or {}).items() if v}  # the registry keeps empty slots
        lv[name] = "split" if rules.get("func_start") else ("structural" if rules else "recognized")
    return lv


def gate_of(reason: str) -> str:
    for pat, g in REASON_GATE:
        if re.search(pat, reason):
            return g
    raise SystemExit(f"refusing to render: no gate claims the exclusion reason {reason!r}")


def load(scan_dir: pathlib.Path, log: str) -> dict:
    audit_path = next(scan_dir.glob("*_galaxy_audit.json"))
    stem = audit_path.name[: -len("_galaxy_audit.json")]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    summ = audit["2. Global Ecosystem Summary"]["summary"]
    eco = audit["2. Global Ecosystem Summary"].get("ecosystem_audits") or {}
    comp = audit["2. Global Ecosystem Summary"]["composition"]
    queue = audit["5. Unparsable Artifacts (Excluded Artifacts Queue)"]

    gates = {g: 0 for g, _, _ in GATES}
    families: dict[tuple[str, str], int] = {}
    for e in queue:
        gk = gate_of(e["Diagnostic Reason"])
        gates[gk] += 1
        key = (gk, family_of(e["Diagnostic Reason"]))
        families[key] = families.get(key, 0) + 1

    levels = language_levels()
    langs = []
    for name, v in comp.items():
        n = int(v["files"])
        if n <= 0:
            continue
        lvl = levels.get(name)
        if lvl is None:
            lvl = "special"  # an engine lane, not a language (e.g. model weights): drawn on its own
        langs.append({"lang": name, "files": n, "loc": int(v.get("loc", 0)), "level": lvl})
    langs.sort(key=lambda x: (-x["files"], x["lang"]))

    total, read = int(summ["total_files"]), int(summ["verified_files"])
    left = sum(gates.values())
    if read + left != total:
        raise SystemExit(f"refusing to render: read {read} + left out {left} != files on disk {total}")
    if sum(x["files"] for x in langs) != read:
        raise SystemExit(f"refusing to render: languages sum to {sum(x['files'] for x in langs)}, not {read}")

    reports = []
    for suffix, what, ext in REPORTS:
        f = scan_dir / (stem + suffix)
        if f.exists():
            reports.append({"name": stem + suffix, "suffix": suffix, "what": what, "ext": ext})
    m = re.search(r"PIPELINE_SUCCESS: ([\d,]+) files mapped in ([\d.]+)s", log)
    if not m or int(m.group(1).replace(",", "")) != read:
        raise SystemExit("refusing to render: the log's PIPELINE_SUCCESS line is missing or disagrees with the audit")
    return {
        "total": total,
        "read": read,
        "loc": int(summ["total_loc"]),
        "gates": gates,
        "langs": langs,
        "reports": reports,
        "seconds": float(m.group(2)),
        "log": log,
        "n_lang": sum(1 for x in langs if x["level"] != "special"),
        "files": per_file(scan_dir, total, read),
        # the two passes that walk the disk themselves, so they still see left-out files (repo-level counts only)
        "xray": (eco.get("xray") or {}).get("anomalies_found"),
        "api": (eco.get("api_mapper") or {}).get("shadow_count"),
        "api_ghost": (eco.get("api_mapper") or {}).get("ghost_count"),
        "families": sorted(
            ({"gate": g, "family": f, "n": n} for (g, f), n in families.items()),
            key=lambda x: ([k for k, _, _ in GATES].index(x["gate"]), -x["n"]),
        ),
        "wall": clock(log)[0],
        "stages": clock(log)[1],
        "line_times": line_times(log),
    }


def line_times(log: str) -> dict[str, float]:
    """Clock time of each terminal line (same trimming as log_lines), so a line appears when the scan wrote it."""
    t0, out = None, {}
    for line in log.splitlines():
        t = _ts(line)
        if t is None:
            continue
        t0 = t if t0 is None else t0
        for msg in log_lines(line, ""):
            out[msg] = t - t0
    return out


def per_file(scan_dir: pathlib.Path, total: int, read: int) -> list[tuple[str, str | None]]:
    """Every file on disk as (path, language), language None when the scan left it out: the master database."""
    db = sqlite3.connect(f"file:{next(scan_dir.glob('*_galaxy_master.db'))}?mode=ro", uri=True)
    got = [(p, lang) for p, lang in db.execute("SELECT file_path, language FROM file_data")]
    left = [(p, None) for (p,) in db.execute("SELECT file_path FROM excluded_artifacts")]
    db.close()
    if len(got) != read or len(got) + len(left) != total:
        raise SystemExit(
            f"refusing to render: database has {len(got)} read + {len(left)} left out, audit {read}/{total}"
        )
    return sorted(got + left)


# what the engine is doing, keyed on the log line that starts each stage (plain words for the progress bar)
STAGES = [
    (r"Aperture Filter Online", "starting the engine"),
    (r"PIPELINE_START", "census of the files"),
    (r"PASS_1: ", "reading every file"),
    (r"PASS_1\.5: Resolving", "resolving import and call graphs"),
    (r"PASS_2: Calculating", "scoring structure"),
    (r"Phase 10: ", "security audits"),
    (r"SQLITE: Generating", "writing the reports"),
    (r"PIPELINE_SUCCESS", "done"),
]
_TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) ")


def _ts(line: str) -> float | None:
    import datetime as _dt

    m = _TS.match(line)
    if not m:
        return None
    return _dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + int(m.group(2)) / 1000


def clock(log: str) -> tuple[float, list[tuple[float, str]], dict[str, float]]:
    """Wall-clock seconds from the engine's first log line to PIPELINE_SUCCESS, each stage's start on that clock,
    and the clock time of every kept terminal line. All read from the log's timestamps."""
    t0, stages, end = None, [], None
    for line in log.splitlines():
        t = _ts(line)
        if t is None:
            continue
        t0 = t if t0 is None else t0
        for pat, label in STAGES:
            if re.search(pat, line) and not any(lbl == label for _, lbl in stages):
                stages.append((t - t0, label))
        if "PIPELINE_SUCCESS" in line:
            end = t - t0
    if t0 is None or end is None:
        raise SystemExit("refusing to render: the log has no timestamps or no PIPELINE_SUCCESS line")
    return end, stages, {}


def log_lines(log: str, label: str) -> list[str]:
    """The scan's own log, trimmed to the lines a reader can follow (timestamps and logger names dropped)."""
    keep = [
        r"CENSUS_COMPLETE",
        r"PASS_1: ",
        r"PASS_1\.5: Resolving",
        r"PASS_2: Calculating",
        r"Audit Success",
        r"LLM: Generating",
        r"PIPELINE_SUCCESS",
    ]
    out = []
    for line in log.splitlines():
        if any(re.search(k, line) for k in keep):
            msg = re.sub(r"^\S+ \S+ \[\w+\] \[[^\]]+\] ", "", line).strip()
            msg = re.sub(r" via ProcessPoolExecutor| via O\(1\) Pre-computed Suffix Hash Maps", "", msg)
            msg = re.sub(r"(->|sealed ->) \S+", "", msg).strip()
            if len(msg) > 74:
                msg = msg[:73] + "…"
            out.append(msg)
    return out


# --- colours ---------------------------------------------------------------------------------------------------------
def rainbow(i: int, n: int) -> tuple[int, int, int]:
    h = 0.0 + 0.80 * (i / max(1, n - 1))  # red -> violet, like the original diagram
    r, g, b = colorsys.hls_to_rgb(h, 0.60, 0.78)
    return int(r * 255), int(g * 255), int(b * 255)


# --- flow model --------------------------------------------------------------------------------------------------------
TOP_LANGS = 11


def build_flow(d: dict) -> dict:
    """Node bars (x, y0, y1) and ribbons between them, in 1x pixels. Ribbon thickness = files (a floor keeps a
    one-file flow visible; its label carries the real number)."""
    y_top, y_bot = 170, 680
    scale = (y_bot - y_top) / d["total"]

    def px(n):
        return max(2.0, n * scale) if n else 0.0

    x = dict(src=120, read=560, lang=690, eng=1010, rep=1020, left=640)
    gx = [215, 330, 445]
    nodes, ribbons = {}, []
    nodes["src"] = (x["src"], y_top, y_bot)
    left_y = 58
    nodes["left"] = (x["left"], left_y, left_y + max(8.0, sum(px(d["gates"][g]) for g, _, _ in GATES)))
    top, bot, prev_x, ly = y_top, y_bot, x["src"], left_y
    for i, ((g, _, _), gxi) in enumerate(zip(GATES, gx)):
        n = d["gates"][g]
        h = px(n)
        ribbons.append(
            {
                "from": (top, bot),
                "to": (top, bot),
                "x0": prev_x + 8,
                "x1": gxi,
                "color": BLUE,
                "n": int(round((bot - top) / scale)),
                "kind": "main",
            }
        )
        nodes[f"g{i}"] = (gxi, top, bot)
        ribbons.append(
            {
                "from": (top, top + h),
                "to": (ly, ly + h),
                "x0": gxi + 4,
                "x1": x["left"],
                "color": GREY,
                "n": n,
                "kind": "left",
            }
        )
        ly += h
        top += h
        prev_x = gxi
    ribbons.append(
        {
            "from": (top, bot),
            "to": (top, bot),
            "x0": prev_x + 4,
            "x1": x["read"],
            "color": BLUE,
            "n": d["read"],
            "kind": "main",
        }
    )
    nodes["read"] = (x["read"], top, bot)

    code = [v for v in d["langs"] if v["level"] == "split"]
    shown, rest = code[:TOP_LANGS], code[TOP_LANGS:]
    bands = [
        {"label": pretty(v["lang"]), "n": v["files"], "color": rainbow(i, TOP_LANGS + 1)} for i, v in enumerate(shown)
    ]
    if rest:
        bands.append(
            {
                "label": f"{len(rest)} more languages",
                "n": sum(v["files"] for v in rest),
                "color": rainbow(TOP_LANGS, TOP_LANGS + 1),
                "sub": "read to the function",
            }
        )
    for lvl, sub, colr in (
        ("structural", "structure only", (150, 160, 178)),
        ("recognized", "counted only", (112, 118, 134)),
    ):
        grp = [v for v in d["langs"] if v["level"] == lvl]
        if grp:
            names = ", ".join(pretty(v["lang"]) for v in grp[:2]) + (f" +{len(grp) - 2}" if len(grp) > 2 else "")
            bands.append({"label": names, "n": sum(v["files"] for v in grp), "color": colr, "sub": sub})

    for v in d["langs"]:
        if v["level"] == "special":
            bands.append(
                {
                    "label": "Model weights" if "binary" in v["lang"] else pretty(v["lang"]),
                    "n": v["files"],
                    "color": (205, 130, 190),
                    "sub": "header audit",
                }
            )

    slot, lang_top, lang_bot = 19.0, 100, 660
    heights = [max(px(b["n"]), 0) for b in bands]
    adv = [max(h, slot) for h in heights]
    gap = max(2.0, min(6.0, (lang_bot - lang_top - sum(adv)) / max(1, len(bands) - 1)))
    y = lang_top + (lang_bot - lang_top - sum(adv) - gap * (len(bands) - 1)) / 2
    ry = ey = nodes["read"][1]
    for b, h, a in zip(bands, heights, adv):
        b["y0"] = y + (a - h) / 2
        b["y1"] = b["y0"] + h
        k = b["n"] * scale
        ribbons.append(
            {
                "from": (ry, ry + k),
                "to": (b["y0"], b["y1"]),
                "x0": x["read"] + 8,
                "x1": x["lang"],
                "color": b["color"],
                "n": b["n"],
                "kind": "lang",
            }
        )
        ribbons.append(
            {
                "from": (b["y0"], b["y1"]),
                "to": (ey, ey + k),
                "x0": x["lang"] + 8,
                "x1": x["eng"],
                "color": b["color"],
                "n": b["n"],
                "kind": "eng",
            }
        )
        ry += k
        ey += k
        y += a + gap
    nodes["eng"] = (x["eng"], nodes["read"][1], ey)
    return {"nodes": nodes, "ribbons": ribbons, "bands": bands, "x": x, "gx": gx, "scale": scale}


def build_flow_rainbow(d: dict) -> dict:
    """Rainbow style: the left part to scale (files), then every language as its own equal stripe, red -> violet,
    running straight to the engine. Stripes are equal on purpose so every name fits; each label carries the count."""
    y_top, y_bot = 175, 688
    scale = (y_bot - y_top) / d["total"]
    x = {"src": 100, "read": 420, "lang": 540, "eng": 1004, "rep": 1014, "left": 452}
    gx = [175, 255, 335]
    nodes, ribbons = {}, []
    nodes["src"] = (x["src"], y_top, y_bot)
    left_total = sum(d["gates"].values())
    left_y = 58
    nodes["left"] = (x["left"], left_y, left_y + max(8.0, left_total * scale))
    top, prev_x, ly = y_top, x["src"], left_y
    for i, ((g, _, _), gxi) in enumerate(zip(GATES, gx, strict=True)):
        n = d["gates"][g]
        h = n * scale
        ribbons.append(
            {
                "from": (top, y_bot),
                "to": (top, y_bot),
                "x0": prev_x + 8,
                "x1": gxi,
                "color": BLUE,
                "n": int(round((y_bot - top) / scale)),
                "kind": "main",
            }
        )
        nodes[f"g{i}"] = (gxi, top, y_bot)
        ribbons.append(
            {
                "from": (top, top + max(h, 1.5)),
                "to": (ly, ly + max(h, 1.5)),
                "x0": gxi + 4,
                "x1": x["left"],
                "color": GREY,
                "n": n,
                "kind": "left",
            }
        )
        ly += h
        top += h
        prev_x = gxi
    ribbons.append(
        {
            "from": (top, y_bot),
            "to": (top, y_bot),
            "x0": prev_x + 4,
            "x1": x["read"],
            "color": BLUE,
            "n": d["read"],
            "kind": "main",
        }
    )
    nodes["read"] = (x["read"], top, y_bot)

    # grey breakdown: the collector fans into one row per reason family (rows equal, labels carry counts)
    fams = d["families"]
    fy0, fstep = 52, 11.0
    fx = x["left"] + 70
    fam_rows = []
    cy = nodes["left"][1]
    for i, fm in enumerate(fams):
        h = fm["n"] * scale
        y0 = fy0 + i * fstep
        fam_rows.append({**fm, "y": y0 + fstep / 2, "x": fx})
        ribbons.append(
            {
                "from": (cy, cy + max(h, 1.0)),
                "to": (y0 + 2, y0 + fstep - 2),
                "x0": x["left"] + 8,
                "x1": fx,
                "color": GREY,
                "n": fm["n"],
                "kind": "fam",
            }
        )
        cy += h

    # one stripe per language: code languages first (rainbow), then structure-only, counted-only, special lanes
    order = {"split": 0, "structural": 1, "recognized": 2, "special": 3}
    langs = sorted(d["langs"], key=lambda v: (order[v["level"]], -v["files"], v["lang"]))
    n = len(langs)
    lt, lb = 176, 668
    step = (lb - lt) / n
    bands = []
    ry = nodes["read"][1]
    for i, v in enumerate(langs):
        y0 = lt + i * step
        colr = rainbow(i, n)
        if v["level"] != "split":  # non-code formats keep their hue but are muted, so the level still reads
            colr = tuple(int(c * 0.55 + 70) for c in colr)
        name = "Model weights \u21ba" if v["level"] == "special" and "binary" in v["lang"] else pretty(v["lang"])
        b = {
            "lang": v["lang"],
            "label": name,
            "n": v["files"],
            "color": colr,
            "y0": y0,
            "y1": y0 + step,
            "level": v["level"],
            "col": i % 3,
        }
        bands.append(b)
        k = v["files"] * scale
        ribbons.append(
            {
                "from": (ry, ry + k),
                "to": (y0, y0 + step),
                "x0": x["read"] + 8,
                "x1": x["lang"],
                "color": colr,
                "n": v["files"],
                "kind": "lang",
            }
        )
        ribbons.append(
            {
                "from": (y0, y0 + step),
                "to": (y0, y0 + step),
                "x0": x["lang"] + 10,
                "x1": x["eng"],
                "color": colr,
                "n": v["files"],
                "kind": "stripe",
            }
        )
        ry += k
    nodes["eng"] = (x["eng"], lt, lb)
    groups = {}
    for b in bands:
        groups.setdefault(b["level"], [b["y0"], b["y1"]])
        groups[b["level"]][1] = b["y1"]
    return {
        "nodes": nodes,
        "ribbons": ribbons,
        "bands": bands,
        "x": x,
        "gx": gx,
        "scale": scale,
        "fams": fam_rows,
        "groups": groups,
        "style": "rainbow",
        "security": [],
    }


def smooth(t):
    return t * t * (3 - 2 * t)


def ribbon_poly(r, k=SS, steps=48):
    (a0, a1), (b0, b1) = r["from"], r["to"]
    x0, x1 = r["x0"], r["x1"]
    top, bot = [], []
    for i in range(steps + 1):
        t = i / steps
        s = smooth(t)
        x = x0 + (x1 - x0) * t
        top.append((x * k, (a0 + (b0 - a0) * s) * k))
        bot.append((x * k, (a1 + (b1 - a1) * s) * k))
    return top + bot[::-1]


def ribbon_point(r, t):
    (a0, a1), (b0, b1) = r["from"], r["to"]
    s = smooth(t)
    return r["x0"] + (r["x1"] - r["x0"]) * t, ((a0 + a1) / 2) + (((b0 + b1) / 2) - ((a0 + a1) / 2)) * s


def tint(c, a):
    return tuple(int(BG[i] + (c[i] - BG[i]) * a) for i in range(3))


# --- static layers -----------------------------------------------------------------------------------------------------
def draw_flow_layer(d, fl) -> Image.Image:
    big = Image.new("RGB", (W * SS, H * SS), BG)
    g = ImageDraw.Draw(big)
    for r in fl["ribbons"]:
        alpha = {"main": 0.30, "left": 0.55, "lang": 0.40, "eng": 0.40, "fam": 0.5, "stripe": 0.62}[r["kind"]]
        g.polygon(ribbon_poly(r), fill=tint(r["color"], alpha))
    for key, (x, y0, y1) in fl["nodes"].items():
        w = 12 if key == "eng" else (4 if key.startswith("g") else 8)
        colr = {"left": GREY, "eng": INK}.get(key, BLUE)
        if key.startswith("g"):
            colr = tint(INK2, 0.6)
        g.rectangle([x * SS, y0 * SS, (x + w) * SS, max(y1, y0 + 2) * SS], fill=colr)
    for b in fl["bands"]:
        g.rectangle(
            [fl["x"]["lang"] * SS, b["y0"] * SS, (fl["x"]["lang"] + 10) * SS, max(b["y1"], b["y0"] + 2) * SS],
            fill=b["color"],
        )
    for fm in fl.get("fams", []):
        g.rectangle([fm["x"] * SS, (fm["y"] - 3.5) * SS, (fm["x"] + 6) * SS, (fm["y"] + 3.5) * SS], fill=GREY)
    return big.resize((W, H), Image.LANCZOS)


def report_rows(d, fl):
    n = len(d["reports"])
    y0, y1 = fl["nodes"]["eng"][1] + 14, fl["nodes"]["eng"][2] - 14
    return [(rep, y0 + (y1 - y0) * (i + 0.5) / n) for i, rep in enumerate(d["reports"])]


def draw_labels(im: Image.Image, d, fl, reveal_x: float):
    g = ImageDraw.Draw(im)
    halo = {"stroke_width": 3, "stroke_fill": BG}

    def show(x):
        return reveal_x >= x

    xs = fl["x"]
    sx, sy0, sy1 = fl["nodes"]["src"]
    if show(sx):
        g.text((sx - 14, (sy0 + sy1) / 2 - 14), f"{d['total']:,}", font=f_big, fill=INK, anchor="rm")
        g.text((sx - 14, (sy0 + sy1) / 2 + 12), "files on disk", font=f_s, fill=INK2, anchor="rm")
    for i, ((gk, title, sub), x) in enumerate(zip(GATES, fl["gx"])):
        if show(x):
            ty = 228 + i * 62
            g.text((x + 2, ty), title, font=f_sb, fill=INK, anchor="mm", **halo)
            g.text((x + 2, ty + 19), f"−{d['gates'][gk]:,} files", font=f_s, fill=INK2, anchor="mm", **halo)
            g.text((x + 2, ty + 37), sub, font=f_s, fill=MUTED, anchor="mm", **halo)
    lx, ly0, _ = fl["nodes"]["left"]
    if show(lx):
        left = sum(d["gates"].values())
        g.text((lx + 18, ly0 - 4), f"{left:,} left out, each with its reason", font=f_sb, fill=INK2, anchor="lt")
        g.text(
            (lx + 18, ly0 + 15),
            "listed one by one in the audit manifest and the database",
            font=f_s,
            fill=MUTED,
            anchor="lt",
        )
    rx, ry0, ry1 = fl["nodes"]["read"]
    if show(rx):
        cy = (ry0 + ry1) / 2
        g.text((rx - 12, cy - 16), f"{d['read']:,}", font=f_big, fill=INK, anchor="rm", **halo)
        g.text((rx - 12, cy + 10), "files read", font=f_s, fill=INK2, anchor="rm", **halo)
        g.text((rx - 12, cy + 28), f"{d['loc'] / 1e6:.2f}M lines of code", font=f_s, fill=MUTED, anchor="rm", **halo)
    if show(xs["lang"]):
        for b in fl["bands"]:
            cy = (b["y0"] + b["y1"]) / 2
            txt = f"{b['label']}  {b['n']:,}"
            g.text((xs["lang"] + 14, cy), txt, font=f_sb, fill=INK, anchor="lm", **halo)
            if b.get("sub"):
                tw = g.textlength(txt + "  ", font=f_sb)
                g.text((xs["lang"] + 14 + tw, cy), b["sub"], font=f_s, fill=INK2, anchor="lm", **halo)
    ex, ey0, _ = fl["nodes"]["eng"]
    if show(ex):
        g.text((ex + 6, ey0 - 32), "one engine", font=f_sb, fill=INK, anchor="mm")
        g.text((ex + 6, ey0 - 14), "one signal set", font=f_s, fill=MUTED, anchor="mm")
        for rep, y in report_rows(d, fl):
            g.line([(ex + 16, y), (xs["rep"] + 20, y)], fill=REPORT, width=2)
            g.polygon([(xs["rep"] + 20, y - 5), (xs["rep"] + 28, y), (xs["rep"] + 20, y + 5)], fill=REPORT)
            g.text((xs["rep"] + 34, y - 9), rep["what"], font=f_sb, fill=INK, anchor="lm")
            g.text((xs["rep"] + 34, y + 9), rep["name"], font=f_code_s, fill=MUTED, anchor="lm")


def draw_labels_rainbow(im: Image.Image, d, fl, reveal_x: float):
    g = ImageDraw.Draw(im)
    halo = {"stroke_width": 3, "stroke_fill": BG}
    f_lab = font("DejaVuSans-Bold.ttf", 12)
    f_cnt = font("DejaVuSans.ttf", 12)
    f_fam = font("DejaVuSans.ttf", 11)

    def show(x):
        return reveal_x >= x

    xs = fl["x"]
    sx, sy0, sy1 = fl["nodes"]["src"]
    if show(sx):
        g.text((sx - 12, (sy0 + sy1) / 2 - 14), f"{d['total']:,}", font=f_big, fill=INK, anchor="rm")
        g.text((sx - 12, (sy0 + sy1) / 2 + 12), "files on disk", font=f_s, fill=INK2, anchor="rm")
    for i, ((gk, title, sub), x) in enumerate(zip(GATES, fl["gx"], strict=True)):
        if show(x):
            ty = 232 + i * 62
            g.text((x + 2, ty), title, font=f_lab, fill=INK, anchor="mm", **halo)
            g.text((x + 2, ty + 17), f"\u2212{d['gates'][gk]:,} files", font=f_cnt, fill=INK2, anchor="mm", **halo)
            g.text((x + 2, ty + 33), sub, font=f_cnt, fill=MUTED, anchor="mm", **halo)
    lx, ly0, ly1 = fl["nodes"]["left"]
    if show(lx):
        g.text((lx - 6, ly0 - 2), f"{sum(d['gates'].values()):,} left out", font=f_lab, fill=INK2, anchor="rt", **halo)
        g.text((lx - 6, ly0 + 14), "every one listed", font=f_cnt, fill=MUTED, anchor="rt", **halo)
        g.text((lx - 6, ly0 + 29), "with its reason", font=f_cnt, fill=MUTED, anchor="rt", **halo)
        for fm in fl["fams"]:
            g.text((fm["x"] + 12, fm["y"]), f"{fm['n']:>3}  {fm['family']}", font=f_fam, fill=INK2, anchor="lm")
    rx, ry0, ry1 = fl["nodes"]["read"]
    if show(rx):
        cy = (ry0 + ry1) / 2
        g.text((rx - 10, cy - 16), f"{d['read']:,}", font=f_big, fill=INK, anchor="rm", **halo)
        g.text((rx - 10, cy + 10), "files read", font=f_s, fill=INK2, anchor="rm", **halo)
        g.text((rx - 10, cy + 28), f"{d['loc'] / 1e6:.2f}M lines", font=f_s, fill=MUTED, anchor="rm", **halo)
    if show(xs["lang"]):
        cols = [xs["lang"] + 22, xs["lang"] + 172, xs["lang"] + 322]
        for b in fl["bands"]:
            cy = (b["y0"] + b["y1"]) / 2
            x0 = cols[b["col"]]
            g.text((x0, cy), b["label"], font=f_lab, fill=INK, anchor="lm", **halo)
            tw = g.textlength(b["label"] + " ", font=f_lab)
            g.text((x0 + tw, cy), f"{b['n']:,}", font=f_cnt, fill=INK2, anchor="lm", **halo)
        for lvl, text in (
            ("structural", "structure only"),
            ("recognized", "counted only"),
            ("special", "\u21ba header audit, put back"),
        ):
            if lvl in fl["groups"]:
                y0, y1 = fl["groups"][lvl]
                x0 = xs["lang"] - 6
                g.line([(x0, y0 + 1), (x0 - 5, y0 + 1), (x0 - 5, y1 - 1), (x0, y1 - 1)], fill=INK2, width=1)
                g.text((x0 - 9, (y0 + y1) / 2), text, font=f_cnt, fill=INK2, anchor="rm", **halo)
        g.text(
            (xs["eng"] - 4, fl["bands"][0]["y0"] - 6),
            f"{d['n_lang']} languages and formats, one stripe each  ·  stripes equal, numbers are files",
            font=f_cnt,
            fill=MUTED,
            anchor="rb",
            **halo,
        )
    ex, ey0, _ = fl["nodes"]["eng"]
    if show(ex):
        g.text((ex + 6, ey0 - 22), "one engine", font=f_sb, fill=INK, anchor="mb", **halo)
        for rep, y in report_rows(d, fl):
            g.line([(ex + 16, y), (xs["rep"] + 20, y)], fill=REPORT, width=2)
            g.polygon([(xs["rep"] + 20, y - 5), (xs["rep"] + 28, y), (xs["rep"] + 20, y + 5)], fill=REPORT)
            g.text((xs["rep"] + 34, y - 9), rep["what"], font=f_sb, fill=INK, anchor="lm")
            g.text((xs["rep"] + 34, y + 9), rep["name"], font=f_code_s, fill=MUTED, anchor="lm")
    for arrow in fl["security"]:
        if show(arrow["x_show"]):
            arrow["draw"](g)


# --- scenes --------------------------------------------------------------------------------------------------------------
def terminal_frames(d, label, real_at) -> tuple[list[Image.Image], int]:
    cmd1 = "pip install gitgalaxy"
    cmd2 = f"galaxyscope {label}/"
    keep = ("CENSUS_COMPLETE", "PASS_1: ", "PASS_1.5: Resolving", "PASS_2: Calc", "Audit Success", "PIPELINE_SUCCESS")
    lines = [ln for ln in log_lines(d["log"], label) if ln.lstrip("- ").startswith(keep)]
    ver = d.get("version", "")
    tf, tf_s = font("DejaVuSansMono.ttf", 22), font("DejaVuSansMono.ttf", 18)
    frames = []

    def term(state):
        im = Image.new("RGB", (W, H), BG)
        g = ImageDraw.Draw(im)
        x0, y0, x1, y1 = 150, 170, 1130, 560
        g.rounded_rectangle([x0, y0, x1, y1], 14, fill=(22, 24, 31), outline=LINE)
        g.rounded_rectangle([x0, y0, x1, y0 + 38], 14, fill=BAR)
        g.rectangle([x0, y0 + 24, x1, y0 + 38], fill=BAR)
        for i, c in enumerate([(236, 95, 90), (240, 190, 80), (110, 200, 100)]):
            g.ellipse([x0 + 18 + i * 24, y0 + 12, x0 + 32 + i * 24, y0 + 26], fill=c)
        y = y0 + 66
        for kind, text in state:
            if kind == "cmd":
                g.text((x0 + 30, y), "$", font=tf, fill=PROMPT)
                g.text((x0 + 58, y), text, font=tf, fill=INK)
                y += 38
            elif kind == "gap":
                y += 14
            else:
                g.text((x0 + 30, y), text, font=tf_s, fill=INK2 if kind == "ok" else MUTED)
                y += 30
        return im

    def typing(state, cmd):
        out = []
        for i in range(0, len(cmd) + 1, 2):
            out.append(term(state + [("cmd", cmd[:i] + "▌")]))
        return out

    state = []
    frames += typing(state, cmd1)
    state.append(("cmd", cmd1))
    frames += [term(state)] * 3
    state.append(("ok", f"Successfully installed gitgalaxy{'-' + ver if ver else ''}"))
    frames += [term(state)] * 5
    state.append(("gap", ""))
    frames += typing(state, cmd2)
    state.append(("cmd", cmd2))
    enter = len(frames)
    for k in range(TERM_HOLD):
        real = real_at(enter + k)
        shown = [
            ("ok" if "PIPELINE_SUCCESS" in ln else "log", ln.strip("- ").strip())
            for ln in lines
            if d["line_times"].get(ln, 1e9) <= real
        ]
        frames.append(term(state + shown))
    return frames, enter


TERM_HOLD = 26
HOLD = 180  # final screen: 15 s to take it in


def lang_colours(fl, d) -> dict[str, tuple]:
    """Each language's colour = the colour of its band in the flow (so a tile and its band match)."""
    if all("lang" in b for b in fl["bands"]):
        return {b["lang"]: b["color"] for b in fl["bands"]}
    colour = {}
    code = [v["lang"] for v in d["langs"] if v["level"] == "split"]
    for i, b in enumerate(fl["bands"]):
        b["_i"] = i
    named = {b["label"]: b["color"] for b in fl["bands"]}
    rest_colour = next((b["color"] for b in fl["bands"] if b["label"].endswith("more languages")), INK2)
    for lang in code:
        colour[lang] = named.get(pretty(lang), rest_colour)
    for v in d["langs"]:
        if v["level"] in ("structural", "recognized", "special"):
            colour[v["lang"]] = next(
                b["color"]
                for b in fl["bands"]
                if b.get("sub")
                == {"structural": "structure only", "recognized": "counted only", "special": "header audit"}[v["level"]]
            )
    return colour


def file_grid(d, fl):
    """One tile per file on disk, grouped into its top-level folder (shelf-packed blocks), coloured by its language."""
    colour = lang_colours(fl, d)
    folders: dict[str, list] = {}
    for path, lang in d["files"]:
        top = path.split("/", 1)[0] if "/" in path else "(root)"
        folders.setdefault(top, []).append(GREY if lang is None else colour.get(lang, INK2))
    blocks = sorted(folders.items(), key=lambda kv: -len(kv[1]))
    pad, area_w, x_org, y_org, y_max = 12, 1170, 55, 140, 668

    def pack(cell):
        placed, x, y, row_h = [], x_org, y_org, 0
        for name, tiles in blocks:
            cols = max(2, int(math.ceil(math.sqrt(len(tiles) * 1.6))))
            bw, bh = cols * cell, int(math.ceil(len(tiles) / cols)) * cell
            if x + bw > x_org + area_w:
                x, y, row_h = x_org, y + row_h + pad + 14, 0
            placed.append({"name": name, "tiles": tiles, "x": x, "y": y + 14, "cols": cols, "w": bw, "h": bh})
            x += bw + pad
            row_h = max(row_h, bh)
        return placed, y + 14 + row_h

    cell = 12
    placed, bottom = pack(cell)
    while bottom > y_max and cell > 4:  # largest tile that fits above the progress bar
        cell -= 1
        placed, bottom = pack(cell)
    return placed, cell


def grid_frames(d, fl, label) -> list[Image.Image]:
    placed, cell = file_grid(d, fl)
    sx, sy0, sy1 = fl["nodes"]["src"]
    tiles = [(blk, i, c) for blk in placed for i, c in enumerate(blk["tiles"])]
    n = len(tiles)
    # pour order: by final destination (left out first, matching the flow's top), so the bar stacks like the flow
    order = sorted(range(n), key=lambda k: (tiles[k][2] != GREY, tiles[k][0]["y"], tiles[k][0]["x"]))
    land = {k: sy0 + (sy1 - sy0) * r / n for r, k in enumerate(order)}
    n_in, n_col, n_pour = 14, 16, 14
    frames = []

    def tile_xy(blk, i):
        return blk["x"] + (i % blk["cols"]) * cell, blk["y"] + (i // blk["cols"]) * cell

    for f in range(n_in + n_col + n_pour):
        im = Image.new("RGB", (W, H), BG)
        g = ImageDraw.Draw(im)
        if f < n_in + n_col:
            t_in = smooth(min(1, f / (n_in - 2)))
            t_col = smooth(max(0, min(1, (f - n_in) / (n_col - 4))))
            g.text((60, 48), label, font=f_title, fill=INK, anchor="lt")
            sub = f"{d['total']:,} files in {len(placed)} folders"
            if t_col > 0:
                sub += "  ·  each tile coloured by the language the scan reads it as, grey if left out"
            g.text((60, 94), sub, font=f_m, fill=INK2, anchor="lt")
            for blk in placed:
                if blk["w"] >= 42:
                    g.text(
                        (blk["x"], blk["y"] - 3),
                        blk["name"][: max(3, blk["w"] // 8)],
                        font=font("DejaVuSans.ttf", 11),
                        fill=tint(MUTED, t_in),
                        anchor="lb",
                    )
                shown = int(len(blk["tiles"]) * t_in)
                for i in range(shown):
                    x, y = tile_xy(blk, i)
                    base = tint(INK2, 0.45)
                    c = blk["tiles"][i]
                    c = tuple(int(base[k] + (c[k] - base[k]) * t_col) for k in range(3))
                    g.rectangle([x, y, x + cell - 2, y + cell - 2], fill=c)
        else:
            t = smooth((f - n_in - n_col) / (n_pour - 1))
            g.text((60, 48), label, font=f_title, fill=tint(INK, 1 - t), anchor="lt")
            for k, (blk, i, c) in enumerate(tiles):
                x, y = tile_xy(blk, i)
                lx, ly = sx + 1, land[k]
                cx, cy = x + (lx - x) * t, y + (ly - y) * t
                s = (cell - 2) * (1 - t) + 2 * t
                g.rectangle([cx, cy, cx + s, cy + s], fill=c)
        frames.append(im)
    return frames


def particles_for(fl, rng):
    parts = []
    for r in fl["ribbons"]:
        k = max(1, int(round(math.sqrt(r["n"]) / 2.2)))
        for _ in range(k):
            parts.append((r, rng.random(), 0.45 + rng.random() * 0.5))
    return parts


def security_overlay(d, fl) -> list[dict]:
    """Rainbow style: what still happens to left-out files. Only X-Ray (binary sweep) and the API map walk the disk
    themselves, so they see most left-out files; each yields one repo-level count that lands in the audit manifest,
    the database and the brief (never SARIF). SAST and SARIF see read files only."""
    if d.get("xray") is None and d.get("api") is None:
        return []
    f_t = font("DejaVuSans-Bold.ttf", 12)
    f_n = font("DejaVuSans.ttf", 12)
    bx0, by0 = 812, 44
    fam_end = max(fm["x"] for fm in fl["fams"]) + 236
    fam_mid = (fl["fams"][0]["y"] + fl["fams"][-1]["y"]) / 2
    rep_rows = report_rows(d, fl)
    x_rep = fl["x"]["rep"] + 30

    def dashed(g, pts, colour, dash=6, gap=4, width=2):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
            length = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(length // (dash + gap)))
            for k in range(n):
                a, b = k * (dash + gap) / length, min(1, (k * (dash + gap) + dash) / length)
                g.line(
                    [(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)],
                    fill=colour,
                    width=width,
                )

    def draw(g):
        halo = {"stroke_width": 3, "stroke_fill": BG}
        dashed(g, [(fam_end, fam_mid), (bx0 - 8, fam_mid)], REPORT)
        g.polygon([(bx0 - 8, fam_mid - 5), (bx0, fam_mid), (bx0 - 8, fam_mid + 5)], fill=REPORT)
        g.text((bx0 + 6, by0), "still security-checked after being left out", font=f_t, fill=REPORT, anchor="lt")
        lines = []
        if d.get("xray") is not None:
            lines.append(f"X-Ray binary sweep walks the disk: {d['xray']:,} anomalies")
        if d.get("api") is not None:
            lines.append(f"API map walks the disk: {d['api']:,} shadow, {d.get('api_ghost') or 0:,} ghost APIs")
        lines.append("repo-level counts \u2192 audit manifest, database, brief")
        for i, ln in enumerate(lines):
            g.text((bx0 + 6, by0 + 18 + i * 16), ln, font=f_n, fill=INK2, anchor="lt", **halo)
        # into the three reports that carry them
        targets = [
            y for rep, y in rep_rows if rep["suffix"] in ("_galaxy_llm.md", "_galaxy_master.db", "_galaxy_audit.json")
        ]
        xr = W - 12
        dashed(g, [(bx0 + 300, by0 + 74), (xr, by0 + 74), (xr, max(targets))], REPORT, width=1)
        for y in targets:
            dashed(g, [(xr, y), (xr - 10, y)], REPORT, width=1)
        sarif = next((y for rep, y in rep_rows if rep["suffix"] == "_galaxy_sarif.json"), None)
        if sarif is not None:
            g.text((x_rep + 4 + 120, sarif - 9), "read files only", font=f_n, fill=MUTED, anchor="lm", **halo)

    return [{"x_show": bx0, "draw": draw}]


def flow_frames(d, fl, label) -> list[Image.Image]:
    """The flow reveals left to right at a constant speed (the clock is linear too). The dots travel as one bolus
    just behind the front, so they reach the reports on the reveal's last frame, the frame before the clock shows
    100%. Then the reports flash once and the screen holds still."""
    layer = draw_flow_layer(d, fl)
    rng = np.random.default_rng(3)
    parts = []
    for r in fl["ribbons"]:
        k = max(2, int(round(math.sqrt(max(1, r["n"])) / 1.6)))
        parts += [(r, rng.random(), rng.random()) for _ in range(k)]
    reveal_n, hold_n, lag = 48, HOLD, 70.0
    x_start = fl["nodes"]["src"][0] + 10
    x_land = fl["x"]["rep"] + 28  # the report arrow tips
    x_end = W - 20
    rainbow_style = fl.get("style") == "rainbow"
    eng_x = fl["nodes"]["eng"][0]

    def x_to_t(r, x):
        return (x - r["x0"]) / max(1e-6, r["x1"] - r["x0"])

    def frame(reveal_x, front, flash):
        im = Image.new("RGB", (W, H), BG)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rectangle([0, 0, int(reveal_x), H], fill=255)
        im.paste(layer, (0, 0), mask)
        g = ImageDraw.Draw(im)
        if front is not None:
            for r, u, v in parts:
                x = front - u * lag
                if not (r["x0"] <= x <= r["x1"]):
                    continue
                t = x_to_t(r, x)
                _, y = ribbon_point(r, t)
                (a0, a1), (b0, b1) = r["from"], r["to"]
                hgt = max(1.0, (a1 - a0) + ((b1 - b0) - (a1 - a0)) * smooth(t))
                y += (v - 0.5) * hgt * 0.8
                c = tuple(min(255, int(ch * 1.15 + 35)) for ch in r["color"])
                rad = 1.6 if r["kind"] in ("left", "fam", "stripe") else 2.2
                g.ellipse([x - rad, y - rad, x + rad, y + rad], fill=c)
            if front > eng_x:  # the bolus crosses from the engine into the reports
                for _, y in report_rows(d, fl):
                    for u in np.linspace(0, 1, 6):
                        x = front - u * lag
                        if eng_x + 14 <= x <= x_land:
                            g.ellipse([x - 2.2, y - 2.2, x + 2.2, y + 2.2], fill=(255, 220, 140))
        (draw_labels_rainbow if rainbow_style else draw_labels)(im, d, fl, reveal_x)
        if flash > 0:  # landing: each report arrow rings once, then fades
            for _, y in report_rows(d, fl):
                rr = 4 + 12 * (1 - flash)
                g.ellipse([x_land - rr, y - rr, x_land + rr, y + rr], outline=tint(REPORT, flash), width=2)
        if rainbow_style:
            g.text((24, 16), "One scan, every language", font=f_big, fill=INK, anchor="lt")
        else:
            g.text((40, 30), "One scan, every language", font=f_title, fill=INK, anchor="lt")
        return im

    frames = []
    for f in range(reveal_n):
        t = f / (reveal_n - 1)  # linear, like the clock
        front = x_start + (x_land - x_start) * t
        frames.append(frame(x_end if t >= 1 else min(x_end, front + 40), front, 0.0))
    for f in range(hold_n):
        frames.append(frame(x_end, None, max(0.0, 1 - f / 10)))
    return frames


def progress_bar(im: Image.Image, d, real: float, speed: float, label: str) -> Image.Image:
    """The scan's real wall clock along the bottom: elapsed seconds, the stage running, then 100%."""
    im = im.copy()
    g = ImageDraw.Draw(im)
    x0, x1, y = 40, 1150, 704
    frac = real / d["wall"]
    done = frac >= 0.9999
    stage = [lbl for t, lbl in d["stages"] if t <= real + 1e-6]
    stage = stage[-1] if stage else d["stages"][0][1]
    g.rounded_rectangle([x0, y - 3, x1, y + 3], 3, fill=LINE)
    if frac > 0:
        g.rounded_rectangle([x0, y - 3, x0 + (x1 - x0) * frac, y + 3], 3, fill=PROMPT if done else BLUE)
    if done:
        left = f"100%  ·  {d['wall']:.1f} s"
        right = (
            f"{d['total']:,} files  →  {d['read']:,} read, {d['n_lang']} languages and formats  →  "
            f"{len(d['reports'])} reports"
        )
    else:
        left = f"{real:4.1f} s"
        right = f"{stage}   ·   real scan time, shown {speed:.1f}× faster"
    g.text((x0, y - 10), left, font=f_mb, fill=INK, anchor="lb", stroke_width=3, stroke_fill=BG)
    g.text((x1, y - 10), right, font=f_s, fill=INK2, anchor="rb", stroke_width=3, stroke_fill=BG)
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="tree to scan with this checkout's engine")
    ap.add_argument("--scan-dir", help="reuse a galaxyscope --output directory instead of scanning")
    ap.add_argument("--log", help="the scan log for --scan-dir (stdout+stderr of galaxyscope)")
    ap.add_argument("--label", required=True, help="the path shown in the terminal and the captions")
    ap.add_argument("--version", default="", help="gitgalaxy version shown after pip install")
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-out", help="also write the flow numbers as JSON")
    ap.add_argument(
        "--style",
        choices=["classic", "rainbow"],
        default="classic",
        help="classic: bands to scale; rainbow: one equal stripe per language, reasons for the grey",
    )
    a = ap.parse_args()
    if a.scan_dir:
        if not a.log:
            ap.error("--scan-dir needs --log")
        scan_dir, log = pathlib.Path(a.scan_dir), pathlib.Path(a.log).read_text(encoding="utf-8")
    elif a.src:
        scan_dir, log = run_scan(pathlib.Path(a.src))
    else:
        ap.error("give --src or --scan-dir")
    d = load(scan_dir, log)
    d["version"] = a.version
    fl = build_flow_rainbow(d) if a.style == "rainbow" else build_flow(d)
    if a.style == "rainbow":
        fl["security"] = security_overlay(d, fl)
    if a.data_out:
        pathlib.Path(a.data_out).write_text(
            json.dumps(
                {
                    k: d[k]
                    for k in (
                        "total",
                        "read",
                        "loc",
                        "gates",
                        "langs",
                        "reports",
                        "seconds",
                        "wall",
                        "stages",
                        "families",
                        "xray",
                        "api",
                        "api_ghost",
                    )
                },
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )

    n_grid, n_reveal = 44, 48  # grid_frames / flow_frames reveal lengths
    span = {}

    def real_at(i):
        """Animation frame -> seconds on the scan's own clock: linear from Enter to the end of the reveal."""
        if not span:
            return 0.0
        return max(0.0, min(d["wall"], d["wall"] * (i - span["enter"]) / (span["end"] - span["enter"])))

    _, enter = terminal_frames(d, a.label, lambda _i: 0.0)  # first pass: where Enter lands
    span.update(enter=enter, end=enter + TERM_HOLD + n_grid + n_reveal)
    term, _ = terminal_frames(d, a.label, real_at)
    grid, flow = grid_frames(d, fl, a.label), flow_frames(d, fl, a.label)
    if len(grid) != n_grid:
        raise SystemExit(f"grid scene is {len(grid)} frames, clock assumes {n_grid}")
    frames = term + grid + flow
    speed = d["wall"] / ((span["end"] - span["enter"]) / FPS)
    for i in range(span["enter"], len(frames)):
        frames[i] = progress_bar(frames[i], d, real_at(i), speed, a.label)
    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-flowframes-"))
    for i, im in enumerate(frames):
        brand(im).convert("RGB").save(fdir / f"f{i:04d}.png")
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pat = str(fdir / "f%04d.png")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            pat,
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
            pat,
            "-vf",
            "scale=1280:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160[p];"
            "[b][p]paletteuse=dither=bayer:bayer_scale=4",
            str(out) + ".gif",
        ],
        check=True,
    )
    shutil.copy(fdir / f"f{len(frames) - 1:04d}.png", str(out) + ".png")
    shutil.rmtree(fdir, ignore_errors=True)
    print(
        f"{out}: {len(frames)} frames ({len(frames) / FPS:.1f} s); {d['total']} files, {d['read']} read, "
        f"left out {d['gates']}, {d['n_lang']} languages, {len(d['reports'])} reports"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
