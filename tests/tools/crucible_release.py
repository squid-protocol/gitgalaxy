#!/usr/bin/env python3
"""A cics-crucible release, from gitgalaxy's side: the draft release notes, and what a pin bump left behind.

    python tests/tools/crucible_release.py notes <crucible-dir> --since v0.4.0 [--to HEAD] [--no-validate]
    python tests/tools/crucible_release.py pin-check v0.4.0          # after bumping the pin away from v0.4.0

`notes` drafts the release notes in the format of the v0.4.0 / v0.5.0 releases (squid-protocol/cics-crucible
RELEASING.md, step 3), from git alone -- the crucible checkout is read, never changed:
  * case and scenario counts at --since and at --to, with the deltas;
  * the added cases by trap: id, title, scenarios, the PR that added each (its commit subject);
  * pre-existing cases with a changed file -- an expected log among them is a LOG CORRECTION, which needs its
    NOTES.md `## Changes` justification (AGENTS.md rule 3); none means "No log was corrected";
  * the SPEC / schema / validator diff, flagged ADDITIVE when the format ids are unchanged and every --since case
    still validates under --to's tools/validate.py and schemas, else NOT ADDITIVE (a format major bump, SPEC rule 5);
  * tools/validate.py on --to's tree, and the other commits since the tag;
  * the RELEASING.md "Where things stand" row to add.
The prose sentences (what the cases are for) are the author's: the draft marks them TODO.

`pin-check OLD_TAG` lists every mention of the old tag left in this gitgalaxy checkout after a pin bump -- the step
"grep for the old tag" of RELEASING.md step 4 -- except the historical proof.crucible_ref values in the ports'
provenance.json (`proof.crucible_ref` and the appended `reproven` entries say where a port WAS proven and are never
rewritten). Mentions on lines that do not say "cics" are listed apart: they are often another repo's tag
(estate-crucible has a v0.4.0 too). Exit 1 when tests/_cics_crucible_pin.py still pins OLD_TAG.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
FORMAT_RE = re.compile(r"cics-crucible/(?:case/|expected/)?(\d+)")
SPEC_PATHS = ("SPEC.md", "schema", "tools/validate.py")


def git(repo: Path, *args: str, check: bool = True) -> str:
    res = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if check and res.returncode:
        raise SystemExit(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def cases_at(repo: Path, ref: str) -> dict[str, dict[str, Any]]:
    """case id -> {"dir", "trap", "title", "scenarios": [(id, summary, path)]} at `ref`."""
    out = {}
    for path in git(repo, "ls-tree", "-r", "--name-only", ref, "--", "cases").splitlines():
        if not path.endswith("/case.json"):
            continue
        doc = json.loads(git(repo, "show", f"{ref}:{path}"))
        out[doc["id"]] = {"dir": path.rsplit("/", 1)[0], "trap": doc.get("trap", path.split("/")[1]),
                          "title": doc.get("title", ""), "programs": [Path(c).stem for c in doc["sources"]["cobol"]],
                          "scenarios": [(s["id"], s.get("summary", ""), s.get("path", "")) for s in doc["scenarios"]]}  # fmt: skip
    return out


def format_majors(repo: Path, ref: str) -> set[str]:
    majors: set[str] = set()
    for path in ("SPEC.md", "schema/case.schema.json", "schema/expected.schema.json"):
        text = git(repo, "show", f"{ref}:{path}", check=False)
        majors |= set(FORMAT_RE.findall(text))
    return majors


def _extract(repo: Path, ref: str, paths: list[str], dest: Path) -> None:
    data = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", ref, "--", *paths],  # noqa: S603, S607
                          capture_output=True, check=True).stdout  # fmt: skip
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        members = _safe_members(tf, dest)
        try:
            tf.extractall(dest, members=members, filter="data")
        except TypeError:  # Python < 3.10.12 / 3.11.4: no extraction filters; the members are checked above
            tf.extractall(dest, members=members)  # noqa: S202


def _safe_members(tf: tarfile.TarFile, dest: Path) -> list[tarfile.TarInfo]:
    """The archive's members, refused unless each is a plain file or directory that lands inside `dest` (no
    absolute path, no `..`, no link or device): a tag of another repository is input, not trusted code."""
    root = dest.resolve()
    members = tf.getmembers()
    for m in members:
        target = (root / m.name).resolve()
        if not (m.isfile() or m.isdir()) or Path(m.name).is_absolute() or not target.is_relative_to(root):
            raise ValueError(f"refusing archive member {m.name!r}: not a plain file or directory inside {dest}")
    return members


def validate(repo: Path, tools_ref: str, cases_ref: str) -> tuple[bool, str]:
    """tools/validate.py (and the schemas) at `tools_ref`, over the cases at `cases_ref`: (ok, last line)."""
    with tempfile.TemporaryDirectory(prefix="crucible-validate-") as tmp:
        root = Path(tmp)
        _extract(repo, tools_ref, ["tools", "schema", "SPEC.md"], root)
        _extract(repo, cases_ref, ["cases"], root)
        res = subprocess.run([sys.executable, "-I", str(root / "tools" / "validate.py")], cwd=root,  # noqa: S603
                             capture_output=True, text=True, check=False)  # fmt: skip
    lines = (res.stdout + res.stderr).strip().splitlines()
    return res.returncode == 0, (lines[-1] if lines else f"exit {res.returncode}")


def notes(repo: Path, since: str, to: str = "HEAD", run_validate: bool = True) -> dict[str, Any]:
    old, new = cases_at(repo, since), cases_at(repo, to)
    added = sorted(set(new) - set(old), key=lambda c: (new[c]["trap"], c))
    removed = sorted(set(old) - set(new))
    changed_files = git(repo, "diff", "--name-only", f"{since}..{to}").splitlines()
    touched: dict[str, list[str]] = defaultdict(list)
    for f in changed_files:
        for cid, c in old.items():
            if f.startswith(c["dir"] + "/"):
                touched[cid].append(f)
    added_by: dict[str, str] = {}
    for cid in added:
        subj = git(
            repo, "log", "--diff-filter=A", "--format=%s", f"{since}..{to}", "--", f"{new[cid]['dir']}/case.json"
        )
        added_by[cid] = subj.strip().splitlines()[-1] if subj.strip() else ""
    spec_stat = git(repo, "diff", "--numstat", f"{since}..{to}", "--", *SPEC_PATHS)
    spec_files = []
    for ln in spec_stat.splitlines():
        a, d, f = ln.split("\t")
        spec_files.append({"file": f, "added": int(a) if a.isdigit() else 0, "removed": int(d) if d.isdigit() else 0})
    majors_old, majors_new = format_majors(repo, since), format_majors(repo, to)
    old_ok, old_line = validate(repo, to, since) if run_validate and spec_files else (True, "no SPEC/tool change")
    new_ok, new_line = validate(repo, to, to) if run_validate else (True, "not run (--no-validate)")
    additive = majors_old == majors_new and old_ok
    other = []
    for ln in git(repo, "log", "--format=%h%x09%s", f"{since}..{to}").splitlines():
        h, s = ln.split("\t", 1)
        files = git(repo, "show", "--name-only", "--format=", h).split()
        if not any(f.startswith("cases/") for f in files):
            other.append(s)
    return {"since": since, "to": to, "cases_before": len(old), "cases_after": len(new),
            "scenarios_before": sum(len(c["scenarios"]) for c in old.values()),
            "scenarios_after": sum(len(c["scenarios"]) for c in new.values()),
            "added": [{"id": c, **new[c], "added_by": added_by[c]} for c in added], "removed": removed,
            "touched": dict(touched), "log_corrections": {c: [f for f in fs if "/expected/" in f] for c, fs in touched.items()
                                                          if any("/expected/" in f for f in fs)},
            "spec_files": spec_files, "formats_before": sorted(majors_old), "formats_after": sorted(majors_new),
            "old_cases_validate": [old_ok, old_line], "validate": [new_ok, new_line], "additive": additive,
            "other_commits": other}  # fmt: skip


def notes_markdown(n: dict[str, Any], tag: str) -> str:
    fmt = "/".join(n["formats_after"]) or "?"
    spec = ("with additive SPEC additions only, so every " + n["since"] + " file still validates"
            if n["spec_files"] and n["additive"] else
            "no SPEC or tool changed" if not n["spec_files"] else
            "**NOT ADDITIVE**: " + ("the format major moved" if n["formats_before"] != n["formats_after"] else
                                    f"{n['since']} cases fail the new validator ({n['old_cases_validate'][1]})"))  # fmt: skip
    corrected = ("No log was corrected: no file under an existing case changed." if not n["touched"] else
                 "Files under existing cases changed (each needs its NOTES.md `## Changes` justification): "
                 + "; ".join(f"`{c}` ({len(fs)} files)" for c, fs in sorted(n["touched"].items())))  # fmt: skip
    lines = [(f"<!-- draft by tests/tools/crucible_release.py notes --since {n['since']} (to {n['to']}); TODO lines "
              "are yours -->"), "",
             (f"Format unchanged: `cics-crucible/{fmt}` (SPEC.md), {spec}. **{n['cases_after']} cases** (was "
              f"{n['cases_before']}) and **{n['scenarios_after']} scenarios** (was {n['scenarios_before']}). "
              f"{corrected}"),
             "",
             "TODO: what the new cases cover and for which gitgalaxy issue / PRs. The expected logs were written by hand "
             "from IBM's CICS Application Programming Reference before running against any implementation; the "
             f"citations are in each case's `NOTES.md`. All {n['cases_after']} cases pass `tools/validate.py`"
             + ("." if n["validate"][0] else f" -- **NO: {n['validate'][1]}**."), ""]  # fmt: skip
    if n["formats_before"] != n["formats_after"]:
        lines[2] = lines[2].replace(
            "Format unchanged", f"**Format changed** ({n['formats_before']} -> {n['formats_after']})"
        )
    by_trap: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in n["added"]:
        by_trap[c["trap"]].append(c)
    lines += ["## Added, by trap", ""] if by_trap else ["No case added.", ""]
    for trap, cs in sorted(by_trap.items()):
        lines += [f"**{trap}** ({len(cs)} case{'s' if len(cs) > 1 else ''}):", ""]
        for c in cs:
            pr = re.search(r"\(#(\d+)\)\s*$", c["added_by"])
            lines.append(f"- **`{c['id']}`** ({len(c['scenarios'])} scenarios{f', #{pr.group(1)}' if pr else ''}; "
                         f"{' / '.join(c['programs'])}). {c['title']}")  # fmt: skip
            lines += [f"  - `{sid}` ({path}): {summary}" for sid, summary, path in c["scenarios"]]
        lines.append("")
    if n["removed"]:
        lines += ["## Removed", "", *[f"- `{c}`" for c in n["removed"]], ""]
    if n["spec_files"]:
        flag = "additive" if n["additive"] else "NOT ADDITIVE"
        lines += [f"## SPEC changes ({flag})", "",
                  *[f"- `{f['file']}`: +{f['added']} / -{f['removed']} lines" for f in n["spec_files"]],
                  f"- {n['since']} cases under the new validator: {n['old_cases_validate'][1]}",
                  "- TODO: one line per addition (what a log may now say).", ""]  # fmt: skip
    if n["log_corrections"]:
        lines += ["## Log corrections", "", *[f"- `{c}`: {', '.join(fs)} -- TODO: the NOTES.md justification"
                                              for c, fs in sorted(n["log_corrections"].items())], ""]  # fmt: skip
    if n["other_commits"]:
        lines += [f"## Also on main since {n['since']}", "", *[f"- {s}" for s in n["other_commits"]], ""]
    ids = ", ".join(f"`{c['id']}`" for c in n["added"]) or "no case"
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    corrected_row = "Logs corrected: TODO." if n["log_corrections"] else "No log corrected."
    lines += [(f"gitgalaxy moves its pin to {tag} in a separate PR, which re-baselines the runner and re-proves the "
               "committed ports."), "", "---", "RELEASING.md row:", "",
              (f"| `{tag}` | {today} | Format unchanged. {n['cases_after']} cases, {n['scenarios_after']} scenarios. "
               f"Adds {ids} (TODO: what for). {corrected_row} |")]  # fmt: skip
    return "\n".join(lines) + "\n"


# ---- pin-check --------------------------------------------------------------------------------------------------
def pin_mentions(repo: Path, tag: str) -> tuple[list[str], list[str]]:
    """(cics-context mentions, other mentions) of `tag` -- `path:line: text` -- minus provenance history."""
    out = subprocess.run(["git", "-C", str(repo), "grep", "-n", "-I", "-E", re.escape(tag) + r"([^0-9]|$)"],  # noqa: S603, S607
                         capture_output=True, text=True, check=False).stdout  # fmt: skip
    cics: list[str] = []
    other: list[str] = []
    for ln in out.splitlines():
        path, _, rest = ln.partition(":")
        lineno, _, text = rest.partition(":")
        if path.endswith("provenance.json") and '"crucible_ref"' in text:
            continue  # proof.crucible_ref / reproven[].crucible_ref: where a port WAS proven, never rewritten
        row = f"{path}:{lineno}: {text.strip()[:140]}"
        (cics if "cics" in (path + text).lower() else other).append(row)
    return cics, other


def cmd_pin_check(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(args.repo / "tests"))
    import _cics_crucible_pin as pin

    cics, other = pin_mentions(args.repo, args.tag)
    still = args.tag == pin.PINNED_REF
    print(f"PINNED_REF = {pin.PINNED_REF}" + ("  <-- still the old tag: the pin is not bumped" if still else ""))
    print(f"\n{len(cics)} mention(s) of {args.tag} in a CICS-crucible context (provenance history excluded):")
    print("\n".join(f"  {r}" for r in cics) or "  none")
    print(f"\n{len(other)} other mention(s) (often another repo's tag; check each):")
    print("\n".join(f"  {r}" for r in other) or "  none")
    return 1 if still else 0


def cmd_notes(args: argparse.Namespace) -> int:
    n = notes(args.crucible, args.since, args.to, run_validate=not args.no_validate)
    if args.json:
        print(json.dumps(n, indent=1))
    else:
        tag = (
            args.tag
            or git(args.crucible, "describe", "--tags", "--exact-match", args.to, check=False).strip()
            or "vX.Y.Z"
        )
        print(notes_markdown(n, tag), end="")
    return 0 if n["validate"][0] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("notes", help="draft release notes since a tag")
    n.add_argument("crucible", type=Path, help="a cics-crucible checkout (read only)")
    n.add_argument("--since", required=True, help="the previous release tag")
    n.add_argument("--to", default="HEAD", help="the commit to release (default HEAD)")
    n.add_argument("--tag", help="the new tag's name (default: the tag at --to, else vX.Y.Z)")
    n.add_argument("--no-validate", action="store_true", help="skip running tools/validate.py")
    n.add_argument("--json", action="store_true")
    p = sub.add_parser("pin-check", help="mentions of the old tag left after a pin bump")
    p.add_argument("tag", help="the tag the pin moved AWAY from")
    p.add_argument("--repo", type=Path, default=REPO, help="the gitgalaxy checkout (default: this one)")
    args = ap.parse_args(argv)
    return cmd_notes(args) if args.cmd == "notes" else cmd_pin_check(args)


if __name__ == "__main__":
    sys.exit(main())
