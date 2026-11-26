# Keyword-family validity: reference and PR checklist (#8863)

The procedure is `.claude/skills/family-validity-fix`; this page is what it points at: the rulings, the cause table, the
recipes, and the checklist a PR carries. Contracts are the definitions (`gitgalaxy/standards/signal_contracts.py`,
`docs/*_rule_contract.md`); a family is scored against its contract, never against a guess.

## Rulings already made (do not re-ask; #8862 and #8868)
| Family | Ruling |
|---|---|
| `serialization_parsing` | JSON, XML, YAML, CSV, protobuf codecs count |
| `lazy_evaluation` | a generator expression does not count (only `yield`, generator and iterator types) |
| `closures` | an anonymous callable only: lambda, arrow, function literal, block, inline callback. A nested named `def` and a method declaration are not closures |
| `cleanup` | `with`, `try/finally`, `del`, handle and connection close, `rmtree` and removals; closing a handle is cleanup's, not io's |
| `telemetry` | a log, metric or trace through a framework; a bare print is `debug_prints`, not telemetry |
| `panics_and_aborts` | abort, fatal error, unreachable marker, process exit. `assert` is not an abort, and `return -1` (an error return) is not an abort. A `.exit()` method call is not a process exit |
| `thread_sleeps` | a sleep, a timed wait, a timeout-driven deferral: `time.Sleep`, `time.After`, `NewTicker`, `NewTimer`, `setTimeout`, `setInterval`, `setImmediate` |
| `time_date_logic` | a clock or calendar value, a duration, a formatting or timezone call. A sleep or timer is not time |
| `doc` | the structured documentation form each language's tools read; a language with none is N/A, not "any comment" |
| string literals | shielding keywords inside strings is extended one family at a time, each timed (#2535); `branch` already has it |

Rust `?` counts as a `branch` (#8868): it is a conditional early return, so the contract's unconditional-transfer exclusion does not apply; the Rust oracle reads `try_expression` (crucible: precision 0.76 -> 0.99, no engine change).

Nothing from #8868 is still open as a question; Go struct tags as `decorators` was settled in #9363.

Go `decorators` counts the `//go:` pragma line(s) directly above a `func` (a blank line detaches; a doc comment between does not), read from the raw lines in `detector._go_leading_pragmas` because the unit starts at `func` (#9343: crucible 0 / 151 -> 151 / 151). Go `regex_execution`'s oracle reads `re.MatchString` method calls as well as `regexp.` calls (prometheus, re-measured 2026-11-26 on the current engine: recall 0.93, precision 1.00 over 7,935 functions, baseline row updated, #9343; the pinned Go crucible has no regexp use, so that cell stays hatched).

Shell (#9338, re-measured 2026-11-26 on the pinned crucible, language-crucible v1.9.0, 816 functions): the five cells the issue listed (`bitwise_ops`, `time_date_logic`, `panics_and_aborts`, `io`, `debug_prints`) were already at or above 0.8 after #9409; `family_oracle_sweep.py --write` reproduced the committed baseline byte for byte, so no rule or oracle changed. Lowest Shell cells now: `thread_sleeps` precision 0.828, `branch` 0.833 (both above the bar).

Kotlin (#9330, re-measured 2026-11-26 on the pinned crucible, language-crucible v1.9.0, 246 functions): the seven cells the issue listed were already at or above 0.8 (`closures` and `doc` after #9358, `io`, `panics_and_aborts`, `bitwise_ops`, `regex_execution` and `time_date_logic` after #9409); `family_oracle_sweep.py --write` reproduced the committed baseline byte for byte and `family_red_cells.py --lang kotlin` lists 0 red cells, so no rule or oracle changed. Only `closures` (1.00 / 0.971) and `doc` (1.00 / 1.00) have pinned instances; the other five are scored on okhttp (hatched, not quotable: `io` 0.948, `regex_execution` 0.912, `panics_and_aborts` 0.98 / 0.993, `bitwise_ops` and `time_date_logic` 1.00). Lowest Kotlin cell: `thread_sleeps` on okhttp, precision 0.80 (above the bar, not in the issue's list).

## What a red cell usually is (check in this order)
| Symptom | Usual cause | Real examples |
|---|---|---|
| recall low, one callee dominates the missed list | the **oracle reads the contract too broadly** | Go `time.` counted timers; C `close`; Rust bare `exit` matched `span.exit()` |
| precision low, oracle sees far fewer | the **rule counts a different construct** | Go `closures` matched method declarations; Rust `short_circuit` counted `||` closures; TypeScript `io` matched the bare word `path` |
| precision low, recall 1.00, a self-scan only | **the oracle misses a form** | `self.logger.info()` read only as a bare `logger.` receiver |
| recall low, the missed tokens are named by the contract | a **real missing keyword** | Go `NewTicker`; Python `with` / `finally` / `del` for cleanup; candidates: `docs/family_missing_keywords.md` |
| `dead` / `no-instances` | the oracle or the corpus has nothing; do not fix an engine rule to it | |
| the contract is `draft`, silent or contradicts itself | a **question**, not a bug | file it on #8863 and move on |

The mining report `docs/family_missing_keywords.md` lists, per family and language, the tokens the oracle saw in functions where the
family read 0 (`functions` = distinct missed functions). Regenerate with `python tests/tools/family_missing_keywords.py --sweep
--top 15 --out docs/family_missing_keywords.md` under `heavy-run.sh`.

Already-fixed is common: re-measure the cell on current `origin/main` before any edit. Of the 20 #8868 rows, about half were already
green or were an oracle error.

## Recipes
**Measure a language on the pinned crucible** (the only numbers that can be quoted):
```sh
python tests/tools/family_oracle_sweep.py            # scans <crucible>/data like the golden masters, scores every language
python tests/tools/family_red_cells.py --lang go     # the red cells with their contract sentences
```
**Quick triage on a real repository** (exploratory, never quoted): scan it with the worktree on `PYTHONPATH`, then
`python tests/tools/family_oracle.py DB --src REPO --lang go`. Corpora checked out on the box: `/nvme-data/gitgalaxy-data/<repo>`
(tokio, prometheus, vue, express, retrofit, redis).

**CPU cost**, per language, three alternating runs, report the mean of `user` seconds (never wall; never run beside another heavy job):
```sh
for i in 1 2 3; do for e in base branch; do /usr/bin/time -f "$e %U" env PYTHONPATH=<$e worktree> \
  <full_precision>/bin/python <$e worktree>/gitgalaxy/galaxyscope.py <crucible>/data/<lang> --output OUT --db-only; done; done
```
**keyword-rosetta**: in a worktree of keyword-rosetta off `origin/main`,
`GALAXYSCOPE_BIN=<v6>/.crucible_venvs/full_precision/bin/galaxyscope python tools/rebless.py <lang> --engine <worktree> --note x --dry-run`.
"nothing moved" means no `rosetta:rebless-owed`. If it refuses ("does not round-trip"), use `tools/verify_language.py <lang> --engine <worktree>`
against both main and the branch; PASS on both is the same answer.

**Golden masters** (never hand-edit): in the PR's own worktree, with `unset PYTHONPATH GALAXYSCOPE_BIN`,
```sh
GITGALAXY_DISABLE_GIT_HISTORY=1 LANGUAGE_CRUCIBLE_PATH=<language-crucible> python tests/tools/crucible_check.py --update --yes
```
then **attribute the diff**: unmodified `origin/main` must bless to zero changed files (if not, the baseline is stale: stop); the file-level
differences should be your language's files. Others are knock-ons: tiny coordinate and cluster-distance nudges, repository aggregates,
and files that embed your language (PHP with an inline `<script>`).

**A conflict in the golden fixtures** (main moved): `git merge origin/main`, then
`git checkout origin/main -- tests/golden_master_audit tests/golden_master_zero_dep_audit`, commit, and re-bless. Never resolve fixture
hunks by hand. A conflict in a source file is a real conflict: read it.

## PR checklist (paste into the PR; every line has a number or a "n/a, because")
- [ ] one language, one PR (two PRs editing one language file and the same fixtures conflict with each other)
- [ ] each cell re-measured on current `origin/main` first; cells already green are listed as "no change"
- [ ] each fix names its cause class from the table above, and the oracle was checked against the contract before the rule was touched
- [ ] oracle recall / precision before and after, on the pinned crucible (at least 10 functions per cell)
- [ ] a regression test with the positives **and** the false-positive forms that motivated the change
- [ ] CPU, three alternating runs, mean user seconds, base and branch
- [ ] keyword-rosetta: dry-run or verify result for this language
- [ ] goldens re-blessed in clean venvs; unmodified main blessed to zero changes; the diff attributed by language
- [ ] a "not in this PR" list for what was found and left, each with a reason
- [ ] draft first; `ruff check` and `ruff format --check` clean on the touched files; no unrelated reformatting

## An epic line a worker can claim
`python tests/tools/family_red_cells.py --slices` prints one per language:
`- [ ] **go**: 7 red cells (recall/precision: ...). Follow .claude/skills/family-validity-fix/SKILL.md. Done when every cell is 0.8 or better on the pinned crucible, or the contract is silent and a question is filed; one PR for this language only.`
Re-run it after every `family_oracle_sweep.py --write` and replace the epic's lines.

## Nightly
`tests/tools/family_sweep_nightly.py` re-measures the grid every night and keeps one standing draft PR (`bot/family-validity-baseline`)
with the new baseline and grid, regressions listed first, and the per-language epic lines. It shares `census-nightly`'s rules: it
needs `box_status` GREEN, runs once per main SHA per UTC day (stamp under `<scratch>/family-sweep-nightly/`), runs in a dedicated
worktree, and uses its own clone of the pinned language-crucible (never the shared checkout). It never force-pushes, never merges,
and never edits an engine rule: it measures and reports.

Units (user systemd, `~/.config/systemd/user/`): `family-sweep-nightly.service` and `.timer` (06:30 local). The service has
`ConditionPathExists` on the script, so the timer is a quiet no-op until the tool is on `origin/main` in the worktree
`/srv/storage_16tb/projects/gitgalaxy-worktrees/family-sweep-nightly`. Run it by hand with `--dry-run --force` (sweeps, prints the PR
body, publishes nothing). Pause it with `systemctl --user stop family-sweep-nightly.timer`.
