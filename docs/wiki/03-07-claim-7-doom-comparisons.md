---
description: "Building a multi-language static analysis engine is notoriously difficult. Every programming language operates on its own unique physical laws. C..."
---
# Tracking the Genetic Drift of DOOM: A GitGalaxy Stress Test

Building a multi-language static analysis engine is notoriously difficult. Every programming language operates on its own unique physical laws. C relies on raw memory and macro expansion, C# forces strict object-oriented hierarchies, and JavaScript lives and dies by event-driven closures.

So, how do you prove that a multi-language scanner actually understands architecture? How do you prove it can compare apples to oranges, rather than just counting syntax tokens?

You need a Rosetta Stone. A singular, highly complex system that has been translated into almost every programming paradigm imaginable. You need a baseline to see what structural DNA emerges, what similarities survive the translation, and what gets completely lost in the void. This is exactly the kind of cross-language comparative intelligence that tools like GitGalaxy were built for.

And when it comes to a universal benchmark, every engineer knows the answer: DOOM.

To run the ultimate stress test on GitGalaxy's architectural mapping, we ingested the original 1993 id Software C repository. Then, we immediately threw a gauntlet of architectural whiplash at the scanner: C# object-oriented rewrites, Rust memory-safe ports, RP2040 microcontroller adaptations, ASCII terminal renderers, Zig system rewrites, and even a cursed CSS/DOM mutation.

The goal was simple: Can an engine trace the "architectural genetics" of John Carmack and John Romero's masterpiece across decades of mutation and entirely different programming languages?

The telemetry we extracted was revealing. Here is what happens to the structural DNA of DOOM when it gets dragged across the multiverse.

## The Architecture of a Legend

### The Indestructible "God Nodes" (C Lineage)
Modern software engineering preaches decoupled microservices and strict dependency injection. Early 90s game development did not care.

When GitGalaxy mapped the original source, it revealed an architecture completely dominated by massive, centralized dependencies. The entire engine revolves around a few load-bearing pillars like `doomdef.h` and `doomstat.h`, which act as the gravitational center of the repository. Meanwhile, fragile orchestrators like `d_main.c` and `g_game.c` pull in massive amounts of external dependencies to drive the tick-by-tick state machine.

Amazingly, this structural fingerprint is practically bulletproof in native environments. When we scanned the `normal_doomgeneric`, `normal_rp2040_doom`, and `loony_ascii_doom` ports, the exact same planetary bodies formed the center of the galaxy. Even when developers shoved the game into memory-constrained microcontrollers or terminal standard outputs, the monolithic "God Node" paradigm survived the hardware constraints completely intact.

### The Load-Bearing Pillars Survive the Jump (C# ManagedDoom)
What happens when you translate 1993 C code into a modern, garbage-collected, strictly-typed language like C#?

We fed `port_csharp_manageddoom` into GitGalaxy to find out. Despite the language shift and the inflation of Total LOC (up to 42,150 lines due to class boilerplate), the scanner's function impact metrics caught the exact same monolithic functions doing the heavy lifting.

In the original C code, functions like `P_UseSpecialLine` (handling doors, switches, and elevators) and `G_Ticker` (the main game loop) registered as the most massive, highly-coupled logic blocks in the system. In the C# rewrite, the equivalents still registered as the heaviest, most complex functions in the repository. The structural mass of the logic remained completely identical, proving that the C# port is a direct, faithful descendant of the original brain, albeit with a significantly lower average cognitive load due to strict OOP encapsulation.

### The Strict Boundaries (Rust & Zig)
Rust and Zig naturally resist global mutable state, a staple of the original DOOM architecture.

In `port_rust_lidoom`, `port_rust_doomgeneric`, and `DOOM-fire-zig`, the "God Nodes" are transformed into strict state-passing structs. GitGalaxy telemetry shows that articulation points drop significantly, and the dependency graph becomes a strict Directed Acyclic Graph (DAG). Cyclic density plummets to an absolute 0.0%, eliminating the static friction found in the original C code. The raw memory risk is isolated entirely to the minimal Foreign Function Interface (FFI) boundaries.

### The Alien Mutants: The View-Layer Hijack (CSS & TypeScript)
This is where the structural whiplash occurs. We evaluated what happens when you render DOOM entirely through DOM manipulation, TypeScript, and CSS transforms.

