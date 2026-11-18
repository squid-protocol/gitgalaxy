---
description: "> **Topic:** What tends to follow a change to a function? A plain-language account of the repair radius: where later fixes land, what they change and how that depends on the size of the change. Measured on 3,000 to 24,000 named cause-and-fix pairs in each of the Linux kernel, DPDK and Mesa, and on curl, OpenSSL and FreeBSD; also around added and deleted functions, as a ranking test against size, and as a test of whether a change will need a fix."
---
# Repair Radius: What Tends to Follow a Change

> **Status:** exploratory research, one author, not peer reviewed. Every number is an association measured on C code in six open-source projects. The scripts, outputs and a prediction written before each run are in the temporal-crucible repository (`docs/sensor-overhaul/sensors/ripple_radius.md`); several predictions failed, and the failures are recorded there. This page replaces the headline of [Blast Radius of a Change](08-28-blast-radius.md) with measurements on verified functions and more repositories.
>
> **Summary:** When a function is changed and a bug caused by that change is later fixed, the fix is most often in the same function, then in a close neighbour in the call graph, and it often reuses a name the change touched. Small changes are repaired once, close by; big changes are repaired again and again, scattered. The same pattern holds around functions that are added or deleted. Given a change that is later fixed, ranking by file and call distance finds the repaired function in its top 20 of tens of thousands for about half of the cases (size alone: 0.2%); whether a change will need a fix at all is mostly a matter of its size. This appears to be useful as a checklist when changing a function, not as a prediction.

<img src="../media/repair-radius.gif" width="760" alt="Four functions A, B, C and D: if B changes, the fix tends to be in B, then A or C, with a new check in callers and a shared name in D; small changes stay close, big ones scatter">

## An example with four functions
- **B** reads a setting and returns a value. **A** calls B. B calls **C**. **D**, in another file, never calls anything here but uses the same setting, `timeout`.
- **Day 1:** a developer changes B so that it returns an error code when the setting is missing (it used to return zero).
- **Weeks or months later** a bug caused by that change is found. What tends to follow:

| If | then, typically | numbers |
|---|---|---|
| a bug caused by the change turns up | the fix is in **B itself** | 43% to 72% of the time, depending on the project |
| the fix is not in B | it is in a **close neighbour** (A or C) more often than in a random function of the same size in the same file | 1.6 to 2.2 times as often |
| B's result or arguments changed | **callers like A** add a check on the result | 8 to 14 times as often as fixes inside B; changed call arguments about 1.6 to 1.7 times as often |
| other code uses the same name as the change (`timeout`) | it can need a fix **with no call link at all** (D) | 45% of such fixes share a specific name with the change, 6.7 times as often as fixes after unrelated changes in the same directory |
| the change is small (under 20 lines) | fixes stay close, and usually there is one | 14% of the changes that were fixed needed two or more fixes |
| the change is big (500 or more lines) | fixes **scatter and keep coming** | half to three quarters needed two or more fixes (kernel and DPDK 77%, Mesa 49%); 4 to 5 fixes on average in the kernel and DPDK |
| a cause checked a name in a condition | the repair adds or changes a guard on it | 53% against 27% otherwise |

## How it was measured
1. **Named causes.** A fix commit that names the commit that caused the bug: the `Fixes: <sha>` line of the kernel, DPDK, Mesa and OpenSSL, curl's references. For each pair, the functions each commit changed.
2. **Verified functions.** The function named by a diff header is often not the function that changed (a table or macro after a function is credited to the function above it). Each named function is compared with its first parent with tree-sitter and kept only if its text changed: 13% of the named functions were not edited. Removing them raised the radius by about 8%.
3. **A baseline.** For each fixed function outside the changed set, the comparison is with other functions from the same file, of similar size, outside the changed set. The "radius" is the observed share within 1 or 2 calls divided by the share expected from that baseline.
4. **Checks that could have removed it.** Matching the baseline on how recently and how often a function was changed (no change: 1.55 against 1.57 in DPDK); removing functions that changed together with the cause before (it grew, to 1.71); the size of the change; the same author or not (kernel).

