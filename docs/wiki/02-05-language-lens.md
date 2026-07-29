# Language Identification Engine

> **File Reference:** [`gitgalaxy/standards/language_lens.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/standards/language_lens.py)

The `LanguageLens` module in `gitgalaxy/standards/language_lens.py` acts as the primary language identification engine for GitGalaxy. Rather than relying solely on file extensions—which can be misleading in polyglot codebases or obscured by custom build steps—the engine applies a Bayesian confidence model to evaluate files against a multi-tier trust matrix.

The module assigns a deterministic language identifier (`lang_id`) and confidence score (`prior_confidence`) to every analyzed file, combining metadata rules with deep lexical analysis.

---

## Bayesian Identification Trust Matrix

The language detection engine evaluates incoming files against defined confidence tiers:

| Tier | Classification Lock | Source Evidence | Confidence Score | Evaluation Logic |
| :--- | :--- | :--- | :--- | :--- |
| **0** | **Convergent Lock** | Dual Evidence | **0.95 - 0.99** | Confirmed match: Two independent signals align (e.g., Extension + Shebang, or Extension + Manifest prior). |
| **1** | **Roadmap Lock** | Manifest Definition | **0.95** | Build system proof: Direct declaration in build manifests (`package.json`, `Cargo.toml`). |
| **1.5** | **Ecosystem Gravity** | Neighborhood Consensus | **0.95** | Extension collision resolution: Resolves contested extensions (`.h`, `.m`) via directory language composition. |
| **1.7** | **Custom Extension** | Unlisted Extension | **0.95** | Custom extension fallback: Accepts short alphanumeric custom extensions as valid unknown types. |
| **2** | **Single Signature** | Extension or Shebang | **0.91** | Single-point indicator: Single signature trigger. Requires mandatory lexical verification. |
| **3** | **Contextual Prior** | Directory Heuristic | **0.90** | Location context: Path suggests importance, but requires regular expression validation. |
| **4** | **Discovery** | Zero Context | **0.10** | Unclassified asset: No extension or shebang. Passes structural density scanning. |
| **5** | **Identity Contradiction** | Signal Conflict | **0.00** | Security anomaly: Extension and shebang explicitly contradict each other. File is unclassified. |

---

## Pre-Flight Normalization & Perimeter Shields

Before executing regular expression detection rules, the engine prepares file paths and prevents misclassification:

* **Dotfile & Extension Unwrapping:** Handles false extensions on dotfiles (e.g., `.bashrc`). Removes secondary wrapper extensions (e.g., extracting `.sh` from `script.sh.template` or `config.py.bak`).
* **Directory Sibling Resolution:** Evaluates adjacent files in the same directory. Ambiguous header files (`.h`) located next to `.c` files lock to C; headers next to `.cpp` or `.hpp` files lock to C++.
* **Prose Hijacking Defense:** Prevents executable files with misleading names (e.g., `README.cpp`) from being misclassified as Markdown documentation.

---

## Conflict Detection & Security Integration

If a file's metadata components directly contradict each other—such as a file named `script.py` containing a Bash shebang (`#!/bin/bash`)—the engine flags the asset for **Identity Masking**. 

The conflicting file is assigned **Tier 5 Absolute Distrust (0.00 Confidence)** and routed to the security module (`security_lens.py`) for potential threat evaluation.

---

## Tier 1.5: Ecosystem Gravity & Extension Collision Resolution

Extensively collided file extensions (such as `.h`, which may represent C, C++, Objective-C, or MATLAB) are resolved using folder and repository ecosystem scoring:

1. **Local & Global Census:** Calculates local directory language density and global repository totals.
2. **Ecosystem Mass Computation:**
   * **Base Mass:** Sum of standard supporting extensions in the directory.
   * **Discriminator Mass (2.0x Multiplier):** Highly specific indicators (e.g., `CMakeLists.txt`, `project.pbxproj`) double ecosystem weighting.
   * **Disqualifying Mass:** Disqualifying file types trigger immediate score disqualification for incompatible language candidates.
3. **Dominance Threshold:** To lock a collided extension without deep parsing, the leading language candidate must hold a **70% dominance margin** over competitors globally (or 60% within the local folder).

---

## Tier 3: Lexical Verification & Pattern Validation

Files with single-point signatures (Tier 2) pass through regular expression validation rules:

* **Iron Wall Scanning:** Enforces strict candidate lists associated with the declared extension, preventing fallback to global scans.
* **Disqualifier Blacklists:** Evaluates syntax blacklists (e.g., rejecting C classification if `<?php` tags are present).
* **Delimiter Scoring (+15.0 Bonus):** Grants score bonuses when comment syntax matching the candidate language is detected (`//`, `#`, `/*`).
* **Legacy Language Multipliers:** Applies a 0.4x weighting penalty to legacy languages with broad keyword rules (e.g., ABAP, COBOL) to prevent false-positive matches over modern languages.
* **Logarithmic Normalization:** Normalizes raw hit scores against file length using logarithmic scaling ($\log(1 + \text{LOC})$).

---

## Tier 4: Unclassified Discovery Funnel

Files lacking extensions, shebangs, or manifest hints pass through a 4-stage discovery funnel:

1. **Comment Family Isolation:** Scans for comment syntax (`//`, `#`, `--`, `/*`). Files lacking recognizable comment delimiters default to `plaintext`.
2. **Heuristic Pruning:** Filters candidate list using disqualifier regular expression patterns.
3. **Structural Density Scan:** Computes structural density ($\text{Regex Hits} / \text{LOC}$). Applies score boosts for C macro preprocessor tags (`#define`, `#include`).
4. **Ensemble Tie-Breaker:** Demands a 1.5x density margin for competing candidates. Ties are broken using regular expression parser execution friction.

---

## Multi-Language Hybrid Detection

Modern source files frequently contain embedded sub-languages (e.g., HTML containing inline JavaScript or CSS, or Rust containing inline assembly).

* **Transition Marker Monitored:** Uses a `HANDSHAKE_REGISTRY` to track embedded language transitions (e.g., `<script>`, `asm!()`, `SELECT`).
* **Bracket Depth Tracking:** Tracks nested opening and closing delimiters to isolate embedded code blocks.
* **Telemetry Vector Payload:** Outputs a `lang_mix` dictionary (e.g., `{"HTML": 0.80, "JavaScript": 0.20}`), signaling the downstream analyzer (`detector.py`) to adjust scanning patterns accordingly.

---

## Extending Language Definitions

New language support is added by defining language heuristics and regular expression schemas in `gitgalaxy/standards/language_standards.py`. For complete integration guidelines, refer to **[Architecting a New Language](../../gitgalaxy/standards/how_to_add_a_language.md)**.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `language_lens.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - Interactive repository cartography dashboard.

---

**[⬅️ Back to Master Index](index.md)**