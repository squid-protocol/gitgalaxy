import logging

import pytest

from gitgalaxy.metrics.signal_processor import SignalProcessor


@pytest.fixture
def processor():
    """Initializes the Signal Processor."""
    return SignalProcessor()


# ==============================================================================
# SYNTHETIC GALAXY DATA (MOCKING THE DETECTOR PAYLOADS)
# ==============================================================================
def create_synthetic_star(processor, name, loc, raw_signals=None, forensics=None, functions=None):
    """Generates a perfectly structured raw detector payload."""
    base_signals = {
        "branch": 0,
        "structural_boundaries": 0,
        "args": 0,
        "func_start": 0,
        "high_risk_execution": 0,
        "sec_high_risk_execution": 0,
        "safety_bypasses": 0,
        "safety": 0,
        "state_mutation": 0,
        "todo": 0,
        "fixme": 0,
        "empty_stubs": 0,
        "fragile_debt": 0,
        "planned_debt": 0,
        "doc": 0,
        "test": 0,
        "api": 0,
        "concurrency": 0,
        "sync_locks": 0,
        "dead_code": 0,
        "spec": 0,
        "pointers": 0,
        "indent_tabs": 0,
        "indent_spaces": 0,
    }

    if raw_signals:
        base_signals.update(raw_signals)

    meta = {
        "path": f"src/{name}.py",
        "name": name,
        "lang_id": "python",
        "coding_loc": loc,
        "telemetry": {},
        "functions": functions or [{"name": "mock_func", "loc": loc, "branch": base_signals["branch"]}],
        "raw_imports": ["os", "sys"],
        "equations": base_signals,  # Keep key backwards compatible for legacy passes if needed
        "dependency_network": {
            "direct_upstream": 2,
            "direct_downstream": 5,
            "total_upstream": 10,
            "total_downstream": 20,
        },
    }

    if forensics:
        meta["forensics"] = forensics
        meta["git_forensics"] = forensics

    return meta, base_signals


# ==============================================================================
# TEST 1: THE PERFECT FILE (Zero Risk Baseline)
# ==============================================================================
def test_signal_processor_perfect_baseline(processor):
    """Proves a file with perfect safety/docs results in 0.0% risk exposures."""
    meta, sig = create_synthetic_star(processor, "perfect", 50, {"safety": 10, "doc": 20, "test": 5})
    res = processor.calculate_risk_vector(meta, sig)

    assert res["risk_vector"][0] < 10.0, "Perfect file failed Cog Load baseline!"
    assert res["risk_vector"][1] < 10.0, "Perfect file failed Error Risk baseline!"
    assert res["risk_vector"][2] == 0.0, "Perfect file has phantom tech debt!"


# ==============================================================================
# TEST 2: THE APOCALYPSE FILE (100% Risk Breaches)
# ==============================================================================
def test_signal_processor_apocalypse_breaches(processor):
    """Proves an overwhelmingly terrible file successfully triggers 100% risk."""
    # Loc MUST be >= 15 to bypass the small-file 5.0% bypass in _calc_cog_load!
    meta, sig = create_synthetic_star(
        processor,
        "nightmare",
        20,
        {
            "branch": 5000,
            "high_risk_execution": 5000,
            "sec_high_risk_execution": 5000,
            "state_mutation": 5000,
            "planned_debt": 5000,
            "fragile_debt": 5000,
            "api": 5000,
            "concurrency": 5000,
        },
    )

    res = processor.calculate_risk_vector(meta, sig)

    assert res["risk_vector"][0] > 80.0, "Failed to max out Cognitive Load!"
    assert res["risk_vector"][1] > 80.0, "Failed to max out Error Risk!"
    assert res["risk_vector"][2] > 80.0, "Failed to max out Tech Debt!"


# ==============================================================================
# TEST 2b: THE PROVABLY-EMPTY TINY FILE (True Zero, Not the Small-File Floor)
# ==============================================================================
def test_signal_processor_empty_tiny_file_scores_true_zero(processor):
    """
    Proves a provably empty <=2 LOC file (e.g. a near-blank __init__.py) gets
    a true 0.0 Cognitive Load, not the small-file 5.0 floor _calc_cog_load
    applies to files under 15 LOC. Regression guard for a bug where this
    exact carve-out existed in the code but was unreachable -- an earlier
    `if safe_loc < 15` branch always returned first, so a 1-2 line file with
    zero signals was still forced to 5.0.
    """
    meta, sig = create_synthetic_star(processor, "blank_init", 2)
    meta["lang_id"] = "rust"  # zero strictness gaps (irc=0); see analysis_lens.LANGUAGE_STRICTNESS
    res = processor.calculate_risk_vector(meta, sig)

    idx_cog = processor.RISK_SCHEMA.index("cognitive_load")
    assert res["risk_vector"][idx_cog] == 0.0, (
        "Provably empty tiny file should score a true 0.0, not the small-file floor!"
    )


# ==============================================================================
# TEST 2c: ENCAPSULATION RATIO USES REAL core_var_decl (#1145 regression guard)
# ==============================================================================
def test_signal_processor_encapsulation_ratio_uses_real_var_decl(processor):
    """
    Before #1145 gave `core_var_decl` a real producer in detector.py, it was
    permanently 0 in every real scan. That silently floored `encapsulation_ratio`
    (this method, ~line 502) to 0.0 for ANY file with a nonzero `globals` hit,
    regardless of how much state was actually encapsulated -- the ratio's
    denominator (`total_vars + global_vars`) collapsed to just `global_vars`,
    making `1.0 - (global_vars / global_vars)` always 0.0. A file that mostly
    locks its state inside functions (18 local decls vs. 2 global accesses)
    must now score a healthy ratio, not the old universal-floor 0.0.
    """
    meta, sig = create_synthetic_star(processor, "mostly_encapsulated", 50, {"core_var_decl": 18, "globals": 2})
    res = processor.calculate_risk_vector(meta, sig)
    ratio = res["telemetry"]["encapsulation_ratio"]
    assert ratio > 0.5, f"18 local declarations vs. 2 global accesses should score well-encapsulated, got {ratio}"


def test_signal_processor_encapsulation_ratio_all_global_still_zero(processor):
    """Companion to the above: a file with ONLY global state (0 local decls) should
    still floor to 0.0 -- proving the fix widened the denominator correctly rather
    than breaking the genuinely-all-global case."""
    meta, sig = create_synthetic_star(processor, "all_global", 50, {"core_var_decl": 0, "globals": 5})
    res = processor.calculate_risk_vector(meta, sig)
    assert res["telemetry"]["encapsulation_ratio"] == 0.0


def test_signal_processor_small_file_scores_on_counts(processor):
    """
    #2655: the old flat 5.0 small-file floor (`loc < 15`) is gone. A file below
    the evidence-mass floor is scored on its COUNTS, as if it were
    EVIDENCE_MASS_FLOOR lines long -- so a 10-LOC file with 3 branches must score
    exactly what a 49-LOC file with 3 branches scores, and exactly what a
    50-LOC file with 3 branches scores (the floor is continuous, not a cliff).
    """
    idx_cog = processor.RISK_SCHEMA.index("cognitive_load")
    scores = {}
    for loc in (3, 10, 14, 15, 16, 49, 50):
        meta, sig = create_synthetic_star(processor, f"small_{loc}", loc, {"branch": 3})
        scores[loc] = processor.calculate_risk_vector(meta, sig)["risk_vector"][idx_cog]

    assert scores[10] != 5.0 or scores[49] == 5.0, "The flat 5.0 floor should no longer exist"
    assert len(set(scores.values())) == 1, f"Identical signals must score identically below the floor: {scores}"
    assert 0.0 < scores[10] < 20.0, f"3 branches per 50 lines is low, not zero and not red: {scores[10]}"

    # Flag + mass are exposed so consumers can tell a count-regime score apart.
    meta, sig = create_synthetic_star(processor, "flagged", 10, {"branch": 3})
    tel = processor.calculate_risk_vector(meta, sig)["telemetry"]
    assert tel["mass_floored"] is True
    assert tel["evidence_mass"] == processor.EVIDENCE_MASS_FLOOR
    meta, sig = create_synthetic_star(processor, "unflagged", 120, {"branch": 3})
    tel = processor.calculate_risk_vector(meta, sig)["telemetry"]
    assert tel["mass_floored"] is False
    assert tel["evidence_mass"] == 120.0


def test_signal_processor_branchless_file_zero_cog_at_any_length(processor):
    """
    #2655: "no branches, no cognitive load" used to apply only above 50 LOC, so a
    branchless file with state mutation scored ~6 at 50 lines and 0.0 at 51. The
    rule now applies at every length.
    """
    idx_cog = processor.RISK_SCHEMA.index("cognitive_load")
    for loc in (2, 10, 30, 50, 51, 200):
        meta, sig = create_synthetic_star(processor, f"flux_only_{loc}", loc, {"state_mutation": 6, "branch": 0})
        assert processor.calculate_risk_vector(meta, sig)["risk_vector"][idx_cog] == 0.0, loc


# ==============================================================================
# TEST 3: ZERO-DIVISION & EMPTY STATE FALLBACKS
# ==============================================================================
def test_signal_processor_zero_division_shields(processor):
    """Ensures no ZeroDivisionError crashes the pipeline on 0 LOC."""
    meta, sig = create_synthetic_star(processor, "ghost", 0)
    meta["functions"] = []

    try:
        res = processor.calculate_risk_vector(meta, sig)
        assert "risk_vector" in res, "Failed to output risk vector!"
        assert res["risk_vector"][0] >= 0.0, "Cog load dropped below zero!"
    except ZeroDivisionError:
        pytest.fail("Signal Processor crashed with ZeroDivisionError on a 0 LOC file!")


# ==============================================================================
# TEST 4: ERROR RISK FLOOR CAP (The 30% Testing Minimum)
# ==============================================================================
def test_signal_processor_error_risk_floor(processor):
    """Proves high danger density floors the Error Risk to ~30% regardless of safety."""
    meta, sig = create_synthetic_star(
        processor,
        "shielded",
        5,
        {"high_risk_execution": 5000, "sec_high_risk_execution": 5000, "safety": 500, "test": 500},
    )

    res = processor.calculate_risk_vector(meta, sig)
    assert res["risk_vector"][1] >= 29.0, (
        f"Error Risk Floor failed! Allowed heavy danger to drop to {res['risk_vector'][1]}%"
    )


# ==============================================================================
# TEST 5: API & CONCURRENCY EXPOSURES
# ==============================================================================
def test_signal_processor_api_and_concurrency(processor):
    """Proves the engine accurately calculates API and Concurrency risks."""
    meta, sig = create_synthetic_star(processor, "api_gw", 10, {"api": 500, "concurrency": 500})
    meta["functions"] = [{"name": "mock_func", "loc": 10, "branch": 0}]

    res = processor.calculate_risk_vector(meta, sig)
    assert res["risk_vector"][4] > 30.0, "API Exposure math failed!"
    assert res["risk_vector"][5] > 30.0, "Concurrency Exposure math failed!"


# ==============================================================================
# TEST 6: CIVIL WAR (Indentation Consistency)
# ==============================================================================
def test_signal_processor_indentation_style(processor):
    """
    Proves indentation_style accurately reads Tab vs Space purity as descriptive
    telemetry -- not a RISK_SCHEMA exposure (#1147: this was never a real risk).
    """
    mt, sigt = create_synthetic_star(processor, "t", 100, {"indent_tabs": 100})
    ms, sigs = create_synthetic_star(processor, "s", 100, {"indent_spaces": 100})
    mm, sigm = create_synthetic_star(processor, "m", 100, {"indent_tabs": 50, "indent_spaces": 50})

    rt = processor.calculate_risk_vector(mt, sigt)
    rs = processor.calculate_risk_vector(ms, sigs)
    rm = processor.calculate_risk_vector(mm, sigm)

    assert rt["telemetry"]["indentation_style"] == "Tabs", "Pure Tabs failed!"
    assert rs["telemetry"]["indentation_style"] == "Spaces", "Pure Spaces failed!"
    assert rm["telemetry"]["indentation_style"] == "Mixed (50.0% Spaces / 50.0% Tabs)", "Mixed indentation failed!"


