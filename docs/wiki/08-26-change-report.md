---
description: "> **Command:** `gitgalaxy change REPO [--rev REV] [--base REV] [--scan-db DB] [--base-db DB]`. What a git change did: the lines that are one rename repeated, the TODO/FIXME markers it added and removed, and with a scan the functions it touched and who calls them. Read-only."
---
# Change Report

> **File Reference:** [`gitgalaxy/tools/sensors/change.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/sensors/change.py)
>
> **Command:** `gitgalaxy change REPO [--rev REV] [--base REV] [--scan-db DB] [--base-db DB] [--top N] [--json FILE]`
>
> **Metric:** For one change (a commit, or any two revisions), its size by role, the repeated renames in it, the debt markers it moved, and with a scan, the functions it touched (changed signatures first, with their callers) and the old debt markers in the touched files.
>
> **Summary:** A reviewer's first look at a diff: which part is one rename repeated and can be skimmed, and which touched functions many others depend on. A list and counts, no score.

## Engineering Summary
The git diff alone gives the first three sections (no scan needed). With `--scan-db`, a scan of the tree at `REV`, the changed line ranges are matched to the functions the scan found, and each is shown with its caller functions, caller files and one hop out, read the way [`gitgalaxy reach`](08-24-reach-sensor.md) reads them. With `--base-db` as well, a scan of the base, libraries whose coupling moved are listed (as [`gitgalaxy libsurface`](08-25-library-surface.md) computes them).

## Design
1. **Roles.** Changed lines are grouped as source, tests/docs and CI/config (the same rule `reach` uses).
2. **Repeated renames.** In a hunk that removes and adds the same number of lines, a line pair counts as a swap when exactly one call name left and exactly one call name arrived. A swap seen 5 or more times in the change is reported with its count, over all changed files. Comment lines and C type keywords before a parenthesis (`int (*cb)(...)`) are ignored.
3. **Debt markers.** Added and removed lines in source files that contain TODO, FIXME, HACK or XXX. A marker that only moved appears on both sides.
4. **Functions touched** (`--scan-db`): functions whose line span overlaps a changed hunk on the new side. **A function whose signature changed comes first and has its callers named**: the signature counts as changed when its parameter count differs between `--base-db` and `--scan-db`, or, without a base scan, when a changed hunk covers the line the function starts on. The rest follow, most-called first.
5. **Library coupling that moved** (`--scan-db` and `--base-db`): libraries whose files, sites or API names changed between the two scans.
6. **While you are here** (`--scan-db` with `debt_marker`, a scan from an engine that records marker positions): when the change adds or removes 50 or more source lines, the open TODO / FIXME / HACK / XXX markers in the touched source files, this author's own first and then the oldest. Age and author come from `git blame` of the marker's line at `REV` (up to 40 markers aged); a marker written by this change is left out. Without markers in the scan the section says "not measured".

## What it can and cannot say
- **How well the rename rule works** (six repositories, 567 sweeps the temporal study found): lines it flags are nearly always renames (in a hand read of 24 flags from three repositories, about 21 were genuine renames), but only 63% of flagged lines are a pure substitution (the new line equals the old with only the name changed), and it sees 57% of a sweep's functions at 90% or more. Renames mixed with other call changes on the same line are mostly invisible to it. So the report says "lines in these swaps", never "mechanical share". Method and numbers: the temporal-crucible note `docs/sensor-overhaul/sensors/change_aware.md`.
- The touched-function counts come from the scan: a call the scan cannot resolve is not counted, and the scan must be of the tree at `REV` (line numbers are matched as given).
- **Why callers are named for a changed signature:** they must agree with it, so they are the first place to look; it is a checklist. It is **not** where later fixes tend to land more than after other changes: an early result (curl 33% against 13% on 33 pairs; OpenSSL and FreeBSD pooled 3.83 times a same-file baseline on 29 pairs; 1.23 across seven repositories without named causes) did not hold with 2,962 kernel pairs, where the caller excess after a signature change (2.27 times a same-file baseline within one call) is no larger than after other changes (2.48). See [Blast Radius of a Change](08-28-blast-radius.md).
- **Why 50 lines** for the marker list: in a back-test on three repositories, markers surfaced by this rule were repaid in that same change in 3.4% of cases against 1.3% when every marker was shown, about 2.6 times (exploratory, one run, no pilot yet). Treat the rule as a starting point.
- A signature found by a hunk on the declaration line also catches a renamed or retyped declaration, not only a parameter count.

## Examples
`gitgalaxy change repo --rev 8bb32e578` on libgit2 reports `git_odb__hashfile -> git_object_id_from_file x22`: 44 of 517 changed lines.
