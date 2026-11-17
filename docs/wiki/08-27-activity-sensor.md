---
description: "> **Command:** `gitgalaxy activity REPO [--rev REV] [--scan-db DB]`. How active each file is, how long it has been settled and who looks after it, from git history alone, in plain units. Read-only."
---
# Activity Sensor

> **File Reference:** [`gitgalaxy/tools/sensors/activity.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/sensors/activity.py)
>
> **Command:** `gitgalaxy activity REPO [--rev REV] [--scan-db DB] [--top N] [--json FILE]`
>
> **Metric:** Per file: commits in the last 365 and 90 days, days since the last change, age in years and lifetime commits, authors in the last year, the top author's share of the last year's commits, and whether that author has committed in the last two years.
>
> **Summary:** The proposed replacement for the two history gauges (`hist_churn`, `hist_stability`; they are unchanged for now), which are one measurement in two forms: readings that stand on their own, and worklists a person can act on. Plain counts and dates, no score and no risk claim.

## Engineering Summary
One `git log -M --name-status` over the whole history (seconds: curl, 4 s). Each file keeps its identity through renames and copies, so a file moved by a reorganisation keeps its age and its history. "Now" is the commit time of `--rev`. Merge commits are left out.

## Why the old pair was replaced
The two engine gauges are the 365-day commit count (churn, rank correlation 0.96) and days since the last change (stability, 0.97), and these two are strongly opposed (about -0.86 within a repository): one axis, shown twice. Of eight horizon features studied, the 365-day window carried the prediction of later fixes; 30- and 90-day windows and lifetime counts added nothing. Details and tables: the temporal-crucible note `docs/sensor-overhaul/sensors/activity.md`.

## Design
1. **Readings**, one row per file present at `REV`, all in plain units. Age is years since the file's first commit, followed through renames.
2. **Roles.** Each file is source, tests/docs, ci/config or other (prose and data: markdown, JSON, YAML, XML, HTML, CSS, CSV). Lists default to source files.
3. **Hot now.** The top tenth of active source files by 365-day commits.
4. **Ownership context.** Active files where one author made 60% or more of the last year's commits and has not committed anywhere in two years, or made 90% or more. This describes who looks after a file; in the study its direction changed between repositories, so it is context, not a risk list.
5. **Dormant.** Source files untouched for two or more years. With `--scan-db` (a scan of the same tree) the ones in the top tenth by number of files that call into them are listed as **quiet foundations**.

## Stored in the scan database
Every scan of a git checkout now records the plain readings per file in `file_data`, from the Chronometer's own pass (no command to run): `commits_365d`, `commits_90d`, `days_since_last_change`, `authors_365d`, `top_author_share_365d`. NULL means not measured: no usable history (not a git checkout, a shallow clone, `GITGALAXY_DISABLE_GIT_HISTORY`), a pass cut by its commit cap, or a file the dating pass did not reach.
- The year is the year before **HEAD's commit time** in every mode, never the wall clock, so the same history gives the same numbers on every machine and on every day. The pass is complete (the churn pass's coverage and time guards do not apply) and is cut only by a commit count, `ACTIVITY_MAX_COMMITS` (150,000; past it every reading is NULL) and `ACTIVITY_DATING_MAX_COMMITS` (250,000; past it a file untouched for the whole year has no date).
- Differences from the command: the columns follow paths without following renames (the command follows them with `git log -M`), count only the year, and leave out revisions in `.git-blame-ignore-revs`; age since the first commit, lifetime commits and whether the top author is still active are not stored yet (they need the whole history).
- `risk_churn` and `risk_stability` (`hist_churn`, `hist_stability`) are kept for now as deprecated aliases of the same history in a different form; the columns above are what to read.

## What it can and cannot say
- Measured against the research mock-up (same definitions, computed independently with numpy), the command gave identical values for all 8 readings on every file of curl, libgit2 and libxml2 (24,149 files; the days reading is rounded to a tenth). This checks the implementation, not the rename logic (the same rule is used by both).
- In the three-repository study, hot files carried about 1.8 to 2.5 times the later-fix rate of active files (1.4 to 1.8 for source files only), and quiet foundations were below the base rate: fixes land in busy files, not in quiet ones that much depends on. The list says so rather than flagging them as risky.
- Not here yet: the share of a file's recent edits that were sweeps (it did not separate fix-prone hot files in the study), change entropy, co-change scatter, and persisting these readings into the scan database.
- A shallow clone gives short ages and the command says so. A directory that is not a git repository is an error, not a zero.
