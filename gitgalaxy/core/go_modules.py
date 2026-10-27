"""#3798: the file a Go import path names, by Go's own module rule.

The generic name search read `import "net/http"` as a file called `http` (any `http.go`
in the repo got an edge from every importer of the standard library), and an import of a
package inside a NESTED module found no edge at all. Go resolves an import path through
`go.mod`:

* A path is inside a module when it is the module path or starts with `<module>/`; the
  rest of the path is the package's directory under the module's own directory. The
  longest matching module path wins (a nested module shadows its parent).
* A path inside no scanned module is the standard library or another module: it names no
  scanned file, so it draws no edge (never the name search).
* A package is a DIRECTORY, so an import depends on the package, not on one of its files.
  The edge goes to one representative non-test file of it: `<dir>/<dirname>.go`, else
  `doc.go`, else the first by name (stable across scans). Every file of the directory is a
  correct target, so the choice never invents a dependency.

* `replace X => ../local` (in `go.mod`, or in `go.work`, which applies workspace-wide) maps
  the import path `X` to the local directory, relative to the file that declares it. A
  replacement outside the scan, or to another module version (`=> Y v1.2`), names no file.
  `go.work` `use ./dir` needs no reading: the module in `dir` is found through its own
  `go.mod` like any other.

`go.mod` / `go.work` are not scanned source files, so they are read from disk, only in
directories that hold a scanned `.go` file or sit above one, with a small line reader
(`module` and `replace` lines only).
`vendor/` and `testdata/` modules are skipped.
"""

from __future__ import annotations

import os
import posixpath
import re
from typing import Any

from gitgalaxy.core.source_text import read_source

_MAX_MANIFEST_BYTES = 1_000_000
_MODULE_LINE = re.compile(
    r"^[ \t]{0,16}module[ \t]{1,16}(?:\"([^\"\n]{1,512})\"|`([^`\n]{1,512})`|([^\s/][^\s]{0,511}))", re.M
)
_REPLACE_LINE = re.compile(
    r"^[ \t]{0,16}(?:replace[ \t]{1,16})?(\S{1,512})(?:[ \t]{1,16}v\S{1,128})?[ \t]{0,16}=>[ \t]{0,16}(\S{1,512})", re.M
)
_REPLACE_BLOCK = re.compile(r"^[ \t]{0,16}replace[ \t]{0,16}\(([^)]{0,200000})\)", re.M)
_REPLACE_ONE = re.compile(r"^[ \t]{0,16}replace[ \t]{1,16}(?!\()[^\n]{1,1200}", re.M)
_SKIPPED_DIRS = frozenset({"vendor", "testdata"})


def parse_go_module(text: str) -> str | None:
    """The module path a go.mod declares, or None."""
    m = _MODULE_LINE.search(text)
    return (m.group(1) or m.group(2) or m.group(3)) if m else None


def parse_go_replaces(text: str) -> list[tuple[str, str]]:
    """(module path, local directory as written) for each `replace X => ./dir` / `../dir`."""
    bodies = [m.group(1) for m in _REPLACE_BLOCK.finditer(text)] + [m.group(0) for m in _REPLACE_ONE.finditer(text)]
    out = []
    for body in bodies:
        for m in _REPLACE_LINE.finditer(body):
            old, new = m.group(1).strip('"`'), m.group(2).strip('"`')
            if new.split("/")[0] in (".", "..") and old:
                out.append((old, new))
    return out


class GoModules:
    """Resolves Go import paths over one scan's files (see the module docstring)."""

    def __init__(self, files: list[dict[str, Any]], by_norm_path: dict[str, str], root: str | None) -> None:
        self._by_norm_path = by_norm_path
        self._by_dir: dict[str, list[str]] = {}
        for f in files:
            if str(f.get("lang_id", "")).lower() != "go" or not f.get("path"):
                continue
            path = f["path"].replace("\\", "/")
            self._by_dir.setdefault(posixpath.dirname(path), []).append(f["path"])
        # (module path, scan-relative directory), longest module path first
        self._modules = self._read_modules(root)

    def _read_modules(self, root: str | None) -> list[tuple[str, str]]:
        if root is None:
            return []
        dirs: set[str] = set()
        for d in self._by_dir:
            while True:
                dirs.add(d)
                if not d:
                    break
                d = posixpath.dirname(d)
        found = []
        for d in sorted(dirs):
            if _SKIPPED_DIRS & set(d.split("/")):
                continue
            for name in ("go.mod", "go.work"):
                text = self._read_manifest(os.path.join(root, d, name))
                if text is None:
                    continue
                module = parse_go_module(text) if name == "go.mod" else None
                if module:
                    found.append((module, d))
                for old, new in parse_go_replaces(text):
                    target = posixpath.normpath(posixpath.join(d, new))
                    if target == ".." or target.startswith("../"):
                        continue  # outside the scan: names no file
                    found.append((old, "" if target == "." else target))
        return sorted(set(found), key=lambda m: (-len(m[0]), m[1]))

    @staticmethod
    def _read_manifest(path: str) -> str | None:
        try:
            if not os.path.isfile(path) or os.path.getsize(path) > _MAX_MANIFEST_BYTES:
                return None
            return read_source(path).text
        except (OSError, UnicodeError, ValueError):
            return None

    def resolve(self, import_path: str) -> str | None:
        """The file of the package `import_path` names, or None."""
        path = import_path.strip().strip('"`')
        for module, mdir in self._modules:
            if path == module or path.startswith(module + "/"):
                rest = path[len(module) :].lstrip("/")
                directory = posixpath.normpath(posixpath.join(mdir, rest)) if mdir or rest else ""
                return self._package_file("" if directory == "." else directory)
        return None

    def _package_file(self, directory: str) -> str | None:
        members = [p for p in self._by_dir.get(directory, ()) if not p.endswith("_test.go")]
        if not members:
            return None
        named = [p for p in members if posixpath.basename(p) == (posixpath.basename(directory) or "") + ".go"]
        docs = [p for p in members if posixpath.basename(p) == "doc.go"]
        return named[0] if named else docs[0] if docs else min(members)
