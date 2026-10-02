"""The COBOL side of a Db2 equivalence case: a precompiler for GnuCOBOL.

GnuCOBOL has no Db2 precompiler. As equivalence_cics.py does for EXEC CICS, this one rewrites each EXEC SQL block,
statement by statement, into a CALL of a stub (tests/equivalence/db2/ggsql.c) that runs the statement on a real Db2
through IBM's CLI driver:

    EXEC SQL INSERT INTO T (C1, C2) VALUES (:A, :B) END-EXEC      ->      MOVE 0003 TO GG-SQL-ID
                                                                         CALL 'GGSQL' USING GG-SQL-ID SQLCA A B

and writes the statement table the stub reads: the SQL with its host variables replaced by `?`, and each host
variable's Db2 type, from its COBOL declaration as the Db2 precompiler reads it (CHAR, VARCHAR -- a 49-level length
and text pair --, DECIMAL, SMALLINT / INTEGER / BIGINT), with its indicator variable.

EXEC SQL INCLUDE is expanded (SQLCA is IBM's layout, a DCLGEN member is looked up in the copy directories, any
extension); DECLARE TABLE is dropped; DECLARE CURSOR is remembered, its SELECT run by OPEN. A form not modelled
(WHENEVER, positioned UPDATE / DELETE, dynamic SQL, a host variable array) raises Unsupported by
name -- never a guess. The reader of the data items is the harness's own (cobol_answer_key), not the translator's."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cobol_answer_key as ak

SQLCA = Path(__file__).resolve().parent.parent / "equivalence" / "db2" / "SQLCA.cpy"
STUB = Path(__file__).resolve().parent.parent / "equivalence" / "db2" / "ggsql.c"
MAX_ARGS = 24  # ggsql.c's GGSQL takes 24 host-variable arguments


class Unsupported(Exception):
    """An EXEC SQL form the precompiler does not model."""


@dataclass
class HostVar:
    arg: int
    type: str  # X V Z P B N
    length: int
    digits: int = 0
    scale: int = 0
    signed: int = 0
    indicator: int = -1


@dataclass
class Statement:
    sid: int
    kind: str  # EXEC SELECT1 OPEN FETCH CLOSE COMMIT ROLLBACK
    sql: str = ""
    cursor: str = "-"
    inputs: list[HostVar] = field(default_factory=list)
    outputs: list[HostVar] = field(default_factory=list)


def _area(line: str) -> str:
    """A fixed-format line's area A + B (columns 8-72); a comment line is empty."""
    if len(line) > 6 and line[6] in "*/":
        return ""
    return line[7:72] if len(line) > 7 else ""


_HOST = re.compile(r":\s*([A-Z0-9][A-Z0-9-]*(?:\s+(?:OF|IN)\s+[A-Z0-9][A-Z0-9-]*)?)"
                   r"(?:\s*(?:INDICATOR\s*)?:\s*([A-Z0-9][A-Z0-9-]*))?", re.I)  # fmt: skip


def _find_member(name: str, dirs: list[Path]) -> Path:
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.stem.upper() == name.upper():
                return p
    raise Unsupported(f"EXEC SQL INCLUDE {name}: no member in the copy directories")


def expand_includes(lines: list[str], dirs: list[Path], depth: int = 0) -> list[str]:
    """The program with every EXEC SQL INCLUDE replaced by its member's lines (SQLCA: IBM's layout)."""
    if depth > 8:
        raise Unsupported("EXEC SQL INCLUDE nested too deeply")
    out: list[str] = []
    i = 0
    while i < len(lines):
        area = _area(lines[i]).upper()
        m = re.search(r"\bEXEC\s+SQL\b", area)
        if m:
            j, text = i, ""
            while j < len(lines):
                text += " " + _area(lines[j])
                if re.search(r"\bEND-EXEC\b", text, re.I):
                    break
                j += 1
            inc = re.match(r"\s*EXEC\s+SQL\s+INCLUDE\s+([A-Z0-9#@$-]+)\s+END-EXEC\s*(\.?)", text, re.I)
            if inc:
                name = inc.group(1).upper()
                member = SQLCA if name == "SQLCA" else _find_member(name, dirs)
                body = member.read_text(encoding="latin-1").split("\n")
                out += expand_includes(body, dirs, depth + 1)
                i = j + 1
                continue
        out.append(lines[i])
        i += 1
    return out


def _items(lines: list[str], path: Path) -> list[dict[str, Any]]:
    return ak._data_items(ak.Source(path, list(enumerate(lines, 1))))


