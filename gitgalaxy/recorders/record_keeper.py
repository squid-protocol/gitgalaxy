# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore ai_guardrails, sec_db_hooks

import sqlite3
import json
import logging
import statistics
from pathlib import Path
from typing import List, Dict, Optional
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS


class RecordKeeper:
    """
    SQLite Telemetry Recorder.

    PURPOSE: Transforms the live RAM state directly into a highly relational
    SQLite database. Bypasses the need for intermediate JSON parsing and creates
    a time-series schema perfectly aligned for Enterprise Data Warehouse (EDW) aggregation.
    """

    def __init__(self, parent_logger: Optional[logging.Logger] = None):
        self.logger = parent_logger.getChild("record_keeper") if parent_logger else logging.getLogger("record_keeper")

        schemas = RECORDING_SCHEMAS
        self.RISK_SCHEMA = schemas.get("RISK_SCHEMA", [])
        self.SIGNAL_SCHEMA = schemas.get("SIGNAL_SCHEMA", [])

        # The Taxonomy Map (Enforces structural schema consistency)
        self.SHORT_KEY_MAP = {
            "branch": "struct_branch",
            "structural_boundaries": "struct_linear",
            "args": "struct_args",
            "func_start": "struct_func_start",
            "class_start": "struct_class_start",
            "closures": "struct_closures",
            "comprehensions": "struct_comprehensions",
            "macros": "struct_macros",
            "decorators": "struct_decorators",
            "generics": "struct_generics",
            "core_var_decl": "struct_var_decl",
            "indent_tabs": "struct_tabs",
            "indent_spaces": "struct_spaces",
            "design_camel_case": "struct_camel_case",
            "design_snake_case": "struct_snake_case",
            "design_pascal_case": "struct_pascal_case",
            "design_upper_case": "struct_upper_case",
            "design_short_vars": "struct_short_vars",
            "design_long_vars": "struct_long_vars",
            "state_mutation": "state_flux",
            "high_risk_execution": "state_danger",
            "dead_code": "state_graveyard",
            "safety_bypasses": "state_safety_neg",
            "orphaned_logic": "state_slop_orphans",
            "duplicate_logic": "state_slop_duplicates",
            "planned_debt": "state_planned_debt",
            "fragile_debt": "state_fragile_debt",
            "panics_and_aborts": "state_bailout_hits",
            "thread_sleeps": "state_halt_hits",
            "reflection_metaprogramming": "state_heat_triggers",
            "pointers": "state_pointers",
            "memory_alloc": "state_memory_alloc",
            "explicit_casts": "state_cast_hits",
            "debug_prints": "state_print_hits",
            "io": "arch_io",
            "api": "arch_api",
            "concurrency": "arch_concurrency",
            "import": "arch_import",
            "ui_framework": "arch_ui_framework",
            "globals": "arch_globals",
            "ipc_rpc_bridges": "arch_ipc",
            "ssr_boundaries": "arch_ssr_boundaries",
            "events": "arch_events",
            "scientific": "arch_scientific",
            "dependency_injection": "arch_dependency_injection",
            "hardware_bridge": "arch_hardware",
            "cryptography": "arch_crypto",
            "serialization_parsing": "arch_serialization",
            "regex_execution": "arch_regex",
            "time_date_logic": "arch_time",
            "feature_flags": "arch_feature_flags",
            "inline_asm": "arch_inline_asm",
            "safety": "def_safety",
            "immutability_locks": "def_freeze_hits",
            "cleanup": "def_cleanup",
            "sync_locks": "def_sync_locks",
            "test": "def_test",
            "test_skip": "def_test_skip",
            "doc": "def_doc",
            "listeners": "def_listeners",
            "encapsulation": "def_encapsulation",
            "auth_middleware": "def_auth",
            "telemetry": "def_telemetry",
            "ownership": "def_ownership",
            "spec_exposure": "def_spec_exposure",
            "lit_code_blocks": "lit_code_blocks",
            "lit_diagrams": "lit_diagrams",
            "lit_headers": "lit_headers",
            "lit_links": "lit_links",
            "sec_hardcoded_secrets": "threat_private_info",
            "sec_tainted_injection": "threat_tainted_injection",
            "sec_reflection_metaprogramming": "threat_obfuscated",
            "sec_bitwise_ops": "threat_crypto_math",
            "sec_extension_mismatch": "threat_extension_mismatch",
            "sec_entropy": "threat_entropy",
            "sec_high_risk_execution": "threat_eval_exec",
            "sec_safety_bypasses": "threat_bypasses",
            "sec_io": "threat_network_hooks",
            "sec_state_mutation": "threat_env_mutation",
            "sec_shadow_imports": "threat_stego_imports",
            "sec_homoglyphs": "threat_homoglyphs",
        }

    def record_mission(
        self,
        parsed_files: List[Dict],
        unparsable_files: List[Dict],
        summary: Dict,
        session_meta: Dict,
        output_path: str,
    ):
        """Builds the formal relational SQLite database directly from pipeline RAM state."""
        repo_name = session_meta.get("target", "Unknown")
        git_audit = session_meta.get("git_audit", {})
        commit_date = git_audit.get("latest_commit_date", "Unknown").split("T")[0]
        commit_hash = git_audit.get("commit_hash", "Unknown")

        db_file = Path(output_path)
        self.logger.debug(f"Record Keeper: Forging native SQLite database -> {db_file.name}")

        conn = sqlite3.connect(db_file)

        # DEFENSIVE GUARD: Performance & Integrity PRAGMAs
        # Write-Ahead Logging (WAL) and Relaxed Sync prevent the DB lockups common in parallel I/O.
        # Enforcing Foreign Keys guarantees isolated deletions don't orphan metadata rows.
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        # 1. DYNAMIC SCHEMA GENERATION
        risk_cols = [f"risk_{r.replace('-', '_')} REAL" for r in self.RISK_SCHEMA]
        hit_cols = [f"{self.SHORT_KEY_MAP.get(h, h)} INTEGER" for h in self.SIGNAL_SCHEMA]

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS repo_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_date TEXT,
                commit_hash TEXT,
                total_files INTEGER,
                total_excluded_artifacts INTEGER,
                total_loc INTEGER,
                total_coding_loc INTEGER,
                total_functions INTEGER,
                total_classes INTEGER,
                total_doc_files INTEGER,    
                total_build_files INTEGER,  
                total_config_files INTEGER, 
                total_test_files INTEGER,   
                typosquat_hits INTEGER,
                ecosystem_baseline TEXT,
                z_score REAL,
                avg_encapsulation_ratio REAL,
                avg_imports_per_file REAL,
                network_modularity REAL,
                network_assortativity REAL,
                network_cyclic_density REAL,
                network_avg_path_length REAL,
                network_articulation_points INTEGER,
                audit_shadow_apis INTEGER DEFAULT 0,
                audit_binary_anomalies INTEGER DEFAULT 0,
                audit_unknown_packages INTEGER DEFAULT 0,
                is_zero_dependency_mode INTEGER DEFAULT 0,
                {", ".join(hit_cols)},
                file_composition TEXT,
                UNIQUE(repo_name, commit_hash)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                folder_path TEXT,
                file_count INTEGER,
                total_loc INTEGER,
                total_coding_loc INTEGER,
                total_functions INTEGER,
                total_classes INTEGER,
                total_mass REAL,
                avg_cognitive_load REAL,
                avg_tech_debt REAL,
                max_cognitive_load REAL,
                max_tech_debt REAL,
                avg_churn_freq REAL,
                FOREIGN KEY(repo_name, commit_hash) REFERENCES repo_data(repo_name, commit_hash) ON DELETE CASCADE
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS file_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_date TEXT,
                commit_hash TEXT,
                file_name TEXT,
                file_path TEXT,
                parent_entity TEXT,
                language TEXT,
                directory_group TEXT,
                total_loc INTEGER,
                coding_loc INTEGER,
                structural_mass REAL,
                cog_raw REAL,
                ownership_entropy REAL,
                silo_risk REAL,
                raw_churn_freq REAL,
                popularity INTEGER,
                import_count INTEGER,
                pagerank_score REAL,
                normalized_blast_radius REAL,
                betweenness_score REAL,
                closeness_score REAL,
                producer_ratio REAL,
                ecosystem_role TEXT,
                control_flow_ratio REAL,
                function_count INTEGER,
                class_count INTEGER,
                func_complexity_vector TEXT,
                avg_func_loc REAL,
                avg_func_complexity REAL,
                max_func_complexity REAL,
                avg_func_args REAL,
                func_complexity_gini REAL,
                func_internal_density REAL,
                dependency_density REAL,
                encapsulation_ratio REAL,
                author TEXT,
                ai_threat_class TEXT,
                ai_threat_confidence REAL,
                func_z_max REAL DEFAULT 0.0, 
                func_z_mean REAL DEFAULT 0.0, 
                func_z_median REAL DEFAULT 0.0, 
                pct_z_above_5 REAL DEFAULT 0.0, 
                pct_z_above_15 REAL DEFAULT 0.0, 
                file_archetype TEXT, 
                file_fingerprint TEXT,
                ecosystem_baseline TEXT,
                repo_z_score REAL,
                max_algorithmic_complexity TEXT,
                max_db_complexity INTEGER,
                ai_threat_score REAL,
                is_malware INTEGER,
                has_credentials INTEGER,
                binary_anomaly INTEGER,
                obfuscation_flag INTEGER,
                token_mass INTEGER DEFAULT 0,
                financial_read_cost REAL DEFAULT 0.0,
                agentic_isolation_risk INTEGER DEFAULT 0,
                requires_hitl INTEGER DEFAULT 0,
                appsec_rce_funnel BOOLEAN DEFAULT 0,
                appsec_god_mode BOOLEAN DEFAULT 0,
                appsec_exfiltration BOOLEAN DEFAULT 0,
                hallucination_zone BOOLEAN DEFAULT 0,
                silent_mutation_risk BOOLEAN DEFAULT 0,
                {", ".join(risk_cols)},
                {", ".join(hit_cols)}
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                class_name TEXT,
                inheritance_parents TEXT,
                method_count INTEGER,
                state_entanglement REAL,
                lcom_score REAL,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS function_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                parent_class_id INTEGER,
                func_name TEXT,
                complexity INTEGER,
                loc INTEGER,
                args INTEGER,
                usage_status INTEGER,
                keyword_density REAL,
                func_archetype TEXT DEFAULT 'Unclassified',
                func_z_score REAL DEFAULT 0.0,
                big_o_depth INTEGER,
                is_recursive INTEGER,
                db_complexity INTEGER,
                docstring TEXT,
                calls_out_to TEXT,
                token_mass INTEGER DEFAULT 0,
                {", ".join(hit_cols)},
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """)

        # DEFENSIVE GUARD: Indexes to Prevent Cascade Delete Hangs
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_class_file_id ON class_data(file_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_file_id ON function_data(file_id);")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS excluded_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                file_path TEXT,
                extension TEXT,
                exclusion_reason TEXT,
                size_bytes INTEGER
            )
        """)

        # THE IDEMPOTENT WIPE: Ensures delta-scans don't duplicate rows for the same commit
        cursor.execute(
            "DELETE FROM file_data WHERE repo_name = ? AND commit_hash = ?",
            (repo_name, commit_hash),
        )
        cursor.execute(
            "DELETE FROM folder_data WHERE repo_name = ? AND commit_hash = ?",
            (repo_name, commit_hash),
        )

        # 2. INSERTION LOOP
        agg_total_loc = 0
        agg_coding_loc = 0
        agg_func_count = 0
        agg_import_count = 0
        agg_encapsulation = 0.0
        agg_hits = [0] * len(self.SIGNAL_SCHEMA)

        agg_doc_files = 0
        agg_build_files = 0
        agg_config_files = 0
        agg_test_files = 0

        # PERFORMANCE OPTIMIZATION: Global array for batched executemany inserts
        all_func_rows = []

        for file_data in parsed_files:
            tel = file_data.get("telemetry", {})
            functions = file_data.get("functions", [])

            # Function Mathematics
            func_count = len(functions)
            complexities = [int(f.get("branch", 0)) for f in functions]
            locs = [int(f.get("loc", 0)) for f in functions]
            args_list = [int(f.get("args", 0)) for f in functions]

            avg_comp = float(sum(complexities) / func_count) if func_count > 0 else 0.0
            max_comp = float(max(complexities)) if func_count > 0 else 0.0
            avg_loc = float(sum(locs) / func_count) if func_count > 0 else 0.0
            avg_args = float(sum(args_list) / func_count) if func_count > 0 else 0.0
            func_comp_vector = json.dumps(complexities)

            # Z-SCORE CALCULATOR FOR STRUCTURAL OUTLIERS
            func_z_max = 0.0
            func_z_mean = 0.0
            func_z_median = 0.0
            pct_z_above_5 = 0.0
            pct_z_above_15 = 0.0
            z_scores = []

            if func_count > 0:
                mean_comp = statistics.mean(complexities)
                std_comp = statistics.pstdev(complexities) if func_count > 1 else 0.0

                for c in complexities:
                    z = (c - mean_comp) / std_comp if std_comp > 0 else 0.0
                    z_scores.append(round(z, 3))

                if z_scores:
                    func_z_max = max(z_scores)
                    func_z_mean = statistics.mean(z_scores)
                    func_z_median = statistics.median(z_scores)
                    pct_z_above_5 = (sum(1 for c in complexities if c >= 5) / func_count) * 100.0
                    pct_z_above_15 = (sum(1 for c in complexities if c >= 15) / func_count) * 100.0

            func_internal_density = (avg_comp / avg_loc) if avg_loc > 0 else 0.0

            logic_loc_denom = max(
                int(file_data.get("coding_loc", 1) * tel.get("control_flow_ratio", 0.0)),
                1,
            )
            import_count = len(file_data.get("raw_imports", []))
            dependency_density = import_count / float(logic_loc_denom)

            ai_threat_conf_str = tel.get("domain_context", {}).get(
                "AI Threat Confidence",
                tel.get("domain_context", {}).get("AI Threat Score", "0.0%"),
            )
            ai_threat = float(str(ai_threat_conf_str).replace("%", "")) if ai_threat_conf_str else 0.0
            ai_threat_class = tel.get("domain_context", {}).get("AI Threat Class", "Safe")
            encapsulation_ratio = float(tel.get("encapsulation_ratio", 1.0))

            rv = file_data.get("risk_vector", [0.0] * len(self.RISK_SCHEMA))
            hv = file_data.get("hit_vector", [0] * len(self.SIGNAL_SCHEMA))

            file_archetype = tel.get("archetype", "Unknown")
            file_fingerprint_str = json.dumps(tel.get("archetype_fingerprint", {}))

            agg_total_loc += file_data.get("total_loc", 0)
            agg_coding_loc += file_data.get("coding_loc", 0)
            agg_func_count += func_count
            agg_import_count += import_count
            agg_encapsulation += encapsulation_ratio
            for i, val in enumerate(hv):
                if i < len(agg_hits):
                    agg_hits[i] += val

            # Tallying Infrastructure Categories
            lang = file_data.get("lang_id", "unknown").lower()
            path_str = file_data.get("path", "").lower()

            if lang in ("markdown", "plaintext", "rst", "asciidoc"):
                agg_doc_files += 1
            elif lang in (
                "dockerfile",
                "makefile",
                "cmake",
                "shell",
                "batch",
                "powershell",
            ):
                agg_build_files += 1
            elif lang in ("json", "yaml", "toml", "xml", "ini", "csv", "properties"):
                agg_config_files += 1

            if "/test" in path_str or "test_" in path_str or "_test" in path_str or ".test." in path_str:
                agg_test_files += 1

            # --- SECURITY EXTRACTIONS ---
            raw_ai_score = file_data.get(
                "ai_threat_score",
                tel.get("domain_context", {}).get("AI Threat Score", 0.0),
            )
            try:
                ai_score = float(str(raw_ai_score).replace("%", ""))
            except ValueError:
                ai_score = 0.0

            is_malware = 1 if file_data.get("is_malware", False) else 0
            has_creds = 1 if file_data.get("has_credentials", False) else 0
            bin_anomaly = 1 if file_data.get("binary_anomaly", False) else 0
            obfuscation_flag = 1 if file_data.get("glassworm_flag", False) else 0

            # --- NETWORK TOPOLOGY EXTRACTION ---
            net_mets = tel.get("network_metrics", {})
            
            if session_meta.get("zero_dependency_mode"):
                ai_score = None
                pagerank_score = None
                blast_radius = None
                betweenness_score = None
                closeness_score = None
                producer_ratio = None
                ecosystem_role = None
            else:
                pagerank_score = net_mets.get("pagerank_score", 0.0)
                blast_radius = net_mets.get("normalized_blast_radius", 0.0)
                betweenness_score = net_mets.get("betweenness_score", 0.0)
                closeness_score = net_mets.get("closeness_score", 0.0)
                producer_ratio = net_mets.get("producer_ratio", 0.0)
                ecosystem_role = net_mets.get("ecosystem_role", "Unknown")

            class_idx = self.SIGNAL_SCHEMA.index("class_start") if "class_start" in self.SIGNAL_SCHEMA else -1
            class_count = hv[class_idx] if class_idx >= 0 and class_idx < len(hv) else 0

            repo_macro = tel.get("repo_macro_species", "Unknown")
            repo_z = tel.get("repo_z_score", 0.0)
            parent_ent = tel.get("domain_context", {}).get("parent_entity", "")

            # --- AI GUARDRAILS & TOKEN DENSITY ---
            guardrails = tel.get("ai_guardrails", {})
            appsec = tel.get("ai_appsec", {})

            is_black_hole = 1 if guardrails.get("is_agentic_black_hole") else 0
            req_hitl = 1 if guardrails.get("requires_hitl") else 0
            hallucination_zone = 1 if guardrails.get("hallucination_zone") else 0
            silent_mutation = 1 if guardrails.get("silent_mutation_risk") else 0

            rce_funnel = 1 if appsec.get("is_rce_funnel") else 0
            god_mode = 1 if appsec.get("over_permissioned_agent") else 0
            exfiltration = 1 if appsec.get("agentic_exfiltration_risk") else 0

            file_token_mass = file_data.get("token_mass")
            file_read_cost = file_data.get("financial_read_cost")

            row_data = [
                repo_name,
                commit_date,
                commit_hash,
                Path(file_data.get("path", "")).name,
                file_data.get("path", ""),
                parent_ent,
                file_data.get("lang_id", "unknown"),
                file_data.get("directory_group", "__monolith__"),
                file_data.get("total_loc", 0),
                file_data.get("coding_loc", 0),
                file_data.get("file_impact", 0.0),
                tel.get("densities", {}).get("cog_raw", 0.0),
                tel.get("ownership_entropy", 0.0),
                tel.get("author_distribution", 0.0),
                tel.get("raw_churn_freq", 0.0),
                tel.get("popularity", 0),
                import_count,
                pagerank_score,
                blast_radius,
                betweenness_score,
                closeness_score,
                producer_ratio,
                ecosystem_role,
                tel.get("control_flow_ratio", 0.0),
                func_count,
                class_count,
                func_comp_vector,
                avg_loc,
                avg_comp,
                max_comp,
                avg_args,
                tel.get("func_complexity_gini", 0.0),
                func_internal_density,
                dependency_density,
                encapsulation_ratio,
                tel.get("ownership", "Unknown"),
                ai_threat_class,
                ai_threat,
                func_z_max,
                func_z_mean,
                func_z_median,
                pct_z_above_5,
                pct_z_above_15,
                file_archetype,
                file_fingerprint_str,
                repo_macro,
                repo_z,
                tel.get("max_algorithmic_complexity", "O(N)"),
                int(tel.get("max_db_complexity", 0)),
                ai_score,
                is_malware,
                has_creds,
                bin_anomaly,
                obfuscation_flag,
                file_token_mass,
                file_read_cost,
                is_black_hole,
                req_hitl,
                rce_funnel,
                god_mode,
                exfiltration,
                hallucination_zone,
                silent_mutation,
            ]

            row_data.extend(rv)
            row_data.extend(hv)

            placeholders = ",".join(["?"] * len(row_data))

            cursor.execute(
                f"""
                INSERT INTO file_data (
                    repo_name, commit_date, commit_hash, file_name, file_path, parent_entity, language, directory_group, 
                    total_loc, coding_loc, structural_mass, cog_raw, ownership_entropy, silo_risk, 
                    raw_churn_freq, popularity, import_count, pagerank_score, normalized_blast_radius, betweenness_score, closeness_score, producer_ratio, ecosystem_role,
                    control_flow_ratio, function_count, class_count,
                    func_complexity_vector, avg_func_loc, avg_func_complexity, max_func_complexity, 
                    avg_func_args, func_complexity_gini, func_internal_density, dependency_density, encapsulation_ratio,
                    author, ai_threat_class, ai_threat_confidence, 
                    func_z_max, func_z_mean, func_z_median, pct_z_above_5, pct_z_above_15, 
                    file_archetype, file_fingerprint,
                    ecosystem_baseline, repo_z_score,
                    max_algorithmic_complexity, max_db_complexity,
                    ai_threat_score, is_malware, has_credentials, binary_anomaly, obfuscation_flag,
                    token_mass, financial_read_cost, agentic_isolation_risk, requires_hitl, appsec_rce_funnel, appsec_god_mode, appsec_exfiltration, hallucination_zone, silent_mutation_risk,
                    {", ".join([f"risk_{r.replace('-', '_')}" for r in self.RISK_SCHEMA])},
                    {", ".join([self.SHORT_KEY_MAP.get(h, h) for h in self.SIGNAL_SCHEMA])}
                ) VALUES ({placeholders})
            """,
                row_data,
            )

            file_id = cursor.lastrowid

            # 1. Extract and Insert Classes
            classes = file_data.get("classes", [])
            class_id_map = {}

            for cls in classes:
                cursor.execute(
                    """
                    INSERT INTO class_data (
                        file_id, class_name, inheritance_parents, 
                        method_count, state_entanglement, lcom_score
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        file_id,
                        cls.get("name", "Unknown"),
                        json.dumps(cls.get("inheritance", [])),
                        cls.get("method_count", 0),
                        cls.get("state_entanglement", 0.0),
                        cls.get("lcom_score", 0.0),
                    ),
                )
                class_id_map[cls.get("name")] = cursor.lastrowid

            # 2. Extract and Accumulate Functions into Master Array
            for func in functions:
                raw_hv = func.get("hit_vector", {})
                func_hits = [int(raw_hv.get(h, 0)) for h in self.SIGNAL_SCHEMA]

                parent_class_name = func.get("parent_class_name")
                parent_class_id = class_id_map.get(parent_class_name) if parent_class_name else None

                all_func_rows.append(
                    [
                        file_id,
                        parent_class_id,
                        str(func.get("name", "unknown_function"))[:255],
                        int(func.get("branch", 0)),
                        int(func.get("loc", 0)),
                        int(func.get("args", 0)),
                        int(func.get("usage_status", 0)),
                        float(func.get("keyword_density", 0.0)),
                        func.get("archetype", "Unclassified"),
                        float(func.get("z_score", 0.0)),
                        int(func.get("big_o_depth", 1)),
                        1 if func.get("is_recursive", False) else 0,
                        int(func.get("db_complexity", 0)),
                        str(func.get("docstring", ""))[:2000],
                        json.dumps(func.get("calls_out_to", [])),
                        (int(func.get("token_mass")) if func.get("token_mass") is not None else None),
                    ]
                    + func_hits
                )

        # PERFORMANCE OPTIMIZATION: Execute all accumulated functions in a single transaction loop
        if all_func_rows:
            func_placeholders = ",".join(["?"] * len(all_func_rows[0]))
            cursor.executemany(
                f"""
                INSERT INTO function_data 
                (file_id, parent_class_id, func_name, complexity, loc, args, usage_status, keyword_density, func_archetype, func_z_score, big_o_depth, is_recursive, db_complexity, docstring, calls_out_to, token_mass, {", ".join([self.SHORT_KEY_MAP.get(h, h) for h in self.SIGNAL_SCHEMA])})
                VALUES ({func_placeholders})
            """,
                all_func_rows,
            )

        # 3. REPO DATA INSERTION
        class_start_idx = self.SIGNAL_SCHEMA.index("class_start") if "class_start" in self.SIGNAL_SCHEMA else -1
        total_classes = agg_hits[class_start_idx] if class_start_idx >= 0 else 0

        macro_info = summary.get("repo_macro_species", {})
        repo_composition_str = json.dumps(summary.get("composition", {}))

        total_files = len(parsed_files)
        total_unparsable = len(unparsable_files)

        avg_encapsulation = (agg_encapsulation / total_files) if total_files > 0 else 1.0
        avg_imports = (agg_import_count / total_files) if total_files > 0 else 0.0

        typosquat_count = summary.get("typosquat_hits", summary.get("summary", {}).get("typosquat_hits", 0))
        net_macro = summary.get("network_macro", {})
        audits = summary.get("ecosystem_audits", {})

        if session_meta.get("zero_dependency_mode"):
            net_modularity = None
            net_assortativity = None
            net_cyclic_density = None
            net_avg_path_length = None
            net_articulation_points = None
        else:
            net_modularity = net_macro.get("modularity", 0.0)
            net_assortativity = net_macro.get("assortativity", 0.0)
            net_cyclic_density = net_macro.get("cyclic_density", 0.0)
            net_avg_path_length = net_macro.get("avg_path_length", 0.0)
            net_articulation_points = net_macro.get("articulation_points", 0)

        repo_row_data = (
            [
                repo_name,
                commit_date,
                commit_hash,
                total_files,
                total_unparsable,
                agg_total_loc,
                agg_coding_loc,
                agg_func_count,
                total_classes,
                agg_doc_files,
                agg_build_files,
                agg_config_files,
                agg_test_files,
                typosquat_count,
                macro_info.get("name", "Unclassified"),
                float(macro_info.get("z_score", 0.0)),
                round(avg_encapsulation, 3),
                round(avg_imports, 3),
                net_modularity,
                net_assortativity,
                net_cyclic_density,
                net_avg_path_length,
                net_articulation_points,
                int(audits.get("api_mapper", {}).get("shadow_count", 0)),
                int(audits.get("xray", {}).get("anomalies_found", 0)),
                int(audits.get("firewall", {}).get("imports_unknown", 0)),
                1 if session_meta.get("zero_dependency_mode") else 0,
            ]
            + agg_hits
            + [repo_composition_str]
        )

        repo_placeholders = ",".join(["?"] * len(repo_row_data))
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO repo_data (
                repo_name, commit_date, commit_hash, total_files, total_excluded_artifacts, total_loc, total_coding_loc, 
                total_functions, total_classes, total_doc_files, total_build_files, total_config_files, total_test_files, 
                typosquat_hits, ecosystem_baseline, z_score,
                avg_encapsulation_ratio, avg_imports_per_file,
                network_modularity, network_assortativity, network_cyclic_density, network_avg_path_length, network_articulation_points,
                audit_shadow_apis, audit_binary_anomalies, audit_unknown_packages, is_zero_dependency_mode,
                {", ".join([self.SHORT_KEY_MAP.get(h, h) for h in self.SIGNAL_SCHEMA])},
                file_composition
            ) VALUES ({repo_placeholders})
        """,
            repo_row_data,
        )

        # 4. EXCLUDED ARTIFACTS INSERTION
        unparsable_rows = []
        for unparsable in unparsable_files:
            path = unparsable.get("path", "")
            ext = Path(path).suffix.lower() if "." in Path(path).name else "none"
            unparsable_rows.append(
                [
                    repo_name,
                    commit_hash,
                    path,
                    ext,
                    unparsable.get("reason", "Unknown"),
                    unparsable.get("size_bytes", 0),
                ]
            )

        if unparsable_rows:
            cursor.executemany(
                """
                INSERT INTO excluded_artifacts 
                (repo_name, commit_hash, file_path, extension, exclusion_reason, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                unparsable_rows,
            )

        # ==============================================================================
        # 5. FOLDER-LEVEL ROLLUP (MATERIALIZED PATH AGGREGATION)
        # ==============================================================================
        folder_stats = {}
        debt_idx = self.RISK_SCHEMA.index("tech_debt") if "tech_debt" in self.RISK_SCHEMA else -1

        for file_data in parsed_files:
            file_path = file_data.get("path", "")
            parts = file_path.split("/")[:-1]  # Strip the filename to get directories

            # Determine all parent paths (e.g., src/api/auth -> src, src/api, src/api/auth)
            paths_to_update = ["."] if not parts else []
            current_path = ""
            for part in parts:
                current_path = f"{current_path}/{part}" if current_path else part
                paths_to_update.append(current_path)

            loc = file_data.get("total_loc", 0)
            coding_loc = file_data.get("coding_loc", 0)
            mass = file_data.get("file_impact", 0.0)
            func_count = len(file_data.get("functions", []))
            class_count = len(file_data.get("classes", []))

            tel = file_data.get("telemetry", {})
            cog_raw = tel.get("densities", {}).get("cog_raw", 0.0)
            churn = tel.get("raw_churn_freq", 0.0)

            rv = file_data.get("risk_vector", [])
            tech_debt = rv[debt_idx] if debt_idx >= 0 and len(rv) > debt_idx else 0.0

            # Roll metrics upwards
            for p in paths_to_update:
                if p not in folder_stats:
                    folder_stats[p] = {
                        "file_count": 0,
                        "total_loc": 0,
                        "total_coding_loc": 0,
                        "total_functions": 0,
                        "total_classes": 0,
                        "total_mass": 0.0,
                        "cog_loads": [],
                        "tech_debts": [],
                        "churns": [],
                    }
                fs = folder_stats[p]
                fs["file_count"] += 1
                fs["total_loc"] += loc
                fs["total_coding_loc"] += coding_loc
                fs["total_functions"] += func_count
                fs["total_classes"] += class_count
                fs["total_mass"] += mass
                fs["cog_loads"].append(cog_raw)
                fs["tech_debts"].append(tech_debt)
                fs["churns"].append(churn)

        # Calculate Domain Averages and Insert
        folder_rows = []
        for f_path, stats in folder_stats.items():
            avg_cog = sum(stats["cog_loads"]) / len(stats["cog_loads"]) if stats["cog_loads"] else 0.0
            max_cog = max(stats["cog_loads"]) if stats["cog_loads"] else 0.0

            avg_debt = sum(stats["tech_debts"]) / len(stats["tech_debts"]) if stats["tech_debts"] else 0.0
            max_debt = max(stats["tech_debts"]) if stats["tech_debts"] else 0.0

            avg_churn = sum(stats["churns"]) / len(stats["churns"]) if stats["churns"] else 0.0

            folder_rows.append(
                (
                    repo_name,
                    commit_hash,
                    f_path,
                    stats["file_count"],
                    stats["total_loc"],
                    stats["total_coding_loc"],
                    stats["total_functions"],
                    stats["total_classes"],
                    round(stats["total_mass"], 2),
                    round(avg_cog, 3),
                    round(avg_debt, 3),
                    round(max_cog, 3),
                    round(max_debt, 3),
                    round(avg_churn, 3),
                )
            )

        if folder_rows:
            cursor.executemany(
                """
                INSERT INTO folder_data (
                    repo_name, commit_hash, folder_path, file_count, total_loc, total_coding_loc,
                    total_functions, total_classes, total_mass, avg_cognitive_load, avg_tech_debt,
                    max_cognitive_load, max_tech_debt, avg_churn_freq
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                folder_rows,
            )

        conn.commit()
        conn.close()
        self.logger.debug(
            f"Database sealed. Exported {len(parsed_files)} files and {len(folder_rows)} directory groups to {db_file.name}"
        )
