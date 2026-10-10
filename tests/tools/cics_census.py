#!/usr/bin/env python3
"""The census of a #4270 CICS command slice: which programs use a command and its options, and whether the det
translator takes them whole, before and after the change -- split burned / non-burned.

    python tests/tools/cics_census.py usage ASSIGN ["SEND TEXT" ...] [--json]
    python tests/tools/cics_census.py survey --out DIR --label before [--verb ASSIGN ...] [--compile]
    python tests/tools/cics_census.py compare DIR --verb ASSIGN [...]
    python tests/tools/cics_census.py blockers DIR [--label before] [--all-programs] [--json]

    python tests/tools/cics_census.py survey --baseline [--root DIR] [--sha SHA]   # once per main SHA, cached
    python tests/tools/cics_census.py blockers --baseline [--sha SHA] [--unmask GAPKEY]
    python tests/tools/cics_census.py compare DIR --before-baseline --verb ASSIGN   # survey only your branch (after)
    python tests/tools/cics_census.py history append --pr N [--note TEXT] | history show

`usage` counts, per corpus and program, the option names each `EXEC CICS <VERB>` uses, and per option the programs
(and the non-burned ones) that use it. Names and counts only: no source text is printed. RESP / RESP2 / NOHANDLE are
left out of the options (every command takes them) unless --all-options. COBOL programs (.cbl/.cob/.cobol, as
det_survey surveys them); --pli adds PL/I programs, flagged, since the det translator takes COBOL only.

`survey` runs tests/tools/det_survey.py (translation only, --no-compile unless --compile) over the burned corpora
into DIR/<label>-b and the non-burned ones into DIR/<label>-nb (census corpora) and DIR/<label>-nb-local (non-burned
corpora fetched under GITGALAXY_MAINFRAME_CORPORA). With --verb, only the corpora where a program uses the verb.

`compare` reads DIR/before-*/survey.json and DIR/after-*/survey.json and prints, for every program using the verb(s):
translated / statements and holes before -> after, burned or not, the holes left after (deduplicated, line numbers
stripped), and the summary counts (programs translated whole, all and non-burned).

`blockers` reads DIR/<label>-*/survey.json (a survey with no --verb: every program) and ranks every gap class --
a CICS command / option, an EXEC SQL gap, a grammar gap (#4462), a missing copybook, a refusal -- by the programs
fixing it would make translate WHOLE: those for which it is the only gap class left (burned / non-burned), those it
leaves one gap class from whole, and all it touches; plus programs whole / total and how many distinct gap classes
each program has. Only programs with an EXEC CICS command unless --all-programs. Pick the next slice by this, the
usage census is the tiebreaker.

The BASELINE (#4270): `survey --baseline` surveys a commit (origin/main, fetched, by default) ONCE and caches it at
<root>/census-cache/<sha>/ (root: --root, else $GG_SCRATCH, else <worktrees dir>/_shared-scratch -- the worktrees dir
is $GITGALAXY_WORKTREES, else the directory holding this worktree, else <main checkout>/../gitgalaxy-worktrees): the commit's own
translator and survey tools (`git archive <sha> gitgalaxy tests/tools pyproject.toml` into src/), its before-*/
surveys, cics_programs.json, blockers.txt/json and meta.json (written last: the cache is complete). Run again for a
cached SHA it does nothing (a lock serialises two agents surveying one SHA). The census clones are --census-corpora,
$CICS_CENSUS_CORPORA, else <root>/census (tests/tools/equivalence_env.py --provision). `blockers --baseline` and
`compare --before-baseline` read it, so an agent only surveys its own branch.

`blockers --unmask GAPKEY` (a `*` row: a refusal that stops the whole program) re-translates only the programs that
gap refuses, with that one refusal check of the det translator switched off (det.source.survey_unmask, honoured only
in det_survey's what-if mode), and reports the gaps hidden behind it and whether any program would become whole.
WHAT-IF, NOT A TRANSLATION: it uses this checkout's translator and the surveyed estates.

`history append --pr N` adds one JSON line (main SHA, date, whole / total, burned + non-burned, refused whole, top 5
gaps, PR) to docs/language_status/blockers_history.jsonl from the cached baseline of origin/main (or --sha); `history
show` prints the series. Names and counts only.

Burned / non-burned comes from ONE place: tests/tools/estate4_draw.py. A corpus is BURNED when its name is one of
the burned estates (BURNED_NAMES: CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication, the async credit-card example);
every other corpus is non-burned. The census repos (estate4_draw.INELIGIBLE_LIST, docs census/INELIGIBLE_FOR_BLIND_ESTATE.md)
are not in .mainframe_corpora: clone them into a scratch directory and pass it as --census-corpora DIR or
$CICS_CENSUS_CORPORA. Blind-estate rule: those repos are read only through translator output and these option
counts; nothing from them is committed. A census-root corpus that is NOT on the census list is warned about: reading
an eligible blind-estate candidate through the translator burns it.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

CENSUS_ENV = "CICS_CENSUS_CORPORA"
PROGRAM_EXTS = {".cbl", ".cob", ".cobol"}  # det_survey.EXTS
PLI_EXTS = {".pli", ".pl1"}  # counted and flagged: the det translator takes COBOL only
EXCEPTION_OPTIONS = {"RESP", "RESP2", "NOHANDLE"}
_LINE_NO = re.compile(r"^line \d+: ")


def burned_names() -> set[str]:
    import estate4_draw

    return {n.lower() for n in estate4_draw.BURNED_NAMES}


def census_names() -> set[str]:
    """Repo names (not owners) of the census-counted repos: estate4_draw.INELIGIBLE_LIST minus the burned estates."""
    import estate4_draw

    burned = burned_names()
    return {r.split("/")[-1].lower() for r in estate4_draw.INELIGIBLE_LIST} - burned


def is_burned(corpus: str, burned: set[str] | None = None) -> bool:
    return corpus.lower() in (burned_names() if burned is None else burned)


# ---- reading EXEC CICS commands (names only) --------------------------------------------------------------------
def fixed_format_text(text: str) -> str:
    """The program's code area (columns 8-72 joined; comment lines dropped), upper-cased."""
    out = []
    for ln in text.splitlines():
        if len(ln) > 6 and ln[6] in "*/":
            continue
        out.append(ln[6:72] if len(ln) > 6 else "")
    return " ".join(out).upper()


def top_level_words(body: str) -> list[str]:
    """The words of a command body outside parentheses and literals: the verb and its option names."""
    words: list[str] = []
    depth, quote, cur = 0, "", []
    for ch in body:
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and (ch.isalnum() or ch == "-"):
            cur.append(ch)
            continue
        if cur:
            words.append("".join(cur))
        cur = []
    if cur:
        words.append("".join(cur))
    return words


