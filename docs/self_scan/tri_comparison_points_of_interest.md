# Tri-Comparison Points of Interest

Generated from `tri_comparison_ledger.json` by `tests/tools/tri_comparison_report.py --write` -- do not hand-edit this file, edit the ledger and regenerate. See `docs/self_scan/how_to_investigate_a_discrepancy.md` for what ❓ entries are asking for.

Sorted 2-vs-1 splits before 3-way splits, unvalidated before validated, biggest occurrence count first within each tier -- see this script's own module docstring for why that order.

## ada

### ❓ `ada` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 217 occurrences as of 2026-11-26T05:32:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ada/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alire/alire-directories.adb | `Touch` | 1177 | 1177 | *(n/a)* |
| alire/alire-directories.adb | `New_Replacement` | 1132 | 1132 | *(n/a)* |
| alire/alire-directories.adb | `Tree_Size` | 1025 | 1025 | *(n/a)* |
| alire/alire-directories.adb | `Traverse_Tree` | 966 | 966 | *(n/a)* |
| alire/alire-directories.adb | `In_Dir` | 1108 | 1108 | *(n/a)* |
| alire/alire-directories.adb | `Accumulate` | 1033 | 1033 | *(n/a)* |
| alire/alire-directories.adb | `Replace` | 1161 | 1161 | *(n/a)* |
| alire/alire-directories.adb | `TTY_Image` | 1068 | 1068 | *(n/a)* |
| alire/alire-directories.adb | `With_Name` | 1092 | 1092 | *(n/a)* |
| alire/alire-directories.adb | `Editable_Name` | 1125 | 1125 | *(n/a)* |

### ❓ `ada` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 52 occurrences as of 2026-11-26T05:32:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ada/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alire/alire-conditional_trees.adb | `Forward_Iterator` | *(n/a)* | *(n/a)* | 577 |
| alire/alire-crate_configuration.adb | `Config_Settings_Array` | *(n/a)* | *(n/a)* | 59 |
| alire/alire-dependencies-states.ads | `Fulfillment_Data` | *(n/a)* | *(n/a)* | 232 |
| alire/alire-dependencies-states.ads | `Fulfillments` | *(n/a)* | *(n/a)* | 13 |
| alire/alire-dependencies-states.ads | `Link_Holder` | *(n/a)* | *(n/a)* | 228 |
| alire/alire-dependencies-states.ads | `Missed_Reasons` | *(n/a)* | *(n/a)* | 18 |
| alire/alire-dependencies-states.ads | `Pinning_Data` | *(n/a)* | *(n/a)* | 245 |
| alire/alire-dependencies-states.ads | `State` | *(n/a)* | *(n/a)* | 34 |
| alire/alire-dependencies-states.ads | `State` | *(n/a)* | *(n/a)* | 256 |
| alire/alire-dependencies-states.ads | `Stored_Release` | *(n/a)* | *(n/a)* | 175 |

### ❓ `ada` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 31 occurrences as of 2026-11-26T05:32:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ada/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alire/alire-conditional_trees.adb | `Enumerate` | *(n/a)* | *(n/a)* | 306 |
| alire/alire-crate_configuration.adb | `Is_Valid` | *(n/a)* | *(n/a)* | 981 |
| alire/alire-crate_configuration.adb | `Builtin_Build_Profile` | *(n/a)* | *(n/a)* | 34 |
| alire/alire-dependencies-states.ads | `Get` | *(n/a)* | *(n/a)* | 230 |
| alire/alire-dependencies-states.ads | `L` | *(n/a)* | *(n/a)* | 171 |
| alire/alire-directories.adb | `Free` | *(n/a)* | *(n/a)* | 496 |
| alire/alire-directories.adb | `Hash` | *(n/a)* | *(n/a)* | 624 |
| alire/alire-directories.adb | `To_Integer` | *(n/a)* | *(n/a)* | 629 |
| alire/alire-properties-configurations.adb | `Is_Valid` | *(n/a)* | *(n/a)* | 23 |
| alire/alire-properties-configurations.adb | `Valid_Keys_Suggestion` | *(n/a)* | *(n/a)* | 24 |

### ❓ `ada` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 31 occurrences as of 2026-11-26T05:32:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ada/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alire/alire-dependencies-states.ads | `Release` | 143 | *(n/a)* | *(n/a)* |
| alire/alire-dependencies-states.ads | `User_Pin` | 140 | *(n/a)* | *(n/a)* |
| alire/alire-dependencies-states.ads | `Milestone_Image` | 152 | *(n/a)* | *(n/a)* |
| alire/alire-dependencies-states.ads | `Link` | 134 | *(n/a)* | *(n/a)* |
| alire/alire-dependencies-states.ads | `Pin_Version` | 137 | *(n/a)* | *(n/a)* |
| alire/alire-dependencies-states.ads | `Reason` | 131 | *(n/a)* | *(n/a)* |
| alire/alire-releases.ads | `Install_System_Package` | 384 | *(n/a)* | *(n/a)* |
| alire/alire-roots.ads | `Sync_Manifest_And_Lockfile_Timestamps` | 220 | *(n/a)* | *(n/a)* |
| alire/alire-roots.ads | `Set_Build_Profile` | 336 | *(n/a)* | *(n/a)* |
| alire/alire-roots.ads | `Requires_Build_Sync` | 155 | *(n/a)* | *(n/a)* |

### ❓ `ada` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 20 occurrences as of 2026-11-26T05:32:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ada/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alire/alire-conditional_trees.adb | `Flatten` | *(n/a)* | 151 | 152 |
| alire/alire-conditional_trees.adb | `Evaluate` | *(n/a)* | 316 | 317 |
| alire/alire-conditional_trees.adb | `"and"` | *(n/a)* | 198 | 198 |
| alire/alire-conditional_trees.adb | `"or"` | *(n/a)* | 205 | 205 |
| alire/alire-conditional_trees.adb | `Iterate` | *(n/a)* | 616 | 616 |
| alire/alire-origins.adb | `As_Data` | *(n/a)* | 26 | 26 |
| alire/alire-releases.adb | `"<"` | *(n/a)* | 39 | 39 |
| alire/alire-roots.adb | `Configuration` | *(n/a)* | 572 | 572 |
| alire/alire-roots.adb | `Add_Pins` | *(n/a)* | 958 | 958 |
| alire/alire-roots.adb | `Temporary_Copy` | *(n/a)* | 2062 | 2062 |

### ❓ `ada` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:32:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ada/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alire/alire-solver.adb | `"<"` | *(n/a)* | 969 | *(n/a)* |

### ❓ `ada` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 11 occurrences as of 2026-11-26T05:32:05Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ada/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alire/alire-conditional_trees.adb | `Join` | 2 | 3 | *(n/a)* |
| alire/alire-directories.adb | `Copy` | 2 | 3 | *(n/a)* |
| alire/alire-directories.adb | `Merge_Contents` | 2 | 6 | *(n/a)* |
| alire/alire-releases.ads | `No_TOML_Value` | 5 | 0 | *(n/a)* |
| alire/alire-roots.adb | `Traverse` | 4 | 2 | *(n/a)* |
| alire/alire-solutions-diffs.adb | `Fulfil_Change` | 1 | 0 | *(n/a)* |
| alire/alire-solutions-diffs.adb | `Add_Change` | 2 | 3 | *(n/a)* |
| alire/alire-test-runner.adb | `Fail` | 2 | 4 | *(n/a)* |
| alire/alire-toml_index.adb | `Set_Error` | 2 | 4 | *(n/a)* |
| alire/alr-commands-self_update.adb | `Windows_Copy_And_Relaunch` | 2 | 3 | *(n/a)* |

## agc_assembly

### ✅ `agc_assembly` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 647 occurrences as of 2026-11-26T05:32:07Z*

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

*2-vs-1 -- 92 occurrences as of 2026-11-26T05:32:07Z*

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
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `TIG-30` | 292 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `TIG-0` | 390 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `CALLT-35` | 222 | *(n/a)* | *(n/a)* |
| apollo-11/BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc | `TIG-5` | 354 | *(n/a)* | *(n/a)* |

## apex

### ❓ `apex` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 18 occurrences as of 2026-11-26T05:32:09Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`apex/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IDomainConstructor.cls | `construct` | *(n/a)* | 28 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `contains` | *(n/a)* | 33 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `containsAll` | *(n/a)* | 40 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `containsAll` | *(n/a)* | 47 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `containsNot` | *(n/a)* | 54 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `containsNot` | *(n/a)* | 61 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `containsNot` | *(n/a)* | 68 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `isEmpty` | *(n/a)* | 73 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `isNotEmpty` | *(n/a)* | 78 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `size` | *(n/a)* | 83 | *(n/a)* |

### ❓ `apex` class existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-11-26T05:32:09Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`apex/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IDomainConstructor.cls | `fflib_IDomainConstructor` | *(n/a)* | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IObjects.cls | `fflib_IObjects` | *(n/a)* | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_ISObjectSelector.cls | `fflib_ISObjectSelector` | *(n/a)* | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_ISObjects.cls | `fflib_ISObjects` | *(n/a)* | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_IServiceFactory.cls | `fflib_IServiceFactory` | *(n/a)* | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_SObjectSelector.cls | `DataAccess` | *(n/a)* | *(n/a)* | *(n/a)* |

### ✅ `apex` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 43 occurrences as of 2026-11-26T05:32:09Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep (direct investigation, no Gemini dispatch needed -- root cause was immediately clear from source), 2026-08-20T22:17:39Z):
> Confirmed GitGalaxy engine defect, not a tree-sitter gap. Both sampled occurrences (apex-recipes/AuraEnabledRecipes_Tests.cls:25 and :43) are `new Account(name = ...)` object-instantiation expressions inside a multi-line SObject-builder call, not real method/constructor definitions -- confirmed by reading the source directly. Root cause: the func_start regex (language_standards.py, apex rules) treats any `[a-zA-Z_][\w.]*[ \t\n]+` token at start-of-line as an eligible optional return-type/modifier prefix before the captured function name, with no exclusion for the `new` keyword -- so `new Account(` parses as "returnType=new, name=Account", passing the #1221 gating fix (which only requires the line START with one of annotation/modifier/return-type-shaped token, not that the token be a real type). tree_sitter correctly does not report these as functions since its grammar distinguishes object_creation_expression from method_declaration structurally. Verified this generalizes beyond the 2-occurrence ledger sample: running the regex directly against the whole apex corpus found 6 total false-positive matches across 2 files (AuraEnabledRecipes_Tests.cls:6,25,43 and SOQLRecipes_Tests.cls:226,235,504), all the identical `new ClassName(` shape. Filed as GitHub issue #1963 (exclude `new` from the eligible return-type/modifier prefix token). No credit_tools/debit_tools adjustment needed: since only gitgalaxy is in agreeing_tools here (len(present)==1), the reconciler already excludes this from gitgalaxy matched_consensus by default while still counting it in total_slots -- the default precision score already reflects this correctly as an unconfirmed/wrong claim.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `return` | 385 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `DomainFactory` | 301 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `DomainFactory` | 312 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `DomainFactory` | 329 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `ServiceFactory` | 134 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `ServiceFactory` | 144 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `SelectorFactory` | 189 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `SelectorFactory` | 198 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `UnitOfWorkFactory` | 45 | *(n/a)* | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `UnitOfWorkFactory` | 52 | *(n/a)* | *(n/a)* |

### ❓ `apex` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 2 occurrences as of 2026-11-26T05:32:09Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`apex/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_Application.cls | `getConstructorTypeByObject` | 2 | 1 | *(n/a)* |
| fflib_apex_common/sfdx-source_apex-common_main_classes_fflib_SObjects.cls | `setFieldValueByMap` | 4 | 3 | *(n/a)* |

## assembly

### ✅ `assembly` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 1550 occurrences as of 2026-11-26T05:32:14Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-31):
> Re-validated 2026-08-31 after the corpus grew 3->16 folders (253 new files, PR #13). Same confirmed mechanism as the prior 2026-08-27 verdict (ctags' generic Asm parser tagging line-start tokens that are not subroutine entries; GitGalaxy correctly excludes every one), now confirmed at ~70x the sample size (1791 occurrences vs. 26) across every new folder, plus two NEW manifestations of the SAME underlying weakness the smaller corpus never exercised: (1) MACRO-INVOCATION-KEYWORD mistagging -- ctags tags the LITERAL macro name as if it were a label, not the real subroutine name inside it. Confirmed directly: NASM's own instruction-set self-test suite (nasm_testsuite/avx005.asm and siblings) uses a `%macro x 1+.nolist` wrapper invoked as bare `x OPCODE ...` on hundreds of lines with no colon anywhere -- `ctags -x --language-force=Asm` tags the word `x` as a 'label' up to 192 times in one file (confirmed via raw ctags run); cpm65_6502's `zproc NAME`/`zendproc` procedure- definition macro convention gets the identical treatment (`zproc`/`zendproc` themselves tagged as literal 'label' names, cpm65_6502/apps_devices.asm, 5 occurrences each) as does the `.label NAME` forward-declaration pseudo-op (tags the NAME as if `.label` itself were the definition, duplicating the real `zproc`-declared one). (2) BARE INSTRUCTION MNEMONIC mistagging on FASM-dialect files -- raspberrypi_baremetal's `format`/`include`/`code64` FASM-assembler directives desync ctags' line-start heuristic entirely, tagging ordinary indented instruction lines (`mov`, `add`, `ldr`, `ands`, `mrc`, ...) as repeated 'labels' (confirmed: x86_bare_metal/apm_shutdown.S tags `mov`x6/`int`x3/`xor`x2 with zero real labels present). GitGalaxy correctly excludes all of these -- its func_start regex requires an actual `name:` colon-terminated declaration head, which none of these forms have. No credit/debit: ctags already pays for these in its own precision denominator (it alone claims them); there is no shared-consensus mistake to debit and nothing of GitGalaxy's to credit.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| blst_generated_asm/add_mod_256-x86_64.s | `Loaded_a_add_mod_256` | *(n/a)* | *(n/a)* | 30 |
| blst_generated_asm/add_mod_256-x86_64.s | `Loop_lshift_mod_256` | *(n/a)* | *(n/a)* | 198 |
| blst_generated_asm/add_mod_256-x86_64.s | `Loop_rshift_mod_256` | *(n/a)* | *(n/a)* | 257 |
| blst_generated_asm/add_mod_384-x86_64.s | `Loop_is_equal` | *(n/a)* | *(n/a)* | 2176 |
| blst_generated_asm/add_mod_384-x86_64.s | `Loop_is_equal_done` | *(n/a)* | *(n/a)* | 2186 |
| blst_generated_asm/add_mod_384-x86_64.s | `Loop_is_zero` | *(n/a)* | *(n/a)* | 2131 |
| blst_generated_asm/add_mod_384-x86_64.s | `Loop_is_zero_done` | *(n/a)* | *(n/a)* | 2139 |
| blst_generated_asm/add_mod_384-x86_64.s | `Loop_lshift_mod_384` | *(n/a)* | *(n/a)* | 463 |
| blst_generated_asm/add_mod_384-x86_64.s | `Loop_rshift_mod_384` | *(n/a)* | *(n/a)* | 239 |
| blst_generated_asm/ct_inverse_mod_256-x86_64.s | `Loop_31_256` | *(n/a)* | *(n/a)* | 1139 |

### ✅ `assembly` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 83 occurrences as of 2026-11-26T05:32:14Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-31):
> Re-validated 2026-08-31 after the corpus grew 3->16 folders; down from 26 to 21 occurrences -- 5 were a real, confirmed GitGalaxy engine defect, now FIXED (not just credited): assembly's own lexical_family ('line_exclusive') only ever recognized `;`/`#` line comments, but `.S` files are routed through the C preprocessor and routinely carry genuine `/* ... */` block comments (BSD/FreeBSD license headers, Emacs modelines, register-usage doc comments) that were never stripped at all -- func_start matched label-shaped text INSIDE the unstripped comment: `Result:` (linux_1_0_kernel/drivers_FPU-emu_reg_u_div.S, a stack-layout doc comment) and `r9:`/`r10:`/`r11:` (freebsd_kernel_arch/amd64_amd64_kexec_tramp.S, a register-usage doc comment). Fixed by adding a new `_strip_asm_block_comments` pre-processing pass in prism.py, run BEFORE `;`/`#` line-stripping (confirmed via direct corpus measurement, not assumed: 121 real `/* ... */` blocks in this corpus contain a bare `;`/`#` internally -- copyright prose, URLs, Emacs modelines -- so line-stripping first would truncate every one of those blocks at its first internal `;`/`#`, corrupting the search for the block's real closing `*/`; the reverse risk, a `;`/`#` comment containing an unclosed `/*`, was checked and found to occur zero times in this corpus). Verified: exactly 5 fewer func_start matches corpus-wide post-fix (1144 -> 1139), matching the confirmed count precisely; both golden masters re-blessed. The remaining 21 are all confirmed GitGalaxy-correct, ctags-structurally-can't, via two established mechanisms plus one newly-confirmed variant of the first: (1) NASM leading-dot local labels (`.loop`/`.find`/`.empty`/`.load_vec`/`.getgot`/`.setcs`/`.no_error`/`.disconnect_error`, bootos/os.asm + nasm_testsuite/aoutso.asm + x86_bare_metal/*, 8 occ) and numeric local labels (`.1`/`.2`, bootos/counter.asm, 2 occ) -- ctags strips the leading dot (normalized by the reconciler) or can't tag a name starting with a digit at all, same precedent as the prior verdict. (2) NEW: GAS's `funcname.localname:` dot-SCOPED local-label convention (NOT leading-dot -- the dot sits in the middle, scoping a jump target to its enclosing routine) -- `do_e820.jmpin`/`do_e820.e820lp`/`do_e820.e820f`/`do_e820.skipent`/`do_e820.notext`/`do_e820.failed` (x86_bare_metal/bios_detect_memory.S, 6 occ) and `seta20.1`/`seta20.2` (xv6_x86_kernel/bootasm.S, 2 occ) -- confirmed via raw ctags run: it tags the real top-level `do_e820` fine but zero of its six dotted sub-labels, a structural inability to parse a `.` inside a label name in this position, not a GitGalaxy over-match (GitGalaxy's own inclusion of these as separate satellites, rather than folding them into the enclosing routine, matches its existing, established policy for NASM leading-dot locals in bucket 1 -- consistent, not a new design question). (3) Real subroutines a `zproc`/custom-macro-heavy file declares via a genuine `name:` label that ctags' 'zproc'/'.label'-mistagging (see the sibling shape's verdict) causes it to miss entirely -- `skip`/`syntax_error`/`write_char`/`io_error`/`justprint` (cpm65_6502/apps_bedit.asm, 6 occ), `longjmp` (cosmopolitan_runtime/longjmp.S -- confirmed real via its `_longjmp:` sibling and `#ifdef __x86_64__` body), `end` (os_tutorial_x86 + x86_bare_metal/bios_pixel*.S, 3 occ). One residual, ACKNOWLEDGED false positive, not chased (single occurrence, narrow root cause): xv6_x86_kernel/usys.S's `name` -- `#define SYSCALL(name) \\n .globl name; \\n name: \\n ...`, a C-preprocessor macro TEMPLATE where `name` is a parameter, not a real label; func_start matches the literal `name:` inside the macro's own body text (a textual regex has no concept of preprocessor parameter substitution). Left in the credited shape's count since it's a single, narrow, low-value edge case (one occurrence in the whole corpus) against 20 confirmed-correct siblings -- documented here rather than silently absorbed into the credit, or chased for a fix disproportionate to its impact.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bootos/counter.asm | `1` | 52 | *(n/a)* | *(n/a)* |
| bootos/counter.asm | `2` | 67 | *(n/a)* | *(n/a)* |
| cosmopolitan_runtime/longjmp.S | `longjmp` | 28 | *(n/a)* | *(n/a)* |
| cpm65_6502/apps_bedit.asm | `skip` | 682 | *(n/a)* | *(n/a)* |
| cpm65_6502/apps_bedit.asm | `skip` | 1361 | *(n/a)* | *(n/a)* |
| cpm65_6502/apps_bedit.asm | `syntax_error` | 335 | *(n/a)* | *(n/a)* |
| cpm65_6502/apps_bedit.asm | `write_char` | 1472 | *(n/a)* | *(n/a)* |
| cpm65_6502/apps_bedit.asm | `io_error` | 1494 | *(n/a)* | *(n/a)* |
| cpm65_6502/apps_bedit.asm | `justprint` | 680 | *(n/a)* | *(n/a)* |
| os_tutorial_x86/05-bootsector-functions-strings_boot_sect_print_hex.asm | `end` | 36 | *(n/a)* | *(n/a)* |

## c

### ✅ `c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 74 occurrences as of 2026-11-26T05:32:20Z*

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

*2-vs-1 -- 13 occurrences as of 2026-11-26T05:32:20Z*

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

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:32:20Z*

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

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:32:20Z*

