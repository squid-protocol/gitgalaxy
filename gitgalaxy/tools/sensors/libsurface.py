# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""`gitgalaxy libsurface SCAN_DB [SCAN_DB_AFTER] [--lib NAME]`: which libraries a repository leans on, and how that surface moves.

    gitgalaxy libsurface DB                          the external libraries in use, with files, sites and distinct API names
    gitgalaxy libsurface DB --lib NAME [--top N]     the files coupled to NAME, most coupled first (where work on the library lands)
    gitgalaxy libsurface DB_BEFORE DB_AFTER --lib NAME   API names added and dropped, files newly or no longer coupled

Counts and lists, no score and no risk claim. A file's sites for a library are its matching imports or includes plus the calls it makes to
the library's API names (`fcall_external`); density is sites per line. Read-only: the databases are opened read-only and nothing is written
except `--json`.

Who defines a library, later layers winning by name (an entry with `disable = true` removes one):
  1. discovery, no list: every external import root is a library (Python, Go, Java, Rust, JS/TS imports; C-family include directories and
     header names), after the engine's own standard-library and system-header lists and the repository's own names are set aside;
  2. the shipped table (library_table.py): glob patterns for the API names of C-family libraries reached through wrapper headers;
  3. TOML files: `$XDG_CONFIG_HOME/gitgalaxy/libraries.toml`, `ROOT/.gitgalaxy/libraries.toml` (with `--src ROOT`), then `--libs FILE`.

    [[library]]
    name      = "openssl"
    languages = ["c", "cpp"]                 # optional: c, cpp, python, go, java, rust, js (default: any language)
    include   = ["openssl/*"]                # globs on an import or include string
    calls     = ["SSL_*", "EVP_*"]           # globs on a called external name (optional)

