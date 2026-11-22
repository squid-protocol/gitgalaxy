#!/usr/bin/env python3
"""The translator's capabilities as an account: what exists, counted from the code, with the zeros left in.

    python tests/tools/capability_ledger.py          # the rows as JSON

progress_report.py puts these rows in progress.json, and progress_slide.py draws them. They replaced hand-typed slide
rows that said "JCL execution: not started" long after the batch forge landed, so nothing here is typed in:

  a count     read from the module or file that defines the capability, at render time
  a state     from the count (`of_state`), or, where IBM publishes no list to count against, from a check of the code
              (`seen`): when the code it names goes away the row falls to "none" instead of going stale

`of` is None where no honest denominator exists, and the row says so rather than showing a percentage. "match" always
means IBM's documentation: `zos` is the count measured on z/OS.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

DET = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det"
FORGE = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "cobol_to_java_batch_forge.py"
STATUS = REPO / "docs" / "language_status"
CASES = REPO / "tests" / "equivalence"
LANGUAGE_FAMILIES = ("CBL", "NUM", "HFP", "EDIT", "FUNC", "DATA", "SORT", "FILE", "SYS")  # not CICS, SQL, LE, DLI, MQ
STATES = ("works", "partial", "extract", "refused", "none")
STATE_LABEL = {"works": "Works", "partial": "Partial", "extract": "Reads only", "refused": "Refused", "none": "Nothing"}
GROUPS = ("COBOL language", "Code pages and national text", "CICS", "Data and messaging", "Batch", "Other languages")
GAUNTLET_BASELINE = REPO / "tests" / "cultural_gauntlet" / "baseline.txt"
ESTATE_BASELINE = REPO / "tests" / "estate_crucible" / "baseline.json"
# the estate crucible's phase 2 ("multicultural", gitgalaxy#3988, its v0.3.0 RELEASING row): EBCDIC members as raw
# exported bytes in cp037 / 273 / 277 / 420 / 930 / 939, Shift-JIS and UTF-8 with and without BOM
MULTICULTURAL_HORRORS = tuple(f"H-{n:04d}" for n in range(35, 50))


def code_pages() -> dict[str, Any]:
    """The EBCDIC pages the scanner decodes, and which of them the generated Java decodes too (a JDK charset name)."""
    from gitgalaxy.core import ebcdic_codecs, ebcdic_dbcs

    ebcdic_codecs.register()
    pages = sorted(ebcdic_codecs.EBCDIC_CODE_PAGES)
    java = 0
    for cp in pages:
        try:
            ebcdic_codecs.java_charset_name(cp)
            java += 1
        except LookupError:
            pass
    dbcs = len(ebcdic_dbcs.DBCS_CODE_PAGES)
    return {"pages": len(pages), "dbcs": dbcs, "sbcs": len(pages) - dbcs, "java": java}


def cultural_gauntlet() -> dict[str, int]:
    """The Cultural Gauntlet's plan (source dialects x data code pages) and its known-failing cells (the CI ratchet)."""
    import cultural_gauntlet as cg

    lines = GAUNTLET_BASELINE.read_text(encoding="utf-8").splitlines() if GAUNTLET_BASELINE.is_file() else []
    failing = sum(1 for ln in lines if ln.strip() and not ln.startswith("#"))
    return {"dialects": len(cg.DIALECTS), "pages": len(cg.PAGES), "failing": failing}


def multicultural_estate() -> tuple[int, int]:
    """(passing, planted) of the estate crucible's multicultural horrors at the pinned release."""
    horrors = (
        (json.loads(ESTATE_BASELINE.read_text(encoding="utf-8")).get("horrors") or {})
        if ESTATE_BASELINE.is_file()
        else {}
    )
    planted = [h for h in MULTICULTURAL_HORRORS if h in horrors]
    return sum(1 for h in planted if horrors[h] == "PASS"), len(planted)


def of_state(done: int, of: int) -> str:
    return "none" if not done else "works" if done == of else "partial"


def seen(path: Path, text: str, state: str) -> str:
    """`state` while the code that earns it is there, else "none"."""
    return state if path.is_file() and text in path.read_text(encoding="utf-8") else "none"


