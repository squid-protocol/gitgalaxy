# Claim 5 (K-means clusters on structural DNA per file)

> **Two complementary lenses.** This page describes the **structural DNA** lens: files clustered by
> the signatures their syntax produces. A second, compositional lens
> ([03-05b: Composition Archetypes](03-05b-composition-archetypes.md)) types a file bottom-up by
> the mix of function archetypes it contains, and rolls that up into repo archetypes. A scan
> carries both labels side by side.

> **Model version note.** The figures on this page (74 dimensions, 10 clusters) describe the
> original research run. The `GENERAL_FILE_INFERENCE_MODEL` shipped in the engine has since been
> retrained twice: a 115-dimensional, 18-cluster model (v2.7.0 data), then the current
> **83-feature, 18-cluster** self-describing model (`file_cluster_0`..`file_cluster_17`; v2.8.0
> corpus, #3061, 2026-09-15). The engine's dimension-mismatch guard (#1158) is what showed that
> this page had drifted from the shipped model. The current model does not yet ship readable
> names for its 18 clusters, so the ten archetypes below are findings from the original run, not
> an index into today's `file_cluster_N` labels.

## Motivation

A single standard applied to every file produces misleading results. A frontend router should not
be scored down for high concurrency, and a low-level memory handler should not be scored down for
lacking dependency injection. Risk is easier to interpret relative to files of the same kind.

## Method

The original run clustered **1,592,674 files** with K-Means. Each file was represented by 74
features: regex signature densities, control-flow ratios, security signature counts, and
syntactic markers. No labels or quality rules were supplied; the algorithm grouped files by
structural similarity alone.

Formatting signals (tabs versus spaces) were excluded, so the clusters reflect structure rather
than style.

The run converged on **10 clusters**.

Each scanned file is assigned to its nearest cluster, and its risk scores can then be compared
with other files in that cluster. The question changes from "is this file complex?" to "is this
file complex for a UI component?". Because the feature set includes security signatures, the
clusters also show where specific vulnerability classes concentrate.

---

## The 10 file archetypes (original research run)

The clusters below come from the original run described above. Each describes a recurring
structural profile, independent of folder layout or language labels. *Defining features* are the
cluster's largest deviations from the population median, in IQR units.

### Cluster 0: Native Core & Memory Management
Low-level execution code in native codebases, characterised by pointer arithmetic, complex
branching and frequent state mutation. Of the ten clusters, it is the most exposed to memory
leaks.
* **Size:** 193,095 files (12.1%) | **Dispersion:** 4.58
* **Dominant languages:** C (50.4%), C++ (35.3%), Go (6.1%), Rust (3.8%)
* **Top origins:** `linux` (17.7%), `freebsd-src` (12.7%), `illumos-gate` (7.4%), `tensorflow` (6.6%)
* **Defining features:**
    * **Pointer Arithmetic / Addressing:** +3.72 IQR
    * **Total Upstream Dependencies:** +1.95 IQR
    * **Max Function Complexity:** +1.42 IQR
    * **State Mutations / Reassignments:** +1.16 IQR
    * **Explicit Type Casts:** +1.10 IQR

### Cluster 1: Annotated Object-Oriented Services
Backend service code that relies on decorators, generics and structured documentation to wire
services, define data models and inject dependencies.
* **Size:** 235,371 files (14.8%) | **Dispersion:** 4.92
* **Dominant languages:** Python (28.6%), Java (19.6%), TypeScript (17.4%), Rust (14.6%)
* **Top origins:** `elasticsearch` (9.0%), `rust` (8.6%), `aws-sdk-js-v3` (8.4%)
* **Defining features:**
    * **Structured Documentation Blocks:** +1.47 IQR
    * **Type Safety Bypasses:** +1.39 IQR
    * **Private Encapsulated Scopes:** +1.39 IQR
    * **Generic Type Abstractions:** +1.22 IQR
    * **Decorators & Annotations:** +1.16 IQR

### Cluster 2: Declarative Data & Inert Interfaces
The largest cluster. Static, dense files with little executable control flow: data structures,
JSON and YAML configuration, and large interface definitions.
* **Size:** 561,500 files (35.3%) | **Dispersion:** 2.87 (the tightest grouping)
* **Dominant languages:** JSON (16.4%), TypeScript (14.7%), JavaScript (9.0%), Kotlin (8.9%)
* **Top origins:** `kotlin` (7.5%), `swc` (7.5%), `rust` (5.9%)
* **Defining features:**
    * **Class Entity Declarations:** +0.30 IQR
    * **Direct Downstream Popularity:** +0.29 IQR
    * **Below median:** Sequential Logic Declarations (-0.83 IQR), Control Flow Branches (-0.64 IQR)

### Cluster 3: High-Dependency C Headers & Metaprogramming
C and C++ headers that many other files depend on, with high preprocessor-macro density, pointer
arithmetic and authorship headers.
* **Size:** 133,223 files (8.4%) | **Dispersion:** 5.38
* **Dominant languages:** C (55.4%), C++ (43.1%)
* **Top origins:** `linux` (17.7%), `freebsd-src` (12.1%), `tensorflow` (8.6%)
* **Defining features:**
    * **Preprocessor Macros:** +3.55 IQR
    * **Pointer Arithmetic / Addressing:** +2.09 IQR
    * **Authorship Metadata:** +1.73 IQR
    * **Direct Downstream Popularity:** +1.55 IQR
    * **Metaprogramming & Reflection:** +1.37 IQR

### Cluster 4: Functional Logic & Closures
Application logic, mostly TypeScript, JavaScript and Dart, that relies heavily on closures,
anonymous functions and defensive checks.
* **Size:** 120,238 files (7.5%) | **Dispersion:** 4.86
* **Dominant languages:** TypeScript (28.3%), JavaScript (24.0%), Java (10.2%), Dart (9.8%)
* **Top origins:** `elasticsearch` (7.5%), `sdk` (7.0%), `swc` (6.4%)
* **Defining features:**
    * **Closures & Anonymous Functions:** +2.75 IQR
    * **Max Function Complexity:** +0.88 IQR
    * **Type Safety Bypasses:** +0.78 IQR
    * **Defensive Programming Constructs:** +0.74 IQR
    * **Immutable Data Declarations:** +0.74 IQR

### Cluster 5: Widely Imported Modules
Utility modules and configuration hubs imported by many other files, so a change to one of them
affects a large part of the repository.
* **Size:** 50,087 files (3.1%) | **Dispersion:** 4.99
* **Dominant languages:** TypeScript (43.8%), Python (32.4%), JavaScript (6.0%)
* **Top origins:** `aws-sdk-js-v3` (16.6%), `google-cloud-python` (14.6%), `core` (11.8%)
* **Defining features:**
    * **Direct Downstream Popularity (Imported By):** +5.49 IQR (the largest deviation in any cluster)
    * **Structured Documentation Blocks:** +1.24 IQR
    * **Decorators & Annotations:** +0.97 IQR
    * **Generic Type Abstractions:** +0.95 IQR
    * **Private Encapsulated Scopes:** +0.77 IQR

### Cluster 6: UI Frameworks & View Layers
Frontend rendering code for React, Angular and Flutter, with high UI-component density and
frequent closures.
* **Size:** 79,288 files (5.0%) | **Dispersion:** 4.61
* **Dominant languages:** TypeScript (82.6%), JavaScript (8.9%), Dart (4.8%)
* **Top origins:** `material-ui` (29.9%), `grafana` (8.8%), `ledger-live` (6.2%)
* **Defining features:**
    * **UI / View Layer Components:** +3.80 IQR
    * **Closures & Anonymous Functions:** +2.16 IQR
    * **Generic Type Abstractions:** +1.83 IQR
    * **Immutable Data Declarations:** +1.20 IQR
    * **Decorators & Annotations:** +1.17 IQR

### Cluster 7: Concurrent State Management
Asynchronous and concurrent code, such as global state stores, async pipelines and multi-threaded
data processing, with heavy closure use.
* **Size:** 85,160 files (5.3%) | **Dispersion:** 6.25 (the second most dispersed)
* **Dominant languages:** TypeScript (42.8%), Python (17.3%), JavaScript (12.1%), Rust (9.4%)
* **Top origins:** `core` (9.7%), `vscode` (5.7%), `rust` (3.2%)
* **Defining features:**
    * **Raw Concurrency:** +4.22 IQR
    * **Closures & Anonymous Functions:** +1.65 IQR
    * **Amplified Race Conditions:** +1.64 IQR
    * **Type Safety Bypasses:** +1.23 IQR
    * **Generic Type Abstractions:** +1.20 IQR

### Cluster 8: Test & Verification Code
Test suites and security-oriented checks that use mock data, deliberate constraint bypasses and
shell execution.
* **Size:** 53,291 files (3.3%) | **Dispersion:** 6.53
* **Dominant languages:** Python (67.2%), Java (12.4%), JavaScript (5.6%)
* **Top origins:** `core` (19.4%), `elasticsearch` (5.8%), `sentry` (4.2%)
* **Defining features:**
    * **Unit Test Assertions:** +4.71 IQR
    * **Raw Danger (Eval/Exec):** +3.26 IQR
    * **Defensive Programming Constructs:** +1.68 IQR
    * **Decorators & Annotations:** +1.59 IQR
    * **Raw Concurrency:** +1.55 IQR

### Cluster 9: I/O Automation & Scripting
Build, automation and tooling scripts that run shell commands and read from or write to disk and
network, often with few safety checks.
* **Size:** 81,421 files (5.1%) | **Dispersion:** 4.50
* **Dominant languages:** JavaScript (51.6%), Shell (13.3%), Python (9.2%), TypeScript (8.8%)
* **Top origins:** `material-ui` (48.1%), `freebsd-src` (5.9%), `illumos-gate` (2.5%)
* **Defining features:**
    * **I/O & Network Boundaries:** +3.54 IQR
    * **UI / View Layer Components:** +1.77 IQR
    * **Type Safety Bypasses:** +1.43 IQR
    * **Metaprogramming & Reflection:** +1.10 IQR

---

### Observations
No cluster in this run consists of a single programming language.

The model was not given the file extension, repository name or language label. It grouped files
only by structural features: control-flow density, size, branching, and use of abstractions such
as generics or pointers.

The resulting grouping suggests that structural intent carries across syntax. A heavily annotated
Java service class (Cluster 1) sits closer to a TypeScript dependency-injection module than to a
simple Java data model, and defensively written Python and Rust files share Cluster 7.

Grouping by structure rather than by file extension gives a language-independent view of software
architecture.

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.



---

**[⬅️ Back to Master Index](index.md)**
