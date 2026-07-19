# 2.3.5. The Detector (The Logic Splicer & Cartographer)

> **Overview: The EMCCD Sensor & Galactic Cartography**
>
> Before the Splicer spends computational energy carving a logic stream, it performs a strict physical viability check. If a file enters the Splicer with a structural confidence score below `0.42`, it triggers the **Singularity Bypass**, safely relegating the file to "Dark Matter" (unparsed mass). Similarly, files explicitly verified as `markdown` or `plaintext` trigger a Prose Deflection, routing them entirely to "Ghost Mass."
>
> **The Ecosystem Gravity Override:** In the Protocol, a critical exception was introduced for highly contested, declarative files—most notably C/C++ header files (`.h`). Pure-macro headers often lack the standard functional logic (braces, loops, branches) required to pass the 0.42 confidence floor naturally, causing vital architectural maps to vanish into Dark Matter.
>
> To solve this, the Splicer now implements an **Ecosystem Gravity Override**. If the upstream Language Lens previously utilized ecosystem mass to safely lock a file into a C-family orbit (`c`, `cpp`, or `objective-c`), the Splicer trusts that macro-level gravity. It artificially boosts the file's parsing confidence to `1.0`, ensuring these critical structural components are fully mapped and integrated into the final spatial cartography.

## 2.3.5.A. The Atomic Literal Shield

Strings and text literals are the natural enemies of structural parsers. A stray opening brace `{` or an unmatched quote `"` trapped inside a developer's string can permanently desynchronize the scope stack, shattering the parsed logic.

To prevent this "Quote Desynchronization," the Splicer utilizes the **Atomic Literal Shield**, an advanced pre-processing engine that securely masks disruptive text *without* altering the physical line counts or character indexing of the original file. This ensures the parsed logic perfectly maps 1:1 with the original source code.

The Protocol introduces heavily upgraded, language-aware shielding:

* **Advanced Atomic Quotes:** The shield processes multi-character sequence markers strictly *before* single quotes. This surgical ordering correctly masks C++ Raw String Literals (e.g., `R"EOF(...)EOF"`) and Python Triple Quotes (`"""` / `'''`) without prematurely triggering on standard double quotes contained within them.
* **Heredoc Isolation:** For scripting languages (Shell, Bash, Ruby, Perl, Elixir), standard regex is insufficient. The Splicer deploys a line-by-line state machine to isolate complex Heredoc logic (e.g., `<<-EOF`), safely blanking out massive text blocks that frequently contain rogue bash characters or unescaped quotes.
* **Ruby `%` Literals:** Strictly gated to the Ruby ecosystem, a dedicated shield evaluates and masks the complex, bracketed `%` string syntax (e.g., `%w[...]`, `%q{...}`, `%x(...)`), preventing the internal brackets from falsely triggering the Mode D handshake stack.
* **Diagnostic Telemetry:** To protect pipeline performance against catastrophic backtracking (ReDoS), the shield actively times its own regex operations. If shielding an excessively large or obfuscated file takes longer than 0.5 seconds, the engine logs a targeted diagnostic warning to trace the latency bottleneck.

## 2.3.5.B. Coding vs. Comment Analysis (Separation of Concerns)

To maintain absolute mathematical integrity, the GitGalaxy Splicer strictly enforces a Separation of Concerns between executable logic (Active Matter) and developer literature (Ghost Mass). Mixing these two streams during regex evaluation is the primary cause of "Logic Erosion" in legacy scanners, where a commented-out `if` statement falsely inflates a file's complexity score.

By routing the pre-split streams into distinct analysis engines, GitGalaxy guarantees that structural metrics and human intent are measured independently.

