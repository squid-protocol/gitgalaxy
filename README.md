# GitGalaxy

**Repository-scale structural intelligence without compilation.**

[Docs](https://squid-protocol.github.io/gitgalaxy/) ·
[Visualizer](https://gitgalaxy.io/) · [Language
Crucible](https://github.com/squid-protocol/language-crucible) · [Raw
Output](https://github.com/squid-protocol/gitgalaxy-raw-output)

**1 scan · 97 structural signals · 50+ languages · no compilation · 19
risk-exposure categories · 6 outputs**

## The short version

GitGalaxy builds a **language-agnostic structural graph of an entire
repository** directly from source text.

It is designed for repositories that are polyglot, partially broken,
legacy, vendor-heavy, or otherwise difficult to analyze through a
build-first workflow.

Instead of requiring a successful build and a separate parser/toolchain
for every language, GitGalaxy extracts a common vocabulary of
**structural signatures**---functions, classes, arguments, control flow,
state mutation, I/O, APIs, dependencies, and other signals---and
normalizes those observations into one repository model.

The same graph can then feed:

-   architecture analysis
-   risk-exposure prioritization
-   dependency/SBOM analysis
-   refactoring and ownership analysis
-   legacy-code analysis
-   AI-oriented codebase context
-   CI/CD workflows
-   historical risk analysis

> **Central thesis:** complete language parsing is not always necessary
> to recover highly useful structural information at repository scale.

------------------------------------------------------------------------

## The problem

Large repositories routinely contain:

``` text
Go + C++ + Python + Java + Bash + YAML
+ generated code + vendored code + legacy code
+ half-migrated modules + broken dependencies
```

Traditional language tooling can be excellent within its intended scope
while still leaving the repository fragmented across language-specific
representations.

GitGalaxy makes a different trade:

``` text
Source repository
       |
       v
Structural signatures
       |
       v
Normalized entities + risk signals
       |
       v
Deterministic repository graph
       |
       +---- Architecture
       +---- Risk exposure
       +---- Dependencies / SBOM
       +---- AI context
       +---- Refactoring
       +---- Git-history analysis
```

The objective is **not** to reproduce every syntactic detail of every
language.

The objective is to recover the structural information downstream
repository intelligence actually needs.

------------------------------------------------------------------------

## One graph, many consumers

GitGalaxy's core output is a deterministic structural representation of
the repository.

  -----------------------------------------------------------------------
  Consumer                            Question
  ----------------------------------- -----------------------------------
  Architecture                        What is this repository made of?

  Structural analysis                 Where are the functions, classes,
                                      APIs, dependencies and control
                                      structures?

  Risk exposure                       Where are potentially important
                                      risk patterns concentrated?

  Refactoring                         Which files are complex, high-churn
                                      or load-bearing?

  Supply chain                        What dependencies physically exist
                                      on disk?

  AI context                          What architecture and relationships
                                      should an agent know?

  Legacy migration                    Where are the structural units to
                                      transform?

  Historical analysis                 How does measured exposure change
                                      as the repository evolves?
  -----------------------------------------------------------------------

![GitGalaxy architecture pipeline](docs/wiki/assets/sankey_v4.3.1.png)

------------------------------------------------------------------------

# The structural-extraction thesis

GitGalaxy deliberately does **not** begin by constructing a complete AST
for every language.

It uses approximately 97 structural-signal categories to identify things
such as:

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

> **For repository-scale intelligence, targeted structural extraction
> can recover the entities required for useful code intelligence without
> requiring a complete language parser for every file.**

That hypothesis is being tested empirically.

------------------------------------------------------------------------

# Structural validation: GitGalaxy vs Tree-sitter vs Ctags

This is currently one of the most important validation programs in the
project.

GitGalaxy is being evaluated against **Tree-sitter and Universal Ctags**
on the same [Language Crucible](https://github.com/squid-protocol/language-crucible) corpus.

The first structural targets are:

-   functions
-   classes
-   arguments

The benchmark is deliberately **not** treated as a three-tool popularity
contest.

When tools disagree:

1.  the disagreement is recorded;
2.  the source is inspected;
3.  each tool's behavior is investigated;
4.  GitGalaxy is fixed when GitGalaxy is wrong;
5.  comparator/adaptor code is fixed when the comparator is wrong;
6.  genuine tool limitations are documented;
7.  the result is re-measured.

**24 of 45 languages get all three tools compared, 16 more get two, and
5 GitGalaxy-only languages** (`abap`, `dockerfile`, `jcl`, `livecode`,
`yaml`) get hand-reviewed manual verification instead of cross-tool
agreement. Of the 180 discrepancy shapes logged so far, **87 are
validated (48%)** — read, investigated, and recorded with a verdict,
not just counted.

The goal is to finish the audit, close remaining GitGalaxy defects,
establish independent ground truth where necessary, and then publish
final precision/recall measurements. See
[the tri-comparison methodology doc](docs/self_scan/tri_comparison_README.md)
for how matching, the ledger lifecycle, and CI enforcement work.

![Tri-comparison](docs/self_scan/tri_comparison_chart.svg)

See:

-   [`tests/tools/tri_comparison_chart.py`](tests/tools/tri_comparison_chart.py)
-   [`docs/self_scan/tri_comparison_ledger.json`](docs/self_scan/tri_comparison_ledger.json)
    — the full, per-shape validated record
-   [`docs/self_scan/tri_comparison_points_of_interest.md`](docs/self_scan/tri_comparison_points_of_interest.md)
    — the same ledger, rendered and ranked by signal strength
-   [`docs/self_scan/how_to_investigate_a_discrepancy.md`](docs/self_scan/how_to_investigate_a_discrepancy.md)
-   [`docs/self_scan/manual_verification.json`](docs/self_scan/manual_verification.json)

### What the benchmark is actually asking

Not:

> "Is GitGalaxy a better parser than Tree-sitter?"

But:

> **"For the structural entities GitGalaxy needs to build its repository
> graph, how accurately can targeted structural extraction recover them
> compared with established parsing and indexing systems?"**

That is the narrower claim the experiment can support.

### Languages without suitable comparator coverage

Some languages do not currently have a suitable independent
Tree-sitter/Ctags comparison path.

Those are kept in a separate evidentiary category and use committed
manual verification rather than pretending cross-tool agreement exists.

This currently includes languages such as:

-   ABAP
-   Dockerfile
-   JCL
-   LiveCode
-   YAML

Where practical, the next step is to add independent lexical,
grammar-based, or domain-specific comparators. Where no credible
independent comparator exists, human-verified ground truth remains the
appropriate category.

------------------------------------------------------------------------

# Validation is a ladder

GitGalaxy's evidence is being organized around progressively stronger
questions.

### 1. Structural validity

**Does GitGalaxy correctly identify code structures?**

Tree-sitter + Ctags + independently investigated disagreements. See
["Structural validation" above](#structural-validation-gitgalaxy-vs-tree-sitter-vs-ctags).

### 2. Regression validity

**Does the implementation remain stable on real code?**

[Golden-master testing](tests/tools/update_golden_master.py) against
[Language Crucible](https://github.com/squid-protocol/language-crucible).

### 3. Scale validity

**Does it work on real repositories?**

Unedited raw scan output from
[hundreds of repositories](https://github.com/squid-protocol/gitgalaxy-raw-output).

### 4. Model validity

**Do structural signatures correspond to the exposure categories they
are intended to represent?**

Statistical analysis against independently observable outcomes---not
merely against GitGalaxy's own equations.

### 5. Temporal validity

**Does exposure behave sensibly as software changes?**

Git-history analysis comparing repository states before and after real
changes.

### 6. External validity

**Do exposure changes correspond to independently documented security or
maintenance outcomes?**

Future work: security fixes, regressions, advisories, defects and other
external event datasets.

This distinction matters: a score can be internally consistent without
necessarily being externally meaningful.

------------------------------------------------------------------------

# Risk exposure: what GitGalaxy claims

GitGalaxy produces **risk-exposure measurements**, not vulnerability
verdicts.

A high exposure means:

> **This location deserves attention relative to the rest of the
> repository.**

It does not mean:

> "This code is definitely vulnerable."

The current system produces normalized exposure categories across the
repository and rolls information from structural entities through files,
folders and repository-level views.

The underlying signatures cover patterns involving areas such as:

-   secrets
-   injection surface
-   unsafe/memory operations
-   dynamic execution
-   I/O
-   concurrency
-   state mutation
-   reflection
-   APIs
-   dependencies
-   entropy
-   other structural/security characteristics

The important research question is whether these signatures are
**empirically associated with meaningful classes of software risk**,
rather than merely correlated with a score that GitGalaxy itself
mathematically constructed.

That distinction drives the next phase.

------------------------------------------------------------------------

# The next validation: risk over Git history

Once structural validation is sufficiently mature, GitGalaxy can test
its exposure model longitudinally.

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

> **Do commits independently identified as security fixes typically
> reduce the corresponding GitGalaxy exposure?**

Negative controls are equally important:

> Do ordinary development commits show the same behavior?

Eventually:

> Do security regressions increase exposure?

The planned harness will preserve commit SHA, parent state, changed
files/functions, exposure before/after, exposure deltas, structural
changes and event classification.

That tests:

**structure → exposure → real software evolution**

rather than merely testing the internal mathematics of the exposure
model.

------------------------------------------------------------------------

# Evidence, not just claims

### Language Crucible

A pinned corpus of real-world source including projects such as Godot,
Roslyn, curl, Kubernetes and Apollo 11 flight software.

[Language Crucible](https://github.com/squid-protocol/language-crucible)

### Golden-master regression

Real source is rescanned and compared against checked-in expected output
so parser changes have an observable diff. Regenerated with
[`tests/tools/update_golden_master.py`](tests/tools/update_golden_master.py),
never hand-edited.

### Tri-comparison

The same corpus is analyzed against GitGalaxy, Tree-sitter and Ctags
where coverage exists — 24 of 45 languages get all three tools, 87 of
180 logged discrepancies validated so far. See
[the methodology](docs/self_scan/tri_comparison_README.md) and the
["structural validation" section above](#structural-validation-gitgalaxy-vs-tree-sitter-vs-ctags)
for the full picture.

### Raw repository output

Unedited GitGalaxy output is retained for hundreds of independently
selected repositories.

[Raw Output](https://github.com/squid-protocol/gitgalaxy-raw-output)

### Regression suite

**7,043 tests** in the default suite (`python -m pytest tests/`), of
which **6,165** are per-signature tests across all 45 structurally-signatured
languages — positive matches, explicit exclusions, and adversarial/ReDoS
inputs. See [`tests/README.md`](tests/README.md) for the breakdown, and
[`docs/why_gitgalaxy_beats_ast_here.md`](docs/why_gitgalaxy_beats_ast_here.md)
for specific, evidenced cases where this extraction beats an AST read.

### Historical validation

The next research layer will test whether exposure measurements
correspond to real security and maintenance events over Git history.

------------------------------------------------------------------------

# What GitGalaxy is --- and isn't

### GitGalaxy is

-   repository-scale structural intelligence
-   language-agnostic source analysis
-   a common structural representation across heterogeneous code
-   risk-exposure prioritization
-   architecture mapping
-   CI-native evidence generation
-   useful on broken/uncompiled repositories
-   designed for local/offline operation

### GitGalaxy is not

-   a replacement for CodeQL's deep dataflow analysis
-   a replacement for Semgrep's rule ecosystem
-   a replacement for dependency CVE databases
-   a proof of exploitability
-   a runtime analyzer
-   a complete language parser
-   a guarantee that a high exposure is a vulnerability

  -----------------------------------------------------------------------
  Tool                                Primary question
  ----------------------------------- -----------------------------------
  **GitGalaxy**                       What does this entire repository
                                      look like, structurally, and where
                                      should attention go first?

  Tree-sitter                         What syntactic structure does this
                                      source contain?

  Ctags                               Where are the navigable code
                                      entities?

  Semgrep                             Does this code match a specified
                                      pattern?

  CodeQL                              What data/control relationships can
                                      deeper analysis establish?

  SCA/CVE tools                       Is this dependency/version
                                      associated with a known advisory?
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# Real-world scale

GitGalaxy is intended for repositories too heterogeneous or broken for a
traditional single-language build-first workflow.

Example: **Kubernetes**

\~1.39M lines across Go, YAML, JSON, Shell and Proto.

End-to-end scan: **50.83 seconds**.

![GitGalaxy scan
speed](https://raw.githubusercontent.com/squid-protocol/gitgalaxy-raw-output/main/speed_charts/latest/loc_vs_time.png)

See the [raw output
repository](https://github.com/squid-protocol/gitgalaxy-raw-output) for
unedited artifacts.

------------------------------------------------------------------------

# Outputs

  Output                       Purpose
  ---------------------------- ----------------------------------------
  **SARIF**                    CI/security dashboard integration
  **CycloneDX SBOM**           Dependency inventory/compliance
  **SQLite**                   Queryable repository knowledge graph
  **LLM architecture brief**   Compact machine/agent-oriented context
  **JSON audit data**          Forensic/automation workflows
  **3D visualization data**    Interactive repository topology

These are different views of the same deterministic scan, rather than
independent analysis engines.

------------------------------------------------------------------------

# Git history and architecture

GitGalaxy already incorporates Git history into signals such as:

-   churn
-   contributor concentration
-   bus-factor exposure
-   refactoring hotspots
-   file ownership
-   temporal activity

The research direction is to extend this from **history as a contextual
signal** to **history as an external validation source for the exposure
model**.

------------------------------------------------------------------------

# Privacy and deployment

GitGalaxy is designed for local and air-gapped operation.

-   Source code is not sent to a GitGalaxy cloud service.
-   Scanning and vectorization occur locally.
-   The scanner has no runtime network requirement.
-   CI/CD execution can remain inside the user's environment.
-   The browser visualizer operates on locally supplied data.

------------------------------------------------------------------------

# Installation

``` bash
pip install gitgalaxy
```

See the [documentation](https://squid-protocol.github.io/gitgalaxy/) for
current commands and configuration.

### CI/CD

Templates are provided for:

-   GitHub Actions
-   GitLab CI
-   Bitbucket Pipelines
-   Azure Pipelines
-   generic shell-invocable CI environments

See [`templates/`](templates/) and the [CI integration
guide](github-action-readme.md).

------------------------------------------------------------------------

# Explore the evidence

  ---------------------------------------------------------------------------------------------------------------------------------
  Resource                                                                                      What it contains
  --------------------------------------------------------------------------------------------- -----------------------------------
  [Documentation](https://squid-protocol.github.io/gitgalaxy/)                                  Architecture, claims and
                                                                                                methodology

  [Language Crucible](https://github.com/squid-protocol/language-crucible)                      Cross-language benchmark and golden
                                                                                                corpus

  [Raw Output](https://github.com/squid-protocol/gitgalaxy-raw-output)                          Unedited scans of real repositories

  [`tests/README.md`](tests/README.md)                                                          Regression and golden-master
                                                                                                methodology

  [`tri_comparison_ledger.json`](docs/self_scan/tri_comparison_ledger.json)                     Disagreement-by-disagreement
                                                                                                validation record

  [`manual_verification.json`](docs/self_scan/manual_verification.json)                         Reviewed cases where comparator
                                                                                                coverage is unavailable

  [`how_to_investigate_a_discrepancy.md`](docs/self_scan/how_to_investigate_a_discrepancy.md)   Comparator-disagreement methodology

  [Visualizer](https://gitgalaxy.io/)                                                           Local browser-based repository
                                                                                                visualization
  ---------------------------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# Current research direction

GitGalaxy is moving through a sequence of increasingly difficult
questions:

> **Can we scan heterogeneous source without compiling it?**

↓

> **Can we reliably recover the structural entities needed to understand
> it?**

↓

> **Do those structural measurements correspond to meaningful risk
> exposure?**

↓

> **Does measured exposure behave correctly as real software evolves?**

The Tree-sitter/Ctags validation is currently about halfway complete.
The immediate priority is to finish that audit before turning
preliminary measurements into stronger claims.

The next major experiment is:

**Git history → independently identified change/fix events → GitGalaxy
before/after scans → exposure deltas → statistical analysis.**

That is where GitGalaxy can begin testing not only whether it *sees*
structure, but whether its structural model **tracks meaningful changes
in real software**.

------------------------------------------------------------------------

# License

Copyright (c) 2026 Joe Esquibel

GitGalaxy is distributed under the **PolyForm Noncommercial License
1.0.0**.

See the repository license for full terms.