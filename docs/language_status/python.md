# Python — Structural Signature Coverage

Snapshot generated 2026-08-09 against `main`. Source: `LANGUAGE_DEFINITIONS["python"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_python.py` /
`test_python_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Python 3.14 |
| `_meta.blueprint_version` | 6.30 |
| `_meta.last_updated` | 2026-03-11 |
| `lexical_family` | `line_exclusive` (single `#` line comments only, no native block-comment syntax — the engine's heuristic pass handles triple-quoted-string-as-docstring separately, see §5) |
| Structural signature keys wired | 61 / 64 (3 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_python.py`) | 60 |
| Strict-signature tests (`test_python_strict.py`) | 92 |
| Total dedicated Python test cases | 152 |
| Real-world function recall vs. `ast` ground truth (real pipeline) | ~60% — see §9 |
| Real-world function recall, isolated slicing (no prism upstream) | 100% — see §9 |
| Real-world class recall vs. `ast` ground truth | 100% — see §9 |

## 2. Identification surface

- **Extensions:** `.py .py3 .py2 .pyw .pyi .pyx .pxd .pxi .pyz .pyzw .bzl .gyp .gypi .vpython .vpython3 .rpy .smk` — modern/legacy suffixes, typed stubs, Cython, and Bazel/GYP/Snakemake build-tooling dialects that are secretly Python.
- **Exact filenames:** `setup.py`, `SConstruct`, `SConscript`, `BUCK`, `BUILD`, `wscript`, `Snakefile` — extensionless build/config scripts.
- **Discriminators:** `.py`, `requirements.txt`, `pyproject.toml`, `Pipfile`, `Pipfile.lock`, `tox.ini`, `poetry.lock`, `setup.cfg` — ecosystem anchors used to disambiguate.
- **Shebangs:** `python`, `python3`, `python2`, `pypy`, `pypy3`, `jython`.
- **`embedded_python`** is a separate language entry (own status doc, not this one) for Python embedded inside another host file (e.g. Django templates, Jupyter-adjacent contexts) — don't conflate the two when reading test counts.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` and `how_to_add_a_language.md` use.
Description is what Python's *actual* regex matches, not the generic cross-language definition.

**Topology & structure**
| Key | What it captures for Python |
|---|---|
| `branch` | `if elif else for while with try finally match case and or` |
| `args` | `def`/`async def`/`lambda` parameter blocks, including PEP 695 (3.12+) bounded generics (`def Foo[T: Sequence[int]](x: T)`) |
| `structural_boundaries` | `def class return import from as pass continue break await assert del global nonlocal type` |
| `func_start` | Anchors `def`/`async def`, stepping over up to 5 decorator lines and PEP 695 generic brackets |
| `class_start` | Anchors `class`, same decorator/generic step-over, captures class name + base-class list |

**Safety & risk**
| Key | What it captures for Python |
|---|---|
| `safety` | `try except except* finally assert isinstance issubclass hasattr getattr dataclass BaseModel Field TypeGuard override` |
| `safety_bypasses` | Bare `pass`, bare/untyped `except:`/`except Exception`, wildcard `from x import *`, `# type: ignore`, `Any`/`cast`, empty `[]`/`{}` literal init |
| `high_risk_execution` | `eval exec subprocess.call/Popen/run os.system pickle.loads yaml.unsafe_load shell=True` |
| `io` | `open requests httpx aiohttp boto3 os. sys. pathlib socket sqlalchemy psycopg2 asyncpg` |
| `api` | Top-level `def`/`class` without a leading underscore, `__all__ =`, FastAPI/Flask-style `@app.get/post/put/delete` route decorators (implicit-public-by-default, per Rule 1 of the engine's generation rules) |
| `state_mutation` | `global`/`nonlocal`, `self.`/`cls.` attribute assignment, walrus operator (`:=`), list/dict mutator calls (`.append/.extend/.update/.pop/.remove/.insert/.clear`) |
| `dead_code` | Commented-out `# def/class/import/if/for/while/try/return` |
| `doc` | Triple-quoted docstrings, Sphinx-style `:param/:return/:raises/:type`, Google-style `Args:/Returns:/Yields:/Raises:/Attributes:` |
| `test` | `unittest pytest TestCase fixture patch`, `def test_`, `assert`, `Mock` |

**Architecture & domain sensors**
| Key | What it captures for Python |
|---|---|
| `concurrency` | `async await asyncio threading multiprocessing ThreadPoolExecutor TaskGroup gather create_task` |
| `ui_framework` | `streamlit django.shortcuts flask.render_template gradio dash fasthtml jinja2 render` |
| `closures` | `lambda` |
| `globals` | `os.environ sys.argv sys.path`, `globals()`, `locals()` |
| `decorators` | Any `@`-prefixed line |
| `generics` | `typing` generics (`List/Dict/Set/Tuple/Optional/Union/TypeVar/Generic/Any/Callable/Mapping[...]`), lowercase builtin generics (`list/dict/set/tuple/type[...]`), `->` return annotations |
| `comprehensions` | `[...for...]` / `{...for...}` / `(...for...)` shapes, bounded to 500 chars per side (list/dict/set comprehensions and generator expressions — Python has no `.map(`/`.filter(` builtin, so it doesn't share JS's comprehensions idiom) |
| `scientific` | `import`/`from` referencing `numpy pandas scipy matplotlib opencv cv2` |
| `hardware_bridge` | `import`/`from` referencing `serialport usb bluetooth socket.io websocket printer webgl` |
| `cryptography` | `import`/`from` referencing `crypto bcrypt x509 tls ssl jsonwebtoken argon2` |
| `reflection_metaprogramming` | Dunder hooks (`__getattr__ __setattr__ __del__ __call__ __new__ ...`), `@staticmethod/@classmethod/@property`, `getattr/setattr/inspect.` |
| `llm_api` / `llm_orchestrator` / `llm_vector_store` / `ml_traditional` / `dl_frameworks` | Shared cross-language `GLOBAL_` AI/ML SDK sensors (issue #322 moved these off a hand-pasted per-language duplicate) |
| `import` | `from X import`, `import X`, `__import__(`, `importlib.import_module(` |
| `_dependency_capture` | Extracts the exact dotted module path from all four import forms above (feeds the dependency DAG) |
| `_named_token_capture` | Captures the raw name list from `from X import ...` |
| `ownership` | `__author__ =`, `Author:`, `Created by:` |

**Specialized subsystems**
| Key | What it captures for Python |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`, `[spec ...]`, `[audit ...]` traceability tags |
| `ssr_boundaries` | `render_template HttpResponse JSONResponse TemplateResponse WSGIApplication ASGIApplication` |
| `events` | `Signal receiver post_save pre_save asyncio.Event EventDispatcher emit send blinker` |
| `dependency_injection` | `Depends Provide Inject Container dependency_injector fastapi.Depends` |
| `pointers` | `ctypes.POINTER c_void_p byref` |

**Resource management & stability**
| Key | What it captures for Python |
|---|---|
| `telemetry` | `logging/logger/structlog/sentry_sdk/datadog/loguru` `.info/.error/.warn/.warning/.debug/.trace/.log/.exception/.critical` |
| `debug_prints` | `print(`, `input(` |
| `explicit_casts` | `int str float list dict set tuple bool bytes cast(` |
| `panics_and_aborts` | `raise quit exit sys.exit abort` |
| `thread_sleeps` | `time.sleep asyncio.sleep Thread.join` |
| `bitwise_ops` | `<< >> ^ ~` |
| `sync_locks` | `Lock RLock Semaphore BoundedSemaphore Event Condition Barrier` |
| `immutability_locks` | `Final frozenset mappingproxy immutable` |
| `cleanup` | `close( __exit__( del( shutdown( cleanup(` |
| `encapsulation` | Leading-underscore naming convention (Python's only privacy signal — no `private` keyword) |
| `listeners` | `on_event add_listener subscribe callback handler` |
| `test_skip` | `pytest.mark.skip unittest.skip mock. MagicMock` |

**Advanced algorithmic / hybrid domain / AppSec sensors**
| Key | What it captures for Python |
|---|---|
| `lazy_evaluation` | `yield`, `yield from`, `Generator/AsyncGenerator/Iterator/AsyncIterator` |
| `vectorized_math` | `einsum matmul tensordot vdot bmm`, `.dot(`, the `@` matrix-multiplication operator between operands |
| `serialization_parsing` | `pickle.loads/Unpickler marshal.loads ast.literal_eval` |
| `regex_execution` | `re.compile/search/match/sub/findall/split` |
| `time_date_logic` | `datetime.datetime timedelta time.sleep time.time calendar` |
| `ipc_rpc_bridges` | `multiprocessing subprocess xmlrpc socketserver` |
| `memory_scraping` | String-built `/proc/` paths, `/proc/<pid>/mem` |
| `exfiltration_camouflage` | `requests.post/urllib.request/httpx.post` calls whose arguments mention `checkmarx/telemetry/metrics/audit/log` (case-insensitive — flags exfiltration traffic dressed up as observability) |

## 4. What GitGalaxy explicitly does not track

Three keys are hard-set to `None` in Python's `rules` dict (Rule 4 of the engine's generation
rules: explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`macros`** — Python has no C-style preprocessor.
- **`memory_alloc`** — memory is GC-managed; there's no manual allocation to track.
- **`inline_asm`** — no native inline-assembly construct.

## 5. Known limitations (accepted, not fixed)

Two gaps are deliberately documented rather than fixed, via `known_limitation`-named tests in
`test_python.py`:

1. **No whitespace tolerance between a function name and a PEP 695 generic bracket.**
   `def Foo[T](...)` matches; `def Foo\n[T](...)` does not. Judged not worth fixing — no real
   formatter (`black`, `ruff format`) ever produces that exact vertical split; real-world
   splitting happens between modifiers/parens/inside the bracket's contents, never between an
   identifier and the generic bracket immediately following it.
2. **`_dependency_capture` matches inside triple-quoted strings.** Unlike `func_start` (shielded
   by Mode C's indentation-based slicing before matching), `_dependency_capture` runs against
   fully unshielded raw file content for every language, unconditionally — an `import os`-shaped
   line sitting at true line-start inside a Python triple-quoted string still produces a phantom
   dependency-graph edge. This is recurring bug class 10 in
   `tests/extraction/how_to_harden_extraction.md`, present for every language, not Python-specific
   — documented here rather than silently worked around.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 60 tests in
  `tests/extraction/languages/test_python.py` — valid/invalid/pathological cases per rule, plus
  the PEP 695 regression tests and the two known-limitation tests above. Fully migrated to the
  per-language file (epic #813, issue #818) — nothing left in the old monolithic gauntlet files
  for Python.
- **Strict signature suite** (all other wired keys): 92 tests in
  `tests/extraction/languages/test_python_strict.py` — positive match, negative/false-positive
  match, cross-rule ambiguity, and ReDoS-immunity checks per signature (epic #518, issue #606;
  deepened further by issue #1072's AI/ML sensor pass, see §7).

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#606](https://github.com/squid-protocol/gitgalaxy/issues/606) — Strict parsing tests for Python structural signatures (epic #518).
- [#818](https://github.com/squid-protocol/gitgalaxy/issues/818) — Extraction hardening for Python (epic #813): PEP 695 nested-bracket fixes to `args`/`func_start`/`class_start`, deepened valid/invalid/pathological case counts.
- [#1072](https://github.com/squid-protocol/gitgalaxy/issues/1072) — Closed a real security-relevant gap: Python's entire AI/ML extension pack (`llm_api`, `llm_orchestrator`, `llm_vector_store`, `dl_frameworks`, `ml_traditional`, `vectorized_math`) plus 13 other keys (`closures`, `comprehensions`, `lazy_evaluation`, `api`, `cryptography`, `encapsulation`, `exfiltration_camouflage`, `hardware_bridge`, `import`, `memory_scraping`, `structural_boundaries`, `test`, `bitwise_ops`) had zero test coverage despite being wired and live.

**Cross-language fixes that touched Python along the way:**
- [#322](https://github.com/squid-protocol/gitgalaxy/issues/322) — Moved Python's (and JavaScript's) hand-pasted AI/LLM SDK detection onto the shared `GLOBAL_LLM_*`/`GLOBAL_ML_*`/`GLOBAL_DL_*` pattern used by every other language.
- [#713](https://github.com/squid-protocol/gitgalaxy/issues/713) — Fixed `spec_exposure`'s unbounded `[^\]]*` ReDoS shape, copy-pasted across 28 languages including Python.
- [#1041](https://github.com/squid-protocol/gitgalaxy/issues/1041) — Nested functions were silently dropped from extraction (affected every language routed through the same extractor path, Python included).

**Real defects found via this doc's own §9 measured-accuracy pass, since fixed:**
- [#1182](https://github.com/squid-protocol/gitgalaxy/issues/1182) (CLOSED, merged #1188) — `_calculate_block_metrics` truncated every extracted name to 40 chars, corrupting any function/method name longer than that.
- [#1183](https://github.com/squid-protocol/gitgalaxy/issues/1183) (CLOSED, merged #1190) — `_partition_segments`'s embedded-language handshake could false-trigger on `<script`/`<style` substrings appearing inside an ordinary string/regex literal (not real embedded code), permanently misrouting the rest of the file to the wrong language's rules.
- [#1184](https://github.com/squid-protocol/gitgalaxy/issues/1184) (fixed, PR [#1192](https://github.com/squid-protocol/gitgalaxy/pull/1192) open pending merge) — `_build_indentation_safe_stream` (and the equivalent Mode D/E shields) stripped comments in a separate pass *after* string-shielding; an English contraction apostrophe inside a `#` comment (`don't`, `it's`) was indistinguishable from a real string-open quote, cascading into large dead zones of dropped functions. Fixed by merging comment-shielding into the same single-pass alternation as string-shielding, mirroring `_build_brace_safe_stream`'s already-correct design.

**Real defect found via this same pass, still open:**
- [#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193) (OPEN) — `prism.py`'s `_strip_single_line_comments` drives its delimiter list from the `line_exclusive` lexical family as a whole rather than per-language, so `;` (real comment char only for `assembly`/`agc_assembly`) and `%` (real comment char only for `matlab`) get treated as comment starts in the other 18 `line_exclusive` languages too, including Python — with zero string-shielding, so `;`/`%` *inside* a string literal also triggers false truncation. This is the dominant reason real-pipeline recall (§9) is still far below the isolated-slicing number.

Search performed via `gh issue list --search 'in:title "Extraction hardening: python"'` /
`'in:title "Strict parsing tests: `python`"'` / `'in:title python'` (2026-08-09) — the last query
also surfaces engine-wide bugs (`#1052`, `#1055`, metrics/scoring issues) that mention Python
incidentally without changing its signature rules; excluded here as not language-coverage-specific.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Four repos from the `v2.4.7` batch, chosen for a size/shape spread rather than four similar
mid-size projects:

- **[`cpython`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/cpython/cpython_galaxy_llm.md)** — Python's own reference implementation (the CPython interpreter + stdlib). The most adversarial Python codebase available: decades of eras, C-extension boundary code, and every syntax generation the language has shipped. Scanned in 12.78s.
- **[`django`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/django/django_galaxy_llm.md)** — large, long-lived production framework; heavy use of `api`/`ssr_boundaries`/`events`/`dependency_injection`-relevant patterns (signals, ORM, class-based views). Scanned in 18.06s.
- **[`requests`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/requests/requests_galaxy_llm.md)** — small, canonical single-purpose library; a useful low-noise baseline. Scanned in 0.45s.
- **[`black`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/black/black_galaxy_llm.md)** — a formatter that itself requires a full AST internally, scanned by an engine that has none; a pointed contrast case. Scanned in 1.12s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

## 9. Measured accuracy (real-world corpus, vs. AST ground truth)

Everything above describes what's *wired* and how it's *tested in isolation* — adversarial
snippets hand-picked to probe one rule at a time. This section is different: it measures what
the engine actually gets right on **real, unmodified production code**, using Python's own
`ast` module as ground truth. This is empirically stronger evidence than the unit-test suite
alone, because it exercises the segment-routing and scope-boundary machinery that sits between
"a regex matched" and "a function got correctly recorded" — machinery the isolated per-rule
tests don't touch.

**Methodology:** regenerated a fresh, *full* (not incremental — see the caution below) self-scan
of GitGalaxy's own repo (`python tests/tools/self_scan.py`, full precision, pinned to the exact
commit scanned), giving 228 Python files / 2,436 real functions / 61 real classes per
`ast.parse()`. For each file, diffed `ast.walk()`'s `FunctionDef`/`AsyncFunctionDef`/`ClassDef`
names (and each function's real parameter count) against `function_data`/`class_data` rows for
that file. Cross-checked the `branch` keyword rule separately using Python's `tokenize` module as
an independent ground truth, and by running the compiled `branch` regex directly against
`prism`-shielded `code_stream` (bypassing the DB entirely) to isolate the rule's own accuracy from
downstream aggregation. Also ran `_slice_by_indentation()` directly against each file's *raw*
content (bypassing `prism.split_streams()` entirely) to isolate the Mode C slicing logic's own
accuracy from whatever `prism.py` does upstream of it — this split turned out to matter a lot,
see the #1193 discussion below.

**Caution for future re-runs:** `self_scan.py` defaults to an *incremental* scan when
`docs/self_scan/gitgalaxy_master.db` already exists, which rehydrates cached per-file results for
any file whose *content* hasn't changed since the baseline commit. That's the right default for
normal orientation use, but it's wrong for measuring accuracy after an *engine* change (detector.py
changed, not the scanned files) — incremental mode silently reused pre-fix results the first time
this measurement was re-run post-#1184, understating the fix's effect. Delete the DB
(`rm docs/self_scan/gitgalaxy_master.db`) to force a full rescan before trusting a post-engine-fix
measurement.

| Signal | Result | Read as |
|---|---|---|
| Class extraction (`class_start`) | **100% recall** (61/61) | Fully reliable on this corpus |
| Function extraction, isolated Mode C slicing (bypasses `prism.py`) | **100% recall** (2436/2436) | `_slice_by_indentation` itself is now fully correct — confirms #1184's fix |
| Function extraction, real production pipeline (`prism.split_streams` → `detector.splice`) | **~60% recall** (1465/2436) | See #1193 below — the gap between this row and the one above **is** #1193 |
| Function-name precision (of functions found via the real pipeline) | **~98.7%** (1446/1465) | Engine essentially never invents a function once it finds one at all |
| Args-count exact match (for functions that *were* found) | **~35%** | Also downstream of #1193 — a truncated/corrupted signature line breaks arg-count parsing too |
| `branch` keyword rule, run directly against shielded code | **~133%** of a `tokenize`-based ground truth (catches everything, plus false-positive hits inside string literals this check doesn't shield against) | Simple keyword-alternation rules are far more reliable than boundary/entity extraction — but this specific comparison over-counts by design, see caveat below |

The `branch` percentage exceeding 100% is expected, not alarming: this check runs the raw regex
against `code_stream` with no further per-occurrence shielding, so it also matches `if`/`for`/etc.
appearing inside string literals — a looser check than what the detector's actual pipeline does
downstream. It's included to demonstrate that keyword-alternation rules are inherently more
robust than boundary-extraction rules (over-counting is a far gentler failure mode than the
under-counting boundary extraction suffers from), not as a precision claim.

**Four real, filed defects were found via this pass across two rounds of measurement** — three
now fixed, one still open. Each has a concrete reproduction, not a vague "heuristics are
imprecise" hand-wave:

1. **[#1182](https://github.com/squid-protocol/gitgalaxy/issues/1182) (CLOSED) — 40-character
   name truncation.** `detector.py`'s `_calculate_block_metrics` did `"name": name[:40]`. 984 of
   this corpus's 2,436 functions (40%) have real names over 40 chars — this codebase's own long
   descriptive test-naming convention routinely exceeds it. A naming-fidelity bug, not a recall
   bug — it was initially mistaken for hallucinated/phantom functions during the first audit pass
   (a truncated name and its real counterpart look like two unrelated functions in a naive diff)
   until corrected for. Fixed by removing the truncation.
2. **[#1183](https://github.com/squid-protocol/gitgalaxy/issues/1183) (CLOSED) — mid-file
   language "gravity" false-triggers.** `_partition_segments` could be misled by a Python
   string/regex literal that merely *contained* embedded-language delimiter text as data
   (confirmed case: a dict literal in `test_prism.py` describing a `"<script>"` trigger pattern,
   itself test data for the embedded-language detector) into permanently misrouting the rest of
   the file to a different language's rules. Root cause: `detector.py`'s own copy of
   `HANDSHAKE_REGISTRY` had drifted out of sync with the canonical, properly-anchored version in
   `language_standards.py`. Fixed by deriving it from the canonical source instead of
   hand-duplicating it.
3. **[#1184](https://github.com/squid-protocol/gitgalaxy/issues/1184) (fixed, PR
   [#1192](https://github.com/squid-protocol/gitgalaxy/pull/1192) pending merge) — scope-loss
   "dead zones."** Contiguous ranges of real, ordinary functions (`__init__`, `main`, `cleanup`)
   went missing in real production files (`prism.py`, `guidestar_lens.py`, `galaxyscope.py`) with
   no language-drift trigger present. Root cause: `_build_indentation_safe_stream` (and the
   equivalent Mode D/E shields) stripped comments in a separate pass *after* string-shielding, so
   an English contraction apostrophe inside a `#` comment (`don't`, `it's`) was indistinguishable
   from a real string-open quote — it would pair with whatever `'` came next anywhere later in the
   file and blank out everything in between. Confirmed fully fixed **in isolation**: direct
   `_slice_by_indentation()` calls now hit 100% recall on this exact corpus (row 2 of the table
   above) — but this is *not* what the real pipeline number reflects, see #1193.
4. **[#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193) (OPEN) — `line_exclusive`
   comment delimiters shared across languages that don't use them.** `prism.py`'s
   `_strip_single_line_comments` drives its delimiter list from the `line_exclusive` *family*
   config as a whole (`# <# #> =begin =end ; dnl %`), applied identically to all 20 languages in
   that family. `;` is only real for `assembly`/`agc_assembly`; `%` only for `matlab`. For the
   other 18 — Python included — a bare `;` or `%` anywhere in the source is misread as a comment
   start, silently truncating the rest of that line from `code_stream`. There's also zero
   string-shielding in that stripper, so `;`/`%` **inside a string literal** (e.g. a SQL query
   string, or `detector.py`'s own `r";"` terminator pattern) triggers the same false truncation.
   This is why the real-pipeline recall row above (~60%) is still far below the isolated-slicing
   row (100%) even with #1184 fixed — #1193 corrupts `code_stream` *before* `_slice_by_indentation`
   ever sees it, and the resulting odd/unbalanced quote count can cascade into further loss
   downstream, the same cascading mechanism #1184 fixed, just triggered upstream in `prism.py`
   instead of in `detector.py`. Not yet fixed; root cause is understood and a fix direction is
   proposed in the issue, but implementing and verifying it is separate follow-on work.

**Net effect of this round:** #1182 and #1183 are fully resolved (verified via the real pipeline).
#1184 is fully resolved *at the layer it touches* — `_slice_by_indentation` itself is now
provably 100% correct on this corpus — but #1193 sits upstream of it in the real pipeline and
wasn't discovered until *after* #1184 shipped, which is why real-pipeline recall barely moved
between the two measurement rounds despite #1184 being a genuine, verified fix. This is worth
internalizing for future rounds: a component being provably correct in isolation does not mean
the pipeline that feeds it is — measure the real pipeline, not just the component you just fixed.

**Scaling this beyond Python:** `ast` is stdlib-only, so this exact technique is Python-specific.
For other languages, `tree-sitter-language-pack` (verified on PyPI, ships pre-compiled grammars
for 371 languages, no per-language compiler toolchain required) is the most promising path to
the same style of ground-truth diff across most of GitGalaxy's other 45 signature-bearing
languages. Genuinely no practical AST ground truth exists for the legacy/esoteric languages
(COBOL, JCL, Fortran, Assembly, ABAP, MATLAB, LiveCode, Apex) — the same reason GitGalaxy exists
for them in the first place.

## 10. Tri-comparison findings (GitGalaxy vs. tree-sitter vs. ctags)

Section 9 above measures GitGalaxy against one privileged ground truth (`ast`). This section is
different: it's a 3-way comparison where *no* tool is privileged (`tests/tools/
tri_comparison_gatherer.py`/`tri_comparison_reconcile.py`), logged per-discrepancy-shape in
`docs/self_scan/tri_comparison_ledger.json` and worked through via the
`tri-comparison-ledger-sweep` skill. As of 2026-08-20, **every currently-reproducing python shape
is `status: "validated"`** (4 shapes, all investigated directly rather than dispatched — the
corpus evidence was conclusive enough on first read that a Gemini dispatch wasn't needed for any
of them).

**Summary:** 4 shapes investigated, covering ~172 raw occurrences at time of investigation. Two
confirmed real, fixed engine/tooling defects; two confirmed non-defects (one GitGalaxy correct/
tree-sitter structurally can't, one GitGalaxy+tree-sitter correct/verification-tooling bug, not a
ctags defect). All four traced to just two files: `cython/MemoryView.pyx`/`.pxd` (Cython, deliberately
routed under the `python` extension set) and `numpy/crackfortran.py`.

**Where GitGalaxy had a real, fixed gap:**
- **[#1999](https://github.com/squid-protocol/gitgalaxy/issues/1999) — Cython `cdef`/`cpdef`
  module-level functions were invisible to `func_start`.** `.pyx`/`.pxd`/`.pxi` are deliberately
  routed under `python`'s extension set for comprehensive Cython coverage, but `func_start` only
  ever matched the literal `def` keyword — Cython's `cdef int _allocate_buffer(array self) except
  -1:` style function definitions have no `def` at all. 68 real functions across
  `cython/MemoryView.pyx` (52) and `.pxd` (16) were a complete recall gap, ctags-corroborated, 0
  found by GitGalaxy. Fixed with a second `func_start` alternative matching `cdef`/`cpdef`
  signatures (excluding `cdef class`/`struct`/`enum`/`union`/`extern`/`packed`/`fused`, which are
  declarations, not functions). One narrow residual gap remains, documented not fixed:
  `get_slice_from_memview`'s return type uses a Cython/Tempita code-generation template
  placeholder (`cdef {{memviewslice_name}} *get_slice_from_memview(...)`), not standard Cython
  syntax — 1 occurrence, a codegen-template artifact rather than real end-user Cython source.

**Where the comparison tooling itself had a bug (not GitGalaxy, not ctags):**
- **[#2000](https://github.com/squid-protocol/gitgalaxy/issues/2000) — `tri_comparison_gatherer.py`'s
  ctags args counter miscounted a comma inside a quoted string-literal default value.**
  `markoutercomma(line, comma=','):` in `numpy/crackfortran.py` has 2 real parameters; GitGalaxy
  and tree-sitter both already correctly reported 2, and ctags' own raw `signature:` text was also
  correct verbatim — only this repo's own verification tooling mis-split it into 3 by treating the
  literal comma inside `','` as a second top-level separator. Fixed with bounded quote-tracking
  (unbounded for `"`, a short 3-character lookahead for `'` specifically because Rust's lifetime
  syntax — `&'a str`, `Context<'_>` — is also a bare apostrophe but with *no* closing quote at all;
  a first attempt at unbounded/generous single-quote tracking silently regressed a real,
  previously-clean rust shape by treating two unrelated lifetimes many characters apart as one
  giant fake string, swallowing a real comma between them — caught by re-running the full
  reconciliation across every language after the fix, not just python, before trusting it).

**Where GitGalaxy wins outright, tree-sitter structurally can't (already documented in
`docs/why_gitgalaxy_beats_ast_here.md`, Claim 2):**
- tree-sitter-python has no concept of Cython's `cdef class` syntax at all — it fails to recognize
  the `cdef class` declaration as a class (0/4 real classes found in `MemoryView.pyx`:  `array`,
  `Enum`, `memoryview`, `_memoryviewslice`), and separately loses track of scope at each `cdef
  class` boundary, undercounting real `def`-based methods inside them (`__cinit__`, `__dealloc__`,
  `__getbuffer__`, etc. — 0 found vs. GitGalaxy+ctags' full recall). Both are the identical root
  cause (the grammar has no concept of the dialect at all) at two different syntactic levels — no
  GitGalaxy fix applicable, this is tree-sitter-python's own structural limitation.

**A schema-asymmetry gotcha surfaced along the way, not a defect:** GitGalaxy's own `class_data`
table has no `start_line` column (`tri_comparison_gatherer.py`'s own module docstring already
documents this), so class-name matching against GitGalaxy is name-only, never line-disambiguated.
This is why a ledger example can show a `None` "reading" for GitGalaxy on a class shape even when
GitGalaxy correctly found that class by name — the `None` is the (structurally absent) line
number field, not a miss indicator. Worth knowing before treating a `None` reading as evidence of
anything on its own.

Full record: `docs/self_scan/tri_comparison_ledger.json` (filter keys starting `python/`) and
`docs/self_scan/tri_comparison_points_of_interest.md`.
