#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Lexical Patcher (Pre-Processor)
#
# PURPOSE:
# Neutralizes legacy COBOL flow control anomalies by safely restructuring
# them into deterministic equivalents.
#
# ARCHITECTURAL DECISION:
# Legacy constructs like 'NEXT SENTENCE' create opaque execution jumps that
# break modern Abstract Syntax Trees and topological mapping. This module
# intercepts these anomalies and rewrites them into explicit scope terminators
# (CONTINUE), protected by a Dialect Sensor to ensure backward-compatibility
# with strict COBOL-74 environments.
# ==============================================================================
import re
from pathlib import Path


def detect_cobol_dialect(content: str) -> str:
    """
    Scans for post-1974 structural signatures to determine the compiler era.
    """
    # COBOL-85 introduced explicit scope terminators, EVALUATE, INITIALIZE, and inline comments (*>)
    modern_signatures = re.compile(
        r"\b(EVALUATE|INITIALIZE|END-IF|END-PERFORM|END-READ|END-EVALUATE|CONTINUE)\b|\*>",
        re.IGNORECASE,
    )

    if modern_signatures.search(content):
        return "COBOL-85"
    return "COBOL-74"


def patch_lexical_traps(filepath: Path) -> bool:
    """
    Scans the file for NEXT SENTENCE. If found, rewrites it safely based on the
    compiler dialect. Returns True if the file was modified, False otherwise.
    """
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {filepath.name}: {e}")
        return False

    # DEFENSIVE DESIGN: Fast substring check before engaging the heavy regex engine
    if not re.search(r"\bNEXT\s+SENTENCE\b", content, re.IGNORECASE):
        return False

    # 1. Sense the Execution Environment
    dialect = detect_cobol_dialect(content)

    # 2. Apply Era-Appropriate Lexical Patches
    if dialect == "COBOL-85":
        # Safe to use modern block-scoped CONTINUE and inline comments
        patched_content = re.sub(
            r"\bNEXT\s+SENTENCE\b",
            "CONTINUE *> GitGalaxy Patch: Neutralized Flow Control Anomaly",
            content,
            flags=re.IGNORECASE,
        )
        print(f"   ↳ [!] {dialect} Detected: Safely upgraded NEXT SENTENCE to CONTINUE.")
    else:
        # COBOL-74 Strict Mode: We must leave it as NEXT SENTENCE to prevent compilation failures.
        # We rewrite it cleanly to ensure standard spacing for the extraction slicer, but avoid modern injection.
        patched_content = re.sub(r"\bNEXT\s+SENTENCE\b", "NEXT SENTENCE", content, flags=re.IGNORECASE)
        print(f"   ↳ [!] {dialect} Detected: Engaged strict legacy compliance mode. Bypassing modern injection.")

    # Save the sanitized code back to the file if structural changes were made
    if content != patched_content:
        filepath.write_text(patched_content, encoding="utf-8")
        return True

    return False
