# ==============================================================================
# GitGalaxy Core: Function Call Resolver (#3328, Epic #3265 step 1)
#
# PURPOSE:
# `calls_out_to` is a list of bare callee NAMES per function (the contract is
# docs/calls_out_rule_contract.md, #3327). A graph built on bare names pools
# every `save()` / `get()` / `run()` together, so a function-level PageRank
# would rank the most common names rather than the most depended-on functions.
# This module sees the whole repository and links each (caller, callee name)
# to the definition it most plausibly means, and says how sure it is.
#
# THE LADDER (first match wins, per (caller function, callee name)):
#   1. `class`   -- a method of the caller's own class, in the caller's file.
#   2. `file`    -- a definition in the caller's own file.
#   2b. `typed`  -- `x.save()` where this function shows x's class
#                   (`x = Store()`, `def f(x: Store)`; the detector's
#                   calls_out_receiver_types): Store's method, or its
#                   nearest ancestor's. Python only for now.
#   3. `import`  -- a definition in a file the caller's file imports (the
#                   resolved import graph, NetworkRiskSensor.dependency_edges).
#   4. `unique`  -- the name is defined exactly once in the repository.
#                   In a package-scoped language (#3443) a BARE call must also
#                   see that one definition -- imported, or in its own
#                   directory where a directory is a namespace -- or it is
#                   `unseen`: ambiguous, the definition kept as the guess.
#   5. `nearest` -- several definitions; the nearest by path wins
#                   (core/path_proximity.py, the rule both import and
#                   mainframe resolution already use).
#   6. `tie`     -- several definitions that are equally near: no target.
#   7. `none`    -- defined nowhere in the repository: a built-in, the
#                   standard library or a third-party package. Not an edge.
#                   This is what removes most built-in noise without a
#                   per-language ignore list (#3327 decision 1).
# `resolution` groups the steps into the four confidence classes #3331
# reports: scoped (1-3), unique (4), ambiguous (`unseen`, 5-6), external (7).
#
# AMBIGUOUS CALLS ARE NOT EDGES (the decision #3328 asked for). A name with k
# definitions is exactly the collision this module exists to defeat. Splitting
# the weight 1/k across the candidates would still hand every `init()` in the
# repository a share of every `init()` call, and summed over many callers that
# rebuilds the "most common name wins" ranking. So an ambiguous site is a ROW
# (fcall_data keeps the nearest guess, and the candidate count, for whoever
# wants to measure it -- #3330 and #3332) but never a confident edge. That
# matches the import resolver, where "an import that is still ambiguous draws
# nothing" (invocation_resolver.py's header).
#
# THE FILE GRAPH (#3333). The resolved pairs become fcall_data rows, and the
# CONFIDENT cross-file ones (confident_file_pairs) also join the dependency
# graph as edge_kind 'fcall' wherever no import already joins the two files --
# so pagerank_score, popularity, internal_dependency_links and blast radius see
# a C file that calls into another translation unit, or a same-package Java
# class, without an import statement. Ambiguous pairs never do. #3332 measured
# confident links at ~96% precision against pyan3 before this was switched on.
# ==============================================================================
import posixpath
from collections import Counter
from typing import Any, Optional

# Languages whose identifiers are case-insensitive, so `CALL Foo` reaches a
# `FOO` definition. The detector's calls_out ignore uses the same list for its
# keywords (detector.py, `_CALLS_OUT_GLOBAL_IGNORE`'s comment).
CASE_INSENSITIVE_CALL_LANGS = frozenset(
    {"abap", "ada", "batch", "cobol", "db2_sql", "fortran", "hlasm", "jcl", "livecode", "pli", "powershell", "rexx"}
)

# A call resolves only to a definition in a language it can link against. Most
# languages link only to themselves. These groups link across a real boundary:
# C/C++/Objective-C/yacc/assembly share one symbol table at link time,
# TypeScript calls JavaScript, the JVM languages call each other, and
# MicroPython is Python. Everything else is its own group.
_LINK_GROUPS = (
    frozenset({"c", "cpp", "objective-c", "yacc", "assembly"}),
    frozenset({"javascript", "typescript"}),
    frozenset({"java", "kotlin", "scala", "groovy"}),
    frozenset({"python", "embedded_python"}),
)
_GROUP_OF = {lang: min(group) for group in _LINK_GROUPS for lang in group}

RESOLUTION_OF_STEP = {
    "class": "scoped",
    "qualified": "scoped",
    "typed": "scoped",
    "file": "scoped",
    "import": "scoped",
    "unique": "unique",
    "unseen": "ambiguous",
    "nearest": "ambiguous",
    "tie": "ambiguous",
    "receiver": "ambiguous",
    "none": "external",
}
CONFIDENT_RESOLUTIONS = frozenset({"scoped", "unique"})
# Best-first, for a callee reached through several qualifiers in one function:
# the ladder's own order, so `self.save()` beats `x.save()` in the same body.
_RANK = {
    step: i
    for i, step in enumerate(
        ("class", "qualified", "typed", "import", "file", "unique", "unseen", "nearest", "receiver", "tie", "none")
    )
}

