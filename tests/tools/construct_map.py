#!/usr/bin/env python3
"""What each COBOL construct becomes in Java: the deterministic port and the model-written port, paragraph by paragraph.

    python tests/tools/construct_map.py scan --det-root DIR [--model-root DIR ...] --work W
    python tests/tools/construct_map.py analyze --work W [--out DIR]

`scan` puts each converted program's three forms in their own git repos (W/cobol|det|model/<estate>/): the COBOL
program, its det-port service (DIR/<case>/port/service/, as det_port.py run --work leaves it) and its model-written
service (tests/equivalence/<case>/port/service/, or a --model-root holding <case>/port/service/), then scans each
with plain galaxyscope: a det port declares itself (`// gitgalaxy-det-port:`), so the aperture admits it past the
generated-noise gates (#4164).

`analyze` lines the three forms up per COBOL paragraph:
  det    exact: the emitter writes each paragraph as a method under a `/** NAME. */` javadoc;
  model  by evidence: the method's name is the paragraph's (high), a comment before the method names it (medium),
         or a comment inside it does (low). A model method that merges paragraphs is compared with their sum.
Each paragraph is tagged with its dominant construct, from the det translator's own parse of the PROCEDURE DIVISION
(det/stmt.py), and the scanner's per-function metrics (function_data: lines, branches, complexity, tokens) are
compared per construct. The paragraphs where the model's method is far smaller than the det port's are mined for the
model's idioms: CANDIDATE rewrite rules for the det readability layers. A model port is proven only on its case's
scenarios, so a candidate is a hypothesis until a rule built from it is proven on every case that has the construct.
Writes correspondence.json and correspondence.md in --out (default W).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sqlite3
import statistics as st
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path[:0] = [str(TOOLS), str(REPO_ROOT)]

ESTATES = {"aws-mainframe-modernization-carddemo": "carddemo", "cics-banking-sample-application-cbsa": "cbsa",
           "cics-genapp": "genapp"}  # fmt: skip
FORMS = ("cobol", "det", "model")
METRICS = ("loc", "struct_branch", "complexity", "token_mass")

# ---------------------------------------------------------------------------------------------------------- cases


def cases() -> list[dict[str, Any]]:
    """Each estate program once (its first case), with the paths the three forms come from."""
    out, seen = [], set()
    for cj in sorted((REPO_ROOT / "tests" / "equivalence").glob("*/case.json")):
        c = json.loads(cj.read_text(encoding="utf-8"))
        estate = ESTATES.get(c.get("corpus", ""))
        if estate is None or (estate, c["program"].upper()) in seen:
            continue
        seen.add((estate, c["program"].upper()))
        out.append({"case": cj.parent.name, "estate": estate, "program": c["program"].upper(), "corpus": c["corpus"],
                    "source": c["program_source"],
                    "copy_dirs": [*c.get("copy_dirs", ["app/cpy"]), *(c.get("db2") or {}).get("include_dirs", [])]})  # fmt: skip
    return out


def corpus_root(corpus: str) -> Path:
    import mainframe_corpus as mc

    (entry,) = mc.select([corpus])
    return mc.require_clone(entry)


def service_file(case: str, program: str, root: Path) -> Path | None:
    import equivalence_java as ej

    f = root / case / "port" / "service" / f"{ej._service_class(program)}.java"
    return f if f.is_file() else None


# ----------------------------------------------------------------------------------------------------------- scan


def scan(det_root: Path, model_roots: list[Path], work: Path) -> None:
    for form in FORMS:
        if (work / form).exists():
            shutil.rmtree(work / form)
    for c in cases():
        src = corpus_root(c["corpus"]) / c["source"]
        _put(work / "cobol" / c["estate"], src)
        det = service_file(c["case"], c["program"], det_root)
        if det:
            _put(work / "det" / c["estate"], det)
        model = next((m for r in model_roots if (m := service_file(c["case"], c["program"], r))), None)
        if model:
            _put(work / "model" / c["estate"], model)
    for form in FORMS:
        for repo in sorted(p for p in (work / form).iterdir() if p.is_dir()):
            git = ["git", "-c", "user.email=construct-map@local", "-c", "user.name=construct-map"]
            for argv in (["git", "init", "-q"], ["git", "add", "-A"], [*git, "commit", "-qm", "construct map"]):
                subprocess.run(argv, cwd=repo, check=True)  # noqa: S603
            subprocess.run([sys.executable, "-m", "gitgalaxy.galaxyscope", str(repo)], cwd=repo, check=True,  # noqa: S603
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # fmt: skip


def _put(repo: Path, f: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    shutil.copy(f, repo / f.name)


# -------------------------------------------------------------------------------------------------------- metrics


def functions(work: Path, form: str, estate: str) -> dict[str, list[dict[str, Any]]]:
    """file name -> the scanner's function rows (function_data) for that form's estate repo."""
    db = next((work / form / estate).glob("*_master.db"), None)
    if db is None:
        return {}
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = con.execute(f"SELECT f.file_name, fn.func_name, fn.start_line, {', '.join('fn.' + m for m in METRICS)} "  # noqa: S608
                       "FROM function_data fn JOIN file_data f ON f.id = fn.file_id")  # fmt: skip
    out: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        out[r["file_name"]].append(dict(r))
    con.close()
    return out


def _sum(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {m: float(sum(r[m] or 0 for r in rows)) for m in METRICS}


# ----------------------------------------------------------------------------------------------------- constructs

CICS_SCREEN = re.compile(r"\b(SEND\s+(MAP|TEXT|CONTROL)|RECEIVE\s+MAP)\b")
CICS_FILE = re.compile(r"\b(READ|WRITE|REWRITE|DELETE|STARTBR|READNEXT|READPREV|ENDBR|UNLOCK)\b(?!Q)")
CICS_QUEUE = re.compile(r"\b(WRITEQ|READQ|DELETEQ)\b")
SQL_CURSOR = re.compile(r"\b(OPEN|FETCH|CLOSE|DECLARE)\b")
ARITH = {"COMPUTE", "ARITH"}
FILE_IO = {"READ", "WRITE", "REWRITE", "DELETE", "START", "OPEN", "CLOSE"}
STRING_OPS = {"STRING", "UNSTRING", "INSPECT"}
QUIET = {"EXIT", "CONTINUE"}


def exec_tag(text: str) -> str:
    t = " ".join(text.upper().split())
    if t.startswith("EXEC SQL"):
        return "db2-cursor" if SQL_CURSOR.search(t[8:]) else "db2-singleton"
    if CICS_SCREEN.search(t):
        return "cics-screen"
    if CICS_QUEUE.search(t):
        return "cics-queue"
    if CICS_FILE.search(t):
        return "cics-file"
    return "cics-control"


def tag_paragraph(body: list, conditions: set[str]) -> collections.Counter:
    """The constructs in a paragraph's statements, weighted by statement count."""
    tags: collections.Counter = collections.Counter()
    for s, depth in _walk_depth(body):
        k = s.kind
        words = set(re.findall(r"[A-Z0-9][A-Z0-9-]*", s.text.upper()))
        if k in ("MOVE", "INITIALIZE"):
            tags["record-move"] += 1
            if k == "INITIALIZE":
                tags["initialize"] += 1  # a marker inside record-move, not a construct of its own
        elif k == "IF":
            tags["nested-if" if depth >= 2 else "if"] += 1
        elif k == "EVALUATE":
            tags["evaluate"] += 1 + len(s.whens)
        elif k == "PERFORM":
            tags["loop" if (s.data.get("until") is not None or s.data.get("varying") is not None) else "perform"] += 1
        elif k in STRING_OPS:
            tags["string-ops"] += 1
        elif k in ARITH:
            tags["arithmetic"] += 1
        elif k in FILE_IO:
            tags["file-io"] += 1
        elif k == "EXEC":
            tags[exec_tag(s.text)] += 1
        elif k == "SET-TRUE":
            tags["88-level"] += 1
        elif k in ("SET-TO", "SET-BY"):
            tags["record-move"] += 1
        elif k == "GOTO":
            tags["goto"] += 1
        elif k == "DISPLAY":
            tags["display"] += 1
        elif k == "CALL":
            tags["call"] += 1
        elif k == "HOLE":
            tags["hole"] += 1
        elif k not in QUIET:
            tags[k.lower()] += 1
        if k in ("IF", "EVALUATE") and words & conditions:
            tags["88-level"] += 1
    return tags


