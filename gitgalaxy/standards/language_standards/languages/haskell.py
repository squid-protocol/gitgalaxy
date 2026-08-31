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
        "target_version": "GHC 9.14.1+ (Linear Types, cases, Type Abstractions, RecordDotSyntax)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard source, literate Haskell, and C-preprocessor Haskell.
    "extensions": [".hs", ".lhs", ".hsc", ".ghci"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Cabal custom setup scripts that evaluate as pure Haskell.
    "exact_matches": ["Setup.hs", "Setup.lhs"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, Stack configs, and Cabal manifests to anchor the ecosystem.
    "discriminators": [".hs", ".lhs", "stack.yaml", "cabal.project", ".cabal"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for script-based Haskell execution.
    "shebangs": ["runhaskell", "runghc", "stack", "ghci"],
    # UPGRADED: Maps to Family 5 (Hybrid Dash) -- #621: this comment
    # named the wrong family; "Hybrid Dash"/multi_style_dash doesn't
    # nest, and this rationale explicitly says Haskell's blocks DO nest.
    # "recursive_block_haskell" reuses the same iterative nested-peel
    # algorithm as recursive_block (Rust/Swift/Dart/Scala) with
    # Haskell's own -- / {- / -} tokens instead of C-style ones. Was
    # "standard_block" until now, meaning zero comment stripping at all
    # (standard_block never used the `--`/`{-`/`-}` tokens).
    # Rationale: Uses '--' for lines and '{- -}' for blocks, which strictly supports recursive nesting.
    "lexical_family": "recursive_block_haskell",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: decisions that split flow. Includes guards (|) and modern \cases.
        "branch": re.compile(r"\b(if|then|else|case|of|MultiWayIf)\b|\\cases?|^[ \t]*\|", re.M),
        # args: Parameters / Coupling. Captures type signatures, lambda bindings, and explicit @type apps.
        # #1209: the type-signature and lambda-parameter spans wrapped in
        # their own capture groups (was only reachable via group(0), the
        # whole match including the leading "::"/"\") so detector.py's
        # counter isolates just the real type/parameter text. Group 1
        # (the `::` type signature) is named in `_args_arrow_count_groups`
        # below, which routes it to detector.py's
        # `_count_haskell_type_arrows` -- curried arity from top-level
        # arrow count -- since neither the comma-list nor whitespace-
        # token fallback used by every other language maps onto
        # Haskell's syntax (and unlike every other branch here, a real
        # signature can have ZERO arrows, e.g. `noop :: IO ()`, so this
        # can't be inferred from content shape the way the other
        # branches are). Group 2 (lambda params, space-separated like
        # Scheme) already gets a correct count from the existing
        # whitespace-split fallback, no special-casing needed.
        # #1505 (follow-up): Group 3 is a signature-less function EQUATION's
        # own LHS pattern list (`name pat1 pat2 = ...`) -- the exact shape
        # func_start's own equation-form alternative anchors on (see that
        # rule's comment below), needed because typeclass instance methods
        # and where/let-local helpers routinely have no restated `::`
        # signature at all, so group 1 never fires for their block and args
        # silently measured 0 regardless of true arity. Anchored to the
        # ABSOLUTE start of the block (`^` with no re.M) so it only ever
        # reads the function's OWN first line, not some unrelated
        # `name ... =` deeper in the body. Named in
        # `_args_pattern_list_groups` below, which routes it to
        # detector.py's `_count_haskell_pattern_list` -- a naive
        # whitespace-split (the generic fallback every other language
        # uses) wrongly splits a single parenthesized compound pattern
        # like `(MetaList xs)` into two tokens, so this needs the same
        # kind of dedicated counter as group 1's arrow-counting. A guard
        # (`| cond = ...`) between the pattern list and the real `=`
        # isn't a shape this alternative understands and simply fails to
        # match (falls back to the pre-existing 0), not a regression.
        # #1616 (follow-up): extended this same group-3 alternative to also
        # accept a guard-only naming line (no `=` on the same line, just
        # immediately followed by `\n[ \t]+\|`), keeping it in sync with
        # func_start's own #1616 fix below.
        #
        # #1505 (follow-up, separate bug in the SAME rule): group 1's own
        # character classes never included "." -- real-world Haskell
        # overwhelmingly writes qualified/imported type names with a dot
        # (`T.Text`, `IO.Newline`, `M.Map`), and the moment the scan hit
        # that dot it fell out of the repetition entirely, truncating the
        # whole captured signature to whatever came before it (confirmed:
        # `inquotes :: T.Text -> T.Text` captured only `T` -- zero arrows
        # counted from a real 1-arrow signature, i.e. every arrow after
        # the first dotted type silently vanished). Added "." to both the
        # first-char and continuation classes; safe for `_count_haskell_
        # type_arrows` either way since it only scans for top-level "->"
        # substrings and doesn't care what other characters ride along
        # (e.g. a `forall a. a -> a` full-stop getting swept into the
        # capture is harmless noise, not a new miscount).
        #
        # #1564 (follow-up, same rule): group 3's own equation-anchored
        # alternative had the identical "let"-blocks-the-whole-line gap
        # func_start had (see that rule's own #1564 comment below) --
        # a same-line `let name args = expr` local binding never got its
        # args counted, since the reserved-word exclusion sat right after
        # `^[ \t]*` with no way to look past a leading "let ". Same fix:
        # an optional `(?:let[ \t]+)?` skipped before the exclusion.
        #
        # #1615 (follow-up, same rule): extended the same optional skip
        # to `where`, mirroring func_start's #1615 fix -- a same-line
        # `where name args = expr` binding is now found by func_start,
        # so args needs the identical `where`-skip or those newly-found
        # functions get a wrong (0) arg count instead of simply being
        # absent as before.
        "args": re.compile(
            r"::(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*((?:[a-zA-Z0-9_\'.,()\[\]]|=>|->|⊸)(?:[a-zA-Z0-9_\'.\s,()\[\]]|=>|->|⊸)*)"
            r"|\\([a-zA-Z0-9_\'\s,()\[\]{} -]+)->"
            r"|@[A-Z][a-zA-Z0-9_\']*"
            r"|^[ \t]*(?:(?:let|where)[ \t]+)?(?!(?:let|in|where|do|mdo|if|then|else|case|of|module|import"
            r"|class|instance|data|type|newtype|deriving|foreign|default"
            r"|infixl|infixr|infix)\b)[a-zA-Z_][a-zA-Z0-9_']*[ \t]+"
            r"((?:\"[^\"\n]*\"|\([^()\n]*\)|\[[^\[\]\n]*\]|[a-zA-Z0-9_'!]+)"
            r"(?:[ \t]+(?:\"[^\"\n]*\"|\([^()\n]*\)|\[[^\[\]\n]*\]|[a-zA-Z0-9_'!]+))*)"
            r"[ \t]*(?:=(?!=)(?!>)|\n[ \t]+\|)"
        ),
        # Which `args` capture-group index represents a `::` type
        # signature (routes to arrow-based counting in detector.py) --
        # see the comment on `args` above. Leading underscore excludes
        # this from the structural-signal scan loop (coding_analysis
        # skips any rule key starting with "_", same convention
        # `_dependency_capture` uses).
        "_args_arrow_count_groups": {1},
        # Which `args` capture-group index represents a signature-less
        # equation's own LHS pattern list -- routes to detector.py's
        # `_count_haskell_pattern_list` (#1505 follow-up). See the `args`
        # comment above for why this can't reuse the generic
        # comma/whitespace fallback.
        "_args_pattern_list_groups": {3},
        # linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope and data definitions.
        "structural_boundaries": re.compile(
            r"\b(module|data|type|newtype|class|instance|let|in|where|do|mdo|deriving|family|pattern)\b|%1\s*->|⊸"
        ),
        # 4. func_start: Executable Logic Anchors. Anchors executable logic (Type Signatures).
        # EXCLUDES data/type/class declarations to fix False Positives.
        # #1442: a plain `::` type signature is the ONLY thing the first
        # alternative below can anchor on -- but two extremely common
        # real-world patterns never have one: typeclass instance method
        # equations (the signature lives on the class declaration, not
        # restated per-instance, e.g. `toJSON PlainMath = String "plain"`)
        # and `where`-clause local helpers (Haskell allows -- and real
        # code commonly omits -- a signature on these). Both are instead
        # defined purely by a pattern-matched EQUATION: `name pattern...
        # = expr`, indented under an enclosing `instance ... where` or
        # `where` block. The second alternative anchors on that shape
        # directly: an indented (`[ \t]+`, deliberately excluding
        # column-0 -- unsigned top-level equations are a materially
        # different, still-open problem, see the issue) lowercase-led
        # identifier (real Haskell function/variable names can never
        # start uppercase, which is what lets this cleanly reject
        # constructor-headed patterns like `Just v = ...`), a reserved-
        # word exclusion (so `where`/`do`/`case`/etc. themselves can
        # never be mistaken for the bound name), then a lookahead
        # requiring at least one non-whitespace pattern token before an
        # unambiguous `=` (bounded to the current line via the `[^\n=]`
        # exclusion, so this can never cross into a later line's `=` --
        # each `=`-free line, e.g. every line of a `do` block that uses
        # `<-` instead, fails closed). The `(?<![!<>/])`/`(?![=>])`
        # guards keep `==`, `=>`, `<=`, `>=`, and `/=` from ever being
        # mistaken for the defining `=`; requiring a real pattern token
        # (not just more whitespace) before it is what excludes a bare
        # `name = expr` value binding (mirrors #1312's point-free
        # reasoning for the signature-anchored form -- zero args between
        # name and `=` means "value", not "function").  A given
        # function's 2nd+ pattern-matched clause (e.g. `toJSON`'s other
        # 5 equations in the example above) independently satisfies this
        # same alternative too; detector.py's `_slice_by_indentation`
        # dedups those against the block the first clause already
        # absorbed via the existing same-name-same-indent continuation
        # walk, rather than emitting one node per clause.
        # #1564: the reserved-word exclusion above (needed so `where`/
        # `do`/`case`/etc. can never be mistaken for the bound name)
        # sits immediately after `^[ \t]+`, so it also blocked the whole
        # line whenever it happened to START with the keyword `let` --
        # e.g. `let outputFile = fromMaybe "-" (optOutputFile opts)`,
        # a same-line `let name args = expr` local binding declared
        # inline in a `do` block. That shape's real name is never "let"
        # itself, just the token right after it, but the old lookahead
        # never got a chance to look past "let " to find it -- there's
        # no other position on the line where `^` can anchor a retry.
        # The new optional `(?:let[ \t]+)?` skips past a leading "let "
        # (if present) before applying the same exclusion+capture on
        # whatever follows, so `let name args = expr` now anchors on
        # `name` exactly like the pre-existing non-`let` equation form
        # -- while a bare multi-binding-block opener (`let` alone on its
        # own line, nothing before the next line's `=`) still can't
        # match, since the trailing `[ \t]+...=` lookahead has nothing
        # on that same line to satisfy either way.
        # #1615: extended the same optional-skip treatment to `where`
        # for same-line where-clause bindings, e.g.
        # `where matchTags tags = flip elem tags . T.toLower`.
        # #1616: the trailing `[ \t]+...=` lookahead above required an `=`
        # on the exact same line as the name and pattern list. This missed
        # guard-only equations (e.g. `isAllowedPunct c \n | cond = ...`)
        # where the `=` only appears on the indented guard lines below.
        # Extended the lookahead to accept either an unambiguous `=` on the
        # same line OR the line ending without an `=`/newline and immediately
        # followed by an indented guard `\n\3[ \t]+\|` (where `\3` is the
        # captured leading indent). Bounded and conservative:
        # this explicitly doesn't parse the indentation stack to prove the `|`
        # belongs to this binding vs. a sibling, but its limitation is
        # documented and ReDoS safe since the same-line prefix scan `[^\n=]*`
        # still fails closed if it hits a real `=` or crosses a newline.
        "func_start": re.compile(
            r"^[ \t]*(?:foreign\s+(?:import|export)\s+[a-zA-Z0-9_]+\s+(?:(?:unsafe|safe|interruptible)\s+)?(?:\"[^\"]*\"\s+)?)?(?!(?:data|type|newtype|class|instance|let|in|where|do|deriving)\b)(?:([a-zA-Z_][a-zA-Z0-9_\']*)|(\([^)]+\)))(?=(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*::)"
            r"|^([ \t]+)(?:(?:let|where)[ \t]+)?(?!(?:case|class|data|default|deriving|do|else|foreign|if|import|in|infix|infixl|infixr|instance|let|mdo|module|newtype|of|then|type|where)\b)([a-z_][a-zA-Z0-9_\']*)(?=[ \t]+[^\s=][^\n=]*(?:(?<![!<>/])=(?![=>])|\n\3[ \t]+\|))",
            re.M,
        ),
        # class_start: Object / Entity Declarations. Defines structural entities and typeclass boundaries.
        "class_start": re.compile(
            r"^[ \t]*(?:data(?:\s+family)?|newtype|class|type(?:\s+family)?)(?:(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*(?:\([^)]+\)(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*=>|[A-Z][a-zA-Z0-9_\']*(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*[a-z][a-zA-Z0-9_\']*(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*=>))?(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*([A-Z][a-zA-Z0-9_\']*)(?=(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*(?:[a-z][a-zA-Z0-9_\']*(?:[ \t\n]|--[^\n]*\n|\{-(?:[^-]|-(?!\}))*-\})*)*(?:=|\||where|deriving|::|\n|$))",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # safety: Defensive Programming. Functional safety (Maybe/Either) and exception brackets.
        "safety": re.compile(
            r"\b(Maybe|Either|Just|Nothing|Right|Left|try|catch|bracket|finally|onException|SafeT|mask|pure|return)\b"
        ),
        # safety_neg: Safety Bypasses. Bypassing purity (unsafePerformIO) and partial functions.
        "safety_bypasses": re.compile(
            r"\b(unsafePerformIO|unsafeCoerce|error|undefined|fromJust|head|tail|init|last|throw|unsafeFixIO)\b"
        ),
        # danger: High-Risk Execution. Forceful aborts and Debug-trace leaks in production.
        "high_risk_execution": re.compile(
            r"\b(die|exitWith|exitFailure|Debug\.Trace|trace|traceShow|traceIO|traceM)\b"
        ),
        # io: I/O & Network Boundaries. IO Monad and hardware interactions.
        "io": re.compile(
            r"\b(IO|readFile|writeFile|appendFile|hGetContents|hPutStr|openFile|withFile|getLine|getChar|Socket|Connection|runDB)\b"
        ),
        # api: Public Surface Area. Captured via module headers. Captures both explicit lists and implicit "all" exports.
        "api": re.compile(
            r"^[ \t]*module\s+[A-Z][a-zA-Z0-9_.]*(?:\s*\([^)]*\))?\s*where|\bforeign\s+export\b",
            re.M,
        ),
        # flux: State Mutation. State mutation (IORef/MVar) and monadic binds (<-).
        "state_mutation": re.compile(
            r"\b(IORef|STRef|TVar|MVar|TMVar|modifyIORef\'?|writeIORef|putMVar|modify|put|StateT)\b|<-"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(
            r"--\s*(?:data|type|newtype|class|instance|let|where|import|putStrLn)\b",
            re.M,
        ),
        # doc: Structured Documentation. Haddock documentation markers.
        "doc": re.compile(r"--\s*\||--\s*\^|\{-\||--\s*@(?:param|return|author)"),
        # test: Testing & Assertions. Verification framework keywords (QuickCheck/Hspec).
        "test": re.compile(
            r'\b(?:hspec|QuickCheck|prop_[a-zA-Z0-9_\']+|assertEqual|shouldBe|testGroup|testCase)\b|\b(?:describe|it|property)\s+"'
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # concurrency: Temporal Static. STM, async, and thread forking.
        "concurrency": re.compile(r"\b(forkIO|forkOS|async|wait|cancel|MVar|TVar|STM|atomically|threadDelay)\b"),
        # ui_framework: UI / View Components. Functional reactive GUI and web components.
        "ui_framework": re.compile(r"\b(Threepenny|Brick|Reflex|Miso|Gtk|widget|vBox|hBox|Lucid|Blaze|Monomer)\b"),
        # closures: Closures / Anonymous Functions. Anonymous lambda depth.
        "closures": re.compile(r"\\[a-zA-Z0-9_\'\s(),\[\]]+\s*->|\\cases?"),
        # globals: Global / Shared State. Top-level state hacks (typically MVars using unsafePerformIO).
        # BUG FIX: `[^=]*` blocked crossing the `=` that MUST appear
        # before `unsafePerformIO` in any real usage (the binding's own
        # implementation line: `counter = unsafePerformIO ...`) -- this
        # signature could never match a single real occurrence of the
        # idiom it's meant to detect. Replaced with a bounded
        # lazy-any-character span ({0,200}?, ReDoS-safe) so it can cross
        # both `=` and intervening lines (e.g. a `{-# NOINLINE #-}`
        # pragma between the signature and the binding).
        "globals": re.compile(
            r"^[ \t]*[a-z_][a-zA-Z0-9_\']*\s*::\s*(?:IORef|TVar|MVar)[\s\S]{0,200}?unsafePerformIO",
            re.M,
        ),
        # decorators: Decorators / Annotations. GHC pragmas (INLINE, LANGUAGE).
        "decorators": re.compile(r"\{-#\s*(?:INLINE|NOINLINE|LANGUAGE|OPTIONS_GHC|RULES|MINIMAL)\s+[^#]*#-\}"),
        # generics: Generics / Type Parameters. forall quantification and constraints.
        "generics": re.compile(
            r"\bforall\s+[^.]+\.|\b(?:[A-Z][a-zA-Z0-9_\']*\s+[a-z][a-zA-Z0-9_\']*[ \t]*=>)|\([^)]+\)[ \t]*=>"
        ),
        # comprehensions: Iterators / Comprehensions. List comprehensions and dense monad applicatives.
        "comprehensions": re.compile(r"\[\s*[^|\]]+\s*\|[^\]]+\]|<\$>|<\*>|>>="),
        # scientific: Numerical / Compute Libraries. Advanced Math and Linear Algebra.
        "scientific": re.compile(
            r"\b(Complex|RealFloat|Floating|Numeric\.LinearAlgebra|Matrix|Vector|ad|grad|jacobian|sin|cos|tan|exp|log|pi)\b"
        ),
        # heat_triggers: Metaprogramming & Reflection. QuasiQuotes and Template Haskell.
        "reflection_metaprogramming": re.compile(
            r"\b(TemplateHaskell|QuasiQuotes|TypeFamilies|GHC\.Generics|Generic)\b|\[[a-z_]+\||\$\([a-zA-Z0-9_\']+\)"
        ),
        # import: Dependency Inclusions. Module resolution.
        "import": re.compile(r"^[ \t]*import\s+(?:qualified[ \t]+)?[A-Z][a-zA-Z0-9_.]*", re.M),
        "_dependency_capture": re.compile(
            r"^[ \t]*import\b[\s\S]{0,100}?(?:qualified\b[\s\S]{0,100}?)?([A-Z][a-zA-Z0-9_.]*)", re.M
        ),
        # ownership: Authorship indicators in comments.
        "ownership": re.compile(r"--\s*\|?\s*(?:Author|Maintainer|Copyright|License):\s+([^\n]+)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:spec-[0-9]+|audit|rfc)\]", re.I),
        "ssr_boundaries": re.compile(
            r"\b(Yesod|Servant|ScottyM|ActionM|lucid|blaze-html|ToJSON|FromJSON|Handler|respond)\b"
        ),
        "events": re.compile(
            r"\b(Event|Behavior|Dynamic|reactive-banana|reflex|frp|stepper|accumE|conduit|Pipes|Stream)\b"
        ),
        "dependency_injection": re.compile(r"\b(ReaderT|MonadReader|Has[A-Z][a-zA-Z0-9_\']+|ask|asks|local)\b"),
        "macros": re.compile(
            r"\{-#\s*LANGUAGE\s+[^#]*#-\}|\$[(a-z_A-Z0-9\']|^[ \t]*#(?:define|undef|if|ifdef|ifndef|elif|else|endif|include)\b",
            re.M,
        ),
        "pointers": re.compile(r"\b(Ptr|ForeignPtr|FunPtr|StablePtr|peek|poke|castPtr|plusPtr|nullPtr|Storable)\b"),
        "memory_alloc": re.compile(r"\b(malloc|mallocBytes|alloca|allocaBytes|free|Foreign\.Marshal)\b"),
        "inline_asm": re.compile(r"\bforeign\s+import\s+(?:ccall|cplusplus|prim|capi)\b"),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # telemetry: Professional structured logging.
        "telemetry": re.compile(r"\b(?:logDebug|logInfo|logWarn|logError|logOther|katip|MonadLogger|LoggerT)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
        "debug_prints": re.compile(r"\b(putStr|putStrLn|print|putChar)\b"),
        # # # 40. explicit_casts (Explicit Type Casting) "Trust Me" Tax.
        "explicit_casts": re.compile(r"\b(unsafeCoerce|coerce|fromIntegral|realToFrac|floor|ceiling|truncate|round)\b"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|throwIO|panic|error)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(threadDelay)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(
            r"\b(?:shift[LR]?|rotate[LR]?|xor|complement|testBit|setBit|clearBit|complementBit)\b|\.&&\.|\|\.\|\|\."
        ),
        # sync_locks: Barricades preventing races.
        "sync_locks": re.compile(r"\b(takeMVar|putMVar|readMVar|swapMVar|atomically|STM|Mutex|lock|unlock)\b"),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(pure|return|frozen|immutable|const)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(hClose|close|free|bracket|finally|onException)\b"),
        # 47. encapsulation (Encapsulation / Access Modifiers)
        "encapsulation": re.compile(r"^[ \t]*module\s+[A-Z][a-zA-Z0-9_.]*\s*\([^)]*\)\s*where", re.M),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(subscribe|onEvent|addEventListener|watch)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs) Safety Theater.
        "test_skip": re.compile(r"\b(ignore|pending|skip|xit|xdescribe)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Haskell Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(Data\.Aeson|decode|decodeStrict|fromJSON|Data\.Binary|Data\.Serialize)\b"
        ),
        # `=~` was inside the shared \b...\b wrapper, but \b requires a
        # word/non-word transition -- since neither `=` nor `~` is a word
        # character, `\b=~\b` can only match when the operator has no
        # surrounding whitespace (e.g. "x=~y"), never idiomatic Haskell
        # like "text =~ pattern" (space on both sides means no boundary
        # exists at either edge). Split out unguarded.
        "regex_execution": re.compile(r"\b(Text\.Regex|makeRegex|matchRegex)\b|=~"),
        "time_date_logic": re.compile(r"\b(getCurrentTime|diffUTCTime|addUTCTime|System\.Time|threadDelay)\b"),
        "ipc_rpc_bridges": re.compile(
            r"\b(System\.Process|createProcess|callProcess|callCommand|forkIO|Control\.Concurrent)\b"
        ),
    },
}
