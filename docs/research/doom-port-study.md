# DOOM port study

What the GitGalaxy engine measures across 44 DOOM ports (issue #5620), re-scanned on engine `eadc036c9`. Measurements only:
no port code is reproduced, and the ports named here are those the license register marks clearly licensed
(`tests/tools/doom_speedrun/README.md`, "Licensing rule"). "DOOM" is used descriptively; this project is not affiliated
with or endorsed by id Software, ZeniMax Media or Microsoft.

## Reproduce

Every table below sits between `<!-- study:NAME begin/end -->` markers and is generated, not typed:

```bash
python tests/tools/doom_speedrun/doom_speedrun.py run --oracle --work DIR      # clone at the pinned SHAs, scan, score
sfs compare ... --subway-reference linuxdoom                                    # gitgalaxy-population-analyses, writes subway.csv
python tests/tools/doom_speedrun/study_report.py --work DIR --sha eadc036c9 --subway subway.csv --write
python tests/tools/doom_speedrun/study_report.py --work DIR --sha eadc036c9 --subway subway.csv --check   # rc 1 when stale
```

The prose between the tables is hand-written and dated 2026-10-22; the tables are the evidence.

## Clean scan, round 2 to now

Round 2 (engine `585c243e9`) scored six checks; the call-graph check is new since. The seven checks are in the harness
README. Read the table with three cautions:

- **Passing is not the same as measured.** A port shown `(vacuous)` has no first-party file the scorer recognises
  (its source extension is outside the scorer's set), so its coverage check passes on zero files. Those rows prove
  nothing about the port.
- **The call-graph check fails 2 ports** (`doom3-bfg`, `doomsday`; both existed in round 2). It failed 17 at the first
  scan that had it, so engine fixes since then cleared 15. Two newer ports (`sqldoom`, `cssdoom`) fail the functions check.
- **Coverage and health failures from round 2 are gone** for every port that existed then (missed files now 0
  everywhere; `doomsday` went from 993 missed files to 0).

<!-- study:clean-scan begin -->

40 of 44 ports pass every scored check now; 24 of them failed at least one in round 2 (`n/a` = the port was added after round 2; `(vacuous)` = the scorer saw no first-party source files, so the pass proves nothing; `not compared` = ctags has no reading of that language). The call-graph check did not exist in round 2.

| port | failed checks, round 2 | failed checks, now | first-party files, now | missed files, round 2 | now | functions vs ctags %, round 2 | now | functions now |
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
| doom3-bfg | coverage | callgraph | 888 | 3 | 0 | -2.1 | 0.8 | 16379 |
| doom-ascii | coverage health | - | 180 | 1 | 0 | 0.0 | 0.0 | 1019 |
| srb2 | coverage | - | 422 | 1 | 0 | 2.1 | 2.5 | 6759 |
| freedoom | - | - | 13 | 0 | 0 | -0.7 | 0.0 | 119 |
| helion | coverage functions | - | 1518 | 1 | 0 | 4.0 | 3.7 | 9780 |
| doomsday | coverage functions health | callgraph | 2552 | 993 | 0 | 16.2 | 14.0 | 25450 |
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
token mass, arguments) and linuxdoom's. It is a shape comparison, not a correctness claim: it runs from 0.08
(puredoom) to 0.54 (fps-cob). linuxdoom itself sits near the 91st percentile of the ports for complexity and for LOC
(the 1993 original has longer, branchier functions than the median port).

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
| cssdoom | javascript | divergent | 225 | 2 | 18.2 | 12 | 0.16 |
| dartdoom | dart | enhanced | 865 | 2 | 14.3 | 10 | 0.17 |
| managed-doom | csharp | compatible | 1300 | 1 | 9.5 | 15 | 0.18 |
| woof | c | enhanced | 3795 | 2 | 13.6 | 16 | 0.18 |
| eternity | cpp | enhanced | 7308 | 1 | 13.2 | 12 | 0.20 |
| nugget-doom | c | enhanced | 4180 | 2 | 14.7 | 16 | 0.21 |
| agentic-cobol-doom-codex | cobol | divergent | 162 | 2 | 8.0 | 10 | 0.23 |
| room4doom | rust | compatible | 4684 | 0 | 6.9 | 11 | 0.24 |
| doom-scheme | scheme | faithful | 1034 | 1 | 9.1 | 7 | 0.24 |
| dsda-doom | c | enhanced | 4937 | 2 | 13.5 | 13 | 0.25 |
| sqldoom | python | faithful | 419 | 2 | 14.6 | 9 | 0.25 |
| agentic-cobol-doom-cc | cobol | divergent | 45 | 4 | 17.8 | 25 | 0.26 |
| doomf77 | fortran | compatible | 146 | 6 | 37.7 | 24 | 0.28 |
| fastdoom | c | enhanced | 2135 | 1 | 12.9 | 20 | 0.29 |
| srb2 | c | divergent | 6759 | 2 | 20.4 | 16 | 0.33 |
| fsharp-doom | fsharp | unstated | 53 | 1 | 9.4 | 12 | 0.34 |
| edge-classic | cpp | enhanced | 4963 | 2 | 14.0 | 13 | 0.34 |
| doom3-bfg | cpp | unstated | 16379 | 1 | 9.8 | 8 | 0.34 |
| fps-cob | cobol | divergent | 54 | 6 | 33.3 | 32 | 0.35 |
| kocoa-doom | kotlin | unstated | 3565 | 0 | 5.5 | 5 | 0.36 |
| mochadoom | java | unstated | 3781 | 0 | 5.3 | 5 | 0.36 |
| odamex | cpp | compatible | 8670 | 1 | 9.4 | 8 | 0.36 |
| doo-cr | crystal | divergent | 1509 | 0 | 7.5 | 3 | 0.37 |
| rust-doom | rust | divergent | 616 | 0 | 4.4 | 5 | 0.37 |
| helion | csharp | divergent | 9780 | 0 | 4.0 | 8 | 0.38 |
| doom-fx | assembly | unstated | 2004 | 0 | 2.1 | 12 | 0.39 |
| gore | go | compatible | 1025 | 2 | 13.4 | 13 | 0.39 |
| doomretro | c | enhanced | 2236 | 3 | 24.6 | 18 | 0.40 |
| doomsday | cpp | enhanced | 25450 | 0 | 6.6 | 7 | 0.45 |
| gzdoom | cpp | unstated | 20401 | 1 | 10.2 | 8 | 0.62 |

| metric | linuxdoom median | population median | IQR of port medians | linuxdoom percentile |
|---|---|---|---|---|
| complexity | 3.0 | 2.0 | 1.0 - 2.0 | 91 |
| loc | 21.0 | 14.0 | 9.2 - 19.0 | 91 |
| func_fan_out | 1.0 | 1.0 | 1.0 - 1.0 | 58 |
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
against linuxdoom's. **The matcher is exact on name, so a port that renames (`p_` / `r_` prefixes dropped) finds
few or none of the twelve** (managed-doom, doomf77, kocoa-doom, mochadoom): "0 / 12" is a matcher limit, not a
measurement of the port.

Findings, each checked against the source:

1. **Scheme: `case` clauses are not counted (defect).** doom-scheme's `p-cross-special-line` carries 75 `[(N) ...]`
   clauses and reads complexity 6 against linuxdoom's 93 (ratio 0.33 median over the nine found landmarks). The
   Scheme branch rule counts the `case` keyword once, not its clauses.
2. **Dart: `break` / `continue` count as branches (defect).** dartdoom's `pUseSpecialLine` and `pCrossSpecialLine` read
   169 and 165 against C's 121 and 93. The sources have the same structure (67 `case` labels and 48 `if` against 68
   and 48); the Dart branch rule adds `break|continue` (51 `break` in that function), the C rule does not. The 48-point
   gap is the `break` count.
