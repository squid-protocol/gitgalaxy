"""#4265: COPY library resolution -- the estate's own library concatenation, when it is declared.

On z/OS a `COPY member` is found by searching the program's SYSLIB concatenation (its copy
libraries, in order): the FIRST library holding the member wins. `COPY member IN|OF library`
searches that library only. Without a declaration the scan cannot know either -- the import
resolver then narrows same-named members by language, program-ness and proximity (#3199), as
it always has. With one (`galaxyscope --copy-libraries FILE`), a COPY resolves the way the
compiler resolves it, and a member that sits in more than one library of a program's search
order is REPORTED as a collision (the first one still wins, as on z/OS).

The declaration is a JSON (or YAML, with PyYAML) file::

    {
      "libraries": {"PAYRCPY": ["apps/PAYR/copybook"], "SHRCPY": ["shared/copylib"]},
      "syslib": [
        {"programs": "apps/PAYR/*", "order": ["PAYRCPY", "PAYRDCL", "SHRCPY"]},
        {"programs": "*", "order": ["SHRCPY"]}
      ]
    }

`libraries` maps a library-name (as `COPY ... IN` writes it) to the scan-relative directories
that hold its members (a PDS is flat: a member is a file directly in one of them, any
extension). `syslib` lists search orders; a program takes the FIRST entry whose `programs`
glob (fnmatch, `*` crosses `/`) matches its scan-relative path. A program no entry matches and
a library-name the declaration does not know fall back to the default resolver. A program WITH
a declared search order is held to it (#4420): a member found in none of its libraries -- or not
in the library `IN` names -- gets no edge, as the compiler would not find it either (nothing
falls back to a program source of the same name), and is reported as a gap
(`copy_member_gaps`).
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CopyLibraryError(ValueError):
    """A --copy-libraries declaration that cannot be read."""


@dataclass
class CopyLibraries:
    libraries: dict[str, list[str]] = field(default_factory=dict)  # NAME -> directories
    syslib: list[tuple[str, list[str]]] = field(default_factory=list)  # (programs glob, [NAME, ...])

    def order_for(self, importer: str) -> list[str] | None:
        """The library search order of the program at scan-relative `importer`, or None."""
        path = importer.replace("\\", "/")
        for glob, order in self.syslib:
            if fnmatch.fnmatchcase(path, glob):
                return order
        return None

    def knows(self, library: str) -> bool:
        return library.upper() in self.libraries


def _norm_dir(d: str) -> str:
    return d.replace("\\", "/").strip("/").upper()


def parse_copy_libraries(spec: Any) -> CopyLibraries:
    """A CopyLibraries from a parsed declaration (dict), raising CopyLibraryError on a bad shape."""
    if not isinstance(spec, dict):
        raise CopyLibraryError("a copy-library declaration is an object with `libraries` and `syslib`")
    libs: dict[str, list[str]] = {}
    for name, dirs in (spec.get("libraries") or {}).items():
        if isinstance(dirs, str):
            dirs = [dirs]
        if not isinstance(dirs, list) or not all(isinstance(d, str) and d.strip() for d in dirs):
            raise CopyLibraryError(f"library {name!r}: a directory or a list of directories")
        libs[str(name).upper()] = [_norm_dir(d) for d in dirs]
    order: list[tuple[str, list[str]]] = []
    for i, entry in enumerate(spec.get("syslib") or []):
        if not isinstance(entry, dict) or not isinstance(entry.get("programs"), str):
            raise CopyLibraryError(f"syslib[{i}]: needs `programs` (a glob) and `order` (library-names)")
        names = [str(n).upper() for n in entry.get("order") or []]
        unknown = [n for n in names if n not in libs]
        if unknown:
            raise CopyLibraryError(f"syslib[{i}]: unknown library-name(s) {', '.join(unknown)}")
        order.append((entry["programs"].replace("\\", "/"), names))
    return CopyLibraries(libs, order)


def load_copy_libraries(path: str | None) -> CopyLibraries | None:
    """The declaration in the JSON / YAML file at `path`, or None when no path is given."""
    if not path:
        return None
    text = Path(path).read_text(encoding="utf-8")
    try:
        if Path(path).suffix.lower() in (".yaml", ".yml"):
            import yaml  # optional dependency; JSON needs nothing

            spec = yaml.safe_load(text)
        else:
            spec = json.loads(text)
    except Exception as exc:  # a malformed file is the user's to fix, reported with its name
        raise CopyLibraryError(f"{path}: {exc}") from exc
    return parse_copy_libraries(spec)


class MemberIndex:
    """(library directory, MEMBER) -> the scanned files that are that member."""

    def __init__(self, paths: list[str]):
        self._index: dict[tuple[str, str], list[str]] = {}
        for p in paths:
            norm = p.replace("\\", "/")
            directory, _, name = norm.rpartition("/")
            stem = name.rsplit(".", 1)[0] if "." in name.lstrip(".") else name
            self._index.setdefault((directory.upper(), stem.upper()), []).append(p)

    def members(self, libs: CopyLibraries, library: str, member: str) -> list[str]:
        out: list[str] = []
        for d in libs.libraries.get(library.upper(), []):
            out += self._index.get((d, member.upper()), [])
        return out
