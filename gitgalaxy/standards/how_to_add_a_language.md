# Adding a New Language (Defining Structural Signatures)

GitGalaxy does not use brittle Abstract Syntax Trees (ASTs) or traditional compiler toolchains. Instead, we map enterprise codebases using a **Structural Signature Analysis Engine**: a polyglot structural analyzer.

Rather than writing a custom AST parser that breaks upon encountering syntax errors or incomplete code, we configure the engine with **Structural Signatures**—high-speed, mathematically bounded, ReDoS-proof regular expressions. This allows GitGalaxy to build a universal, comparative structural taxonomy across entirely different computing eras (from 1980s COBOL to modern Rust).

For the mathematical proofs backing this architecture, review:
* [The Heuristic Parsing Paradigm](../../docs/wiki/01-03-the-heuristic-paradigm.md)
* [Claim 10: Heuristic vs. AST Parsing](../../docs/wiki/03-10-claim-10-ast-vs-heuristic-parsing.md)
* [Claim 8: Empirical Validation of AST-Free Parsing](../../docs/wiki/03-08-claim-8-empirical-validation-of-ast-free-parsing.md)

To add a new language to the Language Classifier, you will use an advanced LLM (like Claude 3.5 Sonnet, GPT-4o, or Gemini 1.5 Pro) to generate the Structural Signatures dictionary.

---

### Step 1: Initialize the LLM Context
Before asking the LLM to generate the new language signatures, upload the `gitgalaxy/standards/language_standards.py` file to the chat window. Issue this exact command:
> *"Read this file to understand how the GitGalaxy Structural Signature Analysis Engine uses bounded regex to guarantee ReDoS immunity. Pay close attention to how C++ and Python are mapped to prevent Catastrophic Backtracking."*

### Step 2: Inject the Structural Signature Prompt
Copy the **Generation Prompt** below and paste it into the LLM. Replace `[TARGET LANGUAGE]` with the exact language you want to map.

### Step 3: Register the Signatures
1. Open `gitgalaxy/standards/language_standards.py`.
2. Locate the `LANGUAGE_DEFINITIONS` registry.
3. Paste the generated Python dictionary directly into the registry to instantly grant the engine native support for the new language architecture.

<br><br>

---

## ⚙️ The Structural Signature Generation Prompt
*Copy everything below this line and feed it directly to the LLM.*

**Prompt:**
You are an expert compiler engineer and static analysis specialist. Please generate a GitGalaxy REGISTRY regex dictionary for **[TARGET LANGUAGE]** using the strict Zero-Trust framework defined below. 

This dictionary defines the **Structural Signatures** used by an AST-free parsing engine to create a system of consistent 1:1 cross-language comparisons. The engine calculates risk exposures across implicit and explicit language behaviors. The engine uses `re.M` (Multiline) to scan 50,000+ line enterprise files at extreme velocity.

### 🚨 CRITICAL ENGINE RULES
1. **Semantic Intent Over Keyword Matching (Implicit vs. Explicit):** Do not just hunt for explicit keywords; capture the practical reality of the language. If defining `api` (Public Surface Area), determine if the language is implicitly public (e.g., Python, Fortran). If so, the regex must capture standard function/subroutine definitions, not just the rare use of an explicit public or export tag.
2. **Idiomatic Paradigm Alignment:** Do not penalize a language for operating within its standard paradigm. Example: Standard C-style pointer casting is standard operating procedure, not a structural fracture. It must be routed to `explicit_casts` (Resource Management), NOT placed in `safety_bypasses` where it will artificially trigger risk alerts.
3. **Annotation & Execution Isolation:** When assessing Technical Debt or High-Risk Execution, isolate human commentary from execution flow. Example: `TODO` and `FIXME` are planned debt. They must NEVER be placed in execution-blocking keys like `high_risk_execution`, otherwise a file with high developer documentation will be falsely penalized as a volatile execution risk.
4. **Strict Feature Parity (Use `None`):** If a structural dimension does not exist natively in the target language (e.g., pointers in JavaScript, decorators in C), you MUST explicitly set its key to `None`. Do not force a fit.
5. **Absolute ReDoS Immunity (No Catastrophic Backtracking):** Bound all wildcards. Never use `.*` inside brackets. Always use negation (e.g., `<[^>]*>`). In `re.M` mode, `\s` matches newlines (`\n`). 
    * ❌ NEVER use `^\s*`. ✅ ALWAYS use `^[ \t]*`.
    * ❌ NEVER use `\s*$`. ✅ ALWAYS use `[ \t]*$`.
    * ❌ NEVER use `\s*=`. ✅ ALWAYS use `[ \t]*=`.
    * ❌ NEVER nest unbounded quantifiers like `(?:[ \t]*\*+)*` or `(?:(?:public|private)\s+)*`. ✅ ALWAYS use strict numeric clamps like `(?:[ \t*&]+){0,10}` or `(?:(?:public|static)[ \t]+){0,3}`.
