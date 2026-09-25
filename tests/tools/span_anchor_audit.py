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
Span anchoring: how often a function's recorded `start_line` sits BEFORE its
declaration, on lines that belong to other code (#3543).

A unit is MIS-ANCHORED when the line its `start_line` names does not contain the
unit's name, and every line from there down to the declaration (the first line,
within a window, that does) is blank, a comment, or ENDS a previous construct:
`{`, `}`, `,`, `;` or `*/`. That is the shape a `func_start` pattern leaves when
its leading class swallows the newline before the declaration -- the span opens
on the class/interface header, the previous member's `},` or a docblock's `*/`.

What is NOT mis-anchored, by construction: a declaration that starts on an
annotation, attribute, decorator, `template <...>` or C return-type line. Those
lines do not end a previous construct, and the repo counts them as part of the
declaration (see docs/func_start_rule_contract.md).

Measured on language-crucible from one in-process scan with THIS checkout's
engine, reading `function_data` back -- the real pipeline, not an extractor
built from LANGUAGE_DEFINITIONS (#2806). Lower is better; --ci fails a language
whose rate rises beyond the tolerance, so a fix locks in with --regenerate.

    python tests/tools/span_anchor_audit.py                # report
    python tests/tools/span_anchor_audit.py --samples 5    # + examples per language
    python tests/tools/span_anchor_audit.py --ci           # gate vs the baseline
    python tests/tools/span_anchor_audit.py --regenerate   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CRUCIBLE = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))
BASELINE = REPO_ROOT / "tests" / "span_anchor_baseline.json"

# Gate tolerance, in percentage points, before --ci calls a rise a regression.
TOLERANCE_PP = 0.5
# A language with fewer measured units than this is reported but not gated.
MIN_GATED_UNITS = 20
# How far below start_line the declaration may be (a long stripped docblock).
WINDOW = 60

_ENDS_CONSTRUCT = re.compile(r"(?:[{},;]|\*/)\s*$")
_HASH_COMMENT_LANGS = frozenset({"python", "ruby", "perl", "shell", "php", "powershell", "r", "tcl", "elixir", "nim"})
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")


def _is_filler(line: str, lang: str) -> bool:
    """Blank, a comment, or a line that ends a previous construct."""
    s = line.strip()
    if not s or _ENDS_CONSTRUCT.search(s):
        return True
    if s.startswith(("//", "/*", "*")):
        return True
    return lang in _HASH_COMMENT_LANGS and s.startswith("#")


def misanchored(lines: list[str], start_line: int, name: str, lang: str) -> Optional[bool]:
    """True/False for a unit at 1-based `start_line`; None when it cannot be judged
    (the line is out of range or the name never appears in the window)."""
    if not (1 <= start_line <= len(lines)):
        return None
    pat = re.compile(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])")
    if pat.search(lines[start_line - 1]):
        return False
    decl = next((j for j in range(start_line, min(len(lines), start_line + WINDOW)) if pat.search(lines[j])), None)
    if decl is None:
        return None
    return all(_is_filler(x, lang) for x in lines[start_line - 1 : decl])


def engine_units(crucible: Path) -> list[tuple[str, str, str, int]]:
    """(language, path relative to data/, name, start_line) from one in-process scan."""
    sys.path.insert(0, str(REPO_ROOT))
    os.environ["GITGALAXY_DISABLE_GIT_HISTORY"] = "1"
    import gitgalaxy
    from gitgalaxy.galaxyscope import main as galaxyscope_main

    if Path(gitgalaxy.__file__).resolve().parents[1] != REPO_ROOT:
        raise SystemExit(f"engine import resolved to {gitgalaxy.__file__}, not {REPO_ROOT} -- set PYTHONPATH")
    with tempfile.TemporaryDirectory() as tmp:
        argv = sys.argv
        sys.argv = ["galaxyscope", str(crucible / "data"), "--output", f"{tmp}/c.json", "--db-only"]
        try:
            galaxyscope_main()
        finally:
            sys.argv = argv
        (db,) = Path(tmp).glob("*_master.db")
        conn = sqlite3.connect(db)
        try:
            rows = conn.execute(
                "SELECT fd.language, fd.file_path, fn.func_name, fn.start_line "
                "FROM function_data fn JOIN file_data fd ON fd.id = fn.file_id"
            ).fetchall()
        finally:
            conn.close()
    return [(str(lang or "").lower(), path, name or "", int(line or 0)) for lang, path, name, line in rows]


