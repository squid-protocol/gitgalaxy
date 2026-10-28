#!/usr/bin/env python3
"""DOOM study lineage (#5620): how much of id Software's linuxdoom-1.10 survives in each licensed port.

    python tests/tools/doom_speedrun/lineage.py [--only a,b] [--work DIR] [--sha SHA]

Reads what ``doom_speedrun.py`` leaves: the scans (``<work>/scans/<sha>/<port>``) and the pinned clones
(``<work>/repos/<port>``). Function boundaries are the engine's (``function_data.start_line`` / ``loc``); each body
is sliced from the clone from its first ``{``, comments dropped, tokenised, and hashed over the joined tokens, so
whitespace, comments and the signature line do not count. A linuxdoom function survives in a port by:

- **name**: a function with the same normalised name (class qualifier dropped, case and ``_`` ignored);
- **exact**: a function anywhere in the port with the same body hash;
- **near** / **derived**: the best same-name body has difflib token similarity >= 0.9 / >= 0.6.

Per port and per linuxdoom subsystem (file-name prefix: ``r_`` renderer, ``p_`` playsim, ...), against the port's
stated lineage in ``manifest.csv`` (its parent, when the lineage text names a manifest port). Also: which
linuxdoom file stems survive, pairwise divergence between ports (name and body Jaccard over first-party code, mean
similarity of the linuxdoom functions both keep), and the complexity / LOC of a dozen landmark functions per port.

Outputs ``<work>/results/<sha>/lineage/``: survival.csv, survival_subsystem.csv, survival_functions.csv,
filename_survival.csv, divergence_names.csv, divergence_bodies.csv, divergence_core.csv,
canonical_functions.csv and lineage.md. Licensed ports only (owner ruling 2026-10-19): any other port is refused.
Port of the round-1 study scripts (survival.py, canonical.py; engine ``a8510fc07``) onto the harness.
"""

import argparse
import collections
import csv
import difflib
import hashlib
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import callgraph_oracle  # noqa: E402
import doom_speedrun  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402

BASE = "linuxdoom"
BASE_DIRS = ("linuxdoom-1.10/", "sndserv/", "ipx/", "sersrc/")
# Licensed ports of the manifest that are not C/C++ (the C/C++ ones are callgraph_oracle.LICENSED); licenses read
# from the repo files. A port in neither set is never run, reported or committed by this tool.
LICENSED = callgraph_oracle.LICENSED | frozenset(
    "room4doom gore managed-doom mochadoom rust-doom doom-ios freedoom helion "
    "sqldoom doomf77 doom-scheme dartdoom doo-cr kocoa-doom fsharp-doom cssdoom doom-fx fps-cob "
    "agentic-cobol-doom-cc agentic-cobol-doom-codex mood".split()
)
MIN_TOKENS = 20  # trivial bodies (empty stubs, one-line returns) hash-match spuriously
NEAR, DERIVED = 0.9, 0.6
MAX_CANDIDATES = 20
PREFIXED_NAME = re.compile(r"[A-Za-z]{1,2}_[A-Za-z]")
MIN_BARE_NAME = 6  # a prefix-less landmark name must be longer than this to match on its own
C_STYLE = frozenset(
    "c cpp objective-c c_header cuda rust go java csharp kotlin dart javascript typescript swift".split()
)
COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|0x[0-9A-Fa-f]+|\d+|\S")
SOURCE_SUFFIXES = frozenset(".c .h .cpp .cc .cxx .hpp .h++ .rs .m .go .java .cs .kt .dart".split())
OTHER_GAMES = re.compile(r"(^|/)(heretic|hexen|strife)/", re.I)
# Landmark linuxdoom functions: complexity / LOC of each one's largest same-name match per port.
CANONICAL = (
    "P_UseSpecialLine", "P_CrossSpecialLine", "P_TouchSpecialThing", "M_Responder", "G_Ticker", "P_XYMovement",
    "P_CheckPosition", "R_DrawColumn", "R_RenderPlayerView", "R_StoreWallRange", "P_DamageMobj", "D_DoomLoop",
)  # fmt: skip
SUBSYSTEM_BY_PREFIX = {
    "r": "renderer", "p": "playsim", "g": "game-loop", "d": "main/defs", "i": "platform (i_*)", "v": "video",
    "w": "wad", "z": "zone-alloc", "m": "misc", "hu": "hud/ui", "st": "hud/ui", "am": "hud/ui", "wi": "hud/ui",
    "f": "hud/ui", "info": "data-tables", "tables": "data-tables", "doomdef": "main/defs", "doomstat": "main/defs",
    "dstrings": "main/defs",
}  # fmt: skip


