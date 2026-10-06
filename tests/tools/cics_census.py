#!/usr/bin/env python3
"""The census of a #4270 CICS command slice: which programs use a command and its options, and whether the det
translator takes them whole, before and after the change -- split burned / non-burned.

    python tests/tools/cics_census.py usage ASSIGN ["SEND TEXT" ...] [--json]
    python tests/tools/cics_census.py survey --out DIR --label before [--verb ASSIGN ...] [--compile]
    python tests/tools/cics_census.py compare DIR --verb ASSIGN [...]
    python tests/tools/cics_census.py blockers DIR [--label before] [--all-programs] [--json]

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

Burned / non-burned comes from ONE place: tests/tools/estate4_draw.py. A corpus is BURNED when its name is one of
the burned estates (BURNED_NAMES: CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication -- det ports exist); every
other corpus is non-burned. The census repos (estate4_draw.INELIGIBLE_LIST, docs census/INELIGIBLE_FOR_BLIND_ESTATE.md)
are not in .mainframe_corpora: clone them into a scratch directory and pass it as --census-corpora DIR or
$CICS_CENSUS_CORPORA. Blind-estate rule: those repos are read only through translator output and these option
counts; nothing from them is committed. A census-root corpus that is NOT on the census list is warned about: reading
an eligible blind-estate candidate through the translator burns it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
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
            use = ProgramUse(name, str(prog.relative_to(corpus)), is_burned(name, burned),
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
    census = census_root(args.census_corpora, required=not args.no_census)
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
    import pr_gates

    mainframe = mainframe_root(args.corpora)
    census = census_root(args.census_corpora, required=not args.no_census)
    uses = usage([mainframe, *([census] if census else [])], args.verb) if args.verb else None
    env = pr_gates.environment(e2e=True)
    args.out.mkdir(parents=True, exist_ok=True)
    rc = 0
    for suffix, root, names in survey_runs(mainframe, census, uses, args.corpus):
        work = args.out / f"{args.label}-{suffix}"
        argv = [sys.executable, str(TOOLS / "det_survey.py"), "--work", str(work), "--jobs", str(args.jobs)]
        argv += [] if args.compile else ["--no-compile"]
        for n in names:
            argv += ["--corpus", n]
        log = args.out / f"{args.label}-{suffix}.log"
        print(f"{args.label}-{suffix}: {len(names)} corpora from {root} -> {work} (log {log})", flush=True)
        with log.open("wb") as fh:
            res = subprocess.run(argv, cwd=REPO, env=dict(env, GITGALAXY_MAINFRAME_CORPORA=str(root)),  # noqa: S603
                                 stdout=fh, stderr=subprocess.STDOUT, check=False)  # fmt: skip
        if res.returncode or not (work / "survey.json").is_file():
            print(f"  det_survey exited {res.returncode} (survey.json written: {(work / 'survey.json').is_file()}): "
                  f"see {log}", file=sys.stderr)  # fmt: skip
            rc = 1
    return rc


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
    before, after = load_surveys(args.dir, args.before), load_surveys(args.dir, args.after)
    if not before or not after:
        raise SystemExit(f"no {args.before}-*/survey.json or {args.after}-*/survey.json under {args.dir} "
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
    if re.fullmatch(r"[A-Z][\w-]*: no such item", why):  # a map field, DIBSTAT, ...: one class whatever the name
        return "<name>: no such item"
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
                        out.add((name, str(prog.relative_to(corpus))))
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


def cmd_blockers(args: argparse.Namespace) -> int:
    rows = load_surveys(args.dir, args.label)
    if not rows:
        raise SystemExit(f"no {args.label}-*/survey.json under {args.dir} (run `cics_census.py survey --out "
                         f"{args.dir} --label {args.label}` first)")  # fmt: skip
    only = None if args.all_programs else cics_programs(roots_from(args))
    res = blockers(rows, only)
    res["scope"] = "every surveyed program" if only is None else "programs with an EXEC CICS command"
    if only is not None:
        res["cics_programs_not_surveyed"] = len(only - set(rows))
    if args.json:
        print(json.dumps(res, indent=1))
        return 0
    print(f"# blockers in {args.dir}/{args.label}-*: {res['scope']}")
    print(f"translated whole: {res['whole']} / {res['programs']} (non-burned {res['whole_non_burned']} / "
          f"{res['non_burned']}); refused whole (no statements translated): {res['refused']}")  # fmt: skip
    if res.get("cics_programs_not_surveyed"):
        print(f"CICS programs with no survey row: {res['cics_programs_not_surveyed']} (a corpus left out of the run?)")
    print("distinct gap classes per program: " + ", ".join(f"{n}: {c}" for n, c in res["histogram"].items()))
    print(f"\n{'only gap (B/NB)':>16} {'one away (B/NB)':>16} {'touched':>8}  gap  (* = refuses the whole program: "
          f"its count is an upper bound)")  # fmt: skip
    for g in res["gaps"][: args.top or None]:
        print(f"{g['only']:>6} ({g['only_burned']:>2}/{g['only_non_burned']:>2}) {g['one_away']:>6} "
              f"({g['one_away_burned']:>2}/{g['one_away_non_burned']:>2}) {g['touched']:>8}  "
              f"{'*' if g['refuses_program'] else ' '}{g['gap'][:110]}")  # fmt: skip
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpora", type=Path, help="the burned / local corpora root (default: "
                        "$GITGALAXY_MAINFRAME_CORPORA, else <main checkout>/.mainframe_corpora)")  # fmt: skip
    common.add_argument("--census-corpora", type=Path, help=f"the non-burned census clones (default: ${CENSUS_ENV})")
    common.add_argument("--no-census", action="store_true", help="count without the census corpora")
    common.add_argument("--all-options", action="store_true", help="keep RESP / RESP2 / NOHANDLE among the options")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("usage", parents=[common], help="option names per program and totals")
    u.add_argument("verbs", nargs="+", metavar="VERB", help='e.g. ASSIGN, START, "SEND TEXT" (or SEND-TEXT)')
    u.add_argument("--json", action="store_true")
    u.add_argument("--pli", action="store_true", help="also count PL/I programs (flagged; the det translator takes "
                   "COBOL only)")  # fmt: skip
    s = sub.add_parser("survey", parents=[common], help="det_survey.py over the burned and non-burned corpora")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--label", default="before", help="before | after (the run directory prefix)")
    s.add_argument("--verb", nargs="+", help="only the corpora where a program uses one of these")
    s.add_argument("--corpus", nargs="+", help="only these corpus names")
    s.add_argument("--compile", action="store_true", help="also compile each port (det_survey without --no-compile)")
    s.add_argument("--jobs", type=int, default=4)
    c = sub.add_parser("compare", parents=[common], help="before / after table of the programs using the verb")
    c.add_argument("dir", type=Path)
    c.add_argument("--verb", nargs="+", required=True)
    c.add_argument("--before", default="before")
    c.add_argument("--after", default="after")
    c.add_argument("--json", action="store_true")
    k = sub.add_parser("blockers", parents=[common], help="rank every gap by the programs fixing it makes whole")
    k.add_argument("dir", type=Path)
    k.add_argument("--label", default="before", help="the survey run prefix (DIR/<label>-*/survey.json)")
    k.add_argument("--all-programs", action="store_true", help="every surveyed program, not only the CICS ones "
                   "(then no corpora are read)")  # fmt: skip
    k.add_argument("--top", type=int, default=0, help="print only the first N gaps (default: all)")
    k.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    cmds = {"usage": cmd_usage, "survey": cmd_survey, "compare": cmd_compare, "blockers": cmd_blockers}
    return cmds[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
