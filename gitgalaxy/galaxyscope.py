# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import logging
import time
import zipfile
import tempfile
import shutil
import sys
import re
import os
import subprocess
import importlib
import multiprocessing
import concurrent.futures
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union, Set
from collections import defaultdict

from gitgalaxy.core.network_risk_sensor import HAS_NETWORKX
from gitgalaxy.core.detector import HAS_TIKTOKEN
from gitgalaxy.core.aperture import ApertureFilter, InaccessibleArtifactError
from gitgalaxy.core.guidestar_lens import GuideStarLens
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.core.prism import Prism
from gitgalaxy.core.spatial_mapper import SpatialMapper
from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.metrics.chronometer import Chronometer
from gitgalaxy.metrics.signal_processor import SignalProcessor
from gitgalaxy.metrics.statistical_auditor import StatisticalAuditor
from gitgalaxy.tools.network_auditing.full_api_network_map import run_api_audit
from gitgalaxy.tools.supply_chain_security.binary_anomaly_detector import run_xray_audit
from gitgalaxy.tools.supply_chain_security.supply_chain_firewall import (
    run_firewall_audit,
)
from gitgalaxy.recorders.gpu_recorder import GPURecorder
from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.recorders.sarif_recorder import SarifRecorder
from gitgalaxy.recorders.sbom_recorder import SbomRecorder
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.security.security_auditor import SecurityAuditor, ML_AVAILABLE
from gitgalaxy.tools.ai_guardrails.dev_agent_firewall import DevAgentFirewall
from gitgalaxy.tools.ai_guardrails.ai_appsec_sensor import AIAppSecSensor
from gitgalaxy.standards.gitgalaxy_config import (
    APERTURE_CONFIG,
    PRIORITY_WHITELIST,
    LEXICAL_FAMILY_HEURISTICS,
    GUIDESTAR_CONFIG,
    TEST_NAMING_CONVENTIONS,
)
from gitgalaxy.standards.language_standards import (
    LANGUAGE_DEFINITIONS,
    PROJECT_OVERRIDES,
)
from gitgalaxy.standards.analysis_lens import (
    ThreatPolicy,
    PATH_MODIFIERS,
    ASSET_MASKS,
)

HAS_PYYAML = importlib.util.find_spec("yaml") is not None

logger = logging.getLogger("GalaxyScope")

# ==============================================================================
# WORKER PROCESS: ISOLATED MEMORY SPACE FOR PASS 1 (CPU BOUND)
# ==============================================================================
# Top-level functions to bypass Python's Multi-Processing pickling limitations

_worker_state = {}

def execution_timeout_failsafe(signum, frame):
    """
    Hardware-level OS interrupt for Catastrophic Backtracking (ReDoS) protection.

    Registered via the Unix 'signal' library, this failsafe forcibly halts the worker
    process if a malformed file traps the regex engine in an exponential evaluation loop
    for more than 15 seconds, preventing pipeline starvation.
    """
    raise TimeoutError("Structural Saturation (ReDoS Timeout)")


def _init_worker(
    root_str: str,
    config: Dict[str, Any],
    ext_tally: Dict[str, int],
    log_level: int,
    git_tracked: Set[str],
    census: Set[str],
):
    """
    Initializes the CPU-bound optical modules within the worker process's isolated memory.
    
    ARCHITECTURAL DECISION (ISOLATED WORKER MEMORY):
    Python's Global Interpreter Lock (GIL) prevents true multi-threading for CPU-bound tasks.
    To map a massive repository at extreme velocity, GitGalaxy spawns entirely separate OS
    processes. This boot-loader instantiates the heavy regex matrices entirely within the 
    child's isolated RAM. This prevents the OS from attempting to pickle/serialize massive 
    compiled regex objects across the IPC (Inter-Process Communication) boundary.
    """
    from gitgalaxy.core.detector import StructuralExtractor as OpticalDetector

    logging.getLogger().setLevel(log_level)
    worker_logger = logging.getLogger("GalaxyScope.Worker")

    root = Path(root_str)
    lang_defs = config.get("LANGUAGE_DEFINITIONS", {})
    lexical_heuristics = config.get("LEXICAL_FAMILY_HEURISTICS", {})
    aperture_cfg = config.get("APERTURE_CONFIG", {})
    priority_whitelist = config.get("PRIORITY_WHITELIST", [])

    # --- PERFORMANCE ANCHOR: DETECTOR CACHE WARM-UP ---
    detector_cache = {}

    # 1. Force-warm the fallbacks immediately.
    # This silences the [AUTO-HEAL] warnings and compiles the regex engine for these IDs.
    for fallback_id in ["plaintext", "markdown"]:
        detector_cache[fallback_id] = OpticalDetector(fallback_id, lang_defs, parent_logger=worker_logger)

    # 2. Warm up active project languages based on extensions found in Pass 0.
    active_langs = set()
    for ext in ext_tally.keys():
        for l_id, l_cfg in lang_defs.items():
            if ext in l_cfg.get("extensions", []):
                active_langs.add(l_id)
                break

    for lang_id in active_langs:
        if lang_id not in detector_cache:
            detector_cache[lang_id] = OpticalDetector(lang_id, lang_defs, parent_logger=worker_logger)

    # --- NEW: Decide the Rules of Engagement before booting the engines ---
    if config.get("PARANOID_MODE", False):
        _active_policy = ThreatPolicy.get_policy("paranoid")
    else:
        _active_policy = ThreatPolicy.get_policy("baseline")

    _worker_state.update(
        {
            "root": root,
            "config": config,
            "ext_tally": ext_tally,
            "lang_defs": lang_defs,
            "worker_logger": worker_logger,
            "git_tracked": git_tracked,
            "census": census,
            "filter": ApertureFilter(root, lang_defs, aperture_cfg, parent_logger=worker_logger),
            "guidestar": GuideStarLens(root, priority_whitelist, parent_logger=worker_logger),
            "detector": LanguageDetector(lang_defs, lexical_heuristics),
            "prism": Prism(lexical_heuristics, lang_defs, parent_logger=worker_logger),
            "detector_cache": detector_cache,
            "word_tokenizer": re.compile(r"\b\w+\b"),
            # --- NEW: Boot the Analysis Engines into worker memory ---
            "chronometer": Chronometer(root, parent_logger=worker_logger),
            "signal": SignalProcessor(aperture_config=config, parent_logger=worker_logger),
            "security": SecurityLens(policy=_active_policy),
            # --------------------------------------------------------
        }
    )

    _worker_state["guidestar"].scan_project_config()


