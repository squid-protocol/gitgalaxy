---
description: "Where the add-a-language protocol and extraction gauntlet hardening docs live, and how per-language strict tests and extraction tests are organised on disk."
---
# Adding or hardening a language's structural signatures

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

Full protocol (LLM generation prompt, the 12 numbered engine rules for ReDoS/boundary
correctness, strict-testing prompt) lives in
`gitgalaxy/standards/how_to_add_a_language.md` — read that file directly rather than expecting
a summary here; it's long because the rules matter and drift if paraphrased. Tests for this
live in `tests/extraction/languages/test_<lang>_strict.py`, one file per language, colocated
alongside that directory's own extraction-gauntlet `test_<lang>.py` files (the `_strict` suffix
avoids a basename collision between the two, since this repo has no `tests/__init__.py`
anywhere). They share a `_strict_harness.py` ReDoS-testing helper module the same way the
extraction gauntlets share `_extraction_harness.py` — two independent per-concern harnesses, not
one shared module. `tests/core_engine/test_language_standards_strict.py` now holds only the
handful of genuinely cross-language/global tests (registry-wide sanity checks, the harness's own
self-tests).

**Hardening the four extraction gauntlets** (func_start/args/class_start/_dependency_capture
test depth per language) is a related but distinct exercise, driven by
`tests/extraction/how_to_harden_extraction.md` — the companion doc epic #813 (closed) used to
take all 44 in-scope languages through a documented valid/invalid/pathological methodology, a
43-entry (and growing) recurring-bug-class list, and a strict verification chain
(`tests/extraction/tools/verify_candidates.py` → `audit_check.py` → `crucible_check.py`). Per-
language cases now live in `tests/extraction/languages/test_<lang>.py`, not the four old
monolithic dict files. Use the `harden-language-extraction` skill to pick this up for a new
language or a follow-on bug sweep rather than re-deriving the process from scratch.
