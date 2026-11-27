---
name: family-validity-remeasure
description: Refresh the keyword-family validity baseline on the pinned language-crucible, regenerate the grid, and rewrite the per-language red-cell lines in epic #8863 so churn always has current, launchable work. Use after a batch of family fixes merges, nightly or weekly, when the grid looks stale, or when churn reports the Eagle Eye focus has nothing launchable. NOT for fixing a cell (family-validity-fix).
---

# Re-measure the grid and refill the epic

The grid is a pure function of `tests/family_validity_baseline.json`, and the baseline only changes when someone sweeps. Fixes do
not show until a sweep runs, and churn picks work from the epic's `- [ ]` lines, so a stale baseline both hides progress and
starves the focus.

1. **Pin and sync**: `python tests/tools/crucible_pins.py sync` so `language-crucible` is at the pinned tag; the sweep refuses a
   checkout off the pin.
2. **Sweep under the box gate**: `tests/tools/box/heavy-run.sh python tests/tools/family_oracle_sweep.py --write` (it scans
   `<crucible>/data` the way the golden masters do, scores every oracle language, and merges the cells into the baseline).
   Check `box_status` is GREEN first; the scan is heavy.
3. **Regenerate the grid**: `python tests/tools/family_validity_chart.py` ; the README chart is rendered from the baseline by CI and published, never committed or edited.
4. **Rank what is left**: `python tests/tools/family_red_cells.py` (and `--slices`). Compare with the previous baseline: list the cells that
   went green, any that fell (a regression: open it first), and new cells.
5. **Refill the epic**: replace the per-language `- [ ]` lines on #8863 with the `--slices` output, tick finished languages, and
   keep the lines that wait on an owner question marked as such. Each line must be launchable by one worker with no further input.
6. **Open one draft PR** with the baseline and chart, titled "Refresh the family-validity baseline", with the before and after
   counts (red cells, languages, families). Part of #8863.
7. **Tell churn the focus is fed**: `churn focus` should list queued items for #8863; if it still says "nothing launchable", the lines
   are not in a shape the queue reads (a `- [ ]` line with an issue or a skill and a finish line).

Report: cells red before and after, languages fully green, regressions, and the lines now on the epic.
