#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: MVS 3.8j COBOL Compiler Scaffolding
#
# PURPOSE:
# Dynamically generates the mainframe build JCL based on the detected COBOL
# dialect (74 vs 85) to ensure deterministic legacy compilation.
#
# ARCHITECTURAL DECISION:
# Legacy compilers are highly sensitive to dialect constraints. Feeding modern
# COBOL-85 structural signatures (like EVALUATE or END-IF) into an OS/VS COBOL-74
# compiler will trigger catastrophic compilation failures. This module inspects
# the extracted source logic, detects the era-specific dialect, and automatically
# routes the build sequence to the correct enterprise compiler (COBUCL vs IGYWCL).
# ==============================================================================
import argparse
import re
import sys
from pathlib import Path

# Execution constraint to prevent resource starvation from cyclic copybooks
MAX_RECURSION_DEPTH = 10


def detect_cobol_dialect(content: str) -> str:
    """Scans for post-1974 structural signatures to determine the compiler era."""
    modern_signatures = re.compile(
        r"\b(EVALUATE|INITIALIZE|END-IF|END-PERFORM|END-READ|END-EVALUATE|CONTINUE)\b|\*>",
        re.IGNORECASE,
    )
    if modern_signatures.search(content):
        return "COBOL-85"
    return "COBOL-74"


def flatten_copybooks(source_text: str, base_dir: Path, current_depth: int = 0) -> str:
    """
    Recursively inlines COPY statements to create a self-contained execution payload.
    """
    # ==========================================================================
    # DEFENSIVE DESIGN (RECURSION LIMITER):
    # Legacy architectures frequently contain cyclic dependencies (e.g., Copybook A
    # imports Copybook B, which imports Copybook A). Without a strict recursion
    # depth limit, this resolution function will trap the CPU in an infinite loop,
    # triggering an Out-Of-Memory (OOM) pipeline collapse.
    # ==========================================================================
    if current_depth > MAX_RECURSION_DEPTH:
        print(f"  [!] WARNING: Copybook recursion depth ({MAX_RECURSION_DEPTH}) exceeded. Aborting cyclic branch.")
        return source_text

    lines = source_text.replace("\r", "").split("\n")
    out_lines = []

    for line in lines:
        upper_line = line.upper()
        # Ignore lines that are commented out (asterisk in column 7)
        if "COPY " in upper_line and not (len(line) > 6 and line[6] == "*"):
            match = re.search(r'COPY\s+[\'"]?([A-Z0-9\-_]+)[\'"]?\.?', upper_line)
            if match:
                copy_name = match.group(1)
                copy_file = next(base_dir.rglob(f"{copy_name}.cpy"), None)
                if not copy_file:
                    copy_file = next(base_dir.rglob(f"{copy_name}.cbl"), None)

                if copy_file:
                    out_lines.append(f"      * --- INLINED COPYBOOK: {copy_name} ---")

                    # Pass current_depth + 1 into the recursive call to advance the safety counter
                    inlined_text = flatten_copybooks(
                        copy_file.read_text(errors="ignore"),
                        base_dir,
                        current_depth + 1,
                    )

                    out_lines.extend(inlined_text.split("\n"))
                    out_lines.append(f"      * --- END COPYBOOK: {copy_name} ---")
                    continue
                else:
                    out_lines.append(f"      * [!] WARNING: COPYBOOK {copy_name} NOT LOCATED IN REPOSITORY BOUNDS")

        out_lines.append(line)

    return "\n".join(out_lines)


def extract_intent(source_text: str) -> tuple:
    """Extracts the program identity and file assignment boundaries."""
    prog_id = "UNKNOWN"
    id_match = re.search(r"PROGRAM-ID\.\s+([A-Z0-9\-]+)\.", source_text, re.IGNORECASE)
    if id_match:
        prog_id = id_match.group(1).strip()

    file_matches = re.finditer(
        r"SELECT\s+[A-Z0-9\-]+\s+ASSIGN\s+TO\s+([A-Z0-9\-]+)",
        source_text,
        re.IGNORECASE,
    )
    files = {m.group(1).strip() for m in file_matches}
    return prog_id, files


