# GitGalaxy Test Suite

This directory holds the test suite for the GitGalaxy engine — the source of truth behind
every structural-signature, ReDoS-immunity, and accuracy claim in the main
[`README.md`](../README.md).

An AST-free, regex/lexical parser has two distinct ways to fail silently: matching the wrong
thing (false positives, false negatives) and matching pathologically slowly (ReDoS,
catastrophic backtracking). This suite exists to catch both, for every rule the engine ships,
rather than asserting the approach is immune to the tradeoffs that come with skipping an AST.

It validates GitGalaxy's structural extraction rules, enforces ReDoS-immunity bounds across
the 2,406 production rule patterns, and checks deterministic output across the 56 languages
that have real structural signatures (65 languages/formats registered, including pure data
formats with nothing to signature-match), plus the mainframe pipeline and the COBOL-to-Java
proofs. As of 2026-10-01, `python -m pytest tests/ --collect-only -q` collects 13,281 tests.

---

## Index

### 1. `/core_engine` — Parsing and Processing Core
Covers the engine's core parsing and scoring logic: the AST-free parsers, ReDoS timeouts,
execution lifecycle, and the risk-scoring math.

* **`test_language_standards_strict.py`** — Registry-wide sanity checks (every regex in `LANGUAGE_DEFINITIONS` compiles), the ReDoS harness's own self-tests, and the one test explicitly written (issue #713) as a single parametrized cross-language test rather than duplicated 17 times. The per-language structural-signature tests that used to live here now live in `/extraction/languages` (see below) — split out the same way `/extraction`'s own four gauntlet files were.
* **`test_detector.py`** — Validates the core extractor. Proves nested functions and nested classes are extracted as their own correctly-scoped nodes rather than being dropped or truncating their enclosing scope, applies blast-radius risk multipliers based on dependency-graph position, and checks the ReDoS line-length limiter.
* **`test_signal_processor.py`** — Validates the risk-exposure scoring math: no divide-by-zero crashes on zero-signal input, sigmoid overflow clamping at high densities, and logarithmic normalization for git-history-derived time signals.
* **`test_licensing.py`** — Validates the PolyForm compliance gate, offline HMAC-SHA256 key verification, and CI/CD audit-tripwire behavior for enterprise environments.
* **`test_chronometer_timeout.py`** — Validates the hard scan timeout: simulates a hanging Git stream and checks that a `SIGKILL` is sent, pipes are flushed, and file descriptors are closed so the process doesn't leak RAM.

### 2. `/extraction` — Structural Extraction Gauntlets
Large, parameterized testing matrices that fire thousands of mutated code snippets across
every supported language, organized into three tiers: **Valid** (does it match real, idiomatic
code), **Invalid** (does it correctly reject the documented lookalike), and **Pathological**
(does it survive adversarial or malformed input without hanging).

