"""A step that pushes to the `generated` branch needs push credentials (#6555): the Evidence Refresh harness publish died
with "could not read Username" because its checkout had persist-credentials: false. Lint every workflow."""

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
PUSHERS = ("generated_branch.py publish", "generated_branch.py push-head")


def _pushing_jobs(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for name, job in (doc.get("jobs") or {}).items():
        steps = job.get("steps") or []
        pushes = [s for s in steps if any(p in str(s.get("run", "")) for p in PUSHERS)]
        if pushes:
            yield name, steps, pushes


def _checkouts(steps):
    return [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@")]


def _push_dir(step):
    """The directory the step pushes from: its working-directory, else the first `cd X` of its script, else the root."""
    run = str(step.get("run", ""))
    m = re.search(r"^\s*(?:\(\s*)?cd\s+([\w./-]+)", run, re.M)
    return str(step.get("working-directory") or (m.group(1) if m else ".")).rstrip("/")


def _cases():
    return [(p.name, job, steps, pushes) for p in WORKFLOWS for job, steps, pushes in _pushing_jobs(p)]


CASES = _cases()


def test_the_lint_sees_the_pushing_jobs():
    assert {"evidence-refresh.yml", "evidence-pages.yml", "generated-docs.yml"} <= {c[0] for c in CASES}  # noqa: S101


@pytest.mark.parametrize("wf,job,steps,pushes", CASES, ids=[f"{c[0]}:{c[1]}" for c in CASES])
def test_a_pushing_step_runs_from_a_checkout_that_kept_credentials(wf, job, steps, pushes):
    by_path = {str((c.get("with") or {}).get("path") or ".").rstrip("/"): c for c in _checkouts(steps)}
    for step in pushes:
        where = _push_dir(step)
        if "set-url" in str(step.get("run", "")):  # the step hands itself a token URL
            continue
        c = by_path.get(where)
        assert c is not None, f"{wf}:{job}: the push runs in {where!r}, which no checkout step creates"  # noqa: S101
        kept = (c.get("with") or {}).get("persist-credentials") is True
        assert kept, (  # noqa: S101
            f"{wf}:{job}: the push runs from {where!r}, checked out without persist-credentials: true, so it fails "
            "with 'could not read Username' (#6555)"
        )
