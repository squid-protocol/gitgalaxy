"""JCL oracle for the keyword-family validity tool (#8863): the repo's job-flow statement reader, not a tree-sitter node map.

A JCL "function" is an EXEC step (the engine's `func_start`): the statements from its EXEC card up to the next EXEC, JOB, PROC or PEND
card. `gitgalaxy/core/job_flow.py::_statements` joins continuation lines and skips `//*` comments and in-stream data, so this oracle
reads the operands of every card from the joined statement, which is independent of the engine's per-family regexes (what the families
are scored against). It is the project's own reader, so it is not independent of the project.

Readings (from the family contracts and IBM's z/OS MVS JCL Reference, written before the first run):
  branch      an IF statement. ELSE and ENDIF are the arms and the end of that one decision, not decisions of their own.
  args        a PARM= operand on the EXEC card (the step's parameter string; one per step).
  io          a DD card that allocates an external target: DSN= / DSNAME= other than a `&&` temporary, or SYSOUT=. One per DD card.
  sync_locks  a DD whose DISP status is OLD or MOD (exclusive use of the dataset, held until the step ends).
  cleanup     a DD whose DISP normal-termination disposition is DELETE (the second DISP subparameter, the normal-termination disposition).
  safety      a COND= operand that tests a return code; COND=EVEN / COND=ONLY alone are bypasses, not tests.
  danger      EXEC PGM= naming a program that runs caller-supplied commands (TSO batch, the z/OS UNIX shell, REXX, batch SDSF).
An unnamed EXEC is indexed under the empty name; a source with no statements indexes to nothing.
"""

from __future__ import annotations

import collections
import dataclasses
import re

from family_oracle import Family

FAMILIES: tuple[Family, ...] = (
    Family(
        "struct_branch", "branch", "decision points: IF statements (ELSE / ENDIF belong to the same decision)", "branch"
    ),
    Family("args", "args", "a PARM= operand on the step's EXEC card", "args"),
    Family(
        "arch_io",
        "io",
        "DD cards that allocate an external target: DSN= / DSNAME= (not a && temporary) or SYSOUT=",
        "io",
    ),
    Family("def_sync_locks", "locks", "DD cards held with exclusive disposition: DISP=OLD or DISP=MOD", "sync_locks"),
    Family(
        "def_cleanup", "cleanup", "DD cards whose DISP disposes the dataset with DELETE after a normal end", "cleanup"
    ),
    Family(
        "def_safety",
        "safety",
        "COND= return-code tests on the step (COND=EVEN / COND=ONLY alone are bypasses)",
        "safety",
    ),
    Family(
        "state_danger",
        "danger",
        "EXEC PGM= naming a program that runs caller-supplied commands: IKJEFT01 / IKJEFT1A / IKJEFT1B, BPXBATCH family, AOPBATCH, IRXJCL, SDSF",
        "high_risk_execution",
    ),
)

_DANGEROUS = frozenset(
    {"IKJEFT01", "IKJEFT1A", "IKJEFT1B", "BPXBATCH", "BPXBATSL", "BPXBATA2", "BPXBATA8", "AOPBATCH", "IRXJCL", "SDSF"}
)
_STEP_ENDS = frozenset({"EXEC", "JOB", "PROC", "PEND"})


@dataclasses.dataclass
class Step:
    """One EXEC step: its cards as (line, op, operand string)."""

    name: str
    line: int
    cards: list[tuple[int, str, str]]


def _split_operands(text: str) -> list[str]:
    """Top-level comma-separated operands (commas inside parentheses or apostrophes do not split)."""
    out: list[str] = []
    depth = 0
    quoted = False
    cur: list[str] = []
    for ch in text:
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        if ch == "," and depth == 0 and not quoted:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def _keywords(operands: str) -> list[tuple[str, str]]:
    """(KEYWORD, value) for each keyword operand, in order; a positional operand has an empty keyword."""
    out = []
    for part in _split_operands(operands):
        key, eq, val = part.partition("=")
        out.append((key.strip().upper(), val.strip()) if eq else ("", part.strip()))
    return out


def _disp(value: str) -> list[str]:
    """DISP subparameters (status, normal, abnormal) upper-cased; DISP=OLD is `["OLD"]`, DISP=(,DELETE) keeps the empty status."""
    v = value.strip()
    if v.startswith("(") and v.endswith(")"):
        v = v[1:-1]
    return [p.strip().upper() for p in _split_operands(v)]


class JclOracle:
    lang = "jcl"
    exts = (".jcl", ".prc", ".proc")
    families = FAMILIES

    def index(self, text: str) -> dict:
        """(step name, line) -> Step; an unnamed EXEC has the name ''."""
        from gitgalaxy.core import job_flow

        out: dict = {}
        cur: Step | None = None
        for line, name, op, operands in job_flow._statements(text):
            if op in _STEP_ENDS:
                cur = None
            if op == "EXEC":
                cur = Step(name, line, [])
                out.setdefault((name, line), cur)
                out.setdefault((name.upper(), line), cur)
            if cur is not None:
                cur.cards.append((line, op, operands))
        return out

    def count(self, step: Step) -> tuple[collections.Counter, dict]:
        n: collections.Counter[str] = collections.Counter()
        tokens: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)

        def add(key: str, tok: str) -> None:
            n[key] += 1
            tokens[key][tok] += 1

        for _, op, operands in step.cards:
            if op == "IF":
                add("branch", "IF")
                continue
            kws = _keywords(operands)
            if op == "EXEC":
                for key, val in kws:
                    if key == "PARM":
                        add("args", "PARM=")
                    elif key == "PGM" and val.upper() in _DANGEROUS:
                        add("danger", val.upper())
                    elif key == "COND" and re.sub(r"\s", "", val).upper() not in ("EVEN", "ONLY"):
                        add("safety", "COND=")
            elif op == "DD":
                targets = [k for k, v in kws if (k in ("DSN", "DSNAME") and not v.startswith("&&")) or k == "SYSOUT"]
                if targets:
                    add("io", targets[0])
                for key, val in kws:
                    if key != "DISP":
                        continue
                    parts = _disp(val)
                    if parts and parts[0] in ("OLD", "MOD"):
                        add("locks", "DISP=" + parts[0])
                    if len(parts) > 1 and parts[1] == "DELETE":
                        add("cleanup", "DISP=DELETE")
        return n, tokens


_ORACLE = JclOracle()


def get_oracle() -> JclOracle:
    return _ORACLE
