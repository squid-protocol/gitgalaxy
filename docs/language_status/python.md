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
| Real-world function recall vs. `ast` ground truth | ~63% (clean files) / ~27% (files hitting #1183) — see §9 |
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

**Methodology:** regenerated a fresh self-scan of GitGalaxy's own repo
(`python tests/tools/self_scan.py`, full precision, pinned to the exact commit scanned), giving
228 Python files / 2,436 real functions / 61 real classes per `ast.parse()`. For each file,
diffed `ast.walk()`'s `FunctionDef`/`AsyncFunctionDef`/`ClassDef` names (and each function's real
parameter count) against `function_data`/`class_data` rows for that file. Cross-checked the
`branch` keyword rule separately using Python's `tokenize` module as an independent ground truth,
and by running the compiled `branch` regex directly against `prism`-shielded `code_stream`
(bypassing the DB entirely) to isolate the rule's own accuracy from downstream aggregation.

| Signal | Result | Read as |
|---|---|---|
| Class extraction (`class_start`) | **100% recall** (61/61) | Fully reliable on this corpus |
| Function extraction (`func_start`), no confounding bug | **~63% recall** | See #1184 below |
| Function extraction, mid-file language drift triggered | **~27% recall** | See #1183 below |
| Function-name precision (corrected) | **~99.7%** | Engine essentially never invents a function |
| Args-count exact match (for functions that *were* found) | **~46%** | Likely shares #1184's root cause, not separately isolated |
| `branch` keyword rule, run directly against shielded code | **~110%** of a `tokenize`-based ground truth (catches everything, plus a few edge-case extras) | Simple keyword-alternation rules are far more reliable than boundary/entity extraction |

**Three real, filed defects explain the gap** — this is not a vague "heuristics are imprecise"
hand-wave, each has a concrete reproduction:

1. **[#1182](https://github.com/squid-protocol/gitgalaxy/issues/1182) — 40-character name
   truncation.** `detector.py`'s `_calculate_block_metrics` does `"name": name[:40]`. 984 of this
   corpus's 2,436 functions (40%) have real names over 40 chars — this codebase's own long
   descriptive test-naming convention routinely exceeds it. This is a naming-fidelity bug, not a
   recall bug: it was initially mistaken for hallucinated/phantom functions during this audit
   (a truncated name and its real counterpart look like two unrelated functions in a naive diff)
   until corrected for — worth noting so the same false alarm isn't re-raised. Once corrected,
   precision is genuinely ~99.7%.
2. **[#1183](https://github.com/squid-protocol/gitgalaxy/issues/1183) — mid-file language
   "gravity" false-triggers.** `_partition_segments` can be misled by a Python string/regex
   literal that merely *contains* embedded-language delimiter text as data (confirmed case: a
   dict literal in `test_prism.py` describing a `"<script>"` trigger pattern, itself test data
   for the embedded-language detector) into permanently misrouting the rest of the file to a
   different language's rules. Confirmed by direct inspection of `_partition_segments()`'s
   output segments, not inferred. Affects 11/228 files in this corpus.
3. **[#1184](https://github.com/squid-protocol/gitgalaxy/issues/1184) — scope-loss "dead
   zones."** Contiguous ranges of real, ordinary functions (`__init__`, `main`, `cleanup`) go
   missing in real production files (`prism.py`, `guidestar_lens.py`, `galaxyscope.py`) with no
   language-drift trigger present — functions immediately before and after the range are found
   correctly. This is the dominant driver of the 63% recall ceiling; root cause not yet isolated
   (filed as a confirmed, reproducible pattern, not a diagnosed fix).

**Rough estimate once fixed:** #1182 doesn't move recall (cosmetic only). #1183 affects too few
files (~5%) to move the needle much on its own (~59% → ~63% corpus-wide). #1184 is the real
lever — since class extraction resolves an analogous scope-boundary problem at 100% on this same
corpus (via separately-fixed logic, #1040), and the isolated unit-test suite already proves
`func_start`'s regex is correct in principle, function recall landing in the **high-80s to
high-90s%** range once #1184 is fixed is a defensible estimate — not a promise, and not
re-measured until the fix actually lands.

**Scaling this beyond Python:** `ast` is stdlib-only, so this exact technique is Python-specific.
For other languages, `tree-sitter-language-pack` (verified on PyPI, ships pre-compiled grammars
for 371 languages, no per-language compiler toolchain required) is the most promising path to
the same style of ground-truth diff across most of GitGalaxy's other 45 signature-bearing
languages. Genuinely no practical AST ground truth exists for the legacy/esoteric languages
(COBOL, JCL, Fortran, Assembly, ABAP, MATLAB, LiveCode, Apex) — the same reason GitGalaxy exists
for them in the first place.
