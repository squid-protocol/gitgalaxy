"""#4918 step 4: the "unpinned dependency install in CI" rule (security/pipeline_pins.py)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.security.pipeline_pins import find_unpinned, scan_pipeline

ROOT = Path(__file__).resolve().parents[2]


def _kinds(text):
    return [k for _, k, _ in find_unpinned(text)]


@pytest.mark.parametrize(
    "line,kind",
    [
        ("pip install requests", "pip"),
        ('pip install "gitgalaxy[yaml]" tiktoken', "pip"),
        ("python -m pip install --upgrade pip", "pip"),
        ("pip3 install pytest>=8", "pip"),
        ("pip install git+https://github.com/x/y", "pip"),
        ("npm install left-pad", "npm"),
        ("npm i -g typescript@latest", "npm"),
        ("npm install --global typescript@^6", "npm"),
        ("yarn add lodash", "npm"),
        ("npx cowsay hi", "npm"),
        ("gem install rake", "gem"),
        ("go install golang.org/x/tools/cmd/stringer@latest", "go"),
        ("go install example.com/tool", "go"),
        ("cargo install ripgrep", "cargo"),
        ("curl -sSL https://example.com/i.sh | bash", "curl-pipe-shell"),
        ("curl -fsSL https://example.com/i.sh | sudo sh", "curl-pipe-shell"),
        ("bash <(curl -s https://example.com/i.sh)", "curl-pipe-shell"),
        ("- uses: actions/checkout@v4", "uses"),
        ("- uses: actions/checkout@main", "uses"),
        ("- uses: docker://alpine:3", "uses"),
        ("- uses: octo/action", "uses"),
    ],
)
def test_flags_each_install_form(line, kind):
    assert _kinds(line) == [kind], line


@pytest.mark.parametrize(
    "line",
    [
        "pip install --require-hashes -r ci/requirements/engines.txt",
        'pip install "ruff==0.16.0" PyYAML==6.0.3',
        'pip install "gitgalaxy[${SET}]==${V}"',
        "pip install -e .",
        'pip install -e ".[yaml]"',
        "pip install ./baseline",
        "pip install -r requirements.txt",
        "pip install git+https://github.com/x/y@" + "a" * 40,
        'npm install --global "typescript@6.0.2"',
        "npm ci",
        "npm install",
        "gem install rake -v 13.0.6",
        "go install example.com/tool@v1.2.3",
        "go install ./cmd/tool",
        "cargo install ripgrep --version 14.1.0 --locked",
        "curl -fsSLo f.sh https://example.com/i.sh",
        "- uses: actions/checkout@" + "3d3c42e5aac5ba805825da76410c181273ba90b1" + " # v7",
        "- uses: ./.github/actions/local",
        "- uses: docker://alpine@sha256:" + "a" * 64,
        "# pip install requests",
    ],
)
def test_allows_pinned_forms(line):
    assert not find_unpinned(line), line


def test_line_numbers_and_continuations_and_chains():
    text = "steps:\n  - run: |\n      echo hi\n      pip install \\\n        requests\n      pip install a==1 && npm i foo\n"
    assert [(n, k) for n, k, _ in find_unpinned(text)] == [(4, "pip"), (6, "npm")]


def test_scan_pipeline_matches_security_lens_shape():
    r = scan_pipeline("- run: pip install requests\n")
    assert r["counts"] == {"unpinned_install": 1}
    assert r["positions"] == {"unpinned_install": [1]}
    assert r["snippets"]["unpinned_install"] and scan_pipeline("a: b\n")["counts"] == {"unpinned_install": 0}


def test_hostile_input_is_linear():
    # one very long line (over the line cap, skipped) and many partial verbs: bounded, no backtracking
    find_unpinned("curl " + "a " * 100000 + "\n" + "pip install " * 5000)
    find_unpinned("curl " + "x" * 300 + " |" * 3000)


PIPELINE_SURFACES = [
    *sorted((ROOT / ".github" / "workflows").glob("*.yml")),
    *sorted((ROOT / "templates").rglob("*.yml")),
    ROOT / "action.yml",
    ROOT / "bitbucket-pipelines.yml",
]


@pytest.mark.parametrize("path", PIPELINE_SURFACES, ids=lambda p: str(p.relative_to(ROOT)))
def test_our_own_pipelines_are_clean(path):
    """The #4918 acceptance, kept: our own and shipped pipeline files carry no unpinned install."""
    assert not find_unpinned(path.read_text()), find_unpinned(path.read_text())


def test_reaches_sarif_end_to_end(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n      - run: pip install requests\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"], cwd=repo, check=True)
    out = tmp_path / "out"
    env = {**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER", "PYTHONPATH": str(ROOT)}
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(repo), "--output", str(out), "--sarif-only"],
        check=True,
        capture_output=True,
        env=env,
        timeout=300,
    )
    sarif = json.loads(next(out.glob("*_sarif.json")).read_text())
    hits = [r for r in sarif["runs"][0]["results"] if r["ruleId"] == "GG-SAST-UNPINNED_INSTALL"]
    lines = sorted(h["locations"][0]["physicalLocation"]["region"]["startLine"] for h in hits)
    assert lines == [7, 8], hits
    assert {r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]} >= {"GG-SAST-UNPINNED_INSTALL"}