def commands(text: str, pli: bool = False) -> list[list[str]]:
    """Each EXEC CICS command of a fixed-format COBOL program (or a PL/I one: ended by `;`), as its top-level words."""
    if pli:
        code = "\n".join(ln[:72] for ln in text.splitlines())  # columns 73-80: sequence numbers
        src = re.sub(r"/\*.*?\*/", " ", code, flags=re.S).upper()
        return [top_level_words(m.group(1)) for m in re.finditer(r"\bEXEC\s+CICS\s+([^;]*);", src)]
    src = fixed_format_text(text)
    return [top_level_words(m.group(1)) for m in re.finditer(r"\bEXEC\s+CICS\s+(.*?)\bEND-EXEC\b", src, re.S)]


def verb_words(verb: str) -> list[str]:
    return verb.upper().replace("-", " ").split()


def options_of(cmd: list[str], verb: list[str], all_options: bool = False) -> list[str] | None:
    """The options of `cmd` when it is the verb, else None."""
    if cmd[: len(verb)] != verb:
        return None
    return [o for o in cmd[len(verb) :] if o[:1].isalpha() and (all_options or o not in EXCEPTION_OPTIONS)]


@dataclass
class ProgramUse:
    corpus: str
    program: str  # path relative to the corpus, as det_survey records it
    burned: bool
    options: dict[str, set[str]] = field(default_factory=dict)  # verb -> option names
    commands: dict[str, int] = field(default_factory=dict)  # verb -> number of commands
    language: str = "cobol"

    @property
    def stem(self) -> str:
        return Path(self.program).stem


def corpus_dirs(roots: list[Path]) -> list[tuple[str, Path]]:
    """(name, dir) of every corpus under the roots, first root wins on a name clash."""
    seen: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            seen.setdefault(d.name, d)
    return sorted(seen.items())


def usage(roots: list[Path], verbs: list[str], all_options: bool = False, pli: bool = False) -> list[ProgramUse]:
    from gitgalaxy.core.source_text import read_source

    burned = burned_names()
    vws = {v: verb_words(v) for v in verbs}
    out = []
    for name, corpus in corpus_dirs(roots):
        progs = sorted(p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in (PROGRAM_EXTS | PLI_EXTS if pli else PROGRAM_EXTS)
                       and ".git" not in p.relative_to(corpus).parts)  # fmt: skip
        for prog in progs:
            try:
                text = read_source(prog).text
            except OSError:
                continue
            is_pli = prog.suffix.lower() in PLI_EXTS
            use = ProgramUse(name, prog.relative_to(corpus).as_posix(), is_burned(name, burned),
                             language="pli" if is_pli else "cobol")  # fmt: skip
            for cmd in commands(text, is_pli):
                for verb, vw in vws.items():
                    opts = options_of(cmd, vw, all_options)
                    if opts is not None:
                        use.options.setdefault(verb, set()).update(opts)
                        use.commands[verb] = use.commands.get(verb, 0) + 1
            if use.commands:
                out.append(use)
    return out


def totals(uses: list[ProgramUse], verb: str) -> list[tuple[str, int, int, int]]:
    """[(option, programs, non-burned programs, PL/I programs)], most used first."""
    progs: dict[str, int] = defaultdict(int)
    nb: dict[str, int] = defaultdict(int)
    pli: dict[str, int] = defaultdict(int)
    for u in uses:
        for o in u.options.get(verb, ()):
            progs[o] += 1
            nb[o] += not u.burned
            pli[o] += u.language == "pli"
    return sorted(((o, progs[o], nb[o], pli[o]) for o in progs), key=lambda t: (-t[1], t[0]))


# ---- roots ------------------------------------------------------------------------------------------------------
def mainframe_root(arg: Path | None) -> Path:
    if arg:
        return arg
    import pr_gates

    env = pr_gates.environment(e2e=False)
    return Path(env.get("GITGALAXY_MAINFRAME_CORPORA") or REPO / ".mainframe_corpora")


def census_root(arg: Path | None, required: bool) -> Path | None:
    path = arg or (Path(os.environ[CENSUS_ENV]) if os.environ.get(CENSUS_ENV) else None)
    if path is None or not path.is_dir():
        if not required:
            return None
        raise SystemExit(
            f"the non-burned census corpora are not given{f' ({path} is not a directory)' if path else ''}: clone the "
            f"census repos (tests/tools/estate4_draw.py INELIGIBLE_LIST, minus the burned estates) into a scratch "
            f"directory and pass --census-corpora DIR or set {CENSUS_ENV} (never commit anything from them), or "
            f"pass --no-census to count the burned / local corpora only"
        )
    known = census_names()
    for name, _ in corpus_dirs([path]):
        if name.lower() not in known and not is_burned(name):
            print(f"warning: {name} (in {path}) is not on estate4_draw.py's census list: if it could be the blind "
                  f"4th estate, reading it through the translator burns it", file=sys.stderr)  # fmt: skip
    return path


def roots_from(args: argparse.Namespace) -> list[Path]:
    roots = [mainframe_root(args.corpora)]
    census = None if args.no_census else census_root(args.census_corpora, required=True)  # (--no-census: no env either)
    return roots + ([census] if census else [])


# ---- usage ------------------------------------------------------------------------------------------------------
def cmd_usage(args: argparse.Namespace) -> int:
    uses = usage(roots_from(args), args.verbs, args.all_options, args.pli)
    if args.json:
        rows = [{"corpus": u.corpus, "program": u.program, "burned": u.burned, "language": u.language,
                 "commands": u.commands,
                 "options": {v: sorted(o) for v, o in u.options.items()}} for u in uses]  # fmt: skip
        tot = {
            v: [{"option": o, "programs": n, "non_burned": k, "pli": p} for o, n, k, p in totals(uses, v)]
            for v in args.verbs
        }
        print(json.dumps({"programs": rows, "totals": tot}, indent=1))
        return 0
    for verb in args.verbs:
        vu = [u for u in uses if verb in u.commands]
        corpora = {u.corpus for u in vu}
        cobol = [u for u in vu if u.language == "cobol"]
        print(f"# EXEC CICS {verb.upper()}: {len(cobol)} COBOL programs ({sum(not u.burned for u in cobol)} "
              f"non-burned) + {len(vu) - len(cobol)} PL/I, in {len(corpora)} corpora, "
              f"{sum(u.commands[verb] for u in vu)} commands")  # fmt: skip
        for u in vu:
            tag = ("B " if u.burned else "NB") + (" PLI" if u.language == "pli" else "    ")
            print(f"{tag}  {u.corpus:<46} {u.program:<40} {' '.join(sorted(u.options[verb]))}")
        print(f"\n{'option':<16} {'programs':>8} {'non-burned':>10} {'of them PL/I':>12}")
        for o, n, k, p in totals(uses, verb):
            print(f"{o:<16} {n:>8} {k:>10} {p:>12}")
        print()
    return 0


