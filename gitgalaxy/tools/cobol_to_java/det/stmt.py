"""The PROCEDURE DIVISION as a statement tree.

tree-sitter's COBOL grammar gives a flat sequence -- statements, IF / ELSE / WHEN headers, END-x terminators,
conditional phrases (AT END, INVALID KEY, ON SIZE ERROR ...) and periods. The scope rules of COBOL rebuild the
nesting: a period ends every open scope; ELSE pairs with the nearest IF without one; WHEN starts an EVALUATE branch;
a phrase belongs to the statement before it until the next phrase of that statement, its END-x, or a terminator of
an enclosing scope. Each statement's own meaning is parsed from its text (det.expr).

EXEC blocks are replaced, before parsing, by `CALL 'GGEXECnnnn'` placeholders; their text is kept in a table."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det.source import (
    Line,
    _outside_literals,
    as_fixed_rows,
    cobol_parser,
    comma_literals,
    narrowed,
    refusal,
    unwrap,
)


@dataclass
class Stmt:
    kind: str  # MOVE, IF, EVALUATE, PERFORM, ...; HOLE for what is not modelled
    line: int
    text: str
    data: dict = field(default_factory=dict)  # the parsed parts
    body: list = field(default_factory=list)  # IF then / inline PERFORM body
    orelse: list = field(default_factory=list)  # IF else
    whens: list = field(default_factory=list)  # EVALUATE: [(conditions, body)], conditions None for OTHER
    phrases: dict = field(default_factory=dict)  # AT-END / NOT-AT-END / INVALID-KEY / SIZE-ERROR ... -> body


@dataclass
class Paragraph:
    name: str
    section: str | None
    line: int
    body: list = field(default_factory=list)
    sentence_ends: list = field(default_factory=list)  # len(body) at each period: the sentences


@dataclass
class Procedure:
    paragraphs: list
    execs: dict  # placeholder number -> EXEC text
    using: list  # PROCEDURE DIVISION USING items


PHRASES = {"at_end": "AT-END", "not_at_end": "NOT-AT-END", "invalid_key": "INVALID-KEY",
           "not_invalid_key": "NOT-INVALID-KEY", "on_size_error": "SIZE-ERROR", "not_on_size_error": "NOT-SIZE-ERROR",
           "on_overflow": "OVERFLOW", "not_on_overflow": "NOT-OVERFLOW", "on_exception": "EXCEPTION",
           "not_on_exception": "NOT-EXCEPTION", "at_eop": "AT-EOP", "not_at_eop": "NOT-AT-EOP"}  # fmt: skip
STATEMENT_ENDS = {"END_READ", "END_WRITE", "END_REWRITE", "END_DELETE", "END_START", "END_COMPUTE", "END_ADD",
                  "END_SUBTRACT", "END_MULTIPLY", "END_DIVIDE", "END_STRING", "END_UNSTRING", "END_CALL",
                  "END_RETURN", "END_ACCEPT", "END_DISPLAY"}  # fmt: skip


class _Frame:
    def __init__(self, kind: str, node: Stmt | None, target: list):
        self.kind, self.node, self.target = kind, node, target
        self.has_else = False


def parse(lines: list[Line]) -> Procedure:
    parser = _parser_cache()  # first: a missing translator extra fails here, before any work

    # #4462: national / DBCS text, IDMS, several programs (each read on its own): refused by name
    why = refusal(lines)  # (a survey's what-if may switch one check off: source.survey_unmask)
    if why:
        raise E.ExprError(why)
    # #4272: a wide character in a `*>` comment / a PROCEDURE DIVISION literal; #4462: a decimal comma's literal
    lines = comma_literals(narrowed(lines))
    text, rows = as_fixed_rows(lines)
    m = re.search(r"^ {7}\s*PROCEDURE\s+DIVISION\b[^.]*\.", text, re.I | re.M)
    if not m:
        raise E.ExprError("no PROCEDURE DIVISION")
    header = m.group(0)
    using = []
    u = re.search(r"\bUSING\b(.*)\.", header, re.I | re.S)
    if u:
        using = [w.upper() for w in u.group(1).replace(",", " ").split()
                 if w.upper() not in ("BY", "REFERENCE", "VALUE", "CONTENT")]  # fmt: skip
    execs: dict[int, str] = {}

    def ph(mm):
        execs[len(execs) + 1] = unwrap(mm.group(0))
        # as many lines as the block: every later statement keeps its own line (a multi-line EXEC SQL / CICS block
        # had shifted them -- the Db2 repositories' methods are found by the statement's line)
        return f"CALL 'GGEXEC{len(execs):04d}'" + "\x01" * mm.group(0).count("\n")

    proc_text = re.sub(r"\bEXEC(?:UTE)?\s+(CICS|SQL|DLI)\b.*?\bEND-EXEC\b", ph, text[m.start() :], flags=re.S | re.I)
    # #4462: JSON PARSE / JSON GENERATE / XML PARSE / XML GENERATE and SET pointer TO ENTRY: no statements of the
    # grammar's; a placeholder CALL, translated as a hole by name (_markup; before ENTRY's, which would take SET's
    # `ENTRY 'x'`)
    markups: dict[int, str] = {}
    proc_text = _markup_placeholders(proc_text, markups)
    # SORT / MERGE: the grammar drops their later phrases (WITH DUPLICATES, OUTPUT PROCEDURE ...); each becomes a
    # placeholder CALL too, its text parsed here (_sort_merge)
    sorts: dict[int, str] = {}
    proc_text = _sort_placeholders(proc_text, sorts)
    # #4462: ENTRY 'name' [USING ...] (an IMS DL/I batch program's ENTRY 'DLITCBL' USING its PCBs): no statement of
    # the grammar's; a placeholder CALL too, its text parsed here (_entry)
    entries: dict[int, str] = {}
    proc_text = _entry_placeholders(proc_text, entries)
    # #4462: OS/VS COBOL's EXHIBIT {NAMED | CHANGED NAMED | CHANGED} operand ...: no statement of the grammar's; a
    # placeholder CALL too, its text parsed here (_exhibit)
    exhibits: dict[int, str] = {}
    proc_text = _exhibit_placeholders(proc_text, exhibits)
    # the block's lines back after the rest of its last line (its period stays with the CALL), as blank lines
    proc_text = re.sub(r"(\x01+)([^\n]*\n)", lambda mm: mm.group(2) + "       \n" * len(mm.group(1)), proc_text)
    proc_text = re.sub(r"\bNOT=", "NOT =", proc_text, flags=re.I)  # the grammar wants a space after NOT
    proc_text = _join_not_breaks(proc_text)
    # #4681: the grammar refuses the abbreviated `... OR NOT = 'C'` / `AND NOT = 'C'` (it takes `NOT <`, `NOT >`
    # and `NOT EQUAL`): spelled EQUAL, the same relation; string literals are left as they are
    proc_text = _ABBREV_NOT_EQ.sub(lambda m: m.group(0) if m.group(1) is None else m.group(1) + "NOT EQUAL", proc_text)
    pre = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. GGDET.\n"
    src = (pre + "       PROCEDURE DIVISION.\n" + proc_text[len(header) :].lstrip("\n")).encode("latin-1")
    # line numbers: map back to the expanded program's lines
    # (src row 3 is the text line after the header's last; it had been two lines early)
    base_line = text[: m.end()].count("\n") + 1
    # #4462: the grammar is handed FUNCTION f (1:4) as f (1,4) (the same length: every node's text is still `src`'s)
    root = parser.parse(_function_refmods(src.decode("latin-1")).encode("latin-1")).root_node
    prog = next((c for c in root.children if c.type == "program_definition"), root)
    pd = next((c for c in prog.children if c.type == "procedure_division"), None)
    if pd is None:
        raise E.ExprError("the PROCEDURE DIVISION does not parse")

    def origin(node) -> int:
        k = node.start_point[0] - 3 + base_line  # 3 synthetic lines before; a row of `text`
        return lines[rows[k]].line if 0 <= k < len(rows) else node.start_point[0] + 1

    # #4411: a parse error outside the PROCEDURE DIVISION node is procedure text the walk below never sees (a
    # paragraph after ENTRY ... USING, say): the program is refused, never translated without it
    stray = next(
        (n for n in _problems(root) if not (pd.start_byte <= n.start_byte and n.end_byte <= pd.end_byte)), None
    )
    if stray is not None:
        raise E.ExprError(f"the PROCEDURE DIVISION does not parse at line {origin(stray)}")

    # #4411: a parse error outside the PROCEDURE DIVISION node is procedure text the walk below never sees (a
    # paragraph after ENTRY ... USING, say): the program is refused, never translated without it
    stray = next(
        (n for n in _problems(root) if not (pd.start_byte <= n.start_byte and n.end_byte <= pd.end_byte)), None
    )
    if stray is not None:
        raise E.ExprError(f"the PROCEDURE DIVISION does not parse at line {origin(stray)}")

    paragraphs: list[Paragraph] = [Paragraph("(MAIN)", None, 0)]
    section: str | None = None
    stack: list[_Frame] = [_Frame("PARA", None, paragraphs[0].body)]

    def close_all():
        del stack[1:]

    def node_text(n) -> str:
        return unwrap(src[n.start_byte : n.end_byte].decode("latin-1"))

    for n in pd.children:
        t = n.type
        if t in (".",):
            continue
        if t == "ERROR":
            stack[-1].target.append(Stmt("HOLE", origin(n), node_text(n), {"why": "does not parse"}))
            continue
        if n.has_error:  # #4411: an ERROR / MISSING node inside: the node's text is not what the grammar read
            if t in ("paragraph_header", "section_header"):
                raise E.ExprError(f"line {origin(n)}: {t} does not parse")
            if t in _FRAMED:  # the frame still opens (its END closes it); its condition is a hole
                n_text = node_text(n)
                bad = ("UNPARSED", n_text, "does not parse")
                if t in ("if_header", "else_if_header"):
                    f = _pop_to_if(stack) if t == "else_if_header" else None
                    if f is not None:
                        f.has_else = True
                        f.target = _node(f).orelse
                    s = Stmt("IF", origin(n), n_text, {"cond": bad})
                    stack[-1].target.append(s)
                    stack.append(_Frame("IF", s, s.body))
                elif t == "evaluate_header":
                    s = Stmt("EVALUATE", origin(n), n_text, {"subjects": [("UNPARSED", n_text)]})
                    stack[-1].target.append(s)
                    stack.append(_Frame("EVALUATE", s, []))
                elif t == "perform_statement_loop":
                    s = Stmt("HOLE", origin(n), n_text, {"why": "does not parse"})
                    stack[-1].target.append(s)
                    stack.append(_Frame("PERFORM", s, s.body))
                elif t == "when" and (sf := _search_frame(stack)) is not None:  # a SEARCH's WHEN: condition a hole
                    unparsed_body: list = []
                    _node(sf).whens.append((("UNPARSED", n_text, "does not parse"), unparsed_body))
                    sf.target = unparsed_body
                else:  # WHEN / WHEN OTHER: its body is reached through an unparsed object
                    f = _pop_to(stack, "EVALUATE")
                    unparsed_body = []
                    _node(f).whens.append(([[("UNPARSED", n_text, "does not parse", False)]], unparsed_body))
                    f.target = unparsed_body
                continue
            if t.endswith("_statement") or t.startswith("perform_statement"):
                stack[-1].target.append(Stmt("HOLE", origin(n), node_text(n), {"why": "does not parse"}))
                continue
            # a phrase, an END-x ...: as a hole it would move the statements after it to another block
            raise E.ExprError(f"line {origin(n)}: {t} does not parse")
        if t == "paragraph_header":
            name = node_text(n).strip().rstrip(".").strip().upper()
            p = Paragraph(name, section, origin(n))
            paragraphs.append(p)
            stack[:] = [_Frame("PARA", None, p.body)]
            continue
        if t == "section_header":
            section = node_text(n).split()[0].upper()
            p = Paragraph(section, section, origin(n))
            paragraphs.append(p)
            stack[:] = [_Frame("PARA", None, p.body)]
            continue
        if t == "period":
            close_all()
            paragraphs[-1].sentence_ends.append(len(paragraphs[-1].body))
            continue
        if t == "if_header":
            s = Stmt("IF", origin(n), node_text(n), {"cond": _cond(node_text(n)[2:])})
            stack[-1].target.append(s)
            stack.append(_Frame("IF", s, s.body))
            continue
        if t == "else_if_header":
            # ELSE IF ...: the else branch holds a new IF
            f = _pop_to_if(stack)
            f.has_else = True
            f.target = _node(f).orelse
            s = Stmt("IF", origin(n), node_text(n), {"cond": _cond(re.sub(r"(?i)^\s*ELSE\s+IF", "", node_text(n)))})
            f.target.append(s)
            stack.append(_Frame("IF", s, s.body))
            continue
        if t == "else_header":
            f = _pop_to_if(stack)
            f.has_else = True
            f.target = _node(f).orelse
            continue
        if t == "END_IF":
            _pop_to(stack, "IF")  # the innermost open IF, with or without its ELSE
            stack.pop()
            continue
        if t == "evaluate_header":
            s = Stmt("EVALUATE", origin(n), node_text(n), {"subjects": _subjects(node_text(n)[8:])})
            stack[-1].target.append(s)
            stack.append(_Frame("EVALUATE", s, []))
            continue
        if t == "when" and (sf := _search_frame(stack)) is not None:
            # #4462: a SEARCH's WHEN (SEARCH ALL has one): its condition, its body
            body: list = []
            _node(sf).whens.append((_cond(re.sub(r"(?i)^\s*WHEN\b", "", node_text(n))), body))
            sf.target = body
            continue
        if t in ("when", "when_other"):
            f = _pop_to(stack, "EVALUATE")
            ev = _node(f)
            body = []
            if t == "when_other":
                ev.whens.append((None, body))
            else:
                conds = _whens(node_text(n))
                # stacked WHENs with no statements between share one body
                if ev.whens and not ev.whens[-1][1] and ev.whens[-1][0] is not None:
                    prev = ev.whens.pop()
                    conds = prev[0] + conds
                ev.whens.append((conds, body))
            f.target = body
            continue
        if t == "END_EVALUATE":
            _pop_to(stack, "EVALUATE")
            stack.pop()
            continue
        if t == "perform_statement_loop":
            s = _statement(node_text(n), origin(n))
            s.data["inline"] = True
            stack[-1].target.append(s)
            stack.append(_Frame("PERFORM", s, s.body))
            continue
        if t == "END_PERFORM":
            _pop_to(stack, "PERFORM")
            stack.pop()
            continue
        if t in PHRASES:
            name = PHRASES[t]
            while stack[-1].kind == "PHRASE":
                stack.pop()
            if t == "at_end" and stack[-1].kind == "SEARCH" and not _node(stack[-1]).whens:
                # #4462: SEARCH ... AT END (before its WHENs): the SEARCH's own phrase
                search = _node(stack[-1])
                stack.append(_Frame("PHRASE", search, search.phrases.setdefault(name, [])))
                continue
            owner = next((x for x in reversed(stack[-1].target) if x.kind not in ("HOLE",)), None)
            if owner is None:
                stack[-1].target.append(Stmt("HOLE", origin(n), node_text(n), {"why": "phrase with no statement"}))
                continue
            body = owner.phrases.setdefault(name, [])
            stack.append(_Frame("PHRASE", owner, body))
            continue
        if t == "search_statement":
            # #4462: SEARCH [ALL] table [VARYING x]: a frame, its AT END and WHENs (_search_frame) inside, closed by
            # END-SEARCH or the period
            s = _search(node_text(n), origin(n))
            stack[-1].target.append(s)
            stack.append(_Frame("SEARCH", s, []))
            continue
        if t == "END_SEARCH":
            while stack[-1].kind == "PHRASE":
                stack.pop()
            _pop_to(stack, "SEARCH")
            stack.pop()
            continue
        if t in STATEMENT_ENDS:
            while stack[-1].kind == "PHRASE":
                stack.pop()
            continue
        if t.endswith("_statement") or t.startswith("perform_statement"):
            s = _statement(node_text(n), origin(n))
            if s.kind == "CALL" and re.match(r"GGEXEC\d{4}$", s.data.get("program") or ""):
                s = Stmt("EXEC", s.line, execs[int(s.data["program"][6:])])
            elif s.kind == "CALL" and re.match(r"GGSORT\d{4}$", s.data.get("program") or ""):
                s = _sort_merge(unwrap(sorts[int(s.data["program"][6:])]), s.line)
            elif s.kind == "CALL" and re.match(r"GGENTR\d{4}$", s.data.get("program") or ""):
                s = _entry(unwrap(entries[int(s.data["program"][6:])]), s.line)
            elif s.kind == "CALL" and re.match(r"GGEXHB\d{4}$", s.data.get("program") or ""):
                s = _exhibit(unwrap(exhibits[int(s.data["program"][6:])]), s.line)
            elif s.kind == "CALL" and re.match(r"GGMKUP\d{4}$", s.data.get("program") or ""):
                s = _markup(unwrap(markups[int(s.data["program"][6:])]), s.line)
            stack[-1].target.append(s)
            continue
        stack[-1].target.append(Stmt("HOLE", origin(n), node_text(n), {"why": f"grammar node {t}"}))
    if not paragraphs[0].body:
        paragraphs.pop(0)
    first = next((p.body[0] for p in paragraphs if p.body), None)
    if first is not None and first.kind == "ENTRY" and not using:
        # #4462: the program's first statement (DL/I's ENTRY 'DLITCBL' USING pcb ...): where the caller enters it,
        # with those parameters, as PROCEDURE DIVISION USING would; reached in sequence, ENTRY does nothing
        first.data["first"] = True
        using = [r.name for r in first.data["using"]]
    return Procedure(paragraphs, execs, using)


# pd children that open a frame (closed by their END_x / ELSE / WHEN, or by the period)
_FRAMED = {"if_header", "else_if_header", "evaluate_header", "when", "when_other", "perform_statement_loop"}


_REL_WORD = r"(?:[<>=]+|EQUAL|GREATER|LESS)(?![\w-])"


def _join_not_breaks(text: str) -> str:
    """#4674 / #4656: the grammar refuses a NOT split from its relational operator by a line break -- NOT at the end
    of a source line (`IF S3 NOT` / `< 3`), or a NOT that starts a line after an AND / OR (`AND` / `NOT < 2`) -- and
    with it the whole PROCEDURE DIVISION. The break moves after the operator (or the token after NOT), with the next
    line's indent (fixed-format columns count): the same number of lines, so every statement keeps its line."""

    def in_literal(at: int) -> bool:
        before = text[text.rfind("\n", 0, at) + 1 : at]  # an odd quote count: the NOT is data, not a keyword
        return bool(before.count("'") % 2 or before.count('"') % 2)

    def rejoin(prev: str, ws: str, tail: str) -> str:
        return f"{prev}{tail}" + "\n" * ws.count("\n") + (ws[ws.rfind("\n") + 1 :] if "\n" in ws else "")

    def before_not(mm: re.Match) -> str:
        if in_literal(mm.end(2)):
            return mm.group(0)
        return rejoin(mm.group(1) + " ", mm.group(2) + mm.group(3), f"NOT {mm.group(4)}")

    def after_not(mm: re.Match) -> str:
        if in_literal(mm.start()):
            return mm.group(0)
        return rejoin("", mm.group(2), f"{mm.group(1)} {mm.group(3)}")

    text = re.sub(rf"(\S)(\s*\n\s*)(?<![\w-])NOT(\s+)({_REL_WORD})", before_not, text, flags=re.I)
    return re.sub(r"(?<![\w-])(NOT)([ \t]*\n\s*)([^\s.]+)", after_not, text, flags=re.I)


