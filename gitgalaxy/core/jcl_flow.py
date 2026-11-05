# jcl_flow.py -- #4891: the execution model for JCL step flow over the `job_flow` rows.
#
# Given a job's STEP rows (`job_flow.jcl_job_flow`) and, per step that starts, the return code or abend it ends with,
# `JclFlow.run` answers which steps run and which are bypassed. The rules are IBM's (z/OS MVS JCL Reference, SA23-1385:
# the EXEC COND parameter and the IF/THEN/ELSE/ENDIF construct); the level fixture
# `tests/equivalence/jcl/fixture/scenarios.json` carries answers written from that text before this module existed.
#
# ASSUMED (named in scenarios.json): A1 a step that never started is a bypassed step for a later COND test (false);
# A2 `stepname.RUN = FALSE` on a step that did not start is true; A3 after an ordinary abend an IF that does not name
# ABEND / ABENDCC starts nothing; A4 EVEN / ONLY follow IBM's prose.
# Refused by name (JclFlowRefused): AND and OR mixed without parentheses, more than 8 COND tests, a COND test on a
# PROC step (`a.b`), a bare `ABEND` / `RUN` keyword, `RC` before any step executed, an ABENDCC ordering comparison.
# Not modelled: JOB-statement COND, COND inside THEN / ELSE, the job's final completion code, RESTART, cancel / time
# expiry (IBM: the remaining steps do not run whatever the tests say).
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_COND_OPS = {"GT": ">", "GE": ">=", "EQ": "==", "NE": "!=", "LT": "<", "LE": "<="}
_IF_OPS = {
    "=": "==",
    "==": "==",
    "EQ": "==",
    "NE": "!=",
    "!=": "!=",
    "<>": "!=",
    "GT": ">",
    ">": ">",
    "GE": ">=",
    ">=": ">=",
    "LT": "<",
    "<": "<",
    "LE": "<=",
    "<=": "<=",
    "NG": "<=",
    "NL": ">=",
}
_OUTCOME_KEYS = ("rc", "abend")  # the keys of a `given` outcome
_NOT = "¬"
_TOKEN = re.compile(r"\s*(\(|\)|\||&|" + _NOT + r"=|" + _NOT + r"|<>|>=|<=|==|=|<|>|[A-Za-z0-9@#$.]+)")


class JclFlowRefused(ValueError):
    """A construct IBM's text does not settle, or that the model does not carry: refused by name, never guessed."""


@dataclass
class StepResult:
    name: str
    action: str  # "run" (started, ended with an RC or abended) or "bypass"
    rc: int | None = None
    abend: str | None = None


@dataclass
class FlowResult:
    steps: dict[str, StepResult] = field(default_factory=dict)

    @property
    def actions(self) -> dict[str, str]:
        return {n: s.action for n, s in self.steps.items()}

    @property
    def highest_rc(self) -> int | None:
        rcs = [s.rc for s in self.steps.values() if s.rc is not None]
        return max(rcs) if rcs else None


def _compare(left: Any, op: str, right: Any) -> bool:
    return {
        "==": left == right,
        "!=": left != right,
        ">": left > right,
        ">=": left >= right,
        "<": left < right,
        "<=": left <= right,
    }[op]


def _split_top(text: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts]


def parse_cond(cond: str | None) -> tuple[list[tuple[int, str, str | None]], bool, bool]:
    """`COND=` text -> (tests as (code, op, stepname or None), even, only)."""
    if not cond:
        return [], False, False
    text = cond.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    items = _split_top(text)
    if items and re.fullmatch(r"\d+", items[0]):
        items = ["(" + text + ")"]  # a single bare test: COND=(4,GT)
    tests: list[tuple[int, str, str | None]] = []
    even = only = False
    for item in items:
        word = item.upper()
        if word == "EVEN":
            even = True
        elif word == "ONLY":
            only = True
        elif item.startswith("(") and item.endswith(")"):
            f = [x.strip() for x in item[1:-1].split(",")]
            if len(f) not in (2, 3) or not f[0].isdigit() or f[1].upper() not in _COND_OPS:
                raise JclFlowRefused(f"COND test not understood: {item}")
            if len(f) == 3 and "." in f[2]:
                raise JclFlowRefused(f"COND test on a PROC step: {item}")
            tests.append((int(f[0]), _COND_OPS[f[1].upper()], f[2] if len(f) == 3 else None))
        else:
            raise JclFlowRefused(f"COND parameter not understood: {cond}")
    if len(tests) > (7 if (even or only) else 8):
        raise JclFlowRefused("more than 8 COND tests (7 with EVEN or ONLY) is invalid JCL per IBM")
    return tests, even, only