# ---- survey -----------------------------------------------------------------------------------------------------
def survey_runs(mainframe: Path, census: Path | None, uses: list[ProgramUse] | None,
                only: list[str] | None) -> list[tuple[str, Path, list[str]]]:  # fmt: skip
    """[(suffix, corpora root, corpus names)] -- one det_survey run each."""
    wanted = {u.corpus for u in uses} if uses is not None else None

    def pick(root: Path, burned: bool | None) -> list[str]:
        names = [n for n, _ in corpus_dirs([root]) if burned is None or is_burned(n) == burned]
        if wanted is not None:
            names = [n for n in names if n in wanted]
        if only:
            names = [n for n in names if n in only]
        return names

    runs = [("b", mainframe, pick(mainframe, True)), ("nb-local", mainframe, pick(mainframe, False))]
    if census:
        local = set(runs[0][2]) | set(runs[1][2])
        runs.append(("nb", census, [n for n in pick(census, None) if n not in local]))
    return [r for r in runs if r[2]]


def cmd_survey(args: argparse.Namespace) -> int:
    if args.baseline:
        return cmd_survey_baseline(args)
    if args.out is None:
        raise SystemExit("survey needs --out DIR (or --baseline)")
    mainframe = mainframe_root(args.corpora)
    census = None if args.no_census else census_root(args.census_corpora, required=True)  # (--no-census: no env either)
    uses = usage([mainframe, *([census] if census else [])], args.verb) if args.verb else None
    runs = survey_runs(mainframe, census, uses, args.corpus)
    return run_det_survey(args.out, args.label, runs, jobs=args.jobs, compile_ports=args.compile)


# ---- compare ----------------------------------------------------------------------------------------------------
def load_surveys(d: Path, label: str) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for f in sorted(d.glob(f"{label}-*/survey.json")):
        for corpus, rows in json.loads(f.read_text(encoding="utf-8")).items():
            for r in rows:
                out[(corpus, r["program"])] = r
    return out


def whole(r: dict[str, Any] | None) -> bool:
    return r is not None and "error" not in r and "statements" in r and not r.get("holes")


def describe(r: dict[str, Any] | None) -> str:
    if r is None:
        return "MISSING"
    if "error" in r:
        return "ERROR " + re.sub(r"/\S+", "<path>", r["error"])[:60]
    return f"{r['translated']}/{r['statements']} holes={len(r['holes'])}"


def holes(r: dict[str, Any] | None) -> list[str]:
    return sorted({_LINE_NO.sub("", h) for h in (r or {}).get("holes", [])})


def compare_rows(uses: list[ProgramUse], before: dict[tuple[str, str], dict[str, Any]],
                 after: dict[tuple[str, str], dict[str, Any]], verbs: list[str]) -> dict[str, Any]:  # fmt: skip
    rows = []
    summary = {"programs": len(uses), "non_burned": sum(not u.burned for u in uses),
               "whole_before": 0, "whole_after": 0, "whole_before_nb": 0, "whole_after_nb": 0,
               "missing_before": 0, "missing_after": 0, "verb_holes_before": 0, "verb_holes_after": 0}  # fmt: skip
    vws = [" ".join(verb_words(v)) for v in verbs]
    for u in sorted(uses, key=lambda u: (u.burned, u.corpus, u.program)):
        k = (u.corpus, u.program)
        b, a = before.get(k), after.get(k)
        for tag, r in (("before", b), ("after", a)):
            summary[f"whole_{tag}"] += whole(r)
            summary[f"whole_{tag}_nb"] += whole(r) and not u.burned
            summary[f"missing_{tag}"] += r is None
            summary[f"verb_holes_{tag}"] += sum(any(v in h.upper() for v in vws) for h in holes(r))
        rows.append({"corpus": u.corpus, "program": u.program, "burned": u.burned,
                     "options": sorted({o for v in verbs for o in u.options.get(v, ())}),
                     "before": describe(b), "after": describe(a), "holes_after": holes(a)})  # fmt: skip
    return {"rows": rows, "summary": summary}


def cmd_compare(args: argparse.Namespace) -> int:
    uses = [u for u in usage(roots_from(args), args.verb, args.all_options) if u.language == "cobol"]  # det: COBOL
    before_dir = baseline_dir(args) if args.before_baseline else args.dir
    before = load_surveys(before_dir, "before" if args.before_baseline else args.before)
    after = load_surveys(args.dir, args.after)
    if not before or not after:
        raise SystemExit(f"no {args.before}-*/survey.json (under {before_dir}) or {args.after}-*/survey.json under {args.dir} "
                         f"(run `cics_census.py survey --out {args.dir} --label ...` before and after)")  # fmt: skip
    res = compare_rows(uses, before, after, args.verb)
    if args.json:
        print(json.dumps(res, indent=1))
        return 0
    for r in res["rows"]:
        print(f"{'B ' if r['burned'] else 'NB'}  {r['corpus'][:30]:<30} {Path(r['program']).stem:<10} "
              f"{','.join(r['options'])[:30]:<30} {r['before']} -> {r['after']}")  # fmt: skip
        for h in r["holes_after"]:
            print(f"      hole: {h[:110]}")
    s = res["summary"]
    print(
        f"\nprograms using {' / '.join(v.upper() for v in args.verb)}: {s['programs']} ({s['non_burned']} non-burned)"
    )
    print(f"translated whole: {s['whole_before']} -> {s['whole_after']} (non-burned {s['whole_before_nb']} -> "
          f"{s['whole_after_nb']})")  # fmt: skip
    print(f"holes naming the verb: {s['verb_holes_before']} -> {s['verb_holes_after']}")
    if s["missing_before"] or s["missing_after"]:
        print(f"not surveyed: {s['missing_before']} before, {s['missing_after']} after (a corpus left out of a run?)")
    return 0


# ---- blockers ---------------------------------------------------------------------------------------------------
_TAIL_PAREN = re.compile(r"\s*\((?:[^()]|\([^()]*\))*\)\s*$")
_PATH = re.compile(r"(?:[A-Za-z]:)?[/\\]\S+?(?::\d+)?(?=:|\s|$)")
_AT_LINE = re.compile(r"(?:\bat )?\bline \d+:?\s*", re.I)
REFUSES = ("refused", "missing copybook")  # gap classes that stop the whole program (no statements translated)


