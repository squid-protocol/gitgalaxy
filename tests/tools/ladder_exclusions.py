"""#5280: the burned-ladder programs that cannot reach L1 for a reason that is not a translator gap.

The ladder keeps every program (the denominator is fixed). These are reported in their own rows next to a reachable
denominator, with the issue and the citation, so a reader does not mistake them for core translator work:

  source_defect  source IBM's compiler rejects (the oracle refuses it too)
  not_cobol      refused whole because the member is not COBOL (an assembler member the HLASM front end does not yet
                 lower; the entry goes when the member leaves L0 and the page lists it as stale until then)
  owner_held     held by an owner ruling or by a z/OS calibration that cannot be taken from this box
  refused_by_design  outside what the port proves, for good (owner, 2026-11-03, #5106): its holes are constructs no
                 oracle can back (a model would rest on assumptions alone) or breadth work no ladder program needs;
                 the program stays at L0 as a stated boundary, not as unfinished translator work

Stdlib only (progress_report and evidence_report both import it).
"""

from __future__ import annotations

from typing import Any

KINDS = ("source_defect", "not_cobol", "owner_held", "refused_by_design")
KIND_LABEL = {
    "source_defect": "source defect (source IBM rejects)",
    "not_cobol": "refused whole: not COBOL",
    "owner_held": "held by an owner ruling or z/OS calibration",
    "refused_by_design": "refused by design (owner ruling: outside what the port proves)",
}
KIND_SHORT = {
    "source_defect": "Source defect",
    "not_cobol": "Not COBOL",
    "owner_held": "Owner hold",
    "refused_by_design": "Refused by design",
    "open": "Still climbing",
}

_RECORD_KEY_SHORT = "RECORD KEY names a WORKING-STORAGE item; IBM's compiler rejects the source"
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
        "short": _RECORD_KEY_SHORT,
    },
    ("aws-mainframe-modernization-carddemo", "cbimport.cbl"): {
        "kind": "source_defect",
        "issue": "#5866",
        "reason": _RECORD_KEY,
        "short": _RECORD_KEY_SHORT,
    },
    ("zecs", "zecs002.asm"): {
        "kind": "not_cobol",
        "issue": "#5859",
        "short": "assembler member, lowered by the HLASM front end",
        "reason": "CICS Assembler member; the HLASM front end lowers it and the det translator translates it whole (slices 3b-3e: reserved-word names renamed, GGCVER stub); its equivalence case tests/equivalence/zecs-zecs002 proves the port of the lowering (11 scenarios; the VERIFY verdict is keyed by userid_hex), and tests/cobol_mainframe/test_hlasm_interp_5859.py cross-checks the lowering with an independent interpreter",
    },
    ("dbb-mortgage-application", "epscsmrd.cbl"): {
        "kind": "refused_by_design",
        "issue": "#5106",
        "short": "LE condition handling and SOAP faults that no oracle can back",
        "reason": "its 7 holes are Language Environment condition handling (CEEHDLR / CEEHDLU and the CEE3SRP recovery "
        "point, refused by the owner's 2026-10-21 ruling) and CICS web services (SOAPFAULT CREATE), which no oracle "
        "backs, plus procedure pointers (SET TO ENTRY) and national / DBCS text, breadth work no ladder program "
        "needs (#5042, #4664); owner ruling 2026-11-03: no model built on assumptions alone, the program stays at L0",
    },
    ("dbb-mortgage-application", "epsmpmt.cbl"): {
        "kind": "owner_held",
        "issue": "#5867",
        "short": "floating-point power needs captured z/OS results",
        "reason": "floating-point power and FUNCTION ANNUITY need captured z/OS results (oracle_assumptions.md C6)",
    },
}


# Programs above L0 that stop below L4 by an owner decision. They are not unreachable (summarize() never counts
# them); the status slide names them beside the ladder so a reader sees a ruling, not a dropped program.
HELD_BELOW_L4: dict[tuple[str, str], dict[str, str]] = {
    ("cics-banking-sample-application-cbsa", "bankdata.cbl"): {
        "kind": "owner_held",
        "issue": "#7577",
        "reason": "47 of 48 branch outcomes run. The last (GOD010 line 917, IF OPENED-DATE-ATTEMPTS > 100) needs 100 "
        "random opened-date draws in a row to fail, probability under 15^-100; #7577's z3 check shows it reachable, "
        "so it is a stated assumption, not a netted infeasible outcome. Owner skip from the ladder (2026-10-30).",
        "short": "last branch needs 100 failed random draws in a row: reachable, so not netted (owner skip)",
    },
}


def _key(estate: str, program: str) -> tuple[str, str]:
    return (estate, program.replace("\\", "/").rsplit("/", 1)[-1].lower())


def lookup(estate: str, program: str) -> dict[str, str] | None:
    """The entry for a program (path as the evidence report names it), or None."""
    return EXCLUSIONS.get(_key(estate, program))


def held(estate: str, program: str) -> dict[str, str] | None:
    """The owner hold of a program that stops below L4 above L0, or None."""
    return HELD_BELOW_L4.get(_key(estate, program))


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
