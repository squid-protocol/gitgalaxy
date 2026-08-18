# Tri-Comparison Points of Interest

Generated from `tri_comparison_ledger.json` by `tests/tools/tri_comparison_report.py --write` -- do not hand-edit this file, edit the ledger and regenerate. See `docs/self_scan/how_to_investigate_a_discrepancy.md` for what ❓ entries are asking for.

Sorted 2-vs-1 splits before 3-way splits, unvalidated before validated, biggest occurrence count first within each tier -- see this script's own module docstring for why that order.

## agc_assembly

### ❓ `agc_assembly` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 760 occurrences as of 2026-08-18T21:01:21Z*

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

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:38:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`apex/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| apex-recipes/AuraEnabledRecipes_Tests.cls | `Account` | 25 | *(n/a)* | *(n/a)* |
| apex-recipes/AuraEnabledRecipes_Tests.cls | `Account` | 43 | *(n/a)* | *(n/a)* |

## assembly

### ❓ `assembly` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 52 occurrences as of 2026-08-18T21:01:21Z*

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

*2-vs-1 -- 7 occurrences as of 2026-08-18T21:01:21Z*

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

### ❓ `c` class existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 525 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/class/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/ceval.c | `_py_code_state` | *(n/a)* | 3577 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 101 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 187 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 223 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 223 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 239 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 247 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 251 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 263 | *(n/a)* |
| cpython/compile.c | `compiler_unit` | *(n/a)* | 586 | *(n/a)* |

### ❓ `c` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 104 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/ceval.c | `PyEval_GetLocals` | 0 | 0 | 1 |
| cpython/ceval.c | `_PyEval_GetFrameLocals` | 0 | 0 | 1 |
| cpython/ceval.c | `PyEval_GetFrame` | 0 | 0 | 1 |
| cpython/ceval.c | `PyEval_GetFrameGlobals` | 0 | 0 | 1 |
| cpython/ceval.c | `Py_GetRecursionLimit` | 0 | 0 | 1 |
| cpython/ceval.c | `_PyEval_GetCoroutineOriginTrackingDepth` | 0 | 0 | 1 |
| cpython/ceval.c | `_PyEval_GetAsyncGenFirstiter` | 0 | 0 | 1 |
| cpython/ceval.c | `_PyEval_GetAsyncGenFinalizer` | 0 | 0 | 1 |
| cpython/ceval.c | `_PyEval_GetFrame` | 0 | 0 | 1 |
| cpython/ceval.c | `PyEval_GetBuiltins` | 0 | 0 | 1 |

### ❓ `c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 74 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

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

### ❓ `c` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 23 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/ceval.c | `__anona8bd960a0108` | *(n/a)* | *(n/a)* | 94 |
| cpython/dictobject.c | `__anonc22296ba0108` | *(n/a)* | *(n/a)* | 5420 |
| cpython/object.c | `__anond0de49f60108` | *(n/a)* | *(n/a)* | 2973 |
| cpython/typeobject.c | `__anon886280780108` | *(n/a)* | *(n/a)* | 3808 |
| cpython/typeobject.c | `__anon886280780208` | *(n/a)* | *(n/a)* | 3830 |
| cpython/typeobject.c | `__anon886280780308` | *(n/a)* | *(n/a)* | 3936 |
| cpython/typeobject.c | `__anon886280780408` | *(n/a)* | *(n/a)* | 4191 |
| cpython/typeobject.c | `__anon886280780508` | *(n/a)* | *(n/a)* | 12342 |
| doom/r_bsp.c | `__anon0e1b013f0108` | *(n/a)* | *(n/a)* | 81 |
| doom/r_defs.h | `__anond523c6a10108` | *(n/a)* | *(n/a)* | 72 |

### ❓ `c` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 13 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `c` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 9 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/frameobject.c | `kind` | *(n/a)* | 1175 | *(n/a)* |
| cpython/gc.c | `flagstates` | *(n/a)* | 377 | *(n/a)* |
| micropython/objtype.c | `_setname_list_t` | *(n/a)* | 980 | *(n/a)* |
| sqlite/lemon.c | `option_type` | *(n/a)* | 271 | *(n/a)* |
| sqlite/lemon.c | `symbol_type` | *(n/a)* | 319 | *(n/a)* |
| sqlite/lemon.c | `e_assoc` | *(n/a)* | 324 | *(n/a)* |
| sqlite/lemon.c | `cfgstatus` | *(n/a)* | 389 | *(n/a)* |
| sqlite/lemon.c | `e_action` | *(n/a)* | 405 | *(n/a)* |
| sqlite/lemon.c | `e_state` | *(n/a)* | 2323 | *(n/a)* |