Patterns are globs (`fnmatch`), never regexes: a pattern a user writes cannot hang the matcher. Research and validation: temporal-crucible,
docs/sensor-overhaul/sensors/library_surface.md.
"""

from __future__ import annotations

import argparse
import collections
import fnmatch
import json
import os
import sqlite3
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

from gitgalaxy.standards.stdlib_modules import is_stdlib_module
from gitgalaxy.standards.system_headers import is_system_header
from gitgalaxy.tools.sensors.library_table import DEFAULT_LIBRARIES

LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "c": (".c", ".h"),
    "cpp": (".cc", ".cpp", ".cxx", ".c++", ".hh", ".hpp", ".hxx", ".h++", ".h"),
    "python": (".py", ".pyi", ".pyw"),
    "go": (".go",),
    "java": (".java",),
    "rust": (".rs",),
    "js": (".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx"),
}
C_FAMILY = LANGUAGE_EXTENSIONS["c"] + LANGUAGE_EXTENSIONS["cpp"]
_HEADER_SUFFIXES = (".h", ".hh", ".hpp", ".hxx", ".h++")
_RUST_SKIP = frozenset({"std", "core", "alloc", "crate", "self", "super"})
_JAVA_SKIP = ("java.", "javax.", "jdk.", "org.xml.", "org.w3c.", "org.ietf.", "org.omg.")
_GO_THREE_PART_HOSTS = frozenset({"github.com", "gitlab.com", "bitbucket.org", "golang.org"})
_JAVA_THREE_PART_PREFIXES = (("org", "apache"), ("com", "google"), ("org", "eclipse"), ("io", "github"))
_MAX_PATTERN = 200
XDG_CONFIG_ENV = "XDG_CONFIG_HOME"  # where a user's library file lives (the XDG base directory convention)
DISABLE_KEY = "disable"  # a key of the user's TOML, read here only


class LibraryConfigError(ValueError):
    """A library definition file is malformed."""


@dataclass(frozen=True)
class Lib:
    name: str
    include: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    extensions: frozenset[str] | None = None  # None: any language


@dataclass
class Coupling:
    path: str
    loc: int
    includes: list[str] = field(default_factory=list)
    names: dict[str, int] = field(default_factory=dict)

    @property
    def sites(self) -> int:
        return len(self.includes) + sum(self.names.values())

    @property
    def density(self) -> float:
        return self.sites / max(self.loc, 1)


@dataclass
class Surface:
    """Everything one scan says about library coupling: per library, per file."""

    files: int
    table_libraries: frozenset[str]
    libraries: dict[str, dict[str, Coupling]] = field(default_factory=dict)
    external_recorded: bool = True


@dataclass
class Change:
    names_added: list[str]
    names_dropped: list[str]
    files_newly_coupled: list[str]
    files_no_longer_coupled: list[str]
    files_before: int
    files_after: int
    sites_before: int
    sites_after: int
    names_before: int
    names_after: int


# ---------------------------------------------------------------- definitions


def _check_patterns(where: str, patterns: object) -> tuple[str, ...]:
    if not isinstance(patterns, list) or not all(isinstance(p, str) and 0 < len(p) <= _MAX_PATTERN for p in patterns):
        raise LibraryConfigError(
            f"{where}: a list of non-empty pattern strings (at most {_MAX_PATTERN} characters each) is required"
        )
    return tuple(patterns)


def _entry(raw: dict, where: str) -> Lib | None:
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LibraryConfigError(f"{where}: every [[library]] needs a name")
    if raw.get(DISABLE_KEY) is True:
        return None
    languages = raw.get("languages")
    extensions: frozenset[str] | None = None
    if languages is not None:
        if not isinstance(languages, list) or any(lang not in LANGUAGE_EXTENSIONS for lang in languages):
            raise LibraryConfigError(f"{where}: {name}: languages must be a list of {', '.join(LANGUAGE_EXTENSIONS)}")
        extensions = frozenset(ext for lang in languages for ext in LANGUAGE_EXTENSIONS[lang])
    include = _check_patterns(f"{where}: {name}: include", raw.get("include", []))
    calls = _check_patterns(f"{where}: {name}: calls", raw.get("calls", []))
    if not include and not calls:
        raise LibraryConfigError(f"{where}: {name}: needs include or calls patterns (or disable = true)")
    return Lib(name.strip(), include, calls, extensions)


def parse_libraries(raws: list[dict], where: str) -> dict[str, Lib | None]:
    """name -> Lib, or None for an entry that disables the name."""
    out: dict[str, Lib | None] = {}
    for raw in raws:
        if not isinstance(raw, dict):
            raise LibraryConfigError(f"{where}: [[library]] must be a table")
        lib = _entry(raw, where)
        out[str(raw.get("name")).strip()] = lib
    return out


def load_libraries(extra: list[Path]) -> dict[str, Lib]:
    """The shipped table, then each TOML file in order; a later entry replaces an earlier one by name, `disable = true` removes it."""
    merged: dict[str, Lib | None] = dict(parse_libraries(DEFAULT_LIBRARIES, "shipped table"))
    for path in extra:
        try:
            data = tomllib.loads(path.read_text("utf8"))
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise LibraryConfigError(f"{path}: cannot read: {exc}") from exc
        raws = data.get("library", [])
        if not isinstance(raws, list):
            raise LibraryConfigError(f"{path}: [[library]] entries are required")
        merged.update(parse_libraries(raws, str(path)))
    return {name: lib for name, lib in merged.items() if lib is not None}


def config_files(src_root: Path | None, explicit: Path | None) -> list[Path]:
    """The override files that exist, in precedence order (later wins)."""
    xdg = Path(os.environ.get(XDG_CONFIG_ENV) or Path.home() / ".config")
    candidates = [xdg / "gitgalaxy" / "libraries.toml"]
    if src_root is not None:
        candidates.append(src_root / ".gitgalaxy" / "libraries.toml")
    found = [p for p in candidates if p.is_file()]
    if explicit is not None:
        found.append(explicit)  # an explicit file that is missing is an error, reported by load_libraries
    return found


# ------------------------------------------------------------------ discovery


def _segments(paths: list[str]) -> frozenset[str]:
    """Every directory name and file stem in the repository: a root that is one of them is the repository's own."""
    out: set[str] = set()
    for p in paths:
        pure = PurePosixPath(p)
        out.update(part.lower().replace("-", "_") for part in pure.parts[:-1])
        out.add(pure.stem.lower().replace("-", "_"))
    return frozenset(out)