# ==============================================================================
# TEST 7: SIBLING TEST BONUS (Cross-File Network Mapping)
# ==============================================================================
def test_signal_processor_sibling_test_bonus(processor):
    """Proves the umbrella_bonus parameter halves the testing risk penalty."""
    m1, sig1 = create_synthetic_star(processor, "logic", 100)
    m1["functions"] = [{"name": "mock_func", "impact": 5000.0, "hit_vector": {}}]

    m2, sig2 = create_synthetic_star(processor, "logic", 100)
    m2["functions"] = [{"name": "mock_func", "impact": 5000.0, "hit_vector": {}}]

    high_risk = processor.calculate_risk_vector(m1, sig1, umbrella_bonus=0.0)
    low_risk = processor.calculate_risk_vector(m2, sig2, umbrella_bonus=50.0)

    idx_test = processor.RISK_SCHEMA.index("verification")
    assert low_risk["risk_vector"][idx_test] < high_risk["risk_vector"][idx_test], "Sibling Test Bonus failed to apply!"


# ==============================================================================
# TEST 8: GIT FORENSICS (Deep Churn & Stability)
# ==============================================================================
def test_signal_processor_git_forensics(processor):
    """Proves the Deep Churn and Instability formulas process git metadata across multiple files."""
    m1, sig1 = create_synthetic_star(processor, "vol_max", 100)
    # Inject exact temporal keys expected by _calc_raw_temporal_signals
    m1["temporal_telemetry"] = {
        "is_git_tracked": True,
        "mtime": 100,
        "repo_min_time": 0,
        "repo_max_time": 110,
        "commit_count": 500,
    }
    # Inject exact authors dict expected by _calculate_silo_risk
    m1["authors"] = {"dev_a": 500}  # 100% silo risk

    m2, sig2 = create_synthetic_star(processor, "vol_min", 100)
    m2["temporal_telemetry"] = {
        "is_git_tracked": True,
        "mtime": 0,
        "repo_min_time": 0,
        "repo_max_time": 110,
        "commit_count": 5,
    }
    m2["authors"] = {"dev_a": 5, "dev_b": 5}  # 50% distribution

    # Process both and properly unwrap the telemetry
    tel1 = processor.calculate_risk_vector(m1, sig1)
    m1["telemetry"] = tel1["telemetry"]
    m1["risk_vector"] = tel1["risk_vector"]
    m1["file_impact"] = tel1["file_impact"]

    tel2 = processor.calculate_risk_vector(m2, sig2)
    m2["telemetry"] = tel2["telemetry"]
    m2["risk_vector"] = tel2["risk_vector"]
    m2["file_impact"] = tel2["file_impact"]

    parsed = [m1, m2]
    processor.summarize_galaxy_metrics(parsed, [])

    assert m1["risk_vector"][9] > 0.0, "Failed to calculate Instability!"
    assert m1["risk_vector"][10] > 0.0, "Failed to calculate Deep Churn!"
    assert m1["telemetry"]["author_distribution"] == 100.0, "Failed to calculate Silo Risk!"


# ==============================================================================
# TEST 9: THE OVERFLOW SHIELD (Math Limits)
# ==============================================================================
def test_signal_processor_math_overflow_shield(processor):
    """Proves astronomical negative densities trigger and survive the OverflowError."""
    meta, sig = create_synthetic_star(
        processor, "absurd", 1, {"sec_high_risk_execution": -99999999, "branch": -99999999}
    )

    try:
        res = processor.calculate_risk_vector(meta, sig)
        assert "risk_vector" in res
    except OverflowError:
        pytest.fail("Signal Processor crashed with an OverflowError on extreme density!")


# ==============================================================================
# TEST 10: GALAXY AGGREGATORS (Summary & Forensics)
# ==============================================================================
def test_signal_processor_aggregations(processor):
    """Triggers the final galaxy-level summary and forensic reports."""
    m1, sig1 = create_synthetic_star(processor, "f1", 100, {"branch": 10})
    m2, sig2 = create_synthetic_star(processor, "f2", 200, {"sec_high_risk_execution": 10})

    # Process and unwrap correctly!
    tel1 = processor.calculate_risk_vector(m1, sig1)
    m1["telemetry"] = tel1["telemetry"]
    m1["risk_vector"] = tel1["risk_vector"]
    m1["file_impact"] = tel1["file_impact"]

    tel2 = processor.calculate_risk_vector(m2, sig2)
    m2["telemetry"] = tel2["telemetry"]
    m2["risk_vector"] = tel2["risk_vector"]
    m2["file_impact"] = tel2["file_impact"]

    parsed = [m1, m2]
    unparsed = [{"path": "bad.py", "reason": "corrupted"}]

    summary = processor.summarize_galaxy_metrics(parsed, unparsed)
    assert isinstance(summary, dict)

    forensics = processor.generate_forensic_report(parsed)
    # #3112: the report no longer carries a "cumulative_risk" composite -- it
    # was a unitless sum over 13 independently scaled vectors, ~31% of which
    # was ceiling-defaulted or ablated to zero. file_impact is the unit-honest
    # ranking that replaced it; assert the replacement exists rather than just
    # asserting the absence, so this test still pins a real contract.
    assert "cumulative_risk" not in forensics, "The cumulative-risk composite was removed in #3112"
    assert "file_impact" in forensics, "Forensic report missing the file_impact ranking!"


def test_ecosystem_baseline_is_the_composition_repo_archetype(processor):
    """
    #1159: the retired repo K-Means model ran before file archetypes were
    assigned, so it scored every repo as an all-zero vector ("Cluster 3").
    The baseline now reports the composition repo archetype and its fit z,
    and no longer writes per-file cluster telemetry.
    """
    stars = []
    for i in range(3):
        m, sig = create_synthetic_star(processor, f"f{i}", 100, {"branch": 5})
        out = processor.calculate_risk_vector(m, sig)
        m.update(telemetry=out["telemetry"], risk_vector=out["risk_vector"], file_impact=out["file_impact"])
        stars.append(m)

    summary = processor.summarize_galaxy_metrics(stars, [])

    inner = summary["summary"]
    assert inner["repo_composition_archetype"]
    assert summary["repo_macro_species"] == {
        "name": inner["repo_composition_archetype"],
        "z_score": inner["repo_composition_z"],
    }
    for m in stars:
        assert "ecosystem_baseline_cluster" not in m["telemetry"]
        assert "dist_to_0" not in m["telemetry"]


def test_systemic_bottlenecks_rank_only_computed_metrics(processor):
    """
    #3027: each bottleneck ranking multiplies one centrality metric by a risk.
    A file whose metric was not computed (None -- a centrality past its work
    budget, or a failed computation) must not enter that ranking; read as
    0.0 it used to fill every list with zero-score files picked by path order.
    """
    files = []
    for name, net in (
        ("computed", {"normalized_blast_radius": 2.0, "betweenness_score": 0.3, "closeness_score": 0.4}),
        ("zero_dep", {"normalized_blast_radius": 1.0, "betweenness_score": None, "closeness_score": None}),
    ):
        meta, sig = create_synthetic_star(processor, name, 100, {"branch": 10, "state_mutation": 20})
        scored = processor.calculate_risk_vector(meta, sig)
        meta["telemetry"] = scored["telemetry"]
        meta["risk_vector"] = scored["risk_vector"]
        meta["file_impact"] = scored["file_impact"]
        meta["telemetry"]["network_metrics"] = net
        files.append(meta)

    bottlenecks = processor.generate_forensic_report(files)["systemic_bottlenecks"]

    def paths(key):
        return [entry["path"] for entry in bottlenecks[key]]

    assert paths("cascading_state_mutation") == ["src/computed.py"]
    assert paths("fragile_dependency_chain") == ["src/computed.py"]
    assert sorted(paths("undocumented_critical_path")) == ["src/computed.py", "src/zero_dep.py"]


# ==============================================================================
# TEST 11: THE MINIFIED VENDOR TRIPWIRE
# ==============================================================================
def test_signal_processor_minified_tripwire(processor, caplog):
    """
    Proves minified files bypass standard math and surface malicious intent via a
    critical log, rather than fabricating a risk-vector spike on a metric this
    AST-less engine can't structurally back (#1020 removed the obscured_payload/
    injection_surface composites this tripwire used to spike).
    """
    meta, sig = create_synthetic_star(processor, "vendor_bundle", 1000, {"sec_high_risk_execution": 50})
    meta["is_minified"] = True  # Trigger the tripwire

    with caplog.at_level(logging.CRITICAL, logger="processing"):
        res = processor.calculate_risk_vector(meta, sig)

    # Standard cognitive load should be 0.0, and the file impact forced to 1.0
    assert res["risk_vector"][0] == 0.0, "Standard cognitive load should be bypassed for minified files!"
    assert res["file_impact"] == 1.0, "Minified files should have an impact of exactly 1.0!"

    # All standard risk math is bypassed for minified files -- the whole vector stays zeroed.
    assert all(v == 0.0 for v in res["risk_vector"]), "Minified files should bypass all standard risk math!"

    # The malicious intent is still surfaced, just via a critical log instead.
    assert "OBFUSCATION DETECTED" in caplog.text, "Minified tripwire failed to flag malicious intent!"


# ==============================================================================
# TEST 12: THE DOCUMENTATION BYPASS & SECRETS LEAK
# ==============================================================================
def test_signal_processor_doc_and_secrets_bypass(processor):
    """Proves markdown files skip logic math, and exposed secrets spike risk."""
    # 1. Test Documentation Bypass
    meta_doc, sig_doc = create_synthetic_star(processor, "readme", 500, {"branch": 500})
    meta_doc["lang_id"] = "markdown"  # Claim to be docs

    res_doc = processor.calculate_risk_vector(meta_doc, sig_doc)
    assert res_doc["risk_vector"][0] == 0.0, "Documentation shouldn't calculate logic cognitive load!"

    # 2. Test Critical Secrets Leak
    meta_sec, sig_sec = create_synthetic_star(processor, "keys", 10)
    meta_sec["metadata"] = {"reason": "CRITICAL LEAK"}  # #374: real key is "reason", not "aperture_reason"

    res_sec = processor.calculate_risk_vector(meta_sec, sig_sec)
    assert 100.0 in res_sec["risk_vector"], "Critical Leak failed to spike the Secrets Risk to 100%!"


def test_signal_processor_doc_language_secrets_risk_not_blanket_zeroed(processor):
    """
    #2978: the Static Literature Override zeroes the whole risk_vector for
    doc_languages (markdown/plaintext/rst/text) except churn/documentation --
    but a hardcoded credential in a README or plaintext config is a real leak.
    secrets_risk must be carved out of the blanket zero and reflect a real
    sec_hardcoded_secrets hit the same way it does for non-doc languages,
    instead of silently reading 0 no matter how many leaks are present.
    """
    idx_secrets = processor.RISK_SCHEMA.index("secrets_risk")

    meta_clean, sig_clean = create_synthetic_star(processor, "readme_clean", 50)
    meta_clean["lang_id"] = "markdown"
    res_clean = processor.calculate_risk_vector(meta_clean, sig_clean)
    assert res_clean["risk_vector"][idx_secrets] == 0.0, "Clean markdown should have zero secrets risk!"

    meta_leaky, sig_leaky = create_synthetic_star(
        processor, "readme_leaky", 50, {"sec_hardcoded_secrets": 5, "debug_prints": 3}
    )
    meta_leaky["lang_id"] = "markdown"
    res_leaky = processor.calculate_risk_vector(meta_leaky, sig_leaky)
    assert res_leaky["risk_vector"][idx_secrets] > 0.0, "Markdown with a real leak must not read 0 secrets risk!"

    meta_plain, sig_plain = create_synthetic_star(processor, "notes_leaky", 50, {"sec_hardcoded_secrets": 5})
    meta_plain["lang_id"] = "plaintext"
    res_plain = processor.calculate_risk_vector(meta_plain, sig_plain)
    assert res_plain["risk_vector"][idx_secrets] > 0.0, "Plaintext with a real leak must not read 0 secrets risk!"

    # The rest of the doc_languages bypass must stay intact -- this is a narrow
    # carve-out, not a reversion of the override.
    idx_cog = processor.RISK_SCHEMA.index("cognitive_load")
    assert res_leaky["risk_vector"][idx_cog] == 0.0, "Cognitive load must stay bypassed for doc languages!"