### ❓ `c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 8 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

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

### ❓ `c` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `RICHCMP_WRAPPER` | *(n/a)* | *(n/a)* | 10099 |
| cpython/typeobject.c | `SLOT0` | *(n/a)* | *(n/a)* | 10626 |
| cpython/typeobject.c | `SLOT0` | *(n/a)* | *(n/a)* | 10682 |
| cpython/typeobject.c | `SLOT0` | *(n/a)* | *(n/a)* | 10728 |
| cpython/typeobject.c | `SLOT1` | *(n/a)* | *(n/a)* | 10542 |
| cpython/typeobject.c | `SLOT1` | *(n/a)* | *(n/a)* | 10703 |
| cpython/typeobject.c | `SLOT1BINFULL` | *(n/a)* | *(n/a)* | 10575 |

### ❓ `c` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `slot_tp_hash` | 10730 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_mp_ass_subscript` | 10544 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_tp_repr` | 10714 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_nb_inplace_power` | 10697 | *(n/a)* | *(n/a)* |

### ❓ `c` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython/emitnative.c | `EXPORT_FUN` | *(n/a)* | 300 | 300 |
| micropython/emitnative.c | `EXPORT_FUN` | *(n/a)* | 320 | 320 |
| micropython/vm.c | `MICROPY_WRAP_MP_EXECUTE_BYTECODE` | *(n/a)* | 220 | 220 |

### ❓ `c` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:24Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`c/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython/gc.c | `gc_mark_subtree` | 2 | 1 | 2 |

## cobol

### ❓ `cobol` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 133 occurrences as of 2026-08-18T21:38:28Z*

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

*2-vs-1 -- 19 occurrences as of 2026-08-18T21:38:28Z*

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

*2-vs-1 -- 18 occurrences as of 2026-08-18T21:38:28Z*

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

*2-vs-1 -- 1270 occurrences as of 2026-08-18T21:01:28Z*

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

*2-vs-1 -- 1061 occurrences as of 2026-08-18T21:01:28Z*

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

*2-vs-1 -- 120 occurrences as of 2026-08-18T21:01:28Z*

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

*2-vs-1 -- 98 occurrences as of 2026-08-18T21:01:28Z*

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

*2-vs-1 -- 70 occurrences as of 2026-08-18T21:01:28Z*

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

*2-vs-1 -- 24 occurrences as of 2026-08-18T21:01:28Z*

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

*2-vs-1 -- 22 occurrences as of 2026-08-18T21:01:28Z*

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

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mlir/flatbuffer_export.cc | `GetTFLiteType` | 2 | 1 | 2 |
| mlir/flatbuffer_export.cc | `Insert` | 5 | 4 | 5 |
| mlir/flatbuffer_export.cc | `ExportBuffer` | 4 | 3 | 4 |

### ❓ `cpp` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:01:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `HashMapComparatorDefault` | *(n/a)* | *(n/a)* | 886 |
| godot/variant.h | `is_zero_constructible` | *(n/a)* | *(n/a)* | 984 |

### ❓ `cpp` function args: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/args/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| NVDA/storage.cpp | `outputEscapedAttribute` | 0 | 2 | 3 |

### ❓ `cpp` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `call` | 2 | 2 | 1 |

### ❓ `cpp` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`cpp/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mlir/flatbuffer_export.cc | `Translator` | *(n/a)* | 654 | 654 |

## csharp

### ❓ `csharp` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 271 occurrences as of 2026-08-18T21:01:31Z*

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

*2-vs-1 -- 108 occurrences as of 2026-08-18T21:01:31Z*

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

*2-vs-1 -- 48 occurrences as of 2026-08-18T21:01:31Z*

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

*2-vs-1 -- 7 occurrences as of 2026-08-18T21:01:31Z*

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

*2-vs-1 -- 6 occurrences as of 2026-08-18T21:01:31Z*

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

*2-vs-1 -- 5 occurrences as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `TerminatorState` | *(n/a)* | 57 | *(n/a)* |
| roslyn/LanguageParser.cs | `NamespaceParts` | *(n/a)* | 399 | *(n/a)* |
| roslyn/LanguageParser.cs | `LanguageParserState` | *(n/a)* | 4295 | *(n/a)* |
| roslyn/LanguageParser.cs | `AccessorDeclaringKind` | *(n/a)* | 4342 | *(n/a)* |
| roslyn/LanguageParser.cs | `PostSkipAction` | *(n/a)* | 4472 | *(n/a)* |

