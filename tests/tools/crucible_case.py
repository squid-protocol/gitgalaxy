#!/usr/bin/env python3
"""A new cics-crucible case, and the check that its expected logs were derived by hand (#4270 slices).

    python tests/tools/crucible_case.py new <trap>/<case-id> --programs GTX,GTY [--transids GT41,GT42]
                                            [--crucible DIR] [--gen SCRATCH/gen_expected.py]
    python tests/tools/crucible_case.py check-hand-derived SCRATCH/gen_expected.py [...]

`new` scaffolds cases/<trap>/<case-id>/ in a cics-crucible checkout (--crucible, else $CICS_CRUCIBLE_PATH) per its
SPEC.md section 3: case.json (the section 5 skeleton: sources, one placeholder scenario), src/<PROGRAM>.cbl (a
fixed-format skeleton per program, PROGRAM-ID = file stem), copy/, csd/<case-id>.csd (DEFINE PROGRAM per program,
DEFINE TRANSACTION per --transids, mapped to the programs in order; default <trap prefix>01), expected/, and NOTES.md with the sections
tools/validate.py requires (The trap, Why a naive translation breaks, Expected behaviour, What a correct port must
do, Avoided ambiguities, Citations). With --gen, also a log-writing script skeleton OUTSIDE the crucible (your scratch
directory): it formats hand-traced values with tests/tools/crucible_events.py and nothing else.

`check-hand-derived` is the crucible's oracle rule as a check (its AGENTS.md rules 2-3: logs come from IBM's
documentation, never from running an implementation). It fails (exit 1) when a log-writing script imports anything
beyond the standard library and crucible_events -- gitgalaxy, the runtimes, the harness -- or reaches for a way to run
one: subprocess, os.system / popen / exec* / spawn*, importlib, runpy, ctypes, multiprocessing, __import__, exec,
eval. It is a guard against accidents, not a sandbox.

Then: python3 tools/validate.py cases/<trap>/<case-id> in the crucible checkout, and the proofs (cobol-stub, the det
port via tests/tools/cics_case_ports.py).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import pprint
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import crucible_events as ev  # noqa: E402

TRAP_PREFIX = {"condition-handling": "HC", "hex-attributes": "HX", "commarea-mismatch": "CA", "ghost-tasks": "GT",
               "pseudo-conversational": "PC"}  # fmt: skip  # cics-crucible AGENTS.md, "Adding a case"
NOTES_SECTIONS = ("The trap", "Why a naive translation breaks", "Expected behaviour", "What a correct port must do",
                  "Avoided ambiguities", "Citations")  # fmt: skip  # cics-crucible tools/validate.py NOTES_SECTIONS
ALLOWED_EXTRA = {"crucible_events", "__future__"}
# #4270 (cics_command_spec.md section 6 rule 1): the CICS command spec says what gitgalaxy MODELS, never what IBM
# does; a log must never come from it. Named here, and checked before ALLOWED_EXTRA, so that no future allow-list
# entry (a "gitgalaxy" one included) can let it through.
DENIED_SPEC = "gitgalaxy.standards.cics"
DENIED_MODULES = {"subprocess", "importlib", "runpy", "ctypes", "multiprocessing", "concurrent", "pty", "code",
                  "codeop", "socket", "urllib", "http", "xmlrpc", "ftplib", "telnetlib", "smtplib", "webbrowser",
                  "imp", "zipimport", "pkgutil", "site", "sysconfig", "venv", "ensurepip", "pydoc"}  # fmt: skip
DENIED_CALLS = {"__import__", "exec", "eval", "compile", "os.system", "os.popen", "os.startfile", "os.posix_spawn",
                "os.posix_spawnp", "os.fork", "os.forkpty"}  # fmt: skip
DENIED_PREFIXES = ("os.exec", "os.spawn")
_NAME8 = re.compile(r"^[A-Z0-9#@$]{1,8}$")
_NAME4 = re.compile(r"^[A-Z0-9#@$]{1,4}$")
_CASE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

PROGRAM_SKELETON = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. {prog}.
      * {banner}
      * Original code only (cics-crucible AGENTS.md rule 1).
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RESP                 PIC S9(8) COMP VALUE 0.
       LINKAGE SECTION.
       PROCEDURE DIVISION.
       MAIN-PARA.
      * TODO: the trap. Leave a breadcrumb (screen or TS queue) for
      * every behaviour the expected logs assert (SPEC 6.2: ASSIGN,
      * HANDLE, ... are not events).
           EXEC CICS RETURN END-EXEC.
"""

NOTES_TEMPLATE = """\
# {case}: TODO one-line statement of the trap

## The trap

TODO: what the programs do ({programs}), mode by mode, and what each log item or screen shows.

## Why a naive translation breaks

* TODO: the plausible port that gets it wrong, and what it does instead.

## Expected behaviour

Model (SPEC sections 2 and 4): TODO (the region, the terminal, the clock {clock}).

* **`happy-path`**: TODO, step by step. Every non-obvious step cites IBM with a quoted rule, e.g.
  "..." [COMMAND].

## What a correct port must do

* TODO

## Avoided ambiguities

* TODO: release-dependent or undocumented behaviour the scenarios are designed not to depend on.

## Citations

* [COMMAND] IBM CICS TS 6.x, Application Programming Reference, EXEC CICS ...:
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=TODO
* [RESP-CODES] IBM CICS TS 6.x, RESP and RESP2 values: https://www.ibm.com/docs/en/cics-ts/6.x?topic=TODO
"""

