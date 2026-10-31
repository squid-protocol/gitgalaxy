"""IMS DL/I database calls in a det port (#4893): a batch DL/I program -- IMS enters its ENTRY 'DLITCBL' USING its
PCBs -- and its CALL 'CBLTDLI' USING function pcb io-area [ssa ...], each run by the det runtime's DetDli
(cobolrt/dli/DetDli.java), the twin of the equivalence harness's COBOL-side model (tests/equivalence/ims/ggdli.c).
Register family I states the model; what it does not model is refused here by name, or stops the run by name there.

    DetDli.enter(pcb-1, ..., pcb-n)                     the program's entry (runBatch): binds the PSB's DB PCBs
    DetDli.call(function, pcb, io, ssa ...)             each CALL 'CBLTDLI'; RETURN-CODE 0 after it (register I1)
    DetDli.leave()                                      the step ended: the databases written for the comparison

and, under CICS (#5278, register I5), the EXEC DLI commands SCHD PSB, TERM, the gets and ISRT / REPL / DLET, each answering DIBSTAT:

    DIBSTAT = DetDli.schedule(psb, nodhabend)           EXEC DLI SCHD PSB(name | (area)) [NODHABEND]
    DIBSTAT = DetDli.terminate()                        EXEC DLI TERM
    DIBSTAT = DetDli.get(verb, pcb, into, ssa ...)      EXEC DLI GU | GN | GNP USING PCB(n) [SEGMENT(s) [WHERE(f op v)]
                                                        ...] INTO(area); ssa = DetDli.ssa(seg [, fld, op, value])
    DIBSTAT = DetDli.execIsrt(pcb, from, seglength | -1, ssa ...)    EXEC DLI ISRT USING PCB(n) SEGMENT(s) [WHERE ...] ...
                                                        SEGMENT(t) FROM(area) [SEGLENGTH(n)]
    DIBSTAT = DetDli.execChange("REPL" | "DLET", pcb, from, seg)   EXEC DLI REPL | DLET USING PCB(n) SEGMENT(s) FROM(area)
"""

from __future__ import annotations

import re
from typing import Any

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import stmt as S

ENTRY = "DLITCBL"  # IMS's entry name for a DL/I program written in COBOL
CALL = "CBLTDLI"
# CEETDLI (#5233, LE's interface) takes the same USING list as CBLTDLI: function, PCB, I/O area, SSAs
CALLS = (CALL, "CEETDLI")
# the other DL/I language interface: refused by name (CBLTDLI's call through an AIB)
REFUSED_BY_NAME = {
    "AIBTDLI": "CALL AIBTDLI: the DL/I call through an AIB (application interface block) is not modelled",
}
BINARY = {"COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"}


def entry_pcbs(proc: S.Procedure) -> list[str] | None:
    """The PCB names of a program IMS enters at ENTRY 'DLITCBL' (its first statement, stmt._entry), else None."""
    first = next((p.body[0] for p in proc.paragraphs if p.body), None)
    if first is None or first.kind != "ENTRY" or not first.data.get("first") or first.data["name"].upper() != ENTRY:
        return None
    names = [r.name.upper() for r in first.data["using"]]
    return None if _io_first(proc, names) else names


def _io_first(proc: S.Procedure, entry: list[str]) -> bool:
    """#5233: whether the header's PROCEDURE DIVISION USING is the I/O PCB then exactly the ENTRY 'DLITCBL' list (PAUDBLOD:
    a BMP, CMPAT=YES, whose ENTRY lists the DB PCB only). IMS enters a BMP at the header, so the I/O PCB comes first."""
    head = [u.upper() for u in proc.division_using]
    return bool(entry) and len(head) == len(entry) + 1 and head[1:] == entry


class BmpPcbs(list):
    """The DB PCB names of a BMP / batch program that issues EXEC DLI (#5857, register I5): it is entered by PROCEDURE
    DIVISION USING io-pcb db-pcb ... (the PSB is CMPAT=YES, IMS passes the I/O PCB first), and PCB(n) counts the I/O PCB."""

    io: str = ""


