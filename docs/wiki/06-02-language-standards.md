# Language Standards Registry

> **File Reference:** [`gitgalaxy/standards/language_standards.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/standards/language_standards.py)

The `language_standards.py` module is the central language definition registry in GitGalaxy. It supplies regular expression schemas, syntax delimiters, comment parsing definitions, and function extraction rules used by the file parser and static analysis engines.

By centralizing language specifications in this registry, GitGalaxy allows developers to add support for new programming languages, proprietary scripts, or domain-specific languages (DSLs) without altering core parsing code.

## The 51-Element Universal Metrics Schema (`UNIVERSAL_METRICS_SCHEMA`)

To ensure downstream processing engines (such as statistical analysis modules, export recorders, and WebGL visualizers) receive predictable data structures, GitGalaxy enforces a standardized `UNIVERSAL_METRICS_SCHEMA`.

Regardless of the target language, extracted syntax heuristics map directly into a fixed 51-element numerical array. This allows control flow structures, variable declarations, and function signatures across diverse programming paradigms (e.g., C++, Python, Lisp, SQL) to be compared on a consistent mathematical scale. Unregistered metrics or schema violations are filtered out during ingestion.

## The Language Definitions Registry (`LANGUAGE_DEFINITIONS`)

The core dictionary in `language_standards.py` is `LANGUAGE_DEFINITIONS`. Each supported language includes a definition block containing four key configurations:

### 1. Ecosystem Metadata
* **`extensions`:** List of supported file extensions (e.g., `['.js', '.jsx', '.ts']`). Used during initial file classification.
* **`disqualifiers`:** Regular expressions that filter out false positives. If a file matching a Python extension contains language patterns exclusive to PHP (such as `<?php`), the classifier rejects the match.
* **`handicap`:** Weight adjustment factor (typically `1.0`). Languages with broad or generic keyword sets (such as ABAP or Fortran) receive a reduced weight (e.g., `0.4`) to prevent over-matching during multi-language discovery scans.

### 2. Function Extraction Mode (Parsing Strategy)
Specifies the extraction algorithm used to slice source code files into discrete functions:
* **Mode A (Label-Based):** For procedural or label-defined languages (Assembly, COBOL).
* **Mode B (Recursive Scope):** For block-scoped languages utilizing braces `{}` or parentheses `()` (C/C++, Java, Rust, Go).
* **Mode C (Density Stratification):** For indentation-sensitive languages (Python, YAML).
* **Mode D (Semantic Handshake):** For keyword-bounded block scripts (Ruby, Elixir, Bash).
* **Mode E (Terminator Cleaving):** For statement-terminated declarative syntaxes (SQL, Erlang).

### 3. Comment and String Handling
Maps each language to one of nine standardized comment extraction handlers (e.g., `std_c` for `//` and `/* */`, `pure_hash` for `#`, `hybrid_dash` for `--`). This enables comment stripping without corrupting string literals.

### 4. Syntax Patterns and Security Heuristics
Maps syntax constructs to standardized metric indices within the 51-element schema:
* **Control Flow & Structure:** Matches branching keywords (`if`, `else`, `switch`, `for`, `while`) and structural statements.
* **Security Triggers:** Matches dangerous APIs, dynamic execution calls (e.g., `eval()`, `child_process.exec()`), and file/network I/O functions for risk analysis.

## Adding Support for New Languages

Because parsing engines build their rule sets dynamically from `language_standards.py` at startup, supporting a new language does not require changes to core parsing logic.

To introduce a new language:
1. Open `language_standards.py`.
2. Add a new entry to the `LANGUAGE_DEFINITIONS` dictionary.
3. Define the associated file extensions, parsing mode, comment handler, and regular expression schemas.
4. On startup, the language classifier and parser will automatically load the blueprint and process files matching the registered extensions.

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

