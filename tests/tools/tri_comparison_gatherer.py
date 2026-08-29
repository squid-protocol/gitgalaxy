#!/usr/bin/env python3
"""
tri_comparison_gatherer.py

Runs GitGalaxy's own scanner, tree-sitter (via tree-sitter-language-pack), and universal-ctags
independently over the same language-crucible corpus files, per language, and returns three raw,
UNSCORED occurrence lists: what each tool thinks exists, at what line, with how many parameters.

Deliberately does no reconciliation or scoring here -- see tri_comparison_reconcile.py for how
three independent readings get compared into agreement/discrepancy. Splitting these two concerns
(gather vs. reconcile) is different from tree_sitter_accuracy_audit.py's own measure(), which
does both in one pass -- that shape made sense for two readers scored against one fixed ground
truth; it stops making sense once no reader is privileged as ground truth and a discrepancy
needs to be logged rather than immediately resolved.

OPTIONAL, VERIFICATION-ONLY -- NOT PART OF THE ZERO-DEPENDENCY ENGINE
    This is the one module in the tri_comparison_* family that actually NEEDS the optional
    downloads: tree-sitter-language-pack (a hard requirement here -- there's no meaningful "gather
    without tree-sitter" mode, so importing this module without it installed exits immediately
    with an actionable message rather than a raw traceback) and universal-ctags (a soft
    requirement -- ctags_reader.ctags_available(lang) gates every call site, so a missing ctags
    binary degrades every language to a GitGalaxy + tree-sitter comparison instead of erroring).
    Nothing under gitgalaxy/ imports this module; it has no bearing on the shipped package's "0
    dependencies" claim. tri_comparison_reconcile.py, tri_comparison_ledger.py, and
    tri_comparison_report.py only need this module's classes as TYPE HINTS (not at runtime), so
    none of them require either optional download just to reconcile already-gathered data, read
    the ledger, or render the report -- only re-gathering fresh readings does.

REUSE, NOT DUPLICATION
    tests/tools/tree_sitter_accuracy_audit.py is NOT modified by this module (explicit direction:
    don't add ctags into it yet) but several of its pieces are imported read-only rather than
    copied, since they're already correct and tested:
      - NODE_MAPS: which tree-sitter node types are "a function" / "a class" per language.
      - ensure_corpus / run_engine_scan: clones-are-not-this-module's-job corpus path resolution,
        and running the CURRENT checkout's own `galaxyscope` against it via subprocess.
      - _get_node_name / _get_param_count: tree-sitter node -> (name, param count), including all
        the per-language special-casing (C-style declarator unwrapping, Zig container names,
        Haskell arrow-counting, ...) that took multiple real issues to get right the first time.
      - _SYNTHETIC_GG_FUNC_NAMES / _SYNTHETIC_GG_CLASS_NAMES: GitGalaxy's own placeholder names
        (Anonymous_Block, __global_context__, ...) that were never meant to correspond to a real
        named function and must be excluded from every reader's comparison, not just tree-sitter's.
    This module owns its OWN, simpler tree-sitter walk (just "list every func/class node", no
    ground-truth reconciliation, no blind-spot promotion) rather than trying to reuse
    measure()'s walk() closure, which is inseparable from that file's two-reader scoring logic.

GITGALAXY'S OWN READING
    Comes from the same sqlite DB run_engine_scan() already produces (`function_data` /
    `class_data`, the identical schema tests/tools/self_scan.py's DB uses). One real schema
    asymmetry worth knowing before reconciling: `function_data` has a `start_line` column,
    `class_data` does not -- GitGalaxy's own class records carry no line number at all. Class-name
    matching against GitGalaxy's reading is therefore name-only, never position-disambiguated,
    across all three tools (not a gap introduced here -- a pre-existing GitGalaxy schema fact).

CTAGS' OWN READING
    Via ctags_reader.py (this same tests/tools/ directory) -- language coverage there is a subset
    of NODE_MAPS's 31 (24 overlap) plus 9 more from GitGalaxy's tree-sitter-blind set (ada,
    agc_assembly, assembly, cobol, embedded_python, m4, scheme, sqlite, yacc). Call
    ctags_reader.ctags_available(lang) before assuming a reading exists for a given language.
"""

from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import importlib.util
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import ctags_reader  # noqa: E402