def _problems(root) -> list:
    """The outermost ERROR and MISSING nodes of a tree."""
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if n.type == "ERROR" or n.is_missing:
            out.append(n)
        elif n.has_error:
            stack.extend(n.children)
    return out


_PARSER = None


def _parser_cache():
    global _PARSER
    if _PARSER is None:
        _PARSER = cobol_parser()
    return _PARSER


def _node(f: _Frame) -> Stmt:
    if f.node is None:
        raise E.ExprError(f"{f.kind} frame has no statement")
    return f.node


def _search_frame(stack: list[_Frame]) -> _Frame | None:
    """#4462: the SEARCH a WHEN belongs to: the innermost open SEARCH or EVALUATE is a SEARCH (the frames above it,
    an IF in the previous WHEN's body ..., are closed by the WHEN), and it may take one more WHEN (SEARCH ALL has
    one: a second WHEN after it closes it and belongs to the EVALUATE around it). None: an EVALUATE's WHEN."""
    k = next((i for i in range(len(stack) - 1, 0, -1) if stack[i].kind in ("SEARCH", "EVALUATE")), None)
    if k is None or stack[k].kind != "SEARCH":
        return None
    search = _node(stack[k])
    del stack[k + 1 :]
    if search.data["all"] and search.whens:
        stack.pop()
        return _search_frame(stack)
    return stack[k]


