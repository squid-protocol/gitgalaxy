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

    python tests/tools/cross_verify_sections.py census   --corpus NAME --out DIR --stage DIR [--max-items 70] [--suite channels|files|calls]
    python tests/tools/cross_verify_sections.py grade    --corpus NAME --dir DIR/batch_NN
    python tests/tools/cross_verify_sections.py sign     --corpus NAME --dir DIR/batch_NN --by "REVIEWER"
    python tests/tools/cross_verify_sections.py coverage --corpus NAME [--suite channels|files|calls]

SUITES. `channels` (the default) is the six sections above, asked of every COBOL
source. `files` (#3455 / #3451) is the file-definition sections, asked of every
COBOL program and JCL member:

    file_control      file_control_validated   each FILE-CONTROL SELECT's clauses and FD COPYs
    vsam_defines      vsam_validated           IDCAMS DEFINE CLUSTER / AIX / PATH
    job_flow          jobflow_validated        JCL JOB / STEP / DSN-DD rows

`calls` (#3454 / #3450) is asked of every COBOL source:

    call_using        call_using_validated     CALL USING lists, PROCEDURE DIVISION / ENTRY USING
    dli_calls         dli_validated            DL/I calls as written, and the IMS segment access

`lineage` (#3477 / #3452) pairs a full census with a SAMPLED one:

    ims_gen           ims_gen_validated        PSB / DBD macros, JCL IMS regions, the access check
                                               (every entry of the section, asked in full)
    data_moves        data_moves_validated     MOVE / COMPUTE / ... rows and MOVE truncation --
                                               ~10k facts, so asked over a seeded, stratified SAMPLE
                                               of 12-line windows (see lineage_plan)

`io` (#3492) is asked of every COBOL source with a FILE SECTION, an ACCEPT, or
keyed rows, in full:

    io_moves          io_moves_validated       READ / RETURN INTO, WRITE / REWRITE / RELEASE FROM, ACCEPT

`dynamic` (#3493) is asked of every COBOL program with a LINK / XCTL / CALL, in full:

    dynamic_targets   dynamic_validated        the programs a data-name LINK / XCTL / CALL can name

`web` (#3496) is asked of every JCL member, in full:

    web_services      web_validated            web-services assistant steps (the API surface)

`jcics` (#3497) is asked of every Java source that imports com.ibm.cics.server, in full:

    jcics             jcics_validated          JCICS LINKs and file / queue / channel / container operations

`resources` (#3351-#3354 / #3495) is asked of every COBOL and HLASM source issuing EXEC CICS:

    cics_resources    cics_validated           FILE / QUEUE / MAP / CONTAINER / CHANNEL operations
    (an HLASM source also answers cics_tasks and uow_handlers here -- COBOL answers them in `channels`)

The data-move sample is fixed when the census is cut and stored in the key under
`sample_census.data_moves.plan`: windows around truncation claims and around the
rarer verbs (so every contract clause is exercised), then random windows over all
procedure code, empty ones included (recall). A reviewer lists every row whose
verb sits in a window. Signing a batch records it under `sample_census`; once
every planned window is signed, every data_moves entry gets the flag with tier
`sample_verified` -- the weakest tier: a blind second reading of a sample, with the
observed disagreement count and a 95% upper bound on the key's error rate.

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
import random
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


# ---- the `calls` suite (#3454 / #3450) ------------------------------------------
CALL_TASKS = ("using", "dli", "ims")
CALL_SECTIONS = {
    "using": ("call_using", "call_using_validated"),
    "dli": ("dli_calls", "dli_validated"),
    "ims": ("dli_calls", "dli_validated"),
}


def _args_list(v: Any) -> str:
    """A positional argument list, order kept: blanks collapsed, upper-cased."""
    if not v:
        return "-"
    items = v.split(",") if isinstance(v, str) else list(v)
    return ",".join(_ws(x) for x in items if str(x).strip()) or "-"


def canon_using(r: dict[str, Any]) -> str:
    return f"L{int(r.get('line') or 0)} {_ws(r.get('kind'))} {_d(r.get('name'))} USING {_args_list(r.get('args'))}"


# The access the brief defines for each DL/I function: a reviewer who answers with
# the function (GN) instead of its access (read) states the same fact.
_DLI_ACCESS = {
    "GU": "read", "GHU": "read", "GN": "read", "GHN": "read", "GNP": "read", "GHNP": "read",
    "ISRT": "insert", "REPL": "update", "DLET": "delete",
}  # fmt: skip


def _io_operand(v: Any) -> Any:
    """`INTO(X)` / `FROM(X)` -> `X`: the option keyword around the operand says nothing more."""
    m = re.fullmatch(r"\s*(?:INTO|FROM)\s*\(\s*(.*?)\s*\)\s*", str(v), re.I) if v else None
    return m.group(1) if m else v


def canon_dli(r: dict[str, Any]) -> str:
    where = ";".join(_nsp(w) for w in r.get("where") or []) or "-"
    return (
        f"L{int(r.get('line') or 0)} {_ws(r.get('interface'))} FN={_d(r.get('function') or r.get('operand'))} "
        f"PCB={_d(r.get('pcb'))} IO={_d(_io_operand(r.get('io')))} SEG={_args_list(r.get('segs'))} WHERE={where} "
        f"PSB={_d(r.get('psb'))}"
    )


def key_facts_calls(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {t: {} for t in CALL_TASKS}
    for rel in files:
        out["using"][rel] = sorted({canon_using(r) for r in key.get("call_using", {}).get(rel, {}).get("rows", [])})
        dl = key.get("dli_calls", {}).get(rel, {})
        out["dli"][rel] = sorted({canon_dli(r) for r in dl.get("calls", [])})
        out["ims"][rel] = sorted(
            {_ws(a).lower().split(" ", 1)[0] + " " + _ws(a).split(" ", 1)[1] for a in dl.get("segment_access", [])}
        )
    return out


def reviewer_facts_calls(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    def rel(p: str) -> str:
        root = str(repo).rstrip("/") + "/"
        return p[len(root) :] if p.startswith(root) else p

    out: dict[str, dict[str, set[str]]] = {t: {} for t in CALL_TASKS}
    for path, v in (answers.get("files") or {}).items():
        r, v = rel(path), v or {}
        out["using"][r] = {canon_using(x) for x in v.get("using", []) if isinstance(x, dict)}
        out["dli"][r] = {
            canon_dli(
                {
                    "line": x.get("line"),
                    "interface": x.get("interface"),
                    "function": x.get("function"),
                    "operand": x.get("function_operand"),
                    "pcb": x.get("pcb"),
                    "io": x.get("io_area"),
                    "segs": (x.get("segments") or []) + (x.get("ssas") or []),
                    "where": x.get("where") or [],
                    "psb": x.get("psb"),
                }
            )
            for x in v.get("dli", [])
            if isinstance(x, dict)
        }
        out["ims"][r] = {
            f"{_DLI_ACCESS.get(_ws(x.get('access')), str(x.get('access', '')).strip().lower())} {_ws(x.get('segment'))}"
            for x in v.get("ims", [])
            if isinstance(x, dict)
        }
    return out


def batches_calls(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    facts = key_facts_calls(key, files)
    load = {f: 1 + sum(len(facts[t].get(f, [])) for t in CALL_TASKS) for f in files}
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


def render_calls(key: dict[str, Any], repo: Path, files: list[str], index: int, of: int) -> tuple[str, dict[str, Any]]:
    truth = {
        "corpus": key["corpus"],
        "ref": key["ref"],
        "root": str(repo),
        "mode": "section_census",
        "suite": "calls",
        "batch": index,
        "of": of,
        "files": files,
        "facts": key_facts_calls(key, files),
    }
    listing = "\n".join(str(repo / f) for f in files)
    brief = f"""You are independently verifying facts about real IBM mainframe COBOL source code, as a second reviewer.
Read the source files yourself. They are all under the repository root {repo}; read only inside that directory
(a COBOL program's copybooks are other files in it). Do NOT edit or create any files except your answers file, and
do not look for any existing answer key or analysis of this code: the point is an independent reading. Line numbers
are 1-based physical line numbers. Ignore comment lines, text inside quoted literals (DISPLAY 'CALL X' is no call),
and columns 73-80.

{FIXED_FORMAT_RULES}

For EACH file below answer the three tasks; an empty list when a file has none.

TASK USING -- one entry per:
  - CALL statement that has a USING list: "kind": "CALL", "line" (of the word CALL), "name" (the called program
    exactly as written: a literal's text without quotes, or the data-name), "args": the USING items in order.
  - PROCEDURE DIVISION that has a USING list: "kind": "PROCEDURE", "line", "name": null, "args".
  - ENTRY 'X' statement: "kind": "ENTRY", "line", "name": "X", "args" (null when it has no USING).
  Each arg: the data-name upper-case, a qualification kept as `A OF B`, subscripts / reference modifiers dropped;
  after BY CONTENT or BY VALUE prefix each following item "CONTENT:" / "VALUE:" until another BY (BY REFERENCE
  is the default, no prefix); `ADDRESS OF X`, `LENGTH OF X`, `OMITTED` and quoted literals (quotes kept) as written.
  The list ends at RETURNING, ON / NOT ON (EXCEPTION / OVERFLOW), END-CALL, a period, or the next statement.

TASK DLI -- one entry per IMS call, operands exactly as written:
  - EXEC DLI: "interface": "EXEC", "line", "function" (the command: GU / GN / GNP / ISRT / REPL / DLET / SCHD /
    TERM / CHKP ...), "pcb" (the PCB(...) operand), "io_area" (INTO(...) or FROM(...)), "segments" (every
    SEGMENT(...) operand in order), "where" (every WHERE(...) text in order), "psb" (SCHD PSB(...), extra
    parentheses removed); null / [] where not coded.
  - CALL 'CBLTDLI' (or 'AIBTDLI'): "interface": "CALL", "line", "function_operand" (1st USING item), "pcb" (2nd),
    "io_area" (3rd), "ssas" (the remaining items in order).

TASK IMS -- which IMS segments the file accesses and how: one {{"access": .., "segment": ..}} per distinct pair.
  access: GU / GHU / GN / GHN / GNP / GHNP read, ISRT insert, REPL update, DLET delete (SCHD / TERM / CHKP none).
  For a CALL 'CBLTDLI' the function is the VALUE of its function operand (usually in a copybook) and each segment is
  the first 8 characters of the SSA's load-time value -- a group's elementary VALUEs concatenated, each padded or cut
  to its PIC width (an SSA whose first 8 characters are unknown names no segment). For EXEC DLI the segments are its
  SEGMENT(...) names. When a call names several segments (a path), the LAST gets the access and the ones before it
  are "read".

Files:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"using": [...], "dli": [...], "ims": [...]}}, ...every file above...}}}}
"""
    return brief, truth


# ---- the `lineage` suite (#3477 / #3452) ----------------------------------------
LINEAGE_TASKS = ("imsdef", "imscheck", "moves", "trunc")
WINDOW = 12  # lines per data-move window
_IMS_FIELDS = ("name", "parent", "owner", "dbd", "procopt", "type", "access", "bytes", "start", "psb", "program")


def canon_ims_row(r: dict[str, Any]) -> str:
    """`L<line> KIND field=value ...` over the set fields (the key's ims_gen_keys form)."""
    parts = []
    for f in _IMS_FIELDS:
        v = r.get(f)
        if v in (None, "", []):
            continue
        parts.append(f"{f}={int(v) if f in ('bytes', 'start') else _ws(v)}")
    return f"L{int(r.get('line') or 0)} {_ws(r.get('kind'))} " + " ".join(parts)


def canon_ims_check(segment: Any, status: Any, pcbs: list) -> str:
    hits = sorted(
        f"{_ws(p.get('psb'))}/{_ws(p.get('pcb'))}"
        + (":" + "+".join(sorted(str(d).strip().lower() for d in p.get("denied") or [])) if p.get("denied") else "")
        for p in pcbs
        if isinstance(p, dict)
    )
    return f"{_ws(segment)} {str(status).strip().lower()} {','.join(hits) or '-'}"


def _recanon_check(line: str) -> str:
    """The key's access-check string with its PCB list sorted (reviewer order is free)."""
    seg, status, hits = line.split(" ", 2)
    pcbs = []
    for h in [] if hits == "-" else hits.split(","):
        ref, _, denied = h.partition(":")
        psb, _, pcb = ref.partition("/")
        pcbs.append({"psb": psb, "pcb": pcb, "denied": denied.split("+") if denied else []})
    return canon_ims_check(seg, status, pcbs)


def _mv_side(text: Any, refmod: Any) -> str:
    if text in (None, "", "-"):
        return "-"
    t = _ws(text)
    if not re.match(r"[XNGZ]?['\"]|ALL\s", t):  # a literal keeps its text
        t = re.sub(r"\s+IN\s+", " OF ", t)
    return t + ("(:)" if refmod else "")


def canon_move(r: dict[str, Any]) -> str:
    verb = _ws(r.get("verb")) + (" CORR" if r.get("corresponding") else "")
    src = _mv_side(r.get("source"), r.get("source_refmod"))
    return f"L{int(r.get('line') or 0)} {verb} {src} -> {_mv_side(r.get('target'), r.get('target_refmod'))}"


def canon_trunc(r: dict[str, Any]) -> str:
    return f"L{int(r.get('line') or 0)} {_mv_side(r.get('source'), False)} -> {_mv_side(r.get('target'), False)}"


def _line_of(fact: str) -> int:
    return int(fact.split(" ", 1)[0][1:])


def _wid(w: dict[str, Any]) -> str:
    return f"{w['file']}@{w['from']}-{w['to']}"


def _window_facts(key: dict[str, Any], w: dict[str, Any]) -> tuple[list[str], list[str]]:
    entry = key.get("data_moves", {}).get(w["file"], {})
    moves = sorted({_ws(m) for m in entry.get("moves", []) if w["from"] <= _line_of(m) <= w["to"]})
    trunc = sorted({_ws(t) for t in entry.get("truncations", []) if w["from"] <= _line_of(t) <= w["to"]})
    return moves, trunc


def lineage_plan(key: dict[str, Any], repo: Path, budget: int, seed: int) -> list[dict[str, Any]]:
    """The data-move sample: 12-line windows, non-overlapping per file, until about
    `budget` key facts are covered. Anchors, in order: up to 15 truncation claims,
    up to 4 rows of each rarer form (COMPUTE, arithmetic, STRING, UNSTRING,
    INITIALIZE, MOVE CORR, reference modification), then random procedure lines of
    every program's procedure division and every copybook of procedure statements
    (a window with no rows checks recall)."""
    rng = random.Random(f"{seed}:{key['corpus']}")
    dm = key.get("data_moves", {})
    lengths: dict[str, tuple[int, int]] = {}
    for rel in corpus_files(repo):
        lines = (repo / rel).read_text(encoding="utf-8", errors="ignore").split("\n")
        start = next((i + 1 for i, ln in enumerate(lines) if re.search(r"PROCEDURE\s+DIVISION", ln[6:72], re.I)), None)
        if start is not None or rel in dm:  # a data-only copybook can hold no statement
            lengths[rel] = (start or 1, len(lines))
    anchors: list[tuple[str, int]] = []
    trunc = sorted((rel, _line_of(t)) for rel, e in dm.items() for t in e.get("truncations", []))
    anchors += rng.sample(trunc, min(15, len(trunc)))
    rows = sorted((rel, m) for rel, e in dm.items() for m in e.get("moves", []))
    forms = [
        lambda m: " COMPUTE " in m,
        lambda m: re.search(r" (?:ADD|SUBTRACT|MULTIPLY|DIVIDE) ", m) is not None,
        lambda m: " STRING " in m,
        lambda m: " UNSTRING " in m,
        lambda m: " INITIALIZE " in m,
        lambda m: " CORR " in m,
        lambda m: "(:)" in m,
    ]
    for test in forms:
        hits = [(rel, _line_of(m)) for rel, m in rows if test(m)]
        anchors += rng.sample(hits, min(4, len(hits)))
    procedure = [(rel, n) for rel, (a, b) in lengths.items() for n in range(a, b + 1)]
    rng.shuffle(procedure)
    windows: list[dict[str, Any]] = []
    covered = 0
    for rel, line in anchors + procedure:
        if covered >= budget:
            break
        if rel not in lengths:
            continue
        lo = max(1, line - 4)
        hi = min(lengths[rel][1], lo + WINDOW - 1)
        if any(w["file"] == rel and not (hi < w["from"] or lo > w["to"]) for w in windows):
            continue
        w = {"file": rel, "from": lo, "to": hi}
        moves, tr = _window_facts(key, w)
        windows.append(w)
        covered += 1 + len(moves) + len(tr)
    return sorted(windows, key=lambda w: (w["file"], w["from"]))


def key_facts_lineage(key: dict[str, Any], files: list[str], windows: list[dict[str, Any]]) -> dict[str, dict]:
    out: dict[str, dict[str, list[str]]] = {t: {} for t in LINEAGE_TASKS}
    for rel in files:
        e = key.get("ims_gen", {}).get(rel, {})
        if "rows" in e:
            out["imsdef"][rel] = sorted({canon_ims_row(r) for r in e["rows"]})
        else:
            out["imscheck"][rel] = sorted({_recanon_check(x) for x in e.get("access_check", [])})
    for w in windows:
        out["moves"][_wid(w)], out["trunc"][_wid(w)] = _window_facts(key, w)
    return out


def reviewer_facts_lineage(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    def rel(p: str) -> str:
        root = str(repo).rstrip("/") + "/"
        return p[len(root) :] if p.startswith(root) else p

    out: dict[str, dict[str, set[str]]] = {t: {} for t in LINEAGE_TASKS}
    for path, v in (answers.get("files") or {}).items():
        r, v = rel(path), v or {}
        if "imsdef" in v:
            out["imsdef"][r] = {canon_ims_row(x) for x in v.get("imsdef") or [] if isinstance(x, dict)}
        if "imscheck" in v:
            out["imscheck"][r] = {
                canon_ims_check(x.get("segment"), x.get("status"), x.get("pcbs") or [])
                for x in v.get("imscheck") or []
                if isinstance(x, dict)
            }
    for wid, v in (answers.get("windows") or {}).items():
        w, rows = rel(wid), [x for x in (v or {}).get("moves") or [] if isinstance(x, dict)]
        out["moves"][w] = {canon_move(x) for x in rows}
        out["trunc"][w] = {canon_trunc(x) for x in rows if x.get("truncates") is True}
    return out


def render_lineage(
    key: dict[str, Any], repo: Path, files: list[str], windows: list[dict[str, Any]], index: int, of: int
) -> tuple[str, dict[str, Any]]:
    truth = {
        "corpus": key["corpus"],
        "ref": key["ref"],
        "root": str(repo),
        "mode": "section_census",
        "suite": "lineage",
        "batch": index,
        "of": of,
        "files": files,
        "windows": windows,
        "facts": key_facts_lineage(key, files, windows),
    }
    parts = [
        f"""You are independently verifying facts about real IBM mainframe source code, as a second reviewer.
Read the source files yourself. They are all under the repository root {repo}; read only inside that directory
(a COBOL program's copybooks are other files in it). Do NOT edit or create any files except your answers file, and
do not look for any existing answer key or analysis of this code: the point is an independent reading. Line numbers
are 1-based physical line numbers. Ignore comment lines, text inside quoted literals, and columns 73-80.

{FIXED_FORMAT_RULES}
"""
    ]
    if files:
        listing = "\n".join(str(repo / f) for f in files)
        parts.append(
            f"""
PART A -- IMS DEFINITIONS. For each file below:

If it is a PSB or DBD generation source (assembler macros; `*` in column 1 is a comment; a non-blank column 72
continues the statement, the next line resuming at column 16) or a JCL member, answer "imsdef": one entry per
PSBGEN / PCB / SENSEG / DBD / SEGM / FIELD / LCHILD / DATASET macro statement, and per JCL
`EXEC PGM=DFSRRC00,PARM=...` step. Each: "kind" (the macro name, or "REGION" for the JCL step), "line" (where the
statement starts), and ONLY these fields (omit or null the rest), values upper-case and as written:
  - PCB: "name" (its label; PCBNAME= when unlabeled; else "PCB@<line>"), "type" (TYPE=), "dbd" (DBDNAME=, or NAME=),
    "procopt" (PROCOPT=)
  - SENSEG: "name" (NAME=), "parent" (PARENT=, the first name inside any parentheses; `0` as written),
    "owner" (the PCB above it, named as above), "procopt" (its own PROCOPT= if coded)
  - PSBGEN: "name" (PSBNAME=)
  - DBD: "name" (NAME=), "access" (the FIRST value of ACCESS=, e.g. HIDAM for ACCESS=(HIDAM,VSAM))
  - SEGM: "name", "parent" (first name inside PARENT=, `0` as written), "owner" (the DBD above), "bytes" (the first
    number of BYTES= as an integer)
  - FIELD: "name" (the first name in NAME=), "parent" (the SEGM above), "owner" (the DBD above), "access": "SEQ" when
    NAME=(x,SEQ,...) else null, "start" and "bytes" (integers)
  - LCHILD: "name" (first name in NAME=(seg,dbd)), "parent" (the SEGM above), "owner" (the DBD), "dbd" (the second)
  - DATASET: "name" (DD1=), "owner" (the DBD above)
  - REGION: from PARM='TYPE,PROGRAM,PSB,...': "access" (TYPE, e.g. DLI / BMP), "name" and "program" (PROGRAM),
    "psb" (PSB)

If it is a COBOL program, answer "imscheck": one entry per IMS segment the program accesses. Accesses: each EXEC DLI
command's SEGMENT(...) names and each CALL 'CBLTDLI' SSA's segment (the first 8 characters of the SSA's load-time
value; the function is the VALUE of the first USING item); GU / GHU / GN / GHN / GNP / GHNP read, ISRT insert,
REPL update, DLET delete; in a path call the LAST segment gets the access and the ones before it are read. The
program's PSBs: the PSB of any JCL `EXEC PGM=DFSRRC00,PARM='x,PROG,PSB'` whose PROG is this program's PROGRAM-ID,
and each EXEC DLI SCHD PSB(...) (a literal, or a data item's VALUE). PSB sources are PSBGEN members in the
repository. Each entry: "segment", "pcbs": one {{"psb", "pcb" (named as in PART A), "denied": [accesses]}} per PCB of
the program's PSBs that has a SENSEG for this segment, where "denied" lists the program's accesses to the segment
that the PCB's PROCOPT does not allow (PROCOPT letters: A all, G read, I insert, R update, D delete, L / LS load =
insert; e.g. GOTP allows read only), and "status": "no_psb" when none of the program's PSBs is defined in the
repository, else "not_sensitive" when no PCB has the segment, else "denied" when every such PCB denies something,
else "ok".

Files:
{listing}
"""
        )
    if windows:
        listing = "\n".join(f"{repo / w['file']}  lines {w['from']}-{w['to']}" for w in windows)
        parts.append(
            f"""
PART B -- DATA MOVES. For each file + line range below, list EVERY data-moving statement whose verb word (MOVE,
COMPUTE, ADD, SUBTRACT, MULTIPLY, DIVIDE, STRING, UNSTRING, INITIALIZE) is on a line inside the range -- the
statement may continue after the range; statements whose verb is before the range are not listed. Skip anything
inside EXEC ... END-EXEC, comment lines, and debugging lines ('D' in column 7). Only procedure code counts (after
PROCEDURE DIVISION; a copybook without that header is procedure code throughout). Pseudo-text awaiting COPY
REPLACING, like (TAG)-NAME, is not an operand.

One entry per source -> target PAIR:
  {{"line" (of the verb), "verb", "corresponding" (true for MOVE CORR/CORRESPONDING), "source", "source_refmod",
    "target", "target_refmod", "truncates"}}
Operands: data names upper-case with qualifiers as `A OF B` (IN written as OF); subscripts dropped (X(I) is X and
I is no operand); a reference modification X(1:5) is X with *_refmod true. A literal as written with its quotes
('ABC', 16, -1), a figurative constant as written (SPACES, ZERO, ALL '9'), `FUNCTION NAME` (arguments dropped),
`LENGTH OF X` / `ADDRESS OF X`.
Pairs per verb (TARGETS are always data names -- a literal / figurative / function target is no pair):
  - MOVE a TO t1 t2 ...: (a, t) for each target.
  - COMPUTE t1 [ROUNDED] t2 = expr: (x, t) for every DATA NAME x in expr (inside function arguments too; literals,
    function names and LENGTH OF / ADDRESS OF X are not sources) and every target t.
  - ADD / SUBTRACT a b TO|FROM c d: (a, c) (a, d) (b, c) (b, d); with GIVING g: every operand before GIVING -> g.
    MULTIPLY a BY b: (a, b); DIVIDE a INTO|BY b: (a, b); with GIVING / REMAINDER, every operand before GIVING ->
    each GIVING and REMAINDER item. ADD/SUBTRACT CORRESPONDING: no pairs.
  - STRING s1 s2 DELIMITED BY d ... INTO t: (s, t) for each sending item s (literals included); the DELIMITED BY
    operands and POINTER are control, not sources.
  - UNSTRING s DELIMITED BY ... INTO t1 [DELIMITER IN x] [COUNT IN c] t2 ...: (s, t) for each receiving t; the
    delimiters, DELIMITER IN / COUNT IN items, POINTER and TALLYING are not pairs.
  - INITIALIZE t1 t2 [REPLACING ...]: source null for each t.
  A statement ends at a period, the next statement's verb, an END- word, or ON / NOT / INVALID / AT / SIZE.
"truncates" (MOVE only, else null; null too in a copybook without PROCEDURE DIVISION, and when either operand has
reference modification or it is MOVE CORR): true when the target is alphanumeric (a PIC with X or A) or a group
item and the source -- a data item, or a QUOTED literal (its character count) -- is longer than the target, else
false; null for any other source or target, or when a width cannot be told. Widths are ONE occurrence: DISPLAY one
byte per PIC position except S, V and P; COMP-3 / PACKED-DECIMAL digits/2+1; COMP / BINARY 2, 4 or 8 bytes for up
to 4, 9, 18 digits; N / G two bytes each; a group is the sum of its children (COPY members expanded in place,
REDEFINES and 88 / 66 entries adding nothing, an OCCURS child counted times its maximum).

Ranges:
{listing}
"""
        )
    parts.append(
        """
OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative; a window key is
"<path>@<from>-<to>" exactly as listed, e.g. "app/cbl/X.cbl@120-131"):
{"files": {"<path>": {"imsdef": [...]} or {"imscheck": [...]}, ...every PART A file...},
 "windows": {"<path>@<from>-<to>": {"moves": [...]}, ...every PART B range...}}
"""
    )
    return "".join(parts), truth


def batches_lineage(
    key: dict[str, Any], windows: list[dict[str, Any]], max_items: int
) -> list[tuple[list[str], list[dict[str, Any]]]]:
    """IMS files in batch 1 (few), then the windows packed by key facts, per file together."""
    ims = sorted(key.get("ims_gen", {}))
    out: list[tuple[list[str], list[dict[str, Any]]]] = []
    if ims:
        out.append((ims, []))
    cur: list[dict[str, Any]] = []
    size = 0
    for w in windows:
        moves, tr = _window_facts(key, w)
        cost = 1 + len(moves) + len(tr)
        if cur and size + cost > max_items:
            out.append(([], cur))
            cur, size = [], 0
        cur.append(w)
        size += cost
    if cur:
        out.append(([], cur))
    return out


# ---- the `io` suite (#3492) ------------------------------------------------------
def corpus_files_io(key: dict[str, Any], repo: Path) -> list[str]:
    """COBOL sources that could hold file I/O moves: keyed ones, and any with a FILE
    SECTION or an ACCEPT (so a reviewer checks the ones the key says have none)."""
    out = set(key.get("io_moves", {}))
    for rel in corpus_files(repo):
        text = (repo / rel).read_text(encoding="utf-8", errors="ignore").upper()
        if re.search(r"\bFILE\s+SECTION\b|\bACCEPT\s", text):
            out.add(rel)
    return sorted(out)


def key_facts_io(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    return {
        "io": {rel: sorted({_ws(m) for m in key.get("io_moves", {}).get(rel, {}).get("moves", [])}) for rel in files}
    }


def reviewer_facts_io(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    root = str(repo).rstrip("/") + "/"
    out: dict[str, dict[str, set[str]]] = {"io": {}}
    for path, v in (answers.get("files") or {}).items():
        r = path[len(root) :] if path.startswith(root) else path
        out["io"][r] = {canon_move(x) for x in (v or {}).get("io", []) if isinstance(x, dict)}
    return out


def render_io(key: dict[str, Any], repo: Path, files: list[str], index: int, of: int) -> tuple[str, dict[str, Any]]:
    truth = {"corpus": key["corpus"], "ref": key["ref"], "root": str(repo), "mode": "section_census", "suite": "io",
             "batch": index, "of": of, "files": files, "facts": key_facts_io(key, files)}  # fmt: skip
    listing = "\n".join(str(repo / f) for f in files)
    brief = f"""You are independently verifying facts about real IBM mainframe COBOL source code, as a second reviewer.
Read the source files yourself. They are all under the repository root {repo}; read only inside that directory.
Do NOT edit or create any files except your answers file, and do not look for any existing answer key or analysis
of this code: the point is an independent reading. Line numbers are 1-based physical line numbers. Ignore comment
lines, debugging lines ('D' in column 7), text inside quoted literals, EXEC ... END-EXEC blocks, and columns 73-80.

{FIXED_FORMAT_RULES}

For EACH file below list, in "io", one entry per FILE-I/O DATA MOVE in the procedure code (after PROCEDURE
DIVISION; a copybook without that header is procedure code throughout); an empty list when it has none:
  - READ file ... INTO t, RETURN file ... INTO t: {{"line" (of the verb), "verb": "READ" | "RETURN",
    "source": the FILE name as written, "target": t}}. A READ without INTO moves nothing: no entry.
  - WRITE r FROM s, REWRITE r FROM s, RELEASE r FROM s: {{"line", "verb", "source": s, "target": r}}. Without FROM:
    no entry.
  - ACCEPT t [FROM ...]: {{"line", "verb": "ACCEPT", "source": the (at most two) words after FROM, e.g.
    "DATE YYYYMMDD", "TIME", "DAY-OF-WEEK"; "SYSIN" when there is no FROM, "target": t}}.
Operands: data names upper-case with qualifiers as `A OF B`; subscripts dropped; a literal as written with quotes;
a figurative constant as written.

Files:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"io": [...]}}, ...every file above...}}}}
"""
    return brief, truth


def batches_dynamic(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    return _pack({f: len(v) for f, v in key_facts_dynamic(key, files)["dynamic"].items()}, max_items)


def _pack(load: dict[str, int], max_items: int) -> list[list[str]]:
    out: list[list[str]] = []
    sizes: list[int] = []
    for f in sorted(load, key=lambda x: (-load[x], x)):
        cost = 1 + load[f]
        for i, sz in enumerate(sizes):
            if sz + cost <= max_items:
                out[i].append(f)
                sizes[i] += cost
                break
        else:
            out.append([f])
            sizes.append(cost)
    return [sorted(b) for b in out]


def batches_io(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    facts = key_facts_io(key, files)["io"]
    out: list[list[str]] = []
    sizes: list[int] = []
    for f in sorted(files, key=lambda x: (-len(facts.get(x, [])), x)):
        load = 1 + len(facts.get(f, []))
        for i, sz in enumerate(sizes):
            if sz + load <= max_items:
                out[i].append(f)
                sizes[i] += load
                break
        else:
            out.append([f])
            sizes.append(load)
    return [sorted(b) for b in out]


# ---- the `dynamic` suite (#3493) ------------------------------------------------
def corpus_files_dynamic(key: dict[str, Any], repo: Path) -> list[str]:
    """Keyed programs, and every COBOL program with a LINK / XCTL / CALL (recall)."""
    out = set(key.get("dynamic_targets", {}))
    for rel in corpus_files(repo):
        if not rel.lower().endswith((".cbl", ".cob", ".cobol", ".ccp")):
            continue
        text = (repo / rel).read_text(encoding="utf-8", errors="ignore").upper()
        if re.search(r"\b(?:XCTL|LINK)\b|\bCALL\s", text):
            out.add(rel)
    return sorted(out)


def canon_dynamic(r: dict[str, Any]) -> str:
    operand = re.sub(r"\s*\(.*$", "", _ws(r.get("operand")))
    return f"L{int(r.get('line') or 0)} {_ws(r.get('verb'))} {operand} -> {_ws(r.get('program')).strip(chr(39))}"


def key_facts_dynamic(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    dt = key.get("dynamic_targets", {})
    return {"dynamic": {rel: sorted({_ws(t) for t in dt.get(rel, {}).get("targets", [])}) for rel in files}}


def reviewer_facts_dynamic(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    root = str(repo).rstrip("/") + "/"
    out: dict[str, dict[str, set[str]]] = {"dynamic": {}}
    for path, v in (answers.get("files") or {}).items():
        r = path[len(root) :] if path.startswith(root) else path
        facts = set()
        for site in (v or {}).get("dynamic", []):
            if isinstance(site, dict):
                for prog in site.get("programs") or []:
                    facts.add(canon_dynamic(dict(site, program=prog)))
        out["dynamic"][r] = facts
    return out


def render_dynamic(
    key: dict[str, Any], repo: Path, files: list[str], index: int, of: int
) -> tuple[str, dict[str, Any]]:
    truth = {"corpus": key["corpus"], "ref": key["ref"], "root": str(repo), "mode": "section_census",
             "suite": "dynamic", "batch": index, "of": of, "files": files, "facts": key_facts_dynamic(key, files)}  # fmt: skip
    listing = "\n".join(str(repo / f) for f in files)
    brief = f"""You are independently verifying facts about real IBM mainframe COBOL source code, as a second reviewer.
Read the source files yourself. They are all under the repository root {repo}; read only inside that directory
(a program's copybooks are other files in it). Do NOT edit or create any files except your answers file, and do
not look for any existing answer key or analysis of this code: the point is an independent reading. Line numbers
are 1-based physical line numbers. Ignore comment lines, text inside quoted literals, and columns 73-80.

{FIXED_FORMAT_RULES}

For EACH program below, find every EXEC CICS LINK / XCTL PROGRAM(x) and every CALL x whose program operand x is a
DATA NAME (not a quoted literal) -- in the program's procedure code, and in any copybook it brings into its
PROCEDURE DIVISION with COPY or EXEC SQL INCLUDE (line numbers are then the copybook's). For each such site answer
{{"line" (of EXEC / CALL), "verb": "LINK" | "XCTL" | "CALL", "operand": x (subscript dropped), "programs": [...]}}
where "programs" lists every program name x can hold, from exactly these three sources (names upper-case, trimmed):
  1. x's own VALUE clause (x may be defined in a copybook the program COPYs);
  2. when x is an element of an OCCURS table that REDEFINES a group of FILLERs with VALUEs, each occurrence's
     slice of that group's text at x's position (skip blank slices);
  3. every MOVE in the program (and those copybooks) into x: a quoted literal source, or a source data item that
     has a VALUE (its VALUE). A source item with no VALUE adds nothing.
Sites with no program from these sources still get an entry with "programs": [].

Programs:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"dynamic": [...]}}, ...every program above...}}}}
"""
    return brief, truth


# ---- the `web` suite (#3496) ----------------------------------------------------
def corpus_files_web(key: dict[str, Any], repo: Path) -> list[str]:
    """Every JCL member (and any keyed file): the assistant can run from any of them."""
    return sorted(
        set(key.get("web_services", {}))
        | {
            p.relative_to(repo).as_posix()
            for p in repo.rglob("*")
            if p.is_file() and p.suffix.lower() in (".jcl", ".prc", ".proc") and ".git" not in p.parts
        }
    )


def canon_web(r: dict[str, Any]) -> str:
    fields = " ".join(f"{k}={_ws(r[k])}" for k in ("program", "uri", "request", "response", "interface") if r.get(k))
    # One case for both sides: the key's strings are compared upper-cased (_ws).
    return _ws(f"L{int(r.get('line') or 0)} {r.get('assistant') or ''} {r.get('direction') or ''} {fields}")


def key_facts_web(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    ws = key.get("web_services", {})
    return {"web": {rel: sorted({_ws(x) for x in ws.get(rel, {}).get("services", [])}) for rel in files}}


def reviewer_facts_web(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    root = str(repo).rstrip("/") + "/"
    out: dict[str, dict[str, set[str]]] = {"web": {}}
    for path, v in (answers.get("files") or {}).items():
        r = path[len(root) :] if path.startswith(root) else path
        out["web"][r] = {canon_web(x) for x in (v or {}).get("web", []) if isinstance(x, dict)}
    return out


def render_web(key: dict[str, Any], repo: Path, files: list[str], index: int, of: int) -> tuple[str, dict[str, Any]]:
    truth = {"corpus": key["corpus"], "ref": key["ref"], "root": str(repo), "mode": "section_census",
             "suite": "web", "batch": index, "of": of, "files": files, "facts": key_facts_web(key, files)}  # fmt: skip
    listing = "\n".join(str(repo / f) for f in files)
    brief = f"""You are independently verifying facts about real IBM mainframe JCL, as a second reviewer.
Read the files yourself. They are all under the repository root {repo}; read only inside that directory. Do NOT
edit or create any files except your answers file, and do not look for any existing answer key or analysis of this
code: the point is an independent reading. Line numbers are 1-based physical line numbers. Ignore `//*` comment
lines and columns 73-80.

For EACH JCL member below list, in "web", one entry per job step that runs one of IBM's CICS web-services assistants
-- `EXEC DFHLS2WS`, `DFHLS2JS`, `DFHWS2LS` or `DFHJS2LS` (as a procedure, `PROC=`, or `PGM=`); an empty list when it
has none. Each entry:
  {{"line" (of the EXEC), "assistant" (which of the four), "direction": "provider" for DFHLS2WS / DFHLS2JS,
    "requester" for DFHWS2LS / DFHJS2LS, and from the step's in-stream parameters (the KEY=VALUE lines after the
    step's `DD *` / `DD DATA` statement, up to `/*` or the next JCL statement), exactly as written, upper-case:
    "program" (PGMNAME=), "uri" (URI=), "request" (REQMEM=), "response" (RESPMEM=), "interface" (PGMINT=);
    null for a parameter the step does not code}}

JCL members:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"web": [...]}}, ...every member above...}}}}
"""
    return brief, truth


def batches_web(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    return _pack({f: len(v) for f, v in key_facts_web(key, files)["web"].items()}, max_items)


# ---- the `jcics` suite (#3497) ---------------------------------------------------
def corpus_files_jcics(key: dict[str, Any], repo: Path) -> list[str]:
    """Every Java source importing JCICS (and any keyed file)."""
    return sorted(
        set(key.get("jcics", {}))
        | {
            p.relative_to(repo).as_posix()
            for p in repo.rglob("*.java")
            if ".git" not in p.parts and "com.ibm.cics.server" in p.read_text(encoding="utf-8", errors="ignore")
        }
    )


def canon_jcics(r: dict[str, Any]) -> str:
    kind = _ws(r.get("kind"))
    if kind in ("LINK", "PROGRAM"):
        return _ws(f"L{int(r.get('line') or 0)} LINK {r.get('name') or '?'}")
    return _ws(f"L{int(r.get('line') or 0)} {kind} {r.get('name') or '?'} {r.get('access') or ''}")


def key_facts_jcics(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    jc = key.get("jcics", {})
    return {"jcics": {rel: sorted({_ws(x) for x in jc.get(rel, {}).get("calls", [])}) for rel in files}}


def reviewer_facts_jcics(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    root = str(repo).rstrip("/") + "/"
    out: dict[str, dict[str, set[str]]] = {"jcics": {}}
    for path, v in (answers.get("files") or {}).items():
        r = path[len(root) :] if path.startswith(root) else path
        out["jcics"][r] = {canon_jcics(x) for x in (v or {}).get("jcics", []) if isinstance(x, dict)}
    return out


def render_jcics(key: dict[str, Any], repo: Path, files: list[str], index: int, of: int) -> tuple[str, dict[str, Any]]:
    truth = {"corpus": key["corpus"], "ref": key["ref"], "root": str(repo), "mode": "section_census",
             "suite": "jcics", "batch": index, "of": of, "files": files, "facts": key_facts_jcics(key, files)}  # fmt: skip
    listing = "\n".join(str(repo / f) for f in files)
    brief = f"""You are independently verifying facts about real Java source code that runs on IBM CICS, as a second
reviewer. Read the files yourself. They are all under the repository root {repo}; read only inside that directory.
Do NOT edit or create any files except your answers file, and do not look for any existing answer key or analysis
of this code: the point is an independent reading. Line numbers are 1-based physical line numbers. Ignore comments.

The CICS Java API (JCICS, package com.ibm.cics.server) reaches CICS resources through objects. For EACH file below
list, in "jcics", one entry per call of these methods (an empty list when it has none):
  - on an object of type Program (declared or created with `new Program()`): `link(...)` ->
    {{"line", "kind": "LINK", "name": the program name}}
  - on a KSDS / ESDS / RRDS (a CICS FILE): read / readForUpdate / readGeneric / readGenericForUpdate -> "read",
    write -> "write", rewrite -> "update", delete -> "delete", startBrowse / startGenericBrowse -> "browse",
    unlock -> "unlock" as {{"line", "kind": "FILE", "name", "access"}}
  - on a TSQ / TDQ (a CICS QUEUE): writeItem / writeItemConditional / writeData / writeString -> "write",
    rewriteItem -> "update", readItem / readNextItem / readData -> "read", delete -> "delete" as
    {{"line", "kind": "QUEUE", "name", "access"}}
  - createChannel(x) -> {{"line", "kind": "CHANNEL", "name": x, "access": "pass"}}
  - createContainer(x) -> {{"line", "kind": "CONTAINER", "name": x, "access": "write"}}; getContainer(x) -> the same
    with "access": "read"
"line" is the line of the method name (a chained call may put it below its object). An object's "name" is the
argument of the most recent `obj.setName(...)` call above the method call on that same variable: a string literal,
or the value of a `static final String` constant in the same file; when it is built by concatenation starting with
a string literal, that literal followed by "*"; otherwise null. For createChannel / createContainer / getContainer
the name is the argument itself when it is a literal or such a constant, else null. A Program link whose name is
not a literal / constant is not listed.

Java files:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"jcics": [...]}}, ...every file above...}}}}
"""
    return brief, truth


def batches_jcics(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    return _pack({f: len(v) for f, v in key_facts_jcics(key, files)["jcics"].items()}, max_items)


# ---- the `resources` suite (#3351-#3354 / #3495) ---------------------------------
# The CICS resource operations (FILE / QUEUE / MAP / CONTAINER / CHANNEL), asked of
# every COBOL and HLASM source that issues EXEC CICS; for an HLASM source also its
# task control and units of work (a COBOL source answers those in `channels`).
HLASM_EXTS = (".asm", ".hlasm", ".assemble")
RESOURCE_SECTIONS = {("cics_resources", "cics_validated")}
HLASM_SECTIONS = {("cics_tasks", "cics_tasks_validated"), ("uow_handlers", "uow_validated")}


def _is_hlasm(rel: str) -> bool:
    return rel.lower().endswith(HLASM_EXTS)


def corpus_files_resources(key: dict[str, Any], repo: Path) -> list[str]:
    """Every COBOL / HLASM source that issues EXEC CICS (and any keyed file)."""
    found = set(key.get("cics_resources", {}))
    for p in repo.rglob("*"):
        if p.is_file() and ".git" not in p.parts and p.suffix.lower() in COBOL_EXTS + HLASM_EXTS:
            if re.search(r"EXEC\s+CICS", p.read_text(encoding="utf-8", errors="ignore"), re.I):
                found.add(p.relative_to(repo).as_posix())
    return sorted(found)


def canon_resource(r: dict[str, Any]) -> str:
    rec = f" {_ws(r.get('record_clause'))}={_d(r.get('record'))}" if r.get("record_clause") else ""
    return (
        f"L{int(r.get('line') or 0)} {_ws(r.get('verb'))} {_ws(r.get('kind'))} N={_d(r.get('name'))} "
        f"Q={_d(r.get('qualifier'))}{rec}"
    )


def key_facts_resources(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    per_channel = key_facts(key, files, wide=False)
    out: dict[str, dict[str, list[str]]] = {"resources": {}, "tasks": {}, "uow": {}}
    for rel in files:
        ops = key.get("cics_resources", {}).get(rel, {}).get("operations", [])
        out["resources"][rel] = sorted({canon_resource(r) for r in ops})
        if _is_hlasm(rel):
            out["tasks"][rel] = per_channel["tasks"][rel]
            out["uow"][rel] = per_channel["uow"][rel]
    return out


def reviewer_facts_resources(answers: dict[str, Any], repo: Path) -> dict[str, dict[str, set[str]]]:
    root = str(repo).rstrip("/") + "/"
    out: dict[str, dict[str, set[str]]] = {"resources": {}, "tasks": {}, "uow": {}}
    for path, v in (answers.get("files") or {}).items():
        r = path[len(root) :] if path.startswith(root) else path
        v = v or {}
        out["resources"][r] = {canon_resource(x) for x in v.get("resources", []) if isinstance(x, dict)}
        if _is_hlasm(r):
            out["tasks"][r] = {canon_task(x) for x in v.get("tasks", []) if isinstance(x, dict)}
            out["uow"][r] = {canon_uow(x) for x in v.get("uow", []) if isinstance(x, dict)}
    return out


def render_resources(
    key: dict[str, Any], repo: Path, files: list[str], index: int, of: int
) -> tuple[str, dict[str, Any]]:
    truth = {"corpus": key["corpus"], "ref": key["ref"], "root": str(repo), "mode": "section_census",
             "suite": "resources", "batch": index, "of": of, "files": files,
             "facts": key_facts_resources(key, files)}  # fmt: skip
    listing = "\n".join(str(repo / f) + ("   (assembler)" if _is_hlasm(f) else "") for f in files)
    asm = any(_is_hlasm(f) for f in files)
    asm_rules = (
        """
ASSEMBLER (HLASM) FILES (marked "(assembler)" below). A line with `*` (or `.*`) in column 1 is a comment. A
statement continues onto the next line when its column 72 is non-blank; the continuation's text should start in
column 16 (take the whole continuation line's text -- real source drifts a column). Columns 73-80 are a sequence
field, never part of the statement. An `EXEC CICS` command is its whole statement (there is no END-EXEC). A
data-name's fixed value is its constant `NAME DC C'text'` or `NAME DC CLn'text'` (trailing blanks are padding, not
part of the value); `NAME DS ...` reserves storage and fixes no value.

For every ASSEMBLER file also answer:
TASK TASKS -- CICS task-control commands: RUN, START, START ATTACH, FETCH CHILD, FETCH ANY, FREE CHILD, RETRIEVE,
CANCEL, DELAY, POST, WAIT EVENT, WAIT EXTERNAL, WAITCICS, ENQ, DEQ. One entry each: "line" (of `EXEC CICS`), "verb",
"target" (TRANSID for RUN/START/START ATTACH/CANCEL, RESOURCE for ENQ/DEQ) only when the source fixes it -- a
literal or the operand's DC constant -- else null; "channel" (CHANNEL(...) resolved the same way, else null);
"token" (the operand of CHILD(...) / ANY(...) / REQID(...), else null); "record" (the FROM / INTO / SET operand as
written, else null).
TASK UOW -- one entry each, with "line" (of the EXEC), "kind", "verb", "condition", "target", "target_kind",
"resp_var", "attributes" (null where not given):
  - EXEC CICS SYNCPOINT: kind COMMIT, verb "SYNCPOINT"; SYNCPOINT ROLLBACK: kind ROLLBACK, verb "SYNCPOINT ROLLBACK".
  - HANDLE CONDITION / HANDLE AID / IGNORE CONDITION / PUSH HANDLE / POP HANDLE / HANDLE ABEND as for COBOL:
    kind HANDLE_CONDITION / HANDLE_AID / IGNORE_CONDITION / PUSH_HANDLE / POP_HANDLE / HANDLE_ABEND.
  - EXEC CICS ABEND: kind ABEND, condition the ABCODE (the literal, or the operand's DC constant, else the operand as
    written), attributes the NODUMP / CANCEL options in written order, else null.
  - RESP checks: every OTHER EXEC CICS command coded RESP(v), or NOHANDLE (then v = EIBRESP): kind RESP_CHECK, verb
    the command's first word, resp_var v, condition what is compared against v after the command -- up to the next
    command coded RESP(v) / NOHANDLE again or about 100 lines (labels do not end it) -- as a list of names: a
    DFHRESP(x) reference counts as x; `OC v,v` (which tests v for zero) counts as NORMAL; `CLC v,=F'n'` counts as
    the response numbered n (0 NORMAL, 13 NOTFND, 14 DUPREC, 16 INVREQ, 17 IOERR, 22 LENGERR, 27 PGMIDERR, ...);
    null when nothing tests v in that span.
"""
        if asm
        else ""
    )
    asm_shape = (
        """,
                      "tasks": [{"line": 1, "verb": "START", "target": null, "channel": null, "token": null, "record": null}],
                      "uow": [{"line": 1, "kind": "ABEND", "verb": "ABEND", "condition": "X", "target": null,
                               "target_kind": null, "resp_var": null, "attributes": null}]"""
        if asm
        else ""
    )
    brief = f"""You are independently verifying facts about real IBM mainframe source code (COBOL and assembler that
issue CICS commands), as a second reviewer. Read the source files yourself. They are all under the repository root
{repo}; read only inside that directory. Do NOT edit or create any files except your answers file, and do not look
for any existing answer key or analysis of this code: the point is an independent reading. Line numbers are 1-based
physical line numbers of the file. Ignore commented-out lines and text inside quoted literals.

{FIXED_FORMAT_RULES}
{asm_rules}
For EACH file below answer TASK RESOURCES (a file with none gets an empty list):
TASK RESOURCES -- every EXEC CICS command that names a CICS resource, one entry each: "line" (of `EXEC CICS`),
"verb" (the command's first word), "kind", "name", "qualifier", "record_clause", "record":
  - kind CONTAINER: PUT / GET / MOVE / DELETE with a CONTAINER(...) option; name the container, qualifier the
    CHANNEL(...) value.
  - kind FILE: READ / READNEXT / READPREV / STARTBR / RESETBR / ENDBR / WRITE / REWRITE / DELETE / UNLOCK with a
    FILE(...) or DATASET(...) option (not a DELETE CONTAINER); name that option's value, qualifier null.
  - kind MAP: SEND / RECEIVE with a MAP(...) option; name the map, qualifier the MAPSET(...) value.
  - kind QUEUE: WRITEQ / READQ / DELETEQ with QUEUE(...) or QNAME(...); name the queue, qualifier "TD" when the
    command says TD, else "TS".
  - kind CHANNEL: LINK / XCTL (qualifier the PROGRAM(...) value) or START / RETURN / RUN (qualifier the TRANSID(...)
    value) with a CHANNEL(...) option; name the channel.
  A command naming none of these (SEND TEXT, WRITE OPERATOR, ASKTIME, ...) is not listed. A name or qualifier is a
  value only when the source fixes it: a literal (its text), or a data-name with a fixed value (COBOL: its VALUE
  literal, else the one literal ever MOVEd into it; assembler: its DC constant); otherwise null. "record_clause" is
  the first of INTO / FROM / SET the command codes (null if none), "record" that option's operand as written.

Files:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"resources": [{{"line": 1, "verb": "READ", "kind": "FILE", "name": "F", "qualifier": null,
                                     "record_clause": "INTO", "record": "R"}}]{asm_shape}}}, ...every file above...}}}}
"""
    return brief, truth


def batches_resources(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    facts = key_facts_resources(key, files)
    return _pack({f: sum(len(facts[t].get(f, [])) for t in facts) for f in files}, max_items)


# ---- the `plicalls` suite (#3491): a SAMPLED census of PL/I program call sites ----
# 1,473 DSF files hold ~8,000 call-site facts, so -- like the data-move sample -- a
# seeded, stratified sample of FILES is read in full (CICS-transfer files, CALL-only
# files and files with none, so "nothing here" is checked too). The reviewer reads
# each file alone; the repository-wide rule (a CALL whose target is only ever a
# nested procedure of some other member is an include-internal call, not a program
# call) is a set operation over every file's procedure labels, applied to the
# reviewer's rows here from the plan's `included` list.
PLI_SAMPLE = {"cics": 14, "call": 14, "none": 8}


def _canon_pli_call(r: dict[str, Any]) -> str:
    return f"L{int(r.get('line') or 0)} {_ws(r.get('verb'))} {_d(r.get('operand'))} -> {_d(r.get('target'))}"


def pli_calls_plan(key: dict[str, Any], seed: int) -> list[str]:
    buckets: dict[str, list[str]] = {"cics": [], "call": [], "none": []}
    for rel, entry in sorted(key.get("pli_calls", {}).items()):
        verbs = {r["verb"] for r in entry.get("calls", [])}
        buckets["none" if not verbs else "call" if verbs == {"CALL"} else "cics"].append(rel)
    rng = random.Random(seed)
    return sorted(f for b, n in PLI_SAMPLE.items() for f in rng.sample(buckets[b], min(n, len(buckets[b]))))


def corpus_files_plicalls(key: dict[str, Any]) -> list[str]:
    return list(key.get("sample_census", {}).get("pli_calls", {}).get("plan", {}).get("files", []))


def key_facts_plicalls(key: dict[str, Any], files: list[str]) -> dict[str, dict[str, list[str]]]:
    pc = key.get("pli_calls", {})
    return {"plicalls": {rel: sorted({_canon_pli_call(r) for r in pc.get(rel, {}).get("calls", [])}) for rel in files}}


def reviewer_facts_plicalls(answers: dict[str, Any], repo: Path, included: set[str]) -> dict[str, dict[str, set[str]]]:
    root = str(repo).rstrip("/") + "/"
    out: dict[str, dict[str, set[str]]] = {"plicalls": {}}
    for path, v in (answers.get("files") or {}).items():
        r = path[len(root) :] if path.startswith(root) else path
        rows = [x for x in (v or {}).get("calls", []) if isinstance(x, dict)]
        rows = [x for x in rows if not (_ws(x.get("verb")) == "CALL" and _ws(x.get("target")) in included)]
        out["plicalls"][r] = {_canon_pli_call(x) for x in rows}
    return out


def render_plicalls(
    key: dict[str, Any], repo: Path, files: list[str], index: int, of: int
) -> tuple[str, dict[str, Any]]:
    included = key.get("sample_census", {}).get("pli_calls", {}).get("plan", {}).get("included", [])
    truth = {"corpus": key["corpus"], "ref": key["ref"], "root": str(repo), "mode": "section_census",
             "suite": "plicalls", "batch": index, "of": of, "files": files, "included": included,
             "facts": key_facts_plicalls(key, files)}  # fmt: skip
    listing = "\n".join(str(repo / f) for f in files)
    brief = f"""You are independently verifying facts about real IBM mainframe PL/I source code that runs under CICS,
as a second reviewer. Read the files yourself. They are all under the repository root {repo}; read only the files
listed below. Do NOT edit or create any files except your answers file, and do not look for any existing answer
key or analysis of this code: the point is an independent reading. Line numbers are 1-based physical line numbers.

PL/I READING RULES. `/* ... */` is a comment (it may span lines). A statement ends at `;` (outside a quoted
'literal'). Columns 73-80 of a line may hold a sequence field (e.g. `00001740` or `R0015160`): never code. Names
are case-insensitive (answer them upper-cased) and may contain national letters (Æ Ø Å), digits, `_ @ # $`. A
statement may carry labels (`NAME:`) and may sit after THEN / ELSE / OTHERWISE / WHEN(...) / an ON condition.

For EACH file list, in "calls", every PROGRAM CALL SITE, one entry per statement (an empty list when none):
  - `EXEC CICS LINK` / `EXEC CICS XCTL`: {{"line": the line of EXEC, "verb": "LINK" or "XCTL", "operand": the value
    in PROGRAM(...) -- a literal's text without quotes, or the data name as written -- "target": the literal's text,
    or, for a data name, the string in the `INIT('...')` of its DCL in the same file (null if it has none)}}. No
    PROGRAM option: operand and target null.
  - `EXEC CICS RETURN` / `START` / `RUN` WITH a TRANSID(...) option: verb "RETURN TRANSID" / "START TRANSID" /
    "RUN TRANSID", operand and target as above from TRANSID(...). A RETURN without TRANSID is not listed.
  - `CALL name` (with or without an argument list): only when `name` is NOT a label of a PROCEDURE / PROC or ENTRY
    statement in the same file (`name: PROC ...`) -- a call to one of the file's own procedures is not listed.
    {{"line": the line of CALL, "verb": "CALL", "operand": name, "target": name}}. Judge this file alone.

Files:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after (paths repo-relative):
{{"files": {{"<path>": {{"calls": [{{"line": 1, "verb": "XCTL", "operand": "R0010301", "target": "R0010301"}}]}}, ...every file above...}}}}
"""
    return brief, truth


def batches_plicalls(key: dict[str, Any], files: list[str], max_items: int) -> list[list[str]]:
    return _pack({f: len(v) for f, v in key_facts_plicalls(key, files)["plicalls"].items()}, max_items)


def _sign_pli_sample(key: dict[str, Any], truth: dict[str, Any], g: dict[str, Any], rulings: dict[str, Any],
                     by: str, at: str) -> None:  # fmt: skip
    """Record a PL/I call-site sample batch; once every planned file is signed, flag
    the whole pli_calls section `sample_verified` with the sample's error bound."""
    sc = key["sample_census"]["pli_calls"]
    sc.setdefault("batches", []).append({"by": by, "at": at, "batch": truth["batch"], "files": truth["files"]})
    sc["asked"] = sc.get("asked", 0) + g["tasks"].get("plicalls", {}).get("asked", 0)
    sc["key_errors"] = sc.get("key_errors", 0) + sum(1 for r in rulings.values() if r.get("verdict") == "key_fixed")
    done = {f for b in sc["batches"] for f in b["files"]}
    if all(f in done for f in sc["plan"]["files"]):
        sc["upper_bound_95"] = round(upper_bound_95(sc["key_errors"], sc["asked"]), 5)
        stamp = {"status": "validated", "tier": "sample_verified", "census": {"by": by, "at": at, "sampled": True}}
        for entry in key.get("pli_calls", {}).values():
            entry["pli_calls_validated"] = True
            entry["verification"] = dict(entry.get("verification", {}), **stamp)


def upper_bound_95(errors: int, n: int) -> float:
    """One-sided 95% upper bound on an error rate from `errors` in `n` (Clopper-Pearson
    for 0, else a Wilson score bound): what a clean sample does and does not prove."""
    if n == 0:
        return 1.0
    if errors == 0:
        return 1 - 0.05 ** (1 / n)
    z, p = 1.645, errors / n
    return min(1.0, (p + z * z / (2 * n) + z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5) / (1 + z * z / n))


def grade(truth: dict[str, Any], answers: dict[str, Any], repo: Path) -> dict[str, Any]:
    suite = truth.get("suite")
    got = (
        reviewer_facts_files(answers, repo)
        if suite == "files"
        else reviewer_facts_calls(answers, repo)
        if suite == "calls"
        else reviewer_facts_lineage(answers, repo)
        if suite == "lineage"
        else reviewer_facts_io(answers, repo)
        if suite == "io"
        else reviewer_facts_dynamic(answers, repo)
        if suite == "dynamic"
        else reviewer_facts_web(answers, repo)
        if suite == "web"
        else reviewer_facts_jcics(answers, repo)
        if suite == "jcics"
        else reviewer_facts_resources(answers, repo)
        if suite == "resources"
        else reviewer_facts_plicalls(answers, repo, set(truth.get("included", [])))
        if suite == "plicalls"
        else reviewer_facts(answers, repo)
    )
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
    per_file = (
        set(FILE_SECTIONS.values())
        if truth.get("suite") == "files"
        else set(CALL_SECTIONS.values())
        if truth.get("suite") == "calls"
        else {("ims_gen", "ims_gen_validated")}
        if truth.get("suite") == "lineage"
        else {("io_moves", "io_moves_validated")}
        if truth.get("suite") == "io"
        else {("dynamic_targets", "dynamic_validated")}
        if truth.get("suite") == "dynamic"
        else {("web_services", "web_validated")}
        if truth.get("suite") == "web"
        else {("jcics", "jcics_validated")}
        if truth.get("suite") == "jcics"
        else RESOURCE_SECTIONS
        if truth.get("suite") == "resources"
        else set()  # plicalls: flagged all at once when the sample completes
        if truth.get("suite") == "plicalls"
        else {SECTIONS[t] for t in PER_FILE}
    )
    for rel in truth["files"]:
        # #3495: an assembler source answers its task control and units of work here.
        extra = HLASM_SECTIONS if truth.get("suite") == "resources" and _is_hlasm(rel) else set()
        for section, flag in per_file | extra:
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
    if truth.get("windows"):
        _sign_sample(key, truth, g, rulings, by, at)
    if truth.get("suite") == "plicalls":
        _sign_pli_sample(key, truth, g, rulings, by, at)
    return key


def _sign_sample(
    key: dict[str, Any], truth: dict[str, Any], g: dict[str, Any], rulings: dict[str, Any], by: str, at: str
) -> None:
    """Record a data-move sample batch; once every planned window is signed, flag the
    whole data_moves section `sample_verified` with the sample's error bound. A
    disagreement ruled key_fixed was a key error the sample caught, and counts."""
    sc = key["sample_census"]["data_moves"]
    sc.setdefault("batches", []).append(
        {"by": by, "at": at, "batch": truth["batch"], "windows": [_wid(w) for w in truth["windows"]]}
    )
    asked = sum(g["tasks"].get(t, {}).get("asked", 0) for t in ("moves", "trunc"))
    errors = sum(
        1 for i, r in rulings.items() if r.get("verdict") == "key_fixed" and i.split(":", 1)[0] in ("moves", "trunc")
    )
    sc["asked"] = sc.get("asked", 0) + asked
    sc["key_errors"] = sc.get("key_errors", 0) + errors
    done = {w for b in sc["batches"] for w in b["windows"]}
    if all(_wid(w) in done for w in sc["plan"]["windows"]):
        sc["upper_bound_95"] = round(upper_bound_95(sc["key_errors"], sc["asked"]), 5)
        stamp = {"status": "validated", "tier": "sample_verified", "census": {"by": by, "at": at, "sampled": True}}
        for entry in key.get("data_moves", {}).values():
            entry["data_moves_validated"] = True
            entry["verification"] = dict(entry.get("verification", {}), **stamp)


def coverage(key: dict[str, Any], files: list[str], suite: str = "channels") -> dict[str, Any]:
    recs = [r for r in key.get("section_census", []) if r.get("suite", "channels") == suite]
    if suite == "lineage":
        # IMS: every ims_gen entry; data moves: every planned window.
        files = sorted(key.get("ims_gen", {}))
        plan = key.get("sample_census", {}).get("data_moves", {})
        done_w = {w for b in plan.get("batches", []) for w in b["windows"]}
        missing_w = [_wid(w) for w in plan.get("plan", {}).get("windows", []) if _wid(w) not in done_w]
        done = {f for rec in recs for f in rec["files"]}
        return {
            "files": [len(done & set(files)), len(files)],
            "wide": bool(plan.get("plan")) and not missing_w,
            "missing": sorted(set(files) - done) + missing_w,
        }
    done = {f for rec in recs for f in rec["files"]}
    # Only the channels suite has corpus-wide tasks.
    wide = suite != "channels" or any(rec.get("wide") for rec in recs)
    return {"files": [len(done & set(files)), len(files)], "wide": wide, "missing": sorted(set(files) - done)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("census")
    c.add_argument("--corpus", required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--stage", type=Path, required=True)
    c.add_argument("--max-items", type=int, default=70)
    c.add_argument(
        "--suite",
        choices=("channels", "files", "calls", "lineage", "io", "dynamic", "web", "jcics", "resources", "plicalls"),
        default="channels",
    )
    c.add_argument("--sample-facts", type=int, default=400, help="lineage: key facts the data-move sample covers")
    c.add_argument("--seed", type=int, default=3452, help="lineage: the sample's seed")
    cov = sub.add_parser("coverage")
    cov.add_argument("--corpus", required=True)
    cov.add_argument(
        "--suite",
        choices=("channels", "files", "calls", "lineage", "io", "dynamic", "web", "jcics", "resources", "plicalls"),
        default="channels",
    )
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
    files = (
        corpus_files_files(repo)
        if suite == "files"
        else corpus_files_io(key, repo)
        if suite == "io"
        else corpus_files_dynamic(key, repo)
        if suite == "dynamic"
        else corpus_files_web(key, repo)
        if suite == "web"
        else corpus_files_jcics(key, repo)
        if suite == "jcics"
        else corpus_files_resources(key, repo)
        if suite == "resources"
        else corpus_files_plicalls(key)
        if suite == "plicalls"
        else corpus_files(repo)  # calls: every COBOL source
    )
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
        if suite == "plicalls":
            # #3491: fix the file sample (and the include-internal name set) in the key.
            pc = key.setdefault("sample_census", {}).setdefault("pli_calls", {})
            if not pc.get("batches"):
                pc["plan"] = {"seed": args.seed, "strata": PLI_SAMPLE, "files": pli_calls_plan(key, args.seed),
                              "included": sorted(key.get("pli_calls_included", []))}  # fmt: skip
                (REPO_ROOT / corpus["answer_key"]).write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
            files = corpus_files_plicalls(key)
        if suite == "lineage":
            # The sample is fixed here and stored in the key, so coverage and sign
            # judge completeness against it (re-cutting replaces an unsigned plan).
            sc = key.setdefault("sample_census", {}).setdefault("data_moves", {})
            if not sc.get("batches"):
                windows = lineage_plan(key, repo, args.sample_facts, args.seed)
                sc["plan"] = {"seed": args.seed, "budget": args.sample_facts, "window": WINDOW, "windows": windows}
                (REPO_ROOT / corpus["answer_key"]).write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
            done = {w for b in sc.get("batches", []) for w in b["windows"]}
            todo = [w for w in sc["plan"]["windows"] if _wid(w) not in done]
            signed_ims = {f for r in key.get("section_census", []) if r.get("suite") == "lineage" for f in r["files"]}
            groups = batches_lineage(key, todo, args.max_items)
            groups = [(sorted(set(f) - signed_ims), w) for f, w in groups]
            groups = [g for g in groups if g[0] or g[1]]
            for i, (fs, ws) in enumerate(groups, 1):
                d = args.out / f"batch_{i:02d}"
                d.mkdir(parents=True, exist_ok=True)
                brief, truth = render_lineage(key, staged, fs, ws, i, len(groups))
                (d / "brief.md").write_text(brief, encoding="utf-8")
                (d / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
                n = sum(len(v) for t in truth["facts"].values() for v in t.values())
                print(f"{d}: {len(fs)} IMS files, {len(ws)} windows, {n} key facts")
            return 0
        pack = {
            "files": batches_files,
            "calls": batches_calls,
            "io": batches_io,
            "dynamic": batches_dynamic,
            "web": batches_web,
            "jcics": batches_jcics,
            "resources": batches_resources,
            "plicalls": batches_plicalls,
        }.get(suite, batches)
        packed = pack(key, files, args.max_items)
        for i, batch in enumerate(packed, 1):
            d = args.out / f"batch_{i:02d}"
            d.mkdir(parents=True, exist_ok=True)
            make = {
                "files": render_files,
                "calls": render_calls,
                "io": render_io,
                "dynamic": render_dynamic,
                "web": render_web,
                "jcics": render_jcics,
                "resources": render_resources,
                "plicalls": render_plicalls,
            }.get(suite, render)
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
    elif truth.get("suite") == "calls":
        current = dict(truth, facts=key_facts_calls(key, truth["files"]))
    elif truth.get("suite") == "jcics":
        current = dict(truth, facts=key_facts_jcics(key, truth["files"]))
    elif truth.get("suite") == "web":
        current = dict(truth, facts=key_facts_web(key, truth["files"]))
    elif truth.get("suite") == "dynamic":
        current = dict(truth, facts=key_facts_dynamic(key, truth["files"]))
    elif truth.get("suite") == "io":
        current = dict(truth, facts=key_facts_io(key, truth["files"]))
    elif truth.get("suite") == "lineage":
        current = dict(truth, facts=key_facts_lineage(key, truth["files"], truth.get("windows", [])))
    elif truth.get("suite") == "resources":
        current = dict(truth, facts=key_facts_resources(key, truth["files"]))
    elif truth.get("suite") == "plicalls":
        current = dict(truth, facts=key_facts_plicalls(key, truth["files"]))
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
