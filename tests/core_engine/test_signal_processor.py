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
    meta["lang_id"] = "rust"  # tier1 (irc=0) -- tier2/3 languages carry a nonzero
    # irc floor that keeps total_density above 0 even with no raw signals, so this
    # carve-out can only ever fire for tier1 languages. See _get_tier().
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


def test_signal_processor_small_file_floor_still_applies(processor):
    """
    Proves the small-file 5.0 floor is untouched for files under 15 LOC that
    DO have some signal -- only the provably-empty <=2 LOC case should get
    the true-zero carve-out.
    """
    meta, sig = create_synthetic_star(processor, "small_but_real", 10, {"branch": 3})
    res = processor.calculate_risk_vector(meta, sig)

    idx_cog = processor.RISK_SCHEMA.index("cognitive_load")
    assert res["risk_vector"][idx_cog] == 5.0, "Small file with real signal should still hit the 5.0 floor!"


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
    assert "cumulative_risk" in forensics, "Forensic report missing cumulative risk!"
    assert "highest" in forensics["cumulative_risk"], "Forensic report missing highest risk array!"


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


# ==============================================================================
# TEST 17: STRUCTURAL METRICS (Graveyard & Spec Match)
# ==============================================================================
def test_signal_processor_structural_metrics(processor):
    """Ensures Graveyard and Spec Match exposures calculate correctly."""

    # Graveyard (High dead code)
    m_grave, sig_grave = create_synthetic_star(processor, "dead_code", 100, {"dead_code": 80})

    # Spec Match (0 specs for 10 functions = 100% risk)
    m_spec, sig_spec = create_synthetic_star(processor, "spec", 100, {"func_start": 10, "spec_exposure": 0})

    r_grave = processor.calculate_risk_vector(m_grave, sig_grave)
    r_spec = processor.calculate_risk_vector(m_spec, sig_spec)

    idx_grave = processor.RISK_SCHEMA.index("dead_code")
    idx_spec = processor.RISK_SCHEMA.index("spec_match")

    assert r_grave["risk_vector"][idx_grave] > 50.0, "Graveyard risk failed to register!"
    assert r_spec["risk_vector"][idx_spec] == 100.0, (
        "Spec match risk failed to register maximum exposure on undocumented functions!"
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
        {"planned_debt": 10, "orphaned_logic": 5, "duplicate_logic": 2},
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
    # 1. Force a catastrophic math crash (string instead of int)
    m_crash, sig_crash = create_synthetic_star(processor, "crash", 100)
    m_crash["coding_loc"] = "THIS_WILL_BREAK_MATH"

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
# TEST 40: OPAQUE EXECUTION RISK (Documentation Risk)
# ==============================================================================
def test_signal_processor_opaque_execution_risk(processor):
    """Proves that heavy-impact functions lacking docstrings spike documentation risk."""
    # 1. High-impact function WITH a docstring
    m_doc, sig_doc = create_synthetic_star(processor, "documented_heavy", 100, {"doc": 10})
    m_doc["functions"] = [{"name": "heavy_func", "loc": 50, "impact": 60.0, "docstring": True}]

    # 2. High-impact function WITHOUT a docstring
    m_blind, sig_blind = create_synthetic_star(processor, "blind_heavy", 100, {"doc": 10})
    m_blind["functions"] = [{"name": "heavy_func", "loc": 50, "impact": 60.0, "docstring": False}]

    r_doc = processor.calculate_risk_vector(m_doc, sig_doc)
    r_blind = processor.calculate_risk_vector(m_blind, sig_blind)

    idx_doc = processor.RISK_SCHEMA.index("documentation")

    assert r_blind["risk_vector"][idx_doc] > r_doc["risk_vector"][idx_doc], (
        "Opaque execution risk failed to penalize undocumented heavy functions!"
    )


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
        {"fragile_debt": 2, "orphaned_logic": 2, "duplicate_logic": 1},
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
def test_signal_processor_tier_3_language(processor):
    """Ensures esoteric/unstructured languages trigger Tier 3 physics modifiers."""
    m_t3, sig_t3 = create_synthetic_star(processor, "esoteric", 100, {"branch": 20})
    # "haskell" is not in the Tier 1 or Tier 2 explicit sets
    m_t3["lang_id"] = "haskell"

    r_t3 = processor.calculate_risk_vector(m_t3, sig_t3)

    # If it didn't crash, the _get_tier fallback successfully returned "tier3" and pulled the correct physics vars
    assert r_t3 is not None, "Tier 3 language fallback crashed the physics engine!"


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
    from gitgalaxy.recorders.sarif_recorder import SarifRecorder
    import json
    import tempfile
    import os

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

        with open(temp_path, "r") as f:
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


def test_function_archetype_unclassified_when_model_dims_mismatch(processor, caplog):
    """
    The shipped GENERAL_FUNCTION_INFERENCE_MODEL is 62-dim while the live
    per-function vector is 5-dim (#1157): classification must fail loudly and
    leave every function "Unclassified" instead of a truncated label.
    """
    functions = [
        {
            "name": "hot_path",
            "loc": 30,
            "branch": 25,
            "args": 4,
            "keyword_density": 0.15,
            "control_flow_ratio": 0.9,
            "cf_ratio": 0.9,
        }
    ]
    meta, sig = create_synthetic_star(processor, "mismatch", 50, functions=functions)
    processor.calculate_risk_vector(meta, sig)

    assert functions[0]["archetype"] == "Unclassified"
    assert any("Archetype dimension mismatch" in r.message for r in caplog.records), (
        "The 5-vs-62 mismatch should be logged loudly"
    )


def test_function_archetype_classified_when_model_matches_live_dims(processor, monkeypatch):
    """
    With a model that actually matches the 5-dim live vector, the shared
    classifier should still classify the function (regression guard for the
    #1157 refactor that routes function classification through
    _classify_archetype). The shipped model keys are "fxn_cluster_N", which
    the name-mapping code passes through verbatim (only space-numbered keys
    like "Cluster 0" map onto the cluster_names list).
    """
    fake_model = {
        "SCALER_MEDIANS": [0.0, 0.0, 0.0, 0.0, 0.0],
        "SCALER_IQRS": [1.0, 1.0, 1.0, 1.0, 1.0],
        "ARCHETYPES_K2": {
            "fxn_cluster_0": [0.0, 0.0, 0.0, 0.0, 0.0],
            "fxn_cluster_1": [10.0, 10.0, 10.0, 10.0, 10.0],
        },
        "cluster_names": ["Utility/Helper", "State Mutator"],
    }
    monkeypatch.setattr("gitgalaxy.metrics.signal_processor.analysis_lens.GENERAL_FUNCTION_INFERENCE_MODEL", fake_model)

    functions = [
        {
            "name": "mutator",
            "loc": 30,
            "branch": 25,
            "args": 4,
            "keyword_density": 0.15,
            "control_flow_ratio": 0.9,
            "cf_ratio": 0.9,
        }
    ]
    meta, sig = create_synthetic_star(processor, "match", 50, functions=functions)
    processor.calculate_risk_vector(meta, sig)

    assert functions[0]["archetype"] == "fxn_cluster_1"


def test_file_archetype_unclassified_when_model_dims_mismatch(processor, caplog):
    """
    The shipped GENERAL_FILE_INFERENCE_MODEL is 115-dim while the live
    raw_vector is 83-dim (#1158): every executable file must become
    "Unclassified" rather than being labeled from a truncated comparison.
    """
    meta, sig = create_synthetic_star(processor, "file_mismatch", 50, {"branch": 20})
    res = processor.calculate_risk_vector(meta, sig)

    assert res["telemetry"]["archetype"] == "Unclassified"
    assert any("Archetype dimension mismatch" in r.message for r in caplog.records), (
        "The 83-vs-115 mismatch should be logged loudly"
    )


def test_file_archetype_classified_when_model_matches_live_dims(monkeypatch):
    """
    With an 83-dim model matching the live raw_vector, file-level classification
    still labels files through _classify_archetype (regression guard for #1158's
    loud-failure guard not over-correcting into always-Unclassified).
    """
    from gitgalaxy.metrics.signal_processor import SignalProcessor

    n_dims = len(SignalProcessor.SIGNAL_SCHEMA) - 19 + 7  # filtered signals + 7 engineered
    fake_model = {
        "SCALER_MEDIANS": [0.0] * n_dims,
        "SCALER_IQRS": [1.0] * n_dims,
        "ARCHETYPES_K2": {
            "file_cluster_0": [100.0] * n_dims,
            "file_cluster_1": [0.0] * n_dims,
        },
    }
    monkeypatch.setattr("gitgalaxy.metrics.signal_processor.analysis_lens.GENERAL_FILE_INFERENCE_MODEL", fake_model)
    processor = SignalProcessor()

    meta, sig = create_synthetic_star(processor, "file_match", 50, {"branch": 20})
    res = processor.calculate_risk_vector(meta, sig)

    assert res["telemetry"]["archetype"] == "file_cluster_1"
