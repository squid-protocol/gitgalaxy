#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Deprecated Trails Analyzer
#
# PURPOSE:
# Static Analysis of COBOL structural signatures to isolate unused memory
# declarations and mathematically unreachable execution logic.
#
# ARCHITECTURAL DECISION:
# Legacy COBOL architectures frequently suffer from "code rot" where memory
# addresses (Data Division) and execution blocks (Procedure Division) are
# abandoned but never removed by cautious developers. This analyzer prevents
# migrating this dead weight to the cloud by statically mapping actual execution
# usage against declarations, shedding unnecessary state flux and cognitive load.
# ==============================================================================
import argparse
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Copybook members are found by stem. .cbl/.cob are allowed because some shops keep
# copybooks under program extensions, but a member with a PROGRAM-ID is a program
# and is never inlined (#3203: `COPY ACCTCTRL` used to inline ACCTCTRL.cbl).
_COPYBOOK_EXTS = (".cpy", ".copy", ".cbl", ".cob")
_PROGRAM_ID = re.compile(r"\bPROGRAM-ID\b", re.IGNORECASE)

# Fixed-format sequence area (cols 1-6, blanks or a sequence field) + indicator (col 7).
_SEQ_AREA = r"(?:[^\n]{6} )?"

# Scope terminators and verbs that can stand alone on a line ending in a period.
# None of these can name a paragraph (#3203 defect 1).
_NOT_A_PARAGRAPH = re.compile(r"END-[A-Z0-9\-]+|GOBACK|EXIT|CONTINUE|STOP|DECLARATIVES")

# Matches: COPY NAME. or COPY NAME REPLACING ==A== BY ==B==., with or without
# a sequence field in cols 1-6 (`R2     COPY SAM2PARM.`).
COPY_PATTERN = re.compile(
    "^" + _SEQ_AREA + r'[ \t]*COPY\s+[\'"]?([A-Z0-9_\-]+)[\'"]?(?:\s+REPLACING\s+(.+?))?\.',
    re.MULTILINE | re.IGNORECASE,
)

# A fixed-format paragraph header: name starts in Area A (cols 8-11), alone on its line.
_FIXED_PARA = re.compile(r"^[^\n]{6} {1,4}([A-Z0-9][A-Z0-9\-]*)\.[ \t]*$", re.MULTILINE)


@lru_cache(maxsize=8)
def _copybook_index(root: Path) -> dict[str, list[Path]]:
    """Maps an upper-cased member stem to every copybook candidate under `root`.

    Cached: the refractor resolves every program of a repository against the same root.
    """
    index: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if path.suffix.lower() in _COPYBOOK_EXTS and path.is_file():
            index.setdefault(path.stem.upper(), []).append(path)
    return index


def _nearest(candidates: list[Path], origin: Path) -> list[Path]:
    """Orders candidates by how many leading path parts they share with `origin`, then by path."""

    def shared(p: Path) -> int:
        n = 0
        for a, b in zip(p.parent.parts, origin.parent.parts):
            if a != b:
                break
            n += 1
        return n

    return sorted(candidates, key=lambda p: (-shared(p), p.suffix.lower() != ".cpy", str(p)))


def find_copybook(name: str, copybook_root: Path, origin: Path) -> Optional[Path]:
    """The member `COPY name` resolves to: searched under `copybook_root` (the
    repository, not just the program's directory: real layouts keep copybooks in
    COPYBOOK/ or cobol_copy/), nearest to `origin` first, never a program (#3203)."""
    for candidate in _nearest(_copybook_index(copybook_root).get(name.upper(), []), origin):
        if not _PROGRAM_ID.search(candidate.read_text(encoding="utf-8", errors="ignore")):
            return candidate
    return None


def paragraph_headers(proc_div: str) -> list[str]:
    """Paragraph names of an upper-cased PROCEDURE DIVISION, in source order.

    A header is a lone `NAME.` whose name starts in Area A (cols 8-11). A lone
    `NAME.` deeper in Area B is the last line of a multi-line statement or a scope
    terminator (`END-IF.`, `GOBACK.`), not a paragraph (#3203 defect 1). Cols 1-6
    may carry a sequence field (defect 4).

    `proc_div` is the text after `PROCEDURE DIVISION`; the rest of that header line
    (` USING DFHCOMMAREA.`) is skipped, or its operand would read as the entry paragraph.
    """
    body = proc_div.split("\n", 1)[1] if "\n" in proc_div else ""
    return [p for p in _FIXED_PARA.findall(body) if not _NOT_A_PARAGRAPH.fullmatch(p)]