6. **The Metric Inflation Anti-Pattern:** Do NOT put access modifiers (e.g., public, private, static) in the `structural_boundaries` array. This artificially inflates structural complexity metrics.
7. **Strict Execution Anchoring:** `func_start` must ONLY match executable logic blocks (methods/functions/constructors). Do NOT match interfaces, types, or classes here.
8. **Resource Management & Synchronization:** Pay special attention to Phase 5. Ensure that asynchronous execution (`concurrency`) and synchronization (`sync_locks`) are cleanly separated into their specific regex keys so the engine can balance them accurately.
9. **Word-Boundary Correctness for Mixed Alternations:** `\b` only fires at a transition between a word character (`\w`) and a non-word character (or string edge) — it does NOT fire next to a symbolic character unless a word character sits on the other side. Never wrap a single `\b(...)\b` group around alternatives that don't all share the same edge shape. If even one alternative starts or ends with a non-word character (`-`, `.`, `@`, `$`, `(`, `[`, `!`, `?`, `~`, `+`, `:`, `=`), pull it out of the group and drop the `\b` on that side — the symbol is already self-delimiting.
    * ❌ `\b(Import-Module|-Parallel)\b` — `-Parallel` can never satisfy the leading `\b`; real code always precedes it with whitespace (a non-word character), so the alternative silently never matches.
    * ✅ `\bImport-Module\b|-Parallel\b`
    * This was, by a wide margin, the single most common defect found across every language audited so far — it produces zero errors or warnings, the signature just quietly never matches its most common real-world form.
    * **Whitespace itself is non-word too — this trap isn't limited to punctuation.** An alternative ending in `\s+`/`\s*` (not a symbol) has exactly the same problem: `\bCALL\s+\b` inside a shared group can only fire if a word character *immediately* follows all the consumed whitespace, which fails the moment the real form is `CALL 'SUBPROGRAM'` (a quote right after the space). Found independently in COBOL (`CALL\s+`) and elsewhere — treat any alternative ending in a `\s`-quantifier the same as one ending in a literal symbol.
    * **A "broken" alternative can still silently work if a sibling alternative shadows it — always verify with a real `.search()` call, not by reading the regex shape.** If a group also contains a *shorter, unqualified* alternative that's a prefix of the broken one (e.g. bare `yield` next to broken `yield\s*\*`), the shorter one may satisfy the match first on every realistic input, masking the defect entirely. Confirmed repeatedly (YAML's `TODO`/`@todo`, Tcl's `::`-suffixed namespaces, Rust's `yield`/`yield\s*\*`) — don't flag *or* clear a boundary finding based on the pattern's shape alone; check what `.search()` actually returns on the realistic text.
10. **Zero-Argument / Symbol-First-Argument Call Forms:** When anchoring a function/method call by name with a trailing `\b` (e.g. `\bapp\(\b`-style reasoning), remember real calls are frequently written with zero arguments or a quoted/numeric first argument — never assume a word character follows the opening paren.
    * ❌ A trailing `\b` placed right after a literal `(` — matches `app(x)` but not `app()` or `app("foo")`, which are usually the *more* common call shapes.
    * ✅ Drop the trailing `\b` when an alternative already ends on `(` — the paren is self-delimiting, same principle as Rule 9.
11. **Nested-Delimiter Coverage:** A negated character class like `[^\]]+` cannot represent even one level of legitimate nesting (e.g. a generic return type like `Dictionary[string,int]`, or `List<Map<K,V>>`). If the language has any construct where the same delimiter can nest one level deep (generics, indexers, attribute lists), use a bounded one-level-nesting form instead of a flat negated class.
    * ❌ `\[[^\]]+\]` — breaks on `[List[int]]` (matches only up to the first `]`, then fails).
    * ✅ `\[(?:[^\[\]]|\[[^\[\]]*\])+\]` — handles one level of nesting and stays linear (the two alternatives never match overlapping text, so it can't trigger the catastrophic backtracking Rule 5 warns against).
12. **Comment-Style Completeness for `dead_code`:** If a language's lexical family supports more than one comment style (e.g. a `standard_block` language with both `//` and `/* */`), the `dead_code` keyword check must be wired to ALL of them, not just one — do not assume the style you happen to write the regex against first is the dominant one.
    * ❌ `(?:/\*)\s*(?:function|class|...)\b` — only fires inside block comments, silently missing every `// function foo() {}` line-comment case even though `//` is usually the far more common style.
    * ✅ `(?://|/\*)\s*(?:function|class|...)\b`
    * The same completeness check applies to `doc`/`ownership` if they're anchored to a specific comment marker (e.g. m4's `dnl` vs. its equally-real `#` default comment) — don't assume the family's shared delimiter table and the rule's own hand-written anchor agree just because they're both "correct" in isolation.
