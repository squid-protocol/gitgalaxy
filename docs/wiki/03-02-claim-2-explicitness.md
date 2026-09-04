Claim 2 -- Coding Languages Evolve Towards Explicitness

After subjecting 40+ distinct programming languages to the blAST engine, the evidence suggests an inarguable pattern: the history of software language development is a trend towards explicitness. This correlation directly scales the ability for heuristic regex to scan for "Intent" rather than mere "Syntax."

In older, implicit languages, intent is often "hidden," requiring deep compiler context or the interpreter's "hidden knowledge" to understand. In modern languages, intent is "broadcasted" through explicit keywords and rigid, self-describing structures.

### 2.4.1.A. The "Banana" Paradox (Linguistic Relativity)

Before the age of global travel, some isolated languages lacked words for concepts they had never encountered—like a "banana." If the concept isn’t present, the language doesn’t need a name for it. We see the exact equivalent in the evolution of code:

* **The Invisible Shield (Assembly/C):** These languages have no "word" (keyword) for Memory Safety. A developer implements safety via convention (return codes, jump checks, pointer math), but to a heuristic scanner, the safety is invisible. Safety is an inferred concept, not a structural one.
* **The Modern Broadcast (Rust/Go/Swift):** Modern languages have finally "named" every feature in the complexity spectrum. Concepts like "Ownership," "Error Handling," and "Concurrency" have dedicated, unambiguous keywords. The scanner hits ~99% accuracy here because the code explicitly "screams" its intent to both machines and humans.

### 2.4.1.B. Normalizing the "Material" (The Steel vs. Stone Bridge)

To ensure comparative fairness, we must normalize the "Material Properties" of the languages. We do not judge a Shell script for being "worse" than Go; we acknowledge that it is built from a more opaque material.

* **The Steel Bridge (Go — one strictness gap):** The structure is explicit. We can clearly see the bolts and the tension cables. If there are no visible cracks, we can be 99% sure the bridge is safe.
* **The Stone Bridge (Shell — three strictness gaps):** The internal integrity is hidden inside the masonry. A visual inspection might show zero cracks, but the material might still be hiding faults.

