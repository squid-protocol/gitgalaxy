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
        "target_version": "C# 14 / .NET 10 / Modern ASP.NET Core & Blazor",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, legacy ASP.NET, and build-tooling formats.
    "extensions": [
        ".cs",
        ".csx",
        ".razor",
        ".cshtml",
        ".cake",
        ".linq",
        ".ashx",
        ".asmx",
        ".ascx",
        ".svc",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
    "exact_matches": ["build.cake"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
    "discriminators": [
        ".cs",
        ".csproj",
        ".sln",
        "packages.config",
        "nuget.config",
        "global.json",
        "App.config",
        "Web.config",
        "project.json",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["dotnet-script", "csi"],
    # UPGRADED: Maps to Family 1 (Standard C)
    # Rationale: Uses '//' for line-level literature; multi-line literature
    # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. EXCLUDES throw (bailout_hits).
        # Includes pattern matching (and, or, not) and null-coalescing.
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|foreach|while|do|catch|finally|continue|break|goto|try|yield\s+return|yield\s+break|and|or|not)\b|\?\?|\?\.|(?<=\s)\?(?=\s)"
        ),
        # 2. args (Parameters / Coupling)
        # Parameter blocks for methods, primary constructors, and lambdas.
        "args": re.compile(
            # =====================================================================
            # [ THE GHOST ARGS SHIELD (C#) ]
            # To prevent hallucinating standard function invocations, we demand structural proof.
            # Branch 1: Standard Methods MUST have a return type (e.g., `Task<T> Foo(...)`).
            # Branch 2: Constructors lack return types, so they MUST be anchored to `:` or `{`.
            # Branch 3: Standard fat-arrow lambdas.
            # Upgraded all spaces to `[ \t\n]+` to support Pathological vertical parameters.
            # QUADRATIC BLOWUP FIX: Branch 3's bare-identifier lambda form
            # (`[a-zA-Z_$][\w_$]*` with no \b anchor, unlike Branches 1/2
            # which are `^`-anchored) got retried at every position in a
            # long `=>`-less line, backtracking O(n) per position for
            # O(n^2) total (same bug found and fixed in javascript's args).
            # Bounded to {0,100}; real identifiers don't get that long.
            # =====================================================================
            # #1209: parameter-list span wrapped in its own capture group
            # in all three branches (was only reachable via group(0), the
            # whole match including the attribute/modifier/return-type/
            # name prefix, or for lambdas nothing at all) so detector.py's
            # counter isolates just the real parameter text -- the
            # whole-match fallback overcounted every zero/one-arg
            # signature by +1 the same way Python's did (#1199). Name
            # groups added to branches 1/2 too, purely so existing
            # extraction tests keep passing.
            r"(?:"
            # 1. Standard Methods
            r"^[ \t]*(?:\[[^\]]*\][ \t\n]*){0,5}(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|scoped|readonly)[ \t\n]+){0,5}(?:(?!(?:new|if|for|while|switch|return|yield|delegate|event)\b)(?:[\w<>\[\]?,.*]|\([^()]{0,100}\))+[ \t\n]{1,200}){1,10}(operator[ \t\n]+(?:[+\-*/%&|^~!=<>]+|true|false|[\w_$.]+)|(?!(?:new|if|for|while|switch|return|yield|delegate|event)\b)\w+)(?:[ \t\n]*<[^>]{0,100}>)?[ \t\n]*(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))|"
            # 2. Constructors
            r"^[ \t]*(?:(?:public|private|protected|internal|static|unsafe)[ \t\n]+)?([A-Z]\w*)(?:[ \t\n]*<[^>]{0,100}>)?[ \t\n]*(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))[ \t\n]*(?::[ \t\n]*(?:base|this)|[{])|"
            # 3. Lambdas
            r"(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)|[a-zA-Z_$][\w_$]{0,100})[ \t\n]*=>"
            r")",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const/readonly (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(var|return|class|interface|struct|record|enum|using|namespace|yield|await|delegate|event|init|required|field|implements|extends|declare)\b|=>"
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks. EXCLUDES types/classes.
        #
        # =====================================================================
        # [ CONTEXT: C# "IRON WALL" FUNCTION EXTRACTOR & REDOS SHIELD ]
        # PURPOSE: Anchors executable logic blocks (methods) in C# up to C# 14.
        # VULNERABILITY: C# allows massive return types (e.g., nested tuples),
        #   generics, and explicit interface implementations. If spaces are allowed
        #   freely inside unbounded quantifiers, massive Roslyn test strings cause
        #   Catastrophic Backtracking, locking the Python GIL at the C-level.
        # THE FIX: Strict character exclusion, numeric bounding, and mutual
        #   exclusivity between word characters and spaces.
        #
        # [ THE VERTICAL IRON WALL UPDATE ] (Hard-learned from Pathological Fuzzer):
        #   Developers often place attributes, modifiers, return types, and names
        #   on completely separate lines. We replaced horizontal spaces `[ \t]+`
        #   with strictly bounded multi-line spaces `[ \t\n]+`. We EXPLICITLY DO NOT
        #   use `\s+` because unbounded wildcards with newlines trigger ReDoS.
        # =====================================================================
        "func_start": re.compile(
            # 1. THE HORIZONTAL ANCHOR & ATTRIBUTE SHIELD
            # Anchors to the line start. Steps over C# attributes [Obsolete], [Fact], etc.
            # [REDOS ARMOR]: `[^\]]{0,250}` prevents a missing closing bracket from spiraling
            # across the entire file. `{0,5}` caps the max number of stacked attributes.
            # [VERTICAL FIX]: `[ \t\n]*` allows attributes to sit on lines above the function.
            r"^[ \t]*(?:\[[^\]]{0,250}\][ \t\n]*){0,5}"
            # =====================================================================
            # [THE INSTANTIATION SHIELD]: AST-FREE HALLUCINATION PREVENTION
            # If an object instantiation `new TargetFunc()` is poorly indented against
            # the left margin, the engine will hallucinate it as a constructor definition
            # (because constructors naturally lack return types).
            # FIX: Forcefully abort matching if the sequence begins with the 'new' keyword
            # followed immediately by an identifier and an opening parenthesis.
            # =====================================================================
            r"(?!new[ \t\n]+[@A-Za-z_$][\w_$.]*(?:<[^>]{0,100}>)?[ \t\n]*\()"
            r"(?:"
            # 2. MODIFIERS (Linkage, Storage, & Access)
            # Matches `public async`, `protected internal static`, etc.
            # [VERTICAL FIX]: `[ \t\n]+` allows modifiers to wrap across newlines.
            r"(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|readonly)[ \t\n]+){1,5}"
            # 3. THE "IRON WALL" RETURN TYPE
            # Safely captures complex modern C# return types before the function name.
            # Supports: standard types `int`, arrays `int[]`, generics `List<T>`,
            # namespaces `System.Threading.Tasks.Task`, tuples `(int, string)`, and nullables `string?`.
            # [REDOS ARMOR 1]: `(?![ \t]*#)` prevents the engine from crossing into a #region or #if block.
            # [REDOS ARMOR 2]: The character class `[...]+` STRICTLY FORBIDS spaces/tabs. The `[ \t\n]+`
            # follows it outside the group. This mutual exclusivity guarantees O(N) parsing.
            # [REDOS ARMOR 3]: Explicitly prevents return types from eating modifiers during a backtrack,
            # sealing the overlapping permutation leak that caused Catastrophic Backtracking.
            # BUG FIX (Rule 14): this loop's trailing `[ \t\n]+` and the
            # final `[ \t\n]*\(` before the opening paren (item 5 below)
            # are two effectively-adjacent unbounded whitespace
            # quantifiers -- once a real method never follows (no `(`
            # anywhere), the engine must retry every possible split of
            # the same trailing whitespace run across both gaps, O(n^2).
            # Confirmed ~4x/doubling, 1.5s at n=32000 on a bare
            # `"int foo" + " "*n` payload. Bounded both to `{1,200}`/
            # `{0,200}`, same fix shape already applied in cpp.
            # #1314: this per-token exclusion only banned MODIFIER keywords, so a statement
            # header preceding a call expression -- `foreach (var x in someList.Method())`,
            # `for (...)`, `using (...)` -- could get silently swallowed token-by-token as
            # fake "return type" tokens, letting the walk land on the call's own receiver+
            # method (e.g. `someList.Method`) as if it were a real function name (group 1's
            # `[\w_$.]*` already permits dots, meant for explicit interface implementations
            # like `IFoo.DoWork`, but that also legalizes `receiver.Method` as a shape).
            # Added the same statement/control-flow keyword set item 4 already excludes at
            # the FINAL identifier position, plus the contextual keywords item 4 also gained
            # below (`var`/`in`/`when`/`or`/`and`/`not`/`is`) since those can equally start a
            # parenthesized non-function construct (`var (a, b) = ...`, `... in expr(...)`)
            # mid-walk, not just at position zero. Confirmed via language-crucible/data/
            # csharp/roslyn/{CSharpCompilation,Workspace}.cs (real, mainstream Roslyn source).
            # #2054: (1) a bare comma in this token class let the walk absorb comma-separated
            # CALL ARGUMENTS (`ref mdName,`/`SpecialType.None,` inside a multi-line call) as if
            # they were return-type tokens, landing on the call's own target identifier as a
            # phantom function name. A real return type never has a bare top-level comma outside
            # a tuple's own parens, a generic's own angle brackets, or an array's own brackets --
            # moved comma-tolerance into explicit `<...>`/`[...]` single-token alternatives
            # (tuple commas already had `\([^()]{0,80}\)`) instead of allowing it bare. Confirmed
            # via a full corpus diff this also retroactively closes ~190 previously-unknown
            # phantom occurrences of the identical shape (`this.EatToken`, `this.ParseXxx`,
            # `_syntaxFactory.Xxx`, etc. -- every one confirmed to have zero real declaration
            # anywhere in the file, only call sites) that were never in scope for #1314/#2035's
            # own fixes but shared this exact root cause.
            # (2) `(?!\?)` at each token's start rejects a token beginning with `?` -- closes a
            # ternary operator (`\n ? expr`) being consumed as if it were a nullable-type marker
            # (`string?`, where the `?` never STARTS a token, it ends the preceding one).
            # The `<...>` alternative itself tolerates ONE level of nesting inside the outer
            # angle brackets (mirrors the pre-existing groovy pattern at this file's Java/Groovy
            # rule) -- needed for real multi-generic return types like `ImmutableSegmentedDictionary
            # <ReadOnlyMemory<byte>, OneOrMany<SyntaxTree>>` (roslyn/CSharpCompilation.cs), which a
            # flat `<[^>]{0,100}>` can't span since it stops at the FIRST inner `>`. Bounded to 5
            # nested pairs per outer token -- 3+ levels of nesting (`List<Foo<Bar<Baz>>>`) is a
            # real, accepted gap, not attempted, since it wasn't found in the corpus.
            r"(?:(?![ \t]*#)(?!(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|readonly|delegate|event|if|for|foreach|while|switch|catch|using|lock|return|class|interface|struct|record|enum|yield|throw|await|sizeof|typeof|nameof|var|in|when|or|and|not|is)\b)(?!\?)(?:[a-zA-Z0-9_<>\[\]?.*]|\([^()]{0,80}\)|<[^<>]{0,100}(?:<[^<>]{0,100}>[^<>]{0,100}){0,5}>|\[[^\]]{0,80}\])+[ \t\n]{1,200}){0,10}"
            # 4. THE "NOT A FUNCTION" SHIELD
            # Negative lookahead ensuring we don't accidentally capture control flow,
            # primitive type keywords, or object instantiations as function names.
            # #1314: also excludes the contextual keywords that can directly precede a `(` in
            # non-function constructs -- `static (args) => ...` (a static lambda, C# 9+),
            # `var (a, b) = Method(...)` (tuple deconstruction), `catch (Ex e) when (...)`
            # (exception filter), and the pattern-combinator keywords `or`/`and`/`not`/`is`
            # (`x is Foo or Bar`, C# 9+ pattern matching) -- each of which was previously
            # captured whole as a phantom function literally named "static"/"var"/"when"/"or"
            # etc. when no preceding modifier/type tokens were consumed. Confirmed via the
            # same Roslyn corpus files as item 3's fix above.
            r"(?!(?:if|for|foreach|while|switch|catch|using|lock|new|return|class|interface|struct|record|enum|yield|throw|await|sizeof|typeof|nameof|delegate|event|var|in|when|or|and|not|is|static)\b)"
            # 5. THE IDENTIFIER CAPTURE (GROUP 1) & GENERIC STEPPER
            # Captures the actual satellite name:
            # - `[@A-Za-z_$]` supports C# verbatim identifiers (e.g., `@class`).
            # - `[\w_$.]*` supports explicit interface implementations (e.g., `IMyInterface.DoWork`).
            # - `(?:[ \t\n]*<[^>]{0,100}>)?` safely steps over method-level generic definitions
            #   like `<T, U>` BEFORE hitting the opening parenthesis.
            # [VERTICAL FIX]: Removed `\n` exclusion from the generic stepper to support multi-line generics.
            r"((?:operator[ \t\n]+(?:[+\-*/%&|^~!=<>]+|true|false|[\w_$.]+)|[@A-Za-z_$][\w_$.]*))(?:[ \t\n]*<[^>]{0,100}>)?[ \t\n]{0,200}\("
            r"|"
            # Branch B: Has return type (no modifier)
            r"(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|readonly)[ \t\n]+){0,5}"
            # #2054: same fix as Branch A's identical token loop above -- see its comment for
            # full rationale (bare comma let call-argument lists be absorbed as return-type
            # tokens; `(?!\?)` closes a ternary `?` being consumed as a nullable-type marker).
            r"(?:(?![ \t]*#)(?!(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|readonly|delegate|event|if|for|foreach|while|switch|catch|using|lock|return|class|interface|struct|record|enum|yield|throw|await|sizeof|typeof|nameof|var|in|when|or|and|not|is)\b)(?!\?)(?:[a-zA-Z0-9_<>\[\]?.*]|\([^()]{0,80}\)|<[^<>]{0,100}(?:<[^<>]{0,100}>[^<>]{0,100}){0,5}>|\[[^\]]{0,80}\])+[ \t\n]{1,200}){1,10}"
            r"(?!(?:if|for|foreach|while|switch|catch|using|lock|new|return|class|interface|struct|record|enum|yield|throw|await|sizeof|typeof|nameof|delegate|event|var|in|when|or|and|not|is|static)\b)"
            r"((?:operator[ \t\n]+(?:[+\-*/%&|^~!=<>]+|true|false|[\w_$.]+)|[@A-Za-z_$][\w_$.]*))(?:[ \t\n]*<[^>]{0,100}>)?[ \t\n]{0,200}\("
            r"|"
            # Branch C: Zero-prefix (No modifier, No return type)
            # #1418: The zero-prefix branch matches ordinary multi-line bare call statements if their
            # argument list spans multiple lines and ends in a bare ';' with no '{'. We apply an
            # "Invocation Shield" (similar to dart #1221 / rust #1319 / csharp's own args shield) to
            # only allow the bare-';' tolerance on branches that matched a modifier or return type
            # (which a real abstract/interface method declaration has). For this zero-prefix path, we
            # require the signature to actually open a block (`{` or `=>`).
            r"(?!(?:if|for|foreach|while|switch|catch|using|lock|new|return|class|interface|struct|record|enum|yield|throw|await|sizeof|typeof|nameof|delegate|event|var|in|when|or|and|not|is|static)\b)"
            r"((?:operator[ \t\n]+(?:[+\-*/%&|^~!=<>]+|true|false|[\w_$.]+)|[@A-Za-z_$][\w_$.]*))(?:[ \t\n]*<[^>]{0,100}>)?[ \t\n]{0,200}\("
            r"(?=[ \t\n]*(?:[^)]|\([^)]*\))*[ \t\n]*\)[ \t\n]*(?:\{|=>))"
            r")",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # RULE 11 FIX (epic #813/#820): there was no generic-parameter step-over between the
        # class/interface/etc. name and the base-list `:` check, so ANY generic type with a base
        # list (`class Foo<T> : Base<T> {`, extremely common) left the class's own `<...>`
        # unconsumed right before `:`, silently losing the entire base-list capture (group 2)
        # even though the name (group 1) still matched fine -- same failure shape as java's
        # #816 class_start bug. Also added a primary-constructor parameter-list step-over
        # (`record Foo<T>(T Value) : Base<T>`, C# 9+ records / C# 12 primary constructors on
        # classes/structs, mainstream and common) for the same reason -- the `(...)` between the
        # generics and the `:` was equally unconsumed.
        # #1708: modifier alternation was missing `readonly`/`ref` -- C# 7.2+
        # `readonly struct`, `ref struct`, and `readonly ref struct` declarations
        # (mainstream in modern codebases, e.g. Roslyn's own parser) structurally failed to
        # match, a pure class_recall gap. Verified via roslyn/CSharpCompilation.cs
        # (`readonly struct ImportInfo`) and roslyn/LanguageParser.cs
        # (`readonly ref struct ParserSyntaxContextResetter`): found_classes 22 -> 24,
        # class recall 91.7% -> 100%, zero precision cost (extra_classes still 0).
        "class_start": re.compile(
            r"^[ \t]*(?:\[[^\]]*\][ \t]*){0,5}(?:(?:public|internal|private|protected|static|sealed|abstract|partial|file|unsafe|new|readonly|ref)[ \t]+){0,5}(?:class|interface|struct|record(?:[ \t]+(?:struct|class))?|enum)\s+([A-Za-z_$][\w_$]*)(?:\s*<(?:[^<>]|<[^<>]*>)*>)?(?:\s*\((?:[^()]|\([^()]*\))*\))?(?:\s*:\s*([A-Za-z_$][\w_$, \t<>\?]*))?",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(try|catch|finally|checked|is|as|nameof|required|ArgumentNullException|ThrowIfNull|ThrowIfNullOrWhiteSpace)\b|\[(?:Required|NotNull|Authorize)\]|\?\?|\?\."
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Null-forgiving operator, dynamic, and unsafe bypasses.
        "safety_bypasses": re.compile(r"!\.|\bnull!|#pragma\s+warning\s+disable|\.Result\b|\.Wait\(\)|\b(dynamic)\b"),
        # 8. danger (High-Risk Execution / System Calls)
        # Extreme tech debt/vulnerabilities. EXCLUDES TODO (debt) and Console (print).
        "high_risk_execution": re.compile(
            r"\b(Thread\.Abort|Process\.Start|Environment\.FailFast|Environment\.Exit|goto)\b"
        ),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(File|Directory|Stream|HttpClient|Path|SqlConnection|SqlCommand|DbContext|DbSet|HttpRequest|HttpResponse)\b\.|\[Table\("
        ),
        # 10. api (Public Surface Area)
        # Public exposure surface. Explicit visibility + Controller mapping.
        "api": re.compile(
            r"\b(public|internal)\b|\[(?:HttpGet|HttpPost|HttpPut|HttpDelete|Route|ApiController|HubMethodName)\]|\bapp\.Map(?:Get|Post|Put|Delete|Group)\b"
        ),
        # 11. flux (State Mutation)
        # Mutation of state. EXCLUDES const/readonly (freeze_hits).
        # BUG FIX (Rule 13): `^[ \t]*(?:this\.)?\w+[ \t]*=` requires
        # `re.M` for the `^` to anchor per-line -- without it, `^` only
        # matches true string-start, so this alternative (the plain
        # `field = value;` assignment form, arguably the most common
        # state-mutation shape in any real C# file) could only ever
        # fire if the assignment happened to be the first line of the
        # entire scanned content.
        "state_mutation": re.compile(
            r"\b(set|field)\s*[{;]|volatile|ref\s|out\s|^[ \t]*(?:this\.)?\w+[ \t]*=|(?:\w+\.)?(?:Add|Remove|Clear|Insert|Push|Pop|Update)\s*\(",
            re.M,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # BUG FIX (Rule 12): only checked `//` line comments, entirely
        # missing `/* */` block comments despite csharp being a
        # `standard_block` language where both styles are equally
        # idiomatic (`/* if (x) foo(); */`).
        "dead_code": re.compile(
            r"(?://|/\*)[ \t]*(?:public|private|protected|internal|class|void|if|for|foreach|while|return|using)\b"
        ),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"///|///\s*<summary>|///\s*<param|///\s*<returns>|///\s*<remarks>"),
        # 14. test (Testing & Assertions)
        # BUG FIX: `Should\(\)` (FluentAssertions) ends on `)`
        # (non-word), so the shared trailing \b could never fire --
        # the fluent form is always immediately chained with another
        # `.method(...)`, never followed by a word character. Never
        # matched.
        "test": re.compile(
            r"\[(?:Test|Fact|Theory|TestMethod|TestClass|SetUp|TearDown)\]"
            r"|\b(?:Assert\.|Mock\.|Substitute\.For)\b|Should\(\)"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(async|await|Task|ValueTask|Thread|Parallel|SemaphoreSlim|Mutex|Channel|IAsyncEnumerable|Interlocked)\b"
        ),
        # 16. ui_framework (UI / View Components)
        "ui_framework": re.compile(
            r"\b(ControllerBase|IActionResult|Binding|ObservableCollection|DependencyProperty|ComponentBase|RenderFragment|MonoBehaviour)\b"
        ),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(r"=>|delegate[ \t]*\{"),
        # 18. globals (Global / Shared State)
        # BUG FIX (Rule 9): the `public static ... = ` alternative ends
        # in `=` (non-word) but shared a trailing `\b` with word-ending
        # siblings -- only fired when the assignment had zero
        # whitespace around `=` (`X=5;`), breaking on the idiomatic
        # spaced form (`MAX_VALUE = 100;`) that's the dominant real C#
        # style.
        "globals": re.compile(
            r"\b(?:ConfigurationManager|AsyncLocal)\b|\bEnvironment\.|"
            r"\bpublic\s+static\s+(?:readonly[ \t]+)?[\w<>]+\s+[A-Z_0-9]+[ \t]*=|\[ThreadStatic\]"
        ),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"^[ \t]*\[[A-Za-z_][^\]]*\]", re.M),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(r"<\s*[A-Z][^>]*>|\bwhere\s+\w+\s*:"),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(
            r"\.(?:Select|Where|OrderBy|GroupBy|Aggregate|Any|All|ToList|ToArray|SelectMany)\(|^[ \t]*from\s+\w+\s+in\s+",
            re.M,
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(Math\.|MathF\.|Vector[234]|Matrix4x4|Random|Complex|Tensor|TensorPrimitives)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Reflection and dynamic Emit.
        "reflection_metaprogramming": re.compile(
            r"\b(System\.Reflection|DllImport|LibraryImport|MethodInfo|Activator|Marshal\.|Emit|ILGenerator)\b"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"^[ \t]*(?:global[ \t]+)?using\s+(?:static[ \t]+)?[\w.]+;", re.M),
        # ALIAS DIRECTIVE FIX (epic #813/#820): `using Alias = Target.Namespace;` (a using-alias
        # directive, common for shortening long generic types or disambiguating identical type
        # names from different namespaces) didn't match AT ALL -- there was no allowance for the
        # `IDENT =` prefix before the actual target, so the whole statement produced zero
        # dependency-graph edges. Added an optional alias-prefix skip-over so the capture lands
        # on the real target (`Target.Namespace`), not the local alias name. Also added an
        # optional generic-suffix step-over after the target capture: an alias directive's
        # target is very commonly a CLOSED generic type (`using StringList =
        # System.Collections.Generic.List<string>;` -- the primary real-world reason alias
        # directives exist, to shorten long generics), and the required trailing `;` check
        # failed on the unconsumed `<...>` without it.
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:global[ \t\n]+)?using[ \t\n]+(?:static[ \t\n]+)?(?:[\w]+[ \t\n]*=[ \t\n]*)?([\w.]+)(?:[ \t\n]*<(?:[^<>]|<[^<>]*>)*>)?[ \t\n]*;",
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"(?:<author>|Author:|Created by)\s*(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # BUG FIX (Rule 14): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust,
        # c, and cpp earlier in this epic (the 10th hit). Bounded both
        # quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (The Blazor/Razor Horizon)
        "ssr_boundaries": re.compile(
            r"@(?:page|rendermode|code|layout)|\[(?:Route|CascadingParameter)\]|\b(RenderFragment|ComponentBase|IViewComponentResult)\b"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # BUG FIX: `+=`/`-=` (event subscribe/unsubscribe operators) used
        # to be inside the \b(...)\b wrapper. \b requires a word/non-word
        # transition; since neither `+`/`=` nor `-`/`=` is a word
        # character, `\b+=\s*\b` could only match with no surrounding
        # whitespace at either edge (e.g. "x+=y"), never idiomatic C#
        # like "MyEvent += handler" (spaced on both sides). Split out
        # unguarded, same fix shape as #621's dash/hash families.
        "events": re.compile(
            r"\b(event\s+[\w<>]+\s+\w+|EventHandler|Invoke|Raise|MediatR|INotification|IRequest|Publish)\b|\+=\s*|-=\s*"
        ),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(
            r"\b(IServiceCollection|AddTransient|AddScoped|AddSingleton|AddKeyed|\[Inject\]|FromServices|IServiceProvider)\b"
        ),
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(
            r"^[ \t]*#(?:define|undef|if|elif|else|endif|region|endregion|pragma|warning|error)\b",
            re.M,
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Native pointers and modern memory structures (Span/Memory).
        "pointers": re.compile(r"\b(?:fixed|stackalloc|Unsafe\.AsPointer|IntPtr|UIntPtr|nint|nuint)\b|->"),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(
            r"\b(Marshal\.AllocHGlobal|GC\.AllocateArray|MemoryPool|ArrayPool<[^>]*>\.Shared\.Rent|ref\s+struct|scoped\s+ref)\b"
        ),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(?:ILogger|_logger|Log|TelemetryClient|ActivitySource)\.(?:LogInformation|LogError|LogWarning|LogDebug|StartActivity|TrackEvent)\b|\[LoggerMessage"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
        "debug_prints": re.compile(r"\b(Console\.(?:Write|WriteLine|Error)|Debug\.(?:Write|WriteLine|Print))\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            r"\bas\s+[A-Z]\w*|\(\s*(?:int|long|short|byte|char|float|double|decimal|bool|string|[A-Z][A-Za-z0-9_]*)\s*\)\s*[a-zA-Z_$]"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|abort|FailFast|Environment\.Exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        # BUG FIX: `Wait\(\)` ends on `)` (non-word), so the shared
        # trailing \b could never fire (`task.Wait();` -- the next
        # char is always `;`, a newline, or another `.method`, never a
        # word character). Never matched.
        "thread_sleeps": re.compile(r"\b(?:sleep|delay|Task\.Delay|Thread\.Sleep)\b|\bWait\(\)"),
        # 43. bitwise_ops (Bitwise Operations)
        # Low-level byte manipulation. Safely maps to C# bitwise operators without overlapping language-specific pipelines.
        "bitwise_ops": re.compile(r"<<|>>|\^|~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(
            r"\b(mutex|lock|Monitor|Semaphore|Interlocked|SpinLock|ReaderWriterLockSlim)\b",
            re.I,
        ),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(const|readonly|init|Immutable[A-Z]\w*)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        # BUG FIX (grammar mismatch): this was entirely case-sensitive
        # and only matched lowercase `dispose(`/`close(`/etc -- but
        # idiomatic C# always PascalCases public members
        # (`.Dispose()`, `.Close()`), so the realistic form never
        # matched at all; only a non-idiomatic lowercase call would.
        "cleanup": re.compile(r"\b(dispose|close|free|delete|GC\.Collect|GC\.SuppressFinalize)\b\s*\(", re.I),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        "encapsulation": re.compile(r"\b(private|protected|internal|file)\b"),
        # 48. listeners (Event Listeners / Observers)
        # BUG FIX (grammar mismatch): case-sensitive lowercase
        # `subscribe`/`on` never matched idiomatic C# PascalCase
        # (Rx.NET's `.Subscribe(...)`, SignalR's `.On<T>(...)`) --
        # same shape as the `cleanup` fix above.
        "listeners": re.compile(r"\b(on|addEventListener|subscribe|EventHandler)\b|\+=", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # BUG FIX (real coverage gap): missing xUnit's `[Fact(Skip =
        # "...")]` / `[Theory(Skip = "...")]` form entirely -- the
        # dominant real xUnit skip idiom (NUnit/MSTest use a standalone
        # `[Ignore]` attribute instead, which was already covered).
        "test_skip": re.compile(
            r"\[(?:Ignore|Skipped)\]|\[(?:Fact|Theory)\([^)]*Skip\s*=|test\.skip\(|mock\(|stub\(|Substitute\.For"
        ),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (C# Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(JsonSerializer\.Deserialize|JsonConvert\.DeserializeObject|XmlSerializer|BinaryFormatter)\b"
        ),
        "regex_execution": re.compile(r"\b(Regex\.Match(?:es)?|Regex\.Replace|Regex\.IsMatch|new\s+Regex)\b"),
        "time_date_logic": re.compile(
            r"\b(DateTime\.Now|DateTime\.UtcNow|DateTimeOffset|TimeSpan|Stopwatch\.StartNew)\b"
        ),
        "ipc_rpc_bridges": re.compile(r"\b(Process\.Start|NamedPipeServerStream|ChannelFactory|GrpcChannel)\b"),
    },
}