def _search(text: str, line: int) -> Stmt:
    """SEARCH [ALL] table [VARYING identifier] (the phrases and WHENs follow as nodes of their own). data: table
    (Ref), all, varying (Ref | None); whens [(condition, body)]; phrases AT-END."""
    p = E.Parser(E.tokenize(text)[1:])
    every = bool(p.accept("ALL"))
    d: dict[str, Any] = {"table": None, "all": every, "varying": None, "error": None}
    try:  # an unreadable header still opens the frame (its WHENs are its own); gen refuses the statement
        d["table"] = p.ref()
        d["varying"] = p.ref() if p.accept("VARYING") else None
        if not p.done():
            raise E.ExprError(f"left over {' '.join(p.t[p.i :])}")
    except E.ExprError as e:
        d["error"] = str(e)
    return Stmt("SEARCH", line, text, d)


def _pop_to_if(stack: list[_Frame]) -> _Frame:
    """The innermost IF still open without an ELSE (closing phrases and IFs that already have theirs)."""
    while len(stack) > 1:
        f = stack[-1]
        if f.kind == "IF" and not f.has_else:
            return f
        if f.kind == "IF" and f.has_else:
            stack.pop()
            continue
        stack.pop()
    raise E.ExprError("ELSE / END-IF with no IF")


def _pop_to(stack: list[_Frame], kind: str) -> _Frame:
    while len(stack) > 1 and stack[-1].kind != kind:
        stack.pop()
    if stack[-1].kind != kind:
        raise E.ExprError(f"no open {kind}")
    return stack[-1]


def _cond(text: str):
    t = re.sub(r"(?i)\bTHEN\s*$", "", text.strip())
    try:
        return E.parse_condition(t)
    except E.ExprError as e:
        return ("UNPARSED", t, str(e))


def _subjects(text: str) -> list:
    out = []
    for part in re.split(r"(?i)\bALSO\b", text.strip()):
        p = part.strip()
        if p.upper() in ("TRUE", "FALSE"):
            out.append(p.upper())
        else:
            try:
                out.append(E.parse_arith(p))
            except E.ExprError:
                out.append(("UNPARSED", p))
    return out