def discover_root(
    token: str,
    ext: str,
    own_roots: frozenset[str],
    segments: frozenset[str],
    paths_blob: str,
    basenames: frozenset[str],
) -> str | None:
    """The external library an import or include string names, or None (standard library, system header, relative, or the repository's own)."""
    tok = token.strip().strip("<>\"'")
    if not tok or tok.startswith((".", "/")):
        return None
    if ext in C_FAMILY:
        if is_system_header(tok, ext) or PurePosixPath(tok).name in basenames:
            return None
        root = tok.split("/", 1)[0]
        return PurePosixPath(root).stem if root.endswith(_HEADER_SUFFIXES) else root
    if ext in LANGUAGE_EXTENSIONS["python"]:
        root = tok.split(".", 1)[0]
        return None if is_stdlib_module(tok, ".py") or root.lower().replace("-", "_") in segments else root
    if ext in LANGUAGE_EXTENSIONS["go"]:
        parts = tok.split("/")
        if is_stdlib_module(tok, ".go") or "." not in parts[0] or len(parts) < 2:
            return None
        root = "/".join(parts[: 3 if parts[0] in _GO_THREE_PART_HOSTS else 2])
        return None if root in own_roots else root
    if ext in LANGUAGE_EXTENSIONS["java"]:
        if tok.startswith(_JAVA_SKIP):
            return None
        parts = tok.split(".")
        k = (
            4
            if parts[:3] == ["org", "apache", "commons"]
            else 3
            if tuple(parts[:2]) in _JAVA_THREE_PART_PREFIXES
            else 2
        )
        root = ".".join(parts[:k])
        return None if "/".join(parts[:k]) in paths_blob else root
    if ext in LANGUAGE_EXTENSIONS["rust"]:
        root = tok.split("::", 1)[0]
        return None if root in _RUST_SKIP or root.lower().replace("-", "_") in segments else root
    if ext in LANGUAGE_EXTENSIONS["js"]:
        parts = tok.split("/")
        root = "/".join(parts[:2]) if tok.startswith("@") else parts[0]
        return None if is_stdlib_module(tok, ".js") or root.lower().replace("-", "_") in segments else root
    return None


def go_own_roots(tokens: list[str], dirs: frozenset[str]) -> frozenset[str]:
    """The Go import roots that are the repository's own module: an import under the root whose remaining path is one of the repository's
    directories (`github.com/o/r/util/testutil` with a `util/testutil` directory) names code the repository holds."""
    own: set[str] = set()
    for tok in tokens:
        parts = tok.split("/")
        if len(parts) < 2 or "." not in parts[0] or is_stdlib_module(tok, ".go"):
            continue
        k = 3 if parts[0] in _GO_THREE_PART_HOSTS else 2
        if len(parts) > k and "/".join(parts[k:]) in dirs:
            own.add("/".join(parts[:k]))
    return frozenset(own)


# ----------------------------------------------------------------------- scan


def _tokens(raw_imports: str | None) -> list[str]:
    try:
        return [t for t in json.loads(raw_imports or "[]") if isinstance(t, str)]
    except (ValueError, TypeError):
        return []


def _applies(lib: Lib, ext: str) -> bool:
    return lib.extensions is None or ext in lib.extensions


