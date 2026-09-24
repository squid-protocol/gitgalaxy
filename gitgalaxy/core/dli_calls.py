# ==============================================================================
# GitGalaxy Core: IMS DL/I calls (#3450)
#
# PURPOSE:
# IMS database calls were invisible: nothing said which programs read or update
# which IMS segments. Both interfaces become rows, one per call:
#
#   interface  EXEC  -- `EXEC DLI GU USING PCB(n) SEGMENT(S) INTO(A) WHERE(K = V)`
#              CALL  -- `CALL 'CBLTDLI' USING FUNC PCB-MASK IO-AREA SSA1 ... SSAn`
#   function   EXEC: the command (GU / GN / GNP / GHU / ISRT / REPL / DLET / SCHD
#              / TERM / CHKP ...); CALL: None -- it lives in the function operand's
#              VALUE, usually in a copybook, which the reader resolves
#   function_operand  CALL: the first argument as written
#   pcb        EXEC: the PCB(...) operand; CALL: the second argument
#   io_area    EXEC: INTO / FROM; CALL: the third argument
#   segments   EXEC: each SEGMENT(...) of a path call, comma-joined
#   ssas       CALL: the SSA arguments after the I/O area, comma-joined
#   where      EXEC: each WHERE(...) as written, `;`-joined
#   psb        EXEC SCHD PSB(...) as written (the name or the data-name holding it)
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file, operands as written. Resolving a CBLTDLI function
#     code or an SSA's segment / qualification through its working-storage VALUEs
#     (which live in copybooks) is the reader's (GalaxyIR.ims_calls), which sees
#     every COPY-expanded record.
#   - A PCB is kept as written; which database a segment lives in and whether the
#     program's PSB allows each access is #3477's (core/ims_gen.py,
#     GalaxyIR.ims_access_check).
#   - Bounded: the EXEC DLI block at END-EXEC / the next EXEC / `_BLOCK_LIMIT`,
#     read with the cics_resources option walker; CBLTDLI arguments with the
#     #3454 USING reader.
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

from gitgalaxy.core.call_using import blank_stream, call_using_args
from gitgalaxy.core.cics_resources import _BLOCK_LIMIT, _END_EXEC, _options

_EXEC_DLI = re.compile(r"(?<![A-Z0-9-])EXEC[ \t\n]{1,200}DLI(?![A-Z0-9-])", re.I)
_CBLTDLI = re.compile(r"(?<![A-Z0-9-])CALL[ \t\n]{1,200}(?:'(?:CBLTDLI|AIBTDLI)'|\"(?:CBLTDLI|AIBTDLI)\")", re.I)


def _unparen(value: Optional[str]) -> Optional[str]:
    """`(PSB-NAME)` -> `PSB-NAME` (SCHD PSB((name)) names a data item)."""
    if value is None:
        return None
    v = value.strip()
    while len(v) >= 2 and v[0] == "(" and v[-1] == ")":
        v = v[1:-1].strip()
    return v or None


def extract_dli_calls(code_stream: str, shielded: Optional[Callable[[int], bool]] = None) -> list[dict[str, Any]]:
    """Every EXEC DLI command and CALL 'CBLTDLI' of one COBOL file (see the header)."""
    if not code_stream or ("DLI" not in code_stream.upper()):
        return []
    text = blank_stream(code_stream)
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(offset: int) -> int:
        return bisect.bisect_left(newlines, offset) + 1

    def row(**kw: Any) -> dict[str, Any]:
        base = {
            "interface": None,
            "function": None,
            "function_operand": None,
            "pcb": None,
            "io_area": None,
            "segments": None,
            "ssas": None,
            "where": None,
            "psb": None,
            "line": 0,
        }
        base.update(kw)
        return base

    rows: list[tuple[int, dict[str, Any]]] = []
    execs = [m for m in _EXEC_DLI.finditer(text) if shielded is None or not shielded(m.start())]
    for i, m in enumerate(execs):
        stop = execs[i + 1].start() if i + 1 < len(execs) else len(text)
        block = text[m.end() : min(stop, m.end() + _BLOCK_LIMIT)]
        end = _END_EXEC.search(block)
        ordered = _options(block[: end.start()] if end else block)
        if not ordered or ordered[0][1] is not None:
            continue
        function = ordered[0][0]
        rest = [(k, v) for k, v in ordered[1:] if k != "USING"]
        segments = [v.strip().upper() for k, v in rest if k == "SEGMENT" and v]
        wheres = [" ".join(v.split()) for k, v in rest if k == "WHERE" and v]
        opts = dict(rest)
        rows.append(
            (
                m.start(),
                row(
                    interface="EXEC",
                    function=function,
                    pcb=(opts.get("PCB") or "").strip().upper() or None,
                    io_area=((opts.get("INTO") or opts.get("FROM") or "").strip().upper() or None),
                    segments=",".join(segments) or None,
                    where=";".join(wheres) or None,
                    psb=(_unparen(opts.get("PSB")) or "").upper() or None,
                    line=line_of(m.start()),
                ),
            )
        )
    for m in _CBLTDLI.finditer(text):
        if shielded is not None and shielded(m.start()):
            continue
        args = [a for a in (call_using_args(text, m.end()) or "").split(",") if a]
        rows.append(
            (
                m.start(),
                row(
                    interface="CALL",
                    function_operand=args[0] if args else None,
                    pcb=args[1] if len(args) > 1 else None,
                    io_area=args[2] if len(args) > 2 else None,
                    ssas=",".join(args[3:]) or None,
                    line=line_of(m.start()),
                ),
            )
        )
    rows.sort(key=lambda r: r[0])
    return [r for _, r in rows]
