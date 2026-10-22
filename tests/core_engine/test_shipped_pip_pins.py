"""#4918 step 1: the shipped CI surface installs only hash-pinned requirements."""

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQS = ROOT / "templates" / "requirements"
SHIPPED = [
    ROOT / "action.yml",
    ROOT / "templates" / "scan.yml",
    ROOT / "templates" / "github" / "gitgalaxy-pipeline.yml",
    ROOT / "templates" / "gitlab" / "scan.yml",
    ROOT / "templates" / "azure" / "azure-pipelines.yml",
    ROOT / "templates" / "bitbucket" / "bitbucket-pipelines.yml",
]


@pytest.mark.parametrize("name", ["core", "yaml", "full"])
def test_requirements_are_exact_and_hashed(name):
    text = (REQS / f"{name}.txt").read_text()
    entries = re.findall(r"^([A-Za-z0-9_.\-]+)(==\S+)", text, re.M)
    assert entries, name
    # every requirement line carries at least one hash continuation
    blocks = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", text)
    for block in blocks[1:]:
        assert "--hash=sha256:" in block, block.splitlines()[0]
    assert "gitgalaxy==" in text


def test_pins_agree_across_sets():
    pins = {
        n: re.search(r"^gitgalaxy==(\S+)", (REQS / f"{n}.txt").read_text(), re.M).group(1)
        for n in ("core", "yaml", "full")
    }
    assert len(set(pins.values())) == 1, pins


TEMPLATES = [p for p in SHIPPED if p.name != "action.yml"]
FETCHED = "/tmp/gg-requirements.txt"
MARKER = re.compile(r"GG_REF=([0-9a-f]{40}) GG_SHA256=([0-9a-f]{64}) # gg-pin:(core|yaml|full)")


def _install_lines(path):
    for i, line in enumerate(path.read_text().splitlines()):
        s = line.strip()
        if "pip install" in s and not s.startswith("#"):
            yield i, s


@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_unpinned_pip_install(path):
    for _, s in _install_lines(path):
        ok = (
            "--require-hashes" in s
            or "-e " in s  # local dogfood source
            or "==${" in s  # explicit caller-chosen exact version
        )
        assert ok, f"{path.name}: unpinned install: {s}"


def test_action_reads_lockfiles_from_its_own_checkout():
    text = (ROOT / "action.yml").read_text()
    assert "${GITHUB_ACTION_PATH}/templates/requirements" in text
    assert (REQS / "full.txt").is_file() and (REQS / "yaml.txt").is_file()


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: str(p.relative_to(ROOT)))
def test_template_fetches_lockfile_from_immutable_source(path):
    """A template runs in a customer repo (or a remote component): it must not read the workspace."""
    lines = path.read_text().splitlines()
    assert "-r templates/requirements" not in path.read_text(), "installs from a path the customer does not have"
    # the `version: local` dogfood branch runs in THIS repo's workspace, so it reads the bootstrap set from it
    installs = [
        i for i, s in _install_lines(path) if "--require-hashes" in s and "ci/requirements/bootstrap.txt" not in s
    ]
    assert installs, path.name
    for i in installs:
        assert f"-r {FETCHED}" in lines[i], lines[i]
        # the same step, before the install: marker, download from a pinned raw URL, sha256 check
        window = "\n".join(lines[max(0, i - 12) : i])
        assert MARKER.search(window), f"{path.name}:{i + 1} no gg-pin marker before install"
        assert "raw.githubusercontent.com/squid-protocol/gitgalaxy/${GG_REF}/templates/requirements/" in window
        assert f"sha256sum -c -" in window and window.index("urlretrieve") < window.index("sha256sum -c")


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: str(p.relative_to(ROOT)))
def test_markers_match_committed_lockfiles(path):
    markers = MARKER.findall(path.read_text())
    assert markers, path.name
    for ref, sha, name in markers:
        assert ref != "0" * 40 and sha != "0" * 64, "unstamped marker: run tests/tools/stamp_template_pins.py"
        assert sha == hashlib.sha256((REQS / f"{name}.txt").read_bytes().replace(b"\r\n", b"\n")).hexdigest(), (
            f"{path.name}: gg-pin:{name} stale; run tests/tools/stamp_template_pins.py"
        )
    assert len({ref for ref, _, _ in markers}) == 1


def test_all_templates_share_one_ref():
    refs = {m[0] for p in TEMPLATES for m in MARKER.findall(p.read_text())}
    assert len(refs) == 1, refs
