# ==============================================================================

# galaxyscope:ignore sec_db_hooks
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_db_hooks

# galaxyscope:ignore ai_guardrails, sec_db_hooks

import json
import logging
import math
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Optional, TypedDict, cast

from gitgalaxy.standards.analysis_lens import (
    ENGINE_CONSTANTS,
    GENERAL_FILE_INFERENCE_MODEL,
    GENERAL_FUNCTION_INFERENCE_MODEL,
    RECORDING_SCHEMAS,
    SURFACE_FAMILIES,
)

# #2705: per-function evidence-mass floor (see analysis_lens.ENGINE_CONSTANTS).
FUNC_EVIDENCE_MASS_FLOOR = float(cast("int", ENGINE_CONSTANTS["FUNC_EVIDENCE_MASS_FLOOR"]))
# #2655: per-file evidence-mass floor, the denominator every per-file density
# equation divides by. #2770 brought dependency_density under it.
EVIDENCE_MASS_FLOOR = float(cast("int", ENGINE_CONSTANTS["EVIDENCE_MASS_FLOOR"]))


# #3126: the FILE archetype brain's per-feature value sources. The builder in
# `_classify_file_archetype` dispatches on these kinds and `_prep_file_brain`
# validates against them, so the two cannot disagree about which FEATURE_NAMES
# the engine can actually compute -- the drift that used to turn a renamed
# trainer feature into a silent 0.0 column.
_FILE_FEATURE_ZSTATS = frozenset({"func_z_max", "func_z_mean", "func_z_median", "pct_z_above_5", "pct_z_above_15"})


def _file_feature_kind(feature_name: str) -> Optional[str]:
    """Which value source feeds this FEATURE_NAME, or None if the engine has none."""
    if feature_name == "log_coding_loc":
        return "coding_loc"
    if feature_name in _FILE_FEATURE_ZSTATS:
        return "zstat"
    if feature_name.startswith("log_micro_") and feature_name.endswith("_pct"):
        inner = feature_name[len("log_micro_") : -len("_pct")]
        return "micro" if inner.isdigit() else None
    if feature_name.startswith("log_density_"):
        return "density"
    if feature_name.startswith("log_"):
        return "precalc"
    return None


def _is_already_renamed(exc: sqlite3.OperationalError) -> bool:
    """#2806: is this ALTER ... RENAME COLUMN failure the benign already-done one?

    A fresh database is created with the current column names, so the rename
    finds "no such column"; a database migrated by an earlier run reports the
    new name as a "duplicate column name". Neither is an error; anything else is.
    """
    detail = str(exc).lower()
    return "no such column" in detail or "duplicate column name" in detail


def _ensure_columns(cursor: sqlite3.Cursor, table: str, col_defs: list[str]) -> None:
    """DEFENSIVE GUARD: Auto-Heal Schema Drift (gitgalaxy#2994).

    Generalizes the guarded-ALTER precedent already used for
    `is_zero_dependency_mode`/`repo_data` (below) into a loop: on a
    pre-existing DB from before this reform, `CREATE TABLE IF NOT EXISTS` is
    a no-op, so new columns must be healed in one at a time with ALTER
    TABLE. Safe on a freshly created DB too -- CREATE TABLE already added
    every column below, so each ALTER here just hits the benign "duplicate
    column name" branch and is skipped.

    `col_defs` is a list of "name TYPE" strings, the same shape as the
    risk_cols/hit_cols/fam_cols lists built in record_mission. `table` and
    every entry in `col_defs` are internal literals (schema-derived, never
    user input) -- SQLite has no parameterized syntax for column/table
    names, same as the CREATE TABLE f-strings elsewhere in this module.
    """
    for col_def in col_defs:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        except sqlite3.OperationalError as exc:  # noqa: PERF203 -- per-column isolation: one already-present column shouldn't abort healing the rest
            if "duplicate column name" in str(exc).lower():
                logging.getLogger("record_keeper").debug(
                    f"Schema migration skipped: '{table}.{col_def}' already exists."
                )
            else:
                raise