13. **Multiline Flag Completeness for `^`-Anchored Rules:** Any rule using `^` (start-of-line anchor) MUST include `re.M` in its compile flags. Without it, `^` anchors to the true start of the *string*, not the start of each line — the rule can then only ever fire if the anchored keyword happens to be the literal first characters of the entire file, almost never true for a real multi-line source file.
    * ❌ `re.compile(r"^(?:EXPOSE|VOLUME|ENTRYPOINT)\b")` with no `re.M` — can only match if one of these keywords is the first thing in the file; a real Dockerfile always starts with `FROM`, so this silently never fires.
    * ✅ `re.compile(r"^(?:EXPOSE|VOLUME|ENTRYPOINT)\b", re.M)`
    * Exactly as invisible as Rule 9's defect: the pattern compiles fine and the anchor "looks" correct, it just structurally can't match real multi-line code. Always check the flags, not just the pattern text.
14. **Adjacent Quantifiers With Overlapping Character Classes (a ReDoS shape distinct from Rule 11):** Two quantified pieces placed back-to-back, where the first's character class is a superset of or overlaps the second's, let the engine try exponentially many ways to split the matched text between them before failing on a payload with no valid closing token. This is NOT about bracket/delimiter nesting (see Rule 11) — it happens with any adjacent quantifiers, including a plain `\s+ ... \s+` sandwiching an unbounded middle piece.
    * ❌ `\d+[^\]]*` — `[^\]]*` also matches digits, so on a long run of digits with no closing `]`, the engine repartitions the run between the two quantifiers exponentially. Confirmed independently broken this exact way in 7+ languages in this codebase's own audit history (embedded_python, css, tcl, matlab, scheme, typescript, rust) — bound both: `\d{1,10}[^\]]{0,300}`.
    * ❌ `\s+.*\s+FROM` — `.` matches whitespace too, so a long space-only run with no `FROM` ever appearing lets the engine partition it between `\s+`, `.*`, and the second `\s+` in exponentially many ways. Confirmed **9+ real seconds at just n=2000** in one case — far faster to blow up than the typical nested-delimiter shape, which usually only shows real cost around n=16000-32000. Replace the unbounded middle piece with the actual expected token shape (e.g. a real identifier character class) — this is usually both more correct AND removes the ambiguity entirely.
    * When testing for this shape, start the scaling sweep at a SMALL n (e.g. 2000) rather than assuming n=32000 is where a real hang would first appear.
15. **A Documented Exclusion Must Actually Exclude:** If a rule's own comment claims to exclude a specific case (e.g. "only public methods, not private"), verify the regex uses a negative lookahead/lookbehind to actually enforce it — not an *optional* positive group that, when it fails to match the excluded text, simply backs off and matches the unqualified base case anyway.
    * ❌ `methods\b(?:[ \t]*\(Access[ \t]*=[ \t]*public[ \t]*\))?` intended to flag only public methods blocks — the qualifying group is optional, so `methods (Access = private)` still matches via the bare `methods` alone; the "exclusion" never actually gates anything.
    * ✅ `methods\b(?![ \t]*\([^)]*\bAccess[ \t]*=[ \t]*(?:private|protected)\b)` — a negative lookahead that genuinely blocks the match when the excluded condition is present.
    * This defect is invisible to a casual read of the regex — it *looks* like it discriminates on the qualifier — and only surfaces when you specifically test the case the comment claims to exclude.
16. **Identifier Capture Classes Must Match the Language's Real Grammar:** A capture class like `[a-zA-Z0-9_!?-]+` for a function/type name assumes a narrow, C-like identifier grammar. Many languages (Lisp-family especially, but any language with idiomatic naming conventions using extra punctuation) allow far more characters in identifiers than that. Because the capture typically feeds a required trailing lookahead, a truncated capture doesn't just capture less — it can break the lookahead entirely, turning a partial-match bug into a complete non-match for the whole rule.
    * ❌ `[a-zA-Z0-9_!?-]+` for Scheme identifiers — excludes `> < = * + / . ~ $ % ^ &`, so idiomatic names like `list->vector`, `1+`, and SRFI-9's `<TypeName>` record-naming convention never matched AT ALL, because the truncated capture broke the trailing lookahead requiring whitespace/`)` right after.
    * ✅ Check the language's actual identifier grammar (e.g. R7RS's special-initial/special-subsequent character sets) before picking the capture class, and verify against real idiomatic names from that language's own standard library — not just simple ASCII test names.

