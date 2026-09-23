# ==============================================================================
# GitGalaxy Core: Idiom-Wrapper Extraction (#3313 step 3)
#
# PURPOSE:
# A literal-vocabulary rule (`debug_prints`, `panics_and_aborts`,
# `memory_alloc`) counts calls to a primitive by name. A project that wraps the
# primitive in its own helper hides every call site of that helper from the
# rule: fortran/wrf's `wrf_error_fatal` (`print *,string` then `stop`) has 166
# callers, and curl 8.18 moved 1,625 allocator call sites behind `curlx_*`
# macros, so its literal `memory_alloc` fell 82% while nothing changed. See
# docs/known_blind_spots.md.
#
# This module is the PER-FILE half of the wrapper fact channel. It records the
# raw facts a repo-wide resolver (`wrapper_resolver.py`) needs, because a
# wrapper and its callers almost never share a file:
#   - `defined`    every non-synthetic function name the file defines, with how
#                  many times (a test file's ten nested `def f` are ten
#                  definitions, and a bare `f(` there is ambiguous);
#   - `candidates` its short functions (<= CANDIDATE_MAX_LOC), each with the
#                  features the resolver's per-rule filter reads -- LOC, the
#                  engine's branch count, whether the engine's span is aligned
#                  with the definition, whether it is a method, which wrapper
#                  rules its body hits, and which names it calls UNQUALIFIED
#                  (a method call `x.push(` never links it to a wrapper `push`);
#   - `calls`      unqualified call sites per callee name, counted inside the
#                  file's function bodies after the literal shield;
#   - `macros`     function-like `#define` aliases (C-preprocessor languages
#                  only), with the rules their body hits and the names it calls
#                  (never its own parameters: `EMIT_ARG(fun, ...)` calling
#                  `fun(` is the argument, not a function named fun).
#
# EVERY DEFINITION HERE WAS MEASURED FIRST (tests/tools/wrapper_probe.py,
# #3315 / #3324, hand-labelled in tests/tools/wrapper_labels.json). This module
# does not decide what a wrapper is -- the resolver does, with per-rule
# thresholds -- it only records what the resolver needs to decide.
#
# NOTHING HERE CHANGES A SIGNAL. The facts ride on the file payload; no rule
# count, score or graph edge reads them.
# ==============================================================================
import collections
import re
from typing import Any, Callable, Optional

# The callee names the engine never treats as calls (control-flow keywords and
# builtins), shared with detector.py's own `calls_out_to` filter so a macro
# body's `while (0)` is not recorded as a callee.
from gitgalaxy.core.detector import _CALLS_OUT_GLOBAL_IGNORE

# The literal-vocabulary rules the wrapper channel covers (#3313): the two
# step 1 measured, plus the allocator case step 2 measured on full clones.
WRAPPER_RULES = ("debug_prints", "panics_and_aborts", "memory_alloc")

# The widest cutoff any rule's filter uses (memory_alloc's; the others use 8).
CANDIDATE_MAX_LOC = 12

# Languages whose source runs through the C preprocessor, so a function-like
# `#define` is a callable alias (curl 8.18's `curlx_malloc`).
PREPROCESSOR_LANGS = frozenset({"c", "cpp", "objective-c"})

# A function-like macro definition, continuation lines included. Every repeat is
# bounded (a name, <= 200 chars of params, <= 400 chars of body), so one
# pathological line cannot scan the file.
_DEFINE = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)\(([^)\n]{0,200})\)[ \t]*((?:[^\n\\]|\\\n){0,400})", re.M
)
# A call-shaped name inside a macro body.
_CALLED = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
# An UNQUALIFIED call-shaped name: `x.f(`, `x::f(` and `x->f(` are calls on
# something else and are never counted.
_UNQUALIFIED_CALL = re.compile(r"(?<![\w$.:>])([A-Za-z_$][\w$]*)\s*\(")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
# Callees kept per candidate / macro. The closure only needs to know whether ONE
# callee is a wrapper; a cap keeps a generated file's payload bounded.
_MAX_CALLEES = 24