def _process_file_worker(rel_path: str) -> Dict[str, Any]:
    """Processes a single file path using the worker's cached hardware modules."""

    # ---> START THE CLOCK FOR THE MICRO-PROFILER <---
    t_start = time.time()

    root = _worker_state["root"]
    full_path_str = str(root / rel_path)

    # --- NEW: PARALLEL PHANTOM CHECK ---
    # Silently evaporates files missing on disk to prevent main-thread anomaly logging
    if not Path(full_path_str).is_file():
        return {
            "rel_path": rel_path,
            "status": "phantom",
            "reason": "Phantom file (missing on disk)",
            "data": {},
            "processing_time": time.time() - t_start,
        }

    logger = _worker_state["worker_logger"]
    aperture = _worker_state["filter"]
    guidestar = _worker_state["guidestar"]
    detector = _worker_state["detector"]
    prism = _worker_state["prism"]
    census = _worker_state["census"]
    lang_defs = _worker_state["lang_defs"]
    detector_cache = _worker_state["detector_cache"]
    tokenizer = _worker_state["word_tokenizer"]

    # --- NEW: Extract the Analysis Engines from worker memory ---
    security = _worker_state["security"]
    # -----------------------------------------------------------

    has_prior, intent_vector = guidestar.get_intent_status(full_path_str)
    observation = {
        "rel_path": rel_path,
        "status": "filtered",
        "reason": "Aperture block",
        "data": {},
    }

    # --- PHASE PROFILING STATE ---
    is_file_profiling = _worker_state["config"].get("FILE_SPEED", False)
    is_profiling = _worker_state["config"].get("SPLICING_SPEED", False)
    phase_times = {}

    try:
        # Phase 1: Aperture Filter
        t_aperture = time.perf_counter()
        is_valid, size_bytes, reason = aperture.evaluate_path_integrity(full_path_str, has_intent=has_prior)
        if is_file_profiling:
            phase_times["1_Aperture_Filter"] = time.perf_counter() - t_aperture

        if not is_valid:
            # ---> NEW: THE BINARY ANALYSIS SENSOR <---
            # Intercept binary and blacklisted extensions for deep inspection
            if "Binary Format" in reason or "Blacklisted Extension" in reason or "Embedded Data Payload" in reason:
                try:
                    with open(full_path_str, "rb") as f:
                        # Read the first 8KB to check headers and entropy
                        head = f.read(8192)

                    ext = Path(rel_path).suffix.lower()
                    binary_threats = security.scan_binary(head, ext)

                    if binary_threats:
                        logger.critical(f"🚨 BINARY ANALYSIS TRIGGERED: Weaponized binary detected at '{rel_path}'!")

                        # Threat Escalation: Forge a synthetic artifact and force it into the repository graph
                        from gitgalaxy.metrics.signal_processor import SignalProcessor

                        hit_vector = [0] * len(SignalProcessor.SIGNAL_SCHEMA)
                        for t_key, t_val in binary_threats.items():
                            if t_key in SignalProcessor.SIGNAL_SCHEMA:
                                hit_vector[SignalProcessor.SIGNAL_SCHEMA.index(t_key)] = t_val

                        observation["status"] = "success"
                        observation["reason"] = None
                        observation["data"] = {
                            "path": rel_path,
                            "stem": Path(rel_path).stem.lower(),
                            "lang_id": "binary_threat",
                            "is_minified": False,
                            "lock_tier": 0,
                            "intensity": 1.0,
                            "source_proof": "Binary Analysis Sensor",
                            "size_bytes": size_bytes,
                            "total_loc": 1,
                            "coding_loc": 1,
                            "doc_loc": 0,
                            "raw_imports": [],
                            "popularity_hits": set(),
                            "equations": binary_threats,
                            "satellites": [],
                            "logic_density": 100.0,
                            "sum_fxn_impact": 5000.0,  # Massive structural impact!
                            "total_control_flow_ratio": 0.0,
                            "threat_snippets": {
                                "binary_xray": [binary_threats.get("threat_snippet", "Unknown Threat")]
                            },
                            "metadata": {
                                "alert": "WEAPONIZED BINARY DETECTED",
                                "purpose": reason,
                            },
                        }
                        observation["processing_time"] = time.time() - t_start
                        return observation
                except Exception as e:
                    logger.debug(f"Binary Analysis failed on '{rel_path}': {e}")

            # If no threats found, or it wasn't a binary, dump to Unparsable Artifacts as usual
            observation["status"] = "parser_bypass"
            observation["reason"] = reason
            observation["size_bytes"] = size_bytes
            observation["processing_time"] = time.time() - t_start
            return observation

        # Phase 2: Disk I/O
        t_io = time.perf_counter()
        try:
            with open(full_path_str, "r", encoding="utf-8", errors="ignore") as f:
                content_buffer = f.read()
        except FileNotFoundError:
            # Fast, zero-overhead disk failure routing.
            observation["status"] = "phantom"
            observation["reason"] = "Phantom file (missing on disk)"
            observation["processing_time"] = time.time() - t_start
            return observation
        except Exception as e:
            observation["reason"] = f"I/O Error: {str(e)}"
            observation["processing_time"] = time.time() - t_start
            return observation
        if is_file_profiling:
            phase_times["2_Disk_IO"] = time.perf_counter() - t_io

        filter_res = aperture.is_in_scope(full_path_str, content=content_buffer, has_intent=has_prior)
        if not filter_res["is_in_scope"]:
            observation["status"] = "parser_bypass"
            observation["reason"] = filter_res["reason"]
            observation["processing_time"] = time.time() - t_start
            return observation

        # =========================================================================
        # THE EXECUTION TIMEOUT FAILSAFE (GLOBAL ReDoS Protection)
        # =========================================================================
        import signal
        import sys

        # Check if the operating system is not Windows
        is_posix = sys.platform != "win32"

        if is_posix:
            signal.signal(signal.SIGALRM, execution_timeout_failsafe)
            signal.alarm(15)  # 15-second fuse for POSIX systems

        try:
            # Phase 3: Linguistic Detector
            t_detector = time.perf_counter()
            detection_result = detector.inspect(
                full_path_str,
                content_sample=content_buffer,
                has_intent=has_prior,
                intent_vector=intent_vector,
                ext_tally=_worker_state.get("ext_tally", {}),
                census=_worker_state["census"],
            )
            if is_file_profiling:
                phase_times["3_Language_Detector"] = time.perf_counter() - t_detector

            lang_id = detection_result["lang_id"]

            # ---> NEW: STATIC ASSET IDENTIFICATION <---
            is_inert = lang_id in ("plaintext", "markdown", "json", "yaml", "csv")
            is_supported = lang_id in lang_defs or is_inert

            if lang_id in ("undeterminable", "unknown") or not is_supported:
                observation["status"] = "parser_bypass"
                observation["reason"] = f"Unsupported Format (.{lang_id})"
                observation["identity_confidence"] = detection_result.get("intensity", 0.0)
                observation["processing_time"] = time.time() - t_start
                return observation

            # ---> NEW: MINIFICATION / VENDOR DETECTION <---
            is_minified = False
            total_loc = filter_res.get("total_loc", 1)
            size_bytes = filter_res.get("size_bytes", 0)

            if total_loc > 0:
                avg_line_length = size_bytes / total_loc
                if avg_line_length > 800 or (size_bytes > 50000 and total_loc < 15):
                    is_minified = True

            vendor_paths = _worker_state["config"].get("APERTURE_CONFIG", {}).get("VENDOR_MINIFICATION_PATHS", [])
            safe_path = full_path_str.replace("\\", "/")

            if re.search(r"\.min\.[a-z]+$", full_path_str, re.I) or any(v in safe_path for v in vendor_paths):
                is_minified = True

            if is_minified:
                logger.debug(f"[WORKER-TRACE] MINIFIED/VENDOR DETECTED: {rel_path}. Bypassing structural extraction.")
                logic_data = {"equations": {}, "coding_loc": total_loc, "doc_loc": 0}
                refraction = {
                    "coding_loc": total_loc,
                    "doc_loc": 0,
                    "code_stream": content_buffer,
                    "comment_stream": "",
                }
            else:
                # Phase 4: Lexical Scanning
                t_prism = time.perf_counter()
                refraction = prism.split_streams(content_buffer, lang_id)
                if is_file_profiling:
                    phase_times["4_Lexical_Scan"] = time.perf_counter() - t_prism

                if lang_id not in detector_cache:
                    from gitgalaxy.core.detector import OpticalDetector

                    detector_cache[lang_id] = OpticalDetector(lang_id, lang_defs, parent_logger=logger)

                opt_detector = detector_cache[lang_id]

                # --- INJECTED DEBUG TRACE ---
                logger.debug(f"[WORKER-TRACE] >>> ENTERING DETECTOR: {rel_path} (Lang: {lang_id})")

                # Phase 5: Optical Detector
                t_detector_phase = time.perf_counter()
                logic_data = opt_detector.splice(
                    code_stream=refraction["code_stream"],
                    comment_stream=refraction["comment_stream"],
                    confidence=detection_result.get("intensity", 1.0),
                    profile_regex=is_profiling,
                    raw_content=content_buffer,
                )
                if is_file_profiling:
                    phase_times["5_Optical_Detector"] = time.perf_counter() - t_detector_phase

                # ---> INJECT THE KNOWLEDGE SHIELD <---
                dir_path = str(Path(rel_path).parent).replace("\\", "/")
                if dir_path == ".":
                    dir_path = "__root__"

                if "metadata" not in logic_data:
                    logic_data["metadata"] = {}
                logic_data["metadata"]["doc_umbrella"] = guidestar.documentation_coverage.get(dir_path, 0.0)

                logger.debug(f"[WORKER-TRACE] <<< EXITING EXTRACTOR: {rel_path}")

            # --- Phase 5.5: Security Lens (Passive Observers) ---
            t_security = time.perf_counter()
            if "equations" not in logic_data:
                logic_data["equations"] = {}

            if not is_inert:
                # Handle the new nested dictionary
                sec_results = security.scan_content(content_buffer, filter_res.get("total_loc", 0))

                for sec_key, hit_count in sec_results["counts"].items():
                    logic_data["equations"][f"sec_{sec_key}"] = hit_count

                # Pass the snippets into the payload
                logic_data["threat_snippets"] = sec_results["snippets"]

            if is_file_profiling:
                phase_times["5.5_Security_Lens"] = time.perf_counter() - t_security
            # ----------------------------------------------------

            # Phase 6: Raw Imports & Named Tokens
            t_imports = time.perf_counter()
            raw_imports = set()
            named_tokens = set()  # <--- NEW: Initialize token tracker

            if not is_inert:
                # 1. Extract raw file dependencies
                import_regex = lang_defs.get(lang_id, {}).get("rules", {}).get("_dependency_capture")
                if import_regex:
                    try:
                        for match in import_regex.finditer(content_buffer):
                            extracted_path = next((g for g in match.groups() if g), None)
                            if extracted_path:
                                # Handle comma-separated blocks and brackets (e.g., Rust/Scala: {A, B}, Python: a, b as c)
                                clean_group = extracted_path.replace("{", "").replace("}", "")
                                for item in clean_group.split(","):
                                    # Strip 'as alias' and whitespace to isolate the pure module name
                                    clean_module = re.split(r"\s+as\s+", item)[0].strip()
                                    if clean_module:
                                        raw_imports.add(clean_module)
                    except Exception:
                        logging.exception("Import extraction failed for language '%s'.", lang_id)

                # 2. Extract Named Tokens dynamically via Language Standards
                named_token_regex = lang_defs.get(lang_id, {}).get("rules", {}).get("_named_token_capture")
                if named_token_regex:
                    try:
                        for match in named_token_regex.finditer(content_buffer):
                            extracted_group = next((g for g in match.groups() if g), None)
                            if extracted_group:
                                # Split by comma and strip 'as' aliases to isolate the pure token
                                for token in extracted_group.split(","):
                                    clean_token = re.split(r"\s+as\s+", token)[0].strip()
                                    if clean_token:
                                        named_tokens.add(clean_token)
                    except Exception:
                        logging.exception("Named token extraction failed for language '%s'.", lang_id)

            if is_file_profiling:
                phase_times["6_Import_Regex"] = time.perf_counter() - t_imports

            # Phase 7: Tokenization & Census
            t_token = time.perf_counter()
            popularity_hits = set()
            if not is_inert:
                popularity_hits = set(tokenizer.findall(refraction["code_stream"])) & census
            t_end = time.perf_counter()
            if is_file_profiling:
                phase_times["7_Token_Intersection"] = t_end - t_token

            # Append the new blind-spot telemetry to the regex output
            if is_profiling and not is_inert:
                logic_data["regex_telemetry"] = logic_data.get("regex_telemetry", {})
                logic_data["regex_telemetry"][f"{lang_id}::Worker_Imports"] = t_token - t_imports
                logic_data["regex_telemetry"][f"{lang_id}::Worker_Popularity_Tokens"] = t_end - t_token

        except TimeoutError:
            logger.warning(f"TIMEOUT FAILSAFE: '{rel_path}' exceeded 15s. Relegating to Unparsable Artifacts.")
            observation["status"] = "parser_bypass"
            observation["reason"] = "Unparsable (Structural Saturation / Global Regex Timeout)"
            observation["size_bytes"] = filter_res.get("size_bytes", 0)
            observation["identity_confidence"] = detection_result.get("intensity", 0.0)
            observation["processing_time"] = time.time() - t_start
            return observation
        finally:
            # IMPORTANT: Clear the timeout failsafe immediately upon success!
            if is_posix:
                signal.alarm(0)
        # =========================================================================

        data_payload = {
            "path": rel_path,
            "stem": Path(rel_path).stem.lower(),
            "lang_id": lang_id,
            "is_minified": is_minified,
            "lock_tier": detection_result.get("lock_tier", 4),
            "intensity": detection_result.get("intensity", 0.0),
            "source_proof": detection_result.get("source_proof", "Discovery"),
            "size_bytes": filter_res.get("size_bytes", 0),
            "total_loc": filter_res.get("total_loc", 0),
            "prior_lock": has_prior,
            "coding_loc": refraction["coding_loc"],
            "doc_loc": refraction["doc_loc"],
            "mitigations": refraction.get("mitigations", []), # <--- THE FIX: Route the suppressions
            "raw_imports": list(raw_imports),
            "named_tokens": list(named_tokens),  
            "popularity_hits": popularity_hits,
            "regex_telemetry": (logic_data.pop("regex_telemetry", {}) if is_profiling else {}),
        }

        data_payload.update(logic_data)
        data_payload["control_flow_ratio"] = logic_data.get("total_control_flow_ratio", 0.0)
        data_payload["file_impact"] = logic_data.get("sum_fxn_impact", 0.0)

        observation.update(
            {
                "status": "success",
                "reason": None,
                "data": data_payload,
                "phase_times": phase_times if is_file_profiling else {},
            }
        )

    except Exception as e:
        observation["status"] = "anomaly"
        observation["reason"] = f"Hardware failure: {str(e)}"

    # ---> RECORD THE FINAL TIME <---
    total_time = time.time() - t_start
    observation["processing_time"] = total_time

    # ---> NEW: REAL-TIME SLOW FILE ALERT <---
    if total_time > 10.0:
        logger.warning(f"🐌 SLOW PARSE DETECTED: '{rel_path}' took {total_time:.2f} seconds.")

    return observation


# ==============================================================================
# GitGalaxy Phase 3: Pipeline Orchestrator
# Bayesian Optics & Parser Bypasses
# ==============================================================================