def _walk_depth(stmts: list, depth: int = 0):
    for s in stmts:
        nest = depth + (1 if s.kind == "IF" else 0)
        yield s, nest
        yield from _walk_depth(s.body, nest)
        yield from _walk_depth(s.orelse, nest)
        for _, b in s.whens:
            yield from _walk_depth(b, depth + 1)
        for b in s.phrases.values():
            yield from _walk_depth(b, depth + 1)


MARKERS = {"initialize"}  # counted for evidence, never a paragraph's construct
IO_TAGS = {"file-io", "cics-file", "cics-screen", "cics-queue", "db2-cursor", "db2-singleton"}
IO_WEIGHT = 3  # one I/O statement is what a paragraph is for: an OPEN with its status IFs is a file-io paragraph


def dominant(tags: collections.Counter) -> str:
    """The paragraph's construct: record-move when MOVEs are most of it, else its heaviest other construct (an I/O
    statement counting IO_WEIGHT)."""
    tags = collections.Counter({t: n for t, n in tags.items() if t not in MARKERS})
    total = sum(tags.values())
    if total == 0:
        return "trivial"
    moves = tags.get("record-move", 0)
    if moves >= 5 and moves / total >= 0.6:
        return "record-move"
    rest = [(n * (IO_WEIGHT if t in IO_TAGS else 1), t) for t, n in tags.items() if t != "record-move"]
    if not rest:
        return "record-move"
    return sorted(rest, key=lambda p: (-p[0], p[1]))[0][1]


