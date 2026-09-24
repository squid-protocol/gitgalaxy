# ==============================================================================
# GitGalaxy Core: IBM MQ calls -- which program puts to / gets from which queue (#3447)
#
# PURPOSE:
# `CALL 'MQOPEN'` / `'MQPUT'` / `'MQGET'` reach call_site_data as external
# calls and nothing more, so the asynchronous message flow between programs --
# who produces onto a queue and who consumes from it -- is missing. This channel
# records every MQI call of a COBOL program, one row each:
#
#   verb        MQOPEN | MQPUT | MQPUT1 | MQGET | MQCLOSE | MQINQ | MQSET |
#               MQCONN | MQCONNX | MQDISC | MQSUB | MQCB ...
#   direction   get | browse | put | inquire | set (from the MQOO-* open
#               options; MQPUT/MQPUT1 put, MQGET get); None when unknown
#   queue       the queue the call touches, and `resolution` how it was read
#   handle      the object handle an MQPUT / MQGET / MQCLOSE passes, and
#               `open_line`, the MQOPEN it was matched to
#   options     the MQOO-/MQPMO-/MQGMO- option names in effect
#
# HOW A QUEUE IS READ. MQ names its object through a descriptor, never a call
# operand: `MOVE <q> TO MQOD-OBJECTNAME [OF <od>]`, then `CALL 'MQOPEN' USING
# hconn <od> options hobj ...` (or MQPUT1, which opens, puts and closes by
# descriptor). The queue of an MQOPEN / MQPUT1 is the operand last MOVEd to that
# descriptor's OBJECTNAME before the call, in source order. That operand is then
# read the way a CICS resource name is -- a literal, the data-name's VALUE, the
# literals MOVEd to it -- following data-name to data-name MOVEs (depth 3), and
# two runtime sources are named rather than guessed:
#   - `trigger`:  MOVEd from MQTM-QNAME -- the queue whose trigger started this
#                 transaction (the trigger definition is MQ/CICS configuration,
#                 outside the repository);
#   - `reply_to`: MOVEd from MQMD-REPLYTOQ -- the requester's reply-to queue.
# An MQPUT / MQGET / MQCLOSE names a HANDLE, not a queue. The handle an MQOPEN
# returns (its 4th operand) is followed through the MOVEs that copy it before
# the next MQ call (`MOVE MQ-HOBJ TO INPUT-QUEUE-HANDLE`), and a later call is
# matched by the handle it passes or the one MOVEd into its handle operand just
# before it (`MOVE INPUT-QUEUE-HANDLE TO MQ-HOBJ`). The matched open lends the
# call its queue, resolution and open_line; an unmatched handle is `unresolved`.
#
# SCOPE AND NON-SCOPE:
#   - COBOL only; the engine's worker sees one file, so a queue name set in a
#     copybook or passed in a COMMAREA is `unresolved`, never guessed.
#   - SOURCE ORDER, not control flow: "last MOVE before the call" is textual.
#     CardDemo's MQ programs open each queue in its own paragraph, so the two
#     agree there; a program that reuses one descriptor across branches can be
#     misread, and says so only through `resolution`.
#   - Producer -> queue -> consumer pairing across programs is the reader's
#     join (GalaxyIR.mq_flows), like every other cross-file assembly.
#   - Bounded: one pass of capped regexes over the code stream; a CALL reads at
#     most `_MAX_ARGS` operands. Fixed-format sequence fields are blanked first
#     (db2_declare_table._blank_sequence_fields), so a numbered line's cols 73-80
#     never end an operand list.
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

from gitgalaxy.core.db2_declare_table import _blank_sequence_fields