### THE LEXICAL PARSING FAMILIES
You must assign the language to one of these 5 lexical parsing families based on how it handles comments and non-executable text:
* `standard_block`: The language uses both line and block delimiters, but blocks CANNOT be nested. Examples: C, C++, Java, JavaScript, PHP, SQL, Go, Ruby, Lua.
* `recursive_block`: The language allows block comments to be safely nested inside one another. Examples: Rust, Swift, Dart, Scala.
* `line_exclusive`: The language possesses no native multi-line block syntax. The engine ignores closing tags. Examples: Python, Shell, Makefile, Assembly.
* `block_exclusive`: The language possesses no native single-line comment syntax. All text must be enclosed. Examples: HTML, XML.
* `positional_anchored`: The engine must verify the token's physical column placement. Examples: Legacy COBOL, Legacy Fortran, ABAP.

### OUTPUT SCHEMA & DEFINITIONS
Generate a valid Python dictionary matching this exact structure. 

```python
"[TARGET LANGUAGE]": {
    "_meta": {
        "target_version": "Include the modern compiler/standard version",
        "last_updated": "YYYY-MM-DD",
        "blueprint_version": "v6.3",
        "status": "production"
    },
    "extensions": [], # e.g. [".js", ".jsx"]
    "exact_matches": [], # e.g. ["Makefile"]
    "discriminators": [], # Ecosystem Indicators / Disambiguation Anchors (e.g. "package.json")
    "shebangs": [], 
    "lexical_family": "", # See Lexical Parsing Families list above
    # NOTE: comment/code separation is NOT configured per-language. It's driven
    # entirely by `lexical_family` above, dispatched against the shared,
    # family-level delimiter table in gitgalaxy_config.py's
    # LEXICAL_FAMILY_HEURISTICS. An earlier version of this schema had
    # per-language "_line_anchor"/"_inline_comment"/"_block_start"/"_block_end"
    # rule keys; they were removed because nothing ever read them (confirmed
    # via `grep -rn` across the whole package) -- prism.py's real comment
    # stripper has always used the family table, not these. Do not re-add them.
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: Control flow that forces the CPU to make a decision or jump. Includes: if, else, switch, for, while, catch, try, &&, ||, ternary. EXCLUDES: Exceptions (throw, raise) — these belong in panics_and_aborts.
        "branch": re.compile(r""), 
        # args: Signatures defining input parameters. Includes: parameter blocks of functions, methods, and lambdas. Must safely step over type hints.
        "args": re.compile(r""), 
        # structural_boundaries: Keywords defining structural boundaries and straight-line execution. Includes: var, return, class, import. EXCLUDES: Access modifiers (public, private) and Immutability keywords (const, final — these belong in immutability_locks).
        "structural_boundaries": re.compile(r""), 
        # func_start: Exact syntax anchoring the start of an executable block of logic. Includes: Method signatures, constructors. EXCLUDES: Interfaces, types, and classes.
        "func_start": re.compile(r""), 
        # class_start: The syntax that defines an object-oriented class, struct, or record.
        "class_start": re.compile(r""), 

        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety: Defensive programming constructs that prevent crashes at runtime. Includes: try/catch, explicit null checks, guard. EXCLUDES: Immutability.
        "safety": re.compile(r""), 
        # safety_bypasses: Syntax that actively bypasses type safety, swallows errors, or relies on unpredictable state. Includes: Force unwrapping (!), any, raw memory casting, linter bypasses (@ts-ignore).
        "safety_bypasses": re.compile(r""), 
        # high_risk_execution: Process-killing commands and catastrophic runtime vulnerabilities. Includes: eval, exec, process.exit. EXCLUDES: TODO/HACK (planned_debt) and print (debug_prints).
        "high_risk_execution": re.compile(r""), 
        # io: Interaction with the disk, network, or external systems. Includes: File writing/reading, HTTP clients, sockets. EXCLUDES: Logging/printing.
        "io": re.compile(r""), 
        # api: Code exposed to the outside world. Captures explicit visibility markers (export, public) AND implicit architectural defaults.
        "api": re.compile(r""), 
        # state_mutation: Reassignment of variables or modifying collections. Includes: let, mut, volatile, .push(), .set().
        "state_mutation": re.compile(r""), 
        # dead_code (Commented Logic / Deprecated Trails): Commented-out structural code and unused logic trails. Includes: // if (x), /* var y */.
        "dead_code": re.compile(r""), 
        # doc: Structured documentation meant to be parsed by IDEs or generators. Includes: JSDoc, Docstrings.
        "doc": re.compile(r""), 
        # test: Assertions and unit testing framework keywords. Includes: describe, it, assert, expect.
        "test": re.compile(r""), 

        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # concurrency: Asynchronous logic and parallel execution. Includes: async, await, Promise, Thread.
        "concurrency": re.compile(r""), 
        # ui_framework: DOM manipulation, UI components. Includes: HTML tags, React hooks.
        "ui_framework": re.compile(r""), 
        # closures: Anonymous functions, lambdas, inline callbacks. Includes: Fat arrows (=>).
        "closures": re.compile(r""), 
        # globals: Accessing global state, environment variables, or system registries. Includes: window., process.env.
        "globals": re.compile(r""), 
        # decorators: Annotations applied to classes/methods. Includes: @Injectable, [Obsolete].
        "decorators": re.compile(r""), 
        # generics: Type parameters indicating generic abstractions. Includes: <T>, List<T>.
        "generics": re.compile(r""), 
        # comprehensions: Collection iterators or inline looping. Includes: .map(, .filter(.
        "comprehensions": re.compile(r""), 
        # scientific: Math, data science, and complex rendering libraries. Includes: Math., numpy.
        "scientific": re.compile(r""), 
        # reflection_metaprogramming (Cognitive Load / Metaprogramming Density): Metaprogramming, reflection, and dynamic property assignment. Includes: Reflection, Proxy, .bind().
        "reflection_metaprogramming": re.compile(r""), 
        # import: Dependency resolution and module loading. Includes: import, require, using.
        "import": re.compile(r""), 
        # _dependency_capture: Regex strictly capturing group 1 as the exact dependency path string.
        "_dependency_capture": re.compile(r""), 
        # ownership: Authorship metadata. Includes: @author, Created by:.
        "ownership": re.compile(r""), 

        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # planned_debt: Annotated future work. Includes: TODO, WIP, STUB.
        "planned_debt": re.compile(r""), 
        # fragile_debt: Explicit admissions of fragile or dangerous logic. Includes: HACK, FIXME, XXX.
        "fragile_debt": re.compile(r""), 
        # hardcoded_secrets: Static credentials or API keys baked into code. Includes: password, secret, token.
        "hardcoded_secrets": re.compile(r""), 
        # spec_exposure: Audit tags establishing traceability of intent. Includes: [SPEC-123], [audit].
        "spec_exposure": re.compile(r""), 
        # tabs_vs_spaces (Formatting Inconsistencies): Structural formatting markers used to calculate indentation consistency. Often None.
        "tabs_vs_spaces": None, 
        # ssr_boundaries: Server-Side Rendering computation boundaries. Includes: getServerSideProps.
        "ssr_boundaries": re.compile(r""), 
        # events: Event-driven architecture signatures and message brokers. Includes: emit, EventEmitter, Kafka.
        "events": re.compile(r""), 
        # dependency_injection: Inversion of Control (IoC) injection markers. Includes: @Autowired, @Inject.
        "dependency_injection": re.compile(r""), 
        # macros: Compiler pragmas or macro definitions that generate code at compile-time. Includes: #define, macro_rules!.
        "macros": re.compile(r""), 
        # pointers: Explicit tracking of raw memory addressing and pointer dereferencing. Includes: *const, &mut, IntPtr.
        "pointers": re.compile(r""), 
        # memory_alloc: Explicit unmanaged memory allocations and raw heap manipulations. Includes: malloc, new.
        "memory_alloc": re.compile(r""), 
        # inline_asm: Direct CPU architecture bridging. Includes: __asm__, asm!.
        "inline_asm": re.compile(r""), 

        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # telemetry: Structured logging and observability frameworks.
        "telemetry": re.compile(r""), 
        # debug_prints (Debug Artifacts / Unstructured Outputs): Ad-hoc, temporary debug statements. Includes: print(, console.log(.
        "debug_prints": re.compile(r""), 
        # explicit_casts: Explicitly bypassing the compiler's type-checker. Includes: as String, (int), static_cast.
        "explicit_casts": re.compile(r""), 
        # panics_and_aborts (Execution Interrupts / Fatal Aborts): Forcefully destroying the current execution context. Includes: throw, raise, panic!, abort().
        "panics_and_aborts": re.compile(r""), 
        # thread_sleeps (Thread Blocking / Synchronous Pauses): Thread blocking or forced timeouts. Includes: sleep(, delay(.
        "thread_sleeps": re.compile(r""), 
        # bitwise_ops: Bitwise operations manipulating raw bytes. EXCLUDES logical &&/||.
        "bitwise_ops": re.compile(r""), 
        # sync_locks: Explicitly coordinating threaded logic to prevent race conditions.
        "sync_locks": re.compile(r""), 
        # immutability_locks (Immutability Constraints): Explicitly locking data so it cannot be mutated. Includes: const, final, readonly.
        "immutability_locks": re.compile(r""), 
        # cleanup (Resource Cleanup / Teardown): Explicitly destroying state or releasing resources. Includes: free(, dispose(), .close().
        "cleanup": re.compile(r""), 
        # encapsulation (Encapsulation / Access Modifiers): Explicitly hiding logic from the rest of the application. Includes: private, protected, internal.
        "encapsulation": re.compile(r""), 
        # listeners: Waiting to receive state from an external broadcast. Includes: on(, addEventListener, subscribe(.
        "listeners": re.compile(r""), 
        # test_skip: Bypassed tests or ignored verification specs. Includes: @Ignore, test.skip(.
        "test_skip": re.compile(r""), 

        # --- HYBRID DOMAIN SENSORS ---
        # serialization_parsing: JSON, XML, YAML parsing libraries.
        "serialization_parsing": re.compile(r""), 
        # regex_execution: Native regex evaluation commands.
        "regex_execution": re.compile(r""), 
        # time_date_logic: Time/date instantiation and math.
        "time_date_logic": re.compile(r""), 
        # ipc_rpc_bridges: Inter-process or RPC bridging commands.
        "ipc_rpc_bridges": re.compile(r"") 
    }
}
```

