# ==============================================================================
# GitGalaxy Core: Idiom-Wrapper Resolver (#3313 step 3)
#
# PURPOSE:
# `wrapper_extractor.py` records, per file, the short functions and `#define`
# aliases that COULD be wrappers and every unqualified call site. This module
# sees the whole repository and decides: which of them ARE thin wrappers over a
# literal-vocabulary rule, and how many call sites resolve to each. The answer
# is a fact channel (wrapper_data), not a count: the literal signals are
# unchanged, and nothing here enters a rule, a score or the dependency graph.
#
# THE DECISION RULES ARE MEASURED, NOT CHOSEN (epic #3313, steps 1-2), and the
# channel stays INSIDE what was measured (`RULE_SCOPE`):
#   - debug_prints / panics_and_aborts: function wrappers whose body hits the
#     rule itself, in every by-name language -- step 1's hand-labelled shape.
#     Short (<= 8 LOC), engine span aligned, and NO branches: a function that
#     exists to print or abort does so unconditionally, and the no-branch filter
#     took labelled precision from 32% to 77% (98% site-weighted) with no
#     labelled wrapper's call sites lost. No closure: chains through these rules
#     were never measured.
#   - memory_alloc: C-preprocessor languages only (step 2 measured curl and
#     CPython; other languages' allocation vocabulary -- JS `new`, Go `make` --
#     is a different thing and was not). Functions (<= 12 LOC, aligned, branches
#     ALLOWED: real allocator wrappers guard size/NULL, and the no-branch filter
#     dropped 507 of CPython's call sites), function-like `#define` aliases, and
#     the closure between them (curl's `Curl_safefree` -> `curlx_free`, CPython's
#     `PyMem_New` -> `PyMem_Malloc`), bounded at `CLOSURE_DEPTH` rounds.
#   - Resolution, for call sites AND closure edges alike: an unqualified call
#     reaches a FUNCTION wrapper only through a definition in the caller's own
#     file, else exactly one definition in the repository; zero or several
#     credit nothing, and a METHOD is never a target. "Several" counts
#     definitions, not files: a test file with ten nested `def f` makes its own
#     bare `f(` ambiguous (CPython's Lib/test credited one `f` with 93 calls
#     before this was counted). A macro alias resolves by
#     name: several `#ifdef` definitions of one macro are normal, and any of
#     them being an alias makes it one.
#   - A wrapper nobody calls hides nothing, so only wrappers with at least one
#     resolved call site are recorded.
# ==============================================================================
import collections
from typing import Any, Optional

from gitgalaxy.core.wrapper_extractor import PREPROCESSOR_LANGS

# rule -> (max LOC, require zero branches, language scope or None for all by-name
# languages, closure allowed). See the header for the evidence behind each value.
RULE_SCOPE: dict[str, tuple[int, bool, Optional[frozenset], bool]] = {
    "debug_prints": (8, True, None, False),
    "panics_and_aborts": (8, True, None, False),
    "memory_alloc": (12, False, PREPROCESSOR_LANGS, True),
}
# Kept for readers of the (max LOC, no-branch) pair alone.
RULE_FILTERS: dict[str, tuple[int, bool]] = {r: (v[0], v[1]) for r, v in RULE_SCOPE.items()}
CLOSURE_DEPTH = 6


def _passes(candidate: dict[str, Any], rule: str) -> bool:
    max_loc, no_branches, _, _ = RULE_SCOPE[rule]
    if candidate["method"] or not candidate["aligned"] or candidate["loc"] > max_loc:
        return False
    return not (no_branches and candidate["branches"])