# Receivers that mean "the caller's own object" / "its parent".
_SELF_RECEIVERS = frozenset({"self", "this", "Me", "me"})
_SUPER_RECEIVERS = frozenset({"super", "base", "parent"})

# Languages whose extractor does not attach a method to its receiver type (go's
# `func (r *T) Save()` is a top-level declaration), so a qualified call there may
# reach any definition, not only a method.
_OWNERLESS_METHOD_LANGS = frozenset({"go"})

# #3401: names a BARE call always means as the language's built-in, whatever
# the repository defines. Perl's named operators and built-in functions take
# precedence over a user `sub` of the same name -- `sub map` in Mojo's
# Promise.pm is reachable only as `$promise->map`, `&map` or
# `Mojo::Promise::map` -- so a bare `map(` is never an edge to it. Measured on
# language-crucible: bugzilla's and spamassassin's `map(` all resolved
# `unique` to Mojo's Promise.pm, inflating its Popularity Rank. A language
# where a user definition CAN shadow a built-in (Python, Lua, JS) is not listed.
_BARE_BUILTINS: dict[str, frozenset[str]] = {
    "perl": frozenset(
        {
            "abs",
            "binmode",
            "bless",
            "caller",
            "chdir",
            "chmod",
            "chomp",
            "chop",
            "chown",
            "chr",
            "close",
            "closedir",
            "cos",
            "defined",
            "delete",
            "die",
            "each",
            "eof",
            "eval",
            "exec",
            "exists",
            "exit",
            "exp",
            "fork",
            "grep",
            "hex",
            "index",
            "int",
            "join",
            "keys",
            "kill",
            "lc",
            "lcfirst",
            "length",
            "local",
            "localtime",
            "gmtime",
            "lock",
            "log",
            "map",
            "mkdir",
            "oct",
            "open",
            "opendir",
            "ord",
            "pack",
            "pop",
            "pos",
            "print",
            "printf",
            "push",
            "quotemeta",
            "rand",
            "read",
            "readdir",
            "ref",
            "rename",
            "require",
            "return",
            "reverse",
            "rindex",
            "rmdir",
            "scalar",
            "seek",
            "select",
            "shift",
            "sin",
            "sleep",
            "sort",
            "splice",
            "split",
            "sprintf",
            "sqrt",
            "srand",
            "substr",
            "system",
            "tell",
            "tie",
            "tied",
            "time",
            "uc",
            "ucfirst",
            "undef",
            "unlink",
            "unpack",
            "unshift",
            "untie",
            "values",
            "wait",
            "waitpid",
            "wantarray",
            "warn",
        }
    ),
}

# Languages where a directory is a namespace: a class in a sibling file is
# visible without an import (a Java/Kotlin/Scala/Groovy package, a Go package,
# a C# namespace by convention). Elsewhere (Python, JS/TS, Ruby, PHP, C++) a
# sibling file is not visible until imported, so an untyped receiver whose only
# candidate is in the same directory stays an ambiguous `receiver` guess --
# #3333 measured ~3.7k such same-directory Python pairs on cpython alone, which
# would otherwise have become file-graph edges.
_PACKAGE_DIR_LANGS = frozenset({"java", "kotlin", "scala", "groovy", "go", "csharp"})

# #3443: languages where a BARE call reaches only the caller's own module, what
# it imports, and (in _PACKAGE_DIR_LANGS) its own package directory. A name
# defined exactly once elsewhere is not `unique` there: bugzilla's bare
# `remove(` is not Mojo's IOLoop.pm `remove`, a TypeScript `pipe(` is not
# jQuery's. The global-namespace languages (C, Lua, PHP, Ruby, Swift's
# module-wide scope, the mainframe languages) keep `unique`. Measured on
# language-crucible: ~530 pairs moved, most of them links into another
# repository; allowing definitions one import hop (or any number) away
# rescued almost no correct link and let wrong cross-repository Zig links back.
_PACKAGE_SCOPED_LANGS = _PACKAGE_DIR_LANGS | frozenset(
    {"perl", "python", "embedded_python", "javascript", "typescript", "zig", "rust", "dart"}
)


def encode_qualifiers(calls_out_to: list[str], qualifiers: dict[str, list[str]]) -> Optional[list[Any]]:
    """The persisted form of `calls_out_qualifiers` (#3329): a list aligned with
    `calls_out_to`, so the callee names are not stored twice. Each element is the
    single receiver chain as a string (`""` for a bare call -- the common case),
    or a list when one function reaches the callee through several. None when
    the language captures no qualifiers (the map is empty).
    """
    if not qualifiers:
        return None
    out: list[Any] = []
    for callee in calls_out_to:
        seen = qualifiers.get(callee) or [""]
        out.append(seen[0] if len(seen) == 1 else list(seen))
    return out