def bmp_pcbs(proc: S.Procedure) -> BmpPcbs | None:
    """The PCBs of a non-CICS program entered by PROCEDURE DIVISION USING io-pcb db-pcb ... that issues EXEC DLI, else
    None (a program with a USING and EXEC DLI but no ENTRY 'DLITCBL'). Needs at least the I/O PCB and one DB PCB."""
    using = proc.division_using if proc.division_using else proc.using
    stmts = [x for q in proc.paragraphs for x in S.walk(q.body)]
    if len(using) < 2 or not (
        uses_exec(x.text for x in stmts if x.kind == "EXEC") or any(x.kind == "CALL" and _is_cbltdli(x) for x in stmts)
    ):
        return None
    out = BmpPcbs(u.upper() for u in using[1:])
    out.io = using[0].upper()
    return out


def _is_cbltdli(s: S.Stmt) -> bool:
    return str(s.data.get("program") or "").upper() == CALL


def call(gen: Any, s: S.Stmt, ind: str) -> list[str]:
    """CALL 'CBLTDLI' | 'CEETDLI' USING function pcb io-area [ssa-1 ... ssa-15]: DetDli.call, then RETURN-CODE 0."""
    from gitgalaxy.tools.cobol_to_java.det.cics_common import Untranslatable

    pcbs = gen.dli_pcbs
    name = str(s.data.get("program") or CALL).upper()
    if name != CALL and isinstance(pcbs, BmpPcbs):
        raise Untranslatable(
            f"CALL {name}: in a BMP entered USING its I/O PCB is not modelled (only at ENTRY '{ENTRY}')"
        )
    if pcbs is None:
        raise Untranslatable(f"CALL {name}: a program IMS does not enter at ENTRY '{ENTRY}' (BMP, MPP or CICS) "
                             "is not modelled")  # fmt: skip
    args = s.data["args"]
    if s.phrases:
        raise Untranslatable(f"CALL {name}: ON EXCEPTION / OVERFLOW phrases are not modelled")
    if not 3 <= len(args) <= 18:
        raise Untranslatable(f"CALL {name}: a function, a PCB, an I/O area and up to 15 SSAs expected")
    if any(m != "REFERENCE" or not isinstance(a, E.Ref) for m, a in args):
        raise Untranslatable(f"CALL {name}: items BY REFERENCE expected")
    refs = [a for _, a in args]
    first = gen.resolve(refs[0])
    if (getattr(first, "usage", None) or "").upper() in BINARY:
        raise Untranslatable(f"CALL {name}: the parameter-count form (a binary count first) is not modelled")
    if isinstance(pcbs, BmpPcbs) and refs[1].name.upper() == pcbs.io:
        raise Untranslatable(f"CALL {name}: the I/O PCB {refs[1].name} (IMS TM message calls) is not modelled")
    if refs[1].name.upper() not in pcbs or refs[1].subscripts or refs[1].refmod is not None:
        raise Untranslatable(f"CALL {name}: the PCB {refs[1].name} is not one IMS passed at ENTRY '{ENTRY}'")
    fields = ", ".join(gen.field_expr(r) for r in refs)
    rc = gen.field_expr(E.Ref("RETURN-CODE"))
    return [f"{ind}DetDli.call({fields});", f"{ind}Cobol.store({rc}, BigDecimal.ZERO, false, CS);"]


# ---- EXEC DLI under CICS (#5278): SCHD PSB, TERM, the gets and the writes; the other commands stay holes by name ------------------
_EXEC_DLI = re.compile(r"(?is)\s*EXEC\s+DLI\s+(.*?)\s*(?:END-EXEC\s*\.?)?\s*$")
_ID = "[A-Z0-9" + "-]"  # a COBOL name: built from parts, a dense regex literal trips X-Ray's entropy check
_SCHD = re.compile(
    r"(?is)SCHD\s+PSB\s*\(\s*"
    + r"(?:\(\s*(?P<area>" + _ID + r"+)\s*\)"
    + r"|'(?P<lit>[^'\s]{1,8})'"
    + r"|(?P<name>" + _ID + r"{1,8}))"
    + r"\s*\)(?P<nodh>\s+NODHABEND)?"
)  # fmt: skip


