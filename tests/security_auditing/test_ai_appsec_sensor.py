# IMPORTANT: Adjust this path to match exactly where your file is located
from gitgalaxy.tools.ai_guardrails.ai_appsec_sensor import AIAppSecSensor


# ==============================================================================
# TEST 1: Autonomous Execution Vector (Weaponized Prompt Injection)
# ==============================================================================
def test_autonomous_execution_vector_detection():
    """
    Proves that an LLM directly wired to OS execution (eval/subprocess)
    and exposed via a public API correctly triggers the Autonomous Execution Vector alert.
    """
    sensor = AIAppSecSensor()

    mock_files = [
        {
            "telemetry": {},
            "equations": {
                "llm_api": 1,  # AI is present
                "api": 1,  # Exposed to the public internet
                "sec_high_risk_execution": 1,  # Contains eval() or subprocess execution
            },
        }
    ]

    result = sensor.hunt_threats(mock_files)
    appsec_report = result[0]["telemetry"]["ai_appsec"]

    assert appsec_report["is_rce_funnel"] is True, "Failed to detect the Autonomous Execution Vector!"
    assert any("Autonomous Execution Vector" in warning for warning in appsec_report["critical_warnings"])


# ==============================================================================
# TEST 2: Over-Permissioned Agent (Autonomous Data Corruption)
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
# TEST 2.1: THE DEAD KEY REGRESSION GUARD (#365)
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
# TEST 3: Agentic Exfiltration Vector (Unsandboxed Sockets)
# ==============================================================================
def test_exfiltration_vector_detection():
    """
    Proves that an LLM with access to both raw network sockets and hardcoded
    environment secrets triggers the Agentic Exfiltration Vector alert.
    """
    sensor = AIAppSecSensor()

    mock_files = [
        {
            "telemetry": {},
            "equations": {
                "llm_api": 1,  # AI is present
                "io": 1,  # Can make outbound network requests
                "sec_hardcoded_secrets": 1,  # Has access to AWS keys/passwords
            },
        }
    ]

    result = sensor.hunt_threats(mock_files)
    appsec_report = result[0]["telemetry"]["ai_appsec"]

    assert appsec_report["agentic_exfiltration_risk"] is True, "Failed to detect the Agentic Exfiltration Vector!"
    assert any("Agentic Exfiltration Vector" in warning for warning in appsec_report["critical_warnings"])


# ==============================================================================
# TEST 4: The Clean Baseline (False-Positive Guard)
# ==============================================================================
def test_safe_baseline():
    """
    Proves that a properly sandboxed AI integration (e.g., an LLM script with
    no network execution, no eval(), and high safety density) passes cleanly.
    """
    sensor = AIAppSecSensor()

    mock_files = [
        {
            "coding_loc": 50,
            "telemetry": {},
            "equations": {
                "llm_api": 1,  # ✅ AI is present
                "api": 0,  # ✅ Not exposed to the public
                "sec_high_risk_execution": 0,  # ✅ No eval/subprocess
                "sec_hardcoded_secrets": 0,  # ✅ No secrets exposed
                "safety": 5,  # ✅ High defensive try/catch density (-> density 1.0)
            },
        }
    ]

    result = sensor.hunt_threats(mock_files)
    appsec_report = result[0]["telemetry"]["ai_appsec"]

    # Assert absolutely NO flags were triggered
    assert appsec_report["is_rce_funnel"] is False
    assert appsec_report["over_permissioned_agent"] is False
    assert appsec_report["agentic_exfiltration_risk"] is False
    assert len(appsec_report["critical_warnings"]) == 0, "False positive triggered on a safe file!"
