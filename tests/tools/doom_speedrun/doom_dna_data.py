#!/usr/bin/env python3
"""Build data.json for the DOOM's DNA article (docs/wiki/museum-of-code/doom-dna/) from a DOOM study run (#7839).

    python tests/tools/doom_speedrun/doom_dna_data.py --work WORK --sha SHA --sfs-compare DIR --subway JSON \
        --blind JSON --timeline JSON [--whole-work WORK0] [--scope CSV] [--facts-date YYYY-MM-DD] -o data.json

Inputs, all produced outside this repo (third-party code and scans are never committed):

- ``WORK``: a ``doom_speedrun.py run --oracle`` work dir (``--scoped`` for the scoped edition) with ``lineage.py`` run
  over it: the scans (``scans/SHA/<port>``) and ``results/SHA/lineage/``.
- ``--sfs-compare``: ``sfs compare WORK/scans/SHA -o DIR --declared-lineage examples/doom/declared_lineage.csv
  --subway-reference linuxdoom --taxonomy examples/doom/subsystems.json --crosscheck
  WORK/results/SHA/lineage/survival_functions.csv`` (structural-fingerprint-scanner, gitgalaxy-population-analyses).
- ``--subway``: ``sfs subway WORK/scans/SHA -o DIR --reference linuxdoom --taxonomy ... --declared-lineage ...``
  with the cross-wiring null (population-analyses #21); its ``subway.json``.
- ``--blind``: sfs blind placement results (``examples/doom/blind_placement.json``); ``--timeline``: ``sfs timeline``
  output over full-history clones (the "drift" panel). Both are whole-repo measures.
- ``--whole-work``: the whole-repo run, for a scoped port's whole-repository size beside its DOOM-only size.

Needs numpy and the ``structural_fingerprint`` package (an sfs checkout with the cross-wiring null on PYTHONPATH)
for the subway layout. GitHub identity facts come from ``gh api``, cached; the cache is seeded from the previous
``-o`` file's ``facts.github`` so a rebuild makes no calls. Measurements and function names only; no source text.
Port of the explorer's build_data.py + build_facts.py (2026-10-31), which made the published data.json.
"""

import argparse
import csv
import datetime
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import doom_speedrun  # noqa: E402

