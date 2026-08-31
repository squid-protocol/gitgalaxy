# The GitGalaxy Validation Program

This is the full narrative of how GitGalaxy's claims get tested — the thesis, the
three-tool structural benchmark, the cross-language control corpus, the validity
ladder, and the next experiment. [`README.md`](../README.md) carries the summary;
this document carries the whole argument, with every number linked to the artifact
behind it.

------------------------------------------------------------------------

## The structural-extraction thesis

GitGalaxy deliberately does **not** begin by constructing a complete AST for every
language.

It uses approximately 97 structural-signal categories to identify things such as:

-   function and method boundaries
-   classes and declarations
-   arguments
-   branches and control flow
-   state mutation
-   I/O
-   APIs and routes
-   imports and dependencies
-   unsafe operations
-   reflection and dynamic execution
-   concurrency
-   closures
-   globals
-   entropy and physical-file anomalies

This creates a specific, testable hypothesis:

> **For repository-scale intelligence, targeted structural extraction can recover
> the entities required for useful code intelligence without requiring a complete
> language parser for every file.**

That hypothesis is being tested empirically, on three independent axes: accuracy
against established parsers (below), measurement consistency across languages
(the control corpus), and — next — correspondence with real software evolution
(risk over Git history).

------------------------------------------------------------------------

## Structural validation: GitGalaxy vs Tree-sitter vs Ctags

This is currently one of the most important validation programs in the project.

