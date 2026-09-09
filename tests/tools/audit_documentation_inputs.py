#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Per-file input decomposition for `_calc_documentation` (epic #2908, Phase 0).

The bias report says `risk_documentation` is the corpus's most variable gated score
and its one confirmed length leak. This tool shows WHY, file by file, and keeps that
explanation honest: for every scanned file it reads the inputs the formula consumes
straight out of the galaxyscope database, calls `SignalProcessor._calc_documentation`
directly with them, and compares the result to the `risk_documentation` the engine
recorded. A residual means the decomposition no longer explains the score -- which is
the fact the epic's design rests on, so the tool exits nonzero.

What it reads per file (DB column -> formula input):

    arch_api              -> raw_signals["api"]     the ADJUSTED api (rule hits + orphan credit)
    raw_arch_api                                    the rule's own count; credit = arch_api - raw
    def_doc               -> raw_signals["doc"]
    def_ownership         -> raw_signals["ownership"]
    state_heat_triggers   -> raw_signals["reflection_metaprogramming"]  (_dynamism)
    doc_loc               -> doc_loc
    coding_loc            -> loc
    popularity, silo_risk -> the multipliers
    file_path             -> the path modifier (`mp`)

`functions` is passed empty: the opaque-execution term needs a function with impact
above 50 and no docstring, which no corpus file has. If a real repository's file
carries one, that file shows up as a residual here -- deliberately, so the term's
contribution is never silently folded into "api".

Three outputs: one row per file; the CLUSTER table (files grouped by adjusted api per
file, which is the whole story on the corpus); and the SENSITIVITY table (score vs
adjusted api with every other input held at the corpus values), which is what makes a
+-1 api error a +-13 point score error.

Usage:
    python tests/tools/audit_documentation_inputs.py --db path/to/<x>_galaxy_master.db [--db ...]
    python tests/tools/audit_documentation_inputs.py --corpus /path/to/keyword-rosetta/data
    python tests/tools/audit_documentation_inputs.py --corpus ... --languages c,cpp,makefile