REFERENCE = "linuxdoom"
TWIN_ROWS = 80  # twin sample shown per port; the count is always the full one
MIN_SHARED = 0.02  # sfs compare's default: shared structure below this is no evidence of descent
NON_CODE_LANG = {
    "makefile",
    "markdown",
    "json",
    "yaml",
    "xml",
    "html",
    "css",
    "text",
    "unknown",
    "cmake",
    "shell",
    "batch",
}
NON_CODE_FACTS = NON_CODE_LANG | {"plaintext", "toml", "ini", "dockerfile", "csv"}
GENERIC = {"main", "init", "run", "update", "draw"}  # every program has these: no evidence of descent
# Well-known linuxdoom functions, grouped the way a DOOM player knows them. All are in lineage.py's base set (P_Random
# and W_CacheLumpName are not: too small to score).
FAMOUS = [
    ("Rendering", [("R_RenderPlayerView", "draws the player's view"), ("R_DrawColumn", "draws one wall/sprite column"),
                   ("R_DrawPlanes", "draws floors and ceilings"), ("R_PointToAngle", "the angle lookup behind everything")]),
    ("Monsters", [("A_Look", "a monster waits for you"), ("A_Chase", "a monster hunts you"),
                  ("P_DamageMobj", "anything takes damage"), ("P_KillMobj", "anything dies")]),
    ("Player & weapons", [("A_FireShotgun", "the shotgun"), ("P_LineAttack", "hitscan bullets"),
                          ("P_CheckSight", "line of sight"), ("P_XYMovement", "sliding, momentum, friction")]),
    ("World", [("P_SpawnMobj", "anything appears"), ("P_MobjThinker", "every thing's tick"),
               ("T_MovePlane", "doors, lifts and crushers move"), ("T_MoveCeiling", "crushing ceilings")]),
    ("Game & screens", [("D_DoomLoop", "the main loop"), ("G_Ticker", "one game tic"), ("AM_Drawer", "the automap"),
                        ("ST_Drawer", "the status bar and face"), ("M_Responder", "the menus"), ("F_Ticker", "the finale")]),
]  # fmt: skip
# Family: child -> (parent, kind), from each port's stated lineage in the manifest. Lower-case names are ports in the
# study; capitalised ones (Boom, MBF, ...) are ancestors it did not scan. Kinds: fork (code carried over), translation
# (rewritten into another language from that code), rewrite (written anew with it as the reference).
FAMILY = {
    "chocolate-doom": ("linuxdoom", "fork"), "crispy-doom": ("chocolate-doom", "fork"), "doomgeneric": ("chocolate-doom", "fork"),
    "doomretro": ("chocolate-doom", "fork"), "doom-wasm": ("chocolate-doom", "fork"), "doom-ascii": ("chocolate-doom", "fork"),
    "inter-doom": ("crispy-doom", "fork"), "fastdoom": ("linuxdoom", "fork"), "sdl-doom": ("linuxdoom", "fork"),
    "doom-ios": ("linuxdoom", "fork"), "mood": ("linuxdoom", "fork"),
    "Boom": ("linuxdoom", "fork"), "PrBoom": ("Boom", "fork"), "prboom-plus": ("PrBoom", "fork"), "dsda-doom": ("prboom-plus", "fork"),
    "puredoom": ("PrBoom", "fork"), "MBF": ("Boom", "fork"), "WinMBF": ("MBF", "fork"), "woof": ("WinMBF", "fork"),
    "nugget-doom": ("woof", "fork"), "SMMU": ("MBF", "fork"), "eternity": ("SMMU", "fork"), "EDGE": ("Boom", "fork"),
    "edge-classic": ("EDGE", "fork"), "ZDoom": ("linuxdoom", "fork"), "gzdoom": ("ZDoom", "fork"), "CSDoom": ("ZDoom", "fork"),
    "odamex": ("CSDoom", "fork"), "Doom Legacy": ("linuxdoom", "fork"), "srb2": ("Doom Legacy", "fork"),
    "gore": ("linuxdoom", "translation"), "managed-doom": ("linuxdoom", "translation"), "mochadoom": ("linuxdoom", "translation"),
    "doom-scheme": ("linuxdoom", "translation"), "dartdoom": ("linuxdoom", "translation"), "sqldoom": ("linuxdoom", "translation"),
    "doomf77": ("linuxdoom", "translation"), "kocoa-doom": ("mochadoom", "translation"), "doo-cr": ("puredoom", "translation"),
    "room4doom": ("linuxdoom", "rewrite"),
}  # fmt: skip
GAMES = {"heretic": "Heretic", "hexen": "Hexen", "strife": "Strife"}


def rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def num(v, nd=4):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x or x in (float("inf"), float("-inf")) else round(x, nd)


def mean_of(d):
    if isinstance(d, dict):
        for k in ("mean", "null_mean", "value"):
            if k in d:
                return num(d[k])
    return num(d)


def norm(name):
    """Compare names across languages: gore's m_Responder and a C M_Responder are the same name."""
    return name.lower().replace("_", "").replace("-", "")


def master_db(scans, name):
    db = scans / name / f"{name}_galaxy_master.db"
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def main_language(scans, name):
    """The language most of a port's functions are written in, read from its scan."""
    got = (
        master_db(scans, name)
        .execute(
            "select lower(d.language), count(*) from function_data f join file_data d on d.id = f.file_id"
            " group by 1 order by 2 desc"
        )
        .fetchall()
    )
    return next((lang for lang, _ in got if lang and lang not in NON_CODE_LANG), "")


def scan_size(scans, name):
    con = master_db(scans, name)
    rd = con.execute(
        "select total_loc, total_coding_loc, total_files, total_functions from repo_data limit 1"
    ).fetchone()
    funcs = con.execute(
        "select f.func_name, f.complexity, f.loc, f.func_fan_in, d.file_path, lower(d.language) from function_data f"
        " join file_data d on d.id = f.file_id"
    ).fetchall()
    return rd, [f for f in funcs if f[5] and f[5] not in NON_CODE_FACTS and f[0]]


