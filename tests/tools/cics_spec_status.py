#!/usr/bin/env python3
"""#4270: the CICS command spec's status page, docs/language_status/cics_spec_status.md (generated; do not edit).

    python tests/tools/cics_spec_status.py render [--check]       # write the page (or fail when it is stale)
    python tests/tools/cics_spec_status.py refresh [--census] [--crucible DIR] [--corpora DIR] [--census-corpora DIR]

Per CICS command the spec (gitgalaxy/standards/cics) has an entry for:
  - its entry: full (status "modelled"), engine-only, or name-only (a refusal with its reason);
  - the det translator: does det/cics.py's OPTIONS model it (honoured / refused-by-name option counts);
  - the stub runtime (tests/tools/equivalence_cics.py): a probe of translate_command -- refused whole, or taken;
  - the X-register entries it names (its own, its refusals'), checked against oracle_assumptions.md's table;
  - census use: the programs using it, burned / non-burned (counts only);
  - the cics-crucible cases whose programs issue it;
plus the progress of the 8 spec PRs (cics_command_spec.md section 7).

The spec, the translator and the stub are read live. Census use and crucible coverage need corpora no CI job has, so
`refresh` measures them into docs/language_status/cics_spec_status.json (counts and case ids only; the census
programs are read as `cics_census.py usage` reads them, through the translator's own EXEC parser, and nothing but
counts is kept) and `render` reads that file. #4789: the page is derived output, like the evidence report (#4703):
the evidence-refresh bot runs `render` on main and commits it; a PR does NOT commit it (parallel slices conflicted on
it). A PR that changes the spec, translator or stub commits nothing here; a slice commits the `refresh`ed
cics_spec_status.json. Per-PR CI only says whether the page would change (smoke-test.yml, advisory);
test_cics_spec_status.py's currency test runs only outside it (EVIDENCE_REPORT_ADVISORY unset). Never open docs/language_status/estate4_candidates.json: the census corpora are the ineligible list only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

PAGE = REPO / "docs" / "language_status" / "cics_spec_status.md"
DATA = REPO / "docs" / "language_status" / "cics_spec_status.json"
SPEC_DOC = REPO / "docs" / "language_status" / "cics_command_spec.md"
REGISTER = REPO / "docs" / "language_status" / "oracle_assumptions.md"
FORMAT = "cics-spec-status/1"

# The spec PRs merged so far (cics_command_spec.md section 7): each spec PR adds its own row here.
SPEC_PRS_DONE = {"1": "#4589", "2": "#4591", "3": "#4593", "4": "#4608"}


# ---- live reads -------------------------------------------------------------------------------------------------
def spec() -> Any:
    from gitgalaxy.standards.cics.commands import COMMANDS

    return COMMANDS


def entry_kind(c: Any) -> str:
    return {"modelled": "full", "engine-only": "engine-only", "refused": "name-only"}[c.status]


def registers(c: Any) -> list[str]:
    regs = {c.register, *(r.register for r in c.refused.values()), *(r.register for r in c.runtime_refusals)}
    if c.default_refusal is not None:
        regs.add(c.default_refusal.register)
    return sorted((r for r in regs if r), key=lambda r: int(r[1:]))


def register_rows(path: Path = REGISTER) -> set[str]:
    """The X-numbers oracle_assumptions.md's summary table has a row for."""
    return set(re.findall(r"^\| (X\d+) \|", path.read_text(encoding="utf-8"), re.M))


def translator_options() -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_java.det.cics import OPTIONS

    return OPTIONS


