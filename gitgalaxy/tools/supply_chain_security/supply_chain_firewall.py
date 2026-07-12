#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Supply Chain Firewall
#
# PURPOSE: 
# Zero-Trust Dependency Verification and Behavioral Policy Enforcement.
#
# ARCHITECTURAL DECISION:
# Operating as a RAM-Exclusive Logic Gate, this firewall consumes the Phase 1 
# Dependency Graph. By completely divesting from redundant O(N) disk parsing, 
# it achieves near-instant policy enforcement. It mitigates Namespace Hijacking 
# and Dependency Confusion attacks by comparing raw codebase imports against 
# resolved manifest aliases, while enforcing dynamic risk thresholds based on 
# build-time execution contexts and network topography.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import sys
import json
import logging
from pathlib import Path

# Import exclusively from the GitGalaxy Hub
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.analysis_lens import ThreatPolicy

# Safely import the config, falling back if the user hasn't configured exceptions yet
try:
    from gitgalaxy.standards.gitgalaxy_config import (
        ALLOWLIST_PATHS,
        STRICT_IMPORT_MODE,
        APPROVED_IMPORTS,
        BLACKLISTED_IMPORTS,
    )
except ImportError:
    ALLOWLIST_PATHS = []
    STRICT_IMPORT_MODE = False
    APPROVED_IMPORTS = []
    BLACKLISTED_IMPORTS = []