### ❓ `csharp` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `GetHashCode` | 1 | 1 | 0 |
| roslyn/LanguageParser.cs | `GetModifierExcludingScoped` | 1 | 1 | 2 |
| roslyn/Workspace.cs | `SetCurrentSolution` | 1 | 1 | 6 |
| roslyn/Workspace.cs | `SetCurrentSolution` | 6 | 6 | 4 |

### ❓ `csharp` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 4 occurrences as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `ShouldCheckTypeForMembers` | *(n/a)* | 5268 | 5268 |
| roslyn/CSharpCompilation.cs | `Matches` | *(n/a)* | 5281 | 5281 |
| roslyn/CSharpSyntaxTree.cs | `GetRoot` | *(n/a)* | 86 | 86 |
| roslyn/DiagnosticAnalyzer.cs | `Initialize` | *(n/a)* | 24 | 24 |

### ❓ `csharp` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `LanguageParser` | *(n/a)* | *(n/a)* | 20 |
| roslyn/LanguageParser.cs | `DisposableResetPoint` | *(n/a)* | *(n/a)* | 14575 |
| roslyn/LanguageParser.cs | `ResetPoint` | *(n/a)* | *(n/a)* | 14600 |

### ❓ `csharp` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `Equals` | 1 | 2 | 1 |

### ❓ `csharp` function args: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/args/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/Workspace.cs | `SetCurrentSolution` | 0 | 4 | 5 |

### ❓ `csharp` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpSyntaxTree.cs | `TryGetRoot` | *(n/a)* | 91 | *(n/a)* |

## css

### ❓ `css` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 112 occurrences as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`css/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| element/common.css | `.is-component` | *(n/a)* | 10 | *(n/a)* |
| element/common.css | `.is-component` | *(n/a)* | 18 | *(n/a)* |
| element/common.css | `.is-component` | *(n/a)* | 166 | *(n/a)* |
| element/common.css | `#app` | *(n/a)* | 15 | *(n/a)* |
| element/common.css | `#app` | *(n/a)* | 166 | *(n/a)* |
| element/common.css | `.main-cnt` | *(n/a)* | 73 | *(n/a)* |
| element/common.css | `.headerWrapper` | *(n/a)* | 28 | *(n/a)* |
| element/common.css | `.headerWrapper` | *(n/a)* | 166 | *(n/a)* |
| element/common.css | `.container` | *(n/a)* | 161 | *(n/a)* |
| element/common.css | `.container` | *(n/a)* | 166 | *(n/a)* |

### ❓ `css` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 85 occurrences as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`css/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| element/common.css | `#app.is-component .headerWrapper .container` | *(n/a)* | *(n/a)* | 166 |
| element/fonts-baseline.css | `.icon-rate-face-1:before` | *(n/a)* | *(n/a)* | 30 |
| element/fonts-baseline.css | `.icon-rate-face-2:before` | *(n/a)* | *(n/a)* | 33 |
| element/fonts-baseline.css | `.icon-rate-face-3:before` | *(n/a)* | *(n/a)* | 36 |
| element/fonts-baseline.css | `.icon-rate-face-off:before` | *(n/a)* | *(n/a)* | 27 |
| odoo/control_panel_mobile.css | `.o-control-panel-adaptive-dropdown.dropdown-menu > :nth-child(1 of :not(.d-none` | *(n/a)* | *(n/a)* | 24 |
| odoo/control_panel_mobile.css | `.o_control_panel_main_buttons:has(> .o-control-panel-adaptive-dropdown:only-child)` | *(n/a)* | *(n/a)* | 19 |
| odoo/control_panel_mobile.css | `.o_hidden))` | *(n/a)* | *(n/a)* | 24 |
| odoo/icons-baseline.css | `.o_rtl .oi-arrow-down-left` | *(n/a)* | *(n/a)* | 99 |
| odoo/icons-baseline.css | `.o_rtl .oi-arrow-down-right` | *(n/a)* | *(n/a)* | 100 |

### ❓ `css` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:31Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`css/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| element/common.css | `media` | 153 | 153 | *(n/a)* |
| element/common.css | `media` | 160 | 160 | *(n/a)* |
| odoo/control_panel_mobile.css | `media` | 1 | 1 | *(n/a)* |

## dart

