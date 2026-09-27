#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: PII Data Leak Hunter
# Purpose: High-speed, single-pass log analyzer that detects and masks
#          exposed Credit Cards, SSNs, and AWS API Keys.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

# ==============================================================================
# 1. REGEX PATTERNS (PII SIGNATURES)
# ==============================================================================
# We compile these as binary (bytes) to maintain maximum execution speed
# during large-scale log ingestion.
#
# National identifiers come in REGION PACKS (#3832): the hunter used to know
# only the US SSN, so an Indian Aadhaar number, a Brazilian CPF or a UK
# National Insurance number sailed through a "clean" scan. A shape alone is a
# weak signal for a bare run of digits, so every pack whose shape could be an
# ordinary number carries a checksum validator (and BSN, a bare 9-digit number,
# also needs its label on the line). A pattern hit only counts if its validator
# accepts it.


def _iban_valid(raw: bytes) -> bool:
    """ISO 13616 mod-97: move the first four characters to the end, map A-Z to
    10-35, and the number must leave remainder 1."""
    iban = raw.replace(b" ", b"").decode("ascii").upper()
    if not 15 <= len(iban) <= 34:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(ch, 36)) for ch in rearranged)) % 97 == 1


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def _digits(raw: bytes) -> str:
    return "".join(ch for ch in raw.decode("ascii") if ch.isascii() and ch.isdigit())


def _aadhaar_valid(raw: bytes) -> bool:
    """UIDAI Aadhaar: 12 digits, the last a Verhoeff check digit."""
    digits = _digits(raw)
    check = 0
    for i, ch in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[i % 8][int(ch)]]
    return len(digits) == 12 and check == 0


def _cpf_valid(raw: bytes) -> bool:
    """Brazilian CPF: 11 digits, the last two mod-11 check digits. A run of one
    repeated digit passes the arithmetic but is never issued."""
    digits = [int(ch) for ch in _digits(raw)]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for n in (9, 10):
        total = sum(d * w for d, w in zip(digits[:n], range(n + 1, 1, -1)))
        if (total * 10 % 11) % 10 != digits[n]:
            return False
    return True


_BSN_LABEL = re.compile(rb"(?i)\b(?:bsn|burgerservicenummer|sofinummer)\b")


def _bsn_valid(raw: bytes, line: bytes) -> bool:
    """Dutch BSN: 9 digits passing the "11-proof" (weights 9..2 and -1). A bare
    9-digit number is too common to flag on arithmetic alone, so the line must
    also name it."""
    digits = [int(ch) for ch in _digits(raw)]
    if len(digits) != 9 or not any(digits):
        return False
    total = sum(d * w for d, w in zip(digits, (9, 8, 7, 6, 5, 4, 3, 2, -1)))
    return total % 11 == 0 and _BSN_LABEL.search(line) is not None


# (pattern, validator). A validator takes the matched bytes and the whole line
# and returns whether it is a real identifier; None accepts every match.
_Validator = Optional[Callable[[bytes, bytes], bool]]
PII_REGION_PACKS: dict[str, dict[str, tuple["re.Pattern[bytes]", _Validator]]] = {
    "global": {
        "VISA": (re.compile(rb"\b4[0-9]{12}(?:[0-9]{3})?\b"), None),
        "MASTERCARD": (
            re.compile(rb"\b(?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}\b"),
            None,
        ),
        "AWS_KEY": (re.compile(rb"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA)[A-Z0-9]{16}\b"), None),
    },
    "us": {
        "SSN": (re.compile(rb"\b\d{3}-\d{2}-\d{4}\b"), None),
    },
    # IBAN is used across Europe, the Middle East and beyond, not just the EU.
    "iban": {
        "IBAN": (
            re.compile(rb"\b[A-Z]{2}[0-9]{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b"),
            lambda raw, _line: _iban_valid(raw),
        ),
    },
    "uk": {
        # HMRC NINO: two prefix letters (D, F, I, Q, U, V never; O never second;
        # BG, GB, KN, NK, NT, TN, ZZ never issued), six digits, suffix A-D.
        "NINO": (
            re.compile(
                rb"\b(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z] ?[0-9]{2} ?[0-9]{2} ?[0-9]{2} ?[A-D]\b"
            ),
            None,
        ),
    },
    "in": {
        # Aadhaar never starts with 0 or 1; the separator, if any, is consistent.
        "AADHAAR": (
            re.compile(rb"(?<![0-9])(?<![0-9][ -])[2-9][0-9]{3}([ -]?)[0-9]{4}\1[0-9]{4}(?![ -]?[0-9])"),
            lambda raw, _line: _aadhaar_valid(raw),
        ),
    },
    "br": {
        "CPF": (
            re.compile(rb"(?<![0-9.])(?:[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}|[0-9]{11})(?![0-9])"),
            lambda raw, _line: _cpf_valid(raw),
        ),
    },
    "nl": {
        "BSN": (
            re.compile(rb"(?<![0-9])[0-9]{9}(?![0-9])"),
            _bsn_valid,
        ),
    },
}

_PACK_ENTRY_BY_NAME = {name: entry for pack in PII_REGION_PACKS.values() for name, entry in pack.items()}

# The flat {name: pattern} view every pack contributes to.
PII_PATTERNS = {name: pattern for name, (pattern, _) in _PACK_ENTRY_BY_NAME.items()}


