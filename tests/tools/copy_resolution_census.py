"""Copybook-resolution census (#8111): the engine's COPY resolver against a plain file search, counts only.

    python tests/tools/copy_resolution_census.py [--root DIR ...]   # default: burned + non-candidate corpus_cobol

Every COPY / EXEC SQL INCLUDE member of every COBOL file in a repo is resolved twice: by the engine
(`GalaxyIR.copy_resolution`, from a `--db-only` scan) and by an independent search of the repo by member name (any
case, any extension or none, anywhere). Disagreements are counted in three classes and never named:
  miss      the engine draws no edge for the one member the repo holds;
  ambiguous the repo holds the member in several files and the engine draws no edge (its stated refusal, not counted
            as a disagreement: with no declared SYSLIB order nothing picks one);
  different the engine's edge is not a copybook-shaped file although the repo holds one under that name;
  neither   the engine and the search both find nothing (a member the repo does not hold);
  vendored  the importer, or every file holding the member, sits in a directory aperture drops as vendored (a bundled
            test suite): the engine never scans it, so it is no resolver disagreement and is not counted as one.

Corpus rule (#8111): only burned estates, authored fixtures and the non-candidate repos of corpus_cobol. `excluded_names`
is every blind candidate, census repo and non-burned ledger estate, matched by basename; `check_allowed` refuses one, so a
counted candidate can never be spent as a blind target.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

import cics_census as cc  # noqa: E402
import equivalence_env as ee  # noqa: E402

CLASSES = ("miss", "ambiguous", "different", "neither", "vendored")
COBOL_EXTS = cc.PROGRAM_EXTS | {".pco", ".cpy", ".copy", ".cpb"}
# a file can be a COPY member when it has no extension or one a COBOL shop uses for members (a .json or .c of the
# same name is not one)
MEMBER_EXTS = COBOL_EXTS | {"", ".inc", ".lib", ".dcl", ".cobcpy", ".cobcopy"}
MAX_BYTES = 2_000_000
PLAIN_EXTS = {".cpy", ".copy", ".cbl", ".cob", ".cobol", ".cpb"}
_NAME = "[A-Za-z0-9#@$_-]+"
# `COPY member [OF|IN library]` names the library that holds the member (#8111); EXEC SQL INCLUDE has no qualifier
_COPY = re.compile(
    r"\b(?:COPY|EXEC\s+SQL\s+INCLUDE)\s+['\"]?(" + _NAME + r")(?:['\"]?\s+(?:OF|IN)\s+['\"]?(" + _NAME + "))?", re.I
)
_COBOLISH = re.compile(r"\b(?:PROGRAM-ID|DIVISION|SECTION|PIC(?:TURE)?)\b", re.I)

# (importer file) -> {member: engine-resolved file names}, and the (importer, member) gaps
EngineSide = Callable[[Path], tuple[dict[str, dict[str, set[str]]], set[tuple[str, str]]]]


def excluded_names() -> set[str]:
    """Basenames (lower case) a census must never open: blind candidates, census repos, non-burned ledger estates."""
    import trial

    burned = ee.burned_names() | {cc.CRUCIBLE_CORPUS}
    names = {n.split("/")[-1] for n in ee.candidate_names()} | cc.census_names()
    names |= {str(e["id"]).lower() for e in trial.load()["estates"]}
    return names - burned


def check_allowed(repo: Path, excluded: set[str] | None = None) -> None:
    if repo.name.lower() in (excluded_names() if excluded is None else excluded):
        raise SystemExit("refused: a candidate, census or trialled repo is not measured here (#8111 corpus rule)")


def _copies(text: str) -> set[tuple[str, str | None]]:
    """{(MEMBER, LIBRARY or None)} of every COPY / EXEC SQL INCLUDE in the code lines of `text`."""
    code = []
    for line in text.splitlines():
        if line.lstrip().startswith("*>") or (len(line) > 6 and line[6] in "*/" and not line[:6].strip().isalpha()):
            continue
        code.append(line)
    return {(m.upper(), lib.upper() or None) for m, lib in _COPY.findall("\n".join(code))}


def _members(text: str) -> set[str]:
    return {m for m, _lib in _copies(text)}


def _in_library(path: str, library: str | None) -> bool:
    """`path` sits under a directory named `library` (any case), or no library is named."""
    return library is None or library in {part.upper() for part in Path(path).parent.parts}


def importers(repo: Path) -> dict[str, str]:
    """{repo-relative posix path: text} of every COBOL-shaped file that COPYs something."""
    from gitgalaxy.core.source_text import read_source

    out: dict[str, str] = {}
    for f in sorted(repo.rglob("*")):
        rel = f.relative_to(repo)
        if ".git" in rel.parts or not f.is_file():
            continue
        if f.suffix.lower() not in COBOL_EXTS and f.suffix:
            continue
        try:
            if f.stat().st_size > MAX_BYTES:
                continue
            text = read_source(f).text
        except OSError:
            continue
        if f.suffix == "" and not _COBOLISH.search(text):
            continue
        out[rel.as_posix()] = text
    return out


def member_index(repo: Path) -> dict[str, set[str]]:
    """{MEMBER: repo-relative paths} where the file's stem or whole name is the member, any case, any extension."""
    idx: dict[str, set[str]] = {}
    for f in repo.rglob("*"):
        rel = f.relative_to(repo)
        if ".git" in rel.parts or not f.is_file():
            continue
        if f.suffix.lower() not in MEMBER_EXTS:
            continue
        for key in {f.stem.upper(), f.name.upper()}:
            idx.setdefault(key, set()).add(rel.as_posix())
    return idx


