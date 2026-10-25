"""#5499: the PR-time sparse checkout of muninn.yml must cover every path its own PR filter triggers on."""

import json
import sys
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
    pr_step = next(s for s in _steps() if s.get("if", "").startswith("${{ github.event_name == 'pull_request'"))
    sparse = set(pr_step["with"]["sparse-checkout"].split())
    for pattern in filt:
        root = "/" + pattern.removesuffix("**").rstrip("/")
        if pattern.endswith("**"):
            root += "/"
        assert any(root.startswith(entry) if entry.endswith("/") else root == entry for entry in sparse), (
            f"PR path filter {pattern!r} is not in the sparse checkout"
        )


def test_full_tree_checkout_remains_for_schedule_and_dispatch():
    full = [s for s in _steps() if s.get("if", "").startswith("${{ github.event_name != 'pull_request'")]
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
    pr_step = next(s for s in _steps() if s.get("if", "").startswith("${{ github.event_name == 'pull_request'"))
    sparse = pr_step["with"]["sparse-checkout"].split()

    def covered(path):
        return any(("/" + path).startswith(e) if e.endswith("/") else fnmatch.fnmatch("/" + path, e) for e in sparse)

    missing = [p for p in tracked if not covered(p)]
    assert not missing, f"manifests absent from the PR sparse checkout: {missing}"


def test_dispatch_scope_input_selects_the_pr_checkout():
    doc = _load()
    assert doc[True]["workflow_dispatch"]["inputs"]["scope"]["default"] == "full"
    pr = next(s for s in _steps() if s["name"].startswith("Checkout (PR"))
    full = next(s for s in _steps() if s["name"].startswith("Checkout (full"))
    assert "inputs.scope == 'pr'" in pr["if"]
    assert "inputs.scope != 'pr'" in full["if"]  # schedule: scope is empty, so the full tree stays the backstop


def _sarif(path, rows):
    results = [
        {
            "ruleId": rule,
            "message": {"text": "m"},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri}, "region": {"startLine": line}}}],
        }
        for rule, uri, line in rows
    ]
    path.write_text(json.dumps({"runs": [{"results": results}]}), encoding="utf-8")
    return str(path)


def test_scope_diff_equal_inside_scope_ignores_outside(tmp_path, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import muninn_scope_diff as msd

    inside = ("CKV_X", ".github/workflows/a.yml", 3)
    full = _sarif(tmp_path / "f.sarif", [inside, ("CKV_Y", "tests/fixtures/x.tf", 1), ("g", "docs/a.md", 2)])
    pr = _sarif(tmp_path / "p.sarif", [inside])
    assert msd.main([full, pr, "--scope", "/.github/", "/gitgalaxy/"]) == 0
    assert "'tests': 1" in capsys.readouterr().out


def test_scope_diff_flags_a_finding_missing_or_extra_inside_scope(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import muninn_scope_diff as msd

    a = ("R", "gitgalaxy/x.py", 1)
    b = ("R", "pyproject.toml", 1)
    full = _sarif(tmp_path / "f.sarif", [a, b])
    pr_missing = _sarif(tmp_path / "p1.sarif", [a])
    pr_extra = _sarif(tmp_path / "p2.sarif", [a, b, ("R2", "gitgalaxy/y.py", 2)])
    scope = ["/gitgalaxy/", "/pyproject.toml"]
    assert msd.main([full, pr_missing, "--scope", *scope]) == 1
    assert msd.main([full, pr_extra, "--scope", *scope]) == 1


def test_default_scope_is_the_workflow_sparse_list():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    pytest.importorskip("yaml")
    import muninn_scope_diff as msd

    scope = msd.default_scope()
    assert "/gitgalaxy/" in scope and msd.in_scope("pyproject.toml", scope) and not msd.in_scope("tests/a.py", scope)
