#!/usr/bin/env python3
"""
ctags_reader.py

Runs universal-ctags against a single file and returns its function/class symbols in the
same shape the tri-comparison tool needs: (name, line, kind, signature_text).

Why a standalone module: this is subprocess integration (spawn ctags, parse its text output),
a completely different shape from tree_sitter_accuracy_audit.py's in-process AST walking, and
worth being able to smoke-test in isolation against real corpus files before any reconciliation
or scoring logic sits on top of it.

KIND MAPS
    Kind *letters* collide across languages on purpose in ctags (its own docs warn about this) --
    "c" means "class" in Python/C++/C#, "constant" in Perl, "constructor" in Haskell/Rust. Never
    treat a letter as portable. CTAGS_FUNC_KINDS / CTAGS_CLASS_KINDS below were built by reading
    `ctags --list-kinds-full=<Lang>` output (the DESCRIPTION column, not the letter) for every
    language GitGalaxy also covers, then cross-checked against GitGalaxy's OWN
    `class_start`/`func_start` regex intent in gitgalaxy/standards/language_standards.py for every
    language with no tree-sitter precedent to lean on (the gg_only-but-ctags-available set: ada,
    agc_assembly, assembly, cobol, embedded_python, m4, scheme, sqlite, yacc). Notable results of
    that cross-check, not just assumed:
      - rust: ctags' "c" kind is `implementation` (impl blocks). GitGalaxy's own class_start is
        `struct|enum|union|trait` -- explicitly NOT impl blocks. "c" is excluded from
        CTAGS_CLASS_KINDS for rust on purpose; mapping it in would inflate rust's class count
        against a definition GitGalaxy itself doesn't use.
        Separately: `ctags --list-kinds-full=Rust` has no "union" kind at all (only struct/enum/
        interface/typedef/etc.) -- a real `union Foo { ... }` declaration (Rust's C-style unsafe
        union, rare but real, e.g. wasmtime's register-union types) is invisible to ctags no
        matter what, confirmed via a direct ctags run showing it correctly finds the *wrapping*
        struct next to a union it misses entirely. Also (function-side): ctags' Rust parser
        appears to skip a function outright when one of its parameters is a destructuring pattern
        (`fn f(Done { _priv }: Done)`) rather than a plain `name: Type` binding -- confirmed via a
        sibling-function comparison (an ordinary-signature method one line away tags fine, the
        pattern-parameter one doesn't), only ever seen once in this corpus so not chased further.
        Both investigated via docs/self_scan/tri_comparison_ledger.json's rust
        `class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]` and
        `function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]` entries -- real, structural
        ctags limitations, not GitGalaxy or tree-sitter defects.
      - cobol: GitGalaxy's class_start covers PROGRAM-ID / CLASS-ID / INTERFACE-ID / FACTORY /
        OBJECT paragraphs. ctags' Cobol parser only has a "program" (P) kind -- no CLASS-ID/
        INTERFACE-ID equivalent exists at all. Permanent, structural gap: ctags can partially
        check GitGalaxy's Cobol class detection (PROGRAM-ID only), never fully.
        Two more "program" (P) kind limitations, confirmed 2026-08-28 against the corpus's
        expanded COBOL content (issue-#4-provenance-audited repos, `language-crucible` v1.1.0):
        (1) ctags emits **zero** tags at all when `PROGRAM-ID.` and the program name are split
        across two lines (a legitimate, common COBOL style) -- confirmed via a direct ctags run
        on `aws-mainframe-modernization-carddemo/COACTUPC.cbl` and 4 siblings, all written
        `PROGRAM-ID.\n    <NAME>.`; GitGalaxy's class_start handles both the same-line and
        split-line form. (2) ctags truncates a program name at its first underscore -- confirmed
        on `gnucobol/CBL_OC_DUMP.cob`, tagged as bare `CBL` instead of `CBL_OC_DUMP` -- the same
        underscore-intolerant identifier convention documented in Claim 12's "second instance"
        (`gnucobol_internals/parser.y`'s YACC rules), just manifesting as truncation for this
        kind instead of total rejection. Both are the full, sole explanation for ledger shape
        `cobol/class/existence/agree[gitgalaxy]_vs[ctags]`'s 6 occurrences (5 split-line + 1
        underscore, zero residual) -- see `docs/why_gitgalaxy_beats_ast_here.md` Claim 12's third
        instance for the full evidence.
        Separately (function-side): ctags' Cobol parser tags ANY period-terminated word as a
        "paragraph" (kind "p"), regardless of which COBOL division it appears in or what role the
        period actually plays. Confirmed shapes, all sharing this one mechanism: scope terminators
        like `END-IF.`/`END-PERFORM.` (the original 2026-08-19 finding, via a direct ctags run on
        cics-banking-sample-application-cbsa/BANKDATA.cbl, dozens of `END-IF.` lines tagged as
        paragraphs); IDENTIFICATION/ENVIRONMENT/DATA DIVISION section and paragraph headers like
        `WORKING-STORAGE SECTION.`/`CONFIGURATION SECTION.`/`LINKAGE SECTION.`/`AUTHOR.` (confirmed
        2026-08-28, the single largest contributor at corpus-expansion scale); and embedded-SQL
        qualified-column periods like `COMMERCIAL.POLICYNUMBER` inside an `EXEC SQL...END-EXEC`
        block, where the period is a table/column separator, not a COBOL statement terminator at
        all (confirmed 2026-08-28 via a direct ctags run on cics-genapp/lgipdb01.cbl, which tags
        `POLICY`/`COMMERCIAL`/`MOTOR` from `FROM POLICY,COMMERCIAL` and `MOTOR.POLICYNUMBER`
        clauses as paragraphs). GitGalaxy correctly excludes all three shapes via its own
        reserved-word shield and division/section awareness. Permanent, structural ctags
        limitation, not filterable by kind (real paragraphs and every false-positive share kind
        "p") -- this is the majority cause of `cobol/function/existence/agree[ctags]_vs[gitgalaxy]`
        (133 occurrences at 2026-08-19's smaller corpus; 773 confirmed same-mechanism occurrences
        at 2026-08-28's ~6x larger one, see `how_to_investigate_a_discrepancy.md`'s "When a
        validated shape's count changes a lot" for how that generalization was actually checked
        rather than assumed). A smaller, genuine GitGalaxy defect (a `\b`-vs-hyphen word-boundary
        bug excluding real verb-prefixed paragraph names like `DELETE-POLICY-DB2-INFO`) used to
        hide underneath this noise in the same ledger shape -- fixed, issue #1892; re-confirmed
        2026-08-28 that zero real-paragraph false negatives remain in the expanded corpus, only
        the three ctags-side false-positive shapes above.
      - scheme: GitGalaxy's class-analog is SRFI-9 `define-record-type`. ctags' Scheme parser
        exposes no kind for it (only function/set/unknown) -- CTAGS_CLASS_KINDS["scheme"] is
        deliberately empty, so class metrics render as ctags_available=False for scheme, not a
        silently-wrong 0%.
      - ada: GitGalaxy only counts *tagged* types as classes (Ada's OOP construct). ctags' "t"
        kind is every type declaration, tagged or not -- mapped anyway (it's the only option) but
        this WILL over-count vs. GitGalaxy's narrower definition; documented here so a resulting
        low ctags "precision" number for ada isn't misread as a GitGalaxy defect.
      - haskell: ctags' Haskell parser has no class-shaped kind at all (constructor/function/
        module/type only) -- CTAGS_CLASS_KINDS["haskell"] is empty on purpose.
        Separately (function-side, not this class map, but same parser): ctags' Haskell parser
        also has no layout-rule/lexical-scope awareness -- it only tags equations anchored at
        column 1 (true module top level), never `instance ... where` methods, `where`-clause
        helpers, or `let`-bound names inside a `do` block, even when it correctly handles those
        same definitions' multiple pattern-match clauses at the top level (confirmed:
        `expandFilterPath`/`writeFnBinary`/`writerFn` all tag fine). Investigated via
        docs/self_scan/tri_comparison_ledger.json's
        `haskell/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]` entry -- a real,
        structural ctags limitation, not a GitGalaxy or tree-sitter defect.
      - shell: no class-shaped kind either (alias/function/heredoc/script) -- matches GitGalaxy's
        and tree-sitter's own class_recall/precision being N/A for shell already.
        Separately (function-side, not this class map): ctags' Sh parser tags a bare SCALAR
        assignment as a function in some contexts -- `GREP_OPTS=`, `FILTERED_ENV=`, `_GROUPS=`,
        `l=` all come back as `f`-kind tags (name includes the trailing `=`), where GitGalaxy and
        tree-sitter both correctly ignore them. Not a curated name-exclusion here (same
        ground-truth-judgment reasoning as the c macro-invocation note below). Investigated via
        `shell/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]` (44 occurrences, mixed:
        this assignment false-positive plus a genuine ctags-only recall win on `sub`-style helpers
        in `darwin-xnu/makesyscalls.sh` that GitGalaxy and tree-sitter both miss) -- the
        false-positive half is a real ctags limitation, not a GitGalaxy or tree-sitter defect.
      - c: ctags' C parser misreads a MACRO INVOCATION (not a definition) as a real function
        when the macro name is used to generate boilerplate, e.g. cpython/typeobject.c's
        `RICHCMP_WRAPPER(lt, Py_LT)` and `SLOT1(slot_mp_subscript, __getitem__, PyObject *)` --
        both real calls to a previously-`#define`d macro, confirmed by reading the source; ctags
        tags `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/`SLOT1BINFULL` themselves as function names,
        GitGalaxy and tree-sitter both correctly don't. Deliberately NOT added as a curated
        name-exclusion list here (unlike the anonymous-struct fix below, this would be a
        ground-truth judgment call -- "these specific macro names are known bad" -- the same
        category of decision `tri_comparison_gatherer.py`'s own docstring explains keeping out of
        the raw readers and in reconciliation instead). Investigated via
        `c/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]` (7 occurrences) -- a real
        ctags limitation, not a GitGalaxy or tree-sitter defect.
        Separately (also c, but function-agnostic -- affects both CTAGS_FUNC_KINDS and
        CTAGS_CLASS_KINDS the same way, so noted once here): ctags synthesizes a placeholder name
        (`__anon<hex>`) for an anonymous struct/union/enum
        (`typedef struct { ... } Foo;`, e.g. cpython/ceval.c's platform pthread-attr shim).
        Neither GitGalaxy nor tree-sitter report a name for an anonymous type at all -- there
        genuinely isn't one -- so ctags' own bookkeeping name always surfaced as a false
        discrepancy. FIXED in `tri_comparison_gatherer.py` (`_is_ctags_synthetic_anon_name`,
        applied to both func and class ctags readings) rather than just documented, since
        matching a structural naming pattern (not a curated list of specific names) is the same
        kind of neutral fact the C struct-body-check fix already established is fair game for the
        walk itself. Investigated via `c/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`
        (23 occurrences, cpython + doom).
      - m4: same macro-invocation-vs-definition confusion as C's RICHCMP_WRAPPER note above, just
        via autoconf's `AC_DEFINE`/`AC_DEFINE_UNQUOTED` helpers instead of a raw C macro call --
        ctags' M4 parser heuristically tags any `AC_DEFINE(NAME, ...)`/`AC_DEFINE_UNQUOTED([NAME],
        ...)` call as a macro DEFINITION by extracting its first argument as the "defined" name,
        e.g. curl/configure.ac:2112's `AC_DEFINE_UNQUOTED([CURL_DEFAULT_SSL_BACKEND], [...], [...])`
        -- but `AC_DEFINE*` only ever emits a C preprocessor `#define` into the generated
        `config.h` at build time; it never defines a new callable M4 macro the way
        `AC_DEFUN`/`m4_define`/`define` do. GitGalaxy's own `func_start` for m4 deliberately
        excludes `AC_DEFINE*` from its keyword set, so its silence on these lines is correct, not
        a miss. Confirmed on all 10 sampled cases (all `curl/configure.ac`, all real
        `AC_DEFINE`/`AC_DEFINE_UNQUOTED` calls, zero genuine `AC_DEFUN`/`m4_define` misses) via
        `m4/function/existence/agree[ctags]_vs[gitgalaxy]` (79 occurrences total) -- a real ctags
        limitation, not a GitGalaxy defect.
      - cpp: same macro-invocation-vs-definition confusion as C's RICHCMP_WRAPPER note above, in
        two distinct shapes, both real ctags limitations, neither a GitGalaxy or tree-sitter
        defect. (1) A macro used as a RETURN-TYPE PREFIX before the real function name: Windows
        COM's `IFACEMETHODIMP_(void) FancyZones::Run() noexcept {...}`
        (powertoys/FancyZones.cpp:213) -- ctags tags the macro invocation `IFACEMETHODIMP_(void)`
        itself as a complete function (name `IFACEMETHODIMP_`, signature `(void)`) and then reads
        the REAL name `FancyZones::Run` that follows as body content, missing it entirely. Same
        shape for godot/rendering_server_default.h's `FUNC2`/`FUNC3`/`FUNCRIDTEX1` macros (each
        expands to a full method declaration at its call site, but ctags tags the macro call
        itself) and powertoys/ImageResizerExt.cpp's `__control_entrypoint`. (2) A macro DEFINITION
        BODY containing what looks like a complete function declarator, tagged as if it were real,
        already-expanded code: godot/object.h's `GDCLASS`/`_FORCE_INLINE_`-based macros
        (`#define GDCLASS(m_class, m_inherits) ... _FORCE_INLINE_ bool (Object::*_get_get() const)
        (...) {...} ...`) never actually run as written -- they only produce real code once
        expanded at a `GDCLASS(SomeClass, Base)` call site elsewhere -- but ctags parses inside the
        `#define` body itself and tags `_get_get`/`_get_set`/`_get_bind_methods`/etc. as if they
        were ordinary member functions. Investigated via
        `cpp/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]` (1097 occurrences,
        2026-08-21) -- the overwhelming majority of that shape was actually a
        qualification/pattern-truncation gap in THIS reader (see `_QUALIFY_NAME_WITH_SCOPE`/
        `--pattern-length-limit=0` below), fixed directly; these two macro-parsing shapes are the
        genuine remainder.
        Separately (class-side, not function): ctags' "g" (enum) kind was entirely absent from
        `CTAGS_CLASS_KINDS["cpp"]` (unlike C's, which already had it) -- `enum class`/`enum struct`
        (C++11 scoped enums) are real GitGalaxy class_start matches with no ctags counterpart at
        all until this map included "g" too (gated on the source line itself distinguishing scoped
        from unscoped enums, since ctags' own "g" kind doesn't -- see `_is_cpp_unscoped_enum`).
        Investigated via `cpp/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]` (95
        occurrences, 2026-08-21) -- a bug in this test harness (mirroring C's own pre-2026-08-19
        gap above), not in ctags, GitGalaxy, or tree-sitter. A separate, smaller finding from the
        same investigation is a real GitGalaxy defect, not a ctags one: `class Foo;` forward
        declarations are counted as real classes by both GitGalaxy's `class_start` regex and this
        module's own tree-sitter walker (fixed here -- see `_walk_tree_sitter`'s docstring) but
        NOT by ctags, which correctly excludes them -- filed separately since the production
        engine's fix needs care around C++ multiple inheritance, see the GitHub issue referenced in
        tri_comparison_ledger.json's corresponding entry.
      - csharp: ctags' C# parser silently drops a tag for a subset of real method declarations
        with a complex signature, both isolated single misses and, separately, an overload-name
        collision. (1) Complex signature: `CSharpCompilation.cs`'s `FindEntryPoint` (nullable
        return type `MethodSymbol?`, nullable param `MethodSymbol?`, and an `out` param of a
        generic type `out ReadOnlyBindingDiagnostic<AssemblySymbol> sealedDiagnostics`) gets no
        tag at all, confirmed via a direct `ctags -x` run showing tags immediately before and
        after it in the file but none at its own line -- an isolated miss, not part of a wider
        blind region. `GetSourceDeclarationDiagnostics` (5 params including two with default
        values and a `Func<...>` generic delegate parameter) is missed the same way. (2) Overload
        collision: `ReportUnusedImports` has two overloads at different line numbers in the same
        file; ctags tags only the first, silently dropping the second. Also a genuine ctags FALSE
        POSITIVE from the same file: a `public bool Equals((ImmutableArray<byte> ContentHash, int
        Position) x, (ImmutableArray<byte> ContentHash, int Position) y)` overload (tuple-typed
        parameters) gets tagged under the name `bool` instead of `Equals` -- ctags' lightweight
        parser appears to misread the return-type/tuple-parameter boundary. All confirmed via
        `csharp/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]` (107 occurrences) and
        `csharp/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]` (1 occurrence,
        2026-08-21) -- real, structural ctags parser limitations, not GitGalaxy or tree-sitter
        defects. (Separately, and NOT a ctags defect: most of that 107-shape is local/nested
        function declarations, e.g. `validateSignature`/`isSupportedType` -- ctags has no concept
        of a local function the same way it has no concept of a local variable; GitGalaxy and
        tree-sitter both correctly count these, ctags correctly doesn't try to.)
      - javascript: ctags' JavaScript scanner has two structural limitations. (1) Class-side: it
        heuristically tags ANY bare object-literal assignment (`var X = {...}`) or function-expression
        assignment (`var X = function(){}`) as a class, assuming it might be used as a pre-ES6
        constructor. GitGalaxy and tree-sitter both correctly require the literal `class` keyword.
        (2) Function-side: it loses the real property-key name for a function-valued object-literal
        property when passed as a CALL ARGUMENT (e.g. `jQuery.extend(..., {ajaxSetup: function(){}})`),
        instead emitting a synthetic 'AnonymousFunction<hex>' tag (now filtered by the gatherer).
        It also incorrectly tags the BASE OBJECT name instead of the property for dynamic property
        assignments (`jQuery[ method ] = function()`), tags method calls as method DEFINITIONS
        (`X.prototype.Y.call()`), and emits literal bracket strings for computed property names
        (`[ASYNC_ITERATOR]`). GitGalaxy and tree-sitter correctly avoid all these traps.
    Cross-reference gitgalaxy/standards/language_standards.py's own class_start/func_start
    definitions before ever widening one of these maps -- do not add a kind because its letter
    looks right.

LANGUAGE COVERAGE
    Not every GitGalaxy language has a ctags parser at all. See LANG_MAP below: 33 languages have
    an entry (24 that overlap with tree-sitter's 31 baselined languages, plus 9 more from
    GitGalaxy's tree-sitter-blind set -- ada, agc_assembly, assembly, cobol, embedded_python, m4,
    scheme, sqlite, yacc -- where ctags is the first-ever external check on GitGalaxy's numbers).
    7 of the 31 tree-sitter-baselined languages have no ctags parser (Apex, Dart, Groovy, Scala,
    Solidity, Swift, Zig); 5 gg_only languages have neither (abap, dockerfile, jcl, livecode,
    yaml). Call `ctags_available(lang)` before assuming a reading exists.

SIGNATURE FIELD
    `--fields=+S` gives a free-text parameter-list string, not a count -- format varies by
    language parser (Rust's can include a trailing `-> ReturnType`; Python/C#/Rust all include
    self/receiver literally in the text, consistent with how GitGalaxy's own existing
    tree_sitter_accuracy_audit.py already counts self_parameter as a real parameter, so no
    special-casing needed there). Some languages never populate it even for real functions --
    confirmed for shell (bash has no formal parameter list for ctags to read, same structural
    gap tree-sitter has there) -- `signature` comes back as None in that case, not an empty
    string, so callers can tell "no params" apart from "field not supported here."

OPTIONAL, VERIFICATION-ONLY -- NOT PART OF THE ZERO-DEPENDENCY ENGINE
    Nothing under gitgalaxy/ imports this module or anything from tests/tools/tri_comparison_*.
    GitGalaxy's "0 dependencies" claim (README.md's proof strip; PyYAML's own move to an
    optional `gitgalaxy[yaml]` extra when it briefly threatened that claim, see
    docs/readme_evidence_roadmap.md) is about the SHIPPED `pip install gitgalaxy` package --
    universal-ctags never touches it. `has_ctags()` below is what makes a missing binary a
    normal, expected state rather than an error: every language just reports
    ctags_available(lang) == False and the tri-comparison degrades to GitGalaxy + tree-sitter,
    the same graceful-degradation shape a tree-sitter-blind language already has.

REQUIRES (only if you're actually running the tri-comparison tooling)
    A `ctags` binary on PATH that is universal-ctags (not exuberant-ctags, not the
    `arduino-ctags` package Ubuntu also ships, which shadows the same binary name and lacks most
    of these language parsers and the --fields=+S/+n extensions this module depends on) --
    `has_ctags()` checks for the "Universal Ctags" string in `ctags --version`'s own banner, not
    just that some binary named `ctags` exists. Version matters too: Ubuntu's packaged
    universal-ctags (5.9, from 2021) has meaningfully less language coverage than a current
    release; this was validated against 6.2.1 built from the official release tarball
    (https://github.com/universal-ctags/ctags/releases -- has a pre-generated `configure`, so it
    builds with just gcc/make, no autoconf/automake, no root needed -- `./configure
    --prefix=$HOME/.local/ctags-6.2.1 && make && make install`, then put that prefix's `bin/` on
    PATH; a plain `git clone` of the repo does NOT include a pre-generated configure and needs
    the full autotools chain instead). Pin the exact version used the same way language-crucible
    and tree-sitter-language-pack are pinned elsewhere in this repo's CI -- do not rely on
    whatever apt happens to have.
"""