class Program:
    """One program's host variables, by name (qualified when the name is not unique)."""

    def __init__(self, items: list[dict[str, Any]]):
        self.items = items
        self.kids: dict[int, list[int]] = {}
        for i, it in enumerate(items):
            if it.get("parent") is not None:
                self.kids.setdefault(it["parent"], []).append(i)

    def ancestors(self, i: int) -> list[str]:
        out = []
        p = self.items[i].get("parent")
        while p is not None:
            out.append(self.items[p]["name"].upper())
            p = self.items[p].get("parent")
        return out

    def find(self, ref: str) -> int:
        parts = [p.upper() for p in re.split(r"\s+(?:OF|IN)\s+|\.", ref.strip(), flags=re.I)]
        name, quals = parts[0], parts[1:]
        hits = [i for i, it in enumerate(self.items) if it["name"].upper() == name
                and all(q in self.ancestors(i) for q in quals)]  # fmt: skip
        if len(hits) != 1:
            raise Unsupported(f"host variable {ref}: {'not declared' if not hits else 'ambiguous'}")
        return hits[0]

    def is_varchar(self, i: int) -> bool:
        kids = self.kids.get(i, [])
        if len(kids) != 2 or any(self.items[k]["level"] != 49 for k in kids):
            return False
        ln, tx = (self.items[k] for k in kids)
        return bool(ln.get("pic")) and re.fullmatch(r"S9\(4\)|S9999", ln["pic"].upper()) is not None and \
            (ln.get("usage") or "").upper() in ("COMP", "COMP-4", "BINARY", "COMP-5") and \
            bool(tx.get("pic")) and re.fullmatch(r"X\(\d+\)|X+", tx["pic"].upper()) is not None  # fmt: skip

    def elementary(self, i: int) -> list[int]:
        """A host variable, or a host structure's elementary members (a VARCHAR pair is one)."""
        it = self.items[i]
        if it.get("pic") or self.is_varchar(i):
            return [i]
        if it.get("occurs"):
            raise Unsupported(f"host variable array {it['name']}")
        out: list[int] = []
        for k in self.kids.get(i, []):
            out += self.elementary(k)
        if not out:
            raise Unsupported(f"host variable {it['name']}: no elementary item")
        return out

    def describe(self, i: int, arg: int) -> HostVar:
        it = self.items[i]
        if self.is_varchar(i):
            text = self.items[self.kids[i][1]]
            return HostVar(arg, "V", ak._pic_bytes(text["pic"], None))
        pic, usage = it["pic"].upper(), (it.get("usage") or "DISPLAY").upper()
        if it.get("sign_separate"):
            raise Unsupported(f"host variable {it['name']}: SIGN SEPARATE")
        if re.fullmatch(r"[XA]+(\(\d+\))?([XA]+(\(\d+\))?)*", pic):
            return HostVar(arg, "X", ak._pic_bytes(pic, None))
        m = re.fullmatch(r"(S?)((?:9(?:\(\d+\))?)+)(?:V((?:9(?:\(\d+\))?)+))?", pic)
        if not m:
            raise Unsupported(f"host variable {it['name']}: PIC {pic}")

        def count(s: Optional[str]) -> int:
            return sum(int(r) if r else 1 for r in re.findall(r"9(?:\((\d+)\))?", s or ""))

        whole, scale = count(m.group(2)), count(m.group(3))
        digits, signed = whole + scale, int(bool(m.group(1)))
        kind = {"DISPLAY": "Z", "COMP-3": "P", "PACKED-DECIMAL": "P", "COMP": "B", "COMP-4": "B", "BINARY": "B",
                "COMP-5": "N"}.get(usage)  # fmt: skip
        if kind is None:
            raise Unsupported(f"host variable {it['name']}: USAGE {usage}")
        if kind in "BN" and scale:
            raise Unsupported(f"host variable {it['name']}: a binary item with a scale")
        return HostVar(arg, kind, ak._pic_bytes(pic, usage), digits, scale, signed)


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


