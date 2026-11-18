#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Import Policy Gate
#
# PURPOSE:
# Zero-Trust Dependency Verification and Behavioral Policy Enforcement.
#
# ARCHITECTURAL DECISION:
# Operating as a RAM-Exclusive Logic Gate, this import policy gate consumes the Phase 1
# Dependency Graph. By completely divesting from redundant O(N) disk parsing,
# it achieves near-instant policy enforcement. It mitigates Namespace Hijacking
# and Dependency Confusion attacks by comparing raw codebase imports against
# resolved manifest aliases, while enforcing dynamic risk thresholds based on
# build-time execution contexts and network topography.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Import exclusively from the GitGalaxy Hub
from gitgalaxy.metrics.signal_processor import SignalProcessor
from gitgalaxy.standards.config_resolver import ResolvedConfig, path_allowlisted, resolve_config

# The behavioral category this import policy gate gates on, mapped to its name in
# SignalProcessor.RISK_SCHEMA -- Phase 3 computes it once; the import policy gate
# reads it back instead of recomputing risk from raw hit counts.
_IMPORT_GATE_RISK_MAP = {
    "Secrets Leak Risk": "secrets_risk",
}
_IMPORT_GATE_RISK_INDEXES = {
    label: SignalProcessor.RISK_SCHEMA.index(key)
    for label, key in _IMPORT_GATE_RISK_MAP.items()
    if key in SignalProcessor.RISK_SCHEMA
}

# risk_vector entries are 0-100 sigmoid outputs from SignalProcessor; 50.0 is
# the sigmoid's own midpoint, so using it as the block cutoff defers entirely
# to SignalProcessor's judgment instead of maintaining a second threshold.
_IMPORT_GATE_BLOCK_THRESHOLD = 50.0

# Manifest flags the ManifestParser writes into the resolution map (#8432).
_INSECURE_REGISTRY_PREFIX = "INSECURE_REGISTRY_"
_INSTALL_HOOK_PREFIX = "INSTALL_HOOK_"
# A resolved value that bypasses the registry (direct URI / VCS / file reference).
_DIRECT_REF_PREFIXES = ("file:", "github:", "git+", "http:", "hg+", "svn+", "bzr+")
_TUNNEL_HOSTS = ("ngrok", "localtunnel", "loca.lt")


def manifest_flag_findings(alias_map: dict) -> list[tuple[str, str, str]]:
    """Every manifest flag the parser raised, as (directory, kind, detail).

    The parser records these in the resolution map but nothing read them as
    findings; the import policy gate now does (#8432). Kinds: insecure_registry
    (http:// registry, ngrok / localtunnel host), install_hook (a lifecycle
    script that fetches or evals), direct_reference (alias or requirement
    resolved to a file / git / http source that skips registry integrity).
    """
    found: list[tuple[str, str, str]] = []
    for dir_key, local in alias_map.items():
        if not isinstance(local, dict):
            continue
        for key, value in local.items():
            if not isinstance(value, str):
                continue
            if key.startswith(_INSECURE_REGISTRY_PREFIX):
                found.append((dir_key, "insecure_registry", value))
            elif key.startswith(_INSTALL_HOOK_PREFIX):
                found.append((dir_key, "install_hook", value))
            elif value.lower().startswith(_DIRECT_REF_PREFIXES):
                kind = "insecure_registry" if any(h in value.lower() for h in _TUNNEL_HOSTS) else "direct_reference"
                found.append((dir_key, kind, value))
    return found


def _is_test_path(rel_path: str) -> bool:
    """True only when a path has a directory component named `test` or `tests`.

    Anchored on whole path components, never a substring and never the filename:
    `src/helper_test.py` or `src/test_x.py` is judged like any other file, so a
    payload cannot hide by being named like a test (#8432)."""
    parts = rel_path.lower().replace("\\", "/").split("/")
    return any(d in ("test", "tests") for d in parts[:-1])


