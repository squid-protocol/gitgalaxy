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
from typing import Dict, List, Any

# Import exclusively from the GitGalaxy Hub
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.analysis_lens import ThreatPolicy
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector

# UniversalManifestSlicer now lives in the canonical manifest module (PR A of
# the dependency-audit overhaul). Re-imported here so existing consumers and
# tests importing it from this module keep working unchanged.
from gitgalaxy.security.manifest_parser import UniversalManifestSlicer


class SbomRecorder:
    """
    Transforms the verified repository state into a CycloneDX SBOM manifest.
    Integrates the zero-trust physical audit to guarantee component integrity.
    """

    def __init__(self, version: str = "2.4.0", parent_logger: logging.Logger = None):
        self.logger = parent_logger.getChild("sbom_recorder") if parent_logger else logging.getLogger("sbom_recorder")
        self.version = version

    def generate_report(
        self,
        parsed_files: List[Dict[str, Any]],
        summary: Dict[str, Any],
        session_meta: Dict[str, Any],
        output_path: str,
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
        manifest_targets = [
            "package.json",
            "composer.json",
            "requirements.txt",
            "Cargo.toml",
            "go.mod",
            "Gemfile",
            "pom.xml",
        ]
        found_manifests = [target_path / m for m in manifest_targets if (target_path / m).exists()]

        if not found_manifests:
            self.logger.warning("SBOM: No supported manifests found in the root directory. Outputting empty BOM.")

        # 2. The Zero-Trust Physical Audit
        for manifest in found_manifests:
            ecosystem, packages = slicer.slice_manifest(manifest)
            if not packages:
                continue

            self.logger.debug(f"SBOM: Auditing {len(packages)} {ecosystem.upper()} dependencies from {manifest.name}...")

            for pkg_name, pkg_version in packages.items():
                trust_status = "VERIFIED_SAFE"
                anomaly_notes = []

                pkg_path = slicer.locate_physical_package(target_path, pkg_name, ecosystem)

                if not pkg_path:
                    trust_status = "UNVERIFIED_MISSING_ON_DISK"
                    anomaly_notes.append("Package declared in manifest but not found locally.")
                    total_missing += 1
                else:
                    # Physical Audit (Max 5 core files PER DIRECTORY to
                    # maintain velocity). The cap is reset on every directory
                    # os.walk visits, and enforced per-file (not once per
                    # directory) so a single bloated folder can't consume the
                    # whole package's audit budget and starve every other
                    # directory from being sampled at all (#254).
                    for root, _, files in os.walk(pkg_path):
                        scanned_in_dir = 0
                        for file in files:
                            if scanned_in_dir >= 5:
                                break

                            if not file.endswith((".js", ".py", ".ts", ".php", ".rs")):
                                continue

                            file_path = Path(root) / file
                            try:
                                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    content = f.read(8192)

                                sec_results = security.scan_content(content, 100)
                                if sec_results["counts"].get("entropy", 0) > 0:
                                    trust_status = "SPOOF_DETECTED"
                                    anomaly_notes.append(f"High Entropy (>4.8) in {file}")

                                id_result = detector.inspect(file_path, content)
                                if id_result["anomaly_flags"]:
                                    trust_status = "SPOOF_DETECTED"
                                    anomaly_notes.extend(id_result["anomaly_flags"])

                                scanned_in_dir += 1
                            except Exception as e:
                                self.logger.debug(f"Skipped unreadable file during physical audit ({file_path}): {e}")
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