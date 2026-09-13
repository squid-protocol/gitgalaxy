# 🌌 GitGalaxy: WebGPU Visualizer ([GitGalaxy.io](https://gitgalaxy.io))

**A High-Performance, Zero-Trust 3D Codebase Cartography Engine.**

Modern IDEs present code as a flat list of files, masking the true physical weight, fragility, and blast radius of enterprise architecture. GitGalaxy is a forensic visualizer that solves this by mapping repository telemetry into an interactive, real-time 3D universe. 

This repository houses the standalone WebGPU presentation layer for the [GitGalaxy blAST Engine](https://github.com/squid-protocol/gitgalaxy). By translating raw static analysis into spatial geometry, it instantly exposes hidden architectural bottlenecks, dependency gravity, and each file's Structural Surface Profile (formerly called risk exposure).

🔭 **[Launch the Live Interactive Visualizer at GitGalaxy.io](https://gitgalaxy.io/)**

## 🔭 Architectural Case Studies

The following demonstrations highlight GitGalaxy mapping hyperscale architectures in real-time. *(Click to watch the full analysis on YouTube)*

| **Ruby on Rails** (Network Topology) | **Pandas** (Dependency Gravity) |
| :---: | :---: |
| [![Ruby on Rails Architecture](https://img.youtube.com/vi/XWWSd8LmoCM/maxresdefault.jpg)](https://youtu.be/XWWSd8LmoCM) | [![Pandas Architecture](https://img.youtube.com/vi/uReG4CdP5KI/maxresdefault.jpg)](https://youtu.be/uReG4CdP5KI) |
| **Kubernetes** (2M LOC Go Monolith) | **Apache Fineract** (Enterprise Java) |
| [![Kubernetes Architecture](https://img.youtube.com/vi/3ScQCSUBdZw/maxresdefault.jpg)](https://youtu.be/3ScQCSUBdZw) | [![Apache Fineract Architecture](https://img.youtube.com/vi/ycno7VARKWs/maxresdefault.jpg)](https://youtu.be/ycno7VARKWs) |

## 🚀 Engine Capabilities

This isn't a standard charting library; it's a custom-built, hardware-accelerated 3D environment designed for massive scale.

* **Next-Gen WebGPU Rendering:** Built on `three/webgpu` with custom TSL (Three.js Shading Language) nodes. It utilizes bit-packed vertex attributes and instanced meshes to render up to 150,000 files simultaneously at a smooth 60FPS, even on mobile GPUs.
* **Fibonacci Physics & 3D Phyllotaxis:** Files aren't placed randomly. The engine calculates "Orbital Reach" and distributes satellite functions around parent classes using golden-angle mathematics, creating organic, mathematically sound code constellations.
* **Multi-Dimensional Forensic Metrics:** The UI provides deep telemetry, visually mapping each file's Structural Surface Profile (formerly called risk exposures) derived from our AST-free regex heuristics. Toggle shader-driven color overlays to instantly identify [Connectivity, formerly API Exposure](https://squid-protocol.github.io/gitgalaxy/08-14-api-exposure.md), [Mutation Surface, formerly State Flux](https://squid-protocol.github.io/gitgalaxy/08-16-state-flux-exposure.md), [Complexity Load, formerly Cognitive Load](https://squid-protocol.github.io/gitgalaxy/08-05-cognitive-load.md), and even [Civil War](https://squid-protocol.github.io/gitgalaxy/08-12-civil-war.md) formatting fractures (tabs vs. spaces) across the entire system.
* **The Structural RAG Graph:** Visualizes the exact deterministic [Knowledge Graph Context](https://squid-protocol.github.io/gitgalaxy/01-06-the-structural-rag-graph.md) that the core engine feeds to downstream AI agents, allowing humans to audit the precise boundaries of their DevSecOps pipelines.
* **Interactive Dependency Webs:** Navigate the architecture with hyperspace jumps, isolate single components, and toggle global inbound/outbound dependency rings that arc across the galaxy.

## 🛡️ Zero-Trust & Local Execution

Your code is your business. This visualizer operates under a strict **Zero-Trust Client-Side Architecture**. 

When you drop a `your_repo_GPU_galaxy.json` state dump into the interface, **absolutely zero data is transmitted to any server**. All parsing, rendering, data refraction, and spatial calculations happen entirely locally in your browser's memory.

## 🛠️ Getting Started & Local Development

This visualizer is the front-end counterpart to the core [GitGalaxy Python CLI](https://github.com/squid-protocol/gitgalaxy). To generate your own 3D repository map:

1. Install the core engine: `pip install gitgalaxy`
2. Scan your local repository: `galaxyscope /path/to/your/repo`
3. Drop the resulting `_galaxy_gpu.json` payload directly into [GitGalaxy.io](https://gitgalaxy.io), or spin up this engine locally for completely air-gapped enterprise environments.

1. Clone this repository and navigate to the visualizer directory.
2. Boot the local server (e.g., using the included `app.py` or any standard HTTP server).
   ```bash
   python3 app.py