def resolve_copybooks(
    content: str,
    source_path: Path,
    copybook_root: Optional[Path] = None,
    origin: Optional[Path] = None,
) -> str:
    """
    Recursively hunts for COBOL 'COPY' statements and injects the contents of the
    target .cpy file directly into the memory string to ensure accurate structural scanning.
    """
    # ==========================================================================
    # DEFENSIVE DESIGN (INLINE COPYBOOK EXPANSION):
    # A COBOL program's data declarations are often hidden inside external copybooks.
    # Scanning the source file alone would result in massive false-positives for
    # undeclared variables. We recursively expand and inline copybooks directly
    # into the memory buffer before analysis to ensure mathematically accurate
    # dependency tracking.
    # ==========================================================================

    root = copybook_root if copybook_root is not None else source_path.parent
    origin = origin if origin is not None else source_path

    def replacer(match):
        copy_name = match.group(1).upper()
        replacing_clause = match.group(2)
        cpy_file = find_copybook(copy_name, root, origin)
        if cpy_file is not None:
            cpy_content = cpy_file.read_text(encoding="utf-8", errors="ignore").upper()
            # ==============================================================
            # DEFENSIVE DESIGN (DYNAMIC ALIASING):
            # COBOL's 'REPLACING' clause allows dynamic text substitution at
            # compile time. We must simulate this substitution in our in-memory
            # buffer to prevent missing usage references for aliased variables.
            # ==============================================================
            if replacing_clause:
                # Extracts pairs, ignoring the optional == delimiters
                pairs = re.findall(
                    r"(?:==)?([A-Z0-9_\-]+)(?:==)?\s+BY\s+(?:==)?([A-Z0-9_\-]+)(?:==)?",
                    replacing_clause,
                    re.IGNORECASE,
                )
                for old_val, new_val in pairs:
                    # Use negative lookarounds so we don't accidentally replace partial words with hyphens
                    cpy_content = re.sub(
                        r"(?<![A-Z0-9_\-])" + re.escape(old_val) + r"(?![A-Z0-9_\-])",
                        new_val,
                        cpy_content,
                    )

            return f"*> --- START COPY {copy_name} ---\n{cpy_content}\n*> --- END COPY {copy_name} ---"

        # If the copybook is missing from the repo, leave the statement intact to avoid crashing
        return match.group(0)

    # Run the substitution up to 3 times to handle nested copybooks (COPY within a COPY)
    safe_content = content
    for _ in range(3):
        safe_content = COPY_PATTERN.sub(replacer, safe_content)

    return safe_content