def decode_qualifiers(calls_out_to: list[str], encoded: Any) -> dict[str, list[str]]:
    """`encode_qualifiers`'s inverse; anything malformed decodes to "not captured"."""
    if not isinstance(encoded, list) or len(encoded) != len(calls_out_to):
        return {}
    out: dict[str, list[str]] = {}
    for callee, q in zip(calls_out_to, encoded):
        if isinstance(q, str):
            out[callee] = [q]
        elif isinstance(q, list) and all(isinstance(x, str) for x in q):
            out[callee] = list(q)
        else:
            return {}
    return out


def _group(lang: str) -> str:
    return _GROUP_OF.get(lang, lang)


def _key(name: str, lang: str) -> str:
    return name.casefold() if lang in CASE_INSENSITIVE_CALL_LANGS else name


def _leaf(name: str) -> tuple[str, Optional[str]]:
    """`Foo::bar` / `Foo.bar` -> (`bar`, `Foo`); a plain name -> (name, None).

    Out-of-line C++ definitions (`int Foo::bar(...)`) and some method forms are
    extracted under their qualified name; a call site only ever carries the bare
    name (contract C6), so the definition is indexed by its last segment and the
    prefix stands in for the owning class.
    """
    for sep in ("::", "."):
        if sep in name:
            owner, _, leaf = name.rpartition(sep)
            if leaf:
                return leaf, owner.rpartition(sep)[2] or None
    return name, None


def _stem(path: str) -> str:
    base = posixpath.basename(path.replace("\\", "/"))
    return base.split(".", 1)[0]


def _dirname(path: str) -> str:
    return posixpath.dirname(path.replace("\\", "/"))


def _parts(dir_: str) -> tuple[str, ...]:
    return tuple(dir_.split("/")) if dir_ else ()


def _rank(src_parts: tuple[str, ...], d: "_Definition") -> tuple[int, int]:
    """`path_proximity.proximity_rank` over pre-split directories (same order,
    same ties) -- the resolver ranks millions of candidates on a large repo."""
    shared = 0
    for a, b in zip(src_parts, d.parts):
        if a != b:
            break
        shared += 1
    return -shared, len(d.parts)


class _Definition:
    __slots__ = ("dir", "kind", "line", "name", "owner_key", "parts", "path", "stem")

    def __init__(
        self,
        path: str,
        dir_: str,
        parts: tuple[str, ...],
        stem: str,
        name: str,
        line: int,
        owner_key: Optional[str],
        kind: str,
    ) -> None:
        self.path = path
        self.dir = dir_
        self.parts = parts
        self.stem = stem
        self.name = name
        self.line = line
        self.owner_key = owner_key  # the owning class's name key, None for a free function
        self.kind = kind  # 'function' | 'class'


class _Set:
    """One filtered candidate list with the lookups the ladder needs, built once."""

    __slots__ = ("_prefix", "by_dir", "by_path", "defs", "n_paths", "owners")

    def __init__(self, defs: list[_Definition]) -> None:
        self.defs = defs
        self.by_path: dict[str, _Definition] = {}  # path -> first definition in it
        self.by_dir: dict[str, list[_Definition]] = {}
        # path -> the distinct owners (classes; None = free) defining the name there
        self.owners: dict[str, set[Optional[str]]] = {}
        for d in defs:
            self.owners.setdefault(d.path, set()).add(d.owner_key)
            if d.path not in self.by_path:
                self.by_path[d.path] = d
                self.by_dir.setdefault(d.dir, []).append(d)
        self.n_paths = len(self.by_path)
        self._prefix: Optional[dict[tuple[str, ...], list[_Definition]]] = None

    def nearest(self, src_parts: tuple[str, ...]) -> Optional[_Definition]:
        """`_nearest_of` over the whole set, through a directory-prefix index.

        The deepest directory prefix of the caller that any candidate shares is
        the best shared depth; among the candidates at exactly that depth the
        shallowest wins, and two equally shallow ones are a tie -- the same
        order `_rank` defines, without ranking every candidate.
        """
        if self.n_paths < 16:
            return _nearest_of(list(self.by_path.values()), src_parts)
        if self._prefix is None:
            self._prefix = {}
            for d in self.by_path.values():
                for k in range(len(d.parts) + 1):
                    self._prefix.setdefault(d.parts[:k], []).append(d)
        for k in range(len(src_parts), -1, -1):
            group = self._prefix.get(src_parts[:k])
            if group:
                # every member shares exactly k directories (deeper prefixes were empty)
                return _nearest_of(group, src_parts)
        return None


