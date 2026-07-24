#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Autonomous Agent Firewall
#
# PURPOSE:
# Evaluates the structural and topological constraints of the codebase to 
# determine the safety boundaries for autonomous AI agents (e.g., Claude, Cursor).
#
# ARCHITECTURAL DECISION:
# Autonomous coding agents excel in isolated, pure-function environments but 
# struggle with highly coupled, poorly documented, or dynamically generated logic.
# This firewall establishes Zero-Trust guardrails to prevent AI agents from 
# executing unchecked modifications in volatile sectors, mitigating the risk 
# of cascading failures, context window exhaustion, and silent state mutations.
# ==============================================================================
import logging
from typing import List, Dict, Any

from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS
from gitgalaxy.core.spatial_correlation import correlate_against_ledger

class DevAgentFirewall:
    """
    Autonomous Agent Guardrail Engine.
    """

    def __init__(self, parent_logger=None):
        self.logger = parent_logger.getChild("guardrails") if parent_logger else logging.getLogger("guardrails")

    def evaluate_ecosystem(self, parsed_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.logger.info("Executing Autonomous Agent Firewall & Token Density Validation...")

        risk_schema = RECORDING_SCHEMAS.get("RISK_SCHEMA", [])

        for file_data in parsed_files:
            token_mass = file_data.get("token_mass", 0)
            network_metrics = file_data.get("telemetry", {}).get("network_metrics", {})
            risk_vector = file_data.get("risk_vector", [])  # Assuming standard 0-100 risk scores

            # Extract relevant structural metrics, safely handling None values from Zero-Dependency Mode
            pagerank = network_metrics.get("normalized_blast_radius") or 0.0
            max_big_o = file_data.get("max_big_o") or 1

            guardrails = {
                "is_agentic_black_hole": False,
                "requires_hitl": False,  # Human-in-the-Loop
                "hallucination_zone": False,
                "silent_mutation_risk": False,
                "warnings": [],
            }

            # ---> SAFE SCHEMA EXTRACTION <---
            state_flux = 0
            if "state_flux" in risk_schema and len(risk_vector) > risk_schema.index("state_flux"):
                state_flux = risk_vector[risk_schema.index("state_flux")]

            # 1. Context Window Exhaustion (Agentic Black Hole)
            # If a file exceeds token limits AND has severe algorithmic complexity, the AI will lose context.
            if token_mass is not None and token_mass > 8000 and max_big_o >= 3:
                guardrails["is_agentic_black_hole"] = True
                guardrails["warnings"].append(
                    f"CRITICAL [Context Window Exhaustion]: Token mass ({token_mass}) and O(N^{max_big_o}) complexity will exceed agent context capabilities and induce severe hallucination."
                )

            # 2. The HITL Mandate (Downstream Exposure + Severe Risk Debt)
            if pagerank > 1.0 and sum(risk_vector) > 200:
                guardrails["requires_hitl"] = True
                guardrails["warnings"].append(
                    "WARNING [HITL Mandate]: High Downstream Exposure combined with severe risk debt. Human-in-the-Loop required for structural modifications."
                )

            # 3. Metaprogramming Hallucination Risk (#106)
            # Replaces the old global-average check (file-wide doc_density vs.
            # file-wide metaprogramming count), which was fully dead code -- no
            # producer ever wrote telemetry["doc_density"] (#345) -- and, even
            # if it had, a global average has two documented blind spots: it
            # misses undocumented metaprogramming buried in an otherwise
            # well-documented file, and it false-positives on well-documented
            # metaprogramming just because the REST of the file is sparse.
            #
            # correlate_against_ledger() (#348) proves proximity directly: a
            # "reflection_metaprogramming" hit is only flagged if no "doc" hit
            # falls within max_distance=10 lines AND the same function/satellite
            # -- reusing #106's own anticipated fixture value, matching
            # test_spatial_correlation.py's existing correlate_against_ledger
            # coverage for this exact signal pair.
            undocumented_metaprogramming, _ = correlate_against_ledger(
                file_data.get("threat_locations", {}),
                file_data.get("functions", []),
                "reflection_metaprogramming",
                "doc",
                max_distance=10,
            )
            if undocumented_metaprogramming > 0:
                guardrails["undocumented_metaprogramming"] = undocumented_metaprogramming
                guardrails["hallucination_zone"] = True
                guardrails["warnings"].append(
                    f"DANGER [Hallucination Risk]: {undocumented_metaprogramming} undocumented metaprogramming "
                    "construct(s) found with no surrounding documentation in the same function. Autonomous "
                    "agents are highly likely to hallucinate missing methods."
                )

            # 4. Cascading State Flux (Silent Mutation Risk)
            in_degree = network_metrics.get("in_degree", 0)
            has_tests = file_data.get("telemetry", {}).get("has_tests", False)

            if state_flux > 50 and in_degree > 5 and not has_tests:
                guardrails["silent_mutation_risk"] = True
                guardrails["warnings"].append(
                    f"CRITICAL [Cascading State Flux]: High state mutation ({state_flux}) and dense downstream dependencies ({in_degree}), with zero verification coverage. Autonomous agents cannot mathematically verify their own structural modifications."
                )

            # Inject the firewall report back into the file's telemetry
            if "telemetry" not in file_data:
                file_data["telemetry"] = {}
            file_data["telemetry"]["ai_guardrails"] = guardrails

        return parsed_files