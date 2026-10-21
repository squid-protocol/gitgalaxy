#!/usr/bin/env python
"""The cobolrt rule catalogue (#4711): every semantic rule of the det-port Java runtime, by a stable ID.

Source of truth: ``docs/language_status/cobolrt_rules.json``
  documents   the manuals the rules cite, by key (IBM's; for COBDATFT the estate's own routine)
  options     what a rule may depend on, by kind: a compile option (one the #4704 resolver knows,
              gitgalaxy/core/compiler_options.py), a source clause, a dialect switch or a deployment fact
  families    runtime files (cobolrt/...) under one rule-ID prefix; `plumbing` names the methods that carry no rule of
              their own (byte helpers, item constructors, accessors); `done` once the family is catalogued (a family
              not done yet is listed, not checked, and may carry no marker)
  rules       id (RT-<PREFIX>-<NAME>, never reused), title, family, methods ("name", or "file:name" where the family's
              files share a name), site (optional: the declaration the marker stands on, "name", "file:name" or
              "...@N" for the Nth declaration of the name; default the first method), ibm ({doc, section}, or null with
              `ibm_note` for a rule that is not MATCHED), options, features (optional, only when non-empty: the
              feature-inventory keys "category: key" the rule governs, joined by the support matrix, #5565), register (oracle-assumptions entries,
              docs/language_status/register/), status (MATCHED / DIFFERS / REFUSED / ASSUMED, against IBM),
              calibration ("uncalibrated", or "z/OS-measured" with `evidence` and `calibrated_under`, the LE / Db2 / CICS
              options the measurement held under, runtime_options.calibration_problems; #4702)

Each rule's code site carries ``// [rule <ID>]`` on the line above its declaration. check() is two-way: a marker with
no entry, an entry with no marker, a marker standing before a method that is not the rule's, a method of a catalogued
family that no rule and no plumbing list names, a named method that does not exist, a register entry a family's code
cites that none of its rules carries, and a runtime file no family lists all fail
(tests/cobol_mainframe/test_cobolrt_rules.py). A marker is a comment: det_port.java_code -- what `det_port.py check`
compares a runtime class by -- does not see it, so citing an ID moves no port.

Generated: ``docs/language_status/cobolrt_rules.md`` -- git-ignored, rendered by generated_docs.py and published to the
`generated` branch (#5057's pattern).

  cobolrt_rules.py --check     exit 1 when the catalogue and the code disagree
  cobolrt_rules.py render      write the page into the working tree (local reading)
  cobolrt_rules.py mark        write the missing markers of the catalogued families at their sites
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

from det_port import java_segments  # noqa: E402 -- the one Java lexer (det_port.java_code compares by it)

CATALOGUE = REPO / "docs" / "language_status" / "cobolrt_rules.json"
PAGE = REPO / "docs" / "language_status" / "cobolrt_rules.md"
RT = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"
REGISTER = REPO / "docs" / "language_status" / "register"

STATUSES = ("MATCHED", "DIFFERS", "REFUSED", "ASSUMED")
CALIBRATIONS = ("uncalibrated", "z/OS-measured")
OPTION_KINDS = ("compile", "source", "dialect", "deployment")
MARKER = re.compile(r"\[rule (RT-[A-Z0-9]+(?:-[A-Z0-9]+)+)\]")
ID_RE = re.compile(r"^RT-([A-Z0-9]+)-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
# a register entry a comment cites: "register C11", "oracle_assumptions C14", "oracle_assumptions.md X23"
REGISTER_CITE = re.compile(r"(?:register|oracle_assumptions(?:\.md)?)\s+([A-Z][0-9]+[a-z]?)\b")
_MODS = r"(?:(?:public|protected|private|static|final|synchronized|abstract|native|default|strictfp)\s+)*"
METHOD = re.compile(
    rf"(?m)^[ \t]*(?:@\w+(?:\([^)]*\))?\s+)*{_MODS}(?:<[^>{{}};=]*>\s+)?([\w$.]+(?:<[^{{}};=()]*>)?(?:\[\])*)\s+(\w+)\s*\("
)
NOT_TYPES = {
    "return",
    "new",
    "throw",
    "else",
    "case",
    "yield",
    "assert",
    "throws",
    "extends",
    "implements",
    "record",
    "public",
    "protected",
    "private",
    "static",
    "final",
    "synchronized",
    "abstract",
    "native",
    "default",
}


def compile_options() -> set[str]:
    """The Enterprise COBOL compiler options the #4704 resolver knows by name."""
    from gitgalaxy.core import compiler_options as co  # noqa: PLC0415

    return set(co.SEMANTIC_OPTIONS) | set(co._ABBREVIATIONS.values())