def test_signal_processor_doc_and_secrets_churn_survives_normalization(processor):
    """
    Regression test for #245: documentation and critical-leak overrides must
    report raw_churn_freq in their telemetry, otherwise the Pass 2 global
    normalization pass (_normalize_temporal_metrics) reads back the default
    0.0 and silently zeroes out the churn score these branches just computed.
    """
    churn_idx = processor.RISK_SCHEMA.index("churn")
    hot_temporal = {
        "is_git_tracked": True,
        "mtime": 100,
        "repo_min_time": 0,
        "repo_max_time": 110,
        "commit_count": 500,
    }

    meta_doc, sig_doc = create_synthetic_star(processor, "readme", 500, {"branch": 500})
    meta_doc["lang_id"] = "markdown"
    meta_doc["temporal_telemetry"] = hot_temporal

    meta_sec, sig_sec = create_synthetic_star(processor, "keys", 10)
    meta_sec["metadata"] = {"reason": "CRITICAL LEAK"}  # #374: real key is "reason", not "aperture_reason"
    meta_sec["temporal_telemetry"] = hot_temporal

    for meta, sig in ((meta_doc, sig_doc), (meta_sec, sig_sec)):
        res = processor.calculate_risk_vector(meta, sig)
        meta["telemetry"] = res["telemetry"]
        meta["risk_vector"] = res["risk_vector"]
        meta["file_impact"] = res["file_impact"]
        assert meta["risk_vector"][churn_idx] > 0.0, "Override branch failed to compute an initial churn score!"
        assert "raw_churn_freq" in meta["telemetry"], (
            "Override branch must publish raw_churn_freq so Pass 2 normalization doesn't clobber it back to 0.0!"
        )

    processor.summarize_galaxy_metrics([meta_doc, meta_sec], [])

    assert meta_doc["risk_vector"][churn_idx] > 0.0, (
        "Documentation file's churn was silently zeroed by global normalization!"
    )
    assert meta_sec["risk_vector"][churn_idx] > 0.0, (
        "Critical-secret-leak file's churn was silently zeroed by global normalization!"
    )


# ==============================================================================
# TEST 12.5: RAW COUNTS ARE COUNTS (#2813, contract roadmap Phase 2 / D1)
# The proximity weights moved out of the recorded counts into the per-file
# tally; the score layer must reproduce the old figures from raw + tally.
# ==============================================================================
def test_signal_processor_weighted_view_is_score_neutral(processor):
    """A file scored from raw counts + the proximity tally must produce byte-identical
    risk_vector and file_impact to the same file scored from the old in-place
    weighted counts -- while hit_vector now carries the raw counts and the telemetry
    carries the tally and the weighted figures under their own key."""
    raw = {
        "branch": 6,
        "state_mutation": 3,
        "high_risk_execution": 2,
        "concurrency": 1,
        "memory_alloc": 2,
        "safety": 1,
        "func_start": 2,
    }
    tally = {
        "amplified_cascading_flux": 2,  # x3 on two of the three mutations
        "mitigated_danger": 1,  # one of the two danger hits silenced
        "amplified_race_conditions": 1,  # +5
        "mitigated_memory_allocs": 1,  # one alloc cleaned up
    }
    old_weighted = dict(raw)
    old_weighted["state_mutation"] = 3 + 2 * 2
    old_weighted["high_risk_execution"] = 2 - 1
    old_weighted["concurrency"] = 1 + 5
    old_weighted["memory_alloc"] = 2 - 1

    meta_new, sig_new = create_synthetic_star(processor, "raw_counts", 120, raw)
    meta_new["mitigation_telemetry"] = tally
    meta_old, sig_old = create_synthetic_star(processor, "raw_counts", 120, old_weighted)

    res_new = processor.calculate_risk_vector(meta_new, sig_new)
    res_old = processor.calculate_risk_vector(meta_old, sig_old)

    assert res_new["risk_vector"] == res_old["risk_vector"], "Every risk score must be unchanged by construction"
    assert res_new["file_impact"] == res_old["file_impact"], "Structural magnitude reads the weighted flux/concurrency"
    assert res_new["telemetry"]["archetype_fingerprint"] == res_old["telemetry"]["archetype_fingerprint"]

    idx = {k: processor.SIGNAL_SCHEMA.index(k) for k in ("state_mutation", "high_risk_execution", "concurrency")}
    assert res_new["hit_vector"][idx["state_mutation"]] == 3, "hit_vector carries the raw count"
    assert res_new["hit_vector"][idx["high_risk_execution"]] == 2
    assert res_new["hit_vector"][idx["concurrency"]] == 1
    assert res_old["hit_vector"][idx["state_mutation"]] == 7, "the old star really was weighted"

    tel = res_new["telemetry"]
    assert tel["mitigation_telemetry"] == tally, "the detector's tally reaches the recorders"
    assert tel["weighted_signals"] == {
        "state_mutation": 7,
        "high_risk_execution": 1,
        "concurrency": 6,
        "memory_alloc": 1,
    }, "the weighted figures the counts used to carry, under their own key"
    assert res_old["telemetry"]["weighted_signals"] == {}, "no tally, nothing weighted"


def test_signal_processor_weighted_view_tolerates_missing_or_list_tally(processor):
    """Minified / inert files never ran the correlation pass; a legacy list in the slot
    (the galaxyscope:ignore suppressions) must not break scoring either."""
    meta, sig = create_synthetic_star(processor, "no_tally", 50, {"state_mutation": 4, "branch": 2})
    res_plain = processor.calculate_risk_vector(meta, sig)

    meta["mitigation_telemetry"] = ["state_flux"]
    res_list = processor.calculate_risk_vector(meta, sig)

    assert res_plain["risk_vector"] == res_list["risk_vector"]
    assert res_plain["telemetry"]["weighted_signals"] == {}


# ==============================================================================
# TEST 13: SPATIALLY VERIFIED MEMORY EXHAUSTION (Cascading Flux)
# ==============================================================================
def test_signal_processor_memory_exhaustion_spatial(processor):
    """
    Proves that the engine properly translates spatially-amplified state mutations
    into severe State Flux risk exposures, bypassing the old probabilistic guessing.
    """
    # 1. Baseline: Normal function with safe, isolated state mutation
    meta_safe, sig_safe = create_synthetic_star(processor, "safe_flux", 100, {"state_mutation": 5})

    # 2. Memory Exhaustion: The upstream detector found a loop and multiplied the signal
    meta_bomb, sig_bomb = create_synthetic_star(
        processor,
        "oom_flux",
        100,
        {"state_mutation": 50},  # Signal was amplified upstream
    )

    res_safe = processor.calculate_risk_vector(meta_safe, sig_safe)
    res_bomb = processor.calculate_risk_vector(meta_bomb, sig_bomb)

    idx_flux = processor.RISK_SCHEMA.index("state_flux")

    safe_score = res_safe["risk_vector"][idx_flux]
    bomb_score = res_bomb["risk_vector"][idx_flux]

    assert bomb_score > safe_score, (
        "Processor failed to convert the spatially amplified signal into a higher State Flux risk!"
    )
    assert bomb_score > 60.0, "Processor failed to trigger a severe risk exposure on the OOM Bomb!"


# ==============================================================================
# TEST 14: AI TOPOLOGY & NETWORK POSTURE
# ==============================================================================
def test_signal_processor_ai_topology(processor):
    """
    Proves the AI Network Posture insights (PageRank blast radius,
    Betweenness choke-point) fire for any file that registers nonzero AI
    mass, using llm_orchestrator as the trigger signal.

    #323: this test used to exercise ai_logic_loop/ai_tools/ai_memory
    ("Autonomous Agentic Fleet (Level 4)" + "context amnesia" insight) --
    those 3 categories were removed from SIGNAL_SCHEMA entirely (they
    detect BEHAVIOR, not import identity, which a regex engine can't do;
    they had zero producers in language_standards.py and were permanently
    unreachable against real source). RAG Pipeline / Cloud API Wrapper
    classification coverage lives in
    test_signal_processor_ai_topology_rag_cloud below; this test now only
    needs to prove the network-posture insight logic itself still works
    off a signal that's actually still real.
    """
    m1, sig1 = create_synthetic_star(processor, "orchestrator", 100, {"llm_orchestrator": 10})

    tel1 = processor.calculate_risk_vector(m1, sig1)
    m1["telemetry"] = tel1["telemetry"]
    m1["hit_vector"] = tel1["hit_vector"]  # Essential for the AI sensor!

    # Inject Fake Network Posture
    m1["telemetry"]["network_metrics"] = {
        "pagerank_score": 5.0,
        "normalized_blast_radius": 2.5,
        "betweenness_score": 0.1,
        "ecosystem_role": "Core Hub",
    }

    summary = processor.summarize_galaxy_metrics([m1], [])

    topology = summary.get("ai_topology", {})
    assert topology["classification"] == "Framework-Heavy Orchestration", "Failed to classify orchestration-heavy repo!"

    insights = " ".join(topology["insights"])
    assert "catastrophically across the system" in insights, "Failed to detect high PageRank blast radius!"
    assert "Cognitive Choke Point" in insights, "Failed to detect high Betweenness!"


def test_signal_processor_ai_topology_skips_uncomputed_metrics(processor):
    """
    #3027: a None blast radius / betweenness means "not computed" (past its
    work budget, or a failed computation). The posture insights that need them are skipped --
    a placeholder 0.0 used to produce a false "Containment (Low Risk)" verdict.
    """
    m1, sig1 = create_synthetic_star(processor, "orchestrator", 100, {"llm_orchestrator": 10})
    tel1 = processor.calculate_risk_vector(m1, sig1)
    m1["telemetry"] = tel1["telemetry"]
    m1["hit_vector"] = tel1["hit_vector"]
    m1["telemetry"]["network_metrics"] = {
        "pagerank_score": None,
        "normalized_blast_radius": None,
        "betweenness_score": None,
        "ecosystem_role": "Core Hub",
    }

    insights = " ".join(processor.summarize_galaxy_metrics([m1], [])["ai_topology"]["insights"])

    assert "Structural Posture" in insights  # ecosystem_role is exact in every mode
    assert "Containment" not in insights
    assert "catastrophically" not in insights
    assert "Cognitive Choke Point" not in insights


# ==============================================================================
# TEST 17: STRUCTURAL METRICS (Graveyard & Spec Match)
# ==============================================================================
def test_signal_processor_structural_metrics(processor):
    """Ensures Graveyard and Spec Match exposures calculate correctly.

    #3111: spec alignment is now opt-in and OFF by default, so this test --
    which exercises the FORMULA, not the default -- builds its own processor
    with the vector enabled. The default-off behaviour is asserted separately
    in tests/tools_recorders/test_report_surface_3111_3114.py.
    """
    spec_processor = SignalProcessor(aperture_config={"SPEC_ALIGNMENT": True})

    # Graveyard (High dead code)
    m_grave, sig_grave = create_synthetic_star(processor, "dead_code", 100, {"dead_code": 80})

    # Spec Match (0 specs for 10 functions = 100% risk)
    m_spec, sig_spec = create_synthetic_star(spec_processor, "spec", 100, {"func_start": 10, "spec_exposure": 0})

    r_grave = processor.calculate_risk_vector(m_grave, sig_grave)
    r_spec = spec_processor.calculate_risk_vector(m_spec, sig_spec)

    idx_grave = processor.RISK_SCHEMA.index("dead_code")
    idx_spec = processor.RISK_SCHEMA.index("spec_match")

    assert r_grave["risk_vector"][idx_grave] > 50.0, "Graveyard risk failed to register!"
    assert r_spec["risk_vector"][idx_spec] == 100.0, (
        "Spec match risk failed to register maximum exposure on undocumented functions!"
    )

    # And the default really is off -- the same inputs measure nothing.
    assert (
        processor.calculate_risk_vector(*create_synthetic_star(processor, "spec", 100, {"func_start": 10}))[
            "risk_vector"
        ][idx_spec]
        == 0.0
    )


# ==============================================================================
# TEST 18: UNACKNOWLEDGED DEBT (Design Slop Amplifier)
# ==============================================================================
def test_signal_processor_design_slop(processor):
    """Proves that silent design slop (orphans/duplicates) exponentially spikes Tech Debt."""

    # 1. Clean Debt: Only explicit TODOs
    m_clean, sig_clean = create_synthetic_star(processor, "clean_debt", 100, {"planned_debt": 10})

    # 2. Sloppy Debt: Explicit TODOs + Invisible Slop
    m_slop, sig_slop = create_synthetic_star(
        processor,
        "sloppy_debt",
        100,
        {"planned_debt": 10, "unreferenced_by_name": 5, "duplicate_logic": 2},
    )

    r_clean = processor.calculate_risk_vector(m_clean, sig_clean)
    r_slop = processor.calculate_risk_vector(m_slop, sig_slop)

    idx_debt = processor.RISK_SCHEMA.index("tech_debt")

    assert r_slop["risk_vector"][idx_debt] > r_clean["risk_vector"][idx_debt], (
        "Design Slop failed to amplify Tech Debt!"
    )
    assert r_slop["risk_vector"][idx_debt] > 50.0, "Severe slop failed to trigger high exposure!"