def scope_label(keep, drop):
    if keep:
        return f"Most of this repository is Doom 3's engine (id Tech 4); only its bundled classic DOOM ({', '.join(keep)}) is counted."
    games = [GAMES[g] for g in GAMES if any(p.rstrip("/").split("/")[-1] == g for p in drop)]
    return f"This repository also holds other games ({', '.join(games)}); they are left out."


# -- GitHub identity (cached) ---------------------------------------------------------------------------------------


def gh(path, headers=False):
    cmd = ["gh", "api", *(["-i"] if headers else []), path]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603 (gh by name, fixed args)
    return None if out.returncode else out.stdout


def last_page(raw):
    m = re.search(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"', raw or "")
    return int(m.group(1)) if m else None


def body(raw):
    return json.loads(raw.split("\r\n\r\n", 1)[-1].split("\n\n", 1)[-1] if raw and raw.startswith("HTTP") else raw)


def github(slug, cache):
    if slug in cache:
        return cache[slug]
    info = {}
    repo = gh(f"repos/{slug}")
    if repo:
        r = json.loads(repo)
        info = {"description": r.get("description"), "stars": r.get("stargazers_count"), "archived": r.get("archived"),
                "pushed": (r.get("pushed_at") or "")[:10], "created": (r.get("created_at") or "")[:10],
                "homepage": r.get("homepage") or None, "default_branch": r.get("default_branch")}  # fmt: skip
        raw = gh(f"repos/{slug}/contributors?per_page=1&anon=1", headers=True)
        n = last_page(raw)
        if n is None and raw:
            try:
                n = len(body(raw))
            except ValueError:
                n = None
        info["contributors"] = n
        raw = gh(f"repos/{slug}/commits?per_page=1", headers=True)
        try:
            newest = body(raw)
            info["last_commit"] = newest[0]["commit"]["committer"]["date"][:10] if newest else None
            n = last_page(raw)
            oldest = body(gh(f"repos/{slug}/commits?per_page=1&page={n}", headers=True)) if n else newest
            info["first_commit"] = oldest[-1]["commit"]["author"]["date"][:10] if oldest else None
            info["commits"] = n or (len(newest) if newest else None)
        except (ValueError, TypeError, KeyError, IndexError):
            pass
    cache[slug] = info
    return info


# -- build ----------------------------------------------------------------------------------------------------------


def twin_pairs(report_html):
    twins = json.loads(re.search(r"<script type=application/json id=twins>(.*?)</script>", report_html, re.S).group(1))
    out = {}
    for p in twins["pairs"]:
        if REFERENCE not in (p["q"], p["t"]):
            continue
        other = p["t"] if p["q"] == REFERENCE else p["q"]
        ref_first = p["q"] == REFERENCE
        sample = []
        for qn, qp, ql, tn, tp, tl, dist, flags in p["rows"][:TWIN_ROWS]:
            ln, lp, ll, on, op, ol = (qn, qp, ql, tn, tp, tl) if ref_first else (tn, tp, tl, qn, qp, ql)
            sample.append({"ref": ln, "ref_file": p["paths"][lp], "ref_loc": ll, "port": on, "port_file": p["paths"][op],
                           "port_loc": ol, "distance": round(dist / 1000, 3), "exact": bool(flags & 1),
                           "same_name": bool(flags & 2)})  # fmt: skip
        out[other] = {"count": p["twins"], "shared": num(p["shared"]), "survival": num(p["survival"]), "sample": sample}
    return out


def build_ports(a, manifest, scans, lineage_dir):
    import numpy as np
    from structural_fingerprint import subway as sw

    survival = {r["variant"]: r for r in rows(lineage_dir / "survival.csv")}
    subway = json.loads(a.subway.read_text())
    cross = {r["port"]: r for r in rows(a.sfs_compare / "crosscheck.csv")}
    twins = twin_pairs((a.sfs_compare / "report.html").read_text())
    blind = {p["repo"]: p for p in json.loads(a.blind.read_text())["ports"]}
    ss_rows = rows(a.sfs_compare / "matrices/shared_structure.csv")
    key = next(iter(ss_rows[0]))
    shared = {r[key]: {k: num(v) for k, v in r.items() if k != key} for r in ss_rows}

    subs = subway["subsystems"]
    maps = {m["repo"]: m for m in subway["maps"]}
    ref = maps[REFERENCE]
    ix = {s: i for i, s in enumerate(subs)}
    calls = np.zeros((len(subs), len(subs)), dtype=np.int64)
    for ln in ref["lines"]:
        calls[ix[ln["from"]], ix[ln["to"]]] += ln["calls"]
    sizes = np.array([ref["stations"][s]["functions"] for s in subs])
    pos = sw.layout(sw.SubwayMap(REFERENCE, subs, sizes, calls, {}))

    ports = []
    for name, m in maps.items():
        man = manifest.get(name, {})
        sv, cc, bl = survival.get(name), cross.get(name), blind.get(name)
        near = sorted(
            ((v, k) for k, v in shared.get(name, {}).items() if k != name and v is not None and v >= MIN_SHARED),
            reverse=True,
        )
        gap = None
        if m.get("cross_wiring") is not None and m.get("cross_wiring_null") is not None:
            gap = round(m["cross_wiring"] - m["cross_wiring_null"], 4)
        ports.append({
            "name": name, "language": main_language(scans, name), "languages": man.get("languages", ""),
            "class": man.get("class", ""), "fidelity": man.get("fidelity") or "unstated", "license": man.get("license", ""),
            "lineage": man.get("lineage", ""), "upstream": man.get("upstream", ""), "functions": m["functions"],
            "wiring": num(m["wiring_similarity"]), "cross_wiring": num(m.get("cross_wiring")),
            "cross_null": num(m.get("cross_wiring_null")), "gap": gap, "calls_kept": num(m["edges_kept"]),
            "shape_distance": num(m["shape_distance"]), "assigned_by": m["assigned_by"],
            "stations": {s: {"functions": v["functions"], "survival": num(v["survival"])} for s, v in m["stations"].items()},
            "lines": m["lines"],
            "survival": None if sv is None else {k: num(sv[c], 1) for k, c in (
                ("name", "pct_name"), ("exact", "pct_exact_body"), ("near", "pct_near_ge_0_9"), ("derived", "pct_derived_ge_0_6"))},
            "parent": (sv or {}).get("parent") or None,
            "shared_with_linuxdoom": shared.get(name, {}).get(REFERENCE),
            "nearest": [{"name": k, "shared": v} for v, k in near[:3]],
            "crosscheck": None if cc is None else {
                "precision": num(cc["precision"]), "recall": num(cc["recall"]),
                "scanner_survival": num(cc["scanner_survival"]), "source_survival": num(cc["source_survival"])},
            "blind": None if bl is None else {
                "accuracy": num(bl["accuracy"]), "accuracy_null": mean_of(bl["accuracy_null"]), "kappa": num(bl["kappa"]),
                "top_quartile": num(bl["accuracy_top_quartile_confidence"])},
            "twins": twins.get(name),
        })  # fmt: skip
    data = {
        "engine": a.sha,
        "reference": REFERENCE,
        "wiring_floor": num(subway.get("wiring_floor")),
        "subsystems": [{"name": s, "x": round(float(pos[i, 0]), 4), "y": round(float(pos[i, 1]), 4)} for i, s in enumerate(subs)],
        "ports": ports,
    }  # fmt: skip
    return data, shared


def add_facts(a, data, manifest, scans, lineage_dir, scope, cache):
    fate = {}
    for r in rows(lineage_dir / "survival_functions.csv"):
        fate.setdefault(r["variant"], {})[r["func"]] = (r["cls"], float(r["best_sim"] or 0))
    famous_names = {f for _, group in FAMOUS for f, _ in group}
    ref_rd, ref_funcs = scan_size(scans, REFERENCE)
    ref_names = {norm(f[0]) for f in ref_funcs} - GENERIC
    whole_scans = a.whole_work / "scans" / a.sha if a.whole_work else None
    for p in data["ports"]:
        name = p["name"]
        slug = re.sub(r"^https://github\.com/|\.git$|/$", "", manifest.get(name, {}).get("upstream", ""))
        gh_info = github(slug, cache) if slug.count("/") == 1 else {}
        rd, funcs = (ref_rd, ref_funcs) if name == REFERENCE else scan_size(scans, name)
        named = sum(norm(f[0]) in ref_names for f in funcs)

        def top(key, n=1, keep=None, funcs=funcs):
            got = sorted((f for f in funcs if f[key] is not None and (keep is None or keep(f))), key=lambda f: -f[key])[
                :n
            ]
            return [{"name": f[0], "file": f[4].split("/")[-1], "complexity": f[1], "loc": f[2], "calls_in": f[3],
                     "linuxdoom_name": norm(f[0]) in ref_names} for f in got]  # fmt: skip

        if name == REFERENCE:
            famous = {f: ["original", 1.0] for f in famous_names}
        else:
            famous = {f: list(fate.get(name, {}).get(f, ("gone", 0.0))) for f in famous_names}
        size = {"loc": rd[0], "coding_loc": rd[1], "files": rd[2], "functions": rd[3], "code_functions": len(funcs),
                "linuxdoom_named": named}  # fmt: skip
        if name in scope:
            keep, drop = scope[name]
            # the page shows scope.{coding_loc,code_functions,files} as the DOOM part and the size totals as the whole
            # repository: measured here, both from scans (the scoped one and the whole-repo one)
            sc = {"label": scope_label(keep, drop), "mode": "keep" if keep else "drop",
                  "paths": [x + "/" for x in (keep or drop)], "measured": True,
                  "coding_loc": rd[1], "code_functions": len(funcs), "files": rd[2], "linuxdoom_named": named,
                  "basis": "measured on the scoped tree (tests/doom_rosetta/scope.csv, #7839)"}  # fmt: skip
            if whole_scans:
                wrd, wfuncs = scan_size(whole_scans, name)
                size.update({"loc": wrd[0], "coding_loc": wrd[1], "files": wrd[2], "functions": wrd[3],
                             "code_functions": len(wfuncs),
                             "linuxdoom_named": sum(norm(f[0]) in ref_names for f in wfuncs)})  # fmt: skip
            size["scope"] = sc
        p["facts"] = {
            "github": {"slug": slug, **gh_info},
            "size": size,
            "famous": {f: {"cls": c, "sim": round(s, 3)} for f, (c, s) in famous.items()},
            # the biggest function with real logic (data tables score complexity 0) and no linuxdoom name
            "hero": {"complex": top(1), "called": top(3),
                     "new": top(2, keep=lambda f: (f[1] or 0) >= 1 and norm(f[0]) not in ref_names)},
        }  # fmt: skip
    # family edges, with the structure each port shares with its parent when both were scanned
    ss_rows = rows(a.sfs_compare / "matrices/shared_structure.csv")
    key = next(iter(ss_rows[0]))
    shared = {r[key]: r for r in ss_rows}
    measured_parent = {p["name"]: p.get("parent") for p in data["ports"]}
    names = {p["name"] for p in data["ports"]}
    edges = []
    for child, (parent, kind) in FAMILY.items():
        s = shared.get(child, {}).get(parent)
        edges.append({"child": child, "parent": parent, "kind": kind, "measured": measured_parent.get(child) == parent,
                      "shared": round(float(s), 4) if s not in (None, "") else None,
                      "external": [n for n in (child, parent) if n not in names]})  # fmt: skip
    independent = sorted(p["name"] for p in data["ports"] if p["name"] not in FAMILY and p["name"] != REFERENCE)
    data["family"] = {"edges": edges, "independent": independent}
    # drift: yearly snapshots from sfs timeline (whole-repo history), for the ports it measured
    tl = json.loads(a.timeline.read_text())
    drift = {}
    for s in tl["snapshots"]:
        drift.setdefault(s["repo"], []).append({"date": s["date"], "shared": round(s["shared_structure"], 4),
                                               "survival": round(s["reference_survival"], 4), "functions": s["functions"],
                                               "coding_loc": int(s["coding_loc"] or 0)})  # fmt: skip
    for p in data["ports"]:
        p["facts"]["drift"] = sorted(drift.get(p["name"], []), key=lambda x: x["date"]) or None
    data["drift_engine"] = re.sub(r"^(sfs-)?engine-", "", Path(tl.get("engine", "")).name)
    # Follow a function: every one of linuxdoom's scored functions, its fate in every descendant as one letter
    # (e identical, n near-identical, d derived, o name only, g gone) and its best body similarity as a digit 0-9
    code = {"exact": "e", "near": "n", "derived": "d", "name-only": "o", "gone": "g"}
    frows = rows(lineage_dir / "survival_functions.csv")
    order = sorted({r["variant"] for r in frows})
    at = {v: i for i, v in enumerate(order)}
    fn = {}
    for r in frows:
        e = fn.setdefault((r["func"], r["file"]), {
            "name": r["func"], "file": r["file"].split("/")[-1], "sub": r["subsystem"], "loc": int(r["base_loc"] or 0),
            "f": ["g"] * len(order), "s": ["0"] * len(order)})  # fmt: skip
        e["f"][at[r["variant"]]] = code.get(r["cls"], "g")
        e["s"][at[r["variant"]]] = str(min(9, int(float(r["best_sim"] or 0) * 10)))
    data["fates"] = {"ports": order, "funcs": sorted(
        ({**e, "f": "".join(e["f"]), "s": "".join(e["s"])} for e in fn.values()), key=lambda e: (e["name"].lower(), e["file"]))}  # fmt: skip
    data["famous"] = [{"group": g, "functions": [{"name": f, "what": w} for f, w in fs]} for g, fs in FAMOUS]
    data["facts_built"] = a.facts_date or datetime.datetime.now(datetime.UTC).date().isoformat()
    data["reference_size"] = {"loc": ref_rd[0], "coding_loc": ref_rd[1], "files": ref_rd[2], "functions": ref_rd[3]}
    if scope:
        data["scope"] = {
            "ports": sorted(scope),
            "note": "multi-game repos measured on their DOOM part (tests/doom_rosetta/scope.csv); blind placement "
            "and drift stay whole-repo (#7839)",
        }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--work", type=Path, required=True, help="doom_speedrun work dir (scans + lineage results)")
    ap.add_argument("--sha", required=True, help="engine SHA key of the scans")
    ap.add_argument("--sfs-compare", type=Path, required=True, help="sfs compare output dir")
    ap.add_argument("--subway", type=Path, required=True, help="sfs subway.json with the cross-wiring null")
    ap.add_argument("--blind", type=Path, required=True, help="sfs blind_placement.json")
    ap.add_argument("--timeline", type=Path, required=True, help="sfs timeline.json")
    ap.add_argument("--manifest", type=Path, default=doom_speedrun.MANIFEST)
    ap.add_argument("--scope", type=Path, help="scope CSV of a --scoped work dir (default: scope.csv when scoped)")
    ap.add_argument("--whole-work", type=Path, help="the whole-repo work dir: scoped ports' whole-repository sizes")
    ap.add_argument("--facts-date", help="facts_built date (default today; the page dates 'last commit' against it)")
    ap.add_argument("--github-cache", type=Path, help="JSON cache of GitHub answers (default: seeded from -o)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args(argv)
    scoped = (a.work / "scope-mode").exists() and doom_speedrun._mark(a.work / "scope-mode") == "scoped"
    scope = doom_speedrun.read_scope(a.scope) if (scoped or a.scope) else {}
    manifest = {r["name"]: r for r in doom_speedrun.read_manifest(a.manifest)}
    scans, lineage_dir = a.work / "scans" / a.sha, a.work / "results" / a.sha / "lineage"
    cache = {}
    if a.github_cache and a.github_cache.exists():
        cache = json.loads(a.github_cache.read_text())
    elif a.out.exists():
        for p in json.loads(a.out.read_text()).get("ports", []):
            g = dict(p.get("facts", {}).get("github", {}))
            if g.pop("slug", None):
                cache[p["facts"]["github"]["slug"]] = g
    data, _ = build_ports(a, manifest, scans, lineage_dir)
    add_facts(a, data, manifest, scans, lineage_dir, scope, cache)
    if a.github_cache:
        a.github_cache.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    a.out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"wrote {a.out} ({a.out.stat().st_size // 1024} KiB, {len(data['ports'])} ports; scoped: {sorted(scope)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