class _Run:
    """The state IF and COND read: each step's outcome so far, in order."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.out: dict[str, StepResult] = {}

    def abended(self) -> bool:
        return any(s.abend for s in self.out.values())

    def highest_rc(self) -> int:
        rcs = [s.rc for s in self.out.values() if s.rc is not None]
        if not rcs:
            raise JclFlowRefused("IF RC before any step executed: IBM's text gives no value")
        return max(rcs)

    def started(self, name: str) -> StepResult | None:
        s = self.out.get(name)
        return s if s and s.action == "run" else None


def _relation(run: _Run, lhs: str, op: str, rhs: str) -> bool:
    step, _, key = lhs.rpartition(".")
    key = key.upper()
    started = run.started(step) if step else None
    if key == "RC":
        if step:
            return bool(started and started.rc is not None and _compare(started.rc, op, int(rhs)))
        return _compare(run.highest_rc(), op, int(rhs))
    if key in ("ABEND", "RUN"):
        want = rhs.upper()
        if want not in ("TRUE", "FALSE") or op not in ("==", "!="):
            raise JclFlowRefused(f"{key} is tested against TRUE or FALSE with = / NE: {lhs} {op} {rhs}")
        truth = want == "TRUE"
        if op == "!=":
            truth = not truth
        if key == "RUN":
            if not step:
                raise JclFlowRefused("RUN needs a stepname")
            return (started is not None) == truth  # A2: not started -> RUN = FALSE is true
        if step:
            if not started:
                return False  # IBM relationexp: a step that did not execute makes the relation false
            return bool(started.abend) == truth
        return run.abended() == truth
    if key == "ABENDCC":
        if op not in ("==", "!="):
            raise JclFlowRefused("ABENDCC is compared with = / NE only")
        pool = [started] if step else [s for s in run.out.values() if s.action == "run"]
        codes = [s.abend for s in pool if s and s.abend]
        if not codes:
            return False
        return (codes[-1] == rhs.upper()) == (op == "==")
    raise JclFlowRefused(f"IF relation not understood: {lhs} {op} {rhs}")


def _tokens(expr: str) -> list[str]:
    toks, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m:
            raise JclFlowRefused(f"IF expression not understood: {expr}")
        toks.append(m.group(1))
        pos = m.end()
    return toks


def _norm_op(tok: str) -> str:
    if tok == _NOT + "=":
        return "!="
    return _IF_OPS.get(tok.upper(), "")


def evaluate_if(expr: str, run: _Run) -> bool:
    """Evaluate an IF expression (the reader's `if_cond`: nested clauses are joined by ` AND `)."""
    toks = _tokens(expr.replace(" AND ", " & "))
    pos = 0

    def peek() -> str | None:
        return toks[pos] if pos < len(toks) else None

    def take() -> str:
        nonlocal pos
        if pos >= len(toks):
            raise JclFlowRefused(f"IF expression ends early: {expr}")
        pos += 1
        return toks[pos - 1]

    def primary() -> bool:
        t = take()
        if t.upper() == "NOT" or t == _NOT:
            return not primary()
        if t == "(":
            v = chain()
            if take() != ")":
                raise JclFlowRefused(f"IF parenthesis not closed: {expr}")
            return v
        op = _norm_op(take())
        if not op:
            raise JclFlowRefused(f"IF operator not understood in: {expr}")
        return _relation(run, t, op, take())

    def chain() -> bool:
        vals = [primary()]
        joins: set[str] = set()
        while peek() in ("&", "|") or (peek() or "").upper() in ("AND", "OR"):
            joins.add("&" if take().upper() in ("&", "AND") else "|")
            vals.append(primary())
        if len(joins) > 1:
            raise JclFlowRefused("AND and OR mixed in one IF without parentheses: IBM gives them one priority")
        if "|" in joins:
            return any(vals)
        return all(vals)

    v = chain()
    if pos != len(toks):
        raise JclFlowRefused(f"IF expression not understood: {expr}")
    return v


def _names_abend(expr: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z0-9@#$])(?:[A-Za-z0-9@#$]+\.)?ABEND(?:CC)?(?![A-Za-z0-9@#$])", expr.upper()))


class JclFlow:
    """The STEP rows of each job in a `jcl_job_flow` result, ready to run against per-step outcomes."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.jobs: dict[str, list[dict[str, Any]]] = {}
        current = None
        for row in rows:
            if row["kind"] == "JOB":
                current = row["name"]
                self.jobs[current] = []
            elif row["kind"] == "STEP" and current is not None:
                self.jobs[current].append(row)

    def run(self, job: str, given: dict[str, dict[str, Any]]) -> FlowResult:
        """`given`: per step that starts, {"rc": n} or {"abend": "S0C7"}. A step the flow starts that has no entry
        raises: the caller owes an outcome for every step that runs."""
        state = _Run()
        for row in self.jobs[job]:
            name = row["step_name"]
            if self._starts(row, state):
                if name not in given:
                    raise KeyError(f"step {name} starts but no outcome was given")
                g = given[name]
                rc, abend = (g.get(k) for k in _OUTCOME_KEYS)
                res = StepResult(name, "run", rc=rc, abend=abend)
            else:
                res = StepResult(name, "bypass")
            state.out[name] = res
        unused = set(given) - {n for n, s in state.out.items() if s.action == "run"}
        if unused:
            raise KeyError(f"outcome given for steps that do not start: {sorted(unused)}")
        return FlowResult(dict(state.out))

    @staticmethod
    def _starts(row: dict[str, Any], state: _Run) -> bool:
        abended = state.abended()
        if row.get("if_cond"):
            expr = row["if_cond"]
            if abended and not _names_abend(expr):
                return False  # A3
            if not evaluate_if(expr, state):
                return False
        tests, even, only = parse_cond(row.get("cond"))
        if abended and not (even or only) and not (row.get("if_cond") and _names_abend(row["if_cond"])):
            return False  # after an abend: bypass unless EVEN / ONLY or an IF naming ABEND
        if only and not abended:
            return False
        for code, op, step in tests:
            pool = [step] if step else list(state.out)
            for n in pool:
                s = state.started(n)  # a bypassed or never-started step tests false (A1)
                if s and s.rc is not None and _compare(code, op, s.rc):
                    return False
        return True