### ❓ `dart` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 216 occurrences as of 2026-08-18T21:01:33Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`dart/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `dart` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 37 occurrences as of 2026-08-18T21:01:33Z*

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

*2-vs-1 -- 18 occurrences as of 2026-08-18T21:01:33Z*

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

## fortran

### ❓ `fortran` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 14 occurrences as of 2026-08-18T21:01:35Z*

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

*2-vs-1 -- 8 occurrences as of 2026-08-18T21:01:35Z*

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

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:01:35Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_configure.F | `in_use_for_config` | *(n/a)* | 353 | 353 |
| wrf/module_domain.F | `first_loc_integer` | *(n/a)* | 1693 | 1693 |

### ❓ `fortran` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:01:35Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_initialize_real.F | `vint` | 5375 | *(n/a)* | *(n/a)* |
| wrf/module_initialize_real.F | `foo` | 7519 | *(n/a)* | *(n/a)* |

### ❓ `fortran` function args: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:35Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/args/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_physics_init.F | `phy_init` | 40 | 39 | 677 |

## go

### ❓ `go` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 75 occurrences as of 2026-08-18T21:01:36Z*

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

### ❓ `haskell` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 91 occurrences as of 2026-08-18T21:01:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/App.hs | `isPandocCiteproc` | *(n/a)* | 271 | *(n/a)* |
| pandoc/Filter.hs | `applyFilter` | *(n/a)* | 89 | *(n/a)* |
| pandoc/Filter.hs | `applyFilter` | *(n/a)* | 91 | *(n/a)* |
| pandoc/Filter.hs | `toJSON` | *(n/a)* | 70 | *(n/a)* |
| pandoc/Filter.hs | `toJSON` | *(n/a)* | 72 | *(n/a)* |
| pandoc/Options.hs | `toJSON` | *(n/a)* | 172 | *(n/a)* |
| pandoc/Options.hs | `toJSON` | *(n/a)* | 173 | *(n/a)* |
| pandoc/Options.hs | `toJSON` | *(n/a)* | 174 | *(n/a)* |
| pandoc/Options.hs | `toJSON` | *(n/a)* | 191 | *(n/a)* |
| pandoc/Options.hs | `toJSON` | *(n/a)* | 192 | *(n/a)* |

### ❓ `haskell` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 69 occurrences as of 2026-08-18T21:01:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

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

### ❓ `haskell` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 64 occurrences as of 2026-08-18T21:01:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/Options.hs | `class` | *(n/a)* | *(n/a)* | 62 |
| pandoc/Options.hs | `defaultAbbrevs` | *(n/a)* | *(n/a)* | 96 |
| pandoc/Options.hs | `defaultKaTeXURL` | *(n/a)* | *(n/a)* | 451 |
| pandoc/Options.hs | `defaultMathJaxURL` | *(n/a)* | *(n/a)* | 445 |
| pandoc/Options.hs | `defaultWebTeXURL` | *(n/a)* | *(n/a)* | 448 |
| pandoc/Options.hs | `deriveJSON` | *(n/a)* | *(n/a)* | 454 |
| pandoc/Options.hs | `deriveJSON` | *(n/a)* | *(n/a)* | 458 |
| pandoc/Options.hs | `pattern` | *(n/a)* | *(n/a)* | 204 |
| pandoc/Options.hs | `pattern` | *(n/a)* | *(n/a)* | 205 |
| pandoc/Options.hs | `pattern` | *(n/a)* | *(n/a)* | 208 |

### ❓ `haskell` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 38 occurrences as of 2026-08-18T21:01:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/App.hs | `writerFn` | *(n/a)* | 426 | 426 |
| pandoc/App.hs | `writeFnBinary` | *(n/a)* | 422 | 422 |
| pandoc/Filter.hs | `expandFilterPath` | *(n/a)* | 106 | 106 |
| pandoc/Filter.hs | `expandFilterPath` | *(n/a)* | 107 | 107 |
| pandoc/Shared.hs | `tabFilter` | *(n/a)* | 260 | 260 |
| pandoc/Shared.hs | `compactify` | *(n/a)* | 408 | 408 |
| pandoc/Shared.hs | `camelCaseStrToHyphenated` | *(n/a)* | 226 | 226 |
| pandoc/Shared.hs | `camelCaseStrToHyphenated` | *(n/a)* | 230 | 230 |
| pandoc/Shared.hs | `camelCaseStrToHyphenated` | *(n/a)* | 234 | 234 |
| pandoc/Shared.hs | `blockToInlines` | *(n/a)* | 796 | 796 |

