"""#4736: CALL identifier -- the program names the identifier can hold when the CALL runs, from the source alone.

IBM Enterprise COBOL, CALL statement: with a data item as the program, "the program-name is the content of
identifier-1" and the program is found when the CALL runs (a dynamic call); a name that finds no program is the
CALL's exception condition (ON EXCEPTION, else the run unit ends). The port dispatches over the names the item can
hold and refuses by name when it cannot know them:

  1. A MOVE of a literal (or of an item whose content is known) earlier in the same paragraph, on the CALL's own path,
     with nothing between it and the CALL that can change the item -- the one value that reaches the CALL; else
  2. an item with a VALUE clause whose every other write in the program is such a MOVE: the VALUE and each MOVEd
     value (the VALUE table of DBB epscsmrt: `MOVE CALLED-PROGRAM-NAME(1) TO WS-CALLED-PROGRAM`).

A "known" source is a literal, or an alphanumeric item that nothing in the program writes (or overlaps through a
REDEFINES or a group) whose VALUE clauses (through a REDEFINES table too) fix the bytes, subscripted by literals only.
Anything else -- a READ INTO, a STRING, a group MOVE, the item passed to a CALL, a MOVE from COMMAREA data, a
computed subscript, an item with no VALUE, a CALL inside a loop that rewrites the item -- is named in the refusal."""

from __future__ import annotations

import re
from decimal import Decimal

import gitgalaxy.tools.cobol_to_java.det.expr as E
import gitgalaxy.tools.cobol_to_java.det.layout as L
import gitgalaxy.tools.cobol_to_java.det.stmt as S

_WORD = re.compile(r"[A-Z0-9][A-Z0-9-]*")
# a program name the port matches: IBM's PGMNAME(COMPAT) names are at most 8 characters, uppercase (PGMNAME(MIXED) /
# LONGUPPER names are not modelled)
_NAME = re.compile(r"[A-Z0-9@#$]{1,8}")
# statements that write no data item of their own (their nested statements are walked on their own)
_READ_ONLY = {"DISPLAY", "GOTO", "CONTINUE", "EXIT", "GOBACK", "STOP", "NEXT-SENTENCE", "IF", "EVALUATE"}
# IBM's Db2 message formatter and the SQLCA formatter: the text is Db2's message catalogue (oracle_assumptions.md Q5)
REFUSED_BY_NAME = {
    "DSNTIAC": "DSNTIAC: Db2's message text is not modelled (oracle_assumptions.md Q5)",
    "DSNTIAR": "DSNTIAR: Db2's message text is not modelled (oracle_assumptions.md Q5)",
}


class Unknown(Exception):
    """The value cannot be known statically (the reason names where)."""


def _name_of(ref: E.Ref) -> str:
    return ref.name + ("".join(f" OF {q}" for q in ref.qualifiers) if ref.qualifiers else "")


def _flow(gen) -> dict:
    """id(statement) -> (its statement list, its index, the statement holding the list or None)."""
    if getattr(gen, "_dyn_flow", None) is None:
        out: dict = {}

        def lists(st):
            yield st.body
            yield st.orelse
            for _, b in st.whens:
                yield b
            yield from st.phrases.values()

        def visit(stmts, parent):
            for i, st in enumerate(stmts):
                out[id(st)] = (stmts, i, parent)
                for sub in lists(st):
                    visit(sub, st)

        for para in gen.p.proc.paragraphs:
            visit(para.body, None)
        gen._dyn_flow = out
    return gen._dyn_flow


def _overlap_names(gen, it: L.Item) -> set[str]:
    """The names of every item sharing a byte with `it` (a group over it, a REDEFINES, a table holding it), the 88s
    on them (SET cond TO TRUE writes the item), in any record laid over the same storage."""
    root = gen.root_of.get(id(it.record))
    _, full, _ = _extents(it)
    near: list[L.Item] = []
    for lst in gen.items.values():
        for o in lst:
            if gen.root_of.get(id(o.record)) != root:
                continue
            _, f2, _ = _extents(o)
            if f2[0] < full[1] and full[0] < f2[1]:
                near.append(o)
    names = {o.name for o in near}
    ids = {id(o) for o in near}
    for lst in gen.conds.values():
        names |= {c.name for c in lst if c.parent is not None and id(c.parent) in ids}
    names.discard("FILLER")
    return names


def _extents(it: L.Item):
    from gitgalaxy.tools.cobol_to_java.det.gen import _extents as ext

    return ext(it)


