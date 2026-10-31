"""#4767: the zECS programs that use EXEC CICS WEB have an equivalence case that STATES the HTTP peer, and a proven record.

Server side (ZECS001) states the inbound request (`http_request`); the client side (ECS001, ZECS000, ZECS003) states the
peers it talks to (`http_peers`). JSON-only checks: the stated facts are present and each record is a proven det-sweep
record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CASES = Path(__file__).resolve().parents[1] / "equivalence"

SERVER = ["zecs-zecs001"]
CLIENTS = ["zecs-ecs001", "zecs-zecs000", "zecs-zecs003"]


def _json(name, leaf):
    return json.loads((CASES / name / leaf).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SERVER)
def test_the_server_case_states_an_inbound_request_in_most_scenarios(name):
    scenarios = _json(name, "case.json")["scenarios"]
    stated = [s for s in scenarios if s.get("http_request")]
    assert stated
    assert len(stated) * 2 > len(scenarios)
    for s in stated:
        assert s["http_request"].get("method")


@pytest.mark.parametrize("name", CLIENTS)
def test_the_client_case_states_the_peers_it_talks_to(name):
    scenarios = _json(name, "case.json")["scenarios"]
    assert any(s.get("http_peers") for s in scenarios)


@pytest.mark.parametrize("name", SERVER + CLIENTS)
def test_the_record_is_a_proven_det_sweep_record(name):
    proof = _json(name, "evidence.json")["proof"]
    assert proof["verdict"] == "proven"
    assert proof["source"] == "det-sweep"
    assert proof["runs"] >= 1
    assert not proof["java_failed"]