def paragraphs(c: dict[str, Any], work: Path) -> list[dict[str, Any]]:
    """The program's paragraphs with statements: name, section, constructs, dominant construct. Copybooks resolve as
    det_port.py resolves them: the case's copy and DCLGEN directories, then the estate's BMS symbolic maps."""
    from gitgalaxy.tools.cobol_to_java.det import cics as C
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as S
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks, program_lines

    root = corpus_root(c["corpus"])
    bms = work / f"bms-{c['corpus']}"
    if not bms.is_dir():
        bms_copybooks([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".bms"
                       and ".git" not in p.parts], bms)  # fmt: skip
    lines = program_lines(root / c["source"], [*(root / d for d in c["copy_dirs"]), bms, C.COPY])
    conds = {c88.name.upper() for rec in L.parse(lines) for item in rec.walk() for c88 in item.conditions}
    out = []
    for p in S.parse(lines).paragraphs:
        if not p.body:
            continue
        tags = tag_paragraph(p.body, conds)
        out.append({"name": p.name.upper(), "section": p.section, "line": p.line, "tags": dict(tags),
                    "construct": dominant(tags), "statements": sum(1 for _ in S.walk(p.body))})  # fmt: skip
    return out


# ------------------------------------------------------------------------------------------------------ alignment

DET_PARA = re.compile(
    r"/\*\* (?P<name>[A-Z0-9][A-Z0-9-]*)\. \*/\s*\n\s*(?:private|public) (?:int|void) (?P<method>\w+)\(\)"
)


def det_methods(java: str) -> dict[str, str]:
    """paragraph name -> det method name, from the emitter's `/** NAME. */` javadoc on each paragraph method."""
    return {m["name"]: m["method"] for m in DET_PARA.finditer(java)}


def method_span(lines: list[str], start: int) -> tuple[int, int]:
    """1-based [first, last] lines of the method whose declaration is at `start` (brace matching; strings and
    comments are skipped coarsely)."""
    depth, opened = 0, False
    for i in range(start - 1, len(lines)):
        text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//.*', "", lines[i])
        for ch in text:
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
                if opened and depth == 0:
                    return start, i + 1
    return start, len(lines)


def leading_comment(lines: list[str], start: int) -> str:
    out, i = [], start - 2
    while i >= 0 and (s := lines[i].strip()) and (s.startswith(("*", "/*", "//", "@")) or s.endswith("*/")):
        out.append(s)
        i -= 1
    return "\n".join(reversed(out))


