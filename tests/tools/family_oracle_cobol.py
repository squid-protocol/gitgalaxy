"""COBOL oracle for the keyword-family validity tool (#8863): the translator's own statement parser, not a tree-sitter node map.

A COBOL "function" is a paragraph (the engine's `func_start` anchors paragraphs and sections). `gitgalaxy/tools/cobol_to_java/det/stmt.py`
parses the PROCEDURE DIVISION into paragraphs of `Stmt` nodes; this oracle counts the verbs and conditions each paragraph holds, as the
family contracts (gitgalaxy/standards/signal_contracts.py) read for COBOL. The parser is the deterministic translator's, which is the repo's
own tool, so it is not independent of the project; it is independent of the engine's regexes, which is what the families are scored against.

Readings (written before the first run; the contract is silent where noted):
  branch        IF, each EVALUATE / SEARCH WHEN arm (OTHER is the default arm, branch contract C3), a loop (PERFORM UNTIL / VARYING / n TIMES),
                GO TO ... DEPENDING ON. A bare `PERFORM para` is a call, not a decision (contract corollary 3). An exception phrase
                (AT END, INVALID KEY, ON SIZE ERROR, ON EXCEPTION, ON OVERFLOW) is a handler, not a decision (corollary 1, as `catch`).
  short_circuit counted (AND / OR in an IF, EVALUATE, SEARCH or PERFORM UNTIL / VARYING condition) but NOT scored: COBOL has no `short_circuit`
                rule, so its chart cell stays N/A (a stated-absence decision, not a measured zero).
  debug_prints  DISPLAY and EXHIBIT (console output).
  io            OPEN, READ, WRITE, REWRITE, DELETE, START on a file; EXEC SQL / DLI and the EXEC CICS file, browse and queue commands. CLOSE is
                cleanup's (io contract C2).
  args          not scored: a paragraph has no parameters; USING belongs to the program's PROCEDURE DIVISION header.
A statement the parser could not model (kind HOLE) still counts by its leading verb, so a hole does not hide an I/O verb. A program the parser
refuses (national text, several programs, an unmodelled construct) indexes to nothing, and its functions are reported as unmatched.
"""

from __future__ import annotations

import collections
import dataclasses
import re
from typing import Any

from family_oracle import Family

_IO_VERBS = frozenset({"OPEN", "READ", "WRITE", "REWRITE", "DELETE", "START"})  # CLOSE is cleanup's hit (io contract C2)
_EXEC_IO = re.compile(
    r"EXEC\s+(?:SQL|DLI)\b|EXEC\s+CICS\s+(?:READ|WRITE|REWRITE|DELETE|UNLOCK|STARTBR|READNEXT|READPREV|ENDBR|RESETBR|READQ|WRITEQ|DELETEQ)\b",
    re.I,
)
_PRINT_VERBS = frozenset({"DISPLAY", "EXHIBIT"})

FAMILIES: tuple[Family, ...] = (
    Family(
        "struct_branch",
        "branch",
        "decision points: IF, EVALUATE / SEARCH WHEN arms, PERFORM UNTIL / VARYING / TIMES loops, GO TO DEPENDING (not a bare PERFORM, not an AT END / INVALID KEY / SIZE ERROR phrase)",
        "branch",
    ),
    Family("state_print_hits", "print", "console output: DISPLAY, EXHIBIT", "debug_prints"),
    Family("arch_io", "io", "file verbs OPEN, READ, WRITE, REWRITE, DELETE, START and EXEC SQL / DLI / CICS file and queue commands (CLOSE is cleanup's, io contract C2)", "io"),
)


def _boolean_ops(obj: Any) -> int:
    """And / Or nodes anywhere inside a parsed condition (walks dataclass fields, lists and tuples)."""
    from gitgalaxy.tools.cobol_to_java.det import expr as E

    if isinstance(obj, (E.And, E.Or)):
        return 1 + _boolean_ops(obj.left) + _boolean_ops(obj.right)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return sum(_boolean_ops(getattr(obj, f.name)) for f in dataclasses.fields(obj))
    if isinstance(obj, (list, tuple)):
        return sum(_boolean_ops(x) for x in obj)
    return 0


def _verb(stmt) -> str:
    if stmt.kind != "HOLE":
        return stmt.kind
    words = (stmt.text or "").split(None, 1)
    return words[0].upper().rstrip(".") if words else "HOLE"


class CobolOracle:
    lang = "cobol"
    exts = (".cbl", ".cob", ".cobol", ".cpy")
    families = FAMILIES

    def index(self, text: str) -> dict:
        """(paragraph name, line) -> Paragraph. A source the translator refuses indexes to nothing."""
        from gitgalaxy.tools.cobol_to_java.det import source as SRC
        from gitgalaxy.tools.cobol_to_java.det import stmt as S

        try:
            proc = S.parse(SRC.logical_lines(text.splitlines(), "family_oracle"))
        except ImportError:
            raise
        except Exception:  # a refusal by name (ExprError, NotCobol, ...) is "no oracle for this program"  # noqa: BLE001
            return {}
        out: dict = {}
        for para in proc.paragraphs:
            if para.name.startswith("(") or para.line <= 0:  # the pseudo-paragraph before the first label
                continue
            out.setdefault((para.name, para.line), para)
            out.setdefault((para.name.upper(), para.line), para)
        return out

    def count(self, para) -> tuple[collections.Counter, dict]:
        n: collections.Counter[str] = collections.Counter()
        tokens: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)

        def add(key: str, tok: str, k: int = 1) -> None:
            if k:
                n[key] += k
                tokens[key][tok] += k

        def walk(body: list) -> None:
            for s in body:
                kind = _verb(s)
                data = s.data
                if kind == "IF":
                    add("branch", "IF")
                    add("short_circuit", "AND/OR", _boolean_ops(data.get("cond")))
                elif kind == "EVALUATE":
                    for conds, _ in s.whens:
                        add("branch", "WHEN")
                        add("short_circuit", "AND/OR", _boolean_ops(conds))
                elif kind == "SEARCH":
                    for conds, _ in s.whens:
                        add("branch", "WHEN")
                        add("short_circuit", "AND/OR", _boolean_ops(conds))
                elif kind == "PERFORM":
                    loop = data.get("until") or data.get("varying") or data.get("times")
                    if loop is not None:
                        add("branch", "PERFORM loop")
                        add("short_circuit", "AND/OR", _boolean_ops(data.get("until")) + _boolean_ops(data.get("varying")))
                elif kind in ("GOTO", "GO") and data.get("depending"):
                    add("branch", "GO TO DEPENDING")
                elif kind in _PRINT_VERBS:
                    add("print", kind)
                elif kind in _IO_VERBS:
                    add("io", kind)
                elif kind == "EXEC" and _EXEC_IO.match(s.text or ""):
                    add("io", "EXEC")
                walk(s.body)
                walk(s.orelse)
                for _, wb in s.whens:
                    walk(wb)
                for pb in s.phrases.values():
                    walk(pb)

        walk(para.body)
        return n, tokens


_ORACLE = CobolOracle()


def get_oracle() -> CobolOracle:
    return _ORACLE
