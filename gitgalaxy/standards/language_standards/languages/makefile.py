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
        "target_version": "GNU Make 4.4+",
        "last_updated": "2026-02-28",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard make extensions, definitions, and includes.
    "extensions": [".mk", ".mak", ".make", ".def"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: The universally recognized, extensionless build configurations that are executed as pure code.
    "exact_matches": [
        "Makefile",
        "makefile",
        "GNUmakefile",
        "Kbuild",
        "Makeconf",
        "Makevars",
    ],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling configurations acting as disambiguation anchors to resolve ambiguous .mk includes.
    "discriminators": ["Makefile", "makefile", "configure.ac", "CMakeLists.txt"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for executable make scripts.
    "shebangs": ["make", "gmake"],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: Make natively uses '#' exclusively for line-level comments.
    "lexical_family": "line_exclusive",
    "rules": {
        # --------------------------------------------------------------------------
        # 1. GEOMETRY & SHAPE (Geometry & Shape)
        # --------------------------------------------------------------------------
        # Captures Make conditionals and typical inline shell conditional branches.
        "branch": re.compile(
            r"^[ \t]*(?:ifeq|ifneq|ifdef|ifndef|else|endif)\b(?![ \t]*:)|(?:^[ \t]*(?:@|-|\+)*[ \t]*|[;|&(][ \t]*)\b(?:if|elif|for|while|case)\b|&&|\|\|",
            re.M,
        ),
        # Make dynamically accesses arguments within $(call macro, args...) or positional $1, $2 inside recipes.
        # BUG FIX (epic #813/#844): had no awareness of Make's own `$$`
        # escaping convention (a doubled `$` means "a literal `$`,
        # unescaped, for whatever consumes this text next"). Recipe lines
        # commonly write `$$1`/`$$(1)` specifically to pass a literal
        # `$1` through to the SHELL (the shell's own first positional
        # parameter, or any other shell variable) -- unrelated to Make's
        # own macro-call mechanism entirely, since Make's own `$`
        # expansion already happened one layer up. The old pattern had no
        # way to tell these apart from a real Make-level reference. Fixed
        # with a negative lookbehind so a `$` immediately preceded by
        # another `$` can never start a match.
        "args": re.compile(r"(?<!\$)\$(?:\([0-9]+\)|\{[0-9]+\}|[0-9]\b|[({]call[ \t]+[a-zA-Z0-9_.-]+)"),
        # Smooth structural boundaries: variable assignments (:=, =, ?=) and native structural controls like vpath.
        # Explicitly excludes the append operator `+=` which belongs in flux.
        "structural_boundaries": re.compile(
            r"^[ \t]*(?:[a-zA-Z0-9_.-]|\+(?!=))+[ \t]*(?::|\?|::)?=(?![ \t]*=)|^[ \t]*(?:vpath|undefine)\b",
            re.M,
        ),
        # 4. func_start (Executable Logic Anchors)
        # Strict capture group and positive lookahead applied for both Obj-C methods and C-functions.
        # BUG FIX (epic #813/#844), two findings:
        # 1. The trailing lookahead only checked for a bare `:`/`::`, with
        #    no exclusion for an immediately-following `=` -- so
        #    `MY_VAR := value` and `MY_VAR ::= value` (GNU Make's two
        #    immediate-expansion assignment operators, arguably THE most
        #    common modern Make idiom) were both misidentified as real
        #    target declarations. Fixed with a negative lookahead so
        #    neither colon form can be immediately followed by `=`.
        # 2. A multi-target rule (`a b c: deps`, a real and common Make
        #    idiom for sharing one recipe across several targets) wasn't
        #    detected AT ALL -- the identifier class stopped at the first
        #    space, then the colon lookahead failed against the next
        #    target name instead of a colon, and there's no second `^`
        #    anchor point later on the same line to retry from. Fixed by
        #    allowing additional space-separated co-target tokens (same
        #    char class) between the captured first name and the colon
        #    lookahead -- but this alone reopened a NEW false-positive
        #    vector: a recipe line with multiple words where a later word
        #    contains a colon not followed by `=` (a URL's `://`, a bare
        #    time value `10:30`) would misparse as "co-target tokens then
        #    a real target-defining colon". Recipe lines are ALWAYS
        #    tab-indented in Make's own lexical rules (a leading tab means
        #    "recipe", unconditionally, absent a custom .RECIPEPREFIX) --
        #    so the leading-whitespace class was narrowed from `[ \t]*` to
        #    `[ ]*` (spaces only), which structurally excludes every
        #    recipe line from ever reaching the target-declaration path at
        #    all, closing the new vector without limiting the multi-target
        #    fix itself.
        #
        # Considered and DELIBERATELY NOT fixed: a variable-referenced
        # target name (`$(TARGET): $(OBJECTS)`, also common) is still
        # invisible -- `$`/`(`/`)` are still outside the char class. This
        # is intentional, not an oversight: tests/extraction/languages/test_makefile_strict
        # .py's test_makefile_func_start_and_macros_no_false_collision
        # deliberately locks in that `$(1): $(2)` (a `define...endef`
        # template's macro-positional-parameter placeholder) must NOT
        # satisfy func_start, and this rule has no block/context tracking
        # (line_exclusive lexical family) to distinguish that shape from a
        # real `$(TARGET):` reference at the regex level. Safely
        # separating the two would need a structured token (real
        # variable names vs. bare positional-parameter digits), not a
        # flat character-class widening -- judged out of scope for this
        # issue; documented as a known limitation instead.
        "func_start": re.compile(
            r"^[ ]*(?!\.(?:PHONY|POSIX|SECONDARY|PRECIOUS|DELETE_ON_ERROR|KEEP_STATE|NOTPARALLEL|WAIT|SILENT|EXPORT_ALL_VARIABLES|IGNORE|SUFFIXES|DEFAULT|INTERMEDIATE|NOTINTERMEDIATE|LOW_RESOLUTION_TIME|ONESHELL|SECONDEXPANSION)\b)"
            r"([a-zA-Z0-9_./%+-]+)(?:[ \t]+[a-zA-Z0-9_./%+-]+)*(?=[ \t]*(?:::(?!=)|:(?!:?=)))",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Defines OO boundaries. Strict capture group and positive lookahead applied.
        "class_start": None,
        # --------------------------------------------------------------------------
        # 2. STRUCTURAL INTEGRITY & TECH DEBT (Structural Integrity & Tech Debt)
        # --------------------------------------------------------------------------
        # Defensive programming: Executing internal logic checks, asserting tool paths, or using safety system states.
        "safety": re.compile(
            r"^[ \t]*\.(?:POSIX|SECONDARY|PRECIOUS|DELETE_ON_ERROR|KEEP_STATE)\b|\bcommand[ \t]+-v\b|\$\((?:if|or|and)[ \t]+",
            re.M,
        ),
        # Bypassing safety: Prefixing recipes with `-` to swallow errors, or forcefully exiting true via shell logic.
        # NOTE: real recipes commonly separate the `-` modifier from the command with
        # whitespace (e.g. "\t- rm -f build/"); GNU Make strips the modifier and any
        # following whitespace before invoking the shell, so both "-rm" and "- rm" are
        # valid, equally common ignore-errors forms.
        "safety_bypasses": re.compile(r"^\t[ \t]*-[ \t]*[a-zA-Z0-9_./$]|\|\|[ \t]*(?:true|exit[ \t]+0)\b", re.M),
        # Heavily destructive sequence patterns or overriding permissions. (Eval is categorized under heat_triggers).
        "high_risk_execution": re.compile(r"\bsudo[ \t]+|\brm[ \t]+-[rR]?[fF][ \t]+(?:/|\$[{(])|\bkill[ \t]+-9\b"),
        # Interacting directly with outputs, networks, or the disk filesystem.
        "io": re.compile(
            r"\$\((?:file|wildcard)[ \t]+|\b(?:curl|wget|scp|rsync|tar|unzip|mkdir|cp|mv)\b|>>?[ \t]*[^ \t\n/]+"
        ),
        # Exposed architecture limits (Exporting variables globally or explicit lifecycle public endpoints).
        "api": re.compile(
            r"^[ \t]*(?:\.PHONY|export\b|(?:all|install|build|clean|test|run)[ \t]*::?)",
            re.M,
        ),
        # Mutating variable state by appending (+=) or shell assignment (!=). .
        "state_mutation": re.compile(r"^[ \t]*(?:[a-zA-Z0-9_.-]|\+(?!=))+[ \t]*(?:\+|!)=", re.M),
        # Commented-out targets, commented out shell logic, or commented conditional Make directives.
        "dead_code": re.compile(
            r"^[ \t]*#[ \t]*(?:[a-zA-Z0-9_./%+-]+[ \t]*::?|(?:[a-zA-Z0-9_.-]|\+(?!=))+[ \t]*(?::|\?|::)?=|\b(?:ifeq|ifneq|ifdef|ifndef|include)\b)",
            re.M,
        ),
        # Structured self-documenting makefile comments typically utilizing a double hash block.
        "doc": re.compile(r"^[ \t]*##[ \t]+[^ \t\n]+", re.M),
        # Testing endpoints natively executing verifications or launching language-specific test suites.
        "test": re.compile(
            r"\b(?:npm[ \t]+test|yarn[ \t]+test|pytest|go[ \t]+test|cargo[ \t]+test|make[ \t]+test)\b",
            re.M | re.I,
        ),
        # --------------------------------------------------------------------------
        # 3. DOMAIN & ARCHITECTURE (Architectural Style and Abstractions)
        # --------------------------------------------------------------------------
        # Setting explicitly threaded job pipelines, detaching processes to background, or asserting waits.
        "concurrency": re.compile(
            r"\b(?:make[ \t]+-j|xargs[ \t]+-P|wait)\b|&[ \t]*$|\$\(MAKE\)[ \t]+-j",
            re.M,
        ),
        "ui_framework": None,
        "closures": None,
        # Core global state built-in environments spanning the build system.
        "globals": re.compile(r"\$\((?:MAKE|MAKEFLAGS|MAKECMDGOALS|CURDIR|SHELL|PATH|USER|HOME|PWD|\.VARIABLES)\)"),
        "decorators": None,
        "generics": None,
        # High-density text manipulating algorithms native to GNU Make iterating through variable spaces.
        "comprehensions": re.compile(
            r"\$\((?:foreach|filter|filter-out|patsubst|subst|addprefix|addsuffix|words|firstword|lastword|sort|findstring|join)[ \t]+"
        ),
        # Launching explicit calculation boundaries outside the Make environment natively.
        "scientific": re.compile(r"\b(?:bc|expr|awk)\b|\$\(shell[ \t]+expr[ \t]+"),
        # Extremely dense meta-programming manipulations drastically raising cognitive load during debugging.
        "reflection_metaprogramming": re.compile(
            r"\$\((?:eval|call|value|origin|flavor|shell)[ \t]+|\.SECONDEXPANSION:"
        ),
        # Linking isolated segments of the graph execution via modular file resolution.
        "import": re.compile(r"^[ \t]*-?(?:include|sinclude)[ \t]+[^ \t\n]+", re.M),
        # BUG FIX (epic #813/#844): the leading `[ \t]*` allowed a TAB, but
        # a tab-initial line is ALWAYS a recipe command in Make's own
        # lexical rules (never a directive, absent a custom
        # .RECIPEPREFIX) -- same root cause and fix as func_start's fix
        # above. A recipe line whose command happens to be literally
        # named "include"/"sinclude" (e.g. `\tinclude /etc/motd`) was
        # misidentified as a real include directive. Narrowed to `[ ]*`
        # (spaces only), matching func_start's fix. `import` (a sibling,
        # non-gauntlet-scoped rule with the same pattern) deliberately
        # left unfixed, out of the four-gauntlet scope for this issue --
        # same precedent as #843's identical call for yaml.
        "_dependency_capture": re.compile(r"^[ ]*-?(?:include|sinclude)[ \t\n]+([^\s#]+)", re.M),
        # Metadata anchoring authorship and structural domain owners.
        "ownership": re.compile(
            r"^[ \t]*#[ \t]*(?:@author\b|author:|maintainer:|created by:)",
            re.I | re.M,
        ),
        # --------------------------------------------------------------------------
        # 4. SPECIALIZED EXTRACTIONS (Sub-Equations and Low-Level/System)
        # --------------------------------------------------------------------------
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:spec-[0-9]+|audit|spec)\]", re.I),
        "ssr_boundaries": None,
        "events": None,
        "dependency_injection": None,
        # Expanding structural blocks dynamically into recipes prior to runtime evaluation.
        "macros": re.compile(r"^[ \t]*define[ \t]+[a-zA-Z0-9_.-]+", re.M),
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --------------------------------------------------------------------------
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # --------------------------------------------------------------------------
        # Emitting pure, safe structural observability that does not risk halting or crashing the graph execution.
        # NOTE: bounded to one level of nested $(...) (e.g. "$(info Building $(call name))")
        # instead of a flat [^)\n]* class, which truncated at the first inner ")" and
        # under-captured the real $(info ...) span on realistic nested-call messages.
        "telemetry": re.compile(r"\$\(info[ \t]+(?:[^()\n]|\([^()\n]*\))*\)"),
        # Standard output commands echoing transient debris to the shell execution log.
        # NOTE: also matches echo/printf immediately after a `;` (the common one-liner
        # recipe form "target: deps; echo hi"), not just at true line start -- recipes are
        # frequently written on the same physical line as the target when short.
        "debug_prints": re.compile(
            r"^[ \t]*@?(?:echo|printf)[ \t]+|;[ \t]*@?(?:echo|printf)[ \t]+|\$\(warning[ \t]+(?:[^()\n]|\([^()\n]*\))*\)",
            re.M,
        ),
        "explicit_casts": None,
        # System detonators specifically intended to abort the build flow if preconditions are failed natively or via shell.
        "panics_and_aborts": re.compile(
            r"\$\(error[ \t]+(?:[^()\n]|\([^()\n]*\))*\)|\bexit[ \t]+[1-9][0-9]*\b|\bfalse\b"
        ),
        # Temporal duct tape strictly applying forced pausing.
        "thread_sleeps": re.compile(r"\bsleep[ \t]+[0-9]+"),
        "bitwise_ops": None,  # Kept null as Bash pipe IPC limits logic math precision.
        # Explicit locks halting temporal thread races. .
        "sync_locks": re.compile(r"^[ \t]*\.(?:NOTPARALLEL|WAIT)[ \t]*::?|\bflock[ \t]+", re.M),
        # Enforcing strict immutability bounds on state configuration. .
        "immutability_locks": re.compile(r"^[ \t]*override[ \t]+[a-zA-Z0-9_.-]+", re.M),
        # Janitor routines ripping apart build artifacts and cleanly tearing down output paths. .
        "cleanup": re.compile(r"^[ \t]*(?:dist)?clean[ \t]*::?|\brm[ \t]+-[a-zA-Z]*f[a-zA-Z]*\b", re.M),
        # The Vault explicitly hiding scope logic away from external API leakage boundaries. .
        "encapsulation": re.compile(
            r"^[ \t]*(?:unexport[ \t]+[a-zA-Z0-9_.-]+|[a-zA-Z0-9_.-]+[ \t]*:[ \t]*private[ \t]+|\.SILENT[ \t]*:)",
            re.M,
        ),
        # Subscribing the file system to continuous native observation hooks.
        "listeners": re.compile(r"\b(?:inotifywait|watch)[ \t]+"),
        # Safety theater actively bypassing execution verifications during a test endpoint invocation.
        "test_skip": re.compile(
            r"\b(?:SKIP(?:_TESTS?)?|XFAIL)[ \t]*=[ \t]*[1TtYy]|\bpytest[ \t]+-k[ \t]+not\b|--skip",
            re.I,
        ),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Makefile Specifics) ---
        # NOTE: `^\s*` (matching `\n` under re.M) is a confirmed real O(n^2) ReDoS on a
        # long run of blank lines with no closing keyword -- each blank-line `^` position
        # re-scans forward through the rest of the run before failing. Swapped for the
        # engine's mandated `^[ \t]*` form (Rule 5), which cannot cross a newline and is
        # therefore bounded to the current line.
        "serialization_parsing": re.compile(r"(?m)^[ \t]*(?:@|-)?(?:tar|unzip|gunzip|jq|sed|awk)\b"),
        "regex_execution": re.compile(r"(?m)\$\((?:filter|filter-out|patsubst)\b|^[ \t]*(?:@|-)?(?:grep|egrep|sed)\b"),
        "time_date_logic": re.compile(r"(?m)\$\(shell[ \t]+date\b|^[ \t]*(?:@|-)?(?:sleep|date)\b"),
        "ipc_rpc_bridges": re.compile(r"(?m)\$\(shell\b|^[ \t]*(?:@|-)?(?:curl|wget|ssh|scp|docker|kubectl)\b"),
    },
}