def x_ray_dead_code(
    filepath: Path,
    copybook_root: Optional[Path] = None,
    origin: Optional[Path] = None,
) -> Optional[dict]:
    """Parses a fully-expanded COBOL file to find mathematically unreachable logic and memory.

    `copybook_root` is where COPY members are searched (default: the file's own
    directory); `origin` is the program's path in the repository when `filepath`
    is a patched copy elsewhere, used to pick the nearest of several same-named copybooks.
    """
    try:
        raw_content = filepath.read_text(encoding="utf-8", errors="ignore").upper()
    except Exception:
        return None

    # Resolve all external memory layouts into the local string before structural validation
    content = resolve_copybooks(raw_content, filepath, copybook_root, origin)

    # COBOL is strictly divided. We need to split the data from the execution.
    if "PROCEDURE DIVISION" not in content:
        return None

    parts = content.split("PROCEDURE DIVISION", 1)
    data_div = parts[0]
    proc_div = parts[1]

    # ==========================================
    # 1. ISOLATING UNUSED MEMORY ADDRESSES
    # ==========================================
    # Look for COBOL variable declarations (Levels 01-49, 77, 88)
    # Bypassing Area A sequence numbers by allowing up to 11 leading spaces/chars.
    var_pattern = re.compile(
        r"^[ \tA-Z0-9]{0,11}(?:0[1-9]|[1-4][0-9]|77|88)[ \t]+([A-Z0-9\-]+)",
        re.MULTILINE,
    )
    declared_vars = set(var_pattern.findall(data_div))

    # Strip out common noise like FILLER
    if "FILLER" in declared_vars:
        declared_vars.remove("FILLER")

    used_vars = set()
    for var in declared_vars:
        # A variable is "used" if it appears as a whole word anywhere in the Procedure Division
        # We use a fast regex boundary \b to prevent partial matches (e.g. tracking "ID" shouldn't flag "USER-ID")
        if re.search(r"\b" + re.escape(var) + r"\b", proc_div):
            used_vars.add(var)

    orphaned_vars = declared_vars - used_vars

    # ==========================================
    # 2. ISOLATING UNREACHABLE LOGIC BLOCKS
    # ==========================================
    paragraphs = paragraph_headers(proc_div)

    # Find every explicitly called target in the code
    call_pattern = re.compile(r"\b(?:PERFORM|GO\s+TO)\s+([A-Z0-9\-]+)\b")
    called_targets = set(call_pattern.findall(proc_div))

    dead_paragraphs = set()
    if paragraphs:
        # The first paragraph is the Main Entry Point. It is always reached by default.
        entry_point = paragraphs[0]
        reached_paragraphs = {entry_point}.union(called_targets)
        declared_paragraphs = set(paragraphs)

        # The Math: Unreachable logic is anything declared but never explicitly called
        dead_paragraphs = declared_paragraphs - reached_paragraphs

    # Ignore system paragraphs and generic loop ends (like *-EXIT)
    dead_paragraphs = {p for p in dead_paragraphs if not p.endswith("-EXIT")}

    # Calculate a rough estimate of Lines of Code (LOC) saved
    # (Assuming average 10 lines per paragraph and 1 line per variable)
    loc_saved = (len(dead_paragraphs) * 10) + len(orphaned_vars)

    return {
        "program_id": filepath.name,
        "total_vars": len(declared_vars),
        "orphaned_vars": orphaned_vars,
        "total_paras": len(paragraphs) if paragraphs else 0,
        "dead_paras": dead_paragraphs,
        "loc_saved": loc_saved,
    }


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Deprecated Trails Analyzer")

    parser = argparse.ArgumentParser(description="GitGalaxy Deprecated Trails Analyzer")
    parser.add_argument("target", help="Directory containing legacy COBOL payloads")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🔍 GitGalaxy Deprecated Trails Analyzer scanning {target_path.name} for obsolete logic...\n")

    cobol_files = list(target_path.rglob("*.cbl")) + list(target_path.rglob("*.cob"))

    totals = {
        "loc_saved": 0,
        "orphaned_vars": 0,
        "dead_paras": 0,
        "files_with_dead_code": 0,
    }

    for file_path in cobol_files:
        metrics = x_ray_dead_code(file_path, copybook_root=target_path)
        if metrics and (metrics["orphaned_vars"] or metrics["dead_paras"]):
            totals["files_with_dead_code"] += 1
            totals["loc_saved"] += metrics["loc_saved"]
            totals["orphaned_vars"] += len(metrics["orphaned_vars"])
            totals["dead_paras"] += len(metrics["dead_paras"])

            print(f" 🎯 TARGET: {metrics['program_id']}")
            if metrics["orphaned_vars"]:
                print(
                    f"    ↳ Unused Memory Addresses ({len(metrics['orphaned_vars'])}): {', '.join(list(metrics['orphaned_vars'])[:5])}"
                    + ("..." if len(metrics["orphaned_vars"]) > 5 else "")
                )
            if metrics["dead_paras"]:
                print(
                    f"    ↳ Unreachable Logic Blocks ({len(metrics['dead_paras'])}): {', '.join(list(metrics['dead_paras'])[:5])}"
                    + ("..." if len(metrics["dead_paras"]) > 5 else "")
                )
            print("-" * 60)

    # Presentation
    print("\n==========================================================")
    print(" 📉 DEPRECATED TRAILS REDUCTION REPORT")
    print("==========================================================")
    print(f" Files Flagged for Cleanup : {totals['files_with_dead_code']}")
    print(f" Unused Memory Addresses   : {totals['orphaned_vars']} variables")
    print(f" Unreachable Logic Blocks  : {totals['dead_paras']} paragraphs")
    print(f" ✂️ Estimated Bloat Removed : ~{totals['loc_saved']} Lines of Code")
    print("==========================================================\n")


if __name__ == "__main__":
    main()
