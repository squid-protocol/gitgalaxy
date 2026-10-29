#!/usr/bin/env python3
"""#6072 (ladder tooling 1/3): what a ladder slice must still close, per case or program.

    python tests/tools/ladder_gaps.py CASE|PROGRAM [CASE|PROGRAM ...] [--sweep DIR] [--json] [--corpus-dir DIR]

Lists every uncovered LIVE paragraph and branch outcome of a case's program, measured the way CI's det-sweep measures
(`proof_sweep.py --det-only`: the same proof, SQL-fault tasks included, the same numbers as det_coverage_ledger /
`det_sweep_coverage/<CASE>.json`). The tool never measures: it reads one of, in this order,

  1. SWEEP's `<case>/proof/cobol/coverage.json` (SWEEP is a `proof_sweep.py --det-only --work DIR` directory, or its det/),
  2. that sweep's `sweep.json` row (`uncovered`, `uncovered_paragraphs`),
  3. the case's ledger entry `uncovered` (written by `det_coverage_ledger.py update` from a sweep; a stale entry is
     refused, like every reader of the ledger does),

and otherwise prints the sweep command that produces one.

Each gap carries the COBOL file:line, the IF / EVALUATE condition text and arm (a WHEN arm shows its WHEN line), the
enclosing paragraph, and the GitGalaxy scan of the program source (`galaxyscope --db-only`: function_data paragraph
start_line, complexity, loc, calls_out_to = the PERFORM graph, transfers_to = GO TO): the paragraph's complexity and the
PERFORM path from the entry paragraph. A scan that fails leaves those columns `?`, never a clean zero.

Beside the gaps: the infeasible outcomes already stated for the case (tests/tools/infeasible_outcomes.py; a gap with an
entry is marked and kept), and the oracle refusals that look like gaps -- scenarios the case leaves unjudged by name
(`bounds_refused`, register X8; the sweep's `refused.json`: X8 / X23 "not modelled").
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import cobol_coverage as cov  # noqa: E402
import det_coverage_ledger as ledger  # noqa: E402
import infeasible_outcomes  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402

CASES = ledger.CASES
FORMAT = "ladder-gaps/1"
UNKNOWN = "?"
_COND_STOP = cov.VERBS | {"WHEN", "ELSE", "END-IF", "END-EVALUATE"}
_THEN = re.compile(r"\bTHEN\b")


# ---- which case --------------------------------------------------------------------------------------------
def load_case(case: str, cases_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(((cases_dir or CASES) / case / "case.json").read_text(encoding="utf-8"))


def resolve(names: list[str], cases_dir: Path | None = None) -> list[str]:
    """CASE names as they are; a PROGRAM name expands to every case whose `program` it is. An unknown name is an
    error, never an empty result."""
    root = cases_dir or CASES
    by_program: dict[str, list[str]] = {}
    for f in sorted(root.glob("*/case.json")):
        prog = str(json.loads(f.read_text(encoding="utf-8")).get("program") or "").upper()
        by_program.setdefault(prog, []).append(f.parent.name)
    out: list[str] = []
    for name in names:
        found = [name] if (root / name / "case.json").is_file() else by_program.get(name.upper(), [])
        if not found:
            raise SystemExit(f"ladder_gaps: {name!r} is neither a case under tests/equivalence nor the program of one")
        out += [c for c in found if c not in out]
    return out


def source_path(case: dict[str, Any], corpus: Path | None = None) -> Path:
    if corpus is None:
        import mainframe_corpus as mc  # noqa: PLC0415 -- only to find the pinned clone

        (entry,) = mc.select([case["corpus"]])
        corpus = mc.require_clone(entry)
    return corpus / case["program_source"]


# ---- the uncovered lists -----------------------------------------------------------------------------------
def _split_outcome(s: str) -> tuple[int, str]:
    line, _, outcome = s.partition(":")
    return int(line), outcome


def from_coverage_json(path: Path) -> dict[str, Any]:
    """The proof's own coverage.json: paragraphs {name, line}, branches {line, kind, outcome, unit}."""
    s = json.loads(path.read_text(encoding="utf-8"))
    return {"origin": "coverage.json", "paragraphs": [dict(u) for u in s["paragraphs"]["uncovered"]],
            "branches": [dict(u) for u in s["branches"]["uncovered"]]}  # fmt: skip


