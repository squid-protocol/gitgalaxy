"""#4918 step 1: the shipped CI surface installs only hash-pinned requirements."""

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


@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_unpinned_pip_install(path):
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if "pip install" not in stripped or stripped.startswith("#"):
            continue
        ok = (
            "--require-hashes" in stripped
            or "-e " in stripped  # local dogfood source
            or "==${" in stripped  # explicit caller-chosen exact version
        )
        assert ok, f"{path.name}: unpinned install: {stripped}"
