# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution

import json
import logging
from typing import Dict, Any, List

class SarifRecorder:
    """
    Translates GitGalaxy's global RAM state into the Static Analysis Results 
    Interchange Format (SARIF) 2.1.0 for native enterprise CI/CD integration.
    """

    def __init__(self, version: str = "2.4.0", parent_logger: logging.Logger = None):
        self.logger = parent_logger.getChild("sarif_recorder") if parent_logger else logging.getLogger("sarif_recorder")
        self.version = version

    def generate_report(
        self, 
        parsed_files: List[Dict[str, Any]], 
        summary: Dict[str, Any], 
        session_meta: Dict[str, Any], 
        output_path: str
    ) -> None:
        self.logger.info("SARIF: Translating RAM state to industry-standard SARIF 2.1.0 payload...")

        # 1. Dependency Mode Sensitivity
        is_zero_dep = session_meta.get("zero_dependency_mode", False)
        missing_deps = session_meta.get("missing_dependencies", {})

        # 2. Build the foundational SARIF Schema
        sarif_payload = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "GitGalaxy Scanner",
                            "version": session_meta.get("engine", f"v{self.version}"),
                            "informationUri": "https://gitgalaxy.io",
                            "rules": self._build_rules_taxonomy()
                        }
                    },
                    "invocations": [
                        {
                            "executionSuccessful": True,
                            "toolExecutionNotifications": self._build_dependency_notifications(is_zero_dep, missing_deps)
                        }
                    ],
                    "results": []
                }
            ]
        }

        results_list = sarif_payload["runs"][0]["results"]

        # 3. Iterate the File Nodes and translate physical detections
        for node in (parsed_files or []):
            rel_path = node.get("path", "unknown")
            telemetry = node.get("telemetry", {})
            start_line = node.get("start_line", 1)

            # A. Extract Multiclass ML Threat Targets (XGBoost)
            # If zero_dependency_mode is true, this will naturally be false and omit safely
            if node.get("is_ml_threat", False):
                ai_class = telemetry.get("domain_context", {}).get("AI Threat Class", "Unknown Threat")
                confidence = telemetry.get("domain_context", {}).get("AI Threat Confidence", "0%")
                
                results_list.append({
                    "ruleId": f"GG-ML-{ai_class.upper().replace(' ', '_').replace('/', '')}",
                    "level": "error",
                    "message": {
                        "text": f"XGBoost Inference confirmed a weaponized behavioral signature: {ai_class} (Confidence: {confidence})."
                    },
                    "locations": [self._build_location(rel_path, start_line)],
                    "properties": {
                        "category": "Machine Learning Inference",
                        "precision": confidence
                    }
                })

            # B. Extract Passive Security Lens Snippets (SAST)
            threat_snippets = telemetry.get("threat_snippets", {})
            threat_locations = telemetry.get("threat_locations", {})

            for threat_type, snippets in threat_snippets.items():
                # Attempt to retrieve exact line locations, matching by raw or sec_ prefixed key
                locs = threat_locations.get(threat_type) or threat_locations.get(f"sec_{threat_type}", [])

                for idx, snippet in enumerate(snippets):
                    # Safely determine severity
                    severity = "error" if any(x in threat_type for x in ["secret", "injection", "execution", "corruption"]) else "warning"
                    
                    # Fallback to file's start_line if specific LOC isn't captured
                    exact_line = locs[idx] if idx < len(locs) else start_line
                    
                    results_list.append({
                        "ruleId": f"GG-SAST-{threat_type.upper()}",
                        "level": severity,
                        "message": {
                            "text": f"Vulnerability signature triggered: {snippet}"
                        },
                        "locations": [self._build_location(rel_path, exact_line)],
                        "properties": {
                            "category": "Structural SAST"
                        }
                    })

            # C. Extract AI AppSec Sensor Warnings
            ai_appsec = telemetry.get("ai_appsec", {})
            for warning in ai_appsec.get("critical_warnings", []):
                results_list.append({
                    "ruleId": "GG-AGENT-VULNERABILITY",
                    "level": "error",
                    "message": {"text": warning},
                    "locations": [self._build_location(rel_path, start_line)],
                    "properties": {"category": "AI Application Security"}
                })

            # D. Extract Autonomous Guardrails (Dev Agent Firewall)
            guardrails = telemetry.get("ai_guardrails", {})
            for warning in guardrails.get("warnings", []):
                results_list.append({
                    "ruleId": "GG-AGENT-GUARDRAIL",
                    "level": "warning",
                    "message": {"text": warning},
                    "locations": [self._build_location(rel_path, start_line)],
                    "properties": {"category": "Autonomous Zero-Trust"}
                })

        # 4. Write the sealed standardized file to disk
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(sarif_payload, f, indent=2)
            self.logger.info(f"SARIF: Successfully exported {len(results_list)} findings to {output_path}")
        except Exception as e:
            self.logger.error(f"SARIF: Export failed - {str(e)}", exc_info=True)


    def _build_location(self, uri: str, line: int) -> Dict[str, Any]:
        """Constructs the standard SARIF physical location object."""
        return {
            "physicalLocation": {
                "artifactLocation": {
                    "uri": uri
                },
                "region": {
                    "startLine": line,
                    # Enterprise pipelines default to highlighting the whole line if columns are omitted
                    "startColumn": 1 
                }
            }
        }

    def _build_dependency_notifications(self, is_zero_dep: bool, missing_deps: Dict[str, bool]) -> List[Dict[str, Any]]:
        """Injects explicit telemetry into the SARIF runner so auditors know if engines degraded."""
        notifications = []
        if is_zero_dep:
            missing_list = [pkg for pkg, is_missing in missing_deps.items() if is_missing]
            notifications.append({
                "level": "note",
                "message": {
                    "text": f"GitGalaxy executed in Zero-Dependency Mode. The following engines were bypassed and their metrics are safely reported as NULL: {', '.join(missing_list)}"
                },
                "descriptor": {
                    "id": "GG-SYS-ZERO-DEP"
                }
            })
        return notifications

    def _build_rules_taxonomy(self) -> List[Dict[str, Any]]:
        """
        Maps GitGalaxy's internal rule IDs to standardized descriptions.
        This provides enterprise dashboards with the context needed to display the alerts.
        """
        return [
            {
                "id": "GG-SAST-HARDCODED_SECRETS",
                "shortDescription": {"text": "Hardcoded Cryptographic Secret or Token"},
                "fullDescription": {"text": "A hardcoded credential, API key, or cryptographic secret was detected in the source code."},
                "properties": {"tags": ["CWE-798", "security"]}
            },
            {
                "id": "GG-SAST-HIGH_RISK_EXECUTION",
                "shortDescription": {"text": "Dynamic Code Execution (RCE Vector)"},
                "fullDescription": {"text": "Detected usage of dynamic execution (eval, exec, subprocess) which can lead to Remote Code Execution if tainted by user input."},
                "properties": {"tags": ["CWE-94", "security"]}
            },
            {
                "id": "GG-SAST-IO",
                "shortDescription": {"text": "Unfiltered Network or Disk I/O"},
                "properties": {"tags": ["CWE-400", "security"]}
            },
            {
                "id": "GG-AGENT-VULNERABILITY",
                "shortDescription": {"text": "Agentic Execution or Exfiltration Vulnerability"},
                "fullDescription": {"text": "An AI/LLM model is structurally wired to network I/O or execution sinks, introducing Prompt Injection and Agentic RCE risks."},
                "properties": {"tags": ["CWE-1336", "security", "ai-appsec"]}
            },
            {
                "id": "GG-AGENT-GUARDRAIL",
                "shortDescription": {"text": "Guardrail: High-Complexity File (No Autonomous AI Edits)"},
                "fullDescription": {"text": "This file's structural complexity, downstream exposure, or state flux makes it unsafe for autonomous AI agents to edit. Human-in-the-Loop (HITL) supervision is strictly required to prevent architectural degradation or hallucinated logic."},
                "properties": {"tags": ["architecture", "ai-guardrail", "hitl-required"]}
            },
            {
                "id": "GG-ML-STEALER_TROJAN",
                "shortDescription": {"text": "Behavioral Malware Signature: Stealer/Trojan"},
                "fullDescription": {"text": "The XGBoost inference engine detected high-entropy structural topologies consistent with Trojans or Credential Stealers."},
                "properties": {"tags": ["CWE-506", "malware"]}
            }
            # Additional mappings will automatically fall back to the ruleId string in the UI if not explicitly defined here
        ]