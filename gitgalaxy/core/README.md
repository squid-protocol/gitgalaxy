# GitGalaxy Core: Ingestion, Standardization, and Structural Detection

[![Pipeline](https://img.shields.io/badge/Pipeline-Phase_0_to_7-00BFFF.svg)](#)
[![Architecture](https://img.shields.io/badge/Architecture-AST--Free_Heuristics-8A2BE2.svg)](#)
[![Performance](https://img.shields.io/badge/Performance-Zero--Trust_Ingestion-FF4500.svg)](#)

Welcome to **GitGalaxy Core**. This directory serves as the frontline of the entire analysis engine. 

Before any risk equations are calculated or machine learning models are applied in the `metrics/` or `security/` directories, raw source code must be safely ingested, sanitized, and structurally identified. The modules in this directory are responsible for exactly that: transforming a chaotic, multi-gigabyte repository on disk into a standardized, mathematical state in RAM.

## The Why: Defensive Engineering & The AST-Free Paradigm

Enterprise repositories are rarely pristine. They contain minified vendor blobs, undocumented legacy monoliths, embedded malware, and broken syntax that refuses to compile. Traditional static analysis tools attempt to build Abstract Syntax Trees (ASTs) for these files, resulting in Out-Of-Memory (OOM) crashes, infinite loops, and pipeline timeouts.

GitGalaxy operates on a different philosophy: **Visualizing functional intent over rigid syntax parsing.** We bypass ASTs entirely. Instead, this core utilizes high-velocity, ReDoS-proof regular expressions to extract **Structural Signatures**. To achieve processing speeds exceeding 90,000 lines of code per second, the pipeline relies on extreme defensive engineering to protect the CPU and RAM from saturation.

---

## The What: The Information Flow (Module Breakdown)

Data flows through these modules sequentially. If a file is unparsable by this engine, we deal with it gracefully, attempting to extract as much information while routing the file to the **Unparsable Artifacts** queue, preventing pipeline bottlenecks.

### 1. `aperture.py` (The Boundary Filter)
**Role:** Zero-Trust Ingestion.
Information hits this filter first. It evaluates OS-level metadata (file path, extension, byte size) *before* executing any disk I/O. It actively shunts massive data dumps, neural network weights (`.safetensors`), and binary payloads masking as text files (via null-byte detection). This protects the Python memory space from immediate exhaustion.

### 2. `guidestar_lens.py` (Contextual Baselines)
**Role:** Architectural Intelligence.
Rather than guessing what a file does, this module parses explicit project manifests (`package.json`, `.gitattributes`, `Cargo.toml`). If a file is defined as a roadmap anchor or test suite by the developer, GuideStar assigns an **Intent Lock**. This provides a contextual baseline that bypasses expensive heuristic guessing downstream.

### 3. `prism.py` (Payload & Surface Splitter)
**Role:** Lexical Tokenization.
This module takes the raw string data and surgically decouples it into mutually exclusive components: the **Executable Payload** (coding_stream) and the **Documentation Surface** (comment_stream). It utilizes an O(1) atomic literal shield to temporarily mask strings during the split, preventing the regex scanner from accidentally mutating URLs or string contents that mimic comment delimiters.

### 4. `detector.py` (The Structural Extractor)
**Role:** Structural Signature Identification.
This file categorizes different keyword terms into structural signature counts. It evaluates the Executable Payload to slice the code into discrete functional blocks, map intra-file invocations, and detect critical security behaviors (e.g., I/O boundaries, state mutation, RCE triggers). 
* **Fluid-State Language Switching:** Rather than failing on polyglot files, the engine dynamically swaps syntax registries mid-file. It uses scope-aware handshakes to seamlessly isolate and parse embedded languages (e.g., evaluating SQL execution inside a Python string, or extracting JavaScript logic nested within HTML blocks) without losing context.
* **AST-Free Cyclomatic Complexity:** Instead of compiling an Abstract Syntax Tree, this module counts control-flow branch signatures (conditionals, loops, switches) directly from the lexical stream as a fast proxy for cyclomatic complexity, evaluating structural density at ~100,000 LOC/s. It does not infer algorithmic (Big-O) complexity or recursion depth from indentation shape -- an earlier heuristic that attempted this was removed after proving unreliable in practice (whitespace geometry doesn't measure algorithmic complexity, and name-occurrence recursion detection false-positived on docstrings, comments, and logging calls).

### 5. `network_risk_sensor.py` (The Topology Mapper)
**Role:** Dependency Graphing.
Once files are structurally parsed, this module wires them together into a Directed Acyclic Graph (DAG) using their raw import statements. It executes PageRank mathematics to determine each file's absolute **Dependency Blast Radius**, identifies **Architectural Choke Points**, and classifies their **Ecosystem Role** (Producer vs. Consumer).

### 6. `spatial_mapper.py` (The Positioning Engine)
**Role:** 3D Geometric Resolution.
Transforms the mathematical DAG into a deterministic 3D Cartesian coordinate map for the WebGPU visualizer. It groups files into directory clusters relative to high-impact central nodes.

### 7. `state_rehydrator.py` (The Cache Manager)
**Role:** Incremental Delta Scanning.
During CI/CD pipelines, it is highly inefficient to re-parse 10,000 unchanged files for a 2-file pull request. This module extracts the previous structural state from the SQLite database and rehydrates it directly into RAM, allowing the pipeline to skip the heavy regex extraction phases for unchanged artifacts.

---

## Engineering Highlights

If you are onboarding into the `core/` architecture, pay special attention to how we solve traditional static analysis scaling problems. By relying on high-velocity heuristics rather than heavy compilation steps, we achieve capabilities and speeds that standard tooling cannot match.

* **Multi-Tiered ReDoS Defense Architecture (`detector.py` & `prism.py`):** Regular Expression Denial of Service (ReDoS) is a critical threat when scanning unknown or minified code. We do not rely on a single timeout guillotine. The engine utilizes a three-tiered defense:
    1. **O(1) Atomic Literal Shielding:** Temporarily masks string literals to prevent the regex engine from catastrophically backtracking on overlapping quotes.
    2. **Line-Length Limiters:** Identifies abnormally long lines (e.g., hex arrays or minified data blobs) and truncates them before regex evaluation, while perfectly preserving the mathematical Lines of Code (LOC) count.
    3. **OS-Level Interrupts:** If a malformed file still traps the engine in an evaluation loop, a hardware-level OS interrupt fires after 15 seconds. It safely terminates the isolated worker process, downgrades the file to `plaintext`, and ensures the CI/CD pipeline never hangs.
* **Dynamic Mid-File Language Switching (`detector.py`):** Standard parsers routinely fail or miscategorize polyglot files (e.g., SQL logic embedded within a Python string, or JavaScript nested inside HTML). Instead of failing, the engine dynamically swaps syntax registries mid-file. It uses scope-aware handshakes to isolate and correctly parse embedded languages, preserving perfect structural context across 50+ languages.
* **AST-Free Cyclomatic Complexity (`detector.py`):** Compiling an Abstract Syntax Tree to determine cyclomatic nesting depth requires massive overhead. GitGalaxy bypasses this by counting control-flow branch signatures directly from the lexical stream as a fast proxy for cyclomatic complexity, evaluating structural density at speeds exceeding 90,000 LOC/second. This deliberately stops short of inferring algorithmic (Big-O) complexity or recursion depth from code shape -- a prior heuristic attempting that was removed for producing systematic false positives.
* **Recall vs. Exhaustiveness (By Design):** GitGalaxy optimizes for near-total structural recall at heuristic speed, not byte-for-byte AST completeness, and has two explicit, intentional boundaries. `aperture.py` excludes pathological single-file monoliths outright (30,000+ LOC, or content matching binary/minified/machine-generated-source heuristics) to protect the regex engine from catastrophic backtracking. `detector.py` caps per-file function extraction at a fixed ceiling to bound memory and CPU on extremely dense files. Both trade a small amount of recall on the long tail of pathological files for guaranteed bounded runtime across the rest of a repository.
* **Topological Call Graphs & Architectural Test Coverage (`network_risk_sensor.py`):** Recreating a granular, cross-repository function call graph using Abstract Syntax Trees (ASTs) is computational overkill for DevSecOps. ASTs require perfectly compiling code, massive memory overhead, and brittle, language-specific parsers. We bypass this bottleneck by utilizing a high-velocity topological proxy. By mapping file-level `import` statements to establish ecosystem boundaries, and extracting targeted outbound function invocations via structural signatures, we achieve the necessary precision at a fraction of the compute cost. This allows us to calculate the systemic **Dependency Blast Radius** of specific logic purely in RAM. For example, by mapping outbound calls from test files directly to their production targets, we mathematically calculate the exact architectural vulnerability footprint of untested modules across polyglot microservices.
* **The Repository Knowledge Graph (Core Vision):** All of these extractions culminate in a unified mathematical model of the codebase. By treating files as **Nodes** and import statements as **Edges**, we stitch together a cross-repository Knowledge Graph. We then overlay our extracted *Structural Signatures* (state mutations, I/O boundaries, RCE triggers) directly onto these nodes as properties. This provides deep, queryable clarity into how vulnerable information flows across polyglot microservices, surfacing systemic risks that isolated file scanners miss.

## 🌌 The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy Core is the foundational ingestion layer of the broader **GitGalaxy Ecosystem**—a high-velocity, AST-free, LLM-free heuristic knowledge graph engine designed to extract knowledge from any repository.

Explore the ecosystem:

* 🪐 **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* 🔭 **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* 📖 **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* ⚙️ **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.