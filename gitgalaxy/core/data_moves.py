# ==============================================================================
# GitGalaxy Core: field-level data movement -- MOVE / COMPUTE / STRING ... (#3452)
#
# PURPOSE:
# The channels before this one say which records a program exchanges with a
# screen, a COMMAREA, a file, a table or a queue. Nothing said how data moves
# between the ITEMS inside a program, so a screen field could not be followed
# through working storage into the COMMAREA or a DB column. One row per
# source -> target pair of every data-moving statement:
#
#   verb        MOVE | COMPUTE | ADD | SUBTRACT | MULTIPLY | DIVIDE | STRING |
#               UNSTRING | INITIALIZE, and (#3492) the file-I/O verbs READ /
#               RETURN (INTO) | WRITE / REWRITE / RELEASE (FROM) | ACCEPT
#   source      the sending operand as written: a data name with its qualifiers
#               (`A OF B`), a literal, a figurative constant, `FUNCTION NAME`,
#               `LENGTH OF X` / `ADDRESS OF X`; None for INITIALIZE
#   source_kind item | literal | figurative | function | length | address |
#               file (READ / RETURN: the FILE name, whose FD record is the source)
#               | special (ACCEPT: `DATE YYYYMMDD`, `TIME`, `SYSIN` when no FROM)
#   target      the receiving data name with its qualifiers
#   corresponding  MOVE CORRESPONDING (group to group, by matching names)
#   source_refmod / target_refmod  the operand carries a reference modification
#               (`X(1:5)`); a subscript (`X(I)`) is dropped and is not a source
#
# Per verb: MOVE a TO t...; COMPUTE t... = expr (every data name in expr);
# ADD / SUBTRACT a... TO|FROM t... (a -> t), or with GIVING g... (a and the
# TO / FROM operands -> g); MULTIPLY a BY b (a -> b) / GIVING; DIVIDE a INTO|BY
# b (a -> b) / GIVING, REMAINDER r; STRING s... DELIMITED BY d INTO t (the
# delimiters and the POINTER are control, not data); UNSTRING s DELIMITED BY d
# INTO t... (DELIMITER IN / COUNT IN / POINTER / TALLYING are control);
# INITIALIZE t....; READ / RETURN f INTO t (f's record -> t); WRITE / REWRITE /
# RELEASE r FROM s (s -> r); ACCEPT t [FROM x] (x -> t).
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file, operands as written. Resolving a name to its
#     storage (record, offset, width) -- which is what makes group moves,
#     REDEFINES overlays and qualification meaningful -- and following the flow
#     across programs and to the channel endpoints is the reader's
#     (GalaxyIR.data_flows / field_lineage).
#   - Procedure code only: from PROCEDURE DIVISION, or the whole member for a
#     copybook of procedure statements. EXEC ... END-EXEC blocks are skipped
#     (their host variables and INTO / FROM areas are the SQL / CICS / DL/I
#     channels' endpoints, #3452). SET is not a row; a READ without INTO or a
#     WRITE without FROM moves no program data (the FD record is the buffer).
#   - Sequence fields, comment and debugging lines are blanked first. Bounded per
#     statement. Pseudo-text awaiting COPY REPLACING (`(TAG)-NAME`) is not an
#     operand, and names a COPY ... REPLACING would produce are not resolved by
#     the reader (record_data keeps the copybook's own names).
# ==============================================================================
import bisect
import re
from typing import Any, Optional

from gitgalaxy.core.db2_declare_table import _blank_sequence_fields