_NAME = r"[A-Z][A-Z0-9-]{0,62}"
# `MOVE src TO target [OF qualifier]`: src is a literal or a (qualified) data-name.
_MOVE = re.compile(
    rf"(?<![A-Z0-9-])MOVE[ \t\n]{{1,200}}('[^'\n]{{0,160}}'|\"[^\"\n]{{0,160}}\"|{_NAME})"
    rf"(?:[ \t\n]{{1,200}}OF[ \t\n]{{1,200}}{_NAME})?[ \t\n]{{1,200}}TO[ \t\n]{{1,200}}({_NAME})"
    rf"(?:[ \t\n]{{1,200}}OF[ \t\n]{{1,200}}({_NAME}))?",
    re.I,
)
# `COMPUTE X = MQOO-A + MQOO-B ...` -- an options word being built.
_COMPUTE = re.compile(
    rf"(?<![A-Z0-9-])COMPUTE[ \t\n]{{1,200}}({_NAME})[ \t\n]{{0,200}}=[ \t\n]{{0,200}}"
    rf"(MQ[A-Z0-9-]{{1,40}}(?:[ \t\n]{{0,200}}\+[ \t\n]{{0,200}}MQ[A-Z0-9-]{{1,40}}){{0,15}})",
    re.I,
)
_CALL = re.compile(r"(?<![A-Z0-9-])CALL[ \t\n]{1,200}(?:'(MQ[A-Z0-9]{2,8})'|\"(MQ[A-Z0-9]{2,8})\")", re.I)
_ARG = re.compile(rf"[ \t\n,]{{0,200}}(?:BY[ \t\n]{{1,20}}(?:REFERENCE|CONTENT|VALUE)[ \t\n]{{1,20}})?({_NAME})", re.I)
_USING = re.compile(r"[ \t\n]{1,200}USING(?![A-Z0-9-])", re.I)
_MAX_ARGS = 4
_OPTION_WORD = re.compile(r"MQ(?:OO|PMO|GMO)-[A-Z0-9-]{1,40}", re.I)
_FAMILY = {"MQOPEN": "MQOO-", "MQPUT": "MQPMO-", "MQPUT1": "MQPMO-", "MQGET": "MQGMO-"}
_RUNTIME = {"MQTM-QNAME": "trigger", "MQMD-REPLYTOQ": "reply_to"}
_FIGURATIVE = frozenset({"SPACE", "SPACES", "LOW-VALUE", "LOW-VALUES", "HIGH-VALUE", "HIGH-VALUES", "ZERO", "ZEROS"})
_HANDLE_VERBS = frozenset({"MQPUT", "MQGET", "MQCLOSE", "MQINQ", "MQSET"})
_DEPTH = 3


def _direction(verb: str, options: list[str]) -> Optional[str]:
    if verb in ("MQPUT", "MQPUT1"):
        return "put"
    if verb == "MQGET":
        return "get"
    if verb == "MQOPEN":
        words = {o.upper() for o in options}
        if any(w.startswith("MQOO-INPUT") for w in words):
            return "get"
        if "MQOO-BROWSE" in words:
            return "browse"
        if "MQOO-OUTPUT" in words:
            return "put"
        if "MQOO-INQUIRE" in words:
            return "inquire"
        if "MQOO-SET" in words:
            return "set"
    return None


