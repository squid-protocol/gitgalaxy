#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Binary Anomaly Detector
#
# PURPOSE:
# Performs high-speed triage of binary anomalies, magic byte mismatches, and
# obfuscated payloads within the CI/CD pipeline.
#
# ARCHITECTURAL DECISION:
# Traditional SAST tools struggle with binaries, either ignoring them completely
# (allowing steganography/hidden malware) or attempting to parse them, causing
# pipeline timeouts. This module acts as a lightweight heuristic gatekeeper,
# relying on mathematical entropy and header verification to detect malicious
# packing without requiring deep binary execution.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import fnmatch
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

# Import exclusively from the GitGalaxy Hub
from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.config_resolver import ResolvedConfig, path_allowlisted, resolve_config
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

MAX_DENSE_SCAN_BYTES = 5_000_000
ENCODED_RUN = re.compile(rb"[A-Za-z0-9+/_-]{256,}={0,2}")  # a long unbroken encoded run: no backtracking in one class
DENSE_RUN_ENTROPY = 5.0  # base64 of random data reads about 5.9; identifiers and hex stay under 4.5


def _scan_head(security: SecurityLens, head: bytes, ext: str) -> dict:
    """scan_binary, with `MZ` counted only where a Windows executable has it: the first two bytes. Anywhere in 8 KB, those
    two letters flag ordinary text, and a dense payload could be caught by chance rather than by a real check (#7187)."""
    return security.scan_binary(head if head.startswith(b"MZ") else head.replace(b"MZ", b"Mz"), ext)


def _dense_run(path: Path, head: bytes) -> bool:
    """A long encoded run anywhere in a text file. SecurityLens empties lines of 250+ characters and this tool reads 8 KB
    of each file, so without this a large payload on one line, or past 8 KB, is never measured (#7187)."""
    if b"\0" in head or path.stat().st_size > MAX_DENSE_SCAN_BYTES:
        return False
    raw = path.read_bytes()
    for match in ENCODED_RUN.finditer(raw):
        if raw[max(0, match.start() - 7) : match.start()] == b"base64,":
            continue  # a declared data: URI. An embedded icon is ordinary CSS and HTML, not a hidden payload
        sample = match.group(0)[:4096]
        entropy = -sum(n / len(sample) * math.log2(n / len(sample)) for n in Counter(sample).values())
        if entropy > DENSE_RUN_ENTROPY:
            return True
    return False


def _in_test_folder(rel_path: str) -> bool:
    """Tests carry high-entropy mock data. Whole path segments: "phpunit" as a substring also exempted phpunit_helper.py."""
    return path_allowlisted(rel_path.lower(), ("test/", "tests/", "phpunit/"))


def _binary_threat(threats: dict, dense_is_expected: bool) -> bool:
    """Whether scan_binary's result counts. XRAY_BYPASS_EXTENSIONS says dense data is normal in this file type, which
    excuses its entropy and any short header that random bytes happen to contain. It never excuses a file that doesn't
    start the way its type must: an executable named logo.png is the mismatch this tool exists to catch (#7155)."""
    return bool(threats.get("sec_extension_mismatch")) if dense_is_expected else bool(threats)


