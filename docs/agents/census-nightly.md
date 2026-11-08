# Local census run (#6064)

The nightly CI survey is `--no-census` (census clones never reach CI or a commit: blind-estate rule). The non-burned
translation rate comes from `tests/tools/census_nightly.py`, run on the owner box.

## What a run does
1. `box_status.py` must say GREEN, else it exits 0 ("skipped"). `--force` ignores the verdict, the stamp and the cache.
2. One run per main SHA per UTC day (stamp `<scratch>/census-nightly/<date>-<sha>.done`, written after a publish), and none
   when the published census series already holds the SHA.
3. `equivalence_env.py --provision`, then `nice -n 10 cics_census.py survey --baseline --jobs 2 --no-fetch --sha SHA`
   (census included; the #6124 root check refuses a wrong census root).
4. `history append --nightly` into `docs/language_status/blockers/census_history.jsonl` and a push of that one file to
   `generated`. `counts_only` refuses a line with a key outside the history schema, or one that names the census root or a
   census repo. `blockers.txt` / `.json` / `meta.json` (program rows) are never published; `cics_census.py publish` still
   refuses a census baseline.

## On demand, after a merge
`python tests/tools/census_nightly.py --after-merge SHA` runs the same gates, stamp and `counts_only` for one commit (full or
short SHA). It fetches `origin main` first and refuses a SHA that is not an ancestor of, or equal to, `origin/main`, so no
unmerged commit is ever published. Its stamp is the nightly's, so a SHA run on demand is not run again that UTC day. The
census series on `generated` is the one source of census rows: no PR appends a history or register line for it
(blocker-slice section 4, #7962). Churn triggering this after a census-linked merge is tracked on the promoter-bot side.

Read the series: `python tests/tools/cics_census.py history show --generated --series census`. Local check without a push:
`python tests/tools/census_nightly.py --dry-run --force`.

## Blind trial (#8077)
The blind estate is surveyed alone, through the same tools, into its own series. It is pinned by hand (never provisioned)
and its source is never read: tools run over the clone as is, and only counts leave the box.
- `cics_census.py survey --baseline --blind-root DIR [--sha SHA --no-fetch --root SCRATCH]`: only the blind corpora, at
  that commit's translator, cached under `<scratch>/blind-cache/<sha>` (never the census cache). `--blind-root` refuses a
  root holding a census or burned corpus, and contradicts `--census-corpora`, `--no-census`, `--crucible`, `--corpora`.
  `survey --out DIR --blind-root DIR` is the same without the cache.
- `census_nightly.py --after-merge SHA --blind-root DIR`: the per-merge measurement, with the same gates, `counts_only`
  and stamp (`blind-<date>-<sha>.done`), published to `docs/language_status/blockers/blind_history.jsonl` on `generated`.
  `--blind-root` without `--after-merge` is refused. Read it: `cics_census.py history show --generated --series blind`.
- `gap_prevalence.py --census-survey <blind-cache>/<sha> --blind-root DIR`: whole, accounted and coverage-if-closed
  counts plus the scrubbed gap table to stdout; it writes nothing (`--write` is refused).

## Install (owner step; the units live outside the repo, in `~/.config/systemd/user/`)
The unit runs from a dedicated detached worktree moved to `origin/main` before every run: the code that runs is whatever is
checked out, and the `v6` checkout lagged main by 299 commits on 2026-11-06, so a unit pointed there publishes stale counts.
Create it once: `git -C /srv/storage_16tb/projects/gitgalaxy/v6 worktree add --detach /srv/storage_16tb/projects/gitgalaxy-worktrees/census-nightly origin/main`.

`census-nightly.service`:
```ini
[Unit]
Description=GitGalaxy local census run (counts only to the generated branch)
[Service]
Type=oneshot
WorkingDirectory=/srv/storage_16tb/projects/gitgalaxy-worktrees/census-nightly
Environment=PATH=/srv/storage_16tb/projects/gitgalaxy/venvs/selfscan/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=/usr/bin/git -C /srv/storage_16tb/projects/gitgalaxy-worktrees/census-nightly fetch -q origin main
ExecStartPre=/usr/bin/git -C /srv/storage_16tb/projects/gitgalaxy-worktrees/census-nightly checkout -q --detach -f origin/main
ExecStart=/srv/storage_16tb/projects/gitgalaxy/venvs/selfscan/bin/python tests/tools/census_nightly.py
Nice=10
IOSchedulingClass=idle
TimeoutStartSec=7200
```
`census-nightly.timer`:
```ini
[Unit]
Description=Daily GitGalaxy census run
[Timer]
OnCalendar=*-*-* 05:30
Persistent=true
[Install]
WantedBy=timers.target
```
Then `systemctl --user daemon-reload && systemctl --user enable --now census-nightly.timer`. A RED/YELLOW box skips that
day's run; the next firing tries again. The push needs the box's git credentials for `origin`.
