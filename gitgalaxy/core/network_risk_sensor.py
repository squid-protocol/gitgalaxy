# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
# ==============================================================================
import logging
import math
import posixpath
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.core.graph_engine import (
    GraphIndex,
    WorkBudget,
    WorkBudgetExceeded,
    articulation_point_count,
    betweenness_centrality,
    closeness_and_path_length,
    degree_assortativity,
    louvain_modularity,
    nodes_in_cycles,
    pagerank,
)
from gitgalaxy.core.invocation_resolver import PROGRAM_DECLARING_LANGUAGES
from gitgalaxy.core.path_proximity import proximity_rank
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# #2540: languages whose import/module references resolve case-insensitively
# (fortran `USE A` binds a.f90, cobol `COPY A.` binds a.cpy, haskell's
# necessarily-capitalized `import A` may live in a.hs). Declared per-language
# via the "case_insensitive_imports" flag on each language DEFINITION;
# resolution for every other language stays strictly case-sensitive.
# #3333: the weight of a call-implied edge -- a file that calls into another
# without importing it. The same as one plain import (1.0): a confident call is
# at least as real a dependency as an import statement, and no stronger. Only
# pairs no import already joins get one, so an import-and-call pair keeps its
# import weight and a pair is never counted twice.
CALL_EDGE_WEIGHT = 1.0

CASE_INSENSITIVE_IMPORT_LANGS = frozenset(
    lang_id for lang_id, definition in LANGUAGE_DEFINITIONS.items() if definition.get("case_insensitive_imports")
)

# #3199: languages whose import statement names a library member that is pasted
# into the importing compilation unit -- cobol/hlasm/bms `COPY`, pli `%INCLUDE`.
# A member is source in the importing language by construction, so an ambiguous
# copied name is resolved within that language or not at all. Declared per
# language via the "imports_are_source_members" flag on each DEFINITION.
SOURCE_MEMBER_IMPORT_LANGS = frozenset(
    lang_id for lang_id, definition in LANGUAGE_DEFINITIONS.items() if definition.get("imports_are_source_members")
)

# #2668: leading relative-path markers are path syntax, not part of the
# imported target's name -- "./b.sh" and "../lib/helper.js" name b.sh and
# lib/helper.js. Anchored and bounded by the input's own length; no
# backtracking risk (single non-overlapping alternative, fixed-width group).
LEADING_RELATIVE_MARKER = re.compile(r"^(?:\.{1,2}/)+")

# #3553: languages whose import is resolved against the IMPORTING file's own
# directory before any search path -- C/C++/Objective-C `#include "x.h"`, Ruby
# `require_relative`, Zig `@import("x.zig")`. Declared per language via the
# "imports_resolve_from_importer_dir" flag on each DEFINITION. (A `./`/`../`
# token is resolved that way in every language.)
IMPORTER_DIR_FIRST_LANGS = frozenset(
    lang_id
    for lang_id, definition in LANGUAGE_DEFINITIONS.items()
    if definition.get("imports_resolve_from_importer_dir")
)

# #3545: a Python module token as the import statement spells it -- `a.b`,
# `.a`, `..`, never a path. Bounded, linear: no nested quantifiers.
_DOTTED_MODULE = re.compile(r"\.{0,16}(?:[A-Za-z_]\w{0,255}(?:\.[A-Za-z_]\w{0,255}){0,64})?")

# #3554: the module name of a Rust `mod name;` declaration.
_MODULE_NAME = re.compile(r"[A-Za-z_]\w{0,127}")
_MODULE_TREE_OWNERS = frozenset({"mod.rs", "lib.rs", "main.rs", "build.rs"})
_CRATE_ROOT_DIRS = frozenset({"tests", "examples", "benches"})

# #3552: an ESM import spells a TypeScript source by its EMITTED name
# (`./x.js` for x.ts); the compiler maps it back to one of these.
_ESM_EMITTED_EXTS = frozenset({".js", ".jsx", ".mjs", ".cjs"})
_ESM_SOURCE_EXTS = (".ts", ".tsx", ".mts", ".cts", ".d.ts", ".js", ".jsx", ".mjs", ".cjs")

# #3544: languages whose dotted/compound import token IS the target's path
# (`pkg.utils` lives at .../pkg/utils.*): a candidate must end in that path even
# when it is the only file with the name. Declared per language via the
# "import_path_mirrors_module_path" flag on each DEFINITION.
MODULE_PATH_MIRROR_LANGS = frozenset(
    lang_id for lang_id, definition in LANGUAGE_DEFINITIONS.items() if definition.get("import_path_mirrors_module_path")
)

# #3037/#3038: the deterministic work budget for each hop-count path metric.
# Closeness and average path length share one search; betweenness and Louvain
# modularity (#3039) each run their own.
# It counts edges scanned across every file's breadth-first search. 50M is about
# 3 s of pure-Python search; past it the metric is None ("not computed"), never
# 0.0. It replaced node-count cutoffs and sampling -- closeness skipped above
# 1,500 files, path length and modularity above 5,000, betweenness sampled to 100 sources above
# 500 -- on graphs like the 2,817-file language-crucible one, whose searches take
# about 2 ms each.
PATH_METRICS_WORK_BUDGET = 50_000_000


def _without_extension(path_str: str) -> str:
    """
    Drops a trailing file extension from a slash-separated token, leaving
    everything else untouched. Hand-rolled rather than
    `PurePosixPath.with_suffix("")` because import tokens are arbitrary
    captured text: `.`, `..` and `` all reach here and all raise from
    pathlib. A leading dot is a hidden-file marker, not an extension.
    """
    name = path_str.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    if dot <= 0:
        return path_str
    return path_str[: len(path_str) - (len(name) - dot)]


