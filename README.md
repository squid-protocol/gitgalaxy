<div align="center">

# GitGalaxy

[Docs](https://squid-protocol.github.io/gitgalaxy/) · [Visualizer](https://gitgalaxy.io/)

[![PyPI version](https://badge.fury.io/py/gitgalaxy.svg)](https://badge.fury.io/py/gitgalaxy)
[![Python 3.09+](https://img.shields.io/badge/python-3.09+-blue.svg)](https://www.python.org/downloads/)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm%20Noncommercial-blue.svg)](https://polyformproject.org/licenses/noncommercial/1.0.0/)
[![Dependencies](https://img.shields.io/badge/Dependencies-0-brightgreen.svg)](https://pypi.org/project/gitgalaxy/)
[![Airgap Ready](https://img.shields.io/badge/Security-Airgap_Ready-teal.svg)](#data-privacy--on-premise-deployment)

</div>

<div align="center">

**1 scan** · **97 structural signals** · **50+ languages** · **0 need for compilation**<br>
**19 risk exposure scores** · **6 final reports** · **0 dependencies** · `pip install gitgalaxy`

</div>

<div>

## What Pain Point Does This Solve?

GitGalaxy exists for one recurring problem: understanding a large, real, multi-language
codebase that doesn't compile cleanly — the state most production repositories are actually
in, not the clean single-language input most static-analysis tooling assumes.

* **Full-system scans across 50+ languages in one pass.** No per-language toolchain, no
  successful build required. A polyglot repo with Go, YAML, Shell, and Python mixed together
  scans as one system, not five separate tool invocations.
* **No compilation, ever.** Broken dependencies, missing packages, disconnected vendored code,
  half-migrated legacy modules — all scan the same way a clean repo does, because nothing here
  has to build first.
* **Fast enough to run on every commit.** Most repositories scan in well under a minute —
  [Kubernetes](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.6/kubernetes/kubernetes_galaxy_llm.md),
  1.39M lines across Go, YAML, JSON, Shell, and Proto, scans end to end in 50.83 seconds. Scan
  time is fit as two regimes across a 599-repo batch — flat overhead below ~4,258 LOC, then
  `time(s) ≈ 3.36e-05 × LOC^0.969` above it (R²=0.88, near-linear, not degrading on large
  inputs) — see [Proof, Not Just Claims](#proof-not-just-claims) for the chart and derivation,
  not just this rounded headline.
* **CI-native output, not a standalone report.** Every scan produces a SARIF file (drops
  straight into GitHub/GitLab security dashboards), a CycloneDX SBOM (dependency compliance),
  and a 0–100 risk-exposure score per file, folder, and repo. See [Benchmarks](#benchmarks) for
  real, inspectable examples of each.

**This is not a vulnerability scanner competing with CodeQL, Semgrep, or SonarQube.** Those
tools do deep, precise analysis once your code compiles, usually one language at a time.
GitGalaxy answers a different question first — what does this whole system actually look like,
and where is the risk concentrated — across every language in the repo simultaneously, before
those deeper tools even have a build to work with. See
["How This Compares, Architecturally"](#how-this-compares-architecturally) below for exactly
where each tool's job starts and stops.

</div>

<div align="center">

Gitgalaxy can assess full repos, comprised of mixes of 50+ different languages, map out the architecture, and surface risk exposures alongside prioritized refactoring targets — hotspots, bus-factor risk, and load-bearing files — so you know where to focus first. The graph below is a workflow from one gitgalaxy scan of our golden test repo, which contains sample code files from the Apollo-11 1969 flight software through the modern tech stacks. [Benchmark](https://github.com/squid-protocol/language-crucible)
<img src="docs/wiki/assets/sankey_v4.3.1.png" alt="GitGalaxy Architecture Pipeline" width="100%">

</div>

<div>

### One Graph, Not Five Separate Tools

Gitgalaxy's core output is one thing: a deterministic structural graph of the whole
repository — Python, Go, Shell, YAML, and everything else in it, represented through the
same signal set. Security auditing, refactor prioritization, and legacy-to-modern language
translation (see [Enterprise Codebase Tools & Use Cases](#enterprise-codebase-tools--use-cases)
below) are all consumers of that one graph, not separate products with separate engines —
which is why this reads closer to an architecture-intelligence platform than a
single-language linter with a security label on it.

Most code-intelligence engines build that graph from an AST. Tree-sitter is the best of
them — fast, resilient to broken syntax, real grammars for dozens of languages — and
GitGalaxy isn't claiming to out-parse it; see
**[Claim 10](https://squid-protocol.github.io/gitgalaxy/03-10-claim-10-ast-vs-heuristic-parsing/)**
for where each approach actually wins — with one narrow, measured exception: for functions with
no formal parameter-list syntax at all (bash, traditional-style Perl), a declaration-only AST
read has nothing to count and reports zero regardless of real arity, while GitGalaxy's
body-aware `args` signal reads the same `$1`/`my (...) = @_`/`shift` idiom a human would; see
[why GitGalaxy beats a plain AST here](docs/why_gitgalaxy_beats_ast_here.md) for the measured
before/after (shell 0%→100%, perl 14.6%→82.1%) and exactly where this does and doesn't apply.
The reason GitGalaxy still doesn't build one is that
a syntax tree isn't the end product here — it's an input that would need normalizing across
dozens of separate per-language toolchains before "risk in this Python file" and "risk in
this Go file" mean the same thing. GitGalaxy skips that normalization step by never building the
per-language tree at all: instead of parsing exhaustively, it matches ~97 regex "structural
signal" categories directly against the source — function boundaries, control flow, I/O,
state mutation, dozens more — the same signals, in the same pass, regardless of language,
on code that doesn't need to compile. That's the actual trade: less syntactic precision per
file, measured rather than assumed (see item 4 in
[Proof, Not Just Claims](#proof-not-just-claims) below), in exchange for one comparable
graph across a repository no single toolchain could parse end to end.

It's the same trade sequencing makes over exhaustive alignment:
[BLAST swapped Smith-Waterman's](https://squid-protocol.github.io/gitgalaxy/03-01-claim-1-search-strategies/)
exhaustive comparison for fast signature matching, at the cost of some precision, to make
genome-scale search tractable at all. GitGalaxy applies the same idea to source code —
match structural signatures first, infer higher-level architecture from those signatures
second — to make repository-scale, cross-language analysis tractable.

The per-file signal vector feeds a per-repo dependency graph (import resolution +
PageRank/centrality), gets normalized into 0–100 risk scores via sigmoid functions, and
exports to six formats in one scan pass: SARIF, CycloneDX SBOM, a queryable SQLite
knowledge graph, an LLM-optimized architecture brief, and 3D visualization data. Crossing
that graph against git history adds two further signals: **bus-factor risk** (load-bearing
files owned almost entirely by one contributor) and **refactoring hotspots** (files
simultaneously high-churn, high-complexity, and high-debt) — both named, file-level
targets, not just a score.

</div>

<div>

### Scanning Apollo-11 with the blAST Engine

![GitGalaxy CLI Scan](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/apollo11_scan.gif)

</div>

<div>

## What GitGalaxy Finds — and What It Doesn't Claim

GitGalaxy produces two different kinds of output, and they should be read differently.

**Risk Exposure scores** are a 0–100, density-normalized signal across 19 categories
(secrets, injection surface, memory corruption, and more), rolled up from function to
file to folder to repository. A high score means *this deserves attention first* — it
is a prioritization signal, not a verdict. Two files can carry the same score for
completely different reasons: a real problem, or a legitimate pattern that looks
identical on the surface. Encrypted malware and a well-tested cryptography routine
both produce high entropy. GitGalaxy can't tell you which one it found — only that
something worth a second look is there.

**Findings** are individual, line-level flags: a specific Structural Signature that
crossed a risk threshold. These are evidence to review, not confirmed vulnerabilities.
GitGalaxy never executes code, traces runtime dataflow, or verifies exploitability —
it tells you a pattern exists in the text, at this exact line, and hands you the
context to judge it yourself.

**This is intentional, not a limitation we're hiding.** GitGalaxy is built to err
toward recall over precision: flag more, and let a human or a deeper tool narrow the
list, rather than risk staying silent on something real. False positives are the
expected cost of that trade-off, the same way they are for every static analyzer that
doesn't execute the code it reads.

That also means GitGalaxy is strongest against a specific class of problem —
**negligence, not adversarial evasion.** A hardcoded key someone forgot to remove, an
insecure registry, an obviously dangerous `eval()` call — nobody on the other end of
those is trying to hide from a scanner. A specifically motivated attacker who knows
how static, signature-based detection works can evade individual signals like entropy
thresholds without much effort. Treat GitGalaxy as the fast first pass across a
codebase too large to read by hand — not the last word on whether something is safe.

</div>

### Weakness Classes, Not Just Known CVEs

Most dependency scanners work from a lookup table: they know a vulnerability exists
because someone found it, filed it, and it now has a CVE number in a feed. That's
useful, but it's necessarily reactive — a scanner built this way is blind to anything
that hasn't been discovered and disclosed yet, including straightforward variants of
known-bad patterns that just look slightly different from the filed instance.

GitGalaxy takes a different approach: instead of matching known instances, it matches
weakness *classes*. Its findings are tagged by CWE (Common Weakness Enumeration) —
hardcoded credentials, dynamic code execution, unsafe deserialization — not by CVE ID.
A structural signature for "dynamic execution of tainted input" catches that pattern
wherever it appears, with whatever variable names, in whatever specific arrangement —
not just the one instance someone already filed a report about.

The same philosophy extends to the SBOM layer. Rather than asking "does this package
version appear in a vulnerability database," GitGalaxy asks "does this package's actual
content on disk structurally match what a legitimate version should look like" —
entropy, structural fingerprint, behavioral anomaly flags.
That's how a tampered dependency gets caught on day one, before anyone has discovered
or disclosed anything, because there's no CVE to wait for.

This is a complement to CVE-feed tools (Snyk, Dependabot, OSV-Scanner), not a
replacement for them — those tools are the right answer for "is this exact known bug
present." GitGalaxy is the right answer for the wider net: weakness classes and
physical anomalies that don't require anyone to have found and filed the specific
instance first.

### How This Compares, Architecturally

This is a self-reported comparison of what each tool structurally requires and detects on,
not an independent benchmark — verify against each project's own documentation. It exists to
answer one question plainly: what gap is GitGalaxy actually built to cover, versus tools doing
a related but different job.

| | GitGalaxy | Semgrep | CodeQL | Snyk / Dependabot |
|---|---|---|---|---|
| **Requires an AST or a build** | No — regex/lexical structural signatures | Yes — per-language AST pattern matching | Yes — compiles/extracts a code database | No — reads package manifests |
| **Detection basis** | Weakness-class (CWE) + physical/structural anomaly | Pattern-match rules (SAST) | Dataflow/taint queries (SAST) | CVE/advisory-database lookup (SCA) |
| **Works on broken/uncompiled code** | Yes — this is the design target | Partial, depends on the rule/parser | No — needs a working build | Yes — only reads the manifest |
| **Offline / air-gapped** | Yes, fully local | OSS engine runs locally; Cloud Platform is hosted | Runs locally; commonly used via GitHub-hosted Actions | Cloud-dependent (Snyk); GitHub-hosted (Dependabot) |

Where GitGalaxy's SAST-category peers need an AST or a compiling build, and where the CVE-feed
tools need a package manifest, is precisely the gap GitGalaxy is built to cover — not a claim
that it replaces what they do well.

<div>

## Proof, Not Just Claims

Every "structural signature" and "AST-free" claim above is backed by three things you can inspect and re-run yourself, not just take on faith:

1. **[3,649 per-signature regression tests](tests/README.md).** `gitgalaxy/standards/language_standards.py` defines every regex rule the engine uses to recognize a construct — a function start, an API boundary, a safety bypass — across the 45 languages that have real structural signatures (~1,970 compiled patterns total). Every one of those rules is tested for what it should match, what it should explicitly *exclude* (the false-positive check most regex-based tools skip), and that it can't be hung by an adversarial input. See **[`tests/README.md`](tests/README.md)** for the full index, and [epic #518](https://github.com/squid-protocol/gitgalaxy/issues/518) for the audit that closed it out — dozens of real regex bugs found and fixed along the way, not just theoretical coverage.
2. **A true golden diff against real, unmodified production code.** [`language-crucible`](https://github.com/squid-protocol/language-crucible) is a pinned, tagged snapshot of ~120 real subdirectories pulled from major open-source projects — Godot's C++, the Roslyn C# compiler, curl, Kubernetes, Apollo 11's AGC flight software, and more — deliberately left disconnected and uncompilable, the same hostile state real repos are in. Every pull request that touches the parsing engine re-scans that entire corpus and diffs the output, field by field, against a checked-in snapshot (`tests/golden_master_audit.json`); a diff means the output changed on real code, and it has to be explained before it's accepted — not a smoke test, an actual golden-master comparison. See [`tests/README.md`](tests/README.md#5-golden-master-differential-testing-the-language-crucible) for exactly how this is wired into CI, and [language-crucible's own README](https://github.com/squid-protocol/language-crucible) for why that corpus is built the way it is.
3. **[Unedited raw scan output at real-world scale](https://github.com/squid-protocol/gitgalaxy-raw-output).** Where the golden-master corpus above proves correctness on ~120 curated adversarial paradigms, this repo is the complementary evidence that the engine actually runs, unmodified, across hundreds of independently-chosen real repositories — every `_galaxy_audit.json`, `_galaxy_master.db`, and `_galaxy_llm.md` the scanner produced, kept versioned per engine release. The corpus manifest pinning exactly which repos and commits were scanned currently covers a 323-repo subset of the larger batch archived there — stated plainly in that repo's own README rather than implied to be complete.
4. **[Measured against Tree-sitter](docs/language_status/README.md), not asserted.** [`tests/tools/tree_sitter_accuracy_audit.py`](tests/tools/tree_sitter_accuracy_audit.py) diffs GitGalaxy's extraction against real AST ground truth on the [`language-crucible`](https://github.com/squid-protocol/language-crucible) corpus, one committed baseline per language, re-measured and re-charted automatically on every push that touches the parsing engine:

<p align="center">
  <img src="docs/self_scan/tree_sitter_accuracy_chart.svg" alt="GitGalaxy structural extraction accuracy vs. Tree-sitter ground truth, ranked recall/precision panels by language" width="700">
</p>

31 languages baselined so far; each panel is ranked independently and "n/a" (no ground-truth
instances) sorts to the bottom rather than scoring as 0%. Two languages have a full written
audit behind the chart — [python](docs/language_status/python.md) and
[javascript](docs/language_status/javascript.md) — which is how real defects like
[#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193) (still open) got found in
the first place; the rest of the 31 are baseline-only so far, not yet manually audited.

That same raw-output batch is what the speed claim above is fit from — every repo plotted, not just the favorable Kubernetes example:

<p align="center">
  <img src="https://raw.githubusercontent.com/squid-protocol/gitgalaxy-raw-output/main/speed_charts/latest/loc_vs_time.png" alt="GitGalaxy scan time vs. LOC across hundreds of repositories, log-log, both axes" width="600">
</p>

Always the newest scanner version — full derivation and methodology in
[gitgalaxy-raw-output's Speed Telemetry section](https://github.com/squid-protocol/gitgalaxy-raw-output#speed-telemetry).

</div>

<div>

## Benchmarks
* **[50+ Language Test Repo](https://github.com/squid-protocol/language-crucible)** — also the golden-master corpus described above — and [artifacts](https://github.com/squid-protocol/language-crucible/tree/main/raw_output)
* **[Raw Output at Real-World Scale](https://github.com/squid-protocol/gitgalaxy-raw-output)** — unedited scan output (audit JSON, SQLite, LLM briefs) from hundreds of independently-chosen repositories, kept versioned per engine release
* **[Speed Results from 104 Repos](https://squid-protocol.github.io/gitgalaxy/03-01-claim-1-search-strategies/)**
* **[Cross-Language Comparisons of over 1000 repos](https://squid-protocol.github.io/gitgalaxy/03-04-claim-4-comparing-languages/):** Deterministic 1:1 benchmarking of distinct syntax architectures.
* **[Universal File Archetypes by k-means clustering](https://squid-protocol.github.io/gitgalaxy/03-05-claim-5-file-archetypes/):** ML isolation of files into K-means clusters.
* **[Mainframe Migration: 27/27 Compile Success Across Legacy COBOL Repos](https://github.com/squid-protocol/gitgalaxy/tree/main/examples/ibm_cics_translation):** 27 distinct legacy COBOL repositories (including IBM CICS benchmark apps) translated into compiling Java Spring Boot environments.

</div>

<div>

### Real-World Adoption

<div align="center">

GitGalaxy is meant to run *in* CI, not just get starred and forgotten — so we track CI/production integration as its own adoption signal alongside human discovery, instead of filtering it out as noise.

<img src="https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/human_vs_ci_adoption.png" alt="GitGalaxy: Human Discovery vs. Production Integration" width="700">

**Left:** GitHub stars and forks (cumulative — reconstructed from each star's/fork's own timestamp, not just a snapshot going forward) alongside daily unique cloners and profile views. **Right:** GitLab CI/CD Catalog usage (unique projects running GitGalaxy in a pipeline in the last 30 days) and GitHub Action adoption (unique repos referencing the action in a workflow, via code search — GitGalaxy isn't Marketplace-listed yet, so this is the best passive signal available). Unlike the left panel, GitHub and GitLab don't expose any history for these two — expect the right panel to fill in day by day rather than show a backfilled trend.

<img src="https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/cumulative_downloads.png" alt="GitGalaxy Cumulative Downloads" width="500">

Combined distribution volume across PyPI, GitHub, and GitLab against our baseline control repositories — **not a uniformly deduplicated count**. GitHub's unique-cloner count and GitLab's unique-project count are genuinely deduplicated; PyPI's public download data has no identity to deduplicate against (measured without mirrors, which excludes known mirror-sync bots but not CI-driven installs), so that component is a raw download-event count. The GitHub/PyPI breakdown lines begin partway through the window because per-source tracking was added after total-fetch tracking; the total line before that point is aggregate across all sources.

Full methodology, including exactly what is and isn't deduplicated per source: [squid-protocol/squid-telemetry](https://github.com/squid-protocol/squid-telemetry#methodology-notes).
</div>

</div>

<div>

## Data Privacy & On-Premise Deployment

GitGalaxy performs 100% of its scanning and vectorization locally — the engine runs the same
way fully air-gapped as it does connected.

* **No Data Transmission:** Source code is never transmitted to any API, cloud database, or third-party service.
* **On-Premise / Air-Gapped Execution:** No runtime network dependency — the engine runs identically in a fully disconnected environment.
* **Ephemeral Memory Processing (web visualizer):** Repositories are unpacked into a volatile memory buffer (RAM) and automatically purged when the browser tab is closed.
* **Privacy-by-Design:** Even when using the web-based viewer, the data remains behind the user's firewall at all times.

</div>

<div>

## Installation & Usage
* Python-based: `pip install gitgalaxy`
* CLI execution
* **[How to add a new programming language in 1 prompt](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)**
* Outputs forensic JSONs (optimized for AI-agent summary reports) and a native SQLite3 database for robust querying and storage.

### CI/CD Integration

Drop the template for your platform straight into your pipeline — each one runs a GitGalaxy scan and can fail the build on risk-threshold or malware-signature breaches.

| Platform | Template |
|---|---|
| **GitHub Actions** | [`gitgalaxy-pipeline.yml`](https://github.com/squid-protocol/gitgalaxy/blob/main/templates/github/gitgalaxy-pipeline.yml) — see the [full integration guide](https://github.com/squid-protocol/gitgalaxy/blob/main/github-action-readme.md) |
| **GitLab CI** | [`scan.yml`](https://github.com/squid-protocol/gitgalaxy/blob/main/templates/gitlab/scan.yml) |
| **Bitbucket Pipelines** | [`bitbucket-pipelines.yml`](https://github.com/squid-protocol/gitgalaxy/blob/main/templates/bitbucket/bitbucket-pipelines.yml) + [`bitbucket_insights.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/templates/bitbucket/bitbucket_insights.py) (posts findings as Bitbucket Code Insights annotations) |
| **Azure Pipelines** | [`azure-pipelines.yml`](https://github.com/squid-protocol/gitgalaxy/blob/main/templates/azure/azure-pipelines.yml) |
| **Anything else** (Jenkins, CircleCI, etc.) | [`scan.yml`](https://github.com/squid-protocol/gitgalaxy/blob/main/templates/scan.yml) — generic, shell-invocable template |

</div>



## Enterprise Codebase Tools & Use Cases

This is the "several consumers" half of [One Graph, Not Five Separate Tools](#one-graph-not-five-separate-tools)
above, made concrete: each tool below is a standalone module under `gitgalaxy/tools/` that
consumes the same deterministic scan output rather than re-parsing the repo itself.

### [Automated Legacy Migration: COBOL to Java Spring Boot](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/cobol_to_java/)
A deterministic, high-fidelity translation pipeline. It converts legacy COBOL into fully compiling, modern Spring Boot architectures, mapping memory exactly and scaffolding JPA entities, REST controllers, and Maven builds before utilizing AI to translate isolated business logic.
* **Benchmark:** Achieved a 27/27 Maven compile success rate across a batch test of distinct legacy repos. Compiling is a necessary but not sufficient signal of a correct translation — it confirms the generated code builds, not that the business logic is semantically equivalent to the original; a business logic review is still required.
* **Verify for Yourself:** [Inspect the raw outputs of the IBM CICS Application Translation here.](https://github.com/squid-protocol/gitgalaxy/tree/main/examples/ibm_cics_translation/)

### [Mainframe Refactoring: COBOL & JCL Optimization](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/cobol_to_cobol/)
An analytical suite for sanitizing mainframe monoliths. It safely neutralizes legacy lexical traps, extracts dead execution memory, maps topological DAG execution orders, and generates Zero-Trust JCL configurations for modern cloud deployments.
* **Benchmark:** The dead-code extraction engine removed over 6,700 lines of dead execution blocks and orphaned variables from the standard IBM CICS benchmark app in seconds.

### [Software Supply Chain Security & Pre-Commit Firewalls](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/supply_chain_security/)
Pre-commit firewalls that scan physical file internals rather than trusting manifest files — built to block steganography, byte-level XOR decryption loops, homoglyph typosquatting, and exposed cryptographic vaults before they enter your CI/CD pipeline. **[Deploy directly via our GitHub Action](https://github.com/squid-protocol/gitgalaxy/blob/main/github-action-readme.md).**

### [SBOM Generation & Dependency Auditing](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/recorders/sbom_recorder.py)
A Software Bill of Materials (SBOM) generator that doesn't blindly trust `package.json` or `requirements.txt` — it locates the physical dependencies on disk, checks their entropy and linguistic identity against what a legitimate version should look like, and generates strict CycloneDX 1.4 JSON reports.
* **Benchmark:** Mapped and verified the physical internals of 170 unique Go modules inside the local Kubernetes repository. A single-repo result, not a claim of coverage across the Go ecosystem.

### [API Security & Shadow API Detection](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/network_auditing/)
A deterministic mapping tool for undocumented and outdated API surface. It uses structural regex to find active physical routing logic (Express, Spring Boot, FastAPI) and applies set theory against official OpenAPI/Swagger documentation to isolate Shadow APIs (undocumented routes) and Ghost APIs (documented routes no longer implemented).

### [High-Speed PII Detection & Log Analysis](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/terabyte_log_scanning/)
Log analysis operating at 0.07 GB/sec without requiring an index. It streams massive database dumps to hunt and mask PII (credit cards, SSNs, AWS keys) and uses static architecture maps to report runtime execution frequencies as ASCII time-series histograms.

### [AI Agent Guardrails & Codebase Protection](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/ai_guardrails/)
The AppSec Sensor flags AI agents wired to raw state-mutation capability: an LLM orchestration
framework (LangChain, LlamaIndex) imported alongside direct network/disk I/O, combined with
below-threshold defensive-programming density. That's a library-identity signal, not a claim
about runtime behavior — a regex-only engine with no dataflow tracing can't prove code actually
executes that path, so it doesn't claim to (see [#1102](https://github.com/squid-protocol/gitgalaxy/issues/1102)
for the checks that were removed for making that unprovable claim). Separately, the Dev Agent
Firewall evaluates token mass and blast radius to restrict autonomous coding agents from
modifying dangerous or context-token-draining files.

## Local Browser-Based 3D Codebase Visualization

If you prefer visual analytics, we've built a topological dashboard where each file represents a node, sized and colored according to specific risk metrics.

Simply drag and drop your generated `your_repo_GPU_galaxy.json` file (or a `.zip` of your raw repository) directly into [GitGalaxy.io](https://gitgalaxy.io/). All rendering and scanning happens entirely in your browser's local memory.

### Watch GitGalaxy in Action

**Mapping 3.2 Million Lines of C++ in 11 Seconds | OpenCV** [![OpenCV Demo](https://img.youtube.com/vi/3ScQCSUBdZw/maxresdefault.jpg)](https://youtu.be/3ScQCSUBdZw)

![GitGalaxy Topological Visualizer 3D graph rendering complex software repository structures and K-means clustering archetypes in the browser](https://raw.githubusercontent.com/squid-protocol/gitgalaxy/main/docs/wiki/assets/metavisualizer.png)

## Licensing & Usage

Copyright (c) 2026 Joe Esquibel

GitGalaxy is distributed under the **PolyForm Noncommercial License 1.0.0**.

### Community Free Tier (Academic, Research, & Hobbyist)
We are deeply committed to the open-source and academic communities. If you are using GitGalaxy for personal projects, academic research, or non-commercial development, the engine is 100% free to use.

To suppress the commercial licensing delays in your terminal or personal CI/CD pipelines, simply set the following environment variable:

```bash
export GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER"
```

### Commercial & Enterprise Use
Running GitGalaxy in corporate environments, proprietary codebases, or commercial CI/CD pipelines requires an enterprise license. Unlicensed corporate pipelines will experience intentional execution friction, and attempting to use the Community Free Tier key in a corporate environment will trigger explicit non-compliance warnings in your audit logs.

To acquire a commercial key for your organization and ensure clean compliance logs, please contact: **joe@gitgalaxy.io**