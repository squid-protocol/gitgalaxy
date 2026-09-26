"""
Compiler call-graph references: the adapter contract, the registry, the cache
(#3773, epic #3772).

A language's call graph is scored (tests/tools/call_graph_resolution.py) and
triaged (tests/tools/callgraph_triage.py) against a REFERENCE: a tool that
resolves calls with more information than GitGalaxy has -- pyan3 for Python,
the TypeScript compiler's type checker for TypeScript. Every reference produces
the same JSON (the contract), so adding a language is an adapter plus a
registry entry, never a scorer change:

    {"tool": "tsc", "version": "6.0.2", "files": 515,
     "defs":     [[path, name, line], ...],          # every named function with a body
     "edges":    [[caller_key, callee_key, line?]],  # key = [path, name, line]; line = the call site
     "external": [[caller_key, callee_name], ...]}   # optional: resolved ONLY outside the repo

Paths are repo-relative with forward slashes. A reference is a reference, not
ground truth (CLAUDE.md, "Comparative-correctness claims").

A reference graph depends only on the corpus repo's content, the tool and its
version, and the adapter's own code -- never on the engine -- so it is cached
(GITGALAXY_CALLGRAPH_CACHE, default ~/.cache/gitgalaxy/callgraph_refs). A
gate re-run after an engine change then costs only the engine scan.

    python tests/tools/callgraph_refs.py typescript <repo>    # print the contract JSON
    python tests/tools/callgraph_refs.py --list               # languages, tools, pins, installed versions
"""

from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CRUCIBLE = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))
CACHE_DIR = Path(os.environ.get("GITGALAXY_CALLGRAPH_CACHE", Path.home() / ".cache" / "gitgalaxy" / "callgraph_refs"))
# bump when the contract's shape changes, so no stale entry is ever read
CONTRACT_VERSION = 1


class RefGraph:
    """A reference's call graph for one repo, keyed (relpath, name, line).

    defs      (relpath, name) -> def lines
    edges     {(caller_key, callee_key)}
    by_name   (caller_key, callee_name) -> the callee keys the reference links it to
    external  {(caller_key, callee_name)}: calls the reference resolved ONLY outside
              the repo (a built-in or library method). pyan cannot say this; the
              TypeScript checker can, so an engine link there is provably wrong.
    sites     (caller_key, callee_key) -> call-site lines, when the adapter reports them
    """

    def __init__(self, defs, edges, by_name, external=frozenset(), sites=None) -> None:
        self.defs, self.edges, self.by_name, self.external = defs, edges, by_name, external
        self.sites: dict[tuple, list[int]] = sites or {}


def load_contract(raw: dict[str, Any]) -> RefGraph:
    """The contract JSON -> a RefGraph."""
    defs: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    edges: set[tuple] = set()
    by_name: dict[tuple, set[tuple]] = collections.defaultdict(set)
    sites: dict[tuple, list[int]] = collections.defaultdict(list)
    for p, n, line in raw["defs"]:
        defs[(p, n)].append(int(line))
    for edge in raw["edges"]:
        ks, kd = tuple(edge[0]), tuple(edge[1])
        edges.add((ks, kd))
        by_name[(ks, kd[1])].add(kd)
        if len(edge) > 2 and edge[2]:
            sites[(ks, kd)].append(int(edge[2]))
    external = {(tuple(src), name) for src, name in raw.get("external") or []}
    return RefGraph(defs, edges, by_name, external, dict(sites))


# ----------------------------------------------------------------------------- adapters


def _compiles(path: str) -> bool:
    """pyan aborts the whole run on one file Python itself cannot compile."""
    try:
        compile(Path(path).read_text(encoding="utf-8", errors="replace"), path, "exec")
    except (SyntaxError, ValueError):
        return False
    return True


