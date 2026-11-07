"""`cics_census.py preflight` (#7964): counts-only checks before a blind-estate trial, exit non-zero on any finding.

    python tests/tools/cics_census.py preflight [--census-corpora DIR] [--root DIR] [--t0 SHA]

Five checks, each printing a count and no corpus, program or member name:
  1. programs vs copy members in the census (`cics_census.copy_member_reason`): no program at all is a finding;
  2. copybook names COPY'd by census programs whose 3-letter prefix is in neither the estate's own members nor the
     IBM product list (`gap_prevalence._COPYBOOK_FAMILIES`): any is a finding (a product the list lacks, #7899);
  3. every issue the gap map (`gap_prevalence.OWNERS`) points at is open; rows already accounted (a named source
     defect, a product copybook frontier) are skipped (#4767 / #4270 stayed named after they closed);
  4. the census dir holds exactly the census corpora (`cics_census.census_root_problems`, #6064);
  5. the T0 SHA is recorded (`--t0`, else `census-t0.json` in the scratch root) and resolves in git.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

import cics_census as cc  # noqa: E402

T0_FILE = "census-t0.json"
REPO_SLUG = "squid-protocol/gitgalaxy"
PREFIX_LEN = 3
_COPY = re.compile(r"\bCOPY\s+([A-Za-z0-9#@$_-]+)", re.I)
_OWNER = re.compile(r"^#(\d+)")

StateOf = Callable[[int], str]


def gh_state(number: int) -> str:
    """The state of issue `number` (`open` / `closed`), or `unknown` when gh fails (a finding, never a pass)."""
    res = subprocess.run(  # noqa: S603
        ["gh", "api", f"repos/{REPO_SLUG}/issues/{number}", "-q", ".state"],  # noqa: S607
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    return res.stdout.strip().lower() if res.returncode == 0 and res.stdout.strip() else "unknown"


def census_programs(census: Path) -> tuple[list[tuple[str, Path]], int]:
    """(corpus, file) of every census program, and the count of copy members (data-only members, #7901)."""
    from gitgalaxy.core.source_text import read_source

    progs: list[tuple[str, Path]] = []
    members = 0
    for name, corpus in cc.corpus_dirs([census]):
        for f in sorted(corpus.rglob("*")):
            if not (f.is_file() and f.suffix.lower() in cc.PROGRAM_EXTS and ".git" not in f.relative_to(corpus).parts):
                continue
            try:
                text = read_source(f).text
            except OSError:
                continue
            if cc.copy_member_reason(text) is None:
                progs.append((name, f))
            else:
                members += 1
    return progs, members


def unknown_prefixes(census: Path, progs: list[tuple[str, Path]]) -> int:
    """How many distinct copybook names the census programs COPY whose prefix is in neither the estate's members nor the
    IBM product list."""
    import gap_prevalence as gp
    from gitgalaxy.core.source_text import read_source

    product = tuple(p for prefixes, _ in gp._COPYBOOK_FAMILIES for p in prefixes)
    estate = {
        f.stem.upper()[:PREFIX_LEN]
        for _, corpus in cc.corpus_dirs([census])
        for f in corpus.rglob("*")
        if f.is_file() and ".git" not in f.relative_to(corpus).parts
    }
    unknown: set[tuple[str, str]] = set()
    for corpus, f in progs:
        try:
            code = cc.fixed_format_text(read_source(f).text)
        except OSError:
            continue
        for name in {m.upper() for m in _COPY.findall(code)}:
            if name[:PREFIX_LEN] not in estate and not name.startswith(product):
                unknown.add((corpus, name))
    return len(unknown)


def owner_issues() -> list[int]:
    """Issue numbers the gap map points at, skipping accounted rows (named source defect, product copybook frontier)."""
    import gap_prevalence as gp

    out = set()
    for _pat, owner in gp.OWNERS:
        m = _OWNER.match(owner)
        if m and "source defect" not in owner and "product copybook frontier" not in owner:
            out.add(int(m.group(1)))
    return sorted(out)


def recorded_t0(arg: str | None, root: Path) -> str | None:
    if arg:
        return arg
    f = root / T0_FILE
    if not f.is_file():
        return None
    try:
        return str(json.loads(f.read_text(encoding="utf-8")).get("sha") or "") or None
    except (OSError, ValueError, AttributeError):
        return None


def run_preflight(
    census: Path | None, root: Path, t0: str | None, state_of: StateOf = gh_state
) -> tuple[list[str], list[str]]:
    """(lines, findings): counts-only report lines and the failed checks."""
    lines: list[str] = []
    findings: list[str] = []

    def note(line: str, bad: bool = False) -> None:
        lines.append(("FAIL " if bad else "ok   ") + line)
        if bad:
            findings.append(line)

    if census is None or not census.is_dir():
        note("census dir: not given or not a directory", True)
    else:
        progs, members = census_programs(census)
        note(f"programs {len(progs)}, copy members {members}", not progs)
        unk = unknown_prefixes(census, progs)
        note(f"unknown copybook prefixes {unk}", unk > 0)
        problems = cc.census_root_problems(census)
        note(f"census dir: {len(problems)} problems" + (f" ({'; '.join(p.split(':')[0] for p in problems)})" if problems else ""),
             bool(problems))  # fmt: skip
    owners = owner_issues()
    states = [state_of(n) for n in owners]
    not_open = sum(s != "open" for s in states)
    note(f"gap-map owners {len(owners)}, not open {not_open}", not_open > 0)
    if t0 is None:
        note(f"T0 SHA: not recorded (--t0 or {T0_FILE} in the scratch root)", True)
    else:
        res = subprocess.run(  # noqa: S603
            ["git", "-C", str(cc.REPO), "rev-parse", "--verify", f"{t0}^{{commit}}"],  # noqa: S607
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        note(f"T0 SHA: {'recorded' if res.returncode == 0 else 'does not resolve in git'}", res.returncode != 0)
    return lines, findings


def cmd_preflight(args: argparse.Namespace, state_of: StateOf = gh_state) -> int:
    root = cc.scratch_root(args.root)
    arg = args.census_corpora or (Path(os.environ[cc.CENSUS_ENV]) if os.environ.get(cc.CENSUS_ENV) else root / "census")
    lines, findings = run_preflight(arg, root, recorded_t0(args.t0, root), state_of)
    print("census preflight")
    print("\n".join(lines))
    print(f"{len(findings)} finding(s)")
    return 1 if findings else 0
