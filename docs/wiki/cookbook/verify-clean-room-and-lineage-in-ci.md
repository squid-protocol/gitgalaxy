---
description: "Run automated clean-room, lineage, and horizontal-borrowing checks in GitHub Actions using structural-fingerprint-scanner."
---
# How to Run Clean-Room & Provenance Audits in CI

Teams maintaining clean-room reimplementations, cross-language ports, or regulated forks often need to verify on every pull request that new code neither unexpectedly mirrors an upstream call graph nor silently borrows an unapproved subsystem.

Using the `structural-fingerprint-scanner` composite GitHub Action, you can run a blind two-layer check in CI in seconds.

---

## 1. Add the GitHub Action Workflow

Create `.github/workflows/provenance-check.yml`:

```yaml
name: Structural Provenance Check
on:
  pull_request:

jobs:
  provenance:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout candidate PR
        uses: actions/checkout@v4
        with:
          path: candidate

      - name: Checkout reference baseline
        uses: actions/checkout@v4
        with:
          repository: your-org/reference-baseline
          path: baseline

      - name: Compare structure (Layer 1 + Layer 2)
        id: sfs
        uses: squid-protocol/structural-fingerprint-scanner@v0.1.0
        with:
          repo-a: baseline
          repo-b: candidate
          lens: portable

      - name: Check thresholds
        shell: bash
        run: |
          echo "FGW cost: ${{ steps.sfs.outputs.fgw-cost }}"
          echo "SE coverage: ${{ steps.sfs.outputs.se-coverage }}"
          echo "32-Keyword JSD: ${{ steps.sfs.outputs.kw-jsd }}"
```

The Action automatically writes a Markdown summary (`fgw_cost`, `se_n`, `se_coverage`, `kw_jsd`, `matched_kw_cos`, `matched_arch_agree`) to `$GITHUB_STEP_SUMMARY`.

---

## 2. Optional: Gate on Scan Quality First

Before failing a PR on structural metrics, verify that GitGalaxy extracted functions and signals cleanly for the languages in the PR:

```bash
sfs quality candidate/ --source candidate/ --verify --strict \
  --epic-issue --privacy paranoid --issue-out quality-epic.md
```

If `sfs quality --strict` exits with code `1`, downstream `fgw_cost` and `kw_jsd` numbers should be treated as inconclusive until the language's slicer/regexes are tuned.

---

## 3. Interpreting CI Results

- **Clean-room expectation (`fgw_cost > 0.70`, `se_coverage ~ 0%`):** Matches the empirical floor of from-scratch engines (`room4doom`, `rust-doom`, `helion`, `doome`, `DOOM-style-Game`).
- **Unexpected vertical homology (`fgw_cost < 0.60`, high `se_coverage`):** Indicates imperative call-graph alignment with the baseline (even across `C → Go` or renamed symbols/directories).
- **Localized horizontal borrowing:** Re-run locally with `--matches --json` to check whether `tier=0` and `tier=1` matches cluster inside a single subsystem (such as Chocolate Doom's `textscreen` module in `eternity` and `odamex`).

---

**[⬅️ Back to Master Index](../index.md)**
