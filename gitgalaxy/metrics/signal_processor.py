# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_llm_hooks


import math
import logging
import re
import statistics
from typing import Dict, Any, List, Optional, Tuple
from gitgalaxy.standards import analysis_lens as config
from gitgalaxy.standards import analysis_lens

# ==============================================================================
# GitGalaxy Phase 4: Signal Processor (The Structural Signature Analysis Engine)
# Strategy v6.2.0 Protocol: Temporal Normalization & Universal Exposure
# ==============================================================================


class SignalProcessor:
    """
    The GitGalaxy Signal Processor.

    PURPOSE: Converts raw logic counts and temporal telemetry into "Exposure Vectors"
    and generates high-fidelity forensic reports identifying structural risks.

    ARCHITECTURE (v6.2.0):
    1. Temporal Consolidation: Math formulas for Churn and Stability now live here.
    2. Two-Pass Normalization: Auto-scales Churn based on the galaxy's global maximum.
    3. Sigmoid Armor: `try/except OverflowError` guarantees survival on extreme file densities.
    4. Flexible Risk Schema: Vector indexing is dynamic, preventing offset bugs.
    """

    # ==========================================================================
    # SCHEMA BINDING (Single Source of Truth)
    # Dynamically inherited from gitgalaxy_standards_v011.py
    # ==========================================================================

    # The 60-Point Spectral Sync (Standard + Security Lens)
    SIGNAL_SCHEMA = config.RECORDING_SCHEMAS.get("SIGNAL_SCHEMA", [])

    # The 18-Point Risk Exposure Schema
    RISK_SCHEMA = config.RECORDING_SCHEMAS.get("RISK_SCHEMA", [])

    def __init__(
        self,
        aperture_config: Optional[Dict[str, Any]] = None,
        parent_logger: Optional[logging.Logger] = None,
    ):
        """Initializes the signal processing engine with forensic constants and telemetry."""
        if parent_logger:
            self.logger = parent_logger.getChild("processing")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("processing")
            self.logger.setLevel(logging.INFO)

        self.logger.debug("Initializing Universal Exposure Framework...")
        self.config = aperture_config or {}

        # ======================================================================
        # 🧠 FETCH PRE-TRAINED INFERENCE MODELS (Global & Local)
        # ======================================================================
        # ---> NEW (DYNAMIC) <---
        inference_model = getattr(config, "GENERAL_FILE_INFERENCE_MODEL", {})
        self.SCALER_MEDIANS = inference_model.get("SCALER_MEDIANS", [0.0] * 100)  # Safe fallback size
        self.SCALER_IQRS = inference_model.get("SCALER_IQRS", [1.0] * 100)

        # Dynamically grab whichever ARCHETYPES_K key exists (e.g. ARCHETYPES_K9)
        arch_key = next((k for k in inference_model.keys() if k.startswith("ARCHETYPES_K")), None)
        self.GLOBAL_ARCHETYPES = inference_model.get(arch_key, {}) if arch_key else {}

        # ---> NEW: Fetch Language-Specific Clustering Models <---
        self.LANGUAGE_INFERENCE_MODELS = getattr(config, "SPECIFIC_FILE_INFERENCE_MODEL", {})

        # Fetch Structural Constants
        physics = getattr(config, "ENGINE_CONSTANTS", {})
        self.WEIGHT_RISK = physics.get("WEIGHT_RISK", 2.5)
        self.WEIGHT_DEFENSE = physics.get("WEIGHT_DEFENSE", 1.0)
        self.TIER_VARS = physics.get(
            "TIER_VARS",
            {
                "tier1": {"fc": 1.0, "irc": 0},
                "tier2": {"fc": 0.85, "irc": 2},
                "tier3": {"fc": 0.60, "irc": 5},
            },
        )
        self.MASSIVE_FILE_THRESHOLD = physics.get("MASSIVE_FILE_THRESHOLD", 300)
        self.TESTING_RISK_FLOOR = physics.get("TESTING_RISK_FLOOR", 15.0)

        # Fetch Path Modifiers & Asset Masks
        self.path_modifiers = getattr(config, "PATH_MODIFIERS", {})
        self.asset_masks = getattr(config, "ASSET_MASKS", {})
        self.risk_tuning = getattr(config, "RISK_EQUATION_TUNING", {})
        self.is_paranoid = self.config.get("PARANOID_MODE", False)

        # ======================================================================
        # THE CONTEXT VS. ENTITY MATRIX (Domain Ontologies)
        # ======================================================================
        # We now fetch this dynamically from gitgalaxy_standards_v1.py instead of hardcoding it!
        security_profiles = getattr(config, "LANGUAGE_SECURITY_PROFILES", {})
        self.ECOSYSTEMS = security_profiles.get("ECOSYSTEMS", {})
        self.NATIVE_WEIGHTS = security_profiles.get("NATIVE_WEIGHTS", {})

        # Fetch ECOSYSTEM_MISMATCH_WEIGHTS dynamically, with a fallback to the hardcoded dictionary
        self.ECOSYSTEM_MISMATCH_WEIGHTS = security_profiles.get(
            "ECOSYSTEM_MISMATCH_WEIGHTS",
            {
                "systems_in_web": {
                    "memory": 5.0,
                    "logic_bomb": 3.0,
                },  # C code hiding in a JS app = Trojan
                "infra_in_web": {"logic_bomb": 4.0},  # Shell script hiding in a JS app = Backdoor
                "web_in_systems": {"state_mutation": 3.0},  # JS embedded in C firmware = Bizarre architecture
            },
        )

        # ---> NEW: Fetch the Archetype Matrix
        self.CONTEXT_VIOLATION_MATRIX = security_profiles.get("CONTEXT_VIOLATION_MATRIX", {})

        self.logger.info("Signal Processor Online | Context-Aware Risk Schema & ML Archetypes loaded.")

    def _classify_archetype(
        self, scaled_vector: List[float], archetypes_dict: Dict[str, List[float]]
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Dynamically calculates the Euclidean Distance for any provided K-Means dictionary.
        Returns: Best Match Name, Minimum Distance (Drift), Full Feature Fingerprint.
        """
        fingerprint = {}
        best_match = "Unknown Archetype"
        min_dist = float("inf")

        if not archetypes_dict:
            return best_match, 0.0, fingerprint

        for arch_name, centroid_vector in archetypes_dict.items():
            dist_sq = 0.0

            for i in range(min(len(scaled_vector), len(centroid_vector))):
                dist_sq += (scaled_vector[i] - centroid_vector[i]) ** 2

            distance = math.sqrt(dist_sq)
            fingerprint[arch_name] = round(distance, 3)

            if distance < min_dist:
                min_dist = distance
                best_match = arch_name

        return best_match, round(min_dist, 3), fingerprint

    def _get_context_multipliers(self, file_lang: str, folder_lang: str) -> Dict[str, float]:
        """
        Calculates risk multipliers by comparing an asset's language to its directory environment.
        Detects architectural boundary violations and embedded payloads (e.g., C code in a JS directory).
        """
        # Default multipliers if no specific context rules apply
        multipliers = {"memory": 1.0, "logic_bomb": 1.0, "state_mutation": 1.0, "injection": 1.0}

        file_lang = file_lang.lower()
        folder_lang = folder_lang.lower() if folder_lang else file_lang

        # Determine the ecosystem of the specific File
        file_eco = "backend"  # Default fallback
        for eco, langs in self.ECOSYSTEMS.items():
            if file_lang in langs:
                file_eco = eco
                break

        # Determine the ecosystem of the surrounding Folder
        folder_eco = "backend"
        for eco, langs in self.ECOSYSTEMS.items():
            if folder_lang in langs:
                folder_eco = eco
                break

        # SCENARIO 1: The Entity matches the Context (Native)
        if file_eco == folder_eco:
            return self.NATIVE_WEIGHTS.get(file_eco, multipliers)

        # SCENARIO 2: The Entity is an Alien (Context Mismatch)
        alien_key = f"{file_eco}_in_{folder_eco}"
        alien_penalties = self.ECOSYSTEM_MISMATCH_WEIGHTS.get(alien_key, {})

        # Apply standard weights of the file, but overwrite with severe mismatch penalties
        base_weights = self.NATIVE_WEIGHTS.get(file_eco, multipliers).copy()
        base_weights.update(alien_penalties)

        if alien_penalties:
            self.logger.debug(
                f"🚨 CONTEXTUAL MISMATCH DETECTED: {file_lang} asset embedded in a {folder_eco} domain. Applying out-of-bounds security penalties: {alien_penalties}"
            )

        return base_weights

    def _calculate_silo_risk(self, authors: dict) -> float:
        """
        Calculates the Authorship Centralization risk of a file.
        100% = A single developer wrote the entire file (High Centralization).
        0% = Perfectly distributed across multiple developers (Low Centralization).
        """
        if not authors:
            return 0.0

        total_commits = sum(authors.values())
        if total_commits == 0:
            return 0.0

        dominant_commits = max(authors.values())
        ownership_ratio = dominant_commits / total_commits

        return round(ownership_ratio * 100.0, 1)

    def calculate_risk_vector(
        self,
        meta: Dict[str, Any],
        raw_signals: Dict[str, int],
        umbrella_bonus: float = 0.0,
    ) -> Dict[str, Any]:
        """Calculates risk exposure, temporal analysis, and per-file structural impact."""
        rel_path = meta.get("path", "unknown")
        loc = 1  # Safe fallback for the except block

        try:
            try:
                loc = max(int(meta.get("coding_loc", 1)), 1)
            except (ValueError, TypeError):
                loc = 1

            try:
                total_loc = max(int(meta.get("total_loc", loc)), 1)
            except (ValueError, TypeError):
                total_loc = loc

            try:
                doc_lines = int(meta.get("doc_loc", 0))
            except (ValueError, TypeError):
                doc_lines = 0

            lang_id = meta.get("lang_id", "undeterminable")

            import os

            filename = os.path.basename(rel_path).lower()
            ext = f".{filename.split('.')[-1]}" if "." in filename else ""
            ghost_meta = meta.get("metadata", {})

            # ==================================================================
            # EXTENSION SPOOFING DETECTOR
            # Punishes files claiming to be inert data but evaluated as executable code
            # ==================================================================
            if ext:
                inert_disguises = {
                    ".txt",
                    ".md",
                    ".csv",
                    ".json",
                    ".yaml",
                    ".yml",
                    ".xml",
                    ".log",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".mp4",
                }
                executable_langs = {
                    "shell",
                    "python",
                    "javascript",
                    "typescript",
                    "ruby",
                    "perl",
                    "php",
                    "c",
                    "cpp",
                    "rust",
                    "go",
                    "java",
                    "powershell",
                }

                if ext in inert_disguises and lang_id.lower() in executable_langs:
                    self.logger.warning(
                        f"🚨 SPOOFING DETECTED: {rel_path} claims to be {ext} but executed as {lang_id}!"
                    )
                    raw_signals["sec_extension_mismatch"] = 1

            # ==================================================================
            # CRITICAL SECRETS EXPOSURE OVERRIDE
            # Treat exposed keyfiles as structural vulnerabilities, skipping math
            # ==================================================================
            aperture_cfg = getattr(config, "APERTURE_CONFIG", {})
            secrets_exts = aperture_cfg.get("SECRETS_EXTENSIONS", set())
            secrets_exact = aperture_cfg.get("SECRETS_EXACT", set())
            aperture_reason = ghost_meta.get("aperture_reason", "")

            is_critical_leak = "CRITICAL LEAK" in aperture_reason or ext in secrets_exts or filename in secrets_exact

            if is_critical_leak:
                temporal_data = meta.get("temporal_telemetry", {})
                _, raw_churn_freq = self._calc_raw_temporal_signals(temporal_data)
                authors_map = meta.get("authors", {})

                dominant_author = (
                    max(authors_map, key=authors_map.get)
                    if authors_map
                    else ghost_meta.get("ownership", "Unknown Architect")
                )

                # 1. Base array of zeroes
                blanket_risk_vector = [0.0] * len(self.RISK_SCHEMA)

                # 2. Spike Hardcoded Secrets Exposure to Maximum
                if "secrets_risk" in self.RISK_SCHEMA:
                    secrets_idx = self.RISK_SCHEMA.index("secrets_risk")
                    blanket_risk_vector[secrets_idx] = 100.0

                # 3. Retain Churn so we know if the secret is actively being modified
                if "churn" in self.RISK_SCHEMA:
                    churn_idx = self.RISK_SCHEMA.index("churn")
                    blanket_risk_vector[churn_idx] = min(raw_churn_freq * 10, 100.0)

                return {
                    "risk_vector": blanket_risk_vector,
                    "hit_vector": [0] * len(self.SIGNAL_SCHEMA),
                    "file_impact": 150.0,  # <-- FIX: Restored the 150.0 mass spike for critical leaks
                    "telemetry": {
                        "archetype": getattr(config, "STATIC_ARCHETYPES", {}).get(
                            "quarantine", "Static: Critical Contraband Leak"
                        ),
                        "control_flow_ratio": 0.0,
                        "ownership_entropy": 0.0,
                        "author_distribution": 0.0,
                        "ownership": dominant_author,
                        "domain_context": {
                            "alert": "CRITICAL LEAK BYPASS",
                            **ghost_meta,
                        },
                        "threat_locations": meta.get("threat_locations", {}),
                    },
                }

            # ==================================================================
            # OBFUSCATED / VENDOR ASSET OVERRIDE
            # ==================================================================
            is_minified = meta.get("is_minified", False)
            if is_minified:
                # 1. Zero out all standard architectural risks
                blanket_risk_vector = [0.0] * len(self.RISK_SCHEMA)

                # 2. Check for ANY malicious intent (eval, network fetching, etc.)
                intent_mass = (
                    raw_signals.get("sec_high_risk_execution", 0)
                    + raw_signals.get("sec_io", 0)
                    + raw_signals.get("sec_safety_bypasses", 0)
                )

                if intent_mass > 0:
                    self.logger.critical(f"🚨 OBFUSCATION DETECTED: {rel_path} contains obscured execution/IO!")
                    if "obscured_payload" in self.RISK_SCHEMA:
                        blanket_risk_vector[self.RISK_SCHEMA.index("obscured_payload")] = 100.0
                    if "logic_bomb" in self.RISK_SCHEMA:
                        blanket_risk_vector[self.RISK_SCHEMA.index("logic_bomb")] = 100.0
                    if "injection_surface" in self.RISK_SCHEMA:
                        blanket_risk_vector[self.RISK_SCHEMA.index("injection_surface")] = 100.0

                return {
                    "risk_vector": blanket_risk_vector,
                    "hit_vector": [raw_signals.get(k, 0) for k in self.SIGNAL_SCHEMA],
                    "file_impact": 1.0,  # Minified files don't carry architectural weight
                    "telemetry": {
                        "archetype": getattr(config, "STATIC_ARCHETYPES", {}).get(
                            "minified", "Static: Minified & Vendor Opaque Mass"
                        ),
                        "control_flow_ratio": 0.0,
                        "ownership_entropy": 0.0,
                        "author_distribution": 0.0,
                        "ownership": ghost_meta.get("ownership", "Unknown Architect"),
                        "domain_context": {
                            "alert": "MINIFIED VENDOR BYPASS",
                            **ghost_meta,
                        },
                        "threat_locations": meta.get("threat_locations", {}),
                    },
                }

            # ==================================================================
            # STATIC LITERATURE OVERRIDE
            # Treat pure literature as static structural assets, skipping logic math
            # ==================================================================
            doc_languages = self.asset_masks.get("DOCUMENTATION_LANGUAGES", {"markdown", "plaintext", "rst", "text"})

            if lang_id.lower() in doc_languages:
                temporal_data = meta.get("temporal_telemetry", {})
                _, raw_churn_freq = self._calc_raw_temporal_signals(temporal_data)
                authors_map = meta.get("authors", {})

                dominant_author = (
                    max(authors_map, key=authors_map.get)
                    if authors_map
                    else ghost_meta.get("ownership", "Unknown Architect")
                )

                blanket_risk_vector = [0.0] * len(self.RISK_SCHEMA)

                if "churn" in self.RISK_SCHEMA:
                    blanket_risk_vector[self.RISK_SCHEMA.index("churn")] = min(raw_churn_freq * 10, 100.0)
                if "documentation" in self.RISK_SCHEMA:
                    blanket_risk_vector[self.RISK_SCHEMA.index("documentation")] = 0.0  # <-- The Fix! 0% Risk.
                if "tabs_vs_spaces" in self.RISK_SCHEMA:
                    blanket_risk_vector[self.RISK_SCHEMA.index("tabs_vs_spaces")] = 50.0

                return {
                    "risk_vector": blanket_risk_vector,
                    "hit_vector": [0] * len(self.SIGNAL_SCHEMA),
                    "file_impact": round(max(total_loc / 50.0, 1.0), 2),
                    "telemetry": {
                        "archetype": getattr(config, "STATIC_ARCHETYPES", {}).get(
                            "literature", "Static: Literature & Documentation"
                        ),
                        "control_flow_ratio": 0.0,
                        "ownership_entropy": 0.0,  # <-- FIX: Documentation has no logic entropy
                        "author_distribution": 0.0,  # <-- FIX: Plaintext changelogs don't have Authorship Centralization risk
                        "ownership": dominant_author,
                        "domain_context": ghost_meta,
                        "threat_locations": meta.get("threat_locations", {}),
                    },
                }

            # ==================================================================
            # 1. ACTIVE SIGNAL PROCESSING ENGINE (For normal executable code)
            # ==================================================================
            tier = self._get_tier(lang_id)
            fc = self.TIER_VARS[tier]["fc"]
            irc = self.TIER_VARS[tier]["irc"]
            ot = self.TIER_VARS[tier].get("ot", 1.0)

            # Environmental Context (Path-based overrides)
            mp_map = self._get_locational_multipliers(rel_path)

            folder_lang = ghost_meta.get("folder_dominant_lang", lang_id)
            eco_mp = self._get_context_multipliers(lang_id, folder_lang)

            self.logger.debug(f"[{rel_path}] Structural Calc | Lang: {lang_id} (Fc: {fc:.2f}, Irc: {irc}, Ot: {ot:.2f})")
            
            hit_vector = [raw_signals.get(key, 0) for key in self.SIGNAL_SCHEMA]

            # ------------------------------------------------------------------
            # 1. TEMPORAL PRE-PROCESSING (Raw Extraction)
            # ------------------------------------------------------------------
            temporal_data = meta.get("temporal_telemetry", {})
            stability_score, raw_churn_freq = self._calc_raw_temporal_signals(temporal_data)

            # ------------------------------------------------------------------
            # 1.5 BUILD THE ML VECTOR & CLASSIFY ARCHETYPE
            # ------------------------------------------------------------------
            cfr = meta.get("control_flow_ratio", 0.0)

            # ---> NEW: THE ENCAPSULATION RATIO <---
            # How much of the file's data is safely locked inside functions?
            total_vars = raw_signals.get("core_var_decl", 0)
            global_vars = raw_signals.get("globals", 0)

            if total_vars == 0 and global_vars == 0:
                encapsulation_ratio = 1.0  # Safe by default if no state exists
            else:
                # 1.0 = Perfect (0 globals). 0.0 = Terrible (All globals).
                encapsulation_ratio = max(0.0, 1.0 - (global_vars / max(total_vars + global_vars, 1)))

            logic_loc = max(int(round(meta.get("coding_loc", 0) * cfr)), 1)
            safe_denom = max(logic_loc, meta.get("coding_loc", 1))

            # ---> START FUNCTION-LEVEL ML CLASSIFICATION <---
            functions = meta.get("functions", [])
            max_func_comp = 0
            avg_func_args = 0.0
            func_gini = 0.0
            max_big_o = 1
            max_db_complexity = 0

            func_ml_brain = getattr(analysis_lens, "GENERAL_FUNCTION_INFERENCE_MODEL", {})
            f_medians = func_ml_brain.get("SCALER_MEDIANS", [])
            f_iqrs = func_ml_brain.get("SCALER_IQRS", [])
            f_arch_key = next((k for k in func_ml_brain.keys() if k.startswith("ARCHETYPES_K")), None)
            f_centroids = func_ml_brain.get(f_arch_key, {}) if f_arch_key else {}

            # Bulletproof fallback names if the model dictionary forgets them
            f_names = func_ml_brain.get(
                "cluster_names",
                [
                    "Utility/Helper",
                    "Data Router",
                    "State Mutator",
                    "God Function",
                    "Math Engine",
                    "I/O Bridge",
                    "Constructor",
                    "Callback/Event",
                    "API Endpoint",
                    "Validator",
                    "Renderer",
                    "Loop Processor",
                ],
            )

            # ---> NEW: DIAGNOSTIC ML LOGGING <---
            if functions and not f_centroids:
                self.logger.warning(
                    f"⚠️ FUNCTION ML SILENT BYPASS: Brain loaded? {bool(func_ml_brain)} | Centroids: {len(f_centroids)} | Arch Key: {f_arch_key}"
                )

            # Initialize has_recursion before the if block
            has_recursion = False

            if functions:
                complexities = [f.get("branch", 0) for f in functions]
                max_func_comp = max(complexities)
                avg_func_args = sum([f.get("args", 0) for f in functions]) / len(functions)
                max_big_o = max([f.get("big_o_depth", 1) for f in functions])
                max_db_complexity = max([f.get("db_complexity", 0) for f in functions])
                has_recursion = any([f.get("is_recursive", False) for f in functions])

                # 1. Z-Scores Mathematics
                func_count = len(functions)
                mean_comp = statistics.mean(complexities) if func_count > 0 else 0.0
                std_comp = statistics.pstdev(complexities) if func_count > 1 else 0.0

                for s in functions:
                    # Apply Z-Score directly to RAM dictionary
                    c = s.get("branch", 0)
                    z_val = (c - mean_comp) / std_comp if std_comp > 0 else 0.0
                    s["z_score"] = round(z_val, 3)

                    # 2. Archetype Euclidean Classification
                    s["archetype"] = "Unclassified"
                    if f_centroids:  # <--- REMOVED f_features STRICT REQUIREMENT
                        raw_vec = [
                            float(s.get("branch", 0)),
                            float(s.get("loc", 0)),
                            float(s.get("args", 0)),
                            float(s.get("keyword_density", 0.0)),
                            float(s.get("control_flow_ratio", s.get("cf_ratio", 0.0))),
                        ]

                        scaled_vec = []
                        for i, val in enumerate(raw_vec):
                            med = f_medians[i] if i < len(f_medians) else 0.0
                            iqr = f_iqrs[i] if i < len(f_iqrs) and f_iqrs[i] > 0 else 1.0
                            scaled_vec.append((val - med) / iqr)

                        min_dist = float("inf")
                        for c_key, centroid in f_centroids.items():
                            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(scaled_vec, centroid)))
                            if dist < min_dist:
                                min_dist = dist
                                try:
                                    # If the key is numbered like "Cluster 0", extract the 0
                                    c_idx = int(str(c_key).split(" ")[-1])
                                    s["archetype"] = f_names[c_idx] if c_idx < len(f_names) else c_key
                                except ValueError:
                                    # If the key is already the name (e.g., "Interfaces"), use it directly!
                                    s["archetype"] = str(c_key)

                # 3. Calculate Structural Inequality (Gini)
                if len(complexities) > 1 and sum(complexities) > 0:
                    sorted_comps = sorted(float(c) for c in complexities)
                    n = len(sorted_comps)
                    index = range(1, n + 1)
                    func_gini = (sum((2 * i - n - 1) * c for i, c in zip(index, sorted_comps))) / (
                        n * sum(sorted_comps)
                    )
            # ---> END FUNCTION-LEVEL ML CLASSIFICATION <---

            raw_imports_count = len(meta.get("raw_imports", []))
            popularity = meta.get("popularity", 0)

            log_logic_loc = math.log1p(logic_loc)
            log_imports_out = math.log1p(raw_imports_count)
            log_popularity_in = math.log1p(popularity)
            log_max_func_comp = math.log1p(max_func_comp)
            log_avg_func_args = math.log1p(avg_func_args)
            log_churn = math.log1p(raw_churn_freq)

            raw_vector = []
            for key in self.SIGNAL_SCHEMA:
                # ---> THE DIMENSIONAL FIX: Ignore hardware_bridge and cryptography <---
                if key in {
                    "tabs_vs_spaces",
                    "indent_tabs",
                    "indent_spaces",
                    "hardware_bridge",
                    "cryptography",
                } or key.startswith("sec_"):
                    continue
                raw_hit = raw_signals.get(key, 0)
                raw_density = (raw_hit / safe_denom) * 100.0
                raw_vector.append(math.log1p(raw_density))

            raw_vector.extend(
                [
                    cfr,
                    log_logic_loc,
                    log_imports_out,
                    log_popularity_in,
                    log_max_func_comp,
                    log_avg_func_args,
                    log_churn,
                ]
            )

            # ------------------------------------------------------------------
            # 1.6 BIAXIAL ANOMALY DETECTION (Global vs Local)
            # ------------------------------------------------------------------
            # A) GLOBAL MACRO-SPECIES
            scaled_vector_global = []
            for i, val in enumerate(raw_vector):
                median = self.SCALER_MEDIANS[i] if i < len(self.SCALER_MEDIANS) else 0.0
                safe_iqr = self.SCALER_IQRS[i] if i < len(self.SCALER_IQRS) and self.SCALER_IQRS[i] > 0 else 1.0
                scaled_vector_global.append((val - median) / safe_iqr)

            global_archetype, global_drift, arch_fingerprint = self._classify_archetype(
                scaled_vector_global, self.GLOBAL_ARCHETYPES
            )

            # B) LOCAL MICRO-SPECIES
            local_archetype = None
            local_drift = 0.0
            local_fingerprint = {}

            lang_brain = self.LANGUAGE_INFERENCE_MODELS.get(lang_id.lower())
            if lang_brain:
                lang_medians = lang_brain.get("SCALER_MEDIANS", [])
                lang_iqrs = lang_brain.get("SCALER_IQRS", [])

                # Find the dynamic K-key (e.g., ARCHETYPES_K11)
                arch_key = next((k for k in lang_brain.keys() if k.startswith("ARCHETYPES_K")), None)
                lang_archetypes = lang_brain.get(arch_key, {}) if arch_key else {}

                if lang_medians and lang_iqrs and lang_archetypes:
                    scaled_vector_local = []
                    for i, val in enumerate(raw_vector):
                        median = lang_medians[i] if i < len(lang_medians) else self.SCALER_MEDIANS[i]
                        iqr = lang_iqrs[i] if i < len(lang_iqrs) else self.SCALER_IQRS[i]
                        safe_iqr = iqr if iqr > 0 else 1.0
                        scaled_vector_local.append((val - median) / safe_iqr)

                    local_archetype, local_drift, local_fingerprint = self._classify_archetype(
                        scaled_vector_local, lang_archetypes
                    )

            # ------------------------------------------------------------------
            # 2. CORE RISK EXPOSURE CALCULATIONS
            # ------------------------------------------------------------------
            # The OOM Bomb heuristic has been phased out of the probabilistic model.
            # Spatial correlation is now handled natively upstream in detector.py.

            cog_score, cog_raw = self._calc_cog_load(loc, raw_signals, irc, fc, mp_map.get("cog", 1.0), func_gini)
            saf_score = self._calc_safety(loc, raw_signals, irc, fc, mp_map.get("safety", 1.0))
            debt_score = self._calc_tech_debt(loc, raw_signals, irc, mp_map.get("debt", 1.0))

            test_score = self._calc_verification(
                loc,
                rel_path,
                meta.get("is_protected", False),
                raw_signals,
                ot,
                fc,
                mp_map.get("test", 1.0),
                functions,
                meta.get("test_coverage_map", {}),
                umbrella_bonus=umbrella_bonus,
                popularity=popularity,
            )

            # Calculate Silo Risk early for the Documentation N-Dimensional Math
            silo_exposure = self._calculate_silo_risk(meta.get("authors", {}))

            doc_score = self._calc_documentation(
                loc,
                doc_lines,
                raw_signals,
                fc,
                irc,
                mp_map.get("doc", 1.0),
                functions,
                doc_umbrella=ghost_meta.get("doc_umbrella", 0.0),
                popularity=popularity,
                silo_exposure=silo_exposure,
            )
            spec_score = self._calc_spec_alignment(raw_signals, mp_map.get("spec", 1.0))

            bureaucracy_dampener = min(loc / 15.0, 1.0)
            test_score *= bureaucracy_dampener
            doc_score *= bureaucracy_dampener
            spec_score *= bureaucracy_dampener

            exposure_vector = {
                "cognitive_load": cog_score,
                "safety_score": saf_score,
                "tech_debt": debt_score,
                "verification": test_score,
                "api_exposure": self._calc_api_exposure(raw_signals, total_loc, popularity),
                "concurrency": self._calc_concurrency(loc, raw_signals, irc, mp_map.get("async", 1.0), functions),
                "state_flux": self._calc_state_flux(loc, raw_signals, irc, mp_map.get("state_mutation", 1.0)),
                "dead_code": self._calc_graveyard(total_loc, raw_signals, mp_map.get("dead", 1.0)),
                "spec_match": spec_score,
                "stability": stability_score,
                "churn": 0.0,
                "documentation": doc_score,
                "tabs_vs_spaces": self._calc_civil_war(raw_signals),
                "algorithmic_dos": self._calc_algorithmic_dos(
                    loc,
                    raw_signals,
                    mp_map.get("algorithmic_dos", 1.0),
                    functions,
                    popularity,
                ),
                # ---> BIAXIAL WEAPONIZATION <---
                "obscured_payload": self._calc_obscured_payload(
                    loc,
                    raw_signals,
                    mp_map.get("obscured", 1.0),
                    global_archetype,
                    global_drift,
                    local_drift,
                ),
                "logic_bomb": self._calc_logic_bomb(
                    loc,
                    raw_signals,
                    mp_map.get("logic_bomb", 1.0) * eco_mp.get("logic_bomb", 1.0),
                    global_archetype,
                    global_drift,
                    local_drift,
                    max_big_o,
                ),
                "injection_surface": self._calc_injection_surface(
                    loc,
                    raw_signals,
                    mp_map.get("injection", 1.0) * eco_mp.get("injection", 1.0),
                    global_archetype,
                ),
                "memory_corruption": self._calc_memory_corruption(
                    loc,
                    raw_signals,
                    mp_map.get("memory", 1.0) * eco_mp.get("memory", 1.0),
                    lang_id,
                    global_archetype,
                ),
                "secrets_risk": self._calc_secrets_risk(loc, raw_signals, mp_map.get("secrets", 1.0)),
            }

            # ==================================================================
            # INLINE SUPPRESSION OVERRIDE (galaxyscope:ignore)
            # ==================================================================
            mitigations = meta.get("mitigations", [])
            for suppressed_risk in mitigations:
                if suppressed_risk in exposure_vector:
                    self.logger.debug(f"[{rel_path}] Suppressing {suppressed_risk} due to inline galaxyscope:ignore")
                    exposure_vector[suppressed_risk] = 0.0

            # ------------------------------------------------------------------
            # 3. VECTOR ASSEMBLY (Locked to RISK_SCHEMA order)
            # ------------------------------------------------------------------
            risk_vector_ordered = [round(exposure_vector[key], 4) for key in self.RISK_SCHEMA]

            # ------------------------------------------------------------------
            # 4. CALCULATE FILE IMPACT (Structural Magnitude)
            # ------------------------------------------------------------------
            functions = meta.get("functions", [])
            func_start = raw_signals.get("func_start", 0)

            if functions:
                sum_function_impacts = sum(f.get("impact", 0) for f in functions)
            else:
                if func_start == 0:
                    temp_branches = 0
                    temp_args = 0
                else:
                    temp_branches = raw_signals.get("branch", 0)
                    temp_args = raw_signals.get("args", 0)

                temp_signals = temp_branches + temp_args
                temp_effective_loc = min(loc, (temp_signals + 1) * 10)
                temp_arg_multiplier = math.sqrt(temp_args + 1)

                sum_function_impacts = ((temp_branches + 1) * temp_arg_multiplier + (0.05 * temp_effective_loc)) * 10

            api_exposure = raw_signals.get("api", 0)
            concurrency = raw_signals.get("concurrency", 0)
            flux = raw_signals.get("state_mutation", 0)

            file_mass = sum_function_impacts + api_exposure + concurrency + flux + (loc / 50.0)

            # ------------------------------------------------------------------
            # 5. EXECUTE OWNERSHIP ENTROPY MATH & AUTHORSHIP CENTRALIZATION
            # ------------------------------------------------------------------
            authors_map = meta.get("authors", {})
            ownership_score = self._calc_ownership_entropy(authors_map)
            silo_exposure = self._calculate_silo_risk(authors_map)

            if authors_map:
                dominant_author = max(authors_map, key=authors_map.get)
            else:
                dominant_author = ghost_meta.get("ownership", "Unknown Architect")

            telemetry_payload = {
                "archetype": global_archetype,
                "encapsulation_ratio": round(encapsulation_ratio, 3),
                "global_drift": global_drift,
                "archetype_fingerprint": arch_fingerprint,
                "local_archetype": local_archetype,
                "local_drift": local_drift,
                "local_fingerprint": local_fingerprint,
                "densities": {"cog_raw": round(cog_raw, 3)},
                "raw_churn_freq": raw_churn_freq,
                "func_complexity_gini": func_gini,
                "max_algorithmic_complexity": (
                    "O(2^N) [Recursive]" if has_recursion else (f"O(N^{max_big_o})" if max_big_o > 1 else "O(N)")
                ),
                "max_db_complexity": max_db_complexity,
                "ownership_entropy": ownership_score,
                "author_distribution": silo_exposure,
                "ownership": dominant_author,
                "domain_context": ghost_meta,
                "mitigation_telemetry": meta.get("mitigations", []),
                "threat_locations": meta.get("threat_locations", {}),
            }

            if mp_map:
                telemetry_payload["multipliers"] = mp_map

            return {
                "risk_vector": risk_vector_ordered,
                "hit_vector": hit_vector,
                "file_impact": round(file_mass, 2),
                "telemetry": telemetry_payload,
            }

        except Exception as e:
            self.logger.error(
                f"Catastrophic structural failure on artifact '{rel_path}': {e}",
                exc_info=True,
            )
            return {
                "risk_vector": [0.0] * len(self.RISK_SCHEMA),
                "hit_vector": [raw_signals.get(k, 0) for k in self.SIGNAL_SCHEMA],
                "file_impact": max(loc / 50.0, 1.0),
                "telemetry": {"error": str(e)},
            }

    # ==========================================================================
    # GLOBAL SYNTHESIS & 2-PASS NORMALIZATION
    # ==========================================================================

    def summarize_galaxy_metrics(
        self, parsed_files: List[Dict[str, Any]], unparsable_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """[GLOBAL SYNTHESIS] Executes Pass 2 Normalization and aggregates health metrics."""

        # Execute Pass 2: Temporal Normalization across the Universe
        self._normalize_temporal_metrics(parsed_files)

        total_files = len(parsed_files) + len(unparsable_files)
        if total_files == 0:
            return {}

        self.logger.info(
            f"Synthesizing repository metrics across {total_files} artifacts ({len(parsed_files)} verified, {len(unparsable_files)} unparsable)..."
        )

        # Safely extract score averages from the risk_vector list via mapping
        def get_avg(metric_name):
            if metric_name not in self.RISK_SCHEMA:
                return 0.0
            idx = self.RISK_SCHEMA.index(metric_name)
            scores = [f["risk_vector"][idx] for f in parsed_files if "risk_vector" in f and len(f["risk_vector"]) > idx]
            return round(statistics.mean(scores), 3) if scores else 0.0

        lang_comp = {}
        total_loc = 0
        for f in parsed_files:
            lang = f.get("lang_id", "unknown")
            loc = f.get("coding_loc", 0)
            impact = f.get("file_impact", 0.0)
            total_loc += loc
            if lang not in lang_comp:
                lang_comp[lang] = {"files": 0, "loc": 0, "impact": 0.0}
            lang_comp[lang]["files"] += 1
            lang_comp[lang]["loc"] += loc
            lang_comp[lang]["impact"] += impact

        churn_idx = self.RISK_SCHEMA.index("churn")
        high_volatility = len(
            [
                f
                for f in parsed_files
                if "risk_vector" in f and len(f["risk_vector"]) > churn_idx and f["risk_vector"][churn_idx] > 80.0
            ]
        )
        volatility_idx = round(high_volatility / max(len(parsed_files), 1), 3)
        darkness_ratio = round(len(unparsable_files) / max(total_files, 1), 3)

        self.logger.info(
            f"Synthesis Complete | Volatility Index: {volatility_idx:.2f} | Darkness Ratio: {darkness_ratio * 100:.1f}%"
        )

        # --- NEW: Directory Group Aggregation Logic ---
        directory_group_data = {}
        for f in parsed_files:
            d_name = f.get("directory_group", "__monolith__")
            if d_name not in directory_group_data:
                directory_group_data[d_name] = {
                    "count": 0,
                    "mass": 0.0,
                    "risks": [0.0] * len(self.RISK_SCHEMA),
                }

            directory_group_data[d_name]["count"] += 1
            directory_group_data[d_name]["mass"] += f.get("file_impact", 0.0)

            for i, val in enumerate(f.get("risk_vector", [])):
                if i < len(self.RISK_SCHEMA):
                    directory_group_data[d_name]["risks"][i] += val

        d_metrics = {
            name: {
                "file_count": data["count"],
                "total_mass": round(data["mass"], 2),
                "avg_exposures": {
                    self.RISK_SCHEMA[i]: round(data["risks"][i] / data["count"], 2)
                    for i in range(len(self.RISK_SCHEMA))
                },
            }
            for name, data in directory_group_data.items()
        }

        # --- NEW: Ecosystem Fingerprint (Archetype Ratios) ---
        # --- NEW: Ecosystem Fingerprint (Archetype Ratios & Counts) ---
        archetype_counts = {}
        static_counts = {}

        for f in parsed_files:
            arch = f.get("telemetry", {}).get("archetype", "Unknown")
            if arch.startswith("Static:"):
                static_counts[arch] = static_counts.get(arch, 0) + 1
            else:
                archetype_counts[arch] = archetype_counts.get(arch, 0) + 1

        ecosystem_fingerprint = {"ml_clusters": {}, "static_mass": {}}
        if len(parsed_files) > 0:
            ecosystem_fingerprint["ml_clusters"] = {
                name: {
                    "count": count,
                    "pct": round((count / len(parsed_files)) * 100.0, 1),
                }
                for name, count in sorted(archetype_counts.items(), key=lambda x: x[1], reverse=True)
            }
            ecosystem_fingerprint["static_mass"] = {
                name: {
                    "count": count,
                    "pct": round((count / len(parsed_files)) * 100.0, 1),
                }
                for name, count in sorted(static_counts.items(), key=lambda x: x[1], reverse=True)
            }

        # --- NEW: AI TOPOLOGY & LLM INTELLIGENCE ---
        ai_sensor_keys = [
            "llm_api",
            "llm_orchestrator",
            "llm_vector_store",
            "llm_local_compute",
            "ai_tools",
            "ai_memory",
            "ai_logic_loop",
            "ml_traditional",
            "dl_frameworks",
        ]
        ai_indices = {k: self.SIGNAL_SCHEMA.index(k) for k in ai_sensor_keys if k in self.SIGNAL_SCHEMA}

        # Isolate the physical files harboring AI logic
        ai_files = []
        for f in parsed_files:
            hv = f.get("hit_vector", [])
            file_ai_mass = sum(hv[idx] for k, idx in ai_indices.items() if idx < len(hv))
            if file_ai_mass > 0:
                ai_files.append(f)

        llm_api_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("llm_api")]
                if "llm_api" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("llm_api")
                else 0
            )
            for f in parsed_files
        )
        llm_orch_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("llm_orchestrator")]
                if "llm_orchestrator" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("llm_orchestrator")
                else 0
            )
            for f in parsed_files
        )
        llm_vector_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("llm_vector_store")]
                if "llm_vector_store" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("llm_vector_store")
                else 0
            )
            for f in parsed_files
        )
        llm_local_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("llm_local_compute")]
                if "llm_local_compute" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("llm_local_compute")
                else 0
            )
            for f in parsed_files
        )

        # Agentic Sensors
        ai_tools_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("ai_tools")]
                if "ai_tools" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("ai_tools")
                else 0
            )
            for f in parsed_files
        )
        ai_memory_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("ai_memory")]
                if "ai_memory" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("ai_memory")
                else 0
            )
            for f in parsed_files
        )
        ai_loop_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("ai_logic_loop")]
                if "ai_logic_loop" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("ai_logic_loop")
                else 0
            )
            for f in parsed_files
        )

        # ML/DL Sensors
        ml_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("ml_traditional")]
                if "ml_traditional" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("ml_traditional")
                else 0
            )
            for f in parsed_files
        )
        dl_total = sum(
            (
                f.get("hit_vector", [])[self.SIGNAL_SCHEMA.index("dl_frameworks")]
                if "dl_frameworks" in self.SIGNAL_SCHEMA
                and len(f.get("hit_vector", [])) > self.SIGNAL_SCHEMA.index("dl_frameworks")
                else 0
            )
            for f in parsed_files
        )
        ai_topology = {"classification": "Non-AI / Traditional", "insights": []}

        total_ai_mass = (
            llm_api_total
            + llm_orch_total
            + llm_vector_total
            + llm_local_total
            + ai_tools_total
            + ai_memory_total
            + ai_loop_total
            + ml_total
            + dl_total
        )

        if total_ai_mass > 0:
            # Assess Agentic Autonomy First (Highest Complexity)
            if ai_loop_total > 0 and ai_tools_total > 0:
                ai_topology["classification"] = "Autonomous Agentic Fleet (Level 4)"
                ai_topology["insights"].append(
                    "High density of bound tools and cyclic reasoning loops (ReAct). Agents possess autonomy to execute code. Critical risk of non-deterministic runtime behavior."
                )
                if ai_memory_total == 0:
                    ai_topology["insights"].append(
                        "WARNING: High autonomy but low memory density. Agents may suffer from context amnesia between loops."
                    )
            elif ai_tools_total > 0:
                ai_topology["classification"] = "Tool-Augmented LLM (Level 3)"
                ai_topology["insights"].append(
                    "LLM is explicitly bound to external functions/tools. High blast radius if prompt injection occurs."
                )
            elif llm_local_total > 0:
                ai_topology["classification"] = "Local Sovereignty (Heavy Compute)"
                ai_topology["insights"].append(
                    "Repository contains local model execution or tensor math. Expect heavy GPU memory allocation."
                )
            elif llm_vector_total > 0 and llm_api_total > 0:
                ai_topology["classification"] = "RAG Pipeline (Retrieval-Augmented Generation)"
                ai_topology["insights"].append(
                    "Active vector database integration detected. Architecture centers around data chunking and context retrieval."
                )
            elif llm_orch_total > (llm_api_total * 2):
                ai_topology["classification"] = "Framework-Heavy Orchestration"
                ai_topology["insights"].append(
                    "Heavy reliance on agentic frameworks (e.g., LangChain). High cognitive load and abstraction risk."
                )
            elif dl_total > 0:
                ai_topology["classification"] = "Deep Learning Architecture"
                ai_topology["insights"].append(
                    "Heavy neural network footprint detected (PyTorch/TensorFlow/JAX). Optimized for tensor math and gradient descent."
                )
            elif ml_total > 0:
                ai_topology["classification"] = "Statistical Machine Learning"
                ai_topology["insights"].append(
                    "Traditional ML architecture detected (XGBoost/Scikit-Learn). Focus on decision trees, regressions, and structured data."
                )
            else:
                ai_topology["classification"] = "Cloud API Wrapper"
                ai_topology["insights"].append(
                    "Thin wrapper around external LLM APIs. Low local compute mass, but high vendor lock-in risk."
                )

            # ---> N-DIMENSIONAL AI NETWORK POSTURE <---
            if ai_files:
                # Find the most heavily relied-upon AI node in the graph
                ai_files.sort(
                    key=lambda x: x.get("telemetry", {}).get("network_metrics", {}).get("pagerank_score") or 0.0,
                    reverse=True,
                )
                primary_ai_node = ai_files[0]
                net_mets = primary_ai_node.get("telemetry", {}).get("network_metrics", {})

                role = net_mets.get("ecosystem_role", "Unknown")
                pr = net_mets.get("normalized_blast_radius") or 0.0
                btw = net_mets.get("betweenness_score") or 0.0

                ai_topology["insights"].append(
                    f"Structural Posture: The primary AI integration acts as a '{role}' within the repository."
                )

                if pr > 1.0:
                    ai_topology["insights"].append(
                        f"Systemic Risk (High): The AI components are deeply embedded with a massive Dependency Blast Radius (PageRank: {pr}). Hallucinations or prompt injections here will cascade catastrophically across the system."
                    )
                elif pr < 0.2:
                    ai_topology["insights"].append(
                        "Containment (Low Risk): The AI components are safely isolated at the edge of the network with a minimal dependency blast radius."
                    )

                if btw > 0.05:
                    ai_topology["insights"].append(
                        "Cognitive Choke Point: The AI sits on the shortest path between major system domains (High Betweenness). It is acting as an intelligent router, filter, or mandatory data transformer."
                    )

            ai_topology["signal_mass"] = {
                "Cloud APIs": llm_api_total,
                "Orchestrators": llm_orch_total,
                "Vector Stores": llm_vector_total,
                "Local Compute": llm_local_total,
                "Agent Tools": ai_tools_total,
                "Agent Memory": ai_memory_total,
                "Agent Loops": ai_loop_total,
                "Traditional ML": ml_total,
                "Deep Learning": dl_total,
            }

        # --- NEW: Ecosystem Baseline Clustering (Global Repository Archetype) ---
        repo_model = getattr(config, "GENERAL_REPO_INFERENCE_MODEL", None)
        repo_macro_data = {
            "name": "Unclassified",
            "id": -1,
            "z_score": 0.0,
            "raw_drift": 0.0,
        }

        if repo_model and parsed_files:
            # Rebuild the ratios based purely on the K-Means features
            feature_counts = {feat: archetype_counts.get(feat, 0) for feat in repo_model["features"]}
            live_ratios = [feature_counts[feat] / len(parsed_files) for feat in repo_model["features"]]

            distances = []
            for i in range(repo_model["k_clusters"]):
                centroid = repo_model["centroids"][f"Cluster {i}"]
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(live_ratios, centroid)))
                distances.append(dist)

            assigned_idx = distances.index(min(distances))
            raw_drift = distances[assigned_idx]

            z_params = repo_model["z_score_params"][f"Cluster {assigned_idx}"]
            z_score = (raw_drift - z_params["mean"]) / z_params["std"]

            cluster_names = repo_model.get(
                "cluster_names",
                [f"Cluster {i}" for i in range(repo_model["k_clusters"])],
            )

            repo_macro_data = {
                "name": cluster_names[assigned_idx],
                "id": assigned_idx,
                "z_score": round(z_score, 3),
                "raw_drift": round(raw_drift, 3),
            }

            # Inject into parsed_files so security_auditor and gpu_recorder have it in RAM
            for f in parsed_files:
                f["telemetry"]["ecosystem_baseline_cluster"] = assigned_idx
                f["telemetry"]["ecosystem_z_score"] = repo_macro_data["z_score"]
                for i, d in enumerate(distances):
                    f["telemetry"][f"dist_to_{i}"] = d

        return {
            "summary": {
                "total_files": total_files,
                "verified_files": len(parsed_files),
                "total_loc": total_loc,
                "dominant_language": self._get_dominant_lang(lang_comp),
                "volatility_index": volatility_idx,
                "Percent_Visible": round((1 - darkness_ratio) * 100, 1),
            },
            "repo_macro_species": repo_macro_data,
            "unparsable_files": {
                "ambig_file_count": len(unparsable_files),
            },
            "health": {
                "avg_cognitive_load": get_avg("cognitive_load"),
                "avg_safety_score": get_avg("safety_score"),
                "avg_tech_debt": get_avg("tech_debt"),
                "avg_documentation": get_avg("documentation"),
            },
            "composition": lang_comp,
            "ecosystem_fingerprint": ecosystem_fingerprint,
            "ai_topology": ai_topology,
            "directory_groups": d_metrics,
        }

    def _normalize_temporal_metrics(self, parsed_files: List[Dict[str, Any]]):
        """[PASS 2] Normalizes churn using a Logarithmic Curve for better UI gradients."""
        if not parsed_files:
            return
        max_freq = 0.0

        # Pass 2.A: Find the volcano (Global Max)
        for file_data in parsed_files:
            freq = file_data.get("telemetry", {}).get("raw_churn_freq", 0.0)
            if freq > max_freq:
                max_freq = freq

        # THE FIX: Apply a logarithmic curve to the maximum ceiling
        # math.log1p safely handles 0 values (log(1 + x))
        safe_max_f = math.log1p(max(max_freq, 1.0))
        idx = self.RISK_SCHEMA.index("churn")

        # Pass 2.B: Normalize every file against the logarithmic curve
        for file_data in parsed_files:
            freq = file_data.get("telemetry", {}).get("raw_churn_freq", 0.0)

            # THE FIX: Apply the same logarithmic curve to the individual file
            base_score = (math.log1p(freq) / safe_max_f) * 100.0

            mp = file_data.get("telemetry", {}).get("multipliers", {}).get("churn", 1.0)
            final_churn = min(base_score * mp, 100.0)

            # Inject Churn directly into the correct Risk Vector index
            if "risk_vector" in file_data and len(file_data["risk_vector"]) > idx:
                file_data["risk_vector"][idx] = round(final_churn, 2)

    # ==========================================================================
    # FORENSIC EQUATIONS (The Structural Models)
    # ==========================================================================

    def _calc_raw_temporal_signals(self, temp: Dict[str, Any]) -> Tuple[float, float]:
        """Calculates Stability (Age) and Raw Churn (Seismic Frequency)."""
        if not temp or not temp.get("is_git_tracked", False):
            return 50.0, 0.0

        mtime = temp.get("mtime", 0.0)
        repo_min = temp.get("repo_min_time", mtime)
        repo_max = temp.get("repo_max_time", mtime)
        commits = temp.get("commit_count", 0)

        # ---> THE FIX: Clamp the time difference so it never goes negative <---
        seconds_from_max = max(repo_max - mtime, 0.0)
        time_range = max(repo_max - repo_min, 1.0)

        # 1. Stability (0 = Newest/Surface, 100 = Oldest/Bedrock)
        stability_ratio = seconds_from_max / time_range
        stability_score = min(stability_ratio * 100.0, 100.0)

        # 2. Raw Churn Frequency
        age_weeks = max(seconds_from_max / 604800.0, 1.0)
        raw_churn_freq = commits / math.sqrt(age_weeks)

        return stability_score, raw_churn_freq

    def _calc_ownership_entropy(self, authors: Dict[str, int]) -> float:
        """
        Calculates Ownership Entropy (Shannon Entropy) for the file.
        0 = Single Author (Pure Ownership/Stable), 100 = Highly Distributed (Vibrating/White).
        """
        if not authors:
            return 0.0

        total_commits = sum(authors.values())
        if total_commits == 0:
            return 0.0

        entropy = 0.0
        for count in authors.values():
            if count > 0:
                p_i = count / total_commits
                entropy -= p_i * math.log2(p_i)

        # Scale to 0-100 score as defined in spec: OwnershipScore = min(H * 32, 100)
        ownership_score = min(entropy * 32.0, 100.0)

        return round(ownership_score, 2)

    def _calc_civil_war(self, raw_signals: Dict[str, int]) -> float:
        """
        Calculates Formatting Inconsistencies (Tabs vs Spaces).
        0 = Pure Tabs (Consistent), 100 = Pure Spaces (Consistent), 50 = High Discrepancy.
        """
        tab_lines = raw_signals.get("indent_tabs", 0)
        space_lines = raw_signals.get("indent_spaces", 0)

        l_total = tab_lines + space_lines

        # 2. Handle Void States (No indentation at all)
        if l_total == 0:
            return 50.0  # Default to Neutral

        # 3. Calculate Space-Ratio (R)
        space_ratio = space_lines / l_total

        # 4. Final Score Mapping (0-100)
        return space_ratio * 100.0

    def _calc_cog_load(
        self,
        loc: int,
        raw_signals: Dict[str, int],
        irc: int,
        fc: float,
        mp: float,
        func_gini: float = 0.0,
    ) -> Tuple[float, float]:
        safe_loc = max(loc, 1)
        t = self.risk_tuning.get("cognitive_load", {})

        if safe_loc < 15:
            total_density = sum(
                [
                    raw_signals.get(k, 0)
                    for k in [
                        "branch",
                        "state_mutation",
                        "concurrency",
                        "reflection_metaprogramming",
                        "high_risk_execution",
                    ]
                ]
            ) / safe_loc + (irc / safe_loc)
            return 5.0, total_density

        branches = raw_signals.get("branch", 0)
        if branches == 0 and safe_loc > 50:
            return 0.0, 0.0

        branch_density = branches / safe_loc
        flux_density = raw_signals.get("state_mutation", 0) / safe_loc
        concurrency_density = raw_signals.get("concurrency", 0) / safe_loc
        heat_density = raw_signals.get("reflection_metaprogramming", 0) / safe_loc
        danger_density = raw_signals.get("high_risk_execution", 0) / safe_loc

        clamped_branch = min(branch_density * 1.0, t.get("branch_clamp", 0.5))
        clamped_flux = min(flux_density * t.get("flux_mult", 2.0), t.get("flux_clamp", 0.75))
        heavy_logic = (
            (concurrency_density * t.get("async_mult", 3.0))
            + (heat_density * t.get("heat_mult", 5.0))
            + (danger_density * t.get("danger_mult", 5.0))
        )

        # ---> GOD OBJECT ANTI-PATTERN PENALTY <---
        # If complexity is heavily skewed into a single massive function (High Gini),
        # reading the file requires jarring mental context switches. Spike the load.
        gini_multiplier = 1.0
        if func_gini > 0.7:
            gini_multiplier = 1.0 + (func_gini * 0.5)

        total_density = (clamped_branch + clamped_flux + heavy_logic + (irc / safe_loc)) * gini_multiplier

        if safe_loc <= 2 and total_density == 0:
            return 0.0, total_density

        try:
            raw_score = 100.0 / (
                1.0 + math.exp(-t.get("sigmoid_slope", 4.0) * (total_density - t.get("sigmoid_offset", 0.75)))
            )
        except OverflowError:
            raw_score = 100.0 if total_density > t.get("sigmoid_offset", 0.75) else 0.0

        doc_coverage = (raw_signals.get("doc", 0) * t.get("doc_mult", 10.0)) / safe_loc
        cooling = max(0.5, 1.0 - (doc_coverage * fc))

        return min(raw_score * cooling * mp, 100.0), total_density

    def _calc_safety(self, loc: int, raw_signals: Dict[str, int], irc: int, fc: float, mp: float) -> float:
        safe_loc = max(loc, 1)
        t = self.risk_tuning.get("safety", {})

        attack_hits = (
            (raw_signals.get("high_risk_execution", 0) * t.get("danger_weight", 4.0))
            + (raw_signals.get("safety_bypasses", 0) * t.get("safety_neg_weight", 1.5))
            + (raw_signals.get("state_mutation", 0) * t.get("flux_weight", 0.5))
        )
        defense_hits = (
            (raw_signals.get("safety", 0) * self.WEIGHT_DEFENSE)
            + (raw_signals.get("test", 0) * t.get("test_weight", 0.5))
            + (raw_signals.get("doc", 0) * t.get("doc_weight", 0.1))
        )

        if attack_hits == 0:
            return 0.0

        smoothed_loc = safe_loc + t.get("laplace_smoothing", 20.0)
        attack = ((attack_hits + irc) / smoothed_loc) * mp
        defense = (defense_hits / smoothed_loc) * fc

        systems_buffer = t.get("systems_buffer", 0.25) if fc < 1.0 else 0.0
        net_exposure = (attack - defense) - systems_buffer

        try:
            score = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 12.0) * net_exposure))
        except OverflowError:
            score = 100.0 if net_exposure > 0 else 0.0

        danger_density = (raw_signals.get("high_risk_execution", 0) + raw_signals.get("safety_bypasses", 0)) / safe_loc
        if danger_density > t.get("vulnerability_density_min", 0.03) and attack > defense:
            floor = min(
                t.get("breach_floor_max", 80.0),
                30.0 + (danger_density * t.get("breach_floor_mult", 500.0)),
            )
            score = max(score, floor)

        return max(score, 0.0)

    def _calc_tech_debt(self, loc: int, raw_signals: Dict[str, int], irc: int, mp: float) -> float:
        t = self.risk_tuning.get("tech_debt", {})
        good_debt = raw_signals.get("planned_debt", 0)
        bad_debt = raw_signals.get("fragile_debt", raw_signals.get("keyword_debt", 0))
        stubs = raw_signals.get("func_empty", 0)

        # --- NEW: UNTRACKED COMPLEXITY (SLOP) ---
        orphans = raw_signals.get("orphaned_logic", 0)
        duplicates = raw_signals.get("duplicate_logic", 0)

        if good_debt == 0 and bad_debt == 0 and stubs == 0 and orphans == 0 and duplicates == 0:
            return 0.0

        # Implicit debt carries a heavier baseline penalty because it is invisible to standard linters
        slop_stress = (orphans * 2.0) + (duplicates * 5.0)

        stress = (
            (good_debt * t.get("good_debt_weight", 1.0))
            + (bad_debt * t.get("bad_debt_weight", 3.0))
            + (stubs * t.get("stub_weight", 0.5))
            + (irc * t.get("irc_weight", 0.5))
            + slop_stress
        )

        # If there is implicit debt AND acknowledged debt, they multiply each other's severity
        if slop_stress > 0 and (good_debt > 0 or bad_debt > 0):
            stress *= 1.5

        density = (stress / max(loc, 1)) * 100.0
        threshold = t.get("threshold", 5.0)

        try:
            raw_score = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 0.5) * (density - threshold)))
        except OverflowError:
            raw_score = 100.0 if density > threshold else 0.0

        return min(raw_score * mp, 100.0)

    def _calc_documentation(
        self,
        loc: int,
        doc_loc: int,
        raw_signals: Dict[str, int],
        fc: float,
        irc: int,
        mp: float,
        functions: List[Dict[str, Any]] = None,
        doc_umbrella: float = 0.0,
        popularity: int = 0,
        silo_exposure: float = 0.0,
    ) -> float:
        t = self.risk_tuning.get("documentation", {})

        # 1. THE DEFENSE (The Knowledge Shield)
        # GuideStar Umbrella projection: 1.0 shield = 50 lines of virtual documentation
        umbrella_defense = doc_umbrella * 50.0

        defense_hits = (
            (raw_signals.get("doc", 0) * t.get("doc_weight", 1.0))
            + (raw_signals.get("ownership", 0) * t.get("ownership_weight", 0.5))
            + (doc_loc * t.get("doc_loc_weight", 0.33))
            + umbrella_defense
        ) * fc

        # 2. THE RISK (Opaque Execution Risk)
        opaque_execution = 0.0
        api_exposure = raw_signals.get("api", 0) * 2.0

        if functions:
            for func in functions:
                impact = func.get("impact", 0.0)
                big_o = func.get("big_o_depth", 1)

                # If a load-bearing or deeply nested block lacks a semantic tether
                if (impact > 50.0 or big_o >= 3) and not func.get("docstring"):
                    opaque_execution += 5.0 + (math.log1p(impact) * (big_o * 0.5))

        # Add Implicit Risk Correction (Maintenance Overhead) to the risk
        risk_hits = opaque_execution + api_exposure + irc

        # 3. UNIVERSAL DENSITY EQUATION
        net_exposure = max(0.0, risk_hits - (defense_hits / 2.0))
        density = (net_exposure / max(loc, 1)) * 100.0

        # 4. THE MULTIPLIERS (Dependency Blast Radius & Authorship Centralization)
        # Undocumented code is exponentially more dangerous if it is highly
        # integrated (popularity) or siloed to a single developer.
        network_multiplier = 1.0 + (popularity / 10.0)
        silo_multiplier = 1.0 + (silo_exposure / 200.0)

        final_multiplier = network_multiplier * silo_multiplier * mp

        threshold = t.get("threshold_base", 10.0)

        try:
            # We use a negative slope because high density = high risk exposure
            raw_risk = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 0.2) * (density - threshold)))
        except OverflowError:
            raw_risk = 100.0 if density > threshold else 0.0

        return min(raw_risk * final_multiplier, 100.0)

    def _calc_verification(
        self,
        loc: int,
        rel_path: str,
        is_protected: bool,
        raw_signals: Dict[str, int],
        ot: float,
        fc: float,
        mp: float,
        functions: List[Dict[str, Any]],
        test_coverage_map: Dict[str, List[Dict[str, Any]]],
        umbrella_bonus: float = 0.0,
        popularity: int = 0,
    ) -> float:
        """
        Calculates Verification Risk Exposure by comparing structural function complexity
        against the scope of tests validating it via asymptotic dampening.
        """
        t = self.risk_tuning.get("verification", {})
        ct = t.get("asymptotic_dampener", 1.5)

        total_untested_impact = 0.0
        total_function_impact = 0.0

        if functions:
            for func in functions:
                name = func.get("name", "")
                func_impact = func.get("impact", 0.0)
                total_function_impact += func_impact

                if func_impact == 0:
                    continue

                # Step A: The Base Impact
                hit_vector = func.get("hit_vector", {})
                verification = float(hit_vector.get("test", 0))
                safety = float(hit_vector.get("safety", 0))
                bypassed = float(hit_vector.get("test_skip", 0))

                internal_defenses = (verification + safety - (bypassed * 2.0)) * fc
                base_impact = max(func_impact - internal_defenses, 0.0)

                # Step B: The Defensive Ratio (Effective Mass)
                targeting_tests = test_coverage_map.get(name, [])
                effective_test_impact_sum = 0.0

                for test in targeting_tests:
                    # Assertion Density: Ignore empty test shells
                    if test.get("test_hits", 0) == 0:
                        continue

                    # Validation Bypass: Ignore skipped tests
                    if test.get("test_skip_hits", 0) > 0:
                        continue

                    raw_impact = test.get("impact", 0.0)
                    target_count = max(test.get("target_count", 1), 1)

                    # Parameterization Multiplier
                    param_multiplier = 2.0 if test.get("decorators", 0) > 0 else 1.0

                    effective_test_impact_sum += (raw_impact * param_multiplier) / target_count

                defensive_ratio = effective_test_impact_sum / func_impact

                # Step C: The Asymptotic Dampener
                untested_impact = base_impact * (1.0 / (1.0 + (ct * defensive_ratio)))
                total_untested_impact += untested_impact

        # Add file-level danger as raw unverified mass
        file_level_danger = float(raw_signals.get("high_risk_execution", 0))
        total_untested_impact += file_level_danger

        # Step D: Executable Density Normalization & Ecosystem Modifiers
        # Apply the Opacity Tax (ot) directly to the density
        raw_density = (total_untested_impact / max(loc, 1)) * ot

        # The GuideStar Umbrella (Dampener)
        # umbrella_bonus is max 50.0. If bonus is 50, dampener is 0.5.
        guidestar_dampener = max(1.0 - (umbrella_bonus / 100.0), 0.1)

        # Dependency Blast Radius (Amplifier)
        blast_radius = mp + min(popularity * 0.2, 3.0)

        adjusted_density = (raw_density * guidestar_dampener) * blast_radius

        # Step E: Sigmoidal Normalization
        threshold = t.get("threshold_base", 15.0)
        slope = t.get("sigmoid_slope", 0.25)

        try:
            base_score = 100.0 / (1.0 + math.exp(-slope * (adjusted_density - threshold)))
        except OverflowError:
            base_score = 100.0 if adjusted_density > threshold else 0.0

        # Step F: The Path Modifier & Breach Cap
        if mp == 0.0 or is_protected:
            return 0.0

        # Breach Cap: If untested mass is overwhelmingly larger than verified, cap to Fragile (80+)
        if total_untested_impact > (total_function_impact * 0.8) and total_function_impact > 50.0:
            return max(base_score, 80.0)

        return min(base_score, 100.0)

    def _calc_graveyard(self, total_loc: float, raw_signals: Dict[str, int], mp: float) -> float:
        hits = raw_signals.get("dead_code", 0)
        if hits == 0:
            return 0.0

        t = self.risk_tuning.get("dead_code", {})
        deprecated_lines = hits * t.get("hit_mult", 3.0)
        density = (deprecated_lines / max(total_loc, t.get("safe_mass_floor", 50.0))) * 100.0

        threshold = t.get("threshold_base", 10.0) / max(mp, 0.1)
        try:
            score = 100.0 / (1.0 + math.exp(-t.get("sigmoid_slope", 0.3) * (density - threshold)))
        except OverflowError:
            score = 100.0 if density > threshold else 0.0

        return min(score, 100.0)

    def _calc_api_exposure(self, raw_signals: dict, total_loc: int, popularity: int = 0) -> float:
        """
        RISK: Publicly exposed surfaces (api).
        MITIGATION: Internal/Private boundaries (encapsulation).
        """
        api_hits = float(raw_signals.get("api", 0))
        encapsulation = float(raw_signals.get("encapsulation", 0))

        if api_hits == 0:
            return 0.0

        # NET RISK RATIO: Public / (Public + Private)
        exposure_ratio = api_hits / max(api_hits + encapsulation, 1.0)

        # ---> ISOLATED NODE ADJUSTMENT <---
        # If a file exposes 50 APIs but has 0 inbound network edges, it is an isolated node.
        # We dampen the risk. If it has massive popularity, we amplify it.
        network_multiplier = 1.0
        if popularity == 0:
            network_multiplier = 0.2  # 80% reduction for orphaned APIs
        else:
            network_multiplier = min(1.0 + (math.log1p(popularity) / 5.0), 2.0)

        # LOGARITHMIC MASS CORRECTION
        volume_weight = math.log1p(api_hits) / math.log1p(max(total_loc, 10))

        return min(exposure_ratio * volume_weight * network_multiplier * 100.0, 100.0)

    def _calc_concurrency(
        self,
        loc: int,
        raw_signals: Dict[str, int],
        irc: int,
        mp: float,
        functions: List[Dict[str, Any]] = None,
    ) -> float:
        """
        RISK: Threads/Async execution + Thread Starvation (O(N) Bombs).
        MITIGATION: Mutex/Locks/Semaphores (sync_locks).
        """
        tuning = self.risk_tuning.get("concurrency", {})
        loc_padding = tuning.get("loc_padding", 150)

        raw_concurrency = float(raw_signals.get("concurrency", 0))
        sync_locks = float(raw_signals.get("sync_locks", 0))

        # --- RESOURCE EXHAUSTION GUARD ---
        # If an individual function has concurrency hits AND terrible Big-O, it spikes the risk.
        starvation_multiplier = 1.0
        if functions:
            for func in functions:
                if func.get("hit_vector", {}).get("concurrency", 0) > 0:
                    big_o = func.get("big_o_depth", 1)
                    is_rec = func.get("is_recursive", False)
                    if is_rec:
                        starvation_multiplier = max(starvation_multiplier, 5.0)
                    elif big_o >= 3:
                        starvation_multiplier = max(starvation_multiplier, 4.0)
                    elif big_o == 2:
                        starvation_multiplier = max(starvation_multiplier, 2.0)

        # MITIGATION BALANCE: 1 lock mitigates 1.5 thread spawns.
        net_concurrency = max(0.0, raw_concurrency - (sync_locks * 1.5))

        if net_concurrency == 0:
            return 0.0

        density = ((net_concurrency * starvation_multiplier) / max(loc + loc_padding, 1)) * 100.0

        threshold = tuning.get("threshold_base", 4.0)  # Matches your config!
        slope = tuning.get("sigmoid_slope", 0.4)

        return self._sigmoid(density, threshold, slope) * 100.0 * mp

    def _calc_state_flux(self, loc: int, raw_signals: Dict[str, int], irc: int, mp: float) -> float:
        """
        RISK: State mutation (flux).
        MITIGATION: Immutability enforcements (freeze_hits).
        """
        tuning = self.risk_tuning.get("state_flux", {})

        # THE FIX: Dropped padding to 0 so mutations immediately impact density
        loc_padding = tuning.get("loc_padding", 0)

        raw_flux = float(raw_signals.get("state_mutation", 0))
        freeze_hits = float(raw_signals.get("immutability_locks", 0))

        # MITIGATION BALANCE: Subtract immutability from raw mutation.
        net_volatility = max(0.0, raw_flux - (freeze_hits * 0.5))

        if net_volatility == 0:
            return 0.0

        density = (net_volatility / max(loc + loc_padding, 1)) * 100.0

        threshold = tuning.get("threshold_base", 15.0)
        slope = tuning.get("sigmoid_slope", 0.2)

        return self._sigmoid(density, threshold, slope) * 100.0 * mp

    def _calc_spec_alignment(self, raw_signals: Dict[str, int], mp: float) -> float:
        entities = max(raw_signals.get("func_start", 0) + raw_signals.get("class_start", 0), 1)
        ratio = min(raw_signals.get("spec_exposure", 0) / entities, 1.0)
        return min((1.0 - ratio) * 100.0 * mp, 100.0)

    def _sigmoid(self, density: float, threshold: float, slope: float) -> float:
        """Safely calculates the sigmoid curve with overflow protection for extreme densities."""
        try:
            return 1.0 / (1.0 + math.exp(-slope * (density - threshold)))
        except OverflowError:
            return 1.0 if density > threshold else 0.0

    def _calc_obscured_payload(
        self,
        loc: int,
        raw_signals: Dict[str, int],
        mp: float,
        archetype: str,
        global_drift: float,
        local_drift: float,
    ) -> float:
        """
        Calculates Obscured Payload Exposure (Malicious Intent Density).
        Combines passive Security Lens observers with hardcoded secret detection.
        """
        # Fetch the archetype multiplier
        arch_matrix = self.CONTEXT_VIOLATION_MATRIX.get(archetype, {})
        arch_multiplier = arch_matrix.get("obscured_payload_multiplier", 1.0)

        obfuscation_indicators = (raw_signals.get("sec_reflection_metaprogramming", 0) * 5.0) + (
            raw_signals.get("sec_bitwise_ops", 0) * 2.0
        )
        malicious_payload = raw_signals.get("sec_safety_bypasses", 0) * 3.0
        exfiltration = raw_signals.get("sec_io", 0) * 4.0
        rce_indicators = raw_signals.get("sec_high_risk_execution", 0) * 5.0
        state_corruption = raw_signals.get("sec_state_mutation", 0) * 3.0
        dead_code_threat = raw_signals.get("sec_dead_code", 0) * 2.0
        secrets = raw_signals.get("sec_hardcoded_secrets", 0) * 1.5

        # Extension mismatch is proof of active evasion. Assign it a massive 20.0x mass.
        evasion_indicators = (raw_signals.get("sec_shadow_imports", 0) * 10.0) + (
            raw_signals.get("sec_extension_mismatch", 0) * 20.0
        )

        # DOWNGRADE: Greek letters in math/science libs are normal. Drop from 10.0 to 1.0.
        homoglyph_threat = raw_signals.get("sec_homoglyphs", 0) * 1.0

        # 1. Group the threat vectors into Behavior vs Intent
        obfuscation_mass = obfuscation_indicators + dead_code_threat + evasion_indicators + homoglyph_threat
        intent_mass = malicious_payload + exfiltration + rce_indicators + state_corruption + secrets

        # ---> THE AGENTIC / SCIENCE SHIELD <---
        # Forgive scientific/math libraries for having high entropy and weird unicode.
        science_dampener = 1.0 + (raw_signals.get("scientific", 0) * 2.0)
        obfuscation_mass = obfuscation_mass / science_dampener

        # ---> APPLY THE ARCHETYPE CONTEXT <---
        total_threat_mass = (obfuscation_mass + intent_mass) * arch_multiplier

        if total_threat_mass == 0:
            return 0.0

        if not getattr(self, "is_paranoid", False):
            if obfuscation_mass > 0 and intent_mass == 0:
                total_threat_mass *= 0.05
            elif intent_mass > 0 and obfuscation_mass == 0:
                total_threat_mass *= 0.10

        # ---> THE CONTEXTUAL DRIFT ANOMALY <---
        if local_drift > 0 and global_drift > 0:
            drift_delta = local_drift / global_drift
            # If the file blends in globally but violates local language physics
            if drift_delta > 1.5:
                total_threat_mass *= drift_delta

        # ---> NEW: THE PROFESSIONALISM QUOTIENT & CRYPTO SHIELD <---
        # Malware authors don't write 500 lines of documentation or meticulous try/catch blocks.
        docs_and_safety = (raw_signals.get("doc", 0) * 0.5) + raw_signals.get("safety", 0)
        prof_dampener = 1.0 + (docs_and_safety * 0.05)

        # Cryptography libraries naturally have high entropy/obfuscation.
        crypto_dampener = 1.0 + (raw_signals.get("cryptography", 0) * 5.0)

        # Apply the dampeners
        total_threat_mass = (total_threat_mass / prof_dampener) / crypto_dampener

        # 3. Fetch the decoupled tuning parameters from the standards configuration
        t = self.risk_tuning.get("obscured_payload", {})

        # 4. Use the dynamically fetched LOC padding (+150 by default)
        density = (total_threat_mass / max(loc + t.get("loc_padding", 150), 1)) * 100.0

        # 5. Use the dynamically fetched thresholds based on the active mode
        if getattr(self, "is_paranoid", False):
            threshold = t.get("paranoid_threshold", 2.0)
            slope = t.get("paranoid_slope", 1.5)
        else:
            threshold = t.get("std_threshold", 15.0)
            slope = t.get("std_slope", 1.0)

        try:
            score = 100.0 / (1.0 + math.exp(-slope * (density - threshold)))
        except OverflowError:
            score = 100.0 if density > threshold else 0.0

        return min(score * mp, 100.0)

    def _calc_logic_bomb(
        self,
        loc: int,
        raw_signals: Dict[str, int],
        mp: float,
        archetype: str,
        global_drift: float,
        local_drift: float,
        max_big_o: int = 1,
    ) -> float:
        """
        Calculates Logic Bomb / Sabotage Exposure.
        Looks for delayed or condition-heavy execution leading to destructive commands.
        """
        # Fetch the archetype multiplier
        arch_matrix = self.CONTEXT_VIOLATION_MATRIX.get(archetype, {})
        arch_multiplier = arch_matrix.get("logic_bomb_multiplier", 1.0)

        trigger = raw_signals.get("branch", 0) + (raw_signals.get("thread_sleeps", 0) * 3.0)
        payload = (
            (raw_signals.get("panics_and_aborts", 0) * 2.0)
            + (raw_signals.get("cleanup", 0) * 1.5)
            + (raw_signals.get("sec_high_risk_execution", 0) * 4.0)
        )

        # ---> THE AGENTIC SHIELD <---
        # AI/Robotics natively use dynamic execution. Dampen the payload if ML math is present.
        agent_dampener = (
            1.0
            + (raw_signals.get("scientific", 0) * 2.0)
            + (raw_signals.get("llm_orchestrator", 0) * 3.0)
            + (raw_signals.get("llm_local_compute", 0) * 2.0)
        )
        hardware_dampener = 1.0 + (raw_signals.get("hardware_bridge", 0) * 3.0)
        payload = payload / agent_dampener
        payload = payload / hardware_dampener

        # ---> APPLY THE ARCHETYPE CONTEXT <---
        sabotage_mass = (trigger * payload) * arch_multiplier

        # ---> THE ALGORITHMIC DOS SPIKE (Big-O Vulnerability) <---
        if max_big_o >= 3:
            # 1. API/IO Choke Point (User-Controlled N or Network Latency)
            attack_surface = raw_signals.get("api", 0) + raw_signals.get("sec_io", 0) + raw_signals.get("io", 0)
            dos_mass = attack_surface * (max_big_o**2) * 10.0

            # 2. State Flux Bomb (Memory Exhaustion)
            flux = raw_signals.get("state_mutation", 0) + raw_signals.get("globals", 0)
            dos_mass += flux * (max_big_o**2) * 5.0

            # 3. The Shielding Dampener (Safety Guardrails)
            if raw_signals.get("safety", 0) > 0 or raw_signals.get("panics_and_aborts", 0) > 0:
                dos_mass *= 0.25  # 75% reduction if guardrails exist

            sabotage_mass += dos_mass

        # ---> THE TAINT SPIKE <---
        # If the LHS Slicer confirmed data crossed from I/O to Danger, risk is absolute.
        taint_confirmed = raw_signals.get("sec_tainted_injection", 0)
        if taint_confirmed > 0:
            sabotage_mass += taint_confirmed * 500.0

        # ---> THE CONTEXTUAL DRIFT ANOMALY <---
        if local_drift > 0 and global_drift > 0:
            drift_delta = local_drift / global_drift
            if drift_delta > 1.5:
                sabotage_mass *= drift_delta

        if sabotage_mass == 0:
            return 0.0

        explicit_threats = raw_signals.get("sec_dead_code", 0) + raw_signals.get("sec_reflection_metaprogramming", 0)
        if max_big_o >= 3:
            explicit_threats += 1  # Preserve DoS Mass from being zeroed out

        if explicit_threats == 0 and taint_confirmed == 0 and not getattr(self, "is_paranoid", False):
            sabotage_mass *= 0.05

        # Fetch tuning parameters
        t = self.risk_tuning.get("logic_bomb", {})
        density = (sabotage_mass / max(loc + t.get("loc_padding", 150), 1)) * 100.0

        if getattr(self, "is_paranoid", False):
            threshold = t.get("paranoid_threshold", 10.0)
            slope = t.get("paranoid_slope", 0.5)
        else:
            threshold = t.get("std_threshold", 75.0)
            slope = t.get("std_slope", 0.2)

        try:
            score = 100.0 / (1.0 + math.exp(-slope * (density - threshold)))
        except OverflowError:
            score = 100.0 if density > threshold else 0.0

        return min(score * mp, 100.0)

    def _calc_injection_surface(self, loc: int, raw_signals: Dict[str, int], mp: float, archetype: str) -> float:
        """
        Calculates Injection Surface Exposure (XSS, SQLi, RCE, SSTI).
        Looks for external network input flowing near dynamic execution without safety nets.
        """
        # Fetch the archetype multiplier
        arch_matrix = self.CONTEXT_VIOLATION_MATRIX.get(archetype, {})
        arch_multiplier = arch_matrix.get("injection_surface_multiplier", 1.0)

        input_vectors = raw_signals.get("sec_io", 0) + (raw_signals.get("ssr_boundaries", 0) * 2.0)
        execution_vectors = (raw_signals.get("sec_high_risk_execution", 0) * 4.0) + (raw_signals.get("sec_safety_bypasses", 0) * 2.0)

        # ---> LLM EXECUTION VULNERABILITY (Prompt Injection to Exec) <---
        if raw_signals.get("sec_high_risk_execution", 0) > 0 and (
            raw_signals.get("llm_orchestrator", 0) > 0 or raw_signals.get("ai_tools", 0) > 0
        ):
            # If an AI can trigger eval/exec/OS commands, it's a massive vulnerability
            execution_vectors *= 10.0
            input_vectors += 5.0  # Treat the LLM itself as a hostile input vector
        else:
            # ---> STATIC AI COMPUTE DAMPENER (Standard safe agents) <---
            agent_dampener = (
                1.0 + (raw_signals.get("scientific", 0) * 2.0) + (raw_signals.get("llm_local_compute", 0) * 2.0)
            )
            execution_vectors = execution_vectors / agent_dampener

        # Hardware bridges natively take external input (usb/serial) and execute it.
        hardware_dampener = 1.0 + (raw_signals.get("hardware_bridge", 0) * 3.0)
        execution_vectors = execution_vectors / hardware_dampener

        # ---> APPLY THE ARCHETYPE CONTEXT <---
        injection_mass = (input_vectors * execution_vectors) * arch_multiplier

        # ---> CONFIRMED TAINT VULNERABILITY <---
        taint_confirmed = raw_signals.get("sec_tainted_injection", 0)
        if taint_confirmed > 0:
            injection_mass += taint_confirmed * 500.0  # Massive gravity spike

        if injection_mass == 0:
            return 0.0

        explicit_threats = raw_signals.get("sec_high_risk_execution", 0) + raw_signals.get("sec_io", 0)
        if explicit_threats == 0 and taint_confirmed == 0 and not getattr(self, "is_paranoid", False):
            injection_mass *= 0.10

        # Fetch tuning parameters
        t = self.risk_tuning.get("injection_surface", {})
        density = (injection_mass / max(loc + t.get("loc_padding", 150), 1)) * 100.0

        if getattr(self, "is_paranoid", False):
            threshold = t.get("paranoid_threshold", 3.0)
            slope = t.get("paranoid_slope", 1.2)
        else:
            threshold = t.get("std_threshold", 40.0)
            slope = t.get("std_slope", 0.4)

        try:
            score = 100.0 / (1.0 + math.exp(-slope * (density - threshold)))
        except OverflowError:
            score = 100.0 if density > threshold else 0.0

        return min(score * mp, 100.0)

    def _calc_memory_corruption(
        self,
        loc: int,
        raw_signals: Dict[str, int],
        mp: float,
        lang_id: str = "",
        archetype: str = "",
    ) -> float:
        """
        Calculates Memory Corruption Exposure (Buffer Overflows, UAF).
        Strictly Opt-In: Only applies to languages with manual memory/pointers.
        """
        # Fetch the archetype multiplier
        arch_matrix = self.CONTEXT_VIOLATION_MATRIX.get(archetype, {})
        arch_multiplier = arch_matrix.get("memory_corruption_multiplier", 1.0)

        # ---> THE ARCHITECTURAL FIX: Opt-In Vulnerability Whitelist <---
        native_memory_langs = {
            "c",
            "cpp",
            "objective-c",
            "rust",
            "zig",
            "assembly",
            "agc_assembly",
            "nim",
        }

        # If it's not a native memory language, it physically cannot have these exploits.
        if lang_id.lower() not in native_memory_langs:
            return 0.0

        raw_memory_mass = (
            (raw_signals.get("pointers", 0) * 2.5)
            + (raw_signals.get("memory_alloc", 0) * 3.0)
            + (raw_signals.get("inline_asm", 0) * 5.0)
            + (raw_signals.get("explicit_casts", 0) * 1.5)
        )

        if raw_memory_mass == 0:
            return 0.0

        mitigation_mass = raw_signals.get("cleanup", 0) + (raw_signals.get("safety", 0) * 1.5)

        net_risk = max(raw_memory_mass - mitigation_mass, 0.0) * arch_multiplier

        explicit_threats = (
            raw_signals.get("sec_high_risk_execution", 0)
            + raw_signals.get("sec_safety_bypasses", 0)
            + raw_signals.get("sec_reflection_metaprogramming", 0)
        )
        if explicit_threats == 0 and not getattr(self, "is_paranoid", False):
            net_risk *= 0.05

        # 1. Fetch the decoupled tuning parameters
        t = self.risk_tuning.get("memory_corruption", {})

        # 2. Use the dynamically fetched LOC padding
        density = (net_risk / max(loc + t.get("loc_padding", 150), 1)) * 100.0

        # 3. Use the dynamically fetched thresholds based on the active mode
        if getattr(self, "is_paranoid", False):
            threshold = t.get("paranoid_threshold", 4.0)
            slope = t.get("paranoid_slope", 0.8)
        else:
            threshold = t.get("std_threshold", 25.0)
            slope = t.get("std_slope", 0.4)

        try:
            score = 100.0 / (1.0 + math.exp(-slope * (density - threshold)))
        except OverflowError:
            score = 100.0 if density > threshold else 0.0

        return min(score * mp, 100.0)

    def _calc_secrets_risk(self, loc: int, raw_signals: Dict[str, int], mp: float) -> float:
        """
        Calculates Secrets Risk Exposure (Credential Exposure).
        Looks for hardcoded credentials. Trusts the SecurityLens RHS-string sensor.
        """
        base_leak = raw_signals.get("sec_hardcoded_secrets", 0) * 10.0

        if base_leak == 0:
            return 0.0

        careless_amplifiers = (
            1.0 + raw_signals.get("debug_prints", 0) + raw_signals.get("dead_code", 0) + raw_signals.get("globals", 0)
        )

        # LLM API keys are massive targets. If they are calling APIs without globals, spike the risk.
        if raw_signals.get("llm_api", 0) > 0 and raw_signals.get("globals", 0) == 0:
            careless_amplifiers *= 3.0

        if not getattr(self, "is_paranoid", False) and raw_signals.get("sec_reflection_metaprogramming", 0) == 0:
            careless_amplifiers = min(careless_amplifiers, 2.0)

        leak_mass = base_leak * careless_amplifiers

        # 1. Fetch the decoupled tuning parameters
        t = self.risk_tuning.get("secrets_risk", {})

        # 2. Use the dynamically fetched LOC padding (defaults to 50 because secrets are highly sensitive regardless of file size)
        density = (leak_mass / max(loc + t.get("loc_padding", 50), 1)) * 100.0

        # 3. Use the dynamically fetched thresholds based on the active mode
        if getattr(self, "is_paranoid", False):
            threshold = t.get("paranoid_threshold", 0.5)
            slope = t.get("paranoid_slope", 2.0)
        else:
            threshold = t.get("std_threshold", 3.0)
            slope = t.get("std_slope", 1.0)

        try:
            score = 100.0 / (1.0 + math.exp(-slope * (density - threshold)))
        except OverflowError:
            score = 100.0 if density > threshold else 0.0

        if score < 5.0:
            score = 0.0

        return min(score * mp, 100.0)

    def _calc_algorithmic_dos(
        self,
        loc: int,
        raw_signals: Dict[str, int],
        mp: float,
        functions: List[Dict[str, Any]],
        popularity: int,
    ) -> float:
        """
        Calculates Algorithmic DoS Exposure based on Big-O depth, data gravity, and dependency bottlenecks.
        """
        if not functions:
            return 0.0

        dos_mass = 0.0

        for func in functions:
            depth = func.get("big_o_depth", 1)
            if depth < 2:
                continue

            # 1. The Base Threat (Exponential decay of performance)
            func_threat = float(depth**2)

            # 2. The Amplifiers (Network & Data Gravity)
            db_complex = func.get("db_complexity", 0)
            if db_complex > 0:
                func_threat *= 1.0 + (db_complex * 0.5)

            hv = func.get("hit_vector", {})
            api_hits = hv.get("api", 0)
            io_hits = hv.get("io", 0) + hv.get("sec_io", 0)
            flux_hits = hv.get("state_mutation", 0) + hv.get("globals", 0)

            choke_multiplier = 1.0 + api_hits + io_hits + flux_hits
            func_threat *= choke_multiplier

            # 3. The Dampeners (Guardrails)
            safety_hits = hv.get("safety", 0) + hv.get("panics_and_aborts", 0) + hv.get("cleanup", 0)
            if safety_hits > 0:
                func_threat *= 0.5  # 50% reduction for bounded iteration

            dos_mass += func_threat

        if dos_mass == 0.0:
            return 0.0

        # Apply File-Level Network Dampeners/Amplifiers
        network_multiplier = 1.0
        if popularity == 0 and raw_signals.get("api", 0) == 0:
            network_multiplier = 0.10  # Safely isolated orphan
        elif popularity > 0:
            network_multiplier = min(1.0 + (math.log1p(popularity) / 5.0), 3.0)

        total_threat_mass = dos_mass * network_multiplier

        # Fetch tuning parameters
        t = self.risk_tuning.get("algorithmic_dos", {})
        density = (total_threat_mass / max(loc + t.get("loc_padding", 150), 1)) * 100.0

        threshold = t.get("threshold_base", 15.0)
        slope = t.get("sigmoid_slope", 0.3)

        try:
            score = 100.0 / (1.0 + math.exp(-slope * (density - threshold)))
        except OverflowError:
            score = 100.0 if density > threshold else 0.0

        return min(score * mp, 100.0)

    # --------------------------------------------------------------------------
    # REPORTING UTILITIES
    # --------------------------------------------------------------------------

    def generate_forensic_report(self, parsed_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """[FORENSIC RANKING] Generates Top/Bottom 3 for dynamically indexed exposures."""
        if not parsed_files:
            return {}
        self.logger.info("Generating forensic exposure rankings...")

        # ====================================================================
        # THE ACTIVE LOGIC FILTER
        # 1. Define the structural assets that should be invisible to risk rankings
        # ====================================================================
        STRUCTURAL_ASSETS = self.asset_masks.get("STRUCTURAL_ASSETS", set())

        # 2. Filter the files to ONLY include active executable logic
        active_files = [
            file_data
            for file_data in parsed_files
            if file_data.get("lang_id", "unknown").lower() not in STRUCTURAL_ASSETS
        ]

        # 3. Fallback: If a repo is *only* markdown/data files, don't crash
        if not active_files:
            active_files = parsed_files

        # ====================================================================
        # NEW: CALCULATE CUMULATIVE RISK (Excluding Formatting Inconsistency)
        # ====================================================================
        civil_war_idx = self.RISK_SCHEMA.index("tabs_vs_spaces") if "tabs_vs_spaces" in self.RISK_SCHEMA else -1

        def get_cumulative_risk(f):
            rv = f.get("risk_vector", [])
            if not isinstance(rv, list):
                return 0.0
            # Sum all exposures except civil_war
            return sum(
                val for i, val in enumerate(rv) if i != civil_war_idx and i < len(rv) and isinstance(val, (int, float))
            )

        sorted_by_cumulative = sorted(active_files, key=get_cumulative_risk, reverse=True)

        # --- NEW: CALCULATE SYSTEMIC ARCHITECTURAL BOTTLENECKS ---
        flux_idx = self.RISK_SCHEMA.index("state_flux") if "state_flux" in self.RISK_SCHEMA else -1
        err_idx = self.RISK_SCHEMA.index("safety_score") if "safety_score" in self.RISK_SCHEMA else -1
        doc_idx = self.RISK_SCHEMA.index("documentation") if "documentation" in self.RISK_SCHEMA else -1

        bottlenecks = {
            "cascading_state_mutation": [],
            "fragile_dependency_chain": [],
            "undocumented_critical_path": [],
        }

        for file_data in active_files:
            net = file_data.get("telemetry", {}).get("network_metrics", {})
            raw_rv = file_data.get("risk_vector", [])
            rv = raw_rv if isinstance(raw_rv, list) else []
            p = file_data.get("path", "")

            btw = net.get("betweenness_score") or 0.0
            close = net.get("closeness_score") or 0.0
            pr = net.get("normalized_blast_radius") or 0.0

            flux_risk = (
                float(rv[flux_idx])
                if flux_idx >= 0 and len(rv) > flux_idx and isinstance(rv[flux_idx], (int, float))
                else 0.0
            )
            err_risk = (
                float(rv[err_idx])
                if err_idx >= 0 and len(rv) > err_idx and isinstance(rv[err_idx], (int, float))
                else 0.0
            )
            doc_risk = (
                float(rv[doc_idx])
                if doc_idx >= 0 and len(rv) > doc_idx and isinstance(rv[doc_idx], (int, float))
                else 0.0
            )

            bottlenecks["cascading_state_mutation"].append(
                {
                    "path": p,
                    "score": round(btw * flux_risk, 3),
                    "btw": round(btw, 4),
                    "state_mutation": flux_risk,
                }
            )
            bottlenecks["fragile_dependency_chain"].append(
                {
                    "path": p,
                    "score": round(close * err_risk, 3),
                    "close": round(close, 4),
                    "err": err_risk,
                }
            )
            bottlenecks["undocumented_critical_path"].append(
                {
                    "path": p,
                    "score": round(pr * doc_risk, 3),
                    "pr": round(pr, 4),
                    "doc": doc_risk,
                }
            )

        bottlenecks["cascading_state_mutation"].sort(key=lambda x: x["score"], reverse=True)
        bottlenecks["fragile_dependency_chain"].sort(key=lambda x: x["score"], reverse=True)
        bottlenecks["undocumented_critical_path"].sort(key=lambda x: x["score"], reverse=True)

        # 4. Generate rankings using ONLY the masked `active_files` list
        report = {
            "exposures": {},
            "file_impact": self._rank_list(active_files, key_path=["file_impact"]),
            "function_impact": self._generate_function_rankings(active_files),
            "systemic_bottlenecks": {k: v[:5] for k, v in bottlenecks.items()},
            # Inject the new Cumulative Risk ranking directly into the root of the report
            "cumulative_risk": {
                "highest": [
                    {
                        "name": f.get("name", "unknown"),
                        "path": f.get("path", ""),
                        "value": round(get_cumulative_risk(f), 2),
                    }
                    for f in sorted_by_cumulative[:10]
                ],
                "lowest": [
                    {
                        "name": f.get("name", "unknown"),
                        "path": f.get("path", ""),
                        "value": round(get_cumulative_risk(f), 2),
                    }
                    for f in reversed(sorted_by_cumulative[-3:])
                ],
            },
        }

        for idx, rk in enumerate(self.RISK_SCHEMA):
            report["exposures"][rk] = self._rank_list(active_files, key_path=["risk_vector", idx])

        return report

    def _get_locational_multipliers(self, path: str) -> Dict[str, float]:
        """Matches path against regex configurations and extracts applicable Modifiers."""
        active_multipliers = {}
        bridge = {
            "Cognitive Load Exposure": "cog",
            "Error & Exception Exposure": "safety",
            "Tech Debt Exposure": "debt",
            "Documentation Exposure": "doc",
            "Testing Exposure": "test",
            "Dead Code Exposure": "dead",
            "API Exposure": "api",
            "Concurrency Exposure": "async",
            "State Flux Exposure": "state_mutation",
            "Specification Exposure": "spec",
            "Churn Exposure": "churn",
            "Algorithmic DoS Exposure": "algorithmic_dos",
            # --- SECURITY LENSES ---
            "Obscured Payload Exposure": "obscured",
            "Logic Bomb Exposure": "logic_bomb",
            "Injection Vector Exposure": "injection",
            "Memory Corruption Exposure": "memory",
            "Hardcoded Secrets Exposure": "secrets",
        }

        for category, modifiers in self.path_modifiers.items():
            signal_key = bridge.get(category)
            if not signal_key:
                continue

            for pattern, multiplier in modifiers:
                if hasattr(pattern, "search") and pattern.search(path):
                    active_multipliers[signal_key] = multiplier
                    break
                elif isinstance(pattern, str) and re.search(pattern, path):
                    active_multipliers[signal_key] = multiplier
                    break

        return active_multipliers

    def _rank_list(self, parsed_files: List[Dict[str, Any]], key_path: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Extracts top and bottom ranks safely navigating dictionaries and lists."""

        def get_val(f):
            curr = f
            for k in key_path:
                if isinstance(curr, dict):
                    curr = curr.get(k, 0.0)
                elif isinstance(curr, list) and isinstance(k, int) and k < len(curr):
                    curr = curr[k]
                else:
                    return 0.0
            return float(curr) if isinstance(curr, (int, float)) else 0.0

        sorted_files = sorted(parsed_files, key=get_val, reverse=True)
        return {
            "highest": [
                {
                    "name": f.get("name", "unknown"),
                    "path": f.get("path", ""),
                    "value": get_val(f),
                }
                for f in sorted_files[:3]
            ],
            "lowest": [
                {
                    "name": f.get("name", "unknown"),
                    "path": f.get("path", ""),
                    "value": get_val(f),
                }
                for f in reversed(sorted_files[-3:])
            ],
        }

    def _generate_function_rankings(self, parsed_files: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        all_funcs = []
        for f in parsed_files:
            for func in f.get("functions", []):
                if isinstance(func, dict):
                    all_funcs.append(
                        {
                            "name": func.get("name", "anon"),
                            "file": f.get("name", "unknown"),
                            "impact": func.get("impact", 0),
                            "loc": func.get("loc", 0),
                        }
                    )
        all_funcs.sort(key=lambda x: x["impact"], reverse=True)
        return {
            "highest": all_funcs[:3],
            "lowest": all_funcs[-3:] if len(all_funcs) >= 3 else all_funcs,
        }

    def _get_tier(self, lang_id: str) -> str:
        explicit = {"rust", "go", "swift", "java", "typescript", "csharp", "dart"}
        structured = {"python", "javascript", "cpp", "c", "ruby", "kotlin", "php"}
        if lang_id in explicit:
            return "tier1"
        if lang_id in structured:
            return "tier2"
        return "tier3"

    def _get_dominant_lang(self, composition: Dict[str, Dict[str, Any]]) -> str:
        if not composition:
            return "mixed"
        # Sort by active structural impact instead of raw lines of code
        return max(composition.items(), key=lambda x: x[1].get("impact", 0.0))[0]