def _may_write(st: S.Stmt, names: set[str]) -> bool:
    k = st.kind
    if k in _READ_ONLY:
        return False
    if k == "PERFORM":
        v = st.data.get("varying")
        return v is not None and v[0].name in names
    if k == "MOVE":
        return any(t.name in names for t in st.data["to"])
    if k == "CALL":  # the program-name is read; every USING / RETURNING item may be changed by the callee
        tail = re.split(r"\bUSING\b|\bRETURNING\b", st.text.upper(), maxsplit=1)
        return len(tail) > 1 and bool(set(_WORD.findall(tail[1])) & names)
    return bool(set(_WORD.findall(st.text.upper())) & names)


def _closure(gen, stmts, seen: set[int]):
    """Every statement under `stmts`, and under each paragraph a PERFORM among them runs."""
    paras = gen.p.proc.paragraphs
    for st in S.walk(stmts):
        yield st
        d = st.data
        if st.kind == "PERFORM" and d.get("target") in gen.para_index:
            t = d["target"]
            i = gen.para_index[t]
            if paras[i].section == t and d["thru"] is None:
                rng = [j for j, p in enumerate(paras) if p.section == t]
            else:
                rng = range(i, gen.para_index.get(d["thru"] or t, i) + 1)
            for j in rng:
                if j not in seen:
                    seen.add(j)
                    yield from _closure(gen, paras[j].body, seen)


def _valued(rec: L.Item) -> bytearray:
    """The bytes of a record a VALUE clause fixes (layout._fill, which bytes it takes from a VALUE, not a default)."""
    if rec.level == 1 and rec.redefines and rec.record is not None and rec.record is not rec:
        return _valued(rec.record)
    mask = bytearray(rec.size * rec.occurs)

    def fill(it: L.Item, shift: int, under: bool) -> None:
        for k in range(it.occurs):
            base = it.offset + shift + k * it.size
            here = under or bool(it.redefines)
            if it.children and it.pic is None:
                if it.values and not here:
                    mask[base : base + it.size] = b"\x01" * it.size
                    continue
                for c in it.children:
                    fill(c, shift + k * it.size, here)
                continue
            if here and it is not it.record:
                continue
            if it.values:
                mask[base : base + it.size] = b"\x01" * it.size

    fill(rec, 0, False)
    return mask


def _const_int(e) -> int | None:
    v = e.value if isinstance(e, E.Lit) else None
    return int(v) if isinstance(v, Decimal) and v == v.to_integral_value() else None


def _plain_text_item(gen, ref: E.Ref, role: str) -> L.Item:
    it = gen.resolve(ref)
    if ref.refmod is not None:
        raise Unknown(f"{role} {ref.name}: reference-modified")
    if it.category != "ALPHANUMERIC" or it.usage != "DISPLAY" or it.children or it.justified:
        raise Unknown(f"{role} {ref.name}: not an elementary alphanumeric item")
    return it


def _element(gen, ref: E.Ref, it: L.Item) -> tuple[int, int]:
    """The byte range of the element a literal-subscripted reference names, within the item's record."""
    from gitgalaxy.tools.cobol_to_java.det.gen import _occurs_chain

    chain = _occurs_chain(it)
    if len(chain) != len(ref.subscripts):
        raise Unknown(f"{ref.name}: {len(ref.subscripts)} subscripts for {len(chain)} OCCURS levels")
    off = it.offset
    for lvl, sub in zip(chain, ref.subscripts):
        n = _const_int(sub)
        if n is None or lvl.depending:
            raise Unknown(f"{ref.name}: a subscript that is not a literal")
        if not 1 <= n <= lvl.occurs:
            raise Unknown(f"{ref.name}({n}): outside the table")
        off += (n - 1) * lvl.size
    return off, off + it.size


def _fit(text: str, size: int) -> str:
    """An alphanumeric MOVE into an item of `size` bytes: cut on the right, padded with blanks."""
    return text[:size].ljust(size)


def _source_values(gen, src, dst: L.Item, seen: tuple, why: str) -> set[str]:
    """The contents (dst.size characters) a MOVE of `src` leaves in `dst`."""
    if isinstance(src, E.Lit) and isinstance(src.value, str):
        return {_fit(src.value, dst.size)}
    if isinstance(src, E.Ref):
        it = _plain_text_item(gen, src, "MOVE source")
        if it is dst:
            raise Unknown(f"{why}: MOVE of the item to itself")
        return {_fit(v, dst.size) for v in _item_values(gen, src, it, seen)}
    raise Unknown(f"{why}: the MOVE source is not an alphanumeric literal or item")


