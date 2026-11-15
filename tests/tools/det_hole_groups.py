#!/usr/bin/env python3
"""L0 -> L1 static det-sweep hole grouping and downstream-caller unblock ranker.

Groups deterministic translator (`det`) blockers across whole-estate `det_survey.py` runs (and optional
`det_port` / equivalence case manifests) into domain categories (`called_hole`, `exec_cics`, `exec_dli`,
`exec_sql`, `arith_ebcdic`, `grammar_refusal`, `other`), propagates holes transitively along the static
CALL + EXEC CICS LINK/XCTL graph (#4803), and ranks every hole class by how many downstream callers and
estate programs/cases closing it unblocks.

Usage:
    python tests/tools/det_hole_groups.py --survey PATH [--corpora DIR] [--top 25] [--json]
    python tests/tools/det_hole_groups.py --det-port-dir DIR [--equivalence-dir DIR] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

import cics_census as cc  # noqa: E402
import det_survey as ds  # noqa: E402
import gap_prevalence as gp  # noqa: E402

FORMAT = "det-hole-groups/1"
CATEGORIES = (
    "called_hole",
    "exec_cics",
    "exec_dli",
    "exec_sql",
    "arith_ebcdic",
    "grammar_refusal",
    "other",
)

# Domain classification patterns applied to normalized gap keys (cc.gap_key / cc.error_key).
_CALLED_RE = re.compile(
    r"^(?:"
    r"CALL\b"
    r"|unlisted callee\b"
    r"|called hole:"
    r"|no generated project to carry\b"
    r"|.+?:\s*no program of that name with a CALL entry"
    r"|.+?: not in the case\b"
    r"|.*?:\s*(?:the program name is not statically known|a blank program name can reach the CALL)"
    r"|.*?not a program name the port matches"
    r"|sibling\b.*?\brefused"
    r")",
    re.I,
)
_DLI_RE = re.compile(
    r"^(?:EXEC\s+DLI\b|CALL\s+(?:CBLTDLI|AIBTDLI)\b|missing copybook:\s*IMS system)"
    r"|\b(?:CBLTDLI|AIBTDLI|DLITCBL|DFSRRC00|DLI)\b",
    re.I,
)
_SQL_RE = re.compile(r"^(?:EXEC\s+SQL\b|missing copybook:\s*Db2 system)|\bSQLCA\b", re.I)
_CICS_RE = re.compile(
    r"^(?:EXEC\s+CICS\b|missing copybook:\s*CICS system|refused:\s*(?:macro-level CICS|CICS Assembler))",
    re.I,
)
_ARITH_EBCDIC_RE = re.compile(
    r"(?:"
    r"\bARITHMETIC-OSVS\b|\bARITH\(EXTEND\)|\bHFP\b|\bCOMP-[1235]\b|\bCOMP5\b|\bzos_comp5\b"
    r"|\bbinary64\b|\bfloating-point\b|\bROUNDED into\b|\bP-scaled\b|\bSIGN SEPARATE\b"
    r"|\bseparately signed\b|\bPACKED\b|\bzoned\b|\boverpunch\b"
    r"|\bnonnumeric literal in arithmetic\b|\bsigned numeric literal\b|\barithmetic target\b"
    r"|compared with a (?:nonnumeric|arithmetic expression)"
    r"|\bEBCDIC\b|\bsingle-byte code page\b|\bnational / DBCS\b|\bthe PICTURE N\b"
    r"|\bCOLLATING\b|\bALPHABET\b|\bthe bytes of a\b|\bbytes overlap another item\b"
    r")",
    re.I,
)

# Extract statically named unresolved CALL target from a raw det hole message.
_RAW_CALL_TARGET = re.compile(
    r"(?:\bline\s+\d+:\s*)?(?:HOLE\s+)?(?:"
    r"CALL\s+([A-Z0-9@#$_-]+)(?::|\s|$)"
    r"|([A-Z0-9@#$_-]+):\s*(?:no program of that name with a CALL entry|not in the case\b)"
    r"|sibling\s+([A-Z0-9@#$_-]+)\b"
    r")",
    re.I,
)


def classify_gap(gap: str) -> str:
    """Map a normalized gap/error key into an L0->L1 domain category."""
    if _DLI_RE.search(gap):
        return "exec_dli"
    if _SQL_RE.search(gap):
        return "exec_sql"
    if _CALLED_RE.search(gap):
        return "called_hole"
    if _CICS_RE.search(gap):
        return "exec_cics"
    if _ARITH_EBCDIC_RE.search(gap):
        return "arith_ebcdic"
    if gap.startswith(("grammar:", "refused:", "missing copybook")):
        return "grammar_refusal"
    return "other"


def _unlisted_stub_name(raw_hole: str) -> str | None:
    """If raw_hole points to an unresolved/unlisted callee stub, return its uppercase program name."""
    if raw_hole.startswith("unlisted callee "):
        return raw_hole.removeprefix("unlisted callee ").strip().upper()
    m = _RAW_CALL_TARGET.match(raw_hole.strip())
    if not m:
        return None
    name = next((g for g in m.groups() if g), None)
    if not name:
        return None
    up = name.upper()
    if up in ("CBLTDLI", "AIBTDLI", "CEE3ABD", "BY", "REFERENCE", "CONTENT"):
        return None
    return up


# Closed COBOL/translator vocabulary terms that cics_census._generic strips (because of hyphens/digits/parens)
# yet identify distinct arithmetic/EBCDIC idioms rather than customer data names.
_PRESERVE_TERMS: tuple[tuple[str, str], ...] = (
    ("ARITHMETIC-OSVS", "ZZARITHMETICOSVSZZ"),
    ("ARITH(EXTEND)", "ZZARITHEXTENDZZ"),
    ("COMP-1", "ZZCOMPONEZZ"),
    ("COMP-2", "ZZCOMPTWOZZ"),
    ("COMP-3", "ZZCOMPTHREEZZ"),
    ("COMP-5", "ZZCOMPFIVEZZ"),
    ("P-scaled", "ZZPSCALEDZZ"),
)


def _gap_key_preserving_idioms(text: str) -> str:
    """Delegate to cics_census.gap_key while preserving fixed COBOL/translator arithmetic keywords."""
    masked = text
    for src, tok in _PRESERVE_TERMS:
        masked = masked.replace(src, tok)
    key = cc.gap_key(masked)
    for src, tok in _PRESERVE_TERMS:
        key = key.replace(tok, src)
    return key


def _normalize_called_hole(raw_hole: str) -> str:
    """Normalize an entry from det_port's `called_holes` (`CALLEE: <hole>` or `<NAME>: not in the case ...`)."""
    s = str(raw_hole).strip()
    m = re.match(r"^([A-Z0-9@#$_-]{1,8}):\s*not in the case\b", s, re.I)
    if m:
        return f"unlisted callee {m.group(1).upper()}"
    m = re.match(r"^([A-Z0-9@#$_-]{1,8}):\s+(.+)$", s)
    if m:
        return _gap_key_preserving_idioms(m.group(2))
    return _gap_key_preserving_idioms(s)


