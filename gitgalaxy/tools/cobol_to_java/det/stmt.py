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
from gitgalaxy.tools.cobol_to_java.det.source import Line, as_fixed


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
                  "END_RETURN", "END_SEARCH", "END_ACCEPT", "END_DISPLAY"}  # fmt: skip


class _Frame:
    def __init__(self, kind: str, node: Stmt | None, target: list):
        self.kind, self.node, self.target = kind, node, target
        self.has_else = False


def parse(lines: list[Line]) -> Procedure:
    from tree_sitter_language_pack import get_parser

    text = as_fixed(lines)
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
        execs[len(execs) + 1] = mm.group(0)
        return f"CALL 'GGEXEC{len(execs):04d}'"

    proc_text = re.sub(r"\bEXEC(?:UTE)?\s+(CICS|SQL|DLI)\b.*?\bEND-EXEC\b", ph, text[m.start() :], flags=re.S | re.I)
    proc_text = re.sub(r"\bNOT=", "NOT =", proc_text, flags=re.I)  # the grammar wants a space after NOT
    pre = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. GGDET.\n"
    src = (pre + "       PROCEDURE DIVISION.\n" + proc_text[len(header) :].lstrip("\n")).encode("latin-1")
    # line numbers: map back to the expanded program's lines
    base_line = text[: m.start()].count("\n") + 1 + header.count("\n") - 2
    root = _parser_cache(get_parser).parse(src).root_node
    prog = next((c for c in root.children if c.type == "program_definition"), root)
    pd = next((c for c in prog.children if c.type == "procedure_division"), None)
    if pd is None:
        raise E.ExprError("the PROCEDURE DIVISION does not parse")

    def origin(node) -> int:
        k = node.start_point[0] - 3 + base_line  # 3 synthetic lines before
        return lines[k].line if 0 <= k < len(lines) else node.start_point[0] + 1

    paragraphs: list[Paragraph] = [Paragraph("(MAIN)", None, 0)]
    section: str | None = None
    stack: list[_Frame] = [_Frame("PARA", None, paragraphs[0].body)]

    def close_all():
        del stack[1:]

    def node_text(n) -> str:
        return src[n.start_byte : n.end_byte].decode("latin-1")

    for n in pd.children:
        t = n.type
        if t in (".",):
            continue
        if t == "ERROR":
            stack[-1].target.append(Stmt("HOLE", origin(n), node_text(n), {"why": "does not parse"}))
            continue
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
            f.target = f.node.orelse
            s = Stmt("IF", origin(n), node_text(n), {"cond": _cond(re.sub(r"(?i)^\s*ELSE\s+IF", "", node_text(n)))})
            f.target.append(s)
            stack.append(_Frame("IF", s, s.body))
            continue
        if t == "else_header":
            f = _pop_to_if(stack)
            f.has_else = True
            f.target = f.node.orelse
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
        if t in ("when", "when_other"):
            f = _pop_to(stack, "EVALUATE")
            body: list = []
            if t == "when_other":
                f.node.whens.append((None, body))
            else:
                conds = _whens(node_text(n), len(f.node.data["subjects"]))
                # stacked WHENs with no statements between share one body
                if f.node.whens and not f.node.whens[-1][1] and f.node.whens[-1][0] is not None:
                    prev = f.node.whens.pop()
                    conds = prev[0] + conds
                f.node.whens.append((conds, body))
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
            owner = next((x for x in reversed(stack[-1].target) if x.kind not in ("HOLE",)), None)
            if owner is None:
                stack[-1].target.append(Stmt("HOLE", origin(n), node_text(n), {"why": "phrase with no statement"}))
                continue
            body = owner.phrases.setdefault(name, [])
            stack.append(_Frame("PHRASE", owner, body))
            continue
        if t in STATEMENT_ENDS:
            while stack[-1].kind == "PHRASE":
                stack.pop()
            continue
        if t.endswith("_statement") or t.startswith("perform_statement"):
            s = _statement(node_text(n), origin(n))
            if s.kind == "CALL" and re.match(r"GGEXEC\d{4}$", s.data.get("program") or ""):
                s = Stmt("EXEC", s.line, execs[int(s.data["program"][6:])])
            stack[-1].target.append(s)
            continue
        stack[-1].target.append(Stmt("HOLE", origin(n), node_text(n), {"why": f"grammar node {t}"}))
    if not paragraphs[0].body:
        paragraphs.pop(0)
    return Procedure(paragraphs, execs, using)