class Precompiler:
    def __init__(self, program: Program):
        self.p = program
        self.statements: list[Statement] = []
        self.cursors: dict[str, str] = {}  # name -> its SELECT (host variables still named)

    def _bind(self, text: str, args: list[str]) -> tuple[str, list[tuple[list[int], Optional[int]]]]:
        """The SQL with every host variable a `?`, and per marker (the elementary items, the indicator)."""
        refs: list[tuple[list[int], Optional[int]]] = []

        def marker(m: re.Match) -> str:
            elems = self.p.elementary(self.p.find(m.group(1)))
            ind = self.p.find(m.group(2)) if m.group(2) else None
            if ind is not None and len(elems) > 1:
                raise Unsupported(f"an indicator array for host structure {m.group(1)}")
            refs.append((elems, ind))
            return ", ".join("?" for _ in elems)

        return _HOST.sub(marker, text), refs

    def _vars(self, refs: list[tuple[list[int], Optional[int]]], args: list[str]) -> list[HostVar]:
        out = []
        for elems, ind in refs:
            for e in elems:
                hv = self.p.describe(e, self._arg(args, e))
                if ind is not None:
                    hv.indicator = self._arg(args, ind)
                out.append(hv)
        return out

    def _arg(self, args: list[str], i: int) -> int:
        name = self.p.items[i]["name"].upper()
        quals = self.p.ancestors(i)
        ref = name + (f" OF {quals[0]}" if quals else "")
        if ref not in args:
            args.append(ref)
        return args.index(ref)

    def statement(self, body: str) -> Optional[tuple[Statement, list[str]]]:
        """One EXEC SQL block's statement and the CALL's arguments, or None (no code: DECLARE)."""
        text = _norm(body)
        u = text.upper()
        verb = u.split()[0] if u else ""
        args: list[str] = []
        sid = len(self.statements) + 1
        if re.match(r"DECLARE\s+\S+\s+TABLE\b", u):
            return None
        cur = re.match(r"DECLARE\s+([A-Z0-9_-]+)\s+(?:(?:SENSITIVE|INSENSITIVE|ASENSITIVE)\s+)?(?:SCROLL\s+)?CURSOR\s+"
                       r"(?:WITH\s+HOLD\s+)?(?:WITH\s+RETURN\s+)?FOR\s+(.*)", text, re.I | re.S)  # fmt: skip
        if cur:
            if re.search(r"\bSCROLL\b", u.split("CURSOR")[0]):
                raise Unsupported("EXEC SQL DECLARE ... SCROLL CURSOR")
            self.cursors[cur.group(1).upper()] = cur.group(2)
            return None
        if verb == "SET" and re.match(r"SET\s*\(?\s*:", text, re.I):  # SET :H = expr: one row of VALUES into :H
            targets, exprs = _assignments(text)
            _, out_refs = self._bind(", ".join(targets), args)
            outputs = self._vars(out_refs, args)
            sql, refs = self._bind(f"VALUES ({', '.join(exprs)})", args)
            st = Statement(sid, "SELECT1", _norm(sql), "-", self._vars(refs, args), outputs)
            self.statements.append(st)
            return st, args
        if verb in ("WHENEVER", "PREPARE", "EXECUTE", "DESCRIBE", "CONNECT", "SET", "CALL", "ALLOCATE", "ASSOCIATE"):
            raise Unsupported(f"EXEC SQL {verb}")
        pos = re.search(r"\bWHERE\s+CURRENT\s+OF\s+([A-Z0-9_-]+)", u)
        if pos and (verb not in ("UPDATE", "DELETE") or pos.group(1) not in self.cursors):
            raise Unsupported(f"EXEC SQL {verb} ... WHERE CURRENT OF {pos.group(1)}: not a declared cursor")
        # a positioned UPDATE / DELETE runs as written: ggsql.c names each cursor (SQLSetCursorName) at its OPEN
        if verb in ("COMMIT", "ROLLBACK"):
            if not re.fullmatch(r"(COMMIT|ROLLBACK)(\s+WORK)?", u):
                raise Unsupported(f"EXEC SQL {u}")
            st = Statement(sid, verb)
        elif verb == "OPEN":
            name = u.split()[1]
            if name not in self.cursors or len(u.split()) > 2:
                raise Unsupported(f"EXEC SQL {u}: an undeclared cursor, or OPEN ... USING")
            sql, refs = self._bind(self.cursors[name], args)
            st = Statement(sid, "OPEN", _norm(sql), name, self._vars(refs, args))
        elif verb == "FETCH":
            m = re.fullmatch(r"FETCH\s+(?:NEXT\s+)?(?:FROM\s+)?([A-Z0-9_-]+)\s+INTO\s+(.*)", text, re.I | re.S)
            if not m:
                raise Unsupported(f"EXEC SQL {u[:60]}")
            _, refs = self._bind(m.group(2), args)
            st = Statement(sid, "FETCH", "", m.group(1).upper(), [], self._vars(refs, args))
        elif verb == "CLOSE":
            st = Statement(sid, "CLOSE", "", u.split()[1])
        elif verb == "SELECT" or verb == "WITH":
            m = re.match(r"(.*?)\bINTO\b(.*?)\bFROM\b(.*)", text, re.I | re.S)
            if not m:
                raise Unsupported("EXEC SQL SELECT without INTO")
            _, out_refs = self._bind(m.group(2), args)
            outputs = self._vars(out_refs, args)
            sql, refs = self._bind(m.group(1) + " FROM " + m.group(3), args)
            st = Statement(sid, "SELECT1", _norm(sql), "-", self._vars(refs, args), outputs)
        elif verb in ("INSERT", "UPDATE", "DELETE", "MERGE", "LOCK"):
            sql, refs = self._bind(text, args)
            st = Statement(sid, "EXEC", _norm(sql), "-", self._vars(refs, args))
        else:
            raise Unsupported(f"EXEC SQL {verb}")
        if len(args) > MAX_ARGS:
            raise Unsupported(f"EXEC SQL with {len(args)} host variables (the stub takes {MAX_ARGS})")
        self.statements.append(st)
        return st, args

    def table(self) -> str:
        """The statement table ggsql.c reads ($GGSQL_STMTS)."""
        out = []
        for s in self.statements:
            out.append(f"S {s.sid} {s.kind} {len(s.inputs)} {len(s.outputs)} {s.cursor}")
            for tag, vs in (("I", s.inputs), ("O", s.outputs)):
                for v in vs:
                    out.append(f"{tag} {v.arg} {v.type} {v.length} {v.digits} {v.scale} {v.signed} {v.indicator}")
            out.append(f"Q {s.sql}")
        return "\n".join(out) + "\n"