def norm(name: str) -> str:
    """A paragraph or method name without its numeric prefix, dashes, underscores or case."""
    parts = [p for p in re.split(r"[-_]", name.upper()) if p and not p.isdigit()]
    return "".join(parts) if parts else name.upper()


def model_alignment(java: str, rows: list[dict[str, Any]], names: list[str]) -> dict[str, tuple[str, str]]:
    """paragraph -> (model method, evidence) by the strongest evidence: name > leading comment > inner comment."""
    lines = java.splitlines()
    mentions = {n: re.compile(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])") for n in names if len(n) >= 4}
    best: dict[str, tuple[int, int, str, str]] = {}
    for r in sorted(rows, key=lambda r: r["start_line"]):
        first, last = method_span(lines, r["start_line"])
        lead = leading_comment(lines, first)
        inner = "\n".join(ln for ln in lines[first - 1 : last] if ln.strip().startswith(("//", "*", "/*")))
        for n in names:
            score = 0
            if norm(n) == norm(r["func_name"]):
                score = 3
            elif n in mentions and mentions[n].search(lead):
                score = 2
            elif n in mentions and mentions[n].search(inner):
                score = 1
            if score and (n not in best or score > best[n][0]):
                best[n] = (score, r["start_line"], r["func_name"], ("", "low", "medium", "high")[score])
    return {n: (b[2], b[3]) for n, b in best.items()}


# -------------------------------------------------------------------------------------------------------- idioms

IDIOMS = {
    "switch": (r"\bswitch\s*\(", "EVALUATE / IF-chains as a Java switch"),
    "typed-accessors": (r"\b[a-z]\w*\.(?:get|set)[A-Z]\w*\(", "record fields through typed DTO / entity accessors"),
    "bigdecimal": (r"\bBigDecimal\b", "decimal arithmetic in BigDecimal values, not storage-level COMPUTE"),
    "string-helpers": (r"String\.format|\.formatted\(|\.repeat\(|\.strip\w*\(|\.trim\(\)|\bfit\(|\bpad\w*\(",
                       "String / padding helpers for STRING, MOVE-truncation and edited output"),
    "task-api": (r"\btask\.(?:read|write|rewrite|delete|startBr|readNext|readPrev|endBr|sendMap|receiveMap|link|xctl"
                 r"|returnTo|abend)\w*\(", "CICS commands through CicsTask's typed API"),
    "repository": (r"Repository\b|\b\w*[Rr]epo\w*\.(?:find|save|delete|update)\w*\(",
                   "Db2 / VSAM records through the generated repositories"),
    "optional-stream": (r"\bOptional\b|\.stream\(\)|\.orElse\w*\(|\.ifPresent\(", "Optional / streams for found / "
                        "not-found and record lists"),
    "early-return": (r"\breturn\b", "early returns in place of GO TO / flag-and-fall-through"),
    "boolean-flags": (r"\bboolean\s+\w+\s*=", "88-level switches as boolean locals"),
    "string-concat": (r'"\s*\+|\+\s*"', "string concatenation for STRING ... DELIMITED BY"),
}  # fmt: skip


def idioms(text: str) -> set[str]:
    found = {k for k, (rx, _) in IDIOMS.items() if re.search(rx, text)}
    if len(re.findall(r"\breturn\b", text)) < 2:
        found.discard("early-return")
    if len(re.findall(IDIOMS["typed-accessors"][0], text)) < 3:
        found.discard("typed-accessors")
    return found


def excerpt(java: str, first: int, last: int, n: int = 14) -> str:
    body = [ln for ln in java.splitlines()[first - 1 : last] if ln.strip()]
    pad = min((len(ln) - len(ln.lstrip()) for ln in body), default=0)
    out = [ln[pad:].rstrip()[:118] for ln in body[:n]]
    return "\n".join(out + (["..."] if len(body) > n else []))


# -------------------------------------------------------------------------------------------------------- analyze


def ratio(a: float, b: float) -> float | None:
    return b / a if a else None


def spread(xs: list[float]) -> dict[str, Any]:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return {"n": 0}
    q = st.quantiles(xs, n=4) if len(xs) >= 4 else [xs[0], st.median(xs), xs[-1]]
    return {"n": len(xs), "median": st.median(xs), "q1": q[0], "q3": q[2]}


