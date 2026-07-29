# Project Manifest and Metadata Resolution

> **File Reference:** [`gitgalaxy/core/guidestar_lens.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/guidestar_lens.py)

The `GuideStarLens` module in `gitgalaxy/core/guidestar_lens.py` acts as the project metadata parser and contextual intelligence engine for GitGalaxy. While the file filter (`aperture.py`) excludes unwanted binaries and path patterns, the metadata resolver evaluates build configuration manifests (`package.json`, `Cargo.toml`, `pyproject.toml`, Makefiles) and repository attributes (`.gitattributes`) to assign initial language priors and intent locks to files before lexical analysis.

By analyzing project build definitions and developer metadata, the resolver establishes file importance and language hints, allowing downstream detectors to prioritize analysis based on verified developer intent.

---

## Bayesian Prior Probability Vectors

Files discovered during initial repository scanning begin as unclassified artifacts. The metadata resolver updates prior confidence vectors based on build system evidence:

* **Targeted Evidence Assignment:** Rather than applying broad assumptions, the resolver assigns language hints and confidence scores strictly when backed by explicit manifest definitions, pattern rules, or directory locations.
* **Metadata Vector Tagging:** When build manifest references are identified, the module attaches a contextual vector containing predicted language IDs (`lang_id`), prior confidence scores (`prior_confidence`), and source provenance labels (`source_proof`).
* **Priority Whitelist Boost:** If a file path matches an explicit user-configured priority whitelist, its prior confidence receives a **+0.10** boost (capped at 0.99), signaling explicit human verification to the downstream pipeline.

---

## Separation of Concerns: Context vs. Identification

The pipeline separates context resolution from lexical analysis:

1. **Metadata Resolver (`guidestar_lens.py`):** Determines **Intent and Context** (Why the file exists in the project build graph). Example: *"File referenced in Makefile source list with .c extension; prior confidence 0.90."*
2. **Language Identifier (`language_lens.py`):** Determines **Concrete Identity** (Validates structural content against language regular expression signatures to confirm the claim).

---

## Evidence Quality Hierarchy

Evidence is ranked based on proximity to explicit developer declaration:

### Tier 1: Machine Roadmap (Authoritative Declarations)
Explicit language definitions in `.gitattributes` (e.g., `*.h linguist-language=C++`).
* **Handling:** Parses `.gitattributes` for `linguist-language=` assignments, normalizes language identifiers, and locks matching file paths with a **0.99 prior confidence**, overriding standard extension defaults.

### Tier 2: Build Manifest Declarations (Functional Triggers)
Files explicitly declared in machine-readable build configurations.
* **Primary Entry Points:** Files designated as `main` or `bin` targets in `package.json` or `Cargo.toml` receive a **0.95 prior confidence**.
* **Script Dependencies & Sources:** Files referenced within build script commands (`npm run`) or Makefile source lists (`SRCS =`) receive an **0.85 prior confidence**.

### Tier 3: Directory Location Heuristics (Informational Context)
Files located within established executable or source directories.
* **Directory Sector Biases:** Files residing in standard build or execution paths (`/src`, `/bin`, `/scripts`, `/tools`, `/hooks`) receive an automatic **0.75 prior confidence**.
* **Custom Build Targets:** Custom non-reserved target names in Makefiles receive a **0.70 prior confidence**.

---

## Manifest Parsing Mechanics

* **Node.js Ecosystem (`package.json`):** Parses `main`, `bin`, and command strings inside `scripts` blocks to extract target `.js`/`.ts` file paths via regular expressions.
* **Makefiles:** Extracts file paths from variable declarations (`SRCS`, `SOURCES`, `FILES`, `TARGET`). Identifies custom targets while filtering out standard targets (`all`, `clean`, `test`).
* **Rust & Python Ecosystems (`Cargo.toml`, `pyproject.toml`):** Parses `path =` directives in Rust targets and entry-point specifications in Python TOML configs.
* **GitAttributes Normalization:** Maps Linguist tag names (e.g., `c++`, `objective-c++`) to standardized internal language keys (`cpp`, `objective-c`).

---

## Deterministic Path Lookup Resolution

When querying file metadata, the resolver evaluates rules in a strict lookup order:

$$\text{Lookup Sequence} = \text{Exact Filename Match} \rightarrow \text{Relative Path Match} \rightarrow \text{GitAttributes Pattern} \rightarrow \text{Directory Context}$$

All file paths are normalized (stripping `./` prefixes and trailing whitespace) prior to lookup to ensure consistency between manifest references and filesystem paths.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `guidestar_lens.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive 3D visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

