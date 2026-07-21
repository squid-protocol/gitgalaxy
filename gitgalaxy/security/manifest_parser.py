# ==============================================================================
# GitGalaxy - Manifest Parser
# Purpose: Parses ecosystem manifests and lockfiles to extract absolute dependency
#          resolutions, auditing for Supply Chain Substitution attacks, undocumented
#          VCS (Version Control System) references, and insecure registry routing.
# ==============================================================================
import json
import logging
import re
from pathlib import Path


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
