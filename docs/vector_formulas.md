# Vector calculator formula facts (mechanical audit)

Appendix to [`vectors.md`](vectors.md) — gitgalaxy#2991. A mechanical, per-calculator
extraction (inputs, arithmetic, hardcoded constants, line references) from
[`gitgalaxy/metrics/signal_processor.py`](../gitgalaxy/metrics/signal_processor.py),
performed without interpretation or renaming. New vector names are noted alongside each
calculator; the calculator function names and formulas themselves are unchanged by
gitgalaxy#2991 — this is a naming/documentation change, not a formula change.

## Extraction date

2026-09-13

## Structural finding

**11 of 13 vectors are density formulas** (numerator ÷ LOC/mass). The validation record
(gitgalaxy#2982) convicted the density *shape* specifically — the ledger's reflection
("every density either stayed flat or produced an artifact; the one vector that moved its
assumed direction is a credit/debit net") and the two ticketed artifacts (`debt_markers`
formerly `risk_tech_debt`, #2984; `credential_material` formerly `risk_secrets_risk`, #2979)
are instances of a pattern that turns out to be the layer's default architecture, not
exceptions. Every density formula has the same failure mode available to it: the denominator
moves when code is added/removed, so the score can change with no change in the phenomenon it
names.

**Consequence for the rename.** For the descriptive reframe, each density vector should
either (a) publish its raw numerator alongside (the count IS the presence meter — the
validated x-ray layer is the raw signals), or (b) be re-derived count-based. The sigmoid+cap+
multiplier stacks (9 tuned constants in `complexity_load` alone, breach floors, path
multipliers) assert calibration that was never validated against outcomes — appropriate for
a *display* normalization if documented as such, inappropriate as measurement claims. This
document renames; it does not rework the formulas. The two REWORK-flagged vectors
(`debt_markers`, `credential_material`) still compute the same density formula as before —
see their sections in `vectors.md`.

Also noteworthy: `hist_stability`/`hist_churn` (formerly `risk_stability`/`risk_churn`) — the
family the evidence PROMOTES — are the two calculators with the simplest, most honest
arithmetic in the file (age ratio; commits/√weeks, unbounded).

## Per-calculator table

### 1. `_calc_cog_load` -> `complexity_load` (lines 1390–1443)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_cog_load` |
| **raw_signals Keys Read** | `branch`, `state_mutation`, `concurrency`, `reflection_metaprogramming`, `doc` |
| **Other Inputs** | `loc` (int), `fid` (per-language fidelity dict), `mp` (path multiplier float), `func_gini` (float) |
| **Output Range** | Tuple: (clamped 0–100 float, raw density float); first element capped `min(score * cooling * mp, 100.0)` line 1443 |
| **Arithmetic (Literal)** | Branch density, state mutation density, and concurrency/reflection density (heat) are clamped individually; summed; multiplied by gini-skew factor; passed through sigmoid `100/(1+exp(-4.0*(density-0.75)))` with OverflowError fallback; cooled by doc coverage; final multiply by `mp` |
| **Hardcoded Constants** | `branch_clamp=0.5` (line 1417), `flux_mult=2.0` (line 1418), `flux_clamp=0.75` (line 1418), `async_mult=3.0` (line 1419), `heat_mult=5.0` (line 1419), `gini_threshold=0.7` (line 1425), `gini_multiplier=1.0+(func_gini*0.5)` (line 1426), `sigmoid_slope=4.0` (line 1435), `sigmoid_offset=0.75` (line 1435), `doc_mult=10.0` (line 1440), `cooling_floor=0.5` (line 1441) |
| **DENSITY** | YES – divides by `mass_loc` at lines 1410–1415 (branch_density, flux_density, concurrency_density, heat_density) |

### 2. `_calc_safety` -> `guard_balance` (lines 1445–1498)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_safety` |
| **raw_signals Keys Read** | `high_risk_execution`, `safety_bypasses`, `state_mutation`, `safety`, `test`, `doc` |
| **Other Inputs** | `loc` (int), `irc` (language-specific int), `fid` (per-language fidelity dict), `mp` (float), `mem_mp` (memory context multiplier, default 1.0) |
| **Output Range** | 0–100; capped `max(score, 0.0)` line 1498; conditional breach floor min of 80 (line 1496) |
| **Arithmetic (Literal)** | Attack hits: `high_risk_execution*4.0 + safety_bypasses*1.5 + state_mutation*0.5`; defense hits: `safety*1.0*fid[safety] + test*0.5*fid[test] + doc*0.1*fid[doc]`; if attack==0 return 0; attack density: `(attack_hits+irc)/(mass_loc+20)*mp*mem_mp`; defense density: `defense_hits/(mass_loc+20)`; net: `attack-defense` passed through sigmoid `100/(1+exp(-12.0*net))`; danger floor applied if danger_density > 0.03 and attack > defense |
| **Hardcoded Constants** | `danger_weight=4.0` (1458), `safety_neg_weight=1.5` (1459), `flux_weight=0.5` (1460), `WEIGHT_DEFENSE=1.0` (line 1465), `test_weight=0.5` (1466), `doc_weight=0.1` (1467), `laplace_smoothing=20.0` (line 1475), `sigmoid_slope=12.0` (line 1486), `vulnerability_density_min=0.03` (line 1491), `breach_floor_max=80.0` (line 1493), `breach_floor_mult=500.0` (line 1494) |
| **DENSITY** | YES – divides by `smoothed_loc = mass_loc + 20` at lines 1480–1481 |

### 3. `_calc_tech_debt` -> `debt_markers` (lines 1500–1534) — REWORK flagged

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_tech_debt` |
| **raw_signals Keys Read** | `planned_debt`, `fragile_debt`, `unreferenced_by_name`, `duplicate_logic` |
| **Other Inputs** | `loc` (int), `irc` (int), `mp` (float) |
| **Output Range** | 0–100, capped `min(raw_score*mp, 100.0)` line 1534 |
| **Arithmetic (Literal)** | Slop stress: `orphans*2.0 + duplicates*5.0`; total stress: `planned_debt*1.0 + fragile_debt*3.0 + irc*0.5 + slop_stress`; if both slop and explicit debt present, multiply stress by 1.5; compute density: `(stress/mass_loc)*100`; pass `density-5.0` through sigmoid `100/(1+exp(-0.5*x))`; cap result at 100, multiply by mp |
| **Hardcoded Constants** | `good_debt_weight=1.0` (line 1516), `bad_debt_weight=3.0` (line 1517), `irc_weight=0.5` (line 1518), `orphan_multiplier=2.0` (line 1513), `duplicate_multiplier=5.0` (line 1513), `cross_stress_multiplier=1.5` (line 1524), `threshold=5.0` (line 1527), `sigmoid_slope=0.5` (line 1530) |
| **DENSITY** | YES – divides by `mass_loc` at line 1526 — convicted, #2984 |

### 4. `_calc_documentation` -> `doc_surface` (lines 1536–1586)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_documentation` |
| **raw_signals Keys Read** | NONE directly; reads from function hit_vector: `reflection_metaprogramming` per function |
| **Other Inputs** | `functions` (list of dicts), `doc_umbrella` (float, default 0.0) |
| **Output Range** | 0–100, capped `min(100.0*ratio*shield, 100.0)` line 1586 |
| **Arithmetic (Literal)** | For each non-synthetic function unit: weight = (2.0 if public else 1.0) + reflection_count; exposed_weight = weight if not documented; score = `100 * (exposed_weight/total_weight) * (1.0 - 0.5*doc_umbrella)` capped at 100 |
| **Hardcoded Constants** | `public_weight=2.0` (line 1559), `umbrella_shield=0.5` (line 1560) |
| **DENSITY** | NO – per-unit weight ratio (lines 1543–1544 doc string: "A ratio over units, never a density over lines") |

### 5. `_calc_verification` -> `test_surface` (lines 1588–1692)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_verification` |
| **raw_signals Keys Read** | `high_risk_execution` (file-level danger, line 1659) |
| **Other Inputs** | `loc` (int), `is_protected` (bool), `ot` (language opacity), `fid` (fidelity dict), `mp` (float), `functions` (list), `test_coverage_map` (dict by name), `umbrella_bonus` (float, default 0.0), `popularity` (int, default 0) |
| **Output Range** | 0–100, capped `min(base_score, 100.0)` line 1692; breach cap at 80 line 1690 |
| **Arithmetic (Literal)** | For each function: base_impact = max(func_impact - (test*fid[test] + safety*fid[safety] - test_skip*2.0), 0); defensive_ratio = sum(test_impact*param_mult/target_count)/func_impact; untested = base_impact/(1.0+1.5*defensive_ratio); accumulate untested; add file_level high_risk_execution; raw_density = (total_untested/mass_loc)*ot; guidestar_dampener = max(1.0 - umbrella_bonus/100, 0.1); blast_radius = mp + min(popularity*0.2, 3.0); adjusted_density = (raw_density * dampener) * blast_radius; sigmoid on (adjusted_density - 15.0): 100/(1+exp(-0.25*x)) |
| **Hardcoded Constants** | `asymptotic_dampener=1.5` (line 1606), `param_multiplier=2.0` (line 1648), `test_skip_penalty=2.0` (line 1627), `threshold_base=15.0` (line 1676), `sigmoid_slope=0.25` (line 1677), `popularity_scalar=0.2` (line 1671), `blast_radius_cap=3.0` (line 1671), `breach_untested_ratio=0.8` (line 1689), `breach_floor=80.0` (line 1690) |
| **DENSITY** | YES – divides by `mass_loc` at line 1664 |

### 6. `_calc_graveyard` -> `dead_code_surface` (lines 1694–1711)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_graveyard` |
| **raw_signals Keys Read** | `dead_code` |
| **Other Inputs** | `total_loc` (float), `mp` (float) |
| **Output Range** | 0–100, capped `min(score, 100.0)` line 1711 |
| **Arithmetic (Literal)** | deprecated_lines = dead_code_hits * 3.0; density = (deprecated_lines / max(total_loc, EVIDENCE_MASS_FLOOR)) * 100; threshold = 10.0 / max(mp, 0.1); sigmoid on (density - threshold): 100/(1+exp(-0.3*x)) |
| **Hardcoded Constants** | `hit_mult=3.0` (line 1700), `threshold_base=10.0` (line 1705), `sigmoid_slope=0.3` (line 1707), `safe_mass_floor=EVIDENCE_MASS_FLOOR` (line 1703, default 50) |
| **DENSITY** | YES – divides by `max(total_loc, safe_mass_floor)` line 1703 |

### 7. `_calc_api_exposure` -> `connectivity` (lines 1713–1740)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_api_exposure` |
| **raw_signals Keys Read** | `api`, `encapsulation` |
| **Other Inputs** | `total_loc` (int), `popularity` (int, default 0) |
| **Output Range** | 0–100, capped `min(exposure_ratio*volume_weight*network_multiplier*100, 100.0)` line 1740 |
| **Arithmetic (Literal)** | exposure_ratio = api / (api + encapsulation); network_multiplier = 0.2 if popularity==0 else min(1.0 + log1p(popularity)/5.0, 2.0); volume_weight = log1p(api) / log1p(max(total_loc, EVIDENCE_MASS_FLOOR)); final = exposure_ratio * volume_weight * network_multiplier * 100 capped at 100 |
| **Hardcoded Constants** | `isolated_multiplier=0.2` (line 1732), `network_multiplier_base=1.0` (line 1734), `popularity_scalar=0.2` (line 1734), `network_multiplier_cap=2.0` (line 1734), `log_divisor=5.0` (line 1734) |
| **DENSITY** | YES – includes logarithmic mass correction dividing log(api) by log(total_loc) line 1738 |

### 8. `_calc_concurrency` -> `concurrency_surface` (lines 1742–1771)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_concurrency` |
| **raw_signals Keys Read** | `concurrency`, `sync_locks` |
| **Other Inputs** | `loc` (int), `mp` (float) |
| **Output Range** | 0–100, capped `min(sigmoid*100*mp, 100.0)` line 1771 |
| **Arithmetic (Literal)** | net_concurrency = max(concurrency - (sync_locks * 1.5), 0.0); if net==0 return 0; density = (net_concurrency / (mass_loc + 150)) * 100; sigmoid on (density - 4.0): 100/(1+exp(-0.4*x)); multiply by 100*mp; cap at 100 |
| **Hardcoded Constants** | `sync_locks_multiplier=1.5` (line 1759), `loc_padding=150` (line 1753), `threshold_base=4.0` (line 1768), `sigmoid_slope=0.4` (line 1769) |
| **DENSITY** | YES – divides by `(mass_loc + 150)` line 1766 |

### 9. `_calc_state_flux` -> `mutation_surface` (lines 1773–1799)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_state_flux` |
| **raw_signals Keys Read** | `state_mutation`, `immutability_locks` |
| **Other Inputs** | `loc` (int), `mp` (float) |
| **Output Range** | 0–100, capped `min(sigmoid*100*mp, 100.0)` line 1799 |
| **Arithmetic (Literal)** | net_volatility = max(state_mutation - (immutability_locks * 0.5), 0.0); if net==0 return 0; density = (net_volatility / (mass_loc + 0)) * 100; sigmoid on (density - 15.0): 100/(1+exp(-0.2*x)); multiply by 100*mp; cap at 100 |
| **Hardcoded Constants** | `freeze_hits_multiplier=0.5` (line 1787), `loc_padding=0` (line 1781), `threshold_base=15.0` (line 1796), `sigmoid_slope=0.2` (line 1797) |
| **DENSITY** | YES – divides by `(mass_loc + 0)` = `mass_loc` line 1794 |

### 10. `_calc_spec_alignment` -> `spec_alignment` (lines 1801–1809)

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_spec_alignment` |
| **raw_signals Keys Read** | `func_start`, `class_start`, `spec_exposure` |
| **Other Inputs** | `mp` (float) |
| **Output Range** | 0–100, capped `min((1-ratio)*100*mp, 100.0)` line 1809 |
| **Arithmetic (Literal)** | entities = func_start + class_start; if entities==0 return 0; ratio = min(spec_exposure / entities, 1.0); score = (1.0 - ratio) * 100 * mp; cap at 100 |
| **Hardcoded Constants** | NONE |
| **DENSITY** | NO – per-entity ratio, not LOC-based (line 1808 comment: file with no functions/classes scores 0) |

### 11. `_calc_secrets_risk` -> `credential_material` (lines 1818–1863) — REWORK flagged

| Field | Value |
|-------|-------|
| **Function Name** | `_calc_secrets_risk` |
| **raw_signals Keys Read** | `sec_hardcoded_secrets`, `debug_prints`, `dead_code`, `globals`, `llm_api`, `sec_reflection_metaprogramming` |
| **Other Inputs** | `loc` (int), `mp` (float) |
| **Output Range** | 0–100; floored at 0.0 if < 5.0 (line 1861); final cap `min(score*mp, 100.0)` line 1863 |
| **Arithmetic (Literal)** | base_leak = sec_hardcoded_secrets * 10.0; careless_amplifiers = 1.0 + debug_prints + dead_code + globals; if llm_api > 0 and globals == 0, careless_amplifiers *= 3.0; if not paranoid and sec_reflection==0, cap careless at 2.0; leak_mass = base_leak * careless; density = (leak_mass / max(loc + 50, 1)) * 100; sigmoid on (density - 3.0): 100/(1+exp(-1.0*x)) or (paranoid) on (density - 0.5): 100/(1+exp(-2.0*x)); if score < 5 then 0; cap at 100*mp |
| **Hardcoded Constants** | `base_leak_weight=10.0` (line 1823), `llm_api_amplifier=3.0` (line 1834), `careless_amplifier_cap=2.0` (line 1837), `loc_padding=50` (line 1845), `std_threshold=3.0` (line 1852), `std_slope=1.0` (line 1853), `paranoid_threshold=0.5` (line 1849), `paranoid_slope=2.0` (line 1850), `score_floor=5.0` (line 1860) |
| **DENSITY** | YES – divides by `(loc + 50)` line 1845 — convicted, ρ=−0.91 vs LOC, #2979 |

### 12 & 13. `_calc_raw_temporal_signals` -> `hist_stability`, `hist_churn` (lines 1273–1295) — Returns Pair: (stability_score, raw_churn_freq)

#### 12a. `hist_stability` (Stability Score)

| Field | Value |
|-------|-------|
| **Signal Name** | `stability_score` (first return value, line 1289) |
| **Input Source** | `temp` dict keys: `is_git_tracked`, `mtime`, `repo_min_time`, `repo_max_time` |
| **Output Range** | 0–100, capped `min(stability_ratio*100, 100.0)` line 1289 |
| **Arithmetic (Literal)** | If not git-tracked, return 50.0; seconds_from_max = max(repo_max - mtime, 0); time_range = max(repo_max - repo_min, 1.0); stability_ratio = seconds_from_max / time_range; score = min(ratio * 100, 100.0) |
| **Hardcoded Constants** | `default_score=50.0` (line 1276), `time_range_floor=1.0` (line 1285), `untracked_default_mtime=100.0` cap (line 1289) |
| **DENSITY** | NO – age-based, not LOC-based |

#### 12b. `hist_churn` (Raw Churn Frequency)

| Field | Value |
|-------|-------|
| **Signal Name** | `raw_churn_freq` (second return value, line 1293) |
| **Input Source** | `temp` dict keys: `is_git_tracked`, `repo_max_time`, `mtime`, `commit_count` |
| **Output Range** | Unbounded (commits / sqrt(age_weeks), typically 0–50 range but no hard cap) |
| **Arithmetic (Literal)** | If not git-tracked, return 0.0; seconds_from_max = max(repo_max - mtime, 0); age_weeks = max(seconds_from_max / 604800, 1.0); raw_churn = commits / sqrt(age_weeks) |
| **Hardcoded Constants** | `seconds_per_week=604800.0` (line 1292), `min_age_weeks=1.0` (line 1292) |
| **DENSITY** | NO – normalized by sqrt(weeks), not by lines of code |

## Notes

- All calculator functions enforce 0–100 capping on their final scores (except
  `raw_churn_freq`, which is unbounded but normalized by time).
- The `mass_loc` function (line 1354) applies an evidence-mass floor of 50 LOC by default,
  meaning files under 50 lines are scored as if they were 50 lines (preventing tiny files
  from inflating density ratios).
- Path multipliers (`mp`) are applied last in nearly all formulas, as a context-based scaling
  factor.
- Per-language constants (`irc` = code-reflection count, `ot` = opacity tax, `fid` =
  per-signal fidelity) are fetched via `_language_constants()` (line 2093).
- Sigmoid functions use `try/except OverflowError` guards to fallback to hard 0 or 100 at
  density extremes.
- Line numbers cited are exact at extraction time (2026-09-13); function names in
  `signal_processor.py` were not renamed by gitgalaxy#2991 — only the persisted vector names
  and their display labels changed. Extraction performed mechanically without interpretation.
