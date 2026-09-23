# Known Blind Spots — Where GitGalaxy's Signal Goes Quiet

The counterpart to [`why_gitgalaxy_beats_ast_here.md`](why_gitgalaxy_beats_ast_here.md). That doc
tracks the measured cases where GitGalaxy's regex signal is *more* useful than a plain AST read.
This one tracks the measured cases where it is structurally **blind**: the engine reports a low or
zero value, and the code is not actually low or zero.

Each entry is narrow and evidence-backed, with the reason the engine cannot see it and what (if
anything) is planned. An entry here is an accepted, documented limitation, not an open bug. Its
purpose is that the next session to meet the same evidence reads it here instead of rediscovering
it from scratch.

## Blind spot 1: project-local idiom wrappers (gitgalaxy#3003)

**Affects:** every literal-vocabulary rule, meaning a rule that matches a fixed set of primitive
names. Evidenced on `memory_alloc` (C: `malloc|calloc|realloc|free|aligned_alloc|mmap|alloca`) and
`auth_middleware` (`def_auth`). The same shape applies to any rule built the same way, such as
`telemetry`, `debug_prints` or the io/ipc vocabularies.

### Plain-language version

A literal rule counts calls to the primitive by name. A mature project often stops calling the
primitive directly. It wraps it in its own helper and calls the helper everywhere:

```c
/* lib/curlx/...: defined once */
void *curlx_malloc(size_t n) { return malloc(n); }

/* everywhere else: hundreds of call sites */
buf = curlx_malloc(len);
```

`memory_alloc` sees the one `malloc(` inside the wrapper and none of the hundreds of
`curlx_malloc(` call sites. The allocation surface did not shrink. It moved behind a name the rule
has never heard of.

### The evidence

**curl, `memory_alloc`: an 86% drop in one release.** `temporal-crucible`'s walk panel
(2026-09-13, cited on gitgalaxy#2990 and #3003) shows curl's summed `state_memory_alloc` falling
from **1197 to 171 between 8.17 and 8.18**, while LOC grew and every other signal stayed
continuous. 8.18 is the `curlx` allocator-wrapping refactor. A reader of the time series would
conclude curl stopped managing memory; in fact it renamed how it does so.

**curl, `def_auth`: 0 across 1.05M C rows.** curl delegates crypto and authentication to backend
libraries (OpenSSL, Schannel, GnuTLS, ...) instead of calling OpenSSL-shaped primitives itself, so
the auth vocabulary never appears in its own source. This is the same failure class one step
further: the idiom is not wrapped in-repo but behind a library boundary.

**CPython, `memory_alloc`: reproduced in the pinned corpus.** In language-crucible v1.4.0 (the
CI pin), all seven CPython C files record `Manual Memory Allocation = 0` in
`tests/golden_master_audit.json`. Between them they make **45** calls through CPython's own
allocator API (`PyMem_Malloc`/`PyMem_Free`/`PyMem_Realloc`/`PyObject_Malloc`/..., which wraps the C
allocator in `Objects/obmalloc.c`). By file: typeobject.c 15, ceval.c 8, compile.c 6,
frameobject.c 6, dictobject.c 5, object.c 4, gc.c 1. The wrapper definitions are not in the
corpus sample, so the rule has nothing to match at all.

**COBOL: checked, currently mild.** `docs/cobol_semantic_coverage.md` (#2990) looked for the
COBOL analogue, an `EXEC CICS` block hosted in a copybook rather than a program. It found zero of
the corpus's 591 COBOL files do this, and carddemo's `CSUTLDTC` date wrapper is a `CALL` site that
is still counted. That is a fact about this corpus's content, not immunity.

### Why the engine cannot see it

- **The rule is a vocabulary, by design.** A structural signal counts syntax, which is what keeps it
  comparable across every language without a per-language toolchain. A per-project vocabulary would
  make `memory_alloc` mean different things in different repositories.
- **A same-file heuristic would find nothing.** In every instance above, the wrapper is defined in
  one file and called from others (curl's `curlx` module; CPython's `obmalloc.c`, not even in the
  sample). The engine's per-file extraction never sees a definition and its call sites together.
- **There is no data flow.** A regex engine cannot follow a value through a function. So it cannot
  tell that `curlx_malloc`'s return value *is* a `malloc` without seeing the wrapper's body, and it
  can never see through a library boundary (the `def_auth` case).

### What this means when reading output

- **A literal signal reads as "calls to the primitive by that name, in this code".** It does not
  read as "how much of this behaviour the code has".
- **A sharp drop in one release while LOC grows is a refactor signature, not a behaviour change.**
  This is especially true when other signals stay continuous. Check for a new helper layer before
  concluding anything.
- **A near-zero on a mature project in a domain that obviously needs the behaviour** (a C network
  library with 0 `memory_alloc`, an HTTP client with 0 `def_auth`) is more likely a wrapper or a
  delegation than an absence.

### What is planned

Wrapper *detection* is epic gitgalaxy#3313. The design keeps
the literal signal exactly as it is and records wrappers as a **fact**, not a count, the same
signal/fact split the fact channels use (`gitgalaxy/core/how_to_add_a_fact_channel.md`):

- **Repo-wide detection pass.** After every file is parsed, find thin wrappers of two kinds:
  - short functions whose body hits a rule;
  - function-like `#define` aliases in C-preprocessor languages, such as curl's
    `#define curlx_malloc(size) malloc(size)`.

  A bounded closure links the two (a function calling an alias, an alias calling a function).
  Record `wrapper → kind → primitive → rule` in the master DB.
- **A separate wrapper-aware count reported beside the literal one.** For example, `memory_alloc`
  171 plus N calls through K detected wrappers. The literal signal stays syntactic and comparable;
  the derived figure explains a refactor like curl 8.18 instead of hiding it.

An opt-in, per-project wrapper list was considered and rejected. Almost nobody would fill it in,
it goes stale as code changes, and it makes two scans of the same code disagree depending on who
configured what.

### What detection will still not see

Even with the planned pass, these stay blind and belong on this page:
- **Object-like macro redirects.** `#define malloc(size) Curl_cmalloc(size)` (curl 8.17) or
  `#define xmalloc malloc` silently re-points an existing name. The literal call is still counted,
  so the count is right, but *which* allocator runs is invisible. Function-like *aliases* under a
  new name are **not** blind: epic step 2 (#3324) measured them on curl 8.18, where the
  `curlx_*` alias layer carries 1,625 allocator call sites and literal plus aliases stays
  continuous (+4%) across the refactor that dropped the literal count 82%.
- **Function-pointer tables reached only through a pointer.** CPython's `_PyMem_RawMalloc` is
  never called by name. Its callers go through `_PyMem.malloc(ctx, size)`, which the C rule
  happens to match, so here the table's callers are still counted.
- **Thick wrappers.** A helper that allocates *and* does real work (logging, pooling, accounting)
  is not a thin pass-through, and treating it as one would over-count.
- **Library delegation.** The `def_auth` case: the primitive never appears in the repository at
  all.
