"""#3789: a JS/TS package importing ITSELF by its published name (`from "zod/v4"` inside zod).

The import graph treats a bare specifier as an npm package outside the repository, so a
package's own tests, examples and docs, which import it by name, drew no edge to its source.
Node resolves that spelling through the nearest `package.json`: its `name`, then its `exports`
map (the "self-referencing a package using its name" rule). This module reads exactly that and
nothing more: the nearest package.json's `name`, and the file its `exports` (or, with none,
`main` / `module` / the subpath itself) declares for the subpath. It guesses nothing beyond what
the manifest says: a specifier naming another package, a subpath the manifest does not export,
or a target that is not a scanned file resolves to nothing.

Workspace packages (one package importing a SIBLING by name) are a different lookup and are
not handled here.
"""

import json
import os
import posixpath
from collections.abc import Iterator
from typing import Any, Optional

_MAX_MANIFEST_BYTES = 1_000_000
_MAX_DEPTH = 6  # nesting of `exports` conditions followed
_MAX_TARGETS = 24  # candidate files tried per specifier


class Package:
    """One package.json: where it lives, its name and the fields that map a subpath to a file."""

    __slots__ = ("dir", "exports", "has_exports", "main", "name")

    def __init__(self, directory: str, manifest: dict[str, Any]) -> None:
        self.dir = directory
        name = manifest.get("name")
        self.name = name if isinstance(name, str) else ""
        self.has_exports = "exports" in manifest
        self.exports = manifest.get("exports")
        self.main = [v for v in (manifest.get("module"), manifest.get("main")) if isinstance(v, str) and v]


def owning_package(root: str, directory: str, cache: dict[str, Optional[Package]]) -> Optional[Package]:
    """The package whose package.json is nearest at or above `directory` (a scan-relative,
    slash-separated path), or None. Parsed once per directory, so the walk is bounded by the
    repository's depth and each manifest is read once."""
    walked: list[str] = []
    found: Optional[Package] = None
    current = directory.strip("/")
    while True:
        if current in cache:
            found = cache[current]
            break
        walked.append(current)
        manifest = os.path.join(root, current, "package.json")
        try:
            if os.path.isfile(manifest) and os.path.getsize(manifest) <= _MAX_MANIFEST_BYTES:
                with open(manifest, encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    found = Package(current, data)
                    break
        except (OSError, ValueError):
            pass
        if not current:
            break
        current = posixpath.dirname(current)
    for d in walked:
        cache[d] = found
    return found


def _leaves(value: Any, depth: int = 0) -> Iterator[str]:
    """Every string target of an `exports` value, in declaration order (conditions, arrays)."""
    if isinstance(value, str):
        yield value
    elif depth < _MAX_DEPTH and isinstance(value, list):
        for item in value:
            yield from _leaves(item, depth + 1)
    elif depth < _MAX_DEPTH and isinstance(value, dict):
        for item in value.values():
            yield from _leaves(item, depth + 1)


def export_targets(pkg: Package, subpath: str) -> list[str]:
    """The package-relative targets (`./src/v4/index.ts`) the manifest declares for `subpath`
    (`.` or `./v4`), in declaration order. With no `exports` field the subpath is itself the
    path, and `.` is `module` / `main`."""
    if not pkg.has_exports:
        if subpath == ".":
            return pkg.main
        return [subpath]
    exports = pkg.exports
    if isinstance(exports, dict) and any(k.startswith(".") for k in exports):
        if subpath in exports:
            return list(_leaves(exports[subpath]))[:_MAX_TARGETS]
        best: Optional[tuple[str, str]] = None  # the longest `./prefix/*` pattern that matches
        for key, value in exports.items():
            head, star, tail = key.partition("*")
            if (
                star
                and "*" not in tail
                and subpath.startswith(head)
                and subpath.endswith(tail)
                and len(subpath) >= len(head) + len(tail)
                and (best is None or len(head) > len(best[0]))
            ):
                best = (head, key)
        if best is None:
            return []
        head, key = best
        tail = key.partition("*")[2]
        matched = subpath[len(head) : len(subpath) - len(tail)]
        return [leaf.replace("*", matched) for leaf in _leaves(exports[key])][:_MAX_TARGETS]
    # a bare string / array / conditions object is the "." export
    return list(_leaves(exports))[:_MAX_TARGETS] if subpath == "." else []


def split_specifier(specifier: str) -> tuple[str, str]:
    """`zod/v4/core` -> (`zod`, `./v4/core`); `@scope/pkg/x` -> (`@scope/pkg`, `./x`)."""
    parts = specifier.split("/")
    cut = 2 if specifier.startswith("@") else 1
    name = "/".join(parts[:cut])
    rest = "/".join(parts[cut:])
    return name, "./" + rest if rest else "."