class _Bucket:
    """Every definition of one name in one link group. The lookup sets are built
    on first use -- most names in a repository are never called by that name:
    `all`, `free` (free functions and classes -- what a bare call may reach),
    `methods` (functions with an owner -- what a receiver may reach)."""

    __slots__ = ("_all", "_free", "_methods", "by_owner", "defs")

    def __init__(self) -> None:
        self.defs: list[_Definition] = []
        # owner key -> every definition of this name on a class of that name.
        # Several: two programs can share a PROGRAM-ID (zopeneditor's SAM1 and
        # SAM1LIB), two packages a class name -- `owned()` picks among them.
        self.by_owner: dict[str, list[_Definition]] = {}
        self._all: Optional[_Set] = None
        self._free: Optional[_Set] = None
        self._methods: Optional[_Set] = None

    def add(self, d: _Definition) -> None:
        self.defs.append(d)
        if d.kind == "function" and d.owner_key is not None:
            self.by_owner.setdefault(d.owner_key, []).append(d)

    @property
    def all(self) -> _Set:
        if self._all is None:
            self._all = _Set(self.defs)
        return self._all

    @property
    def free(self) -> _Set:
        if self._free is None:
            self._free = _Set([d for d in self.defs if d.kind == "class" or d.owner_key is None])
        return self._free

    @property
    def methods(self) -> _Set:
        if self._methods is None:
            self._methods = _Set([d for d in self.defs if d.kind == "function" and d.owner_key is not None])
        return self._methods


def _index(parsed_files: list[dict[str, Any]]) -> dict[tuple[str, str], _Bucket]:
    """(link group, name key) -> every definition of that name, in scan order.

    Functions and classes share the index: a constructor call `Foo(...)` names
    the class (contract C3). Synthetic top-level slices are callers, never
    definitions.
    """
    index: dict[tuple[str, str], _Bucket] = {}
    for f in parsed_files:
        path = f.get("path", "")
        lang = str(f.get("lang_id", "")).lower()
        group = _group(lang)
        dir_, stem = _dirname(path), _stem(path)
        parts = _parts(dir_)
        for func in f.get("functions", []) or []:
            if func.get("is_synthetic_slice"):
                continue
            name = str(func.get("name") or "")
            leaf, prefix = _leaf(name)
            if not leaf:
                continue
            owner = func.get("parent_class_name") or prefix
            owner_key = _key(_leaf(owner)[0], lang) if owner else None
            index.setdefault((group, _key(leaf, lang)), _Bucket()).add(
                _Definition(path, dir_, parts, stem, name, int(func.get("start_line", 0) or 0), owner_key, "function")
            )
        for cls in f.get("classes", []) or []:
            name = str(cls.get("name") or "")
            if name:
                index.setdefault((group, _key(name, lang)), _Bucket()).add(
                    _Definition(path, dir_, parts, stem, name, int(cls.get("start_line", 0) or 0), None, "class")
                )
    return index


# What a language calls a class's constructor, when it is a method (#3642
# follow-up). A call that resolves to a class is linked to this method, so the
# function graph sees `Foo(...)` reach `Foo.__init__`. Languages not listed
# name the constructor after the class (java, c#, c++, dart); go, rust, c and
# the rest have no constructor method at all, and keep the class as the target.
_CONSTRUCTOR_NAMES: dict[str, tuple[str, ...]] = {
    "python": ("__init__", "__new__"),
    "embedded_python": ("__init__", "__new__"),
    "javascript": ("constructor",),
    "typescript": ("constructor",),
    "kotlin": ("constructor",),
    "php": ("__construct",),
    "ruby": ("initialize",),
    "swift": ("init",),
}
_CLASS_NAMED_CONSTRUCTOR_LANGS = frozenset({"java", "csharp", "cpp", "dart", "apex", "objective-c"})


def _constructor_of(index: dict[tuple[str, str], "_Bucket"], cls: _Definition, lang: str) -> Optional[_Definition]:
    """The constructor method of class definition `cls`, if the scan extracted one.

    One in the class's own file, else one beside it with the same stem (a C++
    `foo.h` class, its `Foo::Foo` in `foo.cpp`). Owner keys are bare class
    names, so a constructor anywhere else may belong to another class of the
    same name and is never taken. None when the class has no constructor of
    its own (an inherited or implicit one): the call keeps the class.
    """
    leaf = _leaf(cls.name)[0]
    names = _CONSTRUCTOR_NAMES.get(lang) or ((leaf,) if lang in _CLASS_NAMED_CONSTRUCTOR_LANGS else ())
    group = _group(lang)
    owner = _key(leaf, lang)
    for n in names:
        bucket = index.get((group, _key(n, lang)))
        defs = [d for d in (bucket.by_owner.get(owner, []) if bucket else []) if d.kind == "function"]
        if not defs:
            continue
        for d in defs:
            if d.path == cls.path:
                return d
        for d in defs:
            if d.dir == cls.dir and d.stem == cls.stem:
                return d
    return None