_LITERAL = r"[XNGZ]?'[^'\n]{0,320}'?|[XNGZ]?\"[^\"\n]{0,320}\"?"
_NUMBER = r"[+-]?[0-9]*\.[0-9]+|[+-]?[0-9]+"
_WORD = r"[A-Z0-9][A-Z0-9-]{0,62}"
_NUMBER_TOKEN = rf"(?:{_NUMBER})(?![A-Z0-9-])"  # a number, not the head of a name (1ST-X)
_OPERATOR = r"\*\*|[()=:+*/,.<>-]"
_TOKEN = re.compile("|".join((_LITERAL, _NUMBER_TOKEN, _WORD, _OPERATOR)), re.I)
_STATEMENT_TOKENS = 600
_VERBS = frozenset(
    {
        "ACCEPT", "ADD", "ALTER", "CALL", "CANCEL", "CLOSE", "COMPUTE", "CONTINUE", "DELETE", "DISPLAY",
        "DIVIDE", "ELSE", "END-ADD", "END-COMPUTE", "END-DIVIDE", "END-EVALUATE", "END-IF", "END-MULTIPLY",
        "END-PERFORM", "END-READ", "END-SEARCH", "END-STRING", "END-SUBTRACT", "END-UNSTRING", "EVALUATE",
        "EXEC", "EXIT", "GO", "GOBACK", "IF", "INITIALIZE", "INSPECT", "MERGE", "MOVE", "MULTIPLY", "OPEN",
        "PERFORM", "READ", "RELEASE", "RETURN", "REWRITE", "SEARCH", "SET", "SORT", "START", "STOP", "STRING",
        "SUBTRACT", "UNSTRING", "WHEN", "WRITE", "COPY", "OTHERWISE", "THEN", "NEXT",
    }
)  # fmt: skip
# The COBOL explicit scope terminators: a data name may itself start with END-
# (GENAPP's END-POLICY-POS), so only these words end a statement.
_END_WORDS = frozenset(
    "END-" + w
    for w in ("ACCEPT", "ADD", "CALL", "COMPUTE", "DELETE", "DISPLAY", "DIVIDE", "EVALUATE", "EXEC", "IF",
              "INVOKE", "JSON", "MULTIPLY", "PERFORM", "READ", "RECEIVE", "RETURN", "REWRITE", "SEARCH", "START",
              "STRING", "SUBTRACT", "UNSTRING", "WRITE", "XML")
)  # fmt: skip
_DATA_VERBS = ("MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "STRING", "UNSTRING", "INITIALIZE",
               "READ", "RETURN", "WRITE", "REWRITE", "RELEASE", "ACCEPT")  # fmt: skip
# #3492: the file-I/O verbs above move a whole record, as a MOVE does.
IO_VERBS = frozenset({"READ", "RETURN", "WRITE", "REWRITE", "RELEASE", "ACCEPT"})
_READ_PHRASE = frozenset({"NEXT", "PREVIOUS", "RECORD", "KEY", "IS", "WITH", "NO", "LOCK", "IGNORE"})
_STOPS = frozenset({"ON", "NOT", "SIZE", "OVERFLOW", "EXCEPTION", "INVALID", "AT"})
_FIGURATIVE = frozenset(
    {
        "SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES", "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
        "QUOTE", "QUOTES", "NULL", "NULLS",
    }
)  # fmt: skip
# Words inside a COMPUTE / arithmetic operand list that are not data names.
_NOISE = frozenset({"ROUNDED", "MODE", "IS", "BY", "OF", "IN", "AND", "OR", "TO", "FROM", "GIVING", "INTO"})


def _procedure_text(code_stream: str) -> str:
    """Sequence fields blanked, comment lines blanked, and everything before the
    PROCEDURE DIVISION header blanked (offsets and line numbers unchanged)."""
    text = _blank_sequence_fields(code_stream, "cobol")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if len(line) > 6 and line[6] in "*/Dd":  # comment, page eject, debugging line
            lines[i] = ""
        elif "*>" in line:
            lines[i] = line[: line.index("*>")]
    text = "\n".join(lines)
    m = re.search(r"(?<![A-Z0-9-])PROCEDURE[ \t\n]{1,200}DIVISION(?![A-Z0-9-])", text, re.I)
    if m:
        text = re.sub(r"[^\n]", " ", text[: m.end()]) + text[m.end() :]
    return text


