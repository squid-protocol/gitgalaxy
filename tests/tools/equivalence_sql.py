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
(a WHENEVER not GO TO or CONTINUE, dynamic SQL, a host variable array) raises Unsupported by
name -- never a guess. The reader of the data items is the harness's own (cobol_answer_key), not the translator's."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cobol_answer_key as ak

SQLCA = Path(__file__).resolve().parent.parent / "equivalence" / "db2" / "SQLCA.cpy"
SQLDA = SQLCA.with_name("SQLDA.cpy")  # declared only: dynamic SQL is refused
STUB = Path(__file__).resolve().parent.parent / "equivalence" / "db2" / "ggsql.c"
MAX_ARGS = 32  # ggsql.c's GGSQL takes 32 host-variable arguments


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
    program: str = "-"  # #4173: the statement's program and the line of its EXEC SQL in that program's source --
    line: int = 0  # the key a SQL fault names, the same one the det port's DetSql calls carry (PROGRAM:LINE)
    verb: str = ""  # the SQL's first word (INSERT, UPDATE, DELETE, SELECT, VALUES, ...): a fault's default SQLCODE
    hold: bool = False  # #4269: an OPEN of a cursor declared WITH HOLD (a COMMIT leaves it open)
    scroll: bool = False  # #4269: an OPEN of a cursor declared SCROLL, or a FETCH with an orientation
    orient: str = ""  # #4269: that FETCH's orientation (PRIOR FIRST LAST CURRENT ABSOLUTE RELATIVE)
    orient_n: int | None = None  # #4269: its integer constant; a host variable's value is the statement's one input
    rowset: bool = False  # #4269: a FETCH ROWSET: the outputs are tables, one per column; orient_n is FOR n ROWS' n


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
    return [ln for ln, _ in expand_includes_traced(lines, dirs, depth)]