def is_method_definition(lang_id: str, header: str, name: str) -> bool:
    """Whether the definition makes `name` reachable only through a qualifier.

    A method can only be called as `obj.name(...)`, so it never receives an
    unqualified call. Without this, the step-0 census credited go/core's
    `func (cr *connReader) lock()` with 209 bare `lock(` calls that reach a
    different, out-of-sample `lock`. Conservative: an unrecognised shape is NOT
    a method, so the rule only removes credit a real qualifier would remove.
    """
    before = header.split(name, 1)[0]
    if re.search(r"(?:\.|::|->|:)\s*$", before):  # Lua `M.f`/`M:f`, C++ `X::f`, Ruby `self.f`
        return True
    if lang_id == "go" and re.match(r"\s*func\s*\(", header):  # receiver
        return True
    if lang_id == "python":
        m = re.search(re.escape(name) + r"\s*\(\s*(\w+)", header)
        return bool(m and m.group(1) in ("self", "cls"))
    return False


def _rule_patterns(lang_def: dict[str, Any]) -> dict[str, "re.Pattern[str]"]:
    rules = lang_def.get("rules", {})
    return {r: rules[r] for r in WRAPPER_RULES if hasattr(rules.get(r), "finditer")}


def extract_wrapper_facts(
    lang_id: str,
    lang_def: dict[str, Any],
    code_stream: str,
    raw_text: str,
    functions: list[dict[str, Any]],
    shield: Callable[[str], str],
) -> Optional[dict[str, Any]]:
    """The wrapper channel's raw per-file facts, or None when the file has none.

    `functions` are the detector's extracted units for this file (spans index
    into `code_stream`); `shield` is the detector's literal shield, applied to a
    function body before its call sites are counted so a name inside a string
    is never a call. `raw_text` is only read for `#define` aliases, whose body
    is exactly what the preprocessor pastes in.
    """
    if lang_def.get("invocation_model") == "positional":
        return None  # no invoke-by-name form, so no wrapper can be called by name
    patterns = _rule_patterns(lang_def)
    preprocessor = lang_id in PREPROCESSOR_LANGS
    if not patterns and not preprocessor:
        return None

    defined: collections.Counter[str] = collections.Counter()
    candidates: list[dict[str, Any]] = []
    calls: collections.Counter[str] = collections.Counter()
    for func in functions:
        name = func.get("name") or ""
        if func.get("is_synthetic_slice") or not _IDENT.fullmatch(name):
            continue
        defined[name] += 1
        start, end = func.get("start_idx"), func.get("end_idx")
        if start is None or end is None:
            continue
        body = code_stream[start:end]
        # Unqualified call sites of names the engine's own `calls_out_to` saw as
        # calls. `calls_out_to` also lists qualified method calls (`x.push(`),
        # which are calls on something else, so it is only the gate.
        unqualified: collections.Counter[str] = collections.Counter()
        wanted = set(func.get("calls_out_to") or [])
        if wanted:
            for m in _UNQUALIFIED_CALL.finditer(shield(body)):
                if m.group(1) in wanted:
                    unqualified[m.group(1)] += 1
        calls.update(unqualified)
        callees = sorted(unqualified)
        loc = func.get("loc") or 0
        if loc > CANDIDATE_MAX_LOC:
            continue
        own = [m.span() for m in re.finditer(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", body)]
        hits = sorted(
            rule
            for rule, pattern in patterns.items()
            if any(not any(a <= m.start() < b for a, b in own) for m in pattern.finditer(body))
        )
        if not hits and not callees:
            continue
        lines = body.split("\n", 3)
        candidates.append(
            {
                "name": name,
                "loc": loc,
                "branches": func.get("branch_count", 0) or 0,
                # The engine's span names the function within its first 3 lines
                # (C puts the return type on its own line). When it does not,
                # the span is not the function's and its hits are other code's.
                "aligned": bool(re.search(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", "\n".join(lines[:3]))),
                "method": is_method_definition(lang_id, lines[0], name),
                "hits": hits,
                "callees": callees[:_MAX_CALLEES],
            }
        )

    macros: list[dict[str, Any]] = []
    if preprocessor:
        for m in _DEFINE.finditer(raw_text):
            body = m.group(3).replace("\\\n", " ")
            hits = sorted(rule for rule, pattern in patterns.items() if pattern.search(body))
            params = {p.strip() for p in m.group(2).split(",")}
            called = [
                c for c in dict.fromkeys(_CALLED.findall(body)) if c not in _CALLS_OUT_GLOBAL_IGNORE and c not in params
            ]
            called = called[:_MAX_CALLEES]
            if hits or called:
                macros.append({"name": m.group(1), "hits": hits, "called": called})

    if not (candidates or calls or macros):
        return None
    return {
        "defined": dict(sorted(defined.items())),
        "candidates": candidates,
        "calls": dict(sorted(calls.items())),
        "macros": macros,
    }