# tree-sitter-language-pack is an optional, verification-only download -- see this module's own
# docstring's GITGALAXY'S OWN READING section and ctags_reader.py's near-identical note. Neither
# this module nor tree_sitter_accuracy_audit.py is ever imported by anything under gitgalaxy/,
# so this has no bearing on the shipped package's "0 dependencies" claim. Checked BEFORE
# importing tree_sitter_accuracy_audit (which has its own hard, unguarded top-level `import
# tree_sitter_language_pack`) specifically so a missing install produces this repo's normal
# actionable sys.exit (matching tests/tools/self_scan.py's FULL_PRECISION_PACKAGES check) instead
# of a raw ImportError traceback surfacing from several frames deep inside someone else's import.
if importlib.util.find_spec("tree_sitter_language_pack") is None:
    sys.exit(
        "tri_comparison_gatherer: missing optional dependency 'tree-sitter-language-pack'.\n"
        "This is a verification-only download for the tri-comparison tooling, never a dependency "
        "of the shipped gitgalaxy package -- install it with:\n"
        "    pip install tree-sitter-language-pack"
    )

import tree_sitter_accuracy_audit as tsaa  # noqa: E402 -- read-only reuse, see module docstring

import tree_sitter_language_pack  # noqa: E402


@dataclass(frozen=True)
class Occurrence:
    name: str
    line: Optional[int]  # None where the tool structurally can't report one (GitGalaxy classes)
    args: Optional[int]  # None where the tool didn't/can't report a parameter count here


@dataclass
class FileReadings:
    file_path: str  # relative to the language's corpus dir
    gg_funcs: list[Occurrence]
    gg_classes: list[Occurrence]
    ts_funcs: list[Occurrence]
    ts_classes: list[Occurrence]
    ctags_funcs: list[Occurrence]  # empty if ctags_reader.ctags_available(lang) is False
    ctags_classes: list[Occurrence]


def _is_cpp_unscoped_enum(node) -> bool:
    """tree-sitter-cpp's `enum_specifier` node covers BOTH a C++11 scoped enum (`enum class Foo
    {...}`/`enum struct Foo {...}`) and a plain, unscoped C-style enum (`enum Foo {...}`) --
    distinguished only by whether a `class`/`struct` keyword TOKEN is one of its direct children
    (confirmed via direct parse: `enum class Foo {...}` has a `class` child between `enum` and the
    name, `enum Bar {...}` doesn't). GitGalaxy's own cpp `class_start` regex only counts the
    SCOPED form (`enum[ \\t\\n]+class|enum[ \\t\\n]+struct` --
    gitgalaxy/standards/language_standards.py) as a class-analog; a plain enum is just a set of
    named integer constants, not a type with its own scope. Confirmed via
    `cpp/class/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]` (22 occurrences, 2026-08-21):
    every sampled case (`godot/editor_node.h`'s `SceneNameCasing`/`ActionOnPlay`/`ActionOnStop`/
    `MenuOptions`/`MenuType`, `godot/main.h`'s `CLIOptionAvailability`) is a plain `enum Foo {...}`
    that GitGalaxy and ctags both correctly agree isn't a class -- only this walker's
    unconditional `enum_specifier` counting disagreed. C is deliberately NOT included here: C has
    no scoped-enum syntax at all, so GitGalaxy's own C `class_start` counts every enum
    unconditionally already (see ctags_reader.py's matching `CTAGS_CLASS_KINDS["c"]` comment) --
    gating C the same way would newly create false negatives, not fix anything."""
    if node.type != "enum_specifier":
        return False
    return not any(c.type in ("class", "struct") for c in node.children)


