# Claim 5 (K-means clusters on structural DNA per file)

> **Two complementary lenses.** This page describes the **structural DNA** lens — files clustered by
> what their syntax *physically resembles*. A second, compositional lens
> ([03-05b: Composition Archetypes](03-05b-composition-archetypes.md)) types a file *bottom-up* by
> the mix of function-archetypes it contains, and rolls that up into repo archetypes. A scan now
> carries both labels side by side.

To truly understand software health, we need to stop judging every file by the same generic standard. A frontend UI router should not be penalized for having high concurrency, just as a low-level memory handler shouldn't be penalized for lacking dependency injection. Context matters.

To map the true physical reality of how software is built, we conducted a massive unsupervised machine learning analysis. We fed the pure, structural DNA of **1,592,674 files**—representing 74 distinct dimensions of regex hit densities, control flow ratios, active security threat payloads, and syntactic markers—into a K-Means clustering algorithm. We didn't give the AI any human rules about what constitutes "good" or "bad" code. We simply asked it to group them by physical resemblance.

*Crucially, we stripped out all formatting lint (Tabs vs. Spaces).* The AI was forced to look past the "paint" and strictly evaluate the architectural "plumbing."

The result? The algorithm naturally converged and separated the nearly 1.6 million files into **10 distinct architectural micro-species**.

By labeling every new file we scan with its exact ML Archetype, we can measure its risk scores *relative to its cluster*. We no longer ask, "Is this file too complex?" We ask, "Is this file too complex *for a UI Framework component*?" Furthermore, because our matrix tracks security signatures, we can see exactly which architectural islands are most susceptible to specific vulnerabilities.

---

## 🧬 The 10 File Archetypes

Here are the 10 archetypes identified by the clustering algorithm. Each micro-species represents a distinct architectural fingerprint based on structural DNA, independent of human-defined folders or logic tags.

### **Cluster 0: Native Core & Memory Management**
The "Meat Grinder." This is the raw, unshielded execution layer of native codebases. It is defined by extreme pointer arithmetic, complex branching, and dense state mutation, making it the highest-risk zone for memory leaks.
* **Size:** 193,095 files (12.1%) | **Dispersion:** 4.58
* **Dominant Languages:** C (50.4%), C++ (35.3%), Go (6.1%), Rust (3.8%)
* **Top Origins:** `linux` (17.7%), `freebsd-src` (12.7%), `illumos-gate` (7.4%), `tensorflow` (6.6%)
* **Defining DNA:**
    * **Pointer Arithmetic / Addressing:** +3.72 IQR
    * **Total Upstream Dependencies:** +1.95 IQR
    * **Max Function Complexity:** +1.42 IQR
    * **State Mutations / Reassignments:** +1.16 IQR
    * **Explicit Type Casts:** +1.10 IQR

### **Cluster 1: Annotated Object-Oriented Services**
The backend connective tissue. This cluster is defined by its massive reliance on decorators, generics, and structured documentation to wire up services, define data models, and inject dependencies.
* **Size:** 235,371 files (14.8%) | **Dispersion:** 4.92
* **Dominant Languages:** Python (28.6%), Java (19.6%), TypeScript (17.4%), Rust (14.6%)
* **Top Origins:** `elasticsearch` (9.0%), `rust` (8.6%), `aws-sdk-js-v3` (8.4%)
* **Defining DNA:**
    * **Structured Documentation Blocks:** +1.47 IQR
    * **Type Safety Bypasses:** +1.39 IQR
    * **Private Encapsulated Scopes:** +1.39 IQR
    * **Generic Type Abstractions:** +1.22 IQR
    * **Decorators & Annotations:** +1.16 IQR