def subsystem(path):
    """linuxdoom subsystem of a file, by directory and file-name prefix."""
    name = Path(path).name.lower()
    if path.startswith("sndserv/") or name.startswith(("s_sound", "i_sound", "sounds")):
        return "sound"
    if path.startswith(("ipx/", "sersrc/")) or name.startswith(("d_net", "i_net", "net_")):
        return "netcode"
    return SUBSYSTEM_BY_PREFIX.get(name.split("_")[0].split(".")[0], "other")


def name_index(base_functions):
    """Subsystem index of linuxdoom's functions by normalised name: ``(full, bare)`` dicts {nname: subsystem}.

    Only ``X_Name`` / ``XX_Name`` functions (linuxdoom's prefix convention: ``main`` or ``Init`` say nothing) and only
    names whose definitions all sit in one subsystem. ``bare`` is the name without its prefix (``UseSpecialLine``), kept
    when longer than ``MIN_BARE_NAME`` and not itself a full name or ambiguous."""
    seen = collections.defaultdict(set)
    bare_seen = collections.defaultdict(set)
    for name, path in base_functions:
        tail = name.split("::")[-1].split(".")[-1]
        if not PREFIXED_NAME.match(tail):
            continue
        sub = subsystem(path)
        seen[norm_name(tail)].add(sub)
        bare = norm_name(tail.split("_", 1)[1])
        if len(bare) > MIN_BARE_NAME:
            bare_seen[bare].add(sub)
    full = {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}
    bare = {k: next(iter(v)) for k, v in bare_seen.items() if len(v) == 1 and k not in seen}
    return full, bare


def assign_subsystem(name, path, index):
    """Subsystem of a port's function: the linuxdoom subsystem of the function it descends from (same name, with or
    without the ``p_`` / ``r_`` prefix), else the file-name placement of ``subsystem``."""
    full, bare = index
    key = norm_name(name or "")
    return full.get(key) or bare.get(key) or subsystem(path)


def norm_name(name):
    """``Class::P_Ticker`` / ``Game.p_ticker`` / ``PTicker`` -> ``pticker``."""
    return re.sub(r"[^a-z0-9]", "", name.split("::")[-1].split(".")[-1].lower())


def tokens(body, language):
    """Body tokens from its first ``{`` (signature dropped), C-style comments removed where the language has them."""
    brace = body.find("{")
    if brace >= 0:
        body = body[brace:]
    if (language or "").lower() in C_STYLE:
        body = COMMENT_RE.sub(" ", body)
    return TOKEN_RE.findall(body)


def body_hash(toks):
    return hashlib.sha1("".join(toks).encode()).hexdigest()


def similarity(a, b):
    """difflib ratio over two token streams; a cheap bound short-circuits clearly different bodies."""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < 0.3 or sm.quick_ratio() < 0.3:
        return sm.quick_ratio() * 0.5
    return sm.ratio()


def classify(exact, best, named):
    if exact:
        return "exact"
    if best >= NEAR:
        return "near"
    if best >= DERIVED:
        return "derived"
    return "name-only" if named else "gone"


def _rel(path, repo):
    path = path.replace("\\", "/")
    prefix = str(repo).replace("\\", "/").rstrip("/") + "/"
    return path[len(prefix) :] if path.startswith(prefix) else path