def build(db: str | Path, libs: dict[str, Lib]) -> Surface:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT id, file_path, total_loc, raw_imports, repo_name FROM file_data").fetchall()
        has_external = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'fcall_external'").fetchone() is not None
        external: dict[int, dict[str, int]] = collections.defaultdict(dict)
        if has_external:
            for fid, callee, callers in con.execute("SELECT src_file_id, callee, callers FROM fcall_external"):
                external[fid][callee] = callers
    finally:
        con.close()
    paths = [r[1] for r in rows]
    segments = _segments(paths)
    paths_blob = "\n".join(paths)
    basenames = frozenset(PurePosixPath(p).name for p in paths)
    dir_suffixes = frozenset(
        "/".join(parts[i:]) for p in paths for parts in [PurePosixPath(p).parts[:-1]] for i in range(len(parts))
    )
    go_tokens = [t for r in rows if r[1].endswith(".go") for t in _tokens(r[3])]
    own_roots = go_own_roots(go_tokens, dir_suffixes)
    name_cache: dict[tuple[str, str], bool] = {}
    surface = Surface(files=len(rows), table_libraries=frozenset(libs), external_recorded=has_external)

    def add(lib: str, path: str, loc: int) -> Coupling:
        return surface.libraries.setdefault(lib, {}).setdefault(path, Coupling(path, loc))

    for fid, path, loc, raw_imports, _repo in rows:
        ext = PurePosixPath(path).suffix.lower()
        for token in _tokens(raw_imports):
            claimed = False
            for lib in libs.values():
                if _applies(lib, ext) and any(fnmatch.fnmatchcase(token, g) for g in lib.include):
                    add(lib.name, path, int(loc or 0)).includes.append(token)
                    claimed = True
            if not claimed:
                root = discover_root(token, ext, own_roots, segments, paths_blob, basenames)
                if root and root not in libs:
                    add(root, path, int(loc or 0)).includes.append(token)
        for callee, callers in external.get(fid, {}).items():
            for lib in libs.values():
                if not lib.calls or not _applies(lib, ext):
                    continue
                key = (lib.name, callee)
                if key not in name_cache:
                    name_cache[key] = any(fnmatch.fnmatchcase(callee, g) for g in lib.calls)
                if name_cache[key]:
                    add(lib.name, path, int(loc or 0)).names[callee] = callers
    return surface


def change(before: dict[str, Coupling], after: dict[str, Coupling]) -> Change:
    names_b = {n for c in before.values() for n in c.names}
    names_a = {n for c in after.values() for n in c.names}
    return Change(
        names_added=sorted(names_a - names_b),
        names_dropped=sorted(names_b - names_a),
        files_newly_coupled=sorted(set(after) - set(before)),
        files_no_longer_coupled=sorted(set(before) - set(after)),
        files_before=len(before),
        files_after=len(after),
        sites_before=sum(c.sites for c in before.values()),
        sites_after=sum(c.sites for c in after.values()),
        names_before=len(names_b),
        names_after=len(names_a),
    )


# --------------------------------------------------------------------- output