def _whens(text: str) -> list:
    """One WHEN node may hold several stacked WHENs: [[object per subject], ...]."""
    out = []
    for w in re.split(r"(?i)\bWHEN\b", text)[1:]:
        objs = []
        for part in re.split(r"(?i)\bALSO\b", w.strip()):
            p = part.strip()
            objs.append(_when_object(p))
        out.append(objs)
    return out


def _when_object(p: str) -> tuple[Any, Any, Any, bool]:
    """(kind, a, b, negated): ANY / TRUE / FALSE; VALUE v; RANGE lo hi; COND condition; UNPARSED text why."""
    up = p.upper()
    if up == "ANY":
        return ("ANY", None, None, False)
    if up in ("TRUE", "FALSE"):
        return (up, None, None, False)
    # WHEN NOT negates a value or a range (an identifier, a literal, an arithmetic expression); a condition keeps a
    # leading NOT as its own -- `WHEN NOT A-FLAG AND B = C` is (NOT A-FLAG) AND B = C, not NOT (A-FLAG AND B = C)
    whole, neg = p, False
    if up.startswith("NOT "):
        neg, p = True, p[4:]
    m = re.match(r"(.+?)\s+(?:THRU|THROUGH)\s+(.+)$", p, re.I)
    try:
        if m:
            return ("RANGE", E.parse_arith(m.group(1)), E.parse_arith(m.group(2)), neg)
        try:
            return ("VALUE", E.parse_arith(p), None, neg)
        except E.ExprError:
            return ("COND", E.parse_condition(whole), None, False)
    except E.ExprError:
        try:
            return ("COND", E.parse_condition(whole), None, False)
        except E.ExprError as e:
            return ("UNPARSED", p, str(e), False)


# ---- one statement ---------------------------------------------------------------------------------------------
def _statement(text: str, line: int) -> Stmt:
    toks = E.tokenize(text)
    if not toks:
        return Stmt("HOLE", line, text, {"why": "empty"})
    verb = toks[0].upper()
    try:
        fn = _PARSERS.get(verb)
        if fn is None:
            return Stmt("HOLE", line, text, {"why": f"{verb} not modelled"})
        return fn(E.Parser(toks[1:]), text, line)
    except E.ExprError as e:
        return Stmt("HOLE", line, text, {"why": f"{verb}: {e}"})


def _refs_until(p: E.Parser, stops: set[str]) -> list:
    out = []
    while not p.done() and p.up() not in stops:
        out.append(p.operand())
    return out


def _move(p: E.Parser, text: str, line: int) -> Stmt:
    corr = p.accept("CORRESPONDING", "CORR")
    src = p.operand()
    if not p.accept("TO"):
        raise E.ExprError("MOVE without TO")
    targets = []
    while not p.done():
        targets.append(p.ref())
    if corr:
        return Stmt("HOLE", line, text, {"why": "MOVE CORRESPONDING"})
    return Stmt("MOVE", line, text, {"from": src, "to": targets})


def _display(p: E.Parser, text: str, line: int) -> Stmt:
    ops, upon, no_adv = [], None, False
    while not p.done():
        if p.up() == "UPON":
            p.take()
            upon = p.take().upper()
            continue
        if p.up() == "WITH" and p.up(1) == "NO":
            p.i += 3
            no_adv = True
            continue
        if p.up() == "NO" and p.up(1) == "ADVANCING":
            p.i += 2
            no_adv = True
            continue
        ops.append(p.operand())
    return Stmt("DISPLAY", line, text, {"operands": ops, "upon": upon, "no_advancing": no_adv})


def _target_list(p: E.Parser, stops: set[str]) -> list:
    out = []
    while not p.done() and p.up() not in stops:
        r = p.ref()
        rounded = p.accept("ROUNDED")
        out.append((r, rounded))
    return out


def _compute(p: E.Parser, text: str, line: int) -> Stmt:
    targets = _target_list(p, {"=", "EQUAL"})
    p.take()
    expr = p.arith()
    if not p.done():
        raise E.ExprError(f"left over: {' '.join(p.t[p.i :])}")
    return Stmt("COMPUTE", line, text, {"targets": targets, "expr": expr})


def _add(p: E.Parser, text: str, line: int) -> Stmt:
    if p.up() in ("CORRESPONDING", "CORR"):
        raise E.ExprError("ADD CORRESPONDING")
    ops = _refs_until(p, {"TO", "GIVING"})
    giving = None
    targets = []
    if p.accept("TO"):
        tos: list[Any] = []
        while not p.done() and p.up() != "GIVING":
            tos.append(p.operand())
            if p.accept("ROUNDED"):
                tos[-1] = (tos[-1], True)
            else:
                tos[-1] = (tos[-1], False)
        if p.accept("GIVING"):
            giving = _target_list(p, set())
            return Stmt("ARITH", line, text, {"op": "+", "operands": ops + [t for t, _ in tos], "giving": giving})
        targets = tos
        return Stmt("ARITH", line, text, {"op": "+=", "operands": ops, "targets": targets})
    if p.accept("GIVING"):
        giving = _target_list(p, set())
        return Stmt("ARITH", line, text, {"op": "+", "operands": ops, "giving": giving})
    raise E.ExprError("ADD without TO / GIVING")


def _subtract(p: E.Parser, text: str, line: int) -> Stmt:
    ops = _refs_until(p, {"FROM"})
    if not p.accept("FROM"):
        raise E.ExprError("SUBTRACT without FROM")
    froms = []
    while not p.done() and p.up() != "GIVING":
        o = p.operand()
        froms.append((o, p.accept("ROUNDED")))
    if p.accept("GIVING"):
        return Stmt("ARITH", line, text, {"op": "-", "operands": [froms[0][0], *ops], "giving": _target_list(p, set())})
    return Stmt("ARITH", line, text, {"op": "-=", "operands": ops, "targets": froms})


def _multiply(p: E.Parser, text: str, line: int) -> Stmt:
    a = p.operand()
    if not p.accept("BY"):
        raise E.ExprError("MULTIPLY without BY")
    bys = []
    while not p.done() and p.up() != "GIVING":
        o = p.operand()
        bys.append((o, p.accept("ROUNDED")))
    if p.accept("GIVING"):
        return Stmt("ARITH", line, text, {"op": "*", "operands": [a, bys[0][0]], "giving": _target_list(p, set())})
    return Stmt("ARITH", line, text, {"op": "*=", "operands": [a], "targets": bys})


def _divide(p: E.Parser, text: str, line: int) -> Stmt:
    a = p.operand()
    if p.accept("INTO"):
        intos = []
        while not p.done() and p.up() not in ("GIVING", "REMAINDER"):
            o = p.operand()
            intos.append((o, p.accept("ROUNDED")))
        if p.accept("GIVING"):
            giving = _target_list(p, {"REMAINDER"})
            rem = p.ref() if p.accept("REMAINDER") else None
            return Stmt(
                "ARITH", line, text, {"op": "/", "operands": [intos[0][0], a], "giving": giving, "remainder": rem}
            )
        return Stmt("ARITH", line, text, {"op": "/=", "operands": [a], "targets": intos})
    if p.accept("BY"):
        b = p.operand()
        if not p.accept("GIVING"):
            raise E.ExprError("DIVIDE BY without GIVING")
        giving = _target_list(p, {"REMAINDER"})
        rem = p.ref() if p.accept("REMAINDER") else None
        return Stmt("ARITH", line, text, {"op": "/", "operands": [a, b], "giving": giving, "remainder": rem})
    raise E.ExprError("DIVIDE without INTO / BY")


