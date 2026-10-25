"""
The C and C++ call-graph reference (#3784, epic #3772): libclang's resolved call
graph as the callgraph_refs.py contract.

    python tests/tools/clang_callgraph.py <repo> [c|cpp]   # the contract JSON on stdout

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
* A def written as a one-argument macro (`TEST_IMPL(kill) {`, which declares `run_test_kill`) is named
  by the macro's argument, as the engine names it.
* Directories named `win` are not parsed: Windows-only sources need <windows.h>
  and their names collide with the Unix ones. Where per-platform files define the
  same external name, an edge goes to each definition.

C++ (`cpp`) differs in four ways:
* Sources are .cc/.cpp/.cxx, parsed as C++; definitions are found in namespaces and
  classes (methods, constructors, destructors, conversion operators, templates).
* A def is named as the engine names it: bare, except that a definition written outside
  its class (`int Foo::bar() {...}`) is `Foo::bar`.
* A call is linked to the exact overload by USR, not by name: the callee's declaration
  and its definition (a header prototype, a .cc body) share one USR. A function or
  method template is its pattern, whatever the instantiation. A callee with no def in
  the repo (std, libc) is `external`, under its bare and its qualified name.
* Internal linkage is `static` or an anonymous namespace: that callee is the
  translation unit's own definition.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SKIP_DIRS = frozenset({".git", "win"})

CPP_SOURCES = frozenset({".cc", ".cpp", ".cxx"})
CPP_HEADERS = frozenset({".h", ".hh", ".hpp", ".hxx"})  # each header's directory is an -I path
# the gtest macros whose body is `<suite>_<name>_Test::TestBody`; the engine names the unit `<name>`
GTEST_MACRO = re.compile(r"\b(?:TEST|TEST_F|TEST_P|TYPED_TEST|TYPED_TEST_P)\s*\(\s*\w+\s*,\s*(\w+)")
# `TEST_IMPL(name) {` and its siblings define `run_test_name`; the engine names the unit `name` (#3784)
IMPL_MACRO = re.compile(r"^\s*[A-Z][A-Z0-9_]*\(\s*(\w+)\s*\)\s*\{?\s*$")
CPP_ARGS = ("-x", "c++", "-std=c++20", "-w", "-ferror-limit=0")


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


def build(repo: Path, lang: str = "c") -> dict[str, Any]:
    if lang == "cpp":
        return _build_cpp(repo)
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

    source_lines: dict[str, list[str]] = {}

    def macro_name(cursor) -> str:
        """The engine's name for a def written `MACRO(name) {`: `name`, not the macro's `run_test_name`."""
        loc = cursor.extent.start
        lines = source_lines.get(loc.file.name)
        if lines is None:
            lines = source_lines[loc.file.name] = Path(loc.file.name).read_bytes().decode("latin-1").splitlines()
        hit = IMPL_MACRO.match(lines[loc.line - 1]) if 0 < loc.line <= len(lines) else None
        return hit.group(1) if hit and cursor.spelling.endswith(hit.group(1)) else cursor.spelling

    def key_of(cursor) -> tuple[str, str, int] | None:
        loc = cursor.extent.start
        rel = _rel(repo, loc.file.name if loc.file else None)
        return (rel, macro_name(cursor), loc.line) if rel else None

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


def _system_includes() -> list[str]:
    """The C++ standard-library and compiler-builtin header dirs of the host g++ (the pip libclang
    wheel carries neither); an empty list means no host compiler, and the parse cannot start."""
    try:
        out = subprocess.run(  # noqa: S603 -- fixed argv
            ["g++", "-E", "-x", "c++", "-v", os.devnull],  # noqa: S607
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    dirs, inside = [], False
    for line in out.stderr.splitlines():
        if line.startswith("#include <...>"):
            inside = True
        elif line.startswith("End of search"):
            break
        elif inside and line.startswith(" "):
            dirs.append(line.strip())
    return dirs


def _build_cpp(repo: Path) -> dict[str, Any]:
    try:
        from clang import cindex
    except ImportError as exc:
        raise SystemExit(f"clang_callgraph: libclang is not installed ({exc}) -- {_install_hint()}") from exc

    repo = repo.resolve()
    sources, include_dirs = [], set()
    for p in _walk(repo):
        if p.suffix in CPP_SOURCES:
            sources.append(p)
        elif p.suffix in CPP_HEADERS:
            # the header's directory and each ancestor: `#include "fmt/format.h"` lives under include/
            include_dirs.update(str(d) for d in (p.parent, *p.parent.parents) if d == repo or repo in d.parents)
    system = _system_includes()
    if not system:
        raise SystemExit("clang_callgraph: no host g++ to read the C++ system header dirs from -- install g++")
    # the repo's header dirs go AFTER the system ones: a repo header named like a system one
    # (`<format.h>` vs `<format>`'s includes) must not shadow it
    args = [
        *CPP_ARGS,
        f"-I{repo}",
        *(f"-isystem{d}" for d in system),
        *(f"-idirafter{d}" for d in sorted(include_dirs)),
    ]
    kinds = cindex.CursorKind
    func_kinds = {
        kinds.FUNCTION_DECL,
        kinds.CXX_METHOD,
        kinds.CONSTRUCTOR,
        kinds.DESTRUCTOR,
        kinds.CONVERSION_FUNCTION,
        kinds.FUNCTION_TEMPLATE,
    }
    scope_kinds = {
        kinds.NAMESPACE,
        kinds.CLASS_DECL,
        kinds.STRUCT_DECL,
        kinds.UNION_DECL,
        kinds.CLASS_TEMPLATE,
        kinds.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
        kinds.LINKAGE_SPEC,
    }
    type_scopes = scope_kinds - {kinds.NAMESPACE, kinds.LINKAGE_SPEC}
    index = cindex.Index.create()

    def key_of(cursor, name: str) -> tuple[str, str, int] | None:
        loc = cursor.extent.start
        rel = _rel(repo, loc.file.name if loc.file else None)
        return (rel, name, loc.line) if rel else None

    source_lines: dict[str, list[str]] = {}

    def gtest_name(cursor) -> str | None:
        """#3784: a `TEST(suite, name) {...}` body is the method `suite_name_Test::TestBody`; the engine
        names it `name`. The macro's own line holds the pair, so read it (`suite_name` alone is ambiguous)."""
        loc = cursor.extent.start
        if loc.file is None or cursor.spelling != "TestBody":
            return None
        lines = source_lines.get(loc.file.name)
        if lines is None:
            lines = source_lines[loc.file.name] = Path(loc.file.name).read_bytes().decode("latin-1").splitlines()
        hit = GTEST_MACRO.search(lines[loc.line - 1]) if 0 < loc.line <= len(lines) else None
        return hit.group(1) if hit else None

    def name_of(cursor) -> str:
        """The engine's name: bare, `Class::name` when the body is written outside the class."""
        test = gtest_name(cursor)
        if test:
            return test
        # a partial specialization's constructor is spelled with its arguments: `buffer<T *, U>`
        name = (
            cursor.spelling.split("<")[0]
            if cursor.kind in (kinds.CONSTRUCTOR, kinds.DESTRUCTOR, kinds.CONVERSION_FUNCTION)
            else cursor.spelling
        )
        owner, written_in = cursor.semantic_parent, cursor.lexical_parent
        if (
            owner is not None
            and owner.kind in type_scopes
            and (written_in is None or written_in.kind not in type_scopes)
        ):
            return f"{owner.spelling.split('<')[0]}::{name}"
        return name

    def internal(cursor) -> bool:
        return cursor.linkage in (cindex.LinkageKind.INTERNAL, cindex.LinkageKind.NO_LINKAGE)

    def pattern(cursor):
        """A template instantiation -> the template it came from."""
        template = cindex.conf.lib.clang_getSpecializedCursorTemplate(cursor)
        return template if template is not None and not template.kind.is_invalid() else cursor

    defs: set[tuple[str, str, int]] = set()
    by_usr: dict[str, tuple[str, str, int]] = {}
    calls: list[tuple[tuple[str, str, int], str, tuple[str, ...], int]] = []  # caller, usr, names, line
    static_edges: dict[tuple[tuple, tuple], int] = {}
    seen_callers: set[tuple[str, str, int]] = set()

    def visit(top) -> None:
        if top.kind in scope_kinds:
            for child in top.get_children():
                visit(child)
            return
        if top.kind not in func_kinds or not top.is_definition():
            return
        caller = key_of(top, name_of(top))
        if caller is None:
            return
        defs.add(caller)
        usr = top.get_usr()
        if usr and not internal(top):
            by_usr.setdefault(usr, caller)
        if caller in seen_callers:  # a header function met again through another source file
            return
        seen_callers.add(caller)
        for node in top.walk_preorder():
            if node.kind != kinds.CALL_EXPR:
                continue
            target = node.referenced
            if target is None or target.kind not in func_kinds:
                continue
            target = pattern(target)
            if internal(target):
                body = target.get_definition()
                callee = key_of(body, name_of(body)) if body is not None else None
                if callee and callee != caller:
                    static_edges.setdefault((caller, callee), node.location.line)
            else:
                calls.append((caller, target.get_usr(), (target.spelling, name_of(target)), node.location.line))

    for src in sources:
        tu = index.parse(str(src), args=args)
        for top in tu.cursor.get_children():
            visit(top)

    edges: dict[tuple, int] = dict(static_edges)
    external: set[tuple] = set()
    for caller, usr, names, line in calls:
        target = by_usr.get(usr)
        if target is None:
            external.update((caller, n) for n in names)
        elif target != caller:
            edges.setdefault((caller, target), line)
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
    if len(args) not in (1, 2) or (len(args) == 2 and args[1] not in ("c", "cpp")):
        raise SystemExit(__doc__)
    print(json.dumps(build(Path(args[0]), args[1] if len(args) == 2 else "c")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
