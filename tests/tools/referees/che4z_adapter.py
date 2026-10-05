r"""Eclipse Che4z COBOL Language Support referee (#4377): the language server's headless
`analysis` command (EPL-2.0; run as an external, unmodified tool, never vendored), as a
referee-facts/1 document: PROGRAM-IDs, paragraphs / sections with extents, PERFORM / GO TO edges,
COPY members and the DATA DIVISION items with their clauses.

    python tests/tools/referees/che4z_adapter.py --corpus <name> --root <corpus clone> \
        --key tests/cobol_mainframe/answer_key/<name>.json --out facts/<name>/che4z.json

Needs the environment variable CHE4Z_SERVER_JAR: server/jar/server.jar unpacked from the
cobol-language-support VSIX release (README.md). Each member runs as
`java -jar server.jar analysis -s <member> -cf=<every copybook dir> --ast`; the AST's first stage
(`START`) is read. Che4z's lines are 0-based. A member whose AST cannot be serialised (the server's
JSON writer overflows its stack on some trees) falls back to a run without `--ast`: it then counts
as `fail` for facts but its diagnostics still say whether it parsed. Per-member time is the
server's own `timings.total` (JVM start-up excluded; it is reported separately as wall time).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import facts as F

JAR_ENV = "CHE4Z_SERVER_JAR"
COPY_EXTS = (".cpy", ".CPY", ".cbl", ".CBL", ".dcl", ".DCL", ".copy", ".cob")
CHANNELS = ["program_ids", "units", "unit_extents", "edges", "copybooks",
            "data_items", "pic", "usage", "occurs", "redefines", "value"]  # fmt: skip
UNIT_TYPES = ("PARAGRAPH", "PROCEDURE_SECTION")


def che4z_version(jar: Path) -> str:
    out = subprocess.run(["unzip", "-p", str(jar), "META-INF/MANIFEST.MF"], capture_output=True, text=True)
    for ln in out.stdout.splitlines():
        if ln.startswith("Version:"):
            return ln.split(":", 1)[1].strip()
    return jar.name


def _line(loc: dict[str, Any], end: bool = False) -> int:
    return int(loc["range"]["end" if end else "start"]["line"]) + 1


def _in_file(node: dict[str, Any], uri: str) -> bool:
    return node.get("locality", {}).get("uri", "").rstrip("/") == uri


def _name(node: dict[str, Any]) -> Optional[str]:
    if node.get("name"):
        return str(node["name"]).upper()
    for c in node.get("children", []):
        if c.get("nodeType") in ("PARAGRAPH_NAME_NODE", "SECTION_NAME_NODE") and c.get("name"):
            return str(c["name"]).upper()
    return None


def _first(clauses: list[Any]) -> Optional[str]:
    if not clauses:
        return None
    c = clauses[0]
    if isinstance(c, dict):
        for k in ("name", "value", "usage", "format"):
            if c.get(k):
                return str(c[k])
        return None
    return str(c)


def _usage(clauses: list[Any]) -> Optional[str]:
    u = _first(clauses)
    return u.replace("_", "-") if u else None  # Che4z writes the enum name, COMP_3


def _occurs(clauses: list[Any]) -> tuple[Optional[int], Optional[int], Optional[str]]:
    if not clauses or not isinstance(clauses[0], dict):
        return None, None, None
    c = clauses[0]
    lo, hi = c.get("from"), c.get("to")
    if hi is None:
        hi = lo
    # The serialised clause carries no DEPENDING ON object (2.5.1): an ODO table scores as a miss.
    dep = c.get("dependingOn")
    if isinstance(dep, dict):
        dep = dep.get("name")
    return lo, hi, (str(dep) if dep else None)


def _value(clauses: list[Any]) -> Optional[str]:
    if not clauses or not isinstance(clauses[0], dict):
        return None
    iv = clauses[0].get("valueIntervals") or []
    return str(iv[0].get("from")) if iv and iv[0].get("from") is not None else None


def ast_facts(doc: dict[str, Any], path: Path) -> dict[str, set[str]]:
    uri = path.resolve().as_uri().replace("file:///", "file:/")
    root = doc["asts"]["START"]
    f: dict[str, set[str]] = {ch: set() for ch in CHANNELS}
    programs: list[str] = []
    spans: dict[str, list[int]] = {}

    def visit(n: dict[str, Any], unit: Optional[str], in_proc: bool, prog: int) -> None:
        t = n.get("nodeType")
        if t == "PROGRAM_ID" and n.get("programId"):
            programs.append(str(n["programId"]).upper())
            f["program_ids"].add(programs[-1])
        if t == "PROGRAM" and programs:
            prog = len(programs)
        if t == "COPY" and n.get("name"):
            f["copybooks"].add(str(n["name"]).upper())
        if t == "VARIABLE_DEFINITION" and _in_file(n, uri):
            name = (n.get("variableName") or {}).get("name") or "FILLER"
            ln = _line(n.get("levelLocality") or n["locality"])
            lo, hi, dep = _occurs(n.get("occursClauses") or [])
            F.merge_item(f, F.item_values(ln, int(n.get("level") or 0), str(name), _first(n.get("picClauses") or []),
                                          _usage(n.get("usageClauses") or []), lo, hi, dep,
                                          _first(n.get("redefinesClauses") or []), _value(n.get("valueClauses") or [])))  # fmt: skip
        if t == "DIVISION" and n.get("divisionType") == "PROCEDURE_DIVISION" and _in_file(n, uri):
            in_proc = True
            spans.setdefault(F.MAIN_LINE, [_line(n["locality"]), 0])
            unit = F.MAIN_LINE
        if t in UNIT_TYPES and _in_file(n, uri):
            name = _name(n)
            if name:
                pid = programs[-1] if programs else None
                unit = F.unit_name(max(len(programs) - 1, 0), pid, name)
                f["units"].add(unit)
                start = _line(n["locality"])
                spans[unit] = [start, start]  # the header; its own sentences extend it below
        if t == "SENTENCE" and unit in spans and _in_file(n, uri):
            # a unit ends at its last sentence: trailing comments and the sentences of a
            # section's paragraphs are not its own (the answer keys' extent contract)
            spans[unit][1] = max(spans[unit][1], _line(n["locality"], end=True))
        if unit is not None and _in_file(n, uri):
            if t == "PERFORM" and (n.get("target") or {}).get("name"):
                f["edges"].add(F.edge_value(unit, "PERFORM", str(n["target"]["name"])))
            if t == "GO_TO":
                for tgt in n.get("targets") or []:
                    f["edges"].add(F.edge_value(unit, "GO_TO", str(tgt)))
        for c in n.get("children", []):
            visit(c, unit, in_proc, prog)

    visit(root, None, False, 0)
    for name, (s, e) in spans.items():
        if e and e >= s:
            f["unit_extents"].add(f"{name} L{s}-{e}")
    return f


def copy_dirs(root: Path) -> list[str]:
    return sorted({str(p.parent) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and p.suffix in COPY_EXTS})


def run_member(jar: Path, path: Path, dirs: list[str], work: Path, ast: bool) -> tuple[Optional[dict[str, Any]], str]:
    cmd = ["java", "-Xss64m", "-jar", str(jar), "analysis", "-s", str(path)]
    cmd += [f"-cf={d}" for d in dirs] + [f"-ce={e.lstrip('.')}" for e in COPY_EXTS] + (["--ast"] if ast else [])
    out = work / "out.json"
    with out.open("wb") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, timeout=600)
    try:
        return json.loads(out.read_text(encoding="utf-8")), ""
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, (proc.stderr.decode("utf-8", "backslashreplace").splitlines() or ["no output"])[0][:200]
    finally:
        out.unlink(missing_ok=True)


def che4z_doc(corpus: str, root: Path, key: dict[str, Any]) -> dict[str, Any]:
    jar = Path(os.environ.get(JAR_ENV) or "")
    if not jar.is_file():
        raise SystemExit(f"{JAR_ENV} does not name the Che4z server.jar (see tests/tools/referees/README.md)")
    doc = F.new_doc("che4z", che4z_version(jar), corpus, CHANNELS)
    dirs = copy_dirs(root)
    scratch = os.environ.get("REFEREES_CACHE")
    if scratch:
        Path(scratch).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="che4z-", dir=scratch))
    wall = 0.0
    for rel in sorted(key.get("programs", {})):
        path = root / rel
        t0 = time.perf_counter()
        out, err = run_member(jar, path, dirs, work, ast=True)
        if out is None:
            diag, err2 = run_member(jar, path, dirs, work, ast=False)
            wall += time.perf_counter() - t0
            syntax = [d for d in (diag or {}).get("diagnostics", []) if d.get("severity") == "ERROR" and d.get("code") != "missing copybook"]  # fmt: skip
            note = "parsed clean" if diag is not None and not syntax else f"{len(syntax)} error diagnostic(s)"
            F.add_file(doc, rel, {}, status="fail", seconds=(diag or {}).get("timings", {}).get("total"),
                       error=f"AST not serialisable ({err}); without --ast: {note if diag else err2}")  # fmt: skip
            continue
        wall += time.perf_counter() - t0
        if "asts" not in out:
            # 2.5.1's CLI prints only {uri, language} and exits 1 on a program with a CALL statement
            F.add_file(doc, rel, {}, status="fail", error="analysis returned no AST and no diagnostics (CLI crash)")
            continue
        syntax = [d for d in out.get("diagnostics", []) if d.get("severity") == "ERROR" and d.get("code") != "missing copybook"]  # fmt: skip
        try:
            facts = ast_facts(out, path)
        except (KeyError, TypeError, ValueError) as e:
            F.add_file(doc, rel, {}, status="fail", error=f"AST walk: {type(e).__name__}: {e}")
            continue
        F.add_file(doc, rel, facts, status="partial" if syntax else "ok", seconds=out.get("timings", {}).get("total"),
                   error=(syntax[0].get("suggestion") or syntax[0].get("message") or "")[:160] if syntax else None)  # fmt: skip
    work.rmdir()
    doc["wall_seconds"] = wall
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    F.dump(che4z_doc(args.corpus, args.root, key), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