def run_import_gate_audit(
    parsed_files: list,
    alias_map: dict | None = None,
    config: ResolvedConfig | dict[str, Any] | None = None,
) -> dict:
    """
    Programmatic entry point for GalaxyScope (Zero-Disk I/O).
    Operates exclusively on the pre-tokenized, anomaly-checked RAM graph from Phase 1.

    `config` was previously a module-level `gitgalaxy_config.py` import
    (#332/#335) -- that meant no YAML/CLI override could ever reach this
    import policy gate, regardless of what a user put in .galaxyscope.yaml. Defaults
    to an unconfigured resolve_config() only when the caller doesn't
    already have a resolved config to hand over (e.g. direct/test use).
    """
    logger = logging.getLogger("GalaxyScope.import_policy_gate")
    safe_alias_map = alias_map or {}
    # .get() rather than attribute access: the caller may hand over either
    # a ResolvedConfig or Orchestrator's plain full_config dict, and only
    # .get() works uniformly across both.
    resolved_config = config if config is not None else resolve_config()
    allowlist_paths = resolved_config.get("ALLOWLIST_PATHS", [])
    strict_import_mode = resolved_config.get("STRICT_IMPORT_MODE", False)
    approved_imports = resolved_config.get("APPROVED_IMPORTS", [])
    blacklisted_imports = resolved_config.get("BLACKLISTED_IMPORTS", [])
    import_gate_network_weighting = resolved_config.get("IMPORT_GATE_NETWORK_WEIGHTING", False)

    imports_whitelisted = 0
    imports_blacklisted = 0
    imports_unknown = 0
    threats_found_files: set[str] = set()
    threats_allowed = 0

    if not parsed_files:
        return {
            "imports_whitelisted": imports_whitelisted,
            "imports_unknown": imports_unknown,
            "imports_blacklisted": imports_blacklisted,
            "threats_found": len(threats_found_files),
            "threats_allowed": threats_allowed,
        }

    # Manifest flags (insecure registry, direct refs, install hooks) are threats in
    # their own right; the allowlist can excuse them like any other threat.
    for flag_dir, flag_kind, flag_detail in manifest_flag_findings(safe_alias_map):
        flag_path = f"{flag_dir}/<manifest:{flag_kind}>"
        if path_allowlisted(flag_dir, allowlist_paths):
            threats_allowed += 1
            continue
        logger.warning(f"🚨 [MANIFEST {flag_kind.upper()}] {flag_detail} (manifest dir: {flag_dir})")
        threats_found_files.add(flag_path)

    for file_node in parsed_files:
        rel_path_str = file_node.get("path", "unknown")
        is_whitelisted = path_allowlisted(rel_path_str, allowlist_paths)

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

            # DEFENSIVE DESIGN (ABSOLUTE PATH ROOT BARRIER): the "." check
            # above only terminates a strictly relative traversal. If
            # rel_path_str is instead an absolute path (e.g. "/opt/app/
            # main.py"), current_dir climbs to the filesystem root and
            # Path("/").parent == Path("/") forever -- it never becomes
            # ".", so the loop never terminates. A path is at its own root
            # exactly when .parent returns itself; catch that directly.
            if current_dir == current_dir.parent:
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

            if true_pkg in blacklisted_imports:
                imports_blacklisted += 1
                threats_found_files.add(rel_path_str)
                # The Allowlist Loophole Fix: A blacklisted import is ALWAYS a threat. Never suppress it.
                if true_pkg != pkg:
                    logger.critical(
                        f"🚨 [BLACKLISTED IMPORT] Spoofed alias blocked: '{pkg}' -> '{true_pkg}' in: {rel_path_str}"
                    )
                else:
                    logger.critical(f"🚨 [BLACKLISTED IMPORT] Unauthorized package '{pkg}' blocked in: {rel_path_str}")
            elif true_pkg in approved_imports:
                imports_whitelisted += 1
            else:
                imports_unknown += 1
                if strict_import_mode and not is_whitelisted:
                    threats_found_files.add(rel_path_str)
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
        # package.json is the exception: it carries npm lifecycle hooks, so the build-time
        # multiplier below must see it (#8432).
        is_package_json = Path(rel_path_str).name == "package.json"
        if not is_package_json and (
            ext
            in {
                ".svg",
                ".xml",
                ".jelly",
                ".html",
                ".css",
                ".md",
                ".json",
                ".yaml",
                ".yml",
                ".txt",
                ".properties",
            }
            or safe_path_lower.endswith(".d.ts")
        ):
            continue

        # Shield test environments. Unit tests intentionally mock attacks, use hardcoded dummy data,
        # and contain high-entropy strings which trigger massive false positives in behavioral heuristics.
        if _is_test_path(rel_path_str):
            continue

        # DEFENSIVE DESIGN (BUILD-TIME EXECUTION MULTIPLIER):
        # Configuration scripts (like setup.py or package.json) are executed by CI/CD
        # runners at build time. RCE here compromises the host before the app even runs.
        # We amplify SignalProcessor's already-computed risk scores for these files so
        # any I/O or Danger signal instantly trips the import policy gate's block threshold.
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

        # DEFENSIVE DESIGN (NETWORK-CENTRALITY MULTIPLIER, opt-in):
        # A highly central "hub" file (large Downstream Exposure / Blast Radius from
        # Phase 4's network topology) gets less tolerance for the same embedded threat
        # signal than a peripheral file. Only ever amplifies -- a low-centrality file
        # is still judged on its own merits, never given a discount for being obscure.
        network_multiplier = 1.0
        if import_gate_network_weighting:
            network_metrics = file_node.get("telemetry", {}).get("network_metrics", {})
            # #3027: None = not computed (e.g. betweenness past its work budget) -- no
            # amplification from a metric nobody measured.
            blast_radius = network_metrics.get("normalized_blast_radius") or 0.0
            betweenness = network_metrics.get("betweenness_score") or 0.0
            if blast_radius > 1.0:
                network_multiplier += blast_radius * 0.5
            if betweenness > 0.05:
                network_multiplier += 0.5

        # Read the risk scores SignalProcessor already computed for this file back in
        # Phase 3, rather than recomputing risk from raw hit counts (single source of truth).
        risk_vector = file_node.get("risk_vector", [])
        exposures = {}
        for risk_label, schema_idx in _IMPORT_GATE_RISK_INDEXES.items():
            if schema_idx >= len(risk_vector):
                continue
            raw_score = risk_vector[schema_idx]
            if not isinstance(raw_score, (int, float)) or raw_score <= 0.0:
                continue
            scaled_score = min(raw_score * build_time_multiplier * network_multiplier, 100.0)
            if scaled_score >= _IMPORT_GATE_BLOCK_THRESHOLD:
                exposures[risk_label] = scaled_score

        if exposures:
            if is_whitelisted:
                threats_allowed += 1
            else:
                logger.warning(f"🚨 [THREAT DETECTED] Risk Threshold Breached in: {rel_path_str}")
                for risk, score in exposures.items():
                    logger.warning(f"   -> {risk}: {score:.1f}%")
                threats_found_files.add(rel_path_str)

    return {
        "imports_whitelisted": imports_whitelisted,
        "imports_unknown": imports_unknown,
        "imports_blacklisted": imports_blacklisted,
        "threats_found": len(threats_found_files),
        "threats_allowed": threats_allowed,
    }


