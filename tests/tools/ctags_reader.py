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
      - cobol: GitGalaxy's class_start covers PROGRAM-ID / CLASS-ID / INTERFACE-ID / FACTORY /
        OBJECT paragraphs. ctags' Cobol parser only has a "program" (P) kind -- no CLASS-ID/
        INTERFACE-ID equivalent exists at all. Permanent, structural gap: ctags can partially
        check GitGalaxy's Cobol class detection (PROGRAM-ID only), never fully.
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
    "fortran": {"f", "s"},  # functions, subroutines
    "go": {"f"},
    "haskell": {"f"},
    "html": set(),
    "java": {"m"},
    "javascript": {"f", "m"},  # functions + methods
    # kotlin: ctags has no separate free-function kind -- top-level functions tag "m" too
    # (verified via probe file: a file-scope `fun` with no enclosing class still tags "m",
    # just without a `class:` field), so "m" alone already covers both cases.
    "kotlin": {"m"},
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
    "cobol": {"p"},  # paragraph -- GitGalaxy's own func_start for cobol targets paragraphs
    "embedded_python": {"f", "m"},  # same method-vs-function split as python above
    "m4": {"d"},  # macro -- M4's def-like construct
    "scheme": {"f"},
    "sqlite": {"f", "p"},  # function + procedure
    "yacc": set(),  # ctags' YACC parser only tracks label/token, not grammar rule definitions
    # -- GitGalaxy has functions to find here, ctags structurally cannot see them
}

CTAGS_CLASS_KINDS: dict[str, set[str]] = {
    "c": {"s"},  # struct -- matches GitGalaxy's own C class_start convention
    "cpp": {"c", "s"},  # class, struct
    "csharp": {"c", "s", "i"},  # class, struct, interface
    "css": {"c"},  # CSS "class" kind is a literal .class selector -- matches GitGalaxy's own
    # css class_start intent (it also targets selector-like entities)
    "fortran": {"t"},  # derived types and structures
    "go": {"s", "i"},  # struct, interface -- matches GitGalaxy's own `type X struct|interface`
    "haskell": set(),  # no class-shaped kind in ctags' Haskell parser at all
    "html": set(),
    "java": {"c", "i", "g"},  # class, interface, enum
    "javascript": {"c"},
    "kotlin": {"c", "i"},  # class, interface
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
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        name = cols[0]
        # cols[2] is the /pattern/;" search pattern, cols[3] is the kind, cols[4:] are
        # extension fields (line:N, signature:(...), class:Foo, etc.)
        kind = cols[3]
        if kind not in wanted_kinds:
            continue
        fields = _parse_extension_fields("\t".join(cols[4:]))
        line_no = int(fields["line"]) if "line" in fields else -1
        signature = fields.get("signature")
        symbols.append(CtagsSymbol(name=name, line=line_no, kind=kind, signature=signature))
    return symbols