class Orchestrator:
    """
    Orchestrator Core: The GitGalaxy Central Processing Core.
    This class operates as the Hub in GitGalaxy's Hub-and-Spoke architecture. It is strictly
    a traffic cop—it delegates all heavy lifting to specialized computational engines.

    Information Flow:
    1. Pre-Flight (Phase 0): The root path is scanned to build a 'Census' of tracked files,
       consulting Git/OS boundaries, .gitattributes, and dynamic micro-mass limits.
    2. Parallel Extraction (Phase 1): Bypasses the GIL by spawning isolated worker processes.
       Workers perform the heavy Structural Signature and token extraction and filter out Static Assets.
    3. Structural Impact Analysis (Phases 2-4): Returns extracted features to the main thread. Maps out
       DAGs (Directed Acyclic Graphs) and converts token frequencies into actionable metrics. Note:
       risk exposures are calculated metrics from the raw Structural Signatures, not the hits themselves.
    4. Threat Inference (Phases 5-10): Executes ML pipelines (XGBoost) and zero-trust policies
       (AppSec/Supply Chain Firewalls) to hunt behavioral anomalies.
    5. Output Routing (Phases 11-12): Transforms the global RAM state into columnar
       JSON payloads, native SQLite bases, and LLM-ready markdown artifacts.
    """

    def __init__(
        self,
        target_input: Union[str, Path],
        config: Dict[str, Any],
        version: str = "6.2.0",
    ):
        self.config = config
        self.version = version
        self.temp_dir: Optional[str] = None
        self.root = self._prepare_target(target_input)

        lang_defs = config.get("LANGUAGE_DEFINITIONS", {})
        aperture_cfg = config.get("APERTURE_CONFIG", {})
        priority_whitelist = config.get("PRIORITY_WHITELIST", [])

        # ==============================================================================
        # CORE SENSOR SUBMODULES (The Spokes)
        # ==============================================================================
        # Perimeter shield rejecting unreadable/binary matter before deep scanning
        self.filter = ApertureFilter(self.root, lang_defs, aperture_cfg, parent_logger=logger)

        # Bayesian prior injector (evaluates intent via Manifests, Readmes, .gitattributes)
        self.guidestar = GuideStarLens(self.root, priority_whitelist, parent_logger=logger)

        # Temporal engine extracting Git volatility, churn velocity, and ownership entropy
        self.chronometer = Chronometer(self.root, parent_logger=logger)
        self.spatial_mapper = SpatialMapper(parent_logger=logger)

        # The primary heuristic math engine converting raw Structural Signatures to risk exposure vectors
        self.processor = SignalProcessor(aperture_config=config, parent_logger=logger)

        # Third-Gate gatekeeper identifying and dropping un-parseable data dumps
        self.auditor = StatisticalAuditor(parent_logger=logger)

        # Constructs the physical import DAG and calculates PageRank/Downstream Exposure
        self.network_sensor = NetworkRiskSensor(parent_logger=logger)

        # ==============================================================================
        # THE EXIT STRATEGY (Recorders & Payload Generation)
        # ==============================================================================
        # GPU Recorder: Performs destructive columnar pivot for WebGL consumption
        self.gpu_recorder = GPURecorder(version=self.version, parent_logger=logger)
        # Audit Recorder: Emits human-readable forensic traceability reports
        self.audit_recorder = AuditRecorder(parent_logger=logger)
        # LLM Recorder: Generates token-compressed RAG context text for AI Agents
        self.llm_recorder = LLMRecorder(parent_logger=logger)
        # DB Recorder: Archives relational tables natively to SQLite3
        self.db_recorder = RecordKeeper(parent_logger=logger)
        # SARIF Recorder: Exports industry-standard JSON for enterprise security dashboards
        self.sarif_recorder = SarifRecorder(version=self.version, parent_logger=logger)
        # SBOM Recorder: Produces mathematically verified CycloneDX manifests
        self.sbom_recorder = SbomRecorder(version=self.version, parent_logger=logger)

        # --- NEW: THE SMART THREAT SWITCH (MAIN THREAD) ---
        if self.config.get("PARANOID_MODE", False):
            _active_policy = ThreatPolicy.get_policy("paranoid")
        else:
            _active_policy = ThreatPolicy.get_policy("baseline")

        # Zero-Trust execution validation
        self.security_analyzer = SecurityLens(policy=_active_policy)

        # Multi-class XGBoost threat classification model
        self.model_auditor = SecurityAuditor(model_path="gitgalaxy_malware_xgb_multiclass.json", parent_logger=logger)
        # --------------------------------------------------

        # ==============================================================================
        # GLOBAL STATE ARRAYS
        # Shared memory constructs used to aggregate worker output and manage state
        # ==============================================================================
        self.census: Set[str] = set()
        self.stem_map: Dict[str, str] = {}
        self.ram_cache: Dict[str, Dict[str, Any]] = {}
        self.parsed_files: List[Dict[str, Any]] = []
        self.unparsable_files: List[Dict[str, Any]] = []
        self.anomalies: List[Dict[str, str]] = []
        self.popularity_scores: Dict[str, int] = {}
        self.ext_tally: Dict[str, int] = {}
        self.git_tracked_files: Set[str] = set()

        # ---> NEW: NEIGHBORHOOD MICRO-MASS QUOTA STATE <---
        # Prevents high-density utility directories (like icons/ or config blocks)
        # from overloading localized physical mass calculations.
        self.MICRO_MASS_BYTES = 50
        self.MICRO_MASS_GRACE_LIMIT = 15
        self.neighborhood_tracker = defaultdict(int)

        self.splicing_telemetry = {
            "top_slowest": [],
            "regex_totals": defaultdict(float),
            "files_sampled": 0,
            "regex_limit_reached": False,
        }

        self.file_speed_telemetry = {
            "phase_totals": defaultdict(float),
            "file_count": 0,
        }

    def execute_pipeline(self, output_file: str = "galaxy.json"):
        """
        Executes the synthesis protocol with a multi-recorder exit strategy.

        PIPELINE ONBOARDING (Execution Flow):
        The method enforces a strict chronological dependency chain. For example,
        Workers (Phase 1) must run before Relational Analysis (Phase 3) so that
        we have exact code tokens in RAM before mapping the API Downstream Exposure.
        Likewise, Network Topology (Phase 4) is required before XGBoost Inference
        (Phase 9) since a file's centrality influences its logic bomb threat weighting.
        """
        start_time = time.time()
        logger.info(f"--- PIPELINE_START: {self.root.name} (v{self.version}) ---")

        if not HAS_NETWORKX or not HAS_TIKTOKEN or not ML_AVAILABLE or not HAS_PYYAML:
            missing_libs = []
            if not HAS_NETWORKX:
                missing_libs.append("networkx")
            if not HAS_TIKTOKEN:
                missing_libs.append("tiktoken")
            if not ML_AVAILABLE:
                missing_libs.extend(["xgboost", "pandas", "numpy"])
            if not HAS_PYYAML:
                missing_libs.append("pyyaml")

            pip_cmd = f"pip install {' '.join(missing_libs)}"

            logger.warning("")
            logger.warning(" ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
            logger.warning(" ┃ ⚠️  ZERO-DEPENDENCY MODE ACTIVE                                         ┃")
            logger.warning(" ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫")
            logger.warning(" ┃ Missing computational engines. Metrics will be safely set to NULL:      ┃")
            if not HAS_NETWORKX:
                logger.warning(" ┃  - networkx (Network Topology, Downstream Exposure, Choke Points)       ┃")
            if not HAS_TIKTOKEN:
                logger.warning(" ┃  - tiktoken (Absolute Token Mass, Financial Read Cost)                  ┃")
            if not ML_AVAILABLE:
                logger.warning(" ┃  - xgboost, pandas (Advanced ML Threat Inference & Taxonomy)            ┃")
            if not HAS_PYYAML:
                logger.warning(" ┃  - pyyaml (Required for parsing .yaml/.yml Swagger/OpenAPI specs)       ┃")
            logger.warning(" ┃                                                                         ┃")
            logger.warning(" ┃ To unlock absolute precision, run:                                      ┃")
            logger.warning(f" ┃    {pip_cmd}".ljust(75) + "┃")
            logger.warning(" ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
            logger.warning("")

        try:
            # PHASE 0: Radar & Pre-Flight
            # OS-level walk determining physical existence, OS permissions, and intent.
            t_phase = time.time()
            self.guidestar.scan_project_config()
            self._build_file_census()
            logger.info(f"⏱️ EXECUTION_TIME [Phase 0 - Radar]: {time.time() - t_phase:.2f}s")

            # PHASE 1: Workers & IPC Extraction
            # Bypasses the GIL, deploying CPU-heavy regex scanning into isolated Memory spaces.
            t_phase = time.time()
            self._extract_features_parallel()
            logger.info(f"⏱️ EXECUTION_TIME [Phase 1 - Workers & IPC]: {time.time() - t_phase:.2f}s")

            # PHASE 2: Dependency Resolution (Import Graph)
            # Reconstructs inter-file linkages. Executes *before* Relational Analysis so we
            # can mathematically define a file's public exposure index.
            t_phase = time.time()
            self._resolve_dependency_graph()
            logger.info(f"⏱️ EXECUTION_TIME [Phase 2 - Dependency Resolution]: {time.time() - t_phase:.2f}s")

            # PHASE 3: Structural Impact Analysis
            # Fuses chronological Git telemetry with raw token counts to calculate multi-dimensional
            # risks (e.g., Tech Debt, Cognitive Load, State Flux).
            t_phase = time.time()
            self._calculate_risk_exposures()
            logger.info(f"⏱️ EXECUTION_TIME [Phase 3 - Structural Impact Analysis]: {time.time() - t_phase:.2f}s")

            # PHASE 4: Network Topology & Downstream Exposure
            # Computes PageRank and Betweenness Centrality on the assembled Dependency Graph.
            t_phase = time.time()
            self.parsed_files, network_macro = self.network_sensor.build_dependency_graph(self.parsed_files)
            logger.info(f"⏱️ EXECUTION_TIME [Phase 4 - Network Topology]: {time.time() - t_phase:.2f}s")

            # PHASE 5: Zero-Trust Guardrails (AI & AppSec)
            # Enforces explicit system rules identifying Prompt Injections or Context Window Exhaustion.
            t_phase = time.time()
            dev_firewall = DevAgentFirewall(parent_logger=logger)
            self.parsed_files = dev_firewall.evaluate_ecosystem(self.parsed_files)

            appsec_sensor = AIAppSecSensor(parent_logger=logger)
            self.parsed_files = appsec_sensor.hunt_threats(self.parsed_files)
            logger.info(f"⏱️ EXECUTION_TIME [Phase 5 - Zero-Trust Guardrails]: {time.time() - t_phase:.2f}s")

            # PHASE 6: Spectral Audit & Verification
            # Uses standard deviations to identify and drop un-parseable data dumps or log files.
            t_phase = time.time()
            repository_graph, unparsable_audits = self.auditor.audit(self.parsed_files)
            total_unparsable = self.unparsable_files + unparsable_audits
            logger.info(f"⏱️ EXECUTION_TIME [Phase 6 - Spectral Audit]: {time.time() - t_phase:.2f}s")

            # PHASE 7: Dependency Graphing & Visualization
            # Assigns coordinates based on topological hierarchies for WebGL.
            t_phase = time.time()
            if repository_graph:
                repository_graph = self.spatial_mapper.map_repository(repository_graph)
            files_mapped_count = len(repository_graph) if repository_graph else 0
            logger.info(f"⏱️ EXECUTION_TIME [Phase 7 - Dependency Graphing]: {time.time() - t_phase:.2f}s")

            # PHASE 8: Metrics Synthesis & Forensics
            # Aggregates raw outputs for the LLM payload generation.
            t_phase = time.time()
            summary = self.processor.summarize_galaxy_metrics(repository_graph, total_unparsable)
            summary["network_macro"] = network_macro
            report = self.processor.generate_forensic_report(repository_graph)
            logger.info(f"⏱️ EXECUTION_TIME [Phase 8 - Metrics Synthesis]: {time.time() - t_phase:.2f}s")

            # PHASE 9: ML Threat Inference & Graph Resolution
            # Processes the fully formed context through XGBoost trees to isolate embedded Trojans/Stealers.
            t_phase = time.time()
            if repository_graph:
                # Pass the Shadow Patch flag to the Security Auditor
                is_shadow_patch = self.config.get("SHADOW_PATCH_DETECTED", False)
                repository_graph = self.model_auditor.audit_repository(
                    repository_graph, is_shadow_patch=is_shadow_patch
                )
            logger.info(f"⏱️ EXECUTION_TIME [Phase 9 - ML Threat Inference]: {time.time() - t_phase:.2f}s")

            # ==========================================================
            # PHASE 10: ECOSYSTEM SECURITY AUDITS
            # Evaluates structural boundaries (Ghost APIs, Supply Chain spoofing).
            # ==========================================================
            logger.info("Phase 10: Executing Ecosystem Security Audits (X-Ray, Firewall, API Mapper)...")

            # 1. Gather all manifests instantly using the Phase 0 stem_map (Zero Disk Walk)
            target_manifests = set(GUIDESTAR_CONFIG.get("MANIFEST_MAP", {}).keys())
            manifest_paths = [
                str(self.root / rel_path)
                for rel_path in self.stem_map.values()
                if Path(rel_path).name in target_manifests
            ]

            # 2. Build the global translation map
            from gitgalaxy.security.manifest_parser import ManifestParser

            alias_map = ManifestParser(parent_logger=logger).build_resolution_map(manifest_paths)

            ecosystem_audits = {
                "api_mapper": run_api_audit(self.root),
                "xray": run_xray_audit(self.root),
                # 3. Pass the RAM graph and the alias map to the Firewall
                "firewall": run_firewall_audit(repository_graph, alias_map=alias_map),
            }

            # Attach it to the summary payload
            summary["ecosystem_audits"] = ecosystem_audits
            
            # ==========================================================
            # PHASE 10.5: CI/CD POLICY ENFORCEMENT GATE
            # ==========================================================
            self.policy_failed = False
            max_risk_allowed = self.config.get("MAX_RISK_EXPOSURE", 0.0)
            
            if self.config.get("FAIL_ON_SECRETS") or self.config.get("FAIL_ON_MALWARE") or max_risk_allowed > 0.0:
                logger.info("🛡️ Evaluating CI/CD Threat Thresholds...")
                
                from gitgalaxy.metrics.signal_processor import SignalProcessor
                
                for file_data in (repository_graph or []):
                    # 1. Absolute Security Floor (Secrets)
                    if self.config.get("FAIL_ON_SECRETS"):
                        has_secrets = False
                        
                        # Extract mitigations safely
                        mitigs = file_data.get("mitigations", [])
                        if isinstance(mitigs, dict):
                            mitigs = list(mitigs.keys())
                        elif not isinstance(mitigs, list):
                            mitigs = []
                            
                        if "sec_hardcoded_secrets" not in mitigs and "secrets_risk" not in mitigs:
                            # Check Risk Vector
                            if "secrets_risk" in SignalProcessor.RISK_SCHEMA:
                                idx = SignalProcessor.RISK_SCHEMA.index("secrets_risk")
                                rv = file_data.get("risk_vector", [])
                                if isinstance(rv, list) and len(rv) > idx and rv[idx] > 0.0:
                                    has_secrets = True
                            
                            # THE FIX: Bulletproof Truthiness Check
                            ts = file_data.get("telemetry", {}).get("threat_snippets", {})
                            if isinstance(ts, dict):
                                if ts.get("hardcoded_secrets") or ts.get("sec_hardcoded_secrets"):
                                    has_secrets = True
                                
                            # Check Domain Context
                            ctx = file_data.get("telemetry", {}).get("domain_context", {})
                            if isinstance(ctx, dict):
                                warning_msg = ctx.get("warning", "")
                                if warning_msg and "CRITICAL CREDENTIAL LEAK DETECTED" in str(warning_msg):
                                    has_secrets = True
                                
                        if has_secrets:
                            logger.critical(f"BUILD FAILED: Hardcoded secret detected in {file_data.get('path', 'unknown')}")
                            self.policy_failed = True

                    # 2. XGBoost Malware Floor
                    if self.config.get("FAIL_ON_MALWARE") and file_data.get("is_ml_threat", False):
                        ai_class = file_data.get("telemetry", {}).get("domain_context", {}).get("AI Threat Class", "Unknown")
                        logger.critical(f"BUILD FAILED: Behavioral malware signature ({ai_class}) detected in {file_data.get('path', 'unknown')}")
                        self.policy_failed = True
                        
                    # 3. Maximum Risk Exposure Ratchet
                    if max_risk_allowed > 0.0:
                        risk_vec = file_data.get("risk_vector", [])
                        highest_risk = max(risk_vec) if isinstance(risk_vec, list) and risk_vec else 0.0
                        if highest_risk >= max_risk_allowed:
                            logger.critical(f"BUILD FAILED: {file_data.get('path', 'unknown')} exceeded maximum risk threshold ({highest_risk}% >= {max_risk_allowed}%)")
                            self.policy_failed = True

            # ==========================================================
            # PHASE 10.8: SARIF SANITIZATION (Purge Suppressed Alerts & Config Exclusions)
            # ==========================================================
            logger.info("🧹 Sanitizing telemetry to prevent export of mitigated and ignored threats...")
            
            ignored_rules = self.config.get("SARIF_IGNORED_RULES", [])
            ignored_paths = self.config.get("SARIF_IGNORED_PATHS", [])
            
            for file_data in (repository_graph or []):
                # Ensure cross-platform slash normalization
                file_path = file_data.get("path", "").replace("\\", "/")
                path_excluded = any(p in file_path for p in ignored_paths)
                
                if path_excluded:
                    file_data["equations"] = {}
                    file_data["is_ml_threat"] = False
                    
                    if "hit_vector" in file_data and isinstance(file_data["hit_vector"], list):
                        file_data["hit_vector"] = [0] * len(file_data["hit_vector"])
                        
                    if "risk_vector" in file_data and isinstance(file_data["risk_vector"], list):
                        file_data["risk_vector"] = [0.0] * len(file_data["risk_vector"])
                        
                    if "telemetry" in file_data:
                        file_data["telemetry"]["threat_snippets"] = {}
                        file_data["telemetry"]["network_metrics"] = {} 
                        file_data["telemetry"]["domain_context"] = {}
                    continue
                
                mitigs = file_data.get("mitigations", [])
                if isinstance(mitigs, dict):
                    mitigs = list(mitigs.keys())
                elif not isinstance(mitigs, list):
                    mitigs = []
                
                ts = file_data.get("telemetry", {}).get("threat_snippets", {})
                eqs = file_data.get("equations", {})
                
                if isinstance(ts, dict) and isinstance(eqs, dict):
                    keys_to_delete_ts = [
                        k for k in ts.keys() 
                        if k in mitigs 
                        or f"sec_{k}" in mitigs 
                        or k.replace("sec_", "") in mitigs
                        or k in ignored_rules
                        or f"sec_{k}" in ignored_rules
                    ]
                    keys_to_delete_eqs = [
                        k for k in eqs.keys()
                        if k in mitigs
                        or k.replace("sec_", "") in mitigs
                        or k in ignored_rules
                        or k.replace("sec_", "") in ignored_rules
                    ]
                    
                    for k in keys_to_delete_ts:
                        if k in ts:
                            del ts[k]
                            
                    for k in keys_to_delete_eqs:
                        if k in eqs:
                            del eqs[k]

            # ==========================================================
            # PHASE 11: GLOBAL TELEMETRY & METADATA LOCKING
            # ==========================================================
            # Calculate physical mass before the GPU Recorder destroys the repository_graph list
            total_loc = sum(s.get("total_loc", 0) for s in (repository_graph or []))

            # Calculate rate using exact precision BEFORE rounding for display
            raw_duration = time.time() - start_time
            loc_per_sec = int(total_loc / raw_duration) if raw_duration > 0 else 0
            duration = round(raw_duration, 2)

            session_meta = {
                "engine": f"GitGalaxy Scope v{self.version} (Delta Mode)",
                "target": self.root.name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(time.time() - start_time, 2),
                "target_directory": str(self.root.resolve()),
                "git_audit": self._get_git_audit(),
                "missing_dependencies": {
                    "networkx": not HAS_NETWORKX,
                    "tiktoken": not HAS_TIKTOKEN,
                    "xgboost": not ML_AVAILABLE,
                    "pyyaml": not HAS_PYYAML,
                },
                "zero_dependency_mode": (not HAS_NETWORKX or not HAS_TIKTOKEN or not ML_AVAILABLE or not HAS_PYYAML),
            }

            if "unparsable_files" not in summary:
                summary["unparsable_files"] = {}

            # Pass the array into the function, and merge the results directly
            summary["unparsable_files"].update(self._summarize_anomalies(total_unparsable))

            # --- PURE OUTPUT ROUTER ---
            # Respect the exact path provided, just ensure the parent folder exists
            out_path = Path(output_file).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            output_file = str(out_path)
            # --------------------------

            # --- CHECK EXCLUSIVE MODE FLAGS ---
            exclusive_mode = (
                self.config.get("LLM_ONLY")
                or self.config.get("GPU_ONLY")
                or self.config.get("AUDIT_ONLY")
                or self.config.get("DB_ONLY")
                or self.config.get("SARIF_ONLY")
                or self.config.get("SBOM_ONLY")
            )
            audit_output = "Skipped"

            # ==========================================================
            # PHASE 12: ARCHIVAL & EXPORT ROUTING
            # Delegates the sealed state objects to output-specific engines.
            # ==========================================================

            # --- Phase 12.1: Audit Recorder (Forensic Log) ---
            if not exclusive_mode or self.config.get("AUDIT_ONLY"):
                try:
                    out_path = Path(output_file)
                    safe_suffix = out_path.suffix if out_path.suffix else ".json"
                    audit_output = str(out_path.with_name(f"{out_path.stem}_audit{safe_suffix}"))
                    logger.debug(f"AUDIT: Generating comprehensive human-readable forensic log -> {audit_output}")

                    self.audit_recorder.generate_report(
                        parsed_files=repository_graph,
                        unparsable_files=total_unparsable,
                        summary=summary,
                        forensic_report=report,
                        session_meta=session_meta,
                        output_path=audit_output,
                    )
                except Exception as e:
                    logger.error(
                        f"AUDIT_FAILURE: Could not generate forensic log. {e}",
                        exc_info=True,
                    )

            # --- Phase 12.2: LLM Recorder (AI Context) ---
            if not exclusive_mode or self.config.get("LLM_ONLY"):
                try:
                    output_dir = str(Path(output_file).parent)
                    logger.info(f"LLM: Generating AI translation artifacts -> {output_dir}")

                    self.llm_recorder.generate_artifacts(
                        parsed_files=repository_graph,
                        unparsable_files=total_unparsable,
                        summary=summary,
                        session_meta=session_meta,
                        output_dir=output_dir,
                        forensic_report=report,
                    )
                except Exception as e:
                    logger.error(
                        f"LLM_FAILURE: Could not generate AI artifacts. {e}",
                        exc_info=True,
                    )

            # --- Phase 12.3: SQLite Recorder (Native Database) ---
            if not exclusive_mode or self.config.get("DB_ONLY"):
                try:
                    db_output = str(Path(output_file).with_name(f"{Path(output_file).stem}_master.db"))
                    logger.info(f"SQLITE: Generating repository-specific database -> {db_output}")

                    self.db_recorder.record_mission(
                        parsed_files=(list(repository_graph) if repository_graph else []),  # <--- PASS A COPY
                        unparsable_files=(list(total_unparsable) if total_unparsable else []),  # <--- PASS A COPY
                        summary=summary,
                        session_meta=session_meta,
                        output_path=db_output,
                    )
                except Exception as e:
                    logger.error(
                        f"SQLITE_FAILURE: Could not generate native database. {e}",
                        exc_info=True,
                    )

            # --- Phase 12.4: SARIF Recorder (Enterprise Security JSON) ---
            if not exclusive_mode or self.config.get("SARIF_ONLY"):
                try:
                    sarif_output = str(Path(output_file).with_name(f"{Path(output_file).stem}_sarif.json"))
                    logger.info(f"SARIF: Generating standardized security payload -> {sarif_output}")

                    self.sarif_recorder.generate_report(
                        parsed_files=repository_graph,
                        summary=summary,
                        session_meta=session_meta,
                        output_path=sarif_output,
                    )
                except Exception as e:
                    logger.error(
                        f"SARIF_FAILURE: Could not generate enterprise payload. {e}",
                        exc_info=True,
                    )

            # --- Phase 12.5: SBOM Recorder (CycloneDX Generation) ---
            if not exclusive_mode or self.config.get("SBOM_ONLY"):
                try:
                    sbom_output = str(Path(output_file).with_name(f"{Path(output_file).stem}_sbom.json"))
                    logger.info(f"SBOM: Generating standard manifest -> {sbom_output}")

                    self.sbom_recorder.generate_report(
                        parsed_files=repository_graph,
                        summary=summary,
                        session_meta=session_meta,
                        output_path=sbom_output,
                    )
                except Exception as e:
                    logger.error(
                        f"SBOM_FAILURE: Could not generate CycloneDX manifest. {e}",
                        exc_info=True,
                    )

            # --- Phase 12.6: GPU Recorder (Destructive Columnar Pivot) ---
            gpu_output = str(Path(output_file).with_name(f"{Path(output_file).stem}_gpu.json"))

            if not exclusive_mode or self.config.get("GPU_ONLY"):
                logger.info(f"GPU: Generating minified payload -> {gpu_output}")
                # record_mission destructively clears RAM as it pivots
                payload = self.gpu_recorder.record_mission(
                    parsed_files=repository_graph,
                    unparsable_files=total_unparsable,
                    summary=summary,
                    forensic_report=report,
                    repo_name=self.root.name,
                    session_meta=session_meta,
                )

                payload["meta"]["session"] = session_meta
                self.gpu_recorder.save_minified(payload, gpu_output)

            logger.info(f"--- PIPELINE_SUCCESS: {files_mapped_count} files mapped in {duration}s ---")
            logger.info(f"--- ENGINE_TELEMETRY: Processed {total_loc:,} lines of code at {loc_per_sec:,} LOC/s ---")
            logger.info(f"--- ARCHIVES_SEALED: {gpu_output} & {audit_output} ---")

            if not HAS_NETWORKX or not HAS_TIKTOKEN:
                logger.warning(
                    " ⚠️  NOTE: Pipeline completed in Zero-Dependency Mode. Run `pip install networkx tiktoken` for full precision."
                )

            if self.config.get("FILE_SPEED"):
                self._render_file_speed_chart()

            if self.config.get("SPLICING_SPEED"):
                self._render_splicing_chart()

            # --- THE FINAL CALL TO ACTION (CLI BILLBOARD) ---
            print("\n" + "=" * 75)

            # Windows command prompts crash on emojis, so we strip it for them
            if sys.platform == "win32":
                print(" READY FOR VISUALIZATION (100% LOCAL / ZERO UPLOAD)")
            else:
                print(" 🌌 READY FOR VISUALIZATION (100% LOCAL / ZERO UPLOAD)")

            print("=" * 75)
            print(" 1. Open your browser to: \033[94m\033[4m[https://gitgalaxy.io/](https://gitgalaxy.io/)\033[0m")
            print(f" 2. Drag and drop '{gpu_output}'")
            print("\n * PRIVACY SECURED: Your data never leaves your machine.")
            print("   All architectural rendering executes locally in your browser.")
            print("=" * 75 + "\n")

        except Exception as e:
            logger.critical(f"FATAL_SYSTEM_COLLAPSE: {str(e)}", exc_info=True)
            raise
        finally:
            self.cleanup()

    def _build_file_census(self):
        """Phase 0: Building the Census via Git Authority with Fallback."""
        try:
            raw_output = subprocess.check_output(
                ["git", "ls-files"], cwd=self.root, text=True, stderr=subprocess.DEVNULL
            )
            git_paths = raw_output.splitlines()
            self.git_tracked_files = set(git_paths)

            # --- FAST I/O: ThreadPool for os.stat operations ---
            def _inspect_path(rel_path):
                path_obj = Path(rel_path)
                full_path = self.root / path_obj
                has_intent, _ = self.guidestar.get_intent_status(path_obj)
                is_valid, size_bytes, reason = self.filter.evaluate_path_integrity(full_path, has_intent=has_intent)
                return rel_path, path_obj, is_valid, size_bytes, reason

            # Use 32 threads to saturate the disk I/O queue
            with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
                inspections = executor.map(_inspect_path, git_paths)

            # Process the results synchronously to prevent race conditions on state maps
            for rel_path, path_obj, is_valid, size_bytes, reason in inspections:
                # ---> NEW: THE NEIGHBORHOOD MICRO-MASS QUOTA <---
                # Exempt mainframe files (COBOL/JCL) from being flagged as micro-debris
                safe_ext = path_obj.suffix.lower()
                if is_valid and size_bytes < self.MICRO_MASS_BYTES and safe_ext not in {".cpy", ".cbl", ".cob", ".jcl"}:
                    dir_path = str(path_obj.parent)
                    self.neighborhood_tracker[dir_path] += 1

                    if self.neighborhood_tracker[dir_path] > self.MICRO_MASS_GRACE_LIMIT:
                        is_valid = False
                        reason = "Excluded: Neighborhood Micro-Mass Limit Exceeded"
                # ------------------------------------------------

                if is_valid:
                    stem = path_obj.stem.lower()
                    ext = path_obj.suffix.lower()
                    name = path_obj.name.lower()

                    self.census.add(stem)
                    self.stem_map[rel_path] = rel_path

                    # ---> Tally both the extension AND the full filename
                    self.ext_tally[ext] = self.ext_tally.get(ext, 0) + 1
                    self.ext_tally[name] = self.ext_tally.get(name, 0) + 1
                else:
                    # Route directly to Unparsable Artifacts, bypassing the Multi-Processing pool
                    self.unparsable_files.append(
                        {
                            "path": rel_path,
                            "reason": reason,
                            "identity_confidence": 0.0,
                            "size_bytes": size_bytes,
                        }
                    )
                    self._record_anomaly(rel_path, reason)

            logger.info(f"CENSUS_COMPLETE: Found {len(git_paths)} tracked artifacts via Git.")

        except (subprocess.CalledProcessError, FileNotFoundError):
            self.git_tracked_files = set()
            logger.warning("GIT_NOT_FOUND: Reverting to standard filesystem walk.")
            self._fallback_filesystem_walk()

    def _fallback_filesystem_walk(self):
        """
        Standard OS-level filesystem walk for non-Git projects or ZIP archives.

        Acts as the fallback mechanism if `git ls-files` fails. Evaluates every file against
        the Aperture filter's Ignored Directories and dynamic micro-mass quotas, discarding ignored
        assets before they are added to the active Census.
        """
        for root, dirs, files in os.walk(self.root):
            # Add [0] to extract just the boolean 'is_valid'
            dirs[:] = [d for d in dirs if self.filter.evaluate_path_integrity(Path(root) / d)[0]]
            for file in files:
                full_p = Path(root) / file
                is_valid, size_bytes, reason = self.filter.evaluate_path_integrity(full_p)

                # ---> NEW: THE NEIGHBORHOOD MICRO-MASS QUOTA <---
                # Exempt mainframe files (COBOL/JCL) from being flagged as micro-debris
                safe_ext = full_p.suffix.lower()
                if is_valid and size_bytes < self.MICRO_MASS_BYTES and safe_ext not in {".cpy", ".cbl", ".cob", ".jcl"}:
                    dir_path = str(full_p.parent.relative_to(self.root))
                    self.neighborhood_tracker[dir_path] += 1
                    if self.neighborhood_tracker[dir_path] > self.MICRO_MASS_GRACE_LIMIT:
                        is_valid = False
                        reason = "Excluded: Neighborhood Micro-Mass Limit Exceeded"
                # ------------------------------------------------

                rel_p = str(full_p.relative_to(self.root))

                if is_valid:
                    stem = full_p.stem.lower()
                    ext = full_p.suffix.lower()
                    name = full_p.name.lower()  # <-- Extract lowercased filename

                    self.census.add(stem)
                    self.stem_map[rel_p] = rel_p

                    # ---> Tally both the extension AND the full filename
                    self.ext_tally[ext] = self.ext_tally.get(ext, 0) + 1
                    self.ext_tally[name] = self.ext_tally.get(name, 0) + 1
                else:
                    self.unparsable_files.append(
                        {
                            "path": rel_p,
                            "reason": reason,
                            "identity_confidence": 0.0,
                            "size_bytes": size_bytes,
                        }
                    )
                    self._record_anomaly(rel_p, reason)

    def _extract_features_parallel(self):
        """
        Phase 1: Parallel Extraction & Asset Filtering via Multi-Core Map-Reduce.

        Dispatches the physical file paths to the isolated worker pool (bypassing the GIL).
        As the workers complete their high-speed regex extraction, this method consumes the
        futures dynamically to prevent O(N^2) polling wait states. It catches structural
        saturations (ReDoS), logs processing telemetry, and aggregates the extracted 
        Structural Signatures into the global RAM cache.
        """
        total_files = len(self.stem_map)
        logger.info(f"PASS_1: Optical sequence initiated for {total_files} artifacts via ProcessPoolExecutor.")

        if total_files == 0:
            return

        cpu_count = os.cpu_count()
        if cpu_count is None:
            cpu_count = 4
        max_workers = max(1, cpu_count - 1)

        current_log_level = logging.getLogger().getEffectiveLevel()
        completed_count = 0

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,
            initargs=(
                str(self.root),
                self.config,
                self.ext_tally,
                current_log_level,
                self.git_tracked_files,
                self.census,
            ),
        ) as executor:
            # Map futures to their file paths in a tracking dictionary
            active_futures = {
                executor.submit(_process_file_worker, rel_path): rel_path for rel_path in self.stem_map.values()
            }

            # THE STARVATION MONITOR (Event-Driven Generator)
            # as_completed yields instantly upon future completion, averting O(N^2) polling wait states.
            try:
                # THE FIX: Removed `timeout=60.0`. Python's timeout is an absolute mission timer,
                # not an idle worker timer. Massive repositories (80k+ files) take more than
                # 60 seconds to scan end-to-end. Infinite loops are now prevented
                # natively by the 1500-char Line Limiter and strict Regex bounds.
                for future in concurrent.futures.as_completed(active_futures):
                    rel_path = active_futures.pop(future)
                    completed_count += 1

                    if completed_count % 50 == 0:
                        logger.info(f"PROGRESS: Surveyed {completed_count}/{total_files} coordinates.")

                    try:
                        res = future.result()
                        status = res["status"]

                        if status == "success":
                            self.ram_cache[rel_path] = res["data"]

                            if self.config.get("FILE_SPEED"):
                                p_times = res.get("phase_times", {})
                                for phase, duration in p_times.items():
                                    self.file_speed_telemetry["phase_totals"][phase] += duration
                                self.file_speed_telemetry["file_count"] += 1

                            if self.config.get("SPLICING_SPEED"):
                                process_time = res.get("processing_time", 0)

                                # 1. Always track the globally slowest files (bounded to save RAM)
                                self.splicing_telemetry["top_slowest"].append({"path": rel_path, "time": process_time})

                                # Keep the array tiny: Sort and truncate every 50 files
                                if len(self.splicing_telemetry["top_slowest"]) > 50:
                                    self.splicing_telemetry["top_slowest"].sort(key=lambda x: x["time"], reverse=True)
                                    self.splicing_telemetry["top_slowest"] = self.splicing_telemetry["top_slowest"][:10]

                                # 2. Cap Regex Telemetry at 5,000 files to save RAM
                                if not self.splicing_telemetry["regex_limit_reached"]:
                                    regex_stats = res["data"].pop("regex_telemetry", {})

                                    for regex_name, duration in regex_stats.items():
                                        self.splicing_telemetry["regex_totals"][regex_name] += duration

                                    self.splicing_telemetry["files_sampled"] += 1
                                    if self.splicing_telemetry["files_sampled"] >= 5000:
                                        self.splicing_telemetry["regex_limit_reached"] = True
                                        logger.warning(
                                            "SPLICING SPEED: 5,000 file sample reached. Halting regex telemetry (Global file speeds still tracking)."
                                        )

                        elif status == "parser_bypass":
                            logger.debug(
                                f"UNPARSABLE_BYPASS: '{rel_path}' lacks structural integrity. Relegating to Excluded Artifacts."
                            )
                            self.unparsable_files.append(
                                {
                                    "path": rel_path,
                                    "reason": res["reason"],
                                    "identity_confidence": res.get("identity_confidence", 0.0),
                                    "size_bytes": res.get("size_bytes", 0),
                                }
                            )
                            self._record_anomaly(rel_path, res["reason"])

                        elif status in ("filtered", "anomaly"):
                            self._record_anomaly(rel_path, res["reason"])

                    except Exception as e:
                        logger.error(f"WORKER_CRASH on {rel_path}: {e}")
                        self._record_anomaly(rel_path, f"Fatal Worker Crash: {str(e)}")

            except concurrent.futures.TimeoutError:
                logger.error("\n" + "=" * 75)
                logger.error(" SYSTEM HALT: Worker Thread Starvation")
                logger.error(" All CPU workers have exceeded the 60.0s execution limit.")
                logger.error(" This indicates Catastrophic Backtracking (ReDoS) in the regex engine.")
                logger.error(" The following artifacts paralyzed the thread pool:")

                for future in active_futures:
                    stuck_file = active_futures[future]
                    logger.error(f"  -> TIMEOUT: {stuck_file}")

                    self._record_anomaly(stuck_file, "Thread Timeout (Regex ReDoS)")
                    self.unparsable_files.append(
                        {
                            "path": stuck_file,
                            "reason": "Thread Timeout (Regex ReDoS)",
                            "identity_confidence": 0.0,
                            "size_bytes": 0,
                        }
                    )

                logger.error("=" * 75 + "\n")
                logger.warning("Aborting synthesis to unfreeze the terminal. Please check the Anti-ReDoS shields.")

                executor.shutdown(wait=False, cancel_futures=True)
                raise TimeoutError("Mission aborted due to worker starvation (ReDoS or IPC Deadlock).")

    def _resolve_dependency_graph(self):
        """
        Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching.
        Defused O(N^2) Bomb using O(1) Pre-Sliced Suffix Hash Maps.
        """
        logger.info("PASS_1.5: Resolving import graphs via O(1) Pre-computed Suffix Hash Maps...")

        self.popularity_scores = {rel_path: 0 for rel_path in self.stem_map.values()}
        repo_file_paths = set(self.stem_map.values())

        # --- O(1) SUFFIX MAP ---
        suffix_map = {}
        stem_to_paths = {}

        for repo_file in repo_file_paths:
            s = Path(repo_file).stem.lower()
            if s not in stem_to_paths:
                stem_to_paths[s] = []
            stem_to_paths[s].append(repo_file)

            norm_repo = repo_file.replace("\\", "/")
            repo_no_ext = norm_repo.rsplit(".", 1)[0] if "." in Path(norm_repo).name else norm_repo

            parts_ext = norm_repo.split("/")
            for i in range(len(parts_ext)):
                suffix = "/".join(parts_ext[i:])
                if suffix not in suffix_map:
                    suffix_map[suffix] = []
                suffix_map[suffix].append(repo_file)

            parts_no_ext = repo_no_ext.split("/")
            for i in range(len(parts_no_ext)):
                suffix = "/".join(parts_no_ext[i:])
                if suffix not in suffix_map:
                    suffix_map[suffix] = []
                if repo_file not in suffix_map[suffix]:
                    suffix_map[suffix].append(repo_file)

        stop_stems = {
            "text",
            "type",
            "types",
            "param",
            "params",
            "index",
            "main",
            "data",
            "util",
            "utils",
            "config",
            "common",
            "core",
            "base",
            "app",
            "model",
            "models",
            "schema",
            "style",
            "styles",
            "global",
            "env",
            "helper",
            "helpers",
            "constants",
            "init",
            "setup",
            "view",
            "testing",
            "compat",
            "api",
            "tools",
            "format",
            "os",
            "sys",
            "math",
            "time",
            "datetime",
            "json",
            "csv",
            "pickle",
            "copy",
            "warnings",
            "collections",
            "itertools",
            "functools",
            "numpy",
            "pytest",
            "cython",
            "typing",
            "io",
        }

        # --- THE REGEX OPTIMIZATION ---
        import_cleaner = re.compile(
            r"^(?:#\s*include|%\s*include|import|export import|from|require|use|source)\s*",
            re.IGNORECASE,
        )

        external_imports_tally = {}  # <--- NEW: Track external dependencies

        for rel_path, meta in self.ram_cache.items():
            raw_imports = meta.get("raw_imports", set())
            for raw_import in raw_imports:
                clean_path = import_cleaner.sub("", raw_import.strip())
                if "from" in clean_path:
                    clean_path = clean_path.split("from")[-1]

                clean_path = clean_path.strip("<>\"'; ()").replace("\\", "/")
                if not clean_path:
                    continue

                if "." in clean_path and "/" not in clean_path:
                    ext_guess = "." + clean_path.rsplit(".", 1)[-1].lower()
                    if ext_guess not in self.ext_tally:
                        clean_path = clean_path.replace(".", "/")

                clean_path = clean_path.lstrip("./")
                if not clean_path:
                    continue

                matched_internal = False  # <--- NEW: Flag to verify if import is local

                # --- FAST PATH 1: O(1) Suffix & Exact Match ---
                if clean_path in suffix_map:
                    matched_internal = True
                    for target_path in suffix_map[clean_path]:
                        self.popularity_scores[target_path] += 1

                # --- FAST PATH 2: O(1) Python Package Resolution ---
                if not matched_internal:
                    init_path = clean_path + "/__init__"
                    if init_path in suffix_map:
                        matched_internal = True
                        for target_path in suffix_map[init_path]:
                            self.popularity_scores[target_path] += 1

                # --- THE FALLBACK: Stem Matching ---
                if not matched_internal:
                    guess_stem = Path(clean_path).stem.lower()
                    if guess_stem in stem_to_paths and guess_stem not in stop_stems and len(guess_stem) >= 3:
                        for target_path in stem_to_paths[guess_stem]:
                            if clean_path in target_path or guess_stem == clean_path:
                                self.popularity_scores[target_path] += 1
                                matched_internal = True
                            elif "/" not in clean_path:
                                self.popularity_scores[target_path] += 1
                                matched_internal = True

                # ---> NEW: LOG EXTERNAL IMPORTS <---
                if not matched_internal:
                    if clean_path not in external_imports_tally:
                        external_imports_tally[clean_path] = []
                    external_imports_tally[clean_path].append(rel_path)

        # =========================================================================
        # ---> NEW: THE AIR-GAPPED TYPOSQUATTING RADAR <---
        # =========================================================================
        logger.info("PASS_1.5: Running Air-Gapped Typosquatting & Dependency Confusion Radar...")

        anchors = []
        orphans = []

        # 1. Separate Anchors (Used heavily) and Orphans (Used once)
        for ext_imp, paths in external_imports_tally.items():
            if len(paths) >= 3:
                anchors.append(ext_imp)
            elif len(paths) == 1:
                orphans.append((ext_imp, paths[0]))

        # 2. Fast Levenshtein Distance (Inline to avoid external dependencies)
        def _levenshtein(s1, s2):
            if len(s1) < len(s2):
                return _levenshtein(s2, s1)
            if len(s2) == 0:
                return len(s1)
            prev = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                curr = [i + 1]
                for j, c2 in enumerate(s2):
                    curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
                prev = curr
            return prev[-1]

        # ---> NEW: SymSpell O(1) Pre-Filter (Eliminates O(N^2) loops) <---
        def _get_deletes(word):
            deletes = {word}
            for i in range(len(word)):
                deletes.add(word[:i] + word[i + 1 :])
            return deletes

        anchor_index = {}
        for anchor_imp in anchors:
            if len(anchor_imp) < 5:
                continue
            for variant in _get_deletes(anchor_imp):
                if variant not in anchor_index:
                    anchor_index[variant] = set()
                anchor_index[variant].add(anchor_imp)

        from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG

        whitelist = APERTURE_CONFIG.get("TYPOSQUAT_WHITELIST", set())

        typosquat_hits = 0
        for orphan_imp, rel_path in orphans:
            # 1. The Project Override Shield & Length Shield
            if orphan_imp in whitelist or len(orphan_imp) < 5:
                continue

            # 2. O(1) Candidate Lookup (Only test strings in the exact same neighborhood)
            candidates = set()
            for variant in _get_deletes(orphan_imp):
                if variant in anchor_index:
                    candidates.update(anchor_index[variant])

            for anchor_imp in candidates:
                # 3. The Casing Shield (Developer typos, not malware)
                if orphan_imp.lower() == anchor_imp.lower():
                    continue

                # 4. The OOP Interface Shield (Prevents 'IEmailer' vs 'Emailer')
                orphan_base = orphan_imp.split("/")[-1]
                anchor_base = anchor_imp.split("/")[-1]
                if orphan_base == f"I{anchor_base}" or anchor_base == f"I{orphan_base}":
                    continue

                # Ignore massive length differences to save CPU cycles
                if abs(len(orphan_imp) - len(anchor_imp)) > 2:
                    continue

                dist = _levenshtein(orphan_imp, anchor_imp)

                # 5. Dynamic Distance Threshold
                max_dist = 1 if min(len(orphan_imp), len(anchor_imp)) < 10 else 2

                if 0 < dist <= max_dist:
                    logger.critical(
                        f"🚨 TYPOSQUATTING DETECTED: '{orphan_imp}' in {rel_path} closely matches anchor '{anchor_imp}'!"
                    )

                    # Inject the threat directly into the file's equations before Phase 2
                    if "equations" not in self.ram_cache[rel_path]:
                        self.ram_cache[rel_path]["equations"] = {}

                    self.ram_cache[rel_path]["equations"]["sec_homoglyphs"] = (
                        self.ram_cache[rel_path]["equations"].get("sec_homoglyphs", 0) + 1
                    )

                    if "metadata" not in self.ram_cache[rel_path]:
                        self.ram_cache[rel_path]["metadata"] = {}
                    self.ram_cache[rel_path]["metadata"]["alert"] = (
                        f"TYPOSQUATTING THREAT: '{orphan_imp}' mimics '{anchor_imp}'"
                    )

                    typosquat_hits += 1
                    break  # Move to next orphan

        if typosquat_hits > 0:
            logger.warning(f"Intercepted {typosquat_hits} typosquatting attempts via repository baseline analysis.")

        # Evict memory before Pass 2
        for rel_path, meta in self.ram_cache.items():
            if "popularity_hits" in meta:
                del meta["popularity_hits"]

    def _calculate_risk_exposures(self):
        """
        Phase 3: Universal Exposure Framework & Signal Processing.

        Translates raw Structural Signatures into 18-point physical risk vectors (e.g., Tech Debt,
        Cognitive Load, State Flux). This pass applies architectural dampeners (like testing
        umbrellas and documentation shields), resolves test coverage graphs, and routes
        extracted metadata to the SignalProcessor for final heuristic scoring.
        """
        logger.info("PASS_2: Calculating structural impact and Tiered Normalization.")

        # ==============================================================
        # NEW: CALCULATE FOLDER CONTEXTS (For Domain Ontologies)
        # Tally the languages in every folder to find the dominant ecosystem
        # ==============================================================
        folder_tallies = {}
        for rel_path, meta in self.ram_cache.items():
            folder = str(Path(rel_path).parent)
            lang = meta.get("lang_id", "unknown")

            if folder not in folder_tallies:
                folder_tallies[folder] = {}
            folder_tallies[folder][lang] = folder_tallies[folder].get(lang, 0) + 1

        folder_dominant_langs = {}
        for folder, tallies in folder_tallies.items():
            if tallies:
                # The language with the most files wins the neighborhood
                folder_dominant_langs[folder] = max(tallies, key=tallies.get)

        # --- NEW: CALCULATE THE GLOBAL TEST UMBRELLA ---
        total_loc = 0
        test_loc = 0

        # ==============================================================
        # ---> NEW: BUILD GLOBAL TOKEN TRACKER <---
        # ==============================================================
        self.used_tokens = set()
        for meta in self.ram_cache.values():
            self.used_tokens.update(meta.get("named_tokens", []))
        # ==============================================================

        # ==============================================================
        # ---> TEST COVERAGE MAPPING <---
        # Sweep the galaxy for test files and map their outbound calls
        # directly to the production functions they verify.
        # ==============================================================
        logger.info("PASS_2: Extracting Test Coverage Mapping...")
        test_coverage_map = self.network_sensor.extract_test_coverage_mapping(list(self.ram_cache.values()))
        # ==============================================================

        # ==============================================================
        # ---> NEW: CALCULATE INSTRUCTIONAL DENSITY MULTIPLIERS <---
        # Aggregate markdown heuristics to upgrade the doc_umbrella shields
        # ==============================================================
        instructional_multipliers = {}
        for rel_path, meta in self.ram_cache.items():
            if meta.get("lang_id") == "markdown":
                folder = str(Path(rel_path).parent).replace("\\", "/")
                if folder == ".":
                    folder = "__root__"

                eq = meta.get("equations", {})

                # Instructional Mass = Diagrams (10x) + Code Blocks (5x) + Headers (1x) + Links (0.5x)
                instructional_mass = (
                    (eq.get("lit_diagrams", 0) * 10.0)
                    + (eq.get("lit_code_blocks", 0) * 5.0)
                    + (eq.get("lit_headers", 0) * 1.0)
                    + (eq.get("lit_links", 0) * 0.5)
                )

                # Base Multiplier is 1.0. High-quality docs can double the shield (2.0)
                multiplier = 1.0 + min(instructional_mass / 50.0, 1.0)

                if folder not in instructional_multipliers or multiplier > instructional_multipliers.get(folder, 0.0):
                    instructional_multipliers[folder] = multiplier

        # Apply the multiplier to the existing doc_umbrellas
        for rel_path, meta in self.ram_cache.items():
            folder = str(Path(rel_path).parent).replace("\\", "/")
            if folder == ".":
                folder = "__root__"

            if "metadata" in meta and "doc_umbrella" in meta["metadata"]:
                base_shield = meta["metadata"]["doc_umbrella"]
                mult = instructional_multipliers.get(folder, 1.0)
                meta["metadata"]["doc_umbrella"] = min(base_shield * mult, 1.0)
        # ==============================================================

        for rel_path, meta in self.ram_cache.items():
            loc = meta.get("coding_loc", 0)
            total_loc += loc
            # Identify if the file lives in a test folder or is a test file
            if re.search(r"/tests?/|/testing/|\.test$", rel_path.lower()) or "test" in Path(rel_path).stem.lower():
                test_loc += loc

        # Calculate percentage of repo dedicated to testing
        umbrella_coverage = (test_loc / max(total_loc, 1)) * 100.0

        # Scale the bonus. Max out at 50.0 to clear the Sigmoid threshold for the whole project
        umbrella_bonus = min(umbrella_coverage * 2.0, 50.0)
        logger.info(
            f"UMBRELLA SHIELD: Repo test coverage is {umbrella_coverage:.1f}%. Applying +{umbrella_bonus:.1f} density bonus."
        )
        # -----------------------------------------------

        for rel_path, meta in self.ram_cache.items():
            # ---> NEW: INJECT THE FOLDER CONTEXT FOR THE SIGNAL PROCESSOR <---
            folder = str(Path(rel_path).parent)
            if "metadata" not in meta:
                meta["metadata"] = {}

            # Grab the winning language for this folder (defaulting to the file's own language)
            meta["metadata"]["folder_dominant_lang"] = folder_dominant_langs.get(folder, meta.get("lang_id", "unknown"))
            # -----------------------------------------------------------------

            # =================================================================
            # ---> THE CONTEXTUAL BASELINE FIX <---
            # If the file is imported by the ecosystem, its "orphans" are actually its API.
            # =================================================================
            popularity = self.popularity_scores.get(rel_path, 0)
            if popularity > 0 and "equations" in meta:
                orphans = meta["equations"].get("orphaned_logic", 0)
                if orphans > 0:
                    # 1. Convert the dead weight into API Exposure
                    meta["equations"]["api"] = meta["equations"].get("api", 0) + orphans
                    # 2. Wipe the Technical Debt
                    meta["equations"]["orphaned_logic"] = 0

                    # 3. Heal the function metadata
                    for func in meta.get("functions", []):
                        if func.get("usage_status") == 1:
                            func["usage_status"] = 0
            # =================================================================

            meta["temporal_telemetry"] = self.chronometer.get_file_history_metrics(rel_path)
            meta["authors"] = meta["temporal_telemetry"].get("authors", {})
            stem = Path(rel_path).stem.lower()

            # The Enterprise Bridge: Expanding sibling detection to catch Java/C# standards.
            # Because 'self.census' is global, this naturally bridges 'src/main' and 'src/test'
            # without writing brittle directory-parsing logic.
            test_patterns = self.config.get("TEST_NAMING_CONVENTIONS", [])
            sibling_candidates = [pattern.format(stem=stem) for pattern in test_patterns]
            meta["is_protected"] = any(cand in self.census for cand in sibling_candidates)

            # Pass the mapped test coverage data to the risk engine
            meta["test_coverage_map"] = test_coverage_map.get(rel_path, {})

            # The Analysis Engine natively handles the Exposed Secret and Documentation bypass protocols.
            # We unconditionally route to the Signal Processor so it can execute the 18-point math.
            forensic_result = self.processor.calculate_risk_vector(
                meta, meta.get("equations", {}), umbrella_bonus=umbrella_bonus
            )

            # =========================================================
            # THE BASELINE SHIELD: APPLY STRUCTURAL IMPACT DAMPENERS
            # SignalProcessor handles % Risks, but Orchestrator handles raw Mass.
            # =========================================================
            mass_modifiers = self.config.get("PATH_MODIFIERS", {}).get("Structural Mass", [])
            mass_multiplier = 1.0

            # Normalize path for safe cross-platform regex matching
            search_path = rel_path.replace("\\", "/")
            for mod_regex, mod_val in mass_modifiers:
                if mod_regex.search(search_path):
                    mass_multiplier = mod_val
                    break  # First match wins

            # Apply the dampener to the physical mass
            forensic_result["file_impact"] = round(forensic_result.get("file_impact", 0.0) * mass_multiplier, 2)
            # =========================================================

            # =========================================================
            # REPLACE YOUR EXISTING TELEMETRY BLOCK WITH THIS
            # =========================================================
            telemetry_payload = forensic_result.get("telemetry", {})
            ghost_meta = meta.get("metadata", {})

            # Legacy Telemetry
            telemetry_payload["control_flow_ratio"] = meta.get("control_flow_ratio", 0.0)
            telemetry_payload["popularity"] = self.popularity_scores.get(rel_path, 0)

            # THE FIX: Replace the brittle regex ownership with the dominant Git author
            if meta.get("authors"):
                # Get the name of the author with the most commits
                dominant_author = max(meta["authors"], key=meta["authors"].get)
                telemetry_payload["ownership"] = dominant_author
            else:
                # Fallback to the comment regex if Git is dormant or unavailable
                telemetry_payload["ownership"] = ghost_meta.get("ownership", "Unknown Architect")

            # THE FIX: Conditionally inject historical metadata into the domain_context
            # ONLY if the PROJECT_OVERRIDES regex successfully extracted it.
            if "purpose" in ghost_meta:
                if "domain_context" not in telemetry_payload:
                    telemetry_payload["domain_context"] = {}
                telemetry_payload["domain_context"]["purpose"] = ghost_meta["purpose"]

            # Phase 1 Bayesian Optics Traceability (SBOM compliance)
            telemetry_payload["roadmap_locked"] = meta.get("prior_lock", False)
            telemetry_payload["identity_lock_tier"] = meta.get("lock_tier", 4)
            telemetry_payload["identity_confidence"] = meta.get("intensity", 0.0)
            telemetry_payload["identity_source_proof"] = meta.get("source_proof", "Discovery")
            telemetry_payload["threat_snippets"] = meta.get("threat_snippets", {})

            self.parsed_files.append(
                {
                    **meta,
                    "name": Path(rel_path).name,
                    "risk_vector": forensic_result["risk_vector"],
                    "hit_vector": forensic_result["hit_vector"],
                    "file_impact": forensic_result["file_impact"],
                    "telemetry": telemetry_payload,
                }
            )

        # ==================================================================
        # CRITICAL LEAKS: Synthetic Node Generation
        # Extract files flagged as secret leaks from the unparsable queue
        # and forcefully inject them into the parsed map for visualization.
        # ==================================================================
        leaks = [cand for cand in self.unparsable_files if "CRITICAL LEAK" in cand.get("reason", "")]

        # Remove them from Excluded Artifacts so they aren't double-counted in the summary
        self.unparsable_files = [
            cand for cand in self.unparsable_files if "CRITICAL LEAK" not in cand.get("reason", "")
        ]

        from gitgalaxy.metrics.signal_processor import SignalProcessor

        for leak in leaks:
            rel_path = leak["path"]
            logger.critical(f"Threat Escalation: Forcing {rel_path} onto the 3D Map!")

            synthetic_artifact = {
                "name": Path(rel_path).name,
                "path": rel_path,
                "lang_id": "plaintext",  # <-- Bypasses the Spectral Auditor as Static Assets
                "coding_loc": 1,
                "total_loc": 1,
                "classification": "critical_secret_leak",
                # 18-point risk vector. Index 17 is secrets_risk. Peg it to 100%.
                "risk_vector": [0.0] * 13 + [0.0, 0.0, 0.0, 0.0, 100.0],
                "hit_vector": [0] * len(SignalProcessor.SIGNAL_SCHEMA),
                # ---> TOPOLOGY BASELINE <---
                # This makes the structural impact score massive and pushes all other files away
                "file_impact": 5000.0,
                "telemetry": {
                    "ownership": "Secrets Radar",
                    "domain_context": {"warning": "CRITICAL CREDENTIAL LEAK DETECTED"},
                    "identity_source_proof": "Aperture Security Override",
                    "identity_lock_tier": 0,
                },
            }

            if "sec_hardcoded_secrets" in SignalProcessor.SIGNAL_SCHEMA:
                idx = SignalProcessor.SIGNAL_SCHEMA.index("sec_hardcoded_secrets")
                synthetic_artifact["hit_vector"][idx] = 1

            self.parsed_files.append(synthetic_artifact)

        # ==================================================================
        # AI MODEL WEIGHTS: Binary Header Extraction
        # Extract large model binaries (.gguf, .safetensors) from the unparsable queue,
        # parse their metadata headers without loading them into RAM, and map them.
        # ==================================================================
        models = [cand for cand in self.unparsable_files if "AI MODEL WEIGHTS" in cand.get("reason", "")]

        self.unparsable_files = [
            cand for cand in self.unparsable_files if "AI MODEL WEIGHTS" not in cand.get("reason", "")
        ]

        if models:
            from gitgalaxy.metrics.tensor_scanner import TensorScanner

            tensor_scanner = TensorScanner(parent_logger=logger)

            for model in models:
                rel_path = model["path"]
                size_bytes = model.get("size_bytes", 0)
                full_path_str = str(self.root / rel_path)

                logger.info(f"🧠 TENSOR SCAN: Auditing local model weights for {rel_path}...")

                # Perform the zero-RAM binary header audit
                audit_results = tensor_scanner.audit_model(full_path_str)

                # Model weights are incredibly dense. We give them a massive file_impact.
                # 1 GB = ~100.0 impact points, capped at 10,000 to prevent breaking the 3D renderer.
                structural_impact_score = min((size_bytes / (1024 * 1024 * 1024)) * 100.0, 10000.0)

                synthetic_artifact = {
                    "name": Path(rel_path).name,
                    "path": rel_path,
                    "lang_id": "binary_threat",  # Forces it to render uniquely in the UI
                    "coding_loc": 1,
                    "total_loc": 1,
                    "classification": "ai_model_weights",
                    "risk_vector": [0.0] * len(SignalProcessor.RISK_SCHEMA),
                    "hit_vector": [0] * len(SignalProcessor.SIGNAL_SCHEMA),
                    "file_impact": max(structural_impact_score, 500.0),  # Minimum massive structural impact
                    "telemetry": {
                        "ownership": "Tensor Scanner",
                        "domain_context": {
                            "alert": "LOCAL MODEL WEIGHTS DETECTED",
                            "architecture": audit_results["architecture"],
                            "parameters": audit_results["parameters"],
                            "quantization": audit_results["quantization"],
                            "size_gb": f"{size_bytes / (1024**3):.2f} GB",
                        },
                        "identity_source_proof": "Tensor Scanner Header Extraction",
                        "identity_lock_tier": 0,
                    },
                }

                # Force the hit_vector to register as local compute so the AI Topology catches it
                if "llm_local_compute" in SignalProcessor.SIGNAL_SCHEMA:
                    idx = SignalProcessor.SIGNAL_SCHEMA.index("llm_local_compute")
                    synthetic_artifact["hit_vector"][idx] = 100  # Massive hit spike

                self.parsed_files.append(synthetic_artifact)

    def _prepare_target(self, target_input: Union[str, Path]) -> Path:
        """
        Validates the user's target input and constructs an ephemeral extraction environment if necessary.

        If the target is a compressed archive (.zip), this method generates a secure, isolated temporary
        directory in the host OS to unpack the contents. This ensures the engine can analyze
        cloud-downloaded repositories without permanently polluting the user's local file system.
        """
        input_path = Path(target_input)
        if not input_path.exists():
            raise InaccessibleArtifactError(f"Target missing: {target_input}")

        if input_path.suffix.lower() == ".zip":
            logger.info(f"ARCHIVE_DETECTED: Unpacking {input_path.name} to temporary lead shielding.")
            try:
                self.temp_dir = tempfile.mkdtemp(prefix="refraction_")
                with zipfile.ZipFile(input_path, "r") as zip_ref:
                    # DEVIOUS SHIELD: Zip Bomb Protection (Max 5GB expansion)
                    MAX_SAFE_BYTES = 5 * 1024 * 1024 * 1024 
                    total_uncompressed_size = sum(file_info.file_size for file_info in zip_ref.infolist())
                    
                    if total_uncompressed_size > MAX_SAFE_BYTES:
                        raise ValueError(f"Decompression bomb detected! Archive expands to {total_uncompressed_size} bytes.")
                        
                    zip_ref.extractall(self.temp_dir)
                return Path(self.temp_dir).resolve()
            except Exception as e:
                self.cleanup()
                raise InaccessibleArtifactError(f"Extraction failure: {e}")

        return input_path.resolve(strict=True)

    def cleanup(self):
        """
        Executes a mandatory garbage collection routine to securely purge any ephemeral environments.

        Called within the `finally` block of the main orchestration loop. This guarantees that even
        if the pipeline experiences a catastrophic Out-Of-Memory (OOM) crash or a Regex Timeout,
        the system will recursively delete the temporary extraction directories, preventing disk bloat.
        """
        if self.temp_dir and Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.warning(f"CLEANUP_FAILED: Could not remove {self.temp_dir} ({e})")

    def _record_anomaly(self, path: Union[str, Path], message: str):
        """Records failure telemetry."""
        name = Path(path).name
        logger.debug(f"ANOMALY: {name} | {message}")
        self.anomalies.append({"star": name, "diagnostic": message})

    def _summarize_anomalies(self, total_unparsable: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bridges isolated worker failures back to the main thread's forensic ledger.

        Instead of halting the entire pipeline when a single file triggers an OS permission error,
        a binary saturation threshold, or a regex timeout, this method captures the diagnostic
        string and appends it to the global anomalies array for the final Audit Recorder payload.
        """
        summary = {"size_limit": 0, "binary": 0, "unparsable": 0, "os_permissions": 0}
        unparsable_artifacts: List[str] = []

        # 1. Maintain the physical error tallies (I/O, Binary, OS)
        for a in self.anomalies:
            diag = a["diagnostic"].lower()

            if "massive" in diag or "size" in diag:
                summary["size_limit"] += 1
            elif "binary" in diag:
                summary["binary"] += 1
            elif "saturated" in diag or "syntax" in diag or "unparsable" in diag:
                summary["unparsable"] += 1
                # Grab the full file path and save it to our array
                unparsable_artifacts.append(a["star"])
            elif "permission" in diag or "os " in diag or "read error" in diag:
                summary["os_permissions"] += 1

        if unparsable_artifacts:
            summary["unparsable_artifacts"] = unparsable_artifacts

        # 2. Build the hierarchical composition_by_extension_and_reason
        composition = {}
        for unparsable in total_unparsable:
            path = unparsable.get("path", "")
            reason = unparsable.get("reason", "Unknown Reason")

            # Extract and normalize the extension using the engine's REGEX SHIELD
            ext = Path(path).suffix.lower()
            if not ext or len(ext) > 12 or not re.match(r"^\.[a-z0-9_\-+]+$", ext):
                ext = "no_extension"

            if ext not in composition:
                composition[ext] = {}
            if reason not in composition[ext]:
                composition[ext][reason] = 0

            composition[ext][reason] += 1

        # Sort extensions by total count, and reasons within them by count
        summary["composition_by_extension_and_reason"] = {
            ext: dict(sorted(reasons.items(), key=lambda x: x[1], reverse=True))
            for ext, reasons in sorted(composition.items(), key=lambda x: sum(x[1].values()), reverse=True)
        }

        return summary

    def _render_file_speed_chart(self):
        """Generates a terminal ASCII chart for macro file phases."""
        count = self.file_speed_telemetry["file_count"]
        if count == 0:
            return

        print("\n" + "=" * 75)
        print(" ⏱️  FILE SPEED (MACRO PHASE) TELEMETRY REPORT")
        print("=" * 75)
        print(f"\n [ CUMULATIVE TIME SPENT ACROSS {count} FILES ]")

        sorted_phases = sorted(
            self.file_speed_telemetry["phase_totals"].items(),
            key=lambda x: x[1],
            reverse=True,
        )
        max_time = sorted_phases[0][1] if sorted_phases else 1

        for phase, duration in sorted_phases:
            bar_len = int((duration / max_time) * 30)
            bar = "█" * bar_len
            avg_ms = (duration / max(count, 1)) * 1000
            print(f" {duration:.2f}s | {bar:<30} | {phase} (Avg: {avg_ms:.2f}ms/file)")

        print("=" * 75 + "\n")

    def _render_splicing_chart(self):
        """Generates a terminal ASCII chart for regex and file performance."""
        if not self.splicing_telemetry["top_slowest"]:
            return

        print("\n" + "=" * 75)
        print(" ⏱️  SPLICING SPEED TELEMETRY REPORT")
        print("=" * 75)

        print("\n [ TOP 10 SLOWEST FILES (Global Search) ]")

        # Ensure it's fully sorted before displaying
        sorted_files = sorted(
            self.splicing_telemetry["top_slowest"],
            key=lambda x: x["time"],
            reverse=True,
        )[:10]
        max_file_time = sorted_files[0]["time"] if sorted_files else 1

        for f in sorted_files:
            bar_len = int((f["time"] / max_file_time) * 30)
            bar = "█" * bar_len
            print(f" {f['time']:.3f}s | {bar:<30} | {f['path']}")

        sample_size = min(self.splicing_telemetry["files_sampled"], 5000)
        print(f"\n [ CUMULATIVE REGEX EXECUTION TIME (Sampled {sample_size} Files) ]")
        sorted_regex = sorted(
            self.splicing_telemetry["regex_totals"].items(),
            key=lambda x: x[1],
            reverse=True,
        )[:15]

        if sorted_regex:
            max_rx_time = sorted_regex[0][1]
            for name, duration in sorted_regex:
                bar_len = int((duration / max_rx_time) * 30)
                bar = "█" * bar_len
                print(f" {duration:.3f}s | {bar:<30} | {name}")
        else:
            print(" No regex telemetry collected.")

        print("=" * 75 + "\n")

    def _get_git_audit(self) -> Dict[str, str]:
        """
        Extracts forensic Git metadata (Commit SHA, Branch, Remote URL, Date) via subprocess.

        This metadata acts as the immutable anchor for the generated SHBOM (Structural Health
        Bill of Materials). It ensures that the resulting JSON/SQLite databases are cryptographically
        tied to a specific point in the repository's history for strict audit compliance.
        """
        audit = {
            "branch": "Unknown",
            "commit_hash": "Unknown",
            "remote_url": "Unknown",
            "latest_commit_date": "Unknown",
        }
        try:
            # 1. Commit Hash
            audit["commit_hash"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

            # 2. Branch Name
            audit["branch"] = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

            # 3. Remote URL (The true identity of the repo)
            try:
                audit["remote_url"] = subprocess.check_output(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=self.root,
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            except subprocess.CalledProcessError:
                audit["remote_url"] = "Local Only (No Remote)"

            # 4. Last Commit Date (When the repo was last updated/pulled)
            audit["latest_commit_date"] = subprocess.check_output(
                ["git", "log", "-1", "--format=%cd", "--date=iso-strict"],
                cwd=self.root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

        except (subprocess.CalledProcessError, FileNotFoundError):
            return {"status": "Not a Git repository (or Git not installed)"}

        return audit

    def execute_incremental_scan(
        self,
        ram_cache: Dict[str, Any],
        added: List[str],
        modified: List[str],
        deleted: List[str],
        db_output_path: str,
    ):
        """
        Executes a high-efficiency 'Continuous Delta' scan for CI/CD environments.

        Instead of re-scanning a 10,000-file repository for a 2-file PR, this method ingests
        the previous structural state from RAM/SQLite, evicts the deleted/modified files,
        and only runs the heavy regex optics on the newly added or changed files. It then
        triggers the 'Ripple Effect' to recalculate global Downstream Exposures and PageRank
        scores for the entire ecosystem before sealing the updated database.
        """
        start_time = time.time()
        logger.info(f"--- DELTA_IGNITION: {self.root.name} (v{self.version}) ---")

        try:
            # 1. Inject the surviving state
            self.ram_cache = ram_cache
            for d_file in deleted:
                if d_file in self.ram_cache:
                    del self.ram_cache[d_file]

            # 2. Rebuild the Census & Ext Tally from the surviving RAM
            self.census = set()
            self.ext_tally = {}
            self.stem_map = {}

            for rel_path in self.ram_cache.keys():
                stem = Path(rel_path).stem.lower()
                ext = Path(rel_path).suffix.lower()
                name = Path(rel_path).name.lower()
                self.census.add(stem)
                self.ext_tally[ext] = self.ext_tally.get(ext, 0) + 1
                self.ext_tally[name] = self.ext_tally.get(name, 0) + 1

            # 3. Target the New/Modified files for Pass 1 (Surgical Strike)
            for rel_path in added + modified:
                stem = Path(rel_path).stem.lower()
                ext = Path(rel_path).suffix.lower()
                name = Path(rel_path).name.lower()

                self.census.add(stem)
                self.ext_tally[ext] = self.ext_tally.get(ext, 0) + 1
                self.ext_tally[name] = self.ext_tally.get(name, 0) + 1
                self.stem_map[rel_path] = rel_path  # Instruct Pass 1 to ONLY process these

            # 4. Execute the Surgical Scan (Only parses new files)
            self._extract_features_parallel()

            # 5. The Ripple Effect (Recalculate Downstream Exposure for ALL files)
            self.stem_map = {f: f for f in self.ram_cache.keys()}
            self._resolve_dependency_graph()
            self._calculate_risk_exposures()

            # Re-map the directed graph because nodes/edges have mutated
            self.parsed_files, network_macro = self.network_sensor.build_dependency_graph(self.parsed_files)

            # 6. Audit Verification & ML Threat Inference
            repository_graph, unparsable_audits = self.auditor.audit(self.parsed_files)
            if repository_graph:
                repository_graph = self.model_auditor.audit_repository(repository_graph)

            # 7. Synthesis and Database Forging
            summary = self.processor.summarize_galaxy_metrics(repository_graph, unparsable_audits)
            summary["network_macro"] = network_macro
            session_meta = {
                "engine": f"GitGalaxy Scope v{self.version} (Delta Mode)",
                "target": self.root.name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(time.time() - start_time, 2),
                "target_directory": str(self.root.resolve()),
                "git_audit": self._get_git_audit(),  # Gets the NEW commit hash
                "missing_dependencies": {
                    "networkx": not HAS_NETWORKX,
                    "tiktoken": not HAS_TIKTOKEN,
                },
                "zero_dependency_mode": (not HAS_NETWORKX or not HAS_TIKTOKEN),
            }

            self.db_recorder.record_mission(
                parsed_files=repository_graph,
                unparsable_files=unparsable_audits,
                summary=summary,
                session_meta=session_meta,
                output_path=db_output_path,
            )

            logger.info(
                f"--- DELTA_SUCCESS: {len(repository_graph)} files mapped in {session_meta['duration_seconds']}s ---"
            )

        except Exception as e:
            logger.critical(f"FATAL_DELTA_COLLAPSE: {str(e)}", exc_info=True)
            raise
        finally:
            self.cleanup()


# ==============================================================================
# ORCHESTRATOR CORE: THE ENTRY POINT
# ==============================================================================


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("GalaxyScope v2")

    import argparse
    import copy
    import os  # <-- Added for the hard memory eviction
    from pathlib import Path

    # Required for safe execution limits with the multiprocessing pool on Windows
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="GitGalaxy GalaxyScope v2")
    parser.add_argument("target", help="Path to repo or ZIP")
    parser.add_argument("--output", default=None, help="Optional output filename override")
    parser.add_argument("--debug", action="store_true", help="Turn on verbose Analytical logging")
    parser.add_argument(
        "--paranoid",
        action="store_true",
        help="Lower security thresholds to flag more potential threats.",
    )

    # ---> NEW: THE SHADOW PATCH OVERRIDE <---
    parser.add_argument(
        "--shadow-patch-detected",
        action="store_true",
        help="Indicates the payload hash mutated without a version bump.",
    )

    # --- EXCLUSIVE RECORDER FLAGS ---
    parser.add_argument("--llm-only", action="store_true", help="Run ONLY the LLM recorder")
    parser.add_argument("--gpu-only", action="store_true", help="Run ONLY the GPU recorder")
    parser.add_argument("--audit-only", action="store_true", help="Run ONLY the Audit recorder")
    parser.add_argument("--db-only", action="store_true", help="Run ONLY the native SQLite recorder")
    parser.add_argument("--sarif-only", action="store_true", help="Run ONLY the SARIF exporter")
    parser.add_argument("--sbom-only", action="store_true", help="Run ONLY the CycloneDX SBOM generator")
    parser.add_argument("--fail-on-secrets", action="store_true", help="CI/CD Gate: Fail build if hardcoded secrets are detected")
    parser.add_argument("--fail-on-malware", action="store_true", help="CI/CD Gate: Fail build if ML threat inference flags malware")
    parser.add_argument("--max-risk-exposure", type=float, default=0.0, help="CI/CD Gate: Fail build if any file exceeds this risk percentage (0.0 to disable)")
    parser.add_argument("--incremental", type=str, metavar="DB_PATH", help="Path to baseline SQLite database for Delta Scanning")
    parser.add_argument("--config", type=str, help="Path to project-level configuration file (e.g., .galaxyscope.yaml)")
    parser.add_argument(
        "--splicing-speed",
        action="store_true",
        help="Profile regex and file processing speeds (capped at 5000 files)",
    )
    parser.add_argument(
        "--file-speed",
        action="store_true",
        help="Profile the macro lifecycle phases of file processing",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO

    # ---------------------------------------------------------
    # YAML Configuration File Interceptor
    # ---------------------------------------------------------
    config_file_data = {}
    if args.config and HAS_PYYAML:
        import yaml
        try:
            with open(args.config, 'r') as f:
                config_file_data = yaml.safe_load(f) or {}
            logging.info(f"⚙️ Loaded repository configuration from {args.config}")
        except Exception as e:
            logging.error(f"Failed to load config file {args.config}: {e}")
    
    # Map YAML configurations directly to argparse attributes if not overridden via CLI
    if 'galaxyscope' in config_file_data:
        for key, val in config_file_data['galaxyscope'].items():
            arg_key = key.replace('-', '_')
            if hasattr(args, arg_key) and getattr(args, arg_key) in (None, False, 0.0, ""):
                setattr(args, arg_key, val)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        stream=sys.stderr, # <--- THE FIX: Route logs to stderr so CI/CD catches them
        force=True,
    )

    logging.getLogger().setLevel(log_level)

    try:
        # ---------------------------------------------------------
        # 1. Target Identification
        # ---------------------------------------------------------
        # THE FIX: Resolve the path immediately so '.' becomes the actual folder name
        target_path = Path(args.target).resolve()
        project_name = target_path.name

        # ---> DEFAULT PROTOTYPING PATH <---
        # Hardcode your preferred testing directory here.
        # Leave as "" to default to your current terminal directory.
        DEFAULT_OUT_DIR = ""

        if args.output:
            out_arg = Path(args.output)
            # If it's an existing directory OR has no file extension, treat it as a target folder
            if out_arg.is_dir() or not out_arg.suffix:
                final_output = str(out_arg / f"{project_name}_galaxy.json")
            else:
                final_output = args.output
        else:
            if DEFAULT_OUT_DIR:
                final_output = str(Path(DEFAULT_OUT_DIR) / f"{project_name}_galaxy.json")
            else:
                final_output = f"{project_name}_galaxy.json"

        # ---------------------------------------------------------
        # 2. The Domain Dialect Pre-Flight Patch
        # ---------------------------------------------------------
        base_langs = LANGUAGE_DEFINITIONS
        project_overrides = PROJECT_OVERRIDES
        base_aperture = APERTURE_CONFIG

        merged_langs = copy.deepcopy(base_langs)
        merged_aperture = copy.deepcopy(base_aperture)

        if 'galaxyscope' in config_file_data and 'APERTURE_CONFIG' in config_file_data['galaxyscope']:
            yaml_aperture = config_file_data['galaxyscope']['APERTURE_CONFIG']
            
            if 'IGNORED_DIRECTORIES' in yaml_aperture:
                if "IGNORED_DIRECTORIES" not in merged_aperture:
                    merged_aperture["IGNORED_DIRECTORIES"] = set()
                merged_aperture["IGNORED_DIRECTORIES"].update(yaml_aperture['IGNORED_DIRECTORIES'])
            
            if 'CONTRABAND_PATTERNS' in yaml_aperture:
                if "CONTRABAND_PATTERNS" not in merged_aperture:
                    merged_aperture["CONTRABAND_PATTERNS"] = []
                merged_aperture["CONTRABAND_PATTERNS"].extend(yaml_aperture['CONTRABAND_PATTERNS'])

            if 'VENDOR_MINIFICATION_PATHS' in yaml_aperture:
                if "VENDOR_MINIFICATION_PATHS" not in merged_aperture:
                    merged_aperture["VENDOR_MINIFICATION_PATHS"] = []
                merged_aperture["VENDOR_MINIFICATION_PATHS"].extend(yaml_aperture['VENDOR_MINIFICATION_PATHS'])
                
            if 'SECRETS_EXACT' in yaml_aperture:
                if "SECRETS_EXACT" not in merged_aperture:
                    merged_aperture["SECRETS_EXACT"] = set()
                merged_aperture["SECRETS_EXACT"].update(yaml_aperture['SECRETS_EXACT'])

        if project_name in project_overrides:
            logging.info(f"🌌 DIALECT DETECTED: Injecting Project Overrides for '{project_name}'")
            dialect_dict = project_overrides[project_name]

            for lang, overrides in dialect_dict.items():
                if lang == "_shield_":
                    if "exclude_dirs" in overrides:
                        if "IGNORED_DIRECTORIES" not in merged_aperture:
                            merged_aperture["IGNORED_DIRECTORIES"] = set()
                        merged_aperture["IGNORED_DIRECTORIES"].update(overrides["exclude_dirs"])
                        logging.debug(
                            f"   -> Patched Aperture Shield (Added {len(overrides['exclude_dirs'])} Ignored Directories)."
                        )

                    if "exclude_paths" in overrides:
                        if "CONTRABAND_PATTERNS" not in merged_aperture:
                            merged_aperture["CONTRABAND_PATTERNS"] = []
                        merged_aperture["CONTRABAND_PATTERNS"].extend(overrides["exclude_paths"])
                        logging.debug(
                            f"   -> Patched Contraband Shield (Added {len(overrides['exclude_paths'])} exact paths)."
                        )
                    continue

                if lang in merged_langs:
                    if "extensions" in overrides:
                        merged_langs[lang]["extensions"] = overrides["extensions"]
                        logging.debug(f"   -> Patched '{lang}' extensions.")

                    rules_patch = {k: v for k, v in overrides.items() if k != "extensions"}
                    if rules_patch and "rules" in merged_langs[lang]:
                        merged_langs[lang]["rules"].update(rules_patch)
                        logging.debug(f"   -> Patched '{lang}' geometry rules.")

        # --- THE SMART THREAT SWITCH ---
        if args.paranoid:
            _active_policy = ThreatPolicy.get_policy("paranoid")
            logging.getLogger("GalaxyScope").info(
                "🔒 ZERO-TRUST MODE: Security Lens thresholds set to maximum sensitivity."
            )
        else:
            _active_policy = ThreatPolicy.get_policy("baseline")
        # -------------------------------

        # ---------------------------------------------------------
        # 3. Assemble the Final Configuration
        # ---------------------------------------------------------
        full_config = {
            "LANGUAGE_DEFINITIONS": merged_langs,
            "LEXICAL_FAMILY_HEURISTICS": LEXICAL_FAMILY_HEURISTICS,
            "APERTURE_CONFIG": merged_aperture,
            "PATH_MODIFIERS": PATH_MODIFIERS,
            "PRIORITY_WHITELIST": PRIORITY_WHITELIST,
            "TEST_NAMING_CONVENTIONS": TEST_NAMING_CONVENTIONS,
            "DOCUMENTATION_LANGUAGES": ASSET_MASKS.get("DOCUMENTATION_LANGUAGES", set()),
            "PARANOID_MODE": args.paranoid,
            "SHADOW_PATCH_DETECTED": args.shadow_patch_detected,
            "LLM_ONLY": args.llm_only,
            "GPU_ONLY": args.gpu_only,
            "AUDIT_ONLY": args.audit_only,
            "DB_ONLY": args.db_only,
            "SARIF_ONLY": args.sarif_only,
            "SBOM_ONLY": args.sbom_only,
            "FAIL_ON_SECRETS": args.fail_on_secrets,
            "FAIL_ON_MALWARE": args.fail_on_malware,
            "MAX_RISK_EXPOSURE": args.max_risk_exposure,
            "SPLICING_SPEED": args.splicing_speed,
            "FILE_SPEED": args.file_speed,
            "SARIF_IGNORED_RULES": config_file_data.get("galaxyscope", {}).get("SARIF_IGNORED_RULES", []),
            "SARIF_IGNORED_PATHS": config_file_data.get("galaxyscope", {}).get("SARIF_IGNORED_PATHS", []),
        }

        # ---------------------------------------------------------
        # 4. Ignite the Engine
        # ---------------------------------------------------------
        scope = Orchestrator(args.target, full_config)

        if args.incremental:
            from gitgalaxy.state_rehydrator import StateRehydrator
            logging.info(f"🔄 Delta Scan Requested: Attempting to rehydrate from {args.incremental}")
            
            db_out_path = str(Path(final_output).with_name(f"{Path(final_output).stem}_master.db"))
            rehydrator = StateRehydrator(args.incremental)
            baseline_state = rehydrator.load_latest_state(project_name)

            if baseline_state:
                baseline_commit = baseline_state["commit_hash"]
                ram_cache = baseline_state["ram_cache"]
                
                try:
                    import subprocess
                    diff_output = subprocess.check_output(
                        ["git", "diff", "--name-status", baseline_commit],
                        cwd=target_path,
                        text=True,
                        stderr=subprocess.DEVNULL
                    )
                    
                    added, modified, deleted = [], [], []
                    for line in diff_output.splitlines():
                        if not line.strip():
                            continue
                        
                        # DEVIOUS SHIELD: Split strictly by tabs, as filenames may contain spaces.
                        parts = line.split('\t')
                        status = parts[0]
                        
                        # Safely strip Git's quotation marks from spaced filenames
                        def _clean(p): return p.strip('"\n\r')
                        
                        if status.startswith('A'):
                            added.append(_clean(parts[1]))
                        elif status.startswith('M'):
                            modified.append(_clean(parts[1]))
                        elif status.startswith('D'):
                            deleted.append(_clean(parts[1]))
                        elif status.startswith('R') or status.startswith('C'):
                            # Git Outputs: R100 \t "old file.py" \t "new file.py"
                            deleted.append(_clean(parts[1]))
                            if len(parts) > 2:
                                added.append(_clean(parts[2]))
                    
                    logging.info(f"📊 Delta extraction: {len(added)} Added, {len(modified)} Modified, {len(deleted)} Deleted")
                    scope.execute_incremental_scan(ram_cache, added, modified, deleted, db_out_path)
                    
                except subprocess.CalledProcessError:
                    logging.warning(f"⚠️ Git diff failed against {baseline_commit}. Falling back to full scan.")
                    scope.execute_pipeline(final_output)
            else:
                logging.warning("⚠️ Rehydration failed. Falling back to full baseline scan.")
                scope.execute_pipeline(final_output)
        else:
            scope.execute_pipeline(final_output)

        # --- THE FIX: NATURAL RETURN FOR WRAPPERS ---
        if getattr(scope, "policy_failed", False):
            sys.exit(1)

    except Exception as e:
        logging.error(f"Critical failure during execution: {e}", exc_info=True)
        sys.exit(1)


# This tells Python to run main() if you call the file directly,
# but allows PyPI to map to main() dynamically.
if __name__ == "__main__":
    main()