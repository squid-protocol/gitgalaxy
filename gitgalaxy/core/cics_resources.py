# ==============================================================================
# GitGalaxy Core: CICS resource operations (#3351, #3352, #3353, #3354, #3512)
#
# PURPOSE:
# The counted rules say THAT a program issues CICS commands (`io`/`ipc`
# signals). This channel says WHAT each one touches. Every command below names a
# CICS resource in an operand, and each becomes one row:
#
#   kind       commands                                         name operand
#   FILE       READ WRITE REWRITE DELETE UNLOCK STARTBR          FILE / DATASET
#              READNEXT READPREV ENDBR RESETBR           (#3351)
#   MAP        SEND MAP, RECEIVE MAP                     (#3352)  MAP (+ MAPSET)
#   QUEUE      WRITEQ / READQ / DELETEQ  TS|TD           (#3353)  QUEUE / QNAME
#   CONTAINER  PUT / GET / MOVE / DELETE CONTAINER       (#3354)  CONTAINER (+ CHANNEL)
#   CHANNEL    LINK / XCTL / START / RETURN / RUN ... CHANNEL(...)  CHANNEL
#              -- the channel a program hands to another program or transaction
#   WEB        WEB OPEN / CONVERSE / SEND / RECEIVE / CLOSE,  URIMAP, else HOST
#              WEB READ / WRITE HTTPHEADER           (#3512)  (OPEN) or PATH;
#                                                             READ / WRITE: HTTPHEADER
#   SERVICE    INVOKE SERVICE / WEBSERVICE           (#3512)  SERVICE / WEBSERVICE (+ CHANNEL)
#   TRANSFORM  TRANSFORM DATATOXML / XMLTODATA /     (#3512)  XMLTRANSFORM / JSONTRANSFRM
#              DATATOJSON / JSONTODATA                        (+ CHANNEL)
#
# The WEB / SERVICE / TRANSFORM verbs are the command's first two words (`WEB
# SEND`, `INVOKE SERVICE`). A WEB row's qualifier is its side of the HTTP
# exchange: CLIENT for OPEN / CONVERSE / CLOSE and any command coding SESSTOKEN
# (an outbound session), else SERVER -- a SERVER SEND / RECEIVE is a hand-written
# HTTP provider (zECS). WEB EXTRACT / PARSE / browse commands inspect a request
# already received and name nothing, so they draw no row.
#
# ONE TABLE, NOT FOUR. The four kinds share one shape: a verb, an access
# direction, one named resource (a literal or a data-name read through its
# VALUE), at most one qualifying resource (a map's mapset, a queue's TS/TD, a
# container's channel, a channel's receiving program/transaction), and at most
# one record (INTO/FROM/SET). A consumer asks the same question of all of them
# -- "which programs touch resource R, and in which direction" -- so they sit in
# one `cics_resource_data` table keyed by `resource_kind`.
#
# NAME RESOLUTION. A name operand is a literal (`FILE('CUSTOMER')`) or a
# data-name. A data-name is resolved the way a CICS LINK target is (#3200):
# through its working-storage `VALUE` literal, same file only. When it has none,
# a `MOVE 'LIT' TO name` in the same file is the next reading -- CBSA sets every
# channel and container name that way -- and it is taken only when exactly one
# distinct literal is ever moved there. #3578: a `MOVE other-name TO name` counts
# too, bounded at _CHAIN_DEPTH hops: `name` can then hold whatever `other-name`
# holds (its VALUE, else its own MOVEd literals, recursively), so CardDemo's
# `MOVE LIT-THISMAP TO CCARD-NEXT-MAP` + `SEND MAP(CCARD-NEXT-MAP)` resolves. A
# source with no fixed value adds nothing, as a non-literal source always has. Several distinct literals are kept as
# `candidates` with `resolution = 'ambiguous'`; a subscripted or computed
# operand is `expression`; a name with neither is `unresolved`. None of these is
# a guess: `resource_name` is set only for `literal`, `value` and `move`.
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. Joining a MAP to its BMS map, a queue's
#     producers to its consumers, and a FILE to its CSD DSNAME is the reader's
#     job (galaxy_ir), like every other cross-file assembly.
#   - Reads the PRISM code stream, so a commented-out command draws nothing, and
#     an `EXEC CICS` inside a DISPLAY literal is skipped.
#   - Every scan is bounded: the command block is cut at END-EXEC (COBOL) or `;`
#     (PL/I), at the next `EXEC CICS`, and hard-capped at `_BLOCK_LIMIT`;
#     operands are read by one linear, quote-aware parenthesis walk, never a
#     spanning regex.
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