# ==============================================================================
# TEST 19: VERIFICATION MITIGATION BALANCE (Skips & Breach Cap)
# ==============================================================================
def test_signal_processor_verification_mitigation_balance(processor):
    """Proves skipped tests neutralize assertions, and highly unverified files hit the breach cap."""

    # 1. Safe: High impact, lots of tests
    m_safe, sig_safe = create_synthetic_star(processor, "safe_logic", 100)
    m_safe["functions"] = [{"name": "func", "impact": 5000.0, "hit_vector": {"test": 2500, "test_skip": 0}}]

    # 2. Bypassed: High impact, tests neutralized by skips
    m_skip, sig_skip = create_synthetic_star(processor, "skip_logic", 100)
    m_skip["functions"] = [
        {
            "name": "func",
            "impact": 5000.0,
            "hit_vector": {"test": 2500, "test_skip": 1250},
        }
    ]

    # 3. Breached: Almost entirely unverified logic
    m_breach, sig_breach = create_synthetic_star(processor, "breach_logic", 100)
    m_breach["functions"] = [{"name": "func", "impact": 5000.0, "hit_vector": {"test": 50, "test_skip": 0}}]

    r_safe = processor.calculate_risk_vector(m_safe, sig_safe)
    r_skip = processor.calculate_risk_vector(m_skip, sig_skip)
    r_breach = processor.calculate_risk_vector(m_breach, sig_breach)

    idx_test = processor.RISK_SCHEMA.index("verification")

    # Higher score = Higher Risk Exposure (Worse Verification)
    assert r_safe["risk_vector"][idx_test] < r_skip["risk_vector"][idx_test], (
        "Test skips failed to neutralize assertions!"
    )
    assert r_breach["risk_vector"][idx_test] >= 80.0, "Overwhelmingly unverified file failed to hit the breach cap!"


# ==============================================================================
# TEST 20: GOD OBJECT ANTI-PATTERN PENALTY (Cognitive Load Gini)
# ==============================================================================
def test_signal_processor_god_object_gini(processor):
    """Proves that concentrating complexity into a single function spikes Cognitive Load."""

    # Both files have 100 LOC and 20 Branches total.

    # 1. Flat Distribution (4 functions, 5 branches each) -> Low Gini
    m_flat, sig_flat = create_synthetic_star(processor, "flat_dist", 100, {"branch": 20})
    m_flat["functions"] = [
        {"name": "f1", "branch": 5, "loc": 25},
        {"name": "f2", "branch": 5, "loc": 25},
        {"name": "f3", "branch": 5, "loc": 25},
        {"name": "f4", "branch": 5, "loc": 25},
    ]

    # 2. God Object (1 massive function, 3 empty) -> High Gini
    m_god, sig_god = create_synthetic_star(processor, "god_func", 100, {"branch": 20})
    m_god["functions"] = [
        {"name": "god", "branch": 20, "loc": 90},
        {"name": "f2", "branch": 0, "loc": 3},
        {"name": "f3", "branch": 0, "loc": 3},
        {"name": "f4", "branch": 0, "loc": 4},
    ]

    r_flat = processor.calculate_risk_vector(m_flat, sig_flat)
    r_god = processor.calculate_risk_vector(m_god, sig_god)

    idx_cog = processor.RISK_SCHEMA.index("cognitive_load")

    assert r_god["risk_vector"][idx_cog] > r_flat["risk_vector"][idx_cog], (
        "God object anti-pattern Gini index failed to amplify Cognitive Load!"
    )


# ==============================================================================
# TEST 21: CONCURRENCY MITIGATION BALANCE (Locks)
# ==============================================================================
def test_signal_processor_concurrency_mitigation_balance(processor):
    """Proves sync locks mitigate async risk."""

    # 1. High Async, No Locks
    m_async, sig_async = create_synthetic_star(processor, "pure_async", 100, {"concurrency": 20})

    # 2. High Async, Mitigated by Locks (1 lock mitigates 1.5 async hits)
    m_sync, sig_sync = create_synthetic_star(processor, "locked_async", 100, {"concurrency": 20, "sync_locks": 15})

    r_async = processor.calculate_risk_vector(m_async, sig_async)
    r_sync = processor.calculate_risk_vector(m_sync, sig_sync)

    idx_async = processor.RISK_SCHEMA.index("concurrency")

    assert r_sync["risk_vector"][idx_async] < r_async["risk_vector"][idx_async], (
        "Sync locks failed to mitigate concurrency risk!"
    )


# ==============================================================================
# TEST 22: ISOLATED NODE ADJUSTMENT (API Isolation)
# ==============================================================================
def test_signal_processor_api_isolated_node(processor):
    """Proves that APIs with no inbound network connections receive a massive risk dampener."""

    # 1. Orphaned API (Exposes 50 APIs, but 0 popularity)
    m_orphan, sig_orphan = create_synthetic_star(processor, "orphan_api", 100, {"api": 50})
    m_orphan["popularity"] = 0

    # 2. Networked API (Exposes 50 APIs, highly popular)
    m_network, sig_network = create_synthetic_star(processor, "network_api", 100, {"api": 50})
    m_network["popularity"] = 20

    r_orphan = processor.calculate_risk_vector(m_orphan, sig_orphan)
    r_network = processor.calculate_risk_vector(m_network, sig_network)

    idx_api = processor.RISK_SCHEMA.index("api_exposure")

    assert r_orphan["risk_vector"][idx_api] < (r_network["risk_vector"][idx_api] * 0.5), (
        "Isolated node adjustment failed: Orphaned APIs were not properly dampened!"
    )


# ==============================================================================
# TEST 23: STATE FLUX MITIGATION BALANCE (Immutability)
# ==============================================================================
def test_signal_processor_flux_immutability(processor):
    """Proves that immutable data declarations (freeze_hits) neutralize state flux."""

    # 1. Pure Flux (High mutation)
    m_flux, sig_flux = create_synthetic_star(processor, "high_flux", 100, {"state_mutation": 30})

    # 2. Frozen Flux (High mutation, but heavily mitigated by freeze/const/final)
    m_frozen, sig_frozen = create_synthetic_star(
        processor, "frozen_flux", 100, {"state_mutation": 30, "immutability_locks": 40}
    )

    r_flux = processor.calculate_risk_vector(m_flux, sig_flux)
    r_frozen = processor.calculate_risk_vector(m_frozen, sig_frozen)

    idx_flux = processor.RISK_SCHEMA.index("state_flux")

    assert r_frozen["risk_vector"][idx_flux] < r_flux["risk_vector"][idx_flux], (
        "Immutability (freeze_hits) failed to mitigate state flux risk!"
    )


# ==============================================================================
# TEST 24: EXTENSION DECEPTION SENSOR
# ==============================================================================
def test_signal_processor_extension_deception(processor):
    """Proves the engine flags files that claim to be inert data but contain executable logic."""
    m_dec, sig_dec = create_synthetic_star(processor, "data", 100)
    m_dec["path"] = "src/data.json"  # Claims to be JSON
    m_dec["lang_id"] = "python"  # Actually evaluated as Python!

    r_dec = processor.calculate_risk_vector(m_dec, sig_dec)

    idx_mismatch = processor.SIGNAL_SCHEMA.index("sec_extension_mismatch")
    assert r_dec["hit_vector"][idx_mismatch] == 1, "Extension Deception Sensor failed to flag the mismatch!"


# ==============================================================================
# TEST 27: CATASTROPHIC FALLBACKS & EMPTY GALAXIES
# ==============================================================================
def test_signal_processor_catastrophic_fallbacks(processor):
    """Ensures the physics engine survives catastrophic type errors and empty data sets."""
    # 1. Force a catastrophic crash early in per-file processing (before the risk
    # math), so the fallback must zero the risk vector. A str `functions` breaks
    # the function-classification loop (iterating chars, `.get` on a str). coding_loc
    # alone no longer crashes here since file archetype classification moved to
    # record_keeper.
    m_crash, sig_crash = create_synthetic_star(processor, "crash", 100)
    m_crash["coding_loc"] = "THIS_WILL_BREAK_MATH"
    m_crash["functions"] = "THIS_WILL_BREAK_MATH"

    r_crash = processor.calculate_risk_vector(m_crash, sig_crash)

    assert "error" in r_crash["telemetry"], "Engine failed to catch and log the catastrophic physics failure!"
    assert r_crash["risk_vector"] == [0.0] * len(processor.RISK_SCHEMA), (
        "Crash fallback did not safely zero out the risk vector!"
    )

    # 2. Force an empty global synthesis
    empty_summary = processor.summarize_galaxy_metrics([], [])
    assert empty_summary == {}, "Summarizer failed to safely exit on an empty repository!"


# ==============================================================================
# TEST 28: INDENTATION STYLE (Descriptive Telemetry, not a Risk -- #1147)
# ==============================================================================
def test_signal_processor_indentation_style_void(processor):
    """Proves a file with no indentation reports "Neutral / No Indentation" telemetry."""
    m_void, sig_void = create_synthetic_star(processor, "void_file", 10, {"indent_tabs": 0, "indent_spaces": 0})

    r_void = processor.calculate_risk_vector(m_void, sig_void)

    assert "tabs_vs_spaces" not in processor.RISK_SCHEMA, (
        "tabs_vs_spaces was moved out of RISK_SCHEMA (#1147) -- it isn't a risk exposure."
    )
    assert r_void["telemetry"]["indentation_style"] == "Neutral / No Indentation"


def test_signal_processor_indentation_style_camps(processor):
    """Proves pure-tabs, pure-spaces, and mixed files each get the right descriptive label."""
    m_tabs, sig_tabs = create_synthetic_star(processor, "tabs_file", 10, {"indent_tabs": 5, "indent_spaces": 0})
    m_spaces, sig_spaces = create_synthetic_star(processor, "spaces_file", 10, {"indent_tabs": 0, "indent_spaces": 5})
    m_mixed, sig_mixed = create_synthetic_star(processor, "mixed_file", 10, {"indent_tabs": 1, "indent_spaces": 3})

    r_tabs = processor.calculate_risk_vector(m_tabs, sig_tabs)
    r_spaces = processor.calculate_risk_vector(m_spaces, sig_spaces)
    r_mixed = processor.calculate_risk_vector(m_mixed, sig_mixed)

    assert r_tabs["telemetry"]["indentation_style"] == "Tabs"
    assert r_spaces["telemetry"]["indentation_style"] == "Spaces"
    assert r_mixed["telemetry"]["indentation_style"] == "Mixed (75.0% Spaces / 25.0% Tabs)"


# ==============================================================================
# TEST 31: LLM API SECRETS LEAK
# ==============================================================================
def test_signal_processor_llm_api_secrets(processor):
    """
    Proves that hardcoded secrets mixed with LLM APIs trigger a massive
    careless amplifier in _calc_secrets_risk.

    Regression test: this test previously built both fixtures but never
    called calculate_risk_vector or asserted anything on either -- a
    complete no-op that always passed regardless of whether the LLM
    amplifier (or _calc_secrets_risk at all) worked. Ruff's F841/RUF059
    would have caught the resulting unused variables, but tests/ is out
    of scope for the ruff baseline, so it went unnoticed.
    """
    # 1. Standard secret leak (Requires sec_heat_triggers to bypass the 2.0 clamp)
    m_std, sig_std = create_synthetic_star(
        processor,
        "std_leak",
        500,
        {"sec_hardcoded_secrets": 1, "globals": 1, "sec_reflection_metaprogramming": 1},
    )

    # 2. Careless LLM API secret leak (Calling APIs without using global variables)
    m_llm, sig_llm = create_synthetic_star(
        processor,
        "llm_leak",
        500,
        {"sec_hardcoded_secrets": 1, "llm_api": 5, "globals": 0, "sec_reflection_metaprogramming": 1},
    )

    r_std = processor.calculate_risk_vector(m_std, sig_std)
    r_llm = processor.calculate_risk_vector(m_llm, sig_llm)

    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")

    assert r_llm["risk_vector"][idx_sec] > r_std["risk_vector"][idx_sec], (
        "Careless LLM API secret leak (no globals) should score higher than a standard leak, "
        "via the 3x careless_amplifiers spike -- it didn't!"
    )
    assert r_std["risk_vector"][idx_sec] > 0.0, "A genuine hardcoded-secret signal should never score exactly 0."


