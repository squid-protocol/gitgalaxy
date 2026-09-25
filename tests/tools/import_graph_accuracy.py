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
Import-graph accuracy: the engine's file->file `import` edges against a parser's
own import statements, on pinned real repos, per language.

The import graph is what PageRank, blast radius, popularity and
`dependency_density` run on. Until this audit nothing checked its EDGES: the
graph maths are pinned against networkx (graph_parity.py), the import COUNT by
its contract (docs/import_rule_contract.md), but not whether an edge joins the
two files the source actually joins. Found missing while measuring #3544/#3545.

CORPUS
  tests/import_graph_corpus.json pins one or more real upstream repos per
  language, fetched shallow at a fixed commit (`--fetch`) into
  IMPORT_GRAPH_CORPUS_PATH (default ../import-graph-corpus). Not language-crucible:
  its samples are flattened into one directory per repo, so `py/compile.h`,
  `../core.js` or a PSR-4 namespace path no longer exist there and no parser can
  say what an import meant.

HOW
  Engine: each repo is scanned SEPARATELY, as the repo it is (one galaxyscope run
          per repo, in a subprocess pinned to this checkout), and its `edge_data`
          rows of kind `import` are read.
  Parser: every file the engine classified as the repo's language is parsed --
          Python with the stdlib `ast`, the rest with tree-sitter -- and each
          import statement is resolved by the LANGUAGE'S OWN rule (below) to the
          set of files in the same repo it can mean. An import that resolves to
          nothing in the repo is external (a library, the stdlib) and is not
          scored.

  precision = engine import edges whose target is in one of the source file's
              resolved import sets / all engine import edges from that language
  recall    = resolvable import statements with at least one engine edge into
              their set / all resolvable import statements
  Scored per import STATEMENT, not per edge, because a statement names a set:
  a Go import is a package (a directory of files), `from a import b` can mean
  `a/__init__.py` or `a/b.py`.