def analyze(work: Path) -> dict[str, Any]:
    paras, groups, programs = [], [], []
    for c in cases():
        rows = {form: functions(work, form, c["estate"]) for form in FORMS}
        cob_file = Path(c["source"]).name
        cob_rows = {r["func_name"].upper(): r for r in rows["cobol"].get(cob_file, [])}
        det_java_path = next((work / "det" / c["estate"]).glob(f"*{_svc(c)}.java"), None)
        if det_java_path is None:
            continue
        det_java = det_java_path.read_text(encoding="utf-8")
        det_rows = {r["func_name"]: r for r in rows["det"].get(det_java_path.name, [])}
        dmap = det_methods(det_java)
        plist = paragraphs(c, work)
        names = [p["name"] for p in plist]
        model_path = next((work / "model" / c["estate"]).glob(f"{_svc(c)}.java"), None)
        model_java = model_path.read_text(encoding="utf-8") if model_path else ""
        model_rows = rows["model"].get(model_path.name, []) if model_path else []
        malign = model_alignment(model_java, model_rows, names) if model_path else {}
        for p in plist:
            cob = cob_rows.get(p["name"])
            det = det_rows.get(dmap.get(p["name"], ""))
            if cob is None or det is None:
                continue
            rec = {"case": c["case"], "estate": c["estate"], "program": c["program"], **p,
                   "cobol": {m: float(cob[m] or 0) for m in METRICS}, "det": {m: float(det[m] or 0) for m in METRICS},
                   "det_method": det["func_name"], "det_span": method_span(det_java.splitlines(), det["start_line"]),
                   "model_method": malign.get(p["name"], (None, None))[0],
                   "model_evidence": malign.get(p["name"], (None, None))[1]}  # fmt: skip
            paras.append(rec)
        by_method: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for rec in paras:
            if rec["case"] == c["case"] and rec["model_method"]:
                by_method[rec["model_method"]].append(rec)
        mrows = {r["func_name"]: r for r in model_rows}
        for method, members in by_method.items():
            mr = mrows[method]
            span = method_span(model_java.splitlines(), mr["start_line"])
            tags: collections.Counter = collections.Counter()
            for m in members:
                tags.update(m["tags"])
            text = "\n".join(model_java.splitlines()[span[0] - 1 : span[1]])
            groups.append({"case": c["case"], "estate": c["estate"], "program": c["program"], "method": method,
                           "paragraphs": [m["name"] for m in members], "construct": dominant(tags),
                           "evidence": min((m["model_evidence"] for m in members), key=("low", "medium", "high").index),
                           "cobol": _sum([m["cobol"] for m in members]), "det": _sum([m["det"] for m in members]),
                           "model": {m: float(mr[m] or 0) for m in METRICS}, "model_span": span,
                           "idioms": sorted(idioms(text))})  # fmt: skip
        programs.append(_program_totals(c, rows, det_java_path.name, model_path, paras))
    return {"paragraphs": paras, "groups": groups, "programs": programs,
            "constructs": _construct_tables(paras, groups), "candidates": _candidates(groups),
            "todo": _todo_origins(work)}  # fmt: skip


def _svc(c: dict[str, Any]) -> str:
    import equivalence_java as ej

    return ej._service_class(c["program"])


DET_PARTS = (("DTO bridges (COMMAREA / record objects to storage)", r"^(in|fill|out)_"),
             ("storage field declarations", r"^fields\d+$"), ("entity keys", r"^id_"),
             ("PERFORM / GO TO dispatch", r"^(run|perform|paragraph|condition)$"),
             ("entry points (task, batch, link)", r"^(runTask|runBatch|runProgram|handle\w+|execute\w+|\w+Service)$"),
             ("CICS plumbing", r"^(store|cx|dd)$"))  # fmt: skip


def det_parts(fn_rows: list[dict[str, Any]], paragraph_methods: set[str]) -> dict[str, float]:
    """A det port's function lines by what they are: paragraph methods, then the emitter's own parts."""
    out: collections.Counter = collections.Counter()
    for r in fn_rows:
        name = r["func_name"]
        part = (
            "paragraph methods"
            if name in paragraph_methods
            else next((label for label, rx in DET_PARTS if re.match(rx, name)), "other helpers")
        )
        out[part] += float(r["loc"] or 0)
    return dict(out)