class FolderStats(TypedDict):
    """Accumulator shape for the folder-level rollup below -- without this,
    the mixed int/float/list values collapse to "object" under mypy, which
    then can't type-check the sum()/max()/append() calls that consume it."""

    file_count: int
    total_loc: int
    total_coding_loc: int
    total_functions: int
    total_classes: int
    total_mass: float
    cog_loads: list[float]
    tech_debts: list[float]
    churns: list[float]


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
        # gitgalaxy#2991: canonical new-name -> legacy risk_* mapping, bound
        # here for parity with the other 4 definition sites. Deliberately NOT
        # used to change the `risk_{r}` column names built below: this
        # recorder writes the persisted SQLite schema temporal-crucible
        # queries directly (docs/self_scan/gitgalaxy_master.db and every
        # downstream consumer), so the DB columns stay risk_* exactly,
        # unconditionally, per #2991's dual-emission requirement.
        self.VECTOR_NAMES = schemas.get("VECTOR_NAMES", {})
        # gitgalaxy#2994: Tier-1 declarative family map (analysis_lens.py
        # section 7b), bound here for the same reason VECTOR_NAMES is --
        # not part of RECORDING_SCHEMAS itself (a standalone top-level
        # constant), but travels with the rest of the schema wherever this
        # recorder is imported from.
        self.SURFACE_FAMILIES = SURFACE_FAMILIES

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
            "unreferenced_by_name": "state_unreferenced",
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
            "system_config_mutation": "arch_sys_config",
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
            # #2985: new columns, so naming them under the threat_* convention
            # costs no existing query. (The three pre-existing sec_* signals with
            # no entry here -- sec_dead_code, sec_unicode_steganography,
            # sec_self_propagation -- keep their raw column names deliberately:
            # mapping them now would RENAME a shipped column out from under the
            # temporal-crucible queries this schema exists to serve.)
            "sec_db_hooks": "threat_db_sinks",
            # gitgalaxy#3018: named for the SHAPE it measures, not a verdict. It was
            # briefly "threat_sql_injection" (#3017, one merge); measuring it found
            # ~0% precision -- fastapi's test_annotated.py, which contains no database
            # code at all, scored 13 "confirmed SQL injections" off FastAPI's `Query(`
            # parameter helper. An AST-less engine cannot prove a value reaches a query
            # (exactly #1020's reasoning), so the column may not claim that it did.
            "sec_amplified_sql_injection": "threat_api_near_db_sink",
        }

    def _prep_file_brain(self) -> None:
        """#ENGINE-PARITY: cache the self-describing FILE archetype brain contract.
        The engine builds the file vector strictly in FEATURE_NAMES order from the
        fully-computed file record (all metrics + the function->file composition
        rollup), so it can never drift from the trainer (cluster_files.py).

        #3126: building in FEATURE_NAMES order guarantees the ENGINE's half of
        that contract, but only if the brain's own scaler arrays and centroids
        agree with its FEATURE_NAMES -- which nothing checked. Every internal
        inconsistency is validated here, ONCE at boot, and an inconsistent
        brain is refused outright (`_file_brain = None`, caller keeps its
        fallback label) rather than classifying over whatever happens to line
        up. That is `signal_processor`'s posture -- "skipping classification
        rather than silently truncating", the principle #1157/#1158 set after
        the v2.8.0 three-way feature-space incident -- which this path did not
        inherit when #3061 moved classification here.
        """
        b = cast("dict[str, Any]", GENERAL_FILE_INFERENCE_MODEL)
        self._file_brain: Optional[dict[str, Any]] = None
        if not b.get("FEATURE_NAMES") or not b.get("SCALER_MEDIANS"):
            return
        ak = next((k for k in b if k.startswith("ARCHETYPES_K")), None)
        if ak is None:
            return
        names = b.get("cluster_names") or list(b.get(ak, {}).keys())

        # --- #3126 PARITY GATE: refuse an internally inconsistent brain ---
        feature_names = b["FEATURE_NAMES"]
        n = len(feature_names)
        centroids = list(b.get(ak, {}).values())
        weights = b.get("FEATURE_WEIGHTS", [1.0] * n)
        problems = []
        for key, arr in (
            ("SCALER_MEDIANS", b["SCALER_MEDIANS"]),
            ("SCALER_IQRS", b.get("SCALER_IQRS")),
            ("FEATURE_WEIGHTS", weights),
        ):
            if arr is None or len(arr) != n:
                problems.append(f"{key} has {None if arr is None else len(arr)} entries, expected {n}")
        bad_centroids = {i: len(c) for i, c in enumerate(centroids) if len(c) != n}
        if bad_centroids:
            problems.append(f"centroid dims {sorted(set(bad_centroids.values()))} != {n} FEATURE_NAMES")
        if len(names) != len(centroids):
            problems.append(f"{len(names)} cluster names for {len(centroids)} centroids")
        # An unrecognised feature name used to contribute a silent 0.0 column,
        # which kept the vector length correct and so evaded every length
        # check -- a renamed trainer feature became an invisible dead input.
        unknown = [fn for fn in feature_names if _file_feature_kind(fn) is None]
        if unknown:
            problems.append(f"FEATURE_NAMES the engine cannot compute: {unknown}")
        if problems:
            self.logger.warning(
                "FILE archetype brain is internally inconsistent; skipping file-archetype "
                "classification rather than classifying on a partial vector (#3126): %s",
                "; ".join(problems),
            )
            return

        self._file_brain = {
            "FEATURE_NAMES": b["FEATURE_NAMES"],
            "SCALER_MEDIANS": b["SCALER_MEDIANS"],
            "SCALER_IQRS": b["SCALER_IQRS"],
            "FEATURE_WEIGHTS": b.get("FEATURE_WEIGHTS", [1.0] * len(b["FEATURE_NAMES"])),
            "CAP_VALUES": b.get("CAP_VALUES", {}),
            "DNA_SOURCES": b.get("DNA_SOURCES", {}),
            "names": names,
            "centroids": list(b.get(ak, {}).values()),
        }
        self._file_sig_idx: dict[str, int] = {s: i for i, s in enumerate(self.SIGNAL_SCHEMA)}
        # function cluster order defines the micro_<i> composition index (verified
        # identical to the rollup order used to train the file model).
        fn_model = cast("dict[str, Any]", GENERAL_FUNCTION_INFERENCE_MODEL)
        self._func_name_to_idx: dict[str, int] = {n: i for i, n in enumerate(fn_model.get("cluster_names", []))}

    def _classify_file_archetype(self, ctx: dict, hv: list) -> Optional[str]:
        """Nearest-centroid file archetype from the assembled metrics, mirroring the
        offline apply_file_clusters. Returns the archetype name, or None if the brain
        is unavailable/degenerate (caller keeps its fallback label)."""
        if not hasattr(self, "_file_brain"):
            self._prep_file_brain()
        fb = self._file_brain
        if not fb:
            return None
        cl = float(ctx.get("coding_loc", 0.0) or 0.0)
        denom = cl if cl > 0 else 1.0
        micro = ctx.get("micro", {})
        precalc = ctx.get("precalc", {})
        dna = fb["DNA_SOURCES"]
        caps = fb["CAP_VALUES"]
        med, iqr, wts = fb["SCALER_MEDIANS"], fb["SCALER_IQRS"], fb["FEATURE_WEIGHTS"]
        vec = []
        # #3126: every length here is guaranteed equal by _prep_file_brain's
        # parity gate, so the scaler lookups index directly and the distance
        # loop below runs the FULL vector. The previous `med[i] if i < len(med)
        # else 0.0` / `min(len(vec), len(cen))` forms silently padded and
        # truncated instead, producing a confident label off a partial vector.
        for i, fn in enumerate(fb["FEATURE_NAMES"]):
            kind = _file_feature_kind(fn)
            if kind == "coding_loc":
                v = math.log1p(cl)
            elif kind == "zstat":
                v = float(ctx.get(fn, 0.0))
            elif kind == "micro":
                v = math.log1p(float(micro.get(int(fn[len("log_micro_") : -len("_pct")]), 0.0)))
            elif kind == "density":
                col = fn[len("log_density_") :]
                sidx = self._file_sig_idx.get(dna.get(fn, col))
                hit = float(hv[sidx]) if sidx is not None and sidx < len(hv) else 0.0
                raw = (hit / denom) * 100.0
                cap = caps.get(col)
                if cap is not None and raw > cap:
                    raw = cap
                v = math.log1p(raw)
            else:  # "precalc" -- the only remaining kind the gate admits
                v = math.log1p(float(precalc.get(fn[len("log_") :], 0.0)))
            q = iqr[i] if iqr[i] > 0 else 1.0
            vec.append(((v - med[i]) / q) * wts[i])
        best_i, best_d = -1, None
        for ci, cen in enumerate(fb["centroids"]):
            d = 0.0
            for j in range(len(vec)):
                diff = vec[j] - cen[j]
                d += diff * diff
            if best_d is None or d < best_d:
                best_d, best_i = d, ci
        return fb["names"][best_i] if 0 <= best_i < len(fb["names"]) else None

    def record_mission(
        self,
        parsed_files: list[dict],
        unparsable_files: list[dict],
        summary: dict,
        session_meta: dict,
        output_path: str,
        dependency_edges: Optional[list[dict]] = None,
    ):
        """
        Builds the formal relational SQLite database directly from pipeline RAM state.

        `dependency_edges` (#2992) is the network sensor's resolved edge list
        (`NetworkRiskSensor.dependency_edges`), persisted as edge_data. None --
        a caller with no graph -- writes no edges and leaves
        repo_data.network_edges_unrecorded NULL rather than a fake 0.
        """
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

        # gitgalaxy#2994: Tier-1/2/3 measurement columns, generated the same
        # dynamic way as risk_cols/hit_cols above. Canonical order used
        # consistently across CREATE TABLE, the guarded-ALTER heal, and the
        # INSERT below: families (raw sums, then their snapshot percentiles),
        # then the legacy-vector snapshot percentiles, then the relations.
        fam_cols = [f"fam_{fam} INTEGER" for fam in self.SURFACE_FAMILIES]
        pct_fam_cols = [f"pct_fam_{fam} REAL" for fam in self.SURFACE_FAMILIES]
        pct_vec_cols = [f"pct_vec_{r.replace('-', '_')} REAL" for r in self.RISK_SCHEMA]
        rel_cols = ["rel_guard_balance REAL", "rel_alloc_cleanup REAL"]
        tier_cols = fam_cols + pct_fam_cols + pct_vec_cols + rel_cols

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
                -- #2992: resolved graph edges left out of edge_data because an
                -- endpoint has no file_data row (see the edge_data insert).
                network_edges_unrecorded INTEGER,
                -- #1148: real producer (run_api_audit -> calculate_api_drift in
                -- full_api_network_map.py), but nonzero only when the repo ships exactly
                -- one auto-discoverable OpenAPI/Swagger spec AND has code endpoints missing
                -- from it. Near-zero across a general repo corpus is expected, not a bug --
                -- most repos have no machine-readable API spec at all.
                audit_shadow_apis INTEGER DEFAULT 0,
                audit_binary_anomalies INTEGER DEFAULT 0,
                audit_unknown_packages INTEGER DEFAULT 0,
                is_zero_dependency_mode INTEGER DEFAULT 0,
                -- #3028: JSON map of package -> missing, so snapshot history
                -- can tell WHICH optional engine a zero-dependency scan lacked.
                missing_dependencies TEXT,
                {", ".join(hit_cols)},
                file_composition TEXT,
                repo_composition_archetype TEXT,
                repo_composition_z REAL,
                UNIQUE(repo_name, commit_hash)
            )
        """)

        # DEFENSIVE GUARD: Auto-Heal Schema Drift
        try:
            cursor.execute("ALTER TABLE repo_data ADD COLUMN is_zero_dependency_mode INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            # Expected on existing databases where migration was already applied.
            if "duplicate column name" in str(exc).lower():
                self.logger.debug("Schema migration skipped: 'is_zero_dependency_mode' already exists.")
            else:
                raise
        _ensure_columns(cursor, "repo_data", ["missing_dependencies TEXT"])

        # gitgalaxy#2985: repo_data's half of the hit_cols heal (see file_data's
        # below for why the INSERTs make this mandatory, not merely tidy).
        _ensure_columns(cursor, "repo_data", hit_cols)
        # repo composition archetype (function-stoichiometry taxonomy) + its fit z-score
        _ensure_columns(cursor, "repo_data", ["repo_composition_archetype TEXT", "repo_composition_z REAL"])
        # #2992: same heal for a pre-#2992 repo_data.
        _ensure_columns(cursor, "repo_data", ["network_edges_unrecorded INTEGER"])

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
                doc_loc INTEGER,
                structural_mass REAL,
                cog_raw REAL,
                ownership_entropy REAL,
                silo_risk REAL,
                raw_churn_freq REAL,
                popularity INTEGER,
                import_count INTEGER,
                internal_dependency_links INTEGER,
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
                composition_file_archetype TEXT,
                composition_file_z REAL,
                ecosystem_baseline TEXT,
                repo_z_score REAL,
                ai_threat_score REAL,
                is_malware INTEGER,
                has_credentials INTEGER,
                binary_anomaly INTEGER,
                obfuscation_flag INTEGER,
                token_mass INTEGER DEFAULT 0,
                financial_read_cost REAL DEFAULT 0.0,
                agentic_isolation_risk INTEGER DEFAULT 0,
                requires_hitl INTEGER DEFAULT 0,
                appsec_god_mode BOOLEAN DEFAULT 0,
                hallucination_zone BOOLEAN DEFAULT 0,
                silent_mutation_risk BOOLEAN DEFAULT 0,
                raw_arch_api INTEGER DEFAULT 0,
                raw_state_unreferenced INTEGER DEFAULT 0,
                {", ".join(risk_cols)},
                {", ".join(hit_cols)},
                {", ".join(tier_cols)},
                mitigation_telemetry TEXT,
                doc_umbrella REAL DEFAULT 0.0,
                raw_imports TEXT
            )
        """)

        # DEFENSIVE GUARD: Auto-Heal Schema Drift (gitgalaxy#2994) -- a
        # pre-existing DB from before this reform already has file_data, so
        # CREATE TABLE IF NOT EXISTS above is a no-op for it; heal the new
        # fam_*/pct_fam_*/pct_vec_*/rel_* columns in with guarded ALTERs.
        _ensure_columns(cursor, "file_data", tier_cols)

        # #3220: mitigation_telemetry is the detector's proximity-correlation tally
        # (mitigated_danger / amplified_cascading_flux ...) that re-weights
        # cognitive_load / safety_score / state_flux in the score layer. It was never
        # persisted, so a delta scan's rehydrated files lost the amplification and those
        # three signals drifted. Persist it as JSON so StateRehydrator can restore an
        # exact score input. Guarded-ALTER heal for pre-existing DBs, same as above.
        _ensure_columns(cursor, "file_data", ["mitigation_telemetry TEXT"])

        # #3220: doc_umbrella (the documentation shield in meta["metadata"]) dampens
        # risk_documentation in _calc_documentation. It is a parse-time value never
        # persisted, so rehydrated files defaulted it to 0.0 and risk_documentation
        # drifted. Persist it so the rehydrator can restore the exact shield.
        _ensure_columns(cursor, "file_data", ["doc_umbrella REAL DEFAULT 0.0"])

        # #3220: raw_imports (the file's pre-resolution import target strings) is what
        # the graph resolver turns into edges. rehydrated files had it emptied, so the
        # delta graph missed every edge FROM an unchanged file -> in-degree (popularity)
        # of widely-imported headers was undercounted and risk_api_exposure drifted.
        # Persist the strings (JSON) so the rehydrator can feed the resolver exactly.
        _ensure_columns(cursor, "file_data", ["raw_imports TEXT"])

        # gitgalaxy#2985: the same guard, now over hit_cols. SIGNAL_SCHEMA grows
        # (it gained sec_db_hooks/sec_amplified_sql_injection here), and the
        # INSERTs below name every hit column explicitly -- so without this, the
        # first scan after a schema addition dies on a pre-existing DB with
        # "table file_data has no column named threat_db_sinks" and writes
        # nothing at all. Verified against a DB built by the previous release.
        # repo_data is healed further down, beside its own existing guarded
        # ALTER; class_data carries no hit columns.
        _ensure_columns(cursor, "file_data", hit_cols)
        # composition archetype (function-stoichiometry taxonomy) + its fit z-score
        _ensure_columns(cursor, "file_data", ["composition_file_archetype TEXT", "composition_file_z REAL"])

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                class_name TEXT,
                inheritance_parents TEXT,
                method_count INTEGER,
                state_entanglement REAL,
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
                start_line INTEGER,
                args INTEGER,
                usage_status INTEGER,
                keyword_density REAL,
                func_archetype TEXT DEFAULT 'Unclassified',
                func_z_score REAL DEFAULT 0.0,
                docstring TEXT,
                calls_out_to TEXT,
                token_mass INTEGER DEFAULT 0,
                is_public INTEGER DEFAULT 0,
                is_documented INTEGER DEFAULT 0,
                {", ".join(hit_cols)},
                impact REAL DEFAULT 0.0,
                FOREIGN KEY(file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """)

        # gitgalaxy#2985: function_data's half of the hit_cols heal.
        _ensure_columns(cursor, "function_data", hit_cols)

        # #3220: func["impact"] (round(magnitude,1)) is a parse-time per-function
        # structural weight _calc_verification reads to size untested impact. It was
        # never persisted, so rehydrated functions defaulted it to 0.0 and
        # risk_verification drifted. Persist it so a delta rehydrate reproduces it.
        _ensure_columns(cursor, "function_data", ["impact REAL DEFAULT 0.0"])

        # DEFENSIVE GUARD: Indexes to Prevent Cascade Delete Hangs
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_class_file_id ON class_data(file_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_file_id ON function_data(file_id);")

        # #2992: the dependency graph's edge list. The engine builds the full
        # file-to-file import graph every scan (network_risk_sensor) but used to
        # persist only per-node summaries of it (popularity, pagerank_score,
        # internal_dependency_links), so no neighbourhood question -- what do a
        # file's importers carry? -- was answerable from the DB. One row per
        # resolved (importer, imported) pair: repeated imports of the same target
        # collapse into one row that keeps count in import_statements (of which
        # entity_imports were the `from x import y` entity form); weight is the
        # value pagerank/betweenness read. edge_kind is 'import' today -- the
        # column exists so another relation (calls, test coverage) can share the
        # table later without a schema change. No FK to repo_data on purpose:
        # its INSERT OR REPLACE below would cascade-delete these rows.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edge_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT,
                commit_hash TEXT,
                src_file_id INTEGER,
                dst_file_id INTEGER,
                edge_kind TEXT DEFAULT 'import',
                weight REAL,
                import_statements INTEGER,
                entity_imports INTEGER,
                FOREIGN KEY(src_file_id) REFERENCES file_data(id) ON DELETE CASCADE,
                FOREIGN KEY(dst_file_id) REFERENCES file_data(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edge_src_file_id ON edge_data(src_file_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edge_dst_file_id ON edge_data(dst_file_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edge_snapshot ON edge_data(repo_name, commit_hash);")

        # #2908 Phase 2: per-unit is_public/is_documented (function_data.
        # docs/risk_documentation_contract.md). Auto-heal for a pre-#2908
        # database whose function_data table (the CREATE IF NOT EXISTS
        # above won't touch it) predates these columns -- same precedent as
        # file_data's doc_loc heal above.
        try:
            cursor.execute("ALTER TABLE function_data ADD COLUMN is_public INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                self.logger.debug("Schema migration skipped: 'is_public' already exists.")
            else:
                raise

        try:
            cursor.execute("ALTER TABLE function_data ADD COLUMN is_documented INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                self.logger.debug("Schema migration skipped: 'is_documented' already exists.")
            else:
                raise

        # #2625: file_data historically persisted only total_loc (blank-inclusive)
        # and coding_loc (blank-exclusive), forcing downstream consumers to
        # re-derive documentation mass as total_loc - coding_loc -- which silently
        # counts every BLANK line as documentation. prism.py's real doc_loc
        # (non-blank, non-code lines) is now persisted alongside them; this
        # ALTER heals pre-#2625 databases whose existing file_data table (the
        # CREATE IF NOT EXISTS above won't touch it) predates the column --
        # same auto-heal precedent as repo_data's is_zero_dependency_mode.
        # Runs AFTER the CREATE so a fresh database (table just created, column
        # already present) lands in the expected duplicate-column branch.
        try:
            cursor.execute("ALTER TABLE file_data ADD COLUMN doc_loc INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                self.logger.debug("Schema migration skipped: 'doc_loc' already exists.")
            else:
                raise

        # #2806: the signal these two columns record was called `orphaned_logic`
        # and stored as `state_slop_orphans` -- both names asserting the count
        # was dead weight ("slop"), when what it measures is that no other text
        # in the file names the function. The contract
        # (docs/unreferenced_by_name_contract.md) renamed the signal, and the
        # columns follow it so a DB query and an equations key cannot disagree
        # about what the number means. Pre-#2806 databases are renamed in place
        # rather than re-scanned: the values are unchanged, only the label was
        # wrong. Runs BEFORE the ADD COLUMN heals below, so an old database is
        # renamed rather than growing a second, empty raw column beside it.
        # One block per column, like the ADD COLUMN heals around it: "no such
        # column" means a fresh database already created with the current name,
        # "duplicate column name" means an already-migrated one.
        try:
            cursor.execute("ALTER TABLE file_data RENAME COLUMN state_slop_orphans TO state_unreferenced")
        except sqlite3.OperationalError as exc:
            if not _is_already_renamed(exc):
                raise
            self.logger.debug("Schema migration skipped: 'state_slop_orphans' is not present to rename.")

        try:
            cursor.execute("ALTER TABLE file_data RENAME COLUMN raw_state_slop_orphans TO raw_state_unreferenced")
        except sqlite3.OperationalError as exc:
            if not _is_already_renamed(exc):
                raise
            self.logger.debug("Schema migration skipped: 'raw_state_slop_orphans' is not present to rename.")

        # #2536: galaxyscope.py's Contextual Baseline Fix folds unreferenced_by_name
        # into api for any imported file BEFORE the hit_vector is built, so
        # arch_api / state_unreferenced only ever carry the ADJUSTED values.
        # These two columns persist the raw pre-adjustment extraction counts
        # alongside them (needed by the #1096 cross-language control corpus);
        # for files the adjustment never touches, raw == adjusted. Same
        # auto-heal precedent as doc_loc above for pre-#2536 databases.
        try:
            cursor.execute("ALTER TABLE file_data ADD COLUMN raw_arch_api INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                self.logger.debug("Schema migration skipped: 'raw_arch_api' already exists.")
            else:
                raise

        try:
            cursor.execute("ALTER TABLE file_data ADD COLUMN raw_state_unreferenced INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                self.logger.debug("Schema migration skipped: 'raw_state_unreferenced' already exists.")
            else:
                raise

        # #2801: import_count is the raw pre-resolution capture surface
        # (len(raw_imports)); internal_dependency_links is the resolved-edge count --
        # the same DAG edge set popularity/pagerank/normalized_blast_radius already
        # read (network_risk_sensor's out_degree). The two diverge by design wherever
        # a capture resolves to no node in the scan (embedded_python's `import machine`
        # firmware, dockerfile's `FROM scratch`, jcl's `DSN=` datasets). Same auto-heal
        # precedent as the columns above for pre-#2801 databases.
        try:
            cursor.execute("ALTER TABLE file_data ADD COLUMN internal_dependency_links INTEGER DEFAULT 0")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                self.logger.debug("Schema migration skipped: 'internal_dependency_links' already exists.")
            else:
                raise

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

        # THE IDEMPOTENT WIPE: Ensures delta-scans don't duplicate rows for the same commit.
        # edge_data would also go with file_data's cascade; deleting it first by
        # snapshot key is one indexed pass instead of two FK lookups per file.
        cursor.execute(
            "DELETE FROM edge_data WHERE repo_name = ? AND commit_hash = ?",
            (repo_name, commit_hash),
        )
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

        # PERFORMANCE OPTIMIZATION: Global arrays for batched executemany inserts.
        # #3183 (B1): file_data and class_data used to be inserted one execute()
        # per row purely to read cursor.lastrowid for the FK children below. We
        # now accumulate their rows and batch them with executemany, precomputing
        # the ids the children reference. On an AUTOINCREMENT table the next id is
        # (highest-ever id) + 1, tracked in sqlite_sequence and NOT reset by the
        # idempotent wipe above, so we anchor to that seq; executemany then
        # auto-assigns ids in list order (base+1, base+2, ...), byte-identical to
        # the old per-row path.
        all_file_rows: list = []
        all_class_rows: list = []
        all_func_rows = []

        def _seq_base(table: str) -> int:
            row = cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone()
            return int(row[0]) if row and row[0] is not None else 0

        file_id_base = _seq_base("file_data")
        class_id_base = _seq_base("class_data")

        # #2992: graph node (file path) -> the file_data row it became, for edge_data.
        path_to_file_id: dict[str, int] = {}

        # #2536: hit_vector indexes for the two keys the Contextual Baseline
        # Fix rewrites -- used to fall back to the adjusted values whenever a
        # producer doesn't ship the raw snapshot (synthetic leak/model nodes),
        # so raw == adjusted there rather than a fake zero.
        api_sig_idx = self.SIGNAL_SCHEMA.index("api") if "api" in self.SIGNAL_SCHEMA else -1
        orphan_sig_idx = (
            self.SIGNAL_SCHEMA.index("unreferenced_by_name") if "unreferenced_by_name" in self.SIGNAL_SCHEMA else -1
        )

        for file_data in parsed_files:
            tel = file_data.get("telemetry", {})
            # #2691: exclude the slicer's synthetic top-level buckets from the
            # function POPULATION. `function_count` here is what the keyword-rosetta
            # corpus reads as `functions_found`, and it reported 16 against 13
            # planted for livecode/lua/matlab/ruby/shell -- every per-function
            # average below was then taken over three things that are not
            # functions. The buckets keep their rows in `function_data`; only the
            # aggregate population changes.
            functions = [f for f in file_data.get("functions", []) if not f.get("is_synthetic_slice")]

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

            # #2705: evidence-mass floor on the per-function denominator, the
            # analog of signal_processor._mass_loc. Without it a file whose
            # functions average one line and one branch each read 1.00, and the
            # rosetta corpus measured the column as file length (rho -0.96 with
            # coding_loc, content held equal). The max() also absorbs the old
            # avg_loc > 0 guard: no functions -> avg_comp 0 -> density 0.
            func_internal_density = avg_comp / max(avg_loc, FUNC_EVIDENCE_MASS_FLOOR)

            # #2801: two different numbers were being conflated under one column.
            # import_count is the RAW capture surface -- how many import targets the
            # language's _dependency_capture regex produced, before any resolution.
            # internal_dependency_links is the RESOLVED-edge count: how many of those
            # captures network_risk_sensor mapped to a node in the scan, i.e. the exact
            # edge set popularity/pagerank/normalized_blast_radius/betweenness already
            # read (its out_degree). The two disagree by design wherever a capture points
            # at something outside the graph -- external firmware/libraries (`import
            # machine`, `import numpy`), Docker's reserved `FROM scratch` base, JCL `DSN=`
            # datasets. Keeping both means the capture count stays available as external-
            # dependency surface while the graph column means its name. out_degree is a
            # pure topology count the zero-dependency fallback computes too, so it is
            # populated in every mode -- same as popularity (in_degree), unlike the
            # budgeted graph scores that can be None further down.
            import_count = len(file_data.get("raw_imports", []))
            internal_dependency_links = int(tel.get("network_metrics", {}).get("out_degree", 0) or 0)

            # #2770/#2801: coupling per line of code, over the same evidence-mass floor
            # every other per-file density uses (analysis_lens' EVIDENCE_MASS_FLOOR
            # doctrine, #2655). #2770 replaced the old
            # `max(int(coding_loc * control_flow_ratio), 1)` denominator (0 for any
            # branch-free file, so the column reported the raw count up to 20x); #2801
            # then fixed the NUMERATOR -- coupling is INTERNAL coupling, the resolved
            # edges, not the raw capture count. Dividing import_count here made a
            # vendored-dependency-free service read as import-dense purely on external-
            # library surface (os/numpy/React), which says nothing about its coupling.
            dependency_density = internal_dependency_links / max(
                float(file_data.get("coding_loc", 0) or 0), EVIDENCE_MASS_FLOOR
            )

            # #364: security_auditor.py writes "AI Threat Score" -- "AI Threat
            # Confidence" was never a real producer key here, just a dead primary
            # lookup that always fell through to this same fallback anyway.
            ai_threat_conf_str = tel.get("domain_context", {}).get("AI Threat Score", "0.0%")
            ai_threat: Optional[float] = float(str(ai_threat_conf_str).replace("%", "")) if ai_threat_conf_str else 0.0
            ai_threat_class: Optional[str] = tel.get("domain_context", {}).get("AI Threat Class", "Safe")
            # #3028: without a real XGBoost run (missing numpy/pandas/xgboost, no
            # model file, or a failed inference) "Safe" and 0.0 are placeholders,
            # not verdicts, so the AI threat columns are NULL. The key defaults to
            # True so a caller that predates it keeps its values.
            ml_scored = session_meta.get("ml_inference_ran", True)
            if not ml_scored:
                ai_threat = None
                ai_threat_class = None
            encapsulation_ratio = float(tel.get("encapsulation_ratio", 1.0))

            rv = file_data.get("risk_vector", [0.0] * len(self.RISK_SCHEMA))
            hv = file_data.get("hit_vector", [0] * len(self.SIGNAL_SCHEMA))

            # #2536: raw pre-adjustment extraction counts, snapshotted by
            # galaxyscope.py BEFORE the Contextual Baseline Fix rewrites
            # api/unreferenced_by_name. Absent snapshot -> fall back to the adjusted
            # hit_vector slots (raw == adjusted).
            raw_pre = file_data.get("raw_pre_adjustment", {})
            adjusted_api = hv[api_sig_idx] if 0 <= api_sig_idx < len(hv) else 0
            adjusted_orphans = hv[orphan_sig_idx] if 0 <= orphan_sig_idx < len(hv) else 0
            raw_api = int(raw_pre.get("api", adjusted_api))
            raw_orphans = int(raw_pre.get("unreferenced_by_name", adjusted_orphans))

            file_archetype = tel.get("archetype", "Unknown")
            # #ENGINE-PARITY (file archetype): classify from the fully-assembled
            # metrics + function->file composition via the self-describing file
            # brain (Option 1 post-assembly pass, mirroring apply_file_clusters).
            # Replaces signal_processor's hardcoded-vector value, which drifted from
            # the trainer and read "Unclassified" for code files.
            if not hasattr(self, "_file_brain"):
                self._prep_file_brain()
            # Classify any file with code (matching the trainer's coding_loc>=10
            # population); a func-less code file just has all-zero z-score/composition
            # features, exactly as it did during training. No functions is fine.
            if self._file_brain and float(file_data.get("coding_loc", 0) or 0) > 0:
                _mix: dict[int, int] = {}
                for _f in file_data.get("functions", []) or []:
                    _idx = self._func_name_to_idx.get(_f.get("archetype"))
                    if _idx is not None:
                        _mix[_idx] = _mix.get(_idx, 0) + 1
                _tot = sum(_mix.values())
                _micro = {k: (v / _tot) * 100.0 for k, v in _mix.items()} if _tot else {}
                _res = self._classify_file_archetype(
                    {
                        "coding_loc": float(file_data.get("coding_loc", 0) or 0),
                        "func_z_max": func_z_max,
                        "func_z_mean": func_z_mean,
                        "func_z_median": func_z_median,
                        "pct_z_above_5": pct_z_above_5,
                        "pct_z_above_15": pct_z_above_15,
                        "micro": _micro,
                        "precalc": {
                            "control_flow_ratio": float(tel.get("control_flow_ratio", 0.0)),
                            "avg_func_loc": avg_loc,
                            "avg_func_complexity": avg_comp,
                            "max_func_complexity": max_comp,
                            "avg_func_args": avg_args,
                            "func_complexity_gini": float(tel.get("func_complexity_gini", 0.0)),
                            "func_internal_density": func_internal_density,
                            "dependency_density": dependency_density,
                            "encapsulation_ratio": encapsulation_ratio,
                        },
                    },
                    hv,
                )
                if _res:
                    file_archetype = _res
            # Propagate the authoritative file archetype back into the shared
            # telemetry dict so the audit/LLM recorders (which run AFTER this DB
            # recorder, see galaxyscope recorder order) report the same value the
            # DB stores, instead of signal_processor's now-retired placeholder.
            tel["archetype"] = file_archetype
            file_fingerprint_str = json.dumps(tel.get("archetype_fingerprint", {}))
            composition_file_archetype = tel.get("composition_file_archetype", "Unclassified")
            composition_file_z = float(tel.get("composition_file_z", 0.0) or 0.0)

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
                ai_score: Optional[float] = float(str(raw_ai_score).replace("%", ""))
            except ValueError:
                ai_score = 0.0

            # #366: security_auditor.py's real output key is "is_ml_threat", not
            # "is_malware" -- a near-miss rename that left this column always 0.
            is_malware: Optional[int] = 1 if file_data.get("is_ml_threat", False) else 0
            if not ml_scored:
                is_malware = None  # #3028: no inference, so no verdict either way
            # #367: no producer ever set file_data["has_credentials"]. #381 then
            # read equations["sec_hardcoded_secrets"], but file_data["equations"]
            # is not a durable carrier -- it's rebuilt/emptied/pruned across
            # several galaxyscope.py phases (= {} at ~L1039, per-key del at
            # ~L1090, assembled on a separate logic_data object in the worker),
            # so that read was still 100% zero at population scale
            # (squid-protocol/gitgalaxy#1144). The durable carriers are the same
            # hit_vector / risk_vector slots this recorder already writes as
            # threat_private_info / risk_secrets_risk:
            #   - hit_vector["sec_hardcoded_secrets"]: raw SecurityLens count
            #   - risk_vector["secrets_risk"]: thresholded score, also spiked to
            #     100 for critical leaks via a path that zeroes hit_vector
            #     (signal_processor.py:360), so both slots are checked.
            # equations is kept only as a last-resort fallback.
            hs_idx = (
                self.SIGNAL_SCHEMA.index("sec_hardcoded_secrets")
                if "sec_hardcoded_secrets" in self.SIGNAL_SCHEMA
                else -1
            )
            sr_idx = self.RISK_SCHEMA.index("secrets_risk") if "secrets_risk" in self.RISK_SCHEMA else -1
            has_creds = (
                1
                if (
                    (hs_idx >= 0 and len(hv) > hs_idx and hv[hs_idx] > 0)
                    or (sr_idx >= 0 and len(rv) > sr_idx and rv[sr_idx] > 0)
                    or file_data.get("equations", {}).get("sec_hardcoded_secrets", 0) > 0
                )
                else 0
            )
            # #368: no producer ever set file_data["binary_anomaly"]. #381 read
            # equations["sec_extension_mismatch"], but (same as #367) that dict
            # is not a durable carrier -- and worse, the two real producers of
            # this signal don't even write to it:
            #   - signal_processor.py (a text file that parses as an executable
            #     language but carries an inert extension like .png) sets
            #     raw_signals["sec_extension_mismatch"] -> the durable hit_vector
            #     slot, never equations.
            #   - galaxyscope.py's Binary Analysis Sensor (scan_binary() magic-
            #     byte mismatch) now attaches its hit_vector to file_data too
            #     (it used to compute one and throw it away -- #368).
            # So read the durable hit_vector["sec_extension_mismatch"] slot, the
            # same one already written to the threat_extension_mismatch column.
            # sec_high_risk_execution / sec_reflection_metaprogramming from a
            # binary scan are distinct threat categories surfaced elsewhere and
            # would double-count if folded in here. equations kept as a fallback.
            em_idx = (
                self.SIGNAL_SCHEMA.index("sec_extension_mismatch")
                if "sec_extension_mismatch" in self.SIGNAL_SCHEMA
                else -1
            )
            bin_anomaly = (
                1
                if (
                    (em_idx >= 0 and len(hv) > em_idx and hv[em_idx] > 0)
                    or file_data.get("equations", {}).get("sec_extension_mismatch", 0) > 0
                )
                else 0
            )
            # #1150: resolves #369's deferred decision -- a real (deliberately
            # narrow) GlassWorm-style detector now exists in security_lens.py's
            # THREAT_SIGNATURES rather than formally deprecating the column.
            # Two independent lexical proxies, either sufficient to flag:
            #   - sec_unicode_steganography: a RUN of 3+ consecutive Unicode
            #     Variation Selector / Tag codepoints, the actual invisible-
            #     payload-smuggling technique GlassWorm used. A single such
            #     codepoint is common/benign (emoji presentation, e.g. "❤️");
            #     only a run has no legitimate source-code use.
            #   - sec_self_propagation: a self-file-reference token
            #     (__filename/__file__/import.meta.url/etc.) passed as the
            #     literal first argument to a copy/write/rename call -- the
            #     mechanical signature of a worm duplicating or overwriting
            #     itself. Deliberately excludes bare self-reads (open(__file__))
            #     and loose "self-ref anywhere near a write" windows, both of
            #     which are common benign idioms that would otherwise dominate
            #     false positives.
            # Neither attempts the multi-file/manifest-correlation angle
            # (install-script + registry-publish sequences) -- that needs
            # execution/temporal semantics this AST-free engine doesn't have.
            obfuscation_flag = (
                1
                if file_data.get("equations", {}).get("sec_unicode_steganography", 0) > 0
                or file_data.get("equations", {}).get("sec_self_propagation", 0) > 0
                else 0
            )

            # --- NETWORK TOPOLOGY EXTRACTION ---
            net_mets = tel.get("network_metrics", {})

            # #3027: the network sensor is the authority on what was computed. It
            # writes None for a metric it could not compute (a search past its work
            # budget, a failed computation)
            # and a real value otherwise -- including native PageRank in
            # zero-dependency mode. So these are read straight through (None ->
            # NULL) instead of being NULLed whenever the scan ran in zero-dependency
            # mode, which discarded real values (the network half of #3028).
            # #3028: ai_threat_score is NULL on whether inference ran, not on the
            # global mode flag (a missing pyyaml used to discard real scores).
            if not ml_scored:
                ai_score = None
            pagerank_score = net_mets.get("pagerank_score", 0.0)
            blast_radius = net_mets.get("normalized_blast_radius", 0.0)
            betweenness_score = net_mets.get("betweenness_score", 0.0)
            closeness_score = net_mets.get("closeness_score", 0.0)
            producer_ratio = net_mets.get("producer_ratio", 0.0)
            ecosystem_role = net_mets.get("ecosystem_role", "Unknown")

            class_count = len(file_data.get("classes", []))

            repo_macro = tel.get("repo_macro_species", "Unknown")
            repo_z = tel.get("repo_z_score", 0.0)
            parent_ent = tel.get("domain_context", {}).get("parent_entity", "")

            # --- AI GUARDRAILS & TOKEN DENSITY ---
            # Phase 5 is opt-in (#1178). An absent key means the phase never ran,
            # recorded as NULL ("not evaluated") -- 0 is reserved for "evaluated,
            # no risk found".
            guardrails = tel.get("ai_guardrails")
            appsec = tel.get("ai_appsec")

            if guardrails is None:
                is_black_hole = req_hitl = hallucination_zone = silent_mutation = None
            else:
                is_black_hole = 1 if guardrails.get("is_agentic_black_hole") else 0
                req_hitl = 1 if guardrails.get("requires_hitl") else 0
                hallucination_zone = 1 if guardrails.get("hallucination_zone") else 0
                silent_mutation = 1 if guardrails.get("silent_mutation_risk") else 0

            god_mode = None if appsec is None else (1 if appsec.get("over_permissioned_agent") else 0)

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
                file_data.get("doc_loc", 0),
                file_data.get("file_impact", 0.0),
                tel.get("densities", {}).get("cog_raw", 0.0),
                tel.get("ownership_entropy", 0.0),
                tel.get("author_distribution", 0.0),
                tel.get("raw_churn_freq", 0.0),
                tel.get("popularity", 0),
                import_count,
                internal_dependency_links,
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
                composition_file_archetype,
                composition_file_z,
                repo_macro,
                repo_z,
                ai_score,
                is_malware,
                has_creds,
                bin_anomaly,
                obfuscation_flag,
                file_token_mass,
                file_read_cost,
                is_black_hole,
                req_hitl,
                god_mode,
                hallucination_zone,
                silent_mutation,
                raw_api,
                raw_orphans,
            ]

            row_data.extend(rv)
            row_data.extend(hv)

            # gitgalaxy#2994: Tier-1/2/3 measurement values, same canonical
            # order as tier_cols above (families raw sums, family
            # percentiles, legacy-vector percentiles, relations) -- read via
            # tel.get(...) with 0/0.0 defaults so files that took an early-
            # return path in calculate_risk_vector (critical-leak override,
            # minified override, literature override -- none of which
            # compute surface_families) still insert a clean row instead of
            # raising.
            fam_values = tel.get("surface_families", {})
            pct_fam_values = tel.get("surface_percentiles", {}).get("fam", {})
            pct_vec_values = tel.get("surface_percentiles", {}).get("vec", {})
            rel_values = tel.get("surface_relations", {})

            row_data.extend(fam_values.get(fam, 0) for fam in self.SURFACE_FAMILIES)
            row_data.extend(pct_fam_values.get(fam, 0.0) for fam in self.SURFACE_FAMILIES)
            row_data.extend(pct_vec_values.get(r, 0.0) for r in self.RISK_SCHEMA)
            row_data.append(rel_values.get("guard_balance_ratio", 0.0))
            row_data.append(rel_values.get("alloc_cleanup_pairing", 0.0))
            # #3220: persist the proximity-mitigation tally so a delta rehydrate can
            # restore the exact score-layer weighting (json, deterministic key order).
            row_data.append(json.dumps(file_data.get("mitigation_telemetry") or {}, sort_keys=True))
            # #3220: persist the documentation shield so a delta rehydrate reproduces
            # risk_documentation exactly.
            row_data.append(float((file_data.get("metadata") or {}).get("doc_umbrella", 0.0) or 0.0))
            # #3220: persist the raw import strings so a delta rehydrate rebuilds the
            # dependency graph (popularity/pagerank/api_exposure) exactly.
            row_data.append(json.dumps(sorted(file_data.get("raw_imports", []) or [])))

            # #3183 (B1): accumulate the row and precompute its AUTOINCREMENT id
            # (assigned in list order by the executemany after the loop) instead
            # of inserting now to read lastrowid. The loop never skips a file, so
            # the id is exactly file_id_base + (rows so far) + 1.
            file_id = file_id_base + len(all_file_rows) + 1
            all_file_rows.append(row_data)
            path_to_file_id[file_data.get("path", "")] = file_id

            # 1. Extract and Insert Classes
            classes = file_data.get("classes", [])
            class_id_map = {}

            for cls in classes:
                # #3183 (B1): same precompute-then-batch treatment as file_data.
                # class_data rows are flushed (in this same order) after the loop,
                # before the function/edge batches, so FK parents exist first.
                class_id = class_id_base + len(all_class_rows) + 1
                all_class_rows.append(
                    (
                        file_id,
                        cls.get("name", "Unknown"),
                        json.dumps(cls.get("inheritance", [])),
                        cls.get("method_count", 0),
                        cls.get("state_entanglement", 0.0),
                    )
                )
                class_id_map[cls.get("name")] = class_id

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
                        int(func.get("start_line", 0)),
                        int(func.get("args", 0)),
                        int(func.get("usage_status", 0)),
                        float(func.get("keyword_density", 0.0)),
                        func.get("archetype", "Unclassified"),
                        float(func.get("z_score", 0.0)),
                        str(func.get("docstring", ""))[:2000],
                        json.dumps(func.get("calls_out_to", [])),
                        (int(func.get("token_mass")) if func.get("token_mass") is not None else None),
                        int(bool(func.get("is_public", False))),
                        int(bool(func.get("is_documented", False))),
                        *func_hits,
                        # #3220: trailing impact column (matches the INSERT list below).
                        round(float(func.get("impact", 0.0) or 0.0), 1),
                    ]
                )

        # #3183 (B1): flush file_data then class_data in FK-safe order (parents
        # before children) ahead of the function/edge batches below. Row order
        # matches the loop, so the AUTOINCREMENT ids equal the values precomputed
        # into path_to_file_id / class_id_map above.
        if all_file_rows:
            file_placeholders = ",".join(["?"] * len(all_file_rows[0]))
            # Safe: f-string interpolation is limited to self.RISK_SCHEMA/
            # self.SIGNAL_SCHEMA/self.SHORT_KEY_MAP/self.SURFACE_FAMILIES,
            # internal hardcoded class constants (column names), not user
            # input -- SQLite has no parameterized syntax for column names.
            # Every actual row value goes through `file_placeholders`/`?`.
            cursor.executemany(
                f"""
                INSERT INTO file_data (
                    repo_name, commit_date, commit_hash, file_name, file_path, parent_entity, language, directory_group,
                    total_loc, coding_loc, doc_loc, structural_mass, cog_raw, ownership_entropy, silo_risk,
                    raw_churn_freq, popularity, import_count, internal_dependency_links, pagerank_score, normalized_blast_radius, betweenness_score, closeness_score, producer_ratio, ecosystem_role,
                    control_flow_ratio, function_count, class_count,
                    func_complexity_vector, avg_func_loc, avg_func_complexity, max_func_complexity,
                    avg_func_args, func_complexity_gini, func_internal_density, dependency_density, encapsulation_ratio,
                    author, ai_threat_class, ai_threat_confidence,
                    func_z_max, func_z_mean, func_z_median, pct_z_above_5, pct_z_above_15,
                    file_archetype, file_fingerprint,
                    composition_file_archetype, composition_file_z,
                    ecosystem_baseline, repo_z_score,
                    ai_threat_score, is_malware, has_credentials, binary_anomaly, obfuscation_flag,
                    token_mass, financial_read_cost, agentic_isolation_risk, requires_hitl, appsec_god_mode, hallucination_zone, silent_mutation_risk,
                    raw_arch_api, raw_state_unreferenced,
                    {", ".join([f"risk_{r.replace('-', '_')}" for r in self.RISK_SCHEMA])},
                    {", ".join([self.SHORT_KEY_MAP.get(h, h) for h in self.SIGNAL_SCHEMA])},
                    {", ".join([f"fam_{fam}" for fam in self.SURFACE_FAMILIES])},
                    {", ".join([f"pct_fam_{fam}" for fam in self.SURFACE_FAMILIES])},
                    {", ".join([f"pct_vec_{r.replace('-', '_')}" for r in self.RISK_SCHEMA])},
                    rel_guard_balance, rel_alloc_cleanup, mitigation_telemetry, doc_umbrella, raw_imports
                ) VALUES ({file_placeholders})
            """,  # noqa: S608
                all_file_rows,
            )

        if all_class_rows:
            cursor.executemany(
                """
                INSERT INTO class_data (
                    file_id, class_name, inheritance_parents,
                    method_count, state_entanglement
                ) VALUES (?, ?, ?, ?, ?)
            """,
                all_class_rows,
            )

        # PERFORMANCE OPTIMIZATION: Execute all accumulated functions in a single transaction loop
        if all_func_rows:
            func_placeholders = ",".join(["?"] * len(all_func_rows[0]))
            # Safe: same as above -- self.SHORT_KEY_MAP/SIGNAL_SCHEMA are
            # internal constants, row values go through func_placeholders/`?`.
            cursor.executemany(
                f"""
                INSERT INTO function_data
                (file_id, parent_class_id, func_name, complexity, loc, start_line, args, usage_status, keyword_density, func_archetype, func_z_score, docstring, calls_out_to, token_mass, is_public, is_documented, {", ".join([self.SHORT_KEY_MAP.get(h, h) for h in self.SIGNAL_SCHEMA])}, impact)
                VALUES ({func_placeholders})
            """,  # noqa: S608
                all_func_rows,
            )

        # 2b. #2992: DEPENDENCY EDGE INSERTION
        # An edge is recorded only when BOTH endpoints got a file_data row. The
        # statistical audit runs after the graph is built and can relegate a node
        # to excluded_artifacts, leaving its edges nothing to key on. Those are
        # counted into repo_data.network_edges_unrecorded rather than dropped
        # silently, so a reader reconciling edge_data against popularity /
        # internal_dependency_links knows how many edges the table cannot show.
        edges_unrecorded: Optional[int] = None
        if dependency_edges is not None:
            edge_rows = []
            for edge in dependency_edges:
                src_id = path_to_file_id.get(edge.get("src", ""))
                dst_id = path_to_file_id.get(edge.get("dst", ""))
                if src_id is None or dst_id is None:
                    continue
                edge_rows.append(
                    (
                        repo_name,
                        commit_hash,
                        src_id,
                        dst_id,
                        edge.get("edge_kind", "import"),
                        float(edge.get("weight", 0.0)),
                        int(edge.get("import_statements", 0)),
                        int(edge.get("entity_imports", 0)),
                    )
                )
            edges_unrecorded = len(dependency_edges) - len(edge_rows)
            if edges_unrecorded:
                self.logger.debug(
                    f"Record Keeper: {edges_unrecorded} graph edge(s) touch a file with no file_data row."
                )

            if edge_rows:
                cursor.executemany(
                    """
                    INSERT INTO edge_data (
                        repo_name, commit_hash, src_file_id, dst_file_id,
                        edge_kind, weight, import_statements, entity_imports
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    edge_rows,
                )

        # 3. REPO DATA INSERTION
        class_start_idx = self.SIGNAL_SCHEMA.index("class_start") if "class_start" in self.SIGNAL_SCHEMA else -1
        total_classes = agg_hits[class_start_idx] if class_start_idx >= 0 else 0

        macro_info = summary.get("repo_macro_species", {})
        repo_composition_str = json.dumps(summary.get("composition", {}))
        _repo_summary = summary.get("summary", {})
        repo_comp_archetype = _repo_summary.get("repo_composition_archetype") or "Unclassified"
        repo_comp_z = float(_repo_summary.get("repo_composition_z", 0.0) or 0.0)

        total_files = len(parsed_files)
        total_unparsable = len(unparsable_files)

        avg_encapsulation = (agg_encapsulation / total_files) if total_files > 0 else 1.0
        avg_imports = (agg_import_count / total_files) if total_files > 0 else 0.0

        typosquat_count = summary.get("typosquat_hits", summary.get("summary", {}).get("typosquat_hits", 0))
        net_macro = summary.get("network_macro", {})
        audits = summary.get("ecosystem_audits", {})

        # #473: no `, 0.0` fallback -- network_risk_sensor.py's producer
        # always sets these keys to either a real value or an explicit None
        # (not computed: failed, or past its work budget), never
        # leaves them absent. Defaulting a missing key to 0.0 here would
        # silently turn that honest None back into a fake "measured zero".
        # #3027: read in every mode -- the sensor's None already says "not
        # computed", so a separate zero-dependency-mode gate adds nothing.
        net_modularity = net_macro.get("modularity")
        net_assortativity = net_macro.get("assortativity")
        net_cyclic_density = net_macro.get("cyclic_density")
        net_avg_path_length = net_macro.get("avg_path_length")
        net_articulation_points = net_macro.get("articulation_points")

        repo_row_data = [
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
            None if macro_info.get("z_score") is None else float(macro_info["z_score"]),
            round(avg_encapsulation, 3),
            round(avg_imports, 3),
            net_modularity,
            net_assortativity,
            net_cyclic_density,
            net_avg_path_length,
            net_articulation_points,
            edges_unrecorded,
            int(audits.get("api_mapper", {}).get("shadow_count", 0)),
            int(audits.get("xray", {}).get("anomalies_found", 0)),
            int(audits.get("firewall", {}).get("imports_unknown", 0)),
            1 if session_meta.get("zero_dependency_mode") else 0,
            json.dumps(session_meta["missing_dependencies"], sort_keys=True)
            if "missing_dependencies" in session_meta
            else None,
            *agg_hits,
            repo_composition_str,
            repo_comp_archetype,
            repo_comp_z,
        ]

        repo_placeholders = ",".join(["?"] * len(repo_row_data))
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO repo_data (
                repo_name, commit_date, commit_hash, total_files, total_excluded_artifacts, total_loc, total_coding_loc,
                total_functions, total_classes, total_doc_files, total_build_files, total_config_files, total_test_files,
                typosquat_hits, ecosystem_baseline, z_score,
                avg_encapsulation_ratio, avg_imports_per_file,
                network_modularity, network_assortativity, network_cyclic_density, network_avg_path_length, network_articulation_points,
                network_edges_unrecorded,
                audit_shadow_apis, audit_binary_anomalies, audit_unknown_packages, is_zero_dependency_mode,
                missing_dependencies,
                {", ".join([self.SHORT_KEY_MAP.get(h, h) for h in self.SIGNAL_SCHEMA])},
                file_composition, repo_composition_archetype, repo_composition_z
            ) VALUES ({repo_placeholders})
        """,  # noqa: S608 -- SHORT_KEY_MAP/SIGNAL_SCHEMA are internal constants, values go through repo_placeholders/`?`
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

        # galaxyscope:ignore sec_db_hooks
        # 5. FOLDER-LEVEL ROLLUP (MATERIALIZED PATH AGGREGATION)
        # ==============================================================================

        # galaxyscope:ignore sec_db_hooks
        folder_stats: dict[str, FolderStats] = {}
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
