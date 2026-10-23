"""#5499: the PR-time sparse checkout of muninn.yml must cover every path its own PR filter triggers on."""

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "muninn.yml"


def _load():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps():
    return _load()["jobs"]["muninn"]["steps"]


def test_sparse_checkout_covers_the_pr_path_filter():
    doc = _load()
    filt = doc[True]["pull_request"]["paths"]  # PyYAML reads the bare key `on` as True
    pr_step = next(s for s in _steps() if s.get("if", "").strip("${} ") == "github.event_name == 'pull_request'")
    sparse = set(pr_step["with"]["sparse-checkout"].split())
    for pattern in filt:
        root = "/" + pattern.removesuffix("**").rstrip("/")
        if pattern.endswith("**"):
            root += "/"
        assert any(root.startswith(entry) if entry.endswith("/") else root == entry for entry in sparse), (
            f"PR path filter {pattern!r} is not in the sparse checkout"
        )


def test_full_tree_checkout_remains_for_schedule_and_dispatch():
    full = [s for s in _steps() if s.get("if", "").strip("${} ") == "github.event_name != 'pull_request'"]
    assert len(full) == 1
    assert "sparse-checkout" not in full[0]["with"]


_MANIFEST = re.compile(
    r"(^|/)(requirements[^/]*\.txt|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Pipfile\.lock|uv\.lock"
    r"|go\.mod|Cargo\.lock|pom\.xml|Gemfile\.lock|composer\.lock)$"
)


def test_sparse_checkout_keeps_a_manifest_for_osv_scanner():
    """osv-scanner exits 128 (no packages found) with no manifest, silently dropping dependency scanning on PRs."""
    pr_step = next(s for s in _steps() if s.get("if", "").strip("${} ") == "github.event_name == 'pull_request'")
    sparse = pr_step["with"]["sparse-checkout"].split()
    git = shutil.which("git")
    out = subprocess.run(
        [git or "git", "ls-files"], cwd=WORKFLOW.parents[2], capture_output=True, text=True, check=False
    )
    if not git or out.returncode != 0:
        pytest.skip("not a git checkout")
    manifests = [f for f in out.stdout.splitlines() if _MANIFEST.search(f)]
    covered = [
        f
        for f in manifests
        if any(
            fnmatch.fnmatch("/" + f, e) or "/" + f == e or ("/" + f).startswith(e)
            for e in sparse
            if e.endswith("/") or "/" not in e[1:] or "." in e
        )
    ]
    assert covered, "no manifest osv-scanner recognises survives the PR sparse checkout"
