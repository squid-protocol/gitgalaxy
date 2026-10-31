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
GROUPS = ("COBOL language", "CICS", "Data and messaging", "Batch", "Other languages")


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
    from gitgalaxy.standards.cics.commands import COMMANDS

    cmds = list(COMMANDS.values())
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


def build(rules: dict[str, Any], cics: dict[str, Any]) -> dict[str, Any]:
    """The rows. `rules` is cobolrt_rules.json; `cics` is progress_report's CICS component (the burned denominator)."""
    from gitgalaxy.core.cics_macro_tables import _TABLES
    from gitgalaxy.standards import mq
    from gitgalaxy.standards.cics.commands import COMMANDS
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
    sorts = len(list(CASES.glob("*-sort-*")))
    fc, cics_py = DET / "cics_filecontrol.py", DET / "cics.py"
    keyed = proved_organizations().get("indexed", 0)
    maps = [k for k in ("SEND MAP", "RECEIVE MAP") if k in COMMANDS and COMMANDS[k].status == "modelled"]
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
            note=f"{sorts} proved sort cases",
        ),  # fmt: skip
        row(
            "Batch",
            "IDCAMS, IEBGENER",
            "REPRO and plain copies; other commands refused",
            seen(DET / "idcams.py", "REPRO", "partial"),
        ),  # fmt: skip
        row(
            "Batch",
            "JCL jobs",
            f"{jobs} multi-step job case",
            "partial" if jobs and FORGE.is_file() else "none",
            note="steps are wired by the case, not read from JCL",
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
    probes = json.loads((STATUS / "zos_probes.json").read_text(encoding="utf-8"))
    measured = sum(1 for r in rs if r.get("calibration") not in (None, "uncalibrated"))
    return {"groups": list(GROUPS), "rows": rows, "register": register(),
            "zos": {"measured": measured, "of": len(rs), "probes": len(probes["probes"])}}  # fmt: skip


def main() -> int:
    import progress_report as pr

    print(json.dumps(pr.gather()["components"]["capabilities"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
