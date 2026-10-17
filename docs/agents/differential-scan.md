---
description: "Full Differential Scan protocol: golden-master fixture directories, rebase_rebless, tri-comparison audits, local venv trap, scoping a bless, audit runners."
---
# The Differential Scan: full protocol

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

Any PR touching parsing logic (`detector.py`, `language_standards.py`, `prism.py`, etc.) is
expected to be verified against `tests/golden_master_audit/` /
`tests/golden_master_zero_dep_audit/` — snapshots diffed by the `crucible-audit` CI check
against a ~80-repo corpus plus the PR's target repo. A failing diff means output changed: either
a bug, or an intentional improvement that needs the baseline re-blessed. **Never hand-edit these
fixtures.** Regenerate with `python tests/tools/crucible_check.py --update --yes` (default
`--mode both`) — explain *why* the output changed in the PR description, CI flags any PR touching
these files. This handles BOTH fixtures (full-precision and zero-dependency each need their own
venv/interpreter) in one command with no manual `PATH`/`pip install -e .` bookkeeping — see the
"Verifying locally before pushing" paragraph just below for exactly what it automates and why
that matters. `python tests/tools/update_golden_master.py` (`--yes` to skip its own confirmation
prompt) is the underlying single-mode script `--update` shells out to per venv; call it directly
only if you're already inside one specific mode's venv and deliberately want just that fixture —
reaching for it from your default shell silently updates whichever ONE fixture matches whatever
happens to be importable there (#2547: this cost a full investigation cycle before landing on
`crucible_check.py --update` instead).

**The fixtures are directories, not files (#3384).** Each is ~200 per-section JSON parts written
by `tests/golden_store.py` — one file per top-level section key, and inside "6. Parsed Files" one
file per (per-file section, sub-key) holding that value for every corpus file — so two PRs that
each add a new fact channel, signal, or report section create *different new files* and merge
without conflicts. Every reader goes through `golden_store.load()` (and so
`golden_diff.load_and_sanitize()`), which reassembles the exact dict the old monolith held and
fails loudly on a stray, misplaced, or orphaned part; `tests/test_golden_store.py` also asserts
both committed fixtures are byte-canonical. For a single-file copy (e.g. a pre-bless snapshot),
use `python tests/golden_store.py export --rev HEAD tests/golden_master_audit /tmp/old.json`, not
`git show`. On a conflict inside a fixture, take main's side and re-run
`crucible_check.py --update --yes` (or `rebase_rebless.py`, which does exactly that).

**Rebasing a parser/channel PR after a sibling merges:** `python tests/tools/rebase_rebless.py`
(#3385) automates the manual procedure PRs #3369/#3375 each did by hand — rebase onto
`origin/main`, take main's side for golden masters/ruff/mypy/dead-key baselines on conflict (a
code-file conflict instead stops the run with a clear list rather than being auto-resolved),
re-bless with `crucible_check.py --update`, then **verify** the resulting golden-master diff
against main is limited to this branch's own new keys (auto-detected from the pre-rebase
branch-vs-merge-base diff, or passed via `--expect-keys`) — failing loudly on any other
("foreign") drift, the same scoped-review discipline "Scoping a bless" below describes. It then
runs `audit_check.py --regenerate` scoped to touched files (with #3384's content-keyed ruff/mypy
baselines, moved lines no longer need refreshing; this only re-accepts edited baselined lines) and
runs ruff check/format plus
a fast, touched-file-scoped test selection. The default is a dry run (a read-only `git
merge-tree` preview, no branch mutation); `--execute` performs it for real, and `--push` (only
valid with `--execute`) does `git push --force-with-lease` — never plain force.

