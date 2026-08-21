#!/usr/bin/env python3
"""
Tree-sitter Accuracy Audit

Baseline-gated regression check for GitGalaxy's own structural-signature
extraction accuracy, measured against tree-sitter as ground truth.
Generalizes the methodology from `ast_accuracy_audit.py` to support multiple
languages via `--lang <name>`.

USAGE
    python tests/tools/tree_sitter_accuracy_audit.py --lang javascript
    python tests/tools/tree_sitter_accuracy_audit.py --lang javascript --ci
    python tests/tools/tree_sitter_accuracy_audit.py --lang javascript --regenerate
        Also refreshes the --summary-table below in the same run (it's a pure
        derivation from committed baselines, so this is free) -- no separate
        manual --summary-table step needed to keep CI's "summary table matches
        committed baselines" check passing.
    python tests/tools/tree_sitter_accuracy_audit.py --all --ci
        Runs --ci for every language that has a committed baseline file
        (tests/tree_sitter_accuracy_baseline_<lang>.json), not just one --lang.
        This is what the tree-sitter-accuracy-audit CI workflow runs.
    python tests/tools/tree_sitter_accuracy_audit.py --summary-table
        Regenerates the Markdown table between the
        <!-- TREE_SITTER_ACCURACY_TABLE:BEGIN/END --> markers in
        gitgalaxy/standards/language_standards.py's module docstring from the
        COMMITTED baselines (no live scan, no corpus needed). Languages with
        no committed baseline are simply absent from the table -- it never
        fabricates a row.
    python tests/tools/tree_sitter_accuracy_audit.py --history
        Live-measures every baselined language and appends one row each to
        docs/self_scan/tree_sitter_accuracy_history.csv (gitignored nowhere on
        purpose -- unlike the self-scan DB, this is meant to accumulate across
        runs so it can be graphed over time). Never touches the gating
        baseline files -- only --regenerate does that, and only per language.
        Adaptive: if the fresh measurement is identical (every raw count, every
        language) to the most recently recorded batch, nothing is appended --
        prints a message and exits 0 instead of manufacturing a duplicate row.
        This is what lets the CI workflow's chart/CSV/PR stay a no-op on a push
        that touched a trigger path without actually moving any language's
        measured accuracy (see _batch_matches_measured). Also measures every
        gg_only language (see _gg_only_langs) -- languages GitGalaxy extracts
        functions from but that have no NODE_MAPS entry at all, via
        measure_gg_only() instead of measure() -- so the chart can show a real
        GitGalaxy count for them (tree-sitter side permanently n/a) instead of
        omitting them entirely. A gg_only language with no language-crucible
        corpus yet (e.g. `ada`) gets a stub row (gg_only_data_available=0, every
        count 0) rather than crashing the run -- fills in whenever the corpus
        catches up, no code change needed here.
    python tests/tools/tree_sitter_accuracy_audit.py --chart
        Renders the most recent --history run (the batch sharing the latest
        timestamp_utc in the CSV) as docs/self_scan/tree_sitter_accuracy_chart.svg
        -- a small-multiples bar chart, five independent metric panels (func
        recall/precision, class recall/precision, args exact-match). #1849: each
        language now renders as TWO stacked bars per panel -- GitGalaxy on top,
        tree-sitter's own raw reading on the bottom, both scored against the same
        reconciled ground truth (see measure()'s raw_ts_funcs/raw_ts_classes
        comment for what that can and can't show yet). Rows share ONE alphabetical
        language order across all five panels, printed once in a shared label
        column, so a single language's numbers can be read straight across every
        column. Whenever the two bars in a cell actually differ, the cell gets an
        amber outline plus a "G"/"T" badge for whichever tool scored higher there.
        Bar fill is a red(low)->blue(high) hue-sweep keyed to that bar's OWN value.
        gg_only languages (see --history above) render a plain gray found-count
        bar instead of a scored ratio, tree-sitter side always n/a.
        Includes python via NODE_MAPS like every other language now (see that
        entry's own comment: this is for --chart/--history uniformity only --
        tests/ast_accuracy_audit.py's stdlib `ast` ground truth remains the actual
        CI gate for python's accuracy, unchanged). Reads the CSV only -- does not
        itself run a live scan, so run --history first for fresh numbers.
    python tests/tools/tree_sitter_accuracy_audit.py --blurbs
        Prints Markdown bullets describing every (language, metric) pair whose value moved
        by >=1.0 percentage points between the two most recent --history batches in the CSV
        (e.g. "- **javascript** func precision improved 12.3pp (61.2% -> 73.5%)"), sorted
        biggest move first. Reads the CSV only, no live scan. Feeds the "Notable changes"
        section of the tree-sitter-accuracy-history workflow's auto-merged PR body -- not
        written to a committed file on purpose, this is PR-body content, not a standalone
        artifact.

CORPUS
    Unlike ast_accuracy_audit.py which pins this repo's own code via git archive,
    this tool uses the external `language-crucible` corpus. By default, it expects
    it checked out as a sibling directory `../language-crucible`, or set via
    `LANGUAGE_CRUCIBLE_PATH` env var. NOTE: "sibling directory" is relative to
    THIS repo's own checkout root, not a git worktree's -- running from a worktree
    (e.g. `gitgalaxy-worktrees/some-branch/`) needs `LANGUAGE_CRUCIBLE_PATH` set
    explicitly, same pre-existing limitation `crucible_check.py` already has.

BASELINE
    tests/tree_sitter_accuracy_baseline_<lang>.json, one file per language (not
    a combined JSON) so a PR touching one language's baseline shows a small diff.
    Same tracked-metric split as ast_accuracy_audit.py:
      - found_functions / found_classes: higher is better (recall floor).
      - extra_functions / extra_classes: lower is better (precision ceiling -- a
        name GitGalaxy reports that tree-sitter has no record of at all).
      - args_exact_match: higher is better (of the functions GitGalaxy DID find,
        how many also got the real parameter count right).
      - files_scanned / real_functions / real_classes / args_comparable are NOT
        regression-gated -- they're tree-sitter's own ground-truth counts against
        the corpus, which should be stable given a fixed corpus checkout. If one
        of these drifts on a PR that didn't touch the corpus, the local
        `language-crucible` checkout is probably not at the expected pinned tag
        (see `crucible_check.py`'s own corpus pin) rather than a real finding.

SCOPE & LIMITATIONS
    A function is "found" by name match WITHIN ITS FILE. Same-named occurrences
    (property getter/setter pairs, `__init__`/`__call__` across different
    classes, a module-level helper and a same-named prototype method) are no
    longer collapsed onto one slot per name (#1526) -- each occurrence's real
    `start_line` (persisted on `function_data` since #1526's companion recorder
    change) is used to pair same-named real/found occurrences by position via
    `_align_occurrences_by_line`, not by "whichever happened to be walked/
    queried first or last". This isn't full scope-tracking (still no notion of
    "which class" beyond the line-proximity signal), so a genuinely ambiguous
    same-line-order swap is theoretically still possible, but the common cases
    -- `jquery/event.js`'s two same-named `on` functions (a module-level 6-arg
    helper and a 4-arg `.on()` prototype method), numpy's repeated
    `shape`/`mask`/`recordmask` property pairs, cython's 14 separate
    `__init__`s in one file -- now pair up correctly instead of manufacturing a
    false args-count mismatch.

    Ground truth (tree-sitter) is not infallible either: the plain `javascript`
    grammar cannot fully parse Flow-typed syntax (return-type/param-type
    annotations like `function f(x: ?any): ?Iterator<any> {`), which several
    `language-crucible/data/javascript/react/*.js` files use. A Flow-typed
    function that tree-sitter fails to recognize as a real `function_declaration`
    is invisible to `real_functions`, so if GitGalaxy's own (grammar-agnostic,
    regex-based) `func_start` still correctly matches it, that function gets
    counted as a false "extra" (phantom) against GitGalaxy here -- an artifact of
    this measurement's ground-truth parser, not necessarily a GitGalaxy
    precision defect. Confirmed example: `react/ReactSymbols.js::getIteratorFn`.
    Neither of these is fixable without deeper per-file disambiguation (real
    scope tracking) or a Flow-aware grammar -- noted here so the recall/
    precision numbers aren't read as more precise than the methodology actually
    supports, same spirit as ast_accuracy_audit.py's own SCOPE section.

    python's `real_functions` undercounts inside `.pyx` (Cython) files for the same class of
    reason: tree-sitter-python is a pure-Python grammar with no notion of Cython's `cdef class`
    syntax, so it loses track of scope across `cdef class` boundaries and doesn't reliably re-emit
    a `function_definition` for every same-named method across multiple `cdef class` blocks (a
    plain GitGalaxy `def`/`cdef` regex match has no such scope confusion). Confirmed via
    `language-crucible/data/python/cython/MemoryView.pyx`: 4 separate `cdef class` blocks
    (`array`, `Enum`, `memoryview`, `_memoryviewslice`) each define their own `__dealloc__`,
    `__cinit__`, etc. -- GitGalaxy finds all of them; tree-sitter's ground truth is short by one or
    more per name, so #1526's occurrence pairing correctly reports those extra GitGalaxy-found
    occurrences as unmatched ("extra") once no longer masked by the old one-slot-per-name collapse.
    Same "ground-truth parser gap, not a GitGalaxy precision defect" shape as the Flow-typed JS
    note above.

    Same cause, a different Cython file kind (2026-08-21): `language-crucible/data/python/
    cython/MemoryView.pxd` (a `.pxd` declaration file, not `.pyx`) has 16 bare top-level `cdef`
    function declarations with no enclosing `cdef class` at all (`array_cwrapper`,
    `memoryview_check`, `get_memview`, etc.) -- tree-sitter-python doesn't recognize a
    `cdef`-prefixed declaration as a `function_definition` under any circumstance, so all 16 are
    invisible to `real_functions` while GitGalaxy's regex correctly finds every one. Surfaces as
    `extra_functions: 0 -> 16` in the baseline check; reviewed and re-blessed, not a real
    regression -- see `docs/why_gitgalaxy_beats_ast_here.md` Claim 2's third instance.

    matlab and shell make heavy use of GitGalaxy's own synthetic `Anonymous_Block`/
    `__global_context__` placeholder function-like records -- `detector.py`'s fallback names for
    top-level control-flow blocks (`if`/`for`/`while`/...) in script-style files that have no
    enclosing named function at all (a MATLAB `.m` script, or any shell script's top-level body).
    These exist so the complexity/risk-scoring graph has something to attach top-level logic to;
    they were never meant to correspond to a real named function, and no real source language can
    produce a grammar node with either literal name, so tree-sitter's ground truth structurally can
    never contain them. `_SYNTHETIC_GG_FUNC_NAMES` excludes both from the comparison entirely (found
    while regenerating the matlab/shell baselines post-#1526's pairing fix: left uncorrected,
    `eeglab/eeglab.m` alone has 57 `Anonymous_Block` rows plus 1 `__global_context__`, all newly
    counted as individually "extra" once same-named rows stopped collapsing onto one dict slot,
    which read as a wildly misleading 18.0%/10.7% func precision for matlab/shell in the summary
    table before the exclusion) -- see that constant's own comment for the full rationale and why
    "Main" is deliberately not also excluded.

    C/C++'s `function_definition` has no top-level "name" field -- see
    `_unwrap_c_style_declarator`'s docstring for the general fix (#1265). One remaining gap in
    that unwrap: C++ user-defined conversion operators (`operator int() const { ... }`) use a
    distinct `operator_cast` declarator node with no identifier-shaped child at all (the "name" is
    the return type itself, e.g. "operator int"), so those still resolve to None and are absent
    from `real_functions`/`real_funcs` -- confirmed via `language-crucible/data/cpp/godot/variant.cpp`
    (Godot's `Variant` class defines ~40 of these). A small, rare-enough fraction of real-world C++
    (56/1491 function_definition nodes, ~3.8%, in this corpus) that it's noted rather than chased.

    Rust's `extra_functions` count (#1311, investigated after #1302/#1266 broadened prism.py's
    comment shield and exposed it) is dominated by a DIFFERENT ground-truth gap, not a GitGalaxy
    regex-precision defect: real `fn` items whose text sits inside a `macro_rules!` definition's
    template body, or inside a function-like macro invocation's braces (`quote! { ... }`, or a
    custom `cfg_*! { ... }` gating wrapper as used throughout tokio). tree-sitter-rust parses both
    shapes as one opaque `macro_rules` / `macro_invocation` node wrapping an unstructured
    `token_tree` -- it does not (cannot, without actual macro expansion) descend into that token
    tree to emit nested `function_item` nodes, so real_functions never counts them. GitGalaxy's
    func_start regex has no concept of macro-brace nesting and correctly matches the `fn` text
    regardless, which is arguably the more useful answer for a structural-signature tool (the
    function is genuinely there in the source, once macro-expanded) -- so this reads as a
    measurement-tool blind spot rather than something to chase by teaching func_start to detect
    macro context. Every one of the 69 rust `extra_functions` samples present at investigation
    time traced to one of these two macro shapes (bevy/serde/syn/tokio/wasmtime in
    language-crucible), after the `function_signature_item` NODE_MAPS fix above already accounted
    for the two genuinely-fixable bodyless-trait-method cases in that same sample.

    #1319 (fixing rust's real recall gap for bodyless trait-method signatures --
    `detector.py`'s `_slice_by_braces` previously dropped every `func_start` match whose window
    never found a `{`, silently treating a legitimate `;`-terminated signature the same as a
    non-match) raised `extra_functions` further (67 -> 108), not via a new GitGalaxy defect but by
    exposing more instances of this SAME macro-body blind spot: `;`-terminated `fn` signatures were
    already invisible pre-#1319 regardless of whether they sat in real code or macro-body text, so
    only the ones in real code became newly-visible (fixed by #1319) while the ones inside
    `macro_rules!`/custom-DSL macro invocations (e.g. wasmtime's `br_if_imm! { fn br_if_xeq32_i8(...)
    = BrIfXeq32I8 / == / get_i32; ... }`, a hand-rolled macro DSL that reuses rust's own `fn ... ;`
    syntax as a per-entry template, not a real trait signature) became newly "extra" here for the
    exact same already-documented reason. Confirmed: every one of the 41 net new `extra_functions`
    entries traces to one of the two macro shapes above (mostly `wasmtime_pulley_interp.rs`'s
    `br_if_imm!` table, plus one `macro_rules!`-nested serde case) -- not a new, third blind-spot
    shape.

    Also #1319: `_get_param_count`'s counted child-type set (identifier/parameter_declaration/etc,
    designed around C-family and JS-family grammars) never included rust's own parameter child
    types (`parameter`, `self_parameter`) -- rust's args_exact_match was measuring 0 real params for
    every single function regardless of its actual signature, silently passing only by coincidence
    on genuinely zero-arg functions (~9% baseline). Fixed by extending the counted set for rust's
    two `func_node_types` specifically (gated by node type, not applied to any other NODE_MAPS
    language) -- args_exact_match went 133 -> 1446 out of 1489 comparable as a result, unrelated to
    the `extra_functions` blind spot above but discovered by the same investigation.

    #1339: the #1319 rust fix's own comment claimed its two added node types were rust-specific --
    that turned out to be wrong for `parameter` (also csharp's and scala's real per-param node
    type) and, separately, 8 more NODE_MAPS languages (java, apex, typescript, php, ruby, go,
    swift, dart, matlab) each had their OWN never-audited gap in this same whitelist, from a
    missing node type name (java/apex/typescript/php/ruby/go) to a missing field entirely
    (swift/dart/matlab, each needing its own no-field-shape branch same as kotlin/objc/powershell
    already had). All 11 languages showed the identical false-"real=0 regardless of actual
    signature" symptom #1319 fixed for rust. See `_get_param_count`'s own inline comments for the
    per-language node-type breakdown; net effect was args_exact_match roughly doubling to
    quadrupling for most of the 11 (see #1339 for the full before/after table), with zero
    regressions on any other NODE_MAPS language.

    #1518/#1519: shell and perl-traditional-style are architecturally different from every
    other language this tool measures -- Bash functions (`foo() { ... }`) and traditional Perl
    subs (`sub foo { ... }`) have NO formal parameter-list syntax at all, permanently, by
    grammar. A function's own `()` in bash are always empty; Perl's traditional style has no
    parens on the `sub` line whatsoever. Args instead arrive via body-level idioms: bash reads
    $1/$2/.../"$@" wherever they're referenced; Perl reads `my (...) = @_;` and/or `shift`
    calls. `_get_param_count`'s original branches only ever checked the DECLARATION for a
    formal signature field, found nothing (correctly -- there genuinely is none), and reported
    real=0 for nearly every function regardless of true arity -- args_exact_match measured a
    misleading 0% (shell) / 14.6% (perl), which reads as "GitGalaxy's args regex is badly
    broken" when the actual defect was in the MEASUREMENT: comparing GitGalaxy's body-aware
    heuristic against a ground truth that only ever looked at the (nonexistent) declaration.
    `_count_shell_real_positional_max`/`_count_perl_real_args` fixed this by walking the same
    body text tree-sitter already parses just fine, for the exact same idioms GitGalaxy's own
    regex reads -- a fair, apples-to-apples comparison instead of an empty-signature strawman.
    Result: shell 0% -> 100% (3/3), perl 14.6% -> 82.1% (769/937). This is also why
    `docs/why_gitgalaxy_beats_ast_here.md` exists: for this one specific signal, in these
    specific no-formal-signature circumstances, a plain AST/tree-sitter-only tool has nothing
    to read at the declaration site and can only ever report 0 -- correct, but useless for
    coupling/complexity scoring. GitGalaxy's regex-based body scan is the more informative
    measurement here, not a lower-precision tradeoff; see that doc for the full writeup and
    where this fits (and doesn't) alongside the "AST usually wins on precision" framing in
    README.md's "One Graph, Not Five Separate Tools" section.

    #1427/#1567: csharp's `extra_functions` count included real, correctly-found GitGalaxy
    matches in `roslyn/LanguageParser.cs` misclassified as false positives because
    tree-sitter-c-sharp's installed grammar version fails to parse a C# 11 list-pattern +
    property-pattern construct at line 5198 (`modifiers is [.., SyntaxToken { Kind: ... }
    scopedKeyword]`) -- the resulting `ERROR` node cascade leaves ground truth with zero
    `real_functions` for the rest of the file (lines 5198-14680), not just the 3 names #1427
    originally found and hand-excluded (that attribution also blamed the wrong construct -- a
    `ref struct` 9,000+ lines later that parses cleanly on its own; see #1567 and
    `docs/why_gitgalaxy_beats_ast_here.md`'s Claim 3 for the full correction). Replaced the
    3-name allowlist with `_find_trailing_error_cascade_start`, a general, language-agnostic
    detector for "one bad construct swallows the rest of the file" cascades, rather than
    re-diagnosing and re-hand-listing names every time the pinned corpus file changes. This is
    Claim 3: a grammar parse-error cascade corrupting ground truth for syntactically-unrelated
    real code, distinct from Claim 2's "grammar has no concept of this dialect at all".

    cpp's found_functions dropped 1392 -> 1296 (and c's 1713 -> 1702) on 2026-08-21 for the
    opposite reason most entries in this section exist: not a new GitGalaxy defect, but
    GitGalaxy correctly FIXING a false-positive class it used to share with tree-sitter's own
    parse. A macro invocation shaped like a function call immediately followed by a real `{`
    body (`OPCODE(OPCODE_OPERATOR) { ... }`, a bytecode-dispatch macro in
    godot/gdscript_vm.cpp -- `#define OPCODE(m_op) case m_op:`; cpython/typeobject.c's
    `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/`SLOT1BINFULL` boilerplate generators) is syntactically
    indistinguishable from a real function definition to BOTH a regex with no macro-table
    memory and tree-sitter's own C/C++ grammar -- confirmed via a direct universal-ctags probe
    that ctags itself is not fooled, because it already tracks which identifiers were
    `#define`'d and never re-tags an invocation of a known macro. `detector.py`'s
    `_slice_by_braces` now does the same (scans each file for `#define NAME(...)` and excludes
    any match on a known macro name), which is a real correctness improvement -- but
    tree-sitter's own grammar was never fixed to match (out of scope for this repo), so
    `real_functions` (built from tree-sitter's parse) still wrongly counts every one of these
    macro invocations as "real". GitGalaxy no longer agrees with that wrong ground truth, which
    reads as a recall regression in THIS tool's narrow methodology even though it's a genuine
    improvement in absolute correctness -- confirmed via the separate, no-privileged-ground-truth
    3-way comparison against ctags too (see `docs/self_scan/tri_comparison_README.md` and
    `docs/language_status/cpp.md`/`c.md`'s own §9, where this is the finding that moved both
    languages' Func Precision badge from ctags to GitGalaxy). Baseline regenerated and reviewed
    rather than treated as a real regression, same "ground truth can be wrong" precedent as
    every other entry in this section.
"""

import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple, Optional

import tree_sitter_language_pack

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CRUCIBLE_PATH = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))


