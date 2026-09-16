# Claim 5b — Composition Archetypes (the function → file → repo tower)

[Claim 5](03-05-claim-5-file-archetypes.md) clusters a file by its raw **structural DNA** — "what
does this file's syntax physically resemble?" This page describes a second, complementary lens:
the **compositional** archetype tower, which classifies code **bottom-up by what it is made of**.
A function is typed by its own shape; a file is typed by *the mix of function-types it contains*;
a repo is typed by *the mix of file-types it contains* (plus scale and coupling). Both lenses ship
side-by-side — a file now carries both a DNA `File Archetype` and a `Composition Archetype`.

> **Why two lenses?** They answer different questions. The DNA lens is *morphological* ("this file
> looks like a native memory handler"). The composition lens is *functional* ("this file is 80%
> Defensive-Guard functions" → a validation module). The composition lens is what makes an LLM
> report legible: every function is tagged with what it *does structurally*.

---

## The three levels

### 1. Function archetypes (14)

Every function is assigned one of 14 archetypes from an unsupervised k-means over a **38-dimension**
vector: 5 geometry features (log LOC, complexity, args, keyword density, internal decision density)
+ 33 per-LOC "DNA" densities of the architectural / structural / state / defensive signals.

| | | |
|---|---|---|
| Parameter Forwarders | Compute Cores | Defensive Guards |
| Many-Argument Workhorses | Generic / Templated Code | Callbacks & Closures |
| Interface Declarations | State Mutators | Type Conversions |
| I/O & Config Routines | Encapsulated Accessors | Annotated Framework Methods |
| C Struct Operations | Tests & Verification | |

**Feature selection is bias-governed by [keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta).**
The same planted program in 46 languages tells us which signals measure *architecture* vs. merely
*language idiom*. Signals that are inert (zero across all 46 languages — `llm_*`, `lit_*`, crypto/
regex/time families) are dropped, and signals that track language rather than structure (e.g.
`arch_api`, or idiom-mandatory hits like a JS `const` firing `immutability_locks`) are
down-weighted. `def_encapsulation` — a genuinely dominant real signal — is down-weighted 0.3× so it
doesn't crowd out secondary archetypes. The result is a taxonomy that reflects *how code is built*,
not *which language wrote it* — the language concentration that survives (C-struct code, JVM
annotations, JS callbacks) is real engineering idiom, not a measurement artifact.

### 2. File composition archetypes (15)

A file is characterized **compositionally** — by its function-archetype **stoichiometry** (the mix
of the 14 function types) — plus a small set of genuinely file-level properties that aren't just
re-aggregations of its functions:

- **Scale:** LOC, function count, class count, import count.
- **Organization:** encapsulation ratio, documentation ratio, control-flow ratio.
- **Dependency-graph role:** `pagerank` and blast-radius (is this a central hub or a leaf?).

Archetypes include *Parameter-Forwarder Files, Defensive-Guard Files, Compute-Core Files, Generic/
Templated Files, C-Struct Files, Tests & Verification, Annotated-Framework Files*, a positively
defined **Large Core Modules** (big, mixed, central), and a **Declarative / Non-Code** bucket for
config/constants/`__init__`-style files. Structural/graph features are **percentile-rank
transformed against the whole corpus** (heavy-tailed graph metrics like pagerank must never be
variance-scaled — doing so collapses the clustering into one mega-cluster).

### 3. Repo composition archetypes (7)

A repo is its **file-archetype composition + scale + dependency coupling**:

| Archetype | Signature | e.g. |
|---|---|---|
| **Hub-Coupled Monorepo** | huge, high pagerank-gini | linux, freebsd, tensorflow |
| **Flat Modular Platform** | huge, low pagerank-gini | kotlin, rust, swift, kubernetes |
| **Hub-Coupled App** | mid, high coupling | okhttp, openzeppelin, kivy |
| **Small Flat Repo** | small, low coupling | black, mojo, raspberrypi |
| **Typed Library** | generics-heavy | mypy, pydantic, pytest |
| **Mainframe / COBOL & Config** | I/O-heavy | abapGit, Apollo-11, gnucobol |
| **Guard/Validation-Heavy** | guard-heavy | zod, express |

The headline axis is **coupling** (`pagerank_gini`, hub concentration): it separates a single
interdependent core (linux) from many independent modules (kotlin/rust) *within the same scale
band* — a distinction composition and size alone miss.

---

## Fit z-scores

Every composition assignment carries a **fit z-score** = `(distance − cluster mean) / std`: how
**textbook** (z ≈ 0) vs. **hybrid / atypical** (high z) a file or repo is for its assigned
archetype. A `Defensive Guards (z +0.2)` file is a clean example; `Defensive Guards (z +2.8)` is a
hybrid worth a second look. (This mirrors the DNA lens's drift z-score.)

## Where it surfaces

- **Scan DB:** `function_data.func_archetype`; `file_data.composition_file_archetype` +
  `composition_file_z`; `repo_data.repo_composition_archetype` + `repo_composition_z`.
- **Ecosystem baseline:** `repo_data.ecosystem_baseline` / `z_score`, the per-file
  `file_data.ecosystem_baseline` / `repo_z_score`, and the audit's "Repository Ecosystem Baseline"
  all carry the repo composition archetype and its fit z. They previously came from a separate
  K-Means repo model, retired in #1159 because it labelled every repo "Cluster 3".
- **Audit JSON:** each file's "Composition Archetype" + "Composition Fit (Z-Score)"; a repo-wide
  "Repository Composition Archetype", "File Composition Distribution", and "Function Archetype
  Distribution".
- **LLM brief:** every named function is tagged inline — `parse_config (Compute Cores)` — with a
  definitions legend; the repo shows its composition archetype and file mix.

## How it works at scan time

The taxonomies are **population-relative** (features are percentile-ranked against the corpus). To
classify a single scan deterministically, the engine ships **frozen "brains"**
(`gitgalaxy/standards/archetype_brains/*.json`) carrying the centroids + names, feature order and
weights, the rank-transform **reference quantiles**, and per-cluster **z_score_params**. The
classifier runs post-network (so `pagerank` is available): it labels each function, rolls the
function mix up per file, labels each file, then aggregates file archetypes + scale + coupling into
the repo label — all in one pass.

## Provenance & methodology

The taxonomies were trained and chosen through pre-registered experiments in
[gitgalaxy-population-analyses](https://github.com/squid-protocol/gitgalaxy-population-analyses)
(`kmeans_clustering/FUNCTION_ARCHETYPES.md`, `experiments/2.7.0/file-archetype-clustering/`,
`experiments/2.7.0/repo-archetype-clustering/`), over the v2.7.0 scan corpus (729 repos, 8.2M
functions; repo archetypes trained on the 368 repos large enough to have a stable file mix). See also [Claim 5 — File Archetypes](03-05-claim-5-file-archetypes.md) (the DNA lens)
and the [keyword-rosetta bias methodology](https://github.com/squid-protocol/keyword-rosetta).
