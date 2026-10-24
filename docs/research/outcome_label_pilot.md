# Outcome-label pilot: do strictness and dynamism predict later fix commits? (#2720, child of #2716)

Reproduce with `tests/tools/outcome_pilot.py` (`clone`, `scan`, `label`, `analyze`; work dir `/tmp/gitgalaxy-scratch/claude/outcome-pilot`).
Ten repos (plus the five other burned estates, see below) is a pilot, not a calibration: it says whether the full build-out is worth it, and which way the first numbers point.

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

## Burned mainframe estates beyond CardDemo (second slice, #2720)

Added to `PILOT_REPOS` (`outcome_pilot.py clone|scan|label --burned-only`; `analyze` on a rows file holding only these). The local
`.mainframe_corpora` copies are single-commit squashes, so each estate is cloned from its upstream URL with history; the pin is mid-history
(first-parent midpoint, except zECS and DBB, which carry an explicit pin: a midpoint pin precedes their sources). No non-burned repo was cloned or read. Window and labeller are the first slice's.

| estate | upstream history | scanned files (rowed languages) | later fix hits | files with a fix |
|---|---|---|---|---|
| CardDemo | full | 106 (cobol 70, jcl 36) | 0 | 0 |
| CBSA | 443 commits, 2022-10 to 2026-07 | 272 (jcl 110, java 90, cobol 68, shell 2, batch 2) | 4 | 4 |
| GenApp | 20 commits, 2021-05 to 2026-07 | 76 (cobol 44, jcl 29, rexx 2, shell 1) | 24 | 22 |
| zECS | 20 commits, 2016-11 to 2017-07; pinned at the commit that adds the sources (`9ab1e35`) | 20 (jcl 10, cobol 7, hlasm 2, rexx 1) | 0 | 0 |
| DBB MortgageApplication | `zBuilder/MortgageApplication` only, moved in 2025-09-11; 2 commits touch it | 12 (cobol) | 0 | 0 |
| cicsdev async credit-card | 20 commits | 10 (cobol) | 0 | 0 |

Pooled with CardDemo: 496 files, 28 fix hits on 26 files. Dynamism MH rate ratio 0.73 (95% CI 0.14-2.5); the strictness contrasts have no
interval (their exposed groups carry 0 or 1 files with a fix). These numbers are not an estimate of anything, and they do not move the first
slice's conclusion:

* **22 of the 24 GenApp hits come from two commits both titled "COBOL updates and fixes"**, bulk edits across the tree, not fixes found by file.
  The subject-only label cannot tell a bulk update from a fix.
* **Label check (all fix subjects of the estates with any):** CBSA 5 labelled, about 2-3 are code fixes ("Fix bugs for Qube", "Bug fixes"; "Fix pictures",
  "Fix doc" are not); zECS 1 labelled (a markdown fix, in the window but touching no scanned source file); GenApp 2 labelled, both bulk. Precision for code defects is below the first slice's 83%.
* The estates are small, sample-style repos with few commits; with these windows they cannot give a COBOL rate. The honest result: COBOL stays
  untested, and the burned estates cannot test it by git history alone.

## DBB MortgageApplication, 2019 layout (third slice, #2720)

The second slice's sibling gap said `--follow` across the 2025 move would recover the 2019 history. It does not: `git show -M 0f8a61f` lists every
`zBuilder/MortgageApplication` file as an add, and `git log --follow` on `epscmort.cbl` stops at that commit. The tree was copied in, not renamed.
The 2019 sample lives at `Build/MortgageApplication` (committed 2019-03-16, `ecd713f`), so it is a separate `PILOT_REPOS` entry, `dbb-mortgage-2019`
(same upstream clone, `clone_as`), pinned there with the standard 730-day window (full follow-up, unlike the 2026 pins). Two tool changes were needed:
the aperture drops anything under a `Build/` directory, so the subtree is scanned at the snapshot root (`strip_subdir`) and the prefix is added back for
the history join; and `git archive` applies the repo's `zos-working-tree-encoding: ibm-1047`, turning the committed ASCII sources into newline-less EBCDIC
that the aperture refuses (line 1 over 500 chars), so the entry exports the committed blobs raw (`export_raw_tree`).

