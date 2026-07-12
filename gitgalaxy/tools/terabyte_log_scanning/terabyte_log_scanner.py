#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: High-Volume Log Scanner
# Purpose: High-speed, single-pass log analyzer with ASCII time-series histograms.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import sys
import re
import time
import json
from collections import defaultdict
from pathlib import Path


def draw_ascii_histogram(time_buckets: dict, keyword: str):
    """
    Draws a dynamically scaled ASCII histogram.
    If the dataset is massive, it filters to show only the highest volume spikes
    to prevent terminal flooding.
    """
    if not time_buckets:
        return

    print(f"\n === TIME-SERIES: {keyword.upper()} ===")

    max_hits = max(time_buckets.values())
    max_bar_width = 40
    avg_hits = sum(time_buckets.values()) / len(time_buckets)
    anomaly_threshold = avg_hits * 3

    # UX Safeguard: If there are too many buckets, only show the Top 15 highest volume spikes
    if len(time_buckets) > 15:
        print(" (Filtering to Top 15 Highest Volume Spikes)")
        # Sort by highest hits, grab top 15, then resort chronologically for the graph
        top_offenders = sorted(time_buckets.items(), key=lambda x: x[1], reverse=True)[:15]
        display_buckets = dict(sorted(top_offenders))
    else:
        display_buckets = dict(sorted(time_buckets.items()))

    for time_bucket, hits in display_buckets.items():
        # Calculate bar length safely
        bar_len = int((hits / max_hits) * max_bar_width) if max_hits > 0 else 0
        bar = "█" * max(1, bar_len)

        # Flag statistical anomalies visually
        alert = "  <-- VOLUME ANOMALY DETECTED" if hits >= anomaly_threshold and hits > 10 else ""
        print(f" [{time_bucket}] {bar} ({hits:,} hits){alert}")


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("High-Volume Log Scanner")

    # -------------------------------------------------------------------------
    # 1. CLI ARGUMENT PARSING & DOCUMENTATION
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="GitGalaxy High-Volume Log Scanner: High-speed, single-pass log analyzer with ASCII time-series histograms.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
==============================================================================
JSON IR State Structure:
If using --input_state, the script expects a GitGalaxy Intermediate 
Representation (IR) JSON file. It specifically targets the 'known_programs' 
array to detect execution patterns and identify dead code.