def _walk_tree_sitter(root, func_node_types: set[str], class_node_types: set[str], lang: str):
    """This module's OWN tree-sitter walk -- deliberately simpler than
    tree_sitter_accuracy_audit.py's measure()/walk(): list every func/class node's (name, line,
    param count) with no ground-truth reconciliation, no blind-spot promotion, no per-language
    drop rules for bodyless forward declarations. Those drop rules encode "is this a REAL
    function GitGalaxy should have found" (a ground-truth question); this function's job is only
    "what does tree-sitter's own tree contain", which is a different, prior question -- the
    reconciliation step (not this module) is where drop-rule-shaped judgment calls belong, so
    they can be applied uniformly across what GitGalaxy/ctags read too instead of being baked
    into one reader's walk alone.

    One piece of measure()'s walk() IS ported here, verbatim in spirit (#1614): tree-sitter-haskell
    emits one node PER PATTERN-MATCH CLAUSE, not one per logical function -- `toJSON` written as
    five equations is five sibling nodes sharing one name. Left unhandled, that's not "a different,
    prior question" like the drop rules above; it's tree-sitter's tree containing five entries for
    one thing that exists once, which every consumer of this reader's Occurrence list (reconcile,
    ledger, chart) would then have to know to special-case itself. Consecutive func-type SIBLINGS
    (interleaved `comment` nodes don't break the run -- real corpus code routinely comments between
    clauses) sharing a name collapse into the first occurrence only, the same rule
    tree_sitter_accuracy_audit.py already proved correct for this exact grammar.

    A second piece is ported for the identical reason (found via
    `c/class/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`, 525 occurrences -- the single
    largest shape in the whole ledger): tree-sitter-c's `struct_specifier`/`union_specifier`/
    `enum_specifier` node type covers BOTH a real `struct Foo { ... }` DEFINITION and a bare
    reference to an already-defined type (`struct Foo *ptr`, a cast, a parameter) -- the same node
    type either way, distinguished only by whether it has a `body` field. Confirmed via source:
    every one of compile.c's repeated `compiler_unit` hits and ceval.c's `_py_code_state` hit is a
    pointer declaration/parameter/cast, never a definition. Counting every REFERENCE as if it were
    a new DEFINITION isn't "a different, prior question" either -- it's tree-sitter's tree
    containing a node whose own field data already says "not a definition," which every consumer
    of this reader's Occurrence list would otherwise have to special-case itself. Same fix
    `tree_sitter_accuracy_audit.py`'s walk() already applies for C specifically (not a
    general-purpose rule -- most languages' class-shaped node types don't have this reference/
    definition ambiguity).

    Extended to cpp for the identical reason (found via
    `cpp/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`, 95 occurrences): tree-sitter-cpp
    inherits the same `class_specifier`/`struct_specifier`/`union_specifier`/`enum_specifier`
    grammar from tree-sitter-c, so a bare forward declaration (`class AudioStreamPreviewGenerator;`,
    godot/editor_node.h:68) produces the identical bodyless node tree-sitter-c's own reference/cast
    case does -- confirmed directly (`node.child_by_field_name("body") is None` for the forward
    declaration, not-None for a real `class Foo { ... }` definition). ctags correctly excludes
    these; GitGalaxy's own `class_start` regex does NOT (a separate, real GitGalaxy production
    defect -- see the GitHub issue filed alongside this fix -- deliberately NOT patched here since
    C++ multiple inheritance (`class Foo : public A, public B {`) makes the production engine's
    generic comma/paren/equals lookahead unsafe to reuse as-is for cpp without further design work;
    this walker instead uses the grammar's own `body` field, which has no such ambiguity).

    A third piece is ported for the identical reason (found via the tri-comparison-ledger-sweep on
    javascript, 2026-08-21 -- the `javascript/function/existence/*` shapes involving `tree_sitter`
    on the react corpus, e.g. `agree[gitgalaxy]_vs[ctags,tree_sitter]`/
    `agree[tree_sitter]_vs[ctags,gitgalaxy]`): this is the exact same `#1633`/Claim 3 mechanism
    already fixed in `tree_sitter_accuracy_audit.py`'s own walk() -- Flow-typed react source
    (`@flow` pragma, `(expr: Type)` casts, `import {x, type Y}` specifiers) produces grammar
    `ERROR` nodes tree-sitter-javascript can't parse around, and recovery hallucinates plain
    control-flow keywords (`if`/`for`/`while`/...) and specific known names as `method_definition`
    nodes. Confirmed directly against this module's own parse of `react/ReactFiberBeginWork.js`,
    `ReactFiberWorkLoop.js`, and `ReactFlightServer.js`: each has `tree.root_node.has_error is
    True`, with `ReactFiberWorkLoop.js`/`ReactFlightServer.js` each producing ONE `ERROR` node
    spanning the entire file (line 1 to EOF) -- confirming this module's simpler walker was never
    given the reserved-keyword/hallucination filter `tree_sitter_accuracy_audit.py` already proved
    necessary, not a new bug in the underlying grammar. Reuses `tsaa`'s own frozensets directly
    (not a re-derived copy) so there's exactly one place either list is maintained.
    """
    funcs: list[Occurrence] = []
    classes: list[Occurrence] = []

    def walk(node, is_continuation_clause=False):
        # #2452: an HTML `<script>` / `<style>` element is a container -- the real
        # code lives in an embedded language (JavaScript / CSS), which is exactly
        # what GitGalaxy's own polyglot detector descends into (e.g. a `<style>`'s
        # `@media` rule is reported by GitGalaxy as a function `media`). Without
        # this branch tree-sitter-html yields NOTHING for these (its `raw_text` is
        # opaque and `_get_node_name` has no branch for the element types), so a
        # correct GitGalaxy polyglot find looks like an over-detection. Reuses the
        # audit's own `_html_embedded_ts_funcs` (grammar injection + line offset +
        # `<script src=...>` skip), same as `measure()`'s walk().
        if lang == "html" and node.type in tsaa._HTML_EMBEDDED_LANG:
            for name, abs_line, pc, _sub in tsaa._html_embedded_ts_funcs(node):
                funcs.append(Occurrence(name=name, line=abs_line, args=pc))
            return
        if node.type in func_node_types:
            name = tsaa._get_node_name(node)
            if (
                name
                and not (lang == "haskell" and is_continuation_clause)
                and not (
                    lang == "javascript"
                    and node.type == "method_definition"
                    and (
                        name in tsaa._JS_RESERVED_STATEMENT_KEYWORDS
                        or name in tsaa._JS_KNOWN_FLOW_HALLUCINATIONS
                    )
                )
            ):
                funcs.append(
                    Occurrence(
                        name=name,
                        line=node.start_point[0] + 1,
                        args=tsaa._get_param_count(node, lang),
                    )
                )
        if node.type in class_node_types and not (
            lang in ("c", "cpp") and node.child_by_field_name("body") is None
        ) and not (lang == "cpp" and _is_cpp_unscoped_enum(node)):
            name = tsaa._get_node_name(node)
            if name:
                classes.append(Occurrence(name=name, line=node.start_point[0] + 1, args=None))

        last_clause_name: Optional[str] = None
        for child in node.children:
            if lang == "haskell" and child.type == "comment":
                walk(child)
                continue
            child_is_continuation = False
            if lang == "haskell" and child.type in func_node_types:
                child_name = tsaa._get_node_name(child)
                if child_name is not None and child_name == last_clause_name:
                    child_is_continuation = True
                last_clause_name = child_name
            else:
                last_clause_name = None
            walk(child, is_continuation_clause=child_is_continuation)

    walk(root)
    return funcs, classes


