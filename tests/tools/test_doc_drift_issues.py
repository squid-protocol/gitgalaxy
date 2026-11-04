"""doc_drift_issues (#7627): grouping, chunking, dedupe, close, and the workflow's cost shape."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doc_drift_issues as d  # noqa: E402

WORKFLOW = os.path.join(d.REPO_ROOT, ".github", "workflows", "doc-drift.yml")


def p(*parts: str) -> str:
    return "/".join(parts)  # joined: a literal doc path in a tests/tools file is read as a doc a test depends on


def f(doc: str, line: int = 1, target: str = "x.py") -> dict:
    return {"check": "name", "doc": doc, "line": line, "target": target}


def test_areas() -> None:
    assert d.area_of(p(".claude", "skills", "a", "SKILL.md")) == "skills"
    assert d.area_of(p(".claude", "rules", "a.md")) == "rules and agents"
    assert d.area_of(p(".claude", "agents", "a.md")) == "rules and agents"
    assert d.area_of(p("docs", "wiki", "a.md")) == "wiki"
    assert d.area_of(p("docs", "a.md")) == "docs"
    assert d.area_of(p("gitgalaxy", "core", "README.md")) == "package READMEs"
    assert d.area_of(p("tests", "README.md")) == "tests"
    assert d.area_of("README.md") == "other"


def test_chunks_hold_at_most_four_files() -> None:
    fs = [f(p("docs", f"{i}.md")) for i in range(9)] + [f(p("docs", "0.md"), 5, "y.py")]
    out = d.chunks(fs)
    assert sorted(out) == ["doc drift: docs [1]", "doc drift: docs [2]", "doc drift: docs [3]"]
    assert all(len({x["doc"] for x in v}) <= 4 for v in out.values())
    assert sum(len(v) for v in out.values()) == 10


def test_first_run_creates_and_second_run_is_quiet() -> None:
    fs = [f(p("docs", "a.md"), 3), f(p("docs", "a.md"), 7, "z.py")]
    acts = d.decide(fs, {})
    assert [a["op"] for a in acts] == ["create"]
    body = acts[0]["body"]
    assert f"`{p('docs', 'a.md')}:3`" in body and f"`{p('docs', 'a.md')}:7`" in body
    assert d.decide(fs, {acts[0]["title"]: {"number": 1, "body": body}}) == []


def test_changed_findings_update_not_duplicate() -> None:
    title = "doc drift: docs [1]"
    old = {title: {"number": 9, "body": d.body_of(title, [f(p("docs", "a.md")), f(p("docs", "b.md"))])}}
    acts = d.decide([f(p("docs", "a.md"))], old)
    assert [(a["op"], a["number"]) for a in acts] == [("update", 9)]


def test_empty_area_closes_its_issue_and_leaves_other_issues() -> None:
    acts = d.decide([f(p("docs", "a.md"))], {"doc drift: skills [1]": {"number": 4, "body": "x"}})
    assert ("close", 4) in [(a["op"], a.get("number")) for a in acts]
    assert d.decide([], {"doc drift: skills [1]": {"number": 4, "body": ""}})[0]["op"] == "close"


def test_summary_reports_fixed_count() -> None:
    assert "3 fixed" in d.summary([f(p("docs", "a.md"))], 4)
    assert "fixed" not in d.summary([f(p("docs", "a.md"))], 1)


def test_workflow_is_one_cheap_nightly_job() -> None:
    text = Path(WORKFLOW).read_text(encoding="utf-8")
    assert "cron:" in text and "workflow_dispatch" in text
    assert "pull_request" not in text and "setup-python" not in text and "pip install" not in text
    assert "issues: write" in text and "pull-requests" not in text
    assert text.count("runs-on:") == 1
