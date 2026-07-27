#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Microservice Logic Extractor
#
# PURPOSE:
# Recursive taint-tracking and business rule extraction for legacy COBOL.
# Utilizes in-memory IR state (RAM) to bypass unreachable logic blocks.
#
# ARCHITECTURAL DECISION:
# Legacy COBOL programs are typically monolithic, making it difficult to
# extract specific business rules for microservice decomposition. This
# extractor performs data flow taint-tracking starting from a target
# variable, mapping its aliases through MOVE, ADD, and COMPUTE statements.
# By integrating with the Deprecated Trails Analyzer's IR state, it
# guarantees that extracted logic only comes from mathematically reachable
# execution paths, eliminating false-positive business rules.
# ==============================================================================
import argparse
import re
import sys
from pathlib import Path
from typing import Optional


def slice_business_logic(
    filepath: Path, initial_var: str, dead_paras: Optional[set] = None, orphaned_vars: Optional[set] = None
):
    """
    Recursively tracks a variable and its aliases through the AST.
    Utilizes shared IR context to prevent mapping logic inside unreachable code.
    """
    if dead_paras is None:
        dead_paras = set()
    if orphaned_vars is None:
        orphaned_vars = set()

    initial_var = initial_var.upper()

    # ==========================================================================
    # DEFENSIVE DESIGN (UNUSED MEMORY ABORT):
    # If the target variable is already known to be dead memory from the
    # Deprecated Trails Analyzer, we can abort the slice immediately. It has
    # no active business logic associated with it.
    # ==========================================================================
    if initial_var in orphaned_vars:
        return [], {initial_var: "ORPHANED_MEMORY"}

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore").upper()
    except Exception:
        return None

    if "PROCEDURE DIVISION" not in content:
        return None

    proc_div = content.split("PROCEDURE DIVISION")[1]
    lines = proc_div.split("\n")

    tainted_vars = {initial_var}
    para_pattern = re.compile(r"^[ \t]{0,7}([A-Z0-9\-]+)\.[ \t]*$")

    # ==========================================================================
    # PASS 1: Recursive Taint Mapping (Data Flow Engine)
    # ==========================================================================
    # We loop 3 times to catch chained aliases (e.g., A -> B -> C)
    for _ in range(3):
        current_paragraph = "MAIN-ENTRY"
        for line in lines:
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("*"):
                continue

            # Update current paragraph context
            para_match = para_pattern.match(line)
            if para_match:
                current_paragraph = para_match.group(1)
                continue

            # ==================================================================
            # DEFENSIVE DESIGN (UNREACHABLE LOGIC MASKING):
            # If the orchestrator's IR state tells us this paragraph is unreachable,
            # we skip it. This prevents deprecated code from creating false-positive taints.
            # ==================================================================
            if current_paragraph in dead_paras:
                continue

            # Match assignments: MOVE A TO B, ADD A TO B, SUBTRACT A FROM B
            match = re.search(
                r"(?:MOVE|ADD|SUBTRACT)\s+([A-Z0-9\-]+)\s+(?:TO|FROM)\s+([A-Z0-9\-]+)",
                clean_line,
            )
            if match:
                var1, var2 = match.group(1), match.group(2)
                # If either variable is tainted, taint the other
                if var1 in tainted_vars or var2 in tainted_vars:
                    tainted_vars.add(var1)
                    tainted_vars.add(var2)

            # Match math formulas: COMPUTE X = Y * Z
            comp_match = re.search(r"COMPUTE\s+([A-Z0-9\-]+)\s*=", clean_line)
            if comp_match:
                var1 = comp_match.group(1)
                vars_in_eq = re.findall(r"([A-Z][A-Z0-9\-]+)", clean_line.split("=")[1])
                # Taint forwards and backwards!
                if var1 in tainted_vars or any(v in tainted_vars for v in vars_in_eq):
                    tainted_vars.add(var1)
                    tainted_vars.update(vars_in_eq)

    # ==========================================================================
    # PASS 2: Logic Extraction
    # ==========================================================================
    extracted_logic = []
    current_paragraph = "MAIN-ENTRY"

    for i, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("*"):
            continue

        para_match = para_pattern.match(line)
        if para_match:
            current_paragraph = para_match.group(1)
            continue

        # ======================================================================
        # DEFENSIVE DESIGN (EXTRACTION SHIELD):
        # Do not extract text from paragraphs that are mathematically unreachable.
        # ======================================================================
        if current_paragraph in dead_paras:
            continue

        # TAINT CHECK: If ANY tainted variable is on this line, extract it
        if any(var in clean_line for var in tainted_vars):
            extracted_logic.append(
                {
                    "line_num": i + 1,
                    "paragraph": current_paragraph,
                    "statement": clean_line,
                }
            )

    return extracted_logic, tainted_vars


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Microservice Logic Extractor")

    parser = argparse.ArgumentParser(description="GitGalaxy Microservice Logic Extractor v3")
    parser.add_argument("target", help="Path to a .cbl file to slice")
    parser.add_argument("--var", required=True, help="The target variable to track")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🔪 GitGalaxy Logic Extractor tracing dependencies for [{args.var.upper()}] in {target_path.name}...\n")

    # When run in standalone CLI mode, it won't have the IR RAM context,
    # but the function signature safely defaults to empty sets.
    result = slice_business_logic(target_path, args.var)

    if not result:
        print(f"⚠️ Variable {args.var.upper()} is never mutated in the PROCEDURE DIVISION.")
        sys.exit(0)

    logic_slice, aliases = result

    if isinstance(aliases, dict) and "ORPHANED_MEMORY" in aliases.values():
        print("==========================================================")
        print(f" 🪦 ABORTED: Variable [{args.var.upper()}] is mathematically dead memory.")
        print("==========================================================")
        sys.exit(0)

    print("==========================================================")
    print(f" 🧬 TAINTS FOUND: {', '.join(aliases)}")
    print("==========================================================")

    current_p = ""
    for item in logic_slice:
        if item["paragraph"] != current_p:
            print(f"\n[{item['paragraph']}]")
            current_p = item["paragraph"]

        print(f"  Line {item['line_num']:04d} | {item['statement']}")

    print("\n==========================================================")
    print(f" 🎯 Extracted {len(logic_slice)} distinct business rules.")
    print("==========================================================\n")


if __name__ == "__main__":
    main()