from __future__ import annotations

import functools
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# GitGalaxy has a zero-dependency stance for the SHIPPED `gitgalaxy` package (see README.md's
# "0 dependencies" claim and pyproject.toml's `yaml` extra, the only optional Python dependency
# the actual engine has). universal-ctags is a system BINARY, not a Python package, and this
# entire module exists only to support the tri-comparison verification tooling under
# tests/tools/ -- it is never imported by anything under gitgalaxy/. `has_ctags()` below is what
# keeps a missing binary a clean, optional-degradation path (every language just reports
# ctags_available(lang) == False, same as a language tree-sitter has no grammar for) rather than
# a crash. See this module's own docstring's REQUIRES section for install instructions.


@functools.lru_cache(maxsize=1)
def has_ctags() -> bool:
    """True only for a real universal-ctags binary on PATH -- checks the `--version` banner text,
    not just that *some* binary named `ctags` exists, because Ubuntu's `arduino-ctags` package
    (and old-style exuberant-ctags) both install a binary under the exact same name and lack most
    of the language parsers and the --fields=+n/+S extensions this module depends on. Cached
    (this only needs to run the subprocess once per process, not once per file) via lru_cache
    rather than a module-level constant so importing this module never itself shells out --
    only actually calling something that needs ctags does.
    """
    if shutil.which("ctags") is None:
        return False
    try:
        result = subprocess.run(["ctags", "--version"], capture_output=True, text=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return False
    return "Universal Ctags" in result.stdout


# GitGalaxy language name -> ctags --language-force name. Verified against a real
# `ctags --list-languages` run, not assumed from case-folding (e.g. "MatLab", not "Matlab";
# "ObjectiveC", not "Objective-C"; "Sh", not "Shell"; "Make", not "Makefile").
LANG_MAP: dict[str, str] = {
    "c": "C",
    "cpp": "C++",
    "csharp": "C#",
    "css": "CSS",
    "fortran": "Fortran",
    "go": "Go",
    "haskell": "Haskell",
    "html": "HTML",
    "java": "Java",
    "javascript": "JavaScript",
    "kotlin": "Kotlin",
    "lua": "Lua",
    "makefile": "Make",
    "matlab": "MatLab",
    "objective-c": "ObjectiveC",
    "perl": "Perl",
    "php": "PHP",
    "powershell": "PowerShell",
    "python": "Python",
    "ruby": "Ruby",
    "rust": "Rust",
    "shell": "Sh",
    "tcl": "Tcl",
    "typescript": "TypeScript",
    # gg_only languages (no tree-sitter grammar) that DO have a ctags parser -- the first
    # external check GitGalaxy's numbers have ever had for these.
    "ada": "Ada",
    "agc_assembly": "Asm",
    "assembly": "Asm",
    "cobol": "Cobol",
    "embedded_python": "Python",
    "m4": "M4",
    "scheme": "Scheme",
    "sqlite": "SQL",
    "yacc": "YACC",
}

# Kind letters selected by DESCRIPTION text from `ctags --list-kinds-full=<Lang>`, not by
# letter -- see the module docstring's KIND MAPS section for the specific per-language
# reasoning behind every non-obvious entry below.
CTAGS_FUNC_KINDS: dict[str, set[str]] = {
    "c": {"f"},
    "cpp": {"f"},
    "csharp": {"m"},  # methods; C# has no free functions
    "css": set(),  # no function-equivalent
    "fortran": {"f", "s", "p", "e"},  # functions, subroutines, programs, entry points -- matches
    # GitGalaxy's own fortran func_start regex, which treats FUNCTION|SUBROUTINE|PROGRAM|ENTRY as
    # equally function-shaped. "p"/"e" were simply absent from this map (found via tri-comparison-
    # ledger-sweep, fortran/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter], 2026-08-21):
    # wrf/module_initialize_real.F:7519's `program foo` is a real ctags "program" tag ctags itself
    # emits correctly, just invisible to this comparison because "p" wasn't in the set.
    "go": {"f"},
    "haskell": {"f"},
    "html": set(),
    "java": {"m"},
    "javascript": {"f", "m"},  # functions + methods -- but see two confirmed parser-level gaps
    # (found via tri-comparison-ledger-sweep, 2026-08-21, jquery/react corpus), neither fixable by
    # adjusting this kind set: (1) a function-valued object-literal property loses its real
    # property-key name and falls back to a synthetic "AnonymousFunction<hex>" tag (filtered by
    # `_is_ctags_synthetic_anon_name` in tri_comparison_gatherer.py) specifically when that literal
    # is a CALL ARGUMENT rather than a direct assignment -- confirmed via jquery/ajax.js's
    # `jQuery.extend(jQuery, {ajaxSetup: function(){...}, ajax: function(){...}})`: ctags' own
    # scope-tracking loses the `ajaxSetup`/`ajax` key names entirely inside the call, while the
    # exact same `key: function(){}` shape assigned directly (`X.prototype = {abort: function(){}}`
    # style) tags correctly as a "method". jquery/core.js is the extreme case -- one single
    # `jQuery.extend(jQuery, {...})` call holding 20+ real utility methods (`each`, `extend`,
    # `grep`, ...) reduces ctags' whole-file function count to 1. (2) Flow-typed javascript (react's
    # `@flow` source) can trip ctags' own return-type-annotation handling (`): Type {|`) and
    # silently drop every function textually after the trigger for the rest of the file, no
    # placeholder emitted at all -- see docs/why_gitgalaxy_beats_ast_here.md's Claim 3 for the full
    # writeup and a minimal repro; this is ctags' own scanner hitting an equivalent, independently-
    # triggered version of the same cascade tree-sitter-javascript already hits there.
    # (3) ctags falsely tags function CALLS on prototype methods (e.g. `Material.prototype.copy.call(...)`)
    # as method declarations, extracting a method named `copy`. GitGalaxy and tree-sitter correctly ignore these.
    # kotlin: ctags has no separate free-function kind -- top-level functions tag "m" too
    # (verified via probe file: a file-scope `fun` with no enclosing class still tags "m",
    # just without a `class:` field), so "m" alone already covers both cases.
    # Also NOT fixable by adjusting this kind set: ctags' Kotlin parser tags two shapes that
    # aren't real function declarations with the SAME "m" kind as genuine ones (found via
    # tri-comparison-ledger-sweep, kotlin/function/existence/agree[ctags]_vs[gitgalaxy,
    # tree_sitter], 15 occurrences, 2026-08-22, okhttp/Dispatcher.kt): (1) any trailing-lambda
    # block passed as a call argument (`require(x >= 1) { "..." }`, `synchronized(this) { ... }`,
    # `.also { ... }`, `.map { it.call }`) tags as a synthetic `<lambda>` symbol -- confirmed via
    # `ctags -x --languages=Kotlin`, 10 of the 15 occurrences; (2) a `for (x in collection)` loop's
    # iteration variable tags as a method literally named after the variable (`call`, `existingCall`)
    # -- the remaining 5. GitGalaxy's own func_start regex and tree-sitter's grammar both correctly
    # require a real `fun`/constructor declaration, so every one of these is a ctags-side
    # over-count, not a GitGalaxy gap -- same shape as the javascript object-literal note above:
    # ctags gives no separate kind for "anonymous lambda literal" or "for-loop binding" vs. a real
    # named function/method in the first place.
    # Separately, the opposite direction: ctags' Kotlin parser doesn't recognize a secondary
    # constructor (`constructor(...) : this() { ... }`) as a symbol at all -- confirmed via
    # `ctags -x --languages=Kotlin` on the same Dispatcher.kt emitting no entry whatsoever for
    # its line-119 constructor, under any kind. Not a kind-map gap (nothing to remap; ctags never
    # tags it in the first place) -- a genuine parser recall gap, kept as a real, permanent
    # disagreement (kotlin/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]) rather than
    # something this reader can work around.
    "kotlin": {"m"},
    # lua: "f" is the only function kind. Two ctags-Lua behaviours worth knowing, both confirmed by
    # the tri-comparison-ledger-sweep (2026-08-29) and NOT worked around here (ctags is the
    # over-reader, GitGalaxy + tree-sitter-lua are the reference):
    #   * ctags-Lua over-tags -- it tags the LHS name of ANY statement whose RHS contains the token
    #     `function`, so `res = pcall(function() ... end)`, `X = function() ... end`, metatable
    #     fields (`__index = function`), the literal word inside a string (`type(x) == "function"`)
    #     and even inside a comment all become "function" tags. ~442 of ctags' ~1095 corpus tags
    #     are this. Shape lua/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter].
    #   * ctags-Lua emits NO `signature:` field (verified via `ctags --fields=+S --languages=Lua`),
    #     so it cannot participate in a per-function args comparison at all. Shape
    #     lua/function/args/agree[none]_vs[gitgalaxy,tree_sitter] -- GitGalaxy + tree-sitter agree,
    #     ctags is simply absent.
    "lua": {"f"},
    "makefile": {"t"},  # targets are the closest func-analog
    "matlab": {"f"},
    "objective-c": {"f", "m"},
    "perl": {"s"},  # subroutine; NOT "d" (subroutineDeclaration, disabled/refonly by default)
    "php": {"f"},  # PHP's kind table has no separate method kind -- methods tag as "f" too
    "powershell": {"f"},
    # python: "f" is free/module-level functions only. Methods tag as "m" (member) -- confirmed
    # via a probe file that plain class attributes tag as "v" (variable), never "m", so this
    # can't be conflating callables with data attributes. Caught by the reader's own smoke test
    # (a real corpus file showed funcs=0 with just "f" -- every function in it was a method).
    "python": {"f", "m"},
    "ruby": {"f", "S"},  # method + singletonMethod
    "rust": {"f", "P"},  # function + method
    "shell": {"f"},
    "tcl": {"p"},  # procedure
    "typescript": {"f", "m"},
    "ada": {"r"},  # subprogram (procedures/functions)
    "agc_assembly": {"l"},  # labels are AGC's only function-analog; GitGalaxy's own func_start
    # for assembly-family languages matches labels too
    "assembly": {"l"},
    "cobol": {"p", "s"},  # paragraph and section -- GitGalaxy's func_start for cobol targets both
    "embedded_python": {"f", "m"},  # same method-vs-function split as python above
    "m4": {"d"},  # macro -- M4's def-like construct
    "scheme": {"f"},
    "sqlite": {"f", "p"},  # function + procedure
    "yacc": {"l"},  # ctags' YACC parser tags every grammar-rule LHS non-terminal
    # (`Name:` production head) with its own "l" (label) kind -- the same
    # function-analog role a grammar rule plays in GitGalaxy's own yacc func_start
    # and the same mapping precedent as makefile "t" (targets) / assembly "l".
    # This entry was `set()` until yacc/tri-comparison-ledger-sweep (2026-08-27,
    # yacc/function/existence/agree[gitgalaxy]_vs[ctags], 18 occurrences) -- the
    # prior "ctags structurally cannot see them" comment was wrong: `ctags
    # --fields=+K` on freebsd/config.y + jailparse.y tags all 27 rule heads as
    # kind "l" (`Spec  label  line:126`), this map was just dropping them before
    # reconciliation saw them, exactly the cpp "g" / csharp "g" / fortran "m,i,S,b"
    # / kotlin "o" kind-map gap shape. `ctags --list-kinds-full=YACC` confirms
    # "l" (labels) is the parser's ONLY kind -- there is nothing else to weigh.
}

CTAGS_CLASS_KINDS: dict[str, set[str]] = {
    "c": {"s", "g", "u"},  # struct, enum, union -- matches GitGalaxy's own C class_start regex
    # (struct|union|enum, gitgalaxy/standards/language_standards.py). Was struct-only until
    # c/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags] (9 occurrences, 2026-08-19)
    # surfaced it: ctags itself parses enum/union declarations fine (confirmed via a direct
    # `ctags -x` run against sqlite/lemon.c and others), this map was just dropping them before
    # reconciliation ever saw them -- a bug in this test harness, not in ctags, GitGalaxy, or
    # tree-sitter.
    "cpp": {"c", "s", "u", "g"},  # class, struct, union, enum (enum gated below -- see
    # _is_cpp_unscoped_enum: ctags' "g" kind covers BOTH `enum class Foo` and plain, unscoped
    # `enum Foo`, but GitGalaxy's own cpp class_start regex only counts the SCOPED form
    # (enum[ \t\n]+class|enum[ \t\n]+struct, gitgalaxy/standards/language_standards.py) --
    # unlike C, where GitGalaxy counts every enum unconditionally (see the "c" entry above) since
    # C has no scoped-enum concept to distinguish from. Confirmed via
    # cpp/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]: union (MTFlag/MTNumeric,
    # godot/node.h) and enum class (AncestralClass/EditorExitKind/HotkeyId/OpType/SpecialMode/
    # toast_notification_handler_result) were both simply absent from this map, matching C's
    # same pre-2026-08-19 gap (9 occurrences) before it was fixed there.
    "csharp": {"c", "s", "i", "g"},  # class, struct, interface, enum -- matches GitGalaxy's own
    # csharp class_start regex (class|interface|struct|record(?:\s+(?:struct|class))?|enum,
    # gitgalaxy/standards/language_standards.py). Found via the same incidental-finding pass that
    # fixed cpp's identical gap (2026-08-21, cpp/class/existence sweep) -- "g" (enum) was simply
    # absent from this map too. Unlike C++'s enum, C# has no scoped-vs-unscoped distinction to
    # gate on (every `enum Foo {...}` is equally a real type), so this is a plain, unconditional
    # addition -- no source-text gate needed the way cpp's `_is_cpp_unscoped_enum` requires.
    "css": {"c"},  # CSS "class" kind is a literal .class selector -- matches GitGalaxy's own
    # css class_start intent (it also targets selector-like entities)
    "fortran": {"t", "m", "i", "S", "b"},  # derived types/structures, modules, interfaces,
    # submodules, block data -- matches GitGalaxy's own fortran class_start regex
    # (MODULE|BLOCK DATA|INTERFACE|SUBMODULE|TYPE, gitgalaxy/standards/language_standards.py).
    # "m"/"i"/"S"/"b" were simply absent from this map, same shape as the cpp/csharp gaps above
    # (found via tri-comparison-ledger-sweep, fortran/class/existence/
    # agree[gitgalaxy,tree_sitter]_vs[ctags], 2026-08-21): ctags correctly tags every WRF
    # `MODULE ...`/`INTERFACE ...` with its own "m"/"i" kind (confirmed directly, e.g.
    # wrf/module_configure.F's module_configure/module_irr_diag/module_scalar_tables and
    # module_domain.F's `INTERFACE get_ijk_from_grid`), just invisible to this comparison.
    "go": {"s", "i"},  # struct, interface -- matches GitGalaxy's own `type X struct|interface`
    "haskell": set(),  # no class-shaped kind in ctags' Haskell parser at all
    "html": set(),
    "java": {"c", "i", "g"},  # class, interface, enum
    "javascript": {"c"},  # real `class Foo {}` -- but ctags' JS parser also tags this SAME "c"
    # kind on any bare object-literal assignment (`var X = {...}`) or function-expression
    # assignment (`var X = function(){}`, `obj.prop = function(){}`), a blanket heuristic for
    # "might be used as a pre-ES6 constructor" that fires whether or not the value is ever
    # actually invoked with `new` (found via tri-comparison-ledger-sweep,
    # javascript/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter], 96 occurrences,
    # 2026-08-21 -- confirmed both on the jquery/threejs corpus, e.g. jquery/css.js's plain config
    # object `cssHooks`/`cssShow`, and via a minimal isolated repro). GitGalaxy's own class_start
    # regex and tree-sitter's `class_declaration` node both correctly require the literal `class`
    # keyword, so every one of these is a real ctags-side over-count, not a GitGalaxy gap -- no
    # kind-set change fixes it since ctags gives no separate kind for "object literal" vs.
    # "class-shaped assignment" in the first place.
    "kotlin": {"c", "i", "o"},  # class, interface, object -- "o" was simply absent from this
    # map, same shape as the cpp/fortran gaps above (found via tri-comparison-ledger-sweep,
    # kotlin/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags], 2026-08-22): ctags tags a
    # Kotlin `object Foo { ... }` singleton declaration with its own distinct "o" (objects) kind,
    # separate from "c" (classes) -- confirmed directly via `ctags -x --languages=Kotlin` on
    # okhttp/OkHttp.kt, which tags `expect object OkHttp` as kind "object", not "class". GitGalaxy's
    # own class_start regex and tree-sitter's grammar both already treat `object` as class-shaped
    # (gitgalaxy/standards/language_standards.py's kotlin class_start includes the literal `object`
    # keyword), just invisible to this ctags-side comparison until now.
    "lua": set(),
    "makefile": set(),
    "matlab": {"c"},
    "objective-c": {"i", "I"},  # interface (@interface), implementation (@implementation)
    "perl": {"p"},  # package -- Perl has no class kind; GitGalaxy's own class_start matches
    # `package|class|role`, and package_statement is what real-world corpus code
    # (bugzilla, exiftool) actually uses -- see tree_sitter_accuracy_audit.py's #1295 comment
    "php": {"c", "i", "t"},  # class, interface, trait
    "powershell": {"c"},
    "python": {"c"},
    "ruby": {"c", "m"},  # class, module
    "rust": {"s", "g", "i"},  # struct, enum, trait -- NOT "c" (implementation/impl blocks);
    # GitGalaxy's own class_start is struct|enum|union|trait, never impl
    "shell": set(),
    "tcl": set(),  # ctags' Tcl parser has no class-shaped kind
    "typescript": {"c", "i"},
    "ada": {"t"},  # every type decl, tagged or not -- OVER-counts vs. GitGalaxy's tagged-only
    # definition; document this when reporting ada's ctags precision, don't silently absorb it
    "agc_assembly": set(),  # GitGalaxy's own class_start is None for agc_assembly ("AGC lacks
    # native objects") -- matches ctags having nothing class-shaped either
    "assembly": set(),  # GitGalaxy DOES have a struc/STRUCT class_start for x86-style assembly,
    # but ctags' generic "Asm" parser's "t" (types) kind is for structs/records -- map it
    "cobol": {"P"},  # program (PROGRAM-ID only) -- CLASS-ID/INTERFACE-ID/FACTORY/OBJECT have no
    # ctags equivalent; this can only ever partially check GitGalaxy's cobol class_start
    "embedded_python": {"c"},
    "m4": set(),  # GitGalaxy's own class_start is None for m4 ("lacking objects")
    "scheme": set(),  # SRFI-9 define-record-type has no ctags kind; deliberately empty, not a
    # scoring artifact -- ctags_available(lang, "class") should report False here
    "sqlite": {"t"},  # table -- matches GitGalaxy's own class_start (CREATE TABLE)
    "yacc": set(),
}

# assembly's struct/record type-analog does exist in ctags ("t"), correcting the CTAGS_CLASS_KINDS
# entry above (assembly is not truly class-blind the way agc_assembly is -- AGC's variant of the
# Asm parser produces the same kind table, but GitGalaxy's own assembly class_start regex, unlike
# agc_assembly's `None`, does match struc/STRUCT declarations, so map it).
CTAGS_CLASS_KINDS["assembly"] = {"t"}


@dataclass(frozen=True)
class CtagsSymbol:
    name: str
    line: int
    kind: str
    signature: Optional[str]  # None means "field not populated for this symbol", not "no params"


def ctags_available(lang: str) -> bool:
    """False if universal-ctags isn't installed at all, not just if this particular language
    lacks a parser -- callers (tri_comparison_gatherer.py) branch on this one function for both
    cases, so a missing binary degrades every language gracefully to a 2-tool (GitGalaxy +
    tree-sitter) comparison, the same shape a language tree-sitter has no grammar for already
    degrades to GitGalaxy-only."""
    return has_ctags() and lang in LANG_MAP


def ctags_available_for_classes(lang: str) -> bool:
    return bool(CTAGS_CLASS_KINDS.get(lang))


def ctags_available_for_functions(lang: str) -> bool:
    return bool(CTAGS_FUNC_KINDS.get(lang))


# ctags' "g" (enum) kind tags both `enum class Foo {...}` and plain `enum Foo {...}` identically
# (confirmed: neither the tag's kind letter nor any extension field distinguishes them -- checked
# with --fields=+z too), so telling them apart requires reading the tag's own verbatim matched
# source line, the same trick _QUALIFY_NAME_WITH_SCOPE already uses below.
_CPP_SCOPED_ENUM_RE = re.compile(r"\benum[ \t]+(?:class|struct)\b")


def _is_cpp_unscoped_enum(kind: str, source_text: str) -> bool:
    return kind == "g" and not _CPP_SCOPED_ENUM_RE.search(source_text)


# ctags' scope field ("s", on by default) emits `<scopekind>:<scopename>` in the extension-fields
# trailer -- e.g. `class:Object::Connection` for a method nested in namespace Object, class
# Connection. Only one of these keys is ever present per tag (whichever kind actually encloses
# it); checked in this order for no particular reason beyond determinism.
_CTAGS_SCOPE_KIND_KEYS = ("class", "struct", "namespace", "union", "enum", "interface", "function")

# Languages where GitGalaxy's and tree-sitter's own function/class name already bakes the
# enclosing scope into the name for an OUT-OF-CLASS definition, because that source syntax spells
# it out explicitly (C++'s `ReturnType ClassName::method(...)` convention -- both tools just read
# the qualified identifier straight out of the source text). ctags instead splits this into a bare
# `name` field plus a separate scope field -- and, critically, emits that SAME scope field for an
# ordinary IN-CLASS-BODY method too (`class Foo { void bar() {...} }`), where GitGalaxy/tree-sitter
# read the bare, unqualified name because that's genuinely all the source says. ctags' own tag data
# can't tell these two cases apart (confirmed: both `class Foo { void bar() }` and
# `void Foo::bar()` produce the identical `name:bar / class:Foo` tag shape) -- so qualification
# below is gated on actually finding the literal `Scope::name` text in the tag's own verbatim
# matched source line, not applied unconditionally. Confirmed via
# cpp/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags] (1097 occurrences) --
# NVDA/storage.cpp alone has 62 methods, all out-of-class definitions, where all three tools found
# the exact same definition at the exact same line; re-joining name+scope this way (with the
# source-line guard) resolves 969/1015 (95%) of the qualified-name occurrences corpus-wide without
# regressing any in-class-body method.
# Deliberately NOT applied to every ctags language: most (python, java, csharp, ...) never write
# an out-of-class qualified definition at all, so this path is simply inert for them. If a similar
# convention turns up for another language's ledger shapes later, add it here rather than assuming
# this set is complete.
_QUALIFY_NAME_WITH_SCOPE = {"cpp"}


# ctags' scope VALUE for a member of a class nested inside an outer namespace includes that
# outer namespace as its own leading segment (`tensorflow::MlirOptimizationPassRegistry`,
# `__anon50f1088d0111::Translator` for an ANONYMOUS namespace) -- a real, structurally correct
# enclosing scope as far as ctags' own tree is concerned. But an out-of-class DEFINITION written
# INSIDE that same outer namespace's braces never needs to repeat it
# (`namespace tensorflow { ... MlirOptimizationPassRegistry::Global() {...} }` writes
# `MlirOptimizationPassRegistry::Global`, never `tensorflow::MlirOptimizationPassRegistry::Global`;
# an anonymous namespace can't be written at all), so GitGalaxy/tree-sitter's own qualified name
# never includes it either. Confirmed via mlir/mlir_graph_optimization_pass.cc's `tensorflow`
# namespace and mlir/flatbuffer_export.cc's anonymous-namespace-wrapped `Translator` class -- both
# failed the single full-chain containment check this replaced. Tries the FULL chain first, then
# progressively drops the outermost segment, so a genuinely multi-level qualifier that IS written
# out in full (`Object::Connection::operator<`, NVDA/storage.cpp) still matches at its own,
# longer candidate before any shorter one is tried.
def _cpp_qualified_name_candidates(scope_value: str, name: str):
    segments = scope_value.split("::")
    for i in range(len(segments)):
        yield "::".join(segments[i:]) + "::" + name


# universal-ctags' own C++ parser always renders an operator-overload tag name as `operator X`
# (a literal space between the keyword and the symbol), regardless of whether the source itself
# has a space there -- a fixed ctags naming convention, not a reading of the source text. GitGalaxy
# and tree-sitter both read the identifier as written in source, which for every sampled operator
# overload in this corpus has no space (`operator<`, `operator==`, `operator Variant`'s own
# genuine space before a type name is the one legitimate exception, left untouched). Confirmed via
# the same cpp/function/existence shapes above: stripping this one space resolves the remaining
# `operator <`/`operator ==`/`operator !=`/`operator =` mismatches once scope-qualification (above)
# is also applied.
_CTAGS_OPERATOR_SPACE_RE = re.compile(r"^operator (?=[^A-Za-z_])")


def _normalize_cpp_operator_name(name: str) -> str:
    return _CTAGS_OPERATOR_SPACE_RE.sub("operator", name)


def _parse_extension_fields(raw: str) -> dict[str, str]:
    """Parses `key:value` extension fields from a ctags tag line's tail, tab-separated. The
    `signature:(...)` field itself can legitimately contain further colons (e.g. Rust's
    `-> Result<X, Y>`), so this only splits on the FIRST colon per field, never blind-splits
    the whole tail on ':'."""
    fields: dict[str, str] = {}
    for part in raw.split("\t"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, _, value = part.partition(":")
        fields[key] = value
    return fields


def read_ctags_symbols(filepath: Path, lang: str) -> list[CtagsSymbol]:
    """Runs ctags against one file, returns every symbol whose kind is in
    CTAGS_FUNC_KINDS[lang] or CTAGS_CLASS_KINDS[lang]. Empty list if the language has no ctags
    parser, OR if universal-ctags isn't installed at all -- check ctags_available(lang) first if
    the caller needs to distinguish either of those from "parser ran, found nothing". Defensive,
    not just documentation: callers are expected to check ctags_available(lang) before calling
    this at all, but a missing binary degrades to an empty list here too rather than a raw
    FileNotFoundError from subprocess, since ctags is an optional, verification-only download
    (see module docstring) that a caller several layers up may not have re-checked."""
    if not (has_ctags() and lang in LANG_MAP):
        return []

    result = subprocess.run(
        [
            "ctags",
            "-f",
            "-",
            "--fields=+n",
            "--fields=+S",
            # ctags truncates its own "verbatim matched source line" pattern field by default
            # (confirmed ~100 chars) -- harmless for most tags, but this reader leans on that
            # exact text to decide cpp name-qualification (_QUALIFY_NAME_WITH_SCOPE) and
            # scoped-vs-unscoped enum detection (_is_cpp_unscoped_enum), both of which need the
            # FULL line, not a prefix. Confirmed real, not theoretical: a truncated pattern
            # silently broke qualification for godot/editor_node.cpp's
            # `Vector<Ref<EditorResourceConversionPlugin>> EditorNode::
            # find_resource_conversion_plugin_for_resource(...)` -- the truncated pattern cut off
            # mid-identifier before the closing name even appeared.
            "--pattern-length-limit=0",
            f"--language-force={LANG_MAP[lang]}",
            str(filepath),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    wanted_kinds = CTAGS_FUNC_KINDS.get(lang, set()) | CTAGS_CLASS_KINDS.get(lang, set())
    symbols: list[CtagsSymbol] = []
    for line in result.stdout.splitlines():
        if line.startswith("!"):
            continue
        # NOT a blind line.split("\t") -- the address/pattern field (cols[2] in the naive
        # reading) is `/^<verbatim matched source line>$/;"`, and that source text can itself
        # contain a literal TAB character when the real code uses tabs for column alignment
        # (confirmed real, not theoretical: language-crucible/data/c/doom/i_system.c's
        # `byte*\tI_AllocLow(int length)` -- old-school Doom-era C formatting). A tab-splitting
        # parser then reads a fragment of the SOURCE LINE as if it were the kind field, fails
        # the `kind not in wanted_kinds` check below, and silently drops the whole symbol --
        # confirmed via c/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags] (I_AllocLow,
        # I_ZoneBase, I_BaseTiccmd, R_CheckBBox, R_AddLine all missing from ctags' reading purely
        # because of this parsing bug, not because ctags itself failed to tag them -- a raw
        # ctags run against these files finds every one of them correctly). The tag-file format
        # guarantees the address field always ends with the literal `;"` marker before the
        # kind/extension-field trailer begins (ctags' own TAG_FILE_FORMAT spec) -- split on
        # THAT instead, and only tab-split the trailer (extension fields are simple `key:value`
        # pairs with no embedded source text, so tab-splitting is safe there).
        marker_idx = line.find(';"\t')
        if marker_idx == -1:
            continue
        name = line.split("\t", 1)[0]
        if not name:
            continue
        trailer_cols = line[marker_idx + len(';"\t') :].split("\t")
        kind = trailer_cols[0]
        if kind not in wanted_kinds:
            continue
        if lang == "cpp" and _is_cpp_unscoped_enum(kind, line[:marker_idx]):
            continue
        fields = _parse_extension_fields("\t".join(trailer_cols[1:]))
        line_no = int(fields["line"]) if "line" in fields else -1
        signature = fields.get("signature")
        if lang in _QUALIFY_NAME_WITH_SCOPE:
            name = _normalize_cpp_operator_name(name)
            source_text = line[:marker_idx]
            for scope_key in _CTAGS_SCOPE_KIND_KEYS:
                if scope_key in fields:
                    for candidate in _cpp_qualified_name_candidates(fields[scope_key], name):
                        if candidate in source_text:
                            name = candidate
                            break
                    break
        symbols.append(CtagsSymbol(name=name, line=line_no, kind=kind, signature=signature))
    return symbols
