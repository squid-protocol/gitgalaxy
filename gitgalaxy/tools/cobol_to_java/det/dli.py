"""IMS DL/I database calls in a det port (#4893): a batch DL/I program -- IMS enters its ENTRY 'DLITCBL' USING its
PCBs -- and its CALL 'CBLTDLI' USING function pcb io-area [ssa ...], each run by the det runtime's DetDli
(cobolrt/dli/DetDli.java), the twin of the equivalence harness's COBOL-side model (tests/equivalence/ims/ggdli.c).
Register family I states the model; what it does not model is refused here by name, or stops the run by name there.

    DetDli.enter(pcb-1, ..., pcb-n)                     the program's entry (runBatch): binds the PSB's DB PCBs
    DetDli.call(function, pcb, io, ssa ...)             each CALL 'CBLTDLI'; RETURN-CODE 0 after it (register I1)
    DetDli.leave()                                      the step ended: the databases written for the comparison
"""

from __future__ import annotations

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
