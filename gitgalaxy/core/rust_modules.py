"""#4544: the file a Rust `use` path names, by the language's own module rules.

The generic name search read `use crate::render::bsp::Node` as a file called `Node`, so a
Rust crate's import graph was nearly empty (room4doom: 2,603 `use` lines, 336 edges). A Rust
path is resolved here the way rustc does it, as far as the scanned files can show:

* `crate::a::b` is module `a::b` of the importing file's crate; `self::` the importing
  file's own module; `super::` (repeatable) its parent.
* A module is a FILE by the conventional layout: `a::b` is `<crate dir>/a/b.rs` or
  `<crate dir>/a/b/mod.rs`, the crate dir being the crate root's directory (src/ for
  src/lib.rs and src/main.rs). A path names the deepest module that is a file; the
  rest is an item inside it (`crate::a::b::Node` -> a/b.rs).
* A first segment that is no keyword is a child module of the importing module (Rust 2018
  uniform paths) when one exists, else a crate: a dependency of the importing package
  (`[dependencies]`, `workspace = true` through `[workspace.dependencies]`, renames by
  key), the package's own library (bins, tests and examples use it by name) or any scanned
  package's library name, hyphens read as underscores. Anything else (std, crates.io)
  names no scanned file. A Rust 2015 package (a manifest with no `edition`) also reads it
  crate-relative.
* An item a module only re-exports (`pub use self::x::Thing;`, `pub use x::*;`) is followed
  to the module that defines it, at most two hops.

Manifests are read with a small line reader, never `tomllib`: Python 3.10 has none, and
the graph must not depend on the interpreter. It reads only the keys named above.
"""

from __future__ import annotations

import os
import posixpath
import re
from typing import Any

from gitgalaxy.core.source_text import read_source

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_ROOT_DIRS = frozenset({"tests", "examples", "benches"})
_MAX_HOPS = 2
_MAX_SEGMENTS = 32
_MAX_MANIFEST_BYTES = 1_000_000
_MAX_STATEMENT_LINES = 64

_HEADER = re.compile(r"\[\[?[ \t]*([^\[\]]{1,200}?)[ \t]*\]\]?")
_KEY_VALUE = re.compile(r"([A-Za-z0-9_\-.\"' ]{1,200}?)[ \t]*=[ \t]*(.*)", re.S)
_STRING = re.compile(r"\"((?:[^\"\\\n]|\\.){0,1000})\"|'([^'\n]{0,1000})'")
_INLINE_PAIR = re.compile(
    r"([A-Za-z0-9_\-]{1,100})[ \t]*=[ \t]*(?:\"((?:[^\"\\\n]|\\.){0,1000})\"|'([^'\n]{0,1000})'|(true|false))"
)


def _strip_comment(line: str) -> str:
    """`line` without a `#` comment that is outside a string."""
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"':
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return line[:i]
        i += 1
    return line


def _unquote(key: str) -> str:
    return ".".join(part.strip().strip("\"'") for part in key.split("."))


def parse_cargo_manifest(text: str) -> list[tuple[str, dict[str, Any]]]:
    """The tables of a Cargo.toml, in order: (header, {key: value}). A value is a string,
    True/False, a dict for an inline table (its string and boolean keys only) or None for
    anything else (arrays, numbers). `[[bin]]` tables repeat their header."""
    tables: list[tuple[str, dict[str, Any]]] = [("", {})]
    statement = ""
    lines = 0
    for raw in text.splitlines():
        line = _strip_comment(raw).strip()
        if not statement and not line:
            continue
        statement = f"{statement} {line}" if statement else line
        lines += 1
        bare = _STRING.sub('""', statement)
        if (
            bare.count("[") + bare.count("{") > bare.count("]") + bare.count("}")
            and lines < _MAX_STATEMENT_LINES
            and not _HEADER.fullmatch(statement)
        ):
            continue  # a value that continues on the next line
        header = _HEADER.fullmatch(statement)
        if header:
            tables.append((_unquote(header.group(1)), {}))
        else:
            kv = _KEY_VALUE.fullmatch(statement)
            if kv:
                tables[-1][1][_unquote(kv.group(1))] = _value(kv.group(2).strip())
        statement, lines = "", 0
    return tables


def _value(text: str) -> Any:
    if text in ("true", "false"):
        return text == "true"
    string = _STRING.match(text)
    if string and string.end() == len(text):
        return string.group(1) if string.group(1) is not None else string.group(2)
    if text.startswith("{"):
        return {
            m.group(1): (
                m.group(2) if m.group(2) is not None else m.group(3) if m.group(3) is not None else m.group(4) == "true"
            )
            for m in _INLINE_PAIR.finditer(text)
        }
    return None