def _normalize_direct_hole(raw_hole: str) -> str:
    """Normalize an entry from `holes` on a program row."""
    if raw_hole.startswith("unlisted callee "):
        return raw_hole
    return _gap_key_preserving_idioms(raw_hole)


def load_survey_input(path: Path, label: str = "before") -> dict[str, list[dict[str, Any]]]:
    """Load a survey.json file or a cics_census survey directory (`<label>-*`)."""
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): list(v) for k, v in data.items() if isinstance(v, list)}
    if (path / "survey.json").is_file():
        data = json.loads((path / "survey.json").read_text(encoding="utf-8"))
        return {str(k): list(v) for k, v in data.items() if isinstance(v, list)}
    merged: dict[str, list[dict[str, Any]]] = {}
    for sub in sorted(path.glob(f"{label}-*")):
        sj = sub / "survey.json"
        if sj.is_file():
            data = json.loads(sj.read_text(encoding="utf-8"))
            for corpus, rows in data.items():
                if isinstance(rows, list):
                    merged[str(corpus)] = rows
    if merged:
        return merged
    raise FileNotFoundError(f"no survey.json found under {path}")


def _enrich_cics_links(
    rows_by: dict[str, list[dict[str, Any]]],
    corpora_roots: list[Path],
    burned: set[str],
) -> None:
    """Populate `cics_links` from corpus sources when older survey.json rows lack them."""
    if not corpora_roots:
        return
    dirs = dict(cc.corpus_dirs(corpora_roots))
    for corpus, rows in rows_by.items():
        root = dirs.get(corpus)
        if root is None or not cc.is_burned(corpus, burned):
            continue
        for r in rows:
            if "cics_links" in r or "copy_member" in r or "not_program" in r:
                continue
            prog_rel = r.get("program")
            if not prog_rel or prog_rel == "(estate)":
                continue
            src_file = root / prog_rel
            if not src_file.is_file():
                continue
            try:
                from gitgalaxy.core.source_text import read_source

                links = ds.static_cics_links(read_source(src_file).text)
                if links:
                    r["cics_links"] = links
            except OSError:
                continue


