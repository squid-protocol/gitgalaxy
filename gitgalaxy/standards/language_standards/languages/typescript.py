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

from .._shared_patterns import (
    GLOBAL_DL_FRAMEWORKS,
    GLOBAL_FRAGILE_DEBT,
    GLOBAL_LLM_API,
    GLOBAL_LLM_ORCHESTRATOR,
    GLOBAL_LLM_VECTOR_STORE,
    GLOBAL_ML_TRADITIONAL,
    GLOBAL_PLANNED_DEBT,
)

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "TypeScript 6.0 / ES2026",
        "last_updated": "2026-03-12",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, JSX variants, and ambient declaration boundaries.
    "extensions": [
        ".ts",
        ".tsx",
        ".mts",
        ".cts",
        ".d.ts",
        ".d.mts",
        ".d.cts",  # Ambient declarations
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
    "discriminators": [
        ".ts",
        "tsconfig.json",
        "tslint.json",
        "package.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "deno.json",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["ts-node", "deno", "bun", "tsx"],
    # UPGRADED: Maps to Family 1 (Standard C)
    # Rationale: Uses '//' for line-level literature; multi-line literature
    # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # EXCLUDES: Exceptions (throw). Includes control flow and logical short-circuits.
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|while|do|catch|finally|continue|break|try)\b|&&|\|\||\?|\?\?"
        ),
        # 2. args (Parameters / Coupling)
        # CRITICAL FIX: Added negative lookahead for control flow, and `[^=;{]*` to support TypeScript return types.
        # QUADRATIC BLOWUP FIX: the bare-identifier-before-arrow branch's
        # `[\w$]*` was unbounded. On a long line with no `=>` at all, the
        # engine retried the greedy-then-backtrack identifier match at
        # every starting position -- O(n^2) (same bug found and fixed in
        # javascript's near-identical args rule). Bounded to {0,100};
        # real identifiers never get remotely that long.
        # #1209: parameter-list span wrapped in its own capture group in
        # all four branches (was only reachable via group(0), the whole
        # match including the "function"/modifier/name prefix, or for
        # arrow functions nothing at all) so detector.py's counter
        # isolates just the real parameter text -- the whole-match
        # fallback overcounted every zero/one-arg signature by +1 the
        # same way Python's did (#1199). Name groups added to branches
        # 1/4 too, purely so existing extraction tests keep passing.
        "args": re.compile(
            r"function\s+(\w*)(?:[ \t\n]{0,50}<(?:[^<>]|<[^<>]*>)*>)?[ \t\n]{0,50}(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))|"
            r"(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))[^=;{]*=>|"
            r"([a-zA-Z_$][\w$]{0,100})[ \t]*=>|"
            r"^[ \t]*(?:(?:public|private|protected|static|override|abstract|readonly)[ \t]+){0,4}(?:async[ \t]+)?(?:\*[ \t]*)?(?:get\s+|set[ \t]+)?(?!(?:if|for|while|switch|catch|return|throw|new|typeof|yield|await|void)\b)(\[[^\]]+\]|[#]?[a-zA-Z_$][\w$]*)(?:[ \t\n]{0,50}<(?:[^<>]|<[^<>]*>)*>)?[ \t\n]{0,50}(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (public/private) and Immutability (const).
        "structural_boundaries": re.compile(
            r"\b(var|return|class|interface|type|enum|import|export|await|satisfies|using|namespace|module|implements|extends|declare)\b|=>"
        ),
        # 4. func_start (Executable Logic Anchors)
        # Captures standard functions, assignments, object properties, and class methods.
        # Safely steps over TypeScript Generics <T> and explicit return types in the lookaheads.
        # BUG FIX (severe ReDoS, ~4x/doubling confirmed via scaling sweep,
        # ~1.9s at n=32000): the trailing lookahead `\s*(?:<[^>]*>)?\s*\(`
        # (shared by the `function` branch and the class-member branch)
        # has two adjacent unbounded `\s*` quantifiers separated by an
        # optional group -- on a long run of pure whitespace with no `(`
        # ever appearing (e.g. a truncated/malformed source file), the
        # engine can partition that whitespace between the two `\s*`
        # instances in exponentially many ways before failing. Bounded
        # both to `[ \t\n]{0,50}` (generous for real code). Also fixed a
        # separate, unrelated pre-existing gap found while in here: the
        # `function` branch's `\s*\*?\s+` required a whitespace char
        # *after* the generator `*` even when one preceded it instead
        # (`function *gen()`, less common than `function* gen()` but
        # valid), and rejected the zero-space `function*gen()` form
        # entirely. Replaced with `[ \t\n*]+` (one or more of
        # whitespace-or-star), which still requires *some* separator so
        # it can't false-positive-match an unrelated identifier like
        # `functionFoo()`.
        # BUG FIX (Rule 11, nested-delimiter coverage -- this is the
        # issue's own flagged "func_start vs generics" known ambiguity
        # pattern, already found in C#): the flat `[^>]*` generic
        # step-over broke on even one level of nested angle brackets in
        # a generic constraint (`function foo<T extends Array<number>>`),
        # a common realistic TypeScript pattern -- func_start silently
        # failed to match the WHOLE function, not just the generic part.
        # Widened to tolerate one level of self-nesting (non-overlapping
        # alternatives, so no new ReDoS risk per the doc's own Rule 11
        # example).
        # BUG FIX (epic #813/#815): the assignment-style alternative
        # (2nd branch below) has no way to distinguish a real arrow-
        # function assignment (`const Foo = (a: T): T => a;`) from a
        # function-shaped TYPE ALIAS (`type Foo = (a: T) => R;`) --
        # both share the identical `IDENT = (...) => ...` surface shape.
        # A type alias only *describes* a function signature; it isn't
        # one. Fixed with a fixed-width negative lookbehind for the
        # single-space `type ` prefix (Python's `re` doesn't support
        # variable-width lookbehind, and real-world/formatter-produced
        # TypeScript uses exactly one space here in the overwhelming
        # majority of cases -- same "practical reality over perfect
        # accuracy" tradeoff used throughout this file).
        # BUG FIX (epic #813/#815): the same alternative also required
        # the identifier to be followed *directly* by `=`, missing the
        "func_start": re.compile(
            r"(?:"
            # =====================================================================
            # [ THE FLOATING GENERIC SHIELD ] (Hard-learned lesson from Pathological Fuzzer)
            # PURPOSE: In TypeScript, a function name and its generic type `<T>`
            # can be separated by a vertical newline (e.g., `function TargetFunc \n <T>`).
            # THE FIX: Injected `\s*` immediately before the generic step-over `(?:<[^>]*>)?`
            # across all branches. This explicitly permits vertical spacing between
            # the isolated function name and the generic parameters.
            # Note: We also migrated the JS Vertical Assignment fixes here (`[ \t\n]*`).
            # =====================================================================
            r"\b(?:async\s+)?function[ \t\n*]+(\[[^\]]+\]|[a-zA-Z_$][\w$]*)(?=[ \t\n]{0,50}(?:<(?:[^<>]|<[^<>]*>)*>)?[ \t\n]{0,50}\()|"
            # BUG FIX (issue #1838, P2): a constructor parameter property
            # (`constructor(private readonly interval: number, private
            # readonly nowFn = () => Date.now())`) puts an
            # `IDENT = arrow` default-value shape INSIDE the enclosing,
            # still-open parameter list -- textually indistinguishable
            # from a real top-level/class-field `IDENT = arrow`
            # assignment without paren-depth tracking, which this
            # single-pass regex doesn't have. `public`/`private`/
            # `protected`/`readonly` immediately after `,` or `(` is
            # UNIQUE to this TS parameter-property syntax though: no
            # other valid TypeScript construct puts one of those four
            # contextual keywords directly after a bare `,` or `(`
            # (they're otherwise only legal as class-member modifiers,
            # which are never comma/paren-adjacent). Python's `re`
            # requires fixed-width lookbehind, so this enumerates the
            # 7 valid modifier/modifier-pair combinations x 2 preceding
            # delimiters as 14 separate fixed-width negative lookbehinds
            # (each individually fixed-width; stdlib `re` rejects a
            # single lookbehind with internally-variable-length
            # alternation) rather than one general "are we inside an
            # unclosed paren" check.
            r"(?:^|(?<=[^<>(,\s]))[ \t\n]*(?<!\.\.\.)\b(?<!type )"
            r"(?<!,\spublic\s)(?<!,\sprivate\s)(?<!,\sprotected\s)(?<!,\sreadonly\s)"
            r"(?<!,\spublic\sreadonly\s)(?<!,\sprivate\sreadonly\s)(?<!,\sprotected\sreadonly\s)"
            r"(?<!\(public\s)(?<!\(private\s)(?<!\(protected\s)(?<!\(readonly\s)"
            r"(?<!\(public\sreadonly\s)(?<!\(private\sreadonly\s)(?<!\(protected\sreadonly\s)"
            r"(\[[^\]]+\]|[a-zA-Z_$][\w$]*)(?:[ \t\n]*:[ \t\n]{0,50}(?:(?!\b(?:const|let|var|return|export|import|class|private|public|protected|readonly)\b)[^=;{}]|=>){0,200})?"
            # BUG FIX (issue #1838, R2): the arrow-body terminator only
            # accepted a body starting with `{`/`<`/`(`/end-of-line --
            # missed the common point-free/FP-style shape where the body
            # is a bare call or bare identifier reference (`=>
            # pipe(fab, ap(fa))`, `=> scheduled`, `=> this.foo()`).
            # Widened with two more alternatives: an identifier
            # immediately followed by `(` (an unambiguous call shape --
            # types never call anything, so this can't collide with a
            # function-TYPE signature's return type), and a bare
            # lowercase-leading identifier. The bare-identifier
            # alternative is deliberately restricted to `[a-z_]` (never
            # `[A-Z]`) since real custom TypeScript type names are
            # conventionally PascalCase by community/compiler-team
            # convention -- but TS's own BUILT-IN primitive/utility type
            # keywords (`void`, `string`, `number`, ...) are lowercase
            # too, so a member-signature's return type (`c: (x: T) =>
            # void;`) would otherwise false-positive as if `void` were a
            # real function value. Blacklisted the closed, small set of
            # TS primitive/utility type keywords to close that gap
            # without losing the general lowercase-identifier case.
            #
            # BUG FIX (issue #1840): the gap between a param-list's
            # closing `)` and the eventual `=>` (`[^=;{]*`) was unbounded
            # in WHAT it could contain, only in how much of it -- so it
            # happily skipped straight over an entirely unrelated,
            # already-closed method-chain call sitting between the two,
            # landing on a LATER arrow that has nothing to do with the
            # assigned identifier. Real example: `const deps = (await
            # Promise.all([...])).flatMap(o => o);` -- the outer
            # `(await Promise.all([...]))` is a real, fully-closed
            # parenthesized expression (not `deps`'s own parameter
            # list), but `[^=;{]*` cheerfully consumed `.flatMap(o `
            # -- including its OWN unrelated open paren -- to reach the
            # `flatMap` callback's `=>`, false-matching `deps` as if it
            # were an arrow function. A real arrow's param-list-to-`=>`
            # gap is just an optional return-type annotation, which
            # never legitimately contains a bare, unbalanced `(` or `)`
            # of its own -- excluding both from the gap (`[^=;{()]*`)
            # closes this without narrowing any genuine case (return
            # types use `<...>` for generics, not `(...)`).
            # BUG FIX (issue #2231): the body-start alternation had no
            # allowance for a bare unary `!` (`const predicate = (e: T) =>
            # !e.newDocument;`), a common negation-shorthand arrow body --
            # rejected outright since `!` isn't `{`/`<`/`(`/end-of-line nor
            # an identifier. Added as its own literal alternative: `!` can
            # never start a return-type annotation, so this can't collide
            # with the function-TYPE-signature case the rest of this
            # alternation is busy disambiguating against.
            # #2464: in the `IDENT = arrow` (assignment) shape, the arrow's
            # body is always a VALUE, never a type annotation -- so `undefined`
            # / `null` (both legal bare-value bodies, `x = () => null`, common
            # in conditional-reassignment blocks) are NOT blacklisted here,
            # unlike the `:`-annotated branch below where they can be a real
            # member-signature return type. The type keywords (`void`,
            # `string`, ...) stay excluded: they are never valid bare arrow
            # bodies in JS/TS in either context.
            r"(?=[ \t\n]*=[ \t\n]*(?:async\s*)?(?:<(?:[^<>]|<[^<>]*>)*>\s*)?(?:function(?:\s*\*)?\b|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)(?:[^=;{()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*=>[ \t\n]*(?:[{<]|\(|!|$|[a-zA-Z_$][\w$]*(?=[ \t\n]*\()|(?!(?:void|string|number|boolean|any|unknown|never|object|symbol|bigint)\b)[a-z_][\w$]*)|[a-zA-Z_$][\w$]*[ \t\n]*=>[ \t\n]*(?:[{<]|\(|!|$|[a-zA-Z_$][\w$]*(?=[ \t\n]*\()|(?!(?:void|string|number|boolean|any|unknown|never|object|symbol|bigint)\b)[a-z_][\w$]*)))|"
            r"(?:^[ \t]*|(?<=[,{])[ \t\n]*)(\[[^\]]+\]|[#]?[a-zA-Z_$][\w$]*)(?=[ \t\n]*:[ \t\n]*(?:async\s*)?(?:<(?:[^<>]|<[^<>]*>)*>\s*)?(?:function(?:\s*\*)?\b|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)(?:[^=;{()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*=>[ \t\n]*(?:[{<]|\(|!|$|[a-zA-Z_$][\w$]*(?=[ \t\n]*\()|(?!(?:void|string|number|boolean|any|unknown|never|object|symbol|bigint|undefined|null)\b)[a-z_][\w$]*)|[a-zA-Z_$][\w$]*[ \t\n]*=>[ \t\n]*(?:[{<]|\(|!|$|[a-zA-Z_$][\w$]*(?=[ \t\n]*\()|(?!(?:void|string|number|boolean|any|unknown|never|object|symbol|bigint|undefined|null)\b)[a-z_][\w$]*)))|"
            # #1221: the trailing lookahead used to be just
            # `(?=[ \t\n]{0,50}(?:<...>)?[ \t\n]{0,50}\()` -- proof a
            # `(` follows, nothing more -- so any bare call statement
            # starting a line (`next();`) false-positive-matched as a
            # method definition, mirroring the identical javascript gap
            # (see that file's own #1221 fix comment for the full
            # writeup). A real call statement never carries a modifier
            # (public/private/.../readonly), `async`, a generator `*`,
            # or a `get`/`set` accessor keyword -- only a real
            # signature can -- so this now splits into two mutually
            # exclusive alternatives, mirroring java's/dart's/groovy's
            # own #1221 fixes: (A) at least one of those prefix tokens
            # is present -- keeps the ORIGINAL lenient bare-`(`
            # lookahead unchanged (still needed: a legacy monolithic
            # gauntlet, tests/extraction/test_function_extraction.py,
            # has truncated-signature payloads like `public get
            # TargetFunc()` that never reach a real terminator at all,
            # the same leniency csharp/apex/groovy/dart's own
            # zero-prefix branches still need); (B) no prefix token at
            # all -- must fully close its (non-nested, same bound as
            # `args`) parameter list and reach either an optional `:
            # ReturnType` then an optional `=>` (kept only to preserve
            # the ALREADY-documented, deliberately-NOT-fixed
            # `describe('x', () => {` known-limitation ambiguity --
            # see the test right below) then `{`, or a MANDATORY `:
            # ReturnType` then `;` (interface/abstract method stubs,
            # `TargetFunc(): void;`) -- `next();` has neither a prefix
            # nor a reachable terminator, so it satisfies neither
            # branch. A stub with NO explicit return type (`bar();` in
            # an interface, valid but rarer/atypical TS style) is a
            # known, accepted gap of this same trade-off --
            # indistinguishable from `next();` without scope-awareness
            # this engine doesn't have.
            # NOT FIXED (issue #1838, P1 -- ruled out, left as-is on
            # purpose): `protected abstract createReferencedObject(...): T;`
            # has no implementation by TypeScript's own grammar (abstract
            # methods can never carry a body), and tree-sitter itself
            # parses it as a distinct `abstract_method_signature` node --
            # not `method_definition`/`method_signature` -- so the
            # tree-sitter-accuracy audit never counts it as ground truth,
            # making this branch's match look like a false positive there.
            # An earlier attempt excluded `abstract`-prefixed signatures
            # from this branch entirely to chase that number, but
            # `tests/extraction/languages/test_typescript.py`'s own
            # `func_start` gauntlet has an explicit, intentional valid
            # case for exactly this shape (`abstract TargetFunc(): void;`
            # inside `abstract class Foo`) -- GitGalaxy's structural-
            # signature counting is deliberately broader than tree-sitter's
            # AST node taxonomy here (an abstract method declaration is
            # still a real structural unit worth a branch/io/complexity
            # signal, even with no body of its own), and the gauntlet is
            # this file's authoritative correctness spec, not the
            # tree-sitter diff. Fixing "for tree-sitter" would have broken
            # a real, already-agreed-on test. Left unmatched-by-design;
            # the audit's own extra_functions number for this case is a
            # known, accepted tool-methodology mismatch, not a GitGalaxy bug.
            # BUG FIX (Rule 14, ReDoS -- confirmed ~O(n^2), 4.1s at
            # n=16000 pure trailing-whitespace payload): branch B's two
            # `[ \t\n]*` after `\)` and after the optional `:Type`
            # annotation are adjacent unbounded quantifiers separated
            # only by an optional group that can match zero-width (the
            # exact Rule 14 shape this file's own comment elsewhere
            # warns about), so a payload with a huge trailing
            # whitespace run and no real terminator lets the engine
            # partition it between the two quantifiers in O(n^2) ways
            # before failing. Bounded both (and the `=>`-tolerance
            # group's own trailing run) to `{0,50}`, matching this
            # same regex's existing bound for the generic-skip
            # whitespace immediately to their left.
            r"^[ \t]*(?:"
            r"(?:(?:public|private|protected|static|override|abstract|readonly)[ \t\n]+){1,4}(?:async[ \t\n]+)?(?:\*[ \t\n]*)?(?:get\s+|set\s+)?"
            r"|"
            r"(?:(?:public|private|protected|static|override|abstract|readonly)[ \t\n]+){0,4}async[ \t\n]+(?:\*[ \t\n]*)?(?:get\s+|set\s+)?"
            r"|"
            r"(?:(?:public|private|protected|static|override|abstract|readonly)[ \t\n]+){0,4}(?:async[ \t\n]+)?\*[ \t\n]*(?:get\s+|set\s+)?"
            r"|"
            r"(?:(?:public|private|protected|static|override|abstract|readonly)[ \t\n]+){0,4}(?:async[ \t\n]+)?(?:\*[ \t\n]*)?(?:get\s+|set\s+)"
            r")"
            # BUG FIX (issue #2232): no allowance for TypeScript's optional-
            # member `?` (`copy?(source: Uri): void;`) between the name and
            # the parameter list -- `\??` inserted as the very first token
            # of the lookahead, directly against the name capture with zero
            # whitespace tolerance before it, so it only fires for the real
            # zero-space `name?(` adjacency the syntax requires (a spaced
            # ternary like `isEnabled ? (a + b)` can't satisfy it: the `?`
            # isn't immediately adjacent to the name, so `\??` matches
            # zero-width here and the mandatory `\(` lookahead then fails
            # against the literal `?` still sitting in the way).
            # BUG FIX (issue #2276): `catch`/`return`/`throw` used to be
            # unconditionally excluded here to stop `} catch (e) {`
            # control-flow blocks (and ordinary `return`/`throw`
            # statements) from being misidentified as method
            # definitions -- but that also permanently hid a REAL method
            # or property legitimately named `catch`/`return`/`throw`
            # (a Promise-like thenable's `catch<T>()`, an AsyncIterator
            # protocol's `return()`). Moved to a CONDITIONAL exclusion:
            # only excluded when immediately followed by whitespace then
            # `(`/`<` -- idiomatic control-flow/statement syntax always
            # has that shape (`catch (e)`, `return <expr`), while a real
            # method/property definition never does (`catch<T>(...)`,
            # `catch(...)`, `return: () => {...}`). Confirmed via direct
            # testing that `} catch (e) {` still correctly does NOT
            # match, while `catch<TResult = never>(...)` and
            # `return: () => {...}` now do.
            r"(?!(?:class|interface|enum|if|for|while|switch|new|typeof|jQuery|function|yield|await|void)\b|type\b(?![ \t\n]*\()|\$|(?:catch|return|throw)\b[ \t\n]+(?:\(|<))(\[[^\]]+\]|[#]?[a-zA-Z_$][\w$]*)(?=\??[ \t\n]{0,50}(?:<(?:[^<>]|<[^<>]*>)*>)?[ \t\n]{0,50}\()"
            r"|"
            # BUG FIX (R3): The arrow-value (Branch 5 / standalone value) branch
            # is known to fail on mid-statement function values (e.g. `const a = b || () => {}`)
            # because the `^[ \t]*` anchor enforces it must be the start of a line. We cannot
            # easily fix this without massive ReDoS or losing precision.
            # Mid-statement function values cannot be reliably matched without a full AST.
            # BUG FIX (epic #1261 / issue #1630): the zero-prefix branch's
            # parameter-list terminator used a FLAT `\([^)]*\)` character class,
            # which cannot represent even one level of nested parens. Any
            # callback-typed parameter (`onDisconnect: () => void`, `handler:
            # (...args: any[]) => void`) has an inner `()`, so the class stopped
            # at the first inner `)`, the terminator lookahead then failed to find
            # its `{`/`;`/`:` anchor, and the WHOLE signature -- constructor or
            # method -- silently stopped matching (regex-level non-match, not just a
            # misrecord). Replaced with the bounded one-level-nesting form
            # `\((?:[^()]|\([^()]*\))*\)` -- same Rule 11 shape the generic
            # step-over already uses (`(?:[^<>]|<[^<>]*>)*`), linear because the
            # two alternatives never match overlapping text.
            # BUG FIX (issue #1838, R1): one level of nesting still wasn't
            # enough -- a callback-typed parameter can itself contain a
            # parenthesized sub-expression (nesting depth 2 from the outer
            # list-paren), e.g. `appendPlaceholder(value: string | ((snippet:
            # SnippetString) => any), number?: number): SnippetString;`
            # (`vscode/vscode.d.ts:4180`). Recursed the same non-overlapping
            # idiom one level deeper: `\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)`.
            # Still linear (each level's alternatives don't overlap the level
            # above it), same Rule 11 reasoning, just applied twice.
            #
            # NOTE: an earlier version of this fix ALSO added a `constructor`-
            # specific bare-`;` terminator alternative here, on the theory that
            # bodyless ambient/overload constructors (`constructor(...);` with
            # no return-type annotation) were a real recall gap. That was
            # wrong: `tests/tools/tree_sitter_accuracy_audit.py`'s own ground
            # truth (search "Intentional drop of bodyless constructors")
            # deliberately excludes exactly this node shape (`method_signature`/
            # `function_signature` named "constructor") from what counts as a
            # real function -- so matching it only manufactured new false
            # positives across every `.d.ts`-style declaration file in the
            # corpus (confirmed: reverting this addition alone dropped
            # `extra_functions` by dozens on the pinned corpus). Left
            # unmatched, on purpose -- see issue #1838's discussion for the
            # full trace.
            # BUG FIX (issue #2232): same `\??` insertion as Branch A above
            # -- this zero-prefix branch is exactly where GitGalaxy misses
            # `.d.ts`-style optional interface method signatures like
            # `copy?(source: Uri): void;`, since interface members carry no
            # public/private/etc. modifier to route them through Branch A
            # instead. Same zero-whitespace-before-`?` placement, same
            # ternary-collision reasoning.
            # BUG FIX (issue #2279): Split the zero-prefix branch to safely
            # allow bodyless constructors. If we make the return type
            # optional for ALL identifiers here, it falsely matches bare
            # function calls (like `next();`) because they also end in
            # `;`. By strictly requiring `constructor` for the
            # optional-return-type case, we match ambient
            # `constructor(x: number);` without breaking function calls.
            r"(?:^[ \t]*|(?<=[,{])[ \t\n]*)(\bconstructor\b)(?=\??[ \t\n]{0,50}(?:<(?:[^<>]|<[^<>]*>)*>)?[ \t\n]{0,50}\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)[ \t\n]{0,50}(?:(?::[^{;]{0,200})?[ \t\n]{0,50}(?:=>[ \t\n]{0,50})?\{|[ \t\n]{0,50};))"
            r"|"
            # BUG FIX (issue #2276): same conditional-exclusion fix as
            # Branch A above, mirrored here since this branch carries
            # its own copy of the same reserved-keyword shield -- see
            # that branch's comment for the full rationale. Combined
            # with #2277's widened anchor and #2279's `constructor`
            # split (above) during merge conflicts between all three --
            # every change applies to the same branch, independently of
            # the others, so `constructor` is added to this branch's own
            # exclusion list (it's handled by its own alternative above)
            # alongside the catch/return/throw conditional exclusion.
            # #2464: the generic step-over here is `=>`-tolerant (`=>` and a
            # lone `=` are explicit tokens, `>` closes only when not part of
            # `=>`) so a bodyless overload signature whose type-parameter list
            # itself contains a function type -- `createInstance<Ctor extends
            # new (...args: any[]) => unknown, R extends InstanceType<Ctor>>
            # (...): R;` (vscode/instantiationService.ts:117) -- is matched
            # rather than truncated at the `>` of `=>`. Alternatives stay
            # mutually exclusive on their first char (`=>` vs `=(?!>)` vs
            # `[^<>=]` vs `<`), so still linear (Rule 11). The mandatory
            # `:Type;` / `{` terminator below keeps a bare generic call
            # statement (`useCallback<() => void>(cb);`) from matching.
            r"(?:^[ \t]*|(?<=[,{])[ \t\n]*)(?!(?:class|interface|enum|if|for|while|switch|new|typeof|jQuery|function|yield|await|void|constructor)\b|type\b(?![ \t\n]*\()|\$|(?:catch|return|throw)\b[ \t\n]+(?:\(|<))(\[[^\]]+\]|[#]?[a-zA-Z_$][\w$]*)(?=\??[ \t\n]{0,50}(?:<(?:=>|=(?!>)|[^<>=]|<(?:=>|=(?!>)|[^<>=])*>)*>)?[ \t\n]{0,50}\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)[ \t\n]{0,50}(?:(?::[^{;]{0,200})?[ \t\n]{0,50}(?:=>[ \t\n]{0,50})?\{|:[^{;]{0,200}[ \t\n]{0,50};))"
            r")",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # =====================================================================
        # [ THE VERTICAL MODIFIER SHIELD (TYPESCRIPT) ]
        # TypeScript allows modifiers like `export`, `default`, and `abstract`
        # to appear in various orders and across multiple lines.
        # FIX: Grouped the modifiers into a flexible, bounded set `(?:(?:export|default|abstract|declare)[ \t\n]+){0,4}`.
        # Upgraded all internal spaces to `[ \t\n]+` to seamlessly leap over vertical gaps.
        # =====================================================================
        # BUG FIX: the extends/implements capture required whitespace
        # immediately after the class-name capture, but a generic class
        # declaration (`class Foo<T> extends Bar<T>`) has `<T>` there
        # instead -- the optional extends/implements group silently never
        # fired for any generic class, a very common TypeScript pattern.
        # Added an optional `<...>` step-over between the name and the
        # extends/implements check.
        # BUG FIX (Rule 11, epic #813/#815): that step-over was flat
        # (`<[^>]*>`), which truncates at the FIRST `>` -- a one-level-
        # nested generic bound (`class Foo<T extends Comparable<T>>
        # extends Bar {`, a common realistic pattern) left a stray `>`
        # unconsumed right before the real `extends` clause, silently
        # losing the entire extends/implements capture (group 2) even
        # though the class NAME itself still matched fine. Widened to
        # the established one-level-nesting idiom used elsewhere in
        # this file.
        # BUG FIX (#1348): the modifier group was missing `const`, so
        # TypeScript's compile-time-only `const enum Foo {` / `export
        # const enum Foo {` form (common in vscode/assemblyscript/the
        # typescript compiler itself) never matched at all -- `const`
        # isn't a recognized modifier and isn't the mandatory
        # `class|enum|interface` keyword either, so the whole rule
        # failed to fire. Adding `const` here can't introduce new false
        # matches on unrelated `const x = ...` statements: the entity
        # keyword is still mandatory immediately after the modifier
        # run, so a plain `const` declaration (no literal `class`/
        # `enum`/`interface` token following) still doesn't match.
        "class_start": re.compile(
            r"^[ \t]*(?:(?:export|default|abstract|declare|const)[ \t\n]+){0,4}(?:class|enum|interface)[ \t\n]+([a-zA-Z_$][\w$]*)(?:[ \t\n]*<(?:[^<>]|<[^<>]*>)*>)?(?:[ \t\n]+(?:extends|implements)[ \t\n]+([a-zA-Z_$][\w_$, \t\n]*))?",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(try|catch|finally|satisfies|unknown|never|void|Object\.freeze|z\.(?:string|object|parse)|v\.(?:string|parse))\b|\?\?|\?\.|\b(?:is|asserts)\s+\w+\b"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Force unwrapping, any, and linter bypasses.
        "safety_bypasses": re.compile(
            r"\b(any)\b|as\s+any|!\s*[;,\n)\]\.]|!\.|@ts-ignore|@ts-expect-error|@ts-nocheck|eslint-disable|as\s+unknown\s+as|<any>"
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Process killers and catastrophic vulnerabilities. EXCLUDES TODO (debt) and console.log (print).
        "high_risk_execution": re.compile(
            r"\b(eval|document\.write|innerHTML|outerHTML|dangerouslySetInnerHTML|debugger|alert|process\.exit)\b"
        ),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(fetch|axios|http|https|fs|path|database|sql|localStorage|sessionStorage|indexedDB|document\.cookie|XMLHttpRequest|child_process|fs/promises)\b"
        ),
        # 10. api (Public Surface Area)
        # Captures explicit exports and public visibility.
        "api": re.compile(
            r"\b(export|public|module\.exports|exports\.)\b|@(Controller|Resolver|Get|Post|Put|Delete)\b"
        ),
        # 11. flux (State Mutation)
        # Mutation of state. EXCLUDES const (freeze_hits).
        # BUG FIX: `.current =`, `.set(`, `.delete(`, and `.add(` shared a
        # trailing `\b` with word-ending siblings (push/pop/...), but all
        # four end in `(` or `=` (non-word) -- `\b` right after can only
        # fire if the next char happens to be a word character, never true
        # for the realistic forms (`myRef.current = value` -- space after
        # `=`; `myMap.set('key', v)` -- quote after `(`). These four are
        # already self-delimited by their leading `.`, so pulled out of
        # the shared boundary group entirely.
        "state_mutation": re.compile(
            r"\b(?:let|var|this\.|setState|push|pop|shift|unshift|splice|sort|reverse)\b"
            r"|\.current[ \t]*=|\.set\(|\.delete\(|\.add\("
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # BUG FIX (Engine Rule 12, Comment-Style Completeness): typescript
        # is `standard_block` (both `//` and `/* */` are real comment
        # styles), but this only ever checked `//` -- a block-commented-out
        # function/class (`/* function foo() {} */`) was invisible.
        "dead_code": re.compile(r"(?://|/\*)[ \t]*(?:if|for|while|function|class|return|export|import)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"/\*\*|@param|@return|@throws|@deprecated|@typedef|@type|@template|@callback"),
        # 14. test (Testing & Assertions)
        # CRITICAL FIX: Negative lookbehind (?<!\.) prevents matching 'regex.test()' as an assertion.
        "test": re.compile(
            r"\b(?:describe|expect|beforeEach|afterEach|jest|vitest|playwright)\s*\(|(?<!\.)\b(?:it|test|assert)\s*\("
        ),
        # --- PHASE 3: SPECIALIZED SENSORS (Architecture & Hidden Complexity) ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(async|await|Promise|requestAnimationFrame|setImmediate|setTimeout|setInterval|Worker|postMessage|Observable|Subject|Subscription)\b"
        ),
        # 16. ui_framework (UI / View Components)
        "ui_framework": re.compile(
            r'<[A-Z]\w+|className=|use(?:State|Effect|Context|Reducer|Ref|Memo|Callback|Transition|Id)|props\.|this\.state|@Component|@Injectable|document\.(?:getElementById|querySelector)|["\']use\s+(?:client|server)["\']'
        ),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(r"=>[ \t]*\{|\(\)[ \t]*=>|function\s*\([^)]*\)[ \t]*\{"),
        # 18. globals (Global / Shared State)
        "globals": re.compile(r"\b(window\.|global\.|process\.env|document\.|navigator\.|self\.|globalThis\.)\b"),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"@\w+(?:\([^)]*\))?"),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(
            r"<\s*[A-Z][^>]*>|\b(?:keyof|infer|extends|Omit|Pick|Partial|Record|Required|Awaited|ReturnType|Parameters|NonNullable)\b"
        ),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(r"\.(?:map|filter|reduce|flatMap|some|every|find|forEach|groupBy)\s*\("),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(Math\.|tf\.|THREE\.|d3\.|gl-matrix|random)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # BUG FIX: `.bind(`, `.call(`, `.apply(` shared a trailing `\b`
        # with word-ending siblings, but end in a literal `(` -- broke
        # on the truly-empty-argument call form (`foo.bind()`), where
        # the next char after `(` is `)`, not a word char. Already
        # self-delimited by their leading `.`; pulled out of the group.
        "reflection_metaprogramming": re.compile(
            r"\b(?:arguments\.|prototype|__proto__|Object\.assign|Reflect|Proxy|Object\.defineProperty)\b"
            r"|\.bind\(|\.call\(|\.apply\("
        ),
        # --- AI & LLM SDK SENSORS (GLOBAL_, see #322) ---
        "llm_api": GLOBAL_LLM_API,
        "llm_orchestrator": GLOBAL_LLM_ORCHESTRATOR,
        "llm_vector_store": GLOBAL_LLM_VECTOR_STORE,
        "ml_traditional": GLOBAL_ML_TRADITIONAL,
        "dl_frameworks": GLOBAL_DL_FRAMEWORKS,
        # 24. import (Dependency Inclusions)
        "import": re.compile(
            r"\b(?:import(?:\s+type)?|export(?:\s+type)?)\b[^;]*?\bfrom\b|\brequire\s*\(|\bimport\s*\(",
            re.M,
        ),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (TYPESCRIPT) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
            #
            # HISTORICAL BUG: Originally, this regex was anchored to the start of the
            # line `^[ \t]*`. While this perfectly prevented the engine from hallucinating
            # commented-out imports (`// import { x }`), it completely blinded the firewall
            # to dynamic/inline execution. If an attacker tucked an import inside a function
            # (e.g., `const payload = require('malware')` or `await import('trojan')`),
            # it sailed right past the sensors.
            #
            # THE FIX: The `^` anchor has been stripped. We now rely on the `\b` word
            # boundary to find the keywords anywhere in the file. (Note: The engine's
            # optical comment-stripper runs BEFORE this regex, naturally preventing the
            # commented-out hallucination issue without needing strict line anchors).
            #
            # [ THE VERTICAL DESTRUCTURING SHIELD ]
            # We retain `[ \t\n]+` to safely leap across massive vertical multi-line
            # destructured imports: `import type \n { \n ASTNode \n } \n from`
            #
            # BUG FIX (epic #813/#815): side-effect-only imports
            # (`import "./styles.css";`, extremely common for CSS/
            # polyfill imports) have no `from` keyword and no parens at
            # all -- neither of the two alternatives above matched them.
            # Added a third alternative for bare `import "path";`.
            # =====================================================================
            r"\b(?:import(?:[ \t\n]+type)?|export(?:[ \t\n]+type)?)\b[^;]*?\bfrom[ \t\n]*['\"]([^'\"]+)['\"]|\b(?:require|import)[ \t\n]*\([ \t\n]*['\"]([^'\"]+)['\"]|\bimport[ \t\n]*['\"]([^'\"]+)['\"]",
            re.M,
        ),
        "_named_token_capture": re.compile(
            r"(?:import(?:[ \t\n]+type)?|export(?:[ \t\n]+type)?)\s+\{([^}]+)\}",
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"(?:@author|Created by)\s+(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # BUG FIX: adjacent unbounded quantifiers with overlapping
        # character sets (`\d+` next to `[^\]]*`) -- the same ReDoS
        # shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, and scheme earlier in this
        # epic. Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        "ssr_boundaries": re.compile(
            r"\b(getServerSideProps|getStaticProps|generateStaticParams|LoaderFunction|ActionFunction)\b"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(r"\b(emit|on|once|off|dispatchEvent|EventEmitter|EventTarget)\b"),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(r"\b(Inject|Injectable|Container|resolve|register|tsyringe|inversify)\b"),
        # 34. macros
        "macros": None,  # TypeScript uses transformer plugins/pre-processors, not standard inline macros.
        # 35. pointers
        "pointers": None,  # Managed memory environment.
        # 36. memory_alloc
        "memory_alloc": re.compile(r"\bnew\s+[A-Z]\w*"),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(logger|winston|pino|morgan|datadog|prometheus|newrelic|sentry)\.(?:info|error|warn|debug|trace|log)\b"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
        "debug_prints": re.compile(r"\bconsole\.(?:log|warn|error|dir|trace|info|table|time)\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"\bas\s+[A-Z]\w*|<\s*[A-Z]\w*\s*>\s*[a-zA-Z_]"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|fatalError|abort|process\.exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(sleep|delay|setTimeout|setInterval|Atomics\.wait)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>|\^|~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(
            r"\b(mutex|lock|synchronized|Semaphore|Atomics\.lock|Atomics\.wait)\b",
            re.I,
        ),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(const|readonly|final|Object\.freeze|Object\.seal)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(dispose|close|destroy|clearTimeout|clearInterval|removeEventListener|delete)\b"),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # `#` needed its own un-bounded branch: \b#\b can only match when
        # `#` is directly sandwiched between two word characters with no
        # separator (e.g. "x#y"), which never happens in real private-
        # field syntax (`#foo` is always preceded by `{`, whitespace, or
        # `.` -- never a bare word char) -- so the `#` alternative was
        # completely unreachable, same bug as javascript's copy of this.
        "encapsulation": re.compile(r"\b(private|protected|internal)\b|#[a-zA-Z_$]"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(on|addEventListener|subscribe|watch|effect)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(test\.skip|it\.skip|describe\.skip|xit|xdescribe|mock|stub)\b"),
        # --- NEW: ADVANCED ALGORITHMIC SENSORS ---
        # BUG FIX: `function\s*\*` shared a trailing `\b` with word-ending
        # siblings, but ends in a literal `*` -- `\b` right after can only
        # fire if the next char is a word character, never true for the
        # canonical `function* foo()` generator syntax (space after the
        # `*`). Unlike the co-located `yield\s*\*` (silently shadowed by
        # the bare `yield` alternative earlier in the same group, so it
        # happened to still "work"), nothing else in this pattern covers
        # bare `function*` generator declarations -- a genuine, unmasked
        # false negative. Pulled both out of the shared boundary group.
        "lazy_evaluation": re.compile(
            r"\byield\b|yield\s*\*|function\s*\*|\b(?:Generator|AsyncGenerator|Iterable|AsyncIterable)\b"
        ),
        "vectorized_math": re.compile(r"\b(matmul|dot|cross|multiply)\s*\("),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (JS/TS Specifics) ---
        "serialization_parsing": re.compile(r"\b(JSON\.parse|JSON\.stringify)\b"),
        "regex_execution": re.compile(r"\bnew\s+RegExp\b|\.(match|replace|search|split)\s*\("),
        "time_date_logic": re.compile(
            r"\b(Date\.now|new\s+Date|setTimeout|setInterval|clearTimeout|clearInterval|performance\.now)\b"
        ),
        "ipc_rpc_bridges": re.compile(r"\b(postMessage|Worker|MessageChannel|child_process|worker_threads|cluster)\b"),
        # --- PHASE 4: APPSEC & AI SENSORS (Zero-Trust Pipelines) ---
        "rce_funnel": re.compile(r"child_process\.(?:spawn|exec|execSync)\s*\(\s*['\"](?:python|bash|sh|bun|node)\b"),
        # BUG FIX (Rule 11, nested-delimiter coverage): the flat `[^)]*`
        # broke on one level of nested parens before the camouflage
        # keyword -- e.g. a URL built via a helper call
        # (`fetch(buildUrl("x"), {telemetry: payload})`), a realistic
        # evasion shape for exactly the kind of disguised-exfiltration
        # traffic this security-relevant rule exists to catch. Widened
        # to tolerate one level of self-nesting.
        "exfiltration_camouflage": re.compile(
            r"\b(fetch|axios\.post|https\.request)\s*\((?:[^()]|\([^()]*\))*(?:checkmarx|telemetry|metrics|audit|log)\b",
            re.I,
        ),
    },
}
