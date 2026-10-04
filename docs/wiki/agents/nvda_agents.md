---
description: "You are operating within the `nvda` repository, the core codebase for the NonVisual Desktop Access screen reader for Windows. The repository operates..."
---
# AGENTS.md: nvda Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `nvda` repository, the core codebase for the NonVisual Desktop Access screen reader for Windows. The repository operates as a hybrid architecture, dominated by Python (79.3%) for orchestration, accessibility logic, and GUI, heavily supported by a C++ native interop layer (12.6%) for low-level OS and browser accessibility API hooks (e.g., IAccessible2, UIAutomation).
* **Architectural Paradigm:** The system maps to a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.6. The network topology demonstrates a Hub-and-Spoke model with moderate Modularity (0.3575) but negative Assortativity (-0.1503). This indicates a highly centralized architecture characterized by "spaghetti coupling", where isolated app modules rely entirely on a dense core of fragile, single-points-of-failure (e.g., `winUser.py`, `logHandler.py`).
* **Information Flow:** Execution flows from native OS accessibility events through the C++ `nvdaHelper` boundaries, traversing into Python via `source/core.py` and `source/api.py`. State is then managed and dispatched to specific output channels (speech via `synthDrivers`, braille displays) and application-specific objects (`NVDAObjects`).
* **Core Rule:** Maintain strict adherence to the C++/Python interop boundaries. Do NOT attempt to leak complex business logic into the C++ `nvdaHelper` virtual buffer backends; they must remain highly optimized state-syncing mechanisms, delegating orchestration back to the Python layer.

## 2. Notable Structures & Architecture
* **Foundational Load-Bearers:** Core utility modules act as the system's gravitational centers. `source/logHandler.py` (240 inbound connections), `source/_magnifier/config.py` (141 inbound), and `source/winUser.py` (92 inbound) dictate the stability of the entire repository. Modifying these modules carries a massive blast radius.
* **Fragile Orchestrators:** The primary orchestrators pull in vast dependency trees to manage state across the application. `source/core.py` (74 outbound) and `source/gui/settingsDialogs.py` (70 outbound) are highly coupled. Changes to global execution or settings UIs require rigorous verification.
* **Algorithmic Complexity:** The C++ Virtual Buffer backends (`MshtmlVBufBackend_t::fillVBuf`, `GeckoVBufBackend_t::fillVBuf`) carry extreme structural magnitude and operate at recursive O(2^N) time complexities. These components are responsible for parsing and structuring complex DOM trees (MSHTML, Gecko) into accessible buffers.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH RAW MEMORY AND EXPLOIT CAVEATS).** Structural Threat Intelligence audits have flagged 0 malicious artifacts.

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the browser integration layers (`nvdaHelper/vbufBackends/mshtml/mshtml.cpp`, `gecko_ia2.cpp`) and native hooks (`nvdaHelper/remote/gdiHooks.cpp`) inherently rely on raw memory manipulation and pointer arithmetic (up to 9.99% Exposure). Any modifications to these C++ buffers must strictly prevent Buffer Overflows or Use-After-Free (UAF) vulnerabilities when parsing untrusted DOMs.
2. **Exploit Generation Surface:** The `source/NVDAHelper/__init__.py` and `source/IAccessibleHandler/__init__.py` modules possess 100% Exposure for Exploit Generation. Because NVDA actively hooks into running processes and injects remote code (`nvdaHelperRemote`), ensure stringent validation on inter-process communications (IPC) to prevent local privilege escalation.

## 4. Outliers & Extremes
* **The Hotspot Matrix (High Volatility + Risk):** `source/globalCommands.py` is the ultimate hotspot (92.7% Churn, 99.6% Tech Debt). It acts as a massive routing hub for keyboard interactions and is a constant source of developer friction due to 228 orphaned functions and endless conditional branching.
* **Severe Silo Risk (Bus Factor):** Critical accessibility drivers are 100% isolated to single developers. Sascha Cowley owns `source/NVDAObjects/IAccessible/MSHTML.py` (1148 Mass) and `source/JABHandler.py` (697 Mass). Michael Curran owns the primary SAPI4 synthesizer driver (`sapi4.py`). 
* **Blind Bottlenecks (God Nodes):** `source/winUser.py` (Severity 1287) and `source/logHandler.py` (Severity 1185) exhibit massive blast radii but lack adequate structured documentation. Modifying the Win32 API wrapper (`winUser.py`) is effectively flying blind without explicit context tracing.
* **Contagious Mutation:** `source/core.py` and `source/appModuleHandler.py` act as structural bridges with highly volatile, mutating states (>25% Flux). They cause unpredictable side-effects for all downstream consumers.

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the architecture and reduce cognitive load for ongoing maintenance, prioritize the following pragmatic actions:

1. **Decompose `globalCommands.py`:** Address the extreme tech debt and churn in `source/globalCommands.py`. Extract domain-specific command sets (e.g., braille commands, review cursor commands) into isolated command handler mixins or classes. This will mitigate the 92% churn rate and reduce merge conflicts.
2. **Mitigate Key Person Dependencies on Browser/Java Interfaces:** The MSHTML, Gecko, and Java Access Bridge (JAB) integrations represent severe single-points-of-failure regarding domain knowledge. Initiate pairing or architectural documentation for `MSHTML.py`, `JABHandler.py`, and the corresponding C++ backends to distribute maintenance capabilities.
3. **Document Foundational Blind Bottlenecks:** Address the severe documentation risk in `source/winUser.py` and `source/logHandler.py`. Adding rigorous docstrings and architectural contracts to these load-bearing files will prevent cascading failures across the hundreds of modules that rely on them for OS interaction and telemetry.


---

**[⬅️ Back to Master Index](../index.md)**