def from_strings(origin: str, paragraphs: list[str], branches: list[str]) -> dict[str, Any]:
    """The compact `NAME:line` / `line:outcome` lists of a sweep row or a ledger entry; kind and unit are filled from the
    source's inventory later."""
    paras = []
    for p in paragraphs:
        name, _, line = p.rpartition(":")
        paras.append({"name": name, "line": int(line) if line.isdigit() else None})
    branch = []
    for b in branches:
        if b.startswith(
            infeasible_outcomes.PARAGRAPH_MARK
        ):  # a sweep row's "paragraph:NAME", no outcome (a copybook's)
            name = b[len(infeasible_outcomes.PARAGRAPH_MARK) :]
            if name not in {p["name"] for p in paras}:
                paras.append({"name": name, "line": None})
            continue
        line, outcome = _split_outcome(b)
        branch.append({"line": line, "outcome": outcome})
    return {"origin": origin, "paragraphs": paras, "branches": branch}


def find_sweep_dir(sweep: Path) -> Path | None:
    """SWEEP itself or its det/: the directory holding sweep.json or the per-case proof directories."""
    for base in (sweep, sweep / "det"):
        if base.is_dir() and ((base / "sweep.json").is_file() or next(base.glob("*/proof/cobol"), None)):
            return base
    return None


def read_gaps(
    case: str, sweep: Path | None, led: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, Path | None]:
    """(the case's uncovered lists, the directory its coverage.json / refused.json sit in), or (None, None) when no
    measurement is readable (why: `unavailable`)."""
    if sweep is not None:
        base = find_sweep_dir(sweep)
        if base is None:
            raise SystemExit(f"ladder_gaps: {sweep} is not a proof_sweep.py --det-only work directory")
        proof = base / case / "proof" / "cobol"
        if (proof / "coverage.json").is_file():
            return from_coverage_json(proof / "coverage.json"), proof
        row = (
            json.loads((base / "sweep.json").read_text(encoding="utf-8")).get("det", {})
            if (base / "sweep.json").is_file()
            else {}
        ).get(case)
        if row and row.get("uncovered") is not None:
            return from_strings("sweep.json", row.get("uncovered_paragraphs") or [], row["uncovered"]), None
    entry = led.get(case)
    if entry and "uncovered" in entry:
        last = ledger.last_coverage(case, led)
        if last and not last["stale_inputs"]:
            u = entry["uncovered"]
            return from_strings("ledger", u.get("paragraphs", []), u.get("branches", [])), None
    return None, None


def unavailable(case: str, led: dict[str, dict[str, Any]]) -> str:
    entry = led.get(case)
    if entry is None:
        why = "the ledger has no entry for it"
    elif "uncovered" not in entry:
        why = "its ledger entry holds no uncovered lists (written by the next `det_coverage_ledger.py update`), or none are left"
        if (
            entry["paragraphs"]["covered"] == entry["paragraphs"]["live"]
            and entry["branches"]["covered"] == entry["branches"]["total"]
        ):
            why = "its ledger entry is fully covered"
    else:
        why = "its ledger entry is stale"
    return (f"no readable measurement ({why}); run: tests/tools/box/heavy-run.sh python tests/tools/proof_sweep.py "
            f"--det-only --cases {case} --work DIR --no-ratchet, then pass --sweep DIR")  # fmt: skip


# ---- the program: source text, inventory, the GitGalaxy scan -----------------------------------------------
def raw_lines(src: Path) -> list[str]:
    """The program's lines; an HLASM program's are its lowered COBOL's (#6839: the lines coverage.json names)."""
    text = read_source(src).text
    return (cov.lowered_original(text) or text).split("\n")