def expand_includes_traced(lines: list[str], dirs: list[Path], depth: int = 0) -> list[tuple[str, int]]:
    """expand_includes, each line with its line number in the source it is written in (#4173): the program's own,
    or, for a line an INCLUDE brought in, the member's -- as the det port numbers a statement (its EXEC SQL's line
    in the file it is written in, under the program that runs it)."""
    if depth > 8:
        raise Unsupported("EXEC SQL INCLUDE nested too deeply")
    out: list[tuple[str, int]] = []
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
                member = {"SQLCA": SQLCA, "SQLDA": SQLDA}.get(name) or _find_member(name, dirs)
                body = member.read_text(encoding="latin-1").split("\n")
                out += expand_includes_traced(body, dirs, depth + 1)
                i = j + 1
                continue
        out.append((lines[i], i + 1))
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
        if (it.get("occurs_max") or 1) > 1:  # (#4269: a table is a column of a FETCH ROWSET only: _rowset_fetch)
            raise Unsupported(f"host variable array {it['name']}")
        if it.get("pic") or self.is_varchar(i):
            return [i]
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
        m = re.fullmatch(r"(S?)((?:9(?:\(\d+\))?)+)(?:V((?:9(?:\(\d+\))?)*))?", pic)  # a DCLGEN writes S9(11)V
        if not m:
            raise Unsupported(f"host variable {it['name']}: PIC {pic}")

        def count(s: str | None) -> int:
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
    def __init__(self, program: Program, first_id: int = 1):
        self.p = program
        self.first_id = first_id  # several programs in one task share one table: each its own range of ids
        self.statements: list[Statement] = []
        self.cursors: dict[str, str] = {}  # name -> its SELECT (host variables still named)
        self.hold: set[str] = set()  # #4269: the cursors declared WITH HOLD
        self.scroll: set[str] = set()  # #4269: the cursors declared INSENSITIVE / ASENSITIVE SCROLL
        self.rowset: set[str] = set()  # #4269: the cursors declared WITH ROWSET POSITIONING
        self.whenever: dict[str, str] = {}  # #4269: WHENEVER condition -> its GO TO label, in force from here
        self.prepared: dict[str, str] = {}  # #4269: PREPARE name FROM 'literal' -> the text, from here on

    def _bind(self, text: str, args: list[str]) -> tuple[str, list[tuple[list[int], int | None]]]:
        """The SQL with every host variable a `?`, and per marker (the elementary items, the indicator)."""
        refs: list[tuple[list[int], int | None]] = []

        def marker(m: re.Match) -> str:
            elems = self.p.elementary(self.p.find(m.group(1)))
            ind = self.p.find(m.group(2)) if m.group(2) else None
            if ind is not None and len(elems) > 1:
                raise Unsupported(f"an indicator array for host structure {m.group(1)}")
            refs.append((elems, ind))
            return ", ".join("?" for _ in elems)

        return _HOST.sub(marker, text), refs

    def _vars(self, refs: list[tuple[list[int], int | None]], args: list[str]) -> list[HostVar]:
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
        # (#4269: a host-variable table is passed by its first element: cobc wants the subscript)
        ref = name + (f" OF {quals[0]}" if quals else "")
        ref += " (1)" if (self.p.items[i].get("occurs_max") or 1) > 1 else ""
        if ref not in args:
            args.append(ref)
        return args.index(ref)

    def _rowset_fetch(self, sid: int, text: str, args: list[str]) -> Statement:
        """#4269: FETCH [NEXT] ROWSET FROM cursor FOR n ROWS INTO :A1, :A2 -- each a PIC item with OCCURS, a column."""
        m = re.fullmatch(r"FETCH\s+(?:NEXT\s+)?ROWSET\s+(?:FROM\s+)?([A-Z0-9_-]+)\s+FOR\s+(\d+|:[A-Z0-9_-]+)\s+ROWS?"
                         r"\s+INTO\s+(.*)", text, re.I | re.S)  # fmt: skip
        if not m:
            raise Unsupported(f"EXEC SQL {text[:60]}")
        cursor = m.group(1).upper()
        if cursor not in self.rowset:
            raise Unsupported(f"EXEC SQL FETCH ROWSET {cursor}: the cursor is not declared WITH ROWSET POSITIONING")
        refs: list[tuple[list[int], int | None]] = []
        for h in _HOST.finditer(m.group(3)):
            i = self.p.find(h.group(1))
            if not self.p.items[i].get("pic") or (self.p.items[i].get("occurs_max") or 1) < 2 or self.p.is_varchar(i):
                raise Unsupported(f"FETCH ROWSET {cursor}: :{h.group(1)} is not a PIC item with OCCURS")
            refs.append(([i], self.p.find(h.group(2)) if h.group(2) else None))
        st = Statement(sid, "FETCH", "", cursor, [], self._vars(refs, args), rowset=True)
        if m.group(2).startswith(":"):
            _, nrefs = self._bind(m.group(2), args)
            st.inputs = self._vars(nrefs, args)
        else:
            st.orient_n = int(m.group(2))
        return st

    def statement(self, body: str) -> tuple[Statement, list[str]] | None:
        """One EXEC SQL block's statement and the CALL's arguments, or None (no code: DECLARE)."""
        text = _norm(body)
        u = text.upper()
        verb = u.split()[0] if u else ""
        args: list[str] = []
        sid = self.first_id + len(self.statements)
        if re.match(r"DECLARE\s+\S+\s+TABLE\b", u):
            return None
        cur = re.match(r"DECLARE\s+([A-Z0-9_-]+)\s+(?:(?:SENSITIVE|INSENSITIVE|ASENSITIVE)\s+)?(?:SCROLL\s+)?CURSOR\s+"
                       r"(?:WITH\s+(?:HOLD|RETURN|ROWSET\s+POSITIONING)\s+)*FOR\s+(.*)", text, re.I | re.S)  # fmt: skip
        if cur:
            words = u.split("CURSOR")[0].split()
            if "SCROLL" in words:
                if "SENSITIVE" in words or "DYNAMIC" in words:
                    raise Unsupported("EXEC SQL DECLARE ... SENSITIVE SCROLL CURSOR")
                self.scroll.add(cur.group(1).upper())
            self.cursors[cur.group(1).upper()] = cur.group(2)
            if re.search(r"\bCURSOR\s+WITH\s+HOLD\b", u):
                self.hold.add(cur.group(1).upper())
            if re.search(r"\bWITH\s+ROWSET\s+POSITIONING\b", u):
                self.rowset.add(cur.group(1).upper())
            return None
        if verb == "SET" and re.match(r"SET\s*\(?\s*:", text, re.I):  # SET :H = expr: one row of VALUES into :H
            targets, exprs = _assignments(text)
            _, out_refs = self._bind(", ".join(targets), args)
            outputs = self._vars(out_refs, args)
            sql, refs = self._bind(f"VALUES ({', '.join(exprs)})", args)
            st = Statement(sid, "SELECT1", _norm(sql), "-", self._vars(refs, args), outputs)
            self.statements.append(st)
            return st, args
        if verb == "WHENEVER":  # #4269: IBM's precompiler tests the SQLCA after every later statement in the text
            w = re.fullmatch(r"WHENEVER\s+(SQLERROR|NOT\s+FOUND|SQLWARNING)\s+(?:(CONTINUE)|GO\s*TO\s+:?([A-Z0-9_-]+))",
                             u)  # fmt: skip
            if not w:
                raise Unsupported(f"EXEC SQL {u[:60]}")
            cond = " ".join(w.group(1).split())
            if w.group(2):
                self.whenever.pop(cond, None)
            else:
                self.whenever[cond] = w.group(3)
            return None
        if verb == "EXECUTE" and re.match(r"EXECUTE\s+IMMEDIATE\b", u):
            # #4269: EXECUTE IMMEDIATE 'INSERT ... VALUES ...' runs as written (the det port's DetSql.savepoint path)
            lit = re.fullmatch(r"EXECUTE\s+IMMEDIATE\s+'((?:[^']|'')*)'", text, re.I)
            if not lit:
                raise Unsupported(f"EXEC SQL {u[:60]}: only a string literal as the statement text is modelled")
            inner = lit.group(1).replace("''", "'").strip()
            self._dynamic_insert(inner, "EXECUTE IMMEDIATE")
            st = Statement(sid, "EXEC", _norm(inner))
            self.statements.append(st)
            return st, args
        prep = re.fullmatch(r"PREPARE\s+([A-Z0-9_-]+)\s+FROM\s+'((?:[^']|'')*)'", text, re.I)
        if verb == "PREPARE" and prep:  # #4269: the text is kept; the statement runs a no-op (the port's PREPARE_NOOP)
            inner = prep.group(2).replace("''", "'").strip()
            self._dynamic_insert(inner, "PREPARE")
            name = prep.group(1).upper()
            if self.prepared.get(name, inner) != inner:
                raise Unsupported(f"EXEC SQL PREPARE {name}: prepared from more than one literal text")
            self.prepared[name] = inner
            st = Statement(sid, "EXEC", "VALUES 1")
            self.statements.append(st)
            return st, args
        ex = re.fullmatch(r"EXECUTE\s+([A-Z0-9_-]+)(?:\s+USING\s+(.+))?", text, re.I | re.S)
        if verb == "EXECUTE" and ex:  # #4269: EXECUTE name [USING :H, ...] of an earlier PREPARE FROM a literal
            if ex.group(1).upper() not in self.prepared:
                raise Unsupported(f"EXEC SQL EXECUTE {ex.group(1)}: no earlier PREPARE FROM a string literal")
            prepared = self.prepared[ex.group(1).upper()]
            marks = len(re.findall(r"\?", re.sub(r"'(?:[^']|'')*'", "''", prepared)))
            using = ex.group(2) or ""
            # (the host variables bind in order, the stub's parameter markers: IBM binds them as Db2 does)
            if re.sub(r"[\s,]", "", re.sub(r":\s*[A-Z0-9][A-Z0-9-]*(?:\s*(?:INDICATOR\s*)?:\s*[A-Z0-9][A-Z0-9-]*)?", "",
                                           using, flags=re.I)):  # fmt: skip
                raise Unsupported(f"EXEC SQL EXECUTE {ex.group(1)} USING {using[:30]}: only host variables")
            _, refs = self._bind(using, args)
            n_host = sum(len(elems) for elems, _ in refs)
            if n_host != marks:
                raise Unsupported(f"EXEC SQL EXECUTE {ex.group(1)}: {marks} parameter markers, {n_host} host "
                                  "variables")  # fmt: skip
            st = Statement(sid, "EXEC", _norm(prepared), "-", self._vars(refs, args))
            self.statements.append(st)
            return st, args
        if verb in ("PREPARE", "EXECUTE", "DESCRIBE", "CONNECT", "SET", "CALL", "ALLOCATE", "ASSOCIATE"):
            raise Unsupported(f"EXEC SQL {verb}")
        pos = re.search(r"\bWHERE\s+CURRENT\s+OF\s+([A-Z0-9_-]+)", u)
        if pos and (verb not in ("UPDATE", "DELETE") or pos.group(1) not in self.cursors):
            raise Unsupported(f"EXEC SQL {verb} ... WHERE CURRENT OF {pos.group(1)}: not a declared cursor")
        # a positioned UPDATE / DELETE runs as written: ggsql.c names each cursor (SQLSetCursorName) at its OPEN
        if re.fullmatch(r"SAVEPOINT\s.*|ROLLBACK(?:\s+WORK)?\s+TO\s+SAVEPOINT(?:\s+[A-Z0-9_]+)?|"
                        r"RELEASE(?:\s+TO)?\s+SAVEPOINT\s+[A-Z0-9_]+", u, re.S):  # fmt: skip
            # #4269: a savepoint statement runs as written, Db2 answering it (the det port's DetSql.savepoint)
            if ":" in text:
                raise Unsupported(f"EXEC SQL {u[:60]}: a host variable in a savepoint statement")
            # IBM's CLI takes `ROLLBACK WORK ...` for a ROLLBACK of the whole unit of work (measured: it backed out
            # past the savepoint and answered 0 where Db2 answers -880); WORK is a noise word (SQL Reference)
            st = Statement(sid, "EXEC", re.sub(r"^ROLLBACK\s+WORK\s+", "ROLLBACK ", _norm(text), flags=re.I))
        elif verb in ("COMMIT", "ROLLBACK"):
            if not re.fullmatch(r"(COMMIT|ROLLBACK)(\s+WORK)?", u):
                raise Unsupported(f"EXEC SQL {u}")
            st = Statement(sid, verb)
        elif verb == "OPEN":
            name = u.split()[1]
            if name not in self.cursors or len(u.split()) > 2:
                raise Unsupported(f"EXEC SQL {u}: an undeclared cursor, or OPEN ... USING")
            sql, refs = self._bind(self.cursors[name], args)
            st = Statement(sid, "OPEN", _norm(sql), name, self._vars(refs, args), hold=name in self.hold,
                           scroll=name in self.scroll)  # fmt: skip
        elif verb == "FETCH" and re.search(r"\bROWSET\b", u):
            st = self._rowset_fetch(sid, text, args)
        elif verb == "FETCH":
            m = re.fullmatch(r"FETCH\s+(?:INSENSITIVE\s+)?(?:(NEXT|PRIOR|FIRST|LAST|CURRENT|(?:ABSOLUTE|RELATIVE)\s+\S+)\s+)?"
                             r"(?:FROM\s+)?([A-Z0-9_-]+)\s+INTO\s+(.*)", text, re.I | re.S)  # fmt: skip
            if not m:
                raise Unsupported(f"EXEC SQL {u[:60]}")
            _, refs = self._bind(m.group(3), args)
            st = Statement(sid, "FETCH", "", m.group(2).upper(), [], self._vars(refs, args))
            words = (m.group(1) or "NEXT").upper().split()
            if words[0] != "NEXT":
                if st.cursor not in self.scroll:
                    raise Unsupported(f"EXEC SQL FETCH {words[0]}: the cursor is not declared SCROLL")
                st.scroll, st.orient = True, words[0]
                if len(words) > 1:
                    if words[1].startswith(":"):
                        _, nrefs = self._bind(words[1], args)
                        st.inputs = self._vars(nrefs, args)
                    else:
                        st.orient_n = int(words[1])
            elif st.cursor in self.scroll:
                st.scroll, st.orient = True, "NEXT"
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

    @staticmethod
    def _dynamic_insert(inner: str, what: str) -> None:
        marker = re.search(r"\?", re.sub(r"'(?:[^']|'')*'", "''", inner))
        if (not re.fullmatch(r"INSERT\s+INTO\s.*\bVALUES\b.*", inner, re.I | re.S)
                or re.search(r"\bSELECT\b", inner, re.I) or (marker and what == "EXECUTE IMMEDIATE")):  # fmt: skip
            raise Unsupported(f"EXEC SQL {what} '{inner[:40]}': only INSERT ... VALUES is modelled")

    def whenever_tests(self, period: str) -> list[str]:
        """#4269: the SQLCA tests of the WHENEVER actions in force, IBM's order (SQLERROR, NOT FOUND, SQLWARNING)."""
        tests = [("SQLERROR", "SQLCODE < 0"), ("NOT FOUND", "SQLCODE = 100"),
                 ("SQLWARNING", "SQLWARN0 = 'W' OR\n               (SQLCODE > 0 AND SQLCODE NOT = 100)")]  # fmt: skip
        live = [(c, t) for c, t in tests if c in self.whenever]
        out: list[str] = []
        for n, (cond, test) in enumerate(live):
            # (one clause per line: the fixed-format source ends at column 72)
            out.append(f"           {'ELSE ' if n else ''}IF {test}")
            out.append(f"               GO TO {self.whenever[cond]}")
        if live:
            out += ["           END-IF"] * len(live)
            out[-1] += period
        return out

    def table(self) -> str:
        """The statement table ggsql.c reads ($GGSQL_STMTS)."""
        out = []
        for s in self.statements:
            # #4173: then the statement's program and source line, the key a SQL fault names
            # #4269: an OPEN of a cursor declared WITH HOLD ends `H` (ggsql.c keeps it open at a COMMIT)
            # #4269: a scroll OPEN / FETCH then ends `K`, the FETCH's orientation and constant as `K:ORIENT[:n]`
            tail = (" H" if s.hold else "") + (
                (" K" + (f":{s.orient}" if s.orient else "") + (f":{s.orient_n}" if s.orient_n is not None else ""))
                if s.scroll else "")  # fmt: skip
            if s.rowset:  # #4269: a FETCH ROWSET ends `R`, or `R:n` for a constant FOR n ROWS
                tail = " R" + (f":{s.orient_n}" if s.orient_n is not None else "")
            out.append(f"S {s.sid} {s.kind} {len(s.inputs)} {len(s.outputs)} {s.cursor} {s.program} {s.line}" + tail)
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


