"""
Blind census of the answer key's per-file FACT-CHANNEL sections (epic #3445).

cross_verify.py censuses the key's `programs` block (reachability, PROGRAM-ID,
copybooks, calls, files). The fact-channel sections drafted since then live in
their own per-file blocks, each with its own sign-off flag:

    section           flag                     question
    sql_access        sql_access_validated     which DB2 tables a program reads / writes
    cics_tasks        cics_tasks_validated     CICS task control + the transactions a RUN/START starts
    mq_calls          mq_validated             IBM MQ calls: queue, direction, the MQOPEN a handle came from
    uow_handlers      uow_validated            commit / rollback points, handlers, ABENDs, RESP checks
    job_submissions   submissions_validated    jobs submitted to the internal reader (corpus-wide)
    tdq_triggers      tdq_triggers_validated   transactions a filling TD queue starts (corpus-wide)

    python tests/tools/cross_verify_sections.py census   --corpus NAME --out DIR --stage DIR [--max-items 70] [--suite channels|files]
    python tests/tools/cross_verify_sections.py grade    --corpus NAME --dir DIR/batch_NN
    python tests/tools/cross_verify_sections.py sign     --corpus NAME --dir DIR/batch_NN --by "REVIEWER"
    python tests/tools/cross_verify_sections.py coverage --corpus NAME [--suite channels|files]

SUITES. `channels` (the default) is the six sections above, asked of every COBOL
source. `files` (#3455 / #3451) is the file-definition sections, asked of every
COBOL program and JCL member:

    file_control      file_control_validated   each FILE-CONTROL SELECT's clauses and FD COPYs
    vsam_defines      vsam_validated           IDCAMS DEFINE CLUSTER / AIX / PATH
    job_flow          jobflow_validated        JCL JOB / STEP / DSN-DD rows

The census asks about EVERY COBOL source of the corpus -- files the key lists
nothing for included, so "none" is checked too (recall, not only precision) --
packed into batches of about --max-items key facts. The corpus-wide questions
(job submissions, TD trigger starts) ride in batch 1. The brief is blind: it
states each channel's contract, never the key's answers. The reviewer replies
with structured facts, which are put into the same canonical strings the key's
entries become, and compared per file as sets.

grade / rulings.json / sign work as in cross_verify.py: every disagreement needs
a `key_correct` or `key_fixed` ruling (with a why), a `key_fixed` one must no
longer disagree against the current key, and signing sets the section flags of
the batch's files and records the batch under the key's `section_census`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mainframe_corpus as mc  # noqa: E402
from cross_verify import FIXED_FORMAT_RULES, load_key, parse_answers  # noqa: E402

REPO_ROOT = mc.REPO_ROOT
COBOL_EXTS = (".cbl", ".cob", ".cobol", ".ccp", ".cpy", ".copy")
PER_FILE = ("sql", "tasks", "children", "mq", "uow")
CORPUS_WIDE = ("jobs", "triggers")
# answer task -> (key section, flag)
SECTIONS = {
    "sql": ("sql_access", "sql_access_validated"),
    "tasks": ("cics_tasks", "cics_tasks_validated"),
    "children": ("cics_tasks", "cics_tasks_validated"),
    "mq": ("mq_calls", "mq_validated"),
    "uow": ("uow_handlers", "uow_validated"),
    "jobs": ("job_submissions", "submissions_validated"),
    "triggers": ("tdq_triggers", "tdq_triggers_validated"),
}


def _ws(s: Any) -> str:
    return " ".join(str(s).split()).upper()


def _d(v: Any) -> str:
    return _ws(v) if v not in (None, "", []) else "-"


# ---- canonical forms: one string per fact, for the key's rows and the reviewer's ----
def canon_sql(access: str, table: str) -> str:
    return f"{_ws(access).lower()} {_ws(table)}"


def canon_task(r: dict[str, Any]) -> str:
    return (
        f"L{int(r.get('line') or 0)} {_ws(r.get('verb'))} T={_d(r.get('target'))} CH={_d(r.get('channel'))} "
        f"TOK={_d(r.get('token'))} REC={_d(r.get('record'))}"
    )


def canon_child(verb: str, transid: str) -> str:
    return f"{_ws(verb)} {_ws(transid)}"


def canon_mq(r: dict[str, Any]) -> str:
    opened = r.get("open_line")
    return (
        f"L{int(r.get('line') or 0)} {_ws(r.get('verb'))} DIR={_d(r.get('direction'))} Q={_d(r.get('queue'))} "
        f"OPEN={'L' + str(int(opened)) if opened else '-'}"
    )


# Kinds whose verb the kind alone fixes: a reviewer who leaves `verb` out of one of
# these states the same fact (a grader normalisation, like CICS name padding).
_FIXED_VERB = {
    "HANDLE_ABEND": "HANDLE ABEND",
    "HANDLE_CONDITION": "HANDLE CONDITION",
    "HANDLE_AID": "HANDLE AID",
    "IGNORE_CONDITION": "IGNORE CONDITION",
    "PUSH_HANDLE": "PUSH HANDLE",
    "POP_HANDLE": "POP HANDLE",
    "ABEND": "ABEND",
}


def canon_uow(r: dict[str, Any]) -> str:
    if not r.get("verb") and _ws(r.get("kind")) in _FIXED_VERB:
        r = dict(r, verb=_FIXED_VERB[_ws(r.get("kind"))])
    cond = r.get("condition")
    if r.get("kind") == "RESP_CHECK" and cond:
        parts = cond if isinstance(cond, list) else str(cond).split(",")
        cond = ",".join(sorted(_ws(c) for c in parts if str(c).strip()))
    return (
        f"L{int(r.get('line') or 0)} {_ws(r.get('kind'))} {_ws(r.get('verb'))} C={_d(cond)} T={_d(r.get('target'))} "
        f"TK={_d(r.get('target_kind'))} V={_d(r.get('resp_var'))} A={_d(r.get('attributes'))}"
    )


def key_facts(key: dict[str, Any], files: list[str], wide: bool) -> dict[str, dict[str, list[str]]]:
    """The key's canonical facts per task, per file, for `files` (and, when `wide`,
    the corpus-wide tasks for every file that has them)."""
    out: dict[str, dict[str, list[str]]] = {t: {} for t in PER_FILE + CORPUS_WIDE}
    for rel in files:
        sql = key.get("sql_access", {}).get(rel, {})
        out["sql"][rel] = sorted({canon_sql(*a.split(" ", 1)) for a in sql.get("accesses", [])})
        tasks = key.get("cics_tasks", {}).get(rel, {})
        out["tasks"][rel] = sorted(
            {
                canon_task(
                    {
                        "line": r["line"],
                        "verb": r["verb"],
                        "target": r.get("name"),
                        "channel": r.get("channel"),
                        "token": r.get("token"),
                        "record": r.get("record"),
                    }
                )
                for r in tasks.get("operations", [])
            }
        )
        out["children"][rel] = sorted({_ws(c) for c in tasks.get("children", [])})
        mq = key.get("mq_calls", {}).get(rel, {})
        out["mq"][rel] = sorted(
            {
                canon_mq(
                    dict(
                        r,
                        queue=r.get("queue")
                        or (f"<{r['resolution']}>" if r.get("resolution") in ("trigger", "reply_to") else None),
                    )
                )
                for r in mq.get("calls", [])
            }
        )
        uow = key.get("uow_handlers", {}).get(rel, {})
        out["uow"][rel] = sorted({canon_uow(r) for r in uow.get("rows", [])})
    if wide:
        for rel, v in key.get("job_submissions", {}).items():
            out["jobs"][rel] = sorted({_ws(s) for s in v.get("submissions", [])})
        for rel, v in key.get("tdq_triggers", {}).items():
            out["triggers"][rel] = sorted({_ws(s) for s in v.get("starts", [])})
    return out


def reviewer_facts(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    """The reviewer's answers in the same canonical strings."""

    def rel(p: str) -> str:
        root = str(repo).rstrip("/") + "/"
        return p[len(root) :] if p.startswith(root) else p

    out: dict[str, dict[str, set[str]]] = {t: {} for t in PER_FILE + CORPUS_WIDE}
    for path, v in (answers.get("files") or {}).items():
        r = rel(path)
        v = v or {}
        out["sql"][r] = {
            canon_sql(x.get("access", ""), x.get("table", "")) for x in v.get("sql", []) if isinstance(x, dict)
        }
        out["tasks"][r] = {canon_task(x) for x in v.get("tasks", []) if isinstance(x, dict)}
        out["children"][r] = {
            canon_child(x.get("verb", ""), x.get("transid", "")) for x in v.get("children", []) if isinstance(x, dict)
        }
        out["mq"][r] = {canon_mq(x) for x in v.get("mq", []) if isinstance(x, dict)}
        out["uow"][r] = {canon_uow(x) for x in v.get("uow", []) if isinstance(x, dict)}
    for task in CORPUS_WIDE:
        for path, items in (answers.get(task) or {}).items():
            out[task][rel(path)] = {_ws(s) for s in items or []}
    return out