def crate_ident(name: str) -> str:
    """A crate name as Rust code spells it: hyphens are underscores."""
    return name.replace("-", "_")


class Manifest:
    """One Cargo.toml: its directory (scan-relative) and the keys module resolution reads."""

    __slots__ = (
        "bins",
        "build",
        "deps",
        "dir",
        "edition_2015",
        "is_package",
        "is_workspace",
        "lib_name",
        "lib_path",
        "workspace_deps",
    )

    def __init__(self, directory: str, tables: list[tuple[str, dict[str, Any]]]) -> None:
        self.dir = directory
        self.is_package = False
        self.is_workspace = False
        self.lib_name = ""
        self.lib_path = "src/lib.rs"
        self.bins: list[str] = []
        self.build: str | None = None
        self.edition_2015 = False
        # extern name -> (path relative to this manifest | None, True when `workspace = true`)
        self.deps: dict[str, tuple[str | None, bool]] = {}
        self.workspace_deps: dict[str, str] = {}
        package_name = ""
        for header, keys in tables:
            if header == "package":
                self.is_package = True
                name = keys.get("name")
                package_name = name if isinstance(name, str) else ""
                self.edition_2015 = "edition" not in keys and "edition.workspace" not in keys
                if isinstance(keys.get("build"), str):
                    self.build = keys["build"]
            elif header == "lib":
                if isinstance(keys.get("name"), str):
                    self.lib_name = keys["name"]
                if isinstance(keys.get("path"), str):
                    self.lib_path = keys["path"]
            elif header == "bin":
                if isinstance(keys.get("path"), str):
                    self.bins.append(keys["path"])
            elif header == "workspace":
                self.is_workspace = True
            elif header == "workspace.dependencies":
                self.is_workspace = True
                for key, value in keys.items():
                    if isinstance(value, dict) and isinstance(value.get("path"), str):
                        self.workspace_deps[crate_ident(key)] = value["path"]
            elif header.endswith("dependencies"):
                for key, value in keys.items():
                    name, _, field = key.partition(".")
                    if field == "workspace" and value is True:
                        self.deps.setdefault(crate_ident(name), (None, True))
                    elif field == "path" and isinstance(value, str):
                        self.deps[crate_ident(name)] = (value, False)
                    elif not field and isinstance(value, dict):
                        if isinstance(value.get("path"), str):
                            self.deps[crate_ident(name)] = (value["path"], False)
                        elif value.get("workspace") is True:
                            self.deps.setdefault(crate_ident(name), (None, True))
            elif ".dependencies." in f".{header}" or header.startswith("dependencies."):
                # `[dependencies.foo]` / `[target.'cfg(x)'.dependencies.foo]`
                name = crate_ident(header.rsplit(".", 1)[-1])
                if isinstance(keys.get("path"), str):
                    self.deps[name] = (keys["path"], False)
                elif keys.get("workspace") is True:
                    self.deps.setdefault(name, (None, True))
        self.lib_name = crate_ident(self.lib_name or package_name)
        if self.build is None and self.is_package:
            self.build = "build.rs"

    def rel(self, path: str) -> str:
        """`path` (relative to this manifest) as a normalized scan-relative path."""
        return posixpath.normpath(posixpath.join(self.dir, path)) if self.dir else posixpath.normpath(path)


def split_path(token: str) -> list[str] | None:
    """`crate::a::b` -> ["crate", "a", "b"]; a leading `::` is an empty first segment, a glob
    keeps its `*`. None for anything that is not a Rust path."""
    segments = [s.strip() for s in token.strip().split("::")]
    if not segments or len(segments) > _MAX_SEGMENTS:
        return None
    out: list[str] = []
    for i, seg in enumerate(segments):
        if seg.startswith("r#"):
            seg = seg[2:]
        leading = i == 0 and seg == "" and len(segments) > 1  # `::crate_name`
        glob = seg == "*" and i == len(segments) - 1 and i > 0
        if not (leading or glob or _IDENT.fullmatch(seg)):
            return None
        out.append(seg)
    return out