def test_signal_processor_secrets_risk_zero_when_no_hardcoded_signal(processor):
    """base_leak == 0 must short-circuit to a flat 0.0, never entering the amplifier math."""
    meta, sig = create_synthetic_star(processor, "clean_file", 500, {"llm_api": 5, "globals": 0})
    result = processor.calculate_risk_vector(meta, sig)
    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")
    assert result["risk_vector"][idx_sec] == 0.0


def test_signal_processor_secrets_risk_clamped_without_reflection_signal(processor):
    """
    Outside paranoid mode, with zero sec_reflection_metaprogramming signal,
    careless_amplifiers is clamped to a maximum of 2.0 -- proves the clamp
    branch itself (as opposed to the LLM-amplifier test above, which
    deliberately supplies reflection signal to bypass this exact clamp).
    """
    meta, sig = create_synthetic_star(
        processor, "clamped_leak", 500, {"sec_hardcoded_secrets": 1, "globals": 1, "debug_prints": 50}
    )
    result = processor.calculate_risk_vector(meta, sig)
    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")
    # A huge debug_prints count would blow the amplifier way past 2.0 if
    # unclamped; the score should still land in a sane, non-maxed-out range.
    assert 0.0 < result["risk_vector"][idx_sec] < 100.0


def test_signal_processor_secrets_risk_paranoid_mode_skips_clamp(processor):
    """In paranoid mode, the 2.0 clamp never applies regardless of reflection signal."""
    meta, sig = create_synthetic_star(
        processor, "paranoid_leak", 500, {"sec_hardcoded_secrets": 1, "globals": 1, "debug_prints": 50}
    )
    processor.is_paranoid = True
    try:
        result = processor.calculate_risk_vector(meta, sig)
    finally:
        processor.is_paranoid = False

    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")
    assert result["risk_vector"][idx_sec] > 0.0


def test_signal_processor_secrets_risk_low_score_floors_to_zero(processor):
    """A raw score under 5.0 is explicitly floored to 0.0, not left as noisy near-zero signal."""
    # A single hardcoded-secret hit in an enormous file produces a tiny
    # density, and thus a tiny sigmoid score -- exactly the < 5.0 floor case.
    meta, sig = create_synthetic_star(processor, "diluted_leak", 50000, {"sec_hardcoded_secrets": 1})
    result = processor.calculate_risk_vector(meta, sig)
    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")
    assert result["risk_vector"][idx_sec] == 0.0, (
        "A sub-5.0 raw score should floor to exactly 0.0, not a noisy near-zero value."
    )


# ==============================================================================
# TEST 32: SAFE MINIFIED VENDOR FILE
# ==============================================================================
def test_signal_processor_safe_minified(processor):
    """Proves that minified files with zero malicious intent safely bypass the tripwire."""
    m_safe, sig_safe = create_synthetic_star(processor, "jquery_min", 100, {"branch": 50, "state_mutation": 20})
    m_safe["is_minified"] = True

    r_safe = processor.calculate_risk_vector(m_safe, sig_safe)

    assert r_safe["risk_vector"] == [0.0] * len(processor.RISK_SCHEMA), "Safe minified file failed to zero out risks!"
    assert r_safe["telemetry"]["domain_context"]["alert"] == "MINIFIED VENDOR BYPASS", "Minified bypass flag missing!"


# ==============================================================================
# TEST 34: AI TOPOLOGY (DEEP LEARNING & TRADITIONAL ML)
# ==============================================================================
def test_signal_processor_ai_topology_dl_ml(processor):
    """Ensures the AI topology summarizer correctly identifies Deep Learning and Traditional ML."""
    # Deep Learning
    m_dl, sig_dl = create_synthetic_star(processor, "pytorch_model", 100, {"dl_frameworks": 10})
    r_dl = processor.calculate_risk_vector(m_dl, sig_dl)
    m_dl.update(r_dl)

    # Traditional ML
    m_ml, sig_ml = create_synthetic_star(processor, "xgboost_model", 100, {"ml_traditional": 10})
    r_ml = processor.calculate_risk_vector(m_ml, sig_ml)
    m_ml.update(r_ml)

    # Summarize DL
    sum_dl = processor.summarize_galaxy_metrics([m_dl], [])
    assert sum_dl["ai_topology"]["classification"] == "Deep Learning Architecture", (
        "Failed to classify DL Architecture!"
    )

    # Summarize ML
    sum_ml = processor.summarize_galaxy_metrics([m_ml], [])
    assert sum_ml["ai_topology"]["classification"] == "Statistical Machine Learning", (
        "Failed to classify Traditional ML!"
    )


# ==============================================================================
# TEST 36: AI TOPOLOGY (RAG & CLOUD WRAPPERS)
# ==============================================================================
def test_signal_processor_ai_topology_rag_cloud(processor):
    """Ensures the AI topology summarizer correctly identifies RAG pipelines and Cloud wrappers."""
    # RAG Pipeline
    m_rag, sig_rag = create_synthetic_star(processor, "rag_bot", 100, {"llm_vector_store": 10, "llm_api": 5})
    r_rag = processor.calculate_risk_vector(m_rag, sig_rag)
    m_rag.update(r_rag)

    # Cloud API Wrapper
    m_cloud, sig_cloud = create_synthetic_star(processor, "cloud_bot", 100, {"llm_api": 10})
    r_cloud = processor.calculate_risk_vector(m_cloud, sig_cloud)
    m_cloud.update(r_cloud)

    # Summarize RAG
    sum_rag = processor.summarize_galaxy_metrics([m_rag], [])
    assert sum_rag["ai_topology"]["classification"] == "RAG Pipeline (Retrieval-Augmented Generation)", (
        "Failed to classify RAG Pipeline!"
    )

    # Summarize Cloud
    sum_cloud = processor.summarize_galaxy_metrics([m_cloud], [])
    assert sum_cloud["ai_topology"]["classification"] == "Cloud API Wrapper", "Failed to classify Cloud API Wrapper!"


# ==============================================================================
# TEST 37: SIGMOID OVERFLOW RESISTANCE (Extreme Density)
# ==============================================================================
def test_signal_processor_sigmoid_overflow(processor):
    """Proves the Sigmoid curve safely catches math.exp OverflowErrors on extreme densities."""
    # Create a file with mathematically impossible levels of safety to force a massive negative density
    m_safe, sig_safe = create_synthetic_star(
        processor,
        "super_shield",
        1,
        {"safety": 15000, "test": 15000, "doc": 15000, "immutability_locks": 15000},
    )

    # Create a file with mathematically impossible danger to force a massive positive density
    m_danger, sig_danger = create_synthetic_star(
        processor,
        "super_bomb",
        1,
        {"branch": 15000, "concurrency": 15000, "state_mutation": 15000, "sec_high_risk_execution": 15000},
    )

    # If these execute without crashing the test runner, the except blocks are working perfectly.
    r_safe = processor.calculate_risk_vector(m_safe, sig_safe)
    r_danger = processor.calculate_risk_vector(m_danger, sig_danger)

    idx_saf = processor.RISK_SCHEMA.index("safety_score")

    # The OverflowError should gracefully return either 0.0 or 100.0 depending on the threat trajectory
    assert r_safe["risk_vector"][idx_saf] == 0.0, "Overflow fallback failed to zero out the mathematically safe file!"
    assert r_danger["risk_vector"][idx_saf] == 100.0, (
        "Overflow fallback failed to max out the mathematically dangerous file!"
    )


# ==============================================================================
# TEST 38: STANDALONE INIT & SILO VOID
# ==============================================================================
def test_signal_processor_standalone_init_and_silo():
    """Ensures the processor initializes without a parent logger and handles 0-commit silo math."""
    from gitgalaxy.metrics.signal_processor import SignalProcessor

    # Test standalone initialization
    standalone_engine = SignalProcessor(parent_logger=None)
    assert standalone_engine is not None, "SignalProcessor failed to initialize without a parent logger!"

    # Test the silo math directly on a 0-commit developer void state
    zero_silo = standalone_engine._calculate_silo_risk({"dev_a": 0, "dev_b": 0})
    assert zero_silo == 0.0, "Silo risk failed to safely return 0.0 on a void state!"


# ==============================================================================
# TEST 39: THE LOAD-BEARER PENALTY (Verification Risk)
# ==============================================================================
def test_signal_processor_load_bearer_penalty(processor):
    """Proves that highly imported files receive a massive penalty for lacking tests."""
    # 1. Standard file with 0 tests
    m_std, sig_std = create_synthetic_star(processor, "std_untested", 100)
    m_std["functions"] = [{"name": "func", "impact": 5000.0, "hit_vector": {}}]
    m_std["popularity"] = 0

    # 2. Foundational pillar with 0 tests
    m_pillar, sig_pillar = create_synthetic_star(processor, "pillar_untested", 100)
    m_pillar["functions"] = [{"name": "func", "impact": 5000.0, "hit_vector": {}}]
    m_pillar["popularity"] = 20  # Highly imported

    r_std = processor.calculate_risk_vector(m_std, sig_std)
    r_pillar = processor.calculate_risk_vector(m_pillar, sig_pillar)

    idx_ver = processor.RISK_SCHEMA.index("verification")

    assert r_pillar["risk_vector"][idx_ver] > r_std["risk_vector"][idx_ver], (
        "Load-bearer penalty failed to amplify verification risk!"
    )


# ==============================================================================
# TEST 40: DOCUMENTATION COVERAGE RATIO (#2908 Phase 3)
# ==============================================================================
def test_signal_processor_documentation_coverage_ratio(processor):
    """The per-unit contract (docs/risk_documentation_contract.md §1) through the
    full calculate_risk_vector path: an undocumented unit exposes its weight, a
    documented one exposes nothing, and the score is their ratio -- the old
    opaque-execution/impact term is gone (impact ranks the hitlist, D1)."""
    idx_doc = processor.RISK_SCHEMA.index("documentation")

    def score(functions):
        m, sig = create_synthetic_star(processor, "units", 100, {"doc": 10})
        m["functions"] = functions
        return processor.calculate_risk_vector(m, sig)["risk_vector"][idx_doc]

    unit = {"name": "f", "loc": 50, "impact": 60.0, "hit_vector": {}}
    documented = score([{**unit, "is_public": True, "is_documented": True}])
    blind = score([{**unit, "is_public": True, "is_documented": False}])
    assert blind > documented, "An undocumented public unit must outscore a documented one!"
    assert blind == 100.0 and documented == 0.0, "One-unit files read the pure ratio (D5: no damping)"


def test_signal_processor_documentation_acceptance_pins(processor):
    """The #2908 acceptance table, pinned exactly: the rosetta a/b/c shape (3 public
    units, 0 documented) reads 100; the main shape (4 public units, `entry`
    documented) reads 75; the same file at 0 public reads the unweighted ratio;
    no units emits 0.0 (n/a is the reporting layer's inference, D6); reflection
    raises the weight of ITS unit (#2719)."""
    abc = [{"name": n, "is_public": True, "is_documented": False, "hit_vector": {}} for n in ("a", "b", "c")]
    assert processor._calc_documentation(abc) == 100.0

    main = [
        {"name": "entry", "is_public": True, "is_documented": True, "hit_vector": {}},
        *({"name": n, "is_public": True, "is_documented": False, "hit_vector": {}} for n in ("a", "b", "c")),
    ]
    assert processor._calc_documentation(main) == 75.0

    # The api-contract split surfaced on purpose: entry not in the name set -> 6/7.
    main_entry_private = [dict(u, is_public=(u["name"] != "entry")) for u in main]
    assert processor._calc_documentation(main_entry_private) == pytest.approx(100.0 * 6.0 / 7.0)

    # Phase-2 amendment: mains with units_public=0 read the unweighted ratio.
    unweighted = [dict(u, is_public=False) for u in main]
    assert processor._calc_documentation(unweighted) == 75.0

    assert processor._calc_documentation([]) == 0.0

    # The slicer's synthetic buckets are not units (#2691/#2792): a file whose
    # "functions" are all buckets is the n/a class, not 100 -- sqlite's
    # CREATE_Statement buckets put a/b/c at 100 until this filter.
    buckets = [
        {
            "name": "CREATE_Statement",
            "is_public": False,
            "is_documented": False,
            "hit_vector": {},
            "is_synthetic_slice": True,
        },
        {
            "name": "__global_context__",
            "is_public": False,
            "is_documented": False,
            "hit_vector": {},
            "is_synthetic_slice": True,
        },
    ]
    assert processor._calc_documentation(buckets) == 0.0
    assert processor._calc_documentation(buckets + abc) == 100.0

    reflective = [
        {"name": "static", "is_public": False, "is_documented": False, "hit_vector": {}},
        {
            "name": "dynamic",
            "is_public": False,
            "is_documented": False,
            "hit_vector": {"reflection_metaprogramming": 3},
        },
    ]
    # weights 1 and 4, both exposed -> still 100; document the dynamic one -> 1/5.
    assert processor._calc_documentation(reflective) == 100.0
    reflective[1]["is_documented"] = True
    assert processor._calc_documentation(reflective) == 100.0 * (1.0 / 5.0)


