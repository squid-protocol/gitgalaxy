---
description: "How to debug what detector.py extracted for a file: WORKER-TRACE log, recorder DB columns, the registry-declaration trap, two detector paths, serial rerun."
---
# Debugging what detector.py actually extracted

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

Before tracing `_slice_by_keywords`/`_slice_by_terminator`/etc. by hand to understand why a
signal looks wrong for some target file or corpus, check what the engine actually did first —
much cheaper than re-deriving it from the regex/slicing logic cold (#2547: confirmed the exact
root cause — a slicer-synthesized non-function bucket name being miscounted as an orphan — in a
few minutes this way, instead of hours of pure static reading):

- `galaxyscope <path> --db-only --debug --output <scratch-dir>` and grep the resulting log for
  `[WORKER-TRACE] extracted functions for` — one line per file, listing the exact satellite/
  function names `_function_slice` produced for it (`detector.py`'s own debug trace, gated
  behind `logger.isEnabledFor(logging.DEBUG)`). This is the fastest way to see whether a
  suspiciously-named entry (a synthetic bucket, a reused generic keyword, a truncated remnant)
  is in play, before assuming the signal count itself is what's wrong.
- Cross-reference the aggregated per-file numbers in the recorder DB this same run produces
  (`<scratch-dir>/<repo>_galaxy_master.db`, `file_data` table) — column names are the
  `record_keeper.py`-renamed form of the raw equation keys (e.g. `unreferenced_by_name` →
  `state_unreferenced`, `api` → `arch_api`; confirm via `.schema file_data` since this evolves).
- **A unit test does not exercise the config pipeline, and for a REGISTRY DECLARATION that
  difference is the whole bug.** Tests and the probe scripts build `StructuralExtractor` from
  `LANGUAGE_DEFINITIONS` directly; a real scan first goes through `language_lens.py`, whose
  `_calibrate_lookup_maps` compiles every **string** value inside a language's `rules` into a
  regex (a guard for definitions loaded from external JSON), and then through galaxyscope's
  `copy.deepcopy` + `PROJECT_OVERRIDES` merge. A non-pattern helper key therefore belongs at the
  TOP LEVEL of the definition, beside `lexical_family` -- put one in `rules` and it silently
  becomes `re.compile("...")` with every test still green (#2806, which also blessed a wrong
  golden master before a one-file scan caught it).
- For a control/golden corpus already checked out locally (e.g. `keyword-rosetta`,
  `language-crucible`), point `galaxyscope` straight at it this way instead of writing a
  standalone repro script — the census requires git-tracked files (see `census-requires-git-
  tracked` in a corpus's own deviation ledger if one exists), so scan the real corpus checkout,
  not an ad hoc copy.
- detector.py has two paths: function boundaries read `_build_brace_safe_stream` (literals,
  comments and dead `#if 0` branches blanked); rule counts (`coding_analysis`) run on the raw
  segment (dead branches blanked by `_blank_dead_preproc_branches`). A fix must shield both, keep
  masking length-preserving, and never blank live directive lines in the count path.
- Suspected scan non-determinism: rerun with `GALAXYSCOPE_MAX_WORKERS=1` (serial extraction)
  before assuming a race (#2988).