NODE_MAPS = {
    "javascript": {
        "ts_lang": "javascript",
        "func_node_types": {
            "function_declaration",
            "generator_function_declaration",
            "method_definition",
            "arrow_function",
            "function_expression",
        },
        "class_node_types": {"class_declaration"},
    },
    "ruby": {
        "ts_lang": "ruby",
        "func_node_types": {"method", "singleton_method"},
        # #1295: "module" represents `module Foo ... end`, a real class-like entity
        # with a name field that GitGalaxy's own class_start regex intentionally matches,
        # but was previously invisible to real_classes here (confirmed via rails corpus
        # examples like ActionDispatch / AbstractController).
        "class_node_types": {"class", "singleton_class", "module"},
    },
    "php": {
        "ts_lang": "php",
        "func_node_types": {
            "function_definition",
            "method_declaration",
            "anonymous_function",
            "arrow_function",
        },
        "class_node_types": {
            "class_declaration",
            "anonymous_class",
            "interface_declaration",
            "trait_declaration",
            "enum_declaration",
        },
    },
    "perl": {
        "ts_lang": "perl",
        "func_node_types": {
            "subroutine_declaration_statement",
            "anonymous_subroutine_expression",
            "method_declaration_statement",
            "anonymous_method_expression",
        },
        # #1295: "class_statement" alone only targets Perl 5.38+'s new `class Foo {...}`
        # syntax, which real-world corpus code (bugzilla, exiftool) essentially never uses --
        # the traditional `package Foo::Bar;` idiom is Perl's dominant OOP/namespace mechanism
        # and is what perl's own class_start regex actually matches (`package|class|role`).
        # "package_statement" is a real, cleanly-named tree-sitter node type (its "name" field
        # resolves directly, e.g. "Image::ExifTool") that was invisible to real_classes here.
        "class_node_types": {"class_statement", "package_statement"},
    },
    "lua": {
        "ts_lang": "lua",
        "func_node_types": {"function_declaration", "function_definition"},
        "class_node_types": set(),
    },
    "shell": {
        "ts_lang": "bash",
        "func_node_types": {"function_definition"},
        "class_node_types": set(),
    },
    "c": {
        "ts_lang": "c",
        "func_node_types": {"function_definition"},
        "class_node_types": {"struct_specifier", "union_specifier", "enum_specifier"},
    },
    "cpp": {
        "ts_lang": "cpp",
        # "template_function" was here before #1265 -- it's WRONG, that node type is a template
        # *instantiation expression* (e.g. `cast_to<Window>`, `const_cast<Node*>` used as a call/
        # cast target), not a function definition. Including it inflated real_functions with
        # phantom "functions" that are actually casts and calls. See _unwrap_c_style_declarator
        # for how function_definition's real (nested, field-less) name is now extracted.
        "func_node_types": {"function_definition"},
        "class_node_types": {"class_specifier", "struct_specifier", "enum_specifier", "union_specifier"},
    },
    "csharp": {
        "ts_lang": "csharp",
        # #1314: constructor_declaration was missing here -- a real, named node
        # (tree-sitter-c-sharp gives constructors their own node type, distinct from
        # method_declaration) that GitGalaxy's func_start regex already correctly matches
        # (its "Constructors" args branch and the func_start regex both special-case the
        # no-return-type constructor shape), but was previously invisible to real_functions,
        # so every real constructor scored as a false "extra" here.
        "func_node_types": {"method_declaration", "local_function_statement", "constructor_declaration"},
        # class_node_types was missing enum_declaration -- GitGalaxy's csharp class_start regex
        # deliberately matches `enum` too (same design choice as java's class_node_types, which
        # already includes enum_declaration), so every real enum in the corpus scored as a false
        # "extra" class here. Confirmed via direct breakdown: 11 of LanguageParser.cs's 13
        # "extra_classes" were real enums (AccessorDeclaringKind, NameOptions, Precedence, etc.)
        # that GitGalaxy correctly found but the ground truth didn't count as a class.
        "class_node_types": {"class_declaration", "struct_declaration", "interface_declaration", "enum_declaration"},
    },
    "java": {
        "ts_lang": "java",
        "func_node_types": {"method_declaration", "constructor_declaration"},
        "class_node_types": {"class_declaration", "interface_declaration", "enum_declaration"},
    },
    "go": {
        "ts_lang": "go",
        "func_node_types": {"function_declaration", "method_declaration"},
        "class_node_types": {"type_declaration"},
    },
    "rust": {
        "ts_lang": "rust",
        # #1311: function_signature_item is the tree-sitter-rust node type for a BODYLESS
        # fn (a trait method requirement, e.g. `fn foo(&self) -> i32;`, or a bare `extern`
        # declaration) -- a real, named function with no `{ }` body, distinct from function_item
        # which requires one. Confirmed via language-crucible/data/rust/serde/serde_core_de_mod.rs
        # (IntoDeserializer::into_deserializer, DeError::struct_variant): both are real trait
        # method signatures GitGalaxy's func_start regex correctly matches, but were previously
        # invisible to real_functions here, so they scored as false "extra" (GitGalaxy precision
        # defect) when the actual gap was this tool's ground truth, not GitGalaxy's regex.
        "func_node_types": {"function_item", "function_signature_item"},
        # #1295: "union_item" is tree-sitter-rust's node type for `union Foo { ... }` --
        # distinct from struct_item/enum_item, a real, named class-like entity GitGalaxy's own
        # class_start regex intentionally matches (its comment covers struct/enum/union/trait),
        # but was invisible to real_classes here. Confirmed via wasmtime_pulley_interp.rs
        # (FRegUnion/VRegUnion/XRegUnion, all plain top-level `union` declarations with no
        # macro involvement) -- same ground-truth measurement-gap shape as go/kotlin/objc/zig.
        #
        # `impl_item` deliberately excluded (was present here since this NODE_MAPS's original
        # commit, predating #1295, and never revisited): tree-sitter-rust's `impl_item` has no
        # "name" field at all -- the implemented type/trait sit behind separate "type"/"trait"
        # fields -- so `_get_node_name` returned None for every impl block and `if name:
        # real_classes.add(name)` silently dropped all of them, making rust's class recall/
        # precision read a misleading 100%/100% across this tool's entire history (confirmed by
        # temporarily adding real name extraction and re-running against language-crucible:
        # real_classes 270->451, found_classes stayed at 270 since GitGalaxy's own class_start
        # regex only ever matches struct/enum/union/trait -- never impl -- so true recall would
        # read ~59.9%, not a bug fix but a brand new ~40% gap). This is NOT the same shape as
        # #1265's C fix (GitGalaxy's C func_start regex already worked, the audit just couldn't
        # see it) -- GitGalaxy's rust class_start was deliberately authored to track only new-
        # entity declarations ("Object / Entity Declarations"), and an impl block doesn't declare
        # a new entity, it adds methods to one already declared. Same scope-mismatch category as
        # css/html being permanently excluded from class measurement in #1295 (Class 5, mirrored)
        # -- documented and excluded here rather than force-counted. Removing it changes nothing
        # about today's numbers (it was already contributing zero); this just makes the NODE_MAPS
        # config honestly reflect what's measured instead of silently dead-ending on every scan.
        "class_node_types": {"struct_item", "trait_item", "enum_item", "union_item"},
    },
    "scala": {
        "ts_lang": "scala",
        "func_node_types": {"function_definition", "function_declaration"},
        "class_node_types": {"class_definition", "trait_definition", "object_definition"},
    },
    "haskell": {
        "ts_lang": "haskell",
        # #1566: point-free definitions (`trim :: T.Text -> T.Text; trim = T.dropAround isWS`,
        # no explicit argument patterns) parse as a top-level "bind" node, not "function" -- a
        # real function per its type signature, but structurally invisible here before this.
        # Gated in _get_node_name/_get_param_count (search "#1566" there) on having a paired
        # arrow-typed "signature" sibling, so a genuine non-function value binding (`x = 5`,
        # no arrow in its type, or no type signature at all) still isn't counted -- same
        # reasoning GitGalaxy's own regex already applies via #1312.
        "func_node_types": {"function", "bind"},
        # #1295: haskell's data/newtype/type declarations get their own distinct node types
        # (data_type, newtype, type_synomym, data_family, type_family) separate from class.
        # This is a real, named class-like entity GitGalaxy's own class_start regex
        # intentionally matches (its comment says "Object / Entity Declarations" and the regex
        # explicitly matches `data(?:\s+family)?|newtype|class|type(?:\s+family)?`). This was
        # invisible to real_classes here pre-fix, causing pandoc's `data PandocOutput`/`data Filter`
        # etc. to flag as false "extra". Note the spelling `type_synomym` is tree-sitter-haskell's own typo.
        "class_node_types": {
            "class_decl",
            "class",
            "data_type",
            "newtype",
            "type_synomym",
            "data_family",
            "type_family",
        },
    },
    "kotlin": {
        "ts_lang": "kotlin",
        # #1313: both node types are correctly named here, but neither exposes a "name" FIELD in
        # this grammar -- the identifier is a plainly-typed `simple_identifier`/`type_identifier`
        # child instead, so every match silently resolved to None pre-fix. See _get_node_name's
        # kotlin branch.
        "func_node_types": {"function_declaration", "anonymous_function"},
        # #1295: kotlin's `object` declarations (including `actual`/`expect` multiplatform
        # variants) get their own `object_declaration` node type, distinct from
        # `class_declaration` -- a real, named class-like entity GitGalaxy's own class_start
        # regex intentionally matches (`class|interface|object|enum class`), invisible to
        # real_classes here pre-fix (okhttp's `object OkHttp` singletons).
        "class_node_types": {"class_declaration", "object_declaration"},
    },
    "swift": {
        "ts_lang": "swift",
        # #1311: tree-sitter-swift gives initializers their own `init_declaration` node type,
        # distinct from `function_declaration` -- a real, named ("init") method that GitGalaxy's
        # func_start regex correctly matches, but was previously invisible to real_functions here,
        # so every `init` scored as a false "extra" (all 5 language-crucible/data/swift/alamofire
        # samples at the time of investigation were plain `init` methods, not a GitGalaxy defect).
        "func_node_types": {"function_declaration", "init_declaration"},
        # #1295: tree-sitter-swift gives protocols their own `protocol_declaration` node type,
        # distinct from `class_declaration` -- a real, named class-like entity that GitGalaxy's
        # own class_start regex intentionally matches (`class|struct|enum|protocol|actor|
        # extension|macro`), but was invisible to real_classes here (e.g. alamofire's
        # `RequestDelegate` protocol, which has no corresponding `extension RequestDelegate`
        # elsewhere in the corpus to accidentally surface its name via a class_declaration node).
        "class_node_types": {"class_declaration", "protocol_declaration"},
    },
    "dart": {
        "ts_lang": "dart",
        # constructor_signature/constant_constructor_signature/factory_constructor_signature: dart
        # constructors (`Foo()`, `const Foo.raw()`, `factory Foo.create()`) get their own node
        # types, distinct from function_signature/method_signature -- see _get_node_name's dart
        # constructor branch for why they were entirely invisible to real_functions before this.
        # getter_signature/setter_signature/operator_signature: same shape of gap, found later
        # (docs/why_gitgalaxy_beats_ast_here.md Claim 5) -- dart's grammar nests these one level
        # BELOW the generic `method_signature` wrapper (which itself has no "name" field), so a
        # ground truth walk that only recognizes function_signature/method_signature never sees a
        # getter, setter, or operator overload at all, even though GitGalaxy's own func_start regex
        # finds all three uniformly (its `(?:(?:get|set|factory|const)[ \t\n]+)?` prefix and
        # `operator[ \t\n]+[^\s\w]+` alternative treat them exactly like any other method).
        "func_node_types": {
            "function_signature",
            "local_function_declaration",
            "method_signature",
            "constructor_signature",
            "constant_constructor_signature",
            "factory_constructor_signature",
            "getter_signature",
            "setter_signature",
            "operator_signature",
        },
        # #1295: dart's `mixin` declarations get their own `mixin_declaration` node type, and
        # `enum` declarations get `enum_declaration` -- distinct from `class_definition`, real
        # named class-like entities GitGalaxy's own class_start regex intentionally matches,
        # but were invisible to real_classes here (e.g. flutter's `mixin Diagnosticable`).
        "class_node_types": {"class_definition", "mixin_application_class", "mixin_declaration", "enum_declaration"},
    },
    "objective-c": {
        "ts_lang": "objc",
        "func_node_types": {"function_definition", "method_definition", "method_declaration"},
        "class_node_types": {"class_declaration", "class_implementation", "class_interface"},
    },
    "typescript": {
        "ts_lang": "typescript",
        "func_node_types": {
            "function_declaration",
            "function_signature",
            "method_definition",
            "method_signature",
            "arrow_function",
            "function_expression",
            "generator_function",
            "generator_function_declaration",
        },
        # #1338: GitGalaxy's typescript class_start rule is deliberately titled "Object / Entity
        # Declarations" (language_standards.py), not "OOP classes" -- it matches `class|enum|
        # interface` on purpose (and `enum TargetEntity {` is an explicit "valid" test case in
        # tests/extraction/languages/test_typescript.py's CLASS_CASES). This NODE_MAPS entry only
        # counted `class_declaration`/`abstract_class_declaration` as "real classes", so every
        # correctly-matched interface/enum was measured as a false-positive "extra" class -- the
        # same ground-truth-tool-gap shape as #1314's objc `_get_node_name` fix, not a GitGalaxy
        # regex defect. Confirmed via direct breakdown: all 537 baseline `extra_classes` traced
        # to real `interface_declaration` (470) / `enum_declaration` (67) nodes tree-sitter itself
        # parses, zero unexplained false matches. Added both node types here to match what
        # class_start actually measures itself against.
        "class_node_types": {
            "class_declaration",
            "abstract_class_declaration",
            "interface_declaration",
            "enum_declaration",
        },
    },
    "html": {
        "ts_lang": "html",
        "func_node_types": {"script_element", "style_element"},
        "class_node_types": {"element"},
    },
    "css": {
        "ts_lang": "css",
        # #1313: "at_rule" alone (the pre-fix value) is WRONG for this grammar version --
        # @media/@supports/@keyframes each get their OWN dedicated node type
        # (media_statement/supports_statement/keyframes_statement), "at_rule" only covers the
        # generic remainder (@layer, @container, @font-face, @page, @charset, @namespace, ...).
        # GitGalaxy's own func_start rule (language_standards.py) only anchors on
        # @media/@supports/@container/@layer/@keyframes/@-webkit-keyframes -- see
        # _get_node_name's "at_rule" branch, which filters the generic bucket down to just
        # @layer/@container so the other generic at-rules (out of GitGalaxy's declared scope)
        # don't manufacture a false recall gap.
        "func_node_types": {"media_statement", "supports_statement", "keyframes_statement", "at_rule"},
        # #1313: "rule_set" (the pre-fix value) has no name of its own -- GitGalaxy's class_start
        # rule fires per individual class/ID selector token, not per rule_set block, so the real
        # ground-truth entities are the selector nodes themselves. See _get_node_name's
        # class_selector/id_selector branch for how the name (with its "."/"#" prefix, matching
        # GitGalaxy's own captured string) is pulled out of a compound selector.
        "class_node_types": {"class_selector", "id_selector"},
    },
    "powershell": {
        "ts_lang": "powershell",
        "func_node_types": {"function_statement", "class_method_definition"},
        # #1295: "enum_statement" was missing -- powershell's own class_start regex
        # intentionally matches both class and enum declarations (see its comment), but only
        # class_statement was in this set. Resolved via the existing simple_name-child branch
        # in _get_node_name (same shape as class_statement, just a different node type).
        "class_node_types": {"class_statement", "enum_statement"},
    },
    "solidity": {
        "ts_lang": "solidity",
        "func_node_types": {"function_definition", "modifier_definition", "constructor_definition"},
        "class_node_types": {"contract_declaration", "interface_declaration", "library_declaration"},
    },
    "groovy": {
        "ts_lang": "groovy",
        "func_node_types": {"func"},
        "class_node_types": {"generics_class"},
    },
    "zig": {
        "ts_lang": "zig",
        # #1313: "FnProto" is correctly named, but (like kotlin) has no "name" FIELD -- the
        # identifier is a plain `IDENTIFIER` child. "ContainerDecl" (struct/enum/union/opaque) has
        # no name at all of its own -- see _get_zig_container_name's docstring for why the real
        # name lives on an ancestor VarDecl instead.
        "func_node_types": {"FnProto"},
        # #1295: zig's error sets (`const Foo = error{...};`) get their own `ErrorSetDecl` node
        # type, distinct from `ContainerDecl` -- a real class-like entity GitGalaxy's own
        # class_start regex intentionally matches (its comment says so: "Defines structural
        # entities (struct, enum, union, error, opaque)"). Same shape as `_get_zig_container_name`
        # (the real name lives on the enclosing VarDecl, not the ErrorSetDecl itself) so it's
        # dispatched through the same resolver in `_get_node_name`.
        "class_node_types": {"ContainerDecl", "ErrorSetDecl"},
    },
    "apex": {
        "ts_lang": "apex",
        "func_node_types": {"method_declaration"},
        "class_node_types": {"class_declaration"},
    },
    "python": {
        "ts_lang": "python",
        # Not the gating measurement for python's own accuracy -- tests/ast_accuracy_audit.py's
        # stdlib `ast` ground truth is strictly better for this one language and remains the CI
        # gate. This entry exists so python flows through the same --history/--chart pipeline as
        # every other language uniformly, rather than a special one-off merge from a second file.
        "func_node_types": {"function_definition"},
        "class_node_types": {"class_definition"},
    },
    "fortran": {
        "ts_lang": "fortran",
        # The wrapper node types (subroutine/function/module/...) don't reliably form on this
        # real-world (WRF, heavily CPP-preprocessed) corpus -- tree-sitter-fortran falls back to a
        # top-level ERROR node rather than nesting cleanly. The inner *_statement header nodes
        # still get tagged with the real name even under that ERROR recovery, so those are the
        # measured node types here instead -- see _get_node_name's fortran branch.
        "func_node_types": {"subroutine_statement", "function_statement", "program_statement"},
        "class_node_types": {
            "module_statement",
            "derived_type_statement",
            "interface_statement",
            "submodule_statement",
        },
    },
    "makefile": {
        "ts_lang": "make",
        # No class/OOP concept in Make -- matches GitGalaxy's own class_start (None for makefile).
        "func_node_types": {"rule"},
        "class_node_types": set(),
    },
    "matlab": {
        "ts_lang": "matlab",
        "func_node_types": {"function_definition"},
        "class_node_types": {"class_definition"},
    },
    "tcl": {
        "ts_lang": "tcl",
        "func_node_types": {"procedure"},
        # oo::class create/snit::type/itcl::class are indistinguishable from any other command
        # invocation in tree-sitter-tcl's grammar (no dedicated node type carries the class name
        # tree-sitter -- it's buried as an untyped argument), so there's no tree-sitter ground
        # truth to measure GitGalaxy's class_start regex against. Confirmed empty either way: no
        # language-crucible tcl sample actually uses tcl's OOP extensions.
        "class_node_types": set(),
    },
}

# Languages GitGalaxy has a func_start/class_start rule for for AND tree-sitter-language-pack has
# a grammar for, but that are deliberately NOT in NODE_MAPS above -- listed here so the gap reads
# as a decision, not an oversight, the next time someone reconciles this list against
# LANGUAGE_DEFINITIONS:
#   - cobol: tree-sitter-cobol's grammar returns ~100% ERROR nodes on the language-crucible corpus
#     (confirmed on a real-file sample) AND is pathologically slow doing it (one corpus walk spun
#     at 100% CPU for 5+ minutes and was killed) -- both a data-quality and a CI-budget blocker.
#   - dockerfile: GitGalaxy's own func_start/class_start capture the literal instruction keyword
#     ("RUN", "FROM", ...), not a unique per-instance name -- there's nothing for tree-sitter's
#     per-instruction nodes to name-match against under this tool's exact-name methodology.
#   - scheme: homoiconic -- tree-sitter-scheme has no distinct function-definition node type,
#     `(define (name ...))` is just a generic `list`/`symbol` tree. Detecting it needs content-
#     aware walking (inspect a list's first symbol), not simple node-type-set membership, which
#     is a real extension to this tool's architecture, not a NODE_MAPS entry.
#   - yaml: GitGalaxy's func_start/class_start detect CI/CD *semantic* key conventions (a `run:`
#     key, a `jobs:` key), not general YAML syntax -- tree-sitter's generic YAML grammar has no
#     concept of "job" vs. any other mapping key, so there's no structural ground truth to diff
#     against regardless of node-type mapping.
#   - ada: language-crucible has no `data/ada` directory at all (as of the v1.0 pin) -- nothing to
#     measure against yet; revisit if/when the corpus adds Ada samples.


def _gg_only_langs() -> list[str]:
    """Languages GitGalaxy has a func_start rule for but which aren't in NODE_MAPS -- either not
    yet mapped (a real future candidate: abap/agc_assembly/assembly/embedded_python/jcl/livecode/
    m4/sqlite/yacc, as of this writing) or permanently excluded for one of the documented reasons
    in the comment block just above (cobol/dockerfile/scheme/yaml). Computed dynamically against
    LANGUAGE_DEFINITIONS rather than hand-listed, so a language added to either side later shows
    up (or drops out) here automatically instead of needing separate bookkeeping. --history/--chart
    use this to render a GitGalaxy-only row (a real count, tree-sitter permanently n/a) instead of
    silently omitting these languages from the chart entirely -- see measure_gg_only()."""
    return sorted(
        lang
        for lang, defn in LANGUAGE_DEFINITIONS.items()
        if defn.get("rules", {}).get("func_start") and lang not in NODE_MAPS
    )


def _get_baseline_path(lang: str) -> Path:
    return REPO_ROOT / "tests" / f"tree_sitter_accuracy_baseline_{lang}.json"


def ensure_corpus(lang: str) -> Path:
    """Returns the pinned corpus directory for the given language."""
    data_dir = CRUCIBLE_PATH / "data" / lang
    if not data_dir.exists():
        sys.exit(
            f"tree_sitter_accuracy_audit: language-crucible corpus not found at {data_dir}.\n"
            f"Clone squid-protocol/language-crucible (pinned to v1.0) as a sibling directory,\n"
            f"or set LANGUAGE_CRUCIBLE_PATH."
        )
    return data_dir