### ❓ `haskell` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 16 occurrences as of 2026-08-18T21:01:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

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

### ❓ `haskell` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 9 occurrences as of 2026-08-18T21:01:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `haskell` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:01:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/Options.hs | `getExtensions` | 438 | *(n/a)* | *(n/a)* |
| pandoc/Shared.hs | `extensionEnabled` | 475 | *(n/a)* | *(n/a)* |

## java

### ❓ `java` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 315 occurrences as of 2026-08-18T21:01:38Z*

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

*2-vs-1 -- 28 occurrences as of 2026-08-18T21:01:38Z*

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

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:38Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`java/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| springboot/SpringApplication.java | `processUptime` | *(n/a)* | 1816 | *(n/a)* |
| springboot/SpringApplication.java | `action` | *(n/a)* | 1822 | *(n/a)* |
| springboot/SpringApplication.java | `startTime` | *(n/a)* | 1831 | *(n/a)* |

## javascript

### ❓ `javascript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 529 occurrences as of 2026-08-18T21:01:39Z*

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

*2-vs-1 -- 182 occurrences as of 2026-08-18T21:01:39Z*

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

*2-vs-1 -- 104 occurrences as of 2026-08-18T21:01:39Z*

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

### ❓ `javascript` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 11 occurrences as of 2026-08-18T21:01:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| react/ReactFiberBeginWork.js | `updateContextProvider` | 3658 | *(n/a)* | 3658 |
| react/ReactFiberBeginWork.js | `reconcileChildren` | 340 | *(n/a)* | 340 |
| react/ReactFiberBeginWork.js | `updateScopeComponent` | 3727 | *(n/a)* | 3727 |
| react/ReactFiberBeginWork.js | `markWorkInProgressReceivedUpdate` | 3739 | *(n/a)* | 3739 |
| react/ReactFiberWorkLoop.js | `onResolution` | 2837 | *(n/a)* | 2837 |
| react/ReactFiberWorkLoop.js | `shouldForceFlushFallbacksInDEV` | 5539 | *(n/a)* | 5539 |
| react/ReactFlightServer.js | `patchConsole` | 386 | *(n/a)* | 386 |
| react/ReactFlightServer.js | `abortIterable` | 1367 | *(n/a)* | 1367 |
| react/ReactFlightServer.js | `abortStream` | 1233 | *(n/a)* | 1233 |
| react/ReactFlightServer.js | `error` | 1222 | *(n/a)* | 1222 |

### ❓ `javascript` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 8 occurrences as of 2026-08-18T21:01:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `anonymousFunction5b3e322c0800` | *(n/a)* | *(n/a)* | 857 |
| jquery/ajax.js | `anonymousFunction5b3e322c0b00` | *(n/a)* | *(n/a)* | 879 |
| jquery/css.js | `anonymousFunctionc24838310200` | *(n/a)* | *(n/a)* | 306 |
| jquery/css.js | `anonymousFunctionc24838310500` | *(n/a)* | *(n/a)* | 356 |
| jquery/event.js | `anonymousFunction188bb44a0f00` | *(n/a)* | *(n/a)* | 732 |
| jquery/event.js | `anonymousFunction188bb44a1100` | *(n/a)* | *(n/a)* | 811 |
| react/ReactFlightServer.js | `[ASYNC_ITERATOR]` | *(n/a)* | *(n/a)* | 1616 |
| react/ReactFlightServer.js | `[Symbol.iterator]` | *(n/a)* | *(n/a)* | 1576 |

### ❓ `javascript` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-18T21:01:39Z*

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

### ❓ `javascript` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-08-18T21:01:39Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`javascript/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/deferred.js | `Identity` | *(n/a)* | *(n/a)* | 6 |
| jquery/deferred.js | `Thrower` | *(n/a)* | *(n/a)* | 9 |
| jquery/event.js | `Event` | *(n/a)* | *(n/a)* | 617 |
| threejs/Editor.js | `Editor` | *(n/a)* | *(n/a)* | 15 |
| threejs/GLTFLoader.js | `GLTFRegistry` | *(n/a)* | *(n/a)* | 576 |
| threejs/WebGLProgram.js | `WebGLProgram` | *(n/a)* | *(n/a)* | 412 |

## kotlin