def line_text(lines: list[str], n: int) -> str:
    """Area A..B of source line n, literals kept ('' for a comment or a line out of range)."""
    if not 1 <= n <= len(lines):
        return ""
    raw = lines[n - 1].rstrip("\r")
    if cov._FREE.search("\n".join(lines[:5])):  # noqa: SLF001
        return "" if raw.lstrip().startswith("*>") else raw.strip()
    if len(raw) > 6 and raw[6] in "*/D":
        return ""
    return " ".join(cov.gy._trim_fixed_format(raw)[7:72].split())  # noqa: SLF001


def condition_text(lines: list[str], n: int, limit: int = 5) -> str:
    """The IF / EVALUATE / WHEN statement head at line n: its line plus continuation lines until the next statement,
    THEN, a period or `limit` lines."""
    parts: list[str] = []
    for i in range(n, min(n + limit, len(lines) + 1)):
        t = line_text(lines, i)
        if not t:
            continue
        if parts and (t.split()[0].upper().rstrip(".") in _COND_STOP):
            break
        parts.append(t)
        if t.endswith(".") or _THEN.search(t.upper()):
            break
    return " ".join(parts)


def scan_program(src: Path) -> dict[str, dict[str, Any]] | None:
    """{PARAGRAPH (upper): {start_line, complexity, loc, calls, transfers}} from `galaxyscope --db-only` on a copy of
    the source, or None when the scan did not run (the caller marks the columns `?`)."""
    with tempfile.TemporaryDirectory(prefix="ladder-gaps-") as tmp:
        tmp_in, tmp_out = Path(tmp, "in"), Path(tmp, "out")
        tmp_in.mkdir()
        tmp_out.mkdir()
        (tmp_in / src.name).write_bytes(src.read_bytes())
        try:
            subprocess.run([sys.executable, "-m", "gitgalaxy.galaxyscope", str(tmp_in), "--db-only", "--output", str(tmp_out)],  # noqa: S603
                           capture_output=True, check=False, timeout=600)  # fmt: skip
            db = next(iter(sorted(tmp_out.glob("*_galaxy_master.db"))), None)
            return read_scan(db) if db else None
        except (OSError, subprocess.SubprocessError, sqlite3.Error):
            return None


def read_scan(db: Path) -> dict[str, dict[str, Any]] | None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT func_name, start_line, complexity, loc, calls_out_to, transfers_to FROM function_data"
        ).fetchall()
    finally:
        con.close()
    out: dict[str, dict[str, Any]] = {}
    for name, start, cx, loc, calls, transfers in rows:
        if name:
            out[str(name).upper()] = {"start_line": start, "complexity": cx, "loc": loc,
                                      "calls": _names(calls), "transfers": _names(transfers)}  # fmt: skip
    return out or None


def _names(raw: Any) -> list[str]:
    try:
        return [str(x).upper() for x in json.loads(raw or "[]")]
    except (TypeError, ValueError):
        return []


def graph(scan: dict[str, dict[str, Any]], units: list[dict[str, Any]]) -> dict[str, list[str]]:
    """PERFORM + GO TO edges, plus section -> its paragraphs (a PERFORM of a section runs them)."""
    edges: dict[str, list[str]] = {n: [*v["calls"], *v["transfers"]] for n, v in scan.items()}
    section = None
    for u in sorted((u for u in units if u["line"]), key=lambda u: u["line"]):
        name = str(u["name"]).upper()
        if u["kind"] == "section":
            section = name
        elif section:
            edges.setdefault(section, []).append(name)
    return edges


