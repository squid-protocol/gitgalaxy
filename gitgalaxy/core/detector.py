# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution

# galaxyscope:ignore sec_high_risk_execution

import bisect
import logging
import math
import re
import time
from typing import Any, ClassVar, Optional, TypedDict, cast

from gitgalaxy.core.spatial_correlation import (
    apply_amplifier_correlations,
    apply_dampener_correlations,
)
from gitgalaxy.core.spatial_correlation import (
    correlate_signals as _correlate_signals_impl,
)
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS
from gitgalaxy.standards.language_standards import LENS_CONFIG

HAS_TIKTOKEN = False
try:
    import tiktoken

    HAS_TIKTOKEN = True
    # cl100k_base is the standard for GPT-4, o1, and a highly accurate proxy for Claude
    ENCODER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    pass


def get_token_mass(text: str) -> Optional[int]:
    """Calculates context window footprint. Returns None if tiktoken is missing to prevent dataset poisoning."""
    if not text:
        return 0
    if HAS_TIKTOKEN:
        return len(ENCODER.encode(text, disallowed_special=()))
    return None


# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# GitGalaxy Phase 2.5 & 7.5: Logic Splicer & Topological Mapper
# Strategy Protocol: Fluid-State Counters, Language Sliding & Semantic Modes
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution


class ClassInfo(TypedDict):
    """A regex-extracted class/struct/interface/trait/enum, with its linked methods' physics."""

    name: str
    inheritance: list[str]
    method_count: int
    state_entanglement: float


class _ClassInfoWithBounds(ClassInfo, total=False):
    # _start_line/_end_line are spatial scratch state, deleted once function
    # linkage is done (see "Erase the temporary spatial boundaries" below) --
    # split into a total=False subclass so those two `del`s stay valid: mypy
    # rejects deleting a key from a `total=True` TypedDict.
    _start_line: int
    _end_line: int


class FunctionNode(TypedDict, total=False):
    """Metadata for a surgically extracted functional logic block."""

    name: str
    parent_class_name: str
    usage_status: int

    # Dual-Key mapping to ensure compatibility with all pipeline versions
    semantic_type: str
    texture: str
    type_id: str

    loc: int
    coding_loc: int
    keyword_density: float

    branch_count: int
    branch: int

    args: int
    args_count: int

    control_flow_angle: float
    logic_angle: float
    angle: float

    control_flow_ratio: float
    cf_ratio: float

    structural_weight: float
    magnitude: float
    mag: float
    impact: float

    start_line: int
    end_line: int
    start_idx: int
    end_idx: int

    docstring: str
    calls_out_to: list[str]
    hit_vector: dict[str, int]
    token_mass: Optional[int]


class LogicData(TypedDict, total=False):
    """The standardized output schema for Strategy compliance."""

    equations: dict[str, int]
    functions: list[FunctionNode]
    logic_density: float
    total_functional_impact: float
    total_control_flow_ratio: float
    raw_imports: list
    metadata: dict[str, str]
    token_mass: int
    financial_read_cost: float


# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# THE STRUCTURAL SIGNATURE CONFIGURATION MATRIX
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution


class ScopeParsingRegistry:
    """
    The Structural Signature Calibration Matrix for GalaxyScope's Primary Detector.
    Defines the structural heuristics required to slice non-brace languages.

    DEFENSIVE ARCHITECTURE:
    By categorizing languages into integration modes, the engine avoids building
    heavy Abstract Syntax Trees (ASTs). It visualizes functional intent across
    50+ languages natively without requiring the codebase to compile.

    - MODE D: Keyword Scope Tracking (Depth tracking via language-specific keywords)
    - MODE E: Terminator Delimiting (Hard slicing via line-ending tokens)
    """

    # Internal aliases to route variations to their base optical physics
    _ALIASES: ClassVar[dict[str, str]] = {
        "bash": "shell",
        "sh": "shell",
        "zsh": "shell",
        "t-sql": "sql",
        "plpgsql": "sql",
        "mysql": "sql",
        "psql": "sql",
        "sqlite": "sql",
        "visualbasic": "vb",
        "vba": "vb",
    }

    DEFINITIONS: ClassVar[dict[str, dict[str, Any]]] = {
        # ==========================================
        # 🔴 INTEGRATION MODE D: The Handshake Stack
        # ==========================================
        "shell": {
            "mode": "mode_d",
            "openers": [
                r"\bif\b",
                r"\bwhile\b",
                r"\buntil\b",
                r"\bfor\b",
                r"\bcase\b",
                r"\{",  # Shell functions use braces for scope
            ],
            "closers": [r"\bfi\b", r"\bdone\b", r"\besac\b", r"\}"],
        },
        "ruby": {
            "mode": "mode_d",
            "openers": [
                r"(?<![:.])\bdef\b(?!:)",
                r"(?<![:.])\bclass\b(?!:)",
                r"(?<![:.])\bmodule\b(?!:)",
                r"(?<![:.])\bif\b(?!:)",
                r"(?<![:.])\bunless\b(?!:)",
                r"(?<![:.])\bwhile\b(?!:)",
                r"(?<![:.])\buntil\b(?!:)",
                r"(?<![:.])\bfor\b(?!:)",
                r"(?<![:.])\bcase\b(?!:)",
                r"(?<![:.])\bdo\b(?!:)",
                r"(?<![:.])\bbegin\b(?!:)",
            ],
            "closers": [r"(?<![:.])\bend\b(?!:)"],
            # #1262: which of the openers above actually declares a
            # method (as opposed to generic control-flow/module scope) --
            # drives _slice_by_keywords' nested-satellite scan so a `def`
            # inside a `class`/`module` body (virtually all real Ruby
            # methods) gets its own FunctionNode instead of being folded
            # into the enclosing class's single satellite. Same string as
            # the "openers" entry above, kept as its own key rather than
            # reused by index since the two lists could diverge later.
            "function_opener": r"(?<![:.])\bdef\b(?!:)",
            "class_opener": r"(?<![:.])\b(?:class|module)\b(?!:)",
        },
        "lua": {
            "mode": "mode_d",
            "openers": [
                r"\bfunction\b",
                r"\bif\b",
                r"\bwhile\b",
                r"\bfor\b",
                r"\brepeat\b",
            ],
            "closers": [r"\bend\b", r"\buntil\b"],
        },
        "elixir": {
            "mode": "mode_d",
            "openers": [
                r"\bdef\b",
                r"\bdefmodule\b",
                r"\bdefmacro\b",
                r"\bdefp\b",
                r"\bif\b",
                r"\bunless\b",
                r"\bcase\b",
                r"\bcond\b",
                r"\breceive\b",
                r"\bfn\b",
                r"\bdo\b",
            ],
            "closers": [r"\bend\b"],
        },
        "vb": {
            "mode": "mode_d",
            "openers": [
                r"\bsub\b",
                r"\bfunction\b",
                r"\bif\b",
                r"\bwhile\b",
                r"\bselect\b",
                r"\bfor\b",
                r"\bwith\b",
                r"\bproperty\b",
                r"\bclass\b",
            ],
            "closers": [r"\bend\b", r"\bnext\b", r"\bloop\b", r"\bwend\b"],
            "ignore_case": True,
        },
        # #1266: MATLAB uses `end`-keyword-delimited scopes (`function...end`,
        # `if...end`, `classdef...end`), not braces -- previously unregistered
        # here, so it silently fell through to the default Mode B (brace-based)
        # dispatch, which is structurally wrong for MATLAB (its ONLY brace usage
        # is `{}` cell-array literals, unrelated to scope). Confirmed root cause
        # of MATLAB's reported func_start recall gap: `func_start`'s own regex
        # already matched every real function signature correctly -- the bug was
        # entirely in routing, not the regex. `properties`/`methods`/`events`/
        # `enumeration` are classdef sub-block openers (methods-block-nested
        # functions were explicitly the gap #1266 called out); GNU Octave's
        # explicit `endfunction`/`endif`/etc. dialect closers are included
        # alongside bare `end` since this language config is shared with Octave
        # (see "shebangs" above) and both forms are valid there.
        "matlab": {
            "mode": "mode_d",
            "openers": [
                r"\bfunction\b",
                r"\bif\b",
                r"\bfor\b",
                r"\bparfor\b",
                r"\bwhile\b",
                r"\bswitch\b",
                r"\btry\b",
                r"\bclassdef\b",
                r"\bproperties\b",
                r"\bmethods\b",
                r"\benumeration\b",
                r"\bevents\b",
            ],
            "closers": [
                r"\bend\b",
                r"\bendfunction\b",
                r"\bendif\b",
                r"\bendfor\b",
                r"\bendparfor\b",
                r"\bendwhile\b",
                r"\bendswitch\b",
                r"\bendtry\b",
                r"\bendclassdef\b",
                r"\bendproperties\b",
                r"\bendmethods\b",
                r"\bendenumeration\b",
                r"\bendevents\b",
            ],
            "function_opener": r"\bfunction\b",
            "comment_marker": "%",
        },
        # ==========================================
        # 🪓 INTEGRATION MODE E: Terminator Cleaving
        # ==========================================
        "sql": {
            "mode": "mode_e",
            "terminator": r";",
            "igniter": r"\b(SELECT|CREATE|UPDATE|DELETE|INSERT|ALTER|DROP|GRANT|REVOKE|WITH|DECLARE|TRUNCATE)\b",
        },
        "erlang": {
            "mode": "mode_e",
            "terminator": r"\.",
            "igniter": r"^[a-z_][a-zA-Z0-9_]*\s*(?:\(|->)",
        },
        "prolog": {
            "mode": "mode_e",
            "terminator": r"\.",
            "igniter": r"^[a-z_][a-zA-Z0-9_]*\s*(?:\(|:-)",
        },
    }

    @classmethod
    def get_config(cls, lang_id: str) -> Optional[dict]:
        """Resolves aliases and returns the structural signature config for the language."""
        if not lang_id:
            return None
        normalized_id = lang_id.lower()
        base_id = cls._ALIASES.get(normalized_id, normalized_id)
        return cls.DEFINITIONS.get(base_id)

    @classmethod
    def get_mode(cls, lang_id: str) -> Optional[str]:
        """Returns the specific integration mode required for the language."""
        config = cls.get_config(lang_id)
        return config["mode"] if config else None


# ------------------------------------------------------------------------------
# THE DETECTOR (Structural Detector)
# ------------------------------------------------------------------------------

# #1264: languages whose own `class_start` rule has been verified (via
# `python tests/tools/tree_sitter_accuracy_audit.py --lang <x>` against the
# language-crucible corpus) to produce correct, precise named-entity
# extraction when reused as the class-list source in `splice()`, in place of
# the old generic `class|struct|interface|trait|enum` fallback regex. Every
# other language's `class_start` was written purely for numeric signal-
# counting (a structural risk-boundary count feeding `equations`/`counts`,
# same as `branch` or `io`) and is looser than a real declaration anchor --
# e.g. C's intentionally also matches bare struct-TYPE-usage sites like
# `struct foo_ops ops;` (see its own inline comment, epic #813/#822) for
# risk-signal purposes, which floods the named-entity class list with
# phantom/misattributed entries if reused here unmodified (confirmed: C's
# found_classes 45->0 and extra_classes 7->23 on the crucible corpus when
# tried without this gate). Extending this set to the remaining languages
# needs the same kind of per-language hardening pass
# epic #813 already did for func_start/args/class_start's OWN extraction
# gauntlets -- tracked as a follow-up (#1295), not attempted wholesale here.
_CLASS_START_NAMED_EXTRACTION_LANGS = frozenset(
    {
        # #1904: ABAP can't go through this epic's own documented
        # verification method (tree_sitter_accuracy_audit.py against
        # tree-sitter ground truth) -- it has no tree-sitter grammar at
        # all, one of only 5 gg_only languages with neither tree-sitter
        # nor ctags. Verified instead via direct source cross-check
        # (docs/language_status/abap.md §9): 100% precision on all 12 real
        # DEFINITION/IMPLEMENTATION matches across abapGit's 6 real
        # classes, zero false positives. Without this entry the generic
        # fallback regex (lowercase-only `class|struct|interface|trait|
        # enum`, no re.I) can never match ABAP's always-uppercase `CLASS
        # <name> DEFINITION` syntax, so the named classes list stays
        # permanently empty regardless of #1898's prism.py fix.
        "abap",
        "apex",
        "c",
        # #1974: Dockerfile has no `class` keyword and thus fails the generic
        # fallback regex. Its own class_start safely extracts build stage
        # boundaries (either the explicit `AS <alias>` name or the base image).
        "dockerfile",
        # #1858: cobol's own class_start regex already matches PROGRAM-ID/CLASS-ID/
        # INTERFACE-ID/FACTORY/OBJECT correctly and identically to universal-ctags'
        # independent reading (verified directly, e.g. cics-banking-sample-application-
        # cbsa/BANKDATA.cbl:35's `PROGRAM-ID. BANKDATA.` -> "BANKDATA", matching ctags'
        # own tag) -- cobol was simply never added to this allowlist (not decided out
        # like css/html, just never in scope for epic #1295 since that epic's own
        # verification method requires a tree-sitter grammar cobol doesn't have; this
        # one is verified via docs/self_scan/tri_comparison_ledger.json's
        # cobol/class/existence/agree[ctags]_vs[gitgalaxy] entry against ctags instead).
        # Without this entry the generic fallback regex (class|struct|interface|trait|
        # enum) can never match COBOL's PROGRAM-ID syntax, so the named classes list
        # stayed permanently empty (0/19 real classes) despite cobol's own regex working.
        "cobol",
        "cpp",
        "csharp",
        "css",
        "dart",
        "fortran",
        "go",
        "groovy",
        "haskell",
        "java",
        "javascript",
        "kotlin",
        "lua",
        "makefile",
        "matlab",
        "objective-c",
        "perl",
        "php",
        "powershell",
        "python",
        "ruby",
        "rust",
        "scala",
        "shell",
        "solidity",
        "swift",
        "tcl",
        "typescript",
        "zig",
    }
)

_CLASS_START_REQUIRES_BODY_ANCHOR = frozenset({"c", "cpp"})

# #2011: cpp needs its own body-anchor check, not C's flat "stop at the first {/;/,/)/="
# lookahead -- C++'s inheritance-list syntax (`class Foo : public A, public B { ... }`,
# `class Foo : public Base<X, Y> { ... }`) legitimately contains top-level commas and
# angle-bracket template args between the class name and its real body, which the C-only
# regex would misread as an early terminator, falsely excluding a real multi-inheritance
# or templated-base class definition (confirmed via direct regex testing before this
# function was written specifically to avoid that regression). Depth-aware scan, the same
# style as `_dart_scan_terminator`/`_count_top_level_args` elsewhere in this file:
_CPP_BODY_ANCHOR_SEARCH_WINDOW = 500


def _cpp_class_has_body(code_stream: str, scan_start: int) -> bool:
    """True if a real `{` body opens before any of `;`, a top-level `=`, or (before an
    inheritance-list `:` has been seen) a top-level `,` -- the same three non-definition
    signals C's own lookahead already guards against (a bare forward declaration, a
    default-template-arg/other declarator context, and a type-USE inside a larger
    declarator list, e.g. `struct Foo *a, *b;` or a function parameter default
    `void f(struct Foo* p = nullptr)`), but with real paren/bracket/angle depth tracking
    so a real inheritance list's own top-level commas and template args don't trigger a
    false negative. A `)` closing a paren this scan never opened means the scan has
    walked out of an enclosing, already-open context (e.g. a parameter list the class
    match started inside) without finding a real body -- treated the same as any other
    non-definition signal, matching C's own inclusion of `)` in its stop-char set."""
    depth_paren = depth_bracket = depth_angle = 0
    seen_colon = False
    limit = min(scan_start + _CPP_BODY_ANCHOR_SEARCH_WINDOW, len(code_stream))
    pos = scan_start
    while pos < limit:
        ch = code_stream[pos]
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            if depth_paren == 0:
                return False
            depth_paren -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket = max(0, depth_bracket - 1)
        elif ch == "<":
            depth_angle += 1
        elif ch == ">":
            depth_angle = max(0, depth_angle - 1)
        elif depth_paren == 0 and depth_bracket == 0 and depth_angle == 0:
            if ch == "{":
                return True
            if ch == ":":
                seen_colon = True
            elif ch in ";=" or (ch == "," and not seen_colon):
                return False
        pos += 1
    return False


# #1918: ABAP's real parameter declarations live in the DEFINITION section
# (`METHODS name IMPORTING ... .` / `CLASS-METHODS name IMPORTING ... .`), never inside the
# IMPLEMENTATION section's `METHOD name. ... ENDMETHOD.` body that _slice_by_labels (Mode A)
# slices per function -- so a per-function args count needs its own DEFINITION-section lookup,
# built once per file (not re-scanned per function) and indexed by method name.
_ABAP_METHOD_DECL_RE = re.compile(r"^[ \t]*(?:METHODS|CLASS-METHODS)[ \t]+([a-zA-Z_][a-zA-Z0-9_~]*)", re.I | re.M)

# Within one method's DEFINITION-section signature span, real parameter-binding clauses
# (IMPORTING/EXPORTING/CHANGING/RETURNING/RECEIVING/EXCEPTIONS) are found the same way the
# `args` structural signature finds them elsewhere -- this constant intentionally mirrors that
# regex's own keyword list (not the compiled `args` rule itself, which is a per-clause
# EXISTENCE detector -- see its own comment in language_standards.py -- not usable here, where
# the whole point is counting every declared parameter NAME within a clause, not just detecting
# that the clause exists).
_ABAP_PARAM_CLAUSE_KEYWORDS = ("IMPORTING", "EXPORTING", "CHANGING", "RETURNING", "RECEIVING", "EXCEPTIONS")
_ABAP_PARAM_CLAUSE_RE = re.compile(r"\b(" + "|".join(_ABAP_PARAM_CLAUSE_KEYWORDS) + r")\b", re.I)
# A parameter declaration line always starts with its (optionally `!`-escaped) name -- real
# ABAP formatting in this corpus keeps each parameter's full declaration (name, TYPE clause,
# DEFAULT/OPTIONAL modifiers) on one line, so a per-line anchor is sufficient without needing
# to also parse the TYPE clause itself.
_ABAP_PARAM_LINE_RE = re.compile(r"^[ \t]*!?[a-zA-Z_][a-zA-Z0-9_]*", re.M)
# RETURNING's parameter is always exactly one `VALUE(name)` -- never a bare name line the way
# IMPORTING/EXPORTING/CHANGING/RECEIVING/EXCEPTIONS parameters are.
_ABAP_RETURNING_VALUE_RE = re.compile(r"VALUE[ \t]*\([ \t]*[a-zA-Z_][a-zA-Z0-9_]*[ \t]*\)", re.I)

# Canonicalizes one assembly `args` register match to the physical register it names, so
# different-width references to the SAME argument-passing slot (edi/rdi, w3/x3, al/ah/ax)
# collapse to one distinct count instead of being counted as separate arguments. Order matters
# -- earlier alternatives must be tried first since some patterns are prefixes of others (e.g.
# an [er]-prefixed di/si/dx/cx must be checked before the bare si/di fallback).
_ASSEMBLY_ARG_REG_CANON_RE = re.compile(r"^(?:[er](di|si|dx|cx)|(r[89])[dwb]?|w([0-7])|([abcd])[xhl])$", re.IGNORECASE)

# #1853: languages whose signatures genuinely use `<...>` for generics/templates,
# so `_count_top_level_args` should track `<`/`>` as bracket depth for them. Every
# other language reaching that counter (Python's `def foo(a = (x < y))` default-
# value repro, plain C, etc.) has no such syntax, so treating `<`/`>` there as
# anything but ordinary comparison/shift operators only ever corrupts the depth
# counter -- gating removes that false-positive class without touching the
# generic-tracking these languages actually need.
_ANGLE_BRACKET_GENERIC_LANGUAGES = frozenset(
    {"cpp", "rust", "csharp", "java", "kotlin", "scala", "typescript", "swift", "go", "dart"}
)

# #1949: `_slice_by_labels`' shared `assembly_returns` terminator vocabulary is
# ambiguous in these specific languages -- the same keyword is real, legitimate
# MID-body control flow there, not a statement that ends the enclosing
# function/paragraph/method, confirmed against real corpus source: Fortran's
# `EXIT` is a DO-loop break (`language-crucible/data/fortran/wrf/module_sf_noahdrv.F:1999`,
# inside `SUBROUTINE SFLX`), ABAP's `RETURN`/`EXIT` are an early-exit guard
# clause and a DO-loop break respectively (both inside method `delete`,
# `language-crucible/data/abap/abapGit/zcl_abapgit_ajson.clas.abap:192,307`).
# Excluded per-language rather than dropped from the shared pattern outright,
# since the same keyword IS a valid terminator in other Mode A languages (e.g.
# COBOL's own `RETURN`/`EXIT`).
_NON_TERMINATING_KEYWORDS_BY_LANG: dict[str, frozenset[str]] = {
    "fortran": frozenset({"EXIT"}),
    "abap": frozenset({"RETURN", "EXIT"}),
}

# #1949 follow-up: a Mode A "function" can be a bare data/constant definition
# rather than real code -- confirmed against real corpus source. NASM's `equ`
# directive assigns a constant to a label
# (`max_entries:    equ sector_size/entry_size` in
# `language-crucible/data/assembly/bootos/os.asm:166`), and GAS's dot-directives
# define static data the same way (`ape.ident:` immediately followed by
# `.long 2f-1f` -- an ELF note record, not a subroutine -- in
# `language-crucible/data/assembly/cosmopolitan/ape.S:781`; `str.error:` followed
# by `.asciz "error: "` at `ape.S:1226`). Checked against just the FIRST physical
# line of the already-sliced block (not requiring the whole block collapse to one
# line the way the original #1949 single-line-rescue check did) -- a data label's
# swallowed span can run many lines past the directive itself (trailing comments,
# blank lines, or a multi-field record like `ape.ident`'s), so gating on total
# block length under-caught this same shape. Deliberately excludes alignment/
# metadata directives (`.balign`, `.align`, `.p2align`, `.section`, `.size`,
# `.type`) that a REAL function can legitimately open with (entry-point alignment
# is a common, real optimization) -- only directives that unambiguously define a
# VALUE are treated as proof this is data, not code. The gap between the label's
# colon and the directive is `[ \t\n]{0,80}`, not same-line-only whitespace,
# since GAS style commonly puts the label alone on its own line with the
# directive on the next (`ape.ident:` / `\t.long\t2f-1f` on separate lines) --
# bounded to 80 chars, same conservative cap this module's other single-char-class
# gap regexes use, so it stays a fixed-cost lookahead, not an unbounded scan.
# `assembly`'s own `func_start` regex has no visibility into what follows the
# label's colon (it only anchors on the label itself), so this can't be excluded
# there the way COBOL's reserved-word shield excludes SOURCE-COMPUTER/
# OBJECT-COMPUTER -- checked here instead, against the sliced block. Scoped to
# `assembly` only: agc_assembly's own data pseudo-ops are different (`EQUALS`,
# `EBANK=`, ...) and its single-line rescues were confirmed all real via #1949's
# own repro.
_ASSEMBLY_DATA_DIRECTIVE_RE = re.compile(
    r"^[A-Za-z_?@.][A-Za-z0-9_.$?@]*[ \t]*:[ \t\n]{0,80}"
    r"(?:equ|db|dw|dd|dq|dt|do|resb|resw|resd|resq|rest|reso|times"
    r"|\.byte|\.asciz|\.ascii|\.string|\.word|\.short|\.long|\.quad|\.octa"
    r"|\.double|\.float|\.space|\.skip|\.zero|\.fill|\.set|\.equ)\b",
    re.IGNORECASE,
)

# #1973: matches a Dockerfile heredoc opener (`RUN <<EOF`, `RUN --mount=... <<-EOT`)
# at the end of a line, capturing the terminator word so
# _mode_a_args_window_end can recognize the matching closing line and skip
# the whole heredoc body as part of one instruction's own statement span
# (never counted as unrelated later content). The terminator capture is
# bounded to 61 chars and the whole match is applied to one already-sliced
# physical line (never unbounded input), so this stays a fixed-cost check.
_DOCKERFILE_HEREDOC_OPENER_RE = re.compile(r"<<-?[ \t]*(?:['\"]?)([A-Za-z_][A-Za-z0-9_]{0,60})(?:['\"]?)[ \t]*$")


def _resolve_class_start_match(match: re.Match, groups_count: int) -> tuple[Optional[int], str, list[str]]:
    """Given a `class_start` regex match and its pattern's total capture-group
    count, return `(name_group_idx, name, inheritance)`.

    `class_start` regexes vary in capture-group shape across the languages in
    `_CLASS_START_NAMED_EXTRACTION_LANGS` -- most have a mandatory group 1
    (the name) and an optional group 2 (a single inheritance parent), but
    Fortran/Lua/ABAP-shaped patterns use alternation where the name lands in
    EITHER group 1 or group 2 depending on which branch fired, and some
    languages capture no name at all (pure occurrence-counting rules, e.g.
    C -- see the frozenset's own comment). `name_group_idx` is `None`
    in that last case; callers should fall back to `match.start(0)` for the
    anchor position and `"Anonymous_Class"` for the name.

    Factored out (rather than left inline in `splice()`) so
    `tests/tools/class_start_diff.py` -- the offline triage tool for
    extending the allowlist to more languages (#1295) -- can preview exactly
    what a language's own `class_start` rule would name, using the identical
    algorithm the live pipeline uses, with no risk of the two drifting apart.
    """
    if groups_count >= 1 and match.group(1):
        name_group_idx: Optional[int] = 1
    elif groups_count >= 2 and match.group(2):
        name_group_idx = 2
    else:
        name_group_idx = None

    name = match.group(name_group_idx) if name_group_idx else "Anonymous_Class"
    inheritance = [match.group(2)] if name_group_idx == 1 and groups_count >= 2 and match.group(2) else []
    return name_group_idx, name, inheritance