def run_firewall_audit(parsed_files: list, alias_map: dict = None) -> dict:
    """
    Programmatic entry point for GalaxyScope (Zero-Disk I/O).
    Operates exclusively on the pre-tokenized, anomaly-checked RAM graph from Phase 1.
    """
    security = SecurityLens(policy=ThreatPolicy.get_policy("paranoid"))
    logger = logging.getLogger("GalaxyScope.firewall")
    safe_alias_map = alias_map or {}

    imports_whitelisted = 0
    imports_blacklisted = 0
    imports_unknown = 0
    threats_found = 0
    threats_allowed = 0

    if not parsed_files:
        return {
            "imports_whitelisted": imports_whitelisted,
            "imports_unknown": imports_unknown,
            "imports_blacklisted": imports_blacklisted,
            "threats_found": threats_found,
            "threats_allowed": threats_allowed,
        }

    for file_node in parsed_files:
        rel_path_str = file_node.get("path", "unknown")
        is_whitelisted = any(approved in rel_path_str for approved in ALLOWLIST_PATHS)

        # =====================================================================
        # NEW: CONTEXTUAL ALIAS RESOLUTION
        # Traverse up the directory tree to find the nearest authoritative manifest
        # =====================================================================
        local_aliases = {}
        current_dir = Path(rel_path_str).parent
        
        while current_dir:
            dir_key = str(current_dir).replace("\\", "/")
            if dir_key in safe_alias_map:
                local_aliases = safe_alias_map[dir_key]
                break
                
            if str(current_dir) == ".":
                break
                
            current_dir = current_dir.parent

        # =====================================================================
        # 1. ZERO-TRUST IMPORT VERIFICATION
        # =====================================================================
        for imp in file_node.get("raw_imports", []):
            # JSON serializes Python tuples as lists, so we must check for both
            raw_pkg = imp[0] if isinstance(imp, (tuple, list)) else imp

            # DEFENSIVE DESIGN (RELATIVE PATH SHIELD):
            # Ignore native internal routing (e.g., './utils') to focus strictly 
            # on external supply chain dependencies.
            if raw_pkg.startswith("."):
                continue

            # DEFENSIVE DESIGN (DEEP-PATH TRUNCATOR):
            # Attackers often hide malicious payloads deep inside nested sub-modules.
            # Normalizing paths (e.g., 'lodash/nested/file' -> 'lodash') ensures 
            # policy rules evaluate the authoritative root package.
            if raw_pkg.startswith("@"):
                parts = raw_pkg.split("/")
                pkg = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else raw_pkg
            else:
                pkg = raw_pkg.split("/")[0]

            # DEFENSIVE DESIGN (IDENTITY TRANSLATION SHIELD):
            # Dereference manifest aliases to catch Dependency Confusion attacks 
            # where a malicious package masks itself behind a trusted internal alias.
            true_pkg = local_aliases.get(pkg, pkg)

            if true_pkg in BLACKLISTED_IMPORTS:
                imports_blacklisted += 1
                threats_found += 1
                # The Allowlist Loophole Fix: A blacklisted import is ALWAYS a threat. Never suppress it.
                if true_pkg != pkg:
                    logger.critical(f"🚨 [BLACKLISTED IMPORT] Spoofed alias blocked: '{pkg}' -> '{true_pkg}' in: {rel_path_str}")
                else:
                    logger.critical(f"🚨 [BLACKLISTED IMPORT] Unauthorized package '{pkg}' blocked in: {rel_path_str}")
            elif true_pkg in APPROVED_IMPORTS:
                imports_whitelisted += 1
            else:
                imports_unknown += 1
                if STRICT_IMPORT_MODE and not is_whitelisted:
                    threats_found += 1
                    if true_pkg != pkg:
                        logger.warning(
                            f"⚠️ [POLICY VIOLATION] Spoofed alias '{pkg}' -> '{true_pkg}' blocked by Strict Mode in: {rel_path_str}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ [POLICY VIOLATION] Unknown package '{pkg}' blocked by Strict Mode in: {rel_path_str}"
                        )

        # =====================================================================
        # 2. BEHAVIORAL POLICY ENFORCEMENT (Leveraging Phase 1 Measurements)
        # =====================================================================
        # Shield inert static assets (SVGs, Templates, XMLs) from executing behavioral heuristics
        safe_path_lower = rel_path_str.lower()
        ext = Path(rel_path_str).suffix.lower()
        
        # .d.ts files are TypeScript declarations. They contain no executable logic.
        if ext in {".svg", ".xml", ".jelly", ".html", ".css", ".md", ".json", ".yaml", ".yml", ".txt", ".properties"} or safe_path_lower.endswith(".d.ts"):
            continue

        # Shield test environments. Unit tests intentionally mock attacks, use hardcoded dummy data, 
        # and contain high-entropy strings which trigger massive false positives in behavioral heuristics.
        safe_path = rel_path_str.lower()
        if "/test/" in safe_path or "/tests/" in safe_path or "test_" in Path(safe_path).name or "_test" in Path(safe_path).name:
            continue

        # Extract the raw structural signatures calculated natively by the Structural Signature Analysis Engine in Phase 1
        equations = file_node.get("equations", {})
        loc = file_node.get("coding_loc", 1)

        # Clone the dictionary and strip the 'sec_' prefix for the security evaluator
        local_counts = {}
        for k, v in equations.items():
            clean_key = k[4:] if k.startswith("sec_") else k
            local_counts[clean_key] = v

        # DEFENSIVE DESIGN (BUILD-TIME EXECUTION MULTIPLIER):
        # Configuration scripts (like setup.py or package.json) are executed by CI/CD 
        # runners at build time. RCE here compromises the host before the app even runs.
        # We apply an artificial density multiplier to manifest triggers so any I/O or 
        # Danger signatures instantly trigger a blocking action from the firewall.
        build_time_multiplier = 1.0
        filename = Path(rel_path_str).name
        if filename in [
            "setup.py",
            "build.rs",
            "preinstall.js",
            "postinstall.js",
            "package.json",
        ]:
            build_time_multiplier = 10.0

        if build_time_multiplier > 1.0:
            for k in local_counts:
                if isinstance(local_counts[k], (int, float)):
                    local_counts[k] = int(local_counts[k] * build_time_multiplier)

        # Evaluate risk using Phase 1 network topography context (e.g., Downstream Exposure)
        network_metrics = file_node.get("dependency_network", {})
        exposures = security.evaluate_risk(local_counts, loc, network_metrics)

        if (
            "Hidden Malware Risk" in exposures
            or "Data Injection Risk" in exposures
            or "Secrets Leak Risk" in exposures
            or "Logic Bomb Risk" in exposures
            or "Memory Corruption Risk" in exposures
        ):
            if is_whitelisted:
                threats_allowed += 1
            else:
                logger.warning(f"🚨 [THREAT DETECTED] Density Threshold Breached in: {rel_path_str}")
                for risk, density in exposures.items():
                    capped_density = min(density * 100.0, 100.0)
                    logger.warning(f"   -> {risk}: {capped_density:.1f}%")
                threats_found += 1

    return {
        "imports_whitelisted": imports_whitelisted,
        "imports_unknown": imports_unknown,
        "imports_blacklisted": imports_blacklisted,
        "threats_found": threats_found,
        "threats_allowed": threats_allowed,
    }