def _imports_by_file(dependency_edges: Optional[list[dict[str, Any]]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for e in dependency_edges or []:
        if e.get("edge_kind", "import") == "import":
            out.setdefault(e.get("src", ""), set()).add(e.get("dst", ""))
    return out


# Barrel files: a package's public face, which mostly re-exports what its
# modules define (`from .param_functions import Depends as Depends` in a
# package `__init__.py`, `export * from "./x"` in an `index.ts`). A caller that
# imports the barrel can see what the barrel imports.
_BARREL_BASENAMES = frozenset(
    {"__init__.py", "index.js", "index.ts", "index.tsx", "index.jsx", "index.mjs", "index.cjs", "index.mts"}
)
# Barrels import barrels (`pkg/__init__.py` -> `pkg/sub/__init__.py`); follow at most this many.
_BARREL_HOPS = 2


def _with_reexports(imports: dict[str, set[str]]) -> dict[str, set[str]]:
    """#3642 follow-up: each file's imports plus what the barrels among them import.

    `from fastapi import Depends` resolves to `fastapi/__init__.py`, which only
    re-exports `Depends` from `fastapi/param_functions.py`. Without this the
    import step finds no definition in the barrel and the call falls through
    to a repository-wide name search. Only barrel files are expanded, and only
    `_BARREL_HOPS` deep, so importing an ordinary module never makes its own
    imports visible.
    """
    out: dict[str, set[str]] = {}
    for src, dsts in imports.items():
        seen = set(dsts)
        frontier = [d for d in dsts if posixpath.basename(d) in _BARREL_BASENAMES]
        for _ in range(_BARREL_HOPS):
            nxt = []
            for barrel in frontier:
                for d in imports.get(barrel, ()):
                    if d != src and d not in seen:
                        seen.add(d)
                        if posixpath.basename(d) in _BARREL_BASENAMES:
                            nxt.append(d)
            frontier = nxt
        out[src] = seen
    return out


def _ancestry(parsed_files: list[dict[str, Any]]) -> dict[tuple[str, str], set[str]]:
    """(link group, class key) -> the names it inherits from, directly."""
    parents: dict[tuple[str, str], set[str]] = {}
    for f in parsed_files:
        lang = str(f.get("lang_id", "")).lower()
        group = _group(lang)
        for cls in f.get("classes", []) or []:
            name = str(cls.get("name") or "")
            if not name:
                continue
            bases = {_leaf(str(b).strip())[0] for b in cls.get("inheritance", []) or [] if str(b).strip()}
            parents.setdefault((group, _key(name, lang)), set()).update(_key(b, lang) for b in bases)
    return parents


def _is_class(index: dict[tuple[str, str], "_Bucket"], group: str, name: str, lang: str) -> bool:
    bucket = index.get((group, _key(name, lang)))
    return bucket is not None and any(d.kind == "class" for d in bucket.defs)


def _lineage(owner: Optional[str], group: str, lang: str, parents: dict[tuple[str, str], set[str]]) -> list[str]:
    """The caller's class followed by its ancestors, nearest first (bounded)."""
    if not owner:
        return []
    out = [_key(_leaf(owner)[0], lang)]
    frontier = [out[0]]
    while frontier and len(out) < 16:
        nxt = []
        for c in frontier:
            for p in sorted(parents.get((group, c), ())):
                if p not in out:
                    out.append(p)
                    nxt.append(p)
        frontier = nxt
    return out


def _nearest_of(defs: list[_Definition], src_parts: tuple[str, ...]) -> Optional[_Definition]:
    """The nearest of definitions in DISTINCT files, or None on an exact tie."""
    if len(defs) == 1:
        return defs[0]
    best: Optional[_Definition] = None
    best_rank = second_rank = (1, 0)
    for d in defs:
        r = _rank(src_parts, d)
        if best is None or r < best_rank:
            best, second_rank, best_rank = d, best_rank, r
        elif r < second_rank:
            second_rank = r
    return None if second_rank == best_rank else best


class _File:
    """What one calling file brings to every lookup made from it."""

    __slots__ = ("dir", "imported", "imported_dirs", "imported_stems", "lang", "parts", "path")

    def __init__(self, path: str, lang: str, imported: set[str]) -> None:
        self.path = path
        self.lang = lang
        self.dir = _dirname(path)
        self.parts = _parts(self.dir)
        self.imported = imported
        self.imported_stems = {_stem(p) for p in imported}
        self.imported_dirs = {posixpath.basename(_dirname(p)) for p in imported}


_Cache = dict[tuple[str, str, int], Optional[_Definition]]


def _nearest(cset: _Set, caller: _File, cache: _Cache) -> Optional[_Definition]:
    """Nearest file in the whole set; depends only on the caller's directory."""
    ck = ("dir", caller.dir, id(cset))
    if ck not in cache:
        cache[ck] = cset.nearest(caller.parts)
    return cache[ck]


def _nearest_imported(cset: _Set, caller: _File, cache: _Cache) -> Optional[_Definition]:
    """Nearest file among those the caller imports; depends on the caller's file.
    A tie among imported files still picks one (first path): both are visible."""
    ck = ("imp", caller.path, id(cset))
    if ck not in cache:
        if len(caller.imported) < cset.n_paths:
            hits = [cset.by_path[p] for p in caller.imported if p in cset.by_path]
        else:
            hits = [d for p, d in cset.by_path.items() if p in caller.imported]
        cache[ck] = (_nearest_of(hits, caller.parts) or min(hits, key=lambda d: d.path)) if hits else None
    return cache[ck]


def _nearest_local(cset: _Set, caller: _File, cache: _Cache) -> Optional[_Definition]:
    """Nearest file in the caller's own directory (a package)."""
    ck = ("loc", caller.dir, id(cset))
    if ck not in cache:
        local = cset.by_dir.get(caller.dir)
        cache[ck] = (_nearest_of(local, caller.parts) or min(local, key=lambda d: d.path)) if local else None
    return cache[ck]


def _visible_receiver(cset: _Set, caller: _File, cache: _Cache) -> tuple[str, Optional[_Definition]]:
    """An untyped receiver (`x.save()`): confident only when exactly ONE visible
    class defines the method -- in the caller's own file, else among the files
    it imports, else (package-scoped languages only) in its own directory. Several classes at the first level
    that has any (cython's Nodes.py defines `generate_execution_code` on ~40
    node classes; `self.body.generate_execution_code()` could be any of them)
    is the ambiguous `receiver` step, with the nearest as its guess (#3332)."""

    def classes(paths) -> int:
        return len({(p, o) for p in paths for o in cset.owners.get(p, ())})

    own = cset.by_path.get(caller.path)
    if own is not None:
        return ("file", own) if classes([caller.path]) == 1 else ("receiver", own)
    if caller.imported:
        hit = _nearest_imported(cset, caller, cache)
        if hit is not None:
            visible = [p for p in caller.imported if p in cset.owners]
            return ("import", hit) if classes(visible) == 1 else ("receiver", hit)
    hit = _nearest_local(cset, caller, cache) if caller.lang in _PACKAGE_DIR_LANGS else None
    if hit is not None:
        local = [d.path for d in cset.by_dir.get(caller.dir, [])]
        return ("import", hit) if classes(local) == 1 else ("receiver", hit)
    return "receiver", _nearest(cset, caller, cache)


def _ladder(cset: _Set, caller: _File, visible_only: bool, cache: _Cache) -> tuple[str, Optional[_Definition]]:
    """Steps file -> import -> unique -> nearest -> tie over an already-filtered set.

    `visible_only` is the unknown-receiver case: the method's defining file must
    be one the caller can see (its own, one it imports, or its own directory --
    a Java package or a Go package is a directory), or the best a name can do
    is the `receiver` guess.
    """
    if not cset.n_paths:
        return "none", None
    if visible_only:
        return _visible_receiver(cset, caller, cache)
    own = cset.by_path.get(caller.path)
    if own is not None:
        return "file", own
    if caller.imported:
        hit = _nearest_imported(cset, caller, cache)
        if hit is not None:
            return "import", hit
    if cset.n_paths == 1:
        return "unique", cset.defs[0]
    near = _nearest(cset, caller, cache)
    return ("nearest", near) if near is not None else ("tie", None)


def _resolve_one(
    bucket: Optional[_Bucket],
    caller: _File,
    lineage: list[str],
    qualifier: Optional[str],
    cache: _Cache,
    typed: Optional[dict[str, list[str]]] = None,
) -> tuple[str, Optional[_Definition]]:
    """One (caller, callee, qualifier) lookup. `qualifier` None = not captured."""
    if bucket is None:
        return "none", None
    by_owner = bucket.by_owner

    def owned(owner_key: str) -> Optional[_Definition]:
        """The caller's own file's definition on that class, else the nearest one."""
        defs = by_owner.get(owner_key)
        if not defs:
            return None
        for d in defs:
            if d.path == caller.path:
                return d
        return _nearest_of(defs, caller.parts) or min(defs, key=lambda d: d.path)

    ownerless = caller.lang in _OWNERLESS_METHOD_LANGS

    if qualifier == "" and bucket.defs and _leaf(bucket.defs[0].name)[0] in _BARE_BUILTINS.get(caller.lang, ()):
        return "none", None  # the built-in (#3401), external like any library call
    if qualifier is None or qualifier == "":
        for owner_key in lineage:
            d = owned(owner_key)
            if d is not None:
                return "class", d
        # A bare call cannot reach another class's method: only a free
        # function, a class (a constructor), or the caller's own lineage,
        # handled above. (Ownerless-method languages keep every candidate.)
        cset = bucket.free if qualifier == "" and not ownerless else bucket.all
        step, d = _ladder(cset, caller, False, cache)
        if (
            step == "unique"
            and qualifier == ""
            and caller.lang in _PACKAGE_SCOPED_LANGS
            and not (caller.lang in _PACKAGE_DIR_LANGS and d is not None and d.dir == caller.dir)
        ):
            return "unseen", d  # #3443: the only definition, but not one this caller can see
        return step, d

    if qualifier in _SELF_RECEIVERS:
        for owner_key in lineage:
            d = owned(owner_key)
            if d is not None:
                return "class", d
        return _ladder(bucket.methods, caller, True, cache)
    if qualifier in _SUPER_RECEIVERS:
        for owner_key in lineage[1:]:
            d = owned(owner_key)
            if d is not None:
                return "class", d
        return "none", None
    if typed and qualifier in typed:
        # The receiver's class is known from this function (`app = FastAPI()`):
        # the method on that class, or on the nearest ancestor that has it.
        for owner_key in typed[qualifier]:
            d = owned(owner_key)
            if d is not None:
                return "typed", d
    head = qualifier.split(".", 1)[0]
    last = qualifier.rsplit(".", 1)[-1]
    d = owned(_key(last, caller.lang))
    if d is not None:
        return "qualified", d
    if head in caller.imported_stems or last in caller.imported_stems or last in caller.imported_dirs:
        via = [
            d
            for p, d in bucket.all.by_path.items()
            if p in caller.imported and (d.stem in (head, last) or posixpath.basename(d.dir) == last)
        ]
        if via:
            return "import", (_nearest_of(via, caller.parts) or min(via, key=lambda d: d.path))
    # A receiver the engine cannot type: a variable, a call result, an external
    # module. Only a method can answer it (a free function is not reachable
    # through a receiver), and only a visible one confidently.
    return _ladder(bucket.all if ownerless else bucket.methods, caller, True, cache)


def resolve_calls(
    parsed_files: list[dict[str, Any]],
    dependency_edges: Optional[list[dict[str, Any]]] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Resolve every (caller function, callee name) pair in the repository.

    Returns `(sites, stats)`:
      - `sites`: one row per distinct callee name per caller (calls_out_to is
        already deduplicated, contract decision 3), resolved or not. A resolved
        row names its definition by `(dst_path, dst_name, dst_line, dst_kind)`;
        `kind` is 'call', or 'transfer' for a COBOL GO TO target (#3362:
        resolved the same way, never counted in the call-resolution rates).
        `qualifier` is the receiver chain the winning lookup used (#3329), None
        where the language captures none. A callee reached through several
        receivers keeps the most confident of their resolutions. Self-resolution
        (a call that lands on the caller itself) is dropped, as the contract
        drops recursion.
      - `stats`: counts by step and by resolution, repo-wide and per language
        -- the numbers #3331 reports.
    """
    index = _index(parsed_files)
    parents = _ancestry(parsed_files)
    # proximity depends only on the caller's directory, so the nearest pick for
    # a candidate set is shared by every caller in that directory
    cache: _Cache = {}
    imports = _with_reexports(_imports_by_file(dependency_edges))
    sites: list[dict[str, Any]] = []
    by_step: Counter[str] = Counter()
    by_lang: dict[str, Counter[str]] = {}
    transfers: Counter[str] = Counter()

    for f in parsed_files:
        src_path = f.get("path", "")
        lang = str(f.get("lang_id", "")).lower()
        group = _group(lang)
        caller = _File(src_path, lang, imports.get(src_path, set()))
        lang_counts = by_lang.setdefault(lang, Counter())
        for func in f.get("functions", []) or []:
            # #3362: calls, then unconditional transfers (COBOL GO TO). A transfer
            # resolves by the same ladder (it names a unit the same way) but is
            # its own `kind`: it never counts toward the call-resolution rates.
            callees = [(c, "call") for c in func.get("calls_out_to") or []]
            callees += [(t, "transfer") for t in func.get("transfers_to") or []]
            if not callees:
                continue
            caller_name = str(func.get("name") or "")
            caller_line = int(func.get("start_line", 0) or 0)
            lineage = _lineage(func.get("parent_class_name") or _leaf(caller_name)[1], group, lang, parents)
            qualifier_map = func.get("calls_out_qualifiers") or {}
            # receiver -> its class's lineage, for receivers whose class the scan
            # knows (a factory function's name is not a class, and is ignored)
            typed = {
                q: _lineage(c, group, lang, parents)
                for q, c in (func.get("calls_out_receiver_types") or {}).items()
                if _is_class(index, group, str(c), lang)
            }
            for callee, kind in callees:
                bucket = index.get((group, _key(str(callee), lang)))
                options: list[Optional[str]] = (list(qualifier_map.get(callee) or []) if kind == "call" else []) or [
                    None
                ]
                step, dst = _resolve_one(bucket, caller, lineage, options[0], cache, typed)
                used = options[0]
                for q in options[1:]:
                    alt_step, alt_dst = _resolve_one(bucket, caller, lineage, q, cache, typed)
                    if _RANK[alt_step] < _RANK[step]:
                        step, dst, used = alt_step, alt_dst, q
                cls = None
                if dst is not None and dst.kind == "class":
                    # A constructor call reaches the class's constructor method.
                    ctor = _constructor_of(index, dst, lang)
                    if ctor is not None:
                        cls, dst = dst, ctor
                if dst is not None and dst.path == src_path and dst.line == caller_line and dst.name == caller_name:
                    continue  # recursion through a qualified name (`Foo::bar` calling `bar`)
                resolution = RESOLUTION_OF_STEP[step]
                if kind == "call":
                    by_step[step] += 1
                    lang_counts[resolution] += 1
                else:
                    transfers[step] += 1
                sites.append(
                    {
                        "src_path": src_path,
                        "src_name": caller_name,
                        "src_line": caller_line,
                        "src_synthetic": bool(func.get("is_synthetic_slice")),
                        "callee": callee,
                        "kind": kind,
                        "qualifier": used,
                        "step": step,
                        "resolution": resolution,
                        "candidates": bucket.all.n_paths if bucket else 0,
                        "dst_path": dst.path if dst else None,
                        "dst_name": dst.name if dst else None,
                        "dst_line": dst.line if dst else None,
                        "dst_kind": dst.kind if dst else None,
                        # the class a constructor call named, when dst is its constructor
                        "dst_class_path": cls.path if cls else None,
                        "dst_class_name": cls.name if cls else None,
                    }
                )

    by_resolution: Counter[str] = Counter()
    for step, n in by_step.items():
        by_resolution[RESOLUTION_OF_STEP[step]] += n
    stats = {
        "by_step": dict(by_step),
        "by_resolution": dict(by_resolution),
        "by_language": {lang: dict(c) for lang, c in sorted(by_lang.items()) if c},
        "transfers_by_step": dict(transfers),
    }
    return sites, stats


RESOLUTION_CLASSES = ("scoped", "unique", "ambiguous", "external")

# Stated wherever a rate is shown (#3331): the rate is the resolver's confidence,
# not its accuracy -- #3332 measures correctness.
RATE_CAVEAT = (
    "A high scoped/unique share means the resolver made a confident choice, not that the choice "
    "was correct; resolution accuracy is measured separately (gitgalaxy#3332)."
)


def _rate_row(language: str, counts: dict[str, int]) -> dict[str, Any]:
    scoped = int(counts.get("scoped", 0))
    unique = int(counts.get("unique", 0))
    ambiguous = int(counts.get("ambiguous", 0))
    external = int(counts.get("external", 0))
    return {
        "language": language,
        "scoped": scoped,
        "unique": unique,
        "ambiguous": ambiguous,
        "external": external,
        "total": scoped + unique + ambiguous + external,
    }


def resolution_rates(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """#3331: per-language rows plus a repository row (`language` '*'), each with
    the count of (caller, callee) pairs in every resolution class and their total.
    Languages with no pairs are omitted; an empty repository gives no rows."""
    rows = [_rate_row(lang, counts) for lang, counts in sorted((stats.get("by_language") or {}).items())]
    rows = [r for r in rows if r["total"]]
    if rows:
        repo = Counter[str]()
        for r in rows:
            for c in RESOLUTION_CLASSES:
                repo[c] += r[c]
        rows.insert(0, _rate_row("*", repo))
    return rows


def confident_file_pairs(sites: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    """#3333: (caller file, callee file) -> how many calling functions link to
    it confidently (scoped/unique), across files only. What the dependency
    graph adds as call edges. A constructor call that reached a class counts:
    the caller depends on the class's file either way."""
    pairs: Counter[tuple[str, str]] = Counter()
    for s in sites:
        dst = s.get("dst_path")
        # #3362: a transfer (COBOL GO TO) never joins the file graph.
        if s.get("kind", "call") != "call":
            continue
        if dst and s.get("resolution") in CONFIDENT_RESOLUTIONS and dst != s.get("src_path"):
            pairs[(s.get("src_path", ""), dst)] += 1
    return dict(pairs)
