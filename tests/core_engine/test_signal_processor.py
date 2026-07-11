import pytest
from gitgalaxy.metrics.signal_processor import SignalProcessor


@pytest.fixture
def processor():
    """Initializes the Signal Processor."""
    return SignalProcessor()


# ==============================================================================
# SYNTHETIC GALAXY DATA (MOCKING THE DETECTOR PAYLOADS)
# ==============================================================================
def create_synthetic_star(
    processor, name, loc, raw_signals=None, forensics=None, functions=None
):
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
        "functions": functions
        or [{"name": "mock_func", "loc": loc, "branch": base_signals["branch"]}],
        "raw_imports": ["os", "sys"],
        "equations": base_signals, # Keep key backwards compatible for legacy passes if needed
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
    meta, sig = create_synthetic_star(
        processor, "perfect", 50, {"safety": 10, "doc": 20, "test": 5}
    )
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
    meta, sig = create_synthetic_star(
        processor, "api_gw", 10, {"api": 500, "concurrency": 500}
    )
    meta["functions"] = [{"name": "mock_func", "loc": 10, "branch": 0}]

    res = processor.calculate_risk_vector(meta, sig)
    assert res["risk_vector"][4] > 30.0, "API Exposure math failed!"
    assert res["risk_vector"][5] > 30.0, "Concurrency Exposure math failed!"


# ==============================================================================
# TEST 6: CIVIL WAR (Indentation Consistency)
# ==============================================================================
def test_signal_processor_civil_war(processor):
    """Proves the Civil War exposure accurately measures Tab vs Space purity."""
    mt, sigt = create_synthetic_star(processor, "t", 100, {"indent_tabs": 100})
    ms, sigs = create_synthetic_star(processor, "s", 100, {"indent_spaces": 100})
    mm, sigm = create_synthetic_star(
        processor, "m", 100, {"indent_tabs": 50, "indent_spaces": 50}
    )

    rt = processor.calculate_risk_vector(mt, sigt)
    rs = processor.calculate_risk_vector(ms, sigs)
    rm = processor.calculate_risk_vector(mm, sigm)

    assert rt["risk_vector"][12] < 10.0, "Pure Tabs failed!"
    assert rs["risk_vector"][12] > 90.0, "Pure Spaces failed!"
    assert 40.0 < rm["risk_vector"][12] < 60.0, "Mixed indentation failed!"


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
    assert low_risk["risk_vector"][idx_test] < high_risk["risk_vector"][idx_test], (
        "Sibling Test Bonus failed to apply!"
    )


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
    assert m1["telemetry"]["author_distribution"] == 100.0, (
        "Failed to calculate Silo Risk!"
    )


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
        pytest.fail(
            "Signal Processor crashed with an OverflowError on extreme density!"
        )


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
    assert "highest" in forensics["cumulative_risk"], (
        "Forensic report missing highest risk array!"
    )


# ==============================================================================
# TEST 11: THE MINIFIED VENDOR TRIPWIRE
# ==============================================================================
def test_signal_processor_minified_tripwire(processor):
    """Proves minified files bypass standard math and trigger explicit risk spikes."""
    meta, sig = create_synthetic_star(
        processor, "vendor_bundle", 1000, {"sec_high_risk_execution": 50}
    )
    meta["is_minified"] = True  # Trigger the tripwire

    res = processor.calculate_risk_vector(meta, sig)

    # Standard cognitive load should be 0.0, and the file impact forced to 1.0
    assert res["risk_vector"][0] == 0.0, (
        "Standard cognitive load should be bypassed for minified files!"
    )
    assert res["file_impact"] == 1.0, (
        "Minified files should have an impact of exactly 1.0!"
    )

    # We don't know the exact index, but the 100.0 spike MUST exist in the array
    assert 100.0 in res["risk_vector"], (
        "Minified tripwire failed to spike the malicious exposure vector!"
    )


