"""#7965 [c:fa6d44a0]: every GTEQ / GENERIC file READ of a burned program is recorded by its det port as the SPEC 6.2
READ event, so `recorded_file_events` no longer hides its RESP / RESP2 / length from the event comparison.

Burned programs issuing such a READ: ZECS000, ZECS003, genapp LGICVS01 and LGIPVS01 (the corpora's only ones; a
grep of the burned corpora for READ FILE ... GTEQ / GENERIC finds exactly these four). IBM, EXEC CICS READ: GTEQ /
GENERIC retrieve the first record whose (generic) key is equal or greater; the response is part of the command's
outcome, so a port that drops the event hides a wrong RESP (register X22)."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_filecontrol as fc  # noqa: E402

# case -> (corpus-relative source, number of GTEQ / GENERIC file READs in it)
CASES = {
    "zecs-zecs000": ("zecs/Source/ZECS000.cbl", 1),
    "zecs-zecs003": ("zecs/Source/ZECS003.cbl", 1),
    "genapp-lgicvs01": ("cics-genapp/base/src/lgicvs01.cbl", 1),
    "genapp-lgipvs01": ("cics-genapp/base/src/lgipvs01.cbl", 1),
}


def _corpora() -> Path:
    raw = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not raw or not Path(raw).is_dir():
        pytest.skip("GITGALAXY_MAINFRAME_CORPORA is not set to a corpus checkout")
    return Path(raw)


@pytest.fixture(scope="module")
def ports(tmp_path_factory):
    """One translate-only run of the four cases (no javac, no oracle)."""
    corpora = _corpora()
    if not all((corpora / src).is_file() for src, _ in CASES.values()):
        pytest.skip("a burned corpus is not checked out")
    work = tmp_path_factory.mktemp("gteq7965")
    env = {**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER", "PYTHONPATH": str(ROOT)}
    argv = [
        sys.executable,
        str(ROOT / "tests/tools/det_port.py"),
        "run",
        *CASES,
        "--translate-only",
        "--work",
        str(work),
    ]
    subprocess.run(argv, cwd=ROOT, check=True, capture_output=True, env=env)  # noqa: S603
    return {
        c: "\n".join(p.read_text(encoding="utf-8") for p in (work / c / "port").rglob("*Service*.java")) for c in CASES
    }


@pytest.mark.slow(reason="a det translation of four estate programs (about 9 s locally, slower on a CI runner)")
@pytest.mark.parametrize("case", sorted(CASES))
def test_each_gteq_read_of_a_burned_program_records_the_read_event(ports, case):
    java = ports[case]
    assert len(re.findall(r"task\.readSearchEvent\(", java)) == CASES[case][1]
    assert "task.readSearch(" not in java  # the event-free call is the one that hides the response


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_source_still_has_the_reads_the_count_assumes(case):
    src = (_corpora() / CASES[case][0]).read_text(encoding="latin-1")
    reads = re.findall(r"(?is)EXEC\s+CICS\s+READ\b(.*?)END-EXEC", src)
    assert sum(1 for r in reads if re.search(r"\b(GTEQ|GENERIC)\b", r)) == CASES[case][1]


def test_a_search_reads_differing_length_or_response_is_a_difference_not_hidden():
    """The port records the READ, so the COBOL one pairs with it and each field is compared (LENGERR vs NORMAL here)."""
    c = fc.cobol_file_event("READ", {"file": "KSDSCUST", "resp": "22", "resp2": "11", "length": "82"}, b"")
    j = {**c, "resp": "NORMAL"}
    j.pop("resp2")
    assert fc.recorded_file_events([c], [j]) == [c]
    diffs = ec.compare_events([c], [j])["diffs"]
    assert diffs and diffs[0]["fields"][0]["field"] == "resp"


def test_a_read_the_port_records_none_of_is_still_unpaired_so_later_events_keep_their_index():
    read = fc.cobol_file_event("READ", {"file": "F", "resp": "0"}, b"")
    other = {"event": "RETURN"}
    assert fc.recorded_file_events([read, other], [other]) == [other]