<br><br>

---

## Strict Testing & Crucible Verification Framework

Generating the signatures is only half the job. A regex an LLM just wrote, graded by the same
LLM in the same pass, tends to get lenient, self-confirming tests — the model writes cases that
happen to pass, not adversarial ones that probe the edge cases in Rules 9-12 above. Strict testing
must therefore be **a separate prompt, run as a distinct pass** against the signatures you just
registered, not a continuation of the generation conversation.

### Step 4: Generate the Strict Testing Suite (Separate Pass)
Open a **new** conversation (or at minimum a clearly separate turn) and feed the LLM the finished
`rules` dict for the language plus the **Strict Testing Prompt** below. The output should be a
pytest module in the shape of `tests/core_engine/test_language_standards_strict.py`'s existing
per-language sections (see e.g. `_PHP_SIMPLE_CASES` / `test_php_*` for a concrete template).

**Strict Testing Prompt:**
You are an adversarial test engineer. You did not write the regex dictionary below — your job is
to attack it, not confirm it. For the **[TARGET LANGUAGE]** rules dict provided, produce a pytest
module covering all of the following, and do not skip a category just because the pattern "looks
fine":

1. **Per-signature positive/negative cases.** A `_[LANG]_SIMPLE_CASES` list of
   `(signature, positive_snippet, negative_snippet_or_None)` tuples, one entry per non-`None` rule
   key, parametrized into a single test. Every positive snippet must be realistic code you'd
   actually find in a real file of this language — not a synthetic string engineered to match.
