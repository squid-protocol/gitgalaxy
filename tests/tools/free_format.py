#!/usr/bin/env python3
"""Free-format GnuCOBOL source as the fixed-format text the det translator and the statement inventory read.

    python tests/tools/free_format.py SRC_DIR OUT_DIR [--define NAME=VALUE ...]

A compile-time rewrite only -- what cobc does before it parses, made explicit -- so the program it yields is the
same program (docs/language_status/cobolcraft.md):

  * `>>IF NAME op INT` / `>>ELSE` / `>>END-IF` resolved with --define (CobolCraft's Makefile passes GCVERSION);
    any other directive is refused by name, never guessed;
  * `*>` comments dropped (outside literals);
  * an active `REPLACE` is refused (the det front end applies COPY ... REPLACING only);
  * each top-level compilation unit (PROGRAM-ID ... END PROGRAM) becomes its own source file, named after its
    PROGRAM-ID; a unit with nested programs stays whole (the translator refuses nesting by name);
  * the text is laid out in fixed format: division, section and paragraph headers and 01 / 77 / FD / SD entries in
    Area A (column 8), everything else in Area B (column 12), long lines broken at a space outside a literal, and a
    literal that does not fit continued with a '-' indicator line.

Copybooks (*.cpy) get the same layout and keep their names. SRC_DIR's tree shape is kept under OUT_DIR."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from gitgalaxy.core.source_text import read_source  # noqa: E402

AREA_A, AREA_B, WIDTH = 7, 11, 72  # 0-based starts of columns 8 and 12; text ends at column 72


class FreeFormatError(Exception):
    pass


def _strip_comment(line: str) -> str:
    """The line without a `*>` comment that starts outside a literal."""
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif line.startswith("*>", i):
            return line[:i]
    return line


_COND = re.compile(r">>\s*IF\s+([A-Z][A-Z0-9-]*)\s*(>=|<=|<>|=|>|<)\s*(-?\d+)\s*$", re.I)


def _holds(m: re.Match, defines: dict[str, int]) -> bool:
    name, op, val = m.group(1).upper(), m.group(2), int(m.group(3))
    if name not in defines:
        raise FreeFormatError(f">>IF {name}: not defined (pass --define {name}=...)")
    v = defines[name]
    return {">=": v >= val, "<=": v <= val, "<>": v != val, "=": v == val, ">": v > val, "<": v < val}[op]


def resolve(lines: list[str], defines: dict[str, int], file: str) -> list[str]:
    """Conditional compilation resolved and comments dropped; one entry per source line kept."""
    out: list[str] = []
    stack: list[tuple[bool, bool]] = []  # (this branch active, some branch taken)
    for n, raw in enumerate(lines, 1):
        text = _strip_comment(raw).rstrip()
        s = text.strip()
        active = all(a for a, _ in stack)
        if s.startswith(">>"):
            m = _COND.match(s)
            if m:
                take = active and _holds(m, defines)
                stack.append((take, take))
            elif re.match(r">>\s*ELSE\s*$", s, re.I):
                if not stack:
                    raise FreeFormatError(f"{file}:{n}: >>ELSE without >>IF")
                _, taken = stack.pop()
                outer = all(a for a, _ in stack)
                stack.append((outer and not taken, True))
            elif re.match(r">>\s*END-IF\s*$", s, re.I):
                if not stack:
                    raise FreeFormatError(f"{file}:{n}: >>END-IF without >>IF")
                stack.pop()
            elif re.match(r">>\s*SOURCE\b", s, re.I):
                pass
            else:
                raise FreeFormatError(f"{file}:{n}: compiler directive not modelled: {s[:40]}")
            continue
        if not active:
            continue
        if re.match(r"REPLACE\b", s, re.I):
            raise FreeFormatError(f"{file}:{n}: REPLACE statement not modelled")
        out.append(text)
    if stack:
        raise FreeFormatError(f"{file}: >>IF without >>END-IF")
    return out


def units(lines: list[str]) -> list[tuple[str, list[str], bool]]:
    """Top-level compilation units: (PROGRAM-ID, lines, has nested programs). Text before the first unit's
    IDENTIFICATION DIVISION goes with that unit."""
    found: list[tuple[str, list[str], bool]] = []
    cur: list[str] = []
    depth, name, nested = 0, "", False
    for line in lines:
        s = line.strip()
        cur.append(line)
        m = re.match(r"PROGRAM-ID\.\s*([A-Za-z0-9_-]+|\"[^\"]+\"|'[^']+')", s, re.I)
        if m:
            depth += 1
            if depth == 1:
                name = m.group(1).strip("\"'")
            else:
                nested = True
        if re.match(r"END\s+PROGRAM\b", s, re.I):
            depth -= 1
            if depth == 0:
                found.append((name, cur, nested))
                cur, name, nested = [], "", False
    if any(x.strip() for x in cur):
        if name:
            found.append((name, cur, nested))
        elif found:  # trailing text after the last unit
            found[-1][1].extend(cur)
    return found


_HEADER = re.compile(r"[A-Z0-9][A-Z0-9-]*(\s+(DIVISION|SECTION))?\b", re.I)


def _area_a(s: str, in_procedure: bool) -> bool:
    u = s.upper()
    if re.match(r"(IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", u):
        return True
    if re.match(r"(PROGRAM-ID|END\s+PROGRAM)\b", u):
        return True
    if re.match(r"[A-Z0-9-]+\s+SECTION\s*\.", u):
        return True
    if re.match(r"(01|77|FD|SD|RD|CD)\b", u):
        return True
    # a paragraph header: a lone name sentence in the PROCEDURE DIVISION
    return (
        in_procedure
        and bool(re.fullmatch(r"[A-Z0-9][A-Z0-9-]*\s*\.", u))
        and u.rstrip(". ") not in ("EXIT", "GOBACK", "CONTINUE", "STOP RUN")
    )


def _pieces(text: str) -> list[str]:
    """Break text into a word / literal stream that can be re-joined with single spaces."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if text.startswith("==", i):  # a pseudo-text delimiter is its own token (separators around it are free)
            out.append("==")
            i += 2
            continue
        j = i
        while j < n and not text[j].isspace():
            if text.startswith("==", j) and j > i:
                break
            if text[j] in "\"'":
                q = text[j]
                j += 1
                while j < n:
                    if text[j] == q:
                        if j + 1 < n and text[j + 1] == q:
                            j += 2
                            continue
                        break
                    j += 1
            j += 1
        out.append(text[i:j])
        i = j
    return out


