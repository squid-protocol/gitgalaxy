# ==============================================================================
# GitGalaxy Core: Mainframe Invocation Resolver (#3200)
#
# PURPOSE:
# `mainframe_boundary.py` reads one file and produces NAMES -- "this LINK runs
# ABNDPROC". This module sees the whole repository and answers "and ABNDPROC is
# src/base/cobol_src/ABNDPROC.cbl". It turns the per-file call sites into
# resolved rows plus the `call`/`exec` edges that join #2992's edge_data.
#
# WHY NOT `NetworkRiskSensor._resolve_target`:
# Two different relations with two different truths.
#   - An IMPORT names a FILE (`COPY CUSTCOPY` -> CUSTCOPY.cpy), so the import
#     resolver matches on path and stem, and a candidate that declares a
#     PROGRAM-ID is DISQUALIFIED: a copybook is a fragment, never a program
#     (#3199).
#   - A CALL names a PROGRAM (`CALL 'SAM2'` -> whichever file declares
#     PROGRAM-ID SAM2), which is the class_data name, not the filename. Those
#     usually coincide and sometimes do not, and a stem lookup cannot tell a
#     program from a copybook that happens to share its name.
# So resolution here is PROGRAM-ID first, and when a PROGRAM-ID is shared by
# several files (zopeneditor's COBOL/SAM2.cbl and multiroot/sam/SAM2.cbl) the
# NEAREST one wins -- the reading the answer key records, and the one that
# matches how the target is really chosen, by library concatenation order at
# link-edit or CICS-install time. Both resolvers now break a tie on proximity
# (core/path_proximity.py), but they still disagree about what a tie MEANS: a
# call picks one, an import that is still ambiguous draws nothing.
#
# THE EDGES ARE A SEPARATE KIND AND DO NOT ENTER THE GRAPH.
# `edge_kind` is 'call'/'exec', never 'import'. They are NOT handed to the
# DiGraph, so pagerank_score, popularity, internal_dependency_links,
# betweenness, blast radius, the archetypes and every risk score are byte-for-
# byte what they were before this module existed. Whether a runtime invocation
# ought to count as architectural coupling is a scoring question with its own
# measured before/after; it is deliberately not settled here (#3237). The one
# consequence is that #2992's per-file reconciliation
# (COUNT by src == internal_dependency_links) is now scoped to the graph's
# kinds, `WHERE edge_kind IN ('import', 'fcall')` since #3333 added function
# calls to the graph, which is what tests/tools_recorders/test_edge_data.py
# asserts. (#3333 settled it for function calls; these program-level
# 'call'/'exec' edges are still #3237's.)
# ==============================================================================
from pathlib import Path
from typing import Any

from gitgalaxy.core.mainframe_boundary import TRANSACTION_ROUTING_VERBS
from gitgalaxy.core.path_proximity import nearest_path

# Languages whose `classes` entries are program declarations a call can target.
# cobol only today: a JCL `EXEC PGM=` and a COBOL `CALL` both name a COBOL
# program. pli/rexx declare callable units too, but neither is a documented
# target of these verbs yet, so widening this is a measured change, not a guess.
#
# #3199 reads the same fact from the other side: if a `classes` entry here is a
# whole program, then a candidate file that has one is not a copybook, which is
# how `COPY ACCTCTRL` tells ACCTCTRL.cpy from the ACCTCTRL.cbl beside it. Adding
# a language here therefore has to be right for both readings.
PROGRAM_DECLARING_LANGUAGES = ("cobol",)

# #3495: languages whose call target is an executable UNIT, not a `classes` entry.
# An HLASM program is named by its control section -- `name CSECT` / `RSECT` /
# `START`, or `name DFHEIENT` for a command-level CICS program -- which the hlasm
# func_start rule yields as the file's functions; its `classes` are DSECTs,
# storage layouts no verb can call. Without it walmartlabs/zECS's COBOL
# `LINK PROGRAM('ZECS002')` never reached ZECS002.asm. Kept apart from
# PROGRAM_DECLARING_LANGUAGES because #3199 reads that tuple as "this file is a
# program, not a copybook", which a unit-bearing HLASM macro member is not.
UNIT_DECLARED_PROGRAM_LANGUAGES = ("hlasm",)

# #3491: a PL/I program is reached two ways. CICS LINK / XCTL name the LOAD
# MODULE -- the member, i.e. the file stem (navikt/DSF `XCTL PROGRAM('R0010420')`
# runs R0010420.pli, whose main procedure is labelled R001B1) -- and a `CALL`
# names an ENTRY, the outermost procedure's label (DSF's `CALL P9956_BER_G_CICS`
# reaches the member R0019956.pli that defines it). Internal procedures are
# never indexed: calling one stays a function-level edge.
MEMBER_NAMED_PROGRAM_LANGUAGES = ("pli",)

# `CALL`/`LINK`/`XCTL` are COBOL-side invocations; `EXEC PGM` is JCL's.
_EXEC_VERBS = ("EXEC PGM",)


def _program_index(parsed_files: list[dict[str, Any]]) -> dict[str, list[str]]:
    """PROGRAM-ID (upper-cased) -> the paths declaring it, in scan order."""
    index: dict[str, list[str]] = {}
    for f in parsed_files:
        lang = str(f.get("lang_id", "")).lower()
        if lang in MEMBER_NAMED_PROGRAM_LANGUAGES:
            functions = f.get("functions", []) or []
            if functions:  # a member with no procedure is %INCLUDE text, not a program
                path = f.get("path", "")
                # The outermost procedure opens first (`functions` is ordered by size).
                outer = min(functions, key=lambda fn: int(fn.get("start_line") or 0))
                names = {Path(path).stem.upper(), str(outer.get("name", "")).strip().upper()}
                for name in sorted(n for n in names if n):
                    index.setdefault(name, []).append(path)
            continue
        if lang in UNIT_DECLARED_PROGRAM_LANGUAGES:
            for fn in f.get("functions", []) or []:
                name = str(fn.get("name", "")).strip().upper()
                if name:
                    index.setdefault(name, []).append(f.get("path", ""))
            continue
        if lang not in PROGRAM_DECLARING_LANGUAGES:
            continue
        for cls in f.get("classes", []) or []:
            name = str(cls.get("name", "")).strip().upper()
            if name:
                index.setdefault(name, []).append(f.get("path", ""))
    return index


