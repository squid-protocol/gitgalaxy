# ==============================================================================
# GitGalaxy Core: units of work and error handling (#3453)
#
# PURPOSE:
# Commit / rollback points and error handlers only fed risk-signal COUNTS. A
# migration has to preserve where a program's unit of work ends and which
# condition goes to which handler, so each becomes a row:
#
#   kind              source  verb (as written)          condition        target (target_kind)
#   COMMIT            CICS    SYNCPOINT                  -                -
#   COMMIT            SQL     COMMIT [WORK]              -                -
#   ROLLBACK          CICS    SYNCPOINT ROLLBACK         -                -
#   ROLLBACK          SQL     ROLLBACK [WORK | TO SAVEPOINT]
#   HANDLE_CONDITION  CICS    HANDLE CONDITION           NOTFND           PARA (LABEL) |
#                                                                         - (DEFAULT: the
#                                                                         condition named bare)
#   IGNORE_CONDITION  CICS    IGNORE CONDITION           LENGERR          -
#   HANDLE_ABEND      CICS    HANDLE ABEND               -                PARA (LABEL) | PGM
#                                                                         (PROGRAM) | CANCEL | RESET
#   HANDLE_AID        CICS    HANDLE AID                 PF3              PARA (LABEL)
#   PUSH_HANDLE / POP_HANDLE  CICS
#   ABEND             CICS    ABEND                      the ABCODE       -   (attributes:
#                                                                         NODUMP / CANCEL)
#   ON_UNIT / REVERT / SIGNAL  PLI  (#3491: PL/I condition handling, core/pli_on_units.py)
#   RESP_CHECK        CICS    the checked command        the DFHRESP(...) conditions tested
#                             (READ, LINK, ...)          on its RESP field, comma-joined;
#                                                        NULL when nothing tests it
#
# RESP CHECKS. A command coded `RESP(v)` (or NOHANDLE, which leaves the result in
# EIBRESP) is checked by the DFHRESP(...) comparisons on v that follow it: the
# window runs from its END-EXEC to the next command that sets v again, the next
# paragraph / section header, or `_RESP_WINDOW` characters. Inside it, a
# DFHRESP(x) counts once v has been mentioned (`IF v NOT = DFHRESP(NORMAL)`,
# `EVALUATE v WHEN DFHRESP(NOTFND)`), and so does a response code tested BY
# NUMBER on v (`v = 0`, `EVALUATE v WHEN 13`), named through _RESP_CODES. A
# RESP_CHECK with no condition is a command whose outcome is never tested -- a
# real finding, not an error.
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. The owning paragraph of each row, whether a
#     handler label is a paragraph of the program, and the implicit commit at
#     task end (EXEC CICS RETURN) are the reader's (GalaxyIR.units_of_work /
#     error_handlers), not decided here.
#   - IMS checkpoints (CHKP / SYNC through CBLTDLI) belong to the DL/I channel
#     (#3450), not here.
#   - Bounded: the cics_resources block/option walker for EXEC CICS; one capped
#     regex for EXEC SQL COMMIT / ROLLBACK; the RESP window is capped.
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

from gitgalaxy.core.cics_resources import _BLOCK_LIMIT, _END_EXEC, _EXEC_CICS, _options
from gitgalaxy.core.db2_declare_table import _blank_sequence_fields

_SP = r"[ \t\n]{1,200}"
# The words that may follow COMMIT / ROLLBACK (WORK, TO SAVEPOINT name, ...).
_UOW_TAIL = "|".join(("WORK", "TO", "SAVEPOINT", "RELEASE", r"[A-Z][A-Z0-9_]{0,30}"))
_SQL_UOW = re.compile(
    r"(?<![A-Z0-9_-])EXEC" + _SP + "SQL" + _SP + r"(COMMIT|ROLLBACK)(?![A-Z0-9_-])"
    r"((?:" + _SP + r"(?:" + _UOW_TAIL + r")){0,4})",
    re.I,
)
_DFHRESP = re.compile(r"DFHRESP[ \t]{0,4}\([ \t]{0,4}([A-Z][A-Z0-9]{0,15})[ \t]{0,4}\)", re.I)
# A paragraph or section header: a name starting in Area A (cols 8-11), alone
# on its line, ended by a period.
_COBOL_NAME = r"[A-Z0-9][A-Z0-9-]{0,62}"
_HEADER = re.compile(r"^ {7,10}" + _COBOL_NAME + r"(?:[ \t]{1,20}SECTION)?[ \t]{0,20}\.[ \t]*$", re.I | re.M)
_RESP_WINDOW = 8000
# EIBRESP values a program may test by number instead of DFHRESP(name) (CardDemo
# COSGN00C: `EVALUATE WS-RESP-CD WHEN 0 ... WHEN 13`). A number not listed here is
# kept as the number itself.
_RESP_CODES = {
    0: "NORMAL",
    1: "ERROR",
    4: "EOF",
    12: "FILENOTFOUND",
    13: "NOTFND",
    14: "DUPREC",
    15: "DUPKEY",
    16: "INVREQ",
    17: "IOERR",
    18: "NOSPACE",
    19: "NOTOPEN",
    20: "ENDFILE",
    21: "ILLOGIC",
    22: "LENGERR",
    23: "QZERO",
    26: "ITEMERR",
    27: "PGMIDERR",
    28: "TRANSIDERR",
    36: "MAPFAIL",
    44: "QIDERR",
    70: "NOTAUTH",
}
_NUMBER = r"([0-9]{1,4})(?![0-9.])"
# One EVALUATE-structure word: an EVALUATE opens a level, END-EVALUATE closes one,
# and a WHEN arm carries a number when it is `WHEN n`.
_EVALUATE_WORD = re.compile(
    r"(?<![A-Z0-9-])(END-EVALUATE|EVALUATE|WHEN)(?![A-Z0-9-])(?:[ \t\n]{1,200}" + _NUMBER + r")?", re.I
)