def _program_totals(c, rows, det_name, model_path, paras) -> dict[str, Any]:
    mine = [p for p in paras if p["case"] == c["case"]]
    det_all = _sum(rows["det"].get(det_name, []))
    det_para = _sum([p["det"] for p in mine])
    out = {"case": c["case"], "estate": c["estate"], "program": c["program"], "paragraphs": len(mine),
           "cobol": _sum(rows["cobol"].get(Path(c["source"]).name, [])), "det": det_all,
           "det_overhead_loc": det_all["loc"] - det_para["loc"],
           "det_parts": det_parts(rows["det"].get(det_name, []), {p["det_method"] for p in mine})}  # fmt: skip
    if model_path is not None:
        mrows = rows["model"].get(model_path.name, [])
        matched = {p["model_method"] for p in mine if p["model_method"]}
        out["model"] = _sum(mrows)
        out["model_unmatched_loc"] = float(sum(r["loc"] or 0 for r in mrows if r["func_name"] not in matched))
        out["paragraphs_matched"] = sum(1 for p in mine if p["model_method"])
    return out


def _construct_tables(paras, groups) -> list[dict[str, Any]]:
    out = []
    for k in sorted({p["construct"] for p in paras}):
        ps = [p for p in paras if p["construct"] == k]
        gs = [g for g in groups if g["construct"] == k and g["evidence"] != "low"]
        row = {"construct": k, "paragraphs": len(ps), "cases": len({p["case"] for p in ps}),
               "cobol_loc": spread([p["cobol"]["loc"] for p in ps]),
               "det_loc": spread([p["det"]["loc"] for p in ps]),
               "det_x_loc": spread([ratio(p["cobol"]["loc"], p["det"]["loc"]) for p in ps]),
               "det_x_branch": spread([ratio(p["cobol"]["struct_branch"], p["det"]["struct_branch"]) for p in ps]),
               "det_x_complexity": spread([ratio(p["cobol"]["complexity"], p["det"]["complexity"]) for p in ps]),
               "det_x_tokens": spread([ratio(p["cobol"]["token_mass"], p["det"]["token_mass"]) for p in ps]),
               "groups": len(gs), "model_cases": len({g["case"] for g in gs}),
               "model_x_loc": spread([ratio(g["cobol"]["loc"], g["model"]["loc"]) for g in gs]),
               "model_vs_det_loc": spread([ratio(g["det"]["loc"], g["model"]["loc"]) for g in gs])}  # fmt: skip
        out.append(row)
    return out


def _candidates(groups, max_share: float = 0.5, min_det_loc: float = 20) -> list[dict[str, Any]]:
    """Idioms of the model methods at most `max_share` the size of the det methods for the same paragraphs, ranked by
    the det lines those methods save."""
    small = [g for g in groups if g["evidence"] != "low" and g["det"]["loc"] >= min_det_loc
             and g["model"]["loc"] <= max_share * g["det"]["loc"]]  # fmt: skip
    out = []
    for k, (_, what) in IDIOMS.items():
        gs = [g for g in small if k in g["idioms"]]
        if not gs:
            continue
        top = max(gs, key=lambda g: g["det"]["loc"] - g["model"]["loc"])
        out.append({"idiom": k, "what": what, "groups": len(gs), "cases": sorted({g["case"] for g in gs}),
                    "constructs": dict(collections.Counter(g["construct"] for g in gs).most_common()),
                    "det_loc": sum(g["det"]["loc"] for g in gs), "model_loc": sum(g["model"]["loc"] for g in gs),
                    "saved_loc": sum(g["det"]["loc"] - g["model"]["loc"] for g in gs),
                    "example": {"case": top["case"], "method": top["method"], "paragraphs": top["paragraphs"]}})  # fmt: skip
    return sorted(out, key=lambda r: -r["saved_loc"])


GENERATOR_TODO = ("TODO: [AI AGENT]", "is never tested", "TODO: port ")


def _todo_origins(work: Path) -> dict[str, int]:
    out: collections.Counter = collections.Counter()
    for f in (work / "model").glob("*/*.java"):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if "TODO" in ln or "FIXME" in ln:
                out["generator scaffold" if any(g in ln for g in GENERATOR_TODO) else "other"] += 1
    return dict(out)