# The command opener. `EXEC CICS` then the command's first word; the rest of the
# block is read by the operand walker.
_EXEC_CICS = re.compile(r"(?<![A-Z0-9-])EXEC[ \t\n]+CICS(?![A-Z0-9-])", re.I)
# The longest real CICS command block in the pinned corpora is ~12 lines; 2000
# chars is an order of magnitude of headroom and can never run to end of file.
_BLOCK_LIMIT = 2000
_END_EXEC = re.compile(r"(?<![A-Z0-9-])END-EXEC(?![A-Z0-9-])", re.I)
# One option keyword. `-` is a COBOL name character; `_` covers PL/I.
_WORD = re.compile(r"[A-Z][A-Z0-9_-]*", re.I)
# A bare data-name operand (no subscript, no `LENGTH OF`, no reference modifier).
_DATA_NAME = re.compile(r"[A-Z][A-Z0-9_-]*", re.I)
# `MOVE 'LIT' TO name` -- the runtime-set name idiom (CBSA's channels/containers).
# Both literal branches exclude their own quote, so neither can run away; the
# receiver is the first data-name after TO.
_MOVE_LITERAL = re.compile(
    r"(?<![A-Z0-9-])MOVE[ \t\n]+(?:'([^'\n]*)'|\"([^\"\n]*)\")[ \t\n]+TO[ \t\n]+([A-Z][A-Z0-9-]*)",
    re.I,
)

# #3578: `MOVE a TO b` between two plain data-names (no subscript, qualifier or
# reference modification: the receiver may not be followed by `(`).
_MOVE_NAME = re.compile(
    r"(?<![A-Z0-9-])MOVE[ \t\n]+([A-Z][A-Z0-9-]*)[ \t\n]+TO[ \t\n]+([A-Z][A-Z0-9-]*)(?![A-Z0-9-]|[ \t]*\()",
    re.I,
)
# Figurative constants are values, not data-names: never followed as a source.
_FIGURATIVE = re.compile(
    r"(?:SPACES?|ZEROS?|ZEROES|LOW-VALUES?|HIGH-VALUES?|QUOTES?|NULLS?|ALL|FUNCTION|LENGTH|ADDRESS)", re.I
)
_CHAIN_DEPTH = 3

# Verb -> access direction, per kind. `write` produces, `read` consumes.
_FILE_VERBS = {
    "READ": "read",
    "READNEXT": "read",
    "READPREV": "read",
    "STARTBR": "browse",
    "RESETBR": "browse",
    "ENDBR": "browse",
    "WRITE": "write",
    "REWRITE": "update",
    "DELETE": "delete",
    "UNLOCK": "unlock",
}
_QUEUE_VERBS = {"WRITEQ": "write", "READQ": "read", "DELETEQ": "delete"}
_CONTAINER_VERBS = {"PUT": "write", "GET": "read", "MOVE": "move", "DELETE": "delete"}
_MAP_VERBS = {"SEND": "write", "RECEIVE": "read"}
# The transfer verbs that can hand a channel on, and the operand naming who
# receives it.
_CHANNEL_VERBS = {"LINK": "PROGRAM", "XCTL": "PROGRAM", "START": "TRANSID", "RETURN": "TRANSID", "RUN": "TRANSID"}
# #3512: WEB subcommand -> access; the name options, in precedence order.
_WEB_VERBS = {"OPEN": "open", "CONVERSE": "converse", "SEND": "write", "RECEIVE": "read", "CLOSE": "close",
              "READ": "read", "WRITE": "write"}  # fmt: skip
