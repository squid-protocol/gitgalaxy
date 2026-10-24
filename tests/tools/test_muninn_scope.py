"""#5499: the PR-time sparse checkout of muninn.yml must cover every path its own PR filter triggers on."""

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


def test_sparse_checkout_keeps_every_manifest_a_scanner_reads():
    """Manifests outside the PR path filter still feed osv-scanner, so the sparse list must carry them."""
    import fnmatch
    import subprocess

    repo = WORKFLOW.parents[2]
    tracked = subprocess.run(
        ["git", "ls-files", "*requirements*.txt"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.split()
    pr_step = next(s for s in _steps() if s.get("if", "").strip("${} ") == "github.event_name == 'pull_request'")
    sparse = pr_step["with"]["sparse-checkout"].split()

    def covered(path):
        return any(("/" + path).startswith(e) if e.endswith("/") else fnmatch.fnmatch("/" + path, e) for e in sparse)

    missing = [p for p in tracked if not covered(p)]
    assert not missing, f"manifests absent from the PR sparse checkout: {missing}"