### ❓ `kotlin` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 15 occurrences as of 2026-08-18T21:01:40Z*

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

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`kotlin/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| okhttp/OkHttp.android.kt | `OkHttp` | *(n/a)* | 22 | *(n/a)* |
| okhttp/OkHttp.jvm.kt | `OkHttp` | *(n/a)* | 20 | *(n/a)* |
| okhttp/OkHttp.kt | `OkHttp` | *(n/a)* | 18 | *(n/a)* |

### ❓ `kotlin` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:40Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`kotlin/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| okhttp/Dispatcher.kt | `constructor` | 119 | *(n/a)* | *(n/a)* |

## m4

### ❓ `m4` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 147 occurrences as of 2026-08-18T21:01:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`m4/function/existence/agree[ctags]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| curl/configure.ac | `CURL_CA_NATIVE` | *(n/a)* | *(n/a)* | 2127 |
| curl/configure.ac | `CURL_CA_SEARCH_SAFE` | *(n/a)* | *(n/a)* | 2199 |
| curl/configure.ac | `CURL_DEBUG_GLOBAL_MEM` | *(n/a)* | *(n/a)* | 1097 |
| curl/configure.ac | `CURL_DEFAULT_SSL_BACKEND` | *(n/a)* | *(n/a)* | 2112 |
| curl/configure.ac | `CURL_DISABLE_ALTSVC` | *(n/a)* | *(n/a)* | 762 |
| curl/configure.ac | `CURL_DISABLE_ALTSVC` | *(n/a)* | *(n/a)* | 4832 |
| curl/configure.ac | `CURL_DISABLE_AWS` | *(n/a)* | *(n/a)* | 4469 |
| curl/configure.ac | `CURL_DISABLE_BASIC_AUTH` | *(n/a)* | *(n/a)* | 4372 |
| curl/configure.ac | `CURL_DISABLE_BEARER_AUTH` | *(n/a)* | *(n/a)* | 4391 |
| curl/configure.ac | `CURL_DISABLE_BINDLOCAL` | *(n/a)* | *(n/a)* | 4671 |

### ❓ `m4` class existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-18T21:01:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`m4/class/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| curl/configure.ac | `SocketIFace` | *(n/a)* | *(n/a)* | *(n/a)* |
| curl/configure.ac | `Library` | *(n/a)* | *(n/a)* | *(n/a)* |
| curl/configure.ac | `sockaddr_in6` | *(n/a)* | *(n/a)* | *(n/a)* |
| gnucobol/configure.ac | `timespec` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `m4` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`m4/function/existence/agree[gitgalaxy]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| gnucobol/configure.ac | `AC_DEFUN` | 658 | *(n/a)* | *(n/a)* |

## makefile

### ❓ `makefile` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`makefile/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| freebsd/Makefile | `.PATH` | 4 | 4 | *(n/a)* |

## matlab

### ❓ `matlab` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:43Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`matlab/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| eeglab/eeglab.m | `ismatlab` | 1 | 0 | *(n/a)* |

## objective-c

### ❓ `objective-c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 120 occurrences as of 2026-08-18T21:01:43Z*

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

*2-vs-1 -- 70 occurrences as of 2026-08-18T21:01:43Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/Anchor.m | `linkTo:` | *(n/a)* | *(n/a)* | 331 |
| worldwideweb/Anchor.m | `selectDiagnostic:` | *(n/a)* | *(n/a)* | 277 |
| worldwideweb/Anchor.m | `setAddress:` | *(n/a)* | *(n/a)* | 313 |
| worldwideweb/Anchor.m | `setNode:` | *(n/a)* | *(n/a)* | 263 |
| worldwideweb/HyperManager.m | `accessName:Diagnostic:` | *(n/a)* | *(n/a)* | 155 |
| worldwideweb/HyperManager.m | `appAcceptsAnotherFile:` | *(n/a)* | *(n/a)* | 253 |
| worldwideweb/HyperManager.m | `appDidInit:` | *(n/a)* | *(n/a)* | 239 |
| worldwideweb/HyperManager.m | `appOpenFile:type:` | *(n/a)* | *(n/a)* | 260 |
| worldwideweb/HyperManager.m | `appOpenTempFile:type:` | *(n/a)* | *(n/a)* | 272 |
| worldwideweb/HyperManager.m | `closeOthers:` | *(n/a)* | *(n/a)* | 356 |

### ❓ `objective-c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:01:43Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/HyperText.m | `unsigned` | *(n/a)* | 1147 | *(n/a)* |
| worldwideweb/HyperText.m | `void` | *(n/a)* | 1289 | *(n/a)* |

### ❓ `objective-c` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:43Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| worldwideweb/HyperText.m | `keyDown` | 1426 | *(n/a)* | *(n/a)* |