def main():
    import logging

    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Binary Anomaly Detector")

    parser = argparse.ArgumentParser(description="Binary Anomaly Detector: Entropy & Magic Byte Scanner")
    parser.add_argument("target", help="Directory to scan")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to project-level configuration file (e.g., .galaxyscope.yaml) -- "
        "same resolver galaxyscope.py uses, so standalone runs honor the same "
        "ALLOWLIST_PATHS / DENYLIST_PATTERNS / XRAY_BYPASS_* overrides (#335).",
    )
    args = parser.parse_args()

    # #335: was a direct module-level gitgalaxy_config.py import, which meant
    # no YAML/CLI override (#332) could ever reach this standalone detector.
    resolved_config = resolve_config(yaml_path=args.config)
    allowlist_paths = resolved_config.get("ALLOWLIST_PATHS", [])
    denylist_patterns = resolved_config.get("DENYLIST_PATTERNS", [])
    xray_bypass_extensions = resolved_config.get("XRAY_BYPASS_EXTENSIONS", [])
    xray_bypass_paths = resolved_config.get("XRAY_BYPASS_PATHS", [])
    aperture_config = resolved_config.get("APERTURE_CONFIG", {})

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🔍 Initializing Binary Anomaly Detector on {target_path.name}...")

    # Initialize lightweight filters
    filter_engine = ApertureFilter(target_path, LANGUAGE_DEFINITIONS, aperture_config)
    security = SecurityLens()

    # ==============================================================================
    # DEFENSIVE DESIGN (SENSOR OPTIMIZATION):
    # Restrict the Security Lens to entropy and bitwise operations. By disabling
    # the heavy AST and regex processors used for source code, we minimize CPU
    # overhead and prevent Catastrophic Backtracking on dense binary data.
    # ==============================================================================
    # Only the entropy and bitwise_ops counts decide an anomaly (#5500).
    security.restrict_signatures(("bitwise_ops",))

    anomalies_found = 0
    anomalies_allowed = 0
    forbidden_blocked = 0
    files_evaluated = 0

    files_to_deep_scan = []

    # ==============================================================================
    # PHASE 1: Path Filtering and Queue Generation
    # ==============================================================================
    for root, dirs, files in os.walk(target_path):
        rel_root = str(Path(root).relative_to(target_path))

        # ARCHITECTURAL DECISION (ROOT TRAVERSAL PRUNING):
        # We evaluate top-level directories against ignore rules and modify the `dirs`
        # list in-place. This prevents the OS from walking down massive ignored trees
        # (like `node_modules` or `.git`), saving massive I/O overhead.
        if rel_root == ".":
            dirs[:] = [d for d in dirs if filter_engine._check_ignore_rules(d)]
        elif not filter_engine._check_ignore_rules(rel_root):
            dirs[:] = []
            continue

        for file in files:
            files_evaluated += 1
            file_path = Path(root) / file
            ext = file_path.suffix.lower()

            # Create a normalized string for checking against configurations
            rel_path_str = str(file_path.relative_to(target_path)).replace("\\", "/")

            # Evaluate Global vs. Tool-Specific Bypasses
            is_global_allow = path_allowlisted(rel_path_str, allowlist_paths)
            is_xray_bypass = path_allowlisted(rel_path_str, xray_bypass_paths)

            is_whitelisted = is_global_allow or is_xray_bypass

            # FALSE POSITIVE MITIGATION (TEST DIRECTORIES):
            # Unit tests frequently generate high-entropy mock data (e.g., mock
            # cryptographic keys, dummy hashes). We whitelist these paths to prevent
            # pipeline friction, assuming test directories are not deployed to production.
            if _in_test_folder(rel_path_str):
                is_whitelisted = True

            # 1. DENYLIST ENFORCEMENT
            is_forbidden = any(fnmatch.fnmatch(file, pattern) for pattern in denylist_patterns)
            if is_forbidden and not is_whitelisted:
                print(f"[DENYLIST MATCH] Unauthorized file pattern detected: {rel_path_str}")
                forbidden_blocked += 1
                anomalies_found += 1
                continue

            # NOTE: We intentionally bypass `evaluate_path_integrity` here.
            # This specific detector must scan actual binaries (.png, .zip, .dll),
            # which standard Aperture filtering drops.
            files_to_deep_scan.append((file_path, rel_path_str, ext, is_whitelisted, ext in xray_bypass_extensions))

    # ==============================================================================
    # PHASE 2: Deep Content and Binary Header Inspection
    # ==============================================================================
    print(f"\n🔎 Scanning {len(files_to_deep_scan):,} files for structural anomalies:")
    print("   - Magic Byte Mismatches (e.g., hidden executables disguised as images)")
    print("   - Embedded Execution Headers (e.g., executable signatures within static data)")
    print("   - High-Entropy Payloads (e.g., packed executables or obfuscated bitwise loops)")

    start_time = time.time()

    for file_path, rel_path_str, ext, is_whitelisted, dense_is_expected in files_to_deep_scan:
        try:
            # DEFENSIVE DESIGN (MEMORY SHIELD):
            # Read only the first 8KB of the file. This is sufficient to capture
            # magic bytes, execution headers, and enough string data for an accurate
            # entropy calculation, completely preventing Out-Of-Memory (OOM) crashes on huge files.
            with open(file_path, "rb") as f:
                head_bytes = f.read(8192)

            has_anomaly = False
            anomaly_msgs = []

            # 1. Binary Analysis (Magic Bytes & Execution Headers)
            binary_threats = _scan_head(security, head_bytes, ext)

            # EXPECTED HEADER EXCEPTION:
            # Shell scripts naturally contain the '#!/bin/' header. We clear this
            # specific threat if the extension matches a known script format.
            if binary_threats:
                threat_msg = binary_threats.get("threat_snippet", "")
                if ext in [".sh", ".bash", ".zsh", ".command"] and "#!/bin/" in threat_msg:
                    binary_threats = {}

            if _binary_threat(binary_threats, dense_is_expected):
                has_anomaly = True
                anomaly_msgs.append(binary_threats.get("threat_snippet", "Unknown Binary Threat"))

            # 2. String Entropy Analysis (Encrypted/Packed Payloads)
            content = head_bytes.decode("utf-8", errors="ignore")
            sec_results = security.scan_content(content)

            if not dense_is_expected and (
                sec_results["counts"].get("entropy", 0) > 0 or _dense_run(file_path, head_bytes)
            ):
                has_anomaly = True
                anomaly_msgs.append("Mathematically dense/encrypted strings detected (Shannon Entropy > 4.8)")

            if not dense_is_expected and sec_results["counts"].get("bitwise_ops", 0) > 0:
                has_anomaly = True
                anomaly_msgs.append("Obfuscated bitwise operations (XOR loops) detected")

            # 3. Report the Anomaly
            if has_anomaly:
                if is_whitelisted:
                    anomalies_allowed += 1
                else:
                    print(f"[ANOMALY DETECTED] {rel_path_str}")
                    for msg in anomaly_msgs:
                        print(f"   -> {msg}")
                    anomalies_found += 1

        except Exception as e:
            logging.getLogger("binary_anomaly_detector").debug(f"Failed to scan '{rel_path_str}': {e}")

    end_time = time.time()
    time_delta = end_time - start_time
    scan_rate = len(files_to_deep_scan) / time_delta if time_delta > 0 else 0

    # ==============================================================================
    # SCAN SUMMARY
    # ==============================================================================
    print("\n" + "=" * 75)
    print(" BINARY ANOMALY DETECTOR: SCAN SUMMARY")
    print("=" * 75)
    print(f" Files Evaluated      : {files_evaluated:,}")
    print(f" Files Deep Scanned   : {len(files_to_deep_scan):,}")
    print(f" Time Elapsed         : {time_delta:.2f} seconds")
    print(f" Scan Velocity        : {scan_rate:,.0f} files/sec")
    print("-" * 75)
    print(f" Anomalies Detected   : {anomalies_found:,}")
    print(f" File Denylist Blocks : {forbidden_blocked:,}")
    print(f" Allowlist Bypasses   : {anomalies_allowed:,}")
    print("-" * 75)

    if anomalies_found > 0:
        print(f" [BLOCKING ACTION] {anomalies_found} structural anomalies detected. Failing pipeline.")
        print(" TIP: Entropy-based detection naturally flags compressed or dense data.")
        print("         - If safe extension (e.g., .gz, .json): Add to XRAY_BYPASS_EXTENSIONS")
        print("         - If safe specific file: Add to XRAY_BYPASS_PATHS")
        print("         - Edit these inside: gitgalaxy/standards/gitgalaxy_config.py")
        sys.exit(1)
    else:
        print(" [SUCCESS] No obfuscated payloads or binary anomalies detected.")
        if anomalies_allowed > 0:
            print(f" NOTE: {anomalies_allowed} known mock/safe files were bypassed via configuration.")
    print("=" * 75 + "\n")