2. **Symbolic-boundary audit (Rule 9/10).** For every `\b(...)\b` group in the dict, check whether
   any alternative starts or ends on a non-word character — including a bare `\s+`/`\s*`, which is
   just as non-word as a literal symbol. For each one found, write a regression test proving the
   *realistic* real-world form (preceded/followed by whitespace or punctuation, not a
   conveniently-placed word character) actually matches. Before flagging (or clearing) a finding,
   run the actual `.search()` call on the realistic text — a structurally-broken alternative can be
   silently masked by a shorter, unqualified sibling alternative in the same group that matches
   first on every realistic input (confirmed repeatedly: YAML's `TODO`/`@todo`, Tcl's
   `::`-suffixed namespaces, Rust's `yield`/`yield\s*\*`). The pattern's shape alone is not proof
   either way.
3. **Nested-delimiter audit (Rule 11).** For every rule using a flat negated class as a delimiter
   matcher (`[^\]]+`, `[^)]+`, `[^}]+`), construct a realistic one-level-nested input for this
   language (a generic type, a nested call, a nested nested structure) and verify it still matches.
   Separately, check for **adjacent quantifiers with overlapping character classes** (Rule 14) —
   not a nesting/bracket issue, but two quantified pieces back-to-back where the first's character
   class overlaps the second's (`\d+` next to `[^\]]+`, or `\s+` next to `.*`). This shape has shown
   up independently in 7+ languages for the exact same copy-pasted `spec_exposure` pattern, and can
   be *far* more explosive than a typical nested-delimiter ReDoS (one real case hung for 9+ seconds
   at just n=2000) — start the scaling sweep at a small n, not just n=32000.
4. **Comment-style audit (Rule 12).** If the language's `lexical_family` supports more than one
   comment style, verify `dead_code` (and `doc`/`ownership`, if they're anchored to a specific
   comment marker rather than the family's full delimiter set) fires under each of them, not just
   the one it was seemingly written against.
5. **ReDoS adversarial payloads, verified by scaling — not a single timing.** For every rule with
   an unbounded-looking quantifier, construct the "never closes" adversarial payload (e.g. `"{" *
   n` for a rule expecting a closing `}`, `"(" * n` for one expecting `)`) and measure actual
   execution time at **several** geometrically increasing sizes (e.g. n = 2000, 4000, 8000, 16000,
   32000). A roughly 2x time increase per doubling is linear and fine. A roughly 4x increase per
   doubling is the signature of real O(n²) catastrophic backtracking and must be fixed (bound the
   quantifier, e.g. `{0,300}` / `{0,500}`, generous enough to still match realistic code) — do not
   report a ReDoS finding, and do not clear one, off a single timing. See Rule 14 above for a shape
   that can blow up dramatically faster than the usual nested-delimiter case — don't assume n=32000
   is always where trouble would first appear.
6. **Ambiguity sweep.** For every *pair* of signatures in the dict (not just an assumed subset),
   check for shared literal tokens, then empirically verify each flagged pair on real-shaped input:
   is it a genuine false collision (two signatures matching the exact same text when they
   shouldn't), or a structurally-forced non-collision (e.g. `dead_code` requires an immediately
   preceding comment marker that a live-code signature's anchor excludes)? Also explicitly check
   these known cross-language ambiguity-prone pairs if the language has both sides of each:
   `explicit_casts` vs `pointers`, `test` vs `regex_execution`, `func_start` vs `generics`,
   `bitwise_ops` vs `closures`. Not every finding is a bug — e.g. a test-assertion DSL whose
   "matches" keyword genuinely invokes a regex engine under the hood (Pester's `Should -Match`) is
   a correct, intentional double-classification, not a false positive. State which it is and why.
7. **`re.M` completeness audit (Rule 13).** For every rule whose pattern uses a literal `^` outside
   a character class, confirm `re.M` is actually set in its compile flags. A missing flag produces
   no error and no warning — the rule simply can never match past the first line of a file, which
   is easy to miss entirely if you only read the pattern text and not the flags argument.
8. **Lexical-family sanity check.** Before writing any signature-level tests, compare the
   language's own inline `# Rationale:` comment (next to its `lexical_family` field) against the
   *actual* value assigned. If they describe different families, don't just fix the mismatch —
   empirically confirm via `Prism.split_streams()` against a realistic multi-line comment sample
   whether comments are actually being stripped as the rationale comment assumes. This has
   surfaced real, separate pipeline bugs twice (HTML mistagged `line_exclusive` instead of
   `block_exclusive`; Scheme mistagged `line_exclusive` despite describing a nested-block family
   that was never implemented) — file pipeline-level findings like this as their own issue rather
   than folding a `prism.py` fix into a per-language strict-parsing PR (see Step 5's on-target
   discipline below), and write this language's signature tests against the *actual* observed
   stripping behavior, not the aspirational one.
9. **Schema completeness audit (Rule 4, revisited).** Diff the full baseline key list (everything
   in the Output Schema below) against this language's actual `rules.keys()` — not just against
   the subset that's currently non-`None`. A key can be missing from the dict *entirely*, which
   looks identical to "hasn't been assigned yet" unless you explicitly check for its presence.
   Found this way in COBOL: `import` was absent outright (not `None`) even though
   `_dependency_capture` right next to it was already correctly parsing COPY/INCLUDE targets — a
   real, working regex for the key was clearly intended and just never added. If a key is
   genuinely inapplicable, it should be explicit `None` per Rule 4, not silently absent.

### Step 5: Verify Against the Language Crucible
The project maintains `tests/test_golden_crucible.py`, which runs the real `galaxyscope` CLI
against the `language-crucible` corpus (a pinned checkout of real open-source repos, cloned as a
sibling directory or pointed to via `LANGUAGE_CRUCIBLE_PATH`) and diffs the result against
`tests/golden_master_audit.json` / `tests/golden_master_zero_dep_audit.json` using
`tests/golden_diff.py`. Run it explicitly via `pytest -m golden_crucible` (it's opt-in, excluded
from the default run) — once with a full-precision environment installed, once with a
zero-dependency one, since each maintains its own golden master fixture.

Do not stop at "the test failed" or "the test passed" — a passing diff-count and a *correct* diff
are not the same thing:
1. When the test reports drift, don't just re-run `update_golden_master.py` reflexively. Load both
   the old and new artifacts directly with `golden_diff.load_and_sanitize()` +
   `golden_diff.deep_compare()` in a throwaway script — the pytest failure message truncates to 50
   lines, which can hide diffs that matter.
2. **Separate on-target from off-target effects.** Filter every diff by the real file *extension*
   in its path, not by the crucible corpus's directory-group label — a directory grouped under one
   language can legitimately bundle files of another (e.g. a Dockerfile-grouped repo containing
   `.go` files). Every diff should trace to a file whose extension matches the language you just
   touched. Any diff on a file of a *different* language is an off-target effect: your regex change
   had an unintended blast radius (usually a signature-key collision or an overly broad new
   alternative) and must be investigated before proceeding — never dismissed or regenerated over.
3. **Explain every on-target diff by name.** Find the specific real file and construct responsible,
   and confirm the direction of the change matches your fix's intent (a corrected boundary bug
   should *increase* a previously-undercounted signature; a ReDoS bound should only *decrease*
   counts, and only on abnormally large spans). An unexplained diff — even a single-digit one — is
   a sign something other than your intended fix moved, and should not be papered over by
   regenerating the fixture.
4. **A zero-diff result is not automatically a clean bill of health.** If a real, intentional fix
   produces no diff at all, confirm *why* — grep/find the crucible corpus to check whether it
   simply contains no files, or no instances of the fixed construct, in that language. A silent
   zero-diff from an empty corpus is not the same claim as "verified no regression."
5. Only once every diff is individually explained and confirmed legitimate, regenerate the fixture
   with `tests/tools/update_golden_master.py --yes` (run once per environment — it detects and
   updates only the fixture matching whichever venv is currently active).
6. Re-run the full test suite once more after regenerating, to confirm the new fixtures are
   internally self-consistent with everything else.

---

## Optional: The AI/ML & Literate-Programming Extension Pack

The schema above is the universal baseline every language gets. A small number of languages
also carry an **extension pack** of additional rule keys layered on top of the baseline —
today, `python`, `javascript`, and `typescript` carry the AI/ML extension pack, and `markdown`
carries a literate-programming one. These are opt-in: only add them to a language's `rules`
dict if that language is a realistic host for the behavior being detected. Don't add the AI/ML
pack to, say, COBOL just for parity — an empty/never-matching rule is worse than an absent one,
since it implies detection coverage that doesn't exist.

### AI/ML Extension Pack (currently: `python`, `javascript`, `typescript`)
Detects the modern AI-application supply chain and its specific risk surface — none of this
existed in the original 43-key baseline because none of it existed as a mainstream pattern when
that schema was designed.

* `llm_api`: Direct calls into a hosted LLM provider SDK. Includes: `openai`, `anthropic`.
* `llm_orchestrator`: Agent/RAG orchestration frameworks. Includes: `langchain`, `llama_index`.
* `llm_vector_store`: Vector database clients. Includes: `chromadb`, `pinecone`.
* `ml_traditional`: Classical (non-deep-learning) ML libraries. Includes: `sklearn`.
* `dl_frameworks`: Deep learning frameworks. Includes: `tensorflow`, `torch`, `keras`.
* `hardware_bridge`: Bridges from software into physical/peripheral I/O. Includes: `serialport`,
  `usb`, `bluetooth`, `socket.io`, `websocket`.
* `cryptography`: Cryptographic primitives and identity libraries. Includes: `crypto`, `bcrypt`,
  `x509`, `tls`/`ssl`, `jsonwebtoken`, `argon2`.
* `rce_funnel`: Spawning a shell/interpreter subprocess from application code — a common
  agentic-tool-use RCE shape. Includes: `child_process.spawn/exec/execSync` invoking
  `python`/`bash`/`sh`/`node`.
* `exfiltration_camouflage`: Outbound HTTP calls disguised as telemetry/metrics/audit traffic.
  Includes: `requests.post`/`urllib.request`/`httpx.post` whose payload references
  `telemetry`/`metrics`/`audit`-shaped keys.
* `memory_scraping`: Direct reads of process memory. Includes: `/proc/<pid>/mem`-style paths.
* `lazy_evaluation`: Generators and deferred-execution constructs. Includes: `yield`,
  `Generator`, `Iterator` (and their `Async*` counterparts).
* `vectorized_math`: Tensor/matrix math operations. Includes: `einsum`, `matmul`, `tensordot`,
  `.dot(`, the `@` matmul operator.
* `_named_token_capture`: Capture-group rule that extracts the exact imported symbol name(s)
  from a `from X import Y` statement, for dependency-graph precision beyond what the baseline
  `_dependency_capture` rule gives you.

### Literate-Programming Extension Pack (currently: `markdown`)
For languages that *are* documentation rather than executable code, but still have internal
structure worth mapping.

* `lit_code_blocks`: Fenced code block delimiters (` ``` `).
* `lit_diagrams`: Embedded diagram blocks (e.g. Mermaid).
* `lit_headers`: Section headers, for document structure/navigation mapping.
* `lit_links`: Cross-reference/hyperlink targets.

### Adding a new extension pack
If you're detecting a new category of risk that doesn't fit any baseline key and only applies
to a handful of languages, define it here the same way: a short name, its `re.compile(...)`
pattern, and a one-line INCLUDES description, listed under a new `### <Name> Extension Pack`
heading naming which languages carry it. Keep extension keys out of the baseline schema above —
that schema is the one every language is expected to implement to Strict Feature Parity (Rule
4); extension packs are deliberately the exception, not the rule.