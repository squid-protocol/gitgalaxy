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

### THE LEXICAL PARSING FAMILIES
You must assign the language to one of these 5 lexical parsing families based on how it handles comments and non-executable text:
* `standard_block`: The language uses both line and block delimiters, but blocks CANNOT be nested. Examples: C, C++, Java, JavaScript, PHP, SQL, Go, Ruby, Lua.
* `recursive_block`: The language allows block comments to be safely nested inside one another. Examples: Rust, Swift, Dart, Scala.
* `line_exclusive`: The language possesses no native multi-line block syntax. The engine ignores closing tags. Examples: Python, Shell, Makefile, Assembly, Scheme.
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
    "rules": {
        # --- LEXICAL DELIMITER CONTROLS ---
        "_line_anchor": re.compile(r""), 
        "_inline_comment": re.compile(r""),
        "_block_start": re.compile(r""),
        "_block_end": re.compile(r""),

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