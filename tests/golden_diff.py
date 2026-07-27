#!/usr/bin/env python3
import json
import sys
import hashlib
import math
from typing import Any, Dict

# Parallel file processing means per-language/per-repo float sums (e.g.
# "impact") land in a different accumulation order each run, producing
# sub-cent noise like 16694.93 vs 16694.930000000004. Real drift is much
# larger than this, so a tight tolerance still catches genuine regressions.
FLOAT_REL_TOL = 1e-6
FLOAT_ABS_TOL = 1e-6

def load_and_sanitize(filepath: str) -> Dict[str, Any]:
    """Loads JSON and strips volatile execution metadata."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Strip out volatile metadata that changes every run
    if "1. Forensic Trail (Traceability)" in data:
        context = data["1. Forensic Trail (Traceability)"].get("Analysis Context", {})
        context.pop("Analysis ISO Timestamp", None)
        context.pop("Total Scan Duration", None)
        # Absolute path is machine/runner-specific (e.g. /home/joe/... locally
        # vs /home/runner/work/... in CI) -- never structurally meaningful.
        context.pop("Absolute Project Path", None)

        git_footprint = data["1. Forensic Trail (Traceability)"].get("Source Control Footprint (Immutable Anchor)", {})
        git_footprint.pop("Commit Hash (SHA-1)", None)
        git_footprint.pop("Last Code Integration Date", None)
        # Remote URL formatting depends on the clone method (HTTPS clones
        # append .git, some don't), and a `--branch <tag> --depth 1` clone
        # lands in detached HEAD ("HEAD") instead of the tag's branch name.
        # Neither reflects anything about the analyzed repository's structure.
        git_footprint.pop("Remote Origin URL", None)
        git_footprint.pop("Active Branch", None)

    return data

def _normalize_floats(data: Any) -> Any:
    """Rounds floats to FLOAT_ABS_TOL's precision so summation-order noise
    doesn't change the deterministic hash between two structurally-identical runs."""
    if isinstance(data, float):
        return round(data, 6)
    if isinstance(data, dict):
        return {k: _normalize_floats(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_normalize_floats(v) for v in data]
    return data

def generate_deterministic_hash(data: Dict[str, Any]) -> str:
    """Creates a stable MD5 hash of a dictionary regardless of key insertion order."""
    # sort_keys=True guarantees the JSON string is always structurally identical
    normalized = _normalize_floats(data)
    sanitized_string = json.dumps(normalized, sort_keys=True, separators=(',', ':'))
    return hashlib.md5(sanitized_string.encode('utf-8')).hexdigest()

def _is_real_number(value: Any) -> bool:
    # bool is a subclass of int in Python -- True/False must still compare exactly.
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def deep_compare(expected: Any, actual: Any, path: str = "") -> list:
    """Recursive diffing engine. Only runs if hashes mismatch."""
    differences = []

    if isinstance(expected, dict) and isinstance(actual, dict):
        all_keys = set(expected.keys()).union(set(actual.keys()))
        for key in all_keys:
            if key not in expected:
                differences.append(f"➕ EXTRA KEY FOUND: {path}/{key}")
            elif key not in actual:
                differences.append(f"➖ MISSING KEY: {path}/{key}")
            else:
                differences.extend(deep_compare(expected[key], actual[key], f"{path}/{key}"))
    elif _is_real_number(expected) and _is_real_number(actual):
        if not math.isclose(expected, actual, rel_tol=FLOAT_REL_TOL, abs_tol=FLOAT_ABS_TOL):
            differences.append(f"⚠️ MISMATCH at {path}: Expected {expected}, Got {actual}")
    elif expected != actual:
        differences.append(f"⚠️ MISMATCH at {path}: Expected {expected}, Got {actual}")

    return differences

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python golden_diff.py <golden_master.json> <new_output.json>")
        sys.exit(1)

    golden_path = sys.argv[1]
    actual_path = sys.argv[2]

    try:
        golden_data = load_and_sanitize(golden_path)
        actual_data = load_and_sanitize(actual_path)
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        sys.exit(1)

    # =========================================================
    # STAGE 1: FAST-FAIL DETERMINISTIC HASHING (O(1) Time)
    # =========================================================
    golden_hash = generate_deterministic_hash(golden_data)
    actual_hash = generate_deterministic_hash(actual_data)

    if golden_hash == actual_hash:
        print(f"✅ STAGE 1 PASS: Deterministic Hashes Match ({golden_hash}).")
        print("✅ GOLDEN MASTER PARITY CONFIRMED: 100% Structural Match. (Bypassing deep scan).")
        sys.exit(0)

    # =========================================================
    # STAGE 2: DEEP DIAGNOSTIC DIFF (Only runs on failure)
    # =========================================================
    print(f"⚠️ STAGE 1 FAIL: Hash mismatch. Expected {golden_hash}, got {actual_hash}.")
    print("⏳ Initiating Stage 2 Deep Diagnostic Scan (This may take a moment for large telemetry)...")
    
    diffs = deep_compare(golden_data, actual_data)

    if diffs:
        print("\n❌ CRITICAL: Structural Drift Detected in GitGalaxy Output!\n")
        # Cap the output at 50 differences so we don't crash the GitHub Actions log limit
        for diff in diffs[:50]:
            print(diff)
        
        if len(diffs) > 50:
            print(f"\n... and {len(diffs) - 50} more differences.")
            
        print("\nIf this change is intentional (e.g., you improved a parser), update the Golden Master.")
        sys.exit(1)

    print("\n✅ STAGE 2 PASS: Hash differed but no differences exceeded tolerance (float summation-order noise only).")
    sys.exit(0)