_WEB_CLIENT_ONLY = frozenset({"OPEN", "CONVERSE", "CLOSE"})
_WEB_NAMES = {"OPEN": ("URIMAP", "HOST"), "CONVERSE": ("URIMAP", "PATH"), "SEND": ("URIMAP", "PATH"),
              "READ": ("HTTPHEADER",), "WRITE": ("HTTPHEADER",)}  # fmt: skip
_SERVICE_VERBS = ("SERVICE", "WEBSERVICE")
_TRANSFORM_VERBS = {"DATATOXML": "encode", "DATATOJSON": "encode", "XMLTODATA": "decode", "JSONTODATA": "decode"}
_TRANSFORM_NAMES = ("XMLTRANSFORM", "JSONTRANSFRM")
# The record operand, in precedence order.
_RECORD_CLAUSES = ("INTO", "FROM", "SET")
# Options that are error plumbing, not resource facts.
_NOISE = frozenset({"RESP", "RESP2", "NOHANDLE"})
# Bare (value-less) options worth keeping in `attributes`. A whitelist, because a
# stray word in a command block (a sequence-area token) must not become a fact.
_FLAGS = frozenset(
    {
        "UPDATE",
        "GENERIC",
        "EQUAL",
        "GTEQ",
        "MASSINSERT",
        "NOSUSPEND",
        "REWRITE",
        "MAIN",
        "AUXILIARY",
        "NEXT",
        "ERASE",
        "ERASEAUP",
        "MAPONLY",
        "DATAONLY",
        "CURSOR",
        "FREEKB",
        "ALARM",
        "FRSET",
        "ACCUM",
        "PAGING",
        "TERMINAL",
        "WAIT",
        "LAST",
        "PRINT",
        "ASIS",
        "BUFFER",
        "NODATA",
        "SYNCONRETURN",
        "BIT",
        "CHAR",
        "RBA",
        "RRN",
        "XRBA",
        "TOKEN",
    }
)