def pyan_contract(repo: Path) -> dict[str, Any]:
    """pyan3 over every compilable .py file of `repo`, as the contract."""
    from pyan.analyzer import CallGraphVisitor

    files = [f for f in glob.glob(str(repo / "**" / "*.py"), recursive=True) if _compiles(f)]
    v = CallGraphVisitor(files, root=str(repo))

    def key(node):
        if (
            node.filename is None
            or node.ast_node is None
            or str(node.flavor) not in ("Flavor.FUNCTION", "Flavor.METHOD")
        ):
            return None
        rel = os.path.relpath(node.filename, repo).replace(os.sep, "/")
        return [rel, node.name, int(getattr(node.ast_node, "lineno", 0))]

    edges = []
    for src, dsts in v.uses_edges.items():
        ks = key(src)
        if ks is None:
            continue
        for dst in dsts:
            kd = key(dst)
            if kd is not None and kd != ks:
                edges.append([ks, kd])
    defs = [k for node_list in v.nodes.values() for node in node_list if (k := key(node))]
    return {"defs": sorted(defs), "edges": sorted(edges), "external": [], "files": len(files)}


def node_env() -> dict[str, str]:
    """NODE_PATH for ts_callgraph.js: the caller's, else the global npm root."""
    env = dict(os.environ)
    if not env.get("NODE_PATH"):
        try:
            root = subprocess.run(
                ["npm", "root", "-g"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            root = ""
        if root:
            env["NODE_PATH"] = root
    return env


def tsc_contract(repo: Path) -> dict[str, Any]:
    """The TypeScript checker's call graph of `repo` (tests/tools/ts_callgraph.js)."""
    try:
        proc = subprocess.run(  # noqa: S603 -- fixed argv, a corpus path
            ["node", str(TOOLS / "ts_callgraph.js"), str(repo)],  # noqa: S607
            capture_output=True,
            text=True,
            env=node_env(),
        )
    except OSError as exc:
        raise SystemExit(f"callgraph_refs: node is required for the typescript reference ({exc})") from exc
    if proc.returncode != 0:
        raise SystemExit(f"callgraph_refs: ts_callgraph.js failed on {repo}:\n{proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


def _pyan_version() -> str | None:
    try:
        return importlib.metadata.version("pyan3")
    except importlib.metadata.PackageNotFoundError:
        return None


def _tsc_version() -> str | None:
    probe = "const t=require('typescript');process.stdout.write(typeof t.createProgram==='function'?t.version:'')"
    try:
        out = subprocess.run(  # noqa: S603 -- fixed argv
            ["node", "-e", probe],  # noqa: S607
            capture_output=True,
            text=True,
            env=node_env(),
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


# ----------------------------------------------------------------------------- registry


@dataclass(frozen=True)
class Reference:
    lang: str
    tool: str
    version: str  # the pinned version the baseline was measured with
    corpus: str  # 'crucible' (language-crucible/data/<lang>) | 'import_graph' (tests/import_graph_corpus.json)
    build: Callable[[Path], dict[str, Any]]
    installed: Callable[[], str | None]
    adapter_files: tuple[Path, ...]  # hashed into the cache key: editing an adapter invalidates its cache
    reports_external: bool  # can say a call resolves only outside the repo
    install_hint: str


REFERENCES: dict[str, Reference] = {
    "python": Reference(
        "python",
        "pyan3",
        "2.8.1",
        "crucible",
        pyan_contract,
        _pyan_version,
        (Path(__file__),),
        False,
        'pip install "pyan3==2.8.1"',
    ),
    "typescript": Reference(
        "typescript",
        "tsc",
        "6.0.2",
        "import_graph",
        tsc_contract,
        _tsc_version,
        (Path(__file__), TOOLS / "ts_callgraph.js"),
        True,
        'npm install --global "typescript@6.0.2"  (7.x has no JavaScript compiler API)',
    ),
}
BY_TOOL = {r.tool: r for r in REFERENCES.values()}


def corpus_repos(lang: str) -> list[tuple[str, Path]]:
    """(name, path) of every corpus repo the language is scored on. Exits when a
    corpus is missing -- an audit that measured nothing must not pass (#2682)."""
    ref = REFERENCES[lang]
    if ref.corpus == "crucible":
        root = CRUCIBLE / "data" / lang
        if not root.is_dir():
            raise SystemExit(f"callgraph_refs: {root} not found -- clone language-crucible (LANGUAGE_CRUCIBLE_PATH)")
        return [(p.name, p) for p in sorted(root.iterdir()) if p.is_dir()]
    sys.path.insert(0, str(TOOLS))
    import import_graph_accuracy as iga

    entries = [e for e in iga.load_manifest() if e["language"] == lang]
    missing = [e["repo"] for e in entries if not (iga.repo_dir(iga.CORPUS, e) / ".git").is_dir()]
    if missing:
        raise SystemExit(f"callgraph_refs: not fetched: {missing} -- run import_graph_accuracy.py --fetch-only")
    return [(e["repo"], iga.repo_dir(iga.CORPUS, e)) for e in entries]


# ----------------------------------------------------------------------------- cache


def _git(cwd: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603 -- git with fixed subcommands
            ["git", "-C", str(cwd), *args],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def content_id(repo: Path) -> str:
    """The repo's content, as git names it: the tree object of `repo` at HEAD
    (a crucible sub-directory's own tree, a pinned clone's root tree). Clean
    working trees only; anything else hashes the files' paths, sizes and mtimes."""
    top = _git(repo, "rev-parse", "--show-toplevel")
    if top and not _git(repo, "status", "--porcelain", "--", "."):
        rel = os.path.relpath(repo.resolve(), Path(top).resolve()).replace(os.sep, "/")
        tree = _git(repo, "rev-parse", f"HEAD:{'' if rel == '.' else rel}")
        if tree:
            return f"git-{tree}"
    h = hashlib.sha1(usedforsecurity=False)
    for p in sorted(repo.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            st = p.stat()
            h.update(f"{p.relative_to(repo)}|{st.st_size}|{int(st.st_mtime)}\n".encode())
    return f"files-{h.hexdigest()}"


def cache_key(ref: Reference, repo: Path, version: str) -> str:
    h = hashlib.sha1(usedforsecurity=False)
    for f in ref.adapter_files:
        h.update(f.read_bytes())
    return f"{ref.lang}-{ref.tool}-{version}-c{CONTRACT_VERSION}-{h.hexdigest()[:12]}-{content_id(repo)}"


def reference_contract(lang: str, repo: Path, use_cache: bool = True) -> tuple[dict[str, Any], bool]:
    """(contract, from_cache) for `repo` under `lang`'s reference. Exits when the
    tool is not installed."""
    ref = REFERENCES[lang]
    version = ref.installed()
    if not version:
        raise SystemExit(f"callgraph_refs: {ref.tool} is not installed for {lang} -- {ref.install_hint}")
    path = CACHE_DIR / f"{cache_key(ref, repo, version)}.json"
    if use_cache and path.is_file():
        try:
            return json.loads(path.read_text()), True
        except (OSError, ValueError):
            pass  # a torn write: rebuild it
    raw = ref.build(repo)
    raw.setdefault("tool", ref.tool)
    raw["version"] = version
    if use_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw))
        tmp.replace(path)
    return raw, False


def reference_graph(lang: str, repo: Path, use_cache: bool = True) -> tuple[RefGraph, str]:
    raw, _ = reference_contract(lang, repo, use_cache)
    return load_contract(raw), str(raw["version"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lang", nargs="?", choices=sorted(REFERENCES))
    ap.add_argument("repo", nargs="?", type=Path)
    ap.add_argument("--list", action="store_true", help="languages, tools, pins and installed versions")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args(argv)
    if a.list or not a.lang:
        for r in REFERENCES.values():
            print(f"{r.lang:12} {r.tool:8} pinned {r.version:8} installed {r.installed() or '-':8} corpus {r.corpus}")
        return 0
    if a.repo is None:
        ap.error("repo is required with a language")
    raw, cached = reference_contract(a.lang, a.repo.resolve(), not a.no_cache)
    print(json.dumps(raw))
    print(f"callgraph_refs: {'cache hit' if cached else 'built'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