### **Cluster 2: Declarative Data & Inert Interfaces (The Dark Matter)**
The largest single cluster in the galaxy. Highly static and dense, consisting of inert data structures, JSON configs, YAML pipelines, and massive interface definitions. It heavily lacks executable control flow but is essential for orchestrating environments.
* **Size:** 561,500 files (35.3%) | **Dispersion:** 2.87 *(Extremely tight grouping)*
* **Dominant Languages:** JSON (16.4%), TypeScript (14.7%), JavaScript (9.0%), Kotlin (8.9%)
* **Top Origins:** `kotlin` (7.5%), `swc` (7.5%), `rust` (5.9%)
* **Defining DNA:**
    * **Class Entity Declarations:** +0.30 IQR
    * **Direct Downstream Popularity:** +0.29 IQR
    * **Missing:** Sequential Logic Declarations (-0.83 IQR), Control Flow Branches (-0.64 IQR)

### **Cluster 3: High-Dependency C Headers & Metaprogramming**
The foundational core of operating systems and native runtimes. These files act as the central neurological pathways for C/C++ repositories, driven by extreme preprocessor macro density, pointer math, and authorship headers.
* **Size:** 133,223 files (8.4%) | **Dispersion:** 5.38
* **Dominant Languages:** C (55.4%), C++ (43.1%)
* **Top Origins:** `linux` (17.7%), `freebsd-src` (12.1%), `tensorflow` (8.6%)
* **Defining DNA:**
    * **Preprocessor Macros:** +3.55 IQR
    * **Pointer Arithmetic / Addressing:** +2.09 IQR
    * **Authorship Metadata:** +1.73 IQR
    * **Direct Downstream Popularity:** +1.55 IQR
    * **Metaprogramming & Reflection:** +1.37 IQR

### **Cluster 4: Functional Logic & Closures**
Modern, highly fluid execution logic. Primarily composed of TypeScript, JavaScript, and Dart, these files are defined by an extreme reliance on closures, anonymous functions, and defensive programming wrappers.
* **Size:** 120,238 files (7.5%) | **Dispersion:** 4.86
* **Dominant Languages:** TypeScript (28.3%), JavaScript (24.0%), Java (10.2%), Dart (9.8%)
* **Top Origins:** `elasticsearch` (7.5%), `sdk` (7.0%), `swc` (6.4%)
* **Defining DNA:**
    * **Closures & Anonymous Functions:** +2.75 IQR
    * **Max Function Complexity:** +0.88 IQR
    * **Type Safety Bypasses:** +0.78 IQR
    * **Defensive Programming Constructs:** +0.74 IQR
    * **Immutable Data Declarations:** +0.74 IQR

### **Cluster 5: Universal Dependencies (The God Nodes)**
The architectural anchors of the modern software stack. These are highly imported utility modules and central configuration hubs that possess a massive "blast radius" across the repository.
* **Size:** 50,087 files (3.1%) | **Dispersion:** 4.99
* **Dominant Languages:** TypeScript (43.8%), Python (32.4%), JavaScript (6.0%)
* **Top Origins:** `aws-sdk-js-v3` (16.6%), `google-cloud-python` (14.6%), `core` (11.8%)
* **Defining DNA:**
    * **Direct Downstream Popularity (Imported By):** +5.49 IQR *(Massive outlier)*
    * **Structured Documentation Blocks:** +1.24 IQR
    * **Decorators & Annotations:** +0.97 IQR
    * **Generic Type Abstractions:** +0.95 IQR
    * **Private Encapsulated Scopes:** +0.77 IQR

### **Cluster 6: UI Frameworks & View Layers**
The visual rendering engine. Isolated flawlessly by the algorithm, this cluster represents the frontend DOM manipulation of React, Angular, and Flutter, driven by extreme UI component density and closures.
* **Size:** 79,288 files (5.0%) | **Dispersion:** 4.61
* **Dominant Languages:** TypeScript (82.6%), JavaScript (8.9%), Dart (4.8%)
* **Top Origins:** `material-ui` (29.9%), `grafana` (8.8%), `ledger-live` (6.2%)
* **Defining DNA:**
    * **UI / View Layer Components:** +3.80 IQR
    * **Closures & Anonymous Functions:** +2.16 IQR
    * **Generic Type Abstractions:** +1.83 IQR
    * **Immutable Data Declarations:** +1.20 IQR
    * **Decorators & Annotations:** +1.17 IQR