class _Stream:
    def __init__(self, toks: list[tuple[str, int]], start: int, end: int):
        self.toks, self.i, self.end = toks, start, end

    def peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.toks[j][0].upper() if j < self.end else ""

    def done(self) -> bool:
        t = self.peek()
        return self.i >= self.end or t == "." or t in _VERBS or t in _END_WORDS

    def operand(self) -> Optional[tuple[str, str, bool]]:
        """(text, kind, refmod) of the operand at the cursor, advancing past it, or
        None (cursor unmoved) when the cursor is not at an operand."""
        t = self.peek()
        if not t or t == "." or t in _VERBS or t in _STOPS or t in _END_WORDS:
            return None
        raw = self.toks[self.i][0]
        if raw[:1] in "'\"" or (len(raw) > 1 and raw[1] in "'\"" and raw[0].upper() in "XNGZ"):
            self.i += 1
            return raw, "literal", False
        if re.fullmatch(_NUMBER, raw):
            self.i += 1
            return raw, "literal", False
        if t == "ALL" and self.peek(1) and (self.peek(1)[:1] in "'\"" or self.peek(1) in _FIGURATIVE):
            self.i += 2
            return f"ALL {self.toks[self.i - 1][0]}", "figurative", False
        if t in _FIGURATIVE:
            self.i += 1
            return t, "figurative", False
        if t in ("LENGTH", "ADDRESS") and self.peek(1) == "OF":
            self.i += 2
            inner = self.operand()
            return (f"{t} OF {inner[0]}" if inner else t), t.lower(), False
        if t == "FUNCTION":
            name = self.peek(1)
            self.i += 2
            self._skip_parens()
            return f"FUNCTION {name}", "function", False
        if not re.fullmatch(_WORD, raw, re.I) or not re.search(r"[A-Z]", t):
            return None
        name = t
        self.i += 1
        while self.peek() in ("OF", "IN") and re.fullmatch(_WORD, self.peek(1), re.I):
            name += f" OF {self.peek(1)}"
            self.i += 2
        refmod = False
        while self.peek() == "(":
            refmod = self._skip_parens() or refmod
        return name, "item", refmod

    def _skip_parens(self) -> bool:
        """Skip one balanced ( ... ) group; True when it is a reference modifier."""
        if self.peek() != "(":
            return False
        depth, colon = 0, False
        while self.i < self.end:
            t = self.peek()
            if t == "(":
                depth += 1
            elif t == ")":
                depth -= 1
                if depth == 0:
                    self.i += 1
                    break
            elif t == ":" and depth == 1:
                colon = True
            self.i += 1
        return colon

    def operands(self, stop: frozenset) -> list[tuple[str, str, bool]]:
        out = []
        while not self.done() and self.peek() not in stop:
            if self.peek() in (",", "ROUNDED"):
                self.i += 1
                continue
            op = self.operand()
            if op is None:
                break
            out.append(op)
        return out

    def expression_items(self) -> list[tuple[str, str, bool]]:
        """Every data name of an arithmetic expression (FUNCTION names skipped,
        a function's arguments kept), up to the statement's end."""
        out = []
        while not self.done() and self.peek() not in _STOPS and self.peek() != "END-COMPUTE":
            t = self.peek()
            if t == "FUNCTION":
                self.i += 2
                continue
            if t in _NOISE or not re.search(r"[A-Z]", t) or t in _FIGURATIVE:
                self.i += 1
                continue
            op = self.operand()
            if op is None:
                self.i += 1
                continue
            if op[1] == "item":
                out.append(op)
        return out


