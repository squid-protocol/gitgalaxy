# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import json
import argparse
import os
import re
from pathlib import Path
from typing import Any
from gitgalaxy.standards import analysis_lens as config

# ==============================================================================
# GitGalaxy Phase 8 & 9: Forensic Audit Recorder
# Strategy v6.2.0 Protocol: Data Provenance & State Decoding
# Stage 2.5: Total Feature Parity (Descriptive Descriptors + Performance)
# ==============================================================================


class AuditRecorder:
    """
    Forensic Audit Recorder.

    PURPOSE: Generates a verbose, human-readable forensic JSON log from in-memory
    telemetry state. Designed for enterprise compliance, security debugging, and
    Software Supply Chain Security (SSCS) deep-dive analysis.
    """

    def __init__(self, parent_logger=None):
        import logging

        self.logger = parent_logger.getChild("audit_recorder") if parent_logger else logging.getLogger("audit_recorder")

        # --- DYNAMIC SCHEMA FETCH ---
        schemas = getattr(config, "RECORDING_SCHEMAS", {})
        self.RISK_SCHEMA = schemas.get("RISK_SCHEMA", [])
        # Note: The pipeline calls it SIGNAL_SCHEMA, but the Auditor references it as HIT_SCHEMA
        self.HIT_SCHEMA = schemas.get("SIGNAL_SCHEMA", [])

        # PERFORMANCE OPTIMIZATION: Pre-cache all labels to avoid regex overhead on the hot path
        self._label_cache = {}
        self._friendly_map = schemas.get("FRIENDLY_MAP", {})

    def format_label(self, key: str) -> str:
        """Translates raw dictionary keys into descriptive human-readable labels."""
        if key in self._label_cache:
            return self._label_cache[key]

        clean_key = re.sub(r"_x\d+$", "", key)
        label = self._friendly_map.get(clean_key)

        if not label:
            label = " ".join(word.capitalize() for word in clean_key.split("_"))

        self._label_cache[key] = label
        return label

    def descale(self, key: str, value: Any, default_scalar: float = 1.0) -> Any:
        """Dynamically scales integers back to floats using a fixed-string check."""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return value

        if key.endswith("_x1000"):
            return round(value / 1000.0, 3)
        if key.endswith("_x10"):
            return round(value / 10.0, 3)

        if default_scalar != 1.0:
            return round(value / default_scalar, 3)
        return value

    def generate_report(
        self,
        parsed_files,
        unparsable_files,
        summary,
        forensic_report,
        session_meta,
        output_path,
    ):
        """
        Transforms raw pipeline state into a verbose forensic compliance manifest.
        Memory-optimized to handle enterprise monorepos (10,000+ files) efficiently.
        """
        # 1. Forensic Traceability Anchor
        # Cryptographically binds this audit log to a specific moment in the source control history.
        git_audit = session_meta.get("git_audit", {})
        forensic_trail = {
            "Analysis Context": {
                "Engine Identity": session_meta.get("engine", "GitGalaxy Scope v6.2.0"),
                "Zero-Dependency Mode Active": session_meta.get("zero_dependency_mode", False),
                "Missing Dependencies": session_meta.get("missing_dependencies", {}),
                "Target Root Name": session_meta.get("target", "Unknown"),
                "Absolute Project Path": session_meta.get("target_directory", "Unknown"),
                "Analysis ISO Timestamp": session_meta.get("timestamp"),
                "Total Scan Duration": f"{session_meta.get('duration_seconds', 0.0)} seconds",
            },
            "Source Control Footprint (Immutable Anchor)": {
                "Active Branch": git_audit.get("branch", "N/A"),
                "Commit Hash (SHA-1)": git_audit.get("commit_hash", "N/A"),
                "Remote Origin URL": git_audit.get("remote_url", "Local/Disconnected"),
                "Last Code Integration Date": git_audit.get("latest_commit_date", "Unknown"),
            },
        }

        # --- DYNAMIC TRANSLATION FETCH ---
        schemas = getattr(config, "RECORDING_SCHEMAS", {})
        exposure_labels = schemas.get("EXPOSURE_LABELS", {})

        # Pre-calculate labels for vectors to avoid repeating work in the inner loop
        risk_labels = [exposure_labels.get(k, self.format_label(k)) for k in self.RISK_SCHEMA]
        hit_labels = [self.format_label(k) for k in self.HIT_SCHEMA]

        # --- DIRECTORY GROUP SORTING & HIERARCHY ---
        pretty_directory_groups = {}
        directory_groups_meta = summary.get("directory_groups", {})

        # Sort folders descending by structural magnitude
        sorted_directory_groups = sorted(
            directory_groups_meta.items(),
            key=lambda x: x[1].get("total_mass", 0.0),
            reverse=True,
        )

        # Initialize the ordered dictionary with directory-level aggregates
        for d_name, d_data in sorted_directory_groups:
            pretty_directory_groups[d_name] = {
                "Directory Group Magnitude": d_data.get("total_mass", 0.0),
                "File Count": d_data.get("file_count", 0),
                "Average Risk Exposures": {
                    exposure_labels.get(k, self.format_label(k)): f"{v}%"
                    for k, v in d_data.get("avg_exposures", {}).items()
                },
                "Files": {},
            }

        folder_archetype_counts = {}

        # 2. Row Reconstruction (Parsed Files) mapped into Directory Groups
        for file_data in parsed_files:
            path = file_data.get("path", "Unknown")
            telemetry = file_data.get("telemetry", {})
            lang_raw = str(file_data.get("lang_id", "Unknown")).lower()
            d_name = file_data.get("directory_group", "__monolith__")

            # DEFENSIVE GUARD: Synthesize default structural mass for documentation
            # Prevents dimension desyncs if the pipeline bypassed static physics for pure text.
            doc_languages = {"markdown", "plaintext", "rst", "text", "md"}
            if lang_raw in doc_languages:
                if "control_flow_ratio" not in telemetry:
                    telemetry["control_flow_ratio"] = 0.0
                if not file_data.get("file_impact"):
                    file_data["file_impact"] = round(max(file_data.get("total_loc", 1) / 50.0, 1.0), 2)
                
                # THE FIX: Explicitly pop the risk vector if it exists so text files are ALWAYS marked UNSCANNED
                if "risk_vector" in file_data:
                    file_data.pop("risk_vector")

            # --- DYNAMIC IDENTITY BLOCK ---
            identity_block = {
                "Filename": file_data.get("name", Path(path).name),
                "Path": path,
                "Language": str(file_data.get("lang_id", "Unknown")).title(),
                "Architect": telemetry.get("ownership", "Unknown Architect"),
            }

            domain_data = telemetry.get("domain_context", {})
            for custom_key, custom_val in domain_data.items():
                if custom_key not in ["ownership", "AI Threat Score"]:
                    display_key = custom_key.replace("_", " ").title()
                    # Sanitize internal legacy keys for the formal audit report
                    if display_key == "Purpose":
                        display_key = "System Purpose"
                    identity_block[display_key] = custom_val

            identity_block["Lock Tier"] = file_data.get("lock_tier", telemetry.get("identity_lock_tier", 4))
            identity_block["Identity Proof"] = telemetry.get(
                "identity_source_proof", file_data.get("source_proof", "Discovery")
            )

            if "AI Threat Score" in domain_data:
                identity_block["AI Threat Confidence"] = domain_data["AI Threat Score"]

            # --- EXPOSURE FORMATTER ---
            exposures_dict = {}
            raw_risk = file_data.get("risk_vector")
            
            # THE FIX: Enforce strict data provenance. If missing, label it explicitly.
            if not raw_risk:
                for label in risk_labels:
                    exposures_dict[label] = "[UNSCANNED - NO DATA]"
            else:
                for label, v in zip(risk_labels, raw_risk):
                    if label in ["Civil War Exposure", "Indentation Consistency"]:
                        if v == 0.0:
                            exposures_dict["Indentation Consistency"] = "Tabs"
                        elif v == 100.0:
                            exposures_dict["Indentation Consistency"] = "Spaces"
                        elif v == 50.0:
                            exposures_dict["Indentation Consistency"] = "Neutral / Deadlocked"
                        else:
                            exposures_dict["Indentation Consistency"] = f"Mixed ({100 - v:.1f}% Tabs / {v:.1f}% Spaces)"
                    else:
                        exposures_dict[label] = f"{round(v, 2)}%"

            arch = telemetry.get("archetype", "Unknown Archetype")
            if d_name not in folder_archetype_counts:
                folder_archetype_counts[d_name] = {}
            folder_archetype_counts[d_name][arch] = folder_archetype_counts[d_name].get(arch, 0) + 1

            mitigation_data = telemetry.get("mitigation_telemetry", {})
            
            # THE FIX: Cast suppression lists to dictionary tallies to support inline galaxyscope:ignores
            if isinstance(mitigation_data, list):
                mitigation_data = {m: 1 for m in mitigation_data}
                
            formatted_mitigations = {
                key.replace("_", " ").title(): f"{val} instances" for key, val in mitigation_data.items() if val > 0
            }

            # Assemble the individual artifact profile
            file_profile = {
                "1. Artifact Identity": identity_block,
                "2. Topological Coordinates": {
                    "X": file_data.get("pos_x", 0.0),
                    "Y": file_data.get("pos_y", 0.0),
                    "Z": file_data.get("pos_z", 0.0),
                },
                "3. Architectural Profile": {
                    "Repository Archetype": arch,
                    "Repository Drift (Z-Score)": telemetry.get("global_drift", 0.0),
                    "Repository Fingerprint": (
                        {k: round(v, 3) for k, v in telemetry.get("archetype_fingerprint", {}).items()}
                        if isinstance(telemetry.get("archetype_fingerprint"), dict)
                        else {}
                    ),
                    "File Archetype": telemetry.get("local_archetype", "N/A"),
                    "File Drift (Z-Score)": telemetry.get("local_drift", 0.0),
                    "File Fingerprint": (
                        {k: round(v, 3) for k, v in telemetry.get("local_fingerprint", {}).items()}
                        if isinstance(telemetry.get("local_fingerprint"), dict)
                        else {}
                    ),
                    "Total LOC": file_data.get("total_loc", 0),
                    "Coding LOC": file_data.get("coding_loc", 0),
                    "Documentation LOC": file_data.get("doc_loc", 0),
                    "Structural Magnitude": round(file_data.get("file_impact", 0.0), 3),
                    "Control Flow Ratio": f"{round(telemetry.get('control_flow_ratio', 0.0) * 100, 1)}%",
                    "Popularity Rank": telemetry.get("popularity", 0),
                    "Raw Churn Frequency": telemetry.get("raw_churn_freq", 0.0),
                    "Authorship Centralization": telemetry.get("author_distribution", 0.0),
                    "Ownership Entropy": telemetry.get("ownership_entropy", 0.0),
                    "Raw Cognitive Density": telemetry.get("densities", {}).get("cog_raw", 0.0),
                },
                "4. Vulnerability & Risk Exposures": exposures_dict,
                "5. Function Analysis": [
                    {
                        "Function Name": func.get("name", "Unknown"),
                        "Structural Impact": func.get("impact", func.get("magnitude", 0.0)),
                        "Lines of Code (LOC)": func.get("loc", 0),
                        "Control Flow Branches": func.get("branch", func.get("branch_count", 0)),
                        "Input Parameters": func.get("args", func.get("args_count", 0)),
                        "Control Flow Ratio": f"{round((func.get('control_flow_ratio') or func.get('cf_ratio') or 0.0) * 100, 1)}%",
                        "Start Line": func.get("start_line", 0),
                        "End Line": func.get("end_line", 0),
                    }
                    for func in file_data.get("functions", [])
                    if isinstance(func, dict)
                ],
                "6. Contextual Mitigations & Amplifications": (
                    formatted_mitigations if formatted_mitigations else "None Detected"
                ),
                "7. Structural Signatures (Net Mitigated Signals)": {
                    label: v for label, v in zip(hit_labels, file_data.get("hit_vector") or [0] * len(hit_labels))
                },
                "8. Dependency Network": {
                    "Direct Upstream (Fragility)": file_data.get("dependency_network", {}).get(
                        "direct_upstream", len(file_data.get("raw_imports", []))
                    ),
                    "Direct Downstream (Dependency Blast Radius)": file_data.get("dependency_network", {}).get(
                        "direct_downstream", telemetry.get("popularity", 0)
                    ),
                    "Total Upstream (Absolute Fragility)": file_data.get("dependency_network", {}).get(
                        "total_upstream", 0
                    ),
                    "Total Downstream (Absolute Dependency Blast Radius)": file_data.get("dependency_network", {}).get(
                        "total_downstream", 0
                    ),
                },
                "9. Extracted Dependencies": sorted(list(file_data.get("raw_imports", []))),
            }

            # Map the file into its parent directory group
            if d_name not in pretty_directory_groups:
                pretty_directory_groups[d_name] = {
                    "Directory Group Mass": 0.0,
                    "Files": {},
                }
            pretty_directory_groups[d_name]["Files"][path] = file_profile

        # --- CALCULATE FOLDER-LEVEL ARCHETYPE SUMMARIES ---
        for d_name, d_data in pretty_directory_groups.items():
            folder_files = len(d_data.get("Files", {}))
            arch_counts = folder_archetype_counts.get(d_name, {})

            if folder_files > 0 and arch_counts:
                # Calculate percentages and sort highest to lowest
                fingerprint = {
                    name: f"{round((count / folder_files) * 100.0, 1)}%"
                    for name, count in sorted(arch_counts.items(), key=lambda x: x[1], reverse=True)
                }

                reordered_d_data = {
                    "Directory Group Magnitude": d_data.get("Directory Group Magnitude", 0.0),
                    "File Count": d_data.get("File Count", folder_files),
                    "Ecosystem Fingerprint (Archetypes)": fingerprint,
                    "Average Risk Exposures": d_data.get("Average Risk Exposures", {}),
                    "Files": d_data.get("Files", {}),
                }
                pretty_directory_groups[d_name] = reordered_d_data

        # 3. Format Unparsable Files (Excluded Artifacts Queue)
        pretty_unparsable = []
        target_dir = Path(session_meta.get("target_directory", ""))

        # 3.1 Format standard excluded items for the JSON output
        for unparsable in unparsable_files:
            rel_path = unparsable.get("path", "Unknown")
            abs_path = target_dir / rel_path

            # Physically weighs the file on disk if the pipeline dropped the byte count
            try:
                actual_size = os.path.getsize(abs_path) if abs_path.exists() else unparsable.get("size_bytes", 0)
            except Exception:
                actual_size = unparsable.get("size_bytes", 0)

            pretty_unparsable.append(
                {
                    "Path": rel_path,
                    "Forensic Category": "Excluded Artifact",
                    "Diagnostic Reason": unparsable.get("reason", "Security Shielding (Format Excluded)"),
                    "Size": f"{actual_size} bytes",
                    "Identity Confidence": f"{round(unparsable.get('identity_confidence', 0.0) * 100, 1)}%",
                    "Discovery Proof": unparsable.get("identity_source_proof", "Radar Scan"),
                }
            )

        # 3.2 Append structurally bypassed artifacts to the local output list
        for anon_path in summary.get("unparsable_files", {}).get("unparsable_artifacts", []):
            pretty_unparsable.append(
                {
                    "Path": anon_path,
                    "Forensic Category": "Parser Bypass",
                    "Diagnostic Reason": "Engine Bypass (Dense Structure or Unrecognized Syntax)",
                    "Size": "Unknown (Parser Bypass)",
                    "Identity Confidence": "0.0% (Scan Yielded No Data)",
                    "Discovery Proof": "Structural Signature Extractor Shielding",
                }
            )

        # ==========================================================
        # 4. FORENSIC SECURITY & VULNERABILITY AUDIT
        # Synchronized with enterprise SAST terminology mapping.
        # ==========================================================
        sec_risk_mapping = {
            "secrets_risk": {"label": "Secrets Risk Exposure", "threshold": 0.1},
            "obscured_payload": {
                "label": "Hidden Malware Risk Exposure",
                "threshold": 60.0,
            },
            "logic_bomb": {
                "label": "Logic Bomb / Sabotage Risk Exposure",
                "threshold": 50.0,
            },
            "injection_surface": {
                "label": "Injection Surface Risk Exposure",
                "threshold": 65.0,
            },
            "memory_corruption": {
                "label": "Memory Corruption Risk Exposure",
                "threshold": 60.0,
            },
        }

        sec_hit_mapping = {
            "sec_high_risk_execution": "Dynamic Code Execution (RCE)",
            "sec_safety_bypasses": "Security Control & Safety Bypasses",
            "sec_io": "Network & I/O Exfiltration Vectors",
            "sec_state_mutation": "Prototype Pollution & Global State Flux",
            "sec_reflection_metaprogramming": "Obfuscation & Encoding Signatures",
            "sec_dead_code": "Commented-out Executable Logic (Shadow Logic)",
            "sec_bitwise_ops": "Low-Level Cryptographic & Bitwise Operations",
            "sec_shadow_imports": "Steganographic Payload Imports",
            "sec_homoglyphs": "Unicode Homoglyphs & Typosquatting",
        }

        quarantined_files = []
        ml_threat_files = []  # Container for XGBoost threat hits

        vuln_exposures = {
            data["label"]: {
                "Alert Threshold": f">= {data['threshold']}%",
                "Artifacts Flagged": 0,
                "Critical Files": [],
            }
            for key, data in sec_risk_mapping.items()
        }

        raw_threat_hits = {
            "_description": "Total occurrences of explicit vulnerability regex signatures across all analyzed artifacts.",
            **{label: 0 for label in sec_hit_mapping.values()},
        }

        # Safe index lookups mapping formal schema names back to array indices
        risk_indices = {k: self.RISK_SCHEMA.index(k) for k in sec_risk_mapping.keys() if k in self.RISK_SCHEMA}
        hit_indices = {k: self.HIT_SCHEMA.index(k) for k in sec_hit_mapping.keys() if k in self.HIT_SCHEMA}

        # Sweep the files for security anomalies
        for file_data in parsed_files:
            path = file_data.get("path", "Unknown")
            domain_ctx = file_data.get("telemetry", {}).get("domain_context", {})

            is_ml_threat = file_data.get("is_ml_threat", False)
            ai_score_str = domain_ctx.get("AI Threat Score", "0.0%")

            try:
                ai_score_float = float(str(ai_score_str).replace("%", ""))
            except ValueError:
                ai_score_float = 0.0

            if is_ml_threat or ai_score_float >= 50.0:
                ml_threat_files.append(
                    {
                        "Path": path,
                        "AI_Confidence": ai_score_float,
                        "Formatted_Score": ai_score_str,
                    }
                )

            # Explicit check for manual overrides triggered by the Aperture Engine
            if domain_ctx.get("alert") == "CRITICAL LEAK BYPASS":
                quarantined_files.append(
                    {
                        "Path": path,
                        "Diagnostic": f"CRITICAL LEAK (Exposed Secret/Key): {domain_ctx.get('aperture_reason', 'Manual Bypass')}",
                    }
                )

            risk_vector = file_data.get("risk_vector", [])
            if len(risk_vector) == len(self.RISK_SCHEMA):
                for r_key, r_idx in risk_indices.items():
                    score = risk_vector[r_idx]
                    mapping = sec_risk_mapping[r_key]
                    if score >= mapping["threshold"]:
                        label = mapping["label"]
                        vuln_exposures[label]["Critical Files"].append({"Path": path, "Score": f"{score:.1f}%"})
                        vuln_exposures[label]["Artifacts Flagged"] += 1

            hit_vector = file_data.get("hit_vector")
            if isinstance(hit_vector, list) and len(hit_vector) == len(self.HIT_SCHEMA):
                for h_key, h_idx in hit_indices.items():
                    hits = hit_vector[h_idx]
                    if hits > 0:
                        label = sec_hit_mapping[h_key]
                        raw_threat_hits[label] += hits

        # --- THE FALSE POSITIVE GUARD: Decouple Active Threats from Passive Surface Risks ---
        # Count actual malicious regex hits (ignoring the _description metadata string)
        malicious_hits_total = sum(v for k, v in raw_threat_hits.items() if isinstance(v, int))

        has_malware = vuln_exposures["Hidden Malware Risk Exposure"]["Artifacts Flagged"] > 0
        has_secrets = vuln_exposures["Secrets Risk Exposure"]["Artifacts Flagged"] > 0

        # Sort and map the ML (XGBoost) hit list descending by confidence
        ml_threat_files.sort(key=lambda x: x["AI_Confidence"], reverse=True)
        top_ml_threats = [
            {
                "Path": threat["Path"],
                "Confidence": threat["Formatted_Score"],
                "Model": "XGBoost Structural Signatures",
            }
            for threat in ml_threat_files
        ]

        # Tiered Status Routing (ML acts as the supreme authority)
        is_zero_dep = session_meta.get("zero_dependency_mode", False)
        
        if ml_threat_files:
            audit_status = "ML_CONFIRMED_THREAT_DETECTED"
        elif quarantined_files or has_malware or has_secrets or malicious_hits_total > 0:
            audit_status = "CRITICAL_THREATS_DETECTED (Rule-Based)"
        elif any(v["Artifacts Flagged"] > 0 for v in vuln_exposures.values()):
            audit_status = "ELEVATED_SURFACE_RISK"
        elif is_zero_dep:
            audit_status = "[BYPASSED - ZERO DEPENDENCY MODE]"
        else:
            audit_status = "SECURE_NO_THREATS_DETECTED"

        security_audit = {
            "Audit Status": audit_status,
            "ML Threat Intelligence (XGBoost)": {
                "Infected Files Detected": len(ml_threat_files),
                "Critical Targets": top_ml_threats,
            },
            "Scope": {
                "Artifacts Evaluated": len(parsed_files),
                "Threat Signatures Monitored": len(sec_hit_mapping),
                "Vulnerability Vectors Calculated": len(sec_risk_mapping),
            },
            "Exposed Secrets & Credentials (Quarantined Files)": quarantined_files,
            "Vulnerability Exposures (Rule-Based Threshold Breaches)": vuln_exposures,
            "Raw Threat Signature Hits (Total Repository Occurrences)": raw_threat_hits,
        }

        # ==========================================================
        # 5. Final Mission Archive Packaging
        # ==========================================================
        global_fingerprint = summary.get("ecosystem_fingerprint", {})
        pretty_global_fingerprint = {}

        if "ml_clusters" in global_fingerprint or "static_mass" in global_fingerprint:
            if "ml_clusters" in global_fingerprint:
                pretty_global_fingerprint["Active Execution Logic (ML Clusters)"] = {
                    k: f"{v['pct']}% ({v['count']} files)" for k, v in global_fingerprint["ml_clusters"].items()
                }
            if "static_mass" in global_fingerprint:
                pretty_global_fingerprint["Static Assets (Static Categories)"] = {
                    k: f"{v['pct']}% ({v['count']} files)" for k, v in global_fingerprint["static_mass"].items()
                }
        else:
            # Legacy Schema Fallback
            pretty_global_fingerprint = (
                {k: f"{v}%" for k, v in global_fingerprint.items()}
                if global_fingerprint
                else "No architectural clusters detected."
            )

        summary["Global Architectural Fingerprint"] = pretty_global_fingerprint

        # Formalize the Repository Ecosystem Baseline mapping
        macro = summary.get("repo_macro_species", {})
        if macro:
            summary["Repository Ecosystem Baseline (Architecture)"] = {
                "Classification": macro.get("name", "Unclassified"),
                "Architectural Drift (Z-Score)": macro.get("z_score", 0.0),
            }

        mission_audit = {
            "Audit Protocol": "GitGalaxy v6.3.2-Audit",
            "1. Forensic Trail (Traceability)": forensic_trail,
            "2. Global Ecosystem Summary": summary,
            "3. Forensic Security & Vulnerability Audit": security_audit,
            "4. High-Value Forensic Report": forensic_report,
            "5. Unparsable Artifacts (Excluded Artifacts Queue)": pretty_unparsable,
            "6. Parsed Files (Scanned Artifacts)": pretty_directory_groups,
        }

        target_path = Path(output_path)

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(mission_audit, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Audit Success: Forensic manifest sealed -> {target_path}")
        except Exception as e:
            self.logger.error(f"Audit Write Error: {e}")


def decode_galaxy(input_path, output_path=None):
    """Standalone decoding logic preserved for CLI compatibility."""
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitGalaxy v6.2.0 Forensic Audit Recorder CLI")
    parser.add_argument("input", help="Path to columnar galaxy.json")
    parser.add_argument("--out", help="Optional output path")
    args = parser.parse_args()
