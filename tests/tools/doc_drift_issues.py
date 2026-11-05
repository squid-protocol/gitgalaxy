#!/usr/bin/env python3
"""doc-drift issues (#7627, step 4 of #7624): turn the doc-refs baseline into small, churn-sized issues.

Run nightly by .github/workflows/doc-drift.yml (stdlib only, no install):

    python3 tests/tools/doc_drift_issues.py [--dry-run]

It runs `tests/doc_refs_audit.py --json`, groups the findings by area (skills, rules and agents, wiki, docs, package
READMEs, tests, other), and splits each area into chunks of FILES_PER_ISSUE docs so one issue fits the 5-file cap.
Each chunk is one issue labelled `documentation`, titled `doc drift: <area> [k]`:

  * no open issue with that title -> open one;  an open one whose body differs -> update its body (no duplicate);
  * an open `doc drift:` issue whose chunk no longer exists (the area shrank or hit zero) -> comment and close;
  * a summary says how many findings are fixed and that the baseline can shrink (`--write-baseline`).

It never opens a PR and never touches the baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from typing import Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREFIX = "doc drift: "
LABEL = "documentation"
FILES_PER_ISSUE = 4
MARKER = "<!-- doc-drift-issue -->"


# (area, path prefix) in match order; the first prefix a doc starts with wins
def _dir(*parts: str) -> str:
    # joined, not written out: a literal doc path in a tests/tools script is read as a doc a test depends on
    return "/".join(parts) + "/"


AREAS = (
    ("skills", _dir(".claude", "skills")),
    ("rules and agents", _dir(".claude")),
    ("wiki", _dir("docs", "wiki")),
    ("tests", _dir("tests")),
    ("docs", _dir("docs")),
    ("package READMEs", _dir("gitgalaxy")),
)


def area_of(doc: str) -> str:
    for name, prefix in AREAS:
        if doc.startswith(prefix):
            return name
    return "other"


def chunks(findings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """findings -> {issue title: that chunk's findings}; files sorted, FILES_PER_ISSUE per chunk."""
    by_area: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for f in findings:
        by_area[area_of(f["doc"])][f["doc"]].append(f)
    out: dict[str, list[dict[str, Any]]] = {}
    for area, docs in by_area.items():
        names = sorted(docs)
        for k in range(0, len(names), FILES_PER_ISSUE):
            part = names[k : k + FILES_PER_ISSUE]
            out[f"{PREFIX}{area} [{k // FILES_PER_ISSUE + 1}]"] = [f for n in part for f in sorted(docs[n], key=_order)]
    return out


def _order(f: dict[str, Any]) -> tuple[int, str]:
    return (f.get("line") or 0, f["target"])


def body_of(title: str, fs: list[dict[str, Any]]) -> str:
    docs = sorted({f["doc"] for f in fs})
    lines = [
        MARKER,
        f"Nightly doc-drift job (#7627, part of #7624): {len(fs)} baselined finding(s) in {len(docs)} file(s). "
        "Fix the docs (or the reference), then run `python3 tests/doc_refs_audit.py --write-baseline` so the "
        "baseline shrinks in the same PR. This issue is rewritten each night and closes when the chunk reaches zero.",
        "",
    ]
    for d in docs:
        lines.append(f"### `{d}`")
        lines += [f"- `{d}:{f.get('line') or 1}`: {f['check']} `{f['target']}`" for f in fs if f["doc"] == d]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def decide(findings: list[dict[str, Any]], open_issues: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """findings + {title: {number, body}} of open doc-drift issues -> actions (create / update / close)."""
    want = chunks(findings)
    acts: list[dict[str, Any]] = []
    for title, fs in sorted(want.items()):
        body = body_of(title, fs)
        cur = open_issues.get(title)
        if cur is None:
            acts.append({"op": "create", "title": title, "body": body})
        elif (cur.get("body") or "").strip() != body.strip():
            acts.append({"op": "update", "number": cur["number"], "title": title, "body": body})
    for title, cur in sorted(open_issues.items()):
        if title not in want:
            acts.append({"op": "close", "number": cur["number"], "title": title})
    return acts


def summary(findings: list[dict[str, Any]], baseline_size: int | None) -> str:
    text = f"{len(findings)} finding(s) now in {len(chunks(findings))} issue chunk(s)."
    if baseline_size is not None and baseline_size > len(findings):
        text += f" {baseline_size - len(findings)} fixed: shrink the baseline (`--write-baseline`)."
    return text


def gh(*args: str, stdin: str | None = None) -> Any:
    res = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=False)  # noqa: S603, S607
    if res.returncode:
        raise SystemExit(f"gh {' '.join(args)[:120]} failed: {res.stderr.strip()[:300]}")
    return json.loads(res.stdout) if res.stdout.strip() else None


def audit_findings() -> list[dict[str, Any]]:
    res = subprocess.run(  # noqa: S603
        [sys.executable, os.path.join(REPO_ROOT, "tests", "doc_refs_audit.py"), "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    try:
        return json.loads(res.stdout)  # exit 1 just means findings
    except ValueError:
        raise SystemExit(f"doc_refs_audit --json gave no JSON: {res.stderr.strip()[:300]}") from None


def baseline_size() -> int | None:
    try:
        with open(os.path.join(REPO_ROOT, "tests", "doc_refs_audit_baseline.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    return sum(int(v) for v in doc.values()) if isinstance(doc, dict) else None


def open_doc_drift(repo: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for page in range(1, 6):
        items = gh("api", f"repos/{repo}/issues?state=open&labels={LABEL}&per_page=100&page={page}") or []
        for i in items:
            if "pull_request" not in i and i["title"].startswith(PREFIX):
                out[i["title"]] = {"number": i["number"], "body": i.get("body") or ""}
        if len(items) < 100:
            break
    return out


def apply(repo: str, acts: list[dict[str, Any]], dry: bool) -> None:
    for a in acts:
        print(json.dumps({k: v for k, v in a.items() if k != "body"}))
        if dry:
            continue
        if a["op"] == "create":
            gh(
                "api",
                f"repos/{repo}/issues",
                "-f",
                f"title={a['title']}",
                "-f",
                f"body={a['body']}",
                "-f",
                f"labels[]={LABEL}",
            )
        elif a["op"] == "update":
            gh("api", "-X", "PATCH", f"repos/{repo}/issues/{a['number']}", "-f", f"body={a['body']}")
        else:
            gh(
                "api",
                f"repos/{repo}/issues/{a['number']}/comments",
                "-f",
                "body=No doc-refs findings left in this chunk.",
            )
            gh(
                "api",
                "-X",
                "PATCH",
                f"repos/{repo}/issues/{a['number']}",
                "-f",
                "state=closed",
                "-f",
                "state_reason=completed",
            )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repo", default=os.environ.get("REPO", "squid-protocol/gitgalaxy"))
    a = ap.parse_args()
    findings = audit_findings()
    text = summary(findings, baseline_size())
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    apply(a.repo, decide(findings, open_doc_drift(a.repo)), a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