# ==============================================================================
# TEST 41: TECH DEBT SLOP MULTIPLIER
# ==============================================================================
def test_signal_processor_tech_debt_slop(processor):
    """Proves that unacknowledged slop multiplies the severity of fragile debt."""
    # 1. Just fragile debt
    m_debt, sig_debt = create_synthetic_star(processor, "fragile_only", 500, {"fragile_debt": 2})

    # 2. Fragile debt PLUS orphans/duplicates
    m_slop, sig_slop = create_synthetic_star(
        processor,
        "fragile_slop",
        500,
        {"fragile_debt": 2, "unreferenced_by_name": 2, "duplicate_logic": 1},
    )

    r_debt = processor.calculate_risk_vector(m_debt, sig_debt)
    r_slop = processor.calculate_risk_vector(m_slop, sig_slop)

    idx_debt = processor.RISK_SCHEMA.index("tech_debt")

    # The multiplier is 1.5x, so the slop score should be significantly higher
    assert r_slop["risk_vector"][idx_debt] > (r_debt["risk_vector"][idx_debt] * 1.2), (
        "Tech debt slop failed to multiply fragile debt severity!"
    )


# ==============================================================================
# TEST 42: REPORT GENERATOR MALFORMED DICTIONARY FALLBACK
# ==============================================================================
def test_signal_processor_report_fallback(processor):
    """Ensures the report generator safely handles missing keys and malformed telemetry."""
    malformed_files = [
        {"name": "missing_risk_vector", "path": "src/bad1.py"},  # No risk_vector key
        {
            "name": "string_risk_vector",
            "path": "src/bad2.py",
            "risk_vector": "INVALID",
        },  # Wrong type
        {
            "name": "short_risk_vector",
            "path": "src/bad3.py",
            "risk_vector": [0.0],
        },  # Index out of bounds
    ]

    # Should execute smoothly without raising a KeyError, TypeError, or IndexError
    report = processor.generate_forensic_report(malformed_files)

    assert "exposures" in report, "Report generator completely failed on malformed data!"

    # The lowest/highest rankings should have safely defaulted the values to 0.0
    for exposure_key, ranking in report["exposures"].items():
        assert ranking["highest"][0]["value"] == 0.0, f"Fallback failed to zero out invalid data for {exposure_key}!"


# ==============================================================================
# TEST 43: CRITICAL LEAK BYPASS (Absolute Maximum Risk)
# ==============================================================================
def test_signal_processor_critical_leak_bypass(processor):
    """Proves that critical leaks bypass standard physics and max out secrets risk."""
    m_leak, sig_leak = create_synthetic_star(processor, "aws_key", 10, {})
    m_leak["path"] = "config/production.pem"
    m_leak["metadata"] = {"reason": "CRITICAL LEAK DETECTED"}  # #374: real key is "reason", not "aperture_reason"

    r_leak = processor.calculate_risk_vector(m_leak, sig_leak)

    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")

    assert r_leak["file_impact"] == 150.0, "Critical leak failed to trigger the 150.0 mass spike!"
    assert r_leak["risk_vector"][idx_sec] == 100.0, "Critical leak failed to max out secrets risk!"
    assert r_leak["telemetry"]["domain_context"]["alert"] == "CRITICAL LEAK BYPASS", (
        "Bypass alert missing from telemetry!"
    )


def test_signal_processor_critical_leak_via_reason_text_alone(processor):
    """
    Regression test for #374 (#325's own pre-documented instance #3): isolates
    the THIRD is_critical_leak path -- "CRITICAL LEAK" in the reason text --
    from the other two (extension/exact-filename match), which the test above
    already covers via a .pem path. This file has neither a secrets extension
    nor an exact secrets filename, so it can ONLY trigger via
    ghost_meta.get("reason", ""), proving that mechanism works in isolation
    now that it reads the key aperture.py actually writes.
    """
    m_leak, sig_leak = create_synthetic_star(processor, "config_loader", 10, {})
    m_leak["metadata"] = {"reason": "CRITICAL LEAK (Exposed Secret: 'config_loader.py')"}

    r_leak = processor.calculate_risk_vector(m_leak, sig_leak)

    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")
    assert r_leak["risk_vector"][idx_sec] == 100.0, "The reason-text-only critical leak path failed to fire!"


# ==============================================================================
# TEST 44: THE DARKNESS RATIO (100% Unparsable)
# ==============================================================================
def test_signal_processor_darkness_ratio(processor):
    """Ensures global synthesis survives a completely broken repository (0 parsed, 10 unparsable)."""
    unparsable_files = [{"name": f"broken_{i}.py"} for i in range(10)]

    # 0 parsed files, 10 unparsable files
    summary = processor.summarize_galaxy_metrics([], unparsable_files)

    assert summary["summary"]["total_files"] == 10, "Failed to count unparsable files in total!"
    assert summary["summary"]["verified_files"] == 0, "Verified files should be 0!"
    assert summary["summary"]["Percent_Visible"] == 0.0, "Darkness ratio failed to calculate 0% visibility!"
    assert summary["unparsable_files"]["ambig_file_count"] == 10, "Failed to aggregate unparsable file count!"


# ==============================================================================
# TEST 47: TIER 3 LANGUAGE FALLBACK
# ==============================================================================
def test_signal_processor_unknown_language_gets_no_language_term(processor):
    """#2718: an unknown language is scored with NO language-level correction (irc 0,
    ot 1.0, fidelity 1.0) -- the opposite of the old fall-through to the harshest tier.
    haskell, which used to land there for not being in a hand list, resolves to its
    own strictness row (all four columns True) and the same zero irc."""
    for lang in ("haskell", "no-such-language"):
        m, sig = create_synthetic_star(processor, "esoteric", 100, {"branch": 20})
        m["lang_id"] = lang
        assert processor.calculate_risk_vector(m, sig) is not None
        irc, ot, fid = processor._language_constants(lang)
        assert (irc, ot) == (0, 1.0), lang
        if lang == "no-such-language":
            # nothing measured -> nothing scaled; haskell, by contrast, carries the
            # fidelity the corpus measured for its own rules (safety over-fires: 0.67)
            assert all(v == 1.0 for v in fid.values()), lang


# ==============================================================================
# TEST 48: EXTERNAL TEST COVERAGE MAPPING
# ==============================================================================
def test_signal_processor_external_test_coverage(processor):
    """Proves that external test files dampen unverified impact via the coverage map."""

    # 1. Completely unverified function
    m_blind, sig_blind = create_synthetic_star(processor, "blind", 100)
    m_blind["functions"] = [{"name": "target_func", "impact": 50.0}]

    # 2. Verified function (has a test targeting it)
    m_verified, sig_verified = create_synthetic_star(processor, "verified", 100)
    m_verified["functions"] = [{"name": "target_func", "impact": 50.0}]
    m_verified["test_coverage_map"] = {
        "target_func": [
            {
                "impact": 25.0,
                "target_count": 1,
                "test_hits": 5,
                "test_skip_hits": 0,
                "decorators": 0,
            }
        ]
    }

    # 3. Parameterized Verified function (gets a 2.0x multiplier via decorators)
    m_param, sig_param = create_synthetic_star(processor, "param_verified", 100)
    m_param["functions"] = [{"name": "target_func", "impact": 50.0}]
    m_param["test_coverage_map"] = {
        "target_func": [
            {
                "impact": 25.0,
                "target_count": 1,
                "test_hits": 5,
                "test_skip_hits": 0,
                "decorators": 1,
            }
        ]
    }

    r_blind = processor.calculate_risk_vector(m_blind, sig_blind)
    r_verified = processor.calculate_risk_vector(m_verified, sig_verified)
    r_param = processor.calculate_risk_vector(m_param, sig_param)

    idx_ver = processor.RISK_SCHEMA.index("verification")

    assert r_verified["risk_vector"][idx_ver] < r_blind["risk_vector"][idx_ver], (
        "External test coverage failed to dampen verification risk!"
    )
    assert r_param["risk_vector"][idx_ver] < r_verified["risk_vector"][idx_ver], (
        "Parameterization multiplier failed to increase defensive mass!"
    )


# ==============================================================================
# TEST 49: CONCURRENCY THRESHOLD SCALING (REGRESSION TEST)
# ==============================================================================
def test_signal_processor_concurrency_threshold_scaling(processor):
    """
    Proves the (* 100.0) mathematical scalar correctly converts low-ratio concurrency
    signals into valid density percentages.
    """
    # 5 threads in a 100-line file = 0.04 ratio (with the 25-line concurrency padding).
    # Scaled to percentage = 4.0%. Threshold is 2.5%.
    # This MUST trigger a high risk exposure.
    meta, sig = create_synthetic_star(processor, "thread_router", 100, {"concurrency": 5})

    res = processor.calculate_risk_vector(meta, sig)
    idx_async = processor.RISK_SCHEMA.index("concurrency")

    score = res["risk_vector"][idx_async]

    assert score > 50.0, f"Concurrency scaling bug regression! Expected a high risk score, but got {score}%."


# ==============================================================================
# TEST 50: INLINE SUPPRESSION MATH OVERRIDE (galaxyscope:ignore)
# ==============================================================================
def test_signal_processor_inline_suppressions(processor):
    """
    DEVIOUS EDGE CASES:
    1. Proves a mathematically catastrophic risk can be hard-overridden to 0.0.
    2. Proves the engine doesn't crash on "Phantom Risks" (schema drift / typos).
    3. Proves un-suppressed risks remain dangerously high.
    """
    # Create an apocalyptic file that triggers maximum risk everywhere
    meta, sig = create_synthetic_star(
        processor,
        "suppression_test",
        100,
        {
            "branch": 5000,
            "state_mutation": 5000,
            "concurrency": 5000,
            "high_risk_execution": 5000,
            "sec_high_risk_execution": 5000,
            "sec_io": 5000,
            "fragile_debt": 5000,
        },
    )

    # Inject the developer suppressions
    meta["mitigations"] = [
        "tech_debt",  # Valid override
        "made_up_phantom_123",  # Schema drift / fake risk
    ]

    res = processor.calculate_risk_vector(meta, sig)

    idx_debt = processor.RISK_SCHEMA.index("tech_debt")
    idx_cog = processor.RISK_SCHEMA.index("cognitive_load")

    # 1. Assert the targeted risk was zeroed out
    assert res["risk_vector"][idx_debt] == 0.0, "Inline suppression failed to zero out Tech Debt!"

    # 2. Assert un-suppressed risks are still 100% lethal
    assert res["risk_vector"][idx_cog] > 80.0, "Inline suppression accidentally wiped out Cognitive Load!"

    # 3. Assert the metadata passed cleanly to the telemetry for the UI
    assert "made_up_phantom_123" in res["telemetry"]["mitigation_telemetry"], (
        "Phantom risk was not passed to the UI telemetry payload!"
    )


