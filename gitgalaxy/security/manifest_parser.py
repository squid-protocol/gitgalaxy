# ==============================================================================
# GitGalaxy - Manifest Parser
# Purpose: Parses ecosystem manifests and lockfiles to extract absolute dependency
#          resolutions, auditing for Supply Chain Substitution attacks, undocumented
#          VCS (Version Control System) references, and insecure registry routing.
# ==============================================================================
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Tuple


class ManifestParser:
    """
    Software Supply Chain Security (SSCS) Manifest Parser.

    Audits dependency definitions across ecosystems (NPM, PyPI) to build a deterministic
    resolution map. By comparing declared dependencies against their actual resolution URLs,
    this parser identifies namespace hijacking, package aliasing, and insecure registry routing.
    """

    def __init__(self, parent_logger=None):
        self.logger = (
            parent_logger.getChild("manifest_parser") if parent_logger else logging.getLogger("manifest_parser")
        )

        # Matches standard Python packages, extracting the base name and dropping version constraints (==, >=, ~)
        self.python_pkg_regex = re.compile(r"^([a-zA-Z0-9_\-]+)(?:[=><~].*)?$")

        # Matches direct URI references (git, file, http) that bypass PyPI registry verification
        self.python_direct_uri_regex = re.compile(r"^(?:git\+|file:|https?:|hg\+|svn\+|bzr\+)(.*)$")

    def build_resolution_map(self, manifest_paths: list) -> dict:
        """
        Accepts a list of exact file paths and builds a localized dependency resolution
        dictionary, namespaced by directory to prevent monorepo alias clobbering.
        """
        # Change to a nested structure: map[directory_path][package_alias]
        resolution_map = {}

        for path_str in manifest_paths:
            manifest_path = Path(path_str)
            if not manifest_path.exists():
                continue

            filename = manifest_path.name.lower()
            dir_key = str(manifest_path.parent).replace("\\", "/")
            
            # Initialize the namespace if it doesn't exist
            if dir_key not in resolution_map:
                resolution_map[dir_key] = {}

            # Point all parsers to the localized dictionary
            local_map = resolution_map[dir_key]

            try:
                if filename == "package.json":
                    self._parse_package_json(manifest_path, local_map)
                elif filename == "package-lock.json":
                    self._parse_package_lock(manifest_path, local_map)
                elif filename == "requirements.txt":
                    self._parse_requirements_txt(manifest_path, local_map)
                elif filename in ["pip.conf", ".pypirc", "pip.ini"]:
                    self._parse_pip_conf(manifest_path, local_map)
            except Exception as e:
                self.logger.warning(f"Manifest Parser: Failed to parse structural definition {filename} - {e}")

        return resolution_map

    def _parse_package_json(self, filepath: Path, resolution_map: dict):
        """
        Parses active NPM dependencies. Normalizes NPM aliases to their upstream package names
        and flags Direct URI resolutions that bypass Subresource Integrity (SRI) checks.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        for alias, version_string in all_deps.items():
            if not isinstance(version_string, str):
                continue

            # 1. NPM Package Aliasing (e.g., "my-alias": "npm:real-package@1.0")
            # We map the local alias to the true upstream package name for accurate vulnerability mapping.
            if version_string.startswith("npm:"):
                raw_pkg = version_string[4:]
                if raw_pkg.startswith("@"):
                    real_pkg = raw_pkg.rsplit("@", 1)[0] if "@" in raw_pkg[1:] else raw_pkg
                else:
                    real_pkg = raw_pkg.split("@")[0]
                resolution_map[alias] = real_pkg

            # 2. Direct URI Resolution (file:./local-lib, github:user/repo)
            # These dependencies are not fetched from the registry and lack cryptographic hash guarantees.
            elif version_string.startswith(("file:", "github:", "git+", "http")):
                resolution_map[alias] = version_string
                self.logger.warning(f"Manifest Parser: Flagged Direct URI resolution for '{alias}' -> {version_string}")

    def _parse_package_lock(self, filepath: Path, resolution_map: dict):
        """
        Extracts absolute resolution URLs from package-lock.json v2/v3.
        Neutralizes Namespace Hijacking by verifying internal packages point to the correct registry.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        packages = data.get("packages", {})
        for node_path, info in packages.items():
            if not node_path or "node_modules/" not in node_path:
                continue

            pkg_name = node_path.split("node_modules/")[-1]
            resolved_url = info.get("resolved", "")

            # DEFENSIVE GUARD: Registry Spoofing
            # If the resolved URL points to a non-standard domain or a direct Git link, map it
            # so the downstream firewall can flag it as an untrusted source.
            if resolved_url and not resolved_url.startswith("https://registry.npmjs.org/"):
                resolution_map[pkg_name] = resolved_url
                self.logger.info(
                    f"Manifest Parser: Flagged non-standard registry resolution for '{pkg_name}' -> {resolved_url}"
                )

    def _parse_requirements_txt(self, filepath: Path, resolution_map: dict):
        """
        Extracts direct Python packages and flags absolute VCS/URI references.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # 1. Check for Direct URI References (git+https://, file://)
                # These bypass PyPI and must be mapped exactly as written to trigger firewall rules.
                uri_match = self.python_direct_uri_regex.match(line)
                if uri_match:
                    resolution_map[line] = line
                    self.logger.warning(f"Manifest Parser: Flagged direct URI reference -> {line}")
                    continue

                # 2. Standard package capture
                match = self.python_pkg_regex.match(line)
                if match:
                    pkg_name = match.group(1)
                    # Initialize the package in the resolution map for downstream tracking
                    if pkg_name not in resolution_map:
                        resolution_map[pkg_name] = pkg_name

    def _parse_pip_conf(self, filepath: Path, resolution_map: dict):
        """
        Audits Python configuration files (pip.conf, .pypirc) for Dependency Confusion vulnerabilities
        caused by insecure protocol routing or untrusted secondary index URLs.
        """
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(("#", ";")):
                    continue

                # Look for custom registry routing definitions
                if "index-url" in line or "extra-index-url" in line or "repository" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        url = parts[1].strip()

                        # DEFENSIVE GUARD: Insecure Protocols & Tunneling
                        # HTTP connections allow Man-in-the-Middle (MitM) package injection.
                        # Tunneling services (ngrok) in production configs indicate severe architectural risk.
                        if url.startswith("http://") or "ngrok" in url or "localtunnel" in url:
                            self.logger.warning(f"🚨 Manifest Parser: INSECURE REGISTRY PROTOCOL DETECTED -> {url}")
                            # Prefix with INSECURE_REGISTRY so the Supply Chain Firewall can instantly block it
                            resolution_map[f"INSECURE_REGISTRY_{filepath.name}"] = url


# NEW:
# Filenames UniversalManifestSlicer.slice_manifest() below knows how to parse
# into an actual dependency list. This is the single source of truth for
# "what is a project dependency manifest" across the codebase -- both
# SbomRecorder (_MANIFEST_NAMES) and galaxyscope's Phase 10 discovery import
# this instead of maintaining their own copies. Keep this in sync with the
# filename checks inside slice_manifest() itself; they must never drift
# from each other either.
SUPPORTED_MANIFEST_FILENAMES = (
    "package.json", "composer.json", "requirements.txt",
    "Cargo.toml", "go.mod", "Gemfile", "pom.xml",
)


class UniversalManifestSlicer:
    """
    Uses regex and standard parsing to slice dependencies from any ecosystem.

    RELOCATED (PR A of the dependency-audit overhaul): this class previously
    lived in gitgalaxy.recorders.sbom_recorder, creating a second, parallel
    manifest parser alongside ManifestParser above. manifest_parser.py is now
    the single canonical module for "what does this project depend on, and
    where does it physically live on disk." sbom_recorder re-imports this
    class for backward compatibility.
    """

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

        except Exception as exc:
            logging.getLogger("manifest_parser").warning(
                "Failed to parse manifest '%s' (%s): %s",
                manifest_path,
                filename,
                exc,
                exc_info=exc,
            )

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