def report_libraries(surface: Surface, top: int) -> str:
    rows = sorted(surface.libraries.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    lines = [
        f"LIBRARIES  {surface.files} files scanned; {len(rows)} external libraries found (table = names from the shipped or user table)."
    ]
    if not surface.external_recorded:
        lines.append(
            "This scan did not record external calls (fcall_external): API names are not counted, only imports and includes."
        )
    for name, files in rows[:top]:
        sites = sum(c.sites for c in files.values())
        names = len({n for c in files.values() for n in c.names})
        tag = " [table]" if name in surface.table_libraries else ""
        lines.append(f"  {name:44s} {len(files):5d} files {sites:6d} sites {names:5d} API names{tag}")
    return "\n".join(lines)


def report_coupled(surface: Surface, lib: str, top: int) -> str:
    files = surface.libraries.get(lib, {})
    ranked = sorted(files.values(), key=lambda c: (-c.density, c.loc, c.path))
    names = len({n for c in files.values() for n in c.names})
    lines = [
        f"LIBRARY SURFACE  {lib}: {len(files)} coupled files, {sum(c.sites for c in files.values())} sites, {names} distinct API names"
    ]
    lines += [
        f"  {c.path:56s} {c.sites:5d} sites / {c.loc:6d} lines = {c.density:.3f}   {len(c.names)} names"
        for c in ranked[:top]
    ]
    return "\n".join(lines)


def report_change(lib: str, ch: Change, top: int) -> str:
    def row(label: str, items: list[str]) -> str:
        return f"  {label} ({len(items)}): " + ", ".join(items[:top])

    return "\n".join(
        [
            (
                f"SURFACE CHANGE  {lib}: files {ch.files_before} -> {ch.files_after}, sites {ch.sites_before} -> {ch.sites_after}, "
                f"distinct API names {ch.names_before} -> {ch.names_after}"
            ),
            row("API names added", ch.names_added),
            row("API names dropped", ch.names_dropped),
            row("files newly coupled", ch.files_newly_coupled),
            row("files no longer coupled", ch.files_no_longer_coupled),
            "  A renamed or moved file shows as one file leaving and one joining.",
        ]
    )


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "db", nargs="+", type=Path, help="a scan's *_galaxy_master.db; two (before, after) with --lib shows the change"
    )
    p.add_argument(
        "--lib", metavar="NAME", help="a library: its coupled files (one scan) or its surface change (two scans)"
    )
    p.add_argument(
        "--libs",
        type=Path,
        metavar="FILE",
        help="a TOML file of [[library]] entries that adds to or replaces the shipped table",
    )
    p.add_argument(
        "--src", type=Path, metavar="ROOT", help="the scanned tree: also read ROOT/.gitgalaxy/libraries.toml"
    )
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--json", type=Path, metavar="FILE", help="also write the full result as JSON")


def run(args: argparse.Namespace) -> int:
    dbs: list[Path] = args.db
    if len(dbs) > 2 or (len(dbs) == 2 and not args.lib):
        print("gitgalaxy libsurface: give one scan, or two scans with --lib NAME to show the change", file=sys.stderr)
        return 2
    for db in dbs:
        if not db.is_file():
            print(f"gitgalaxy libsurface: no such database: {db}", file=sys.stderr)
            return 2
    try:
        libs = load_libraries(config_files(args.src, args.libs))
        surfaces = [build(db, libs) for db in dbs]
    except LibraryConfigError as exc:
        print(f"gitgalaxy libsurface: {exc}", file=sys.stderr)
        return 2
    except sqlite3.Error as exc:
        print(f"gitgalaxy libsurface: cannot read a database: {exc}", file=sys.stderr)
        return 2
    payload: object
    if len(surfaces) == 2:
        before, after = (s.libraries.get(args.lib, {}) for s in surfaces)
        if not before and not after:
            print(
                f"gitgalaxy libsurface: no coupling to {args.lib} in either scan (names are case-sensitive)",
                file=sys.stderr,
            )
            return 1
        ch = change(before, after)
        print(report_change(args.lib, ch, args.top))
        payload = asdict(ch)
    elif args.lib:
        if args.lib not in surfaces[0].libraries:
            seen = ", ".join(sorted(surfaces[0].libraries, key=lambda n: -len(surfaces[0].libraries[n]))[:10])
            print(
                f"gitgalaxy libsurface: no coupling to {args.lib} (names are case-sensitive); most used: {seen}",
                file=sys.stderr,
            )
            return 1
        print(report_coupled(surfaces[0], args.lib, args.top))
        payload = {"library": args.lib, "files": [asdict(c) for c in surfaces[0].libraries[args.lib].values()]}
    else:
        print(report_libraries(surfaces[0], args.top))
        payload = {
            n: {"files": len(f), "sites": sum(c.sites for c in f.values())} for n, f in surfaces[0].libraries.items()
        }
    if args.json:
        args.json.write_text(json.dumps(payload, indent=1))
    return 0
