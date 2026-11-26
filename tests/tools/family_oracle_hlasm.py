"""HLASM oracle for the keyword-family validity tool (#8863): the deterministic translator's assembler statement reader, not a tree-sitter node map.

An HLASM "function" is what the engine's `func_start` anchors: a control section (`name CSECT | RSECT | START | DFHEIENT`) or an in-file macro
(the prototype statement after `MACRO`, keyed by the MACRO card's line as the engine's match starts there). `gitgalaxy/tools/cobol_to_java/det/hlasm.py::statements` reads the source into label / operation / operand
statements (column-72 continuations joined, comment cards dropped); this oracle groups them into units and counts, per unit, the operations the family
contracts (gitgalaxy/standards/signal_contracts.py) name. The reader is the repo's own tool, so it is not independent of the project; it is
independent of the engine's per-family regexes, which is what the families are scored against.

Readings (written before the first run):
  branch          a CONDITIONAL branch: the extended mnemonics BE BNE BH BNH BL BNL BZ BNZ BP BNP BM BNM BO BNO (and the R forms), the relative J forms,
                  BC / BCR / BRC / BRCL / JC with a mask of 1-14 (mask 0 never branches, mask 15 always does: unconditional, a jump or a return, not a
                  decision), BCT / BCTR / BCTG / BCTGR / BRCT / BRCTG (a counting loop; `BCTR r,0` is a decrement, no branch), BXH / BXLE / BRXH / BRXLE
                  and the compare-and-branch family (CIJ CRJ CIB CRB and the CG / CL / CLG forms). BAS / BALR / BR / B are calls and jumps, not decisions.
  io              EXEC CICS file, browse, queue, spool and counter commands; EXEC SQL except INCLUDE / DECLARE / WHENEVER; EXEC DLI; CALL ASMTDLI /
                  AIBTDLI / CEETDLI; the access-method macros OPEN, GET, PUT, READ, WRITE, CHECK, POINT. CLOSE is cleanup's (io contract C2).
  print           WTO and WTOR (the operator console).
  cast            CVB / CVD (and the Y and G forms) and PACK / UNPK (and the PKA / PKU / UNPKA / UNPKU forms): format conversions.
  bailout         ABEND and EXEC CICS ABEND.
A program the reader refuses (CardDemo's MVSWAIT) (a continuation with text before column 16 outside EXEC CICS) indexes to nothing and its units are reported as unmatched.
"""

from __future__ import annotations

import collections
import re

from family_oracle import Family

_COND_EXT = (
    "E", "NE", "H", "NH", "L", "NL", "Z", "NZ", "P", "NP", "M", "NM", "O", "NO",
)  # fmt: skip
_EXT_BRANCH = frozenset({f"B{c}" for c in _COND_EXT} | {f"B{c}R" for c in _COND_EXT} | {f"J{c}" for c in _COND_EXT})
_MASKED = frozenset({"BC", "BCR", "BRC", "BRCL", "JC", "JLC"})
_COUNTING = frozenset({"BCT", "BCTR", "BCTG", "BCTGR", "BRCT", "BRCTG"})
_INDEX = frozenset({"BXH", "BXLE", "BXHG", "BXLEG", "BRXH", "BRXLE", "BRXHG", "BRXLG"})
_COMPARE_BRANCH = frozenset(
    {f"{c}{k}" for c in ("C", "CG", "CL", "CLG") for k in ("IJ", "RJ", "IB", "RB")}
)  # fmt: skip
_SECTION_OPS = frozenset({"CSECT", "RSECT", "START", "DFHEIENT"})
_ACCESS_METHOD = frozenset({"OPEN", "GET", "PUT", "READ", "WRITE", "CHECK", "POINT"})
_CALL_TARGETS = ("ASMTDLI", "AIBTDLI", "CEETDLI")
_PRINT_OPS = frozenset({"WTO", "WTOR"})
_CAST_OPS = frozenset(
    {"CVB", "CVBY", "CVBG", "CVD", "CVDY", "CVDG", "PACK", "UNPK", "PKA", "PKU", "UNPKA", "UNPKU"}
)  # fmt: skip
_CICS_IO = re.compile(
    r"CICS\s+(?:(?:READQ|WRITEQ|DELETEQ)\b|READ\b|WRITE\b|REWRITE\b|DELETE\b|UNLOCK\b|STARTBR\b|READNEXT\b|READPREV\b|ENDBR\b|RESETBR\b"
    r"|SPOOL(?:OPEN|READ|WRITE|CLOSE)\b|(?:DEFINE|GET|QUERY|UPDATE|REWIND|DELETE)\s+D?COUNTER\b)",
    re.I,
)
_SQL_NOT_IO = re.compile(r"SQL\s+(?:INCLUDE|DECLARE|WHENEVER|BEGIN\s+DECLARE|END\s+DECLARE)\b", re.I)

