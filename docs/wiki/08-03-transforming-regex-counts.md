# Transforming Regex Counts (Universal Exposure Framework)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
This metric normalization subsystem, known as the Universal Exposure Framework (UEF), recalibrates raw static regex counts into stable architectural indicators. It solves the problem of raw hit counts being noisy, misleading, or skewed by codebase size. It exists to provide deterministic, language-aware filtering of heuristic signals. Within GitGalaxy, the UEF calculates final, tiered risk outputs from raw data variables.

## Purpose
To process raw occurrence counts through deterministic normalization transformations, stabilizing signals and eliminating false positives across different language paradigms.

## Problem Being Solved
Uncalibrated static regex counts penalize large files for minor issues and treat structural risk and defensive logic as a flawed 1:1 offset. The UEF stabilizes these signals into actionable, normalized intelligence.

## Design
Applies four stabilizing principles:
1. **Weighted Asymmetry:** Defensive hits receive a 2.5x multiplier to demand strong defensive density.
2. **The Breach Cap:** If raw risk hits exceed guardrail hits, the safety rating is severely capped, bypassing averages.
3. **Sigmoid Gating:** Uses a logistic sigmoid function to filter low-density noise (0-5%) and scale exponentially as risk crosses thresholds.
4. **Quantized Tiering:** Scores are binned into qualitative tiers (Unshielded to Fortified).
5. **Evidence-Mass Floor:** Every per-file density divides by $\max(LOC, 50)$, never by raw LOC. Below 50 coding lines a file is scored on its *counts* (a two-hit file is a two-hit file whether it is 5 or 49 lines long), so identical intent scores identically regardless of file length; at or above the floor the density regime is untouched. This is the per-file analog of the mass-weighted averaging used at directory scope, and it is the *only* small-file mechanism -- it replaced six independent guards (a `<15 LOC` cognitive-load cliff, two `+20` paddings, a `loc/15` dampener, an unbounded $Irc/LOC$ floor, a `max(total_loc, 10)` API guard) that each fired on a different LOC range and fought each other (#2655). Files below the floor carry `mass_floored: true` and their `evidence_mass` in telemetry. Two consistency rules follow from it: $Irc$ *corrects* measured risk and never creates it (zero measured evidence scores zero in every tier), and a file with no branches carries no cognitive load at any length.
   The per-function descriptor has the same floor, derived the same way (#2705): `func_internal_density` $= \text{avg\_func\_complexity} / \max(\text{avg\_func\_loc},\ 12)$, where 12 is the golden-master median lines-per-function exactly as 50 is the median coding LOC per file. Below the floor the column is a pure rescale of `avg_func_complexity` -- it reports branch structure, and two files with the same branches per function read the same density however tersely one of them is written; at or above it the column is unchanged. That means for roughly half of real files the two columns say the same thing, by design.

General Risk Equation:
$$RiskExposure = \left( \frac{((RiskHits + Irc) \times Weight) - \sum_{s}(DefenseHits_s \times Fc_s)}{\max(LOC,\ 50)} \right) \times Mp$$

### Language corrections: three inputs, not one dial (#2716)

A regex sees different amounts in different languages, so a raw count is not comparable across them and something has to correct for it. Until #2718 that "something" was one lookup on the language's name: two inline hand lists picked $Fc$ / $Irc$ / $Ot$ per language, with 45 of 59 defined languages falling through to the harshest setting. Measured on the language-crucible corpus that single term moved 78% of files and 18% of them by 25 points or more; it inverted the safety ordering above 6 attack hits (#2717); and `embedded_python` paid a tier-3 penalty for not being the literal string `"python"` (#2653). The lookup was doing three separable jobs, and each now has its own input sourced from where the truth about it lives:

| what it corrects for | where the truth lives | the input | replaces |
|---|---|---|---|
| **Our rules catch less in some languages.** A `safety` rule that fires 3 times on 2 planted constructs over-credits every hit. | Measured. keyword-rosetta plants identical defence in every language and records what each rule found. | $Fc_s = \min(1,\ planted_s / measured_s)$ per language **and per signal**, generated into `gitgalaxy/standards/fidelity_table.py`. Under-firing stays at 1.0 — that is a rule to fix, and a coefficient that compensates for a fixable gap is a way to stop fixing it. | the single per-language $Fc$, and `_calc_safety`'s `systems_buffer_ratio` |
| **This language lets you leave things unsaid.** Unenforced error paths, implicit globals, no memory safety, no static types. | The language specification — objective yes/no columns, checkable against documentation. | `analysis_lens.LANGUAGE_STRICTNESS`: one row per language; $Irc$ = number of gaps (0–4), $Ot = 1 + 0.1 \cdot Irc$. Data, markup and configuration formats have no runtime and carry **no** term. Dialects resolve through `LANGUAGE_FAMILY`. | the tier lists |
| **This file does runtime-dynamic things a regex cannot follow.** `eval`, reflection, dynamic dispatch. | The file — these are already registry signals, counted per file. | `SignalProcessor._dynamism()` = the file's `reflection_metaprogramming` count (`high_risk_execution` is the safety attack vocabulary and stays there), read by documentation (as risk) and cognitive load (as heat). Concurrency and state flux lost their language term outright; safety and tech debt keep the strictness $Irc$ with a stated reason each (#2719). | the flat $Irc$ in four of the six equations |

Two invariants bound the mechanism. $Irc$ *corrects* measured risk and never creates it: zero measured evidence scores zero in every language (#2655). And the weight on the strictness term is provisional — nothing in the system can validate a language-level shift yet (keyword-rosetta's null hypothesis *is* "no correction", the crucible has no risk labels), so #2720 pilots an outcome fixture before that weight is trusted with more than it carries now.

The tables the engine actually reads are rendered below from the data files, never typed by hand — a hand-written copy is how the repo once carried two tier tables that disagreed for twenty languages.

#### Language strictness

<!-- generated:strictness -->
| language | static types | enforced errors | memory safe | no implicit globals | Irc | Ot |
|---|---|---|---|---|---|---|
| `abap` | yes | **no** | yes | yes | 1 | 1.10 |
| `ada` | yes | **no** | yes | yes | 1 | 1.10 |
| `agc_assembly` | **no** | **no** | **no** | **no** | 4 | 1.40 |
| `apex` | yes | **no** | yes | yes | 1 | 1.10 |
| `assembly` | **no** | **no** | **no** | **no** | 4 | 1.40 |
| `batch` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `blp` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `c` | yes | **no** | **no** | yes | 2 | 1.20 |
| `cobol` | yes | **no** | yes | **no** | 2 | 1.20 |
| `cpp` | yes | **no** | **no** | yes | 2 | 1.20 |
| `csharp` | yes | **no** | yes | yes | 1 | 1.10 |
| `css` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `csv` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `dart` | yes | **no** | yes | yes | 1 | 1.10 |
| `dockerfile` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `fortran` | yes | **no** | **no** | **no** | 3 | 1.30 |
| `glsl` | yes | **no** | yes | yes | 1 | 1.10 |
| `go` | yes | **no** | yes | yes | 1 | 1.10 |
| `groovy` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `haskell` | yes | yes | yes | yes | 0 | 1.00 |
| `hlo` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `html` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `java` | yes | yes | yes | yes | 0 | 1.00 |
| `javascript` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `jcl` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `json` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `kotlin` | yes | **no** | yes | yes | 1 | 1.10 |
| `livecode` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `lua` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `m4` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `makefile` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `markdown` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `matlab` | **no** | **no** | yes | yes | 2 | 1.20 |
| `mlir` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `nix` | **no** | **no** | yes | yes | 2 | 1.20 |
| `objective-c` | yes | **no** | **no** | yes | 2 | 1.20 |
| `pbtxt` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `perl` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `php` | **no** | **no** | yes | yes | 2 | 1.20 |
| `plaintext` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `powershell` | **no** | **no** | yes | yes | 2 | 1.20 |
| `proto` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `python` | **no** | **no** | yes | yes | 2 | 1.20 |
| `ruby` | **no** | **no** | yes | yes | 2 | 1.20 |
| `rust` | yes | yes | yes | yes | 0 | 1.00 |
| `scala` | yes | **no** | yes | yes | 1 | 1.10 |
| `scheme` | **no** | **no** | yes | yes | 2 | 1.20 |
| `shell` | **no** | **no** | yes | **no** | 3 | 1.30 |
| `solidity` | yes | **no** | yes | yes | 1 | 1.10 |
| `sqlite` | **no** | **no** | yes | yes | 2 | 1.20 |
| `swift` | yes | yes | yes | yes | 0 | 1.00 |
| `tcl` | **no** | **no** | yes | yes | 2 | 1.20 |
| `td` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `typescript` | yes | **no** | yes | yes | 1 | 1.10 |
| `xml` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `yacc` | **no** | **no** | **no** | **no** | 4 | 1.40 |
| `yaml` *(no runtime)* | — | — | — | — | 0 | 1.00 |
| `zig` | yes | yes | **no** | yes | 1 | 1.10 |

Dialects read their family's row: `embedded_python` → `python`, `micropython` → `python`.
<!-- /generated:strictness -->

#### Fidelity coefficients the engine reads (signals below 1.00 only)

<!-- generated:fidelity -->
| language | `safety` | `test` | `doc` | `ownership` |
|---|---|---|---|---|
| `c` | 1.00 | **0.67** | 1.00 | 1.00 |
| `embedded_python` | **0.50** | **0.67** | 1.00 | 1.00 |
| `haskell` | **0.67** | 1.00 | 1.00 | 1.00 |
| `perl` | 1.00 | **0.67** | 1.00 | 1.00 |
| `solidity` | 1.00 | 1.00 | 1.00 | **0.25** |
| `typescript` | **0.67** | 1.00 | 1.00 | 1.00 |

Every language and signal not listed reads 1.00. Source: keyword-rosetta `6377eb59` (46 languages), regenerated by `tests/tools/fidelity_table.py`.
<!-- /generated:fidelity -->

## Pipeline Integration
- **Inputs:** Raw regex counts, LOC, language metadata.
- **Outputs:** Normalized, quantized risk tiers (1-5).
- **Dependencies:** Receives input from the scanner extraction module and feeds into the knowledge graph and visual mapping layers.

Scanner Extraction -> Universal Exposure Framework -> Quantized Tier Output

## Tradeoffs
The sigmoid gating principle aggressively suppresses minor risks in large files, intentionally sacrificing micro-level visibility to prevent "alert fatigue" on the macro level. The strictness table is four yes/no columns per language: enough to be reviewable, too coarse to rank two languages that share a row. That coarseness is deliberate until #2720 can say what finer resolution would be measuring.

## Limitations
- The 2.5x defensive multiplier is empirically derived and may not perfectly align with specific internal security postures.
- Path Multipliers ($Mp$) rely on standard directory naming conventions (`src/`, `test/`) which may fail in non-standard repositories.

## Performance Notes
Processing utilizes constant-time floating-point math per file component, resulting in $O(1)$ metric transformation time per unit post-extraction.

## Future Work
- Outcome calibration of the strictness weight against fix-commit history (#2720); the fidelity coefficients are already measured, not tuned.
- Configurable Breach Cap thresholds per repository.

## Related Components
- [Overview of Methodology](08-01-methodology.md)
- [Sub-Equations](08-02-sub-equations.md)