### 1. Coding Analysis (The 51-Element Schema Guarantee)
The `coding_analysis` engine is responsible for measuring the raw physical properties of the Active Matter (branches, IO operations, memory manipulations). In the Protocol, this engine was upgraded to enforce absolute schema rigidity:
* **Anti-Hallucination Binding:** The engine initializes its counting dictionary directly from the `UNIVERSAL_METRICS_SCHEMA`. If a custom language definition attempts to inject an unregistered rule, the Splicer actively ignores it.
* **Deterministic Output:** This strict bounding guarantees that the resulting metrics dictionary is *exactly* 51 elements long, in the exact same order, every single time. This absolute consistency is vital for preventing schema drift and ensuring downstream risk algorithms (which rely on fixed-length arrays) never crash or misalign.
* **Indentation Signatures:** Alongside regex matching, the coding analyzer also calculates the physical indentation density (Tabs vs. Spaces) to help downstream models identify the formatting culture of the logic block.

### 2. Comment Analysis (Ghost Mass Telemetry)
The `comment_analysis` engine scans the isolated literature of the file. Because it operates exclusively on the Ghost Mass, it uses a specialized subset of rules to measure developer intent and technical debt without polluting the core logic metrics. It actively tracks:
* **Debt Signatures:** Specifically hunts for `planned_debt` (TODOs, FIXMEs) and `fragile_debt` (HACK, XXX) markers.
* **Shadow Logic:** Evaluates the `graveyard` rule to find malicious links or dead code blocks trapped inside comments.
* **Documentation Density:** Measures the sheer volume of `doc` tags to establish the "Trust Dampening" baseline (how well the file is explained vs. how complex it actually is).

### 3. Architectural Metadata Extraction
Even if a file is relegated to Dark Matter (failing the 0.42 structural confidence floor), the Splicer still executes the `_decode_comment_stream` protocol. This specialized parser scans the top 500 lines of the Ghost Mass to surgically extract the file's **Ownership** (authorship tags) and its **Architectural Purpose** (via specific block/line intent rules). This ensures that even unparsed config files or monolithic scripts contribute their human context to the final repository map.

## 2.3.5.C. Metric Vectorization: Multi-Dimensional Physics

Because programming languages adhere to vastly different structural physics, a one-size-fits-all regex approach is mathematically impossible. To solve this, the `_function_slice` Master Dispatcher analyzes the language's lexical family and dynamically routes the Active Matter into one of five highly specialized extraction algorithms (Integration Modes).

* **Mode A: Label-Based Scan (Legacy Species)** Used for legacy procedural languages like Assembly, AGC, and COBOL, which lack traditional scoping mechanisms. The Splicer uses a greedy, label-based scan (`_slice_by_labels`). It searches for functional start tags or labels and captures the entire block of logic until it encounters the next start tag or a definitive return instruction (e.g., `RET`, `GOBACK`, `END-PERFORM`), successfully isolating the structural satellite.
* **Mode B: Recursive Scope Analysis (C-Family & Lisp)** The standard algorithm for languages relying on braces `{}` or parentheses `()`. The Protocol heavily fortifies this brace-tracking engine against syntax desynchronization:
  * **The Atomic Alternation Shield:** Evaluates double quotes, single quotes, and backticks simultaneously. This prevents complex string manipulation from confusing the scanner and falsely collapsing the closing braces.
  * **The C++ Preprocessor Brace Shield:** C/C++ macros frequently contain raw floating braces (e.g., `#else {`), which historically shattered scope stacks. The Splicer now implements a preprocessor shield that safely blinds the parser to duplicate or floating braces trapped inside dead structural branches (`#elif`, `#else`) and multi-line `#define` macros.
* **Mode C: Density Stratification (Python & YAML)** Languages that rely on whitespace require a topographical approach. Using `_slice_by_indentation`, the engine identifies a structural igniter (like `def` or `class`) and calculates its base indentation level. It then scans forward, line-by-line, through the code's density. The scope block is naturally terminated the moment the engine encounters a line of active code that drops back to or below the base indentation level.
* **Mode D: Semantic Handshake Stack (Keyword Scoping)** A major addition in the Protocol, Mode D (`_slice_by_keywords`) is explicitly designed for non-brace scripting languages like Shell, Ruby, Lua, and Elixir.
  * Powered by the new `SemanticScopeRegistry`, this engine tracks structural depth via text keywords rather than symbols. It identifies specific *openers* (`if`, `def`, `case`) and *closers* (`fi`, `end`, `esac`) to manage the scope stack.
  * It includes specialized heuristics, such as the **Ruby Inline Modifier Guard**, which prevents single-line modifiers (e.g., `return true if x`) from falsely incrementing the depth stack.