GEN_TEMPLATE = '''\
"""Writes {case}'s case.json and expected logs. Every value below was TRACED BY HAND from the programs and IBM's
documentation (NOTES.md); this script only formats them. Standard library + crucible_events only:
python tests/tools/crucible_case.py check-hand-derived <this file>."""

import sys
from pathlib import Path

sys.path.insert(0, "{tools}")
import crucible_events as ev  # noqa: E402

D = Path(sys.argv[1])  # the case directory: {case_dir}
CLOCK = ev.Clock("{clock}")
CASE = "{case}"

logs = {{}}
logs["happy-path"] = ev.expected(CASE, "happy-path", [
    ev.task(1, "{transid}", "{program}", CLOCK.at(0), ev.terminal(0), [
        ev.return_("{program}"),
    ], termid="T001", eibaid="ENTER"),
])

case = {case_json}
ev.write_case(D, case, logs)
'''


def case_skeleton(case_id: str, trap: str, programs: list[str], clock: str = "2026-03-02T10:00:00",
                  transid: str | None = None) -> dict:  # fmt: skip
    first = transid or f"{TRAP_PREFIX[trap]}01"
    return {
        "format": ev.FORMAT_CASE, "id": case_id, "trap": trap, "title": "TODO: what the case attacks",
        "clock": clock, "terminal": "T001",
        "sources": {"cobol": [f"src/{p}.cbl" for p in programs], "bms": [], "csd": [f"csd/{case_id}.csd"],
                    "copy": ["copy"], "data": []},
        "layouts": {}, "maps": {},
        "scenarios": [ev.scenario("happy-path", "happy", "TODO", [ev.step(0, "ENTER", text=first)])],
    }  # fmt: skip


def csd_text(case_id: str, trap: str, programs: list[str], transids: list[str]) -> str:
    group = f"CRUC{TRAP_PREFIX[trap]}"
    lines = [f"* cics-crucible {trap} / {case_id}"]
    lines += [f"DEFINE PROGRAM({p}) GROUP({group}) LANGUAGE(COBOL)" for p in programs]
    lines += [f"DEFINE TRANSACTION({t}) GROUP({group}) PROGRAM({programs[min(i, len(programs) - 1)]})"
              for i, t in enumerate(transids)]  # fmt: skip
    lines += ["* T001 accepts automatic transaction initiation (START TERMID): SPEC section 2",
              f"DEFINE TYPETERM(CRU3278) GROUP({group}) DEVICE(3270) TERMMODEL(2)", "       ATI(YES) TTI(YES)",
              f"DEFINE TERMINAL(T001) GROUP({group}) TYPETERM(CRU3278)"]  # fmt: skip
    return "\n".join(lines) + "\n"


