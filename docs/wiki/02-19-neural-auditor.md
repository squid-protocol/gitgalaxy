# The Tensor Model Scanner (Binary Weight Inspection)

> **File Reference:** [`gitgalaxy/metrics/tensor_scanner.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/tensor_scanner.py)

The Tensor Model Scanner (`tensor_scanner.py`, historically referenced as the Neural Auditor) inspects large Machine Learning model weights (`.safetensors`, `.gguf`) stored within repositories without loading multi-gigabyte files into system RAM. By parsing binary headers using zero-RAM byte reads, it extracts parameter counts, quantization levels, and architecture metadata for static analysis reporting.

---

## Zero-RAM Binary Inspection

When the ingestion filter (`aperture.py`) encounters large AI model binaries, it routes the file paths to the `TensorScanner`. The scanner inspects binary headers using targeted stream reads based on file extension:

### 1. Safetensors Metadata Extraction
The `.safetensors` format (standardized for machine learning model serialization) places JSON metadata at the beginning of the binary file:
* **8-Byte Header Read:** Reads the first 8 bytes of the file (a little-endian `uint64` integer) to determine the exact byte length of the JSON metadata header.
* **Header Size Validation:** Validates that the declared header size does not exceed safety limits (e.g., > 100MB). If suspicious header sizes are detected, parsing aborts to prevent buffer overflows or memory exhaustion.
* **Parameter Mathematics:** Parses the JSON metadata header to extract model architecture declarations (e.g., LLaMA, Mistral). Calculates total parameter counts by multiplying tensor dimension arrays for every declared weight key.
* **Format Formatting:** Formats raw parameter counts into standardized human-readable strings (e.g., "8.0B", "350.0M").

### 2. GGUF Binary Header Inspection
The `.gguf` format (commonly used for quantized local inference) stores metadata key-value pairs near the beginning of the file:
* **Magic Byte Verification:** Reads the initial 4 bytes to verify the `GGUF` magic byte signature, confirming valid binary format before proceeding.
* **Header Chunk Extraction:** Reads a 1MB stream from the beginning of the file and decodes printable ASCII text strings to extract metadata keys without full binary tree parsing.
* **Metadata Heuristics:** Uses pattern matching to extract architecture family names (e.g., "llama", "qwen") and quantization levels (e.g., "Q4_K", "Q8_0").

---

## Model Metadata & Node Mapping

Once metadata extraction completes, the scanner returns structured metadata dictionaries (`architecture`, `parameters`, `quantization`) to the pipeline orchestrator.

The orchestrator attaches model architecture attributes to the repository file node and computes visual node mass based on file size, enabling engineering teams to audit local machine learning model footprints across repository repositories.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

