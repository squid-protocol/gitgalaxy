#!/usr/bin/env python3
"""The per-test coverage map behind engine-module selection in the Smoke suite (#6278 item 5).

    pytest tests/ --cov=gitgalaxy --cov-context=test        # a full instrumented run (nightly), writes .coverage
    python tests/tools/coverage_map.py build --data .coverage --out .engine_test_map.json
    python tests/tools/coverage_map.py select gitgalaxy/core/prism.py [--map .engine_test_map.json]

`build` reads coverage.py's SQLite data (stdlib sqlite3, no coverage import) and records, for each `gitgalaxy/**.py`
file, the test files whose own tests executed one of its lines, plus `always`: the test files that read the engine tree
(a glob over it), which no execution trace can attribute to one module.

`select` is conservative; it returns None (the caller runs the full suite) when:
* the map is missing, or a changed file is not a `gitgalaxy/**.py` module the map holds (a data file, a new module);
* the module has no per-test line (only import-time lines run, as in a registry of constants: the run's empty context);
* more than MAX_SHARE of the known tests cover it (a spine module: `core`, `standards`);
* the map is older than MAX_AGE_DAYS, or carries no `built_at` stamp (a missed run of the nightly must not leave a
  weeks-old map choosing tests for today's engine: the stamp is read from the file, the cache's own age is not visible).
Otherwise it returns the covering tests plus `always`. The map is a nightly artifact: a test added since is run only
when the PR changes it, and the full run stays nightly + post-merge as the net. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP = REPO_ROOT / ".engine_test_map.json"  # ignored by the repo-wide *.json rule: a nightly artifact
MAX_SHARE = 0.4
MAX_AGE_DAYS = 3  # the nightly runs daily: two missed nights still select, a longer gap runs the full suite
VERSION = 1
_TREE_READ = re.compile(r"\b(?:rglob|os\.walk|glob|iterdir)\b")
_ENGINE_NAME = re.compile(r"""["']gitgalaxy["']|["']gitgalaxy/|\bGITGALAXY_DIR\b|\bPACKAGE_ROOT\b|\bENGINE_ROOT\b""")


def _rel(path: str, root: Path) -> str:
    p = Path(path)
    try:
        return (p.relative_to(root) if p.is_absolute() else p).as_posix()
    except ValueError:
        return p.as_posix()


def test_file_of(context: str) -> str | None:
    """`tests/a/test_x.py::test_y|run` -> `tests/a/test_x.py`; the empty (collection / import) context -> None."""
    head = context.split("|", 1)[0].split("::", 1)[0]
    return head if head.startswith("tests/") and head.endswith(".py") else None


def engine_tree_readers(root: Path = REPO_ROOT) -> list[str]:
    """Test files that glob or walk the engine tree: they read every module, so any engine change can trip them."""
    out = []
    for t in sorted((root / "tests").rglob("test_*.py")):
        text = change_classifier._text(t)
        if _TREE_READ.search(text) and _ENGINE_NAME.search(text):
            out.append(t.relative_to(root).as_posix())
    return out


def build(data: Path, root: Path = REPO_ROOT) -> dict:
    con = sqlite3.connect(f"file:{data}?mode=ro", uri=True)
    try:
        files = dict(con.execute("select id, path from file"))
        ctxs = dict(con.execute("select id, context from context"))
        names = {r[0] for r in con.execute("select name from sqlite_master")}
        pairs: set[tuple[int, int]] = set()
        for table in ("line_bits", "arc"):
            if table in names:
                pairs.update(con.execute(f"select distinct file_id, context_id from {table}"))  # noqa: S608
    finally:
        con.close()
    modules: dict[str, set[str]] = {}
    for fid, cid in pairs:
        rel = _rel(files[fid], root)
        if not (rel.startswith("gitgalaxy/") and rel.endswith(".py")):
            continue
        modules.setdefault(rel, set())
        if (t := test_file_of(ctxs.get(cid, ""))) is not None:
            modules[rel].add(t)
    known = sorted({t for ts in modules.values() for t in ts})
    return {
        "version": VERSION,
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "tests": len(known),
        "always": engine_tree_readers(root),
        "modules": {m: sorted(ts) for m, ts in sorted(modules.items())},
    }


def load(path: Path | None = None) -> dict | None:
    p = DEFAULT_MAP if path is None else path
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return m if isinstance(m, dict) and m.get("version") == VERSION else None


def map_age_problem(cmap: dict, now: dt.datetime | None = None) -> str | None:
    """Why the map is too old to trust (no readable `built_at`, a future stamp, older than MAX_AGE_DAYS), else None."""
    try:
        built = dt.datetime.fromisoformat(str(cmap.get("built_at")))
    except ValueError:
        return "the coverage map has no readable built_at stamp"
    if built.tzinfo is None:
        built = built.replace(tzinfo=dt.timezone.utc)
    age = (now or dt.datetime.now(dt.timezone.utc)) - built
    if age < dt.timedelta(0):
        return "the coverage map is stamped in the future"
    if age > dt.timedelta(days=MAX_AGE_DAYS):
        return f"the coverage map is {age.days} days old (limit {MAX_AGE_DAYS})"
    return None


def select(
    files: list[str], cmap: dict | None, root: Path = REPO_ROOT, now: dt.datetime | None = None
) -> tuple[list[str] | None, str]:
    """(tests, reason): the test files that cover every changed engine module, or (None, why) when the suite runs in full."""
    if not cmap:
        return None, "no coverage map"
    if (why := map_age_problem(cmap, now)) is not None:
        return None, why
    modules, total = cmap.get("modules", {}), int(cmap.get("tests", 0))
    tests: set[str] = set(cmap.get("always", []))
    for f in files:
        covering = modules.get(f)
        if covering is None:
            return None, f"{f} is not a module in the coverage map"
        if not covering:
            return None, f"{f} has no per-test coverage (import-time lines only)"
        if total and len(covering) > MAX_SHARE * total:
            return None, f"{f} is covered by {len(covering)} of {total} test files"
        tests.update(covering)
    return sorted(t for t in tests if (root / t).exists()), "coverage map"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--data", type=Path, default=REPO_ROOT / ".coverage")
    b.add_argument("--out", type=Path, default=DEFAULT_MAP)
    s = sub.add_parser("select")
    s.add_argument("files", nargs="+")
    s.add_argument("--map", type=Path, default=None)
    args = ap.parse_args()
    if args.cmd == "build":
        m = build(args.data)
        args.out.write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
        print(f"{len(m['modules'])} modules, {m['tests']} test files, {len(m['always'])} tree readers -> {args.out}")
        return 0
    tests, why = select(args.files, load(args.map))
    print(json.dumps({"tests": tests, "reason": why}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
