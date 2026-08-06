### COBOL & Mainframe Modernization Test Suite

This directory contains the validation suite for GitGalaxy's mainframe modernization
toolchain — the tools under `gitgalaxy/tools/cobol_to_cobol/` and `gitgalaxy/tools/cobol_to_java/`
that parse, refactor, and translate legacy COBOL/JCL without a compiler or emulator.

(Note: this file previously duplicated the top-level `tests/README.md`'s full index instead of
describing this directory specifically — see [`tests/README.md`](../README.md) for the
whole-suite index, and the rest of this file for what's actually under `tests/cobol_mainframe/`.)

---

### Running This Suite

```bash
python -m pytest tests/cobol_mainframe/ -v
```

---

### Test Index

#### 1. Dialect Detection & Normalization
* **`test_cobol_lexical_patcher.py`** — Validates the dialect sensor, which dates a file's COBOL compiler era (e.g. COBOL-74 vs. COBOL-85) from lexical clues, and the normalization pass that safely patches dialect-specific syntax without altering program logic.

#### 2. Data & Schema Translation
* **`test_cobol_etl_unpacker.py`** — Validates EBCDIC string translation and decoding of `COMP-3` packed-decimal hexadecimal boundaries.
* **`test_cobol_schema_forge.py`** — Validates the translation of legacy COBOL `PIC` clauses into modern data types for the generated Java schema.

#### 3. Execution Flow & Dead-Code Analysis
* **`test_cobol_dag_architect.py`** — Validates topological sorting and dead-branch pruning for mapping a program's exact execution order.
* **`test_cobol_graveyard_finder.py`** — Validates dead-code detection, including resolving local `.cpy` copybook files and inlining their contents before checking for orphaned variables and unreachable blocks.
* **`test_cobol_microservice_slicer.py`** — Validates the taint-tracking engine that traces variable aliases across operations to determine which logic can be safely sliced into an independent microservice boundary.

#### 4. JCL Handling
* **`test_cobol_jcl_auditor.py` & `test_cobol_jcl_forge.py`** — Validates JCL intent parsing, resource-bloat reduction, and least-privilege JCL generation for the translated job definitions.

#### 5. Code Generation & Orchestration
* **`test_cobol_compiler_forge.py`** — Validates the dialect-aware routing logic that generates correct JCL for a given detected COBOL dialect.
* **`test_cobol_refractor_controller.py`** — Validates the orchestrator's scale sensor: it estimates repository size up front and switches to a SQLite-backed state mode on large repositories to avoid holding the full intermediate representation in memory.
* **`test_cobol_system_limits_reporter.py`** — Validates the regex checks that flag COBOL constructs known to hit hard limits in common target runtimes (e.g. array/table size ceilings), plus the comment-shielding that keeps those checks from false-positiving inside comments.

#### 6. Autonomous Agent Handoff
* **`test_cobol_agent_task_forge.py`** — Validates the context merger for autonomous agents, checking that LLMs receive remediation tickets scoped to what's actually in the code, not speculative instructions.