FAMILIES: tuple[Family, ...] = (
    Family(
        "struct_branch",
        "branch",
        "conditional branches: extended BE..BNO / JE..JNO, BC / BCR / BRC with a mask of 1-14, counting (BCT) and index (BXH / BXLE) loops, compare-and-branch (not B, BR, BAS, BALR, a mask-15 BC or `BCTR r,0`)",
        "branch",
    ),
    Family(
        "arch_io",
        "io",
        "EXEC CICS file / queue / counter commands, EXEC SQL (not INCLUDE / DECLARE / WHENEVER), EXEC DLI, CALL ASMTDLI / AIBTDLI / CEETDLI, access-method macros OPEN GET PUT READ WRITE CHECK POINT (CLOSE is cleanup's)",
        "io",
    ),
    Family("state_print_hits", "print", "operator console output: WTO, WTOR", "debug_prints"),
    Family(
        "state_cast_hits",
        "cast",
        "format conversions: CVB / CVD and their Y / G forms, PACK / UNPK and the PKA / PKU / UNPKA / UNPKU forms",
        "explicit_casts",
    ),
    Family("state_bailout_hits", "bailout", "ABEND and EXEC CICS ABEND", "panics_and_aborts"),
)


def _mask(operands: str) -> str:
    return operands.split(",", 1)[0].strip()


def _is_branch(op: str, operands: str) -> bool:
    if op in _EXT_BRANCH or op in _COUNTING or op in _INDEX or op in _COMPARE_BRANCH:
        if op in ("BCTR", "BCTGR"):  # r2 = 0: a decrement that never branches
            parts = operands.split(",")
            return len(parts) < 2 or parts[1].strip() != "0"
        return True
    if op in _MASKED:
        m = _mask(operands)
        return not (m.isdigit() and int(m) in (0, 15))  # a symbolic mask is a real test
    return False


class HlasmOracle:
    lang = "hlasm"
    exts = (".asm", ".hlasm", ".mac")
    families = FAMILIES

    def index(self, text: str) -> dict:
        """(unit name, line) -> list of Stmt. A section is `name CSECT|RSECT|START|DFHEIENT`; a macro is its prototype's name."""
        from gitgalaxy.tools.cobol_to_java.det import hlasm as H

        try:
            stmts = H.statements(text)
        except ImportError:
            raise
        except Exception:  # Refused (continuation text before column 16, ...): no oracle for this source
            return {}
        out: dict = {}
        unit: list | None = None
        in_macro = False
        want_prototype = False
        macro_line = 0

        def open_unit(name: str, *lines: int) -> list:
            """A section is keyed by its statement's line; a macro also by its MACRO card (where the engine's func_start match begins)."""
            body: list = []
            for line in lines:
                out[(name, line)] = body
                out.setdefault((name.upper(), line), body)
            return body

        for s in stmts:
            if s.op == "MACRO":
                want_prototype, in_macro, unit, macro_line = True, True, None, s.line
                continue
            if want_prototype:
                want_prototype = False
                unit = open_unit(s.op, s.line, macro_line)
                continue
            if s.op == "MEND":
                in_macro, unit = False, None
                continue
            if not in_macro and s.op in _SECTION_OPS and s.label:
                unit = open_unit(s.label, s.line)
            if unit is not None:
                unit.append(s)
        return out

    def count(self, stmts: list) -> tuple[collections.Counter, dict]:
        n: collections.Counter[str] = collections.Counter()
        tokens: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)

        def add(key: str, tok: str) -> None:
            n[key] += 1
            tokens[key][tok] += 1

        for s in stmts:
            op, operands = s.op, s.operands
            if op == "EXEC":
                body = operands.strip()
                if _CICS_IO.match(body):
                    add("io", "EXEC CICS")
                elif re.match(r"SQL\b", body, re.I) and not _SQL_NOT_IO.match(body):
                    add("io", "EXEC SQL")
                elif re.match(r"DLI\b", body, re.I):
                    add("io", "EXEC DLI")
                elif re.match(r"CICS\s+ABEND\b", body, re.I):
                    add("bailout", "EXEC CICS ABEND")
                continue
            if _is_branch(op, operands):
                add("branch", op)
            elif op in _ACCESS_METHOD and operands and (operands[0].isalpha() or operands[0] in "@#$("):
                add("io", op)
            elif op == "CALL" and operands.split(",", 1)[0].strip().upper() in _CALL_TARGETS:
                add("io", "CALL " + operands.split(",", 1)[0].strip().upper())
            elif op in _PRINT_OPS:
                add("print", op)
            elif op in _CAST_OPS:
                add("cast", op)
            elif op == "ABEND":
                add("bailout", "ABEND")
        return n, tokens


_ORACLE = HlasmOracle()


def get_oracle() -> HlasmOracle:
    return _ORACLE
