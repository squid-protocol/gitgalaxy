# Assembly (x86/ARM) — Structural Signature Coverage

Snapshot generated 2026-08-20 against `main`; §3 `func_start` note and §9 tri-comparison section
refreshed 2026-08-27 (PR #2320). Source: `LANGUAGE_DEFINITIONS["assembly"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_assembly.py` /
`test_assembly_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

This is the **generic** x86-64/ARMv8 assembly language entry — distinct from `agc_assembly`
(Apollo Guidance Computer source, its own already-documented sibling at
[`agc_assembly.md`](agc_assembly.md)). The two share the same `line_exclusive` lexical family and
a lot of surface-level vocabulary, but make genuinely different design calls in a few places (most
notably `func_start`, §3 below) — don't assume this doc is agc_assembly's doc with names swapped.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | x86-64 (NASM/GAS) & ARMv8 (AArch64) — Backwards Compatible |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `line_exclusive` — `;` (NASM/Intel) and `#` (GAS/ARM) line comments, resolved per-language rather than per-family since #1197 |
| Structural signature keys wired | 42 / 52 (10 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_assembly.py`) | 148 |
| Strict-signature tests (`test_assembly_strict.py`) | 83 |
| Total dedicated assembly test cases | 231 |

## 2. Identification surface

- **Extensions:** `.asm`, `.s`, `.S`, `.inc`, `.nasm`, `.s64`, `.masm`, `.arm`, `.a51` — the union
  of NASM/GAS/MASM's own conventions plus architecture-specific suffixes (`.arm`, `.a51`).
- **Exact filenames:** none. Inline comment: "Assembly is assembled directly to machine code; no
  extensionless exact configurations exist."
- **Discriminators:** `.asm`, `.s`, `.S`, `.c`, `.cpp`, `.ld`, `Makefile`, `CMakeLists.txt` —
  sibling extensions, linker scripts, and build files used to disambiguate ambiguous `.inc`/`.s`
  files.
- **Shebangs:** none. Inline comment: "Assembly is compiled/assembled to binary; no shebangs
  exist."

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` uses for this entry (including the file's own
final "Hybrid domain sensors" grouping). Description is what assembly's *actual* regex captures,
not the generic cross-language definition.

**Phase 1: Logic topology & structure**
| Key | What it captures for assembly |
|---|---|
| `branch` | x86 conditional/unconditional jumps and calls (`jmp je jne jz jnz ja jb jl jg jge jle jae jbe call ret loop`) plus ARM branch instructions (`b bl bx blr cbz cbnz tbz tbnz beq bne`) — deliberately excludes system exits/halts, which live under `high_risk_execution` instead. |
| `args` | ABI calling-convention register coupling: x86-64 `[er]di/[er]si/[er]dx/[er]cx`, the `r8`/`r9` family with size suffixes (`r8d/r8w/r8b`), ARM `x0-7/w0-7/v0-7/xmm0-7/r0-7`, and the legacy 8/16-bit x86 forms (`ax/al/ah`, `si/di`) — the last two groups were closed gaps found by PR #940 (see §7), added specifically because this language's own `_meta.target_version` claims "Backwards Compatible." |
| `structural_boundaries` | Data-movement and arithmetic primitives: `mov` and its `movabs/movsx/movzx/movb/movw/movl/movq/movaps/movups/movdqu` variants, `vmov*`, `lea`, `ldr`/`str` with size suffixes, `push/pop/add/sub/inc/dec/mul/imul/div/idiv/nop/ldp/stp`. Explicitly excludes linker visibility (`api`) and sections (`globals`). |
| `func_start` | **Permissive, with a data-label guard** — matches an identifier followed by `:` at line start, excluding `.L`/`.LC`-prefixed local labels, digit-leading labels, and `.text`/`.data`/`.bss` section markers, **and** (since 2026-08-27) a trailing negative lookahead that rejects a label whose colon is followed — same line, or the very next line — only by a pure data-emission / location-counter directive (`.asciz`, `.byte`, `.long`, `.org`, `.endobj`, `.incbin`, NASM `db`/`resb`/`times`, …). This last clause is the generic-assembly counterpart to `agc_assembly`'s `func_start`, which instead uses a *positive* lookahead requiring one of ~41 vetted subroutine-entry opcodes on the same line; generic assembly has no practical opcode whitelist across its NASM/GAS/MASM/legacy-real-mode dialect spread, so it inverts the test — reject the labels that are unambiguously data rather than accept only the labels that are unambiguously code. Section / visibility / type / align directives are deliberately *not* in the reject list (they legitimately sit between a real function's label and its first instruction). Still recall-biased overall; the guard only removes the clear data-table false positives (`ape.mbrpad`, ELF-note labels, `.short` matrices — see §7's 2026-08-27 entry and §9). |
| `class_start` | `struc <name>` (NASM) / `<name> STRUCT` (MASM) / `.struct <name>` (GAS-adjacent) structure-definition declarations, either name-then-keyword or keyword-then-name ordering. **This is wired here** — unlike `agc_assembly`, which has no class/struct concept at all and is hard-`None` for this key, generic x86/ARM assembler dialects do have a real structure-declaration macro convention worth capturing. |

**Phase 2: Risk & structural integrity**
| Key | What it captures for assembly |
|---|---|
| `safety` | Stack-frame and hardware-hardening guards: `enter/leave`, `endbr64` (Intel CET), `paciasp/autiasp/bti/retab` (ARM pointer authentication), `.align`/`.p2align`, or an `stp`/`ldp x29, x30` frame-pointer save/restore pair. |
| `safety_bypasses` | Indirect control transfer through a register or memory operand (`jmp`/`call` to `*`, `[...]`, an x86 register, or `r\d+`), ARM's `br xN/wN`, `cli` (disable interrupts), `msr daifclr` (ARM interrupt mask clear). |
| `high_risk_execution` | CPU halts and debug traps: `hlt`, `int 3`, `brk`, `ud2`, `sys_exit`, `sys_kill`. |
| `io` | Hardware I/O ports and syscalls: `in/out/insb/insw/insd/outsb/outsw/outsd`, `syscall`, `svc`, `int 0x80`, `sys_read`, `sys_open`. |
| `api` | Linker-visible export/import directives: `.global`/`.globl`/`global`/`EXPORT`/`PUBLIC`/`EXTERN`/`IMPORT` at line start. |
| `state_mutation` | Explicit register/memory swaps and atomic increments: `xchg`, `cmpxchg`, `inc`, `dec`. |
| `dead_code` | Commented-out instruction lines — `;`/`#`/`//` followed by `jmp/call/mov/push/pop/cmp/add/sub`. |
| `doc` | Structured doc-comment tags: a comment-leader line (`;#@/|`) followed by `@param/@return/@brief/@author/@note`. |
| `test` | Generic test-framework vocabulary (`describe/expect/assert/TestCase`, `it(...)`) — not assembly-native, but present when assembly is mixed with a test harness in a polyglot repo. |

**Phase 3: Architecture & domain sensors**
| Key | What it captures for assembly |
|---|---|
| `concurrency` | `lock` prefix, `xadd`, memory fences (`mfence/lfence/sfence`), ARM barriers (`dmb/dsb/isb`), and exclusive load/store (`ldxr/stxr/ldaxr/stlxr`). |
| `globals` | Section declarations: `.data/.bss/.rodata/.comm`, `section .data`, `section .bss`. |
| `comprehensions` | Instruction-repetition constructs: `%rep`/`.rept`/`.irp` block directives, and string-operation repeat prefixes (`rep/repe/repne/repz/repnz`) — assembly's nearest analog to an iterator/comprehension. |
| `scientific` | FPU/SSE/AVX/NEON math instructions: `fadd/fsub/fmul/fdiv/fsqrt`, `vadd[ps][sd]/vsub[ps][sd]/vmul[ps][sd]`, ARM `fmla/fmov`. |
| `reflection_metaprogramming` | Complex SIB (scale-index-base) memory addressing: `[base + index * scale]`. |
| `import` | Inclusion directives: `%include/.include/.incbin/INCLUDE/INCLUDELIB`. |
| `_dependency_capture` | Extracts the included filename (quoted or bare) from the same `%include`/`.include`/`.incbin`/`INCLUDE`/`INCLUDELIB` directives, feeding the dependency DAG. |
| `ownership` | Header authorship metadata: comment-leader line followed by `Author:/Created by:/Maintainer:/Copyright:`. |

**Phase 4: Specialized subsystems**
| Key | What it captures for assembly |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers, same as every other language. |
| `spec_exposure` | `[SPEC-nnn]`/`[spec]`/`[audit]`/`[rfc]` bracketed traceability tags. Bounded (`\d{1,10}`, `[^\]]{0,300}`) since PR #798 (§7) — assembly was one of 17 languages sharing the same unbounded-adjacent-quantifier ReDoS shape. |
| `events` | Interrupt vectors and exception returns: `int 0xNN`, `iret[qd]`, `reti`, `svc`, `hvc`, `smc`, plus line-start labels named `vector_*`/`handler_*`/`isr_*`. |
| `macros` | Preprocessor/macro directives: `%macro/.macro/%endmacro/.endm/%define/.equ/.set/#define`. |
| `pointers` | Explicit-size memory dereferencing: `byte/word/dword/qword ptr [...]`, and bracket dereference generally. |
| `memory_alloc` | Calls into `malloc`/`calloc` (`call`/`bl` with optional leading underscore), plus `sys_mmap`/`sys_brk`. |

**Phase 5: Resource management & stability**
| Key | What it captures for assembly |
|---|---|
| `telemetry` | Calls to structured-logging libc functions: `log_info/log_error/log_warn/log_debug/syslog`. |
| `debug_prints` | Calls to `printf`/`puts`/`sys_write`. |
| `explicit_casts` | The `byte/word/dword/qword ptr` size-cast prefix — assembly's nearest analog to an explicit type cast. |
| `panics_and_aborts` | Fatal/trap instructions: `hlt/ud2/brk/svc/int 3`. |
| `thread_sleeps` | Blocking/pause instructions: `pause/hlt/wfi/wfe`. |
| `bitwise_ops` | Bitwise and shift/rotate instructions: `and/or/xor/not/shl/shr/sal/sar/rol/ror/lsl/lsr/asr`. |
| `sync_locks` | Hardware synchronization primitives: `lock/xchg/cmpxchg/stxr/ldxr/dmb/dsb/isb`. |
| `immutability_locks` | `equ` constant definitions and `.rodata`/`.rdata` read-only sections. |
| `cleanup` | Calls to `free` (`call`/`bl`, optional leading underscore). |
| `encapsulation` | `.local`/`.private` visibility directives at line start. |

**Hybrid domain sensors** (added by PR #745, §7 — replacing four leftover Lua signatures that could never match real assembly source):
| Key | What it captures for assembly |
|---|---|
| `regex_execution` | Calls into the POSIX libc regex API: `regcomp/regexec/regfree/re_search/re_match`. |
| `time_date_logic` | `rdtsc`/`rdtscp` (native timestamp-counter instructions) plus calls to `time/clock/clock_gettime/gettimeofday`. |
| `ipc_rpc_bridges` | Raw process/IPC syscalls and their libc wrappers: `fork/execve/pipe/socket/clone`, `sys_fork/sys_execve/sys_pipe/sys_clone`. Distinct from `io`'s generic `sys_read`/`sys_open`/`syscall` tokens. |

## 4. What GitGalaxy explicitly does not track

Ten keys are hard-set to `None` in assembly's `rules` dict:

- **`ui_framework`** — no inline comment. No built-in display/UI protocol exists in generic x86/ARM
  assembly the way `agc_assembly` has DSKY vocabulary wired for this key; a generic assembly file
  has no equivalent universal convention.
- **`closures`** — no inline comment. No first-class function values or anonymous
  function/lambda syntax exists at the assembly level.
- **`decorators`** — no inline comment. No decorator/annotation syntax exists in assembly source.
- **`generics`** — no inline comment. No generic/parametric type system exists at the assembly
  level.
- **`ssr_boundaries`** — no inline comment. No server-side-rendering boundary concept applies to
  hardware-level instruction source.
- **`dependency_injection`** — no inline comment. No DI framework or container concept exists in
  assembly.
- **`inline_asm`** — inline comment: "This is base assembly." Self-evidently out of scope: this key
  exists to flag inline assembly *embedded inside a higher-level language*; this language's source
  **is** the assembly, so "inline asm within it" doesn't apply.
- **`listeners`** — inline comment: "Assembly relies on hardware interrupts rather than high-level
  listener subscriptions." No listener/observer registration convention exists.
- **`test_skip`** — no assembly-specific inline comment (only the generic numbered-schema
  description above it). No formal test-framework skip/ignore annotation convention exists for
  assembly source.
- **`serialization_parsing`** — inline comment (added by PR #745, §7): "Assembly has no native or
  universal JSON/XML/YAML parsing construct -- unlike malloc/free/printf there is no single
  ubiquitous libc convention for this, so per Strict Feature Parity (Rule 4) this stays `None`
  rather than forcing a fit." This key previously held a leftover, never-matching Lua signature
  before PR #745 corrected it.

**`class_start` is *not* in this list** — see §3's Phase 1 table. This is the one meaningful
divergence from `agc_assembly`'s `None` framing for the same key: generic assembly dialects have a
real `struc`/`STRUCT`/`.struct` structure-declaration convention worth capturing, where AGC source
has no object/structure concept at all.

## 5. Known limitations (accepted, not fixed)

None. Grepping both `tests/extraction/languages/test_assembly.py` and
`test_assembly_strict.py` for `known_limitation`-named tests returns nothing — there are no
deliberately-not-fixed gaps documented in the test suite for this language at this time. (The
shared `_slice_by_labels` truncation/discard bug that used to be noted here as *filed but unfixed*
— issue #1949 — is now **closed**. One filed, still-open, cross-language item remains: #1954,
`prism.py`'s Form Feed / Vertical Tab line-splitting bug; see §7.)

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 148 tests in
  `tests/extraction/languages/test_assembly.py` — valid/invalid/pathological cases per rule. Fully
  migrated to the per-language file (epic #813, issue #856, PR #936); nothing left in the old
  monolithic gauntlet files for assembly.
- **Strict signature suite** (all other wired keys): 83 tests in
  `tests/extraction/languages/test_assembly_strict.py` — positive match, negative/false-positive
  match, cross-rule ambiguity, and ReDoS-immunity checks per signature. Originally added at 58
  tests by epic #518 (issue #574, PR #745) directly in the since-retired monolithic
  `test_language_standards_strict.py`, split out to this per-language file by issue #1057/PR
  merged via #1059, then deepened further to its current 83 by issue #1074's cross-language batch
  pass (PR #1087, see §7).

## 7. Relevant closed work

**Dedicated assembly hardening:**
- [#856](https://github.com/squid-protocol/gitgalaxy/issues/856) → PR
  [#936](https://github.com/squid-protocol/gitgalaxy/pull/936) — extraction hardening (epic #813):
  created `test_assembly.py` with 128 cases. `func_start` expanded to support MASM-style labels
  with `?`/`@`/`.` prefixes (which also unblocked a negative-lookahead exclusion that had been
  neutralized); `args` gained ARM32 `r0`-`r7` support; `class_start` refactored to properly capture
  MASM's `<name> STRUCT` alongside NASM's `struc <name>`; `_dependency_capture` gained
  `INCLUDE`/`INCLUDELIB` support and was made case-insensitive. Logged a new recurring bug class
  (Class 44: Neutralized negative lookaheads) in the extraction-hardening epic doc.
- PR [#940](https://github.com/squid-protocol/gitgalaxy/pull/940) — "Fix #856 follow-up: assembly
  args phantom register vs real r8/r9 suffix forms." An independent review of the already-merged
  #936 found one real bug: `args`' `[er][89]` matched the *fictional* registers `e8`/`e9` while
  failing to match the real `r8d/r9d/r8w/r9w/r8b/r9b` sub-register forms (the trailing `\b` never
  fires between two word characters). Also closed a genuine coverage gap: `args` had zero support
  for the legacy 8/16-bit x86 register set (`al/ah/ax`, etc.) despite `_meta.target_version`
  explicitly claiming "Backwards Compatible" — real 16-bit real-mode bootloader code (the corpus's
  `bootos`) uses exactly this convention for argument coupling. `func_start`, `class_start`, and
  `_dependency_capture` were independently re-audited and found clean. Verified against the real
  corpus through the actual `Prism.split_streams` pipeline (not raw text, which inflated a naive
  first pass to a misleading +391%): 84→305 real `args` matches (+263%), concentrated in the
  16-bit bootloader file the fix targets.
- [#574](https://github.com/squid-protocol/gitgalaxy/issues/574) → PR
  [#745](https://github.com/squid-protocol/gitgalaxy/pull/745) — strict parsing tests (epic #518):
  58 tests added (later deepened, see §6). Found and fixed 3 real bugs: (1) `func_start`'s
  lookahead `\s*` could cross a newline and falsely bind a bare label followed by blank lines to a
  stray colon several lines later — same bug class as `agc_assembly`'s #572/#743 — bounded to
  `[ \t]*` (same physical line only); (2) `encapsulation`'s leading `\b` sat directly before a
  literal `.`, which can never fire since `.local`/`.private` are always preceded by whitespace or
  line-start (both non-word) — fixed by anchoring to line-start instead; (3)
  `serialization_parsing`/`regex_execution`/`time_date_logic`/`ipc_rpc_bridges` were all leftover
  **Lua** signatures (`string.match`, `os.execute`, `cjson.decode`, etc. — the section was even
  labeled `"(Lua Specifics)"`), copy-pasted and never adapted, so none could ever match real
  assembly source. `serialization_parsing` is now explicit `None` (§4); the other three were
  rewired to real native/libc equivalents (POSIX regex, `rdtsc`/`clock_gettime`,
  `fork`/`execve`/`pipe`/`socket`).
- PR [#1955](https://github.com/squid-protocol/gitgalaxy/pull/1955) — "fix(assembly): real
  per-function args count, validate tri-comparison ledger." Same generic single-`.search()`-then-
  split derivation bug as `agc_assembly`'s (#1949-adjacent fix, PR #1952): `args`' regex has
  exactly one capturing group, so every function's per-function args count was capped at a bare
  0/1 regardless of how many calling-convention registers it actually referenced. Added
  `_count_assembly_register_args` (mirroring `_count_agc_register_args`'s pattern), which counts
  *distinct* argument-passing registers referenced anywhere in the body via `.findall`,
  canonicalizing different-width references to the same physical register (`edi`/`rdi`, `w3`/`x3`,
  `al`/`ah`/`ax`) to one slot. Also validated both function-existence tri-comparison ledger shapes
  for assembly against the real corpus and ctags: a NASM/GAS dot-prefix local-label naming split
  (cosmetic, not a real gap), a genuine ctags limitation on purely-numeric local labels, the
  #1949 `detector.py` bug (below) independently reconfirmed live in assembly too, a
  correct-by-design GitGalaxy exclusion for GCC's `.L`-prefix convention, and a genuine GitGalaxy
  precision gap — generic assembly's `func_start` had no following-instruction requirement, unlike
  `agc_assembly`'s, so it also matched pure data/constant labels. At the time this left ctags ahead
  on the Func Precision panel (92.6% vs. GitGalaxy's 85%). **Superseded by PR #2320 below**, which
  fixed that precision gap and the reconciler name-matching artifact and took GitGalaxy to 100% —
  see §9 for the current picture.

- PR **#2320** (2026-08-27) — "fix(assembly): data-label `func_start` false positives + tri-comparison
  reconciler dot-normalization." Two coordinated fixes plus a ledger re-validation, driven by the
  `tri-comparison-ledger-sweep` skill against assembly's remaining Func Precision gap (95/102):
  (1) **engine** — `func_start` gained a bounded trailing negative lookahead (§3) that rejects a
  label followed only by a pure data / location-counter directive; this removed the confirmed
  `ape.mbrpad` false positive and, run against the full corpus, ~30 more genuine data-table labels
  wrongly counted as functions in `cosmopolitan/ape.S` (61→39 raw `func_start` signals),
  `start.S`, and `hellosilicon/matrixmultneon.s`. (2) **tri-comparison tooling** —
  `tri_comparison_reconcile.py` now normalizes a single leading `.` on NASM/GAS local labels
  before cross-tool pairing, so GitGalaxy's `.loop` pairs with ctags' `loop` (same label, same
  line) instead of showing as a two-sided phantom disagreement. Both `function/existence` ledger
  shapes re-validated: the GitGalaxy-solo shape dropped 7→2 (`.1`/`.2`, real numeric local code
  labels ctags structurally can't tag) and earned `credit_tools: ["gitgalaxy"]`, taking
  GitGalaxy's assembly Func Precision to a clean **100%**. Golden masters re-blessed (assembly
  corpus files + one global tech-debt average).

**Open, unresolved (found along the way, not yet fixed for assembly):**
- [#1949](https://github.com/squid-protocol/gitgalaxy/issues/1949) (**CLOSED**) — "`detector.py`
  `_slice_by_labels`: `assembly_returns` truncates real bodies, single-line blocks silently
  discarded (assembly/cobol/fortran/abap/agc_assembly)." Two independent bugs in the shared
  label-based function-slicing path; confirmed to have affected assembly directly (`pc:` at
  `cosmopolitan/ape.S:251` truncated by a `// @return` doc-comment; single-instruction trampoline
  labels silently discarded). Fixed and closed since the 2026-08-20 snapshot — kept here for the
  history, no longer an open gap.
- [#1954](https://github.com/squid-protocol/gitgalaxy/issues/1954) (OPEN) — `prism.py`'s
  `_strip_single_line_comments` uses `str.splitlines()`, which splits on Form Feed/Vertical
  Tab/other Unicode line-boundary characters beyond `\n`/`\r\n`. Found during the same
  investigation as PR #1955 via a real, growing line-number drift in `cosmopolitan/ape.S`, which
  uses `\f` as a deliberate page-break idiom. Affects all 20 `line_exclusive`-family languages in
  principle (assembly included); scoped as its own separate fix.

**Cross-language work that touched assembly:**
- [#713](https://github.com/squid-protocol/gitgalaxy/issues/713) → PR
  [#798](https://github.com/squid-protocol/gitgalaxy/pull/798) — bounded `spec_exposure`'s
  ReDoS-vulnerable `[^\]]*` shape across 17 languages; assembly was one of them (the corpus's own
  Spec-Traceability-Tag hits are concentrated in `cobol`/`agc_assembly` rather than generic
  assembly, so this fix was preventative for assembly rather than closing an observed
  catastrophic-backtracking incident).
- [#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193) → PR
  [#1197](https://github.com/squid-protocol/gitgalaxy/pull/1197) — `prism.py`'s comment-delimiter
  resolution for the entire `line_exclusive` family (20 languages, assembly included) was
  previously shared across the whole family rather than resolved per-language. Assembly's own `;`
  delimiter was already correct pre-fix (unlike Perl, badly broken by the old shared list), but
  this hardened the shared comment-shielding machinery assembly's extraction depends on.
- Issue #1057 / PR merged via #1059 — infrastructure-only: split the old monolithic
  `test_language_standards_strict.py` into per-language files (creating
  `test_assembly_strict.py`), then merged `tests/core_engine/languages/` into
  `tests/extraction/languages/`. No behavior change.
- [#1074](https://github.com/squid-protocol/gitgalaxy/issues/1074) → PR
  [#1087](https://github.com/squid-protocol/gitgalaxy/pull/1087) — part of a 34-language batch
  deepening strict-signature test depth; `test_assembly_strict.py` was one of the files directly
  touched, growing from its original 58 tests to the current 83.
- [#1054](https://github.com/squid-protocol/gitgalaxy/issues/1054) → PR
  [#1063](https://github.com/squid-protocol/gitgalaxy/pull/1063) — `detector.py`'s
  `MAX_SATELLITES = 250` hard cap on function extraction removed repo-wide. Not confirmed to have
  hit any specific generic-assembly file in the corpus checked so far (only `agc_assembly`'s own
  `PINBALL_GAME_BUTTONS_AND_LIGHTS.agc` was directly confirmed), but the cap removal applies
  globally, assembly included.

Search performed via `gh issue list --search 'in:title assembly'` and `gh pr list --search
'assembly'` / `'assembly args'` (2026-08-20) — matches that were actually about `agc_assembly`
(a separate, already-documented language) or unrelated mentions were skimmed and excluded.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Four repos found in the `v2.4.7` batch of `gitgalaxy-raw-output`, chosen for a size/era/dialect
spread rather than four similar mid-size projects. Three of these match the local
`language-crucible/data/assembly/` corpus (`cosmopolitan`, `bootos`, `hellosilicon` — 15 real
`.S`/`.s`/`.asm`/support files across those three) that the §7 hardening work validated its fixes
against; the fourth (`asm`) is additional real-world evidence not in the local corpus:

- **[`HelloSilicon`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/HelloSilicon/HelloSilicon_galaxy_llm.md)**
  — a scan of [`below/HelloSilicon`](https://github.com/below/HelloSilicon), an ARMv8/AArch64
  macOS assembly tutorial. 2,399 total LOC, 57.0% assembly (45 `.s`/`.S` files, 1,983 LOC), scanned
  in 0.19s. Small, modern (AArch64/NEON), the ARM side of the target's stated dialect coverage.
- **[`asm`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/asm/asm_galaxy_llm.md)**
  — a scan of [`0xAX/asm`](https://github.com/0xAX/asm), a widely-referenced x86 assembly-language
  learning/exercise repository. 388 total LOC, 19.4% assembly (7 `.asm` files, 319 LOC), scanned in
  0.15s. Small, x86, deliberately mixed with C/build tooling — a genuinely low-dominance case for
  the language identifier.
- **[`bootOS`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/bootOS/bootOS_galaxy_llm.md)**
  — a scan of [`nanochess/bootOS`](https://github.com/nanochess/bootOS), a 512-byte x86 real-mode
  bootloader operating system. 1,060 total LOC, 62.5% assembly (5 `.asm` files, 1,046 LOC), scanned
  in 0.12s. Small, legacy 16-bit real-mode dialect — the corpus PR #940's legacy-register fix
  specifically targeted.
- **[`cosmopolitan`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/cosmopolitan/cosmopolitan_galaxy_llm.md)**
  — a scan of [`jart/cosmopolitan`](https://github.com/jart/cosmopolitan), the Actually Portable
  Executable framework. 198,259 total LOC, 41.4% assembly (2,482 files, 26,353 LOC), scanned in
  11.71s. Large and genuinely adversarial: a single build mixes GNU `as`, NASM-style, and hand-
  rolled macro-generated assembly across multiple architectures, and its `ape.S`/`ape.lds` files
  are the direct source of both open issues (#1949, #1954) found in §7 — this is the file that
  keeps finding real engine bugs, not a clean pass-through example.

**Local corpus** (not `gitgalaxy-raw-output`, but the source of the fixture files used in the
hardening/validation work cited in §7): `language-crucible/data/assembly/` holds 15 real files
across three real small assembly projects — `cosmopolitan/` (`ape.S`, `start.S`, `ape.lds`,
`notice.inc`, `BUILD.mk`, `loader.c`), `bootos/` (`os.asm`, `counter.asm`, plus `Makefile`/
`LICENSE`), and `hellosilicon/` (`matrixmultneon.s`, `mainpie.s`, `fileio.S`, plus `makefile`/
`LICENSE`).

## 9. Measured tri-comparison: GitGalaxy vs. ctags (no tree-sitter grammar)

assembly has no tree-sitter grammar, so `tree_sitter_accuracy_audit.py`'s single-ground-truth
methodology doesn't apply here. `ctags_reader.py` maps it to Universal Ctags' generic `Asm` parser
(kind `l`, labels — same parser agc_assembly shares, there is no per-dialect ctags parser either)
as the only other signal to compare against. Unlike agc_assembly, `class` DOES have real coverage
here (`struc`/`STRUCT`/`.struct`, §3/§4) — the local corpus's 15 real files simply never use this
syntax, so both tools correctly report zero and no ledger shape exists for it; not an unmeasured
gap, just a corpus that doesn't exercise the construct.

Two `function/existence` shapes exist in `docs/self_scan/tri_comparison_ledger.json`, first
investigated 2026-08-20 and **re-validated 2026-08-27** after the sweep's 95/102 Func Precision
gap was traced to three separable causes and two of them fixed (PR #2320, §7). Current state:
GitGalaxy **97/97 (100%)** on Func Precision, ctags **95/121 (78.5%)** — GitGalaxy holds the
panel badge outright.

**GitGalaxy solo-correct shape** (`agree[gitgalaxy]_vs[ctags]`, 7 → 2 occurrences).
- *Name-serialization split, never a real disagreement (4 occ, now resolved in tooling):*
  NASM/GAS local labels scoped to the preceding global label carry a leading `.` (`.load_vec:`/
  `.loop:`/`.empty:`/`.find:` in `bootos/os.asm`). GitGalaxy's `func_start` keeps the dot; ctags'
  Asm parser strips it (`load_vec`/`loop`/…). Both tools found the identical label at the identical
  line. `tri_comparison_reconcile.py` now normalizes a single leading dot before cross-tool
  pairing, so these register as agreements instead of a two-sided phantom disagreement.
- *Genuine ctags structural limitation (2 occ, GitGalaxy credited):* purely numeric local code
  labels — `.1:` (`bootos/counter.asm:52`, opens a routine: `int 0x22` …) and `.2:` (`:67`,
  `mov [di],ax` …) — cannot be tagged by Universal Ctags' Asm parser under any name (a tag name
  must start with a letter). GitGalaxy is correct; ctags has no way to represent these. This is
  the whole residual of the shape now, so it carries `credit_tools: ["gitgalaxy"]` — the two
  occurrences count toward GitGalaxy's precision numerator, taking it to 97/97.
- *Genuine GitGalaxy false positive (1 occ, now fixed):* `ape.mbrpad:` (`cosmopolitan/ape.S:525`),
  an MBR-padding object (`.org 0x1b4` / `.endobj ape.mbrpad`), was being counted as a subroutine.
  `func_start` gained a bounded negative lookahead (§3) that rejects a label followed only by a
  pure data / location-counter directive. Run against the full ~80-repo corpus this also removed
  ~30 more genuine data-table labels from `cosmopolitan/ape.S` (raw `func_start` signal 61 → 39),
  `start.S` (ELF-note labels), and `hellosilicon/matrixmultneon.s` (`.short`/`.fill` matrices) —
  all verified against source as declarative data, no real subroutine touched.

**ctags solo-correct shape** (`agree[ctags]_vs[gitgalaxy]`, 26 occurrences — unchanged count,
but now cleanly one-directional). Every one is ctags' generic Asm parser tagging a line-start
label that is not a subroutine entry, and GitGalaxy correctly excludes all 26:
- Data-emission labels: `intro`/`error_message`/`commands`/`int_0x20` in `bootos/os.asm` (`db`/`dw`
  strings and jump tables); `A`/`B`/`C` in `hellosilicon/matrixmultneon.s` (`.short`/`.fill`
  matrices); `prtstr`/`getcreditcards`/`instr` (`.asciz`/`.ascii` strings).
- Section / object markers in `cosmopolitan/ape.S`: `__ro`/`cstr`/`_gdt_end`/`sconf` (`.endobj`),
  `ape_loader` (`.incbin`), `ape_phdrs`/`ape_macho`/`ape_grub`/`ape_mz`/`apesh` (ELF/Mach-O/
  Multiboot/shell header data via `.long`/`.ascii`), `_gdtr`/`_gdtrlo` (GDT register values),
  `ape_idata_idtend`/`ape_idata_iatend` (`.byte` terminators).
- `.Lenv0:`/`.Largv0:` — `.L`-prefixed GCC compiler-local labels `func_start` deliberately
  excludes.

No `debit_tools` on this shape: ctags alone claims these 26, so they already sit in its own
precision denominator with no corroboration — there is no shared-consensus mistake to subtract.
The `#1949` `_slice_by_labels` recall bug that used to be mixed into this shape is **fixed and
closed**; there is no remaining GitGalaxy recall miss here.

**A separate, more serious bug found during the same investigation, not part of either ledger
shape:** cross-referencing GitGalaxy's own reported `function_data.start_line` values against
ctags' (correct) line numbers for `cosmopolitan/ape.S` turned up a systematic, monotonically
growing line-number drift (+1 early in the file, growing to +9 by the end) — not a func/class
existence problem, but every function's reported LINE gets progressively wronger the deeper it
sits in the file. Root-caused to `prism.py`'s `_strip_single_line_comments` (shared by every
`line_exclusive`-family language, assembly included) using Python's `str.splitlines()`, which
splits on Form Feed/vertical tab/other Unicode line-boundary characters beyond `\n`/`\r\n` — real
source (`ape.S` uses `\f` as a deliberate page-break idiom in its comments) gets a phantom `\n`
silently inserted for every such character once the stream is rejoined. Confirmed exactly: `ape.S`
has 9 real Form Feed characters, and the observed drift at each function matches the cumulative
Form Feed count up to that point precisely. Filed as
[#1954](https://github.com/squid-protocol/gitgalaxy/issues/1954) — potentially affecting all 20
`line_exclusive` languages, not just assembly, though only confirmed live here so far.

Full verdicts with complete citations live in `docs/self_scan/tri_comparison_ledger.json` (search
for `"language": "assembly"`, distinguishing it from the `agc_assembly`-prefixed keys).