_CTAGS_ANON_NAME_RE = re.compile(r"^__anon[0-9a-f]+$")

# universal-ctags' JavaScript parser uses a DIFFERENT synthetic-placeholder scheme than the C
# parser's "__anon<hex>" above -- "AnonymousFunction<hex><seq>"/"AnonymousClass<hex><seq>" (e.g.
# "AnonymousFunctionff8c17c30100"), emitted for every anonymous function EXPRESSION (a bare inline
# callback with no attributable name, `jQuery.ajaxPrefilter(function(s) {...})`) and, separately,
# for anonymous object-literal/constructor-style assignments its "class" heuristic can't otherwise
# key on. Found via tri-comparison-ledger-sweep on javascript (2026-08-21,
# javascript/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter], 150 occurrences): neither
# GitGalaxy nor tree-sitter report a name for a genuinely-anonymous callback either (there isn't
# one), so this is the exact same false-discrepancy shape as the C `__anon` case above, just a
# differently-shaped placeholder from a different per-language ctags parser.
#
# Deliberately checked ONLY for lang == "javascript", NOT applied blindly to every language the
# way the "__anon" regex above is -- confirmed directly (2026-08-21) that PHP's ctags parser
# reuses this exact same "AnonymousClass<hex>" text for a GENUINE PHP language construct (`$obj =
# new class { ... };`, PHP 7+ anonymous classes), which is real, valid PHP source ctags is
# correctly tagging, not a placeholder to discard. An earlier version of this filter checked the
# name pattern alone with no per-language gate and silently dropped a real php ctags class tag
# (corpus-wide class found-count regression 30->29), caught before commit by re-running the full
# `--all --write` chart and diffing every changed panel, not assumed safe from the javascript
# corpus check alone.
_CTAGS_JS_ANON_NAME_RE = re.compile(r"^Anonymous(?:Function|Class)[0-9a-f]+$")


