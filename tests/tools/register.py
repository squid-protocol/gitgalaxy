#!/usr/bin/env python
"""The oracle-assumptions register: one file per entry, one generated combined page (#4788).

Source of truth: ``docs/language_status/register/``
  <ID>.md        one entry (C1.md, X31.md, Q1a.md ...): a front-matter block, then the entry's body
                 (the text after its ``### ID. title`` heading). Front-matter values are JSON strings.
                   id, family, status (summary table), title (the heading text), area, summary, reached
  _parts/*.md    the page's prose, verbatim (intro, pins, status key, section headings, Method tail ...)
  _layout.json   the order of the page: parts, the summary table, and where each family's entries go

Generated: ``docs/language_status/oracle_assumptions.md`` -- git-ignored, never committed (#5057: every PR that added
an entry re-rendered and committed it, and parallel PRs conflicted on it). generated-docs.yml renders it from main
after each merge and publishes it to the `generated` branch:
  https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md
A PR commits entry files only; its CI renders the page and shows the diff (tests/tools/generated_docs.py).

  register.py render           write the combined page into the working tree (local reading)
  register.py --check          exit 1 if the register is inconsistent (the page does not render)
  register.py next FAMILY      the next free number in a family (C, D, F, X, L, A, Q, J, M), looking at this
                               tree, origin/main and the remote branches; take it when the issue is filed
  register.py new ID           write a skeleton entry file for an ID
  register.py audit [--ci]     list entries that claim a match (ASSUMED / MATCHED / no status) with no IBM document
                               citation and no declared difference (#4702); --ci fails on one not in UNCITED_BASELINE
                               or on a baselined one that is now cited (the list only shrinks)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REG = REPO / "docs" / "language_status" / "register"
PAGE = REPO / "docs" / "language_status" / "oracle_assumptions.md"
KEYS = ("id", "family", "status", "title", "area", "summary", "reached")
ID_RE = re.compile(r"^([A-Z])(\d+)([a-z]?)$")
TABLE_HEAD = "| id | area | entry | status | reached by a proof? |\n|---|---|---|---|---|\n"


def id_key(i: str) -> tuple[str, int, str]:
    m = ID_RE.match(i)
    if not m:
        raise ValueError(f"bad register id {i!r}")
    return (m.group(1), int(m.group(2)), m.group(3))


def parse_entry(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: no front matter")
    head, _, body = text[4:].partition("\n---\n")
    meta: dict[str, str] = {}
    for line in head.splitlines():
        k, _, v = line.partition(": ")
        meta[k] = json.loads(v)
    missing = [k for k in KEYS if k not in meta]
    if missing:
        raise ValueError(f"{path.name}: front matter lacks {missing}")
    return meta, body.rstrip("\n")


def format_entry(meta: dict[str, str], body: str) -> str:
    fm = "".join(f"{k}: {json.dumps(meta[k], ensure_ascii=False)}\n" for k in KEYS)
    return f"---\n{fm}---\n{body.rstrip(chr(10))}\n"


def load_entries() -> list[tuple[dict[str, str], str]]:
    out = []
    for p in sorted(REG.glob("*.md")):
        meta, body = parse_entry(p)
        if p.stem != meta["id"]:
            raise ValueError(f"{p.name}: id {meta['id']!r} does not match the file name")
        if meta["family"] != id_key(meta["id"])[0]:
            raise ValueError(f"{p.name}: family {meta['family']!r} does not match the id")
        out.append((meta, body))
    return sorted(out, key=lambda e: id_key(e[0]["id"]))


def cell(s: str) -> str:
    return s.replace("\n", " ")


def render() -> str:
    layout = json.loads((REG / "_layout.json").read_text(encoding="utf-8"))
    order = [it["family"] for it in layout if "family" in it]
    entries = sorted(
        load_entries(),
        key=lambda e: (order.index(e[0]["family"]) if e[0]["family"] in order else 99, id_key(e[0]["id"])),
    )
    placed: set[str] = set()
    out: list[str] = []
    for item in layout:
        if "part" in item:
            out.append((REG / "_parts" / item["part"]).read_text(encoding="utf-8").rstrip("\n") + "\n")
        elif item.get("summary"):
            rows = "".join(
                f"| {m['id']} | {m['area']} | {m['summary']} | {m['status']} | {m['reached']} |\n"
                for m, _ in entries
                if m["summary"]
            )
            out.append(TABLE_HEAD + rows)
        if "family" in item:
            for m, body in entries:
                if m["family"] == item["family"]:
                    placed.add(m["id"])
                    out.append(f"### {m['id']}. {m['title']}\n{body}\n")
    stray = sorted({m["id"] for m, _ in entries} - placed, key=id_key)
    if stray:
        raise ValueError(f"entries in a family _layout.json does not place: {stray}")
    return "\n".join(out)


def check() -> list[str]:
    """The register's problems: every entry parses and _layout.json places it (#5057: there is no committed page to
    compare against any more)."""
    try:
        render()
    except (ValueError, OSError) as e:
        return [str(e)]
    return []


# Entries that name no IBM document and declare no difference (#4702, swept 2026-10-21). Each needs the IBM quote
# (document, section, page) or a declared difference; fixing one removes it here. A new entry never joins this list.
UNCITED_BASELINE = frozenset(
    "A1 C8 D3 I6 J1 L2 L3 M2 Q1 Q1a Q1b Q2 Q6 Q8 Q9 W2 W3 W4 W5 W8 X2 X3 X4 X7".split()  # noqa: SIM905
)
IBM_CITE = re.compile(
    r"SC\d\d-\d{4}|[SGA][CHA]\d\d-\d{4}|ibm\.com/docs|Language Reference|Programming Guide|Enterprise COBOL"
    r"|CICS TS|Application Programming|Db2 (for z/OS )?\d|DFSORT|IMS (V|\d)|DFSMS",
    re.I,
)
DECLARED_DIFF = re.compile(r"declared (oracle-vs-IBM )?difference|DIFFERS|Where they differ", re.I)


def audit() -> list[tuple[str, str, str]]:
    """(id, status, reached) of each entry that claims a match with neither an IBM citation nor a declared difference."""
    out = []
    for meta, body in load_entries():
        status = meta["status"]
        claims = "ASSUMED" in status or "MATCHED" in status or not status
        if claims and not IBM_CITE.search(body) and not DECLARED_DIFF.search(body):
            out.append((meta["id"], status, meta["reached"]))
    return out


def audit_problems(found: list[tuple[str, str, str]]) -> list[str]:
    ids = {i for i, _, _ in found}
    new = sorted(ids - UNCITED_BASELINE, key=id_key)
    fixed = sorted(UNCITED_BASELINE - ids, key=id_key)
    return [f"{i}: no IBM citation or declared difference (quote IBM, or declare the difference)" for i in new] + [
        f"{i}: now cited; remove it from UNCITED_BASELINE" for i in fixed
    ]


def _git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False)
    return r.stdout if r.returncode == 0 else ""


def taken_ids(local_only: bool = False) -> set[str]:
    ids = {p.stem for p in REG.glob("*.md")}
    if not local_only:
        refs = ["origin/main", *(_git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin").split())]
        for ref in dict.fromkeys(refs):
            for line in _git("ls-tree", "--name-only", f"{ref}:docs/language_status/register").splitlines():
                if line.endswith(".md") and ID_RE.match(line[:-3]):
                    ids.add(line[:-3])
    return ids


def next_id(family: str, local_only: bool = False) -> str:
    nums = [id_key(i)[1] for i in taken_ids(local_only) if id_key(i)[0] == family]
    return f"{family}{max(nums, default=0) + 1}"


def new_entry(i: str) -> Path:
    path = REG / f"{i}.md"
    if path.exists():
        raise SystemExit(f"{path} exists")
    meta = dict.fromkeys(KEYS, "") | {"id": i, "family": id_key(i)[0], "status": "ASSUMED", "reached": "no"}
    path.write_text(format_entry(meta, "- **What.** TODO"), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the register is inconsistent")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("render")
    n = sub.add_parser("next")
    n.add_argument("family")
    n.add_argument("--local", action="store_true", help="this tree only (no origin/main, no remote branches)")
    sub.add_parser("new").add_argument("id")
    au = sub.add_parser("audit")
    au.add_argument("--ci", action="store_true", help="fail on an uncited entry outside UNCITED_BASELINE")
    a = ap.parse_args(argv)
    if a.check:
        problems = check()
        for p in problems:
            print(f"register: {p}", file=sys.stderr)
        return 1 if problems else 0
    if a.cmd == "render":
        PAGE.write_text(render(), encoding="utf-8")
        print(f"wrote {PAGE.relative_to(REPO)}")
    elif a.cmd == "audit":
        found = audit()
        for i, status, reached in found:
            print(f"{i}\t{status or '(none)'}\treached: {reached}")
        print(f"{len(found)} entries without an IBM citation or declared difference", file=sys.stderr)
        problems = audit_problems(found) if a.ci else []
        for p in problems:
            print(f"register audit: {p}", file=sys.stderr)
        return 1 if problems else 0
    elif a.cmd == "next":
        print(next_id(a.family, a.local))
    elif a.cmd == "new":
        print(new_entry(a.id))
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