def resolve_wrappers(parsed_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every idiom wrapper in the repository with its resolved call sites.

    Each row: {path, name, kind ("function" | "macro"), rule, via, call_sites,
    calling_files}. `via` is "primitive" when the body hits the rule itself, or
    "via <wrapper>" when it reaches the rule through another wrapper. `path` is
    the defining file (a macro's first definition, in path order). Rows are
    sorted, so the output is deterministic whatever the scan order.
    """
    facts: list[tuple[str, str, dict[str, Any]]] = [
        (f.get("path", ""), f.get("lang_id", ""), f["wrapper_facts"]) for f in parsed_files if f.get("wrapper_facts")
    ]
    facts.sort(key=lambda plf: plf[0])
    # function name -> {defining file -> how many definitions it holds}
    definitions: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for path, _, f in facts:
        for name, count in f.get("defined", {}).items():
            definitions[name][path] = count

    rows: list[dict[str, Any]] = []
    for rule, (_, _, scope, closure) in RULE_SCOPE.items():
        in_scope = [(p, f) for p, lang, f in facts if scope is None or lang in scope]
        eligible = [(p, c) for p, f in in_scope for c in f.get("candidates", []) if _passes(c, rule)]
        macros: dict[str, list[tuple[str, dict[str, Any]]]] = collections.defaultdict(list)
        if closure:
            for p, f in in_scope:
                for m in f.get("macros", []):
                    macros[m["name"]].append((p, m))
        # function name -> {defining path -> via}; macro name -> {file, via}
        functions: dict[str, dict[str, str]] = collections.defaultdict(dict)
        aliases: dict[str, dict[str, str]] = {}

        def _target(
            caller: str,
            callee: str,
            _aliases: dict[str, dict[str, str]] = aliases,
            _functions: dict[str, dict[str, str]] = functions,
        ) -> Optional[str]:
            """The defining path an unqualified `callee(` from `caller` reaches.

            The two maps are bound as defaults (not captured) so the closure is
            tied to THIS rule's wrappers, never a later iteration's (ruff B023)."""
            if callee in _aliases:
                return _aliases[callee]["file"]
            if callee not in _functions:
                return None
            defs = definitions[callee]
            if caller in defs:
                # The caller's own file wins, but only if it defines the name once.
                return caller if defs[caller] == 1 and caller in _functions[callee] else None
            if sum(defs.values()) == 1:
                (only,) = defs
                return only if only in _functions[callee] else None
            return None

        for depth in range(CLOSURE_DEPTH + 1):
            grew = False
            for path, cand in eligible:
                name = cand["name"]
                if path in functions.get(name, {}) or name in aliases:
                    continue
                via = "primitive" if rule in cand["hits"] else None
                if not via and closure and depth:
                    via = next((f"via {c}" for c in cand["callees"] if c != name and _target(path, c)), None)
                if via:
                    functions[name][path] = via
                    grew = True
            for name, defs in macros.items():
                if name in aliases or name in functions:
                    continue
                for path, m in defs:
                    via = "primitive" if rule in m["hits"] else None
                    if not via and depth:
                        via = next(
                            (f"via {c}" for c in m["called"] if c != name and _target(path, c)),
                            None,
                        )
                    if via:
                        aliases[name] = {"file": min(p for p, _ in defs), "via": via}
                        grew = True
                        break
            if depth and not grew:
                break
            if not closure:
                break

        sites: collections.Counter[tuple[str, str]] = collections.Counter()
        # (wrapper, defining file) -> {calling file -> call sites there}
        callers: dict[tuple[str, str], collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for path, f in in_scope:
            for callee, count in f.get("calls", {}).items():
                target = _target(path, callee)
                if target is None:
                    continue
                sites[(callee, target)] += count
                callers[(callee, target)][path] += count

        for (name, target), count in sites.items():
            macro = aliases.get(name)
            rows.append(
                {
                    "path": target,
                    "name": name,
                    "kind": "macro" if macro else "function",
                    "rule": rule,
                    "via": macro["via"] if macro else functions[name][target],
                    "call_sites": count,
                    "calling_files": len(callers[(name, target)]),
                    # #3313 step 4: where those call sites are, per calling file --
                    # the input of each file's `wrapped_<rule>` count. Not persisted
                    # in wrapper_data (the per-file totals are, on file_data).
                    "callers": dict(sorted(callers[(name, target)].items())),
                }
            )
    rows.sort(key=lambda r: (r["path"], r["rule"], r["name"]))
    return rows


# The rules a file carries a `wrapped_<rule>` count for (#3313 step 4). Every
# file gets all three, 0 when none of its call sites reach a wrapper.
WRAPPED_RULES = tuple(RULE_SCOPE)


def wrapped_site_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """{calling file -> {rule -> call sites in it that resolve to a wrapper of rule}}.

    The derived, wrapper-aware count of #3313 step 4
    (docs/wrapper_aware_count_contract.md): a site-kind count in the same unit as
    the literal rule, so literal + wrapped counts distinct sites that reach the
    behaviour directly or through a project wrapper.
    """
    out: dict[str, dict[str, int]] = collections.defaultdict(lambda: dict.fromkeys(WRAPPED_RULES, 0))
    for row in rows:
        for path, count in row.get("callers", {}).items():
            out[path][row["rule"]] += count
    return dict(out)


def attach_wrappers(parsed_files: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    """Hang the resolution back on the files, for the recorders.

    - `idiom_wrappers` on each DEFINING file: the wrappers it defines
      (presence-keyed; a file that defines none gets none).
    - `wrapped_sites` on EVERY file: {rule -> call sites in it that go through a
      wrapper}, all rules present and 0 when none. Recomputed every scan, full or
      delta, so it is never restored from a previous run.
    """
    by_path: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_path[row["path"]].append(row)
    wrapped = wrapped_site_counts(rows)
    for f in parsed_files:
        path = f.get("path", "")
        found = by_path.get(path)
        if found:
            f["idiom_wrappers"] = found
        else:
            f.pop("idiom_wrappers", None)
        f["wrapped_sites"] = wrapped.get(path, dict.fromkeys(WRAPPED_RULES, 0))