Expected JSON Schema:
{
  "analysis": {
    "known_programs": ["PROGRAM1", "PROGRAM2"]
  }
}
==============================================================================
        """,
    )
    parser.add_argument("target", help="Path to the log file (Translated ASCII SMF or Server Logs)")
    parser.add_argument(
        "-k",
        "--keywords",
        nargs="+",
        help="Keywords to search for manually (e.g., -k PGM1 PGM2)",
    )
    parser.add_argument(
        "--input_state",
        type=str,
        help="Path to GitGalaxy ir_state.json to auto-extract targets",
    )
    parser.add_argument("--out", type=str, help="Optional: Custom directory to save the results log")
    args = parser.parse_args()

    # Validate target log file exists before initializing the stream
    target_path = Path(args.target).resolve()
    if not target_path.exists() or not target_path.is_file():
        print(f"\n[ERROR] Target log file does not exist or is not a file: {target_path}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 2. INPUT VALIDATION & STATE INGESTION
    # -------------------------------------------------------------------------
    search_targets = []

    if args.input_state:
        state_path = Path(args.input_state).resolve()
        if not state_path.exists():
            print(f"\n[ERROR] Input state JSON file not found: {state_path}")
            sys.exit(1)

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                ir_state = json.load(f)

            # Strict Schema Validation
            if not isinstance(ir_state, dict):
                raise ValueError("The root of the JSON file must be an object {}.")
            if "analysis" not in ir_state or "known_programs" not in ir_state["analysis"]:
                raise ValueError("JSON is missing the required ['analysis']['known_programs'] path.")

            search_targets = ir_state["analysis"]["known_programs"]

            if not isinstance(search_targets, list) or not search_targets:
                print("\n[WARNING] 'known_programs' array is empty or invalid. Nothing to search.")
                sys.exit(0)

            print(f"Loaded {len(search_targets)} targets from {state_path.name}")

        except json.JSONDecodeError as e:
            print(f"\n[ERROR] Invalid JSON format in {state_path.name}:\n    {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n[ERROR] Failed to parse input state:\n    {e}")
            sys.exit(1)

    elif args.keywords:
        search_targets = args.keywords
    else:
        print("\n[ERROR] You must provide targets using either -k/--keywords or --input_state.")
        parser.print_help()
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 3. REGEX COMPILATION & FILE PREPARATION
    # -------------------------------------------------------------------------
    keyword_patterns = {}
    for kw in search_targets:
        # Pre-compile regex for speed. Encode to bytes for fast binary reading.
        try:
            pattern_str = rf"{kw}"
            keyword_patterns[kw] = re.compile(pattern_str.encode("utf-8"), re.IGNORECASE)
        except re.error as e:
            print(f"\n[ERROR] Invalid regex generated for keyword '{kw}': {e}")
            sys.exit(1)

    ts_pattern = re.compile(rb"(\d{4}-\d{2}-\d{2}[T\s]\d{2}|\b[A-Z][a-z]{2}\s+\d{1,2}\s\d{2})")
    histograms = {kw: defaultdict(int) for kw in search_targets}

    # Determine output paths
    if args.out:
        out_dir = Path(args.out).resolve()
    else:
        out_dir = target_path.parent

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(f"\n[ERROR] Permission denied to create output directory: {out_dir}")
        sys.exit(1)

    results_path = out_dir / f"{target_path.stem}_results.txt"
    sidecar_path = out_dir / "dynamic_telemetry.json"

    start_time = time.time()
    print(f"🔍 Initializing stream analysis of {target_path.name} for {len(search_targets)} keywords...")

    # -------------------------------------------------------------------------
    # 4. STREAMING LOG ANALYSIS (Memory-Optimized)
    # -------------------------------------------------------------------------
    try:
        with (
            open(target_path, "rb") as f_in,
            open(results_path, "w", encoding="utf-8") as f_out,
        ):
            for line in f_in:
                for kw, pattern in keyword_patterns.items():
                    if pattern.search(line):
                        decoded_line = line.decode("utf-8", errors="ignore").strip()
                        ts_match = ts_pattern.search(line)

                        # Bucket by hour
                        bucket = (
                            ts_match.group(1).decode("utf-8", errors="ignore") + ":00" if ts_match else "Unknown Time"
                        )
                        histograms[kw][bucket] += 1

                        f_out.write(f"{decoded_line}\n")
                        break  # Stop checking keywords once a hit is found on this line
    except IOError as e:
        print(f"\n[FATAL ERROR] I/O failure during streaming: {e}")
        sys.exit(1)

    time_elapsed = time.time() - start_time

    # -------------------------------------------------------------------------
    # 5. REPORTING & SIDECAR GENERATION
    # -------------------------------------------------------------------------
    for kw, buckets in histograms.items():
        draw_ascii_histogram(buckets, kw)

    print(f"\n[SUCCESS] Scan completed in {time_elapsed:.2f} seconds.")
    print(f"Filtered results saved to: {results_path}")

    # Calculate total hits for the JSON sidecar
    total_counts = {kw: sum(buckets.values()) for kw, buckets in histograms.items()}
    telemetry_payload = {"execution_counts": total_counts, "resolved_dynamic_calls": {}}

    try:
        with open(sidecar_path, "w", encoding="utf-8") as f_json:
            json.dump(telemetry_payload, f_json, indent=4)
        print(f"JSON State Sidecar written to: {sidecar_path}")
    except IOError as e:
        print(f"\n[ERROR] Failed to write telemetry sidecar: {e}")

    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