* **Mode E: Terminator Cleaving (Declarative Architectures)** Designed for declarative and query languages like SQL, Erlang, and Prolog (`_slice_by_terminator`). Rather than tracking nested scope, this mode monitors the stream for an **Igniter** keyword (e.g., `SELECT`, `CREATE`, or an Erlang function head) to start orbiting a new logic block. The block remains open until the engine detects the language's specific **Terminator** token (like a semicolon `;` or a period `.`), at which point the "guillotine drops," cleaving the statement into a measurable satellite.

## 2.3.5.D. Satellite Physics & Naming Shields

Once the Master Dispatcher successfully cleaves a block of logic from the file, it becomes a "Satellite." Before it can be placed into the spatial map, the Splicer must calculate its physical properties and extract its true identity.

### 1. Satellite Physics (The Mathematical Engine)
The `_process_satellite_physics` method analyzes the raw string of the isolated block to calculate its weight and trajectory in the final 3D visualization.
* **Control Flow Ratio (`cf_ratio`):** Measures the density of branching logic vs. linear execution. The formula is `branches / max(total_hits, 1)`, clamped tightly between $0.0$ and $1.0$.
* **Logic Angle (`angle`):** Determines the trajectory of the satellite's branches in the 3D viewer. It maps the Control Flow Ratio to a physical angle using the equation: 
  $$\text{Angle} = 22.5 + (1.0 - \text{cf\_ratio}) \times 67.5$$ 
  (Highly linear functions branch at steep 90° angles; highly complex functions branch at wide 22.5° angles).
* **Magnitude (`mag`):** The final physical mass of the block, calculated as: 
  $$\text{Magnitude} = (\text{branches} + 1) \times (\text{args} + 1) + (0.05 \times \text{loc})$$
* *Note on Arguments:* The Protocol upgraded the argument counter to recognize space-separated arguments, ensuring languages like Lisp, Scheme, and Shell calculate accurate magnitudes alongside comma-separated C-family languages.

### 2. The Naming Shields
Extracting a function name from raw text is notoriously difficult; naive regex frequently destroys complex C++ signatures or Objective-C methods. To guarantee pristine architectural labeling, GitGalaxy utilizes a gauntlet of **Naming Shields**:
* **The C++ Operator Shield:** Safely intercepts and extracts overloaded symbolic operators (e.g., `operator<<`, `operator==`) and type casts (e.g., `operator bool`) *before* standard extraction destroys the non-alphanumeric symbols.
* **The C++ Test Macro Shield:** Extracts the true test name from complex macro wrappers, correctly labeling `BOOST_AUTO_TEST_CASE(MyTest)` or `TEST(Suite, MyTest)` simply as `MyTest`.
* **The C++ Scope Shield:** Temporarily replaces the double-colon (`::`) with a safe `__SCOPE__` token. This blinds the standard single-colon guillotine, ensuring names like `std::vector::push_back` aren't erroneously truncated to `std`.
* **Objective-C Extraction:** Surgically parses Apple's unique bracketed message syntax and leading `-`/`+` modifiers to extract the true method name.
* **Makefile Variable Shield:** Protects `$(VAR)` declarations from being shattered by parenthesis-splitting logic.

