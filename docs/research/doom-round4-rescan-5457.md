# DOOM round-4 rescan at `b81b19f78` (2026-10-19)

Epic #5457. Engine: `b81b19f78` (origin/main). Corpus: the 39 pinned ports in `tests/tools/doom_speedrun/manifest.csv`.
Command: `doom_speedrun.py run --oracle` (every port rc=0). Compared with `diff round2 b81b19f78` and `diff aa8919dea.oracle b81b19f78`
(round 3, the first harness run). Counts are measurements, not ground truth (ctags and tree-sitter share blind spots on C macros).

## Headline

| round | engine | PERFECT (6 checks) |
|---|---|---|
| 2 | `585c243e9` | 8 / 39 |
| 3 | `aa8919dea` | 19 / 39 |
| 4 | `b81b19f78` | **20 / 39** |

Round 2 -> 4: 12 ports gain PERFECT (chocolate-doom, crispy-doom, doom-ascii, doom-wasm, doom3do, doomretro, fastdoom, inter-doom,
mochadoom, odamex, puredoom, srb2); typosquat alerts 0, credential flags 0, log problems 0 on every port. Round 3 -> 4: doom3do gains PERFECT
(its one missed file is mapped); edge-classic, helion, vizdoom, zandronum each lose a failed check.

## The 19 ports still failing

| port | fails | cause (from `details.json`) |
|---|---|---|
| linuxdoom, gbadoom, eternity, doom3-bfg | coverage (1 file each) | `tables.c`/`tables.cpp`: Lexical Monotony needs two definitions, file holds one (see `doom-corpus-rescan-5460.md`) |
| woof, nugget-doom | coverage (6) | `third-party/` names excluded as ignored dirs (vendored; scorer counts them first-party) |
| gzdoom | coverage (44) | 43 ignored-dir files, 1 `re2c` bison output (Machine-Generated, accepted) |
| room4doom | coverage (10) | 9 `docs/` samples, `info.rs` with a generator banner |
| vizdoom | coverage (5) | 4 `docs/` files, 1 generated |
| edge-classic, sdl-doom | coverage (1) | `web/site/webplayer.py`; `docs/legacy_doc/README.asm` (hidden/ignored directory) |
| doom-ios | coverage 62, language 2 | 62 `__MACOSX/._*` AppleDouble files (not source); `IBGlue.h`, `iphone_email.h` ObjC by sibling anchor (known caveat) |
| doomsday | coverage 15, language 1, functions +14.8% | ignored-dir build scripts; `fonts_macx.h` ObjC by sibling; function delta below |
| eternity | functions +3.4% | see regression note |
| gore | functions +8.4% (1025 vs ctags 946; tree-sitter 1025) | `doom.go` 939 vs 860: ctags undercounts Go; tree-sitter agrees with the engine |
| doom-nano | functions +7.7% (84 vs 78; tree-sitter 85) | `input.cpp` 14 vs 8; 78 is a small base |
| helion | functions +3.9% (tree-sitter -2.2%) | the two oracles straddle the engine |
| psydoom | functions -8.7% (tree-sitter -5.3%) | engine below both oracles: owned by #5462 (C++ undercount after vendor removal) |

Most "coverage" failures are not engine drops: ignored directories (`docs/`, `third-party/`, `__MACOSX`, `web/`) and generated files the
scorer's `SRC_EXT` sweep sees but the engine is right to skip. Whether `third-party/` under woof/nugget should be treated as vendored by
the scorer is a harness question, not an engine one.

## Regression flagged by the diff

`eternity` 5/6 -> 4/6 against round 3: functions delta 2.8% -> 3.4% (threshold 3%). Both counts fell (engine 8233 -> 7309, ctags
8011 -> 7068) as `first_party_src` dropped 611 -> 584 (vendored files now excluded); the engine fell less than ctags. Against round 2 the
delta was -0.1%. Not read at source: which functions account for the 241-function gap is open.

## Where the round-2 -> 4 gap closed (for the write-up)

- #5458 doomsday: missed_src 993 -> 15; first_party_src 2431 -> 2552.
- #5459 gore: 86 -> 1025 functions (single-file engine no longer amalgamation-blocked); puredoom 777 -> 1560.
- #5461 macro-defined functions: doom64ex 1582 -> 1895, dsda-doom 4784 -> 4937 (engine and ctags both rise, via the payload fixes).
- #5464 vendored trees: psydoom first_party_src 1879 -> 676, vendor_files_mapped 0 on all ports; sarif_errors 48 -> 1.
- #5460 payload guards: see `doom-corpus-rescan-5460.md`.

Raw outputs: `doom-study/speedrun/results/b81b19f78/{clean_check.csv,clean_check.md,details.json}`.
