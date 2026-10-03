"""Structural parity of a det port with its COBOL: a cheap warning before the proof, never a proof failure.

GitGalaxy's own single-file extraction (Prism.split_streams + StructuralExtractor.splice, the numbers a full scan
records as function_count and struct_branch) counts paragraphs/sections and branch points in the COBOL, and methods
and branch points in the det port's service class. Across the 49 programs ported on 2026-10-02 each kind keeps a
fixed overhead plus a slope (Theil-Sen fits below), so a port is compared with what its COBOL predicts:

    methods   batch 11.4 + 1.12 x paragraphs    CICS 20.8 + 1.13 x paragraphs   (proven ports: 0.88 .. 1.21 of it)
    branches  batch 12.6 + 1.30 x branches      CICS 51.8 + 2.33 x branches     (proven ports: 0.73 .. 1.58 of it)

A ratio outside BANDS (wider than any proven port reached) is a warning: a translation that dropped or duplicated
paragraphs, or expanded a construct far more than usual, is worth a look before GnuCOBOL and Db2 spend their time.
The fit is the 2026-10-02 estate's; refit (docs/language_status/det_port_design.md) when the emitter's shape moves
or the scanner's counting does (branches refit after Java stopped counting `?`/`:` inside literals and a ternary twice).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

# kind -> metric -> (overhead, slope)
MODEL = {
    "batch": {"methods": (11.4, 1.12), "branches": (12.6, 1.30)},
    "cics": {"methods": (20.8, 1.13), "branches": (51.8, 2.33)},
}
# metric -> (low, high): port / prediction outside this band warns
BANDS = {"methods": (0.6, 1.6), "branches": (0.5, 2.5)}
_CICS = re.compile(r"EXEC\s+CICS\b", re.IGNORECASE)


@cache
def _engines() -> tuple[Any, Any]:
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS), LANGUAGE_DEFINITIONS


def structure(text: str, lang: str) -> dict[str, int]:
    """GitGalaxy's function and branch counts for one file's text ('cobol' or 'java')."""
    from gitgalaxy.core.detector import StructuralExtractor

    prism, defs = _engines()
    streams = prism.split_streams(text, lang)
    r = StructuralExtractor(lang, defs).splice(streams["code_stream"], streams.get("comment_stream", ""),
                                               raw_content=text)  # fmt: skip
    return {"functions": len(r.get("functions", [])), "branches": int(r.get("equations", {}).get("branch", 0))}


def parity(program: str, cobol: str, java: str) -> dict[str, Any]:
    """One program's counts, predictions, ratios and warnings (cobol / java: the source texts)."""
    kind = "cics" if _CICS.search(cobol) else "batch"
    c, j = structure(cobol, "cobol"), structure(java, "java")
    out: dict[str, Any] = {"program": program, "kind": kind, "cobol": c, "java": j, "warnings": []}
    for metric, have, src in (("methods", j["functions"], c["functions"]), ("branches", j["branches"], c["branches"])):
        overhead, slope = MODEL[kind][metric]
        expected = overhead + slope * src
        ratio = have / expected
        out[metric] = {"expected": round(expected, 1), "ratio": round(ratio, 2)}
        low, high = BANDS[metric]
        if not low <= ratio <= high:
            out["warnings"].append(f"{program}: {metric} {have} vs {expected:.0f} expected from {src} in the COBOL "
                                   f"(x{ratio:.2f}, band {low}..{high})")  # fmt: skip
    return out


def parity_files(program: str, cobol: Path, java: Path) -> dict[str, Any]:
    from gitgalaxy.core.source_text import read_source

    return parity(program, read_source(cobol).text, read_source(java).text)