def path_from(edges: dict[str, list[str]], entry: str, target: str) -> list[str] | None:
    """Shortest PERFORM / GO TO path entry -> target, or None when the graph has none."""
    entry, target = entry.upper(), target.upper()
    prev: dict[str, str | None] = {entry: None}
    queue = deque([entry])
    while queue:
        cur = queue.popleft()
        if cur == target:
            path = []
            node: str | None = cur
            while node is not None:
                path.append(node)
                node = prev[node]
            return path[::-1]
        for nxt in edges.get(cur, ()):
            if nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    return None


# ---- the report --------------------------------------------------------------------------------------------
def refusals(case: dict[str, Any], proof: Path | None) -> list[dict[str, str]]:
    """Scenarios left unjudged by name that can look like a gap: `bounds_refused` (X8) and the sweep's refused.json."""
    out = [
        {"scenario": n, "kind": "X8 bounds_refused", "reason": str(r)}
        for n, r in sorted((case.get("bounds_refused") or {}).items())
    ]
    f = proof / "refused.json" if proof else None
    if f and f.is_file():
        for n, r in sorted(json.loads(f.read_text(encoding="utf-8")).items()):
            kind = (
                "X8 bounds"
                if "register X8" in str(r)
                else "X23 not modelled"
                if "not modelled" in str(r)
                else "refused"
            )
            out.append({"scenario": n, "kind": kind, "reason": str(r)})
    return out


def build_case_report(case: str, sweep: Path | None, led: dict[str, dict[str, Any]], corpus: Path | None = None,
                      scan: bool = True) -> dict[str, Any]:  # fmt: skip
    meta = load_case(case)
    gaps, proof = read_gaps(case, sweep, led)
    rep: dict[str, Any] = {"case": case, "program": meta.get("program"), "source": meta.get("program_source"),
                           "refusals": refusals(meta, proof)}  # fmt: skip
    if gaps is None:
        rep["unavailable"] = unavailable(case, led)
        return rep
    src = source_path(meta, corpus)
    lines = raw_lines(src)
    lowered = "\n".join(lines) if cov.lowered_original(read_source(src).text) else None  # #6839: an HLASM program

    def asm_of(n: int | None) -> dict[str, str]:
        at = cov.asm_line(lowered, n) if lowered and n else None
        return {"asm": f"program.asm:{at}"} if at else {}  # (the key only when there is one)

    inv = cov.inventory(src)
    entry = inv.units[0]["name"] if inv.units else None
    kind_unit = {b.line: (b.kind, b.unit) for b in [*inv.branches, *inv.after_transfer]}
    scanned = scan_program(src) if scan else None
    edges = graph(scanned, inv.units) if scanned else {}
    all_stated = infeasible_outcomes.stated(case)
    stated = {(e["line"], e["outcome"]): e for e in all_stated if not infeasible_outcomes.is_paragraph(e)}
    stated_paragraphs = {str(e["unit"]).upper(): e for e in all_stated if infeasible_outcomes.is_paragraph(e)}

    def where(unit: str | None) -> dict[str, Any]:
        info = (scanned or {}).get(str(unit).upper()) if unit else None
        path = path_from(edges, entry, unit) if edges and entry and unit else None
        return {"complexity": info["complexity"] if info else UNKNOWN, "loc": info["loc"] if info else UNKNOWN,
                "perform_path": path if path else UNKNOWN}  # fmt: skip

    paragraphs = [{"name": p["name"], "file": meta["program_source"], "line": p["line"], **asm_of(p["line"]), **where(p["name"])}
                  for p in gaps["paragraphs"]]  # fmt: skip
    for p in paragraphs:  # a whole paragraph stated infeasible (no `line` needed) marks its gap like a branch does
        if (e := stated_paragraphs.get(str(p["name"]).upper())) is not None:
            p["infeasible"] = {"family": e["family"], "reason": e["reason"]}
    branches = []
    for b in gaps["branches"]:
        kind, unit = (b.get("kind"), b.get("unit")) if b.get("kind") else kind_unit.get(b["line"], (UNKNOWN, None))
        unit = unit or b.get("unit")
        arm = re.match(r"WHEN@(\d+)", b["outcome"])
        text_line = int(arm.group(1)) if arm else b["line"]
        row = {"file": meta["program_source"], "line": b["line"], "kind": kind, "outcome": b["outcome"], "unit": unit,
               "condition": condition_text(lines, text_line), **asm_of(b["line"]), **where(unit)}  # fmt: skip
        if (b["line"], b["outcome"]) in stated:
            e = stated[(b["line"], b["outcome"])]
            row["infeasible"] = {"family": e["family"], "reason": e["reason"]}
        branches.append(row)
    rep.update({"origin": gaps["origin"], "entry": entry, "scan": "ok" if scanned else "failed",
                "paragraphs": paragraphs, "branches": branches,
                "infeasible_stated": all_stated})  # fmt: skip
    return rep


