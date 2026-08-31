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
        "target_version": "C++23 (Modules, Concepts, Coroutines, Ranges, std::print)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard sources, headers, template implementations, inline implementations, and legacy UNIX casing conventions.
    "extensions": [
        ".cpp",
        ".cc",
        ".cxx",
        ".c++",
        ".hpp",
        ".hh",
        ".hxx",
        ".h++",
        ".tpp",
        ".inc",
        ".inl",
        ".ipp",
        ".cp",
        ".C",
        ".H",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files (like .h or .inc).
    "discriminators": [
        ".cpp",
        ".cc",
        ".cxx",
        "CMakeLists.txt",
        "conanfile.txt",
        "vcpkg.json",
        "Makefile",
        "BUILD.bazel",
        "WORKSPACE",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["cling", "cint"],
    # UPGRADED: Maps to Family 1 (Standard C)
    # Rationale: Uses '//' for line-level literature; multi-line literature
    # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
    "lexical_family": "standard_block",
    "rules": {
        # 1. branch (Control Flow / Branching)
        # Control flow jumps. Includes modern coroutine jumps (co_yield, co_await).
        # EXCLUDES exceptions (bailout_hits).
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|while|do|catch|break|continue|goto|co_yield|co_await)\b|&&|\|\||\?"
        ),
        # 2. args (Parameters / Coupling)
        # Parameter blocks of functions and lambdas. Bounded to prevent ReDoS on massive signatures.
        # OUT-OF-LINE OPERATOR + RULE 11 FIX (epic #813/#821): same gaps as func_start -- no
        # allowance for a class-qualified operator name (`TargetClass::operator=`) at all, and
        # the method's own template-argument step-over was the flat `<[^>]*>`, breaking a
        # nested type arg (`Foo::Bar<Baz<int>>(...)`, an explicit template specialization).
        # #1209: parameter-list span wrapped in its own capture group (was
        # only ever reachable via group(0), the whole match including the
        # name/template/return-type-keyword prefix) so detector.py's
        # counter isolates just "(...)" -- the whole-match fallback
        # overcounted every zero/one-arg signature by +1 the same way
        # Python's did (#1199), including a genuinely empty lambda
        # `[]()`. A name group (group 1) is added too, ahead of the
        # args-list groups, purely so the existing extraction tests
        # (which check the captured name) keep passing -- detector.py
        # already picks the highest-numbered participating group via
        # `lastindex`, so it still resolves to the args group either way.
        # #1883: the first-parameter type gate also accepts leading-underscore
        # Windows SAL annotation macros (`_In_`, `_Out_`, `_Inout_`,
        # `_In_opt_`, `_In_reads_(n)`, ...) as an optional, repeatable prefix
        # ahead of the real type, the same way `const`/`volatile` already are
        # -- a real SAL-annotated signature (`f(_In_ int nCode, ...)`)
        # otherwise failed the whole `search()` because `_In_` matched none
        # of the type alternatives. `_[A-Z][A-Za-z0-9_]*_` (required trailing
        # `_`, uppercase first letter) is narrow enough not to catch `_t`
        # types or `__attribute__`/`__cdecl`; the `\([^()]{0,64}\)` tail
        # covers the sized forms.
        "args": re.compile(
            r"\b(?!(?:if|for|while|switch|catch)\b)((?:[a-zA-Z_]\w*::)*(?:[a-zA-Z_]\w*|operator[ \t]*[^a-zA-Z_\s(]+|operator[ \t]+(?:new|delete)(?:\[\])?))(?:<(?:[^<>]|<[^<>]*>)*>)?\s*(\(\s*(?:(?:const|volatile|_[A-Z][A-Za-z0-9_]*_(?:\([^()]{0,64}\))?)\s+)*(?:int|char|void|float|double|bool|long|short|unsigned|signed|struct|class|auto|std::|[A-Z]\w*|[a-z_]\w*_t)\b[^)]*\))|\[[^\]]*\]\s*(\([^)]*\))"
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(namespace|using|class|struct|enum|union|template|typename|concept|requires|auto|return|void|inline|virtual|explicit|friend|module|export|import|typedef)\b"
        ),
        "func_start": re.compile(
            # =====================================================================
            # [ CONTEXT: C++ FUNCTION AST EXTRACTOR & REDOS SHIELD]
            # PURPOSE: Anchors executable logic blocks (methods/functions) in C++.
            # VULNERABILITY: C++ allows multi-line function signatures and complex
            #   return types (e.g., `std::vector<int> \n myFunc()`). In files with
            #   massive macro lists (like hardware register maps), the `[ \t\n]+`
            #   allowances cause catastrophic backtracking (ReDoS).
            # THE "IRON WALL" FIX: `(?![ \t]*#)` is a negative lookahead injected at
            #   high-risk multi-line boundaries. It explicitly forbids the regex engine
            #   from crossing into preprocessor directives, capping the permutation tree.
            # =====================================================================
            r"^[ \t]*"
            # BUG FIX (false-positive correctness): the return-type loop
            # (item 4) never excluded control-flow keywords from being
            # consumed as a generic return-type word -- only the later
            # identifier-capture shield (item 5) excluded them from
            # being the FUNCTION NAME itself. This let a two-word
            # control-flow form slip through: `if constexpr (x) {}`
            # falsely matched with "constexpr" captured as the function
            # name ("if" consumed by the loop, "constexpr" landing in
            # the identifier position, which the shield doesn't reject).
            # Rejects any line starting with one of these keywords
            # outright, before the loop even starts.
            r"(?!(?:if|for|while|switch|catch|else)\b)"
            r"(?:template[ \t\n]*<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>[ \t\n]*)?"
            # 2. LINKAGE & STORAGE MODIFIERS (Now supports vertical formatting)
            r"(?:(?:static|inline|extern|virtual|_Noreturn|constexpr|consteval|constinit|__inline__|__forceinline)[ \t\n]+){0,5}"
            # 3. COMPILER ATTRIBUTES PRE-TYPE (Includes C23 [[...]])
            # #2460: also a SAL / entry-point annotation macro -- a `__`- or
            # `_Uppercase`-prefixed identifier optionally taking a bracketed
            # argument (`__control_entrypoint(DllExport)`, `_Ret_maybenull_`,
            # `_Check_return_`). Bounded to that naming shape so it can't eat
            # an ordinary lowercase function call as a phantom prefix.
            r"(?:(?:__attribute__[ \t]*\((?:[^)(]|\([^)]*\))*\)|\[\[[^\]]*\]\]|__declspec[ \t]*\([^)]*\)|(?:__[a-z]\w*|_[A-Z][A-Za-z0-9]*_)(?:[ \t]*\((?:[^)(]|\([^)]*\))*\))?)[ \t\n]*){0,5}"
            # 4. THE RETURN TYPE (Pointers/references explicitly bound)
            # [IRON WALL]: Prevents the engine from reading a `#define` on the next line as a return type.
            # [POINTER AMBIGUITY FIX]: Strictly enforces sequential evaluation of pointers and spaces.
            r"(?:(?:struct|union|enum)[ \t\n]+)?"
            # BUG FIX (Rule 11): the return-type's flat `<[^>]*>` broke
            # on any nested template argument (`std::vector<std::pair<
            # int,int>>`, `std::map<K, std::vector<V>>`) -- extremely
            # common in real C++ -- causing the whole rule to never
            # match at all (no fallback path exists once the return
            # type fails to consume correctly). Extended to a bounded
            # 2-level nesting tolerance.
            # BUG FIX (Rule 14): this loop's trailing `[ \t\n]+` and the
            # parameter block's leading `[ \t\n]*` (item 7 below) are
            # two effectively-adjacent unbounded whitespace quantifiers
            # -- once a real function never follows (no `(` anywhere),
            # the engine must retry every possible split of the same
            # trailing whitespace run across both gaps, O(n^2).
            # Confirmed ~4x/doubling, 2.8s at n=32000 on a bare
            # `"int foo" + " "*n` payload. Bounded both to `{1,200}`.
            # BUG FIX (#1263): `[*&]*[ \t\n]{1,200}` demanded the pointer/
            # reference symbol sit glued to the type with MANDATORY
            # trailing whitespace before the name -- matching only the
            # `Type* name()` style. Real-world C++ (including large chunks
            # of the language-crucible corpus, e.g. Godot's `Type
            # *name()` / `Type * name()`) overwhelmingly puts the space
            # BEFORE the star instead, with the star landing glued to the
            # name (no trailing whitespace at all left to consume) --
            # that shape couldn't complete this loop iteration, so the
            # entire rule failed to match and the whole function
            # definition was invisible, not just misclassified. Split
            # into two bounded alternatives: one or more pointer/
            # reference symbols (with optional bounded whitespace on
            # EITHER side of the run, covering `Type*name`, `Type* name`,
            # `Type *name`, and `Type * name` alike), or -- when no
            # pointer/reference symbol is present at all -- the original
            # mandatory whitespace run (still the only valid separator
            # between two bare words like `void foo`). The two
            # alternatives never both match the same span (one requires a
            # literal `[*&]`, the other forbids consuming past the first
            # non-whitespace char), so this doesn't reopen the Rule 14
            # backtracking gap the surrounding bounds were built to close.
            r"(?:(?![ \t]*#)(?!(?:[a-zA-Z_]\w*::)*operator\b)[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*"
            r"(?:<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>)?"
            r"(?:[ \t]{0,20}[*&]{1,5}[ \t\n]{0,200}|[ \t\n]{1,200})){0,5}"
            # 5. THE "NOT A FUNCTION" SHIELD
            # Prevents control flow (if, while) and primitive types from being captured as function names.
            r"(?!(?:if|for|while|switch|return|catch|else|elif|sizeof|new|delete|ARGS\d+|NOARGS|int|float|double|char|void|long|short|unsigned|signed|bool|INTEGER|LOGICAL|real|__attribute__|__declspec|__asm__)\b)"
            # 6. THE IDENTIFIER CAPTURE (FUNCTION IDENTIFIER - GROUP 1)
            # [IRON WALL]: Ensures the actual function/operator name isn't hijacked by a macro definition.
            # OUT-OF-LINE OPERATOR FIX (epic #813/#821): the operator alternatives had no
            # allowance for a preceding class-qualifier (`TargetClass::operator=`, `TargetClass::
            # operator==`), unlike the plain-identifier alternative which already supports
            # `(?:[a-zA-Z_]\w*::)*`. Out-of-line operator overload definitions (defined in a
            # .cpp file, declared in the header) are mainstream, common C++ -- completely
            # invisible to func_start before this fix.
            r"(?![ \t]*#)((?:[a-zA-Z_]\w*::)*operator[ \t]*\(\)|(?:[a-zA-Z_]\w*::)*operator[ \t]+(?:::)?[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*(?:<(?:[^<>]|<[^<>]*>)*>)?(?:[ \t]*[*&]+)?|(?:[a-zA-Z_]\w*::)*operator[ \t]*[^a-zA-Z_\s(]+|(?:[a-zA-Z_]\w*::)*operator[ \t]+(?:new|delete)(?:\[\])?|(?:[a-zA-Z_]\w*::)*[~a-zA-Z_]\w*)"
            # 7. THE PARAMETER BLOCK (Supports vertical gap)
            # [NESTED PARENTHESIS FIX]: Uses 1-Level Nesting Trick to swallow function pointers without ReDoS.
            # [LAMBDA-ARGUMENT SHIELD] (#2013): a lambda passed as a constructor argument or
            # member-initializer-list entry (`m_draggingState([this]() { ... }),`,
            # `std::thread([...]() { ... }).detach();`) balances its own parens just fine, but
            # nothing AFTER the closing `)` distinguishes "this was a real function's own
            # parameter list" from "this was a call passing a lambda" -- the very next
            # non-whitespace token legitimately IS `{` either way (a real function body, or,
            # for the initializer-list case, the ENCLOSING constructor's own body), so stage 10
            # can't tell them apart. The one reliable, local signal: a real C++ parameter list
            # can never syntactically START with a bare `[` -- only a lambda's capture-list
            # does that (`[this]`, `[=]`, `[&x]`, `[]`); the sole exception is a parameter-level
            # `[[attribute]]`, which always has a literal DOUBLE bracket. Confirmed via direct
            # testing: FancyZones.cpp's `m_draggingState`/`std::thread` false positives are both
            # this exact shape, and every `[[attribute]] Type param` case in the existing
            # extraction gauntlet still matches (the lookahead only excludes a single `[` NOT
            # immediately followed by a second one).
            r"[ \t\n]{0,200}(?:ARGS\d+\s*\([^)]*\)|\((?![ \t\n]{0,20}\[(?!\[))(?:[^)(]|\([^)]*\))*\)|NOARGS)"
            # 8. POST-PARAMETER MODIFIERS & TRAILING RETURN TYPES
            # [OVERLAP PREVENTION]: Removed ambiguous \s* inside attribute matcher.
            r"(?:[ \t\n]+(?:const|volatile|noexcept|override|final|&{1,2}|__attribute__\((?:[^)(]|\([^)]*\))*\)|\[\[[^\]]*\]\])){0,10}"
            r"(?:[ \t\n]*->[ \t]*[a-zA-Z_:\w*<>]+)?"
            # 9. THE K&R C AND C++ CONSTRUCTOR GAP (ReDoS mitigated via Strict Bounding)
            # Handles C++ initializer lists (e.g., `MyClass() : a(1) {`) and legacy K&R declarations.
            # [IRON WALL - CATASTROPHIC BACKTRACKING FIX]:
            # We enforce strict numeric bounds (`{0,500}` and `{0,100}`) instead of `+` or `*`.
            # This caps the permutation tree instantly.
            r"(?:[ \t\n]*(?![ \t]*#):[^{;]{0,2000}|(?:[ \t\n]+(?![ \t]*#)[a-zA-Z_][^(){};]{0,100};){1,20})?"
            # 10. THE IGNITION (The opening brace confirming it is a definition, not a declaration)
            r"[ \t\n]*\{",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # =====================================================================
        # [ THE C++ ATTRIBUTE & TEMPLATE SHIELD ]
        # C++ entity declarations can be preceded by massive, multi-line templates
        # and C++20 `[[attributes]]` wedged directly before the class name.
        # FIX 1 (Negative Test): Dropped standard C-style `enum` to avoid hallucinating
        # minor constants; restricted to strongly-typed `enum class` / `enum struct`.
        # FIX 2 (Pathological): Injected `(?:\[\[[^\]]*\]\][ \t\n]*){0,5}` to step
        # over attributes, converted `\s*` to `[ \t\n]*` for the template wrapper,
        # and added the exact capture group `([a-zA-Z_]\w*)`.
        # =====================================================================
        # BUG FIX (Rule 11): the template-skip's flat `<[^>]*>` broke on
        # any nested default template argument (`template<typename T =
        # std::vector<int>> class Foo`), truncating at the inner `>` and
        # failing to match at all on the (very common) single-line form
        # -- the multi-line form appeared to "work" only because the
        # optional template group could be skipped entirely via
        # backtracking, re-anchoring on a later line's bare `class Foo`.
        # Extended to the same bounded 2-level nesting tolerance used in
        # func_start's return type.
        "class_start": re.compile(
            r"^[ \t]*(?:export[ \t\n]+)?"
            r"(?:template[ \t\n]*<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>[ \t\n]*)?"
            r"(?:class|struct|union|enum[ \t\n]+class|enum[ \t\n]+struct)[ \t\n]+(?:(?:\[\[[^\]]*\]\]|__attribute__[ \t]*\((?:[^)(]|\([^)]*\))*\))[ \t\n]*){0,5}([a-zA-Z_]\w*(?:<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>)?)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(try|catch|finally|std::unique_ptr|std::shared_ptr|std::weak_ptr|override|final|noexcept|static_assert|assert|std::optional|std::expected|std::span|std::variant|std::lock_guard|std::atomic)\b"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Swallowing errors or bypassing types. EXCLUDES standard casting (Phase 5).
        # BUG FIX (Rule 9): `void\s*\*` ends in `*` (non-word) but shared
        # a trailing `\b` with word-ending `std::any` -- the boundary
        # could only fire if a word character immediately followed the
        # `*` with zero whitespace (`void *p`), breaking on the equally
        # common `void* p`/`void * p` forms and any non-identifier
        # continuation (`(void*)src`). Pulled out with only a leading
        # `\b`.
        "safety_bypasses": re.compile(r"\bstd::any\b|\bvoid\s*\*|catch\s*\(\s*\.\.\.\s*\)"),
        # 8. danger (High-Risk Execution / System Calls)
        # Process killers and low-level blits. EXCLUDES prints (Phase 5).
        "high_risk_execution": re.compile(r"\b(system|memcpy|memset|abort|exit|std::terminate|longjmp|setjmp)\b"),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(std::fstream|std::ifstream|std::ofstream|std::filesystem|fopen|fclose|fread|fwrite|socket|recv|send|asio::|curl_easy_perform|std::cin)\b"
        ),
        # 10. api (Public Surface Area)
        # Code exposed to the world. Explicit visibility and module exports.
        # BUG FIX (Rule 9): `public:`, `__declspec(dllexport)`, and
        # `__attribute__((visibility("default")))` all end in non-word
        # characters (`:`/`)`) but shared a trailing `\b` with
        # word-ending `export module`/`export import`/`export class` --
        # the boundary could never fire for the realistic forms
        # (whitespace/newline follows `public:`; nothing but whitespace
        # follows the closing `)`). Pulled all three out with only a
        # leading `\b`.
        "api": re.compile(
            r"\b(?:export\s+module|export\s+import|export\s+class)\b|"
            r'\bpublic:|__declspec\(dllexport\)|__attribute__\(\(visibility\("default"\)\)\)|'
            r"^[ \t]*export\b(?!\s*module)",
            re.M,
        ),
        # 11. flux (State Mutation)
        # Mutation of state. Includes moves and increments.
        "state_mutation": re.compile(
            r"\b(mutable|std::move|std::exchange|std::swap|std::atomic)\b|(?<![=!<>])=(?![=])|&(?!\s*const)|\+\+|--|(?:\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=)"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented-out execution logic indicating dead features. MUST enforce that the structural keyword immediately follows the comment token.
        # BUG FIX (Rule 12): only checked `//` line comments, entirely
        # missing `/* */` block comments despite cpp being a
        # `standard_block` language where both styles are equally
        # idiomatic (`/* if (x) foo(); */`).
        "dead_code": re.compile(
            r"(?://|/\*)[ \t]*(?:if|for|while|auto|class|struct|std::cout|std::print|printf|void|int|return)\b"
        ),
        # 13. doc (Structured Documentation)
        "doc": re.compile(
            r"///|/\*\*|@param|@return|@brief|@details|@tparam|\\param|\\return|\\brief|\\details|\\tparam"
        ),
        # 14. test (Testing & Assertions)
        # Triggers indicating internal verification. Anchors explicit GTest/Catch2 macros and prevents prose collisions.
        "test": re.compile(
            r"\b(?:TEST|TEST_F|TEST_CASE|SECTION|REQUIRE|CHECK|EXPECT_[A-Z_]+|ASSERT_[A-Z_]+|Catch::|GTest)\b"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(std::thread|std::jthread|std::mutex|std::future|std::promise|std::async|std::latch|std::barrier|std::condition_variable|std::semaphore|co_await|std::coroutine_handle)\b"
        ),
        # 16. ui_framework (UI / View Components)
        # BUG FIX (Rule 9): `slots:`/`signals:` end in `:` (non-word) but
        # shared a trailing `\b` with word-ending siblings -- broke on
        # the realistic Qt form (`signals:` followed by a newline, never
        # a word character). `ImGui::` also ends in non-word (`::`) but
        # verified self-healing: real usage is always immediately
        # followed by an identifier (`ImGui::Begin(...)`), so left as-is.
        "ui_framework": re.compile(r"\b(?:Q_OBJECT|QWidget|wxFrame|ImGui::|Fl_Window)\b|\bslots:|\bsignals:"),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(
            r"\[[^\]]*\]\s*(?:<[^>]*>\s*)?(?:\([^)]*\))?\s*(?:(?:mutable|constexpr|consteval|noexcept)\s+)*(?:mutable|constexpr|consteval|noexcept)?\s*(?:->\s*[\w:<>_]+)?[ \t]*\{"
        ),
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            r"\b(extern|static(?!\s*assert)|thread_local|inline\s+constexpr)\b|^[ \t]*(?:static|extern)\s+[\w:<>_]+\s+[a-zA-Z_]\w*[ \t]*=",
            re.M,
        ),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"\[\[\s*[a-zA-Z_:][^\]]*\]\]"),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(r"\btemplate\s*<[^>]*>|\b(?:concept|requires)\b"),
        # 21. comprehensions (Iterators / Comprehensions)
        # Range pipelines acting as functional mappers.
        "comprehensions": re.compile(
            r"\b(std::ranges::|std::views::|views::|std::transform|std::accumulate|std::reduce|std::for_each|std::filter)\b|\|\s*std::views::"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(
            r"\b(std::cmath|std::complex|std::linalg|std::mdspan|Eigen::|blaze::|std::simd|__m128|__m256|__m512|std::numbers::)\b"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # SFINAE, compile-time reflection, and macros.
        # BUG FIX (Rule 9): `sizeof...` ends in `.` (non-word) but shared
        # a trailing `\b` with word-ending siblings -- the realistic
        # form (`sizeof...(Args)`) is immediately followed by `(`, also
        # non-word, so no boundary transition ever occurs and this
        # alternative could never fire. Pulled out with only a leading
        # `\b`.
        "reflection_metaprogramming": re.compile(
            r"\b(?:if\s+constexpr|if\s+consteval|std::enable_if|std::is_same|std::any_cast|std::bit_cast|decltype)\b|\bsizeof\.\.\.|#define\s+[a-zA-Z_]"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(
            r'^[ \t]*(?:#include\s*[<"][^>"]+[>"]|import\s+[a-zA-Z_][\w.:]*\s*;|export\s+import\s+[a-zA-Z_][\w.:]*\s*;)',
            re.M,
        ),
        "_dependency_capture": re.compile(
            r'^[ \t]*(?:#\s*include\s*[<"]([^>"]+)[>"]|(?:export\s+)?import\s+([a-zA-Z_][\w.:]*)\s*;)',
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"(?:@author|\\author|Author:|Created by:|Copyright)\s+(.*)", re.I),
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
        # and c earlier in this epic (the 9th hit). Bounded both
        # quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        "ssr_boundaries": re.compile(r"\b(FCGI_Accept|render_template|Inja::|ctemplate::)\b"),
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(r"\b(emit|signal|slot|notify|publish|subscribe|boost::signals2)\b"),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(r"\b(boost\.di|fruit::|[I]nject|IServiceCollection)\b"),
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(
            r"^[ \t]*#(?:define|undef|if|elif|else|endif|pragma|warning|error)\b",
            re.M,
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Raw memory addressing and pointer manipulation. CRITICAL: Uses lookbehinds `(?<=[=\s,(])` to strictly capture pointer dereferences `*ptr` and memory addresses `&var` without flagging standard multiplication `a * b` or logical AND `a & b`.
        "pointers": re.compile(
            r"->|\b(?:uintptr_t|intptr_t|ptrdiff_t|size_t)\b|(?<=[=\s,(])&\w+|(?<=[=\s,(])\*(?:\s*const\s*)?\w+"
        ),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(r"\b(new|malloc|calloc|realloc|aligned_alloc|mmap|alloca)\b"),
        # 37. inline_asm (The Bare Metal)
        "inline_asm": re.compile(
            r"\b(?:__asm__|asm|__asm)\b(?:\s+(?:volatile|__volatile__))?\s*\(|\b(?:__asm__|asm|__asm)\b[ \t]*\{"
        ),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(r"\b(log|logger|LOGGER|spdlog|glog|syslog)\.(?:info|error|warn|debug|trace)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(
            r"\b(std::cout|std::cerr|std::clog|printf|fprintf|vprintf|puts|putchar|std::print|std::println)\b"
        ),
        # # 40. explicit_casts (Explicit Type Casting)
        # Forceful type coercion bypassing the safety engine. Captures modern explicitly named casts and strict C-style groupings.
        # BUG FIX (false-positive correctness): the bare `<\s*[A-Za-z_]
        # \w*\s*>` alternative had no requirement that this actually be
        # used as a cast -- it fired on ANY single-identifier template
        # instantiation (`std::vector<int>`, `std::unique_ptr<Foo>`,
        # `Container<T>`), which is an ordinary declaration, not a cast.
        # Since every modern C++ file is full of these, this alternative
        # was a major over-broad false-positive source. Restricted to
        # require a functional-cast-style identifier prefix and a call
        # immediately after the closing `>` (`narrow_cast<int>(x)`,
        # `gsl::narrow_cast<T>(x)`), which is structurally distinct from
        # a plain declaration (identifier follows, not `(`).
        # Also fixed: the C-style-cast alternative required a bare
        # `(int)` with no asterisk, so it never matched C++'s equally
        # valid, common C-style POINTER cast (`(int*)ptr`) -- the exact
        # overlap the issue asked to check against C's `explicit_casts`/
        # `pointers` ambiguity. Extended to allow pointer asterisks
        # (O(1) alternation per the same fix already applied in C).
        "explicit_casts": re.compile(
            r"\b(?:static_cast|dynamic_cast|reinterpret_cast|const_cast|bit_cast)\b|"
            r"\b[a-zA-Z_]\w*<\s*[A-Za-z_]\w*\s*>\s*\(|"
            r"\(\s*(?:int|float|double|char|bool|long|short|unsigned|signed|void)[ \t\n]*(?:\*[ \t\n]*)*\)\s*[a-zA-Z_]"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|abort|exit|_Exit|quick_exit|std::terminate|longjmp)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        # Admission of race conditions or lazy polling.
        "thread_sleeps": re.compile(r"\b(sleep|delay|usleep|nanosleep|std::this_thread::sleep_for)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        # Low-level byte manipulation. CRITICAL: Removed bare `<<` and `>>` to prevent catastrophic false positives on `std::cout` and `std::cin` streams. Explicit bitwise assignments (`<<=`, `&=`) are retained as they are unambiguous.
        "bitwise_ops": re.compile(r"\^|(?<![=!])~|<<=|>>=|&=|\|=|\^="),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(
            r"\b(mutex|lock|synchronized|Semaphore|std::lock_guard|std::scoped_lock|std::unique_lock|mtx_lock)\b",
            re.I,
        ),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(const|constexpr|consteval|constinit|final|readonly|Immutable)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(delete|free|close|fclose|dispose|shutdown|std::destroy|reset)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # BUG FIX (Rule 9): all three alternatives end in `:` (non-word)
        # and the group had NO word-ending sibling at all -- the
        # trailing `\b` could never fire against the realistic form
        # (`private:` always followed by whitespace/newline, never a
        # word character), meaning this rule never matched anything.
        # Removed the trailing `\b`; the literal `:` is already
        # unambiguous.
        "encapsulation": re.compile(r"\b(?:private|protected|internal):"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(on|addEventListener|subscribe|connect|handler|callback)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # BUG FIX (Rule 10): `mock\(`/`fake\(` end in a literal `(` but
        # shared a trailing `\b` with word-ending siblings -- broke on
        # the truly-empty-argument call form (`mock()`), same shape
        # already found and fixed in C (#773).
        "test_skip": re.compile(r"\b(?:GTEST_SKIP|test\.skip|it\.skip)\b|mock\(|fake\("),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (C++ Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(nlohmann::json|rapidjson|boost::archive|ParseFromString|SerializeToString)\b"
        ),
        "regex_execution": re.compile(r"\b(std::regex|std::regex_match|std::regex_search|std::regex_replace)\b"),
        "time_date_logic": re.compile(
            r"\b(std::chrono::(?:system_clock|steady_clock|duration)|std::time_t|std::localtime)\b"
        ),
        "ipc_rpc_bridges": re.compile(r"\b(boost::interprocess|mmap|shm_open|pipe|fork|grpc::ServerBuilder)\b"),
    },
}
