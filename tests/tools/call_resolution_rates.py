"""
Call-resolution rates across language-crucible (#3331, Epic #3265 step 4).

Scans the whole crucible once with THIS checkout's engine (in process, so the
galaxyscope console-script trap cannot swap in another checkout's code), reads the
per-language `fcall_rate_data` rows the scan recorded, and prints the share of
(caller, callee) pairs the call resolver linked as scoped / unique / ambiguous /
external.

    python tests/tools/call_resolution_rates.py                 # print the table
    python tests/tools/call_resolution_rates.py --history       # + append a batch to the CSV
    python tests/tools/call_resolution_rates.py --json out.json # + machine-readable rows

`--history` appends one row per language to docs/self_scan/call_resolution_history.csv
-- a time series, like tree_sitter_accuracy_history.csv -- so a change to a language's
calls_out rule or to the resolver shows up as a measured movement. A batch identical
to the last recorded one is not appended.

The caveat travels with the numbers: a high scoped/unique share means the resolver
made a confident choice, not that the choice was correct. Correctness is #3332.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRUCIBLE = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))
HISTORY = REPO_ROOT / "docs" / "self_scan" / "call_resolution_history.csv"
CLASSES = ("scoped", "unique", "ambiguous", "external")
FIELDS = ["timestamp_utc", "commit_sha", "crucible", "language", "total", *CLASSES, "confident_pct", "external_pct"]


def _git(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def measure(crucible: Path) -> list[dict]:
    """One in-process scan of `crucible/data`; returns the fcall_rate_data rows."""
    sys.path.insert(0, str(REPO_ROOT))
    import gitgalaxy
    from gitgalaxy.galaxyscope import main as galaxyscope_main

    if Path(gitgalaxy.__file__).resolve().parents[1] != REPO_ROOT:
        raise SystemExit(f"engine import resolved to {gitgalaxy.__file__}, not {REPO_ROOT} -- set PYTHONPATH")
    with tempfile.TemporaryDirectory() as out:
        argv = sys.argv
        sys.argv = ["galaxyscope", str(crucible / "data"), "--output", f"{out}/crucible.json", "--db-only"]
        try:
            galaxyscope_main()
        finally:
            sys.argv = argv
        (db,) = Path(out).glob("*_master.db")
        conn = sqlite3.connect(db)
        try:
            cur = conn.execute(
                'SELECT language, total, scoped, "unique", ambiguous, external FROM fcall_rate_data ORDER BY language'
            )
            rows = [dict(zip(["language", "total", *CLASSES], r)) for r in cur]
        finally:
            conn.close()
    for r in rows:
        t = r["total"] or 1
        r["confident_pct"] = round(100.0 * (r["scoped"] + r["unique"]) / t, 1)
        r["external_pct"] = round(100.0 * r["external"] / t, 1)
    return rows


def _last_batch() -> list[dict]:
    if not HISTORY.exists():
        return []
    with HISTORY.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return []
    stamp = rows[-1]["timestamp_utc"]
    return [r for r in rows if r["timestamp_utc"] == stamp]


def _same_as_last(rows: list[dict]) -> bool:
    def key(rs):
        return sorted((r["language"], *(int(r[c]) for c in ("total", *CLASSES))) for r in rs)

    last = _last_batch()
    return bool(last) and key(last) == key(rows)


def append_history(rows: list[dict], crucible: Path) -> bool:
    if _same_as_last(rows):
        print("call_resolution_rates: unchanged since the last recorded batch -- nothing appended.")
        return False
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    sha = _git(["rev-parse", "HEAD"], REPO_ROOT)
    version = _git(["describe", "--tags", "--always"], crucible)
    new = not HISTORY.exists()
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({"timestamp_utc": stamp, "commit_sha": sha, "crucible": version, **r})
    print(f"call_resolution_rates: appended {len(rows)} rows to {HISTORY.relative_to(REPO_ROOT)}")
    return True


def render(rows: list[dict]) -> str:
    lines = [
        "| language | pairs | scoped | unique | ambiguous | external | confident |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r["language"] != "*", -r["total"])):
        t = r["total"] or 1
        cells = " | ".join(f"{100.0 * r[c] / t:.1f}%" for c in CLASSES)
        lines.append(f"| {r['language']} | {r['total']} | {cells} | {r['confident_pct']}% |")
    lines.append("")
    lines.append("Confident = scoped + unique: the resolver chose, which is not the same as chose right (#3332).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history", action="store_true", help="append the batch to the history CSV")
    ap.add_argument("--json", metavar="PATH", help="also write the rows as JSON")
    args = ap.parse_args(argv)
    if not (CRUCIBLE / "data").is_dir():
        print(f"call_resolution_rates: no crucible at {CRUCIBLE} (set LANGUAGE_CRUCIBLE_PATH)")
        return 2
    rows = measure(CRUCIBLE)
    print(render(rows))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2) + "\n")
    if args.history:
        append_history(rows, CRUCIBLE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
