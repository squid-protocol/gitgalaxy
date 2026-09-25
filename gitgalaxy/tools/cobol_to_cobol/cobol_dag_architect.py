#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Data Lineage DAG Architect
#
# PURPOSE:
# Parses COBOL structural intent to map INPUT/OUTPUT data flows and calculates
# the deterministic topological execution order.
#
# ARCHITECTURAL DECISION:
# In legacy mainframe environments, execution order is manually dictated by JCL.
# During cloud modernization, we must programmatically derive this order to
# generate modern orchestration pipelines (e.g., Spring Batch, Airflow). By
# statically analyzing SELECT/ASSIGN clauses and OPEN statements, we build a
# Directed Acyclic Graph (DAG) of data dependencies, ensuring programs execute
# in the exact order required by their physical dataset inputs and outputs.
# ==============================================================================
import argparse
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import _blank_literals, unit_header

_OPEN_MODES = frozenset({"INPUT", "OUTPUT", "I-O", "EXTEND"})
# #3222: anchor only. The operand run used to be `[^.]*\.` inside the pattern,
# which rescans to the next period from every OPEN -- the #3205 shape. The run
# is now sliced with str.find, which visits each character once.
# #3420: `(?<![A-Z0-9-])`, not `\b`: COBOL words run through hyphens, so `\b`
# matched `END-CALL` / `3200-INSERT-IMS-CALL` as the CALL verb.
_V = r"(?<![A-Z0-9\-])"
_OPEN_ANCHOR = re.compile(rf"{_V}OPEN\s+(?=(?:INPUT|OUTPUT|I-O|EXTEND)\b)")
_DYNAMIC_CALL = re.compile(rf"{_V}CALL\s+(?![\'\"])([A-Z0-9\-]+)")
_SELECT = re.compile(rf"{_V}SELECT\s+([A-Z0-9\-]+)\s+ASSIGN\s+(?:TO\s+)?([A-Z0-9@#$\-]+)")
# A COBOL user-defined word contains a letter; a digits-only token after
# `PROGRAM-ID.` is a sequence number (#3418's shape).
_PROGRAM_ID = re.compile(r"PROGRAM-ID\.\s+([0-9\-]*[A-Z@#$][A-Z0-9@#$\-]*)")


def code_view(content: str) -> str:
    """The source as code only, line for line (#3420). Comment and debug lines
    (column 7 `*`, `/`, `D`) become empty, the cols 1-6 sequence area becomes
    blanks, cols 73-80 are dropped, and literal contents are blanked, so a
    commented-out `*CALL MENU PROGRAM`, a `DISPLAY 'GNP CALL FAILED'`, a
    commented `SELECT ... ASSIGN` / `OPEN OUTPUT`, or a sequence number is never
    read as code. Line count and the column of every kept character are
    preserved, so unit_header still finds Area-A headers."""
    out = []
    for line in content.split("\n"):
        if len(line) > 6 and line[6] in "*/D":
            out.append("")
            continue
        line = line[:72]
        if len(line) >= 6:
            line = " " * 6 + line[6:]
        out.append(_blank_literals(line))
    return "\n".join(out)


