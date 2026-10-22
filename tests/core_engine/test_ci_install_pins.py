"""#4918 step 3: no `pip install` of a named package without a pin or a hashed requirements file.

Covers every pipeline surface we own or ship: .github/workflows/*, templates/, action.yml and
bitbucket-pipelines.yml. Steps 1-2 put the pins in templates/requirements/ (shipped) and
ci/requirements/ (our own CI); this keeps them there.
"""

import posixpath
import re
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SURFACES = sorted(
    [
        *(ROOT / ".github" / "workflows").glob("*.yml"),
        *(ROOT / "templates").rglob("*.yml"),
        ROOT / "action.yml",
        ROOT / "bitbucket-pipelines.yml",
    ]
)
INSTALL = re.compile(r"\bpip3?\s+install\b")
BUILD = re.compile(r"\bpython3?\s+-m\s+build\b")
PINNED = re.compile(r"^[A-Za-z0-9_.\-]+(\[[^\]]+\])?==[^=<>!~]+$")
OPTS_WITH_VALUE = {
    "-r",
    "--requirement",
    "-c",
    "--constraint",
    "-e",
    "--editable",
    "-i",
    "--index-url",
    "--target",
    "-t",
}


def _logical_lines(text):
    """Shell-ish logical lines: backslash continuations joined, comments dropped, `&&`/`;` split."""
    out, cur = [], ""
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("#"):
            continue
        s = s.removeprefix("- ").strip()
        if s.endswith("\\"):
            cur += s[:-1] + " "
            continue
        out.append(cur + s)
        cur = ""
    for line in out:
        for part in re.split(r"&&|;|\|\|", line):
            yield part.strip()


def _is_local(spec):
    return (
        spec == "."
        or spec.startswith(("./", "../", "/"))
        or re.match(r"^\.?/?[\w./\-]*\[[\w,\-]+\]$", spec) is not None
    )


def classify(command):
    """None if `command` (one pip install invocation) is acceptable, else the reason."""
    try:
        toks = shlex.split(
            command.split("pip install", 1)[1] if "pip install" in command else command.split("pip3 install", 1)[1]
        )
    except ValueError:
        return "unparseable"
    if "--require-hashes" in toks:
        return None
    specs, reqfiles, i = [], [], 0
    while i < len(toks):
        t = toks[i]
        if t in OPTS_WITH_VALUE:
            if t in ("-r", "--requirement"):
                reqfiles.append(toks[i + 1] if i + 1 < len(toks) else "")
            if t in ("-e", "--editable"):
                specs.append(toks[i + 1] if i + 1 < len(toks) else "")
            i += 2
            continue
        if not t.startswith("-"):
            specs.append(t)
        i += 1
    for spec in specs:
        if _is_local(spec) or PINNED.match(spec) or re.match(r"^[\w\-.\[\],]+==\$\{\w+\}$", spec):
            continue
        return f"unpinned: {spec}"
    for rf in reqfiles:
        p = ROOT / rf
        if not p.is_file() or not _all_exact(p):
            return f"requirements file not exact-pinned: {rf}"
    if not specs and not reqfiles:
        return "no packages named"
    return None


def _all_exact(path):
    for line in path.read_text().splitlines():
        s = line.split("#")[0].strip()
        if s and not s.startswith("-") and "==" not in s:
            return False
    return True


def _local_specs(command):
    """The local-path specs (`.`, `./x`, `.[extra]`) one pip install invocation builds from source."""
    try:
        toks = shlex.split(
            command.split("pip install", 1)[1] if "pip install" in command else command.split("pip3 install", 1)[1]
        )
    except (ValueError, IndexError):
        return []
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in OPTS_WITH_VALUE:
            if t in ("-e", "--editable") and i + 1 < len(toks) and _is_local(toks[i + 1]):
                out.append(toks[i + 1])
            i += 2
            continue
        if not t.startswith("-") and _is_local(t):
            out.append(t)
        i += 1
    return out