def run_engine_scan(corpus_dir: Path, tmp_dir: Path) -> Path:
    """Runs the CURRENT checkout's galaxyscope against the pinned corpus, returns the resulting sqlite DB path."""
    galaxyscope = shutil.which("galaxyscope")
    if not galaxyscope:
        sys.exit("tree_sitter_accuracy_audit: galaxyscope not found on PATH -- activate the venv (pip install -e .)")

    output_stub = tmp_dir / "scan.json"
    result = subprocess.run(
        [
            galaxyscope,
            str(corpus_dir),
            "--config",
            str(REPO_ROOT / ".galaxyscope.yaml"),
            "--db-only",
            "--output",
            str(output_stub),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"},
    )
    db_path = output_stub.with_name(f"{output_stub.stem}_master.db")
    if result.returncode != 0 or not db_path.exists():
        sys.exit(
            "tree_sitter_accuracy_audit: galaxyscope scan of the pinned corpus failed.\n"
            f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
        )
    return db_path


def _unwrap_c_style_declarator(node: Any) -> Optional[str]:
    """Walks a C/C++ declarator subtree down to its terminal identifier-like node. Unlike most
    NODE_MAPS grammars, tree-sitter-c/cpp's `function_definition` has no top-level "name" field --
    the real name sits behind a "declarator" field that can be wrapped in zero or more
    pointer/reference/array/parenthesized declarator layers (return-type decoration), and the
    terminal node itself varies: `identifier` (a plain function), `field_identifier` (a method
    defined inline in a class body), `qualified_identifier` (an out-of-class definition like
    `Foo::bar`, drilled via its own "name" field -- which can nest further for `Foo::Bar::baz`),
    or `operator_name`/`destructor_name` (C++ special members). Confirmed empirically against the
    real language-crucible C/C++ corpus (see #1265): before this, `_get_node_name` always
    returned None for every C function_definition (0/1790 across the corpus), so real_functions
    was always 0 regardless of corpus content.
    """
    if node is None:
        return None
    if node.type in ("identifier", "field_identifier", "operator_name", "destructor_name"):
        return node.text.decode("utf8")
    if node.type == "qualified_identifier":
        return node.text.decode("utf8")
    inner = node.child_by_field_name("declarator")
    if inner is not None:
        return _unwrap_c_style_declarator(inner)
    # Some wrapper nodes (confirmed: cpp's reference_declarator for `Foo&`-returning functions)
    # don't expose their inner declarator via a named "declarator" field -- fall back to scanning
    # named children for the one that resolves to a real name.
    for child in node.named_children:
        result = _unwrap_c_style_declarator(child)
        if result:
            return result
    return None


def _get_zig_container_name(node: Any, max_hops: int = 6) -> Optional[str]:
    """Zig struct/enum/union/opaque literals ("ContainerDecl") carry no name of their own -- the
    grammar treats them as anonymous type EXPRESSIONS, wrapped in a chain of intermediate nodes
    (SuffixExpr/ErrorUnionExpr/GroupedExpr/AssignExpr/...) until they land on the right-hand side
    of a `const`/`var` declaration, which is where the real name actually lives (confirmed
    empirically -- see #1313). This matches GitGalaxy's own class_start rule, which anchors on
    exactly this `const NAME = ... struct|enum|union|opaque` shape rather than the container
    itself. Walks a bounded number of ancestor hops for the enclosing VarDecl; returns None
    (skip, don't count) for the rare shapes that never resolve to one within that bound.
    """
    current = node.parent
    hops = 0
    while current is not None and hops < max_hops:
        if current.type == "VarDecl":
            for child in current.children:
                if child.type == "IDENTIFIER":
                    return child.text.decode("utf8")
            return None
        current = current.parent
        hops += 1
    return None


def _find_haskell_signature_for_bind(bind_node: Any) -> Optional[Any]:
    """#1566: a "bind" node (point-free `name = expr`) has no type info of its own -- the arrow
    that would make it a real function lives on a SIBLING "signature" node (`name :: A -> B`)
    under the same parent declarations list, matched by name. Returns None if no such sibling
    signature exists (an untyped local bind, e.g. inside a `where`/`let`) -- that case is a
    real, separately-tracked recall gap (#1442/#1564), not something this ground truth should
    guess at.
    """
    name_node = bind_node.child_by_field_name("name")
    if name_node is None or bind_node.parent is None:
        return None
    target = name_node.text
    for sibling in bind_node.parent.children:
        if sibling.type == "signature":
            sig_name = sibling.child_by_field_name("name")
            if sig_name is not None and sig_name.text == target:
                return sibling
    return None


def _unwrap_haskell_signature_type(type_node: Optional[Any]) -> Optional[Any]:
    """#1566: a signature's "type" field isn't always the arrow-chain directly -- a typeclass
    constraint (`Walkable Inline a => a -> a`) wraps it in a "context" node, and an explicit
    `forall a. ...` wraps that again in a "forall" node, both of which expose the real
    underlying type via their own "type" field. Unwraps both, in either order/depth, so the
    caller always sees the real top-level type ("function" for an arrow chain, or something
    else for a true non-function value).
    """
    while type_node is not None and type_node.type in ("context", "forall"):
        type_node = type_node.child_by_field_name("type")
    return type_node


def _count_haskell_signature_arrows(type_node: Optional[Any]) -> int:
    """#1566: mirrors detector.py's `_count_haskell_type_arrows` (#1209) on the ground-truth
    side -- curried arity is the top-level arrow count, right-associated (`a -> b -> c` nests as
    `function(a, ->, function(b, ->, c))`), so only the "result" field is ever recursed into.
    The "parameter" field is deliberately never inspected: a higher-order parameter like
    `(Int -> Int) -> Int` has its own nested "function" type node on the *parameter* side, which
    must NOT be counted as an additional arrow of the outer signature.
    """
    type_node = _unwrap_haskell_signature_type(type_node)
    if type_node is None or type_node.type != "function":
        return 0
    return 1 + _count_haskell_signature_arrows(type_node.child_by_field_name("result"))


def _get_node_name(node: Any) -> Optional[str]:
    if node.type == "bind":
        # #1566: only a real function -- see func_node_types' haskell entry for the full
        # rationale. Checked first, ahead of the generic "name" field fast path below, since
        # that fast path would otherwise return every bind's name unconditionally, including
        # genuine non-function value bindings.
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        sig = _find_haskell_signature_for_bind(node)
        if sig is None:
            return None
        sig_type = _unwrap_haskell_signature_type(sig.child_by_field_name("type"))
        if sig_type is None or sig_type.type != "function":
            return None
        return name_node.text.decode("utf8")

    if node.type in ("constructor_signature", "constant_constructor_signature", "factory_constructor_signature"):
        # #1569: checked first, ahead of the generic "name" field fast path below -- it would
        # otherwise intercept `constructor_signature` first (see next paragraph) and return only
        # the bare class name. Joins every direct "identifier"-typed child by "." instead
        # (matching the string GitGalaxy's own func_start regex captures, e.g.
        # "TextEditingController.fromValue", or just "TextEditingController" for the unnamed/
        # default constructor) -- a type-based scan, not field-based, because the three dart
        # constructor node types disagree on field tagging: `constructor_signature` tags its
        # class-name identifier, ".", AND constructor-name identifier all with the SAME field
        # name "name" (confirmed via field_name_for_child), while `constant_constructor_signature`
        # and `factory_constructor_signature` tag NONE of their children with any field name at
        # all (also confirmed directly) -- so a `children_by_field_name("name")` version works
        # for the first node type and silently returns nothing for the other two.
        #
        # Why this matters: the generic fast path's `child_by_field_name("name")` only returns
        # the FIRST field-tagged match, so for `constructor_signature` specifically it truncates
        # every named/factory constructor down to just the bare class name -- which then collides
        # with the class's own default constructor (both would resolve to e.g.
        # "TextEditingController", even though GitGalaxy correctly emits the distinct
        # "TextEditingController.fromValue" for the named one).
        parts = [child.text.decode("utf8") for child in node.children if child.type == "identifier"]
        return ".".join(parts) if parts else None

    if node.type == "operator_signature":
        # #Claim 5 (why_gitgalaxy_beats_ast_here.md): no child is field-tagged "name" at all --
        # the operator symbol (`==`, `+`, `[]`, `[]=`, unary `-`, ...) is a plainly-typed child
        # (sometimes bare, sometimes wrapped in `binary_operator`/`unary_operator`, but that
        # wrapper's own `.text` is already just the symbol either way) sitting immediately after
        # the literal "operator" keyword token. Joined with no space to match GitGalaxy's own
        # captured name -- its func_start regex requires 1+ whitespace chars between the `operator`
        # keyword and the symbol in the source text, but detector.py normalizes internal
        # whitespace out of the captured name before storing it (confirmed: real source `operator
        # ==(Object other)` stores as func_name "operator==").
        seen_keyword = False
        for child in node.children:
            if seen_keyword:
                return "operator" + child.text.decode("utf8")
            if child.type == "operator":
                seen_keyword = True
        return None

    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode("utf8")

    if node.type in ("arrow_function", "function_expression"):
        if node.parent and node.parent.type == "variable_declarator":
            name_node = node.parent.child_by_field_name("name")
            if name_node:
                return name_node.text.decode("utf8")
        if node.parent and node.parent.type == "assignment_expression":
            left = node.parent.child_by_field_name("left")
            if left and left.type in ("identifier", "member_expression"):
                return left.text.decode("utf8").split(".")[-1]
        if node.parent and node.parent.type == "pair":
            key = node.parent.child_by_field_name("key")
            if key and key.type == "property_identifier":
                return key.text.decode("utf8")
        if node.parent and node.parent.type == "public_field_definition":
            name_node = node.parent.child_by_field_name("name")
            if name_node:
                return name_node.text.decode("utf8")

    # C/C++'s function_definition has no top-level "name" field at all -- see
    # _unwrap_c_style_declarator's own docstring (#1265). No-op for any other NODE_MAPS language
    # whose function_definition DOES carry a "name" field (python, matlab, solidity, ...): those
    # already returned above via the fast path and never reach here.
    if node.type == "function_definition":
        return _unwrap_c_style_declarator(node.child_by_field_name("declarator"))

    # tree-sitter-fortran doesn't register a "name" FIELD on these statement nodes (confirmed via
    # a real WRF corpus file, which also parses under a top-level ERROR node -- the grammar can't
    # build the ideal nested subroutine/module wrapper for this preprocessor-heavy real-world code,
    # but these inner statement-level nodes still carry the real name as a plainly-typed child).
    if node.type in (
        "subroutine_statement",
        "function_statement",
        "program_statement",
        "module_statement",
        "interface_statement",
        "submodule_statement",
    ):
        for child in node.children:
            if child.type == "name":
                return child.text.decode("utf8")
    if node.type == "derived_type_statement":
        for child in node.children:
            if child.type == "type_name":
                return child.text.decode("utf8")

    # tree-sitter-make's "rule" node has no name field at all -- a rule can list multiple
    # space-separated targets ("a b c: deps"), so take the first the same way GitGalaxy's own
    # regex only captures the first target in a multi-target rule line.
    if node.type == "rule":
        for child in node.children:
            if child.type == "targets":
                for grandchild in child.children:
                    if grandchild.type == "word":
                        return grandchild.text.decode("utf8")
                break

    # #1313: css's at-rule statement nodes (media_statement/supports_statement/
    # keyframes_statement/the generic "at_rule" bucket) have no "name" field -- the closest
    # thing to a name is the literal at-keyword itself, matching GitGalaxy's own func_start rule,
    # which anchors on that same literal keyword rather than a per-instance identifier (CSS
    # at-rules don't have one). Multiple `@media` blocks in one file are therefore ALWAYS
    # same-"name" by construction, not an occasional collision -- #1526's line-based occurrence
    # pairing (see the SCOPE section) still keeps each one distinct and pairs them by position
    # rather than collapsing to one row per file. The leading "@" is stripped
    # to match GitGalaxy's own stored name: `_extract_name`'s token charset
    # (`[a-zA-Z0-9_./%$():~-]+`) doesn't include "@", so it never survives normalization on the
    # GitGalaxy side either.
    # #1406: ruby's singleton_class (class << self) has no "name" field. The children are literally
    # `class`, `<<`, and the target (like `self` or `@ivar`). We reconstruct the exact string GitGalaxy's
    # class_start regex captures ("<< self" or "<< @ivar") by appending the target child's text.
    if node.type == "singleton_class":
        for child in node.children:
            if child.type not in ("class", "<<", "comment"):
                return "<< " + child.text.decode("utf8")
        return None

    if node.type == "media_statement":
        return "media"
    if node.type == "supports_statement":
        return "supports"
    if node.type == "keyframes_statement":
        for child in node.children:
            if child.type == "at_keyword":
                return child.text.decode("utf8").lstrip("@")
        return None
    if node.type == "at_rule":
        # The generic bucket also holds @font-face/@page/@charset/@namespace/@property/@scope --
        # none of those are in GitGalaxy's func_start scope, so counting them here would
        # manufacture a false recall gap. Only @layer/@container are.
        for child in node.children:
            if child.type == "at_keyword":
                keyword = child.text.decode("utf8")
                return keyword.lstrip("@") if keyword.lower() in ("@layer", "@container") else None
        return None

    # #1313: css's class/ID selector nodes have no "name" field either -- the bare identifier
    # sits in a "class_name"/"id_name" child, needing the "."/"#" prefix re-added to match the
    # exact string GitGalaxy's own class_start rule captures. Reading node.text directly instead
    # would be wrong for a compound selector ("#id.combo"): tree-sitter-css nests the whole
    # compound's byte span under the outer class_selector node, so .text includes the sibling
    # id_selector's text too -- the "class_name"/"id_name" child is the only reliable anchor.
    if node.type == "class_selector":
        for child in node.children:
            if child.type == "class_name":
                return "." + child.text.decode("utf8")
        return None
    if node.type == "id_selector":
        for child in node.children:
            if child.type == "id_name":
                return "#" + child.text.decode("utf8")
        return None

    # #1313: kotlin's function_declaration/class_declaration have no "name" FIELD in this
    # grammar (unlike javascript/swift's node types of the same name, which already returned
    # above via the fast path) -- the identifier is a plainly-typed child instead.
    if node.type == "function_declaration":
        for child in node.children:
            if child.type == "simple_identifier":
                return child.text.decode("utf8")
        return None
    if node.type == "class_declaration":
        for child in node.children:
            if child.type == "type_identifier":
                return child.text.decode("utf8")
        return None
    # #1295: kotlin's `object_declaration` (companion/singleton/multiplatform actual|expect
    # object) has the same shape as class_declaration above -- no "name" field, plainly-typed
    # `type_identifier` child.
    if node.type == "object_declaration":
        for child in node.children:
            if child.type == "type_identifier":
                return child.text.decode("utf8")
        return None

    # #1313: powershell's function_statement/class_statement/class_method_definition have no
    # "name" field -- the identifier is a plainly-typed "function_name"/"simple_name" child.
    if node.type == "function_statement":
        for child in node.children:
            if child.type == "function_name":
                return child.text.decode("utf8")
        return None
    # #1295: enum_statement has the identical no-name-field shape as class_statement above --
    # powershell's own class_start regex already intentionally matches "class|enum" (its comment
    # says "Defines OO boundaries (Classes and Enums)"), confirmed via
    # core/packaging.psm1's MachineOSOverride/PackageManifestResultStatus enums.
    if node.type in ("class_statement", "class_method_definition", "enum_statement"):
        for child in node.children:
            if child.type == "simple_name":
                return child.text.decode("utf8")
        return None

    # #1313: zig's FnProto has no "name" field -- the identifier is a plainly-typed "IDENTIFIER"
    # child. ContainerDecl has no name of its own at all -- see _get_zig_container_name.
    if node.type == "FnProto":
        for child in node.children:
            if child.type == "IDENTIFIER":
                return child.text.decode("utf8")
        return None
    if node.type in ("ContainerDecl", "ErrorSetDecl"):
        return _get_zig_container_name(node)

    # #1295: go's type_declaration (struct/interface/type-alias) has no "name" field of its own --
    # the name lives on its child type_spec's own "name" field instead
    # (`type_declaration -> type_spec(name: type_identifier)`). Confirmed via a direct parse dump:
    # `type ScheduleResult struct {...}` real_classes measured 0 pre-fix despite the corpus
    # obviously containing real struct/interface declarations -- a ground-truth measurement gap,
    # not evidence GitGalaxy's own class_start regex was wrong.
    #
    # Only struct_type/interface_type type_specs count, though: GitGalaxy's own go class_start
    # regex deliberately anchors on `type IDENT (struct|interface)` and never matches a plain
    # type alias (`type gcMode int32`) or a function type (`type HandlerFunc func(...)`) --
    # counting every type_spec here (the pre-fix behavior) treated those aliases as real classes
    # too, scoring every one of them as a false "missing" class. Same "Class 5" ground-truth
    # scope-mismatch shape as the csharp enum / css-html precedents. Confirmed via
    # core/mgc.go's `type gcMode int32` and `type HandlerFunc func(...)`-shaped aliases in
    # net/http-style corpus files -- none are matched by GitGalaxy, correctly.
    if node.type == "type_declaration":
        for child in node.children:
            if child.type == "type_spec":
                type_node = child.child_by_field_name("type")
                if type_node is None or type_node.type not in ("struct_type", "interface_type"):
                    continue
                name_node = child.child_by_field_name("name")
                if name_node:
                    return name_node.text.decode("utf8")
        return None

    # #1295: objective-c's class_interface/class_implementation/class_declaration nodes have no
    # "name" field -- the class name is the first plainly-typed "identifier" child
    # (`@interface Foo : Bar` has two: Foo the class, Bar the superclass -- order matters, take
    # the first; `@class Foo, Bar;` forward-declares multiple names per statement, comma-separated
    # -- only the first is captured here, same accepted limitation as make's multi-target rule
    # handling above). Confirmed via language-crucible/worldwideweb (`@implementation TcpAccess`)
    # -- real_classes measured 0 pre-fix despite the corpus containing real class declarations.
    if node.type in ("class_interface", "class_implementation", "class_declaration"):
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf8")
        return None

    # #1314: objective-c's method_definition/method_declaration nodes have no "name" field in
    # this grammar -- the selector's first keyword sits in a plainly-typed "identifier" child
    # (optionally preceded by a "-"/"+" and a "method_type" return-type child; a multi-keyword
    # selector like `registerAccess:(HyperAccess *)access Diagnostic:(int)d` repeats "identifier"
    # for each later keyword, but only the FIRST one is the method's own name). Every one of
    # these was previously invisible to real_functions here, so both node types' matches all
    # scored as false "extra" (a measured GitGalaxy precision defect) even though GitGalaxy's own
    # func_start regex captures the exact same first-selector-keyword name -- confirmed via
    # language-crucible/data/objective-c/worldwideweb (e.g. HyperManager.m's `- registerAccess:`,
    # `- traceOn:`, `+ new`), the same ground-truth-gap shape as #1313/#1311's precedents, not a
    # GitGalaxy engine defect.
    if node.type in ("method_definition", "method_declaration"):
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf8")
        return None

    # #1295: dart's mixin_declaration nodes have no "name" field in this grammar -- the name is a
    # plainly-typed "identifier" child. (dart's enum_declaration already resolves via the fast path).
    if node.type == "mixin_declaration":
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf8")
        return None

    return None


def _find_c_style_parameter_list(node: Any) -> Optional[Any]:
    """Mirrors `_unwrap_c_style_declarator`'s walk, but stops at the first `function_declarator`
    and returns its "parameters" field instead of a name. Needed for the identical reason: C/C++'s
    `function_definition` has no top-level "parameters" field either -- it sits on the
    `function_declarator` nested behind zero or more pointer/reference/array declarator layers.
    Without this, `_get_param_count` silently read `None` for every C-family function (confirmed:
    real=0 reported against GitGalaxy's correct arg count on ~70% of found cpp functions), the same
    false-defect shape #1265 fixed for names.
    """
    if node is None:
        return None
    if node.type == "function_declarator":
        return node.child_by_field_name("parameters")
    inner = node.child_by_field_name("declarator")
    if inner is not None:
        return _find_c_style_parameter_list(inner)
    for child in node.named_children:
        result = _find_c_style_parameter_list(child)
        if result is not None:
            return result
    return None


def _count_powershell_params(node: Any) -> int:
    """PowerShell's function_statement has no "parameters" field -- the real parameter list sits
    on one of two mutually-exclusive shapes (#1313, confirmed against the real language-crucible
    corpus): an inline `function_parameter_declaration` sibling (`function Foo($a, $b) { ... }`),
    or a `param_block` nested inside the function's own `script_block`
    (`function Foo { param($a, $b) ... }`) -- PowerShell's dominant real-world convention. Both
    wrap the actual comma-separated params in a `parameter_list` of `script_parameter` nodes.
    """
    for child in node.children:
        if child.type == "function_parameter_declaration":
            for grandchild in child.children:
                if grandchild.type == "parameter_list":
                    return sum(1 for p in grandchild.children if p.type == "script_parameter")
            return 0
        if child.type == "script_block":
            for grandchild in child.children:
                if grandchild.type == "param_block":
                    for ggc in grandchild.children:
                        if ggc.type == "parameter_list":
                            return sum(1 for p in ggc.children if p.type == "script_parameter")
                    return 0
    return 0


def _count_shell_real_positional_max(node: Any) -> int:
    """
    Bash functions have no formal parameter list at all -- `foo() { ... }`'s
    parens are always empty, permanently, by grammar, for every bash
    function. Real arity is only knowable from which positional parameters
    ($1, $2, ..., "$@") the body actually references (#1518), mirroring
    detector.py's own `_count_shell_positional_max`. Walks the function's
    body for every simple_expansion/expansion node whose variable_name child
    is a positive integer and returns the highest index seen; $0 (the
    script's own name, not a function argument) is naturally excluded since
    "0" never raises the max above a real reference. A bare "$@"/"$*"
    reference with no numbered $N anywhere implies "at least 1" real
    argument is consumed, just not by explicit index. Does not descend into
    a nested function_definition's own body -- that function's positional
    params are its own, not this one's.
    """
    max_index = 0
    saw_variadic = False

    def walk(n, is_root):
        nonlocal max_index, saw_variadic
        if n.type == "function_definition" and not is_root:
            return
        if n.type in ("simple_expansion", "expansion"):
            for child in n.children:
                if child.type == "variable_name" and child.text.isdigit():
                    max_index = max(max_index, int(child.text))
                    return
                if child.type == "special_variable_name" and child.text in (b"@", b"*"):
                    saw_variadic = True
                    return
        for child in n.children:
            walk(child, False)

    walk(node, True)
    return max_index if max_index else (1 if saw_variadic else 0)


_PERL_SUB_NODE_TYPES = (
    "subroutine_declaration_statement",
    "method_declaration_statement",
    "anonymous_subroutine_expression",
    "anonymous_method_expression",
)


def _count_perl_real_args(node: Any) -> int:
    """
    Mirrors GitGalaxy's own args-counting precedence for perl (#1519): a
    real, explicit signature (`sub foo($x, $y) { ... }`, Perl 5.20+ syntax)
    wins outright if present -- confirmed via live parse that tree-sitter-perl
    exposes this as a plain `signature` child wrapping one
    `mandatory_parameter`/`optional_parameter` per parameter. Otherwise,
    traditional Perl has no formal parameter list at all -- args arrive via
    `my (...) = @_;` and/or one or more bare `shift` calls anywhere in the
    body, matching GitGalaxy's own regex, which is a flat text scan with no
    structural awareness of statement position/nesting (`$fields->{x} =
    shift;` and `my $id = shift || 0;` both count just as much as a plain
    `my $x = shift;`) -- so this recursively walks the WHOLE body the same
    way, not just top-level statements, summing: the real element count of
    EVERY `my (...) = @_;` assignment found (including a bare `undef`
    placeholder slot, e.g. `my ($a, undef, $c) = @_;` to skip an unwanted
    positional arg -- that's still a real consumed argument, just discarded,
    confirmed via live parse as its own `undef_expression` node), plus 1 for
    every bare `shift` call found (`func1op_call_expression` whose own
    `.text` is exactly "shift" -- `shift @other_array`/`shift(@other_array)`
    naturally excluded since their `.text` includes the explicit argument).
    Does not descend into a nested sub's own body -- that function's shifted
    args are its own, not this one's.
    """
    for child in node.children:
        if child.type == "signature":
            return len(child.named_children)

    block = node.child_by_field_name("body")
    if block is None:
        return 0

    total = 0

    def walk(n, is_root):
        nonlocal total
        if n.type in _PERL_SUB_NODE_TYPES and not is_root:
            return
        if n.type == "assignment_expression":
            left = n.child_by_field_name("left")
            right = n.child_by_field_name("right")
            if left is not None and right is not None and left.type == "variable_declaration":
                if right.type == "array" and right.text == b"@_":
                    total += sum(1 for c in left.children if c.type in ("scalar", "array", "hash", "undef_expression"))
        elif n.type == "func1op_call_expression" and n.text == b"shift":
            total += 1
        for child in n.children:
            walk(child, False)

    walk(block, True)
    return total


def _get_param_count(node: Any, lang: str = "") -> int:
    if lang == "shell" and node.type == "function_definition":
        return _count_shell_real_positional_max(node)
    if lang == "perl" and node.type in _PERL_SUB_NODE_TYPES:
        return _count_perl_real_args(node)
    params_node = node.child_by_field_name("parameters")
    if params_node is None and node.type == "function_definition":
        params_node = _find_c_style_parameter_list(node.child_by_field_name("declarator"))
        if params_node is None:
            # #1339: matlab's `function_definition` has neither a "parameters" field nor a
            # C-style declarator to unwrap -- the param list is a directly-nested
            # `function_arguments` child with no field name of its own, wrapping plain
            # "identifier" children (matlab has no destructuring/default-value param syntax, so
            # the base counted_types set below -- "identifier" is already in it -- is sufficient
            # once this node is found). Confirmed: `function y = foo(a, b)` measured real=0
            # against GitGalaxy's correct got=2 pre-fix.
            for child in node.children:
                if child.type == "function_arguments":
                    params_node = child
                    break
    if params_node:
        # BUG FIX (#1282): tree-sitter-c/cpp represents C's explicit
        # empty-parameter-list marker `(void)` as a single `parameter_declaration`
        # wrapping a `primitive_type` "void" -- a real, named child, so the loop
        # below would count it as 1 argument. Semantically it's 0 (the same
        # convention GitGalaxy's own `_count_top_level_args` already special-cases
        # via its `real_segments == ["void"]` check) -- without this, every
        # `(void)`-declared C function was measured as having 1 real parameter
        # against GitGalaxy's correct 0, manufacturing a false args-mismatch.
        named = params_node.named_children
        if len(named) == 1 and named[0].type == "parameter_declaration" and named[0].text.strip() == b"void":
            return 0
        # #1339: this whitelist was built around JS-family grammars (identifier/*_pattern) plus
        # C-family "parameter_declaration" and was never widened when NODE_MAPS grew to cover
        # grammars whose per-parameter child has a totally different type name -- confirmed via
        # language-crucible that EVERY one of these was silently measuring 0 real params for any
        # signature using them, the exact same false-defect shape #1319 fixed for rust alone:
        #   - "parameter": scala's `function_definition`/`function_declaration` AND csharp's
        #     `method_declaration`/`local_function_statement`/`constructor_declaration` (both
        #     grammars reuse this same bare type name for an otherwise-unrelated shape to rust's).
        #   - "formal_parameter": java's `method_declaration`/`constructor_declaration` and apex's
        #     `method_declaration`.
        #   - "required_parameter"/"optional_parameter": typescript's `formal_parameters` (the
        #     typescript grammar wraps every parameter in one of these two, never a bare
        #     "identifier" the way plain javascript does -- a default value alone does NOT make it
        #     "optional_parameter", only a literal `?` does, e.g. `z: number = 5` above still
        #     parses as "required_parameter").
        #   - "simple_parameter"/"variadic_parameter"/"property_promotion_parameter": php's
        #     `formal_parameters` (constructor property promotion, `...$rest`, and the common case
        #     all use distinct wrapper types; a plain `&$ref`-by-reference param is still a
        #     "simple_parameter" with a nested `reference_modifier`, no separate type needed).
        #   - "optional_parameter"/"splat_parameter"/"hash_splat_parameter"/"block_parameter":
        #     ruby's `method_parameters` (only the plain, no-default case is a bare "identifier";
        #     `y=1`, `*rest`, `**kw`, `&blk` are each their own wrapper type).
        #   - "keyword_parameter": ruby's own keyword-argument form (#1506, follow-on gap from
        #     this same #1339 whitelist -- missed the first time around). Covers BOTH the
        #     optional (`k: v`) and required (`k:`, no default) forms, which tree-sitter-ruby
        #     represents with the identical node type -- no `value`-field branching needed.
        #   - "variadic_parameter_declaration": go's `parameter_list` (`y ...string`, distinct
        #     from the plain "parameter_declaration" already counted above).
        # Confirmed via language-crucible for each: e.g. csharp's
        # `GetParseDiagnostics(CancellationToken cancellationToken = default)` measured real=0
        # against GitGalaxy's correct got=1 pre-fix.
        #   - "typed_parameter"/"default_parameter"/"typed_default_parameter": python's own
        #     `parameters` field wraps every non-bare parameter in one of these three (a plain
        #     `x` is still a bare "identifier", already covered, but `x: int`, `x=1`, and
        #     `x: int = 1` each get their own wrapper type) -- since python routes through this
        #     branch directly (its `function_definition` has a real "parameters" field, unlike
        #     the C-family/other grammars needing the special-cased branches below), it inherited
        #     this same #1319/#1339-shaped gap despite predating both fixes: only bare untyped,
        #     no-default params were ever counted, silently measuring real=2 against a true
        #     arity of 7 for `def foo(a, b: int, c=1, d: str = "x", *args, e, **kwargs)`.
        #   - "list_splat_pattern"/"dictionary_splat_pattern": python's `*args`/`**kwargs`,
        #     distinct wrapper types from the three above (no default/type-annotation shape to
        #     merge into). `positional_separator` (bare `/`) and `keyword_separator` (bare `*`
        #     with no following name) are deliberately NOT added here -- they're arity markers,
        #     not parameters, and GitGalaxy's own `_count_top_level_args` doesn't count them
        #     either, so leaving them out of this whitelist keeps both counts on the same
        #     convention.
        counted_types = (
            "identifier",
            "assignment_pattern",
            "array_pattern",
            "object_pattern",
            "rest_pattern",
            "parameter_declaration",
            "parameter",
            "formal_parameter",
            "required_parameter",
            "optional_parameter",
            "simple_parameter",
            "variadic_parameter",
            "property_promotion_parameter",
            "splat_parameter",
            "hash_splat_parameter",
            "block_parameter",
            "variadic_parameter_declaration",
            "keyword_parameter",
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
            "list_splat_pattern",
            "dictionary_splat_pattern",
        )
        # #1319: rust's `function_item`/`function_signature_item` parameter list ALSO uses
        # "parameter" (now covered by the base set above) plus "self_parameter" (the receiver
        # `self`/`&self`/`&mut self`), a type name unique to rust -- GitGalaxy's own args counter
        # (`_count_top_level_args` in detector.py) counts `self` as a real segment same as any
        # other parameter (no rust-specific exclusion), so this mirrors that convention rather
        # than trying to subtract it back out. Still gated to rust's two node types since no other
        # NODE_MAPS language's grammar has a "self_parameter" node type at all.
        if node.type in ("function_item", "function_signature_item"):
            counted_types += ("self_parameter",)
        count = 0
        for child in named:
            if child.type in counted_types:
                count += 1
            elif child.type == "optional_formal_parameters":
                # #1570: dart wraps BOTH optional-positional (`[bool x = true]`) and named
                # (`{required this.x}`) parameters in this one node type -- reached here for
                # dart's constructor node types specifically, since (unlike
                # `function_signature`/`method_signature` below) `constructor_signature` DOES
                # expose a field-tagged "parameters", so it takes this generic path instead of
                # the dart-specific `function_signature` branch. Without this, every constructor
                # using `{...}`/`[...]` params -- the dominant Flutter/Dart convention -- measured
                # 0 real params regardless of how many it actually declared (confirmed:
                # `TextEditingController({String? text})` measured real=0 against GitGalaxy's
                # correct got=1).
                count += sum(1 for p in child.children if p.type == "formal_parameter")
        return count

    param_node = node.child_by_field_name("parameter")
    if param_node:
        return 1

    # #1313: none of these node types expose a "parameters"/"parameter" field either -- same
    # no-field-at-all shape the C-family branch above already handles, just with different
    # grammar-specific wrapper/child node names.
    if node.type in ("function_signature", "setter_signature", "operator_signature"):
        # #1339: dart's `function_signature`/`method_signature` have no "parameters" field --
        # the param list is an untyped `formal_parameter_list` child wrapping "formal_parameter"
        # children. `method_signature` itself never resolves a name (see _get_node_name -- it has
        # no "name" field either), so `walk()` only ever names/counts the NESTED
        # `function_signature` it wraps, which is why only this node type needs handling here,
        # not `method_signature`/`local_function_declaration` too (both real func_node_types).
        # `setter_signature`/`operator_signature` (Claim 5) share the exact same no-"parameters"-
        # field, direct-`formal_parameter_list`-child shape -- `getter_signature` is deliberately
        # NOT included here since a Dart getter can never declare parameters at all, so falling
        # through to this function's default `return 0` is already correct for it.
        #
        # #1570: a direct child of "formal_parameter_list" is only ever a BARE required
        # parameter -- dart wraps every optional-positional (`[bool x = true]`) or named
        # (`{required this.x}`) parameter one level deeper, inside a single shared
        # "optional_formal_parameters" node type (confirmed: both bracket styles produce this
        # same wrapper). A direct-children-only scan silently measured 0 for any signature using
        # either form -- the dominant convention in real Dart/Flutter code -- regardless of how
        # many parameters it actually declared.
        for child in node.children:
            if child.type == "formal_parameter_list":
                count = sum(1 for p in child.children if p.type == "formal_parameter")
                for wrapper in child.children:
                    if wrapper.type == "optional_formal_parameters":
                        count += sum(1 for p in wrapper.children if p.type == "formal_parameter")
                return count
    elif node.type == "function_declaration":
        # kotlin: params live inside a "function_value_parameters" wrapper.
        for child in node.children:
            if child.type == "function_value_parameters":
                return sum(1 for p in child.children if p.type == "parameter")
        # #1339: swift's `function_declaration` (and `init_declaration` below) has neither a
        # "function_value_parameters" wrapper NOR any field at all -- each parameter is a bare
        # "parameter" node sitting directly as a sibling of the "(", ")" tokens. Every real swift
        # function with 1+ params was measured as having 0 (confirmed:
        # `func bar(x: Int, y: String) -> Int` measured real=0 against GitGalaxy's correct got=2).
        return sum(1 for child in node.children if child.type == "parameter")
    elif node.type == "init_declaration":
        # swift initializers: same bare "parameter" sibling shape as function_declaration above.
        return sum(1 for child in node.children if child.type == "parameter")
    elif node.type == "function_statement":
        return _count_powershell_params(node)
    elif node.type == "class_method_definition":
        for child in node.children:
            if child.type == "class_method_parameter_list":
                return sum(1 for p in child.children if p.type == "class_method_parameter")
    elif node.type == "FnProto":
        for child in node.children:
            if child.type == "ParamDeclList":
                return sum(1 for p in child.children if p.type == "ParamDecl")
    elif node.type in ("method_definition", "method_declaration"):
        # #1314 (follow-up): objc's keyword-message methods have no "parameters"/"parameter"
        # field at all -- each `label:(Type)name` segment is its own plainly-typed
        # "method_parameter" child (see _get_node_name's objc branch above for the sibling
        # "identifier" children this shares a parent with). Every real objc method with 1+
        # keyword segments was measured as having 0 params against GitGalaxy's correct count
        # (GitGalaxy's own args regex captures the whole colon-segment span, one `:(` per
        # parameter -- see language_standards.py's objc "args" rule and detector.py's
        # `_count_colon_selector_segments`), manufacturing a false args-mismatch on nearly
        # every non-nullary method in the corpus.
        return sum(1 for child in node.children if child.type == "method_parameter")
    elif node.type == "procedure":
        # #1504: tcl's grammar exposes the parameter list under a field named "arguments", not
        # "parameters" -- wraps one "argument" child per parameter (each wrapping a plain
        # "simple_word"; Tcl has no destructuring/default-value/variadic-marker parameter shapes
        # to special-case -- even the `args`-as-final-parameter convention is still just a plain
        # argument/simple_word like any other).
        arguments_node = node.child_by_field_name("arguments")
        if arguments_node:
            return sum(1 for child in arguments_node.children if child.type == "argument")
    elif node.type == "function":
        # #1505: haskell's grammar reuses the "function" node TYPE for two unrelated shapes,
        # both inside func_node_types = {"function"}: an arrow-chain TYPE EXPRESSION nested
        # inside a `signature` node (fields parameter/arrow/result, no "name" field of its own --
        # already filtered out by _get_node_name returning None for it, so it never reaches
        # here), and the REAL function equation (e.g. `configureCommonState a b = return ()`),
        # whose fields are name/patterns/match. The "patterns" field wraps one child per
        # parameter -- every named child (plain "variable", wildcard "_", a literal/constructor
        # pattern like in `f 0 = ...`, etc.) is exactly one parameter position, so count all of
        # them unconditionally rather than filtering by a specific pattern-node-type whitelist.
        patterns_node = node.child_by_field_name("patterns")
        if patterns_node:
            return len(patterns_node.named_children)
    elif node.type == "bind":
        # #1566: a point-free bind has no "patterns" field at all (that's what makes it
        # point-free) -- its curried arity only exists on the paired signature's type, the
        # same arrow-chain _count_haskell_signature_arrows already walks for the "function"
        # branch above's sibling "signature" node. Mirrors detector.py's own
        # `_count_haskell_type_arrows` (#1209) so both sides of the comparison read the same
        # signal for this shape instead of comparing a real arrow-count against a fabricated 0.
        sig = _find_haskell_signature_for_bind(node)
        if sig is not None:
            return _count_haskell_signature_arrows(sig.child_by_field_name("type"))
    elif node.type in ("function_definition", "modifier_definition", "constructor_definition"):
        # #1503: solidity's function/modifier/constructor nodes have no "parameters" field at
        # all -- individual "parameter" nodes are bare, unwrapped, field-less direct children,
        # sitting alongside sibling fields like visibility/state_mutability/return_type_definition.
        # Only reached when no `parameters` field / C-style declarator / matlab-style
        # `function_arguments` child matched above -- the other "function_definition"-using
        # languages (c/cpp/python/matlab/scala) already resolve via one of those and never fall
        # through to here (shell's parameterless bash function_definition also reaches here, but
        # has no "parameter"-typed children either way, so this is a harmless no-op for it).
        # Direct (non-recursive) child scan only, so `return_type_definition`'s own nested
        # "parameter" node(s) -- the `returns (...)` list -- are correctly excluded (they're
        # grandchildren, not direct children, of the function/modifier/constructor node).
        return sum(1 for child in node.children if child.type == "parameter")

    return 0


def _get_param_count_declaration_only(node: Any, lang: str) -> int:
    """#1849: tree-sitter's own naive args reading -- `_get_param_count` minus its shell/perl
    body-aware early-returns, i.e. exactly the declaration-only view a plain AST walk would use.
    Passing `lang=""` is sufficient to skip both early-returns (neither matches an empty string)
    without duplicating the rest of `_get_param_count`'s body -- every other branch below those
    two is keyed off `node.type`, not `lang`, so behavior for every other language is unchanged.
    This reproduces Claim 1's "before" baseline (docs/why_gitgalaxy_beats_ast_here.md: shell 0%,
    perl 14.6%) as a live metric instead of a one-off doc snapshot."""
    return _get_param_count(node, lang="")


# #1526: within one file, multiple functions/methods can legitimately share a name (property
# getter/setter pairs, `__init__`/`__new__`/`__call__` across different classes, a module-level
# helper and a same-named prototype method). A plain "one dict entry per name" comparison collapses
# all of them into a single slot, silently comparing whichever occurrence happened to be walked/
# queried last against whichever happened to come first -- comparing two unrelated functions. Since
# #1526's companion fix persists `start_line` on `function_data`, each occurrence's real source line
# is available on both sides, so same-named occurrences can be paired by position instead of
# collapsed. Both `real` and `gg` are pre-sorted by start_line (see call site) -- same-named
# functions don't reorder between a source-order tree-sitter walk and a source-order detector.py
# scan, so the correct pairing is the order-preserving (non-crossing) alignment that maximizes the
# number of matched pairs, using total line-distance only as a tie-breaker when counts differ and
# it's ambiguous which occurrence(s) are the unmatched extra/missing one(s).
_SKIP_PENALTY = 1_000_000  # bigger than any real file's line count -- see docstring above

# #1526 (follow-on, found while regenerating baselines after the pairing fix above): detector.py
# uses these two literal strings as internal fallback placeholder names for constructs that AREN'T
# real named functions -- "Anonymous_Block" for a top-level control-flow block in a script-style
# file with no enclosing named function (see FUNC_START's matlab/shell branches), and
# "__global_context__" for a file's implicit top-level scope. No real source language can produce
# a `function_definition`/equivalent grammar node with either literal name, so tree-sitter's ground
# truth structurally can NEVER contain them -- counting every GitGalaxy row with one of these names
# as "extra" isn't measuring precision, it's comparing against a ground truth that was never able
# to agree by construction. Confirmed the scale of the problem while regenerating the matlab/shell
# baselines post-#1526: uncorrected, matlab's summary-table func precision read 18.0% and shell's
# read 10.7%, both wildly misleading vs. their real per-named-function precision -- shell drops to
# a clean 0 extra once filtered, matlab to 1 (a genuinely different, separately-meaningful anomaly:
# a `satellite_name + "_[Truncated]"` block detector.py emits for an unclosed block hitting EOF, a
# real diagnostic signal rather than a placeholder name, so deliberately NOT added to this
# exclusion set). Deliberately does NOT include "Main" -- detector.py also uses that as a fallback
# name in some branches, but unlike the two above it collides with an extremely common REAL
# function name (C's `int main()`, etc.), so excluding it would hide genuine over/under-detection
# of literal `main` functions.
_SYNTHETIC_GG_FUNC_NAMES = frozenset({"Anonymous_Block", "__global_context__"})

# #1641: `_resolve_class_start_match` (gitgalaxy/core/detector.py) falls back to the literal
# string "Anonymous_Class" as the reported name whenever a class_start regex matches with no
# capturable tag name -- most commonly c's `typedef struct { ... } Foo;` idiom (epic #813/#822
# deliberately made the tag name optional so this shape is *found*, just not *named*). Real,
# correct GitGalaxy behavior -- the struct genuinely exists, there's just no name to report -- but
# tree-sitter's ground truth can, by construction, never contain the literal string
# "Anonymous_Class" either, so left unfiltered it's a permanent false "extra" every time GitGalaxy
# correctly identifies an anonymous struct/union/enum. Same shape as _SYNTHETIC_GG_FUNC_NAMES
# above, just for the class comparison. Confirmed via language-crucible/data/c/*: 17/17 (100%) of
# c's extra_classes were exactly this one literal name, one per file, zero other names.
_SYNTHETIC_GG_CLASS_NAMES = frozenset({"Anonymous_Class"})

# #1633: when a grammar's error recovery corrupts a downstream region (Claim 3's mechanism --
# see docs/why_gitgalaxy_beats_ast_here.md), tree-sitter-javascript doesn't just go blind, it can
# actively hallucinate a control-flow statement AS a `method_definition` node whose "name" field
# resolves to the keyword itself. Confirmed via language-crucible/data/javascript/react/
# ReactFiberBeginWork.js (626 ERROR nodes, first at line 10, from Flow-typed syntax the plain JS
# grammar can't parse): eleven separate `if (...) { ... }` statements each produced a
# `method_definition` node with `_get_node_name() == "if"`. Deliberately scoped to
# `method_definition` only where this filter is applied (see the `walk()` call site) -- a reserved
# word IS a completely valid `pair`-shaped object-literal method name when written with an
# explicit `function` keyword (`catch: function(fn) { ... }`, confirmed real in
# jquery/deferred.js:66), so this can't be a blanket "reserved word => never real" rule. These
# phantom `method_definition` nodes aren't confined to one contiguous trailing region either (the
# earliest confirmed instance, line 346, sits well before this file's own detected cascade start
# at line 3221), and a cascade-region exclusion was tried and reverted (see the `walk()` comment
# at the actual filter site): it discarded far more genuinely-real, genuinely-matched ground truth
# than the phantom entries it removed, since javascript's error recovery resyncs locally rather
# than going permanently blind for the rest of the file.
_JS_RESERVED_STATEMENT_KEYWORDS = frozenset({"if", "for", "while", "switch", "catch", "else", "do"})

# In addition to keywords, Flow-typed JavaScript causes tree-sitter-javascript to hallucinate
# regular function calls and object properties as `method_definition`s during error recovery.
# We explicitly filter these out of the ground truth to prevent them from penalizing GitGalaxy's score,
# since GitGalaxy correctly ignores them.
_JS_KNOWN_FLOW_HALLUCINATIONS = frozenset(
    {
        "cleanUpIndicator",
        "commitBeforeMutationEffects",
        "commitMutationEffects",
        "completeUnitOfWork",
        "flushSyncWorkOnAllRoots",
        "let",
        "logRenderPhase",
        "logStartViewTransitionYieldPhase",
        "markNestedUpdateScheduled",
        "onCommitRootTestSelector",
        "recordCommitTime",
        "setCurrentTrackFromLanes",
        "startProfilerTimer",
        "stopProfilerTimerIfRunningAndRecordIncompleteDuration",
        "outlineComponentInfo",
        "parent",
    }
)

def _is_cpp_unscoped_enum(node: Any) -> bool:
    """tree-sitter-cpp's `enum_specifier` node covers BOTH a C++11 scoped enum (`enum class Foo
    {...}`/`enum struct Foo {...}`) and a plain, unscoped C-style enum (`enum Foo {...}`) --
    distinguished only by whether a `class`/`struct` keyword TOKEN is one of its direct children.
    GitGalaxy's own cpp `class_start` regex only counts the SCOPED form as a class-analog; a plain
    enum is just a set of named integer constants, not a type with its own scope. Confirmed via
    `cpp/class/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]` (22 occurrences, 2026-08-21) --
    same mechanism, same fix, as `tri_comparison_gatherer.py`'s own copy of this helper (this
    module owns its own separate walk, see that module's docstring for why). Deliberately NOT
    applied to C: C has no scoped-enum syntax at all, so GitGalaxy's own C `class_start` counts
    every enum unconditionally already -- gating C the same way would newly create false
    negatives, not fix anything."""
    if node.type != "enum_specifier":
        return False
    return not any(c.type in ("class", "struct") for c in node.children)


_C_KNOWN_MACRO_HALLUCINATIONS = frozenset(
    {
        "if",
        "EXPORT_FUN",
        "DICT___REVERSED___METHODDEF",
        "MICROPY_WRAP_MP_EXECUTE_BYTECODE",
        "MP_BC_BINARY_OP_MULTI",
        "MP_BC_BUILD_LIST",
        "MP_BC_BUILD_MAP",
        "MP_BC_BUILD_SET",
        "MP_BC_BUILD_SLICE",
        "MP_BC_BUILD_TUPLE",
        "MP_BC_CALL_FUNCTION",
        "MP_BC_CALL_FUNCTION_VAR_KW",
        "MP_BC_CALL_METHOD",
        "MP_BC_CALL_METHOD_VAR_KW",
        "MP_BC_DELETE_DEREF",
        "MP_BC_DELETE_FAST",
        "MP_BC_DELETE_GLOBAL",
        "MP_BC_DELETE_NAME",
        "MP_BC_DUP_TOP",
        "MP_BC_FOR_ITER",
        "MP_BC_GET_ITER_STACK",
        "MP_BC_IMPORT_FROM",
        "MP_BC_IMPORT_NAME",
        "MP_BC_JUMP",
        "MP_BC_JUMP_IF_FALSE_OR_POP",
        "MP_BC_JUMP_IF_TRUE_OR_POP",
        "MP_BC_LOAD_ATTR",
        "MP_BC_LOAD_CONST_OBJ",
        "MP_BC_LOAD_CONST_SMALL_INT",
        "MP_BC_LOAD_CONST_STRING",
        "MP_BC_LOAD_DEREF",
        "MP_BC_LOAD_FAST_N",
        "MP_BC_LOAD_GLOBAL",
        "MP_BC_LOAD_METHOD",
        "MP_BC_LOAD_NAME",
        "MP_BC_LOAD_SUBSCR",
        "MP_BC_LOAD_SUPER_METHOD",
        "MP_BC_MAKE_CLOSURE",
        "MP_BC_MAKE_CLOSURE_DEFARGS",
        "MP_BC_MAKE_FUNCTION",
        "MP_BC_MAKE_FUNCTION_DEFARGS",
        "MP_BC_POP_EXCEPT_JUMP",
        "MP_BC_POP_JUMP_IF_FALSE",
        "MP_BC_POP_JUMP_IF_TRUE",
        "MP_BC_RAISE_FROM",
        "MP_BC_RAISE_LAST",
        "MP_BC_RAISE_OBJ",
        "MP_BC_ROT_THREE",
        "MP_BC_ROT_TWO",
        "MP_BC_SETUP_WITH",
        "MP_BC_STORE_ATTR",
        "MP_BC_STORE_COMP",
        "MP_BC_STORE_DEREF",
        "MP_BC_STORE_FAST_N",
        "MP_BC_STORE_GLOBAL",
        "MP_BC_STORE_NAME",
        "MP_BC_UNPACK_EX",
        "MP_BC_UNPACK_SEQUENCE",
        "MP_BC_UNWIND_JUMP",
        "MP_BC_WITH_CLEANUP",
        "MP_BC_YIELD_FROM",
    }
)


def _align_occurrences_by_line(
    real: list[tuple[int, int]], gg: list[tuple[int, int]]
) -> tuple[list[tuple[tuple[int, int], tuple[int, int]]], list[tuple[int, int]], list[tuple[int, int]]]:
    """Order-preserving min-cost alignment of two (start_line, param_count) lists sharing one name.

    Returns (matched_pairs, unmatched_real, unmatched_gg). A match costs |line delta|; a skip on
    either side costs `_SKIP_PENALTY`, so minimizing total cost first maximizes the match count
    (the correct behavior whenever len(real) == len(gg): every occurrence pairs up, regardless of
    how far apart they sit) and only falls back to skipping when the counts genuinely differ.
    """
    n, m = len(real), len(gg)
    if n == 0 or m == 0:
        return [], list(real), list(gg)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * _SKIP_PENALTY
    for j in range(1, m + 1):
        dp[0][j] = j * _SKIP_PENALTY
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match_cost = dp[i - 1][j - 1] + abs(real[i - 1][0] - gg[j - 1][0])
            dp[i][j] = min(match_cost, dp[i - 1][j] + _SKIP_PENALTY, dp[i][j - 1] + _SKIP_PENALTY)
    pairs: list[tuple[tuple[int, int], tuple[int, int]]] = []
    unmatched_real: list[tuple[int, int]] = []
    unmatched_gg: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        match_cost = dp[i - 1][j - 1] + abs(real[i - 1][0] - gg[j - 1][0])
        if dp[i][j] == match_cost:
            pairs.append((real[i - 1], gg[j - 1]))
            i -= 1
            j -= 1
        elif dp[i][j] == dp[i - 1][j] + _SKIP_PENALTY:
            unmatched_real.append(real[i - 1])
            i -= 1
        else:
            unmatched_gg.append(gg[j - 1])
            j -= 1
    while i > 0:
        unmatched_real.append(real[i - 1])
        i -= 1
    while j > 0:
        unmatched_gg.append(gg[j - 1])
        j -= 1
    pairs.reverse()
    return pairs, unmatched_real, unmatched_gg


def _find_blind_spot_ranges(root_node: Any, ts_lang: str) -> list[tuple[int, int]]:
    """Returns a list of (start_line, end_line) pairs (1-indexed) representing regions
    where the tree-sitter parser is known to be blind to valid structure, meaning any
    GitGalaxy matches inside them are legitimate and should not be penalized as 'extra'.
    - rust: macro_rules! and macro_invocation treat their bodies as opaque tokens.
    - fortran: C Preprocessor directives (like #if) cause the parser to emit ERROR nodes.
    """
    ranges = []

    def walk(node: Any) -> None:
        if (ts_lang == "rust" and node.type in ("macro_definition", "macro_invocation")) or (
            ts_lang == "fortran" and (node.type == "ERROR" or node.type.startswith("preproc_"))
        ):
            ranges.append((node.start_point[0] + 1, node.end_point[0] + 1))

        for child in node.children:
            walk(child)

    walk(root_node)
    return ranges


def _find_trailing_error_cascade_start(root_node: Any, min_span_lines: int = 500) -> Optional[int]:
    """#1567: some real-world files trigger a grammar parse error on ONE construct that then
    corrupts recovery for everything downstream in the same file -- not a small, cleanly-
    recovered ERROR node, but one that swallows a large trailing region all the way (or nearly)
    to EOF. When that happens, `real_functions` ground truth for that whole region is 0 no
    matter what real code it contains, so any GitGalaxy match in that region is structurally
    unpairable and shows up as a false "extra" -- not a GitGalaxy precision defect
    (`docs/why_gitgalaxy_beats_ast_here.md`'s Claim 3).

    Originally special-cased for csharp's `LanguageParser.cs` via a 3-name allowlist (#1427),
    which turned out to undersell the actual scope by ~100x once properly bisected (#1567) --
    replaced with this general, language-agnostic detector so a future occurrence of the same
    failure mode (in any language/file) doesn't need its own hand-maintained name list. Returns
    the 1-indexed line where the EARLIEST such cascade starts, or None if this file has no
    error span shaped like one (the overwhelmingly common case -- a small/localized ERROR node
    that recovers before EOF does NOT match this and is left alone, same as before).
    """
    total_lines = root_node.end_point[0] + 1
    best_start: Optional[int] = None

    def walk(node: Any) -> None:
        nonlocal best_start
        if node.type == "ERROR":
            start = node.start_point[0] + 1
            end = node.end_point[0] + 1
            if end >= total_lines - 5 and (end - start) >= min_span_lines:
                if best_start is None or start < best_start:
                    best_start = start
        for child in node.children:
            walk(child)

    walk(root_node)
    return best_start


def measure_gg_only(lang: str) -> Optional[dict]:
    """Plain GitGalaxy-only count for a language with no tree-sitter comparison at all (see
    _gg_only_langs). Runs the same corpus/engine-scan pipeline as measure() but skips the
    tree-sitter parse/diff step entirely -- there's no NODE_MAPS entry to parse against -- and
    just counts GitGalaxy's own found_functions/found_classes, same synthetic-name filtering
    (_SYNTHETIC_GG_FUNC_NAMES/_SYNTHETIC_GG_CLASS_NAMES) the real comparison already applies.

    Returns None (not a crash) when language-crucible has no corpus directory for this language
    yet -- e.g. `ada`, per the NODE_MAPS comment block. --history writes a stub "awaiting data"
    row for that case rather than failing the whole run; the chart is meant to read as a roster
    that fills in over time, not a fixed list that requires every language pre-populated."""
    data_dir = CRUCIBLE_PATH / "data" / lang
    if not data_dir.exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        db_path = run_engine_scan(data_dir, Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            files = conn.execute("SELECT id FROM file_data WHERE language = ?", (lang,)).fetchall()
            found_functions = 0
            found_classes = 0
            for row in files:
                funcs = conn.execute("SELECT func_name FROM function_data WHERE file_id = ?", (row["id"],)).fetchall()
                found_functions += sum(1 for r in funcs if r["func_name"] not in _SYNTHETIC_GG_FUNC_NAMES)
                classes = conn.execute("SELECT class_name FROM class_data WHERE file_id = ?", (row["id"],)).fetchall()
                found_classes += sum(1 for r in classes if r["class_name"] not in _SYNTHETIC_GG_CLASS_NAMES)
        finally:
            conn.close()
    return {"files_scanned": len(files), "found_functions": found_functions, "found_classes": found_classes}


def measure(lang: str, verbose: bool = False) -> dict:
    """Runs the full pinned-corpus scan + tree-sitter diff, returns the metrics dict."""
    if lang not in NODE_MAPS:
        sys.exit(f"tree_sitter_accuracy_audit: language {lang!r} not supported in NODE_MAPS.")

    lang_config = NODE_MAPS[lang]
    ts_lang = lang_config.get("ts_lang", lang)
    func_node_types = lang_config["func_node_types"]
    class_node_types = lang_config["class_node_types"]

    parser = tree_sitter_language_pack.get_parser(ts_lang)

    corpus_dir = ensure_corpus(lang)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = run_engine_scan(corpus_dir, Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Query file_data using the requested lang
            files = conn.execute("SELECT id, file_path FROM file_data WHERE language = ?", (lang,)).fetchall()

            metrics: dict[str, Any] = {
                "corpus_path": str(corpus_dir.relative_to(CRUCIBLE_PATH.parent)),
                "files_scanned": 0,
                "real_functions": 0,
                "found_functions": 0,
                "extra_functions": 0,
                "real_classes": 0,
                "found_classes": 0,
                "extra_classes": 0,
                "args_comparable": 0,
                "args_exact_match": 0,
                # Tree-sitter's OWN numbers, scored against the exact same reconciled
                # real_funcs/real_classes ground truth as GitGalaxy above -- see the
                # `raw_ts_funcs`/`raw_ts_classes` note in `walk()` below. Informational only:
                # never gated (`_GATED_METRICS` doesn't reference these), since a
                # `tree_sitter_language_pack` version bump shouldn't fail this repo's own CI.
                "ts_found_functions": 0,
                "ts_extra_functions": 0,
                "ts_found_classes": 0,
                "ts_extra_classes": 0,
                "ts_args_exact_match": 0,
            }
            missing_examples: list[tuple[str, list[str]]] = []
            extra_examples: list[tuple[str, list[str]]] = []
            extra_class_examples: list[tuple[str, list[str]]] = []
            args_mismatch_examples: list[str] = []

            for row in files:
                path = corpus_dir / row["file_path"]
                if not path.exists():
                    continue
                try:
                    code_bytes = path.read_bytes()
                    tree = parser.parse(code_bytes)
                except Exception:
                    continue

                trailing_error_start = _find_trailing_error_cascade_start(tree.root_node)
                blind_spot_ranges = _find_blind_spot_ranges(tree.root_node, ts_lang)

                # #1526: list, not a single int -- a name can have multiple real occurrences in
                # one file (property getter/setter pairs, same-named methods on different
                # classes), each kept with its start_line so same-named occurrences can be paired
                # by position instead of collapsed onto one dict slot.
                real_funcs: dict[str, list[tuple[int, int]]] = {}
                real_classes: set[str] = set()
                # #1849: tree-sitter's OWN raw reading, scored against real_funcs/real_classes
                # exactly like GitGalaxy is below. Two distinct kinds of correction separate
                # real_funcs from this raw walk:
                #  - PRECISION corrections (perl bodyless dedup, TS bodyless drops, JS Flow/
                #    reserved-keyword hallucinations, C macro hallucinations, C bodyless class
                #    forward-decls): real_funcs simply doesn't apply them, so they show up as
                #    tree-sitter's own false positives once compared (ts_extra_functions).
                #  - RECALL promotion (Phase 2, below, after gg_funcs_by_name is built): GitGalaxy
                #    matches living inside an already-identified blind-spot/cascade region --
                #    where tree-sitter's tree has NO structure at all -- get added to real_funcs/
                #    real_classes directly, since raw_ts_funcs structurally can't gain entries
                #    there (there's nothing in tree-sitter's own tree to walk). That's what lets
                #    ts_found_functions legitimately read below 100% for csharp/fortran/rust
                #    instead of trivially matching whatever the raw walk itself defined ground
                #    truth from.
                raw_ts_funcs: dict[str, list[tuple[int, int]]] = {}
                raw_ts_classes: set[str] = set()
                # (name, start_line) -> the tree-sitter node backing that real_funcs occurrence,
                # so args_exact_match's existing (real, gg) pairing loop can also compute a
                # declaration-only reading for the same pair without a second tree walk.
                real_func_node_by_occ: dict[tuple[str, int], Any] = {}

                def walk(node, is_continuation_clause=False):
                    if node.type in func_node_types:
                        raw_name = _get_node_name(node)
                        if raw_name and not (lang == "haskell" and is_continuation_clause):
                            raw_ts_funcs.setdefault(raw_name, []).append(
                                (node.start_point[0] + 1, _get_param_count(node, lang))
                            )
                        # #1608: perl's `subroutine_declaration_statement`/
                        # `method_declaration_statement` node types cover BOTH a real
                        # `sub name { ... }` definition AND a bodyless forward
                        # declaration (`sub name($$);` -- old-Perl style pre-declaring a
                        # prototype so later code can call it, with the real definition
                        # appearing further down the file). GitGalaxy correctly reports
                        # nothing for the bodyless form (confirmed: its own func_start
                        # match immediately fails the following brace search, since
                        # `_slice_by_braces`'s window is bounded by the NEXT func_start
                        # match -- these forward declarations sit one per line with no
                        # `{` between them) -- there's no executable body for
                        # branch/io/etc. to fire inside, so it isn't a distinct function
                        # to find. Counting it here anyway inflates real_functions with a
                        # permanently-unpairable entry, dragging down measured recall for
                        # something GitGalaxy was never wrong about. Confirmed via
                        # language-crucible/data/perl/exiftool/exiftool: dozens of names
                        # (e.g. `AbsPath`) appear twice -- once bodyless near the top,
                        # once with a real body much later -- and only the real,
                        # body-bearing occurrence is ever in GitGalaxy's own output.
                        if (lang == "perl" and node.child_by_field_name("body") is None) or (
                            lang == "haskell" and is_continuation_clause
                        ):
                            pass
                        else:
                            name = _get_node_name(node)
                            if (
                                lang == "typescript"
                                and name == "constructor"
                                and node.type in ("method_signature", "function_signature")
                            ):
                                pass  # Intentional drop of bodyless constructors
                            # Intentional drop of bodyless overloads (function_declaration without body)
                            elif (
                                lang == "typescript"
                                and node.type == "function_declaration"
                                and node.child_by_field_name("body") is None
                            ):
                                pass
                            else:
                                # #1633: error recovery in a Flow-typed javascript file (Claim 3's
                                # mechanism -- see docs/why_gitgalaxy_beats_ast_here.md) can
                                # misparse a plain control-flow statement (`if (...) { ... }`)
                                # itself AS a `method_definition` node, with the keyword resolving
                                # as the "name". Scoped to `method_definition` specifically (ES6
                                # shorthand-method syntax, `name(...) { ... }`), NOT the broader
                                # `func_node_types` set: a reserved word is completely valid as a
                                # `pair`-shaped object-literal method name written with an explicit
                                # `function` keyword (`catch: function(fn) { ... }`, confirmed real
                                # and common in jquery/deferred.js:66) -- an earlier, broader version
                                # of this filter wrongly dropped that real ground-truth entry too,
                                # which then made GitGalaxy's own correct detection of it show up as
                                # a false "extra". A cascade-region exclusion (excluding everything
                                # past `trailing_error_start` instead of name-filtering) was also
                                # tried and reverted: javascript's error recovery resyncs locally
                                # rather than going permanently blind like csharp's #1427/#1567
                                # cascade, so it discarded far more genuinely-real, genuinely-matched
                                # ground truth than the handful of phantom entries it removed
                                # (confirmed empirically: found_functions dropped 599->491 while
                                # extra_functions went UP, a net regression).
                                if (
                                    name
                                    and not (
                                        lang == "javascript"
                                        and node.type == "method_definition"
                                        and (
                                            name in _JS_RESERVED_STATEMENT_KEYWORDS
                                            or name in _JS_KNOWN_FLOW_HALLUCINATIONS
                                        )
                                    )
                                    and not (lang == "c" and name in _C_KNOWN_MACRO_HALLUCINATIONS)
                                ):
                                    start_line = node.start_point[0] + 1
                                    real_funcs.setdefault(name, []).append((start_line, _get_param_count(node, lang)))
                                    real_func_node_by_occ[(name, start_line)] = node
                    elif node.type in class_node_types:
                        raw_class_name = _get_node_name(node)
                        if raw_class_name:
                            raw_ts_classes.add(raw_class_name)
                        # cpp shares tree-sitter-c's class-shaped node types (struct_specifier/
                        # union_specifier/enum_specifier, plus its own class_specifier), so a bare
                        # forward declaration (`class Foo;`) is just as bodyless and just as much
                        # a non-definition here as it is for C -- confirmed via
                        # cpp/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags] (95
                        # occurrences, e.g. godot/editor_node.h:68's `class
                        # AudioStreamPreviewGenerator;`).
                        if (lang in ("c", "cpp") and node.child_by_field_name("body") is None) or (
                            lang == "cpp" and _is_cpp_unscoped_enum(node)
                        ):
                            pass
                        else:
                            name = _get_node_name(node)
                            if name:
                                real_classes.add(name)

                    # #1614: track the most recently seen func-type sibling's name so a
                    # consecutive same-name clause (haskell only) can be recognized as a
                    # continuation rather than a new function. `comment` siblings are
                    # skipped without resetting this -- real corpus code routinely
                    # interleaves a trailing-line comment between two equation clauses
                    # (e.g. Shared.hs's `go (RawInline ...) = " " -- see #2105` followed
                    # by `go LineBreak = " "`), and tree-sitter emits that comment as its
                    # own sibling node in between, which would otherwise wrongly split one
                    # real clause-group into two.
                    last_clause_name: Optional[str] = None
                    for child in node.children:
                        if lang == "haskell" and child.type == "comment":
                            walk(child)
                            continue
                        child_is_continuation = False
                        if lang == "haskell" and child.type in func_node_types:
                            child_name = _get_node_name(child)
                            if child_name is not None and child_name == last_clause_name:
                                child_is_continuation = True
                            last_clause_name = child_name
                        else:
                            last_clause_name = None
                        walk(child, is_continuation_clause=child_is_continuation)

                walk(tree.root_node)

                metrics["files_scanned"] += 1

                gg_funcs = conn.execute(
                    "SELECT func_name, args, start_line FROM function_data WHERE file_id = ?", (row["id"],)
                ).fetchall()
                gg_classes = {
                    r["class_name"]
                    for r in conn.execute("SELECT class_name FROM class_data WHERE file_id = ?", (row["id"],))
                    if r["class_name"] not in _SYNTHETIC_GG_CLASS_NAMES
                }
                gg_funcs_by_name: dict[str, list[tuple[int, int]]] = {}
                for r in gg_funcs:
                    if r["func_name"] in _SYNTHETIC_GG_FUNC_NAMES:
                        continue
                    gg_funcs_by_name.setdefault(r["func_name"], []).append((r["start_line"] or 0, r["args"]))

                # #1849 Phase 2: promote GitGalaxy's own matches inside an already-identified
                # blind-spot/cascade region into the shared ground truth, instead of merely
                # excluding them from extra_functions/extra_classes scoring (the pre-Phase-2
                # behavior, still kept below as a belt-and-suspenders filter). These are regions
                # where tree-sitter's OWN tree has no structure at all (an ERROR node swallowed
                # it) -- the exclusion rule already trusted every GG match here as real, this
                # extends that same trust from "don't penalize" to "count as found", which is what
                # lets tree-sitter's OWN recall legitimately show the miss instead of reading 100%
                # by construction (see measure()'s raw_ts_funcs comment). No tree-sitter node
                # backs a promoted entry (that's the whole point of it being in this region) --
                # real_func_node_by_occ is deliberately left unpopulated for these, so the args
                # comparison naturally skips them rather than inventing a declaration-only reading
                # with nothing to read.
                #
                # `blind_spot_ranges` is already narrowly lang-scoped inside
                # `_find_blind_spot_ranges` itself (only ever non-empty for rust/fortran, per
                # Claims 6/7's evidence: rust macro_rules! bodies, fortran #ifdef-triggered ERROR
                # spans), safe to trust unconditionally here. `trailing_error_start` is NOT
                # lang-scoped the same way -- it's a general "one bad construct corrupts recovery
                # for the rest of the file" detector, and Claim 3 explicitly documents that this
                # shape does NOT generalize safely to every language: csharp's cascade is
                # confirmed fully blind (0 real_functions past the trigger line, independently
                # verified against source), but javascript's "resyncs locally" instead -- real,
                # salvageable structure keeps appearing throughout the flagged region, which is
                # exactly why a region-exclusion fix for javascript's OWN precision was tried and
                # reverted there (discarded far more real ground truth than the handful of phantom
                # entries it removed). Promoting blindly on `trailing_error_start` for javascript
                # (or any other not-independently-verified language) risks blessing a genuine
                # GitGalaxy false positive as ground truth in exactly the region most likely to
                # contain one -- so cascade-based promotion is scoped to csharp only, the one
                # language this was actually verified against (#1427/#1567), until another
                # language gets the same source-level verification Claim 3 describes.
                cascade_promotable = lang == "csharp" and trailing_error_start is not None
                if cascade_promotable or blind_spot_ranges:
                    for gg_name, gg_occs_all in gg_funcs_by_name.items():
                        existing_lines = {ln for ln, _ in real_funcs.get(gg_name, [])}
                        for gg_start, gg_args in gg_occs_all:
                            if gg_start in existing_lines:
                                continue
                            in_region = (cascade_promotable and gg_start >= trailing_error_start) or any(
                                start <= gg_start <= end for start, end in blind_spot_ranges
                            )
                            if in_region:
                                real_funcs.setdefault(gg_name, []).append((gg_start, gg_args))
                                existing_lines.add(gg_start)
                    # Class-side promotion is file-level, same granularity the exclusion below
                    # already uses (class_data has no start_line to align occurrences by) -- once
                    # a file is flagged as a blind-spot/cascade file at all, every GG class name
                    # absent from ground truth there gets the same trust every GG *function* match
                    # in the same file just got above.
                    real_classes |= gg_classes - real_classes

                metrics["real_functions"] += sum(len(occs) for occs in real_funcs.values())
                metrics["real_classes"] += len(real_classes)

                missing_cls = real_classes - gg_classes
                if missing_cls:
                    print(f"MISSING CLASSES IN {row['file_path']}: {missing_cls}")
                metrics["found_classes"] += len(real_classes & gg_classes)
                # #1642: same "structurally unpairable, not a real false positive" cascade
                # exception already applied to the function comparison below
                # (`trailing_error_start`, #1427/#1567) -- extended here to classes. Unlike
                # `function_data`, `class_data` has no `start_line` column, so this is a
                # coarser, file-level version (skip the whole file's extra_classes rather than
                # filtering individual occurrences by line): when a trailing error cascade is
                # detected at all, tree-sitter's real_classes for this file is unreliable enough
                # that any GitGalaxy-found class name absent from it can't be trusted as a
                # genuine false positive. Confirmed via roslyn/LanguageParser.cs: the cascade is
                # severe enough that `tree.root_node.type` itself becomes "ERROR" (not the
                # normal `compilation_unit`), so trailing_error_start resolves to line 1 -- a
                # file-level exclusion produces the identical outcome an occurrence-level one
                # would here, for all 8 of that file's real, correctly-found classes (including
                # the outer `LanguageParser` class itself, whose body spans the entire corrupted
                # region and so never resolves into a proper `class_declaration` node at all).
                if trailing_error_start is None and not blind_spot_ranges:
                    extra_cls = gg_classes - real_classes
                    metrics["extra_classes"] += len(extra_cls)
                    if verbose and extra_cls and len(extra_class_examples) < 8:
                        extra_class_examples.append((row["file_path"], sorted(extra_cls)[:5]))

                # #1849: tree-sitter's own class numbers, same reconciled ground truth, same
                # cascade-region exclusion GitGalaxy's extra_classes above already applies (set-
                # based comparison, same as GitGalaxy's -- class_data has no start_line to align
                # occurrences by).
                metrics["ts_found_classes"] += len(real_classes & raw_ts_classes)
                if trailing_error_start is None and not blind_spot_ranges:
                    ts_extra_cls = raw_ts_classes - real_classes
                    metrics["ts_extra_classes"] += len(ts_extra_cls)

                file_missing_names: set[str] = set()
                file_extra_names: set[str] = set()
                for name in real_funcs.keys() | gg_funcs_by_name.keys() | raw_ts_funcs.keys():
                    real_occs = sorted(real_funcs.get(name, []), key=lambda occ: occ[0])
                    gg_occs = sorted(gg_funcs_by_name.get(name, []), key=lambda occ: occ[0])
                    pairs, unmatched_real, unmatched_gg = _align_occurrences_by_line(real_occs, gg_occs)

                    raw_occs = sorted(raw_ts_funcs.get(name, []), key=lambda occ: occ[0])
                    ts_pairs, _ts_unmatched_real, unmatched_raw = _align_occurrences_by_line(real_occs, raw_occs)
                    if trailing_error_start is not None or blind_spot_ranges:
                        filtered_unmatched_raw = [
                            (raw_start, raw_args)
                            for raw_start, raw_args in unmatched_raw
                            if not any(start <= raw_start <= end for start, end in blind_spot_ranges)
                        ]
                        unmatched_raw = [
                            occ
                            for occ in filtered_unmatched_raw
                            if not (trailing_error_start is not None and occ[0] >= trailing_error_start)
                        ]
                    metrics["ts_found_functions"] += len(ts_pairs)
                    metrics["ts_extra_functions"] += len(unmatched_raw)

                    # #1427/#1567: a grammar parse-error cascade (see
                    # _find_trailing_error_cascade_start's docstring) leaves ground truth
                    # structurally blind to a whole trailing region of this file -- any
                    # GitGalaxy match there is unpairable by construction, not a real false
                    # positive, so it's dropped rather than counted as "extra". #1427 originally
                    # hand-listed 3 csharp names in `roslyn/LanguageParser.cs`; #1567 found that
                    # undersold the real scope (0 real_functions past line 5198 of 14680) and
                    # replaced it with this general, line-scoped, language-agnostic check.
                    if trailing_error_start is not None or blind_spot_ranges:
                        filtered_unmatched_gg = []
                        for gg_start, args in unmatched_gg:
                            # #1709: tree-sitter-fortran suffers cascading parser failures around deep `#ifdef` trees,
                            # leaving valid code blocks encapsulated in `ERROR` or `preproc_` nodes where
                            # tree-sitter is blind. GitGalaxy cleanly regexes these out anyway, resulting in
                            # false-positive "extra" functions. We mask these true-positive blind spots.
                            if any(start <= gg_start <= end for start, end in blind_spot_ranges):
                                continue

                            filtered_unmatched_gg.append((gg_start, args))
                        unmatched_gg = [
                            occ
                            for occ in filtered_unmatched_gg
                            if not (trailing_error_start is not None and occ[0] >= trailing_error_start)
                        ]

                    metrics["found_functions"] += len(pairs)
                    metrics["extra_functions"] += len(unmatched_gg)
                    if unmatched_real:
                        file_missing_names.add(name)
                    if unmatched_gg:
                        file_extra_names.add(name)

                    for real_occ, gg_occ in pairs:
                        metrics["args_comparable"] += 1
                        if real_occ[1] == gg_occ[1]:
                            metrics["args_exact_match"] += 1
                        elif verbose and len(args_mismatch_examples) < 10:
                            args_mismatch_examples.append(
                                f"{row['file_path']}::{name}  real={real_occ[1]} got={gg_occ[1]}"
                                f" (line {real_occ[0]} vs {gg_occ[0]})"
                            )
                        # #1849: tree-sitter's own args reading on this SAME pair -- a plain
                        # declaration-only count (no shell/perl body-aware fallback), reproducing
                        # Claim 1's "before" baseline (docs/why_gitgalaxy_beats_ast_here.md) as a
                        # live per-run metric. Shares args_comparable as its denominator so both
                        # bars are directly comparable on the chart.
                        ts_node = real_func_node_by_occ.get((name, real_occ[0]))
                        if ts_node is not None and _get_param_count_declaration_only(ts_node, lang) == real_occ[1]:
                            metrics["ts_args_exact_match"] += 1

                if verbose and file_missing_names and len(missing_examples) < 100:
                    missing_examples.append((row["file_path"], sorted(file_missing_names)))
                if verbose and file_extra_names and len(extra_examples) < 100:
                    extra_examples.append((row["file_path"], sorted(file_extra_names)))
        finally:
            conn.close()

    if verbose:
        metrics["_missing_examples"] = missing_examples
        metrics["_extra_examples"] = extra_examples
        metrics["_extra_class_examples"] = extra_class_examples
        metrics["_args_mismatch_examples"] = args_mismatch_examples
    return metrics


def load_baseline(lang: str) -> dict:
    baseline_path = _get_baseline_path(lang)
    if not baseline_path.exists():
        return {}
    with open(baseline_path, encoding="utf-8") as f:
        return json.load(f)


_GATED_METRICS = (
    ("found_functions", "higher_is_better"),
    ("extra_functions", "lower_is_better"),
    ("found_classes", "higher_is_better"),
    ("extra_classes", "lower_is_better"),
    ("args_exact_match", "higher_is_better"),
)
_GROUND_TRUTH_METRICS = ("corpus_path", "files_scanned", "real_functions", "real_classes")
_INFORMATIONAL_METRICS = ("args_comparable",)
_ALL_BASELINE_KEYS = (*[k for k, _ in _GATED_METRICS], *_GROUND_TRUTH_METRICS, *_INFORMATIONAL_METRICS)


def _regressions(current: dict, baseline: dict) -> list[str]:
    regressions = []
    for key, direction in _GATED_METRICS:
        if key not in baseline:
            continue
        cur, base = current[key], baseline[key]
        worse = cur < base if direction == "higher_is_better" else cur > base
        if worse:
            regressions.append(f"{key}: {base} -> {cur} ({direction.replace('_', ' ')}, this got worse)")
    return regressions


def _ground_truth_drift(current: dict, baseline: dict) -> list[str]:
    return [
        f"{key}: baseline={baseline[key]} current={current[key]}"
        for key in _GROUND_TRUTH_METRICS
        if key in baseline and baseline[key] != current[key]
    ]


def _print_report(current: dict, baseline: dict) -> None:
    print(f"{'metric':<20} {'baseline':>10} {'current':>10}")
    for key in _ALL_BASELINE_KEYS:
        if key == "corpus_path":
            continue
        print(f"{key:<20} {baseline.get(key, '-')!s:>10} {current.get(key)!s:>10}")

    if current.get("_missing_examples"):
        print("\nSample missing (real function `tree-sitter` found, GitGalaxy didn't):")
        for path, names in current["_missing_examples"]:
            print(f"  {path}: {names}")
    if current.get("_extra_examples"):
        print("\nSample extra (GitGalaxy reported a name `tree-sitter` has no record of):")
        for path, names in current["_extra_examples"]:
            print(f"  {path}: {names}")
    if current.get("_extra_class_examples"):
        print("\nSample extra classes (GitGalaxy reported a class `tree-sitter` has no record of):")
        for path, names in current["_extra_class_examples"]:
            print(f"  {path}: {names}")
    if current.get("_args_mismatch_examples"):
        print("\nSample args-count mismatches:")
        for line in current["_args_mismatch_examples"]:
            print(f"  {line}")


def run_full_report(lang: str) -> int:
    current = measure(lang, verbose=True)
    baseline = load_baseline(lang)

    _print_report(current, baseline)

    if not baseline:
        print("\ntree_sitter_accuracy_audit: no baseline committed yet -- run with --regenerate to create one.")
        return 1

    drift = _ground_truth_drift(current, baseline)
    if drift:
        print("\ntree_sitter_accuracy_audit: ground-truth metric(s) drifted (see SCOPE section for what this means):")
        for line in drift:
            print(f"  {line}")

    regressions = _regressions(current, baseline)
    if regressions:
        print(f"\ntree_sitter_accuracy_audit: {len(regressions)} regression(s) against the baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1

    print("\ntree_sitter_accuracy_audit: no regressions.")
    return 0


def run_ci_check(lang: str) -> int:
    current = measure(lang, verbose=False)
    baseline = load_baseline(lang)

    if not baseline:
        print(f"tree_sitter_accuracy_audit: no baseline committed for {lang} -- failing closed.")
        return 1

    drift = _ground_truth_drift(current, baseline)
    if drift:
        print("tree_sitter_accuracy_audit: ground-truth metric(s) drifted from the pinned corpus's expected values:")
        for line in drift:
            print(f"  {line}")
        print("This means the corpus changed. Investigate before regenerating.")
        return 1

    regressions = _regressions(current, baseline)
    if regressions:
        print(f"tree_sitter_accuracy_audit: {len(regressions)} regression(s) against the baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1

    improved = [k for k, d in _GATED_METRICS if k in baseline and current[k] != baseline[k]]
    if improved:
        print(
            f"tree_sitter_accuracy_audit: OK -- improved on {', '.join(improved)} (consider --regenerate to lock it in)."
        )
    else:
        print("tree_sitter_accuracy_audit: OK -- matches the committed baseline, no regressions.")
    return 0


def run_regenerate(lang: str) -> int:
    current = measure(lang, verbose=True)
    baseline = load_baseline(lang)

    _print_report(current, baseline)

    if baseline:
        regressions = _regressions(current, baseline)
        if regressions:
            print(f"\ntree_sitter_accuracy_audit: refusing to regenerate -- {len(regressions)} regression(s) present:")
            for line in regressions:
                print(f"  {line}")
            print("Fix the regression first, or if it's intentional/expected, explain why in the PR description.")
            return 1

    to_write = {k: current[k] for k in _ALL_BASELINE_KEYS}
    baseline_path = _get_baseline_path(lang)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\ntree_sitter_accuracy_audit: wrote new baseline to {baseline_path.relative_to(REPO_ROOT)}.")

    # generate_summary_table() reads committed baselines only (no live scan), so it's cheap and
    # correct to refresh it here every time -- this is what keeps the CI "summary table matches
    # committed baselines" check from being a second, easy-to-forget manual step that fails on a
    # push after --regenerate alone (see CI's own "Verify the summary table" step).
    if update_docstring_table():
        rel = _LANGUAGE_STANDARDS_PATH.relative_to(REPO_ROOT)
        print(f"tree_sitter_accuracy_audit: also updated the summary table in {rel} to match.")
    return 0


def _all_baseline_langs() -> list[str]:
    """Every language with a committed tests/tree_sitter_accuracy_baseline_<lang>.json, sorted."""
    prefix = "tree_sitter_accuracy_baseline_"
    return sorted(p.stem[len(prefix) :] for p in (REPO_ROOT / "tests").glob(f"{prefix}*.json"))


def run_all(mode_fn) -> int:
    """Runs a single-language mode function (run_ci_check/run_regenerate/run_full_report)
    across every baselined language, in one process. See `_all_baseline_langs`."""
    langs = _all_baseline_langs()
    failed = []
    for lang in langs:
        print(f"\n=== {lang} ===")
        if mode_fn(lang) != 0:
            failed.append(lang)

    print(f"\ntree_sitter_accuracy_audit --all: {len(langs)} language(s) checked.")
    if failed:
        print(f"tree_sitter_accuracy_audit --all: {len(failed)} FAILED: {', '.join(failed)}")
        return 1
    print("tree_sitter_accuracy_audit --all: all OK.")
    return 0


# ----------------------------------------------------------------------------
# --summary-table: regenerate the Markdown table in language_standards.py's
# docstring purely from committed baselines (no live scan, no corpus needed).
# ----------------------------------------------------------------------------

# #1295: css/html were decided PERMANENTLY out of scope for named class extraction --
# class_data's schema (class_name/inheritance_parents/method_count/state_entanglement) is
# OOP-shaped, and neither CSS selectors nor generic HTML elements fit it (see
# tests/extraction/how_to_extend_class_start_named_extraction.md's "Decided: not extending css
# or html" section for the full reasoning). Their class_recall/class_precision numbers are
# forced to N/A here rather than shown as a real "0.0%" -- css genuinely has real_classes=90
# (ground truth works fine), so a bare 0% would misleadingly read as "GitGalaxy tried and
# missed everything" rather than "GitGalaxy never attempts this by design". func_recall/
# func_precision are NOT touched by this set -- func_start extraction is in scope and
# genuinely measured for both languages.
_CLASS_EXTRACTION_OUT_OF_SCOPE = frozenset({"css", "html"})

_TABLE_BEGIN = "<!-- TREE_SITTER_ACCURACY_TABLE:BEGIN -->"
_TABLE_END = "<!-- TREE_SITTER_ACCURACY_TABLE:END -->"
_LANGUAGE_STANDARDS_PATH = REPO_ROOT / "gitgalaxy" / "standards" / "language_standards.py"


def _ratio_pct(numerator: int, denominator: int) -> Optional[float]:
    """None (-> "N/A") when the denominator is 0, same convention the baseline JSON itself uses."""
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def _fmt_pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value}%"


def generate_summary_table() -> str:
    """Builds the Markdown table from committed baselines only. A language with no committed
    baseline is simply absent -- unlike the hand-written table this replaced, it never emits a
    fabricated all-N/A row for a language nobody has actually measured yet."""
    lines = [
        "| Language | Func Recall | Func Precision | Class Recall | Class Precision |",
        "| -------- | ----------- | -------------- | ------------ | --------------- |",
    ]
    for lang in _all_baseline_langs():
        b = load_baseline(lang)
        if not b:
            continue
        func_recall = _fmt_pct(_ratio_pct(b["found_functions"], b["real_functions"]))
        func_precision = _fmt_pct(_ratio_pct(b["found_functions"], b["found_functions"] + b["extra_functions"]))
        if lang in _CLASS_EXTRACTION_OUT_OF_SCOPE:
            class_recall = class_precision = "N/A"
        else:
            class_recall = _fmt_pct(_ratio_pct(b["found_classes"], b["real_classes"]))
            class_precision = _fmt_pct(_ratio_pct(b["found_classes"], b["found_classes"] + b["extra_classes"]))
        lines.append(f"| {lang.title()} | {func_recall} | {func_precision} | {class_recall} | {class_precision} |")
    return "\n".join(lines)


def update_docstring_table() -> bool:
    """Rewrites the table between the BEGIN/END markers in language_standards.py in place.
    Returns True if the file's content actually changed."""
    text = _LANGUAGE_STANDARDS_PATH.read_text(encoding="utf-8")
    if _TABLE_BEGIN not in text or _TABLE_END not in text:
        sys.exit(
            f"tree_sitter_accuracy_audit: markers {_TABLE_BEGIN!r}/{_TABLE_END!r} not found in "
            f"{_LANGUAGE_STANDARDS_PATH.relative_to(REPO_ROOT)} -- was the docstring edited by hand?"
        )
    replacement = f"{_TABLE_BEGIN}\n{generate_summary_table()}\n{_TABLE_END}"
    pattern = re.compile(re.escape(_TABLE_BEGIN) + r".*?" + re.escape(_TABLE_END), re.DOTALL)
    new_text = pattern.sub(replacement, text, count=1)

    changed = new_text != text
    if changed:
        _LANGUAGE_STANDARDS_PATH.write_text(new_text, encoding="utf-8")
    return changed


def run_summary_table() -> int:
    changed = update_docstring_table()
    rel = _LANGUAGE_STANDARDS_PATH.relative_to(REPO_ROOT)
    if changed:
        print(f"tree_sitter_accuracy_audit: updated the summary table in {rel}.")
    else:
        print(f"tree_sitter_accuracy_audit: {rel} already matches the committed baselines, no change.")
    return 0


# ----------------------------------------------------------------------------
# --history: live-measure every baselined language and append one row each to
# a growing CSV, for graphing accuracy trends over time across pushes.
# ----------------------------------------------------------------------------

_HISTORY_PATH = REPO_ROOT / "docs" / "self_scan" / "tree_sitter_accuracy_history.csv"
_HISTORY_FIELDS = [
    "timestamp_utc",
    "commit_sha",
    "language",
    "files_scanned",
    "real_functions",
    "found_functions",
    "extra_functions",
    "real_classes",
    "found_classes",
    "extra_classes",
    "args_comparable",
    "args_exact_match",
    "func_recall_pct",
    "func_precision_pct",
    "class_recall_pct",
    "class_precision_pct",
    # #1849: tree-sitter's own numbers, same reconciled ground truth -- see measure()'s
    # raw_ts_funcs/raw_ts_classes docstring comment for what does and doesn't move these.
    "ts_found_functions",
    "ts_extra_functions",
    "ts_found_classes",
    "ts_extra_classes",
    "ts_args_exact_match",
    "ts_func_recall_pct",
    "ts_func_precision_pct",
    "ts_class_recall_pct",
    "ts_class_precision_pct",
    "ts_args_match_pct",
    # GitGalaxy-only rows (see _gg_only_langs/measure_gg_only): languages with no NODE_MAPS entry
    # at all, so every ts_*/real_*/extra_*/args_* field above is meaningless and stays 0 -- only
    # found_functions/found_classes carry real data, reused as-is (a "found" count is exactly
    # what a plain GitGalaxy-only scan produces). gg_only=1 flags the row for the chart's special
    # rendering path; gg_only_data_available=0 additionally means language-crucible has no corpus
    # for this language yet (e.g. ada), i.e. even found_functions/found_classes are unmeasured.
    "gg_only",
    "gg_only_data_available",
]


def _csv_int(row: dict[str, str], field: str) -> int:
    """int(row[field]), but a missing or blank cell reads as 0 instead of crashing -- covers rows
    written before a column was added to `_HISTORY_FIELDS` (see `_migrate_history_csv_schema`:
    those rows get backfilled with "" for the new columns, not a fabricated 0 in the CSV itself,
    since they genuinely weren't measured -- this is just what a *reader* does with that blank)."""
    value = row.get(field)
    return int(value) if value not in (None, "") else 0


def _migrate_history_csv_schema() -> None:
    """Rewrites docs/self_scan/tree_sitter_accuracy_history.csv in place if its on-disk header
    doesn't match the current `_HISTORY_FIELDS` (e.g. #1849 added five ts_* columns to an
    already-accumulating file). `csv.DictWriter` in append mode writes fields in `fieldnames`
    order with no regard for whatever header already exists on disk -- appending new-schema rows
    under an old-schema header silently desyncs the file (old header column count != new rows'
    value count), which makes the new columns permanently unreadable by name via a plain
    `csv.DictReader`, not just untidy. A no-op when the header already matches (the common case:
    every run after the first one following a schema change)."""
    if not _HISTORY_PATH.exists():
        return
    with open(_HISTORY_PATH, newline="", encoding="utf-8") as f:
        existing_header = next(csv.reader(f), [])
    if existing_header == _HISTORY_FIELDS:
        return
    with open(_HISTORY_PATH, newline="", encoding="utf-8") as f:
        existing_rows = list(csv.DictReader(f))
    with open(_HISTORY_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HISTORY_FIELDS, restval="")
        writer.writeheader()
        writer.writerows(existing_rows)
    print(
        f"tree_sitter_accuracy_audit: migrated {_HISTORY_PATH.relative_to(REPO_ROOT)} to the current "
        f"column set ({len(existing_rows)} existing row(s) backfilled with blank cells for new columns)."
    )


def _current_commit_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _batch_matches_measured(langs: list[str], measured: dict[str, dict], previous: dict[str, dict[str, int]]) -> bool:
    """True when a freshly `measure()`d set of languages is identical (every _HISTORY_RAW_FIELDS
    value, for the same set of languages) to the previous batch loaded by
    `_try_load_latest_history_batch`. A language being added or dropped counts as a change even
    if every other language is untouched -- the chart always wants a full, consistent snapshot
    per batch (see `generate_chart_svg`), so a partial "only what changed" batch isn't an option."""
    if set(langs) != set(previous.keys()):
        return False
    return all(measured[lang][field] == previous[lang][field] for lang in langs for field in _HISTORY_RAW_FIELDS)


def _history_row(lang: str, raw: dict[str, int]) -> dict[str, Any]:
    """Builds one full _HISTORY_FIELDS-shaped row (percentage fields included) from a raw-count
    dict already shaped like _HISTORY_RAW_FIELDS. Shared by both tree-sitter-comparable languages
    and gg_only languages (see _gg_only_langs) -- for the latter, every *_pct field naturally
    comes out None/blank via _ratio_pct's own "denominator <= 0" rule, since all the comparison
    denominators (real_functions, found_functions+extra_functions, etc.) are 0 by construction
    for a row with no tree-sitter side at all. No gg_only-specific branching needed here."""
    return {
        "files_scanned": raw["files_scanned"],
        "real_functions": raw["real_functions"],
        "found_functions": raw["found_functions"],
        "extra_functions": raw["extra_functions"],
        "real_classes": raw["real_classes"],
        "found_classes": raw["found_classes"],
        "extra_classes": raw["extra_classes"],
        "args_comparable": raw["args_comparable"],
        "args_exact_match": raw["args_exact_match"],
        "func_recall_pct": _ratio_pct(raw["found_functions"], raw["real_functions"]),
        "func_precision_pct": _ratio_pct(raw["found_functions"], raw["found_functions"] + raw["extra_functions"]),
        "class_recall_pct": _ratio_pct(raw["found_classes"], raw["real_classes"]),
        "class_precision_pct": _ratio_pct(raw["found_classes"], raw["found_classes"] + raw["extra_classes"]),
        "ts_found_functions": raw["ts_found_functions"],
        "ts_extra_functions": raw["ts_extra_functions"],
        "ts_found_classes": raw["ts_found_classes"],
        "ts_extra_classes": raw["ts_extra_classes"],
        "ts_args_exact_match": raw["ts_args_exact_match"],
        "ts_func_recall_pct": _ratio_pct(raw["ts_found_functions"], raw["real_functions"]),
        "ts_func_precision_pct": _ratio_pct(
            raw["ts_found_functions"], raw["ts_found_functions"] + raw["ts_extra_functions"]
        ),
        "ts_class_recall_pct": _ratio_pct(raw["ts_found_classes"], raw["real_classes"]),
        "ts_class_precision_pct": _ratio_pct(
            raw["ts_found_classes"], raw["ts_found_classes"] + raw["ts_extra_classes"]
        ),
        "ts_args_match_pct": _ratio_pct(raw["ts_args_exact_match"], raw["args_comparable"]),
        "gg_only": raw["gg_only"],
        "gg_only_data_available": raw["gg_only_data_available"],
    }


def run_history() -> int:
    """Live-measures (not baseline-read) every language that has BOTH a committed baseline and
    a NODE_MAPS entry, PLUS every gg_only language (see _gg_only_langs) -- languages GitGalaxy
    extracts functions from but that have no tree-sitter comparison at all, either not yet mapped
    or permanently excluded (NODE_MAPS's own comment block explains which and why). Intentionally
    never writes to the gating baseline JSON files -- this is purely additive, observational data
    for graphing.

    Skips appending entirely when the fresh measurement is byte-for-byte identical to the most
    recent recorded batch (see `_batch_matches_measured`) -- e.g. a push that touched detector.py
    for an unrelated language, or a docs-only change that happened to match one of the workflow's
    trigger paths, shouldn't manufacture a duplicate row (or a pointless chart.svg re-render/PR)
    just because the job ran. This is what makes --history/--chart "adaptive": the CSV and chart
    only move when a language's measured accuracy actually moved."""
    _migrate_history_csv_schema()
    langs = [lang for lang in _all_baseline_langs() if lang in NODE_MAPS]
    skipped = [lang for lang in _all_baseline_langs() if lang not in NODE_MAPS]
    if skipped:
        print(
            f"tree_sitter_accuracy_audit --history: skipping {', '.join(skipped)} "
            f"(baseline committed but no NODE_MAPS entry to re-scan)."
        )
    gg_only_langs = _gg_only_langs()

    raw: dict[str, dict[str, int]] = {}
    for lang in langs:
        print(f"tree_sitter_accuracy_audit --history: measuring {lang}...")
        m = measure(lang, verbose=False)
        raw[lang] = {field: m[field] for field in _HISTORY_RAW_FIELDS if field in m}
        raw[lang]["gg_only"] = 0
        raw[lang]["gg_only_data_available"] = 1

    gg_only_zero_fields = tuple(
        f
        for f in _HISTORY_RAW_FIELDS
        if f not in ("files_scanned", "found_functions", "found_classes", "gg_only", "gg_only_data_available")
    )
    for lang in gg_only_langs:
        print(
            f"tree_sitter_accuracy_audit --history: measuring {lang} (GitGalaxy-only, no tree-sitter grammar mapped)..."
        )
        gm = measure_gg_only(lang)
        row: dict[str, int] = dict.fromkeys(gg_only_zero_fields, 0)
        if gm is None:
            row.update(files_scanned=0, found_functions=0, found_classes=0, gg_only=1, gg_only_data_available=0)
        else:
            row.update(
                files_scanned=gm["files_scanned"],
                found_functions=gm["found_functions"],
                found_classes=gm["found_classes"],
                gg_only=1,
                gg_only_data_available=1,
            )
        raw[lang] = row

    all_langs = langs + gg_only_langs
    previous = _try_load_latest_history_batch()
    if previous is not None and _batch_matches_measured(all_langs, raw, previous[2]):
        print(
            f"tree_sitter_accuracy_audit --history: measured results match the most recent batch "
            f"({previous[0]}) exactly -- skipping, no row appended, chart left as-is."
        )
        return 0

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    commit_sha = _current_commit_sha()

    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not _HISTORY_PATH.exists()
    with open(_HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HISTORY_FIELDS)
        if write_header:
            writer.writeheader()
        for lang in all_langs:
            writer.writerow(
                {
                    "timestamp_utc": timestamp,
                    "commit_sha": commit_sha,
                    "language": lang,
                    **_history_row(lang, raw[lang]),
                }
            )

    print(
        f"tree_sitter_accuracy_audit --history: appended {len(all_langs)} row(s) to "
        f"{_HISTORY_PATH.relative_to(REPO_ROOT)} ({len(langs)} tree-sitter-compared, {len(gg_only_langs)} GitGalaxy-only)."
    )
    return 0


# ----------------------------------------------------------------------------
# --chart: render the most recent --history run as a small-multiples SVG bar
# chart, reading only the accumulated CSV (no live scan, no corpus needed).
# ----------------------------------------------------------------------------

_CHART_PATH = REPO_ROOT / "docs" / "self_scan" / "tree_sitter_accuracy_chart.svg"


class _ChartMetric(NamedTuple):
    """One panel's worth of definition: GitGalaxy's (num, den) fields and tree-sitter's own
    (num, den) fields for the SAME metric, scored against the same reconciled ground truth (see
    measure()'s raw_ts_funcs/raw_ts_classes comment, #1849). num/den are raw-count fields from
    _load_latest_history_batch's row dict, read directly off each bar so the chart can show e.g.
    "0/117" instead of just "0%" (a percentage alone doesn't say whether it's backed by 4 samples
    or 400). den is either a real row key or one of the synthetic "__..._plus_extra_<x>__"
    markers _metric_num_den resolves (found+extra isn't a field the CSV stores directly)."""

    key: str
    title: str
    gg_num: str
    gg_den: str
    ts_num: str
    ts_den: str


_CHART_METRICS = (
    _ChartMetric(
        "func_recall_pct", "Func Recall", "found_functions", "real_functions", "ts_found_functions", "real_functions"
    ),
    _ChartMetric(
        "func_precision_pct",
        "Func Precision",
        "found_functions",
        "__found_plus_extra_functions__",
        "ts_found_functions",
        "__ts_found_plus_extra_functions__",
    ),
    _ChartMetric(
        "class_recall_pct", "Class Recall", "found_classes", "real_classes", "ts_found_classes", "real_classes"
    ),
    _ChartMetric(
        "class_precision_pct",
        "Class Precision",
        "found_classes",
        "__found_plus_extra_classes__",
        "ts_found_classes",
        "__ts_found_plus_extra_classes__",
    ),
    # Args has only one ratio in the data (exact-match), not a recall/precision pair -- labeled
    # distinctly rather than forced into that framing.
    _ChartMetric(
        "args_match_pct",
        "Args Exact-Match",
        "args_exact_match",
        "args_comparable",
        "ts_args_exact_match",
        "args_comparable",
    ),
)


def _metric_num_den(row: dict[str, int], num_field: str, den_field: str) -> tuple[int, int]:
    """den_field is either a real key in `row` or one of the four synthetic
    "__[ts_]found_plus_extra_<x>__" markers _CHART_METRICS uses for the precision denominators
    (found + extra isn't a field the CSV stores directly)."""
    num = row[num_field]
    if den_field == "__found_plus_extra_functions__":
        den = row["found_functions"] + row["extra_functions"]
    elif den_field == "__found_plus_extra_classes__":
        den = row["found_classes"] + row["extra_classes"]
    elif den_field == "__ts_found_plus_extra_functions__":
        den = row["ts_found_functions"] + row["ts_extra_functions"]
    elif den_field == "__ts_found_plus_extra_classes__":
        den = row["ts_found_classes"] + row["ts_extra_classes"]
    else:
        den = row[den_field]
    return num, den


# Bar fill is now a value-driven red(low)->blue(high) hue-sweep LUT (see _rainbow_hex), a
# deliberate request overriding the dataviz skill's own default ("never a rainbow" -- rainbow
# LUTs aren't perceptually uniform and are hard on CVD readers). Kept to ONE fixed hex per value
# rather than separate light/dark variants -- 150+ unique data-driven colors made a real per-mode
# LUT impractical, so saturation/lightness were picked to read reasonably on both surfaces
# instead. Everything else (text, surface, stripes, axis) stays properly theme-aware.
_CHART_STYLE = """<style><![CDATA[
  /* No CSS custom properties -- some SVG renderers in the docs pipeline (confirmed: Inkscape's
     CSS parser) don't support var()/nested :root under @media, and silently fail to parse the
     whole block rather than degrading gracefully. Plain class redeclarations under the media
     query are more portable and render identically in real browsers. CDATA-wrapped because this
     text otherwise contains a literal "style" tag-like substring that trips strict XML parsers
     (confirmed: Inkscape read it as a nested element and broke tag matching). */
  .surface { fill: #fcfcfb; }
  .title { fill: #0b0b0b; font-weight: 600; font-size: 15px; }
  .subtitle { fill: #52514e; font-size: 11px; }
  .scope-note { fill: #52514e; font-size: 9.5px; }
  .legend-label { fill: #52514e; font-size: 10px; }
  .col-title { fill: #0b0b0b; font-weight: 600; font-size: 11px; }
  .row-label { fill: #0b0b0b; font-size: 11px; }
  .value-label { fill: #52514e; font-size: 10px; font-variant-numeric: tabular-nums; }
  .na-dash { fill: #52514e; font-size: 10px; opacity: 0.55; }
  .stripe { fill: #f1f0ed; }
  .axis { stroke: #e4e2dd; stroke-width: 1; }
  .footer { fill: #52514e; font-size: 9px; }
  .diff-outline { fill: none; stroke: #c9971f; stroke-width: 1.25; }
  .badge-gg { fill: #0d9488; }
  .badge-ts { fill: #7c3aed; }
  .badge-text { fill: #ffffff; font-weight: 700; font-size: 8px; text-anchor: middle; }
  .bar-neutral { fill: #9a988f; }
  @media (prefers-color-scheme: dark) {
    .surface { fill: #1a1a19; }
    .title { fill: #ffffff; }
    .subtitle { fill: #c3c2b7; }
    .scope-note { fill: #c3c2b7; }
    .legend-label { fill: #c3c2b7; }
    .col-title { fill: #ffffff; }
    .row-label { fill: #ffffff; }
    .value-label { fill: #c3c2b7; }
    .na-dash { fill: #c3c2b7; }
    .stripe { fill: #242422; }
    .axis { stroke: #33322f; }
    .footer { fill: #c3c2b7; }
    .diff-outline { stroke: #e0ab35; }
    .badge-gg { fill: #14b8a6; }
    .badge-ts { fill: #a78bfa; }
    .bar-neutral { fill: #7a7972; }
  }
]]></style>
"""


def _hsl_to_hex(h: float, s: float, lightness: float) -> str:
    h = (h % 360.0) / 360.0

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        t = t % 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        r = g = b = lightness
    else:
        q = lightness * (1 + s) if lightness < 0.5 else lightness + s - lightness * s
        p = 2 * lightness - q
        r = hue_to_rgb(p, q, h + 1 / 3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1 / 3)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def _rainbow_hex(value: float) -> str:
    """0 -> red, 100 -> blue, sweeping through orange/yellow/green/cyan in between (HSL hue
    0deg->240deg). Fixed saturation/lightness -- see _CHART_STYLE's comment on why this is one
    LUT shared by both display modes rather than a light/dark pair."""
    hue = max(0.0, min(100.0, value)) / 100.0 * 240.0
    return _hsl_to_hex(hue, 0.68, 0.50)


def _rainbow_gradient_defs(stops: int = 13) -> str:
    stops_svg = "".join(
        f'<stop offset="{i / (stops - 1) * 100:.1f}%" stop-color="{_rainbow_hex(i / (stops - 1) * 100)}"/>'
        for i in range(stops)
    )
    return f'<linearGradient id="rainbow-legend" x1="0%" y1="0%" x2="100%" y2="0%">{stops_svg}</linearGradient>'


# Shared by _load_latest_history_batch/_try_load_latest_history_batch (what --chart renders) AND
# run_history's own unchanged-batch check (see _batch_matches_measured) -- includes files_scanned,
# which the chart itself never plots, so that a corpus-size change (a language-crucible bump) is
# still treated as "new data" rather than silently compared away.
_HISTORY_RAW_FIELDS = (
    "files_scanned",
    "real_functions",
    "found_functions",
    "extra_functions",
    "real_classes",
    "found_classes",
    "extra_classes",
    "args_comparable",
    "args_exact_match",
    "ts_found_functions",
    "ts_extra_functions",
    "ts_found_classes",
    "ts_extra_classes",
    "ts_args_exact_match",
    "gg_only",
    "gg_only_data_available",
)


def _try_load_latest_history_batch() -> Optional[tuple[str, str, dict[str, dict[str, int]]]]:
    """Same as `_load_latest_history_batch` but returns None instead of exiting when the CSV
    doesn't exist yet or is empty, so `run_history` can use it to detect "first run ever" and
    skip the unchanged-batch comparison rather than treating an empty file as an error."""
    if not _HISTORY_PATH.exists():
        return None
    with open(_HISTORY_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None

    latest_ts = max(row["timestamp_utc"] for row in rows)
    latest_rows = [row for row in rows if row["timestamp_utc"] == latest_ts]
    commit_sha = latest_rows[0]["commit_sha"]
    data = {row["language"]: {field: _csv_int(row, field) for field in _HISTORY_RAW_FIELDS} for row in latest_rows}
    return latest_ts, commit_sha, data


def _load_latest_history_batch() -> tuple[str, str, dict[str, dict[str, int]]]:
    """Returns (timestamp_utc, commit_sha, {lang: {raw_count_key: int}}) for the most recent
    batch -- the rows sharing the max timestamp_utc -- in the history CSV. Returns raw counts
    (not pre-computed percentages) so the chart can show a metric's actual sample size (e.g.
    "0/117", not just "0%") -- a bare percentage reads identically whether it's backed by 4
    samples or 400. Unlike `_try_load_latest_history_batch`, --chart has nothing to render
    without a real batch, so a missing/empty CSV stays a hard failure here."""
    batch = _try_load_latest_history_batch()
    if batch is None:
        sys.exit(
            f"tree_sitter_accuracy_audit: {_HISTORY_PATH.relative_to(REPO_ROOT)} doesn't exist yet or is empty "
            f"-- run --history first."
        )
    return batch


def generate_chart_svg() -> str:
    """Small multiples: one independent panel per metric in _CHART_METRICS. #1849: each language
    renders as TWO stacked bars per panel -- GitGalaxy on top, tree-sitter's own raw reading on
    the bottom, both scored against the SAME reconciled ground truth (measure()'s real_funcs/
    real_classes; see that function's raw_ts_funcs comment).

    Rows share ONE alphabetical language order across all five panels, printed ONCE in a shared
    label column at the far left rather than repeated in every panel (previously each panel had
    its own label column AND was independently ranked by GitGalaxy's value, which put a given
    language at a different row in every column -- useful for "what's the best/worst language on
    this one metric" but actively hostile to "pick a language, see all five of its numbers at a
    glance", which is the more common way to actually read this chart). A continuous full-width
    stripe band (drawn once, behind every panel) reinforces the same row across the panel gaps so
    the eye doesn't lose it crossing from one panel to the next.

    Whenever a language's two bars in one panel actually differ (both real, non-N/A values, not
    equal), the whole cell gets an amber outline plus a small "G"/"T" badge in a dedicated gutter
    at the start of the panel -- whichever tool scored higher on that specific metric, letter AND
    color (not color alone, for CVD readers) so a difference is legible even skimming past the
    bars themselves. Bar fill is still a red(low)->blue(high) hue-sweep LUT keyed to that bar's
    OWN value (see _rainbow_hex) -- color still encodes magnitude for each bar independently; a
    bar's vertical position (top/bottom of its row band) encodes which tool it is.

    Value labels show the raw fraction ("0/117"), not a bare percentage -- a percentage alone
    looks identical whether it's backed by 4 samples or 400, and reads as "failing" even where
    the underlying gap is a handful of missed matches on a thin corpus. The scope notes under the
    title exist for the same reason: this chart measures ONLY func_start/args/class_start name
    extraction, not GitGalaxy's structural-signature risk rules, and without that context a wall
    of red bars reads as "the product is failing" rather than "this one narrow feature has known,
    already-triaged gaps." One of those notes explains the recall panels specifically: for most
    languages tree-sitter's own recall reads 100% by construction (ground truth is walked from its
    own tree, so it can't miss what it defines), EXCEPT csharp/fortran/rust, where already-verified
    blind-spot/cascade regions are promoted into ground truth (measure()'s Phase 2 promotion step)
    so tree-sitter's real recall loss there (Claims 3/6/7) shows up as a genuine gap instead of
    reading artificially perfect."""
    timestamp, commit_sha, data = _load_latest_history_batch()
    langs_all = sorted(data.keys())
    n = len(langs_all)
    gg_only_count = sum(1 for lang in langs_all if data[lang].get("gg_only"))

    shared_label_col_w = 112  # wide enough for "embedded_python", the longest current name
    badge_col_w = 15  # per-panel gutter for the G/T "who scored higher here" stamp
    bar_col_w = 158
    panel_gap = 28
    row_h = 28  # tall enough for two stacked sub-bars (GitGalaxy on top, tree-sitter below)
    bar_h = 8
    sub_gap = 2
    header_h = 34
    top_margin = 164  # headroom for title + six-line scope note + color-scale legend
    bottom_margin = 56  # three footer lines
    left_margin = 16
    right_margin = 16
    bar_max_w = bar_col_w - 66  # leaves room for a fraction like "1147/1152" riding the bar's tip

    panel_w = badge_col_w + bar_col_w
    n_panels = len(_CHART_METRICS)
    bars_start_x = left_margin + shared_label_col_w
    width = bars_start_x + n_panels * panel_w + (n_panels - 1) * panel_gap + right_margin
    height = top_margin + header_h + n * row_h + bottom_margin
    rows_top = top_margin + header_h

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        _CHART_STYLE,
        f"<defs>{_rainbow_gradient_defs()}</defs>",
        f'<rect class="surface" x="0" y="0" width="{width}" height="{height}"/>',
        f'<text class="title" x="{left_margin}" y="20">Tree-sitter Accuracy by Language -- '
        f"GitGalaxy vs. Tree-sitter, Most Recent Run</text>",
        f'<text class="subtitle" x="{left_margin}" y="36">{timestamp} &#183; commit {commit_sha[:7]} &#183; '
        f"{n} languages ({n - gg_only_count} tree-sitter-compared, {gg_only_count} GitGalaxy-only) &#183; "
        f"source: docs/self_scan/tree_sitter_accuracy_history.csv</text>",
        f'<text class="scope-note" x="{left_margin}" y="52">Measures func_start/args/class_start NAME '
        f"extraction only -- NOT GitGalaxy's structural-signature risk rules (branch/io/safety_bypasses/"
        f"etc.), which are hardened and tested separately.</text>",
        f'<text class="scope-note" x="{left_margin}" y="64">Value labels are raw counts (found/real or '
        f"found/found+extra), not just a percentage, so each bar's sample size is visible at a glance.</text>",
        f'<text class="scope-note" x="{left_margin}" y="76">css and html show n/a on the class panels '
        f"by DESIGN, not as an unmeasured gap -- named class extraction was decided permanently out "
        f"of scope for them (epic #1295): their class_start targets selectors/tags, not OOP-shaped "
        f"entities. See tests/extraction/how_to_extend_class_start_named_extraction.md.</text>",
        f'<text class="scope-note" x="{left_margin}" y="88">Each language: TOP bar = GitGalaxy, BOTTOM '
        f"bar = tree-sitter's own raw reading -- both scored against the same reconciled ground truth "
        f"(docs/why_gitgalaxy_beats_ast_here.md). Rows share ONE alphabetical order across all five "
        f"panels so a language's numbers can be read straight across.</text>",
        f'<text class="scope-note" x="{left_margin}" y="100">Tree-sitter\'s recall panels read 100% for most '
        f"languages by construction (ground truth is walked from its own tree) -- EXCEPT csharp/fortran/rust, "
        f"where source-verified parse-error-cascade/opaque-macro regions (Claims 3/6/7) are promoted into "
        f"ground truth, so a real recall gap shows there instead (#1849).</text>",
        f'<text class="scope-note" x="{left_margin}" y="112">GitGalaxy-only languages (gray bar, no tree-sitter '
        f"grammar mapped -- see NODE_MAPS's own comment for which and why) show a plain found-count instead of "
        f'a scored ratio; "awaiting data" means language-crucible has no corpus for that language yet.</text>',
        f'<rect x="{left_margin}" y="124" width="140" height="8" rx="2" fill="url(#rainbow-legend)"/>',
        f'<text class="legend-label" x="{left_margin}" y="140">0%</text>',
        f'<text class="legend-label" x="{left_margin + 140}" y="140" text-anchor="end">100% (bar color = value)</text>',
        f'<circle cx="{left_margin + 220}" cy="134" r="6" class="badge-gg"/>',
        f'<text class="badge-text" x="{left_margin + 220}" y="136.5">G</text>',
        f'<text class="legend-label" x="{left_margin + 232}" y="140">GitGalaxy scored higher</text>',
        f'<circle cx="{left_margin + 360}" cy="134" r="6" class="badge-ts"/>',
        f'<text class="badge-text" x="{left_margin + 360}" y="136.5">T</text>',
        f'<text class="legend-label" x="{left_margin + 372}" y="140">Tree-sitter scored higher (outlined cell)</text>',
        f'<rect x="{left_margin + 620}" y="130" width="24" height="8" rx="2" class="bar-neutral"/>',
        f'<text class="legend-label" x="{left_margin + 650}" y="140">GitGalaxy-only found-count (no tree-sitter side)</text>',
    ]

    # Shared row order: plain alphabetical (langs_all is already sorted), identical in every
    # panel -- see docstring for why this replaced the old per-panel value ranking. Striping and
    # the language-name label are drawn ONCE here (not per panel): striping spans the full chart
    # width behind every panel so the same row stays visually continuous across the panel gaps,
    # and a single shared label column means a language's name isn't repeated five times.
    full_width = width - left_margin - right_margin
    label_x = left_margin + shared_label_col_w - 8
    for i, lang in enumerate(langs_all):
        row_y = rows_top + i * row_h
        if i % 2 == 1:
            parts.append(f'<rect class="stripe" x="{left_margin}" y="{row_y}" width="{full_width}" height="{row_h}"/>')
        label_y = row_y + row_h / 2 + 3.5
        parts.append(f'<text class="row-label" x="{label_x}" y="{label_y:.1f}" text-anchor="end">{lang}</text>')

    for j, m in enumerate(_CHART_METRICS):
        panel_x = bars_start_x + j * (panel_w + panel_gap)
        col_x = panel_x + badge_col_w

        gg_fractions: dict[str, tuple[int, int]] = {}
        gg_values: dict[str, Optional[float]] = {}
        ts_fractions: dict[str, tuple[int, int]] = {}
        ts_values: dict[str, Optional[float]] = {}
        # GG-only languages (see _gg_only_langs): no tree-sitter side at all, so gg_values/
        # ts_values stay None for them (nothing to score as a ratio) -- gg_count instead carries
        # a raw found-count for the one or two panels where that's meaningful (Func Recall always;
        # Class Recall only if this language's own class_start rule exists at all), rendered as a
        # distinct neutral full-width bar rather than a red->blue scored one.
        gg_count: dict[str, Optional[int]] = {}
        for lang in langs_all:
            row = data[lang]
            if row.get("gg_only"):
                gg_fractions[lang] = (0, 0)
                ts_fractions[lang] = (0, 0)
                ts_values[lang] = None
                gg_values[lang] = None
                if not row.get("gg_only_data_available"):
                    gg_count[lang] = None
                elif m.key == "func_recall_pct":
                    gg_count[lang] = row["found_functions"]
                elif m.key == "class_recall_pct" and LANGUAGE_DEFINITIONS.get(lang, {}).get("rules", {}).get(
                    "class_start"
                ):
                    gg_count[lang] = row["found_classes"]
                else:
                    gg_count[lang] = None
                continue

            gg_num, gg_den = _metric_num_den(row, m.gg_num, m.gg_den)
            ts_num, ts_den = _metric_num_den(row, m.ts_num, m.ts_den)
            gg_fractions[lang] = (gg_num, gg_den)
            ts_fractions[lang] = (ts_num, ts_den)
            gg_count[lang] = None
            # Force N/A on the class panels for languages decided permanently out of scope for
            # named class extraction (see _CLASS_EXTRACTION_OUT_OF_SCOPE) -- a bare 0% there
            # would misread as an unaddressed gap rather than a documented design decision.
            if m.key.startswith("class_") and lang in _CLASS_EXTRACTION_OUT_OF_SCOPE:
                gg_values[lang] = None
                ts_values[lang] = None
            else:
                gg_values[lang] = _ratio_pct(gg_num, gg_den)
                ts_values[lang] = _ratio_pct(ts_num, ts_den)

        parts.append(f'<text class="col-title" x="{col_x}" y="{top_margin + header_h - 12}">{m.title}</text>')
        parts.append(f'<line class="axis" x1="{col_x}" y1="{rows_top}" x2="{col_x}" y2="{rows_top + n * row_h}"/>')

        for i, lang in enumerate(langs_all):
            row_y = rows_top + i * row_h

            # Every-difference highlight: whenever both tools have a real (non-N/A) value for
            # this language+panel and they don't match exactly, outline the cell and stamp which
            # tool scored higher -- "G"/"T", not just a color, so it reads fine without relying on
            # color perception alone. Ties (equal values) get neither: nothing to call out. GG-only
            # rows never reach here (ts_val is always None for them), by construction.
            gg_val, ts_val = gg_values[lang], ts_values[lang]
            if gg_val is not None and ts_val is not None and gg_val != ts_val:
                parts.append(
                    f'<rect class="diff-outline" x="{panel_x + 0.75:.1f}" y="{row_y + 0.75:.1f}" '
                    f'width="{panel_w - 1.5:.1f}" height="{row_h - 1.5:.1f}" rx="3"/>'
                )
                winner, badge_class = ("G", "badge-gg") if gg_val > ts_val else ("T", "badge-ts")
                badge_cx = panel_x + badge_col_w / 2
                badge_cy = row_y + row_h / 2
                parts.append(f'<circle cx="{badge_cx:.1f}" cy="{badge_cy:.1f}" r="6" class="{badge_class}"/>')
                parts.append(f'<text class="badge-text" x="{badge_cx:.1f}" y="{badge_cy + 2.5:.1f}">{winner}</text>')

            gg_bar_y = row_y + (row_h - 2 * bar_h - sub_gap) / 2
            ts_bar_y = gg_bar_y + bar_h + sub_gap

            gg_text_y = gg_bar_y + bar_h / 2 + 3.5
            if gg_count.get(lang) is not None:
                parts.append(
                    f'<rect x="{col_x}" y="{gg_bar_y:.1f}" width="{bar_max_w:.1f}" height="{bar_h}" rx="2.5" '
                    f'class="bar-neutral"/>'
                )
                parts.append(
                    f'<text class="value-label" x="{col_x + bar_max_w + 5:.1f}" y="{gg_text_y:.1f}">'
                    f"{gg_count[lang]} found</text>"
                )
            elif gg_val is None:
                parts.append(f'<text class="na-dash" x="{col_x + 6}" y="{gg_text_y:.1f}">n/a</text>')
            else:
                num, den = gg_fractions[lang]
                bar_w = max(1.5, (gg_val / 100.0) * bar_max_w)
                parts.append(
                    f'<rect x="{col_x}" y="{gg_bar_y:.1f}" width="{bar_w:.1f}" height="{bar_h}" rx="2.5" '
                    f'fill="{_rainbow_hex(gg_val)}"/>'
                )
                parts.append(
                    f'<text class="value-label" x="{col_x + bar_w + 5:.1f}" y="{gg_text_y:.1f}">{num}/{den}</text>'
                )

            ts_text_y = ts_bar_y + bar_h / 2 + 3.5
            if ts_val is None:
                parts.append(f'<text class="na-dash" x="{col_x + 6}" y="{ts_text_y:.1f}">n/a</text>')
            else:
                num, den = ts_fractions[lang]
                bar_w = max(1.5, (ts_val / 100.0) * bar_max_w)
                parts.append(
                    f'<rect x="{col_x}" y="{ts_bar_y:.1f}" width="{bar_w:.1f}" height="{bar_h}" rx="2.5" '
                    f'fill="{_rainbow_hex(ts_val)}"/>'
                )
                parts.append(
                    f'<text class="value-label" x="{col_x + bar_w + 5:.1f}" y="{ts_text_y:.1f}">{num}/{den}</text>'
                )

    parts.append(
        f'<text class="footer" x="{left_margin}" y="{height - 32}">Generated by '
        f"tests/tools/tree_sitter_accuracy_audit.py --chart. Rows are in one alphabetical order shared "
        f'by every panel -- pick a language and read straight across; "n/a" means no ground-truth '
        f"instances for that language on that panel, not a 0% score.</text>"
    )
    parts.append(
        f'<text class="footer" x="{left_margin}" y="{height - 20}">Recall panels ("found/real"): a low '
        f"fraction on a small denominator (e.g. 7/23) is a thinner signal than the same ratio on a large "
        f'one. Precision panels ("found/found+extra"): a large denominator relative to the panel\'s own '
        f"found-count means many false positives, not just misses -- read the two numbers, not just the bar.</text>"
    )
    parts.append(
        f'<text class="footer" x="{left_margin}" y="{height - 8}">A "T" badge means tree-sitter\'s raw reading '
        f"scored higher on THIS metric in THIS run -- for a language with no documented hallucination/noise "
        f"correction (see docs/why_gitgalaxy_beats_ast_here.md), its raw reading equals ground truth by "
        f"construction, so any unrelated GitGalaxy precision defect alone is enough to trigger it. Not a "
        f"general tree-sitter-vs-GitGalaxy verdict -- read the two fractions.</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def run_chart() -> int:
    svg = generate_chart_svg()
    _CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CHART_PATH.write_text(svg, encoding="utf-8")
    print(f"tree_sitter_accuracy_audit: wrote {_CHART_PATH.relative_to(REPO_ROOT)}.")
    return 0


# ----------------------------------------------------------------------------
# --blurbs: diff the two most recent history batches and describe every metric
# that moved, for the tree-sitter-accuracy-history workflow's auto-merged PR
# body. Prints Markdown to stdout only -- deliberately not written to a
# committed file (see the --blurbs help text: this is PR-body content, not a
# standalone artifact to keep in sync).
# ----------------------------------------------------------------------------

_BLURB_MIN_DELTA_PP = 1.0  # ignore sub-noise wobble; a real regex/rule change moves this by more.


def _load_last_two_batches() -> Optional[tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]]:
    """Returns (previous_batch_data, latest_batch_data) -- each {lang: {raw_field: int}} -- for
    the two most recent DISTINCT timestamp_utc values in the history CSV, or None if fewer than
    two batches have been recorded yet (nothing to diff a first-ever run against)."""
    if not _HISTORY_PATH.exists():
        return None
    with open(_HISTORY_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    timestamps = sorted({row["timestamp_utc"] for row in rows})
    if len(timestamps) < 2:
        return None

    def _batch_for(ts: str) -> dict[str, dict[str, int]]:
        return {
            row["language"]: {field: _csv_int(row, field) for field in _HISTORY_RAW_FIELDS}
            for row in rows
            if row["timestamp_utc"] == ts
        }

    return _batch_for(timestamps[-2]), _batch_for(timestamps[-1])


def generate_blurbs() -> str:
    """One Markdown bullet per (language, metric) pair whose value moved by at least
    _BLURB_MIN_DELTA_PP percentage points between the previous and latest history batch, sorted
    biggest move first. Reuses _CHART_METRICS so "what counts as a metric" can't drift between
    the chart and the blurbs. A language/metric only present in one of the two batches (e.g. a
    newly-added baseline) is skipped -- there's no prior value to diff against, not a 0-to-N
    "improvement" worth announcing the same way a real accuracy move is."""
    batches = _load_last_two_batches()
    if batches is None:
        return "_Only one batch recorded so far -- nothing to compare against yet._"
    prev_data, cur_data = batches

    entries: list[tuple[float, str]] = []
    for lang in sorted(set(prev_data) & set(cur_data)):
        # GitGalaxy-only, same as before #1849 -- this feeds the auto-merged PR's "Notable
        # changes" section, which is about GitGalaxy's own accuracy moving from a code change in
        # that same PR, not tree-sitter's (tree-sitter's own numbers move only when
        # tree_sitter_language_pack itself is upgraded, an unrelated PR).
        for m in _CHART_METRICS:
            prev_val = _ratio_pct(*_metric_num_den(prev_data[lang], m.gg_num, m.gg_den))
            cur_val = _ratio_pct(*_metric_num_den(cur_data[lang], m.gg_num, m.gg_den))
            if prev_val is None or cur_val is None:
                continue
            delta = round(cur_val - prev_val, 1)
            if abs(delta) < _BLURB_MIN_DELTA_PP:
                continue
            direction = "improved" if delta > 0 else "regressed"
            entries.append(
                (
                    abs(delta),
                    f"- **{lang}** {m.title} {direction} {abs(delta):.1f}pp ({prev_val:.1f}% → {cur_val:.1f}%)",
                )
            )

    if not entries:
        return f"_No metric moved ≥{_BLURB_MIN_DELTA_PP:g}pp since the previous batch._"

    entries.sort(key=lambda pair: pair[0], reverse=True)
    return "\n".join(text for _delta, text in entries)


def run_blurbs() -> int:
    print(generate_blurbs())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", help="Language to audit (e.g. javascript). Omit when using --all.")
    parser.add_argument(
        "--all", action="store_true", help="Run across every language with a committed baseline instead of one --lang."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ci", action="store_true", help="Terse baseline-gated regression check (what CI runs).")
    group.add_argument("--regenerate", action="store_true", help="Accept current numbers as the new baseline.")
    group.add_argument(
        "--summary-table",
        action="store_true",
        help="Regenerate language_standards.py's summary table from committed baselines. Ignores --lang/--all.",
    )
    group.add_argument(
        "--history",
        action="store_true",
        help="Append current measured metrics for every baselined language to the history CSV. Ignores --lang.",
    )
    group.add_argument(
        "--chart",
        action="store_true",
        help="Render the most recent --history batch as an SVG bar chart. Ignores --lang/--all, no live scan.",
    )
    group.add_argument(
        "--blurbs",
        action="store_true",
        help="Print Markdown bullets describing every metric that moved >=1.0pp between the two "
        "most recent --history batches. Ignores --lang/--all, no live scan.",
    )
    args = parser.parse_args()

    if args.summary_table:
        return run_summary_table()
    if args.history:
        return run_history()
    if args.chart:
        return run_chart()
    if args.blurbs:
        return run_blurbs()

    if bool(args.lang) == bool(args.all):
        parser.error("exactly one of --lang or --all is required")

    if args.all:
        mode_fn = run_regenerate if args.regenerate else run_ci_check if args.ci else run_full_report
        return run_all(mode_fn)

    if args.regenerate:
        return run_regenerate(args.lang)
    if args.ci:
        return run_ci_check(args.lang)
    return run_full_report(args.lang)


if __name__ == "__main__":
    sys.exit(main())