# ==============================================================================
# TEST 51: SARIF EXACT LOC INJECTION
# ==============================================================================
def test_sarif_exact_loc_injection():
    """
    COVERAGE TARGET: sarif_recorder.py (_build_location).
    Ensures the SARIF exporter consumes the threat_locations array and outputs
    the exact line number instead of falling back to line 1.
    """
    import json
    import os
    import tempfile

    from gitgalaxy.recorders.sarif_recorder import SarifRecorder

    recorder = SarifRecorder()

    mock_file = {
        "path": "src/vulnerable.py",
        "start_line": 1,
        "telemetry": {
            "threat_snippets": {"hardcoded_secrets": ["password='123'"]},
            "threat_locations": {
                "sec_hardcoded_secrets": [42]  # The exact line number
            },
        },
    }

    fd, temp_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)

    try:
        recorder.generate_report([mock_file], {}, {}, temp_path)

        with open(temp_path) as f:
            sarif_output = json.load(f)

        results = sarif_output["runs"][0]["results"]
        assert len(results) == 1, "Failed to generate SARIF result!"

        # Extract the exact line number from the payload
        exact_line = results[0]["locations"][0]["physicalLocation"]["region"]["startLine"]
        assert exact_line == 42, f"SARIF fell back to start_line! Expected 42, got {exact_line}."

    finally:
        os.remove(temp_path)


# ==============================================================================
# TEST: STATIC LITERATURE OVERRIDE -- hit_vector DERIVED FROM raw_signals (#691)
# ==============================================================================
def test_signal_processor_doc_bypass_hit_vector_reflects_raw_signals(processor):
    """
    Regression test for #691: the STATIC LITERATURE OVERRIDE previously
    hardcoded hit_vector to all-zero for every doc_languages entry
    (markdown/plaintext/rst/text), completely independent of raw_signals --
    so even after detector.py started correctly populating markdown's
    lit_* signatures in `equations`, they never survived into hit_vector
    (and therefore never appeared in the "Structural Signatures" report
    section, which reads hit_vector, not equations, directly).

    risk_vector must stay untouched by this fix -- documentation still
    correctly reports 0% logic risk. Only hit_vector changes.
    """
    lit_headers_idx = processor.SIGNAL_SCHEMA.index("lit_headers")
    lit_links_idx = processor.SIGNAL_SCHEMA.index("lit_links")
    documentation_idx = processor.RISK_SCHEMA.index("documentation")

    meta_doc, sig_doc = create_synthetic_star(processor, "readme", 500, {"lit_headers": 7, "lit_links": 3})
    meta_doc["lang_id"] = "markdown"

    result = processor.calculate_risk_vector(meta_doc, sig_doc)

    assert result["hit_vector"][lit_headers_idx] == 7, (
        "markdown's lit_headers count should survive into hit_vector, not get hardcoded to 0"
    )
    assert result["hit_vector"][lit_links_idx] == 3, (
        "markdown's lit_links count should survive into hit_vector, not get hardcoded to 0"
    )
    # Logic-risk bypass must still hold -- this fix only touches hit_vector.
    assert result["risk_vector"][documentation_idx] == 0.0, (
        "Documentation risk bypass regressed -- markdown must still report 0% logic risk!"
    )


def test_signal_processor_doc_bypass_empty_signals_still_all_zero(processor):
    """
    Companion to the above: a doc_languages file with no real signals (e.g.
    plaintext, which defines no rules at all in language_standards.py, so
    raw_signals is always empty for it in practice) must still produce an
    all-zero hit_vector -- proves the fix is a strict generalization of the
    old hardcoded-zero behavior, not a change that invents non-zero hits
    out of nothing.
    """
    meta_doc, sig_doc = create_synthetic_star(processor, "notes", 100, {})
    meta_doc["lang_id"] = "plaintext"

    result = processor.calculate_risk_vector(meta_doc, sig_doc)
    assert not any(result["hit_vector"]), "empty raw_signals should still yield an all-zero hit_vector"


# ==============================================================================
# TEST: ECOSYSTEM CONTEXT MISMATCH (#1053 -- Architectural Boundary Violations)
# ==============================================================================
def test_signal_processor_ecosystem_mismatch_penalizes_safety(processor):
    """
    Proves a systems-language file (C) embedded in a web-ecosystem folder scores a
    higher Error/Safety risk than the identical file sitting in its native ecosystem --
    the ECOSYSTEM_MISMATCH_WEIGHTS "systems_in_web" memory penalty, wired into
    _calc_safety via folder_dominant_lang metadata (#1053, previously dead code).
    """
    danger_signals = {"high_risk_execution": 20}

    native_meta, native_sig = create_synthetic_star(processor, "native_c", 50, danger_signals)
    native_meta["lang_id"] = "c"
    native_meta["metadata"] = {"folder_dominant_lang": "c"}

    alien_meta, alien_sig = create_synthetic_star(processor, "alien_c", 50, danger_signals)
    alien_meta["lang_id"] = "c"
    alien_meta["metadata"] = {"folder_dominant_lang": "javascript"}  # C hiding in a JS folder

    native_res = processor.calculate_risk_vector(native_meta, native_sig)
    alien_res = processor.calculate_risk_vector(alien_meta, alien_sig)

    idx_safety = processor.RISK_SCHEMA.index("safety_score")
    native_score = native_res["risk_vector"][idx_safety]
    alien_score = alien_res["risk_vector"][idx_safety]

    assert alien_score > native_score, (
        "Ecosystem-mismatched file (C in a JS folder) should score a higher Error/Safety "
        f"risk than the same file native to its folder! native={native_score} alien={alien_score}"
    )


def test_signal_processor_ecosystem_native_match_is_neutral(processor):
    """
    Proves a file whose language matches its folder's dominant ecosystem scores
    identically to a file with no folder metadata at all -- NATIVE_WEIGHTS baselines
    are deliberately NOT applied on a native match (#1053 chose mismatch-only
    penalties over re-scoring every file in the corpus), so this must stay a no-op.
    """
    danger_signals = {"high_risk_execution": 20}

    no_metadata_meta, no_metadata_sig = create_synthetic_star(processor, "no_meta_c", 50, danger_signals)
    no_metadata_meta["lang_id"] = "c"

    native_meta, native_sig = create_synthetic_star(processor, "native_c2", 50, danger_signals)
    native_meta["lang_id"] = "c"
    native_meta["metadata"] = {"folder_dominant_lang": "c"}

    no_meta_res = processor.calculate_risk_vector(no_metadata_meta, no_metadata_sig)
    native_res = processor.calculate_risk_vector(native_meta, native_sig)

    idx_safety = processor.RISK_SCHEMA.index("safety_score")
    assert no_meta_res["risk_vector"][idx_safety] == native_res["risk_vector"][idx_safety], (
        "A native ecosystem match should score identically to having no folder context at all!"
    )


# ==============================================================================
# K-MEANS ARCHETYPE CLASSIFICATION (#1157 / #1158)
# ==============================================================================
# The pre-trained archetype models (function: 62-dim, file: 115-dim,
# per-language: 74-dim) carry no feature-name metadata and no training script
# lives in this repo, while the live feature vectors are 5-dim (function) and
# 83-dim (file). They have never matched, and the old distance loops silently
# truncated to the shorter sequence -- producing confidently-wrong labels.
# These tests pin the loud-failure guard: a mismatch must yield "Unclassified"
# (plus one warning per vector/centroid length pair), never a truncated label.


def test_classify_archetype_rejects_dimension_mismatch(processor, caplog):
    """A live vector and centroid of different lengths must not be compared."""
    result = processor._classify_archetype([0.5, 0.5], {"cluster_0": [1.0, 2.0, 3.0]})

    assert result == ("Unclassified", 0.0, {}), (
        "Dimension mismatch must fall back to Unclassified instead of truncating"
    )
    assert any("Archetype dimension mismatch" in r.message for r in caplog.records), (
        "The mismatch should be logged loudly"
    )


def test_classify_archetype_matching_dims_classifies_normally(processor):
    """Matching dimensions keep the nearest-centroid behavior intact."""
    centroids = {
        "cluster_near": [0.0, 0.0],
        "cluster_far": [10.0, 10.0],
    }
    best, drift, fingerprint = processor._classify_archetype([1.0, 1.0], centroids)

    assert best == "cluster_near"
    assert drift == round(2**0.5, 3)
    assert set(fingerprint) == {"cluster_near", "cluster_far"}


def _five_geometry_model(archetypes, names):
    """A minimal new-contract function model over the 5 geometry features only
    (no DNA densities, so hit_vector is irrelevant). Used to exercise the
    classifier without pinning to the full 38-D shipped model."""
    return {
        "FEATURE_NAMES": ["log_loc", "log_complexity", "log_args", "keyword_density", "func_internal_density"],
        "FEATURE_WEIGHTS": [1.0, 1.0, 1.0, 1.0, 1.0],
        "SCALER_MEDIANS": [0.0, 0.0, 0.0, 0.0, 0.0],
        "SCALER_IQRS": [1.0, 1.0, 1.0, 1.0, 1.0],
        "CAP_VALUES": {},
        "DNA_SOURCES": {},
        "cluster_names": names,
        "ARCHETYPES_K2": archetypes,
    }


def test_function_archetype_unclassified_when_model_dims_mismatch(processor, monkeypatch):
    """
    A model whose centroids don't match the built feature-vector length must
    leave every function "Unclassified" rather than emit a truncated label
    (the length guard in signal_processor's nearest-centroid loop).
    """
    # FEATURE_NAMES declares 5 features but centroids are length 3 -> all skipped.
    bad_model = _five_geometry_model({"0: A": [0.0, 0.0, 0.0], "1: B": [9.0, 9.0, 9.0]}, ["A", "B"])
    monkeypatch.setattr("gitgalaxy.metrics.signal_processor.analysis_lens.GENERAL_FUNCTION_INFERENCE_MODEL", bad_model)
    functions = [{"name": "hot_path", "loc": 30, "branch": 25, "args": 4, "keyword_density": 0.15, "hit_vector": {}}]
    meta, sig = create_synthetic_star(processor, "mismatch", 50, functions=functions)
    processor.calculate_risk_vector(meta, sig)

    assert functions[0]["archetype"] == "Unclassified"


def test_function_archetype_classified_when_model_matches_live_dims(processor, monkeypatch):
    """
    With a model whose centroids match the built vector length, the function is
    classified to the nearest centroid's plain cluster name (regression guard
    for the 38-D rosetta classifier). A loc=30/branch=25 function sits near the
    "Dense Logic" centroid, not the zero "Tiny Stub" one.
    """
    good_model = _five_geometry_model(
        {"0: Tiny Stub": [0.0, 0.0, 0.0, 0.0, 0.0], "1: Dense Logic": [3.4, 3.3, 1.6, 0.15, 0.83]},
        ["Tiny Stub", "Dense Logic"],
    )
    monkeypatch.setattr("gitgalaxy.metrics.signal_processor.analysis_lens.GENERAL_FUNCTION_INFERENCE_MODEL", good_model)
    functions = [{"name": "mutator", "loc": 30, "branch": 25, "args": 4, "keyword_density": 0.15, "hit_vector": {}}]
    meta, sig = create_synthetic_star(processor, "match", 50, functions=functions)
    processor.calculate_risk_vector(meta, sig)

    assert functions[0]["archetype"] == "Dense Logic"


def test_file_archetype_deferred_to_record_keeper(processor):
    """File-level archetype classification moved out of signal_processor: it now
    happens in record_keeper post-assembly, from the fully-computed file metrics +
    the function->file composition rollup, against the self-describing brain
    (FEATURE_NAMES-ordered, so a dimension mismatch is structurally impossible).
    signal_processor emits a placeholder that record_keeper overwrites."""
    meta, sig = create_synthetic_star(processor, "file_defer", 50, {"branch": 20})
    res = processor.calculate_risk_vector(meta, sig)
    assert res["telemetry"]["archetype"] == "Unclassified"


