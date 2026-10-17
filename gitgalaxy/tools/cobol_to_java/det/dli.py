"""IMS DL/I database calls in a det port (#4893): a batch DL/I program -- IMS enters its ENTRY 'DLITCBL' USING its
PCBs -- and its CALL 'CBLTDLI' USING function pcb io-area [ssa ...], each run by the det runtime's DetDli
(cobolrt/dli/DetDli.java), the twin of the equivalence harness's COBOL-side model (tests/equivalence/ims/ggdli.c).
Register family I states the model; what it does not model is refused here by name, or stops the run by name there.

    DetDli.enter(pcb-1, ..., pcb-n)                     the program's entry (runBatch): binds the PSB's DB PCBs
    DetDli.call(function, pcb, io, ssa ...)             each CALL 'CBLTDLI'; RETURN-CODE 0 after it (register I1)
    DetDli.leave()                                      the step ended: the databases written for the comparison

and, under CICS (#5278, register I5), the EXEC DLI commands SCHD PSB and TERM, each answering DIBSTAT:

    DIBSTAT = DetDli.schedule(psb, nodhabend)           EXEC DLI SCHD PSB(name | (area)) [NODHABEND]
    DIBSTAT = DetDli.terminate()                        EXEC DLI TERM
"""

from __future__ import annotations

import re
from typing import Any

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import stmt as S

ENTRY = "DLITCBL"  # IMS's entry name for a DL/I program written in COBOL
CALL = "CBLTDLI"
# the other DL/I language interfaces: refused by name (CBLTDLI's call through an AIB, LE's CEETDLI)
REFUSED_BY_NAME = {
    "AIBTDLI": "CALL AIBTDLI: the DL/I call through an AIB (application interface block) is not modelled",
    "CEETDLI": "CALL CEETDLI: the Language Environment DL/I interface is not modelled",
}
BINARY = {"COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"}


def entry_pcbs(proc: S.Procedure) -> list[str] | None:
    """The PCB names of a program IMS enters at ENTRY 'DLITCBL' (its first statement, stmt._entry), else None."""
    first = next((p.body[0] for p in proc.paragraphs if p.body), None)
    if first is None or first.kind != "ENTRY" or not first.data.get("first") or first.data["name"].upper() != ENTRY:
        return None
    return [r.name.upper() for r in first.data["using"]]


def call(gen: Any, s: S.Stmt, ind: str) -> list[str]:
    """CALL 'CBLTDLI' USING function pcb io-area [ssa-1 ... ssa-15]: DetDli.call, then RETURN-CODE 0."""
    from gitgalaxy.tools.cobol_to_java.det.gen import Untranslatable

    pcbs = gen.dli_pcbs
    if pcbs is None:
        raise Untranslatable(f"CALL {CALL}: a program IMS does not enter at ENTRY '{ENTRY}' (BMP, MPP or CICS) "
                             "is not modelled")  # fmt: skip
    args = s.data["args"]
    if s.phrases:
        raise Untranslatable(f"CALL {CALL}: ON EXCEPTION / OVERFLOW phrases are not modelled")
    if not 3 <= len(args) <= 18:
        raise Untranslatable(f"CALL {CALL}: a function, a PCB, an I/O area and up to 15 SSAs expected")
    if any(m != "REFERENCE" or not isinstance(a, E.Ref) for m, a in args):
        raise Untranslatable(f"CALL {CALL}: items BY REFERENCE expected")
    refs = [a for _, a in args]
    first = gen.resolve(refs[0])
    if (getattr(first, "usage", None) or "").upper() in BINARY:
        raise Untranslatable(f"CALL {CALL}: the parameter-count form (a binary count first) is not modelled")
    if refs[1].name.upper() not in pcbs or refs[1].subscripts or refs[1].refmod is not None:
        raise Untranslatable(f"CALL {CALL}: the PCB {refs[1].name} is not one IMS passed at ENTRY '{ENTRY}'")
    fields = ", ".join(gen.field_expr(r) for r in refs)
    rc = gen.field_expr(E.Ref("RETURN-CODE"))
    return [f"{ind}DetDli.call({fields});", f"{ind}Cobol.store({rc}, BigDecimal.ZERO, false, CS);"]


# ---- EXEC DLI under CICS (#5278): SCHD PSB and TERM; the segment commands (GU REPL ISRT ...) stay holes by name -------
_EXEC_DLI = re.compile(r"(?is)\s*EXEC\s+DLI\s+(.*?)\s*(?:END-EXEC\s*\.?)?\s*$")
_SCHD = re.compile(
    r"(?is)SCHD\s+PSB\s*\(\s*(?:\(\s*(?P<area>[A-Z0-9-]+)\s*\)|'(?P<lit>[^'\s]{1,8})'|(?P<name>[A-Z0-9-]{1,8}))\s*\)"
    r"(?P<nodh>\s+NODHABEND)?"
)


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
    from gitgalaxy.tools.cobol_to_java.det.gen import Untranslatable, jstr

    if gen.cics is None:
        raise Untranslatable("EXEC DLI outside CICS: a batch program calls CBLTDLI (register I5)")
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
        if s["area"]:
            it = gen.resolve(E.Ref(s["area"]))
            if it.usage not in (None, "", "DISPLAY") or it.size is None:
                raise Untranslatable(f"EXEC DLI SCHD: the PSB name area {s['area']} is not a DISPLAY item")
            name = gen.field_expr(E.Ref(s["area"]))
        else:
            name = jstr((s["lit"] or s["name"]).upper())
        call = f"{runtime}.schedule({name}, {'true' if s['nodh'] else 'false'})"
    elif verb == "TERM":
        if body.split()[1:]:
            raise Untranslatable("EXEC DLI TERM: no option is modelled (register I5)")
        call = f"{runtime}.terminate()"
    else:
        raise Untranslatable(f"EXEC DLI {verb}: the segment commands (GU, GN, REPL, ISRT, DLET ...) are not modelled "
                             "(register I5)")  # fmt: skip
    return [f"{ind}Cobol.move({call}, {dibstat}, CS);"]
