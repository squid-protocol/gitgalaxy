# Outcome-label pilot: do strictness and dynamism predict later fix commits? (#2720, child of #2716)

Reproduce with `tests/tools/outcome_pilot.py` (`clone`, `scan`, `label`, `analyze`; work dir `/tmp/gitgalaxy-scratch/claude/outcome-pilot`).
Ten repos is a pilot, not a calibration: it says whether the full build-out is worth it, and which way the first numbers point.

## Method

* **Repos (10):** curl, micropython, redis, mojolicious, guzzle, fastapi, serde, tokio, assemblyscript at their `data/PROVENANCE.json` pins,
  plus CardDemo (the only burned mainframe estate with an upstream history; its provenance copy sits inside the che4z repo, so the
  `aws-samples` upstream is used and the pin is the mid-history commit `2939d3db5f`, 2022-11-27). Whole upstream tree at the pin is scanned, not the
  crucible sample. No non-burned COBOL repo was cloned or read.
* **Fix commit:** non-merge commit whose subject matches the fix / bug / crash / leak / CVE / regression / revert family (`is_fix_subject`).
* **Later:** commits after the pin, inside a 730-day window capped by upstream HEAD, renames followed. The nine 2026 pins have only
  about 6-7 months of history, so their effective window is short; CardDemo has the full 24 months but 0 later fixes in scanned files.
* **Per file:** language strictness gaps (`strictness_gaps`, count of `False` columns of the file's own language row; files whose language has no row are left out),
  dynamism (`state_heat_triggers`, the DB column of `reflection_metaprogramming`, what #2719 reads), measured evidence (sum of 10
  structural-signal columns, dynamism excluded), LOC, later fix count. 9,107 files, 1,376 later fix commit-file hits, 735 files with at least one.
* **Equal evidence:** strata = repo x LOC decile x evidence quartile (edges per repo). Estimator: Mantel-Haenszel rate ratio of fixes per file
  across strata holding both groups; 95% CI from a stratified bootstrap (400 rounds).

## Label check (read by the PR author, seeded sample, 36 labelled-fix subjects from curl / redis / micropython / tokio)

* Precision: about 30 of 36 are fixes in shipped or tested code. The others are typos in docs or changelogs, CI runner fixes, or test-only fixes (6 of 36).
* Recall: about 8 of 36 unlabelled subjects read as fixes with no keyword ("dnscache: check hostname on lookup", "digest: flush state on origin or credential change",
  "tokio: drop stored waker when cancelling"). Subject-only labels undercount fixes; sample files are `handcheck/<repo>.tsv` in the work dir.

## Results

### Dynamism (per file, any `reflection_metaprogramming` hit vs none), all repos

| LOC x evidence strata | MH rate ratio | 95% CI |
|---|---|---|
| 3 x 3 | 1.81 | 1.57 - 2.14 |
| 6 x 6 | 1.39 | 1.22 - 1.63 |
| 10 x 4 (the tool default) | **1.27** | 1.09 - 1.49 |

Crude: 0.46 vs 0.07 fixes per file, 0.89 vs 0.60 per kLOC. The ratio falls as LOC is held tighter: file size explains most of the crude gap and
a smaller part survives. Per repo (10 x 4): curl 1.29 (1.06-1.63), redis 1.19 (0.84-1.77), micropython 1.10 (0.70-1.70), tokio 0.88
(0.46-1.64), guzzle 0.96, mojo 1.09 (0.18-10.4), fastapi 14.9 (1.4-91, 34 exposed files), assemblyscript 4.8 (0.99-28.8). Serde and CardDemo have no fixes to rank.
Only curl (a large repo) and fastapi (34 exposed files) have intervals that exclude 1.0; the pooled interval is carried mostly by curl and redis, the two repos with the most fixes.

### Strictness (gap count of the file's language), only inside repos with several language rows

Strictness is constant inside a language, so it can only be contrasted between languages of one repo (`curl`, `redis`, `micropython`, `fastapi`,
`assemblyscript`, `carddemo`); the contrast is therefore confounded with what the language is used for (C source vs shell/Tcl/Perl/Makefile tooling and tests).

| contrast | MH rate ratio | 95% CI | repos carrying it |
|---|---|---|---|
| >=3 gaps vs <=2 gaps, pooled | 0.68 | 0.53 - 0.87 | assemblyscript, curl, fastapi, micropython, redis (carddemo has none) |
| per repo: curl | 0.53 | 0.39 - 0.68 | |
| per repo: micropython | 2.32 | 0.95 - 4.39 | |
| per repo: redis | 5.17 | 1.55 - 25.6 | |
| >=3 vs <=1 (and >=2 vs <=1) | 0.14 | 0.04 - 0.84 | assemblyscript only (TypeScript sources vs JavaScript tooling) |

The sign flips between repos (curl and assemblyscript below 1, redis and micropython above), and the one repo that carries the (<=1) contrast compares source
to build scripts. No Rust (0 gaps) shares a repo with a language of more gaps, so the table's low end is untested.

## What this says about the weight in #2716 / #2719

* **Strictness:** no consistent predictive value at equal evidence. The pooled direction is opposite to the table's (0.68), and per-repo results disagree in
  sign. The pilot supports not raising the weight; it cannot show the term is zero either, because strictness is not separable from file role in these repos.
  Setting the weight to zero (the issue's stated consequence of "no predictive value") is the owner's call on this evidence; the language table stays documentation either way.
* **Dynamism:** a positive, size-sensitive association (1.27, CI 1.09-1.49 at the tightest stratification). It supports keeping the per-file term and
  gives a size for it: at most about a quarter more later fixes per file at equal evidence, with the interval's low end near 1.1.
* **Not shown:** that either term causes fixes; that 10 repos generalise; anything for COBOL (CardDemo: 0 later fixes in scanned files).

## Limits

Subject-only labels (precision ~83%, recall well below); effective follow-up of about 6-7 months for nine repos; a rate per file (equal follow-up) rather than per line;
one language row per repo for most repos; dynamism comes from one signal (`reflection_metaprogramming`); evidence is a plain sum, not the formulas' weighted view.

## Sibling gaps

* Full build-out to the 218 pinned repos with a longer horizon (or older pins) - no burned-estate program needs it; frontier.
* A repo pair that puts a 0-gap language beside a 3-4-gap language at equal role (e.g. Rust + build scripts) to test the table's low end - frontier.
* Burned mainframe estates beyond CardDemo (CBSA, GenApp, zECS, DBB, cicsdev async) with history, to test COBOL - only burned estates, so these are the in-scope next step; none needed by a program today.
* Recall of the fix label (trailers, linked issues, diff-verified fixes as in `temporal-crucible`'s harvesters) - sweep.