def _load_equivalence_cases(eq_dir: Path | None) -> dict[tuple[str, str], set[str]]:
    """Map (corpus, rel_source_or_prog_upper) -> set of equivalence case names."""
    mapping: dict[tuple[str, str], set[str]] = defaultdict(set)
    if eq_dir is None or not eq_dir.is_dir():
        return mapping
    for cj in sorted(eq_dir.glob("*/case.json")):
        try:
            data = json.loads(cj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        case_name = cj.parent.name
        corpus_field = data.get("corpus")
        corpus = corpus_field.get("name", "") if isinstance(corpus_field, dict) else str(corpus_field or "")
        if not corpus:
            continue
        for key in ("program_source",):
            if data.get(key):
                mapping[(corpus, str(data[key]))].add(case_name)
        if data.get("program"):
            mapping[(corpus, str(data["program"]).upper())].add(case_name)
        for extra in data.get("programs", []):
            if isinstance(extra, dict):
                if extra.get("program_source"):
                    mapping[(corpus, str(extra["program_source"]))].add(case_name)
                if extra.get("program"):
                    mapping[(corpus, str(extra["program"]).upper())].add(case_name)
        for rel in data.get("subprograms", []):
            mapping[(corpus, str(rel))].add(case_name)
    return mapping


def _build_graph(rows_by: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Normalize surveyed rows into program nodes, direct gap classes, and intra-estate call edges."""
    burned = cc.burned_names()
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    name_index: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)

    for corpus, rows in sorted(rows_by.items()):
        for r in rows:
            if "copy_member" in r or "not_program" in r:
                continue
            prog = str(r.get("program", ""))
            if not prog or prog == "(estate)":
                continue
            key = (corpus, prog)
            prog_id = str(r.get("program_id") or Path(prog).stem).upper()
            stem = Path(prog).stem.upper()
            raw_holes = list(r.get("holes", []))
            error = r.get("error")
            direct_gaps: set[str] = set()
            called_prefixed_gaps: set[str] = set()
            unresolved_stubs: set[str] = set()

            if error:
                direct_gaps.add(cc.error_key(str(error)))
            elif "statements" not in r:
                direct_gaps.add("refused: no result")
            else:
                for h in raw_holes:
                    direct_gaps.add(_normalize_direct_hole(str(h)))
                    stub = _unlisted_stub_name(str(h))
                    if stub:
                        unresolved_stubs.add(stub)
            for h in r.get("called_holes", []):
                called_prefixed_gaps.add(_normalize_called_hole(str(h)))
                stub = _unlisted_stub_name(str(h))
                if stub:
                    unresolved_stubs.add(stub)
            for u in r.get("unlisted", []):
                gk = f"unlisted callee {str(u).upper()}"
                direct_gaps.add(gk)
                unresolved_stubs.add(str(u).upper())

            # Scrub gap keys when non-burned census rows appear (evidence policy sections 2-3).
            if not cc.is_burned(corpus, burned):
                direct_gaps = {gp.scrub_key(g) for g in direct_gaps}
                called_prefixed_gaps = {gp.scrub_key(g) for g in called_prefixed_gaps}
                unresolved_stubs = set()

            edges_raw = sorted(
                {str(c).upper() for c in r.get("callees", [])}
                | {str(c).upper() for c in r.get("cics_links", [])}
                | unresolved_stubs
            )
            nodes[key] = {
                "corpus": corpus,
                "program": prog,
                "program_id": prog_id,
                "burned": cc.is_burned(corpus, burned),
                "refused": bool(error) or ("statements" not in r and not error),
                "direct_gaps": direct_gaps,
                "called_prefixed_gaps": called_prefixed_gaps,
                "unresolved_stubs": unresolved_stubs,
                "edges_raw": edges_raw,
            }
            name_index[(corpus, prog_id)].append(key)
            if stem != prog_id:
                name_index[(corpus, stem)].append(key)

    adj: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for key, info in nodes.items():
        corpus = info["corpus"]
        for target_name in info["edges_raw"]:
            for target_key in name_index.get((corpus, target_name), ()):
                if target_key != key:
                    adj[key].add(target_key)
    return {"nodes": nodes, "adj": adj, "name_index": name_index}


def _reachable(start: tuple[str, str], adj: dict[tuple[str, str], set[tuple[str, str]]]) -> set[tuple[str, str]]:
    """All nodes reachable from `start` along 1+ call/link edges (cycle-safe BFS)."""
    seen: set[tuple[str, str]] = set()
    q = deque(adj.get(start, ()))
    while q:
        nxt = q.popleft()
        if nxt in seen or nxt == start:
            continue
        seen.add(nxt)
        q.extend(adj.get(nxt, ()))
    return seen


def analyze(
    rows_by: dict[str, list[dict[str, Any]]],
    *,
    corpora_roots: list[Path] | None = None,
    equivalence_dir: Path | None = None,
) -> dict[str, Any]:
    """Group L0->L1 det blockers across estates and rank by downstream callers unblocked."""
    burned = cc.burned_names()
    _enrich_cics_links(rows_by, corpora_roots or [], burned)
    case_map = _load_equivalence_cases(equivalence_dir)
    graph = _build_graph(rows_by)
    nodes: dict[tuple[str, str], dict[str, Any]] = graph["nodes"]
    adj: dict[tuple[str, str], set[tuple[str, str]]] = graph["adj"]

    reach_callees: dict[tuple[str, str], set[tuple[str, str]]] = {k: _reachable(k, adj) for k in nodes}
    # Effective L1 gap set for node P = P's own direct gaps | pre-attached called_holes | all callees' direct gaps.
    effective_gaps: dict[tuple[str, str], set[str]] = {}
    caller_only_gaps: dict[tuple[str, str], set[str]] = {}
    for k, info in nodes.items():
        via_callees = set(info["called_prefixed_gaps"])
        for callee in reach_callees[k]:
            via_callees |= nodes[callee]["direct_gaps"]
        eff = set(info["direct_gaps"]) | via_callees
        effective_gaps[k] = eff
        caller_only_gaps[k] = via_callees - info["direct_gaps"]

    # Map each equivalence case to all nodes it exercises and compute its union L1 gap set.
    case_nodes: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for k, info in nodes.items():
        corpus, prog = k
        for c in case_map.get((corpus, prog), set()) | case_map.get((corpus, info["program_id"]), set()):
            case_nodes[c].add(k)
    case_eff_gaps: dict[str, set[str]] = {
        c: set().union(*(effective_gaps[k] for k in ks)) for c, ks in case_nodes.items()
    }

    # Aggregate statistics per canonical gap key.
    stats: dict[str, dict[str, Any]] = {}
    all_gaps = sorted({g for eff in effective_gaps.values() for g in eff})
    for g in all_gaps:
        stats[g] = {
            "gap": g,
            "category": classify_gap(g),
            "refuses_program": g.startswith(cc.REFUSES),
            "estates_set": set(),
            "direct_programs": 0,
            "direct_only": 0,
            "callers_touched": 0,
            "callers_unblocked": 0,
            "callers_one_away": 0,
            "unblocks_whole": 0,
            "cases_unblocked": 0,
            "cases_touched": 0,
            "sample_direct": [],
            "sample_callers": [],
        }

    for k in sorted(nodes):
        info = nodes[k]
        corpus, prog = k
        eff = effective_gaps[k]
        direct = info["direct_gaps"]
        inherited = caller_only_gaps[k]
        for g in direct | inherited:
            st = stats[g]
            st["estates_set"].add(corpus)
            if g in direct:
                st["direct_programs"] += 1
                if info["burned"] and len(st["sample_direct"]) < 5:
                    st["sample_direct"].append(f"{corpus}:{prog}")
                if eff == {g}:
                    st["direct_only"] += 1
                    st["unblocks_whole"] += 1
            else:
                st["callers_touched"] += 1
                if info["burned"] and len(st["sample_callers"]) < 5:
                    st["sample_callers"].append(f"{corpus}:{prog}")
                if eff == {g}:
                    st["callers_unblocked"] += 1
                    st["unblocks_whole"] += 1
                elif len(eff - {g}) == 1:
                    st["callers_one_away"] += 1

    for c, eff in case_eff_gaps.items():
        for g in eff:
            st = stats[g]
            st["cases_touched"] += 1
            if eff == {g}:
                st["cases_unblocked"] += 1

    # Unresolved / uncalled stub rollup ranked by downstream callers blocked.
    stub_direct: dict[str, set[tuple[str, str]]] = defaultdict(set)
    stub_callers: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for k, info in nodes.items():
        if not info["burned"]:
            continue
        for stub in info["unresolved_stubs"]:
            stub_direct[stub].add(k)
        for callee in reach_callees[k]:
            for stub in nodes[callee]["unresolved_stubs"]:
                if k not in stub_direct[stub]:
                    stub_callers[stub].add(k)
    unlisted_stubs = sorted(
        (
            {
                "stub": s,
                "direct_callsites": len(stub_direct[s]),
                "downstream_callers": len(stub_callers[s]),
                "total_blocked": len(stub_direct[s] | stub_callers[s]),
                "sample_callsites": sorted(f"{c}:{p}" for c, p in stub_direct[s])[:5],
            }
            for s in stub_direct
        ),
        key=lambda d: (-d["downstream_callers"], -d["total_blocked"], d["stub"]),
    )

    gaps_out = []
    for g, st in stats.items():
        st["estates"] = len(st.pop("estates_set"))
        gaps_out.append(st)
    gaps_out.sort(
        key=lambda d: (
            -d["callers_unblocked"],
            -d["unblocks_whole"],
            -d["callers_touched"],
            -d["direct_programs"],
            -d["callers_one_away"],
            -d["cases_unblocked"],
            -d["estates"],
            d["gap"],
        )
    )

    # Category summary rollups.
    by_category: dict[str, dict[str, int]] = {
        cat: {
            "gap_classes": 0,
            "direct_occurrences": 0,
            "caller_occurrences": 0,
            "programs_blocked": 0,
            "unblocks_whole": 0,
        }
        for cat in CATEGORIES
    }
    cat_programs: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for k, eff in effective_gaps.items():
        for g in eff:
            cat_programs[classify_gap(g)].add(k)
    for d in gaps_out:
        c = by_category[d["category"]]
        c["gap_classes"] += 1
        c["direct_occurrences"] += d["direct_programs"]
        c["caller_occurrences"] += d["callers_touched"]
        c["unblocks_whole"] += d["unblocks_whole"]
    for cat, ps in cat_programs.items():
        by_category[cat]["programs_blocked"] = len(ps)

    n_progs = len(nodes)
    direct_whole = sum(1 for info in nodes.values() if not info["direct_gaps"])
    l1_whole = sum(1 for eff in effective_gaps.values() if not eff)
    blocked_only_by_called = sum(
        1 for k, info in nodes.items() if not info["direct_gaps"] and bool(effective_gaps[k])
    )
    return {
        "format": FORMAT,
        "estates": sorted({info["corpus"] for info in nodes.values()}),
        "programs": n_progs,
        "direct_whole": direct_whole,
        "l1_whole": l1_whole,
        "blocked_only_by_called_holes": blocked_only_by_called,
        "with_own_holes": sum(1 for info in nodes.values() if info["direct_gaps"] and not info["refused"]),
        "refused": sum(1 for info in nodes.values() if info["refused"]),
        "cases_mapped": len(case_nodes),
        "cases_l1_whole": sum(1 for eff in case_eff_gaps.values() if not eff),
        "by_category": by_category,
        "gaps": gaps_out,
        "unlisted_stubs": unlisted_stubs,
    }


def det_port_dir_to_rows(work: Path, corpus_name: str = "det-port-cases") -> dict[str, list[dict[str, Any]]]:
    """Adapt a directory of det_port result JSON files (`*/result.json` or `*.json`) into survey rows."""
    by_corpus: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in sorted(work.rglob("*.json")):
        if p.name in ("survey.json", "summary.json", "phases.json", "report.json"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(d, dict) or "program" not in d:
            continue
        row: dict[str, Any] = {
            "program": d.get("program_source") or d["program"],
            "program_id": d["program"],
            "statements": d.get("statements", 0),
            "translated": d.get("translated", 0),
            "holes": list(d.get("holes", [])),
        }
        if d.get("error"):
            row["error"] = d["error"]
        if d.get("called_holes"):
            row["called_holes"] = list(d["called_holes"])
        if d.get("callees"):
            row["callees"] = list(d["callees"])
        if d.get("cics_links"):
            row["cics_links"] = list(d["cics_links"])
        if d.get("unlisted"):
            row["unlisted"] = list(d["unlisted"])
        corpus_field = d.get("corpus")
        cname = corpus_field.get("name", corpus_name) if isinstance(corpus_field, dict) else (corpus_field or corpus_name)
        by_corpus[str(cname)].append(row)
    return dict(by_corpus)


def render_markdown(res: dict[str, Any], top: int = 25) -> str:
    """Format grouped L0->L1 blockers and downstream-caller ranking as concise Markdown."""
    lines = [
        "# L0 -> L1 Static Det-Sweep Hole Grouping",
        "",
        (
            f"Estates: {len(res['estates'])} | Programs: {res['programs']} | "
            f"Direct whole: {res['direct_whole']} | L1 whole (net of callees): {res['l1_whole']} | "
            f"Blocked solely by callee holes: {res['blocked_only_by_called_holes']} | Refused: {res['refused']}"
        ),
    ]
    if res["cases_mapped"]:
        lines.append(f"Equivalence cases mapped: {res['cases_mapped']} | L1 whole: {res['cases_l1_whole']}")
    lines += [
        "",
        "## Hole classes by domain category",
        "",
        "| Category | Gap classes | Programs blocked | Direct hits | Transitive caller hits | Unblocks whole |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for cat in CATEGORIES:
        c = res["by_category"][cat]
        if c["gap_classes"] or c["programs_blocked"]:
            lines.append(
                f"| `{cat}` | {c['gap_classes']} | {c['programs_blocked']} | "
                f"{c['direct_occurrences']} | {c['caller_occurrences']} | {c['unblocks_whole']} |"
            )

    lines += [
        "",
        f"## Top {min(top, len(res['gaps']))} hole groups ranked by downstream callers unblocked",
        "",
        "| Rank | Category | Callers unblocked | Unblocks whole | Callers touched | Direct progs | Direct only | Cases unblocked | Estates | Hole class |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for idx, g in enumerate(res["gaps"][:top], start=1):
        lines.append(
            f"| {idx} | `{g['category']}` | {g['callers_unblocked']} | {g['unblocks_whole']} | "
            f"{g['callers_touched']} | {g['direct_programs']} | {g['direct_only']} | "
            f"{g['cases_unblocked']} | {g['estates']} | `{g['gap']}` |"
        )
    if res["unlisted_stubs"]:
        lines += [
            "",
            "## Unlisted / unresolved callee stubs ranked by downstream callers blocked",
            "",
            "| Stub | Downstream callers | Direct callsites | Total blocked | Sample callsites |",
            "|---|---:|---:|---:|---|",
        ]
        for s in res["unlisted_stubs"][:top]:
            lines.append(
                f"| `{s['stub']}` | {s['downstream_callers']} | {s['direct_callsites']} | "
                f"{s['total_blocked']} | {', '.join(s['sample_callsites'])} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--survey", type=Path, help="det_survey survey.json or directory containing surveys")
    ap.add_argument("--label", default="before", help="survey label prefix when --survey is a cics_census dir")
    ap.add_argument("--det-port-dir", type=Path, help="directory of det_port result JSONs")
    ap.add_argument("--corpora", type=Path, action="append", help="corpora root(s) for missing cics_links enrichment")
    ap.add_argument("--corpus", action="append", help="filter to these corpus names")
    ap.add_argument(
        "--equivalence-dir",
        type=Path,
        default=REPO_ROOT / "tests" / "equivalence",
        help="directory of equivalence */case.json manifests (default: tests/equivalence)",
    )
    ap.add_argument("--top", type=int, default=25, help="max ranked hole rows to display")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    ap.add_argument("--write", type=Path, help="write report JSON or Markdown to PATH")
    args = ap.parse_args(argv)

    if args.survey is None and args.det_port_dir is None:
        ap.error("pass --survey PATH or --det-port-dir DIR")

    rows_by: dict[str, list[dict[str, Any]]] = {}
    if args.survey is not None:
        rows_by.update(load_survey_input(args.survey, args.label))
    if args.det_port_dir is not None:
        rows_by.update(det_port_dir_to_rows(args.det_port_dir))
    if args.corpus:
        wanted = set(args.corpus)
        rows_by = {k: v for k, v in rows_by.items() if k in wanted}

    roots = list(args.corpora or [])
    env_corp = os.environ.get("GITGALAXY_MAINFRAME_CORPORA") if not roots else None
    if env_corp:
        roots.append(Path(env_corp))

    eq_dir = args.equivalence_dir if args.equivalence_dir and args.equivalence_dir.is_dir() else None
    res = analyze(rows_by, corpora_roots=roots, equivalence_dir=eq_dir)
    out = json.dumps(res, indent=2) + "\n" if args.json else render_markdown(res, top=args.top)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(out, encoding="utf-8")
    print(out, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