def _balanced(block: str, open_at: int) -> int:
    """Index of the `)` closing the `(` at `open_at`, quote-aware; len(block) if none."""
    depth, quote = 0, None
    for i in range(open_at, len(block)):
        ch = block[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return len(block)


def _options(block: str) -> list[tuple[str, Optional[str]]]:
    """The command's options in order: (KEYWORD, value inside its parens or None).

    One left-to-right pass: a keyword, optional blanks, then an optional
    parenthesised value read to its balancing `)` (`FROM (X)`, `LENGTH(LENGTH OF
    X)`, `PROGRAM(TAB(WS-I))`). Text inside a value is never re-read as options.
    """
    out: list[tuple[str, Optional[str]]] = []
    i, n = 0, len(block)
    while i < n:
        m = _WORD.search(block, i)
        if not m:
            break
        j = m.end()
        while j < n and block[j] in " \t\n":
            j += 1
        if j < n and block[j] == "(":
            close = _balanced(block, j)
            out.append((m.group(0).upper(), " ".join(block[j + 1 : close].split())))
            i = close + 1
        else:
            out.append((m.group(0).upper(), None))
            i = m.end()
    return out


def cobol_move_literals(code_stream: str, values: Optional[dict[str, str]] = None) -> dict[str, set[str]]:
    """Data-name -> every distinct literal it can be MOVEd (same file): `MOVE 'LIT' TO
    name`, and (#3578, given the file's VALUE map) `MOVE other TO name` followed up to
    _CHAIN_DEPTH hops through `other`'s VALUE or its own moves. Cycles stop."""
    literal: dict[str, set[str]] = {}
    for m in _MOVE_LITERAL.finditer(code_stream):
        text = (m.group(1) if m.group(1) is not None else m.group(2) or "").strip()
        if text:
            literal.setdefault(m.group(3).upper(), set()).add(text)
    if values is None:
        return literal
    sources: dict[str, set[str]] = {}
    for m in _MOVE_NAME.finditer(code_stream):
        src, dst = m.group(1).upper(), m.group(2).upper()
        if src != dst and not _FIGURATIVE.fullmatch(src):
            sources.setdefault(dst, set()).add(src)

    def holds(name: str, depth: int, seen: frozenset) -> set[str]:
        out = set(literal.get(name, ()))
        if depth >= _CHAIN_DEPTH:
            return out
        for src in sources.get(name, ()):
            if src in seen:
                continue
            if src in values:
                out.add(values[src])
            else:
                out |= holds(src, depth + 1, seen | {src})
        return out

    moves = {name: holds(name, 0, frozenset({name})) for name in set(literal) | set(sources)}
    return {name: lits for name, lits in moves.items() if lits}


def _resolver(
    values: dict[str, str], moves: dict[str, set[str]]
) -> Callable[[Optional[str]], tuple[Optional[str], Optional[str], Optional[str]]]:
    """A (operand) -> (name, resolution, candidates) reader over one file's VALUE/MOVE maps."""

    def resolve(operand: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if operand is None:
            return None, None, None
        text = operand.strip()
        if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
            name = text[1:-1].strip()
            return (name or None), "literal", None
        if not _DATA_NAME.fullmatch(text):
            return None, "expression", None
        key = text.upper()
        if key in values:
            return values[key], "value", None
        found = moves.get(key)
        if found and len(found) == 1:
            return next(iter(found)), "move", None
        if found:
            return None, "ambiguous", ",".join(sorted(found))
        return None, "unresolved", None

    return resolve


def _row(
    verb: str,
    kind: str,
    access: str,
    opts: dict[str, Optional[str]],
    name_key: Optional[str],
    qualifier_key: Optional[str],
    resolve: Callable,
    consumed: set[str],
    ordered: list[tuple[str, Optional[str]]],
    line: int,
    qualifier_fixed: Optional[str] = None,
) -> dict[str, Any]:
    operand = opts.get(name_key) if name_key else None
    name, resolution, candidates = resolve(operand)
    q_operand = opts.get(qualifier_key) if qualifier_key else None
    qualifier = qualifier_fixed if qualifier_fixed is not None else resolve(q_operand)[0]
    clause = next((c for c in _RECORD_CLAUSES if opts.get(c)), None)
    record = opts.get(clause).upper() if clause else None  # type: ignore[union-attr]
    used = consumed | {name_key, qualifier_key, clause}
    attrs = []
    for key, value in ordered:
        if key in used or key in _NOISE:
            continue
        if value is not None:
            attrs.append(f"{key}({value})")
        elif key in _FLAGS:
            attrs.append(key)
    return {
        "verb": verb,
        "kind": kind,
        "access": access,
        "operand": operand,
        "name": name,
        "resolution": resolution,
        "candidates": candidates,
        "qualifier_operand": q_operand,
        "qualifier": qualifier,
        "record_clause": clause,
        "record": record,
        "attributes": " ".join(attrs) or None,
        "line": line,
    }


def _two_word_spec(
    first: str, second: str, present: set[str]
) -> tuple[str, Optional[tuple[str, str, Optional[str], Optional[str], set[str], Optional[str]]]]:
    """#3512: the (verb, spec) of a WEB / INVOKE / TRANSFORM command, spec None for any other."""
    verb = f"{first} {second}"
    if first == "WEB" and second in _WEB_VERBS:
        if second in ("READ", "WRITE") and "HTTPHEADER" not in present:
            return verb, None  # READ FORMFIELD / QUERYPARM: request data, not a header
        side = "CLIENT" if second in _WEB_CLIENT_ONLY or "SESSTOKEN" in present else "SERVER"
        name_key = next((k for k in _WEB_NAMES.get(second, ()) if k in present), None)
        return verb, ("WEB", _WEB_VERBS[second], name_key, None, {second}, side)
    if first == "INVOKE" and second in _SERVICE_VERBS:
        return verb, ("SERVICE", "invoke", second, "CHANNEL", set(), None)
    if first == "TRANSFORM" and second in _TRANSFORM_VERBS:
        name_key = next((k for k in _TRANSFORM_NAMES if k in present), None)
        return verb, ("TRANSFORM", _TRANSFORM_VERBS[second], name_key, "CHANNEL", {second}, None)
    return verb, None


def extract_cics_resources(
    code_stream: str,
    values: Optional[dict[str, str]] = None,
    moves: Optional[dict[str, set[str]]] = None,
    dialect: str = "cobol",
    shielded: Optional[Callable[[int], bool]] = None,
) -> list[dict[str, Any]]:
    """Every CICS command in one file that names a FILE, MAP, QUEUE, CONTAINER or
    passed CHANNEL, or does web / service / transform I/O (#3512), as flat
    source-ordered rows (see the module header).

    `values` is the file's data-name -> VALUE literal map and `moves` its
    data-name -> MOVEd literals; `shielded(offset)` says an offset sits inside a
    literal. `dialect` picks the command terminator: END-EXEC, or `;` for PL/I.
    """
    if not code_stream or "CICS" not in code_stream.upper():
        return []
    resolve = _resolver(values or {}, moves or {})
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]
    rows: list[dict[str, Any]] = []
    matches = list(_EXEC_CICS.finditer(code_stream))
    for index, match in enumerate(matches):
        if shielded is not None and shielded(match.start()):
            continue
        # A command never contains the next `EXEC CICS`, so the block also stops
        # there: back-to-back unterminated openers then cost O(file), not
        # O(openers x _BLOCK_LIMIT).
        stop_at = matches[index + 1].start() if index + 1 < len(matches) else len(code_stream)
        block = code_stream[match.end() : min(stop_at, match.end() + _BLOCK_LIMIT)]
        if dialect == "pli":
            stop = block.find(";")
            block = block[:stop] if stop != -1 else block
        else:
            end = _END_EXEC.search(block)
            block = block[: end.start()] if end else block
        ordered = _options(block)
        if not ordered:
            continue
        verb = ordered[0][0]
        opts: dict[str, Optional[str]] = {}
        for key, value in ordered[1:]:
            opts.setdefault(key, value)
        if ordered[0][1] is not None:
            # `EXEC CICS READ(...)` is not a command shape; nothing to read.
            continue
        present = set(opts)
        # (kind, access, name option, qualifier option, options consumed, fixed qualifier)
        spec: Optional[tuple[str, str, Optional[str], Optional[str], set[str], Optional[str]]] = None
        if verb in _CONTAINER_VERBS and "CONTAINER" in present:
            spec = ("CONTAINER", _CONTAINER_VERBS[verb], "CONTAINER", "CHANNEL", set(), None)
        elif verb in _FILE_VERBS and ({"FILE", "DATASET"} & present):
            spec = ("FILE", _FILE_VERBS[verb], "FILE" if "FILE" in present else "DATASET", None, set(), None)
        elif verb in _MAP_VERBS and "MAP" in present:
            spec = ("MAP", _MAP_VERBS[verb], "MAP", "MAPSET", set(), None)
        elif verb in _QUEUE_VERBS and ({"QUEUE", "QNAME"} & present):
            # TS is optional on WRITEQ/READQ/DELETEQ TS; TD is always written.
            qtype = "TD" if "TD" in present else "TS"
            spec = ("QUEUE", _QUEUE_VERBS[verb], "QUEUE" if "QUEUE" in present else "QNAME", None, {"TS", "TD"}, qtype)
        elif verb in _CHANNEL_VERBS and "CHANNEL" in present:
            spec = ("CHANNEL", "pass", "CHANNEL", _CHANNEL_VERBS[verb], set(), None)
        elif len(ordered) > 1:
            verb, spec = _two_word_spec(verb, ordered[1][0], present)
        if spec is None:
            continue
        kind, access, name_key, qualifier_key, consumed, fixed = spec
        rows.append(
            _row(
                verb,
                kind,
                access,
                opts,
                name_key,
                qualifier_key,
                resolve=resolve,
                consumed=consumed,
                ordered=ordered[1:],
                line=bisect.bisect_left(newlines, match.start()) + 1,
                qualifier_fixed=fixed,
            )
        )
    return rows