## What was found
| | finding | numbers (verified C functions) |
|---|---|---|
| Radius | within 2 calls of a changed function, against the same-file baseline | kernel 2.15, FreeBSD 2.17 (39 pairs), Mesa 1.78, OpenSSL 1.72, curl 1.65, DPDK 1.57 |
| Same function | share of pairs where the fix is in a function the cause changed | curl and FreeBSD 72%, kernel 59%, Mesa 57%, DPDK 50%, OpenSSL 43% |
| Size | the radius shrinks with the size of the change | under 20 lines to 500 or more: kernel 3.06 to 1.31, Mesa 2.16 to 1.34, DPDK 2.09 to 1.23 |
| Direction | for fixes in a different file, callers beat callees | callers against callees: kernel 4.43 against 2.74, Mesa 4.37 against 2.28, DPDK 2.87 against 1.50, curl 7.9 against 1.5 |
| Callers adapt | repairs in a caller change the call's arguments, and add an `if` that tests the changed function | arguments changed in 19% to 27% of caller repairs against 11% to 17% in the same function; an added `if` testing the changed function 8 to 14 times as often |
| Shared names | the repair uses the same specific identifier as the cause (field, variable, constant, called function) | 80% in the same function, 57% to 73% in neighbours, **45% where no call path exists**; mostly data (79% fields, variables, macros, types) |
| What the cause did | the shared name was mostly tested or used, rarely defined | checked in a condition 31%, newly used 31%, use changed 20%, defined 12%, redefined or removed 3% |
| The repair mirrors the cause | same kind of edit | after a check: guard or condition 53% against 27%; after a changed use: changed arguments 25% against 17% |
| Interfaces | a cause that changes a definition in a header | 37% of causes; their repairs land in another file or far in the same file 1.26 times as often |
| Repeated repairs | the chance of another repair rises with each repair | kernel 29% after one, 66% after five; DPDK 39% to 70%; Mesa 19% to 57% |
| What makes a change need repeated repairs | size, not shape or author | two or more fixes: under 20 lines 14%, 500 or more lines 77% (kernel, DPDK), 49% (Mesa); author's earlier experience little |
| Time | no wave spreading outward | the radius weakens only slightly with lag: kernel 2.13 to 1.93, DPDK 1.48 to 1.39, Mesa clearer, 1.97 to 1.55 |

## Added and deleted functions
Everything above is about functions a change *modified*. The same measurement around functions a change **adds** or **deletes** (DPDK and Mesa; added and deleted functions found by comparing each changed file with its parent with tree-sitter; moves and renames excluded):

| | DPDK | Mesa |
|---|---|---|
| Repairs within 2 calls of an **added** function, against the same-file baseline | **2.2** | **3.0** |
| Repairs within 2 calls of a **deleted** function (in the call graph before the commit) | **2.8 to 3.2** | **2.9 to 3.1** |
| Callers against callees, added functions | 3.5 against 1.5 | 4.9 against 1.8 |
| Callers against callees, deleted functions | 4.6 against 1.9 | 5.5 against 2.4 |
| The fix edits the new function itself | 57% | 46% |
| A deleted function with 3 or more callers draws a repair in its old neighbourhood, against one with 0 or 1 callers | 48% against 27% (1.8 times), both projects pooled | |