def measure(crucible: Path, samples: int = 0) -> dict[str, dict[str, Any]]:
    per: dict[str, dict[str, Any]] = collections.defaultdict(lambda: {"units": 0, "misanchored": 0, "examples": []})
    cache: dict[str, Optional[list[str]]] = {}
    for lang, path, name, line in engine_units(crucible):
        if not _IDENT.fullmatch(name):
            continue  # synthetic buckets and anonymous units have no declaration to find
        if path not in cache:
            try:
                cache[path] = (crucible / "data" / path).read_text(encoding="utf-8", errors="replace").split("\n")
            except OSError:
                cache[path] = None
        lines = cache[path]
        verdict = misanchored(lines, line, name, lang) if lines is not None else None
        if verdict is None:
            continue
        r = per[lang]
        r["units"] += 1
        if verdict:
            r["misanchored"] += 1
            if len(r["examples"]) < samples:
                r["examples"].append(f"{path}:{line} {name} -- {lines[line - 1].strip()[:50]!r}")
    return {
        lang: {
            "units": r["units"],
            "misanchored": r["misanchored"],
            "misanchored_pct": round(100 * r["misanchored"] / r["units"], 1),
            "examples": r["examples"],
        }
        for lang, r in sorted(per.items())
        if r["units"]
    }


def render(results: dict[str, dict[str, Any]]) -> str:
    lines = ["| language | units | mis-anchored | rate |", "|---|---|---|---|"]
    for lang, r in sorted(results.items(), key=lambda kv: (-kv[1]["misanchored_pct"], kv[0])):
        lines.append(f"| {lang} | {r['units']} | {r['misanchored']} | {r['misanchored_pct']}% |")
    return "\n".join(lines)


def regressions(results: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for lang, base in baseline.items():
        if base.get("units", 0) < MIN_GATED_UNITS:
            continue
        cur = results.get(lang)
        if cur is None:
            out.append(f"{lang}: no longer measured (baseline had {base['units']} units)")
        elif cur["misanchored_pct"] > base["misanchored_pct"] + TOLERANCE_PP:
            out.append(f"{lang}: misanchored_pct {base['misanchored_pct']} -> {cur['misanchored_pct']}")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=int, default=0, help="print N mis-anchored examples per language")
    ap.add_argument("--ci", action="store_true", help="fail on a rise beyond the baseline tolerance")
    ap.add_argument("--regenerate", action="store_true", help="rewrite the committed baseline")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--summary", metavar="PATH", help="append the markdown table here (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args(argv)
    if not (CRUCIBLE / "data").is_dir():
        print(f"span_anchor_audit: no crucible at {CRUCIBLE} (set LANGUAGE_CRUCIBLE_PATH)")
        return 2
    results = measure(CRUCIBLE, a.samples)
    table = render(results)
    print(table)
    if a.samples:
        for lang, r in results.items():
            if r["examples"]:
                print(f"\n{lang}\n  " + "\n  ".join(r["examples"]))
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write("### Span anchoring (functions whose start_line opens before the declaration)\n\n")
            fh.write(table + "\n\n")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2) + "\n")
    # #2682: an audit that measured nothing must not pass.
    if not results:
        print("span_anchor_audit: FAIL -- measured 0 languages (scan or corpus problem)")
        return 1
    stripped = {k: {m: v for m, v in r.items() if m != "examples"} for k, r in results.items()}
    if a.regenerate:
        BASELINE.write_text(json.dumps(stripped, indent=2, sort_keys=True) + "\n")
        print(f"span_anchor_audit: baseline rewritten -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0
    if a.ci:
        if not BASELINE.exists():
            print("span_anchor_audit: no baseline; run --regenerate")
            return 1
        bad = regressions(stripped, json.loads(BASELINE.read_text()))
        if bad:
            print("span_anchor_audit: REGRESSION\n  " + "\n  ".join(bad))
            return 1
        print(f"span_anchor_audit: OK -- {len(results)} language(s) measured, none rose beyond tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