## perl

### ❓ `perl` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 122 occurrences as of 2026-08-18T21:01:47Z*

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

### ❓ `perl` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 64 occurrences as of 2026-08-18T21:01:47Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `perl` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-08-18T21:01:47Z*

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

*2-vs-1 -- 7 occurrences as of 2026-08-18T21:01:47Z*

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

### ❓ `perl` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:47Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| spamassassin/PerMsgStatus.pm | `Mail::SpamAssassin::PerMsgStatus` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `perl` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:47Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`perl/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mojo/Promise.pm | `get_p` | 277 | *(n/a)* | *(n/a)* |

## php

### ❓ `php` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 68 occurrences as of 2026-08-18T21:01:49Z*

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

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:49Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`php/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| laravel_core/BladeCompiler.php | `AnonymousClassfe62f8e60100` | *(n/a)* | *(n/a)* | 342 |

### ❓ `php` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:49Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`php/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wordpress/formatting.php | `remove_accents` | 1610 | *(n/a)* | 1611 |

## powershell

### ❓ `powershell` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 5 occurrences as of 2026-08-18T21:01:50Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/packaging.psm1 | `Start-PSPackage` | 0 | 12 | *(n/a)* |
| core/packaging.psm1 | `New-MSIPackage` | 11 | 10 | *(n/a)* |
| core/packaging.psm1 | `Invoke-AzDevOpsLinuxPackageBuild` | 0 | 2 | *(n/a)* |
| core/packaging.psm1 | `Invoke-AzDevOpsLinuxPackageCreation` | 0 | 3 | *(n/a)* |
| core/packaging.psm1 | `Get-LinuxPackageSemanticVersion` | 0 | 1 | *(n/a)* |

### ❓ `powershell` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-18T21:01:50Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/packaging.psm1 | `New-NativeDeb` | 1749 | 1749 | *(n/a)* |
| core/packaging.psm1 | `GetPattern` | 5619 | 5619 | *(n/a)* |
| core/packaging.psm1 | `EnsureArchitecture` | 5647 | 5647 | *(n/a)* |
| core/packaging.psm1 | `SetPattern` | 5633 | 5633 | *(n/a)* |

### ❓ `powershell` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:01:50Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/packaging.psm1 | `PackageManifestResultStatus` | *(n/a)* | 5359 | *(n/a)* |
| core/packaging.psm1 | `MachineOSOverride` | *(n/a)* | 5441 | *(n/a)* |

### ❓ `powershell` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:50Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`powershell/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/ci.psm1 | `Test-MergeConflictMarker` | 1020 | *(n/a)* | 1020 |

## python

### ❓ `python` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 68 occurrences as of 2026-08-18T21:38:25Z*

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

*2-vs-1 -- 32 occurrences as of 2026-08-18T21:38:25Z*

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

*2-vs-1 -- 4 occurrences as of 2026-08-18T21:38:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`python/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pyx | `array` | *(n/a)* | *(n/a)* | 130 |
| cython/MemoryView.pyx | `Enum` | *(n/a)* | *(n/a)* | 318 |
| cython/MemoryView.pyx | `memoryview` | *(n/a)* | *(n/a)* | 348 |
| cython/MemoryView.pyx | `_memoryviewslice` | *(n/a)* | *(n/a)* | 936 |

### ❓ `python` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:38:25Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`python/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| numpy/crackfortran.py | `markoutercomma` | 2 | 2 | 3 |

## ruby

### ❓ `ruby` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 6 occurrences as of 2026-08-18T21:01:54Z*

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

*2-vs-1 -- 6 occurrences as of 2026-08-18T21:01:54Z*

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

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:54Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/base.rb | `process` | 2 | 1 | 2 |
| rails/base.rb | `process_action` | 1 | 0 | 1 |
| rails/metal.rb | `use` | 1 | 0 | 1 |

### ❓ `ruby` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:01:54Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/blob.rb | `Blob` | *(n/a)* | *(n/a)* | 19 |
| rails/inbound_emails_controller.rb | `InboundEmailsController` | *(n/a)* | *(n/a)* | 45 |

## rust

### ❓ `rust` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 152 occurrences as of 2026-08-18T21:01:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`rust/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `rust` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 25 occurrences as of 2026-08-18T21:01:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`rust/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `rust` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 21 occurrences as of 2026-08-18T21:01:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`rust/function/args/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

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

### ❓ `rust` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 21 occurrences as of 2026-08-18T21:01:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`rust/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

