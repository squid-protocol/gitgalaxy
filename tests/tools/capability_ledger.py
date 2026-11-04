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
        unit: str = "", note: str = "") -> dict[str, Any]:  # fmt: skip
    return {"group": group, "name": name, "have": have, "state": state, "done": done, "of": of, "unit": unit,
            "note": note}  # fmt: skip


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


def jcl_step_flow() -> dict[str, Any]:
    """The JCL step-flow evaluator (gitgalaxy.core.jcl_flow) run live on its answer sets: the IBM-written FLOW fixture
    (in the repo, always run) and the CardDemo case (8 jobs with EXEC COND; run only when the pinned CardDemo corpus is
    checked out, else `carddemo_matched` is None). The answers were written from IBM's JCL Reference before the
    evaluator ran on them (#7654, #7676)."""
    import os

    from gitgalaxy.core import job_flow
    from gitgalaxy.core.jcl_flow import JclFlow

    fx = json.loads((JCL_CASES / "fixture" / "scenarios.json").read_text(encoding="utf-8"))
    flow = JclFlow(job_flow.jcl_job_flow((JCL_CASES / "fixture" / "FLOW.jcl").read_text(encoding="latin-1")))
    fx_ok = sum(1 for sc in fx["scenarios"] if flow.run(sc["job"], sc["given"]).actions == sc["expect"])
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
    return {"fixture": (fx_ok, len(fx["scenarios"])), "carddemo": (cd_ok, n_cd), "carddemo_jobs": len(cd["jobs"])}


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
    sorts = len(list(CASES.glob("*-sort-*")))
    fc, cics_py = DET / "cics_filecontrol.py", DET / "cics.py"
    keyed = proved_organizations().get("indexed", 0)
    spec = cics_spec_status.spec()
    maps = [k for k in ("SEND MAP", "RECEIVE MAP") if k in spec and spec[k].status == "modelled"]
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
            note="answers written from IBM's JCL Reference before the evaluator ran",
        ),
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