def _initialize(p: E.Parser, text: str, line: int) -> Stmt:
    refs = []
    while not p.done() and p.up() not in ("REPLACING", "WITH", "ALL", "TO"):
        refs.append(p.ref())
    if not p.done():
        return Stmt("HOLE", line, text, {"why": "INITIALIZE REPLACING / WITH FILLER"})
    return Stmt("INITIALIZE", line, text, {"refs": refs})


def _set(p: E.Parser, text: str, line: int) -> Stmt:
    m = re.fullmatch(r"(?is)\s*SET\s+([A-Z0-9][A-Z0-9-]*)\s+TO\s+ADDRESS\s+OF\s+([A-Z0-9][A-Z0-9-]*)\s*\.?\s*", text)
    if m:  # a pointer set to an item's address: translated only where the pointer is never read (write_only_pointers)
        return Stmt("SET-POINTER", line, text, {"target": m.group(1).upper(), "of": m.group(2).upper()})
    if p.up() == "ADDRESS" or "ADDRESS" in [x.upper() for x in p.t]:
        return Stmt("HOLE", line, text, {"why": "SET ADDRESS OF (pointers)"})
    targets = []
    while not p.done() and p.up() not in ("TO", "UP", "DOWN"):
        targets.append(p.ref())
    if p.accept("TO"):
        if p.up() == "TRUE":
            return Stmt("SET-TRUE", line, text, {"conds": targets})
        if p.up() == "FALSE":
            return Stmt("HOLE", line, text, {"why": "SET ... TO FALSE"})
        return Stmt("SET-TO", line, text, {"targets": targets, "value": p.operand()})
    up = p.take().upper()
    p.accept("BY")
    return Stmt("SET-BY", line, text, {"targets": targets, "by": p.arith(), "up": up == "UP"})


def _perform(p: E.Parser, text: str, line: int) -> Stmt:
    d: dict[str, Any] = {"target": None, "thru": None, "times": None, "until": None, "varying": None,
                         "test_after": False, "inline": False}  # fmt: skip
    if not p.done() and p.up() not in ("UNTIL", "VARYING", "WITH", "TEST") and not (
            (tk := p.peek()) is not None and E._is_number(tk) and p.up(1) == "TIMES") and p.up(1) != "TIMES":  # fmt: skip
        # PERFORM procedure-name [THRU procedure-name]  (or an inline PERFORM n TIMES)
        d["target"] = p.take().upper()
        if p.accept("THRU", "THROUGH"):
            d["thru"] = p.take().upper()
    if p.accept("WITH"):
        pass
    if p.accept("TEST"):
        d["test_after"] = p.take().upper() == "AFTER"
    if not p.done() and p.up(1) == "TIMES":
        d["times"] = p.operand()
        p.take()
    elif p.accept("UNTIL"):
        d["until"] = p.condition()
    elif p.accept("VARYING"):
        var = p.ref()
        p.accept("FROM")
        frm = p.arith()
        p.accept("BY")
        by = p.arith()
        if not p.accept("UNTIL"):
            raise E.ExprError("VARYING without UNTIL")
        until = p.condition()
        if p.up() == "AFTER":
            raise E.ExprError("VARYING ... AFTER")
        d["varying"] = (var, frm, by, until)
    if not p.done():
        raise E.ExprError(f"left over: {' '.join(p.t[p.i :])}")
    return Stmt("PERFORM", line, text, d)


def _goto(p: E.Parser, text: str, line: int) -> Stmt:
    p.accept("TO")
    targets = []
    while not p.done() and p.up() != "DEPENDING":
        targets.append(p.take().upper())
    dep = None
    if p.accept("DEPENDING"):
        p.accept("ON")
        dep = p.ref()
    return Stmt("GOTO", line, text, {"targets": targets, "depending": dep})


def _call(p: E.Parser, text: str, line: int) -> Stmt:
    tok = p.take()
    if tok[:1] not in "'\"":
        return Stmt("HOLE", line, text, {"why": "dynamic CALL"})
    prog = E._unquote(tok).upper()
    args: list[tuple[str, Any]] = []
    mode = "REFERENCE"
    if p.accept("USING"):
        while not p.done() and p.up() not in ("RETURNING", "ON", "EXCEPTION", "OVERFLOW", "NOT"):
            if p.accept("BY"):
                mode = p.take().upper()
                continue
            if p.up() in ("REFERENCE", "CONTENT", "VALUE"):
                mode = p.take().upper()
                continue
            if p.up() == "OMITTED":
                p.take()
                args.append((mode, None))
                continue
            args.append((mode, p.operand()))
    returning = p.ref() if p.accept("RETURNING") else None
    return Stmt("CALL", line, text, {"program": prog, "args": args, "returning": returning})


def _simple(kind: str):
    def f(p: E.Parser, text: str, line: int) -> Stmt:
        rest = [x.upper() for x in p.t[p.i :]]
        if kind == "EXIT" and rest and rest[0] in ("PERFORM", "SECTION"):
            return Stmt("HOLE", line, text, {"why": f"EXIT {rest[0]}"})
        if kind == "STOP" and rest[:1] != ["RUN"]:
            return Stmt("HOLE", line, text, {"why": "STOP literal"})
        return Stmt(kind, line, text, {"what": rest})

    return f


def _open(p: E.Parser, text: str, line: int) -> Stmt:
    files = []
    mode = None
    while not p.done():
        u = p.up()
        if u in ("INPUT", "OUTPUT", "I-O", "EXTEND"):
            mode = p.take().upper()
            continue
        files.append((mode, p.take().upper()))
    return Stmt("OPEN", line, text, {"files": files})


def _close(p: E.Parser, text: str, line: int) -> Stmt:
    files = []
    while not p.done():
        files.append(p.take().upper())
    return Stmt("CLOSE", line, text, {"files": files})


def _read(p: E.Parser, text: str, line: int) -> Stmt:
    f = p.take().upper()
    nxt = p.accept("NEXT", "PREVIOUS")
    p.accept("RECORD")
    into = p.ref() if p.accept("INTO") else None
    key = None
    if p.accept("KEY"):
        p.accept("IS")
        key = p.ref()
    if not p.done():
        raise E.ExprError(f"left over: {' '.join(p.t[p.i :])}")
    return Stmt("READ", line, text, {"file": f, "next": nxt, "into": into, "key": key})


def _write(p: E.Parser, text: str, line: int) -> Stmt:
    rec = p.ref()
    frm = p.operand() if p.accept("FROM") else None
    if not p.done():
        return Stmt("HOLE", line, text, {"why": "WRITE ADVANCING / other phrases"})
    return Stmt("WRITE", line, text, {"record": rec, "from": frm})


def _rewrite(p: E.Parser, text: str, line: int) -> Stmt:
    rec = p.ref()
    frm = p.operand() if p.accept("FROM") else None
    return Stmt("REWRITE", line, text, {"record": rec, "from": frm})


def _start(p: E.Parser, text: str, line: int) -> Stmt:
    f = p.take().upper()
    op, key = "=", None
    if p.accept("KEY"):
        p.accept("IS")
        op, neg = p._rel_op()
        if neg:
            raise E.ExprError("START KEY NOT")
        key = p.ref()
    return Stmt("START", line, text, {"file": f, "op": op, "key": key})


def _accept(p: E.Parser, text: str, line: int) -> Stmt:
    target = p.ref()
    if p.accept("FROM"):
        what = " ".join(x.upper() for x in p.t[p.i :])
        return Stmt("ACCEPT", line, text, {"target": target, "from": what})
    return Stmt("HOLE", line, text, {"why": "ACCEPT from SYSIN / console"})