def findings(text, isolated_builds=False):
    """(command, reason) for every unpinned install in a pipeline file's text.

    `isolated_builds=True` skips the build-isolation rule (workflows, pending the owner patch below).
    """
    has_hashed = "--require-hashes" in text
    has_bootstrap = "ci/requirements/bootstrap.txt" in text
    bad = []
    for cmd in _logical_lines(text):
        if BUILD.search(cmd):
            # `python -m build` isolates by default and fetches an unpinned setuptools / wheel (#4918).
            if "--no-isolation" not in cmd and not isolated_builds:
                bad.append((cmd, "build runs in an isolated env that fetches an unpinned backend: add --no-isolation"))
            continue
        if not INSTALL.search(cmd):
            continue
        reason = classify(cmd)
        if (
            reason is None
            and re.search(r"\[[\w,\-]+\]\"?$", cmd.split()[-1] if cmd.split() else "")
            and "-e" in cmd.split()
            and not has_hashed
        ):
            reason = "editable install with extras but no hashed install in this file"
        if reason is None and not isolated_builds and _local_specs(cmd):
            # Build isolation fetches an unhashed setuptools / setuptools_scm (#4918, #4944): build with the
            # hash-locked backend from bootstrap.txt instead.
            if "--no-build-isolation" not in cmd:
                reason = (
                    "local install builds in an isolated env that fetches an unpinned backend: add --no-build-isolation"
                )
            elif not has_bootstrap:
                reason = "--no-build-isolation without a hashed install of ci/requirements/bootstrap.txt in this file"
        if reason:
            bad.append((cmd, reason))
    return bad


@pytest.mark.parametrize("path", SURFACES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_unpinned_pip_install(path):
    in_workflows = path.parent == ROOT / ".github" / "workflows"
    bad = findings(path.read_text(), isolated_builds=in_workflows)
    assert not bad, "\n".join(f"{c}  <-- {r}" for c, r in bad)


@pytest.mark.parametrize("cmd", ["python -m build", "python3 -m build --wheel"])
def test_self_test_flags_isolated_build(cmd):
    assert [r for _, r in findings(cmd)], cmd
    assert not findings(cmd, isolated_builds=True)


def test_self_test_allows_unisolated_build():
    assert not findings("python -m build --no-isolation")


def test_workflows_build_without_isolation():
    bad = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        bad += [(path.name, c) for c, r in findings(path.read_text()) if "isolat" in r or "bootstrap" in r]
    assert not bad, bad


# -- the gate flags what it claims to flag ---------------------------------------------------------
@pytest.mark.parametrize(
    "cmd",
    [
        "pip install requests",
        'pip install "gitgalaxy[yaml]" tiktoken xgboost',
        "python -m pip install --upgrade pip",
        "pip install pytest>=8",
        "pip3 install tree-sitter-language-pack",
        'pip install "mkdocs<2.0" mkdocs-material',
        "pip install -r some-unpinned.txt",
        "pip install -r requirements.txt",
        "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi",
    ],
)
def test_self_test_flags_unpinned(cmd):
    assert findings(cmd), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "pip install --require-hashes -r ci/requirements/engines.txt",
        'pip install "ruff==0.16.0"',
        "pip install --no-build-isolation -e .",
        "pip install --no-build-isolation ./gitgalaxy-baseline",
        "pip install --no-build-isolation -e ./main",
        'pip install "gitgalaxy[${SET}]==${GALAXY_ACT_VERSION}"',
        "pip install --require-hashes -r ci/requirements/mypy.txt",
    ],
)
def test_self_test_allows_pinned(cmd):
    assert not findings("pip install --require-hashes -r ci/requirements/bootstrap.txt\n" + cmd), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "pip install -e .",
        'pip install -e ".[full]"',
        "pip install -e ./gitgalaxy",
        'pip install -e "./gitgalaxy[translator]"',
        "pip install -e ./main",
        "pip install ./gitgalaxy-baseline",
        "pip install .",
        "pip install --require-hashes -r ci/requirements/pytest.txt && pip install -e ./gitgalaxy",
    ],
)
def test_self_test_flags_isolated_local_build(cmd):
    """Every local-install form is flagged without --no-build-isolation, hashed deps or not."""
    reasons = [r for _, r in findings("pip install --require-hashes -r ci/requirements/bootstrap.txt\n" + cmd)]
    assert any("--no-build-isolation" in r for r in reasons), cmd


def test_no_build_isolation_needs_the_bootstrap_lockfile():
    assert findings("pip install --no-build-isolation -e .")
    assert not findings(
        "pip install --require-hashes -r ci/requirements/bootstrap.txt\npip install --no-build-isolation -e ."
    )