`--corpus` scans each language folder with galaxyscope (`--db-only`) into a temporary
directory, exactly as keyword-rosetta's `verify_language.py` does. Direct invocation of
`_calc_documentation` is the same isolation technique `audit_length_invariance.py` and
`audit_risk_equations.py` use (see their docstrings for the #1055 precedent).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass

from gitgalaxy.metrics.signal_processor import SignalProcessor

EPSILON_DEFAULT = 0.01
IGNORED_BASENAMES = {"expected_signals.json", "pyproject.toml"}


@dataclass
class FileInputs:
    language: str
    file_name: str
    file_path: str
    coding_loc: int
    doc_loc: int
    raw_api: int
    api: int
    doc: int
    ownership: int
    reflection: int
    popularity: int
    silo: float
    recorded: float

    @property
    def credit(self) -> int:
        return self.api - self.raw_api


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------


def read_db(db_path: pathlib.Path, language_hint: str | None = None) -> list[FileInputs]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    have = {r[1] for r in conn.execute("PRAGMA table_info(file_data)")}
    needed = [
        "file_name",
        "file_path",
        "language",
        "coding_loc",
        "doc_loc",
        "raw_arch_api",
        "arch_api",
        "def_doc",
        "def_ownership",
        "state_heat_triggers",
        "popularity",
        "silo_risk",
        "risk_documentation",
    ]
    missing = [c for c in needed if c not in have]
    if missing:
        raise SystemExit(f"{db_path}: file_data lacks {missing}")
    rows = conn.execute(f"SELECT {', '.join(needed)} FROM file_data ORDER BY file_name").fetchall()
    out: list[FileInputs] = []
    for r in rows:
        if r["file_name"] in IGNORED_BASENAMES:
            continue
        out.append(
            FileInputs(
                language=language_hint or (r["language"] or "?"),
                file_name=r["file_name"],
                file_path=r["file_path"] or r["file_name"],
                coding_loc=int(r["coding_loc"] or 0),
                doc_loc=int(r["doc_loc"] or 0),
                raw_api=int(r["raw_arch_api"] or 0),
                api=int(r["arch_api"] or 0),
                doc=int(r["def_doc"] or 0),
                ownership=int(r["def_ownership"] or 0),
                reflection=int(r["state_heat_triggers"] or 0),
                popularity=int(r["popularity"] or 0),
                silo=float(r["silo_risk"] or 0.0),
                recorded=float(r["risk_documentation"] or 0.0),
            )
        )
    conn.close()
    return out


def scan_folder(folder: pathlib.Path, out_dir: pathlib.Path) -> pathlib.Path:
    """galaxyscope --db-only over one folder; returns the produced sqlite path."""
    exe = os.environ.get("GALAXYSCOPE_BIN")
    cmd = [exe] if exe else [sys.executable, "-c", "from gitgalaxy.galaxyscope import main; main()"]
    before = set(out_dir.rglob("*.db"))
    result = subprocess.run(
        [*cmd, str(folder), "--db-only"],
        cwd=out_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    dbs = sorted(p for p in out_dir.rglob("*.db") if p not in before)
    if result.returncode != 0 or not dbs:
        sys.stderr.write(result.stdout[-2000:] + result.stderr[-2000:])
        raise SystemExit(f"galaxyscope failed on {folder} (rc={result.returncode})")
    return dbs[0]


# ---------------------------------------------------------------------------
# reproduction
# ---------------------------------------------------------------------------


def reproduce(p: SignalProcessor, f: FileInputs, *, popularity: int, umbrella: float) -> float:
    _irc, _ot, fid = p._language_constants(f.language)
    mp = p._get_locational_multipliers(f.file_path).get("doc", 1.0)
    signals = {
        "api": f.api,
        "doc": f.doc,
        "ownership": f.ownership,
        "reflection_metaprogramming": f.reflection,
    }
    return float(
        p._calc_documentation(
            max(f.coding_loc, 1),
            f.doc_loc,
            signals,
            fid,
            mp,
            None,
            doc_umbrella=umbrella,
            popularity=popularity,
            silo_exposure=f.silo,
        )
    )


def sensitivity(p: SignalProcessor, language: str, *, doc_loc: int = 2, loc: int = 15) -> list[tuple[int, float]]:
    """score vs adjusted api with every other input at the corpus a/b/c values."""
    _irc, _ot, fid = p._language_constants(language)
    rows = []
    for api in range(0, 8):
        s = p._calc_documentation(loc, doc_loc, {"api": api}, fid, 1.0, None)
        rows.append((api, float(s)))
    return rows


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def run(files: list[FileInputs], *, epsilon: float, umbrella: float) -> int:
    p = SignalProcessor()
    residuals = 0
    popularity_applied = 0
    popularity_ignored = 0
    print(
        f"{'language':16s} {'file':18s} {'loc':>4} {'dloc':>4} {'raw':>3} {'api':>3} {'crd':>3} "
        f"{'doc':>3} {'own':>3} {'rfl':>3} {'pop':>3} | {'recorded':>8} {'repro':>8} {'resid':>7}"
    )
    by_api: dict[int, list[FileInputs]] = defaultdict(list)
    for f in files:
        with_pop = reproduce(p, f, popularity=f.popularity, umbrella=umbrella)
        without = reproduce(p, f, popularity=0, umbrella=umbrella)
        # The formula multiplies by (1 + popularity / 10), but the per-file
        # `popularity` the DB records is only what `meta` carried at scoring
        # time. Report which reading reproduced, counting only files where the
        # two readings differ (popularity 0 cannot tell them apart).
        distinguishable = abs(with_pop - without) > epsilon
        if distinguishable and abs(with_pop - f.recorded) <= epsilon:
            repro = with_pop
            popularity_applied += 1
        elif abs(without - f.recorded) <= epsilon:
            repro = without
            if distinguishable:
                popularity_ignored += 1
        else:
            repro = with_pop
        resid = f.recorded - repro
        flag = "" if abs(resid) <= epsilon else "   <-- NOT REPRODUCED"
        if flag:
            residuals += 1
        print(
            f"{f.language:16s} {f.file_name:18s} {f.coding_loc:>4} {f.doc_loc:>4} {f.raw_api:>3} {f.api:>3} "
            f"{f.credit:>3} {f.doc:>3} {f.ownership:>3} {f.reflection:>3} {f.popularity:>3} | "
            f"{f.recorded:>8.2f} {repro:>8.2f} {resid:>7.2f}{flag}"
        )
        by_api[f.api].append(f)

    print("\n## CLUSTER: files by adjusted api per file (the score is a function of this column)")
    print(
        f"{'api':>3} {'files':>5} {'score min':>9} {'score max':>9}  languages (a/b/c-style files; main listed as <lang>/main)"
    )
    for api in sorted(by_api):
        group = by_api[api]
        scores = [g.recorded for g in group]
        langs = sorted({g.language if not g.file_name.startswith("main") else f"{g.language}/main" for g in group})
        print(f"{api:>3} {len(group):>5} {min(scores):>9.2f} {max(scores):>9.2f}  {', '.join(langs)}")

    if files:
        print("\n## SENSITIVITY: score vs adjusted api (doc_loc 2, doc 0, ownership 0, reflection 0, loc 15)")
        rows = sensitivity(p, files[0].language)
        print("  api    " + " ".join(f"{api:>6}" for api, _ in rows))
        print("  score  " + " ".join(f"{s:>6.1f}" for _, s in rows))
        steps = [rows[i + 1][1] - rows[i][1] for i in range(1, len(rows) - 1)]
        print(f"  points per additional api hit (api 1..7): {min(steps):.1f} to {max(steps):.1f}")

    print(
        f"\npopularity multiplier: reproduced with it on {popularity_applied} file(s), "
        f"with it off {popularity_ignored} file(s)"
    )
    if residuals:
        print(f"\nFAIL: {residuals} file(s) not reproduced from their recorded inputs (epsilon {epsilon}).")
        return 1
    print(f"\nOK: every recorded risk_documentation reproduced from its inputs ({len(files)} files).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", action="append", default=[], help="a galaxyscope *_galaxy_master.db (repeatable)")
    ap.add_argument("--corpus", help="keyword-rosetta data/ directory: scan each language folder")
    ap.add_argument("--languages", help="comma-separated subset of --corpus folders")
    ap.add_argument("--epsilon", type=float, default=EPSILON_DEFAULT)
    ap.add_argument("--umbrella", type=float, default=0.0, help="doc_umbrella to assume (corpus folders have none)")
    args = ap.parse_args(argv)
    if not args.db and not args.corpus:
        ap.error("give --db or --corpus")

    files: list[FileInputs] = []
    for db in args.db:
        files.extend(read_db(pathlib.Path(db)))
    if args.corpus:
        root = pathlib.Path(args.corpus)
        wanted = set(args.languages.split(",")) if args.languages else None
        folders = sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith("."))
        with tempfile.TemporaryDirectory(prefix="doc_inputs_") as tmp:
            for folder in folders:
                if wanted and folder.name not in wanted:
                    continue
                out = pathlib.Path(tmp) / folder.name
                out.mkdir()
                files.extend(read_db(scan_folder(folder, out), language_hint=folder.name))
    files.sort(key=lambda f: (f.language, f.file_name))
    return run(files, epsilon=args.epsilon, umbrella=args.umbrella)


if __name__ == "__main__":
    sys.exit(main())