def stub_takes(key: str, c: Any) -> bool:
    """Does the stub translator take the command (rather than refuse it whole)? A probe of translate_command with
    the key's words, then with each honoured option in turn: taken if any form is translated or refused for a
    reason other than the whole command."""
    import equivalence_cics as ec

    whole = re.compile(rf"^EXEC CICS {re.escape(key.split()[0])}\b.* not modelled(?: \(|$)")

    def taken(body: str) -> bool:
        try:
            ec.translate_command(body, [], False)
        except ec.Unsupported as e:
            return not whole.match(str(e))
        except Exception:  # a probe: any other failure is "not this form"
            return False
        return True

    tries = [key] + [f"{key} {o}(X)" for o in sorted(c.options) if o not in key.split()]
    return any(taken(body) for body in tries)


def spec_prs(path: Path = SPEC_DOC) -> list[dict[str, str]]:
    """The rows of cics_command_spec.md section 7's PR table: PR, content (its first clause), consumers."""
    text = path.read_text(encoding="utf-8")
    sec = text.split("## 7.", 1)[1].split("\n## ", 1)[0]
    rows = []
    for ln in sec.splitlines():
        m = re.match(r"^\| \**(\d+[ab]?)\** \| (.*?) \| (.*?) \| (.*?) \|$", ln)
        if m:
            content = re.sub(r"\*\*|`", "", m.group(2))
            content = re.split(r"; |\. ", content)[0]
            rows.append({"pr": m.group(1), "content": content[:150], "consumers": m.group(3)})
    return rows


# ---- refresh: what needs corpora --------------------------------------------------------------------------------
def spec_key(body: str) -> str:
    """The spec key of one EXEC CICS command as the det translator keys it (parse_exec + command_key, then the
    name-only entry whole_refusal finds), or `(unlisted) VERB`."""
    from gitgalaxy.standards.cics.commands import COMMANDS, whole_refusal
    from gitgalaxy.tools.cobol_to_java.det.cics import command_key, parse_exec

    try:
        words, opts = parse_exec(body)
    except Exception:  # the translator's own parse error: counted, never shown
        return "(unparsed)"
    key = command_key(words, opts)
    c = COMMANDS.get(key)
    if c is not None and c.status == "modelled":
        return key
    verb = " ".join(words)
    known = whole_refusal(key, verb, next(iter(opts), None))
    if known is not None:
        return known.key
    return key if key in COMMANDS else f"(unlisted) {verb}"


_EXEC = re.compile(r"\bEXEC\s+CICS\s+(.*?)\bEND-EXEC\b", re.S)


def program_keys(text: str) -> set[str]:
    import cics_census as cc

    return {spec_key(m.group(1)) for m in _EXEC.finditer(cc.fixed_format_text(text))}


def census_use(roots: list[Path]) -> dict[str, dict[str, int]]:
    """spec key -> {programs, burned, non_burned}: counts only."""
    import cics_census as cc

    from gitgalaxy.core.source_text import read_source

    burned = cc.burned_names()
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"programs": 0, "burned": 0, "non_burned": 0})
    for name, corpus in cc.corpus_dirs(roots):
        b = cc.is_burned(name, burned)
        for prog in sorted(corpus.rglob("*")):
            if (
                not prog.is_file()
                or prog.suffix.lower() not in cc.PROGRAM_EXTS
                or ".git" in prog.relative_to(corpus).parts
            ):
                continue
            try:
                keys = program_keys(read_source(prog).text)
            except OSError:
                continue
            for k in keys:
                row = out[k]
                row["programs"] += 1
                row["burned" if b else "non_burned"] += 1
    return dict(sorted(out.items()))


def crucible_cases(crucible: Path) -> dict[str, list[str]]:
    """spec key -> the cics-crucible case ids whose programs issue it."""
    from gitgalaxy.core.source_text import read_source

    out: dict[str, set[str]] = defaultdict(set)
    for prog in sorted(crucible.glob("cases/*/*/src/*")):
        if prog.suffix.lower() in (".cbl", ".cob", ".cobol"):
            for k in program_keys(read_source(prog).text):
                out[k].add(prog.parents[1].name)
    return {k: sorted(v) for k, v in sorted(out.items())}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603,S607
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_data(path: Path = DATA) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"format": FORMAT, "census": {}, "census_measured": None, "crucible": {}, "crucible_measured": None}