def test_bootstrap_lockfile_carries_the_build_backend():
    txt = (ROOT / "ci" / "requirements" / "bootstrap.txt").read_text().lower()
    for pkg in ("setuptools==", "setuptools-scm=="):
        assert pkg in txt, pkg


def test_mypy_audit_toolchain_is_hash_locked():
    assert (ROOT / "ci" / "requirements" / "mypy.txt").is_file()
    # tests/requirements-mypy.txt is still what mypy-audit.yml reads until the owner applies the workflow patch


def test_self_test_extras_editable_needs_a_hashed_install():
    assert findings('pip install --no-build-isolation -e ".[translator]"')
    assert not findings(
        "pip install --require-hashes -r ci/requirements/bootstrap.txt\n"
        "pip install --require-hashes -r ci/requirements/treesitter.txt\n"
        'pip install --no-build-isolation -e ".[translator]"'
    )


def test_continuation_lines_are_joined():
    assert findings("pip install \\\n  requests")


# -- the shared lockfiles themselves ---------------------------------------------------------------
@pytest.mark.parametrize("txt", sorted((ROOT / "ci" / "requirements").glob("*.txt")), ids=lambda p: p.stem)
def test_ci_lockfiles_are_hashed_and_have_a_source(txt):
    assert txt.with_suffix(".in").is_file(), "lockfile without its .in source"
    blocks = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", txt.read_text())[1:]
    assert blocks
    for b in blocks:
        assert "--hash=sha256:" in b, b.splitlines()[0]


@pytest.mark.parametrize("txt", sorted((ROOT / "ci" / "requirements").glob("*.txt")), ids=lambda p: p.stem)
def test_ci_lockfiles_preserve_multiversion_markers(txt):
    """Packages with version splits across Python >= 3.10 (e.g. numpy) must retain environment markers."""
    from tests.tools.pin_requirements import verify_multiversion_markers

    errors = verify_multiversion_markers(txt, txt.read_text())
    assert not errors, "\n".join(errors)


def test_dependabot_watches_the_ci_lockfiles():
    cfg = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())
    ci_entry = next(u for u in cfg["updates"] if u.get("directory") == "/ci/requirements")
    assert ci_entry["package-ecosystem"] == "pip"
    # Ensure multiversion packages that dependabot collapses are ignored
    ignored = {ig["dependency-name"] for ig in ci_entry.get("ignore", [])}
    assert {"numpy", "xgboost"}.issubset(ignored)


# -- every `-r <path>/ci/requirements/x.txt` resolves from where the step runs ---------------------
def _steps(path):
    doc = yaml.safe_load(path.read_text())
    for job in (doc.get("jobs") or {}).values():
        steps = job.get("steps") or []
        checkouts = set()  # this repo's own checkout dirs (a rosetta job also checks out a baseline ref)
        for st in steps:
            w = st.get("with") or {}
            if str(st.get("uses", "")).startswith("actions/checkout") and "repository" not in w and w.get("path"):
                checkouts.add(w["path"])
            yield checkouts, st.get("run")


@pytest.mark.parametrize("path", sorted((ROOT / ".github" / "workflows").glob("*.yml")), ids=lambda p: p.name)
def test_workflow_lockfile_paths_resolve(path):
    """Resolved from the step's working directory, the path must land in THIS repo's checkout dir."""
    for checkouts, run in _steps(path):
        if not run:
            continue
        cwd = ""
        for line in run.splitlines():
            s = line.strip()
            m = re.match(r"cd (\S+)$", s)
            if m:
                cwd = posixpath.join(cwd, m.group(1))
            for ref in re.findall(r"-r (\S*ci/requirements/\S+\.txt)", s):
                if "${{" in ref:
                    continue
                at = posixpath.normpath(posixpath.join(cwd, ref))
                want = {posixpath.normpath(posixpath.join(c, "ci/requirements")) for c in checkouts or {""}}
                assert posixpath.dirname(at) in want, (
                    f"{path.name}: {ref} from '{cwd}' is {at}, repo checkouts are {checkouts}"
                )
                assert (ROOT / "ci" / "requirements" / posixpath.basename(at)).is_file()
