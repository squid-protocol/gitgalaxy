#!/usr/bin/env python3
"""#4175: can any input tell a det-port Field-declaration mutant from the port?

A det port declares each COBOL item as a Field over its record's storage (`f12_X = Field.kind(s_REC, offset, length,
...)`). A mutant of that line moves or resizes the window the accessor reads and writes. This module settles such a
mutant when one of three facts holds; anything else is left to an attack (`survivor_attack.py try`).

  dead window   no reachable statement reads X, and nothing -- no reachable statement, no runtime reader (the
                harness's DTO records, LINKAGE, FILE, the SQLCA, a sent map, the EIB fields the generated code reads
                unnamed: EIBCALEN, EIBAID under HANDLE AID, all of it after ADDRESS EIB) -- reads a byte of X's window
                or of the mutant's: its writes land where nobody looks.
  map subfield  X is a BMS symbolic-map attribute (<f>A / F / C / H) or length (<f>L) no statement names. SEND MAP
                reads an attribute's first byte only, as "not set" when it is X'00' or a space, and a length only
                for -1 (the cursor) (DetCics.subfields). When every byte the original and the mutant read is written
                by nothing but whole-item figurative moves and can only hold X'00' or a space, both read "not set".
  DFHAID        X is an attention-key constant. The runtime moves the pressed key's constant into the one-byte
                EIBAID (runTask's AID switch), and the program only compares EIBAID for (in)equality with DFHAID
                constants or literals. For every key, the set of comparisons it satisfies is the same with the
                mutant as without, so no key press can tell them apart.

    python tests/tools/field_observability.py CASE   # each Field-declaration survivor of the case: settled or not

Every doubt is "observable": a statement the reading does not split into reads and writes reads everything it names,
any use of EIBAID other than a comparison leaves DFHAID mutants open, and an incomplete walk settles nothing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
import branch_solver as bs  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import layout as L  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402

_DECL = re.compile(r"\bf\d+_(\w+)\s*=\s*Field\.(\w+)\(\s*s_(\w+)\s*,\s*(\d+)\s*,\s*(\d+)")
BLANK = {0x00, 0x20}
FIG_BYTE = {"SPACES": 0x20, "LOW": 0x00, "HIGH": 0xFF, "ZEROS": 0x30, "QUOTES": 0x22}
ATTR_ROLES, LEN_ROLE = set("AFCH"), "L"


def decl(line: str) -> tuple[str, str, int, int] | None:
    """(item, record storage, offset, length) of a det-port Field declaration line, COBOL names restored."""
    m = _DECL.search(line)
    if not m:
        return None
    return m.group(1).replace("_", "-"), m.group(3).replace("_", "-"), int(m.group(4)), int(m.group(5))


def span(it: L.Item) -> range:
    """The bytes an item can occupy in its storage: under OCCURS, the whole outermost table."""
    outer: L.Item | None = None
    p: L.Item | None = it
    while p is not None:
        if p.occurs != 1:
            outer = p
        p = p.parent
    if outer is None:
        return range(it.offset, it.offset + it.size)
    return range(outer.offset, outer.offset + outer.size * outer.occurs)


def storage(it: L.Item) -> str:
    return bs._root(it).name.upper()


class Observability:
    def __init__(self, prog: bs.Program, spec: dict[str, Any], corpus: Path | None = None):
        self.prog = prog
        self.corpus = corpus
        self.longest: dict[str, int] = {}  # map -> the longest field a terminal transmits
        self.stmts = [x for p in prog.proc.paragraphs for x in S.walk(p.body)]
        self.roots = {bs._root(r).name.upper(): bs._root(r) for r in prog.records}
        self.maps = {m.upper() for x in self.stmts if x.kind == "EXEC"
                     for m in re.findall(r"\bMAP\s*\(\s*'([^']+)'", x.text, re.I)}  # fmt: skip
        self.map_of = {storage(r): r.name.upper()[:-1] for r in prog.records
                       if r.name.upper()[:-1] in self.maps and r.name.upper()[-1:] in "IO"}  # fmt: skip
        self.map_storages = set(self.map_of)
        # per map storage: is it "dirty" (RECEIVE MAP since the last whole-storage figurative MOVE) at a SEND MAP?
        items0 = bs.Items(prog.records)
        flags = {st: (self._receives(m), self._clears(st, items0), self._sends(m)) for st, m in self.map_of.items()}
        self.w = bs.Walk(prog, bs.evaluate_arms(prog.source), flags)
        self.w.explore()
        self.items = self.w.items
        reached = [x for x in self.stmts if id(x) in self.w.at]
        self.complete = not self.w.why
        self.clean = {st: self.complete and self.w.ask(self.w.flag_at[st])[0] == "confirmed" for st in self.map_of}
        # what is read: by reachable statements (their read positions) and by the runtime
        self.read_ids: set[int] = set()
        self.read_bytes: dict[str, set[int]] = {}
        for x in reached:
            for it in self.reads(x):
                self._read(it)
            if x.kind == "EXEC" and re.search(r"\bSEND\s+MAP\b", x.text, re.I):
                for st in self.map_storages:  # SEND MAP reads its map's storage, subfield by subfield
                    self.read_bytes.setdefault(st, set()).update(range(self.roots[st].size * self.roots[st].occurs))
        dto = {str(seg.get("record", "")).upper() for seg in (spec.get("commarea") or {}).get("segments", [])}
        for ds in (spec.get("datasets") or {}).values():
            dto |= {str(ds.get(k, "")).upper() for k in ("record", "into") if isinstance(ds, dict) and ds.get(k)}
        self._raw: set[int] = set()  # items whose bytes the runtime copies raw (DTOs, LINKAGE, FILE, SQLCA)
        for r in prog.records:
            if r.name.upper() in dto or r.section in ("LINKAGE", "FILE") or r.name.upper() in ("SQLCA", "DFHAID"):
                self._raw |= {id(x) for x in r.walk()}
                if r.name.upper() != "DFHEIBLK":
                    for it in r.walk():
                        self._read(it)
        # the EIB fields the generated code reads with no statement naming them: EIBCALEN (COMMAREA addressing and
        # write-back), EIBAID under HANDLE AID (the label the key picks), the whole block once its ADDRESS is taken
        texts = " ".join(x.text.upper() for x in self.stmts if x.kind == "EXEC")
        implicit = {"EIBCALEN"} | ({"EIBAID"} if re.search(r"\bHANDLE\s+AID\b", texts) else set())
        whole = bool(re.search(r"\bADDRESS\s+EIB\b", texts))
        for r in prog.records:
            if r.name.upper() == "DFHEIBLK":
                for it in r.walk():
                    if whole or it.name.upper() in implicit:
                        self._read(it)
        self._map_bytes()
        self._aid = self._aid_uses()

    @staticmethod
    def _receives(m: str) -> Any:
        return lambda x: x.kind == "EXEC" and bool(re.search(rf"\bRECEIVE\s+MAP\s*\(\s*'{re.escape(m)}'", x.text, re.I))

    @staticmethod
    def _sends(m: str) -> Any:
        return lambda x: x.kind == "EXEC" and bool(re.search(rf"\bSEND\s+MAP\s*\(\s*'{re.escape(m)}'", x.text, re.I))

    def _clears(self, st: str, items: bs.Items) -> Any:
        size = self.roots[st].size

        def clears(x: S.Stmt) -> bool:
            src = x.data.get("from") if x.kind == "MOVE" else None
            if not (isinstance(src, E.Fig) and src.kind in ("LOW", "SPACES") and not src.all_literal):
                return False
            hit = [it for r in x.data.get("to") or [] for it in items.resolve(r)]
            return any(storage(it) == st and span(it) == range(0, size) for it in hit)

        return clears

    # -- reads and writes --
    def _read(self, it: L.Item) -> None:
        self.read_ids.add(id(it))
        self.read_bytes.setdefault(storage(it), set()).update(span(it))

    def reads(self, s: S.Stmt) -> list[L.Item]:
        """The items a statement reads: a MOVE / COMPUTE / ARITH GIVING its sources (and every subscript), an
        INITIALIZE / SET TRUE only subscripts, anything else every item it names."""
        t, k = s.text, s.kind
        m = self.items.mentioned

        def subs(text: str) -> list[L.Item]:
            return m(" ".join(re.findall(r"\(([^()]*)\)", text)))

        if k == "MOVE":
            parts = re.split(r"(?i)\bTO\b", t, maxsplit=1)
            return m(parts[0]) + subs(parts[1] if len(parts) > 1 else "")
        if k == "COMPUTE" and "=" in t:
            lhs, rhs = t.split("=", 1)
            return m(rhs) + subs(lhs)
        if k == "ARITH" and re.search(r"(?i)\bGIVING\b", t):
            head, tail = re.split(r"(?i)\bGIVING\b", t, maxsplit=1)
            return m(head) + subs(tail)
        if k in ("INITIALIZE", "SET-TRUE"):
            return subs(t)
        return m(t)

    def _map_bytes(self) -> None:
        """Per map storage: the bytes some statement writes (other than a whole-item figurative MOVE), and the values
        each byte can hold otherwise (its image byte, every figurative fill, X'00' from RECEIVE MAP's clear)."""
        self.written: dict[str, set[int]] = {st: set() for st in self.map_storages}
        # bytes RECEIVE MAP writes only as a typed length (binary, at most the longest keyable field: never X'FF')
        self.len_written: dict[str, set[int]] = {st: set() for st in self.map_storages}
        self.fills: dict[str, dict[int, set[int]]] = {st: {} for st in self.map_storages}
        for x in self.stmts:
            if x.kind == "EXEC" and re.search(r"\bRECEIVE\s+MAP\b", x.text, re.I):
                continue  # below: what RECEIVE MAP writes, unless every SEND MAP follows a clear
            src = x.data.get("from") if x.kind == "MOVE" else None
            fig = FIG_BYTE.get(src.kind) if isinstance(src, E.Fig) and not src.all_literal else None
            for it in self.w.writes.targets(x):
                st = storage(it)
                if st not in self.map_storages:
                    continue
                if fig is not None:
                    for b in span(it):
                        self.fills[st].setdefault(b, set()).add(fig)
                else:
                    self.written[st].update(span(it))
        for st, m in self.map_of.items():
            received = any(self._receives(m)(x) for x in self.stmts)
            if received:  # RECEIVE MAP clears the area and types each input field and its length
                for b in range(self.roots[st].size):
                    self.fills[st].setdefault(b, set()).add(0x00)
                if not self.clean[st]:  # a SEND MAP may show what RECEIVE MAP typed: its fields are written
                    keyed = self.receivable(m)
                    short = keyed is not None and self.longest.get(m, 255) < 255
                    for r in self.prog.records:
                        if storage(r) == st:
                            for it in r.walk():
                                name = it.name.upper()
                                if (
                                    it.children
                                    or name[-1:] not in "IL"
                                    or (keyed is not None and name[:-1] not in keyed)
                                ):
                                    continue
                                (self.len_written if name[-1:] == "L" and short else self.written)[st].update(span(it))

    def receivable(self, m: str) -> set[str] | None:
        """The fields of map `m` a terminal transmits on RECEIVE MAP: the unprotected ones (an operator can key them)
        and any with FSET (sent back with its modified-data tag on), from the map's BMS source -- IBM 3270 terminal
        behaviour: a protected field without FSET is never in the inbound data. None (every field) when the source
        is not read."""
        if self.corpus is None:
            return None
        try:
            from gitgalaxy.core.bms_screen_fields import bms_screen_fields  # noqa: PLC0415
            from gitgalaxy.core.source_text import read_source  # noqa: PLC0415
            from gitgalaxy.tools.cobol_to_java.cobol_to_java_screen_forge import _attrs  # noqa: PLC0415
        except ImportError:
            return None
        out: set[str] = set()
        found = False
        longest = 0
        for p in sorted(self.corpus.rglob("*.bms")):
            if ".git" in p.parts:
                continue
            rows = bms_screen_fields(read_source(p).text)
            maps = {r["ordinal"] for r in rows if r["kind"] == "map" and (r["name"] or "").upper() == m}
            found = found or bool(maps)
            for r in rows:
                if r["kind"] == "field" and r["parent_ordinal"] in maps and r["name"]:
                    attrs = _attrs(r)
                    if not attrs & {"ASKIP", "PROT"} or "FSET" in attrs:
                        out.add(r["name"].upper())
                        longest = max(longest, int(r.get("length") or 0))
        self.longest[m] = longest
        return out if found else None

    def length_only(self, st: str, b: int) -> bool:
        """Byte b is written only as part of a typed length (and otherwise holds X'00' or a space): never X'FF'."""
        img = L.image(self.roots[st])
        if b < 0 or b >= len(img) or b not in self.len_written[st] or b in self.written[st]:
            return False
        return ({img[b]} | self.fills[st].get(b, set())) <= BLANK

    def blank_only(self, st: str, b: int) -> bool:
        """Byte b of a map storage can hold only X'00' or a space whenever SEND MAP reads it."""
        root = self.roots[st]
        img = L.image(root)
        if b < 0 or b >= len(img) or b in self.written[st]:
            return False
        return ({img[b]} | self.fills[st].get(b, set())) <= BLANK

    # -- DFHAID --
    def _aid_uses(self) -> dict[str, Any] | None:
        """The DFHAID constants and literals EIBAID is compared with, and the constants read anywhere else; None when
        EIBAID is used otherwise (or HANDLE AID is), which leaves every DFHAID mutant open."""
        comps: set[str] = set()
        lits: set[bytes] = set()
        other_reads: set[str] = set()
        aid = {c.name.upper() for r in self.prog.records if r.name.upper() == "DFHAID" for c in r.children}
        for x in self.stmts:
            up = x.text.upper()
            if x.kind == "EXEC" and re.search(r"\bHANDLE\s+AID\b", up):
                return None
            words = set(re.findall(r"[A-Z0-9][A-Z0-9-]*", up))
            if "EIBAID" not in words:
                other_reads |= words & aid
                continue
            if x.kind == "IF" and self._aid_cond(x.data.get("cond"), comps, lits):
                continue
            if x.kind == "EVALUATE" and self._aid_eval(x, comps, lits):
                continue
            return None
        return {"comps": comps, "lits": lits, "other": other_reads}

    def _aid_side(self, v: Any, comps: set[str], lits: set[bytes]) -> bool:
        if isinstance(v, E.Ref) and not v.subscripts and not v.refmod and v.name.upper().startswith("DFH"):
            comps.add(v.name.upper())
            return True
        if isinstance(v, E.Lit) and isinstance(v.value, str):
            lits.add(bytes(ord(c) if ord(c) < 256 else 0xFF for c in v.value))
            return True
        return False

    def _aid_cond(self, c: Any, comps: set[str], lits: set[bytes]) -> bool:
        """A condition whose every use of EIBAID is `EIBAID = / <> constant` (any AND / OR / NOT around it)."""
        if isinstance(c, (E.And, E.Or)):
            return self._aid_cond(c.left, comps, lits) and self._aid_cond(c.right, comps, lits)
        if isinstance(c, E.Not):
            return self._aid_cond(c.cond, comps, lits)
        if isinstance(c, E.Rel) and c.op in ("=", "<>"):
            sides = [c.left, c.right]
            eib = [s for s in sides if isinstance(s, E.Ref) and s.name.upper() == "EIBAID"]
            if not eib:
                return True
            other = sides[1] if sides[0] is eib[0] else sides[0]
            return len(eib) == 1 and self._aid_side(other, comps, lits)
        if isinstance(c, E.CondName) and c.abbrev is not None:
            op, subject, _neg = c.abbrev
            if isinstance(subject, E.Ref) and subject.name.upper() == "EIBAID":
                return op in ("=", "<>") and self._aid_side(c.ref, comps, lits)
        return "EIBAID" not in repr(c).upper()

    def _aid_eval(self, x: S.Stmt, comps: set[str], lits: set[bytes]) -> bool:
        subj = x.data.get("subjects") or []
        if len(subj) != 1 or not (isinstance(subj[0], E.Ref) and subj[0].name.upper() == "EIBAID"):
            return False
        for conds, _ in x.whens:
            for alt in conds or []:
                for kind, a, _b, _neg in alt:
                    if kind == "ANY":
                        continue
                    if kind != "VALUE" or not self._aid_side(a, comps, lits):
                        return False
        return True

    def aid_fact(self, item: str, off: int, length: int) -> str | None:
        uses = self._aid
        aid = next((r for r in self.prog.records if r.name.upper() == "DFHAID"), None)
        if uses is None or aid is None or item in uses["other"]:
            return None
        img = L.image(aid)
        consts = {
            c.name.upper(): img[c.offset : c.offset + c.size] for c in aid.children if c.name.upper().startswith("DFH")
        }
        if item not in consts or off + length > len(img):
            return None
        mutated = dict(consts)
        mutated[item] = img[off : off + length]

        def eq(a: bytes, b: bytes) -> bool:
            n = max(len(a), len(b))
            return a.ljust(n, b" ") == b.ljust(n, b" ")

        def classes(table: dict[str, bytes]) -> dict[str, frozenset]:
            out = {}
            for key, val in table.items():
                eib = val[:1] or b" "  # the AID switch: MOVE DFH<key> TO EIBAID, a one-byte alphanumeric
                hits = {c for c in uses["comps"] if c in table and eq(eib, table[c])}
                hits |= {f"'{lit!r}'" for lit in uses["lits"] if eq(eib, lit)}
                out[key] = frozenset(hits)
            return out

        if classes(consts) == classes(mutated):
            return (f"DFHAID: every key press matches the same EIBAID comparisons with {item} at ({off}, {length}) as "
                    f"without (EIBAID is compared only with {', '.join(sorted(uses['comps'])) or 'nothing'})")  # fmt: skip
        return None

    # -- the verdict --
    def judge(self, before: str, after: str) -> str | None:
        """Why the mutant from `before` to `after` (two Field-declaration lines) is unobservable, or None."""
        a, b = decl(before), decl(after)
        if a is None or b is None or (a[0], a[1]) != (b[0], b[1]) or not self.complete:
            return None
        name, st, off, ln = a
        _, _, off2, ln2 = b
        cands = [c for c in self.items.by_name.get(name, []) if storage(c) == st and c.level not in (66, 88)]
        if st == "DFHAID":
            return self.aid_fact(name, off2, ln2)
        if len(cands) != 1 or st not in self.roots:
            return None
        it = cands[0]
        size = self.roots[st].size * self.roots[st].occurs
        if off2 + ln2 > size:
            return None  # the mutant's window leaves the storage: an exception, not silence
        if st in self.map_storages:
            return self._map_fact(it, st, off, ln, off2, ln2)
        window = set(range(off, off + ln)) | set(range(off2, off2 + ln2))
        if id(it) in self.read_ids or window & self.read_bytes.get(st, set()):
            return self._relocated(it, st, off, ln, off2, ln2) or self._truncated(it, st, before, off, ln, off2, ln2)
        return f"dead window: no reachable statement or runtime reader reads {name} or bytes {min(window)}-{max(window)} of {st}"

    def _relocated(self, it: L.Item, st: str, off: int, ln: int, off2: int, ln2: int) -> str | None:
        """An offset-only mutant of an item every access reaches through its own Field: the item lives at a new
        address. Unobservable when no other item touching either window is read or written anywhere (so nothing sees
        the old bytes go stale or the new ones taken), the runtime copies none of the record's raw bytes, and the
        record's initial image holds the same bytes in both windows."""
        if ln2 != ln or st in ("DFHEIBLK", "DFHAID") or st in self.map_storages:
            return None
        root = self.roots[st]
        if root.section != "WORKING-STORAGE" or any(id(x) in self._raw for x in root.walk()):
            return None
        img = L.image(root)
        if img[off : off + ln] != img[off2 : off2 + ln2]:
            return None
        window = set(range(off, off + ln)) | set(range(off2, off2 + ln2))
        mine = {id(x) for x in it.walk()}
        for x in self.stmts:
            for other in [*self.reads(x), *self.w.writes.targets(x)]:
                if id(other) not in mine and storage(other) == st and window & set(span(other)):
                    return None
        return (
            f"relocated: every access to {it.name} goes through its own Field, nothing else touches bytes "
            f"{min(window)}-{max(window)} of {st}, and the initial image holds the same bytes at both addresses"
        )

    def _truncated(self, it: L.Item, st: str, before: str, off: int, ln: int, off2: int, ln2: int) -> str | None:
        """A length-only mutant of an alphanumeric item or group the program only ever reads by MOVE X TO Y, every Y
        alphanumeric and no longer than the shorter window: each MOVE takes the same leading bytes either way."""
        if off2 != off or ln2 == ln or not re.search(r"Field\.(alphanumeric|group)\(", before):
            return None
        if st in ("DFHEIBLK", "DFHAID") or st in self.map_storages or id(it) in self._raw:
            return None
        names = {it.name.upper()} | {c.name.upper() for c in it.conditions}
        word = re.compile(r"(?<![A-Z0-9-])(" + "|".join(re.escape(n) for n in sorted(names)) + r")(?![A-Z0-9-])")
        short = min(ln, ln2)
        for x in self.stmts:
            if not word.search(x.text.upper()):
                continue
            src = x.data.get("from") if x.kind == "MOVE" else None
            if not (
                isinstance(src, E.Ref) and self.items.resolve(src) == [it] and not src.subscripts and not src.refmod
            ):
                return None
            for r in x.data.get("to") or []:
                hit = self.items.resolve(r)
                if r.name.upper() in names or len(hit) != 1 or r.refmod:
                    return None
                tgt = hit[0]
                if tgt.category in ("NUMERIC", "NUMERIC-EDITED", "FLOAT") or tgt.size > short or tgt.justified:
                    return None
        return (
            f"truncated: {it.name} is only ever moved whole into alphanumeric items of at most {short} bytes, "
            f"so its {ln} or {ln2} bytes give them the same leading bytes"
        )

    def _keyed_note(self, st: str) -> str:
        if self.clean.get(st):
            return ""
        return " (assumed: a protected BMS field without FSET is never keyed, IBM 3270 inbound data)"

    def _map_fact(self, it: L.Item, st: str, off: int, ln: int, off2: int, ln2: int) -> str | None:
        role = it.name.upper()[-1:]
        base = it.name.upper()[:-1]
        siblings = {c.name.upper() for c in self.items.all if storage(c) == st}
        if role not in ATTR_ROLES | {LEN_ROLE} or not ({base + "O", base + "I"} & siblings):
            return None
        word = re.compile(rf"(?<![A-Z0-9-]){re.escape(it.name.upper())}(?![A-Z0-9-])")
        if any(word.search(x.text.upper()) for x in self.stmts):
            return None  # the program names it: it reads or writes it itself
        if role in ATTR_ROLES:
            if off2 == off:
                return f"map attribute {it.name}: SEND MAP reads its first byte only, and the mutant keeps it"
            if self.blank_only(st, off) and self.blank_only(st, off2):
                return (f"map attribute {it.name}: bytes {off} and {off2} only ever hold X'00' or a space, which SEND "
                        f"MAP reads as not set either way{self._keyed_note(st)}")  # fmt: skip
            return None
        window = [*range(off, off + ln), *range(off2, off2 + ln2)]
        if all(self.blank_only(st, b) or self.length_only(st, b) for b in window):
            return (
                f"map length {it.name}: its bytes and the mutant's hold only X'00', spaces or a typed length "
                f"(under 255: no X'FF' byte), never the cursor's -1{self._keyed_note(st)}"
            )
        return None


def judge_case(case: str, work: Path) -> dict[str, Any]:
    """Each Field-declaration survivor of a case, with the fact that settles it or none."""
    import det_mutation as dm  # noqa: PLC0415

    prog = bs.case_program(case, work)
    spec = json.loads((bs.REPO / "tests" / "equivalence" / case / "case.json").read_text(encoding="utf-8"))
    obs = Observability(prog, spec, bs.corpus_root(spec["corpus"]))
    rows = []
    for mid, e in sorted(dm.stated(case).items()):
        if decl(e.get("before") or ""):
            rows.append({"id": mid, "verdict": e.get("verdict"), "fact": obs.judge(e["before"], e["after"])})
    return {"case": case, "complete": obs.complete, "survivors": rows}


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case")
    ap.add_argument("--work", type=Path, default=Path("/tmp/gitgalaxy-scratch/branch-solver"))
    args = ap.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    print(json.dumps(judge_case(args.case, args.work), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
