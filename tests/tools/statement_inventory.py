#!/usr/bin/env python3
"""
What a deterministic COBOL -> Java translator could take over from the model: every PROCEDURE DIVISION statement of
a set of programs, bucketed by what translating it needs.

    python tests/tools/statement_inventory.py CORPUS_DIR [CORPUS_DIR ...] [--json OUT] [--md OUT]

Buckets (the cheapest one that covers the statement):

  R  runtime-ready     maps 1:1 onto a runtime the generator already emits: a supported EXEC CICS command
                       (equivalence_cics's translator accepts it), file I/O (CobolFiles), DISPLAY (Sysout), ACCEPT
                       FROM DATE / TIME / DAY (MainframeClock), a CALL to a program of the estate or a modelled LE
                       service, GOBACK / STOP RUN / EXIT / CONTINUE, a PERFORM of a paragraph (no THRU).
  S  storage           needs WORKING-STORAGE as bytes and COBOL's MOVE / comparison / arithmetic rules: MOVE,
                       INITIALIZE, SET, IF, EVALUATE, ADD, SUBTRACT, MULTIPLY, DIVIDE, COMPUTE (built once).
  F  control flow      needs COBOL control flow lowered to Java: GO TO, PERFORM ... THRU, NEXT SENTENCE (built once).
  L  library           needs a routine library: STRING, UNSTRING, INSPECT, SEARCH, SORT / MERGE / RELEASE / RETURN,
                       and any statement using an intrinsic FUNCTION the library would have to provide (built once).
  H  hole              needs the model or a modelling decision: an EXEC CICS command the translator refuses, EXEC
                       SQL / DLI, a CALL to a routine neither the estate nor a model provides, a dynamic CALL, ACCEPT
                       from SYSIN / the console, pointer arithmetic (SET ADDRESS OF, SET ... TO ADDRESS), ALTER, ENTRY.

R, S, F and L are deterministic once built; only H is left for the model. A statement is split where a verb starts
one (outside literals and EXEC blocks); conditional phrases (AT END, INVALID KEY, ON SIZE ERROR, WHEN, ELSE) are not
statements, the statements inside them are. Procedure copybooks are expanded (COPY ... REPLACING ==a== BY ==b==).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

VERBS = {
    "ACCEPT", "ADD", "ALTER", "CALL", "CANCEL", "CLOSE", "COMPUTE", "CONTINUE", "DELETE", "DISPLAY", "DIVIDE",
    "ENTRY", "EVALUATE", "EXIT", "GOBACK", "GO", "IF", "INITIALIZE", "INSPECT", "MERGE", "MOVE", "MULTIPLY", "NEXT",
    "OPEN", "PERFORM", "READ", "RELEASE", "RETURN", "REWRITE", "SEARCH", "SET", "SORT", "START", "STOP", "STRING",
    "SUBTRACT", "UNSTRING", "WRITE", "EXEC", "EXECUTE",
}  # fmt: skip
STORAGE = {"MOVE", "INITIALIZE", "SET", "IF", "EVALUATE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "COMPUTE"}
LIBRARY = {"STRING", "UNSTRING", "INSPECT", "SEARCH", "SORT", "MERGE", "RELEASE", "RETURN"}
FILE_IO = {"OPEN", "CLOSE", "READ", "WRITE", "REWRITE", "DELETE", "START"}
MODELLED_CALLS = {"CEEDAYS", "CEE3ABD"}  # tests/equivalence/le, faults/ggabend.c
BUCKETS = ("R", "S", "F", "L", "H")
NAMES = {"R": "runtime-ready", "S": "storage", "F": "control flow", "L": "library", "H": "hole"}

_TOKEN = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|[^\s.,;]+|\.(?=\s|$)")


# ---- source ---------------------------------------------------------------------------------------------------
def code_lines(text: str) -> list[tuple[int, str]]:
    """(line number, columns 8-72) of each non-comment line of a fixed-format source."""
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\n")
        if len(line) >= 7 and line[6] in "*/":
            continue
        if len(line) >= 7 and line[6] == "D":  # debugging line
            continue
        out.append((n, line[7:72] if len(line) > 7 else ""))
    return out


def _find_copy(name: str, index: dict[str, Path]) -> Path | None:
    return index.get(name.upper().strip("'\""))


def expand(lines: list[tuple[int, str]], index: dict[str, Path], depth: int = 0) -> list[tuple[int, str]]:
    """COPY members expanded in place (their lines keep the COPY statement's line number), with simple
    pseudo-text REPLACING."""
    out: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        n, text = lines[i]
        m = re.match(r"\s*COPY\s+([A-Z0-9#@$'\"-]+)", text, re.I)
        if not m or depth > 4:
            out.append((n, text))
            i += 1
            continue
        stmt, j = text, i
        while "." not in re.sub(r"'[^']*'|==.*?==", "", stmt) and j + 1 < len(lines):
            j += 1
            stmt += " " + lines[j][1]
        member = _find_copy(m.group(1), index)
        if member is None:
            out.append((n, f"*GG-UNRESOLVED-COPY {m.group(1)}"))
        else:
            body = code_lines(member.read_text(encoding="latin-1", errors="replace"))
            for a, b in re.findall(r"==(.*?)==\s+BY\s+==(.*?)==", stmt, re.I | re.S):
                body = [(k, t.replace(a.strip(), b.strip())) for k, t in body]
            out += [(n, t) for _, t in expand(body, index, depth + 1)]
        i = j + 1
    return out


def procedure_division(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    for k, (_, text) in enumerate(lines):
        if re.search(r"\bPROCEDURE\s+DIVISION\b", text, re.I):
            return lines[k + 1 :]
    return []


# ---- statements ------------------------------------------------------------------------------------------------
def tokens(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """(line, token): literals whole, EXEC ... END-EXEC as one token, paragraph headers as ('PARA:name')."""
    out: list[tuple[int, str]] = []
    exec_buf: list[str] | None = None
    exec_line = 0
    for n, text in lines:
        if text.startswith("*GG-UNRESOLVED-COPY"):
            out.append((n, text.strip()))
            continue
        header = re.match(r"^ {0,3}([A-Z0-9][A-Z0-9-]*)\s*(SECTION)?\s*\.\s*$", text, re.I)
        if (
            header
            and exec_buf is None
            and header.group(1).upper() not in VERBS | {"END-IF", "END-EVALUATE", "END-PERFORM", "END-EXEC"}
        ):
            out.append((n, "PARA:" + header.group(1).upper()))
            continue
        for tok in _TOKEN.findall(text):
            up = tok.upper()
            if exec_buf is not None:
                exec_buf.append(tok)
                if up.startswith("END-EXEC"):
                    out.append((exec_line, "EXEC:" + " ".join(exec_buf[:-1])))
                    exec_buf = None
                continue
            if up in ("EXEC", "EXECUTE"):
                exec_buf, exec_line = [], n
                continue
            out.append((n, tok))
    return out


def statements(toks: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Split at verbs. Each: {line, verb, text, paragraph}."""
    out: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    para = None
    for n, tok in toks:
        up = tok.upper()
        if up.startswith("PARA:"):
            para = up[5:]
            cur = None
            continue
        if up.startswith("EXEC:") or up.startswith("*GG-UNRESOLVED-COPY"):
            out.append({"line": n, "verb": "EXEC" if up.startswith("EXEC:") else "UNRESOLVED-COPY",
                        "text": tok, "paragraph": para})  # fmt: skip
            cur = None
            continue
        is_literal = tok[:1] in "'\""
        if not is_literal and up in VERBS and not (up == "NEXT" and cur and cur["verb"] in ("READ", "RETURN")):
            cur = {"line": n, "verb": up, "text": tok, "paragraph": para}
            out.append(cur)
        elif cur is not None:
            cur["text"] += " " + tok
    return out


# ---- classification ---------------------------------------------------------------------------------------------
def classify(st: dict[str, Any], estate: set[str]) -> tuple[str, str]:
    """(bucket, reason)."""
    verb, text = st["verb"], st["text"]
    up = text.upper()
    words = up.split()
    if verb == "UNRESOLVED-COPY":
        return "H", "unresolved COPY in the PROCEDURE DIVISION"
    if verb == "EXEC":
        body = text[5:].strip()
        kind = body.split()[0].upper() if body else ""
        if kind == "CICS":
            try:
                import equivalence_cics as ec

                ec.translate_command(body[4:].strip())
                return "R", "EXEC CICS " + _cics_name(body)
            except Exception as e:
                return "H", f"EXEC CICS {_cics_name(body)} (translator refuses: {str(e)[:60]})"
        return "H", f"EXEC {kind or '?'}"
    if "FUNCTION" in words and verb in STORAGE:
        fn = words[words.index("FUNCTION") + 1] if words.index("FUNCTION") + 1 < len(words) else "?"
        return "L", f"intrinsic FUNCTION {fn.split('(')[0]}"
    if verb in FILE_IO or verb == "DISPLAY" or verb in ("GOBACK", "CONTINUE", "EXIT", "STOP"):
        return "R", verb
    if verb == "ACCEPT":
        return (
            ("R", "ACCEPT FROM date/time")
            if re.search(r"\bFROM\s+(DATE|TIME|DAY)", up)
            else ("H", "ACCEPT (SYSIN / console)")
        )
    if verb == "CALL":
        m = re.match(r"CALL\s+'([^']+)'|CALL\s+\"([^\"]+)\"", text, re.I)
        if not m:
            return "H", "dynamic CALL (identifier)"
        target = (m.group(1) or m.group(2)).upper()
        if target in estate:
            return "R", "CALL of an estate program"
        if target in MODELLED_CALLS:
            return "R", f"CALL {target} (modelled)"
        return "H", f"CALL {target} (no program, no model)"
    if verb == "PERFORM":
        return ("F", "PERFORM THRU") if re.search(r"\bTHRU\b|\bTHROUGH\b", up) else ("R", "PERFORM")
    if verb in ("GO", "NEXT"):
        return "F", "GO TO" if verb == "GO" else "NEXT SENTENCE"
    if verb == "SET" and re.search(r"ADDRESS\s+OF|\bTO\s+ADDRESS\b|\bUP\s+BY\b.*POINTER", up):
        return "H", "pointer (SET ADDRESS OF)"
    if verb in ("ALTER", "ENTRY", "CANCEL"):
        return "H", verb
    if verb in LIBRARY:
        return "L", verb
    if verb in STORAGE:
        return "S", verb
    return "H", f"unclassified {verb}"


def _cics_name(body: str) -> str:
    w = body.upper().split()
    return " ".join(w[1:3]) if len(w) > 2 and w[1] in ("SEND", "RECEIVE", "READQ", "WRITEQ", "DELETEQ", "HANDLE",
                                                        "INQUIRE", "ASSIGN") else (w[1] if len(w) > 1 else "?")  # fmt: skip


# ---- the run -----------------------------------------------------------------------------------------------------
def programs(corpus: Path) -> list[Path]:
    exts = {".cbl", ".cob", ".cobol"}
    return sorted(p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in exts)


def copy_index(corpus: Path) -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for p in corpus.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".cpy", ".cbl", ".cob", ".copy", ""):
            idx.setdefault(p.stem.upper(), p)
    return idx