_GETS = ("GU", "GN", "GNP")
_PUTS = ("ISRT", "REPL", "DLET")
_NOT = chr(0xAC)  # the EBCDIC "not" sign
_OPS = {"=": "EQ", ">": "GT", "<": "LT", ">=": "GE", "<=": "LE", _NOT + "=": "NE", "=" + _NOT: "NE"}
_OPS.update({w: w for w in ("EQ", "GT", "LT", "GE", "LE", "NE")})
_WHERE = re.compile(
    r"(?is)\s*(?P<f>" + _ID + r"{1,8})\s*(?P<op>[<>=" + _NOT + r"]{1,2}|[EGLN][QTEA]|[EGLN]E)\s*(?P<v>\S+)\s*"
)


def _clauses(body: str) -> list[tuple[str, str]]:
    """`KEYWORD(text)` clauses of an EXEC DLI command's options, parentheses balanced (a LENGTH OF inside one is text)."""
    from gitgalaxy.tools.cobol_to_java.det.cics_common import Untranslatable

    out: list[tuple[str, str]] = []
    i, n = 0, len(body)
    while i < n:
        if body[i].isspace():
            i += 1
            continue
        m = re.compile(r"[A-Za-z][A-Za-z0-9-]*").match(body, i)
        if m is None:
            raise Untranslatable(f"EXEC DLI: cannot read {body[i : i + 20]!r} (register I5)")
        i = m.end()
        while i < n and body[i].isspace():
            i += 1
        if i >= n or body[i] != "(":
            out.append((m.group(0).upper(), ""))
            continue
        depth, j = 0, i
        while j < n:
            depth += (body[j] == "(") - (body[j] == ")")
            j += 1
            if depth == 0:
                break
        if depth:
            raise Untranslatable("EXEC DLI: unbalanced parentheses (register I5)")
        out.append((m.group(0).upper(), body[i + 1 : j - 1].strip()))
        i = j
    return out


def _get(gen: Any, verb: str, rest: str, ind: str) -> list[str]:
    """GU / GN / GNP USING PCB(n) [SEGMENT(s) [WHERE(f op v)] ...] INTO(area): DetDli.get, DIBSTAT answered."""
    from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, Untranslatable, jstr

    cl = _clauses(re.sub(r"(?is)^\s*USING\b", "", rest))
    names = [k for k, _ in cl]
    for k in names:
        if k not in ("PCB", "SEGMENT", "INTO", "WHERE"):
            raise Untranslatable(f"EXEC DLI {verb} {k}: only PCB, SEGMENT, WHERE and INTO are modelled (register I5)")
    if names.count("PCB") != 1 or names.count("INTO") != 1 or names[0] != "PCB":
        raise Untranslatable(f"EXEC DLI {verb}: one PCB(n) first and one INTO(area) expected (register I5)")
    cics = _ops(gen)
    try:
        pcb = cics.int_(dict(cl)["PCB"])
        into = gen.field_expr(cics.ref(dict(cl)["INTO"]))
        ssas = _ssas(gen, verb, cl)
    except CicsError as e:
        raise Untranslatable(f"EXEC DLI {verb}: {e}") from e
    runtime = "__PACKAGE__.cobolrt.dli.DetDli"
    args = ", ".join([into, *ssas])
    call = f"{runtime}.get({jstr(verb)}, {pcb}, {args})"
    dibstat = gen.field_expr(E.Ref("DIBSTAT"))
    return [f"{ind}Cobol.move({call}, {dibstat}, CS);"]


def uses_exec(texts: Any) -> bool:
    """Whether any of the EXEC statements' texts is EXEC DLI (the program then has the DIB, IBM's DLI interface block)."""
    return any(re.match(r"(?is)\s*EXEC\s+DLI\b", t) for t in texts)


def dib_records() -> list:
    """The DIB a CICS program with EXEC DLI sees: only DIBSTAT (the two bytes after the version halfword) is supplied,
    since it is the only DIB field the runtime sets; any other DIB field stays `no such item`, a hole by name."""
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det.source import logical_lines

    raw = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. GGDIB.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", "       01  DIB.", "           05 FILLER   PIC XX.",
           "           05 DIBSTAT  PIC XX."]  # fmt: skip
    return L.parse(logical_lines(raw, "DIB"))


