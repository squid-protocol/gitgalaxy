#!/usr/bin/env python3
"""#6733: run the test files this branch can break -- the importers of what it changed, not just its own tests.

    python tests/tools/affected_tests.py                 # run them (nearest importers first, within --budget seconds)
    python tests/tools/affected_tests.py --list          # print the selection and its distances, run nothing
    python tests/tools/affected_tests.py --budget 600 --base origin/main
    python tests/tools/pr_gates.py --only affected

Churn fix runs 2026-10-18..26: a PR breaking OTHER existing tests (another language's audit, a planner's test, a dependent
case's evidence) went from 1.2 per 100 PRs at 1-2 hand-written files to 17.7 at 5, while a PR's own tests failing in
CI stayed flat (2-5): workers test what they wrote, and CI found the rest one push later.

The selection: every test file whose imports reach a changed .py file (an `ast` scan of tests/ and gitgalaxy/:
`gitgalaxy.*` imports, the bare imports of tests/tools/ modules and per-directory harnesses, and string constants that
name a .py file, as a test that runs a tool by subprocess does), plus the test files that read a changed docs / Markdown
file (change_classifier's docs_read_by_tests.txt), the .py files that name any other changed file (a workflow, a case's
data, a runtime's Java / C source: its file name when unique, else its directory's name, e.g. the case) and, for a
changed conftest.py, the test files under it. Distance 0 is
a test file the branch changed, 1 a direct importer, and so on. The scan over-approximates (a name in a string counts),
so it can run a test it need not, never skip one an import reaches.

Budget: test files are taken nearest first, then cheapest (.test_durations), until --budget seconds; the rest are named
and left to CI, never skipped silently. Golden masters and corpora stay CI's (pr_gates' golden gate, ground truth).
"""

from __future__ import annotations

import argparse
import ast
import functools
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from gitgalaxy.core.source_text import read_source  # noqa: E402 -- #3813: no lossy decode

SCAN_ROOTS = ("tests", "gitgalaxy")
DURATIONS = REPO / ".test_durations"
UNKNOWN_SECONDS = 2.0  # a test file .test_durations has never timed (a new one)


def _git(*args: str, root: Path = REPO) -> list[str]:
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False).stdout  # noqa: S603, S607
    return [line for line in out.splitlines() if line.strip()]


def changed_files(base: str = "origin/main", root: Path = REPO) -> list[str]:
    """The branch's changes against its merge base with `base`, committed or not, plus untracked files."""
    mb = _git("merge-base", base, "HEAD", root=root)
    tracked = _git("diff", "--name-only", mb[0] if mb else base, root=root)
    return sorted(set(tracked) | set(_git("ls-files", "--others", "--exclude-standard", root=root)))


def py_files(root: Path = REPO) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for top in SCAN_ROOTS for p in (root / top).rglob("*.py")
                  if "__pycache__" not in p.parts)  # fmt: skip


def is_test(rel: str) -> bool:
    return rel.startswith("tests/") and Path(rel).name.startswith("test_")


class Resolver:
    """Import name -> repo file, the way the tests' sys.path makes it resolve."""

    def __init__(self, files: list[str]):
        self.files = set(files)
        self.by_stem: dict[str, list[str]] = defaultdict(list)
        for f in files:
            if f.startswith("tests/"):
                self.by_stem[Path(f).stem].append(f)

    def dotted(self, name: str) -> str | None:
        base = name.replace(".", "/")
        for cand in (f"{base}.py", f"{base}/__init__.py"):
            if cand in self.files:
                return cand
        return None

    def bare(self, name: str, importer: str) -> str | None:
        """`import x` from a test or tool: its own directory or an ancestor up to tests/, then tests/tools/, then the one
        file of that name anywhere under tests/."""
        if "." in name:
            return None
        d = Path(importer).parent
        while d.as_posix().startswith("tests"):
            if (cand := f"{d.as_posix()}/{name}.py") in self.files:
                return cand
            d = d.parent
        if (cand := f"tests/tools/{name}.py") in self.files:
            return cand
        hits = self.by_stem.get(name, [])
        return hits[0] if len(hits) == 1 else None

    def module(self, name: str, importer: str) -> str | None:
        return self.dotted(name) if name.split(".")[0] == "gitgalaxy" else self.bare(name.split(".")[0], importer)

    def string(self, text: str) -> str | None:
        """A string constant naming a .py file: a repo path, or a tests/tools/ tool by its file name."""
        text = text.strip().lstrip("./")
        if not text.endswith(".py") or " " in text or len(text) > 200:
            return None
        if text in self.files:
            return text
        name = text.rsplit("/", 1)[-1]
        return f"tests/tools/{name}" if f"tests/tools/{name}" in self.files else None