def precompile(source: str, dirs: list[Path], path: Path, first_id: int = 1, program: str = "-") -> tuple[str, str]:
    """(the program with its EXEC SQL replaced, the statement table); its statements numbered from `first_id`, each
    keyed by `program` and the line of its EXEC SQL in `source` (#4173: what a SQL fault names)."""
    traced = expand_includes_traced(source.split("\n"), dirs)
    lines = [ln for ln, _ in traced]
    # the reader takes code areas (columns 8-72): a sequence number in columns 1-6 (COTRTLIC's) is no level number
    pre = Precompiler(Program(_items([_area(ln).upper() for ln in lines if not re.search(r"\bEXEC\s+SQL\b", _area(ln), re.I)],
                                     path)), first_id)  # fmt: skip
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
        if done is not None:  # #4173: the key a SQL fault names -- the program and the EXEC SQL's own line
            done[0].program, done[0].line = program.upper(), traced[i][1]
            done[0].verb = (_norm(m.group(1)).upper().split() or [""])[0]
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
            tests = pre.whenever_tests(period)
            out.append("           MOVE GG-SQL-RC TO RETURN-CODE" + ("" if tests else period))
            out += tests
        after = text[m.end() :].strip()
        if after:
            out.append("           " + after)
        i = j + 1
    return "\n".join(out), pre.table()