def main():
    """
    Standalone Execution Mode.
    Because the firewall is decoupled from redundant O(N) disk parsing,
    it must be fed the compiled JSON Dependency Graph generated by the GalaxyScope orchestrator.
    """
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Supply Chain Firewall")

    parser = argparse.ArgumentParser(description="Supply Chain Firewall (RAM-Exclusive Mode)")
    parser.add_argument("target", help="Path to the compiled GalaxyScope RAM graph (e.g., results.json)")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target '{target_path}' does not exist.")
        sys.exit(1)

    print(f"🧱 Initializing Supply Chain Firewall against {target_path.name}...")

    parsed_files = []

    try:
        if target_path.is_dir():
            print("   -> Directory detected. Orchestrating GalaxyScope RAM graph generation...")
            import subprocess
            import tempfile
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Run the orchestrator to generate the JSON graph in a temp directory
                target_out_file = str(Path(tmpdir) / "firewall_temp.json")
                result = subprocess.run(
                    ["python", "-m", "gitgalaxy.galaxyscope", str(target_path), "--output", target_out_file],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    print(f"❌ GalaxyScope execution failed:\n{result.stderr}")
                    sys.exit(1)
                
                # Dynamically locate the generated audit file to avoid naming convention bugs
                tmp_path = Path(tmpdir)
                audit_files = list(tmp_path.glob("*_audit.json"))
                
                if not audit_files:
                    print("❌ GalaxyScope did not produce an audit JSON in the temp directory.")
                    print("\n--- 🕵️ ENGINE TELEMETRY & CRASH LOGS ---")
                    print(result.stderr)
                    print("------------------------------------------\n")
                    sys.exit(1)
                    
                with open(audit_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Extract files from the structured audit directory groups
                    parsed_files = []
                    groups = data.get("6. Parsed Files (Scanned Artifacts)", {})
                    for folder_data in groups.values():
                        for path, file_info in folder_data.get("Files", {}).items():
                            file_info["path"] = path # Ensure path remains attached
                            parsed_files.append(file_info)
        else:
            # Standard file-based load
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                parsed_files = []
                groups = data.get("6. Parsed Files (Scanned Artifacts)", {})
                for folder_data in groups.values():
                    for path, file_info in folder_data.get("Files", {}).items():
                        file_info["path"] = path
                        parsed_files.append(file_info)
                
    except Exception as e:
        print(f"❌ Failed to parse RAM graph: {e}")
        sys.exit(1)

    # In standalone CLI mode, we bypass the dynamic manifest parsing for speed,
    # relying purely on strict exact-match dependencies and behavioral structural signatures.
    results = run_firewall_audit(parsed_files, alias_map={})

    mode_str = "Strict (Exclude Blacklist and Unknown)" if STRICT_IMPORT_MODE else "Audit (Allow Whitelist + Unknown)"

    print("\n" + "=" * 75)
    print(" 🧱 SUPPLY CHAIN FIREWALL: SCAN SUMMARY")
    print("=" * 75)
    print(f" Mode                 : {mode_str}")
    print(f" Files Evaluated      : {len(parsed_files):,}")
    print("-" * 75)
    print(f" Approved Packages    : {results['imports_whitelisted']:,}")
    print(f" Banned Packages      : {results['imports_blacklisted']:,}")
    print(f" Unknown Packages     : {results['imports_unknown']:,}")
    print("-" * 75)
    print(f" Active Threats       : {results['threats_found']:,}")
    print(f" Allowlist Bypasses   : {results['threats_allowed']:,}")
    print("-" * 75)

    if results["threats_found"] > 0:
        print(f" [BLOCKING ACTION] {results['threats_found']} high-risk dependencies or policy violations blocked.")
        sys.exit(1)
    else:
        print(" [SUCCESS] Dependency supply chain is clean.")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()