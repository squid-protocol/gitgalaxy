"""#4892: a CALL of an MQI routine (MQOPEN, MQGET, MQPUT, MQPUT1, MQCLOSE: gitgalaxy/standards/mq.py) on the det
runtime's queue manager (cobolrt.cics.DetMq onto cobolrt.mq.QueueManager, the twin of tests/equivalence/mq/ggmq.c). Every
parameter is passed BY REFERENCE as an item of the program's storage, each MQLONG a fullword BINARY item; a CICS program
only (the task's queue manager, register W6). Anything else -- another MQI call, a batch program, a literal or BY
CONTENT argument, a COMP-5 MQLONG -- is a translation hole that names why."""

from __future__ import annotations

import gitgalaxy.tools.cobol_to_java.det.expr as E
from gitgalaxy.standards.mq import CALLS, MQLONG, UNMODELLED
from gitgalaxy.tools.cobol_to_java.det.cics_common import Untranslatable

RUNTIME = "__PACKAGE__.cobolrt.cics.DetMq"  # the port's MQI calls (cobolrt/cics/DetMq.java)


def handles(prog: str) -> bool:
    """The program name is an MQI call: modelled (CALLS) or refused by name (UNMODELLED)."""
    return prog in CALLS or prog in UNMODELLED


def call(gen, prog: str, args: list, ind: str) -> list[str]:
    """The Java of `CALL prog USING args` (gen: the det Gen; raises its Untranslatable)."""
    if prog in UNMODELLED:
        raise Untranslatable(f"CALL {prog}: {UNMODELLED[prog]} is not modelled (register W6)")
    if gen.cics is None:
        raise Untranslatable(f"CALL {prog} outside CICS: batch MQ (MQCONN) is not modelled (register W6)")
    params = CALLS[prog]
    if len(args) != len(params) or any(m != "REFERENCE" or not isinstance(a, E.Ref) for m, a in args):
        raise Untranslatable(f"CALL {prog}: {len(params)} items BY REFERENCE expected")
    for p, (_, a) in zip(params, args, strict=True):
        it = gen.resolve(a)
        if p in MQLONG and (it.usage != "BINARY" or it.size != 4 or a.refmod is not None):
            raise Untranslatable(f"CALL {prog}: {p} {a.name} is not a fullword BINARY item (PIC S9(9) BINARY)")
    refs = ", ".join(["task", *(gen.field_expr(a) for _, a in args)])
    return [ind + RUNTIME + "." + prog.lower() + "(" + refs + ");"]
