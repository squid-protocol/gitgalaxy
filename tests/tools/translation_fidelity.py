#!/usr/bin/env python3
"""Translation fidelity along the traceability map (#7532).

Compares each COBOL paragraph with the Java method(s) it became (via
``traceability.json``, ``det`` Javadoc ``/** <PARAGRAPH>. */`` provenance, or
normalized paragraph-to-method name matching) across four structural axes:

- branch outcomes (``IF``/``EVALUATE``/``WHEN``/``PERFORM UNTIL`` vs ``if``/``switch``/``case``/loops)
- calls out (``PERFORM``/``CALL``/``EXEC CICS LINK|XCTL`` vs method invocations)
- size (non-comment LOC ratio)
- data-item reads/writes (normalized identifier overlap)

Reports per-paragraph, per-program, and estate-level fidelity alongside two
null controls: shuffled within-program pairs and unrelated-program pairs.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import random
import re

from gitgalaxy.core.source_text import read_source

_COBOL_BRANCH_RE = re.compile(
    r"\b(?:IF|ELSE|EVALUATE|WHEN|AT\s+END|INVALID\s+KEY|ON\s+EXCEPTION|ON\s+OVERFLOW)\b"
    r"|\bPERFORM\b[^.]*\bUNTIL\b",
    re.IGNORECASE,
)
_COBOL_INLINE_PERFORM_RE = re.compile(r"\bPERFORM\s+(?:UNTIL|VARYING|WITH\s+TEST|\d+\s+TIMES)\b", re.IGNORECASE)
_COBOL_PERFORM_RE = re.compile(r"\bPERFORM\s+([A-Z0-9][A-Z0-9-]*)\b", re.IGNORECASE)
_COBOL_CALL_RE = re.compile(r"\bCALL\s+['\"]?([A-Z0-9][A-Z0-9-]*)['\"]?", re.IGNORECASE)
_COBOL_CICS_CALL_RE = re.compile(r"\bEXEC\s+CICS\s+(?:LINK|XCTL)\b", re.IGNORECASE)
_COBOL_PARA_RE = re.compile(r"^ {0,11}([A-Z0-9][A-Z0-9-]*)\.\s*$", re.IGNORECASE)
_COBOL_PROC_DIV_RE = re.compile(r"^\s*PROCEDURE\s+DIVISION\b", re.IGNORECASE)
_COBOL_STOP_WORDS = frozenset(
    {
        "move",
        "to",
        "from",
        "if",
        "else",
        "end",
        "endif",
        "perform",
        "thru",
        "through",
        "until",
        "varying",
        "by",
        "times",
        "evaluate",
        "when",
        "other",
        "add",
        "subtract",
        "multiply",
        "divide",
        "compute",
        "giving",
        "into",
        "set",
        "initialize",
        "display",
        "accept",
        "read",
        "write",
        "rewrite",
        "delete",
        "open",
        "close",
        "input",
        "output",
        "exec",
        "cics",
        "sql",
        "endexec",
        "call",
        "using",
        "returning",
        "goback",
        "stop",
        "run",
        "exit",
        "continue",
        "not",
        "and",
        "or",
        "equal",
        "spaces",
        "zeros",
        "zero",
        "lowvalues",
        "highvalues",
        "true",
        "false",
        "of",
        "in",
        "is",
        "are",
        "section",
        "procedure",
        "division",
    }
)

_JAVA_METHOD_RE = re.compile(
    r"(?:^|\n)\s*(?:public|private|protected)\s+(?:static\s+|final\s+|synchronized\s+)*"
    r"[\w<>\[\], ?]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{]*\)\s*(?:throws\s+[\w., ]+\s*)?\{",
    re.MULTILINE,
)
_JAVA_BRANCH_RE = re.compile(r"\b(?:if|else\s+if|switch|case|for|while|catch)\b|\?")
_JAVA_CALL_RE = re.compile(r"(?:([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*)?\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_JAVA_CALL_SKIP = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "throw",
        "new",
        "sizeof",
        "super",
        "this",
        "synchronized",
        "initialState",
        "runAll",
        "perform",
        "equals",
        "equalsIgnoreCase",
        "compareTo",
        "toString",
        "valueOf",
        "length",
        "size",
        "isEmpty",
        "get",
        "set",
        "add",
        "put",
        "trim",
        "substring",
        "format",
        "parseInt",
        "parseLong",
        "parseDouble",
    }
)
_JAVA_RUNTIME_RECEIVERS = frozenset(
    {
        "Cobol",
        "CobolBytes",
        "DetCics",
        "DetSql",
        "Funcs",
        "Accept",
        "Hfp",
        "Math",
        "Integer",
        "Long",
        "Double",
        "String",
        "BigDecimal",
        "Optional",
        "List",
        "Map",
        "Set",
        "Collections",
        "Arrays",
        "Objects",
        "System",
        "LocalDateTime",
    }
)
_JAVA_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b")
_JAVA_STOP_WORDS = frozenset(
    {
        "public",
        "private",
        "protected",
        "static",
        "final",
        "void",
        "return",
        "if",
        "else",
        "for",
        "while",
        "switch",
        "case",
        "default",
        "break",
        "continue",
        "try",
        "catch",
        "finally",
        "throw",
        "throws",
        "new",
        "this",
        "super",
        "true",
        "false",
        "null",
        "int",
        "long",
        "double",
        "float",
        "boolean",
        "byte",
        "char",
        "short",
        "string",
        "object",
        "var",
        "class",
    }
)
_COBOL_IDENT_RE = re.compile(r"\b([A-Z][A-Z0-9-]{2,})\b", re.IGNORECASE)
_JAVADOC_PARA_RE = re.compile(r"/\*\*\s*([A-Z0-9][A-Z0-9-]*)\.?\s*\*/", re.IGNORECASE)


@dataclass(frozen=True)
class ParagraphMetrics:
    program: str
    name: str
    loc: int
    branches: int
    calls_out: int
    data_refs: frozenset[str]


@dataclass(frozen=True)
class JavaMethodMetrics:
    program: str
    name: str
    javadoc_para: str | None
    loc: int
    branches: int
    calls_out: int
    data_refs: frozenset[str]


@dataclass(frozen=True)
class PairFidelity:
    program: str
    cobol_para: str
    java_method: str
    matched_by: str
    branch_sim: float
    call_sim: float
    loc_sim: float
    data_sim: float
    fidelity: float
    within_tolerance: bool


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _strip_num_prefix(s: str) -> str:
    return re.sub(r"^[0-9]+[-_]?", "", s.lower())


def _strip_cobol_comments(lines: list[str]) -> list[str]:
    fixed = any(len(raw) >= 7 and raw[6] in ("*", "/") for raw in lines)
    out: list[str] = []
    for raw in lines:
        if len(raw) >= 7 and raw[6] in ("*", "/"):
            continue
        s = raw.rstrip("\r\n")
        if s.lstrip().startswith("*>"):
            continue
        body = s[6:72] if fixed and len(s) > 6 else s
        if "*>" in body:
            body = body.split("*>", 1)[0]
        out.append(body)
    return out


def parse_cobol_paragraphs(cbl_path: Path) -> list[ParagraphMetrics]:
    """Extract paragraph-level structural metrics from a COBOL source file."""
    prog = cbl_path.stem.lower()
    raw_lines = read_source(cbl_path).text.splitlines()
    lines = _strip_cobol_comments(raw_lines)

    in_proc = False
    paras: list[tuple[str, list[str]]] = []
    cur_name: str | None = None
    cur_lines: list[str] = []

    for ln in lines:
        if not in_proc:
            if _COBOL_PROC_DIV_RE.match(ln):
                in_proc = True
            continue
        s = ln.strip()
        if not s:
            continue
        m = _COBOL_PARA_RE.match(ln.rstrip())
        if m and not s.upper().startswith(("END-", "EXIT.", "SECTION.")):
            if cur_name is not None:
                paras.append((cur_name, cur_lines))
            cur_name = m.group(1).upper()
            cur_lines = []
        elif cur_name is not None:
            cur_lines.append(s)

    if cur_name is not None:
        paras.append((cur_name, cur_lines))

    metrics: list[ParagraphMetrics] = []
    for name, body_lines in paras:
        if not body_lines or (len(body_lines) == 1 and body_lines[0].upper() in ("EXIT.", "CONTINUE.")):
            continue
        text = " ".join(body_lines)
        branches = len(_COBOL_BRANCH_RE.findall(text))
        performs = [
            p for p in _COBOL_PERFORM_RE.findall(text) if p.upper() not in ("UNTIL", "VARYING", "WITH", "TIMES")
        ]
        # Exclude inline PERFORM UNTIL/VARYING
        inline_n = len(_COBOL_INLINE_PERFORM_RE.findall(text))
        calls_out = (
            max(0, len(performs) - inline_n)
            + len(_COBOL_CALL_RE.findall(text))
            + len(_COBOL_CICS_CALL_RE.findall(text))
        )
        refs = frozenset(
            _norm_name(tok)
            for tok in _COBOL_IDENT_RE.findall(text)
            if _norm_name(tok) not in _COBOL_STOP_WORDS and len(_norm_name(tok)) >= 3
        )
        metrics.append(
            ParagraphMetrics(
                program=prog,
                name=name,
                loc=len(body_lines),
                branches=branches,
                calls_out=calls_out,
                data_refs=refs,
            )
        )
    return metrics


def _strip_java_comments_keep_javadoc(text: str) -> str:
    # Remove // line comments and non-javadoc /* ... */ blocks while preserving /** ... */.
    text = re.sub(r"/\*(?!\*).*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def parse_java_methods(java_path: Path) -> list[JavaMethodMetrics]:
    """Extract method-level structural metrics from a Java service file."""
    prog = java_path.stem.lower()
    if prog.endswith("service"):
        prog = prog[: -len("service")]
    raw = read_source(java_path).text
    cleaned = _strip_java_comments_keep_javadoc(raw)

    methods: list[JavaMethodMetrics] = []
    for m in _JAVA_METHOD_RE.finditer(cleaned):
        name = m.group(1)
        # Check for /** PARA-NAME. */ immediately preceding the method header.
        prefix = cleaned[max(0, m.start() - 160) : m.start()]
        jdocs = _JAVADOC_PARA_RE.findall(prefix)
        javadoc_para = jdocs[-1].upper() if jdocs else None

        # Brace-match method body.
        idx = m.end()
        depth = 1
        n = len(cleaned)
        while idx < n and depth > 0:
            ch = cleaned[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            idx += 1
        body = cleaned[m.end() : max(m.end(), idx - 1)]
        body_no_doc = re.sub(r"/\*\*.*?\*/", " ", body, flags=re.DOTALL)
        loc = sum(1 for ln in body_no_doc.splitlines() if ln.strip())
        if loc == 0:
            continue
        branches = len(_JAVA_BRANCH_RE.findall(body_no_doc))
        calls_out = sum(
            1
            for recv, callee in _JAVA_CALL_RE.findall(body_no_doc)
            if callee not in _JAVA_CALL_SKIP
            and not callee.startswith(("pack_", "unpack_"))
            and recv not in _JAVA_RUNTIME_RECEIVERS
        )
        refs = frozenset(
            _norm_name(tok)
            for tok in _JAVA_IDENT_RE.findall(body_no_doc)
            if tok.lower() not in _JAVA_STOP_WORDS and len(_norm_name(tok)) >= 3
        )
        methods.append(
            JavaMethodMetrics(
                program=prog,
                name=name,
                javadoc_para=javadoc_para,
                loc=loc,
                branches=branches,
                calls_out=calls_out,
                data_refs=refs,
            )
        )
    return methods


def load_traceability_map(trace_path: Path | None) -> dict[tuple[str, str], str]:
    """Load optional ``traceability.json`` mapping ``(program, cobol_para) -> java_method``."""
    if trace_path is None or not trace_path.exists():
        return {}
    data = json.loads(trace_path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], str] = {}
    for art in data.get("artifacts", []):
        sym = str(art.get("symbol", ""))
        if "#" not in sym:
            continue
        cls_name, meth = sym.split("#", 1)
        prog = cls_name.lower().removesuffix("service")
        for fact in art.get("facts", []):
            para = fact.get("paragraph") or fact.get("cobol_paragraph")
            if para:
                out[(prog, str(para).upper())] = meth
    return out


def score_pair(
    para: ParagraphMetrics,
    meth: JavaMethodMetrics,
    matched_by: str,
    tolerance: float = 0.55,
) -> PairFidelity:
    """Compute per-paragraph translation fidelity across branch, call, size, and data axes."""
    branch_sim = 1.0 - abs(para.branches - meth.branches) / max(para.branches, meth.branches, 1)
    call_sim = 1.0 - abs(para.calls_out - meth.calls_out) / max(para.calls_out, meth.calls_out, 1)
    loc_sim = min(para.loc, meth.loc) / max(para.loc, meth.loc, 1)
    union = para.data_refs | meth.data_refs
    data_sim = (len(para.data_refs & meth.data_refs) / len(union)) if union else 1.0
    fidelity = 0.35 * branch_sim + 0.30 * call_sim + 0.20 * loc_sim + 0.15 * data_sim
    return PairFidelity(
        program=para.program,
        cobol_para=para.name,
        java_method=meth.name,
        matched_by=matched_by,
        branch_sim=branch_sim,
        call_sim=call_sim,
        loc_sim=loc_sim,
        data_sim=data_sim,
        fidelity=fidelity,
        within_tolerance=fidelity >= tolerance,
    )


def pair_program(
    paras: list[ParagraphMetrics],
    methods: list[JavaMethodMetrics],
    trace_map: dict[tuple[str, str], str] | None = None,
    tolerance: float = 0.55,
) -> list[PairFidelity]:
    """Pair COBOL paragraphs with Java methods along traceability/Javadoc/name signals."""
    trace_map = trace_map or {}
    by_name = {m.name: m for m in methods}
    by_norm = defaultdict(list)
    for m in methods:
        by_norm[_norm_name(m.name)].append(m)
    by_javadoc = {m.javadoc_para: m for m in methods if m.javadoc_para}

    used_methods: set[str] = set()
    pairs: list[PairFidelity] = []

    for p in paras:
        meth: JavaMethodMetrics | None = None
        how = ""
        t_meth = trace_map.get((p.program, p.name))
        if t_meth and t_meth in by_name and t_meth not in used_methods:
            meth = by_name[t_meth]
            how = "traceability"
        elif p.name in by_javadoc and by_javadoc[p.name].name not in used_methods:
            meth = by_javadoc[p.name]
            how = "javadoc"
        else:
            p_full = _norm_name(p.name)
            p_strip = _norm_name(_strip_num_prefix(p.name))
            for cand_key in (p_full, p_strip):
                cands = [m for m in by_norm.get(cand_key, ()) if m.name not in used_methods]
                if len(cands) == 1:
                    meth = cands[0]
                    how = "name"
                    break
        if meth is not None:
            used_methods.add(meth.name)
            pairs.append(score_pair(p, meth, how, tolerance=tolerance))
    return pairs


def evaluate_fidelity(
    cobol_dir: Path,
    java_dir: Path,
    trace_path: Path | None = None,
    *,
    tolerance: float = 0.55,
    draws: int = 100,
    seed: int = 42,
) -> dict:
    """Evaluate per-paragraph, per-program, and estate-level fidelity against null controls."""
    trace_map = load_traceability_map(trace_path)
    cbl_by_prog = {
        p.stem.lower(): p for p in sorted(cobol_dir.rglob("*")) if p.is_file() and p.suffix.lower() in (".cbl", ".cob")
    }
    java_by_prog: dict[str, Path] = {}
    for jp in sorted(java_dir.rglob("*.java")):
        stem = jp.stem.lower().removesuffix("service")
        java_by_prog[stem] = jp

    common = sorted(set(cbl_by_prog) & set(java_by_prog))
    all_paras: dict[str, list[ParagraphMetrics]] = {}
    all_methods: dict[str, list[JavaMethodMetrics]] = {}
    all_pairs: list[PairFidelity] = []
    per_program: list[dict] = []

    for prog in common:
        paras = parse_cobol_paragraphs(cbl_by_prog[prog])
        methods = parse_java_methods(java_by_prog[prog])
        if not paras or not methods:
            continue
        all_paras[prog] = paras
        all_methods[prog] = methods
        pairs = pair_program(paras, methods, trace_map=trace_map, tolerance=tolerance)
        if not pairs:
            continue
        all_pairs.extend(pairs)
        mean_fid = sum(x.fidelity for x in pairs) / len(pairs)
        tol_share = sum(1 for x in pairs if x.within_tolerance) / len(pairs)
        per_program.append(
            {
                "program": prog,
                "cobol_paragraphs": len(paras),
                "java_methods": len(methods),
                "paired": len(pairs),
                "mean_fidelity": round(mean_fid, 4),
                "within_tolerance": round(tol_share, 4),
            }
        )

    if not all_pairs:
        return {"error": "no paired paragraphs found", "common_programs": len(common)}

    observed = sum(x.fidelity for x in all_pairs) / len(all_pairs)
    tol_share = sum(1 for x in all_pairs if x.within_tolerance) / len(all_pairs)

    rng = random.Random(seed)
    # Null 1: shuffled within-program pairs
    para_lookup = {(p.program, p.name): p for ps in all_paras.values() for p in ps}
    meth_lookup = {(m.program, m.name): m for ms in all_methods.values() for m in ms}
    pairs_by_prog: dict[str, list[PairFidelity]] = defaultdict(list)
    for pf in all_pairs:
        pairs_by_prog[pf.program].append(pf)

    shuffled_scores: list[float] = []
    unrelated_scores: list[float] = []
    all_meth_list = [m for ms in all_methods.values() for m in ms]

    for _ in range(draws):
        s_vals: list[float] = []
        u_vals: list[float] = []
        for prog, plist in pairs_by_prog.items():
            ms = [meth_lookup[(prog, x.java_method)] for x in plist]
            if len(ms) >= 2:
                shuf = ms[:]
                rng.shuffle(shuf)
                for pf, m_shuf in zip(plist, shuf, strict=True):
                    s_vals.append(score_pair(para_lookup[(prog, pf.cobol_para)], m_shuf, "null", tolerance).fidelity)
            other_ms = [m for m in all_meth_list if m.program != prog]
            if other_ms:
                for pf in plist:
                    m_unrel = rng.choice(other_ms)
                    u_vals.append(score_pair(para_lookup[(prog, pf.cobol_para)], m_unrel, "null", tolerance).fidelity)
        if s_vals:
            shuffled_scores.append(sum(s_vals) / len(s_vals))
        if u_vals:
            unrelated_scores.append(sum(u_vals) / len(u_vals))

    shuf_mean = sum(shuffled_scores) / len(shuffled_scores) if shuffled_scores else 0.0
    unrel_mean = sum(unrelated_scores) / len(unrelated_scores) if unrelated_scores else 0.0
    outliers = [asdict(x) for x in sorted(all_pairs, key=lambda x: x.fidelity)[:10]]

    return {
        "common_programs": len(common),
        "evaluated_programs": len(per_program),
        "total_paired": len(all_pairs),
        "observed_fidelity": round(observed, 4),
        "within_tolerance_share": round(tol_share, 4),
        "shuffled_null": round(shuf_mean, 4),
        "gap_vs_shuffled": round(observed - shuf_mean, 4),
        "unrelated_null": round(unrel_mean, 4),
        "gap_vs_unrelated": round(observed - unrel_mean, 4),
        "per_program": per_program,
        "outliers": outliers,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure COBOL->Java translation fidelity along traceability map (#7532).")
    ap.add_argument("--cobol-dir", type=Path, required=True)
    ap.add_argument("--java-dir", type=Path, required=True)
    ap.add_argument("--traceability", type=Path, default=None)
    ap.add_argument("--tolerance", type=float, default=0.55)
    ap.add_argument("--draws", type=int, default=100)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    res = evaluate_fidelity(
        args.cobol_dir,
        args.java_dir,
        args.traceability,
        tolerance=args.tolerance,
        draws=args.draws,
    )
    if args.json:
        print(json.dumps(res, indent=2))
        return 0
    if "error" in res:
        print(res["error"])
        return 1
    print(
        f"Estate fidelity: {res['observed_fidelity']:.3f} "
        f"(within_tol={res['within_tolerance_share'] * 100:.1f}%, n={res['total_paired']} pairs across {res['evaluated_programs']} programs)"
    )
    print(
        f"Controls: shuffled_null={res['shuffled_null']:.3f} (gap={res['gap_vs_shuffled']:+.3f}) | "
        f"unrelated_null={res['unrelated_null']:.3f} (gap={res['gap_vs_unrelated']:+.3f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
