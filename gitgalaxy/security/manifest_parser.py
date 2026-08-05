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
from typing import Optional


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
        resolution_map: dict[str, dict[str, str]] = {}

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
                elif filename == "pyproject.toml":
                    self._parse_pyproject_toml(manifest_path, local_map)
                elif filename == "yarn.lock":
                    self._parse_yarn_lock(manifest_path, local_map)
                elif filename in ("build.gradle", "build.gradle.kts"):
                    self._parse_gradle(manifest_path, local_map)
            except Exception as e:
                self.logger.warning(f"Manifest Parser: Failed to parse structural definition {filename} - {e}")

        return resolution_map

    def _parse_package_json(self, filepath: Path, resolution_map: dict):
        """
        Parses active NPM dependencies. Normalizes NPM aliases to their upstream package names
        and flags Direct URI resolutions that bypass Subresource Integrity (SRI) checks.
        """
        with open(filepath, encoding="utf-8") as f:
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
        with open(filepath, encoding="utf-8") as f:
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
        with open(filepath, encoding="utf-8") as f:
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
        with open(filepath, encoding="utf-8", errors="ignore") as f:
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

    def _parse_pyproject_toml(self, filepath: Path, resolution_map: dict):
        """
        Audits modern Python manifests (PEP 621 `[project] dependencies` arrays and
        Poetry's `[tool.poetry.dependencies]` table) for the same Direct URI bypass
        risk requirements.txt is already audited for.
        """
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # PEP 621: dependencies = ["requests>=2.0", "mypkg @ git+https://evil.com/x.git"]
        array_match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if array_match:
            for entry in re.findall(r'["\']([^"\']+)["\']', array_match.group(1)):
                if " @ " not in entry:
                    continue
                pkg_part, _, ref = entry.partition(" @ ")
                ref = ref.strip()
                if self.python_direct_uri_regex.match(ref):
                    pkg_name = re.split(r"[\[;\s]", pkg_part.strip())[0]
                    resolution_map[pkg_name] = ref
                    self.logger.warning(f"Manifest Parser: Flagged direct URI reference for '{pkg_name}' -> {ref}")

        # Poetry: requests = {git = "https://evil.com/x.git"} / {url = "..."}
        poetry_block = re.search(r"\[tool\.poetry\.dependencies\](.*?)(?=\n\[|\Z)", content, re.DOTALL)
        if poetry_block:
            for line in poetry_block.group(1).splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                pkg_name, _, value = line.partition("=")
                pkg_name = pkg_name.strip()
                if pkg_name.lower() == "python":
                    continue

                git_match = re.search(r'git\s*=\s*["\']([^"\']+)["\']', value)
                url_match = re.search(r'url\s*=\s*["\']([^"\']+)["\']', value)
                if git_match:
                    ref = f"git+{git_match.group(1)}"
                    resolution_map[pkg_name] = ref
                    self.logger.warning(f"Manifest Parser: Flagged direct git reference for '{pkg_name}' -> {ref}")
                elif url_match:
                    resolution_map[pkg_name] = url_match.group(1)
                    self.logger.warning(
                        f"Manifest Parser: Flagged direct URL reference for '{pkg_name}' -> {url_match.group(1)}"
                    )

    def _parse_yarn_lock(self, filepath: Path, resolution_map: dict):
        """
        Yarn's counterpart to _parse_package_lock: yarn.lock entries are separated by
        blank lines, each headed by one or more quoted/unquoted "name@range" specs
        followed by a `resolved "..."` URL. Flags resolutions outside Yarn's/npm's
        standard registries the same way package-lock.json resolutions are.
        """
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        for block in content.split("\n\n"):
            block = block.strip("\n")
            if not block or block.startswith("#"):
                continue

            header_match = re.match(r'^"?(@?[^@"\s]+)@', block)
            resolved_match = re.search(r'resolved\s+"([^"]+)"', block)
            if not header_match or not resolved_match:
                continue

            pkg_name = header_match.group(1)
            resolved_url = resolved_match.group(1)
            if not resolved_url.startswith(("https://registry.yarnpkg.com/", "https://registry.npmjs.org/")):
                resolution_map[pkg_name] = resolved_url
                self.logger.info(
                    f"Manifest Parser: Flagged non-standard registry resolution for '{pkg_name}' -> {resolved_url}"
                )

    def _parse_gradle(self, filepath: Path, resolution_map: dict):
        """
        Audits Gradle build scripts (Groovy or Kotlin DSL) for insecure `http://`
        repository declarations -- the Maven/Gradle equivalent of pip.conf's
        insecure index-url check.
        """
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        insecure_urls = re.findall(r'url\s*[=(]?\s*["\']?(http://[^"\'\s)]+)', content)
        for idx, url in enumerate(insecure_urls):
            self.logger.warning(f"🚨 Manifest Parser: INSECURE GRADLE REPOSITORY DETECTED -> {url}")
            key = f"INSECURE_REGISTRY_{filepath.name}" if idx == 0 else f"INSECURE_REGISTRY_{filepath.name}_{idx}"
            resolution_map[key] = url


