# The GPU Recorder (Columnar Data Exporter)

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/gpu_recorder.py)

The GPU Recorder (`gpu_recorder.py`) is the high-performance data transformation module of the GitGalaxy pipeline. It converts verbose, object-oriented JSON telemetry into a hypercompressed columnar format (Structure of Arrays / SoA) designed specifically for WebGL/WebGPU 3D rendering engines. The exporter prioritizes memory efficiency, low payload transfer size, and low-latency buffer loading over human readability.

---

## Memory Management & Garbage Collection

To process large codebases without exhausting system RAM, the exporter executes an aggressive memory eviction strategy during final payload construction:

* **Iterative Array Eviction:** As file records and anomaly structures are converted into columnar arrays, they are popped from RAM-resident dictionaries using `.pop()`, freeing memory incrementally as serialization progresses.
* **Explicit Garbage Collection:** Object references are explicitly cleared (`del`), followed by manual Python garbage collection calls (`gc.collect()`) prior to disk serialization to minimize memory footprint.

---

## Columnar Layout & Dependency Resolution

The recorder converts nested dictionary hierarchies into parallel flat arrays (Structure of Arrays):

* **Parallel Metric Columns:** Generates parallel arrays for spatial positions (`pos_x`, `pos_y`, `pos_z`), file masses, and structural code metrics (`cog_raw`, `raw_churn_freq`, `ownership_entropy`).
* **Pre-Computed Dependency Edges:** Pre-resolves string import declarations into numerical array index pointers (`edges` and `outbound_edges`). This allows WebGL visualizers to draw Thousands of 3D dependency connections directly from GPU vertex buffers without performing expensive string searches at runtime.
* **Flattened Function Offsets:** Flattens internal function/method records into a single 1D array (`satellite_data_flat`), using offset pointers (`satellite_offsets`) to maintain boundary lookups sorted by metric magnitude.
* **ML Archetypes & Threat Scores:** Vectorizes Machine Learning archetype classifications and embeds XGBoost threat confidence percentages directly into numeric columns (`ai_threats`).

---

## String Dictionary Encoding & Fixed-Point Quantization

To maximize compression ratios and decrease network transfer times, the exporter eliminates redundant text strings and floating-point precision overhead.

### String Dictionary Encoding (Interning)
Repeated string values (file extensions, directory paths, language names, import names, and archetype labels) are stored once in header lookup tables and replaced in columnar data with integer dictionary keys (`ext_lookup`, `import_lookup`, `const_lookup`, `archetype_lookup`).

### Fixed-Point Quantization
Floating-point values are multiplied by fixed scaling factors and stored as integers to match graphics pipeline vertex buffer formats:
* **Position & Structural Mass Scaling (10x):** Applied to spatial coordinates, file masses, and function angles (e.g., `150.45` scales to `1505`).
* **Metric & Threat Scaling (1000x):** Applied to threat probabilities, control flow ratios, ownership entropy, and author distribution percentages (e.g., `0.854` scales to `854`).

---

## Output Packaging & Serialization

Prior to disk export, the module finalizes the visualizer payload:

* **Excluded Artifact Breakdown:** Summarizes file exclusion categories and diagnostics into flat array structures for frontend filter rendering.
* **Metadata & Context Injection:** Includes project metadata, historical overview metrics, and highlighted analysis insights in the payload header.
* **Compressed Serialization:** Serializes JSON output without formatting whitespace (`separators=(',', ':')`), generating minimal-byte payloads for WebGL consumption.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

