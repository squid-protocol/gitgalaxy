# ==============================================================================
# GitGalaxy Core: CICS task control -- async children, starts, joins (#3449)
#
# PURPOSE:
# cics_resource_data (#3351-#3354) says which FILE/MAP/QUEUE/CONTAINER a
# program touches, and call_site_data carries `RUN TRANSID` as a routing verb.
# Neither says how TASKS relate: that a parent RUNs a child transaction and
# later FETCHes its result, that a START's FROM data is RETRIEVEd by the
# started transaction, or that a task DELAYs, ENQueues on a resource or waits
# on an event. A fan-out/fan-in (CBSA's credit-agency flow: RUN OCR1..OCR5,
# then FETCH ANY) otherwise reads as one unconnected child start. Every task
# control command becomes one row:
#
#   verb           operands lifted out
#   RUN            TRANSID target, CHANNEL, CHILD token          (async API)
#   FETCH CHILD    CHILD token, CHANNEL (returned), COMPSTATUS/ABCODE in attributes
#   FETCH ANY      ANY token (returned), CHANNEL (returned)
#   FREE CHILD     CHILD token
#   START          TRANSID target, CHANNEL, REQID token, FROM record, timing
#   START ATTACH   TRANSID target, CHANNEL, FROM record
#   RETRIEVE       INTO/SET record (the data a START passed)
#   CANCEL         TRANSID target, REQID token
#   DELAY          timing, REQID token
#   POST           timing, REQID token, SET record
#   WAIT EVENT     ECADDR in attributes
#   WAIT EXTERNAL  / WAITCICS  ECBLIST/NUMEVENTS in attributes
#   ENQ / DEQ      RESOURCE target (the serialised name), LENGTH in attributes
#
# TARGET RESOLUTION. A TRANSID or RESOURCE operand resolves the way a CICS
# resource name does (cics_resources._resolver): a literal, the data-name's
# VALUE, or a single MOVEd literal; several MOVEd literals are `ambiguous`.
# One more reading applies to COBOL (#3449): a transaction id BUILT by `STRING`
# -- CBSA's `STRING 'OCR' DELIMITED BY SIZE, WS-CC-CNT DELIMITED BY SIZE INTO
# WS-RUN-TRANSID` -- becomes a PATTERN. Each STRING source contributes its
# literal text, or for a data-name DELIMITED BY SIZE its PIC width
# (`[0-9]` per digit of an all-9 PIC, `?` per character of X/A), or `*` when the
# width is unknown. `OCR[0-9]` is then `resolution = 'pattern'` with the pattern
# in `candidates`: it is joined to the CSD transaction map by the reader
# (GalaxyIR.async_tasks), never expanded here, and it deliberately does not
# match `OCRA`, a different transaction in the same deck. A pattern with no
# literal character in it says nothing and is not kept.
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. Joining RUN to the child's program (CSD), RUN's
#     CHILD token to its FETCH, and START to the child's RETRIEVE is the
#     reader's job (galaxy_ir), like every other cross-file assembly.
#   - The CHANNEL a RUN/START passes is ALSO a `CHANNEL` row in
#     cics_resource_data (container flows read it there); it is repeated here so
#     one row carries the whole spawn.
#   - Reads the PRISM code stream with the cics_resources block/option walker:
#     bounded at END-EXEC (COBOL) or `;` (PL/I), the next `EXEC CICS` and
#     `_BLOCK_LIMIT`; an `EXEC CICS` inside a literal is skipped. The STRING
#     reader is bounded by `_STRING_LIMIT` and a statement-ending period.
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

from gitgalaxy.core.cics_resources import (
    _BLOCK_LIMIT,
    _END_EXEC,
    _EXEC_CICS,
    _NOISE,
    _options,
    _resolver,
)

# Operands that say WHEN (START / DELAY / POST): kept together, in order, as `timing`.
_TIMING = frozenset({"INTERVAL", "TIME", "AFTER", "AT", "FOR", "UNTIL", "HOURS", "MINUTES", "SECONDS", "MILLISECS"})
# Flags worth keeping in `attributes` (a bare keyword with no operand).
_FLAGS = frozenset({"NOSUSPEND", "NOCHECK", "PROTECT", "TASK", "UOW", "PURGEABLE", "NOTPURGEABLE"})
# The verb word(s) -> (row verb, target option, token option).
_TASK_VERBS: dict[str, tuple[Optional[str], Optional[str]]] = {
    "RUN": ("TRANSID", "CHILD"),
    "START": ("TRANSID", "REQID"),
    "START ATTACH": ("TRANSID", None),
    "FETCH CHILD": (None, "CHILD"),
    "FETCH ANY": (None, "ANY"),
    "FREE CHILD": (None, "CHILD"),
    "RETRIEVE": (None, None),
    "CANCEL": ("TRANSID", "REQID"),
    "DELAY": (None, "REQID"),
    "POST": (None, "REQID"),
    "WAIT EVENT": (None, None),
    "WAIT EXTERNAL": (None, None),
    "WAITCICS": (None, None),
    "ENQ": ("RESOURCE", None),
    "DEQ": ("RESOURCE", None),
}
_RECORD_CLAUSES = ("FROM", "INTO", "SET")

