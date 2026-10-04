---
description: "You are operating within the `tensorflow` repository, an industry-standard, massive-scale machine learning and numerical computation framework. The..."
---
# AGENTS.md: tensorflow Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `tensorflow` repository, an industry-standard, massive-scale machine learning and numerical computation framework. The codebase is immense (2.8M+ LOC) and heavily dominated by C++ (40.7%) for the execution engine, Protocol Buffers (36.9%) for serialization, Python (8.8%) for user APIs, and MLIR (4.4%) for compiler infrastructure.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.287. The network topology demonstrates completely flat Modularity (0.0) and negative Assortativity (-0.0837). This indicates a highly coupled, monolithic core where fundamental C++ headers (`utility.cc`, `op_kernel.h`, `tensor.h`) act as massive single-points-of-failure serving thousands of downstream dependencies.
* **AI & Machine Learning Topology:** The repository represents "Local Sovereignty (Heavy Compute)." It acts as a 'Pure Producer (Foundation)' with a massive systemic blast radius (PageRank: 38.52). Any memory mismanagement or logic flaws here will cascade catastrophically into downstream user applications.
* **Core Rule:** Maintain strict adherence to the language boundaries. Do not leak C++ kernel logic into the Python API surface or bypass the MLIR/XLA translation layers. Respect memory allocation boundaries within the `Eigen` and `TFRT` (TensorFlow Runtime) components.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core deserialization (`from_proto`), distributed tensor resolution (`unpack` in `dtensor_device.py`), and TFLite compilation logic operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce unbounded loops, deep recursive AST traversals, or synchronous blocking calls within the critical paths of MLIR graph translation, XLA compilation, or distributed coordinator logic.
* **Orchestrator Fragility:** Central orchestrators bridging graphs to runtimes are highly fragile. `graph_to_tf_executor.cc` (117 outbound dependencies), `flatbuffer_export.cc`, and `import_model.cc` dictate the conversion of TF graphs to TFLite and XLA. Modifying these translation passes requires rigorous downstream regression testing across all supported architectures (CPU, GPU, TPU).
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions" (e.g., `message_wrappers.cc`, `tf_op_names.cc`, `op_types.cc`, `tfl_ops.cc`). DO NOT autonomously attempt to prune, format, or clean up these files. TensorFlow relies on exhaustive macro expansions, C API exports (`c_api.cc`), and registered operations (`REGISTER_OP`) that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, optimization passes, or public APIs of these files:
* `tensorflow/python/feature_column/feature_column_v2.py` (Massive Structural Mass: 49,540. 100% Key Person Silo by "A. Unique TensorFlower").
* `tensorflow/core/grappler/optimizers/remapper.cc`, `constant_folding.cc`, & `arithmetic_optimizer.cc` (100% Key Person Silos. Core graph optimization passes; modifications here risk silently breaking model accuracy or performance).
* `tensorflow/python/distribute/coordinator/cluster_coordinator.py` (Highest Cumulative Risk: 604.75. Critical for distributed training orchestration).
* `tensorflow/lite/delegates/nnapi/nnapi_delegate.cc` (Massive Data Gravity. The core bridge to Android's Neural Networks API).
* `tensorflow/compiler/mlir/lite/ir/tfl_ops.cc` (Highest Volatility: 71.9% Churn, 96.9% Tech Debt. Core TFLite MLIR definitions).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH CRITICAL RAW MEMORY & EXPLOIT CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation & Weaponizable Injection:** Python distributed strategy coordinators (`remote_value.py`, `cluster_coordinator.py`) and optimization libraries (`optimize_for_inference_lib.py`) possess 100% Exposure for Exploit Generation. Because TensorFlow processes untrusted serialized graphs and configuration protos, you MUST ensure strict input validation to prevent arbitrary code execution (Agentic RCE) or deserialization attacks.
2. **Raw Memory Manipulation:** The core C API (`c_api.cc`, `kernels.cc`) and memory layout passes (`mkl_layout_pass.cc`, `common_shape_fns.cc`) rely on raw pointer arithmetic and tensor buffer manipulation. Any changes here must be mathematically proven to prevent Buffer Overflows, Use-After-Free (UAF), or Out-of-Bounds (OOB) reads during tensor allocation and execution.
3. **Supply Chain:** There are 51 binary anomalies identified by X-Ray (primarily test fixture archives and native binaries). Do not alter or attempt to scan these binary blobs without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess MLIR dialect conversions, hallucinate XLA compiler behavior, or rely on generalized C++/Python knowledge to determine blast radius within this 2.8M+ LOC framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones** or altering fundamental headers like `types.h`, `utility.cc`, or `op_kernel.h` (Severe Blind Bottlenecks), you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
