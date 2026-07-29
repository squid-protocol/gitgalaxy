# Structural Code Analyzer & Spatial Cartographer

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

The `detector.py` module houses the `PrimaryDetector` structural code analyzer and spatial cartography components for GitGalaxy. The analyzer executes regular expression rule suites to extract function definitions, parameter counts, cyclomatic branching, and control-flow density into a fixed 51-element schema. It also computes spatial layout coordinates for rendering the repository as an interactive 3D node graph.

---

## Viability Gates & Ecosystem Overrides

Before extracting structural metrics, the analyzer validates file viability:

* **Structural Confidence Floor:** Files with confidence scores below `0.42` bypass full structural parsing, registering as unparsed file mass.
* **Prose & Data Bypass:** Markdown, plaintext, JSON, and CSV files bypass function extraction rules.
* **Ecosystem Header Override:** Declarative C/C++ header files (`.h`) lacking function body braces often fall below `0.42` confidence. If locked to C/C++ by `language_lens.py`, the analyzer boosts parsing confidence to `1.0`, ensuring macro headers are fully extracted.

---

## String Literal & Sequence Shielding

To prevent rogue braces (`{}`), parentheses (`()`), or quotes (`"`) inside text literals from desynchronizing bracket-tracking state machines, the analyzer executes string shielding:

* **Atomic Sequence Masking:** Masks C++ raw strings (`R"EOF(...)EOF"`) and Python triple quotes (`"""`) before single quotes, preventing inner quotes from prematurely closing strings.
* **Heredoc State Machine:** Isolates multi-line heredocs (`<<-EOF`) in scripting languages (Bash, Ruby, Elixir).
* **Ruby Sequence Shielding:** Masks Ruby bracketed literals (`%w[...]`, `%q{...}`).
* **Backtracking Latency Guard:** Measures regex execution time. Shielding operations taking longer than 0.5s emit diagnostic warnings to identify backtracking bottlenecks.

---

## Metric Extraction & 51-Element Schema

The analyzer separates executable code from comment streams to enforce independent metric measurement:

### 1. Code Stream Analysis & Schema Binding
* **Fixed 51-Element Schema:** Metric counts are bound directly to keys in `UNIVERSAL_METRICS_SCHEMA`. Unregistered custom metrics are rejected, guaranteeing an exact 51-element array structure per file. This prevents schema drift in downstream ML risk models.
* **Indentation Density Signatures:** Measures tab vs. space indentation distribution to record formatting standards per file.

### 2. Comment Stream Telemetry
* **Technical Debt Markers:** Tallies planned debt markers (`TODO`, `FIXME`) and fragile debt markers (`HACK`, `XXX`).
* **Commented Code Detection:** Detects commented-out executable logic or hidden URL structures.
* **Header Comment Parsing:** Scans the top 500 lines of files to extract authorship tags and top-level file architectural descriptions.

---

## Metric Extraction Modes

The analyzer routes code streams into specialized extraction algorithms based on language family:

* **Mode A: Label-Based Slicing (Procedural Languages):** Scans Assembly, AGC, and COBOL files for target labels, capturing statements until encountering return keywords (`RET`, `GOBACK`, `END-PERFORM`).
* **Mode B: Recursive Scope Tracking (C-Family & Lisp):** Tracks nested braces `{}` or parentheses `()`. Includes preprocessor shields to prevent floating macro braces (`#else {`) from corrupting scope stacks.
* **Mode C: Density Stratification (Python & YAML):** Identifies structural igniter keywords (`def`, `class`), records baseline indentation, and captures logic until indentation drops back to baseline.
* **Mode D: Semantic Keyword Stacking (Scripting Languages):** Tracks keyword pairs (`if`/`fi`, `def`/`end`) in Shell, Ruby, Lua, and Elixir. Includes inline modifier guards to prevent single-line statements (`return if condition`) from corrupting depth stacks.
* **Mode E: Terminator Cleaving (Declarative Languages):** Used for SQL, Erlang, and Prolog. Begins block collection on igniter keywords (`SELECT`, `CREATE`) and closes blocks upon encountering statement terminators (`;` or `.`).

---

## Function Metrics & Signature Shields

Extracted functions (satellites) undergo magnitude and trajectory calculations:

### 1. Function Complexity & Trajectory Metrics
* **Control Flow Ratio ($cf\_ratio$):** Measures branching density relative to total hits:
  $$cf\_ratio = \frac{\text{branches}}{\max(\text{total\_hits}, 1)} \in [0.0, 1.0]$$
* **Logic Trajectory Angle ($\theta$):** Maps control flow density to spatial orientation angle:
  $$\text{Angle} = 22.5^\circ + (1.0 - cf\_ratio) \times 67.5^\circ$$
* **Function Magnitude ($\text{Mag}$):** Calculates function structural mass:
  $$\text{Magnitude} = (\text{branches} + 1) \times (\text{args} + 1) + (0.05 \times \text{LOC})$$

### 2. Signature Extraction Shields
* **C++ Operator Shield:** Preserves overloaded operator signatures (`operator<<`, `operator==`) during name parsing.
* **C++ Test Macro Shield:** Extracts test case names from macro wrappers (`BOOST_AUTO_TEST_CASE(MyTest)` $\rightarrow$ `MyTest`).
* **C++ Scope Shield:** Replaces scope resolution operators (`::`) with temporary tokens (`__SCOPE__`) to prevent truncation.
* **Objective-C Signature Parsing:** Parses bracketed message syntax and leading `+`/`-` method modifiers.

---

## 3D Graph Cartography & Spatial Positioning

The cartography engine transforms flat file lists into 3D spatial node networks:

### 1. Directory Sectorization & Hull Calculations
Files are grouped by directory sectors. Within each sector, the file with the highest structural mass is designated as the primary directory hub node. Sector bounding radii are calculated based on hub node mass and file count:

$$\text{HullRadius} = \text{HubFootprint} + (\sqrt{\text{FileCount}} \times 250.0)$$

### 2. Ray-Casting Layout & Collision Avoidance
To position directory clusters on a 2D layout plane without node collisions:
* **Core Exclusion Zone:** Maintains a center clearance radius of 600.0 units.
* **Angular Spatial Hashing:** Divides 360-degree layout space into 360 angular memory bins.
* **Ray-Circle Intersection Math:** Solves quadratic ray-circle intersection equations for placed cluster bounds $(p_x, p_z)$ with radius $p_r$:
  $$r^2 - 2r(p_x \cos\theta + p_z \sin\theta) + (p_x^2 + p_z^2 - (p_r \times 1.5)^2) = 0$$
  Positions new clusters at the furthest positive root ($r$), ensuring dense, collision-free node packing.

### 3. Local Orbits & Volumetric Tilting
* **Fibonacci Spiral Layout:** Child nodes orbit directory hubs along Fibonacci spiral angles ($\approx 2.399$ radians).
* **Volumetric Tilting:** Tilts directory planes along local axes up to a maximum inclination of 15.0°, creating a 3D node cloud.
* **Deterministic Jitter:** Applies MD5 filename hashing to inject reproducible 3D spatial noise (X/Y jitter: 100 units, Z jitter: 400 units), creating organic node separation while ensuring repeatable visual layouts across scans.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source module for `detector.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - WebGL 3D repository visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

