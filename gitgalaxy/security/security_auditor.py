# ==============================================================================
# security_auditor.py
# GitGalaxy Phase 7.8: Advanced Machine Learning Threat Hunting (HARDENED)
# ==============================================================================
import logging
from pathlib import Path
from collections import deque

try:
    import numpy as np
    import pandas as pd
    import xgboost as xgb

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    import networkx as nx

    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS, AI_THREAT_THRESHOLD


class SecurityAuditor:
    """
    Machine Learning Threat Inference Engine.

    Calculates deep N-th degree dependency graphs to map the systemic Dependency Impact
    of every artifact. Passes the fused structural and topological context through
    a multi-class XGBoost classifier to identify behavioral signatures of malware
    (e.g., Trojans, Stealers, Droppers) that evade traditional static analysis.
    """

    # The taxonomy map for the Multiclass engine
    CLASS_NAMES = {
        0: "Safe Code",
        1: "Botnet / DDoS",
        2: "Stealer / Trojan",
        3: "Dropper / Webshell",
        4: "Native Infector",
    }

    # Updated default to the new multiclass model
    def __init__(self, model_path="gitgalaxy_malware_xgb_multiclass.json", parent_logger=None):
        self.logger = parent_logger.getChild("ml_auditor") if parent_logger else logging.getLogger("ml_auditor")

        # Load the Universal Schemas to map the raw vectors back to names
        self.SIGNAL_SCHEMA = RECORDING_SCHEMAS.get("SIGNAL_SCHEMA", [])

        # Fetch the dynamic threshold from standards (default to 90.0)
        self.ai_threshold = AI_THREAT_THRESHOLD

        if not self.SIGNAL_SCHEMA:
            self.logger.critical(
                "🚨 SIGNAL_SCHEMA is empty! ML feature extraction will fail. Check gitgalaxy_standards_v1.py."
            )

        self.model = None
        self.feature_names = []

        if ML_AVAILABLE:
            # DEFENSIVE GUARD: Bulletproof Path Resolution
            local_model = Path(__file__).parent / model_path
            util_model = Path(__file__).parent.parent / "utilities" / model_path

            model_file = local_model if local_model.exists() else util_model

            if model_file.exists():
                try:
                    self.model = xgb.XGBClassifier()
                    self.model.load_model(str(model_file))
                    self.feature_names = self.model.feature_names_in_

                    if not len(self.feature_names):
                        self.logger.error(
                            "❌ XGBoost model loaded, but feature names are empty. Model may be corrupted."
                        )
                        self.model = None
                    else:
                        self.logger.info(f"🧠 XGBoost Threat Model loaded successfully from: {model_file.resolve()}")
                except Exception as e:
                    self.logger.error(f"❌ Failed to load XGBoost model. File exists but threw an error: {e}")
            else:
                self.logger.warning(
                    f"⚠️ XGBoost model not found at {local_model} OR {util_model}. Running graph resolution only."
                )
        else:
            self.logger.warning("⚠️ Pandas or XGBoost not installed in this environment. Running graph resolution only.")

    def audit_repository(self, artifacts, is_shadow_patch=False):
        """
        Orchestrates the resolution of transitive dependency graphs and
        executes the XGBoost model against the generated feature matrix.
        """
        if not artifacts:
            return artifacts

        self.logger.info("Resolving N-th degree dependency graphs...")
        try:
            artifacts = self._resolve_dependency_graph(artifacts)
        except Exception as e:
            self.logger.error(
                f"❌ Catastrophic failure during dependency graph resolution: {e}",
                exc_info=True,
            )

        if not self.model:
            self.logger.warning("Skipping ML Threat Inference (Model not loaded).")
            return artifacts

        self.logger.info("Executing XGBoost Threat Inference across all artifacts...")

        try:
            # 1. Build the DataFrame matching the exact extraction schema used during training
            df = self._construct_feature_matrix(artifacts)

            if df.empty:
                self.logger.warning("Feature matrix is empty after extraction. Aborting inference.")
                return artifacts

            # 2. DEFENSIVE GUARD: Schema Alignment
            # Reindex to guarantee columns match the exact training schema. 
            # We use np.nan to explicitly preserve missing data for XGBoost decision trees.
            X = df.reindex(columns=self.feature_names, fill_value=np.nan)

            # 3. Ultimate Sanitization: Ensure no Inf values choke XGBoost, but preserve NaN
            X = X.replace([np.inf, -np.inf], np.nan)

            # 4. Predict MULTICLASS Probabilities
            probabilities = self.model.predict_proba(X)

            # 5. Sanity Check: Ensure index alignment between predictions and input data
            if len(probabilities) != len(artifacts):
                self.logger.error(
                    f"❌ FATAL DESYNC: Model returned {len(probabilities)} predictions for {len(artifacts)} artifacts. Aborting injection."
                )
                return artifacts

            # 6. Inject threat classification back into artifact RAM state
            threats_found = 0
            for i, artifact in enumerate(artifacts):
                probs_row = probabilities[i]

                # Find the index (0-4) with the highest probability
                predicted_class = int(np.argmax(probs_row))
                ml_score = round(float(probs_row[predicted_class]) * 100.0, 2)

                # ---> THE SHADOW PATCH OVERRIDE <---
                # If a file's hash mutated without a version bump (detected by the Pipeline Orchestrator),
                # and the file has actual structural mass (not just a 1-line whitespace change),
                # we forcefully override the ML model to flag it as a Trojan.
                if is_shadow_patch and artifact.get("file_impact", 0.0) > 0.5:
                    predicted_class = 2  # Force it to "Stealer / Trojan"
                    ml_score = 100.0
                    if "domain_context" not in artifact["telemetry"]:
                        artifact["telemetry"]["domain_context"] = {}
                    artifact["telemetry"]["domain_context"]["alert"] = (
                        "SHADOW PATCH: Hash mutated without version bump!"
                    )

                # ---> NEW: The Machine Learning Assembly & Static Asset Shield <---
                # XGBoost falsely flags raw Assembly, inert static files (Markdown/JSON), 
                # and Legacy ecosystems (Perl/Templates) as obfuscated Droppers 
                # due to their lack of modern cyclomatic complexity or extreme density.
                lang = str(artifact.get("lang_id", "")).lower()
                if lang in {
                    "assembly", "agc_assembly", "markdown", "plaintext", 
                    "json", "yaml", "csv", "xml", "toml", "ini", "properties", "text",
                    "perl", "template", "html", "css"
                }:
                    ml_score = 0.0
                    predicted_class = 0

                is_threat = predicted_class > 0 and ml_score >= self.ai_threshold

                if "domain_context" not in artifact["telemetry"]:
                    artifact["telemetry"]["domain_context"] = {}

                if is_threat:
                    threat_name = self.CLASS_NAMES.get(predicted_class, "Unknown Threat")
                    artifact["telemetry"]["domain_context"]["AI Threat Class"] = threat_name
                    artifact["telemetry"]["domain_context"]["AI Threat Confidence"] = f"{ml_score}%"
                    artifact["is_ml_threat"] = True
                    threats_found += 1
                    self.logger.debug(f"🚨 AI THREAT DETECTED: {artifact.get('path')} ({threat_name} | {ml_score}%)")
                else:
                    artifact["is_ml_threat"] = False

            self.logger.info(f"XGBoost Inference Complete. Found {threats_found} potential threats.")

        except Exception as e:
            self.logger.error(f"❌ Fatal error during XGBoost Inference: {e}", exc_info=True)

        return artifacts

    def _resolve_dependency_graph(self, artifacts):
        """
        Resolves transitive fragility and Downstream Exposure using C-optimized traversals (NetworkX)
        if available, falling back to a pure Python BFS deque if missing.
        """
        resolution_map = {}
        for artifact in artifacts:
            p = artifact.get("path", "")
            name = artifact.get("name", Path(p).name)
            stem = Path(p).stem
            if p:
                resolution_map[p] = p
            if name:
                resolution_map[name] = p
            if stem:
                resolution_map[stem] = p

        total_repo_files = max(len(artifacts), 1)

        # =========================================================
        # FAST PATH: NetworkX (C-Backend)
        # =========================================================
        if HAS_NETWORKX:
            G = nx.DiGraph()
            for artifact in artifacts:
                curr = artifact.get("path", "")
                G.add_node(curr)
                for imp in artifact.get("raw_imports", []):
                    if imp in resolution_map:
                        target = resolution_map[imp]
                        if target != curr:
                            G.add_edge(curr, target)

            for artifact in artifacts:
                path = artifact.get("path", "")
                dir_up = len(artifact.get("raw_imports", []))
                dir_down = artifact.get("telemetry", {}).get("popularity", 0)

                if path in G:
                    # Cap depth at 500 to prevent OOM/Stalls on massive circular monoliths
                    tot_up = min(len(nx.descendants(G, path)), 500)
                    tot_down = min(len(nx.ancestors(G, path)), 500)
                else:
                    tot_up, tot_down = 0, 0

                artifact["dependency_network"] = {
                    "direct_upstream": dir_up,
                    "direct_downstream": dir_down,
                    "total_upstream": tot_up,
                    "total_downstream": tot_down,
                    "upstream_ratio": round(tot_up / total_repo_files, 4),
                    "downstream_ratio": round(tot_down / total_repo_files, 4),
                }
            return artifacts

        # =========================================================
        # FALLBACK PATH: Pure Python (Deque Optimized)
        # =========================================================
        outbound_graph = {artifact.get("path", ""): [] for artifact in artifacts}
        inbound_graph = {artifact.get("path", ""): [] for artifact in artifacts}

        for artifact in artifacts:
            curr = artifact.get("path", "")
            for imp in artifact.get("raw_imports", []):
                if imp in resolution_map:
                    target = resolution_map[imp]
                    if target != curr:
                        if target not in outbound_graph[curr]:
                            outbound_graph[curr].append(target)
                        if curr not in inbound_graph[target]:
                            inbound_graph[target].append(curr)

        def get_nth_degree(start, graph, max_nodes=500):
            """BFS using collections.deque for O(1) popping."""
            visited = set()
            queue = deque([start])  # <--- THE O(1) MEMORY FIX
            while queue and len(visited) < max_nodes:
                node = queue.popleft()  # <--- No more O(N) array shifts!
                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            return len(visited)

        for artifact in artifacts:
            path = artifact.get("path", "")
            dir_up = len(artifact.get("raw_imports", []))
            dir_down = artifact.get("telemetry", {}).get("popularity", 0)

            # Reduced max_nodes to 500 to match NetworkX ceiling
            tot_up = get_nth_degree(path, outbound_graph, max_nodes=500)
            tot_down = get_nth_degree(path, inbound_graph, max_nodes=500)

            artifact["dependency_network"] = {
                "direct_upstream": dir_up,
                "direct_downstream": dir_down,
                "total_upstream": tot_up,
                "total_downstream": tot_down,
                "upstream_ratio": round(tot_up / total_repo_files, 4),
                "downstream_ratio": round(tot_down / total_repo_files, 4),
            }

        return artifacts

    def _construct_feature_matrix(self, artifacts):
        """Reconstructs the Pandas DataFrame exactly as train_threat_model.py did."""
        rows = []

        # Variables excluded during XGBoost training to prevent overfitting or noise
        exclusion_list = {
            "hit_structural_tab_indentations",
            "hit_structural_space_indentations",
            "hit_indentation_faction",
            "hit_manual_memory_allocation",
            "hit_asynchronous_concurrent_execution",
            "hit_sec_tainted_injection",
            "hit_embedded_credentials_and_keys",
            "hit_non_standard_unicode_homoglyphs",
            "hit_dynamic_code_execution_eval_exec",
            "hit_high_entropy_obfuscated_logic",
            "hit_raw_memory_manipulation",
            "hit_safety_and_constraint_bypasses",
            "hit_external_network_and_i_o_hooks",
            "hit_global_environment_mutation",
            "hit_commented_out_executable_logic",
            "hit_low_level_bitwise_cryptographic_math",
            "hit_non_standard_steganographic_imports",
        }

        for artifact in artifacts:
            try:
                tel = artifact.get("telemetry", {})
                dep = artifact.get("dependency_network", {})
                hits = artifact.get("hit_vector", [0] * len(self.SIGNAL_SCHEMA))

                # 1. Base Variables
                cfr = tel.get("control_flow_ratio", 0.0)
                coding_loc = artifact.get("coding_loc", 0)
                logic_loc = max(int(round(coding_loc * cfr)), 1)
                safe_denom = max(logic_loc, coding_loc, 1)

                functions = artifact.get("functions", [])
                max_func_comp = max([func.get("branch", 0) for func in functions] if functions else [0])
                avg_func_args = sum([func.get("args", 0) for func in functions]) / max(len(functions), 1)

                hit_dict = {self.SIGNAL_SCHEMA[i]: hits[i] for i in range(len(self.SIGNAL_SCHEMA)) if i < len(hits)}

                # 2. Build the Row Dictionary
                row = {
                    "language": str(artifact.get("lang_id", "unknown")).lower(),
                    "structural_mass": float(artifact.get("file_impact", 0.0)),
                    "cog_raw": float(tel.get("densities", {}).get("cog_raw", 0.0)),
                    "ownership_entropy": float(tel.get("ownership_entropy", 0.0)),
                    "silo_risk": float(tel.get("author_distribution", 0.0)),
                    "control_flow_ratio": float(cfr),
                    "popularity": int(dep.get("direct_downstream", 0)),
                    "import_count": int(dep.get("direct_upstream", 0)),
                    # Log Transforms (np.maximum prevents log(-X) math errors)
                    "log_logic_loc": np.log1p(np.maximum(logic_loc, 0)),
                    "log_max_func_complexity": np.log1p(np.maximum(max_func_comp, 0)),
                    "log_avg_func_args": np.log1p(np.maximum(avg_func_args, 0)),
                    "func_complexity_gini": float(tel.get("func_complexity_gini", 0.0)),
                    "func_internal_density": float(tel.get("func_internal_density", 0.0)),
                    "orphaned_logic": float(hit_dict.get("orphaned_logic", 0)),
                    "duplicate_logic": float(hit_dict.get("duplicate_logic", 0)),
                    "log_direct_upstream": np.log1p(np.maximum(dep.get("direct_upstream", 0), 0)),
                    "log_direct_downstream": np.log1p(np.maximum(dep.get("direct_downstream", 0), 0)),
                    "log_total_upstream": np.log1p(np.maximum(dep.get("total_upstream", 0), 0)),
                    "log_total_downstream": np.log1p(np.maximum(dep.get("total_downstream", 0), 0)),
                }

                # 3. Reconstruct Density Signatures
                for key, val in hit_dict.items():
                    col_name = f"hit_{key}"
                    if col_name not in exclusion_list:
                        raw_density = (val / safe_denom) * 100.0
                        row[f"log_density_{col_name}"] = np.log1p(np.maximum(raw_density, 0))

                # 4. Contextual/Mitigation Columns
                contextual = [
                    (
                        "raw_danger",
                        hit_dict.get("high_risk_execution", 0) + hit_dict.get("sec_high_risk_execution", 0),
                    ),
                    ("raw_sec_private_info", hit_dict.get("sec_hardcoded_secrets", 0)),
                    (
                        "raw_sec_tainted_injection",
                        hit_dict.get("sec_tainted_injection", 0),
                    ),
                ]
                for col_name, val in contextual:
                    raw_density = (val / safe_denom) * 100.0
                    row[f"log_density_{col_name}"] = np.log1p(np.maximum(raw_density, 0))

                # Bind to the new Ecosystem Baseline variables established in the Statistical Auditor
                row["assigned_macro_species"] = tel.get("ecosystem_baseline_cluster", 0)
                row["primary_z_score"] = float(tel.get("ecosystem_z_score", 0.0))

                for i in range(11):
                    row[f"dist_to_{i}"] = float(tel.get(f"dist_to_{i}", 0.0))

                rows.append(row)

            except Exception as e:
                self.logger.error(
                    f"Feature extraction failed for '{artifact.get('path', 'Unknown')}': {e}. Injecting safe fallback vector."
                )
                rows.append({"language": "unknown", "structural_mass": 0.0})

        df = pd.DataFrame(rows)
        # One-Hot Encode Languages
        df = pd.get_dummies(df, columns=["language"], dummy_na=False)
        return df