def _string(p: E.Parser, text: str, line: int) -> Stmt:
    parts = []  # (sources, delimiter) ; delimiter None = SIZE
    pending: list = []
    while not p.done() and p.up() != "INTO":
        if p.accept("DELIMITED"):
            p.accept("BY")
            delim = None if p.accept("SIZE") else p.operand()
            parts.append((pending, delim))
            pending = []
            continue
        pending.append(p.operand())
    if pending:
        parts.append((pending, None))
    if not p.accept("INTO"):
        raise E.ExprError("STRING without INTO")
    into = p.ref()
    pointer = None
    if p.accept("WITH"):
        pass
    if p.accept("POINTER"):
        pointer = p.ref()
    return Stmt("STRING", line, text, {"parts": parts, "into": into, "pointer": pointer})


def _unstring(p: E.Parser, text: str, line: int) -> Stmt:
    """UNSTRING src [DELIMITED BY [ALL] d [OR [ALL] d ...]] INTO t [DELIMITER IN x] [COUNT IN y] [, t ...]
    [WITH POINTER p] [TALLYING IN t]."""
    src = p.ref()
    delims: list = []  # (operand, all)
    if p.accept("DELIMITED"):
        p.accept("BY")
        while True:
            every = p.accept("ALL")
            delims.append((p.operand(), every))
            if not p.accept("OR"):
                break
    if not p.accept("INTO"):
        raise E.ExprError("UNSTRING without INTO")
    intos: list = []  # (target, delimiter-in, count-in)
    while not p.done() and p.up() not in ("WITH", "POINTER", "TALLYING"):
        target = p.ref()
        dl = cnt = None
        if p.accept("DELIMITER"):
            p.accept("IN")
            dl = p.ref()
        if p.accept("COUNT"):
            p.accept("IN")
            cnt = p.ref()
        intos.append((target, dl, cnt))
    pointer = tallying = None
    p.accept("WITH")
    if p.accept("POINTER"):
        pointer = p.ref()
    if p.accept("TALLYING"):
        p.accept("IN")
        tallying = p.ref()
    if not p.done() or not intos:
        raise E.ExprError(f"UNSTRING: left over {' '.join(p.t[p.i :])}")
    return Stmt("UNSTRING", line, text, {"src": src, "delims": delims, "intos": intos, "pointer": pointer,
                                          "tallying": tallying})  # fmt: skip


def _inspect(p: E.Parser, text: str, line: int) -> Stmt:
    """INSPECT target TALLYING ... REPLACING ... | CONVERTING ...: clauses in order, each
    ("tally", counter, mode, pattern | None, bounds) / ("replace", mode, pattern | None, by, bounds) /
    ("convert", from, to, bounds); bounds a list of ("BEFORE" | "AFTER", operand)."""
    target = p.ref()
    clauses: list = []

    def bounds() -> list:
        out = []
        while p.up() in ("BEFORE", "AFTER"):
            which = p.take().upper()
            p.accept("INITIAL")
            out.append((which, p.operand()))
        return out

    if p.accept("CONVERTING"):
        a = p.operand()
        if not p.accept("TO"):
            raise E.ExprError("CONVERTING without TO")
        b = p.operand()
        clauses.append(("convert", a, b, bounds()))
    if p.accept("TALLYING"):
        while not p.done() and p.up() != "REPLACING":
            counter = p.ref()
            if not p.accept("FOR"):
                raise E.ExprError("TALLYING without FOR")
            mode = None
            while not p.done() and p.up() != "REPLACING":
                if p.up() in ("ALL", "LEADING", "CHARACTERS"):
                    mode = p.take().upper()
                    if mode == "CHARACTERS":
                        clauses.append(("tally", counter, mode, None, bounds()))
                    continue
                if mode is None:
                    raise E.ExprError("TALLYING FOR without ALL / LEADING / CHARACTERS")
                # another counter: `cnt FOR ...`
                if p.peek(1) is not None and p.up(1) == "FOR":
                    break
                clauses.append(("tally", counter, mode, p.operand(), bounds()))
    if p.accept("REPLACING"):
        mode = None
        while not p.done():
            if p.up() == "CHARACTERS":
                p.take()
                if not p.accept("BY"):
                    raise E.ExprError("CHARACTERS without BY")
                clauses.append(("replace", "CHARACTERS", None, p.operand(), bounds()))
                continue
            if p.up() in ("ALL", "LEADING", "FIRST"):
                mode = p.take().upper()
            if mode is None:
                raise E.ExprError("REPLACING without ALL / LEADING / FIRST")
            pat = p.operand()
            if not p.accept("BY"):
                raise E.ExprError("REPLACING without BY")
            clauses.append(("replace", mode, pat, p.operand(), bounds()))
    if not p.done() or not clauses:
        raise E.ExprError(f"INSPECT: left over {' '.join(p.t[p.i :])}")
    return Stmt("INSPECT", line, text, {"target": target, "clauses": clauses})


# ---- SORT / MERGE / RELEASE / RETURN (IBM Enterprise COBOL for z/OS 6.4 Language Reference) -------------------
# the words a SORT / MERGE statement's phrases are made of; any other reserved word starts the next statement
_SORT_WORDS = {"ON", "ASCENDING", "DESCENDING", "KEY", "IS", "WITH", "DUPLICATES", "IN", "ORDER", "COLLATING",
               "SEQUENCE", "INPUT", "OUTPUT", "PROCEDURE", "THRU", "THROUGH", "USING", "GIVING", "OF"}  # fmt: skip
# reserved words that begin a statement or end a scope: a SORT / MERGE stops before one (a data name cannot be one)
_STATEMENT_WORDS = {"ACCEPT", "ADD", "ALTER", "CALL", "CANCEL", "CLOSE", "COMPUTE", "CONTINUE", "DELETE", "DISPLAY",
                    "DIVIDE", "ELSE", "ENTRY", "EVALUATE", "EXEC", "EXHIBIT", "EXIT", "GO", "GOBACK", "IF", "INITIALIZE",
                    "INSPECT", "MERGE", "MOVE", "MULTIPLY", "NEXT", "NOT", "OPEN", "PERFORM", "READ", "RELEASE",
                    "RETURN", "REWRITE", "SEARCH", "SET", "SORT", "START", "STOP", "STRING", "SUBTRACT", "UNSTRING",
                    "WHEN", "WRITE", "AT", "INVALID"}  # fmt: skip
_ABBREV_NOT_EQ = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|(\b(?:AND|OR)\s+)NOT\s*=(?![=<>])", re.I)
_SORT_TOKEN = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|[A-Za-z0-9][A-Za-z0-9-]*|\.(?=\s|$)|[^\s]")


def _sort_placeholders(text: str, sorts: dict[int, str]) -> str:
    """Each SORT / MERGE statement in `text` (the PROCEDURE DIVISION) replaced by `CALL 'GGSORTnnnn'` and as many
    \\x01 as it had line ends (parse() puts them back as blank lines); its text kept in `sorts`. A statement runs
    from its verb to the period or the next statement's verb (SORT and MERGE have no conditional phrase and no
    END-SORT)."""
    toks = list(_SORT_TOKEN.finditer(text))
    out, last, i = [], 0, 0
    while i < len(toks):
        t = toks[i].group(0).upper()
        if t in ("SORT", "MERGE") and i + 2 < len(toks) and toks[i + 2].group(0).upper() in (
                "ON", "ASCENDING", "DESCENDING"):  # fmt: skip
            j = i + 2
            while j < len(toks):
                w = toks[j].group(0)
                if w == "." or (w.upper() in _STATEMENT_WORDS and w.upper() not in _SORT_WORDS) or w.upper().startswith(
                        "END-"):  # fmt: skip
                    break
                j += 1
            start, end = toks[i].start(), toks[j - 1].end()
            sorts[len(sorts) + 1] = text[start:end]
            out += [text[last:start], f"CALL 'GGSORT{len(sorts):04d}'" + "\x01" * text[start:end].count("\n")]
            last, i = end, j
            continue
        i += 1
    return "".join(out) + text[last:]


_FUNCTION = re.compile(r"\bFUNCTION\s+[A-Z0-9-]+\s*(?=\()", re.I)


