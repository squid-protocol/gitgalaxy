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

Read the series: `python tests/tools/cics_census.py history show --generated --series census`. Local check without a push:
`python tests/tools/census_nightly.py --dry-run --force`.

## Install (owner step; the units live outside the repo, in `~/.config/systemd/user/`)
`census-nightly.service`:
```ini
[Unit]
Description=GitGalaxy local census run (counts only to the generated branch)
[Service]
Type=oneshot
WorkingDirectory=/srv/storage_16tb/projects/gitgalaxy/v6
Environment=PATH=/srv/storage_16tb/projects/gitgalaxy/venvs/selfscan/bin:/usr/local/bin:/usr/bin:/bin
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
