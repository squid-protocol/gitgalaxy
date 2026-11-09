---
name: estate-trial
description: Run a blind-estate trial of the engine (the #7709 census mock trial is the template; #3803 is the real blind one) -- counts-only preflight, freeze main at T0, tools-only measurement loop, owner rulings, close-out against the accounted bar, write-up -- with the mock trial's numbers as calibration, the source-defect rule, and the ask-the-customer list for a real estate. Use when the user says "estate trial", "blind trial", "census trial", "T0 re-survey", "preflight the census", or briefs an agent on #7709 / #3803 style work. For picking each slice use blocker-slice; for the rules on what may be read use mainframe-evidence-policy.
---

A trial measures the engine on code nobody has tuned it to. Its value is the first-contact number, so the protocol's
job is to keep that number honest. Rules: `.claude/rules/mainframe-evidence-policy.md` (esp. 3 blind estate, 10 source
defect). Template: #7709 (mock trial on the 39 census programs); the real one is #3803.

## 1. Before T0: preflight (counts only)
```sh
python tests/tools/cics_census.py preflight [--census-corpora DIR] [--root DIR] [--t0 SHA]
```
Exits non-zero on any finding; fix each before the trial starts. It checks: programs vs copy members (a data-only copy
member is not a program, #7901), copybook prefixes in neither the estate nor the IBM product list (#7899), every owner in
the gap map is an open issue or the row is accounted (#4767 / #4270), the census dir holds only the census corpora
(a stray `before-nb-local` counted 51 programs), the T0 SHA is recorded, and the copybook-resolution census
(#8111, `copy_resolution_census.py`: the engine's COPY resolver against a plain by-name file search, one scan per repo)
counts no member the engine misses or mispicks (final measurement 2026-11-09: 0 on the burned estates and on non-candidate `corpus_cobol`; the rest is `absent` clone faults, 2 stated ambiguous refusals and vendored importers). Measure it standalone only on burned estates, fixtures and non-candidate
`corpus_cobol`: the tool skips a candidate, census or non-burned ledger repo by basename (counting one spends it).

## 2. Freeze main at T0
Record the SHA (`--t0`, or `census-t0.json`). Estate-targeted PRs wait for T0 (#7714 and #7673 merged before it and
muddied the baseline). T0 measures main as is: `cics_census.py survey`, then `gap_prevalence.py --census-survey ...
--write`; post the rate. The series of per-SHA rows is generated (`history show --generated --series census`), no PR
appends a row (blocker-slice section 4).

## 3. Tools-only loop
* Nobody reads estate source, and nobody makes an edited, patched or excerpted copy of it, even unprinted (rule 3).
  Tools run over the clone as is, with aggregate or scrubbed output (`--unmask` must not print names, #7755).
* A fix gets a gap label, the IBM manual page and the owning issue, and proves itself on our own fixture or a burned
  program. A finding that needs more is reported "needs a fixture".
* Measure after each merge with the tool (`census_nightly.py --after-merge SHA`); every refusal needs an owner row, not
  an unowned `other` (#7906).
* L1 only: translates whole. No claim about L2+.

## 4. Source defects (rule 10)
A gap becomes a named source defect only with an IBM citation in its owner text and an Opus review. Product copybooks are
unaccounted frontier work, not defects. Do not relabel a row back and forth: a flip needs a new citation.

## 5. Owner rulings
Collect each ruling in the issue with its date and put it in the policy file when it outlives the trial (basis 39,
product copybooks unaccounted, tightened rule 2 were the mock trial's).

## 6. Close-out and write-up
Time box 14 days from T0. Report accounted = whole + named source defects, over the program basis (programs only, copy
members listed separately). Publish the ledger as it stands: predicted vs actual, new gaps exposed, cost in PRs and hours,
named-not-fixed. Evidence levels, never "proven" (rule 1).

## 7. Calibration (the 39-program mock trial, #7709)
* First contact: about 20% whole (8 of 40 at the 2026-10-24 baseline).
* About 2 days of work reached about 30% whole and about 90% accounted.
* About 40% of PRs are measurement (tool, preflight, census plumbing), not translator work.
* Expect 1-2 feature-sized constructs at 10-20 PRs each (the prediction of 35-45 PRs for 9 small classes undercounted these).
* Bugs that only the trial exposed (each could skew a blind result): copy member counted as a program, product-copybook
  list lacking `BAQ` / `HWT`, gap rows naming closed owners, `--unmask` printing names, refusals collapsed into `other`.

## 8. Ask the customer (a real estate, up front)
Missing members and product copybooks capped 11 of 39 census programs, so ask before the first scan:
1. The **full copybook libraries** every program COPYs from (every library in the compile / SYSLIB concatenation).
2. The **IBM product list**: which products the estate runs (CICS TS release, Db2, MQ, IMS, z/OS Connect, LE, others) so
   product copybooks are known, not guessed. IBM's copybooks are never shipped (rule 6): the customer's own install has them.
3. The compile options per program (NUMPROC, TRUNC, CODEPAGE, SSRANGE, ARITH, DYNAM) and the JCL / procs that set them.
4. Which members are programs, copy members, BMS maps, JCL, screens (ISPF panels are not COBOL).
5. A statement of which programs are live, and a sample of real inputs only if the customer chooses to share them.
