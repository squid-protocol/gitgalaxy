#!/usr/bin/env python3
"""Score every oracle language on the PINNED language-crucible and record the cells (#8863).

    python tests/tools/family_oracle_sweep.py                    # scan <crucible>/data, score every language, print matched counts
    python tests/tools/family_oracle_sweep.py --write            # ... and merge the cells into tests/family_validity_baseline.json
    python tests/tools/family_oracle_sweep.py --db DB            # reuse a finished scan of <crucible>/data

A grid cell is hatched when its corpus is not a pinned crucible, and faded when the corpus gave it under 10 functions. The first scan
of the crucible that fed the baseline was taken from the checkout root and kept 1,092 of 3,658 files (data/c, data/csharp and data/swift
nearly absent), so C had 28 matchable functions, JavaScript 4 and C# / Swift none. The golden masters scan `<crucible>/data` with
`--file-speed --splicing-speed` (tests/tools/update_golden_master.py); this tool scans it the same way, so the cell's corpus is the
corpus the rest of the gates measure, and labels it with the pin in tests/crucible_pins.toml.

Run it under `tests/tools/box/heavy-run.sh` (the scan is heavy) with the checkout at the pin (`crucible_pins.py sync`).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))  # before any gitgalaxy import: a shared venv may be installed from another checkout
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(HERE))
import _crucible_pin  # noqa: E402
import family_oracle as fo  # noqa: E402
import family_oracle_ts  # noqa: E402


def corpus_label() -> str:
    """The name every pinned cell carries: `language-crucible <pinned tag>`."""
    return f"language-crucible {_crucible_pin.PINNED_TAG}"


ALIASES = {
    "bash"
}  # an oracle spec registered under a second name for the same source files; the grid column is `shell`


def languages() -> list[str]:
    return ["python", "cobol", "hlasm", *(lang for lang in family_oracle_ts.languages() if lang not in ALIASES)]


def crucible_data(env: dict[str, str] | None = None) -> Path:
    """`<crucible>/data` from LANGUAGE_CRUCIBLE_PATH, else the checkout beside the primary one; refuses a checkout off the pin."""
    env = os.environ if env is None else env
    root = Path(env.get(_crucible_pin.PATH_ENV) or REPO.parent / "language-crucible")
    data = root / "data"
    if not data.is_dir():
        raise SystemExit(f"{data} not found: set {_crucible_pin.PATH_ENV} to a language-crucible checkout")
    problem = _crucible_pin.pin_mismatch(root)
    if problem:
        raise SystemExit(problem)
    return data


def scan_command(data: Path, out_dir: Path) -> list[str]:
    """The golden masters' scan (update_golden_master.py), writing only the SQLite database."""
    return [
        "galaxyscope",
        str(data),
        "--db-only",
        "--file-speed",
        "--splicing-speed",
        "--output",
        str(out_dir) + os.sep,
    ]


def scan(data: Path, out_dir: Path) -> Path:
    env = {**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER", "GITGALAXY_DISABLE_GIT_HISTORY": "1"}
    subprocess.run(scan_command(data, out_dir), check=True, env=env)
    dbs = sorted(out_dir.glob("*_master.db"))
    if not dbs:
        raise SystemExit(f"galaxyscope wrote no *_master.db under {out_dir}")
    return dbs[0]


def sweep(db: Path, data: Path, baseline: Path | None) -> dict[str, dict]:
    """Score each language; with `baseline`, merge its cells as pinned cells of the current pin. Returns {language: score result}."""
    label = corpus_label()
    results = {}
    for lang in languages():
        result = fo.score(db, data, lang)
        results[lang] = result
        note = ""
        if baseline is not None:
            note = f", {fo.update_baseline(baseline, result, label, pinned=True)} cells written"
        print(f"{lang:12s} {result['matched']:6d} matched, {result['unmatched']:5d} unmatched{note}")
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", help="a finished scan of <crucible>/data (default: scan it now)")
    ap.add_argument("--write", action="store_true", help="merge the cells into the family-validity baseline")
    args = ap.parse_args(argv)
    data = crucible_data()
    if args.db:
        db = Path(args.db)
    else:
        out = Path(tempfile.mkdtemp(prefix="family-sweep-"))
        db = scan(data, out)
    sweep(db, data, fo.BASELINE if args.write else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