The same PR paths also run `tri-comparison-audit.yml`, a baseline-gated regression check on
GitGalaxy's own **validated** precision against tree-sitter+ctags (see `docs/self_scan/
tri_comparison_README.md`'s "CI enforcement" section) — a distinct, blocking check from the
golden-master diff above, alongside `tree-sitter-accuracy-audit.yml`'s 2-tool equivalent. None of
the three requires you to regenerate and commit chart/history artifacts yourself; that's handled
by separate push-to-main companion workflows after merge.

**Verifying locally before pushing:** use `python tests/tools/crucible_check.py` (add `--update`
to regenerate) instead of hand-building venvs. It builds/reuses two venvs at
`.crucible_venvs/{full_precision,zero_dependency}` *inside the current checkout* and — critically
— re-runs a fast `pip install -e . --no-deps` before every check. Skipping that step is a real
footgun: a venv's editable install is a pointer to whatever path was passed to `pip install -e .`
at creation time, and `galaxyscope` is invoked as a subprocess, so reusing a venv across worktrees
(e.g. a long-lived personal dev venv) makes it silently scan a *different* checkout's code — this
produced a false "zero diff" pass locally while CI correctly failed on real output drift (PR
#579/#723, 2026-07-28). Never point `LANGUAGE_CRUCIBLE_PATH`/a shared venv at this without
confirming which checkout its editable install actually resolves to
(`python -c "import gitgalaxy; print(gitgalaxy.__file__)"` from inside that venv).

**Scoping a bless: `crucible_check.py` shows you only a fraction of the diff.** Its output is
capped twice -- `tests/golden_diff.py` prints 50 differences, and `crucible_check.py`'s wrapper
keeps a 4000-char window of that -- so a run reporting "581 differences" surfaces about 28.
GATING-style scoped-diff review ("every unrelated mover is attributed to a named PR, or the
bless waits") is therefore **impossible from its output alone**: on 2026-09-02 all 28 surfaced
diffs were groovy and said nothing about the other 18 languages that had moved. Regenerate the
audit and diff it yourself:

```sh
# GITGALAXY_DISABLE_GIT_HISTORY=1 is NOT optional (#2985): test_golden_crucible.py sets it
# (and so does update_golden_master.py), so the committed fixtures have every git-derived
# field ablated. Omit it here and you get ~8,500 phantom differences on top of the real
# ones -- Architect ("Unknown Architect" -> your git identity), Raw Churn Frequency,
# Authorship Centralization, Instability/Volatility Exposure -- and a wasted rescan cycle
# before you work out none of them are yours.
GITGALAXY_DISABLE_GIT_HISTORY=1 \
.crucible_venvs/zero_dependency/bin/galaxyscope <language-crucible>/data \
    --output /tmp/gm/ --file-speed --splicing-speed          # same flags as tests/test_golden_crucible.py
python -c "
import sys; sys.path.insert(0,'tests'); import golden_diff as gd
g=gd.load_and_sanitize('tests/golden_master_zero_dep_audit')   # split dir, #3384
a=gd.load_and_sanitize('/tmp/gm/data_galaxy_audit.json')
for d in gd.deep_compare(g,a): print(d)"
```

Expect most of the volume to be topological `X`/`Y`/`Z` coordinates: the 3D layout re-solves
corpus-wide whenever any node's mass changes, so a single-language fix ripples coordinates
across every language in the corpus. Those are attributable as a class; filter them out and
scope the remainder, which is what actually needs a per-language explanation.

**The corpus-backed audit runners need the main `.venv`, and they refuse to pass on nothing.**
`tests/tools/tree_sitter_accuracy_audit.py`, `tests/tools/tri_comparison_chart.py` and
`tests/tools/rosetta_audit.py` all need `galaxyscope` on `PATH` (the main `.venv` has it plus
`tree_sitter_language_pack`; neither crucible venv has both). Since #2682 a run that checked zero
languages, or a baselined language whose scan could not run, is a hard failure — previously
`tri_comparison_chart.py --ci` skipped every language and printed `all OK` with exit 0 when
`galaxyscope` was missing. Run them as:

```sh
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tests/tools/tree_sitter_accuracy_audit.py --ci --all
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tests/tools/tri_comparison_chart.py --all --ci
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tests/tools/rosetta_audit.py      # needs ../keyword-rosetta
```

and still glance at the summary line's language count (30, 3 and 46 respectively as of 2026-09-03).
