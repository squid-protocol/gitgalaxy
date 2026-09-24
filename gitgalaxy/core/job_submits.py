# ==============================================================================
# GitGalaxy Core: job submission through the internal reader (#3448)
#
# PURPOSE:
# A program can submit a batch job by writing JCL to the JES internal reader.
# The engine already records both halves of the online case -- the CICS
# `WRITEQ TD QUEUE('JOBS')` (cics_resource_data) and the CSD extrapartition
# `TDQUEUE(JOBS) DDNAME(INREADER)` (csd_resource_data) -- but not the edge
# "transaction X submits job Y", and nothing at all of the batch case, a step
# whose DD is `SYSOUT=(A,INTRDR)`. An online->batch (or job->job) dependency
# is exactly what breaks in a migration. This channel records the per-file
# evidence, and GalaxyIR.job_submissions joins it:
#
#   kind    file   meaning                                      step  name  target
#   JOB     COBOL  a literal JCL job card `//NAME JOB ...`      -     NAME  -
#   EXEC    COBOL  a literal `//STEP EXEC PROC=P | PGM=P | P`   STEP  -     P (target_kind PROC/PGM)
#   INTRDR  JCL    a DD routed to the internal reader           STEP  DD    the step's SYSUT1 DSN
#                  (`SYSOUT=(class,INTRDR)`)                                (target_kind DSN), if any
#
# CardDemo's CORPT00C builds its report job as working-storage VALUE literals
# (`"//TRNRPT00 JOB 'TRAN REPORT',..."`, `"//STEP10 EXEC PROC=TRANREPT"`) and
# writes them line by line to TD queue JOBS; INTRDRJ1.JCL copies member
# INTRDRJ2 of a JCL library to `SYSOUT=(A,INTRDR)` with IEBGENER.
#
# SCOPE AND NON-SCOPE:
#   - A COBOL file's EXEC cards are kept only when the same file carries a JOB
#     card: a JOB card literal is the evidence that the literals are JCL, not a
#     `//` that happens to start a DISPLAY text.
#   - Whether a TD queue reaches the internal reader (its DDNAME bound to
#     SYSOUT=(x,INTRDR) in region JCL, or the writer embeds a JOB card) is the
#     reader's join, never decided here.
#   - The submitted JCL's contents are not re-parsed: a job card's name and its
#     EXEC targets are what the migration question needs.
#   - Bounded: the COBOL scan is one pass of a literal regex whose every
#     quantifier is capped; the JCL half reads the already-parsed statements.
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

# A literal that holds one JCL card: the opening quote, `//`, an optional
# name, then JOB or EXEC and the rest of the card up to the closing quote.
_CARD = re.compile(
    r"(['\"])//([A-Z@#$][A-Z0-9@#$]{0,7})?[ \t]{1,20}(JOB|EXEC)(?![A-Z0-9@#$])((?:(?!\1)[^\n]){0,80})\1",
    re.I,
)
_EXEC_TARGET = re.compile(r"^[ \t]{0,20}(?:(PROC|PGM)=)?([A-Z@#$][A-Z0-9@#$]{0,7})", re.I)
_SYSOUT_INTRDR = re.compile(r"(?<![A-Z0-9])SYSOUT=\([^,()]{0,8},[ \t]{0,4}INTRDR[ \t]{0,4}[,)]", re.I)


def cobol_job_cards(code_stream: str, shielded: Optional[Callable[[int], bool]] = None) -> list[dict[str, Any]]:
    """The JCL JOB and EXEC cards one COBOL file holds as literals (see the header).

    `shielded(offset)` says the offset is inside ANOTHER literal (so the quote
    found there is not an opening quote). EXEC cards are dropped unless the file
    also holds a JOB card.
    """
    if not code_stream or "//" not in code_stream:
        return []
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]
    rows: list[dict[str, Any]] = []
    for m in _CARD.finditer(code_stream):
        if shielded is not None and shielded(m.start()):
            continue
        name = (m.group(2) or "").upper() or None
        line = bisect.bisect_left(newlines, m.start()) + 1
        if m.group(3).upper() == "JOB":
            rows.append({"kind": "JOB", "step": None, "name": name, "target_kind": None, "target": None, "line": line})
            continue
        target = _EXEC_TARGET.match(m.group(4))
        if not target:
            continue
        kind = (target.group(1) or "PROC").upper()
        rows.append(
            {
                "kind": "EXEC",
                "step": name,
                "name": None,
                "target_kind": kind,
                "target": target.group(2).upper(),
                "line": line,
            }
        )
    if not any(r["kind"] == "JOB" for r in rows):
        return []
    return rows


def jcl_intrdr_dds(statements: list[tuple[int, str, str, str]]) -> list[dict[str, Any]]:
    """Every DD a JCL file routes to the internal reader, from its parsed
    statements (mainframe_boundary._jcl_statements: line, name, operation,
    operands). `target` is the same step's SYSUT1 DSN -- what IEBGENER copies to
    SYSUT2 -- when the step has one."""
    rows: list[dict[str, Any]] = []
    step: Optional[str] = None
    step_rows: list[dict[str, Any]] = []
    sysut1: Optional[str] = None

    def close() -> None:
        for r in step_rows:
            if sysut1:
                r["target_kind"], r["target"] = "DSN", sysut1
        rows.extend(step_rows)

    for line, name, operation, operands in statements:
        if operation in ("EXEC", "PROC", "PEND", "JOB"):
            close()
            step, step_rows, sysut1 = (name or None) if operation == "EXEC" else None, [], None
            continue
        if operation != "DD":
            continue
        if name == "SYSUT1":
            dsn = re.search(r"(?<![A-Z0-9])DSN(?:AME)?=([A-Z0-9@#$.&()+-]{1,60})", operands, re.I)
            sysut1 = dsn.group(1).upper() if dsn else None
        if _SYSOUT_INTRDR.search(operands):
            step_rows.append(
                {
                    "kind": "INTRDR",
                    "step": step,
                    "name": name or None,
                    "target_kind": None,
                    "target": None,
                    "line": line,
                }
            )
    close()
    return rows