class RustModules:
    """Resolves Rust import tokens over one scan's files (see the module docstring)."""

    def __init__(self, files: list[dict[str, Any]], by_norm_path: dict[str, str], root: str | None) -> None:
        self._by_norm_path = by_norm_path
        self._root = root
        self._imports: dict[str, list[str]] = {}
        self._declared: dict[str, set[str]] = {}
        for f in files:
            if str(f.get("lang_id", "")).lower() != "rust" or not f.get("path"):
                continue
            path = f["path"].replace("\\", "/")
            self._imports[path] = sorted(
                (imp[0] if isinstance(imp, tuple) else imp)
                for imp in (f.get("raw_imports") or ())
                if isinstance(imp, (str, tuple))
            )
            names = self._declared.setdefault(path, set())
            for unit in (f.get("functions") or []) + (f.get("classes") or []):
                name = unit.get("name") if isinstance(unit, dict) else None
                if isinstance(name, str):
                    names.add(name.rsplit("::", 1)[-1].rsplit(".", 1)[-1])
        self._manifests: dict[str, Manifest | None] = {}
        self._package_of_dir: dict[str, Manifest | None] = {}
        self._workspace_of: dict[str, Manifest | None] = {}
        self._contexts: dict[str, tuple[str, str | None, list[str], Manifest | None]] = {}
        self._libs: dict[str, Manifest] | None = None
        self._resolved: dict[tuple[str, str, int], str | None] = {}
        self._followed: dict[tuple[str, str, int], str | None] = {}

    # ----- manifests -----------------------------------------------------------------
    def _manifest(self, directory: str) -> Manifest | None:
        """The Cargo.toml in scan-relative `directory`, parsed once, or None."""
        if directory in self._manifests:
            return self._manifests[directory]
        found: Manifest | None = None
        if self._root is not None:
            path = os.path.join(self._root, directory, "Cargo.toml")
            try:
                if os.path.isfile(path) and os.path.getsize(path) <= _MAX_MANIFEST_BYTES:
                    found = Manifest(directory, parse_cargo_manifest(read_source(path).text))
            except (OSError, UnicodeError, ValueError):
                found = None
        self._manifests[directory] = found
        return found

    def _package_of(self, directory: str) -> Manifest | None:
        """The package whose Cargo.toml is nearest at or above `directory`."""
        walked: list[str] = []
        current = directory
        found: Manifest | None = None
        while True:
            if current in self._package_of_dir:
                found = self._package_of_dir[current]
                break
            walked.append(current)
            manifest = self._manifest(current)
            if manifest is not None and manifest.is_package:
                found = manifest
                break
            if not current:
                break
            current = posixpath.dirname(current)
        for d in walked:
            self._package_of_dir[d] = found
        return found

    def _workspace(self, package: Manifest) -> Manifest | None:
        """The workspace manifest at or above `package`."""
        if package.dir not in self._workspace_of:
            current: str | None = package.dir
            found: Manifest | None = None
            while current is not None:
                manifest = self._manifest(current)
                if manifest is not None and manifest.is_workspace:
                    found = manifest
                    break
                current = posixpath.dirname(current) if current else None
            self._workspace_of[package.dir] = found
        return self._workspace_of[package.dir]

    def _lib_root(self, package: Manifest) -> str | None:
        return self._by_norm_path.get(package.rel(package.lib_path))

    def _scanned_libs(self) -> dict[str, Manifest]:
        """Library name -> package, for every package that owns a scanned Rust file."""
        if self._libs is None:
            libs: dict[str, Manifest] = {}
            for path in sorted(self._imports):
                package = self._package_of(posixpath.dirname(path))
                if package is not None and package.lib_name and self._lib_root(package) is not None:
                    libs.setdefault(package.lib_name, package)
            self._libs = libs
        return self._libs

    def _extern(self, name: str, package: Manifest | None) -> tuple[str, str] | None:
        """(crate dir, lib root file) of the crate `name` the importing package can use."""
        target: Manifest | None = None
        if package is not None:
            dep = package.deps.get(name)
            if dep is not None:
                rel, inherited = dep
                if inherited:
                    workspace = self._workspace(package)
                    if workspace is not None and name in workspace.workspace_deps:
                        target = self._manifest(workspace.rel(workspace.workspace_deps[name]))
                elif rel is not None:
                    target = self._manifest(package.rel(rel))
            if target is None and package.lib_name == name:
                target = package
        if target is None:
            target = self._scanned_libs().get(name)
        if target is None or not target.is_package:
            return None
        lib = self._lib_root(target)
        return (posixpath.dirname(lib.replace("\\", "/")), lib) if lib is not None else None

    # ----- the importing file's place in its crate --------------------------------------
    def _context(self, path: str) -> tuple[str, str | None, list[str], Manifest | None]:
        """(crate dir, crate root file or None, module path, package) of the file `path`."""
        cached = self._contexts.get(path)
        if cached is not None:
            return cached
        directory = posixpath.dirname(path)
        package = self._package_of(directory)
        crate_dir, root = self._crate_of(path, directory, package)
        if root == path:
            module: list[str] = []
        else:
            rel = path[len(crate_dir) + 1 :] if crate_dir else path
            module = [p for p in posixpath.splitext(rel)[0].split("/") if p]
            if module and module[-1] == "mod":
                module.pop()
        result = (crate_dir, root, module, package)
        self._contexts[path] = result
        return result

    def _crate_of(self, path: str, directory: str, package: Manifest | None) -> tuple[str, str | None]:
        scanned = self._by_norm_path
        if package is not None:
            roots = [package.rel(package.lib_path), package.rel("src/main.rs")]
            roots += [package.rel(b) for b in package.bins]
            if package.build:
                roots.append(package.rel(package.build))
            roots = [r for r in roots if r in scanned]
            if path in roots:
                return directory, scanned[path]
            base = package.dir
            parts = (path[len(base) + 1 :] if base else path).split("/")
            if len(parts) >= 3 and parts[0] == "src" and parts[1] == "bin":
                if len(parts) == 3:
                    return directory, scanned[path]
                bin_dir = posixpath.join(base, "src", "bin", parts[2])
                return bin_dir, scanned.get(posixpath.join(bin_dir, "main.rs"))
            if len(parts) >= 2 and parts[0] in _ROOT_DIRS:
                if len(parts) == 2:
                    return directory, scanned[path]
                sub = posixpath.join(base, parts[0], parts[1])
                if posixpath.join(sub, "main.rs") in scanned:
                    return sub, scanned[posixpath.join(sub, "main.rs")]
                return posixpath.join(base, parts[0]), None
            best: str | None = None
            for r in roots:
                rd = posixpath.dirname(r)
                if (not rd or path.startswith(rd + "/")) and (best is None or len(rd) > len(posixpath.dirname(best))):
                    best = r
            if best is not None:
                return posixpath.dirname(best), scanned[best]
            src = posixpath.join(base, "src")
            return (src if path.startswith(src + "/") else directory), None
        # No manifest: the nearest directory holding a lib.rs / main.rs is the crate's.
        current = directory
        while True:
            for name in ("lib.rs", "main.rs"):
                candidate = posixpath.join(current, name)
                if candidate in scanned:
                    return current, scanned[candidate]
            if not current:
                return directory, None
            current = posixpath.dirname(current)

    def _module_file(self, crate_dir: str, module: list[str], root: str | None) -> str | None:
        if not module:
            return root
        stem = posixpath.join(crate_dir, *module)
        return self._by_norm_path.get(stem + ".rs") or self._by_norm_path.get(stem + "/mod.rs")

    # ----- resolution --------------------------------------------------------------------
    def resolve(self, token: str, importer: str, hops: int = 0) -> str | None:
        """The scanned file the Rust path `token` in `importer` names, or None. Memoized:
        a re-export hop resolves the re-exporting module's own tokens, the same ones for
        every importer, so a crate root's long `pub use` list is read once."""
        key = (token, importer, hops)
        if key not in self._resolved:
            self._resolved[key] = self._resolve(token, importer.replace("\\", "/"), hops)
        return self._resolved[key]

    def _resolve(self, token: str, importer: str, hops: int) -> str | None:
        segments = split_path(token)
        if not segments:
            return None
        if segments[-1] == "*":
            segments = segments[:-1]
        crate_dir, root, module, package = self._context(importer)
        head = segments[0]
        if head == "":
            if package is not None and package.edition_2015:
                return self._walk(crate_dir, root, [], segments[1:], hops)
            return self._in_crate(segments[1:], package, hops)
        if head == "crate":
            return self._walk(crate_dir, root, [], segments[1:], hops)
        if head == "self":
            return self._walk(crate_dir, root, module, segments[1:], hops)
        if head == "super":
            n = 0
            while n < len(segments) and segments[n] == "super":
                n += 1
            if n > len(module):
                return None
            return self._walk(crate_dir, root, module[: len(module) - n], segments[n:], hops)
        if self._module_file(crate_dir, [*module, head], root) is not None:
            return self._walk(crate_dir, root, module, segments, hops)
        hit = self._in_crate(segments, package, hops)
        if hit is None and package is not None and package.edition_2015:
            return self._walk(crate_dir, root, [], segments, hops)
        return hit

    def _in_crate(self, segments: list[str], package: Manifest | None, hops: int) -> str | None:
        """`other_crate::a::b`: module `a::b` of a scanned crate the package can name."""
        if not segments:
            return None
        crate = self._extern(segments[0], package)
        if crate is None:
            return None
        return self._walk(crate[0], crate[1], [], segments[1:], hops)

    def _walk(self, crate_dir: str, root: str | None, base: list[str], rest: list[str], hops: int) -> str | None:
        """The deepest module of `base + rest` that is a file; an item below it may be
        re-exported there from the module that defines it."""
        path = base + rest
        for k in range(len(path), -1, -1):
            hit = self._module_file(crate_dir, path[:k], root)
            if hit is not None:
                break
        else:
            return None
        if k < len(path) and hops < _MAX_HOPS:
            followed = self._reexport(hit, path[k], hops)
            if followed is not None:
                return followed
        return hit

    def _reexport(self, module_file: str, name: str, hops: int) -> str | None:
        """The file that defines `name` when `module_file` only brings it into scope (a
        `use` whose last segment is `name`, or the one glob that can supply it)."""
        key = (module_file, name, hops)
        if key not in self._followed:
            self._followed[key] = self._follow(module_file, name, hops)
        return self._followed[key]

    def _follow(self, module_file: str, name: str, hops: int) -> str | None:
        if name in self._declared.get(module_file, ()):
            return None
        tokens = [t for t in self._imports.get(module_file, ()) if not t.startswith(".")]
        for token in tokens:
            if token.rsplit("::", 1)[-1].strip() == name:
                hit = self.resolve(token, module_file, hops + 1)
                if hit is not None and hit != module_file:
                    return hit
        candidates: list[str] = []
        for token in tokens:
            if token.rstrip().endswith("*"):
                hit = self.resolve(token, module_file, hops + 1)
                if hit is not None and hit != module_file and hit not in candidates:
                    candidates.append(hit)
        if len(candidates) == 1:
            return candidates[0]
        declaring = [c for c in candidates if name in self._declared.get(c, ())]
        return declaring[0] if len(declaring) == 1 else None


