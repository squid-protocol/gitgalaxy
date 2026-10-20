# DOOM corpus rescan after the #5460 payload-guard fixes (2026-10-18)

Backfill for #5460 (slice 3 of 3) and a vendored-tree read for #5464. Engine: `f60dfb0c3` (origin/main, after #5493,
#5547, #5550). Corpus: the 39 pinned ports of `doom-study/variants_r2.csv`, scanned with `GITGALAXY_DISABLE_GIT_HISTORY=1`,
one at a time, every port rc=0. Scorer: doom-study `scripts/clean_check.py` (two local edits: engine path, and
`VendorDirectoryDetector.is_candidate_name` is gone since #5464, so every ancestor directory is probed with `is_vendored`).

> Licensing note (2026-10-20, #5619): the corpus was later cut to clearly licensed ports. Counts below are from the
> original 39-port run and still include ports since removed; those ports are not named.

## #5460: first-party files with ctags-visible functions excluded by a content guard

| guard | before (round 2, 585c243e9) | now |
|---|---|---|
| Embedded Array/Matrix Payload | 37 files, 189 fns | 0 |
| Embedded Hex Payload | 17 files, 250 fns | 0 |
| Packed Payload Guard | 5 files, 416 fns | 0 (`EntityFlags.cs` 363, `gl_load.c` 26, `mac.c` 25 all mapped with those counts) |
| Saturation | 3 files | 0 |
| Lexical Monotony | `d_dehtbl.cpp` (21), `win_qgl.cpp` (3) | 5 files, 1 function each (below) |

`aes_prng.c` 9, `crc32.cpp` 13, `utf8.cpp` 11 and `d_dehtbl.cpp` 17 are mapped. Data-only files the guards still drop
(no ctags function in them) are unchanged and correct.

**Residual: Lexical Monotony needs two definitions** (`aperture.py` Gate 5.1, `_has_definitions(need=2)`). Five
`tables.c`/`tables.cpp` files (four named here) hold exactly one function beside a 2,000-line table and are still excluded:
linuxdoom `linuxdoom-1.10/tables.c`, doomgeneric `doomgeneric/tables.c`, eternity
`source/tables.cpp`, doom3-bfg `doomclassic/doom/tables.cpp`. The acceptance "zero files with ctags-visible
functions" holds for the three guards named in the slice, not for this one; the `need=2` choice is deliberate
(a lone function around an unrolled loop is still generated), so lowering it is a decision, not a fix.

Other "missed" rows in the scorer are not guards: `re2c` `parser.cc` (bison output, accepted), room4doom
`info.rs` (Machine-Generated banner) and `docs/` samples (hidden/ignored directory).

## #5464: vendored trees

| port | first-party-looking vendored files still mapped (scorer's name list) | note |
|---|---|---|
| eternity | 22 | `concurrentqueue.h` (name not in the engine list) and first-party `source/sdl/*`; `libpng`, `zlib`, `nlohmann` no longer mapped |

Whole-corpus scorer verdict: 22 of 39 PERFECT. The rest fail on checks outside this issue (coverage rows above,
function-count deltas, doom-ios language, doomsday and edge-classic).
