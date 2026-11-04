### 🖥️ Mathematical Proofs: The WebGPU Cartography Engine

This directory contains the core graphics architecture, custom shaders, and rendering physics for the GitGalaxy WebGPU visualizer.

Standard DOM-based charting libraries (and even naive WebGL implementations) instantly crash or throttle to 2 FPS when fed the telemetry of a 150,000-file enterprise architecture. This suite exists to mathematically prove that we can render planetary-scale codebases directly in the browser at a locked 60 FPS. It enforces strict VRAM memory limits, utilizes bit-packed vertex attributes to bypass mobile GPU buffer caps, and executes complex 3D Phyllotaxis algorithms—all while maintaining a strict Zero-Trust, client-side execution model where your code never touches a server.

---

### 📂 Verified Capabilities & Architectural Index

The engine is divided into the Core Rendering Pipeline (`site/js/core/`, with `site/js/main.js`) and the surrounding Hardware/Telemetry Tools (`site/tools/`).

#### 1. `js/core/` (The Rendering Pipeline & Physics)
This directory houses the engine's primary loop, data extraction, and hardware-accelerated WebGPU shading logic.

* **`main.js` (The Warp Core, `site/js/main.js`)** — The master orchestrator. Handles asynchronous WebGPU initialization, local RAM-injection for drag-and-drop JSON payloads (Zero-Trust), and dynamic UI synchronization.
* **`galaxy-engine.js` (The 3D Engine)** — The Three.js/WebGPU spatial environment. Manages `InstancedMesh` generation, raycasted interaction, dynamic resolution scaling, and the adaptive Dependency Web orchestrator. Critically, it respects the **8-Buffer Mobile GPU Limit**, packing metadata mathematically to prevent silent WebGL compiler crashes on low-end hardware.
* **`data-parser.js` (The Refractor)** — The mathematical bridge between JSON and 3D space. It calculates **3D Fibonacci Distribution (Phyllotaxis)** to orbit satellite functions organically around parent stars, preventing geometric overlapping, and calculates composite complexity to dynamically cull visual noise (The Fractal Depth Step Function).
* **`phase-6-shaders.js` (The Shader Matrix)** — Written in TSL (Three.js Shading Language), this file moves the heavy lifting from the CPU to the GPU. It decodes the compressed vertex attributes and executes the **Universal Turbo Spectrum**—a dynamic color-grading algorithm that maps 18 dimensions of risk telemetry into visual heatmaps in real-time.
* **`materials.js` (The Visual Cache)** — Manages the caching and refreshing of aesthetic materials to prevent memory leaks during theme transitions.

#### 2. `site/tools/` (Hardware Interfaces & Telemetry)
This directory houses the tools that bypass browser limitations and ensure the environment remains accessible and performant.

* **`poster.js` (The VRAM-Safe Print Engine)** — Most browsers physically crash if you attempt to render a 54-Megapixel canvas due to hardcoded `MAX_TEXTURE_SIZE` limits. This engine bypasses the GPU ceiling by calculating dynamic VRAM safety buffers, executing tile-chunked Super Sample Anti-Aliasing (SSAA), and seamlessly stitching the resulting matrix into a massive, print-ready artifact.
* **`perf_monitor.js` (The Hysteresis Sentinel)** — A highly aggressive performance monitor that tracks rolling 3-second FPS windows and active JavaScript heap memory. It executes mathematical hysteresis loops to dynamically shift rendering tiers (TITAN, STANDARD, POTATO) on the fly, guaranteeing fluid frame rates without causing visual flickering during heavy loads.
* **`ally.js` (The Semantic Shadow DOM)** — 3D visualizations are notoriously hostile to screen readers. This engine solves that by dynamically generating a hidden, semantic Shadow DOM (`<ul>` tree) that perfectly mirrors the 3D galaxy. It mathematically translates visual physics (e.g., "Red Icosahedron with Dense Rings") into semantic ARIA descriptions, allowing blind engineers to physically tab through the galaxy and auto-pilot the camera.
* **`search.js` (The High-Velocity Indexer)** — A lightweight, O(1) filtering engine that flattens hierarchical system data into a searchable array, allowing for instant optical jumps to specific architecture.

#### 3. The 2D Forensic Dashboards
* **`metavisualizer.html` (The Linear Dashboard, `site/js/core/`)** — A high-density statistical dashboard built to ingest the exact same JSON payloads. It features dynamic **Galactic (Log) vs Linear** histogram toggles, zero-bar suppression logic, and non-occluded tooltip architecture for when raw, sorted statistical data is required alongside the 3D visualization.

---

### 🚀 Execution & Integration

Because this architecture adheres to a strict Zero-Trust model, the visualizer requires no backend or API to function.

**To test the WebGPU Visualizer locally:**
```bash
# Boot a local server in the visualizer root directory (site/) to bypass local CORS restrictions
python -m http.server 8000
```
Navigate to `http://localhost:8000/index.html` and drop your generated `<repo>_galaxy_gpu.json` payload directly into the browser.