def _numeric_checks(window: str, var: str) -> list[str]:
    """The response codes `var` is compared with BY NUMBER in `window`: `var [NOT] =
    n` / `var [NOT] EQUAL [TO] n`, and the WHEN n arms of an `EVALUATE var` itself
    (a nested EVALUATE's arms skipped). Each as its DFHRESP name when known."""
    name = re.escape(var)
    found: list[int] = []
    compare = re.compile(
        rf"(?<![A-Z0-9-]){name}(?![A-Z0-9-])[ \t\n]{{0,200}}(?:NOT[ \t\n]{{1,200}})?"
        rf"(?:=|EQUAL(?:[ \t\n]{{1,200}}TO)?)[ \t\n]{{0,200}}" + _NUMBER,
        re.I,
    )
    found += [int(m.group(1)) for m in compare.finditer(window)]
    for ev in re.finditer(rf"(?<![A-Z0-9-])EVALUATE[ \t\n]{{1,200}}{name}(?![A-Z0-9-])", window, re.I):
        # Only the arms of THIS EVALUATE: a nested EVALUATE's WHENs test something else.
        depth = 1
        for w in _EVALUATE_WORD.finditer(window, ev.end()):
            word = w.group(1).upper()
            if word == "EVALUATE":
                depth += 1
            elif word == "END-EVALUATE":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1 and w.group(2):
                found.append(int(w.group(2)))
    # #3495: the assembler forms. `OC v,v` ORs the field with itself only to set the
    # condition code from it -- a test for zero, NORMAL (walmartlabs/zECS
    # `OC EIBRESP,EIBRESP  Normal response?`); `CLC v,=F'n'` / `=AL4(n)` compares by number.
    sym = r"(?<![A-Z0-9@#$_-])"
    if re.search(rf"{sym}OC[ \t]+{name},{name}(?![A-Z0-9@#$_-])", window, re.I):
        found.append(0)
    found += [int(m.group(1)) for m in re.finditer(rf"{sym}CLC[ \t]+{name},=(?:F'|AL4\()([0-9]{{1,4}})", window, re.I)]
    return [_RESP_CODES.get(n, str(n)) for n in found]


_UOW_VERBS = {"SYNCPOINT", "HANDLE", "IGNORE", "PUSH", "POP", "ABEND"}


def _word_boundary_find(text: str, word: str) -> int:
    """Offset of `word` as a whole COBOL word in `text`, or -1."""
    m = re.search(rf"(?<![A-Z0-9-]){re.escape(word)}(?![A-Z0-9-])", text, re.I)
    return m.start() if m else -1


