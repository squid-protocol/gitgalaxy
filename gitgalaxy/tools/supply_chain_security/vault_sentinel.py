#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Spoke: Secrets Scanner
# Purpose: High-speed pre-commit hook to detect hardcoded secrets.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import sys
import os
import time
import fnmatch
from pathlib import Path

# Import exclusively from the GitGalaxy Hub
from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.analysis_lens import ThreatPolicy
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# Safely import the config, falling back if the user hasn't added exceptions yet
try:
    from gitgalaxy.standards.gitgalaxy_config import (
        APERTURE_CONFIG,
        ALLOWLIST_PATHS,
        DENYLIST_PATTERNS,
    )
except ImportError:
    from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG

    ALLOWLIST_PATHS = []
    DENYLIST_PATTERNS = []


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Secrets Scanner")

    parser = argparse.ArgumentParser(description="Secrets Scanner: High-Speed Secrets Scanner")
    parser.add_argument("target", help="Directory or file to scan")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🛡️  Secrets Scanner engaging on {target_path.name}...")

    # Initialize lightweight filters
    filter_engine = ApertureFilter(target_path, LANGUAGE_DEFINITIONS, APERTURE_CONFIG)
    security = SecurityLens(policy=ThreatPolicy.get_policy("paranoid"))

    # SENSOR OPTIMIZATION: Only evaluate keys and dead-code logic for maximum performance
    security.THREAT_SIGNATURES = {
        "hardcoded_secrets": security.THREAT_SIGNATURES["hardcoded_secrets"],
        "dead_code": security.THREAT_SIGNATURES["dead_code"],
    }

    leaks_found = 0
    leaks_allowed = 0
    forbidden_blocked = 0
    files_evaluated = 0

    files_to_deep_scan = []

    # ==============================================================================
    # PHASE 1: Path Filtering & Surface Threat Detection
    # ==============================================================================
    for root, dirs, files in os.walk(target_path):
        rel_root = str(Path(root).relative_to(target_path))

        # Path Optimization: Evaluate top-level directories against ignore rules.
        if rel_root == ".":
            dirs[:] = [d for d in dirs if filter_engine._check_ignore_rules(d)]
        elif not filter_engine._check_ignore_rules(rel_root):
            dirs[:] = []
            continue

        for file in files:
            files_evaluated += 1
            file_path = Path(root) / file

            # Create a normalized string for checking against lists
            rel_path_str = str(file_path.relative_to(target_path)).replace("\\", "/")
            is_whitelisted = any(approved in rel_path_str for approved in ALLOWLIST_PATHS)

            # 1. DENYLIST ENFORCEMENT (Wildcard Pattern Matching)
            is_forbidden = any(fnmatch.fnmatch(file, pattern) for pattern in DENYLIST_PATTERNS)
            if is_forbidden and not is_whitelisted:
                print(f"[DENYLIST MATCH] Unauthorized file pattern detected: {rel_path_str}")
                forbidden_blocked += 1
                leaks_found += 1
                continue  # Skip deep scanning

            # 2. Tier 0 Path Scan (Catches .pem, id_rsa, .env immediately without I/O)
            is_valid, size, reason = filter_engine.evaluate_path_integrity(file_path)

            if reason and "CRITICAL LEAK" in reason:
                if is_whitelisted:
                    print(f"[ALLOWLIST BYPASS] Known safe test key ignored: {rel_path_str}")
                    leaks_allowed += 1
                else:
                    print(f"[PATH BREACH] Exposed Secret File: {rel_path_str}")
                    leaks_found += 1
                continue

            if is_valid:
                files_to_deep_scan.append((file_path, rel_path_str, is_whitelisted))

    # ==============================================================================
    # PHASE 2: Deep Content Inspection
    # ==============================================================================
    print(f"\n🔎 Scanning {len(files_to_deep_scan):,} files for internal contents of:")
    print("   - Cloud Infrastructure Keys")
    print("   - SaaS & CI/CD Tokens")
    print("   - Cryptographic Vaults")

    start_time = time.time()

    for file_path, rel_path_str, is_whitelisted in files_to_deep_scan:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            sec_results = security.scan_content(content, len(content.splitlines()))

            if sec_results["counts"].get("hardcoded_secrets", 0) > 0:
                if is_whitelisted:
                    print(f"[ALLOWLIST BYPASS] Known safe secret ignored in: {rel_path_str}")
                    leaks_allowed += 1
                else:
                    print(f"[CONTENT BREACH] Hardcoded Credential: {rel_path_str}")
                    secret_hits = len(sec_results["snippets"].get("hardcoded_secrets", []))
                    for _ in range(secret_hits):
                        # Never log any portion of a detected secret snippet.
                        print("   -> ********[REDACTED]********")
                    leaks_found += 1
        except Exception:
            pass

    end_time = time.time()
    time_delta = end_time - start_time
    scan_rate = len(files_to_deep_scan) / time_delta if time_delta > 0 else 0

    # ==============================================================================
    # SCAN SUMMARY
    # ==============================================================================
    print("\n" + "=" * 75)
    print(" 🛡️  VAULT SENTINEL: SCAN SUMMARY")
    print("=" * 75)
    print(f" Files Evaluated    : {files_evaluated:,}")
    print(f" Files Deep Scanned : {len(files_to_deep_scan):,}")
    print(f" Time Elapsed       : {time_delta:.2f} seconds")
    print(f" Scan Velocity      : {scan_rate:,.0f} files/sec")
    print("-" * 75)
    print(f" SECRETS DETECTED     : {leaks_found:,}")
    print(f" Denylist Blocks      : {forbidden_blocked:,}")
    print(f" Allowlist Bypasses   : {leaks_allowed:,}")
    print("-" * 75)

    if leaks_found > 0:
        print(f" [BLOCKING ACTION] {leaks_found} unauthorized secrets exposed. Failing pipeline.")
        print(" TIP: If this is a false positive, add the file path to ALLOWLIST_PATHS")
        print("         inside gitgalaxy/standards/gitgalaxy_config.py")
        sys.exit(1)
    else:
        print(" [SUCCESS] No unauthorized secrets detected.")
        if leaks_allowed > 0:
            print(f" NOTE: {leaks_allowed} known mock/safe files were bypassed via configuration.")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()