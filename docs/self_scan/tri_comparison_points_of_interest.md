# Tri-Comparison Points of Interest

Generated from `tri_comparison_ledger.json` by `tests/tools/tri_comparison_report.py --write` -- do not hand-edit this file, edit the ledger and regenerate. See `docs/self_scan/how_to_investigate_a_discrepancy.md` for what ❓ entries are asking for.

Sorted 2-vs-1 splits before 3-way splits, unvalidated before validated, biggest occurrence count first within each tier -- see this script's own module docstring for why that order.

## agc_assembly

### ✅ `agc_assembly` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 215 occurrences as of 2026-08-22T22:18:52Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-20T00:00:00Z):
> Mixed-cause shape, fully accounted for via a corpus-wide cross-reference of ctags' actual output against GitGalaxy's raw func_start regex matches and its real pipeline/DB output (215 + 50 = 265, no unexplained residual). (1) 215/265 (81%): ctags' Asm "l" kind tags EVERY line-start label unconditionally, including pure data/constant-definition labels (e.g. ERASCON1 OCTAL 00061, S10BITS, LSTBNKCH -- AGC_BLOCK_TWO_SELF-CHECK.agc:133 and nearby) that are never followed by an executable instruction. GitGalaxy's func_start regex deliberately requires the label be followed by a real instruction mnemonic from a fixed whitelist, so it does not count these as functions -- a genuine, intentional precision distinction (code label vs. data label), not a GitGalaxy defect; ctags' generic Asm parser has no way to make this distinction at all. (2) 50/265 (19%): a real, confirmed GitGalaxy engine defect in detector.py's _slice_by_labels (Mode A), independently root-caused to two separate bugs: (a) `RELINT` is incorrectly included in `self.assembly_returns`'s early-termination keyword list (detector.py:572-575) -- in real AGC assembly RELINT means "release interrupt inhibit" and commonly opens a long interrupt-handler routine rather than closing one, so it truncates the real body to one line (confirmed: ELOOPFIN, AGC_BLOCK_TWO_SELF-CHECK.agc:303, a 20+-line real routine collapsed to just its own label line); (b) the `len(block.splitlines()) < 2` guard (detector.py:1973) unconditionally discards legitimate single-instruction assembly subroutines when the next func_start match sits on the very next line (confirmed: SOPTION1-SOPTION5+, AGC_BLOCK_TWO_SELF-CHECK.agc:210-214, each a real one-instruction label). Filed as #1949 -- a follow-up read-only Gemini/agy dispatch confirmed both root causes generalize beyond agc_assembly to the shared Mode A mechanism (assembly, cobol, fortran, abap all independently exhibit bug 1; assembly and cobol also exhibit bug 2), plus two further bug-1 variants not visible from agc_assembly alone: the terminator regex also false-matches inside comments (assembly) and inside hyphenated identifier names (cobol), not just legitimate-but-misclassified instructions. See #1949 for the full cross-language evidence and fix scope. No credit/debit -- the 215 portion is an honest scope difference (not two tools independently wrong about the same fact), and the 50 portion is GitGalaxy's own unresolved bug, not something ctags corroborates or contradicts.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ADRS1` | *(n/a)* | *(n/a)* | 155 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ERASCON1` | *(n/a)* | *(n/a)* | 133 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ERASCON2` | *(n/a)* | *(n/a)* | 134 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ERASCON3` | *(n/a)* | *(n/a)* | 136 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ERASCON4` | *(n/a)* | *(n/a)* | 137 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ERASCON5` | *(n/a)* | *(n/a)* | 146 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `LSTBNKCH` | *(n/a)* | *(n/a)* | 512 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `S10BITS` | *(n/a)* | *(n/a)* | 138 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `S13BITS` | *(n/a)* | *(n/a)* | 143 |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `S8BITS` | *(n/a)* | *(n/a)* | 131 |

### ✅ `agc_assembly` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 37 occurrences as of 2026-08-22T22:18:52Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-20T00:00:00Z):
> Confirmed: all 35 occurrences are real AGC labels that GitGalaxy correctly extracts and Universal Ctags' generic Asm parser structurally cannot tag, due to AGC assembly's non-standard label-naming conventions. Two sub-patterns, both confirmed corpus-wide (14/35 + 21/35 = 35/35, not just the sample): (1) labels with an embedded hyphen -- AGC's own convention of naming a point relative to an event, e.g. TIG-35/TIG-30/CALLT-35 in BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc:250/292/222 ("35/30 seconds before Time of Ignition"); (2) labels starting with a digit or a leading minus sign, e.g. 1CHK/2EBANK/-1CHK in AGC_BLOCK_TWO_SELF-CHECK.agc:184 (real label text is "-1CHK"). Directly verified via `ctags --language-force=Asm --kinds-Asm=l` against the real corpus files: ctags emits zero tags for any of these names (confirmed by grepping its actual output for the exact names and their surrounding CHK-suffixed siblings, which ARE tagged when they don't start with a hyphen/digit) -- ctags' Asm parser requires a tag name to start with a letter and contain no hyphen, neither of which is a real constraint in AGC assembly's own label syntax. GitGalaxy's func_start regex ([A-Z0-9_-]+ at line start) has no such restriction. This is a confirmed, structural ctags/Asm-parser limitation, not corroboration of anything wrong on GitGalaxy's side -- logged to docs/why_gitgalaxy_beats_ast_here.md.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `1CHK` | 184 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `27TO30` | 466 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `0EBANK` | 236 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `2EBANK` | 250 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `17TO20` | 460 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `TIG-35` | 250 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `CALLT-35` | 222 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `TIG-0` | 390 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `TIG-30` | 292 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `TIG-5` | 354 | *(n/a)* | *(n/a)* |

## assembly

### ✅ `assembly` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 26 occurrences as of 2026-08-22T22:18:54Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-20T00:00:00Z):
> Mixed shape, no clean credit/debit call. (1) A real, confirmed GitGalaxy defect: the same detector.py `_slice_by_labels` bug filed for agc_assembly as #1949 (RELINT-style early truncation and single-line/blank-collapsed body discard) independently confirmed live for generic assembly too -- `del_command:` (bootos/os.asm:269) sits immediately before the next label `os22:` with nothing between, collapsing to a one-line block and getting discarded; `C:`/`prtstr:` (hellosilicon/matrixmultneon.s:90,92) are each followed only by a data directive (`.fill`, `.asciz`) then a blank line before the next label, same one-line-after-strip() collapse. All three are real regex matches (confirmed via direct func_start.finditer against the raw text) that never reach the final function list -- tracked under #1949, not a new issue. (2) A correct-by-design GitGalaxy exclusion: `.Lenv0:`/`.Largv0:` (cosmopolitan/ape.S:1784-1785) start with the `.L` prefix func_start's own negative lookahead deliberately excludes (GCC's own convention for compiler-generated local/temporary labels) -- both are genuinely data labels (`.asciz` string constants) here, not real subroutines; ctags' generic Asm parser has no such convention-awareness and tags them anyway. (3) ctags itself over-tags some non-callable constructs GitGalaxy correctly excludes -- C-preprocessor `#define` macro constants (`GRUB_MAGIC`/`GRUB_EAX`/`GRUB_AOUT`/`GRUB_CHECKSUM`/`USE_SYMBOL_HACK`, cosmopolitan/ape.S:49,1679-1682) are not real assembly labels at all (no trailing `:`), but ctags' Asm parser tags them regardless. No credit/debit -- the shape mixes a real unresolved GitGalaxy recall gap (#1949) with cases where ctags is the one over-tagging, not a clean corroboration story either direction.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bootos/os.asm | `commands` | *(n/a)* | *(n/a)* | 625 |
| bootos/os.asm | `empty` | *(n/a)* | *(n/a)* | 366 |
| bootos/os.asm | `error_message` | *(n/a)* | *(n/a)* | 619 |
| bootos/os.asm | `find` | *(n/a)* | *(n/a)* | 360 |
| bootos/os.asm | `int_0x20` | *(n/a)* | *(n/a)* | 646 |
| bootos/os.asm | `intro` | *(n/a)* | *(n/a)* | 616 |
| bootos/os.asm | `load_vec` | *(n/a)* | *(n/a)* | 197 |
| bootos/os.asm | `loop` | *(n/a)* | *(n/a)* | 306 |
| cosmopolitan/ape.S | `Largv0` | *(n/a)* | *(n/a)* | 1785 |
| cosmopolitan/ape.S | `Lenv0` | *(n/a)* | *(n/a)* | 1784 |

### ✅ `assembly` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 7 occurrences as of 2026-08-22T22:18:54Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-20T00:00:00Z):
> Mixed shape, three distinct confirmed mechanisms, no clean credit/debit call (real wins and real gaps in both directions within the same shape). (1) A dot-prefix naming-convention split -- NASM/GAS local labels scoped to the preceding global label are written with a leading `.` (e.g. `.load_vec:`, `.loop:` in bootos/os.asm:197,306), which GitGalaxy's func_start regex captures verbatim but ctags' Asm parser strips before emitting the tag (confirmed: ctags reports the SAME real label as `load_vec`/`loop`, no dot -- both tools genuinely found the same real construct, they just serialize the name differently). This is a name-string artifact of exact-string ledger grouping, not a detection difference on either side. (2) A genuine ctags gap: purely numeric local labels (`.1:`, `.2:` in bootos/counter.asm:52,67) are not tagged by ctags' Asm parser under ANY name (confirmed: neither `1`/`2` nor `.1`/`.2` appear in its output at all) -- GitGalaxy correctly finds these. (3) A genuine GitGalaxy precision gap, the mirror image of agc_assembly's own win: unlike agc_assembly's func_start (which requires a label be followed by a real instruction opcode), generic assembly's func_start has no such requirement -- ANY `identifier:` at line start matches, so it also matches pure data/constant declaration labels ctags' comparatively more conservative reading skips: `max_entries: equ sector_size/entry_size` (bootos/os.asm:166, a compile-time constant, not a subroutine), and several string/metadata labels in cosmopolitan/ape.S followed only by `.asciz`/data directives (`ape.ident`, `freebsd.ident`, `netbsd.ident`, `openbsd.ident`, `str.error`, `str.crlf`, `str.e820`, `str.oldcpu`). Not filed as a bug -- generic assembly's func_start is intentionally permissive because it has to span wildly different, informally-specified dialects (x86/ARM/legacy real-mode) where a fixed per-opcode whitelist like agc_assembly's isn't practical; worth a future harden-language-extraction look at whether a narrower heuristic (e.g. excluding labels followed only by known data-directive pseudo-ops like .asciz/.long/.byte/equ) could recover some of this precision without losing real dialect coverage, but that's a design tradeoff, not a clear regression to fix urgently.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bootos/counter.asm | `.1` | 52 | *(n/a)* | *(n/a)* |
| bootos/counter.asm | `.2` | 67 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.loop` | 306 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.find` | 360 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.empty` | 366 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.load_vec` | 197 | *(n/a)* | *(n/a)* |
| cosmopolitan/ape.S | `ape.mbrpad` | 525 | *(n/a)* | *(n/a)* |

## c

### ✅ `c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 74 occurrences as of 2026-08-22T22:18:59Z*

**Verdict** (by Gemini (dispatched via tri-comparison-ledger-sweep), confirmed by Claude Sonnet 5, 2026-08-19T00:00:00Z):
> Confirmed, independently verified all 6 sampled names against real source -- GitGalaxy and ctags both correct, tree-sitter over-recalling from two related but distinct preprocessor-driven mechanisms, both already covered by existing infrastructure: (1) keyword/macro misparse -- 'if' (dictobject.c:522-527, an `#if SIZEOF_VOID_P > 4` / `else if` sequence desyncs the parse) and 'DICT___REVERSED___METHODDEF' (dictobject.c:5102, a PyMethodDef array-initializer macro, not a definition) are both ALREADY in tree_sitter_accuracy_audit.py's `_C_KNOWN_MACRO_HALLUCINATIONS` exclusion set (confirmed by reading it directly) -- this tri-comparison tool's raw walk deliberately doesn't apply that list (it's a curated, ground-truth-shaped judgment call, appropriately left to reconciliation per this module's own stated design, not baked into the walk). (2) dead #if 0 code -- '_PyObject_ManagedDictValidityCheck' (dictobject.c:7396) and 'tos_char'/'print_stack'/'print_stacks' (frameobject.c:1264-1313) are genuinely well-formed function definitions sitting entirely inside `#if 0 ... #endif` guards; tree-sitter has no preprocessor model and parses the dead branch as live code. Both mechanisms are already the exact shape docs/why_gitgalaxy_beats_ast_here.md's Claim 8 names generically ('a dead #if 0 block... macro definitions... that merely look structural') -- added these 4 new concrete citations to Claim 8's evidence section rather than treating this as a new finding. No GitHub issue -- both tools already behave as intended; this is expected, already-documented tree-sitter preprocessor-blindness surfacing under the new tri-comparison reconciliation, not a fresh defect.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/dictobject.c | `if` | *(n/a)* | 524 | *(n/a)* |
| cpython/dictobject.c | `if` | *(n/a)* | 553 | *(n/a)* |
| cpython/dictobject.c | `if` | *(n/a)* | 804 | *(n/a)* |
| cpython/dictobject.c | `DICT___REVERSED___METHODDEF` | *(n/a)* | 5102 | *(n/a)* |
| cpython/dictobject.c | `_PyObject_ManagedDictValidityCheck` | *(n/a)* | 7399 | *(n/a)* |
| cpython/frameobject.c | `tos_char` | *(n/a)* | 1267 | *(n/a)* |
| cpython/frameobject.c | `print_stack` | *(n/a)* | 1284 | *(n/a)* |
| cpython/frameobject.c | `print_stacks` | *(n/a)* | 1304 | *(n/a)* |
| cpython/object.c | `if` | *(n/a)* | 1272 | *(n/a)* |
| micropython/gc.c | `if` | *(n/a)* | 1353 | *(n/a)* |

### ✅ `c` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 14 occurrences as of 2026-08-22T22:18:59Z*

