# IMPORTANT: Adjust this path to match exactly where your file is located
from gitgalaxy.tools.ai_guardrails.ai_appsec_sensor import AIAppSecSensor


# ==============================================================================
# TEST 1: Over-Permissioned Agent (Autonomous Data Corruption)
# ==============================================================================
def test_over_permissioned_agent_detection():
    """
    Proves that an agent orchestration framework (langchain/llama_index --
    #365/#323: the closest lexically-detectable proxy for agentic tool-binding
    this engine has, since "ai_tools" was removed from SIGNAL_SCHEMA in #323
    as fundamentally undetectable via regex), combined with raw network/disk
    IO write access and low defensive programming density, triggers the
    Over-Permissioned Agent alert. (#1013: this used to also accept
    `max_db_complexity` as an alternate trigger, removed as a flawed metric.)
    """
    sensor = AIAppSecSensor()

    mock_files = [
        {
            "coding_loc": 100,
            "telemetry": {},
            "equations": {
                "llm_orchestrator": 1,  # langchain/llama_index present -> agentic tool-binding
                "io": 1,  # Raw network/disk IO write access
                "safety": 0,  # Dangerously low defensive programming -> density 0.0
            },
        }
    ]

    result = sensor.hunt_threats(mock_files)
    appsec_report = result[0]["telemetry"]["ai_appsec"]

    assert appsec_report["over_permissioned_agent"] is True, "Failed to detect the Over-Permissioned Agent!"
    assert any("Over-Permissioned Agent" in warning for warning in appsec_report["critical_warnings"])


# ==============================================================================
# TEST 1.1: THE DEAD KEY REGRESSION GUARD (#365)
# ==============================================================================
def test_over_permissioned_agent_no_longer_reads_dead_ai_tools_key():
    """
    Regression guard for #365: a mocked "ai_tools" equation -- the removed
    SIGNAL_SCHEMA key this rule used to (uselessly) gate on -- must NOT
    trigger the Over-Permissioned Agent alert on its own. Only a real,
    still-live signal (llm_orchestrator) should be able to.
    """
    sensor = AIAppSecSensor()

    mock_files = [
        {
            "coding_loc": 100,
            "telemetry": {},
            "equations": {
                "ai_tools": 1,  # dead key -- must be inert
                "io": 1,  # Raw network/disk IO write access
                "safety": 0,
            },
        }
    ]

    result = sensor.hunt_threats(mock_files)
    appsec_report = result[0]["telemetry"]["ai_appsec"]

    assert appsec_report["over_permissioned_agent"] is False, (
        "The dead 'ai_tools' key must not be able to trigger this rule!"
    )


# ==============================================================================
# TEST 2: The Clean Baseline (False-Positive Guard)
# ==============================================================================
def test_safe_baseline():
    """
    Proves that a properly sandboxed AI integration (e.g., an LLM script with
    high safety density) passes cleanly.
    """
    sensor = AIAppSecSensor()

    mock_files = [
        {
            "coding_loc": 50,
            "telemetry": {},
            "equations": {
                "llm_orchestrator": 1,  # ✅ AI orchestration present
                "io": 1,  # ✅ Has IO access
                "safety": 5,  # ✅ High defensive try/catch density (-> density 1.0)
            },
        }
    ]

    result = sensor.hunt_threats(mock_files)
    appsec_report = result[0]["telemetry"]["ai_appsec"]

    # Assert absolutely NO flags were triggered
    assert appsec_report["over_permissioned_agent"] is False
    assert len(appsec_report["critical_warnings"]) == 0, "False positive triggered on a safe file!"


# ==============================================================================
# TEST 2.1: Removed-metric regression guard (#1102)
# ==============================================================================
def test_report_no_longer_contains_removed_cooccurrence_keys():
    """
    Regression guard for #1102: `is_rce_funnel` and `agentic_exfiltration_risk`
    were removed because they flagged a file just because unrelated regex
    categories (an LLM signal, a public-API/IO signal, an eval/secrets signal)
    co-occurred somewhere in it, with zero proof of actual data flow between
    them -- the same "hallucinated" pattern epic #1025/#1020 already removed
    from RISK_SCHEMA/SIGNAL_SCHEMA. Even a file shaped to have triggered both
    old rules must no longer produce those keys or their CRITICAL messages.
    """
    sensor = AIAppSecSensor()

    mock_files = [
        {
            "coding_loc": 100,
            "telemetry": {},
            "equations": {
                "llm_api": 1,
                "llm_orchestrator": 1,
                "api": 1,
                "io": 1,
                "sec_high_risk_execution": 1,
                "sec_hardcoded_secrets": 1,
                "safety": 5,
            },
        }
    ]

    result = sensor.hunt_threats(mock_files)
    appsec_report = result[0]["telemetry"]["ai_appsec"]

    assert "is_rce_funnel" not in appsec_report
    assert "agentic_exfiltration_risk" not in appsec_report
    assert not any(
        "Autonomous Execution Vector" in w or "Agentic Exfiltration Vector" in w
        for w in appsec_report["critical_warnings"]
    )