def imports_of(rel: str, src: str, res: Resolver) -> set[str]:
    """The repo files one .py file imports or names."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return set()
    out: set[str | None] = set()
    pkg = rel.rsplit("/", 1)[0].replace("/", ".") if rel.startswith("gitgalaxy/") else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {res.module(a.name, rel) for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: only inside the gitgalaxy package
                parts = pkg.split(".")[: len(pkg.split(".")) - node.level + 1] if pkg else []
                base = ".".join(parts + ([node.module] if node.module else []))
                if not base:
                    continue
                mod = base
            else:
                mod = node.module or ""
            if mod.split(".")[0] == "gitgalaxy" or node.level:
                subs = {res.dotted(f"{mod}.{a.name}") for a in node.names}
                out |= subs if any(subs) else {res.dotted(mod)}
            else:
                out.add(res.bare(mod.split(".")[0], rel))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(res.string(node.value))
    out.discard(None)
    out.discard(rel)
    return {x for x in out if x}


def graph(root: Path = REPO) -> dict[str, set[str]]:
    """file -> the repo files it imports or names."""
    files = py_files(root)
    res = Resolver(files)
    return {f: imports_of(f, read_source(root / f).text, res) for f in files}


def importers(g: dict[str, set[str]]) -> dict[str, set[str]]:
    rev: dict[str, set[str]] = defaultdict(set)
    for f, deps in g.items():
        for d in deps:
            rev[d].add(f)
    return rev


@functools.lru_cache(maxsize=1)
def _doc_readers() -> dict[str, list[str]]:
    sys.path.insert(0, str(REPO / "tests" / "tools"))
    import change_classifier as cc  # noqa: PLC0415

    return cc.load()


def doc_readers(path: str, files: set[str]) -> set[str]:
    """The .py files that read a changed docs / Markdown file (a reader scope naming one file)."""
    try:
        sys.path.insert(0, str(REPO / "tests" / "tools"))
        import change_classifier as cc  # noqa: PLC0415

        scopes = cc.readers_of(path, _doc_readers())
    except Exception:  # the list is a hint: a broken one must not break the gate
        return set()
    return {s for s in scopes if s in files}


GENERIC_DIRS = {
    "tests",
    "tools",
    "docs",
    "workflows",
    "fixtures",
    "languages",
    "standards",
    "gitgalaxy",
    "core",
    "data",
}


def name_keys(path: str, files: Counter, dirs: Counter) -> list[str]:
    """What a reader of a non-.py file writes to name it: its file name when no other file has it (det-sweep.yml), else
    its directory's name when no other directory has it (a case's case.json / seed.sql: tests/equivalence/<case>/)."""
    p = Path(path)
    if files[p.name] <= 1 and len(p.stem) > 3:
        return [p.name]
    parent = p.parent.name
    return [parent] if len(parent) > 5 and dirs[parent] <= 1 and parent not in GENERIC_DIRS else []


def name_readers(changed: list[str], root: Path = REPO) -> dict[str, set[str]]:
    """{changed non-.py file: the .py files whose text names it} -- a test that reads a workflow, a case's data or a
    runtime source by its name. One `git grep` per key."""
    tracked = _git("ls-files", root=root)
    files = Counter(Path(f).name for f in tracked)
    dirs = Counter(Path(d).name for d in {Path(f).parent.as_posix() for f in tracked})
    out: dict[str, set[str]] = {}
    for c in changed:
        if c.endswith(".py"):
            continue
        out[c] = {f for key in name_keys(c, files, dirs)
                  for f in _git("grep", "-l", "-F", key, "--", "*.py", root=root)}  # fmt: skip
    return out


def affected(changed: list[str], g: dict[str, set[str]], readers: dict[str, set[str]] | None = None) -> dict[str, int]:
    """{test file: distance} for every test file that reaches a changed file (breadth first over importers)."""
    rev, files = importers(g), set(g)
    readers = name_readers(changed) if readers is None else readers
    dist: dict[str, int] = {}
    frontier: list[str] = []
    for c in changed:
        if c in files:
            dist[c] = 0
            frontier.append(c)
            continue
        found = set(readers.get(c, ())) | doc_readers(c, files)  # the docs-readers list answers for any path
        for r in found & files - dist.keys():
            dist[r] = 1
            frontier.append(r)
    for c in changed:  # a conftest.py configures every test under its directory
        if Path(c).name == "conftest.py" and c in files:
            under = Path(c).parent.as_posix() + "/"
            for t in files:
                if is_test(t) and t.startswith(under) and t not in dist:
                    dist[t] = 1
    while frontier:
        nxt = []
        for f in frontier:
            for imp in rev.get(f, ()):
                if imp not in dist:
                    dist[imp] = dist[f] + 1
                    nxt.append(imp)
        frontier = nxt
    return {f: d for f, d in dist.items() if is_test(f)}


def file_seconds(path: Path = DURATIONS) -> dict[str, float]:
    try:
        per_test = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, float] = defaultdict(float)
    for nodeid, s in per_test.items():
        out[nodeid.split("::", 1)[0]] += float(s)
    return out


def select(hits: dict[str, int], seconds: dict[str, float], budget: float) -> tuple[list[str], list[str], float]:
    """(run, left to CI, estimated seconds of run): nearest first, then cheapest, while the budget lasts."""
    order = sorted(hits, key=lambda f: (hits[f], seconds.get(f, UNKNOWN_SECONDS), f))
    run, left, total = [], [], 0.0
    for f in order:
        s = seconds.get(f, UNKNOWN_SECONDS)
        if total + s <= budget or not run:
            run.append(f)
            total += s
        else:
            left.append(f)
    return run, left, total


def pytest_command(has_pytest: bool | None = None, which=shutil.which) -> tuple[list[str], dict[str, str] | None]:
    """How to run pytest. This interpreter when it has pytest; else the `pytest` on PATH, with this checkout first on
    PYTHONPATH so a shared venv's editable install of another checkout is not what runs. Churn's precheck runs
    pr_gates under /usr/bin/python3, which has no pytest: `-m pytest` failed the gate in 6 s on every branch whose
    change reached a test (PR #6799), the same trap pr_gates' `_tool_bin_dir` closes for ruff."""
    if has_pytest is None:
        has_pytest = importlib.util.find_spec("pytest") is not None
    found = None if has_pytest else which("pytest")
    if not found:
        return [sys.executable, "-m", "pytest"], None
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(REPO), env.get("PYTHONPATH", "")) if p)
    return [found], env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main", help="what the branch is compared with (its merge base)")
    ap.add_argument("--budget", type=float, default=300.0, help="seconds of tests to run, by .test_durations")
    ap.add_argument("--list", action="store_true", help="print the selection, run nothing")
    args = ap.parse_args(argv)
    changed = changed_files(args.base)
    hits = {f: d for f, d in affected(changed, graph()).items() if (REPO / f).exists()}  # a deleted test is not run
    if not hits:
        print(f"affected: no test file reaches the {len(changed)} changed file(s)")
        return 0
    run, left, est = select(hits, file_seconds(), args.budget)
    print(f"affected: {len(hits)} test file(s) reach the {len(changed)} changed file(s); running {len(run)} (~{est:.0f} s)"
          + (f", {len(left)} over the {args.budget:.0f} s budget left to CI" if left else ""))  # fmt: skip
    if args.list:
        for f in run:
            print(f"  run   d={hits[f]}  {f}")
        for f in left:
            print(f"  CI    d={hits[f]}  {f}")
        return 0
    if left:
        print("  left to CI: " + " ".join(left[:20]) + (" ..." if len(left) > 20 else ""))
    cmd, env = pytest_command()
    proc = subprocess.run([*cmd, "-q", "-p", "no:cacheprovider", *run], cwd=REPO, env=env, check=False)  # noqa: S603
    return 0 if proc.returncode == 5 else proc.returncode  # 5: every selected test deselected / skipped


if __name__ == "__main__":
    sys.exit(main())
