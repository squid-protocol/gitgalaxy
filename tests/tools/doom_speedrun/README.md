# DOOM Port Speedrun harness (#5468)

Reproduces the DOOM port study (#5457) from the repo: 39 Doom ports pinned by SHA in `manifest.csv`, cloned shallow
at that SHA into a scratch directory, scanned with the current engine, and scored by six clean-scan checks. Each run
is keyed by the engine's git SHA, so before/after for one fix is a diff of two result directories.

**No third-party code is committed.** The manifest holds names, URLs, SHAs, languages and lineage only; clones are
fetched at run time under `--work` (default `/tmp/gitgalaxy-scratch/doom-speedrun`, refused inside the repo). It is
not part of default CI: run it by hand.

```bash
python tests/tools/doom_speedrun/doom_speedrun.py run --oracle                # all 39: clone, scan, score, report
python tests/tools/doom_speedrun/doom_speedrun.py run --only linuxdoom,gore   # a subset
python tests/tools/doom_speedrun/doom_speedrun.py score --oracle              # re-score existing scans
```

Steps (`fetch`, `scan`, `score`, `report`) can be run singly and are resumable. Scans go through
`tests/tools/box/heavy-run.sh` when present. Results land in `<work>/results/<engine-sha>/`: `clean_check.csv`,
`clean_check.md` (table) and `details.json` (the offending files and rules).

## The six checks (first-party code only)

| # | check | passes when |
|---|---|---|
| 1 | coverage | every first-party source file is mapped; a "Machine-Generated" exclusion counts only with a generator banner in the head; a payload-blocked file with zero ctags definitions is reported as `data_files_excluded`, not a miss |
| 2 | language | each mapped file's language fits its extension (`.h` as objective-c needs ObjC syntax, `.m` must be objective-c, ...) |
| 3 | functions | engine function count within 3% of Universal Ctags (definitions only, per-language kinds) over the mapped files |
| 4 | typosquat | no `TYPOSQUATTING DETECTED` log lines |
| 5 | credentials | no `has_credentials` files (SARIF error-level results are listed in `details.json` for review, never scored) |
| 6 | health | scan rc is 0 and no `[ERROR]` / `CLASSIFICATION REFUTATION` / `Traceback` log lines (engine-wide warnings ignored) |

Vendoring is decided by the engine's own `VendorDirectoryDetector`. `--legacy-vendor` adds the round-2 study's
hand-kept vendor-name list, for comparing against round 2's table.

## Second oracle (`--oracle`)

`treesitter_functions` / `ts_delta_pct`: tree-sitter function-definition node counts over the same files, reported
beside ctags and never scored. ctags misses macro-defined functions (#5461), so agreeing with ctags alone is not the
claim. libclang on a subset with `compile_commands` is not wired up (a remaining slice).

## Known blind spots

- **Agreement is not correctness.** A 0% delta means two counters agree on a number; it says nothing about which
  functions. Per `CLAUDE.md`, a correctness claim needs someone reading the disputed source.
- **ctags and tree-sitter share blind spots on C macros.** Both can miss a function a macro generates (`DEFINE_*(...)`),
  and tree-sitter may count a mis-parsed macro use as a function; the delta can cancel real misses and extras.
- **Languages ctags/tree-sitter lack** (assembly, makefile, ...) are in no oracle: checks 3 and the oracle skip them.
- **Check 1 only sees `SRC_EXT` files**; a first-party file with another extension is invisible to it.
- **Vendoring is the engine's call**: a vendored tree the detector misses leaks into check 1/2/3 as first-party.
- **Check 6 reads the log text**, so a new log wording needs `log_problems` updated.
- **Pinned SHAs are the ports' HEAD at study time** (2026-10-18); a force-pushed upstream makes `fetch` fail loudly.
- **Round 2's CSV was produced at engine `585c243e9`**; the current engine will differ, which is the point.