def extract_uow_handlers(
    code_stream: str,
    values: Optional[dict[str, str]] = None,
    shielded: Optional[Callable[[int], bool]] = None,
) -> list[dict[str, Any]]:
    """Every unit-of-work point, handler, explicit ABEND and RESP check in one
    COBOL file, as source-ordered rows (see the module header)."""
    if not code_stream:
        return []
    upper = code_stream.upper()
    if "CICS" not in upper and "COMMIT" not in upper and "ROLLBACK" not in upper:
        return []
    values = values or {}
    text = _blank_sequence_fields(code_stream, "cobol")
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(offset: int) -> int:
        return bisect.bisect_left(newlines, offset) + 1

    def row(kind: str, source: str, verb: str, offset: int, **extra: Any) -> dict[str, Any]:
        out = {
            "kind": kind,
            "source": source,
            "verb": verb,
            "condition": None,
            "target": None,
            "target_kind": None,
            "resp_var": None,
            "attributes": None,
            "line": line_of(offset),
        }
        out.update(extra)
        return out

    def resolved(operand: Optional[str]) -> Optional[str]:
        if not operand:
            return None
        op = operand.strip()
        if len(op) >= 2 and op[0] in "'\"" and op[-1] == op[0]:
            return op[1:-1].strip() or None
        return values.get(op.upper(), op.upper())

    headers = [m.start() for m in _HEADER.finditer(text)]
    rows: list[tuple[int, dict[str, Any]]] = []
    blocks: list[tuple[int, int, list[tuple[str, Optional[str]]]]] = []
    matches = [m for m in _EXEC_CICS.finditer(text) if shielded is None or not shielded(m.start())]
    for index, match in enumerate(matches):
        stop_at = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : min(stop_at, match.end() + _BLOCK_LIMIT)]
        end_exec = _END_EXEC.search(block)
        body = block[: end_exec.start()] if end_exec else block
        ordered = _options(body)
        if not ordered or ordered[0][1] is not None:
            continue
        blocks.append((match.start(), match.end() + (end_exec.end() if end_exec else len(block)), ordered))

    for pos, _end, ordered in blocks:
        verb = ordered[0][0]
        rest = ordered[1:]
        if verb == "SYNCPOINT":
            rolls = any(k == "ROLLBACK" for k, _ in rest)
            rows.append(
                (
                    pos,
                    row("ROLLBACK" if rolls else "COMMIT", "CICS", "SYNCPOINT ROLLBACK" if rolls else "SYNCPOINT", pos),
                )
            )
        elif verb == "ABEND":
            opts = dict(rest)
            flags = [k for k, v in rest if v is None and k in ("NODUMP", "CANCEL")]
            rows.append(
                (
                    pos,
                    row(
                        "ABEND",
                        "CICS",
                        "ABEND",
                        pos,
                        condition=resolved(opts.get("ABCODE")),
                        attributes=" ".join(flags) or None,
                    ),
                )
            )
        elif verb == "HANDLE" and rest and rest[0][0] == "ABEND":
            opts = dict(rest[1:])
            label, program = opts.get("LABEL"), opts.get("PROGRAM")
            target: Optional[str]
            if label:
                target, tkind = label.upper(), "LABEL"
            elif program:
                target, tkind = resolved(program), "PROGRAM"
            elif "RESET" in opts:
                target, tkind = None, "RESET"
            else:
                target, tkind = None, "CANCEL"
            rows.append((pos, row("HANDLE_ABEND", "CICS", "HANDLE ABEND", pos, target=target, target_kind=tkind)))
        elif verb in ("HANDLE", "IGNORE") and rest and rest[0][0] in ("CONDITION", "AID"):
            kind = f"{verb}_{rest[0][0]}"
            for cond, label in rest[1:]:
                if cond in ("RESP", "RESP2", "NOHANDLE"):
                    continue
                if verb == "IGNORE":
                    rows.append((pos, row(kind, "CICS", "IGNORE CONDITION", pos, condition=cond)))
                else:
                    rows.append(
                        (
                            pos,
                            row(
                                kind,
                                "CICS",
                                f"HANDLE {rest[0][0]}",
                                pos,
                                condition=cond,
                                target=label.upper() if label else None,
                                target_kind="LABEL" if label else "DEFAULT",
                            ),
                        )
                    )
        elif verb in ("PUSH", "POP") and rest and rest[0][0] == "HANDLE":
            rows.append((pos, row(f"{verb}_HANDLE", "CICS", f"{verb} HANDLE", pos)))

    # RESP checks: every command that leaves its outcome in a RESP field.
    for index, (pos, end, ordered) in enumerate(blocks):
        opts = dict(ordered[1:])
        if ordered[0][0] in _UOW_VERBS and ordered[0][0] != "SYNCPOINT":
            continue
        var = (opts.get("RESP") or "").upper() or ("EIBRESP" if "NOHANDLE" in opts else "")
        if not var:
            continue
        limit = min(len(text), end + _RESP_WINDOW)
        nxt = bisect.bisect_right(headers, end)
        if nxt < len(headers):
            limit = min(limit, headers[nxt])
        for later_pos, _later_end, later in blocks[index + 1 :]:
            if later_pos >= limit:
                break
            later_opts = dict(later[1:])
            if (later_opts.get("RESP") or "").upper() == var or (var == "EIBRESP" and "NOHANDLE" in later_opts):
                limit = later_pos
                break
        window = text[end:limit]
        first = _word_boundary_find(window, var)
        checked: list[str] = []
        if first != -1:
            for m in _DFHRESP.finditer(window, first):
                if shielded is not None and shielded(end + m.start()):
                    continue
                name = m.group(1).upper()
                if name not in checked:
                    checked.append(name)
            # The numeric forms name the field themselves (EVALUATE v / v = n), so they
            # read the whole window, not only the text after its first mention.
            for name in _numeric_checks(window, var):
                if name not in checked:
                    checked.append(name)
        rows.append(
            (
                pos,
                row(
                    "RESP_CHECK",
                    "CICS",
                    ordered[0][0],
                    pos,
                    condition=",".join(sorted(checked)) or None,
                    resp_var=var,
                ),
            )
        )

    for m in _SQL_UOW.finditer(text):
        if shielded is not None and shielded(m.start()):
            continue
        tail = " ".join(m.group(2).upper().split())
        tail = " ".join(w for w in tail.split() if w in ("WORK", "TO", "SAVEPOINT", "RELEASE"))
        verb = f"{m.group(1).upper()} {tail}".strip()
        rows.append(
            (m.start(), row("COMMIT" if m.group(1).upper() == "COMMIT" else "ROLLBACK", "SQL", verb, m.start()))
        )

    rows.sort(key=lambda r: (r[0], r[1]["kind"] == "RESP_CHECK"))
    return [r for _, r in rows]
