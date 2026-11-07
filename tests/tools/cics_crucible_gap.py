#!/usr/bin/env python3
"""#7956: the det-modelled EXEC CICS commands and options that no cics-crucible case exercises, ranked by use.

    python tests/tools/cics_crucible_gap.py [--crucible DIR] [--corpora DIR] [--census-corpora DIR] [--json] [--top N]

The modelled set is the det translator's OPTIONS (command key -> honoured options; None = open options, whose
options are listed only as they occur). A program's uses are read as cics_spec_status reads them (parse_exec and
command_key): per program, the set of command keys and of (key, option) pairs. The crucible side reads
`<crucible>/cases/*/*/src/*` the same way. A row is a command with no case, or an option of a covered command with no
case, ranked by the burned programs that use it, then the census programs. Burned programs are counted by corpus and
program; census ones are counts only (no repo, path or program name: .claude/rules/mainframe-evidence-policy.md rule 3).
COBOL only: the det translator takes nothing else. RESP / RESP2 / NOHANDLE are not options here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

_EXEC = re.compile(r"\bEXEC\s+CICS\s+(.*?)\bEND-EXEC\b", re.S)
CRUCIBLE_CORPUS = "cics-crucible"

Uses = dict[str, set[str]]  # command key -> option names ("" marks the bare command)


def command_uses(text: str) -> Uses:
    """The modelled command keys of one program and, per key, the options each command of it names."""
    import cics_census as cc

    from gitgalaxy.tools.cobol_to_java.det.cics import OPTIONS, command_key, parse_exec

    out: Uses = defaultdict(set)
    for m in _EXEC.finditer(cc.fixed_format_text(text)):
        try:
            words, opts = parse_exec(m.group(1))
        except Exception:  # the translator's own parse error: not a use
            continue
        key = command_key(words, opts)
        if key not in OPTIONS:
            continue
        out[key].add("")
        out[key].update(o for o in opts if o not in cc.EXCEPTION_OPTIONS and o not in key.split())
    return out


def _program_files(corpus: Path) -> list[Path]:
    import cics_census as cc

    return sorted(
        p for p in corpus.rglob("*")
        if p.is_file() and p.suffix.lower() in cc.PROGRAM_EXTS and ".git" not in p.relative_to(corpus).parts
    )  # fmt: skip


def crucible_uses(crucible: Path) -> dict[tuple[str, str], set[str]]:
    """(key, option) -> case ids whose programs issue it; option "" is the command itself."""
    from gitgalaxy.core.source_text import read_source

    out: dict[tuple[str, str], set[str]] = defaultdict(set)
    for prog in sorted(crucible.glob("cases/*/*/src/*")):
        if prog.suffix.lower() in (".cbl", ".cob", ".cobol"):
            for key, opts in command_uses(read_source(prog).text).items():
                for o in opts:
                    out[(key, o)].add(prog.parents[1].name)
    return out


def corpus_uses(roots: list[Path]) -> dict[tuple[str, str], dict[str, Any]]:
    """(key, option) -> {"burned": ["corpus/program", ...], "census": n}: census is a count, never a name."""
    import cics_census as cc

    from gitgalaxy.core.source_text import read_source

    burned = cc.burned_names()
    out: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"burned": [], "census": 0})
    for name, corpus in cc.corpus_dirs(roots):
        if name.lower() == CRUCIBLE_CORPUS:
            continue  # the crucible's own programs are the covered side
        is_b = cc.is_burned(name, burned)
        for prog in _program_files(corpus):
            try:
                uses = command_uses(read_source(prog).text)
            except OSError:
                continue
            for key, opts in uses.items():
                for o in opts:
                    row = out[(key, o)]
                    if is_b:
                        row["burned"].append(f"{name}/{prog.relative_to(corpus).as_posix()}")
                    else:
                        row["census"] += 1
    return out


def modelled_options() -> dict[str, frozenset | None]:
    from gitgalaxy.tools.cobol_to_java.det.cics import OPTIONS

    return dict(OPTIONS)


def gaps(crucible: Path, roots: list[Path]) -> dict[str, Any]:
    """The report: `commands` (modelled, no case) and `options` (case for the command, none for the option)."""
    cases = crucible_uses(crucible)
    used = corpus_uses(roots)
    opts = modelled_options()
    covered_keys = {k for (k, o) in cases if o == ""}
    rows: list[dict[str, Any]] = []
    for key, honoured in sorted(opts.items()):
        names = {""} | (set(honoured) if honoured is not None else {o for (k, o) in used if k == key and o})
        for o in sorted(names):
            if (key, o) in cases:
                continue
            u = used.get((key, o), {"burned": [], "census": 0})
            rows.append({
                "command": key,
                "option": o or None,
                "kind": "command" if o == "" else "option",
                "command_covered": key in covered_keys,
                "burned_programs": len(u["burned"]),
                "burned_corpora": sorted({b.split("/", 1)[0] for b in u["burned"]}),
                "census_programs": u["census"],
            })  # fmt: skip
    rows.sort(key=lambda r: (-r["burned_programs"], -r["census_programs"], r["command"], r["option"] or ""))
    return {
        "commands": [r for r in rows if r["kind"] == "command"],
        "options": [r for r in rows if r["kind"] == "option" and r["command_covered"]],
        "options_of_uncovered_commands": sum(1 for r in rows if r["kind"] == "option" and not r["command_covered"]),
        "modelled_commands": len(opts),
        "covered_commands": len(covered_keys & set(opts)),
    }


def format_report(res: dict[str, Any], top: int = 0, census: bool = True) -> str:
    def table(rows: list[dict[str, Any]], head: str) -> list[str]:
        shown = rows[:top] if top else rows
        out = [f"{'command':<24} {head:<18} {'burned':>6} {'census':>6}  burned corpora"]
        for r in shown:
            out.append(
                f"{r['command']:<24} {(r['option'] or '-'):<18} {r['burned_programs']:>6} "
                f"{(r['census_programs'] if census else 'n/a'):>6}  {', '.join(r['burned_corpora']) or '-'}"
            )
        if len(shown) < len(rows):
            out.append(f"... {len(rows) - len(shown)} more")
        return out

    lines = [
        f"# det-modelled EXEC CICS commands with a crucible case: {res['covered_commands']} of {res['modelled_commands']}",
        f"## commands with no case ({len(res['commands'])}), most used first",
        *table(res["commands"], ""),
        "",
        f"## options of covered commands with no case ({len(res['options'])}), most used first",
        *table(res["options"], "option"),
        "",
        f"(+ {res['options_of_uncovered_commands']} options of the uncovered commands, covered once the command is)",
    ]
    if not census:
        lines.append("census: not measured (no census corpora); the census column is n/a")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    import cics_census as cc

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crucible", type=Path, help="a cics-crucible checkout (default: $CICS_CRUCIBLE_PATH)")
    ap.add_argument("--corpora", type=Path, help="the mainframe corpora root (default: as cics_census)")
    ap.add_argument("--census-corpora", type=Path, help="census clones root (counts only; default: as cics_census)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=0, help="show only the first N rows of each table")
    args = ap.parse_args(argv)
    crucible = args.crucible or (
        Path(os.environ["CICS_CRUCIBLE_PATH"]) if os.environ.get("CICS_CRUCIBLE_PATH") else None
    )
    if crucible is None or not crucible.is_dir():
        print("no cics-crucible checkout: pass --crucible DIR or set CICS_CRUCIBLE_PATH", file=sys.stderr)
        return 2
    roots = [cc.mainframe_root(args.corpora)]
    census = cc.census_root(args.census_corpora, required=False)
    if census:
        roots.append(census)
    res = gaps(crucible, roots)
    res["census_measured"] = census is not None
    if args.json:
        print(json.dumps(res, indent=1))
    else:
        print(format_report(res, args.top, census is not None), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