def load_functions(repo, db):
    """Engine functions of one scan, each with its body tokens and hash: a list of dicts."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select f.func_name, f.start_line, f.loc, f.args, f.complexity, d.file_path, d.language "
            "from function_data f join file_data d on d.id = f.file_id"
        ).fetchall()
    finally:
        con.close()
    lines_of, out = {}, []
    for name, start, loc, args, complexity, path, language in rows:
        if not name or not start or not loc:
            continue
        rel = _rel(path, repo)
        if rel not in lines_of:
            try:
                lines_of[rel] = read_source(Path(repo) / rel).text.splitlines()
            except OSError:
                lines_of[rel] = None
        lines = lines_of[rel]
        if lines is None:
            continue
        toks = tokens("\n".join(lines[start - 1 : start - 1 + loc]), language)
        out.append(
            dict(name=name, nname=norm_name(name), file=rel, language=language or "", args=args, loc=loc,
                 complexity=complexity, toks=toks, h=body_hash(toks))
        )  # fmt: skip
    return out


def baseline(functions):
    """linuxdoom's comparable functions: in its source dirs, non-trivial, one per (file, name)."""
    seen, out = set(), []
    for f in functions:
        key = (f["file"], f["name"])
        if f["file"].startswith(BASE_DIRS) and len(f["toks"]) >= MIN_TOKENS and key not in seen:
            seen.add(key)
            out.append(f)
    return out


def survival(base, functions):
    """Each baseline function's fate in one port. Returns (per-function rows, best-match tokens by baseline index)."""
    hashes = {f["h"] for f in functions}
    by_name = collections.defaultdict(list)
    for f in functions:
        by_name[f["nname"]].append(f)
    rows, kept = [], {}
    for i, b in enumerate(base):
        exact = b["h"] in hashes
        cands = by_name.get(b["nname"], [])
        scored = [(similarity(b["toks"], c["toks"]), c) for c in cands[:MAX_CANDIDATES]]
        sim, match = max(scored, key=lambda t: t[0]) if scored else (0.0, None)
        best = 1.0 if exact else sim
        if exact:
            kept[i] = b["toks"]
        elif match is not None:
            kept[i] = match["toks"]
        rows.append(
            dict(subsystem=subsystem(b["file"]), file=b["file"], func=b["name"], base_loc=b["loc"],
                 name_present=int(bool(cands)), args_match=int(any(c["args"] == b["args"] for c in cands)),
                 exact=int(exact), best_sim=round(best, 3), cls=classify(exact, best, bool(cands)))
        )  # fmt: skip
    return rows, kept


def summarise(rows):
    """Survival percentages per subsystem plus ``ALL``: {subsystem: row}."""
    acc = collections.defaultdict(collections.Counter)
    for r in rows:
        for key in (r["subsystem"], "ALL"):
            c = acc[key]
            c["n"] += 1
            c["name"] += r["name_present"]
            c["sig"] += r["name_present"] and r["args_match"]
            c["exact"] += r["exact"]
            c["near"] += r["best_sim"] >= NEAR
            c["derived"] += r["best_sim"] >= DERIVED
            c["loc"] += r["base_loc"]
            c["loc_sim"] += r["base_loc"] * r["best_sim"]

    def pct(c, k):
        return round(100 * c[k] / c["n"], 1)

    return {
        key: dict(subsystem=key, base_funcs=c["n"], pct_name=pct(c, "name"), pct_name_and_argcount=pct(c, "sig"),
                  pct_exact_body=pct(c, "exact"), pct_near_ge_0_9=pct(c, "near"),
                  pct_derived_ge_0_6=pct(c, "derived"),
                  loc_weighted_similarity=round(100 * c["loc_sim"] / c["loc"], 1) if c["loc"] else 0.0)
        for key, c in acc.items()
    }  # fmt: skip


def parent_of(lineage, names, own=""):
    """The manifest port the lineage text opens with ("Chocolate Doom (terminal renderer)" -> chocolate-doom): a port
    name equal to its first one or more whole words, never the port itself ("Go rewrite" is not ``gore``)."""
    head = re.split(r"<-|\(|;|,", lineage or "")[0]
    words = re.findall(r"[a-z0-9]+", head.lower().replace("+", "plus"))
    prefixes = {"".join(words[: i + 1]) for i in range(len(words))}
    return next((n for n in names if n != own and re.sub(r"[^a-z0-9]", "", n.lower()) in prefixes), "")