### **Cluster 7: Highly Concurrent State Management**
The complex asynchronous brains of the application. These files feature massive concurrency signatures paired with closures, often representing global state stores, async pipelines, or heavily threaded data processing.
* **Size:** 85,160 files (5.3%) | **Dispersion:** 6.25 *(Highly scattered)*
* **Dominant Languages:** TypeScript (42.8%), Python (17.3%), JavaScript (12.1%), Rust (9.4%)
* **Top Origins:** `core` (9.7%), `vscode` (5.7%), `rust` (3.2%)
* **Defining DNA:**
    * **Raw Concurrency:** +4.22 IQR
    * **Closures & Anonymous Functions:** +1.65 IQR
    * **Amplified Race Conditions:** +1.64 IQR
    * **Type Safety Bypasses:** +1.23 IQR
    * **Generic Type Abstractions:** +1.20 IQR

### **Cluster 8: High-Risk Verification & Mocking**
The heavy QA and security layer. Because it relies heavily on mock data, intentional constraint bypasses, and dangerous shell executions, this cluster naturally isolates aggressive test-bound logic that tries to break the system.
* **Size:** 53,291 files (3.3%) | **Dispersion:** 6.53
* **Dominant Languages:** Python (67.2%), Java (12.4%), JavaScript (5.6%)
* **Top Origins:** `core` (19.4%), `elasticsearch` (5.8%), `sentry` (4.2%)
* **Defining DNA:**
    * **Unit Test Assertions:** +4.71 IQR
    * **Raw Danger (Eval/Exec):** +3.26 IQR
    * **Defensive Programming Constructs:** +1.68 IQR
    * **Decorators & Annotations:** +1.59 IQR
    * **Raw Concurrency:** +1.55 IQR

### **Cluster 9: I/O Automation & Scripting Glue**
The DevOps and network "Wild West." These files throw safety to the wind to automate builds, execute shell commands, and read/write to disks and external networks. They form the automated scaffolding of the software lifecycle.
* **Size:** 81,421 files (5.1%) | **Dispersion:** 4.50
* **Dominant Languages:** JavaScript (51.6%), Shell (13.3%), Python (9.2%), TypeScript (8.8%)
* **Top Origins:** `material-ui` (48.1%), `freebsd-src` (5.9%), `illumos-gate` (2.5%)
* **Defining DNA:**
    * **I/O & Network Boundaries:** +3.54 IQR
    * **UI / View Layer Components:** +1.77 IQR
    * **Type Safety Bypasses:** +1.43 IQR
    * **Metaprogramming & Reflection:** +1.10 IQR

---

### Thoughts
One of the most profound discoveries of this clustering process is that **not a single architectural micro-species is composed of only one programming language.**

Before feeding the telemetry into the K-Means algorithm, we deliberately blinded the model to the file extension, the repository name, and the human-assigned language. The AI had no idea if it was looking at a Java file, a Python script, or a C++ header. It was forced to group files based purely on their structural physics—their control flow density, architectural mass, structural logic branches, and usage of abstractions like generics or pointers.

The result is a taxonomical map that proves **intent scales across syntax.**

The algorithm mathematically recognized that a massive, heavily annotated Java Service class (Cluster 1) has far more in common with a robust TypeScript Dependency Injection file than it does with a simple Java data model. It recognized that a dense, highly defensive Python script (Cluster 7) shares the exact same structural DNA as a defensively written Rust file.

By grouping code by its physical behavior rather than its file extension, we have created a truly language-agnostic map of software architecture.

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.



---

**[⬅️ Back to Master Index](index.md)**