def test_record_keeper_classifies_file_archetype_from_self_describing_brain(monkeypatch):
    """record_keeper._classify_file_archetype builds the vector in FEATURE_NAMES
    order from the file's metrics (telemetry + engineered) and per-LOC signal
    densities (via DNA_SOURCES), RobustScales, applies FEATURE_WEIGHTS, and takes
    the nearest centroid -- the new home of file archetype classification."""
    from gitgalaxy.recorders import record_keeper as rk_mod
    from gitgalaxy.recorders.record_keeper import RecordKeeper

    fake = {
        "FEATURE_NAMES": ["func_z_max", "log_density_struct_branch"],
        "FEATURE_WEIGHTS": [1.0, 1.0],
        "CAP_VALUES": {},
        "DNA_SOURCES": {"log_density_struct_branch": "branch"},  # column stem -> signal key
        "SCALER_MEDIANS": [0.0, 0.0],
        "SCALER_IQRS": [1.0, 1.0],
        "cluster_names": ["file_cluster_0", "file_cluster_1"],
        "ARCHETYPES_K2": {"file_cluster_0": [50.0, 10.0], "file_cluster_1": [0.0, 0.0]},
    }
    monkeypatch.setattr(rk_mod, "GENERAL_FILE_INFERENCE_MODEL", fake)
    rk = RecordKeeper()
    rk._prep_file_brain()
    base_ctx = {
        "coding_loc": 100.0,
        "func_z_max": 0.0,
        "func_z_mean": 0.0,
        "func_z_median": 0.0,
        "pct_z_above_5": 0.0,
        "pct_z_above_15": 0.0,
        "micro": {},
        "precalc": {},
    }
    hv_zero = [0] * len(rk.SIGNAL_SCHEMA)
    # A quiet, branch-free file lands on the all-zero centroid.
    assert rk._classify_file_archetype(base_ctx, hv_zero) == "file_cluster_1"
    # A branch-heavy, high-outlier file lands on the far centroid; the density
    # feature is reconstructed from the `branch` signal via DNA_SOURCES.
    hv_hot = list(hv_zero)
    hv_hot[rk.SIGNAL_SCHEMA.index("branch")] = 100
    hot_ctx = dict(base_ctx, func_z_max=50.0)
    assert rk._classify_file_archetype(hot_ctx, hv_hot) == "file_cluster_0"


# ==============================================================================
# gitgalaxy#2994: MEASUREMENT TIERS -- TIER 1/3 (FAMILIES & RELATIONS)
# ==============================================================================
def test_signal_processor_surface_families_are_raw_sums(processor):
    """Tier 1: a file's per-family value is the RAW SUM of its member signal
    counts. `guards` = safety + immutability_locks + encapsulation;
    `danger` = safety_bypasses + high_risk_execution + inline_asm +
    panics_and_aborts (see analysis_lens.SURFACE_FAMILIES)."""
    meta, sig = create_synthetic_star(
        processor,
        "families_sum",
        200,
        {
            "safety": 4,
            "immutability_locks": 2,
            "encapsulation": 1,
            "safety_bypasses": 3,
            "high_risk_execution": 1,
        },
    )
    res = processor.calculate_risk_vector(meta, sig)
    families = res["telemetry"]["surface_families"]

    assert families["guards"] == 4 + 2 + 1
    assert families["danger"] == 3 + 1
    # A family with no fired members sums to a true 0, not absent/None.
    assert families["crypto"] == 0


def test_signal_processor_surface_families_covers_every_declared_family(processor):
    """Every key in SURFACE_FAMILIES must appear in telemetry["surface_families"]
    for every file, even when every member is 0 -- consumers (record_keeper,
    the LLM brief) read this dict by family name unconditionally."""
    meta, sig = create_synthetic_star(processor, "empty_families", 50)
    res = processor.calculate_risk_vector(meta, sig)
    assert set(res["telemetry"]["surface_families"].keys()) == set(processor.SURFACE_FAMILIES.keys())
    assert all(v == 0 for v in res["telemetry"]["surface_families"].values())


def test_signal_processor_surface_relations_formulas(processor):
    """Tier 3: guard_balance_ratio = guards / (danger + 1); alloc_cleanup_pairing
    = cleanup / (memory + 1). The +1 denominators mean a danger-free /
    memory-free file never divides by zero."""
    meta, sig = create_synthetic_star(
        processor,
        "relations",
        200,
        {
            "safety": 6,  # guards = 6
            "safety_bypasses": 1,  # danger = 1
            "cleanup": 5,  # cleanup = 5
            "pointers": 1,  # memory = 1
        },
    )
    res = processor.calculate_risk_vector(meta, sig)
    relations = res["telemetry"]["surface_relations"]

    assert relations["guard_balance_ratio"] == round(6 / (1 + 1), 4)
    assert relations["alloc_cleanup_pairing"] == round(5 / (1 + 1), 4)


def test_signal_processor_surface_relations_plus_one_denominator_on_zero(processor):
    """A file with zero danger/memory signals must not raise ZeroDivisionError
    -- the +1 denominator is the whole point of the formula."""
    meta, sig = create_synthetic_star(processor, "no_danger_no_memory", 50, {"safety": 3, "cleanup": 2})
    res = processor.calculate_risk_vector(meta, sig)
    relations = res["telemetry"]["surface_relations"]

    assert relations["guard_balance_ratio"] == round(3 / (0 + 1), 4)
    assert relations["alloc_cleanup_pairing"] == round(2 / (0 + 1), 4)


def test_signal_processor_surface_families_are_raw_truth_despite_suppression(processor):
    """The suppression-interplay contract (gitgalaxy#2994): families sum
    raw_signals, NOT the mitigation-suppressed exposure_vector. A file whose
    legacy risk_safety_score is zeroed by an inline `galaxyscope:ignore`
    must still show a nonzero `guards` family total -- the family is "raw
    truth by construction," independent of what the legacy sigmoid displays."""
    meta, sig = create_synthetic_star(
        processor,
        "suppressed_but_raw",
        100,
        {"safety": 8, "immutability_locks": 2},
    )
    meta["mitigations"] = ["safety_score"]  # suppresses risk_safety_score (legacy "guard_balance")

    res = processor.calculate_risk_vector(meta, sig)

    idx_safety = processor.RISK_SCHEMA.index("safety_score")
    assert res["risk_vector"][idx_safety] == 0.0, "legacy risk_safety_score must be suppressed to 0.0"
    assert res["telemetry"]["surface_families"]["guards"] == 8 + 2, (
        "the guards family sum must survive the legacy vector's suppression -- it reads raw_signals, "
        "not the suppressed exposure_vector"
    )


# ==============================================================================
# gitgalaxy#2994: MEASUREMENT TIERS -- TIER 2 (SNAPSHOT PERCENTILES)
# ==============================================================================
def _star_with_families(processor, name, **raw_signals):
    meta, sig = create_synthetic_star(processor, name, 100, raw_signals)
    res = processor.calculate_risk_vector(meta, sig)
    meta["telemetry"] = res["telemetry"]
    meta["risk_vector"] = res["risk_vector"]
    meta["file_impact"] = res["file_impact"]
    return meta


def test_signal_processor_percentiles_hazen_average_rank(processor):
    """Hazen plotting position: pct = (avg_rank - 0.5) / N * 100. Four files
    with strictly increasing `safety` counts (0, 0, 5, 10) rank as
    [25.0, 25.0, 62.5, 87.5] -- the two zeros tie and share the mean rank."""
    files = [
        _star_with_families(processor, "f0a", safety=0),
        _star_with_families(processor, "f0b", safety=0),
        _star_with_families(processor, "f5", safety=5),
        _star_with_families(processor, "f10", safety=10),
    ]
    processor.summarize_galaxy_metrics(files, [])

    pcts = [f["telemetry"]["surface_percentiles"]["fam"]["guards"] for f in files]
    assert pcts == [25.0, 25.0, 62.5, 87.5]


def test_signal_processor_percentiles_all_zero_series_reads_zero(processor):
    """An all-zero series (no file in the snapshot has this surface at all)
    must read 0.0 for every file -- NOT the 50.0 a naive average-rank tie
    computation would give a tied field of zeroes. Absent signal must not
    read as median."""
    files = [
        _star_with_families(processor, "a", safety=3),
        _star_with_families(processor, "b", safety=7),
        _star_with_families(processor, "c", safety=1),
    ]
    processor.summarize_galaxy_metrics(files, [])

    # None of these files fired any `crypto` family member.
    assert all(f["telemetry"]["surface_percentiles"]["fam"]["crypto"] == 0.0 for f in files)


def test_signal_processor_percentiles_single_file_snapshot_reads_fifty(processor):
    """N=1: a series the file actually HAS reads 50.0 (nothing to rank
    against => true middle); a series it measures zero on reads 0.0 -- the
    all-zero rule takes precedence at every N, including N=1. An absent
    surface must never read as a misleading mid-band 50."""
    files = [_star_with_families(processor, "solo", safety=9)]
    processor.summarize_galaxy_metrics(files, [])

    percentiles = files[0]["telemetry"]["surface_percentiles"]
    # guards family fired (safety=9) -> the honest "true middle" at N=1.
    assert percentiles["fam"]["guards"] == 50.0
    # crypto family entirely absent -> 0.0 even at N=1.
    assert percentiles["fam"]["crypto"] == 0.0
    # legacy-vector series behave identically: this fixture's risk_vector
    # carries cognitive_load == 0, so the all-zero rule applies there too.
    assert percentiles["vec"]["cognitive_load"] == 0.0


def test_signal_processor_percentiles_written_for_every_family_and_vector(processor):
    """telemetry["surface_percentiles"] must carry exactly the 22 families
    (under "fam") and the 13 RISK_SCHEMA slugs (under "vec")."""
    files = [
        _star_with_families(processor, "a", safety=3),
        _star_with_families(processor, "b", safety=1),
    ]
    processor.summarize_galaxy_metrics(files, [])

    percentiles = files[0]["telemetry"]["surface_percentiles"]
    assert set(percentiles["fam"].keys()) == set(processor.SURFACE_FAMILIES.keys())
    assert set(percentiles["vec"].keys()) == set(processor.RISK_SCHEMA)


def test_signal_processor_percentiles_rank_off_post_normalization_churn(processor):
    """Ordering regression guard (gitgalaxy#2994): _compute_snapshot_percentiles
    must run AFTER _normalize_temporal_metrics, because Pass 2 rewrites
    risk_vector[churn_idx] in place from a raw frequency into a log1p-
    normalized 0-100 score. Two files with wildly different raw churn
    frequencies must rank by their NORMALIZED churn (both scores in the
    0-100 range, ordered by relative frequency), not by the pre-normalization
    raw seismic-frequency numbers -- which would still rank the same way by
    coincidence for a monotonic transform, so this pins the actual values
    seen, not just the order, to catch a reordering regression."""
    churn_idx = processor.RISK_SCHEMA.index("churn")

    hot = {
        "is_git_tracked": True,
        "mtime": 100,
        "repo_min_time": 0,
        "repo_max_time": 110,
        "commit_count": 1000,
    }
    cold = {
        "is_git_tracked": True,
        "mtime": 100,
        "repo_min_time": 0,
        "repo_max_time": 110,
        "commit_count": 1,
    }

    meta_hot, sig_hot = create_synthetic_star(processor, "hot", 100)
    meta_hot["temporal_telemetry"] = hot
    meta_cold, sig_cold = create_synthetic_star(processor, "cold", 100)
    meta_cold["temporal_telemetry"] = cold

    for meta, sig in ((meta_hot, sig_hot), (meta_cold, sig_cold)):
        res = processor.calculate_risk_vector(meta, sig)
        meta["telemetry"] = res["telemetry"]
        meta["risk_vector"] = res["risk_vector"]
        meta["file_impact"] = res["file_impact"]

    # Before summarize_galaxy_metrics runs Pass 2, churn is still the 0.0
    # placeholder calculate_risk_vector left in exposure_vector["churn"].
    assert meta_hot["risk_vector"][churn_idx] == 0.0
    assert meta_cold["risk_vector"][churn_idx] == 0.0

    processor.summarize_galaxy_metrics([meta_hot, meta_cold], [])

    # Pass 2 must have already rewritten both risk_vector[churn_idx] values
    # (proving normalization ran) before the percentile pass ranked them.
    assert meta_hot["risk_vector"][churn_idx] > meta_cold["risk_vector"][churn_idx] > 0.0

    # The hotter file must rank at the top of the churn percentile series.
    hot_pct = meta_hot["telemetry"]["surface_percentiles"]["vec"]["churn"]
    cold_pct = meta_cold["telemetry"]["surface_percentiles"]["vec"]["churn"]
    assert hot_pct == 75.0  # 2 files, hot ranks 2nd -> (2-0.5)/2*100
    assert cold_pct == 25.0  # cold ranks 1st -> (1-0.5)/2*100


def test_signal_processor_percentiles_empty_galaxy_survives(processor):
    """Zero files must not crash _compute_snapshot_percentiles (mirrors the
    existing empty-state guard on _normalize_temporal_metrics)."""
    summary = processor.summarize_galaxy_metrics([], [])
    assert summary == {}
