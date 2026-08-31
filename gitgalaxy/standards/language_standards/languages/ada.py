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
        "target_version": "Ada 2012 / SPARK 2014 (GNAT Pro / GNAT CE)",
        "last_updated": "2026-08-07",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: .ads (package/subprogram specs), .adb
    # (bodies), and the historic single-extension convention .ada.
    "extensions": [".adb", ".ads", ".ada"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS: GNAT project files (.gpr) are the dominant
    # Ada build-system anchor (GPRbuild/GNAT Studio), the closest
    # analogue to a manifest file for disambiguation purposes.
    "discriminators": [".adb", ".ads", ".gpr"],
    # EXECUTION SIGNATURES: Ada is compiled; there is no interpreter
    # shebang convention in real-world use.
    "shebangs": [],
    # Rationale (Lexical-family sanity check, how_to_add_a_language.md
    # Step 4 item 8): issue #76 / epic #75 both label this "hybrid_dash",
    # but Ada genuinely has no block-comment form at all -- "no native
    # block comments historically" is stated directly in #76's own
    # checklist, which contradicts the "hybrid_dash" name it also asks
    # for. Reusing the existing "line_exclusive" family was also
    # rejected: that family's shared delimiter list is consumed by a
    # literal-string family-name check in prism.py, and several of its
    # existing members (Perl, Assembly) use `--` as a real
    # operator/decrement -- widening that shared list would silently
    # truncate real code in unrelated languages (the exact failure mode
    # #621 already fixed once by narrowing "standard_block"). Registered
    # a new, properly-wired "line_exclusive_dash" family instead (single
    # `--` delimiter, no block form) -- see gitgalaxy_config.py's
    # LEXICAL_FAMILY_HEURISTICS and prism.py's _compile_regex_matrix.
    "lexical_family": "line_exclusive_dash",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: Ada's short-circuit forms are the two-word "and then"/
        # "or else" (no && / || symbols exist in Ada).
        "branch": re.compile(
            r"\b(?:if|elsif|else|case|when|for|while|loop|exit)\b|\band[ \t]+then\b|\bor[ \t]+else\b",
            re.I,
        ),
        # args: parameter profile following a procedure/function name.
        # Bounded 3-level nested-paren capture (Rule 11) since default
        # expressions routinely contain nested calls/aggregates, e.g.
        # `Y : Integer := Compute(A, (B + C))`.
        "args": re.compile(
            r"\b(?:procedure|function)\b[ \t\n]+[A-Za-z_][A-Za-z0-9_]*[ \t\n]*"
            r"\(((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)",
            re.I,
        ),
        # structural_boundaries: procedure/function/begin/end (per #76's
        # explicit checklist) plus package (Ada's module/namespace
        # boundary keyword) and return (statement form, distinct from
        # func_start's own "return TYPE" clause).
        "structural_boundaries": re.compile(r"\b(?:procedure|function|package|begin|end|return)\b", re.I),
        # func_start: STRICT EXECUTION ANCHORING (Rule 7) -- only a real
        # subprogram BODY, not a bare spec-only declaration. Ada's spec
        # declaration ends `;` right after the profile/return type with
        # no "is"; a body always has a literal "is" there instead. Must
        # also exclude "is abstract"/"is null" (null procedures, both
        # still declarations, not bodies) and "is new" (generic
        # subprogram instantiation, not a body either). SPARK code
        # commonly attaches `with Pre => ..., Post => ...` aspect
        # clauses directly on a body between the profile and "is" --
        # bounded (not unbounded `.*`) so it can't cross a statement
        # terminator or blow up on an adversarial payload.
        "func_start": re.compile(
            r"\b(?:procedure|function)[ \t\n]+([A-Za-z_][A-Za-z0-9_]*)"
            r"(?:[ \t\n]*\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))?"
            r"(?:[ \t\n]+return[ \t\n]+[A-Za-z_][A-Za-z0-9_.]*)?"
            r"(?:[ \t\n]+with[ \t\n]+[^;{}]{0,300}?)?"
            r"[ \t\n]*is\b(?![ \t\n]*(?:abstract|null|new)\b)",
            re.I,
        ),
        # class_start: Ada's OOP entity is a *tagged* type, either a root
        # declaration (`type Foo is tagged record ...`) or a derived/
        # extended one (`type Dog is new Animal with record ...` --
        # inheritance is expressed via "is new BASE with", the literal
        # word "tagged" is NOT repeated on a derived type, so both forms
        # need their own alternative or the (more common, in an
        # OOP-heavy codebase) derived form is entirely invisible).
        "class_start": re.compile(
            r"\btype[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t\n]+is[ \t\n]+"
            r"(?:(?:abstract[ \t\n]+)?(?:limited[ \t\n]+)?tagged\b"
            r"|(?:abstract[ \t\n]+)?new[ \t\n]+[A-Za-z_][A-Za-z0-9_.]*[ \t\n]+with\b)",
            re.I,
        ),
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety: per #76's explicit ask -- strict-typing range
        # constraints (`type ... is range`, but also the equally common
        # `subtype X is Base range Lo .. Hi` form, where "is" and
        # "range" are NOT adjacent -- matching only "is range" verbatim
        # would miss the subtype form entirely) and safety-oriented
        # pragmas/aspects (Assert, Precondition, Postcondition,
        # Invariant, Predicate) -- deliberately NOT bare "pragma" (Rule
        # 1: many pragmas, e.g. Pack or Import, have nothing to do with
        # safety; matching all of them would be keyword-stuffing, not
        # semantic intent). Also real exception-handling constructs.
        # (?<!') on "range" excludes the unrelated `Arr'Range` attribute
        # (array index-range query), which shares the bare word but has
        # nothing to do with a type's strict-typing constraint.
        "safety": re.compile(
            r"\bexception\b|\bwhen[ \t]+others\b"
            r"|\bpragma[ \t]+(?:Assert|Assertion_Policy|Precondition|Postcondition|Invariant|Predicate)\b"
            r"|(?<!')\brange\b",
            re.I,
        ),
        # safety_bypasses: Unchecked_Conversion (raw memory
        # reinterpretation -- Rule 2's own canonical example),
        # pragma Suppress (disables compiler-inserted runtime checks),
        # pragma Import (FFI boundary bypassing Ada's normal safety),
        # and the GNAT-specific 'Unrestricted_Access attribute
        # (bypasses accessibility/aliasing rules entirely).
        "safety_bypasses": re.compile(
            r"\bUnchecked_Conversion\b|\bpragma[ \t]+Suppress\b|\bpragma[ \t]+Import\b"
            r"|'Unrestricted_Access\b",
            re.I,
        ),
        # high_risk_execution: GNAT.OS_Lib.OS_Exit is Ada's real
        # equivalent of process.exit -- an immediate, uncatchable
        # process termination (distinct from `raise`/`abort`, which are
        # ordinary language-level exception/task-termination constructs
        # routed to panics_and_aborts per the branch/func_start
        # exclusion notes above).
        "high_risk_execution": re.compile(r"\bOS_Exit\b|\bGNAT\.OS_Lib\.OS_Exit\b", re.I),
        # io: disk/network/external-system boundaries. EXCLUDES
        # Put_Line/Put (stdout -- debug_prints below).
        "io": re.compile(
            r"\bAda\.Text_IO\.(?:Open|Create|Close|Delete|Reset)\b"
            r"|\bAda\.Directories\b|\bAda\.Streams\b|\bAda\.Direct_IO\b"
            r"|\bAda\.Sequential_IO\b|\bGNAT\.Sockets\b",
            re.I,
        ),
        # api: per #76's explicit ask -- package specifications. EXCLUDES
        # "package body" (private implementation, not a public spec) and
        # "package X is new ..." (generic package instantiation, not a
        # spec declaration -- both use negative lookaheads, not an
        # optional group, per Rule 15).
        "api": re.compile(
            r"\bpackage[ \t]+(?!body\b)(?:private[ \t]+)?([A-Za-z_][A-Za-z0-9_.]*)[ \t\n]+is\b(?![ \t\n]*new\b)",
            re.I,
        ),
        # state_mutation: Ada's assignment operator `:=` is lexically
        # distinct from `=` (equality) -- no ambiguity to guard against.
        "state_mutation": re.compile(r":="),
        # dead_code: commented-out structural code (line_exclusive_dash
        # has exactly one comment style, so no completeness gap per
        # Rule 12).
        "dead_code": re.compile(r"--[ \t]*(?:procedure|function|if|for|while|begin|end|type|package)\b", re.I),
        # doc: structured doc-comment conventions (GNATdoc-style tags;
        # Ada has no single standardized docstring format).
        "doc": re.compile(
            r"--[ \t]*(?:@param|@return|@exception|Purpose:|Parameters?:|Returns?:|Preconditions?:|Postconditions?:)",
            re.I,
        ),
        # test: AUnit (the dominant Ada unit-testing framework) and the
        # standard-library Ada.Assertions.Assert.
        "test": re.compile(r"\bAUnit\b|\bAda\.Assertions\b|\bAssert[ \t]*\(", re.I),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # concurrency: Ada's built-in hardware concurrency model --
        # tasks, protected objects, the select/accept rendezvous, and
        # delay. Broad domain signal, intentionally overlapping the more
        # specific sync_locks/thread_sleeps/events/listeners below (same
        # design already established for COBOL's EXEC CICS ENQ/DELAY).
        "concurrency": re.compile(r"\btask\b|\bprotected\b|\bselect\b|\bdelay\b|\baccept\b|\bentry\b", re.I),
        # ui_framework: no idiomatic built-in UI paradigm (GtkAda exists
        # but isn't a realistic default host -- Strict Feature Parity,
        # Rule 4: an empty/never-matching rule is worse than an absent
        # one, since it implies detection coverage that doesn't exist).
        "ui_framework": None,
        # closures: Ada has no anonymous-function/lambda literal syntax.
        "closures": None,
        # globals: SPARK's own Global aspect explicitly declares a
        # subprogram's global-state dependencies -- a direct, idiomatic
        # match for this key. pragma Volatile marks genuinely shared
        # (e.g. memory-mapped hardware register) state.
        "globals": re.compile(r"\bGlobal[ \t]*=>|\bpragma[ \t]+Volatile\b", re.I),
        # decorators: Ada 2012 aspect specifications (`with Pre => ...`)
        # attached to a declaration, PLUS SPARK's data-flow refinement
        # aspects (Abstract_State/Initializes/Refined_Global/
        # Refined_Post/Refined_State/Refined_Depends -- how a package's
        # private state gets formally modeled for the prover; common in
        # real SPARK code, distinct from the Pre/Post/Global/Depends
        # contract basics above) and the `pragma SPARK_Mode (On);` form
        # (a structurally different shape from the `with SPARK_Mode`
        # aspect form -- both are real and common). Must NOT overlap the
        # plain `with` import clause below -- distinguished by a fixed,
        # known aspect-mark vocabulary rather than by punctuation, since
        # several boolean aspects (Inline, Pure, ...) have no `=>` at
        # all and would otherwise be lexically identical to a bare
        # package-name import list. Keep this list in sync with
        # import/_dependency_capture's exclusion lookahead below.
        "decorators": re.compile(
            r"\bwith[ \t]+(?:Pre|Post|Invariant|Static_Predicate|Dynamic_Predicate|Global|Depends"
            r"|Convention|Import|Export|Inline|Volatile|Atomic|Pack|SPARK_Mode|No_Return"
            r"|Pure|Preelaborate|Elaborate_Body"
            r"|Abstract_State|Initializes|Refined_Global|Refined_Post|Refined_State|Refined_Depends)\b"
            r"|\bpragma[ \t]+SPARK_Mode\b",
            re.I,
        ),
        # generics: `generic` keyword, and instantiation scoped to
        # `package|procedure|function NAME is new ...` specifically --
        # NOT bare "is new" alone, which would collide with
        # class_start's tagged-type derivation (`type Dog is new Animal
        # with ...`), a genuinely different construct sharing the same
        # two words.
        "generics": re.compile(
            r"\bgeneric\b|\b(?:package|procedure|function)\b[ \t]+[A-Za-z_][A-Za-z0-9_]*[ \t\n]+is[ \t\n]+new\b",
            re.I,
        ),
        # comprehensions: Ada 2012 quantified expressions (`for all` /
        # `for some`), the closest analogue to an inline iterator/
        # comprehension.
        "comprehensions": re.compile(r"\bfor[ \t]+(?:all|some)\b", re.I),
        # scientific: Ada.Numerics and its generic elementary-functions
        # children.
        "scientific": re.compile(r"\bAda\.Numerics\b", re.I),
        # reflection_metaprogramming: tagged-type dispatch/RTTI --
        # 'Class and 'Tag attributes, Ada.Tags.
        "reflection_metaprogramming": re.compile(r"'Class\b|'Tag\b|\bAda\.Tags\b", re.I),
        # import: context-clause `with` (compilation-unit dependency),
        # explicitly excluding the same known aspect-mark vocabulary
        # decorators uses above so a `with Pre => ...` aspect clause on
        # a declaration is never miscounted as a dependency.
        "import": re.compile(
            r"^[ \t]*with[ \t\n]+(?!(?:Pre|Post|Invariant|Static_Predicate|Dynamic_Predicate|Global|Depends"
            r"|Convention|Import|Export|Inline|Volatile|Atomic|Pack|SPARK_Mode|No_Return"
            r"|Pure|Preelaborate|Elaborate_Body"
            r"|Abstract_State|Initializes|Refined_Global|Refined_Post|Refined_State|Refined_Depends)\b)"
            r"[A-Za-z_][A-Za-z0-9_.]*(?:[ \t\n]*,[ \t\n]*[A-Za-z_][A-Za-z0-9_.]*){0,20}[ \t\n]*;",
            re.I | re.M,
        ),
        "_dependency_capture": re.compile(
            r"^[ \t]*with[ \t\n]+(?!(?:Pre|Post|Invariant|Static_Predicate|Dynamic_Predicate|Global|Depends"
            r"|Convention|Import|Export|Inline|Volatile|Atomic|Pack|SPARK_Mode|No_Return"
            r"|Pure|Preelaborate|Elaborate_Body"
            r"|Abstract_State|Initializes|Refined_Global|Refined_Post|Refined_State|Refined_Depends)\b)"
            r"([A-Za-z_][A-Za-z0-9_.]*)",
            re.I | re.M,
        ),
        # ownership: header comment convention, same shape as the JCL/
        # COBOL entries.
        "ownership": re.compile(r"^[ \t]*--[ \t]*(?:Author|Created by|Maintainer)[ \t]*:[ \t]*(.*)$", re.I | re.M),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # hardcoded_secrets: assigned Ada string-literal declarations
        # for common secret-shaped identifiers.
        "hardcoded_secrets": re.compile(
            r"\b(?:password|secret|token|api[_-]?key|private[_-]?key|client[_-]?secret)\b"
            r"[ \t]*:[ \t]*(?:constant[ \t]+)?[A-Za-z_][A-Za-z0-9_.]*[ \t]*:=[ \t]*\"[^\"]{8,}\"",
            re.I,
        ),
        "spec_exposure": re.compile(r"\[(?:SPEC[ \t]*-[ \t]*\d{1,6}|spec|audit)\]", re.I),
        # ssr_boundaries: no idiomatic Ada web-application framework
        # (Strict Feature Parity, Rule 4).
        "ssr_boundaries": None,
        # events: a task/protected object *accepting* an entry call --
        # the moment a message/event is actually handled. Intentionally
        # overlaps concurrency's broader domain signal above.
        "events": re.compile(r"\baccept\b", re.I),
        # dependency_injection: no idiomatic IoC/DI framework or
        # convention in Ada (generics already cover its real compile-
        # time parameterization mechanism).
        "dependency_injection": None,
        # macros: gnatprep, GNAT's optional conditional-compilation
        # preprocessor (`#if` / `#elsif` / `#else` / `#end if;`) --
        # real and commonly used in embedded/avionics Ada for
        # per-target-hardware conditional builds.
        "macros": re.compile(r"^[ \t]*#[ \t]*(?:if|elsif|else|end[ \t]+if)\b", re.I | re.M),
        # pointers: Ada access types -- declarations, `access all`/
        # `access constant`, and the 'Access/'Unchecked_Access
        # attributes.
        "pointers": re.compile(
            r"\bis[ \t]+access\b|\baccess[ \t]+all\b|\baccess[ \t]+constant\b"
            r"|'Access\b|'Unchecked_Access\b",
            re.I,
        ),
        # memory_alloc: the `new` allocator.
        "memory_alloc": re.compile(r"\bnew[ \t]+[A-Za-z_]", re.I),
        # inline_asm: System.Machine_Code's Asm construct -- a real,
        # if niche, GNAT-standard extension used in kernel/embedded Ada.
        "inline_asm": re.compile(r"\bSystem\.Machine_Code\b|\bAsm[ \t]*\(", re.I),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # telemetry: GNATCOLL.Traces, the de facto AdaCore-ecosystem
        # tracing/logging library.
        "telemetry": re.compile(r"\bGNATCOLL\.Traces\b", re.I),
        # debug_prints: Ada.Text_IO's Put_Line/Put/New_Line -- the
        # stdout-print idiom, distinct from io's file/network calls
        # above.
        "debug_prints": re.compile(r"\bPut_Line\b|\bPut[ \t]*\(|\bNew_Line\b", re.I),
        # explicit_casts: Ada qualified-expression syntax
        # `Type_Name'(Expr)` -- a real, lexically-unambiguous marker for
        # explicit type conversion/qualification (unlike a bare type
        # conversion `T(Expr)`, which is syntactically identical to a
        # function call and can't be told apart without semantic info).
        "explicit_casts": re.compile(r"\b[A-Za-z_][A-Za-z0-9_.]*'\(", re.I),
        # panics_and_aborts: `raise` (exception propagation) and
        # `abort` (forceful task termination -- the schema's own
        # baseline definition lists "abort()" as a canonical example).
        "panics_and_aborts": re.compile(r"\braise\b|\babort\b", re.I),
        # thread_sleeps: the `delay` statement.
        "thread_sleeps": re.compile(r"\bdelay\b", re.I),
        # bitwise_ops: Interfaces' Shift_Left/Shift_Right/Rotate_Left/
        # Rotate_Right, and `xor` (unlike bare `and`/`or`, `xor` has no
        # short-circuit "and then"/"or else"-style logical variant in
        # Ada, so it's unambiguously the bitwise/boolean-parity
        # operator, not a branch-control keyword).
        "bitwise_ops": re.compile(r"\bShift_Left\b|\bShift_Right\b|\bRotate_Left\b|\bRotate_Right\b|\bxor\b", re.I),
        # sync_locks: protected objects/types are Ada's built-in
        # monitor/mutex primitive. Intentionally overlaps concurrency.
        "sync_locks": re.compile(r"\bprotected\b|\bSuspension_Object\b", re.I),
        # immutability_locks: the `constant` keyword.
        "immutability_locks": re.compile(r"\bconstant\b", re.I),
        # cleanup: Ada.Unchecked_Deallocation (the generic instantiated
        # to build a "Free" procedure) and Ada.Finalization/Finalize
        # (RAII-style teardown). Deliberately NOT paired with
        # Unchecked_Conversion in safety_bypasses above -- this mirrors
        # C's free()/dispose(), a normal cleanup action, not a type-
        # safety bypass.
        "cleanup": re.compile(r"\bAda\.Unchecked_Deallocation\b|\bFinalize\b|\bAda\.Finalization\b", re.I),
        # encapsulation: the `private` keyword (package private parts,
        # private type declarations).
        "encapsulation": re.compile(r"\bprivate\b", re.I),
        # listeners: a task entry declaration -- the endpoint waiting to
        # receive an external call, before it's actually accepted
        # (events, above).
        "listeners": re.compile(r"\bentry\b", re.I),
        # test_skip: no native language/AUnit-standard skip primitive;
        # falls back to a comment-marker convention.
        "test_skip": re.compile(r"--[ \t]*(?:SKIP|SKIPPED|DISABLED)\b", re.I),
        # --- HYBRID DOMAIN SENSORS ---
        # serialization_parsing: GNATCOLL.JSON and XML/Ada (DOM/SAX).
        "serialization_parsing": re.compile(r"\bGNATCOLL\.JSON\b|\bDOM\.Core\b|\bInput_Sources\b", re.I),
        # regex_execution: GNAT.Regpat / GNAT.Regexp, GNAT's native
        # regex engines.
        "regex_execution": re.compile(r"\bGNAT\.Regpat\b|\bGNAT\.Regexp\b", re.I),
        # time_date_logic: Ada.Calendar / Ada.Real_Time.
        "time_date_logic": re.compile(r"\bAda\.Calendar\b|\bAda\.Real_Time\b|\bClock\b", re.I),
        # ipc_rpc_bridges: the Distributed Systems Annex (Annex E)
        # pragmas and PolyORB (Ada's CORBA-like ORB), used in real
        # distributed defense/aerospace Ada systems.
        "ipc_rpc_bridges": re.compile(
            r"\bpragma[ \t]+Remote_Call_Interface\b|\bpragma[ \t]+Remote_Types\b"
            r"|\bpragma[ \t]+Shared_Passive\b|\bPolyORB\b",
            re.I,
        ),
    },
}
