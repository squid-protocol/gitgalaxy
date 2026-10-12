"""#4918 step 4: the "unpinned dependency install in CI" rule (security/pipeline_pins.py)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.security.pipeline_pins import find_unpinned, find_unpinned_gitlab, is_gitlab_ci, scan_pipeline

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


# --- #4944: the four further members of the class -------------------------------------------------------------


def _surface_kinds(text, kind, gitlab=False):
    return [k for _, k, _ in find_unpinned(text, kind, gitlab)]


@pytest.mark.parametrize(
    "text,kind",
    [
        ("FROM python:3.12\nRUN pip install requests\n", "pip"),
        ("FROM node:22\nRUN npm install -g typescript\n", "npm"),
        ("RUN pip install --no-cache-dir requests \\\n    flask\n", "pip"),
        ("RUN apt-get update && apt-get install -y curl\n", "apt"),
        ("RUN curl -sSL https://example.com/i.sh | sh\n", "curl-pipe-shell"),
    ],
)
def test_dockerfile_flags_unpinned_run(text, kind):
    assert _surface_kinds(text, "dockerfile") == [kind], text


@pytest.mark.parametrize(
    "text",
    [
        "FROM python@sha256:" + "a" * 64 + "\n",
        "FROM python:3.12\n",  # a tag-only FROM is not a RUN install (see sibling gaps)
        "RUN pip install requests==2.32.3\n",
        "RUN pip install --require-hashes -r requirements.txt\n",
        "RUN pip install -r requirements.txt\n",
        "RUN npm install -g typescript@5.4.2\n",
        "RUN npm ci\n",
        "RUN apt-get install -y --no-install-recommends curl=7.88.1-10 jq=1.6-2.1\n",
        "RUN apk add --no-cache --virtual .deps gcc=13.2.1_git20231014-r0\n",
        "COPY . /app\n# RUN pip install requests\n",
        'RUN ["pip", "install", "requests"]\n',  # exec form: not parsed, never a false positive
    ],
)
def test_dockerfile_allows_pinned_forms(text):
    assert not find_unpinned(text, "dockerfile"), text


@pytest.mark.parametrize(
    "line,kind",
    [
        ("pip install requests", "pip"),
        ("python3 -m pip install --user flask", "pip"),
        ("npm install -g left-pad", "npm"),
        ("curl -fsSL https://example.com/i.sh | bash", "curl-pipe-shell"),
        ("wget -qO- https://example.com/i.sh | sh", "curl-pipe-shell"),
        ('if [ -z "$X" ]; then pip install requests; fi', "pip"),
        ("sudo apt-get install -y jq", "apt"),
        ("brew install jq", "brew"),
    ],
)
def test_shell_script_flags_unpinned(line, kind):
    assert _surface_kinds("#!/bin/sh\nset -e\n" + line + "\n", "shell") == [kind], line
    assert [n for n, _, _ in find_unpinned("#!/bin/sh\nset -e\n" + line + "\n", "shell")] == [3]


@pytest.mark.parametrize(
    "line",
    [
        'pip install --require-hashes -r "$ROOT/ci/requirements/test.txt"',
        "pip install -e .",
        "pip install 'ruff==0.16.0'",
        "npm ci",
        'npm install -g "typescript@${TS_PIN}"',
        "curl -fsSLo /tmp/i.sh https://example.com/i.sh",
        "# curl https://example.com/i.sh | bash",
        'sudo apt-get install -y "$PKG"',
        "apt-get install -y $(cat packages.txt)",
    ],
)
def test_shell_script_allows_pinned_forms(line):
    assert not find_unpinned("#!/bin/sh\n" + line + "\n", "shell"), line


@pytest.mark.parametrize(
    "line,kind",
    [
        ("- run: sudo apt-get install -y jq", "apt"),
        ("- run: apt-get install -y -o Dpkg::Options::=--force-confnew curl", "apt"),
        ("- run: sudo apt install ripgrep", "apt"),
        ("- run: apt-get install -y curl=7.88.1-10 jq", "apt"),  # one pinned, one not: still flagged
        ("- run: brew install jq", "brew"),
        ("- run: brew install --cask firefox", "brew"),
        ("- run: apk add curl", "apk"),
    ],
)
def test_yaml_flags_apt_brew(line, kind):
    assert _kinds(line) == [kind], line


@pytest.mark.parametrize(
    "line",
    [
        "- run: sudo apt-get install -y jq=1.6-2.1 curl=7.88.1-10",
        "- run: sudo apt-get install -y libfoo=1.2*",
        "- run: sudo apt-get update",
        "- run: apt-get install -y ./local.deb",
        "- run: apt-get install -y ${{ matrix.pkg }}",
        "- run: brew install python@3.12",
        "- run: brew install ./Formula/tool.rb",
        "- run: brew bundle",
        "- run: apk add --no-cache curl=8.5.0-r0",
    ],
)
def test_yaml_allows_pinned_apt_brew(line):
    assert not find_unpinned(line), line


def test_apt_and_brew_install_are_not_flagged_by_name_only_words():
    assert not find_unpinned("- run: echo adapt install things\n")


GITLAB_PINNED = (
    "default:\n  image: python:3.12-slim@sha256:" + "a" * 64 + "\n"
    "build:\n  image:\n    name: node:22@sha256:" + "b" * 64 + "\n    entrypoint: ['']\n"
    "include:\n"
    "  - project: group/shared\n    ref: " + "c" * 40 + "\n    file: /ci.yml\n"
    "  - ref: v1.2.0\n    project: group/other\n    file: /ci.yml\n"
    "  - local: /ci/local.yml\n"
    "  - template: Security/SAST.gitlab-ci.yml\n"
    "  - component: gitlab.com/group/comp/build@1.4.0\n"
    "  - remote: https://example.com/ci.yml\n"
    "deploy:\n  image: $CI_REGISTRY_IMAGE:latest\n  trigger:\n    project: other/repo\n    branch: main\n"
)


def test_gitlab_image_without_digest_is_flagged():
    assert [(n, k) for n, k, _ in find_unpinned_gitlab("job:\n  image: python:3.12\n")] == [(2, "gitlab-image")]
    assert [(n, k) for n, k, _ in find_unpinned_gitlab("image: alpine\n")] == [(1, "gitlab-image")]
    block = "job:\n  image:\n    name: node:22\n    entrypoint: ['']\n"
    assert [(n, k) for n, k, _ in find_unpinned_gitlab(block)] == [(2, "gitlab-image")]


def test_gitlab_include_without_ref_is_flagged():
    text = "include:\n  - project: group/shared\n    file: /ci.yml\n  - file: /ci.yml\n    project: g/o\n"
    assert [(n, k) for n, k, _ in find_unpinned_gitlab(text)] == [(2, "gitlab-include"), (4, "gitlab-include")]
    assert [n for n, _, _ in find_unpinned_gitlab("include:\n  - component: gitlab.com/g/c/b\n")] == [2]
    assert [n for n, _, _ in find_unpinned_gitlab("include:\n  - component: gitlab.com/g/c/b@~latest\n")] == [2]


def test_gitlab_pinned_and_unrelated_forms_are_clean():
    assert not find_unpinned_gitlab(GITLAB_PINNED), find_unpinned_gitlab(GITLAB_PINNED)


def test_gitlab_checks_only_run_on_gitlab_files():
    text = "services:\n  db:\n    image: postgres:16\n"
    assert _surface_kinds(text, "yaml", gitlab=False) == []
    assert _surface_kinds(text, "yaml", gitlab=True) == ["gitlab-image"]
    assert (
        is_gitlab_ci(".gitlab-ci.yml")
        and is_gitlab_ci("ci/.gitlab-ci.yaml")
        and is_gitlab_ci("templates/gitlab/scan.yml")
    )
    assert not is_gitlab_ci("docker-compose.yml") and not is_gitlab_ci(".github/workflows/gitlab-sync.yml")
    assert scan_pipeline(text, "yaml", ".gitlab-ci.yml")["counts"] == {"unpinned_install": 1}
    assert scan_pipeline(text, "yaml", "docker-compose.yml")["counts"] == {"unpinned_install": 0}


def test_uses_is_yaml_only():
    assert not find_unpinned("uses: actions/checkout@v4\n", "shell")
    assert not find_unpinned("uses: actions/checkout@v4\n", "dockerfile")


def test_hostile_new_surfaces_are_linear():
    find_unpinned("apt-get " + "x " * 50000 + "\n" + "apt install " * 5000, "shell")
    find_unpinned("image:\n" * 5000 + "  - project: a\n" * 5000, "yaml", True)
    find_unpinned_gitlab("include:\n" + "  - project: p\n" + "    k: v\n" * 20000)


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
    """The #4918 acceptance, kept: our own and shipped pipeline files carry no unpinned install.

    Exception: the four system-package installs #4944's rule extension found. Pinning them means editing
    `.github/workflows`, which is the CI half of #4944; each entry is exact (file, line, kind), so any other
    finding, or a moved one, fails, and fixing one forces its entry out of this table.
    """
    rel = str(path.relative_to(ROOT))
    got = {(n, k) for n, k, _ in find_unpinned(path.read_text())}
    assert got == OPEN_SYSTEM_PACKAGE_INSTALLS.get(rel, set()), got


OPEN_SYSTEM_PACKAGE_INSTALLS = {
    ".github/workflows/full-suite-gate.yml": {(161, "brew")},
    ".github/workflows/smoke-test.yml": {(110, "brew")},
    ".github/workflows/tri-comparison-audit.yml": {(88, "apt")},
    ".github/workflows/tri-comparison-history.yml": {(96, "apt")},
}


def test_our_own_gitlab_template_is_clean():
    path = ROOT / "templates" / "gitlab" / "scan.yml"
    assert not find_unpinned(path.read_text(), "yaml", True), find_unpinned(path.read_text(), "yaml", True)


def test_reaches_sarif_end_to_end(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n      - run: pip install requests\n"
    )
    (repo / "Dockerfile").write_text("FROM python:3.12\nRUN pip install requests\n")
    (repo / "ci.sh").write_text("#!/bin/sh\nset -e\ncurl -sSL https://example.com/i.sh | bash\n")
    (repo / ".gitlab-ci.yml").write_text("build:\n  image: python:3.12\n  script:\n    - echo hi\n")
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
    where = sorted(
        (
            h["locations"][0]["physicalLocation"]["artifactLocation"]["uri"].split("/")[-1],
            h["locations"][0]["physicalLocation"]["region"]["startLine"],
        )
        for h in hits
    )
    assert where == [(".gitlab-ci.yml", 2), ("Dockerfile", 2), ("ci.sh", 3), ("ci.yml", 7), ("ci.yml", 8)], hits
    assert {r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]} >= {"GG-SAST-UNPINNED_INSTALL"}
