### The Core Engine Test Suite

This directory contains the validation suite for GitGalaxy's core parsing pipeline.

Traditional static analysis relies on Abstract Syntax Trees (ASTs), which require a working
compiler toolchain and fail outright on a repository that's missing a dependency or won't
build. This suite validates that the heuristic **blAST Engine** (Bypassing LLMs and ASTs) can
deterministically map the structure of 50+ languages without ever building an AST.

For the overarching philosophy driving this engine, read the foundational brief: [The blAST Paradigm](../../docs/wiki/01-03-the-blast-paradigm.md).

---

### Running This Suite

These tests stress the core pipeline against ReDoS-shaped input, hanging Git streams, nested
language injection, and adversarially complex control flow. To run this suite in isolation:

```bash
python -m pytest tests/core_engine/ -v
```

---

### Test Index

The following tests validate the core stages of the [Pipeline Overview](../../docs/wiki/02-01-pipeline-overview.md). Click any component for its deep-dive doc.

#### 1. Ingestion
* **`test_aperture.py`** — Validates the [Aperture Filter](../../docs/wiki/02-03-aperture-filter.md). Proves the engine rejects AI model weights, exposed secrets, and massive embedded hex arrays before they reach the regex pool.
* **`test_guidestar_lens.py`** — Validates the [GuideStar Protocol](../../docs/wiki/02-04-guidestar-protocol.md). Proves the manifest-based baseline sensor correctly prioritizes project intent, extracts execution intents from manifests, and handles hostile `.gitignore` evasion attempts.
* **`test_language_lens.py`** — Validates the [Language Lens](../../docs/wiki/02-05-language-lens.md). Proves the engine can identify 50+ languages by content rather than trusting file extensions, catching files misnamed with the wrong extension and gracefully handling unidentifiable binaries.

#### 2. Structural Extraction (AST-Free Mapping)
* **`test_prism.py`** — Validates [The Prism](../../docs/wiki/02-07-the-prism.md). Proves the code/comment splitter correctly peels nested C-style block comments and shields string literals from falsely triggering structural-analysis logic.
* **`test_detector.py`** — Validates [The Detector](../../docs/wiki/02-08-the-detector.md). Proves the engine computes O(N) structural-branch counts, slices hybrid languages (e.g. JavaScript embedded in HTML), and generates the 3D spatial layout used by the WebGPU visualizer.

#### 3. Risk Scoring
* **`test_signal_processor.py`** — Validates [Signal Processing](../../docs/wiki/02-09-signal-processing.md). Proves the risk-exposure equations scale logic density against documentation correctly, reject recursive out-of-memory input, and compute API/concurrency exposure scores.
* **`test_language_standards_strict.py`** — Validates the strict [Language Standards](../../docs/wiki/06-02-language-standards.md). Proves ReDoS immunity: roughly 1,200 regexes are run in an isolated multiprocessing pool against pathological C/C++ macros and overlapping pointers, and the engine is required to never hang. This file itself only holds the registry-wide sanity checks and harness self-tests that don't belong to any single language — per-language coverage (one `test_<lang>_strict.py` per language, sharing a `_strict_harness.py` helper) lives in `../extraction/languages/`, colocated with that directory's own extraction-gauntlet tests.

#### 4. Execution & CI
* **`test_chronometer.py`** — Validates the [Chronometer](../../docs/wiki/02-15-chronometer.md). Proves the hard timeout reaps OS-level zombie processes during hanging Git streams so a CI run can't hang indefinitely.
* **`test_galaxyscope.py`** — Validates the [GalaxyScope CLI Reference](../../docs/wiki/01-02-galaxyscope-cli-reference.md). End-to-end integration test of a full scan run, proving all four output recorders (GPU, Audit, LLM, and SQLite) fire correctly.