def cmd_refresh(args: argparse.Namespace) -> int:
    data = load_data()
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    if args.census:
        import cics_census as cc

        roots = [cc.mainframe_root(args.corpora)]
        census = cc.census_root(args.census_corpora, required=True)
        data["census"] = census_use(roots + ([census] if census else []))
        data["census_measured"] = {"commit": _git("rev-parse", "--short=9", "HEAD"), "date": today,
                                   "corpora": len(cc.corpus_dirs(roots + ([census] if census else [])))}  # fmt: skip
    if args.crucible:
        pin = re.search(r'^PINNED_REF = "(.*)"', (REPO / "tests" / "_cics_crucible_pin.py").read_text(), re.M)
        data["crucible"] = crucible_cases(args.crucible)
        ref = subprocess.run(["git", "describe", "--tags", "--always"], cwd=args.crucible, capture_output=True,  # noqa: S607
                             text=True, check=False).stdout.strip()  # fmt: skip
        if pin and ref != pin.group(1):
            print(f"warning: the crucible at {args.crucible} is {ref}, the pin is {pin.group(1)}", file=sys.stderr)
        data["crucible_measured"] = {"ref": ref, "date": today}
    if not (args.census or args.crucible):
        raise SystemExit("refresh what? --census and / or --crucible DIR")
    DATA.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {DATA.relative_to(REPO)}; now: python tests/tools/cics_spec_status.py render")
    return 0


# ---- render -----------------------------------------------------------------------------------------------------
def _use(data: dict[str, Any], key: str) -> str:
    u = data.get("census", {}).get(key)
    return f"{u['programs']} ({u['burned']} / {u['non_burned']})" if u else "0"


def rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    cmds, opts = spec(), translator_options()
    known = register_rows()
    out = []
    for key, c in cmds.items():
        kind = entry_kind(c)
        regs = registers(c)
        out.append({
            "key": key,
            "entry": kind,
            "translator": (f"yes ({len(c.options)} options" + (f", {len(c.refused)} refused by name)" if c.refused
                           else ")")) if key in opts else "refused whole",
            "stub": ("yes" if stub_takes(key, c) else "refused whole") if kind != "name-only" else "refused whole",
            "register": ", ".join(r if r in known else f"{r} (no row!)" for r in regs) or "—",
            "facts": ", ".join(f.name for f in c.facts),
            "census": data.get("census", {}).get(key),
            "crucible": data.get("crucible", {}).get(key, []),
        })  # fmt: skip
    return out


