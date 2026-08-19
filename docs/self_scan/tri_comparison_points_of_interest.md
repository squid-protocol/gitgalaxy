# Tri-Comparison Points of Interest

Generated from `tri_comparison_ledger.json` by `tests/tools/tri_comparison_report.py --write` -- do not hand-edit this file, edit the ledger and regenerate. See `docs/self_scan/how_to_investigate_a_discrepancy.md` for what ❓ entries are asking for.

Sorted 2-vs-1 splits before 3-way splits, unvalidated before validated, biggest occurrence count first within each tier -- see this script's own module docstring for why that order.

## agc_assembly

### ❓ `agc_assembly` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 760 occurrences as of 2026-08-19T23:12:49Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`agc_assembly/function/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ADRSCHK` | 418 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `1CHK` | 184 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `CONTINU` | 437 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `ERASLOOP` | 262 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `SMODECHK` | 191 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `COMADRS` | 381 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `SOPT` | 496 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `SOPTION` | 482 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `FXFX` | 391 | *(n/a)* | *(n/a)* |
| apollo-11/AGC_BLOCK_TWO_SELF-CHECK.agc | `BNKCHK` | 505 | *(n/a)* | *(n/a)* |

## apex

### ❓ `apex` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:12:50Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`apex/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| apex-recipes/AuraEnabledRecipes_Tests.cls | `Account` | 25 | *(n/a)* | *(n/a)* |
| apex-recipes/AuraEnabledRecipes_Tests.cls | `Account` | 43 | *(n/a)* | *(n/a)* |

## assembly

### ❓ `assembly` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 52 occurrences as of 2026-08-19T23:12:53Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`assembly/function/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bootos/counter.asm | `.1` | 52 | *(n/a)* | *(n/a)* |
| bootos/counter.asm | `.2` | 67 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.loop` | 306 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.find` | 360 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.empty` | 366 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `.load_vec` | 197 | *(n/a)* | *(n/a)* |
| bootos/os.asm | `max_entries` | 166 | *(n/a)* | *(n/a)* |
| cosmopolitan/ape.S | `a20` | 1466 | *(n/a)* | *(n/a)* |
| cosmopolitan/ape.S | `e820` | 1421 | *(n/a)* | *(n/a)* |
| cosmopolitan/ape.S | `dsknfo` | 348 | *(n/a)* | *(n/a)* |

### ❓ `assembly` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 7 occurrences as of 2026-08-19T23:12:53Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`assembly/function/existence/agree[ctags]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bootos/os.asm | `del_command` | *(n/a)* | *(n/a)* | 269 |
| bootos/os.asm | `empty` | *(n/a)* | *(n/a)* | 366 |
| bootos/os.asm | `find` | *(n/a)* | *(n/a)* | 360 |
| bootos/os.asm | `load_vec` | *(n/a)* | *(n/a)* | 197 |
| bootos/os.asm | `loop` | *(n/a)* | *(n/a)* | 306 |
| cosmopolitan/ape.S | `Largv0` | *(n/a)* | *(n/a)* | 1785 |
| hellosilicon/matrixmultneon.s | `prtstr` | *(n/a)* | *(n/a)* | 92 |

## c

### ✅ `c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 74 occurrences as of 2026-08-19T23:12:58Z*

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

### ✅ `c` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 13 occurrences as of 2026-08-19T23:12:58Z*

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

### ✅ `c` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 9 occurrences as of 2026-08-19T23:12:58Z*

**Verdict** (by Gemini (dispatched via tri-comparison-ledger-sweep), confirmed by Claude Sonnet 5, 2026-08-19T00:00:00Z):
> Single cause, confirmed independently twice (dispatched agent + a second independent spot-check, no disagreement) -- a bug in THIS tool's ctags_reader.py, not ctags itself. CTAGS_CLASS_KINDS['c'] was {'s'} (struct only), but GitGalaxy's own C class_start regex (gitgalaxy/standards/language_standards.py) is `struct|union|enum` -- all 3. ctags' C parser handles enum ('g' kind) and union ('u' kind) fine (confirmed via direct ctags runs against sqlite/lemon.c and others, finding all 9 sampled declarations correctly); this map was silently dropping them before reconciliation ever saw them. Fixed: CTAGS_CLASS_KINDS['c'] now {'s', 'g', 'u'}, verified all 9 sampled names (6 enum in sqlite/lemon.c, 1 enum each in cpython/frameobject.c and cpython/gc.c, 1 union in micropython/objtype.c) now correctly found. No GitHub issue -- fixed directly.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/frameobject.c | `kind` | *(n/a)* | 1175 | *(n/a)* |
| cpython/gc.c | `flagstates` | *(n/a)* | 377 | *(n/a)* |
| micropython/objtype.c | `_setname_list_t` | *(n/a)* | 981 | *(n/a)* |
| sqlite/lemon.c | `option_type` | *(n/a)* | 271 | *(n/a)* |
| sqlite/lemon.c | `symbol_type` | *(n/a)* | 319 | *(n/a)* |
| sqlite/lemon.c | `e_assoc` | *(n/a)* | 324 | *(n/a)* |
| sqlite/lemon.c | `cfgstatus` | *(n/a)* | 389 | *(n/a)* |
| sqlite/lemon.c | `e_action` | *(n/a)* | 405 | *(n/a)* |
| sqlite/lemon.c | `e_state` | *(n/a)* | 2323 | *(n/a)* |

### ✅ `c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 8 occurrences as of 2026-08-19T23:12:58Z*

**Verdict** (by Gemini (dispatched via tri-comparison-ledger-sweep), confirmed by Claude Sonnet 5, 2026-08-19T00:00:00Z):
> Two distinct causes, both confirmed by independent verification, not one -- resolved via dispatched investigation plus direct fixes. (1) 5 of 8 (I_AllocLow, I_ZoneBase, I_BaseTiccmd, R_CheckBBox, R_AddLine, all doom): a real bug in THIS tool's OWN ctags_reader.py, not a ctags limitation. Old Doom source uses literal TAB characters for column alignment (e.g. `byte*\tI_AllocLow(int length)`); ctags faithfully echoes that tab into its tag-file's address/pattern field, and read_ctags_symbols' naive line.split('\t') then misreads a fragment of the SOURCE LINE as the kind field, fails the kind-membership check, and silently drops the symbol. Confirmed by running ctags with the exact flags this code uses and inspecting the raw tab-delimited output directly -- reproduced the exact column-shift byte for byte. Fixed: parse now finds the tag-file format's guaranteed `;"` address-terminator marker instead of blind-splitting the whole line, only tab-splitting the safe trailer after it. Verified: all 5 names now correctly found. (2) 3 of 8 (slot_nb_power, slot_nb_bool, wrap_next, all cpython typeobject.c): extension of the already-documented SLOT-macro ctags limitation -- each follows a SLOT1BINFULL/SLOT0/RICHCMP_WRAPPER macro invocation ctags misreads as a function (confirmed at typeobject.c:10574/10577/10630), which also swallows the real function immediately after it. Not code-fixed (same ground-truth-judgment reasoning as the sibling 7-occurrence shape) -- already covered by ctags_reader.py's existing note on this mechanism.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `slot_nb_power` | 10577 | 10577 | *(n/a)* |
| cpython/typeobject.c | `slot_nb_bool` | 10630 | 10630 | *(n/a)* |
| cpython/typeobject.c | `wrap_next` | 10106 | 10106 | *(n/a)* |
| doom/i_system.c | `I_AllocLow` | 147 | 147 | *(n/a)* |
| doom/i_system.c | `I_ZoneBase` | 76 | 76 | *(n/a)* |
| doom/i_system.c | `I_BaseTiccmd` | 65 | 65 | *(n/a)* |
| doom/r_bsp.c | `R_CheckBBox` | 381 | 381 | *(n/a)* |
| doom/r_bsp.c | `R_AddLine` | 259 | 259 | *(n/a)* |

### ✅ `c` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-19T23:12:58Z*

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

*2-vs-1 -- 4 occurrences as of 2026-08-19T23:12:58Z*