def _rows_of(verb: str, s: _Stream) -> list[tuple[Optional[tuple], tuple, bool]]:
    """(source operand or None, target operand, corresponding) pairs of one statement."""
    pairs: list[tuple[Optional[tuple], tuple, bool]] = []
    if verb == "MOVE":
        corr = s.peek() in ("CORR", "CORRESPONDING")
        if corr:
            s.i += 1
        src = s.operand()
        if src is None or s.peek() != "TO":
            return []
        s.i += 1
        pairs = [(src, t, corr) for t in s.operands(frozenset())]
    elif verb == "COMPUTE":
        targets = s.operands(frozenset({"=", "EQUAL"}))
        if s.peek() not in ("=", "EQUAL"):
            return []
        s.i += 1
        sources = s.expression_items()
        pairs = [(a, t, False) for t in targets for a in sources]
    elif verb in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
        if s.peek() in ("CORR", "CORRESPONDING"):
            return []
        first = s.operands(frozenset({"TO", "FROM", "BY", "INTO", "GIVING"}))
        joiner = s.peek()
        s.i += 1 if joiner in ("TO", "FROM", "BY", "INTO", "GIVING") else 0
        second = s.operands(frozenset({"GIVING", "REMAINDER"})) if joiner != "GIVING" else []
        giving = []
        if joiner == "GIVING":
            giving = s.operands(frozenset({"REMAINDER"}))
        elif s.peek() == "GIVING":
            s.i += 1
            giving = s.operands(frozenset({"REMAINDER"}))
        remainder = []
        if s.peek() == "REMAINDER":
            s.i += 1
            remainder = s.operands(frozenset())
        if giving:
            sources = first + second
            pairs = [(a, t, False) for t in giving + remainder for a in sources]
        else:
            pairs = [(a, t, False) for t in second for a in first]
    elif verb == "STRING":
        pieces: list = []
        while not s.done() and s.peek() != "INTO":
            if s.peek() == "DELIMITED":
                s.i += 1
                if s.peek() == "BY":
                    s.i += 1
                if s.peek() == "SIZE":
                    s.i += 1
                else:
                    s.operand()
                continue
            if s.peek() == ",":
                s.i += 1
                continue
            op = s.operand()
            if op is None:
                break
            pieces.append(op)
        if s.peek() != "INTO":
            return []
        s.i += 1
        target = s.operand()
        pairs = [(a, target, False) for a in pieces] if target else []
    elif verb == "UNSTRING":
        src = s.operand()
        if src is None:
            return []
        while not s.done() and s.peek() != "INTO":
            s.i += 1
        if s.peek() != "INTO":
            return []
        s.i += 1
        while not s.done() and s.peek() not in ("WITH", "POINTER", "TALLYING") and s.peek() not in _STOPS:
            if s.peek() in ("DELIMITER", "COUNT"):
                s.i += 1
                if s.peek() == "IN":
                    s.i += 1
                s.operand()
                continue
            if s.peek() == ",":
                s.i += 1
                continue
            op = s.operand()
            if op is None:
                break
            pairs.append((src, op, False))
    elif verb == "INITIALIZE":
        stop = frozenset({"REPLACING", "WITH", "ALL", "TO", "DEFAULT", "FILLER"})
        pairs = [(None, t, False) for t in s.operands(stop)]
    elif verb in ("READ", "RETURN"):
        # READ file [NEXT | PREVIOUS] [RECORD] [INTO x] ...: the file's record -> x.
        f = s.operand()
        # NEXT / PREVIOUS / RECORD / KEY IS / WITH LOCK are READ's own phrases here.
        while s.peek() in _READ_PHRASE or (not s.done() and s.peek() not in _STOPS and s.peek() != "INTO"):
            s.i += 1
        if f is None or s.peek() != "INTO":
            return []
        s.i += 1
        t = s.operand()
        pairs = [((f[0], "file", False), t, False)] if t else []
    elif verb in ("WRITE", "REWRITE", "RELEASE"):
        # WRITE record [FROM x] ...: x -> the record.
        rec = s.operand()
        if rec is None or s.peek() != "FROM":
            return []
        s.i += 1
        src = s.operand()
        pairs = [(src, rec, False)] if src else []
    elif verb == "ACCEPT":
        # ACCEPT x [FROM DATE [YYYYMMDD] | DAY | TIME | ...]: a runtime-supplied value -> x.
        t = s.operand()
        words = ["SYSIN"]
        if t is not None and s.peek() == "FROM":
            s.i += 1
            words = []
            while not s.done() and len(words) < 2 and re.fullmatch(_WORD, s.peek() or "-", re.I):
                words.append(s.peek())
                s.i += 1
        pairs = [((" ".join(words) or "SYSIN", "special", False), t, False)] if t else []
    return [p for p in pairs if p[1][1] == "item"]


def data_moves(code_stream: str) -> list[dict[str, Any]]:
    """Every source -> target pair of the data-moving statements of one COBOL file."""
    if not code_stream or not any(v in code_stream.upper() for v in _DATA_VERBS):
        return []
    text = _procedure_text(code_stream)
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    toks = [(m.group(0), m.start()) for m in _TOKEN.finditer(text)]
    rows: list[dict[str, Any]] = []
    i = 0
    while i < len(toks):
        word = toks[i][0].upper()
        if word == "EXEC":
            while i < len(toks) and toks[i][0].upper() != "END-EXEC":
                i += 1
            i += 1
            continue
        if word not in _DATA_VERBS:
            i += 1
            continue
        line = bisect.bisect_left(newlines, toks[i][1]) + 1
        s = _Stream(toks, i + 1, min(len(toks), i + 1 + _STATEMENT_TOKENS))
        for src, target, corr in _rows_of(word, s):
            rows.append(
                {
                    "verb": word,
                    "source": src[0] if src else None,
                    "source_kind": src[1] if src else None,
                    "target": target[0],
                    "corresponding": corr,
                    "source_refmod": bool(src and src[2]),
                    "target_refmod": target[2],
                    "line": line,
                }
            )
        i = max(s.i, i + 1)
    return rows
