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
Per-file input decomposition for the gated `_calc_*` risk formulas (#2916,
generalising #2910's audit_documentation_inputs.py, which decomposed the
pre-#2908 density formula and retired with it in Phase 3).

For every scanned file it reads the inputs a formula consumes straight out of
the galaxyscope database (the SHORT_KEY_MAP column names), calls the
`SignalProcessor._calc_<metric>` directly with them, and compares the result to
the recorded `risk_<metric>`. A residual means the decomposition no longer
explains the score -- the fact every score contract rests on -- so the tool
exits 1 (except `verification`, see its adapter note).

One adapter per formula in ADAPTERS: which `file_data` columns feed which call
arguments, how `fid`/`irc`/`ot` are obtained (`_language_constants`), how `mp`
is obtained (`_get_locational_multipliers(file_path)`). Like the #2910 template,
the popularity multiplier is tried both on and off per file and the reading that
reproduces is reported (popularity 0 cannot tell them apart).

Outputs: one row per file; a CLUSTER table keyed by the metric's dominant input;
a SENSITIVITY table (score vs that input over its corpus range); `--summary`
(one paragraph: n files, residuals, dominant input, points-per-unit).

Usage:
    python tests/tools/audit_score_inputs.py documentation --db path/to/x_galaxy_master.db
    python tests/tools/audit_score_inputs.py api_exposure --corpus /path/to/keyword-rosetta/data
    python tests/tools/audit_score_inputs.py tech_debt --corpus ... --languages c,python --summary

Adapters shipped (the five carrying open-defect cells or a length leak):
documentation, api_exposure, tech_debt, cognitive_load, verification.

KNOWN LIMIT (verification): the per-function `impact` the formula's function
loop consumes is computed in detector.py and NEVER persisted (function_data has
complexity/loc/hit columns but no impact). The adapter therefore reproduces the
FILE-level terms with `functions=[]`; any file whose score carries a function
term shows as a residual tagged `function-term`, reported but not exit-failing
-- stating the recording gap loudly instead of faking a reconstruction.
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
from dataclasses import dataclass, field
from typing import Callable

from gitgalaxy.metrics.signal_processor import SignalProcessor

EPSILON_DEFAULT = 0.01
IGNORED_BASENAMES = {"expected_signals.json", "pyproject.toml"}


# ---------------------------------------------------------------------------
# adapters
# ---------------------------------------------------------------------------


@dataclass
class Adapter:
    recorded_col: str
    # formula signal key -> file_data column
    signal_cols: dict[str, str]
    # other file_data columns the repro reads (guarded at load time)
    extra_cols: tuple[str, ...]
    repro: Callable[[SignalProcessor, dict, int], float]  # (p, row, popularity) -> score
    cluster_label: str
    cluster_key: Callable[[dict], int]
    sens_label: str
    sens: Callable[[SignalProcessor, str], list[tuple[int, float]]]
    uses_popularity: bool = True
    exit_on_residual: bool = True
    note: str = ""
    row_cols: tuple[str, ...] = field(default_factory=tuple)  # compact per-file columns
    # #2908 Phase 3: per-unit formulas read function_data, not file_data columns.
    # When set, read_db attaches each file's units as row["functions"] (the shape
    # SignalProcessor consumes) plus derived units/units_public/units_documented/
    # refl_hits keys for the row and cluster tables.
    needs_functions: bool = False


def _signals(row: dict, cols: dict[str, str]) -> dict[str, int]:
    return {k: int(row.get(c) or 0) for k, c in cols.items()}


def _mp(p: SignalProcessor, row: dict, which: str) -> float:
    return p._get_locational_multipliers(row["file_path"] or row["file_name"]).get(which, 1.0)


def _consts(p: SignalProcessor, row: dict):
    return p._language_constants(row["language"])  # (irc, ot, fid)


def _repro_documentation(p: SignalProcessor, row: dict, popularity: int) -> float:
    # #2908 Phase 3: the ratio reads the recorded per-unit attributes and the
    # umbrella only. doc_umbrella is not persisted in file_data; a corpus scan
    # carries no GuideStar folder, so 0.0 is the recorded reality, not a guess.
    return float(p._calc_documentation(row.get("functions") or [], doc_umbrella=0.0))


def _repro_api_exposure(p: SignalProcessor, row: dict, popularity: int) -> float:
    return float(
        p._calc_api_exposure(
            _signals(row, ADAPTERS["api_exposure"].signal_cols),
            max(int(row.get("total_loc") or row["coding_loc"] or 0), 1),
            popularity,
        )
    )


def _repro_tech_debt(p: SignalProcessor, row: dict, popularity: int) -> float:
    irc, _ot, _fid = _consts(p, row)
    return float(
        p._calc_tech_debt(
            max(int(row["coding_loc"] or 0), 1),
            _signals(row, ADAPTERS["tech_debt"].signal_cols),
            irc,
            _mp(p, row, "debt"),
        )
    )


def _repro_cognitive_load(p: SignalProcessor, row: dict, popularity: int) -> float:
    _irc, _ot, fid = _consts(p, row)
    score, _density = p._calc_cog_load(
        max(int(row["coding_loc"] or 0), 1),
        _signals(row, ADAPTERS["cognitive_load"].signal_cols),
        fid,
        _mp(p, row, "cog"),
        float(row.get("func_complexity_gini") or 0.0),
    )
    return float(score)


def _repro_verification(p: SignalProcessor, row: dict, popularity: int) -> float:
    _irc, ot, fid = _consts(p, row)
    return float(
        p._calc_verification(
            max(int(row["coding_loc"] or 0), 1),
            False,  # is_protected is not persisted per file
            _signals(row, ADAPTERS["verification"].signal_cols),
            ot,
            fid,
            _mp(p, row, "test"),
            [],  # per-function impact is not persisted -- see KNOWN LIMIT above
            {},
            umbrella_bonus=0.0,
            popularity=popularity,
        )
    )


def _sens_generic(calc: Callable[[SignalProcessor, int], float]) -> Callable:
    def go(p: SignalProcessor, language: str) -> list[tuple[int, float]]:
        return [(x, float(calc(p, x))) for x in range(0, 8)]

    return go


ADAPTERS: dict[str, Adapter] = {
    "documentation": Adapter(
        recorded_col="risk_documentation",
        signal_cols={},
        extra_cols=("coding_loc",),
        repro=_repro_documentation,
        cluster_label="extracted units per file",
        cluster_key=lambda r: int(r.get("units") or 0),
        sens_label="score vs units documented (8 public units, no reflection, no umbrella)",
        sens=lambda p, lang: [
            (
                n,
                float(
                    p._calc_documentation(
                        [
                            {"name": f"u{i}", "is_public": True, "is_documented": i < n, "hit_vector": {}}
                            for i in range(8)
                        ]
                    )
                ),
            )
            for n in range(0, 8)
        ],
        uses_popularity=False,
        row_cols=("coding_loc", "units", "units_public", "units_documented", "refl_hits"),
        needs_functions=True,
    ),
    "api_exposure": Adapter(
        recorded_col="risk_api_exposure",
        signal_cols={"api": "arch_api", "encapsulation": "def_encapsulation"},
        extra_cols=("coding_loc", "total_loc"),
        repro=_repro_api_exposure,
        cluster_label="adjusted api per file",
        cluster_key=lambda r: int(r.get("arch_api") or 0),
        sens_label="score vs api (encapsulation 0, total_loc 15, popularity 0)",
        sens=lambda p, lang: [(api, float(p._calc_api_exposure({"api": api}, 15, 0))) for api in range(0, 8)],
        row_cols=("total_loc", "arch_api", "def_encapsulation"),
    ),
    "tech_debt": Adapter(
        recorded_col="risk_tech_debt",
        signal_cols={
            "planned_debt": "state_planned_debt",
            "fragile_debt": "state_fragile_debt",
            "unreferenced_by_name": "state_unreferenced",
            "duplicate_logic": "state_slop_duplicates",
        },
        extra_cols=("coding_loc",),
        repro=_repro_tech_debt,
        cluster_label="planned+fragile debt per file",
        cluster_key=lambda r: int(r.get("state_planned_debt") or 0) + int(r.get("state_fragile_debt") or 0),
        sens_label="score vs fragile_debt (planned 0, slop 0, loc 15)",
        sens=lambda p, lang: [
            (n, float(p._calc_tech_debt(15, {"fragile_debt": n}, p._language_constants(lang)[0], 1.0)))
            for n in range(0, 8)
        ],
        uses_popularity=False,
        row_cols=("coding_loc", "state_planned_debt", "state_fragile_debt", "state_unreferenced"),
    ),
    "cognitive_load": Adapter(
        recorded_col="risk_cognitive_load",
        signal_cols={
            "branch": "struct_branch",
            "state_mutation": "state_flux",
            "concurrency": "arch_concurrency",
            "reflection_metaprogramming": "state_heat_triggers",
            "doc": "def_doc",
        },
        extra_cols=("coding_loc", "func_complexity_gini"),
        repro=_repro_cognitive_load,
        cluster_label="branch hits per file",
        cluster_key=lambda r: int(r.get("struct_branch") or 0),
        sens_label="score vs branch (flux 0, doc 0, gini 0, loc 15)",
        sens=lambda p, lang: [
            (b, float(p._calc_cog_load(15, {"branch": b}, p._language_constants(lang)[2], 1.0, 0.0)[0]))
            for b in range(0, 8)
        ],
        uses_popularity=False,
        row_cols=("coding_loc", "struct_branch", "state_flux", "func_complexity_gini"),
    ),
    "verification": Adapter(
        recorded_col="risk_verification",
        signal_cols={
            "high_risk_execution": "state_danger",
            "test": "def_test",
            "safety": "def_safety",
            "test_skip": "def_test_skip",
        },
        extra_cols=("coding_loc",),
        repro=_repro_verification,
        cluster_label="file-level danger hits",
        cluster_key=lambda r: int(r.get("state_danger") or 0),
        sens_label="score vs high_risk_execution (functions [], loc 15)",
        sens=lambda p, lang: [
            (
                d,
                float(
                    p._calc_verification(
                        15,
                        False,
                        {"high_risk_execution": d},
                        p._language_constants(lang)[1],
                        p._language_constants(lang)[2],
                        1.0,
                        [],
                        {},
                    )
                ),
            )
            for d in range(0, 8)
        ],
        exit_on_residual=False,
        note=(
            "KNOWN LIMIT: per-function `impact` is not persisted, so the function\n"
            "term runs with functions=[] -- residuals tagged `function-term` are the\n"
            "recording gap itself, reported but not exit-failing (#2916)."
        ),
        row_cols=("coding_loc", "state_danger", "def_test", "def_safety"),
    ),
}


# ---------------------------------------------------------------------------
# reading (SELECT *, guarded)
# ---------------------------------------------------------------------------


def read_db(db_path: pathlib.Path, adapter: Adapter, language_hint: str | None) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    have = {r[1] for r in conn.execute("PRAGMA table_info(file_data)")}
    needed = (
        {"file_name", "file_path", "language", "popularity", adapter.recorded_col}
        | set(adapter.signal_cols.values())
        | set(adapter.extra_cols)
    )
    missing = sorted(c for c in needed if c not in have)
    if missing:
        raise SystemExit(f"{db_path}: file_data lacks {missing}")
    rows = [dict(r) for r in conn.execute("SELECT * FROM file_data ORDER BY file_name")]
    if adapter.needs_functions:
        fhave = {r[1] for r in conn.execute("PRAGMA table_info(function_data)")}
        fneed = {"file_id", "is_public", "is_documented", "state_heat_triggers"}
        if not fneed <= fhave:
            raise SystemExit(f"{db_path}: function_data lacks {sorted(fneed - fhave)} -- scan with a #2908-Phase-2 engine")
        by_file: dict[int, list[dict]] = {}
        for fr in conn.execute(
            "SELECT file_id, func_name, is_public, is_documented, state_heat_triggers FROM function_data"
        ):
            by_file.setdefault(fr["file_id"], []).append(
                {
                    "name": fr["func_name"],
                    "is_public": bool(fr["is_public"]),
                    "is_documented": bool(fr["is_documented"]),
                    "hit_vector": {"reflection_metaprogramming": int(fr["state_heat_triggers"] or 0)},
                }
            )
        for r in rows:
            units = by_file.get(r["id"], [])
            r["functions"] = units
            r["units"] = len(units)
            r["units_public"] = sum(1 for u in units if u["is_public"])
            r["units_documented"] = sum(1 for u in units if u["is_documented"])
            r["refl_hits"] = sum(u["hit_vector"]["reflection_metaprogramming"] for u in units)
    conn.close()
    out = []
    for r in rows:
        if r["file_name"] in IGNORED_BASENAMES:
            continue
        if language_hint:
            r["language"] = language_hint
        out.append(r)
    return out


def scan_folder(folder: pathlib.Path, out_dir: pathlib.Path) -> pathlib.Path:
    exe = os.environ.get("GALAXYSCOPE_BIN")
    cmd = [exe] if exe else [sys.executable, "-c", "from gitgalaxy.galaxyscope import main; main()"]
    before = set(out_dir.rglob("*.db"))
    result = subprocess.run([*cmd, str(folder), "--db-only"], cwd=out_dir, capture_output=True, text=True, timeout=600)
    dbs = sorted(p for p in out_dir.rglob("*.db") if p not in before)
    if result.returncode != 0 or not dbs:
        sys.stderr.write(result.stdout[-2000:] + result.stderr[-2000:])
        raise SystemExit(f"galaxyscope failed on {folder} (rc={result.returncode})")
    return dbs[0]


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def run(metric: str, files: list[dict], *, epsilon: float, summary: bool) -> int:
    a = ADAPTERS[metric]
    p = SignalProcessor()
    if a.note:
        print(a.note + "\n")
    residuals: list[dict] = []
    pop_on = pop_off = 0
    hdr = " ".join(f"{c.split('_')[-1][:5]:>5}" for c in a.row_cols)
    print(f"{'language':16s} {'file':20s} {hdr} | {'recorded':>8} {'repro':>8} {'resid':>7}")
    by_key: dict[int, list[dict]] = defaultdict(list)
    for f in files:
        recorded = float(f.get(a.recorded_col) or 0.0)
        popularity = int(f.get("popularity") or 0)
        if a.uses_popularity:
            w = a.repro(p, f, popularity)
            wo = a.repro(p, f, 0)
            distinguishable = abs(w - wo) > epsilon
            if distinguishable and abs(w - recorded) <= epsilon:
                repro = w
                pop_on += 1
            elif abs(wo - recorded) <= epsilon:
                repro = wo
                if distinguishable:
                    pop_off += 1
            else:
                repro = w
        else:
            repro = a.repro(p, f, popularity)
        resid = recorded - repro
        bad = abs(resid) > epsilon
        if bad:
            residuals.append(f)
        tag = ("   <-- function-term" if metric == "verification" else "   <-- NOT REPRODUCED") if bad else ""
        vals = " ".join(f"{int(f.get(c) or 0):>5}" for c in a.row_cols)
        print(f"{f['language']:16s} {f['file_name'][:20]:20s} {vals} | {recorded:>8.2f} {repro:>8.2f} {resid:>7.2f}{tag}")
        by_key[a.cluster_key(f)].append(f)

    print(f"\n## CLUSTER: files by {a.cluster_label}")
    print(f"{'key':>4} {'files':>5} {'score min':>9} {'score max':>9}  languages")
    for k in sorted(by_key):
        g = by_key[k]
        scores = [float(x.get(a.recorded_col) or 0.0) for x in g]
        langs = sorted({x["language"] for x in g})
        print(f"{k:>4} {len(g):>5} {min(scores):>9.2f} {max(scores):>9.2f}  {', '.join(langs)}")

    steps: list[float] = []
    if files:
        print(f"\n## SENSITIVITY: {a.sens_label}")
        rows = a.sens(p, files[0]["language"])
        print("  x      " + " ".join(f"{x:>6}" for x, _ in rows))
        print("  score  " + " ".join(f"{s:>6.1f}" for _, s in rows))
        steps = [rows[i + 1][1] - rows[i][1] for i in range(1, len(rows) - 1)]
        if steps:
            print(f"  points per additional unit (1..7): {min(steps):.1f} to {max(steps):.1f}")

    if a.uses_popularity:
        print(f"\npopularity multiplier: reproduced with it on {pop_on} file(s), with it off {pop_off} file(s)")

    if summary:
        dom = a.cluster_label
        ppu = f"{min(steps):.1f}-{max(steps):.1f}" if steps else "n/a"
        print(
            f"\n--summary: {len(files)} files; {len(residuals)} residual(s); dominant input: {dom}; "
            f"points per unit: {ppu}."
        )

    if residuals and a.exit_on_residual:
        print(f"\nFAIL: {len(residuals)} file(s) not reproduced from their recorded inputs (epsilon {epsilon}).")
        return 1
    if residuals:
        print(f"\nWARN: {len(residuals)} residual file(s) -- see the adapter's KNOWN LIMIT note; exit 0 by design.")
        return 0
    print(f"\nOK: every recorded {a.recorded_col} reproduced from its inputs ({len(files)} files).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("metric", choices=sorted(ADAPTERS))
    ap.add_argument("--db", action="append", default=[], help="a galaxyscope *_galaxy_master.db (repeatable)")
    ap.add_argument("--corpus", help="keyword-rosetta data/ directory: scan each language folder")
    ap.add_argument("--languages", help="comma-separated subset of --corpus folders")
    ap.add_argument("--epsilon", type=float, default=EPSILON_DEFAULT)
    ap.add_argument("--summary", action="store_true", help="one-paragraph digest for the PR body")
    args = ap.parse_args(argv)
    if not args.db and not args.corpus:
        ap.error("give --db or --corpus")

    adapter = ADAPTERS[args.metric]
    files: list[dict] = []
    for db in args.db:
        files.extend(read_db(pathlib.Path(db), adapter, None))
    if args.corpus:
        root = pathlib.Path(args.corpus)
        wanted = set(args.languages.split(",")) if args.languages else None
        with tempfile.TemporaryDirectory(prefix="score_inputs_") as tmp:
            for folder in sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")):
                if wanted and folder.name not in wanted:
                    continue
                out = pathlib.Path(tmp) / folder.name
                out.mkdir()
                files.extend(read_db(scan_folder(folder, out), adapter, folder.name))
    files.sort(key=lambda f: (f["language"], f["file_name"]))
    return run(args.metric, files, epsilon=args.epsilon, summary=args.summary)


if __name__ == "__main__":
    sys.exit(main())
