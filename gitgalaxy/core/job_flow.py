# ==============================================================================
# GitGalaxy Core: JCL job flow -- steps, conditions, dataset dispositions (#3451)
#
# PURPOSE:
# dataset_data (#3201 / #3345) binds each step's DDs to resolved DSNs, but not
# the job FLOW: the order of steps, which run conditionally (COND=, IF / THEN /
# ELSE / ENDIF), which call a procedure, and whether a DD creates its dataset
# (DISP=NEW / MOD, a GDG `(+1)`) or reads one (SHR / OLD, `(0)`, `(-n)`). That is
# what a batch data-flow DAG is built from. One row per statement of interest:
#
#   kind  fields
#   JOB   name, cond (the JOB card's COND=)
#   STEP  step_ordinal (1-based within its job or PROC), step_name, program
#         (EXEC PGM=), proc (EXEC PROC=P / EXEC P), cond (EXEC COND=, as written),
#         if_cond (the enclosing IF conditions: `(RC = 0)`, `NOT (RC = 0)` in an
#         ELSE, nested ones joined by ` AND `), in_proc (the PROC it belongs to)
#   DD    step_name (the step, or for an override `//PROCSTEP.DD` the proc step),
#         dd_name, dsn (as written, generation stripped), disp (NEW / OLD / SHR /
#         MOD; NEW when a DSN is coded without DISP), generation (+1 / 0 / -1),
#         in_proc; a concatenation's unnamed DDs take the name above them
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. Expanding an EXEC of a PROC into its steps, and
#     pairing a producing DD with the DDs of other steps / jobs that read the same
#     dataset, is the reader's (GalaxyIR.job_steps / job_dataset_flow).
#   - Scheduler dependencies (CA-7, TWS, Control-M) are not in the repository;
#     cross-job ORDER is therefore unknown, and producer -> consumer edges across
#     jobs are candidates, not a schedule.
#   - Only DDs that name a DSN are DD rows (not SYSOUT / DUMMY / in-stream `*`).
#   - Its own statement reader, bounded per statement: a DD with a dotted
#     override name (`//PRC001.FILEIN DD`) and IF / ELSE / ENDIF, which the
#     dataset reader does not keep, are read here.
# ==============================================================================
import re
from typing import Any, Optional

# `<NAME>`: a template JCL's installation placeholder (#3489 GENAPP), kept as written.
_STMT = re.compile(r"^//([A-Z0-9@#$.<>]{0,17})[ \t]+([A-Z]{2,8})(?:[ \t]+(.*))?$", re.I)
_OPS = frozenset({"JOB", "EXEC", "DD", "PROC", "PEND", "IF", "ELSE", "ENDIF", "SET", "INCLUDE", "JCLLIB", "OUTPUT"})
_STATEMENT_LIMIT = 4000
_GEN = re.compile(r"\(([+-]?[0-9]{1,3})\)$")


def _operand_field(text: str) -> str:
    """The operands up to the first blank outside apostrophes (the rest is a comment)."""
    quoted = False
    for i, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch in " \t":
            return text[:i]
    return text


def _split(field: str) -> list[tuple[Optional[str], str]]:
    """Top-level `KEY=value` operands (commas inside parens / quotes kept)."""
    parts, depth, quoted, start = [], 0, False, 0
    for i, ch in enumerate(field):
        if ch == "'":
            quoted = not quoted
        elif quoted:
            continue
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(field[start:i])
            start = i + 1
    parts.append(field[start:])
    out: list[tuple[Optional[str], str]] = []
    for p in parts:
        m = re.match(r"([A-Z@#$][A-Z0-9@#$.]{0,24})=", p, re.I)
        out.append((m.group(1).upper(), p[m.end() :]) if m else (None, p))
    return out


def _statements(code_stream: str) -> list[tuple[int, str, str, str]]:
    """(line, name, op, operands) with continuations joined; IF keeps its whole condition."""
    out: list[tuple[int, str, str, str]] = []
    pending: Optional[list] = None
    for no, raw in enumerate(code_stream.split("\n"), 1):
        line = raw[:72].rstrip()
        # A `//*` comment -- or the empty line PRISM leaves for one -- may sit inside a
        # continued statement (CardDemo BUILDONL: DSN=...,  //* ...  //  DISP=SHR);
        # it neither ends nor joins it. In-stream data ends it.
        if not line or line.startswith("//*"):
            continue
        if not line.startswith("//"):
            if pending:
                out.append(tuple(pending))  # type: ignore[arg-type]
                pending = None
            continue
        m = _STMT.match(line)
        if m and m.group(2).upper() in _OPS:
            if pending:
                out.append(tuple(pending))  # type: ignore[arg-type]
            op = m.group(2).upper()
            rest = (m.group(3) or "").strip()
            if op == "IF":
                cond = re.split(r"[ \t]THEN\b", rest, maxsplit=1, flags=re.I)[0]
                out.append((no, m.group(1).upper(), op, " ".join(cond.split())))
                pending = None
                continue
            field = _operand_field(rest)
            pending = [no, m.group(1).upper(), op, field]
            if not field.endswith(","):
                out.append(tuple(pending))  # type: ignore[arg-type]
                pending = None
        elif pending:
            more = _operand_field(line[2:].strip())
            pending[3] = (pending[3] + more)[:_STATEMENT_LIMIT]
            if not more.endswith(","):
                out.append(tuple(pending))  # type: ignore[arg-type]
                pending = None
    if pending:
        out.append(tuple(pending))  # type: ignore[arg-type]
    return out


