# Lexical Stream Splicer

> **File Reference:** [`gitgalaxy/core/prism.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/prism.py)

The `LogicSplicer` module in `gitgalaxy/core/prism.py` acts as the source code tokenizer and stream separator for GitGalaxy. Once a file's language identity (`lang_id`) is confirmed, the splicer applies language-specific regular expression rules (`LanguageSpec`) to split the source file into two isolated streams: an **Executable Code Stream** (`coding_stream`) and a **Comment & Documentation Stream** (`comment_stream`).

Separating executable code from comments eliminates metric distortion caused by commented-out code blocks or documentation text.

---

## Structural Viability & Deflection Gates

Before executing full regular expression parsing, the splicer enforces viability checks:

* **Confidence Threshold Gate:** Files entering the splicer with confidence scores below `0.42` or belonging to declarative data formats (`json`, `yaml`, `csv`) bypass structural function slicing, registering as static file mass.
* **Prose Deflection:** Markdown (`.md`) and plaintext (`.txt`) files bypass code stream analysis, routing content directly to documentation metrics.
* **Header Override Gate:** Declarative C/C++ header files (`.h`) lacking traditional function braces often fail low-level confidence thresholds. If locked to a C-family language by `language_lens.py`, the splicer boosts parsing confidence to `1.0`, ensuring macro headers are fully analyzed.

---

## Atomic Literal Shielding

String literals containing braces (`{}`), parentheses (`()`), or quotes (`"`) can desynchronize bracket-tracking scope parsers. The splicer applies an **Atomic Literal Shield** to mask string content while preserving exact line counts and character index alignments:

* **Multi-Character Sequence Masking:** Processes complex string sequences prior to single quotes. Correctly masks C++ raw string literals (`R"EOF(...)EOF"`) and Python triple quotes (`"""`, `'''`) without prematurely triggering on internal double quotes.
* **Heredoc Isolation:** Deploys a line-by-line state machine for scripting languages (Bash, Ruby, Elixir) to isolate multi-line heredoc blocks (`<<-EOF`), masking content that contains shell control characters.
* **Ruby Sequence Masking:** Evaluates and masks Ruby bracketed string sequences (`%w[...]`, `%q{...}`, `%x(...)`), preventing internal brackets from corrupting keyword scope stacks.
* **Performance Guard (ReDoS Monitoring):** Times regular expression execution during shielding. If string masking takes longer than 0.5 seconds on obfuscated files, diagnostic warnings are logged to isolate backtracking bottlenecks.

---

## Code Stream vs. Comment Stream Separation

### 1. Executable Code Stream (`coding_analysis`)
Measures physical properties of executable logic:
* **Spatial Coordinate Mapping:** Records index coordinates for every structural match, enabling $O(N)$ spatial correlation checks:
  * **Taint Correlation:** Tracks untrusted I/O calls operating near dynamic execution calls (`eval`/`exec`).
  * **Suppression Checking:** Verifies if error suppression directives exist near unsafe execution blocks.
  * **Concurrency Checking:** Correlates state mutations against asynchronous thread spawns lacking mutex synchronization locks.
  * **Memory Leak Identification:** Matches memory allocation calls against cleanup calls to flag unmitigated allocations.
* **Orphan & Duplicate Function Detection:** Performs an $O(1)$ word-frequency tally across the file to flag unused or duplicated function declarations.
* **Token Mass & Structural Archetype Classification:** Calculates exact token count via `tiktoken` (`cl100k_base`) to compute LLM context costs. Calculates cyclomatic depth, recursion, and structural complexity (Gini index) to classify functions into structural archetypes (e.g., God Function, State Mutator, I/O Bridge).

### 2. Comment & Documentation Stream (`comment_analysis`)
Parses documentation literature independently from executable code:
* **Technical Debt Tracking:** Identifies planned debt markers (`TODO`, `FIXME`) and fragile debt markers (`HACK`, `XXX`).
* **Commented Code Detection (Graveyard Analysis):** Identifies commented-out execution blocks or hidden URL structures inside comments.
* **Documentation Density:** Measures documentation volume relative to code length to establish maintainability metrics.

---

## Integration Modes (5 Language Parsing Algorithms)

The Master Dispatcher selects one of five scope extraction modes based on language family:

* **Mode A: Label-Based Slicing (Procedural Languages):** Used for Assembly, AGC, and COBOL. Captures logic from target labels until reaching explicit return statements (`RET`, `GOBACK`, `END-PERFORM`).
* **Mode B: Recursive Scope Tracking (C-Family & Lisp):** Tracks nested braces (`{}`) or parentheses (`()`). Includes preprocessor shields to prevent floating macro braces (`#else {`) from corrupting scope stacks.
* **Mode C: Density Stratification (Python & YAML):** Evaluates indentation levels. Identifies structural keywords (`def`, `class`), records baseline indentation, and captures logic until indentation drops back to baseline.
* **Mode D: Semantic Keyword Stacking (Scripting Languages):** Used for Shell, Ruby, Lua, and Elixir. Tracks structural depth using keyword pairs (`if`/`fi`, `def`/`end`). Includes inline modifier guards to prevent single-line statements (`return if condition`) from corrupting depth counters.
* **Mode E: Terminator Cleaving (Declarative Languages):** Used for SQL, Erlang, and Prolog. Begins block collection on igniter keywords (`SELECT`, `CREATE`) and closes blocks upon encountering statement terminators (`;` or `.`).

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `prism.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository visualization engine.

---

**[⬅️ Back to Master Index](index.md)**