def row(group: str, name: str, have: str, state: str, done: int | None = None, of: int | None = None,
        unit: str = "", note: str = "", found: str = "") -> dict[str, Any]:  # fmt: skip
    """`found`: what a fresh estate's first contact showed about this row ("Gap found by ..." when it made us build it,
    "Tested by ..." when the row already held), with its issues, so the ledger shows the trials' part in it."""
    return {"group": group, "name": name, "have": have, "state": state, "done": done, "of": of, "unit": unit,
            "note": note, "found": found}  # fmt: skip


COPY_MATRIX = REPO / "tests" / "cobol_mainframe" / "test_copy_layout_matrix_8074.py"


def copy_layouts() -> int:
    """Member layouts the COPY layout matrix pins (#8118): the keys of its FILES table, read without importing the test
    (it scans a real estate)."""
    import ast

    if not COPY_MATRIX.is_file():
        return 0
    for node in ast.parse(COPY_MATRIX.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FILES" for t in node.targets):
            return len(getattr(node.value, "keys", []))
    return 0


def register_status(entry: str) -> str | None:
    """The status line of one register entry (MATCHED / ASSUMED / DIFFERS / REFUSED), or None when it is absent."""
    # read the register folder as register() does: a computed file name made the ground-truth input check
    # (change_classifier) take every docs/language_status file for an input
    for f in (STATUS / "register").glob("*.md"):
        if f.stem == entry:
            m = re.search(r'^status:\s*"?([A-Z]+)', f.read_text(encoding="utf-8"), re.M)
            return m[1] if m else None
    return None


def family_counts(rules: list[dict[str, Any]], families: tuple[str, ...]) -> tuple[int, int]:
    """(MATCHED, all) of the rules in `families`."""
    these = [r for r in rules if r.get("family") in families]
    return sum(1 for r in these if r["status"] == "MATCHED"), len(these)


def spec_tables() -> dict[str, int]:
    """The rule tables the cobolrt *Spec.java files are generated from. Their rules are among the catalogued ones."""
    from gitgalaxy.standards.cobol import arith, compare, editing, func, hfp, move, sort_ops, string_ops

    mods = {arith: "ARITH", compare: "COMPARE", editing: "EDITING", func: "FUNC", hfp: "HFP", move: "MOVE",
            sort_ops: "SORT", string_ops: "STRING"}  # fmt: skip
    return {
        "tables": len(mods),
        "rules": sum(len(getattr(m, f"{p}_RULES")) for m, p in mods.items()),
        "vectors": sum(len(getattr(m, f"{p}_VECTORS")) for m, p in mods.items()),
        "matrix_cells": len(move.MOVE_MATRIX) + len(compare.COMPARE_MATRIX),
    }


def cics_commands() -> dict[str, int]:
    import cics_spec_status  # (the listed consumer of the CICS spec: test_cics_spec.py)

    cmds = list(cics_spec_status.spec().values())
    return {
        "all": len(cmds),
        "modelled": sum(1 for c in cmds if c.status == "modelled"),
        "options": sum(len(c.options) for c in cmds),
        "options_refused": sum(len(c.refused or ()) for c in cmds),
    }


def register() -> dict[str, int]:
    """The register of named limits, from each entry's front matter."""
    files = [f for f in (STATUS / "register").glob("*.md") if re.fullmatch(r"[A-Z]+\d+[a-z]?", f.stem)]
    refuse = sum(1 for f in files if re.search(r"^status:.*REFUSED", f.read_text(encoding="utf-8"), re.M))
    return {"entries": len(files), "refused": refuse}


def proved_organizations() -> dict[str, int]:
    """Equivalence cases per dataset organization, from their case.json."""
    out: dict[str, int] = {}
    for f in CASES.glob("*/case.json"):
        orgs = {str(d.get("organization")) for d in (json.loads(f.read_text(encoding="utf-8")).get("datasets") or {}).values()
                if isinstance(d, dict) and d.get("organization")}  # fmt: skip
        for o in orgs:
            out[o] = out.get(o, 0) + 1
    return out


JCL_CASES = REPO / "tests" / "equivalence" / "jcl"
PROBE_FILE = "mvs38j_probe.json"  # a tier-2 (MVS 3.8J) result file, sitting beside the answers it ran
MVS38J_DOC = REPO / "docs" / "jcl_oracle_mvs38j.md"
JCL_MEASURED = JCL_CASES / "carddemo" / "measured.json"  # the last CardDemo run, for runs without the corpus


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def carddemo_jcl_live(corpus: Path) -> tuple[int, int]:
    """(answers reproduced, answers) of the CardDemo JclFlow case, run on the corpus checkout."""
    from gitgalaxy.core import job_flow
    from gitgalaxy.core.jcl_flow import JclFlow
    from gitgalaxy.core.source_text import read_source

    cd = json.loads((JCL_CASES / "carddemo" / "scenarios.json").read_text(encoding="utf-8"))
    ok = n = 0
    for j in cd["jobs"]:
        f = JclFlow(job_flow.jcl_job_flow(read_source(corpus / j["member"]).text))
        for sc in j["scenarios"]:
            n += 1
            ok += f.run(j["job"], sc["given"]).actions == sc["expect"]
    return ok, n


def write_carddemo_measured(corpus: Path) -> Path:
    """Record the CardDemo run (`python tests/tools/capability_ledger.py jcl-measure CORPORA`), keyed to the answers."""
    ok, n = carddemo_jcl_live(corpus)
    body = {"format": "jcl-flow-measured/1", "matched": ok, "of": n,
            "answers_sha256": _sha(JCL_CASES / "carddemo" / "scenarios.json")}  # fmt: skip
    JCL_MEASURED.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return JCL_MEASURED


def _proc_results() -> list[tuple[dict[str, Any], bool]]:
    """Each scenario of the PROC case (#8413 slice 2) with whether the engine reproduced its answer: each `resolve`
    scenario (the step list a call step ends up with) and each `flow` scenario (run or bypass over procedure steps)."""
    from gitgalaxy.core import job_flow
    from gitgalaxy.core.jcl_flow import JclFlow
    from gitgalaxy.core.jcl_proc import expand_flow_rows, resolve_job

    doc = json.loads((JCL_CASES / "proc" / "scenarios.json").read_text(encoding="utf-8"))
    text = "\n".join(doc["flow_jcl"]) + "\n"
    libs = {lib: {m: "\n".join(lines) + "\n" for m, lines in ms.items()} for lib, ms in doc["libraries"].items()}
    out: list[tuple[dict[str, Any], bool]] = []
    for sc in doc["resolve"]:
        got = resolve_job(text, libs, sc["job"])
        out.append((sc, all(k in got and all(got[k][f] == v for f, v in want.items()) for k, want in sc["expect"].items())
                    and [k for k in got if k.split(".")[0] == sc["call"]] == list(sc["expect"])))  # fmt: skip
    rows = job_flow.jcl_job_flow(text)
    for sc in doc["flow"]:
        out.append(
            (
                sc,
                JclFlow(expand_flow_rows(rows, sc["job"], text, libs)).run(sc["job"], sc["given"]).actions
                == sc["expect"],
            )
        )
    return out


def proc_scenarios_live() -> tuple[int, int]:
    """(answers reproduced, answers) of the PROC case, run live."""
    res = _proc_results()
    return sum(ok for _, ok in res), len(res)


def _step_results() -> dict[str, list[tuple[dict[str, Any], bool]]]:
    """Each scenario of the GDG, restart and data-flow cases (#8413) with whether its resolver reproduced the answer. Every
    case holds `flow_jcl` and `scenarios`; the answers were written from IBM's manuals before the resolver ran on them."""
    from gitgalaxy.core import job_flow
    from gitgalaxy.core.jcl_dataflow import resolve_dataflow
    from gitgalaxy.core.jcl_flow import JclFlow
    from gitgalaxy.core.jcl_gdg import resolve_gdg
    from gitgalaxy.core.jcl_proc import expand_flow_rows
    from gitgalaxy.core.jcl_restart import resolve_gdg_restart, restart_flow

    out: dict[str, list[tuple[dict[str, Any], bool]]] = {}
    for case in ("gdg", "restart", "dataflow"):
        doc = json.loads((JCL_CASES / case / "scenarios.json").read_text(encoding="utf-8"))
        all_rows = rows = job_flow.jcl_job_flow("\n".join(doc["flow_jcl"]) + "\n")
        by_id = {s["id"]: s for s in doc["scenarios"]}
        res: list[tuple[dict[str, Any], bool]] = []
        for sc in doc["scenarios"]:
            job = sc["job"]
            if case == "restart":
                got = restart_flow(rows, job, sc["given"])
                res.append((sc, got == sc["expect"]))
                continue
            if case == "gdg" and sc.get("restart"):  # a restarted run: steps before the restart step do not start
                catalog = by_id[sc["catalog_from"]]["catalog_after"] if "catalog_from" in sc else sc["catalog"]
                names, after = resolve_gdg_restart(all_rows, job, catalog, sc["given"])
                res.append((sc, names == sc["expect"] and after == sc["catalog_after"]))
                continue
            if case == "gdg":  # a procedure step's GDG DD is read from the expanded CALL.PROCSTEP rows
                rows = expand_flow_rows(all_rows, job)
            flow = JclFlow(rows).run(job, sc["given"])
            if case == "gdg":
                catalog = by_id[sc["catalog_from"]]["catalog_after"] if "catalog_from" in sc else sc["catalog"]
                names, after = resolve_gdg(rows, job, catalog, flow)
                res.append((sc, names == sc["expect"] and after == sc["catalog_after"]))
            else:
                answers, temps = resolve_dataflow(rows, job, flow, sc.get("msgclass"))
                res.append((sc, answers == sc["expect"] and temps == sc["temporaries"]))
        out[case] = res
    return out


def step_cases_live() -> dict[str, tuple[int, int]]:
    """(answers reproduced, answers) of the GDG, restart and data-flow cases, each run live."""
    return {c: (sum(ok for _, ok in r), len(r)) for c, r in _step_results().items()}


def _answer_files() -> list[Path]:
    """Every IBM-written JCL answer file on main: a `*.json` with `scenarios` (or the PROC case's `resolve` / `flow`) in
    a case directory under tests/equivalence/jcl, found by walking the tree so a new case directory is counted with no
    edit here. `carddemo` is the measured corpus row, and a `mvs38j_probe.json` holds tier-2 results, not answers."""
    out = []
    for d in sorted(p for p in JCL_CASES.iterdir() if p.is_dir() and p.name != "carddemo"):
        for f in sorted(d.glob("*.json")):
            if f.name != PROBE_FILE and f.name != "measured.json":
                out.append(f)
    return out


def _is_assumed(sc: dict[str, Any]) -> bool:
    """A scenario whose answer rests on a stated assumption (an `assumed` key, or ASSUMED in its basis)."""
    return "assumed" in sc or "ASSUMED" in str(sc.get("basis", ""))


def _flow_results(f: Path, doc: dict[str, Any]) -> list[tuple[dict[str, Any], bool]]:
    """A plain run-or-bypass answer file: `scenarios` of {job, given, expect} over the JCL it names (a `.jcl` file beside
    it in `fixture`, else the lines of `flow_jcl`)."""
    from gitgalaxy.core import job_flow
    from gitgalaxy.core.jcl_flow import JclFlow

    if (f.parent / str(doc.get("fixture", ""))).is_file():
        raw = (f.parent / doc["fixture"]).read_bytes()  # IFFLOW.jcl is UTF-8 (the not sign), FLOW.jcl is latin-1
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
    elif "flow_jcl" in doc:
        text = "\n".join(doc["flow_jcl"]) + "\n"
    else:
        raise ValueError(f"{f}: neither a `fixture` .jcl file beside it nor `flow_jcl`")
    from gitgalaxy.core.jcl_proc import JclProcRefused, expand_flow_rows

    rows = job_flow.jcl_job_flow(text)

    def flow_rows(job: str) -> list[dict[str, Any]]:
        try:  # in-stream procedure steps become CALL.PROCSTEP rows
            return expand_flow_rows(rows, job)
        except JclProcRefused:  # a call to a library procedure: the reader's rows, as the fixture answers were written
            return rows

    return [(sc, JclFlow(flow_rows(sc["job"])).run(sc["job"], sc["given"]).actions == sc["expect"])
            for sc in doc["scenarios"]]  # fmt: skip


def _library_restart_results(doc: dict[str, Any]) -> list[tuple[dict[str, Any], bool]]:
    """The restarts of a library procedure (`restart/library.json`): the member is read from the file's `libraries`."""
    from gitgalaxy.core import job_flow
    from gitgalaxy.core.jcl_restart import restart_flow

    text = "\n".join(doc["library_jcl"]) + "\n"
    libs = {lb: {m: "\n".join(x) + "\n" for m, x in ms.items()} for lb, ms in doc["libraries"].items()}
    rows = job_flow.jcl_job_flow(text)
    return [(sc, restart_flow(rows, sc["job"], sc["given"], text, libs) == sc["expect"]) for sc in doc["scenarios"]]


def _library_gdg_results(doc: dict[str, Any]) -> list[tuple[dict[str, Any], bool]]:
    """The GDG DDs of a library procedure under restart (`gdg/library.json`): the member is read from `libraries`."""
    from gitgalaxy.core import job_flow
    from gitgalaxy.core.jcl_restart import resolve_gdg_restart

    text = "\n".join(doc["library_jcl"]) + "\n"
    libs = {lb: {m: "\n".join(x) + "\n" for m, x in ms.items()} for lb, ms in doc["libraries"].items()}
    rows = job_flow.jcl_job_flow(text)
    out = []
    for sc in doc["scenarios"]:
        names, after = resolve_gdg_restart(rows, sc["job"], sc["catalog"], sc["given"], text, libs)
        out.append((sc, names == sc["expect"] and after == sc["catalog_after"]))
    return out


def jcl_answer_sets() -> dict[str, list[tuple[dict[str, Any], bool]]]:
    """Each answer file (`case/file.json`) with its scenarios and whether the evaluator reproduced each, run live."""
    steps = _step_results()
    out: dict[str, list[tuple[dict[str, Any], bool]]] = {}
    for f in _answer_files():
        doc = json.loads(f.read_text(encoding="utf-8"))
        case = f.parent.name
        if "scenarios" not in doc and "resolve" not in doc:
            continue
        if case == "proc":
            res = _proc_results()
        elif case == "restart" and f.name == "library.json":
            res = _library_restart_results(doc)
        elif case == "gdg" and f.name == "library.json":
            res = _library_gdg_results(doc)
        elif case in steps and f.name == "scenarios.json":
            res = steps[case]
        else:
            res = _flow_results(f, doc)
        out[f"{case}/{f.name}"] = res
    return out


def mvs38j_tier2() -> dict[str, Any]:
    """What tier 2 (MVS 3.8J, the live box) checked, read from the data: each `mvs38j_probe.json` beside its answer file
    gives the scenarios it ran and their verdicts; every other scenario on main is not checked there. `cannot_test` is
    the list in docs/jcl_oracle_mvs38j.md ("What this tier cannot test")."""
    import re

    sets = jcl_answer_sets()
    checked: dict[str, dict[str, int]] = {}
    unchecked: dict[str, int] = {}
    for name, res in sets.items():
        probe = JCL_CASES / name.split("/")[0] / PROBE_FILE
        ids: dict[str, str] = {}
        if probe.is_file():
            ids = {r["id"]: r["verdict"] for r in json.loads(probe.read_text(encoding="utf-8"))["results"]}
        known = [sc for sc, _ in res if sc["id"] in ids]
        if known:
            checked[name] = {"ran": len(known), "agree": sum(ids[sc["id"]] == "agree" for sc in known), "of": len(res)}
        if len(res) - len(known):
            unchecked[name] = len(res) - len(known)
    text = MVS38J_DOC.read_text(encoding="utf-8") if MVS38J_DOC.is_file() else ""
    m = re.search(r"## What this tier cannot test\s+(.+?) do(?:es)? not exist", text, re.S)
    cannot = [c.strip() for c in re.split(r",| and ", m.group(1).replace("\n", " ")) if c.strip()] if m else []
    return {"checked": checked, "unchecked": unchecked, "cannot_test": cannot}


def tier2_have(t: dict[str, Any]) -> str:
    """The tier-2 row text: per answer file what the box ran, and the scenarios on main it did not."""
    ran = "; ".join(f"{k}: {v['agree']} of {v['ran']} agree (file has {v['of']})" for k, v in t["checked"].items())
    rest = sum(t["unchecked"].values())
    return f"{ran or 'nothing run'}; {rest} scenarios in {len(t['unchecked'])} answer files not run on the box"


def jcl_step_flow() -> dict[str, Any]:
    """The JCL step-flow evaluator (gitgalaxy.core.jcl_flow and its siblings) run live on every IBM-written answer set on
    main (`jcl_answer_sets`: FLOW fixtures, IF / THEN / ELSE, PROC resolution, GDG, restart, data flow) and on the
    CardDemo case (8 jobs with EXEC COND; run only when the pinned CardDemo corpus is checked out, else
    `carddemo_matched` is None). The answers were written from IBM's manuals before the evaluator ran on them (#7654,
    #7676). Scenarios that rest on a stated assumption are counted apart: `fixture` is the manual-backed answers,
    `assumed` the assumed ones."""
    import os

    fx_ok = fx_n = as_ok = as_n = 0
    for res in jcl_answer_sets().values():
        for sc, ok in res:
            if _is_assumed(sc):
                as_n += 1
                as_ok += ok
            else:
                fx_n += 1
                fx_ok += ok
    cd = json.loads((JCL_CASES / "carddemo" / "scenarios.json").read_text(encoding="utf-8"))
    n_cd = sum(len(j["scenarios"]) for j in cd["jobs"])
    corpus = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora")) / cd["corpus"]
    cd_ok = None
    if corpus.is_dir():
        cd_ok = carddemo_jcl_live(corpus)[0]
    elif JCL_MEASURED.is_file():  # the recorded run, only while the answers are the ones it ran
        rec = json.loads(JCL_MEASURED.read_text(encoding="utf-8"))
        if rec.get("answers_sha256") == _sha(JCL_CASES / "carddemo" / "scenarios.json") and rec.get("of") == n_cd:
            cd_ok = rec["matched"]
    return {
        "fixture": (fx_ok, fx_n),
        "assumed": (as_ok, as_n),
        "carddemo": (cd_ok, n_cd),
        "carddemo_jobs": len(cd["jobs"]),
        "tier2": mvs38j_tier2(),
    }


def build(rules: dict[str, Any], cics: dict[str, Any]) -> dict[str, Any]:
    """The rows. `rules` is cobolrt_rules.json; `cics` is progress_report's CICS component (the burned denominator)."""
    from gitgalaxy.core.cics_macro_tables import _TABLES
    from gitgalaxy.standards import mq
    import cics_spec_status
    from gitgalaxy.tools.cobol_to_java.det import dfsort, hlasm, sql

    rs = rules["rules"]
    tables, cmds = spec_tables(), cics_commands()
    lang, lang_of = family_counts(rs, LANGUAGE_FAMILIES)
    db2, db2_of = family_counts(rs, ("SQL",))
    le, le_of = family_counts(rs, ("LE",))
    dli, dli_of = family_counts(rs, ("DLI",))
    mq_rules, mq_of = family_counts(rs, ("MQ",))
    mq_all = len(mq.CALLS) + len(mq.UNMODELLED)
    jobs = len(list((CASES / "jobs").glob("*.json")))
    jf = jcl_step_flow()
    cpg = code_pages()
    gnt = cultural_gauntlet()
    mc_ok, mc_n = multicultural_estate()
    import estate_size

    sizes = estate_size.load()
    jz = {k: sum(v.get(k, 0) for v in sizes.values()) for k in ("jcl_members", "jcl_jobs", "jcl_cond_jobs",
                                                                "jcl_checked_jobs")} if sizes else {}  # fmt: skip
    sorts = len(list(CASES.glob("*-sort-*")))
    fc, cics_py = DET / "cics_filecontrol.py", DET / "cics.py"
    keyed = proved_organizations().get("indexed", 0)
    spec = cics_spec_status.spec()
    maps = [k for k in ("SEND MAP", "RECEIVE MAP") if k in spec and spec[k].status == "modelled"]
    import gap_prevalence

    layouts, x77 = copy_layouts(), register_status("X77")
    sql_keywords = len(getattr(gap_prevalence, "_SQL_OTHER_VERBS", ()))
    rows = [
        row(
            "COBOL language",
            "Statements and data",
            "statements, numerics, editing, functions, files",
            of_state(lang, lang_of),
            lang,
            lang_of,
            "rules match IBM",
        ),  # fmt: skip
        row(
            "COBOL language",
            "Runtime spec tables",
            f"{tables['tables']} tables, {tables['rules']} rules, "
            f"{tables['vectors']} test vectors, {tables['matrix_cells']} matrix cells",
            "works",
            note="part of the rules above: depth, not extra rules",
        ),  # fmt: skip
        row(
            "COBOL language",
            "Copybook search",
            f"{layouts} member layouts the engine and translator both resolve",
            "works" if layouts else "none",
            note="extensionless and program-extension members, lowercase, nested COPY, OF library, deep directories",
            found="Gap found by Blind 1: 28 of 29 first-contact misses were copybooks (#8074, #8111)",
        ),
        row(
            "COBOL language",
            "JSON GENERATE / PARSE",
            "translated from IBM's text; GnuCOBOL has no JSON, so no oracle backs it"
            + (f" (register X77: {x77})" if x77 else ""),
            seen(DET / "gen.py", "def json_parse", "partial"),
            found="Gap found by the census rehearsal: 2 programs needed it (#7524)",
        ),
        row(
            "Code pages and national text",
            "EBCDIC code pages",
            f"{cpg['sbcs']} single-byte national pages, {cpg['dbcs']} double-byte",
            of_state(cpg["java"], cpg["pages"]),
            done=cpg["java"],
            of=cpg["pages"],
            unit="in the Java too",
            note="US, European, Arabic, Hebrew, Greek, Turkish; Japanese, Chinese, Korean",
        ),
        row(
            "Code pages and national text",
            "Cultural dialects",
            f"{gnt['dialects']} source dialects in {gnt['pages']} EBCDIC pages",
            "works" if gnt["dialects"] and not gnt["failing"] else "partial" if gnt["dialects"] else "none",
            note=f"comma decimal point, pound / euro / rupee signs, lakh grouping, rounding, Lilian dates; "
            f"{gnt['failing']} failing cells (Cultural Gauntlet)",
        ),
        row(
            "Code pages and national text",
            "Multicultural test estate",
            "members as raw exported mainframe bytes",
            of_state(mc_ok, mc_n) if mc_n else "none",
            done=mc_ok if mc_n else None,
            of=mc_n or None,
            unit="traps read right",
            note="EBCDIC incl. Arabic and Japanese DBCS, Shift-JIS, UTF-8 with and without BOM",
        ),
        row(
            "CICS",
            "Commands the estates use",
            "programs in the burned estates",
            of_state(cics["modelled_both_runtimes"], cics["burned_commands"]),
            cics["modelled_both_runtimes"],
            cics["burned_commands"],
            "modelled on both runtimes",
        ),  # fmt: skip
        row(
            "CICS",
            "All CICS commands",
            "every command IBM's reference lists",
            of_state(cmds["modelled"], cmds["all"]),
            cmds["modelled"],
            cmds["all"],
            "modelled; the rest refused by name",
        ),  # fmt: skip
        row(
            "CICS",
            "Command options",
            f"{cmds['options_refused']} refused by name",
            of_state(cmds["options"] - cmds["options_refused"], cmds["options"]),
            cmds["options"] - cmds["options_refused"],
            cmds["options"],
            "accepted",
        ),  # fmt: skip
        row(
            "CICS",
            "Macro resource tables",
            ", ".join(t.removeprefix("DFH") for t in _TABLES),
            "extract" if _TABLES else "none",
            note=f"{len(_TABLES)} tables read into the resource map; not run",
        ),  # fmt: skip
        row(
            "Data and messaging",
            "Db2 embedded SQL",
            f"{len(sql._REFUSED_VERBS)} verbs refused by name",
            of_state(db2, db2_of),
            db2,
            db2_of,
            "rules match IBM",
            note=f"{sql_keywords} more IBM statement keywords, beyond the modelled ones, each refused by name, never dropped"
            if sql_keywords
            else "",
            found="Tested by Blind 1: its 17 SQL statements all translated at first contact; the rest pinned (#8075, #8146)",
        ),  # fmt: skip
        row(
            "Data and messaging",
            "LE callable services",
            "date, time and condition services",
            of_state(le, le_of),
            le,
            le_of,
            "rules match IBM",
        ),  # fmt: skip
        row(
            "Data and messaging",
            "VSAM KSDS",
            f"keyed read, write and browse, in {keyed} equivalence cases",
            "works" if keyed else "none",
        ),  # fmt: skip
        row(
            "Data and messaging",
            "VSAM alternate index",
            "keyed access through a path",
            seen(cics_py, "an alternate index", "partial"),
        ),  # fmt: skip
        row(
            "Data and messaging",
            "VSAM ESDS",
            "browse by relative byte address under CICS",
            seen(fc, "an ESDS browsed by relative byte address", "partial"),
        ),  # fmt: skip
        row(
            "Data and messaging",
            "VSAM RRDS",
            "relative record access",
            seen(fc, "RBA / RRN / XRBA: not modelled", "refused"),
            note="refused by name, not missing",
        ),  # fmt: skip
        row(
            "Data and messaging",
            "IBM MQ",
            f"{mq_rules} of {mq_of} rules match IBM; CICS calls only",
            of_state(len(mq.CALLS), mq_all),
            len(mq.CALLS),
            mq_all,
            "calls modelled",
        ),  # fmt: skip
        row(
            "Data and messaging",
            "IMS DL/I",
            "calls run on our own model, so no rule matches yet",
            "partial" if dli_of and not dli else of_state(dli, dli_of),
            dli,
            dli_of,
            "rules match IBM",
        ),  # fmt: skip
        row(
            "Batch",
            "DFSORT",
            f"SORT, MERGE, COPY, INCLUDE, OMIT, OUTREC; {len(dfsort.FORMATS)} key formats",
            seen(DET / "dfsort.py", "class Refused", "partial") if sorts else "none",
            note=f"{sorts} sort equivalence cases",
        ),  # fmt: skip
        row(
            "Batch",
            "IDCAMS, IEBGENER",
            "REPRO and plain copies; other commands refused",
            seen(DET / "idcams.py", "REPRO", "partial"),
        ),  # fmt: skip
        row(
            "Batch",
            "JCL step flow",
            f"run or bypass per step (COND), CardDemo's {jf['carddemo_jobs']} COND jobs: "
            + (
                f"{jf['carddemo'][0]} of {jf['carddemo'][1]} answers"
                if jf["carddemo"][0] is not None
                else f"{jf['carddemo'][1]} answers, not run here (no corpus)"
            ),
            of_state(*jf["fixture"]) if jf["fixture"][1] else "none",
            done=jf["fixture"][0],
            of=jf["fixture"][1],
            unit="IBM-written scenarios",
            note="answers written from IBM's manuals before the evaluator ran; "
            f"plus {jf['assumed'][1]} ASSUMED scenarios (a stated assumption, not IBM text), {jf['assumed'][0]} reproduced",
        ),
        row(
            "Batch",
            "JCL on MVS 3.8J (tier 2)",
            tier2_have(jf["tier2"]),
            "works" if jf["tier2"]["checked"] else "none",
            done=sum(v["agree"] for v in jf["tier2"]["checked"].values()),
            of=sum(v["ran"] for v in jf["tier2"]["checked"].values()),
            unit="scenarios agreeing on the box",
            note="not checked on 3.8J: " + ", ".join(jf["tier2"]["cannot_test"]),
        ),
        row(
            "Batch",
            "JCL in the real codebases",
            f"{jz['jcl_jobs']} jobs read in {jz['jcl_members']} JCL members; {jz['jcl_cond_jobs']} depend on COND / IF",
            of_state(jz["jcl_checked_jobs"], jz["jcl_cond_jobs"]) if jz["jcl_cond_jobs"] else "none",
            done=jz["jcl_checked_jobs"] if jz["jcl_cond_jobs"] else None,
            of=jz["jcl_cond_jobs"] or None,
            unit="COND jobs answer-checked",
            note="sizes recorded from the pinned corpora (estate_size.py)",
        )
        if jz
        else row("Batch", "JCL in the real codebases", "not recorded", "none"),
        row(
            "Batch",
            "JCL job execution",
            f"{jobs} multi-step job case",
            "partial" if jobs and FORGE.is_file() else "none",
            note="the programs' steps are wired by the case, not yet run from the JCL",
        ),  # fmt: skip
        row(
            "Other languages",
            "HLASM assembler",
            f"{len(hlasm.SUBSET)} opcodes, the zECS subset",
            "partial" if hlasm.SUBSET else "none",
        ),  # fmt: skip
        row("Other languages", "BMS maps", ", ".join(maps) or "no map command", "works" if len(maps) == 2 else "none"),
        row("Other languages", "PL/I", "scanned, never translated", "none", note="no translator code"),
    ]
    measured = sum(1 for r in rs if r.get("calibration") not in (None, "uncalibrated"))
    return {"groups": list(GROUPS), "rows": rows, "register": register(),
            "zos": {"measured": measured, "of": len(rs)}}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    """`capability_ledger.py` prints the rows; `capability_ledger.py jcl-measure CORPORA` re-records the CardDemo
    JCL step-flow run (tests/equivalence/jcl/carddemo/measured.json) from the corpora directory."""
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["jcl-measure"] and len(argv) == 2:
        cd = json.loads((JCL_CASES / "carddemo" / "scenarios.json").read_text(encoding="utf-8"))
        print(write_carddemo_measured(Path(argv[1]) / cd["corpus"]))
        return 0
    import progress_report as pr

    print(json.dumps(pr.gather()["components"]["capabilities"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
