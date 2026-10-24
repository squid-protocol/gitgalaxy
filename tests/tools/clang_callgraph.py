"""
The C call-graph reference (#3784, epic #3772): libclang's resolved call graph
as the callgraph_refs.py contract.

    python tests/tools/clang_callgraph.py <repo>      # the contract JSON on stdout

Each .c file of the repo is parsed as one translation unit (`clang.cindex`, the
pip `libclang` wheel, pinned in callgraph_refs). No compilation database: every
directory holding a header is an -I path, which is all a call graph needs, and
the bundled libclang recovers from the headers it cannot find.

* A def is a function definition with a body, in a .c file or a header; a
  prototype is not one (#3757). A def's line is where its declaration starts.
* A call is a CALL_EXPR whose callee is a named function. A static callee is
  that translation unit's own definition; any other callee is linked by symbol
  name to every external-linkage def of the repo (the link group across
  translation units). A callee with no def in the repo (libc, a system header)
  is `external`. A call through a function pointer names no function and is
  skipped. A macro that expands to a call is a call here, as the compiler sees it.
* Directories named `win` are not parsed: Windows-only sources need <windows.h>
  and their names collide with the Unix ones. Where per-platform files define the
  same external name, an edge goes to each definition.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SKIP_DIRS = frozenset({".git", "win"})


def _install_hint() -> str:
    return 'pip install "libclang==18.1.1"  (the Python clang.cindex bindings with a bundled libclang)'


def _walk(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            yield Path(root) / f


def _rel(repo: Path, name: str | None) -> str | None:
    if not name:
        return None
    rel = os.path.relpath(os.path.abspath(name), repo).replace(os.sep, "/")
    return None if rel.startswith("..") else rel


def build(repo: Path) -> dict[str, Any]:
    try:
        from clang import cindex
    except ImportError as exc:
        raise SystemExit(f"clang_callgraph: libclang is not installed ({exc}) -- {_install_hint()}") from exc

    repo = repo.resolve()
    sources, include_dirs = [], set()
    for p in _walk(repo):
        if p.suffix == ".c":
            sources.append(p)
        elif p.suffix == ".h":
            include_dirs.add(str(p.parent))
    args = ["-x", "c", "-w", "-ferror-limit=0", f"-I{repo}", *(f"-I{d}" for d in sorted(include_dirs))]
    kinds = cindex.CursorKind
    index = cindex.Index.create()

    defs: dict[tuple[str, str, int], bool] = {}  # key -> has external linkage
    calls: list[tuple[tuple[str, str, int], str, int]] = []  # caller, external callee name, line
    static_edges: dict[tuple[tuple, tuple], int] = {}
    seen_callers: set[tuple[str, str, int]] = set()

    def key_of(cursor) -> tuple[str, str, int] | None:
        loc = cursor.extent.start
        rel = _rel(repo, loc.file.name if loc.file else None)
        return (rel, cursor.spelling, loc.line) if rel else None

    for src in sources:
        tu = index.parse(str(src), args=args)
        for top in tu.cursor.get_children():
            if top.kind != kinds.FUNCTION_DECL or not top.is_definition():
                continue
            caller = key_of(top)
            if caller is None:
                continue
            defs[caller] = top.storage_class != cindex.StorageClass.STATIC
            if caller in seen_callers:  # a header function met again through another .c file
                continue
            seen_callers.add(caller)
            for node in top.walk_preorder():
                if node.kind != kinds.CALL_EXPR:
                    continue
                target = node.referenced
                if target is None or target.kind != kinds.FUNCTION_DECL:
                    continue
                if target.storage_class == cindex.StorageClass.STATIC:
                    body = target.get_definition()
                    callee = key_of(body) if body is not None else None
                    if callee and callee != caller:
                        static_edges.setdefault((caller, callee), node.location.line)
                else:
                    calls.append((caller, target.spelling, node.location.line))

    by_name: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for k, external_linkage in defs.items():
        if external_linkage:
            by_name[k[1]].append(k)
    edges: dict[tuple, int] = dict(static_edges)
    external: set[tuple] = set()
    for caller, name, line in calls:
        targets = [t for t in by_name.get(name, ()) if t != caller]
        if not targets and name not in by_name:
            external.add((caller, name))
        for t in targets:
            edges.setdefault((caller, t), line)
    return {
        "defs": sorted([list(k) for k in defs]),
        "edges": sorted([list(a), list(b), line] for (a, b), line in edges.items()),
        "external": sorted([list(c), n] for c, n in external),
        "files": len(sources),
    }


def libclang_version() -> str | None:
    """The installed libclang wheel's version, or None when clang.cindex cannot load its library."""
    import importlib.metadata

    try:
        from clang import cindex
    except ImportError:
        return None
    try:
        version = importlib.metadata.version("libclang")
        cindex.Index.create()
    except (importlib.metadata.PackageNotFoundError, cindex.LibclangError):
        return None
    return version


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit(__doc__)
    print(json.dumps(build(Path(args[0]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
