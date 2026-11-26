#!/usr/bin/env python3
"""Fix history vs call graph (#8958): a rerunnable study, C only in this slice.

    python tests/tools/fix_ripple_study.py run --manifest docs/research/fix_ripple_manifest.json \
        --corpora ../fix-ripple-corpora --out /tmp/gitgalaxy-scratch/claude/fix_ripple.json [--drop-noise] [--only NAME]
    python tests/tools/fix_ripple_study.py analyze --repo PATH --db SCAN_DB --name NAME --out OUT.json
    python tests/tools/fix_ripple_study.py check RESULTS.json      # exit 1 when a hypothesis verdict differs from the recorded one

Hypotheses and decision rules: docs/research/fix-ripple-preregistration.md (committed before this code). Research only: it reads public
repositories and writes a results file; it changes no engine output and no score, and an association here is never a risk claim.

Method. Graph = `function_data` + resolved `fcall_data` rows of a galaxyscope scan (GITGALAXY_DISABLE_GIT_HISTORY=1 in the child only).
Fixes = commit subjects matched by keyword (defs orig / B / D). Touches = git hunk-header function names mapped to `function_data` by
(path, name); a name that is not unique in its file is dropped. Lift = observed / Poisson-predicted touches (size model on log(1+LOC),
log(1+complexity)). Standard library only (the original used numpy and networkx; neither is a project dependency). Output is rounded and
seeded, so a rerun at the same engine SHA and repository SHA is byte-identical.

`--drop-noise` removes test / doc / vendored directories from a COPY before the scan (history is still read from the original). It changes
the graph, so it is off by default and recorded in the results JSON next to every number.

Not in this slice: Go / Java / Kotlin attribution, the directory-matched null (H5), bug-introducing commits, the size-matched null.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(
    0, str(REPO_ROOT)
)  # before any gitgalaxy import, so a shared venv's editable install of another checkout never runs

SINCE = "2021-01-01"
BOOTSTRAP = 500
SEED = 8958
DEFS = ("orig", "B", "D")
CONFIDENT_STEPS = ("class", "qualified", "typed", "file", "import", "unique", "proximate")
NOISE_DIRS = frozenset(
    {"test", "tests", "doc", "docs", "vendor", "third_party", "thirdparty", "deps", "contrib", "examples", "fuzz"}
)

_MEM = r"overflow|leak|uaf|use-after-free|heap|stack|memory|oob|out-of-bounds"
_ORIG = re.compile(r"fix|bug|cve|crash|" + _MEM, re.I)
_B_POS = re.compile(r"fix|bug|regression", re.I)
_B_NEG = re.compile(_MEM, re.I)
_LIFECYCLE = re.compile(r"(^|_)(free|close|destroy|release|cleanup|dispose|deinit|fini|shutdown|teardown)(_|$)", re.I)
_HUNK = re.compile(r"^@@ [^@]*@@ ?(.*)$")
_IDENT_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


def fix_flags(subject: str) -> dict[str, bool]:
    return {
        "orig": bool(_ORIG.search(subject)),
        "B": bool(_B_POS.search(subject)) and not _B_NEG.search(subject),
        "D": True,
    }


def hunk_name(context: str) -> str | None:
    """The function a C hunk header names: the first identifier followed by `(`. C only: for Go (`func (r *T) m(`) it returns `func`."""
    m = _IDENT_CALL.search(context)
    return m.group(1) if m else None


def mine_touches(
    repo: Path, since: str = SINCE, exts: tuple[str, ...] = ("*.c", "*.h")
) -> dict[str, dict[tuple[str, str], int]]:
    """{definition: {(path, function name): number of distinct commits touching it}}."""
    out = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--no-merges",
            f"--since={since}",
            "--no-color",
            "-U0",
            "--format=%x01%H%x02%s",
            "--",
            *exts,
        ],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", "replace")
    touches: dict[str, dict[tuple[str, str], int]] = {d: {} for d in DEFS}
    for chunk in out.split("\x01")[1:]:
        head, _, body = chunk.partition("\n")
        flags = fix_flags(head.partition("\x02")[2])
        seen: set[tuple[str, str]] = set()
        path = ""
        for line in body.splitlines():
            if line.startswith("+++ b/"):
                path = line[6:]
            elif line.startswith("@@"):
                m = _HUNK.match(line)
                name = hunk_name(m.group(1)) if m else None
                if name and path:
                    seen.add((path, name))
        for d in DEFS:
            if flags[d]:
                for key in seen:
                    touches[d][key] = touches[d].get(key, 0) + 1
    return touches


def load_graph(db: Path, strip: str = "") -> list[dict]:
    """One dict per function: path, name, loc, cx, fan_in, fan_out (distinct resolved callers / callees, self-calls dropped)."""
    con = sqlite3.connect(str(db))
    try:
        rows = con.execute(
            "SELECT f.id, fd.file_path, f.func_name, f.loc, f.complexity FROM function_data f JOIN file_data fd ON f.file_id = fd.id"
        ).fetchall()
        marks = ",".join("?" * len(CONFIDENT_STEPS))
        edges = con.execute(
            f"SELECT DISTINCT src_func_id, dst_func_id FROM fcall_data WHERE dst_func_id IS NOT NULL AND src_func_id IS NOT NULL "
            f"AND step IN ({marks})",
            CONFIDENT_STEPS,
        ).fetchall()
    finally:
        con.close()
    fin: dict[int, int] = {}
    fout: dict[int, int] = {}
    for s, d in edges:
        if s == d:
            continue
        fout[s] = fout.get(s, 0) + 1
        fin[d] = fin.get(d, 0) + 1
    funcs = []
    for fid, path, name, loc, cx in rows:
        p = (path or "").replace("\\", "/")
        if strip and p.startswith(strip):
            p = p[len(strip) :].lstrip("/")
        funcs.append(
            {
                "path": p,
                "name": name,
                "loc": loc or 0,
                "cx": cx or 0,
                "fan_in": fin.get(fid, 0),
                "fan_out": fout.get(fid, 0),
            }
        )
    return funcs


def attach(funcs: list[dict], touches: dict[str, dict[tuple[str, str], int]]) -> list[dict]:
    """Add `t_<def>` counts; a (path, name) held by more than one function is ambiguous and dropped."""
    count: dict[tuple[str, str], int] = {}
    for f in funcs:
        count[(f["path"], f["name"])] = count.get((f["path"], f["name"]), 0) + 1
    kept = [f for f in funcs if count[(f["path"], f["name"])] == 1]
    for f in kept:
        for d in DEFS:
            f["t_" + d] = touches[d].get((f["path"], f["name"]), 0)
    return kept


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        if abs(m[c][c]) < 1e-12:
            m[c][c] = 1e-12
        for r in range(n):
            if r != c:
                k = m[r][c] / m[c][c]
                for j in range(c, n + 1):
                    m[r][j] -= k * m[c][j]
    return [m[i][n] / m[i][i] for i in range(n)]


def poisson_predict(funcs: list[dict], key: str) -> list[float]:
    """Predicted touches per function from an IRLS Poisson fit on [1, log(1+LOC), log(1+complexity)]."""
    x = [(1.0, math.log1p(f["loc"]), math.log1p(f["cx"])) for f in funcs]
    y = [f[key] for f in funcs]
    mean = max(sum(y) / max(len(y), 1), 1e-9)
    beta = [math.log(mean), 0.0, 0.0]
    for _ in range(30):
        eta = [max(min(sum(bj * xj for bj, xj in zip(beta, r, strict=True)), 20.0), -20.0) for r in x]
        mu = [math.exp(e) for e in eta]
        hess = [[1e-8 if i == j else 0.0 for j in range(3)] for i in range(3)]
        grad = [0.0] * 3
        for r, yi, mi in zip(x, y, mu, strict=True):
            for i in range(3):
                grad[i] += r[i] * (yi - mi)
                for j in range(3):
                    hess[i][j] += mi * r[i] * r[j]
        step = _solve(hess, grad)
        beta = [bi + si for bi, si in zip(beta, step, strict=True)]
        if max(abs(s) for s in step) < 1e-8:
            break
    return [math.exp(max(min(sum(bj * xj for bj, xj in zip(beta, r, strict=True)), 20.0), -20.0)) for r in x]


def _ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    rank = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            rank[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return rank


def _resid(y: list[float], cols: list[list[float]]) -> list[float]:
    n = len(y)
    x = [[1.0, cols[0][i], cols[1][i]] for i in range(n)]
    a = [[sum(r[i] * r[j] for r in x) + (1e-9 if i == j else 0.0) for j in range(3)] for i in range(3)]
    b = [sum(r[i] * yi for r, yi in zip(x, y, strict=True)) for i in range(3)]
    beta = _solve(a, b)
    return [yi - sum(bj * xj for bj, xj in zip(beta, r, strict=True)) for r, yi in zip(x, y, strict=True)]


def partial_spearman(x: list[float], y: list[float], ctrl1: list[float], ctrl2: list[float]) -> float:
    """Spearman correlation of x and y after removing the (rank) linear effect of two controls."""
    c = [_ranks(ctrl1), _ranks(ctrl2)]
    rx, ry = _resid(_ranks(x), c), _resid(_ranks(y), c)
    num = sum(a * b for a, b in zip(rx, ry, strict=True))
    den = math.sqrt(sum(a * a for a in rx) * sum(b * b for b in ry))
    return num / den if den else 0.0


def groups(f: dict) -> list[str]:
    out = []
    if f["fan_in"] < 8 and f["fan_out"] >= 8:
        out.append("orchestrator")
    if _LIFECYCLE.search(f["name"] or "") and f["fan_in"] >= 8:
        out.append("lifecycle")
    deg = f["fan_in"] + f["fan_out"]
    if deg:
        ratio = f["fan_in"] / deg
        if ratio < 0.2:
            out.append("consumer")
        elif ratio > 0.8:
            out.append("producer")
    return out


def _lift(pairs: list[tuple[float, float]]) -> float | None:
    pred = sum(p for _, p in pairs)
    return sum(o for o, _ in pairs) / pred if pred > 0 else None


def _ci(strata: list[list[tuple[float, float]]], rng: random.Random) -> list[float | None]:
    """Within-stratum bootstrap of the pooled lift: 2.5th and 97.5th percentile."""
    strata = [s for s in strata if s]
    if not strata:
        return [None, None]
    vals = []
    for _ in range(BOOTSTRAP):
        obs = pred = 0.0
        for s in strata:
            n = len(s)
            for _i in range(n):
                o, p = s[rng.randrange(n)]
                obs += o
                pred += p
        vals.append(obs / pred if pred > 0 else 0.0)
    vals.sort()
    return [round(vals[int(0.025 * BOOTSTRAP)], 2), round(vals[int(0.975 * BOOTSTRAP) - 1], 2)]


def repo_pairs(funcs: list[dict], d: str) -> dict[str, list[tuple[float, float]]]:
    pred = poisson_predict(funcs, "t_" + d)
    out: dict[str, list[tuple[float, float]]] = {"all": []}
    for f, p in zip(funcs, pred, strict=True):
        pair = (float(f["t_" + d]), p)
        for g in groups(f):
            out.setdefault(g, []).append(pair)
    return out


def summarize(repos: dict[str, list[dict]]) -> dict:
    """Per-repo and pooled lifts for each definition, plus H3 per repo. `repos` maps name to attached function dicts."""
    rng = random.Random(SEED)
    res: dict = {"repos": {}, "pooled": {}}
    pooled: dict[str, dict[str, list[list[tuple[float, float]]]]] = {d: {} for d in DEFS}
    for name in sorted(repos):
        funcs = repos[name]
        entry: dict = {
            "functions": len(funcs),
            "touches": {d: sum(f["t_" + d] for f in funcs) for d in DEFS},
            "lift": {},
        }
        for d in DEFS:
            per = repo_pairs(funcs, d)
            entry["lift"][d] = {}
            for g, pairs in sorted(per.items()):
                if g == "all":
                    continue
                lift = _lift(pairs)
                entry["lift"][d][g] = {
                    "n": len(pairs),
                    "lift": None if lift is None else round(lift, 2),
                    "ci": _ci([pairs], rng),
                }
                pooled[d].setdefault(g, []).append(pairs)
        active = [f for f in funcs if f["fan_out"] or f["fan_in"]]
        entry["h3_partial_spearman"] = (
            round(
                partial_spearman(
                    [f["fan_out"] for f in active],
                    [f["t_B"] for f in active],
                    [f["loc"] for f in active],
                    [f["cx"] for f in active],
                ),
                2,
            )
            if len(active) > 5
            else None
        )
        res["repos"][name] = entry
    for d in DEFS:
        res["pooled"][d] = {}
        for g in sorted(pooled[d]):
            strata = pooled[d][g]
            flat = [p for s in strata for p in s]
            lift = _lift(flat)
            res["pooled"][d][g] = {
                "n": len(flat),
                "lift": None if lift is None else round(lift, 2),
                "ci": _ci(strata, rng),
            }
    res["verdicts"] = verdicts(res)
    return res


def _excl1(cell: dict | None) -> bool:
    return bool(cell and cell["ci"][0] is not None and (cell["ci"][0] > 1 or cell["ci"][1] < 1))


def verdicts(res: dict) -> dict:
    """The pre-registered decision rules (docs/research/fix-ripple-preregistration.md), def B, on whatever repositories were run."""
    repos = res["repos"]
    n = len(repos)
    orch = {r: e["lift"]["B"].get("orchestrator") for r, e in repos.items()}
    pooled = res["pooled"]["B"]
    h1_pooled = bool(
        pooled.get("orchestrator")
        and pooled["orchestrator"]["lift"]
        and _excl1(pooled["orchestrator"])
        and pooled["orchestrator"]["lift"] > 1
    )
    h1_repos = sum(1 for c in orch.values() if _excl1(c) and c["lift"] > 1)
    h3_pos = sum(1 for e in repos.values() if (e["h3_partial_spearman"] or 0) > 0)
    cons, prod = pooled.get("consumer"), pooled.get("producer")
    h4 = bool(cons and prod and cons["lift"] and prod["lift"] and cons["ci"][0] > 1 and prod["ci"][1] < 1)
    h4_repos = sum(
        1
        for e in repos.values()
        if e["lift"]["B"].get("consumer")
        and e["lift"]["B"].get("producer")
        and (e["lift"]["B"]["consumer"]["lift"] or 0) > (e["lift"]["B"]["producer"]["lift"] or 0)
    )
    life = pooled.get("lifecycle")
    return {
        "H1": {
            "pooled": "pass" if h1_pooled else "fail",
            "repos_ci_excl_1": h1_repos,
            "of": n,
            "per_repo_majority": "pass" if n and h1_repos * 2 > n else "fail",
        },
        "H2": {"pooled": "pass" if _excl1(life) and life["lift"] > 1 else "fail"},
        "H3": {"positive_repos": h3_pos, "of": n, "verdict": "pass" if n and h3_pos * 2 > n else "fail"},
        "H4": {"pooled": "pass" if h4 else "fail", "consumer_gt_producer_repos": h4_repos, "of": n},
    }


def drop_noise_copy(repo: Path, dest: Path) -> list[str]:
    """Copy `repo` to `dest` without test / doc / vendored directories and `.git`. Returns the directory names that were removed."""
    removed: set[str] = set()

    def ignore(d: str, names: list[str]) -> list[str]:
        skip = [x for x in names if x == ".git" or (x.lower() in NOISE_DIRS and os.path.isdir(os.path.join(d, x)))]
        removed.update(x for x in skip if x != ".git")
        return skip

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(repo, dest, ignore=ignore)
    return sorted(removed)


def scan(path: Path, out: Path) -> Path:
    env = dict(os.environ, GITGALAXY_DISABLE_GIT_HISTORY="1")  # child only: never process-wide
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from gitgalaxy.galaxyscope import main; sys.exit(main())",
            str(path),
            "--db-only",
            "--output",
            str(out),
        ],
        check=True,
        env=env,
    )
    dbs = sorted(out.rglob("*_galaxy_master.db"))
    if not dbs:
        raise SystemExit(f"no *_galaxy_master.db under {out}")
    return dbs[0]


def engine_sha() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, check=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def cmd_analyze(a: argparse.Namespace) -> int:
    funcs = attach(load_graph(Path(a.db), a.strip), mine_touches(Path(a.repo), a.since))
    res = summarize({a.name: funcs})
    res["config"] = {
        "since": a.since,
        "drop_noise": False,
        "strip": a.strip,
        "engine_sha": engine_sha(),
        "bootstrap": BOOTSTRAP,
        "seed": SEED,
    }
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(res["verdicts"], sort_keys=True))
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    scratch = Path(os.environ.get("TMPDIR", "/tmp")) / "gitgalaxy-scratch" / "claude" / "fix_ripple"
    repos: dict[str, list[dict]] = {}
    cfg: dict = {
        "since": a.since,
        "drop_noise": a.drop_noise,
        "removed_dirs": [],
        "engine_sha": engine_sha(),
        "bootstrap": BOOTSTRAP,
        "seed": SEED,
        "pins": {},
    }
    for entry in manifest["repos"]:
        name = entry["name"]
        if a.only and name not in a.only:
            continue
        src = Path(a.corpora) / name
        if not src.is_dir():
            raise SystemExit(f"{src} missing: clone {entry['url']} there (outside this repo) at the pinned sha")
        head = subprocess.run(
            ["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, check=True, text=True
        ).stdout.strip()
        if entry.get("sha") and entry["sha"] != head:
            raise SystemExit(f"{name}: HEAD {head} is not the pinned {entry['sha']}")
        cfg["pins"][name] = head
        target = src
        if a.drop_noise:
            target = scratch / "copies" / name
            cfg["removed_dirs"] = sorted(set(cfg["removed_dirs"]) | set(drop_noise_copy(src, target)))
        db = scan(target, scratch / "scans" / name)
        strip = str(target).replace("\\", "/")
        repos[name] = attach(load_graph(db, strip), mine_touches(src, a.since))
    res = summarize(repos)
    res["config"] = cfg
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(res["verdicts"], sort_keys=True))
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    got = json.loads(Path(a.results).read_text(encoding="utf-8"))
    want = json.loads(Path(a.expected).read_text(encoding="utf-8")) if a.expected else None
    if want is None:
        print(json.dumps(got["verdicts"], indent=1, sort_keys=True))
        return 0
    bad = [k for k in want if got["verdicts"].get(k) != want[k]]
    for k in bad:
        print(f"VERDICT CHANGED {k}: recorded {want[k]} now {got['verdicts'].get(k)}", file=sys.stderr)
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--manifest", required=True)
    r.add_argument(
        "--corpora",
        required=True,
        help="directory holding one clone per manifest name (a sibling of the repo, never inside it)",
    )
    r.add_argument("--out", required=True)
    r.add_argument("--only", action="append")
    r.add_argument("--since", default=SINCE)
    r.add_argument(
        "--drop-noise",
        action="store_true",
        help="scan a copy without test/doc/vendored dirs (changes the graph; default off)",
    )
    r.set_defaults(fn=cmd_run)
    an = sub.add_parser("analyze")
    an.add_argument("--repo", required=True)
    an.add_argument("--db", required=True)
    an.add_argument("--name", required=True)
    an.add_argument("--out", required=True)
    an.add_argument("--strip", default="")
    an.add_argument("--since", default=SINCE)
    an.set_defaults(fn=cmd_analyze)
    c = sub.add_parser("check")
    c.add_argument("results")
    c.add_argument(
        "--expected", help="JSON of recorded verdicts (a subset of the results' `verdicts`); exit 1 on any change"
    )
    c.set_defaults(fn=cmd_check)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
