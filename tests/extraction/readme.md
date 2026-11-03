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
per language, proving `gitgalaxy/standards/language_standards/`'s *structural signature* rules (branch, io,
safety_bypasses, ReDoS immunity, etc. — not the func_start/args/class_start/dependency extraction
this readme describes). The `_strict` suffix and a separate `_strict_harness.py` helper module
keep the two concerns' files distinguishable and independently importable side by side.

Also here: `_extraction_harness.py` (the shared valid/invalid/pathological assertions the
per-language files import), the `test_unicode_identifiers*.py` and `test_identifier_astral_fill.py`
suites (#3814: identifiers follow Unicode UAX #31), and `tools/` (`verify_candidates.py`,
`audit_strict_coverage.py`, `sweep_redos_scaling.py`). The how-to guides:
`how_to_harden_extraction.md` (the four pillars), `how_to_harden_strict_signatures.md` (the
`_strict` suites) and `how_to_extend_class_start_named_extraction.md` (named class extraction).

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
* **Validates:** The `func_start` heuristic rules for the languages not yet migrated to `languages/`.
* **Proves:** The engine can pinpoint exact function and method names while stripping away C++ macros, Scala 3 transparency modifiers, Java annotations, and multi-line generic declarations without losing scope.

#### 2. `test_class_extraction.py`
* **Validates:** The `class_start` boundary rules.
* **Proves:** The engine isolates the precise name of an object-oriented entity (class, struct, interface, trait, enum), correctly ignoring inheritance chains, Dart mixins, and C# interface stacking to return only the clean entity name.

#### 3. `test_args_extraction.py`
* **Validates:** The `args` capture rules.
* **Proves:** Parameter extraction is the hardest of the four to parse heuristically. This suite checks the engine can handle large parameter blocks, default array arguments, and multi-line lambda closures without a nested-parentheses ReDoS spiral.

#### 4. `test_dependency_extraction.py`
* **Validates:** The `_dependency_capture` rules for the languages not yet migrated to `languages/`.
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

To add a new language to a gauntlet, add a `languages/test_<lang>.py` file (see
`how_to_harden_extraction.md`); its case dicts use the same schema as the dictionaries at the top
of the four files above:

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