def _generic(text: str) -> str:
    """A hole / error message without its specifics: literals, argument lists, data / paragraph / map names, numbers.
    A name with no hyphen and no digit (DIBSTAT, CBLTDLI, an IBM routine) is kept: it often IS the gap."""
    text = re.sub(r"`[^`]*`", "`…`", text)  # quoted source text (a cut literal's tail): never kept, never a key
    text = re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", text)
    text = re.sub(r"\((?:[^()]|\([^()]*\))*\)", "(…)", text)
    text = re.sub(r"\b[A-Z][A-Za-z0-9]*\.[a-z]\w*\b", "<class>.<property>", text)  # a generated Java name
    text = re.sub(r"\b[A-Z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+\b", "<name>", text)  # WS-AREA, WS-Qarea, DATA_ITEM
    text = re.sub(r"\b[A-Z][A-Z]*\d[A-Z0-9]*\b", "<name>", text)  # BNK1CCM, C1
    text = re.sub(r"\b(map|COMMAREA) [A-Z][\w-]*", r"\1 <name>", text)
    text = re.sub(r"\b\d+\b", "N", text)
    return re.sub(r"\s+", " ", text).strip(" :")


def gap_key(hole: str) -> str:
    """One hole -> its gap class, line numbers and specifics stripped: `EXEC CICS GETMAIN`, `EXEC CICS ASSIGN APPLID`,
    `EXEC SQL: ...`, `EXEC DLI`, `grammar: does not parse`, `CALL CBLTDLI`, `<name>: no such item`, ..."""
    h = _LINE_NO.sub("", hole).strip()
    kind, _, why = h.partition(" ")
    why = _TAIL_PAREN.sub("", why).strip()  # the issue / slice / oracle_assumptions note in parentheses
    if kind == "EXEC" and why.startswith(("EXEC CICS", "CICS")):
        why = why.split(":", 1)[1].strip() if ":" in why else ""
        m = re.fullmatch(r"(?:EXEC CICS )?([A-Z][A-Z0-9 ]*?):? (?:option )?not modelled", why)
        if m:
            return "EXEC CICS " + m.group(1)
        return "EXEC CICS " + (_generic(why) or "(no reason given)")
    if kind == "EXEC" and why.startswith("EXEC SQL"):
        return "EXEC SQL: " + _generic(why.split(":", 1)[-1].strip())
    if kind == "EXEC":
        return _generic(why)  # EXEC DLI, ...
    if kind == "HOLE":  # the statement parser's own holes: grammar gaps (#4462), unmodelled verbs
        if why in ("does not parse", "not parsed") or why.startswith("grammar node"):
            return "grammar: " + _generic(why)
        return _generic(why)
    # a map field, DIBSTAT, an undeclared host variable ...: one class whatever the name
    if re.fullmatch(r"[A-Z][\w-]*: (?:no such|undeclared) item", why):
        return "<name>: " + why.split(": ", 1)[1]
    if why.startswith(kind + " ") or re.match(r"[A-Z][\w-]*: ", why):  # CALL CALL X / MOVE ITEM: no such item
        return _generic(why)
    return _generic(f"{kind} {why}")


def error_key(error: str) -> str:
    """A program the translator refused whole -> its gap class: `missing copybook BAQRI`, `refused: ExprError: ...`."""
    m = re.search(r"\bCOPY\s+([A-Z0-9@#$_-]+)", error, re.I)
    if error.startswith(("CopyNotFound", "CopyAmbiguous")) and m:
        return f"missing copybook {m.group(1).upper()}" + (" (ambiguous)" if error.startswith("CopyAmbiguous") else "")
    etype, _, msg = error.partition(": ")
    msg = re.sub(r"^\S+\.\w+:\d+:\s*", "", msg)  # the member and line it stopped at
    msg = re.sub(r"\s*\[[^\]]*\]", "", _AT_LINE.sub("", _PATH.sub("<path>", msg)))
    return f"refused: {etype}: {_generic(msg)}"[:120]


def gap_classes(r: dict[str, Any]) -> set[str]:
    """The distinct gap classes keeping one survey row from translating whole (empty: whole)."""
    if "error" in r:
        return {error_key(r["error"])}
    if "statements" not in r:
        return {"refused: no result"}
    return {gap_key(h) for h in r.get("holes", [])}


def cics_programs(roots: list[Path]) -> set[tuple[str, str]]:
    """(corpus, program) of every COBOL program with an EXEC CICS command (names only, as `usage` reads them)."""
    from gitgalaxy.core.source_text import read_source

    out = set()
    for name, corpus in corpus_dirs(roots):
        for prog in corpus.rglob("*"):
            if prog.is_file() and prog.suffix.lower() in PROGRAM_EXTS and ".git" not in prog.relative_to(corpus).parts:
                try:
                    if commands(read_source(prog).text):
                        out.add((name, prog.relative_to(corpus).as_posix()))
                except OSError:
                    continue
    return out