_PARSER = None


def _parser_cache(get_parser):
    global _PARSER
    if _PARSER is None:
        _PARSER = get_parser("cobol")
    return _PARSER


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


def _whens(text: str, subjects: int) -> list:
    """One WHEN node may hold several stacked WHENs: [[object per subject], ...]."""
    out = []
    for w in re.split(r"(?i)\bWHEN\b", text)[1:]:
        objs = []
        for part in re.split(r"(?i)\bALSO\b", w.strip()):
            p = part.strip()
            objs.append(_when_object(p))
        out.append(objs)
    return out


def _when_object(p: str):
    up = p.upper()
    if up == "ANY":
        return ("ANY",)
    if up in ("TRUE", "FALSE"):
        return (up,)
    neg = False
    if up.startswith("NOT "):
        neg, p = True, p[4:]
    m = re.match(r"(.+?)\s+(?:THRU|THROUGH)\s+(.+)$", p, re.I)
    try:
        if m:
            return ("RANGE", E.parse_arith(m.group(1)), E.parse_arith(m.group(2)), neg)
        try:
            return ("VALUE", E.parse_arith(p), neg)
        except E.ExprError:
            return ("COND", E.parse_condition(p), neg)
    except E.ExprError:
        try:
            return ("COND", E.parse_condition(p), neg)
        except E.ExprError as e:
            return ("UNPARSED", p, str(e))


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
        tos = []
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
            E._is_number(p.peek()) and p.up(1) == "TIMES"):  # fmt: skip
        # PERFORM procedure-name [THRU procedure-name]  (or an inline PERFORM n TIMES)
        if p.up(1) != "TIMES":
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
    args, mode = [], "REFERENCE"
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


def _inspect(p: E.Parser, text: str, line: int) -> Stmt:
    target = p.ref()
    rest = " ".join(p.t[p.i :])
    m = re.match(r"(?i)CONVERTING\s+(\S+)\s+TO\s+(\S+)$", rest)
    if m:
        a, b = E.Parser([m.group(1)]).operand(), E.Parser([m.group(2)]).operand()
        return Stmt("INSPECT", line, text, {"target": target, "converting": (a, b)})
    m = re.match(r"(?i)REPLACING\s+ALL\s+(\S+)\s+BY\s+(\S+)$", rest)
    if m:
        a, b = E.Parser([m.group(1)]).operand(), E.Parser([m.group(2)]).operand()
        return Stmt("INSPECT", line, text, {"target": target, "replacing_all": (a, b)})
    m = re.match(r"(?i)TALLYING\s+(\S+)\s+FOR\s+(ALL|LEADING)\s+(\S+)$", rest)
    if m:
        cnt = E.Parser([m.group(1)]).ref()
        what = E.Parser([m.group(3)]).operand()
        return Stmt("INSPECT", line, text, {"target": target, "tallying": (cnt, m.group(2).upper(), what)})
    return Stmt("HOLE", line, text, {"why": "INSPECT form not modelled"})


_PARSERS = {
    "MOVE": _move, "DISPLAY": _display, "COMPUTE": _compute, "ADD": _add, "SUBTRACT": _subtract,
    "MULTIPLY": _multiply, "DIVIDE": _divide, "INITIALIZE": _initialize, "SET": _set, "PERFORM": _perform,
    "GO": _goto, "CALL": _call, "EXIT": _simple("EXIT"), "GOBACK": _simple("GOBACK"), "STOP": _simple("STOP"),
    "CONTINUE": _simple("CONTINUE"), "NEXT": _simple("NEXT-SENTENCE"), "OPEN": _open, "CLOSE": _close,
    "READ": _read, "WRITE": _write, "REWRITE": _rewrite, "START": _start, "ACCEPT": _accept, "STRING": _string,
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
