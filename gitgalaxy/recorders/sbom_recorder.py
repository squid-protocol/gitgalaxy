# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_io
# GitGalaxy Spoke: Universal Zero-Trust SBOM Generator
# Purpose: Generates a CycloneDX SBOM with physical verification of dependencies
#          across multiple language ecosystems (NPM, Composer, PyPI, Cargo).
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, ai_guardrails, sec_io

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import exclusively from the GitGalaxy Hub
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.analysis_lens import ThreatPolicy
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector

# UniversalManifestSlicer now lives in the canonical manifest module (PR A of
# the dependency-audit overhaul). Re-imported here so existing consumers and
# tests importing it from this module keep working unchanged.
from gitgalaxy.security.manifest_parser import UniversalManifestSlicer, SUPPORTED_MANIFEST_FILENAMES

class SbomRecorder:
    """
    Transforms the verified repository state into a CycloneDX SBOM manifest.
    Integrates the zero-trust physical audit to guarantee component integrity.
    """

    def __init__(
        self,
        version: str = "2.4.0",
        parent_logger: logging.Logger = None,
        dependency_cache=None,
        fresh_scan_budget: int = None,
    ):
        self.logger = parent_logger.getChild("sbom_recorder") if parent_logger else logging.getLogger("sbom_recorder")
        self.version = version
        # DependencyAuditCache instance, or None. None preserves the legacy
        # capped-sampling behavior exactly; wiring happens in galaxyscope (PR C).
        self.dependency_cache = dependency_cache
        # Max cache-MISS files freshly scanned per package per run (None =
        # unlimited). Hashing always covers every candidate file regardless;
        # budget-skipped files are disclosed in audit_coverage and picked up
        # on subsequent runs — incremental buildup, never silent omission.
        self.fresh_scan_budget = fresh_scan_budget

    def generate_report(
        self,
        parsed_files: List[Dict[str, Any]],
        summary: Dict[str, Any],
        session_meta: Dict[str, Any],
        output_path: str,
        manifest_paths: Optional[List[str]] = None,
    ) -> None:
        target_path = Path(session_meta.get("target_directory", "")).resolve()
        
        if not target_path.exists():
            self.logger.error(f"SBOM_FAILURE: Target directory {target_path} does not exist.")
            return

        self.logger.info(f"SBOM: Engaging Universal Zero-Trust Generation on {target_path.name}...")

        security = SecurityLens(policy=ThreatPolicy.get_policy("paranoid"))
        detector = LanguageDetector(LANGUAGE_DEFINITIONS, LEXICAL_FAMILY_HEURISTICS)
        slicer = UniversalManifestSlicer()

        components = []
        total_anomalies = 0
        total_missing = 0
        total_verified = 0

        # 1. Harvest Manifests Universally
        # Primary source: manifest_paths, built once in galaxyscope Phase 10
        # from the aperture-filtered Phase-0 census (self.stem_map) — the
        # earliest, most complete, and already vendor-dir-excluded file
        # inventory in the pipeline. This deliberately avoids re-deriving
        # manifest locations from parsed_files/repository_graph, which is
        # several lossy transformations downstream (Phase 6's spectral audit
        # can drop anomalous-looking files before they ever reach us here).
        if manifest_paths:
            manifests_found = [(Path(p), Path(p).parent) for p in manifest_paths]
        else:
            # Fallback for direct/standalone callers (e.g. unit tests) that
            # don't pass the Phase-10 list. Root-only, matching legacy
            # pre-census behavior.
            manifests_found = [
                (target_path / m, target_path)
                for m in self._MANIFEST_NAMES
                if (target_path / m).exists()
            ]

        if not manifests_found:
            self.logger.warning("SBOM: No supported manifests found. Outputting empty BOM.")

        # 2. The Zero-Trust Physical Audit
        for manifest, base_dir in manifests_found:
            ecosystem, packages = slicer.slice_manifest(manifest)
            if not packages:
                continue

            self.logger.debug(f"SBOM: Auditing {len(packages)} {ecosystem.upper()} dependencies from {manifest.name}...")

            for pkg_name, pkg_version in packages.items():
                trust_status = "VERIFIED_SAFE"
                anomaly_notes = []

                pkg_path = slicer.locate_physical_package(base_dir, pkg_name, ecosystem)

                coverage = "0/0 files (package not on disk)"
                if not pkg_path:
                    trust_status = "UNVERIFIED_MISSING_ON_DISK"
                    anomaly_notes.append("Package declared in manifest but not found locally.")
                    total_missing += 1
                    
                else:
                    if self.dependency_cache is not None:
                        trust_status, anomaly_notes, coverage = self._audit_with_cache(
                            pkg_path, pkg_name, ecosystem, security, detector
                        )
                    else:
                        trust_status, anomaly_notes, coverage = self._audit_capped_sample(
                            pkg_path, security, detector
                        )

                    if trust_status == "SPOOF_DETECTED":
                        total_anomalies += 1
                        self.logger.warning(f"🚨 [SPOOF DETECTED] {pkg_name}@{pkg_version}")
                    else:
                        total_verified += 1

                components.append(
                    {
                        "type": "library",
                        "name": pkg_name,
                        "version": pkg_version,
                        "purl": f"pkg:{ecosystem}/{pkg_name}@{pkg_version}",
                        "properties": [
                            {"name": "gitgalaxy:trust_status", "value": trust_status},
                            {
                                "name": "gitgalaxy:anomaly_notes",
                                "value": (" | ".join(anomaly_notes) if anomaly_notes else "None"),
                            },
                            {"name": "gitgalaxy:audit_coverage", "value": coverage},
                        ],
                    }
                )

        # 3. Dependency Mode Meta Flag
        is_zero_dep = session_meta.get("zero_dependency_mode", False)

        # 4. CycloneDX JSON Formatting
        bom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tools": [
                    {
                        "vendor": "GitGalaxy",
                        "name": "Universal Zero-Trust SBOM",
                        "version": f"v{self.version}",
                    }
                ],
                "component": {"type": "application", "name": target_path.name},
                "properties": [
                    {
                        "name": "gitgalaxy:zero_dependency_mode",
                        "value": str(is_zero_dep).lower()
                    }
                ]
            },
            "components": components,
        }

        if self.dependency_cache is not None:
            self.dependency_cache.commit()

        # Output the sealed manifest
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(bom, f, indent=4)

            self.logger.info(
                f"SBOM_SEALED: {len(components)} dependencies mapped -> {Path(output_path).resolve()}"
            )
            if total_anomalies > 0:
                self.logger.warning(f"SBOM_ALERT: {total_anomalies} dependencies failed physical structural verification.")
        except Exception as e:
            self.logger.error(f"SBOM_FAILURE: Could not export CycloneDX payload. {e}", exc_info=True)
    
    # Filenames that typically execute on import/install — the highest-value
    # audit targets, since real-world supply-chain payloads overwhelmingly
    # live in entry points rather than deep utility files.
    _ENTRY_POINT_STEMS = ("index", "main", "__init__", "app", "setup")

    def _iter_candidate_files(self, pkg_path: Path):
        """
        Yields every auditable code file in the package in RISK-PRIORITY order:
        entry-point-named files first, then shallower paths before deeper
        ones, then alphabetical. Under a fresh-scan budget this ensures the
        highest-impact files receive their first verdict on the earliest
        possible run, instead of whatever order os.walk happens to return
        (which an attacker choosing a late-sorting filename could exploit
        to defer their file's first inspection).
        """
        candidates = []
        for root, _, files in os.walk(pkg_path):
            for file in files:
                if file.endswith((".js", ".py", ".ts", ".php", ".rs")):
                    candidates.append(Path(root) / file)

        def _priority(p: Path):
            stem = p.stem.lower()
            is_entry = 0 if stem in self._ENTRY_POINT_STEMS else 1
            depth = len(p.relative_to(pkg_path).parts)
            return (is_entry, depth, str(p).lower())

        yield from sorted(candidates, key=_priority)

    def _scan_single_file(self, file_path: Path, security, detector):
        """Runs the security lens + language detector on one file.
        Returns (is_spoof, notes) or None if the file was unreadable."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(8192)
        except Exception as e:
            self.logger.debug(f"Skipped unreadable file during physical audit ({file_path}): {e}")
            return None

        notes = []
        is_spoof = False

        sec_results = security.scan_content(content, 100)
        if sec_results["counts"].get("entropy", 0) > 0:
            is_spoof = True
            notes.append(f"High Entropy (>4.8) in {file_path.name}")

        id_result = detector.inspect(file_path, content)
        if id_result["anomaly_flags"]:
            is_spoof = True
            notes.extend(id_result["anomaly_flags"])

        return is_spoof, notes

    def _audit_capped_sample(self, pkg_path: Path, security, detector):
        """
        LEGACY mode (no cache configured): per-directory capped sampling
        (#254). Coverage is honestly disclosed as partial.
        """
        trust_status = "VERIFIED_SAFE"
        anomaly_notes = []
        scanned = 0
        total_candidates = 0

        for root, _, files in os.walk(pkg_path):
            scanned_in_dir = 0
            for file in files:
                if not file.endswith((".js", ".py", ".ts", ".php", ".rs")):
                    continue
                total_candidates += 1
                if scanned_in_dir >= 5:
                    continue

                result = self._scan_single_file(Path(root) / file, security, detector)
                if result is None:
                    continue
                is_spoof, notes = result
                if is_spoof:
                    trust_status = "SPOOF_DETECTED"
                    anomaly_notes.extend(notes)
                scanned_in_dir += 1
                scanned += 1

        coverage = f"{scanned}/{total_candidates} files (capped sample; no dependency cache configured)"
        return trust_status, anomaly_notes, coverage

    def _audit_with_cache(self, pkg_path: Path, pkg_name: str, ecosystem: str, security, detector):
        """
        CACHED mode: every candidate file is hashed; verdicts are reused on
        hash hits and freshly computed on misses (up to fresh_scan_budget per
        package per run). Budget-skipped files are disclosed, not hidden —
        they accumulate into the cache on subsequent runs.
        """
        trust_status = "VERIFIED_SAFE"
        anomaly_notes = []
        cached_hits = 0
        fresh_scans = 0
        skipped_budget = 0
        unreadable = 0
        total_candidates = 0

        for file_path in self._iter_candidate_files(pkg_path):
            total_candidates += 1
            relpath = str(file_path.relative_to(pkg_path)).replace("\\", "/")

            content_hash = self.dependency_cache.hash_file(file_path)
            if content_hash is None:
                unreadable += 1
                continue

            cached = self.dependency_cache.lookup(ecosystem, pkg_name, relpath, content_hash)
            if cached is not None:
                cached_hits += 1
                if cached["trust_status"] == "SPOOF_DETECTED":
                    trust_status = "SPOOF_DETECTED"
                    if cached["anomaly_notes"]:
                        anomaly_notes.extend(cached["anomaly_notes"].split(" | "))
                continue

            if self.fresh_scan_budget is not None and fresh_scans >= self.fresh_scan_budget:
                skipped_budget += 1
                continue

            result = self._scan_single_file(file_path, security, detector)
            if result is None:
                unreadable += 1
                continue

            is_spoof, notes = result
            file_status = "SPOOF_DETECTED" if is_spoof else "VERIFIED_SAFE"
            if is_spoof:
                trust_status = "SPOOF_DETECTED"
                anomaly_notes.extend(notes)

            self.dependency_cache.record(
                ecosystem, pkg_name, relpath, content_hash, file_status, " | ".join(notes)
            )
            fresh_scans += 1

        verified = cached_hits + fresh_scans
        coverage = f"{verified}/{total_candidates} files ({cached_hits} cached, {fresh_scans} fresh"
        if skipped_budget:
            coverage += f", {skipped_budget} deferred to next run by scan budget"
        if unreadable:
            coverage += f", {unreadable} unreadable"
        coverage += ")"

        # A package with deferred files is not fully verified yet — reflect
        # that in the status rather than implying completeness (unless a
        # spoof was already found, which always dominates).
        if skipped_budget and trust_status == "VERIFIED_SAFE":
            trust_status = "PARTIALLY_VERIFIED"

        return trust_status, anomaly_notes, coverage
    
    # Single source of truth: manifest_parser.SUPPORTED_MANIFEST_FILENAMES.
    # Only used by the root-only fallback below when a caller doesn't pass
    # manifest_paths.
    _MANIFEST_NAMES = SUPPORTED_MANIFEST_FILENAMES

