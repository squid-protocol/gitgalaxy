---
description: "The counterpart to [`why_gitgalaxy_beats_ast_here.md`](why_gitgalaxy_beats_ast_here.md). That doc"
---
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
CI pin at the time; `tests/crucible_pins.toml` has the current one), all seven CPython C files
record `Manual Memory Allocation = 0` in the golden master (then `tests/golden_master_audit.json`,
now the `tests/golden_master_audit/` directory). Between them they make **45** calls through CPython's own
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

### What is detected now, and what is planned

Wrapper *detection* is epic gitgalaxy#3313. Step 3 records wrappers in the master DB's
`wrapper_data` table, inside the scope steps 1-2 measured: short branchless print/abort wrappers in
every by-name language, and allocator wrappers (functions, `#define` aliases and chains of both) in
C/C++/Objective-C. Step 4 reports a derived count beside the literal one, never inside it:
`wrapped_debug_prints`, `wrapped_panics_and_aborts` and `wrapped_memory_alloc` on `file_data` and
`repo_data` ([`wrapper_aware_count_contract.md`](wrapper_aware_count_contract.md)). The design keeps
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

Even with the detection pass, these stay blind and belong on this page:
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

## Blind spot 2: lines of 250+ characters, in the security lens (gitgalaxy#8429)

**Affects:** every security-lens regex (hard-coded secrets, eval/exec, safety bypasses, unusual imports, environment
mutation, raw database calls and the rest of `SecurityLens.scan_content`) and the high-entropy string check.
Vault Sentinel is the one caller that is not affected.

### Plain-language version

Before any security regex runs, `SecurityLens._armor` (`gitgalaxy/security/security_lens.py`) empties every line of
250 or more characters. The line is kept as an empty line so later line numbers stay right, but its text is gone. This
is a ReDoS guard: it bounds how much text any one regex sees. The cost is that whatever sits on a long line is never
looked at: a secret in a one-line JSON or YAML config, an `eval` buried in minified JavaScript, a base64 payload in a
long string literal. The entropy check reads the same emptied text, so a string literal longer than about 248
characters is never entropy-checked at all, which is the opposite of what a "payload hidden in a huge string" check
needs.

### The evidence

Probed on `SecurityLens.scan_content` directly (2026-11-13, engine at main):

| input | longest line | counts |
|---|---:|---|
| `aws_access_key_id = "AKIA..."` alone | 42 | `hardcoded_secrets: 1` |
| the same key inside a one-line dict padded to 290 characters | 290 | nothing |
| a 96-character high-entropy string literal | 102 | `entropy: 1` |
| the same text repeated to a 288-character literal | 294 | nothing |

### Why the engine cannot see it

- **The cut is unconditional.** `_armor` blanks the whole line; there is no chunking or windowing in
  `scan_content`. The code-stream haystack goes through the same `_armor`.
- **The minified fallback is narrow.** When armoring removes more than 90% of a file, `scan_content` runs a literal
  search on the raw text for nine strings (`eval(`, `setTimeout(`, `child_process`, `shell_exec(`, `XMLHttpRequest`,
  `fetch(`, `http.request`, `NODE_TLS_REJECT_UNAUTHORIZED`, `disable_functions`). It has no secret, entropy or import
  patterns, and it does not run at all on a file where long lines are under 90% of the text (one long line in an
  ordinary file).
- **Only Vault Sentinel chunks long lines.** `gitgalaxy/security/long_lines.py` (`chunk_long_lines`) splits long lines
  into scannable pieces, and only `gitgalaxy/tools/supply_chain_security/vault_sentinel.py` calls it. The main scan
  does not.

### What this means when reading output

- **Zero security hits on minified bundles, base64 blobs, lockfile-style one-line JSON or generated configs means
  "not examined", not "clean".**
- **A file whose findings are all `[Minified Literal Hit]` was scanned only by the nine-literal fallback.**
- For secrets in such files, run Vault Sentinel or a dedicated secret scanner.

### What is planned

Tracked as gitgalaxy#8429 (under the security-claims epic gitgalaxy#8427). Nothing is merged yet.
