# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_io, llm_hooks

import re
import os
import json
import logging
import fnmatch
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from gitgalaxy.standards.gitgalaxy_config import GUIDESTAR_CONFIG

# ==============================================================================
# GitGalaxy Phase 0.5: Sector Intelligence (The GuideStar Lens)
# Strategy: v6.3.0 (Deep Manifest Inspection & Evidence Hierarchy)
# ==============================================================================


class GuideStarLens:
    """
    The GuideStar Lens provides Contextual Baselines for files by parsing repository
    instructions and structural metadata.

    DEFENSIVE DESIGN: Before spinning up heavy regex engines or AST parsers,
    we scan standard project manifests (package.json, Makefiles, .gitattributes).
    If a file is explicitly defined as an entry point, we assign it an 'Intent Lock'.
    This guarantees accurate language detection and bypasses expensive inference checks.
    """

    # Fetch intelligence dictionaries directly from the configuration
    _gs_config = GUIDESTAR_CONFIG

    MANIFEST_MAP = _gs_config.get("MANIFEST_MAP", {})
    INTENT_BIASED_SECTORS = set(_gs_config.get("INTENT_BIASED_SECTORS", []))
    EXEC_PREFIX_MAP = _gs_config.get("EXEC_PREFIX_MAP", {})

    # Compiled regex for extracting target headers from README files
    README_TARGET_HEADERS = re.compile(
        r"^#+\s+(Usage|Structure|File|Layout|Getting\s+Started|Installation|Architecture|Scripts|CLI)",
        re.I | re.MULTILINE,
    )

    def __init__(
        self,
        root_path: Union[str, Path],
        priority_whitelist: Optional[List[str]] = None,
        parent_logger: Optional[logging.Logger] = None,
    ):
        """Initializes the Intelligence Engine and calibrates the lock maps."""
        if parent_logger:
            self.logger = parent_logger.getChild("guidestar")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("guidestar")
            self.logger.setLevel(logging.INFO)

        self.root = Path(root_path).resolve()
        self.whitelist = set(priority_whitelist or [])

        # Internal Lock Map: Dict[filename, {lang, confidence, proof}]
        self.intent_locks: Dict[str, Dict[str, Any]] = {}

        # Pattern Lock Map for .gitattributes (e.g., *.h)
        self.pattern_locks: Dict[str, Dict[str, Any]] = {}

        # Spatial Documentation Map: Dict[directory_path, coverage_strength_float]
        self.documentation_coverage: Dict[str, float] = {}

        self.logger.debug(f"GuideStar Lens Online | Sector: {self.root.name}")

    def scan_project_config(self):
        """
        Phase 0.5: Main orchestration method that dispatches scouts to scan
        manifests, configurations, and explicit directives.
        """
        self.logger.info("GuideStar: Scanning sectors for Contextual Baselines & Roadmap Proof...")

        # 1. Inspect package managers and build manifests
        self._scan_package_manifests()

        # 2. Inspect language overrides
        self._scan_gitattributes()

        # 3. Hunt for malicious evasion tactics
        self._scan_gitignore_evasion()

        # 4. Calculate documentation density
        self._calculate_documentation_coverage()

        self.logger.info(
            f"GuideStar: Scan complete. Cached {len(self.intent_locks)} intent locks, "
            f"{len(self.pattern_locks)} pattern rules, and {len(self.documentation_coverage)} documentation shields."
        )

    def get_intent_status(self, path: Union[str, Path]) -> Tuple[bool, Dict[str, Any]]:
        """Returns the specific Intent Lock for a given file path based on strict, pattern, or sector match."""
        path_obj = Path(path)
        filename = path_obj.name
        rel_path = str(path_obj.relative_to(self.root) if path_obj.is_absolute() else path_obj).replace("\\", "/")

        # 1. Check direct filename match (e.g., 'main.py')
        lock = self.intent_locks.get(filename)

        # 2. Check path-based match (e.g., 'src/index.js')
        if not lock:
            lock = self.intent_locks.get(rel_path)

        # 3. Check Pattern-based match from .gitattributes (e.g., '*.h')
        if not lock:
            for pattern, pat_lock in self.pattern_locks.items():
                # Test against both the raw filename and the relative path
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
                    lock = pat_lock
                    break

        # 4. Sector Bias: If the file lives in an intentional folder, it gets a base lock
        if not lock:
            parts = set(p.lower() for p in path_obj.parts)
            if parts.intersection(self.INTENT_BIASED_SECTORS):
                return True, {
                    "lang_id": "unknown",
                    "intensity": 0.75,
                    "source_proof": "Sector Bias",
                }

        if lock:
            return True, lock

        return False, {}

    def _inject_intent_lock(self, filename: str, lang: str, confidence: float, proof: str):
        """Safely updates the lock map with evidence-based intelligence."""
        if not filename:
            return

        # Clean the filename (remove leading dots or path separators)
        filename = filename.strip("./").strip()

        # If we already have a lock, we only update if the new proof is more authoritative
        existing = self.intent_locks.get(filename)
        if existing and existing["intensity"] >= confidence:
            return

        # Whitelist Trust Bonus
        if filename in self.whitelist:
            confidence = min(confidence + 0.1, 0.99)
            proof = f"{proof} + Whitelist Bonus"

        self.intent_locks[filename] = {
            "lang_id": lang,
            "intensity": round(confidence, 2),
            "source_proof": proof,
        }

    def _inject_pattern_lock(self, pattern: str, lang: str, confidence: float, proof: str):
        """Safely updates the pattern lock map with wildcard evidence."""
        if not pattern:
            return

        existing = self.pattern_locks.get(pattern)
        if existing and existing["intensity"] >= confidence:
            return

        self.pattern_locks[pattern] = {
            "lang_id": lang,
            "intensity": round(confidence, 2),
            "source_proof": proof,
        }

    # ==============================================================================
    # DEEP MANIFEST INSPECTION
    # ==============================================================================

    def _scan_package_manifests(self):
        """Identifies authoritative project contextual baselines and parses their internal logic."""
        # Dynamically inject requirements.txt if it wasn't in the global config
        active_manifests = dict(self.MANIFEST_MAP)
        if "requirements.txt" not in active_manifests:
            active_manifests["requirements.txt"] = "python"

        for manifest, lang in active_manifests.items():
            path = self.root / manifest
            if path.exists():
                # 1. Prioritize the manifest itself
                self._inject_intent_lock(manifest, lang, 0.90, "Roadmap Lock (Manifest)")

                # 2. Deep Inspection: Parse the manifest to find referenced files
                self._deep_inspect_manifest(path, manifest, lang)

    def _deep_inspect_manifest(self, path: Path, filename: str, lang: str):
        """Dispatches files to specific parsers based on their format."""
        try:
            # 1. Scan for AI/LLM footprints in the raw text first
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                self._detect_ai_ecosystem(f.read(), filename)

            # 2. Route to specific parsers for structural roadmaps
            if filename == "package.json":
                self._parse_package_json(path)
            elif filename == "Makefile" or filename.endswith(".mk"):
                self._parse_makefile(path)
            elif filename in ("pyproject.toml", "Cargo.toml", "requirements.txt"):
                self._parse_toml_style_manifest(path, lang)
        except Exception as e:
            self.logger.debug(f"GuideStar: Deep inspection failed for '{filename}': {e}")

    def _detect_ai_ecosystem(self, content: str, filename: str):
        """Scans manifest files for explicit AI/LLM orchestrators or tensor frameworks."""
        ai_keywords = {
            "langchain",
            "llama_index",
            "openai",
            "anthropic",
            "torch",
            "tensorflow",
            "transformers",
            "huggingface_hub",
            "vllm",
            "ollama",
            "chromadb",
            "pinecone",
        }

        found = [kw for kw in ai_keywords if kw in content.lower()]
        if found:
            self.logger.info(f"🧠 AI ECOSYSTEM DETECTED: Found {found} in {filename}. Flagging repository archetype.")
            # Inject a synthetic lock so the downstream pipeline knows this is an AI repo
            self._inject_intent_lock("__gitgalaxy_meta__.json", "json", 1.0, f"AI Ecosystem Lock ({found[0]})")

    def _parse_package_json(self, path: Path):
        """Extracts 'main', 'bin', and 'scripts' from Node/JS manifests."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Main Entry Point
                if "main" in data:
                    self._inject_intent_lock(data["main"], "javascript", 0.95, "Manifest Entry (package.json:main)")

                # Binary targets
                bins = data.get("bin", {})
                if isinstance(bins, str):
                    self._inject_intent_lock(bins, "javascript", 0.95, "Manifest Binary (package.json:bin)")
                elif isinstance(bins, dict):
                    for b_path in bins.values():
                        self._inject_intent_lock(b_path, "javascript", 0.95, "Manifest Binary (package.json:bin)")

                # Scripts (Finding secondary logic)
                scripts = data.get("scripts", {})
                for name, cmd in scripts.items():
                    files = re.findall(r"([a-zA-Z0-9_\-\./]+\.(?:js|ts|mjs|cjs))", cmd)
                    for f in files:
                        self._inject_intent_lock(
                            f, "javascript", 0.85, f"Manifest Script (package.json:scripts:{name})"
                        )
        except Exception:
            pass

    def _parse_makefile(self, path: Path):
        """Parses Makefiles to find source variables and targets."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

                # Strategy 1: Find variable assignments like SRCS = main.c ...
                matches = re.findall(r"(?:SRCS|SOURCES|FILES|TARGET)\s*[+:]?=\s*(.*)", content, re.I)
                for m in matches:
                    files = m.split()
                    for f in files:
                        if "." in f:
                            self._inject_intent_lock(f, "unknown", 0.85, "Manifest Source (Makefile)")

                # Strategy 2: Find target lines like 'build: main.o'
                targets = re.findall(r"^([a-zA-Z0-9_\-]+)\s*:", content, re.M)
                for t in targets:
                    if t not in ("all", "clean", "test", "install"):
                        self._inject_intent_lock(t, "unknown", 0.70, "Makefile Target")
        except Exception:
            pass

    def _parse_toml_style_manifest(self, path: Path, lang: str):
        """Simple regex-based TOML parser for script/entry points."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

                matches = re.findall(r'path\s*=\s*"(.*)"', content)
                matches += re.findall(r'=\s*"(.*):', content)  # Python entry points

                for m in matches:
                    if "/" in m or "." in m:
                        self._inject_intent_lock(m, lang, 0.95, f"Manifest Roadmap ({path.name})")
        except Exception:
            pass

    def _extract_execution_triggers(self, text: str):
        """Finds extensionless files used in command-line examples and infers exact language."""
        exec_matches = re.findall(
            r"(\.\/|python3?\s+|node\s+|sh\s+|bash\s+|cargo\s+run\s+|go\s+run\s+)([a-zA-Z0-9_\-\./]+)",
            text,
        )
        for prefix, filename in exec_matches:
            prefix_clean = prefix.strip().split()[0]
            predicted_lang = self.EXEC_PREFIX_MAP.get(prefix_clean, "unknown")

            if prefix.strip() == "./":
                predicted_lang = "unknown"

            self.logger.debug(f"GuideStar: Contextual hint found via execution trigger: '{filename}'")
            self._inject_intent_lock(filename, predicted_lang, 0.85, f"Execution Trigger ({prefix_clean})")

    # ==============================================================================
    # EXPLICIT AUTHORITY
    # ==============================================================================

    def _scan_gitattributes(self):
        """
        Parses .gitattributes for explicit linguist-language overrides.
        DEFENSIVE DESIGN: If an engineer specifically configured GitHub to treat
        a `.h` file as `objective-c`, we must honor that explicit intent to prevent
        the Language Lens from falsely identifying it as standard `cpp`.
        """
        gitattr_path = self.root / ".gitattributes"
        if not gitattr_path.exists():
            return

        lang_map = {
            "c++": "cpp",
            "c#": "csharp",
            "objective-c": "objective-c",
            "objective-c++": "objective-c",
            "javascript": "javascript",
            "typescript": "typescript",
        }

        try:
            with open(gitattr_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split()
                    if len(parts) < 2:
                        continue

                    pattern = parts[0]
                    for attr in parts[1:]:
                        if attr.startswith("linguist-language="):
                            raw_lang = attr.split("=", 1)[1].lower().strip("'\"")
                            engine_lang = lang_map.get(raw_lang, raw_lang)

                            self._inject_pattern_lock(
                                pattern,
                                engine_lang,
                                0.99,
                                f"Authoritative Override (.gitattributes: {attr})",
                            )
                            self.logger.debug(
                                f"GuideStar: Locked pattern '{pattern}' to '{engine_lang}' via .gitattributes"
                            )

        except Exception as e:
            self.logger.debug(f"GuideStar: Deep inspection failed for .gitattributes: {e}")

    # ==============================================================================
    # SECURITY EVASION DETECTION
    # ==============================================================================

    def _scan_gitignore_evasion(self):
        """
        Scans .gitignore for hostile force-includes (e.g., !payload.so).

        DEFENSIVE DESIGN: Attackers frequently use force-includes in .gitignore
        to bypass standard directory exclusions (like node_modules/) and force
        malicious compiled binaries to be tracked by the repository. We intercept
        these here and flag them for the X-Ray Binary Sensor.
        """
        gitignore_path = self.root / ".gitignore"
        if not gitignore_path.exists():
            return

        hostile_bins = {".so", ".dll", ".exe", ".dylib", ".bin", ".xz", ".gz", ".zip"}

        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    # We are only looking for Force-Includes
                    if line.startswith("!"):
                        ext = Path(line).suffix.lower()

                        if ext in hostile_bins:
                            clean_path = line[1:].strip("/")

                            self.logger.critical(
                                f"🚨 EVASION DETECTED: .gitignore is force-including a binary -> '{line}'"
                            )

                            self._inject_intent_lock(
                                clean_path,
                                "unknown",
                                1.0,
                                "Hostile Gitignore Force-Include",
                            )

        except Exception as e:
            self.logger.debug(f"GuideStar: Evasion inspection failed for .gitignore: {e}")

    # ==============================================================================
    # DOCUMENTATION COVERAGE MAP
    # ==============================================================================

    def _calculate_documentation_coverage(self):
        """
        Scans the repository for high-value architectural literature.

        PERFORMANCE OPTIMIZATION: Instead of opening and reading thousands of
        Markdown files to determine their value, we use `os.stat()` to fetch
        the physical byte size of the file. This is an extremely fast O(1) disk
        operation that allows us to build a topological map of documentation coverage, 
        making the assumption the larger doc files have more information in them.
        """
        anchor_patterns = {
            "README.md",
            "README.txt",
            "README.rst",
            "ARCHITECTURE.md",
            "DESIGN.md",
            "SPEC.md",
            "swagger.json",
            "openapi.yaml",
            "openapi.json",
            "CONTRIBUTING.md",
            "USAGE.md",
        }

        for root_dir, dirs, files in os.walk(self.root):
            dir_path = Path(root_dir)

            if any(part in self._gs_config.get("IGNORED_DIRECTORIES", set()) for part in dir_path.parts):
                continue

            local_shield_footprint = 0

            for file in files:
                if file in anchor_patterns or file.lower().endswith(".md"):
                    file_path = dir_path / file
                    try:
                        size_bytes = file_path.stat().st_size

                        # Ignore stubs (e.g., "# Project Title" and nothing else)
                        if size_bytes > 150:
                            local_shield_footprint += size_bytes
                    except OSError:
                        pass

            if local_shield_footprint > 0:
                # 3000+ bytes of documentation provides a 100% (1.0) shield for this folder.
                shield_strength = min(local_shield_footprint / 3000.0, 1.0)

                rel_dir = str(dir_path.relative_to(self.root)).replace("\\", "/")
                if rel_dir == ".":
                    rel_dir = "__root__"

                self.documentation_coverage[rel_dir] = round(shield_strength, 3)
                self.logger.debug(
                    f"GuideStar: Projected {shield_strength * 100:.1f}% Documentation Coverage over '{rel_dir}'"
                )