def layout(lines: list[str]) -> list[str]:
    """Fixed-format lines (columns 8-72 used) for the resolved free-format lines."""
    out: list[str] = []
    in_procedure = False
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if re.match(r"PROCEDURE\s+DIVISION\b", s, re.I):
            in_procedure = True
        elif re.match(r"(DATA|ENVIRONMENT|IDENTIFICATION)\s+DIVISION\b|END\s+PROGRAM\b", s, re.I):
            in_procedure = False
        prefix = " " * (AREA_A if _area_a(s, in_procedure) else AREA_B)
        cur = ""
        for piece in _pieces(s):
            cand = f"{cur} {piece}" if cur else piece
            if len(prefix) + len(cand) <= WIDTH:
                cur = cand
                continue
            if cur:
                out.append(prefix + cur)
                prefix = " " * AREA_B
            cur = piece
            if len(prefix) + len(cur) <= WIDTH:
                continue
            # a piece longer than a line: only a literal may be continued ('-' indicator, resumes after a quote)
            quote = piece[:1]
            if quote not in "\"'":
                raise FreeFormatError(f"a word longer than a line: {piece[:30]}")
            room = WIDTH - len(prefix)
            out.append(prefix + cur[:room])  # the open literal runs to column 72
            rest = cur[room:]
            cont = " " * 6 + "-" + " " * (AREA_B - 7) + quote
            while len(cont) + len(rest) > WIDTH:
                take = WIDTH - len(cont)
                out.append(cont + rest[:take])
                rest = rest[take:]
            prefix, cur = cont, rest
        if cur:
            out.append(prefix + cur)
    return out


def convert_file(src: Path, defines: dict[str, int]) -> list[tuple[str, list[str], bool]]:
    lines = read_source(src).text.splitlines()
    resolved = resolve(lines, defines, str(src))
    return [(name, layout(body), nested) for name, body, nested in units(resolved)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--define", action="append", default=[], help="NAME=INT for >>IF")
    args = ap.parse_args()
    defines = {k.upper(): int(v) for k, v in (d.split("=", 1) for d in args.define)}
    report = {"files": 0, "units": 0, "nested_units": 0, "copybooks": 0, "refused": []}
    for src in sorted(args.src.rglob("*")):
        if not src.is_file() or src.suffix.lower() not in (".cob", ".cbl", ".cpy"):
            continue
        rel = src.relative_to(args.src)
        try:
            if src.suffix.lower() == ".cpy":
                body = layout(resolve(read_source(src).text.splitlines(), defines, str(src)))
                dst = args.out / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text("\n".join(body) + "\n", encoding="utf-8")
                report["copybooks"] += 1
                continue
            report["files"] += 1
            for name, body, nested in convert_file(src, defines):
                dst = args.out / rel.parent / f"{re.sub(r'[^A-Za-z0-9-]', '-', name).upper()}.cbl"
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text("\n".join(body) + "\n", encoding="utf-8")
                report["units"] += 1
                report["nested_units"] += int(nested)
        except FreeFormatError as e:
            report["refused"].append(f"{rel}: {e}")
    print(
        report["files"],
        "files,",
        report["units"],
        "top-level units (",
        report["nested_units"],
        "with nested programs ),",
        report["copybooks"],
        "copybooks;",
        len(report["refused"]),
        "refused",
    )
    for r in report["refused"]:
        print("  refused:", r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