# NEW:
# Filenames UniversalManifestSlicer.slice_manifest() below knows how to parse
# into an actual dependency list. This is the single source of truth for
# "what is a project dependency manifest" across the codebase -- both
# SbomRecorder (_MANIFEST_NAMES) and galaxyscope's Phase 10 discovery import
# this instead of maintaining their own copies. Keep this in sync with the
# filename checks inside slice_manifest() itself; they must never drift
# from each other either.
SUPPORTED_MANIFEST_FILENAMES = (
    "package.json",
    "composer.json",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "pom.xml",
    # Modern Python (issue #702)
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    # .NET / NuGet
    "packages.config",
    # C/C++
    "conanfile.txt",
    "vcpkg.json",
    # Java/Kotlin/Android (Gradle)
    "build.gradle",
    "build.gradle.kts",
    # Mobile (iOS/macOS)
    "Podfile",
    "Package.swift",
    # Dart/Flutter
    "pubspec.yaml",
    # JS/TS alternative lockfiles
    "yarn.lock",
    "pnpm-lock.yaml",
)

# Suffix-matched manifests, for filenames that vary per-project (e.g. a repo's
# .NET solution can have any number of arbitrarily-named *.csproj files). Kept
# separate from SUPPORTED_MANIFEST_FILENAMES, which is an exact-name set --
# callers that discover manifests via a filename lookup (galaxyscope's Phase
# 10 stem_map filter, SbomRecorder's standalone fallback) must check both.
SUPPORTED_MANIFEST_SUFFIXES = (".csproj",)


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
    def slice_manifest(manifest_path: Path) -> tuple[str, dict[str, str]]:
        filename = manifest_path.name
        deps = {}
        ecosystem = "unknown"

        try:
            if filename == "package.json":
                ecosystem = "npm"
                with open(manifest_path, encoding="utf-8") as f:
                    data = json.load(f)
                    deps.update(data.get("dependencies", {}))
                    deps.update(data.get("devDependencies", {}))

            elif filename == "composer.json":
                ecosystem = "packagist"  # PHP Composer
                with open(manifest_path, encoding="utf-8") as f:
                    data = json.load(f)
                    deps.update(data.get("require", {}))
                    deps.update(data.get("require-dev", {}))
                    # Remove the php version requirement
                    deps.pop("php", None)

            elif filename == "requirements.txt":
                ecosystem = "pypi"
                with open(manifest_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            clean_name = re.split(r"[=><~]", line)[0].strip()
                            # Get version if explicitly defined, else 'latest'
                            version = line.split("==")[1].strip() if "==" in line else "latest"
                            deps[clean_name] = version

            elif filename == "Cargo.toml":
                ecosystem = "cargo"
                with open(manifest_path, encoding="utf-8") as f:
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
                with open(manifest_path, encoding="utf-8") as f:
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
                with open(manifest_path, encoding="utf-8") as f:
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
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                    # Extract artifactId and version from XML blocks
                    deps_raw = re.findall(
                        r"<dependency>.*?<artifactId>([^<]+)</artifactId>(?:.*?<version>([^<]+)</version>)?.*?</dependency>",
                        content,
                        re.DOTALL,
                    )
                    for artifact, version in deps_raw:
                        deps[artifact] = version if version else "latest"

            elif filename == "pyproject.toml":
                ecosystem = "pypi"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                # PEP 621: [project] dependencies = ["requests>=2.0", ...]
                array_match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
                if array_match:
                    for entry in re.findall(r'["\']([^"\']+)["\']', array_match.group(1)):
                        name_match = re.match(r"^[A-Za-z0-9_.\-]+", entry.strip())
                        if name_match:
                            deps[name_match.group(0)] = "latest"  # Simplified version extraction
                # Poetry: [tool.poetry.dependencies]
                poetry_block = re.search(r"\[tool\.poetry\.dependencies\](.*?)(?=\n\[|\Z)", content, re.DOTALL)
                if poetry_block:
                    for line in poetry_block.group(1).splitlines():
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        pkg_name, _, value = line.partition("=")
                        pkg_name = pkg_name.strip()
                        if pkg_name.lower() == "python":
                            continue
                        version_match = re.search(r'"([^"]+)"', value)
                        deps[pkg_name] = version_match.group(1) if version_match else "latest"

            elif filename == "poetry.lock":
                ecosystem = "pypi"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                for block in re.findall(r"\[\[package\]\](.*?)(?=\n\[\[package\]\]|\Z)", content, re.DOTALL):
                    name_match = re.search(r'name\s*=\s*"([^"]+)"', block)
                    version_match = re.search(r'version\s*=\s*"([^"]+)"', block)
                    if name_match:
                        deps[name_match.group(1)] = version_match.group(1) if version_match else "latest"

            elif filename == "Pipfile":
                ecosystem = "pypi"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                for block in re.findall(r"\[(?:dev-)?packages\](.*?)(?=\n\[|\Z)", content, re.DOTALL):
                    for line in block.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            pkg_name, _, value = line.partition("=")
                            version_match = re.search(r'"([^"]+)"', value)
                            version = version_match.group(1) if version_match else "latest"
                            deps[pkg_name.strip()] = "latest" if version == "*" else version

            elif filename == "packages.config":
                ecosystem = "nuget"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                for pkg_id, version in re.findall(r'<package\s+id="([^"]+)"(?:\s+version="([^"]+)")?', content):
                    deps[pkg_id] = version if version else "latest"

            elif filename.endswith(".csproj"):
                ecosystem = "nuget"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                for pkg_id, version in re.findall(
                    r'<PackageReference\s+Include="([^"]+)"(?:\s+Version="([^"]+)")?', content
                ):
                    deps[pkg_id] = version if version else "latest"

            elif filename == "conanfile.txt":
                ecosystem = "conan"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                req_block = re.search(r"\[requires\](.*?)(?=\n\[|\Z)", content, re.DOTALL)
                if req_block:
                    for line in req_block.group(1).splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "/" in line:
                            pkg_name, _, version = line.partition("/")
                            deps[pkg_name.strip()] = version.strip() or "latest"

            elif filename == "vcpkg.json":
                ecosystem = "vcpkg"
                with open(manifest_path, encoding="utf-8") as f:
                    data = json.load(f)
                for dep in data.get("dependencies", []):
                    if isinstance(dep, str):
                        deps[dep] = "latest"
                    elif isinstance(dep, dict) and "name" in dep:
                        deps[dep["name"]] = "latest"

            elif filename in ("build.gradle", "build.gradle.kts"):
                ecosystem = "gradle"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                # Narrow to the dependencies { ... } block when present so unrelated
                # quoted strings elsewhere in the build script aren't misread as coordinates.
                dep_block = re.search(r"dependencies\s*\{(.*?)\n\}", content, re.DOTALL)
                search_space = dep_block.group(1) if dep_block else content
                for coord in re.findall(r"""['"]([\w.\-]+:[\w.\-]+:[\w.\-+]+)['"]""", search_space):
                    group_artifact, _, version = coord.rpartition(":")
                    deps[group_artifact] = version

            elif filename == "Podfile":
                ecosystem = "cocoapods"
                with open(manifest_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Extract: pod 'Alamofire', '~> 5.4'
                        if line.startswith("pod "):
                            parts = line[len("pod ") :].split(",")
                            pkg_name = parts[0].strip(" '\"")
                            version = parts[1].strip(" '\"") if len(parts) > 1 else "latest"
                            deps[pkg_name] = version

            elif filename == "Package.swift":
                ecosystem = "swiftpm"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                # Capture each .package(...) call's full argument list (tolerating one
                # level of nesting, e.g. `.upToNextMajor(from: "1.0.0")`) so `url:` and
                # `from:` can be located independently regardless of argument order.
                for call_args in re.findall(r"\.package\(((?:[^()]|\([^()]*\))*)\)", content):
                    url_match = re.search(r'url:\s*"([^"]+)"', call_args)
                    if not url_match:
                        continue
                    version_match = re.search(r'from:\s*"([^"]+)"', call_args)
                    pkg_name = url_match.group(1).rstrip("/").rsplit("/", 1)[-1]
                    if pkg_name.endswith(".git"):
                        pkg_name = pkg_name[:-4]
                    deps[pkg_name] = version_match.group(1) if version_match else "latest"

            elif filename == "pubspec.yaml":
                ecosystem = "pub"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                dep_block = re.search(r"^dependencies:\n((?:[ \t]+.*\n?)*)", content, re.MULTILINE)
                if dep_block:
                    for line in dep_block.group(1).splitlines():
                        entry_match = re.match(r"^  ([A-Za-z0-9_]+):\s*(.*)$", line)
                        if entry_match:
                            pkg_name, version = entry_match.group(1), entry_match.group(2).strip()
                            deps[pkg_name] = version if version and not version.startswith("{") else "latest"

            elif filename == "yarn.lock":
                ecosystem = "npm"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                for block in content.split("\n\n"):
                    block = block.strip("\n")
                    header_match = re.match(r'^"?(@?[^@"\s]+)@', block)
                    version_match = re.search(r'version\s+"([^"]+)"', block)
                    if header_match and version_match:
                        deps[header_match.group(1)] = version_match.group(1)

            elif filename == "pnpm-lock.yaml":
                ecosystem = "npm"
                with open(manifest_path, encoding="utf-8") as f:
                    content = f.read()
                # pnpm lockfile v6+: top-level `dependencies:`/`devDependencies:` blocks,
                # each entry `  pkg-name:\n    version: 1.2.3` (a `specifier:` sibling
                # line, ignored here, carries the declared range instead of the resolution).
                for section in re.findall(
                    r"^(?:dependencies|devDependencies):\n((?:[ \t]+.*\n?)*)", content, re.MULTILINE
                ):
                    current_pkg = None
                    for line in section.splitlines():
                        pkg_match = re.match(r"^  (\S+):\s*$", line)
                        version_match = re.match(r"^\s+version:\s*([^\s(]+)", line)
                        if pkg_match:
                            current_pkg = pkg_match.group(1)
                        elif version_match and current_pkg:
                            deps[current_pkg] = version_match.group(1)
                            current_pkg = None

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
    def locate_physical_package(
        target_path: Path, pkg_name: str, ecosystem: str, repo_root: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Hunts for the physical location of a package within the project bounds.

        repo_root (optional): the actual repository root, separate from
        target_path (the manifest's own directory). When provided, an npm
        lookup that misses at target_path falls back to walking upward
        toward repo_root, checking node_modules at each intermediate level --
        npm/yarn/pnpm workspaces commonly hoist shared dependencies to the
        workspace root instead of duplicating them into every sub-package's
        own node_modules. The walk stops at repo_root rather than the
        filesystem root, so an unrelated node_modules higher up the machine
        can't produce a false match. Backward compatible: callers that don't
        pass repo_root get the old, non-hoisting-aware behavior unchanged.
        """
        if ecosystem == "npm":
            target = target_path / "node_modules" / pkg_name
            if target.exists():
                return target

            # Hoisting fallback: walk upward from the manifest's own
            # directory toward repo_root, checking node_modules at each
            # intermediate level, without ever going above repo_root.
            if repo_root is not None:
                try:
                    current = target_path.resolve()
                    boundary = repo_root.resolve()
                except OSError:
                    return None
                while current != boundary and boundary in current.parents:
                    current = current.parent
                    hoisted = current / "node_modules" / pkg_name
                    if hoisted.exists():
                        return hoisted
            return None

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

        elif ecosystem == "nuget":
            # Modern SDK-style projects restore into project-local `packages/`
            # or the global per-user cache; check both, local first.
            local = target_path / "packages" / pkg_name
            if local.exists():
                return local
            global_cache = Path.home() / ".nuget" / "packages" / pkg_name.lower()
            return global_cache if global_cache.exists() else None

        elif ecosystem == "conan":
            # Conan 2.x's local cache keys packages by name/version/revision;
            # loosely matched since the exact revision hash varies per build.
            cache_root = Path.home() / ".conan2" / "p"
            if cache_root.exists():
                for entry in cache_root.iterdir():
                    if entry.name.lower().startswith(pkg_name.lower()):
                        return entry
            return None

        elif ecosystem == "vcpkg":
            # vcpkg installs into a project-local triplet-scoped tree.
            target = target_path / "vcpkg_installed"
            if target.exists():
                for root, dirs, _ in os.walk(target):
                    if pkg_name in dirs:
                        return Path(root) / pkg_name
            return None

        elif ecosystem == "gradle":
            # Gradle's per-user module cache, keyed by group:artifact:version.
            cache_root = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
            if cache_root.exists():
                artifact = pkg_name.rsplit(":", 1)[-1]
                for root, dirs, _ in os.walk(cache_root):
                    if artifact in dirs:
                        return Path(root) / artifact
            return None

        elif ecosystem == "cocoapods":
            target = target_path / "Pods" / pkg_name
            return target if target.exists() else None

        elif ecosystem == "swiftpm":
            for build_dir in (".build/checkouts", ".swiftpm/checkouts"):
                target = target_path / build_dir / pkg_name
                if target.exists():
                    return target
            return None

        elif ecosystem == "pub":
            # pub's global per-user hosted-package cache, versioned in the dirname.
            cache_root = Path.home() / ".pub-cache" / "hosted" / "pub.dev"
            if cache_root.exists():
                for entry in cache_root.iterdir():
                    if entry.name.startswith(f"{pkg_name}-"):
                        return entry
            return None

        return None