def select_patterns(regions=None):
    """The {name: (pattern, validator)} set for the chosen region packs (all when
    None). The global pack (cards, cloud keys) is always included."""
    chosen = set(PII_REGION_PACKS) if regions is None else {"global", *regions}
    unknown = chosen - set(PII_REGION_PACKS)
    if unknown:
        raise ValueError(f"unknown PII region pack(s): {', '.join(sorted(unknown))}")
    return {
        name: entry for region, pack in PII_REGION_PACKS.items() if region in chosen for name, entry in pack.items()
    }


def find_pii(line: bytes, patterns=None):
    """The PII types present in one raw line, validators applied."""
    patterns = select_patterns() if patterns is None else patterns
    found = []
    for name, (pattern, validator) in patterns.items():
        if any(validator is None or validator(m.group(0), line) for m in pattern.finditer(line)):
            found.append(name)
    return found


def _mask_validated(text: str, name: str, render) -> str:
    """Mask every match of a region-pack pattern its validator accepts."""
    pattern, validator = _PACK_ENTRY_BY_NAME[name]
    str_pattern = re.compile(pattern.pattern.decode("ascii"))
    line = text.encode("utf-8", errors="ignore")

    def _sub(m):
        if validator is not None and not validator(m.group(0).encode("ascii"), line):
            return m.group(0)
        return render(m.group(0))

    return str_pattern.sub(_sub, text)


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

    # Region packs (#3832). Each keeps only its last four characters.
    text = _mask_validated(text, "IBAN", lambda s: f"IBAN-MASKED-{s.replace(' ', '')[-4:]}")
    text = _mask_validated(text, "NINO", lambda s: f"NINO-MASKED-{s[-1]}")
    text = _mask_validated(text, "AADHAAR", lambda s: f"AADHAAR-MASKED-{s[-4:]}")
    text = _mask_validated(text, "CPF", lambda s: f"CPF-MASKED-{_digits(s.encode('ascii'))[-4:]}")
    text = _mask_validated(text, "BSN", lambda s: f"BSN-MASKED-{s[-4:]}")

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
  - VISA / MASTERCARD Credit Cards and AWS API Keys (always on)
  Region packs (all on by default; narrow with --regions):
  - us:   US Social Security Numbers (SSN)
  - iban: International Bank Account Numbers (mod-97 checked)
  - uk:   UK National Insurance Numbers (NINO)
  - in:   Indian Aadhaar numbers (Verhoeff checked)
  - br:   Brazilian CPF numbers (check digits verified)
  - nl:   Dutch BSN numbers (11-proof checked, label on the line)

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
    parser.add_argument(
        "--regions",
        type=str,
        help="Optional: comma-separated PII region packs to enable (default: all), e.g. us,iban,in",
    )
    args = parser.parse_args()

    try:
        regions = None if not args.regions else [r.strip().lower() for r in args.regions.split(",") if r.strip()]
        active_patterns = select_patterns(regions)
    except ValueError as e:
        print(f"\n[ERROR] {e}. Known packs: {', '.join(sorted(PII_REGION_PACKS))}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 2. FILE VALIDATION & GUARDRAILS
    # -------------------------------------------------------------------------
    target_path = Path(args.target).resolve()
    if not target_path.exists() or not target_path.is_file():
        print(f"\n[ERROR] Target file does not exist or is not a file: {target_path}")
        sys.exit(1)

    out_dir = Path(args.out).resolve() if args.out else target_path.parent

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
    histograms = {kw: defaultdict(int) for kw in active_patterns}

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
                for pii_type in find_pii(line, active_patterns):
                    # Only decode the line if a physical hit is detected to save CPU cycles
                    if not hit_found:
                        decoded_line = line.decode("utf-8", errors="ignore").strip()
                        safe_line = mask_pii(decoded_line)
                        f_out.write(f"[{pii_type}] {safe_line}\n")
                        hit_found = True  # Prevent duplicate writes if a line has multiple PII types

                    ts_match = ts_pattern.search(line)
                    bucket = ts_match.group(1).decode("utf-8", errors="ignore") + ":00" if ts_match else "Unknown Time"
                    histograms[pii_type][bucket] += 1
    except OSError as e:
        print(f"\n[FATAL ERROR] I/O failure during streaming: {e}")
        sys.exit(1)

    time_elapsed = time.time() - start_time

    # -------------------------------------------------------------------------
    # 4. REPORTING & DASHBOARDS
    # -------------------------------------------------------------------------
    for kw in active_patterns:
        draw_ascii_histogram(histograms[kw], kw)

    total_counts = {kw: sum(buckets.values()) for kw, buckets in histograms.items()}
    max_total = max(total_counts.values()) if total_counts.values() else 0

    print("\n" + "=" * 75)
    print(" PII DATA LEAK HUNTER: SCAN SUMMARY")
    print("=" * 75)

    if max_total > 0:
        for kw, count in total_counts.items():
            bar_len = int((count / max_total) * 30)
            bar = "█" * max(1, bar_len) if count > 0 else ""
            print(f" {kw.ljust(15)} | {bar} ({count:,} hits)")
    else:
        print(" [SUCCESS] Clean scan. No national IDs, bank accounts, credit cards, or AWS keys detected.")

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