def _risk_labels() -> list[str]:
    """The display label AuditRecorder gives each RISK_SCHEMA slot (same derivation as its
    "4. Vulnerability & Risk Exposures" block), so the CLI reads back what the recorder wrote."""
    from gitgalaxy.recorders.audit_recorder import AuditRecorder
    from gitgalaxy.standards import gitgalaxy_config as config

    recorder = AuditRecorder()
    exposure_labels = getattr(config, "RECORDING_SCHEMAS", {}).get("EXPOSURE_LABELS", {})
    return [exposure_labels.get(k, recorder.format_label(k)) for k in SignalProcessor.RISK_SCHEMA]


def _audit_file_to_node(path: str, entry: dict, labels: list[str]) -> dict:
    """Translate one audit-JSON file entry (AuditRecorder's shape) into the
    in-memory node shape run_import_gate_audit reads (#8428).

    The audit JSON has no ``raw_imports`` / ``risk_vector``: imports live under
    "9. Extracted Dependencies" and risk scores under "4. Vulnerability & Risk
    Exposures" as ``{display label: "12.5%"}`` (or "[UNSCANNED - NO DATA]").
    """
    exposures = entry.get("4. Vulnerability & Risk Exposures") or {}
    vector = []
    for label in labels:
        try:
            vector.append(float(str(exposures.get(label, 0.0)).rstrip("%")))
        except ValueError:
            vector.append(0.0)  # "[UNSCANNED - NO DATA]"
    return {"path": path, "raw_imports": entry.get("9. Extracted Dependencies") or [], "risk_vector": vector}