def blockers(rows: dict[tuple[str, str], dict[str, Any]], only: set[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Rank every gap class by the programs fixing it would make translate WHOLE: `only` = programs for which it is
    the only gap class left (split burned / non-burned), `one_away` = programs it leaves one gap class from whole,
    `touched` = programs with it at all. A `refused` class stops the whole program: what fixing it reveals is not
    known yet, so its `only` count is an upper bound."""
    burned = burned_names()
    progs = {k: (is_burned(k[0], burned), gap_classes(r)) for k, r in rows.items() if only is None or k in only}
    stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hist: dict[int, int] = defaultdict(int)
    for b, classes in progs.values():
        hist[len(classes)] += 1
        for g in classes:
            st, tag = stats[g], "burned" if b else "non_burned"
            st["touched"] += 1
            st[f"touched_{tag}"] += 1
            if len(classes) <= 2:
                which = "only" if len(classes) == 1 else "one_away"
                st[which] += 1
                st[f"{which}_{tag}"] += 1
    keys = ("only", "only_burned", "only_non_burned", "one_away", "one_away_burned", "one_away_non_burned",
            "touched", "touched_burned", "touched_non_burned")  # fmt: skip
    gaps: list[dict[str, Any]] = [
        {"gap": g, **{k: st.get(k, 0) for k in keys}, "refuses_program": g.startswith(REFUSES)}
        for g, st in stats.items()
    ]
    gaps.sort(key=lambda d: (-d["only"], -d["only_non_burned"], -d["one_away"], -d["touched"], d["gap"]))
    nb = [k for k, (b, _) in progs.items() if not b]
    return {
        "programs": len(progs),
        "non_burned": len(nb),
        "whole": sum(not g for _, g in progs.values()),
        "whole_non_burned": sum(not progs[k][1] for k in nb),
        "refused": sum(any(x.startswith(REFUSES) for x in g) for _, g in progs.values()),
        "histogram": {str(n): hist[n] for n in sorted(hist)},
        "gaps": gaps,
    }


def format_blockers(res: dict[str, Any], where: str, top: int = 0) -> str:
    out = [f"# blockers in {where}: {res['scope']}",
           f"translated whole: {res['whole']} / {res['programs']} (non-burned {res['whole_non_burned']} / "
           f"{res['non_burned']}); refused whole (no statements translated): {res['refused']}"]  # fmt: skip
    if res.get("cics_programs_not_surveyed"):
        out.append(
            f"CICS programs with no survey row: {res['cics_programs_not_surveyed']} (a corpus left out of the run?)"
        )
    out.append("distinct gap classes per program: " + ", ".join(f"{n}: {c}" for n, c in res["histogram"].items()))
    out.append(f"\n{'only gap (B/NB)':>16} {'one away (B/NB)':>16} {'touched':>8}  gap  (* = refuses the whole program: "
               f"its count is an upper bound; `--unmask GAP` shows what it hides)")  # fmt: skip
    for g in res["gaps"][: top or None]:
        out.append(f"{g['only']:>6} ({g['only_burned']:>2}/{g['only_non_burned']:>2}) {g['one_away']:>6} "
                   f"({g['one_away_burned']:>2}/{g['one_away_non_burned']:>2}) {g['touched']:>8}  "
                   f"{'*' if g['refuses_program'] else ' '}{g['gap'][:110]}")  # fmt: skip
    return "\n".join(out)


def cmd_blockers(args: argparse.Namespace) -> int:
    if args.baseline:
        d, label = baseline_dir(args), "before"
        if args.unmask:
            only = None if args.all_programs else {tuple(p) for p in json.loads((d / "cics_programs.json").read_text())}
            slug = re.sub(r"[^a-z0-9]+", "-", args.unmask.lower()).strip("-")[:60]
            return cmd_unmask(args, d, label, only, d / "unmask" / slug)  # type: ignore[arg-type]
        res = baseline_blockers(d, args.all_programs)
        where = f"baseline {d.name[:12]} ({json.loads((d / 'meta.json').read_text())['scope']})"
    else:
        if args.dir is None:
            raise SystemExit("blockers needs a survey DIR or --baseline")
        rows = load_surveys(args.dir, args.label)
        if not rows:
            raise SystemExit(f"no {args.label}-*/survey.json under {args.dir} (run `cics_census.py survey --out "
                             f"{args.dir} --label {args.label}` first)")  # fmt: skip
        only = None if args.all_programs else cics_programs(roots_from(args))
        if args.unmask:
            return cmd_unmask(args, args.dir, args.label, only, args.dir / f"unmask-{args.label}")
        res = blockers(rows, only)
        res["scope"] = "every surveyed program" if only is None else "programs with an EXEC CICS command"
        if only is not None:
            res["cics_programs_not_surveyed"] = len(only - set(rows))
        where = f"{args.dir}/{args.label}-*"
    if args.json:
        print(json.dumps(res, indent=1))
        return 0
    print(format_blockers(res, where, args.top))
    return 0


# ---- the baseline cache (#4270): one before-survey per main SHA, shared by every agent ---------------------------
CACHE = "census-cache"
SNAPSHOT_PATHS = ("gitgalaxy", "tests/tools", "pyproject.toml")  # what det_survey needs from the surveyed commit
HISTORY = REPO / "docs" / "language_status" / "blockers_history.jsonl"


def _git(*argv: str) -> str:
    res = subprocess.run(["git", "-C", str(REPO), *argv], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if res.returncode:
        raise SystemExit(f"git {' '.join(argv)} failed: {res.stderr.strip()[:300]}")
    return res.stdout.strip()


def resolve_sha(sha: str | None, fetch: bool = False) -> str:
    """The full commit SHA of `sha`, default origin/main (fetched first when `fetch`; a failed fetch is a warning)."""
    if sha is None and fetch:
        res = subprocess.run(["git", "-C", str(REPO), "fetch", "-q", "origin", "main"],  # noqa: S603, S607
                             capture_output=True, text=True, check=False)  # fmt: skip
        if res.returncode:
            print(f"warning: git fetch origin main failed ({res.stderr.strip()[:200]}): using the local origin/main",
                  file=sys.stderr)  # fmt: skip
    return _git("rev-parse", "--verify", f"{sha or 'origin/main'}^{{commit}}")


def scratch_root(arg: Path | None) -> Path:
    import equivalence_env

    return equivalence_env.scratch_root(arg)


def cache_dir(root: Path, sha: str) -> Path:
    return root / CACHE / sha


@contextlib.contextmanager
def _locked(path: Path) -> Iterator[None]:
    """An exclusive lock on `path` (another agent surveying the same SHA waits, then finds the cache)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        try:
            import fcntl
        except ImportError:  # Windows: no shared box there
            yield
            return
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def snapshot(sha: str, dest: Path) -> Path:
    """The surveyed commit's translator and survey tools (SNAPSHOT_PATHS of `sha`), unpacked at `dest`."""
    if (dest / "tests" / "tools" / "det_survey.py").is_file():
        return dest
    import tarfile
    import tempfile

    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as td:
        tar = Path(td) / "src.tar"
        _git("archive", "--format=tar", "-o", str(tar), sha, *SNAPSHOT_PATHS)
        with tarfile.open(tar) as tf:
            tf.extractall(tmp, filter="data")  # noqa: S202 (our own git archive)
    tmp.rename(dest)
    return dest


def run_det_survey(out: Path, label: str, runs: list[tuple[str, Path, list[str]]], *, jobs: int = 4,
                   compile_ports: bool = False, src: Path = REPO, extra: list[str] | None = None) -> int:  # fmt: skip
    """det_survey.py (from `src`: this checkout, or a commit's snapshot) once per run into OUT/<label>-<suffix>."""
    import pr_gates

    env = pr_gates.environment(e2e=True)
    env["PYTHONPATH"] = str(src)
    out.mkdir(parents=True, exist_ok=True)
    rc = 0
    for suffix, root, names in runs:
        work = out / f"{label}-{suffix}"
        argv = [
            sys.executable,
            str(src / "tests" / "tools" / "det_survey.py"),
            "--work",
            str(work),
            "--jobs",
            str(jobs),
        ]
        argv += [] if compile_ports else ["--no-compile"]
        for n in names:
            argv += ["--corpus", n]
        argv += extra or []
        log = out / f"{label}-{suffix}.log"
        print(f"{label}-{suffix}: {len(names)} corpora from {root} -> {work} (log {log})", flush=True)
        with log.open("wb") as fh:
            res = subprocess.run(argv, cwd=src, env=dict(env, GITGALAXY_MAINFRAME_CORPORA=str(root)),  # noqa: S603
                                 stdout=fh, stderr=subprocess.STDOUT, check=False)  # fmt: skip
        if res.returncode or not (work / "survey.json").is_file():
            print(f"  det_survey exited {res.returncode} (survey.json written: {(work / 'survey.json').is_file()}): "
                  f"see {log}", file=sys.stderr)  # fmt: skip
            rc = 1
    (out / f"{label}-runs.json").write_text(json.dumps({s: str(r) for s, r, _ in runs}, indent=1) + "\n",
                                            encoding="utf-8")  # fmt: skip
    return rc


def baseline_census(args: argparse.Namespace, root: Path) -> Path | None:
    """The census clones a baseline surveys: --census-corpora, $CICS_CENSUS_CORPORA, else the provisioned
    <root>/census (equivalence_env.py --provision); None with --no-census."""
    if args.no_census:
        return None
    provisioned = root / "census"
    arg = args.census_corpora or (None if os.environ.get(CENSUS_ENV) else provisioned if provisioned.is_dir() else None)
    return census_root(arg, required=True)


def cmd_survey_baseline(args: argparse.Namespace) -> int:
    root = scratch_root(args.root)
    sha = resolve_sha(args.sha, fetch=not args.no_fetch)
    d = cache_dir(root, sha)
    mainframe = mainframe_root(args.corpora)
    census = baseline_census(args, root)
    with _locked(d.parent / f"{sha}.lock"):
        meta_file = d / "meta.json"
        if meta_file.is_file() and not args.force:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if meta.get("census") != (census is not None):
                print(f"baseline {sha[:12]} is cached at {d} surveyed {meta.get('scope')}, but this run asks for "
                      f"{'burned + census' if census else 'no census'}: pass --force to survey it again",
                      file=sys.stderr)  # fmt: skip
                return 2
            print(f"baseline {sha[:12]} already surveyed ({meta.get('scope')}, {meta.get('surveyed_utc')}): {d} -- "
                  f"nothing to do")  # fmt: skip
            print(format_blockers(baseline_blockers(d), f"baseline {sha[:12]}", top=args.top or 10))
            return 0
        if args.force:
            for p in d.glob("before-*"):
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            for name in ("meta.json", "cics_programs.json", "blockers.json", "blockers.txt"):
                (d / name).unlink(missing_ok=True)
        start = time.time()
        src = snapshot(sha, d / "src")
        runs = survey_runs(mainframe, census, None, args.corpus)
        print(f"baseline {sha[:12]}: surveying with that commit's translator ({src})", flush=True)
        rc = run_det_survey(d, "before", runs, jobs=args.jobs, compile_ports=args.compile, src=src)
        if rc:
            print(f"baseline {sha[:12]}: a survey run failed; the cache is left incomplete (no meta.json): rerun",
                  file=sys.stderr)  # fmt: skip
            return rc
        roots = [mainframe, *([census] if census else [])]
        progs = sorted(cics_programs(roots))
        (d / "cics_programs.json").write_text(json.dumps([list(p) for p in progs], indent=0) + "\n", encoding="utf-8")
        scope = "burned + local + census corpora" if census else "burned + local corpora (no census)"
        meta = {"sha": sha, "surveyed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "scope": scope,
                "census": census is not None, "seconds": round(time.time() - start),
                "runs": {s: {"root": str(r), "corpora": names} for s, r, names in runs},
                "translator": f"git archive {sha} ({', '.join(SNAPSHOT_PATHS)})"}  # fmt: skip
        res = baseline_blockers(d)
        (d / "blockers.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
        text = format_blockers(res, f"baseline {sha[:12]} ({scope})")
        (d / "blockers.txt").write_text(text + "\n", encoding="utf-8")
        (d / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")  # last: marks it complete
    print(f"baseline {sha[:12]} surveyed in {meta['seconds']}s: {d}")
    print("\n".join(text.splitlines()[: 4 + (args.top or 10)]))
    return 0


def baseline_blockers(d: Path, all_programs: bool = False) -> dict[str, Any]:
    rows = load_surveys(d, "before")
    only = None if all_programs else {tuple(p) for p in json.loads((d / "cics_programs.json").read_text())}
    res = blockers(rows, only)  # type: ignore[arg-type]
    res["scope"] = "every surveyed program" if only is None else "programs with an EXEC CICS command"
    if only is not None:
        res["cics_programs_not_surveyed"] = len(only - set(rows))
    return res


def baseline_dir(args: argparse.Namespace) -> Path:
    """The cached baseline of --sha (default origin/main, not fetched); a clear error naming the cached ones."""
    root = scratch_root(args.root)
    sha = resolve_sha(args.sha)
    d = cache_dir(root, sha)
    if not (d / "meta.json").is_file():
        have = sorted((p for p in (root / CACHE).glob("*/meta.json")), key=lambda p: -p.stat().st_mtime)
        listed = ", ".join(p.parent.name[:12] for p in have[:5]) or "none"
        raise SystemExit(f"no baseline for {sha[:12]} under {root / CACHE} (cached: {listed}): run "
                         f"`cics_census.py survey --baseline` first (or pass --sha)")  # fmt: skip
    return d


# ---- --unmask: what a whole-program refusal hides (a what-if, never a translation) -------------------------------
# a gap class (error_key) -> the det translator's refusal check a survey may switch off (det.source.UNMASKABLE)
UNMASK_CHECKS = (
    (re.compile(r"source defect: source text past column", re.I), "cut-literal"),
    (re.compile(r"several programs in one source", re.I), "several-programs"),
    (re.compile(r"national / DBCS|national letter|IDMS DML|DECIMAL-POINT IS COMMA|control character", re.I),
     "unmodelled"),
    (re.compile(r"^missing copybook \S+$"), "missing-copybook"),  # not an ambiguous one: that member exists twice
)  # fmt: skip


def unmask_check(gap: str) -> str | None:
    return next((check for rx, check in UNMASK_CHECKS if rx.search(gap)), None)


def load_runs(d: Path, label: str) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    """{run suffix: {(corpus, program): row}} of DIR/<label>-<suffix>/survey.json."""
    out: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for f in sorted(d.glob(f"{label}-*/survey.json")):
        suffix = f.parent.name[len(label) + 1 :]
        out[suffix] = {
            (c, r["program"]): r for c, rows in json.loads(f.read_text(encoding="utf-8")).items() for r in rows
        }
    return out


def unmask_targets(runs: dict[str, dict[tuple[str, str], dict[str, Any]]], gap: str) -> tuple[list[str], str]:
    """(the refusing gap classes `gap` names, the one check behind them). Exact first, else a case-insensitive
    substring; every class must map to the same check. SystemExit (2) with the candidates otherwise."""
    gap = gap.strip().lstrip("*").strip()
    refusing = sorted({error_key(r["error"]) for rows in runs.values() for r in rows.values() if "error" in r})
    keys = [g for g in refusing if g == gap] or [g for g in refusing if gap.lower() in g.lower()]
    if not keys:
        raise SystemExit("no whole-program refusal (a `*` row) matches " + repr(gap) + "; the refusing gaps are:\n  "
                         + "\n  ".join(refusing))  # fmt: skip
    checks = {unmask_check(k) for k in keys}
    if checks == {None}:
        names = ", ".join(k for k in keys if unmask_check(k) is None)
        raise SystemExit(f"no survey-mode switch for {names}: the det translator can lift only these refusal checks "
                         f"in a what-if (det.source.UNMASKABLE): {', '.join(c for _, c in UNMASK_CHECKS)}")  # fmt: skip
    if len(checks) > 1:
        raise SystemExit(f"{gap!r} matches gaps behind different checks ({', '.join(sorted(map(str, checks)))}; None: "
                         "no switch): "
                         "name one of them:\n  " + "\n  ".join(keys))  # fmt: skip
    return keys, checks.pop()  # type: ignore[return-value]


def unmask_report(before: dict[tuple[str, str], dict[str, Any]], after: dict[tuple[str, str], dict[str, Any]],
                  keys: list[str], check: str, only: set[tuple[str, str]] | None) -> dict[str, Any]:  # fmt: skip
    burned = burned_names()
    hidden: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    programs = []
    for k in sorted(before):
        r = after.get(k)
        b = is_burned(k[0], burned)
        classes = sorted(gap_classes(r)) if r is not None else ["(not re-surveyed)"]
        for g in classes:
            hidden[g]["programs"] += 1
            hidden[g]["burned" if b else "non_burned"] += 1
        programs.append({"corpus": k[0], "program": k[1], "burned": b, "cics": only is None or k in only,
                         "after": describe(r), "whole": whole(r), "gaps": classes,
                         "still_refused": r is not None and "error" in r})  # fmt: skip
    gaps: list[dict[str, Any]] = [{"gap": g, **v} for g, v in hidden.items()]
    gaps.sort(key=lambda d: (-d["programs"], d["gap"]))
    return {"what_if": True, "note": "WHAT-IF, NOT A TRANSLATION: one refusal check was switched off in survey mode",
            "gap": keys, "check": check, "programs": len(programs),
            "non_burned": sum(not p["burned"] for p in programs),
            "would_be_whole": sum(p["whole"] for p in programs),
            "would_be_whole_non_burned": sum(p["whole"] and not p["burned"] for p in programs),
            "still_refused": sum(p["still_refused"] for p in programs),
            "hidden_gaps": gaps, "per_program": programs}  # fmt: skip


def format_unmask(res: dict[str, Any], where: str) -> str:
    out = [f"# WHAT-IF, NOT A TRANSLATION -- {' | '.join(res['gap'])}",
           f"# refusal check `{res['check']}` switched off in survey mode only (det.source.survey_unmask; "
           f"translator: {where})",
           f"programs it refuses whole: {res['programs']} (non-burned {res['non_burned']})",
           f"would translate whole with it lifted: {res['would_be_whole']} (non-burned "
           f"{res['would_be_whole_non_burned']}); still refused by another check: {res['still_refused']}",
           "", f"{'programs':>8} {'B/NB':>7}  gap hidden behind it"]  # fmt: skip
    out += [f"{g['programs']:>8} {g.get('burned', 0):>3}/{g.get('non_burned', 0):<3}  {g['gap'][:110]}"
            for g in res["hidden_gaps"]]  # fmt: skip
    out += ["", "per program (what-if):"]
    out += [f"  {'B ' if p['burned'] else 'NB'}  {p['corpus'][:30]:<30} {Path(p['program']).stem:<12} refused -> "
            f"{p['after']}{'  WHOLE' if p['whole'] else ''}" for p in res["per_program"]]  # fmt: skip
    return "\n".join(out)


def cmd_unmask(args: argparse.Namespace, d: Path, label: str, only: set[tuple[str, str]] | None,
               out: Path) -> int:  # fmt: skip
    runs = load_runs(d, label)
    keys, check = unmask_targets(runs, args.unmask)
    roots_file = d / f"{label}-runs.json"
    roots: dict[str, str] = json.loads(roots_file.read_text(encoding="utf-8")) if roots_file.is_file() else {}
    if (d / "meta.json").is_file():
        roots |= {s: v["root"] for s, v in json.loads((d / "meta.json").read_text(encoding="utf-8"))["runs"].items()}
    shutil.rmtree(out, ignore_errors=True)
    before: dict[tuple[str, str], dict[str, Any]] = {}
    plan: list[tuple[str, Path, list[str], list[str]]] = []
    for suffix, rows in runs.items():
        hit = {k: r for k, r in rows.items() if "error" in r and error_key(r["error"]) in keys
               and (only is None or k in only)}  # fmt: skip
        if not hit:
            continue
        if suffix not in roots:
            raise SystemExit(f"which corpora root {label}-{suffix} was surveyed from is not recorded ({roots_file}): "
                             f"re-run its survey with this tool")  # fmt: skip
        before |= hit
        plan.append((suffix, Path(roots[suffix]), sorted({c for c, _ in hit}), sorted({p for _, p in hit})))
    if not before:
        raise SystemExit(f"no {'CICS ' if only is not None else ''}program is refused by {' | '.join(keys)}")
    rc = 0
    for suffix, root, corpora, progs in plan:
        extra = ["--unmask", check, "--estate-from", str(d / f"{label}-{suffix}")]
        for p in progs:
            extra += ["--program", p]
        rc |= run_det_survey(out, "whatif", [(suffix, root, corpora)], extra=extra)
    after = load_surveys(out, "whatif")
    res = unmask_report(before, after, keys, check, only)
    head = _git("rev-parse", "--short=12", "HEAD")
    (out / "whatif.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(res, indent=1))
    else:
        print(format_unmask(res, f"this checkout {head}"))
        print(f"\n(what-if rows: {out}/whatif-*/survey.json)")
    return rc


# ---- history: the whole counts per merged slice -------------------------------------------------------------------
def history_entry(res: dict[str, Any], sha: str, date: str, pr: int, note: str | None, scope: str) -> dict[str, Any]:
    total, nb = res["programs"], res["non_burned"]
    w, wnb = res["whole"], res["whole_non_burned"]
    top = [{k: g[k] for k in ("gap", "only", "only_burned", "only_non_burned", "refuses_program")}
           for g in res["gaps"][:5]]  # fmt: skip
    entry = {"pr": pr, "main_sha": sha, "date": date, "whole": w, "total": total, "whole_burned": w - wnb,
             "total_burned": total - nb, "whole_non_burned": wnb, "total_non_burned": nb,
             "refused_whole": res["refused"], "top_gaps": top, "scope": scope}  # fmt: skip
    if note:
        entry["note"] = note
    return entry


def read_history(path: Path = HISTORY) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def cmd_history(args: argparse.Namespace) -> int:
    path = args.file or HISTORY
    if args.action == "show":
        rows = read_history(path)
        if args.json:
            print(json.dumps(rows, indent=1))
            return 0
        print(f"{'date':<10} {'PR':>6} {'main SHA':<10} {'whole':>9} {'burned':>7} {'non-burned':>10} {'refused':>7}"
              f"  top gap")  # fmt: skip
        for e in rows:
            top = e["top_gaps"][0]["gap"] if e.get("top_gaps") else "-"
            ref = "?" if e.get("refused_whole") is None else e["refused_whole"]
            print(f"{e['date'][:10]:<10} {'#' + str(e['pr']):>6} {e['main_sha'][:9]:<10} "
                  f"{e['whole']:>4}/{e['total']:<4} {e['whole_burned']:>3}/{e['total_burned']:<3} "
                  f"{e['whole_non_burned']:>5}/{e['total_non_burned']:<4} {ref!s:>7}  {top[:70]}"
                  f"{'  (note)' if e.get('note') else ''}")  # fmt: skip
        return 0
    if args.pr is None:
        raise SystemExit("history append needs --pr N (the merged slice)")
    d = baseline_dir(args)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    sha = meta["sha"]
    if any(e["pr"] == args.pr and e["main_sha"] == sha for e in read_history(path)):
        print(f"history already has #{args.pr} at {sha[:12]}: nothing appended", file=sys.stderr)
        return 2
    stamp = _git("show", "-s", "--format=%ct", sha)
    date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(stamp))) if stamp.isdigit() else stamp
    entry = history_entry(baseline_blockers(d), sha, date, args.pr, args.note, meta["scope"])
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"appended to {path}: #{args.pr} {sha[:12]} whole {entry['whole']}/{entry['total']} (non-burned "
          f"{entry['whole_non_burned']}/{entry['total_non_burned']}), refused whole {entry['refused_whole']}")  # fmt: skip
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpora", type=Path, help="the burned / local corpora root (default: "
                        "$GITGALAXY_MAINFRAME_CORPORA, else <main checkout>/.mainframe_corpora)")  # fmt: skip
    common.add_argument("--census-corpora", type=Path, help=f"the non-burned census clones (default: ${CENSUS_ENV})")
    common.add_argument("--no-census", action="store_true", help="count without the census corpora")
    common.add_argument("--all-options", action="store_true", help="keep RESP / RESP2 / NOHANDLE among the options")
    base = argparse.ArgumentParser(add_help=False)
    base.add_argument("--root", type=Path, help="the shared scratch root holding census-cache/ (default: $GG_SCRATCH, "
                      "else <worktrees dir>/_shared-scratch)")  # fmt: skip
    base.add_argument("--sha", help="the baseline commit (default: origin/main)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("usage", parents=[common], help="option names per program and totals")
    u.add_argument("verbs", nargs="+", metavar="VERB", help='e.g. ASSIGN, START, "SEND TEXT" (or SEND-TEXT)')
    u.add_argument("--json", action="store_true")
    u.add_argument("--pli", action="store_true", help="also count PL/I programs (flagged; the det translator takes "
                   "COBOL only)")  # fmt: skip
    s = sub.add_parser("survey", parents=[common, base], help="det_survey.py over the burned and non-burned corpora")
    s.add_argument("--out", type=Path, help="the survey directory (not with --baseline)")
    s.add_argument("--baseline", action="store_true", help="survey --sha (origin/main) once into the shared cache")
    s.add_argument("--no-fetch", action="store_true", help="--baseline: do not fetch origin/main first")
    s.add_argument("--force", action="store_true", help="--baseline: survey a cached SHA again")
    s.add_argument("--top", type=int, default=0, help="--baseline: gaps printed (default 10)")
    s.add_argument("--label", default="before", help="before | after (the run directory prefix)")
    s.add_argument("--verb", nargs="+", help="only the corpora where a program uses one of these")
    s.add_argument("--corpus", nargs="+", help="only these corpus names")
    s.add_argument("--compile", action="store_true", help="also compile each port (det_survey without --no-compile)")
    s.add_argument("--jobs", type=int, default=4)
    c = sub.add_parser("compare", parents=[common, base], help="before / after table of the programs using the verb")
    c.add_argument("dir", type=Path)
    c.add_argument("--verb", nargs="+", required=True)
    c.add_argument("--before", default="before")
    c.add_argument("--after", default="after")
    c.add_argument("--json", action="store_true")
    c.add_argument("--before-baseline", action="store_true", help="the before rows from the cached baseline of --sha "
                   "(survey --baseline), the after rows from DIR")  # fmt: skip
    k = sub.add_parser("blockers", parents=[common, base], help="rank every gap by the programs fixing it makes whole")
    k.add_argument("dir", type=Path, nargs="?", help="a survey directory (or --baseline)")
    k.add_argument("--baseline", action="store_true", help="the cached baseline of --sha (survey --baseline)")
    k.add_argument("--unmask", metavar="GAPKEY", help="WHAT-IF: re-translate the programs this whole-program refusal "
                   "(a `*` row; a unique substring will do) refuses, with its check off; report what it hides")  # fmt: skip
    k.add_argument("--label", default="before", help="the survey run prefix (DIR/<label>-*/survey.json)")
    k.add_argument("--all-programs", action="store_true", help="every surveyed program, not only the CICS ones "
                   "(then no corpora are read)")  # fmt: skip
    k.add_argument("--top", type=int, default=0, help="print only the first N gaps (default: all)")
    k.add_argument("--json", action="store_true")
    h = sub.add_parser("history", parents=[base], help="the whole counts per merged slice (blockers_history.jsonl)")
    h.add_argument("action", choices=["append", "show"])
    h.add_argument("--pr", type=int, help="append: the merged PR")
    h.add_argument("--note", help="append: a note (e.g. what the survey left out)")
    h.add_argument("--file", type=Path, help=f"the history file (default {HISTORY.relative_to(REPO)})")
    h.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if getattr(args, "no_census", False) and getattr(args, "census_corpora", None):  # #4598
        ap.error("--no-census and --census-corpora contradict each other: give one")
    cmds = {"usage": cmd_usage, "survey": cmd_survey, "compare": cmd_compare, "blockers": cmd_blockers,
            "history": cmd_history}  # fmt: skip
    return cmds[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