**Verdict** (by Claude Sonnet 5 (resolved directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Not a new finding -- both sampled names are ALREADY in tree_sitter_accuracy_audit.py's _C_KNOWN_MACRO_HALLUCINATIONS exclusion set (confirmed by grep: 'EXPORT_FUN' and 'MICROPY_WRAP_MP_EXECUTE_BYTECODE' both present). This shape is the same already-documented macro-hallucination mechanism (Claim 8) as the earlier tree-sitter-alone shape, just with ctags ALSO independently hallucinating the same 2 names the same way (both tools' regex/grammar parsers get fooled by the same macro-definition text). GitGalaxy correctly excludes both. Resolved directly, no dispatch needed.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/dictobject.c | `ASSERT_DICT_LOCKED` | *(n/a)* | 163 | 164 |
| cpython/gc.c | `validate_list` | *(n/a)* | 392 | 393 |
| cpython/gc.c | `gc_list_validate_space` | *(n/a)* | 436 | 437 |
| cpython/gc.c | `validate_spaces` | *(n/a)* | 445 | 446 |
| cpython/gc.c | `validate_consistent_old_space` | *(n/a)* | 457 | 458 |
| cpython/typeobject.c | `types_world_is_stopped` | *(n/a)* | 88 | 89 |
| cpython/typeobject.c | `types_stop_world` | *(n/a)* | 122 | 123 |
| cpython/typeobject.c | `types_start_world` | *(n/a)* | 131 | 132 |
| cpython/typeobject.c | `type_lock_prevent_release` | *(n/a)* | 142 | 143 |
| cpython/typeobject.c | `type_lock_allow_release` | *(n/a)* | 164 | 165 |

### ✅ `c` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 13 occurrences as of 2026-08-22T22:18:59Z*

**Verdict** (by Gemini (dispatched via tri-comparison-ledger-sweep), confirmed by Claude Sonnet 5, 2026-08-19T00:00:00Z):
> 3 distinct causes, all genuine tree-sitter-c grammar limitations (GitGalaxy and ctags both correct in all 10 sampled cases) -- confirmed via dispatched investigation (which ran tree-sitter's C grammar directly and found ERROR nodes in every case) plus independent source-level spot-checks of all 3 trigger shapes. This is a C-scale instance of Claim 7 (CPP-directive-driven recall loss) -- added to that claim's evidence section. (1) 4 samples: an #if/#else pair splitting a single `if` condition inside a function body (ceval.c:33, _Py_ReachedRecursionLimitWithMargin). (2) 5 samples: bare, un-semicoloned macro invocations the grammar can't cleanly recover from, losing the next real function (object.c:1269-1271's _Py_COMP_DIAG_PUSH/IGNORE_DEPR_DECLS/POP before _PyObject_SetAttributeErrorContext; similar shape for the typeobject.c slot-getattr cluster). (3) 1 sample: #if/#endif wrapping only the `static` storage-class specifier, separated from the rest of the signature (micropython/compile.c:3473-3476, mp_compile_to_raw_code). Unlike Fortran's existing Claim 7 evidence (entire trailing sections lost), C's version is local -- one function lost per trigger, not a cascading region. No GitHub issue -- documented as new Claim 7 evidence, not a fixable tooling bug (this repo doesn't control tree-sitter-c's grammar).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/ceval.c | `_Py_CheckRecursiveCall` | 282 | *(n/a)* | 283 |
| cpython/ceval.c | `_Py_ReachedRecursionLimitWithMargin` | 28 | *(n/a)* | 29 |
| cpython/ceval.c | `_Py_EnterRecursiveCallUnchecked` | 52 | *(n/a)* | 53 |
| cpython/dictobject.c | `dictiter_iternextitem` | 5994 | *(n/a)* | 5995 |
| cpython/object.c | `_PyObject_SetAttributeErrorContext` | 1279 | *(n/a)* | 1280 |
| cpython/typeobject.c | `_Py_slot_tp_getattr_hook` | 10817 | *(n/a)* | 10818 |
| cpython/typeobject.c | `call_attribute` | 10792 | *(n/a)* | 10793 |
| cpython/typeobject.c | `slot_tp_call` | 10768 | *(n/a)* | 10769 |
| cpython/typeobject.c | `_Py_slot_tp_getattro` | 10785 | *(n/a)* | 10786 |
| micropython/compile.c | `mp_compile_to_raw_code` | 3474 | *(n/a)* | 3476 |

### ✅ `c` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-22T22:18:59Z*

**Verdict** (by Claude Sonnet 5 (resolved + fixed directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Confirmed real ctags limitation, not a GitGalaxy or tree-sitter defect -- resolved directly (no dispatch needed), source read confirms all 7 sampled names. RICHCMP_WRAPPER/SLOT0/SLOT1/SLOT1BINFULL are all-caps macro names; every occurrence is a MACRO INVOCATION (a call to a previously-#define'd boilerplate-generating macro), not a function definition -- confirmed at cpython/typeobject.c:10099 (`RICHCMP_WRAPPER(lt, Py_LT)`) and :10544 (`SLOT1(slot_mp_subscript, __getitem__, PyObject *)`), same shape as the multiple SLOT0/SLOT1 hits at different lines (each is a separate invocation of the same macro generating a different wrapper function). ctags' regex-based C parser tags the macro-invocation site itself as a function; GitGalaxy and tree-sitter both correctly don't. Deliberately NOT fixed with a curated name-exclusion list in the gatherer (unlike the sibling __anon* class shape, this would require hand-curating specific macro names -- the same ground-truth-judgment category tri_comparison_gatherer.py's own docstring reasons belongs in reconciliation, not the raw reader) -- documented in ctags_reader.py instead, alongside its existing per-language notes.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `RICHCMP_WRAPPER` | *(n/a)* | *(n/a)* | 10099 |
| cpython/typeobject.c | `SLOT0` | *(n/a)* | *(n/a)* | 10626 |
| cpython/typeobject.c | `SLOT0` | *(n/a)* | *(n/a)* | 10682 |
| cpython/typeobject.c | `SLOT0` | *(n/a)* | *(n/a)* | 10728 |
| cpython/typeobject.c | `SLOT1` | *(n/a)* | *(n/a)* | 10542 |
| cpython/typeobject.c | `SLOT1` | *(n/a)* | *(n/a)* | 10703 |
| cpython/typeobject.c | `SLOT1BINFULL` | *(n/a)* | *(n/a)* | 10575 |

### ✅ `c` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-22T22:18:59Z*

**Verdict** (by Claude Sonnet 5 (resolved directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Confirmed GitGalaxy correct, real finding -- a new, narrower instance of Claim 3 (parse-error cascade), added to docs/why_gitgalaxy_beats_ast_here.md. All 4 sampled names (slot_mp_ass_subscript:10544, slot_nb_inplace_power:10697, slot_tp_repr:10714, slot_tp_hash:10730, all cpython/typeobject.c) are ordinary, unremarkable function definitions -- nothing unusual individually -- but each sits directly after a bare SLOT0/SLOT1 macro-invocation LINE (`SLOT1(slot_mp_subscript, __getitem__, PyObject *)`, `SLOT0(slot_tp_str, __str__)`, etc.) that isn't valid freestanding C without macro expansion. GitGalaxy's regex has no adjacency sensitivity and finds all 4 correctly; both ctags and tree-sitter locally lose the SINGLE function immediately following each such line (recovers after just one function, not a full cascade to EOF -- confirmed by resolving all 4 as isolated single-function misses, not a growing region). Resolved directly, no dispatch needed -- same pattern verified at all 4 sample points before writing up.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `slot_tp_hash` | 10730 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_mp_ass_subscript` | 10544 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_tp_repr` | 10714 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_nb_inplace_power` | 10697 | *(n/a)* | *(n/a)* |

### ✅ `c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-22T22:18:59Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> UPDATED after a real production fix (the same fix documented in cpp's agree[gitgalaxy,tree_sitter]_vs[ctags] entry -- c and cpp share the mechanism, `lang_id in ("c", "cpp")` in detector.py's `_slice_by_braces`). GitGalaxy now scans each file for `#define NAME(...)` function-like macro definitions and excludes any func_start match whose captured name is a known macro -- confirmed to eliminate the already-documented `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/`SLOT1BINFULL`/`DICT___REVERSED___METHODDEF` cpython/typeobject.c false positives entirely (a direct `SELECT func_name ... WHERE func_name IN (...)` query against a fresh scan returned zero rows). The small residual (3 occurrences: `slot_nb_power`, `slot_nb_bool`, `wrap_next`, all cpython/typeobject.c) is a DIFFERENT, unrelated finding, not yet individually root-caused -- GitGalaxy and tree-sitter both correctly find these real functions and ctags doesn't; plausibly the same category of ctags miss documented in cpp's sibling entry (an ordinary function ctags' C++ parser fails to tag for reasons unrelated to macros) but not directly confirmed for these three specific names. No credit_tools adjustment applies -- already a naturally-corroborated 2-of-3 agreeing pair.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `slot_nb_power` | 10577 | 10577 | *(n/a)* |
| cpython/typeobject.c | `slot_nb_bool` | 10630 | 10630 | *(n/a)* |
| cpython/typeobject.c | `wrap_next` | 10106 | 10106 | *(n/a)* |

### ✅ `c` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:18:59Z*

**Verdict** (by Claude Sonnet 5 (resolved + fixed directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Not a GitGalaxy or ctags defect -- a bug in this tool's OWN _count_ctags_signature_params (tri_comparison_gatherer.py), now fixed. Confirmed directly: ran ctags against cpython/ceval.c, PyEval_GetLocals(void)'s raw signature field is literally the text '(void)'. GitGalaxy and tree-sitter both already special-case C's explicit empty-parameter-list idiom (0 real args, matching detector.py's own _count_top_level_args docstring) -- _count_ctags_signature_params did not, splitting '(void)' into one non-empty segment and counting it as 1 real parameter (the same class of bug its own docstring already describes fixing twice for Python's trailing-comma and bare * / marker cases). Added 'void' to the segment-exclusion set alongside the existing '*'/'/'/'**' -- verified fix: _count_ctags_signature_params('(void)') now returns 0. This corpus (cpython) uses the (void) idiom extremely heavily, plausibly explaining most/all of the 104 occurrences; not independently re-verified beyond the sample, but the mechanism is unconditional (any '(void)' signature was miscounted the same way, corpus-wide) so high confidence it generalizes. No GitHub issue needed -- fixed directly in this same commit, not a repo-code defect.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython/gc.c | `gc_mark_subtree` | 1 | 1 | 2 |

## cobol

### ✅ `cobol` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 181 occurrences as of 2026-08-22T22:19:03Z*

**Verdict** (by Agent, 2026-08-22T00:00:00Z):
> Confirmed GitGalaxy engine defect (issue #1892). Fixed in the same pass by replacing the bare  boundary with (?=[ \t\n.]) in the func_start reserved word shield, preventing hyphenated verbs like DELETE-POLICY from being incorrectly shielded.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `CONFIGURATION` | *(n/a)* | *(n/a)* | 38 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 455 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 600 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 806 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 869 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 916 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 922 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 1240 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 1306 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 1372 |

## cpp

### ✅ `cpp` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 194 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> UPDATED: count grew (98 -> 194) as a direct, correct consequence of the OPCODE-macro fix documented in the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] entry -- tree-sitter's OWN OPCODE-family misparse (godot/gdscript_vm.cpp's bytecode-dispatch macro) was previously MASKED by GitGalaxy sharing the identical mistake (both wrong == they 'agreed', landing in the other shape instead of this one). Now that GitGalaxy correctly excludes known macro invocations, tree-sitter's own grammar limitation on this exact pattern is cleanly isolated here instead, confirmed via the shape's own examples (repeated `OPCODE` entries at godot/gdscript_vm.cpp, tree_sitter line set, ctags/gitgalaxy both None). The remaining, previously-documented causes (bare control-flow-keyword/`void` hallucination, conversion-operator naming-suffix convention) are unchanged and still contribute the bulk of the original 98. No credit/debit applies -- tree-sitter is the one that's wrong here, alone.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 761 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 848 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 865 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 879 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 902 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 932 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 954 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 988 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 1034 | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | *(n/a)* | 1068 | *(n/a)* |

### ✅ `cpp` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 61 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real GitGalaxy args-counting defect, filed as https://github.com/squid-protocol/gitgalaxy/issues/2012 . Two distinct sub-patterns visible in the sample: (1) zero-undercounting for out-of-class method definitions with real parameters (VBufStorage_buffer_t::replaceSubtrees, Translator::BuildBuffer, Translator::BuildVhloCompositeV1Op, and every `operator()` call-operator overload in godot/node.h) where ctags and tree-sitter both correctly count real, non-zero parameter lists and GitGalaxy reads 0; (2) an off-by-one OVERcount for a constructor with a member-initializer-list but zero real parameters (VBufStorage_buffer_t's default constructor -- ctags/tree-sitter correctly read 0 params, GitGalaxy reads 1). Not the same shape as the func_start recall gaps in #2009/#2010 -- these are all functions GitGalaxy already finds, just with the wrong parameter count. Needs its own dedicated investigation per the issue (may be one or two root causes).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| NVDA/storage.cpp | `VBufStorage_buffer_t::replaceSubtrees` | 0 | 1 | 1 |
| NVDA/storage.cpp | `outputEscapedAttribute` | 0 | 3 | 3 |
| NVDA/storage.cpp | `VBufStorage_buffer_t::VBufStorage_buffer_t` | 1 | 0 | 0 |
| godot/node.h | `operator()` | 0 | 2 | 2 |
| godot/node.h | `operator()` | 0 | 2 | 2 |
| godot/node.h | `operator()` | 0 | 2 | 2 |
| godot/node.h | `operator()` | 0 | 2 | 2 |
| godot/variant.cpp | `operator<` | 0 | 1 | 1 |
| godot/variant.h | `operator()` | 0 | 2 | 2 |
| mlir/flatbuffer_export.cc | `Translator::BuildBuffer` | 0 | 3 | 3 |

### ✅ `cpp` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 60 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real tree-sitter-cpp grammar limitation, not a GitGalaxy or ctags defect. Every sampled case (GDScriptFunction::call, Main::setup, Main::setup2, Main::start, Object::Connection::operator Variant) is a large, complex function -- GDScriptFunction::call in particular (godot/gdscript_vm.cpp:499) is a bytecode interpreter's main dispatch loop using GNU 'labels as values' computed-goto syntax (`&&OPCODE_LABEL`) via the same OPCODES_TABLE/OPCODE macro family documented in the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] entry -- a non-standard GNU extension tree-sitter-cpp's grammar does not support, which plausibly causes a parse error cascade that loses the enclosing function_definition node entirely rather than just misreading the body. ctags and GitGalaxy both correctly find and name these functions regardless of body content, since neither one needs to fully parse the function body to recognize its signature. tree-sitter's non-detection is a confirmed limitation in tree-sitter itself -- but no credit_tools adjustment applies: ctags and GitGalaxy are already a 2-of-3 AGREEING PAIR on this shape (agreeing_tools has 2 members), which already satisfies reconcile_symbols' own `len(present) >= 2` precision-credit condition naturally with no ledger adjustment needed. credit_tools exists for a LONE, single-tool claim (agreeing_tools with exactly 1 member) the base algorithm can't otherwise corroborate -- applying it to an already-mutually-corroborating pair would double-count (confirmed: this exact mistake briefly pushed ctags' precision past 100% before being caught and reverted in this same session).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/gdscript_vm.cpp | `GDScriptFunction::call` | 499 | *(n/a)* | 499 |
| godot/main.cpp | `Main::setup` | 1027 | *(n/a)* | 1027 |
| godot/main.cpp | `Main::setup2` | 3007 | *(n/a)* | 3007 |
| godot/main.cpp | `Main::start` | 3987 | *(n/a)* | 3987 |
| godot/object.cpp | `Object::Connection::operator Variant` | 108 | *(n/a)* | 108 |
| godot/object.h | `RequiredResult` | 994 | *(n/a)* | 995 |
| godot/object.h | `RequiredResult` | 1003 | *(n/a)* | 1004 |
| godot/object.h | `RequiredResult` | 1012 | *(n/a)* | 1013 |
| godot/object.h | `RequiredParam` | 1130 | *(n/a)* | 1131 |
| godot/object.h | `operator ptr_type` | 1031 | *(n/a)* | 1031 |

### ✅ `cpp` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 30 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed ctags-only limitation: ctags parses INSIDE C++ macro DEFINITION bodies as if they were real, already-expanded code. godot/object.h's GDCLASS/_FORCE_INLINE_-based macros (`#define GDCLASS(m_class, m_inherits) ... _FORCE_INLINE_ bool (Object::*_get_get() const)(...) {...} ...`) never run as written -- they only produce real code once expanded at a `GDCLASS(SomeClass, Base)` call site elsewhere -- but ctags tags `_get_get`/`_get_set`/`_get_bind_methods`/`_get_bind_compatibility_methods`/`_get_notification`/`_get_property_can_revert`/`_get_property_get_revert`/`_get_validate_property`/`_get_get_property_list` (all 9 sampled cases, all from this same macro) as if they were ordinary member functions. Neither GitGalaxy nor tree-sitter are fooled by this. Documented in ctags_reader.py's KIND MAPS section (cpp bullet) rather than fixed -- this is ctags' own parser behavior, nothing in this repo's tooling can distinguish a macro-definition body from real code without reimplementing preprocessing.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/object.h | `_get_bind_compatibility_methods` | *(n/a)* | *(n/a)* | 552 |
| godot/object.h | `_get_bind_methods` | *(n/a)* | *(n/a)* | 549 |
| godot/object.h | `_get_get` | *(n/a)* | *(n/a)* | 555 |
| godot/object.h | `_get_get_property_list` | *(n/a)* | *(n/a)* | 561 |
| godot/object.h | `_get_notification` | *(n/a)* | *(n/a)* | 573 |
| godot/object.h | `_get_property_can_revert` | *(n/a)* | *(n/a)* | 567 |
| godot/object.h | `_get_property_get_revert` | *(n/a)* | *(n/a)* | 570 |
| godot/object.h | `_get_set` | *(n/a)* | *(n/a)* | 558 |
| godot/object.h | `_get_validate_property` | *(n/a)* | *(n/a)* | 564 |
| godot/object.h | `operator Ref<T_Other>` | *(n/a)* | *(n/a)* | 1036 |

### ✅ `cpp` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 9 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> UPDATED after a real production fix. The OPCODE-family shared mistake documented in this shape's prior verdict (~96 of the original 105 occurrences) is now FIXED: GitGalaxy's func_start (and by the same mechanism, C's) now scans each file for `#define NAME(...)` function-like macro definitions and excludes any match whose captured name is a known macro -- the exact same fact universal-ctags itself already used (confirmed via a direct `ctags -f -` run: ctags tags `OPCODE` only once, at its own #define line, kind `d`, and produces zero tags at any invocation site -- it isn't smarter about the invocation's shape, it just already knows the name is a macro and never re-tags it). This also fixed the already-documented C `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/`SLOT1BINFULL`/`DICT___REVERSED___METHODDEF` false positives as a bonus (same mechanism, `lang_id in ("c", "cpp")`). Verified via 3 repeated full-corpus scans producing byte-identical function lists, the full extraction gauntlet, and both golden masters re-blessed. The remaining residual (9 occurrences, previously miscounted as more of the same shared mistake in the earlier verdict's blanket debit -- corrected here) is a DIFFERENT, unrelated finding: GitGalaxy and tree-sitter are CORRECT here, ctags is wrong. Two sub-patterns confirmed: (1) the already-documented macro-as-return-type-prefix pattern (`IFACEMETHODIMP_(void)` immediately before the real `FancyZones::Run() noexcept` -- ctags tags the macro invocation itself and loses the real name, powertoys/FancyZones.cpp, 4 occurrences); (2) a newly-confirmed, NOT yet root-caused ctags miss on an ordinary virtual method with no macro involvement at all (`virtual RID mesh_create_from_surfaces(const Vector<RenderingServerTypes::SurfaceData> &p_surfaces, int p_blend_shape_count = 0) override { ... }`, godot/rendering_server_default.h -- ctags produces zero tags anywhere near this real method, 5 occurrences). No credit_tools adjustment applies: GitGalaxy and tree-sitter are already a 2-of-3 agreeing pair here, which already satisfies reconcile_symbols' own natural precision-credit condition.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/rendering_server_default.h | `mesh_create_from_surfaces` | 363 | 363 | *(n/a)* |
| godot/rendering_server_default.h | `material_create_from_shader` | 324 | 324 | *(n/a)* |
| godot/rendering_server_default.h | `shader_create` | 278 | 278 | *(n/a)* |
| godot/rendering_server_default.h | `texture_create_from_native_handle` | 222 | 222 | *(n/a)* |
| godot/rendering_server_default.h | `redraw_request` | 111 | 111 | *(n/a)* |
| powertoys/FancyZones.cpp | `FancyZones::OnKeyDown` | 473 | 473 | *(n/a)* |
| powertoys/FancyZones.cpp | `FancyZones::Run` | 214 | 214 | *(n/a)* |
| powertoys/FancyZones.cpp | `FancyZones::Destroy` | 286 | 286 | *(n/a)* |
| powertoys/FancyZones.cpp | `FancyZones::VirtualDesktopChanged` | 303 | 303 | *(n/a)* |

### ✅ `cpp` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Compound shape, three distinct causes confirmed via source, not one. (1) Most of the sample (OPCODE_WHILE x2, OPCODE_SWITCH, OPCODE) is the same GG+tree-sitter shared macro-misparse family documented in the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] entry (godot/gdscript_vm.cpp's OPCODE/OPCODE_WHILE/OPCODE_SWITCH dispatch macros) -- here landing as 'GitGalaxy alone' because tree-sitter's own error recovery on this repeated macro pattern isn't fully deterministic across every occurrence, not because the underlying cause differs. GitGalaxy is WRONG for this portion (same debit as the sibling entry, not double-counted here since debit_tools is per-shape). (2) `attribute_buffer_applier_factories_`/`m_draggingState`/`std::thread` are a separate, real GitGalaxy FALSE POSITIVE: a lambda passed as a constructor argument or member-initializer-list entry (`m_draggingState([this]() {...}),`, `std::thread([...]() {...}).detach();`) is misread as a function definition. Filed as https://github.com/squid-protocol/gitgalaxy/issues/2013 . (3) `Variant::operator ::RID`/`Variant::operator ::AABB`/`Variant::operator Object *` are real functions GitGalaxy correctly finds (confirmed via godot/variant.cpp source) that didn't rank-match ctags/tree-sitter's own readings of the same functions by exact name string -- a residual, low-priority naming-comparison edge case (global-scope `::`-prefixed conversion-operator return types) not chased further in this pass. No credit/debit applied given the mixed, three-cause nature of this shape.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.cpp | `Variant::operator ::RID` | 2002 | *(n/a)* | *(n/a)* |
| godot/variant.cpp | `Variant::operator ::AABB` | 1882 | *(n/a)* | *(n/a)* |
| godot/variant.cpp | `Variant::operator Object *` | 2024 | *(n/a)* | *(n/a)* |
| mlir/flatbuffer_export.cc | `attribute_buffer_applier_factories_` | 679 | *(n/a)* | *(n/a)* |

### ✅ `cpp` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Not a real existence disagreement -- a template-argument name-formatting difference in the comparison tooling. `godot/variant.h`'s `HashMapComparatorDefault<Variant>` and `is_zero_constructible<Variant>` are template CLASS specializations; GitGalaxy and tree-sitter both read the name WITH its template argument baked in (matching the instantiation as written in source), while ctags strips the `<...>` template-argument suffix from its own class tag name. All three tools found the exact same class definition at the exact same line -- confirmed via the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] entry, which is the same pair of classes from the opposite direction. Low magnitude (2 occurrences) -- not chased to a code fix in this pass, but a plausible future micro-fix would strip a trailing `<...>` from gg/tree-sitter's class name before matching, mirroring how ctags_reader.py's operator-name normalization already handles a similar formatting mismatch.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `HashMapComparatorDefault` | *(n/a)* | *(n/a)* | 886 |
| godot/variant.h | `is_zero_constructible` | *(n/a)* | *(n/a)* | 984 |

### ✅ `cpp` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Same template-argument name-formatting difference as the sibling agree[ctags]_vs[gitgalaxy,tree_sitter] class entry, viewed from the opposite direction -- `HashMapComparatorDefault`/`is_zero_constructible` (ctags' bare names) vs. `HashMapComparatorDefault<Variant>`/`is_zero_constructible<Variant>` (GitGalaxy/tree-sitter's names, template argument included). Not a real disagreement about whether these classes exist -- see the sibling entry for the full explanation.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `HashMapComparatorDefault<Variant>` | *(n/a)* | 886 | *(n/a)* |
| godot/variant.h | `is_zero_constructible<Variant>` | *(n/a)* | 984 | *(n/a)* |

### ✅ `cpp` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real tree-sitter accuracy-tool limitation, filed separately (see the sibling agree[none]_vs[ctags,gitgalaxy,tree_sitter] args entry and its referenced issue for the full writeup). tree-sitter's own parameter count (via the shared `_get_param_count` helper in tree_sitter_accuracy_audit.py, reused by tri_comparison_gatherer.py) undercounts by exactly 1 whenever a function has a parameter with a default value -- confirmed 6/6 sampled cases (save_scene_to_path, step, get_index, atr_n, atr, ObjectSignalLock), all off by exactly 1, all involving a `= default_value` parameter, ctags and GitGalaxy both correctly counting the real total. No credit_tools/debit_tools adjustment applies -- this is an args-metric shape, and apply_verified_adjustments only ever touches existence-metric precision (args scores have no equivalent verified-adjustment mechanism in this ledger's own code, see tri_comparison_ledger.py's apply_verified_adjustments docstring), so these fields would be a pure no-op here regardless of value -- left empty rather than set-but-inert, for an accurate record.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/object.h | `RequiredResult` | 1 | 0 | 1 |
| godot/object.h | `RequiredParam` | 1 | 0 | 1 |

### ✅ `cpp` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:07Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> The single sampled occurrence (mlir/flatbuffer_export.cc:654, the `Translator` class's constructor) is exactly the bug filed as https://github.com/squid-protocol/gitgalaxy/issues/2009 -- a member-initializer-list spanning 906 characters exceeds GitGalaxy's func_start regex's 500-character cap for that clause, so the whole constructor is invisible to GitGalaxy despite ctags and tree-sitter both finding it correctly. GitGalaxy's non-detection is a confirmed, filed limitation -- but no credit_tools adjustment applies: ctags and tree-sitter are already a 2-of-3 AGREEING PAIR on this shape, which already satisfies reconcile_symbols' own `len(present) >= 2` precision-credit condition naturally. See the sibling agree[ctags,gitgalaxy]_vs[tree_sitter] entry for the full explanation of why credit_tools only applies to a LONE, single-tool claim, never an already-agreeing pair.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mlir/flatbuffer_export.cc | `Translator` | *(n/a)* | 654 | 654 |

## csharp

### ✅ `csharp` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 271 occurrences as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T18:13:27Z):
> Confirmed: this shape is entirely tree-sitter-c-sharp's own known parse-error cascade in roslyn/LanguageParser.cs, already root-caused and evidence-backed as Claim 3 in docs/why_gitgalaxy_beats_ast_here.md (issues #1427/#1567). A syntax construct at line ~5198 triggers a parse error whose recovery fails to resynchronize for the rest of the (14,680-line) file -- tree.root_node.type itself becomes ERROR, so tree-sitter's own recall for this file collapses to near-zero past that point. GitGalaxy's regex and ctags' text-based parser are both unaffected and correctly find these functions (all sampled: ParseVariableDeclarator, GetPrecedence, ParsePrimaryExpression, ScanType x3 -- real, ordinary private methods, exact line-number agreement between ctags and gitgalaxy on every one). This is the tri-comparison ledger's own version of a phenomenon already fully diagnosed for the 2-way tree_sitter_accuracy_audit.py tool via its cascade_promotable logic -- that logic was never ported to tri_comparison_gatherer.py/tri_comparison_reconcile.py, which is why this shows as an unvalidated ledger shape despite being a known, closed question. Not a GitGalaxy or ctags defect. CORRECTION (2026-08-21): credit_tools was originally set here, but this is wrong -- these tools already mutually corroborate each other (2-of-3 agreement), so their occurrences were already counted in base precision before any credit was applied. Adding credit on top double-counted them, pushing gitgalaxy's func_precision matched_consensus past its own total_slots (1297/965, >100%, a real, visible chart-rendering bug). credit_tools is only valid for a shape where a tool is completely ALONE and otherwise uncorroborated (e.g. this language's agree[gitgalaxy]_vs[ctags,tree_sitter] shape), never for an already-mutually-agreeing pair. Reset to empty; the validation itself (which tool is factually correct here) is unaffected and remains correct.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `ParseVariableDeclarator` | 5476 | *(n/a)* | 5476 |
| roslyn/LanguageParser.cs | `GetPrecedence` | 11213 | *(n/a)* | 11213 |
| roslyn/LanguageParser.cs | `ParsePrimaryExpression` | 11931 | *(n/a)* | 11931 |
| roslyn/LanguageParser.cs | `ScanType` | 7173 | *(n/a)* | 7173 |
| roslyn/LanguageParser.cs | `ScanType` | 7178 | *(n/a)* | 7178 |
| roslyn/LanguageParser.cs | `ScanType` | 7207 | *(n/a)* | 7207 |
| roslyn/LanguageParser.cs | `CanFollowCast` | 13159 | *(n/a)* | 13159 |
| roslyn/LanguageParser.cs | `ParseTypeCore` | 7592 | *(n/a)* | 7592 |
| roslyn/LanguageParser.cs | `IsPossibleExpression` | 11073 | *(n/a)* | 11073 |
| roslyn/LanguageParser.cs | `IsPossibleExpression` | 11078 | *(n/a)* | 11078 |

### ✅ `csharp` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 108 occurrences as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T18:13:44Z):
> Confirmed real ctags parser limitations, not a GitGalaxy or tree-sitter defect, via direct source reading and raw `ctags -x` runs against the flagged files. Two distinct mechanisms: (1) Local/nested functions -- roslyn/CSharpCompilation.cs's `validateSignature` (nested inside a larger method) and `isSupportedType` (a `static bool isSupportedType(...)` local function) are both structurally invisible to ctags, whose csharp kind map is only 'm' (top-level methods; "C# has no free functions" per ctags_reader.py's own comment) with no local-function concept at all -- this generalizes to every local function in the corpus, not just the sampled two. (2) Complex-signature misses and overload collisions on ordinary top-level private methods -- `FindEntryPoint` (nullable return/param types plus a generic `out` parameter) and `GetSourceDeclarationDiagnostics` (5 params, two with default values, one a `Func<...>` generic delegate) get no ctags tag at all, confirmed via `ctags -x` showing tags immediately before/after but not at their own lines -- isolated misses, not a wider blind region (unlike the tree-sitter cascade in the sibling ledger shape). `ReportUnusedImports` has two overloads at different lines; ctags tags only the first, silently dropping the second. Documented in tests/tools/ctags_reader.py's csharp KIND MAPS bullet. Credited on the strength of mechanism (1) generalizing structurally to the whole shape (ctags cannot see ANY local function, by construction) even though only ~5 of 107 occurrences were individually read -- mechanism (2)'s complex-signature misses are a smaller, less certain-to-generalize contributor to the same shape but point the same direction (ctags-side, not GitGalaxy/tree-sitter). CORRECTION (2026-08-21): credit_tools was originally set here, but this is wrong -- these tools already mutually corroborate each other (2-of-3 agreement), so their occurrences were already counted in base precision before any credit was applied. Adding credit on top double-counted them, pushing gitgalaxy's func_precision matched_consensus past its own total_slots (1297/965, >100%, a real, visible chart-rendering bug). credit_tools is only valid for a shape where a tool is completely ALONE and otherwise uncorroborated (e.g. this language's agree[gitgalaxy]_vs[ctags,tree_sitter] shape), never for an already-mutually-agreeing pair. Reset to empty; the validation itself (which tool is factually correct here) is unaffected and remains correct.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `FindEntryPoint` | 1993 | 1993 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `validateSignature` | 4463 | 4463 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `validateSignature` | 4689 | 4689 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `ReportUnusedImports` | 2747 | 2747 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `GetSourceDeclarationDiagnostics` | 3395 | 3395 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `isSupportedType` | 1798 | 1798 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `IsRuntimeAsyncEnabledIn` | 351 | 351 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `registeredUsageOfUsingsInTree` | 3359 | 3359 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `getExplicitAccessibilitySymbol` | 4945 | 4945 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `updateCachedDiagnostics` | 3308 | 3308 | *(n/a)* |

### ✅ `csharp` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 46 occurrences as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T21:45:53Z):
> Mixed shape, confirmed via a full name-diff against gather_language('csharp') rather than the capped sample alone: 44 of 48 are genuine local (nested) functions inside roslyn/LanguageParser.cs's tree-sitter parse-error cascade region (line >= ~5198, same mechanism as the sibling agree[ctags,gitgalaxy]_vs[tree_sitter] shape / Claim 3) -- tree-sitter is fully blind there, and ctags additionally has no concept of a local/nested function at all (only top-level 'm' method tags), so GitGalaxy is the only tool that can see these. The remaining 2 are genuine GitGalaxy false positives with a confirmed, unrelated root cause: roslyn/CSharpCompilation.cs:2282's GetWellKnownType( (a call, no declaration exists anywhere in the file) and roslyn/LanguageParser.cs:2338's this.EatToken( (a call inside a switch-expression arm) are both mis-captured because func_start's return-type-loop character class allows unbalanced parens/commas in a single 'token', letting it swallow a real call-expression fragment as if it were part of a return type and land on the wrong identifier as the 'function name'. Filed as GitHub issue #2035 with root cause and fix direction; fix in progress in an isolated worktree as of this writing. Not crediting/debiting any tool on this shape since it's genuinely mixed (44 real local-function finds, 2 real false positives) -- re-visit once #2035 merges and re-run to confirm the shape drops to 44 (or fewer, if further false positives of the same class surface once #2035's fix generalizes across the full corpus). FOLLOW-UP (2026-08-21, post-#2035/#2036 re-verification): re-checked this shape with a full, uncapped corpus diff rather than the capped example sample. The 2 originally-confirmed false positives (GetWellKnownType, this.EatToken) are gone as expected. However 2 MORE confirmed false positives remain, distinct mechanisms from #2035's fix: CSharpCompilation.cs's `ref mdName, ..., CreateReflectionTypeNotFoundError(` (a real call site mistaken for a declaration because `ref` is a legitimate Branch A modifier keyword when used in a real declaration, but here it's a call-argument prefix) and LanguageParser.cs:2336's `_syntaxFactory.TypeConstraint(this.ParseType())` (a ternary `?` operator consumed by the return-type loop's nullable-type-marker allowance, same general shape as this.EatToken but not covered by #2035's specific fix). Filed as issue #2054. This shape remains genuinely mixed (the overwhelming majority are real cascade-region local functions, but a small residual of false positives keeps surfacing) -- still correctly left uncredited pending #2054. CLOSED (2026-08-21): this shape is now fully clean. Both remaining false-positive mechanisms (issue #2054: bare-comma call-argument absorption, ternary-? consumption, and the nested-generic-return-type regression its own fix introduced and #2061 corrected) are fixed and merged. A full uncapped re-diff confirms all 44 remaining occurrences are genuine local functions inside LanguageParser.cs's tree-sitter parse-error cascade region (Claim 3), zero non-cascade residue. credit_tools is now correctly applicable -- gitgalaxy is alone on this shape (no tool to share the credit-double-counting error this session already found and fixed on the sibling agree[ctags,gitgalaxy]/agree[gitgalaxy,tree_sitter] shapes with), and every one of its 44 claims here is confirmed real with the reason ctags (no local-function concept) and tree-sitter (parse cascade) don't corroborate it being a confirmed limitation in THEM, not an open question about GitGalaxy.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `parsePrimaryExpressionWithoutPostfix` | 11940 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parsePostFixExpression` | 12115 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `canFollowNullableType` | 7719 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ParseCommaSeparatedSyntaxList` | 14422 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ParseCommaSeparatedSyntaxList` | 14444 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `tryExpandExpression` | 11546 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `tokenBreaksTypeArgumentList` | 6626 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseCallingConvention` | 8100 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseSwitchHeader` | 10175 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseUnaryOrPrimaryExpression` | 11452 | *(n/a)* | *(n/a)* |

### ✅ `csharp` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 9 occurrences as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T18:13:27Z):
> Same root cause and file as the sibling function-existence shape (roslyn/LanguageParser.cs's tree-sitter parse-error cascade from line ~5198, Claim 3 in why_gitgalaxy_beats_ast_here.md, #1427/#1567) -- with the parse tree corrupted into a single ERROR node, tree-sitter can't resolve any class_declaration structure in the corrupted region either, including the outer LanguageParser class itself (whose body spans the entire cascade) and every enum/nested class declared inside it (VariableFlags, NameOptions, ScanTypeArgumentListKind, ScanTypeFlags, ParseTypeMode, etc.). ctags and GitGalaxy both correctly find these via text-based parsing, unaffected by tree-sitter's own AST failure. Not a GitGalaxy or ctags defect. CORRECTION (2026-08-21): credit_tools was originally set here, but this is wrong -- these tools already mutually corroborate each other (2-of-3 agreement), so their occurrences were already counted in base precision before any credit was applied. Adding credit on top double-counted them, pushing gitgalaxy's func_precision matched_consensus past its own total_slots (1297/965, >100%, a real, visible chart-rendering bug). credit_tools is only valid for a shape where a tool is completely ALONE and otherwise uncorroborated (e.g. this language's agree[gitgalaxy]_vs[ctags,tree_sitter] shape), never for an already-mutually-agreeing pair. Reset to empty; the validation itself (which tool is factually correct here) is unaffected and remains correct.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `LanguageParser` | *(n/a)* | *(n/a)* | 20 |
| roslyn/LanguageParser.cs | `VariableFlags` | *(n/a)* | *(n/a)* | 5379 |
| roslyn/LanguageParser.cs | `NameOptions` | *(n/a)* | *(n/a)* | 5997 |
| roslyn/LanguageParser.cs | `ScanTypeArgumentListKind` | *(n/a)* | *(n/a)* | 6228 |
| roslyn/LanguageParser.cs | `ScanTypeFlags` | *(n/a)* | *(n/a)* | 7115 |
| roslyn/LanguageParser.cs | `ParseTypeMode` | *(n/a)* | *(n/a)* | 7565 |
| roslyn/LanguageParser.cs | `Precedence` | *(n/a)* | *(n/a)* | 11187 |
| roslyn/LanguageParser.cs | `DisposableResetPoint` | *(n/a)* | *(n/a)* | 14575 |
| roslyn/LanguageParser.cs | `ResetPoint` | *(n/a)* | *(n/a)* | 14600 |

### ✅ `csharp` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 7 occurrences as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T20:06:45Z):
> Confirmed GitGalaxy defect for 6 of 7 occurrences, root-caused to 3 distinct mechanisms in the csharp args regex, none of which func_start's own (already-hardened) regex shares: (1) Branch 1's return-type-loop character class has no parens, so any tuple-shaped or generic-wrapped-tuple return type fails to match at all (HasEntryPointSignature: real=2, GitGalaxy=0; SetCurrentSolutionEx: real=1, GitGalaxy=2; SetCurrentSolutionAsync both overloads: real=6/GitGalaxy=2, real=7/GitGalaxy=0); (2) the shared args capture group `(\([^)]*\))` truncates at the first unbalanced `)`, breaking on any parameter whose own type contains parens (ProcessEventHandlerWorkQueueAsync's ImmutableSegmentedList<(tuple)> param: real=2, GitGalaxy=1); (3) the name-capture has no generic-type-parameter stepper (func_start's already does), so a generic method's <T> before the real parens fails to match (OnAnyDocumentTextChanged<TArg>: real=7, GitGalaxy=2; ScheduleTask<T>: real=2, GitGalaxy=1). Filed as issue #2051 with full evidence per mechanism. The 7th occurrence (GetModifierExcludingScoped) is NOT a real defect on either side: both of its overloads (1 param and 2 params) are correctly counted by GitGalaxy; the apparent ctags=2/gitgalaxy=1 mismatch is the reconciler's rank-based (not name/overload-based) pairing comparing two DIFFERENT real overloads against each other, not a genuine disagreement about the same declaration -- confirmed by reading both real declarations directly. No credit/debit: GitGalaxy is genuinely wrong on 6/7, and the reconciler-pairing noise on the 7th isn't a tool defect at all.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `HasEntryPointSignature` | 0 | 2 | 2 |
| roslyn/Workspace.cs | `SetCurrentSolutionAsync` | 2 | 6 | 6 |
| roslyn/Workspace.cs | `SetCurrentSolutionAsync` | 0 | 7 | 7 |
| roslyn/Workspace.cs | `OnAnyDocumentTextChanged` | 2 | 7 | 7 |
| roslyn/Workspace.cs | `ScheduleTask` | 1 | 2 | 2 |
| roslyn/Workspace.cs | `SetCurrentSolutionEx` | 2 | 1 | 1 |
| roslyn/Workspace.cs | `ProcessEventHandlerWorkQueueAsync` | 1 | 2 | 2 |

### ✅ `csharp` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T20:06:45Z):
> Mixed shape. 1 of 4 is a confirmed genuine ctags defect: GetHashCode's tuple-parameter overload (`GetHashCode((ImmutableArray<byte> ContentHash, int Position) obj)`, 1 real param) -- ctags reports 2, mis-splitting the tuple-typed parameter's own internal comma as a second top-level parameter, the same family as the already-documented tuple-related ctags limitations in tests/tools/ctags_reader.py's csharp bullet. The other 3 (GetModifierExcludingScoped and two SetCurrentSolution rows) are NOT real tool disagreements at all -- SetCurrentSolution has 4 real overloads (1/6/4/5 real params respectively) in roslyn/Workspace.cs; every individual reading from every tool across both rows (ctags=6, gitgalaxy=1, tree_sitter=1, ctags=4, gitgalaxy=6, tree_sitter=6) independently matches SOME real overload's true count exactly when checked against the source -- the ledger shape only exists because the reconciler's rank-based pairing compared different tools' readings of DIFFERENT overloads against each other, not because any tool actually miscounted anything. Confirmed via direct line-by-line source reading of all 4 overloads. Credit gitgalaxy+tree_sitter for the 1 real ctags defect only; the shape as a whole is left without a clean credit/debit since 3 of 4 occurrences aren't a real disagreement to adjudicate.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `GetHashCode` | 1 | 1 | 2 |
| roslyn/LanguageParser.cs | `GetModifierExcludingScoped` | 1 | 1 | 2 |
| roslyn/Workspace.cs | `SetCurrentSolution` | 1 | 1 | 6 |
| roslyn/Workspace.cs | `SetCurrentSolution` | 6 | 6 | 4 |

### ✅ `csharp` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T20:06:45Z):
> Confirmed: both ctags and GitGalaxy are wrong here, tree-sitter alone is right. roslyn/CSharpCompilation.cs:2539's `Equals((ImmutableArray<byte> ContentHash, int Position) x, (ImmutableArray<byte> ContentHash, int Position) y)` has 2 real parameters (both tuple-typed); tree_sitter correctly reports 2. GitGalaxy's args capture group truncates at the first unbalanced `)` inside the first tuple parameter's own type, reporting 1 (mechanism 2 of issue #2051, confirmed via direct regex testing). ctags independently also reports 1, for its own unrelated reason (the same tuple-parameter-splitting limitation documented elsewhere in this file for GetHashCode/Equals-with-bool-tuple-param) -- both tools land on the identical wrong number by coincidence, not real corroboration of each other.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `Equals` | 1 | 2 | 1 |

### ✅ `csharp` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T18:13:27Z):
> Confirmed genuine ctags false positive, not a GitGalaxy or tree-sitter gap. roslyn/CSharpCompilation.cs:2539's real declaration is `public bool Equals((ImmutableArray<byte> ContentHash, int Position) x, (ImmutableArray<byte> ContentHash, int Position) y)` -- an Equals overload with tuple-typed parameters. ctags' lightweight C# parser misreads the return-type/tuple-parameter boundary and tags the match under the name `bool` instead of `Equals`. Documented in tests/tools/ctags_reader.py's csharp KIND MAPS bullet alongside this shape's sibling ctags limitations (local-function blindness, complex-signature misses, overload-name collision -- see the agree[gitgalaxy,tree_sitter]_vs[ctags] shape). Not crediting/debiting: a single-tool false positive from an otherwise-unaffected precision baseline, no shared-mistake mechanism applies.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `bool` | *(n/a)* | *(n/a)* | 2539 |

### ✅ `csharp` function args: none agree, GitGalaxy, tree-sitter, ctags differ

*3-way split -- 1 occurrence as of 2026-08-22T22:19:11Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T20:06:45Z):
> Tangled: partly the same reconciler rank-pairing artifact as the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] shape (SetCurrentSolution's 4 real overloads, 1/6/4/5 params), partly a genuine GitGalaxy defect underneath. ctags=5 and tree_sitter=4 each correctly match a DIFFERENT real overload's true count (line 444's 5 params, line 230's 4 params respectively) -- not wrong, just paired against each other by rank rather than by which declaration they actually read. GitGalaxy=0 traces to the SAME occurrence tree_sitter's 4 reading corresponds to (line 230, a bare tuple return type `(bool updated, Solution newSolution)` before the method name) -- a confirmed instance of issue #2051's mechanism 1 (GitGalaxy's args regex fails to match tuple return types at all). No credit/debit: too tangled between real defect and pairing noise to cleanly adjudicate at the shape level.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/Workspace.cs | `SetCurrentSolution` | 0 | 4 | 5 |

## css

### ✅ `css` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-22T22:19:12Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed ctags-side structural limitation, not a GitGalaxy defect. GitGalaxy's own func_start regex (language_standards.py) deliberately matches CSS at-rule keywords (@media/@supports/@container/@layer/@keyframes/@-webkit-keyframes) as the closest function-shaped construct CSS has, since CSS has no true function-definition/call syntax. tree-sitter's CSS grammar independently corroborates this: media_statement/supports_statement/keyframes_statement are real, distinct node types, already mapped 1:1 onto GitGalaxy's own at-rule set per issue #1313 (see tree_sitter_accuracy_audit.py's css NODE_MAPS entry and its media_statement/supports_statement name-extraction branches). Re-ran gather_language('css') directly against the full 4-file corpus (not just the ledger's capped 3-example sample): GitGalaxy and tree-sitter agree exactly on function count in every file (3/3 total, zero diff files) -- the agreement generalizes completely, it is not a partial/mixed sample. ctags' own FUNCTION_KIND_MAP already documents 'css': set()  # no function-equivalent (ctags_reader.py) -- confirmed empty (ctags_funcs: []) across all 4 corpus files too. ctags structurally cannot tag CSS at-rules as anything function-like; it isn't wrong about a claim, it has no claim to make here at all. No new doc note needed -- both the GitGalaxy/tree-sitter convention (#1313) and the ctags limitation are already documented in code. GitGalaxy+tree-sitter's agreement is real corroboration, not a shared mistake, so no credit/debit adjustment applies; ctags' lack of a comparable slot here is already handled correctly by the reconciler's own total_slots mechanics.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| element/common.css | `media` | 153 | 153 | *(n/a)* |
| element/common.css | `media` | 160 | 160 | *(n/a)* |
| odoo/control_panel_mobile.css | `media` | 1 | 1 | *(n/a)* |

## dart

### ✅ `dart` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 13 occurrences as of 2026-08-22T22:19:15Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real GitGalaxy engine defect, not a tree-sitter limitation. Root-caused two distinct false-positive bugs in dart's func_start regex's zero-prefix branch, both in gitgalaxy/standards/language_standards.py: (1) Dart 3 switch-expression arms (`Pattern => result,` including bare `_ => result,`) matched as getter definitions, because the branch's bare-`=>` lookahead alternative was unconditional (no `get` keyword required) even though Dart's real grammar has no parameterless `=> expr` construct without `get`. (2) Call statements with a lambda argument (`obj.method((x) => ...)`, `setState(() {...})`, bare self-calls like `visitChildren((Element child) {...})`) matched as function definitions, because the paren-lookahead used a naive non-balanced-paren check (`\([^)]*\)`) that stopped at the lambda's own closing paren instead of the outer call's. A full corpus-wide before/after diff (language-crucible/data/dart, 7 Flutter framework files) confirmed 126 false-positive matches removed and only 1 new match gained (a genuine recall fix for EditableText's own multi-line constructor) -- every one of the 126 manually spot-checked as a real false positive (dotted call receiver, or a statement ending `);`, or a switch-expression arm), none a lost real definition. Fixed in gitgalaxy#2071 (merged via this ledger-sweep PR) by gating the bare-arrow alternative behind the existing `get`-group conditional and switching to the same balanced-paren pattern already used elsewhere in this regex. A smaller, related false positive (multi-line class headers with with/implements clauses absorbed as a phantom function's return-type prefix, e.g. `implements AutofillClient {` matching as a function named AutofillClient) was found in the same investigation but is NOT fixed -- the straightforward fix (excluding implements/with/extends from the return-type-prefix vocabulary) was tested and confirmed to break a much more common legitimate pattern, generic method type-parameter bounds (`static Future<T?> pushNamed<T extends Object?>(...)`), which also uses `extends`. Tracked in gitgalaxy#2072 along with several other confirmed-but-deferred recall gaps found in the same pass.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| flutter/editable_text.dart | `AutofillClient` | 2483 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `_scrollableNotificationIsFromSameSubtree` | 4173 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `TextStyle` | 315 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `TextInput.attach` | 4047 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `_CodePointBoundary` | 6303 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `_documentBoundary` | 5331 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `_documentBoundary` | 5333 | *(n/a)* | *(n/a)* |
| flutter/navigator.dart | `_RestorationInformation.anonymous` | 5970 | *(n/a)* | *(n/a)* |
| flutter/navigator.dart | `_RestorationInformation.named` | 5965 | *(n/a)* | *(n/a)* |
| flutter/object.dart | `RenderObject` | 4366 | *(n/a)* | *(n/a)* |

### ✅ `dart` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 10 occurrences as of 2026-08-22T22:19:15Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real GitGalaxy recall gaps (tree-sitter is correct), several distinct causes found via direct source investigation against language-crucible/data/dart. Some entries in this shape's original capped example list were incidentally resolved as a side effect of the func_start fix in gitgalaxy#2071 (e.g. EditableText's own multi-line constructor, generic-return-type getters like `Iterable<Element> get children =>`, and dotted-name getters like `T? get currentState => switch (...) {...}` all now regex-match correctly and reach the final pipeline output). A post-fix full-corpus name-diff still shows 12 residual missing_from_gg cases across 5 distinct confirmed root causes, none yet fixed: (1) EditableText's constructor and a private named constructor (_DiscreteKeyFrameSimulation._(...)) regex-match (confirmed via direct probe) but don't reach the final pipeline output -- a detector.py-level extraction bug downstream of the regex, not yet traced; (2) static getters with a dotted/prefixed-import return type (`static ui.BoxHeightStyle get defaultSelectionHeightStyle {`) never regex-match at all, because the return-type-prefix character class excludes `.`; (3) bodyless default constructors (`_EditableTextTapOutsideAction();`) don't regex-match; (4-5) several more names (recorder, ChildSemanticsConfigurationsResultBuilder, OrdinalSortKey, SemanticsData, SemanticsProperties, extension) not yet individually root-caused. All tracked as a consolidated follow-up in gitgalaxy#2072 -- deliberately not rushed, since the sibling existence shape's investigation already found one naive fix (broadening the return-type charclass or the keyword-exclusion list) can silently break a much more common legitimate pattern elsewhere, so each of these needs its own regression check before shipping.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| flutter/editable_text.dart | `_characterBoundary` | *(n/a)* | 5326 | *(n/a)* |
| flutter/editable_text.dart | `_nextWordBoundary` | *(n/a)* | 5328 | *(n/a)* |
| flutter/editable_text.dart | `_linebreak` | *(n/a)* | 5330 | *(n/a)* |
| flutter/editable_text.dart | `_EditableTextTapOutsideAction` | *(n/a)* | 6706 | *(n/a)* |
| flutter/editable_text.dart | `_EditableTextTapUpOutsideAction` | *(n/a)* | 6739 | *(n/a)* |
| flutter/framework.dart | `findAncestorStateOfType` | *(n/a)* | 5132 | *(n/a)* |
| flutter/framework.dart | `findRootAncestorStateOfType` | *(n/a)* | 5146 | *(n/a)* |
| flutter/semantics.dart | `ChildSemanticsConfigurationsResultBuilder` | *(n/a)* | 658 | *(n/a)* |
| flutter/semantics.dart | `OrdinalSortKey` | *(n/a)* | 7027 | *(n/a)* |
| flutter/theme_data.dart | `extension` | *(n/a)* | 993 | *(n/a)* |

### ✅ `dart` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 221 occurrences as of 2026-08-22T22:19:15Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real GitGalaxy defect on args counts for class/constructor names, root cause distinct from (but likely overlapping with) the func_start existence bugs fixed in gitgalaxy#2071. Spot-checked via language-crucible/data/dart, e.g. flutter/editable_text.dart's `_DeleteTextAction` class (`class _DeleteTextAction<T extends DirectionalTextEditingIntent> extends ContextAction<T> {` at line 6352, real constructor `_DeleteTextAction(this.state, this.getTextBoundary, this._applyTextBoundary);` at line 6353 taking 3 args) -- tree-sitter correctly reports args=3 for the constructor, GitGalaxy reports args=0, most likely because GitGalaxy's func_start is matching the class declaration header itself under the same name (no explicit `(...)` immediately after the class name, since it's followed by `<T extends ...>` then `extends ContextAction<T> {`) rather than the real constructor line. This looks like the same underlying class-header-vs-function-signature ambiguity as gitgalaxy#2072 item 1 (multi-line class headers with generic type-parameter bounds), not yet isolated or fixed -- a full re-diff after this ledger sweep's existence fix still shows 302 name-matched args disagreements, most following this same class/constructor-name shape. Deliberately not fixed in this pass: root-causing exactly which of the func_start branches is misattributing these needs its own investigation with the same regression discipline the existence fix required (a naive class-header exclusion already proved unsafe once in this same investigation). Tracked as a named follow-up under gitgalaxy#2072's scope.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| flutter/editable_text.dart | `EditableText` | 1 | 76 | *(n/a)* |
| flutter/editable_text.dart | `build` | 2 | 3 | *(n/a)* |
| flutter/editable_text.dart | `_inferKeyboardType` | 1 | 2 | *(n/a)* |
| flutter/editable_text.dart | `getEditableButtonItems` | 1 | 9 | *(n/a)* |
| flutter/editable_text.dart | `buildTextSpan` | 1 | 3 | *(n/a)* |
| flutter/editable_text.dart | `textInputConfiguration` | 3 | 0 | *(n/a)* |
| flutter/editable_text.dart | `_Editable` | 1 | 39 | *(n/a)* |
| flutter/editable_text.dart | `applyTextSpacingOverrides` | 1 | 4 | *(n/a)* |
| flutter/editable_text.dart | `_CodePointBoundary` | 1 | 0 | *(n/a)* |
| flutter/editable_text.dart | `ContentInsertionConfiguration` | 1 | 2 | *(n/a)* |

## fortran

### ❓ `fortran` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:20Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_physics_init.F | `phy_init` | 677 | 39 | 677 |

### ✅ `fortran` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 15 occurrences as of 2026-08-22T22:19:20Z*

**Verdict** (by Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T23:35:49Z):
> Confirmed already-documented tree-sitter-fortran limitation (#1709/Claim 7 in docs/why_gitgalaxy_beats_ast_here.md), re-verified directly against this exact shape's 14 occurrences (11 in wrf/module_physics_init.F: bl_init, ra_init, landuse_init, mp_init, cu_init, shcu_init, CAM_INIT, z2sigma, fdob_init, fg_init, ALLOCATE_CAM_ARRAYS; 3 in wrf/wrf_timeseries.F: calc_p8w, calc_ts, write_ts). Directly ran tree_sitter_accuracy_audit.py's own _find_blind_spot_ranges() against both files' real parse trees: every one of the 14 occurrences' start lines falls inside a tree-sitter ERROR/preproc_* blind-spot range (e.g. bl_init/mp_init/cu_init/shcu_init all sit inside one continuous (2203,4393) span; all 3 wrf_timeseries.F occurrences fall inside a (1,1200) span). ctags and GitGalaxy are both correct; tree-sitter-fortran's own grammar cascades into ERROR nodes on the CPP #if/#endif guards surrounding these subroutines. Added as new evidence to the existing Claim 7 in docs/why_gitgalaxy_beats_ast_here.md (this ledger shape is independently sourced from the original accuracy-audit finding -- a raw per-file name diff via tri_comparison_gatherer.py, not the audit tool's promotion logic).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_initialize_real.F | `foo` | 7519 | *(n/a)* | 7519 |
| wrf/module_physics_init.F | `bl_init` | 2461 | *(n/a)* | 2461 |
| wrf/module_physics_init.F | `mp_init` | 4365 | *(n/a)* | 4365 |
| wrf/module_physics_init.F | `ra_init` | 2033 | *(n/a)* | 2033 |
| wrf/module_physics_init.F | `landuse_init` | 1745 | *(n/a)* | 1745 |
| wrf/module_physics_init.F | `cu_init` | 3923 | *(n/a)* | 3923 |
| wrf/module_physics_init.F | `shcu_init` | 4217 | *(n/a)* | 4217 |
| wrf/module_physics_init.F | `CAM_INIT` | 5038 | *(n/a)* | 5038 |
| wrf/module_physics_init.F | `z2sigma` | 4965 | *(n/a)* | 4965 |
| wrf/module_physics_init.F | `fg_init` | 4700 | *(n/a)* | 4700 |

### ✅ `fortran` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:20Z*

**Verdict** (by Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T23:35:49Z):
> Confirmed GitGalaxy correct on both. 'vint' (module_initialize_real.F:5375, inside #ifdef VERT_UNIT) and 'foo' (module_initialize_real.F:7519, inside #if 0) are both real, syntactically valid `PROGRAM name` declarations. tree-sitter misses both via the already-documented #1709 ERROR/preproc_* blind-spot mechanism (both sit inside #if/#ifdef-guarded regions). ctags misses 'foo' only because CTAGS_FUNC_KINDS['fortran'] was {'f','s'} (functions/subroutines only) -- ctags itself DOES correctly tag `foo` as a 'p' (program) kind (confirmed via `ctags -x --kinds-Fortran=p`), just invisible to this comparison. Fixed in tests/tools/ctags_reader.py: CTAGS_FUNC_KINDS['fortran'] now {'f','s','p','e'} (added program, entry -- matching GitGalaxy's own func_start scope of FUNCTION|SUBROUTINE|PROGRAM|ENTRY). ctags separately, genuinely fails to tag 'vint' at all under any kind in this specific file (confirmed it tags an isolated test file with identical #ifdef-wrapped `program vint` syntax fine, so it's a real, unexplained ctags-fortran-parser corruption specific to this file's content, not a preprocessor-conditional-skip decision) -- a genuine, narrow ctags limitation, not chased further for a single occurrence.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_initialize_real.F | `vint` | 5375 | *(n/a)* | *(n/a)* |

## go

### ❓ `go` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 75 occurrences as of 2026-08-22T22:19:22Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`go/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/main.go | `makePos` | 3 | 2 | 3 |
| core/proc.go | `sigprof` | 5 | 3 | 5 |
| core/proc.go | `casgstatus` | 3 | 2 | 3 |
| core/proc.go | `reentersyscall` | 3 | 1 | 3 |
| core/proc.go | `startm` | 3 | 2 | 3 |
| core/proc.go | `runqputslow` | 4 | 3 | 4 |
| core/proc.go | `casfrom_Gscanstatus` | 3 | 2 | 3 |
| core/proc.go | `castogscanstatus` | 3 | 2 | 3 |
| core/proc.go | `casGFromPreempted` | 3 | 2 | 3 |
| core/proc.go | `save` | 3 | 1 | 3 |

## haskell

### ✅ `haskell` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 103 occurrences as of 2026-08-22T22:19:23Z*

**Verdict** (by Claude Sonnet 5 (dispatched agent investigation), 2026-08-19T00:00:00Z):
> All 10 sampled cases are ctags-side artifacts, not real GitGalaxy/tree-sitter misses -- confirmed via direct `ctags -x` output against the corpus. Three distinct ctags Haskell-parser weaknesses cover the sample: (1) multi-clause double/triple-tagging -- ctags tags every pattern-matched equation line as its own occurrence of the name (writerFn/writeFnBinary/expandFilterPath: confirmed 2-3 raw ctags tags per function, one per clause; a file-wide count found 45 such extra same-name tags across the 7-file corpus, e.g. blockToInlines alone has 14). GitGalaxy/tree-sitter both correctly anchor to the FIRST clause only, leaving ctags' later-clause tags as the ones unpaired. (2) keyword-as-identifier misparsing -- `class`/`where`/`pattern` (from PatternSynonyms) get tagged as function names when ctags fails to parse past the keyword; confirmed at Options.hs:62 (`class HasSyntaxExtensions`), Parsing.hs:184 (module-header `where`), and 3 PatternSynonyms declarations in Options.hs. (3) CAF/value-vs-function kind collapse -- defaultAbbrevs/defaultKaTeXURL/defaultMathJaxURL/defaultWebTeXURL are zero-arg top-level VALUES (non-arrow type signatures), not functions; ctags has no value/variable kind at all (`ctags --list-kinds-full=Haskell` shows only constructor/function/module/type) so it lumps every `name = expr` binding into "function". GitGalaxy (language_standards.py haskell rules, #1312) and tree-sitter's own audit tooling (_find_haskell_signature_for_bind, #1566) both independently make the same value-vs-function distinction correctly -- real cross-tool corroboration, not coincidence. (4) TH-splice call sites misread as definitions -- deriveJSON at Options.hs:454/458 is a Template Haskell splice INVOKING an imported function, not defining one; ctags misparses the call as a definition. No GitGalaxy/tree-sitter defect anywhere in this shape; purely a ctags parser limitation, same category as the already-documented empty CTAGS_CLASS_KINDS['haskell'].

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/App.hs | `writerFn` | *(n/a)* | *(n/a)* | 426 |
| pandoc/App.hs | `writeFnBinary` | *(n/a)* | *(n/a)* | 422 |
| pandoc/Filter.hs | `expandFilterPath` | *(n/a)* | *(n/a)* | 106 |
| pandoc/Filter.hs | `expandFilterPath` | *(n/a)* | *(n/a)* | 107 |
| pandoc/Options.hs | `class` | *(n/a)* | *(n/a)* | 62 |
| pandoc/Options.hs | `defaultAbbrevs` | *(n/a)* | *(n/a)* | 96 |
| pandoc/Options.hs | `defaultKaTeXURL` | *(n/a)* | *(n/a)* | 451 |
| pandoc/Options.hs | `defaultMathJaxURL` | *(n/a)* | *(n/a)* | 445 |
| pandoc/Options.hs | `defaultWebTeXURL` | *(n/a)* | *(n/a)* | 448 |
| pandoc/Options.hs | `deriveJSON` | *(n/a)* | *(n/a)* | 454 |

### ✅ `haskell` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 69 occurrences as of 2026-08-22T22:19:23Z*

**Verdict** (by Claude Sonnet 5 (dispatched agent investigation), 2026-08-19T00:00:00Z):
> Confirmed: all 10 sampled misses (and, by cross-check against additional non-sampled instances in Options.hs/Shared.hs, plausibly all 69) are locally-scoped function definitions -- `instance ... where` methods, `where`-clause helpers, or `let`-bound names inside `do` blocks -- never top-level module definitions. ctags' Haskell parser has no layout-rule/scope awareness and only tags equations anchored at column 1; it correctly handles multi-clause TOP-LEVEL definitions (verified via expandFilterPath, writeFnBinary, writerFn -- all tag fine, clauses and all), so this is a pure scope blind spot, not a clause-counting bug (distinct from the tree-sitter clause-splitting bug fixed earlier in this same effort, which shares 2 of the 10 sample names by coincidence of subject matter, not root cause). GitGalaxy and tree-sitter are both correct; ctags is not wrong so much as structurally incapable of seeing these. Known, expected limitation of ctags' Haskell parser, now documented alongside its existing Haskell notes in tests/tools/ctags_reader.py -- not a GitHub issue, nothing in this repo to fix.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/App.hs | `ensureNl` | 329 | 329 | *(n/a)* |
| pandoc/App.hs | `makeSandboxed` | 165 | 165 | *(n/a)* |
| pandoc/App.hs | `isWarning` | 114 | 114 | *(n/a)* |
| pandoc/App.hs | `defFlavor` | 152 | 152 | *(n/a)* |
| pandoc/App.hs | `isPandocCiteproc` | 270 | 270 | *(n/a)* |
| pandoc/Filter.hs | `parseJSON` | 47 | 47 | *(n/a)* |
| pandoc/Filter.hs | `withMessages` | 93 | 93 | *(n/a)* |
| pandoc/Filter.hs | `applyFilter` | 87 | 87 | *(n/a)* |
| pandoc/Filter.hs | `toJSON` | 69 | 69 | *(n/a)* |
| pandoc/Filter.hs | `filterWithPath` | 52 | 52 | *(n/a)* |

### ✅ `haskell` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 16 occurrences as of 2026-08-22T22:19:23Z*

**Verdict** (by Claude Sonnet 5 (session investigation), 2026-08-19T00:00:00Z):
> Not a real discrepancy -- structural tooling gap, already documented in the codebase. tests/tools/ctags_reader.py:39-40,228 sets CTAGS_CLASS_KINDS['haskell'] = set() on purpose: "ctags' Haskell parser has no class-shaped kind at all (constructor/function/module/type only)". Every example in this shape (data/newtype/class declarations -- ReaderOptions, CiteMethod, HasSyntaxExtensions, etc.) is real; ctags structurally cannot report any of them for this language, not a sample-specific miss. No action needed beyond this note.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/App.hs | `PandocOutput` | *(n/a)* | 344 | *(n/a)* |
| pandoc/Filter.hs | `Filter` | *(n/a)* | 41 | *(n/a)* |
| pandoc/Options.hs | `HasSyntaxExtensions` | *(n/a)* | 62 | *(n/a)* |
| pandoc/Options.hs | `ReaderOptions` | *(n/a)* | 65 | *(n/a)* |
| pandoc/Options.hs | `EPUBVersion` | *(n/a)* | 107 | *(n/a)* |
| pandoc/Options.hs | `HTMLMathMethod` | *(n/a)* | 109 | *(n/a)* |
| pandoc/Options.hs | `CiteMethod` | *(n/a)* | 157 | *(n/a)* |
| pandoc/Options.hs | `ObfuscationMethod` | *(n/a)* | 177 | *(n/a)* |
| pandoc/Options.hs | `HighlightMethod` | *(n/a)* | 196 | *(n/a)* |
| pandoc/Options.hs | `HTMLSlideVariant` | *(n/a)* | 233 | *(n/a)* |

### ✅ `haskell` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:23Z*

**Verdict** (by Claude Sonnet 5 (session investigation), 2026-08-19T00:00:00Z):
> Mixed shape as originally investigated (2 occurrences): (1) Options.hs:438 getExtensions -- real function, `instance HasSyntaxExtensions WriterOptions where getExtensions opts = writerExtensions opts`. A sibling instance for ReaderOptions at Options.hs:80 has the identical shape. Tree-sitter's Haskell grammar doesn't expose typeclass-instance-method clause bodies the way it does top-level bindings, and ctags' Haskell parser has no instance-method kind either -- GitGalaxy is correct, both other tools have a real recall gap on typeclass instance methods. (2) Shared.hs:475 extensionEnabled -- was NOT a real function (imported from Text.Pandoc.Extensions, only ever appears as a guard-clause call inside a multi-line `||` condition) -- a genuine GitGalaxy false positive, filed as #2082 and fixed in PR #2083 (2026-08-22): `_slice_by_indentation` now skips an equation-form func_start match whose immediately preceding line ends in `||`/`&&`. Reconciled post-fix: only the getExtensions occurrence remains, so this shape is now a clean, unambiguous GitGalaxy win -- credited accordingly.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/Options.hs | `getExtensions` | 438 | *(n/a)* | *(n/a)* |

### ✅ `haskell` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 9 occurrences as of 2026-08-22T22:19:23Z*

**Verdict** (by Claude Sonnet 5 (session investigation), 2026-08-19T00:00:00Z):
> One systematic cause, confirmed by reading source for 3 of the 9 (getMetadataFromFiles App.hs:395-397, splitTextByIndices Shared.hs:142-143, tabFilter Shared.hs:256-259) and consistent with the shape of the remaining 6. Every case is a point-free/eta-reduced Haskell equation: the type signature declares N params, but the specific clause GitGalaxy and tree-sitter both align to only explicitly binds N-1 of them, handling the trailing argument via composition (`.`) or `\case`. GitGalaxy counts arity from the full type signature (the true logical arity); tree-sitter's declaration-only reading counts only the clause's explicitly-bound patterns (correct for that one equation, but undercounts true arity). Neither reader is wrong about what it's measuring -- same shape as Claim 1 in docs/why_gitgalaxy_beats_ast_here.md. GitGalaxy's answer is arguably the more useful coupling signal; recommend documenting as a candidate Claim rather than treating as an engine defect to fix toward matching tree-sitter.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/App.hs | `getMetadataFromFiles` | 3 | 2 | *(n/a)* |
| pandoc/App.hs | `writerFn` | 3 | 2 | *(n/a)* |
| pandoc/App.hs | `writeFnBinary` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `textToIdentifier` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `tabFilter` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `inlineListToIdentifier` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `formatCode` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `splitTextByIndices` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `blocksToInlinesWithSep` | 2 | 1 | *(n/a)* |

## javascript

### ✅ `javascript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 265 occurrences as of 2026-08-22T22:19:28Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed ctags-side parser limitation, not a GitGalaxy or tree-sitter defect. ctags' JavaScript scanner loses the real property-key name for a function-valued object-literal property specifically when that literal is a CALL ARGUMENT rather than a direct assignment -- confirmed via jquery/ajax.js's `jQuery.extend(jQuery, {ajaxSetup: function(target, settings){...}, ajax: function(url, options){...}})`: ctags emits a synthetic 'AnonymousFunction<hex>' tag for both instead of using the real 'ajaxSetup'/'ajax' key text, while GitGalaxy and tree-sitter both correctly attribute the property key as the name. Generalizes across the whole corpus, not a one-file fluke -- the identical shape recurs in jquery/css.js (css/get/set/style), jquery/deferred.js (Deferred/catch/pipe/promise/then/when), jquery/event.js (Event/handler/off/one/postDispatch/set), jquery/core.js (20+ utility methods, reducing ctags' whole-file function count from 26 to 1), and threejs's Editor.js/GLTFLoader.js/WebGLRenderer.js/WebGLProgram.js. Doc note added to ctags_reader.py's javascript CTAGS_FUNC_KINDS entry.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `ajax` | 383 | 383 | *(n/a)* |
| jquery/ajax.js | `ajaxSetup` | 369 | 369 | *(n/a)* |
| jquery/ajax.js | `getJSON` | 848 | 848 | *(n/a)* |
| jquery/ajax.js | `getScript` | 852 | 852 | *(n/a)* |
| jquery/core.js | `extend` | 115 | 115 | *(n/a)* |
| jquery/core.js | `each` | 70 | 70 | *(n/a)* |
| jquery/core.js | `each` | 237 | 237 | *(n/a)* |
| jquery/core.js | `map` | 74 | 74 | *(n/a)* |
| jquery/core.js | `map` | 370 | 370 | *(n/a)* |
| jquery/core.js | `text` | 260 | 260 | *(n/a)* |

### ✅ `javascript` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 183 occurrences as of 2026-08-22T22:19:28Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed GitGalaxy correct; both ctags and tree-sitter structurally can't, for two INDEPENDENT reasons. All four affected react/*.js corpus files carry the `@flow` pragma. tree-sitter-javascript's grammar can't parse Flow's parenthesized type-cast syntax (`(expr: Type)`, e.g. `(workInProgress.child: any)`), producing an ERROR node that swallows a large trailing region of the file -- confirmed directly: ReactFiberBeginWork.js's ERROR spans lines 3221-4448 (1227 of 4448 lines), and ReactFiberWorkLoop.js/ReactFlightServer.js each produce ONE error node spanning the ENTIRE file (line 1 to EOF). Real, ordinary functions inside these regions (beginWork, attemptEarlyBailoutIfNoScheduledUpdate, mountLazyComponent, and 18 others sampled) have no tree-sitter node at all. Separately, ctags' own hand-written JS scanner hits an independent cascade triggered by a Flow RETURN-type annotation (`): Fiber | null {`) -- confirmed via a minimal isolated repro (a 4-function test file where the function with a Flow return-type annotation and everything textually after it produce zero ctags output), and confirmed against the real corpus (beginWork itself, which has exactly this return-type shape, produces zero ctags tags). GitGalaxy's regex has no dependency on either tool's parse state and finds every one of these correctly. Documented in docs/why_gitgalaxy_beats_ast_here.md (Claim 3, new subsection completing/extending the existing 'Second instance: javascript' write-up with the recall-loss half plus the newly-confirmed ctags cascade).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| react/ReactFiberBeginWork.js | `beginWork` | 4164 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `attemptEarlyBailoutIfNoScheduledUpdate` | 3896 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `mountLazyComponent` | 2079 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `validateRevealOrder` | 3242 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `updateViewTransition` | 3569 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `validateTailOptions` | 3298 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `remountFiber` | 3806 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `updateHostComponent` | 1933 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `replayFunctionComponent` | 1533 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `bailoutOnAlreadyFinishedWork` | 3765 | *(n/a)* | *(n/a)* |

### ✅ `javascript` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 93 occurrences as of 2026-08-22T22:19:28Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed ctags-side parser limitation, not a GitGalaxy or tree-sitter defect. ctags' JavaScript scanner tags its 'class' kind on ANY bare object-literal assignment (`var X = {...}`) or function-expression assignment (`var X = function(){}`, `obj.prop = function(){}`), a blanket heuristic for 'might be used as a pre-ES6 constructor' that fires regardless of whether `new` is ever used on it. Confirmed via a minimal isolated repro (plainObj/ctorLike/obj.Thing all tagged 'class' alongside a real ES6 class) and directly against the corpus: jqXHR (jquery/ajax.js, a plain config object), cssHooks/cssNormalTransform/cssShow (jquery/css.js), promise (jquery/deferred.js), Event/event/special (jquery/event.js, one of which -- Event -- IS a pre-ES6 constructor-style function, correctly ambiguous under ctags' heuristic but still not a real ES6 class), and the ALPHA_MODES/WEBGL_CONSTANTS/etc. config objects in threejs/GLTFLoader.js. GitGalaxy's class_start regex and tree-sitter's class_declaration node both correctly require the literal `class` keyword. Doc note added to ctags_reader.py's javascript CTAGS_CLASS_KINDS entry.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `jqXHR` | *(n/a)* | *(n/a)* | 448 |
| jquery/css.js | `cssHooks` | *(n/a)* | *(n/a)* | 357 |
| jquery/css.js | `cssNormalTransform` | *(n/a)* | *(n/a)* | 22 |
| jquery/css.js | `cssShow` | *(n/a)* | *(n/a)* | 21 |
| jquery/deferred.js | `promise` | *(n/a)* | *(n/a)* | 58 |
| jquery/event.js | `Event` | *(n/a)* | *(n/a)* | 617 |
| jquery/event.js | `event` | *(n/a)* | *(n/a)* | 89 |
| jquery/event.js | `special` | *(n/a)* | *(n/a)* | 756 |
| jquery/event.js | `special` | *(n/a)* | *(n/a)* | 812 |
| react/ReactFiberBeginWork.js | `cachePool` | *(n/a)* | *(n/a)* | 2281 |

### ✅ `javascript` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 11 occurrences as of 2026-08-22T22:19:28Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed tree-sitter-alone recall gap, same Flow-cascade family as agree[gitgalaxy]_vs[ctags,tree_sitter] above but from the other side: for these specific names (updateContextProvider, reconcileChildren, updateScopeComponent, markWorkInProgressReceivedUpdate, shouldForceFlushFallbacksInDEV, patchConsole, abortIterable, abortStream, error, throwTaintViolation), ctags' own Flow-return-type cascade trigger point happens to sit AFTER these functions (or never fires in that file), so ctags finds them correctly and agrees with GitGalaxy at the exact same line number, while tree-sitter's independent (earlier-triggering, different-construct) ERROR cascade has already swallowed them. Because the two tools' cascades trigger on different Flow constructs starting at different lines, they lose different, non-identical sets of functions -- this is why the ledger shows several distinct 3-way shapes instead of one clean 'both non-GitGalaxy tools agree on what they missed' shape. Documented alongside the fuller write-up in docs/why_gitgalaxy_beats_ast_here.md's Claim 3 extension.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| react/ReactFiberBeginWork.js | `updateContextProvider` | 3658 | *(n/a)* | 3658 |
| react/ReactFiberBeginWork.js | `reconcileChildren` | 340 | *(n/a)* | 340 |
| react/ReactFiberBeginWork.js | `updateScopeComponent` | 3727 | *(n/a)* | 3727 |
| react/ReactFiberBeginWork.js | `markWorkInProgressReceivedUpdate` | 3739 | *(n/a)* | 3739 |
| react/ReactFiberWorkLoop.js | `shouldForceFlushFallbacksInDEV` | 5539 | *(n/a)* | 5539 |
| react/ReactFlightServer.js | `patchConsole` | 386 | *(n/a)* | 386 |
| react/ReactFlightServer.js | `abortIterable` | 1367 | *(n/a)* | 1367 |
| react/ReactFlightServer.js | `abortStream` | 1233 | *(n/a)* | 1233 |
| react/ReactFlightServer.js | `error` | 1222 | *(n/a)* | 1222 |
| react/ReactFlightServer.js | `throwTaintViolation` | 618 | *(n/a)* | 618 |

### ✅ `javascript` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 8 occurrences as of 2026-08-22T22:19:28Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed ctags-side synthetic-placeholder artifact, not a real discrepancy -- ctags' JavaScript scanner emits a synthetic 'AnonymousFunction<hex><seq>' tag for every genuinely anonymous function expression (a bare inline callback with no attributable name, e.g. `jQuery.ajaxPrefilter(function(s) {...})`), and GitGalaxy/tree-sitter both correctly agree these aren't named functions worth counting. Fixed by extending `tri_comparison_gatherer.py`'s existing `_is_ctags_synthetic_anon_name` (previously only matched the C-parser's `__anon<hex>` scheme) with a second regex for JavaScript's differently-shaped 'AnonymousFunction'/'AnonymousClass' scheme -- verified this removes every 'Anonymous*' entry across the full 18-file corpus with zero regressions (ruff/mypy audits clean).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `converters` | *(n/a)* | *(n/a)* | 764 |
| jquery/ajax.js | `jQuery` | *(n/a)* | *(n/a)* | 858 |
| jquery/deferred.js | `deferred` | *(n/a)* | *(n/a)* | 319 |
| react/ReactFlightServer.js | `[ASYNC_ITERATOR]` | *(n/a)* | *(n/a)* | 1616 |
| react/ReactFlightServer.js | `[Symbol.iterator]` | *(n/a)* | *(n/a)* | 1576 |
| threejs/GLTFLoader.js | `copy` | *(n/a)* | *(n/a)* | 3457 |
| threejs/GLTFLoader.js | `copy` | *(n/a)* | *(n/a)* | 3477 |
| threejs/GLTFLoader.js | `createInterpolant` | *(n/a)* | *(n/a)* | 4643 |

### ✅ `javascript` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-22T22:19:28Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed tree-sitter-alone argument-count corruption, a third facet of the same Flow-parsing family. Even where tree-sitter DOES still produce a real function_declaration node (outside any ERROR-swallowed region), a Flow parameter type with a union (`current: Fiber | null`) corrupts that node's own formal_parameters child list. Confirmed directly via react/ReactFiberBeginWork.js:405 `updateForwardRef(current: Fiber | null, workInProgress: Fiber, Component: any, nextProps: any, renderLanes: Lanes)` -- 5 real parameters (GitGalaxy=5, ctags=5, both correct) but tree-sitter's own formal_parameters node contains a single ERROR child swallowing 'current: Fiber | null,\n  workInProgress:' whole (merging two real parameters into one unstructured blob), followed by a bare identifier node reading 'Fiber' -- the type name of the swallowed second parameter, left behind by the same ERROR recovery and miscounted as if it were itself a parameter. Net effect: 4 instead of 5, an off-by-one undercount rather than total loss. Documented in docs/why_gitgalaxy_beats_ast_here.md's Claim 3 extension as the 'third facet.'

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| react/ReactFiberBeginWork.js | `updateForwardRef` | 5 | 4 | 5 |
| react/ReactFiberBeginWork.js | `updateContextConsumer` | 3 | 2 | 3 |
| react/ReactFiberWorkLoop.js | `addMarkerProgressCallbackToPendingTransition` | 3 | 2 | 3 |
| react/ReactFiberWorkLoop.js | `addMarkerIncompleteCallbackToPendingTransition` | 3 | 1 | 3 |
| react/ReactFiberWorkLoop.js | `addMarkerCompleteCallbackToPendingTransition` | 2 | 1 | 2 |
| react/ReactFlightServer.js | `progress` | 1 | 2 | 1 |
| react/ReactFlightServer.js | `wrapperMethod` | 1 | 0 | 1 |

### ✅ `javascript` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:19:28Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed comparison-methodology artifact (name-based reconciliation colliding on a reused property name), not a real defect in any of the three tools. jquery/event.js defines TWO separate object-literal properties both named 'setup' (line 441, taking 1 param `function(data)`) and 'trigger' (line 458, 1 param) inside one plugin-hook object, and a SECOND, unrelated pair of 'setup'/'trigger' properties (lines 759/774, taking 0 params) inside a different object later in the same file. This module's/the ledger's reconciliation pairs occurrences by NAME across the whole file, with no scope/position disambiguation, so a same-name collision between two genuinely different functions can produce a spurious per-name args mismatch depending on which occurrence each tool's internal ordering happens to surface first. Both readings (1 param and 0 params) are independently real and correct for their respective definition sites -- there is no actual counting defect here, just a reconciliation limitation inherent to comparing by name only. No credit/debit; no code fix warranted for 2 occurrences arising from a rare same-name collision.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/event.js | `setup` | 1 | 1 | 0 |
| jquery/event.js | `trigger` | 1 | 1 | 0 |

## kotlin

### ✅ `kotlin` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 15 occurrences as of 2026-08-22T22:19:29Z*

**Verdict** (by claude-sonnet-5, dispatched via tri-comparison-ledger-sweep (direct investigation, no Gemini dispatch -- small occurrence counts, answer was directly checkable), 2026-08-22T11:40:48Z):
> Confirmed ctags-side over-detection, not a GitGalaxy/tree-sitter recall gap. Direct `ctags -x --languages=Kotlin` on okhttp/Dispatcher.kt shows all 15 occurrences split into two false-positive shapes ctags' Kotlin parser tags with the same 'method' kind as real functions: (1) 10 trailing-lambda blocks passed as call arguments -- `require(x >= 1) { "..." }` (lines 48/68), `synchronized(this) { ... }` (49/69/178), `check(...) { ... }` (180/185), `.also { readyAsyncCalls.clear() }` (210), and `.map { it.call }` (279/283) -- each tagged as a synthetic `<lambda>` symbol; (2) 5 `for (x in collection)` loop iteration variables tagged as methods literally named after the variable (`call` at 143/146/149 in cancelAll(), `existingCall` at 128/131 in findExistingCallWithHost()). GitGalaxy's own func_start regex and tree-sitter-kotlin's grammar both correctly require a real `fun`/constructor declaration, so their agreement (neither claims these 15) is real corroboration, not a shared miss. Not fixable via ctags_reader.py's FUNCTION_KINDS map -- ctags gives Kotlin no separate kind for 'anonymous lambda literal' or 'for-loop binding' vs. a real named function in the first place (confirmed: both false-positive shapes tag plain 'method', identical to genuine functions). Documented in ctags_reader.py's kotlin FUNCTION_KINDS comment. ctags' own claim on this shape is confirmed wrong, so it's debited.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 48 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 49 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 68 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 69 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 178 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 180 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 185 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 210 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 279 |
| okhttp/Dispatcher.kt | `<lambda>` | *(n/a)* | *(n/a)* | 283 |

### ✅ `kotlin` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:29Z*

**Verdict** (by claude-sonnet-5, dispatched via tri-comparison-ledger-sweep (direct investigation, no Gemini dispatch), 2026-08-22T11:45:48Z):
> Direct continuation of the already-investigated constructor shape (see the now-still_reproduces=False agree[gitgalaxy]_vs[ctags,tree_sitter] entry's verdict for the full investigation): fixing tree_sitter_accuracy_audit.py's kotlin func_node_types to include `secondary_constructor` made tree-sitter agree with GitGalaxy on okhttp/Dispatcher.kt line 119's `constructor(executorService: ExecutorService?) : this() { ... }`, which regrouped this exact occurrence into a NEW 2-vs-1 shape. ctags' own Kotlin parser was independently confirmed (via `ctags -x --languages=Kotlin`) to emit no entry at all for line 119, under any kind -- a genuine ctags parser limitation (it doesn't recognize secondary-constructor syntax as a symbol in the first place), not a ctags_reader.py kind-mapping gap (there is nothing to remap; ctags never sees this construct as a taggable symbol). No credit/debit: ctags never claimed this occurrence at all (a miss, not a wrong claim), so there is nothing in its matched_consensus to debit, and gitgalaxy/tree_sitter's own claims were already correctly counted independent of this adjustment mechanism.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| okhttp/Dispatcher.kt | `constructor` | 119 | 119 | *(n/a)* |

## m4

### ✅ `m4` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 76 occurrences as of 2026-08-22T22:19:32Z*

**Verdict** (by gemini-3.1-pro-high (agy), dispatched via tri-comparison-ledger-sweep, reviewed by claude-sonnet-5, 2026-08-20):
> Clean, single-cause shape (all 10 sampled cases), not a GitGalaxy defect. Every sampled occurrence (curl/configure.ac lines 967-4994) is a real AC_DEFINE or AC_DEFINE_UNQUOTED call (e.g. line 2112: AC_DEFINE_UNQUOTED([CURL_DEFAULT_SSL_BACKEND], [...], [...])) -- an autoconf helper that emits a C preprocessor #define into the generated config.h at build time, NOT a new callable M4 macro definition. GitGalaxy's own func_start regex for m4 deliberately excludes AC_DEFINE/AC_DEFINE_UNQUOTED from its keyword set (m4_define|define|AC_DEFUN|AC_DEFUN_ONCE|AU_DEFUN|m4_defun only), so its silence here is correct. ctags' M4 parser heuristically tags any AC_DEFINE*-family call with a bracketed/plain first argument as a macro definition -- same macro-invocation-vs-definition confusion already documented for C's RICHCMP_WRAPPER pattern, now also documented in tests/tools/ctags_reader.py's m4 note. No GitHub issue against GitGalaxy -- this is a real, confirmed ctags-side limitation. (Separately, unrelated to this shape: a deeper live-pipeline recall gap causing GitGalaxy to extract only 1 m4 function total across the whole corpus, despite its func_start regex matching dozens of genuine AC_DEFUN/m4_define calls when run standalone, was found and fixed in part -- see PR #1927 for the func_start capture-group fix; the remaining pipeline-level gap is tracked separately, not part of this shape's verdict.) Investigated via gemini-3.1-pro-high (agy), all 10 sampled file:line citations independently verified.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| curl/configure.ac | `CURL_DEFAULT_SSL_BACKEND` | *(n/a)* | *(n/a)* | 2112 |
| curl/configure.ac | `CURL_DISABLE_CA_SEARCH` | *(n/a)* | *(n/a)* | 2183 |
| curl/configure.ac | `CURL_DISABLE_HSTS` | *(n/a)* | *(n/a)* | 4890 |
| curl/configure.ac | `CURL_DISABLE_LDAP` | *(n/a)* | *(n/a)* | 2629 |
| curl/configure.ac | `CURL_DISABLE_LDAP` | *(n/a)* | *(n/a)* | 2647 |
| curl/configure.ac | `CURL_DISABLE_LDAPS` | *(n/a)* | *(n/a)* | 2631 |
| curl/configure.ac | `CURL_DISABLE_LDAPS` | *(n/a)* | *(n/a)* | 2649 |
| curl/configure.ac | `CURL_DISABLE_TELNET` | *(n/a)* | *(n/a)* | 967 |
| curl/configure.ac | `CURL_DISABLE_WEBSOCKETS` | *(n/a)* | *(n/a)* | 4994 |
| curl/configure.ac | `CURL_KRB5_VERSION` | *(n/a)* | *(n/a)* | 1986 |

### ✅ `m4` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 36 occurrences as of 2026-08-22T22:19:32Z*

**Verdict** (by claude-sonnet-5 (direct source read, no dispatch needed), 2026-08-20):
> Confirmed real GitGalaxy false positive, now fixed. The old func_start regex had no capture group over the macro-name argument, so it matched the AC_DEFUN keyword itself as the 'function name' -- structurally identical to matching 'def' as a Python function's name instead of what follows it. gnucobol/configure.ac:658 'AC_DEFUN([AC_PROG_F77], [])' was reported as a function literally named 'AC_DEFUN'; ctags correctly reports nothing here since this call defines an empty macro body (a no-op placeholder, common autoconf idiom for stubbing out a check). Fixed in PR #1927: func_start now captures the real macro-name argument (AC_PROG_F77), handling m4's three real quoting conventions (backtick/apostrophe, bracket, double-bracket). Verified directly: the pipeline now reports 'AC_PROG_F77' at line 658, not 'AC_DEFUN'.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_OPTIMIZE` | 142 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_WARNINGS` | 270 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_ARES` | 75 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_DEBUG` | 110 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_SYMBOL_HIDING` | 198 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_RT` | 238 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_WERROR` | 304 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_NONBLOCKING_SOCKET` | 334 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_THREADED_RESOLVER` | 34 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CONFIGURE_SYMBOL_HIDING` | 369 | *(n/a)* | *(n/a)* |

### ✅ `m4` class existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-22T22:19:32Z*

**Verdict** (by claude-sonnet-5 (direct source read, no dispatch needed), 2026-08-20):
> Confirmed real GitGalaxy false positive, not yet fixed (tracked separately). m4's own class_start rule is explicitly None (m4 has no class/OOP concept) -- but detector.py's class extraction branch only checks _CLASS_START_NAMED_EXTRACTION_LANGS allowlist membership, not whether the language's own class_start is None, so m4 (and 18 other class_start=None languages) falls through to the generic 'class|struct|interface|trait|enum NAME' fallback regex regardless. That fallback has no awareness of m4 document structure, so it matches raw C struct declarations embedded as literal text inside autoconf feature-test macro arguments (e.g. curl/configure.ac:1358's 'struct SocketIFace *ISocket = NULL;' inside an AC_LANG_PROGRAM([[ ... ]]) block) as if they were real m4 classes. Verified directly against the live gatherer: gg_classes for curl/configure.ac returns ['SocketIFace', 'Library', 'sockaddr_in6'], none of which are real m4 constructs; ctags correctly reports none (no class-shaped kind for m4 at all). Filed as GitHub issue #1925 (broader architectural gap, confirmed for m4, 18 other class_start=None languages not yet checked) -- not fixed in this sweep.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| curl/configure.ac | `SocketIFace` | *(n/a)* | *(n/a)* | *(n/a)* |
| curl/configure.ac | `Library` | *(n/a)* | *(n/a)* | *(n/a)* |
| curl/configure.ac | `sockaddr_in6` | *(n/a)* | *(n/a)* | *(n/a)* |
| gnucobol/configure.ac | `timespec` | *(n/a)* | *(n/a)* | *(n/a)* |

## makefile

### ❓ `makefile` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:33Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`makefile/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| freebsd/Makefile | `.PATH` | 4 | 4 | *(n/a)* |

## matlab

### ❓ `matlab` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 1 occurrence as of 2026-08-22T22:19:34Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`matlab/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| eeglab/eeglab.m | `ismatlab` | 1 | 0 | *(n/a)* |

## objective-c

### ❓ `objective-c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 104 occurrences as of 2026-08-22T22:19:35Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/Anchor.m | `selectDiagnostic` | 277 | 277 | *(n/a)* |
| worldwideweb/Anchor.m | `newParent` | 84 | 84 | *(n/a)* |
| worldwideweb/Anchor.m | `equivalent` | 69 | 69 | *(n/a)* |
| worldwideweb/Anchor.m | `moveBy` | 172 | 172 | *(n/a)* |
| worldwideweb/Anchor.m | `setAddress` | 313 | 313 | *(n/a)* |
| worldwideweb/Anchor.m | `setManager` | 34 | 34 | *(n/a)* |
| worldwideweb/Anchor.m | `new` | 47 | 47 | *(n/a)* |
| worldwideweb/Anchor.m | `initialize` | 26 | 26 | *(n/a)* |
| worldwideweb/Anchor.m | `back` | 162 | 162 | *(n/a)* |
| worldwideweb/Anchor.m | `next` | 190 | 190 | *(n/a)* |

### ❓ `objective-c` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 91 occurrences as of 2026-08-22T22:19:35Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/Anchor.m | `linkTo:` | *(n/a)* | *(n/a)* | 331 |
| worldwideweb/Anchor.m | `selectDiagnostic:` | *(n/a)* | *(n/a)* | 278 |
| worldwideweb/Anchor.m | `setAddress:` | *(n/a)* | *(n/a)* | 314 |
| worldwideweb/Anchor.m | `setNode:` | *(n/a)* | *(n/a)* | 264 |
| worldwideweb/HyperManager.m | `accessName:Diagnostic:` | *(n/a)* | *(n/a)* | 157 |
| worldwideweb/HyperManager.m | `appAcceptsAnotherFile:` | *(n/a)* | *(n/a)* | 254 |
| worldwideweb/HyperManager.m | `appDidInit:` | *(n/a)* | *(n/a)* | 240 |
| worldwideweb/HyperManager.m | `appOpenFile:type:` | *(n/a)* | *(n/a)* | 261 |
| worldwideweb/HyperManager.m | `appOpenTempFile:type:` | *(n/a)* | *(n/a)* | 273 |
| worldwideweb/HyperManager.m | `back:` | *(n/a)* | *(n/a)* | 198 |

### ❓ `objective-c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:19:35Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/HyperText.m | `unsigned` | *(n/a)* | 1147 | *(n/a)* |
| worldwideweb/HyperText.m | `void` | *(n/a)* | 1289 | *(n/a)* |

### ❓ `objective-c` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:35Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/HyperText.m | `keyDown` | 1426 | *(n/a)* | *(n/a)* |

## perl

### ❓ `perl` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 122 occurrences as of 2026-08-22T22:19:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| exiftool/ExifTool.pm | `ParseArguments` | *(n/a)* | 5061 | *(n/a)* |
| exiftool/ExifTool.pm | `ReadValue` | *(n/a)* | 6263 | *(n/a)* |
| exiftool/ExifTool.pm | `WindowsLongPath` | *(n/a)* | 4776 | *(n/a)* |
| exiftool/ExifTool.pm | `Open` | *(n/a)* | 4845 | *(n/a)* |
| exiftool/ExifTool.pm | `EncodeFileName` | *(n/a)* | 4723 | *(n/a)* |
| exiftool/ExifTool.pm | `DecodeBits` | *(n/a)* | 6362 | *(n/a)* |
| exiftool/ExifTool.pm | `Filter` | *(n/a)* | 6483 | *(n/a)* |
| exiftool/ExifTool.pm | `SplitFileName` | *(n/a)* | 4698 | *(n/a)* |
| exiftool/ExifTool.pm | `Exists` | *(n/a)* | 4902 | *(n/a)* |
| exiftool/ExifTool.pm | `IsDirectory` | *(n/a)* | 4928 | *(n/a)* |

### ❓ `perl` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-22T22:19:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| exiftool/exiftool | `Image` | *(n/a)* | *(n/a)* | 329 |
| exiftool/exiftool | `Image` | *(n/a)* | *(n/a)* | 330 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 802 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 818 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 834 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 966 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 990 |

### ❓ `perl` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 7 occurrences as of 2026-08-22T22:19:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| exiftool/exiftool | `Image::ExifTool::EndDir` | 329 | 329 | *(n/a)* |
| exiftool/exiftool | `Image::ExifTool::End` | 330 | 330 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::postamble` | 990 | 990 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::constants` | 834 | 834 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::dist` | 966 | 966 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::install` | 818 | 818 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::libscan` | 802 | 802 | *(n/a)* |

### ❓ `perl` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| spamassassin/PerMsgStatus.pm | `Mail::SpamAssassin::PerMsgStatus` | *(n/a)* | *(n/a)* | 3022 |

### ❓ `perl` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mojo/Promise.pm | `get_p` | 277 | *(n/a)* | *(n/a)* |

### ❓ `perl` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 64 occurrences as of 2026-08-22T22:19:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bugzilla/Bug.pm | `_multi_select_accessor` | 3 | 2 | *(n/a)* |
| bugzilla/Bug.pm | `_cf_accessor` | 3 | 2 | *(n/a)* |
| bugzilla/CGI.pm | `multipart_start` | 1 | 2 | *(n/a)* |
| exiftool/ExifTool.pm | `ParseArguments` | 2 | 0 | *(n/a)* |
| exiftool/ExifTool.pm | `ReadValue` | 6 | 0 | *(n/a)* |
| exiftool/ExifTool.pm | `WindowsLongPath` | 2 | 0 | *(n/a)* |
| exiftool/ExifTool.pm | `Open` | 4 | 0 | *(n/a)* |
| exiftool/ExifTool.pm | `EncodeFileName` | 3 | 0 | *(n/a)* |
| exiftool/ExifTool.pm | `DecodeBits` | 3 | 0 | *(n/a)* |
| exiftool/ExifTool.pm | `Filter` | 3 | 0 | *(n/a)* |

## php

### ❓ `php` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:44Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`php/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| laravel_core/BladeCompiler.php | `AnonymousClassa08aab890100` | *(n/a)* | *(n/a)* | 342 |

### ❓ `php` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:44Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`php/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wordpress/formatting.php | `remove_accents` | 1610 | *(n/a)* | 1611 |

## powershell

### ❓ `powershell` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 16 occurrences as of 2026-08-22T22:19:45Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/ci.psm1 | `Invoke-LinuxTestsCore` | 749 | 749 | *(n/a)* |
| core/ci.psm1 | `Set-Path` | 701 | 701 | *(n/a)* |
| core/ci.psm1 | `Invoke-BootstrapStage` | 739 | 739 | *(n/a)* |
| core/ci.psm1 | `Show-Environment` | 731 | 731 | *(n/a)* |
| core/packaging.psm1 | `New-GlobalToolNupkgSource` | 4727 | 4727 | *(n/a)* |
| core/packaging.psm1 | `Get-DirectoryNode` | 4431 | 4431 | *(n/a)* |
| core/packaging.psm1 | `ReduceFxDependentPackage` | 4599 | 4599 | *(n/a)* |
| core/packaging.psm1 | `Get-PackageVersionAsMajorMinorBuildRevision` | 4544 | 4544 | *(n/a)* |
| core/packaging.psm1 | `Get-WindowsVersion` | 4512 | 4512 | *(n/a)* |
| core/packaging.psm1 | `Start-PrepForGlobalToolNupkg` | 4676 | 4676 | *(n/a)* |

### ❓ `powershell` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 7 occurrences as of 2026-08-22T22:19:45Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/packaging.psm1 | `R2RVerification` | *(n/a)* | 25 | *(n/a)* |
| core/packaging.psm1 | `LinkInfo` | *(n/a)* | 1584 | *(n/a)* |
| core/packaging.psm1 | `PackageManifestResultStatus` | *(n/a)* | 5359 | *(n/a)* |
| core/packaging.psm1 | `PackageManifestResult` | *(n/a)* | 5366 | *(n/a)* |
| core/packaging.psm1 | `MachineOSOverride` | *(n/a)* | 5441 | *(n/a)* |
| core/packaging.psm1 | `PsPeInfo` | *(n/a)* | 5451 | *(n/a)* |
| core/packaging.psm1 | `BomRecord` | *(n/a)* | 5605 | *(n/a)* |

### ❓ `powershell` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:45Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/ci.psm1 | `Test-MergeConflictMarker` | 1020 | *(n/a)* | 1020 |

### ❓ `powershell` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 5 occurrences as of 2026-08-22T22:19:45Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/packaging.psm1 | `Start-PSPackage` | 0 | 12 | *(n/a)* |
| core/packaging.psm1 | `New-MSIPackage` | 11 | 10 | *(n/a)* |
| core/packaging.psm1 | `Invoke-AzDevOpsLinuxPackageBuild` | 0 | 2 | *(n/a)* |
| core/packaging.psm1 | `Invoke-AzDevOpsLinuxPackageCreation` | 0 | 3 | *(n/a)* |
| core/packaging.psm1 | `Get-LinuxPackageSemanticVersion` | 0 | 1 | *(n/a)* |

## python

### ✅ `python` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 100 occurrences as of 2026-08-22T22:19:54Z*

**Verdict** (by claude sonnet 5, tri-comparison-ledger-sweep (direct investigation, no dispatch needed), 2026-08-21T12:03:03Z):
> Already documented as Claim 2 in docs/why_gitgalaxy_beats_ast_here.md: tree-sitter-python has no concept of Cython's cdef class/cdef/cpdef syntax at all and loses track of scope at each cdef class boundary, so it finds 0 functions in cython/MemoryView.pyx and cython/MemoryView.pxd (0/0 vs GitGalaxy+ctags' 72/16, full agreement as of the 2026-08-21 get_slice_from_memview follow-up fix -- see the sibling agree[ctags]_vs[gitgalaxy,tree_sitter] shape's verdict for that fix's details). This shape's count grew from 32 to 99 to 100 across this PR's two fixes: it originally covered only the 32 'def'-based methods inside cdef class blocks; each cdef/cpdef func_start fix moved newly-recognized occurrences into THIS shape too, since they still disagree with tree-sitter for the identical underlying reason. GitGalaxy now has zero recall gaps on this corpus for Cython functions -- the only remaining disagreement with tree-sitter is tree-sitter's own structural blindness to the Cython dialect, not a GitGalaxy defect. No GitGalaxy fix needed for tree-sitter's own recall here -- grammar limitation, not an engine defect.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pxd | `memoryview_fromslice` | 98 | *(n/a)* | 98 |
| cython/MemoryView.pxd | `memoryview_cwrapper` | 88 | *(n/a)* | 88 |
| cython/MemoryView.pxd | `setitem_slice_assignment` | 79 | *(n/a)* | 79 |
| cython/MemoryView.pxd | `setitem_slice_assign_scalar` | 80 | *(n/a)* | 80 |
| cython/MemoryView.pxd | `setitem_indexed` | 81 | *(n/a)* | 81 |
| cython/MemoryView.pxd | `setitem_indexed1` | 82 | *(n/a)* | 82 |
| cython/MemoryView.pxd | `assign_item_from_object` | 84 | *(n/a)* | 84 |
| cython/MemoryView.pxd | `is_slice` | 78 | *(n/a)* | 78 |
| cython/MemoryView.pxd | `convert_item_to_object` | 83 | *(n/a)* | 83 |
| cython/MemoryView.pxd | `get_memview` | 50 | *(n/a)* | 50 |

### ✅ `python` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 4 occurrences as of 2026-08-22T22:19:54Z*

**Verdict** (by claude sonnet 5, tri-comparison-ledger-sweep (direct investigation, no dispatch needed), 2026-08-21T03:23:52Z):
> Extends Claim 2 (docs/why_gitgalaxy_beats_ast_here.md) one syntactic level up: tree-sitter-python doesn't just lose track of scope inside a cdef class block, it fails to recognize the 'cdef class' declaration itself as a class at all -- 0 class nodes reported for cython/MemoryView.pyx, missing all 4 real classes (array, Enum, memoryview, _memoryviewslice). GitGalaxy's class_start regex and ctags both correctly identify all 4 by name, confirmed via direct gather_language() check. Note: GitGalaxy's own class_data schema has no start_line column (documented in tri_comparison_gatherer.py's own module docstring), so the ledger's stored example shows a None 'reading' for GitGalaxy on this shape -- that's the (structurally absent) line number field, not an indication GitGalaxy missed the class; by NAME it matches ctags exactly. No GitGalaxy fix needed -- tree-sitter-python grammar limitation. docs/why_gitgalaxy_beats_ast_here.md's Claim 2 updated with this class-level evidence in the same PR.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pyx | `array` | *(n/a)* | *(n/a)* | 130 |
| cython/MemoryView.pyx | `Enum` | *(n/a)* | *(n/a)* | 318 |
| cython/MemoryView.pyx | `memoryview` | *(n/a)* | *(n/a)* | 348 |
| cython/MemoryView.pyx | `_memoryviewslice` | *(n/a)* | *(n/a)* | 936 |

## ruby

### ❓ `ruby` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 6 occurrences as of 2026-08-22T22:19:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/base.rb | `<< self` | *(n/a)* | 53 | *(n/a)* |
| rails/blob.rb | `ActiveStorage::Blob` | *(n/a)* | 19 | *(n/a)* |
| rails/blob.rb | `<< self` | *(n/a)* | 69 | *(n/a)* |
| rails/inbound_emails_controller.rb | `Ingresses::Mailgun::InboundEmailsController` | *(n/a)* | 45 | *(n/a)* |
| rails/metal.rb | `<< self` | *(n/a)* | 144 | *(n/a)* |
| rails/metal.rb | `<< self` | *(n/a)* | 290 | *(n/a)* |

### ❓ `ruby` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 6 occurrences as of 2026-08-22T22:19:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/args/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/blob.rb | `touch_attachments` | 1 | 0 | 0 |
| rails/generator.rb | `generate_guides` | 1 | 0 | 0 |
| rails/generator.rb | `add_digests` | 1 | 0 | 0 |
| rails/generator.rb | `copy_assets` | 1 | 0 | 0 |
| rails/generator.rb | `guides_to_generate` | 1 | 0 | 0 |
| rails/inbound_emails_controller.rb | `mail` | 1 | 0 | 0 |

### ❓ `ruby` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 3 occurrences as of 2026-08-22T22:19:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/base.rb | `process` | 2 | 1 | 2 |
| rails/base.rb | `process_action` | 1 | 0 | 1 |
| rails/metal.rb | `use` | 1 | 0 | 1 |

### ❓ `ruby` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:19:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/blob.rb | `Blob` | *(n/a)* | *(n/a)* | 19 |
| rails/inbound_emails_controller.rb | `InboundEmailsController` | *(n/a)* | *(n/a)* | 45 |

## rust

### ✅ `rust` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 152 occurrences as of 2026-08-22T22:19:58Z*

**Verdict** (by Claude Sonnet 5 (resolved from existing Claim 6 documentation, no dispatch), 2026-08-19T00:00:00Z):
> Not a new question -- already-documented, evidence-backed rust behavior (Claim 6, docs/why_gitgalaxy_beats_ast_here.md: 'structure recall inside opaque macro bodies'). Confirmed directly: all 5 sampled names (get_param, init_access, get_components, from_components, apply) are in bevy/bevy_ecs_macros.rs, inside a `quote! { ... }` proc-macro body (confirmed at source lines 444-460 -- `#path`/`#fields_alias` interpolation syntax is the classic quote! token-generation pattern). These are real Rust function definitions being code-generated by a proc macro; GitGalaxy's regex correctly parses real function syntax wherever it textually appears, including inside macro bodies. tree-sitter-rust and ctags' Rust parser both treat macro_rules!/macro-invocation bodies as opaque token trees and structurally cannot emit function nodes for anything inside one -- not a bug in either, a real grammar limitation. This is exactly why rust is one of the 3 languages (with csharp/fortran) already promoted into ground truth via blind-spot-region detection in the OLD bi-comparison tool (tree_sitter_accuracy_audit.py's _find_blind_spot_ranges) -- this tri-comparison ledger entry is that same, already-understood gap surfacing again under the new 3-tool reconciliation. GitGalaxy is correct; no engine defect, no issue needed. Resolved directly from existing documentation, no fresh dispatch required (tri-comparison-ledger-sweep skill step 1.3).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bevy/bevy_ecs_macros.rs | `get_param` | 456 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `get_components` | 158 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `init_access` | 444 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `from_components` | 191 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `apply_effect` | 177 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `apply` | 448 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `queue` | 452 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `build` | 406 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `map_entities` | 229 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `component_ids` | 141 | *(n/a)* | *(n/a)* |

### ✅ `rust` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 25 occurrences as of 2026-08-22T22:19:58Z*

**Verdict** (by Gemini (dispatched via tri-comparison-ledger-sweep), confirmed by Claude Sonnet 5, 2026-08-19T00:00:00Z):
> Same mechanism as the already-resolved rust/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter] shape (Claim 6, docs/why_gitgalaxy_beats_ast_here.md) -- extended from `fn` definitions inside `quote!{}` invocation bodies to `struct` definitions inside `macro_rules!` DEFINITION bodies. All 6 sampled names confirmed, independently re-verified against source (not just the dispatched agent's own read): NonZeroVisitor (line 90), SaturatingVisitor (112), PrimitiveVisitor (136) inside serde/serde_core_de_impls.rs's `impl_deserialize_num!` macro (def starts line 81); SeqVisitor (998), SeqInPlaceVisitor (1036) inside `seq_impl!` (def starts 978); TupleVisitor (1403) inside `tuple_impl_body!` (nested in `tuple_impls!`, def starts 1396). All 6 are real, complete `struct` declarations, each immediately followed by a genuine `impl<'de,...> Visitor<'de> for <Name>` block -- generated once per macro invocation, not fragments or hallucinated matches. tree-sitter and ctags both treat a macro_rules! arm's body as an opaque, unexpanded token tree and structurally cannot emit struct nodes from inside one, for the identical reason they can't see function definitions inside quote!{} bodies. GitGalaxy is correct in all 6 sampled cases; judged (not independently re-confirmed beyond the sample) to generalize to the full 25, all same-shaped serde-crate occurrences. No new tool defect -- Claim 6's doc text already covered this generically (`struct_item` was already named) but had no concrete cited example for this specific shape; added one (docs/why_gitgalaxy_beats_ast_here.md) rather than filing an issue.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| serde/serde_core_de_impls.rs | `NonZeroVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `SaturatingVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `PrimitiveVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `SeqVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `SeqInPlaceVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `TupleVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `TupleInPlaceVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `MapVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `KindVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |
| serde/serde_core_de_impls.rs | `EnumVisitor` | *(n/a)* | *(n/a)* | *(n/a)* |

### ✅ `rust` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-22T22:19:58Z*

**Verdict** (by Claude Sonnet 5 (resolved directly via live ctags run, no dispatch), 2026-08-19T00:00:00Z):
> Confirmed structural ctags limitation, not a bug -- resolved directly (no dispatch needed). All 3 sampled names (XRegUnion, FRegUnion, VRegUnion) are real Rust `union { }` declarations (confirmed at wasmtime/wasmtime_pulley_interp.rs:404,529,604), distinct from `struct` -- Rust's less-common C-style unsafe union construct. Ran `ctags --list-kinds-full=Rust` directly: its Rust parser's kind list is macro/method/implementation/enumerator/function/enum/interface/field/module/struct/typedef/variable -- there is NO union kind at all. Confirmed via direct ctags run against this exact file: it correctly finds the wrapping `struct FRegVal(FRegUnion)`-shaped types right next to each missed union, so this isn't a general miss, specifically a missing Rust-union kind. Same category as the already-documented ctags Haskell class-kind gap (tests/tools/ctags_reader.py) -- worth a similar doc note there, not a GitHub issue (nothing to fix, ctags upstream has no union support for this language).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `XRegUnion` | *(n/a)* | 404 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `FRegUnion` | *(n/a)* | 529 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `VRegUnion` | *(n/a)* | 604 | *(n/a)* |

### ✅ `rust` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:19:58Z*

**Verdict** (by Claude Sonnet 5 (resolved directly via live ctags run, no dispatch), 2026-08-19T00:00:00Z):
> Confirmed via direct ctags run and sibling comparison, resolved directly (no dispatch needed). `done_decode` (wasmtime/wasmtime_pulley_interp.rs:964) has a destructuring-pattern parameter -- `Done { _priv }: Done`, not a simple `name: Type` binding. Ran ctags directly against the file: its IMMEDIATE SIBLING in the same impl block, `debug_assert_done_reason_none` (line 960, same visibility/receiver shape, ordinary `&mut self`-only signature), IS correctly found as a ctags 'method'. done_decode alone is missing from ctags' output. Isolates the cause precisely to the destructuring-pattern parameter -- ctags' regex-based Rust parser appears to fail/skip the whole function when a parameter is a struct pattern rather than a plain identifier binding. GitGalaxy and tree-sitter both handle this fine (both agree on line 964). N=1 in this corpus, plausibly a real, narrow ctags parser gap (not GitGalaxy's) -- not chasing further given the tiny sample, noting rather than filing an issue since there's nothing in this repo to fix.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `done_decode` | 964 | 964 | *(n/a)* |

## scala

### ❓ `scala` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 16 occurrences as of 2026-08-22T22:19:59Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`scala/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| kafka/KafkaApis.scala | `isAcknowledgeDataPresentInFetchRequest` | 1 | 0 | *(n/a)* |
| kafka/LogManager.scala | `logsByDir` | 2 | 0 | *(n/a)* |
| kafka/LogManager.scala | `offlineLogDirs` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `lowWatermarkIfLeader` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `toString` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `activeProducerState` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `numDelayedDelete` | 3 | 0 | *(n/a)* |
| kafka/Partition.scala | `partitionId` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `logEndOffsetString` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `logEndOffsetString` | 1 | 0 | *(n/a)* |

## scheme

### ❓ `scheme` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 50 occurrences as of 2026-08-22T22:20:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`scheme/function/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| racket/cpnanopass.ss | `build-free-ref` | 2260 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `compatible-fv` | 547 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `extract-trace-code` | 8280 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `maybe-add-detour-trap-check` | 3960 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `build-attachment-get` | 5217 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `tarjan` | 1516 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `compute-sccs` | 1510 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `fp-lvalue` | 3335 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `fp-lvalue` | 3682 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `maybe-drop-trap-check` | 3872 | *(n/a)* | *(n/a)* |

### ✅ `scheme` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 84 occurrences as of 2026-08-22T22:20:03Z*

**Verdict** (by gemini-3.1-pro-high (agy), dispatched via tri-comparison-ledger-sweep, reviewed and fixed by claude-sonnet-5, 2026-08-20):
> Confirmed real, catastrophic GitGalaxy engine defect, generalizes to the full 92 occurrences (and beyond -- this was a 100% recall drop for the whole language, not specific to the sampled cases). Root cause isolated to detector.py's StructuralExtractor._slice_by_braces (Integration Mode B): its scope-delimiter selection checked `lang_id == "lisp"` to choose parenthesis delimiters over the curly-brace default -- but "lisp" has never been a real key in LANGUAGE_DEFINITIONS (only "scheme" is), so that branch was unreachable dead code in production. Every real scheme file fell through to the curly-brace default; since scheme is entirely parenthesis-delimited, the downstream scope-body search never found an opener and silently discarded every func_start match. GitGalaxy's own func_start regex was never the problem -- confirmed matching correctly standalone (31/31 hits on one file) and prism.py's comment stripping confirmed clean (raw (define count unchanged pre/post-prism). Fixed: delimiter choice now keys off lexical_family ("recursive_block_lisp") instead of the dead lang_id string, verified directly against the gatherer (0 -> 58 real functions found; ctags finds 92, so a smaller residual recall gap remains for a future pass, tracked as a follow-on, not blocking this fix). Filed as GitHub issue #1928. A pre-existing unit test (test_detector_mode_b_lisp_family) had been passing for the wrong reason (its mock language was literally named "lisp", matching the dead string check by construction) -- corrected to use scheme's real lexical_family value so it now validates the actual production mechanism. Investigated via gemini-3.1-pro-high (agy): live-pipeline isolation with a monkey-patch before/after proof (0 -> 14 functions when lang_id coerced to match the old check), independently re-verified by Claude against the exact cited source lines before applying.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| racket/schemify.rkt | `make-define-variable` | *(n/a)* | *(n/a)* | 471 |
| racket/schemify.rkt | `make-set-variable` | *(n/a)* | *(n/a)* | 456 |
| racket/schemify.rkt | `schemify` | *(n/a)* | *(n/a)* | 496 |
| racket/schemify.rkt | `schemify-body` | *(n/a)* | *(n/a)* | 200 |
| racket/schemify.rkt | `schemify-body*` | *(n/a)* | *(n/a)* | 210 |
| racket/schemify.rkt | `variable-constance` | *(n/a)* | *(n/a)* | 480 |
| racket/thread.rkt | `add-custodian-to-thread!` | *(n/a)* | *(n/a)* | 752 |
| racket/thread.rkt | `add-to-sleeping-threads!` | *(n/a)* | *(n/a)* | 582 |
| racket/thread.rkt | `add-transitive-resume-to-thread!` | *(n/a)* | *(n/a)* | 802 |
| racket/thread.rkt | `break-enabled` | *(n/a)* | *(n/a)* | 1011 |

## shell

### ❓ `shell` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:20:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`shell/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| brew/brew | `FILTERED_ENV=` | *(n/a)* | *(n/a)* | 292 |

## solidity

### ❓ `solidity` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-08-22T22:20:04Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`solidity/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| openzeppelin/CrosschainRemoteExecutor.sol | `constructor` | 33 | *(n/a)* | *(n/a)* |
| openzeppelin/ERC2771Forwarder.sol | `constructor` | 106 | *(n/a)* | *(n/a)* |
| openzeppelin/Governor.sol | `receive` | 83 | *(n/a)* | *(n/a)* |
| openzeppelin/Governor.sol | `constructor` | 76 | *(n/a)* | *(n/a)* |
| openzeppelin/Proxy.sol | `fallback` | 66 | *(n/a)* | *(n/a)* |
| openzeppelin/ReentrancyGuard.sol | `constructor` | 58 | *(n/a)* | *(n/a)* |

## swift

### ❓ `swift` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:20:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/ParameterEncoder.swift | `encode` | 159 | *(n/a)* | *(n/a)* |

### ❓ `swift` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:20:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/Request.swift | `==` | *(n/a)* | 1119 | *(n/a)* |

### ❓ `swift` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 1 occurrence as of 2026-08-22T22:20:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/Session.swift | `performSetupOperations` | 0 | 3 | *(n/a)* |

## tcl

### ❓ `tcl` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-22T22:20:06Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/malloc_common.tcl | `faultsim_test_proc` | 347 | 347 | *(n/a)* |
| sqlite/tester.tcl | `set_test_counter` | 583 | 583 | *(n/a)* |
| sqlite/tester.tcl | `sqlite3` | 116 | 116 | *(n/a)* |
| sqlite/tester.tcl | `finish_test` | 1243 | 1243 | *(n/a)* |

### ❓ `tcl` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:20:06Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/tester.tcl | `drop_all_tables` | *(n/a)* | 2254 | 2254 |
| sqlite/tester.tcl | `drop_all_indexes` | *(n/a)* | 2279 | 2279 |

### ❓ `tcl` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:20:06Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/tester.tcl | `do_test` | 703 | *(n/a)* | 703 |

### ❓ `tcl` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:20:06Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/malloc_common.tcl | `faultsim_test_result` | 348 | *(n/a)* | *(n/a)* |

## typescript

### ❓ `typescript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1907 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| assemblyscript/ast.ts | `lineAt` | 1686 | 1686 | *(n/a)* |
| assemblyscript/ast.ts | `isLibrary` | 1674 | 1674 | *(n/a)* |
| assemblyscript/ast.ts | `isNative` | 1669 | 1669 | *(n/a)* |
| assemblyscript/ast.ts | `columnAt` | 1715 | 1715 | *(n/a)* |
| assemblyscript/compiler.ts | `compileBinaryExpression` | 4046 | 4046 | *(n/a)* |
| assemblyscript/compiler.ts | `compileUnaryPrefixExpression` | 9522 | 9522 | *(n/a)* |
| assemblyscript/compiler.ts | `convertExpression` | 3546 | 3546 | *(n/a)* |
| assemblyscript/compiler.ts | `makePow` | 5088 | 5088 | *(n/a)* |
| assemblyscript/compiler.ts | `compileUnaryPostfixExpression` | 9278 | 9278 | *(n/a)* |
| assemblyscript/compiler.ts | `compileIdentifierExpression` | 7358 | 7358 | *(n/a)* |

### ❓ `typescript` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 501 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| assemblyscript/ast.ts | `NodeKind` | *(n/a)* | 46 | *(n/a)* |
| assemblyscript/ast.ts | `ParameterKind` | *(n/a)* | 948 | *(n/a)* |
| assemblyscript/ast.ts | `DecoratorKind` | *(n/a)* | 990 | *(n/a)* |
| assemblyscript/ast.ts | `CommentKind` | *(n/a)* | 1100 | *(n/a)* |
| assemblyscript/ast.ts | `LiteralKind` | *(n/a)* | 1143 | *(n/a)* |
| assemblyscript/ast.ts | `AssertionKind` | *(n/a)* | 1178 | *(n/a)* |
| assemblyscript/ast.ts | `SourceKind` | *(n/a)* | 1619 | *(n/a)* |
| assemblyscript/ast.ts | `ArrowKind` | *(n/a)* | 2048 | *(n/a)* |
| assemblyscript/compiler.ts | `UncheckedBehavior` | *(n/a)* | 353 | *(n/a)* |
| assemblyscript/compiler.ts | `Constraints` | *(n/a)* | 363 | *(n/a)* |

### ❓ `typescript` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 174 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fp-ts/Either.ts | `_traverse` | *(n/a)* | 181 | *(n/a)* |
| fp-ts/Either.ts | `tryCatchK` | *(n/a)* | 1408 | *(n/a)* |
| fp-ts/Either.ts | `fromNullableK` | *(n/a)* | 1421 | *(n/a)* |
| fp-ts/Either.ts | `chainNullableK` | *(n/a)* | 1436 | *(n/a)* |
| fp-ts/Either.ts | `traverseReadonlyArrayWithIndex` | *(n/a)* | 1605 | *(n/a)* |
| fp-ts/Either.ts | `traverseArray` | *(n/a)* | 1628 | *(n/a)* |
| fp-ts/TaskEither.ts | `tryCatchK` | *(n/a)* | 266 | *(n/a)* |
| fp-ts/TaskEither.ts | `fromTaskOptionK` | *(n/a)* | 393 | *(n/a)* |
| fp-ts/TaskEither.ts | `fromIOEitherK` | *(n/a)* | 428 | *(n/a)* |
| fp-ts/TaskEither.ts | `traverseReadonlyNonEmptyArrayWithIndex` | *(n/a)* | 1600 | *(n/a)* |

### ❓ `typescript` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 61 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2184 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2202 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2220 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2238 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2257 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2277 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2185 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2203 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2221 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2239 |

### ❓ `typescript` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 9 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fp-ts/pipeable.ts | `pipeable` | *(n/a)* | 2344 | 2344 |
| fp-ts/pipeable.ts | `pipeable` | *(n/a)* | 2374 | 2374 |
| fp-ts/pipeable.ts | `pipeable` | *(n/a)* | 2404 | 2404 |
| fp-ts/pipeable.ts | `pipeable` | *(n/a)* | 2433 | 2433 |
| fp-ts/pipeable.ts | `pipeable` | *(n/a)* | 2463 | 2463 |
| fp-ts/pipeable.ts | `pipeable` | *(n/a)* | 2490 | 2490 |
| fp-ts/pipeable.ts | `pipeable` | *(n/a)* | 2520 | 2520 |
| typescript_compiler/binder.ts | `createBinder` | *(n/a)* | 509 | 509 |
| vscode/ipc.ts | `drain` | *(n/a)* | 105 | 105 |

### ❓ `typescript` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| vscode/instantiationService.ts | `extends` | *(n/a)* | *(n/a)* | 410 |
| vscode/lifecycle.ts | `implements` | *(n/a)* | *(n/a)* | 235 |

### ❓ `typescript` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| vscode/lifecycle.ts | `createReferencedObject` | 711 | *(n/a)* | *(n/a)* |
| vscode/lifecycle.ts | `destroyReferencedObject` | 712 | *(n/a)* | *(n/a)* |

### ❓ `typescript` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 4 occurrences as of 2026-08-22T22:20:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| vscode/async.ts | `constructor` | 2 | 0 | *(n/a)* |
| vscode/vscode.d.ts | `constructor` | 5 | 2 | *(n/a)* |
| vscode/vscode.d.ts | `constructor` | 1 | 2 | *(n/a)* |
| vscode/vscode.d.ts | `constructor` | 1 | 4 | *(n/a)* |

## zig

### ❓ `zig` class existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 10 occurrences as of 2026-08-22T22:20:47Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`zig/class/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bun/napi.zig | `V8API` | *(n/a)* | 1916 | *(n/a)* |
| bun/napi.zig | `uv_functions_to_export` | *(n/a)* | 2474 | *(n/a)* |
| zig/Compilation.zig | `need_writable_dance` | *(n/a)* | 3132 | *(n/a)* |
| zig/Type.zig | `vector_info` | *(n/a)* | 3986 | *(n/a)* |
| zig/main.zig | `template` | *(n/a)* | 4659 | *(n/a)* |
| zig/main.zig | `http_client` | *(n/a)* | 5080 | *(n/a)* |
| zig/main.zig | `op` | *(n/a)* | 6323 | *(n/a)* |
| zig/main.zig | `save` | *(n/a)* | 6834 | *(n/a)* |
| zls/analysis.zig | `result` | *(n/a)* | 1142 | *(n/a)* |
| zls/analysis.zig | `loop` | *(n/a)* | 2643 | *(n/a)* |

### ❓ `zig` class existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:20:47Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`zig/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bun/MimallocArena.zig | `Borrowed` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `zig` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-22T22:20:47Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`zig/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| zig/InternPool.zig | `dbHelper` | *(n/a)* | 4823 | *(n/a)* |