| estate | upstream history | scanned files (rowed languages) | later fix hits | files with a fix |
|---|---|---|---|---|
| DBB MortgageApplication 2019 | 18 non-merge commits touch the subtree inside the window | 12 (cobol 6 programs + 6 copybooks) | 0 | 0 |

* **All 18 commits touch build scripts only** (`build/Tools.groovy` 7, `build.groovy` 5, `build.properties` 4, `deploy.groovy` 3, ...); none touches a `.cbl` or `.cpy`.
  Groovy, properties and yaml have no strictness row, so they are left out of the rows by design.
* **Label check (all 8 labelled subjects in the sample, read by the PR author):** "Fixes #464/#460/#531/#534", "Fixes #464 and other bugs", "Fixed IDz User Build
  Dependency Path Issue" and two "fixes IBMDBB/DBB#N" YAML-sample commits are fixes to the build framework or its samples, not to COBOL. Zero are COBOL defects.
* **Result:** COBOL stays untested. This estate's COBOL was effectively frozen after its 2019 load; 12 files with 0 touches carry no rate. The pooled burned-estate
  numbers above do not change (no fix hit added). A longer-lived burned estate with COBOL churn is the only way to test it by git history; none exists.

## CBSA, maintenance-phase pin (fourth slice, #2720)