# ---- COBOL STRING ... INTO (transaction-id patterns) -------------------------
_STRING_VERB = re.compile(r"(?<![A-Z0-9-])STRING(?![A-Z0-9-])", re.I)
# A STRING statement in the corpora is < 300 chars; 1500 is headroom that can
# never run to end of file.
_STRING_LIMIT = 1500
# One STRING token: a literal (each branch excludes its own quote), a data-name
# with an optional subscript / reference modifier, a comma, or any other char.
_STRING_TOKEN = re.compile(
    r"'[^'\n]*'|\"[^\"\n]*\"|[A-Z0-9][A-Z0-9-]*(?:[ \t]{0,4}\([^()\n]{0,60}\))?|[.,]|\S",
    re.I,
)
_PIC_REPEAT = re.compile(r"([9XA])(?:\((\d{1,4})\))?", re.I)
_FIGURATIVE = frozenset(
    {"SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES", "LOW-VALUE", "LOW-VALUES", "HIGH-VALUE", "HIGH-VALUES", "QUOTE"}
)


def _pic_pattern(pic: Optional[str]) -> str:
    """The fnmatch pattern a data-name of this PIC contributes DELIMITED BY SIZE:
    `[0-9]` per digit of an all-9 PIC (a leading S occupies nothing), `?` per
    character of an X/A PIC, and `*` for anything else (edited, V, unknown)."""
    if not pic:
        return "*"
    text = pic.upper().replace(" ", "")
    text = text[1:] if text.startswith("S") else text
    kinds: list[str] = []
    width = 0
    pos = 0
    while pos < len(text):
        m = _PIC_REPEAT.match(text, pos)
        if not m:
            return "*"
        kinds.append(m.group(1))
        width += int(m.group(2) or 1)
        pos = m.end()
    if not width or width > 32:
        return "*"
    if set(kinds) == {"9"}:
        return "[0-9]" * width
    return "?" * width


def _escape(text: str) -> str:
    """A literal's text inside an fnmatch pattern (`[`, `]`, `*`, `?` taken literally)."""
    return re.sub(r"([\[\]*?])", r"[\1]", text)


def _string_patterns(code_stream: str, pics: dict[str, str]) -> dict[str, set[str]]:
    """Receiver data-name -> the patterns every `STRING ... INTO name` builds (COBOL)."""
    out: dict[str, set[str]] = {}
    for m in _STRING_VERB.finditer(code_stream):
        region = code_stream[m.end() : m.end() + _STRING_LIMIT]
        toks = _STRING_TOKEN.findall(region)
        pieces: list[str] = []
        i = 0
        receiver = None
        while i < len(toks):
            tok = toks[i]
            up = tok.upper()
            if up == "INTO":
                if i + 1 < len(toks):
                    receiver = toks[i + 1].upper()
                break
            if tok == ".":
                break  # the statement ended without INTO: not a STRING statement
            if tok == ",":
                i += 1
                continue
            # One source and its optional `DELIMITED [BY] x`.
            delim = None
            j = i + 1
            if j < len(toks) and toks[j].upper() == "DELIMITED":
                j += 1
                if j < len(toks) and toks[j].upper() == "BY":
                    j += 1
                if j < len(toks):
                    delim = toks[j]
                    j += 1
            by_size = delim is not None and delim.upper() == "SIZE"
            if tok[:1] in "'\"":
                text = tok[1:-1]
                if delim is not None and not by_size:
                    d = delim[1:-1] if delim[:1] in "'\"" else (" " if delim.upper() in ("SPACE", "SPACES") else None)
                    text = text.split(d, 1)[0] if d else text
                    pieces.append(_escape(text) + ("" if d and d in tok[1:-1] else "*"))
                else:
                    pieces.append(_escape(text))
            elif up in _FIGURATIVE:
                pieces.append("*")
            elif re.fullmatch(r"[A-Z][A-Z0-9-]*", up) and by_size:
                pieces.append(_pic_pattern(pics.get(up)))
            else:
                pieces.append("*")
            i = j
        if not receiver or not re.fullmatch(r"[A-Z][A-Z0-9-]*", receiver) or not pieces:
            continue
        pattern = re.sub(r"\*+", "*", "".join(pieces))
        if not re.search(r"[A-Z0-9]", re.sub(r"\[[^\]]*\]", "", pattern), re.I):
            continue  # all wildcards: says nothing about the name
        out.setdefault(receiver, set()).add(pattern.upper())
    return out


def _is_pattern(text: str) -> bool:
    """True when `text` has a wildcard left once its escaped `[c]` characters are dropped."""
    return bool(re.search(r"[*?\[]", re.sub(r"\[[\[\]*?]\]", "", text)))