def _group_end(text: str, at: int) -> int:
    """The index of the `)` closing the `(` at `at` (-1: unclosed)."""
    depth = 0
    for k in range(at, len(text)):
        depth += {"(": 1, ")": -1}.get(text[k], 0)
        if depth == 0:
            return k
    return -1


def _top_colons(text: str, at: int, end: int) -> list[int]:
    depth, out = 0, []
    for k in range(at, end + 1):
        depth += {"(": 1, ")": -1}.get(text[k], 0)
        if text[k] == ":" and depth == 1:
            out.append(k)
    return out


def _function_refmods(text: str) -> str:
    """#4462: `text` with each reference modification of an intrinsic function written the way the grammar reads
    it (it has none: estate-crucible KØBREG's `FUNCTION CURRENT-DATE (1:4)` refused the program), at the same
    length: `FUNCTION F (1:4)` -> `FUNCTION F (1,4)` and `FUNCTION F(A) (1:4)` -> `FUNCTION F(A, 1,4)` (a list of
    arguments). Only the grammar sees it; the statement's text, which expr reads, is the source's."""
    bare = _outside_literals(text)
    out = list(text)
    for m in _FUNCTION.finditer(bare):
        p = m.end()
        q = _group_end(bare, p)
        if q < 0:
            continue
        colons = _top_colons(bare, p, q)
        if not colons:  # the arguments; a reference modification may follow
            p2 = q + 1
            while p2 < len(bare) and bare[p2] == " ":
                p2 += 1
            q2 = _group_end(bare, p2) if p2 < len(bare) and bare[p2] == "(" else -1
            colons = _top_colons(bare, p2, q2) if q2 > 0 else []
            if not colons:
                continue
            out[q], out[p2] = ",", " "
        for k in colons:
            out[k] = ","
    return "".join(out)


def _entry_placeholders(text: str, entries: dict[int, str]) -> str:
    """#4462: each ENTRY statement in `text` (the PROCEDURE DIVISION: `ENTRY literal [USING ...]`, up to the period
    or the next statement's verb) replaced by `CALL 'GGENTRnnnn'` and \\x01 per line end, as _sort_placeholders."""
    toks = list(_SORT_TOKEN.finditer(text))
    out, last, i = [], 0, 0
    while i < len(toks):
        if toks[i].group(0).upper() == "ENTRY" and i + 1 < len(toks) and toks[i + 1].group(0)[:1] in "'\"":
            j = i + 2
            while j < len(toks):
                w = toks[j].group(0)
                if w == "." or (w.upper() in _STATEMENT_WORDS and w.upper() != "USING") or w.upper().startswith("END-"):
                    break
                j += 1
            start, end = toks[i].start(), toks[j - 1].end()
            entries[len(entries) + 1] = text[start:end]
            out += [text[last:start], f"CALL 'GGENTR{len(entries):04d}'" + "\x01" * text[start:end].count("\n")]
            last, i = end, j
            continue
        i += 1
    return "".join(out) + text[last:]


def _exhibit_placeholders(text: str, exhibits: dict[int, str]) -> str:
    """#4462: each EXHIBIT statement in `text` (`EXHIBIT {NAMED | CHANGED NAMED | CHANGED} operand ...`, up to the
    period or the next statement's verb) replaced by `CALL 'GGEXHBnnnn'` and \\x01 per line end, as
    _sort_placeholders."""
    toks = list(_SORT_TOKEN.finditer(text))
    out, last, i = [], 0, 0
    while i < len(toks):
        if toks[i].group(0).upper() == "EXHIBIT" and i + 1 < len(toks) and toks[i + 1].group(0).upper() in (
                "NAMED", "CHANGED"):  # fmt: skip
            j = i + 2
            while j < len(toks):
                w = toks[j].group(0)
                if w == "." or w.upper() in _STATEMENT_WORDS or w.upper().startswith("END-"):
                    break
                j += 1
            start, end = toks[i].start(), toks[j - 1].end()
            exhibits[len(exhibits) + 1] = text[start:end]
            out += [text[last:start], f"CALL 'GGEXHB{len(exhibits):04d}'" + "\x01" * text[start:end].count("\n")]
            last, i = end, j
            continue
        i += 1
    return "".join(out) + text[last:]


_MARKUP_FIGURATIVE = {"ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES", "LOW-VALUE", "LOW-VALUES", "HIGH-VALUE",
                      "HIGH-VALUES"}  # fmt: skip


def _markup_placeholders(text: str, markups: dict[int, str]) -> str:
    """#4462: each JSON / XML PARSE / GENERATE statement and each `SET pointer ... TO ENTRY x` in `text` replaced by `CALL 'GGMKUPnnnn'` and \\x01 per line
    end, as _sort_placeholders. A statement runs from its verb to its END-JSON / END-XML (when one comes before the
    period), else to the period, the next statement's verb, an END-x or ELSE -- its [NOT] ON EXCEPTION phrases' own
    statements included (after EXCEPTION only the period, END-x, ELSE or a WHEN ends it). `SUPPRESS ... WHEN SPACES`
    is the statement's own WHEN."""
    toks = list(_SORT_TOKEN.finditer(text))
    words = [t.group(0).upper() for t in toks]

    def starts(k: int) -> bool:
        return words[k] in ("JSON", "XML") and k + 1 < len(words) and words[k + 1] in ("PARSE", "GENERATE")

    out, last, i = [], 0, 0
    while i < len(toks):
        if words[i] == "SET":  # SET p ... TO ENTRY {literal | identifier}
            j = i + 1
            while j < len(words) and words[j] not in ("TO", ".") and words[j] not in _STATEMENT_WORDS:
                j += 1
            if j + 2 < len(words) and words[j] == "TO" and words[j + 1] == "ENTRY" and words[j + 2] != ".":
                start, end = toks[i].start(), toks[j + 2].end()
                markups[len(markups) + 1] = text[start:end]
                out += [text[last:start], f"CALL 'GGMKUP{len(markups):04d}'" + "\x01" * text[start:end].count("\n")]
                last, i = end, j + 3
                continue
        if not starts(i):
            i += 1
            continue
        end_word = "END-" + words[i]
        period = next((k for k in range(i, len(words)) if words[k] == "."), len(words))
        closed = end_word in words[i + 2 : period]
        j, depth, in_exc, suppress = i + 2, 0, False, False
        while j < len(toks):
            u = words[j]
            if u == ".":
                break
            if closed:  # to the END-JSON / END-XML matching it
                if starts(j) and words[j] == words[i]:
                    depth += 1
                elif u == end_word:
                    if depth == 0:
                        j += 1
                        break
                    depth -= 1
                j += 1
                continue
            nxt = words[j + 1] if j + 1 < len(words) else ""
            if u == "WHEN" and suppress and nxt in _MARKUP_FIGURATIVE:
                j += 2
                continue
            if u.startswith("END-") or u in ("ELSE", "WHEN"):
                break
            if u == "EXCEPTION" or (u == "NOT" and nxt in ("ON", "EXCEPTION")):
                in_exc = True
            elif u == "SUPPRESS":
                suppress = True
            elif not in_exc and u in _STATEMENT_WORDS:
                break
            j += 1
        start, end = toks[i].start(), toks[j - 1].end()
        markups[len(markups) + 1] = text[start:end]
        out += [text[last:start], f"CALL 'GGMKUP{len(markups):04d}'" + "\x01" * text[start:end].count("\n")]
        last, i = end, j
    return "".join(out) + text[last:]


