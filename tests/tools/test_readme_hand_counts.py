"""#5282: README counts that the code defines are checked against it, and a measured timing is labelled a dated single run."""

import re
from pathlib import Path

import pytest

from gitgalaxy.tools.readiness import era_tags

REPO = Path(__file__).resolve().parents[2]
READINESS = REPO / "gitgalaxy" / "tools" / "readiness" / "README.md"
TIMING_PAGES = ("gitgalaxy/README.md", "gitgalaxy/tools/supply_chain_security/README.md")
TIMING = re.compile(r"\d[\d,.]*\s*(?:seconds|files per second|files/sec|LOC/s)", re.IGNORECASE)
LABEL = re.compile(r"Single run, measured \d{4}-\d{2}-\d{2}")
TELL_COUNT = re.compile(r"\b(\d+)\s+(?:syntactic\s+)?(?:tells|constructs)\b")
ERA_COUNT = re.compile(r"\b(\d+)\s+eras\b")


def _prose(path):
    """Text outside <details> blocks and fenced code (a ``` or ~~~ fence)."""
    text = (REPO / path).read_text(encoding="utf-8")
    text = re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)
    return re.sub(r"^(```|~~~).*?^\1", "", text, flags=re.DOTALL | re.MULTILINE)


def test_readiness_tell_count_matches_the_code():
    counts = [int(m.group(1)) for m in TELL_COUNT.finditer(READINESS.read_text(encoding="utf-8"))]
    assert counts, "the readiness README no longer states a tell count; update this guard"
    assert set(counts) == {len(era_tags.TELLS)}, f"README says {sorted(set(counts))}, TELLS has {len(era_tags.TELLS)}"


def test_readiness_era_count_matches_the_code():
    counts = [int(m.group(1)) for m in ERA_COUNT.finditer(READINESS.read_text(encoding="utf-8"))]
    assert counts, "the readiness README no longer states an era count; update this guard"
    assert set(counts) == {len(era_tags.ERAS)}


def test_readiness_readme_names_every_tell():
    text = READINESS.read_text(encoding="utf-8")
    missing = [t[0] for t in era_tags.TELLS if f"`{t[0]}`" not in text]
    assert not missing, f"tells absent from the readiness README era table: {missing}"


@pytest.mark.parametrize("page", TIMING_PAGES)
def test_measured_timings_are_labelled_single_runs(page):
    paragraphs = re.split(r"\n\s*\n", _prose(page))
    timed = [p for p in paragraphs if TIMING.search(p)]
    assert timed, f"{page}: no timing paragraph found; update this guard"
    unlabelled = [p.strip()[:80] for p in timed if not LABEL.search(p)]
    assert not unlabelled, f"{page}: timing without a 'Single run, measured <date>' label: {unlabelled}"


# ---- the non-CICS hero tiles (#5282) ----------------------------------------------------------------------------------

README = REPO / "README.md"


def _tile(text_start):
    tiles = re.findall(r"<td[^>]*>.*?</td>", README.read_text(encoding="utf-8"), flags=re.S)
    return next(t for t in tiles if text_start in t)


def _registry_counts():
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    split = {n for n, d in LANGUAGE_DEFINITIONS.items() if d.get("rules", {}).get("func_start")}
    return set(LANGUAGE_DEFINITIONS), split


def test_language_tile_and_table_follow_the_registry():
    registry, split = _registry_counts()
    text = README.read_text(encoding="utf-8")
    assert f"<h2>{len(split)}</h2>" in text
    assert f"{len(registry)} recognized" in _tile("languages, down to the function")
    assert f"Languages: {len(registry)} recognized, {len(split)} read down to the function" in text
    rows = re.findall(r"^\| \*\*(.*?)\*\*.*?\| (\d+) \| (.*) \|$", text, re.M)
    listed = {label: set(re.findall(r"`([^`]+)`", names)) for label, _, names in rows}
    assert listed["Split into functions"] == split
    assert set().union(*listed.values()) == registry


@pytest.mark.parametrize("start", ["to scan Kubernetes", "validated function precision"])
def test_measured_tiles_carry_a_date_and_a_source_link(start):
    tile = _tile(start)
    assert re.search(r"\b\d{4}-\d{2}-\d{2}\b", tile), f"{start}: a measured tile needs its date"
    assert "href=" in tile.split("<br />", 1)[1], f"{start}: a measured tile needs a source link"


def test_speed_section_is_a_labelled_single_run():
    section = re.search(r"## Every size, in seconds.*?\n---", README.read_text(encoding="utf-8"), re.S).group(0)
    assert LABEL.search(section), "the Kubernetes timing needs a 'Single run, measured <date>' label"
    assert "gitgalaxy-raw-output" in section
