# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution

# galaxyscope:ignore sec_high_risk_execution

import json
import logging
import gc
from pathlib import Path
from typing import List, Dict, Any, Optional
from gitgalaxy.standards import analysis_lens
from gitgalaxy.standards import gitgalaxy_config

# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# GitGalaxy Phase 9: GPU Recorder
# Strategy v6.2.0 Protocol: Destructive Columnar Pivot & Text Interning
# Stage 3.3: Destructive RAM Eviction (Final Pipeline Phase)
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution


class GPURecorder:
    """
    GPU Telemetry Recorder (WebGL Payload Generator).

    PURPOSE: Transforms heavily nested, row-based artifact data into flattened,
    numerical columns (Structure of Arrays) optimized for GPU/WebGL ingestion.

    MECHANICS: Minifies repetitive strings via Text Interning (Lookups). Executes
    destructive RAM eviction by aggressively `.pop()`ing the central pipeline lists
    and manually triggering Python's Garbage Collector.

    NOTE: While internal Python logic uses formal DevSecOps terminology (e.g., 'Artifacts',
    'Directory Groups'), the output JSON explicitly retains the legacy visual taxonomy
    ('galaxy', 'singularity', 'c_ids') to maintain strict compatibility with the
    downstream WebGL rendering engine.
    """

    def __init__(self, version: str, parent_logger: Optional[logging.Logger] = None):
        self.version = version
        self.logger = parent_logger.getChild("gpu_recorder") if parent_logger else logging.getLogger("gpu_recorder")

        # --- DYNAMIC SCHEMA FETCH ---
        schemas = getattr(analysis_lens, "RECORDING_SCHEMAS", {})

        # --- TEXT INTERNING REGISTRIES ---
        # Converts repetitive strings across 10,000+ files into O(1) integer array lookups
        self.lang_lookup: List[str] = []
        self.author_lookup: List[str] = []
        self.proof_lookup: List[str] = []
        self.purpose_lookup: List[str] = []
        self.reason_lookup: List[str] = []
        self.ext_lookup: List[str] = []
        self.import_lookup: List[str] = []
        self.texture_lookup: List[str] = schemas.get("GPU_TEXTURE_LOOKUPS", [])
        self.dir_group_lookup: List[str] = []
        self.archetype_lookup: List[str] = []

        # --- POSITION-SENSITIVE SCHEMAS ---
        self.RISK_SCHEMA = schemas.get("RISK_SCHEMA", [])
        self.HIT_SCHEMA = schemas.get("SIGNAL_SCHEMA", [])
        self.FUNCTION_SCHEMA = schemas.get("SAT_SCHEMA", [])

    def record_mission(
        self,
        parsed_files: List[Dict],
        unparsable_files: List[Dict],
        summary: Dict,
        forensic_report: Dict,
        repo_name: str,
        session_meta: Dict = None,
        commit_hash: str = "untracked_local",
        branch_name: str = "unknown_branch",
    ) -> Dict:
        """
        Orchestrates the synthesis and implementation of Destructive RAM Eviction.
        Iteratively destroys the input lists to free memory while building the columnar manifest.
        """
        self.logger.info("GPU_RECORDER: Engaging Stage 3.3 Destructive RAM Eviction.")

        # The 'Galaxy' array maps 1:1 to the WebGL rendering instance
        repository_graph = {
            "names": [],
            "paths": [],
            "lang_ids": [],
            "locs": [],
            "m_locs": [],
            "d_locs": [],
            "mass": [],
            "author_distribution": [],
            "ownership_entropy": [],
            "raw_churn_freq": [],
            "cog_raw": [],
            "pos_x": [],
            "pos_y": [],
            "pos_z": [],
            "risks_flat": [],
            "hits_flat": [],
            "tel_aid": [],
            "tel_pid": [],
            "tel_purp": [],
            "tel_lt": [],
            "tel_pop": [],
            "tel_cfr": [],
            "ai_threats": [],
            "satellite_data_flat": [],  # Output retains WebGL 'satellite' namespace for functions
            "satellite_offsets": [0],
            "imports": [],
            "c_ids": [],  # Directory Group / Subsystem mappings
            "a_ids": [],  # Ecosystem Baseline / Archetype IDs
            "a_dists": [],
            "edges": [],  # Inbound dependency pointers
            "outbound_edges": [],  # Outbound dependency pointers
        }

        # The 'Singularity' array maps 1:1 to Excluded Artifacts
        excluded_artifacts = {
            "paths": [],
            "exts": [],
            "reasons": [],
            "sizes": [],
            "confidences": [],
        }

        # --- O(1) DEPENDENCY RESOLUTION MAP ---
        # Because .pop() takes from the end of the list, parsed_files[-1] becomes column index 0.
        resolution_map = {}
        for idx, file_data in enumerate(reversed(parsed_files)):
            path = file_data.get("path", "")
            name = file_data.get("name", Path(path).name)
            stem = Path(path).stem

            if path:
                resolution_map[path] = idx
            if name:
                resolution_map[name] = idx
            if stem:
                resolution_map[stem] = idx

        # Pre-allocate the "Imported By" (inbound dependency) array for all files
        inbound_edges = [[] for _ in range(len(parsed_files))]

        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        # DESTRUCTIVE PIVOT: Parsed Artifacts
        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        while parsed_files:
            current_idx = len(repository_graph["paths"])
            file_data = parsed_files.pop()
            path = file_data.get("path", "")
            tel = file_data.get("telemetry", {})

            # 1. Directory Group Mapping
            d_name = file_data.get("directory_group", "__monolith__")
            repository_graph["c_ids"].append(self._intern(d_name, self.dir_group_lookup))

            # 2. Dynamic Architectural Fingerprint Extraction
            fingerprint = tel.get("archetype_fingerprint", {})
            file_a_ids = []
            file_a_dists = []

            if fingerprint and len(fingerprint) >= 2:
                # Sort archetypes by distance ascending (lowest = best match)
                sorted_archs = sorted(fingerprint.items(), key=lambda x: x[1])
                prim_name, prim_dist = sorted_archs[0]
                sec_name, sec_dist = sorted_archs[1]

                file_a_ids.append(self._intern(prim_name, self.archetype_lookup))
                file_a_dists.append(int(round(prim_dist * 1000)))  # Quantize to save bytes

                # Identify architectural drift (Anti-Patterns)
                if (sec_dist - prim_dist) <= 0.9:
                    file_a_ids.append(self._intern(sec_name, self.archetype_lookup))
                    file_a_dists.append(int(round(sec_dist * 1000)))
            else:
                arch_name = tel.get("archetype", "Unknown Archetype")
                file_a_ids.append(self._intern(arch_name, self.archetype_lookup))
                file_a_dists.append(0)

            repository_graph["a_ids"].append(file_a_ids)
            repository_graph["a_dists"].append(file_a_dists)

            # 3. Core Identity & Loc Data
            repository_graph["paths"].append(path)
            repository_graph["names"].append(file_data.get("name", Path(path).name))
            repository_graph["lang_ids"].append(
                self._intern(str(file_data.get("lang_id", "unknown")), self.lang_lookup)
            )
            repository_graph["locs"].append(int(file_data.get("total_loc", 0)))
            repository_graph["m_locs"].append(int(file_data.get("coding_loc", 0)))
            repository_graph["d_locs"].append(int(file_data.get("doc_loc", 0)))

            # 4. Quantized Structural Metrics
            repository_graph["mass"].append(int(round(file_data.get("file_impact", 0.0) * 10)))
            repository_graph["author_distribution"].append(int(round(tel.get("author_distribution", 0.0) * 1000)))
            repository_graph["ownership_entropy"].append(int(round(tel.get("ownership_entropy", 0.0) * 1000)))
            repository_graph["raw_churn_freq"].append(int(round(tel.get("raw_churn_freq", 0.0) * 1000)))
            repository_graph["cog_raw"].append(int(round(tel.get("densities", {}).get("cog_raw", 0.0) * 1000)))

            repository_graph["pos_x"].append(int(round(file_data.get("pos_x", 0.0) * 10)))
            repository_graph["pos_y"].append(int(round(file_data.get("pos_y", 0.0) * 10)))
            repository_graph["pos_z"].append(int(round(file_data.get("pos_z", 0.0) * 10)))

            # 5. Flat Array Mapping (Structure of Arrays)
            # THE FIX: If risk_vector is missing (unscanned), inject -10 to flag it as -1.0 in WebGPU
            repository_graph["risks_flat"].extend(
                [int(v * 10) for v in file_data.get("risk_vector", [-1.0] * len(self.RISK_SCHEMA))]
            )
            repository_graph["hits_flat"].extend(
                [int(v) for v in file_data.get("hit_vector", [-1] * len(self.HIT_SCHEMA))]
            )

            # 6. Telemetry Interning
            domain_ctx = tel.get("domain_context", {})
            repository_graph["tel_aid"].append(self._intern(tel.get("ownership", "unknown"), self.author_lookup))
            repository_graph["tel_pid"].append(
                self._intern(tel.get("identity_source_proof", "Discovery"), self.proof_lookup)
            )
            repository_graph["tel_purp"].append(
                self._intern(
                    domain_ctx.get("purpose", "Standard Logic Matrix"),
                    self.purpose_lookup,
                )
            )
            repository_graph["tel_lt"].append(tel.get("identity_lock_tier", 4))
            repository_graph["tel_pop"].append(tel.get("popularity", 0))
            repository_graph["tel_cfr"].append(int(round(tel.get("control_flow_ratio", 0.0) * 1000)))

            # 7. Threat Score Quantization
            ai_score_str = domain_ctx.get("AI Threat Score", "0.0%")
            try:
                ai_score_val = float(ai_score_str.replace("%", ""))
            except ValueError:
                ai_score_val = 0.0

            repository_graph["ai_threats"].append(int(round(ai_score_val * 1000)))

            # 8. Function Minification (Compressed Sparse Row Format)
            function_list = []
            funcs = file_data.get("functions", [])
            while funcs:
                func = funcs.pop()
                function_list.extend(
                    [
                        func.get("name", "unk"),
                        func.get("loc", 0),
                        func.get("branch", 0),
                        int(func.get("angle", 0) * 10),
                        func.get("args", 0),
                        self._intern(func.get("texture", "standard"), self.texture_lookup),
                        int(func.get("control_flow_ratio", 0.0) * 1000),
                        int(func.get("impact", func.get("magnitude", 0)) * 10),
                        int(func.get("start_line", 0)),
                        int(func.get("end_line", 0)),
                    ]
                )

            # Re-reverse chunks so original order is preserved despite .pop()
            chunks = [function_list[i : i + 10] for i in range(0, len(function_list), 10)]
            chunks.reverse()
            for chunk in chunks:
                repository_graph["satellite_data_flat"].extend(chunk)

            # Append the offset marker tracking array lengths for WebGL parsing
            current_total_functions = len(repository_graph["satellite_data_flat"]) // 10
            repository_graph["satellite_offsets"].append(current_total_functions)

            # 9. Dependency Resolution
            raw_imports = sorted(list(file_data.get("raw_imports", [])))
            repository_graph["imports"].append([self._intern(imp, self.import_lookup) for imp in raw_imports])

            current_outbound = []
            for imp in raw_imports:
                if imp in resolution_map:
                    target_idx = resolution_map[imp]
                    if target_idx != current_idx:
                        inbound_edges[target_idx].append(current_idx)
                        current_outbound.append(target_idx)

            repository_graph["outbound_edges"].append(list(set(current_outbound)))

            # Memory Eviction
            del file_data

        repository_graph["edges"] = [list(set(edges)) for edges in inbound_edges]

        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        # DESTRUCTIVE PIVOT: Excluded Artifacts Queue
        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        while unparsable_files:
            unparsable = unparsable_files.pop()
            path = unparsable.get("path", "")

            ext = Path(path).suffix.lower() if Path(path).suffix else "none"

            excluded_artifacts["paths"].append(path)
            excluded_artifacts["exts"].append(self._intern(ext, self.ext_lookup))
            excluded_artifacts["reasons"].append(self._intern(unparsable.get("reason", "anomaly"), self.reason_lookup))
            excluded_artifacts["sizes"].append(int(unparsable.get("size_bytes", 0)))
            excluded_artifacts["confidences"].append(int(round(unparsable.get("identity_confidence", 0.0) * 1000)))
            del unparsable

        # Evict detached dict references
        gc.collect()
        self.logger.debug("GPU_RECORDER: RAM Eviction complete. Python GC cycle triggered.")

        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        # SUMMARY FLATTENING (UI Diagnostics)
        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        unparsable_sum = summary.get("unparsable_files", {})
        breakdown = {
            "binary": unparsable_sum.get("binary", 0),
            "unparsable": unparsable_sum.get("unparsable", 0),
            "no_extension": unparsable_sum.get("no_extension", 0),
            "size_limit": unparsable_sum.get("size_limit", 0),
            "os_permissions": unparsable_sum.get("os_permissions", 0),
        }

        # Unpack nested dictionary logic for UI parsing
        comp = unparsable_sum.get("composition_by_extension_and_reason", {})
        for ext, reasons in comp.items():
            total = sum(reasons.values())
            if total > 0:
                safe_ext = ext if ext and ext != "no_extension" else "unknown"
                breakdown[f"Format [{safe_ext}]"] = {"count": total, "details": reasons}

        if "unparsable_files" not in summary:
            summary["unparsable_files"] = {}

        summary["unparsable_files"]["breakdown"] = breakdown

        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        # MISSION LORE INJECTION
        # ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
        project_stories = getattr(gitgalaxy_config, "PROJECT_STORIES", {})

        story_payload = project_stories.get(
            repo_name,
            {
                "status": "",
                "why": "",
                "who": "",
                "significance": "",
                "link": "",
                "artifacts": [{"title": "", "url": "", "description": ""}],
            },
        )

        # Extract dependencies if provided
        missing_deps = session_meta.get("missing_dependencies", {}) if session_meta else {}
        zero_dep_mode = session_meta.get("zero_dependency_mode", False) if session_meta else False

        # Return payload mirroring the exact schema expected by the WebGPU Visualizer
        return {
            "meta": {
                "zero_dependency_mode": zero_dep_mode,
                "missing_dependencies": missing_deps,
                "schemas": {
                    "galaxy_columns": list(repository_graph.keys()),
                    "singularity_columns": list(excluded_artifacts.keys()),
                    "risk_vector_x1000": self.RISK_SCHEMA,
                    "hit_vector": self.HIT_SCHEMA,
                    "satellites": self.FUNCTION_SCHEMA,
                    "scalars": {"exposure": 1000, "physics": 10},
                    "lookups": {
                        "languages": self.lang_lookup,
                        "textures": self.texture_lookup,
                        "authors": self.author_lookup,
                        "proofs": self.proof_lookup,
                        "purposes": self.purpose_lookup,
                        "reasons": self.reason_lookup,
                        "exts": self.ext_lookup,
                        "imports": self.import_lookup,
                        "constellations": self.dir_group_lookup,
                        "archetypes": self.archetype_lookup,
                    },
                }
            },
            "global_summary": summary,
            "galaxy": repository_graph,
            "singularity": excluded_artifacts,
            "story": story_payload,
        }

    def _intern(self, val: str, registry: List[str]) -> int:
        """Minifies payload footprints by mapping repetitive strings to integer IDs."""
        if val not in registry:
            registry.append(val)
        return registry.index(val)

    def save_minified(self, payload: Dict[str, Any], filename: str):
        """Serializes with maximum JSON compression to the provided output path."""
        target_path = Path(filename)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=None, separators=(",", ":"), ensure_ascii=False)
            self.logger.info(f"GPU Manifest Sealed -> {target_path}")
        except Exception as e:
            self.logger.error(f"Failed to seal GPU manifest: {e}")