class StructuralExtractor:
    """
    GitGalaxy Structural Extractor (Primary Heuristic Logic & Function Mapper).

    PURPOSE: Performs AST-less analysis of executable logic streams to extract
    functional nodes, calculate complexity, and detect structural security signatures.

    DEFENSIVE ARCHITECTURE (Lexical Heuristics vs. AST Parsing):
    AST parsers often fail when encountering non-standard syntax, legacy dialects,
    or partially-broken codebases. This extractor utilizes Fluid State Counters
    and O(1) lexical masking to achieve high-fidelity node extraction at
    ~100,000 LOC/sec, maintaining high performance without requiring
    fully-compilable source code.

    ARCHITECTURE:
    1. Fluid State Counter: Dynamically swaps regex registries mid-file for embedded languages.
    2. Bucket Continuation: Accumulates secondary language hits into the primary vector.
    3. Integration Modes: Labels (A), Braces (B), Indentation (C), Keywords (D), Terminators (E).
    """

    # --- DYNAMIC SCHEMA FETCH ---
    # Directly mirrors the central registry to prevent schema drift
    UNIVERSAL_METRICS_SCHEMA = RECORDING_SCHEMAS.get("SIGNAL_SCHEMA", [])

    # #1183: this used to be a hand-maintained duplicate of LENS_CONFIG's
    # HANDSHAKE_REGISTRY (gitgalaxy/standards/language_standards.py) that had
    # drifted out of sync -- it dropped the "^[ \t]*...\b" line-anchoring the
    # canonical config uses, so an unanchored "<script"/"<style" substring
    # matched even inside a string/regex literal (e.g. Python test fixture
    # data describing an embedded-JS trigger), permanently misrouting every
    # function for the rest of the file to the wrong language's rules.
    # Deriving directly from LENS_CONFIG keeps the two in permanent sync.
    # re.M is required for the "^" anchor to match at the start of any line
    # rather than only the start of the whole file -- without it, a genuine
    # mid-file "<script>" (the normal case) would never match either.
    HANDSHAKE_REGISTRY: ClassVar[list[dict[str, Any]]] = [
        {
            "trigger": re.compile(h["trigger"], re.I | re.M),
            "end": re.compile(h["end"], re.I | re.M),
            "target": h["target"],
            "pair": h["pair"],
        }
        for h in LENS_CONFIG["HANDSHAKE_REGISTRY"]
    ]

    def __init__(
        self,
        lang_id: str,
        language_definitions: dict[str, Any],
        parent_logger: Optional[logging.Logger] = None,
    ):
        if parent_logger:
            self.logger = parent_logger.getChild("splicer")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("splicer")
            self.logger.setLevel(logging.INFO)

        self.primary_lang_id = lang_id.lower() if lang_id else "unknown"
        # Pinned explicitly: LANGUAGE_DEFINITIONS (assigned to this same
        # attribute below, in the AUTO-HEAL branch) has no module-level
        # annotation, so mypy infers its instance-attribute type from that
        # massive nested literal instead of this constructor's declared
        # Dict[str, Any] param -- which doesn't support the plain .get()
        # calls this class relies on throughout.
        self.languages: dict[str, Any] = language_definitions

        lang_config: dict[str, Any] = self.languages.get(self.primary_lang_id, {})
        self.primary_rules: dict[str, Any] = lang_config.get("rules", {})
        self.primary_family = lang_config.get("lexical_family", "c_style_comment")

        # #1949: `END-PERFORM`/`END-IF` were removed entirely -- both are block
        # *closers*, never a real function/paragraph-terminating statement in
        # any Mode A language, so no per-language exclusion can save them; a
        # COBOL paragraph's real trailing instructions were being dropped
        # whenever a nested `IF ... END-IF` happened to appear before them
        # (`language-crucible/data/cobol/cics-banking-sample-application-cbsa/BNKMENU.cbl:242`,
        # paragraph `PMM010.`). `RELINT` was also removed outright (not just
        # per-language-excluded) since AGC's own idiom commonly uses it to
        # *open* a long interrupt handler rather than close one
        # (`language-crucible/data/agc_assembly/apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc:303`,
        # routine `ELOOPFIN`) -- unlike `EXIT`/`RETURN` below, no Mode A
        # language in this corpus was observed using `RELINT` as a genuine
        # terminator, so there was no case worth preserving via the
        # per-language exclusion map instead.
        self.assembly_returns = re.compile(
            r"\b(?:TC\s+Q|TCF\s+Q|RETURN|RESUME|RET|RTS|JMP\s+LR|BLR|GOBACK|EXIT)\b",
            re.IGNORECASE,
        )

        # #1145: universal (not per-language) variable-declaration-shaped assignment
        # matcher -- same "one regex for every language" precedent as indent_tabs/
        # indent_spaces in coding_analysis(), since identifier casing is a lexical/
        # formatting property, not a language-semantic one that needs 59 hand-tuned
        # per-language regexes. Captures the identifier immediately before an
        # unguarded `=` (`(?!=)` excludes `==`), tolerating an optional bounded,
        # whitespace-terminated prefix -- this reaches the declared name whether
        # it's bare (`x = 5`), keyword-led (`let x = 5`), or C-style typed
        # (`Map<String,Integer> counterMap = ...`) without needing a type-keyword
        # enumeration. `[^=\n]{0,80}` is capped so its overlap with the adjacent
        # `[ \t]+` run (Rule 14) stays a small bounded constant, not unbounded --
        # confirmed linear (not quadratic) via a manual ReDoS scaling sweep.
        self._var_decl_pattern = re.compile(
            r"^[ \t]*(?:[^=\n]{0,80}[ \t]+)?([A-Za-z_]\w{0,63})[ \t]*=(?!=)",
            re.M,
        )

        self.CORE_MAPPING = {
            "branching": "branch",
            "io_ops": "io",
            "safety": "safety",
            "high_risk_execution": "high_risk_execution",
            "concurrency": "concurrency",
            "logic_flux": "state_mutation",
        }

        self.MAX_DEPTH = 50
        self.HANDSHAKE_LOOKAHEAD_LIMIT = 50000

        if self.primary_lang_id not in self.languages or "rules" not in self.languages.get(self.primary_lang_id, {}):
            try:
                from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

                # Apply the healed definitions to the instance state. cast():
                # despite self.languages being pinned to Dict[str, Any] above,
                # reassigning it from LANGUAGE_DEFINITIONS here re-narrows it
                # to LANGUAGE_DEFINITIONS' own (unannotated, wide) inferred
                # type for the rest of this branch -- confirmed via
                # reveal_type that .get() on it then returns `object`, not
                # Any. The cast forces it back to the declared type instead
                # of fighting that narrowing.
                self.languages = cast(dict[str, Any], LANGUAGE_DEFINITIONS)
                # renamed (not reusing lang_config): mypy rejects
                # re-annotating the same name twice in one scope.
                healed_lang_config: dict[str, Any] = self.languages.get(self.primary_lang_id, {})
                self.primary_rules = healed_lang_config.get("rules", {})
                self.primary_family = healed_lang_config.get("lexical_family", "c_style_comment")

                self.logger.warning(f"[AUTO-HEAL] Re-injected LANGUAGE_DEFINITIONS for '{self.primary_lang_id}'")
            except ImportError:
                pass

    def splice(
        self,
        code_stream: str,
        comment_stream: str,
        confidence: float = 1.0,
        profile_regex: bool = False,
        raw_content: str = "",
    ) -> dict[str, Any]:
        """Executes the structural regex pass over refracted code streams."""
        self.raw_content_lines = raw_content.splitlines() if raw_content else []
        regex_telemetry: dict[str, float] = {}

        # We always extract the metadata first, even for Unparsable Artifacts
        ghost_meta = self._decode_comment_stream(comment_stream)

        # ---> THE ECOSYSTEM GRAVITY OVERRIDE <---
        # If the broader ecosystem safely locked a contested file (like a .h header)
        # into a C-family language, we trust the gravity and artificially boost the confidence.
        # This prevents pure-macro headers from falling below the 0.42 floor and vanishing into Unparsable Artifacts.
        if self.primary_lang_id in ["c", "cpp", "objective-c"]:
            confidence = 1.0

        # 1. The Custom Unparsable Artifact Bypass & Prose Deflection
        # Rejects unverified artifacts AND Static Assets before wasting compute
        # #694: yaml/json/csv used to sit here too, treated like pure prose --
        # but unlike plaintext (empty rules dict, genuinely nothing to gain),
        # they have real non-empty rules dicts AND prism.py already populates
        # their code_stream correctly (none of the three go through prism.py's
        # Prose Bypass, unlike markdown -- see #691). signal_processor.py's own
        # doc_languages set already excludes all three, correctly treating them
        # as real structured content that can carry genuine risk signal (a
        # malicious package.json postinstall script, a `rm -rf /` in a CI
        # yaml). This gate was the one place still treating them as prose;
        # removing them lets them fall through to the normal code_stream path
        # below, same as every real code language.
        if confidence < 0.42 or self.primary_lang_id in ("plaintext",):
            self.logger.debug(
                f"[DIAGNOSTIC] Bypass triggered (Conf: {confidence:.2f} | Lang: {self.primary_lang_id}). Relegating to Unparsable Artifacts."
            )
            return {
                "equations": {},
                "functions": [],
                "logic_density": 0.0,
                "sum_fxn_impact": 0.0,
                "total_control_flow_ratio": 0.0,
                "raw_imports": [],
                "metadata": ghost_meta,
            }

        # 1b. Markdown Prose Deflection (Issue #691)
        # Markdown has no functions/control-flow to run coding_analysis against
        # (prism.py's Prose Bypass always routes its entire content into
        # comment_stream, leaving code_stream empty), but it DOES have real
        # structural signatures (lit_code_blocks/lit_diagrams/lit_headers/
        # lit_links) that live in comment_stream. Route it through
        # comment_analysis instead of the blanket empty-return the other
        # prose/structured-data languages above still get -- this leaves
        # coding_loc/doc_loc semantics (and everything downstream of them)
        # completely untouched, since we never touch code_stream here.
        if self.primary_lang_id == "markdown":
            counts = dict.fromkeys(self.UNIVERSAL_METRICS_SCHEMA, 0)
            counts = self.comment_analysis(comment_stream, self.primary_lang_id, counts)
            return {
                "equations": counts,
                "functions": [],
                "logic_density": 0.0,
                "sum_fxn_impact": 0.0,
                "total_control_flow_ratio": 0.0,
                "raw_imports": [],
                "metadata": ghost_meta,
            }

        if not code_stream:
            return {
                "equations": {},
                "functions": [],
                "logic_density": 0.0,
                "sum_fxn_impact": 0.0,
                "total_control_flow_ratio": 0.0,
                "raw_imports": [],
                "metadata": ghost_meta,
            }

        # --- THE ANTI-REDOS SHIELD (Line Length Limiter) ---
        # Identifies absurdly long continuous lines (Make .depend files, C hex arrays)
        # and blanks them out before they reach the regex engine. Neutralizes Catastrophic
        # Backtracking while perfectly preserving the file's geometry (mass and LOC).
        safe_lines = []
        for line in code_stream.split("\n"):
            if len(line) > 1500:
                # Preserve indentation and inject a single safe char so it isn't counted as a blank line
                indent = len(line) - len(line.lstrip())
                safe_lines.append(" " * indent + "x" + " " * (len(line) - indent - 1))
            else:
                safe_lines.append(line)
        code_stream = "\n".join(safe_lines)

        try:
            line_count = sum(1 for l in code_stream.splitlines() if l.strip())

            # --- EXISTING STRUCTURAL PIPELINE ---
            segments = self._partition_segments(code_stream, self.primary_lang_id)

            equations, mitigation_telemetry, segment_spatial_maps, extracted_parents, threat_locations = (
                self.coding_analysis(segments, regex_telemetry if profile_regex else None)
            )

            if extracted_parents:
                # Store the top 3 parent entities to prevent massive string bloat on huge files
                ghost_meta["parent_entity"] = ", ".join(list(dict.fromkeys(extracted_parents))[:3])

            equations = self.comment_analysis(comment_stream, self.primary_lang_id, equations)

            functions, sum_fxn_impact = self._function_slice(
                segments,
                segment_spatial_maps,
                equations,
                mitigation_telemetry,
                regex_telemetry if profile_regex else None,
            )

            # ---> NEW: FAST CLASS EXTRACTOR & FUNCTION LINKAGE <---
            classes: list[_ClassInfoWithBounds] = []
            # #1264: for the verified-clean languages in
            # _CLASS_START_NAMED_EXTRACTION_LANGS, use each language's own
            # `class_start` rule -- the same rule func_start already consults
            # correctly a few lines up -- instead of one hardcoded, language-
            # agnostic regex (`class|struct|interface|trait|enum` behind a
            # single-slot `export|public|abstract` modifier). That fallback
            # silently produced 0% class recall for any language whose OOP
            # keyword isn't in that fixed set (Fortran's MODULE/TYPE,
            # Solidity's contract/library) or whose modifier grammar allows
            # more than one word/isn't in that 3-word list (Apex's "public
            # with sharing", C#'s "internal sealed partial"). Everyone else
            # stays on the legacy fallback until their own class_start is
            # hardened for this use (see the frozenset's comment).
            class_start_pattern = (
                self.languages.get(self.primary_lang_id, {}).get("rules", {}).get("class_start")
                if self.primary_lang_id in _CLASS_START_NAMED_EXTRACTION_LANGS
                else None
            )
            if class_start_pattern is not None:
                class_matches = list(class_start_pattern.finditer(code_stream))
                # class_start regexes vary in capture-group shape across
                # these languages -- most have a mandatory group 1 (the
                # name) and an optional group 2 (a single inheritance
                # parent), but Fortran uses alternation where the name lands
                # in EITHER group 1 or group 2 depending on which branch
                # fired. Resolved per-match below rather than assumed here.
                class_start_groups = class_start_pattern.groups
            else:
                # Legacy fallback: one hardcoded regex catching the common
                # `[modifier] (class|struct|interface|trait|enum) Name`
                # shape, for every language not yet verified safe to extract
                # named classes from its own class_start rule.
                class_start_pattern = re.compile(
                    r"^\s*(?:export\s+|public\s+|abstract\s+)?(?:class|struct|interface|trait|enum)\s+([a-zA-Z0-9_]+)"
                    r"(?:\s*(?:\(|extends\s+|implements\s+|:\s*)([a-zA-Z0-9_]+))?",
                    re.MULTILINE,
                )
                class_matches = list(class_start_pattern.finditer(code_stream))
                class_start_groups = 2

            # #1040: a flat "ends at the next class match" boundary truncates
            # an outer class's scope the instant it contains a nested class,
            # since the nested class's own `class` keyword becomes that "next
            # match". Resolve each class's real end via brace-depth (or, for
            # indentation-scoped languages, dedent-depth) tracking instead --
            # same dispatch this engine already uses for Mode B vs Mode C
            # function slicing -- so a nested class's body is correctly
            # consumed as part of its enclosing class rather than cutting it
            # off early. Computed unconditionally (not just when class_matches
            # is non-empty) so class_safe_stream/use_indentation_scoping are
            # never referenced uninitialized below.
            lang_family = self.languages.get(self.primary_lang_id, {}).get("lexical_family", "c_style_comment")
            use_indentation_scoping = self.primary_lang_id in ("python", "yaml") or lang_family in (
                "single_line_only",
                "multi_style_dash",
            )
            class_safe_stream = (
                self._build_indentation_safe_stream(code_stream)
                if use_indentation_scoping
                else self._build_brace_safe_stream(code_stream, self.primary_lang_id)
            )

            for i, match in enumerate(class_matches):
                if self.primary_lang_id == "cpp":
                    if not _cpp_class_has_body(code_stream, match.end()):
                        continue
                elif self.primary_lang_id in _CLASS_START_REQUIRES_BODY_ANCHOR:
                    lookahead = code_stream[match.end() : match.end() + 200]
                    anchor_match = re.search(r"^[^\{;,)=]{0,200}?([\{;,)=])", lookahead)
                    if not anchor_match or anchor_match.group(1) != "{":
                        continue

                name_group_idx, name, inheritance = _resolve_class_start_match(match, class_start_groups)

                # Anchored on the class NAME's own position, not
                # match.start(0): a pattern's leading optional whitespace/
                # annotation/modifier span can itself swallow a blank line
                # sitting before the keyword, landing match.start(0) on that
                # blank line instead of the declaration's real line -- which
                # would corrupt the brace/indent-depth math below. The name
                # always sits on the class's own line, so it's a reliable
                # anchor whenever one was captured; falls back to
                # match.start(0) for the handful of languages whose
                # class_start captures no name (anonymous structs, etc.).
                start_idx = match.start(name_group_idx) if name_group_idx else match.start(0)
                # Old flat boundary, now used only as a fallback for brace-less
                # forward declarations where no real body can be located.
                fallback_end_idx = class_matches[i + 1].start() if i + 1 < len(class_matches) else len(code_stream)
                if self.primary_lang_id in ("abap", "dockerfile"):
                    # #1907: ABAP has no brace-delimited class bodies at all
                    # (IMPLEMENTATION. ... ENDCLASS.), but DOES have string-
                    # template interpolation syntax (`|Object { name }|`)
                    # containing real `{`/`}` that _build_brace_safe_stream
                    # doesn't know to shield (it only understands `"`/`'`/
                    # backtick-style quoting). The brace search below would
                    # mistake that interpolation brace for the class's real
                    # body opener and truncate the scope after the first
                    # couple of methods. ABAP classes are never nested, so
                    # the flat "next class match, or EOF" fallback is always
                    # correct here -- skip the brace search entirely.
                    # #1974: Dockerfile shares this exact problem with its own
                    # `${VAR}` template-substitution braces. Build stages are
                    # never nested, so skip the brace search entirely here too.
                    end_idx = fallback_end_idx
                else:
                    end_idx = self._resolve_class_scope_end(
                        class_safe_stream, start_idx, fallback_end_idx, use_indentation_scoping
                    )

                # Convert raw string indices to line numbers for spatial bounding
                start_line = code_stream.count("\n", 0, start_idx) + 1
                end_line = code_stream.count("\n", 0, end_idx) + 1
                # If end_idx sits exactly at the start of a new line (the
                # indentation resolver's dedent point, or the flat fallback,
                # both land there by construction) that line belongs to
                # whatever comes *next* -- a sibling method after a nested
                # class dedents, or the next class's own header -- not to
                # this class, so don't count it as part of this class's range.
                if 0 < end_idx <= len(code_stream) and code_stream[end_idx - 1] == "\n":
                    end_line -= 1

                classes.append(
                    {
                        "name": name,
                        "inheritance": inheritance,
                        "_start_line": start_line,
                        "_end_line": end_line,
                        "method_count": 0,
                        "state_entanglement": 0.0,
                    }
                )

            # ---> LINK FUNCTIONS TO CLASSES & CALCULATE CLASS PHYSICS <---
            # Assign each function to its innermost (most specific) enclosing
            # class first. Nesting-aware scopes mean an outer class's span now
            # correctly contains everything a nested class's span also contains
            # -- so without this step, a nested class's methods would double-
            # count toward every enclosing outer class too, not just the nested
            # class itself.
            class_methods_by_id: dict[int, list[FunctionNode]] = {id(cls): [] for cls in classes}
            for func in functions:
                func_line = func.get("start_line", 0)
                innermost_cls: Optional[_ClassInfoWithBounds] = None
                for cls in classes:
                    if cls["_start_line"] <= func_line <= cls["_end_line"] and (
                        innermost_cls is None or cls["_start_line"] > innermost_cls["_start_line"]
                    ):
                        innermost_cls = cls
                if innermost_cls is not None:
                    func["parent_class_name"] = innermost_cls["name"]
                    class_methods_by_id[id(innermost_cls)].append(func)

            for cls in classes:
                class_methods = class_methods_by_id[id(cls)]
                cls["method_count"] = len(class_methods)

                # State Entanglement: Density of state mutations (flux) inside the class methods
                total_flux = sum(m.get("hit_vector", {}).get("state_mutation", 0) for m in class_methods)
                cls["state_entanglement"] = round((total_flux / max(cls["method_count"], 1)) * 5.0, 2)

                # Erase the temporary spatial boundaries
                del cls["_start_line"]
                del cls["_end_line"]

            branch_hits = equations.get("branch", 0)
            linear_hits = equations.get("structural_boundaries", 0)
            total_control_flow_ratio = round(branch_hits / max(branch_hits + linear_hits, 1), 3)

            # Use the newly standardized keys from the updated coding_analysis
            total_signals = sum(equations.values())
            logic_density = round(total_signals / line_count, 3) if line_count > 0 else 0.0

            # --- NEW: INTRA-FILE ORPHAN & DUPLICATE DETECTOR ---
            import collections
            import hashlib

            # Fast, C-backed word frequency counter for the entire file
            token_counts = collections.Counter(re.findall(r"\b\w+\b", code_stream))

            orphan_count = 0
            duplicate_count = 0
            func_names = [f.get("name", "") for f in functions]
            func_name_counts = collections.Counter(func_names)

            # Name collisions alone don't prove duplication: languages like Haskell
            # idiomatically reuse a generic local-helper name (e.g. `go`) across many
            # unrelated `where`/`let` scopes in the same file, which are legitimately
            # distinct functions, not copy-pasted logic (#1498). Require the body's
            # normalized content to also match before treating same-named functions
            # as duplicates -- only computed for names that actually collide, since
            # hashing every function body would be wasted work in the common case.
            body_hash_counts: collections.Counter[tuple[str, str]] = collections.Counter()
            func_body_hashes: dict[int, str] = {}
            for func in functions:
                func_name = func.get("name", "")
                if func_name and func_name_counts[func_name] > 1:
                    start_idx = func.get("start_idx", 0)
                    end_idx = func.get("end_idx", start_idx)
                    normalized_body = re.sub(r"\s+", " ", code_stream[start_idx:end_idx]).strip()
                    body_hash = hashlib.md5(
                        normalized_body.encode("utf-8", "ignore"), usedforsecurity=False
                    ).hexdigest()
                    func_body_hashes[id(func)] = body_hash
                    body_hash_counts[(func_name, body_hash)] += 1

            for func in functions:
                func_name = func.get("name", "")
                usage_status = 0  # 0 = Normal

                # Check for Duplicates: same name AND materially the same body,
                # defined multiple times in the same file.
                if (
                    func_name
                    and func_name_counts[func_name] > 1
                    and body_hash_counts[(func_name, func_body_hashes[id(func)])] > 1
                ):
                    usage_status = 2  # 2 = Duplicate
                    duplicate_count += 1
                elif len(func_name) > 3 and func_name not in {
                    "Unknown_Sat",
                    "Anonymous_Block",
                    "Main",
                    "Declarative_Block",
                }:
                    # If the function name only exists where it was defined, it's an orphan
                    if token_counts[func_name] <= 1:
                        orphan_count += 1
                        usage_status = 1  # 1 = Orphan / Unused

                func["usage_status"] = usage_status

            if orphan_count > 0:
                equations["orphaned_logic"] = orphan_count
            if duplicate_count > 0:
                equations["duplicate_logic"] = duplicate_count

            # --- NEW: NAMING-CONVENTION CLASSIFIER (#1145) ---
            # core_var_decl feeds signal_processor.py's encapsulation_ratio (total_vars)
            # -- until now it was permanently 0, which silently floored that ratio to
            # 0.0 for any file with a single global-state hit. The design_* buckets
            # classify each declared identifier's casing/length for style-consistency
            # and outlier signal.
            for decl_match in self._var_decl_pattern.finditer(code_stream):
                equations["core_var_decl"] += 1
                identifier = decl_match.group(1)

                casing_bucket = self._classify_identifier_casing(identifier)
                if casing_bucket:
                    equations[casing_bucket] += 1

                name_len = len(identifier)
                if name_len <= 2:
                    equations["design_short_vars"] += 1
                elif name_len >= 25:
                    equations["design_long_vars"] += 1

            # Calculate total file footprint, preferring the unshielded raw text if available
            file_token_mass = get_token_mass(raw_content if raw_content else code_stream)

            result_payload = {
                "equations": equations,
                "classes": classes,
                "functions": functions,
                "logic_density": logic_density,
                "sum_fxn_impact": sum_fxn_impact,
                "total_control_flow_ratio": total_control_flow_ratio,
                "metadata": ghost_meta,
                "mitigation_telemetry": mitigation_telemetry,
                "token_mass": file_token_mass,
                "financial_read_cost": (
                    round((file_token_mass / 1000000) * 3.00, 5) if file_token_mass is not None else None
                ),
                "threat_locations": threat_locations,
            }
            if profile_regex:
                result_payload["regex_telemetry"] = regex_telemetry
            return result_payload

        except TimeoutError:
            # Let the Hardware Guillotine drop cleanly to the Worker thread!
            raise
        except Exception as e:
            self.logger.error(f"Catastrophic failure during structural splicing: {e}", exc_info=True)
            return {
                "equations": {},
                "functions": [],
                "logic_density": 0.0,
                "sum_fxn_impact": 0.0,
                "total_control_flow_ratio": 0.0,
                "raw_imports": [],
                "metadata": ghost_meta,
            }

    @staticmethod
    def _classify_identifier_casing(name: str) -> Optional[str]:
        """Buckets a declared identifier into one mutually-exclusive casing style (#1145)."""
        if re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", name):
            return "design_upper_case"
        if "_" in name and name.islower():
            return "design_snake_case"
        if re.fullmatch(r"[a-z][a-z0-9]*", name):
            # Bare lowercase, no underscore or uppercase (e.g. "count") -- still a
            # valid single-word instance of snake_case, not a distinct style.
            return "design_snake_case"
        if re.fullmatch(r"[A-Z][a-zA-Z0-9]*", name) and not name.isupper():
            return "design_pascal_case"
        if re.fullmatch(r"[a-z][a-zA-Z0-9]*", name):
            return "design_camel_case"
        return None

    def _decode_comment_stream(self, comment_stream: str) -> dict[str, str]:
        meta = {"ownership": "Unknown Architect"}
        if not comment_stream:
            return meta

        re_ownership = self.primary_rules.get("ownership")
        ownership_val = None
        if re_ownership:
            try:
                m_owner = re_ownership.search(comment_stream)
                if m_owner:
                    ownership_val = (
                        m_owner.group(m_owner.lastindex).strip() if m_owner.lastindex else m_owner.group(0).strip()
                    )
            except Exception as e:
                self.logger.debug(f"Ownership regex extraction failed, leaving 'Unknown Architect': {e}")

        if ownership_val:
            raw_ownership = re.sub(r"<[^>]+>", "", ownership_val).strip()
            raw_ownership = raw_ownership.rstrip(".,;-")
            if raw_ownership:
                meta["ownership"] = raw_ownership

        # Look for the underscore-prefixed metadata rules
        re_purpose_line = self.primary_rules.get("_meta_purpose_line")
        re_purpose_block = self.primary_rules.get("_meta_purpose_block")
        re_boundary = self.primary_rules.get("_meta_boundary")

        if not (re_purpose_line or re_purpose_block):
            return meta

        # ---> MEMORY CAP <---
        # We only scan the top 500 lines anyway, so hard-cap the string at ~15,000 characters
        # to prevent massive license blocks or generated data from thrashing the regex engine.
        capped_stream = comment_stream[:15000]

        clean_text = re.sub(
            r"^[ \t]*([#/*!\-]+|[Cc][ \t]+)[ \t]*",
            "",
            capped_stream,
            flags=re.MULTILINE,
        )
        lines = clean_text.splitlines()

        active_capture = None
        purpose_buffer = []
        fallback_buffer = []
        has_block_text = False

        for line in lines[:500]:
            line_str = line.strip()

            if active_capture == "block":
                if not line_str:
                    if has_block_text:
                        break
                    else:
                        continue
                if re_boundary and hasattr(re_boundary, "match") and re_boundary.match(line_str):
                    break
                purpose_buffer.append(line_str)
                has_block_text = True
                continue

            if active_capture == "line":
                if (
                    not line_str
                    or (re_boundary and hasattr(re_boundary, "match") and re_boundary.match(line_str))
                    or (re_purpose_block and hasattr(re_purpose_block, "match") and re_purpose_block.match(line_str))
                ):
                    active_capture = None
                else:
                    fallback_buffer.append(line_str)
                    continue

            if re_purpose_block and hasattr(re_purpose_block, "match") and re_purpose_block.match(line_str):
                active_capture = "block"
                purpose_buffer = []
                has_block_text = False
                continue

            if re_purpose_line and hasattr(re_purpose_line, "match") and not purpose_buffer:
                try:
                    m_purpose = re_purpose_line.match(line_str)
                    if m_purpose:
                        active_capture = "line"
                        purpose_text = (
                            m_purpose.group(m_purpose.lastindex).strip()
                            if m_purpose.lastindex
                            else m_purpose.group(0).strip()
                        )
                        if purpose_text:
                            fallback_buffer.append(purpose_text)
                except Exception as e:
                    self.logger.debug(f"Purpose-line regex extraction failed, skipping this line: {e}")
                continue

        final_purpose = purpose_buffer if purpose_buffer else fallback_buffer
        if final_purpose:
            p_text = " ".join(final_purpose)
            p_text = re.sub(r"\s+", " ", p_text).strip()
            if p_text:
                meta["purpose"] = p_text[:800] + ("..." if len(p_text) > 800 else "")

        return meta

    def _extract_documentation_tether(self, start_line: int, lang_id: str) -> str:
        """Surgically extracts the human intent (docstring/comments) using exact spatial coordinates."""
        if not hasattr(self, "raw_content_lines") or not self.raw_content_lines:
            return ""

        # Convert the 1-indexed start_line to a 0-indexed array position
        i = start_line - 1
        if i < 0 or i >= len(self.raw_content_lines):
            return ""

        doc_buffer: list[str] = []

        # 1. Harvest Above (C, Java, JS, Rust, Go, PHP, C#)
        for j in range(i - 1, max(-1, i - 15), -1):
            prev = self.raw_content_lines[j].strip()
            if not prev:
                continue
            if (
                prev.startswith(("#", "//", "/*", "*", "///", "--", "<!--", "dnl", ";", "%"))
                or prev.endswith("*/")
                or prev.endswith("#>")
            ):
                doc_buffer.insert(0, prev)
            elif prev.startswith("@") or prev.startswith("["):  # Step over decorators safely
                continue
            else:
                break

        # 2. Harvest Below (Python docstrings, MATLAB help, Ruby =begin)
        if lang_id in ("python", "matlab", "ruby", "elixir"):
            in_below_doc = False
            for j in range(i + 1, min(len(self.raw_content_lines), i + 10)):
                nxt = self.raw_content_lines[j].strip()
                if not nxt:
                    continue
                if not in_below_doc:
                    # Only the FIRST non-blank line below the signature is
                    # checked for whether it opens a docstring/comment block.
                    # A subsequent line (e.g. a stand-alone closing '"""')
                    # must never be re-tested against this branch (#246) —
                    # once we're inside the block, only the elif below
                    # applies, regardless of what the line itself starts with.
                    if nxt.startswith(('"""', "'''", "%", "#", "=begin")):
                        doc_buffer.append(nxt)
                        in_below_doc = True
                        # Single-line docstring: opens AND closes on the same
                        # line (e.g. """Summary."""). len(nxt) > 3 excludes a
                        # bare 3-char opening marker with nothing else on it.
                        if len(nxt) > 3 and (nxt.endswith('"""') or nxt.endswith("'''")):
                            break
                    else:
                        break
                else:
                    doc_buffer.append(nxt)
                    if nxt.endswith('"""') or nxt.endswith("'''") or nxt == "=end":
                        break

        return "\n".join(doc_buffer)[:2000]  # Cap at 2000 chars to prevent DB bloat

    def _partition_segments(self, content: str, primary_id: str) -> list[tuple[str, str, int]]:
        """Splits content into language segments based on handshake triggers."""
        segments = []
        last_idx = 0
        current_line_offset = 0

        triggers = [
            {
                "start": m.start(),
                "end_pattern": h["end"],
                "target": h["target"],
                "pair": h["pair"],
                "trigger_end": m.end(),
            }
            for h in self.HANDSHAKE_REGISTRY
            for m in h["trigger"].finditer(content)
        ]

        triggers.sort(key=lambda x: x["start"])

        for t in triggers:
            if t["start"] < last_idx:
                continue

            if t["start"] > last_idx:
                chunk = content[last_idx : t["start"]]
                segments.append((primary_id, chunk, current_line_offset))
                current_line_offset += chunk.count("\n")

            if t["pair"]:
                open_char, close_char = t["pair"]
                end_idx = self._find_balanced_end(content, t["start"], open_char, close_char)
            else:
                search_limit = min(t["trigger_end"] + self.HANDSHAKE_LOOKAHEAD_LIMIT, len(content))
                end_match = t["end_pattern"].search(content, pos=t["trigger_end"], endpos=search_limit)
                end_idx = end_match.end() if end_match else len(content)

            chunk = content[t["start"] : end_idx]
            segments.append((t["target"], chunk, current_line_offset))
            current_line_offset += chunk.count("\n")
            last_idx = end_idx

        if last_idx < len(content):
            chunk = content[last_idx:]
            segments.append((primary_id, chunk, current_line_offset))

        return segments if segments else [(primary_id, content, 0)]

    def _find_balanced_end(self, safe_text: str, start_pos: int, opener: str, closer: str) -> int:
        """
        C-Optimized jump-tracking algorithm.
        Expects 'safe_text' where string literals and comments have already been shielded.
        """
        depth = 0
        limit = min(start_pos + self.HANDSHAKE_LOOKAHEAD_LIMIT, len(safe_text))
        pos = start_pos

        while pos < limit:
            # Ask the C-engine to instantly find the next brace, bypassing Python loops
            next_open = safe_text.find(opener, pos, limit)
            next_close = safe_text.find(closer, pos, limit)

            # If there are no more closing braces, the scope is truncated/malformed. Bail out.
            if next_close == -1:
                break

            # If the opener comes next, dive one level deeper
            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open + 1

                if depth > self.MAX_DEPTH:
                    depth = self.MAX_DEPTH

            # If the closer comes next, surface one level
            else:
                depth -= 1
                pos = next_close + 1

                # We have cleanly exited the original scope
                if depth <= 0:
                    return pos

        return limit

    def _resolve_class_scope_end(
        self,
        safe_stream: str,
        header_start: int,
        fallback_end_idx: int,
        use_indentation: bool,
    ) -> int:
        """
        Resolves a class declaration's true end boundary via brace-depth (or,
        for indentation-scoped languages, dedent-depth) tracking, instead of a
        flat "ends at the next class match" boundary -- which truncates an
        outer class's scope the instant it contains a nested class, since the
        nested class's own `class` keyword becomes that "next match" (#1040).
        `fallback_end_idx` -- the old flat boundary -- is used only when no
        real body can be located (e.g. a brace-less forward declaration).
        `safe_stream` must be the same length as the original code_stream
        (shielding preserves newlines), so indices computed here stay valid
        against it.

        Deliberately anchored on `header_start` (`match.start()`) only, never
        `match.end()`: class_pattern's optional inheritance capture
        (`:\\s*([a-zA-Z0-9_]+)`) lets `\\s*` cross a newline, so for a
        brace-less header like `class Inner:` it can walk onto the *next*
        line and capture its first identifier (e.g. the `def` of a nested
        method) as a bogus "inheritance" token -- pushing `match.end()` well
        past the header's own line. Recomputing the header line directly
        from `header_start` sidesteps that pre-existing regex quirk instead
        of relying on a `match.end()` that isn't trustworthy here.
        """
        line_start_idx = safe_stream.rfind("\n", 0, header_start) + 1
        header_line_end = safe_stream.find("\n", header_start)
        header_line_end = len(safe_stream) if header_line_end == -1 else header_line_end

        if use_indentation:
            header_line = safe_stream[line_start_idx:header_line_end]
            base_indent = len(header_line) - len(header_line.lstrip())

            scan_pos = header_line_end + 1 if header_line_end < len(safe_stream) else len(safe_stream)

            while scan_pos < len(safe_stream):
                next_nl = safe_stream.find("\n", scan_pos)
                line_end = len(safe_stream) if next_nl == -1 else next_nl + 1
                line = safe_stream[scan_pos:line_end]
                stripped = line.lstrip()
                if stripped:
                    indent = len(line) - len(stripped)
                    if indent <= base_indent:
                        return scan_pos
                scan_pos = line_end
            return len(safe_stream)

        search_limit = min(header_start + 2000, len(safe_stream))
        brace_idx = safe_stream.find("{", header_start, search_limit)
        if brace_idx == -1:
            return fallback_end_idx
        return self._find_balanced_end(safe_stream, brace_idx, "{", "}")

    def _correlate_signals(self, targets: list[int], dampeners: list[int], max_distance: int = 500) -> tuple[int, int]:
        """
        Sweeps two sorted lists of indices to find how many targets are within
        'max_distance' of a dampener. Runs in O(N) linear time.

        Extracted to gitgalaxy.core.spatial_correlation (#346) so the same
        primitive is reusable outside this class; kept here as a thin
        delegating wrapper for backward compatibility with existing callers.
        """
        return _correlate_signals_impl(targets, dampeners, max_distance)

    def coding_analysis(
        self, segments: list[tuple[str, str, int]], regex_telemetry: Optional[dict] = None
    ) -> tuple[dict[str, int], dict[str, int], list[dict[str, list[int]]], list[str], dict[str, list[int]]]:
        counts: dict[str, int] = dict.fromkeys(self.UNIVERSAL_METRICS_SCHEMA, 0)

        # --- THE FIX: INJECT APPSEC SENSORS ---
        # Force the new Phase 4 sensors into the schema so the LogicSplicer doesn't ignore them
        for appsec_key in ["memory_scraping", "exfiltration_camouflage", "rce_funnel"]:
            if appsec_key not in counts:
                counts[appsec_key] = 0

        mitigations: dict[str, int] = {
            "mitigated_danger": 0,
            "mitigated_memory_allocs": 0,
            "amplified_rce": 0,
            "amplified_race_conditions": 0,
            "amplified_leaks": 0,
        }
        segment_spatial_maps = []
        extracted_parents: list[str] = []
        threat_locations: dict[str, list[int]] = {}

        for seg_lang, seg_code, current_line_offset in segments:
            # 1. Grab the language-specific rules
            rules = self.languages.get(seg_lang, {}).get("rules", {}).copy()

            seg_len = len(seg_code)

            # ---> NEW: Spatial Map for this segment <---
            spatial_map: dict[str, list[int]] = {}

            for rule_name, pattern in rules.items():
                if rule_name.startswith("_"):
                    continue

                mapped_key = self.CORE_MAPPING.get(rule_name, rule_name)

                if mapped_key not in counts:
                    self.logger.warning(
                        f"[DIAGNOSTIC] Unregistered rule '{mapped_key}' found in '{seg_lang}'. Ignoring to preserve schema."
                    )
                    continue

                if not pattern:
                    continue

                raw_pat = getattr(pattern, "pattern", str(pattern))
                clean_pat = raw_pat.replace("(?i)", "").replace("(?m)", "").replace("(?s)", "").strip()
                if clean_pat in ("", "()", "(?:)", "^", "$"):
                    continue

                try:
                    t_rule_start = time.perf_counter()

                    # ---> THE UPGRADE: Spatial Mapping instead of raw counting <---
                    if hasattr(pattern, "finditer"):
                        matches = list(pattern.finditer(seg_code))
                        hit_indices = [m.start() for m in matches]

                        # ---> NEW: Offset to LOC Conversion <---
                        for m in matches:
                            line_number = current_line_offset + seg_code.count("\n", 0, m.start()) + 1
                            threat_locations.setdefault(mapped_key, []).append(line_number)

                        # ---> THE LINEAGE EXTRACTOR <---
                        # If the regex has 2+ capture groups, group 2 contains the inheritance mapping
                        if rule_name == "class_start" and pattern.groups >= 2:
                            extracted_parents.extend(m.group(2).strip() for m in matches if m.group(2))
                    else:
                        matches = list(re.finditer(str(pattern), seg_code))
                        hit_indices = [m.start() for m in matches]

                        # ---> NEW: Offset to LOC Conversion <---
                        for m in matches:
                            line_number = current_line_offset + seg_code.count("\n", 0, m.start()) + 1
                            threat_locations.setdefault(mapped_key, []).append(line_number)

                    c = len(hit_indices)

                    t_elapsed = time.perf_counter() - t_rule_start

                    if regex_telemetry is not None:
                        key = f"{seg_lang}::{rule_name}"
                        regex_telemetry[key] = regex_telemetry.get(key, 0.0) + t_elapsed
                    if t_elapsed > 0.5:
                        self.logger.debug(f"[REGEX-TRACE] ^-- SLOW RULE: '{rule_name}' took {t_elapsed:.4f}s")

                    if c > seg_len and seg_len > 0:
                        c = 0
                        hit_indices = []

                    counts[mapped_key] += c
                    spatial_map.setdefault(mapped_key, []).extend(hit_indices)

                except Exception as e:
                    self.logger.error(
                        f"[DIAGNOSTIC] Regex failure in rule '{rule_name}' for language '{seg_lang}': {e}"
                    )

            # ---> NEW: SPATIAL CORRELATION (Runs once per segment) <---

            # ==============================================================================

            # galaxyscope:ignore sec_high_risk_execution
            # PHASE 4: AI APPSEC & ZERO-TRUST SENSORS (The Checkmarx/Bitwarden Defense)
            # ==============================================================================

            # galaxyscope:ignore sec_high_risk_execution
            # 0a. The Exfiltration Distance Check has been RELOCATED (#102) to
            # apply_amplifier_correlations() in gitgalaxy.core.spatial_correlation,
            # called from _function_slice() -- it was the one correlate() pair
            # #346/#348 missed when they enumerated and migrated the other six,
            # so it kept running flat/unscoped after everything else had moved
            # to same-function scoping.

            # 0b. The RCE Funnel Amplifier
            if "rce_funnel" in spatial_map:
                # RCE funnels inside JS/TS/Python are fatal structural anomalies. Multiply the mass.
                counts["rce_funnel"] += len(spatial_map["rce_funnel"]) * 50
            # ==============================================================================

            # galaxyscope:ignore sec_high_risk_execution

            # 1. Taint Tracking (RCE Weaponization), 2. The Silencer Region,
            # 3. The Race Condition Radar, 5. The Memory Leak / UAF Tracker, and
            # 6. The OOM Bomb have all been RELOCATED (#346 phase 1, #348 phase 2)
            # to apply_dampener_correlations()/apply_amplifier_correlations() in
            # gitgalaxy.core.spatial_correlation, called from _function_slice()
            # once real satellite/function boundaries exist -- coding_analysis()
            # runs before those boundaries are computed, so none of these six
            # pairs ever had real scope available to them here.
            #
            # 4. The Active Hemorrhage is NOT relocated to that same in-detector
            # correlation step: its target key ("sec_hardcoded_secrets") is the
            # Passive Security Lens Observer name, only ever populated by
            # security_lens.py in galaxyscope.py's Phase 5.5 -- strictly after
            # this function (and _function_slice()) have both already returned.
            # It is instead reimplemented as a genuine post-hoc correlation in
            # galaxyscope.py, against the persisted threat_locations ledger, via
            # spatial_correlation.correlate_against_ledger() (#348).

            # Capture indentation signatures
            counts["indent_tabs"] += len(re.findall(r"^\t+(?=\S)", seg_code, flags=re.MULTILINE))
            counts["indent_spaces"] += len(re.findall(r"^[ ]{2,}(?=\S)", seg_code, flags=re.MULTILINE))
            segment_spatial_maps.append(spatial_map)

        return counts, mitigations, segment_spatial_maps, extracted_parents, threat_locations

    def comment_analysis(self, comment_stream: str, lang_id: str, counts: dict[str, int]) -> dict[str, int]:
        """
        Analyzes the comment stream for developer intent, technical debt, and traceability.
        Kept strictly separated from active coding analysis to maintain Separation of Concerns.
        """
        if not comment_stream:
            return counts

        rules = self.languages.get(lang_id, {}).get("rules", {})

        # The specific rules designed to extract telemetry from human-readable text
        comment_rules = [
            "dead_code",
            "doc",
            "ownership",
            "planned_debt",
            "fragile_debt",
            "spec_exposure",
            # Literate-Programming Extension Pack (#691): these only exist on
            # markdown's rules dict today, so this is a no-op for every other
            # language -- same graceful-fallback shape as the six keys above.
            "lit_code_blocks",
            "lit_diagrams",
            "lit_headers",
            "lit_links",
        ]

        for rule_name in comment_rules:
            pattern = rules.get(rule_name)
            mapped_key = self.CORE_MAPPING.get(rule_name, rule_name)

            # Ensure the pattern exists and the key is safely in our 51-element schema
            if pattern and mapped_key in counts:
                try:
                    if hasattr(pattern, "findall"):
                        c = len(pattern.findall(comment_stream))
                    else:
                        c = len(re.findall(str(pattern), comment_stream))

                    counts[mapped_key] += c

                except Exception as e:
                    self.logger.error(f"[DIAGNOSTIC] Comment stream regex failure in '{rule_name}': {e}")

        return counts

    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution
    # PRE-PROCESSING HELPERS
    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution

    def _apply_literal_shield(self, text: str, lang_id: Optional[str] = None) -> str:
        """
        The Smarter Atomic Literal Shield: Handles C++ Raw Strings, Python Triple Quotes,
        and safely isolates Heredocs to prevent Quote Desynchronization.
        """
        if len(text) > 500000:
            self.logger.warning(f"[DIAGNOSTIC-SHIELD] Extremely long block ({len(text)} chars). Shielding may be slow.")

        t_start = time.time()

        # #1184: comments are folded into the SAME alternation as the quote
        # patterns below (see atomic_string_pattern's trailing "comment"
        # branch) instead of being stripped in a separate later pass -- a
        # separate pass let an English contraction apostrophe inside a "#"/
        # "--"/"//" comment (don't, it's, wasn't) get treated as a real
        # string-open quote by the single-quote alternative, pairing with
        # whatever "'" came next anywhere later in the code and blanking out
        # every real line in between (silently dropping whole functions from
        # extraction downstream in `_slice_by_keywords`). One combined pass
        # lets whichever construct -- string or comment -- starts first at a
        # given position atomically claim its whole span, so an apostrophe
        # already inside a claimed comment is never independently
        # reconsidered as a string delimiter. Mirrors
        # `_build_brace_safe_stream`'s existing single-pass design, and the
        # identical fix in `_build_indentation_safe_stream`.
        def preserve_newlines(m):
            # groupdict().get(...) rather than m.group("comment") -- this
            # closure is also reused below for the Ruby %-literal shield
            # pass, whose pattern has no "comment" group at all, and
            # m.group() on a group name absent from the ORIGINATING pattern
            # raises IndexError rather than returning None.
            if m.groupdict().get("comment") is not None:
                return ""
            return '""' + "\n" * m.group(0).count("\n")

        # 1. Advanced Atomic Quotes
        # Order is critical: Check multi-char string markers before single quotes.
        # Handles Python ("""), C++ (R"(...)"), and standard strings.
        #
        # #1266: the comment-marker alternation was hardcoded to `#|--|//`, so
        # this shield never recognized MATLAB's `%` line comments at all --
        # unlike a "no comment support" gap in most other languages, this one
        # is actively dangerous for MATLAB specifically because its char-array
        # strings use the SAME unbounded single-quote branch above, so a
        # comment's stray apostrophe (the exact #1184/#1302 bug shape) could
        # false-open a "string" spanning to the next unrelated `'` and corrupt
        # the open/close keyword counting this shield exists to protect.
        # Gated to matlab only via `lang_id` (not added to the shared default
        # set) so shell/ruby/lua/elixir/vb's existing marker set is untouched.
        comment_markers = r"#|--|//"
        if lang_id == "matlab":
            comment_markers = r"%|#|--|//"
        atomic_string_pattern = (
            r'""".*?"""|'  # Python Triple Double
            r"'''.*?'''|"  # Python Triple Single
            r'R"([a-zA-Z0-9_]*)\(.*?\)\1"|'  # C++ Raw String Literal (e.g. R"EOF(...)EOF")
            r'@"[^"]*(?:""[^"]*)*"|'  # THE FIX: Unrolled C# Verbatim Shield (O(N) safe)
            r'"(?:\\.|[^"\\\n\r])*"|'  # Standard Double
            r"'(?:\\.|[^'\\\n\r])*'|"  # Standard Single
            r"`(?:\\.|[^`\\])*`|"  # Standard Backtick
            # Comment marker must be at line-start or preceded by whitespace
            # (guards against e.g. shell's "$#" positional-arg-count being
            # mistaken for a comment). Same marker set previously stripped
            # by `_slice_by_keywords`'s own post-hoc pass.
            rf"(?:^|(?<=[ \t]))(?P<comment>{comment_markers})[^\n]*"
        )
        text = re.sub(atomic_string_pattern, preserve_newlines, text, flags=re.DOTALL | re.MULTILINE)
        t_quotes = time.time()

        t_heredoc = t_quotes
        t_pct = t_quotes

        # 2. Isolate Heredoc Logic to supported scripting languages
        if lang_id in ["ruby", "perl", "elixir", "shell", "bash"]:
            # State-Machine for Heredocs
            lines = text.split("\n")
            shielded_lines = []
            active_heredoc_delimiter = None

            # In detector.py -> _apply_literal_shield
            heredoc_opener_pattern = re.compile(r'<<[-~]?\s*[\'"]?\\?([a-zA-Z_][a-zA-Z0-9_]*)[\'"]?')

            for line in lines:
                if active_heredoc_delimiter:
                    if line.strip() == active_heredoc_delimiter:
                        shielded_lines.append(line)
                        active_heredoc_delimiter = None
                    else:
                        shielded_lines.append("")
                    continue

                match = heredoc_opener_pattern.search(line)
                if match:
                    delimiter = match.group(1)
                    is_standard_heredoc = (
                        "-" in match.group(0)
                        or "~" in match.group(0)
                        or "'" in match.group(0)
                        or '"' in match.group(0)
                        or delimiter.isupper()
                    )
                    if is_standard_heredoc:
                        active_heredoc_delimiter = delimiter

                shielded_lines.append(line)

            text = "\n".join(shielded_lines)
            t_heredoc = time.time()

            # 3. Shield Ruby % Literals (Strictly gated to Ruby)
            if lang_id == "ruby":
                text = re.sub(r"%[qQwWiIrxs]?\{.*?\}", preserve_newlines, text, flags=re.DOTALL)
                text = re.sub(r"%[qQwWiIrxs]?\[.*?\]", preserve_newlines, text, flags=re.DOTALL)
                text = re.sub(r"%[qQwWiIrxs]?\(.*?\)", preserve_newlines, text, flags=re.DOTALL)
                text = re.sub(r"%[qQwWiIrxs]?\|.*?\|", preserve_newlines, text, flags=re.DOTALL)
                t_pct = time.time()

        if (time.time() - t_start) > 0.5:
            self.logger.warning(
                f"[DIAGNOSTIC-SHIELD] Slow Shield Regex: {time.time() - t_start:.2f}s total "
                f"(Quotes: {t_quotes - t_start:.2f}s | Heredoc: {t_heredoc - t_quotes:.2f}s | "
                f"PCT: {t_pct - t_heredoc:.2f}s)"
            )

        return text

    def _extract_semantic_name(self, line: str, lang_id: str) -> str:
        """Safely extracts function/block names for Mode D logic."""
        lang_key = ScopeParsingRegistry._ALIASES.get(lang_id.lower(), lang_id.lower())
        if lang_key == "shell":
            m = re.search(r"\bfunction\s+([a-zA-Z0-9_.-]+)", line)
            if m:
                return m.group(1)
            m = re.search(r"([a-zA-Z0-9_.-]+)\s*\(\)", line)
            if m:
                return m.group(1)
        elif lang_key == "ruby":
            # #1262: strips an optional "self."/"Namespace."-style prefix
            # before capturing the name (mirrors func_start's own non-
            # capturing prefix group), so a singleton method (`def
            # self.foo`) reports the bare name "foo" -- matching both
            # tree-sitter's ground-truth naming convention and how a plain
            # instance method of the same name is reported. The capture
            # group also allows a trailing `=`/`?`/`!` so setter methods
            # (`def foo=(v)`) aren't silently collapsed onto their getter's
            # name (`foo`). `::`-segments stay part of the capture (not the
            # skippable prefix, which requires a trailing `.`) so namespaced
            # class/module names (`class ActiveStorage::Blob`) are unaffected.
            m = re.search(
                r"\b(?:def|class|module|defmacro|defmodule|defp)\s+"
                r"(?:(?:[^\W\d]\w*(?:::[^\W\d]\w*)*\.|self\.)[ \t\n]*)?"
                r"([^\W\d]\w*(?:::[^\W\d]\w*)*[?!=]?)",
                line,
            )
            if m:
                return m.group(1)
        elif lang_key == "elixir":
            m = re.search(
                r"\b(?:def|class|module|defmacro|defmodule|defp)\s+([a-zA-Z0-9_.:?!]+)",
                line,
            )
            if m:
                return m.group(1)
        elif lang_key == "lua":
            m = re.search(r"\bfunction\s+([a-zA-Z0-9_.:]+)", line)
            if m:
                return m.group(1)
        elif lang_key == "vb":
            m = re.search(
                r"\b(?:sub|function|class|property)\s+([a-zA-Z0-9_]+)",
                line,
                re.IGNORECASE,
            )
            if m:
                return m.group(1)
        elif lang_key == "matlab":
            # Mirrors func_start's own output-array step-over (`function [out1,
            # out2] = name(...)` / `function out = name(...)` / `function
            # name(...)`) -- the name is whatever identifier immediately
            # precedes the parameter list, after stepping over any output
            # assignment.
            m = re.search(
                r"\bfunction\s+(?:\[[^\]]*\]\s*=\s*|[a-zA-Z_]\w*\s*=\s*)?([a-zA-Z_]\w*)",
                line,
            )
            if m:
                return m.group(1)
        return "Anonymous_Block"

    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution
    # THE MASTER DISPATCHER
    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution

    def _function_slice(
        self,
        segments: list[tuple[str, str, int]],
        segment_spatial_maps: list[dict[str, list[int]]],
        counts: dict[str, int],
        mitigations: dict[str, int],
        regex_telemetry: Optional[dict] = None,
    ) -> tuple[list[FunctionNode], float]:
        """The Master Routing Dispatcher: Directs the structural signal into the correct integration mode."""
        all_satellites: list[FunctionNode] = []
        global_impact = 0.0

        for (lang_id, code, offset), spatial_map in zip(segments, segment_spatial_maps):
            lang_config = self.languages.get(lang_id, {})
            rules = lang_config.get("rules", {})
            family = lang_config.get("lexical_family", "c_style_comment")

            integration_mode = ScopeParsingRegistry.get_mode(lang_id)

            t_mode_start = time.perf_counter()
            # NOT dead despite CodeQL's py/multiple-definition flag: the "no
            # func_start rule for this language" fallthrough below leaves this
            # unassigned, and the `mode_name != "Unknown"` check further down
            # relies on that sentinel surviving. Removing this would crash
            # with UnboundLocalError on that path.
            mode_name = "Unknown"
            sats: list[FunctionNode] = []
            impact = 0.0

            if integration_mode == "mode_d":
                mode_name = "Mode_D_Keywords"
                sats, impact = self._slice_by_keywords(code, lang_id, rules, offset, spatial_map)
            elif integration_mode == "mode_e":
                mode_name = "Mode_E_Terminator"
                sats, impact = self._slice_by_terminator(code, lang_id, rules, offset, spatial_map)
            else:
                # Fallback to standard structural heuristics (Modes A, B, C)
                func_start = rules.get("func_start")
                if func_start:
                    # Routed via formal Lexical Family taxonomy
                    if lang_id in (
                        "assembly",
                        "agc_assembly",
                        "cobol",
                        "fortran",
                        # #1899: ABAP has no ScopeParsingRegistry entry and no
                        # braces at all (`METHOD name. ... ENDMETHOD.`, never
                        # `{`/`}`), so it was silently falling through to
                        # Mode_B_Braces below, which can only bound a body when
                        # a stray brace-like character happens to appear nearby
                        # by coincidence -- dropping ~87% of real methods.
                        # Mode A's "greedy to the next func_start match" body
                        # heuristic (already used for COBOL's own label-only
                        # paragraphs, no closing keyword at all) is a correct
                        # fit here too: ABAP methods are never nested inside
                        # each other, so each one's real body always ends
                        # before the next METHOD/FORM/FUNCTION/MODULE starts.
                        "abap",
                        # dockerfile/tri-comparison-ledger-sweep manual-verification
                        # pass: Dockerfile has no ScopeParsingRegistry entry and no
                        # brace-delimited bodies at all (`RUN`/`CMD`/`ENTRYPOINT`/
                        # `HEALTHCHECK` instructions end at the next instruction,
                        # never at a `{`/`}` pair), so it was silently falling
                        # through to Mode_B_Braces below -- which only "succeeds"
                        # when a `{` happens to appear by coincidence within the
                        # bounded search window (most often a LATER, unrelated
                        # instruction's `${VAR}` template-substitution syntax, or
                        # occasionally a `RUN`'s own shell `{ ...; }` brace-group
                        # command). Confirmed via docs/self_scan/moby's daemon.
                        # Dockerfile (58 raw RUN/ENTRYPOINT matches, only 15 ever
                        # reached the named function_data list, and even those had
                        # bogus body boundaries borrowed from an unrelated later
                        # FROM line's `${VAR}` brace -- e.g. the RUN at line 57 was
                        # "sliced" using the `{`/`}` from line 62's
                        # `${GOLANG_IMAGE}`, five lines and one FROM boundary
                        # later). Mode A's "greedy to the next func_start match"
                        # body heuristic is a correct, direct fit: each instruction
                        # (including a `RUN <<EOT ... EOT` heredoc body) really does
                        # span exactly from its own keyword to the next
                        # RUN/CMD/ENTRYPOINT/HEALTHCHECK match, or EOF.
                        "dockerfile",
                        # #1975: jcl has no ScopeParsingRegistry entry and no
                        # brace-delimited bodies at all (JCL is fixed-column
                        # mainframe syntax), so it was silently falling through to
                        # Mode_B_Braces below -- which only "succeeds" when a `{`
                        # happens to appear by coincidence. This dropped 100% of
                        # real matches (0 of 3 raw matches reached the named list).
                        # Mode A's "greedy to the next func_start match" body
                        # heuristic is a correct, direct fit.
                        "jcl",
                        # #1975: m4 has no ScopeParsingRegistry entry and no
                        # brace-delimited bodies at all (macro definitions are
                        # parenthesis-delimited with backtick/bracket quoting), so
                        # it was silently falling through to Mode_B_Braces below --
                        # which only "succeeds" when a `{` happens to appear by
                        # coincidence. This dropped ~97.4% of real matches (1 of 39
                        # raw matches reached the named list). Mode A's "greedy to
                        # the next func_start match" body heuristic is a correct fit.
                        "m4",
                    ) or family in ("column_sensitive"):
                        mode_name = "Mode_A_Labels"
                        sats, impact = self._slice_by_labels(code, rules, offset, spatial_map)
                    elif family in ("single_line_only", "multi_style_dash") or lang_id in (
                        "python",
                        "yaml",
                        # #1266: Haskell's layout rule is indentation-based (the
                        # "off-side rule"), not brace-based -- it was falling
                        # through to Mode B, which can never find a `{` for a
                        # real function body, silently dropping almost every
                        # real function. `func_start` itself only ever matches a
                        # top-level (column-0) type-signature line
                        # (`foo :: Int -> Int`); Mode C's dedent-boundary scan
                        # then correctly extends that match's body through the
                        # actual equation(s) below it (`foo x = x + 1`) until
                        # the next column-0 definition, which is exactly the
                        # right heuristic for Haskell's layout rule even though
                        # it wasn't designed with Haskell in mind.
                        "haskell",
                    ):
                        mode_name = "Mode_C_Indentation"
                        sats, impact = self._slice_by_indentation(code, rules, offset, spatial_map, lang_id)
                    else:
                        mode_name = "Mode_B_Braces"
                        sats, impact = self._slice_by_braces(code, lang_id, rules, offset, spatial_map)
                # else: no func_start rule for this language at all -- sats stays [],
                # and the dampener correlation below falls back to flat behavior for
                # this segment (see apply_dampener_correlations()).

            # Record the telemetry if profiling is active
            if regex_telemetry is not None and mode_name != "Unknown":
                key = f"{lang_id}::Cartography_{mode_name}"
                regex_telemetry[key] = regex_telemetry.get(key, 0.0) + (time.perf_counter() - t_mode_start)

            # --- SATELLITE-SCOPED CORRELATION (#346 phase 1, #348 phase 2) ---
            # Runs for every segment unconditionally, using THIS segment's own
            # satellite ranges.
            sat_ranges = sorted(
                (sat["start_idx"], sat["end_idx"]) for sat in sats if "start_idx" in sat and "end_idx" in sat
            )
            apply_dampener_correlations(spatial_map, sat_ranges, counts, mitigations)
            apply_amplifier_correlations(spatial_map, sat_ranges, counts, mitigations)

            all_satellites.extend(sats)
            global_impact += impact

        all_satellites.sort(key=lambda x: x.get("mag", 0), reverse=True)
        return all_satellites, global_impact

    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution
    # INTEGRATION MODES (Slicers)
    # ==============================================================================

    def _index_abap_definition_signatures(self, code: str) -> dict[str, str]:
        """Maps each `METHODS`/`CLASS-METHODS` DEFINITION-section declaration's lowercased
        name to its own signature text (from right after the name to its terminating `.`,
        bounded to 2000 chars to stay ReDoS-safe against adversarial input) -- built once per
        file (#1918), not re-scanned per function, since a file can declare many methods.
        Chained `METHODS: foo ..., bar ... .` declarations aren't indexed (the regex requires
        whitespace, not a colon, right after the keyword) -- a real but narrow gap, not
        pretending to handle every ABAP declaration idiom in one pass. Interface-implemented
        methods (`METHOD zif_x~foo.` in the IMPLEMENTATION section) also never appear here by
        construction -- their real parameter list lives in the interface's own definition,
        typically a different file entirely, out of scope for a single-file index."""
        index: dict[str, str] = {}
        for m in _ABAP_METHOD_DECL_RE.finditer(code):
            name = m.group(1)
            sig_start = m.end()
            search_limit = min(sig_start + 2000, len(code))
            term = code.find(".", sig_start, search_limit)
            sig_end = term if term != -1 else search_limit
            index[name.lower()] = code[sig_start:sig_end]
        return index

    def _count_abap_declared_params(self, sig_text: str) -> int:
        """Counts real declared parameter names across every parameter-binding clause
        (IMPORTING/EXPORTING/CHANGING/RETURNING/RECEIVING/EXCEPTIONS) within one method's
        DEFINITION-section signature text (#1918). Splits the signature into clause spans
        first (from each keyword to the next keyword or end of signature), then counts
        parameter-shaped lines within each span -- RETURNING's own `VALUE(name)` shape
        needs its own pattern since it's never a bare name line the way the other five
        clauses' parameters are."""
        clause_matches = list(_ABAP_PARAM_CLAUSE_RE.finditer(sig_text))
        total = 0
        for i, clause_match in enumerate(clause_matches):
            keyword = clause_match.group(1).upper()
            span_start = clause_match.end()
            span_end = clause_matches[i + 1].start() if i + 1 < len(clause_matches) else len(sig_text)
            span_text = sig_text[span_start:span_end]
            if keyword == "RETURNING":
                total += len(_ABAP_RETURNING_VALUE_RE.findall(span_text))
            else:
                total += len(_ABAP_PARAM_LINE_RE.findall(span_text))
        return total

    def _count_agc_register_args(self, matches: list[str]) -> int:
        """AGC subroutines have no formal parameter list -- inputs arrive via a small, fixed
        set of accumulator-style registers (A, Q, L, Z) referenced anywhere in the body via a
        real math/memory opcode, the same "no formal signature, read the body idiom" shape as
        bash's $1/$2/... (why_gitgalaxy_beats_ast_here.md Claim 1). Counts the number of
        DISTINCT registers among A/Q/L/Z the body demonstrably reads, plus one more if an
        EBANK=/FBANK=/BBANK= bank-context assignment is present (a real, separate kind of input
        the subroutine depends on, not a register touch). Takes every match found in the body
        (the caller uses `.findall`, not `.search`) so a function that touches 3 different
        registers scores 3, not the single-match-derived 0/1/2 the generic whole-block
        `.search()`-then-split derivation this overrides produced before #1949's follow-up."""
        registers: set[str] = set()
        saw_bank = False
        for text in matches:
            if text.endswith("="):
                saw_bank = True
                continue
            parts = text.split()
            if parts:
                registers.add(parts[-1].upper())
        return len(registers) + (1 if saw_bank else 0)

    def _count_assembly_register_args(self, matches: list[str]) -> int:
        """Generic assembly (x86/ARM, unlike agc_assembly's own fixed A/Q/L/Z set) has no
        formal parameter list either -- args's regex matches calling-convention registers
        (SysV x86-64 rdi/rsi/rdx/rcx/r8/r9/xmm0-7, ARM AAPCS x0-7/w0-7/v0-7, legacy 16-bit
        ax/bx/cx/dx/si/di), the same body-idiom shape as `_count_agc_register_args`. Counts
        the number of DISTINCT argument-passing registers the body demonstrably touches
        (`.findall`, not the generic single-`.search()`-then-split derivation this overrides,
        which capped every function at a bare 0/1 regardless of how many registers it actually
        used -- the regex has exactly one capturing group, so a single match's text never has
        a comma or internal whitespace to split on). Different-width references to the SAME
        physical register (edi/rdi, w3/x3, al/ah/ax) canonicalize to one slot via
        `_ASSEMBLY_ARG_REG_CANON_RE` rather than counting as separate arguments."""
        registers: set[str] = set()
        for text in matches:
            m = _ASSEMBLY_ARG_REG_CANON_RE.match(text)
            if m is None:
                registers.add(text.lower())
            elif m.group(1):
                registers.add(m.group(1).lower())
            elif m.group(2):
                registers.add(m.group(2).lower())
            elif m.group(3):
                registers.add("x" + m.group(3))
            elif m.group(4):
                registers.add(m.group(4).lower() + "x")
        return len(registers)

    # galaxyscope:ignore sec_high_risk_execution

    # #1973: per-language line-continuation marker used to extend a Mode A
    # label's args-search window past its own first physical line, keyed by
    # primary_lang_id. Deliberately NOT a generic "any trailing symbol"
    # rule -- cobol's fixed-format continuation is a column-7 indicator on
    # the CONTINUING line, not a trailing marker on the line before, so
    # cobol legitimately gets no entry here and stays single-line-only.
    _MODE_A_ARGS_CONTINUATION_MARKER: ClassVar[dict[str, str]] = {
        "dockerfile": "\\",
        "fortran": "&",
    }

    def _mode_a_args_window_end(self, code: str, start_idx: int, hard_limit_idx: int) -> int:
        """Bounds a Mode A label's args-search window to its own statement span
        instead of a blind character count, which a verbose real-world
        Dockerfile RUN's `--mount=` continuation lines can easily exceed
        (#1973). Walks forward line by line from `start_idx`, extending the
        window while the current line ends in this language's own
        continuation marker (see _MODE_A_ARGS_CONTINUATION_MARKER) or sits
        inside a still-open Dockerfile heredoc body (`<<EOF ... EOF`) --
        stopping at the first line that's neither, which is the real end of
        the label's own signature/statement. A language with no
        continuation marker (cobol) never extends past its own first line.
        For fortran specifically, a blank line, a full `!...` comment line,
        or a C-preprocessor line (`#ifdef`/`#endif`/etc. -- real-world `.F`
        files like WRF's are cpp-preprocessed) carries no continuation
        marker of its own but doesn't end an in-progress continuation
        either; these are treated as transparent and skipped rather than
        mistaken for the label's real terminator line.
        Capped at 300 physical lines -- confirmed necessary, not just
        theoretical caution: real-world WRF Fortran subroutines
        (module_sf_noahdrv.F's `lsm`) legitimately span 90+ continuation
        lines for a single formal-parameter list (200+ real dummy
        arguments) interleaved with exactly these transparent-line shapes,
        and an earlier, tighter 40-line cap (before the transparent-line
        handling existed) silently truncated that signature before its
        closing `)`, dropping a real args count from 247 to 0 -- a
        regression caught by this fix's own before/after corpus
        verification, not a hypothetical. This is a cheap line scan (no
        regex backtracking), so a generous cap costs nothing at the common
        (short) case and only matters for genuinely pathological input.
        """
        marker = self._MODE_A_ARGS_CONTINUATION_MARKER.get(self.primary_lang_id)
        is_fortran = self.primary_lang_id == "fortran"
        pos = start_idx
        heredoc_terminator: Optional[str] = None
        for _ in range(300):
            line_end = code.find("\n", pos)
            if line_end == -1 or line_end >= hard_limit_idx:
                return hard_limit_idx
            line = code[pos:line_end].rstrip()
            if heredoc_terminator is not None:
                if line.strip() == heredoc_terminator:
                    heredoc_terminator = None
                pos = line_end + 1
                continue
            if self.primary_lang_id == "dockerfile":
                heredoc_match = _DOCKERFILE_HEREDOC_OPENER_RE.search(line)
                if heredoc_match:
                    heredoc_terminator = heredoc_match.group(1)
                    pos = line_end + 1
                    continue
            if is_fortran:
                stripped_lead = line.lstrip()
                # Transparent lines: blank, a full-line `!` comment, or a
                # cpp directive -- none of these end (or need to extend)
                # a continuation; skip straight past them.
                if not stripped_lead or stripped_lead.startswith("!") or stripped_lead.startswith("#"):
                    pos = line_end + 1
                    continue
                # Fortran routinely tags a continued parameter with an
                # inline `!` comment AFTER the `&` (e.g. WRF's own
                # `CHS,CHS2,...,qz0,   & !H` grouping-by-category style) --
                # strip a trailing `!...` comment before checking for the
                # marker; real Fortran dummy-argument names can't
                # themselves contain `!`, so this can't misidentify a real
                # terminator line as a continuation.
                code_part = line.split("!", 1)[0].rstrip()
                if code_part.endswith(marker):  # type: ignore[arg-type]
                    pos = line_end + 1
                    continue
            elif marker is not None and line.endswith(marker):
                pos = line_end + 1
                continue
            return min(line_end + 1, hard_limit_idx)
        return min(pos, hard_limit_idx)

    def _slice_by_labels(
        self,
        code: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE A] - Greedy Label-Based Scan (Assembly, COBOL, ABAP)."""
        satellites: list[FunctionNode] = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        try:
            # If func_start is None (key missing from rules), .finditer()
            # raises AttributeError, which the except below already handles --
            # mypy just can't see that the try/except is the actual guard here.
            matches = list(func_start.finditer(code))  # type: ignore[union-attr]
        except Exception:
            return [], 0.0

        # #1918: built once per file, not per function -- ABAP's real parameter
        # declarations live in the DEFINITION section, never in the IMPLEMENTATION body
        # this mode slices per function, so a per-function args count needs its own
        # name-indexed lookup into the DEFINITION section instead of searching `block`.
        abap_definition_index = self._index_abap_definition_signatures(code) if self.primary_lang_id == "abap" else None

        # --- FAST O(N) LINE TRACKER ---
        current_line_count = offset + 1
        last_counted_idx = 0

        for i, match in enumerate(matches):
            start_idx = match.start()
            greedy_end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(code)

            sandbox = code[start_idx:greedy_end_idx]
            end_offset = len(sandbox)

            if self.assembly_returns:
                excluded_keywords = _NON_TERMINATING_KEYWORDS_BY_LANG.get(self.primary_lang_id, frozenset())
                ret_matches = [
                    m
                    for m in self.assembly_returns.finditer(sandbox)
                    # #1949: only a standalone statement -- start of line, modulo
                    # leading whitespace -- counts as a real terminator. This
                    # rejects matches embedded inside a doc-comment
                    # (`// @return dl = pc_drive...` truncating label `pc:` in
                    # `language-crucible/data/assembly/cosmopolitan/ape.S:251`)
                    # and matches that are only a substring of a larger
                    # hyphenated identifier (`\bEXIT\b` firing inside
                    # `WS-EXIT-RETRY-LOOP`, since hyphens are non-word
                    # characters that satisfy `\b` without being a real token
                    # boundary -- `language-crucible/data/cobol/cics-banking-sample-application-cbsa/XFRFUN.cbl:105`).
                    if not sandbox[sandbox.rfind("\n", 0, m.start()) + 1 : m.start()].strip()
                    and m.group(0).upper().split()[0] not in excluded_keywords
                ]
                if ret_matches:
                    end_offset = ret_matches[-1].end()

            # #1949: Mode A's "greedy to the next label" body is already a
            # correct, real function boundary for this integration mode --
            # single-instruction "trampoline" labels are completely normal in
            # assembly-family code (seven consecutive one-instruction labels
            # `SOPTION1`-`SOPTON10` in
            # `language-crucible/data/agc_assembly/apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc:210-219`,
            # a zero-instruction label immediately followed by the next in
            # `language-crucible/data/assembly/bootos/os.asm:269-270`), so
            # unlike other integration modes a one-line body here is not a
            # mis-slice to discard -- only an actually-empty label has no
            # real content.
            block = code[start_idx : start_idx + end_offset].strip()
            if not block:
                continue

            if self.primary_lang_id == "assembly" and _ASSEMBLY_DATA_DIRECTIVE_RE.match(block):
                continue

            raw_name = match.group(match.lastindex) if match.lastindex else match.group(0)
            if raw_name is None:
                raw_name = match.group(0)

            if any(m in raw_name for m in ["BOOST_", "TEST", "TEST_F", "TEST_CASE"]):
                raw_name = match.group(0)

            name = self._extract_name(raw_name)

            # --- FAST O(N) LINE TRACKER ---
            current_line_count += code.count("\n", last_counted_idx, start_idx)
            last_counted_idx = start_idx
            start_line = current_line_count

            loc = block.count("\n") + 1
            end_line = start_line + loc - 1

            args_count_override = None
            if abap_definition_index is not None:
                def_sig = abap_definition_index.get(name.lower())
                if def_sig is not None:
                    args_count_override = self._count_abap_declared_params(def_sig)
                # else: no DEFINITION-section declaration found under this name (e.g. an
                # interface-implemented method, whose real signature lives in the
                # interface's own definition, typically a different file) -- leave None
                # rather than guess, same as every other language's default behavior.
            elif self.primary_lang_id == "agc_assembly":
                agc_args_pattern = rules.get("args")
                if agc_args_pattern is not None:
                    agc_matches = agc_args_pattern.findall(block)
                    if agc_matches:
                        args_count_override = self._count_agc_register_args(agc_matches)
            elif self.primary_lang_id == "assembly":
                asm_args_pattern = rules.get("args")
                if asm_args_pattern is not None:
                    asm_matches = asm_args_pattern.findall(block)
                    if asm_matches:
                        args_count_override = self._count_assembly_register_args(asm_matches)

            # #1973: for the 3 Mode A languages that never get a dedicated
            # args_count_override at all (cobol, fortran, dockerfile), the
            # generic args-count derivation in _calculate_block_metrics
            # defaults to searching the WHOLE greedy `block` -- which can span
            # many unrelated statements past the matched label's own
            # signature (Mode A's body legitimately runs to the next
            # func_start match, not to a brace-bounded end). For a language
            # whose args pattern only ever appears ON the matched
            # declaration itself (fortran's `SUBROUTINE/FUNCTION name(...)`),
            # an unbounded whole-block search happens to land on the right
            # match only because it's textually first -- fragile, not a
            # guarantee. For a language whose args construct is a genuinely
            # separate, unrelated statement (dockerfile's `ARG`, cobol's
            # program-level `PROCEDURE DIVISION USING/RETURNING`), an
            # unbounded search can walk past the (correctly absent) match on
            # the label's own line and pick up an unrelated later
            # occurrence instead, misattributing it as this label's own
            # parameter count. Bound the search to just the label's own
            # statement span (via _mode_a_args_window_end -- follows real
            # line-continuation syntax rather than a blind character count,
            # since a Dockerfile RUN's own `--mount=` continuation lines
            # routinely run past any fixed char budget) instead of leaving
            # Mode A as the one integration mode with no bound at all.
            #
            # Deliberately gated to primary_lang_id, NOT "args_count_override
            # is None" -- abap/agc_assembly/assembly can ALSO legitimately
            # leave args_count_override as None on a specific match (e.g. an
            # ABAP interface-implemented method with no DEFINITION-section
            # entry, see abap_definition_index's own comment above) without
            # that meaning "fall through to this bound." Confirmed via this
            # fix's own crucible_check verification: gating on the override
            # alone silently applied an untuned single-line window (no
            # continuation marker configured for abap) to real ABAP methods,
            # dropping their correct args count (e.g.
            # zcl_abapgit_http_client.clas.abap's `check_http_200`,
            # `send_receive`: real args 1, regressed to 0). Those 3
            # languages' own body-idiom scans are intentionally left on the
            # original unbounded path -- this issue never covered them.
            args_search_text = None
            if self.primary_lang_id in ("cobol", "fortran", "dockerfile"):
                args_window_end = self._mode_a_args_window_end(code, start_idx, start_idx + end_offset)
                args_search_text = code[start_idx:args_window_end]

            sat, mag = self._calculate_block_metrics(
                name,
                block,
                loc,
                start_line,
                end_line,
                rules,
                start_idx,
                start_idx + end_offset,
                spatial_map,
                args_search_text=args_search_text,
                args_count_override=args_count_override,
            )

            satellites.append(sat)
            sum_fxn_impact += mag

        return satellites, sum_fxn_impact

    def _build_brace_safe_stream(self, code: str, lang_id: str) -> str:
        """
        Shields string/char literals and (for C-family languages) dead
        #if/#else macro branches so a brace-balance scan isn't fooled by a
        literal `{`/`}` inside them. Shared by `_slice_by_braces` and the
        nesting-aware class-boundary scanner (#1040), both of which need a
        text stream whose only real braces are structural code -- same
        length as `code` (shielding preserves newlines) so every index
        computed against it stays valid against the original.
        """

        def fast_shield(m):
            text = m.group(0)
            if lang_id == "zig" and text.startswith('@"'):
                return text
            if "\n" not in text:
                return " " * len(text)
            return "\n".join(" " * len(line) for line in text.split("\n"))

        # Rust uses single quotes for lifetimes (e.g. 'a), so a greedy string match corrupts ASTs.
        single_quote = r"'(?:\\.|[^'\\])*'"
        if lang_id == "cpp":
            # #1718: C++14+ digit separators (512'000, 1'000'000, 0xDE'AD) use ' inside
            # numeric literals. The unbounded branch read a separator as a char-literal opener
            # and paired it with the next unrelated ' anywhere later in the file, blanking every
            # real function body in between from the brace scan. Consume separators as their own
            # alternative (same shape as prism.py's CPP_LITERAL_MASK_PATTERN) and bound the branch
            # to 64 chars, matching #1302/#1426.
            single_quote = r"[0-9a-fA-F]'[0-9a-fA-F]|(?<!\\)'(?:\\.|[^'\\]){0,64}'"
        elif lang_id in ("rust", "zig"):
            # #1426: zig's char literals ('a', '\n', '\u{1F600}') are just as short-lived
            # as rust's, but zig ALSO has multi-line `\\`-prefixed string literals that are
            # never shielded at all here (a separate, pre-existing gap) -- so a real
            # contraction/possessive apostrophe inside one of those strings' prose content
            # (e.g. "Compare Zig's CPU feature detection", language-crucible's own
            # zig/main.zig:128) reaches this unbounded pattern as an unpaired `'`, which then
            # greedily searches forward for the NEXT unrelated `'` (found ~44 lines later, in
            # "won't", main.zig:172) and blanks everything in between -- including the `{` of
            # `pub fn log(...) {` at main.zig:142. That one swallowed `{` desyncs the brace-depth
            # counter for the rest of the scan: whichever function's body search was already in
            # flight when the desync hit (here, `wasi_cwd` at line 60) never finds its real
            # closing brace and instead swallows every subsequent line until some later,
            # unrelated `}` happens to rebalance the count -- confirmed on this exact corpus:
            # `wasi_cwd`'s reported body swallowed lines 60-7104 (nearly the whole 7529-line
            # file), stuck at 18 total functions found regardless of #1419's separate
            # extern-callconv/quoted-identifier fix. Same idiom as the rust bound above.
            single_quote = r"'(?![a-zA-Z_]\w*[=<>(),&|\]\s])(?:\\.|[^'\\\n\r]){0,10}'"

        # #1266 follow-up: Scala's backtick is only ever a short quoted-identifier escape
        # (e.g. `` `type` ``), never a long delimiter -- unlike JS/TS template literals, which
        # legitimately span hundreds of characters/multiple lines and must stay unbounded here.
        # An unbounded backtick branch let a single stray, unpaired backtick (a real upstream
        # comment typo, confirmed on a live corpus file) pair with a much-later, unrelated
        # backtick and mask out several real functions in between. Gated to scala only, same
        # shape as the rust single-quote bound above.
        backtick = r"`(?:\\.|[^`\\])*`"
        if lang_id == "scala":
            backtick = r"`(?:\\.|[^`\\]){0,200}`"

        csharp_verbatim = r'@"[^"]*(?:""[^"]*)*"|'
        if lang_id == "zig":
            csharp_verbatim = r'@"(?:\\.|[^"\\])*"|'

        if lang_id == "powershell":
            combined_pattern = (
                r'@".*?\n"@|'
                r"@'.*?\n'@|"
                r'"(?:`"|""|[^"])*"|'
                r"'(?:''|[^'])*'|"
                r"<#.*?#>|#[^\n]*"
            )
        elif lang_id == "perl":
            # #1437: perl was falling through to the C-family default below, which shields
            # `//`-as-line-comment and `/* */` -- neither exists in perl (`//` is the
            # defined-or operator, e.g. `$x // $y`) -- so real code containing `//` had
            # everything after it on the line wrongly blanked, and any coincidental `/*...*/`
            # -shaped span (easy to hit inside a `/regex/` literal) got misparsed as a block
            # comment. Perl's own comments are `#`-to-end-of-line, with no block-comment form.
            #
            # Both quote patterns are also bounded (same idiom as the rust single-quote /
            # scala backtick bounds above): perl's `/regex/`, `m//`, `s///` etc. literals
            # (not shielded at all here -- out of scope for #1437, which only needed the
            # brace-delimited quote-op forms below) can contain a bare `\"`/`\'` as an
            # escaped-literal-quote INSIDE the regex body, not a real string delimiter. An
            # unbounded quote pattern lets that stray quote pair with the next unrelated
            # real quote anywhere later in the file, silently swallowing everything (including
            # any `{`/`}` characters) in between -- confirmed on this exact corpus: CGI.pm's
            # `s/^\"//g;` / `s/\"$//g;` pair (two escaped quotes inside unrelated substitution
            # regexes, ~15 lines apart) paired with each other as a bogus "string", desyncing
            # `_slice_by_braces` for the rest of the file. Real perl double/single-quoted
            # strings are essentially always short; 200 chars comfortably covers legitimate
            # long ones while still bounding the worst-case cross-regex mispairing.
            #
            # #1606: perl POD documentation blocks (`=head1`/`=item ... =cut`) are never
            # stripped from this stream at all (a separate, pre-existing gap -- perl's
            # `line_exclusive` lexical_family has no POD-marker support), so English prose
            # containing contractions/possessives ("doesn't", "don't", "it's", "users'")
            # reaches this shield as plain text. Without a lookbehind, the single-quote
            # alternative treats a contraction's apostrophe as an OPENING string delimiter
            # and searches up to 200 chars forward for the next real `'` to close it --
            # typically the opening quote of an unrelated real string much later -- blanking
            # everything in between, including any real `sub name { ... }` declaration that
            # falls inside that span. Confirmed on this exact corpus:
            # spamassassin/Message.pm's POD prose "doesn't have a root node ..." swallowed
            # `sub parse_body {` a few lines below entirely, and spamassassin/SpamAssassin.pm's
            # "don't" did the same to `sub init_learner {`. A real perl string-opening quote
            # is essentially never immediately preceded by a letter/digit/underscore (it's
            # preceded by whitespace, an operator, or a bracket/paren) -- confirmed via this
            # same corpus that no apostrophe-delimited quote-like operator (`q'...'`,
            # `m'...'`, etc., which WOULD be preceded by a word character) is actually used
            # anywhere in it, so this lookbehind has no observed false-negative cost here.
            combined_pattern = r'"(?:\\.|[^"\\]){0,200}"|' r"(?<![A-Za-z0-9_])'(?:\\.|[^'\\]){0,200}'"
        else:
            combined_pattern = (
                r'""".*?"""|' + csharp_verbatim + r'R"([a-zA-Z0-9_]*)\(.*?\)\1"|'
                r'"(?:\\.|[^"\\])*"|' + single_quote + r"|" + backtick + r"|//[^\n]*|/\*.*?\*/"
            )

        safe_code = re.sub(combined_pattern, fast_shield, code, flags=re.DOTALL) if lang_id != "perl" else code

        # #1517: an escaped `\{`/`\}` inside a bare `/regex/` literal (never shielded at
        # all here -- a documented, separate gap, e.g. matching a literal brace in a real
        # file format: `$$valPt =~ /^[\n\r]*\{[\n\r]*\\rtf/`) reads as a real structural
        # brace to the naive depth counters below (both the quote-op shielding's own
        # `_find_balanced_end` calls just below and `_slice_by_braces`'s downstream
        # function-body search), throwing the depth count off by however many escaped
        # braces go unrecognized and silently extending a function's "body" hundreds of
        # lines past its real end. Confirmed on this exact corpus: exiftool/exiftool's
        # `SuggestedExtension`, a real 57-line function, measured as swallowing 1206 lines
        # because of exactly this one escaped `\{` in an RTF-detection regex. An escaped
        # brace is never a real structural code brace in perl regardless of context, so
        # this blanks every `\{`/`\}` globally before any brace-depth counting runs.
        if lang_id == "perl":
            safe_code = re.sub(r"\\[{}]", "  ", safe_code)

        # #1437: perl's brace-delimited quote-like operators (qr{...}, m{...}, s{...}{...},
        # tr{...}{...}, y{...}{...}, q{...}, qq{...}, qw{...}, qx{...}) are NOT ordinary
        # code blocks -- their contents are arbitrary regex/string text that can itself
        # contain unmatched `{`/`}` (quantifiers like `{2,4}`, literal braces in a character
        # class, etc.), which desyncs any brace-depth counter downstream. Shield each one's
        # full span (both brace groups, for the two-part s///tr///y/// forms) using the same
        # balanced-brace finder (`_find_balanced_end`) the rest of this class already trusts,
        # rather than a hand-rolled depth counter -- reuses proven logic instead of
        # duplicating it. Longest-operator-first alternation order so `qq`/`qw`/`qx`/`qr`
        # aren't shadowed by the single-character `q` alternative matching just its own
        # first letter.
        if lang_id == "perl":

            def blank(span: str) -> str:
                if "\n" not in span:
                    return " " * len(span)
                return "\n".join(" " * len(line) for line in span.split("\n"))

            perl_quote_op = re.compile(r"\b(?:qw|qq|qx|qr|tr|q|m|s|y)[ \t]*\{")
            pos = 0
            parts: list[str] = []
            while True:
                qm = perl_quote_op.search(safe_code, pos)
                if not qm:
                    parts.append(safe_code[pos:])
                    break
                parts.append(safe_code[pos : qm.start()])
                op = qm.group(0)[:-1].strip()
                brace_start = qm.end() - 1
                end_idx = self._find_balanced_end(safe_code, brace_start, "{", "}")
                parts.append(blank(safe_code[qm.start() : end_idx]))
                pos = end_idx
                if op in ("s", "tr", "y"):
                    ws_match = re.match(r"[ \t]*", safe_code[pos:])
                    ws_len = len(ws_match.group(0)) if ws_match else 0
                    second_start = pos + ws_len
                    if second_start < len(safe_code) and safe_code[second_start] == "{":
                        end_idx2 = self._find_balanced_end(safe_code, second_start, "{", "}")
                        parts.append(safe_code[pos:second_start])
                        parts.append(blank(safe_code[second_start:end_idx2]))
                        pos = end_idx2
            safe_code = "".join(parts)

            # #1517: mirrors the brace-delimited shielding just above, but for the
            # SAME operators using `/` as their delimiter (`m/regex/`, `s/pat/repl/`,
            # `tr/a-z/A-Z/`, `y///`, `qr/.../`, `q/.../`, etc.) -- arguably the more
            # common style in real perl for these, not an edge case. `/` is also the
            # division operator (and `//` is defined-or), so unlike the brace form this
            # needs a real end-finder rather than reusing `_find_balanced_end` (`/`
            # doesn't nest) -- `_find_slash_terminator` below scans for the next
            # unescaped `/` and bails at end-of-line rather than guessing across a real
            # statement boundary. Gated with a negative lookbehind excluding a sigil
            # immediately before the keyword (`(?<![$@%&])`) so a bare single-letter
            # variable div/concat expression (`$s / $b`, `@y . $x`) can't false-positive
            # as the operator -- real perl virtually never omits the sigil on a variable
            # reference, so this costs no real coverage. Confirmed root cause for #1517:
            # mojo/Template.pm's `_line` (`$name =~ y/"//d;` immediately followed by
            # `return qq{#line @{[shift]} "$name"};`) had the bare `"` in `y/"//d`
            # false-paired by the double-quote shield above (which has no way to know
            # it's really quote-op content, not a string) with `"$name"`'s own opening
            # quote a line later, blanking the literal `qq{` keyword before the
            # brace-delimited pass above ever got a chance to shield it -- swallowing the
            # rest of the file behind an unclosed `_find_balanced_end` search. Shielding
            # the slash-delimited op FIRST (before the general quote shield ever sees the
            # `"` inside it) closes this at the source rather than chasing each downstream
            # symptom.
            def _find_slash_terminator(text: str, content_start: int) -> int:
                pos = content_start
                while pos < len(text):
                    ch = text[pos]
                    if ch == "\\":
                        pos += 2
                        continue
                    if ch == "/" or ch == "\n":
                        return pos
                    pos += 1
                return len(text)

            perl_quote_op_slash = re.compile(r"(?<![$@%&])\b(?:qw|qq|qx|qr|tr|q|m|s|y)[ \t]*/")
            pos = 0
            parts = []
            while True:
                qm = perl_quote_op_slash.search(safe_code, pos)
                if not qm:
                    parts.append(safe_code[pos:])
                    break
                parts.append(safe_code[pos : qm.start()])
                op = qm.group(0)[:-1].strip()
                slash_start = qm.end() - 1
                term1 = _find_slash_terminator(safe_code, slash_start + 1)
                if term1 >= len(safe_code) or safe_code[term1] != "/":
                    # Unterminated within this line -- not a real quote-op (most
                    # likely a bare division/defined-or expression). Leave it
                    # unshielded and resume scanning right after this match so the
                    # loop always makes forward progress.
                    parts.append(safe_code[qm.start() : qm.end()])
                    pos = qm.end()
                    continue
                end_idx = term1 + 1
                if op in ("s", "tr", "y"):
                    term2 = _find_slash_terminator(safe_code, end_idx)
                    if term2 < len(safe_code) and safe_code[term2] == "/":
                        end_idx = term2 + 1
                parts.append(blank(safe_code[qm.start() : end_idx]))
                pos = end_idx
            safe_code = "".join(parts)
            safe_code = re.sub(combined_pattern, fast_shield, safe_code, flags=re.DOTALL)

        # Macro Shields (Strictly Gated to C-Family)
        if lang_id in ("c", "cpp", "objective-c", "cs", "swift"):
            lines = safe_code.splitlines(keepends=True)
            # Per-open-#if branch policy. Each stack entry is a (policy, side)
            # pair where policy is the #if condition's static truth value and
            # side is which branch of that #if we are currently in:
            #   policy True  (#if 1 / #if true)   -> first branch alive, #else dead
            #   policy False (#if 0 / #if false)  -> first branch dead, #else alive
            #   policy None  (unknown, e.g. #if FOO / #ifdef FOO)
            #                                -> scan BOTH branches. This is the
            #                                   #1720 fix: tree-sitter ground truth
            #                                   parses both, and implementations
            #                                   living in #else were being blanked.
            # any() over the stack: an inner #if inside an outer dead region stays
            # dead even if its own condition would flip it; #endif pops restore it.
            branch_stack: list[tuple[Optional[bool], str]] = []
            in_multiline_macro = False

            def _branch_dead(entry: tuple[Optional[bool], str]) -> bool:
                policy, side = entry
                if policy is True:
                    return side == "else"
                if policy is False:
                    return side == "first"
                return False

            for i in range(len(lines)):
                line = lines[i]
                stripped = line.lstrip()

                if in_multiline_macro:
                    lines[i] = " " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line)
                    if not stripped.rstrip(" \t\r\n").endswith("\\"):
                        in_multiline_macro = False
                    continue

                if stripped.startswith("#"):
                    if re.match(r"#if\b", stripped):
                        branch_stack.append((self._classify_preproc_condition(stripped[3:].strip()), "first"))
                    elif stripped.startswith("#ifdef ") or stripped.startswith("#ifndef "):
                        branch_stack.append((None, "first"))
                    elif re.match(r"#elif\b", stripped) and branch_stack:
                        # an #elif starts a fresh condition on the else side
                        branch_stack[-1] = (self._classify_preproc_condition(stripped[5:].strip()), "first")
                    elif stripped.startswith("#else") and branch_stack:
                        policy, _ = branch_stack[-1]
                        branch_stack[-1] = (policy, "else")
                    elif stripped.startswith("#endif") and branch_stack:
                        branch_stack.pop()

                    if stripped.startswith("#define") and stripped.rstrip(" \t\r\n").endswith("\\"):
                        in_multiline_macro = True

                    lines[i] = " " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line)
                    continue

                if any(_branch_dead(e) for e in branch_stack):
                    lines[i] = " " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line)

            safe_code = "".join(lines)

        return safe_code

    @staticmethod
    def _classify_preproc_condition(condition: str) -> Optional[bool]:
        """
        Returns the static truth value of a C-family preprocessor #if condition,
        or None when it cannot be evaluated without a macro table.

        Recognized constants (after stripping C comments and whitespace):
          True  -- "1", "true", "TRUE"
          False -- "0", "false", "FALSE"
          None  -- everything else (macro names, defined(X), expressions)

        Used by _build_brace_safe_stream's macro shield so #else branches that
        genuinely contain implementations are scanned instead of blindly blanked
        (#1720): only a statically-true #if (#if 1) makes its #else branch dead,
        and only a statically-false #if (#if 0) makes its first branch dead.
        """
        if condition is None:
            return None
        # strip C-style comments and surrounding whitespace
        cond = re.sub(r"/\*.*?\*/|//.*$", "", condition, flags=re.S).strip()
        if cond in ("1", "true", "TRUE", "True"):
            return True
        if cond in ("0", "false", "FALSE", "False"):
            return False
        return None

    def _slice_by_braces(
        self,
        code: str,
        lang_id: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE B] - Global Recursive Scope Analysis (C-Family & Lisp)."""
        satellites: list[FunctionNode] = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        if not func_start:
            return [], 0.0

        # Dynamically set scope bounds based on lexical family
        # We now consistently use curly braces for standard block-style languages.
        # BUG FIX (2026-08-20, tri-comparison ledger sweep): this used to check
        # `lang_id == "lisp"` -- but "lisp" has never been a real key in
        # LANGUAGE_DEFINITIONS, only "scheme" is (dead code, unreachable true-
        # branch). Every real scheme file fell through to the curly-brace default,
        # which never finds a "{" in parenthesis-delimited scheme source, so
        # `_find_balanced_end`'s downstream brace search always failed and every
        # func_start match was silently discarded -- a 100% recall drop for the
        # whole language, confirmed via scheme/function/existence/
        # agree[ctags]_vs[gitgalaxy] (92 occurrences). Keyed off `lexical_family`
        # instead of a hardcoded lang_id string so any future lisp-family language
        # sharing this integration mode is covered automatically.
        opener, closer = "{", "}"
        if self.languages.get(lang_id, {}).get("lexical_family") == "recursive_block_lisp":
            opener, closer = "(", ")"

        safe_code = self._build_brace_safe_stream(code, lang_id)

        # BUG FIX (epic #813, extraction hardening, #814/#815): func_start
        # used to be matched against the raw, unshielded `code` -- computed
        # above, BEFORE `safe_code` existed. That let a single-line string
        # literal or comment containing function-shaped text (e.g. `let
        # query = "function Foo() {";`) false-positive-match, since
        # javascript's/typescript's func_start regex is `\b`-anchored (not
        # `^`-anchored) and has no way to know it's inside a string/comment
        # on its own. `safe_code` already exists at this point specifically
        # to solve this for the downstream brace search -- matching against
        # it here instead of `code` closes the same gap for the match
        # itself. `safe_code` is guaranteed the same length as `code`
        # (shielding replaces matched spans with same-length whitespace), so
        # every index computed from `matches` below remains valid against
        # the original `code` for slicing.
        #
        # Gated to javascript/typescript only, NOT applied to every Mode B
        # language: verifying this fix against the real crucible corpus
        # surfaced a pre-existing, separate bug in `prism.py`'s comment/
        # string stripping for PHP (#859, FIXED -- the broken
        # PHP_MULTILINE_STRING extraction step was removed entirely) --
        # `combined_pattern`'s shielding already relies on `code_stream`
        # being clean, and for at least two real PHP corpus files it wasn't,
        # causing a multi-thousand-character false shield match. That was
        # harmless before this fix because the brace search's blast radius
        # is naturally bounded (a bounded window, one brace lookup) -- but
        # matching *all* of func_start's positions against a corrupted
        # `safe_code` (this fix's approach) turned that latent corruption
        # into wholesale loss of real functions for those files (confirmed:
        # one file dropped from 1 real function detected to 0, with a 17x
        # structural-magnitude blowup). #859 is now fixed, so broadening
        # this gate to other Mode B languages is unblocked -- but still do
        # it as its own audited PR (confirm no other language has a similar
        # latent prism.py gap first), not as a drive-by expansion here.
        try:
            matches = list(func_start.finditer(safe_code))
        except Exception:
            return [], 0.0

        # #1041: this used to skip any match whose start fell before the
        # previously accepted match's end ("if start_idx < last_end_idx:
        # continue"), on the theory that it must already be inside an
        # in-progress function. But a nested/inner function declaration
        # necessarily starts before its enclosing function's end -- so that
        # guard silently dropped every nested function instead of counting
        # it. It's unnecessary anyway: each match below resolves its own end
        # independently via `_find_balanced_end`'s brace-depth tracking from
        # its OWN opening brace, so a nested match already gets a correctly
        # bounded (and correctly nested) scope on its own, without needing
        # to inherit or compare against any prior match's boundary.
        current_line_count = offset + 1
        last_counted_idx = 0

        for match_idx, match in enumerate(matches):
            start_idx = match.start()

            # #1631: typescript's func_start colon-annotated-arrow branch
            # cannot distinguish a real arrow-function property from a
            # parameter's function-type annotation -- both are the same
            # `IDENT: (...) => ...` surface syntax, but only the property
            # has a runtime function. A nested parameter (`f: (a: A) => B`
            # inside an interface member's own signature, fp-ts pipeable.ts's
            # `f`/`g` phantoms) is always the first thing after an
            # already-open parameter list, so its line is directly preceded
            # by `(`. An object-literal arrow property is never preceded by
            # `(` -- its enclosing `{` is -- so dropping line-anchored
            # matches whose preceding non-whitespace char is `(` removes
            # the phantom parameter annotations without touching real
            # arrow-function properties. JavaScript shares the same regex
            # branch and the same ambiguity, so the gate covers both.
            if lang_id in ("typescript", "javascript"):
                p = start_idx - 2  # start_idx - 1 is the line's own \n
                while p >= 0 and safe_code[p] in " \t":
                    p -= 1
                if p >= 0 and safe_code[p] == "(":
                    continue

            # #1632: the object-literal-method branch matches `IDENT :` followed
            # by a function/arrow -- but a ternary's true branch (`cond ? name :
            # function() { ... }`, jquery/deferred.js:182-184) has the identical
            # `name :\nfunction() {` surface while `name` is a plain identifier
            # reference, not an object key. A real object/namespace key is never
            # preceded (skipping whitespace/newlines) by `?` -- that position is
            # exclusively the ternary true-branch -- so a bounded backward scan
            # for the preceding non-whitespace char rules the shape out the same
            # way #1221's Invocation Shield rules out bare call statements.
            # JavaScript and TypeScript share the branch, so the gate covers both.
            if lang_id in ("typescript", "javascript"):
                p = start_idx - 1
                back_steps = 0
                while p >= 0 and back_steps < 200 and safe_code[p] in " \t\n\r":
                    p -= 1
                    back_steps += 1
                if p >= 0 and safe_code[p] == "?":
                    continue

            next_match_start = matches[match_idx + 1].start() if match_idx + 1 < len(matches) else len(code)
            search_limit = min(next_match_start, start_idx + 2000)

            # #1335: set to the index right
            # after the signature's own terminator (`{`/`;`) -- bounds the
            # args-pattern search to the signature text, never the body. See
            # `_calculate_block_metrics`'s `args_search_text` docstring.
            args_sig_end: Optional[int] = None

            # #789: csharp's func_start regex (unlike every other C-family
            # language here) doesn't consume the parameter list or require
            # a terminator -- it stops matching right at the opening `(`,
            # deferring entirely to the generic brace search below. That
            # search alone has two gaps for csharp specifically: (1) a bare
            # top-level call statement with no enclosing brace at all (C#
            # 9+ top-level statements, e.g. `Environment.Exit(0);`) would
            # get whatever `{` the bounded window found downstream
            # (typically an unrelated later block) hallucinated as its
            # body, and (2) expression-bodied members
            # (`Square(int x) => x * x;`, idiomatic since C# 6) have no `{`
            # at all and were never counted as functions. Both are closed
            # here by finding the parameter list's own closing paren first,
            # then checking whether a `{`, an expression-bodied `=>`, or a
            # bare `;` comes first immediately after it -- a `;` before
            # either means this was never a real function signature.
            # Gated to csharp only; every other Mode-B language keeps the
            # exact original brace-only behavior.
            if lang_id == "csharp":
                params_end_idx = self._find_balanced_end(safe_code, match.end() - 1, "(", ")")
                depth_paren = 0
                depth_bracket = 0
                pos = params_end_idx
                term_idx, term_kind = -1, None
                while pos < search_limit:
                    ch = safe_code[pos]
                    if ch == "(":
                        depth_paren += 1
                    elif ch == ")":
                        depth_paren = max(0, depth_paren - 1)
                    elif ch == "[":
                        depth_bracket += 1
                    elif ch == "]":
                        depth_bracket = max(0, depth_bracket - 1)
                    elif depth_paren == 0 and depth_bracket == 0:
                        if ch == opener:
                            term_idx, term_kind = pos, "brace"
                            break
                        elif ch == ";":
                            term_idx, term_kind = pos, "semi"
                            break
                        elif ch == "=" and pos + 1 < search_limit and safe_code[pos + 1] == ">":
                            term_idx, term_kind = pos, "arrow"
                            break
                    pos += 1

                if term_kind == "semi":
                    continue  # a bare statement -- `;` arrived before any real terminator
                if not term_kind:
                    continue  # neither a brace nor an arrow ever showed up in the window

                if term_kind == "brace":
                    end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                else:
                    semi_after_arrow = safe_code.find(";", term_idx, search_limit)
                    if semi_after_arrow == -1:
                        continue
                    end_idx = semi_after_arrow + 1
            # #1266: Scala's idiomatic parenthesis-less/single-expression method
            # body (`def foo(x: Int): Int = x + 1`, no `{` at all -- extremely
            # common, not a rare style) was invisible here: the generic brace-only
            # path below drops any match whose window never finds a `{`, even
            # though `func_start` matched a completely real `def`. Mirrors #789's
            # csharp expression-bodied-member fix (same underlying shape, `=>`
            # there vs. bare `=` here), but Scala has no reliable terminator
            # (`;` is optional/rare) to bound the expression's end the way
            # csharp's trailing `;` does -- so a brace-less match's body is
            # bounded by the next `def`/`class`/etc. match instead. This
            # under-captures the odd case where a `{` inside the SAME
            # single-expression body belongs to a trailing block-argument lambda
            # (`xs.map { y => y + 1 }.sum`) rather than the def's own block --
            # that still gets recorded (just with a truncated body/line-range),
            # which is strictly better than the previous silent drop.
            elif lang_id == "scala":
                brace_idx = safe_code.find(opener, start_idx, search_limit)
                if brace_idx != -1:
                    end_idx = self._find_balanced_end(safe_code, brace_idx, opener, closer)
                else:
                    eq_match = re.search(r"(?<![=!<>])=(?!=|>)", safe_code[start_idx:search_limit])
                    if not eq_match:
                        continue
                    end_idx = next_match_start
            # #1319: rust's func_start regex (like csharp's above -- #789 --
            # also stops right at the parameter list's opening `(` via a
            # lookahead, without consuming it) never captured bodyless
            # trait-method signatures (`fn deserialize_any<V>(self, visitor:
            # V) -> Result<...>\nwhere\n    V: Visitor<'de>;` -- a trait
            # *requirement*, not a default impl, so it's legitimately
            # terminated by `;` instead of a `{...}` block). These are
            # common in trait definitions (serde's `Deserializer` trait
            # alone has dozens) and were silently dropped by the generic
            # brace-only path below, which treats "no `{` in the window" as
            # "not a real match". Mirrors csharp's arrow-vs-brace split, but
            # unlike csharp a bare `;` here is never a false match -- every
            # match `func_start` produces is a real `fn` declaration, never
            # a call or bare statement, since the regex requires the
            # literal `fn` keyword -- so both terminators are valid, not
            # just one.
            #
            # The naive "whichever of `{`/`;` comes first" scan (copied
            # verbatim from csharp) is wrong for rust specifically: array
            # types (`[u8; 32]`, `[T; N]`) put a `;` INSIDE `[...]`, often
            # in the very return type right before the real body's `{`
            # (`fn hash(&self) -> [u8; 32] { ... }`) -- a bracket-blind scan
            # would truncate a completely normal function at that `;`. Track
            # `[`/`]` depth and only treat `{`/`;` as the terminator at
            # depth 0.
            elif lang_id in ("rust", "zig", "solidity"):
                params_end_idx = self._find_balanced_end(safe_code, match.end(), "(", ")")
                depth = 0
                pos = params_end_idx
                term_idx, term_kind = -1, None
                while pos < search_limit:
                    ch = safe_code[pos]
                    if ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth = max(0, depth - 1)
                    elif depth == 0 and (ch == opener or ch == ";"):
                        term_idx, term_kind = pos, ("brace" if ch == opener else "semi")
                        break
                    pos += 1
                if term_kind == "brace":
                    end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                elif term_kind == "semi":
                    if lang_id == "solidity":
                        matched_text = match.group(0).strip()
                        if not matched_text.startswith("function"):
                            continue
                    end_idx = term_idx + 1
                else:
                    continue  # neither a body nor a bodyless `;` terminator ever showed up in the window
            # #1756: Go's bodyless function declarations (assembly-backed
            # implementations and //go:linkname targets -- e.g. "func
            # memmove(to, from unsafe.Pointer, n uintptr)" with no { body,
            # legal and common in the stdlib) were silently dropped by the
            # generic brace-only fallback below: Go's automatic-semicolon-
            # insertion rule means a bodyless declaration ends at the end of
            # its signature line without a literal ";", so the brace search
            # either found nothing in the bounded window (brace_idx == -1,
            # match discarded) or -- when a struct/interface literal
            # happened to appear later -- attributed an unrelated block as
            # the function's body. Mirrors #1319's rust bodyless
            # trait-method handling, with the declaration bound taken from
            # Go's own ASI rule: after the parameter list closes, the first
            # top-level { is the body; a literal ";" or (far more common)
            # the end of the line means the declaration is bodyless. "func"
            # at line start is unambiguous in Go (never a call or bare
            # statement), so a bodyless terminator is never a false match.
            #
            # One Go-specific wrinkle: a return type may itself contain a
            # brace group ("func f() struct{ X int } { ... }",
            # "interface{ ... }"), which sits at top level after the
            # parameter list and would be mistaken for the body. Such a
            # group is always closed on the same line, and a real body {
            # always follows on that same line -- so a top-level { whose
            # balanced close is followed by another { before the line ends
            # is a type literal, not the body; skip past it and keep
            # scanning.
            elif lang_id == "go":
                params_end_idx = self._find_balanced_end(safe_code, match.end() - 1, "(", ")")
                # Go has no angle-bracket grouping: generics use square brackets
                # ([T any]), so < and > only ever appear as operators -- most
                # notably the channel-direction operator (chan<- / <-chan),
                # whose lone < would poison an angle-depth counter and stall the
                # scan below. Track parens and brackets only.
                depth_paren = depth_bracket = 0
                pos = params_end_idx
                term_idx, term_kind = -1, None
                while pos < search_limit:
                    ch = safe_code[pos]
                    if ch == "(":
                        depth_paren += 1
                    elif ch == ")":
                        depth_paren = max(0, depth_paren - 1)
                    elif ch == "[":
                        depth_bracket += 1
                    elif ch == "]":
                        depth_bracket = max(0, depth_bracket - 1)
                    elif depth_paren == 0 and depth_bracket == 0:
                        if ch == opener:
                            # A brace group that is a type literal (struct{
                            # ... } / interface{ ... } in the return type)
                            # closes before the line ends and is followed by
                            # the real body's { on that same line -- or, for
                            # a bodyless declaration, by the end of the
                            # line. Only a { whose balanced close is NOT
                            # followed by another { before the next newline
                            # is the function's own body.
                            group_end = self._find_balanced_end(safe_code, pos, opener, closer)
                            line_end = safe_code.find("\n", group_end + 1, search_limit)
                            if line_end == -1:
                                line_end = search_limit
                            if safe_code.find(opener, group_end + 1, line_end) != -1:
                                pos = group_end + 1
                                continue
                            term_idx, term_kind = pos, "brace"
                            break
                        elif ch == ";":
                            term_idx, term_kind = pos, "semi"
                            break
                        elif ch == "\n":
                            term_idx, term_kind = pos, "eol"
                            break
                    pos += 1
                if term_kind == "brace":
                    end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                elif term_kind in ("semi", "eol"):
                    end_idx = term_idx + 1
                else:
                    continue  # neither a body nor a bodyless declaration bound showed up in the window
            elif lang_id == "kotlin":
                paren_idx = safe_code.find("(", match.end(), search_limit)
                brace_idx = safe_code.find(opener, match.end(), search_limit)
                if brace_idx != -1 and (paren_idx == -1 or brace_idx < paren_idx):
                    end_idx = self._find_balanced_end(safe_code, brace_idx, opener, closer)
                else:
                    if paren_idx == -1:
                        continue
                    params_end_idx = self._find_balanced_end(safe_code, paren_idx, "(", ")")
                    depth_angle = 0
                    depth_paren = 0
                    pos = params_end_idx
                    term_idx, term_kind = -1, None
                    while pos < search_limit:
                        ch = safe_code[pos]
                        if ch == "<":
                            depth_angle += 1
                        elif ch == ">":
                            depth_angle = max(0, depth_angle - 1)
                        elif ch == "(":
                            depth_paren += 1
                        elif ch == ")":
                            depth_paren = max(0, depth_paren - 1)
                        elif depth_angle == 0 and depth_paren == 0:
                            if ch == opener:
                                term_idx, term_kind = pos, "brace"
                                break
                            elif (
                                ch == "="
                                and pos + 1 < search_limit
                                and safe_code[pos + 1] != "="
                                and safe_code[pos - 1] not in "=!<>"
                            ):
                                term_idx, term_kind = pos, "eq"
                                break
                        pos += 1
                    if term_kind == "brace":
                        end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                    elif term_kind == "eq":
                        end_idx = next_match_start
                    else:
                        end_idx = (
                            params_end_idx  # neither a body nor a bodyless `;` terminator ever showed up in the window
                        )
            # #1314 (follow-up): objc's func_start has two alternatives sharing one pattern --
            # group 1 is the `-`/`+`-prefixed method-selector form, group 2 is a plain C-style
            # prototype form. Group 1 is unambiguous: nothing but a real method signature can
            # ever start with a bare `-`/`+`, so a bodyless `@interface` declaration (`-
            # setupWindow;`, `+ newAnchor:(Anchor*)anAnchor;`) is exactly as safe to accept via a
            # bare `;` terminator as rust's bodyless trait methods were in #1319 -- and this shape
            # is the ENTIRE public surface of every objc header, not an edge case (confirmed via
            # language-crucible/data/objective-c/worldwideweb/HyperText.h: 38 of 38 real interface
            # methods were silently dropped here pre-fix, 0 recall on that file).
            elif lang_id == "objective-c" and match.group(1) is not None:
                pos = match.end()
                depth = 0
                term_idx, term_kind = -1, None
                while pos < search_limit:
                    ch = safe_code[pos]
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth = max(0, depth - 1)
                    elif depth == 0 and ch in (opener, ";"):
                        term_idx, term_kind = pos, ("brace" if ch == opener else "semi")
                        break
                    pos += 1
                if term_kind == "brace":
                    end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                elif term_kind == "semi":
                    end_idx = term_idx + 1
                else:
                    continue  # neither a body nor a bodyless `;` terminator ever showed up in the window
                args_sig_end = term_idx + 1
            # #1336: group 2 (plain C-style prototypes, e.g. `extern void
            # write_rtf_header(NXStream* rtfStream);`) does NOT get group 1's bodyless-`;`
            # treatment -- unlike group 1's method form, a prototype has no function body to
            # score at all (no executable logic, nothing for `branch`/`io`/etc. to fire inside),
            # so it's out of scope for `func_start` entirely rather than a recall gap to close.
            # The generic brace-only fallback below (the final `else`) used to "accept" these
            # anyway whenever some unrelated `{` happened to appear later in its bounded search
            # window -- typically a nearby `@interface` block's own ivar-list braces -- and
            # silently attribute that block's whole span as the prototype's "body" (the actual
            # #1336 bug: a real prototype found *only* by accident, with a bogus body/LOC).
            # Fixed by explicitly detecting the bodyless-`;` case here and rejecting it outright,
            # rather than falling through to the blind forward `{` search. A real function
            # definition (`static inline void c_style_func(int a, float b) { ... }`) is
            # unaffected: its own `{` always arrives before any `;`, so it still reaches the
            # `brace` branch below unchanged. The regex itself (language_standards.py) now also
            # carries a "not a function" keyword shield mirroring `branch`'s own control-flow
            # keyword set, so a bare call/return statement (`return foo(x);`) -- which could
            # already match this alternative's lenient (type-token)+ loop -- can no longer reach
            # this branch at all; every match landing here is a real declaration or definition.
            elif lang_id == "objective-c" and match.group(2) is not None:
                pos = match.end()
                depth = 0
                term_idx, term_kind = -1, None
                while pos < search_limit:
                    ch = safe_code[pos]
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth = max(0, depth - 1)
                    elif depth == 0 and ch in (opener, ";"):
                        term_idx, term_kind = pos, ("brace" if ch == opener else "semi")
                        break
                    pos += 1
                if term_kind != "brace":
                    continue  # a bodyless prototype (or neither terminator in the window) -- out of func_start's scope
                end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                args_sig_end = term_idx + 1
            elif lang_id == "dart":
                pos = match.end()
                has_parens = False
                while pos < next_match_start and pos < len(safe_code):
                    ch = safe_code[pos]
                    if ch == "(":
                        has_parens = True
                        break
                    elif ch in "{;=":
                        break
                    pos += 1

                if has_parens:
                    params_end_idx = self._find_balanced_end(safe_code, match.end(), "(", ")")
                else:
                    params_end_idx = match.end()

                # #1624: Invocation Shield for closure arguments.
                # A regular parameter list tracks only parens `()` and ignores `{}`. However, a call whose
                # argument is a closure (e.g. `setState(() { ... });`) will have a `{` inside its parens.
                # Since the parameter list scan is brace-blind, it walks through the entire closure body
                # and stops at the final `)`, treating the trailing `;` as a bodyless function terminator.
                # We identify closure arguments by checking if any `{` at depth 1 (directly inside the
                # outer parens) is immediately preceded by a `)` (the closure's own parameter list closing).
                # A `{` preceded by `(` or `,` is a legitimate named-parameter block, not a closure.
                def _dart_is_closure_invocation(
                    scan_start: int,
                    scan_end: int,
                    *,
                    safe_code: str = safe_code,
                ) -> bool:
                    pos = scan_start
                    # Shield against getters without parens: if we hit a body/arrow before any paren,
                    # the first paren we eventually find isn't a parameter list.
                    while pos < scan_end:
                        ch = safe_code[pos]
                        if ch == "(":
                            break
                        if ch in "{;=":
                            return False
                        pos += 1

                    depth = 0
                    while pos < scan_end:
                        ch = safe_code[pos]
                        if ch == "(":
                            depth += 1
                        elif ch == ")":
                            depth = max(0, depth - 1)
                        elif ch == "{" and depth == 1:
                            back_pos = pos - 1
                            steps = 0
                            while back_pos >= scan_start and steps < 200:
                                b_ch = safe_code[back_pos]
                                if b_ch not in " \t\n\r":
                                    if b_ch == ")":
                                        return True
                                    break
                                back_pos -= 1
                                steps += 1
                        pos += 1
                    return False

                if _dart_is_closure_invocation(match.end(), params_end_idx):
                    continue
                # #1493: the generic `search_limit = start_idx + 2000` gives most real
                # functions (short/medium param lists) hundreds to ~2000 chars of
                # terminator-hunt room past `params_end_idx` -- flooring the terminator
                # scan's own budget at a small flat constant (tried +200 first) broke
                # real cases that relied on that existing slack and dropped
                # found_functions BELOW the pre-fix baseline. Only the pathological case
                # -- a param list itself long enough that `params_end_idx` overruns
                # `start_idx + 2000` -- needs extra room; `max(...)` keeps every other
                # match byte-for-byte at the original generic bound and only widens
                # for the specific case #1493 reported, instead of loosening the window
                # file-wide (which was independently found to add spurious "extra"
                # matches in unrelated files when tried as a flat `params_end_idx + 2000`).
                dart_search_limit = min(next_match_start, max(search_limit, params_end_idx + 200))

                def _dart_scan_terminator(
                    scan_start: int,
                    stop_chars: str,
                    *,
                    safe_code: str = safe_code,
                    search_limit: int = dart_search_limit,
                ) -> tuple[int, Optional[str]]:
                    """Paren/bracket/angle-depth-aware scan for the next top-level char
                    in `stop_chars` starting at `scan_start`. `stop_chars` differs by
                    caller: the params-end scan stops at a top-level `,` too (Bug 4:
                    a bare list-element call has one right after its own `)`), but the
                    initializer-list scan below must NOT -- a colon-initializer list
                    (`Ctor(...) : a = b, assert(c);`) legitimately has multiple
                    comma-separated initializers at depth 0, which aren't list-element
                    commas at all; stopping on the first one there would wrongly reject
                    every constructor with more than one initializer. `safe_code`/
                    `search_limit` are bound as defaults (not closed over) since both
                    are per-iteration loop variables -- ruff's B023 flags a nested
                    function reading a loop variable by closure as a late-binding
                    footgun even though this one is only ever called synchronously
                    within the same iteration; binding at def-time is the standard fix
                    and is clearer regardless of whether the footgun could fire here."""
                    depth_paren = depth_bracket = depth_angle = 0
                    pos = scan_start
                    while pos < search_limit:
                        ch = safe_code[pos]
                        if ch == "(":
                            depth_paren += 1
                        elif ch == ")":
                            depth_paren = max(0, depth_paren - 1)
                        elif ch == "[":
                            depth_bracket += 1
                        elif ch == "]":
                            depth_bracket = max(0, depth_bracket - 1)
                        elif ch == "<":
                            depth_angle += 1
                        elif ch == ">":
                            depth_angle = max(0, depth_angle - 1)
                        elif depth_paren == 0 and depth_bracket == 0 and depth_angle == 0:
                            if ch == "=":
                                if "=" in stop_chars and pos + 1 < search_limit and safe_code[pos + 1] == ">":
                                    return pos, "arrow"
                                # a lone "=" (not "=>") is never itself a terminator --
                                # skip it rather than falling into the dict lookup below,
                                # which has no entry for it.
                            elif ch in stop_chars:
                                return pos, {opener: "brace", ";": "semi", ":": "colon", ",": "comma"}[ch]
                        pos += 1
                    return -1, None

                term_idx, term_kind = _dart_scan_terminator(params_end_idx, opener + ";=:,")

                if term_kind == "comma":
                    continue  # Bug 4: list-element bare call
                if term_kind == "colon":
                    # Constructor initializer list (`Ctor(...) : a = b, assert(c);`).
                    # Commas here separate initializers, not list elements -- keep
                    # scanning past the whole list (excluding "," from stop_chars, so
                    # they're skipped rather than mistaken for Bug 4's terminator) for
                    # the real terminator: either a bodyless `;` or a body-bearing `{`.
                    colon_term_idx, colon_term_kind = _dart_scan_terminator(term_idx + 1, opener + ";")
                    if colon_term_kind == "brace":
                        end_idx = self._find_balanced_end(safe_code, colon_term_idx, opener, closer)
                    elif colon_term_kind == "semi":
                        end_idx = colon_term_idx + 1
                    else:
                        continue
                elif term_kind == "semi":
                    end_idx = term_idx + 1  # Bug 2: bodyless constructor
                elif term_kind == "brace":
                    end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                elif term_kind == "arrow":
                    semi_after_arrow = safe_code.find(";", term_idx, dart_search_limit)
                    if semi_after_arrow == -1:
                        continue
                    end_idx = semi_after_arrow + 1
                else:
                    continue
            # #1629: typescript/javascript idiomatically use brace-less,
            # expression-bodied arrow functions (`const swap = (x) => x + 1`,
            # curried FP chains with no `{` anywhere in the definition --
            # fp-ts's primary export shape). The generic brace-only fallback
            # below drops every one of them; at least 88 of the corpus's 159
            # func recall misses are this shape. Mirror #1266's scala
            # approach: when no `{` shows up in the window, find the first
            # un-nested `=>` after the signature and bound the expression
            # body by the next func_start match (TS/JS arrow bodies have no
            # reliable `;` terminator either, so the next-match bound is the
            # closer analogy than csharp's trailing-semicolon scan).
            elif lang_id in ("typescript", "javascript"):
                # A brace-less assignment match that is itself in expression
                # position (preceding non-whitespace char is `>`/`)`) is a
                # return type, not a name -- `=> M = (M) => ...` in fp-ts's
                # foldMap reports a phantom `M`. We removed `,` from this check
                # because object literal properties are preceded by `,`.
                if start_idx > 0:
                    p = start_idx - 1
                    while p >= 0 and safe_code[p] in " \t":
                        p -= 1
                    if p >= 0 and safe_code[p] in ">)":
                        continue
                depth_paren = depth_bracket = depth_angle = 0
                pos = match.end()
                saw_assignment = False
                saw_colon = False
                term_idx = -1
                term_kind = None
                while pos < search_limit:
                    ch = safe_code[pos]
                    if ch == "(":
                        depth_paren += 1
                    elif ch == ")":
                        depth_paren = max(0, depth_paren - 1)
                    elif ch == "[":
                        depth_bracket += 1
                    elif ch == "]":
                        depth_bracket = max(0, depth_bracket - 1)
                    elif ch == "<":
                        depth_angle += 1
                    elif ch == ">":
                        depth_angle = max(0, depth_angle - 1)
                    elif depth_paren == 0 and depth_bracket == 0 and depth_angle == 0:
                        if ch == opener:
                            term_idx = pos
                            term_kind = "brace"
                            break
                        if ch == "=" and pos + 1 < search_limit and safe_code[pos + 1] == ">":
                            if saw_assignment or saw_colon:
                                if saw_colon and not saw_assignment:
                                    p_idx = start_idx - 1
                                    d_paren = d_bracket = d_angle = d_brace = 0
                                    outer_container = None
                                    while p_idx >= 0:
                                        c_ch = safe_code[p_idx]
                                        if c_ch == "}":
                                            d_brace += 1
                                        elif c_ch == "{":
                                            if d_brace == 0:
                                                outer_container = "{"
                                                break
                                            d_brace -= 1
                                        elif c_ch == ")":
                                            d_paren += 1
                                        elif c_ch == "(":
                                            if d_paren == 0:
                                                outer_container = "("
                                                break
                                            d_paren -= 1
                                        elif c_ch == "]":
                                            d_bracket += 1
                                        elif c_ch == "[":
                                            if d_bracket == 0:
                                                outer_container = "["
                                                break
                                            d_bracket -= 1
                                        elif c_ch == ">":
                                            d_angle += 1
                                        elif c_ch == "<":
                                            if d_angle == 0:
                                                outer_container = "<"
                                                break
                                            d_angle -= 1
                                        p_idx -= 1
                                    if outer_container in ("(", "<", "["):
                                        break  # it's a type annotation inside a parameter list or generic
                                term_idx = pos
                                term_kind = "arrow"
                                break
                            break  # the `=>` belongs to an annotation, not an assignment
                        if ch == "=":
                            saw_assignment = True
                        elif ch == ":":
                            saw_colon = True
                        elif ch == ";":
                            term_idx = pos
                            term_kind = "semi"
                            break  # bodyless prototype
                    pos += 1

                if term_kind == "brace":
                    end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
                elif term_kind == "arrow":
                    end_idx = next_match_start
                elif term_kind == "semi":
                    end_idx = term_idx + 1
                else:
                    continue
            # #1609: perl's bodyless forward declarations (e.g. `sub GetASCII($);`)
            # are not real function definitions and should not have a block/body
            # attributed to them. Because func_start correctly only matches line-anchored
            # sub/method declarations, any match that sees a `;` terminator before its
            # real `{` body is a forward declaration. This mirrors objc-group-2's (#1336)
            # bodyless-prototype rejection. Note that Perl prototypes can contain a semicolon
            # (e.g., `sub Options($$;@)`), so we MUST track paren depth to avoid
            # confusing a prototype's internal semicolon with a top-level statement terminator.
            elif lang_id == "perl":
                pos = match.end()
                depth_paren = 0
                term_idx, term_kind = -1, None
                while pos < search_limit:
                    ch = safe_code[pos]
                    if ch == "(":
                        depth_paren += 1
                    elif ch == ")":
                        depth_paren = max(0, depth_paren - 1)
                    elif depth_paren == 0 and ch in (opener, ";"):
                        term_idx, term_kind = pos, ("brace" if ch == opener else "semi")
                        break
                    pos += 1
                if term_kind != "brace":
                    continue  # bodyless forward declaration (or neither terminator in the window)
                end_idx = self._find_balanced_end(safe_code, term_idx, opener, closer)
            else:
                brace_idx = safe_code.find(opener, start_idx, search_limit)
                if brace_idx == -1:
                    continue
                end_idx = self._find_balanced_end(safe_code, brace_idx, opener, closer)
                # #1836: cpp shares c's Mode-B fallback here but was left out of this
                # bound, so args_sig_end stayed None and args_search_text fell back to
                # the FULL block (signature + body) for cpp only. An empty-parameter-list
                # signature (`void foo()`) doesn't satisfy the strict `args` regex, so the
                # unbounded search kept scanning into the body and hallucinated an argument
                # count off the first internal call statement's own parens instead
                # (`godot/editor_node.cpp::EditorNode::save_before_run`: real 0 args,
                # measured 2, borrowed from an unrelated call inside the body).
                if lang_id in ("c", "cpp"):
                    args_sig_end = brace_idx

            block = code[start_idx:end_idx].strip()
            if not block:
                continue

            args_search_text = code[start_idx:args_sig_end] if args_sig_end is not None else None

            # #1837: a c/cpp signature is sometimes duplicated across an
            # #if/#else preprocessor conditional (e.g. micropython/gc.c's
            # gc_mark_subtree, gated on MICROPY_GC_SPLIT_HEAP), so
            # args_search_text ends up containing BOTH branches' signatures
            # concatenated with preprocessor tokens between them. `.search()`
            # downstream finds whichever branch comes first textually (the
            # `#if` branch), but tree-sitter's own ground truth resolves to
            # the branch immediately preceding the shared body (the
            # `#else`/`#elif` fallback -- the "guard is undefined" case,
            # which is also what actually compiles by default). Re-slicing
            # to start right after the LAST `#else`/`#elif` line isolates
            # that branch; a signature with no preprocessor split at all
            # (the overwhelming majority) has no such line and is untouched.
            # Gated to only fire when the text immediately preceding that
            # `#else`/`#elif` line (ignoring whitespace) is a `)` -- i.e. a
            # COMPLETE, already-closed signature sits right before the
            # branch fork, exactly the "two whole duplicate signatures"
            # shape this issue is about. Without this guard, the same regex
            # also (wrongly) fired on an `#ifdef`/`#else` splitting a single
            # signature's OWN parameter list mid-stream (chopping off the
            # real leading params) and on an unrelated `#ifdef`/`#elif`
            # block sitting between an already-complete signature and the
            # body's `{` (discarding the whole real signature) -- both real,
            # found during review, neither is the shape this fix targets, so
            # both now fall through unchanged to pre-#1837 behavior instead
            # of being newly broken by an overly broad re-slice.
            if lang_id in ("c", "cpp") and args_search_text is not None:
                last_branch_end = None
                for pp_match in re.finditer(r"^[ \t]*#\s*(?:else|elif)\b.*$", args_search_text, re.M):
                    if args_search_text[: pp_match.start()].rstrip().endswith(")"):
                        last_branch_end = pp_match.end()
                if last_branch_end is not None:
                    args_search_text = args_search_text[last_branch_end:]

            raw_name = match.group(match.lastindex) if match.lastindex else match.group(0)
            if any(m in raw_name for m in ["BOOST_", "TEST", "TEST_F", "TEST_CASE"]):
                raw_name = match.group(0)

            name = self._extract_name(raw_name)
            current_line_count += code.count("\n", last_counted_idx, start_idx)
            last_counted_idx = start_idx

            sat, mag = self._calculate_block_metrics(
                name,
                block,
                block.count("\n") + 1,
                current_line_count,
                current_line_count + block.count("\n"),
                rules,
                start_idx,
                end_idx,
                spatial_map,
                args_search_text,
            )
            satellites.append(sat)
            sum_fxn_impact += mag

        return satellites, sum_fxn_impact

    def _build_indentation_safe_stream(self, code: str, lang_id: Optional[str] = None) -> str:
        """
        Index-aligned shield for indentation-depth scans: blanks out
        triple/single-quoted string and `#`-comment content so a dedented
        line inside a docstring can't be mistaken for the real end of a
        function/class body, while preserving newlines so every index
        still maps 1:1 to `code`. Shared by `_slice_by_indentation` and
        the nesting-aware class-boundary scanner (#1040).

        #1266: `lang_id` selects the comment marker (`#` for python/yaml,
        `--` for haskell -- the only two markers Mode C has ever needed to
        route since it's currently gated to those languages) and bounds the
        single-quote branch for haskell only, same reasoning as the rust/
        scala bounds elsewhere: Haskell's idiomatic trailing-apostrophe
        identifiers (`x'`, `map'`) are unpaired single quotes that could
        otherwise cascade-pair with a much-later, unrelated one (the exact
        #1302 bug shape) -- python/yaml have no such identifier convention,
        so their branch stays unbounded (real Python strings can be long).

        #1184: strings and comments MUST be shielded in one combined-
        alternation pass, not sequential independent re.sub calls. Stripping
        comments in a separate LAST pass (the old approach) let an English
        contraction apostrophe inside a "#" comment (don't, it's, wasn't)
        get treated as a real string-open quote by the single-quote pass
        that ran before it -- it would then pair with whatever "'" came
        next anywhere later in the file and blank out every real line
        (including "def" lines) in between, silently dropping entire
        contiguous ranges of functions from extraction. A single pass lets
        whichever construct -- string or comment -- starts first at a given
        position atomically claim its whole span, so an apostrophe already
        inside a claimed comment is never independently reconsidered as a
        string delimiter. Mirrors `_build_brace_safe_stream`'s existing
        single-pass design, which never had this bug for the same reason.
        """

        def index_aligned_shield(m):
            text = m.group(0)
            return "".join("\n" if c == "\n" else " " for c in text)

        single_quote = r"'(?:\\.|[^'\\])*'"
        comment_marker = r"#[^\n]*"  # Python and YAML both use "#" for comments
        if lang_id == "haskell":
            single_quote = r"'(?:\\.|[^'\\]){0,10}'"
            comment_marker = r"--[^\n]*"

        # Order matters: triple-quote markers must precede the single-char
        # quote patterns, or e.g. the double-quote alternative would match
        # the first two characters of a `"""..."""` as an empty `""` string.
        combined_pattern = (
            r'"""(?:.*?)"""|'
            r"'''(?:.*?)'''|"
            r'"(?:\\.|[^"\\])*"|' + single_quote + r"|" + comment_marker
        )
        return re.sub(combined_pattern, index_aligned_shield, code, flags=re.DOTALL)

    def _slice_by_indentation(
        self,
        code: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
        lang_id: Optional[str] = None,
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE C] - Density Stratification (Python, YAML, Haskell)."""
        satellites: list[FunctionNode] = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        if not func_start:
            return [], 0.0

        # 1. Apply the Index-Aligned Shield
        # Preserves exact character indices and newline counts so safe_code maps 1:1 with code.
        safe_code = self._build_indentation_safe_stream(code, lang_id)

        # Match against safe_code to prevent triggering on words inside docstrings!
        try:
            matches = list(func_start.finditer(safe_code))
        except Exception:
            return [], 0.0

        # #1041: no longer skips matches whose start falls before the
        # previously accepted match's end -- see the identical fix (and
        # rationale) in `_slice_by_braces` above. Here each match resolves
        # its own end independently via the dedent scan below, from its OWN
        # indent level, so a nested def already gets a correctly bounded
        # (and correctly nested) scope on its own.

        # --- FAST O(N) LINE TRACKER ---
        current_line_count = offset + 1
        last_counted_idx = 0

        # #1442: haskell's equation-form func_start alternative (no `::`
        # required -- see the rule's own comment) matches EVERY pattern-
        # matched clause of a multi-clause function independently (e.g. each
        # of `toJSON`'s 6 instance-method equations), not just the first.
        # The first clause's own dedent-scan below already absorbs every
        # sibling clause into ONE block via the pre-existing same-name
        # continuation walk, so clauses 2..N would otherwise each spawn their
        # own duplicate, overlapping FunctionNode. Track a STACK of
        # (name, end) frames for every haskell group currently still "open"
        # (its span hasn't ended yet) and skip any later match that's just a
        # clause already inside one of them. #1564 (follow-up): this used to
        # also require an exact indent match -- see the skip's own comment
        # below for why that broke on multi-clause `let` bindings.
        #
        # #1616 (follow-up): a single (name, end) slot (rather than a stack)
        # broke as soon as a DIFFERENTLY-named match started nested inside
        # the tracked span -- e.g. a `let`-bound local like `adjustNum`
        # inside an outer multi-clause `go`'s own `do`-block, only visible
        # after this issue's own guard-only fix. That inner match correctly
        # needs its own tracking slot (so ITS siblings can dedup against
        # it), but overwriting the single slot lost the outer group entirely
        # -- a later `go` clause, still within the outer group's real span,
        # then failed the name check against "adjustNum" and was wrongly
        # recorded as a second, separate "go". A stack keeps the outer
        # frame alive underneath the inner one; popping closed frames (whose
        # span has ended) before each check lets a later match "return" to
        # whichever enclosing frame is still actually open, at any depth.
        haskell_group_stack: list[tuple[str, int]] = []

        for match in matches:
            start_idx = match.start()

            raw_name = match.group(match.lastindex) if match.lastindex else match.group(0)
            if raw_name is None:
                raw_name = match.group(0)
            name = self._extract_name(raw_name)

            # Find base indent level using the safe_code
            line_start_idx = safe_code.rfind("\n", 0, start_idx) + 1
            first_line = safe_code[line_start_idx : match.end()]
            base_indent = len(first_line) - len(first_line.lstrip())

            # #1564 (follow-up): dropped the `base_indent == last_hs_group_indent`
            # requirement this skip used to carry. It assumed every clause of a
            # multi-clause group shares its FIRST clause's exact indent -- true
            # for where/instance-block siblings (all flush at the same column),
            # but not for a multi-clause `let`, where Haskell's idiomatic style
            # aligns clause 2+ under the bound NAME rather than under `let`
            # itself (e.g. `let isPandocCiteproc (JSONFilter f) = ...\n      isPandocCiteproc _ = False`
            # -- clause 2 sits 4 columns deeper than clause 1's `let`). That
            # deeper indent is already correctly absorbed as body content by
            # clause 1's own dedent-scan below (it only stops at a line whose
            # indent dedents to <= base_indent), so `start_idx < last_hs_group_end`
            # alone already proves this match is a clause nested inside the
            # immediately-preceding same-named group, regardless of its own
            # indent column.
            if lang_id == "haskell":
                while haskell_group_stack and haskell_group_stack[-1][1] <= start_idx:
                    haskell_group_stack.pop()
                if any(fname == name and start_idx < fend for fname, fend in haskell_group_stack):
                    continue

            end_idx = len(safe_code)

            # #1199: func_start's regex ends right at the signature's opening
            # "(" (it never consumes the parameter list), so a signature that
            # wraps onto multiple physical lines leaves that "(" unclosed at
            # match.end(). The old code started the dedent scan on the very
            # next line -- for a wrapped signature, its closing "):" line is
            # typically re-dedented back to the def's own indent level, which
            # looked identical to a sibling statement ending the function and
            # truncated the block before the real body (or even the closing
            # paren) was ever included. Walk the signature's own paren depth
            # back to 0 first so the dedent scan only ever begins on the first
            # line that's genuinely past the signature.
            sig_scan = match.end()
            paren_depth = safe_code.count("(", start_idx, match.end()) - safe_code.count(")", start_idx, match.end())
            while sig_scan < len(safe_code) and paren_depth > 0:
                ch = safe_code[sig_scan]
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
                sig_scan += 1

            scan_pos = safe_code.find("\n", sig_scan)
            if scan_pos == -1:
                scan_pos = len(safe_code)
            else:
                scan_pos += 1

            equation_start_idx = None

            # --- FAST O(N) INDENT TRACKER ---
            # Replaced O(N^2) array allocations with zero-copy index jumping
            while scan_pos < len(safe_code):
                next_nl = safe_code.find("\n", scan_pos)
                line_end = len(safe_code) if next_nl == -1 else next_nl + 1

                f_line = safe_code[scan_pos:line_end]
                stripped = f_line.lstrip()

                if stripped:
                    current_indent = len(f_line) - len(stripped)
                    if current_indent <= base_indent:
                        # #1266: Haskell's convention puts a function's type
                        # signature and its defining equation(s) on SEPARATE
                        # top-level (column-0) lines (`foo :: Int -> Int` then
                        # `foo x = x + 1` right below it, both indent 0) --
                        # unlike Python, where the body is always MORE indented
                        # than its `def` line. A dedent-to-<=-base_indent line
                        # that's actually a continuation clause of THIS SAME
                        # function (the equation itself, or a further pattern-
                        # matched clause like `foo [] = ...`) must not end the
                        # block here, or the whole block is just the bare
                        # signature line -- caught and dropped by the `< 2`
                        # line-count floor below on every single-signature
                        # function, which is nearly all of them.
                        if lang_id == "haskell" and re.match(re.escape(name) + r"(?!['\w])", stripped):
                            if equation_start_idx is None:
                                equation_start_idx = scan_pos
                            scan_pos = line_end
                            continue
                        end_idx = scan_pos
                        break

                scan_pos = line_end

            # #1442: the eqn-form alternative (group 3) has no `::` signature
            # at all by construction -- it anchors purely on a pattern-
            # matched equation (`name pattern... = expr`). The point-free
            # arrow check below only makes sense for the `::`-signature
            # alternative (groups 1/2), where a missing arrow distinguishes
            # a point-free VALUE binding from a point-free FUNCTION; applying
            # it to an eqn-form match would reject nearly every real one
            # (e.g. `toJSON PlainMath = String "plain"` has no arrow at all).
            if lang_id == "haskell" and match.group(3) is None:
                # #1312: point-free value bindings (e.g. `defaultKaTeXURL :: Text`) look identical
                # to point-free functions at the `func_start` match level. The only difference is
                # that a true function's type signature contains an arrow (`->` or linear `⊸`).
                # We bound this check strictly to the signature span (from the match start up to
                # the first continuation clause, or the end of the block if no equations follow)
                # rather than using an unbounded regex lookahead in `func_start`.
                sig_end = equation_start_idx if equation_start_idx is not None else end_idx
                # `safe_code` has strings/comments masked, which is perfect since we don't
                # want to match an arrow inside a default-value string literal or comment
                signature_text = safe_code[start_idx:sig_end]
                if "->" not in signature_text and "⊸" not in signature_text:
                    continue

            # Extract the raw payload using the ORIGINAL code to retain the exact executable payload
            block = code[start_idx:end_idx].strip()
            if not block or (len(block.splitlines()) < 2 and lang_id not in ("haskell", "python")):
                continue

            # --- FAST O(N) LINE TRACKER ---
            current_line_count += code.count("\n", last_counted_idx, start_idx)
            last_counted_idx = start_idx
            start_line = current_line_count

            loc = block.count("\n") + 1
            end_line = start_line + loc - 1

            sat, mag = self._calculate_block_metrics(
                name,
                block,
                loc,
                start_line,
                end_line,
                rules,
                start_idx,
                end_idx,
                spatial_map,
            )

            satellites.append(sat)
            sum_fxn_impact += mag

            if lang_id == "haskell":
                haskell_group_stack.append((name, end_idx))

        return satellites, sum_fxn_impact

    def _slice_by_keywords(
        self,
        code: str,
        lang_id: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE D] - Semantic Handshake Stack (Shell, Ruby, Lua)."""
        self.logger.debug(f"[DIAGNOSTIC] Mode D: Initiating _slice_by_keywords for {lang_id}")
        config = ScopeParsingRegistry.get_config(lang_id)
        if not config:
            return self._slice_by_braces(code, lang_id, rules, offset, spatial_map)

        flags = re.IGNORECASE if config.get("ignore_case") else 0
        open_pattern = re.compile("|".join(config["openers"]), flags)
        close_pattern = re.compile("|".join(config["closers"]), flags)

        class_opener = config.get("class_opener")
        class_opener_pattern = re.compile(class_opener, flags) if class_opener else None

        satellites = []
        sum_fxn_impact = 0.0

        global_dust = []
        current_satellite = []

        stack_depth = 0
        satellite_name = "Main"
        is_current_satellite_class = False

        # 1. Apply the comprehensive Atomic Literal Shield
        # #1184: comment-stripping now happens INSIDE _apply_literal_shield,
        # in the same pass as string-shielding -- see that method's
        # docstring/comments for why a separate later pass was unsafe.
        # #1266: this call used to drop `lang_id` entirely (always passing
        # the implicit `None` default), which silently disabled BOTH the
        # heredoc-protection branch for ruby/perl/elixir/shell/bash (each
        # explicitly gated on `lang_id in [...]`, never actually reachable)
        # and, now, MATLAB's `%`-comment-marker resolution. Passing it
        # through is a strict correctness fix -- verified via
        # `crucible_check.py` to change nothing for the languages other than
        # matlab (their gates were already vacuous, now genuinely active with
        # no observed corpus diff).
        safe_code = self._apply_literal_shield(code, lang_id)

        # 2. Split both into parallel arrays
        original_lines = code.splitlines(keepends=True)
        safe_lines = safe_code.splitlines(keepends=True)

        total_lines = len(original_lines)
        self.logger.debug(f"[DIAGNOSTIC] Mode D: Traversing {total_lines} lines...")

        current_line_offset = offset
        sat_start_line = offset + 1
        current_char_offset = 0
        sat_start_char = 0

        lang_key = ScopeParsingRegistry._ALIASES.get(lang_id.lower(), lang_id.lower())

        # #1262: precompute every line's net scope-depth change (and the char
        # offset it starts at) ONCE, up front -- the primary top-level scan
        # below and the nested-function-opener scan further down both need
        # identical per-line bookkeeping (including the Ruby/Elixir inline-
        # modifier guard), and computing it twice would risk the two scans
        # silently drifting out of sync.
        net_changes: list[int] = []
        line_char_starts: list[int] = []
        running_char_offset = 0
        for safe_line in safe_lines:
            line_char_starts.append(running_char_offset)
            running_char_offset += len(safe_line)

            opens = len(open_pattern.findall(safe_line))
            closes = len(close_pattern.findall(safe_line))

            # The Ruby/Elixir Inline Modifier Guard
            if lang_key in ["ruby", "elixir"] and opens > 0:
                # Find all valid condition keywords on the line
                inline_mods = len(re.findall(r"(?<![:.])\b(if|unless|while|until)\b(?!:)", safe_line))

                if inline_mods > 0:
                    # Check if one of them is the actual start of the statement
                    if re.search(
                        r"^\s*(?:[a-zA-Z0-9_@.\[\]]+\s*=\s*)?(?:if|unless|while|until)\b",
                        safe_line,
                    ):
                        # Subtract all EXCEPT the one that started the line
                        opens -= inline_mods - 1
                    else:
                        # ALL of them are trailing modifiers (e.g., `return true if x unless y`)
                        opens -= inline_mods

            net_changes.append(opens - closes)

        # 3. Zip them together. We scan the safe_line for triggers, but save the orig_line into the satellite.
        depth_before_line: list[int] = []
        for orig_line, safe_line, net_change in zip(original_lines, safe_lines, net_changes):
            depth_before_line.append(stack_depth)

            if stack_depth == 0:
                if net_change > 0:
                    satellite_name = self._extract_semantic_name(safe_line, lang_key)
                    current_satellite = [orig_line]
                    is_current_satellite_class = (
                        bool(class_opener_pattern.search(safe_line)) if class_opener_pattern else False
                    )
                    stack_depth += net_change
                    sat_start_line = current_line_offset + 1
                    sat_start_char = current_char_offset
                else:
                    global_dust.append(orig_line)
                    stack_depth = max(0, stack_depth + net_change)
            else:
                current_satellite.append(orig_line)
                stack_depth += net_change

                # Check against MAX_DEPTH to prevent infinite saturation overflow
                if stack_depth > self.MAX_DEPTH:
                    self.logger.warning(
                        f"[DIAGNOSTIC] Mode D: Max depth ({self.MAX_DEPTH}) exceeded in {satellite_name}. Clamping."
                    )
                    stack_depth = self.MAX_DEPTH

                if stack_depth <= 0:
                    block = "\n".join(current_satellite).strip()
                    if block and not is_current_satellite_class:
                        loc = max(len(current_satellite), 1)
                        sat_end_line = current_line_offset + 1
                        sat_end_char = current_char_offset + len(orig_line)
                        sat, mag = self._calculate_block_metrics(
                            satellite_name,
                            block,
                            loc,
                            sat_start_line,
                            sat_end_line,
                            rules,
                            sat_start_char,
                            sat_end_char,
                            spatial_map,
                        )
                        satellites.append(sat)
                        sum_fxn_impact += mag

                    current_satellite = []
                    satellite_name = "Main"
                    stack_depth = 0
                    is_current_satellite_class = False

            current_line_offset += 1
            current_char_offset += len(orig_line)

        self.logger.debug("[DIAGNOSTIC] Mode D: Finished traversing. Processing remnants...")

        if stack_depth > 0 and current_satellite:
            block = "\n".join(current_satellite).strip()
            if block and not is_current_satellite_class:
                loc = max(len(current_satellite), 1)
                # #1266: MATLAB's language rule permits the LAST (or every)
                # function in a file to omit its closing `end` entirely when
                # no local function in the same file uses one either -- a
                # common, legitimate idiom in real corpus code (confirmed:
                # eeglab's eeg_eval.m), not a malformed/pathological file the
                # way an unclosed `if`/`for`/`while` block would be. Only
                # suppress the "_[Truncated]" anomaly marker when the unclosed
                # scope was opened by a real `function` line (i.e. got a real
                # name from `_extract_semantic_name`, not the generic
                # "Anonymous_Block" fallback control-flow openers still get)
                # -- an unclosed non-function block is still worth flagging.
                is_matlab_eof_function = lang_id == "matlab" and satellite_name not in ("Anonymous_Block", "Main")
                final_name = satellite_name if is_matlab_eof_function else satellite_name + "_[Truncated]"
                sat, mag = self._calculate_block_metrics(
                    final_name,
                    block,
                    loc,
                    sat_start_line,
                    current_line_offset,
                    rules,
                    sat_start_char,
                    current_char_offset,
                    spatial_map,
                )
                satellites.append(sat)
                sum_fxn_impact += mag

        if global_dust and "".join(global_dust).strip():
            block = "\n".join(global_dust).strip()
            if block:
                loc = max(len(global_dust), 1)
                sat, mag = self._calculate_block_metrics(
                    "__global_context__",
                    block,
                    loc,
                    offset + 1,
                    current_line_offset,
                    rules,
                )
                satellites.append(sat)
                sum_fxn_impact += mag

        # #1262: the stack-depth counter above only ever emits a satellite
        # for the OUTERMOST scope open at any given point -- once inside a
        # class/module body (stack_depth > 0), a further "def" just adjusts
        # the shared depth counter and gets folded into the enclosing
        # satellite's text instead of becoming its own FunctionNode. That's
        # correct for plain control-flow openers (if/while/... were never
        # meant to produce their own satellite either), but it silently
        # swallowed virtually every real Ruby method, since almost none are
        # defined outside a class/module body -- confirmed against the
        # language-crucible corpus: 0/117 real methods detected. Mirrors how
        # Mode B (_slice_by_braces) finds every func_start match independently
        # and resolves its own end via balanced-brace search regardless of
        # nesting (see the #1041 comment on that method) -- same idea here,
        # just keyword-balanced instead of brace-balanced, gated behind the
        # language config's "function_opener" so shell/lua/vb/elixir (not
        # audited against a corpus yet) keep their exact existing behavior.
        function_opener = config.get("function_opener")
        if function_opener:
            function_opener_pattern = re.compile(function_opener, flags)
            n = len(original_lines)
            # Bounds each individual trace so a pathological file (thousands
            # of unclosed/unbalanced "def" lines) can't turn this into an
            # O(n^2) scan -- mirrors Mode B's own bounded search_limit.
            max_trace_lines = 2000

            for i in range(n):
                if depth_before_line[i] <= 0:
                    continue
                if not function_opener_pattern.search(safe_lines[i]):
                    continue

                local_depth = 0
                block_lines: list[str] = []
                j = i
                trace_limit = min(n, i + max_trace_lines)
                while j < trace_limit:
                    local_depth += net_changes[j]
                    block_lines.append(original_lines[j])
                    if local_depth <= 0:
                        break
                    j += 1
                else:
                    j -= 1  # trace_limit reached without closing -- treat as truncated at the last line scanned

                block = "\n".join(block_lines).strip()
                if not block:
                    continue

                name = self._extract_semantic_name(safe_lines[i], lang_key) or "Main"
                loc = max(len(block_lines), 1)
                nested_start_line = offset + i + 1
                nested_end_line = offset + j + 1
                nested_start_char = line_char_starts[i]
                nested_end_char = line_char_starts[j] + len(safe_lines[j])

                sat, mag = self._calculate_block_metrics(
                    name,
                    block,
                    loc,
                    nested_start_line,
                    nested_end_line,
                    rules,
                    nested_start_char,
                    nested_end_char,
                    spatial_map,
                )
                satellites.append(sat)
                sum_fxn_impact += mag

        self.logger.debug(f"[DIAGNOSTIC] Mode D: Extracted {len(satellites)} satellites.")
        return satellites, sum_fxn_impact

    def _slice_by_terminator(
        self,
        code: str,
        lang_id: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE E] - Terminator Cleaving (SQL, Erlang, Prolog)."""
        config = ScopeParsingRegistry.get_config(lang_id)
        if not config:
            return self._slice_by_braces(code, lang_id, rules, offset, spatial_map)

        terminator_pattern = re.compile(config["terminator"])
        igniter_pattern = re.compile(config["igniter"], re.IGNORECASE)

        satellites = []
        sum_fxn_impact = 0.0
        current_satellite = []
        satellite_name = "Declarative_Block"

        is_orbiting = False
        sat_start_line = offset + 1
        current_line_offset = offset
        current_char_offset = 0
        sat_start_char = 0

        # 1. Apply the shield to the ENTIRE string, preserving newline counts.
        # This prevents multi-line strings from collapsing the parallel line iteration.
        # #1184: strings and comments are shielded in ONE combined-alternation
        # pass, not sequential independent re.sub calls -- a separate LATER
        # comment-strip pass (the old approach) let an English contraction
        # apostrophe inside a "--"/"%" comment (it's, doesn't) get treated as
        # a real string-open quote by the single-quote pass that ran before
        # it, pairing with whatever "'" came next anywhere later in the code
        # and blanking out entire real statements (including igniter
        # keywords like CREATE PROCEDURE) in between. One combined pass lets
        # whichever construct starts first at a given position atomically
        # claim its whole span, so a comment's apostrophe is never
        # independently reconsidered as a string delimiter. Same fix as
        # `_build_indentation_safe_stream` / `_apply_literal_shield`.
        def preserve_newlines(m):
            if m.groupdict().get("comment") is not None:
                return ""
            return '""' + "\n" * m.group(0).count("\n")

        safe_code = re.sub(
            r'"(?:\\.|[^"\\])*"|'
            r"'(?:\\.|[^'\\])*'|"
            r"`(?:\\.|[^`\\])*`|"
            r"(?P<comment>--|%)[^\n]*",
            preserve_newlines,
            code,
            flags=re.DOTALL,
        )

        # 2. Split both into parallel arrays
        original_lines = code.splitlines(keepends=True)
        safe_lines = safe_code.splitlines(keepends=True)

        # 3. Zip them together. We scan the safe_line for igniters/terminators,
        # but save the orig_line into the satellite block.
        for orig_line, safe_line in zip(original_lines, safe_lines):
            current_line_offset += 1

            if not safe_line.strip() and not is_orbiting:
                sat_start_line = current_line_offset + 1
                current_char_offset += len(orig_line)
                continue

            # Check for block ignition
            if not is_orbiting:
                is_orbiting = True
                sat_start_char = current_char_offset
                match = igniter_pattern.search(safe_line)
                if match:
                    lang_key = ScopeParsingRegistry._ALIASES.get(lang_id.lower(), lang_id.lower())
                    satellite_name = (
                        f"{match.group(1).upper()}_Statement" if "sql" in lang_key else match.group(0).strip()
                    )
                    satellite_name = re.sub(r"[^a-zA-Z0-9_]", "", satellite_name)

            # Build the block using the unaltered original line
            current_satellite.append(orig_line)

            # The Guillotine Drop (Evaluate the safe_line for the terminator)
            if terminator_pattern.search(safe_line):
                block = "\n".join(current_satellite).strip()
                if block:
                    loc = max(len(current_satellite), 1)
                    sat_end_line = current_line_offset
                    sat_end_char = current_char_offset + len(orig_line)
                    sat, mag = self._calculate_block_metrics(
                        satellite_name,
                        block,
                        loc,
                        sat_start_line,
                        sat_end_line,
                        rules,
                        sat_start_char,
                        sat_end_char,
                        spatial_map,
                    )
                    satellites.append(sat)
                    sum_fxn_impact += mag

                # Reset for the next orbit
                current_satellite = []
                satellite_name = "Declarative_Block"
                is_orbiting = False
                sat_start_line = current_line_offset + 1

            current_char_offset += len(orig_line)

        # Process Remnants (Unterminated blocks at the end of the file)
        if current_satellite and "".join(current_satellite).strip():
            block = "\n".join(current_satellite).strip()
            if block:
                loc = max(len(current_satellite), 1)
                sat, mag = self._calculate_block_metrics(
                    satellite_name + "_[Unterminated]",
                    block,
                    loc,
                    sat_start_line,
                    current_line_offset,
                    rules,
                    sat_start_char,
                    current_char_offset,
                    spatial_map,
                )
                satellites.append(sat)
                sum_fxn_impact += mag

        return satellites, sum_fxn_impact

    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution
    # SHARED FUNCTIONAL METRICS ENGINE
    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution

    def _matching_paren_end(self, text: str, open_idx: int) -> int:
        """
        String-aware scan for the index of the "(" at `open_idx`'s matching ")".
        Returns `len(text)` if it never closes within `text` (e.g. a signature
        capture that only includes an opening context paren, like Scheme's
        `(define (...)`). Shared by `_count_top_level_args` and
        `_calculate_block_metrics`'s args-count self-containment check (#1199).
        """
        depth = 0
        in_string = False
        quote_char = ""
        i = open_idx
        while i < len(text):
            ch = text[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
            elif ch in ("'", '"', "`"):
                in_string = True
                quote_char = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return len(text)

    def _count_top_level_args(self, args_str: str, treat_as_body: bool = False) -> int:
        """
        Depth- and string-aware argument counter for a captured function signature.

        `args` regexes capture the whole signature (e.g. "def foo(x, y)",
        "(x, y) =>"), so the real argument list sits one bracket level inside the
        first "(...)"; bracket-less forms (Python lambda, Lisp/space-separated)
        have no such wrapper, so top level IS depth 0 for them. Either way, only
        commas at that top level are real argument separators -- commas trapped
        inside nested (), [], {}, <> (generic type hints, default dict/list
        literals, nested callback signatures) or inside string literals must be
        ignored, or a single `data: Dict[str, int]` argument gets miscounted as
        two.

        Returns the actual argument count, not a raw comma tally: an empty
        parameter list is 0 (not 1), a trailing top-level comma -- the
        near-universal `ruff format` style for a multi-line signature with one
        parameter per line -- doesn't create a phantom extra segment, a lone
        `void` segment (C's explicit empty-parameter-list marker, `int f(void)`)
        is 0 arguments not 1, and a bare `*`/`/` segment (Python's keyword-only/
        positional-only markers, e.g. `def f(a, *, b):`) is real signature
        syntax but not itself an argument -- `ast.parse`'s own `FunctionDef.args`
        doesn't count it either, so counting every comma-separated segment as
        one argument overcounts any such signature by exactly one per marker
        (#1199, #1209).

        `treat_as_body=True` (#1645) skips the "find the first '(' and re-slice
        into it" wrapper-detection entirely, treating `args_str` as ALREADY the
        bare parameter-list body with no signature prefix or wrapper of its own.
        For a capture shape where that's genuinely true (zig's `args` regex --
        unlike python's, it captures only the inner text, never sharing group(0)
        with a "fn name(...)" prefix), the default `.find("(")` heuristic is
        actively wrong the moment any PARAMETER'S OWN TYPE contains literal
        parens (`ctx: @This()`, a function-pointer param typed `fn (...) void`):
        it mistakes that inner paren for the outer wrapper and re-slices to just
        its contents, silently truncating or zeroing the real body.
        """
        body = args_str
        if not treat_as_body:
            open_idx = args_str.find("(")
            if open_idx != -1:
                wrapper_end = self._matching_paren_end(args_str, open_idx)
                # #1854: a C/C++ function returning a function pointer wraps its
                # own name in parens (`void (*foo(int a, int b))(int c)`, or the
                # pointer-to-member form `void (Cls::*foo(int a, int b))(int c)`)
                # -- the FIRST "(" here is that wrapper's, not the parameter
                # list's, so blindly matching it truncates the body to
                # "*foo(int a, int b)" and hides every comma inside the real
                # params one depth level too deep. When the text between the
                # first "(" and the next one is just a pointer/name token
                # (optionally class-qualified), the wrapper is this shape and
                # the parameter list is the SECOND "(" instead -- gated on the
                # wrapper's own close being immediately followed by another "("
                # (the pointer's own return-type parameter list, always present
                # in this syntax) so a macro invocation shaped the same way at a
                # glance (`EXECUTE_TASK(*task_ptr(a, b))`, found during review --
                # nothing of that shape ever follows a macro call's closing
                # paren) doesn't false-positive into the same rewrite.
                inner_open = args_str.find("(", open_idx + 1)
                if inner_open != -1 and inner_open < wrapper_end:
                    between = args_str[open_idx + 1 : inner_open]
                    after_wrapper = args_str[wrapper_end + 1 :].lstrip(" \t\n")
                    if after_wrapper.startswith("(") and re.fullmatch(
                        r"[ \t\n]*(?:[a-zA-Z_]\w*[ \t\n]*::[ \t\n]*)*\*[ \t\n]*[a-zA-Z_]\w*[ \t\n]*", between
                    ):
                        open_idx = inner_open
                        wrapper_end = self._matching_paren_end(args_str, open_idx)
                body = args_str[open_idx + 1 : wrapper_end]

        if not body.strip():
            return 0

        depth = 0
        in_string = False
        quote_char = ""
        segments: list[str] = []
        seg_start = 0
        i = 0
        while i < len(body):
            ch = body[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
            elif ch in ('"', "`"):
                in_string = True
                quote_char = ch
            elif ch == "'":
                if getattr(self, "language", "") in ("rust", "scala") and re.match(
                    r"[a-zA-Z_]\w*\b(?!')", body[i + 1 :]
                ):
                    # It's a Rust lifetime or Scala symbol (e.g. `'a>`, `'_ `), not a string literal
                    pass
                else:
                    in_string = True
                    quote_char = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth > 0:
                    depth -= 1
            # #1853: `<`/`>` double as math/comparison/shift operators, not just
            # generic-bracket delimiters -- a default value like `a = (x < y)`
            # permanently inflated depth (no matching `>` ever follows), silently
            # hiding every later top-level comma, while `a = (x > y, z)` did the
            # reverse: `>` prematurely closed a bracket that was never open,
            # exposing a nested comma as a false top-level separator. Neither
            # failure mode is possible in a language with no `<...>` generic/
            # template syntax at all (Python's own repro example), so bracket
            # treatment is scoped to languages that actually use angle brackets
            # this way in a signature. This doesn't fully solve the ambiguity
            # inside a generic-using language's OWN default-value expressions
            # (a genuinely hard case without a type-aware parser) -- it only
            # removes the false positives everywhere else, per the languages
            # this counter is reached from.
            elif ch == "<" and self.primary_lang_id in _ANGLE_BRACKET_GENERIC_LANGUAGES:
                depth += 1
            elif ch == ">" and self.primary_lang_id in _ANGLE_BRACKET_GENERIC_LANGUAGES:
                # #1645: a bare `>` is treated as a generic-closing bracket (Rust
                # `Vec<T>`, TS/C++ templates), but zig's `=>` switch/match-arm
                # arrow is a two-char token whose `>` isn't a bracket at all --
                # decrementing depth on it let a switch-expression's internal
                # commas leak out as false top-level argument separators (zig
                # `result_status: switch (operation) { .a, .b => X, ... }` as a
                # parameter's type measured got=10 against real=4). Scoped to
                # `treat_as_body` (zig's own call path) rather than fixed
                # unconditionally: other languages sharing this counter reach
                # `>` only via the wrapper-detected `body` slice, where a stray
                # `->`/`=>` inside already-truncated text is a different,
                # pre-existing bug this narrower guard deliberately leaves alone
                # rather than risk shifting their baselines in a zig-scoped fix.
                if i > 0 and body[i - 1] in "=-":
                    pass
                elif depth > 0:
                    depth -= 1
            elif ch == "," and depth == 0:
                segments.append(body[seg_start:i])
                seg_start = i + 1
            i += 1
        segments.append(body[seg_start:])

        real_segments = [s for s in (seg.strip() for seg in segments) if s and s not in ("*", "/")]
        if real_segments == ["void"]:
            return 0
        return len(real_segments)

    def _count_colon_selector_segments(self, args_str: str) -> int:
        """
        Counts parameters in an Objective-C keyword-message selector, e.g.
        `doThing:(int)x withOther:(int)y` -- unlike every other language's
        args shape, each parameter here is its own repeated `label:(Type)name`
        segment scattered across the signature, not one comma-separated list
        inside a single "(...)" (#1209). One argument per top-level `:`
        occurrence; colons inside nested brackets or string literals (a
        default value's own type, an embedded block signature) don't count.

        #1314 (follow-up): the `:` and `(` don't have to be adjacent -- real
        corpus code (language-crucible/data/objective-c/worldwideweb/HyperText.h)
        commonly writes `applyStyle: (HTStyle *)style` with a space after the
        colon.

        #1335: the `(Type)` cast is now optional in the source regex (older
        untyped keyword-message style, e.g. `back:sender`, defaults to
        `id`), so this no longer requires a `(` after the colon at all --
        every top-level colon in `args_str` is guaranteed by the calling
        regex's structure to be a real `label:` separator, never a stray
        `label:` cast sitting apart from its parameter.
        """
        depth = 0
        in_string = False
        quote_char = ""
        count = 0
        i = 0
        while i < len(args_str):
            ch = args_str[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
            elif ch in ("'", '"', "`"):
                in_string = True
                quote_char = ch
            elif ch in "([{<":
                depth += 1
            elif ch in ")]}>":
                if depth > 0:
                    depth -= 1
            elif ch == ":" and depth == 0:
                count += 1
            i += 1
        return count

    def _count_shell_positional_max(self, matches: list[str]) -> int:
        """
        Bash has no formal parameter-list syntax at all (`foo() { ... }`'s
        parens are always empty, permanently, by grammar) -- args arrive via
        $1/$2/.../"$@" referenced anywhere in the function body, not one
        contiguous signature span. #1518: takes every positional-parameter
        reference found in the block (via `_args_findall_max_groups`, which
        makes the caller scan the WHOLE block instead of stopping at the
        first match) and returns the highest numbered $N seen -- that's the
        real minimum arg count the body demonstrably relies on. $0 (the
        script's own name, not a function argument) is naturally excluded
        since "0" never raises the max above a real reference. A bare
        "$@"/"$*" reference with no numbered $N anywhere implies "at least
        1" real argument is consumed, just not by explicit index.
        """
        max_index = 0
        saw_variadic = False
        for text in matches:
            digits = re.search(r"[0-9]+", text)
            if digits:
                max_index = max(max_index, int(digits.group(0)))
            elif "@" in text or "*" in text:
                saw_variadic = True
        return max_index if max_index else (1 if saw_variadic else 0)

    def _count_haskell_type_arrows(self, args_str: str) -> int:
        """
        Counts a Haskell function's curried arity from its flattened `::`
        type signature (e.g. "Int -> Int -> Int" is 2 arguments): each
        top-level "->" separates one more parameter from the rest, so N
        arrows = N parameters -- not "arrows - 1", since the trailing
        (return-type) segment never has an arrow of its own to begin with
        (#1209). A leading typeclass-constraint clause (`Show a => ...`) is
        skipped by only counting arrows after the LAST top-level "=>", since
        constraints on a type variable aren't a real parameter. An arrow
        nested inside a parameter's own parenthesized function type (a
        higher-order argument, e.g. `(Int -> Int) -> Int`) isn't top-level
        and doesn't count as a separate parameter of the OUTER function.
        """
        last_constraint = args_str.rfind("=>")
        scan_from = last_constraint + 2 if last_constraint != -1 else 0

        depth = 0
        count = 0
        i = scan_from
        while i < len(args_str):
            ch = args_str[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth > 0:
                    depth -= 1
            elif ch == "-" and depth == 0 and i + 1 < len(args_str) and args_str[i + 1] == ">":
                count += 1
                i += 1
            i += 1
        return count

    def _count_haskell_pattern_list(self, text: str) -> int:
        """
        Counts space-separated argument patterns in a signature-less Haskell
        function equation's own LHS (#1505 follow-up), e.g.
        `combine newval (MetaList xs)` is 2 arguments, not 3. The generic
        whitespace-split fallback every other language uses would wrongly
        split the single parenthesized compound pattern `(MetaList xs)` into
        two tokens -- this is depth- and string-aware instead: whitespace
        inside a (), [], or a double-quoted string doesn't separate two real
        top-level pattern arguments, only whitespace at depth 0 outside a
        string does. Mirrors the token shapes the `args` regex's own
        equation-pattern-list alternative captures (quoted string / one-level
        paren group / one-level bracket group / bare identifier-ish run), so
        this only ever needs to walk text that regex has already validated.
        """
        depth = 0
        in_string = False
        quote_char = ""
        count = 0
        at_boundary = True
        i = 0
        while i < len(text):
            ch = text[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
                i += 1
                continue
            if ch == '"':
                in_string = True
                quote_char = ch
                if at_boundary:
                    count += 1
                    at_boundary = False
                i += 1
                continue
            if ch in "([":
                if depth == 0 and at_boundary:
                    count += 1
                    at_boundary = False
                depth += 1
                i += 1
                continue
            if ch in ")]":
                if depth > 0:
                    depth -= 1
                i += 1
                continue
            if ch in " \t":
                if depth == 0:
                    at_boundary = True
                i += 1
                continue
            if depth == 0 and at_boundary:
                count += 1
                at_boundary = False
            i += 1
        return count

    def _count_tcl_arg_list(self, text: str) -> int:
        """
        Counts Tcl argument list parameters, aware of brace nesting.
        Tcl uses {name default_value} for optional arguments. This entire
        nested brace structure counts as a single parameter.
        Whitespace separates parameters only at depth 0.
        """
        depth = 0
        count = 0
        at_boundary = True
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "{":
                if depth == 0 and at_boundary:
                    count += 1
                    at_boundary = False
                depth += 1
                i += 1
                continue
            if ch == "}":
                if depth > 0:
                    depth -= 1
                i += 1
                continue
            if ch in " \t\r\n":
                if depth == 0:
                    at_boundary = True
                i += 1
                continue
            if depth == 0 and at_boundary:
                count += 1
                at_boundary = False
            i += 1
        return count

    def _calculate_block_metrics(
        self,
        name: str,
        block: str,
        loc: int,
        start_line: int,
        end_line: int,
        rules: dict[str, Any],
        start_idx: int = 0,
        end_idx: int = 0,
        spatial_map: Optional[dict[str, list[int]]] = None,
        args_search_text: Optional[str] = None,
        args_count_override: Optional[int] = None,
    ) -> tuple[FunctionNode, float]:
        """
        Calculates the structural weight, algorithmic complexity, and hit vector
        for an extracted functional block.

        DEFENSIVE ARCHITECTURE (Big-O without ASTs):
        ASTs require intense compilation overhead to determine cyclomatic nesting depth.
        Because we prioritize functional intent, this engine uses standard indentation
        as a 95% accurate proxy for O(N) complexity at a fraction of the compute cost.

        #1335: `args_search_text`, when given, bounds the args-pattern search to just
        that text (a caller-computed signature-only slice) instead of the whole `block`.
        `block` for a Mode-B (`_slice_by_braces`) function always spans the signature
        AND its full body, so an unbounded `args_pattern.search(block)` can silently
        match call-statement or control-flow text deep in the body instead of the real
        signature once the signature itself doesn't match any args-pattern branch (e.g.
        objc's `- free { if (Address) free(Address); ... }`, a zero-arg method whose own
        signature has no parens/colons at all -- the body's own `free(Address);` call
        wrongly "borrowed" as the args). Only objc's `_slice_by_braces` branch passes
        this today; every other caller leaves it None and keeps the original
        whole-`block` search.

        #1918: `args_count_override`, when given (an int, not None), is used AS the final
        `args_count` directly, skipping the generic single-`.search()`-match derivation
        below entirely. That derivation assumes a matched arg-pattern's own captured text
        is either a self-contained parameter list or a splittable body -- true for most
        languages, structurally false for ABAP's `args` regex (an intentional per-clause
        existence detector, see language_standards.py's own comment), which can never
        represent "how many parameters" from one match. Only ABAP's `_slice_by_labels`
        caller passes this today, via its own dedicated counter.
        """
        args_pattern = rules.get("args")

        # --- THE FIX: O(log N) Binary Search for Structural Heuristics ---
        hit_vector = {}
        if spatial_map is not None:
            for key, indices in spatial_map.items():
                left = bisect.bisect_left(indices, start_idx)
                right = bisect.bisect_left(indices, end_idx)
                count = right - left
                if count > 0:
                    hit_vector[key] = count

            branch_hits = hit_vector.get("branch", 0)
            linear_hits = hit_vector.get("structural_boundaries", 0)
        else:
            # Fallback for untested manual calls
            branch_pattern = rules.get("branch")
            linear_pattern = rules.get("structural_boundaries")
            # Both .findall() calls below are guarded by hasattr(), which
            # mypy doesn't narrow None away for the way it would isinstance()
            # -- hence the type: ignore[union-attr] markers on each.
            branch_hits = (
                len(branch_pattern.findall(block))  # type: ignore[union-attr]
                if hasattr(branch_pattern, "findall")
                else (len(re.findall(str(branch_pattern), block)) if branch_pattern else 0)
            )
            linear_hits = (
                len(linear_pattern.findall(block))  # type: ignore[union-attr]
                if hasattr(linear_pattern, "findall")
                else (len(re.findall(str(linear_pattern), block)) if linear_pattern else 0)
            )

        total_hits = branch_hits + linear_hits

        # --- FAST CODING LOC HEURISTIC (Syntax Fixed!) ---
        # Quickly strip out blank lines and standard single-line comments to find the true logic mass
        # THE FIX: Preserve leading whitespace to calculate Big-O nesting depth!
        raw_lines = [l for l in block.splitlines() if l.strip() and not l.lstrip().startswith(("#", "//", "/*", "*"))]
        coding_loc = len(raw_lines)

        # --- NEW: FUNCTION-LEVEL KEYWORD DENSITY (The Micro-Auditor) ---
        # Total structural signals divided by the physical lines of the function.
        total_keyword_hits = sum(hit_vector.values()) if hit_vector else total_hits
        keyword_density = total_keyword_hits / max(loc, 1)

        args_count = 0
        if args_pattern and hasattr(args_pattern, "search"):
            try:
                arg_match = args_pattern.search(args_search_text if args_search_text is not None else block)
                if arg_match:
                    args_str = arg_match.group(arg_match.lastindex) if arg_match.lastindex else arg_match.group(0)
                    stripped = args_str.strip() if args_str else ""
                    # #1199: a capture group whose ENTIRE span is a self-contained
                    # "(...)" pair (true of python's def/lambda-with-parens args
                    # group once it stops sharing group(0) with the "def name"
                    # prefix) is unambiguously the real parameter list -- a
                    # comma-free non-empty body there is exactly ONE argument, not
                    # zero. The old code could only decide via "does args_str
                    # contain a comma", which silently overcounted every
                    # zero/one-arg signature by +1 (the "def name(...)" prefix
                    # itself supplied a spurious extra whitespace-split token).
                    # Signatures that AREN'T self-contained (e.g. Scheme's
                    # `(define (func arg1 arg2)`, whose outer "(define" paren
                    # never closes within the capture) fall through unchanged to
                    # the original comma/whitespace-split heuristics below.
                    bare_body_groups = rules.get("_args_bare_body_groups")
                    arrow_count_groups = rules.get("_args_arrow_count_groups")
                    colon_selector_groups = rules.get("_args_colon_selector_groups")
                    pattern_list_groups = rules.get("_args_pattern_list_groups")
                    tcl_pattern_list_groups = rules.get("_args_tcl_pattern_list_groups")
                    findall_max_groups = rules.get("_args_findall_max_groups")
                    findall_sum_groups = rules.get("_args_findall_sum_groups")
                    # #1607: perl's group-2 "sub/method signature" capture matches a
                    # legacy PROTOTYPE (`sub Options($$;@)`, `sub Get8u($$)`) exactly
                    # the same as a real modern named signature (`sub foo($a, $b)`) --
                    # both are just "(...)" text sitting right after the sub/method
                    # keyword. But a prototype is a sequence of bare sigils (`$`
                    # scalar, `@` array, `%` hash, `;` optional-args marker, `\`
                    # by-ref) with NO commas between them, BY GRAMMAR, regardless of
                    # how many parameters it declares -- so the #1199 self-contained-
                    # "(...)" branch below (comma-free non-empty parens = exactly 1
                    # argument, correct for a real signature) silently locks every
                    # prototype's count at 1 no matter its real arity. Confirmed on
                    # the corpus: `sub Get8u($$) { return DoUnpackStd('C', @_); }`
                    # (real arity 0, no shift/my-unpacking at all) and `sub
                    # HDump($$$$;$$$)` (real arity 7, seven sequential shifts) both
                    # measured got=1. A prototype gives sigil TYPES, not a reliable
                    # argument COUNT (a real signature's own comma-count heuristic
                    # doesn't apply, and summing sigils isn't equivalent to arity
                    # once `;` marks an optional boundary either) -- so a prototype is
                    # treated exactly like perl's signature-LESS traditional subs
                    # already are (#1519): skip it and fall through to the same
                    # body-idiom scan (`_args_findall_sum_groups`, groups 3/4/5)
                    # rather than trusting the declaration at all.
                    prototype_groups = rules.get("_args_prototype_groups")
                    is_bare_prototype = False
                    if prototype_groups and arg_match.lastindex in prototype_groups:
                        proto_inner = (
                            stripped[1:-1] if stripped.startswith("(") and stripped.endswith(")") else stripped
                        )
                        is_bare_prototype = bool(re.fullmatch(r"[$@%\\;+*&]*", proto_inner))
                    if bare_body_groups and arg_match.lastindex in bare_body_groups:
                        # Zig (#1645): unlike python's args group (which still shares
                        # group(0) with "def name(...)" and so needs the #1199
                        # self-contained-"(...)" detection above to know it's already
                        # unwrapped), zig's "args" regex captures ONLY the inner
                        # parameter-list text -- there is no surrounding "(...)" in
                        # the captured group at all, by construction of the regex
                        # itself. That broke BOTH downstream heuristics:
                        #   - comma-free single param (`self: Default`) has an
                        #     internal space in its type annotation, so the
                        #     whitespace-split fallback below miscounted it as 2
                        #     tokens instead of 1 (measured got=2/3 against real=1,
                        #     the majority of zig's args mismatches).
                        #   - multi-param lists where a param's TYPE itself contains
                        #     literal parens (`ctx: @This()`, `fn (?*anyopaque) void`
                        #     function-pointer params -- both idiomatic, common Zig)
                        #     broke `_count_top_level_args`'s own wrapper-detection:
                        #     it assumes the first "(" it finds via `.find("(")` is
                        #     the outer wrapper of the whole signature (true for
                        #     python's "def foo(x, y)"-shaped capture) and re-slices
                        #     to "between that paren and its match" -- for zig's
                        #     already-bare capture that first "(" is instead some
                        #     inner type's own parens (e.g. `@This()`'s empty pair),
                        #     silently truncating or zeroing the counted body
                        #     (measured got=0/1 against real up to 12).
                        # `treat_as_body=True` skips that wrapper-detection entirely
                        # and depth-counts commas over the ENTIRE captured string as
                        # already being the parameter-list body, which is correct by
                        # construction for this regex shape.
                        args_count = self._count_top_level_args(args_str, treat_as_body=True)
                    elif findall_max_groups and arg_match.lastindex in findall_max_groups:
                        # Shell (#1518): a single match only ever sees the FIRST
                        # positional-parameter reference in the block, silently
                        # dropping every one after it (`readlink "$1"` ... `"$2"`
                        # measured got=1, not 2). Re-scans the whole block for
                        # every match this rule's pattern can find and takes the
                        # max positional index via `_count_shell_positional_max`,
                        # instead of trusting the single leftmost match found above.
                        search_text = args_search_text if args_search_text is not None else block
                        all_matches = [m.group(0) for m in args_pattern.finditer(search_text)]
                        args_count = self._count_shell_positional_max(all_matches)
                    elif findall_sum_groups and (arg_match.lastindex in findall_sum_groups or is_bare_prototype):
                        # Perl (#1519): traditional subs commonly unpack their
                        # args across MULTIPLE statements -- one `my $class =
                        # shift;` for the invocant plus a later `my ($a, $b) =
                        # @_;` for the rest, or several sequential `my $x =
                        # shift;` lines -- and a single match only ever sees
                        # the first one. Re-scans the whole block and sums each
                        # matched statement's own contribution: a self-contained
                        # "(...)" match (the `my (...) = @_` shape) contributes
                        # its comma-count; anything else matching one of these
                        # groups (the tightened `my $x = shift` shape, which
                        # deliberately excludes `shift @other`/`shift(@other)` --
                        # those shift a DIFFERENT array, not @_) contributes
                        # exactly 1. Reached either when the single leftmost match
                        # above ISN'T a real declared signature (group 2) at all, or
                        # (#1607) IS group 2 but is a bare-sigil legacy PROTOTYPE
                        # rather than a real named signature -- see `is_bare_prototype`
                        # above. A sub with an actual named signature (real commas,
                        # real identifiers) still takes the self-contained-"(...)"
                        # branch below unchanged.
                        search_text = args_search_text if args_search_text is not None else block
                        total = 0
                        for m in args_pattern.finditer(search_text):
                            if not m.lastindex or m.lastindex not in findall_sum_groups:
                                continue
                            sub_str = (m.group(m.lastindex) or "").strip()
                            if (
                                sub_str.startswith("(")
                                and sub_str.endswith(")")
                                and self._matching_paren_end(sub_str, 0) == len(sub_str) - 1
                            ):
                                total += self._count_top_level_args(sub_str)
                            else:
                                total += 1
                        args_count = total
                    elif tcl_pattern_list_groups and arg_match.lastindex in tcl_pattern_list_groups:
                        # Tcl default-value braces (#1512):
                        # Tcl allows nested braces like {db db} for default
                        # parameter values, which should count as a single argument.
                        args_count = self._count_tcl_arg_list(stripped)
                    elif pattern_list_groups and arg_match.lastindex in pattern_list_groups:
                        # Haskell signature-less equation LHS (#1505 follow-up):
                        # a naive whitespace split would wrongly split a single
                        # parenthesized compound pattern like `(MetaList xs)`
                        # into two tokens (and the self-contained-"(...)"
                        # branch below only handles the case where the ENTIRE
                        # capture is one paren group, not a mix of bare and
                        # parenthesized patterns like `newval (MetaList xs)`),
                        # so this needs its own dedicated depth-aware counter,
                        # same rationale as arrow_count_groups just above.
                        args_count = self._count_haskell_pattern_list(stripped)
                    elif arrow_count_groups and arg_match.lastindex in arrow_count_groups:
                        # Haskell `::` type signature (#1209): curried arity
                        # is the top-level arrow count, not a comma-separated
                        # list or a whitespace-token count -- neither maps
                        # onto Haskell's syntax at all (a signature has no
                        # commas, and naive whitespace-splitting would count
                        # every type constructor and "->" token as if it were
                        # its own argument). Gated on an explicit, opt-in
                        # rules-dict flag naming the SPECIFIC capture-group
                        # index this applies to (haskell's args rule has a
                        # separate, differently-shaped lambda-parameter
                        # group too) rather than sniffing "does stripped
                        # contain '->'" -- a real signature can have ZERO
                        # arrows (`noop :: IO ()`), so content-based
                        # detection can't distinguish "Haskell type sig,
                        # zero args" from "not a type sig at all" the way
                        # every other branch here safely can from shape alone.
                        args_count = self._count_haskell_type_arrows(stripped)
                    elif (
                        stripped.startswith("(")
                        and stripped.endswith(")")
                        and self._matching_paren_end(stripped, 0) == len(stripped) - 1
                    ):
                        # #1199: a capture group whose ENTIRE span is a self-contained
                        # "(...)" pair (true of python's def/lambda-with-parens args
                        # group once it stops sharing group(0) with the "def name"
                        # prefix) is unambiguously the real parameter list -- a
                        # comma-free non-empty body there is exactly ONE argument, not
                        # zero. The old code could only decide via "does args_str
                        # contain a comma", which silently overcounted every
                        # zero/one-arg signature by +1 (the "def name(...)" prefix
                        # itself supplied a spurious extra whitespace-split token).
                        # Signatures that AREN'T self-contained (e.g. Scheme's
                        # `(define (func arg1 arg2)`, whose outer "(define" paren
                        # never closes within the capture) fall through unchanged to
                        # the original comma/whitespace-split heuristics below.
                        args_count = self._count_top_level_args(stripped)
                    elif colon_selector_groups and arg_match.lastindex in colon_selector_groups:
                        # Objective-C keyword-message selector (#1209,
                        # #1335) -- the only shape here whose parameters
                        # aren't inside a single "(...)" span at all, so
                        # neither the self-contained branch above nor the
                        # comma-based one below apply. Gated on an explicit,
                        # opt-in rules-dict flag naming the SPECIFIC
                        # capture-group index this applies to (same
                        # convention as haskell's `_args_arrow_count_groups`)
                        # rather than sniffing "does stripped start with
                        # `label?:(`" -- #1335 made the `(Type)` cast
                        # optional, so shape-based detection can no longer
                        # tell a real untyped segment (`back:sender`) apart
                        # from unrelated `label: value` text by content alone.
                        args_count = self._count_colon_selector_segments(stripped)
                    elif stripped and stripped != "()":
                        if "," in args_str:
                            args_count = self._count_top_level_args(args_str)
                        else:
                            # Handle space-separated arguments (Lisp/Scheme/Shell)
                            args_count = len(args_str.strip().split())
            except Exception as e:
                self.logger.debug(f"Argument-count regex extraction failed, leaving args_count 0: {e}")

        # #1918: overrides whatever the generic single-match derivation above computed.
        # ABAP's `args` regex (see language_standards.py's own comment) is intentionally a
        # per-CLAUSE existence detector -- `.search()` finds one match, once, and that
        # match's captured text is just the bare keyword (IMPORTING/EXPORTING/...), which
        # none of the generic derivation strategies above can turn into a real parameter
        # COUNT (a 4-parameter IMPORTING clause and a 0-parameter one produce the identical
        # single match). Callers that already know the real count via a dedicated,
        # language-specific counter (currently only ABAP's caller in _slice_by_labels) pass
        # it here instead of trying to force this generic path to produce it.
        if args_count_override is not None:
            args_count = args_count_override

        texture_str = self._classify_function(name, block, rules)

        # ---> THE FIX 1: SIGNAL-ANCHORED LOC <---
        # Cap the 'weight-bearing' lines to 10x the number of actual logic signals.
        # A massive dictionary with 0 signals shrinks to an effective_loc of 10.
        total_signals = branch_hits + linear_hits + args_count
        effective_loc = min(loc, (total_signals + 1) * 10)

        # ---> THE FIX 2: SUB-LINEAR ARGUMENT DAMPENER & BIG-O SCALAR <---
        # Apply a square root to the arguments to prevent combinatorial magnitude explosions
        # on edge-case mega-functions, while preserving the core structural philosophy.
        arg_multiplier = math.sqrt(args_count + 1)

        # Calculate magnitude using the dampened arguments and logic-bounded length
        magnitude = float((branch_hits + 1) * arg_multiplier + (0.05 * effective_loc))

        # ---> THE FIX: LOGIC TOPOLOGY MATH <---
        # Calculate the Control Flow Ratio and the Fractal Fibonacci Angle (Theta)
        total_cf_signals = branch_hits + linear_hits
        control_flow_ratio = (branch_hits / total_cf_signals) if total_cf_signals > 0 else 0.0
        angle = 22.5 + (1.0 - control_flow_ratio) * 67.5

        # ---> NEW: THE DOCUMENTATION TETHER <---
        # Re-attach the human intent using the exact starting line coordinate!
        docstring = self._extract_documentation_tether(start_line, self.primary_lang_id)

        # ---> NEW: LEVEL 3 WIRING (Function Call Chains) <---
        # We scan the block for any word followed by a parenthesis, minus common language keywords.
        invocation_pattern = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
        raw_calls = invocation_pattern.findall(block)
        ignore_keywords = {
            "if",
            "for",
            "while",
            "switch",
            "catch",
            "return",
            "sizeof",
            "typeof",
            "alignof",
            "decltype",
            "using",
            "throw",
            "await",
            "import",
            "require",
            "include",
            "def",
            "function",
            "class",
            "print",
            "println",
            "console",
            "log",
            "echo",
            "printf",
            "fmt",
            "assert",
            "expect",
            "require_once",
            "include_once",
            "cast",
            "isinstance",
            "issubclass",
            "hasattr",
            "getattr",
            "setattr",
            "delattr",
            "len",
            "max",
            "min",
            "range",
            "xrange",
            "enumerate",
            "zip",
            "map",
            "filter",
            "list",
            "dict",
            "set",
            "tuple",
            "bool",
            "int",
            "float",
            "str",
            "bytes",
            "bytearray",
            "memoryview",
            "super",
            "try",
            "except",
            "finally",
            "String",
            "Array",
            "Object",
            "Number",
            "Boolean",
        }
        # Deduplicate and filter (excluding the function calling itself recursively)
        calls_out = list({c for c in raw_calls if c not in ignore_keywords and c != name})[:20]

        sat: FunctionNode = {
            "name": name,
            "calls_out_to": calls_out,
            "texture": texture_str,
            "type_id": texture_str,
            "loc": loc,
            "branch_count": branch_hits,
            "branch": branch_hits,
            "args": args_count,
            "args_count": args_count,
            "docstring": docstring,
            "logic_angle": round(angle, 2),
            "angle": round(angle, 2),
            "control_flow_ratio": round(control_flow_ratio, 3),
            "cf_ratio": round(control_flow_ratio, 3),
            "magnitude": round(magnitude, 1),
            "mag": round(magnitude, 1),
            "impact": round(magnitude, 1),
            "start_line": start_line,
            "end_line": end_line,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "hit_vector": hit_vector,
            "keyword_density": round(keyword_density, 3),
            "coding_loc": coding_loc,
            "token_mass": get_token_mass(block),
        }
        return sat, magnitude

    def _extract_name(self, raw_match: str) -> str:
        """
        Heuristic Token Normalizer.
        Safely extracts the functional identifier (function, class, or method name) from a raw
        regex capture block by isolating the last valid alphanumeric token before parameter boundaries.
        """
        match_strip = raw_match.strip()

        if match_strip.startswith('@"'):
            return match_strip

        # 1.2 Python Decorator Stripping
        if "@" in match_strip and "def " in match_strip:
            match_strip = re.sub(r"(?:@[\w.]+(?:\([^)]*\))?\s+)+", "", match_strip)

        # 1. Objective-C Message Passing Normalization
        if match_strip.startswith("-") or match_strip.startswith("+"):
            clean_objc = re.sub(r"^[-+]\s*(?:\([^)]+\))?\s*", "", match_strip)
            clean_objc = clean_objc.split(":")[0].split("(")[0].split("{")[0].strip()
            words = [w for w in re.findall(r"[a-zA-Z0-9_.-]+", clean_objc) if w.strip("_-")]
            return words[0] if words else "Unknown_Block"

        # --- 1.5 Overloaded Operator Extraction (C++) ---
        # Safely extracts overloaded C++ operators before standard token truncation destroys the symbols.
        if "operator" in match_strip:
            # BUG FIX (#1263): this used to match just the bare `operator...`
            # token, discarding any class qualifier that came before it --
            # `Array::Iterator::operator*` collapsed to `operator*`, silently
            # colliding every same-symbol operator overload across every
            # class in a file into one function_data row. func_start's own
            # regex has supported capturing the qualified form since #813/
            # #821 (`TargetClass::operator=`); this normalizer just never
            # kept up, so the qualifier was captured then thrown away here.
            # Group 1 now grabs the optional `(Ident::)+` chain immediately
            # before the `operator` keyword and it's prefixed back on below.
            op_match = re.search(
                r"((?:[a-zA-Z_]\w*::)*)\b(operator\s*(?:\[\s*\]|\(\s*\)|(?:::)?[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*(?:\s*\*+)?|[^a-zA-Z0-9_\s({]+))",
                match_strip,
            )
            if op_match:
                qualifier = op_match.group(1)
                op_str = op_match.group(2).strip()
                # If it's a symbolic operator (<<, ==, ++, ()), remove all spaces: 'operator <<' -> 'operator<<'
                if not re.search(r"[a-zA-Z]", op_str[8:]):
                    return qualifier + re.sub(r"\s+", "", op_str)
                else:  # It's a type cast like 'operator int', ensure single spacing standardization
                    return qualifier + re.sub(r"\s+", " ", op_str)

        # 2. C-Macro Signature Normalization
        clean = re.sub(r"\b(?:ARGS\d+|NOARGS)\b", "", raw_match)

        # ---> 2.5 Test Framework Signature Extraction <---
        # Extracts the actual test name from C++ testing frameworks (BOOST_AUTO_TEST_CASE or GTest's TEST)
        # preventing the engine from logging the macro name itself.
        macro_match = re.search(
            r"(?:BOOST_[A-Z_]+|TEST|TEST_F|TEST_CASE)\s*\(\s*([a-zA-Z0-9_]+)",
            match_strip,
        )
        if macro_match:
            return macro_match.group(1)

        # 3. Standard Token Truncation
        if "$(" in clean:
            # Variable Interpolation Preservation (Makefiles): Do not split variable names by parenthesis
            clean = clean.split(":")[0].strip()
        else:
            # ---> Namespace Resolution Preservation (C++/PHP) <---
            # DEFENSIVE ARCHITECTURE: Rather than utilizing expensive regex lookaheads to ignore
            # double-colons (::) while splitting on single colons (:) for type hints, we utilize
            # a high-speed O(N) string replacement to temporarily mask the namespace operator.
            clean = clean.replace("::", "__NAMESPACE_SCOPE__")

            # BUG FIX (2026-08-21, tri-comparison-ledger-sweep follow-up): a Cython Tempita
            # codegen placeholder in a cdef return type (`cdef {{memviewslice_name}}
            # *get_slice_from_memview(...)`, cython/MemoryView.pyx) isn't a real body-opening
            # brace, but the split("{") truncation below can't tell the difference -- it cut
            # the match down to just "cdef ", discarding the real name entirely (recorded as
            # the bogus function "cdef"). Strip the placeholder first so its own `{{`/`}}`
            # never reaches the brace-truncation step.
            clean = re.sub(r"\{\{[ \t]*[A-Za-z_]\w*[ \t]*\}\}", "", clean)

            # Truncate at parameter lists, body openings, or return type hints
            clean = clean.split("(")[0].split("{")[0].split(":")[0].strip()

            # Restore the namespace operator
            clean = clean.replace("__NAMESPACE_SCOPE__", "::")

        # Allow standard characters, plus Makefiles ($/%), and Scopes (:)
        # BUG FIX (#1263): `~` (C++/destructor marker) was missing from this
        # charset, so it acted as an unintended word-boundary -- a qualified
        # destructor like `EditorNode::~EditorNode` split into two tokens at
        # the tilde and `words[-1]` kept only the trailing `EditorNode`,
        # silently discarding the tilde and colliding the destructor's
        # function_data row with its own constructor's (`EditorNode::
        # EditorNode`). Adding it here keeps `~EditorNode`/`::~EditorNode`
        # intact as part of the same token as the class-name suffix.
        # BUG FIX (#1565): `'` (Haskell's idiomatic trailing-apostrophe/"prime"
        # naming convention, e.g. `convertWithOpts'`) was also missing --
        # func_start's own regex already captures the trailing prime intact,
        # but this token-extraction pass silently truncated it right back off,
        # so a primed function collided with (and got recorded under) its
        # unprimed sibling's name.
        # BUG FIX: `[` and `]` (TypeScript's computed properties like `[Symbol.asyncIterator]`)
        # were missing, causing them to be extracted as `Symbol.asyncIterator`, misaligning
        # with AST engines.
        words = [w for w in re.findall(r"[a-zA-Z0-9_./%$():~'\-\[\]]+", clean) if w.strip("_-:")]

        return words[-1] if words else "Unknown_Block"

    def _classify_function(self, name: str, block: str, rules: dict[str, Any]) -> str:
        tag_match = re.search(r"[\@](?:type|gal_type)[:\s]+(\w+)", block, re.IGNORECASE)
        if tag_match:
            return tag_match.group(1).lower()

        name_lower = name.lower()
        if any(v in name_lower for v in ["get", "fetch", "load", "read", "query", "select"]):
            return "io"
        if any(v in name_lower for v in ["set", "write", "save", "update", "delete", "post", "send", "put"]):
            return "mutation"
        if any(v in name_lower for v in ["on", "handle", "click", "submit", "route", "rupt", "task"]):
            return "event"
        if any(
            v in name_lower
            for v in [
                "calc",
                "compute",
                "parse",
                "transform",
                "map",
                "filter",
                "reduce",
                "tcf",
                "ccs",
            ]
        ):
            return "logic"
        if any(v in name_lower for v in ["is", "has", "validate", "check", "ensure"]):
            return "check"
        if any(v in name_lower for v in ["test", "assert", "mock", "stub"]):
            return "verification"

        danger_pattern = rules.get("high_risk_execution")
        io_pattern = rules.get("io")

        if danger_pattern and hasattr(danger_pattern, "search") and danger_pattern.search(block):
            return "high_risk_execution"
        if io_pattern and hasattr(io_pattern, "search") and io_pattern.search(block):
            return "io"

        return "standard"