### ❓ `rust` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-08-18T21:01:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`rust/class/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `XRegUnion` | *(n/a)* | 404 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `FRegUnion` | *(n/a)* | 529 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `VRegUnion` | *(n/a)* | 604 | *(n/a)* |

### ❓ `rust` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:55Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`rust/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `done_decode` | 964 | 964 | *(n/a)* |

## scala

### ❓ `scala` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 16 occurrences as of 2026-08-18T21:01:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`scala/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

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

*2-vs-1 -- 75 occurrences as of 2026-08-18T21:01:58Z*

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

## solidity

### ❓ `solidity` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-08-18T21:01:59Z*

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

### ❓ `swift` function args: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:59Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/args/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/Session.swift | `performSetupOperations` | 0 | 3 | *(n/a)* |

### ❓ `swift` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:59Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/ParameterEncoder.swift | `encode` | 159 | *(n/a)* | *(n/a)* |

### ❓ `swift` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:01:59Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`swift/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/Request.swift | `==` | *(n/a)* | 1119 | *(n/a)* |

## tcl

### ❓ `tcl` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-08-18T21:02:00Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/malloc_common.tcl | `faultsim_test_proc` | 347 | 347 | *(n/a)* |
| sqlite/tester.tcl | `set_test_counter` | 583 | 583 | *(n/a)* |
| sqlite/tester.tcl | `sqlite3` | 116 | 116 | *(n/a)* |
| sqlite/tester.tcl | `finish_test` | 1243 | 1243 | *(n/a)* |

### ❓ `tcl` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:02:00Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/tester.tcl | `drop_all_tables` | *(n/a)* | 2254 | 2254 |
| sqlite/tester.tcl | `drop_all_indexes` | *(n/a)* | 2279 | 2279 |

### ❓ `tcl` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:02:00Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/tester.tcl | `do_test` | 703 | *(n/a)* | 703 |

### ❓ `tcl` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:02:00Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`tcl/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite/malloc_common.tcl | `faultsim_test_result` | 348 | *(n/a)* | *(n/a)* |

## typescript

### ❓ `typescript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1961 occurrences as of 2026-08-18T21:02:16Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| assemblyscript/ast.ts | `columnAt` | 1715 | 1715 | *(n/a)* |
| assemblyscript/compiler.ts | `compileBinaryExpression` | 4046 | 4046 | *(n/a)* |
| assemblyscript/compiler.ts | `compileUnaryPrefixExpression` | 9522 | 9522 | *(n/a)* |
| assemblyscript/compiler.ts | `convertExpression` | 3546 | 3546 | *(n/a)* |
| assemblyscript/compiler.ts | `makePow` | 5088 | 5088 | *(n/a)* |
| assemblyscript/compiler.ts | `compileUnaryPostfixExpression` | 9278 | 9278 | *(n/a)* |
| assemblyscript/compiler.ts | `compileIdentifierExpression` | 7358 | 7358 | *(n/a)* |
| assemblyscript/compiler.ts | `compileExpression` | 3432 | 3432 | *(n/a)* |
| assemblyscript/compiler.ts | `makeAssignment` | 5793 | 5793 | *(n/a)* |
| assemblyscript/compiler.ts | `compileObjectLiteral` | 8577 | 8577 | *(n/a)* |

### ❓ `typescript` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 520 occurrences as of 2026-08-18T21:02:16Z*

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

*2-vs-1 -- 175 occurrences as of 2026-08-18T21:02:16Z*

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

*2-vs-1 -- 64 occurrences as of 2026-08-18T21:02:16Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| assemblyscript/ast.ts | `assert` | *(n/a)* | *(n/a)* | 1711 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2184 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2202 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2220 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2238 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2257 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2277 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2185 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2203 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2221 |

### ❓ `typescript` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 8 occurrences as of 2026-08-18T21:02:16Z*

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

*2-vs-1 -- 2 occurrences as of 2026-08-18T21:02:16Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`typescript/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| vscode/lifecycle.ts | `createReferencedObject` | 711 | *(n/a)* | *(n/a)* |
| vscode/lifecycle.ts | `destroyReferencedObject` | 712 | *(n/a)* | *(n/a)* |

## zig

### ❓ `zig` class existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 10 occurrences as of 2026-08-18T21:02:19Z*

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

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:02:19Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`zig/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bun/MimallocArena.zig | `Borrowed` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `zig` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-08-18T21:02:19Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`zig/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| zig/InternPool.zig | `dbHelper` | *(n/a)* | 4823 | *(n/a)* |
