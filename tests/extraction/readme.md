### ⚔️ Mathematical Proofs: The Strict Extraction Gauntlets

This directory contains the adversarial proving grounds for GitGalaxy's universal extraction engine.

Building a planetary-scale parser without an Abstract Syntax Tree (AST) is widely considered dangerous by compiler engineers. Without a strict compiler toolchain, naive regular expressions will hallucinate architecture, corrupt forensic math, or trigger Catastrophic Backtracking (ReDoS) death spirals when encountering nested logic. 

This test suite exists to mathematically prove that our heuristic **blAST Engine** securely and deterministically isolates exact structural identifiers across 30+ programming languages, surviving the most pathological formatting a developer (or obfuscator) can throw at it.

**Note:** most languages' cases have since migrated out of the four dict files below into
`languages/test_<lang>.py`, one file per language (see `how_to_harden_extraction.md`). That same
`languages/` directory also colocates a second, independent test concern: `test_<lang>_strict.py`
per language, proving `language_standards.py`'s *structural signature* rules (branch, io,
safety_bypasses, ReDoS immunity, etc. — not the func_start/args/class_start/dependency extraction
this readme describes). The `_strict` suffix and a separate `_strict_harness.py` helper module
keep the two concerns' files distinguishable and independently importable side by side.

---

### 🧪 Execution Protocols

These gauntlets fire thousands of heavily mutated, multi-lingual code snippets at the engine. To run the extraction matrix in isolation:

```bash
python -m pytest tests/extraction/ -v
```

---

### 📂 Verified Capabilities & The Four Pillars

The following test suites validate the core structural spawners of the physics engine. Each file proves the engine can cleanly extract the target while stepping over massive attribute stacks, asynchronous modifiers, and preprocessor garbage.

#### 1. `test_function_extraction.py` (The Satellite Spawner)
* **Validates:** The `func_start` heuristic rules across 32 distinct architectures.
* **Proves:** The engine can pinpoint exact function and method names (the "Satellites") while entirely stripping away C++ macros, Scala 3 transparency modifiers, Java annotations, and extreme vertical generic blobs without losing scope.

#### 2. `test_class_extraction.py` (The Entity Census)
* **Validates:** The `class_start` boundary rules.
* **Proves:** The engine accurately isolates the precise name of an Object-Oriented entity (Class, Struct, Interface, Trait, Enum). It mathematically proves the regex ignores complex inheritance chains, Dart mixins, and C# interface stacking to return *only* the clean entity name.

#### 3. `test_args_extraction.py` (The Coupling Mass)
* **Validates:** The `args` capture rules.
* **Proves:** Parameter extraction is the hardest structural component to parse heuristically. This gauntlet proves the engine can swallow massive parameter blocks, default array arguments, and multi-line lambda closures without collapsing into a nested-parentheses ReDoS spiral.

#### 4. `test_dependency_extraction.py` (The Gravity Links)
* **Validates:** The `_dependency_capture` rules (Tested across a 37-Language Mega Suite).
* **Proves:** The engine can trace precise information flow by extracting the exact file path or module name from an import statement. It survives complex ES6 destructuring, Rust `pub use crate::` chains, and Python alias stacking without capturing dirty modifiers.

---

### 🧬 The 3-Tier Adversarial Matrix

Every single language mapped in these gauntlets is subjected to three distinct phases of adversarial testing. If a regex fails even one phase, the build is rejected.

1. **`valid` (The Iron Wall)**
   * **Purpose:** Proves baseline precision.
   * **Pass Condition:** The engine must match the payload AND strictly isolate the exact target string (using Capture Groups), leaving behind zero dirty modifiers, return types, or whitespace.
2. **`invalid` (Ghost Prevention)**
   * **Purpose:** Proves the engine will not hallucinate architecture.
   * **Pass Condition:** The engine MUST return `None` when fed malicious structural lookalikes (e.g., class instantiations like `new Target()`, control flow like `if (Target)`, or variable assignments). 
3. **`pathological` (The Frankenstein Test)**
   * **Purpose:** Proves ReDoS immunity and vertical parsing capability.
   * **Pass Condition:** The engine must successfully extract the target from code formatted with absurd vertical newlines, tabs, margin-hugging, and extreme modifier stacking, executing in $O(1)$ or $O(N)$ time without locking the CPU thread.

---

### 🛠️ Extending the Gauntlet

To subject a new language to the gauntlet, inject it into the constant dictionaries at the top of the respective test file using the standard schema:

```python
"new_language": {
    "valid": [
        ("function TargetName() {", "TargetName")
    ],
    "invalid": [
        "var TargetName = 5;",
        "if (TargetName) {"
    ],
    "pathological": [
        ("public \n async \n function \n TargetName \n (", "TargetName")
    ]
}
```