GitGalaxy is being evaluated against **Tree-sitter and Universal Ctags** on the
same [Language Crucible](https://github.com/squid-protocol/language-crucible)
corpus.

The first structural targets are:

-   functions
-   classes
-   arguments

The benchmark is deliberately **not** treated as a three-tool popularity contest.

When tools disagree:

1.  the disagreement is recorded;
2.  the source is inspected;
3.  each tool's behavior is investigated;
4.  GitGalaxy is fixed when GitGalaxy is wrong;
5.  comparator/adaptor code is fixed when the comparator is wrong;
6.  genuine tool limitations are documented;
7.  the result is re-measured.

**24 of 45 languages get all three tools compared, 13 more get two, and 5**
(`abap`, `agc_assembly`, `dockerfile`, `jcl`, `livecode`) **use committed manual
verification** — in whole, or for the `args` metric where no tool emits a
signature — instead of cross-tool agreement. Of the 201 discrepancy shapes
logged, **200 are validated (99.5%)** — read against real source, investigated,
and recorded with a verdict, not just counted.

**Current state (2026-08-30), on the pinned corpus:**

- **Functions — precision:** 100.0% validated across all 31
  tree-sitter-comparable languages. Once every three-way disagreement is read and
  verdicted, every function GitGalaxy reports is a real function.
- **Functions — recall:** 100.0% for 30 of 31. Shell measures 99.8% — a single
  nested function definition (inside an `if` guard) that GitGalaxy's
  top-level-only shell extractor doesn't reach by design. Every other apparent
  miss is a validated comparison-tool artifact (both tools independently
  hallucinating the same macro, per-clause tagging of one Haskell function, and
  so on).
- **Classes:** GitGalaxy is never the tool found wrong in any class disagreement
  — 100.0% validated recall and precision wherever a class ground truth exists.
- **Arguments:** GitGalaxy is never debited in any *validated* argument
  disagreement either; each one resolves to tree-sitter or ctags miscounting, or
  a language with no formal parameter list. One small Objective-C shape is still
  unverified.

This is a narrow benchmark: three structural targets, one fixed corpus, and
several languages whose entity counts are small enough that a percentage means
little. It is not "GitGalaxy parses as accurately as an AST" in general — it is
"for the entities GitGalaxy's graph needs, targeted extraction recovers them as
completely as established parsers, here." Real code outside the corpus will
surface shapes it doesn't cover; the mandatory occurrence-level
[recall audit](self_scan/tri_comparison_README.md#the-recall-audit-is-gitgalaxy-missing-anything)
is the standing process for the next one.

![Tri-comparison](self_scan/tri_comparison_chart.svg)

See:

-   [the tri-comparison methodology doc](self_scan/tri_comparison_README.md) —
    how matching, the ledger lifecycle, the recall audit, and CI enforcement work
-   [`tests/tools/tri_comparison_chart.py`](../tests/tools/tri_comparison_chart.py)
-   [`docs/self_scan/tri_comparison_ledger.json`](self_scan/tri_comparison_ledger.json)
    — the full, per-shape validated record
-   [`docs/self_scan/tri_comparison_points_of_interest.md`](self_scan/tri_comparison_points_of_interest.md)
    — the same ledger, rendered and ranked by signal strength
-   [`docs/self_scan/how_to_investigate_a_discrepancy.md`](self_scan/how_to_investigate_a_discrepancy.md)
-   [`docs/self_scan/manual_verification.json`](self_scan/manual_verification.json)

### What the benchmark is actually asking

Not:

> "Is GitGalaxy a better parser than Tree-sitter?"

But:

> **"For the structural entities GitGalaxy needs to build its repository graph,
> how accurately can targeted structural extraction recover them compared with
> established parsing and indexing systems?"**

That is the narrower claim the experiment can support.

### Languages without suitable comparator coverage

Some languages do not currently have a suitable independent Tree-sitter/Ctags
comparison path.

Those are kept in a separate evidentiary category and use committed manual
verification rather than pretending cross-tool agreement exists.

This currently includes languages such as:

-   ABAP
-   Dockerfile
-   JCL
-   LiveCode
-   YAML

Where practical, the next step is to add independent lexical, grammar-based, or
domain-specific comparators. Where no credible independent comparator exists,
human-verified ground truth remains the appropriate category.

------------------------------------------------------------------------

## Cross-language consistency: the Keyword Rosetta control corpus

The tri-comparison above asks *"does GitGalaxy find real structure?"* A separate
control corpus, [keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta),
asks the orthogonal question: *"does GitGalaxy measure identical intent
identically across languages?"*

The same 12-probe, functions-only program shell is hand-planted in **all 46
supported languages**, with the exact count of every signal keyword known in
advance. Any column-to-column divergence on that corpus is measured language
bias — an extraction inequality or a scoring inequality — because the planted
intent is identical by construction.

Current results
([bias report](https://github.com/squid-protocol/keyword-rosetta/blob/main/docs/bias_report.md)):
across 33 comparable metrics, on average **75% of languages land within ±25% of
the cross-language median** — but under the strict gate (no language beyond ±50%
of the median), only **3 of 33 metrics pass** cross-language validation today.
The weakest metrics are named, not hidden: `risk_cognitive_load` holds only 15%
of languages in the ±25% band, `risk_api_exposure` 43%, `state_mutation` 46%. Every known
deviation is recorded in a validated
[deviation ledger](https://github.com/squid-protocol/keyword-rosetta/blob/main/deviation_ledger.json),
and the defect classes found this way are filed as GitGalaxy issues — see the
[findings-by-language index](https://github.com/squid-protocol/keyword-rosetta/blob/main/docs/findings_by_language.md).
A companion
[incidence report](https://github.com/squid-protocol/keyword-rosetta/blob/main/docs/incidence_report.md)
sizes each confirmed shape against real licensed code, separating constant
per-file biases (e.g. PHP's open tag counting as a branch in 100% of files) from
sparse per-repo hazards.

What this proves and doesn't: a control corpus demonstrates measurement
*inequality* on identical intent with zero ambiguity, but says nothing about
accuracy on real code (that's the tri-comparison's job) and nothing about whether
a biased metric is still *usefully ranked* within a single language (a constant
per-file offset preserves ordering inside that language).

------------------------------------------------------------------------

## Validation is a ladder

GitGalaxy's evidence is being organized around progressively stronger questions.

### 1. Structural validity

**Does GitGalaxy correctly identify code structures?**

Tree-sitter + Ctags + independently investigated disagreements. See
["Structural validation" above](#structural-validation-gitgalaxy-vs-tree-sitter-vs-ctags).

### 2. Measurement consistency

**Does GitGalaxy measure the same intent the same way in every language?**

The [Keyword Rosetta control corpus above](#cross-language-consistency-the-keyword-rosetta-control-corpus)
— exact planted signal counts, 46 languages, validated deviation ledger.

### 3. Regression validity

**Does the implementation remain stable on real code?**

[Golden-master testing](../tests/tools/update_golden_master.py) against
[Language Crucible](https://github.com/squid-protocol/language-crucible).

### 4. Scale validity

**Does it work on real repositories?**

Unedited raw scan output from
[hundreds of repositories](https://github.com/squid-protocol/gitgalaxy-raw-output).

### 5. Model validity

**Do structural signatures correspond to the exposure categories they are
intended to represent?**

Statistical analysis against independently observable outcomes---not merely
against GitGalaxy's own equations.

### 6. Temporal validity

**Does exposure behave sensibly as software changes?**

Git-history analysis comparing repository states before and after real changes.

### 7. External validity

**Do exposure changes correspond to independently documented security or
maintenance outcomes?**

Future work: security fixes, regressions, advisories, defects and other external
event datasets.

This distinction matters: a score can be internally consistent without
necessarily being externally meaningful.

------------------------------------------------------------------------

## The next validation: risk over Git history

Once structural validation is sufficiently mature, GitGalaxy can test its
exposure model longitudinally.

``` text
Git history
    |
    v
security-relevant event
    |
    +-------------------+
    |                   |
    v                   v
parent state        changed state
    |                   |
    v                   v
GitGalaxy scan      GitGalaxy scan
    |                   |
    +---------+---------+
              |
              v
        exposure delta
              |
              v
     independent event class
```

The central experiment is:

> **Do commits independently identified as security fixes typically reduce the
> corresponding GitGalaxy exposure?**

Negative controls are equally important:

> Do ordinary development commits show the same behavior?

Eventually:

> Do security regressions increase exposure?

The planned harness will preserve commit SHA, parent state, changed
files/functions, exposure before/after, exposure deltas, structural changes and
event classification.

That tests:

**structure → exposure → real software evolution**

rather than merely testing the internal mathematics of the exposure model.

------------------------------------------------------------------------

## Current research direction

GitGalaxy is moving through a sequence of increasingly difficult questions:

> **Can we scan heterogeneous source without compiling it?**

↓

> **Can we reliably recover the structural entities needed to understand it?**

↓

> **Do those structural measurements correspond to meaningful risk exposure?**

↓

> **Does measured exposure behave correctly as real software evolves?**

The Tree-sitter/Ctags validation is currently about halfway complete. The
immediate priority is to finish that audit before turning preliminary
measurements into stronger claims.

The next major experiment is:

**Git history → independently identified change/fix events → GitGalaxy
before/after scans → exposure deltas → statistical analysis.**

That is where GitGalaxy can begin testing not only whether it *sees* structure,
but whether its structural model **tracks meaningful changes in real software**.
