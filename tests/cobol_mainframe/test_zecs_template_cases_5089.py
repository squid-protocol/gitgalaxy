"""#5089 / #4771: the zECS cases state the instance a run-time ZC##FILE / ZC##KEY name resolves to.

ZECS000 READs ZC##FILE with GTEQ and ZECS003 DELETEs by key in ZC##KEY and ZC##FILE (GENERIC); the file names are data
items built from the transaction id, so each case states the install instance (ID 01) and seeds the resolved datasets,
and carries the scenarios that reach those file operations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CASES = Path(__file__).resolve().parents[1] / "equivalence"

RUN_TIME_NAMED = {
    "zecs-zecs000": {"ZECS.ZC01FILE.TEST", "ZECS.ZC01KEY.TEST"},
    "zecs-zecs003": {"ZECS.ZC01FILE.TEST", "ZECS.ZC01KEY.TEST"},
}
SCENARIOS = {
    "zecs-zecs000": {"resume-empty-file", "resume-fresh-record", "resume-expired-peer-201"},
    "zecs-zecs003": {"expired-record-deleted", "fresh-record-kept", "expired-record-without-key-record"},
}


def _case(name):
    return json.loads((CASES / name / "case.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(RUN_TIME_NAMED))
def test_the_case_states_the_install_instance_and_seeds_the_resolved_datasets(name):
    case = _case(name)
    assert case["install_symbols"]["values"]["ID"] == "01"
    assert case["install_symbols"]["why"]
    assert RUN_TIME_NAMED[name] <= set(case["datasets"])


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_case_runs_the_scenarios_that_reach_the_run_time_named_files(name):
    assert SCENARIOS[name] <= {s["name"] for s in _case(name)["scenarios"]}
