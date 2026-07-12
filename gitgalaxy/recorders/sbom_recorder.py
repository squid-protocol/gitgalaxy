# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_io
# GitGalaxy Spoke: Universal Zero-Trust SBOM Generator
# Purpose: Generates a CycloneDX SBOM with physical verification of dependencies
#          across multiple language ecosystems (NPM, Composer, PyPI, Cargo).
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_io

# galaxyscope:ignore sec_high_risk_execution, ai_guardrails, sec_io

import os
import json
import uuid
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple, List, Any

# Import exclusively from the GitGalaxy Hub
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.analysis_lens import ThreatPolicy
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector


class UniversalManifestSlicer:
    """Uses regex and standard parsing to slice dependencies from any ecosystem."""

    @staticmethod
    def slice_manifest(manifest_path: Path) -> Tuple[str, Dict[str, str]]:
        filename = manifest_path.name
        deps = {}
        ecosystem = "unknown"

        try:
            if filename == "package.json":
                ecosystem = "npm"
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    deps.update(data.get("dependencies", {}))
                    deps.update(data.get("devDependencies", {}))

            elif filename == "composer.json":
                ecosystem = "packagist"  # PHP Composer
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    deps.update(data.get("require", {}))
                    deps.update(data.get("require-dev", {}))
                    # Remove the php version requirement
                    deps.pop("php", None)

            elif filename == "requirements.txt":
                ecosystem = "pypi"
                with open(manifest_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            clean_name = re.split(r"[=><~]", line)[0].strip()
                            # Get version if explicitly defined, else 'latest'
                            version = line.split("==")[1].strip() if "==" in line else "latest"
                            deps[clean_name] = version

            elif filename == "Cargo.toml":
                ecosystem = "cargo"
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Universal regex to grab [dependencies] blocks
                    dep_blocks = re.findall(r"\[(?:dev-)?dependencies\](.*?)(\n\[|$)", content, re.DOTALL)
                    for block, _ in dep_blocks:
                        for line in block.splitlines():
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                pkg_name = line.split("=")[0].strip()
                                deps[pkg_name] = "latest"  # Simplified version extraction

            elif filename == "go.mod":
                ecosystem = "golang"
                with open(manifest_path, "r", encoding="utf-8") as f:
                    in_require_block = False
                    for line in f:
                        line = line.strip()
                        if line.startswith("require ("):
                            in_require_block = True
                            continue
                        if line == ")":
                            in_require_block = False
                            continue
                        if in_require_block and line and not line.startswith("//"):
                            parts = line.split()
                            if len(parts) >= 2:
                                deps[parts[0]] = parts[1]
                        elif line.startswith("require ") and not in_require_block:
                            parts = line.split()
                            if len(parts) >= 3:
                                deps[parts[1]] = parts[2]

            elif filename == "Gemfile":
                ecosystem = "rubygems"
                with open(manifest_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Extract: gem 'nokogiri', '~> 1.11'
                        if line.startswith("gem "):
                            parts = line.split(",")
                            pkg_name = parts[0].replace("gem", "").strip(" '\"")
                            version = parts[1].strip(" '\"") if len(parts) > 1 else "latest"
                            deps[pkg_name] = version

            elif filename == "pom.xml":
                ecosystem = "maven"
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Extract artifactId and version from XML blocks
                    deps_raw = re.findall(
                        r"<dependency>.*?<artifactId>([^<]+)</artifactId>(?:.*?<version>([^<]+)</version>)?.*?</dependency>",
                        content,
                        re.DOTALL,
                    )
                    for artifact, version in deps_raw:
                        deps[artifact] = version if version else "latest"

        except Exception:
            pass

        return ecosystem, deps

    @staticmethod
    def locate_physical_package(target_path: Path, pkg_name: str, ecosystem: str) -> Path:
        """Hunts for the physical location of a package within the project bounds."""
        if ecosystem == "npm":
            target = target_path / "node_modules" / pkg_name
            return target if target.exists() else None

        elif ecosystem == "packagist":
            # Composer packages are in vendor/vendor-name/package-name
            target = target_path / "vendor" / pkg_name
            return target if target.exists() else None

        elif ecosystem == "pypi":
            # Hunt through common local virtual environment folders
            safe_pkg_name = pkg_name.replace("-", "_").lower()
            for venv_dir in ["venv", ".venv", "env"]:
                venv_path = target_path / venv_dir
                if venv_path.exists():
                    for root, dirs, _ in os.walk(venv_path):
                        if "site-packages" in root:
                            # Case-insensitive match for the package folder
                            for d in dirs:
                                if d.lower() == safe_pkg_name or d.lower().startswith(f"{safe_pkg_name}-"):
                                    return Path(root) / d

        elif ecosystem == "golang":
            # Go packages are often vendored in the project's root 'vendor/' directory
            target = target_path / "vendor" / pkg_name
            return target if target.exists() else None

        elif ecosystem == "rubygems":
            # Ruby often vendors gems locally here
            target = target_path / "vendor" / "bundle"
            if target.exists():
                for root, dirs, _ in os.walk(target):
                    if pkg_name in dirs:
                        return Path(root) / pkg_name
            return None

        elif ecosystem == "maven":
            # Java local dependency pulls usually land here
            target = target_path / "target" / "dependency"
            if target.exists():
                # Just verifying the jar/folder exists loosely
                for file in target.iterdir():
                    if pkg_name.lower() in file.name.lower():
                        return file
            return None

        return None


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
                    # Physical Audit (Max 5 core files to maintain velocity)
                    scanned_files = 0
                    for root, _, files in os.walk(pkg_path):
                        if scanned_files > 5:
                            break

                        for file in files:
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

                                scanned_files += 1
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