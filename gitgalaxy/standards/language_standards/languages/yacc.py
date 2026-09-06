# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re
from typing import Any

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "GNU Bison / Yacc / Flex",
        "last_updated": "2026-03-11",
        "blueprint_version": "v5.1",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Yacc/Bison parser grammars (.y) and Lex/Flex tokenizers (.l), plus their C++ variants (.ypp, .lpp).
    "extensions": [".y", ".yy", ".ypp", ".l", ".ll", ".lpp"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Parser generators rely strictly on extensions.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: The generated C/C++ outputs and standard build systems acting as disambiguation anchors.
    "discriminators": [
        ".c",
        ".cpp",
        ".h",
        "Makefile",
        "CMakeLists.txt",
        "configure.ac",
    ],
    # EXECUTION SIGNATURES: Grammars are compiled into C/C++ state machines; no shebangs exist.
    "shebangs": [],
    # INTERNAL DISCRIMINATOR (Collision Resolution Only): `.y`/`.yy`/`.ypp` (and the lex
    # `.l` family) collide with C -- the C-action blocks in a real grammar routinely
    # out-mass the grammar itself, so a plain lexical density scan misclassifies
    # action-heavy grammars as `c` (confirmed: freebsd's config.y). These line-start
    # markers are definitive yacc/bison/lex syntax that no plain C file ever contains:
    # the `%{`/`%}` prologue delimiters, the `%%` section separator, and the `%token`/
    # `%union`/... declaration keywords. Matches the same collision-resolution role
    # objective-c/matlab already use for `.m`.
    "internal_discriminator": re.compile(
        r"^%\{|^%\}|^%%[ \t]*(?:$|/[/*])"
        r"|^%(?:token|type|union|left|right|nonassoc|precedence|start|prec|expect(?:-rr)?"
        r"|define|code|option|name-prefix|pure-parser|glr-parser|parse-param|lex-param"
        r"|require|language|locations|destructor|printer|initial-action|empty)\b",
        re.M,
    ),
    # UPGRADED: Maps to Family 1 (Standard C-Style)
    # Rationale: Yacc and Lex files interleave grammar definitions with pure C/C++ code
    # blocks (enclosed in %{ %}), relying entirely on standard '/* */' and '//' comments.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        "branch": re.compile(r"\b(if|else|switch|case|for|while|do)\b|\|"),
        "args": re.compile(r"(?<!\$)\$(?:<[a-zA-Z_]\w*>)?(?:-?\d+|\$)(?!\$|\w)"),
        "structural_boundaries": re.compile(
            r"\b(return|goto|break|continue)\b|%token\b|%type\b|%left\b|%right\b|%nonassoc\b"
        ),
        # Executable Logic Anchor: Anchors specifically onto Grammar Rules
        # Matches "rule_name :" or "rule_name:" at the start of a line.
        # Excludes C/C++ constructs that share the identical "identifier:" shape
        # (switch-case default labels, C++ access specifiers in embedded .ypp code).
        "func_start": re.compile(
            r"^[ \t]*(?!(?:case|default|public|private|protected)\b)([a-zA-Z_]\w*)(?=(?:[ \t\n]|/\*(?:[^*]|\*[^/])*\*/|//[^\n]*)*:)",
            re.M,
        ),
        # #2644: Bison/Yacc's `%union` directive declares a real compound type --
        # the C union spanning every rule's semantic value (`$$`/`$1`, already
        # counted by `args`). Same "non-OOP language's struct/class equivalent"
        # mapping the engine already makes for Fortran's `TYPE ... END TYPE`,
        # COBOL's `PROGRAM-ID` and assembly's `struc` macros -- and core grammar
        # syntax, not embedded C: `internal_discriminator` above already lists
        # `union` among the `%`-directives that IDENTIFY a file as yacc.
        #
        # Optional group 1 captures bison's rarer named-tag form (`%union name {`);
        # the common anonymous form leaves it unset and resolves to
        # "Anonymous_Class" through `_resolve_class_start_match`, the same path
        # assembly's own no-name `class_start` takes. Deliberately no group 2 --
        # a union has no inheritance parent for detector.py's group-2-is-parent
        # convention to misread.
        #
        # NOTE: this rule is only reachable for named extraction because yacc is
        # in detector.py's `_CLASS_START_NAMED_EXTRACTION_LANGS`. Removing it
        # there does not restore the old behavior -- it drops yacc onto the
        # legacy generic fallback (`class|struct|interface|trait|enum`), which
        # reads every `struct foo` declaration in a grammar's embedded C actions
        # as a class: 17 and 9 on the two real corpus grammars where the honest
        # answer is 1 each. The two changes only make sense together.
        "class_start": re.compile(r"^[ \t]*%union\b(?:[ \t]+([a-zA-Z_]\w*))?", re.M),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(r"\b(assert|YYABORT|YYACCEPT|YYERROR)\b"),
        "safety_bypasses": re.compile(r"\bgoto\b|\bvoid\s*\*"),
        "high_risk_execution": re.compile(r"\b(abort|exit|YYNOMEM)\b"),
        "io": re.compile(r"\b(fopen|fclose|fread|fwrite|yyin|yyout|fprintf)\b"),
        "api": re.compile(r"%define\b|%code\b|%provides\b|%requires\b"),
        "state_mutation": re.compile(
            # #2765 contract: one hit is a statement that writes a new value into state
            # that already exists. A declaration is not a write, even with an initializer,
            # so the assignment arm anchors a STATEMENT START to a bare lvalue -- a type
            # name in front of the lvalue breaks the match. `==` is excluded by the
            # operator set, a trailing-comma line (enum member / named argument) is not
            # a statement, and `++`/`--` must touch an operand (a run of dashes inside a
            # string literal is not an increment).
            # `$$` / `$1` are the semantic-value lvalues of an action block.
            r"(?:^|[;{}(),])[ \t]*\**(?:\$\$|\$\d{1,3}|[A-Za-z_]\w*)(?:(?:\.|->)[A-Za-z_]\w*|\[[^\]\n]{0,80}\])*"
            r"[ \t]*(?:[-+*/%&|^]|<<|>>)?=(?![=])(?![^\n(]{0,300},[ \t]*$)"
            r"|[\w)\]$][ \t]*(?:\+\+|--)|(?:\+\+|--)[ \t]*[A-Za-z_(*$]",
            re.M,
        ),
        "dead_code": re.compile(r"//[ \t]*(?:if|for|while|return|%token)\b|/\*[ \t]*(?:if|for|while|return|%token)"),
        # #2672: doc-family fix -- block form first (bounded, non-greedy, same
        # shape/bound as #2658) so a whole /** ... */ doc comment counts once
        # even when it carries @param/@return tags inside it, instead of once
        # per marker plus once per tag. Bare tags remain last so a tag
        # outside any doc comment (not applicable to yacc today, but kept for
        # family-shape parity) still counts. yacc's own corpus doc line is a
        # single-star `/* @param ... */` comment, which `/\*\*` never
        # matches, so this is corpus-inert for yacc (doc stays 1) -- the
        # fix only changes yacc's off-corpus behavior on a real `/** ... */`
        # Doxygen-style block.
        "doc": re.compile(r"/\*\*[\s\S]{0,15000}?\*/|@param|@return"),
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": None,
        "ui_framework": None,
        "closures": None,
        "globals": re.compile(r"\b(yylval|yylloc|yynerrs|yydebug)\b"),
        "decorators": None,
        "generics": re.compile(r"<[a-zA-Z_][a-zA-Z0-9_]*>"),  # Captures %type <val>
        "comprehensions": None,
        "scientific": None,
        "reflection_metaprogramming": re.compile(r"%\{|%\}|%%"),
        "import": re.compile(r'^[ \t]*#(?:include)\s*[<"][^>"]+[>"]', re.M),
        # BUG FIX (#2652 shape, #2668): same gap as m4 above -- the `import`
        # signal was counted but never became a DAG edge, leaving yacc in
        # keyword-rosetta's `no-dependency-capture-languages` entry with a
        # structurally empty graph. Captures the header out of the same
        # preprocessor form the `import` rule matches (grammar files carry
        # ordinary C `#include`s in their prologue); both delimiters and the
        # quantifier are bounded (Engine Rule 14).
        "_dependency_capture": re.compile(r'^[ \t]*#[ \t]*include[ \t]*[<"]([^>"\n]{1,200})[>"]', re.M),
        "ownership": re.compile(r"(?:@author|Author:|Created by:|Copyright)\s+(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": None,
        "events": None,
        "dependency_injection": None,
        "macros": re.compile(r"^[ \t]*#(?:define|undef|if|elif|else|endif|pragma)\b", re.M),
        "pointers": re.compile(r"->|&\w+|(?<=[=(,])[ \t]*\*(?:\s*const\s*)?[a-zA-Z_]\w*"),
        "memory_alloc": re.compile(r"\b(malloc|calloc|realloc|free|YYMALLOC|YYFREE)\b"),
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(r"\b(?:syslog|openlog|log_info|YYDPRINTF)\b"),
        "debug_prints": re.compile(r"\b(printf|fprintf|vprintf|puts|yyerror)\b"),
        "explicit_casts": re.compile(
            r"\([ \t]{0,20}(?:int|char|short|long|float|double|void|unsigned|signed|[A-Z]\w*)"
            r"[ \t]{0,20}\*?[ \t]{0,20}\)[ \t]{0,20}[a-zA-Z_$]"
        ),
        "panics_and_aborts": re.compile(r"\b(abort|exit|YYABORT)\b"),
        "thread_sleeps": None,
        "bitwise_ops": re.compile(r"<<|>>|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
        "sync_locks": None,
        "immutability_locks": re.compile(r"\bconst\b"),
        "cleanup": re.compile(r"\b(free|YYFREE|fclose|destroy)\b\s*\("),
        "encapsulation": re.compile(r"^[ \t]*static\b", re.M),
        "listeners": None,
        "test_skip": None,
    },
}