def _is_ctags_synthetic_anon_name(name: str, lang: str) -> bool:
    """universal-ctags synthesizes a placeholder name (`__anon<hex hash>`, e.g.
    `__anon2570bd640108`) for an anonymous struct/union/enum (`typedef struct { ... } Foo;` --
    real, common C, e.g. cpython/ceval.c's platform-specific pthread attr shim) so it has
    something to key the tag on internally. Neither GitGalaxy nor tree-sitter report a name for
    an anonymous type at all (there genuinely isn't one), so ctags' internal bookkeeping name
    always shows up as a lone `agree[ctags]_vs[gitgalaxy,tree_sitter]` false discrepancy --
    confirmed via c/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter] (23 occurrences,
    every single sample this exact shape, spanning cpython/doom). The same exclusion GitGalaxy's
    own synthetic placeholder names already get (_SYNTHETIC_GG_FUNC_NAMES/
    _SYNTHETIC_GG_CLASS_NAMES) applied to ctags' equivalent. Also covers javascript's own
    "AnonymousFunction"/"AnonymousClass" placeholder scheme (_CTAGS_JS_ANON_NAME_RE above), gated
    to `lang == "javascript"` only -- see that regex's own comment for why this one CAN'T be
    applied language-agnostically like the "__anon" check above."""
    if _CTAGS_ANON_NAME_RE.match(name):
        return True
    return lang == "javascript" and bool(_CTAGS_JS_ANON_NAME_RE.match(name))


