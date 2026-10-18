#!/usr/bin/env python3
"""libclang oracle for the DOOM Port Speedrun harness (#5468): function-definition counts from a real C/C++ parser.

ctags and tree-sitter both read text, so a function a macro generates (``DEFINE_*(name)``) is invisible to them
(#5461). libclang runs the preprocessor first, so it counts those. It is only as good as its include path: a file whose
headers are missing still parses, but its macros may expand differently, so each count carries how many files had a
parse error. Used on a subset of ports (``--clang``), reported beside ctags and tree-sitter, never scored.

``libclang`` (the PyPI wheel, which bundles the shared library) is optional and imported lazily: without it
``clang_counts`` returns ``None`` and the harness leaves the columns empty.
"""

import json
import os
import shlex
from pathlib import Path

C_EXT = {".c": "c", ".h": "c", ".cc": "c++", ".cpp": "c++", ".cxx": "c++", ".c++": "c++", ".hpp": "c++", ".hh": "c++"}
DEFINITION_KINDS = (
    "FUNCTION_DECL", "CXX_METHOD", "CONSTRUCTOR", "DESTRUCTOR", "CONVERSION_FUNCTION", "FUNCTION_TEMPLATE",
)  # fmt: skip
MAX_INCLUDE_DIRS = 300
ERROR_SEVERITY = 3  # clang.cindex Diagnostic.Error; 4 is Fatal


def _index():
    try:
        import clang.cindex as cindex

        return cindex, cindex.Index.create()
    except Exception:  # no bindings, or no shared library behind them
        return None, None


def compile_commands(repo):
    """{absolute file: argument list} from ``<repo>/compile_commands.json`` (or ``build/``), compiler and output stripped."""
    for cand in (Path(repo) / "compile_commands.json", Path(repo) / "build" / "compile_commands.json"):
        if not cand.exists():
            continue
        try:
            entries = json.loads(cand.read_text())
        except ValueError:
            return {}
        out = {}
        for e in entries:
            args = e.get("arguments") or shlex.split(e.get("command", ""))
            keep, skip = [], False
            for a in args[1:]:
                if skip:
                    skip = False
                elif a in ("-o", "-MF", "-MT", "-MQ"):
                    skip = True
                elif a in ("-c", "-MD", "-MMD") or a == e.get("file"):
                    continue
                else:
                    keep.append(a)
            out[os.path.realpath(os.path.join(e.get("directory", repo), e["file"]))] = keep
        return out
    return {}


def include_dirs(repo):
    """The repo root plus every directory holding a header (capped): the best guess without a build system."""
    dirs = [str(repo)]
    for root, subdirs, files in os.walk(repo):
        subdirs[:] = [d for d in subdirs if d != ".git"]
        if any(f.endswith((".h", ".hpp", ".hh")) for f in files) and root != str(repo):
            dirs.append(root)
        if len(dirs) >= MAX_INCLUDE_DIRS:
            break
    return dirs


def count_definitions(cindex, index, path, args):
    """(definitions in this file itself, parse errors) for one translation unit."""
    tu = index.parse(str(path), args=args)
    real = os.path.realpath(path)
    kinds = {getattr(cindex.CursorKind, k) for k in DEFINITION_KINDS}
    count, stack = 0, [tu.cursor]
    while stack:
        cur = stack.pop()
        loc = cur.location.file
        if cur.kind in kinds:
            if loc is not None and os.path.realpath(loc.name) == real and cur.is_definition():
                count += 1
        if cur.kind == cindex.CursorKind.TRANSLATION_UNIT or (cur.kind.is_declaration() and cur.kind not in kinds):
            stack.extend(cur.get_children())
    return count, sum(d.severity >= ERROR_SEVERITY for d in tu.diagnostics)


def clang_counts(repo, files):
    """``(counts, with_errors, used_compile_commands)`` for the given C/C++ files, or ``None`` when libclang is absent.

    ``counts`` is {relpath: definitions}; ``with_errors`` the number of files whose parse reported an error;
    ``used_compile_commands`` how many files took their flags from a compile_commands.json entry.
    """
    cindex, index = _index()
    if index is None:
        return None
    repo = Path(repo)
    commands, incs = compile_commands(repo), None
    counts, with_errors, from_db = {}, 0, 0
    for rel in files:
        lang = C_EXT.get(os.path.splitext(rel)[1])
        if not lang:
            continue
        path = repo / rel
        args = commands.get(os.path.realpath(path))
        if args is None:
            incs = incs if incs is not None else include_dirs(repo)
            args = ["-x", lang, "-w", "-ferror-limit=0", f"-I{path.parent}", *(f"-I{d}" for d in incs)]
            if lang == "c++":
                args.append("-std=c++17")
        else:
            from_db += 1
        try:
            counts[rel], errs = count_definitions(cindex, index, path, args)
        except Exception:  # TranslationUnitLoadError on an unreadable file: skipped, not counted
            continue
        with_errors += bool(errs)
    return counts, with_errors, from_db