def engine_side(repo: Path) -> tuple[dict[str, dict[str, set[str]]], set[tuple[str, str]]]:
    """Scan `repo` and read the resolver's edges (resolved files per importer) and gaps."""
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

    with tempfile.TemporaryDirectory(prefix="copycensus-") as tmp:
        ir = load_galaxy_ir(scan_to_db(repo, Path(tmp)))
        edges: dict[str, dict[str, set[str]]] = {}
        gaps: set[tuple[str, str]] = set()
        for f in ir.files:
            res = ir.copy_resolution(f)
            gaps |= {(i, m) for i, m in res["gaps"]}
            if f in res["edges"]:
                edges[f] = {d: set() for d in res["edges"][f]}
                # a BMS symbolic map (`map.bms#MAPSET`) is resolved apart from the edges: copy_resolution leaves it out
                for sym in ir.files[f].symbolic_copies:
                    bms, _, mapset = sym.file_path.partition("#")
                    edges[f][bms] = set()
                    edges[f][mapset] = set()
    return edges, gaps


def cause_of(member: str, holds: set[str], text: str) -> str:
    """Why a disagreeing member is hard, from the path shape of the file the repo holds (never a name): `qualified`
    / `absent` (nothing held), `dot-dir`, `extensionless`, `other-ext`, `lower-case`, or `plain` (a normal place)."""
    if not holds:
        return "qualified" if re.search(r"\b" + re.escape(member) + r"['\"]?\s+(?:OF|IN)\s", text, re.I) else "absent"
    p = Path(sorted(holds)[0])
    if any(part.startswith(".") for part in p.parent.parts):
        return "dot-dir"
    if not p.suffix:
        return "extensionless"
    if p.suffix.lower() not in PLAIN_EXTS:
        return "other-ext"
    return "lower-case" if p.stem != p.stem.upper() else "plain"


def tally(n: Counter[str], cls: str, cause: str) -> None:
    n[cls] += 1
    n[f"{cls}:{cause}"] += 1