### 3. Functional Classification
Finally, the satellite is assigned a *texture* (its functional classification: `io`, `mutation`, `logic`, `event`, etc.). The engine first checks for explicit architectural tags (like `@gal_type: mutation` in the block's comments). If none exist, it infers the texture based on standard naming conventions (e.g., functions starting with `fetch` become `io`; `parse` becomes `logic`). If the name is ambiguous, it falls back to the heavy regex sensors to classify the block based on its literal contents.

## 2.3.5.E. The Cartographer: Fractal Fibonacci Positioning

The Cartographer transforms flat file lists into a deterministic 3D star map. By applying procedurally generated patterns to digital architecture, it ensures the visual layout reflects the structural hierarchy and "gravitational" importance of the repository's components. Under the Protocol, the engine utilizes a collision-aware packing algorithm to create organic, repeatable, and dense volumetric galaxies.

### 1. Sectorization & Hull Calculation (The Bounding Boxes)
Before spatial coordinates are assigned, the engine must calculate the physical footprint of every folder (Constellation).
* **Sector Census:** Files are grouped by their root directory.
* **The Sun Mass:** Within each constellation, the file with the highest Structural Mass is designated as the central "Sun."
* **Dynamic Hull Radius:** The engine calculates the required bounding box for the entire folder using the baseline spacing (`MICRO_SPACING` of **250.0**) combined with the footprint of its central star:
  $$\text{HullRadius} = \text{SunFootprint} + (\sqrt{\text{StarCount}} \times 250.0)$$
* **Prioritization:** The sectors are then sorted by their massive Hull Radii, ensuring the largest architectural hubs are placed nearest to the galactic core.

### 2. The Ray-Casting Dynamic Mask (Macro Layout)
Replaces the legacy static spiral with an active collision-avoidance system.
* **The Core Exclusion Zone:** The absolute center of the map is preserved by a `CORE_EXCLUSION_RADIUS` of **600.0** units, preventing massive monolithic files from collapsing into the origin point.
* **Angular Stepping:** As the engine loops through the constellations, it calculates the required angular step ($\Delta\theta$) based on the combined radii of the current and previous constellations, ensuring an optimal `MACRO_STEP_FACTOR` of **1.5x**.
* **Ray-Casting Intersection Math:** To prevent the spiral arms from overlapping as they wrap around the core, the engine shoots a mathematical ray down the current angle. It evaluates a quadratic intersection against an array of all previously `placed_circles` (representing previously placed constellations).

By solving the ray-circle intersection where $r$ is the distance along the ray and $(p_x, p_z)$ is the center of a previously placed constellation with radius $p_r$:

$$r^2 - 2r(p_x \cos\theta + p_z \sin\theta) + (p_x^2 + p_z^2 - (p_r \times 1.5)^2) = 0$$

* **The "Why" (Dense Packing):** The engine pushes the new constellation outward only to the furthest intersecting positive root ($r$). This guarantees zero collisions while ensuring the galaxy remains as tightly packed as mathematically possible, preventing sparse, disconnected visualizations.

### 3. Local Star Systems & Constellation Tilt (Micro Layout)
* **Dynamic Footprints:** The clearance required for a single star is no longer static. The `_calculate_orbit_footprint` method dynamically scales the visual radius and orbital clearance based on the star's literal Structural Mass.
* **The Golden Angle:** Planets orbit their central Sun using the classic Fibonacci `MICRO_GOLDEN_ANGLE` ($\approx$ **2.399** radians). The radius expands based on the square root of the star's mass-rank, gracefully decreasing the density of the star system as it moves outward.
* **Volumetric Tilting:** To break the artificial flatness of a 2D plane, each constellation is rotated on its local axis. Using hash-derived math, entire folders are tilted in unique directions with a maximum inclination (`MAX_TILT_DEG`) of **15.0°**, creating a true 3D volumetric cloud.

### 4. Organic Entropy (Hash Jitter)
To break the mechanical perfection of the mathematical spirals, the engine injects "Organic Noise" via the `_hash_jitter` function.
* **MD5 Seed Logic:** It hashes the filename to a hex string, mapping it to a normalized float between **-1.0** and **1.0**.
* **3D Jitter Magnitudes:**
  * **X/Y Jitter:** **100** units.
  * **Z Jitter:** **400** units (The Z-axis receives a 4x multiplier to aggressively deepen the volumetric layering of the stars).
* **The "Why" (Reproducible Chaos):** A perfectly mathematical spiral feels artificial and makes it harder for the human eye to distinguish individual stars. Jitter provides the "texture" of a real galaxy. Because the seed is based on the filename, the chaos is strictly deterministic—a file will always "vibrate" to the exact same relative sub-coordinate every time the map is rendered, allowing the developer to build a persistent mental map of the project's physical shape.

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.



---

**[⬅️ Back to Master Index](index.md)**