def _cell(v: Any) -> str:
    return " > ".join(v) if isinstance(v, list) else str(v).replace("|", "\\|")


def _where(p: dict[str, Any]) -> str:
    """file:line, or the file alone for a paragraph with no line of its own (a COPY member's)."""
    at = f" ({p['asm']})" if "asm" in p else ""  # #6839: the assembler statement a lowered line stands for
    return f"{p['file']}:{p['line']}{at}" if p["line"] is not None else f"{p['file']} (COPY member)"


def render_md(reports: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for r in reports:
        out.append(f"## {r['case']} ({r['program']}, `{r['source']}`)")
        if "unavailable" in r:
            out += ["", r["unavailable"], ""]
        else:
            out.append(f"\nmeasured from {r['origin']}; scan {r['scan']}; entry paragraph `{r['entry']}`; "
                       f"{len(r['paragraphs'])} paragraph gap(s), {len(r['branches'])} branch gap(s)\n")  # fmt: skip
            if r["paragraphs"]:
                out += [
                    "| paragraph | file:line | complexity | loc | PERFORM path | infeasible |",
                    "|---|---|---|---|---|---|",
                ]
                for p in r["paragraphs"]:
                    inf = f"{p['infeasible']['family']}: {p['infeasible']['reason']}" if "infeasible" in p else ""
                    out.append(f"| `{p['name']}` | {_where(p)} | {p['complexity']} | {p['loc']} | "
                               f"{_cell(p['perform_path'])} | {_cell(inf)} |")  # fmt: skip
                out.append("")
            if r["branches"]:
                out += [
                    "| file:line | kind | arm | condition | paragraph | cx | PERFORM path | infeasible |",
                    "|---|---|---|---|---|---|---|---|",
                ]
                for b in r["branches"]:
                    inf = f"{b['infeasible']['family']}: {b['infeasible']['reason']}" if "infeasible" in b else ""
                    out.append(f"| {_where(b)} | {b['kind']} | {b['outcome']} | `{_cell(b['condition'])}` | "
                               f"{b['unit']} | {b['complexity']} | {_cell(b['perform_path'])} | {_cell(inf)} |")  # fmt: skip
                out.append("")
        if r["refusals"]:
            out += ["Oracle refusals that look like gaps (scenarios left unjudged by name):", ""]
            out += [f"- `{x['scenario']}` ({x['kind']}): {x['reason']}" for x in r["refusals"]] + [""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+", metavar="CASE|PROGRAM")
    ap.add_argument("--sweep", type=Path, help="a proof_sweep.py --det-only work directory (default: the ledger)")
    ap.add_argument("--corpus-dir", type=Path, help="the corpus checkout (default: the pinned clone)")
    ap.add_argument("--no-scan", action="store_true", help="skip the galaxyscope scan (path and complexity are ?)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    led = ledger.load()
    reports = [
        build_case_report(c, args.sweep, led, args.corpus_dir, scan=not args.no_scan) for c in resolve(args.names)
    ]
    print(json.dumps({"format": FORMAT, "cases": reports}, indent=1) if args.json else render_md(reports))
    return 0


if __name__ == "__main__":
    sys.exit(main())
