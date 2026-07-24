import pytest
from unittest.mock import patch
from gitgalaxy.tools.ai_guardrails.dev_agent_firewall import DevAgentFirewall


@pytest.fixture
def firewall():
    """
    Initializes the firewall with a controlled schema patch.
    This ensures tests don't break if upstream schema indices change.
    """
    mock_schemas = {
        "RISK_SCHEMA": ["tech_debt", "state_flux", "cognitive_load"],
        "SIGNAL_SCHEMA": ["io", "reflection_metaprogramming"]
    }
    with patch("gitgalaxy.tools.ai_guardrails.dev_agent_firewall.RECORDING_SCHEMAS", mock_schemas):
        yield DevAgentFirewall()


# ==============================================================================
# TEST 1: The Context Window Shredder (Black Hole Detection)
# ==============================================================================
def test_black_hole_detection(firewall):
    """
    Proves that files exceeding 8k tokens with O(N^3) or worse complexity
    are correctly flagged as Context Window Shredders.
    """
    mock_files = [
        {
            "token_mass": 8500,  # ☢️ Exceeds 8k limit
            "max_big_o": 3,      # ☢️ High algorithmic complexity
            "telemetry": {},
            "risk_vector": [],
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails["is_agentic_black_hole"] is True, "Failed to detect the Agentic Black Hole!"
    assert any("Context Window Exhaustion" in warning for warning in guardrails["warnings"])


# ==============================================================================
# TEST 1.5: THE BLACK HOLE, END TO END (#372 -- the real pipeline, not a mock)
# ==============================================================================
def test_black_hole_detection_from_real_network_risk_sensor_output(firewall):
    """
    Regression test for #372: dev_agent_firewall.py read file_data["max_big_o"]
    directly, but the only real producer set it as a networkx graph node
    attribute (network_risk_sensor.py) that was never copied back onto the
    file dict -- so this check could never fire on real data, only on a
    hand-mocked "max_big_o" like the test above. Drives a REAL
    NetworkRiskSensor.build_dependency_graph() output into the REAL firewall.
    """
    from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor

    parsed_files = [
        {
            "path": "src/math/heavy_calc.py",
            "raw_imports": [],
            "risk_vector": [],
            "token_mass": 8500,  # Exceeds 8k limit
            "functions": [{"big_o_depth": 4, "is_recursive": True}],  # O(N^4)
            "telemetry": {},
        }
    ]

    mapped_files, _ = NetworkRiskSensor().build_dependency_graph(parsed_files)
    result = firewall.evaluate_ecosystem(mapped_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails["is_agentic_black_hole"] is True, (
        "max_big_o from the real network sensor output must reach the firewall!"
    )


# ==============================================================================
# TEST 2: The HITL Mandate (Blast Radius + Risk Debt)
# ==============================================================================
def test_hitl_mandate_detection(firewall):
    """
    Proves that high PageRank (blast radius) combined with severe risk debt
    mandates a Human-in-the-Loop constraint.
    """
    mock_files = [
        {
            "token_mass": 1000,
            "max_big_o": 1,
            "risk_vector": [100, 50, 60],  # ☢️ Sum = 210 (> 200 threshold)
            "telemetry": {
                "network_metrics": {"normalized_blast_radius": 1.5} # ☢️ > 1.0 threshold
            }
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails["requires_hitl"] is True, "Failed to enforce the HITL Mandate!"
    assert any("Human-in-the-Loop required" in warning for warning in guardrails["warnings"])


# ==============================================================================
# TEST 3: The Hallucination Zone (#106 -- spatially verified, not global-average)
# ==============================================================================
def test_hallucination_zone_detection(firewall):
    """
    Proves that a "reflection_metaprogramming" hit with no nearby "doc" hit --
    in the SAME function -- triggers the Hallucination Zone warning, via the
    persisted threat_locations ledger and correlate_against_ledger() (#348),
    not the old dead doc_density global average (#345).
    """
    mock_files = [
        {
            "threat_locations": {"reflection_metaprogramming": [50]},
            "functions": [{"start_line": 40, "end_line": 60}],
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails["hallucination_zone"] is True, "Failed to detect the Hallucination Zone!"
    assert guardrails["undocumented_metaprogramming"] == 1
    assert any("Hallucination Risk" in warning for warning in guardrails["warnings"])


def test_hallucination_zone_spares_locally_documented_metaprogramming(firewall):
    """
    #106's second documented blind spot: metaprogramming that IS documented
    right where it lives must NOT be flagged, even though this is exactly the
    shape the old dead doc_density check would have gotten wrong if it had
    ever fired (a low file-wide average could still block a well-documented
    function).
    """
    mock_files = [
        {
            "threat_locations": {
                "reflection_metaprogramming": [45],
                "doc": [40],
            },
            "functions": [{"start_line": 40, "end_line": 60}],
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails["hallucination_zone"] is False
    assert "undocumented_metaprogramming" not in guardrails


def test_hallucination_zone_ignores_documentation_in_a_different_function(firewall):
    """
    #106's first documented blind spot: a doc comment concentrated in one
    function (e.g. a class docstring near the top) must not paper over
    undocumented metaprogramming in a totally different function -- this is
    exactly the false negative the old GLOBAL doc_density average produced.
    """
    mock_files = [
        {
            "threat_locations": {
                "reflection_metaprogramming": [50],
                "doc": [5],
            },
            "functions": [
                {"start_line": 1, "end_line": 10},
                {"start_line": 40, "end_line": 60},
            ],
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails["hallucination_zone"] is True
    assert guardrails["undocumented_metaprogramming"] == 1


# ==============================================================================
# TEST 4: The Silent Mutation Risk (Schema Drift Fix)
# ==============================================================================
def test_silent_mutation_risk_detection(firewall):
    """
    Proves that files with high state flux (pulled from risk_vector), high inbound 
    dependencies, and zero test coverage are flagged as a Silent Mutation Risk.
    """
    mock_files = [
        {
            "risk_vector": [10.0, 55.0, 20.0],  # ☢️ Index 1 is state_flux (> 50)
            "telemetry": {
                "has_tests": False,                   # ☢️ Zero test coverage
                "network_metrics": {"in_degree": 6},  # ☢️ > 5 dependencies rely on this
            }
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails.get("silent_mutation_risk") is True, "Failed to detect Silent Mutation Risk!"
    assert any("Cascading State Flux" in warning for warning in guardrails["warnings"])


# ==============================================================================
# TEST 5: The Clean Baseline (False-Positive Guard)
# ==============================================================================
def test_safe_agentic_baseline(firewall):
    """
    Proves that a well-documented, well-tested, simple file passes the firewall
    without triggering any agentic guardrails.
    """
    mock_files = [
        {
            "token_mass": 2000,
            "max_big_o": 1,
            "risk_vector": [10, 5, 0],  # ✅ Low risk debt
            "hit_vector": [0, 0],       # ✅ No dynamic execution
            "telemetry": {
                "doc_density": 0.85,
                "has_tests": True,
                "network_metrics": {
                    "normalized_blast_radius": 0.5,
                    "in_degree": 1,
                },
            },
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    assert guardrails["is_agentic_black_hole"] is False
    assert guardrails["requires_hitl"] is False
    assert guardrails["hallucination_zone"] is False
    assert guardrails.get("silent_mutation_risk", False) is False
    assert len(guardrails["warnings"]) == 0


# ==============================================================================
# TEST 6: Unhappy Path - Missing Vectors (Zero-Dependency Mode)
# ==============================================================================
def test_survives_missing_vectors(firewall):
    """
    Proves the firewall does not crash with KeyErrors or TypeErrors if the 
    artifact entirely lacks a risk_vector or hit_vector (e.g., bypassed assets).
    """
    mock_files = [
        {
            "token_mass": 100,
            # No hit_vector
            # No risk_vector
            "telemetry": {}
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    # Should default cleanly to safe
    assert guardrails["silent_mutation_risk"] is False
    assert guardrails["hallucination_zone"] is False


# ==============================================================================
# TEST 7: Unhappy Path - Short Vectors (Index Out Of Bounds Guard)
# ==============================================================================
def test_survives_short_vectors(firewall):
    """
    Proves the firewall avoids IndexError if an upstream bug truncates the 
    arrays before they reach the expected schema indices.
    """
    mock_files = [
        {
            # Schema says state_flux is at index 1, but we only pass index 0
            "risk_vector": [99.0], 
            # Schema says metaprogramming is at index 1, but we only pass index 0
            "hit_vector": [5],     
            "telemetry": {
                "has_tests": False,
                "network_metrics": {"in_degree": 10},
                "doc_density": 0.1
            }
        }
    ]

    result = firewall.evaluate_ecosystem(mock_files)
    guardrails = result[0]["telemetry"]["ai_guardrails"]

    # Even though conditions for flags were met in telemetry, the short arrays 
    # should safely abort the checks rather than crash the engine.
    assert guardrails["silent_mutation_risk"] is False
    assert guardrails["hallucination_zone"] is False