def inventory(corpora: list[Path]) -> dict[str, Any]:
    result: dict[str, Any] = {"corpora": {}}
    for corpus in corpora:
        index = copy_index(corpus)
        progs = programs(corpus)
        estate = {p.stem.upper() for p in progs}
        rows = []
        for p in progs:
            text = p.read_text(encoding="latin-1", errors="replace")
            proc = procedure_division(expand(code_lines(text), index))
            sts = statements(tokens(proc))
            counts: Counter[str] = Counter()
            reasons: Counter[tuple[str, str]] = Counter()
            for st in sts:
                bucket, why = classify(st, estate)
                counts[bucket] += 1
                reasons[(bucket, why)] += 1
            rows.append({"program": str(p.relative_to(corpus)), "statements": len(sts),
                         "buckets": {b: counts[b] for b in BUCKETS},
                         "holes": {why: k for (b, why), k in reasons.items() if b == "H"},
                         "reasons": {f"{b}:{why}": k for (b, why), k in reasons.items()}})  # fmt: skip
        result["corpora"][corpus.name] = rows
    return result


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "--"


def markdown(r: dict[str, Any]) -> str:
    lines = ["# Statement inventory: what a deterministic translator could take over", ""]
    lines += ["| corpus | programs | statements | " + " | ".join(f"{b} {NAMES[b]}" for b in BUCKETS)
              + " | deterministic (R+S+F+L) | programs with no hole |",
              "|---|---|---|" + "---|" * len(BUCKETS) + "---|---|"]  # fmt: skip
    grand: Counter[str] = Counter()
    gn = gp = gz = 0
    for name, rows in r["corpora"].items():
        c: Counter[str] = Counter()
        for row in rows:
            c.update(row["buckets"])
        n = sum(row["statements"] for row in rows)
        zero = sum(1 for row in rows if row["statements"] and not row["buckets"]["H"])
        grand.update(c)
        gn += n
        gp += len(rows)
        gz += zero
        det = n - c["H"]
        lines.append(f"| {name} | {len(rows)} | {n} | " + " | ".join(_pct(c[b], n) for b in BUCKETS)
                     + f" | {_pct(det, n)} | {zero} |")  # fmt: skip
    lines.append(f"| **all** | {gp} | {gn} | " + " | ".join(_pct(grand[b], gn) for b in BUCKETS)
                 + f" | {_pct(gn - grand['H'], gn)} | {gz} |")  # fmt: skip
    holes: Counter[str] = Counter()
    where: dict[str, Counter[str]] = defaultdict(Counter)
    for name, rows in r["corpora"].items():
        for row in rows:
            for why, k in row["holes"].items():
                holes[why] += k
                where[why][name] += k
    lines += ["", "## Holes, by kind", "", "| kind | statements | where |", "|---|---|---|"]
    for why, k in holes.most_common(40):
        lines.append(f"| {why} | {k} | {', '.join(f'{c} {n}' for c, n in where[why].most_common())} |")
    reasons: Counter[str] = Counter()
    for rows in r["corpora"].values():
        for row in rows:
            reasons.update(row["reasons"])
    lines += ["", "## Every statement kind", "", "| bucket:kind | statements |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in reasons.most_common()]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpora", nargs="+", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    args = ap.parse_args(argv)
    r = inventory([c.resolve() for c in args.corpora])
    if args.json:
        args.json.write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    md = markdown(r)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