def _markup(text: str, line: int) -> Stmt:
    """JSON PARSE / JSON GENERATE (Enterprise COBOL 6.1+) and XML PARSE / XML GENERATE: a hole by name. Not modelled:
    their name matching and conversions (JSON PARSE INTO a group, NAME OF, SUPPRESS, CONVERTING), the special
    registers they set (JSON-CODE, JSON-STATUS, XML-CODE, XML-EVENT ...), XML PARSE's processing procedure and the
    encodings and code pages of the text they read and write."""
    if text.split()[0].upper() == "SET":
        return Stmt("HOLE", line, text, {"why": "SET TO ENTRY: procedure / function pointers are not modelled"})
    verb = " ".join(text.split()[:2]).upper()
    era = "Enterprise COBOL 6.1+" if verb.startswith("JSON") else "Enterprise COBOL"
    return Stmt("HOLE", line, text, {"why": f"{verb} ({era}): not modelled"})


def _exhibit(text: str, line: int) -> Stmt:
    """EXHIBIT {NAMED | CHANGED NAMED | CHANGED} {identifier | literal} ... (IBM OS/VS COBOL, a debugging statement
    Enterprise COBOL dropped). data: named, changed, operands [(the operand as written, operand)]. Each execution of
    EXHIBIT NAMED displays one line: each identifier as `name = value`, each literal as its value, separated by a
    space (GnuCOBOL's output; IBM: each identifier "followed by an equal sign and its current value", on one line in
    the order written). EXHIBIT CHANGED displays only what changed since the statement last ran: not modelled."""
    p = E.Parser(E.tokenize(text)[1:])
    changed = bool(p.accept("CHANGED"))
    named = bool(p.accept("NAMED"))
    ops = []
    try:
        while not p.done():
            at = p.i
            o = p.operand()
            ops.append((" ".join(p.t[at : p.i]), o))
    except E.ExprError as e:
        return Stmt("HOLE", line, text, {"why": f"EXHIBIT: {e}"})
    if changed:
        return Stmt("HOLE", line, text, {"why": "EXHIBIT CHANGED (OS/VS COBOL: display on change) not modelled"})
    return Stmt("EXHIBIT", line, text, {"named": named, "changed": changed, "operands": ops})


def _entry(text: str, line: int) -> Stmt:
    """ENTRY literal [USING [BY REFERENCE | BY VALUE] identifier ...]. data: name, using [Ref]."""
    p = E.Parser(E.tokenize(text)[1:])
    name = E._unquote(p.take())
    using = []
    if p.accept("USING"):
        while p.peek() is not None:
            if p.accept("BY", "REFERENCE", "VALUE", "CONTENT"):
                continue
            using.append(p.ref())
    return Stmt("ENTRY", line, text, {"name": name, "using": using})


def _proc_range(p: E.Parser) -> tuple[str, str | None]:
    """PROCEDURE [IS] name [THRU | THROUGH name]."""
    p.accept("PROCEDURE")
    p.accept("IS")
    a = p.take().upper()
    b = p.take().upper() if p.accept("THRU", "THROUGH") else None
    return a, b


def _sort_merge(text: str, line: int) -> Stmt:
    """SORT file [ON] {ASCENDING | DESCENDING} [KEY] [IS] key ... [WITH DUPLICATES [IN ORDER]]
    [COLLATING SEQUENCE [IS] alphabet] {INPUT PROCEDURE [IS] p [THRU q] | USING file ...}
    {OUTPUT PROCEDURE [IS] p [THRU q] | GIVING file ...}; MERGE the same without DUPLICATES and INPUT PROCEDURE.
    data: file, keys [(Ref, ascending)], duplicates, collating, using [file], input (p, q), giving [file],
    output (p, q)."""
    toks = E.tokenize(text)
    verb = toks[0].upper()
    p = E.Parser(toks[1:])
    try:
        d: dict[str, Any] = {"file": p.take().upper(), "keys": [], "duplicates": False, "collating": None,
                             "using": [], "input": None, "giving": [], "output": None}  # fmt: skip
        while p.up() in ("ON", "ASCENDING", "DESCENDING"):
            p.accept("ON")
            asc = p.take().upper() == "ASCENDING"
            p.accept("KEY")
            p.accept("IS")
            n = len(d["keys"])
            while not p.done() and p.up() not in _SORT_WORDS:
                d["keys"].append((p.ref(), asc))
            if len(d["keys"]) == n:
                raise E.ExprError(f"{verb}: a KEY phrase with no key")
        if not d["keys"]:
            raise E.ExprError(f"{verb}: no KEY phrase")
        if p.up() in ("WITH", "DUPLICATES"):
            p.accept("WITH")
            p.take()
            p.accept("IN")
            p.accept("ORDER")
            d["duplicates"] = True
        if p.up() in ("COLLATING", "SEQUENCE"):
            p.accept("COLLATING")
            p.take()
            p.accept("IS")
            d["collating"] = p.take().upper()
        if p.accept("USING"):
            while not p.done() and p.up() not in _SORT_WORDS:
                d["using"].append(p.take().upper())
        elif p.accept("INPUT"):
            d["input"] = _proc_range(p)
        if p.accept("GIVING"):
            while not p.done() and p.up() not in _SORT_WORDS:
                d["giving"].append(p.take().upper())
        elif p.accept("OUTPUT"):
            d["output"] = _proc_range(p)
        if not p.done():
            raise E.ExprError(f"{verb}: left over {' '.join(p.t[p.i :])}")
        if verb == "SORT" and not (d["using"] or d["input"] or d["giving"] or d["output"]):
            raise E.ExprError("SORT of a table (format 2) not modelled")
        if not (d["using"] or d["input"]) or not (d["giving"] or d["output"]):
            raise E.ExprError(f"{verb}: no input or no output phrase")
        if verb == "MERGE" and (d["duplicates"] or d["input"] or len(d["using"]) < 2):
            raise E.ExprError("MERGE takes two or more USING files and no DUPLICATES / INPUT PROCEDURE")
    except E.ExprError as e:
        return Stmt("HOLE", line, text, {"why": str(e)})
    return Stmt(verb, line, text, d)


def _release(p: E.Parser, text: str, line: int) -> Stmt:
    """RELEASE record [FROM identifier]."""
    rec = p.ref()
    frm = p.operand() if p.accept("FROM") else None
    if not p.done():
        raise E.ExprError(f"left over: {' '.join(p.t[p.i :])}")
    return Stmt("RELEASE", line, text, {"record": rec, "from": frm})


def _return(p: E.Parser, text: str, line: int) -> Stmt:
    """RETURN file [RECORD] [INTO identifier] (AT END / NOT AT END are phrases)."""
    f = p.take().upper()
    p.accept("RECORD")
    into = p.ref() if p.accept("INTO") else None
    if not p.done():
        raise E.ExprError(f"left over: {' '.join(p.t[p.i :])}")
    return Stmt("RETURN", line, text, {"file": f, "into": into})


_PARSERS = {
    "RELEASE": _release, "RETURN": _return,
    "MOVE": _move, "DISPLAY": _display, "COMPUTE": _compute, "ADD": _add, "SUBTRACT": _subtract,
    "MULTIPLY": _multiply, "DIVIDE": _divide, "INITIALIZE": _initialize, "SET": _set, "PERFORM": _perform,
    "GO": _goto, "CALL": _call, "EXIT": _simple("EXIT"), "GOBACK": _simple("GOBACK"), "STOP": _simple("STOP"),
    "CONTINUE": _simple("CONTINUE"), "NEXT": _simple("NEXT-SENTENCE"), "OPEN": _open, "CLOSE": _close,
    "READ": _read, "WRITE": _write, "REWRITE": _rewrite, "START": _start, "ACCEPT": _accept, "STRING": _string, "UNSTRING": _unstring,
    "INSPECT": _inspect,
}  # fmt: skip


def walk(stmts: list):
    for s in stmts:
        yield s
        yield from walk(s.body)
        yield from walk(s.orelse)
        for _, b in s.whens:
            yield from walk(b)
        for b in s.phrases.values():
            yield from walk(b)
