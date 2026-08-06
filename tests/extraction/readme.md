### Structural Extraction Gauntlets

This directory contains the adversarial test suite for GitGalaxy's universal extraction engine
— the rules that pull function names, class names, arguments, and dependency paths out of raw
source text without an AST.

Building a parser without an Abstract Syntax Tree (AST) means naive regular expressions can
easily match the wrong thing or, worse, hang on nested logic via catastrophic backtracking
(ReDoS). This suite exists to check that the heuristic **blAST Engine** isolates exact
structural identifiers across 30+ languages and survives adversarial or pathological
formatting without either failure mode.

**Note:** most languages' cases have since migrated out of the four dict files below into
`languages/test_<lang>.py`, one file per language (see `how_to_harden_extraction.md`). That same
`languages/` directory also colocates a second, independent test concern: `test_<lang>_strict.py`
per language, proving `language_standards.py`'s *structural signature* rules (branch, io,
safety_bypasses, ReDoS immunity, etc. — not the func_start/args/class_start/dependency extraction
this readme describes). The `_strict` suffix and a separate `_strict_harness.py` helper module
keep the two concerns' files distinguishable and independently importable side by side.

---

### Running This Suite

These tests fire thousands of mutated, multi-language code snippets at the engine. To run this
suite in isolation:

```bash
python -m pytest tests/extraction/ -v
```

---

### The Four Extraction Rules

Each file below proves the engine can cleanly extract its target while ignoring surrounding
noise — long attribute chains, async modifiers, preprocessor macros.

#### 1. `test_function_extraction.py`
* **Validates:** The `func_start` heuristic rules across 32 distinct language grammars.
* **Proves:** The engine can pinpoint exact function and method names while stripping away C++ macros, Scala 3 transparency modifiers, Java annotations, and multi-line generic declarations without losing scope.

#### 2. `test_class_extraction.py`
* **Validates:** The `class_start` boundary rules.
* **Proves:** The engine isolates the precise name of an object-oriented entity (class, struct, interface, trait, enum), correctly ignoring inheritance chains, Dart mixins, and C# interface stacking to return only the clean entity name.

#### 3. `test_args_extraction.py`
* **Validates:** The `args` capture rules.
* **Proves:** Parameter extraction is the hardest of the four to parse heuristically. This suite checks the engine can handle large parameter blocks, default array arguments, and multi-line lambda closures without a nested-parentheses ReDoS spiral.

#### 4. `test_dependency_extraction.py`
* **Validates:** The `_dependency_capture` rules, tested across 37 languages.
* **Proves:** The engine extracts the exact file path or module name from an import statement, correctly handling ES6 destructuring, Rust `pub use crate::` chains, and Python alias stacking without capturing extra modifiers.

---

### The 3-Tier Adversarial Matrix

Every language in these gauntlets is tested through three phases. A regex has to pass all
three to ship.

1. **`valid`** — Proves baseline precision: the engine must match the payload and isolate exactly the target string (via capture groups), with no leftover modifiers, return types, or whitespace.
2. **`invalid`** — Proves the engine doesn't false-positive on lookalikes: it must return `None` on structural lookalikes such as instantiations (`new Target()`), control flow (`if (Target)`), or plain variable assignments.
3. **`pathological`** — Proves ReDoS immunity and correct handling of adversarial formatting: the engine must still extract the target from code with extreme vertical whitespace, tabs, or modifier stacking, in $O(1)$ or $O(N)$ time, without hanging the CPU thread.

---

### Extending a Gauntlet

To add a new language to a gauntlet, add it to the constant dictionaries at the top of the
relevant test file using the standard schema:

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