def _pli_included_procedures(parsed_files: list[dict[str, Any]]) -> set[str]:
    """#3491: names that are only ever NESTED PL/I procedures. navikt/DSF splits a
    program into %INCLUDE members (R00153NC.pli is pasted into R0015301.pli), and a
    member calls its includer's internal procedures (`CALL P020_SKRIV_BARN_AV_TRANHIST`,
    defined inside R0015301). After include expansion that is an internal call, a
    function-level edge -- not a program call site -- so it is dropped here, where
    the whole repository is visible. A name some file declares as its OUTERMOST
    procedure (an entry another program can CALL) is never dropped."""
    nested: set[str] = set()
    outer: set[str] = set()
    for f in parsed_files:
        if str(f.get("lang_id", "")).lower() not in MEMBER_NAMED_PROGRAM_LANGUAGES:
            continue
        functions = sorted(f.get("functions", []) or [], key=lambda fn: int(fn.get("start_line") or 0))
        for i, fn in enumerate(functions):
            name = str(fn.get("name", "")).strip().upper()
            (outer if i == 0 else nested).add(name)
    return nested - outer


def resolve_invocations(
    parsed_files: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve every extracted call site, and aggregate the resolved ones into edges.

    Returns `(call_sites, edges)`:
      - `call_sites` is EVERY site, resolved or not. A site whose target name could
        not be read (a CALL through an identifier with no VALUE clause) keeps
        `target: None`; one whose target is not a program in this repository
        (`CALL 'CEEGMT'`, `EXEC PGM=IEFBR14`) keeps its target and gets
        `resolved_path: None`. That is #3200's "unresolved targets are recorded
        nowhere", answered: they are rows, not silence.
      - `edges` is one row per (src, dst, kind) pair with a `call_sites` count,
        shaped like #2992's import edges so edge_data takes them unchanged.
    """
    index = _program_index(parsed_files)
    included = _pli_included_procedures(parsed_files)
    sites: list[dict[str, Any]] = []
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    for f in parsed_files:
        src_path = f.get("path", "")
        is_pli = str(f.get("lang_id", "")).lower() in MEMBER_NAMED_PROGRAM_LANGUAGES
        for site in f.get("call_sites", []) or []:
            target = site.get("target")
            if is_pli and site.get("verb") == "CALL" and str(target or "").upper() in included:
                continue  # an internal procedure of the program that %INCLUDEs this member
            resolved = None
            # A TRANSID-routing site's target is a transaction id, not a program:
            # it resolves through the CSD map (resolve_transactions), so it is
            # never matched against the PROGRAM-ID index here. It still rides in
            # call_site_data as a row, just with no program destination.
            if target and site.get("verb") not in TRANSACTION_ROUTING_VERBS:
                resolved = nearest_path(index.get(str(target).upper(), []), src_path)
                # A program calling itself is recursion, not an edge: the
                # import graph drops self-edges for the same reason.
                if resolved == src_path:
                    resolved = None

            record = dict(site)
            record["src_path"] = src_path
            record["resolved_path"] = resolved
            sites.append(record)

            if not resolved:
                continue
            kind = "exec" if site.get("verb") in _EXEC_VERBS else "call"
            edge = edges.setdefault(
                (src_path, resolved, kind),
                {"src": src_path, "dst": resolved, "edge_kind": kind, "weight": 0.0, "call_sites": 0},
            )
            # One unit of weight per site, matching the import edge's "1.0 per
            # plain import". Nothing reads this weight today -- these edges are
            # not in the graph -- but it keeps the column meaningful per kind.
            edge["weight"] += 1.0
            edge["call_sites"] += 1

    ordered = sorted(edges.values(), key=lambda e: (e["src"], e["dst"], e["edge_kind"]))
    return sites, ordered


def resolve_transactions(parsed_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve each CSD transaction's PROGRAM to the file that declares it (#3211-followup).

    A `DEFINE TRANSACTION(TTTT) ... PROGRAM(PPPP)` record (extracted from a `.csd`
    deck or a DFHCSDUP SYSIN inside a JCL job) names a program by PROGRAM-ID, the
    same relation `resolve_invocations` resolves for a CALL -- so it reuses the
    PROGRAM-ID index and the nearest-match tie-break. Each returned record keeps
    the transaction fields and adds `src_path` (the deck that defines it) and
    `resolved_path` (the program's file, or None for a program not in this
    repository -- a system transaction or one whose module is external).

    Unlike calls, a transaction never self-resolves: a CSD deck is not a program,
    so `resolved_path == src_path` cannot happen and is not special-cased.
    """
    index = _program_index(parsed_files)
    out: list[dict[str, Any]] = []
    for f in parsed_files:
        src_path = f.get("path", "")
        for txn in f.get("transaction_defs", []) or []:
            program = txn.get("program")
            resolved = nearest_path(index.get(str(program).upper(), []), src_path) if program else None
            record = dict(txn)
            record["src_path"] = src_path
            record["resolved_path"] = resolved
            out.append(record)
    out.sort(key=lambda t: (t.get("src_path", ""), int(t.get("line", 0) or 0), t.get("transid", "")))
    return out
