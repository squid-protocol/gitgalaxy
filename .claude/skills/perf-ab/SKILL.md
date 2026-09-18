---
name: perf-ab
description: The honest measurement playbook for a GitGalaxy engine performance change -- how to A/B a scanning-hot-path optimization on a real repo without fooling yourself, and how to prove a "makes it faster, changes nothing" claim. Use when landing or reviewing a perf PR that touches the scan hot path (rule_prefilter, detector, prism, security_lens, galaxyscope phase code), when a perf ticket asks for a before/after number, or when the user says "measure it", "is it actually faster", "A/B this". Not for correctness-only changes.
---

GitGalaxy perf work lives in the per-file worker phases surfaced by
`--file-speed --splicing-speed` (`5_Optical_Detector`, `5.5_Security_Lens`,
plus per-regex/per-file tails). This skill is how #3069, #3072, and #3173 were
measured. Follow it or you will ship a number that is noise.

## 0. Setup (do this first, every time)
- `export GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER` -- without it a ~5s license
  delay skews every timing (see the `speed-test-license-key` memory).
- Run mega-repo scans with the **Bash sandbox OFF** -- batch scans get reaped on
  large repos otherwise (`batch-scan-needs-sandbox-off` memory).
- Drive the engine by **importing `gitgalaxy.galaxyscope.main()` over PYTHONPATH**,
  never the installed console script (it runs whatever is on PATH). Print
  `gitgalaxy.__file__` to confirm which engine actually ran.
- From a worktree, also set `KEYWORD_ROSETTA_PATH` / `LANGUAGE_CRUCIBLE_PATH` and
  use `v6/.venv` python, or you get phantom census MISMATCHes
  (`gitgalaxy-worktree-env` memory).

## 1. Measure with the harness
`tests/tools/phase_ab.py` does the whole loop -- alternating rounds, an A-vs-A
control, and the artifact-identity check:

    python tests/tools/phase_ab.py \
        --repo <mega-repo> --rounds 3 --control \
        --engine main=<worktree-at-base> \
        --engine mine=<v6-with-your-change> \
        --phase 5.5_Security_Lens          # add per-regex labels for #3174 etc.

The first `--engine` is the baseline every delta is measured against. Read the
per-phase mean + `Δ vs base`, and the wall.

## 2. The three rules that keep the number honest
- **Alternate the engines every round** (the harness does). "All A then all B"
  aliases background drift onto the comparison.
- **Run an A-vs-A control** (`--control`). It re-runs the baseline under a second
  label; its `Δ` is your **noise floor**. A real win must clear it and keep a
  **consistent sign across all rounds** -- a −8% delta next to a ±1% control is
  real; next to a ±6% control it is not.
- **Never scale a single-segment micro-bench to end-to-end.** Micro-benches on
  amalgamated mega-headers overstate -- galaxyscope SKIPS the amalgamated
  `simdjson.h`/`.cpp` in production. Check what the production path actually scans
  before believing an estimate (`next-perf-target-brace-slicer` memory).

## 3. Prove "changes nothing" on the DETERMINISTIC surface
`master.db` / `graph.sqlite` call lists carry hash-seed-order nondeterminism
(~128 rows differ between two IDENTICAL-engine runs on curl), so they are NOT a
valid diff surface. The deterministic surfaces are `audit.json` (ignoring the
nested `Analysis ISO Timestamp` / `Total Scan Duration`) and `sarif.json`. The
harness diffs exactly those; an output-preserving change must print `IDENTICAL`
for both against every engine.

For a change that gates/skips regex work, that artifact check is necessary but not
sufficient -- also prove the gate is **one-sided** over the corpus (a rejection ==
zero real matches), the way `tests/tools/gate_parity_audit.py` and
`tests/tools/scan_content_gate_parity.py` do: zero violations required.

## 4. Report without overclaiming
State the phase delta, the control noise floor, the round-by-round consistency,
the corpus/repo used, and Zero-Dependency Mode if active (numpy/tiktoken absent
is the historical baseline condition and is fine to report). Say plainly what you
could NOT measure -- e.g. **the node/vscode source trees used for the original
profiles are no longer on the box (only prior outputs remain); use
`all_language_repo`, `curl`, or `temporal-crucible-pool` as the present mega-repos**
and note the substitution. Some optimizations legitimately do not pay off (see the
`func_start` gating record) -- reporting a null result honestly is the job.