def corpus_files(repo: Path) -> list[str]:
    return sorted(
        p.relative_to(repo).as_posix()
        for p in repo.rglob("*")
        if p.is_file() and p.suffix.lower() in COBOL_EXTS and ".git" not in p.parts
    )


def batches(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    """Every COBOL source, packed by the number of key facts it carries (a file
    with none still costs a reading), largest first."""
    facts = key_facts(key, files, wide=False)
    load = {f: 1 + sum(len(facts[t].get(f, [])) for t in PER_FILE) for f in files}
    out: list[list[str]] = []
    sizes: list[int] = []
    for f in sorted(files, key=lambda x: (-load[x], x)):
        for i, s in enumerate(sizes):
            if s + load[f] <= max_items:
                out[i].append(f)
                sizes[i] += load[f]
                break
        else:
            out.append([f])
            sizes.append(load[f])
    return [sorted(b) for b in out]


def render(key: dict[str, Any], repo: Path, files: list[str], index: int, of: int) -> tuple[str, dict[str, Any]]:
    wide = index == 1
    truth = {
        "corpus": key["corpus"],
        "ref": key["ref"],
        "root": str(repo),
        "mode": "section_census",
        "batch": index,
        "of": of,
        "files": files,
        "wide": wide,
        "facts": key_facts(key, files, wide),
    }
    listing = "\n".join(str(repo / f) for f in files)
    wide_tasks = (
        f"""
TASK JOBS (whole repository) -- job submission to the JES internal reader. List every file in the repository that
submits a batch job, as strings in exactly these forms:
  - a COBOL program that writes (EXEC CICS WRITEQ TD) to a TD queue Q which a CSD deck (*.csd) defines TYPE(EXTRA),
    when the program holds a literal JCL job card (`//NAME JOB ...` inside a quoted literal) or some JCL routes Q's
    DDNAME to SYSOUT=(x,INTRDR):  "tdq Q -> JOB NAME" for each such job card, and "tdq Q -> PROC P = <repo path>" /
    "tdq Q -> PGM P = <repo path>" for each literal `//STEP EXEC PROC=P` / `EXEC PGM=P` / `EXEC P` card in that
    program (the path of the JCL member named P -- for a PROC prefer a .prc file or a file under a proc directory;
    "?" when none or several);
  - a JCL member (*.jcl, *.JCL, *.prc) with a DD statement coded SYSOUT=(class,INTRDR): "intrdr <ddname> -> JOB M =
    <repo path of the JCL member M>" (<ddname> is that DD statement's own name, e.g. SYSUT2) where M is the member name in parentheses of the same step's SYSUT1 DSN
    (`LIB(M)`), or "intrdr <ddname> -> ?" when that step has no SYSUT1 member.
TASK TRIGGERS (whole repository) -- a CSD `DEFINE TDQUEUE(Q) ... TRANSID(T)` makes CICS start T when Q fills. For
every COBOL file that WRITEQ TDs such a Q: "Q -> T -> P" with P the PROGRAM of `DEFINE TRANSACTION(T)` ("?" if none).
"""
        if wide
        else ""
    )
    brief = f"""You are independently verifying facts about real IBM mainframe COBOL source code, as a second reviewer.
Read the source files yourself. They are all under the repository root {repo}; read only inside that directory. Do
NOT edit or create any files except your answers file, and do not look for any existing answer key or analysis of
this code: the point is an independent reading. Read the COBOL source directly (grep/sed/cat or a file reader).
Line numbers are 1-based physical line numbers of the file. Ignore commented-out lines and text inside quoted
literals (a DISPLAY 'EXEC CICS ...' is not a command).

{FIXED_FORMAT_RULES}

For EACH file below answer every per-file task; a file with nothing for a task gets an empty list.

TASK SQL -- DB2 table access. Every table an embedded `EXEC SQL` statement touches, with its access: "read" (a table
in FROM / JOIN of a SELECT, a DECLARE CURSOR's SELECT, an INSERT ... SELECT source, a MERGE USING source), "insert",
"update", "delete", "merge", "lock". Tables as written (qualifier kept, e.g. CARDDEMO.TRANSACTION_TYPE). Not
DECLARE TABLE / INCLUDE / WHENEVER; a cursor's table is read by its DECLARE, OPEN/FETCH add nothing new.

TASK TASKS -- CICS task-control commands: RUN, START, START ATTACH, FETCH CHILD, FETCH ANY, FREE CHILD, RETRIEVE,
CANCEL, DELAY, POST, WAIT EVENT, WAIT EXTERNAL, WAITCICS, ENQ, DEQ. One entry each: "line" (of `EXEC CICS`), "verb"
(one of those names), "target" (TRANSID for RUN/START/START ATTACH/CANCEL, RESOURCE for ENQ/DEQ) as ONE value only
when the source fixes it -- a literal, the data-name's VALUE literal, or the one literal ever MOVEd or STRINGed into
it -- else null; "channel" (CHANNEL(...) resolved the same way, else null); "token" (the data-name in CHILD(...) /
ANY(...) / REQID(...), else null); "record" (the FROM / INTO / SET operand, else null).
TASK CHILDREN -- for every RUN / START / START ATTACH, each CSD transaction id (DEFINE TRANSACTION in *.csd) it can
start: the fixed target, or when the id is built at run time (e.g. STRING 'AB' + a PIC 9 counter INTO the field),
every defined transaction whose id fits what the source builds (literal prefix, then the counter's width and class).

TASK MQ -- IBM MQ calls (CALL 'MQOPEN' / 'MQPUT' / 'MQPUT1' / 'MQGET' / 'MQCLOSE' ...). One entry each: "line" (of the
CALL), "verb", "direction" ("get" for MQGET or an MQOPEN whose options include MQOO-INPUT*, "browse" for MQOO-BROWSE,
"put" for MQPUT/MQPUT1 or MQOO-OUTPUT, else null), "queue" (the queue name when one literal determines it --
through the value last MOVEd to the object descriptor's OBJECTNAME before an MQOPEN/MQPUT1 and on through MOVEs --
"<trigger>" when it comes from MQTM-QNAME, "<reply_to>" when from MQMD-REPLYTOQ, else null; an MQPUT / MQGET /
MQCLOSE takes the queue of the MQOPEN its object handle came from), "open_line" (that MQOPEN's line, else null).

TASK UOW -- units of work and error handling. One entry each, with "line" (of the EXEC), "kind", "verb",
"condition", "target", "target_kind", "resp_var", "attributes" (null where not given):
  - EXEC CICS SYNCPOINT: kind COMMIT, verb "SYNCPOINT"; SYNCPOINT ROLLBACK: kind ROLLBACK, verb "SYNCPOINT ROLLBACK";
    EXEC SQL COMMIT / ROLLBACK [WORK]: kind COMMIT / ROLLBACK, verb as written ("COMMIT WORK"), line of EXEC SQL.
  - HANDLE CONDITION / HANDLE AID: one entry per condition or key: kind HANDLE_CONDITION / HANDLE_AID, condition the
    name, target the paragraph in its parentheses with target_kind LABEL, or target null + target_kind DEFAULT when
    named bare. IGNORE CONDITION: one per condition, kind IGNORE_CONDITION. PUSH / POP HANDLE: kind PUSH_HANDLE /
    POP_HANDLE.
  - HANDLE ABEND: kind HANDLE_ABEND, target_kind LABEL (target the paragraph) / PROGRAM (target the program name,
    through its VALUE) / CANCEL / RESET.
  - EXEC CICS ABEND: kind ABEND, condition the ABCODE (the literal, or the data-name's VALUE literal, else the
    data-name), attributes the NODUMP / CANCEL options in written order ("NODUMP CANCEL"), else null.
  - RESP checks: every OTHER EXEC CICS command coded RESP(v) (or NOHANDLE, then v = EIBRESP): kind RESP_CHECK, verb
    the command's first word (READ, SEND, LINK, SYNCPOINT, ...), resp_var v, condition the DFHRESP(x) names compared
    against v after the command -- from its END-EXEC up to the next command that sets v again, the next paragraph /
    section header, or about 100 lines -- as a list, or null when nothing tests v in that span.
{wide_tasks}
Files:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"sql": [{{"access": "read", "table": "T"}}],
                      "tasks": [{{"line": 1, "verb": "RUN", "target": null, "channel": null, "token": null, "record": null}}],
                      "children": [{{"verb": "RUN", "transid": "ABC1"}}],
                      "mq": [{{"line": 1, "verb": "MQOPEN", "direction": "get", "queue": null, "open_line": null}}],
                      "uow": [{{"line": 1, "kind": "COMMIT", "verb": "SYNCPOINT", "condition": null, "target": null,
                               "target_kind": null, "resp_var": null, "attributes": null}}]}}, ...every file above...}}{', "jobs": {"<path>": ["..."]}, "triggers": {"<path>": ["..."]}' if wide else ""}}}
"""
    return brief, truth


# ---- the `files` suite (#3455 / #3451) -------------------------------------------
FILE_TASKS = ("selects", "vsam", "flow")
FILE_SECTIONS = {
    "selects": ("file_control", "file_control_validated"),
    "vsam": ("vsam_defines", "vsam_validated"),
    "flow": ("job_flow", "jobflow_validated"),
}
PROGRAM_EXTS = (".cbl", ".cob", ".cobol", ".ccp")
JCL_EXTS = (".jcl", ".prc")


def _nsp(v: Any) -> str:
    """A condition with every blank dropped: `(STEP10.RC = 0)` == `(STEP10.RC=0)`."""
    return re.sub(r"\s+", "", str(v)).upper() if v not in (None, "") else "-"


def _list(v: Any) -> str:
    return ",".join(sorted(_ws(x) for x in v)) if v else "-"


def canon_select(r: dict[str, Any]) -> str:
    return (
        f"L{int(r.get('line') or 0)} {_ws(r.get('select'))} ASSIGN={_d(r.get('assign'))} ORG={_d(r.get('org'))} "
        f"ACCESS={_d(r.get('access'))} KEY={_d(r.get('key'))} ALT={_list(r.get('alt'))} REL={_d(r.get('rel'))} "
        f"STATUS={_d(r.get('status'))} COPY={_list(r.get('copies'))}"
    )


def canon_vsam(r: dict[str, Any]) -> str:
    keys = ",".join(str(x) for x in r["keys"]) if r.get("keys") else "-"
    rec = ",".join(str(x) for x in r["rec"]) if r.get("rec") else "-"
    return (
        f"L{int(r.get('line') or 0)} {_ws(r.get('kind'))} {_d(r.get('name'))} ORG={_d(r.get('org'))} KEYS={keys} "
        f"REC={rec} REL={_d(r.get('related'))} UNIQ={_d(r.get('unique'))} UPG={_d(r.get('upgrade'))} "
        f"STEP={_d(r.get('step'))}"
    )


def canon_flow(r: dict[str, Any]) -> str:
    line = int(r.get("line") or 0)
    kind = _ws(r.get("kind"))
    if kind == "JOB":
        return f"L{line} JOB {_d(r.get('name'))} COND={_nsp(r.get('cond'))}"
    if kind == "STEP":
        return (
            f"L{line} STEP {int(r.get('ord') or 0)} {_d(r.get('step'))} PGM={_d(r.get('pgm'))} "
            f"PROC={_d(r.get('proc'))} COND={_nsp(r.get('cond'))} IF={_nsp(r.get('if'))} IN={_d(r.get('in'))}"
        )
    gen = r.get("gen")
    if gen not in (None, ""):
        n = int(str(gen))
        gen = f"+{n}" if n > 0 else str(n)
    return (
        f"L{line} DD {_d(r.get('step'))}.{_d(r.get('dd'))} DSN={_d(r.get('dsn'))} DISP={_d(r.get('disp'))} "
        f"GEN={_d(gen)} IN={_d(r.get('in'))}"
    )


def key_facts_files(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {t: {} for t in FILE_TASKS}
    for rel in files:
        out["selects"][rel] = sorted(
            {canon_select(r) for r in key.get("file_control", {}).get(rel, {}).get("selects", [])}
        )
        out["vsam"][rel] = sorted({canon_vsam(r) for r in key.get("vsam_defines", {}).get(rel, {}).get("defines", [])})
        out["flow"][rel] = sorted({canon_flow(r) for r in key.get("job_flow", {}).get(rel, {}).get("rows", [])})
    return out


def reviewer_facts_files(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    def rel(p: str) -> str:
        root = str(repo).rstrip("/") + "/"
        return p[len(root) :] if p.startswith(root) else p

    out: dict[str, dict[str, set[str]]] = {t: {} for t in FILE_TASKS}
    for path, v in (answers.get("files") or {}).items():
        r, v = rel(path), v or {}
        sel = []
        for x in v.get("selects", []):
            if not isinstance(x, dict):
                continue
            alt = [
                a["name"] + ("+DUP" if a.get("duplicates") else "") if isinstance(a, dict) else a
                for a in x.get("alternate_keys") or []
            ]
            sel.append(
                canon_select(
                    {
                        "line": x.get("line"),
                        "select": x.get("select"),
                        "assign": x.get("assign"),
                        "org": x.get("organization"),
                        "access": x.get("access_mode"),
                        "key": x.get("record_key"),
                        "alt": alt,
                        "rel": x.get("relative_key"),
                        "status": x.get("file_status"),
                        "copies": x.get("fd_copies") or [],
                    }
                )
            )
        out["selects"][r] = set(sel)
        vs = []
        for x in v.get("vsam", []):
            if not isinstance(x, dict):
                continue
            keys = [x.get("key_length"), x.get("key_offset")]
            rec = [x.get("record_avg"), x.get("record_max")]
            vs.append(
                canon_vsam(
                    {
                        "line": x.get("line"),
                        "kind": x.get("kind"),
                        "name": x.get("name"),
                        "org": x.get("organization"),
                        "keys": [k for k in keys if k is not None] or None,
                        "rec": [k for k in rec if k is not None] or None,
                        "related": x.get("related"),
                        "unique": x.get("unique"),
                        "upgrade": x.get("upgrade"),
                        "step": x.get("step"),
                    }
                )
            )
        out["vsam"][r] = set(vs)
        fl = []
        for x in v.get("flow", []):
            if not isinstance(x, dict):
                continue
            fl.append(
                canon_flow(
                    {
                        "line": x.get("line"),
                        "kind": x.get("kind"),
                        "name": x.get("name"),
                        "ord": x.get("ordinal"),
                        "step": x.get("step"),
                        "pgm": x.get("program"),
                        "proc": x.get("proc"),
                        "cond": x.get("cond"),
                        "if": x.get("if_cond"),
                        "in": x.get("in_proc"),
                        "dd": x.get("dd"),
                        "dsn": x.get("dsn"),
                        "disp": x.get("disp"),
                        "gen": x.get("generation"),
                    }
                )
            )
        out["flow"][r] = set(fl)
    return out


def corpus_files_files(repo: Path) -> list[str]:
    return sorted(
        p.relative_to(repo).as_posix()
        for p in repo.rglob("*")
        if p.is_file() and p.suffix.lower() in PROGRAM_EXTS + JCL_EXTS and ".git" not in p.parts
    )


def batches_files(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    facts = key_facts_files(key, files)
    load = {f: 1 + sum(len(facts[t].get(f, [])) for t in FILE_TASKS) for f in files}
    out: list[list[str]] = []
    sizes: list[int] = []
    for f in sorted(files, key=lambda x: (-load[x], x)):
        for i, sz in enumerate(sizes):
            if sz + load[f] <= max_items:
                out[i].append(f)
                sizes[i] += load[f]
                break
        else:
            out.append([f])
            sizes.append(load[f])
    return [sorted(b) for b in out]


def render_files(key: dict[str, Any], repo: Path, files: list[str], index: int, of: int) -> tuple[str, dict[str, Any]]:
    truth = {
        "corpus": key["corpus"],
        "ref": key["ref"],
        "root": str(repo),
        "mode": "section_census",
        "suite": "files",
        "batch": index,
        "of": of,
        "files": files,
        "facts": key_facts_files(key, files),
    }
    listing = "\n".join(str(repo / f) for f in files)
    brief = f"""You are independently verifying facts about real IBM mainframe COBOL and JCL source code, as a second reviewer.
Read the source files yourself. They are all under the repository root {repo}; read only inside that directory. Do
NOT edit or create any files except your answers file, and do not look for any existing answer key or analysis of
this code: the point is an independent reading. Read the source directly (grep/sed/cat or a file reader). Line
numbers are 1-based physical line numbers. Ignore comment lines and columns 73-80 of every line.

{FIXED_FORMAT_RULES}
JCL: a statement starts on a `//` line; it continues onto the next `//` line when its operand field ends with a
comma. `//*` lines are comments. Lines not starting with `//` are in-stream data.

For EACH file below answer the tasks that apply (COBOL programs: SELECTS; JCL members: VSAM and FLOW); an empty
list when a file has none.

TASK SELECTS (COBOL) -- every FILE-CONTROL `SELECT` entry: "line" (of the word SELECT), "select" (the file name),
"assign" (the ASSIGN target, quotes removed), "organization" (INDEXED / RELATIVE / SEQUENTIAL / LINE SEQUENTIAL as
coded -- `ORGANIZATION IS x` or a bare INDEXED / RELATIVE / SEQUENTIAL -- or null when the file has no
organization clause), "access_mode" (SEQUENTIAL / RANDOM / DYNAMIC, or null), "record_key", "relative_key",
"file_status" (the first data-name after FILE STATUS), each null when absent, "alternate_keys" ([{{"name": ..,
"duplicates": true|false}}]), and "fd_copies" (the members of the COPY statements inside that file's FD entry, from
`FD name` to the next FD / SD / section header; [] when none).

TASK VSAM (JCL) -- every IDCAMS DEFINE CLUSTER / DEFINE ALTERNATEINDEX (AIX) / DEFINE PATH in in-stream data
(continuation lines end in `-`): "line" (of the DEFINE), "kind" (CLUSTER / AIX / PATH), "name", "organization"
(INDEXED / NUMBERED / NONINDEXED / LINEAR, or null), "key_length" / "key_offset" (KEYS(l o)), "record_avg" /
"record_max" (RECORDSIZE(a m)), "related" (an AIX's RELATE, a PATH's PATHENTRY), "unique" (an AIX's UNIQUE /
NONUNIQUE when UNIQUEKEY / NONUNIQUEKEY is coded), "upgrade" (an AIX's UPGRADE / NOUPGRADE when coded), "step" (the
EXEC step name the IDCAMS input belongs to); null where not coded. Read only the object's own parameters, not those
of its DATA( ) / INDEX( ) components. Not DEFINE GDG.

TASK FLOW (JCL) -- one entry per JOB statement, EXEC statement and DD statement that codes DSN= / DSNAME=:
  - JOB: "kind": "JOB", "line", "name", "cond" (the JOB's COND= value as written, else null).
  - EXEC: "kind": "STEP", "line", "ordinal" (1, 2, ... in order within its job; within a PROC definition the
    numbering restarts at 1), "step" (the step name), "program" (PGM=), "proc" (PROC=x, or the procedure named as
    the first positional operand), "cond" (COND= as written), "if_cond" (the condition of each enclosing
    `IF ... THEN`, as written between IF and THEN; inside the ELSE branch write "NOT " before it; nested ones
    joined with " AND "), "in_proc" (the name of the PROC being defined -- between a PROC statement and PEND, or in
    a member that starts with a PROC statement -- else null).
  - DD with a DSN: "kind": "DD", "line", "step" (the current step name; for an override `//PROCSTEP.DDNAME` the
    PROCSTEP), "dd" (the DD name; an unnamed concatenation DD takes the name of the DD above it), "dsn" (upper
    case, without a trailing GDG generation like (+1) / (0) / (-1)), "disp" (the first DISP sub-parameter: NEW /
    OLD / SHR / MOD; NEW when DISP is not coded or its first sub-parameter is omitted, as in DISP=(,CATLG)),
    "generation" ("+1" / "0" / "-1" ..., else null), "in_proc" (as for EXEC).

Files:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"selects": [...], "vsam": [...], "flow": [...]}}, ...every file above...}}}}
"""
    return brief, truth


def grade(truth: dict[str, Any], answers: dict[str, Any], repo: Path) -> dict[str, Any]:
    got = reviewer_facts_files(answers, repo) if truth.get("suite") == "files" else reviewer_facts(answers, repo)
    out: dict[str, Any] = {"tasks": {}, "disagreements": []}
    for task, per_file in truth["facts"].items():
        if task in CORPUS_WIDE and not truth.get("wide"):
            continue
        paths = set(per_file) | (set(got[task]) if task in CORPUS_WIDE else set())
        agree = asked = 0
        for p in sorted(paths):
            want, have = set(per_file.get(p, [])), got[task].get(p, set())
            for item in sorted(want | have):
                asked += 1
                if item in want and item in have:
                    agree += 1
                else:
                    out["disagreements"].append(
                        {
                            "id": f"{task}:{p}::{item}",
                            "task": task,
                            "key": "present" if item in want else "absent",
                            "reviewer": "present" if item in have else "absent",
                        }
                    )
        out["tasks"][task] = {"agree": agree, "asked": asked}
    return out


def sign(
    key: dict[str, Any],
    truth: dict[str, Any],
    g: dict[str, Any],
    rulings: dict[str, Any],
    by: str,
    at: Optional[str] = None,
) -> dict[str, Any]:
    unruled = [d["id"] for d in g["disagreements"] if d["id"] not in rulings]
    if unruled:
        sys.exit(f"{len(unruled)} disagreement(s) have no ruling in rulings.json: {unruled[:5]}")
    still = [d["id"] for d in g["disagreements"] if rulings[d["id"]].get("verdict") == "key_fixed"]
    if still:
        sys.exit(f"ruled key_fixed but the current key still disagrees: {still[:5]}")
    bad = [i for i, r in rulings.items() if r.get("verdict") not in ("key_correct", "key_fixed") or not r.get("why")]
    if bad:
        sys.exit(f"rulings need verdict key_correct|key_fixed and a why: {bad[:5]}")
    at = at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Read twice, blind, with every disagreement settled: the program census tier.
    stamp = {"status": "validated", "tier": "cross_verified", "cross_by": by, "census": {"by": by, "at": at}}
    per_file = set(FILE_SECTIONS.values()) if truth.get("suite") == "files" else {SECTIONS[t] for t in PER_FILE}
    for rel in truth["files"]:
        for section, flag in per_file:
            entry = key.get(section, {}).get(rel)
            if entry is not None:
                entry[flag] = True
                entry["verification"] = dict(entry.get("verification", {}), **stamp)
    if truth.get("wide"):
        for section, flag in {SECTIONS[t] for t in CORPUS_WIDE}:
            for entry in key.get(section, {}).values():
                entry[flag] = True
                entry["verification"] = dict(entry.get("verification", {}), **stamp)
    key.setdefault("section_census", []).append(
        {
            "by": by,
            "at": at,
            "batch": truth["batch"],
            "files": truth["files"],
            "wide": truth.get("wide", False),
            "suite": truth.get("suite", "channels"),
            "tasks": g["tasks"],
            "rulings": {i: rulings[i] for i in sorted(rulings)},
        }
    )
    return key


def coverage(key: dict[str, Any], files: list[str], suite: str = "channels") -> dict[str, Any]:
    recs = [r for r in key.get("section_census", []) if r.get("suite", "channels") == suite]
    done = {f for rec in recs for f in rec["files"]}
    # The files suite has no corpus-wide task.
    wide = suite == "files" or any(rec.get("wide") for rec in recs)
    return {"files": [len(done & set(files)), len(files)], "wide": wide, "missing": sorted(set(files) - done)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("census")
    c.add_argument("--corpus", required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--stage", type=Path, required=True)
    c.add_argument("--max-items", type=int, default=70)
    c.add_argument("--suite", choices=("channels", "files"), default="channels")
    cov = sub.add_parser("coverage")
    cov.add_argument("--corpus", required=True)
    cov.add_argument("--suite", choices=("channels", "files"), default="channels")
    for name in ("grade", "sign"):
        s = sub.add_parser(name)
        s.add_argument("--corpus", required=True)
        s.add_argument("--dir", type=Path, required=True)
        if name == "sign":
            s.add_argument("--by", required=True)
    args = ap.parse_args()

    (corpus,) = mc.select([args.corpus])
    key = load_key(corpus)
    repo = mc.require_clone(corpus)
    suite = getattr(args, "suite", "channels")
    files = corpus_files_files(repo) if suite == "files" else corpus_files(repo)
    if args.cmd == "coverage":
        cv = coverage(key, files, suite)
        print(
            f"{corpus['name']}: {suite} census covers {cv['files'][0]}/{cv['files'][1]} files; corpus-wide: {cv['wide']}"
        )
        return 0 if not cv["missing"] and cv["wide"] else 1
    if args.cmd == "census":
        staged = args.stage.resolve() / corpus["name"]
        if staged.exists():
            shutil.rmtree(staged)
        shutil.copytree(repo, staged, ignore=shutil.ignore_patterns(".git"))
        packed = batches_files(key, files, args.max_items) if suite == "files" else batches(key, files, args.max_items)
        for i, batch in enumerate(packed, 1):
            d = args.out / f"batch_{i:02d}"
            d.mkdir(parents=True, exist_ok=True)
            make = render_files if suite == "files" else render
            brief, truth = make(key, staged, batch, i, len(packed))
            (d / "brief.md").write_text(brief, encoding="utf-8")
            (d / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
            n = sum(len(v) for t in truth["facts"].values() for v in t.values())
            print(f"{d}: {len(batch)} files, {n} key facts")
        return 0

    truth = json.loads((args.dir / "truth.json").read_text(encoding="utf-8"))
    root = Path(truth["root"])
    answers = parse_answers((args.dir / "answers.json").read_text(encoding="utf-8"))
    if args.cmd == "grade":
        g = grade(truth, answers, root)
        (args.dir / "grade.json").write_text(json.dumps(g, indent=2) + "\n", encoding="utf-8")
        lines = [
            f"# Section census: {corpus['name']} batch {truth['batch']}",
            "",
            "| task | agree | asked |",
            "|---|---|---|",
        ]
        lines += [f"| {t} | {v['agree']} | {v['asked']} |" for t, v in g["tasks"].items()]
        lines += ["", f"**{len(g['disagreements'])} disagreement(s)**:", ""]
        lines += [f"- `{d['id']}` -- key: {d['key']}, reviewer: {d['reviewer']}" for d in g["disagreements"]]
        md = "\n".join(lines) + "\n"
        (args.dir / "grade.md").write_text(md, encoding="utf-8")
        print(md)
        return 0 if not g["disagreements"] else 1
    # sign: re-grade the same questions against the CURRENT key.
    if truth.get("suite") == "files":
        current = dict(truth, facts=key_facts_files(key, truth["files"]))
    else:
        current = dict(truth, facts=key_facts(key, truth["files"], truth.get("wide", False)))
    g = grade(current, answers, root)
    rulings_path = args.dir / "rulings.json"
    rulings = json.loads(rulings_path.read_text(encoding="utf-8")) if rulings_path.is_file() else {}
    signed = sign(key, truth, g, rulings, args.by)
    (REPO_ROOT / corpus["answer_key"]).write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
    print(f"{corpus['answer_key']}: batch {truth['batch']} signed by {args.by} ({len(truth['files'])} files)")
    return 0


# Exported for tests.
__all__: list[Callable[..., Any] | str] = ["batches", "canon_uow", "grade", "key_facts", "render", "sign"]

if __name__ == "__main__":
    sys.exit(main())