def _disp(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip("()").split(",")[0].strip().upper()
    return v or "NEW"  # DISP=(,CATLG) is NEW


_NORMAL_ENDS = ("KEEP", "CATLG", "DELETE", "PASS", "UNCATLG")


def _disp_normal(value: Optional[str]) -> Optional[str]:
    """#3622: DISP's normal-end disposition -- `(MOD,DELETE,DELETE)` -> DELETE -- or None."""
    if value is None:
        return None
    parts = value.strip("()").split(",")
    end = parts[1].strip().upper() if len(parts) > 1 else ""
    return end if end in _NORMAL_ENDS else None


def _generation(text: str) -> str:
    """A GDG relative generation as `+1` / `0` / `-1`."""
    n = int(text)
    return f"+{n}" if n > 0 else str(n)


def jcl_job_flow(code_stream: str) -> list[dict[str, Any]]:
    """The job flow of one JCL file (see the module header)."""
    if not code_stream or "//" not in code_stream:
        return []
    rows: list[dict[str, Any]] = []
    blank = {
        "kind": None,
        "name": None,
        "step_ordinal": None,
        "step_name": None,
        "program": None,
        "proc": None,
        "cond": None,
        "if_cond": None,
        "in_proc": None,
        "dd_name": None,
        "dsn": None,
        "disp": None,
        "generation": None,
        "line": 0,
    }
    in_proc: Optional[str] = None
    ordinal = 0
    step: Optional[str] = None
    last_dd: Optional[str] = None
    ifs: list[str] = []
    for line, name, op, field in _statements(code_stream):
        if op == "JOB":
            job_ops = dict(_split(field))
            rows.append(dict(blank, kind="JOB", name=name or None, cond=job_ops.get("COND"), line=line))
            in_proc, ordinal, step = None, 0, None
        elif op == "PROC":
            in_proc, ordinal, step = (name or "PROC"), 0, None
        elif op == "PEND":
            in_proc, ordinal, step = None, 0, None
        elif op == "IF":
            ifs.append(field)
        elif op == "ELSE" and ifs:
            ifs[-1] = f"NOT {ifs[-1]}"
        elif op == "ENDIF" and ifs:
            ifs.pop()
        elif op == "EXEC":
            exec_ops = _split(field)
            keyed = {k: v for k, v in exec_ops if k}
            program = keyed.get("PGM")
            proc = keyed.get("PROC") or (
                next((v for k, v in exec_ops if k is None and v), None) if not program else None
            )
            ordinal += 1
            step = name or None
            last_dd = None
            rows.append(
                dict(
                    blank,
                    kind="STEP",
                    step_ordinal=ordinal,
                    step_name=step,
                    program=program.upper() if program else None,
                    proc=proc.upper() if proc else None,
                    cond=keyed.get("COND"),
                    if_cond=" AND ".join(ifs) or None,
                    in_proc=in_proc,
                    line=line,
                )
            )
        elif op == "DD":
            dd_step, dd_name = step, name
            if "." in name:
                dd_step, dd_name = name.split(".", 1)
            if dd_name:
                last_dd = dd_name
            else:
                dd_name = last_dd or ""
            keyed = {k: v for k, v in _split(field) if k}
            dsn = keyed.get("DSN") or keyed.get("DSNAME")
            if not dsn:
                continue
            dsn = dsn.upper()
            gen = _GEN.search(dsn)
            if gen:
                dsn = dsn[: gen.start()]
            disp = _disp(keyed.get("DISP")) or "NEW"
            normal = _disp_normal(keyed.get("DISP"))
            rows.append(
                dict(
                    blank,
                    kind="DD",
                    step_name=dd_step,
                    dd_name=dd_name or None,
                    dsn=dsn,
                    disp=disp,
                    generation=_generation(gen.group(1)) if gen else None,
                    in_proc=in_proc,
                    line=line,
                    # #3622: presence-keyed -- a DD without a normal-end disposition keeps its pre-#3622 shape
                    **({"disp_normal": normal} if normal else {}),
                )
            )
    return rows
