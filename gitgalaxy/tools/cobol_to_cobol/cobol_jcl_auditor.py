#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Zero-Trust JCL Auditor
#
# PURPOSE:
# Compares generated Cloud JCLs against original IBM legacy JCLs to calculate
# exact code reduction and quantify the shedding of over-permissioned I/O.
#
# ARCHITECTURAL DECISION:
# Over decades, mainframe Job Control Language (JCL) scripts accumulate "ghost" 
# Data Definition (DD) statements—files that are allocated to a job step but 
# never actually opened or utilized by the compiled COBOL program. This violates 
# the principle of least privilege. This auditor mathematically proves the 
# security posture of the modernized architecture by comparing the legacy 
# footprint against the newly generated, zero-trust equivalents.
# ==============================================================================
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any

SYSTEM_DDS = {
    "STEPLIB",
    "SYSOUT",
    "SYSPRINT",
    "SYSUDUMP",
    "SYSIN",
    "CEEDUMP",
    "DFHCSD",
    "IGZDDOP",
}
SYSTEM_PGMS = {
    "IEFBR14",
    "IEWL",
    "ASMA90",
    "IGYCRCTL",
    "IGYWC",
    "HEWL",
    "IDCAMS",
    "IEBGENER",
}


def parse_jcl_intent(filepath: Path) -> dict:
    """Parses a JCL file to extract its raw execution and dataset allocation intent."""
    metrics = {"lines_of_code": 0, "exec_pgms": set(), "data_definitions": set()}
    pgm_pattern = re.compile(r"EXEC\s+(?:PGM=)?([A-Z0-9@#$\-]+)", re.IGNORECASE)
    dd_pattern = re.compile(r"^//([A-Z0-9@#$\-]+)\s+DD\s+", re.IGNORECASE)

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//*"):
                    continue
                metrics["lines_of_code"] += 1

                pgm_match = pgm_pattern.search(line)
                if pgm_match:
                    pgm = pgm_match.group(1).upper()
                    if pgm not in SYSTEM_PGMS:
                        metrics["exec_pgms"].add(pgm)

                dd_match = dd_pattern.search(line)
                if dd_match:
                    dd_name = dd_match.group(1).upper()
                    if dd_name not in SYSTEM_DDS:
                        metrics["data_definitions"].add(dd_name)
    except Exception:
        pass
    return metrics


def audit_zero_trust_jcls(generated_dir: Path, original_dir: Path) -> dict:
    """Core logic to calculate architectural bloat and privilege reduction metrics."""
    legacy_jcls = list(original_dir.rglob("*.[jJ][cC][lL]")) + list(original_dir.rglob("*.txt"))
    legacy_map: Dict[str, Any] = {}

    # 1. Map Legacy JCLs by Intent (Handling multi-step monoliths)
    for lj in legacy_jcls:
        if generated_dir in lj.parents:
            continue
        metrics = parse_jcl_intent(lj)
        for pgm in metrics["exec_pgms"]:
            # If multiple legacy JCLs call the same program, keep the biggest one
            if pgm not in legacy_map or metrics.get("lines_of_code", 0) > legacy_map[pgm].get("lines_of_code", 0):
                legacy_map[pgm] = {"file": lj, "metrics": metrics}

    # 2. Compare against Generated (Zero-Trust) JCLs
    generated_files = list(generated_dir.glob("*.jcl"))
    report = {
        "audited": 0,
        "original_loc": 0,
        "forged_loc": 0,  # Maintained key for downstream DB compatibility
        "excess_dds_blocked": 0,
        "program_breakdown": {},
    }

    for generated_file in generated_files:
        generated_metrics = parse_jcl_intent(generated_file)
        if not generated_metrics["exec_pgms"]:
            continue

        pgm_name = list(generated_metrics["exec_pgms"])[0]

        if pgm_name in legacy_map:
            twin_metrics = legacy_map[pgm_name]["metrics"]

            loc_saved = max(0, twin_metrics["lines_of_code"] - generated_metrics["lines_of_code"])
            
            # The exact number of datasets allocated in legacy but stripped from modern
            excess_dds = max(
                0,
                len(twin_metrics["data_definitions"] - generated_metrics["data_definitions"]),
            )

            report["audited"] += 1
            report["original_loc"] += twin_metrics["lines_of_code"]
            report["forged_loc"] += generated_metrics["lines_of_code"]
            report["excess_dds_blocked"] += excess_dds

            report["program_breakdown"][pgm_name] = {
                "loc_saved": loc_saved,
                "io_blocked": excess_dds,
                "legacy_file": legacy_map[pgm_name]["file"].name,
            }

    if report["original_loc"] > 0:
        report["bloat_reduction_pct"] = round(
            ((report["original_loc"] - report["forged_loc"]) / report["original_loc"]) * 100,
            1,
        )
    else:
        report["bloat_reduction_pct"] = 0.0

    return report


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Zero-Trust JCL Auditor")

    parser = argparse.ArgumentParser(description="GitGalaxy Zero-Trust JCL Auditor")
    parser.add_argument("generated", help="Directory containing the modernized GitGalaxy JCLs")
    parser.add_argument("legacy", help="Directory containing the original legacy IBM JCLs")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of a formatted terminal report",
    )

    args = parser.parse_args()
    generated_path = Path(args.generated).resolve()
    legacy_path = Path(args.legacy).resolve()

    if not generated_path.exists() or not legacy_path.exists():
        print("\n[!] ERROR: One or both directories do not exist.")
        sys.exit(1)

    # Run the audit
    report = audit_zero_trust_jcls(generated_path, legacy_path)

    # Output routing
    if args.json:
        print(json.dumps(report, indent=2))
        sys.exit(0)

    # CLI Terminal Output
    print("\n==============================================================")
    print(" 🛡️  GitGalaxy Tool: Zero-Trust JCL Auditor")
    print("==============================================================")
    print(f" [*] Modernized Dir : {generated_path.name}")
    print(f" [*] Legacy Root    : {legacy_path.name}")
    print("--------------------------------------------------------------")

    if report["audited"] == 0:
        print(" [!] No matching execution intents found between the directories.")
        print("     Ensure your generated JCLs share PROGRAM-IDs with the legacy corpus.")
    else:
        print(" PROGRAM BREAKDOWN:")
        for pgm, data in report["program_breakdown"].items():
            loc = str(data["loc_saved"]).rjust(4)
            io = str(data["io_blocked"]).rjust(2)
            print(f"  [+] {pgm.ljust(10)} | LOC Saved: {loc} | I/O Blocked: {io} | Ref: {data['legacy_file']}")

        print("--------------------------------------------------------------")
        print(" 📊 FINAL AUDIT METRICS:")
        print(f"  > Programs Audited       : {report['audited']}")
        print(f"  > Original Legacy LOC    : {report['original_loc']}")
        print(f"  > GitGalaxy Zero-Trust LOC: {report['forged_loc']}")
        print(f"  > Bloat Reduction        : {report['bloat_reduction_pct']}%")
        print(f"  > Over-Permissioned I/O  : {report['excess_dds_blocked']} Dataset Boundaries Shed")

    print("==============================================================\n")


if __name__ == "__main__":
    main()