3. **Go: none found.** gore matches linuxdoom on all 12 landmarks (complexity ratio median 1.00).
4. **Not measurable here:** Java, Kotlin, C# and Fortran, for the matcher reason above.

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

Figures come from `sfs compare --subway-reference linuxdoom` (gitgalaxy-population-analyses), run on an earlier scan
of the same pinned ports (2026-10-21), so function counts differ slightly from the clean-scan table. `wiring
similarity` is how closely a port's call wiring matches linuxdoom's; `calls kept` is the share of linuxdoom's call
edges present in the port. A port in another language can keep the wiring (doom-scheme 0.95, dartdoom 0.93,
doomf77 0.91) while keeping few edges by name (0.49, 0.41, 0.00); managed-doom keeps 0.73 wiring with no surviving
names. `nan` rows (doom-fx) mean the tool could not compute a similarity.

<!-- study:subway begin -->

_No `--subway` file given: run `sfs compare` (see the header of `study_report.py`) and pass its `subway.csv`._

<!-- study:subway end -->

## Limits and remaining slices

- Tables describe structure the engine extracts, not behaviour. A matching shape is not a proof of equivalent play.
- Vendored libraries are not excluded from the distributions.
- Not done here: engine fixes for the two calibration defects, a landmark matcher that drops the `p_` / `r_` prefixes,
  per-subsystem distributions, the plots, and the scorer's source-extension set (Fortran, Crystal, F#, COBOL), which
  makes check 1 vacuous for those ports. The subway maps (`callmaps.py`) were dropped by the owner on 2026-10-21; the
  figures above come from `sfs`.