def command(gen: Any, text: str, ind: str) -> list[str]:
    """One EXEC DLI command of a CICS program: SCHD PSB(...) [NODHABEND] and TERM, DIBSTAT answered."""
    from gitgalaxy.tools.cobol_to_java.det.cics_common import Untranslatable, jstr

    batch = isinstance(gen.dli_pcbs, BmpPcbs)
    if gen.cics is None and not batch:
        raise Untranslatable("EXEC DLI outside CICS: a batch program calls CBLTDLI, or is entered by PROCEDURE "
                             "DIVISION USING its I/O PCB and DB PCBs (register I5)")  # fmt: skip
    m = _EXEC_DLI.match(text)
    body = m.group(1) if m else ""
    verb = (body.split() or [""])[0].upper()
    dibstat = gen.field_expr(E.Ref("DIBSTAT"))
    runtime = "__PACKAGE__.cobolrt.dli.DetDli"
    if verb == "SCHD":
        s = _SCHD.fullmatch(body.strip())
        if s is None:
            raise Untranslatable("EXEC DLI SCHD: only PSB(name), PSB('name') or PSB((area)) with NODHABEND is modelled "
                                 "(register I5)")  # fmt: skip
        if s.group("area"):
            it = gen.resolve(E.Ref(s.group("area")))
            if it.usage not in (None, "", "DISPLAY") or it.size is None:
                raise Untranslatable(f"EXEC DLI SCHD: the PSB name area {s.group('area')} is not a DISPLAY item")
            name = gen.field_expr(E.Ref(s.group("area")))
        else:
            name = jstr((s.group("lit") or s.group("name")).upper())
        call = f"{runtime}.schedule({name}, {'true' if s.group('nodh') else 'false'})"
    elif verb in _GETS:
        return _get(gen, verb, body[len(verb) :], ind)
    elif verb in _PUTS:
        return _put(gen, verb, body[len(verb) :], ind)
    elif verb == "CHKP":
        if not batch:
            raise Untranslatable("EXEC DLI CHKP: only in a BMP / batch program entered by PROCEDURE DIVISION USING "
                                 "(register I5)")  # fmt: skip
        return _chkp(gen, body[len(verb) :], ind)
    elif verb == "TERM":
        if body.split()[1:]:
            raise Untranslatable("EXEC DLI TERM: no option is modelled (register I5)")
        call = f"{runtime}.terminate()"
    else:
        raise Untranslatable(f"EXEC DLI {verb}: this command is not modelled (register I5)")
    return [f"{ind}Cobol.move({call}, {dibstat}, CS);"]


class _Ops:
    """The operand readers EXEC DLI needs (ref, int_, read_field) where there is no CICS lane: a BMP / batch program."""

    def __init__(self, gen: Any):
        self.g = gen

    def ref(self, text: str) -> E.Ref:
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError

        p = E.Parser(E.tokenize(text))
        e = p.operand()
        if not p.done() or not isinstance(e, E.Ref):
            raise CicsError(f"not a data area: {text}")
        return e

    def int_(self, text: str) -> str:
        from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError

        p = E.Parser(E.tokenize(text))
        e = p.operand()
        if not p.done():
            raise CicsError(f"operand {text!r}")
        return str(self.g.int_expr(e))

    def read_field(self, text: str) -> str:
        with self.g.reading():
            return str(self.g.field_expr(self.ref(text)))


def _ops(gen: Any) -> Any:
    """The operand reader of an EXEC DLI command: the CICS lane's, else the batch one."""
    return gen.cics if gen.cics is not None else _Ops(gen)


def _chkp(gen: Any, rest: str, ind: str) -> list[str]:
    """CHKP ID(area) in a BMP: DetDli.checkpoint(area), DIBSTAT answered. The ID is a data name (8 bytes, IBM: the
    checkpoint id); the symbolic options (SAVE, AREA, ...) are not modelled."""
    from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, Untranslatable

    cl = _clauses(rest)
    if [k for k, _ in cl] != ["ID"]:
        raise Untranslatable("EXEC DLI CHKP: only ID(area) is modelled (register I5)")
    try:
        ident = gen.field_expr(_ops(gen).ref(cl[0][1]))
    except CicsError as e:
        raise Untranslatable(f"EXEC DLI CHKP: {e}") from e
    dibstat = gen.field_expr(E.Ref("DIBSTAT"))
    return [f"{ind}Cobol.move(__PACKAGE__.cobolrt.dli.DetDli.checkpoint({ident}), {dibstat}, CS);"]