def run_xray_audit(target_path: Path, config: ResolvedConfig | dict[str, Any] | None = None) -> dict:
    """
    Programmatic entry point for GalaxyScope (orchestrator execution).

    `config` was previously a module-level `gitgalaxy_config.py` import
    (#332/#335) -- that meant no YAML/CLI override could ever reach this
    audit, regardless of what a user put in .galaxyscope.yaml. Defaults to
    an unconfigured resolve_config() only when the caller doesn't already
    have a resolved config to hand over (e.g. direct/test use).
    """
    import logging

    # Mute the noisy Aperture Filter init during headless Phase 10 execution
    quiet_logger = logging.getLogger("GalaxyScope.xray")
    quiet_logger.setLevel(logging.WARNING)

    # .get() rather than attribute access: the caller may hand over either
    # a ResolvedConfig or Orchestrator's plain full_config dict, and only
    # .get() works uniformly across both.
    resolved_config = config if config is not None else resolve_config()
    allowlist_paths = resolved_config.get("ALLOWLIST_PATHS", [])
    denylist_patterns = resolved_config.get("DENYLIST_PATTERNS", [])
    xray_bypass_extensions = resolved_config.get("XRAY_BYPASS_EXTENSIONS", [])
    xray_bypass_paths = resolved_config.get("XRAY_BYPASS_PATHS", [])

    filter_engine = ApertureFilter(
        target_path, LANGUAGE_DEFINITIONS, resolved_config.get("APERTURE_CONFIG", {}), parent_logger=quiet_logger
    )
    security = SecurityLens()
    # Only the entropy and bitwise_ops counts decide an anomaly (#5500).
    security.restrict_signatures(("bitwise_ops",))

    anomalies_found = 0

    # Minimal silent scan for headless execution
    for root, dirs, files in os.walk(target_path):
        rel_root = str(Path(root).relative_to(target_path))
        if rel_root == ".":
            dirs[:] = [d for d in dirs if filter_engine._check_ignore_rules(d)]
        elif not filter_engine._check_ignore_rules(rel_root):
            dirs[:] = []
            continue

        for file in files:
            file_path = Path(root) / file
            rel_path_str = str(file_path.relative_to(target_path)).replace("\\", "/")

            is_whitelisted = (
                path_allowlisted(rel_path_str, allowlist_paths)
                or path_allowlisted(rel_path_str, xray_bypass_paths)
                or _in_test_folder(rel_path_str)
            )
            dense_is_expected = file_path.suffix.lower() in xray_bypass_extensions

            if any(fnmatch.fnmatch(file, p) for p in denylist_patterns) and not is_whitelisted:
                anomalies_found += 1
                continue

            try:
                with open(file_path, "rb") as f:
                    head_bytes = f.read(8192)
                ext = file_path.suffix.lower()

                # Check Binary Headers
                bt = _scan_head(security, head_bytes, ext)
                if (
                    _binary_threat(bt, dense_is_expected)
                    and not (ext in [".sh", ".bash", ".zsh"] and "#!/bin/" in bt.get("threat_snippet", ""))
                    and not is_whitelisted
                ):
                    anomalies_found += 1

                # Check String Entropy
                content = head_bytes.decode("utf-8", errors="ignore")
                sr = security.scan_content(content)
                if (
                    (
                        sr["counts"].get("entropy", 0) > 0
                        or sr["counts"].get("bitwise_ops", 0) > 0
                        or _dense_run(file_path, head_bytes)
                    )
                    and not is_whitelisted
                    and not dense_is_expected
                ):
                    anomalies_found += 1
            except Exception as e:
                # Deliberately NOT quiet_logger (WARNING-only, muted above for
                # ApertureFilter's init noise) -- that would silently drop this too.
                logging.getLogger("binary_anomaly_detector").debug(f"Failed to scan '{rel_path_str}': {e}")

    return {"anomalies_found": anomalies_found}


if __name__ == "__main__":
    main()