* **`/extraction/languages`** — One `test_<lang>.py` per language for the four extraction gauntlets below plus a colocated, `_strict`-suffixed `test_<lang>_strict.py` per language — the direct, per-language proof behind every "structural signature" claim GitGalaxy makes (4,884 tests across 56 languages, sharing a `_strict_harness.py` ReDoS-testing helper module the same way the extraction files share `_extraction_harness.py`). The `_strict` suffix keeps the two sets of basenames from colliding under pytest's default import mode, since this repo has no `tests/__init__.py` anywhere. The `gitgalaxy/standards/language_standards/` package registers 65 languages/formats; 56 of them define real structural signatures (the rest — `json`, `xml`, `csv`, ... — are pure data formats with nothing to structurally signature-match), totaling 2,406 rule patterns. For every one of those 56 languages, its `_strict.py` file enforces a strict per-signature template:
  1. **Positive match** — the rule fires on a realistic snippet of its own documented, included construct.
  2. **Negative match** — the rule does *not* fire on the documented excluded construct (the false-positive check most naive regex test suites skip entirely).
  3. **Cross-rule ambiguity** — where two signatures share a token (e.g. C#'s `event ... += handler` firing both `events` and `listeners`), the test asserts the overlap is intentional and named, not an accidental collision.
  4. **ReDoS immunity** — every rule with an unbounded-looking quantifier is scaled from 2,000 to 100,000+ characters of adversarial input and timed in an isolated, kill-switched subprocess (`assert_redos_immune`), so no rule can hang a real scan. To confirm this timeout doesn't just mask true $O(n^2)$ behavior, a global geometric sweep (`tests/extraction/tools/sweep_redos_scaling.py`) checks that scaling stays linear across all heuristics.
  This template was initially applied under [epic #518](https://github.com/squid-protocol/gitgalaxy/issues/518), and subsequently deepened with more adversarial matrices (edge-case formatting, noise thresholds, strict boundary checks) under [epic #1071](https://github.com/squid-protocol/gitgalaxy/issues/1071). Both epics turned up and fixed dozens of real, previously-undetected regex bugs along the way — not just theoretical coverage. The full recurring-bug-class checklist this accumulated (16 numbered engine rules, from ReDoS shapes to schema completeness) lives in [`how_to_add_a_language.md`](../gitgalaxy/standards/how_to_add_a_language.md), the canonical spec every one of these tests is written against.
* **`test_function_extraction.py`** — Proves the engine can pinpoint exact function names while stepping over long attribute chains, explicit return types, and C++ macro noise.
* **`test_class_extraction.py`** — Proves the engine can isolate the precise name of an object-oriented entity while ignoring inheritance chains, generics, and visibility modifiers.
* **`test_args_extraction.py`** — Proves the engine can parse large parameter blocks and multi-line lambda closures without a ReDoS spiral from nested parentheses.
* **`test_dependency_extraction.py`** — Proves the engine can extract the exact file path from an import statement, ignoring aliases and destructuring syntax.

### 3. `/security_auditing` — Threat Intelligence and AppSec
Validates the vulnerability, compliance, and dependency-audit sensors. These tests check that
the engine can flag real threat classes using structural pattern-matching, without relying on
dynamic execution.

* **`test_dev_agent_firewall.py`** — Validates AI-agent guardrails: flags files whose combined size and complexity would blow an autonomous agent's context budget ($O(N^3)$ scaling), enforces human-in-the-loop gates on high-risk file modifications, and flags mutations to files with low test coverage.
* **`test_vault_sentinel.py`** — Validates the multi-tiered secrets scanner: a denylist match and a deeper entropy-based scan can each independently halt a pipeline on leaking credentials.
* **`test_binary_anomaly_detector.py`** — Validates the binary-inspection engine: magic-byte mismatches (e.g. an executable disguised as a `.jpg`) and high-entropy payloads consistent with encryption.
* **`test_network_risk_sensor.py`** — Validates the dependency-graph math (PageRank, betweenness centrality) without relying on heavy external dependencies.
* **`test_redos_poison.py`** — Spawns an isolated 8-core multiprocessing pool to run every production rule pattern against classic ReDoS payloads, checking pipeline stability under adversarial input at scale.

### 4. `/cobol_mainframe` — Legacy Modernization
The mainframe extraction tools and the COBOL-to-Java pipeline: the generated project, the porting
tickets and loop, and the equivalence proofs (93 test files; see
[`cobol_mainframe/readme.md`](cobol_mainframe/readme.md) for the full index, and
[`equivalence/`](equivalence) for the proof cases). A sample:

* **`test_cobol_etl_unpacker.py`** — Validates EBCDIC string translation and decoding of `COMP-3` packed-decimal hexadecimal boundaries.
* **`test_cobol_dag_architect.py`** — Validates topological sorts and dead-branch pruning for mapping exact execution flow.
* **`test_cobol_jcl_auditor.py` & `test_cobol_jcl_forge.py`** — Validates JCL intent parsing, resource-bloat reduction, and least-privilege JCL generation.
* **`test_cobol_agent_task_forge.py`** — Validates the context merger for autonomous agents, checking that LLMs receive remediation tickets scoped to what's actually in the code, not speculative instructions.
* **`test_equivalence*.py`, `test_porting_loop_tooling.py`, `test_mutation_tooling.py`** — The proof that a ported Java program matches its COBOL (records, SYSOUT, CICS screens, fault runs), the porting loop, and mutation testing of the proofs. The end-to-end proofs run with `EQUIVALENCE_E2E=1` (Docker GnuCOBOL + JDK 17).

### 4b. Other suites
* **`/cics_crucible`** — The [CICS crucible](../docs/language_status/cics_crucible.md): small CICS applications built around known migration traps, per side (engine facts, compile, the COBOL under a stub CICS, the generated Java, the ported Java), held by a ratchet.
* **`/cultural_gauntlet`, `/unicode_gauntlet`** — National characters, code pages and cultural conventions (decimal comma, calendars) through the engine and the generated Java.
* **`/tools`** — The repository's own tooling (audit gates, baselines, comparison harnesses).
* **Root audit gates** — `ruff_audit.py`, `mypy_audit.py`, `signal_contract_audit.py`, `dead_key_audit.py` (baseline-gated, run by `tests/tools/audit_check.py`), and `test_source_reads.py` (no lossy decode of an estate's bytes, #3813).

### 5. Golden Master Differential Testing (the Language Crucible)
Everything above is a synthetic unit test — a snippet written by hand to probe one specific
rule. This section is different: it's the check that the whole engine, wired together,
produces the right answer on real, unmodified production source code, not just on the
adversarial strings a test author thought to write.

**[`language-crucible`](https://github.com/squid-protocol/language-crucible)** is a companion repository: ~120 real subdirectories of production code pulled directly from significant open-source projects (Godot's C++, the Roslyn C# compiler, curl, Kubernetes, Apollo 11's AGC flight software, and dozens more), deliberately left disconnected and uncompilable — the same hostile, dependency-broken state real repos are in. See its own README for the full list of paradigms it's built to stress.

GitGalaxy pins that corpus to a tagged release (`v1.7.0` as of 2026-10-01 — the single source of truth is `tests/crucible_pins.toml`, which every crucible/tri-comparison/tree-sitter-accuracy workflow clones against (`python tests/tools/crucible_pins.py get language`; `check` / `sync` keep local checkouts on it); see [`docs/self_scan/BUMPING_THE_CRUCIBLE_PIN.md`](../docs/self_scan/BUMPING_THE_CRUCIBLE_PIN.md) for the full bump checklist, and language-crucible's own `RELEASING.md` for that repo's side of the process) and checks two files into this repo — `tests/golden_master_audit/` and `tests/golden_master_zero_dep_audit/` — deterministic snapshots of a full scan over the entire corpus, one for each of the engine's two dependency modes (full-precision and zero-dependency). `tests/test_golden_crucible.py` (driven by the `crucible-audit` GitHub Actions job, which runs automatically on every pull request in both modes) re-runs `galaxyscope` against a fresh clone of that same pinned corpus and diffs the output against the checked-in snapshot, field by field, down to individual structural-signature counts per file.

**A failing diff means GitGalaxy's output changed on real code.** That's either a regression (fix the engine) or a deliberate improvement (the fixture gets re-blessed via `tests/tools/update_golden_master.py`, which shows the full diff and requires explicit confirmation — never a blind `cp`). Every bug fixed across [epic #518](https://github.com/squid-protocol/gitgalaxy/issues/518) was verified this way before merging: not just "the new regex passes its own unit test," but "the new regex's output on `godot/`, `roslyn/`, `curl/`, and the rest of the real corpus changed in exactly the way the fix predicts, and nowhere else." `tests/tools/crucible_check.py` is the one-command local equivalent of the CI job, for verifying this before a PR is even opened.
