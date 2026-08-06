# 🌌 Mathematical Proofs: The Master Test Suite

This directory contains the testing architecture and physics gauntlets for the GitGalaxy engine. 

Building a planetary-scale, polyglot parser without relying on an Abstract Syntax Tree (AST) or a compiler toolchain is widely considered impossible. Traditional regex approaches hallucinate architecture and inevitably crash corporate pipelines via Catastrophic Backtracking (ReDoS). 

This test suite exists to mathematically prove the opposite. It aggressively validates GitGalaxy's structural extraction, enforces absolute ReDoS immunity across 1,200+ heuristics, and ensures zero-trust deterministic accuracy across 30+ programming languages and 40-year-old legacy mainframes.

---

## 📂 Architectural Proof Index

### 1. `/core_engine` (The Physics & Parsing Core)
This domain is the beating heart of GitGalaxy's structural physics. It validates the AST-free parsers, ReDoS shields, execution lifecycles, and mathematical models that allow the engine to operate flawlessly under extreme, adversarial conditions.

* **`test_language_standards_strict.py`** — Registry-wide sanity checks (every regex in `LANGUAGE_DEFINITIONS` compiles), the ReDoS harness's own self-tests, and the one test explicitly written (issue #713) as a single parametrized cross-language test rather than duplicated 17 times. The per-language structural-signature tests that used to live here now live in `/extraction/languages` (see below) — split out the same way `/extraction`'s own four gauntlet files were.
* **`test_detector.py`** — Validates the Logic Splicer. Proves nested functions and nested classes are extracted as their own correctly-scoped nodes rather than being dropped or truncating their enclosing scope, applies AppSec Spatial Correlation (blast radius multipliers), and safely implements the Anti-ReDoS Line Limiter.
* **`test_signal_processor.py`** — Validates the 18-point risk exposure math. Ensures Zero-State Resiliency (no divide-by-zero crashes), Sigmoid Overflow Clamping for massive densities, and Logarithmic Temporal Normalization.
* **`test_documentation_sensor.py`** — Validates the heuristic physics for code-to-comment density. Proves the engine correctly applies mass multipliers and complexity accelerants to eliminate false-positive fatigue on small files.
* **`test_licensing_guard.py`** — Validates the PolyForm compliance gate, offline HMAC-SHA256 cryptographic key verification, and the execution of CI/CD audit tripwires for enterprise environments.
* **`test_chronometer_timeout.py`** — Validates the Hardware Guillotine. Simulates a hanging Git stream and ensures the OS-level `SIGKILL` is sent, pipes are forcefully flushed, and file descriptors are closed to prevent RAM leaks.

### 2. `/extraction` (The Strict Gauntlets)
Because our heuristics *are* the compiler, these massive, parameterized testing matrices fire thousands of mutated code snippets across all supported languages using a 3-Tier Matrix: **Valid** (The Iron Wall), **Invalid** (Ghost Prevention), and **Pathological** (Frankenstein formatting).