# --------------------------------------------------------------------------------------------------------- report


def _f(x: Any, d: int = 1) -> str:
    return "-" if x is None else f"{x:,.{d}f}"


def _sp(s: dict[str, Any], d: int = 1) -> str:
    if not s.get("n"):
        return "-"
    return f"{_f(s['median'], d)} ({_f(s['q1'], d)}–{_f(s['q3'], d)})"


def report_md(r: dict[str, Any], work: Path) -> str:
    out = ["# Construct correspondence (generated by tests/tools/construct_map.py)", "",
           "| construct | paragraphs | cases | COBOL lines | det lines | det x lines | det x branches | det x complexity "
           "| model groups | model x lines | model / det lines |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]  # fmt: skip
    out += [
        f"| {t['construct']} | {t['paragraphs']} | {t['cases']} | {_sp(t['cobol_loc'], 0)} | "
        f"{_sp(t['det_loc'], 0)} | {_sp(t['det_x_loc'])} | {_sp(t['det_x_branch'])} | "
        f"{_sp(t['det_x_complexity'])} | {t['groups']} | {_sp(t['model_x_loc'])} | "
        f"{_sp(t['model_vs_det_loc'], 2)} |"
        for t in sorted(r["constructs"], key=lambda t: -t["paragraphs"])
    ]
    parts: collections.Counter = collections.Counter()
    for prog in r["programs"]:
        parts.update(prog["det_parts"])
    total = sum(parts.values()) or 1
    out += ["", "| det port part | lines | share |", "|---|---:|---:|"]
    out += [f"| {k} | {v:,.0f} | {v / total:.0%} |" for k, v in parts.most_common()]
    out += [
        "",
        "| idiom | groups | cases | det lines | model lines | saved | constructs |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for c in r["candidates"]:
        cons = ", ".join(f"{k} {v}" for k, v in c["constructs"].items())
        out.append(f"| {c['idiom']} | {c['groups']} | {len(c['cases'])} | {c['det_loc']:,.0f} | {c['model_loc']:,.0f} "
                   f"| {c['saved_loc']:,.0f} | {cons} |")  # fmt: skip
    out += ["", f"model-port TODO / FIXME lines by origin: {r['todo']}", ""]
    for c in r["candidates"]:
        ex = c["example"]
        g = next(g for g in r["groups"] if g["case"] == ex["case"] and g["method"] == ex["method"])
        est = g["estate"]
        model_java = next((work / "model" / est).glob(f"{_svc(g)}.java")).read_text(encoding="utf-8")
        det_java = next((work / "det" / est).glob(f"{_svc(g)}.java")).read_text(encoding="utf-8")
        para = next(p for p in r["paragraphs"] if p["case"] == g["case"] and p["name"] == g["paragraphs"][0])
        out += [f"### {c['idiom']}: {ex['case']} {', '.join(ex['paragraphs'])}", "",
                f"model `{ex['method']}` ({g['model']['loc']:.0f} lines) vs det ({g['det']['loc']:.0f} lines)", "",
                "```java", excerpt(model_java, *g["model_span"]), "```", "", "```java",
                excerpt(det_java, *para["det_span"]), "```", ""]  # fmt: skip
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--det-root", type=Path, required=True)
    s.add_argument("--model-root", type=Path, action="append", default=[])
    s.add_argument("--work", type=Path, required=True)
    a = sub.add_parser("analyze")
    a.add_argument("--work", type=Path, required=True)
    a.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.cmd == "scan":
        roots = [*args.model_root, REPO_ROOT / "tests" / "equivalence"]
        scan(args.det_root, roots, args.work)
        return 0
    out = args.out or args.work
    out.mkdir(parents=True, exist_ok=True)
    r = analyze(args.work)
    (out / "correspondence.json").write_text(json.dumps(r, indent=1, default=list) + "\n", encoding="utf-8")
    (out / "correspondence.md").write_text(report_md(r, args.work), encoding="utf-8")
    print(f"{len(r['paragraphs'])} paragraphs, {len(r['groups'])} model groups, {len(r['candidates'])} candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
