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


# ---- undated counts of repo facts (#7626) -----------------------------------------------------------------------------

VECTORS = REPO / "docs" / "vectors.md"
VECTOR_COUNT = re.compile(r"\b(\d+)(?: per-file vectors\b|-vector Structural Surface Profile)")


def _vector_names():
    section = VECTORS.read_text(encoding="utf-8").split("## The name table", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\| `(\w+)` \|", section, re.M)


@pytest.mark.parametrize(
    "page",
    [
        "README.md",
        "docs/vectors.md",
        "gitgalaxy/README.md",
        "gitgalaxy/metrics/README.md",
        "gitgalaxy/recorders/README.md",
    ],
)
def test_per_file_vector_count_matches_the_name_table(page):
    counts = {int(n) for n in VECTOR_COUNT.findall((REPO / page).read_text(encoding="utf-8"))}
    assert counts, f"{page} no longer states the vector count; update this guard"
    assert counts == {len(_vector_names())}


def test_corpus_counts_in_readme_and_contributing_are_dated():
    """The sibling corpora's sizes live in other repos: a count of them is a snapshot and needs its date."""
    pattern = re.compile(r"\b(?:56|10)\b[- ](?:languages|language|COBOL repos)|~80\b|COBOL repos \(10\b")
    for page in ("README.md", "CONTRIBUTING.md"):
        for line in (REPO / page).read_text(encoding="utf-8").splitlines():
            if pattern.search(line):
                assert re.search(r"\d{4}-\d{2}-\d{2}", line), f"{page}: undated corpus count: {line[:90]}"


def test_package_readme_signal_and_threat_counts_match_the_code():
    from gitgalaxy.metrics.signal_processor import SignalProcessor
    from gitgalaxy.security.security_lens import SecurityLens

    text = (REPO / "gitgalaxy" / "README.md").read_text(encoding="utf-8")
    assert f"{len(SignalProcessor.SIGNAL_SCHEMA)}-signal structural schema" in text
    text = (REPO / "gitgalaxy" / "security" / "README.md").read_text(encoding="utf-8")
    assert f"detect {len(SecurityLens().THREAT_SIGNATURES)} signature categories" in text


def test_package_readme_tuning_and_language_counts_are_dated():
    """Variable counts and the language-file count move with every config or language PR: a snapshot needs its date."""
    pattern = re.compile(r"\b(?:300|175|75|50|35|15)\+|\(71\b|over 1,000 repositories|~71,000|checked \d")
    pages = ("gitgalaxy/README.md", "gitgalaxy/core/README.md", "gitgalaxy/standards/README.md")
    for page in pages:
        for line in (REPO / page).read_text(encoding="utf-8").splitlines():
            for m in pattern.finditer(line):
                assert re.search(r"\d{4}-\d{2}-\d{2}", line[m.start() :]), f"{page}: undated count: {line[:90]}"


@pytest.mark.parametrize(
    ("page", "pattern"),
    [
        ("tests/README.md", r"~\d+ real subdirectories|\d+ test files"),
        ("CLAUDE.md", r"pool of ~\d+ concurrent runners"),
    ],
)
def test_snapshot_counts_in_tests_readme_and_claude_md_are_dated(page, pattern):
    """A count of an external corpus, a CI pool or the test tree is a snapshot and carries its date (#7626)."""
    found = [m for m in re.finditer(pattern, (REPO / page).read_text(encoding="utf-8"))]
    assert found, f"{page} no longer states this count; update this guard"
    text = (REPO / page).read_text(encoding="utf-8")
    for m in found:
        assert re.search(r"\d{4}-\d{2}-\d{2}", text[m.start() : m.end() + 160]), f"{page}: undated count: {m.group(0)}"


def test_wiki_and_network_auditing_counts_match_the_code():
    """#7626 slice 4: the registry, signal and framework-profile counts quoted in docs/wiki/01-* and the network-audit README."""
    from gitgalaxy.metrics.signal_processor import SignalProcessor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    from gitgalaxy.tools.network_auditing.full_api_network_map import FRAMEWORK_SIGNATURES

    rag = (REPO / "docs" / "wiki" / "01-06-the-structural-rag-graph.md").read_text(encoding="utf-8")
    overview = (REPO / "docs" / "wiki" / "01-01-project-overview.md").read_text(encoding="utf-8")
    n_sig, n_lang = len(SignalProcessor.SIGNAL_SCHEMA), len(LANGUAGE_DEFINITIONS)
    n_ext = len({e for d in LANGUAGE_DEFINITIONS.values() for e in d.get("extensions") or []})
    assert f"{n_sig}-signal" in rag
    assert f"{n_lang} languages" in overview and f"{n_ext} file extensions" in overview
    for text in (rag, overview):
        for m in re.finditer(rf"\b{n_lang} (?:registered )?languages|\b{n_ext} file extensions", text):
            assert re.search(r"as of \d{4}-\d{2}-\d{2}", text[m.start() : m.end() + 80]), f"undated: {m.group(0)}"
    readme = (REPO / "gitgalaxy" / "tools" / "network_auditing" / "README.md").read_text(encoding="utf-8")
    names = {n.split(" (")[0] for n in FRAMEWORK_SIGNATURES}
    assert "nine framework profiles" in readme and len(FRAMEWORK_SIGNATURES) == 9
    assert "eight languages" in readme and len(names) == 8  # two C# profiles share one language