To make the comparison fair, GitGalaxy applies two separate corrections (#2716). The Fidelity Coefficient $Fc$ is *measured*: keyword-rosetta plants identical defence in every language, and a rule that over-fires has each of its hits credited at the planted-to-measured ratio, so the same defence earns the same credit everywhere. The Implicit Risk Correction $Irc$ is *tabulated*: one point per thing the language lets you leave unsaid — static types, enforced error paths, memory safety, declared globals — from `analysis_lens.LANGUAGE_STRICTNESS`. A "Safe" rating in Shell still requires more defensive effort than in Go, but the amount is now written down per column rather than picked by bucket, and [08-03](08-03-transforming-regex-counts.md) renders both tables from the data the engine reads.

### 2.4.1.C. The Fidelity Matrix (40 Languages x 51 Signals)

This matrix maps the structural "Broadcast Power" of coding languages across history. Signals are clustered into logical processors to visualize the transition from Implicit (I) to Explicit (E) physics.

### 2.4.1.C. The Fidelity Matrix (40 Languages x 51 Signals)

This matrix maps the structural "Broadcast Power" of coding languages across history. Signals are clustered into logical processors to visualize the transition from Implicit to Explicit physics.

**Legend:**
* 🟦 **E (Explicit):** The language has dedicated, unambiguous structural syntax for this concept.
* 🟧 **I (Implicit):** The concept exists, but must be inferred from context, conventions, or secondary logic.
* ⚪ **- (None):** The concept is not structurally applicable to the language.

| Language (Year) | Tier (2025 buckets, retired by #2718 — see [08-03](08-03-transforming-regex-counts.md) for the live strictness rows) | CF | Phys | Risk | Domain | Thermo |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| MLIR (2019) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | ⚪ **-** | 🟦 **E** |
| Zig (2016) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Swift (2014) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Dockerfile (2013) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| TypeScript (2012) | 2 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Kotlin (2011) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Dart (2011) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Rust (2010) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Go (2009) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Scala (2004) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Groovy (2003) | 3 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟦 **E** |
| LiveCode (2001) | 3 | 🟦 **E** | 🟧 **I** | 🟧 **I** | 🟦 **E** | 🟧 **I** |
| C# (2000) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| SQLite (2000) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** |
| PHP 8 (1995/2020) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟦 **E** |
| Java (1995) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| JavaScript (1995) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟦 **E** |
| Ruby (1995) | 3 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟦 **E** |
| Lua (1993) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟦 **E** |
| Python (1991) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| Haskell (1990) | 2 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** |
| HTML5 (1990/2014) | 3 | 🟧 **I** | 🟧 **I** | 🟧 **I** | 🟦 **E** | 🟧 **I** |
| Bash/Shell (1989) | 3 | 🟧 **I** | 🟧 **I** | 🟧 **I** | 🟧 **I** | 🟧 **I** |
| Tcl (1988) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟧 **I** | 🟧 **I** |
| HyperTalk (1987) | 3 | 🟦 **E** | 🟧 **I** | 🟧 **I** | 🟦 **E** | 🟧 **I** |
| Perl (1987) | 3 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟧 **I** | 🟧 **I** |
| C++ (1985) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟦 **E** |
| MATLAB (1984) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟧 **I** |
| Objective-C (1984) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟦 **E** | 🟦 **E** |
| ABAP (1983) | 1 | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** | 🟦 **E** |
| M4 (1977) | 3 | 🟧 **I** | 🟧 **I** | 🟧 **I** | ⚪ **-** | 🟧 **I** |
| SQL (1974) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | ⚪ **-** | 🟦 **E** |
| Prolog (1972) | 2 | 🟧 **I** | 🟧 **I** | 🟧 **I** | ⚪ **-** | 🟧 **I** |
| C (1972) | 2 | 🟦 **E** | 🟦 **E** | 🟧 **I** | 🟧 **I** | 🟦 **E** |
| Yacc/Bison (1970) | 2 | 🟧 **I** | 🟦 **E** | 🟧 **I** | ⚪ **-** | 🟧 **I** |
| COBOL (1959) | 2 | 🟦 **E** | 🟧 **I** | 🟧 **I** | 🟦 **E** | 🟧 **I** |
| Fortran (1957) | 2 | 🟦 **E** | 🟧 **I** | 🟧 **I** | 🟧 **I** | 🟧 **I** |
| Assembly (x86) (1970s) | 3 | 🟧 **I** | 🟧 **I** | 🟧 **I** | ⚪ **-** | 🟧 **I** |
| AGC Assembly (1966) | 3 | 🟧 **I** | 🟧 **I** | 🟧 **I** | ⚪ **-** | 🟧 **I** |
| CSV/Data (Universal) | 1 | ⚪ **-** | ⚪ **-** | ⚪ **-** | ⚪ **-** | ⚪ **-** |

#### Column Legend (Signal Clusters)
* **CF (Control Flow):** branch, linear, closures, comprehensions.
* **Phys (Physics):** mass, args, func_start, class_start, import.
* **Risk (Risk Exposure):** safety, safety_neg, danger, flux, graveyard, debt.
* **Domain (Ecosystem):** ui_framework, ssr_boundaries, events, di.
* **Thermo (Thermodynamics):** telemetry, print_hits, bailout, halt, bitwise, locks, cleanup.

#### Column Legend (Signal Clusters)
* **CF (Control Flow):** branch, linear, closures, comprehensions.
* **Phys (Physics):** mass, args, func_start, class_start, import.
* **Risk (Risk Exposure):** safety, safety_neg, danger, flux, graveyard, debt.
* **Domain (Ecosystem):** ui_framework, ssr_boundaries, events, di.
* **Thermo (Thermodynamics):** telemetry, print_hits, bailout, halt, bitwise, locks, cleanup.

### 2.4.2.1. False Positives & Error Direction (Equations)

By trading the microscope of an AST for the telescope of blAST, we accept a 5% margin of microscopic error to achieve macroscopic velocity. When ambiguity exists, it manifests in specific, documented directions:

* **Neg-Safe Error Direction (Over-flagging):** In modern JavaScript, the double-bang `!!` operator is often flagged as a safety risk. While it coerces types (a structural risk), it is usually a standard idiom for truthiness. Direction: False Risk Inflation.
* **Tests Error Direction (Boilerplate Noise):** In large enterprise projects, non-test files often contain internal helper methods like `validateInput` or `checkStatus`. These can hit "Test Keywords" (validate, check). Direction: False Verification Bonus.
* **Heat Error Direction (Macro Ambiguity):** C/C++ Macros that wrap simple loops can be missed, leading to a "False Cold" reading. Conversely, complex macros that wrap definitions can look like branching. Direction: Contextual Noise.

### 2.4.1.D. Conclusion: Design for Scannability

The progression from implicit to explicit suggests that scannability — the trend towards explicitness — is increasing. The younger the language, the louder it "screams" its intent. The blAST engine normalises what it can *measure* of that variation with the per-signal Fidelity Coefficient ($Fc$), and writes down what it cannot measure — the silence of the ancients — as the strictness table's $Irc$, one point per thing the language leaves unsaid.

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.



---

**[⬅️ Back to Master Index](index.md)**
