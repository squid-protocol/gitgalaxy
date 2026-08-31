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
        "target_version": "Dart 3.11 (Records, Patterns, Class Modifiers, Macros, FFI)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard Dart sources.
    "extensions": [".dart"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Dart rarely uses extensionless configurations.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, pub package manifests, and analyzer configurations to anchor Flutter/Dart projects.
    "discriminators": [
        ".dart",
        "pubspec.yaml",
        "pubspec.lock",
        "analysis_options.yaml",
        ".metadata",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for standalone Dart scripting.
    "shebangs": ["dart"],
    # UPGRADED: Maps to Family 2 (Nested C)
    # Rationale: (CORRECTION) Like Swift and Rust, Dart officially supports nested multi-line
    # comments (/* /* */ */). Standard C parsing would prematurely terminate here causing geometry failure.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow. Includes modern pattern guards (when) and null-coalescing.
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|while|do|try|catch|finally|break|continue|when)\b|&&|\|\||\?|\?\?",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Captures parameters in function, method, and lambda signatures.
        # #1209: parameter-list span wrapped in its own capture group in
        # both alternatives (was only reachable via group(0), the whole
        # match including the name prefix) so detector.py's counter
        # isolates just "(...)" -- the whole-match fallback overcounted
        # every zero/one-arg signature by +1 the same way Python's did
        # (#1199). Name group added to the first alternative too, purely
        # so existing extraction tests keep passing.
        # #2309 (investigated, NOT fixed via this regex -- see detector.py's
        # dart branch instead): a bodyless (`;`-terminated) `this.`/`super.`-
        # forwarding constructor (`_DeleteTextAction(this.state, ...);`,
        # flutter/editable_text.dart:6353) reads 0 args because `func_start`
        # accepts a bare `;` terminator for these but this SEPARATE
        # `args`-counting regex never did. Adding `;` to the trailing
        # lookahead here was tried and reverted: `test_dart_args_invalid`
        # (`tests/extraction/languages/test_dart.py`) already asserts this
        # regex must NEVER match a bare call statement (`foo(x);`) --
        # `func_start`'s own Invocation Shield (#1221) doesn't apply here,
        # since this regex is also `.search()`ed over the whole function
        # `block` when dart supplies no `args_search_text` (true before
        # #2309's own detector.py fix), so a `;`-accepting version matches
        # the FIRST bare call statement inside a zero-paren declaration's own
        # body (e.g. `Rect get bounds { ... box.getTransformTo(null); ...
        # }`, wrongly borrowing 1 arg) just as readily as a real bodyless
        # ctor. Fixed instead via `args_count_override` in detector.py,
        # which counts the real parameter list directly for this one shape
        # without loosening this shared regex's own contract.
        "args": re.compile(
            r"(?!(?:if|for|while|switch|catch|case|when|return|throw|new)\b)\b([A-Za-z_$][\w$]*)(?:[ \t\n]*<[^>]*>)?[ \t\n]*(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))(?=[ \t\n]*(?:\{|=>|:|async|sync))|(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))[ \t\n]*=>",
            re.I | re.M,
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and const/final.
        "structural_boundaries": re.compile(
            r"\b(var|late|return|yield|await|class|mixin|extension|enum|typedef|import|export|part|library|base|sealed|interface|macro)\b|=>",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # ReDoS clamped to {0,5}. Strict capture group and positive lookahead applied.
        # #1221: the trailing lookahead's parenthesized alternative
        # used to be a bare `\(` -- proof a `(` follows, nothing more
        # -- so a bare call statement at true line start (`next();`)
        # false-positive-matched as a method/function definition. Dart
        # has both a genuinely prefixed stub case that ends in bare
        # `;` with no `{`/`=>` anywhere (`external void
        # externalFunc();`, has a modifier + return type) and a
        # legitimate zero-prefix case (the bare constructor shape
        # `MyClass() {}`, no modifier and no return type) that always
        # reaches a real `{` anyway -- so, mirroring groovy's #1221
        # fix, this is split into three alternatives instead of one:
        # (A) has a modifier (static/external/abstract/covariant/
        # late), (B) has no modifier but has a return-type-shaped
        # prefix token -- both keep the original lenient lookahead
        # (bare `;` still allowed, since a real call statement never
        # carries a modifier or a return type), or (C) has neither --
        # must fully close its (non-nested, same bound as `args`)
        # parameter list and reach a real `=>`/`{`, never a bare `;`
        # (a bare call and a zero-prefix stub are otherwise
        # indistinguishable here, but dart's zero-prefix valid cases
        # are all constructors that always have bodies anyway, so this
        # loses no coverage).
        # =====================================================================
        # [ THE RETURN-TYPE BOUNDARY SHIELD (DART) ]
        # Issue #1417: The previous return-type token class `[\w<>\[\],?(){}]`
        # allowed `{`, `}`, `(`, `)` as valid literal characters. Combined with
        # lazy repetition, this let the return-type guess wander across a real
        # function's own parameter-list close and body-open `) {` and land on an
        # unrelated identifier deep inside the body (e.g. `Navigator.of`),
        # misreporting it as a phantom function definition.
        # FIX: Tightened the character class to `(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))`
        # to reject `{`/`}` entirely and only permit `(`/`)` if they are balanced.
        # This prevents the regex from crossing structural boundaries like `) {`.
        # =====================================================================
        "func_start": re.compile(
            r"^[ \t]*(?!(?:implements|with|extends)\b)(?:@[a-zA-Z_$][\w$]*\b(?:\([^)]*\))?[ \t\n]*){0,5}"
            r"(?:"
            r"(?:(?:static|external|abstract|covariant|late)[ \t\n]+){1,5}"
            r"(?!(?:(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+[ \t\n]+){0,5}?)(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\())\b)"
            r"(?:(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+[ \t\n]+){0,4}?(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+(?<!,)[ \t\n]+))?"
            r"(?!(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\()|Function)\b)"
            r"(?:(?:(?P<getA>get)|set|factory|const)[ \t\n]+)?((?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*|operator[ \t\n]+[^\s\w]+)"
            # #2462: one level of generic-argument nesting in the method's
            # own type-parameter list (`foo<T extends State<StatefulWidget>>()`)
            # -- a bare `<[^>]*>` stops at the inner `>` and the whole
            # generic method is missed.
            r"(?=[ \t\n]*(?:<(?:[^<>]|<[^<>]*>)*>[ \t\n]*)?(?:\(|=>|\{|(?(getA);|(?!))))"
            r"|"
            r"(?:(?:static|external|abstract|covariant|late)[ \t\n]+){0,5}"
            r"(?!(?:(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+[ \t\n]+){0,5}?)(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\())\b)"
            r"(?:(?!\?[ \t\n]+(?:get|set|factory|[a-zA-Z_]))(?:(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+[ \t\n]+){0,4}?(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+(?<!,)[ \t\n]+)))"
            r"(?!(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\()|Function)\b)"
            r"(?:(?:(?P<getB>get)|set|factory|const)[ \t\n]+)?((?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*|operator[ \t\n]+[^\s\w]+)"
            r"(?=[ \t\n]*(?:<(?:[^<>]|<[^<>]*>)*>[ \t\n]*)?(?:\(|=>|\{|(?(getB);|(?!))))"
            r"|"
            # #2308 item 1: `implements`/`with` added to every occurrence of this
            # keyword-exclusion list (all 8, shared verbatim across all 4
            # alternatives). The outermost `(?!(?:implements|with|extends)\b)`
            # guard at this regex's very start only rejects a match that STARTS
            # on one of these keywords -- it doesn't stop the return-type-prefix
            # token loop below from swallowing one of them as an ordinary interior
            # token when the match starts on an earlier line instead (e.g. a
            # multi-line `class Foo extends Base\n    with\n        MixinA,\n
            # MixinB\n    implements SomeInterface {` header, where a match
            # starting on `MixinB`'s own line can consume `implements` as its
            # final "return-type" token and land on `SomeInterface` as a phantom
            # function name). Confirmed via flutter/editable_text.dart:2480's
            # `EditableTextState ... implements AutofillClient {` header.
            # Deliberately does NOT add `extends` here -- already confirmed unsafe
            # in this same investigation (#2072 item 1): `extends` also appears
            # inside a generic method's own type-parameter bound
            # (`pushNamed<T extends Object?>(...)`), which this token loop cannot
            # distinguish from a bare class-header continuation without real
            # bracket-depth tracking. A class header that continues via a bare
            # `extends` on its own line (rare -- `extends` is almost always
            # attached to the same line as `class Foo`) can still slip through;
            # left as a known, documented residual limitation rather than risk
            # breaking the far more common generic-bound pattern.
            # #2071: this zero-prefix branch's lookahead used to accept a bare
            # `=>` unconditionally (no `get` required) and validated a preceding
            # "parameter list" with a naive, non-balanced-paren `\([^)]*\)` --
            # together these made Dart 3 switch-expression arms (`Pattern =>
            # result,`, including bare `_ => result,`) and ordinary call
            # statements with a lambda argument (`obj.method((x) => ...)`, whose
            # nested `)` satisfied the naive paren check) false-positive-match as
            # function/getter definitions. Dart's real grammar has no
            # parameterless `=> expr` construct without an explicit `get`, so the
            # bare-arrow alternative is now gated the same way the bare `;`
            # alternative already is via `(?(getC)...)`. The paren alternative now
            # reuses the SAME balanced-paren pattern the `args` rule and this
            # regex's own return-type-prefix groups already use elsewhere, and
            # rejects a parameter list that opens with `:` (only valid in Dart's
            # object-destructuring patterns, e.g. `StatefulElement(:final T
            # state) => state,` -- never a real parameter list).
            r"(?!(?:(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+[ \t\n]+){0,5}?)(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\())\b)"
            r"(?!(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\()|Function)\b)"
            r"(?:(?:(?P<getC>get)|set|factory|const)[ \t\n]+)?((?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*|operator[ \t\n]+[^\s\w]+)"
            r"(?=[ \t\n]*(?:<(?:[^<>]|<[^<>]*>)*>[ \t\n]*)?(?:\((?!\s*:)(?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)[ \t\n]*(?:async\*?|sync\*)?[ \t\n]*(?:=>|\{|:)|(?(getC)=>|(?!))|\{))"
            r"|"
            r"(?!(?:(?:(?:[\w<>\[\],.?]|\((?:[^()]|\([^()]*\))*\))+[ \t\n]+){0,5}?)(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\())\b)"
            r"(?!(?:class|mixin|enum|extension(?![ \t\n]*[(<])|typedef|implements|with|in|on|if|for|while|switch|catch|try|finally|case|when|assert|return|throw|new|var|final|const(?![ \t\n]+(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*(?:<[^>]*>[ \t\n]*)?\()|Function)\b)"
            r"(?:const[ \t\n]+)?(_?[A-Z]\w*(?:\.[a-zA-Z_]\w*)?)"
            # #2308 item 2 / #2462: this alternative originally required
            # `this.`/`super.` inside the parens. A bodyless DEFAULT/named
            # constructor with an EMPTY parameter list (`ClassName();`,
            # `ClassName.foo();` -- e.g. flutter/semantics.dart's
            # `ChildSemanticsConfigurationsResultBuilder();`) has neither and
            # never matched. The lookahead now also accepts whitespace-only
            # parens -- but that form is shape-identical to a bare zero-arg
            # call statement (`FlutterTimeline.finishSync();`,
            # `SystemNavigator.selectSingleEntryHistory();`), so detector.py's
            # dart branch gates the empty-paren case on real brace-depth
            # tracking: it's kept only when the name's leading segment is the
            # nearest brace-enclosing class/mixin/enum -- true for a real
            # constructor, never for a call statement. The `this.`/`super.`
            # form stays regex-only (unambiguous on its own).
            r"(?=[ \t\n]*(?:<[^>]*>[ \t\n]*)?\((?:[ \t\n]*|[^)]*(?:this\.|super\.)[^)]*)\)[ \t\n]*;)"
            r")",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # =====================================================================
        # [ THE VERTICAL MODIFIER & INHERITANCE SHIELD (DART) ]
        # Dart allows modifiers to stack (e.g., `abstract base mixin class`)
        # and extends/implements declarations that broke the rigid trailing lookahead.
        # FIX: Grouped the class modifiers into a bounded set `(?:(?:abstract|sealed|base|interface|final|macro)[ \t\n]+){0,5}`.
        # Upgraded all internal spaces to `[ \t\n]+` to jump vertical gaps, and
        # swapped the rigid lookahead for an optional non-capturing inheritance
        # group `(?:[ \t\n]+(?:extends|implements|with).*?)?` to handle inheritance paths.
        # =====================================================================
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+\b(?:\([^)]*\))?[ \t\n]*){0,5}"
            r"(?:(?:abstract|sealed|base|interface|final|macro|mixin)[ \t\n]+){0,5}"
            r"(?:class|mixin|enum|extension(?:[ \t\n]+type(?:[ \t\n]+const)?)?|extension)[ \t\n]+(?:/\*.*?\*/[ \t\n]*)?([A-Z_]\w*)(?:[ \t\n]+(?:extends|implements|with)[ \t\n]+[A-Za-z_$][\w_<>, \t\n]*)?",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Null safety boundaries, type assertions, and required parameters.
        # BUG FIX: `@immutable` and `@mustCallSuper` both start with `@`
        # (non-word), so the shared leading \b could only fire when a
        # word char immediately preceded the `@` -- never true for how
        # annotations are actually written (always preceded by
        # whitespace or a line start). Both never matched at all.
        # (`!is` is a separate, harmless case: it still "matches" via
        # the bare `is` alternative catching its own tail as a
        # substring, so it isn't a functional miss -- left as-is.)
        "safety": re.compile(
            r"\b(?:try|catch|finally|on\s+[A-Z]\w*|assert|required|late|is|!is|SafeArea)\b"
            r"|@immutable|@mustCallSuper|\?\?|\?.",
            re.I,
        ),
        # 7. safety_neg: Safety Bypasses. Actively bypassing sound null safety or static analysis.
        "safety_bypasses": re.compile(r"!\s*[;,\n)\.\]]|\bdynamic\b|//\s*ignore(?:_for_file)?:\s*\w+"),
        # 8. danger: High-Risk Execution. Process killers and catastrophic exit commands.
        "high_risk_execution": re.compile(r"\b(exit|exitCode|Process\.killPid)\b", re.I),
        # 9. io: I/O & Network Boundaries. Disk, Network, WebSockets, and Uri parsing (Includes legacy CERN triggers).
        "io": re.compile(
            r"\b(File|Directory|HttpClient|HttpServer|ServerSocket|WebSocket|Uri\.parse|HtmlDocument|HttpRequest|HttpResponse|HTRequest|Nexus|ENQUIRE)\b",
            re.I,
        ),
        # 10. api: Public Surface Area. Exposed visibility (Lack of _ prefix) and routing decorators.
        "api": re.compile(
            r"\b(export|part\s+of)\b|@(Route|Get|Post|Mapping|visibleForTesting|pragma)\b|^[ \t]*(?:class|mixin|enum|extension|typedef)\s+(?![_])[A-Za-z]\w*",
            re.I | re.M,
        ),
        # 11. flux: State Mutation. State mutation (setState and reactive collection mutators).
        "state_mutation": re.compile(
            r"\b(setState|notifyListeners|markNeedsBuild|StreamController\.add)\b|[^!=<>\+\-\*\/%&\|\s]=\s*[^=]|(?:\+\+|--)|\.(?:add|addAll|remove|insert|clear|update)\s*\(",
            re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code or dead widgets.
        "dead_code": re.compile(
            r"//[ \t]*(?:class|mixin|void|if|for|while|print|Widget|return)\b|/\*[ \t]*(?:class|mixin|void|Widget|if|for)"
        ),
        # 13. doc: Structured Documentation. dartdoc annotations and structured comments.
        "doc": re.compile(r"///|/\*\*|@param|@return"),
        # 14. test: Testing & Assertions. Flutter test frameworks and standard expect/verify markers.
        "test": re.compile(
            r"\b(?:test|testWidgets|group|setUp|tearDown|pumpWidget|pumpAndSettle|find\.(?:byType|text|byKey))\b|\b(?:expect|verify|when)\s*\("
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. Event Loop primitives (Future, Stream, Isolate).
        # BUG FIX: `sync\*` ended on `*` (non-word) inside the shared
        # trailing \b group -- the generator-function modifier
        # `sync* { ... }` never matched (no bare "sync" alternative
        # exists to mask it, unlike `async*`, which happened to still
        # match via the bare "async" alternative catching it as a
        # substring). Pulled both `\*`-suffixed forms out for
        # consistency.
        "concurrency": re.compile(
            r"\b(?:async|await|Future|Stream|Isolate|ReceivePort|SendPort|Completer|Timer|StreamSubscription)\b"
            r"|\basync\*|\bsync\*",
            re.I,
        ),
        # 16. ui_framework: UI / View Components. Flutter Component trees and DOM nodes (Includes TBL triggers).
        "ui_framework": re.compile(
            r"\b(Widget|BuildContext|StatefulWidget|Scaffold|Container|Text|HtmlElementView|RichText|Hyperlink|SGML|HyperText|Browser)\b",
            re.I,
        ),
        # 17. closures: Closures / Anonymous Functions. Fat-arrows and anonymous function blocks.
        # BUG FIX (ReDoS): `[^)]*` was unbounded. Confirmed quadratic
        # scaling (0.011s/0.045s/0.179s/0.713s/2.85s for n=5k/10k/20k/
        # 40k/80k -- ~4x per doubling) against an adversarial run of
        # unclosed `(` characters: at each of the ~n candidate `(`
        # start positions, the unbounded class scans to the end of the
        # string looking for a `)` that never appears, backtracking
        # across the whole remaining length -- O(n) work at each of
        # O(n) positions. Bounded to `{0,300}`, the same fix shape used
        # elsewhere in this sweep.
        "closures": re.compile(r"=>|\(\s*[^)]{0,300}\)\s*(?:async\*?|sync\*?)?[ \t]*\{"),
        # 18. globals: Global / Shared State. Static class fields and environmental bindings.
        "globals": re.compile(
            r"\b(static\s+final|static\s+const|Platform\.environment|window\.|Zone\.current)\b|^[ \t]*(?:final|const|var)\s+[A-Za-z_$][\w$]*[ \t]*=",
            re.I | re.M,
        ),
        # 19. decorators: Decorators / Annotations. Annotations applied to methods/classes.
        "decorators": re.compile(r"@[A-Za-z_$][\w$]*(?:\([^)]*\))?"),
        # 20. generics: Generics / Type Parameters. Parameterized collections and generic classes.
        "generics": re.compile(r"<\s*[A-Z][^>]*>"),
        # 21. comprehensions: Iterators / Comprehensions. Collection for/if and functional pipelines.
        "comprehensions": re.compile(
            r"\[\s*(?:for|if)\s*\([^)]*\)|\{\s*(?:for|if)\s*\([^)]*\)|\.(?:map|where|reduce|fold|expand|every|any)\s*\("
        ),
        # 22. scientific: Numerical / Compute Libraries. math.pi, typed binary arrays, and Matrix4 vectors.
        "scientific": re.compile(
            r"\b(math\.sin|math\.cos|math\.sqrt|math\.pi|dart:math|Float64List|Float32List|Int32List|Uint8List|Vector2|Vector3|Matrix4)\b",
            re.I,
        ),
        # 23. heat_triggers: Metaprogramming & Reflection. Reflection, Native Bridges, and code generation markers.
        "reflection_metaprogramming": re.compile(
            r'\b(MethodChannel|EventChannel|dart:mirrors|reflect|reflectClass|noSuchMethod|dart:js_interop)\b|part\s+[\'"][^\'"]+\.(?:g|freezed)\.dart[\'"]',
            re.I,
        ),
        # 24. import: Dependency Inclusions. Dependency resolution and library partitions.
        "import": re.compile(r'^[ \t]*(?:import|export|part|part\s+of)\b\s*[\'"][^\'"]+[\'"]', re.M),
        "_dependency_capture": re.compile(
            r"(?:^|[ \t;{}])(?:import|export|part(?:[ \t\n]+of)?)\b[ \t\n]*(?:['\"]([^'\"]+)['\"]|([a-zA-Z_$][\w$]*)[ \t\n]*;)",
            re.M,
        ),
        # 25. ownership: Authorship indicators.
        "ownership": re.compile(r"//\s*(?:Author|Created by|Maintainer|Copyright):\s+([^\n]+)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags and architecture specs.
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(
            r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit|RFC|W3C|CERN|TBL|ENQUIRE)[^\]]{0,300}\]|\b(?:Tim\s+Berners-Lee|WorldWideWeb|HyperText\s+Proposal)\b",
            re.I,
        ),
        # 31. ssr_boundaries: View Horizon. shelf/Serverpod response handlers.
        # BUG FIX: `Router\(\)` ends on `)` -- shared trailing \b never
        # fired. Never matched.
        "ssr_boundaries": re.compile(
            r"\b(?:shelf|dart_frog|Serverpod|Response\.(?:ok|internalServerError)|RequestContext|Handler|Serve|renderHtml)\b"
            r"|Router\(\)",
            re.I,
        ),
        # 32. events: Pub/Sub Network. Stream subscriptions and broadcast observables.
        "events": re.compile(
            r"\b(StreamController|EventBus|Subject|BehaviorSubject|PublishSubject|EventEmitter|BlocProvider|notifyListeners)\b|\.listen\s*\(",
            re.I,
        ),
        # 33. dependency_injection: Inversion of Control. GetIt, Provider, and Injectable markers.
        # BUG FIX: `@injectable` starts with `@` (non-word), so the
        # shared leading \b could only fire when a word char
        # immediately preceded the `@` -- never true for how
        # annotations are actually written. Never matched at all.
        "dependency_injection": re.compile(
            r"\b(?:GetIt\.I|GetIt\.instance|Provider\.of|ConsumerWidget|ref\.watch|ref\.read|Injector)\b|@injectable",
            re.I,
        ),
        # 34. macros: Preprocessor Hooks. Modern macros and JsonSerializable generators.
        "macros": re.compile(
            r"\bmacro\s+class\b|@(?!(?:override|deprecated|required|protected|visibleForTesting|pragma|immutable))[A-Z]\w*Macro\(\)|@JsonSerializable|@freezed",
            re.I,
        ),
        # 35. pointers: Memory Map. dart:ffi bridging to native memory space.
        "pointers": re.compile(
            r"\b(dart:ffi|Pointer<|NativeFunction<|Opaque|ffi\.cast|IntPtr|ffi\.Pointer)\b",
            re.I,
        ),
        # 36. memory_alloc: Manual Memory Management. Allocators bypassing the GC.
        "memory_alloc": re.compile(
            r"\b(ffi\.Allocator|malloc\.allocate|calloc\.allocate|malloc\.free|Arena|using\s*\(\s*\(Arena)\b",
            re.I,
        ),
        # 37. inline_asm: Bare Metal.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics (Structured logs).
        "telemetry": re.compile(
            r"\b(developer\.log|Logger|log|FirebaseCrashlytics|Sentry)\.(?:info|error|warn|severe|debug|trace|recordError)\b|\bdart:developer\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
        "debug_prints": re.compile(r"\b(print|debugPrint)\s*\(", re.I),
        # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit casting.
        "explicit_casts": re.compile(r"\bas\s+[A-Z]\w*|\(\s*[A-Z]\w*\s*\)\s*[a-zA-Z_$]"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting context.
        "panics_and_aborts": re.compile(r"\b(throw|rethrow|exit|exitCode|Process\.killPid)\b", re.I),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits/delays).
        "thread_sleeps": re.compile(r"\b(sleep|delay|setTimeout|setInterval)\s*\(", re.I),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~(?!=|/)"),
        # 44. sync_locks (Resource Management & Stability) Coordinated threading.
        "sync_locks": re.compile(r"\b(Mutex|Lock|synchronized|Semaphore|Completer)\b", re.I),
        # 45. immutability_locks (Immutability Constraints) Immutability.
        # BUG FIX: `@immutable` starts with `@` (non-word), so the
        # shared leading \b could only fire when a word char
        # immediately preceded it -- never true for how annotations are
        # actually written. Never matched at all.
        "immutability_locks": re.compile(r"\b(?:const|final|readonly)\b|@immutable", re.I),
        # 46. cleanup (Resource Cleanup / Teardown) Resource release.
        "cleanup": re.compile(r"\b(dispose|close|cleanup|cancel|drop|free)\s*\(", re.I),
        # 47. encapsulation Scope hiding (Underscore prefix).
        "encapsulation": re.compile(r"\b(_[a-zA-Z0-9_$]+)\b|@protected|@private"),
        # 48. listeners (Event Listeners / Observers) Waiting for state broadcasts.
        # BUG FIX: `on\(` ends on `(` (non-word), so the shared trailing
        # \b could only fire when a word char immediately followed --
        # never true for the common real call shape `on('event', ...)`,
        # where a quote follows the paren.
        "listeners": re.compile(r"\bon\(|\b(?:addEventListener|subscribe|watch|useEffect|listen)\b", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # BUG FIX: `@Ignore` starts with `@` (non-word), so the shared
        # leading \b could only fire when a word char immediately
        # preceded it -- never true for how annotations are actually
        # written. Never matched at all.
        "test_skip": re.compile(r"@Ignore|\b(?:test\.skip|t\.Skip|xit|mock)\b", re.I),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Dart Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(jsonDecode|jsonEncode|json\.decode|json\.encode|Utf8Decoder|Utf8Encoder)\b"
        ),
        "regex_execution": re.compile(r"\b(RegExp\s*\()|\.(hasMatch|allMatches|stringMatch)\b"),
        # BUG FIX: `Duration\s*\(` ends on `(` (non-word), so the shared
        # trailing \b only fired when a word char immediately followed
        # -- true for the common named-argument form (`Duration(seconds:
        # 5)`) but not for the zero-argument form (`Duration()`), where
        # `)` (non-word) follows and the boundary fails.
        "time_date_logic": re.compile(r"\b(?:DateTime\.now|Timer\.run|Timer\.periodic|Stopwatch)\b|\bDuration\s*\("),
        "ipc_rpc_bridges": re.compile(
            r"\b(Isolate\.spawn|ReceivePort|SendPort|Process\.run|Process\.start|HttpClient)\b"
        ),
    },
}
