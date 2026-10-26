# DOOM-rosetta (#5619)

A zero-drift check of the engine over 44 real, licensed DOOM ports in 25-odd languages: the Golden Crucible's twin for
code nobody wrote for us. Each port is cloned at a pinned SHA, scanned, and its **measurements** are diffed against
`tests/golden_doom_rosetta/<port>.json.gz`. The harness that scores a port (the checks, the oracles) is
`tests/tools/doom_speedrun/` (see its README); this folder holds the manifest and the pytest gate.

## Files

| Path | What |
|---|---|
| `manifest.csv` | the corpus: `name, upstream, sha, branch, languages, class, license, lineage, expected_fails, fidelity, fidelity_file, fidelity_phrase, fidelity_reason` |
| `test_doom_rosetta.py` | `pytest -m doom_rosetta` (self-skips unless the marker is selected) |
| `../golden_doom_rosetta/` | one gzip JSON per port (`*.json` is git-ignored, hence `.json.gz`) |
| `../tools/doom_rosetta_check.py` | check, bless (`--update --yes`), `--diagnose PORT` |
| `../../.github/workflows/doom-rosetta.yml` | PR shards (LOC-packed) and the nightly `callgraph` job |

## Run

```bash
python tests/tools/doom_rosetta_check.py --only linuxdoom,gore    # a subset; rc 1 on drift
python -m pytest -m doom_rosetta tests/doom_rosetta               # all ports (about 8 min serial)
DOOM_ROSETTA_PORTS=a,b python -m pytest -m doom_rosetta tests/doom_rosetta
```

Needs Universal Ctags on PATH (Arduino's `ctags` fails the preflight). Clones go under `DOOM_SPEEDRUN_WORK` (default
outside the repo; the harness refuses a work dir inside it). CI ctags can differ from yours: the golden holds
`ctags_functions`, `func_delta_pct` and `functions_agree`, so pin ctags rather than re-bless on a ctags-only move.

## Bless

Drift is a bug or an intended engine change. For an intended change, regenerate and explain the moves in the PR:

```bash
python tests/tools/doom_rosetta_check.py --update --yes
```

Never hand-edit a golden. Use `--diagnose PORT [--file PATH]` locally to see the real function names behind a hash
mismatch (names are never committed). A port that is known to fail a check is listed in `expected_fails`; passing a
listed check is drift too, so remove the entry when the engine gets it right.

## Nightly

`doom-rosetta.yml` runs a nightly `callgraph` job on main (C/C++ call-graph accuracy against
`tests/tools/doom_speedrun/callgraph_baseline.json`). The full clean scan is run by hand for now:

```bash
python tests/tools/doom_speedrun/doom_speedrun.py run --oracle                       # ctags + tree-sitter, all ports
python tests/tools/doom_speedrun/doom_speedrun.py diff <before> <after> --fail-on-regression
```

A nightly `--oracle` job that publishes the table and diffs it with the previous night is not wired yet (#5619).

## Add a port

1. Read its license from the repo's own files (GitHub's detected license is often `NONE` for a subdirectory
   `COPYING`). Only a clear OSI license (or CC0 for content) qualifies; anything questionable is not added here.
2. Pin a SHA and add a row with `class` and `license` (columns in `tests/tools/doom_speedrun/README.md`).
3. `python tests/tools/doom_speedrun/doom_speedrun.py run --only <name>` must exit 0, then bless the new golden.
4. Check `docs/research/third-party-material-policy.md` still describes the license set.

## Rules

* **Licensed ports only** (owner, 2026-10-19): GitGalaxy is an LLC, so every use is commercial. A port without a
  clear license is never in the manifest, a cache, a golden, a PR, an issue or a doc, and is never named in them.
* **Measurements, not code**: goldens hold counts, hashes and exclusion reasons. No third-party source, function
  names, WADs or game data are committed; clones are fetched at run time and live outside the repo.
* "DOOM" is used descriptively only. This project is not affiliated with or endorsed by id Software, ZeniMax Media or
  any port's authors.
* Third-party material in general: `docs/research/third-party-material-policy.md`.