def gather_language(lang: str, corpus_dir: Optional[Path] = None) -> list[FileReadings]:
    """Runs GitGalaxy always, tree-sitter if this language has a NODE_MAPS entry, and ctags if
    ctags_reader.ctags_available(lang) -- over every corpus file for `lang`, returns one
    FileReadings per file. Both tree-sitter and ctags are independently optional per language
    (not "tree-sitter always" -- an earlier version of this function required it, before the
    chart needed to cover GitGalaxy's 9 tree-sitter-blind-but-ctags-covered languages too: ada,
    agc_assembly, assembly, cobol, embedded_python, m4, scheme, sqlite, yacc. A language with
    neither reads as GitGalaxy-only, a 1-bar chart group -- the same shape a language with no
    committed tree-sitter baseline at all already had before ctags existed.
    Raises the same sys.exit-on-missing-corpus behavior as tree_sitter_accuracy_audit.py's
    ensure_corpus if corpus_dir isn't passed explicitly.
    """
    has_tree_sitter = lang in tsaa.NODE_MAPS
    if has_tree_sitter:
        lang_config = tsaa.NODE_MAPS[lang]
        ts_lang = lang_config.get("ts_lang", lang)
        func_node_types = lang_config["func_node_types"]
        class_node_types = lang_config["class_node_types"]
        parser = tree_sitter_language_pack.get_parser(ts_lang)

    corpus_dir = corpus_dir or tsaa.ensure_corpus(lang)
    has_ctags = ctags_reader.ctags_available(lang)
    ctags_func_kinds = ctags_reader.CTAGS_FUNC_KINDS.get(lang, set())
    ctags_class_kinds = ctags_reader.CTAGS_CLASS_KINDS.get(lang, set())

    with tempfile.TemporaryDirectory() as tmp:
        db_path = tsaa.run_engine_scan(corpus_dir, Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            files = conn.execute("SELECT id, file_path FROM file_data WHERE language = ?", (lang,)).fetchall()

            results: list[FileReadings] = []
            for row in files:
                path = corpus_dir / row["file_path"]
                if not path.exists():
                    continue

                gg_funcs = [
                    Occurrence(name=r["func_name"], line=r["start_line"], args=r["args"])
                    for r in conn.execute(
                        "SELECT func_name, args, start_line FROM function_data WHERE file_id = ?",
                        (row["id"],),
                    )
                    if r["func_name"] not in tsaa._SYNTHETIC_GG_FUNC_NAMES
                ]
                gg_classes = [
                    Occurrence(name=r["class_name"], line=None, args=None)
                    for r in conn.execute("SELECT class_name FROM class_data WHERE file_id = ?", (row["id"],))
                    if r["class_name"] not in tsaa._SYNTHETIC_GG_CLASS_NAMES
                ]

                if has_tree_sitter:
                    try:
                        code_bytes = path.read_bytes()
                        tree = parser.parse(code_bytes)
                        ts_funcs, ts_classes = _walk_tree_sitter(
                            tree.root_node, func_node_types, class_node_types, lang
                        )
                    except Exception:
                        ts_funcs, ts_classes = [], []
                else:
                    ts_funcs, ts_classes = [], []

                if has_ctags:
                    ct_syms = ctags_reader.read_ctags_symbols(path, lang)
                    ctags_funcs = [
                        Occurrence(
                            name=s.name,
                            line=s.line if s.line >= 0 else None,
                            args=_count_ctags_signature_params(s.signature),
                        )
                        for s in ct_syms
                        if s.kind in ctags_func_kinds and not _is_ctags_synthetic_anon_name(s.name, lang)
                    ]
                    ctags_classes = [
                        Occurrence(name=s.name, line=s.line if s.line >= 0 else None, args=None)
                        for s in ct_syms
                        if s.kind in ctags_class_kinds and not _is_ctags_synthetic_anon_name(s.name, lang)
                    ]
                else:
                    ctags_funcs, ctags_classes = [], []

                results.append(
                    FileReadings(
                        file_path=row["file_path"],
                        gg_funcs=gg_funcs,
                        gg_classes=gg_classes,
                        ts_funcs=ts_funcs,
                        ts_classes=ts_classes,
                        ctags_funcs=ctags_funcs,
                        ctags_classes=ctags_classes,
                    )
                )
            return results
        finally:
            conn.close()


def _count_ctags_signature_params(signature: Optional[str]) -> Optional[int]:
    """ctags' `signature:` field is free text, e.g. `(cx: &Ctxt, name: &Name) -> Result<X, ()>`
    -- not a count. Returns None (not 0) when the field wasn't populated at all, so callers can
    tell "no params" apart from "this language/parser doesn't report a signature here" (confirmed
    case: shell -- bash functions have no formal parameter list for ctags to read, matching
    tree-sitter's own structural gap there). Only reads up to the first top-level-balanced closing
    paren -- a trailing `-> ReturnType` (seen on rust) is never part of the parameter list, so
    text after it is ignored entirely. Nested generics/parens (`Vec<(i32, i32)>`) are tolerated
    by depth-tracking the split so an internal comma doesn't inflate the count.

    Splits into segments first, THEN counts real parameters -- deliberately not "comma count +
    1", after four real bugs found by spot-checking flagged "disagreements" against the actual
    ctags output before trusting them:
      1. A trailing comma before the closing paren (`def f(a, b, )` -- real, common Python/black
         formatting) left a phantom empty final segment that "comma count + 1" counted as a
         param. (language-crucible/data/python/airflow/dag.py)
      2. Python's bare `*` / `/` keyword-only / positional-only markers (`def f(self, *, x)`) are
         their own comma-separated segment but represent zero real parameters, not one.
         (language-crucible/data/python/airflow/dag.py)
      3. C's explicit empty-parameter-list marker (`int f(void)`) is one segment, "void", but zero
         real parameters -- confirmed via `c/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`
         (104 occurrences, tri_comparison_ledger.json): GitGalaxy and tree-sitter both already
         special-case this (see `_count_top_level_args`'s own docstring in detector.py), this
         function didn't. `PyEval_GetLocals(void)` in cpython/ceval.c confirmed both the raw ctags
         signature text (`(void)`) and the miscount (1, not 0) directly before this was fixed.
      4. A quoted string-literal default value containing its own comma (`def markoutercomma(line,
         comma=','):`, numpy/crackfortran.py) was being split like any other top-level comma --
         the depth tracker only understood bracket nesting, not string-literal boundaries, so the
         literal `','` character inside the quotes produced a phantom 3rd segment (real param
         count is 2). Confirmed via `python/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`
         (1 occurrence, tri_comparison_ledger.json) -- GitGalaxy and tree-sitter both already
         correctly report 2; only this counting function's split was wrong. Double-quote tracking
         (unbounded, backslash-escape aware -- a real string can be arbitrarily long) suppresses
         comma-splitting and bracket-depth changes alike while inside one, mirroring how
         `detector.py`'s own real engine shields string literals before running a structural regex
         over source text.

         A single-quote `'` is deliberately NOT treated the same unbounded way: Rust's lifetime
         syntax (`&'a str`, `Context<'_>`, bare `'static`) is also a single apostrophe, but one
         with NO closing quote at all -- scanning "until the next `'`" swallowed everything up to
         some LATER, unrelated lifetime's own apostrophe as one giant fake "string", silently
         eating the real comma between them. This regressed `rust/function/args/
         agree[ctags,gitgalaxy]_vs[tree_sitter]` the first time this fix shipped (`poll_read(self:
         Pin<&mut Self>, cx: &mut Context<'_>, buf: &mut ReadBuf<'_>)`, tokio/tokio_named_pipe.rs
         -- 3 real params undercounted to 2 once the first `'_` was treated as opening a string
         that only "closed" 23 characters later at the second `'_`; a first attempt at widening
         the lookahead to 24 chars (generous enough for an escaped-Unicode char literal like
         `'\\u{1F600}'`) still wasn't tight enough -- both this case (distance 23) and a second
         synthetic lifetime case (distance 12) needed excluding, so the bound is deliberately just
         `_CHAR_LITERAL_LOOKAHEAD = 3`: enough for an unescaped single character (`','`, distance
         2) or a short 2-char escape (`'\\n'`, `'\\''`), but nowhere near enough for even the
         shortest realistic lifetime-to-next-apostrophe gap seen in real corpus code. A longer
         escape (Unicode, e.g. `'\\u{1F600}'`) would fall outside this bound and simply not be
         treated as a string -- an acceptable, narrower trade-off given no ledger shape has ever
         actually flagged one, versus the confirmed, real lifetime regression a looser bound
         reintroduces every time). Otherwise the apostrophe is left alone as ordinary text, same
         as any other non-quote character.
    A reconciliation-side counting bug and a genuine cross-tool disagreement produce the
    identical symptom (numbers don't match) -- every flagged args-mismatch is worth a raw-
    signature spot check like this one before it's trusted as real, not just this function, and a
    fix to shared logic like this one is worth re-checking against every OTHER language that
    shares it, not just the one language that originally flagged it.
    """
    if signature is None:
        return None
    text = signature.strip()
    if not text.startswith("("):
        return None

    _CHAR_LITERAL_LOOKAHEAD = 3

    def _scan(s: str) -> list[tuple[str, bool]]:
        """Returns (char, in_string) for every char in `s`, tracking double-quoted string literals
        (unbounded, backslash-escape aware) and single-quoted char literals (bounded lookahead --
        see the docstring's bug #4 note on why an unbounded scan is wrong for `'`, e.g. Rust
        lifetimes) so callers can skip bracket/comma handling while inside one."""
        out = []
        quote_char: Optional[str] = None
        escape = False
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            in_string = quote_char is not None
            if in_string:
                out.append((ch, True))
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == quote_char:
                    quote_char = None
                i += 1
                continue
            if ch == '"':
                quote_char = ch
                out.append((ch, False))
                i += 1
                continue
            if ch == "'":
                closer = s.find("'", i + 1, i + 1 + _CHAR_LITERAL_LOOKAHEAD)
                if closer != -1:
                    quote_char = ch
                out.append((ch, False))
                i += 1
                continue
            out.append((ch, False))
            i += 1
        return out

    scanned = _scan(text)
    depth = 0
    close_idx = None
    for i, (ch, in_string) in enumerate(scanned):
        if in_string:
            continue
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
            if depth == 0 and ch == ")":
                close_idx = i
                break
    if close_idx is None:
        return None
    inner = text[1:close_idx].strip()
    if not inner:
        return 0

    depth = 0
    segments = [""]
    for ch, in_string in _scan(inner):
        if in_string:
            segments[-1] += ch
            continue
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            segments.append("")
        else:
            segments[-1] += ch

    return sum(1 for seg in segments if seg.strip() and seg.strip() not in ("*", "/", "**", "void"))