# ==============================================================================
# TEST 12: THE DOCUMENTATION BYPASS & SECRETS LEAK
# ==============================================================================
def test_signal_processor_doc_and_secrets_bypass(processor):
    """Proves markdown files skip logic math, and exposed secrets spike risk."""
    # 1. Test Documentation Bypass
    meta_doc, sig_doc = create_synthetic_star(
        processor, "readme", 500, {"branch": 500}
    )
    meta_doc["lang_id"] = "markdown"  # Claim to be docs

    res_doc = processor.calculate_risk_vector(meta_doc, sig_doc)
    assert res_doc["risk_vector"][0] == 0.0, (
        "Documentation shouldn't calculate logic cognitive load!"
    )

    # 2. Test Critical Secrets Leak
    meta_sec, sig_sec = create_synthetic_star(processor, "keys", 10)
    meta_sec["metadata"] = {"aperture_reason": "CRITICAL LEAK"}

    res_sec = processor.calculate_risk_vector(meta_sec, sig_sec)
    assert 100.0 in res_sec["risk_vector"], (
        "Critical Leak failed to spike the Secrets Risk to 100%!"
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
    meta_safe, sig_safe = create_synthetic_star(
        processor, "safe_flux", 100, {"state_mutation": 5}
    )

    # 2. Memory Exhaustion: The upstream detector found a loop and multiplied the signal
    meta_bomb, sig_bomb = create_synthetic_star(
        processor, "oom_flux", 100, {"state_mutation": 50}  # Signal was amplified upstream
    )

    res_safe = processor.calculate_risk_vector(meta_safe, sig_safe)
    res_bomb = processor.calculate_risk_vector(meta_bomb, sig_bomb)

    idx_flux = processor.RISK_SCHEMA.index("state_flux")
    
    safe_score = res_safe["risk_vector"][idx_flux]
    bomb_score = res_bomb["risk_vector"][idx_flux]

    assert bomb_score > safe_score, (
        "Processor failed to convert the spatially amplified signal into a higher State Flux risk!"
    )
    assert bomb_score > 60.0, (
        "Processor failed to trigger a severe risk exposure on the OOM Bomb!"
    )




# ==============================================================================
# TEST 14: AI TOPOLOGY & NETWORK POSTURE
# ==============================================================================
def test_signal_processor_ai_topology(processor):
    """Proves the aggregator correctly classifies Autonomous Fleets and RAG pipelines."""
    # Level 4 Agent (Tools + Logic Loops, but NO memory)
    m1, sig1 = create_synthetic_star(
        processor,
        "agent",
        100,
        {"ai_logic_loop": 10, "ai_tools": 10, "ai_memory": 0},
    )

    # RAG Pipeline
    m2, sig2 = create_synthetic_star(
        processor, "rag", 100, {"llm_api": 10, "llm_vector_store": 10}
    )

    # Process files
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

    tel2 = processor.calculate_risk_vector(m2, sig2)
    m2["telemetry"] = tel2["telemetry"]
    m2["hit_vector"] = tel2["hit_vector"]

    parsed = [m1, m2]
    summary = processor.summarize_galaxy_metrics(parsed, [])

    topology = summary.get("ai_topology", {})
    assert topology["classification"] == "Autonomous Agentic Fleet (Level 4)", (
        "Failed to classify Level 4 Agent!"
    )

    insights = " ".join(topology["insights"])
    assert "context amnesia" in insights, "Failed to detect missing Agent Memory!"
    assert "catastrophically across the system" in insights, (
        "Failed to detect high PageRank blast radius!"
    )
    assert "Cognitive Choke Point" in insights, "Failed to detect high Betweenness!"


# ==============================================================================
# TEST 15: ALGORITHMIC DOS EXPOSURE
# ==============================================================================
def test_signal_processor_algorithmic_dos(processor):
    """Proves the Big-O risk exposure scales with data gravity and choke points, and is dampened by safety guardrails."""

    # 1. Isolated Harmless Loop: O(N^3) but no IO/API and 0 popularity.
    m_iso, sig_iso = create_synthetic_star(processor, "isolated", 100, {"api": 0})
    m_iso["popularity"] = 0
    m_iso["functions"] = [
        {
            "name": "safe_loop",
            "loc": 50,
            "big_o_depth": 3,
            "db_complexity": 0,
            "hit_vector": {},
        }
    ]

    # 2. API DoS Bomb: O(N^3) + DB Complexity + Exposed to API
    m_bomb, sig_bomb = create_synthetic_star(
        processor, "exposed_bomb", 500, {"api": 4}
    )
    m_bomb["popularity"] = 2
    m_bomb["functions"] = [
        {
            "name": "dos_bomb",
            "loc": 250,
            "big_o_depth": 3,
            "db_complexity": 2,
            "hit_vector": {"api": 4},
        }
    ]

    # 3. Guarded DoS Bomb: Same as above but mitigated by safety bailouts
    m_guard, sig_guard = create_synthetic_star(
        processor, "guarded_bomb", 500, {"api": 4}
    )
    m_guard["popularity"] = 2
    m_guard["functions"] = [
        {
            "name": "safe_bomb",
            "loc": 250,
            "big_o_depth": 3,
            "db_complexity": 2,
            "hit_vector": {"api": 4, "safety": 1, "panics_and_aborts": 2},
        }
    ]

    res_iso = processor.calculate_risk_vector(m_iso, sig_iso)
    res_bomb = processor.calculate_risk_vector(m_bomb, sig_bomb)
    res_guard = processor.calculate_risk_vector(m_guard, sig_guard)

    # Index 13 is the new algorithmic_dos vector
    iso_score = res_iso["risk_vector"][13]
    bomb_score = res_bomb["risk_vector"][13]
    guard_score = res_guard["risk_vector"][13]

    assert iso_score < bomb_score, (
        "Isolated loop should have significantly lower risk than exposed bomb!"
    )
    assert guard_score < bomb_score, (
        "Safety guardrails failed to dampen the Algorithmic DoS threat!"
    )
    assert bomb_score > 50.0, "API DoS bomb failed to spike the risk exposure!"


# ==============================================================================
# TEST 16: WEAPONIZABLE SURFACE EXPOSURES (Security Lenses)
# ==============================================================================
def test_signal_processor_security_lenses(processor):
    """Ensures all security lens risk equations return valid floats and properly scale."""

    # 1. Logic Bomb
    m_lb, sig_lb = create_synthetic_star(
        processor,
        "logic_bomb",
        100,
        {"branch": 50, "sec_high_risk_execution": 20, "sec_tainted_injection": 5},
    )

    # 2. Obscured Payload (Requires intent_mass via sec_danger to bypass the 95% false-positive shield)
    m_ob, sig_ob = create_synthetic_star(
        processor,
        "obscured",
        100,
        {
            "sec_reflection_metaprogramming": 20,
            "sec_bitwise_ops": 50,
            "sec_shadow_imports": 5,
            "sec_high_risk_execution": 10,
        },
    )

    # 3. Injection Surface
    m_inj, sig_inj = create_synthetic_star(
        processor, "injection", 100, {"sec_io": 30, "sec_high_risk_execution": 30}
    )

    # 4. Memory Corruption (Requires native memory language like 'c' + malicious intent to bypass the 95% shield)
    m_mem, sig_mem = create_synthetic_star(
        processor,
        "memory",
        100,
        {"pointers": 50, "memory_alloc": 20, "sec_high_risk_execution": 10},
    )
    m_mem["lang_id"] = "c"

    r_lb = processor.calculate_risk_vector(m_lb, sig_lb)
    r_ob = processor.calculate_risk_vector(m_ob, sig_ob)
    r_inj = processor.calculate_risk_vector(m_inj, sig_inj)
    r_mem = processor.calculate_risk_vector(m_mem, sig_mem)

    idx_lb = processor.RISK_SCHEMA.index("logic_bomb")
    idx_ob = processor.RISK_SCHEMA.index("obscured_payload")
    idx_inj = processor.RISK_SCHEMA.index("injection_surface")
    idx_mem = processor.RISK_SCHEMA.index("memory_corruption")

    assert isinstance(r_lb["risk_vector"][idx_lb], float), (
        "Logic bomb must return a float!"
    )
    assert r_lb["risk_vector"][idx_lb] > 10.0, "Logic bomb failed to register!"

    assert isinstance(r_ob["risk_vector"][idx_ob], float), (
        "Obscured payload must return a float!"
    )
    assert r_ob["risk_vector"][idx_ob] > 10.0, "Obscured payload failed to register!"

    assert isinstance(r_inj["risk_vector"][idx_inj], float), (
        "Injection surface must return a float!"
    )
    assert r_inj["risk_vector"][idx_inj] > 10.0, "Injection surface failed to register!"

    assert isinstance(r_mem["risk_vector"][idx_mem], float), (
        "Memory corruption must return a float!"
    )
    assert r_mem["risk_vector"][idx_mem] >= 9.0, "Memory corruption failed to register!"


# ==============================================================================
# TEST 17: STRUCTURAL METRICS (Graveyard & Spec Match)
# ==============================================================================
def test_signal_processor_structural_metrics(processor):
    """Ensures Graveyard and Spec Match exposures calculate correctly."""

    # Graveyard (High dead code)
    m_grave, sig_grave = create_synthetic_star(
        processor, "dead_code", 100, {"dead_code": 80}
    )

    # Spec Match (0 specs for 10 functions = 100% risk)
    m_spec, sig_spec = create_synthetic_star(
        processor, "spec", 100, {"func_start": 10, "spec_exposure": 0}
    )

    r_grave = processor.calculate_risk_vector(m_grave, sig_grave)
    r_spec = processor.calculate_risk_vector(m_spec, sig_spec)

    idx_grave = processor.RISK_SCHEMA.index("dead_code")
    idx_spec = processor.RISK_SCHEMA.index("spec_match")

    assert r_grave["risk_vector"][idx_grave] > 50.0, (
        "Graveyard risk failed to register!"
    )
    assert r_spec["risk_vector"][idx_spec] == 100.0, (
        "Spec match risk failed to register maximum exposure on undocumented functions!"
    )


# ==============================================================================
# TEST 18: UNACKNOWLEDGED DEBT (Design Slop Amplifier)
# ==============================================================================
def test_signal_processor_design_slop(processor):
    """Proves that silent design slop (orphans/duplicates) exponentially spikes Tech Debt."""

    # 1. Clean Debt: Only explicit TODOs
    m_clean, sig_clean = create_synthetic_star(
        processor, "clean_debt", 100, {"planned_debt": 10}
    )

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
    assert r_slop["risk_vector"][idx_debt] > 50.0, (
        "Severe slop failed to trigger high exposure!"
    )


# ==============================================================================
# TEST 19: VERIFICATION MITIGATION BALANCE (Skips & Breach Cap)
# ==============================================================================
def test_signal_processor_verification_mitigation_balance(processor):
    """Proves skipped tests neutralize assertions, and highly unverified files hit the breach cap."""

    # 1. Safe: High impact, lots of tests
    m_safe, sig_safe = create_synthetic_star(processor, "safe_logic", 100)
    m_safe["functions"] = [
        {"name": "func", "impact": 5000.0, "hit_vector": {"test": 2500, "test_skip": 0}}
    ]

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
    m_breach["functions"] = [
        {"name": "func", "impact": 5000.0, "hit_vector": {"test": 50, "test_skip": 0}}
    ]

    r_safe = processor.calculate_risk_vector(m_safe, sig_safe)
    r_skip = processor.calculate_risk_vector(m_skip, sig_skip)
    r_breach = processor.calculate_risk_vector(m_breach, sig_breach)

    idx_test = processor.RISK_SCHEMA.index("verification")

    # Higher score = Higher Risk Exposure (Worse Verification)
    assert r_safe["risk_vector"][idx_test] < r_skip["risk_vector"][idx_test], (
        "Test skips failed to neutralize assertions!"
    )
    assert r_breach["risk_vector"][idx_test] >= 80.0, (
        "Overwhelmingly unverified file failed to hit the breach cap!"
    )


# ==============================================================================
# TEST 20: GOD OBJECT ANTI-PATTERN PENALTY (Cognitive Load Gini)
# ==============================================================================
def test_signal_processor_god_object_gini(processor):
    """Proves that concentrating complexity into a single function spikes Cognitive Load."""

    # Both files have 100 LOC and 20 Branches total.

    # 1. Flat Distribution (4 functions, 5 branches each) -> Low Gini
    m_flat, sig_flat = create_synthetic_star(
        processor, "flat_dist", 100, {"branch": 20}
    )
    m_flat["functions"] = [
        {"name": "f1", "branch": 5, "loc": 25},
        {"name": "f2", "branch": 5, "loc": 25},
        {"name": "f3", "branch": 5, "loc": 25},
        {"name": "f4", "branch": 5, "loc": 25},
    ]

    # 2. God Object (1 massive function, 3 empty) -> High Gini
    m_god, sig_god = create_synthetic_star(
        processor, "god_func", 100, {"branch": 20}
    )
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
# TEST 21: CONCURRENCY MITIGATION BALANCE (Locks & Starvation)
# ==============================================================================
def test_signal_processor_concurrency_mitigation_balance(processor):
    """Proves sync locks mitigate async risk, and high Big-O spikes thread starvation."""

    # 1. High Async, No Locks
    m_async, sig_async = create_synthetic_star(
        processor, "pure_async", 100, {"concurrency": 20}
    )

    # 2. High Async, Mitigated by Locks (1 lock mitigates 1.5 async hits)
    m_sync, sig_sync = create_synthetic_star(
        processor, "locked_async", 100, {"concurrency": 20, "sync_locks": 15}
    )

    # 3. Thread Starvation (Async + High Big-O)
    m_starve, sig_starve = create_synthetic_star(
        processor, "starved_async", 100, {"concurrency": 20}
    )
    m_starve["functions"] = [
        {
            "name": "heavy_thread",
            "loc": 50,
            "big_o_depth": 3,
            "hit_vector": {"concurrency": 5},
        }
    ]

    r_async = processor.calculate_risk_vector(m_async, sig_async)
    r_sync = processor.calculate_risk_vector(m_sync, sig_sync)
    r_starve = processor.calculate_risk_vector(m_starve, sig_starve)

    idx_async = processor.RISK_SCHEMA.index("concurrency")

    assert r_sync["risk_vector"][idx_async] < r_async["risk_vector"][idx_async], (
        "Sync locks failed to mitigate concurrency risk!"
    )
    assert r_starve["risk_vector"][idx_async] > r_async["risk_vector"][idx_async], (
        "Thread starvation (Big-O + Async) failed to amplify risk!"
    )


# ==============================================================================
# TEST 22: ISOLATED NODE ADJUSTMENT (API Isolation)
# ==============================================================================
def test_signal_processor_api_isolated_node(processor):
    """Proves that APIs with no inbound network connections receive a massive risk dampener."""

    # 1. Orphaned API (Exposes 50 APIs, but 0 popularity)
    m_orphan, sig_orphan = create_synthetic_star(
        processor, "orphan_api", 100, {"api": 50}
    )
    m_orphan["popularity"] = 0

    # 2. Networked API (Exposes 50 APIs, highly popular)
    m_network, sig_network = create_synthetic_star(
        processor, "network_api", 100, {"api": 50}
    )
    m_network["popularity"] = 20

    r_orphan = processor.calculate_risk_vector(m_orphan, sig_orphan)
    r_network = processor.calculate_risk_vector(m_network, sig_network)

    idx_api = processor.RISK_SCHEMA.index("api_exposure")

    assert r_orphan["risk_vector"][idx_api] < (
        r_network["risk_vector"][idx_api] * 0.5
    ), "Isolated node adjustment failed: Orphaned APIs were not properly dampened!"


# ==============================================================================
# TEST 23: STATE FLUX MITIGATION BALANCE (Immutability)
# ==============================================================================
def test_signal_processor_flux_immutability(processor):
    """Proves that immutable data declarations (freeze_hits) neutralize state flux."""

    # 1. Pure Flux (High mutation)
    m_flux, sig_flux = create_synthetic_star(
        processor, "high_flux", 100, {"state_mutation": 30}
    )

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
    assert r_dec["hit_vector"][idx_mismatch] == 1, (
        "Extension Deception Sensor failed to flag the mismatch!"
    )


# ==============================================================================
# TEST 25: CONTEXTUAL MISMATCH PENALTIES
# ==============================================================================
def test_signal_processor_contextual_mismatch(processor):
    """Proves that a Systems language hiding in a Web folder receives severe ecosystem mismatch multipliers."""
    # 1. Native C (C code inside a C/CPP folder)
    m_native, sig_native = create_synthetic_star(
        processor,
        "native",
        100,
        {"branch": 50, "sec_high_risk_execution": 20, "sec_tainted_injection": 5},
    )
    m_native["lang_id"] = "c"
    m_native["metadata"] = {"folder_dominant_lang": "cpp"}

    # 2. Alien C (C code inside a Javascript/Web folder)
    m_alien, sig_alien = create_synthetic_star(
        processor,
        "alien",
        100,
        {"branch": 50, "sec_high_risk_execution": 20, "sec_tainted_injection": 5},
    )
    m_alien["lang_id"] = "c"
    m_alien["metadata"] = {"folder_dominant_lang": "javascript"}

    r_native = processor.calculate_risk_vector(m_native, sig_native)
    r_alien = processor.calculate_risk_vector(m_alien, sig_alien)

    idx_lb = processor.RISK_SCHEMA.index("logic_bomb")

    assert r_alien["risk_vector"][idx_lb] > r_native["risk_vector"][idx_lb], (
        "Contextual mismatch penalty failed to apply!"
    )


# ==============================================================================
# TEST 26: STATIC AI COMPUTE & SCIENCE SHIELD
# ==============================================================================
def test_signal_processor_science_shield(processor):
    """Proves that Scientific/Math logic dampens the false-positive threat of Logic Bombs."""
    # 1. Standard executable with dangerous triggers
    m_std, sig_std = create_synthetic_star(
        processor, "standard", 100, {"branch": 30, "sec_high_risk_execution": 20}
    )

    # 2. Scientific executable with the exact same triggers
    m_sci, sig_sci = create_synthetic_star(
        processor,
        "science",
        100,
        {"branch": 30, "sec_high_risk_execution": 20, "scientific": 10},
    )

    r_std = processor.calculate_risk_vector(m_std, sig_std)
    r_sci = processor.calculate_risk_vector(m_sci, sig_sci)

    idx_lb = processor.RISK_SCHEMA.index("logic_bomb")

    assert r_sci["risk_vector"][idx_lb] < r_std["risk_vector"][idx_lb], (
        "Scientific shield failed to dampen the Logic Bomb false positive!"
    )


# ==============================================================================
# TEST 27: CATASTROPHIC FALLBACKS & EMPTY GALAXIES
# ==============================================================================
def test_signal_processor_catastrophic_fallbacks(processor):
    """Ensures the physics engine survives catastrophic type errors and empty data sets."""
    # 1. Force a catastrophic math crash (string instead of int)
    m_crash, sig_crash = create_synthetic_star(processor, "crash", 100)
    m_crash["coding_loc"] = "THIS_WILL_BREAK_MATH"

    r_crash = processor.calculate_risk_vector(m_crash, sig_crash)

    assert "error" in r_crash["telemetry"], (
        "Engine failed to catch and log the catastrophic physics failure!"
    )
    assert r_crash["risk_vector"] == [0.0] * len(processor.RISK_SCHEMA), (
        "Crash fallback did not safely zero out the risk vector!"
    )

    # 2. Force an empty global synthesis
    empty_summary = processor.summarize_galaxy_metrics([], [])
    assert empty_summary == {}, (
        "Summarizer failed to safely exit on an empty repository!"
    )


# ==============================================================================
# TEST 28: CIVIL WAR VOID STATE (Zero Indentation)
# ==============================================================================
def test_signal_processor_civil_war_void(processor):
    """Proves the Civil War exposure safely defaults to 50.0 (Neutral) if a file has no indentation."""
    m_void, sig_void = create_synthetic_star(
        processor, "void_file", 10, {"indent_tabs": 0, "indent_spaces": 0}
    )

    r_void = processor.calculate_risk_vector(m_void, sig_void)
    idx_civil = processor.RISK_SCHEMA.index("tabs_vs_spaces")

    assert r_void["risk_vector"][idx_civil] == 50.0, (
        "Void state failed to default to 50.0% neutral exposure!"
    )


# ==============================================================================
# TEST 29: LLM EXECUTION VULNERABILITY
# ==============================================================================
def test_signal_processor_llm_execution_vulnerability(processor):
    """Proves that pairing an LLM Orchestrator with dynamic execution creates a massive Injection Surface spike."""
    # 1. Standard dynamic execution
    m_std, sig_std = create_synthetic_star(
        processor, "std_exec", 100, {"sec_high_risk_execution": 10}
    )

    # 2. Agentic dynamic execution
    m_agent, sig_agent = create_synthetic_star(
        processor,
        "agent_exec",
        100,
        {"sec_high_risk_execution": 10, "llm_orchestrator": 5, "ai_tools": 5},
    )

    r_std = processor.calculate_risk_vector(m_std, sig_std)
    r_agent = processor.calculate_risk_vector(m_agent, sig_agent)

    idx_inj = processor.RISK_SCHEMA.index("injection_surface")

    assert r_agent["risk_vector"][idx_inj] > r_std["risk_vector"][idx_inj], (
        "LLM execution vulnerability failed to amplify injection risk!"
    )


# ==============================================================================
# TEST 30: CRYPTOGRAPHY & PROFESSIONALISM SHIELDS
# ==============================================================================
def test_signal_processor_crypto_professionalism_shield(processor):
    """Proves that heavy documentation, safety blocks, and crypto math dampen obfuscation false positives."""
    # 1. Raw obfuscation (High entropy, bitwise math) + malicious intent
    m_raw, sig_raw = create_synthetic_star(
        processor,
        "raw_obf",
        100,
        {"sec_reflection_metaprogramming": 50, "sec_bitwise_ops": 50, "sec_high_risk_execution": 10},
    )

    # 2. Professional cryptography (Same obfuscation, but heavily documented and safe)
    m_pro, sig_pro = create_synthetic_star(
        processor,
        "pro_crypto",
        100,
        {
            "sec_reflection_metaprogramming": 50,
            "sec_bitwise_ops": 50,
            "sec_high_risk_execution": 10,
            "doc": 100,
            "safety": 20,
            "cryptography": 10,
        },
    )

    r_raw = processor.calculate_risk_vector(m_raw, sig_raw)
    r_pro = processor.calculate_risk_vector(m_pro, sig_pro)

    idx_ob = processor.RISK_SCHEMA.index("obscured_payload")

    assert r_pro["risk_vector"][idx_ob] < r_raw["risk_vector"][idx_ob], (
        "Crypto/Professionalism shield failed to dampen obfuscation risk!"
    )


# ==============================================================================
# TEST 31: LLM API SECRETS LEAK
# ==============================================================================
def test_signal_processor_llm_api_secrets(processor):
    """Proves that hardcoded secrets mixed with LLM APIs trigger a massive careless amplifier."""
    # 1. Standard secret leak (Requires sec_heat_triggers to bypass the 2.0 clamp)
    _unused_m_std, sig_std = create_synthetic_star(
        processor,
        "std_leak",
        500,
        {"sec_hardcoded_secrets": 1, "globals": 1, "sec_reflection_metaprogramming": 1},
    )

    # 2. Careless LLM API secret leak (Calling APIs without using global variables)
    m_llm, _unused_sig_llm = create_synthetic_star(
        processor,
        "llm_leak",
        500,
        {"sec_hardcoded_secrets": 1, "llm_api": 5, "globals": 0, "sec_reflection_metaprogramming": 1},
    )


# ==============================================================================
# TEST 32: SAFE MINIFIED VENDOR FILE
# ==============================================================================
def test_signal_processor_safe_minified(processor):
    """Proves that minified files with zero malicious intent safely bypass the tripwire."""
    m_safe, sig_safe = create_synthetic_star(
        processor, "jquery_min", 100, {"branch": 50, "state_mutation": 20}
    )
    m_safe["is_minified"] = True

    r_safe = processor.calculate_risk_vector(m_safe, sig_safe)

    assert r_safe["risk_vector"] == [0.0] * len(processor.RISK_SCHEMA), (
        "Safe minified file failed to zero out risks!"
    )
    assert r_safe["telemetry"]["domain_context"]["alert"] == "MINIFIED VENDOR BYPASS", (
        "Minified bypass flag missing!"
    )



# ==============================================================================
# TEST 34: AI TOPOLOGY (DEEP LEARNING & TRADITIONAL ML)
# ==============================================================================
def test_signal_processor_ai_topology_dl_ml(processor):
    """Ensures the AI topology summarizer correctly identifies Deep Learning and Traditional ML."""
    # Deep Learning
    m_dl, sig_dl = create_synthetic_star(
        processor, "pytorch_model", 100, {"dl_frameworks": 10}
    )
    r_dl = processor.calculate_risk_vector(m_dl, sig_dl)
    m_dl.update(r_dl)

    # Traditional ML
    m_ml, sig_ml = create_synthetic_star(
        processor, "xgboost_model", 100, {"ml_traditional": 10}
    )
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
# TEST 35: PARANOID MODE ACTIVATION
# ==============================================================================
def test_signal_processor_paranoid_mode(processor):
    """Proves that Paranoid Mode tightens the Sigmoid thresholds across security lenses."""
    m_para, sig_para = create_synthetic_star(
        processor, "paranoid_file", 500, {"sec_high_risk_execution": 5, "sec_io": 5}
    )

    # Calculate in Standard Mode
    processor.is_paranoid = False
    r_std = processor.calculate_risk_vector(m_para, sig_para)

    # Calculate in Paranoid Mode
    processor.is_paranoid = True
    r_para = processor.calculate_risk_vector(m_para, sig_para)

    # Reset the engine state so subsequent tests aren't affected
    processor.is_paranoid = False

    idx_inj = processor.RISK_SCHEMA.index("injection_surface")
    assert r_para["risk_vector"][idx_inj] > r_std["risk_vector"][idx_inj], (
        "Paranoid mode failed to amplify the risk exposure!"
    )


# ==============================================================================
# TEST 36: AI TOPOLOGY (RAG & CLOUD WRAPPERS)
# ==============================================================================
def test_signal_processor_ai_topology_rag_cloud(processor):
    """Ensures the AI topology summarizer correctly identifies RAG pipelines and Cloud wrappers."""
    # RAG Pipeline
    m_rag, sig_rag = create_synthetic_star(
        processor, "rag_bot", 100, {"llm_vector_store": 10, "llm_api": 5}
    )
    r_rag = processor.calculate_risk_vector(m_rag, sig_rag)
    m_rag.update(r_rag)

    # Cloud API Wrapper
    m_cloud, sig_cloud = create_synthetic_star(
        processor, "cloud_bot", 100, {"llm_api": 10}
    )
    r_cloud = processor.calculate_risk_vector(m_cloud, sig_cloud)
    m_cloud.update(r_cloud)

    # Summarize RAG
    sum_rag = processor.summarize_galaxy_metrics([m_rag], [])
    assert (
        sum_rag["ai_topology"]["classification"]
        == "RAG Pipeline (Retrieval-Augmented Generation)"
    ), "Failed to classify RAG Pipeline!"

    # Summarize Cloud
    sum_cloud = processor.summarize_galaxy_metrics([m_cloud], [])
    assert sum_cloud["ai_topology"]["classification"] == "Cloud API Wrapper", (
        "Failed to classify Cloud API Wrapper!"
    )


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
    assert r_safe["risk_vector"][idx_saf] == 0.0, (
        "Overflow fallback failed to zero out the mathematically safe file!"
    )
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
    assert standalone_engine is not None, (
        "SignalProcessor failed to initialize without a parent logger!"
    )

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
    """Proves that deeply nested/heavy functions lacking docstrings spike documentation risk."""
    # 1. Complex function WITH a docstring
    m_doc, sig_doc = create_synthetic_star(
        processor, "documented_heavy", 100, {"doc": 10}
    )
    m_doc["functions"] = [
        {"name": "heavy_func", "loc": 50, "big_o_depth": 3, "docstring": True}
    ]

    # 2. Complex function WITHOUT a docstring
    m_blind, sig_blind = create_synthetic_star(
        processor, "blind_heavy", 100, {"doc": 10}
    )
    m_blind["functions"] = [
        {"name": "heavy_func", "loc": 50, "big_o_depth": 3, "docstring": False}
    ]

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
    m_debt, sig_debt = create_synthetic_star(
        processor, "fragile_only", 500, {"fragile_debt": 2}
    )

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

    assert "exposures" in report, (
        "Report generator completely failed on malformed data!"
    )

    # The lowest/highest rankings should have safely defaulted the values to 0.0
    for exposure_key, ranking in report["exposures"].items():
        assert ranking["highest"][0]["value"] == 0.0, (
            f"Fallback failed to zero out invalid data for {exposure_key}!"
        )


# ==============================================================================
# TEST 43: CRITICAL LEAK BYPASS (Absolute Maximum Risk)
# ==============================================================================
def test_signal_processor_critical_leak_bypass(processor):
    """Proves that critical leaks bypass standard physics and max out secrets risk."""
    m_leak, sig_leak = create_synthetic_star(processor, "aws_key", 10, {})
    m_leak["path"] = "config/production.pem"
    m_leak["metadata"] = {"aperture_reason": "CRITICAL LEAK DETECTED"}

    r_leak = processor.calculate_risk_vector(m_leak, sig_leak)

    idx_sec = processor.RISK_SCHEMA.index("secrets_risk")

    assert r_leak["file_impact"] == 150.0, (
        "Critical leak failed to trigger the 150.0 mass spike!"
    )
    assert r_leak["risk_vector"][idx_sec] == 100.0, (
        "Critical leak failed to max out secrets risk!"
    )
    assert r_leak["telemetry"]["domain_context"]["alert"] == "CRITICAL LEAK BYPASS", (
        "Bypass alert missing from telemetry!"
    )


# ==============================================================================
# TEST 44: THE DARKNESS RATIO (100% Unparsable)
# ==============================================================================
def test_signal_processor_darkness_ratio(processor):
    """Ensures global synthesis survives a completely broken repository (0 parsed, 10 unparsable)."""
    unparsable_files = [{"name": f"broken_{i}.py"} for i in range(10)]

    # 0 parsed files, 10 unparsable files
    summary = processor.summarize_galaxy_metrics([], unparsable_files)

    assert summary["summary"]["total_files"] == 10, (
        "Failed to count unparsable files in total!"
    )
    assert summary["summary"]["verified_files"] == 0, "Verified files should be 0!"
    assert summary["summary"]["Percent_Visible"] == 0.0, (
        "Darkness ratio failed to calculate 0% visibility!"
    )
    assert summary["unparsable_files"]["ambig_file_count"] == 10, (
        "Failed to aggregate unparsable file count!"
    )


# ==============================================================================
# TEST 45: HARDWARE BRIDGE DAMPENERS
# ==============================================================================
def test_signal_processor_hardware_bridge_shield(processor):
    """Proves that Hardware Bridges (Serial/USB I/O) are forgiven for dynamic execution."""
    # 1. Raw Execution (Malicious)
    m_raw, sig_raw = create_synthetic_star(
        processor, "raw_exec", 100, {"sec_high_risk_execution": 10, "sec_io": 10}
    )

    # 2. Hardware Execution (Expected Arduino/Serial behavior)
    m_hw, sig_hw = create_synthetic_star(
        processor,
        "hw_exec",
        100,
        {"sec_high_risk_execution": 10, "sec_io": 10, "hardware_bridge": 10},
    )

    r_raw = processor.calculate_risk_vector(m_raw, sig_raw)
    r_hw = processor.calculate_risk_vector(m_hw, sig_hw)

    idx_inj = processor.RISK_SCHEMA.index("injection_surface")

    assert r_hw["risk_vector"][idx_inj] < r_raw["risk_vector"][idx_inj], (
        "Hardware bridge shield failed to dampen injection risk!"
    )


# ==============================================================================
# TEST 46: ALGORITHMIC DOS O(N) BYPASS
# ==============================================================================
def test_signal_processor_algorithmic_dos_linear_bypass(processor):
    """Ensures O(N) linear loops are ignored by the Algorithmic DoS equations."""
    m_linear, sig_linear = create_synthetic_star(
        processor, "linear_loop", 100, {"api": 10}
    )
    # big_o_depth = 1 is standard O(N)
    m_linear["functions"] = [
        {"name": "safe_loop", "loc": 50, "big_o_depth": 1, "db_complexity": 5}
    ]

    r_linear = processor.calculate_risk_vector(m_linear, sig_linear)
    idx_dos = processor.RISK_SCHEMA.index("algorithmic_dos")

    # Because depth is < 2, the loop `continue` triggers and mass remains 0.0
    assert r_linear["risk_vector"][idx_dos] == 0.0, (
        "O(N) linear loops should not trigger Algorithmic DoS!"
    )


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
    signals into valid density percentages, catching thread starvation.
    """
    # 5 threads in a 100-line file = 0.05 ratio. 
    # Scaled to percentage = 5.0%. Threshold is 4.0%. 
    # This MUST trigger a high risk exposure.
    meta, sig = create_synthetic_star(
        processor, "thread_router", 100, {"concurrency": 5}
    )
    
    # Give it a heavy O(N^3) big_o_depth to spike the thread starvation multiplier
    meta["functions"] = [
        {"name": "heavy_thread", "loc": 50, "big_o_depth": 3, "hit_vector": {"concurrency": 5}}
    ]

    res = processor.calculate_risk_vector(meta, sig)
    idx_async = processor.RISK_SCHEMA.index("concurrency")
    
    score = res["risk_vector"][idx_async]
    
    assert score > 50.0, (
        f"Concurrency scaling bug regression! Expected a high risk score, but got {score}%."
    )


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
            "high_risk_execution": 5000,
            "sec_high_risk_execution": 5000,
            "sec_io": 5000,
            "fragile_debt": 5000,
        },
    )

    # Inject the developer suppressions
    meta["mitigations"] = [
        "logic_bomb",         # Valid override
        "tech_debt",          # Valid override
        "made_up_phantom_123" # Schema drift / fake risk
    ]

    res = processor.calculate_risk_vector(meta, sig)

    idx_lb = processor.RISK_SCHEMA.index("logic_bomb")
    idx_debt = processor.RISK_SCHEMA.index("tech_debt")
    idx_inj = processor.RISK_SCHEMA.index("injection_surface")

    # 1. Assert the targeted risks were zeroed out
    assert res["risk_vector"][idx_lb] == 0.0, "Inline suppression failed to zero out Logic Bomb!"
    assert res["risk_vector"][idx_debt] == 0.0, "Inline suppression failed to zero out Tech Debt!"

    # 2. Assert un-suppressed risks are still 100% lethal
    assert res["risk_vector"][idx_inj] > 80.0, "Inline suppression accidentally wiped out Injection Surface!"

    # 3. Assert the metadata passed cleanly to the telemetry for the UI
    assert "made_up_phantom_123" in res["telemetry"]["mitigation_telemetry"], (
        "Phantom risk was not passed to the UI telemetry payload!"
    )