**Verdict** (by Claude Sonnet 5 (resolved directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Confirmed GitGalaxy correct, real finding -- a new, narrower instance of Claim 3 (parse-error cascade), added to docs/why_gitgalaxy_beats_ast_here.md. All 4 sampled names (slot_mp_ass_subscript:10544, slot_nb_inplace_power:10697, slot_tp_repr:10714, slot_tp_hash:10730, all cpython/typeobject.c) are ordinary, unremarkable function definitions -- nothing unusual individually -- but each sits directly after a bare SLOT0/SLOT1 macro-invocation LINE (`SLOT1(slot_mp_subscript, __getitem__, PyObject *)`, `SLOT0(slot_tp_str, __str__)`, etc.) that isn't valid freestanding C without macro expansion. GitGalaxy's regex has no adjacency sensitivity and finds all 4 correctly; both ctags and tree-sitter locally lose the SINGLE function immediately following each such line (recovers after just one function, not a full cascade to EOF -- confirmed by resolving all 4 as isolated single-function misses, not a growing region). Resolved directly, no dispatch needed -- same pattern verified at all 4 sample points before writing up.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `slot_tp_hash` | 10730 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_mp_ass_subscript` | 10544 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_tp_repr` | 10714 | *(n/a)* | *(n/a)* |
| cpython/typeobject.c | `slot_nb_inplace_power` | 10697 | *(n/a)* | *(n/a)* |

### ✅ `c` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 3 occurrences as of 2026-11-26T05:32:20Z*

**Verdict** (by Claude Sonnet 5 (resolved directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Not a new finding -- both sampled names are ALREADY in tree_sitter_accuracy_audit.py's _C_KNOWN_MACRO_HALLUCINATIONS exclusion set (confirmed by grep: 'EXPORT_FUN' and 'MICROPY_WRAP_MP_EXECUTE_BYTECODE' both present). This shape is the same already-documented macro-hallucination mechanism (Claim 8) as the earlier tree-sitter-alone shape, just with ctags ALSO independently hallucinating the same 2 names the same way (both tools' regex/grammar parsers get fooled by the same macro-definition text). GitGalaxy correctly excludes both. Resolved directly, no dispatch needed.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython/emitnative.c | `EXPORT_FUN` | *(n/a)* | 300 | 300 |
| micropython/emitnative.c | `EXPORT_FUN` | *(n/a)* | 320 | 320 |
| micropython/vm.c | `MICROPY_WRAP_MP_EXECUTE_BYTECODE` | *(n/a)* | 220 | 220 |

### ✅ `c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-11-26T05:32:20Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> UPDATED after a real production fix (the same fix documented in cpp's agree[gitgalaxy,tree_sitter]_vs[ctags] entry -- c and cpp share the mechanism, `lang_id in ("c", "cpp")` in detector.py's `_slice_by_braces`). GitGalaxy now scans each file for `#define NAME(...)` function-like macro definitions and excludes any func_start match whose captured name is a known macro -- confirmed to eliminate the already-documented `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/`SLOT1BINFULL`/`DICT___REVERSED___METHODDEF` cpython/typeobject.c false positives entirely (a direct `SELECT func_name ... WHERE func_name IN (...)` query against a fresh scan returned zero rows). The small residual (3 occurrences: `slot_nb_power`, `slot_nb_bool`, `wrap_next`, all cpython/typeobject.c) is a DIFFERENT, unrelated finding, not yet individually root-caused -- GitGalaxy and tree-sitter both correctly find these real functions and ctags doesn't; plausibly the same category of ctags miss documented in cpp's sibling entry (an ordinary function ctags' C++ parser fails to tag for reasons unrelated to macros) but not directly confirmed for these three specific names. No credit_tools adjustment applies -- already a naturally-corroborated 2-of-3 agreeing pair.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cpython/typeobject.c | `slot_nb_power` | 10577 | 10577 | *(n/a)* |
| cpython/typeobject.c | `slot_nb_bool` | 10630 | 10630 | *(n/a)* |
| cpython/typeobject.c | `wrap_next` | 10106 | 10106 | *(n/a)* |

### ✅ `c` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:32:20Z*

**Verdict** (by Claude Sonnet 5 (resolved + fixed directly, no dispatch needed), 2026-08-19T00:00:00Z):
> Not a GitGalaxy or ctags defect -- a bug in this tool's OWN _count_ctags_signature_params (tri_comparison_gatherer.py), now fixed. Confirmed directly: ran ctags against cpython/ceval.c, PyEval_GetLocals(void)'s raw signature field is literally the text '(void)'. GitGalaxy and tree-sitter both already special-case C's explicit empty-parameter-list idiom (0 real args, matching detector.py's own _count_top_level_args docstring) -- _count_ctags_signature_params did not, splitting '(void)' into one non-empty segment and counting it as 1 real parameter (the same class of bug its own docstring already describes fixing twice for Python's trailing-comma and bare * / marker cases). Added 'void' to the segment-exclusion set alongside the existing '*'/'/'/'**' -- verified fix: _count_ctags_signature_params('(void)') now returns 0. This corpus (cpython) uses the (void) idiom extremely heavily, plausibly explaining most/all of the 104 occurrences; not independently re-verified beyond the sample, but the mechanism is unconditional (any '(void)' signature was miscounted the same way, corpus-wide) so high confidence it generalizes. No GitHub issue needed -- fixed directly in this same commit, not a repo-code defect.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython/gc.c | `gc_mark_subtree` | 1 | 1 | 2 |

## cobol

### ✅ `cobol` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 3534 occurrences as of 2026-11-26T05:32:46Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-28):
> Re-verified 2026-08-28 after the corpus grew ~6x for this language (53 -> 308 files, issue-#4 provenance audit / language-crucible v1.1.0): the count grew from 133 to 773 (gather_language name-diff; ledger's own capped-sample count differs slightly, same shape) without a status change, per merge_and_save()'s normal behavior -- re-checked rather than assumed, per how_to_investigate_a_discrepancy.md's 'When a validated shape's count changes a lot'. Confirmed: still the single already-documented mechanism (ctags' Cobol parser tags ANY period-terminated word as a paragraph, kind 'p', regardless of COBOL division or what role the period plays), now generalizing to syntax shapes the smaller corpus never exercised. Full accounting, zero unexplained residual: scope terminators like END-IF./END-PERFORM. (original 2026-08-19 finding); IDENTIFICATION/ENVIRONMENT/DATA DIVISION section/paragraph headers like WORKING-STORAGE SECTION./CONFIGURATION SECTION./LINKAGE SECTION./AUTHOR. (confirmed 2026-08-28, now the single largest contributor -- 564/773 in a corpus-wide name-tally); embedded-SQL qualified-column periods like COMMERCIAL.POLICYNUMBER inside an EXEC SQL...END-EXEC block, where the period is a table/column separator, not a COBOL statement terminator (confirmed 2026-08-28 via direct ctags run on cics-genapp/lgipdb01.cbl -- POLICY/COMMERCIAL/MOTOR tagged as paragraphs from FROM POLICY,COMMERCIAL and MOTOR.POLICYNUMBER clauses). GitGalaxy correctly excludes all three via its reserved-word shield and division/section awareness. Issue #1892's hyphenated-verb fix remains fully effective -- a corpus-wide name tally of every 'missing from GitGalaxy' occurrence found zero real paragraph names, only the three ctags-side false-positive shapes above. Full cross-reference: tests/tools/ctags_reader.py's cobol notes.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| CICS-Cobol/CBL0102v01DivisionAmbiente.cbl | `CONFIGURATION` | *(n/a)* | *(n/a)* | 11 |
| CICS-Cobol/CBL0102v01DivisionAmbiente.cbl | `FILE-CONTROL` | *(n/a)* | *(n/a)* | 18 |
| CICS-Cobol/CBL0102v01DivisionAmbiente.cbl | `INPUT-OUTPUT` | *(n/a)* | *(n/a)* | 17 |
| CICS-Cobol/CBL0102v01DivisionAmbiente.cbl | `OBJECT-COMPUTER` | *(n/a)* | *(n/a)* | 15 |
| CICS-Cobol/CBL0102v01DivisionAmbiente.cbl | `SOURCE-COMPUTER` | *(n/a)* | *(n/a)* | 13 |
| CICS-Cobol/CBL0103v01DivisionData.cbl | `FILE` | *(n/a)* | *(n/a)* | 17 |
| CICS-Cobol/CBL0103v01DivisionData.cbl | `INPUT-OUTPUT` | *(n/a)* | *(n/a)* | 11 |
| CICS-Cobol/CBL0104v01ProcedureDivision.cbl | `WORKING-STORAGE` | *(n/a)* | *(n/a)* | 11 |
| CICS-Cobol/CBL0105v01DeclararElementoGrupo.cbl | `WORKING-STORAGE` | *(n/a)* | *(n/a)* | 11 |
| CICS-Cobol/CBL0106v01ClausulaImagen.cbl | `MOVE` | *(n/a)* | *(n/a)* | 20 |

### ✅ `cobol` class existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 164 occurrences as of 2026-11-26T05:32:46Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-28):
> Confirmed: GitGalaxy correct on all 6, two independent confirmed ctags 'program' (P) kind limitations, zero unexplained residual. (1) 5/6 (aws-mainframe-modernization-carddemo's COACTUPC/COACTVWC/COCRDLIC/COCRDSLC/COCRDUPC): PROGRAM-ID. and the program name are written on two separate lines (a legitimate, common COBOL style) -- `ctags -x --language-force=Cobol --kinds-Cobol=P` emits zero tags at all for this shape, confirmed directly on all 5 real occurrences in the corpus, not a sample. GitGalaxy's class_start matches the name regardless of which line it's on. (2) 1/6 (gnucobol/CBL_OC_DUMP.cob): ctags truncates the program name at its first underscore, tagging bare 'CBL' instead of 'CBL_OC_DUMP' -- confirmed via direct ctags run, compared against a hyphen-named sibling (cics-genapp's LGACDB01) tagged correctly in full in the same run. Same underscore-intolerant identifier convention as Claim 12's second instance (GnuCOBOL's own YACC grammar), manifesting as truncation instead of total rejection here. GitGalaxy's class_start correctly captures underscores as valid identifier characters. Full writeup: docs/why_gitgalaxy_beats_ast_here.md Claim 12's third instance; cross-referenced in tests/tools/ctags_reader.py's cobol notes.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aws-mainframe-modernization-carddemo/COACTUPC.cbl | `COACTUPC` | *(n/a)* | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/COACTVWC.cbl | `COACTVWC` | *(n/a)* | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/COCRDLIC.cbl | `COCRDLIC` | *(n/a)* | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/COCRDSLC.cbl | `COCRDSLC` | *(n/a)* | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/COCRDUPC.cbl | `COCRDUPC` | *(n/a)* | *(n/a)* | *(n/a)* |
| che-che4z_nist_ccvs85/DB1024.2.cbl | `DB102A` | *(n/a)* | *(n/a)* | *(n/a)* |
| che-che4z_nist_ccvs85/DB1034.2.cbl | `DB103M` | *(n/a)* | *(n/a)* | *(n/a)* |
| che-che4z_nist_ccvs85/DB1044.2.cbl | `DB104A` | *(n/a)* | *(n/a)* | *(n/a)* |
| che-che4z_nist_ccvs85/DB3014.2.cbl | `DB301M` | *(n/a)* | *(n/a)* | *(n/a)* |
| che-che4z_nist_ccvs85/DB3024.2.cbl | `DB302M` | *(n/a)* | *(n/a)* | *(n/a)* |

### ✅ `cobol` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 63 occurrences as of 2026-11-26T05:32:46Z*

**Verdict** (by Claude (Sonnet 5), direct investigation + fix (gitgalaxy#2480 follow-up), 2026-08-30):
> Mixed-cause shape, two independent confirmed defects, neither in GitGalaxy's core function detection being right or wrong as a whole. (1) MAINLINE/TIMESTAMP and most of the 18 cases: these are real COBOL SECTION headers in the PROCEDURE DIVISION (e.g. cics-genapp/lgacdb01.cbl:128 "MAINLINE SECTION.", cics-banking-sample-application-cbsa/BANKDATA.cbl:1441 "TIMESTAMP SECTION." followed by executable CALL statements) that GitGalaxy correctly captures per its own documented func_start scope ("Paragraphs and Sections") -- and ctags ALSO correctly tags them, as kind 'section' (verified via live ), not as the 'paragraph' kind. The disagreement is manufactured by tests/tools/ctags_reader.py's CTAGS_FUNC_KINDS["cobol"] = {"p"}, which drops section-kind tags before comparison -- a test-harness bug, not a real ctags-vs-GitGalaxy disagreement. Filed as GitHub issue #1891. (2) LOCAL-STORAGE (cics-banking-sample-application-cbsa/XFRFUN.cbl:107 "LOCAL-STORAGE SECTION." immediately followed by 01-level data item declarations, no executable logic): this is a genuine GitGalaxy false positive -- the func_start regex's reserved-word negative lookahead bans WORKING-STORAGE and LINKAGE as Data Division section names but omits LOCAL-STORAGE, so it slips through and gets miscounted as a paragraph. ctags correctly reports nothing here. Filed as GitHub issue #1890. Investigated via gemini-3.1-pro-high (agy), file:line citations independently re-verified by Claude against language_standards.py and a live ctags run before applying.

2026-08-30 (v1.2.0 corpus expansion, post-pin-bump #2478): count 55 -> 10. The v1.2.0 cobol content (che-che4z NIST COBOL-85 CCVS suite + cobol-check, ~600 files) newly surfaced three func_start false-positive shapes unique to strict fixed-format punched-card COBOL, all fixed in gitgalaxy#2481: (a) the CONTINUE no-op statement on its own line (`003200  CONTINUE.`) matched as a paragraph -- 36 occurrences across IF4014/IF4024/IF4034/SAMPLE1; fixed by adding CONTINUE to the reserved-verb shield (same class as LOCAL-STORAGE/#1890). (b) a bare 6-digit sequence number on a lone-period statement line (`012100      .`) captured as a paragraph name -- 6 occurrences; fixed by requiring the captured identifier to contain at least one letter (digit-led real names like `0000-MAIN` still match). (c) a column-7 `D` debug-line indicator glued onto the real paragraph name (`064100D` + `DEBUG-LINE-TEST-03-A` -> `DDEBUG-LINE-TEST-03-A`) -- fixed in the anchor (consume col-7 `D` only when a name-char follows) plus removing detector.py _slice_by_labels' C++-only BOOST_/TEST match.group(0) fallback, which was re-mangling any Mode-A name containing the substring TEST (also corrected 5 JCL step names: LGTESTC1/LGTESTP1-4 had been collapsing to `EXEC`). One residual: `066600DDEBUG-LINE-TEST-05-A` in DB1034.2.cbl still mangles via a not-yet-identified fourth extraction path (debug-line paragraph bracketed by `*` comment lines) -- filed as gitgalaxy#2480. The 9 remaining non-residual occurrences are SECT-IC219-000N / NUMBERN, real COBOL SECTION headers GitGalaxy correctly captures -- still the #1891 harness `{"p"}`-kind filter, unchanged.

2026-08-30 (gitgalaxy#2480 follow-up, cobol function precision -> 100%): the one residual (`066600DDEBUG-LINE-TEST-05-A`, DB1034.2.cbl) is FIXED. Root cause: prism.py blanks the `*` comment lines bracketing that debug paragraph to empty lines, and the func_start anchor's post-sequence-area `[ \t\n]*` let `^` (re.M) match on one of those blank lines and skip forward across the newline onto the real content line -- past the col-1-6 sequence-area shield -- so `066600` + col-7 `D` were swept into the captured name. Fixed by narrowing that slot to `[ \t]*` (horizontal only); `^` already re-anchors on the real line under re.M, and the sole genuine vertical gap (name / SECTION on separate lines) is handled by the section-6 lookahead. Verified corpus-wide: exactly one captured name changes (`066600DDEBUG-LINE-TEST-05-A` -> `DEBUG-LINE-TEST-05-A`), total func-name count unchanged, no ReDoS. ctags tags `DEBUG-LINE-TEST-05-A` correctly, so GitGalaxy now agrees on that slot.

The 9 remaining occurrences (`NUMBER1/2/3` in SG3034.2.cbl and SG4014.2.cbl; `SECT-IC219-0001/0002/0003` in OBIC24.2.cbl) are ALL segment-numbered SECTION headers (`NUMBER1 SECTION 18.`, `SECT-IC219-0001 SECTION 30.`) -- COBOL-68/74 program segmentation (segment-priority number after SECTION), still accepted by modern compilers. GitGalaxy's func_start handles them via its `SECTION(?:[ \t\n]+[0-9]{1,2})?` allowance. Universal Ctags 5.9.0's Cobol parser CANNOT parse a segment-numbered section header: `ctags -x --language-force=Cobol --kinds-Cobol='*'` emits ZERO tags (neither 's' nor 'p') for all 9 lines -- verified directly on all three files, not a sample. This is a structural ctags parser limitation, NOT a kind-filter issue: the earlier framing ("still the #1891 harness `{p}` filter") was STALE -- #1891 was fixed 2026-08-22 in gitgalaxy#2121, and CTAGS_FUNC_KINDS["cobol"] has been {"p", "s"} since. credit_tools=[gitgalaxy] applied: GitGalaxy's 9 extra claims are confirmed real, ctags' non-corroboration is a confirmed structural ctags limitation, not an open question -- textbook credit_tools case, identical pattern to the sibling `cobol/class/existence/agree[gitgalaxy]_vs[ctags]` (split-line PROGRAM-ID). Cross-referenced in tests/tools/ctags_reader.py's cobol notes and docs/why_gitgalaxy_beats_ast_here.md.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| Z-SMS-Gateway/BALANCE.cbl | `BALANCE` | 94 | *(n/a)* | *(n/a)* |
| Z-SMS-Gateway/HISTORY.cbl | `HISTORY` | 117 | *(n/a)* | *(n/a)* |
| Z-SMS-Gateway/MESSAGES.cbl | `MESSAGES` | 129 | *(n/a)* | *(n/a)* |
| Z-SMS-Gateway/SENDSMS.cbl | `SENDSMS` | 47 | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/CBACT01C.cbl | `CBACT01C` | 70 | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/CBACT02C.cbl | `CBACT02C` | 70 | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/CBACT03C.cbl | `CBACT03C` | 70 | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/CBACT04C.cbl | `CBACT04C` | 180 | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/CBCUS01C.cbl | `CBCUS01C` | 70 | *(n/a)* | *(n/a)* |
| aws-mainframe-modernization-carddemo/CBTRN02C.cbl | `CBTRN02C` | 193 | *(n/a)* | *(n/a)* |

### ✅ `cobol` class existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:32:46Z*

**Verdict** (by gemini-3.1-pro-high (agy), dispatched via tri-comparison-ledger-sweep, self-corrected and reviewed by claude-sonnet-5, 2026-08-19):
> Confirmed real GitGalaxy pipeline defect, generalizes to all 19 occurrences. ctags correctly tags PROGRAM-ID as a program (kind P). Initial framing (that ctags is over-matching/GitGalaxy is semantically correct to return null, since PROGRAM-ID is not an OOP class) turned out to be wrong once the actual pipeline was traced -- GitGalaxy's own cobol class_start regex ALREADY matches PROGRAM-ID correctly and identically to ctags (verified directly: LANGUAGE_DEFINITIONS["cobol"]["rules"]["class_start"] matches "PROGRAM-ID. BANKDATA." at cics-banking-sample-application-cbsa/BANKDATA.cbl:35, capturing "BANKDATA", exactly matching ctags' own reading). The null is produced further downstream: gitgalaxy/core/detector.py's _CLASS_START_NAMED_EXTRACTION_LANGS allowlist (added by epic #1295, closed 2026-08-12, 11/13 languages) gates which languages' own class_start regex is used for named-entity extraction; cobol was never added (not decided out like css/html, simply never in scope since #1295's verification method requires a tree-sitter grammar cobol lacks). Every language missing from that allowlist falls through to a hardcoded generic fallback regex (class|struct|interface|trait|enum) that cannot structurally match COBOL syntax at all -- so the correct class_start match is computed internally (feeding the numeric risk-signal count) but discarded before named-entity output. Same bug class #1295 already fixed for 11 other languages. This corrects and supersedes issue #1858's original diagnosis (which claimed the regex itself never matches -- it does); posted a correcting comment on #1858 rather than filing a duplicate. Investigated via gemini-3.1-pro-high (agy); the dispatched agent itself caught and corrected Gemini's initial (semantically-plausible but pipeline-unverified) verdict by tracing the real extraction code, then Claude independently re-verified both the regex match and the allowlist gap directly against source before applying. credit_tools=[ctags] applied: ctags' claim (19 real PROGRAM-ID classes) is fully confirmed real, and GitGalaxy's non-corroboration is a confirmed pipeline bug in GitGalaxy, not an open question about ctags -- this is the textbook credit_tools case per tri_comparison_ledger.py's own VERIFIED ADJUSTMENTS docstring.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| gnucobol/CBL_OC_DUMP.cob | `CBL` | *(n/a)* | *(n/a)* | 30 |

## cpp

### ✅ `cpp` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 135 occurrences as of 2026-11-26T05:32:54Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> UPDATED: count grew (98 -> 194) as a direct, correct consequence of the OPCODE-macro fix documented in the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] entry -- tree-sitter's OWN OPCODE-family misparse (godot/gdscript_vm.cpp's bytecode-dispatch macro) was previously MASKED by GitGalaxy sharing the identical mistake (both wrong == they 'agreed', landing in the other shape instead of this one). Now that GitGalaxy correctly excludes known macro invocations, tree-sitter's own grammar limitation on this exact pattern is cleanly isolated here instead, confirmed via the shape's own examples (repeated `OPCODE` entries at godot/gdscript_vm.cpp, tree_sitter line set, ctags/gitgalaxy both None). The remaining, previously-documented causes (bare control-flow-keyword/`void` hallucination, conversion-operator naming-suffix convention) are unchanged and still contribute the bulk of the original 98. No credit/debit applies -- tree-sitter is the one that's wrong here, alone. 2026-08-29 follow-up (#2455): the tree_sitter_accuracy_audit / tri_comparison_gatherer shared tree-sitter reader now canonicalizes C++ conversion-operator and destructor names to GitGalaxy's own convention -- `Variant::operator String() const` -> `Variant::operator String`, `operator BitField<T>() const` -> `operator BitField`, and the `_FORCE_INLINE_`-macro-mangled `~Variant` / `operator T` forms recovered from the sibling ERROR node -- and treats a small tree-sitter-cpp ERROR node (a function-like macro with no visible definition immediately before a special member) as a blind-spot region, promoting GitGalaxy's correct extraction there to ground truth. cpp function precision 95.0% -> 100.0%, extra_functions 68 -> 0. That resolved the 'conversion-operator naming-suffix convention' cause named above (~55 occurrences moved into GitGalaxy+tree-sitter consensus, count ~194 -> ~136). The residual is the genuine OPCODE-macro and bare-control-flow-keyword / bare-`void` hallucinations, still tree-sitter's alone.

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

### ✅ `cpp` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 30 occurrences as of 2026-11-26T05:32:54Z*

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

*2-vs-1 -- 22 occurrences as of 2026-11-26T05:32:54Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> UPDATED after a real production fix. The OPCODE-family shared mistake documented in this shape's prior verdict (~96 of the original 105 occurrences) is now FIXED: GitGalaxy's func_start (and by the same mechanism, C's) now scans each file for `#define NAME(...)` function-like macro definitions and excludes any match whose captured name is a known macro -- the exact same fact universal-ctags itself already used (confirmed via a direct `ctags -f -` run: ctags tags `OPCODE` only once, at its own #define line, kind `d`, and produces zero tags at any invocation site -- it isn't smarter about the invocation's shape, it just already knows the name is a macro and never re-tags it). This also fixed the already-documented C `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/`SLOT1BINFULL`/`DICT___REVERSED___METHODDEF` false positives as a bonus (same mechanism, `lang_id in ("c", "cpp")`). Verified via 3 repeated full-corpus scans producing byte-identical function lists, the full extraction gauntlet, and both golden masters re-blessed. The remaining residual (9 occurrences, previously miscounted as more of the same shared mistake in the earlier verdict's blanket debit -- corrected here) is a DIFFERENT, unrelated finding: GitGalaxy and tree-sitter are CORRECT here, ctags is wrong. Two sub-patterns confirmed: (1) the already-documented macro-as-return-type-prefix pattern (`IFACEMETHODIMP_(void)` immediately before the real `FancyZones::Run() noexcept` -- ctags tags the macro invocation itself and loses the real name, powertoys/FancyZones.cpp, 4 occurrences); (2) a newly-confirmed, NOT yet root-caused ctags miss on an ordinary virtual method with no macro involvement at all (`virtual RID mesh_create_from_surfaces(const Vector<RenderingServerTypes::SurfaceData> &p_surfaces, int p_blend_shape_count = 0) override { ... }`, godot/rendering_server_default.h -- ctags produces zero tags anywhere near this real method, 5 occurrences). No credit_tools adjustment applies: GitGalaxy and tree-sitter are already a 2-of-3 agreeing pair here, which already satisfies reconcile_symbols' own natural precision-credit condition. 2026-08-29 follow-up (#2455): the tree_sitter_accuracy_audit / tri_comparison_gatherer shared tree-sitter reader now canonicalizes C++ conversion-operator and destructor names to GitGalaxy's own convention -- `Variant::operator String() const` -> `Variant::operator String`, `operator BitField<T>() const` -> `operator BitField`, and the `_FORCE_INLINE_`-macro-mangled `~Variant` / `operator T` forms recovered from the sibling ERROR node -- and treats a small tree-sitter-cpp ERROR node (a function-like macro with no visible definition immediately before a special member) as a blind-spot region, promoting GitGalaxy's correct extraction there to ground truth. cpp function precision 95.0% -> 100.0%, extra_functions 68 -> 0. Several conversion operators GitGalaxy and tree-sitter now agree on (ctags names them without the `operator ` prefix or misses the `_FORCE_INLINE_`-macro forms) shifted into this shape, count ~9 -> ~21 -- still GitGalaxy+tree-sitter correct, ctags limited.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/object.h | `operator Ref` | 1035 | 1036 | *(n/a)* |
| godot/rendering_server_default.h | `mesh_create_from_surfaces` | 363 | 363 | *(n/a)* |
| godot/rendering_server_default.h | `material_create_from_shader` | 324 | 324 | *(n/a)* |
| godot/rendering_server_default.h | `shader_create` | 278 | 278 | *(n/a)* |
| godot/rendering_server_default.h | `texture_create_from_native_handle` | 222 | 222 | *(n/a)* |
| godot/rendering_server_default.h | `redraw_request` | 111 | 111 | *(n/a)* |
| godot/variant.cpp | `Variant::operator ::RID` | 2002 | 2002 | *(n/a)* |
| godot/variant.cpp | `Variant::operator Vector` | 2219 | 2219 | *(n/a)* |
| godot/variant.cpp | `Variant::operator Vector` | 2229 | 2229 | *(n/a)* |
| godot/variant.cpp | `Variant::operator Vector` | 2247 | 2247 | *(n/a)* |

### ✅ `cpp` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 14 occurrences as of 2026-11-26T05:32:54Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real tree-sitter-cpp grammar limitation, not a GitGalaxy or ctags defect. Every sampled case (GDScriptFunction::call, Main::setup, Main::setup2, Main::start, Object::Connection::operator Variant) is a large, complex function -- GDScriptFunction::call in particular (godot/gdscript_vm.cpp:499) is a bytecode interpreter's main dispatch loop using GNU 'labels as values' computed-goto syntax (`&&OPCODE_LABEL`) via the same OPCODES_TABLE/OPCODE macro family documented in the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] entry -- a non-standard GNU extension tree-sitter-cpp's grammar does not support, which plausibly causes a parse error cascade that loses the enclosing function_definition node entirely rather than just misreading the body. ctags and GitGalaxy both correctly find and name these functions regardless of body content, since neither one needs to fully parse the function body to recognize its signature. tree-sitter's non-detection is a confirmed limitation in tree-sitter itself -- but no credit_tools adjustment applies: ctags and GitGalaxy are already a 2-of-3 AGREEING PAIR on this shape (agreeing_tools has 2 members), which already satisfies reconcile_symbols' own `len(present) >= 2` precision-credit condition naturally with no ledger adjustment needed. credit_tools exists for a LONE, single-tool claim (agreeing_tools with exactly 1 member) the base algorithm can't otherwise corroborate -- applying it to an already-mutually-corroborating pair would double-count (confirmed: this exact mistake briefly pushed ctags' precision past 100% before being caught and reverted in this same session). 2026-08-29 follow-up (#2455): the tree_sitter_accuracy_audit / tri_comparison_gatherer shared tree-sitter reader now canonicalizes C++ conversion-operator and destructor names to GitGalaxy's own convention -- `Variant::operator String() const` -> `Variant::operator String`, `operator BitField<T>() const` -> `operator BitField`, and the `_FORCE_INLINE_`-macro-mangled `~Variant` / `operator T` forms recovered from the sibling ERROR node -- and treats a small tree-sitter-cpp ERROR node (a function-like macro with no visible definition immediately before a special member) as a blind-spot region, promoting GitGalaxy's correct extraction there to ground truth. cpp function precision 95.0% -> 100.0%, extra_functions 68 -> 0. `Object::Connection::operator Variant` (doubly-qualified conversion operator) is now in consensus. The residual (`GDScriptFunction::call`, `Main::setup*`) is the computed-goto / OPCODES_TABLE parse cascade that loses the whole `function_definition` node -- GitGalaxy and ctags both still correct, count ~66 -> ~14.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/gdscript_vm.cpp | `GDScriptFunction::call` | 499 | *(n/a)* | 499 |
| godot/main.cpp | `Main::setup` | 1027 | *(n/a)* | 1027 |
| godot/main.cpp | `Main::setup2` | 3007 | *(n/a)* | 3007 |
| godot/main.cpp | `Main::start` | 3987 | *(n/a)* | 3987 |
| godot/object.h | `operator=` | 970 | *(n/a)* | 971 |
| godot/object.h | `RequiredResult` | 976 | *(n/a)* | 977 |
| godot/object.h | `RequiredResult` | 985 | *(n/a)* | 986 |
| godot/object.h | `RequiredResult` | 994 | *(n/a)* | 995 |
| godot/object.h | `RequiredResult` | 1003 | *(n/a)* | 1004 |
| godot/object.h | `RequiredResult` | 1012 | *(n/a)* | 1013 |

### ✅ `cpp` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-11-26T05:32:54Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Not a real existence disagreement -- a template-argument name-formatting difference in the comparison tooling. `godot/variant.h`'s `HashMapComparatorDefault<Variant>` and `is_zero_constructible<Variant>` are template CLASS specializations; GitGalaxy and tree-sitter both read the name WITH its template argument baked in (matching the instantiation as written in source), while ctags strips the `<...>` template-argument suffix from its own class tag name. All three tools found the exact same class definition at the exact same line -- confirmed via the sibling agree[gitgalaxy,tree_sitter]_vs[ctags] entry, which is the same pair of classes from the opposite direction. Low magnitude (2 occurrences) -- not chased to a code fix in this pass, but a plausible future micro-fix would strip a trailing `<...>` from gg/tree-sitter's class name before matching, mirroring how ctags_reader.py's operator-name normalization already handles a similar formatting mismatch.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `HashMapComparatorDefault` | *(n/a)* | *(n/a)* | 886 |
| godot/variant.h | `is_zero_constructible` | *(n/a)* | *(n/a)* | 984 |

### ✅ `cpp` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-11-26T05:32:54Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Same template-argument name-formatting difference as the sibling agree[ctags]_vs[gitgalaxy,tree_sitter] class entry, viewed from the opposite direction -- `HashMapComparatorDefault`/`is_zero_constructible` (ctags' bare names) vs. `HashMapComparatorDefault<Variant>`/`is_zero_constructible<Variant>` (GitGalaxy/tree-sitter's names, template argument included). Not a real disagreement about whether these classes exist -- see the sibling entry for the full explanation.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| godot/variant.h | `HashMapComparatorDefault<Variant>` | *(n/a)* | 886 | *(n/a)* |
| godot/variant.h | `is_zero_constructible<Variant>` | *(n/a)* | 984 | *(n/a)* |

## crystal

### ❓ `crystal` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 46 occurrences as of 2026-11-26T05:32:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`crystal/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| crystal_stdlib_http/client.cr | `tls_flag` | 882 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `should_retry_request?` | 666 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `io` | 832 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `retry_once` | 684 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `exec_internal` | 581 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `exec_internal` | 628 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `host_header` | 861 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `set_defaults` | 725 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `implicit_compression?` | 734 | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/client.cr | `exec` | 575 | *(n/a)* | *(n/a)* |

### ❓ `crystal` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:32:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`crystal/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| crystal_stdlib_http/client.cr | `ethod` | *(n/a)* | 413 | *(n/a)* |
| crystal_stdlib_http/client.cr | `ethod` | *(n/a)* | 472 | *(n/a)* |
| crystal_stdlib_http/client.cr | `ethod` | *(n/a)* | 490 | *(n/a)* |
| crystal_stdlib_http/client.cr | `ethod` | *(n/a)* | 507 | *(n/a)* |
| crystal_stdlib_http/client.cr | `ethod` | *(n/a)* | 524 | *(n/a)* |
| kemal_framework/kemal_dsl.cr | `method` | *(n/a)* | 44 | *(n/a)* |
| kemal_framework/kemal_dsl.cr | `type` | *(n/a)* | 174 | *(n/a)* |

### ❓ `crystal` class existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 5 occurrences as of 2026-11-26T05:32:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`crystal/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| crystal_stdlib_http/common.cr | `HTTP` | *(n/a)* | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/server.cr | `HTTP::Server` | *(n/a)* | *(n/a)* | *(n/a)* |
| crystal_stdlib_http/server_handlers_compress_handler.cr | `HTTP::CompressHandler` | *(n/a)* | *(n/a)* | *(n/a)* |
| kemal_framework/kemal_ext_response.cr | `HTTP::Server::Response` | *(n/a)* | *(n/a)* | *(n/a)* |
| kemal_framework/kemal_handler.cr | `Handler` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `crystal` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 48 occurrences as of 2026-11-26T05:32:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`crystal/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| crystal_stdlib_http/client.cr | `read_timeout=` | 1 | 0 | *(n/a)* |
| crystal_stdlib_http/client.cr | `write_timeout=` | 1 | 0 | *(n/a)* |
| crystal_stdlib_http/client.cr | `connect_timeout=` | 1 | 0 | *(n/a)* |
| crystal_stdlib_http/client.cr | `dns_timeout=` | 1 | 0 | *(n/a)* |
| crystal_stdlib_http/common.cr | `serialize_headers_and_body` | 6 | 7 | *(n/a)* |
| crystal_stdlib_http/content.cr | `read_token` | 2 | 1 | *(n/a)* |
| crystal_stdlib_http/content.cr | `initialize` | 2 | 3 | *(n/a)* |
| crystal_stdlib_http/cookie.cr | `name=` | 1 | 0 | *(n/a)* |
| crystal_stdlib_http/cookie.cr | `value=` | 1 | 0 | *(n/a)* |
| crystal_stdlib_http/cookie.cr | `secure=` | 1 | 0 | *(n/a)* |

## csharp

### ❓ `csharp` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:33:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`csharp/class/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Max.cs | `IBinaryInteger` | *(n/a)* | *(n/a)* | 28 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Max.cs | `IBinaryInteger` | *(n/a)* | *(n/a)* | 524 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Max.cs | `IBinaryInteger` | *(n/a)* | *(n/a)* | 556 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Max.cs | `IFloatingPointIeee754` | *(n/a)* | *(n/a)* | 96 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Max.cs | `IFloatingPointIeee754` | *(n/a)* | *(n/a)* | 164 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Max.cs | `IFloatingPointIeee754` | *(n/a)* | *(n/a)* | 629 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Max.cs | `IFloatingPointIeee754` | *(n/a)* | *(n/a)* | 671 |

### ✅ `csharp` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 272 occurrences as of 2026-11-26T05:33:03Z*

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
| roslyn/LanguageParser.cs | `IsPossibleExpression` | 11073 | *(n/a)* | 11073 |
| roslyn/LanguageParser.cs | `IsPossibleExpression` | 11078 | *(n/a)* | 11078 |
| roslyn/LanguageParser.cs | `CanFollowCast` | 13159 | *(n/a)* | 13159 |
| roslyn/LanguageParser.cs | `ParseTypeCore` | 7592 | *(n/a)* | 7592 |

### ✅ `csharp` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 149 occurrences as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T18:13:44Z):
> Confirmed real ctags parser limitations, not a GitGalaxy or tree-sitter defect, via direct source reading and raw `ctags -x` runs against the flagged files. Two distinct mechanisms: (1) Local/nested functions -- roslyn/CSharpCompilation.cs's `validateSignature` (nested inside a larger method) and `isSupportedType` (a `static bool isSupportedType(...)` local function) are both structurally invisible to ctags, whose csharp kind map is only 'm' (top-level methods; "C# has no free functions" per ctags_reader.py's own comment) with no local-function concept at all -- this generalizes to every local function in the corpus, not just the sampled two. (2) Complex-signature misses and overload collisions on ordinary top-level private methods -- `FindEntryPoint` (nullable return/param types plus a generic `out` parameter) and `GetSourceDeclarationDiagnostics` (5 params, two with default values, one a `Func<...>` generic delegate) get no ctags tag at all, confirmed via `ctags -x` showing tags immediately before/after but not at their own lines -- isolated misses, not a wider blind region (unlike the tree-sitter cascade in the sibling ledger shape). `ReportUnusedImports` has two overloads at different lines; ctags tags only the first, silently dropping the second. Documented in tests/tools/ctags_reader.py's csharp KIND MAPS bullet. Credited on the strength of mechanism (1) generalizing structurally to the whole shape (ctags cannot see ANY local function, by construction) even though only ~5 of 107 occurrences were individually read -- mechanism (2)'s complex-signature misses are a smaller, less certain-to-generalize contributor to the same shape but point the same direction (ctags-side, not GitGalaxy/tree-sitter). CORRECTION (2026-08-21): credit_tools was originally set here, but this is wrong -- these tools already mutually corroborate each other (2-of-3 agreement), so their occurrences were already counted in base precision before any credit was applied. Adding credit on top double-counted them, pushing gitgalaxy's func_precision matched_consensus past its own total_slots (1297/965, >100%, a real, visible chart-rendering bug). credit_tools is only valid for a shape where a tool is completely ALONE and otherwise uncorroborated (e.g. this language's agree[gitgalaxy]_vs[ctags,tree_sitter] shape), never for an already-mutually-agreeing pair. Reset to empty; the validation itself (which tool is factually correct here) is unaffected and remains correct.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| powertoys_common/src_common_UITestAutomation_ModuleConfigData.cs | `GetModuleWindowName` | 161 | 161 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `FindEntryPoint` | 1993 | 1993 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `validateSignature` | 4463 | 4463 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `validateSignature` | 4689 | 4689 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `ReportUnusedImports` | 2747 | 2747 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `GetSourceDeclarationDiagnostics` | 3395 | 3395 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `isSupportedType` | 1798 | 1798 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `registeredUsageOfUsingsInTree` | 3359 | 3359 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `IsRuntimeAsyncEnabledIn` | 351 | 351 | *(n/a)* |
| roslyn/CSharpCompilation.cs | `updateCachedDiagnostics` | 3308 | 3308 | *(n/a)* |

### ✅ `csharp` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 46 occurrences as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T21:45:53Z):
> Mixed shape, confirmed via a full name-diff against gather_language('csharp') rather than the capped sample alone: 44 of 48 are genuine local (nested) functions inside roslyn/LanguageParser.cs's tree-sitter parse-error cascade region (line >= ~5198, same mechanism as the sibling agree[ctags,gitgalaxy]_vs[tree_sitter] shape / Claim 3) -- tree-sitter is fully blind there, and ctags additionally has no concept of a local/nested function at all (only top-level 'm' method tags), so GitGalaxy is the only tool that can see these. The remaining 2 are genuine GitGalaxy false positives with a confirmed, unrelated root cause: roslyn/CSharpCompilation.cs:2282's GetWellKnownType( (a call, no declaration exists anywhere in the file) and roslyn/LanguageParser.cs:2338's this.EatToken( (a call inside a switch-expression arm) are both mis-captured because func_start's return-type-loop character class allows unbalanced parens/commas in a single 'token', letting it swallow a real call-expression fragment as if it were part of a return type and land on the wrong identifier as the 'function name'. Filed as GitHub issue #2035 with root cause and fix direction; fix in progress in an isolated worktree as of this writing. Not crediting/debiting any tool on this shape since it's genuinely mixed (44 real local-function finds, 2 real false positives) -- re-visit once #2035 merges and re-run to confirm the shape drops to 44 (or fewer, if further false positives of the same class surface once #2035's fix generalizes across the full corpus). FOLLOW-UP (2026-08-21, post-#2035/#2036 re-verification): re-checked this shape with a full, uncapped corpus diff rather than the capped example sample. The 2 originally-confirmed false positives (GetWellKnownType, this.EatToken) are gone as expected. However 2 MORE confirmed false positives remain, distinct mechanisms from #2035's fix: CSharpCompilation.cs's `ref mdName, ..., CreateReflectionTypeNotFoundError(` (a real call site mistaken for a declaration because `ref` is a legitimate Branch A modifier keyword when used in a real declaration, but here it's a call-argument prefix) and LanguageParser.cs:2336's `_syntaxFactory.TypeConstraint(this.ParseType())` (a ternary `?` operator consumed by the return-type loop's nullable-type-marker allowance, same general shape as this.EatToken but not covered by #2035's specific fix). Filed as issue #2054. This shape remains genuinely mixed (the overwhelming majority are real cascade-region local functions, but a small residual of false positives keeps surfacing) -- still correctly left uncredited pending #2054. CLOSED (2026-08-21): this shape is now fully clean. Both remaining false-positive mechanisms (issue #2054: bare-comma call-argument absorption, ternary-? consumption, and the nested-generic-return-type regression its own fix introduced and #2061 corrected) are fixed and merged. A full uncapped re-diff confirms all 44 remaining occurrences are genuine local functions inside LanguageParser.cs's tree-sitter parse-error cascade region (Claim 3), zero non-cascade residue. credit_tools is now correctly applicable -- gitgalaxy is alone on this shape (no tool to share the credit-double-counting error this session already found and fixed on the sibling agree[ctags,gitgalaxy]/agree[gitgalaxy,tree_sitter] shapes with), and every one of its 44 claims here is confirmed real with the reason ctags (no local-function concept) and tree-sitter (parse cascade) don't corroborate it being a confirmed limitation in THEM, not an open question about GitGalaxy.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/LanguageParser.cs | `parsePrimaryExpressionWithoutPostfix` | 11940 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ParseCommaSeparatedSyntaxList` | 14422 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `ParseCommaSeparatedSyntaxList` | 14444 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parsePostFixExpression` | 12115 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `canFollowNullableType` | 7719 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `tryExpandExpression` | 11546 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `tokenBreaksTypeArgumentList` | 6626 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseCallingConvention` | 8100 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseSwitchHeader` | 10175 | *(n/a)* | *(n/a)* |
| roslyn/LanguageParser.cs | `parseUnaryOrPrimaryExpression` | 11452 | *(n/a)* | *(n/a)* |

### ✅ `csharp` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 9 occurrences as of 2026-11-26T05:33:03Z*

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

### ✅ `csharp` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-26T00:00:00Z):
> Stale -- fixed. ShouldCheckTypeForMembers, Matches, GetRoot, Initialize are all bodyless (';'-terminated) abstract/interface method declarations that closed issue #2036 (detector.py unconditionally dropped every bodyless interface/abstract method declaration) fixed. A fresh gather confirms gitgalaxy now finds all 4 (matching ctags and tree-sitter) -- `docs/language_status/csharp.md` §10 names these exact functions as recovered by #2036.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| runtime_linq/src_libraries_System.Linq_src_System_Linq_OrderedEnumerable.cs | `CreateOrderedEnumerable` | *(n/a)* | 29 | 29 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Repeat.SpeedOpt.cs | `Clear` | *(n/a)* | 112 | 112 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Repeat.SpeedOpt.cs | `Insert` | *(n/a)* | 113 | 113 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Repeat.SpeedOpt.cs | `RemoveAt` | *(n/a)* | 115 | 115 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_SkipTake.SpeedOpt.cs | `Clear` | *(n/a)* | 211 | 211 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_SkipTake.SpeedOpt.cs | `Insert` | *(n/a)* | 212 | 212 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_SkipTake.SpeedOpt.cs | `RemoveAt` | *(n/a)* | 214 | 214 |

### ✅ `csharp` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 5 occurrences as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-26T00:00:00Z):
> Stale -- fixed, same #2036 fix as the ShouldCheckTypeForMembers/Matches/GetRoot/Initialize shape. TryGetRoot (roslyn/CSharpSyntaxTree.cs:91, `public abstract bool TryGetRoot([NotNullWhen(true)] out CSharpSyntaxNode? root);`) is a bodyless abstract method declaration; #2036 (closed) recovered it. A fresh gather confirms gitgalaxy and tree-sitter both find it now; only ctags still misses it -- a separate, pre-existing, already-documented ctags complex-signature limitation (docs/language_status/csharp.md §10), not a new finding.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| runtime_linq/src_libraries_System.Linq_src_System_Linq_OrderedEnumerable.cs | `GetEnumerator` | *(n/a)* | 27 | *(n/a)* |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Repeat.SpeedOpt.cs | `Add` | *(n/a)* | 111 | *(n/a)* |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Repeat.SpeedOpt.cs | `Remove` | *(n/a)* | 114 | *(n/a)* |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_SkipTake.SpeedOpt.cs | `Add` | *(n/a)* | 210 | *(n/a)* |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_SkipTake.SpeedOpt.cs | `Remove` | *(n/a)* | 213 | *(n/a)* |

### ✅ `csharp` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 3 occurrences as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T20:06:45Z):
> Mixed shape. 1 of 4 is a confirmed genuine ctags defect: GetHashCode's tuple-parameter overload (`GetHashCode((ImmutableArray<byte> ContentHash, int Position) obj)`, 1 real param) -- ctags reports 2, mis-splitting the tuple-typed parameter's own internal comma as a second top-level parameter, the same family as the already-documented tuple-related ctags limitations in tests/tools/ctags_reader.py's csharp bullet. The other 3 (GetModifierExcludingScoped and two SetCurrentSolution rows) are NOT real tool disagreements at all -- SetCurrentSolution has 4 real overloads (1/6/4/5 real params respectively) in roslyn/Workspace.cs; every individual reading from every tool across both rows (ctags=6, gitgalaxy=1, tree_sitter=1, ctags=4, gitgalaxy=6, tree_sitter=6) independently matches SOME real overload's true count exactly when checked against the source -- the ledger shape only exists because the reconciler's rank-based pairing compared different tools' readings of DIFFERENT overloads against each other, not because any tool actually miscounted anything. Confirmed via direct line-by-line source reading of all 4 overloads. Credit gitgalaxy+tree_sitter for the 1 real ctags defect only; the shape as a whole is left without a clean credit/debit since 3 of 4 occurrences aren't a real disagreement to adjudicate.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| roslyn/CSharpCompilation.cs | `GetHashCode` | 1 | 1 | 2 |
| roslyn/LanguageParser.cs | `GetModifierExcludingScoped` | 1 | 1 | 2 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_OrderedEnumerable.cs | `SortedMap` | 1 | 1 | 3 |

### ✅ `csharp` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 3 occurrences as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T18:13:27Z):
> Confirmed genuine ctags false positive, not a GitGalaxy or tree-sitter gap. roslyn/CSharpCompilation.cs:2539's real declaration is `public bool Equals((ImmutableArray<byte> ContentHash, int Position) x, (ImmutableArray<byte> ContentHash, int Position) y)` -- an Equals overload with tuple-typed parameters. ctags' lightweight C# parser misreads the return-type/tuple-parameter boundary and tags the match under the name `bool` instead of `Equals`. Documented in tests/tools/ctags_reader.py's csharp KIND MAPS bullet alongside this shape's sibling ctags limitations (local-function blindness, complex-signature misses, overload-name collision -- see the agree[gitgalaxy,tree_sitter]_vs[ctags] shape). Not crediting/debiting: a single-tool false positive from an otherwise-unaffected precision baseline, no shared-mistake mechanism applies.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| powershell_commands_utility/src_Microsoft.PowerShell.Commands.Utility_commands_utility_trace_MshHostTraceListener.cs | `~PSHostTraceListener` | *(n/a)* | *(n/a)* | 43 |
| roslyn/CSharpCompilation.cs | `bool` | *(n/a)* | *(n/a)* | 2539 |
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Cast.cs | `CastICollectionIterator` | *(n/a)* | *(n/a)* | 45 |

### ✅ `csharp` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-26T00:00:00Z):
> Stale, pre-fix snapshot -- confirmed no longer reproducing. The 5 sampled names (TerminatorState, NamespaceParts, LanguageParserState, AccessorDeclaringKind, PostSkipAction -- private nested enums in roslyn/LanguageParser.cs) are all correctly tagged by ctags as kind 'enum' as of a fresh corpus-wide gather (confirmed via direct `ctags --language-force=C# --output-format=json` run and via tri_comparison_gatherer, ctags=True for every one). ctags_reader.py's csharp KIND_MAP already covers enum ('g') as a class-equivalent kind. No current defect in any tool for this shape; a subsequent regen with real, correctly-invoked ctags simply no longer produces this disagreement.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| runtime_linq/src_libraries_System.Linq_src_System_Linq_Cast.cs | `CastICollectionIterator` | *(n/a)* | 44 | *(n/a)* |

### ✅ `csharp` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:33:03Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-26T00:00:00Z):
> Stale, superseded by the now-live, already-validated 3-tool shape `csharp/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]` (9 occurrences, still_reproduces=true). This 6-occurrence 2-tool shape (VariableFlags, NameOptions, ScanTypeArgumentListKind, ScanTypeFlags, ParseTypeMode, Precedence -- private nested enums in roslyn/LanguageParser.cs, all declared past line 5198) dates from a period where ctags' reading was unavailable/degraded (see CLAUDE.md's PR #2111 incident and tri-comparison-chart.md's 'always regenerate --all' rule); a fresh gather confirms ctags now correctly finds all 6 names, collapsing this shape into the 3-tool one where only tree-sitter dissents -- the documented Claim 3 parse-error-cascade mechanism (LanguageParser.cs's C# 11 list-pattern trigger at line 5198 corrupts tree-sitter-c-sharp's recovery for the rest of the 14,680-line file).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| powertoys_common/src_common_LanguageModelProvider_FoundryLocal_FoundryCatalogModel.cs | `FoundryCatalogModel` | *(n/a)* | *(n/a)* | *(n/a)* |

## css

### ✅ `css` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 164 occurrences as of 2026-11-26T05:33:10Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed ctags-side structural limitation, not a GitGalaxy defect. GitGalaxy's own func_start regex (language_standards.py) deliberately matches CSS at-rule keywords (@media/@supports/@container/@layer/@keyframes/@-webkit-keyframes) as the closest function-shaped construct CSS has, since CSS has no true function-definition/call syntax. tree-sitter's CSS grammar independently corroborates this: media_statement/supports_statement/keyframes_statement are real, distinct node types, already mapped 1:1 onto GitGalaxy's own at-rule set per issue #1313 (see tree_sitter_accuracy_audit.py's css NODE_MAPS entry and its media_statement/supports_statement name-extraction branches). Re-ran gather_language('css') directly against the full 4-file corpus (not just the ledger's capped 3-example sample): GitGalaxy and tree-sitter agree exactly on function count in every file (3/3 total, zero diff files) -- the agreement generalizes completely, it is not a partial/mixed sample. ctags' own FUNCTION_KIND_MAP already documents 'css': set()  # no function-equivalent (ctags_reader.py) -- confirmed empty (ctags_funcs: []) across all 4 corpus files too. ctags structurally cannot tag CSS at-rules as anything function-like; it isn't wrong about a claim, it has no claim to make here at all. No new doc note needed -- both the GitGalaxy/tree-sitter convention (#1313) and the ctags limitation are already documented in code. GitGalaxy+tree-sitter's agreement is real corroboration, not a shared mistake, so no credit/debit adjustment applies; ctags' lack of a comparable slot here is already handled correctly by the reconciler's own total_slots mechanics.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bootstrap_dist/bootstrap-grid.css | `media` | 22 | 22 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 27 | 27 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 32 | 32 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 37 | 37 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 42 | 42 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 283 | 283 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 452 | 452 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 621 | 621 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 790 | 790 | *(n/a)* |
| bootstrap_dist/bootstrap-grid.css | `media` | 959 | 959 | *(n/a)* |

## dart

### ❓ `dart` class existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 9 occurrences as of 2026-11-26T05:33:15Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`dart/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dart_sdk_language_tests/tests_language_mixin_legacy_illegal_constructor_test.dart | `C0` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_mixin_legacy_illegal_constructor_test.dart | `C1` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_mixin_legacy_illegal_constructor_test.dart | `C2` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_mixin_legacy_illegal_constructor_test.dart | `C3` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_mixin_legacy_illegal_constructor_test.dart | `C4` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_mixin_legacy_illegal_constructor_test.dart | `C5` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_mixin_legacy_illegal_constructor_test.dart | `C6` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_nonfunction_type_aliases_generic_usage_null_test.dart | `E` | *(n/a)* | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_regress_regress18713_legacy_test.dart | `TS` | *(n/a)* | *(n/a)* | *(n/a)* |

### ✅ `dart` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 14 occurrences as of 2026-11-26T05:33:15Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real GitGalaxy engine defect, not a tree-sitter limitation. Root-caused two distinct false-positive bugs in dart's func_start regex's zero-prefix branch, both in gitgalaxy/standards/language_standards.py: (1) Dart 3 switch-expression arms (`Pattern => result,` including bare `_ => result,`) matched as getter definitions, because the branch's bare-`=>` lookahead alternative was unconditional (no `get` keyword required) even though Dart's real grammar has no parameterless `=> expr` construct without `get`. (2) Call statements with a lambda argument (`obj.method((x) => ...)`, `setState(() {...})`, bare self-calls like `visitChildren((Element child) {...})`) matched as function definitions, because the paren-lookahead used a naive non-balanced-paren check (`\([^)]*\)`) that stopped at the lambda's own closing paren instead of the outer call's. A full corpus-wide before/after diff (language-crucible/data/dart, 7 Flutter framework files) confirmed 126 false-positive matches removed and only 1 new match gained (a genuine recall fix for EditableText's own multi-line constructor) -- every one of the 126 manually spot-checked as a real false positive (dotted call receiver, or a statement ending `);`, or a switch-expression arm), none a lost real definition. Fixed in gitgalaxy#2071 (merged via this ledger-sweep PR) by gating the bare-arrow alternative behind the existing `get`-group conditional and switching to the same balanced-paren pattern already used elsewhere in this regex. A smaller, related false positive (multi-line class headers with with/implements clauses absorbed as a phantom function's return-type prefix, e.g. `implements AutofillClient {` matching as a function named AutofillClient) was found in the same investigation but is NOT fixed -- the straightforward fix (excluding implements/with/extends from the return-type-prefix vocabulary) was tested and confirmed to break a much more common legitimate pattern, generic method type-parameter bounds (`static Future<T?> pushNamed<T extends Object?>(...)`), which also uses `extends`. Tracked in gitgalaxy#2072 along with several other confirmed-but-deferred recall gaps found in the same pass.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dart_sdk_analyzer/pkg_analyzer_lib_src_dart_analysis_status.dart | `async` | 132 | *(n/a)* | *(n/a)* |
| dart_sdk_analyzer/pkg_analyzer_lib_src_dart_element_replacement_visitor.dart | `LinkingTypeVisitor` | 27 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_control_flow_collections_for_await_test.dart | `testMap` | 15 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_control_flow_collections_for_await_test.dart | `testList` | 14 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_control_flow_collections_for_await_test.dart | `testSet` | 16 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_identifier_built_in_identifier_test.dart | `static` | 60 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_identifier_built_in_identifier_test.dart | `static` | 90 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_identifier_built_in_identifier_test.dart | `operator=` | 101 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_identifier_built_in_identifier_test.dart | `operator` | 95 | *(n/a)* | *(n/a)* |
| dart_sdk_language_tests/tests_language_patterns_exhaustiveness_null_type_test.dart | `Unknown_Block` | 11 | *(n/a)* | *(n/a)* |

### ✅ `dart` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 3 occurrences as of 2026-11-26T05:33:15Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-21T00:00:00Z):
> Confirmed real GitGalaxy recall gaps (tree-sitter is correct), several distinct causes found via direct source investigation against language-crucible/data/dart. Some entries in this shape's original capped example list were incidentally resolved as a side effect of the func_start fix in gitgalaxy#2071 (e.g. EditableText's own multi-line constructor, generic-return-type getters like `Iterable<Element> get children =>`, and dotted-name getters like `T? get currentState => switch (...) {...}` all now regex-match correctly and reach the final pipeline output). A post-fix full-corpus name-diff still shows 12 residual missing_from_gg cases across 5 distinct confirmed root causes, none yet fixed: (1) EditableText's constructor and a private named constructor (_DiscreteKeyFrameSimulation._(...)) regex-match (confirmed via direct probe) but don't reach the final pipeline output -- a detector.py-level extraction bug downstream of the regex, not yet traced; (2) static getters with a dotted/prefixed-import return type (`static ui.BoxHeightStyle get defaultSelectionHeightStyle {`) never regex-match at all, because the return-type-prefix character class excludes `.`; (3) bodyless default constructors (`_EditableTextTapOutsideAction();`) don't regex-match; (4-5) several more names (recorder, ChildSemanticsConfigurationsResultBuilder, OrdinalSortKey, SemanticsData, SemanticsProperties, extension) not yet individually root-caused. All tracked as a consolidated follow-up in gitgalaxy#2072 -- deliberately not rushed, since the sibling existence shape's investigation already found one naive fix (broadening the return-type charclass or the keyword-exclusion list) can silently break a much more common legitimate pattern elsewhere, so each of these needs its own regression check before shipping.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dart_sdk_analyzer/pkg_analyzer_lib_src_dart_analysis_status.dart | `signal` | *(n/a)* | 132 | *(n/a)* |
| dart_sdk_language_tests/tests_language_identifier_built_in_identifier_test.dart | `Expect` | *(n/a)* | 92 | *(n/a)* |
| dart_sdk_language_tests/tests_language_nonfunction_type_aliases_generic_usage_null_test.dart | `C1.name1` | *(n/a)* | 41 | *(n/a)* |

## erlang

### ❓ `erlang` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 501 occurrences as of 2026-11-26T05:33:22Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`erlang/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cowboy_http_server/cowboy.erl | `log` | *(n/a)* | 230 | *(n/a)* |
| cowboy_http_server/cowboy.erl | `ensure_dynamic_buffer` | *(n/a)* | 179 | *(n/a)* |
| cowboy_http_server/cowboy.erl | `ensure_connection_type` | *(n/a)* | 169 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `terminate_loop` | *(n/a)* | 136 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `before_terminate_loop` | *(n/a)* | 115 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `longest_shutdown_time` | *(n/a)* | 157 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `longest_shutdown_time` | *(n/a)* | 159 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `handle_supervisor_call` | *(n/a)* | 166 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `handle_supervisor_call` | *(n/a)* | 171 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `handle_supervisor_call` | *(n/a)* | 176 | *(n/a)* |

### ❓ `erlang` class existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 52 occurrences as of 2026-11-26T05:33:22Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`erlang/class/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cowboy_http_server/cowboy.erl | `cowboy` | *(n/a)* | 15 | *(n/a)* |
| cowboy_http_server/cowboy_app.erl | `cowboy_app` | *(n/a)* | 15 | *(n/a)* |
| cowboy_http_server/cowboy_app.erl | `application` | *(n/a)* | 16 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `cowboy_children` | *(n/a)* | 15 | *(n/a)* |
| cowboy_http_server/cowboy_children.erl | `child` | *(n/a)* | 25 | *(n/a)* |
| cowboy_http_server/cowboy_clear.erl | `cowboy_clear` | *(n/a)* | 15 | *(n/a)* |
| cowboy_http_server/cowboy_clear.erl | `ranch_protocol` | *(n/a)* | 16 | *(n/a)* |
| cowboy_http_server/cowboy_clock.erl | `cowboy_clock` | *(n/a)* | 19 | *(n/a)* |
| cowboy_http_server/cowboy_clock.erl | `gen_server` | *(n/a)* | 20 | *(n/a)* |
| cowboy_http_server/cowboy_clock.erl | `state` | *(n/a)* | 35 | *(n/a)* |

### ❓ `erlang` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 41 occurrences as of 2026-11-26T05:33:22Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`erlang/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cowboy_http_server/cowboy_compress_h.erl | `fold` | 3 | 2 | *(n/a)* |
| cowboy_http_server/cowboy_constraints.erl | `int` | 3 | 2 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `parse_unidirectional_stream_header` | 0 | 4 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `headers_frame_parse_host` | 0 | 7 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `send_response` | 0 | 5 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `frame` | 0 | 4 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `reset_stream` | 0 | 3 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `become_webtransport_stream` | 0 | 6 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `early_error` | 0 | 7 | *(n/a)* |
| cowboy_http_server/cowboy_http3.erl | `webtransport_terminate_session` | 0 | 2 | *(n/a)* |

## fortran

### ❓ `fortran` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 8 occurrences as of 2026-11-26T05:33:27Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fpm_fortran/example_packages_submodule_tree_shake_src_parent_unused.f90 | `unused_sub` | 6 | 6 | *(n/a)* |
| fpm_fortran/src_fpm_environment.f90 | `c_setenv` | 459 | 459 | *(n/a)* |
| fpm_fortran/src_fpm_environment.f90 | `c_unsetenv` | 502 | 502 | *(n/a)* |
| stdlib_fortran/src_system_stdlib_load_library.f90 | `c_loadlib_open` | 84 | 84 | *(n/a)* |
| stdlib_fortran/src_system_stdlib_load_library.f90 | `c_loadlib_symbol` | 94 | 94 | *(n/a)* |
| stdlib_fortran/src_system_stdlib_load_library.f90 | `c_loadlib_data` | 104 | 104 | *(n/a)* |
| stdlib_fortran/src_system_stdlib_load_library.f90 | `c_loadlib_close` | 114 | 114 | *(n/a)* |
| wrf/module_initialize_real.F | `vint` | 5375 | 5375 | *(n/a)* |

### ❓ `fortran` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:33:27Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fpm_fortran/example_packages_submodule_tree_shake_src_parent_unused.f90 | `module` | *(n/a)* | *(n/a)* | *(n/a)* |
| fpm_fortran/src_fpm_environment.f90 | `integer` | *(n/a)* | *(n/a)* | *(n/a)* |
| fpm_fortran/src_fpm_environment.f90 | `integer` | *(n/a)* | *(n/a)* | *(n/a)* |
| stdlib_fortran/src_system_stdlib_load_library.f90 | `function` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `fortran` class existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:33:27Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fortran/class/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_initialize_real.F | `module_initialize_real` | *(n/a)* | 9205 | *(n/a)* |

### ✅ `fortran` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 20 occurrences as of 2026-11-26T05:33:27Z*

**Verdict** (by Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-21T23:35:49Z):
> Confirmed already-documented tree-sitter-fortran limitation (#1709/Claim 7 in docs/why_gitgalaxy_beats_ast_here.md), re-verified directly against this exact shape's 14 occurrences (11 in wrf/module_physics_init.F: bl_init, ra_init, landuse_init, mp_init, cu_init, shcu_init, CAM_INIT, z2sigma, fdob_init, fg_init, ALLOCATE_CAM_ARRAYS; 3 in wrf/wrf_timeseries.F: calc_p8w, calc_ts, write_ts). Directly ran tree_sitter_accuracy_audit.py's own _find_blind_spot_ranges() against both files' real parse trees: every one of the 14 occurrences' start lines falls inside a tree-sitter ERROR/preproc_* blind-spot range (e.g. bl_init/mp_init/cu_init/shcu_init all sit inside one continuous (2203,4393) span; all 3 wrf_timeseries.F occurrences fall inside a (1,1200) span). ctags and GitGalaxy are both correct; tree-sitter-fortran's own grammar cascades into ERROR nodes on the CPP #if/#endif guards surrounding these subroutines. Added as new evidence to the existing Claim 7 in docs/why_gitgalaxy_beats_ast_here.md (this ledger shape is independently sourced from the original accuracy-audit finding -- a raw per-file name diff via tri_comparison_gatherer.py, not the audit tool's promotion logic).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_initialize_real.F | `const_module_initialize` | 4951 | *(n/a)* | 4951 |
| wrf/module_physics_init.F | `bl_init` | 2461 | *(n/a)* | 2461 |
| wrf/module_physics_init.F | `mp_init` | 4365 | *(n/a)* | 4365 |
| wrf/module_physics_init.F | `ra_init` | 2033 | *(n/a)* | 2033 |
| wrf/module_physics_init.F | `landuse_init` | 1745 | *(n/a)* | 1745 |
| wrf/module_physics_init.F | `cu_init` | 3923 | *(n/a)* | 3923 |
| wrf/module_physics_init.F | `shcu_init` | 4217 | *(n/a)* | 4217 |
| wrf/module_physics_init.F | `CAM_INIT` | 5038 | *(n/a)* | 5038 |
| wrf/module_physics_init.F | `z2sigma` | 4965 | *(n/a)* | 4965 |
| wrf/module_physics_init.F | `fg_init` | 4700 | *(n/a)* | 4700 |

### ✅ `fortran` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:33:27Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/ctags correctly extract 677 args. Tree-sitter truncates at 39.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wrf/module_physics_init.F | `phy_init` | 677 | 39 | 677 |

## fsharp

### ❓ `fsharp` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 65 occurrences as of 2026-11-26T05:33:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fsharp/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| giraffe_web/Core.fs | `bindXml` | *(n/a)* | 356 | *(n/a)* |
| giraffe_web/Core.fs | `tryBindForm` | *(n/a)* | 393 | *(n/a)* |
| giraffe_web/Core.fs | `tryBindQuery` | *(n/a)* | 441 | *(n/a)* |
| giraffe_web/Core.fs | `json` | *(n/a)* | 532 | *(n/a)* |
| giraffe_web/Core.fs | `jsonChunked` | *(n/a)* | 543 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `convert` | *(n/a)* | 39 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `tryGetParser` | *(n/a)* | 77 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `decodeSlashes` | *(n/a)* | 78 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `parseGuid` | *(n/a)* | 81 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `convertToTuple` | *(n/a)* | 97 | *(n/a)* |

### ❓ `fsharp` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-11-26T05:33:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fsharp/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| giraffe_web/Auth.fs | `authorizeByPolicy` | 129 | *(n/a)* | *(n/a)* |
| giraffe_web/Core.fs | `htmlView` | 605 | *(n/a)* | *(n/a)* |
| giraffe_web/Negotiation.fs | `negotiate` | 177 | *(n/a)* | *(n/a)* |
| giraffe_web/Preconditional.fs | `validatePreconditions` | 209 | *(n/a)* | *(n/a)* |
| giraffe_web/ResponseCaching.fs | `publicResponseCaching` | 98 | *(n/a)* | *(n/a)* |
| giraffe_web/Routing.fs | `subRoutef` | 373 | *(n/a)* | *(n/a)* |

### ❓ `fsharp` class existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:33:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fsharp/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| giraffe_web/Json.fs | `ISerializer` | *(n/a)* | *(n/a)* | *(n/a)* |
| giraffe_web/Negotiation.fs | `INegotiationConfig` | *(n/a)* | *(n/a)* | *(n/a)* |
| giraffe_web/Negotiation.fs | `INegotiationConfig` | *(n/a)* | *(n/a)* | *(n/a)* |
| giraffe_web/Xml.fs | `Xml` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `fsharp` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 26 occurrences as of 2026-11-26T05:33:28Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`fsharp/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| giraffe_web/ComputationExpressions.fs | `Return` | 1 | 0 | *(n/a)* |
| giraffe_web/ComputationExpressions.fs | `Return` | 1 | 0 | *(n/a)* |
| giraffe_web/ComputationExpressions.fs | `ReturnFrom` | 1 | 0 | *(n/a)* |
| giraffe_web/Core.fs | `safeRedirectToExt` | 0 | 3 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `MapMultiEndpoint` | 0 | 2 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `MapNestedEndpoint` | 0 | 2 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `MapSingleEndpoint` | 0 | 2 | *(n/a)* |
| giraffe_web/EndpointRouting.fs | `subRouteWithExtensions` | 0 | 3 | *(n/a)* |
| giraffe_web/Json.fs | `SerializeToStreamAsync` | 2 | 1 | *(n/a)* |
| giraffe_web/ModelValidation.fs | `validateModel` | 3 | 2 | *(n/a)* |

## go

### ✅ `go` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 77 occurrences as of 2026-11-26T05:33:31Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/ctags correctly parse multiple arguments sharing a type. Tree-sitter groups them.

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

### ❓ `haskell` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 20 occurrences as of 2026-11-26T05:33:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aeson_core/src_Data_Aeson_Parser_Time.hs | `Parser` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `RowHead` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `RowBody` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `AnnM` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_DocBook.hs | `DB` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_DokuWiki.hs | `DokuWiki` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_Jira.hs | `JiraConverter` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_LaTeX_Table.hs | `BlocksWriter` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_Muse.hs | `Notes` | *(n/a)* | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_Muse.hs | `Muse` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `haskell` class existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:33:37Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`haskell/class/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| xmonad_core/src_XMonad_Core.hs | `LayoutClass` | *(n/a)* | 282 | *(n/a)* |

### ✅ `haskell` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 529 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude Sonnet 5 (dispatched agent investigation), 2026-08-19T00:00:00Z):
> All 10 sampled cases are ctags-side artifacts, not real GitGalaxy/tree-sitter misses -- confirmed via direct `ctags -x` output against the corpus. Three distinct ctags Haskell-parser weaknesses cover the sample: (1) multi-clause double/triple-tagging -- ctags tags every pattern-matched equation line as its own occurrence of the name (writerFn/writeFnBinary/expandFilterPath: confirmed 2-3 raw ctags tags per function, one per clause; a file-wide count found 45 such extra same-name tags across the 7-file corpus, e.g. blockToInlines alone has 14). GitGalaxy/tree-sitter both correctly anchor to the FIRST clause only, leaving ctags' later-clause tags as the ones unpaired. (2) keyword-as-identifier misparsing -- `class`/`where`/`pattern` (from PatternSynonyms) get tagged as function names when ctags fails to parse past the keyword; confirmed at Options.hs:62 (`class HasSyntaxExtensions`), Parsing.hs:184 (module-header `where`), and 3 PatternSynonyms declarations in Options.hs. (3) CAF/value-vs-function kind collapse -- defaultAbbrevs/defaultKaTeXURL/defaultMathJaxURL/defaultWebTeXURL are zero-arg top-level VALUES (non-arrow type signatures), not functions; ctags has no value/variable kind at all (`ctags --list-kinds-full=Haskell` shows only constructor/function/module/type) so it lumps every `name = expr` binding into "function". GitGalaxy (language_standards.py haskell rules, #1312) and tree-sitter's own audit tooling (_find_haskell_signature_for_bind, #1566) both independently make the same value-vs-function distinction correctly -- real cross-tool corroboration, not coincidence. (4) TH-splice call sites misread as definitions -- deriveJSON at Options.hs:454/458 is a Template Haskell splice INVOKING an imported function, not defining one; ctags misparses the call as a definition. No GitGalaxy/tree-sitter defect anywhere in this shape; purely a ctags parser limitation, same category as the already-documented empty CTAGS_CLASS_KINDS['haskell'].

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `bigRecord` | *(n/a)* | *(n/a)* | 29 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field01` | *(n/a)* | *(n/a)* | 11 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field02` | *(n/a)* | *(n/a)* | 11 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field03` | *(n/a)* | *(n/a)* | 11 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field04` | *(n/a)* | *(n/a)* | 11 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field05` | *(n/a)* | *(n/a)* | 11 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field06` | *(n/a)* | *(n/a)* | 12 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field07` | *(n/a)* | *(n/a)* | 12 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field08` | *(n/a)* | *(n/a)* | 12 |
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `field09` | *(n/a)* | *(n/a)* | 12 |

### ✅ `haskell` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 211 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude Sonnet 5 (dispatched agent investigation), 2026-08-19T00:00:00Z):
> Confirmed: all 10 sampled misses (and, by cross-check against additional non-sampled instances in Options.hs/Shared.hs, plausibly all 69) are locally-scoped function definitions -- `instance ... where` methods, `where`-clause helpers, or `let`-bound names inside `do` blocks -- never top-level module definitions. ctags' Haskell parser has no layout-rule/scope awareness and only tags equations anchored at column 1; it correctly handles multi-clause TOP-LEVEL definitions (verified via expandFilterPath, writeFnBinary, writerFn -- all tag fine, clauses and all), so this is a pure scope blind spot, not a clause-counting bug (distinct from the tree-sitter clause-splitting bug fixed earlier in this same effort, which shares 2 of the 10 sample names by coincidence of subject matter, not root cause). GitGalaxy and tree-sitter are both correct; ctags is not wrong so much as structurally incapable of seeing these. Known, expected limitation of ctags' Haskell parser, now documented alongside its existing Haskell notes in tests/tools/ctags_reader.py -- not a GitHub issue, nothing in this repo to fix.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `rnf` | 19 | 19 | *(n/a)* |
| aeson_core/benchmarks_bench_Compare_BufferBuilder.hs | `toJson` | 19 | 19 | *(n/a)* |
| aeson_core/benchmarks_bench_Compare_BufferBuilder.hs | `toJson` | 22 | 22 | *(n/a)* |
| aeson_core/benchmarks_bench_Compare_BufferBuilder.hs | `toJson` | 27 | 27 | *(n/a)* |
| aeson_core/benchmarks_bench_Compare_BufferBuilder.hs | `toJson` | 31 | 31 | *(n/a)* |
| aeson_core/benchmarks_bench_Compare_BufferBuilder.hs | `toJson` | 36 | 36 | *(n/a)* |
| aeson_core/benchmarks_bench_Compare_BufferBuilder.hs | `toJson` | 53 | 53 | *(n/a)* |
| aeson_core/benchmarks_bench_ReadFile.hs | `loop` | 26 | 26 | *(n/a)* |
| pandoc/App.hs | `ensureNl` | 329 | 329 | *(n/a)* |
| pandoc/App.hs | `makeSandboxed` | 165 | 165 | *(n/a)* |

### ✅ `haskell` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 60 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude Sonnet 5 (session investigation), 2026-08-19T00:00:00Z):
> Not a real discrepancy -- structural tooling gap, already documented in the codebase. tests/tools/ctags_reader.py:39-40,228 sets CTAGS_CLASS_KINDS['haskell'] = set() on purpose: "ctags' Haskell parser has no class-shaped kind at all (constructor/function/module/type only)". Every example in this shape (data/newtype/class declarations -- ReaderOptions, CiteMethod, HasSyntaxExtensions, etc.) is real; ctags structurally cannot report any of them for this language, not a sample-specific miss. No action needed beyond this note.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aeson_core/benchmarks_bench_Auto_G_BigRecord.hs | `BigRecord` | *(n/a)* | 10 | *(n/a)* |
| aeson_core/examples_src_Generic.hs | `Coord` | *(n/a)* | 19 | *(n/a)* |
| pandoc/App.hs | `PandocOutput` | *(n/a)* | 344 | *(n/a)* |
| pandoc/Filter.hs | `Filter` | *(n/a)* | 41 | *(n/a)* |
| pandoc/Options.hs | `HasSyntaxExtensions` | *(n/a)* | 62 | *(n/a)* |
| pandoc/Options.hs | `ReaderOptions` | *(n/a)* | 65 | *(n/a)* |
| pandoc/Options.hs | `EPUBVersion` | *(n/a)* | 107 | *(n/a)* |
| pandoc/Options.hs | `HTMLMathMethod` | *(n/a)* | 109 | *(n/a)* |
| pandoc/Options.hs | `CiteMethod` | *(n/a)* | 157 | *(n/a)* |
| pandoc/Options.hs | `ObfuscationMethod` | *(n/a)* | 177 | *(n/a)* |

### ✅ `haskell` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 48 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-26T00:00:00Z):
> Stale, superseded by extensive GitGalaxy Haskell hardening between this shape's original capture and today (closed issues #1312, #1435, #1442, #1532, #1564, #1565, #1614, #1615, #1616 all touch this exact case). A fresh gather of every sampled example (writerFn, writeFnBinary in App.hs; expandFilterPath in Filter.hs; tabFilter, compactify, camelCaseStrToHyphenated, blockToInlines in Shared.hs) shows GitGalaxy now correctly anchors to the function's TYPE SIGNATURE line, tree-sitter anchors to the first pattern-match equation, and ctags tags every equation clause separately (up to 14 tags for blockToInlines' many clauses). Rank-paired, slot 0 is now full 3-way agreement; the extra ctags clause-tags fall into the already-validated shape `haskell/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`, which already covers this exact multi-clause-tagging phenomenon.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aeson_core/tests_PropUtils.hs | `roundTripKey` | *(n/a)* | 124 | 124 |
| aeson_core/tests_PropUtils.hs | `toParseJSON1` | *(n/a)* | 73 | 73 |
| aeson_core/tests_PropUtils.hs | `sameAs1` | *(n/a)* | 177 | 177 |
| aeson_core/tests_PropUtils.hs | `sameAs1Agree` | *(n/a)* | 189 | 189 |
| pandoc/Shared.hs | `addPandocAttributes` | *(n/a)* | 301 | 301 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `annotateRowSection` | *(n/a)* | 222 | 222 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `toTable` | *(n/a)* | 133 | 133 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `annotateTable` | *(n/a)* | 153 | 153 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `splitCellHang` | *(n/a)* | 261 | 261 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `fromTable` | *(n/a)* | 280 | 280 |

### ✅ `haskell` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 11 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-29):
> Reconciler rank-pairing artifact from ctags-haskell's per-line tagging. All three tools FIND the function -- pandoc/Shared.hs's `addPandocAttributes`: GitGalaxy at line 299 (the bare name line of a multi-line definition), tree-sitter-haskell at line 301 (the first equation), each exactly once. ctags-haskell emits THREE `f` tags for it, at lines 300, 301 and 302 (the `::` type-signature line plus both `addPandocAttributes ... = ...` equation lines). tri_comparison_reconcile pairs same-named occurrences by rank: GitGalaxy's single occurrence rank-pairs with ctags' rank-1 tag (@300) and tree-sitter's single occurrence rank-pairs with ctags' rank-2 tag (@301), so the GitGalaxy+ctags slot is left with no tree-sitter partner and surfaces as `agree[ctags,gitgalaxy]_vs[tree_sitter]` for 1 occurrence. Not a tree-sitter recall gap and not a GitGalaxy defect -- purely ctags' surplus tags shifting the rank alignment. Documented in tests/tools/ctags_reader.py's haskell CTAGS_FUNC_KINDS comment. No credit/debit: ctags' extra tags are its own per-line behaviour, not a shared mistake with another tool, and neither GitGalaxy nor tree-sitter has a confirmed limitation here.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aeson_core/tests_PropUtils.hs | `roundTripKey` | 121 | *(n/a)* | 122 |
| aeson_core/tests_PropUtils.hs | `toParseJSON1` | 67 | *(n/a)* | 68 |
| aeson_core/tests_PropUtils.hs | `sameAs1` | 172 | *(n/a)* | 173 |
| aeson_core/tests_PropUtils.hs | `sameAs1Agree` | 183 | *(n/a)* | 184 |
| pandoc/Shared.hs | `addPandocAttributes` | 299 | *(n/a)* | 300 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `annotateRowSection` | 208 | *(n/a)* | 209 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `toTable` | 125 | *(n/a)* | 126 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `annotateTable` | 148 | *(n/a)* | 149 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `splitCellHang` | 256 | *(n/a)* | 257 |
| pandoc_writers/src_Text_Pandoc_Writers_AnnotatedTable.hs | `fromTable` | 271 | *(n/a)* | 272 |

### ✅ `haskell` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 11 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude Sonnet 5 (session investigation), 2026-08-19T00:00:00Z):
> Mixed shape as originally investigated (2 occurrences): (1) Options.hs:438 getExtensions -- real function, `instance HasSyntaxExtensions WriterOptions where getExtensions opts = writerExtensions opts`. A sibling instance for ReaderOptions at Options.hs:80 has the identical shape. Tree-sitter's Haskell grammar doesn't expose typeclass-instance-method clause bodies the way it does top-level bindings, and ctags' Haskell parser has no instance-method kind either -- GitGalaxy is correct, both other tools have a real recall gap on typeclass instance methods. (2) Shared.hs:475 extensionEnabled -- was NOT a real function (imported from Text.Pandoc.Extensions, only ever appears as a guard-clause call inside a multi-line `||` condition) -- a genuine GitGalaxy false positive, filed as #2082 and fixed in PR #2083 (2026-08-22): `_slice_by_indentation` now skips an equation-form func_start match whose immediately preceding line ends in `||`/`&&`. Reconciled post-fix: only the getExtensions occurrence remains, so this shape is now a clean, unambiguous GitGalaxy win -- credited accordingly.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc/Options.hs | `getExtensions` | 63 | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_Jira.hs | `mathInlines` | 294 | *(n/a)* | *(n/a)* |
| pandoc_writers/src_Text_Pandoc_Writers_LaTeX_Table.hs | `colCount` | 219 | *(n/a)* | *(n/a)* |
| xmonad_core/src_XMonad_Core.hs | `cmd1` | 795 | *(n/a)* | *(n/a)* |
| xmonad_core/src_XMonad_Core.hs | `Unknown_Block` | 794 | *(n/a)* | *(n/a)* |
| xmonad_core/src_XMonad_Core.hs | `maybe` | 537 | *(n/a)* | *(n/a)* |
| xmonad_core/src_XMonad_Core.hs | `libTs` | 681 | *(n/a)* | *(n/a)* |
| xmonad_core/src_XMonad_Main.hs | `traverse_` | 453 | *(n/a)* | *(n/a)* |
| xmonad_core/src_XMonad_Main.hs | `forever` | 254 | *(n/a)* | *(n/a)* |
| xmonad_core/src_XMonad_Operations.hs | `pure` | 472 | *(n/a)* | *(n/a)* |

### ✅ `haskell` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-26T00:00:00Z):
> Stale, fully resolved by the same haskell-hardening wave as the sibling shape above. A fresh gather of every sampled example (isPandocCiteproc in App.hs; applyFilter and toJSON in Filter.hs; nine toJSON instance methods in Options.hs) shows GitGalaxy now matches tree-sitter exactly, occurrence-for-occurrence and line-for-line (e.g. Options.hs toJSON: both tools find the identical 9-line set), with only ctags missing all of them -- precisely the already-validated shape `haskell/function/existence/agree[gitgalaxy,tree_sitter]_vs[ctags]` ('locally-scoped function definitions... instance ... where methods... ctags' Haskell parser has no layout-rule/scope awareness... pure scope blind spot'). None of this shape's original examples still show GitGalaxy missing anything tree-sitter finds.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| pandoc_writers/src_Text_Pandoc_Writers_Muse.hs | `f'` | *(n/a)* | 360 | *(n/a)* |
| xmonad_core/src_XMonad_Core.hs | `show` | *(n/a)* | 355 | *(n/a)* |
| xmonad_core/src_XMonad_Main.hs | `padToLen` | *(n/a)* | 191 | *(n/a)* |
| xmonad_core/src_XMonad_Operations.hs | `least` | *(n/a)* | 332 | *(n/a)* |

### ✅ `haskell` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 21 occurrences as of 2026-11-26T05:33:37Z*

**Verdict** (by Claude Sonnet 5 (session investigation), 2026-08-19T00:00:00Z):
> One systematic cause, confirmed by reading source for 3 of the 9 (getMetadataFromFiles App.hs:395-397, splitTextByIndices Shared.hs:142-143, tabFilter Shared.hs:256-259) and consistent with the shape of the remaining 6. Every case is a point-free/eta-reduced Haskell equation: the type signature declares N params, but the specific clause GitGalaxy and tree-sitter both align to only explicitly binds N-1 of them, handling the trailing argument via composition (`.`) or `\case`. GitGalaxy counts arity from the full type signature (the true logical arity); tree-sitter's declaration-only reading counts only the clause's explicitly-bound patterns (correct for that one equation, but undercounts true arity). Neither reader is wrong about what it's measuring -- same shape as Claim 1 in docs/why_gitgalaxy_beats_ast_here.md. GitGalaxy's answer is arguably the more useful coupling signal; recommend documenting as a candidate Claim rather than treating as an engine defect to fix toward matching tree-sitter.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| aeson_core/src_Data_Aeson_Internal_ByteString-2.hs | `unsafePackLenLiteral` | 1 | 2 | *(n/a)* |
| aeson_core/src_Data_Aeson_Internal_ByteString.hs | `unsafePackLenLiteral` | 1 | 2 | *(n/a)* |
| pandoc/App.hs | `getMetadataFromFiles` | 3 | 2 | *(n/a)* |
| pandoc/App.hs | `writerFn` | 3 | 2 | *(n/a)* |
| pandoc/App.hs | `writeFnBinary` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `textToIdentifier` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `inlineListToIdentifier` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `formatCode` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `tabFilter` | 2 | 1 | *(n/a)* |
| pandoc/Shared.hs | `splitTextByIndices` | 2 | 1 | *(n/a)* |

## html

### ✅ `html` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 37 occurrences as of 2026-11-26T05:33:41Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-29):
> GitGalaxy correct, corroborated by tree-sitter, ctags structurally cannot see it. cpython_jinja/layout.html:40 `@media only screen { ... }` inside a `<style>` block is a real CSS at-rule. GitGalaxy's polyglot detector reports it as a function `media`; tri_comparison_gatherer.py's tree-sitter walk now injects the css grammar for `<style>`/`<script>` elements (#2452, mirroring #2421 in the accuracy audit) and agrees. ctags-html has no CSS parser at all, so it emits nothing -- a documented ctags-html limitation (tests/tools/ctags_reader.py's html CTAGS_FUNC_KINDS comment), not a GitGalaxy or tree-sitter defect. This shape is the post-#2452 successor to `agree[gitgalaxy]_vs[ctags,tree_sitter]` (now non-reproducing): GitGalaxy's claim moved from uncorroborated to tree-sitter-corroborated. No credit/debit -- a real 2-tool consensus, and ctags' absence is a known structural gap, not a shared mistake.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cesium_sandcastle/gallery_cylinders_and_cones.html | `startup` | 29 | 29 | *(n/a)* |
| cpython_jinja/layout.html | `media` | 40 | 40 | *(n/a)* |
| html5_boilerplate/dist_404.html | `media` | 40 | 40 | *(n/a)* |
| html5_boilerplate/src_404.html | `media` | 40 | 40 | *(n/a)* |
| jquery_test_fixtures/trusted-html.html | `runTests` | 22 | 22 | *(n/a)* |
| jquery_test_fixtures/trusted-html.html | `createHTML` | 48 | 48 | *(n/a)* |
| jquery_test_fixtures/trusted-html.html | `wrapInTrustedHtml` | 53 | 53 | *(n/a)* |
| jquery_test_fixtures/trusted-html.html | `toString` | 65 | 65 | *(n/a)* |
| playwright_dom_fixtures/dynamic-oopif.html | `goRemote` | 18 | 18 | *(n/a)* |
| playwright_dom_fixtures/dynamic-oopif.html | `goLocal` | 14 | 14 | *(n/a)* |

## javascript

### ✅ `javascript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 277 occurrences as of 2026-11-26T05:33:47Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed ctags-side parser limitation, not a GitGalaxy or tree-sitter defect. ctags' JavaScript scanner loses the real property-key name for a function-valued object-literal property specifically when that literal is a CALL ARGUMENT rather than a direct assignment -- confirmed via jquery/ajax.js's `jQuery.extend(jQuery, {ajaxSetup: function(target, settings){...}, ajax: function(url, options){...}})`: ctags emits a synthetic 'AnonymousFunction<hex>' tag for both instead of using the real 'ajaxSetup'/'ajax' key text, while GitGalaxy and tree-sitter both correctly attribute the property key as the name. Generalizes across the whole corpus, not a one-file fluke -- the identical shape recurs in jquery/css.js (css/get/set/style), jquery/deferred.js (Deferred/catch/pipe/promise/then/when), jquery/event.js (Event/handler/off/one/postDispatch/set), jquery/core.js (20+ utility methods, reducing ctags' whole-file function count from 26 to 1), and threejs's Editor.js/GLTFLoader.js/WebGLRenderer.js/WebGLProgram.js. Doc note added to ctags_reader.py's javascript CTAGS_FUNC_KINDS entry.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cesium_particle_emitters/CircleEmitter.js | `CircleEmitter` | 14 | 14 | *(n/a)* |
| cesium_particle_emitters/CircleEmitter.js | `set` | 35 | 35 | *(n/a)* |
| cesium_particle_emitters/CircleEmitter.js | `get` | 32 | 32 | *(n/a)* |
| jquery/ajax.js | `ajax` | 383 | 383 | *(n/a)* |
| jquery/ajax.js | `ajaxSetup` | 369 | 369 | *(n/a)* |
| jquery/ajax.js | `getJSON` | 848 | 848 | *(n/a)* |
| jquery/ajax.js | `getScript` | 852 | 852 | *(n/a)* |
| jquery/core.js | `extend` | 115 | 115 | *(n/a)* |
| jquery/core.js | `map` | 74 | 74 | *(n/a)* |
| jquery/core.js | `map` | 370 | 370 | *(n/a)* |

### ✅ `javascript` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 189 occurrences as of 2026-11-26T05:33:47Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed GitGalaxy correct; both ctags and tree-sitter structurally can't, for two INDEPENDENT reasons. All four affected react/*.js corpus files carry the `@flow` pragma. tree-sitter-javascript's grammar can't parse Flow's parenthesized type-cast syntax (`(expr: Type)`, e.g. `(workInProgress.child: any)`), producing an ERROR node that swallows a large trailing region of the file -- confirmed directly: ReactFiberBeginWork.js's ERROR spans lines 3221-4448 (1227 of 4448 lines), and ReactFiberWorkLoop.js/ReactFlightServer.js each produce ONE error node spanning the ENTIRE file (line 1 to EOF). Real, ordinary functions inside these regions (beginWork, attemptEarlyBailoutIfNoScheduledUpdate, mountLazyComponent, and 18 others sampled) have no tree-sitter node at all. Separately, ctags' own hand-written JS scanner hits an independent cascade triggered by a Flow RETURN-type annotation (`): Fiber | null {`) -- confirmed via a minimal isolated repro (a 4-function test file where the function with a Flow return-type annotation and everything textually after it produce zero ctags output), and confirmed against the real corpus (beginWork itself, which has exactly this return-type shape, produces zero ctags tags). GitGalaxy's regex has no dependency on either tool's parse state and finds every one of these correctly. Documented in docs/why_gitgalaxy_beats_ast_here.md (Claim 3, new subsection completing/extending the existing 'Second instance: javascript' write-up with the recall-loss half plus the newly-confirmed ctags cascade).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `jQuery[ method ]` | 858 | *(n/a)* | *(n/a)* |
| jquery/ajax.js | `converters[               ]` | 764 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `beginWork` | 4164 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `attemptEarlyBailoutIfNoScheduledUpdate` | 3896 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `mountLazyComponent` | 2079 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `updateViewTransition` | 3569 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `validateRevealOrder` | 3242 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `remountFiber` | 3806 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `validateTailOptions` | 3298 | *(n/a)* | *(n/a)* |
| react/ReactFiberBeginWork.js | `updateHostComponent` | 1933 | *(n/a)* | *(n/a)* |

### ✅ `javascript` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 99 occurrences as of 2026-11-26T05:33:47Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed ctags-side parser limitation, not a GitGalaxy or tree-sitter defect. ctags' JavaScript scanner tags its 'class' kind on ANY bare object-literal assignment (`var X = {...}`) or function-expression assignment (`var X = function(){}`, `obj.prop = function(){}`), a blanket heuristic for 'might be used as a pre-ES6 constructor' that fires regardless of whether `new` is ever used on it. Confirmed via a minimal isolated repro (plainObj/ctorLike/obj.Thing all tagged 'class' alongside a real ES6 class) and directly against the corpus: jqXHR (jquery/ajax.js, a plain config object), cssHooks/cssNormalTransform/cssShow (jquery/css.js), promise (jquery/deferred.js), Event/event/special (jquery/event.js, one of which -- Event -- IS a pre-ES6 constructor-style function, correctly ambiguous under ctags' heuristic but still not a real ES6 class), and the ALPHA_MODES/WEBGL_CONSTANTS/etc. config objects in threejs/GLTFLoader.js. GitGalaxy's class_start regex and tree-sitter's class_declaration node both correctly require the literal `class` keyword. Doc note added to ctags_reader.py's javascript CTAGS_CLASS_KINDS entry.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cesium_particle_emitters/CircleEmitter.js | `CircleEmitter` | *(n/a)* | *(n/a)* | 14 |
| jquery/ajax.js | `jqXHR` | *(n/a)* | *(n/a)* | 448 |
| jquery/css.js | `cssHooks` | *(n/a)* | *(n/a)* | 357 |
| jquery/css.js | `cssNormalTransform` | *(n/a)* | *(n/a)* | 22 |
| jquery/css.js | `cssShow` | *(n/a)* | *(n/a)* | 21 |
| jquery/deferred.js | `promise` | *(n/a)* | *(n/a)* | 58 |
| jquery/event.js | `Event` | *(n/a)* | *(n/a)* | 617 |
| jquery/event.js | `event` | *(n/a)* | *(n/a)* | 89 |
| jquery/event.js | `special` | *(n/a)* | *(n/a)* | 756 |
| jquery/event.js | `special` | *(n/a)* | *(n/a)* | 812 |

### ✅ `javascript` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 13 occurrences as of 2026-11-26T05:33:47Z*

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
| react/ReactFlightServer.js | `[Symbol.iterator]` | 1576 | *(n/a)* | 1576 |
| react/ReactFlightServer.js | `[ASYNC_ITERATOR]` | 1616 | *(n/a)* | 1616 |
| react/ReactFlightServer.js | `abortIterable` | 1367 | *(n/a)* | 1367 |
| react/ReactFlightServer.js | `abortStream` | 1233 | *(n/a)* | 1233 |

### ✅ `javascript` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:33:47Z*

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

### ✅ `javascript` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-11-26T05:33:47Z*

**Verdict** (by Claude (Sonnet 5), dispatched via tri-comparison-ledger-sweep, 2026-08-21):
> Confirmed ctags-side synthetic-placeholder artifact, not a real discrepancy -- ctags' JavaScript scanner emits a synthetic 'AnonymousFunction<hex><seq>' tag for every genuinely anonymous function expression (a bare inline callback with no attributable name, e.g. `jQuery.ajaxPrefilter(function(s) {...})`), and GitGalaxy/tree-sitter both correctly agree these aren't named functions worth counting. Fixed by extending `tri_comparison_gatherer.py`'s existing `_is_ctags_synthetic_anon_name` (previously only matched the C-parser's `__anon<hex>` scheme) with a second regex for JavaScript's differently-shaped 'AnonymousFunction'/'AnonymousClass' scheme -- verified this removes every 'Anonymous*' entry across the full 18-file corpus with zero regressions (ruff/mypy audits clean).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| jquery/ajax.js | `converters` | *(n/a)* | *(n/a)* | 764 |
| jquery/ajax.js | `jQuery` | *(n/a)* | *(n/a)* | 858 |
| jquery/deferred.js | `deferred` | *(n/a)* | *(n/a)* | 319 |
| threejs/GLTFLoader.js | `copy` | *(n/a)* | *(n/a)* | 3457 |
| threejs/GLTFLoader.js | `copy` | *(n/a)* | *(n/a)* | 3477 |
| threejs/GLTFLoader.js | `createInterpolant` | *(n/a)* | *(n/a)* | 4643 |

## julia

### ❓ `julia` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 114 occurrences as of 2026-11-26T05:33:51Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`julia/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dataframes_jl/abstractdataframe_io.jl | `show` | *(n/a)* | 603 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `show` | *(n/a)* | 606 | *(n/a)* |
| dataframes_jl/abstractdataframe_iteration.jl | `reduce` | *(n/a)* | 752 | *(n/a)* |
| dataframes_jl/abstractdataframe_iteration.jl | `show` | *(n/a)* | 354 | *(n/a)* |
| dataframes_jl/abstractdataframe_iteration.jl | `show` | *(n/a)* | 365 | *(n/a)* |
| dataframes_jl/abstractdataframe_iteration.jl | `show` | *(n/a)* | 391 | *(n/a)* |
| dataframes_jl/abstractdataframe_iteration.jl | `show` | *(n/a)* | 402 | *(n/a)* |
| dataframes_jl/abstractdataframe_iteration.jl | `Base` | *(n/a)* | 271 | *(n/a)* |
| dataframes_jl/abstractdataframe_selectionfast.jl | `table_transformation` | *(n/a)* | 150 | *(n/a)* |
| dataframes_jl/abstractdataframe_selectionfast.jl | `table_transformation` | *(n/a)* | 255 | *(n/a)* |

### ❓ `julia` class existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 24 occurrences as of 2026-11-26T05:33:51Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`julia/class/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dataframes_jl/abstractdataframe_iteration.jl | `DataFrameRows` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/abstractdataframe_iteration.jl | `DataFrameColumns` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/abstractdataframe_reshape.jl | `StackedVector` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/abstractdataframe_reshape.jl | `RepeatedVector` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/abstractdataframe_sort.jl | `UserColOrdering` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/abstractdataframe_sort.jl | `DFPerm` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/dataframerow_dataframerow.jl | `DataFrameRow` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/groupeddataframe_callprocessing.jl | `FirstMultiCol` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/groupeddataframe_callprocessing.jl | `FirstSingleCol` | *(n/a)* | *(n/a)* | *(n/a)* |
| dataframes_jl/groupeddataframe_fastaggregates.jl | `Reduce` | *(n/a)* | *(n/a)* | *(n/a)* |

### ❓ `julia` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 5 occurrences as of 2026-11-26T05:33:51Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`julia/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dataframes_jl/abstractdataframe_show.jl | `Anonymous_Block_[Truncated]` | 147 | *(n/a)* | *(n/a)* |
| dataframes_jl/dataframe_dataframe.jl | `_deleteat!` | 899 | *(n/a)* | *(n/a)* |
| dataframes_jl/groupeddataframe_fastaggregates.jl | `groupreduce!` | 152 | *(n/a)* | *(n/a)* |
| dataframes_jl/groupeddataframe_show.jl | `show_[Truncated]` | 9 | *(n/a)* | *(n/a)* |
| dataframes_jl/groupeddataframe_utils.jl | `row_group_slots!_[Truncated]` | 283 | *(n/a)* | *(n/a)* |

### ❓ `julia` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 584 occurrences as of 2026-11-26T05:33:51Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`julia/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dataframes_jl/abstractdataframe_io.jl | `_show` | 3 | 12 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `_show` | 3 | 13 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `_show` | 4 | 5 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `printtable` | 6 | 7 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `_verify_kwargs_for_html` | 2 | 1 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `show` | 6 | 7 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `show` | 0 | 4 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `show` | 0 | 3 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `show` | 0 | 3 | *(n/a)* |
| dataframes_jl/abstractdataframe_io.jl | `show` | 0 | 4 | *(n/a)* |

## kotlin

### ❓ `kotlin` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 51 occurrences as of 2026-11-26T05:33:54Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`kotlin/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| spring_boot_kotlin/core_spring-boot-test_src_test_kotlin_org_springframework_boot_test_context_SpringBootContextLoaderKotlinTests.kt | ``when UseMainMethod ALWAYS and main method throws exception`` | *(n/a)* | 30 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | ``Kotlin runApplication() top level function`` | *(n/a)* | 35 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | ``Kotlin runApplication() top level function with a custom environment`` | *(n/a)* | 41 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | ``Kotlin runApplication(arg1, arg2) top level function`` | *(n/a)* | 51 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | ``Kotlin runApplication(arg1, arg2) top level function with a custom environment`` | *(n/a)* | 59 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | ``Kotlin fromApplication() top level function`` | *(n/a)* | 71 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | ``Kotlin fromApplication() top level function with multiple sources`` | *(n/a)* | 77 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | ``Kotlin fromApplication() top level function when no main`` | *(n/a)* | 85 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_KotlinConfigurationPropertiesBeanRegistrarTests.kt | ``type with primary constructor and no autowired should register value object configuration properties`` | *(n/a)* | 36 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_KotlinConfigurationPropertiesBeanRegistrarTests.kt | ``type with no primary constructor should register java bean configuration properties`` | *(n/a)* | 45 | *(n/a)* |

### ❓ `kotlin` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 15 occurrences as of 2026-11-26T05:33:54Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`kotlin/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `DeleteUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `GetUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `HeadUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `HttpUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `OptionsUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `PatchUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `PostUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `PutUser` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `Service` | *(n/a)* | *(n/a)* | *(n/a)* |
| retrofit_kotlin/retrofit-response-type-keeper_src_test_kotlin_retrofit2_keeper_RetrofitResponseTypeKeepProcessorTest.kt | `Service` | *(n/a)* | *(n/a)* | *(n/a)* |

### ✅ `kotlin` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 217 occurrences as of 2026-11-26T05:33:54Z*

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

### ✅ `kotlin` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 51 occurrences as of 2026-11-26T05:33:54Z*

**Verdict** (by claude-sonnet-5, dispatched via tri-comparison-ledger-sweep (direct investigation, no Gemini dispatch -- small occurrence counts, answer was directly checkable), 2026-08-22T11:40:48Z):
> Confirmed real tree_sitter_accuracy_audit.py NODE_MAPS gap, same shape as swift's init_declaration/dart's constructor-node precedents. Line 119 of okhttp/Dispatcher.kt is `constructor(executorService: ExecutorService?) : this() { ... }` -- a genuine Kotlin secondary constructor. GitGalaxy's own func_start regex already correctly matches it (its dedicated `(constructor)` alternative). Direct tree-sitter-kotlin parse confirms this construct gets its own `secondary_constructor` node type, distinct from `function_declaration` -- absent from kotlin's func_node_types pre-fix, so tree-sitter's real_functions silently excluded every secondary constructor. Fixed by adding 'secondary_constructor' (and, proactively, 'anonymous_initializer' for `init { }` blocks -- same no-name-field shape, same regex's `(init)` sibling alternative, no live occurrence in this corpus but same underlying gap) to func_node_types, plus a _get_node_name branch returning the literal 'constructor'/'init' keyword text (there is no other name to capture -- Kotlin gives secondary constructors and init blocks no user-chosen identifier), plus a _get_param_count branch reusing function_declaration's existing function_value_parameters-wrapper logic for secondary_constructor. Verified post-fix: tree-sitter's real_functions for Dispatcher.kt now includes 'constructor', matching GitGalaxy. Separately confirmed ctags' own Kotlin parser does NOT recognize secondary constructors at all -- `ctags -x --languages=Kotlin` on this file emits no entry for line 119 whatsoever, not even under a different kind -- a genuine ctags parser limitation, not a kind-mapping gap (nothing to remap; ctags never sees it as a symbol in the first place). No credit/debit on this exact shape: post-fix, tree-sitter now agrees with gitgalaxy, so this specific agree[gitgalaxy]_vs[ctags,tree_sitter] grouping stops reproducing; the residual gitgalaxy+tree_sitter-vs-ctags gap (a real, confirmed ctags parser limitation) will surface as its own shape on the next reconcile and gets its own verdict then.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| spring_boot_kotlin/core_spring-boot-test_src_test_kotlin_org_springframework_boot_test_context_SpringBootContextLoaderKotlinTests.kt | `fun` | 30 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | `fun` | 35 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | `fun` | 41 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | `fun` | 51 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | `fun` | 59 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | `fun` | 71 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | `fun` | 77 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_SpringApplicationExtensionsTests.kt | `fun` | 85 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_KotlinConfigurationPropertiesBeanRegistrarTests.kt | `fun` | 36 | *(n/a)* | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_KotlinConfigurationPropertiesBeanRegistrarTests.kt | `fun` | 45 | *(n/a)* | *(n/a)* |

### ✅ `kotlin` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 22 occurrences as of 2026-11-26T05:33:54Z*

**Verdict** (by claude-sonnet-5, dispatched via tri-comparison-ledger-sweep (direct investigation, no Gemini dispatch), 2026-08-22T11:45:48Z):
> Direct continuation of the already-investigated constructor shape (see the now-still_reproduces=False agree[gitgalaxy]_vs[ctags,tree_sitter] entry's verdict for the full investigation): fixing tree_sitter_accuracy_audit.py's kotlin func_node_types to include `secondary_constructor` made tree-sitter agree with GitGalaxy on okhttp/Dispatcher.kt line 119's `constructor(executorService: ExecutorService?) : this() { ... }`, which regrouped this exact occurrence into a NEW 2-vs-1 shape. ctags' own Kotlin parser was independently confirmed (via `ctags -x --languages=Kotlin`) to emit no entry at all for line 119, under any kind -- a genuine ctags parser limitation (it doesn't recognize secondary-constructor syntax as a symbol in the first place), not a ctags_reader.py kind-mapping gap (there is nothing to remap; ctags never sees this construct as a taggable symbol). No credit/debit: ctags never claimed this occurrence at all (a miss, not a wrong claim), so there is nothing in its matched_consensus to debit, and gitgalaxy/tree_sitter's own claims were already correctly counted independent of this adjustment mechanism.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| okhttp/Dispatcher.kt | `constructor` | 119 | 119 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_KotlinConfigurationPropertiesBeanRegistrarTests.kt | `constructor` | 63 | 63 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_KotlinConfigurationPropertiesBeanRegistrarTests.kt | `constructor` | 65 | 65 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_bind_KotlinConstructorParametersBinderTests.kt | `constructor` | 239 | 239 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_bind_KotlinConstructorParametersBinderTests.kt | `constructor` | 244 | 244 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_bind_KotlinConstructorParametersBinderTests.kt | `constructor` | 246 | 246 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_bind_KotlinDefaultBindConstructorProviderTests.kt | `constructor` | 152 | 152 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_bind_KotlinDefaultBindConstructorProviderTests.kt | `constructor` | 158 | 158 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_bind_KotlinDefaultBindConstructorProviderTests.kt | `constructor` | 165 | 165 | *(n/a)* |
| spring_boot_kotlin/core_spring-boot_src_test_kotlin_org_springframework_boot_context_properties_bind_KotlinDefaultBindConstructorProviderTests.kt | `constructor` | 170 | 170 | *(n/a)* |

## lua

### ✅ `lua` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 487 occurrences as of 2026-11-26T05:34:00Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-29):
> ctags-lua over-detection, GitGalaxy and tree-sitter-lua both correct. Universal Ctags' Lua parser tags the LHS name of every statement whose right-hand side contains the token `function`, without checking that the function is the whole RHS or even real code. Categorised across the full corpus (1095 ctags tags total): 617 real `function name()` / `local function name()` declarations (in consensus), then ~442 that only ctags claims -- ~136 anonymous callbacks passed as a call argument (`res,msg = pcall(function() ... end)` -> ctags tags `res`; `f = coroutine.wrap(function() ... end)`; `xpcall(loop, function(m) ...)`), ~210 `name = function(...)` / `local a = function(x)` / `a[i] = function()` anonymous-assignment forms, ~84 table-constructor / metamethod fields (`{set = function(x) ... end}`, `getmetatable(env).__index = function() end`, `__add`/`__unm`/`__eq` in a metatable literal), ~29 the literal token `function` INSIDE a string (`assert(doit("function a (, ...) end"))`, `type(x) == "function"`), and ~19 the word `function` inside a COMMENT (`local t = debug.getinfo(1) -- get function information`). tree-sitter-lua (a real grammar) names only `function_declaration` nodes and GitGalaxy's `func_start` regex only anchors on `^ (local )? (export )? function <name> (`; the `name = function` / metamethod / string / comment forms are all deliberately out of both readers' scope. Generalises to the full count -- every sampled case fits one of the six categories above, zero genuine GitGalaxy/tree-sitter misses in the set. Documented in tests/tools/ctags_reader.py's lua section.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cosmopolitan/all.lua | `Cstacklevel` | *(n/a)* | *(n/a)* | 114 |
| cosmopolitan/all.lua | `Cstacklevel` | *(n/a)* | *(n/a)* | 129 |
| cosmopolitan/all.lua | `dofile` | *(n/a)* | *(n/a)* | 143 |
| cosmopolitan/all.lua | `showmem` | *(n/a)* | *(n/a)* | 108 |
| cosmopolitan/all.lua | `showmem` | *(n/a)* | *(n/a)* | 116 |
| cosmopolitan/api.lua | `foo` | *(n/a)* | *(n/a)* | 1336 |
| cosmopolitan/api.lua | `foo` | *(n/a)* | *(n/a)* | 1457 |
| cosmopolitan/api.lua | `f` | *(n/a)* | *(n/a)* | 422 |
| cosmopolitan/api.lua | `F` | *(n/a)* | *(n/a)* | 804 |
| cosmopolitan/api.lua | `"XX` | *(n/a)* | *(n/a)* | 491 |

### ✅ `lua` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 22 occurrences as of 2026-11-26T05:34:00Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-29):
> Universal Ctags misses a handful of real functions GitGalaxy and tree-sitter-lua both find and agree on -- method-style declaration heads (`db.lua:a:f` = `function a:f()`) and, after this pass's `function_opener` fix, several nested `local function` closures now in GitGalaxy+tree-sitter consensus that ctags' single-pass scanner does not reach (`closure.lua:v`, `closure.lua:c`). GitGalaxy's claim is corroborated by tree-sitter (a real grammar), so its precision is unaffected; the gap is ctags'. Documented in tests/tools/ctags_reader.py's lua section. 2026-08-29 follow-up (PR for #2438/#2439/#2440): #2438 (one-liner `function f(...) ... end` declarations, net keyword change <= 0, were filed as global dust and never became their own FunctionNode -- fixed by extending the `function_opener` pass to top-level self-closing declarations, lua-scoped) and #2440 (polyglot segmentation carved a `<style>`/`<script>` out of a `Write([[ ... ]])` HTML heredoc, splitting the enclosing lua function -- fixed by masking lua long-bracket literals in `_partition_segments`' trigger scan) both landed. tree-sitter-accuracy found_functions 557 -> 618, extra_functions 7 -> 1, extra_classes 14 -> 1, args_exact_match 516 -> 572; lua recall 89.8% -> 99.7%, precision 98.8% -> 99.8%. Both golden masters re-blessed, baseline regenerated. This shape 6 -> 21: #2438's one-liner + nested recovery brought many more real method-style / nested `local function` declarations into GitGalaxy+tree-sitter consensus that Universal Ctags' single-pass scanner does not reach. GitGalaxy's precision is unaffected (corroborated by a real grammar); the gap is ctags'.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cosmopolitan/calls.lua | `foo` | 126 | 126 | *(n/a)* |
| cosmopolitan/calls.lua | `foo` | 143 | 143 | *(n/a)* |
| cosmopolitan/calls.lua | `f` | 67 | 67 | *(n/a)* |
| cosmopolitan/calls.lua | `a.b.c:f2` | 60 | 60 | *(n/a)* |
| cosmopolitan/calls.lua | `a:add` | 53 | 53 | *(n/a)* |
| cosmopolitan/closure.lua | `v` | 224 | 224 | *(n/a)* |
| cosmopolitan/closure.lua | `c` | 223 | 223 | *(n/a)* |
| cosmopolitan/constructs.lua | `f` | 105 | 105 | *(n/a)* |
| cosmopolitan/coroutine.lua | `f` | 310 | 310 | *(n/a)* |
| cosmopolitan/coroutine.lua | `f` | 404 | 404 | *(n/a)* |

### ✅ `lua` class existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:00Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-29):
> Lua has NO class syntax -- tree-sitter-lua has no class-shaped node type and Universal Ctags' Lua kind table has no class kind (`ctags_reader.py`'s lua CTAGS_CLASS_KINDS is the empty set), so both structurally report 0 lua classes on every file, forever. GitGalaxy's `class_start` is a deliberate best-effort heuristic for the Lua proto-table OOP idiom (`Account = {}; Account.__index = Account; function Account.new() ...`): `^ (local )? (export )? (type )? [A-Z]\w* (?= = {)`, i.e. a Capitalised name assigned a table literal. Of the 14 it flags, some are real entity-shaped tables (`pandoc/extensions.lua`'s `Extensions` module table) but several are plain Capitalised DATA tables -- `redis/life.lua`'s `FISH` / `EXPLODE` / `BUTTERFLY` are Conway's-Game-of-Life cell patterns, `AA` / `K` / `A` / `U` are one/two-letter test fixtures. Same category as css/html classes (`_CLASS_EXTRACTION_OUT_OF_SCOPE` in tree_sitter_accuracy_audit.py): a signal GitGalaxy emits by heuristic for cross-language schema comparability, with no ground-truth tool able to corroborate or refute it. The heuristic's looseness (catches ALL_CAPS data tables) is worth tightening -- routed to #2439 -- but the tree-sitter/ctags 0 is a structural absence, not a refutation. 2026-08-29 follow-up (PR for #2438/#2439/#2440): #2438 (one-liner `function f(...) ... end` declarations, net keyword change <= 0, were filed as global dust and never became their own FunctionNode -- fixed by extending the `function_opener` pass to top-level self-closing declarations, lua-scoped) and #2440 (polyglot segmentation carved a `<style>`/`<script>` out of a `Write([[ ... ]])` HTML heredoc, splitting the enclosing lua function -- fixed by masking lua long-bracket literals in `_partition_segments`' trigger scan) both landed. tree-sitter-accuracy found_functions 557 -> 618, extra_functions 7 -> 1, extra_classes 14 -> 1, args_exact_match 516 -> 572; lua recall 89.8% -> 99.7%, precision 98.8% -> 99.8%. Both golden masters re-blessed, baseline regenerated. #2439 added a proto-table 'tell' gate to lua's `class_start` heuristic (keep a `Name = {` match only when `function Name[.:]`, `Name.__index`, `setmetatable(..., Name)`, or `Name[.:]new` appears within a bounded window). 14 -> 1: only `tracegc.lua:M` survives -- a real module table with `function M.start` / `function M.stop` / `return M`, legitimately class-like. The `---@class` (explicit LuaLS annotation) branch is never gated. The remaining 0.0% class-precision cell is the unavoidable 'no ground-truth tool for lua classes' artifact, not a refutation of that one hit.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cosmopolitan/tracegc.lua | `M` | *(n/a)* | *(n/a)* | *(n/a)* |

### ✅ `lua` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 42 occurrences as of 2026-11-26T05:34:00Z*

**Verdict** (by Claude Sonnet 5, dispatched via tri-comparison-ledger-sweep, 2026-08-29):
> ctags-lua emits no `signature:` field at all (confirmed: `ctags --fields=+S --languages=Lua` on a real corpus file returns just the `f` kind, no signature), so it structurally cannot participate in a per-function argument-count comparison for Lua -- the `agree[none]` side is ctags being absent, not ctags disagreeing. GitGalaxy and tree-sitter-lua both derive the count from the real parenthesised `function name(a, b, ...)` parameter list and agree on it. This is real 2-tool corroboration of a `per_function` args metric (Lua has a conventional parameter list, unlike the `none`-granularity document-structural languages), not a discrepancy to resolve. Documented in tests/tools/ctags_reader.py's lua section (no signature-field support).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cosmopolitan/api.lua | `checkerr` | 3 | 2 | *(n/a)* |
| cosmopolitan/api.lua | `check3` | 2 | 1 | *(n/a)* |
| cosmopolitan/attrib.lua | `import` | 1 | 0 | *(n/a)* |
| cosmopolitan/bitwise.lua | `bit.band` | 4 | 3 | *(n/a)* |
| cosmopolitan/bitwise.lua | `bit.bor` | 4 | 3 | *(n/a)* |
| cosmopolitan/bitwise.lua | `bit.bxor` | 4 | 3 | *(n/a)* |
| cosmopolitan/bitwise.lua | `bit.btest` | 1 | 0 | *(n/a)* |
| cosmopolitan/calls.lua | `foo1` | 1 | 0 | *(n/a)* |
| cosmopolitan/code.lua | `checkR` | 4 | 3 | *(n/a)* |
| cosmopolitan/code.lua | `check` | 2 | 1 | *(n/a)* |

## m4

### ✅ `m4` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 98 occurrences as of 2026-11-26T05:34:02Z*

**Verdict** (by Antigravity (direct source read), 2026-08-24T03:52:19Z):
> GitGalaxy is correct to ignore these. Ctags incorrectly extracts AC_DEFINE and AC_DEFINE_UNQUOTED macro invocations as if they were macro definitions.

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

*2-vs-1 -- 86 occurrences as of 2026-11-26T05:34:02Z*

**Verdict** (by Antigravity (direct source read), 2026-08-24T03:52:19Z):
> GitGalaxy correctly extracts AC_DEFUN macro definitions. Ctags completely misses these.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| curl/m4/curl-confopts.m4 | `CURL_CHECK_NONBLOCKING_SOCKET` | 334 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_OPTIMIZE` | 142 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_WARNINGS` | 270 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_THREADED_RESOLVER` | 34 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_ARES` | 75 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_DEBUG` | 110 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_SYMBOL_HIDING` | 198 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_RT` | 238 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CHECK_OPTION_WERROR` | 304 | *(n/a)* | *(n/a)* |
| curl/m4/curl-confopts.m4 | `CURL_CONFIGURE_SYMBOL_HIDING` | 369 | *(n/a)* | *(n/a)* |

## makefile

### ❓ `makefile` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 81 occurrences as of 2026-11-26T05:34:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`makefile/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cosmopolitan_build_mk/ctl_BUILD.mk | `$(CTL_A)` | *(n/a)* | *(n/a)* | 31 |
| cosmopolitan_build_mk/ctl_BUILD.mk | `$(CTL_A).pkg` | *(n/a)* | *(n/a)* | 35 |
| cosmopolitan_build_mk/ctl_BUILD.mk | `$(CTL_A_OBJS)` | *(n/a)* | *(n/a)* | 39 |
| cosmopolitan_build_mk/ctl_BUILD.mk | `$(CTL_OBJS)` | *(n/a)* | *(n/a)* | 52 |
| cosmopolitan_build_mk/ctl_BUILD.mk | `o/$(MODE)/ctl` | *(n/a)* | *(n/a)* | 55 |
| cosmopolitan_build_mk/examples_BUILD.mk | `$(EXAMPLES_OBJS)` | *(n/a)* | *(n/a)* | 171 |
| cosmopolitan_build_mk/examples_BUILD.mk | `o/$(MODE)/examples` | *(n/a)* | *(n/a)* | 181 |
| cosmopolitan_build_mk/examples_BUILD.mk | `o/$(MODE)/examples/%.dbg` | *(n/a)* | *(n/a)* | 118 |
| cosmopolitan_build_mk/examples_BUILD.mk | `o/$(MODE)/examples/blas.o` | *(n/a)* | *(n/a)* | 169 |
| cosmopolitan_build_mk/examples_BUILD.mk | `o/$(MODE)/examples/examples.pkg` | *(n/a)* | *(n/a)* | 109 |

### ❓ `makefile` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 15 occurrences as of 2026-11-26T05:34:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`makefile/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cosmopolitan_build_mk/ctl_BUILD.mk | `.PHONY` | *(n/a)* | 54 | *(n/a)* |
| cosmopolitan_build_mk/examples_BUILD.mk | `.PHONY` | *(n/a)* | 180 | *(n/a)* |
| cosmopolitan_build_mk/net_BUILD.mk | `.PHONY` | *(n/a)* | 4 | *(n/a)* |
| cosmopolitan_build_mk/test_BUILD.mk | `.PHONY` | *(n/a)* | 4 | *(n/a)* |
| cosmopolitan_build_mk/third_party_BUILD.mk | `.PHONY` | *(n/a)* | 4 | *(n/a)* |
| cosmopolitan_build_mk/tool_BUILD.mk | `.PHONY` | *(n/a)* | 4 | *(n/a)* |
| micropython_make/py_dynruntime.mk | `.PHONY` | *(n/a)* | 206 | *(n/a)* |
| micropython_make/py_mkenv.mk | `.PHONY` | *(n/a)* | 57 | *(n/a)* |
| micropython_make/py_mkenv.mk | `.DELETE_ON_ERROR` | *(n/a)* | 59 | *(n/a)* |
| micropython_make/py_mkrules.mk | `.PHONY` | *(n/a)* | 111 | *(n/a)* |

### ❓ `makefile` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:03Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`makefile/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| micropython_make/py_mkrules.mk | `lib` | *(n/a)* | 287 | 287 |

### ✅ `makefile` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:03Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/tree-sitter correctly extract makefile targets like .PATH

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| freebsd/Makefile | `.PATH` | 4 | 4 | *(n/a)* |

## matlab

### ✅ `matlab` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 13 occurrences as of 2026-11-26T05:34:06Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy regex splits args more robustly than tree-sitter on MATLAB edge cases.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| eeglab/eeglab.m | `ismatlab` | 1 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `cb_plot_timecourse` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `set_clim` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `mouse_dragged` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `mouse_dragged` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `rot_ended` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `window_closed` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `window_closed` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `button_down` | 2 | 0 | *(n/a)* |
| fieldtrip_plotting_utils/plotting_ft_plot_mesh_interactive.m | `button_down` | 2 | 0 | *(n/a)* |

## nim

### ❓ `nim` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 99 occurrences as of 2026-11-26T05:34:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`nim/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| nim_stdlib/algorithm.nim | `isSorted` | 508 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | `all` | 459 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | ``$`` | 314 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | ``and`` | 431 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | `readImpl` | 362 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | `add` | 179 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | ``or`` | 447 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | `call` | 165 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | `setCallback` | 499 | *(n/a)* | *(n/a)* |
| nim_stdlib/asyncfutures.nim | `fail` | 234 | *(n/a)* | *(n/a)* |

### ❓ `nim` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 103 occurrences as of 2026-11-26T05:34:08Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`nim/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| nim_stdlib/algorithm.nim | `binarySearch` | 0 | 3 | *(n/a)* |
| nim_stdlib/algorithm.nim | `rotateInternal` | 3 | 4 | *(n/a)* |
| nim_stdlib/algorithm.nim | `mergeAlt` | 0 | 7 | *(n/a)* |
| nim_stdlib/algorithm.nim | `sort` | 2 | 3 | *(n/a)* |
| nim_stdlib/algorithm.nim | `rotatedInternal` | 3 | 4 | *(n/a)* |
| nim_stdlib/algorithm.nim | `lowerBound` | 0 | 3 | *(n/a)* |
| nim_stdlib/algorithm.nim | `upperBound` | 0 | 3 | *(n/a)* |
| nim_stdlib/algorithm.nim | `sorted` | 2 | 3 | *(n/a)* |
| nim_stdlib/algorithm.nim | `rotateLeft` | 0 | 3 | *(n/a)* |
| nim_stdlib/algorithm.nim | `rotatedLeft` | 0 | 3 | *(n/a)* |

## objective-c

### ❓ `objective-c` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 14 occurrences as of 2026-11-26T05:34:10Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFURLSessionManager.m | `AFURLSessionManagerTaskDelegate` | *(n/a)* | *(n/a)* | 90 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `AFURLSessionManagerTaskDelegate` | *(n/a)* | *(n/a)* | 106 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `_AFURLSessionTaskSwizzling` | *(n/a)* | *(n/a)* | 343 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `_AFURLSessionTaskSwizzling` | *(n/a)* | *(n/a)* | 347 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `AFURLSessionManager` | *(n/a)* | *(n/a)* | 448 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `AFURLSessionManager` | *(n/a)* | *(n/a)* | 475 |
| godot_ios/godot_view_ios.mm | `GDTViewIOS` | *(n/a)* | *(n/a)* | 46 |
| tensorflow_lite_objc/apps_TestApp_TestApp_AppDelegate.m | `AppDelegate` | *(n/a)* | *(n/a)* | 19 |
| tensorflow_lite_objc/sources_TFLCoreMLDelegate.m | `TFLCoreMLDelegateOptions` | *(n/a)* | *(n/a)* | 25 |
| tensorflow_lite_objc/sources_TFLCoreMLDelegate.m | `TFLCoreMLDelegate` | *(n/a)* | *(n/a)* | 41 |

### ❓ `objective-c` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 14 occurrences as of 2026-11-26T05:34:10Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `description` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `supportsSecureCoding` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFSecurityPolicy.m | `keyPathsForValuesAffectingPinnedPublicKeys` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFSecurityPolicy.m | `supportsSecureCoding` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFURLRequestSerialization.m | `supportsSecureCoding` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFURLResponseSerialization.m | `supportsSecureCoding` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFURLResponseSerialization.m | `supportsSecureCoding` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFURLResponseSerialization.m | `supportsSecureCoding` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFURLResponseSerialization.m | `supportsSecureCoding` | 0 | 0 | 1 |
| afnetworking/AFNetworking_AFURLResponseSerialization.m | `supportsSecureCoding` | 0 | 0 | 1 |

### ❓ `objective-c` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 6 occurrences as of 2026-11-26T05:34:10Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFURLSessionManager.m | `af_resume` | 0 | 2 | 0 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `af_suspend` | 0 | 2 | 0 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `dealloc` | 0 | 2 | 0 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `init` | 0 | 1 | 0 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `taskDescriptionForSessionTasks` | 0 | 1 | 0 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `tasks` | 0 | 6 | 0 |

### ✅ `objective-c` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 404 occurrences as of 2026-11-26T05:34:10Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> Ctags incorrectly extracts brace instead of function name.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `dataTaskWithHTTPMethod` | 252 | 252 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `POST` | 159 | 159 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `POST` | 173 | 173 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `setSecurityPolicy` | 103 | 103 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `initWithCoder` | 307 | 307 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `initWithBaseURL` | 58 | 58 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `initWithBaseURL` | 66 | 66 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `HEAD` | 142 | 142 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `encodeWithCoder` | 332 | 332 | *(n/a)* |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `GET` | 120 | 120 | *(n/a)* |

### ✅ `objective-c` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 368 occurrences as of 2026-11-26T05:34:10Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy misses methods with brace on the next line.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `DELETE:parameters:headers:success:failure:` | *(n/a)* | *(n/a)* | 243 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `GET:parameters:headers:progress:success:failure:` | *(n/a)* | *(n/a)* | 126 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `HEAD:parameters:headers:success:failure:` | *(n/a)* | *(n/a)* | 147 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `PATCH:parameters:headers:success:failure:` | *(n/a)* | *(n/a)* | 230 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `POST:parameters:headers:constructingBodyWithBlock:progress:success:failure:` | *(n/a)* | *(n/a)* | 179 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `POST:parameters:headers:progress:success:failure:` | *(n/a)* | *(n/a)* | 165 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `PUT:parameters:headers:success:failure:` | *(n/a)* | *(n/a)* | 217 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `copyWithZone:` | *(n/a)* | *(n/a)* | 348 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `dataTaskWithHTTPMethod:URLString:parameters:headers:uploadProgress:downloadProgress:success:failure:` | *(n/a)* | *(n/a)* | 260 |
| afnetworking/AFNetworking_AFHTTPSessionManager.m | `encodeWithCoder:` | *(n/a)* | *(n/a)* | 332 |

### ✅ `objective-c` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 24 occurrences as of 2026-11-26T05:34:10Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy misses method missing return type or brace next line.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFNetworkReachabilityManager.m | `if` | *(n/a)* | 63 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `task` | *(n/a)* | 98 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `self` | *(n/a)* | 194 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `self` | *(n/a)* | 992 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `if` | *(n/a)* | 203 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `if` | *(n/a)* | 668 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `if` | *(n/a)* | 670 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `if` | *(n/a)* | 975 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `if` | *(n/a)* | 978 | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `if` | *(n/a)* | 981 | *(n/a)* |

### ✅ `objective-c` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 19 occurrences as of 2026-11-26T05:34:10Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-25T00:00:00Z):
> Confirmed: both sampled occurrences (worldwideweb/HyperText.m:1147 `- unsigned char next_input_block` and :1289 `- void appendEndBlock`) are real Objective-C methods using an old, unparenthesized return-type method-declaration style ('- ReturnType name' instead of the modern '- (ReturnType)name'). GitGalaxy's func_start regex and ctags' generic ObjC parser both handle this loosely and correctly identify both as methods -- confirmed by direct source read. tree-sitter-objc cannot parse this form under ANY node type: a direct parse of the isolated snippet (via tree_sitter_language_pack's 'objc' grammar) shows the grammar treats the leading '-' as a unary-minus operator instead of the ObjC method-scope marker once the return type isn't parenthesized. For next_input_block, this produces a bogus 'expression_statement' (unary_expression on the identifier 'unsigned') immediately followed by a real function_definition node -- but keyed off the wrong return-type token, and the existing method_definition/method_declaration name-extraction fix from #1314 never fires since the node type is wrong entirely. For appendEndBlock, parsing fails further: the whole construct falls into 'void appendEndBlock { ... }' being misread as an assignment_expression on identifier 'void' with the rest swallowed into an ERROR node. This is why tree_sitter_accuracy_audit.py's walker reports the two dissenting names as 'void'/'unsigned' (the misparsed leftover tokens) rather than the real method names, and never reports next_input_block/appendEndBlock as real function names at all -- a genuine tree-sitter-objc grammar limitation (it structurally requires a parenthesized return type to recognize an ObjC method at all), not a GitGalaxy or ctags defect. No credit/debit adjustment -- ctags and GitGalaxy are already an agreeing pair and get precision credit from base reconciliation; adding credit_tools here would double-count exactly the anti-pattern CLAUDE.md's 'Comparative-correctness claims require verification' section warns against. Logged as a new claim in docs/why_gitgalaxy_beats_ast_here.md rather than folded into Claim 2 (dialect/extension syntax) or Claim 3 (parse-error cascade into unrelated code) -- this is neither: it's a strict-grammar-vs-permissive-real-dialect gap within the SAME base language, not an extension the grammar has no concept of, and it's a single, contained, correctly-recovered misparse of the construct itself, not a cascading failure that swallows unrelated downstream code.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFURLSessionManager.m | `session` | 532 | *(n/a)* | 532 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `state` | 420 | *(n/a)* | 420 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `dataTasks` | 686 | *(n/a)* | 686 |
| afnetworking/AFNetworking_AFURLSessionManager.m | `downloadTasks` | 694 | *(n/a)* | 694 |
| godot_ios/display_server_ios.mm | `screen_get_dpi` | 63 | *(n/a)* | 63 |
| godot_ios/display_server_ios.mm | `screen_get_refresh_rate` | 104 | *(n/a)* | 104 |
| godot_ios/display_server_ios.mm | `_screen_hdr_is_supported` | 124 | *(n/a)* | 124 |
| godot_ios/display_server_ios.mm | `_screen_potential_edr_headroom` | 131 | *(n/a)* | 131 |
| godot_ios/display_server_ios.mm | `_screen_current_edr_headroom` | 138 | *(n/a)* | 138 |
| godot_ios/display_server_ios.mm | `screen_get_scale` | 116 | *(n/a)* | 116 |

### ✅ `objective-c` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 13 occurrences as of 2026-11-26T05:34:10Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts method.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFURLSessionManager.m | `URLSession` | 259 | *(n/a)* | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `URLSession` | 929 | *(n/a)* | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `initWithTask` | 108 | *(n/a)* | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `load` | 349 | *(n/a)* | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `invalidateSessionCancelingTasks` | 700 | *(n/a)* | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `setDataTaskDidReceiveResponseBlock` | 862 | *(n/a)* | *(n/a)* |
| afnetworking/AFNetworking_AFURLSessionManager.m | `copyWithZone` | 1270 | *(n/a)* | *(n/a)* |
| afnetworking/UIKit_AFNetworking_AFNetworkActivityIndicatorManager.m | `NS_ENUM` | 27 | *(n/a)* | *(n/a)* |
| godot_ios/display_server_ios.mm | `~DisplayServerIOS` | 48 | *(n/a)* | *(n/a)* |
| godot_ios/os_ios.mm | `~OS_IOS` | 46 | *(n/a)* | *(n/a)* |

### ❓ `objective-c` function args: none agree, GitGalaxy, tree-sitter, ctags differ

*3-way split -- 1 occurrence as of 2026-11-26T05:34:10Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`objective-c/function/args/agree[none]_vs[ctags,gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| afnetworking/AFNetworking_AFURLSessionManager.m | `description` | 0 | 4 | 1 |

## perl

### ✅ `perl` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 122 occurrences as of 2026-11-26T05:34:15Z*

**Verdict** (by Claude (Sonnet 5), direct investigation correcting a prior misdiagnosis, 2026-08-26T00:00:00Z):
> Prior verdict ("GitGalaxy misses subroutines with prototypes or signatures", investigated_at 2026-08-24 by Antigravity) was a misdiagnosis, disproven by direct re-verification: ran both a raw galaxyscope scan of the real corpus file and the actual tri_comparison_gatherer.py pipeline against exiftool/ExifTool.pm. For all 10 sampled names (ParseArguments, ReadValue, WindowsLongPath, Open, EncodeFileName, DecodeBits, Filter, SplitFileName, Exists, IsDirectory), GitGalaxy and ctags EACH report exactly 1 occurrence, at the real body-bearing definition line, identical to each other in every case (e.g. Filter at ExifTool.pm:6483). GitGalaxy is not missing these subs at all. tree_sitter reports 2 occurrences for every one of them: the same real definition, PLUS a bodyless forward declaration a few hundred lines earlier (e.g. "sub Filter($$$);" at ExifTool.pm:97) -- the exact same tree-sitter grammar defect already root-caused and closed as #1608 ("tree-sitter ground truth: perl bodyless forward declarations counted as real functions GitGalaxy correctly ignores"), which the stale 2-tool sibling shape (perl/function/existence/agree[tree_sitter]_vs[gitgalaxy], still_reproduces: false) already documented correctly. This 3-tool shape exists only because tri_comparison_reconcile.py pairs same-named occurrences by RANK (1st-with-1st, 2nd-with-2nd): tree_sitter's phantom forward-declaration entry sorts first (lower line number) for every one of these names, so GitGalaxy/ctags' single real occurrence gets rank-paired against tree_sitter's phantom rank-1 entry instead of its real rank-2 one -- leaving tree_sitter's (correct, real) rank-2 occurrence looking unpaired and "tree_sitter-only." No credit: tree_sitter's rank-2 reading is a real, correct claim, but crediting it here would incorrectly imply ctags/GitGalaxy have a confirmed limitation causing them to miss it -- they do not, they report the identical occurrence, just paired to a different (phantom) tree_sitter slot by the rank algorithm. No debit either: tree_sitter's claim at this rank is not itself wrong, only mis-paired by an artifact of its OWN separate, already-tracked #1608 bug elsewhere in the same file. Net: this shape should not move any tool's precision score in either direction.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| exiftool/ExifTool.pm | `ParseArguments` | *(n/a)* | 138 | *(n/a)* |
| exiftool/ExifTool.pm | `ReadValue` | *(n/a)* | 139 | *(n/a)* |
| exiftool/ExifTool.pm | `WindowsLongPath` | *(n/a)* | 129 | *(n/a)* |
| exiftool/ExifTool.pm | `Open` | *(n/a)* | 130 | *(n/a)* |
| exiftool/ExifTool.pm | `EncodeFileName` | *(n/a)* | 128 | *(n/a)* |
| exiftool/ExifTool.pm | `Filter` | *(n/a)* | 97 | *(n/a)* |
| exiftool/ExifTool.pm | `DecodeBits` | *(n/a)* | 95 | *(n/a)* |
| exiftool/ExifTool.pm | `Exists` | *(n/a)* | 131 | *(n/a)* |
| exiftool/ExifTool.pm | `SplitFileName` | *(n/a)* | 127 | *(n/a)* |
| exiftool/ExifTool.pm | `IsDirectory` | *(n/a)* | 132 | *(n/a)* |

### ✅ `perl` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:34:15Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> Ctags incorrectly truncates subroutine names containing package separators (::).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| exiftool/exiftool | `Image` | *(n/a)* | *(n/a)* | 329 |
| exiftool/exiftool | `Image` | *(n/a)* | *(n/a)* | 330 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 802 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 818 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 834 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 966 |
| spamassassin/Makefile.PL | `MY` | *(n/a)* | *(n/a)* | 990 |

### ✅ `perl` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:34:15Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/tree-sitter correctly extract full subroutine names with package separators.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| exiftool/exiftool | `Image::ExifTool::EndDir` | 329 | 329 | *(n/a)* |
| exiftool/exiftool | `Image::ExifTool::End` | 330 | 330 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::constants` | 834 | 834 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::dist` | 966 | 966 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::postamble` | 990 | 990 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::libscan` | 802 | 802 | *(n/a)* |
| spamassassin/Makefile.PL | `MY::install` | 818 | 818 | *(n/a)* |

### ✅ `perl` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:15Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/ctags correctly extract package declarations.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| spamassassin/PerMsgStatus.pm | `Mail::SpamAssassin::PerMsgStatus` | *(n/a)* | *(n/a)* | 3022 |

### ✅ `perl` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 12 occurrences as of 2026-11-26T05:34:15Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy regex splits args appropriately.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bugzilla/Bug.pm | `_multi_select_accessor` | 3 | 2 | *(n/a)* |
| bugzilla/Bug.pm | `_cf_accessor` | 3 | 2 | *(n/a)* |
| bugzilla/CGI.pm | `multipart_start` | 1 | 2 | *(n/a)* |
| mojo/Promise.pm | `_finally` | 4 | 3 | *(n/a)* |
| mojo/Template.pm | `process` | 2 | 1 | *(n/a)* |
| spamassassin/AsyncLoop.pm | `bgsend_and_start_lookup` | 10 | 7 | *(n/a)* |
| spamassassin/HTML.pm | `parse_css_background` | 25 | 1 | *(n/a)* |
| spamassassin/HTML.pm | `html_tests` | 20 | 4 | *(n/a)* |
| spamassassin/HTML.pm | `display_text` | 2 | 3 | *(n/a)* |
| spamassassin/HTML.pm | `get_rendered_text` | 1 | 2 | *(n/a)* |

## php

### ✅ `php` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:20Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> Ctags incorrectly extracts synthetic AnonymousClass artifacts as real named classes. GitGalaxy and tree-sitter are correct to ignore them.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| laravel_core/BladeCompiler.php | `AnonymousClassa08aab890100` | *(n/a)* | *(n/a)* | 342 |

## powershell

### ✅ `powershell` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 91 occurrences as of 2026-11-26T05:34:26Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts function.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/PowerShell__build.psm1 | `New-NugetConfigFile` | 3793 | 3793 | *(n/a)* |
| core/PowerShell__build.psm1 | `New-TestPackage` | 3706 | 3706 | *(n/a)* |
| core/PowerShell__build.psm1 | `Clear-NativeDependencies` | 3967 | 3967 | *(n/a)* |
| core/PowerShell__build.psm1 | `Set-CorrectLocale` | 3891 | 3891 | *(n/a)* |
| core/PowerShell__build.psm1 | `Get-UniquePackageFolderName` | 3681 | 3681 | *(n/a)* |
| core/PowerShell__build.psm1 | `ToString` | 3134 | 3134 | *(n/a)* |
| core/PowerShell__build.psm1 | `ToString` | 3174 | 3174 | *(n/a)* |
| core/PowerShell__build.psm1 | `ToString` | 3219 | 3219 | *(n/a)* |
| core/PowerShell__build.psm1 | `ToString` | 3244 | 3244 | *(n/a)* |
| core/PowerShell__build.psm1 | `ToString` | 3256 | 3256 | *(n/a)* |

### ✅ `powershell` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 33 occurrences as of 2026-11-26T05:34:26Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/tree-sitter correctly extract classes.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| PowerToys/Check preview handler registration.ps1 | `TypeHandlerData` | *(n/a)* | 12 | *(n/a)* |
| core/PowerShell__build.psm1 | `assemblies` | *(n/a)* | 3119 | *(n/a)* |
| core/PowerShell__build.psm1 | `testAssembly` | *(n/a)* | 3149 | *(n/a)* |
| core/PowerShell__build.psm1 | `collection` | *(n/a)* | 3205 | *(n/a)* |
| core/PowerShell__build.psm1 | `errors` | *(n/a)* | 3235 | *(n/a)* |
| core/PowerShell__build.psm1 | `error` | *(n/a)* | 3238 | *(n/a)* |
| core/PowerShell__build.psm1 | `cdata` | *(n/a)* | 3253 | *(n/a)* |
| core/PowerShell__build.psm1 | `failure` | *(n/a)* | 3261 | *(n/a)* |
| core/PowerShell__build.psm1 | `resultenum` | *(n/a)* | 3280 | *(n/a)* |
| core/PowerShell__build.psm1 | `trait` | *(n/a)* | 3286 | *(n/a)* |

### ✅ `powershell` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:26Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts function.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/ci.psm1 | `Test-MergeConflictMarker` | 1020 | *(n/a)* | 1020 |

### ✅ `powershell` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 3 occurrences as of 2026-11-26T05:34:26Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy extracts args accurately.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| core/PowerShell__build.psm1 | `Restore-PSPester` | 0 | 1 | *(n/a)* |
| core/build.psm1 | `Restore-PSPester` | 0 | 1 | *(n/a)* |
| core/packaging.psm1 | `New-MSIPackage` | 11 | 10 | *(n/a)* |

## python

### ✅ `python` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 100 occurrences as of 2026-11-26T05:34:36Z*

**Verdict** (by claude sonnet 5, tri-comparison-ledger-sweep (direct investigation, no dispatch needed), 2026-08-21T12:03:03Z):
> Already documented as Claim 2 in docs/why_gitgalaxy_beats_ast_here.md: tree-sitter-python has no concept of Cython's cdef class/cdef/cpdef syntax at all and loses track of scope at each cdef class boundary, so it finds 0 functions in cython/MemoryView.pyx and cython/MemoryView.pxd (0/0 vs GitGalaxy+ctags' 72/16, full agreement as of the 2026-08-21 get_slice_from_memview follow-up fix -- see the sibling agree[ctags]_vs[gitgalaxy,tree_sitter] shape's verdict for that fix's details). This shape's count grew from 32 to 99 to 100 across this PR's two fixes: it originally covered only the 32 'def'-based methods inside cdef class blocks; each cdef/cpdef func_start fix moved newly-recognized occurrences into THIS shape too, since they still disagree with tree-sitter for the identical underlying reason. GitGalaxy now has zero recall gaps on this corpus for Cython functions -- the only remaining disagreement with tree-sitter is tree-sitter's own structural blindness to the Cython dialect, not a GitGalaxy defect. No GitGalaxy fix needed for tree-sitter's own recall here -- grammar limitation, not an engine defect.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pxd | `memoryview_fromslice` | 98 | *(n/a)* | 98 |
| cython/MemoryView.pxd | `memoryview_copy_contents` | 105 | *(n/a)* | 105 |
| cython/MemoryView.pxd | `array_cwrapper` | 53 | *(n/a)* | 53 |
| cython/MemoryView.pxd | `memoryview_cwrapper` | 88 | *(n/a)* | 88 |
| cython/MemoryView.pxd | `setitem_slice_assignment` | 79 | *(n/a)* | 79 |
| cython/MemoryView.pxd | `setitem_slice_assign_scalar` | 80 | *(n/a)* | 80 |
| cython/MemoryView.pxd | `setitem_indexed` | 81 | *(n/a)* | 81 |
| cython/MemoryView.pxd | `setitem_indexed1` | 82 | *(n/a)* | 82 |
| cython/MemoryView.pxd | `assign_item_from_object` | 84 | *(n/a)* | 84 |
| cython/MemoryView.pxd | `get_item_pointer` | 77 | *(n/a)* | 77 |

### ✅ `python` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:34:36Z*

**Verdict** (by claude sonnet 5, tri-comparison-ledger-sweep (direct investigation, no dispatch needed), 2026-08-21T03:23:52Z):
> Extends Claim 2 (docs/why_gitgalaxy_beats_ast_here.md) one syntactic level up: tree-sitter-python doesn't just lose track of scope inside a cdef class block, it fails to recognize the 'cdef class' declaration itself as a class at all -- 0 class nodes reported for cython/MemoryView.pyx, missing all 4 real classes (array, Enum, memoryview, _memoryviewslice). GitGalaxy's class_start regex and ctags both correctly identify all 4 by name, confirmed via direct gather_language() check. Note: GitGalaxy's own class_data schema has no start_line column (documented in tri_comparison_gatherer.py's own module docstring), so the ledger's stored example shows a None 'reading' for GitGalaxy on this shape -- that's the (structurally absent) line number field, not an indication GitGalaxy missed the class; by NAME it matches ctags exactly. No GitGalaxy fix needed -- tree-sitter-python grammar limitation. docs/why_gitgalaxy_beats_ast_here.md's Claim 2 updated with this class-level evidence in the same PR.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cython/MemoryView.pyx | `array` | *(n/a)* | *(n/a)* | 130 |
| cython/MemoryView.pyx | `Enum` | *(n/a)* | *(n/a)* | 318 |
| cython/MemoryView.pyx | `memoryview` | *(n/a)* | *(n/a)* | 348 |
| cython/MemoryView.pyx | `_memoryviewslice` | *(n/a)* | *(n/a)* | 936 |

## r

### ❓ `r` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 14 occurrences as of 2026-11-26T05:34:38Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`r/function/existence/agree[gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dplyr_package/across.R | `error` | 333 | *(n/a)* | *(n/a)* |
| dplyr_package/case-when.R | `.f` | 534 | *(n/a)* | *(n/a)* |
| dplyr_package/case-when.R | `error` | 570 | *(n/a)* | *(n/a)* |
| rlang_package/deparse.R | `push_one` | 115 | *(n/a)* | *(n/a)* |
| rlang_package/deparse.R | `decrease_indent` | 183 | *(n/a)* | *(n/a)* |
| rlang_package/deparse.R | `get_indent` | 99 | *(n/a)* | *(n/a)* |
| rlang_package/deparse.R | `increase_indent` | 167 | *(n/a)* | *(n/a)* |
| rlang_package/deparse.R | `push` | 108 | *(n/a)* | *(n/a)* |
| rlang_package/deparse.R | `push_sticky` | 150 | *(n/a)* | *(n/a)* |
| rlang_package/deparse.R | `deparse` | 78 | *(n/a)* | *(n/a)* |

### ❓ `r` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 8 occurrences as of 2026-11-26T05:34:38Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`r/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| dplyr_package/colwise-funs.R | `[.fun_list` | *(n/a)* | 131 | *(n/a)* |
| rlang_package/attr.R | `names2<-` | *(n/a)* | 240 | *(n/a)* |
| rlang_package/bytes.R | `[.rlib_bytes` | *(n/a)* | 67 | *(n/a)* |
| rlang_package/bytes.R | `[[.rlib_bytes` | *(n/a)* | 71 | *(n/a)* |
| rlang_package/cnd-entrace.R | `hnd_entrace` | *(n/a)* | 91 | *(n/a)* |
| rlang_package/cnd-last.R | `[.rlang:::list_of_conditions` | *(n/a)* | 286 | *(n/a)* |
| rlang_package/cnd-last.R | `print.rlang:::list_of_conditions` | *(n/a)* | 291 | *(n/a)* |
| rlang_package/cnd-last.R | `summary.rlang:::list_of_conditions` | *(n/a)* | 296 | *(n/a)* |

## ruby

### ❓ `ruby` class existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 75 occurrences as of 2026-11-26T05:34:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 11 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 22 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 35 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 45 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 56 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 71 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 87 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 95 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 104 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `Foo` | *(n/a)* | *(n/a)* | 117 |

### ❓ `ruby` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 16 occurrences as of 2026-11-26T05:34:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 163 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 177 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 188 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 205 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 347 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 403 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 419 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 435 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 451 |
| homebrew_ruby/Library_Homebrew_test_rubocops_components_order_spec.rb | `install` | *(n/a)* | *(n/a)* | 467 |

### ❓ `ruby` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:34:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| homebrew_ruby/Library_Homebrew_rubocops_text.rb | `audit_formula` | *(n/a)* | 135 | 135 |
| rails_http_token_auth/http_token_authentication_test.rb | `mock_authorization_request` | *(n/a)* | 243 | 243 |
| rails_http_token_auth/http_token_authentication_test.rb | `encode_credentials` | *(n/a)* | 247 | 247 |
| selenium_ruby/rb_lib_selenium_webdriver_common_keys.rb | `[]` | *(n/a)* | 123 | 123 |

### ❓ `ruby` function args: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 2 occurrences as of 2026-11-26T05:34:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/args/agree[gitgalaxy,tree_sitter]_vs[ctags]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| selenium_ruby/rb_lib_selenium_webdriver_chromium_options.rb | `initialize` | 2 | 2 | 1 |
| selenium_ruby/rb_lib_selenium_webdriver_ie_driver.rb | `initialize` | 4 | 4 | 3 |

### ❓ `ruby` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:42Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`ruby/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| selenium_ruby/rb_lib_selenium_webdriver_common_keys.rb | `self` | 123 | *(n/a)* | *(n/a)* |

### ✅ `ruby` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 33 occurrences as of 2026-11-26T05:34:42Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/tree-sitter miss classes containing module scope operators.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when invalid` | *(n/a)* | *(n/a)* | 31 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when it contains no DSL version` | *(n/a)* | *(n/a)* | 49 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when language is set explicitly` | *(n/a)* | *(n/a)* | 164 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when manual` | *(n/a)* | *(n/a)* | 504 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when no intel value is specified` | *(n/a)* | *(n/a)* | 347 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when no_autobump! is set` | *(n/a)* | *(n/a)* | 149 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when running on arm` | *(n/a)* | *(n/a)* | 122 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when running on arm` | *(n/a)* | *(n/a)* | 350 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when running on intel` | *(n/a)* | *(n/a)* | 132 |
| homebrew_ruby/Library_Homebrew_test_cask_dsl_spec.rb | `when running on intel` | *(n/a)* | *(n/a)* | 360 |

### ✅ `ruby` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 9 occurrences as of 2026-11-26T05:34:42Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/tree-sitter correctly extract class << self.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| homebrew_ruby/Library_Homebrew_abstract_command.rb | `<< self` | *(n/a)* | 27 | *(n/a)* |
| rails/base.rb | `<< self` | *(n/a)* | 53 | *(n/a)* |
| rails/blob.rb | `ActiveStorage::Blob` | *(n/a)* | 19 | *(n/a)* |
| rails/blob.rb | `<< self` | *(n/a)* | 69 | *(n/a)* |
| rails/inbound_emails_controller.rb | `Ingresses::Mailgun::InboundEmailsController` | *(n/a)* | 45 | *(n/a)* |
| rails/metal.rb | `<< self` | *(n/a)* | 144 | *(n/a)* |
| rails/metal.rb | `<< self` | *(n/a)* | 290 | *(n/a)* |
| selenium_ruby/rb_lib_selenium_devtools.rb | `<< self` | *(n/a)* | 22 | *(n/a)* |
| selenium_ruby/rb_lib_selenium_webdriver_remote_http_common.rb | `<< self` | *(n/a)* | 33 | *(n/a)* |

### ✅ `ruby` function args: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:34:42Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/ctags accurately split args.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| rails/base.rb | `process` | 2 | 1 | 2 |
| rails/base.rb | `process_action` | 1 | 0 | 1 |
| rails/metal.rb | `use` | 1 | 0 | 1 |
| selenium_ruby/rb_lib_selenium_webdriver_remote_http_common.rb | `request` | 0 | 1 | 0 |

### ✅ `ruby` function args: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 3 occurrences as of 2026-11-26T05:34:42Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy regex misses some trailing args.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| homebrew_ruby/Library_Homebrew_abstract_command.rb | `dev_cmd?` | 1 | 0 | 0 |
| homebrew_ruby/Library_Homebrew_abstract_command.rb | `ruby_cmd?` | 1 | 0 | 0 |
| homebrew_ruby/Library_Homebrew_abstract_command.rb | `parser` | 1 | 0 | 0 |

## rust

### ✅ `rust` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 159 occurrences as of 2026-11-26T05:34:53Z*

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

*2-vs-1 -- 26 occurrences as of 2026-11-26T05:34:53Z*

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

*2-vs-1 -- 3 occurrences as of 2026-11-26T05:34:53Z*

**Verdict** (by Claude Sonnet 5 (resolved directly via live ctags run, no dispatch), 2026-08-19T00:00:00Z):
> Confirmed structural ctags limitation, not a bug -- resolved directly (no dispatch needed). All 3 sampled names (XRegUnion, FRegUnion, VRegUnion) are real Rust `union { }` declarations (confirmed at wasmtime/wasmtime_pulley_interp.rs:404,529,604), distinct from `struct` -- Rust's less-common C-style unsafe union construct. Ran `ctags --list-kinds-full=Rust` directly: its Rust parser's kind list is macro/method/implementation/enumerator/function/enum/interface/field/module/struct/typedef/variable -- there is NO union kind at all. Confirmed via direct ctags run against this exact file: it correctly finds the wrapping `struct FRegVal(FRegUnion)`-shaped types right next to each missed union, so this isn't a general miss, specifically a missing Rust-union kind. Same category as the already-documented ctags Haskell class-kind gap (tests/tools/ctags_reader.py) -- worth a similar doc note there, not a GitHub issue (nothing to fix, ctags upstream has no union support for this language).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `XRegUnion` | *(n/a)* | 404 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `FRegUnion` | *(n/a)* | 529 | *(n/a)* |
| wasmtime/wasmtime_pulley_interp.rs | `VRegUnion` | *(n/a)* | 604 | *(n/a)* |

### ✅ `rust` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:53Z*

**Verdict** (by Claude Sonnet 5 (resolved directly via live ctags run, no dispatch), 2026-08-19T00:00:00Z):
> Confirmed via direct ctags run and sibling comparison, resolved directly (no dispatch needed). `done_decode` (wasmtime/wasmtime_pulley_interp.rs:964) has a destructuring-pattern parameter -- `Done { _priv }: Done`, not a simple `name: Type` binding. Ran ctags directly against the file: its IMMEDIATE SIBLING in the same impl block, `debug_assert_done_reason_none` (line 960, same visibility/receiver shape, ordinary `&mut self`-only signature), IS correctly found as a ctags 'method'. done_decode alone is missing from ctags' output. Isolates the cause precisely to the destructuring-pattern parameter -- ctags' regex-based Rust parser appears to fail/skip the whole function when a parameter is a struct pattern rather than a plain identifier binding. GitGalaxy and tree-sitter both handle this fine (both agree on line 964). N=1 in this corpus, plausibly a real, narrow ctags parser gap (not GitGalaxy's) -- not chasing further given the tiny sample, noting rather than filing an issue since there's nothing in this repo to fix.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| wasmtime/wasmtime_pulley_interp.rs | `done_decode` | 964 | 964 | *(n/a)* |

## scala

### ❓ `scala` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 6 occurrences as of 2026-11-26T05:34:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`scala/function/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cobrix_scala/cobol-parser_src_main_scala_za_co_absa_cobrix_cobol_parser_encoding_codepage_CodePage.scala | `codePageShortName` | *(n/a)* | 30 | *(n/a)* |
| cobrix_scala/cobol-parser_src_main_scala_za_co_absa_cobrix_cobol_parser_encoding_codepage_CodePage.scala | `convert` | *(n/a)* | 35 | *(n/a)* |
| cobrix_scala/cobol-parser_src_main_scala_za_co_absa_cobrix_cobol_parser_encoding_codepage_CodePage.scala | `convert` | *(n/a)* | 45 | *(n/a)* |
| gradle_scala/platforms_documentation_docs_src_snippets_scala_customizedLayout_kotlin_src_scala_org_gradle_sample_Named.scala | `names` | *(n/a)* | 4 | *(n/a)* |
| gradle_scala/platforms_documentation_docs_src_snippets_scala_quickstart_kotlin_src_main_scala_org_gradle_sample_Named.scala | `names` | *(n/a)* | 9 | *(n/a)* |
| gradle_scala/platforms_documentation_docs_src_snippets_scala_quickstart_kotlin_src_main_scala_org_gradle_sample_Named.scala | `importedList` | *(n/a)* | 11 | *(n/a)* |

### ❓ `scala` class existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:34:56Z*

**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the process -- read the source at a few examples below, then hand-edit this entry (`scala/class/existence/agree[tree_sitter]_vs[gitgalaxy]`) in `tri_comparison_ledger.json`.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| gradle_scala/testing_performance_src_templates_project-with-source_Production.scala | `$` | *(n/a)* | 3 | *(n/a)* |

### ✅ `scala` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 17 occurrences as of 2026-11-26T05:34:56Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy counts args accurately.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| cobrix_scala/cobol-parser_src_main_scala_za_co_absa_cobrix_cobol_parser_encoding_codepage_CodePage.scala | `supportsEncoding` | 1 | 0 | *(n/a)* |
| kafka/KafkaApis.scala | `isAcknowledgeDataPresentInFetchRequest` | 1 | 0 | *(n/a)* |
| kafka/LogManager.scala | `logsByDir` | 2 | 0 | *(n/a)* |
| kafka/LogManager.scala | `offlineLogDirs` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `lowWatermarkIfLeader` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `toString` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `activeProducerState` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `numDelayedDelete` | 3 | 0 | *(n/a)* |
| kafka/Partition.scala | `partitionId` | 1 | 0 | *(n/a)* |
| kafka/Partition.scala | `logEndOffsetString` | 1 | 0 | *(n/a)* |

## scheme

### ✅ `scheme` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 219 occurrences as of 2026-11-26T05:34:59Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts nested define blocks.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| racket/cpnanopass.ss | `extract-trace-code` | 8280 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `extract-uvar` | 694 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `insert-procedure-check` | 957 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `insert-procedure-check` | 4173 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `build-attachment-get` | 5217 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `build-free-ref` | 2260 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `compatible-fv` | 547 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `maybe-add-detour-trap-check` | 3960 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `tarjan` | 1516 | *(n/a)* | *(n/a)* |
| racket/cpnanopass.ss | `compute-sccs` | 1510 | *(n/a)* | *(n/a)* |

### ✅ `scheme` function existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 129 occurrences as of 2026-11-26T05:34:59Z*

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

### ✅ `shell` function existence: tree-sitter, ctags agree, GitGalaxy differ

*2-vs-1 -- 153 occurrences as of 2026-11-26T05:35:04Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-28T23:59:00Z):
> Down from 16 to 4 after this PR's shell shielding fixes. Of the 4 residual GitGalaxy misses: `moby/check-config.sh::zgrep` (line 23) is a deliberate architectural limitation -- it is defined nested inside an `if ! command -v zgrep; then ... fi` guard, and GitGalaxy's Mode-D extractor (`_slice_by_keywords`) only emits `scope_depth == 0` constructs; tree-sitter and ctags both do full nesting. `freebsd-src/runulp.sh::t` and `::check` are a real GitGalaxy bug (GH #2405): a bare `for` keyword inside a command argument (`echo ERROR: Could not determine ULP limit for $routine ...`) is counted as a Mode-D scope opener, desyncing the depth stack so `t` is mis-named `t_[Truncated]` and `check` after it is never seen. `serenity/builtin.sh::__complete_job_spec` is a SerenityOS Shell dialect difference (`if ... {` brace blocks, no `then`/`fi`), folded into the same issue. ctags and tree-sitter are correct on all 4. No credit/debit: real 2-tool corroboration of functions GitGalaxy's regex path misses, already reflected in raw recall -- validating only clears the chart asterisk.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| freebsd-src/ed_test.sh | `move_head` | *(n/a)* | 258 | 258 |
| freebsd-src/ed_test.sh | `move_body` | *(n/a)* | 262 | 262 |
| freebsd-src/ed_test.sh | `transfer_head` | *(n/a)* | 292 | 292 |
| freebsd-src/ed_test.sh | `transfer_body` | *(n/a)* | 296 | 296 |
| freebsd-src/ed_test.sh | `transfer_search_head` | *(n/a)* | 330 | 330 |
| freebsd-src/ed_test.sh | `transfer_search_body` | *(n/a)* | 334 | 334 |
| freebsd-src/ed_test.sh | `undo_head` | *(n/a)* | 359 | 359 |
| freebsd-src/ed_test.sh | `undo_body` | *(n/a)* | 363 | 363 |
| freebsd-src/ed_test.sh | `global_move_head` | *(n/a)* | 422 | 422 |
| freebsd-src/ed_test.sh | `global_move_body` | *(n/a)* | 426 | 426 |

### ✅ `shell` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 49 occurrences as of 2026-11-26T05:35:04Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-28T23:59:00Z):
> Mixed shape, two independent causes. (a) FALSE POSITIVE: ctags' Sh parser tags a bare SCALAR assignment as an `f`-kind function in some contexts -- `GREP_OPTS=`, `FILTERED_ENV=`, `_GROUPS=`, `l=` (the tag name keeps the trailing `=`); GitGalaxy and tree-sitter both correctly ignore these. (b) REAL ctags-only recall win: `darwin-xnu/makesyscalls.sh::parseline` / `::parserr` / `::align_comment` are genuine functions GitGalaxy and tree-sitter both miss (non-`name()` definition style, single corpus file). Neither is a GitGalaxy defect -- (a) is a ctags limitation now noted in `tests/tools/ctags_reader.py`'s shell KIND-MAP section, (b) is a minor GitGalaxy/tree-sitter recall gap on an unusual form, not filed separately. No credit/debit: ctags is a lone claimant and its claim is only partly real, so neither adjustment is well-formed. (Prior verdict said 'array assignments' -- inaccurate; they are scalar assignments.)

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| ansible/ansible-doc__runme.sh | `GREP_OPTS=` | *(n/a)* | *(n/a)* | 22 |
| brew/brew | `FILTERED_ENV=` | *(n/a)* | *(n/a)* | 292 |
| darwin-xnu/makesyscalls.sh | `[{}` | *(n/a)* | *(n/a)* | 134 |
| darwin-xnu/makesyscalls.sh | `align_comment` | *(n/a)* | *(n/a)* | 314 |
| darwin-xnu/makesyscalls.sh | `parseline` | *(n/a)* | *(n/a)* | 327 |
| darwin-xnu/makesyscalls.sh | `parseline` | *(n/a)* | *(n/a)* | 498 |
| darwin-xnu/makesyscalls.sh | `parserr` | *(n/a)* | *(n/a)* | 321 |
| darwin-xnu/persona_test_run_src.sh | `_GROUPS=` | *(n/a)* | *(n/a)* | 159 |
| darwin-xnu/persona_test_run_src.sh | `l=` | *(n/a)* | *(n/a)* | 227 |
| darwin-xnu/vnode_if.sh | `do_offset` | *(n/a)* | *(n/a)* | 284 |

### ✅ `shell` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 15 occurrences as of 2026-11-26T05:35:04Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-28T23:59:00Z):
> GitGalaxy and ctags are both correct; tree-sitter is wrong. All 11 occurrences are ordinary top-level `name() { ... }` definitions in `moby/check-config.sh` (`color`, `check_limit_over`, `wrap_good`, ...). `tree-sitter-bash` treats a `;` inside a `${codes:+$codes;}` use-alternative parameter expansion (line 72, inside `color()`) as a real command separator, sets `tree.root_node.has_error = True`, and emits ZERO `function_definition` nodes for the whole file -- a Claim-3-style parse-error cascade, minimized and logged in `docs/why_gitgalaxy_beats_ast_here.md` (Claim 3, fourth confirmed instance). No credit: `agreeing_tools` has 2 entries, so these occurrences are already in both tools' `matched_consensus` and a credit would double-count. Validating clears the tree-sitter asterisk.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| moby/check-config.sh | `color` | 47 | *(n/a)* | 47 |
| moby/check-config.sh | `check_limit_over` | 408 | *(n/a)* | 408 |
| moby/check-config.sh | `check_flag` | 95 | *(n/a)* | 95 |
| moby/check-config.sh | `check_sysctl` | 131 | *(n/a)* | 131 |
| moby/check-config.sh | `check_command` | 113 | *(n/a)* | 113 |
| moby/check-config.sh | `check_device` | 122 | *(n/a)* | 122 |
| moby/check-config.sh | `check_flags` | 106 | *(n/a)* | 106 |
| moby/check-config.sh | `wrap_good` | 85 | *(n/a)* | 85 |
| moby/check-config.sh | `wrap_bad` | 88 | *(n/a)* | 88 |
| moby/check-config.sh | `wrap_color` | 76 | *(n/a)* | 76 |

### ✅ `shell` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:35:04Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-28T23:59:00Z):
> All 3 remaining occurrences are GitGalaxy over-detection artifacts, not real functions that ctags and tree-sitter both miss. `runulp.sh::t_[Truncated]` and `serenity/builtin.sh::_complete_unalias_[Truncated]` are the SAME functions GitGalaxy reports as missed in `shell/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`: a Mode-D scope-stack desync leaves the enclosing block open to EOF, so `_slice_by_keywords` emits one file-spanning `<name>_[Truncated]` satellite under a mangled name instead of the real function. `serenity/run-tests-and-shutdown.sh::Anonymous_Block_[Truncated]` is the same mechanism on a SerenityOS Shell `if ... { ... }` brace block that GitGalaxy's POSIX-oriented opener/closer set cannot balance. Zero genuine GitGalaxy-only true positives. The two remaining triggers (a bare `for` keyword inside an `echo` argument in runulp.sh; SerenityOS non-POSIX `if...{` block syntax) are filed as GH #2405. No credit: GitGalaxy is a lone claimant and its claim is not real, so the false positives already count against its precision with no adjustment. This shape was 7 occurrences before this PR; the `--`/`//` bogus-comment-marker fix and heredoc-delimiter-preservation fix (gitgalaxy/core/detector.py) cleared the other 4.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| serenity/generate_manpages.sh | `Anonymous_Block_[Truncated]` | 23 | *(n/a)* | *(n/a)* |

### ✅ `shell` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 11 occurrences as of 2026-11-26T05:35:04Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-28T23:59:00Z):
> POSIX shell has no formal parameter-list syntax, so this is an `args`-granularity `proxy` case (see `docs/why_gitgalaxy_beats_ast_here.md` Claim 1). GitGalaxy derives arity from the highest positional-parameter index referenced in the function body (`$1`/`$2`/`$@`) -- `S_flag_body`->7, `kube::build::docker_available_on_osx`->2, `detect-project`->3 are all correct real arities, not over-counts. `tree-sitter-bash` emits a spurious 1-element `parameter_list` on some functions (a grammar artifact -- there is nothing to parse), which is the source of every disagreement here. ctags emits no `signature:` field for shell at all. `credit_tools` CLEARED: `agreeing_tools` is empty (`agree[none]`), so a credit has no defined effect on precision (`_credit_is_well_formed` requires exactly one agreeing tool) -- it was malformed and printed a warning on every chart run. Args precision is not badge-gated; no-adjustment is the correct outcome.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| ansible/ansible-galaxy__runme.sh | `f_ansible_galaxy_status` | 0 | 1 | *(n/a)* |
| curl/initscript.sh | `CLcommand` | 0 | 1 | *(n/a)* |
| freebsd-src/ls_tests.sh | `S_flag_body` | 7 | 1 | *(n/a)* |
| freebsd-src/runulp.sh | `t` | 2 | 1 | *(n/a)* |
| kubernetes/common.sh | `kube::build::docker_available_on_osx` | 2 | 0 | *(n/a)* |
| kubernetes/configure-helper.sh | `addockeropt` | 1 | 0 | *(n/a)* |
| kubernetes/configure-helper.sh | `log-init` | 2 | 0 | *(n/a)* |
| kubernetes/configure-helper.sh | `log-trap-push` | 0 | 1 | *(n/a)* |
| kubernetes/etcd.sh | `kube::etcd::version` | 3 | 1 | *(n/a)* |
| kubernetes/pre-existing__util.sh | `detect-project` | 3 | 0 | *(n/a)* |

## solidity

### ✅ `solidity` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 18 occurrences as of 2026-11-26T05:35:05Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts constructors.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| openzeppelin/CrosschainRemoteExecutor.sol | `constructor` | 33 | *(n/a)* | *(n/a)* |
| openzeppelin/ERC2771Forwarder.sol | `constructor` | 106 | *(n/a)* | *(n/a)* |
| openzeppelin/Governor.sol | `receive` | 83 | *(n/a)* | *(n/a)* |
| openzeppelin/Governor.sol | `constructor` | 76 | *(n/a)* | *(n/a)* |
| openzeppelin/Proxy.sol | `fallback` | 66 | *(n/a)* | *(n/a)* |
| openzeppelin/ReentrancyGuard.sol | `constructor` | 58 | *(n/a)* | *(n/a)* |
| solady_utils/src_utils_Initializable.sol | `constructor` | 46 | *(n/a)* | *(n/a)* |
| solady_utils/src_utils_LibRLP.sol | `encodeList` | 239 | *(n/a)* | *(n/a)* |
| solady_utils/src_utils_LibRLP.sol | `encodeBytes` | 211 | *(n/a)* | *(n/a)* |
| solady_utils/src_utils_LibRLP.sol | `encodeUint` | 190 | *(n/a)* | *(n/a)* |

## sqlite

### ✅ `sqlite` class existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 7 occurrences as of 2026-11-26T05:35:07Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-30):
> Confirmed GitGalaxy correct on all 7; two independent, confirmed ctags 't' (table) kind limitations, zero unexplained residual. (1) mediawiki_sqlite_tables/searchindex-fts3.sql's 'searchindex' -- `CREATE VIRTUAL TABLE searchindex USING FTS3(...)`; ctags' SQL parser doesn't tag `CREATE VIRTUAL TABLE`, only plain `CREATE TABLE`. (2) sqitch_sqlite_engine/engine_sqlite.sql and t_upgradable_registry.sql's 'releases', upgrade_sqlite-1.0.sql's 'releases', upgrade_sqlite-1.1.sql's 'new_changes' -- real `CREATE TABLE releases (...)` / `CREATE TABLE new_changes (...)` statements that ctags drops when the file opens with a leading `BEGIN;` transaction-start statement (confirmed directly: `ctags -x --language-force=SQL` on engine_sqlite.sql misses only the first CREATE TABLE after `BEGIN;`, correctly tagging every later one in the same file). (3) yii2_sqlite_schema/framework_i18n_schema-sqlite.sql's 'message'/'source_message' -- backtick-quoted `CREATE TABLE \`message\``; ctags' SQL parser doesn't strip SQLite's backtick-quoted-identifier syntax (it does handle double-quoted, confirmed separately on the prisma corpus). GitGalaxy's class_start (epic #813/#836) already handled all three shapes correctly, but was gated off named-entity output until sqlite was added to _CLASS_START_NAMED_EXTRACTION_LANGS (detector.py, #2513). Re-verified after #2512 fixed 3 separate aperture/census exclusions that had silently dropped 33 of 73 real sqlite files from ever being scanned (infra_path_pattern, the machine-generated-content gate, and the Neighborhood Micro-Mass Quota) -- the newly-visible 33 files introduce zero new gitgalaxy-only class occurrences; this shape's set of 7 is unchanged. GitGalaxy finds 188/190 real tables across the full pinned crucible corpus (73 scanned files) vs. ctags' 183/190, a strict superset once the 2 new ctags false positives (see the sibling agree[ctags]_vs[gitgalaxy] shape) are accounted for.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| mediawiki_sqlite_tables/searchindex-fts3.sql | `searchindex` | *(n/a)* | *(n/a)* | *(n/a)* |
| sqitch_sqlite_engine/engine_sqlite.sql | `releases` | *(n/a)* | *(n/a)* | *(n/a)* |
| sqitch_sqlite_engine/t_upgradable_registry.sql | `releases` | *(n/a)* | *(n/a)* | *(n/a)* |
| sqitch_sqlite_engine/upgrade_sqlite-1.0.sql | `releases` | *(n/a)* | *(n/a)* | *(n/a)* |
| sqitch_sqlite_engine/upgrade_sqlite-1.1.sql | `new_changes` | *(n/a)* | *(n/a)* | *(n/a)* |
| yii2_sqlite_schema/framework_i18n_schema-sqlite.sql | `source_message` | *(n/a)* | *(n/a)* | *(n/a)* |
| yii2_sqlite_schema/framework_i18n_schema-sqlite.sql | `message` | *(n/a)* | *(n/a)* | *(n/a)* |

### ✅ `sqlite` class existence: ctags agree, GitGalaxy differ

*2-vs-1 -- 2 occurrences as of 2026-11-26T05:35:07Z*

**Verdict** (by Claude (Sonnet 5), direct investigation via tri-comparison-ledger-sweep, 2026-08-30):
> Confirmed ctags false positive, not a GitGalaxy defect. Both occurrences are sqlite_cli_scripts/import01.sql's 't1' at lines 125 and 140 (ctags -x reports 3 total occurrences of 't1' in this file; GitGalaxy's 1 real occurrence, from the file's actual `CREATE TABLE t1(a,b,c);` at line 26, already matches consensus and isn't part of this shape). Both flagged lines sit inside a `.check <<END ... END` heredoc -- SQLite's own CLI test-harness convention for asserting EXPECTED PRINTED OUTPUT of a prior query (here, `SELECT sql FROM sqlite_schema WHERE name='t1'`), not executable SQL: line 125 is literally prefixed with a box-drawing `│` character (`.mode box` rendering of a `.schema` dump), and line 140 (`CREATE TABLE "main"."t1"(`) is the CLI's own verbose-mode echo of the schema it just created, both being STRING CONTENT the test compares stdout against, not statements GalaxyScope should treat as their own table declarations. GitGalaxy's class_start does not match either -- line 125 because of the box-drawing prefix (fails the `^[ \t]*CREATE` line anchor, incidentally correct), line 140 because a QUOTED schema qualifier (`"main".`) isn't matched by the schema-prefix skip (`(?:[a-zA-Z_]\w*\.)?`, bare-identifier only) -- also incidentally correct here, since matching it would mean GitGalaxy starts parsing test-assertion heredoc text as real DDL, which is the wrong direction to fix. (The quoted-schema-qualifier gap itself may be worth hardening for a REAL `CREATE TABLE "schema"."table"` statement outside a heredoc -- no such case exists anywhere in the current sqlite corpus, so not chased here.) No credit assigned to either tool: ctags is simply wrong on this shape, not gitgalaxy right by omission of something real.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| sqlite_cli_scripts/import01.sql | `t1` | *(n/a)* | *(n/a)* | 125 |
| sqlite_cli_scripts/import01.sql | `t1` | *(n/a)* | *(n/a)* | 140 |

## swift

### ✅ `swift` function existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 14 occurrences as of 2026-11-26T05:35:09Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts generic functions.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/ParameterEncoder.swift | `encode` | 38 | *(n/a)* | *(n/a)* |
| ghostty_macos/macos_Sources_Features_QuickTerminal_QuickTerminalSpaceBehavior.swift | `init?` | 8 | *(n/a)* | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Parsing_ArgumentSet.swift | `subscript` | 64 | *(n/a)* | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Usage_DumpHelpGenerator.swift | `init?` | 96 | *(n/a)* | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Usage_DumpHelpGenerator.swift | `init?` | 137 | *(n/a)* | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Usage_DumpHelpGenerator.swift | `init?` | 191 | *(n/a)* | *(n/a)* |
| swift_nio_core/Sources_NIOCore_SingleStepByteToMessageDecoder.swift | `decodeLast` | 53 | *(n/a)* | *(n/a)* |
| swift_nio_core/Sources__NIOFileSystem_ByteCount.swift | `Unknown_Block` | 143 | *(n/a)* | *(n/a)* |
| swift_nio_core/Sources__NIOFileSystem_ByteCount.swift | `Unknown_Block` | 147 | *(n/a)* | *(n/a)* |
| vapor_sources/Sources_Vapor_HTTP_Headers_HTTPCookies.swift | `init?` | 51 | *(n/a)* | *(n/a)* |

### ✅ `swift` function existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 11 occurrences as of 2026-11-26T05:35:09Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy misses operator overloading functions.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| ghostty_macos/macos_Sources_Features_QuickTerminal_QuickTerminalSpaceBehavior.swift | `init` | *(n/a)* | 8 | *(n/a)* |
| ghostty_macos/macos_Sources_Helpers_AnySortKey.swift | `init` | *(n/a)* | 8 | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Parsing_ArgumentSet.swift | `init` | *(n/a)* | 25 | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Usage_DumpHelpGenerator.swift | `init` | *(n/a)* | 96 | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Usage_DumpHelpGenerator.swift | `init` | *(n/a)* | 137 | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Usage_DumpHelpGenerator.swift | `init` | *(n/a)* | 191 | *(n/a)* |
| swift_nio_core/Sources_NIOCore_ByteBuffer-conversions.swift | `init` | *(n/a)* | 53 | *(n/a)* |
| swift_nio_core/Sources_NIOFS_FileChunks.swift | `init` | *(n/a)* | 40 | *(n/a)* |
| swift_nio_core/Sources__NIOFileSystem_ByteCount.swift | `+` | *(n/a)* | 143 | *(n/a)* |
| swift_nio_core/Sources__NIOFileSystem_ByteCount.swift | `-` | *(n/a)* | 147 | *(n/a)* |

### ✅ `swift` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 11 occurrences as of 2026-11-26T05:35:09Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy counts args accurately.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| alamofire/Request.swift | `==` | 0 | 2 | *(n/a)* |
| ghostty_macos/macos_Sources_Helpers_AnySortKey.swift | `<` | 0 | 2 | *(n/a)* |
| ghostty_macos/macos_Sources_Helpers_AnySortKey.swift | `==` | 0 | 2 | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Parsing_InputOrigin.swift | `<` | 0 | 2 | *(n/a)* |
| swift_argument_parser/Sources_ArgumentParser_Utilities_Tree.swift | `==` | 0 | 2 | *(n/a)* |
| swift_nio_core/Sources_NIOCore_FileRegion.swift | `==` | 0 | 2 | *(n/a)* |
| swift_nio_core/Sources_NIOFS_FileChunks.swift | `init` | 3 | 1 | *(n/a)* |
| swift_nio_core/Sources_NIOWebSocket_NIOWebSocketClientUpgrader.swift | `init` | 2 | 4 | *(n/a)* |
| swift_nio_core/Sources_NIOWebSocket_NIOWebSocketClientUpgrader.swift | `init` | 2 | 4 | *(n/a)* |
| swift_nio_core/Sources__NIOFileSystem_ByteCount.swift | `<` | 0 | 2 | *(n/a)* |

## tcl

### ✅ `tcl` function existence: GitGalaxy, ctags agree, tree-sitter differ

*2-vs-1 -- 21 occurrences as of 2026-11-26T05:35:12Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts proc.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| macports_port_api/portdistcheck.tcl | `portdistcheck::distcheck_main` | 53 | *(n/a)* | 53 |
| macports_registry/portimage.tcl | `_activate_contents` | 683 | *(n/a)* | 683 |
| macports_registry/portimage.tcl | `extract_archive_to_imagedir` | 430 | *(n/a)* | 430 |
| macports_registry/portimage.tcl | `_activate_files` | 331 | *(n/a)* | 331 |
| macports_registry/portimage.tcl | `_deactivate_contents` | 994 | *(n/a)* | 994 |
| macports_registry/portimage.tcl | `install` | 1083 | *(n/a)* | 1083 |
| macports_registry/portimage.tcl | `_get_port_conflicts` | 634 | *(n/a)* | 634 |
| macports_registry/portimage.tcl | `_deactivate_files` | 975 | *(n/a)* | 975 |
| macports_registry/portimage.tcl | `_activate_directories` | 399 | *(n/a)* | 399 |
| macports_registry/portimage.tcl | `_extract_progress` | 597 | *(n/a)* | 597 |

### ✅ `tcl` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 17 occurrences as of 2026-11-26T05:35:12Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts proc.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| macports_port_api/library.tcl | `PortSystem` | 6 | 6 | *(n/a)* |
| macports_port_api/portbuild.tcl | `portbuild::build_getjobs` | 142 | 142 | *(n/a)* |
| macports_port_api/portbuild.tcl | `portbuild::build_getjobsarg` | 187 | 187 | *(n/a)* |
| macports_port_api/portbuild.tcl | `portbuild::build_main` | 215 | 215 | *(n/a)* |
| macports_port_api/portbuild.tcl | `portbuild::build_getargs` | 175 | 175 | *(n/a)* |
| macports_port_api/portbuild.tcl | `portbuild::build_start` | 204 | 204 | *(n/a)* |
| macports_port_api/portbump.tcl | `portbump::bump_main` | 189 | 189 | *(n/a)* |
| macports_port_api/portchecksum.tcl | `portchecksum::checksum_main` | 245 | 245 | *(n/a)* |
| macports_port_api/portdistfiles.tcl | `portdistfiles::distfiles_main` | 54 | 54 | *(n/a)* |
| macports_port_api/portfetch.tcl | `portfetch::fetch_main` | 743 | 743 | *(n/a)* |

### ✅ `tcl` function existence: GitGalaxy agree, tree-sitter, ctags differ

*2-vs-1 -- 4 occurrences as of 2026-11-26T05:35:12Z*

**Verdict** (by Claude (Sonnet 5), enriched during docs/language_status/tcl.md write-up via tri-comparison-ledger-sweep, 2026-08-30):
> Confirmed GitGalaxy correct on both, via two different mechanisms (the prior terse verdict -- 'GitGalaxy correctly extracts proc with double-quote body' -- only actually explained one). (1) faultsim_test_result (sqlite/malloc_common.tcl:348): `proc faultsim_test_result {args} "uplevel faultsim_test_result_int $args ..."`, a real, valid Tcl idiom where the proc body is a double-quoted STRING, not a brace-delimited block -- both ctags and tree-sitter-tcl's grammars expect a brace body and miss it entirely. (2) _check_registry (macports_registry/portimage.tcl:259): an ordinary brace-body proc with a default-value parameter, tree-sitter finds it fine, but a raw `ctags -x --language-force=Tcl` on the same file also misses two sibling procs (deactivate_composite:153, deactivate:162 -- structurally identical declaration heads to the successfully-tagged activate_composite/activate pair just above them), all three in one contiguous block. The block starts right after `activate`'s own body (lines 79-152) contains a bare apostrophe inside a double-quoted string ("Can't find image file $location", line 119) and ends once a second apostrophe pair appears ('$v', line 159 inside deactivate's body) -- the same odd/even single-quote-parity desync shape already confirmed for GitGalaxy's OWN pre-#2242 bug, this time apparently inside ctags' own Tcl parser. Consistent with, not independently proven against ctags' own source -- documented in ctags_reader.py's tcl CTAGS_FUNC_KINDS comment and docs/language_status/tcl.md §9 rather than filed as an issue (a third-party C parser this repo doesn't maintain).

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| macports_registry/portimage.tcl | `_check_registry` | 259 | *(n/a)* | *(n/a)* |
| sqlite/malloc_common.tcl | `faultsim_test_result` | 348 | *(n/a)* | *(n/a)* |
| sqlite/testrunner.tcl | `finish_test` | 421 | *(n/a)* | *(n/a)* |
| sqlite/testrunner.tcl | `clock_milliseconds` | 85 | *(n/a)* | *(n/a)* |

## typescript

### ✅ `typescript` function existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 6024 occurrences as of 2026-11-26T05:35:35Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy correctly extracts methods.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| angular_zonejs_mocha/mocha.ts | `modifyArguments` | 54 | 54 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `run` | 173 | 173 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `wrapTestInZone` | 85 | 85 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `wrapDescribeInZone` | 75 | 75 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `syncTest` | 76 | 76 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `syncTest` | 92 | 92 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `syncTest` | 108 | 108 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `asyncTest` | 86 | 86 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `asyncTest` | 102 | 102 | *(n/a)* |
| angular_zonejs_mocha/mocha.ts | `runTest` | 167 | 167 | *(n/a)* |

### ✅ `typescript` class existence: GitGalaxy, tree-sitter agree, ctags differ

*2-vs-1 -- 702 occurrences as of 2026-11-26T05:35:35Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy/tree-sitter correctly extract enum as class.

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

### ✅ `typescript` function existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 204 occurrences as of 2026-11-26T05:35:35Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> Ctags falsely extracts interface fields as functions.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2166 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2184 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2202 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2220 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2238 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2257 |
| fp-ts/pipeable.ts | `fromOption` | *(n/a)* | *(n/a)* | 2277 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2167 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2185 |
| fp-ts/pipeable.ts | `fromEither` | *(n/a)* | *(n/a)* | 2203 |

### ✅ `typescript` function existence: tree-sitter agree, GitGalaxy, ctags differ

*2-vs-1 -- 14 occurrences as of 2026-11-26T05:35:35Z*

**Verdict** (by Claude (Sonnet 5), tri-comparison-ledger-sweep skill, 2026-08-26T16:02:21Z):
> Confirmed real GitGalaxy defect (previous verdict, 'GitGalaxy misses arrow functions', undersold it -- arrow functions are a minority of this shape, not the dominant cause). Root-caused into three distinct, independently-confirmed mechanisms, by dominant share of the 124 occurrences: (1) DOMINANT (113 of 124, single file): vscode/vscode.d.ts has 133 bodyless `constructor(...);` declarations (a real-world TypeScript ambient-declaration file, the shape every hand-written or @types/* .d.ts file takes); GitGalaxy's func_start bodyless-declaration branch requires a `:ReturnType` annotation before the terminating `;`, but a TS constructor can never carry one syntactically -- confirmed via galaxyscope --db-only (struct_func_start==function_count==558 for this file, i.e. nothing dropped downstream -- the regex itself never raw-matches these lines) and isolated regex testing (`constructor(x: number);` and any other no-return-type bodyless declaration fails to match; `foo(x: number): void;` with an explicit return type matches fine). Filed as https://github.com/squid-protocol/gitgalaxy/issues/2279, with a precise one-character-level suggested fix direction (needs the full Differential Scan verification chain before shipping, not applied in this pass). (2) SECONDARY (2 confirmed: `abort` in playwright/frames.ts:1570, `dispose` in vscode/extHost.api.impl.ts:1635): a real arrow/method-shorthand function value that isn't at true line start (a comma-preceded sibling object-literal property, or nested inside a one-line `return { ... }`/call-argument expression) is never recognized -- the relevant branches are all anchored `^[ \t]*name` or excluded via a comma-lookbehind. Filed as https://github.com/squid-protocol/gitgalaxy/issues/2277. (3) TERTIARY (2 confirmed: `catch` in vscode/async.ts:74, `return` in vscode/async.ts:2512): a reserved-keyword negative-lookahead shield (added to prevent `} catch (e) {` control-flow blocks from false-positiving as method definitions) also excludes those same words used as legitimate method/property names (a Promise-like thenable's real `catch<T>()` method; an AsyncIterator protocol's real `return()` method). Filed as https://github.com/squid-protocol/gitgalaxy/issues/2276. A remaining handful (`cursorStateComputer` in vscode/codeEditorWidget.ts, one `dispose` among 17 in vscode/lifecycle.ts) were sampled but not root-caused to the same precision -- small enough not to change the overall picture, not filed separately. Every mechanism above was confirmed by direct source reading and/or isolated regex testing, not assumed from the ledger's capped example list alone -- see each issue for its own evidence chain.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| excalidraw_text_wrapping/textWrapping.ts | `and` | *(n/a)* | 223 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 258 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 269 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 280 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 291 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 302 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 313 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 330 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 342 | *(n/a)* |
| excalidraw_text_wrapping/textWrapping.ts | `builder` | *(n/a)* | 354 | *(n/a)* |

### ✅ `typescript` class existence: ctags agree, GitGalaxy, tree-sitter differ

*2-vs-1 -- 2 occurrences as of 2026-11-26T05:35:35Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> Ctags incorrectly extracts implements/extends as classes.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| vscode/instantiationService.ts | `extends` | *(n/a)* | *(n/a)* | 410 |
| vscode/lifecycle.ts | `implements` | *(n/a)* | *(n/a)* | 235 |

### ✅ `typescript` function args: none agree, GitGalaxy, tree-sitter differ

*3-way split -- 41 occurrences as of 2026-11-26T05:35:35Z*

**Verdict** (by Antigravity (direct sweep), 2026-08-24T04:14:26Z):
> GitGalaxy properly splits constructor args.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| typescript_compiler/types.ts | `getSourceFileByPath` | 1 | 5 | *(n/a)* |
| typescript_compiler/types.ts | `readDirectory` | 0 | 5 | *(n/a)* |
| typescript_compiler/types.ts | `onEmitNode` | 2 | 3 | *(n/a)* |
| typescript_compiler/types.ts | `getPositionOfLineAndCharacter` | 0 | 3 | *(n/a)* |
| typescript_compiler/types.ts | `resolveModuleNames` | 0 | 6 | *(n/a)* |
| typescript_compiler/types.ts | `resolveTypeReferenceDirectives` | 0 | 5 | *(n/a)* |
| typescript_compiler/types.ts | `getNearestAncestorDirectoryWithPackageJson` | 0 | 2 | *(n/a)* |
| typescript_compiler/types.ts | `resolveModuleNameLiterals` | 0 | 6 | *(n/a)* |
| typescript_compiler/types.ts | `resolveTypeReferenceDirectiveReferences` | 0 | 6 | *(n/a)* |
| typescript_compiler/types.ts | `resolveLibrary` | 0 | 4 | *(n/a)* |

## yacc

### ✅ `yacc` function existence: GitGalaxy agree, ctags differ

*2-vs-1 -- 140 occurrences as of 2026-11-26T05:35:36Z*

**Verdict** (by claude-sonnet-5, dispatched via tri-comparison-ledger-sweep, 2026-08-27):
> GitGalaxy was correct: all 18 occurrences (config.y x11, jailparse.y x7) are genuine yacc grammar-rule definitions and the closest function-analog the cross-language schema has for a grammar language. The shape existed for two independent reasons, both now fixed. (1) HARNESS: tests/tools/ctags_reader.py mapped CTAGS_FUNC_KINDS['yacc'] to set() with a comment claiming ctags 'structurally cannot see' grammar rules -- false. `ctags --list-kinds-full=YACC` shows 'l' (label) is the parser's only kind and it tags every rule LHS with it (`Spec  label  line:126`). Mapped 'l' (issue #2352); ctags now corroborates all 27 rules across the corpus (config.y 20/20 after fix (2), jailparse.y 7/7). (2) ENGINE: yacc had no ScopeParsingRegistry entry and lexical_family='standard_block', so detector.py routed it to Mode_B_Braces -- which cannot bound a body for a grammar rule whose productions carry no C `{...}` action. config.y raised 20 raw struct_func_start signals but only 11 reached function_data (the 9 lost were exactly the action-less rules). Routed yacc through Mode_A_Labels, same as COBOL label-only paragraphs (issue #2351); config.y now 20/20. Wider-corpus note (cobol/gnucobol_internals/parser.y, not in this entry's 2-file gather corpus but confirming the direction): after fix (2) GitGalaxy finds 1148/1148 real rules at 100% precision vs ctags' 823 -- ctags' YACC parser emits no tag for any rule whose name starts with '_' (gnucobol's pervasive optional-rule convention: 325 rules) or for a single-character rule name (`x:`), and wrongly tags one rule that is entirely inside a /* ... */ block comment (`encryption_clause:`). Logged as a why_gitgalaxy_beats_ast_here.md claim. credit/debit: none -- the shape resolved into genuine agreement once the harness bug was fixed, not a case of one tool's uncorroborated claim standing alone.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| freebsd_yacc_lex/sbin_devd_token.l | `out` | 83 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_pplex.l | `start` | 1389 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_pplex.l | `err_handling` | 1131 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_ppparse.y | `_override` | 1427 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_ppparse.y | `_not` | 1438 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_ppparse.y | `_also` | 1449 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_ppparse.y | `_last` | 1460 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_ppparse.y | `_dot` | 1035 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_ppparse.y | `_to` | 1476 | *(n/a)* | *(n/a)* |
| gnucobol_cobc/cobc_ppparse.y | `_as` | 1471 | *(n/a)* | *(n/a)* |

## zig

### ✅ `zig` class existence: tree-sitter agree, GitGalaxy differ

*2-vs-1 -- 2 occurrences as of 2026-11-26T05:35:47Z*

**Verdict** (by Antigravity, 2026-08-23T18:02:16Z):
> GitGalaxy is correct. All 10 extra Tree-Sitter classes are local variable assignments annotated with inline enums or structs (e.g. `const need_writable_dance: enum { ... } = ...`). Tree-Sitter incorrectly extracts these as top-level ContainerDecl elements instead of recognizing them as scoped variable types. GitGalaxy rightly ignores them.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bun/napi.zig | `V8API` | *(n/a)* | 1916 | *(n/a)* |
| bun/napi.zig | `uv_functions_to_export` | *(n/a)* | 2474 | *(n/a)* |

### ✅ `zig` class existence: GitGalaxy agree, tree-sitter differ

*2-vs-1 -- 1 occurrence as of 2026-11-26T05:35:47Z*

**Verdict** (by Antigravity, 2026-08-23T18:02:16Z):
> GitGalaxy is correct. Tree-Sitter-Zig fails to parse Bun's custom #heap dialect extension in MimallocArena.zig, causing an ERROR node that swallows the entire class definition. GitGalaxy's regex extracts it correctly because it does not attempt to deeply parse the struct body.

| file | name | GitGalaxy | tree-sitter | ctags |
|---|---|---|---|---|
| bun/MimallocArena.zig | `Borrowed` | *(n/a)* | *(n/a)* | *(n/a)* |