def render(data: dict[str, Any] | None = None) -> str:
    data = load_data() if data is None else data
    rs = rows(data)
    by = defaultdict(list)
    for r in rs:
        by[r["entry"]].append(r)
    cm, xm = data.get("census_measured") or {}, data.get("crucible_measured") or {}
    out = [
        "# CICS command spec: status",
        "",
        (
            "<!-- generated by tests/tools/cics_spec_status.py render; do not edit (test_cics_spec_status.py fails "
            "when it is stale) -->"
        ),
        "",
        (
            "Per command the spec (`gitgalaxy/standards/cics`, design: [cics_command_spec.md](cics_command_spec.md)) has "
            "an entry for: the entry's kind, whether the det translator and the stub runtime take it, its X-register "
            "entries ([oracle_assumptions.md](oracle_assumptions.md)), its census use and the cics-crucible cases that "
            "issue it. The spec, translator and stub are read live; census use and crucible cases are measured by "
            "`cics_spec_status.py refresh` into `cics_spec_status.json`"
            + (
                f" (census: {cm.get('corpora')} corpora at {cm.get('commit')}, {cm.get('date')}"
                if cm
                else " (census: not measured"
            )
            + (f"; crucible: {xm.get('ref')}, {xm.get('date')})." if xm else "; crucible: not measured).")
        ),
        "",
        (
            "Census use is `programs (burned / non-burned)`, counts only. A spec key is the det translator's: "
            "`parse_exec` + `command_key`, then the name-only entry `whole_refusal` finds."
        ),
        "",
        (
            f"**{len(rs)} entries:** {len(by['full'])} full, {len(by['engine-only'])} engine-only, "
            f"{len(by['name-only'])} name-only."
        ),
        "",
        "## Spec PRs (cics_command_spec.md section 7)",
        "",
        "| PR | status | content | consumers changed |",
        "|---|---|---|---|",
    ]
    for p in spec_prs():
        done = SPEC_PRS_DONE.get(p["pr"])
        out.append(f"| {p['pr']} | {'done (' + done + ')' if done else 'open'} | {p['content']} | {p['consumers']} |")
    out += ["", "## Full and engine-only entries", "",
            "| command | entry | det translator | stub | X-register | stated facts | census use | crucible cases |",
            "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in by["full"] + by["engine-only"]:
        cases = ", ".join(r["crucible"]) or "—"
        out.append(f"| {r['key']} | {r['entry']} | {r['translator']} | {r['stub']} | {r['register']} | "
                   f"{r['facts'] or '—'} | {_use(data, r['key'])} | {cases} |")  # fmt: skip
    used = [r for r in by["name-only"] if r["census"]]
    used.sort(key=lambda r: (-r["census"]["programs"], -r["census"]["non_burned"], r["key"]))
    out += ["", "## Name-only entries a census program uses", "",
            ("Refused whole by the translator and the stub, with the entry's reason. Ranked by programs; a full entry "
             "is promoted from one of these when `cics_census.py blockers` says it would make programs whole."), "",
            "| command | census use | crucible cases |", "|---|---|---|"]  # fmt: skip
    for r in used:
        out.append(f"| {r['key']} | {_use(data, r['key'])} | {', '.join(r['crucible']) or '—'} |")
    out.append(f"\n{len(by['name-only']) - len(used)} more name-only entries no census program uses.")
    extra = {k: v for k, v in data.get("census", {}).items() if k.startswith("(")}
    if extra:
        out += ["", "## Commands the translator keys to no spec entry", "",
                ("As `parse_exec` reads them: a bare option first (`ASKTIME NOHANDLE`) is read as a verb word, an SPI "
                 "command (`INQUIRE`, `SET`) has no entry; `(unparsed)`: the parser stopped."), "",
                "| command | census use |", "|---|---|"]  # fmt: skip
        for k, v in sorted(extra.items(), key=lambda kv: (-kv[1]["programs"], kv[0])):
            out.append(f"| {k} | {v['programs']} ({v['burned']} / {v['non_burned']}) |")
    return "\n".join(out) + "\n"


def cmd_render(args: argparse.Namespace) -> int:
    text = render()
    if args.check:
        if not PAGE.is_file() or PAGE.read_text(encoding="utf-8") != text:
            print(f"stale: {PAGE.relative_to(REPO)} -- run python tests/tools/cics_spec_status.py render",
                  file=sys.stderr)  # fmt: skip
            return 1
        print(f"{PAGE.relative_to(REPO)} is current")
        return 0
    PAGE.write_text(text, encoding="utf-8")
    print(f"wrote {PAGE.relative_to(REPO)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="write the page from the spec and cics_spec_status.json")
    r.add_argument("--check", action="store_true", help="fail (exit 1) when the committed page is stale")
    f = sub.add_parser("refresh", help="measure census use / crucible cases into cics_spec_status.json")
    f.add_argument("--census", action="store_true", help="count census use (needs the corpora and census clones)")
    f.add_argument("--crucible", type=Path, help="a cics-crucible checkout AT THE PIN (a private clone)")
    f.add_argument("--corpora", type=Path)
    f.add_argument("--census-corpora", type=Path)
    args = ap.parse_args(argv)
    return {"render": cmd_render, "refresh": cmd_refresh}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