def _task_verb(ordered: list[tuple[str, Optional[str]]]) -> Optional[tuple[str, int]]:
    """(row verb, index of the first option after it), or None for a non-task command."""
    if not ordered or ordered[0][1] is not None:
        return None
    first = ordered[0][0]
    second = ordered[1][0] if len(ordered) > 1 else None
    if first == "FETCH" and second in ("CHILD", "ANY"):
        return f"FETCH {second}", 1
    if first == "FREE" and second == "CHILD":
        return "FREE CHILD", 1
    if first == "WAIT" and second in ("EVENT", "EXTERNAL") and ordered[1][1] is None:
        return f"WAIT {second}", 2
    if first == "START" and second == "ATTACH" and ordered[1][1] is None:
        return "START ATTACH", 2
    if first in ("RUN", "START", "RETRIEVE", "CANCEL", "DELAY", "POST", "WAITCICS", "ENQ", "DEQ"):
        return first, 1
    return None


def extract_cics_tasks(
    code_stream: str,
    values: Optional[dict[str, str]] = None,
    moves: Optional[dict[str, set[str]]] = None,
    pics: Optional[dict[str, str]] = None,
    dialect: str = "cobol",
    shielded: Optional[Callable[[int], bool]] = None,
) -> list[dict[str, Any]]:
    """Every CICS task-control command in one file, as flat source-ordered rows
    (see the module header).

    `values` / `moves` are the file's VALUE and MOVEd-literal maps (as for
    cics_resources); `pics` is data-name -> PIC, which sizes a STRING source;
    `shielded(offset)` says an offset sits inside a literal.
    """
    if not code_stream or "CICS" not in code_stream.upper():
        return []
    base = _resolver(values or {}, moves or {})
    patterns = _string_patterns(code_stream, pics or {}) if dialect == "cobol" else {}

    def resolve(operand: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        name, resolution, candidates = base(operand)
        # A STRING assigns the name too, so a sole MOVEd literal is no longer the
        # only value it can hold; a VALUE clause still wins (the first reading).
        built = (
            patterns.get((operand or "").strip().upper()) if resolution in ("move", "unresolved", "ambiguous") else None
        )
        if not built:
            return name, resolution, candidates
        moved = {name} if resolution == "move" and name else set((candidates or "").split(","))
        every = (built | moved) - {""}
        if len(every) == 1 and not _is_pattern(next(iter(every))):
            return next(iter(every)), "string", None
        return None, ("pattern" if any(_is_pattern(c) for c in every) else "ambiguous"), ",".join(sorted(every))

    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]
    rows: list[dict[str, Any]] = []
    matches = list(_EXEC_CICS.finditer(code_stream))
    for index, match in enumerate(matches):
        if shielded is not None and shielded(match.start()):
            continue
        stop_at = matches[index + 1].start() if index + 1 < len(matches) else len(code_stream)
        block = code_stream[match.end() : min(stop_at, match.end() + _BLOCK_LIMIT)]
        if dialect == "pli":
            stop = block.find(";")
            block = block[:stop] if stop != -1 else block
        else:
            end = _END_EXEC.search(block)
            block = block[: end.start()] if end else block
        ordered = _options(block)
        head = _task_verb(ordered)
        if head is None:
            continue
        verb, first = head
        target_key, token_key = _TASK_VERBS[verb]
        rest = ordered[first:]
        opts: dict[str, Optional[str]] = {}
        for key, value in rest:
            opts.setdefault(key, value)
        # `FETCH CHILD(x)` / `FETCH ANY(x)`: the verb's own second word carries the token.
        token = ordered[1][1] if verb in ("FETCH CHILD", "FETCH ANY", "FREE CHILD") else opts.get(token_key or "")
        operand = opts.get(target_key) if target_key else None
        name, resolution, candidates = resolve(operand)
        channel_operand = opts.get("CHANNEL")
        clause = next((c for c in _RECORD_CLAUSES if opts.get(c)), None)
        used = {target_key, token_key, "CHANNEL", clause}
        timing, attrs = [], []
        for key, value in rest:
            if key in _TIMING:
                timing.append(f"{key}({value})" if value is not None else key)
            elif key in used or key in _NOISE:
                continue
            elif value is not None:
                attrs.append(f"{key}({value})")
            elif key in _FLAGS:
                attrs.append(key)
        rows.append(
            {
                "verb": verb,
                "target_kind": target_key,
                "operand": operand,
                "name": name,
                "resolution": resolution,
                "candidates": candidates,
                "channel_operand": channel_operand,
                "channel": base(channel_operand)[0],
                "token": " ".join(token.upper().split()) if token else None,
                "record_clause": clause,
                "record": opts[clause].upper() if clause and opts.get(clause) else None,  # type: ignore[union-attr]
                "timing": " ".join(timing) or None,
                "attributes": " ".join(attrs) or None,
                "line": bisect.bisect_left(newlines, match.start()) + 1,
            }
        )
    return rows
