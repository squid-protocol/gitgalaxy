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
    """
    funcs: list[Occurrence] = []
    classes: list[Occurrence] = []

    def walk(node):
        if node.type in func_node_types:
            name = tsaa._get_node_name(node)
            if name:
                funcs.append(
                    Occurrence(
                        name=name,
                        line=node.start_point[0] + 1,
                        args=tsaa._get_param_count(node, lang),
                    )
                )
        if node.type in class_node_types:
            name = tsaa._get_node_name(node)
            if name:
                classes.append(Occurrence(name=name, line=node.start_point[0] + 1, args=None))
        for child in node.children:
            walk(child)

    walk(root)
    return funcs, classes


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
            files = conn.execute(
                "SELECT id, file_path FROM file_data WHERE language = ?", (lang,)
            ).fetchall()

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
                    for r in conn.execute(
                        "SELECT class_name FROM class_data WHERE file_id = ?", (row["id"],)
                    )
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
                        if s.kind in ctags_func_kinds
                    ]
                    ctags_classes = [
                        Occurrence(name=s.name, line=s.line if s.line >= 0 else None, args=None)
                        for s in ct_syms
                        if s.kind in ctags_class_kinds
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
    1", after two real bugs found by spot-checking flagged "disagreements" against the actual
    ctags output before trusting them (both confirmed via
    language-crucible/data/python/airflow/dag.py):
      1. A trailing comma before the closing paren (`def f(a, b, )` -- real, common Python/black
         formatting) left a phantom empty final segment that "comma count + 1" counted as a
         param.
      2. Python's bare `*` / `/` keyword-only / positional-only markers (`def f(self, *, x)`) are
         their own comma-separated segment but represent zero real parameters, not one.
    A reconciliation-side counting bug and a genuine cross-tool disagreement produce the
    identical symptom (numbers don't match) -- every flagged args-mismatch is worth a raw-
    signature spot check like this one before it's trusted as real, not just this function.
    """
    if signature is None:
        return None
    text = signature.strip()
    if not text.startswith("("):
        return None
    depth = 0
    close_idx = None
    for i, ch in enumerate(text):
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
    for ch in inner:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            segments.append("")
        else:
            segments[-1] += ch

    return sum(1 for seg in segments if seg.strip() and seg.strip() not in ("*", "/", "**"))
