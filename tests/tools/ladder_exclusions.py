"""#5280: the burned-ladder programs that cannot reach L1 for a reason that is not a translator gap.

The ladder keeps every program (the denominator is fixed). These are reported in their own rows next to a reachable
denominator, with the issue and the citation, so a reader does not mistake them for core translator work:

  source_defect  source IBM's compiler rejects (the oracle refuses it too)
  not_cobol      refused whole because the member is not COBOL (an assembler member the HLASM front end does not yet
                 lower; the entry goes when the member leaves L0 and the page lists it as stale until then)
  owner_held     held by an owner ruling or by a z/OS calibration that cannot be taken from this box

Stdlib only (progress_report and evidence_report both import it).
"""

from __future__ import annotations

from typing import Any

KINDS = ("source_defect", "not_cobol", "owner_held")
KIND_LABEL = {
    "source_defect": "source defect (source IBM rejects)",
    "not_cobol": "refused whole: not COBOL",
    "owner_held": "held by an owner ruling or z/OS calibration",
}

_RECORD_KEY = (
    "RECORD KEY names an item defined in WORKING-STORAGE, not in a record of the file; IBM requires it in a record "
    "description of that file (Enterprise COBOL Language Reference, RECORD KEY clause)"
)

# (estate, program basename lower-cased) -> entry
EXCLUSIONS: dict[tuple[str, str], dict[str, str]] = {
    ("aws-mainframe-modernization-carddemo", "cbexport.cbl"): {
        "kind": "source_defect",
        "issue": "#5866",
        "reason": _RECORD_KEY,
    },
    ("aws-mainframe-modernization-carddemo", "cbimport.cbl"): {
        "kind": "source_defect",
        "issue": "#5866",
        "reason": _RECORD_KEY,
    },
    ("zecs", "zecs002.asm"): {
        "kind": "not_cobol",
        "issue": "#5859",
        "reason": "CICS Assembler member; the HLASM front end lowers it and the det translator translates it whole (slices 3b-3e: reserved-word names renamed, GGCVER stub); its equivalence case tests/equivalence/zecs-zecs002 proves the port of the lowering (11 scenarios; the VERIFY verdict is keyed by userid_hex), and tests/cobol_mainframe/test_hlasm_interp_5859.py cross-checks the lowering with an independent interpreter",
    },
    ("dbb-mortgage-application", "epscsmrd.cbl"): {
        "kind": "owner_held",
        "issue": "#5106",
        "reason": "Language Environment condition handlers (CEEHDLR) refused by name, owner ruling 2026-10-21",
    },
    ("dbb-mortgage-application", "epsmpmt.cbl"): {
        "kind": "owner_held",
        "issue": "#5867",
        "reason": "floating-point power and FUNCTION ANNUITY need captured z/OS results (oracle_assumptions.md C6)",
    },
}


def lookup(estate: str, program: str) -> dict[str, str] | None:
    """The entry for a program (path as the evidence report names it), or None."""
    return EXCLUSIONS.get((estate, program.replace("\\", "/").rsplit("/", 1)[-1].lower()))


def summarize(reports: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    """estate -> program rows (each with `program` and `level`). Returns None when no row is listed. A listed program
    above L0 is not counted as unreachable (it is reported under `stale`: the entry no longer holds)."""
    kinds: dict[str, dict[str, Any]] = {}
    stale: list[str] = []
    for estate in sorted(reports):
        for p in reports[estate]:
            e = lookup(estate, p["program"])
            if e is None:
                continue
            name = f"{estate}/{p['program']}"
            if p["level"] != "L0":
                stale.append(name)
                continue
            k = kinds.setdefault(e["kind"], {"count": 0, "programs": [], "issues": [], "reasons": []})
            k["count"] += 1
            k["programs"].append(name)
            if e["issue"] not in k["issues"]:
                k["issues"].append(e["issue"])
            if e["reason"] not in k["reasons"]:
                k["reasons"].append(e["reason"])
    if not kinds and not stale:
        return None
    out: dict[str, Any] = {
        "kinds": {k: kinds[k] for k in KINDS if k in kinds},
        "count": sum(v["count"] for v in kinds.values()),
    }
    if stale:
        out["stale"] = sorted(stale)
    return out