The CBSA pin in the second slice is the first-parent midpoint, which sits inside the 2022-12 to 2023-09 build-out (110 commits in 2023-01 alone, most of the
repo's renames). The `cbsa-late` entry (same upstream clone, `clone_as`) pins at `f15453b` (2023-10-19), after the renames and the 2023-08/09 burst, with the
standard 730-day window: the maintenance phase, where a defect found in shipped COBOL would show up as a later touch.

| estate | upstream history | scanned files (rowed languages) | later fix hits | files with a fix |
|---|---|---|---|---|
| CBSA, 2023-10 pin | 37 non-merge commits in the window | 264 (jcl 110, java 82, cobol 68, shell 2, batch 2) | 0 | 0 |

* **28 COBOL files are touched in the window, none by a labelled fix.** 146 JCL and 71 Java touches, also none by a labelled fix. The one labelled subject in the
  window ("Fix pictures", 2024-07-24) deletes four images; it touches no scanned source file.
* **Result:** COBOL stays untested: 68 files with touches but 0 fix hits carry no rate. The pooled burned-estate numbers above do not change.
  The late pin shows the other half of the second slice's CBSA row: the 4 hits there came from the build-out, and the maintenance phase of this
  sample repo is feature and documentation work.

## Bulk-commit guard and fix-label recall (fifth slice, #2720)

`outcome_pilot.py` gained `--max-files-per-commit N` (`label` / `analyze`: a commit touching more than N scanned files is credited to no file, renames still followed)
and a `recall` command (subject-only vs subject-or-body labels). Numbers below are from the 15 clones at their pins, 9,497 scanned files.

* **GenApp:** 24 fix hits on 22 files fall to 2 hits on 2 files at every N from 3 to 20. The two "COBOL updates and fixes" commits are bulk edits (each touches more
  than 20 scanned files), so the GenApp signal was the label, not the files. CBSA (4 hits), zECS, CardDemo, async credit-card, DBB: unchanged. COBOL stays untested.
* **The guard on the other repos (N=20):** 1,404 hits fall to 954 (curl 763 to 381, redis 332 to 286; micropython, tokio, fastapi, guzzle unchanged). It is a blunt
  tool for a repo like curl, whose wide commits include real tree-wide fixes, so it is a sensitivity check, not a replacement label.
* **Effect on the pooled answers (10 x 4 strata):** dynamism 1.27 (1.06-1.50) unguarded, 1.20 (0.98-1.50) guarded; strictness (>=3 vs <=2 gaps) 0.67 (0.53-0.84)
  unguarded, 0.73 (0.52-1.02) guarded. Direction and rough size hold; both intervals now touch 1.0.
* **Recall of the label (`recall`, window commits of the 15 clones):** 629 of 5,168 commits have a fix subject. A body label (a `Fixes #N` / `Fixes:` / `Bug:` trailer or a
  CVE id; `Closes #N` is excluded because curl puts it on every merged PR, features included) adds 179 more (curl 131, tokio 24, micropython 14, redis 9, guzzle 1; zero for the
  mainframe estates). Reading 18 of them (curl, tokio): about 10 are code fixes ("schannel: handle empty tokens during renegotiation", "mime.c: avoid integer overflow in
  base64 size calculation", tokio timer and waker fixes), about 8 are CI, docs or test changes. So the body label has roughly 55% precision and would lift the fix count by
  roughly 14%; it does not change the picture, and no mainframe estate gains a hit. A diff-verified label (harvesters as in `temporal-crucible`) is still the only way to measure true recall.

## Pooled memo for #2716 (all slices)

Posted on #2716: https://github.com/squid-protocol/gitgalaxy/issues/2716#issuecomment-6361780842 (2026-10-23).

* **Corpus:** 15 pins from 12 upstream repos (9 non-burned, plus CardDemo, CBSA twice, GenApp, zECS, DBB twice, async credit-card), 9,497 files with a strictness row, 1,404 fix-file
  hits on 761 files (954 on 526 with the bulk guard), 24-month window capped by HEAD (about 6-7 months for the nine 2026 pins).
* **Strictness:** no consistent predictive value at equal evidence. Pooled 0.67 (0.53-0.84) goes the opposite way to the table; per-repo signs disagree (curl 0.53, redis 5.2,
  micropython 2.3); the contrast is confounded with file role. It supports not raising the weight, and does not by itself prove zero; the call on setting the #2719 weight to zero is the owner's.
* **Dynamism:** positive and size-sensitive, 1.27 (1.06-1.50) pooled, 1.20 (0.98-1.50) with the bulk guard: at most about a quarter more later fixes per file at equal evidence.
  Supports keeping the per-file term at its present modest weight; carried by curl and redis.
* **COBOL / mainframe:** untested. Six burned estate pins have 4 fix hits in scanned files (CBSA) and 2 after the guard on GenApp; no rate can be computed. No burned program needs more.
* **Labels:** precision about 83% (subject), recall incomplete (body labels add about 28% more candidates at about 55% precision).
* **Not shown:** causation, generalisation beyond 12 repos, any COBOL effect.

## Limits

Subject-only labels (precision ~83%, recall well below); effective follow-up of about 6-7 months for nine repos; a rate per file (equal follow-up) rather than per line;
one language row per repo for most repos; dynamism comes from one signal (`reflection_metaprogramming`); evidence is a plain sum, not the formulas' weighted view.

## Sibling gaps

* Full build-out to the 218 pinned repos with a longer horizon (or older pins) - no burned-estate program needs it; frontier.
* A repo pair that puts a 0-gap language beside a 3-4-gap language at equal role (e.g. Rust + build scripts) to test the table's low end - frontier.
* Burned mainframe estates beyond CardDemo: done in the second slice above (CBSA, GenApp, zECS, DBB MortgageApplication, cicsdev async); too little history and too few fixes to test COBOL. Closing the COBOL question needs diff-verified fix labels (below) or a longer-lived burned estate - none needed by a program today.
* DBB MortgageApplication: done in the third slice above. The 2025 `zBuilder` tree is a copy (`--follow` cannot recover the 2019 history), and the 2019 `Build/MortgageApplication` layout has 0 touches on COBOL; no burned program needs more.
* CBSA: done in the fourth slice above (late pin, 0 fix hits). The `etc/install/base` to `springBootUI` move (2026-04) leaves 12 commits after it; too few for a pin.
* GenApp bulk-commit guard: done in the fifth slice (24 hits fall to 2).
* Recall of the fix label: trailer / linked-issue labels done in the fifth slice; a diff-verified label (as in `temporal-crucible`'s harvesters) is still open - sweep, no burned program needs it.