def cmd_new(args: argparse.Namespace) -> int:
    trap, _, case_id = args.case.partition("/")
    if trap not in TRAP_PREFIX or not _CASE_ID.match(case_id):
        raise SystemExit(f"want <trap>/<case-id>: trap one of {', '.join(TRAP_PREFIX)}, case-id lower-case kebab")
    programs = [p.strip().upper() for p in args.programs.split(",") if p.strip()]
    transids = [t.strip().upper() for t in (args.transids or "").split(",") if t.strip()]
    transids = transids or [f"{TRAP_PREFIX.get(trap, 'XX')}01"]  # a placeholder: pick the case's own
    bad = [p for p in programs if not _NAME8.match(p)] + [t for t in transids if not _NAME4.match(t)]
    if not programs or bad:
        raise SystemExit(f"bad program / transaction names: {bad or 'none given'} (1-8 / 1-4 of A-Z 0-9 # @ $)")
    crucible = args.crucible or (
        Path(os.environ["CICS_CRUCIBLE_PATH"]) if os.environ.get("CICS_CRUCIBLE_PATH") else None
    )
    if crucible is None or not (crucible / "SPEC.md").is_file():
        raise SystemExit(f"no cics-crucible checkout at {crucible} (--crucible DIR or $CICS_CRUCIBLE_PATH; work on a "
                         "case branch of your own clone, never the shared pin checkout)")  # fmt: skip
    existing = sorted(p.parent.name for p in crucible.glob(f"cases/*/{case_id}/case.json"))
    case_dir = crucible / "cases" / trap / case_id
    if existing or case_dir.exists():
        raise SystemExit(f"case id {case_id} is taken (ids are unique across traps): {case_dir}")
    for sub in ("src", "copy", "csd", "expected"):
        (case_dir / sub).mkdir(parents=True)
    case_doc = case_skeleton(case_id, trap, programs, transid=transids[0] if transids else None)
    (case_dir / "case.json").write_text(json.dumps(case_doc, indent=2) + "\n", encoding="utf-8")
    for p in programs:
        (case_dir / "src" / f"{p}.cbl").write_text(PROGRAM_SKELETON.format(prog=p, banner=f"{trap} / {case_id}"[:65]),
                                                   encoding="utf-8")  # fmt: skip
    (case_dir / "csd" / f"{case_id}.csd").write_text(csd_text(case_id, trap, programs, transids), encoding="utf-8")
    (case_dir / "copy" / ".gitkeep").write_text("", encoding="utf-8")
    (case_dir / "NOTES.md").write_text(NOTES_TEMPLATE.format(case=case_id, programs=", ".join(programs),
                                                             clock=case_doc["clock"]), encoding="utf-8")  # fmt: skip
    print(f"scaffolded {case_dir}")
    if args.gen:
        if args.gen.resolve().is_relative_to(crucible.resolve()):
            raise SystemExit("--gen goes in your scratch directory, not the crucible checkout")
        args.gen.parent.mkdir(parents=True, exist_ok=True)
        args.gen.write_text(GEN_TEMPLATE.format(
            case=case_id, tools=TOOLS, case_dir=case_dir, clock=case_doc["clock"],
            transid=transids[0] if transids else f"{TRAP_PREFIX[trap]}01", program=programs[0],
            case_json=pprint.pformat(case_doc, width=110, sort_dicts=False)), encoding="utf-8")  # fmt: skip
        print(f"log-writing script skeleton: {args.gen}  (run: python {args.gen} {case_dir})")
    print(f"next: write the programs and NOTES.md, trace the logs by hand, then\n"
          f"  python tests/tools/crucible_case.py check-hand-derived <script>\n"
          f"  (cd {crucible} && python3 tools/validate.py cases/{trap}/{case_id})")  # fmt: skip
    return 0


# ---- check-hand-derived -----------------------------------------------------------------------------------------
def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def hand_derived_problems(source: str, name: str = "<script>") -> list[str]:
    """Why `source` is not a pure formatter of hand-traced values ([] when it is)."""
    try:
        tree = ast.parse(source, filename=name)
    except SyntaxError as e:
        return [f"{name}:{e.lineno}: does not parse: {e.msg}"]
    stdlib = set(sys.stdlib_module_names)
    problems = []
    for node in ast.walk(tree):
        mods: list[str] = []
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                problems.append(f"{name}:{node.lineno}: relative import (from {'.' * node.level}{node.module or ''})")
                continue
            mods = [node.module or ""]
        named = mods + ([f"{node.module}.{a.name}" for a in node.names] if isinstance(node, ast.ImportFrom) else [])
        for m in named:  # (`from gitgalaxy.standards import cics` names it too)
            if m == DENIED_SPEC or m.startswith(DENIED_SPEC + "."):
                problems.append(f"{name}:{line}: imports {m}: the CICS command spec is an implementation artifact, "
                                "never the oracle (cics_command_spec.md section 6)")  # fmt: skip
                mods = []
                break
        for m in mods:
            top = m.split(".")[0]
            if top in ALLOWED_EXTRA:
                continue
            if top in DENIED_MODULES:
                problems.append(f"{name}:{line}: imports {m}: it can run an implementation")
            elif top not in stdlib:
                problems.append(f"{name}:{line}: imports {m}: only the standard library and crucible_events "
                                "(a log is traced by hand, never computed by gitgalaxy or a runtime)")  # fmt: skip
        if isinstance(node, ast.Call):
            called = _dotted(node.func)
            if called in DENIED_CALLS or called.startswith(DENIED_PREFIXES):
                problems.append(f"{name}:{node.lineno}: calls {called}: it can run an implementation")
    return problems


def cmd_check(args: argparse.Namespace) -> int:
    bad = 0
    for script in args.scripts:
        problems = hand_derived_problems(script.read_text(encoding="utf-8"), str(script))
        bad += bool(problems)
        print("\n".join(problems) if problems else f"OK  {script}: standard library + crucible_events only")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="scaffold cases/<trap>/<case-id>/ in a cics-crucible checkout")
    n.add_argument("case", help="<trap>/<case-id>, e.g. ghost-tasks/gt-assign-startcode")
    n.add_argument("--programs", required=True, help="comma-separated PROGRAM names (file stem = PROGRAM-ID)")
    n.add_argument("--transids", help="comma-separated transaction ids, mapped to the programs in order")
    n.add_argument("--crucible", type=Path, help="the cics-crucible checkout (default: $CICS_CRUCIBLE_PATH)")
    n.add_argument("--gen", type=Path, help="also write a log-writing script skeleton here (a scratch path)")
    c = sub.add_parser("check-hand-derived", help="fail when a log-writing script imports beyond stdlib + events")
    c.add_argument("scripts", type=Path, nargs="+")
    args = ap.parse_args(argv)
    return cmd_new(args) if args.cmd == "new" else cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