For modified functions the same measurement gives 1.6 (DPDK) and 1.8 (Mesa), so the call graph absorbs the arrival or loss of a function at least as locally as a change to one. **The result does not depend on how renames are handled**: it moves by under 3% around added functions, and at most 10% around deleted ones, across six ways of recognising a move (none at all, three token-overlap thresholds, the engine's structural fingerprint, and a combination). Token overlap found 77% of the moves that git's own line tracking finds, with 4% false alarms; the structural fingerprint found 57%; about one move in five (a function split in two, or rewritten on the way) is found by neither.

## How good is it as a ranking?
Given a change that is later fixed, rank every function in the program (and every file) and see where the repaired one lands. A comparison with size alone, because bigger code is simply repaired more often. DPDK and Mesa for added and deleted functions; the kernel, DPDK and Mesa for modified ones.

| Ranker | Repaired function in the top 20 (of 30,000 to 110,000) | Area under the curve (AUC) |
|---|---|---|
| Random | 0.0 to 0.1% | 0.50 |
| Size alone (largest first) | **0.2 to 0.4%** | 0.74 to 0.83 |
| Call distance alone | 30% (modified), 36 to 41% (added, deleted) | 0.73 (0.66 to 0.70 for added, deleted) |
| Same file, then call distance, then size | **45%** (modified), **44 to 53%** (added, deleted) | 0.91 to 0.93 |

- **Not only size.** Among functions of the same size, call distance alone separates the repaired function with an AUC of 0.73 (modified) and 0.66 to 0.70 (added, deleted); with the file, 0.85 (modified). This is a different question from which files will have bugs: it is where a fix goes once one is needed.
- **Files.** Ranking every file in the program, a repaired file is among the top 20 for 67 to 80% of added or deleted functions (random 0.5 to 1.3%). Much of that is the change's own file; counting only repairs in **other** files, the top 20 still holds a repaired file for **39 to 50%** (random 0.5 to 1.3%, file size alone 2.5 to 5.7%), found by call distance.

## Will a change need a fix?
The reverse question, on **all** changes including those never fixed (DPDK and Mesa; label: named as the cause of a fix within two years):

- **Size predicts it** (AUC 0.77 and 0.72). Nothing known when the change is made adds to size here except the kind of change.
- **The neighbourhood does not** (+0.003 and +0.000 AUC over size and process), and neither does the author's experience or how often the touched files changed recently.
- **The kind of change adds a little** (+0.016 and +0.027 AUC), carried by added conditions; it transfers from one project to the other. But it disappears when the label does not use `Fixes:` trailers (+0.002 and +0.003), so it predicts being *named* as a cause (the bug is blamed on added lines), not that the code is fixed soon. Deleted-only changes are named about 0.3 times as often as same-size changes, partly for the same reason: a fix names the commit that added the faulty lines.

The neighbourhood is a **where** predictor, not a **whether** predictor.

## What it does not say
- **Association, not cause.** Nothing here shows why a fix lands where it does. A shared name can mean an interface changed and its users had to follow, the same hardware condition handled elsewhere, or a copied pattern.
- **It describes where, it does not predict whether.** A given change may break nothing. The radius and the ranking are measured on changes that were later fixed and whose fix names its cause, so they cannot say how likely a change is to be fixed; size is the only predictor of that found, and the small gain from the kind of change depends on how causes are labelled.
- **C only, so far.** Only `.c` and `.h` files were read; Mesa's and QEMU's C++ and Rust are outside. Other languages are being tested with a cause label that needs no trailers; until that is done nothing here is shown for them.
- **Modest effects.** 1.6 to 2.2 times a baseline for the radius, and weaker for big changes (1.2 to 1.3 at 500 lines or more), partly because a big change has a big neighbourhood.
- **Selection by habit.** Projects that write `Fixes:` lines are the ones measured; DPDK's near-mandatory trailer gives a different mix of changes from the kernel's.
- **Static calls.** Calls through function pointers are missing from the call graph, which understates the radius somewhat.
- **Closest earlier work.** Fixes following dependency links near their cause is not new: for example Wen et al., FSE 2019 (Java, the same file and statement level), and Park, Kim and Bae, EMSE 2017 (follow-up fixes and structural dependence). A literature check did not find the function-level call distance against a matched same-file baseline, the callers-versus-callees direction, the size dependence or the shared-name result, but it did not read every paper in full and found nothing is not the same as nothing exists.

## What it could mean for `gitgalaxy change`
Nothing is implemented. The measured pattern suggests a reminder under a changed function: its direct callers, whether they handle a changed result, other code using the same fields and constants, and a note that a change of several hundred lines is usually followed by repeated repairs. These would be reminders, phrased as such: the page above says what tends to follow, not what will. See [Change Report](08-26-change-report.md) for the current behaviour.