def runtime_option_problems(under: Any) -> list[str]:
    from gitgalaxy.core.runtime_options import calibration_problems  # noqa: PLC0415

    return calibration_problems(under)


def load(path: Path = CATALOGUE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scan(text: str) -> tuple[str, list[tuple[int, str]]]:
    """(code, comments) of Java source: the code with every comment and literal blanked (same lines, so a match keeps
    its line), and each comment as (line, text)."""
    code: list[str] = []
    comments: list[tuple[int, str]] = []
    line = 1
    for kind, t in java_segments(text):
        if kind == "comment":
            comments.append((line, t))
        code.append(t if kind == "code" else re.sub(r"[^\n]", " ", t))
        line += t.count("\n")
    return "".join(code), comments


def declarations(text: str) -> list[tuple[int, str]]:
    """[(line, name)] of each method a Java file declares (constructors excepted), in order: the line its name is on."""
    code, _ = scan(text)
    return [(code[: m.start(2)].count("\n") + 1, m.group(2)) for m in METHOD.finditer(code)
            if m.group(1) not in NOT_TYPES and m.group(2) not in NOT_TYPES]  # fmt: skip


def methods(text: str) -> list[str]:
    """The names of the methods a Java file declares, in order, each once."""
    return list(dict.fromkeys(n for _, n in declarations(text)))


def sites(text: str) -> list[tuple[int, str]]:
    """[(line, rule ID)] of each `[rule ID]` marker in the file's comments."""
    _, comments = scan(text)
    return [(ln + c[: m.start()].count("\n"), m.group(1)) for ln, c in comments for m in MARKER.finditer(c)]


def register_cites(text: str) -> set[str]:
    _, comments = scan(text)
    return {m.group(1) for _, c in comments for m in REGISTER_CITE.finditer(c)}


def register_status() -> dict[str, str]:
    """{register ID: its status text}."""
    out = {}
    for p in REGISTER.glob("*.md"):
        for ln in p.read_text(encoding="utf-8").splitlines()[1:]:
            if ln == "---":
                break
            if ln.startswith("status: "):
                out[p.stem] = json.loads(ln[len("status: ") :])
    return out


def _covers(entry: str, f: str, name: str) -> bool:
    """Whether a rule's `methods` entry ("name" anywhere in the family, or "file:name") names method `name` of `f`."""
    ef, _, en = entry.rpartition(":")
    return en == name and ef in ("", f)


def site_of(rule: dict[str, Any], files: list[str], decls: dict[str, list[tuple[int, str]]]) -> tuple[str, int] | None:
    """(file, line) of the declaration a rule's marker stands on: `site` ("name", "file:name", "...@N" for the Nth
    declaration of that name), else its first method's first declaration; None when there is none."""
    want = rule.get("site") or rule["methods"][0]
    want, _, nth = want.partition("@")
    hits = [(f, ln) for f in files for ln, n in decls.get(f, []) if _covers(want, f, n)]
    k = int(nth or 1)
    return hits[k - 1] if 0 < k <= len(hits) else None


def check(cat: dict[str, Any] | None = None, rt: Path = RT, register: dict[str, str] | None = None) -> list[str]:
    """The catalogue's problems against itself, the register and the runtime's code."""
    cat = load() if cat is None else cat
    register = register_status() if register is None else register
    docs, opts = cat.get("documents", {}), cat.get("options", {})
    probs: list[str] = []
    fams: dict[str, dict[str, Any]] = {}
    owner: dict[str, str] = {}
    for fam in cat["families"]:
        fams[fam["id"]] = fam
        for f in fam["files"]:
            if f in owner:
                probs.append(f"{f}: in families {owner[f]} and {fam['id']}")
            owner[f] = fam["id"]
            if not (rt / f).is_file():
                probs.append(f"family {fam['id']}: no runtime file {f}")
    on_disk = sorted(p.relative_to(rt).as_posix() for p in rt.rglob("*.java"))
    probs += [f"{f}: a runtime file no family lists" for f in on_disk if f not in owner]
    for o, d in opts.items():
        if d.get("kind") not in OPTION_KINDS:
            probs.append(f"option {o}: kind {d.get('kind')!r} is not one of {OPTION_KINDS}")
        elif d["kind"] == "compile" and o not in compile_options():
            probs.append(f"option {o}: not an Enterprise COBOL compiler option (gitgalaxy/core/compiler_options.py)")

    rules: dict[str, dict[str, Any]] = {}
    for r in cat["rules"]:
        rid = r.get("id", "?")
        if rid in rules:
            probs.append(f"{rid}: listed twice")
        rules[rid] = r
        m = ID_RE.match(rid)
        fam = fams.get(r.get("family", ""))
        if fam is None:
            probs.append(f"{rid}: no family {r.get('family')!r}")
            continue
        if not m or m.group(1) != fam["prefix"]:
            probs.append(f"{rid}: an ID of family {fam['id']} is RT-{fam['prefix']}-<NAME>")
        for k in ("title", "methods", "status", "calibration"):
            if not r.get(k):
                probs.append(f"{rid}: no {k}")
        for k in ("options", "register"):
            if not isinstance(r.get(k), list):
                probs.append(f"{rid}: {k} is a list (empty when none)")
        if r.get("status") not in STATUSES:
            probs.append(f"{rid}: status {r.get('status')!r} is not one of {STATUSES}")
        ibm = r.get("ibm")
        if ibm is None:
            if r.get("status") == "MATCHED" or not r.get("ibm_note"):
                probs.append(f"{rid}: no IBM reference -- only a rule that is not MATCHED, with ibm_note saying why")
        elif ibm.get("doc") not in docs or not ibm.get("section"):
            probs.append(f"{rid}: ibm needs a doc of `documents` and a section, has {ibm!r}")
        feats = r.get("features", [])
        if not isinstance(feats, list) or not feats or any(not isinstance(f, str) or ": " not in f for f in feats):
            if "features" in r:
                probs.append(f"{rid}: features is a non-empty list of 'category: key' (leave the key out when none)")
        probs += [f"{rid}: option {o!r} is not in `options`" for o in r.get("options") or [] if o not in opts]
        probs += [f"{rid}: no register entry {e}" for e in r.get("register") or [] if e not in register]
        if r.get("calibration") not in CALIBRATIONS:
            probs.append(f"{rid}: calibration {r.get('calibration')!r} is not one of {CALIBRATIONS}")
        elif r["calibration"] == "z/OS-measured" and not r.get("evidence"):
            probs.append(f"{rid}: z/OS-measured needs `evidence` (#4702)")
        if r.get("calibration") == "z/OS-measured":
            probs += [f"{rid}: {p}" for p in runtime_option_problems(r.get("calibrated_under"))]

    for fam in cat["families"]:
        fid = fam["id"]
        texts = {f: (rt / f).read_text(encoding="utf-8") for f in fam["files"] if (rt / f).is_file()}
        if not fam.get("done"):
            probs += [f"{f}:{ln}: [rule {rid}] in family {fid}, which is not catalogued yet (done: false)"
                      for f, t in texts.items() for ln, rid in sites(t)]  # fmt: skip
            continue
        mine = {rid: r for rid, r in rules.items() if r.get("family") == fid}
        decls = {f: declarations(t) for f, t in texts.items()}
        named = [e for r in mine.values() for e in r.get("methods") or []] + list(fam.get("plumbing", []))
        for f, ds in decls.items():
            for n in dict.fromkeys(n for _, n in ds):
                if not any(_covers(e, f, n) for e in named):
                    probs.append(f"{f}: method {n} is in no rule of {fid} and not in its plumbing")
        for e in dict.fromkeys(named):
            if not any(_covers(e, f, n) for f, ds in decls.items() for _, n in ds):
                probs.append(f"{fid}: {e} (named by a rule or plumbing) is not a method of {fam['files']}")
        sited: set[str] = set()
        for f, t in texts.items():
            for ln, rid in sites(t):
                r = rules.get(rid)
                if r is None:
                    probs.append(f"{f}:{ln}: [rule {rid}] has no catalogue entry")
                    continue
                if r.get("family") != fid:
                    probs.append(f"{f}:{ln}: [rule {rid}] is a rule of {r.get('family')}, not {fid}")
                    continue
                sited.add(rid)
                nxt = next((n for dl, n in decls[f] if dl > ln), None)
                if nxt is None or not any(_covers(e, f, nxt) for e in r.get("methods") or []):
                    probs.append(f"{f}:{ln}: [rule {rid}] stands before {nxt or 'no method'}, not one of its methods")
        for rid, r in mine.items():
            if rid not in sited:
                probs.append(f"{rid}: no code site (a `[rule {rid}]` comment in {fam['files']})")
            if r.get("methods") and site_of(r, fam["files"], decls) is None:
                probs.append(f"{rid}: its site {r.get('site') or r['methods'][0]!r} is no method of {fam['files']}")
        carried = {e for r in mine.values() for e in r.get("register") or []}
        for f, t in texts.items():
            probs += [f"{f}: cites register {e}, which no rule of {fid} carries"
                      for e in sorted(register_cites(t) - carried)]  # fmt: skip
    return probs


def mark(cat: dict[str, Any] | None = None, rt: Path = RT) -> list[str]:
    """Write the missing `// [rule ID]` markers of the catalogued families, each on its own line just above its
    site's declaration (and its annotations). Returns the files changed. A comment changes no port (det_port.java_code)."""
    cat = load() if cat is None else cat
    changed = []
    for fam in cat["families"]:
        if not fam.get("done"):
            continue
        texts = {f: (rt / f).read_text(encoding="utf-8") for f in fam["files"]}
        have = {rid for t in texts.values() for _, rid in sites(t)}
        decls = {f: declarations(t) for f, t in texts.items()}
        add: dict[str, list[tuple[int, str]]] = {}
        for r in cat["rules"]:
            if r["family"] == fam["id"] and r["id"] not in have:
                at = site_of(r, fam["files"], decls)
                if at:
                    add.setdefault(at[0], []).append((at[1], r["id"]))
        for f, items in add.items():
            lines = texts[f].split("\n")
            by_line: dict[int, list[str]] = {}
            for ln, rid in items:
                by_line.setdefault(ln, []).append(rid)
            for ln in sorted(by_line, reverse=True):
                i = ln - 1
                while i > 0 and lines[i - 1].lstrip().startswith("@"):
                    i -= 1
                indent = lines[ln - 1][: len(lines[ln - 1]) - len(lines[ln - 1].lstrip())]
                lines.insert(i, indent + "// " + " ".join(f"[rule {rid}]" for rid in sorted(by_line[ln])))
            (rt / f).write_text("\n".join(lines), encoding="utf-8")
            changed.append(f)
    return changed


def _cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def render(cat: dict[str, Any] | None = None, register: dict[str, str] | None = None) -> str:
    cat = load() if cat is None else cat
    register = register_status() if register is None else register
    docs = cat["documents"]
    rules = cat["rules"]
    out = [
        "# cobolrt rule catalogue",
        "",
        "<!-- generated by tests/tools/cobolrt_rules.py from docs/language_status/cobolrt_rules.json; do not edit -->",
        "",
        *cat["about"],
        "",
        "| family | files | rules | catalogued |",
        "|---|---|---|---|",
    ]
    for fam in cat["families"]:
        n = sum(1 for r in rules if r["family"] == fam["id"])
        files = ", ".join(f"`{f}`" for f in fam["files"])
        out.append(f"| {fam['id']}: {fam['title']} | {files} | {n} | {'yes' if fam.get('done') else 'not yet'} |")
    counts = ", ".join(f"{sum(1 for r in rules if r['status'] == s)} {s}" for s in STATUSES)
    cal = sum(1 for r in rules if r["calibration"] == "z/OS-measured")
    out += ["", f"{len(rules)} rules: {counts}; {cal} measured on z/OS (#4702).", "", "## IBM documents", ""]
    out += [f"- `{k}`: {d['title']}" + (f", {d['number']}" if d.get("number") else "") for k, d in docs.items()]
    out += ["", "## Options", ""] + [f"- `{k}` ({d['kind']}): {d['about']}" for k, d in cat["options"].items()]
    for fam in cat["families"]:
        out += ["", f"## {fam['id']}: {fam['title']}", "", fam["about"]]
        if not fam.get("done"):
            out += ["", "_Not catalogued yet._"]
            continue
        out += ["", "| id | rule | IBM | options | register (its status) | status | calibration |",
                "|---|---|---|---|---|---|---|"]  # fmt: skip
        for r in (r for r in rules if r["family"] == fam["id"]):
            ibm = f"`{r['ibm']['doc']}` {r['ibm']['section']}" if r.get("ibm") else f"none: {r['ibm_note']}"
            reg = "; ".join(f"{e} ({register.get(e, '?')})" for e in r["register"]) or "-"
            out.append(f"| {r['id']} | {_cell(r['title'])} | {_cell(ibm)} | {', '.join(r['options']) or '-'} | "
                       f"{_cell(reg)} | {r['status']} | {r['calibration']} |")  # fmt: skip
    return "\n".join(out).rstrip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("render")
    sub.add_parser("mark", help="write the missing [rule ID] markers at their sites")
    a = ap.parse_args()
    if a.check:
        probs = check()
        print("\n".join(probs) if probs else "cobolrt rule catalogue: consistent")
        return 1 if probs else 0
    if a.cmd == "render":
        PAGE.write_text(render(), encoding="utf-8")
        print(PAGE.relative_to(REPO))
        return 0
    if a.cmd == "mark":
        print("\n".join(mark()) or "no marker missing")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