**Verdict** (by Claude Sonnet 5 (resolved directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Confirmed GitGalaxy correct, real finding -- a new, narrower instance of Claim 3 (parse-error cascade), added to docs/why_gitgalaxy_beats_ast_here.md. All 4 sampled names (slot_mp_ass_subscript:10544, slot_nb_inplace_power:10697, slot_tp_repr:10714, slot_tp_hash:10730, all cpython/typeobject.c) are ordinary, unremarkable function definitions -- nothing unusual individually -- but each sits directly after a bare SLOT0/SLOT1 macro-invocation LINE (`SLOT1(slot_mp_subscript, __getitem__, PyObject *)`, `SLOT0(slot_tp_str, __str__)`, etc.) that isn't valid freestanding C without macro expansion. GitGalaxy's regex has no adjacency sensitivity and finds all 4 correctly; both ctags and tree-sitter locally lose the SINGLE function immediately following each such line (recovers after just one function, not a full cascade to EOF -- confirmed by resolving all 4 as isolated single-function misses, not a growing region). Resolved directly, no dispatch needed -- same pattern verified at all 4 sample points before writing up.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `slot_tp_hash` | 10730 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_mp_ass_subscript` | 10544 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_tp_repr` | 10714 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_nb_inplace_power` | 10697 | *(n/a)* | *(n/a)* |

### ✅ `c` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:12:58Z*

**Verdict** (by Claude Sonnet 5 (resolved directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Not a new finding -- both sampled names are ALREADY in tree_sitter_accuracy_audit.py's _C_KNOWN_MACRO_HALLUCINATIONS exclusion set (confirmed by grep: 'EXPORT_FUN' and 'MICROPY_WRAP_MP_EXECUTE_BYTECODE' both present). This shape is the same already-documented macro-hallucination mechanism (Claim 8) as the earlier tree-sitter-alone shape, just with ctags ALSO independently hallucinating the same 2 names the same way (both tools' regex/grammar parsers get fooled by the same macro-definition text). GitGalaxy correctly excludes both. Resolved directly, no dispatch needed.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython/emitnative.c | `EXPORT_FUN` | *(n/a)* | 300 | 300 |
| micropython/emitnative.c | `EXPORT_FUN` | *(n/a)* | 320 | 320 |
| micropython/vm.c | `MICROPY_WRAP_MP_EXECUTE_BYTECODE` | *(n/a)* | 220 | 220 |

### ✅ `c` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:12:58Z*

**Verdict** (by Claude Sonnet 5 (resolved directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Not a tool defect on either side -- an inherent CPP-conditional-compilation ambiguity. gc_mark_subtree is declared AND defined twice in micropython/gc.c, once under `#if MICROPY_GC_SPLIT_HEAP` (2 args: area, block -- lines 137/501) and once under the matching `#else` (1 arg: block -- lines 139/503). Neither signature is more 'real' than the other -- which one actually compiles depends on a macro none of these three tools evaluates (no real preprocessor run in any of them). GG and ctags happened to align on the 2-arg branch, tree-sitter on the 1-arg branch; this is a coin-flip of which #if branch a tool's occurrence-matching happens to pick up, not a real disagreement about ground truth. N=1 in this corpus -- not chased further given the tiny sample and the ambiguity being structural rather than a bug.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython/gc.c | `gc_mark_subtree` | 2 | 1 | 2 |

## cobol

### ❓ `cobol` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 133 occurrences as of 2026-08-19T23:13:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cobol/function/existence/agree[ctags]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 455 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 600 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 806 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 869 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 916 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 922 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 1240 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 1306 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 1372 |
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `END-IF` | *(n/a)* | *(n/a)* | 1431 |

### ❓ `cobol` class existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 19 occurrences as of 2026-08-19T23:13:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cobol/class/existence/agree[ctags]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `BANKDATA` | *(n/a)* | *(n/a)* | 35 |
| cics-banking-sample-application-cbsa/BNKMENU.cbl | `BNKMENU` | *(n/a)* | *(n/a)* | 18 |
| cics-banking-sample-application-cbsa/XFRFUN.cbl | `XFRFUN` | *(n/a)* | *(n/a)* | 41 |
| cics-genapp/lgacdb01.cbl | `LGACDB01` | *(n/a)* | *(n/a)* | 13 |
| cics-genapp/lgacdb02.cbl | `LGACDB02` | *(n/a)* | *(n/a)* | 13 |
| cics-genapp/lgacus01.cbl | `LGACUS01` | *(n/a)* | *(n/a)* | 11 |
| cics-genapp/lgacvs01.cbl | `LGACVS01` | *(n/a)* | *(n/a)* | 11 |
| cics-genapp/lgapdb01.cbl | `LGAPDB01` | *(n/a)* | *(n/a)* | 13 |
| cics-genapp/lgapol01.cbl | `LGAPOL01` | *(n/a)* | *(n/a)* | 13 |
| cics-genapp/lgapvs01.cbl | `LGAPVS01` | *(n/a)* | *(n/a)* | 11 |

### ❓ `cobol` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 18 occurrences as of 2026-08-19T23:13:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cobol/function/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cics-banking-sample-application-cbsa/BANKDATA.cbl | `TIMESTAMP` | 1440 | *(n/a)* | *(n/a)* |
| cics-banking-sample-application-cbsa/XFRFUN.cbl | `LOCAL-STORAGE` | 105 | *(n/a)* | *(n/a)* |
| cics-genapp/lgacdb01.cbl | `MAINLINE` | 126 | *(n/a)* | *(n/a)* |
| cics-genapp/lgacdb02.cbl | `MAINLINE` | 113 | *(n/a)* | *(n/a)* |
| cics-genapp/lgacus01.cbl | `MAINLINE` | 76 | *(n/a)* | *(n/a)* |
| cics-genapp/lgacvs01.cbl | `MAINLINE` | 61 | *(n/a)* | *(n/a)* |
| cics-genapp/lgapdb01.cbl | `MAINLINE` | 144 | *(n/a)* | *(n/a)* |
| cics-genapp/lgapol01.cbl | `MAINLINE` | 78 | *(n/a)* | *(n/a)* |
| cics-genapp/lgapvs01.cbl | `MAINLINE` | 92 | *(n/a)* | *(n/a)* |
| cics-genapp/lgastat1.cbl | `MAINLINE` | 68 | *(n/a)* | *(n/a)* |

## cpp

### ❓ `cpp` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1270 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| NVDA/storage.cpp | `VBufStorage_buffer_t::getLineOffsets` | 1066 | 1066 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_buffer_t::findNodeByAttributes` | 973 | 973 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_fieldNode_t::nextNodeInTree` | 57 | 57 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_buffer_t::insertNode` | 445 | 445 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_buffer_t::unlinkFieldNode` | 766 | 766 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_buffer_t::replaceSubtrees` | 642 | 642 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_fieldNode_t::getTextInRange` | 274 | 274 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_buffer_t::addTextFieldNode` | 585 | 585 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_buffer_t::addTextFieldNode` | 623 | 623 | *(n/a)* |
| NVDA/storage.cpp | `VBufStorage_fieldNode_t::generateAttributesForMarkupOpeningTag` | 225 | 225 | *(n/a)* |

### ❓ `cpp` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1025 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| NVDA/storage.cpp | `VBufStorage_buffer_t` | *(n/a)* | *(n/a)* | 539 |
| NVDA/storage.cpp | `VBufStorage_controlFieldNodeIdentifier_t` | *(n/a)* | *(n/a)* | 36 |
| NVDA/storage.cpp | `VBufStorage_controlFieldNode_t` | *(n/a)* | *(n/a)* | 373 |
| NVDA/storage.cpp | `VBufStorage_fieldNode_t` | *(n/a)* | *(n/a)* | 313 |
| NVDA/storage.cpp | `VBufStorage_textFieldNode_t` | *(n/a)* | *(n/a)* | 425 |
| NVDA/storage.cpp | `addAttribute` | *(n/a)* | *(n/a)* | 321 |
| NVDA/storage.cpp | `addControlFieldNode` | *(n/a)* | *(n/a)* | 548 |
| NVDA/storage.cpp | `addControlFieldNode` | *(n/a)* | *(n/a)* | 561 |
| NVDA/storage.cpp | `addReferenceNodeToBuffer` | *(n/a)* | *(n/a)* | 1231 |
| NVDA/storage.cpp | `addTextFieldNode` | *(n/a)* | *(n/a)* | 585 |

### ❓ `cpp` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 120 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/editor_node.h | `AcceptDialog` | *(n/a)* | 45 | *(n/a)* |
| godot/editor_node.h | `ColorPicker` | *(n/a)* | 46 | *(n/a)* |
| godot/editor_node.h | `ConfirmationDialog` | *(n/a)* | 47 | *(n/a)* |
| godot/editor_node.h | `Control` | *(n/a)* | 48 | *(n/a)* |
| godot/editor_node.h | `FileDialog` | *(n/a)* | 49 | *(n/a)* |
| godot/editor_node.h | `HBoxContainer` | *(n/a)* | 50 | *(n/a)* |
| godot/editor_node.h | `ImageTexture` | *(n/a)* | 51 | *(n/a)* |
| godot/editor_node.h | `MenuBar` | *(n/a)* | 52 | *(n/a)* |
| godot/editor_node.h | `MenuButton` | *(n/a)* | 53 | *(n/a)* |
| godot/editor_node.h | `OptionButton` | *(n/a)* | 54 | *(n/a)* |

### ❓ `cpp` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 98 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/node.cpp | `for` | *(n/a)* | 2518 | *(n/a)* |
| godot/object.cpp | `Object::Connection::operator Variant() const` | *(n/a)* | 108 | *(n/a)* |
| godot/object.cpp | `if` | *(n/a)* | 784 | *(n/a)* |
| godot/object.cpp | `if` | *(n/a)* | 827 | *(n/a)* |
| godot/object.h | `operator=` | *(n/a)* | 1116 | *(n/a)* |
| godot/object.h | `operator=` | *(n/a)* | 1125 | *(n/a)* |
| godot/object.h | `operator=` | *(n/a)* | 1134 | *(n/a)* |
| godot/object.h | `void` | *(n/a)* | 549 | *(n/a)* |
| godot/object.h | `void` | *(n/a)* | 552 | *(n/a)* |
| godot/object.h | `void` | *(n/a)* | 561 | *(n/a)* |

### ❓ `cpp` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 70 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/gdscript_vm.cpp | `GDScriptFunction::call` | 499 | *(n/a)* | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE_WHILE` | 754 | *(n/a)* | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE_WHILE` | 757 | *(n/a)* | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE_SWITCH` | 760 | *(n/a)* | *(n/a)* |
| godot/gdscript_vm.cpp | `OPCODE` | 3944 | *(n/a)* | *(n/a)* |
| godot/main.cpp | `Main::setup` | 1027 | *(n/a)* | *(n/a)* |
| godot/main.cpp | `Main::setup2` | 3007 | *(n/a)* | *(n/a)* |
| godot/main.cpp | `Main::start` | 3987 | *(n/a)* | *(n/a)* |
| godot/object.cpp | `Object::Connection::operator Variant` | 108 | *(n/a)* | *(n/a)* |
| godot/object.h | `RequiredResult` | 994 | *(n/a)* | *(n/a)* |

### ❓ `cpp` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 24 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/args/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| NVDA/inProcess.cpp | `inProcess_initialize` | 1 | 0 | 0 |
| godot/editor_node.cpp | `get_game_view_plugin` | 1 | 0 | 0 |
| godot/main.cpp | `initialize_physics` | 2 | 0 | 0 |
| godot/main.cpp | `get_full_version_string` | 1 | 0 | 0 |
| godot/main.cpp | `initialize_theme_db` | 1 | 0 | 0 |
| mlir/flatbuffer_export.cc | `CreateLocation` | 1 | 5 | 5 |
| mlir/flatbuffer_export.cc | `GetStringsFromDictionaryAttr` | 0 | 2 | 2 |
| mlir/flatbuffer_export.cc | `CreateOpLocation` | 0 | 5 | 5 |
| mlir/flatbuffer_export.cc | `GetTensorFlowNodeDef` | 11 | 1 | 1 |
| mlir/flatbuffer_export.cc | `MlirToFlatBufferTranslateFunction` | 0 | 3 | 3 |

### ❓ `cpp` class existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 22 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/class/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/editor_node.h | `SceneNameCasing` | *(n/a)* | 124 | *(n/a)* |
| godot/editor_node.h | `ActionOnPlay` | *(n/a)* | 132 | *(n/a)* |
| godot/editor_node.h | `ActionOnStop` | *(n/a)* | 138 | *(n/a)* |
| godot/editor_node.h | `MenuOptions` | *(n/a)* | 143 | *(n/a)* |
| godot/editor_node.h | `MenuType` | *(n/a)* | 711 | *(n/a)* |
| godot/main.h | `CLIOptionAvailability` | *(n/a)* | 40 | *(n/a)* |
| godot/main.h | `CLIScope` | *(n/a)* | 64 | *(n/a)* |
| godot/node.h | `ProcessMode` | *(n/a)* | 79 | *(n/a)* |
| godot/node.h | `ProcessThreadGroup` | *(n/a)* | 87 | *(n/a)* |
| godot/node.h | `ProcessThreadMessages` | *(n/a)* | 93 | *(n/a)* |

### ❓ `cpp` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mlir/flatbuffer_export.cc | `GetTFLiteType` | 2 | 1 | 2 |
| mlir/flatbuffer_export.cc | `Insert` | 5 | 4 | 5 |
| mlir/flatbuffer_export.cc | `ExportBuffer` | 4 | 3 | 4 |

### ❓ `cpp` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `HashMapComparatorDefault` | *(n/a)* | *(n/a)* | 886 |
| godot/variant.h | `is_zero_constructible` | *(n/a)* | *(n/a)* | 984 |

### ❓ `cpp` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `call` | 2 | 2 | 1 |

### ❓ `cpp` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mlir/flatbuffer_export.cc | `Translator` | *(n/a)* | 654 | 654 |

### ❓ `cpp` function args: none agree, GitGalaxy, tree-sitter, ctags differ

*3-way split -- 1 occurrence as of 2026-08-19T23:13:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/args/agree[none]_vs[ctags,gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| NVDA/storage.cpp | `outputEscapedAttribute` | 0 | 2 | 3 |

## csharp

### ❓ `csharp` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 271 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `csharp` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 107 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

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

### ❓ `csharp` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 48 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `GetWellKnownType` | 2282 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parsePrimaryExpressionWithoutPostfix` | 11940 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parsePostFixExpression` | 12115 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `canFollowNullableType` | 7719 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ParseCommaSeparatedSyntaxList` | 14422 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ParseCommaSeparatedSyntaxList` | 14444 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `tryExpandExpression` | 11546 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `tokenBreaksTypeArgumentList` | 6626 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseCallingConvention` | 8100 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseSwitchHeader` | 10175 | *(n/a)* | *(n/a)* |

### ❓ `csharp` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 7 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/args/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `HasEntryPointSignature` | 0 | 2 | 2 |
| roslyn/Workspace.cs | `SetCurrentSolutionAsync` | 2 | 6 | 6 |
| roslyn/Workspace.cs | `SetCurrentSolutionAsync` | 0 | 7 | 7 |
| roslyn/Workspace.cs | `OnAnyDocumentTextChanged` | 2 | 7 | 7 |
| roslyn/Workspace.cs | `ScheduleTask` | 1 | 2 | 2 |
| roslyn/Workspace.cs | `SetCurrentSolutionEx` | 2 | 1 | 1 |
| roslyn/Workspace.cs | `ProcessEventHandlerWorkQueueAsync` | 1 | 2 | 2 |

### ❓ `csharp` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 6 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `VariableFlags` | *(n/a)* | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `NameOptions` | *(n/a)* | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ScanTypeArgumentListKind` | *(n/a)* | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ScanTypeFlags` | *(n/a)* | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ParseTypeMode` | *(n/a)* | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `Precedence` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `csharp` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 5 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `TerminatorState` | *(n/a)* | 57 | *(n/a)* |
| roslyn/LanguageParser.cs | `NamespaceParts` | *(n/a)* | 399 | *(n/a)* |
| roslyn/LanguageParser.cs | `LanguageParserState` | *(n/a)* | 4295 | *(n/a)* |
| roslyn/LanguageParser.cs | `AccessorDeclaringKind` | *(n/a)* | 4342 | *(n/a)* |
| roslyn/LanguageParser.cs | `PostSkipAction` | *(n/a)* | 4472 | *(n/a)* |

### ❓ `csharp` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `GetHashCode` | 1 | 1 | 2 |
| roslyn/LanguageParser.cs | `GetModifierExcludingScoped` | 1 | 1 | 2 |
| roslyn/Workspace.cs | `SetCurrentSolution` | 1 | 1 | 6 |
| roslyn/Workspace.cs | `SetCurrentSolution` | 6 | 6 | 4 |

### ❓ `csharp` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 4 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `ShouldCheckTypeForMembers` | *(n/a)* | 5268 | 5268 |
| roslyn/CSharpCompilation.cs | `Matches` | *(n/a)* | 5281 | 5281 |
| roslyn/CSharpSyntaxTree.cs | `GetRoot` | *(n/a)* | 86 | 86 |
| roslyn/DiagnosticAnalyzer.cs | `Initialize` | *(n/a)* | 24 | 24 |

### ❓ `csharp` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `LanguageParser` | *(n/a)* | *(n/a)* | 20 |
| roslyn/LanguageParser.cs | `DisposableResetPoint` | *(n/a)* | *(n/a)* | 14575 |
| roslyn/LanguageParser.cs | `ResetPoint` | *(n/a)* | *(n/a)* | 14600 |

### ❓ `csharp` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `Equals` | 1 | 2 | 1 |

### ❓ `csharp` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `bool` | *(n/a)* | *(n/a)* | 2539 |

### ❓ `csharp` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpSyntaxTree.cs | `TryGetRoot` | *(n/a)* | 91 | *(n/a)* |

### ❓ `csharp` function args: none agree, GitGalaxy, tree-sitter, ctags differ

*3-way split -- 1 occurrence as of 2026-08-19T23:13:14Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/args/agree[none]_vs[ctags,gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/Workspace.cs | `SetCurrentSolution` | 0 | 4 | 5 |

## css

### ❓ `css` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:13:15Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`css/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| element/common.css | `media` | 153 | 153 | *(n/a)* |
| element/common.css | `media` | 160 | 160 | *(n/a)* |
| odoo/control_panel_mobile.css | `media` | 1 | 1 | *(n/a)* |

## dart

### ❓ `dart` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 37 occurrences as of 2026-08-19T23:13:19Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`dart/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| flutter/editable_text.dart | `AutofillClient` | 2483 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `_scrollableNotificationIsFromSameSubtree` | 4173 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `EditableText.getEditableButtonItems` | 3167 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `TextStyle` | 316 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `TargetPlatform.windows` | 2117 | *(n/a)* | *(n/a)* |
| flutter/editable_text.dart | `TargetPlatform.windows` | 4126 | *(n/a)* | *(n/a)* |
| flutter/framework.dart | `keyStringCount.update` | 3363 | *(n/a)* | *(n/a)* |
| flutter/framework.dart | `elementStringCount.update` | 3383 | *(n/a)* | *(n/a)* |
| flutter/framework.dart | `_children.where` | 7181 | *(n/a)* | *(n/a)* |
| flutter/framework.dart | `Unknown_Block` | 194 | *(n/a)* | *(n/a)* |

### ❓ `dart` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 18 occurrences as of 2026-08-19T23:13:19Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`dart/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| flutter/editable_text.dart | `_DiscreteKeyFrameSimulation._` | *(n/a)* | 535 | *(n/a)* |
| flutter/editable_text.dart | `EditableText` | *(n/a)* | 829 | *(n/a)* |
| flutter/editable_text.dart | `defaultSelectionHeightStyle` | *(n/a)* | 2076 | *(n/a)* |
| flutter/editable_text.dart | `defaultSelectionWidthStyle` | *(n/a)* | 2089 | *(n/a)* |
| flutter/editable_text.dart | `_EditableTextTapOutsideAction` | *(n/a)* | 6706 | *(n/a)* |
| flutter/editable_text.dart | `_EditableTextTapUpOutsideAction` | *(n/a)* | 6739 | *(n/a)* |
| flutter/framework.dart | `findAncestorStateOfType` | *(n/a)* | 5132 | *(n/a)* |
| flutter/framework.dart | `findRootAncestorStateOfType` | *(n/a)* | 5146 | *(n/a)* |
| flutter/framework.dart | `currentState` | *(n/a)* | 192 | *(n/a)* |
| flutter/framework.dart | `children` | *(n/a)* | 7180 | *(n/a)* |

### ❓ `dart` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 216 occurrences as of 2026-08-19T23:13:19Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`dart/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| flutter/editable_text.dart | `build` | 2 | 3 | *(n/a)* |
| flutter/editable_text.dart | `_inferKeyboardType` | 1 | 2 | *(n/a)* |
| flutter/editable_text.dart | `getEditableButtonItems` | 1 | 9 | *(n/a)* |
| flutter/editable_text.dart | `buildTextSpan` | 1 | 3 | *(n/a)* |
| flutter/editable_text.dart | `textInputConfiguration` | 3 | 0 | *(n/a)* |
| flutter/editable_text.dart | `_Editable` | 1 | 39 | *(n/a)* |
| flutter/editable_text.dart | `applyTextSpacingOverrides` | 1 | 4 | *(n/a)* |
| flutter/editable_text.dart | `ContentInsertionConfiguration` | 1 | 2 | *(n/a)* |
| flutter/editable_text.dart | `_UpdateTextSelectionAction` | 0 | 6 | *(n/a)* |
| flutter/editable_text.dart | `_RenderCompositionCallback` | 0 | 2 | *(n/a)* |

## fortran

### ❓ `fortran` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 14 occurrences as of 2026-08-19T23:13:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_physics_init.F | `bl_init` | 2461 | *(n/a)* | 2461 |
| wrf/module_physics_init.F | `ra_init` | 2033 | *(n/a)* | 2033 |
| wrf/module_physics_init.F | `landuse_init` | 1745 | *(n/a)* | 1745 |
| wrf/module_physics_init.F | `mp_init` | 4365 | *(n/a)* | 4365 |
| wrf/module_physics_init.F | `cu_init` | 3923 | *(n/a)* | 3923 |
| wrf/module_physics_init.F | `shcu_init` | 4217 | *(n/a)* | 4217 |
| wrf/module_physics_init.F | `CAM_INIT` | 5038 | *(n/a)* | 5038 |
| wrf/module_physics_init.F | `z2sigma` | 4965 | *(n/a)* | 4965 |
| wrf/module_physics_init.F | `fdob_init` | 4823 | *(n/a)* | 4823 |
| wrf/module_physics_init.F | `fg_init` | 4700 | *(n/a)* | 4700 |

### ❓ `fortran` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 8 occurrences as of 2026-08-19T23:13:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_configure.F | `module_scalar_tables` | *(n/a)* | 4 | *(n/a)* |
| wrf/module_configure.F | `module_irr_diag` | *(n/a)* | 20 | *(n/a)* |
| wrf/module_configure.F | `module_configure` | *(n/a)* | 51 | *(n/a)* |
| wrf/module_domain.F | `module_domain` | *(n/a)* | 26 | *(n/a)* |
| wrf/module_domain.F | `get_ijk_from_grid` | *(n/a)* | 67 | *(n/a)* |
| wrf/module_initialize_real.F | `module_initialize_real` | *(n/a)* | 9 | *(n/a)* |
| wrf/module_physics_init.F | `module_physics_init` | *(n/a)* | 10 | *(n/a)* |
| wrf/module_sf_noahdrv.F | `module_sf_noahdrv` | *(n/a)* | 1 | *(n/a)* |

### ❓ `fortran` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:13:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_configure.F | `in_use_for_config` | *(n/a)* | 353 | 353 |
| wrf/module_domain.F | `first_loc_integer` | *(n/a)* | 1693 | 1693 |

### ❓ `fortran` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:13:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_initialize_real.F | `vint` | 5375 | *(n/a)* | *(n/a)* |
| wrf/module_initialize_real.F | `foo` | 7519 | *(n/a)* | *(n/a)* |

### ❓ `fortran` function args: none agree, GitGalaxy, tree-sitter, ctags differ

*3-way split -- 1 occurrence as of 2026-08-19T23:13:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/args/agree[none]_vs[ctags,gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_physics_init.F | `phy_init` | 40 | 39 | 677 |

## go

### ❓ `go` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 75 occurrences as of 2026-08-19T23:13:28Z*

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

*2-vs-1 -- 103 occurrences as of 2026-08-19T23:13:30Z*

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

*2-vs-1 -- 69 occurrences as of 2026-08-19T23:13:30Z*

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

*2-vs-1 -- 16 occurrences as of 2026-08-19T23:13:30Z*

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

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:13:30Z*

**Verdict** (by Claude Sonnet 5 (session investigation), 2026-08-19T00:00:00Z):
> Mixed shape, resolved by reading both of the 2 occurrences directly (no larger sample needed). (1) Options.hs:438 getExtensions -- real function, `instance HasSyntaxExtensions WriterOptions where getExtensions opts = writerExtensions opts`. A sibling instance for ReaderOptions at Options.hs:80 has the identical shape. Tree-sitter's Haskell grammar doesn't expose typeclass-instance-method clause bodies the way it does top-level bindings, and ctags' Haskell parser has no instance-method kind either -- GitGalaxy is correct, both other tools have a real recall gap on typeclass instance methods. (2) Shared.hs:475 extensionEnabled -- NOT a real function. Imported from Text.Pandoc.Extensions (Shared.hs:114), only ever appears as a guard-clause call (`| extensionEnabled Ext_gfm_auto_identifiers exts = ...`). GitGalaxy's regex misreads a guard-clause invocation as a definition -- genuine GitGalaxy false positive, worth its own engine bug against language_standards.py's haskell func_start rule.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/Options.hs | `getExtensions` | 438 | *(n/a)* | *(n/a)* |
| pandoc/Shared.hs | `extensionEnabled` | 475 | *(n/a)* | *(n/a)* |

### ✅ `haskell` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 9 occurrences as of 2026-08-19T23:13:30Z*

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

## java

### ❓ `java` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 315 occurrences as of 2026-08-19T23:13:33Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`java/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| springboot/AutoConfigurationImportSelector.java | `filter` | 399 | 399 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `selectImports` | 118 | 118 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `selectImports` | 488 | 488 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `checkExcludedClasses` | 212 | 212 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `invokeAwareMethods` | 329 | 329 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `process` | 466 | 466 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `getExcludeAutoConfigurationsProperty` | 263 | 263 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `fireAutoConfigurationImportEvents` | 314 | 314 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `handleInvalidExcludes` | 230 | 230 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `AutoConfigurationImportSelector` | 109 | 109 | *(n/a)* |

### ❓ `java` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 28 occurrences as of 2026-08-19T23:13:33Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`java/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| springboot/AutoConfigurationImportSelector.java | `ConfigurationClassFilter` | *(n/a)* | 388 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `AutoConfigurationGroup` | *(n/a)* | 431 | *(n/a)* |
| springboot/AutoConfigurationImportSelector.java | `AutoConfigurationEntry` | *(n/a)* | 541 | *(n/a)* |
| springboot/Binder.java | `Context` | *(n/a)* | 581 | *(n/a)* |
| springboot/OnClassCondition.java | `OutcomesResolver` | *(n/a)* | 139 | *(n/a)* |
| springboot/OnClassCondition.java | `ThreadedOutcomesResolver` | *(n/a)* | 145 | *(n/a)* |
| springboot/OnClassCondition.java | `StandardOutcomesResolver` | *(n/a)* | 183 | *(n/a)* |
| springboot/ServletWebServerApplicationContext.java | `ExistingWebApplicationScopes` | *(n/a)* | 287 | *(n/a)* |
| springboot/SpringApplication.java | `Augmented` | *(n/a)* | 1490 | *(n/a)* |
| springboot/SpringApplication.java | `RunListener` | *(n/a)* | 1549 | *(n/a)* |

### ❓ `java` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:13:33Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`java/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| springboot/SpringApplication.java | `processUptime` | *(n/a)* | 1816 | *(n/a)* |
| springboot/SpringApplication.java | `action` | *(n/a)* | 1822 | *(n/a)* |
| springboot/SpringApplication.java | `startTime` | *(n/a)* | 1831 | *(n/a)* |

## javascript

### ❓ `javascript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 528 occurrences as of 2026-08-19T23:13:36Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `ajax` | 383 | 383 | *(n/a)* |
| jquery/ajax.js | `done` | 715 | 715 | *(n/a)* |
| jquery/ajax.js | `inspect` | 91 | 91 | *(n/a)* |
| jquery/ajax.js | `getResponseHeader` | 452 | 452 | *(n/a)* |
| jquery/ajax.js | `statusCode` | 498 | 498 | *(n/a)* |
| jquery/ajax.js | `setRequestHeader` | 480 | 480 | *(n/a)* |
| jquery/ajax.js | `abort` | 517 | 517 | *(n/a)* |
| jquery/ajax.js | `ajaxSetup` | 369 | 369 | *(n/a)* |
| jquery/ajax.js | `overrideMimeType` | 490 | 490 | *(n/a)* |
| jquery/ajax.js | `getAllResponseHeaders` | 475 | 475 | *(n/a)* |

### ❓ `javascript` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 183 occurrences as of 2026-08-19T23:13:36Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `javascript` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 104 occurrences as of 2026-08-19T23:13:36Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 346 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 3243 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 3305 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 3668 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 3770 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 3775 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 3811 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 3980 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 4077 | *(n/a)* |
| react/ReactFiberBeginWork.js | `if` | *(n/a)* | 4150 | *(n/a)* |

### ❓ `javascript` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 67 occurrences as of 2026-08-19T23:13:36Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/css.js | `cssShow` | *(n/a)* | *(n/a)* | 21 |
| jquery/event.js | `Event` | *(n/a)* | *(n/a)* | 617 |
| jquery/event.js | `event` | *(n/a)* | *(n/a)* | 89 |
| react/ReactFiberBeginWork.js | `cachePool` | *(n/a)* | *(n/a)* | 2281 |
| react/ReactFiberBeginWork.js | `derivedState` | *(n/a)* | *(n/a)* | 1245 |
| react/ReactFiberBeginWork.js | `initialState` | *(n/a)* | *(n/a)* | 1224 |
| react/ReactFiberBeginWork.js | `instance` | *(n/a)* | *(n/a)* | 3577 |
| react/ReactFiberBeginWork.js | `markerInstance` | *(n/a)* | *(n/a)* | 1297 |
| react/ReactFiberBeginWork.js | `memoizedState` | *(n/a)* | *(n/a)* | 3347 |
| react/ReactFiberBeginWork.js | `newOffscreenQueue` | *(n/a)* | *(n/a)* | 2452 |

### ❓ `javascript` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 10 occurrences as of 2026-08-19T23:13:36Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `javascript` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 8 occurrences as of 2026-08-19T23:13:36Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `AnonymousFunctionc3e813860800` | *(n/a)* | *(n/a)* | 857 |
| jquery/ajax.js | `AnonymousFunctionc3e813860900` | *(n/a)* | *(n/a)* | 879 |
| jquery/css.js | `AnonymousFunctionae2e564b0300` | *(n/a)* | *(n/a)* | 306 |
| jquery/css.js | `AnonymousFunctionae2e564b0500` | *(n/a)* | *(n/a)* | 356 |
| jquery/event.js | `AnonymousFunction9671c0e40a00` | *(n/a)* | *(n/a)* | 732 |
| jquery/event.js | `AnonymousFunction9671c0e40b00` | *(n/a)* | *(n/a)* | 811 |
| react/ReactFlightServer.js | `[ASYNC_ITERATOR]` | *(n/a)* | *(n/a)* | 1616 |
| react/ReactFlightServer.js | `[Symbol.iterator]` | *(n/a)* | *(n/a)* | 1576 |

### ❓ `javascript` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-19T23:13:36Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| react/ReactFiberBeginWork.js | `updateForwardRef` | 5 | 4 | 5 |
| react/ReactFiberBeginWork.js | `updateContextConsumer` | 3 | 2 | 3 |
| react/ReactFiberWorkLoop.js | `addMarkerProgressCallbackToPendingTransition` | 3 | 2 | 3 |
| react/ReactFiberWorkLoop.js | `addMarkerIncompleteCallbackToPendingTransition` | 3 | 1 | 3 |
| react/ReactFiberWorkLoop.js | `addMarkerCompleteCallbackToPendingTransition` | 2 | 1 | 2 |
| react/ReactFlightServer.js | `progress` | 1 | 2 | 1 |
| react/ReactFlightServer.js | `wrapperMethod` | 1 | 0 | 1 |

## kotlin

### ❓ `kotlin` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 15 occurrences as of 2026-08-19T23:13:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`kotlin/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `kotlin` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:13:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`kotlin/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| okhttp/OkHttp.android.kt | `OkHttp` | *(n/a)* | 22 | *(n/a)* |
| okhttp/OkHttp.jvm.kt | `OkHttp` | *(n/a)* | 20 | *(n/a)* |
| okhttp/OkHttp.kt | `OkHttp` | *(n/a)* | 18 | *(n/a)* |

### ❓ `kotlin` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`kotlin/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| okhttp/Dispatcher.kt | `constructor` | 119 | *(n/a)* | *(n/a)* |

## m4

### ❓ `m4` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 48 occurrences as of 2026-08-19T23:13:45Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`m4/function/existence/agree[ctags]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

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

### ❓ `m4` class existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-19T23:13:45Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`m4/class/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| curl/configure.ac | `SocketIFace` | *(n/a)* | *(n/a)* | *(n/a)* |
| curl/configure.ac | `Library` | *(n/a)* | *(n/a)* | *(n/a)* |
| curl/configure.ac | `sockaddr_in6` | *(n/a)* | *(n/a)* | *(n/a)* |
| gnucobol/configure.ac | `timespec` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `m4` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:45Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`m4/function/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| gnucobol/configure.ac | `AC_DEFUN` | 658 | *(n/a)* | *(n/a)* |

## makefile

### ❓ `makefile` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:46Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`makefile/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| freebsd/Makefile | `.PATH` | 4 | 4 | *(n/a)* |

## matlab

### ❓ `matlab` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 1 occurrence as of 2026-08-19T23:13:48Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`matlab/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| eeglab/eeglab.m | `ismatlab` | 1 | 0 | *(n/a)* |

## objective-c

### ❓ `objective-c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 120 occurrences as of 2026-08-19T23:13:49Z*

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

*2-vs-1 -- 71 occurrences as of 2026-08-19T23:13:49Z*

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
| worldwideweb/HyperManager.m | `closeOthers:` | *(n/a)* | *(n/a)* | 357 |

### ❓ `objective-c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:13:49Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/HyperText.m | `unsigned` | *(n/a)* | 1147 | *(n/a)* |
| worldwideweb/HyperText.m | `void` | *(n/a)* | 1289 | *(n/a)* |

### ❓ `objective-c` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:49Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/HyperText.m | `keyDown` | 1426 | *(n/a)* | *(n/a)* |

## perl

### ❓ `perl` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 122 occurrences as of 2026-08-19T23:13:56Z*

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

*2-vs-1 -- 7 occurrences as of 2026-08-19T23:13:56Z*

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

*2-vs-1 -- 7 occurrences as of 2026-08-19T23:13:56Z*

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

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| spamassassin/PerMsgStatus.pm | `Mail::SpamAssassin::PerMsgStatus` | *(n/a)* | *(n/a)* | 3022 |

### ❓ `perl` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:13:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mojo/Promise.pm | `get_p` | 277 | *(n/a)* | *(n/a)* |

### ❓ `perl` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 64 occurrences as of 2026-08-19T23:13:56Z*

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

### ❓ `php` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 68 occurrences as of 2026-08-19T23:14:00Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`php/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wordpress/class-wp-query.php | `get_posts` | 1890 | 1890 | *(n/a)* |
| wordpress/class-wp-query.php | `parse_query` | 803 | 803 | *(n/a)* |
| wordpress/class-wp-query.php | `parse_tax_query` | 1166 | 1166 | *(n/a)* |
| wordpress/class-wp-query.php | `parse_orderby` | 1688 | 1688 | *(n/a)* |
| wordpress/class-wp-query.php | `parse_search` | 1423 | 1423 | *(n/a)* |
| wordpress/class-wp-query.php | `get_queried_object` | 3968 | 3968 | *(n/a)* |
| wordpress/class-wp-query.php | `generate_cache_key` | 4975 | 4975 | *(n/a)* |
| wordpress/class-wp-query.php | `generate_postdata` | 4869 | 4869 | *(n/a)* |
| wordpress/class-wp-query.php | `set_found_posts` | 3676 | 3676 | *(n/a)* |
| wordpress/class-wp-query.php | `is_page` | 4554 | 4554 | *(n/a)* |

### ❓ `php` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:00Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`php/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| laravel_core/BladeCompiler.php | `AnonymousClassea70ff800100` | *(n/a)* | *(n/a)* | 342 |

### ❓ `php` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:00Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`php/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wordpress/formatting.php | `remove_accents` | 1610 | *(n/a)* | 1611 |

## powershell

### ❓ `powershell` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 16 occurrences as of 2026-08-19T23:14:03Z*

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

*2-vs-1 -- 7 occurrences as of 2026-08-19T23:14:03Z*

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

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/ci.psm1 | `Test-MergeConflictMarker` | 1020 | *(n/a)* | 1020 |

### ❓ `powershell` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 5 occurrences as of 2026-08-19T23:14:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/packaging.psm1 | `Start-PSPackage` | 0 | 12 | *(n/a)* |
| core/packaging.psm1 | `New-MSIPackage` | 11 | 10 | *(n/a)* |
| core/packaging.psm1 | `Invoke-AzDevOpsLinuxPackageBuild` | 0 | 2 | *(n/a)* |
| core/packaging.psm1 | `Invoke-AzDevOpsLinuxPackageCreation` | 0 | 3 | *(n/a)* |
| core/packaging.psm1 | `Get-LinuxPackageSemanticVersion` | 0 | 1 | *(n/a)* |

## python

### ❓ `python` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 68 occurrences as of 2026-08-19T23:14:12Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`python/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pxd | `_get_base` | *(n/a)* | *(n/a)* | 85 |
| cython/MemoryView.pxd | `array_cwrapper` | *(n/a)* | *(n/a)* | 53 |
| cython/MemoryView.pxd | `assign_item_from_object` | *(n/a)* | *(n/a)* | 84 |
| cython/MemoryView.pxd | `convert_item_to_object` | *(n/a)* | *(n/a)* | 83 |
| cython/MemoryView.pxd | `get_item_pointer` | *(n/a)* | *(n/a)* | 77 |
| cython/MemoryView.pxd | `get_memview` | *(n/a)* | *(n/a)* | 50 |
| cython/MemoryView.pxd | `is_slice` | *(n/a)* | *(n/a)* | 78 |
| cython/MemoryView.pxd | `memoryview_check` | *(n/a)* | *(n/a)* | 91 |
| cython/MemoryView.pxd | `memoryview_copy_contents` | *(n/a)* | *(n/a)* | 105 |
| cython/MemoryView.pxd | `memoryview_cwrapper` | *(n/a)* | *(n/a)* | 88 |

### ❓ `python` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 32 occurrences as of 2026-08-19T23:14:12Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`python/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pyx | `__cinit__` | 147 | *(n/a)* | 147 |
| cython/MemoryView.pyx | `__cinit__` | 361 | *(n/a)* | 361 |
| cython/MemoryView.pyx | `__getbuffer__` | 199 | *(n/a)* | 199 |
| cython/MemoryView.pyx | `__getbuffer__` | 552 | *(n/a)* | 552 |
| cython/MemoryView.pyx | `__setitem__` | 253 | *(n/a)* | 253 |
| cython/MemoryView.pyx | `__setitem__` | 440 | *(n/a)* | 440 |
| cython/MemoryView.pyx | `__dealloc__` | 226 | *(n/a)* | 226 |
| cython/MemoryView.pyx | `__dealloc__` | 390 | *(n/a)* | 390 |
| cython/MemoryView.pyx | `__dealloc__` | 947 | *(n/a)* | 947 |
| cython/MemoryView.pyx | `__getitem__` | 250 | *(n/a)* | 250 |

### ❓ `python` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 4 occurrences as of 2026-08-19T23:14:12Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`python/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pyx | `array` | *(n/a)* | *(n/a)* | 130 |
| cython/MemoryView.pyx | `Enum` | *(n/a)* | *(n/a)* | 318 |
| cython/MemoryView.pyx | `memoryview` | *(n/a)* | *(n/a)* | 348 |
| cython/MemoryView.pyx | `_memoryviewslice` | *(n/a)* | *(n/a)* | 936 |

### ❓ `python` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:12Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`python/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| numpy/crackfortran.py | `markoutercomma` | 2 | 2 | 3 |

## ruby

### ❓ `ruby` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 6 occurrences as of 2026-08-19T23:14:13Z*

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

*2-vs-1 -- 6 occurrences as of 2026-08-19T23:14:13Z*

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

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:14:13Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/base.rb | `process` | 2 | 1 | 2 |
| rails/base.rb | `process_action` | 1 | 0 | 1 |
| rails/metal.rb | `use` | 1 | 0 | 1 |

### ❓ `ruby` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:14:13Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/blob.rb | `Blob` | *(n/a)* | *(n/a)* | 19 |
| rails/inbound_emails_controller.rb | `InboundEmailsController` | *(n/a)* | *(n/a)* | 45 |

## rust

### ✅ `rust` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 152 occurrences as of 2026-08-19T23:14:17Z*

**Verdict** (by Claude Sonnet 5 (resolved from existing Claim 6 documentation, no dispatch), 2026-08-19T00:00:00Z):
> Not a new question -- already-documented, evidence-backed rust behavior (Claim 6, docs/why_gitgalaxy_beats_ast_here.md: 'structure recall inside opaque macro bodies'). Confirmed directly: all 5 sampled names (get_param, init_access, get_components, from_components, apply) are in bevy/bevy_ecs_macros.rs, inside a `quote! { ... }` proc-macro body (confirmed at source lines 444-460 -- `#path`/`#fields_alias` interpolation syntax is the classic quote! token-generation pattern). These are real Rust function definitions being code-generated by a proc macro; GitGalaxy's regex correctly parses real function syntax wherever it textually appears, including inside macro bodies. tree-sitter-rust and ctags' Rust parser both treat macro_rules!/macro-invocation bodies as opaque token trees and structurally cannot emit function nodes for anything inside one -- not a bug in either, a real grammar limitation. This is exactly why rust is one of the 3 languages (with csharp/fortran) already promoted into ground truth via blind-spot-region detection in the OLD bi-comparison tool (tree_sitter_accuracy_audit.py's _find_blind_spot_ranges) -- this tri-comparison ledger entry is that same, already-understood gap surfacing again under the new 3-tool reconciliation. GitGalaxy is correct; no engine defect, no issue needed. Resolved directly from existing documentation, no fresh dispatch required (tri-comparison-ledger-sweep skill step 1.3).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bevy/bevy_ecs_macros.rs | `get_param` | 456 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `init_access` | 444 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `get_components` | 158 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `from_components` | 191 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `apply` | 448 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `queue` | 452 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `build` | 406 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `map_entities` | 229 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `apply_effect` | 177 | *(n/a)* | *(n/a)* |
| bevy/bevy_ecs_macros.rs | `component_ids` | 141 | *(n/a)* | *(n/a)* |

### ✅ `rust` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 25 occurrences as of 2026-08-19T23:14:17Z*

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

### ✅ `rust` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 21 occurrences as of 2026-08-19T23:14:17Z*

**Verdict** (by Gemini (dispatched via tri-comparison-ledger-sweep, 2 rounds with self-correction), confirmed by Claude Sonnet 5, 2026-08-19T00:00:00Z):
> Confirmed GitGalaxy engine defect, same root cause as the sibling shape rust/function/args/agree[none]_vs[gitgalaxy,tree_sitter] (#1872): a Rust lifetime tick (`'_`, `'a`, `'static`) never gets recognized as non-string during bracket/quote scanning. This shape surfaces the SECOND manifestation, in a different function than the first: `_matching_paren_end` (gitgalaxy/core/detector.py:3675-3703) has NO lifetime guard at all (unlike _count_top_level_args's broken-but-present one). A lifetime tick makes its self-containment check falsely fail, falling through to the comma/whitespace-split fallback meant for Lisp/Scheme/Shell (~line 4296) -- for single-parameter signatures with a lifetime and no comma this OVER-counts (opposite direction from the sibling shape's under-count), for multi-param signatures it under-counts via the same swallowed-closing-paren mechanism. Extends the how_to_investigate_a_discrepancy.md worked example (bevy_ecs_table.rs::initialize, 5 real params, GitGalaxy reports 3) across the full 8-item sample, independently hand-traced and confirmed exact-match against real source for all 8: bevy_ecs_table.rs:171,194, bevy_ecs_world.rs:2969,3005, serde_internals_ast.rs:62 (under-count, multi-param); bevy_reflect_path.rs:43, serde_core_de_impls.rs:3147, serde_internals_ast.rs:119 (over-count, single-param via the whitespace-split fallback). Dispatched investigation initially produced a fabricated mechanism on its first pass; caught by the dispatching agent's own manual code trace, corrected on a second pass, then independently re-verified byte-for-byte against all 8 real signatures before being accepted here -- treat this as a genuinely double-checked finding, not a single-pass claim. ctags and tree-sitter are both correct in every case. Judged to plausibly explain most/all of the remaining 21 (any rust signature with a lifetime annotation is susceptible) and possibly under-reported beyond this specific ledger shape too, since lifetimes are extremely common idiomatic rust. Added as a follow-up comment on #1872 rather than a duplicate issue, since both bugs should be fixed together.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bevy/bevy_ecs_table.rs | `initialize` | 3 | 5 | 5 |
| bevy/bevy_ecs_table.rs | `replace` | 3 | 5 | 5 |
| bevy/bevy_ecs_world.rs | `insert_resource_by_id` | 3 | 4 | 4 |
| bevy/bevy_ecs_world.rs | `insert_non_send_by_id` | 3 | 4 | 4 |
| bevy/bevy_reflect_path.rs | `new` | 3 | 1 | 1 |
| serde/serde_core_de_impls.rs | `new` | 3 | 1 | 1 |
| serde/serde_internals_ast.rs | `from_ast` | 2 | 4 | 4 |
| serde/serde_internals_ast.rs | `all_fields` | 2 | 1 | 1 |
| serde/serde_internals_attr.rs | `none` | 1 | 2 | 2 |
| serde/serde_internals_attr.rs | `none` | 1 | 2 | 2 |

### ✅ `rust` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-19T23:14:17Z*

**Verdict** (by Claude Sonnet 5 (resolved directly via live ctags run, no dispatch), 2026-08-19T00:00:00Z):
> Confirmed structural ctags limitation, not a bug -- resolved directly (no dispatch needed). All 3 sampled names (XRegUnion, FRegUnion, VRegUnion) are real Rust `union { }` declarations (confirmed at wasmtime/wasmtime_pulley_interp.rs:404,529,604), distinct from `struct` -- Rust's less-common C-style unsafe union construct. Ran `ctags --list-kinds-full=Rust` directly: its Rust parser's kind list is macro/method/implementation/enumerator/function/enum/interface/field/module/struct/typedef/variable -- there is NO union kind at all. Confirmed via direct ctags run against this exact file: it correctly finds the wrapping `struct FRegVal(FRegUnion)`-shaped types right next to each missed union, so this isn't a general miss, specifically a missing Rust-union kind. Same category as the already-documented ctags Haskell class-kind gap (tests/tools/ctags_reader.py) -- worth a similar doc note there, not a GitHub issue (nothing to fix, ctags upstream has no union support for this language).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `XRegUnion` | *(n/a)* | 404 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `FRegUnion` | *(n/a)* | 529 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `VRegUnion` | *(n/a)* | 604 | *(n/a)* |

### ✅ `rust` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:17Z*

**Verdict** (by Claude Sonnet 5 (resolved directly via live ctags run, no dispatch), 2026-08-19T00:00:00Z):
> Confirmed via direct ctags run and sibling comparison, resolved directly (no dispatch needed). `done_decode` (wasmtime/wasmtime_pulley_interp.rs:964) has a destructuring-pattern parameter -- `Done { _priv }: Done`, not a simple `name: Type` binding. Ran ctags directly against the file: its IMMEDIATE SIBLING in the same impl block, `debug_assert_done_reason_none` (line 960, same visibility/receiver shape, ordinary `&mut self`-only signature), IS correctly found as a ctags 'method'. done_decode alone is missing from ctags' output. Isolates the cause precisely to the destructuring-pattern parameter -- ctags' regex-based Rust parser appears to fail/skip the whole function when a parameter is a struct pattern rather than a plain identifier binding. GitGalaxy and tree-sitter both handle this fine (both agree on line 964). N=1 in this corpus, plausibly a real, narrow ctags parser gap (not GitGalaxy's) -- not chasing further given the tiny sample, noting rather than filing an issue since there's nothing in this repo to fix.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `done_decode` | 964 | 964 | *(n/a)* |

### ✅ `rust` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 21 occurrences as of 2026-08-19T23:14:17Z*

**Verdict** (by Gemini (dispatched via tri-comparison-ledger-sweep), confirmed by Claude Sonnet 5, 2026-08-19T00:00:00Z):
> Confirmed GitGalaxy engine defect, not a modeling disagreement -- tree-sitter is correct in all 8 sampled cases (and this generalizes to the full 21: every sampled name is a deserialize_*/spawn_*_caller-shaped signature carrying a rust lifetime annotation, the exact trigger). Root cause, independently confirmed via two methods (dispatched agent read the code path; a second grep pass confirmed the attribute is dead): `gitgalaxy/core/detector.py::StructuralExtractor._count_top_level_args` has a guard meant to exempt rust/scala lifetime marks (`'_`, `'static`) from its string-literal scanner -- `getattr(self, 'language', '') in ('rust', 'scala')` around line 3766 -- but the class stores the language as `self.primary_lang_id` (set at line 497), never `self.language`. `self.language` is referenced NOWHERE ELSE in the file, confirmed by grep. The getattr always silently falls back to `''`, so the exemption guard never fires for any language, ever -- every lifetime `'` gets treated as an unterminated string-literal opener, swallowing all subsequent top-level commas until a real closing quote or end-of-string, fusing 2+ parameters into 1. A signature with 3 lifetime marks (odd count) never exits string mode at all and undercounts every remaining parameter. Real signatures confirmed at source: bevy/bevy_ecs_world.rs:1106,1121,1270 (`MovingPtr<'_, B>` swallows the next comma, 3 vs real 4, or 2 vs real 3); serde/serde_core_de_mod.rs:1105,1115 (`&'static str` swallows the next comma, 2 vs real 3); serde_core_de_mod.rs:1136 (two lifetimes, both trailing commas swallowed, 2 vs real 4); serde_core_de_mod.rs:1152,1163 (three lifetime marks, odd count means string mode never exits, 2 vs real 4). ctags has null coverage for these specific occurrences because they're bodyless trait-method declarations (ending in `;` inside a `trait` block) -- unrelated to the args bug, ctags appears to skip signature-only declarations generally. Filed as its own GitHub issue (attribute-name mismatch, one-line fix: `self.language` -> `self.primary_lang_id`, or equivalent), separate from this ledger record.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bevy/bevy_ecs_world.rs | `spawn_at_unchecked` | 3 | 4 | *(n/a)* |
| bevy/bevy_ecs_world.rs | `spawn_at_with_caller` | 3 | 4 | *(n/a)* |
| bevy/bevy_ecs_world.rs | `spawn_with_caller` | 2 | 3 | *(n/a)* |
| serde/serde_core_de_mod.rs | `deserialize_unit_struct` | 2 | 3 | *(n/a)* |
| serde/serde_core_de_mod.rs | `deserialize_newtype_struct` | 2 | 3 | *(n/a)* |
| serde/serde_core_de_mod.rs | `deserialize_tuple_struct` | 2 | 4 | *(n/a)* |
| serde/serde_core_de_mod.rs | `deserialize_struct` | 2 | 4 | *(n/a)* |
| serde/serde_core_de_mod.rs | `deserialize_enum` | 2 | 4 | *(n/a)* |
| serde/serde_internals_ast.rs | `enum_from_ast` | 2 | 4 | *(n/a)* |
| serde/serde_internals_ast.rs | `fields_from_ast` | 2 | 5 | *(n/a)* |

## scala

### ❓ `scala` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 16 occurrences as of 2026-08-19T23:14:20Z*

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

### ❓ `scheme` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 92 occurrences as of 2026-08-19T23:14:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`scheme/function/existence/agree[ctags]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| racket/schemify.rkt | `make-define-variable` | *(n/a)* | *(n/a)* | 471 |
| racket/schemify.rkt | `make-expr-defn` | *(n/a)* | *(n/a)* | 477 |
| racket/schemify.rkt | `make-set-consistent-variables` | *(n/a)* | *(n/a)* | 462 |
| racket/schemify.rkt | `make-set-variable` | *(n/a)* | *(n/a)* | 456 |
| racket/schemify.rkt | `schemify` | *(n/a)* | *(n/a)* | 496 |
| racket/schemify.rkt | `schemify-body` | *(n/a)* | *(n/a)* | 200 |
| racket/schemify.rkt | `schemify-body*` | *(n/a)* | *(n/a)* | 210 |
| racket/schemify.rkt | `schemify-linklet` | *(n/a)* | *(n/a)* | 83 |
| racket/schemify.rkt | `variable-constance` | *(n/a)* | *(n/a)* | 480 |
| racket/thread.rkt | `add-custodian-to-thread!` | *(n/a)* | *(n/a)* | 752 |

## shell

### ❓ `shell` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`shell/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| brew/brew | `FILTERED_ENV=` | *(n/a)* | *(n/a)* | 292 |

## solidity

### ❓ `solidity` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-08-19T23:14:27Z*

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

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/ParameterEncoder.swift | `encode` | 159 | *(n/a)* | *(n/a)* |

### ❓ `swift` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/Request.swift | `==` | *(n/a)* | 1119 | *(n/a)* |

### ❓ `swift` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 1 occurrence as of 2026-08-19T23:14:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/Session.swift | `performSetupOperations` | 0 | 3 | *(n/a)* |

## tcl

### ❓ `tcl` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-19T23:14:30Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/malloc_common.tcl | `faultsim_test_proc` | 347 | 347 | *(n/a)* |
| sqlite/tester.tcl | `set_test_counter` | 583 | 583 | *(n/a)* |
| sqlite/tester.tcl | `sqlite3` | 116 | 116 | *(n/a)* |
| sqlite/tester.tcl | `finish_test` | 1243 | 1243 | *(n/a)* |

### ❓ `tcl` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:14:30Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/tester.tcl | `drop_all_tables` | *(n/a)* | 2254 | 2254 |
| sqlite/tester.tcl | `drop_all_indexes` | *(n/a)* | 2279 | 2279 |

### ❓ `tcl` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:30Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/tester.tcl | `do_test` | 703 | *(n/a)* | 703 |

### ❓ `tcl` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:30Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/malloc_common.tcl | `faultsim_test_result` | 348 | *(n/a)* | *(n/a)* |

## typescript

### ❓ `typescript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 2103 occurrences as of 2026-08-19T23:14:51Z*

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

*2-vs-1 -- 515 occurrences as of 2026-08-19T23:14:51Z*

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

*2-vs-1 -- 175 occurrences as of 2026-08-19T23:14:51Z*

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

*2-vs-1 -- 61 occurrences as of 2026-08-19T23:14:51Z*

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

*2-vs-1 -- 8 occurrences as of 2026-08-19T23:14:51Z*

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

### ❓ `typescript` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-19T23:14:51Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| vscode/lifecycle.ts | `createReferencedObject` | 711 | *(n/a)* | *(n/a)* |
| vscode/lifecycle.ts | `destroyReferencedObject` | 712 | *(n/a)* | *(n/a)* |

## zig

### ❓ `zig` class existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 10 occurrences as of 2026-08-19T23:14:59Z*

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

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:59Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`zig/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bun/MimallocArena.zig | `Borrowed` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `zig` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-19T23:14:59Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`zig/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| zig/InternPool.zig | `dbHelper` | *(n/a)* | 4823 | *(n/a)* |