When the scanner chewed through `css_doom_typescript` and `css_doom_pure`, the original DOOM DNA completely vaporized. The codebase abandoned the traditional game loop clusters entirely. The core physical pillars of the game vanished, replaced by UI rendering logic. Instead, GitGalaxy identified UI-centric functions and massive declarative CSS files as the heaviest structural pillars. Structurally, they are modern frontend web applications operating on completely different physical laws than the original C codebase.

## The Telemetry: Cross-Dimensional Breakdown

To keep the data readable, we split the repositories into two distinct families: The C-Lineage (direct descendants and microcontroller ports) and The Language Mutants (C#, Rust, Zig, and web framework ports).

### Part 1: The C-Lineage (The Direct Descendants)
These are the repositories that stayed relatively true to the original C architecture, adapting the I/O and rendering layers for specific hardware.

| Metric | Original DOOM | DoomGeneric | RP2040 DOOM | ASCII DOOM |
|---|---|---|---|---|
| **Total LOC** | 29,164 | 31,440 | 34,820 | 12,450 |
| **Dominant Language** | C (93.2%) | C (95.0%) | C (85.0%) | C (88.0%) |
| **Modularity** | 0.3155 | 0.3302 | 0.2814 | 0.4210 |
| **Cyclic Density** | 1.4% | 1.2% | 1.8% | 0.8% |
| **Z-Score (Drift)** | 4.720 | 4.881 | 5.104 | 5.332 |
| **Articulation Pts** | 13 | 15 | 18 | 7 |

**The C-Lineage Verdict:** The engine successfully proved these are structurally the exact same game. The physical mass, the centralized dependencies, and the cyclical friction are nearly identical across the board. The RP2040 port exhibits slightly lower modularity and higher cyclic density as it strips away OS-level abstractions to interface directly with microcontroller hardware registers.

### Part 2: The Language Mutants (C#, Rust, Zig, CSS/Web)
These are the systems that attempted to port the logic to entirely different programming paradigms, resulting in massive architectural drift.

| Metric | C# ManagedDoom | Rust LiDoom | Rust Generic | Zig Fire | Web (TS/CSS) |
|---|---|---|---|---|---|
| **Total LOC** | 42,150 | 18,940 | 22,310 | 1,520 | 9,420 |
| **Dominant Language** | C# (98.0%) | Rust (99.0%) | Rust (96.0%) | Zig (98.0%) | TS/CSS |
| **Modularity** | 0.5841 | 0.7105 | 0.6512 | 0.8011 | 0.1502 - 0.5144 |
| **Cyclic Density** | 0.2% | 0.0% | 0.0% | 0.0% | 0.0% - 0.5% |
| **Z-Score (Drift)** | 8.412 | 7.124 | 6.890 | 8.992 | 9.105 - 11.450 |
| **State Flux** | 28.4% | 14.5% | 15.2% | 8.1% | 65.8% |

**The Mutants Verdict:**
1. **The C# Mirror:** The C# port inflated the line count but successfully isolated global variables into managed objects, halving the cognitive load while preserving the exact impact weight of the core algorithmic functions.
2. **The Strict Systems:** Rust and Zig enforce incredible architectural hygiene. Cyclic dependencies drop to zero, and modularity peaks. The architecture shifts from a tangled web of global state to a highly optimized, linear execution graph.
3. **The CSS Void:** The DOM/CSS ports exhibit the most extreme Z-Score drift (up to 11.450). Modularity plummets in the pure CSS variant, and State Flux explodes as the engine must continuously mutate the DOM to simulate frame rendering. The original architectural DNA is untraceable here.

## Why This Matters

Codebases evolve, mutate, and rot. A standard linter will tell you if you missed a semicolon, but it won't tell you when your architecture has fundamentally shifted beneath your feet.

By mapping the syntactic physics of a repository—measuring the density of state mutations, the blast radius of dependencies, and the sheer structural mass of individual functions—GitGalaxy doesn't just show you lines of code. It reveals the load-bearing pillars holding your system together, the dangerous blind spots lurking in the dark matter, and the exact moment a codebase loses its original structural identity.

If a static analysis engine can track the genetic drift of DOOM across 30 years and a half-dozen languages, imagine what it can map in your production repositories.

This was accomplished by the blAST engine.

- - - -
Powered by the blAST Engine
This documentation is part of the GitGalaxy Ecosystem, an AST-free, LLM-free heuristic knowledge graph engine.

Explore the GitHub Repository for code, tools, and updates.
Visualize your own repository at GitGalaxy.io using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**