RESOLUTION RULES (the language's, never the engine's)
  python      `import a.b` / `from a.b import c`: a/b.py, a/b/__init__.py, and for
              `from`, a/b/c.py -- under any SOURCE ROOT (a directory that is not a
              package itself: the repo root, src/, ...). Relative imports resolve
              exactly against the importing package.
  go          import path p inside a go.mod's module -> every .go file in the
              module's directory joined with the rest of p (a package is its
              directory); outside every module, external.
  c, cpp      `#include "x/y.h"`: the including file's directory first, else any
              file ending in /x/y.h (the include path); `<x/y.h>` the latter only.
  java        `a.b.C` -> .../a/b/C.java; `a.b.*` -> files in .../a/b; a static
              import drops the member, and a nested class `a.b.Outer.Inner`
              lives in .../a/b/Outer.java.
  javascript, typescript
              relative specifiers only (`./`, `../`): the path, with each JS/TS
              extension, a `.js` spelling of a `.ts` file, or its index file.
              Bare specifiers are packages (or tsconfig aliases) and not scored.
  lua         `require "a.b"` -> a/b.lua, a/b/init.lua (suffix); dofile/loadfile
              string paths by suffix.
  php         include/require of a string literal (a leading __DIR__ . "/x"
              folds away): relative to the file, else by suffix. `use A\\B\\C` and
              a class-body trait `use T;` (resolved through the file's namespace
              and imports) -> the file composer.json's PSR-4 map gives the class,
              else a file ending in its last two segments.
  zig         `@import("x.zig")` / `@import("x.zon")` relative to the file; a module
              name -> the module root build.zig declares with `b.path("<name>.zig")`
              (by file name: build.zig is code, so the name->root binding is read
              by name, not evaluated). std/builtin/root and dependencies are external.
  ruby        require_relative exact; require under a load-path root (a lib/, test/
              or spec/ directory, or the repo root).
  rust        `mod a;` -> a.rs or a/mod.rs beside a mod.rs or crate root (lib/main/
              build.rs, a file in tests/, examples/, benches/ or src/bin/), else in
              the file's own stem directory. A `#[path = "..."]` override is not
              read (such a `mod` is left unscored). `use` paths are not scored.
  perl        `use A::B` / `require A::B` -> a file ending in A/B.pm.
  objective-c the C rule (`#import` is `#include` once); `@import Module;` is a
              framework module, external.
  dart        `package:p/x.dart` -> <p's pubspec.yaml directory>/lib/x.dart for a
              package in the repo, else external; `dart:` is the SDK; any other
              URI (import, export, part, part of) is relative to the file.
  kotlin, scala
              by PACKAGE and NAME, never by path: every file's package and its
              top-level declarations are indexed, and `a.b.C` is a file declaring
              C in package a.b. A member or nested import falls back to its
              owner's file; `a.b.*` / `a.b._` is the package's files (or an
              object's); Scala retries a name relative to each enclosing package.
              A Java class is found by Java's rule (a/b/C.java).
  haskell     `import A.B.C` -> a file ending in A/B/C.hs (.lhs, .hsc).
  shell       `source p` / `. p`: relative to the file, else by suffix; a path
              behind a variable (`"$DIR/lib/x.sh"`) keeps its literal tail and
              matches by suffix.
  solidity    `./`/`../` relative to the file; `@scope/pkg/x.sol` through a
              package.json in the repo named @scope/pkg (npm remapping); else
              from the project root; otherwise a dependency.

  NOT HERE: COBOL. tree-sitter-cobol has no EXEC SQL / EXEC CICS rule, so its
  error recovery swallows the COPY statements after one (CBSA's ACCTCTRL: one
  ERROR node spans lines 85-127, taking three COPYs with it) -- it found 64 of
  CBSA's ~148 COPY/INCLUDE statements. COBOL's copybook and call edges are scored
  against the hand-verified answer keys instead (tests/cobol_mainframe/, gated by
  ground_truth_ledger.py on every PR), a stronger truth than this parser gives.

  These are the rules a compiler or interpreter applies, minus configuration
  the corpus does not carry (include flags, tsconfig paths, GOPATH, @INC); where
  configuration would pick one root, the suffix match accepts any. Disagreements
  are leads to check against source, per CLAUDE.md's comparative-correctness
  rule: a dynamic import the parser cannot see (`__import__('x')`) shows up as a
  false positive the engine actually got right.

    python tests/tools/import_graph_accuracy.py --fetch-only   # clone the pinned repos (once)
    python tests/tools/import_graph_accuracy.py                # report
    python tests/tools/import_graph_accuracy.py --samples 5    # + example FP/FN
    python tests/tools/import_graph_accuracy.py --buckets 3    # + FP/FN by cause, raw + validated
    python tests/tools/import_graph_accuracy.py --ledger       # merge the shapes into the graph
                                                               # comparison ledger (#3641)
    python tests/tools/import_graph_accuracy.py --ci           # gate vs the baseline
    python tests/tools/import_graph_accuracy.py --regenerate   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import ast
import collections
import concurrent.futures
import json
import os
import posixpath
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = Path(os.environ.get("IMPORT_GRAPH_CORPUS_PATH", REPO_ROOT.parent / "import-graph-corpus"))
MANIFEST = REPO_ROOT / "tests" / "import_graph_corpus.json"
BASELINE = REPO_ROOT / "tests" / "import_graph_accuracy_baseline.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graph_ledger as gl  # noqa: E402

LANGS = (
    "python",
    "go",
    "c",
    "cpp",
    "java",
    "javascript",
    "typescript",
    "lua",
    "php",
    "zig",
    "ruby",
    "rust",
    "perl",
    "objective-c",
    "dart",
    "kotlin",
    "scala",
    "haskell",
    "shell",
    "solidity",
)

# Gate tolerance, in percentage points, before --ci calls a drop a regression.
TOLERANCE_PP = 0.5
# A language whose measurement has fewer resolvable imports than this is
# reported but not gated: one statement would swing it by several points.
MIN_GATED_IMPORTS = 5

_ZIG_B_PATH = re.compile(r'\bb\.path\(\s*"([^"\n]{1,200}\.zig)"\s*\)')
_RUBY_LOAD_ROOT = re.compile(r"(?:.*/)?(?:lib|test|spec)|")
_JS_EXTS = (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")


# ----------------------------------------------------------------------------- file sets


class Group:
    """The files of one scanned repo group, by path relative to the group root."""

    def __init__(self, files: Iterable[str], root: Optional[Path] = None):
        self.root = root
        self.files = set(files)
        self._cache: dict[str, Any] = {}
        self.by_dir: dict[str, set[str]] = collections.defaultdict(set)
        for f in self.files:
            self.by_dir[posixpath.dirname(f)].add(f)

    def exact(self, path: str) -> set[str]:
        path = posixpath.normpath(path)
        return {path} if path in self.files else set()

    def suffix(self, tail: str) -> set[str]:
        """Files whose path is `tail` or ends in `/tail` -- a match under any root."""
        tail = tail.strip("/")
        if not tail:
            return set()
        return {f for f in self.files if f == tail or f.endswith("/" + tail)}

    def read_json(self, rel: str) -> Any:
        if self.root is None or rel not in self.files:
            return None
        try:
            return json.loads((self.root / rel).read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            return None

    def go_modules(self) -> list[tuple[str, str]]:
        """(module path, its directory) for every go.mod, longest module first."""
        if "go" not in self._cache:
            mods = []
            # From disk: a scan does not record go.mod as a source file.
            for gomod in sorted(self.root.rglob("go.mod")) if self.root is not None else []:
                f = gomod.relative_to(self.root).as_posix()
                if "/vendor/" in f"/{f}" or "/testdata/" in f"/{f}":
                    continue
                try:
                    text = gomod.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                module = next((ln.split()[1].strip('"') for ln in text.splitlines() if ln.startswith("module ")), None)
                if module:
                    mods.append((module, posixpath.dirname(f)))
            self._cache["go"] = sorted(mods, key=lambda m: -len(m[0]))
        return self._cache["go"]

    def zig_module_roots(self) -> list[str]:
        """Every file a build.zig names with `b.path("...")` -- module root sources."""
        if "zig" not in self._cache:
            roots = []
            for build in sorted(self.root.rglob("build.zig")) if self.root is not None else []:
                base = build.parent.relative_to(self.root).as_posix()
                try:
                    text = build.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for m in _ZIG_B_PATH.finditer(text):
                    roots.append(posixpath.normpath(posixpath.join("" if base == "." else base, m.group(1))))
            self._cache["zig"] = roots
        return self._cache["zig"]

    def psr4(self) -> list[tuple[str, str]]:
        """(namespace prefix, directory) from composer.json autoload(-dev) psr-4, longest first."""
        if "psr4" not in self._cache:
            pairs = []
            data = self.read_json("composer.json") or {}
            for section in ("autoload", "autoload-dev"):
                for prefix, dirs in ((data.get(section) or {}).get("psr-4") or {}).items():
                    for d in [dirs] if isinstance(dirs, str) else dirs:
                        pairs.append((prefix.strip("\\"), d.strip("/")))
            self._cache["psr4"] = sorted(pairs, key=lambda m: -len(m[0]))
        return self._cache["psr4"]

    def python_module(self, dotted: str) -> set[str]:
        """The files an absolute Python module path can be: `a/b.py` or
        `a/b/__init__.py` under a SOURCE ROOT -- a directory that is not itself a
        package. `import types` is the stdlib, not `fastapi/types.py`: that file is
        `fastapi.types`, because `fastapi/` has an `__init__.py`."""
        m = dotted.replace(".", "/")
        out = set()
        for tail in (m + ".py", m + "/__init__.py"):
            for f in self.suffix(tail):
                prefix = f[: -len(tail)].rstrip("/")
                if not prefix or posixpath.join(prefix, "__init__.py") not in self.files:
                    out.add(f)
        return out

    def dirs_with_suffix(self, tail: str) -> list[str]:
        tail = tail.strip("/")
        return [d for d in self.by_dir if d and (tail == d or tail.endswith("/" + d))]


# ----------------------------------------------------------------------------- import statements


def _text(node: Any, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _string_value(node: Any, src: bytes) -> Optional[str]:
    """The literal content of a string node (quotes stripped), or None."""
    raw = _text(node, src).strip()
    if len(raw) >= 2 and raw[0] in "\"'`" and raw[-1] == raw[0]:
        return raw[1:-1]
    return None


def _walk(node: Any) -> Iterable[Any]:
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def python_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return []
    pkg = posixpath.dirname(rel)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(group.python_module(alias.name))
        elif isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names if a.name != "*"]
            if node.level:
                base = pkg.split("/") if pkg else []
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                prefix = "/".join(base)
                mod = (node.module or "").replace(".", "/")
                root = posixpath.join(prefix, mod) if mod else prefix
                targets: set[str] = set()
                if mod:
                    targets |= group.exact(root + ".py") | group.exact(posixpath.join(root, "__init__.py"))
                for n in names:
                    targets |= group.exact(posixpath.join(root, n + ".py"))
                    targets |= group.exact(posixpath.join(root, n, "__init__.py"))
                if not mod and not targets:
                    targets |= group.exact(posixpath.join(root, "__init__.py"))
                out.append(targets)
            elif node.module:
                targets = group.python_module(node.module)
                for n in names:
                    targets |= group.python_module(f"{node.module}.{n}")
                out.append(targets)
    return out


def _ts_tree(lang: str, src: bytes) -> Any:
    import tree_sitter_language_pack

    return tree_sitter_language_pack.get_parser(lang).parse(src).root_node


def go_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    for n in _walk(_ts_tree("go", src)):
        if n.type == "import_spec":
            for c in n.children:
                if c.type in ("interpreted_string_literal", "raw_string_literal"):
                    path = _string_value(c, src) or ""
                    targets: set[str] = set()
                    # Go's rule: an import path inside a module is the module's
                    # directory plus the rest of the path; outside every go.mod
                    # it is another module (external).
                    for module, mdir in group.go_modules():
                        if path == module or path.startswith(module + "/"):
                            d = posixpath.normpath(posixpath.join(mdir, path[len(module) :].lstrip("/")))
                            d = "" if d == "." else d
                            targets = {f for f in group.by_dir.get(d, ()) if f.endswith(".go")}
                            break
                    out.append(targets)
    return out


def c_imports(lang: str) -> Callable[[bytes, str, Group], list[set[str]]]:
    def imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
        out = []
        for n in _walk(_ts_tree(lang, src)):
            if n.type != "preproc_include":
                continue
            for c in n.children:
                if c.type == "string_literal":
                    spec = _string_value(c, src) or ""
                    local = group.exact(posixpath.join(posixpath.dirname(rel), spec))
                    out.append(local or group.suffix(spec))
                elif c.type == "system_lib_string":
                    out.append(group.suffix(_text(c, src).strip("<> ")))
        return out

    return imports


def java_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    for n in _walk(_ts_tree("java", src)):
        if n.type != "import_declaration":
            continue
        text = _text(n, src)
        ident = next((c for c in n.children if c.type == "scoped_identifier"), None)
        if ident is None:
            continue
        parts = _text(ident, src).split(".")
        if any(c.type == "asterisk" for c in n.children):
            targets = set()
            for d in group.dirs_with_suffix("/".join(parts)):
                targets |= {f for f in group.by_dir[d] if f.endswith(".java")}
            out.append(targets)
            continue
        if text.split()[1:2] == ["static"] and len(parts) > 1:
            parts = parts[:-1]
        targets = group.suffix("/".join(parts) + ".java")
        # A nested class (`a.b.Outer.Inner`) lives in its outer class's file.
        while not targets and len(parts) > 2 and parts[-2][:1].isupper():
            parts = parts[:-1]
            targets = group.suffix("/".join(parts) + ".java")
        out.append(targets)
    return out


def js_imports(lang: str) -> Callable[[bytes, str, Group], list[set[str]]]:
    def resolve(spec: str, rel: str, group: Group) -> Optional[set[str]]:
        if not spec.startswith(("./", "../")):
            return None  # a package or a configured alias: not the language's rule to resolve
        base = posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec))
        cands = [base] + [base + e for e in _JS_EXTS] + [posixpath.join(base, "index" + e) for e in _JS_EXTS]
        stem, ext = posixpath.splitext(base)
        if ext in (".js", ".jsx", ".mjs", ".cjs"):  # ESM spelling of a TS source: './a.js' -> a.ts
            cands += [stem + e for e in (".ts", ".tsx", ".mts", ".cts", ".d.ts")]
        return {c for c in cands if c in group.files}

    def imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
        out = []
        for n in _walk(_ts_tree(lang, src)):
            spec = None
            if n.type in ("import_statement", "export_statement"):
                s = next((c for c in n.children if c.type == "string"), None)
                spec = _string_value(s, src) if s is not None else None
            elif n.type == "call_expression" and n.children:
                callee = n.children[0]
                if callee.type == "import" or (callee.type == "identifier" and _text(callee, src) == "require"):
                    args = next((c for c in n.children if c.type == "arguments"), None)
                    first = next((c for c in args.children if c.type == "string"), None) if args else None
                    spec = _string_value(first, src) if first is not None else None
            if spec:
                targets = resolve(spec, rel, group)
                if targets is not None:
                    out.append(targets)
        return out

    return imports


def lua_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    for n in _walk(_ts_tree("lua", src)):
        if n.type != "function_call" or not n.children or n.children[0].type != "identifier":
            continue
        fn = _text(n.children[0], src)
        if fn not in ("require", "dofile", "loadfile"):
            continue
        args = next((c for c in n.children if c.type == "arguments"), None)
        s = next((c for c in _walk(args) if c.type == "string"), None) if args else None
        spec = _string_value(s, src) if s is not None else None
        if not spec:
            continue
        if fn == "require":
            m = spec.replace(".", "/")
            out.append(group.suffix(m + ".lua") | group.suffix(m + "/init.lua"))
        else:
            out.append(group.suffix(spec))
    return out


def _php_class_file(fqn: str, group: Group) -> set[str]:
    """The file PSR-4 (composer.json) maps a fully-qualified class to; without a
    mapping, a file ending in its last two name segments."""
    fqn = fqn.strip("\\")
    for prefix, d in group.psr4():
        if prefix and (fqn == prefix or fqn.startswith(prefix + "\\")):
            rest = fqn[len(prefix) :].strip("\\").replace("\\", "/")
            return group.exact(posixpath.join(d, rest + ".php"))
    parts = [p for p in fqn.split("\\") if p]
    return group.suffix("/".join(parts[-2:]) + ".php") if parts else set()


def php_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    tree = _ts_tree("php", src)
    namespace = ""
    aliases: dict[str, str] = {}  # alias (last segment or `as` name) -> FQN, from `use` imports
    uses: list[str] = []
    traits: list[str] = []
    for n in _walk(tree):
        if n.type == "namespace_definition":
            nm = next((c for c in n.children if c.type == "namespace_name"), None)
            namespace = _text(nm, src) if nm is not None else ""
        elif n.type in (
            "require_expression",
            "require_once_expression",
            "include_expression",
            "include_once_expression",
        ):
            strings = [c for c in _walk(n) if c.type in ("encapsed_string", "string")]
            if len(strings) != 1:
                continue  # a computed path: not a literal the rule can resolve
            spec = (_string_value(strings[0], src) or "").lstrip("/")
            if not spec or "$" in spec:
                continue
            local = group.exact(posixpath.join(posixpath.dirname(rel), spec))
            out.append(local or group.suffix(spec))
        elif n.type == "namespace_use_declaration":
            if any(c.type in ("function", "const") for c in n.children):
                continue  # `use function` / `use const` import a symbol, not a class file
            prefix = next((c for c in n.children if c.type == "namespace_name"), None)
            group_node = next((c for c in n.children if c.type == "namespace_use_group"), None)
            clauses = group_node.children if group_node is not None else n.children
            base = (_text(prefix, src) + "\\") if (group_node is not None and prefix is not None) else ""
            for clause in clauses:
                if clause.type != "namespace_use_clause":
                    continue
                names = [c for c in clause.children if c.type in ("qualified_name", "name")]
                if not names:
                    continue
                fqn = base + _text(names[0], src)
                alias = _text(names[1], src) if len(names) > 1 else fqn.split("\\")[-1]
                aliases[alias] = fqn
                uses.append(fqn)
        elif n.type == "use_declaration":  # a trait used inside a class body
            traits += [_text(c, src) for c in n.children if c.type in ("qualified_name", "name")]
    out += [_php_class_file(fqn, group) for fqn in uses]
    for t in traits:  # PHP name resolution: fully qualified, an imported alias, else the current namespace
        if t.startswith("\\"):
            fqn = t
        elif t.split("\\")[0] in aliases:
            head, _, tail = t.partition("\\")
            fqn = aliases[head] + ("\\" + tail if tail else "")
        else:
            fqn = (namespace + "\\" + t) if namespace else t
        out.append(_php_class_file(fqn, group))
    return out


def zig_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    for n in _walk(_ts_tree("zig", src)):
        if n.type == "BUILTINIDENTIFIER" and _text(n, src) == "@import" and n.parent is not None:
            args = next((c for c in n.parent.children if c.type == "FnCallArguments"), None)
            s = (
                next((c for c in _walk(args) if c.type in ("STRINGLITERALSINGLE", "STRINGLITERAL")), None)
                if args
                else None
            )
            spec = _string_value(s, src) if s is not None else None
            if spec and spec.endswith((".zig", ".zon")):
                out.append(group.exact(posixpath.join(posixpath.dirname(rel), spec)))
            elif spec and spec not in ("std", "builtin", "root"):
                # A build-configured module: the build.zig module root of that name.
                out.append(
                    {r for r in group.zig_module_roots() if posixpath.basename(r) == spec + ".zig"} & group.files
                )
    return out


def ruby_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    for n in _walk(_ts_tree("ruby", src)):
        if n.type != "call" or not n.children or n.children[0].type != "identifier":
            continue
        fn = _text(n.children[0], src)
        if fn not in ("require", "require_relative"):
            continue
        args = next((c for c in n.children if c.type == "argument_list"), None)
        s = next((c for c in args.children if c.type == "string"), None) if args else None
        spec = _string_value(s, src) if s is not None else None
        if not spec or "#{" in spec:
            continue
        spec = spec if spec.endswith(".rb") else spec + ".rb"
        if fn == "require_relative":
            out.append(group.exact(posixpath.join(posixpath.dirname(rel), spec)))
        else:  # the load path: a lib/ (or test/, spec/) directory, or the repo root
            out.append({f for f in group.suffix(spec) if _RUBY_LOAD_ROOT.fullmatch(f[: -len(spec)].rstrip("/"))})
    return out


def rust_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    d, name = posixpath.split(rel)
    # A mod.rs and a crate root (lib/main/build.rs, tests/, examples/, benches/, src/bin/) own their directory.
    crate_root = posixpath.basename(d) in ("tests", "examples", "benches") or d == "src/bin" or d.endswith("/src/bin")
    owns = name in ("mod.rs", "lib.rs", "main.rs", "build.rs") or crate_root
    owner = d if owns else posixpath.join(d, posixpath.splitext(name)[0])
    for n in _walk(_ts_tree("rust", src)):
        if n.type == "mod_item" and not any(c.type == "declaration_list" for c in n.children):
            ident = next((c for c in n.children if c.type == "identifier"), None)
            if ident is not None:
                m = _text(ident, src)
                out.append(
                    group.exact(posixpath.join(owner, m + ".rs")) | group.exact(posixpath.join(owner, m, "mod.rs"))
                )
    return out


def perl_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    out = []
    for n in _walk(_ts_tree("perl", src)):
        if n.type == "use_statement":
            pkg = next((c for c in n.children if c.type == "package"), None)
            name = _text(pkg, src) if pkg is not None else ""
            if name[:1].isupper():  # lower-case names are pragmas (strict, warnings, lib)
                out.append(group.suffix(name.replace("::", "/") + ".pm"))
        elif n.type == "require_expression":
            bare = next((c for c in n.children if c.type == "bareword"), None)
            lit = next((c for c in n.children if c.type == "string_literal"), None)
            if bare is not None:
                out.append(group.suffix(_text(bare, src).replace("::", "/") + ".pm"))
            elif lit is not None and (spec := _string_value(lit, src)):
                out.append(group.suffix(spec))
    return out


# ----------------------------------------------------------------------------- package-scoped JVM languages


def _jvm_decl_index(group: Group, lang: str, exts: tuple[str, ...]) -> dict[str, Any]:
    """Kotlin / Scala: a declaration's file is found by PACKAGE and NAME, not by
    path -- neither language ties the directory or the file name to what it
    declares. Every file of the language is parsed once: its package, and the
    names it declares at top level (classes, objects, traits, functions,
    properties, type aliases; a Scala `package object p` adds package `pkg.p`)."""
    key = "decl:" + lang
    if key in group._cache:
        return group._cache[key]
    by_name: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    by_pkg: dict[str, set[str]] = collections.defaultdict(set)
    for f in group.files:
        if not f.endswith(exts) or group.root is None:
            continue
        try:
            src = (group.root / f).read_bytes()
        except OSError:
            continue
        root = _ts_tree(lang, src)
        pkg_parts: list[str] = []
        names: list[tuple[str, str]] = []  # (package suffix, name)
        for c in root.children:
            t = c.type
            if t in ("package_header", "package_clause"):
                ident = next((x for x in c.children if x.type in ("identifier", "package_identifier")), None)
                if ident is not None:
                    # a backquoted segment (`io.circe.`export``) is the plain name
                    pkg_parts += [p.strip("`") for p in re.split(r"[.\s]+", _text(ident, src)) if p.strip("`")]
            elif t == "package_object":
                n = c.child_by_field_name("name")
                if n is not None:
                    by_pkg[".".join([*pkg_parts, _text(n, src)])].add(f)
                    names.append(("", _text(n, src)))
            else:
                n = c.child_by_field_name("name")
                if n is None:
                    n = next(
                        (x for x in c.children if x.type in ("type_identifier", "simple_identifier", "identifier")),
                        None,
                    )
                if n is None and t == "property_declaration":
                    vd = next((x for x in c.children if x.type == "variable_declaration"), None)
                    n = next((x for x in vd.children if x.type == "simple_identifier"), None) if vd else None
                if n is not None and t.endswith(("declaration", "definition", "type_alias", "object")):
                    names.append(("", _text(n, src)))
        pkg = ".".join(pkg_parts)
        by_pkg[pkg].add(f)
        for _, name in names:
            by_name[(pkg, name)].add(f)

    def java_file(parts: list[str]) -> set[str]:
        for cut in range(0, min(3, len(parts))):
            head = parts[: len(parts) - cut]
            hit = group.suffix("/".join(head) + ".java") if head else set()
            if hit:
                return hit
        return set()

    group._cache[key] = {"name": by_name, "pkg": by_pkg, "java": java_file}
    return group._cache[key]


def _jvm_resolve(index: dict[str, Any], parts: list[str], wildcard: bool, context: str) -> set[str]:
    """`a.b.C` -> the files declaring C in package a.b; a member or nested import
    (`a.b.C.member`, `a.b.C.Inner`) -> C's file; `a.b.*` -> package a.b's files
    (or, for an object, its file). A name not found absolutely is retried under
    each enclosing package of the importing file (Scala's relative imports)."""
    prefixes = [""]
    ctx = context.split(".") if context else []
    prefixes += [".".join(ctx[:i]) for i in range(len(ctx), 0, -1)]
    for prefix in prefixes:
        full = ([*prefix.split(".")] if prefix else []) + parts
        if wildcard:
            hit = set(index["pkg"].get(".".join(full), ()))
            if not hit and len(full) > 1:
                hit = set(index["name"].get((".".join(full[:-1]), full[-1]), ()))
            if hit:
                return hit
            continue
        for cut in range(0, min(3, len(full) - 1)):
            head = full[: len(full) - cut]
            hit = index["name"].get((".".join(head[:-1]), head[-1]))
            if hit:
                return set(hit)
    # A JVM language also imports Java classes, by Java's rule (a/b/C.java).
    java = index["java"](parts)
    return java


def _jvm_package_of(index: dict[str, Any], rel: str) -> str:
    return next((p for p, fs in index["pkg"].items() if rel in fs), "")


def kotlin_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    index = _jvm_decl_index(group, "kotlin", (".kt", ".kts"))
    out = []
    for n in _walk(_ts_tree("kotlin", src)):
        if n.type != "import_header":
            continue
        ident = next((c for c in n.children if c.type == "identifier"), None)
        if ident is None:
            continue
        parts = [_text(s, src) for s in ident.children if s.type == "simple_identifier"]
        wildcard = any(c.type == "wildcard_import" for c in n.children)
        out.append(_jvm_resolve(index, parts, wildcard, ""))
    return out


def scala_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    index = _jvm_decl_index(group, "scala", (".scala", ".sc"))
    context = _jvm_package_of(index, rel)
    out = []
    for n in _walk(_ts_tree("scala", src)):
        if n.type != "import_declaration":
            continue
        path = [_text(c, src) for c in n.children if c.type == "identifier"]
        selectors = next((c for c in n.children if c.type == "namespace_selectors"), None)
        if any(c.type == "namespace_wildcard" for c in n.children):
            out.append(_jvm_resolve(index, path, True, context))
        elif selectors is not None:
            for s in selectors.children:
                if s.type == "identifier":
                    out.append(_jvm_resolve(index, [*path, _text(s, src)], False, context))
                elif s.type == "arrow_renamed_identifier":
                    first = next((x for x in s.children if x.type == "identifier"), None)
                    if first is not None:
                        out.append(_jvm_resolve(index, [*path, _text(first, src)], False, context))
                elif s.type in ("namespace_wildcard", "wildcard"):
                    out.append(_jvm_resolve(index, path, True, context))
        elif path:
            out.append(_jvm_resolve(index, path, False, context))
    return out


# ----------------------------------------------------------------------------- dart, haskell, shell, solidity


def dart_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    """`package:p/x.dart` -> <p's pubspec directory>/lib/x.dart for a package in
    this repo (a pubspec.yaml whose `name:` is p), else external; `dart:` is the
    SDK; anything else is relative to the file. import, export, part, part of."""
    if "pubspec" not in group._cache:
        pkgs = {}
        for spec in sorted(group.root.rglob("pubspec.yaml")) if group.root is not None else []:
            try:
                text = spec.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            m = re.search(r"^name:\s*([\w.]+)", text, re.M)
            if m:
                base = spec.parent.relative_to(group.root).as_posix()
                pkgs[m.group(1)] = "" if base == "." else base
        group._cache["pubspec"] = pkgs
    pkgs = group._cache["pubspec"]
    out = []
    for n in _walk(_ts_tree("dart", src)):
        if n.type != "uri":
            continue
        spec = _string_value(n, src)
        if not spec or spec.startswith("dart:"):
            continue
        if spec.startswith("package:"):
            name, _, rest = spec[len("package:") :].partition("/")
            if name in pkgs:
                out.append(group.exact(posixpath.join(pkgs[name], "lib", rest)))
            continue
        out.append(group.exact(posixpath.join(posixpath.dirname(rel), spec)))
    return out


def haskell_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    """`import A.B.C` -> a file ending in A/B/C.hs (.lhs, .hsc) under any source
    directory (cabal's hs-source-dirs; the suffix accepts any)."""
    out = []
    for n in _walk(_ts_tree("haskell", src)):
        if n.type != "import":
            continue
        mod = next((c for c in n.children if c.type == "module"), None)
        if mod is not None:
            tail = _text(mod, src).replace(".", "/")
            out.append(set().union(*(group.suffix(tail + e) for e in (".hs", ".lhs", ".hsc"))))
    return out


_SHELL_EXPANSIONS = ("simple_expansion", "expansion", "command_substitution")


def shell_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    """`source p` / `. p`: a literal path relative to the file's directory, else
    any file ending in it. A path behind a variable (`"$DIR/lib/x.sh"`) keeps its
    literal tail and matches by suffix -- the variable is configuration."""
    out = []
    for n in _walk(_ts_tree("bash", src)):
        if n.type != "command":
            continue
        name = next((c for c in n.children if c.type == "command_name"), None)
        if name is None or _text(name, src) not in ("source", "."):
            continue
        arg = next((c for c in n.children if c.type != "command_name"), None)
        if arg is None:
            continue
        leaves = list(_walk(arg))
        if any(x.type in _SHELL_EXPANSIONS for x in leaves):
            literal = "".join(_text(x, src) for x in leaves if x.type in ("string_content", "word") and x is not arg)
            tail = literal.strip("/").lstrip("./")
            if "/" in literal and tail:
                out.append(group.suffix(tail))
            continue
        spec = _string_value(arg, src) or _text(arg, src)
        if not spec or spec.startswith("-"):
            continue
        local = group.exact(posixpath.join(posixpath.dirname(rel), spec))
        out.append(local or group.suffix(spec.lstrip("./")))
    return out


def solidity_imports(src: bytes, rel: str, group: Group) -> list[set[str]]:
    """`import "./x.sol"` relative to the file; `"@scope/pkg/x.sol"` through a
    package.json in this repo named @scope/pkg (npm remapping), else from the
    project root; otherwise a dependency."""
    if "npm" not in group._cache:
        names = {}
        for pj in sorted(group.root.rglob("package.json")) if group.root is not None else []:
            if "node_modules" in pj.parts:
                continue
            try:
                name = json.loads(pj.read_text(encoding="utf-8", errors="replace")).get("name")
            except (OSError, ValueError, AttributeError):
                continue
            if isinstance(name, str):
                base = pj.parent.relative_to(group.root).as_posix()
                names[name] = "" if base == "." else base
        group._cache["npm"] = sorted(names.items(), key=lambda kv: -len(kv[0]))
    out = []
    for n in _walk(_ts_tree("solidity", src)):
        if n.type != "import_directive":
            continue
        lit = next((c for c in n.children if c.type == "string"), None)
        spec = _string_value(lit, src) if lit is not None else None
        if not spec:
            continue
        if spec.startswith(("./", "../")):
            out.append(group.exact(posixpath.join(posixpath.dirname(rel), spec)))
            continue
        pkg = next(((nm, d) for nm, d in group._cache["npm"] if spec.startswith(nm + "/")), None)
        if pkg is not None:
            out.append(group.exact(posixpath.join(pkg[1], spec[len(pkg[0]) + 1 :])))
        else:
            out.append(group.exact(spec))
    return out


EXTRACTORS: dict[str, Callable[[bytes, str, Group], list[set[str]]]] = {
    "python": python_imports,
    "go": go_imports,
    "c": c_imports("c"),
    "cpp": c_imports("cpp"),
    "java": java_imports,
    "javascript": js_imports("javascript"),
    "typescript": js_imports("typescript"),
    "lua": lua_imports,
    "php": php_imports,
    "zig": zig_imports,
    "ruby": ruby_imports,
    "rust": rust_imports,
    "perl": perl_imports,
    "objective-c": c_imports("objc"),
    "dart": dart_imports,
    "kotlin": kotlin_imports,
    "scala": scala_imports,
    "haskell": haskell_imports,
    "shell": shell_imports,
    "solidity": solidity_imports,
}


# ----------------------------------------------------------------------------- engine side

_SCAN = (
    "import sys, gitgalaxy\n"
    "from pathlib import Path\n"
    "root = Path(sys.argv[1]).resolve()\n"
    "if Path(gitgalaxy.__file__).resolve().parents[1] != root:\n"
    "    raise SystemExit(f'engine import resolved to {gitgalaxy.__file__}, not {root}')\n"
    "from gitgalaxy.galaxyscope import main\n"
    "sys.argv = ['galaxyscope', sys.argv[2], '--output', sys.argv[3], '--db-only']\n"
    "main()\n"
)


def scan_group(group_dir: Path, out_dir: Path) -> tuple[dict[str, str], set[tuple[str, str]], dict[str, list[str]]]:
    """(file path -> engine language, {(src, dst) import edges}, file path -> raw import tokens)
    for one group, scanned in a subprocess pinned to THIS checkout (the console-script trap)."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(PYTHONPATH=str(REPO_ROOT), GITGALAXY_DISABLE_GIT_HISTORY="1")
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-c", _SCAN, str(REPO_ROOT), str(group_dir), str(out_dir / "g.json")],
        env=env,
        capture_output=True,
        text=True,
    )
    dbs = list(out_dir.glob("*_master.db"))
    if proc.returncode != 0 or not dbs:
        raise RuntimeError(f"scan of {group_dir} failed ({proc.returncode}): {proc.stderr[-800:]}")
    conn = sqlite3.connect(dbs[0])
    try:
        langs = {p: str(lang or "").lower() for p, lang in conn.execute("SELECT file_path, language FROM file_data")}
        ids = {i: p for i, p in conn.execute("SELECT id, file_path FROM file_data")}
        edges = {
            (ids[s], ids[d])
            for s, d in conn.execute("SELECT src_file_id, dst_file_id FROM edge_data WHERE edge_kind = 'import'")
            if s in ids and d in ids and s != d
        }
        raw = {p: _tokens(t) for p, t in conn.execute("SELECT file_path, raw_imports FROM file_data")}
    finally:
        conn.close()
    return langs, edges, raw


def _tokens(raw: Optional[str]) -> list[str]:
    """The file's pre-resolution import tokens (#3220), flattened to strings."""
    try:
        items = json.loads(raw or "[]")
    except ValueError:
        return []
    return [str(x[0] if isinstance(x, list) and x else x) for x in items]


# ----------------------------------------------------------------------------- disagreement causes


def _stem(path: str) -> str:
    """`src/a/Foo.test.ts` -> `foo`: the bare name a token would spell."""
    return path.rsplit("/", 1)[-1].split(".", 1)[0].lower()


def _token_tail(token: str) -> str:
    """The last name a raw import token spells: `a.b.Foo` / `../foo.js` / `A\\B` / `pkg:x/y.dart` -> its stem."""
    t = token.strip().strip("'\"<>")
    for sep in ("\\", "::", ":"):
        t = t.replace(sep, "/")
    t = t.rstrip("/").rsplit("/", 1)[-1]
    parts = [p for p in t.split(".") if p]
    # `a.b.Foo` / `..a.foo` name Foo / foo; `foo.js` / `foo.h` name foo -- a source-file suffix.
    if len(parts) > 1 and parts[-1].lower() in _SOURCE_SUFFIXES:
        parts = parts[:-1]
    return (parts[-1] if parts else t).lower()


_SOURCE_SUFFIXES = frozenset(
    "py pyi js mjs cjs jsx ts tsx mts cts h hh hpp hxx c cc cpp cxx m mm rb rs go php lua pl pm "
    "dart kt kts scala hs sh bash sol zig java json".split()
)


def _names_declaration_in(token: str, path: str) -> bool:
    """A dotted import of a DECLARATION (`com.x.metadata.isPrimary`, kotlin/scala/java) whose
    package path is the target file's directory: captured, but the name is not the file's."""
    parts = [p for p in token.strip().split(".") if p and p != "_"]
    if len(parts) < 3:
        return False
    package = parts[:-1]
    dirs = path.rsplit("/", 1)[0].split("/") if "/" in path else []
    return len(dirs) >= len(package) and dirs[-len(package) :] == package


_TEST_PATH = re.compile(r"(^|/)(tests?|spec|__tests__|testdata|fixtures?)(/|$)|[._-](test|spec)\.", re.I)


def import_cause(kind: str, truth: set[str], union: set[str], tokens: list[str], has_edges: bool) -> str:
    """Why one side has this import and the other does not, by LAYER: capture (no engine
    token), resolution (a token, but no edge or the wrong file), or the truth side (a
    multi-file answer, or no import the parser can see). Leads, not verdicts.

    kind "fn": `truth` is one import statement's resolvable file set the engine hit none of.
    kind "fp": `truth` is {the engine's wrong target}; `union` is every file the parser
    resolved for that importer."""
    tails = {_token_tail(t) for t in tokens}
    if kind == "fn":
        if len(truth) > 1:
            return "fn:truth-names-several-files"
        if any(_stem(p) in tails for p in truth):
            return "fn:token-unresolved"
        if any(_names_declaration_in(t, p) for t in tokens for p in truth):
            return "fn:declaration-unresolved"
        return "fn:capture-missed" if has_edges or tokens else "fn:capture-none-in-file"
    (dst,) = truth
    if not union:
        return "fp:truth-sees-no-import-in-file"
    if _stem(dst) in {_stem(p) for p in union}:
        return "fp:same-name-other-path"
    if _TEST_PATH.search(dst):
        return "fp:target-is-test-file"
    return "fp:target-not-imported"


# ----------------------------------------------------------------------------- scoring


def score_group(
    group_dir: Path,
    langs: dict[str, str],
    edges: set[tuple[str, str]],
    wanted: tuple[str, ...],
    raw: Optional[dict[str, list[str]]] = None,
) -> dict[str, dict[str, Any]]:
    group = Group(langs, group_dir)
    per: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {"files": 0, "imports": 0, "found": 0, "edges": 0, "correct": 0, "fp": [], "fn": [], "causes": []}
    )
    out_edges: dict[str, set[str]] = collections.defaultdict(set)
    for s, d in edges:
        out_edges[s].add(d)
    for rel, lang in langs.items():
        if lang not in wanted or lang not in EXTRACTORS:
            continue
        try:
            src = (group_dir / rel).read_bytes()
            sets = [t - {rel} for t in EXTRACTORS[lang](src, rel, group)]
        except (OSError, RecursionError):
            continue
        r = per[lang]
        r["files"] += 1
        resolvable = [t for t in sets if t]
        mine = out_edges.get(rel, set())
        tokens = (raw or {}).get(rel, [])
        union = set().union(*resolvable) if resolvable else set()
        for t in resolvable:
            r["imports"] += 1
            if mine & t:
                r["found"] += 1
            else:
                edge = f"{rel} -> {sorted(t)[0]}" + (f" (+{len(t) - 1})" if len(t) > 1 else "")
                r["fn"].append(edge)
                r["causes"].append((import_cause("fn", t, union, tokens, bool(mine)), rel, edge))
        for d in mine:
            r["edges"] += 1
            if d in union:
                r["correct"] += 1
            else:
                r["fp"].append(f"{rel} -> {d}")
                r["causes"].append((import_cause("fp", {d}, union, tokens, True), rel, f"{rel} -> {d}"))
    return per


