# Lexical Control Flow Preprocessor

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_lexical_patcher.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_lexical_patcher.py)
>
> **Architecture: Preprocessing & Control Flow Normalization**
>
> **Summary:** The Lexical Patcher is a source code preprocessor that identifies legacy control flow constructs (such as `NEXT SENTENCE`) and safely refactors them into explicit scope terminators (`CONTINUE`) prior to Abstract Syntax Tree (AST) parsing or static analysis.

## Compiler Dialect Detection

Because altering legacy source code can introduce compiler incompatibilities, the patcher includes a dialect sensor (`detect_cobol_dialect`) to inspect the target source file for modern structural features.

* **Modern Language Signatures:** Scans for COBOL-85 features such as `EVALUATE`, `INITIALIZE`, explicit scope terminators (`END-IF`, `END-PERFORM`, `END-READ`, `END-EVALUATE`, `CONTINUE`), or inline comments (`*>`).
* **Dialect Classification:** Classifies the source file as `COBOL-85` (modern dialect) or `COBOL-74` (legacy dialect) to govern transformation safety.

## Control Flow Refactoring

The `NEXT SENTENCE` directive skips execution forward to the statement following the next period (`.`), creating implicit control flow branches that complicate static dependency extraction and AST generation. The `patch_lexical_traps` function remediates this as follows:

* **COBOL-85 Mode:** Refactors `NEXT SENTENCE` into a block-scoped `CONTINUE` statement and inserts an inline tracking comment (`CONTINUE *> GitGalaxy Patch: Neutralized Flow Control Anomaly`).
* **COBOL-74 Mode:** Leaves the `NEXT SENTENCE` syntax intact to preserve strict compiler compatibility, but standardizes surrounding whitespace to ensure predictable parsing by downstream extraction engines.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**