def _parsed_files_from_audit(data: dict) -> list:
    labels = _risk_labels()
    groups = data.get("6. Parsed Files (Scanned Artifacts)", {})
    return [
        _audit_file_to_node(path, file_info, labels)
        for folder_data in groups.values()
        for path, file_info in folder_data.get("Files", {}).items()
    ]


def main():
    """
    Standalone Execution Mode.
    Because the import policy gate is decoupled from redundant O(N) disk parsing,
    it must be fed the compiled JSON Dependency Graph generated by the GalaxyScope orchestrator.
    """
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Import Policy Gate")

    parser = argparse.ArgumentParser(description="Import Policy Gate (RAM-Exclusive Mode)")
    parser.add_argument("target", help="Path to the compiled GalaxyScope RAM graph (e.g., results.json)")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to project-level configuration file (e.g., .galaxyscope.yaml) -- "
        "same resolver galaxyscope.py uses, so standalone runs honor the same "
        "STRICT_IMPORT_MODE / BLACKLISTED_IMPORTS / etc. overrides (#335).",
    )
    args = parser.parse_args()

    resolved_config = resolve_config(yaml_path=args.config)

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target '{target_path}' does not exist.")
        sys.exit(1)

    print(f"🧱 Initializing Import Policy Gate against {target_path.name}...")

    parsed_files = []

    try:
        if target_path.is_dir():
            print("   -> Directory detected. Orchestrating GalaxyScope RAM graph generation...")
            import subprocess
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                # Run the orchestrator to generate the JSON graph in a temp directory
                target_out_file = str(Path(tmpdir) / "import_gate_temp.json")
                # sys.executable, not a bare "python" PATH lookup -- guarantees
                # the exact same interpreter/venv GitGalaxy itself is running
                # under, not whatever "python" happens to resolve to (#472).
                result = subprocess.run(  # noqa: S603 -- args are fixed strings + a Path, no untrusted input
                    [sys.executable, "-m", "gitgalaxy.galaxyscope", str(target_path), "--output", target_out_file],
                    capture_output=True,
                    text=True,
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

                with open(audit_files[0], encoding="utf-8") as f:
                    data = json.load(f)
                    parsed_files = _parsed_files_from_audit(data)
        else:
            # Standard file-based load
            with open(target_path, encoding="utf-8") as f:
                data = json.load(f)
                parsed_files = _parsed_files_from_audit(data)

    except Exception as e:
        print(f"❌ Failed to parse RAM graph: {e}")
        sys.exit(1)

    # In standalone CLI mode, we bypass the dynamic manifest parsing for speed,
    # relying purely on strict exact-match dependencies and behavioral structural signatures.
    results = run_import_gate_audit(parsed_files, alias_map={}, config=resolved_config)

    mode_str = (
        "Strict (Exclude Blacklist and Unknown)"
        if resolved_config.get("STRICT_IMPORT_MODE")
        else "Audit (Allow Whitelist + Unknown)"
    )

    print("\n" + "=" * 75)
    print(" 🧱 IMPORT POLICY GATE: SCAN SUMMARY")
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