def _item_values(gen, ref: E.Ref, it: L.Item, seen: tuple) -> set[str]:
    """Every content an elementary alphanumeric item can hold, in the characters of its bytes: its VALUE-fixed bytes
    and each MOVE into it of a known value. Anything else that may write it (or a byte of it) is an Unknown."""
    if id(it) in seen:
        return set()  # a cycle of MOVEs: the values it adds are the ones already collected
    seen = (*seen, id(it))
    if it.section != "WORKING-STORAGE":
        raise Unknown(f"{ref.name}: not in WORKING-STORAGE, so its initial content is not the program's")
    lo, hi = _element(gen, ref, it) if ref.subscripts else (it.offset, it.offset + it.size)
    rec = it.record
    mask = _valued(rec)
    if not all(mask[lo:hi]):
        raise Unknown(f"{ref.name}: no VALUE clause fixes its initial content")
    values = {L.image(rec)[lo:hi].decode("latin-1")}
    names = _overlap_names(gen, it)
    for para in gen.p.proc.paragraphs:
        for st in S.walk(para.body):
            if not _may_write(st, names):
                continue
            if st.kind == "MOVE" and len(st.data["to"]) == 1:
                tgt = st.data["to"][0]
                if not tgt.subscripts and tgt.refmod is None and not ref.subscripts and it.occurs == 1:
                    try:
                        same = gen.resolve(tgt) is it
                    except Exception:
                        same = False
                    if same:
                        values |= _source_values(gen, st.data["from"], it, seen, f"line {st.line}")
                        continue
            raise Unknown(f"{ref.name}: {st.kind} at line {st.line} may change it")
    return values


def _reaching(gen, s: S.Stmt, ref: E.Ref, it: L.Item) -> set[str] | None:
    """The one content a MOVE earlier on the CALL's own path leaves in the item, or None when none is found before
    the paragraph's start (or a loop is crossed). A statement between that may change the item is an Unknown."""
    names = _overlap_names(gen, it)
    flow = _flow(gen)
    here = flow.get(id(s))
    if here is None:
        return None
    seen_paras: set[int] = set()
    while here is not None:
        stmts, i, parent = here
        for j in range(i - 1, -1, -1):
            st = stmts[j]
            if st.kind == "MOVE" and len(st.data["to"]) == 1 and st.data["to"][0].name == ref.name:
                tgt = st.data["to"][0]
                if not tgt.subscripts and tgt.refmod is None and gen.resolve(tgt) is it:
                    return _source_values(gen, st.data["from"], it, (id(it),), f"line {st.line}")
            for sub in _closure(gen, [st], seen_paras):
                if _may_write(sub, names):
                    raise Unknown(f"{ref.name}: {sub.kind} at line {sub.line} may change it before the CALL")
        if parent is None:
            return None
        if parent.kind == "PERFORM" and (
            parent.data.get("until") or parent.data.get("varying") or parent.data.get("times")
        ):
            return None  # a loop: the body's later statements reach the CALL again
        here = flow.get(id(parent))
    return None


def values(gen, s: S.Stmt) -> list[str]:
    """The program names (blanks trimmed) the CALL's identifier can hold; Unknown (its reason) when not known."""
    ref = s.data["dynamic"]
    it = _plain_text_item(gen, ref, "CALL")
    if ref.subscripts or it.occurs > 1 or any(a.occurs > 1 for a in _ancestors(it)):
        raise Unknown(f"{ref.name}: a table element as the program name")
    first = None
    try:
        contents = _reaching(gen, s, ref, it)
    except Unknown as e:
        contents, first = None, str(e)  # something between the last MOVE and the CALL may change it
    if contents is None:
        try:
            contents = _item_values(gen, ref, it, ())  # every write of the item is looked at
        except Unknown as e:
            raise Unknown(f"{first}; {e}" if first else str(e)) from e
    return sorted({c.rstrip(" ") for c in contents})


def _ancestors(it: L.Item):
    a = it.parent
    while a is not None:
        yield a
        a = a.parent


def targets(gen, s: S.Stmt) -> list[str]:
    """`values`, each checked to be a program the port can call: an unknown value, a name no estate service or
    library routine answers to, or one the port does not match (blank, mixed case, over 8 characters) is refused by name."""
    from gitgalaxy.tools.cobol_to_java.det.gen import LIBRARY, Untranslatable

    ref = s.data["dynamic"]
    try:
        names = values(gen, s)
    except Unknown as e:
        raise Untranslatable(f"{_name_of(ref)}: the program name is not statically known ({e})") from e
    except Untranslatable as e:
        raise Untranslatable(f"{_name_of(ref)}: {e}") from e
    for n in names:
        if n in REFUSED_BY_NAME:
            raise Untranslatable(REFUSED_BY_NAME[n])
        if not n:
            raise Untranslatable(f"{_name_of(ref)}: a blank program name can reach the CALL")
        if not _NAME.fullmatch(n):
            raise Untranslatable(
                f"{n!r}: not a program name the port matches (uppercase, 8 characters at most: PGMNAME(COMPAT))"
            )
        if n != "CEE3ABD" and n not in gen.callees and n not in LIBRARY:
            raise Untranslatable(f"{n}: no program of that name with a CALL entry in the estate")
    return names
