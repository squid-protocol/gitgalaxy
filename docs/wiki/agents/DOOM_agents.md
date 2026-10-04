---
description: "You are operating within the `DOOM` repository, the foundational 1993 source code for id Software's Doom engine. The codebase is almost exclusively C..."
---
# AGENTS.md: DOOM Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `DOOM` repository, the foundational 1993 source code for id Software's Doom engine. The codebase is almost exclusively C (93.2%) and relies on highly optimized, procedural, and memory-constrained techniques typical of early 1990s game development.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species. The network topology demonstrates a strict "hub-and-spoke" architecture (Assortativity: -0.1065) centered entirely around massive, globally shared state headers (e.g., `linuxdoom-1.10/doomdef.h`, `doomstat.h`, `i_system.h`). 
* **Core Rule:** Do NOT attempt to "modernize" this codebase by introducing object-oriented decoupling, strict encapsulation, or dynamic memory allocation (`malloc`/`free`). The engine operates on a custom, static-bound memory allocator (Zone memory) and relies heavily on global state arrays and macros.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core rendering and networking functions (`R_Subsector` for BSP traversal, `V_DrawPatch` for column rendering, and `GetPacket`/`SendPacket` in IPX networking) operate at O(2^N) recursive time complexities in static analysis. You MUST NOT introduce branching logic or floating-point math into these hot paths. The renderer relies on fixed-point arithmetic (`m_fixed.c`) and precalculated lookup tables.
* **Orchestrator Fragility:** Central orchestrators like `d_main.c` (the main game loop and initialization, 30 outbound dependencies) and `g_game.c` (the tic-based action loop, 28 outbound dependencies) are highly fragile. Altering the sequence of initialization or the synchronous `G_Ticker` loop will instantly cause desyncs in demo playback and multiplayer.
* **Avoid Dead Code Pruning:** Files like `p_enemy.c` (49 orphaned functions) and `p_pspr.c` (24 orphaned functions) contain logic flagged as "dead code." DO NOT autonomously attempt to prune these files. These functions are action routines invoked dynamically via function pointers in the engine's hardcoded state machine arrays (mobj states), bypassing static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or act as central choke points. 

**MANDATORY RULE:** You require explicit human permission and downstream engine testing before modifying the structural signatures, fixed-point math, or global structs of these files:
* `linuxdoom-1.10/doomdef.h` & `doomstat.h` (Severe Load-Bearers - Over 80 combined inbound connections. These define the absolute reality of the game state).
* `linuxdoom-1.10/p_enemy.c` (Highest Cumulative Risk: 506.69. Contains the core enemy AI and state-machine transitions; highly complex and error-prone to modify).
* `linuxdoom-1.10/z_zone.c` (The Zone memory allocator. Modifying `Z_Malloc` or `Z_Free` risks catastrophic heap corruption).
* `linuxdoom-1.10/r_main.c` & `r_segs.c` (Core renderer. Any modification to `R_StoreWallRange` impacts the BSP drawing boundaries and will cause visual hall-of-mirrors effects).
* `sndserv/sounds.h` (Severe Blind Bottleneck - High blast radius flying blind with 83.2% Doc Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts.

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** The engine manages its own heap via `z_zone.c` and relies heavily on pointer arithmetic for rendering (`r_draw.c`) and networking (`d_net.c`, `ipx/IPXNET.C`). The networking stack has a 3.5% exposure to raw memory manipulation. Ensure any modifications to packet parsing rigorously validate buffer lengths to prevent buffer overflows (often referred to as the "ping of death" in early engines).
2. **Type Punning & Casting:** The codebase heavily utilizes type punning and raw struct casting when reading WAD data (the game assets) from disk (`w_wad.c`). Do not "fix" these casts; they are necessary for reading binary-packed, little-endian data structures directly into memory.

## 5. Environmental Tooling (The Oracle)
Do not guess BSP tree traversal semantics, hallucinate fixed-point integer conversions, or rely on modern C/C++ knowledge to determine blast radius within this 1993 artifact. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