def file_stems(repo, subdir=None):
    """Stems of the tracked source files of a clone (``git ls-files``), lower-cased."""
    args = ["git", "-C", str(repo), "ls-files"] + ([subdir] if subdir else [])
    out = subprocess.run(args, capture_output=True, text=True, check=False).stdout.splitlines()
    return {Path(p).stem.lower() for p in out if Path(p).suffix.lower() in SOURCE_SUFFIXES}


def canonical(functions, is_vendor):
    """Complexity / LOC of each landmark function's largest first-party same-name match: {function: row}.

    A port that dropped linuxdoom's ``p_`` / ``r_`` prefix (``UseSpecialLine``, ``draw_column``) is matched on the bare
    name, but only when no function keeps the full name and the bare name is longer than ``MIN_BARE_NAME`` (``Ticker``
    is every subsystem's)."""
    want = {norm_name(f): f for f in CANONICAL}
    bare = {norm_name(f.split("_", 1)[1]): norm_name(f) for f in CANONICAL}
    best, best_bare = {}, {}
    for f in functions:
        k = f["nname"]
        if is_vendor(f["file"]) or OTHER_GAMES.search(f["file"]):
            continue
        for key, pool in ((k, best), (bare.get(k) if len(k) > MIN_BARE_NAME else None, best_bare)):
            if key in want and (key not in pool or f["loc"] > pool[key]["loc"]):
                pool[key] = f
    out = {}
    for k, label in want.items():
        b = best.get(k) or best_bare.get(k)
        out[label] = dict(function=label, found_as=b["name"] if b else "", file=b["file"] if b else "",
                          complexity=b["complexity"] if b else "", loc=b["loc"] if b else "")  # fmt: skip
    return out


