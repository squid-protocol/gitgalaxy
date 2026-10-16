#!/usr/bin/env python3
"""#5117: the era distribution of estates that have no committed per-program inventory -- COUNTS ONLY.

    python tests/tools/era_distribution.py --write [--census DIR] [--root LABEL=DIR ...]
    python tests/tools/era_distribution.py --print --census DIR

The burned estates commit a per-program inventory (tests/fixtures/feature_inventory/). A non-burned estate keeps its
first-contact numbers (.claude/rules/mainframe-evidence-policy.md sections 2-3), so nothing per program is committed for
it: not a program name, a tell list, a line number or a source line. Each estate is scanned by `feature_inventory.
scan_estate` (the same tagger and copybook pass as the burned ones) and only `summarise`'s aggregate is kept: programs
per era, none, mixed, programs per tell, programs a copybook raised. Census clones get an opaque label (`census-` plus
a hash of the name) and never their repo name; a burned estate is refused. The result is
tests/fixtures/era_distribution/summary.json, which `support_matrix` renders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

SUMMARY_FILE = REPO / "tests" / "fixtures" / "era_distribution" / "summary.json"
PINNED_NON_BURNED = ("dsf", "zopeneditor-sample")
KEYS = (
    "programs",
    "by_era",
    "mixed",
    "tells",
    "raised_by_copybook",
    "copybook_skipped",
)  # the only keys a summary may carry
ABOUT = (
    "Counts only (#5117). Estates here are not burned: no per-program data is committed, so their first-contact "
    "numbers stay first-contact. `census-*` labels are opaque."
)


def census_label(name: str) -> str:
    return "census-" + hashlib.sha256(name.encode()).hexdigest()[:6]


def counts_only(summary: dict[str, Any]) -> dict[str, Any]:
    """`summarise`'s aggregate with nothing but the allowed keys (tell names are the engine's own vocabulary)."""
    return {k: summary[k] for k in KEYS if k in summary}


def distribution(estate_dir: Path, db_dir: Path) -> dict[str, Any]:
    from tests.tools.feature_inventory import scan_estate

    return counts_only(scan_estate(estate_dir, db_dir)["eras"]["summary"])


def burned_names() -> set[str]:
    from tests.tools.estate4_draw import BURNED_NAMES

    return set(BURNED_NAMES)


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or SUMMARY_FILE
    if not path.is_file():
        return {"about": ABOUT, "estates": {}}
    return json.loads(path.read_text())


def collect(roots: dict[str, Path], census: Path | None, corpora: Path) -> dict[str, dict[str, Any]]:
    """label -> {kind, ...counts}. `roots` are labelled estates (pinned, non-burned); `census` a directory of clones."""
    burned = burned_names()
    todo: dict[str, tuple[str, Path]] = {}
    for label, d in roots.items():
        if label.lower() in burned:
            raise SystemExit(f"{label} is a burned estate: its inventory is committed under feature_inventory/")
        todo[label] = ("pinned", d)
    for name in PINNED_NON_BURNED:
        if name not in todo and (corpora / name).is_dir():
            todo[name] = ("pinned", corpora / name)
    if census and census.is_dir():
        for d in sorted(p for p in census.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
            if d.name.lower() in burned:
                continue
            todo[census_label(d.name)] = ("census", d)
    out: dict[str, dict[str, Any]] = {}
    for label, (kind, d) in sorted(todo.items()):
        db_dir = Path(tempfile.mkdtemp(prefix="era-distribution-"))  # fresh scans, never a shared path
        out[label] = {"kind": kind, **distribution(d, db_dir)}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="merge into tests/fixtures/era_distribution/summary.json")
    ap.add_argument("--print", action="store_true", dest="show", help="print, write nothing")
    ap.add_argument(
        "--census", type=Path, help="a directory of non-burned census clones (default: $CICS_CENSUS_CORPORA)"
    )
    ap.add_argument(
        "--root", action="append", default=[], metavar="LABEL=DIR", help="one more labelled non-burned estate"
    )
    args = ap.parse_args(argv)
    if not (args.write or args.show):
        ap.print_help()
        return 2
    census = args.census or (Path(os.environ["CICS_CENSUS_CORPORA"]) if os.environ.get("CICS_CENSUS_CORPORA") else None)
    roots = {}
    for r in args.root:
        label, _, d = r.partition("=")
        roots[label] = Path(d)
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora"))
    got = collect(roots, census, corpora)
    if args.write:
        data = load()
        data["about"] = ABOUT
        data["estates"] = {**data["estates"], **got}
        data["estates"] = dict(sorted(data["estates"].items()))
        SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY_FILE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print(f"Wrote {SUMMARY_FILE} ({len(got)} estates)", file=sys.stderr)
    else:
        print(json.dumps(got, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
