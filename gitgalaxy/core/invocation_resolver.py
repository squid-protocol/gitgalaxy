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
#     resolver matches on path and stem, and REFUSES to guess when a stem is
#     ambiguous (#3199) -- a wrong copybook edge is a wrong dependency.
#   - A CALL names a PROGRAM (`CALL 'SAM2'` -> whichever file declares
#     PROGRAM-ID SAM2), which is the class_data name, not the filename. Those
#     usually coincide and sometimes do not, and a stem lookup cannot tell a
#     program from a copybook that happens to share its name.
# So resolution here is PROGRAM-ID first, and when a PROGRAM-ID is shared by
# several files (zopeneditor's COBOL/SAM2.cbl and multiroot/sam/SAM2.cbl) the
# NEAREST one wins -- the reading the answer key records, and the one that
# matches how the target is really chosen, by library concatenation order at
# link-edit or CICS-install time. The import resolver's refuse-to-guess rule is
# right for its relation and wrong for this one.
#
# THE EDGES ARE A SEPARATE KIND AND DO NOT ENTER THE GRAPH.
# `edge_kind` is 'call'/'exec', never 'import'. They are NOT handed to the
# DiGraph, so pagerank_score, popularity, internal_dependency_links,
# betweenness, blast radius, the archetypes and every risk score are byte-for-
# byte what they were before this module existed. Whether a runtime invocation
# ought to count as architectural coupling is a scoring question with its own
# measured before/after; it is deliberately not settled here (#3237). The one
# consequence is that #2992's per-file reconciliation
# (COUNT by src == internal_dependency_links) is now scoped to
# `WHERE edge_kind = 'import'`, which is what tests/tools_recorders/
# test_edge_data.py asserts.
# ==============================================================================
from typing import Any, Optional

# Languages whose `classes` entries are program declarations a call can target.
# cobol only today: a JCL `EXEC PGM=` and a COBOL `CALL` both name a COBOL
# program. pli/rexx declare callable units too, but neither is a documented
# target of these verbs yet, so widening this is a measured change, not a guess.
_PROGRAM_LANGUAGES = ("cobol",)

# `CALL`/`LINK`/`XCTL` are COBOL-side invocations; `EXEC PGM` is JCL's.
_EXEC_VERBS = ("EXEC PGM",)


def _program_index(parsed_files: list[dict[str, Any]]) -> dict[str, list[str]]:
    """PROGRAM-ID (upper-cased) -> the paths declaring it, in scan order."""
    index: dict[str, list[str]] = {}
    for f in parsed_files:
        if str(f.get("lang_id", "")).lower() not in _PROGRAM_LANGUAGES:
            continue
        for cls in f.get("classes", []) or []:
            name = str(cls.get("name", "")).strip().upper()
            if name:
                index.setdefault(name, []).append(f.get("path", ""))
    return index


def _nearest(candidates: list[str], src_path: str) -> Optional[str]:
    """The candidate sharing the longest directory prefix with `src_path`.

    Ties break on the shallower path and then alphabetically, so the choice is
    deterministic and independent of scan order -- a repository scanned on two
    machines must produce the same edge.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    src_dirs = src_path.replace("\\", "/").split("/")[:-1]

    def _shared(candidate: str) -> int:
        dirs = candidate.replace("\\", "/").split("/")[:-1]
        depth = 0
        for a, b in zip(src_dirs, dirs):
            if a != b:
                break
            depth += 1
        return depth

    return sorted(candidates, key=lambda c: (-_shared(c), c.count("/"), c))[0]


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
    sites: list[dict[str, Any]] = []
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    for f in parsed_files:
        src_path = f.get("path", "")
        for site in f.get("call_sites", []) or []:
            target = site.get("target")
            resolved = None
            if target:
                resolved = _nearest(index.get(str(target).upper(), []), src_path)
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
