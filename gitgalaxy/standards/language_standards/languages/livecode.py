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
        "target_version": "LiveCode 9.6 / 10.0 (Current Stable/DP)",
        "last_updated": "2026-02-19",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Includes modern server scripts, builder files, binary stacks, and legacy Revolution stacks.
    "extensions": [".lc", ".livecodescript", ".lcb", ".livecode", ".stack", ".rev"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: LiveCode environments rarely use extensionless execution scripts.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions to anchor the LiveCode server/builder environment.
    "discriminators": [".lc", ".livecode", ".lcb", ".livecodescript"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for LiveCode Server environments.
    "shebangs": ["livecode-server"],
    # UPGRADED: Maps to Family 1d (multi_style_live)
    # Rationale: Accepts '--', '//', '#', and '/* */' to support both its legacy HyperTalk roots and modern C-style syntax.
    "lexical_family": "multi_style_live",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow. Includes English-like loops and try-catch.
        "branch": re.compile(
            r"\b(if|then|else|switch|case|default|repeat|while|until|times|try|catch|finally|throw|next\s+repeat|and|or|not)\b",
            re.I,
        ),
        # 2. args: Parameters / Coupling. Captures parameters in handlers (on, command, function).
        # BUG FIX (livecode tri-comparison manual verification, 2026-08-28): this
        # `^`-anchored per-line pattern was compiled `re.I` only -- missing the
        # `re.M` its structurally-identical `func_start` sibling below has -- so
        # `^` only ever matched the very start of the file. Result: at most one
        # args match per file (only when line 1 is a handler header), and ZERO
        # across the entire language-crucible/data/livecode corpus (99 files, 781
        # real handlers). Same one-flag omission class as any `^`-anchored
        # signal rule; the pattern itself was already correct on a single line.
        #
        # #2409: second alternative for LiveCode Builder `.lcb` handlers, whose
        # param list IS parenthesized and typed (`handler Foo(in x as String,
        # out y as Integer)`) -- captures the parenthesized body; the generic
        # per-function derivation then counts the comma-separated `in`/`out`/
        # `inout` clauses. Single-physical-line only (a `\`-continued multi-line
        # header still counts group 1 as whatever fit before the break) --
        # matches how LiveCode Script's own branch already behaves for a
        # continued line, and good enough for a proxy metric.
        "args": re.compile(
            r"^[ \t]*(?:"
            r"(?:private[ \t]+|public[ \t]+)?(?:on|command|function|getprop|setprop)[ \t]+[a-zA-Z0-9_-]+[ \t]+((?:(?!--|//|#|/\*)[^ \t\r\n])(?:(?!--|//|#|/\*)[^\r\n])*?)(?=[ \t]*(?:--|//|#|/\*|\r|\n|$))"
            r"|"
            r"(?:public[ \t]+|private[ \t]+)?handler[ \t]+(?!type[ \t])[a-zA-Z_][a-zA-Z0-9_]*[ \t]*\(([^)\r\n]+)\)"
            r")",
            re.I | re.M,
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries and state transformation verbs.
        # BUG FIX (#593): "constant" used to be listed here too, duplicating
        # immutability_locks and violating this key's own documented EXCLUDES
        # rule (immutability keywords belong in immutability_locks, not here).
        "structural_boundaries": re.compile(
            r"\b(put|get|set|go|send|dispatch|pass|return|add|subtract|multiply|divide|visual\s+effect|play|sort|find|replace)\b",
            re.I,
        ),
        # 4. func_start: Executable Logic Anchors. Anchors executable logic blocks (handlers).
        # Two dialects, one rule (#2409):
        #   * LiveCode Script (`.livecodescript`/`.lc`) -- `[public|private]
        #     on|command|function|getprop|setprop <name>` with an
        #     *unparenthesized* arg list, so the name is followed by
        #     whitespace/EOL/comment, never `(` (the `("function TargetFunc()",
        #     None)` invalid case in test_livecode.py stays invalid). Name in group 1.
        #   * LiveCode Builder (`.lcb`) -- `[public|private] handler <name>(...)`
        #     with a *parenthesized*, typed param list, or a `\` line
        #     continuation before the params. Name in group 2. The optional
        #     `(?:public|private)` prefix followed directly by `handler` (never
        #     `foreign`) means every `foreign handler` / `public foreign handler`
        #     FFI *binding declaration* -- C-prototype shaped, `binds to
        #     "<builtin>"`, no `... end handler` body -- is excluded by
        #     construction (parallel to a C header prototype not being a
        #     definition; decided in #2409). detector.py's Mode D naming goes
        #     through `_extract_semantic_name`, not these groups, so the
        #     two-group shape only affects the raw `struct_func_start` count.
        "func_start": re.compile(
            r"^[ \t]*(?:"
            r"(?:private[ \t]+|public[ \t]+)?(?:on|command|function|getprop|setprop)[ \t]+([a-zA-Z0-9_-]+)(?=[ \t\r\n]|--|//|#|/\*|$)"
            r"|"
            r"(?:public[ \t]+|private[ \t]+)?handler[ \t]+(?!type[ \t])([a-zA-Z_][a-zA-Z0-9_]*)[ \t]*(?=\(|\\[ \t]*(?:\r?\n|$))"
            r")",
            re.I | re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Defines structural entities (Stacks, Behaviors, Widgets).
        # BUG FIX (#593, Rule 11 nested-delimiter/coverage class): the name
        # class `["\'a-zA-Z_]\w*` stopped at the first non-word char, so it
        # could never consume dotted reverse-DNS module names -- LiveCode
        # Builder's real, dominant declaration form (`module
        # com.livecode.string`, confirmed against the language-crucible
        # corpus). The lookahead then required whitespace/EOL immediately
        # after that partial match, which a `.` never satisfies, so the
        # whole match failed outright. Widened to allow up to 10 dotted
        # segments (numerically bounded per Rule 5) and dropped the
        # never-functional leading quote-char option (a quote immediately
        # after would break the same lookahead, so it never actually
        # matched anything either).
        #
        # BUG FIX (livecode tri-comparison manual verification, 2026-08-28):
        # added a real quoted-name alternative as its OWN capture branch
        # (`"([^"\r\n]{1,200})"`), distinct from the broken char-class option
        # removed above. A LiveCode Script stack/behavior script exported to a
        # `.livecodescript` file opens with `script "Name"` (quoted, one per
        # file) -- the dominant declaration form for the Script half of the
        # corpus, ~63 files -- and the bareword-only capture matched NONE of
        # them (struct_class_start was 33, all from `.lcb` `module com.x.y`
        # bareword decls, 0 from `.livecodescript`). Two capture groups now;
        # `_resolve_class_start_match` in detector.py already handles the
        # group-1-or-group-2 alternation shape (same as fortran/lua/abap).
        "class_start": re.compile(
            r"^[ \t]*(?:script|behavior|widget|module|library)[ \t]+"
            r"(?:\"([^\"\r\n]{1,200})\"|([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*){0,10}))"
            r"(?=[ \t]*(?:--|//|#|/\*|\r?$))",
            re.I | re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Defensive programming and screen/message locking.
        "safety": re.compile(
            r"\b(try|catch|finally|throw|lock\s+screen|lock\s+messages|lock\s+errordialogs|assert|strict\s+compilation|is\s+a|is\s+strictly)\b",
            re.I,
        ),
        # 7. safety_neg: Safety Bypasses. Actively bypassing safety (disabling messages, raw do).
        # BUG FIX (#593, Rule 9/10-class trailing-boundary bug): the "do"
        # alternative's own negative lookahead exists specifically to
        # target "do" followed by a NON-identifier (a raw string/
        # expression -- the actual dynamic-eval bypass), yet the shared
        # trailing `\b` on the outer group required a WORD character
        # right after the consumed whitespace. Since the realistic target
        # of this alternative is almost always a quote or paren (both
        # non-word), that trailing boundary could essentially never be
        # satisfied for the alternative's own intended match --
        # `do "put 1 into x"` and `do (tExpr)` both silently never
        # matched. Pulled "do\s+(?!...)" out of the group (the lookahead
        # already fully delimits it; no trailing \b needed).
        "safety_bypasses": re.compile(
            r"\b(disable\s+messages|unlock\s+(?:screen|messages)|global\s+)\b|\bdo\s+(?![a-zA-Z_]\w*\b)",
            re.I,
        ),
        # 8. danger: High-Risk Execution. Process killers and blocking UI alerts in execution flow.
        "high_risk_execution": re.compile(
            r"\b(answer|ask|do(?!\s+(?:AppleScript|VBScript))|delete\s+(?:file|folder|url)|quit|exit\s+to\s+top)\b",
            re.I,
        ),
        # 9. io: I/O & Network Boundaries. Disk, Network, and URL fetching.
        # BUG FIX (#593): "post" used `[^ \t\n]+?` to span the payload
        # expression before "to url", which excludes spaces -- so any
        # realistic multi-word payload (`post "action=" & tAction to url
        # tURL`, string concatenation, function calls with args) never
        # matched; only a single bare token did. Widened to `[^\n]{1,300}?`
        # (bounded per Rule 5, still linear) so it spans the whole
        # single-line expression instead of stopping at the first space.
        "io": re.compile(
            r"\b(open\s+(?:file|socket|process)|read\s+from|write\s+to|close\s+(?:file|socket|process)|post\s+[^\n]{1,300}?\s+to\s+url|get\s+url|put\s+url|load\s+url)\b",
            re.I,
        ),
        # 10. api: Public Surface Area. Exposed surface area (Any non-private handler).
        "api": re.compile(
            r"^[ \t]*(?:public[ \t]+)?(?!(?:private)[ \t]+)(?:on|command|function|getprop|setprop)[ \t]+[a-zA-Z0-9_-]+",
            re.I | re.M,
        ),
        # 11. flux: State Mutation. State mutation (The 'put into' core of xTalk).
        # BUG FIX (#593): the put/add/subtract source-expression matchers
        # used `[^ \t\n]+?`, which excludes spaces -- so the dominant real
        # form (`put the effective filename of this stack into tPath`,
        # `add the number of lines of tList to tTotal`, any multi-word
        # expression before the keyword) never matched; only a single bare
        # token before "into"/"to"/"from" did. Widened to `[^\n]{1,300}?`
        # (bounded per Rule 5, still linear) so it spans the whole
        # single-line expression.
        "state_mutation": re.compile(
            r"\b(?:put\s+[^\n]{1,300}?\s+(?:into|after|before)|set\s+(?:the[ \t]+)?[a-zA-Z0-9_.]+\s+to|add\s+[^\n]{1,300}?\s+to|subtract\s+[^\n]{1,300}?\s+from)\b",
            re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code.
        "dead_code": re.compile(
            r"^[ \t]*(?:--|#|//)[ \t]*(?:on|command|function|put|get|set|if|repeat|try|end)\b",
            re.I | re.M,
        ),
        # 13. doc: Structured Documentation. Structured documentation (/** or --@ tags).
        # BUG FIX (#593, Rule 9/10-class trailing-boundary bug): the
        # `Description|Purpose|Author|Summary` alternation had a trailing
        # `\b` placed immediately after the literal `:` it requires. `:`
        # is a non-word character, so that `\b` only fires if the very
        # next character is a word character -- but the near-universal
        # real form is "Author: John Doe" (colon then a space), which is
        # non-word on both sides of that position, so the boundary never
        # fired and the tag never matched. `:` is already self-delimiting
        # (same principle as Rule 10), so the trailing `\b` is dropped.
        "doc": re.compile(
            r"^[ \t]*(?:--\||--@|/\*\*|//!).*(?:@param|@return|@author)|\b(?:Description|Purpose|Author|Summary):",
            re.I | re.M,
        ),
        # 14. test: Testing & Assertions. Unit testing framework markers.
        "test": re.compile(
            r"\b(command\s+test[a-zA-Z0-9_]*|pass\s+test|fail\s+test|Levure|LcU|runTests)\b",
            re.I,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. Message scheduling and non-blocking waits.
        # BUG FIX (#593): the "send X in Y seconds" target-message matcher
        # used `[^ \t\n]+?`, which excludes spaces -- so the dominant real
        # form (`send "myHandler" to me in 2 seconds`, any multi-word
        # message/target expression) never matched; only a single bare
        # token did. Widened to `[^\n]{1,300}?` (bounded per Rule 5, still
        # linear).
        "concurrency": re.compile(
            r"\b(send\s+[^\n]{1,300}?\s+in\s+[^\n]{1,300}?\s+(?:seconds|milliseconds|ticks)|wait\s+(?:for[ \t]+)?\d+\s+[^ \t\n]+?\s+with\s+messages|dispatch|pendingMessages|cancel)\b",
            re.I,
        ),
        # 16. ui_framework: UI / View Components. HyperCard-descendant object hierarchy.
        "ui_framework": re.compile(
            r"\b(card|stack|background|bg|button|btn|field|fld|group|grp|graphic|grc|image|img|scrollbar|browser|data\s+grid|widget)\b",
            re.I,
        ),
        # 17. closures: Closures / Anonymous Functions. (LiveCode Script lacks native lambdas).
        "closures": None,
        # 18. globals: Global / Shared State. Global state and environmental bindings.
        # BUG FIX (#593, Rule 9): `$ENV` started with the symbolic `$`,
        # which can never satisfy the shared leading `\b` -- real usage is
        # always preceded by whitespace/line-start (non-word on both
        # sides of that position), so it never matched. Pulled out of the
        # group with only a trailing `\b` (the `$` is self-delimiting).
        "globals": re.compile(
            r"\b(global\s+|the\s+global|the\s+environment|the\s+platform|it)\b|\$ENV\b",
            re.I,
        ),
        # 19. decorators: Decorators / Annotations. LCB attributes.
        "decorators": re.compile(r"^[ \t]*@(?:metadata|property|type|name|title)\b", re.M),
        # 20. generics: Generics / Type Parameters. (LCS is dynamically typed).
        "generics": None,
        # 21. comprehensions: Iterators / Comprehensions. Implicit list processing.
        # BUG FIX (#593): the `filter` target matcher used `[^ \t\n]+?`,
        # which excludes spaces -- so the common multi-word target form
        # (`filter lines of tData with "*.txt"`) never matched; only a
        # single bare token did. Widened to `[^\n]{1,300}?` (bounded per
        # Rule 5, still linear).
        "comprehensions": re.compile(
            r"\brepeat\s+for\s+each\s+(?:item|line|word|char|key|element)\b|\bfilter\s+[^\n]{1,300}?\s+(?:with|without)\b",
            re.I,
        ),
        # 22. scientific: Numerical / Compute Libraries. Native math commands.
        "scientific": re.compile(
            r"\b(sqrt|exp|ln|log2|log10|sin|cos|tan|asin|acos|atan|atan2|abs|round|trunc|random|any|average|max|min)\b",
            re.I,
        ),
        # 23. heat_triggers: Metaprogramming & Reflection. Dynamic execution and path hijacking.
        # BUG FIX (#593, Rule 10): `value(` and `evaluate(` end on the
        # self-delimiting `(`, but the shared trailing `\b` required a
        # word character immediately after it -- so the dominant real
        # call shape (a quoted expression, e.g. `value("1+1")`) never
        # matched; only an unquoted bare-identifier argument
        # (`value(tExpr)`) did. Pulled both out of the group with the
        # trailing `\b` dropped. Same defect hit `do\s+`: the dominant
        # real form of dynamic script execution is `do "some script"`
        # (a quoted string), but the shared trailing `\b` required a
        # word character right after the consumed whitespace, which a
        # quote never satisfies -- only `do <bareIdentifier>` matched.
        # Pulled "do\s+" out too (already self-delimited by \s+).
        "reflection_metaprogramming": re.compile(
            r"\b(the\s+params|the\s+paramcount|frontscripts|backscripts|insert\s+script)\b|\bdo\s+|value\(|evaluate\(",
            re.I,
        ),
        # 24. import: Dependency Inclusions. Library and stack loading.
        "import": re.compile(r"\b(start\s+using\s+(?:stack|behavior)|require|include|module)\b", re.I),
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:start[ \t]+using[ \t]+(?:stack[ \t]+|behavior[ \t]+)?|require[ \t]+|include[ \t]+|module[ \t]+)(?:['\"]([^'\"]+)['\"]|([^'\"\s]+))",
            re.I | re.M,
        ),
        # 25. ownership: Authorship metadata in comments.
        "ownership": re.compile(
            r"^[ \t]*(?:--|//|#)\s*(?:Author|Created by|Maintainer|Copyright):\s+([^\n]+)",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
        # 31. ssr_boundaries: View Horizon. Server-side rendering.
        # BUG FIX: the whole alternation used to be wrapped in \b(...)\b.
        # \b requires a word/non-word transition; `<?lc`, `?>`, and every
        # `$_POST`-style superglobal START with a non-word character
        # (`<` or `$`), so the leading \b could never match once that
        # symbol was preceded by anything else non-word (e.g. a space or
        # line start) -- meaning none of those 6 alternatives (everything
        # except the plain-word "put header") ever actually matched.
        # Each alternative now carries only the boundary that makes
        # sense for its own shape.
        "ssr_boundaries": re.compile(
            r"<\?lc|\?>|\$_POST|\$_GET|\$_SERVER|\$_COOKIE|\$_SESSION|\bput\s+header\b",
            re.I,
        ),
        # 32. events: Pub/Sub Network. Signal handlers and event brokers.
        "events": re.compile(
            r"^[ \t]*on\s+(?:mouseUp|mouseDown|openCard|closeCard|preOpenCard|openStack|closeStack|resizeStack|rawKeyDown|textChanged)\b",
            re.I | re.M,
        ),
        # 33. dependency_injection: Inversion of Control. Service locator patterns.
        "dependency_injection": re.compile(
            r"\b(?:set\s+the\s+behavior\s+of|start\s+using\s+(?:stack|behavior)|insert\s+script\s+into\s+(?:front|back))\b",
            re.I,
        ),
        # 34. macros: Preprocessor Hooks.
        "macros": None,
        # 35. pointers: Memory Map. Pass by reference in params.
        # BUG FIX (#593, Rule 9): the leading `\b` sat directly in front
        # of the symbolic `@` sigil. Real pass-by-reference params are
        # always preceded by whitespace/comma/paren (non-word on both
        # sides of that position), so the leading boundary never fired --
        # `@pList` never matched at all except in the contrived case of a
        # word character glued directly onto the `@`. Dropped the leading
        # `\b` (the `@` is self-delimiting); kept the trailing `\b`.
        "pointers": re.compile(r"@[a-zA-Z_]\w*\b", re.I),
        # 36. memory_alloc: Manual Memory Management.
        "memory_alloc": None,
        # 37. inline_asm: Bare Metal.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics.
        "telemetry": re.compile(
            r"\b(revLog|syslog|logError|logInfo|logWarn|logDebug|mergLog|rreLog|lcLog)\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Raw terminal output (puts to message box without target).
        "debug_prints": re.compile(r'^[ \t]*put\s+(?:"[^"]*"|[a-zA-Z0-9_]+)[ \t]*$', re.I | re.M),
        # 40. explicit_casts (Explicit Type Casting): English-style type checking.
        "explicit_casts": re.compile(r"\bis\s+(?:not\s+)?a\b|\bis\s+strictly\b", re.I),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts): Hard detonations.
        "panics_and_aborts": re.compile(r"\b(exit\s+to\s+top|quit|throw|abort)\b", re.I),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses): Temporal Duct Tape (Blocking wait).
        "thread_sleeps": re.compile(r"\bwait\s+(?:for[ \t]+)?\d+\s+[^ \t\n]+?(?!\s+with\s+messages)\b", re.I),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"\b(bitAnd|bitOr|bitXor|bitNot|bitShiftLeft|bitShiftRight)\b", re.I),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(lock\s+screen|lock\s+messages|lock\s+errordialogs)\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(constant\s+)\b", re.I),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(
            r"\b(delete\s+variable|close\s+file|stop\s+using|remove\s+script)\b",
            re.I,
        ),
        # 47. encapsulation
        "encapsulation": re.compile(r"\b(private\s+)\b", re.I),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"^[ \t]*on\s+[a-zA-Z0-9_-]+", re.I | re.M),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(skip\s+test)\b", re.I),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (LiveCode Specifics) ---
        "serialization_parsing": re.compile(
            r"(?i)\b(jsonImport|jsonExport|arrayEncode|arrayDecode|revXMLCreateTree)\b"
        ),
        "regex_execution": re.compile(r"(?i)\b(matchText|matchChunk|replaceText|filter\s+.*\s+with\s+regex)\b"),
        "time_date_logic": re.compile(
            r"(?i)\b(the\s+(?:seconds|ticks|time|date|internet date)|wait\s+(?:for|until))\b"
        ),
        # BUG FIX (#593, Rule 10): `shell\s*\(` ends on the self-delimiting
        # `(`, but the shared trailing `\b` required a word character
        # immediately after it -- so the dominant real call shape (a
        # quoted command string, e.g. `shell("ls -la")`) never matched;
        # only an unquoted bare-identifier argument (`shell(tCmd)`) did.
        # Pulled out of the group with the trailing `\b` dropped. Also
        # bounded the unbounded `.*` in `post\s+.*to` per Rule 5 (was
        # already empirically linear here, but bounding it removes the
        # theoretical risk while this line was already being touched).
        "ipc_rpc_bridges": re.compile(
            r"(?i)\b(open\s+socket|read\s+from\s+socket|post\s+[^\n]{0,300}to|get\s+url|open\s+process)\b|shell\s*\("
        ),
    },
}
