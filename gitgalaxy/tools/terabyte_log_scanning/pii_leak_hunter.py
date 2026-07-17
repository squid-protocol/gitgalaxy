#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: PII Data Leak Hunter
# Purpose: High-speed, single-pass log analyzer that detects and masks
#          exposed Credit Cards, SSNs, and AWS API Keys.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import sys
import re
import time
from collections import defaultdict
from pathlib import Path

# ==============================================================================
# 1. REGEX PATTERNS (PII SIGNATURES)
# ==============================================================================
# We compile these as binary (bytes) to maintain maximum execution speed
# during large-scale log ingestion.
PII_PATTERNS = {
    "VISA": re.compile(rb"\b4[0-9]{12}(?:[0-9]{3})?\b"),
    "MASTERCARD": re.compile(rb"\b(?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}\b"),
    "SSN": re.compile(rb"\b\d{3}-\d{2}-\d{4}\b"),
    "AWS_KEY": re.compile(rb"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA)[A-Z0-9]{16}\b"),
}


def mask_pii(text: str) -> str:
    """Masks out the middle of sensitive data so the evidence log is safe for retention."""
    # Mask Visa & Mastercard (Leave last 4)
    text = re.sub(
        r"\b(4[0-9]{12}(?:[0-9]{3})?)\b",
        lambda m: f"VISA-MASKED-{m.group(1)[-4:]}",
        text,
    )
    text = re.sub(
        r"\b((?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12})\b",
        lambda m: f"MC-MASKED-{m.group(1)[-4:]}",
        text,
    )

    # Mask SSN (Leave last 4)
    text = re.sub(r"\b\d{3}-\d{2}-(\d{4})\b", r"XXX-XX-\1", text)

    # Mask AWS Keys (Leave first 4 and last 4)
    text = re.sub(
        r"\b((?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA))[A-Z0-9]{12}([A-Z0-9]{4})\b",
        r"\1-XXXX-\2",
        text,
    )

    return text


def draw_ascii_histogram(time_buckets: dict, keyword: str):
    """Draws a dynamically scaled ASCII histogram to visualize exposure frequency over time."""
    if not time_buckets:
        return

    print(f"\n === TIME-SERIES: {keyword.upper()} EXPOSURE ===")

    max_hits = max(time_buckets.values())
    max_bar_width = 40
    avg_hits = sum(time_buckets.values()) / len(time_buckets)
    anomaly_threshold = avg_hits * 3

    if len(time_buckets) > 15:
        print(" (Filtering to Top 15 Highest Volume Spikes)")
        top_offenders = sorted(time_buckets.items(), key=lambda x: x[1], reverse=True)[:15]
        display_buckets = dict(sorted(top_offenders))
    else:
        display_buckets = dict(sorted(time_buckets.items()))

    for time_bucket, hits in display_buckets.items():
        bar_len = int((hits / max_hits) * max_bar_width) if max_hits > 0 else 0
        bar = "█" * max(1, bar_len)

        alert = "  <-- HIGH VOLUME SPIKE DETECTED" if hits >= anomaly_threshold and hits > 10 else ""
        print(f" [{time_bucket}] {bar} ({hits:,} hits){alert}")


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("PII Data Leak Hunter")

    # -------------------------------------------------------------------------
    # 1. CLI ARGUMENT PARSING & DOCUMENTATION
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="GitGalaxy PII Data Leak Hunter: High-speed streaming parser to detect and mask exposed sensitive data.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
==============================================================================
SCANNING CAPABILITIES:
This engine bypasses standard indexing to stream raw binary logs or database 
dumps. It currently detects and actively masks the following patterns:
  - VISA Credit Cards
  - MASTERCARD Credit Cards
  - US Social Security Numbers (SSN)
  - AWS API Keys (AKIA, ASIA, etc.)