def generate_build_jcl(source_text: str, prog_name: str, files: set, dialect: str) -> str:
    """Generates the JCL deployment configuration mapping program files to physical data sets."""
    jcl = []
    job_name = f"BLD{prog_name[:4].upper()}"
    jcl.append(f"//{job_name} JOB (12345),'GITGALAXY COMPILER',")
    jcl.append("//             CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1),")
    jcl.append("//             USER=HERC01,PASSWORD=CUL8TR")

    jcl.append("//* ==========================================================")
    jcl.append("//* PHASE 1: INFRASTRUCTURE PROVISIONING (IEFBR14)")
    jcl.append("//* ==========================================================")
    jcl.append("//ALLOC EXEC PGM=IEFBR14")

    jcl.append("//LOADLIB  DD DSN=HERC01.LOADLIB,DISP=(MOD,CATLG,DELETE),")
    jcl.append("//            UNIT=SYSDA,SPACE=(CYL,(5,5,10)),")
    jcl.append("//            DCB=(RECFM=U,BLKSIZE=32760,DSORG=PO)")

    for f in files:
        clean_f = f.upper().strip()
        # 1. Strip IBM prefixes first
        clean_f = re.sub(r"^(?:UT|UR)-S-", "", clean_f)
        # 2. Strip non-alphanumeric characters
        clean_f = re.sub(r"[^A-Z0-9]", "", clean_f)
        # 3. Enforce 8-character Mainframe limit
        if len(clean_f) > 8:
            clean_f = clean_f[-8:]

        if clean_f:
            jcl.append(f"//{clean_f} DD DSN=HERC01.DATA.{clean_f},DISP=(MOD,CATLG,DELETE),")
            jcl.append("//            UNIT=SYSDA,SPACE=(TRK,(10,10),RLSE),")
            jcl.append("//            DCB=(LRECL=80,RECFM=FB,BLKSIZE=800)")

        if clean_f:
            jcl.append(f"//{clean_f} DD DSN=HERC01.DATA.{clean_f},DISP=(MOD,CATLG,DELETE),")
            jcl.append("//            UNIT=SYSDA,SPACE=(TRK,(10,10),RLSE),")
            jcl.append("//            DCB=(LRECL=80,RECFM=FB,BLKSIZE=800)")

    jcl.append("//* ==========================================================")
    jcl.append("//* PHASE 2: IBM COMPILER & LINKAGE EDITOR")
    jcl.append("//* ==========================================================")

    # --- DIALECT ROUTING ---
    if dialect == "COBOL-85":
        jcl.append("//* 🚨 DIALECT SENSOR: COBOL-85+ DETECTED 🚨")
        jcl.append("//* ROUTING TO MODERN ENTERPRISE COMPILER (IGYWCL)")
        jcl.append("//COMPILE  EXEC IGYWCL")
    else:
        jcl.append("//* 🟢 DIALECT SENSOR: COBOL-74 DETECTED")
        jcl.append("//* ROUTING TO LEGACY OS/VS COMPILER (COBUCL)")
        jcl.append("//COMPILE  EXEC COBUCL")

    jcl.append("//COB.SYSIN DD *")
    jcl.extend(source_text.rstrip().split("\n"))
    jcl.append("/*")

    jcl.append("//* ==========================================================")
    jcl.append("//* PHASE 3: SAVE BINARY MODULE TO HERC01.LOADLIB")
    jcl.append("//* ==========================================================")
    jcl.append("//LKED.SYSLIB  DD DSN=SYS1.COBLIB,DISP=SHR")
    jcl.append(f"//LKED.SYSLMOD DD DSN=HERC01.LOADLIB({prog_name}),DISP=SHR")
    jcl.append("//")

    return "\n".join(jcl)


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("MVS 3.8j COBOL Compiler Scaffolding")

    parser = argparse.ArgumentParser(description="GitGalaxy COBOL Compiler Scaffolding")
    parser.add_argument("source_dir", help="Path to the original COBOL source files")
    parser.add_argument("out_dir", help="Path to save the generated Compiler JCLs")
    args = parser.parse_args()

    src_path = Path(args.source_dir).resolve()
    out_path = Path(args.out_dir).resolve()
    if not src_path.exists():
        sys.exit(1)
    out_path.mkdir(parents=True, exist_ok=True)

    cobol_files = [f for f in src_path.rglob("*.cbl") if "PROGRAM-ID" in f.read_text(errors="ignore").upper()]

    print("\n" + "=" * 70)
    print(" 🏗️  GITGALAXY MAINFRAME COMPILER GENERATOR (PRE-COMPILER ACTIVE)")
    print("=" * 70)

    for file_path in cobol_files:
        try:
            raw_text = file_path.read_text(encoding="utf-8", errors="ignore")

            # 1. Flatten the copybooks
            flattened_source = flatten_copybooks(raw_text, src_path)

            # 2. Detect the dialect
            dialect = detect_cobol_dialect(flattened_source)

            # 3. Generate the JCL based on the detected era
            prog_name, expected_files = extract_intent(flattened_source)
            jcl_payload = generate_build_jcl(flattened_source, prog_name, expected_files, dialect)

            output_file = out_path / f"BUILD_{prog_name}.jcl"
            output_file.write_text(jcl_payload, encoding="utf-8")

            print(f"  [+] Generated {dialect} Pipeline : {output_file.name}")
        except Exception as e:
            print(f"  [!] Failed to process {file_path.name}: {e}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