def _commas(text: str) -> list[str]:
    """`text` split at commas outside parentheses and quotes (this harness's own reading: the oracle shares no
    parser with the translator it checks)."""
    parts, depth, quote, start = [], 0, "", 0
    for i, ch in enumerate(text):
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "()":
            depth += 1 if ch == "(" else -1
        elif ch == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    return parts + [text[start:].strip()]


def _assignments(text: str) -> tuple[list[str], list[str]]:
    """SET's targets and values (Db2 SQL Reference, SET assignment-statement): `SET :A = e1, :B = e2` or
    `SET (:A, :B) = (e1, e2)`."""
    m = re.fullmatch(r"SET\s*\(([^)]*)\)\s*=\s*\((.*)\)", text.strip(), re.I | re.S)
    if m:
        targets, values = _commas(m.group(1)), _commas(m.group(2))
    else:
        pairs = [re.fullmatch(r"(:[^=]+?)\s*=\s*(.+)", p, re.S) for p in _commas(text.strip()[3:])]
        if not all(pairs):
            raise Unsupported(f"EXEC SQL {text[:60]}")
        targets, values = [p.group(1) for p in pairs if p], [p.group(2) for p in pairs if p]
    if len(targets) != len(values):
        raise Unsupported(f"EXEC SQL {text[:60]}: not as many values as host variables")
    return targets, values


def precompile(source: str, dirs: list[Path], path: Path) -> tuple[str, str]:
    """(the program with its EXEC SQL replaced, the statement table)."""
    lines = expand_includes(source.split("\n"), dirs)
    # the reader takes code areas (columns 8-72): a sequence number in columns 1-6 (COTRTLIC's) is no level number
    pre = Precompiler(Program(_items([_area(ln).upper() for ln in lines if not re.search(r"\bEXEC\s+SQL\b", _area(ln), re.I)],
                                     path)))  # fmt: skip
    out: list[str] = []
    in_procedure = False
    i = 0
    while i < len(lines):
        area = _area(lines[i])
        if re.match(r"\s*PROCEDURE\s+DIVISION\b", area, re.I):
            in_procedure = True
        if not re.search(r"\bEXEC\s+SQL\b", area, re.I):
            out.append(lines[i])
            if re.match(r"\s*WORKING-STORAGE\s+SECTION\s*\.", area, re.I):
                out.append("       01  GG-SQL-ID                PIC 9(4) VALUE 0.")
                out.append("       01  GG-SQL-RC                PIC S9(9) COMP-5 VALUE 0.")
            i += 1
            continue
        j, text = i, area
        while not re.search(r"\bEND-EXEC\b", text, re.I) and j + 1 < len(lines):
            j += 1
            text += "\n" + _area(lines[j])
        m = re.search(r"\bEXEC\s+SQL\b(.*?)\bEND-EXEC\b(\s*\.)?", text, re.I | re.S)
        if not m:
            raise Unsupported("EXEC SQL without END-EXEC")
        before = text[: m.start()]
        done = pre.statement(m.group(1))
        period = "." if m.group(2) else ""
        if before.strip():
            out.append("       " + before.rstrip())
        if done is None:
            if period and in_procedure:  # (a DECLARE among the statements: the sentence still ends)
                out.append("           CONTINUE.")
        else:
            st, args = done
            # EXEC SQL is no CALL in the source: RETURN-CODE is kept around the stub's (whether IBM's DSNHLI call
            # resets it is not measured -- docs/language_status/det_port_design.md, declared differences)
            out.append(f"           MOVE {st.sid:04d} TO GG-SQL-ID")
            out.append("           MOVE RETURN-CODE TO GG-SQL-RC")
            out += [f"           CALL 'GGSQL' USING GG-SQL-ID SQLCA"] + [f"                {a}" for a in args]
            out.append("           MOVE GG-SQL-RC TO RETURN-CODE" + period)
        after = text[m.end() :].strip()
        if after:
            out.append("           " + after)
        i = j + 1
    return "\n".join(out), pre.table()