Masked evidence logs are safely written to disk without exposing the full PII.
==============================================================================
        """,
    )
    parser.add_argument("target", help="Path to the log file or database dump to scan")
    parser.add_argument(
        "--out",
        type=str,
        help="Optional: Custom directory to save the redacted evidence log",
    )
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # 2. FILE VALIDATION & GUARDRAILS
    # -------------------------------------------------------------------------
    target_path = Path(args.target).resolve()
    if not target_path.exists() or not target_path.is_file():
        print(f"\n[ERROR] Target file does not exist or is not a file: {target_path}")
        sys.exit(1)

    if args.out:
        out_dir = Path(args.out).resolve()
    else:
        out_dir = target_path.parent

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(f"\n[ERROR] Permission denied to create output directory: {out_dir}")
        sys.exit(1)

    results_path = out_dir / f"{target_path.stem}_pii_leak_evidence.log"

    try:
        file_size_bytes = target_path.stat().st_size
        file_size_gb = file_size_bytes / (1024**3)
        file_size_mb = file_size_bytes / (1024**2)
    except OSError as e:
        print(f"\n[ERROR] Could not read target file size: {e}")
        sys.exit(1)

    print(f"🔍 Initializing stream analysis: {target_path.name} ({file_size_gb:.2f} GB / {file_size_mb:.2f} MB)")
    print(f"🛡️  Masking enabled. Writing redacted evidence to: {results_path.name}")

    ts_pattern = re.compile(rb"(\d{4}-\d{2}-\d{2}[T\s]\d{2}|\b[A-Z][a-z]{2}\s+\d{1,2}\s\d{2})")
    histograms = {kw: defaultdict(int) for kw in PII_PATTERNS.keys()}

    start_time = time.time()

    # -------------------------------------------------------------------------
    # 3. HIGH-SPEED SCANNING
    # -------------------------------------------------------------------------
    try:
        with (
            open(target_path, "rb") as f_in,
            open(results_path, "w", encoding="utf-8") as f_out,
        ):
            for line in f_in:
                hit_found = False
                for pii_type, pattern in PII_PATTERNS.items():
                    if pattern.search(line):
                        # Only decode the line if a physical hit is detected to save CPU cycles
                        if not hit_found:
                            decoded_line = line.decode("utf-8", errors="ignore").strip()
                            safe_line = mask_pii(decoded_line)
                            f_out.write(f"[{pii_type}] {safe_line}\n")
                            hit_found = True  # Prevent duplicate writes if a line has multiple PII types

                        ts_match = ts_pattern.search(line)
                        bucket = (
                            ts_match.group(1).decode("utf-8", errors="ignore") + ":00" if ts_match else "Unknown Time"
                        )
                        histograms[pii_type][bucket] += 1
    except IOError as e:
        print(f"\n[FATAL ERROR] I/O failure during streaming: {e}")
        sys.exit(1)

    time_elapsed = time.time() - start_time

    # -------------------------------------------------------------------------
    # 4. REPORTING & DASHBOARDS
    # -------------------------------------------------------------------------
    for kw in PII_PATTERNS.keys():
        draw_ascii_histogram(histograms[kw], kw)

    total_counts = {kw: sum(buckets.values()) for kw, buckets in histograms.items()}
    max_total = max(total_counts.values()) if total_counts.values() else 0

    print("\n" + "=" * 75)
    print(" PII DATA LEAK HUNTER: SCAN SUMMARY")
    print("=" * 75)

    if max_total > 0:
        for kw, count in total_counts.items():
            bar_len = int((count / max_total) * 30) if max_total > 0 else 0
            bar = "█" * max(1, bar_len) if count > 0 else ""
            print(f" {kw.ljust(15)} | {bar} ({count:,} hits)")
    else:
        print(" [SUCCESS] Clean scan. No Social Security, Credit Card, or AWS Keys detected.")

    print("-" * 75)

    # Safely calculate processing speed depending on file size to prevent math errors
    if time_elapsed > 0:
        if file_size_gb > 0.1:
            speed = file_size_gb / time_elapsed
            speed_str = f"{speed:.3f} GB/s"
        else:
            speed = file_size_mb / time_elapsed
            speed_str = f"{speed:.2f} MB/s"
    else:
        speed_str = "Instant"

    print(f" [COMPLETE] Processed {target_path.name} in {time_elapsed:.2f} seconds.")
    print(f" Processing Velocity: {speed_str}")
    print(f" Redacted Evidence Log: {results_path.resolve()}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
