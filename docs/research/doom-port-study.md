# DOOM port study

What the GitGalaxy engine measures across 44 DOOM ports (issue #5620), re-scanned on engine `6c7c6c1bc`. Measurements only:
no port code is reproduced, and the ports named here are those the license register marks clearly licensed
(`tests/tools/doom_speedrun/README.md`, "Licensing rule"). "DOOM" is used descriptively; this project is not affiliated
with or endorsed by id Software, ZeniMax Media or Microsoft.

## Reproduce

Every table below sits between `<!-- study:NAME begin/end -->` markers and is generated, not typed:

```bash
python tests/tools/doom_speedrun/doom_speedrun.py run --oracle --work DIR      # clone at the pinned SHAs, scan, score
sfs subway DIR/scans/SHA -o subway --reference linuxdoom --taxonomy examples/doom/subsystems.json \
    --declared-lineage examples/doom/declared_lineage.csv                       # gitgalaxy-population-analyses, writes subway.csv
python tests/tools/doom_speedrun/study_report.py --work DIR --sha 6c7c6c1bc --subway subway.csv --write
python tests/tools/doom_speedrun/study_report.py --work DIR --sha 6c7c6c1bc --subway subway.csv --check   # rc 1 when stale
```

Every table, the `sfs` one included, reads the same scans. The prose between the tables is hand-written and dated
2026-10-30; the tables are the evidence.

## Clean scan, round 2 to now

Round 2 (engine `585c243e9`) scored six checks; the call-graph check is new since. The seven checks are in the harness
README. Read the table with three cautions:

- **The call-graph check passes every port.** It failed 17 at the first scan that had it; engine fixes cleared all of
  them, the last (`doomsday`'s remaining engine-only edges) in #7019.
- **The two remaining failures are counting conventions, not engine misses.** `sqldoom` and `cssdoom` fail the
  functions check because the engine and ctags disagree on what counts as a function in those sources; #5876 ruled
  both as counting conventions, so they stay listed rather than fixed.
- **Coverage and health failures from round 2 are gone** for every port that existed then (missed files now 0
  everywhere; `doomsday` went from 993 missed files to 0). No port is `(vacuous)` any more: the scorer now recognises
  the Fortran, Crystal, F# and COBOL sources (#6705), so check 1 measures every port.

<!-- study:clean-scan begin -->

42 of 44 ports pass every scored check now; 26 of them failed at least one in round 2 (`n/a` = the port was added after round 2; `(vacuous)` = the scorer saw no first-party source files, so the pass proves nothing; `not compared` = ctags has no reading of that language; `functions in ctags languages` counts only the files the ctags check reads, so a port written in a language ctags lacks shows 0 here: its full count is in the distribution table). The call-graph check did not exist in round 2.

| port | failed checks, round 2 | failed checks, now | first-party files, now | missed files, round 2 | now | functions vs ctags %, round 2 | now | functions in ctags languages |
|---|---|---|---|---|---|---|---|---|
| linuxdoom | coverage | - | 133 | 1 | 0 | 0.0 | 0.0 | 779 |
| chocolate-doom | coverage health | - | 576 | 3 | 0 | 0.9 | 0.9 | 5168 |
| crispy-doom | coverage health | - | 632 | 6 | 0 | 0.8 | 0.8 | 5909 |
| doomgeneric | coverage | - | 192 | 1 | 0 | 0.1 | 0.1 | 1192 |
| doomretro | coverage | - | 188 | 3 | 0 | 0.0 | 0.0 | 2236 |
| prboom-plus | - | - | 286 | 0 | 0 | 2.3 | 2.3 | 2517 |
| dsda-doom | - | - | 506 | 0 | 0 | 0.4 | 0.4 | 4937 |
| woof | coverage health | - | 399 | 1 | 0 | 0.8 | 0.8 | 3783 |
| eternity | coverage health | - | 584 | 2 | 0 | -0.1 | 3.3 | 7305 |
| odamex | coverage functions | - | 590 | 3 | 0 | -3.3 | -1.9 | 8670 |
| gzdoom | coverage | - | 1567 | 4 | 0 | 0.0 | 0.5 | 18260 |
| room4doom | coverage | - | 385 | 10 | 0 | 0.7 | 0.7 | 4684 |
| gore | coverage | - | 9 | 1 | 0 | 0.0 | 8.4 | 1025 |
| managed-doom | - | - | 245 | 0 | 0 | 0.0 | -0.1 | 1300 |
| mochadoom | coverage | - | 452 | 1 | 0 | -0.2 | -0.2 | 3781 |
| rust-doom | - | - | 50 | 0 | 0 | 2.2 | 2.2 | 616 |
| doom-wasm | coverage | - | 306 | 2 | 0 | 0.7 | 0.7 | 2055 |
| fastdoom | coverage | - | 387 | 2 | 0 | 1.7 | 1.5 | 1736 |
| puredoom | coverage | - | 130 | 2 | 0 | 0.9 | 1.0 | 1560 |
| doom-ios | language | - | 304 | 0 | 0 | 1.0 | 1.0 | 1958 |
| doom3-bfg | coverage | - | 888 | 3 | 0 | -2.1 | 0.8 | 16379 |
| doom-ascii | coverage health | - | 180 | 1 | 0 | 0.0 | 0.0 | 1019 |
| srb2 | coverage | - | 422 | 1 | 0 | 2.1 | 2.5 | 6759 |
| freedoom | - | - | 13 | 0 | 0 | -0.7 | 0.0 | 119 |
| helion | coverage functions | - | 1518 | 1 | 0 | 4.0 | 3.7 | 9780 |
| doomsday | coverage functions health | - | 2552 | 993 | 0 | 16.2 | 14.0 | 25480 |
| edge-classic | coverage health | - | 388 | 3 | 0 | 0.9 | 0.8 | 4963 |
| nugget-doom | coverage health | - | 401 | 1 | 0 | 0.7 | 0.7 | 4168 |
| inter-doom | coverage | - | 475 | 7 | 0 | 0.2 | 0.2 | 6236 |
| sdl-doom | coverage | - | 182 | 2 | 0 | 0.1 | 0.1 | 1079 |
| doom3do | coverage | - | 200 | 1 | 0 | 0.0 | 0.0 | 511 |
| sqldoom | n/a | functions | 41 | n/a | 0 | n/a | 11.4 | 419 |
| doomf77 | n/a | - | 14 | n/a | 0 | n/a | not compared | 0 |
| doom-scheme | n/a | - | 74 | n/a | 0 | n/a | -1.1 | 92 |
| dartdoom | n/a | - | 92 | n/a | 0 | n/a | not compared | 0 |
| doo-cr | n/a | - | 43 | n/a | 0 | n/a | not compared | 0 |
| kocoa-doom | n/a | - | 441 | n/a | 0 | n/a | not compared | 0 |
| fsharp-doom | n/a | - | 18 | n/a | 0 | n/a | not compared | 0 |
| cssdoom | n/a | functions | 54 | n/a | 0 | n/a | 4.7 | 225 |
| doom-fx | n/a | - | 71 | n/a | 0 | n/a | -88.9 | 1 |
| fps-cob | n/a | - | 1 | n/a | 0 | n/a | not compared | 0 |
| agentic-cobol-doom-cc | n/a | - | 8 | n/a | 0 | n/a | not compared | 0 |
| agentic-cobol-doom-codex | n/a | - | 14 | n/a | 0 | n/a | 0.0 | 52 |
| mood | n/a | - | 307 | n/a | 0 | n/a | -0.4 | 1785 |

<!-- study:clean-scan end -->

## What each port says about itself

Read from each port's own README at the pinned SHA, never inferred from the code. Examples, quoted briefly:
chocolate-doom, "Accurate reproduction of the original DOS versions of the games, including bugs" (faithful);
managed-doom, "Chocolate Doom is used as the reference of compatibility tests" (compatible);
dartdoom, "A second hardware renderer draws the world as GPU geometry" (enhanced). Twelve ports state nothing, each with a recorded
reason (`fidelity_reason` in the manifest), and are reported as unstated rather than guessed.

<!-- study:fidelity begin -->

| class | original | faithful | compatible | enhanced | divergent | unstated |
|---|---|---|---|---|---|---|
| assets | - | - | freedoom | - | - | - |
| engine-port | linuxdoom | chocolate-doom, doom-scheme, sqldoom | crispy-doom, doomf77, gore, inter-doom, managed-doom, odamex, prboom-plus | dartdoom, doomretro, doomsday, dsda-doom, edge-classic, eternity, fastdoom, nugget-doom, puredoom, woof | doo-cr, doom3do, srb2 | doom-ascii, doom-ios, doom-wasm, doomgeneric, gzdoom, kocoa-doom, mochadoom, mood, sdl-doom |
| raycaster | - | - | - | - | agentic-cobol-doom-cc, agentic-cobol-doom-codex, fps-cob | - |
| reimplementation | - | - | room4doom | - | cssdoom, helion, rust-doom | doom-fx, fsharp-doom |
| separate-engine | - | - | - | - | - | doom3-bfg |
| **ports** | 1 | 3 | 9 | 10 | 9 | 12 |

<!-- study:fidelity end -->

## Survival of linuxdoom's functions

A function survives by **name**, **exact** body, **near** (similarity >= 0.9) or **derived** (>= 0.6). Name survival
is the lineage claim for a rewrite; exact survival says how much was left untouched.

- chocolate-doom keeps 86.7% of linuxdoom's function names and 34.9% exact bodies; doomretro keeps 69.0% of names and
  0.2% exact bodies: same names, rewritten bodies.
- mood keeps 100% of names and 99.7% of exact bodies: a near-verbatim copy.
- `exact vs parent` is the exact-body points gained or lost against the port's declared parent (linuxdoom counts as 100).

<!-- study:lineage begin -->

| port | class | stated fidelity | parent | name % | exact % | near % | derived % | exact vs parent |
|---|---|---|---|---|---|---|---|---|
| mood | engine-port | unstated | - | 100.0 | 99.7 | 100.0 | 100.0 | - |
| doom3-bfg | separate-engine | unstated | - | 91.8 | 12.8 | 35.8 | 78.9 | - |
| puredoom | engine-port | enhanced | - | 91.1 | 44.6 | 76.4 | 87.6 | - |
| doo-cr | engine-port | divergent | - | 88.5 | 0.0 | 0.0 | 0.5 | - |
| chocolate-doom | engine-port | faithful | linuxdoom | 86.7 | 34.9 | 64.5 | 77.5 | -65.1 |
| crispy-doom | engine-port | compatible | chocolate-doom | 86.7 | 21.0 | 48.6 | 72.2 | -13.9 |
| doom-ascii | engine-port | unstated | chocolate-doom | 85.8 | 38.1 | 65.4 | 77.2 | 3.2 |
| sdl-doom | engine-port | unstated | linuxdoom | 85.8 | 39.4 | 65.4 | 77.3 | -60.6 |
| doomgeneric | engine-port | unstated | chocolate-doom | 85.5 | 39.4 | 65.4 | 77.2 | 4.5 |
| doom-wasm | engine-port | unstated | chocolate-doom | 85.5 | 34.0 | 62.5 | 76.4 | -0.9 |
| gore | engine-port | compatible | - | 81.4 | 0.0 | 0.2 | 24.8 | - |
| prboom-plus | engine-port | compatible | - | 80.5 | 8.8 | 20.8 | 49.1 | - |
| doom-ios | engine-port | unstated | - | 80.1 | 10.7 | 27.3 | 56.2 | - |
| inter-doom | engine-port | compatible | crispy-doom | 76.1 | 14.5 | 30.8 | 52.7 | -6.5 |
| fastdoom | engine-port | enhanced | linuxdoom | 72.4 | 6.8 | 24.2 | 53.9 | -93.2 |
| dsda-doom | engine-port | enhanced | prboom-plus | 72.2 | 3.2 | 10.0 | 34.3 | -5.6 |
| nugget-doom | engine-port | enhanced | woof | 70.5 | 2.9 | 10.9 | 34.4 | 0.3 |
| doomretro | engine-port | enhanced | chocolate-doom | 69.0 | 0.2 | 2.1 | 20.2 | -34.7 |
| doom-scheme | engine-port | faithful | - | 68.9 | 0.0 | 0.0 | 0.2 | - |
| eternity | engine-port | enhanced | - | 66.3 | 0.8 | 5.3 | 23.7 | - |
| odamex | engine-port | compatible | - | 66.0 | 1.2 | 4.7 | 22.2 | - |
| woof | engine-port | enhanced | - | 49.1 | 2.6 | 9.1 | 25.8 | - |
| dartdoom | engine-port | enhanced | - | 43.5 | 0.0 | 0.5 | 22.2 | - |
| srb2 | engine-port | divergent | - | 43.4 | 1.4 | 4.8 | 14.2 | - |
| gzdoom | engine-port | unstated | - | 32.0 | 0.2 | 0.5 | 2.1 | - |
| doomsday | engine-port | enhanced | - | 29.9 | 0.6 | 3.2 | 11.2 | - |
| mochadoom | engine-port | unstated | - | 29.3 | 5.6 | 5.9 | 17.1 | - |
| kocoa-doom | engine-port | unstated | - | 23.1 | 0.0 | 0.0 | 5.3 | - |
| doom3do | engine-port | divergent | - | 18.9 | 0.0 | 0.5 | 10.0 | - |
| room4doom | reimplementation | compatible | - | 13.7 | 0.0 | 0.0 | 0.5 | - |
| helion | reimplementation | divergent | - | 9.5 | 0.0 | 0.0 | 0.2 | - |
| edge-classic | engine-port | enhanced | - | 4.4 | 0.0 | 0.0 | 0.2 | - |
| doomf77 | engine-port | compatible | - | 1.1 | 0.0 | 0.0 | 0.0 | - |
| managed-doom | engine-port | compatible | - | 0.9 | 0.0 | 0.0 | 0.2 | - |
| freedoom | assets | compatible | - | 0.9 | 0.0 | 0.0 | 0.0 | - |
| agentic-cobol-doom-codex | raycaster | divergent | - | 0.8 | 0.0 | 0.0 | 0.0 | - |
| rust-doom | reimplementation | divergent | - | 0.6 | 0.0 | 0.0 | 0.0 | - |
| sqldoom | engine-port | faithful | - | 0.6 | 0.0 | 0.0 | 0.0 | - |
| fsharp-doom | reimplementation | unstated | - | 0.5 | 0.0 | 0.0 | 0.0 | - |
| fps-cob | raycaster | divergent | - | 0.5 | 0.0 | 0.0 | 0.0 | - |
| doom-fx | reimplementation | unstated | - | 0.3 | 0.0 | 0.0 | 0.0 | - |
| agentic-cobol-doom-cc | raycaster | divergent | - | 0.3 | 0.0 | 0.0 | 0.0 | - |
| cssdoom | reimplementation | divergent | - | 0.0 | 0.0 | 0.0 | 0.0 | - |

<!-- study:lineage end -->

## Per-function distributions

`dist` is the mean normalised Wasserstein distance between a port's per-function distributions (complexity, LOC, fan-out,
token mass, arguments) and linuxdoom's. It is a shape comparison, not a correctness claim: it runs from 0.07
(puredoom) to 0.61 (gzdoom). linuxdoom itself sits near the 91st percentile of the ports for complexity and for LOC
(the 1993 original has longer, branchier functions than the median port). Vendored code is excluded (#6749).

Ports in Java, Kotlin, Rust, C#, Crystal and assembly show a median complexity of 0, against 2 for most C ports. The
baseline is the same (a branchless function is 0 in every language; 26% of linuxdoom's are); the difference is method
size. 34% of mochadoom's functions, 43% of kocoa-doom's and 38% of rust-doom's are 3 lines or shorter, against under 2%
in linuxdoom and chocolate-doom. On the landmark functions below the same Java and Kotlin ports read 0.71 and 0.86 of
linuxdoom's complexity, so the low medians describe how the code is split, not missing branches.

<!-- study:distribution begin -->

| port | language | stated fidelity | functions | complexity med | % complexity >= 10 | LOC med | dist |
|---|---|---|---|---|---|---|---|
| linuxdoom | c | original | 779 | 3 | 19.8 | 21 | 0.00 |
| puredoom | c | enhanced | 1560 | 2 | 17.7 | 18 | 0.07 |
| doom-ascii | c | unstated | 1019 | 2 | 13.8 | 20 | 0.08 |
| sdl-doom | c | unstated | 1079 | 2 | 13.2 | 21 | 0.09 |
| doomgeneric | c | unstated | 1192 | 2 | 12.6 | 20 | 0.10 |
| doom3do | c | divergent | 537 | 2 | 16.6 | 16 | 0.11 |
| chocolate-doom | c | faithful | 5168 | 2 | 13.2 | 19 | 0.13 |
| mood | c | unstated | 1839 | 2 | 16.8 | 20 | 0.13 |
| crispy-doom | c | compatible | 5909 | 2 | 14.9 | 19 | 0.13 |
| prboom-plus | c | compatible | 2517 | 2 | 18.9 | 16 | 0.15 |
| doom-wasm | c | unstated | 2055 | 2 | 10.5 | 19 | 0.15 |
| doom-ios | c | unstated | 1958 | 2 | 16.9 | 14 | 0.16 |
| inter-doom | c | compatible | 6236 | 2 | 15.7 | 16 | 0.16 |
| cssdoom | javascript | divergent | 225 | 2 | 18.2 | 12 | 0.17 |
| dartdoom | dart | enhanced | 865 | 2 | 14.3 | 10 | 0.17 |
| managed-doom | csharp | compatible | 1300 | 1 | 9.5 | 15 | 0.18 |
| woof | c | enhanced | 3795 | 2 | 13.6 | 16 | 0.19 |
| eternity | cpp | enhanced | 7308 | 1 | 13.2 | 12 | 0.21 |
| nugget-doom | c | enhanced | 4180 | 2 | 14.7 | 16 | 0.22 |
| agentic-cobol-doom-codex | cobol | divergent | 162 | 2 | 8.0 | 10 | 0.23 |
| room4doom | rust | compatible | 4684 | 0 | 6.9 | 11 | 0.24 |
| doom-scheme | scheme | faithful | 1034 | 1 | 9.1 | 7 | 0.25 |
| dsda-doom | c | enhanced | 4937 | 2 | 13.5 | 13 | 0.25 |
| sqldoom | python | faithful | 419 | 2 | 14.6 | 9 | 0.25 |
| agentic-cobol-doom-cc | cobol | divergent | 45 | 4 | 17.8 | 25 | 0.26 |
| doomf77 | fortran | compatible | 146 | 6 | 37.7 | 24 | 0.28 |
| fastdoom | c | enhanced | 2135 | 1 | 12.9 | 20 | 0.29 |
| edge-classic | cpp | enhanced | 4963 | 2 | 14.0 | 13 | 0.34 |
| fsharp-doom | fsharp | unstated | 53 | 1 | 9.4 | 12 | 0.34 |
| doom3-bfg | cpp | unstated | 16379 | 1 | 9.8 | 8 | 0.35 |
| fps-cob | cobol | divergent | 54 | 6 | 33.3 | 32 | 0.35 |
| kocoa-doom | kotlin | unstated | 3565 | 0 | 5.5 | 5 | 0.36 |
| odamex | cpp | compatible | 8670 | 1 | 9.4 | 8 | 0.36 |
| mochadoom | java | unstated | 3781 | 0 | 5.3 | 5 | 0.36 |
| srb2 | c | divergent | 6759 | 2 | 20.4 | 16 | 0.36 |
| doo-cr | crystal | divergent | 1509 | 0 | 7.5 | 3 | 0.37 |
| rust-doom | rust | divergent | 616 | 0 | 4.4 | 5 | 0.38 |
| helion | csharp | divergent | 9780 | 0 | 4.0 | 8 | 0.38 |
| doom-fx | assembly | unstated | 2004 | 0 | 2.1 | 12 | 0.39 |
| gore | go | compatible | 1025 | 2 | 13.4 | 13 | 0.39 |
| doomretro | c | enhanced | 2236 | 3 | 24.6 | 18 | 0.40 |
| doomsday | cpp | enhanced | 25480 | 0 | 6.6 | 7 | 0.45 |
| gzdoom | cpp | unstated | 20401 | 1 | 10.2 | 8 | 0.61 |

| metric | linuxdoom median | population median | IQR of port medians | linuxdoom percentile |
|---|---|---|---|---|
| complexity | 3.0 | 2.0 | 1.0 - 2.0 | 91 |
| loc | 21.0 | 14.0 | 9.2 - 19.0 | 91 |
| func_fan_out | 1.0 | 1.0 | 1.0 - 1.0 | 56 |
| token_mass | 130.0 | 100.0 | 81.2 - 117.0 | 88 |
| args | 1.0 | 1.0 | 1.0 - 1.0 | 50 |

<!-- study:distribution end -->

### By subsystem

Each function goes to the subsystem of the linuxdoom function it descends from (`lineage.assign_subsystem`), vendored
code dropped. A cell is the port's median complexity in that subsystem over linuxdoom's median in the same one; a blank
is a subsystem with under 5 functions on either side. The full per-metric tables and heatmaps come from
`subsystem_distribution.py` and `subsystem_plot.py`.

<!-- study:subsystem begin -->

| port | data-tables | game-loop | hud/ui | main/defs | misc | netcode | platform (i_*) | playsim | renderer | sound | video | wad | zone-alloc | other % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| agentic-cobol-doom-cc |  |  |  |  |  |  |  |  |  |  |  |  |  | 98 |
| agentic-cobol-doom-codex |  |  |  |  |  |  |  |  |  |  |  |  |  | 99 |
| chocolate-doom |  | 1.50 | 1.00 | 0.75 | 0.67 | 0.57 | 2/0 | 0.67 | 1.09 | 2.00 | 0.17 | 0.67 | 0.60 | 28 |
| crispy-doom |  | 1.00 | 1.50 | 0.75 | 0.67 | 0.57 | 2/0 | 0.67 | 1.09 | 3.00 | 0.17 | 0.67 | 0.60 | 27 |
| cssdoom |  |  |  |  |  |  |  |  |  |  |  |  |  | 98 |
| dartdoom |  | 0.50 | 1.50 | 0.12 | 0.00 |  |  | 0.67 | 0.64 | 2.00 |  |  |  | 30 |
| doo-cr |  | 0.00 | 0.00 | 0.00 | 0.00 | 0.43 | 0/0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 17 |
| doom-ascii |  | 2.00 | 1.00 | 1.00 | 0.67 | 0.43 | 1/0 | 0.67 | 1.09 | 2.00 | 0.17 | 0.50 | 0.70 | 5 |
| doom-fx |  |  |  |  |  |  |  |  |  |  |  |  |  | 100 |
| doom-ios |  | 2.00 | 1.50 | 1.25 | 0.67 |  | 0/0 | 1.33 | 0.55 | 1.50 | 0.08 | 0.67 | 0.40 | 45 |
| doom-scheme |  | 0.00 | 0.50 |  | 0.67 | 0.71 | 0/0 | 0.33 | 0.36 | 1.00 | 0.00 | 0.33 |  | 24 |
| doom-wasm |  | 2.50 | 1.00 | 0.75 | 0.67 | 0.57 | 2/0 | 0.67 | 1.09 | 2.00 | 0.17 | 0.67 | 0.60 | 31 |
| doom3-bfg |  | 1.25 | 1.00 | 0.50 | 0.67 | 0.29 | 0/0 | 1.33 | 1.09 | 3.00 | 1.00 | 0.50 | 0.60 | 95 |
| doom3do |  | 0.50 | 2.75 |  |  |  |  | 1.33 | 0.55 | 3.00 |  |  |  | 61 |
| doomf77 |  |  | 5.50 | 2.50 | 4.67 |  | 1/0 | 3.00 | 1.18 | 7.50 |  | 0.50 |  | 0 |
| doomgeneric |  | 2.00 | 1.00 | 0.88 | 0.67 | 0.43 | 2/0 | 0.67 | 1.09 | 2.00 | 0.17 | 0.50 | 0.70 | 11 |
| doomretro |  | 4.00 | 2.50 | 1.25 | 2.00 |  | 2/0 | 1.00 | 0.55 | 3.00 | 1.00 | 1.17 | 1.00 | 20 |
| doomsday |  | 1.00 | 1.00 | 0.50 | 1.33 | 0.57 |  | 0.67 | 0.18 | 0.50 |  | 0.00 | 0.60 | 89 |
| dsda-doom |  | 2.50 | 1.50 | 1.00 | 1.33 |  | 2/0 | 0.67 | 0.55 | 3.00 | 0.00 | 0.33 | 0.00 | 47 |
| edge-classic |  | 1.50 | 1.00 |  | 1.33 |  | 3/0 | 1.33 | 0.36 | 3.00 |  | 0.67 |  | 67 |
| eternity |  | 0.50 | 0.50 | 0.75 | 0.00 | 0.71 | 1/0 | 1.33 | 0.36 | 1.00 | 0.33 | 0.33 | 0.00 | 45 |
| fastdoom |  | 0.50 | 1.25 | 1.25 | 0.67 | 1.57 | 1/0 | 1.33 | 1.27 | 4.00 | 0.67 | 1.00 | 0.60 | 51 |
| fps-cob |  |  |  |  |  |  |  |  |  |  |  |  |  | 96 |
| fsharp-doom |  |  |  |  |  |  |  | 0.33 |  |  |  |  |  | 87 |
| gore |  | 2.00 | 1.50 | 0.25 | 0.67 |  | 1/0 | 1.00 | 0.91 | 2.00 | 0.83 | 0.50 |  | 44 |
| gzdoom |  | 0.50 | 0.00 | 0.50 | 0.00 | 0.57 | 1/0 | 0.67 | 0.00 | 0.00 | 0.00 | 0.00 |  | 71 |
| helion |  |  | 6.50 |  | 1.67 |  |  | 0.33 | 0.18 | 2.50 |  |  |  | 99 |
| inter-doom |  | 1.00 | 2.00 | 0.75 | 0.67 | 0.57 | 2/0 | 0.67 | 0.91 | 2.00 | 0.83 | 0.67 | 0.60 | 41 |
| kocoa-doom |  | 0.00 | 1.00 | 0.00 | 0.00 | 1.71 | 0/0 | 0.33 | 0.55 | 0.00 | 0.00 | 0.00 |  | 71 |
| managed-doom |  | 0.00 | 1.75 |  | 1.00 |  |  | 0.33 | 0.73 | 0.00 |  |  |  | 74 |
| mochadoom |  | 0.00 | 1.00 | 0.12 | 0.00 | 0.86 | 0/0 | 0.67 | 0.00 | 0.00 | 0.00 | 0.00 |  | 70 |
| mood |  | 1.00 | 1.00 | 1.00 | 1.33 | 1.14 | 0/0 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 19 |
| nugget-doom |  | 1.00 | 2.00 | 0.75 | 0.67 | 0.57 | 1/0 | 1.00 | 0.73 | 2.00 | 0.50 | 0.33 | 1.00 | 28 |
| odamex |  | 0.50 | 1.50 | 0.25 | 0.00 | 0.29 | 0/0 | 0.67 | 0.18 | 0.00 | 0.00 | 0.33 | 0.00 | 43 |
| prboom-plus |  | 2.00 | 1.50 | 1.25 | 0.67 | 0.00 | 3/0 | 1.33 | 0.73 | 3.00 | 0.00 | 0.67 | 0.40 | 37 |
| puredoom |  | 1.00 | 1.00 | 0.25 | 0.67 | 1.86 | 0/0 | 1.00 | 1.00 | 2.00 | 1.00 | 1.00 | 1.00 | 15 |
| room4doom |  | 2.00 | 0.00 | 0.38 | 0.00 |  |  | 1.00 | 0.73 | 1.00 |  |  |  | 94 |
| rust-doom |  |  |  |  |  |  |  |  |  |  |  |  |  | 98 |
| sdl-doom |  | 2.00 | 1.00 | 1.00 | 0.67 | 0.43 | 2/0 | 0.67 | 1.09 | 2.00 | 0.17 | 0.50 | 0.70 | 4 |
| sqldoom |  |  |  |  |  |  |  |  |  |  |  |  |  | 99 |
| srb2 |  | 1.50 | 3.00 | 0.75 | 1.33 | 1.14 | 0/0 | 2.00 | 0.55 | 0.00 | 0.83 | 0.83 | 0.60 | 39 |
| woof |  | 1.00 | 1.50 | 0.75 | 0.67 | 0.86 | 1/0 | 1.00 | 0.55 | 2.00 | 0.50 | 0.50 | 1.00 | 35 |

<!-- study:subsystem end -->

## Cross-language calibration: landmark functions

Twelve named linuxdoom functions are looked up in each translation; the ratio is the translation's complexity or LOC
against linuxdoom's. The matcher tries the exact name first and then the name without its `p_` / `r_` prefix (#6703).
A port that renames further still finds few: doomf77 uses Fortran 77-style abbreviations (`P_USELN` for
`P_UseSpecialLine`, `G_TICK` for `G_Ticker`), so its "0 / 12" is a naming limit, not a measurement of the port.

Findings, each checked against the source:

1. **Scheme `case` clauses now count (fixed in #6700).** doom-scheme's `p-cross-special-line` carries 75 `[(N) ...]`
   clauses. It read complexity 6 against linuxdoom's 93 when the branch rule counted the `case` keyword once; it now
   reads 78 (ratio 0.84). Its median ratio over the nine landmarks it has is 0.47.
2. **Dart `break` / `continue` are no longer branches (fixed in #6700).** dartdoom's `pUseSpecialLine` and
   `pCrossSpecialLine` read 169 and 165 against C's 121 and 93 when the Dart rule counted `break|continue` and the C
   rule did not. They now read 118 and 92, matching the shared structure (67 `case` labels and 48 `if` against 68 and
   48).
3. **Go: none found.** gore matches linuxdoom on all 12 landmarks (complexity ratio median 1.00).
4. **Java, Kotlin and C# are now measurable:** mochadoom finds 12, kocoa-doom 11 and managed-doom 7 of the twelve.

<!-- study:landmarks begin -->

| port | landmarks found | complexity ratio, median | range | LOC ratio, median | range |
|---|---|---|---|---|---|
| managed-doom | 7 / 12 | 1.00 | 0.50 - 1.80 | 1.12 | 0.89 - 1.30 |
| dartdoom | 11 / 12 | 0.98 | 0.28 - 1.06 | 0.66 | 0.24 - 0.90 |
| kocoa-doom | 11 / 12 | 0.86 | 0.00 - 1.71 | 0.86 | 0.01 - 2.03 |
| mochadoom | 12 / 12 | 0.71 | 0.00 - 1.86 | 0.96 | 0.01 - 2.31 |
| doom-scheme | 9 / 12 | 0.47 | 0.00 - 0.84 | 0.49 | 0.21 - 0.69 |
| doomf77 | 0 / 12 | - | - | - | - |
| gore | 12 / 12 | 1.00 | 0.00 - 1.26 | 0.76 | 0.41 - 0.99 |

<!-- study:landmarks end -->

## Call-graph shape ("subway") from `sfs`

Figures come from `sfs subway --reference linuxdoom` (gitgalaxy-population-analyses) over the same scans as the other
tables; `sfs` applies its own function filters, so its function counts run a little below the distribution table's. `wiring similarity` is how closely a port's call wiring matches linuxdoom's; `calls kept` is the
share of linuxdoom's call edges present in the port.

- **Read `wiring similarity` against its floor.** It is the cosine of a 16-subsystem call-share matrix, and 54% of
  linuxdoom's calls stay inside one subsystem, so a map whose calls only stay inside subsystems, spread evenly, already
  scores 0.47. A translation's functions are placed in subsystems by function name or file path (structural twins do
  not match across languages), so the score also leans on the port keeping linuxdoom's names or file prefixes.
- **Counting only calls between subsystems still separates translations from reimplementations.** chocolate-doom keeps
  0.83, doom-scheme 0.75, gore 0.65, dartdoom 0.59 and doomf77 0.41 of linuxdoom's cross-subsystem pattern; the
  from-scratch reimplementations (rust-doom, room4doom, helion) keep 0.07 to 0.10, and managed-doom 0.10 despite its
  0.72 overall. That rests on the engine's call graph being accurate in each language, given where each function
  belongs; it does not show structure alone recovering the placement.
- **doom3-bfg is the reverse case:** a separate engine (wiring 0.32) that ships DOOM Classic converted to C++, so 83%
  of linuxdoom's calls are still present by name.
- `nan` (doom-fx) means the tool could not compute a similarity for that port.

<!-- study:subway begin -->

| port | functions | wiring similarity | linuxdoom calls kept | graph-shape distance |
|---|---|---|---|---|
| mood | 1859 | 0.9911 | 0.9994 | 0.7163 |
| doom-ascii | 1019 | 0.9878 | 0.8411 | 0.3049 |
| sdl-doom | 1079 | 0.9807 | 0.8411 | 0.3364 |
| doomgeneric | 1192 | 0.9762 | 0.8393 | 0.4258 |
| puredoom | 1546 | 0.9715 | 0.9202 | 0.6085 |
| doom-scheme | 798 | 0.9516 | 0.4386 | 0.7360 |
| crispy-doom | 5870 | 0.9513 | 0.7452 | 0.4897 |
| chocolate-doom | 5129 | 0.9479 | 0.7153 | 0.4307 |
| dartdoom | 723 | 0.9324 | 0.4112 | 0.5548 |
| doomf77 | 146 | 0.9139 | 0.0000 | 0.7950 |
| dsda-doom | 4930 | 0.9027 | 0.4579 | 0.5168 |
| inter-doom | 6094 | 0.8781 | 0.6411 | 0.5237 |
| doom-ios | 1768 | 0.8742 | 0.6062 | 0.6329 |
| prboom-plus | 2430 | 0.8719 | 0.5950 | 0.6536 |
| gore | 996 | 0.8564 | 0.7707 | 0.3919 |
| doomretro | 2233 | 0.8311 | 0.4991 | 0.4499 |
| doom3do | 511 | 0.7848 | 0.1632 | 0.7266 |
| mochadoom | 3037 | 0.7766 | 0.3564 | 1.2682 |
| kocoa-doom | 2902 | 0.7652 | 0.2741 | 1.4847 |
| nugget-doom | 4173 | 0.7589 | 0.5040 | 0.3917 |
| managed-doom | 1285 | 0.7246 | 0.2118 | 0.9622 |
| eternity | 6641 | 0.7150 | 0.4162 | 0.7147 |
| srb2 | 6805 | 0.7092 | 0.1944 | 0.7267 |
| odamex | 7759 | 0.7068 | 0.3645 | 0.8408 |
| woof | 3788 | 0.6711 | 0.4822 | 0.4244 |
| edge-classic | 5151 | 0.6464 | 0.0255 | 0.7620 |
| doom-wasm | 2035 | 0.6454 | 0.7514 | 0.5825 |
| fastdoom | 2114 | 0.5647 | 0.5022 | 0.9382 |
| helion | 8386 | 0.5450 | 0.0199 | 1.1298 |
| cssdoom | 217 | 0.5011 | 0.0000 | 0.9380 |
| agentic-cobol-doom-cc | 45 | 0.4954 | 0.0000 | 1.7705 |
| gzdoom | 18434 | 0.4834 | 0.0729 | 1.1171 |
| doomsday | 23304 | 0.3859 | 0.1607 | 0.9859 |
| doom3-bfg | 13859 | 0.3180 | 0.8274 | 0.8956 |
| room4doom | 4582 | 0.2842 | 0.1377 | 1.0859 |
| rust-doom | 582 | 0.1612 | 0.0000 | 1.6348 |
| doo-cr | 1488 | 0.1439 | 0.0411 | 3.0180 |
| sqldoom | 475 | 0.1287 | 0.0037 | 1.3367 |
| freedoom | 106 | 0.1140 | 0.0000 | 2.4304 |
| agentic-cobol-doom-codex | 152 | 0.1068 | 0.0000 | 0.9097 |
| fsharp-doom | 47 | 0.0883 | 0.0000 | 2.8326 |
| fps-cob | 51 | 0.0765 | 0.0000 | 0.9701 |
| doom-fx | 1865 | nan | 0.0000 | 3.2540 |

<!-- study:subway end -->

## Limits

- Tables describe structure the engine extracts, not behaviour. A matching shape is not a proof of equivalent play.
- The subsystem split is by file name, so a port that renamed its files puts those functions under `other %`.
- Stated fidelity is read from READMEs; twelve ports state none, and a claim is not a measurement (sqldoom calls itself
  faithful while keeping 0.6% of linuxdoom's names and 0.13 of its wiring, because it is a translation).
- The follow-ups of #6097 have all shipped (#6700, #6703, #6705, #6749, #6752 and the per-subsystem slices); the owner
  dropped the remaining plots and `sfs`-side pieces on 2026-10-28. The subway maps (`callmaps.py`) were dropped on
  2026-10-21; the figures above come from `sfs`.