def extract_mq_calls(
    code_stream: str,
    values: Optional[dict[str, str]] = None,
    shielded: Optional[Callable[[int], bool]] = None,
) -> list[dict[str, Any]]:
    """Every MQI call in one COBOL file, as flat source-ordered rows (see the header).

    `values` is the file's data-name -> VALUE literal map; `shielded(offset)`
    says an offset sits inside a literal (a DISPLAY 'CALL MQPUT' is no call).
    """
    if not code_stream or "MQ" not in code_stream.upper():
        return []
    values = values or {}
    # Sequence numbers (cols 1-6, 73-80) sit between a CALL's operands in
    # numbered source (CardDemo COACCT01); blank them, offsets unchanged.
    code_stream = _blank_sequence_fields(code_stream, "cobol")
    events: list[tuple[int, str, tuple]] = []
    sources: dict[str, set[str]] = {}  # data-name -> every MOVE source (literal text or data-name)
    for m in _MOVE.finditer(code_stream):
        if shielded is not None and shielded(m.start()):
            continue
        src, tgt, qual = m.group(1), m.group(2).upper(), (m.group(3) or "").upper() or None
        if src[0] in "'\"":
            text = src[1:-1].strip()
            if text:
                sources.setdefault(tgt, set()).add("'" + text)
        elif src.upper() not in _FIGURATIVE:
            sources.setdefault(tgt, set()).add(src.upper())
        events.append((m.start(), "move", (src, tgt, qual)))
    events.extend(
        (m.start(), "options", (m.group(1).upper(), _OPTION_WORD.findall(m.group(2))))
        for m in _COMPUTE.finditer(code_stream)
        if shielded is None or not shielded(m.start())
    )
    for m in _CALL.finditer(code_stream):
        if shielded is not None and shielded(m.start()):
            continue
        verb = (m.group(1) or m.group(2)).upper()
        args: list[str] = []
        using = _USING.match(code_stream, m.end())
        pos = using.end() if using else m.end()
        while using and len(args) < _MAX_ARGS:
            a = _ARG.match(code_stream, pos)
            if not a or a.group(1).upper() in ("OF", "END-CALL"):
                break
            args.append(a.group(1).upper())
            pos = a.end()
            of = re.match(rf"[ \t\n]{{1,200}}OF[ \t\n]{{1,200}}{_NAME}", code_stream[pos : pos + 500], re.I)
            if of:
                pos += of.end()
        events.append((m.start(), "call", (verb, args)))
    events.sort(key=lambda e: e[0])

    def resolve(operand: str, depth: int = 0) -> set[str]:
        """Every value `operand` can hold: `'LIT` literals and `<trigger>` / `<reply_to>` markers."""
        key = operand.upper()
        if key in _RUNTIME:
            return {f"<{_RUNTIME[key]}>"}
        if key in values:
            return {"'" + values[key]}
        out: set[str] = set()
        for s in sources.get(key, set()):
            if s.startswith("'"):
                out.add(s)
            elif depth < _DEPTH:
                out |= resolve(s, depth + 1)
        return out

    def reading(operand: Optional[str]) -> tuple[Optional[str], str, Optional[str]]:
        """(queue, resolution, candidates) for the operand MOVEd to an OBJECTNAME."""
        if operand is None:
            return None, "unresolved", None
        if operand[0] in "'\"":
            return operand[1:-1].strip() or None, "literal", None
        found = resolve(operand)
        if len(found) == 1:
            only = next(iter(found))
            if only.startswith("'"):
                return only[1:], ("value" if operand.upper() in values else "move"), None
            return None, only.strip("<>"), None
        if found:
            return None, "ambiguous", ",".join(sorted(v.lstrip("'") for v in found))
        return None, "unresolved", None

    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]
    objectname: dict[Optional[str], str] = {}  # descriptor qualifier (None = unqualified) -> operand
    options: dict[str, list[str]] = {}  # options field -> option words, as last assigned
    handle_moves: dict[str, str] = {}  # handle field -> the handle MOVEd into it since the last call
    opens: list[dict[str, Any]] = []
    last_open: Optional[dict[str, Any]] = None
    rows: list[dict[str, Any]] = []
    for _pos, kind, data in events:
        if kind == "move":
            src, tgt, qual = data
            if tgt.endswith("OBJECTNAME"):
                objectname[qual] = src
                objectname[None] = src
            elif _OPTION_WORD.fullmatch(src):
                options[tgt] = [src.upper()]
            elif src[0] not in "'\"":
                handle_moves[tgt] = src.upper()
                if last_open is not None and src.upper() in last_open["aliases"]:
                    last_open["aliases"].add(tgt)
            continue
        if kind == "options":
            options[data[0]] = [w.upper() for w in data[1]]
            continue
        verb, args = data
        family = _FAMILY.get(verb)
        opts = []
        if family:
            opts = next(
                (w for field, w in reversed(list(options.items())) if w and w[0].startswith(family)),
                [],
            )
        row: dict[str, Any] = {
            "verb": verb,
            "direction": _direction(verb, opts),
            "operand": None,
            "queue": None,
            "resolution": None,
            "candidates": None,
            "handle": None,
            "open_line": None,
            "options": " ".join(opts) or None,
            "line": bisect.bisect_left(newlines, _pos) + 1,
        }
        if verb in ("MQOPEN", "MQPUT1") and len(args) >= 2:
            operand = objectname.get(args[1], objectname.get(None))
            row["operand"] = operand.upper() if operand and operand[0] not in "'\"" else operand
            row["queue"], row["resolution"], row["candidates"] = reading(operand)
            if verb == "MQOPEN" and len(args) >= 4:
                row["handle"] = args[3]
                last_open = {"row": row, "aliases": {args[3]}}
                opens.append(last_open)
        elif verb in _HANDLE_VERBS and len(args) >= 2:
            passed = args[1]
            via = handle_moves.get(passed)
            row["handle"] = via or passed
            match = [o for o in opens if via and via in o["aliases"] and via != o["row"]["handle"]]
            match = match or [o for o in opens if (via or passed) in o["aliases"]]
            match = match or [o for o in opens if passed in o["aliases"]]
            if len(match) > 1:
                # A shared handle field (every open returns into MQ-HOBJ): prefer an
                # open whose own copies include the passed name, else the latest.
                named = [o for o in match if (via or passed) in o["aliases"] - {o["row"]["handle"]}]
                match = named or match[-1:]
            if len(match) == 1:
                src_row = match[0]["row"]
                row["operand"], row["queue"] = src_row["operand"], src_row["queue"]
                row["resolution"], row["candidates"] = src_row["resolution"], src_row["candidates"]
                row["open_line"] = src_row["line"]
            else:
                row["resolution"] = "unresolved"
        rows.append(row)
        handle_moves = {}
        if verb != "MQOPEN":
            last_open = None
    return rows