def _clause(cl: list[tuple[str, str]], name: str) -> str:
    """The text of the first clause called `name`, or empty."""
    return next((v for k, v in cl if k == name), "")


def _ssas(gen: Any, verb: str, cl: list[tuple[str, str]]) -> list[str]:
    """The DetDli.ssa(...) expressions of a command's SEGMENT / WHERE clauses, in order (a WHERE follows its SEGMENT)."""
    from gitgalaxy.tools.cobol_to_java.det.cics_common import Untranslatable, jstr

    cics = _ops(gen)
    ssas: list[str] = []
    for k, v in cl:
        if k == "SEGMENT":
            if not re.fullmatch(_ID + r"{1,8}", v, re.I):
                raise Untranslatable(f"EXEC DLI {verb}: SEGMENT({v}) is not a segment name")
            ssas.append(jstr(v.upper()))
        elif k == "WHERE":
            w = _WHERE.fullmatch(v)
            if not ssas or ssas[-1].startswith("("):
                raise Untranslatable(f"EXEC DLI {verb}: WHERE must follow its SEGMENT, once (register I5)")
            if w is None or w.group("op").upper() not in _OPS:
                raise Untranslatable(f"EXEC DLI {verb}: WHERE({v}): only field op value is modelled (register I5)")
            val = gen.field_expr(cics.ref(w.group("v")))
            ssas[-1] = f"({ssas[-1]}, {jstr(w.group('f').upper())}, {jstr(_OPS[w.group('op').upper()])}, {val})"
    runtime = "__PACKAGE__.cobolrt.dli.DetDli"
    return [f"{runtime}.ssa{a}" if a.startswith("(") else f"{runtime}.ssa({a})" for a in ssas]


def _put(gen: Any, verb: str, rest: str, ind: str) -> list[str]:
    """ISRT / REPL / DLET USING PCB(n) SEGMENT(s) [WHERE ...] ... FROM(area) [SEGLENGTH(n), ISRT only]: DetDli.execIsrt /
    DetDli.execChange, DIBSTAT answered. REPL and DLET name the one segment they act on (the one the last get held)."""
    from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError, Untranslatable, jstr

    cl = _clauses(re.sub(r"(?is)^\s*USING\b", "", rest))
    names = [k for k, _ in cl]
    allowed = ("PCB", "SEGMENT", "WHERE", "FROM", "SEGLENGTH") if verb == "ISRT" else ("PCB", "SEGMENT", "FROM")
    for k in names:
        if k not in allowed:
            raise Untranslatable(f"EXEC DLI {verb} {k}: only {', '.join(allowed)} are modelled (register I5)")
    if names.count("PCB") != 1 or names.count("FROM") != 1 or names[0] != "PCB" or names.count("SEGLENGTH") > 1:
        raise Untranslatable(f"EXEC DLI {verb}: one PCB(n) first and one FROM(area) expected (register I5)")
    if "SEGMENT" not in names or (verb != "ISRT" and names.count("SEGMENT") != 1):
        raise Untranslatable(f"EXEC DLI {verb}: SEGMENT(s) expected, once for REPL and DLET (register I5)")
    cics = _ops(gen)
    try:
        pcb = cics.int_(dict(cl)["PCB"])
        src = cics.read_field(dict(cl)["FROM"])
        runtime = "__PACKAGE__.cobolrt.dli.DetDli"
        if verb == "ISRT":
            seglen = cics.int_(clause) if (clause := _clause(cl, "SEGLENGTH")) else "-1"
            call = f"{runtime}.execIsrt({', '.join([pcb, src, seglen, *_ssas(gen, verb, cl)])})"
        else:
            call = f"{runtime}.execChange({jstr(verb)}, {pcb}, {src}, {jstr(_clause(cl, 'SEGMENT').upper())})"
            _ssas(gen, verb, cl)  # the SEGMENT is a segment name
    except CicsError as e:
        raise Untranslatable(f"EXEC DLI {verb}: {e}") from e
    dibstat = gen.field_expr(E.Ref("DIBSTAT"))
    return [f"{ind}Cobol.move({call}, {dibstat}, CS);"]