def load_manifest() -> list[dict[str, str]]:
    return list(json.loads(MANIFEST.read_text())["repos"])


def repo_dir(corpus: Path, entry: dict[str, str]) -> Path:
    return corpus / entry["repo"].replace("/", "__")


def fetch(corpus: Path, entries: list[dict[str, str]]) -> None:
    """Clone each pinned repo shallow at its commit (idempotent)."""
    for e in entries:
        d = repo_dir(corpus, e)
        head = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True)
        if head.returncode == 0 and head.stdout.strip() == e["commit"]:
            continue
        d.mkdir(parents=True, exist_ok=True)
        for cmd in (
            ["git", "-C", str(d), "init", "-q"],
            ["git", "-C", str(d), "fetch", "-q", "--depth", "1", f"https://github.com/{e['repo']}.git", e["commit"]],
            ["git", "-C", str(d), "checkout", "-q", "--force", "FETCH_HEAD"],
        ):
            subprocess.run(cmd, check=True)
        print(f"import_graph_accuracy: fetched {e['repo']}@{e['commit'][:12]}")


def measure(
    corpus: Path, langs: tuple[str, ...], jobs: int, samples: int, buckets: int = 0
) -> dict[str, dict[str, Any]]:
    entries = [e for e in load_manifest() if e["language"] in langs]
    missing = [e["repo"] for e in entries if not (repo_dir(corpus, e) / ".git").is_dir()]
    if missing:
        raise SystemExit(f"import_graph_accuracy: not fetched: {missing} -- run with --fetch")
    totals: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as tmp:

        def run(e: dict[str, str]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
            d = repo_dir(corpus, e)
            file_langs, edges, raw = scan_group(d, Path(tmp) / d.name)
            return e, score_group(d, file_langs, edges, (e["language"],), raw)

        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            for e, per in pool.map(run, entries):
                lang = e["language"]
                r = per.get(lang)
                if not r:
                    continue
                t = totals.setdefault(
                    lang,
                    {
                        "repos": [],
                        "files": 0,
                        "imports": 0,
                        "found": 0,
                        "edges": 0,
                        "correct": 0,
                        "fp": [],
                        "fn": [],
                        "causes": [],
                    },
                )
                t["repos"].append(e["repo"])
                for k in ("files", "imports", "found", "edges", "correct"):
                    t[k] += r[k]
                name = e["repo"].split("/")[1]
                t["fp"] += [f"{name}/{x}" for x in r["fp"]]
                t["fn"] += [f"{name}/{x}" for x in r["fn"]]
                t["causes"] += [(c, f"{name}/{rel}", f"{name}/{edge}") for c, rel, edge in r["causes"]]
    results = {}
    for lang in langs:
        t = totals.get(lang)
        if not t:
            continue
        results[lang] = {
            "repos": ", ".join(sorted(t["repos"])),
            "files": t["files"],
            "imports": t["imports"],
            "engine_edges": t["edges"],
            "precision_pct": round(100 * t["correct"] / t["edges"], 1) if t["edges"] else None,
            "recall_pct": round(100 * t["found"] / t["imports"], 1) if t["imports"] else None,
            "fp": t["edges"] - t["correct"],
            "fn": t["imports"] - t["found"],
            "sample_fp": sorted(t["fp"])[:samples],
            "sample_fn": sorted(t["fn"])[:samples],
            "correct": t["correct"],
            "found": t["found"],
        }
        if buckets:
            counts = collections.Counter(c for c, _, _ in t["causes"])
            examples: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
            for c, rel, edge in sorted(t["causes"]):
                if len(examples[c]) < buckets:
                    examples[c].append({"file_path": rel, "name": edge, "line": None, "text": ""})
            results[lang]["top_causes"] = [
                {"cause": c, "count": k, "examples": examples[c]} for c, k in counts.most_common()
            ]
    return results


def render(results: dict[str, dict[str, Any]]) -> str:
    def pct(v: Optional[float]) -> str:
        return "n/a" if v is None else f"{v}%"

    lines = [
        "| language | repos | files | resolvable imports | engine edges | precision | recall | FP | FN |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for lang, r in results.items():
        lines.append(
            f"| {lang} | {r['repos']} | {r['files']} | {r['imports']} | {r['engine_edges']} | "
            f"{pct(r['precision_pct'])} | {pct(r['recall_pct'])} | {r['fp']} | {r['fn']} |"
        )
    return "\n".join(lines)


def regressions(results: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for lang, base in baseline.items():
        cur = results.get(lang)
        if cur is None:
            out.append(f"{lang}: no longer measured (baseline had {base['imports']} resolvable imports)")
            continue
        if max(base.get("imports") or 0, base.get("engine_edges") or 0) < MIN_GATED_IMPORTS:
            continue
        out.extend(
            f"{lang}: {metric} {base[metric]} -> {cur.get(metric)}"
            for metric in ("precision_pct", "recall_pct")
            if base.get(metric) is not None and (cur.get(metric) or 0.0) < base[metric] - TOLERANCE_PP
        )
    return out


# The ledger plumbing is shared with call_graph_accuracy.py (graph_ledger.py, #3641):
# precision = correct edges / engine edges, recall = found imports / resolvable imports.
COUNTS = ("correct", "fp", "found", "fn")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("languages", nargs="*", help=f"default: {' '.join(LANGS)}")
    ap.add_argument("--samples", type=int, default=0, help="print N example FP/FN per language")
    ap.add_argument("--buckets", type=int, default=0, help="classify every FP/FN by cause, N examples each")
    ap.add_argument(
        "--ledger", action="store_true", help="merge the discrepancy shapes into the graph comparison ledger"
    )
    ap.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2))))
    ap.add_argument("--ci", action="store_true", help="fail on a drop beyond the baseline tolerance")
    ap.add_argument("--regenerate", action="store_true", help="rewrite the committed baseline")
    ap.add_argument("--fetch", action="store_true", help="clone the pinned repos first (idempotent)")
    ap.add_argument("--fetch-only", action="store_true", help="clone the pinned repos and stop")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--summary", metavar="PATH", help="append the markdown table here (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args(argv)
    langs = tuple(a.languages) or LANGS
    unknown = [lang for lang in langs if lang not in EXTRACTORS]
    if unknown:
        print(f"import_graph_accuracy: no parser rule for {unknown}")
        return 2
    if a.fetch or a.fetch_only:
        fetch(CORPUS, [e for e in load_manifest() if e["language"] in langs])
        if a.fetch_only:
            return 0
    buckets = max(a.buckets, gl.LEDGER_EXAMPLES) if a.ledger else a.buckets
    results = measure(CORPUS, langs, a.jobs, a.samples, buckets)
    table = render(results)
    print(table)
    if buckets:
        print(gl.render_causes(results, COUNTS))
        if a.ledger:
            if a.languages:
                print("import_graph_accuracy: --ledger merges every language; run it without a language list")
                return 2
            gl.merge(results, "import")
            print(f"\nimport_graph_accuracy: shapes merged into {gl.LEDGER.relative_to(REPO_ROOT)}")
        print("\n" + gl.render_validated(results, gl.validated(results, "import", COUNTS)))
    if a.samples:
        for lang, r in results.items():
            print(f"\n{lang}\n  FP: {r['sample_fp']}\n  FN: {r['sample_fn']}")
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write("### Import-graph accuracy (engine import edges vs parser imports)\n\n" + table + "\n\n")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2) + "\n")
    # #2682: an audit that measured nothing must not pass.
    measured = [lang for lang, r in results.items() if r["imports"] or r["engine_edges"]]
    if not measured:
        print("import_graph_accuracy: FAIL -- measured 0 languages (scan or corpus problem)")
        return 1
    stripped = {
        k: {m: v for m, v in r.items() if not m.startswith(("sample_", "top_")) and m not in ("correct", "found")}
        for k, r in results.items()
    }
    if a.regenerate:
        if a.languages:
            print("import_graph_accuracy: --regenerate rewrites every language; run it without a language list")
            return 2
        BASELINE.write_text(json.dumps(stripped, indent=2, sort_keys=True) + "\n")
        print(f"import_graph_accuracy: baseline rewritten -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0
    if a.ci:
        if not BASELINE.exists():
            print("import_graph_accuracy: no baseline; run --regenerate")
            return 1
        baseline = json.loads(BASELINE.read_text())
        if a.languages:
            baseline = {k: v for k, v in baseline.items() if k in langs}
        bad = regressions(stripped, baseline)
        if bad:
            print("import_graph_accuracy: REGRESSION\n  " + "\n  ".join(bad))
            return 1
        print(f"import_graph_accuracy: OK -- {len(measured)} language(s) measured, none dropped beyond tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
