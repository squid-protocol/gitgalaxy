#!/usr/bin/env python3
"""libclang call-graph reference for the C ports of the DOOM corpus (#5630 step 4, #3784).

    python tests/tools/doom_speedrun/doom_clang_calls.py [--only a,b] [--work DIR] [--sha SHA]

Where ``callgraph_oracle.py`` reads text (tree-sitter), this resolves calls the way a compiler does: it runs
``tests/tools/clang_callgraph.py`` (the #3784 C reference: preprocessor first, calls linked to the repo's definitions)
on a port's clone and compares its caller -> callee edges with the engine's ``calls_out_to`` from the scan under
``<work>/scans/<sha>/<port>``. A caller is matched by (file, name); both sides drop self-edges, vendored files and
callees the port does not define. Recall = clang edges the engine has; precision = engine edges clang has.

Reported, never scored: with no build system the headers are guessed (every header directory is an ``-I`` path), so a
disagreement is a lead to read, not a verdict (``--examples`` prints some). C ports only (the C reference does not
read C++); licensed ports only. Needs the ``libclang`` wheel (the selfscan venv has it).
"""

import argparse
import collections
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import callgraph_oracle  # noqa: E402
import clang_callgraph  # noqa: E402
import doom_scorer  # noqa: E402

# Licensed ports whose engine functions are all C (the C reference parses .c files only).
C_PORTS = ("linuxdoom", "chocolate-doom", "crispy-doom", "doomgeneric", "doomretro", "prboom-plus", "doom-ascii",
           "sdl-doom", "puredoom", "fastdoom", "inter-doom", "doom-wasm", "dsda-doom", "woof", "nugget-doom")  # fmt: skip
EXAMPLES = 5


def engine_edges(rows):
    """{(file, caller): callee names} from ``load_port`` rows (the union over same-named definitions in a file)."""
    out = collections.defaultdict(set)
    for rel, lang, name, _start, callees in rows:
        if lang == "c":
            out[(rel, callee_bare(name))] |= {callee_bare(c) for c in callees}
    return out


def callee_bare(name):
    return callgraph_oracle.bare(name)


def clang_edges(contract, vendored=None):
    """({(file, caller): callee names}, defined names) from the clang contract, vendored files dropped."""
    keep = (lambda rel: not vendored(rel)) if vendored else (lambda rel: True)
    out, defined = collections.defaultdict(set), set()
    for rel, name, _line in contract["defs"]:
        if keep(rel):
            defined.add(name)
            out[(rel, name)]
    for (crel, cname, _), (erel, ename, _), _line in contract["edges"]:
        if keep(crel) and keep(erel):
            out[(crel, cname)].add(ename)
    return out, defined


def compare(engine, clang, defined, fatal=()):
    """Recall / precision over the callers both sides define, each disagreement listed as ``file: caller -> callee``.

    ``fatal`` names the files whose parse hit a fatal error (a generated ``config.h`` or a system header missing from
    the clone): clang guesses the types after it and can lose a call to a function of its own file (opl.c without
    ``config.h``). Nearly every file of a port without a build is in it, so none is dropped; ``disagreements_in_clean_files``
    counts the ones in a file clang parsed without one, the part of the delta that is not a missing-header artefact."""
    agree = n_clang = n_eng = 0
    missed, extra = [], []
    callers = sorted(set(engine) & set(clang))
    for key in callers:
        want = clang[key] - {key[1]}
        have = (engine[key] & defined) - {key[1]}
        agree += len(want & have)
        n_clang += len(want)
        n_eng += len(have)
        missed += [f"{key[0]}: {key[1]} -> {c}" for c in sorted(want - have)]
        extra += [f"{key[0]}: {key[1]} -> {c}" for c in sorted(have - want)]
    return {
        "files_fatal": len(fatal),
        "callers_compared": len(callers),
        "callers_engine_only": len(set(engine) - set(clang)),
        "callers_clang_only": len(set(clang) - set(engine)),
        "clang_edges": n_clang,
        "engine_edges": n_eng,
        "agree": agree,
        "recall": round(agree / n_clang, 4) if n_clang else 1.0,
        "precision": round(agree / n_eng, 4) if n_eng else 1.0,
        "disagreements_in_clean_files": sum(line.split(":")[0] not in fatal for line in missed + extra),
        "missed": missed,
        "engine_only": extra,
    }


def run_port(name, work, sha):
    repo, db = work / "repos" / name, callgraph_oracle.find_db(work / "scans" / sha / name)
    if db is None or not repo.is_dir():
        return None
    vendored = doom_scorer._engine_vendor_test(repo)
    engine = engine_edges(callgraph_oracle.load_port(repo, db, vendored))
    contract = clang_callgraph.build(repo, "c")
    clang, defined = clang_edges(contract, vendored)
    return compare(engine, clang, defined, set(contract.get("fatal", ())))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help=f"comma-separated ports (default: {', '.join(C_PORTS)})")
    ap.add_argument("--work", type=Path, default=callgraph_oracle.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--sha", help="engine SHA of the scans to read (default: this checkout's HEAD)")
    ap.add_argument("--examples", type=int, default=EXAMPLES, help="disagreements to print per port")
    args = ap.parse_args(argv)
    if clang_callgraph.libclang_version() is None:
        print("doom_clang_calls: libclang is not installed; nothing to compare")
        return 0
    work, sha = args.work.resolve(), args.sha or callgraph_oracle.engine_sha()
    names = [n for n in (args.only.split(",") if args.only else C_PORTS) if n]
    if bad := sorted(set(names) - (set(C_PORTS) & callgraph_oracle.LICENSED)):
        raise SystemExit(f"doom_clang_calls: not a licensed C port: {', '.join(bad)}")
    result = {}
    for name in names:
        res = run_port(name, work, sha)
        if res is None:
            print(f"doom_clang_calls: no scan or clone for {name} under {work} at {sha}")
            continue
        result[name] = res
        print(f"{name:16} recall {res['recall']:.4f} precision {res['precision']:.4f} over {res['clang_edges']} clang "
              f"edges, {res['callers_compared']} callers ({res['files_fatal']} files with a fatal parse error; clang-only {res['callers_clang_only']}, "
              f"engine-only {res['callers_engine_only']}; {res['disagreements_in_clean_files']} disagreements in clean files)")  # fmt: skip
        for label, key in (("missed", "missed"), ("engine-only", "engine_only")):
            for line in res[key][: args.examples]:
                print(f"    {label}: {line}")
    dest = work / "results" / sha
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "clang_calls.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"wrote {dest / 'clang_calls.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