def census_repo(repo: Path, engine: EngineSide = engine_side) -> Counter[str]:
    """Counts for one repo: `members` (COPY occurrences resolved), `agree`, and each of CLASSES."""
    from gitgalaxy.core.aperture import VendorDirectoryDetector
    from gitgalaxy.core.source_text import read_source

    edges, gaps = engine(repo)
    idx = member_index(repo)
    texts = importers(repo)
    shaped: dict[str, bool] = {}
    vendor = VendorDirectoryDetector(repo)

    def vendored(rel: str) -> bool:
        parts = rel.split("/")[:-1]
        return any(vendor.is_vendored("/".join(parts[: i + 1])) for i in range(len(parts)))

    def copy_shaped(rel: str) -> bool:
        if rel not in shaped:
            try:
                shaped[rel] = cc.copy_member_reason(read_source(repo / rel).text) is not None
            except OSError:
                shaped[rel] = False
        return shaped[rel]

    n: Counter[str] = Counter()
    for imp, text in texts.items():
        resolved = set(edges.get(imp, {}))
        for member, library in _copies(text):
            n["members"] += 1
            holds = {p for p in idx.get(member, set()) - {imp} if _in_library(p, library)}
            if holds and (vendored(imp) or all(vendored(p) for p in holds)):
                tally(n, "vendored", "importer" if vendored(imp) else "member")
                continue
            hit = {
                p
                for p in resolved
                if (Path(p).stem.upper() == member or Path(p).name.upper() == member) and _in_library(p, library)
            }
            if (imp, member) in gaps:
                hit = set()
            if not holds and not hit:
                tally(n, "neither", cause_of(member, holds, text))
            elif holds and not hit:
                tally(n, "ambiguous" if len(holds) > 1 else "miss", cause_of(member, holds, text))
            elif holds and not any(copy_shaped(p) for p in hit) and any(copy_shaped(p) for p in holds):
                tally(n, "different", cause_of(member, holds, text))
            else:
                n["agree"] += 1
    return n


def default_roots() -> list[Path]:
    import os

    out = []
    if os.environ.get("GITGALAXY_MAINFRAME_CORPORA"):
        out.append(Path(os.environ["GITGALAXY_MAINFRAME_CORPORA"]))
    out.append(Path("/nvme-data/gitgalaxy-data/corpus_cobol"))
    return out


def run_roots(roots: list[Path], engine: EngineSide = engine_side) -> tuple[Counter[str], int]:
    """(summed counts, repos measured) over every non-excluded repo under the roots."""
    excluded = excluded_names()
    total: Counter[str] = Counter()
    repos = 0
    for _name, d in cc.corpus_dirs(roots):
        if d.name.lower() in excluded:
            continue
        total += census_repo(d, engine)
        repos += 1
    return total, repos


def run_groups(roots: list[Path], engine: EngineSide = engine_side) -> dict[str, Counter[str]]:
    """Counts per corpus group (`burned`, `non-candidate`) over every non-excluded repo under the roots."""
    excluded = excluded_names()
    burned = cc.burned_names()
    groups: dict[str, Counter[str]] = {}
    for _name, d in cc.corpus_dirs(roots):
        if d.name.lower() in excluded:
            continue
        g = "burned" if d.name.lower() in burned else "non-candidate"
        groups.setdefault(g, Counter())
        groups[g] += census_repo(d, engine)
    return groups


def disagreements(counts: Counter[str]) -> int:
    """The gate's number: the engine misses or mispicks a member the repo holds (`neither` and `ambiguous` are not)."""
    return counts["miss"] + counts["different"]


def render(counts: Counter[str], repos: int) -> str:
    cls = ", ".join(f"{c} {counts[c]}" for c in CLASSES)
    return f"repos {repos}, members {counts['members']}, agree {counts['agree']}, {cls}"


def render_causes(counts: Counter[str]) -> str:
    """One `class: cause N, ...` line per class that has members (counts only)."""
    lines = []
    for c in CLASSES:
        causes = sorted((k.split(":", 1)[1], v) for k, v in counts.items() if k.startswith(c + ":"))
        if causes:
            lines.append(f"  {c} {counts[c]}: " + ", ".join(f"{k} {v}" for k, v in causes))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", action="append", type=Path, help="a directory of repos (default: burned + corpus_cobol)")
    ap.add_argument("--by-group", action="store_true", help="also print each class by cause, per corpus group")
    args = ap.parse_args(argv)
    roots = args.root or default_roots()
    if args.by_group:
        counts = Counter()
        for g, c in sorted(run_groups(roots).items()):
            counts += c
            print(f"{g}: {render(c, 0).split(', ', 1)[1]}")
            print(render_causes(c))
        return 1 if disagreements(counts) else 0
    counts, repos = run_roots(roots)
    print(render(counts, repos))
    return 1 if disagreements(counts) else 0


if __name__ == "__main__":
    sys.exit(main())