def divergence(data, kept, vendor):
    """Pairwise name / body Jaccard over first-party functions and mean similarity of the linuxdoom functions both
    ports keep. Returns three lists of rows (one per port)."""
    hs = {
        v: {f["h"] for f in fs if len(f["toks"]) >= MIN_TOKENS and not vendor[v](f["file"])} for v, fs in data.items()
    }
    ns = {v: {f["nname"] for f in fs if not vendor[v](f["file"])} for v, fs in data.items()}

    def jaccard(a, b):
        return round(len(a & b) / max(len(a | b), 1), 3)

    names, bodies, core, cache = [], [], [], {}
    for a in data:
        rn, rb, rc = dict(variant=a), dict(variant=a), dict(variant=a)
        for b in data:
            rn[b], rb[b] = jaccard(ns[a], ns[b]), jaccard(hs[a], hs[b])
            if a in kept and b in kept:
                shared = sorted(set(kept[a]) & set(kept[b]))
                key = tuple(sorted((a, b)))
                if a == b:
                    rc[b] = 1.0
                elif shared:
                    if key not in cache:
                        cache[key] = sum(similarity(kept[a][i], kept[b][i]) for i in shared) / len(shared)
                    rc[b] = round(cache[key], 3)
                else:
                    rc[b] = ""
                rc[b + "__n"] = len(shared)
        names.append(rn)
        bodies.append(rb)
        if a in kept:
            core.append(rc)
    return names, bodies, core


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def render(summary, sha, nbase):
    lines = [
        f"# DOOM lineage vs linuxdoom-1.10: engine `{sha}`", "",
        f"{nbase} linuxdoom functions (>= {MIN_TOKENS} body tokens). Percentages of those functions; `parent` is the "
        "manifest port the stated lineage names, `exact vs parent` the change in exact bodies against it.", "",
        "| port | lineage | parent | name % | exact % | near % | derived % | LOC-weighted sim % | file stems % | exact vs parent |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for r in summary:
        lines.append(
            "| {variant} | {lineage} | {parent} | {pct_name} | {pct_exact_body} | {pct_near_ge_0_9} | "
            "{pct_derived_ge_0_6} | {loc_weighted_similarity} | {pct_filenames} | {exact_vs_parent} |".format(**r)
        )
    return "\n".join(lines) + "\n"


def run(rows, work, sha, vendor_test=None):
    """Lineage of every port in ``rows`` (manifest rows, BASE among them). Returns (outputs by file name, skipped)."""
    vendor_test = vendor_test or _engine_vendor_test
    data, vendor, skipped = {}, {}, []
    for row in rows:
        repo, db = work / "repos" / row["name"], callgraph_oracle.find_db(work / "scans" / sha / row["name"])
        if db is None or not repo.is_dir():
            skipped.append(row["name"])
            continue
        data[row["name"]] = load_functions(repo, db)
        vendor[row["name"]] = vendor_test(repo)
    if BASE not in data:
        raise SystemExit(f"lineage: no scan or clone of {BASE} under {work} at {sha} (run doom_speedrun.py scan)")
    base = baseline(data[BASE])
    base_stems = sorted(file_stems(work / "repos" / BASE, "linuxdoom-1.10"))
    lineage_of = {r["name"]: r.get("lineage", "") for r in rows}
    out = collections.defaultdict(list)
    kept, summary = {}, {}
    for v, functions in data.items():
        out["canonical_functions.csv"] += [dict(variant=v, **r) for r in canonical(functions, vendor[v]).values()]
        if v == BASE:
            continue
        per_fn, kept[v] = survival(base, functions)
        out["survival_functions.csv"] += [dict(variant=v, **r) for r in per_fn]
        subs = summarise(per_fn)
        out["survival_subsystem.csv"] += [dict(variant=v, **r) for k, r in sorted(subs.items()) if k != "ALL"]
        stems = file_stems(work / "repos" / v)
        hit = [s for s in base_stems if s in stems]
        out["filename_survival.csv"].append(
            dict(variant=v, linuxdoom_stems=len(base_stems), present=len(hit),
                 pct=round(100 * len(hit) / len(base_stems), 1) if base_stems else 0.0,
                 missing=" ".join(s for s in base_stems if s not in stems))
        )  # fmt: skip
        summary[v] = dict(variant=v, lineage=lineage_of.get(v, ""), parent=parent_of(lineage_of.get(v), lineage_of, v))
        summary[v].update({k: x for k, x in subs.get("ALL", summarise([])).items() if k != "subsystem"})
        summary[v]["pct_filenames"] = out["filename_survival.csv"][-1]["pct"]
    for r in summary.values():
        parent_exact = 100.0 if r["parent"] == BASE else summary.get(r["parent"], {}).get("pct_exact_body")
        r["exact_vs_parent"] = "" if parent_exact is None else round(r["pct_exact_body"] - parent_exact, 1)
    out["survival.csv"] = list(summary.values())
    out["divergence_names.csv"], out["divergence_bodies.csv"], out["divergence_core.csv"] = divergence(
        data, kept, vendor
    )
    out["lineage.md"] = render(out["survival.csv"], sha, len(base))
    return out, skipped


def _engine_vendor_test(repo):
    import doom_scorer

    return doom_scorer._engine_vendor_test(repo)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help=f"comma-separated ports ({BASE} is always added; default: every licensed port)")
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--sha", help="engine SHA of the scans to read (default: this checkout's HEAD)")
    ap.add_argument("--manifest", type=Path, help="alternate manifest CSV")
    args = ap.parse_args(argv)
    only = [n for n in (args.only or "").split(",") if n]
    if bad := sorted(set(only) - LICENSED):
        raise SystemExit(f"lineage: not in the licensed port set: {', '.join(bad)}")
    rows = doom_speedrun.read_manifest(args.manifest, None)
    wanted = set(only or LICENSED) | {BASE}
    rows = [r for r in rows if r["name"] in wanted and r["name"] in LICENSED]
    work, sha = args.work.resolve(), args.sha or doom_speedrun.engine_sha()
    out, skipped = run(rows, work, sha)
    for name in skipped:
        print(f"lineage: no scan or clone for {name} under {work} at {sha} (run doom_speedrun.py scan)")
    dest = work / "results" / sha / "lineage"
    dest.mkdir(parents=True, exist_ok=True)
    for name, content in out.items():
        if name.endswith(".md"):
            (dest / name).write_text(content)
        else:
            write_csv(dest / name, content)
    for r in out["survival.csv"]:
        print(f"{r['variant']:16} name {r['pct_name']:5}%  exact {r['pct_exact_body']:5}%  parent {r['parent'] or '-'}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
