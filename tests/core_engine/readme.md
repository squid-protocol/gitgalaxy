### ⚙️ Mathematical Proofs: The blAST Core Engine

This directory contains the strict structural validation and physics gauntlets for the GitGalaxy Core Engine.

Traditional static analysis relies on Abstract Syntax Trees (ASTs), which are slow, strictly monolingual, and instantly fail if a repository is missing a single dependency or refuses to compile. This test suite exists to mathematically prove that our heuristic **blAST Engine** (Bypassing LLMs and ASTs) can deterministically map the physical architecture of 50+ languages at extreme velocities—without ever building an AST.

For the overarching philosophy driving this engine, read the foundational brief: [The blAST Paradigm](../../docs/wiki/01-03-the-blast-paradigm.md).

---

### 🧪 Execution Protocols

These gauntlets stress-test the core physics engine against pathological ReDoS attacks, infinite Git streams, nested language injections, and extreme algorithmic complexity. To run this specific validation suite in isolation:

```bash
python -m pytest tests/core_engine/ -v
```

---

### 📂 Verified Capabilities & Documentation Index

The following tests validate the core stages of the [Pipeline Overview](../../docs/wiki/02-01-pipeline-overview.md). Click on any component to review its deep-dive architectural physics.

#### 1. Optical Orchestration & Ingestion (The Gates)
* **`test_aperture.py`** — Validates the [Aperture Filter](../../docs/wiki/02-03-aperture-filter.md). Proves the engine securely shields against structural anomalies, instantly blocking AI model weights, exposed secrets, and massive embedded hex arrays before they poison the regex pool.
* **`test_guidestar_lens.py`** — Validates the [GuideStar Protocol](../../docs/wiki/02-04-guidestar-protocol.md). Proves the Bayesian ecosystem sensor correctly prioritizes Sector Bias, extracts execution intents from manifests, and traps hostile `.gitignore` evasion tactics.
* **`test_language_lens.py`** — Validates the [Language Lens](../../docs/wiki/02-05-language-lens.md). Proves the engine can identify 50+ languages natively, deploying "Identity Crisis" traps for files lying about their extensions and executing Spectral Scans on unidentifiable binaries.

#### 2. Structural Refraction & Topology (AST-Free Mapping)
* **`test_prism.py`** — Validates [The Prism](../../docs/wiki/02-07-the-prism.md). Proves the optical splitting matrix safely peels nested C-style block comments and shields complex string literals from falsely triggering structural analysis logic.
* **`test_detector.py`** — Validates [The Detector](../../docs/wiki/02-08-the-detector.md). Proves the engine can calculate exact O(N) algorithmic depth natively, slice hybrid languages (e.g., JavaScript inside HTML), and generate the 3D spatial cartography required for the WebGPU visualizer.

#### 3. Threat Sensors & Signal Physics (The Math)
* **`test_signal_processor.py`** — Validates [Signal Processing](../../docs/wiki/02-09-signal-processing.md). Proves the 13-point risk exposure equations deterministically scale logic density against documentation, deflecting recursive OOM (Out of Memory) bombs and calculating precise API and concurrency exposures.
* **`languages/test_<lang>_strict.py`** — Validates our strict [Language Standards](../../docs/wiki/06-02-language-standards.md), one file per language (mirroring `tests/extraction/languages/`; suffixed `_strict` so its basenames don't collide with that directory's own `test_<lang>.py` files under pytest's default import mode, since this repo has no `tests/__init__.py` anywhere). Proves absolute Catastrophic Backtracking (ReDoS) immunity. We lock our 1,200+ regexes inside an isolated "Blast Chamber" multiprocessing pool (`languages/_strict_harness.py`) and fire pathological C/C++ macros and overlapping pointers at them to guarantee the engine will never hang. `test_language_standards_strict.py` itself now holds only the registry-wide sanity checks and harness self-tests that don't belong to any single language.

#### 4. Execution & Continuous Integration (The Run Loop)
* **`test_chronometer.py`** — Validates the [Chronometer](../../docs/wiki/02-15-chronometer.md). Proves the hardware kill-switch can successfully reap OS-level zombie processes during hanging Git streams, ensuring pipeline stability during high-velocity CI/CD runs.
* **`test_galaxyscope.py`** — Validates the [GalaxyScope CLI Reference](../../docs/wiki/01-02-galaxyscope-cli-reference.md). Performs end-to-end integration testing of the entire mission lifecycle, proving that all four output recorders (GPU, Audit, LLM, and SQLite) fire accurately and successfully.