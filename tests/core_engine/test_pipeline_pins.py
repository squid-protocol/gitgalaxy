"""#4918 step 4: the "unpinned dependency install in CI" rule (security/pipeline_pins.py)."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.security.pipeline_pins import (
    find_unpinned,
    find_unpinned_github,
    find_unpinned_gitlab,
    is_github_workflow,
    is_gitlab_ci,
    scan_pipeline,
)

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
        ("RUN yum install -y git\n", "yum"),
        ("RUN dnf install -y wget\n", "dnf"),
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
        "RUN yum install -y git-2.43.0-1.el9\n",
        "RUN dnf install -y wget-1.21.3-1.el9\n",
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
        ("yum install -y jq", "yum"),
        ("dnf install -y nginx", "dnf"),
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
        "yum install -y jq-1.6-2.el9",
        "dnf install -y nginx-1:1.24.0-1.el9",
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
        ("- run: sudo yum install -y jq", "yum"),
        ("- run: yum install -y python3-pip gcc-c++", "yum"),
        ("- run: sudo dnf install -y nginx", "dnf"),
    ],
)
def test_yaml_flags_apt_brew_yum(line, kind):
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
        "- run: sudo yum install -y jq-1.6-2.el9 curl-7.88.1-1.el9",
        "- run: sudo dnf install -y nginx-1:1.24.0-1.el9",
        "- run: yum install -y gcc-c++-11.4.1-2.el9",
        "- run: yum install -y ./local.rpm",
        "- run: yum install -y pkg.rpm",
        "- run: yum install -y $PKG",
        "- run: dnf install -y ${{ matrix.pkg }}",
    ],
)
def test_yaml_allows_pinned_apt_brew_yum(line):
    assert not find_unpinned(line), line


def test_apt_and_brew_install_are_not_flagged_by_name_only_words():
    assert not find_unpinned("- run: echo adapt install things\n")


GITLAB_PINNED = (
    "default:\n  image: python:3.12-slim@sha256:" + "a" * 64 + "\n"
    "build:\n  image:\n    name: node:22@sha256:" + "b" * 64 + "\n    entrypoint: ['']\n"
    "  services:\n"
    "    - postgres:16@sha256:" + "c" * 64 + "\n"
    "    - name: redis:7@sha256:" + "d" * 64 + "\n      alias: redis\n"
    "    - $SERVICE_IMAGE\n"
    "include:\n"
    "  - project: group/shared\n    ref: " + "e" * 40 + "\n    file: /ci.yml\n"
    "  - ref: v1.2.0\n    project: group/other\n    file: /ci.yml\n"
    "  - local: /ci/local.yml\n"
    "  - template: Security/SAST.gitlab-ci.yml\n"
    "  - component: gitlab.com/group/comp/build@1.4.0\n"
    "deploy:\n  image: $CI_REGISTRY_IMAGE:latest\n  trigger:\n    project: other/repo\n    branch: main\n"
)


def test_gitlab_image_without_digest_is_flagged():
    assert [(n, k) for n, k, _ in find_unpinned_gitlab("job:\n  image: python:3.12\n")] == [(2, "gitlab-image")]
    assert [(n, k) for n, k, _ in find_unpinned_gitlab("image: alpine\n")] == [(1, "gitlab-image")]
    block = "job:\n  image:\n    name: node:22\n    entrypoint: ['']\n"
    assert [(n, k) for n, k, _ in find_unpinned_gitlab(block)] == [(2, "gitlab-image")]


def test_gitlab_services_without_digest_is_flagged():
    assert [(n, k) for n, k, _ in find_unpinned_gitlab("services:\n  - postgres:16\n")] == [(2, "gitlab-service")]
    assert [(n, k) for n, k, _ in find_unpinned_gitlab("job:\n  services:\n    - name: redis:7\n")] == [
        (3, "gitlab-service")
    ]
    mixed = "services:\n  - postgres:16@sha256:" + "a" * 64 + "\n  - redis:7\n"
    assert [(n, k) for n, k, _ in find_unpinned_gitlab(mixed)] == [(3, "gitlab-service")]


def test_gitlab_include_without_ref_is_flagged():
    text = "include:\n  - project: group/shared\n    file: /ci.yml\n  - file: /ci.yml\n    project: g/o\n"
    assert [(n, k) for n, k, _ in find_unpinned_gitlab(text)] == [(2, "gitlab-include"), (4, "gitlab-include")]
    assert [n for n, _, _ in find_unpinned_gitlab("include:\n  - component: gitlab.com/g/c/b\n")] == [2]
    assert [n for n, _, _ in find_unpinned_gitlab("include:\n  - component: gitlab.com/g/c/b@~latest\n")] == [2]


def test_gitlab_include_remote_is_flagged():
    text = "include:\n  - remote: https://example.com/ci.yml\n"
    assert [(n, k) for n, k, _ in find_unpinned_gitlab(text)] == [(2, "gitlab-include")]
    quoted = "include:\n  - remote: 'https://cdn.example.com/pipe.yml'\n"
    assert [(n, k) for n, k, _ in find_unpinned_gitlab(quoted)] == [(2, "gitlab-include")]


def test_gitlab_pinned_and_unrelated_forms_are_clean():
    assert not find_unpinned_gitlab(GITLAB_PINNED), find_unpinned_gitlab(GITLAB_PINNED)


def test_github_actions_container_and_services_flagged():
    assert [(n, k) for n, k, _ in find_unpinned_github("job:\n  container: node:20\n")] == [(2, "github-container")]
    block = "job:\n  container:\n    image: node:20\n    options: --cpus 1\n"
    assert [(n, k) for n, k, _ in find_unpinned_github(block)] == [(3, "github-container")]
    srv = "job:\n  services:\n    redis:\n      image: redis:6\n"
    assert [(n, k) for n, k, _ in find_unpinned_github(srv)] == [(4, "github-service")]


def test_github_actions_container_and_services_pinned_forms_clean():
    text = (
        "job:\n"
        "  container: node:20@sha256:" + "a" * 64 + "\n"
        "  services:\n"
        "    redis:\n"
        "      image: redis:6@sha256:" + "b" * 64 + "\n"
        "    db:\n"
        "      image: ${{ matrix.db_image }}\n"
    )
    assert not find_unpinned_github(text), find_unpinned_github(text)
    mapping = "job:\n  container:\n    image: node:20@sha256:" + "c" * 64 + "\n"
    assert not find_unpinned_github(mapping), find_unpinned_github(mapping)


def test_declined_sibling_forms_remain_unflagged():
    # 1. Dockerfile FROM without digest (declined: base image tags are standard practice, high false-positive noise)
    assert not find_unpinned("FROM python:3.12\nFROM alpine:latest\n", "dockerfile")
    # 2. docker-compose image without digest (declined: local dev orchestration, not CI pipeline)
    compose = "services:\n  web:\n    image: nginx:alpine\n  db:\n    image: postgres:16\n"
    assert scan_pipeline(compose, "yaml", "docker-compose.yml")["counts"] == {"unpinned_install": 0}
    # 3. Kubernetes manifest image without digest (declined: deployment manifest, governed by cluster admission control)
    k8s = "apiVersion: apps/v1\nkind: Deployment\nspec:\n  template:\n    spec:\n      containers:\n      - image: myapp:v1\n"
    assert scan_pipeline(k8s, "yaml", "k8s/deployment.yml")["counts"] == {"unpinned_install": 0}


def test_gitlab_and_github_checks_scoped_by_file_path():
    text = "services:\n  db:\n    image: postgres:16\n"
    assert _surface_kinds(text, "yaml", gitlab=False) == []
    assert _surface_kinds(text, "yaml", gitlab=True) == ["gitlab-image"]
    assert (
        is_gitlab_ci(".gitlab-ci.yml")
        and is_gitlab_ci("ci/.gitlab-ci.yaml")
        and is_gitlab_ci("templates/gitlab/scan.yml")
    )
    assert is_github_workflow(".github/workflows/ci.yml") and is_github_workflow("action.yml")
    assert not is_gitlab_ci("docker-compose.yml") and not is_github_workflow("docker-compose.yml")
    assert scan_pipeline(text, "yaml", ".gitlab-ci.yml")["counts"] == {"unpinned_install": 1}
    assert scan_pipeline(text, "yaml", ".github/workflows/ci.yml")["counts"] == {"unpinned_install": 1}
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
    rel = path.relative_to(ROOT).as_posix()  # the table's keys are POSIX; str() gives backslashes on Windows
    got = {(n, k) for n, k, _ in find_unpinned(path.read_text())}
    assert got == OPEN_SYSTEM_PACKAGE_INSTALLS.get(rel, set()), got


OPEN_SYSTEM_PACKAGE_INSTALLS = {
    ".github/workflows/doom-rosetta.yml": {(129, "apt")},
    ".github/workflows/full-suite-gate.yml": {(160, "brew")},
    ".github/workflows/os-smoke-grid.yml": {(59, "brew")},
    ".github/workflows/tri-comparison-audit.yml": {(127, "apt")},
    ".github/workflows/tri-comparison-history.yml": {(135, "apt")},
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


def test_no_workflow_pins_a_python_below_requires_python():
    """#3322: a workflow leg on a Python under `requires-python` cannot install the package."""
    floor_text = re.search(r'^requires-python\s*=\s*">=(\d+\.\d+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    assert floor_text, "pyproject.toml has no requires-python >=X.Y"
    floor = tuple(int(p) for p in floor_text.group(1).split("."))
    offenders = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for m in re.finditer(r"python-version\"?\s*[:=]\s*\"?'?(\d+\.\d+)", path.read_text()):
            if tuple(int(p) for p in m.group(1).split(".")) < floor:
                offenders.append(f"{path.name}: {m.group(0)}")
    assert not offenders, offenders


def test_os_smoke_grid_setup_steps_have_their_own_timeout():
    """#5747: a hung macOS setup step must fail as that step, not as a bare job cancellation."""
    text = (ROOT / ".github" / "workflows" / "os-smoke-grid.yml").read_text()
    for step in ("Install macOS dependencies", "Install dependencies"):
        block = text.split(f"- name: {step}", 1)[1].split("\n      - name:", 1)[0]
        assert "timeout-minutes:" in block, step


def test_every_workflow_brew_step_has_a_timeout():
    """#5747: a hung `brew install` must fail as its own step, not as a bare job cancellation."""
    offenders = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = path.read_text()
        for step in re.split(r"\n\s*- (?=name:|uses:|run:)", text)[1:]:
            if "brew install" in step and "timeout-minutes:" not in step:
                offenders.append(f"{path.name}: {step.splitlines()[0]}")
    assert not offenders, offenders


def test_ci_retry_wraps_the_hashed_installs_of_the_two_os_grids():
    """#5747: the smoke grid and the full-suite gate install through ci_retry.sh, so a network flake is marked INFRASTRUCTURE."""
    for name in ("os-smoke-grid.yml", "full-suite-gate.yml"):
        lines = (ROOT / ".github" / "workflows" / name).read_text().splitlines()
        bare = [ln.strip() for ln in lines if "pip install --require-hashes" in ln and "ci_retry.sh" not in ln]
        assert not bare, (name, bare)


def test_every_workflow_brew_install_goes_through_ci_retry():
    """#5747: a flaky `brew install` is retried and marked INFRASTRUCTURE, not left to fail the leg."""
    lines = [
        f"{path.name}: {ln.strip()}"
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        for ln in path.read_text().splitlines()
        if "brew install" in ln and "ci_retry.sh" not in ln and not ln.lstrip().startswith("#")
    ]
    assert not lines, lines