def extract_lineage(filepath: Path, dead_paras: Optional[set] = None) -> Optional[dict]:
    """
    Analyzes a COBOL program to map internal variables to external physical files.
    Utilizes shared IR state to mask out unreachable logic and prevent hallucinated dependencies.
    """
    if dead_paras is None:
        dead_paras = set()

    try:
        content = code_view(filepath.read_text(encoding="utf-8", errors="ignore").upper())
    except Exception:
        return None

    # 1. Extract the permanent PROGRAM-ID
    prog_match = _PROGRAM_ID.search(content)
    if not prog_match:
        return None
    program_id = prog_match.group(1)

    # 2. Map internal file variables to physical external boundaries (DD Names)
    file_map = {}
    for match in _SELECT.finditer(content):
        raw_dd = match.group(2)
        clean_dd = re.sub(r"^(?:UT|UR)-S-", "", raw_dd)
        file_map[match.group(1)] = clean_dd

    inputs = set()
    outputs = set()

    # ==========================================================================
    # DEFENSIVE DESIGN (UNREACHABLE LOGIC MASKING):
    # COBOL programs often contain legacy, unreachable paragraphs. If we allow
    # the regex engine to scan these abandoned blocks, it will extract 'OPEN'
    # statements for files that are never actually utilized at runtime, creating
    # false dependencies. We mask out known dead paragraphs with spaces to
    # preserve the exact logic topology without triggering regex false positives.
    # ==========================================================================
    # #3533: `PROCEDURE        DIVISION.` (navikt/DSF PLUKKFR) is the same header.
    content = re.sub(r"PROCEDURE[ \t]+DIVISION", "PROCEDURE DIVISION", content)
    if "PROCEDURE DIVISION" in content:
        parts = content.split("PROCEDURE DIVISION")
        data_div = parts[0]
        proc_div = parts[1]

        active_proc_lines = []
        current_paragraph = "MAIN-ENTRY"

        # Each line belongs to the most recent paragraph or section header, found
        # exactly as the graveyard finds the units it marks dead. Line 0 is the rest
        # of the PROCEDURE DIVISION header, never a unit.
        for i, line in enumerate(proc_div.split("\n")):
            header = unit_header(line) if i else None
            if header:
                current_paragraph = header

            # If the paragraph is dead, we replace its characters with spaces
            if current_paragraph in dead_paras:
                active_proc_lines.append(" " * len(line))
            else:
                active_proc_lines.append(line)

        safe_content = data_div + "PROCEDURE DIVISION\n" + "\n".join(active_proc_lines)
    else:
        safe_content = content

    # 3. Extract exact Functional Intent (OPEN INPUT vs OPEN OUTPUT)
    # We run this on the safe_content where unreachable logic is invisible.
    # One OPEN can carry several modes (`OPEN INPUT A B OUTPUT C D.`), so the
    # operand list is walked and the mode switches at each mode keyword (#3204).
    consumed = 0
    for match in _OPEN_ANCHOR.finditer(safe_content):
        # Keep the old pattern's non-overlapping scan: an anchor inside the
        # operand run of a statement we already read is not a second OPEN.
        if match.start() < consumed:
            continue
        stop = safe_content.find(".", match.end())
        if stop == -1:
            # `[^.]*\.` required the terminator, so an unterminated tail matched
            # nothing. Unchanged here.
            continue
        consumed = stop + 1
        mode = None
        for internal_file in safe_content[match.end() : stop].replace(",", " ").split():
            if internal_file in _OPEN_MODES:
                mode = internal_file
            elif internal_file in file_map:
                physical_file = file_map[internal_file]
                # I-O and EXTEND require the file to exist (Input) but also mutate it (Output)
                if mode in ("INPUT", "I-O", "EXTEND"):
                    inputs.add(physical_file)
                if mode in ("OUTPUT", "I-O", "EXTEND"):
                    outputs.add(physical_file)

    # ==========================================================================
    # ARCHITECTURAL ANOMALY DETECTION (DYNAMIC CALLS):
    # A standard CALL followed by string quotes is a static, deterministic
    # dependency. A CALL utilizing a variable is dynamic, making the
    # compilation-time DAG incomplete. We flag these for architectural review.
    # ==========================================================================
    dynamic_calls = set()
    for match in _DYNAMIC_CALL.finditer(safe_content):
        dynamic_calls.add(match.group(1))

    return {
        "program_id": program_id,
        "inputs": inputs,
        "outputs": outputs,
        "unresolved_calls": sorted(dynamic_calls),  # a set: sorted so the IR is hash-seed independent (#3212)
    }


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("DAG Architect (Data Lineage)")

    parser = argparse.ArgumentParser(description="GitGalaxy DAG Architect v3")
    parser.add_argument("target", help="Directory containing legacy COBOL payloads")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🕸️ GitGalaxy Data Lineage Architect mapping execution topology in: {target_path.name}...\n")

    cobol_files = list(target_path.rglob("*.cbl")) + list(target_path.rglob("*.cob"))

    programs = []
    for f in cobol_files:
        # In standalone CLI mode, it defaults to an empty set for dead_paras
        lineage = extract_lineage(f)
        if lineage and (lineage["inputs"] or lineage["outputs"]):
            programs.append(lineage)

    # Map which programs create which physical files
    file_creators = defaultdict(set)
    for p in programs:
        for out_file in p["outputs"]:
            file_creators[out_file].add(p["program_id"])

    # Build the Dependency Graph
    dependencies = defaultdict(set)
    dependents = defaultdict(set)
    in_degree = {p["program_id"]: 0 for p in programs}

    for p in programs:
        pid = p["program_id"]
        for in_file in p["inputs"]:
            # If a file this program needs is created by another program in this cluster...
            if in_file in file_creators:
                for creator in file_creators[in_file]:
                    if creator != pid:  # Program doesn't depend on itself
                        dependencies[pid].add(creator)
                        dependents[creator].add(pid)

    # Calculate in-degrees
    for pid in dependencies:
        in_degree[pid] = len(dependencies[pid])

    # --- Kahn's Algorithm for Topological Sort ---
    queue = deque([pid for pid, deg in in_degree.items() if deg == 0])
    execution_order = []

    while queue:
        current = queue.popleft()
        execution_order.append(current)

        for dependent in dependents[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # --- Presentation ---
    print("==========================================================")
    print(" ⚡ DETERMINISTIC EXECUTION PIPELINE (TOPOLOGICAL SORT)")
    print("==========================================================\n")

    if len(execution_order) != len(programs):
        print(" ⚠️ WARNING: Cyclic Dependency Detected! Pipeline locked.")
        # Identify the cycle for the user
        stuck_nodes = [pid for pid, deg in in_degree.items() if deg > 0]
        print(f"    ↳ Deadlocked Programs: {', '.join(stuck_nodes)}")
        sys.exit(1)

    for step, pid in enumerate(execution_order, 1):
        prog_data = next((p for p in programs if p["program_id"] == pid), None)
        in_files = ", ".join(prog_data["inputs"]) if prog_data["inputs"] else "None"
        out_files = ", ".join(prog_data["outputs"]) if prog_data["outputs"] else "None"

        print(f" STEP {step:02d}: Run [{pid}]")
        print(f"          ↳ Reads : {in_files}")
        print(f"          ↳ Writes: {out_files}")
        print("-" * 58)


if __name__ == "__main__":
    main()