# ----- inline modules (#4544) -------------------------------------------------------------
# `#[cfg(test)] mod tests { use super::*; }` names the FILE's own module, not its parent: a
# `self::` / `super::` path inside an inline `mod name { ... }` is relative to that inline
# module. The extractor rewrites such a path relative to the file (`rescope_to_file`) so the
# resolver, which knows files only, reads it right. String and char literals are blanked
# before braces are matched; comments are already gone from the code stream.
_LITERAL = re.compile(
    r"b?r(#{0,8})\"[\s\S]*?\"\1"
    r"|b?\"(?:[^\"\\]|\\[\s\S])*\""
    r"|b?'(?:[^'\\\n]|\\(?:u\{[0-9a-fA-F]{1,6}\}|x[0-9a-fA-F]{2}|[^\n]))'"
)
_INLINE_MOD = re.compile(r"\bmod[ \t\n]+(?:r#)?([A-Za-z_][A-Za-z0-9_]{0,127})[ \t\n]*\{")


def inline_module_spans(text: str) -> list[tuple[int, int, str]]:
    """(open brace, close brace, name) of every inline `mod name { ... }` in `text`."""
    if "mod" not in text:
        return []
    blank = _LITERAL.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)
    opens = {m.end() - 1: m.group(1) for m in _INLINE_MOD.finditer(blank)}
    if not opens:
        return []
    spans: list[tuple[int, int, str]] = []
    stack: list[int] = []
    for i, ch in enumerate(blank):
        if ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            start = stack.pop()
            if start in opens:
                spans.append((start, i, opens[start]))
    # unbalanced: the module runs to the end of the file
    spans.extend((start, len(blank), opens[start]) for start in stack if start in opens)
    spans.sort()
    return spans


def enclosing_modules(spans: list[tuple[int, int, str]], position: int) -> list[str]:
    """The inline modules around `position`, outermost first."""
    return [name for start, end, name in spans if start < position < end]


def rescope_to_file(token: str, inline_path: list[str]) -> str:
    """A `self::` / `super::` path written inside inline modules `inline_path`, relative to
    the file's own module instead."""
    if not inline_path:
        return token
    segments = [s.strip() for s in token.split("::")]
    if segments[0] == "self":
        return "::".join(["self", *inline_path, *segments[1:]])
    if segments[0] != "super":
        return token
    k = 0
    while k < len(segments) and segments[k] == "super":
        k += 1
    n = len(inline_path)
    if k <= n:
        return "::".join(["self", *inline_path[: n - k], *segments[k:]])
    return "::".join(["super"] * (k - n) + segments[k:])