class NetworkRiskSensor:
    """
    The GitGalaxy Network Risk Sensor (Graph Topology & Blast Radius).

    PURPOSE: Ingests the flat list of parsed files, wires them into a Directed Graph (DAG)
    using raw_imports, and calculates Ecosystem Roles, PageRank, and
    Vector-Weighted Systemic Threats.
    """

    def __init__(self, parent_logger: Optional[logging.Logger] = None):
        self.logger = parent_logger.getChild("network_sensor") if parent_logger else logging.getLogger("network_sensor")
        self.RISK_SCHEMA = RECORDING_SCHEMAS.get("RISK_SCHEMA", [])
        # #2992: the resolved edge list of the most recent build_dependency_graph
        # call. The graph is discarded once its degree/centrality math is done;
        # this is the only copy that survives it, and record_keeper persists it
        # as the edge_data table. Deliberately not written into file telemetry
        # or the returned macro metrics -- both reach the audit/GPU JSON exports.
        self.dependency_edges: list[dict[str, Any]] = []
        # #perf: memoized extension-stripped candidate paths for Stage-2 import
        # disambiguation. On generated SDKs (many files share a stem) a single
        # token matches thousands of candidates, so _resolve_target stripped the
        # suffix millions of times -- via pathlib, the dominant cost of the whole
        # graph phase. Candidate paths are drawn from the repo's ~N files, so
        # memoizing collapses those millions of computes to one per unique path.
        self._stem_cache: dict[str, str] = {}
        # #3545/#3553: slash-normalized path -> the scan's own path string, for
        # the location-based stages of _resolve_target. Rebuilt with the
        # resolution map by _build_resolution_map.
        self._by_norm_path: dict[str, str] = {}

    def _build_resolution_map(self, files: list[dict[str, Any]]) -> dict[str, list[str]]:
        """
        Maps each lookup key (full path, filename, stem) to ALL candidate file
        paths sharing that key — never silently overwrites on duplicate
        filenames. Full-path keys are always unambiguous; name/stem keys may
        resolve to multiple candidates in monorepos with duplicate filenames
        across directories.
        """
        resolution_map: dict[str, list[str]] = defaultdict(list)
        self._by_norm_path = {}
        for f in files:
            path = f.get("path", "")
            if not path:
                continue
            self._by_norm_path.setdefault(path.replace("\\", "/"), path)
            name = f.get("name", Path(path).name)
            stem = Path(path).stem

            resolution_map[path].append(path)
            if name:
                resolution_map[name].append(path)
            if stem:
                resolution_map[stem].append(path)

        return resolution_map

    def _build_folded_resolution_map(self, files: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
        """
        #2540: derives per-language lowercase-keyed views of the resolution
        keys so imports from case-insensitive-resolution languages (fortran,
        cobol, haskell — see CASE_INSENSITIVE_IMPORT_LANGS) can fall back to a
        case-folded lookup. Kept separate from the exact-case map so
        case-sensitive languages never gain cross-case resolution, and so
        exact-case matches always win first even for the folding languages.

        Folding is a property of the *importing* language's resolution rules,
        so each language's folded view holds only that language's own files —
        haskell's `import Text.Pandoc.Generic` must not fold onto a go file
        named generic.go just because the stems collide case-insensitively.
        (The exact-case stages keep their long-standing language-agnostic
        stem matching; only the folded fallback is scoped.)
        """
        folded_maps: dict[str, dict[str, list[str]]] = {}
        for f in files:
            lang = str(f.get("lang_id", "")).lower()
            if lang not in CASE_INSENSITIVE_IMPORT_LANGS:
                continue
            path = f.get("path", "")
            if not path:
                continue
            lang_map = folded_maps.setdefault(lang, defaultdict(list))
            name = f.get("name", Path(path).name)
            stem = Path(path).stem
            lang_map[path.lower()].append(path)
            if name:
                lang_map[name.lower()].append(path)
            if stem:
                lang_map[stem.lower()].append(path)
        return folded_maps

    @staticmethod
    def _build_file_facts(files: list[dict[str, Any]]) -> dict[str, tuple[str, bool]]:
        """#3199: path -> (language id, declares a program), for Stage-3 narrowing.

        Both facts are already in the parsed file; this is only the lookup the
        resolver needs, keyed by the same path strings the resolution map
        stores. `declares a program` is "has at least one `classes` entry", and
        it is meaningful only for the languages where that means a compilation
        unit -- `_narrow_ambiguous` is what limits its use to those.
        """
        facts: dict[str, tuple[str, bool]] = {}
        for f in files:
            path = f.get("path", "")
            if path:
                facts[path] = (str(f.get("lang_id", "")).lower(), bool(f.get("classes")))
        return facts

    def _stem_path(self, candidate: str) -> str:
        """Extension-stripped, slash-normalized candidate path, memoized per path.

        Equal to `str(Path(candidate).with_suffix("")).replace("\\", "/")` for real
        file paths (verified 0 mismatches over 24,948 corpus paths), but computed
        with the existing pure-string `_without_extension` instead of constructing a
        pathlib.Path. Stage-2 disambiguation calls this once per candidate and a
        single token can match thousands of candidates, so the per-call cost and the
        cross-edge repetition both matter -- hence the cache.
        """
        stem = self._stem_cache.get(candidate)
        if stem is None:
            stem = _without_extension(candidate.replace("\\", "/"))
            self._stem_cache[candidate] = stem
        return stem

    def _resolve_target(
        self,
        target_token: str,
        resolution_map: dict[str, list[str]],
        curr_path: str,
        folded_maps: Optional[dict[str, dict[str, list[str]]]] = None,
        fold_lang: Optional[str] = None,
        src_lang: Optional[str] = None,
        file_facts: Optional[dict[str, tuple[str, bool]]] = None,
    ) -> Optional[str]:
        """
        Resolves an import token to a single file path, refusing to guess when
        genuinely ambiguous rather than silently misattributing an edge.

        When `fold_lang` is set (the importing file's language resolves
        imports case-insensitively, #2540) and no exact-case key matches, the
        lookup retries against that language's own folded map with a
        lowercased token. Exact matches always win first, so mixed-case repos
        keep their precise edges.

        `src_lang` (the importing file's language) and `file_facts` (see
        `_build_file_facts`) feed #3199's Stage 3, which decides an otherwise
        ambiguous stem from the repository's own facts. Without them the
        resolver behaves exactly as it did before #3199 and drops the edge.
        """
        src_def = LANGUAGE_DEFINITIONS.get(src_lang or "", {})
        # #3554: a language whose module separator is not `.` (perl
        # `HTTP::Headers` -> HTTP/Headers.pm) spells the path with it.
        separator = src_def.get("import_path_separator")
        if separator:
            target_token = target_token.replace(separator, "/")

        # #3545: Python resolves a module by its own rule (source roots and
        # package `__init__` files), never by a bare-stem search.
        # A path- or file-name-shaped token (`src/lib.py`, `f1.py` -- a caller
        # that already holds the file) keeps the name search below.
        init_file = src_def.get("package_init_file")
        if init_file and _DOTTED_MODULE.fullmatch(target_token) and not target_token.endswith((".py", ".pyi")):
            return self._resolve_package_module(target_token, curr_path, resolution_map, init_file)

        # #3554: a body-less Rust `mod name;` (recorded as `./name`) names name.rs
        # or name/mod.rs in its owner's module directory -- and nothing else. One
        # the tree cannot place (a `#[path]` module, a file outside the scan) draws
        # no edge: a name search would link it to any same-named file, any language.
        if src_def.get("imports_follow_module_tree") and target_token.startswith("./"):
            module = target_token[2:]
            if _MODULE_NAME.fullmatch(module):
                return self._resolve_module_tree(module, curr_path)

        # #3553/#3552: a `./`/`../` token -- and any token of a language that
        # searches the importing file's directory first -- names a location.
        # Try it before the name search, which drops a name that repeats
        # elsewhere in the repo even though the location pins it.
        if target_token.replace("\\", "/").startswith(("./", "../")) or src_lang in IMPORTER_DIR_FIRST_LANGS:
            located = self._resolve_from_importer_dir(target_token, curr_path, resolution_map, src_lang, file_facts)
            if located is not None:
                return located

        resolved = self._resolve_by_name(
            target_token, resolution_map, curr_path, folded_maps, fold_lang, src_lang, file_facts
        )
        # #3554: a Java `import static a.b.C.member` / nested `a.b.Outer.Inner`
        # names something INSIDE a class file; when the full name resolves to
        # nothing, the class it belongs to is the file.
        if resolved is None and src_def.get("imports_may_name_member"):
            parts = target_token.split(".")
            for cut in range(1, min(3, len(parts) - 2) + 1):
                resolved = self._resolve_by_name(
                    ".".join(parts[:-cut]), resolution_map, curr_path, folded_maps, fold_lang, src_lang, file_facts
                )
                if resolved is not None:
                    break
        return resolved

    def _resolve_by_name(
        self,
        target_token: str,
        resolution_map: dict[str, list[str]],
        curr_path: str,
        folded_maps: Optional[dict[str, dict[str, list[str]]]],
        fold_lang: Optional[str],
        src_lang: Optional[str],
        file_facts: Optional[dict[str, tuple[str, bool]]],
    ) -> Optional[str]:
        """The name search: a token's full path, file name or stem, disambiguated
        by the path context the token carries (Stages 1-3 below)."""
        # The historical form: every dot becomes a separator, which is what
        # lets a package-style token ("pkg.utils") find utils.py.
        token_as_path = target_token.replace(".", "/").replace("\\", "/")
        bare_component = token_as_path.rsplit("/", 1)[-1]

        # #2668: that rewrite also shreds a relative import that carries its
        # own extension — "./b.sh" becomes "//b/sh", so the lookup key is the
        # *extension* ("sh"), nothing resolves, and shell/powershell/yaml/
        # javascript built no edges at all despite reporting dependency_links.
        # Read the token as a literal path first (leading "./" / "../"
        # stripped, dots left alone) and keep the dot rewrite as the last
        # fallback, so every token that resolved before still resolves the
        # same way — the path forms are only *tried* when they differ from
        # the token itself, i.e. exactly for relative and compound paths.
        literal_path = LEADING_RELATIVE_MARKER.sub("", target_token.replace("\\", "/"))
        literal_cmp = _without_extension(literal_path)

        # (lookup key, path context to disambiguate with in Stage 2), in
        # priority order and de-duplicated: exact token, literal relative
        # path, that path's final component, then the dot-rewritten
        # component. A key is compared against candidate paths with their
        # extension stripped, so the token's own extension comes off too.
        # A dict de-dupes by key with the first (highest-priority) context
        # winning, and preserves insertion order.
        lookup_forms: dict[str, str] = {}
        lookup_forms.setdefault(target_token, token_as_path)
        for form in (literal_path, literal_path.rsplit("/", 1)[-1]):
            if form and form != target_token:
                lookup_forms.setdefault(form, literal_cmp)
        lookup_forms.setdefault(bare_component, token_as_path)

        folded_hit = False
        match_cmp = token_as_path
        matched_key = None
        candidates = None

        # Stage 1: direct key lookup — handles full-path, bare-filename and
        # bare-stem tokens that match a stored key exactly (first form), the
        # #2668 literal-path forms next, and finally Stage 1b: compound
        # tokens (e.g. "service_b/utils" or "pkg.utils") are never stored as
        # map keys directly — resolution_map only holds full paths, bare
        # filenames and bare stems — so the dot-rewritten final component is
        # the last resort, giving Stage 2 something to disambiguate against.
        for key, cmp_context in lookup_forms.items():
            candidates = resolution_map.get(key)
            if candidates:
                match_cmp = cmp_context
                matched_key = key
                break

        # Stage 1c (#2540): case-insensitive-resolution languages retry the
        # same lookups case-folded, only after every exact-case form
        # misses — fortran `USE A` -> a.f90, cobol `COPY A.` -> a.cpy,
        # haskell `import A` -> a.hs. Scoped to the importing language's own
        # files so folding never invents a cross-language edge.
        if not candidates and fold_lang and folded_maps is not None:
            lang_map = folded_maps.get(fold_lang)
            if lang_map:
                folded_hit = True
                for key, cmp_context in lookup_forms.items():
                    candidates = lang_map.get(key.lower())
                    if candidates:
                        match_cmp = cmp_context
                        matched_key = key
                        break

        if not candidates:
            return None

        candidates = list(dict.fromkeys(candidates))  # de-dupe, preserve order
        if len(candidates) == 1:
            # #3544: in a language whose import path IS the file path, a token
            # that spells a package path (`starlette.requests`) only names a
            # file ending in that path. The one local `requests.py` is somebody
            # else's module, not a unique match. Only a match made through the
            # token's LAST SEGMENT is checked: a token that matched as a whole
            # file name or path (`dofile("x.lua")`) already named its file.
            if (
                src_lang in MODULE_PATH_MIRROR_LANGS
                and matched_key == bare_component
                and bare_component != target_token
                and "/" in match_cmp.strip("/")
            ):
                stem = self._stem_path(candidates[0])
                cmp_path = match_cmp.strip("/")
                if folded_hit:
                    stem, cmp_path = stem.lower(), cmp_path.lower()
                if not (stem == cmp_path or stem.endswith("/" + cmp_path)):
                    return None
            return candidates[0]

        # Stage 2: multiple files share this name/stem — disambiguate using
        # any path context already present in the token, comparing against
        # each candidate's path with its extension stripped. A case-folded
        # hit compares case-folded here too, for consistency with Stage 1c.
        cmp_token = match_cmp.lower() if folded_hit else match_cmp
        if folded_hit:
            path_matches = [c for c in candidates if self._stem_path(c).lower().endswith(cmp_token)]
        else:
            path_matches = [c for c in candidates if self._stem_path(c).endswith(cmp_token)]
        if len(path_matches) == 1:
            return path_matches[0]

        # Stage 3 (#3199): the token carries no path context that separates
        # these candidates. Dropping the edge outright threw away most real
        # COBOL copybook dependencies -- every `COPY CUSTCOPY` in
        # zopeneditor-sample (the member exists under two libraries) and 36 of
        # CBSA's 119 (`ACCTCTRL` names a .cpy, a .cbl, a .jcl and a .lked).
        # Narrow on what the repository actually knows, and only then give up.
        #
        # SCOPED TO `SOURCE_MEMBER_IMPORT_LANGS`, deliberately. #261 decided
        # that an ambiguous bare stem draws no edge, and for an ordinary
        # `import utils` that is still the honest answer: the resolver has no
        # model of the language's own module search order, and the nearest
        # same-named file is a guess dressed up as a rule. A `COPY` names a
        # library MEMBER, which is a much narrower relation -- same-language
        # source, never a program, found by searching a library list -- and
        # that is what the steps below can actually reason about. Widening this
        # to another language means overturning #261 for it, with evidence.
        #
        # Two shapes are NOT narrowed even there, because both are positive
        # evidence against every candidate rather than an absence of evidence:
        # an empty `path_matches` (the token spelled out a path no candidate
        # has), and a token that led with `./` or `../`, which names one exact
        # location relative to the importer -- PL/I's `%INCLUDE` is the member
        # form that can carry a quoted path.
        is_relative = target_token.replace("\\", "/").startswith(("./", "../"))
        if file_facts and path_matches and not is_relative and src_lang in SOURCE_MEMBER_IMPORT_LANGS:
            narrowed = self._narrow_ambiguous(path_matches, curr_path, src_lang, file_facts)
            if narrowed is not None:
                return narrowed

        # Still ambiguous — skip rather than misattribute.
        self.logger.debug(
            f"Ambiguous import token '{target_token}' matches {len(candidates)} "
            f"files {candidates}; skipping edge from '{curr_path}'."
        )
        return None

    def _resolve_from_importer_dir(
        self,
        target_token: str,
        curr_path: str,
        resolution_map: dict[str, list[str]],
        src_lang: Optional[str],
        file_facts: Optional[dict[str, tuple[str, bool]]],
    ) -> Optional[str]:
        """#3553/#3552: the file a token names RELATIVE TO THE IMPORTER, or None.

        `dirname(importer)/token` exactly. A token without an extension
        (`./db`, `require_relative 'request'`) then takes the one file with that
        extension-less path, else that path's `index` file (`./lib` ->
        lib/index.ts); a token spelled with an emitted JS extension also takes a
        TypeScript source there -- `./x.js` is `x.ts` in an ESM package, whose
        compiler maps the emitted name back (#3552). Any other extension names
        exactly that file. Several same-path
        files (`x.ts` beside `x.js`) are narrowed to the importer's language;
        still several, and nothing is claimed.
        """
        token = target_token.replace("\\", "/")
        base = posixpath.normpath(posixpath.join(posixpath.dirname(curr_path.replace("\\", "/")), token))
        if base == ".." or base.startswith("../"):
            return None
        exact = self._by_norm_path.get(base)
        if exact is not None:
            return exact
        # A token WITH an extension names that file: `<poll.h>` is never poll.c.
        # The one exception is the ESM spelling of a TypeScript source (#3552).
        ext = posixpath.splitext(base)[1].lower()
        if ext and ext not in _ESM_EMITTED_EXTS:
            return None
        allowed = _ESM_SOURCE_EXTS if ext else None
        for want in (_without_extension(base), posixpath.join(base, "index")):
            name = posixpath.basename(want)
            same = [
                c
                for c in dict.fromkeys(resolution_map.get(name, ()))
                if self._stem_path(c) == want and (allowed is None or c.lower().endswith(allowed))
            ]
            if len(same) > 1 and file_facts:
                same = [c for c in same if (file_facts.get(c) or ("", False))[0] == src_lang] or same
            if len(same) == 1:
                return same[0]
        return None

    def _resolve_module_tree(self, module: str, curr_path: str) -> Optional[str]:
        """#3554: the file a Rust `mod module;` in `curr_path` declares, or None.

        The owner's module directory is the file's own directory for a mod.rs or
        a crate root (lib.rs, main.rs, build.rs, a file directly in tests/,
        examples/ or benches/, a src/bin target), else `<dir>/<stem>/` (Rust 2018
        non-mod-rs modules); the module is `module.rs` or `module/mod.rs` there.
        """
        cur = curr_path.replace("\\", "/")
        directory, name = posixpath.split(cur)
        # A crate root (lib.rs, main.rs, build.rs, an integration test, example,
        # bench or src/bin target) and a mod.rs own their directory.
        owns_directory = (
            name in _MODULE_TREE_OWNERS
            or posixpath.basename(directory) in _CRATE_ROOT_DIRS
            or directory == "src/bin"
            or directory.endswith("/src/bin")
        )
        owner = directory if owns_directory else posixpath.join(directory, posixpath.splitext(name)[0])
        for rel in (posixpath.join(owner, module + ".rs"), posixpath.join(owner, module, "mod.rs")):
            hit = self._by_norm_path.get(posixpath.normpath(rel) if owner else rel)
            if hit is not None:
                return hit
        return None

    def _resolve_package_module(
        self,
        target_token: str,
        curr_path: str,
        resolution_map: dict[str, list[str]],
        init_file: str,
    ) -> Optional[str]:
        """#3545/#3544: Python's own module rule, or None.

        `a.b` is `a/b.py` or the package `a/b/__init__.py` under a SOURCE ROOT --
        a directory that is not itself a package (the repo root, `src/`, ...). So
        `import types` is the stdlib, not `fastapi/types.py` (that file is
        `fastapi.types`: `fastapi/` has an `__init__.py`), and `from fastapi
        import X` is `fastapi/__init__.py`, which a stem search can never find.
        Leading dots are relative to the importing package. Several matches
        draw no edge (#261).
        """
        dotted = target_token.replace("\\", "/")
        level = len(dotted) - len(dotted.lstrip("."))
        parts = [p for p in dotted.lstrip(".").split(".") if p]
        cur = curr_path.replace("\\", "/")
        if level:
            pkg = posixpath.dirname(cur).split("/") if posixpath.dirname(cur) else []
            if level - 1 > len(pkg):
                return None
            root = "/".join(pkg[: len(pkg) - (level - 1)] + parts)
            for rel in (root + ".py", posixpath.join(root, init_file) if root else init_file):
                hit = self._by_norm_path.get(rel)
                if hit is not None:
                    return hit
            return None
        if not parts:
            return None
        rel = "/".join(parts)
        matches = []
        for tail in (rel + ".py", rel + ".pyi", rel + "/" + init_file):
            for c in dict.fromkeys(resolution_map.get(posixpath.basename(tail), ())):
                cn = c.replace("\\", "/")
                if cn != tail and not cn.endswith("/" + tail):
                    continue
                prefix = cn[: -len(tail)].rstrip("/")
                if prefix and posixpath.join(prefix, init_file) in self._by_norm_path:
                    continue  # the match sits inside a package: it is `<pkg>.<rel>`, not `<rel>`
                matches.append(c)
        matches = list(dict.fromkeys(matches))
        # Several source roots holding the same module (`service_a/utils.py`,
        # `service_b/utils.py`) are the #261 case: which one wins is sys.path,
        # which the repository does not record, so nothing is claimed.
        return matches[0] if len(matches) == 1 else None

    def _narrow_ambiguous(
        self,
        candidates: list[str],
        curr_path: str,
        src_lang: Optional[str],
        file_facts: dict[str, tuple[str, bool]],
    ) -> Optional[str]:
        """#3199: the one copied member the repository's own facts single out, or None.

        Called only for a `SOURCE_MEMBER_IMPORT_LANGS` importer (see the caller
        for why). Three narrowings, in order:

        1. **The importer's own language.** A copybook is source in the
           language that copies it, so `COPY CUSTOMER` in a COBOL program means
           CUSTOMER.cpy and not the CUSTOMER.java beside it -- and when NO
           candidate is in that language the edge is dropped rather than
           guessed across the boundary. CBSA proves what the alternative costs:
           `COPY BNK1CAM` names a BMS symbolic map generated at build time and
           absent from the repository, and the nearest same-named file is the
           map's build JCL. (That cross-language link belongs to #3122.)
        2. **Not itself a program**, for the languages whose `classes` entries
           are whole compilation units (`PROGRAM_DECLARING_LANGUAGES`, cobol
           today). COBOL's `COPY` names a library MEMBER, which is a fragment
           pasted into a program and therefore never a program itself: given
           ACCTCTRL.cpy and ACCTCTRL.cbl, the PROGRAM-ID disqualifies the .cbl.
           This is what step 3 alone gets wrong -- BANKDATA.cbl's nearest
           ACCTCTRL is the program in its own directory.
        3. **Nearest** (`proximity_rank`): the longest shared directory prefix,
           then the shallower path -- the closest stand-in for the library
           concatenation order a real COPY is resolved by. That is the
           zopeneditor reading the answer key records: `COBOL/SAM1.cbl` takes
           the repository-wide `COPYBOOK/` library and `multiroot/sam/SAM1.cbl`
           takes the `multiroot/copybooks/` one inside its own workspace root.

        If two candidates are still equally near and equally shallow, nothing
        in the repository distinguishes them and the edge is dropped, exactly
        as before. Alphabetical order is not a reason to believe an edge.
        """
        candidates = [c for c in candidates if (file_facts.get(c) or ("", False))[0] == src_lang]
        if not candidates:
            return None
        if len(candidates) > 1 and src_lang in PROGRAM_DECLARING_LANGUAGES:
            members = [c for c in candidates if not (file_facts.get(c) or ("", False))[1]]
            if members:
                candidates = members

        if len(candidates) == 1:
            return candidates[0]
        ranked = sorted(candidates, key=lambda c: proximity_rank(c, curr_path))
        if proximity_rank(ranked[0], curr_path) != proximity_rank(ranked[1], curr_path):
            return ranked[0]
        return None

    @staticmethod
    def _fold_lang(f: dict[str, Any]) -> Optional[str]:
        """#2540: the file's language id if it resolves import targets case-insensitively, else None."""
        lang = str(f.get("lang_id", "")).lower()
        return lang if lang in CASE_INSENSITIVE_IMPORT_LANGS else None

    def extract_test_coverage_mapping(self, files: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """
        Maps function calls from test files to their imported production targets.
        Returns a dictionary mapping: production_file_path -> { production_function_name: [test_function_data] }

        DEFENSIVE DESIGN: Traditional code coverage only checks if a line was executed.
        By mapping outbound AST calls from tests to production targets, we can calculate
        the exact architectural "Dependency Blast Radius" of untested functions.
        """
        coverage_map: dict[str, dict[str, list[dict[str, Any]]]] = {}
        resolution_map = self._build_resolution_map(files)
        folded_maps = self._build_folded_resolution_map(files)
        file_facts = self._build_file_facts(files)

        # 2. Identify Test Files and extract their outgoing invocations
        for f in files:
            path = f.get("path", "")
            low_path = path.lower()

            # Structural heuristic for test files
            is_test = any(x in low_path for x in ["/test/", "/tests/", "test_", "_test", ".spec.", ".test."])
            if not is_test:
                continue

            # Identify which production files this test file imports
            target_paths = set()
            for imp in f.get("raw_imports", []):
                target_token = imp[0] if isinstance(imp, tuple) and len(imp) == 2 else imp
                target_path = self._resolve_target(
                    target_token,
                    resolution_map,
                    path,
                    folded_maps=folded_maps,
                    fold_lang=self._fold_lang(f),
                    src_lang=str(f.get("lang_id", "")).lower(),
                    file_facts=file_facts,
                )

                if target_path and target_path != path:
                    target_paths.add(target_path)

            if not target_paths:
                continue

            # Map each test function's payload to the production functions it calls
            for test_func in f.get("functions", []):
                calls_out = test_func.get("calls_out_to", [])
                if not calls_out:
                    continue

                target_count = len(calls_out)
                test_payload = {
                    "impact": test_func.get("impact", 0.0),
                    "target_count": target_count,
                    "test_hits": test_func.get("hit_vector", {}).get("test", 0),
                    "test_skip_hits": test_func.get("hit_vector", {}).get("test_skip", 0),
                    "decorators": test_func.get("hit_vector", {}).get("decorators", 0),
                }

                for target_path in target_paths:
                    if target_path not in coverage_map:
                        coverage_map[target_path] = {}

                    for called_func_name in calls_out:
                        if called_func_name not in coverage_map[target_path]:
                            coverage_map[target_path][called_func_name] = []
                        coverage_map[target_path][called_func_name].append(test_payload)

        return coverage_map

    def _resolve_edges(self, parsed_files: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        """
        #2992: resolves every file's raw_imports into directed file-to-file
        edges, keyed (importer, imported) in first-occurrence order. Repeated
        imports of the same target collapse into one edge that keeps count:
        `import_statements` (resolved captures), `entity_imports` (the Level 2
        tuple form among them) and `weight` (1.0 per plain import, 1.5 per
        entity import, summed in capture order -- the exact float the DiGraph
        accumulated before this was factored out).

        The single resolver behind both graph builders, so the persisted edge
        list cannot drift from the degrees and pagerank computed off it.
        """
        resolution_map = self._build_resolution_map(parsed_files)
        folded_maps = self._build_folded_resolution_map(parsed_files)
        file_facts = self._build_file_facts(parsed_files)
        edges: dict[tuple[str, str], dict[str, Any]] = {}

        for f in parsed_files:
            curr_path = f.get("path", "")
            fold_lang = self._fold_lang(f)
            src_lang = str(f.get("lang_id", "")).lower()

            for imp in f.get("raw_imports", []):
                # Check if it's a Level 2 Tuple (Entity Import) or Level 1 String
                if isinstance(imp, tuple) and len(imp) == 2:
                    target_token, entity = imp
                else:
                    target_token = imp
                    entity = None

                target_path = self._resolve_target(
                    target_token,
                    resolution_map,
                    curr_path,
                    folded_maps=folded_maps,
                    fold_lang=fold_lang,
                    src_lang=src_lang,
                    file_facts=file_facts,
                )
                if target_path and target_path != curr_path:
                    edge = edges.setdefault(
                        (curr_path, target_path), {"weight": 0.0, "import_statements": 0, "entity_imports": 0}
                    )
                    # Edge weight can be increased if specific entities are highly coupled
                    edge["weight"] += 1.5 if entity else 1.0
                    edge["import_statements"] += 1
                    if entity:
                        edge["entity_imports"] += 1

        return edges

    def _publish_edges(self, edges: dict[tuple[str, str], dict[str, Any]]) -> None:
        """#2992: exposes the resolved edges as `self.dependency_edges` for the recorder."""
        # An import edge carries no edge_kind of its own; a call edge (#3333)
        # says 'fcall', which the spread below keeps.
        self.dependency_edges = [
            {"src": src, "dst": dst, "edge_kind": "import", **attrs} for (src, dst), attrs in edges.items()
        ]

    def _network_metrics(
        self,
        f: dict[str, Any],
        pr_score: Optional[float],
        betweenness: Optional[float],
        closeness: Optional[float],
        in_d: int,
        out_d: int,
    ) -> dict[str, Any]:
        """
        One file's `network_metrics`, shared by both graph builders. #3027: a
        metric that was not computed (betweenness or closeness past its work
        budget, a failed computation) is None, never
        a 0.0 placeholder -- a 0.0 reads as a measurement and every consumer drew
        conclusions from it (a "Containment (Low Risk)" verdict, zero-score
        bottleneck rankings, zeroed archetype features).
        """
        total_edges = in_d + out_d
        if total_edges == 0:
            ecosystem_role = "Isolated/Orphan"
            producer_ratio = 0.0
        else:
            producer_ratio = in_d / total_edges
            if producer_ratio > 0.8:
                ecosystem_role = "Pure Producer (Foundation)"
            elif producer_ratio < 0.2:
                ecosystem_role = "Pure Consumer (Orchestrator)"
            else:
                ecosystem_role = "Transceiver (Middle-Tier)"

        # --- Multi-Dimensional Systemic Threat Vector ---
        # PageRank is usually a tiny decimal (e.g., 0.0005). We normalize it
        # by multiplying by 1000 to make the scale human/LLM readable.
        # Systemic Threat = Dependency Blast Radius * Local Vulnerability Severity
        pagerank_score: Optional[float] = None
        blast_radius: Optional[float] = None
        systemic_threat_vector: Optional[list[float]] = None
        if pr_score is not None:
            pr_normalized = pr_score * 1000
            local_risk_vector = f.get("risk_vector", [0.0] * len(self.RISK_SCHEMA))
            pagerank_score = round(pr_score, 6)
            blast_radius = round(pr_normalized, 3)
            systemic_threat_vector = [
                round(pr_normalized * (local_risk / 100.0), 3) for local_risk in local_risk_vector
            ]

        return {
            "pagerank_score": pagerank_score,
            "normalized_blast_radius": blast_radius,
            "betweenness_score": None if betweenness is None else round(betweenness, 6),
            "closeness_score": None if closeness is None else round(closeness, 6),
            "in_degree": in_d,
            "out_degree": out_d,
            "producer_ratio": round(producer_ratio, 3),
            "ecosystem_role": ecosystem_role,
            "systemic_threat_vector": systemic_threat_vector,
        }

    @staticmethod
    def _graph_index(parsed_files: list[dict[str, Any]], edges: dict[tuple[str, str], dict[str, Any]]) -> GraphIndex:
        """
        #3034: the CSR index every native graph metric reads, built once per scan
        from the resolved edges: files in scan order, edges in first-occurrence
        order, each edge weighted as the DiGraph's.
        """
        return GraphIndex(
            (f.get("path", "") for f in parsed_files),
            ((src, dst, attrs["weight"]) for (src, dst), attrs in edges.items()),
        )

    def _native_pagerank(self, index: GraphIndex) -> dict[str, float]:
        """
        #3027: the ONE PageRank both graph builders use, fed the same index
        (file order, first-occurrence edge order), so the two modes produce
        the same floats, not merely the same rounded values. Full precision used to
        call nx.pagerank, which in networkx 3.x dispatches to a numpy/scipy backend
        that networkx itself does not install -- with networkx alone it raised and
        every file's PageRank was silently lost -- and whose implementation can
        change between networkx releases. One implementation means no mode split
        and no installed version can move the numbers. Empty on failure, so every
        file reads None ("not computed"), never 0.0.
        """
        try:
            return dict(zip(index.nodes, pagerank(index)))
        except Exception as e:
            self.logger.warning(f"PageRank failed to converge, leaving it unset (None): {e}")
            return {}

    def _betweenness(self, index: GraphIndex) -> dict[str, Optional[float]]:
        """
        #3038: exact hop-count betweenness, native in both modes (see
        graph_engine.betweenness_centrality), so the two modes produce the same
        values. Past PATH_METRICS_WORK_BUDGET it is None ("not computed"),
        never 0.0.
        """
        try:
            values = betweenness_centrality(index, WorkBudget(PATH_METRICS_WORK_BUDGET))
        except WorkBudgetExceeded as e:
            self.logger.info(f"Betweenness past its work budget, leaving it unset (None): {e}")
            return dict.fromkeys(index.nodes)
        return dict(zip(index.nodes, values))

    def _path_metrics(self, index: GraphIndex) -> tuple[dict[str, Optional[float]], Optional[float]]:
        """
        #3037: per-file closeness and the repo's average path length, from one
        native search in both modes (see graph_engine.closeness_and_path_length),
        so the two modes produce the same values. Computed at every graph size;
        past PATH_METRICS_WORK_BUDGET both are None ("not computed"), never 0.0.
        """
        try:
            closeness, avg_path_length = closeness_and_path_length(index, WorkBudget(PATH_METRICS_WORK_BUDGET))
        except WorkBudgetExceeded as e:
            self.logger.info(f"Closeness / avg path length past their work budget, leaving them unset (None): {e}")
            return dict.fromkeys(index.nodes), None
        return dict(zip(index.nodes, closeness)), avg_path_length

    def _topology_metrics(self, index: GraphIndex) -> dict[str, Optional[float]]:
        """
        The native repo-topology metrics, in both modes. All are None for a
        graph with no files, as the networkx path left them.
        - #3035: cyclic density (the share of files on a dependency cycle) and
          the articulation-point count, O(N + E)
        - #3036: degree assortativity, O(N + E). An undefined correlation (no
          edges, or a degree that never varies) is 0.0: the value stored when
          networkx returned NaN.
        - #3039: Louvain modularity, a faithful port of networkx's seeded
          `louvain_communities(U, seed=42)`. It is None when no file imports
          another (networkx divided by zero there), or past
          PATH_METRICS_WORK_BUDGET, which replaced the V > 5000 cutoff.
        """
        n = len(index.nodes)
        if n == 0:
            return {"modularity": None, "assortativity": None, "cyclic_density": None, "articulation_points": None}
        try:
            modularity = louvain_modularity(index, budget=WorkBudget(PATH_METRICS_WORK_BUDGET))
        except WorkBudgetExceeded as e:
            self.logger.info(f"Modularity past its work budget, leaving it unset (None): {e}")
            modularity = None
        assortativity = degree_assortativity(index)
        return {
            "modularity": None if modularity is None else round(modularity, 4),
            "assortativity": 0.0 if math.isnan(assortativity) else round(assortativity, 4),
            "cyclic_density": round(nodes_in_cycles(index) / n, 4),
            "articulation_points": articulation_point_count(index),
        }

    def resolve_import_edges(self, parsed_files: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        """#3333: stage 1 of the graph, on its own -- the import edges, published on
        `self.dependency_edges` so the call resolver (#3328), which reads them
        to scope a call to an imported file, can run before the metrics do."""
        self.logger.info(f"Network Risk Sensor: resolving the import graph of {len(parsed_files)} files...")
        edges = self._resolve_edges(parsed_files)
        self._publish_edges(edges)
        return edges

    def build_dependency_graph(
        self,
        parsed_files: list[dict[str, Any]],
        call_pairs: Optional[dict[tuple[str, str], int]] = None,
        import_edges: Optional[dict[tuple[str, str], dict[str, Any]]] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Builds the directed graph and calculates multi-dimensional risk vectors.
        Modifies the 'telemetry' dictionary of each file in place, and leaves
        the resolved edge list on `self.dependency_edges` (#2992).

        `call_pairs` (#3333) are the call resolver's confident cross-file pairs
        (`call_resolver.confident_file_pairs`), (caller file, callee file) ->
        calling-function count. A pair no import already joins becomes an edge
        of kind 'fcall' at CALL_EDGE_WEIGHT, so a file that uses another without
        importing it (C across translation units, PHP/Ruby globals, same-package
        Java/Go) is connected in every graph metric. `import_edges` reuses a
        `resolve_import_edges` result instead of resolving again.
        """
        # 1. Resolve every file's imports into distinct directed edges (#2992),
        # then add the call-implied edges no import covers (#3333).
        edges = dict(import_edges) if import_edges is not None else self._resolve_edges(parsed_files)
        if import_edges is None:
            self.logger.info(f"Network Risk Sensor: resolving the import graph of {len(parsed_files)} files...")
        known = {f.get("path", "") for f in parsed_files}
        for (src, dst), n in (call_pairs or {}).items():
            if (src, dst) not in edges and src != dst and src in known and dst in known:
                edges[(src, dst)] = {
                    "edge_kind": "fcall",
                    "weight": CALL_EDGE_WEIGHT,
                    "import_statements": n,
                    "entity_imports": 0,
                }
        self._publish_edges(edges)

        # 2. Degree: distinct neighbouring files, one per edge (#3024).
        in_degrees = {f.get("path", ""): 0 for f in parsed_files}
        out_degrees = {f.get("path", ""): 0 for f in parsed_files}
        for src, dst in edges:
            out_degrees[src] = out_degrees.get(src, 0) + 1
            in_degrees[dst] = in_degrees.get(dst, 0) + 1

        # 3. Every graph metric, from the engine's own standard-library graph code
        # (#3027, #3034-#3040): one CSR index, then PageRank, betweenness,
        # closeness, avg path length and the repo topology. There is one builder
        # and no optional package: #3041 removed networkx, so every install
        # computes the same values.
        index = self._graph_index(parsed_files, edges)
        pagerank = self._native_pagerank(index)
        betweenness = self._betweenness(index)
        closeness, avg_path_length = self._path_metrics(index)
        topology = self._topology_metrics(index)

        # 4. Write telemetry back to each file.
        for f in parsed_files:
            path = f.get("path", "")
            if "telemetry" not in f:
                f["telemetry"] = {}
            f["telemetry"]["network_metrics"] = self._network_metrics(
                f,
                pagerank.get(path),
                betweenness.get(path),
                closeness.get(path),
                in_degrees.get(path, 0),
                out_degrees.get(path, 0),
            )
            # The strict directed in-degree replaces the old "popularity" integer.
            f["telemetry"]["popularity"] = in_degrees.get(path, 0)

        # 5. Repo-level topology. #473: a metric that was not computed is None,
        # never 0.0/0. A 0.0 modularity is a real score (no community structure),
        # so a failed or skipped computation must not look like one, and
        # consumers (record_keeper.py, llm_recorder.py) must not paper over None
        # with their own 0.0 fallback.
        macro_metrics: dict[str, Optional[float]] = {
            "modularity": topology["modularity"],
            "assortativity": topology["assortativity"],
            "cyclic_density": topology["cyclic_density"],
            "avg_path_length": None if avg_path_length is None else round(avg_path_length, 4),
            "articulation_points": topology["articulation_points"],
        }

        self.logger.info("Network Risk Sensor: Vector Mathematics & Graph Topology Complete.")
        return parsed_files, macro_metrics