* **`/extraction/languages`** — One `test_<lang>.py` per language for the four extraction gauntlets below (see `readme.md` in that directory), plus a colocated, `_strict`-suffixed `test_<lang>_strict.py` per language — the direct, per-language proof behind every "structural signature" claim GitGalaxy makes (2,536 tests across 45 languages, sharing a `_strict_harness.py` ReDoS-testing helper module the same way the extraction files share `_extraction_harness.py`). The `_strict` suffix keeps the two sets of basenames from colliding under pytest's default import mode, since this repo has no `tests/__init__.py` anywhere. `gitgalaxy/standards/language_standards.py` recognizes 58 languages/formats; 45 of them define real structural signatures (the rest — `json`, `xml`, `csv`, ... — are pure data formats with nothing to structurally signature-match), totaling ~1,970 compiled regex patterns. For every one of those 45 languages, its `_strict.py` file enforces a strict per-signature template:
  1. **Positive match** — the rule fires on a realistic snippet of its own documented, included construct.
  2. **Negative match** — the rule does *not* fire on the documented excluded construct (the false-positive check most naive regex test suites skip entirely).
  3. **Cross-rule ambiguity** — where two signatures share a token (e.g. C#'s `event ... += handler` firing both `events` and `listeners`), the test asserts the overlap is intentional and named, not an accidental collision.
  4. **ReDoS immunity** — every rule with an unbounded-looking quantifier is scaled from 2,000 to 100,000+ characters of adversarial input and timed in an isolated, kill-switched subprocess (`assert_redos_immune`), so no rule can ever hang a real scan. To mathematically prove this timeout doesn't mask true $O(n^2)$ behavior, we run a global geometric sweep (`tests/extraction/tools/sweep_redos_scaling.py`) that guarantees linear scaling across all heuristics.
  This template was applied to all 45 languages under [epic #518](https://github.com/squid-protocol/gitgalaxy/issues/518), which turned up and fixed dozens of real, previously-undetected regex bugs along the way — not just theoretical ones. The full recurring-bug-class checklist this epic accumulated (16 numbered engine rules, from ReDoS shapes to schema completeness) lives in [`how_to_add_a_language.md`](../gitgalaxy/standards/how_to_add_a_language.md), the canonical spec every one of these tests is written against.
* **`test_function_extraction.py`** — Proves the engine can pinpoint exact function names while stepping over massive attribute stacks, explicit return types, and C++ macro garbage.
* **`test_class_extraction.py`** — Proves the engine can isolate the precise name of an Object-Oriented entity while ignoring complex inheritance chains, generics, and visibility modifiers.
* **`test_args_extraction.py`** — Proves the engine can swallow massive parameter blocks and multi-line lambda closures without collapsing into a ReDoS spiral caused by nested parentheses.
* **`test_dependency_extraction.py`** — Proves the engine can trace information flow by extracting the exact file path from an import statement, ignoring aliases and destructuring syntax.

### 3. `/security_auditing` (Threat Intelligence & AppSec)
Validates the vulnerability, compliance, and zero-trust intelligence sensors. Instead of relying on fragile dynamic execution, these tests prove we can spot threats using pure structural mathematics.

* **`test_dev_agent_firewall.py`** — Validates AI guardrails, mathematically flagging Context Window Shredders (massive $O(N^3)$ files), enforcing HITL (Human-in-the-Loop) Mandates, and detecting Silent Mutation Risks.
* **`test_vault_sentinel.py`** — Validates the multi-tiered secrets scanner, proving the Denylist Wall and Deep Scan Traps can instantly halt pipelines leaking credentials.
* **`test_binary_anomaly_detector.py`** — Validates the X-Ray engine, spotting Magic Byte Mismatches (e.g., an executable disguised as a `.jpg`) and High-Entropy encrypted payloads.
* **`test_network_risk_sensor.py`** — Validates N-Dimensional graph physics (PageRank, Betweenness centrality) without relying on heavy external dependencies.
* **`test_redos_poison.py`** — Spawns an isolated 8-core multiprocessing pool to blast all 1,200+ production heuristics with classic ReDoS payloads to guarantee absolute pipeline stability.

### 4. `/cobol_mainframe` (Legacy Modernization)
Mathematically proves the engine can bridge the gap between 40-year-old EBCDIC IBM mainframes and modern Zero-Trust architectures without relying on compilers or emulators.

* **`test_cobol_etl_unpacker.py`** — Validates EBCDIC string translation and mathematical decoding of `COMP-3` packed decimal hexadecimal boundaries.
* **`test_cobol_dag_architect.py`** — Validates Topological Sorts and the "Ghost Deflector" for mapping exact execution flow.
* **`test_cobol_jcl_auditor.py` & `test_cobol_jcl_forge.py`** — Validates JCL intent parsing, Bloat Reduction math, and Zero-Trust least-privilege JCL generation.
* **`test_cobol_agent_task_forge.py`** — Validates the context merger for autonomous agents, ensuring LLMs receive strict JSON remediation tickets bounded by reality.

### 5. Golden Master Differential Testing (The Language Crucible)
Everything above is a synthetic unit test — a snippet written by hand to probe one specific rule. This section is different: it's the empirical check that the whole engine, wired together, produces the *right* answer on real, unmodified production source code, not just on the adversarial strings a test author thought to write.

**[`language-crucible`](https://github.com/squid-protocol/language-crucible)** is a companion repository: ~120 real subdirectories of production code pulled directly from significant open-source projects (Godot's C++, the Roslyn C# compiler, curl, Kubernetes, Apollo 11's AGC flight software, and dozens more), deliberately left disconnected and uncompilable — exactly the hostile, dependency-broken state GitGalaxy has to handle in the real world. See its own README for the full list of paradigms it's built to stress.

GitGalaxy pins that corpus to a tagged release (`v1.0`) and checks two files into this repo — `tests/golden_master_audit.json` and `tests/golden_master_zero_dep_audit.json` — deterministic snapshots of a full scan over the entire corpus, one for each of the engine's two dependency modes (full-precision and zero-dependency). `tests/test_golden_crucible.py` (driven by the `crucible-audit` GitHub Actions job, which runs automatically on every pull request in both modes) re-runs `galaxyscope` against a fresh clone of that same pinned corpus and diffs the output against the checked-in snapshot, field by field, down to individual structural-signature counts per file.

**A failing diff means GitGalaxy's output changed on real code.** That's either a regression (fix the engine) or a deliberate improvement (the fixture gets re-blessed via `tests/tools/update_golden_master.py`, which shows the full diff and requires explicit confirmation — never a blind `cp`). Every bug fixed across [epic #518](https://github.com/squid-protocol/gitgalaxy/issues/518) was verified this way before merging: not just "the new regex passes its own unit test," but "the new regex's output on `godot/`, `roslyn/`, `curl/`, and the rest of the real corpus changed in exactly the way the fix predicts, and nowhere else." `tests/tools/crucible_check.py` is the one-command local equivalent of the CI job, for verifying this before a PR is even opened.
