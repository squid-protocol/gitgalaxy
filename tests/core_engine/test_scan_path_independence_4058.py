"""#4058: a scan's results depend only on paths under the scan root.

The same tree is scanned from several parent directories. Some parents carry names the
engine treats specially under the root (`tmp` and `docs` are IGNORED_DIRECTORIES, `vendor`
is a VENDOR_MINIFICATION_PATHS marker, `src` an INTENT_BIASED_SECTORS name). Every scan
must give the same sanitized audit (the golden-master comparison, DB slice included).

pytest's own tmp_path sits under `/tmp`, so before the fix even the "neutral" scan lost its
documentation coverage. The equality checks alone would not catch that, which is why the
neutral scan's coverage and vendor status are also asserted directly.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import golden_diff  # noqa: E402

PARENTS = ("neutral", "tmp", "docs", "vendor", "src")


def _tree(root: Path) -> Path:
    (root / "pkg").mkdir(parents=True)
    (root / "lib").mkdir()
    (root / "README.md").write_text("# Demo\n\n" + "This project shows a scan is path independent. " * 20 + "\n")
    (root / "pkg" / "README.md").write_text("# pkg\n\n" + "The package holds the core module. " * 10 + "\n")
    (root / "pkg" / "core.py").write_text(
        '"""Core."""\nimport os\nfrom lib.util import helper\n\n\ndef run(x):\n'
        "    if x > 1:\n        return helper(x)\n    for i in range(x):\n        print(i)\n    return os.getcwd()\n"
    )
    (root / "lib" / "util.py").write_text(
        "def helper(x):\n    try:\n        return x * 2\n    except Exception:\n        return None\n"
    )
    return root


def _scan(target: Path, out: Path) -> dict:
    out.mkdir(parents=True)
    env = {**os.environ, "GITGALAXY_DISABLE_GIT_HISTORY": "1", "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"}
    subprocess.run(  # noqa: S603 -- this interpreter + fixed module; paths are argv entries
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(target), "--output", str(out) + os.sep],
        check=True,
        env=env,
        capture_output=True,
        timeout=600,
    )
    return golden_diff.load_and_sanitize(str(out / f"{target.name}_galaxy_audit.json"))


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    base = tmp_path_factory.mktemp("path_independence")
    return {parent: _scan(_tree(base / parent / "proj"), base / "out" / parent) for parent in PARENTS}


def _doc_umbrellas(audit: dict) -> dict[str, float]:
    files = {}
    for group in audit["6. Parsed Files (Scanned Artifacts)"].values():
        for path, record in group.get("Files", {}).items():
            files[path] = record["1. Artifact Identity"].get("Doc Umbrella")
    return files


@pytest.mark.parametrize("parent", [p for p in PARENTS if p != "neutral"])
def test_the_same_tree_scans_the_same_under_any_parent(scans, parent):
    diffs = golden_diff.deep_compare(scans["neutral"], scans[parent])
    assert diffs == [], f"scanning from a parent named {parent!r} changed {len(diffs)} leaves: {diffs[:5]}"


def test_documentation_coverage_is_projected(scans):
    """The README shields reach the files beside them. Before the fix, any `tmp` above the
    scan root (pytest's own tmp_path included) zeroed every umbrella."""
    umbrellas = _doc_umbrellas(scans["neutral"])
    assert umbrellas["pkg/core.py"] > 0
    assert umbrellas["README.md"] > 0


def test_no_file_is_blanked_as_vendor(scans):
    """Before the fix, a checkout under `.../vendor/...` bypassed extraction for every file."""
    for parent, audit in scans.items():
        assert "MINIFIED VENDOR BYPASS" not in json.dumps(audit), parent
