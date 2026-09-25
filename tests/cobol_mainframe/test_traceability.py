import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import TraceLog


def test_tracelog_records_facts_and_todos():
    trace = TraceLog()
    facts = [
        {
            "source": "COACTUPC.cbl:42",
            "section": "uow_handlers",
            "ledger_field": "uow_handlers",
            "field_testing": "untested",
        }
    ]
    todos = ["TODO: map something"]

    trace.record(
        "com/gitgalaxy/modernized/service/CoactupcService.java",
        "CoactupcService#commitPointL42",
        "commit",
        facts,
        todos,
    )

    gen_from = {"gitgalaxy_commit": "test-hash"}
    d = trace.as_dict(gen_from)
    assert d["generated_from"] == gen_from
    assert len(d["artifacts"]) == 1

    entry = d["artifacts"][0]
    assert entry["file"] == "com/gitgalaxy/modernized/service/CoactupcService.java"
    assert entry["symbol"] == "CoactupcService#commitPointL42"
    assert entry["kind"] == "commit"
    assert entry["facts"] == facts
    assert entry["todos"] == todos


def _ir(key: str) -> dict:
    return {
        "metadata": {"file_name": f"{key.split('__')[-1]}.cbl"},
        "analysis": {
            "lineage": {"inputs": ["DDIN"], "outputs": [], "unresolved_calls": []},
            "base_intent": {"files_requested": [{"internal": "F-IN", "dd_name": "DDIN"}], "is_cics": True},
        },
    }


def _schema(title: str) -> dict:
    return {"title": title, "properties": {"CUST-ID": {"type": "string", "description": "PIC X(8)"}}}


@pytest.fixture
def clean_room(tmp_path):
    room = tmp_path / "sample_gitgalaxy_clean_20260919"
    (room / "04_ir_state_dumps").mkdir(parents=True)
    (room / "02_cloud_schemas").mkdir(parents=True)
    (room / "05_microservice_slices").mkdir(parents=True)
    (room / "06_skeleton").mkdir(parents=True)
    key = "SAM1LIB"
    (room / "04_ir_state_dumps" / f"{key}_ir.json").write_text(json.dumps(_ir(key)), encoding="utf-8")
    (room / "02_cloud_schemas" / f"{key}_schema.json").write_text(json.dumps(_schema("DFHCOMMAREA")), encoding="utf-8")
    (room / "05_microservice_slices" / f"{key}_slice.json").write_text(
        json.dumps({"program_id": key, "paragraphs": [], "tested_on_public": 1, "tested_on_private": 0}),
        encoding="utf-8",
    )
    # A tiny skeleton file
    skeleton = {
        "program": {"file": "SAM1LIB.cbl", "language": "cobol"},
        "sections": {
            "uow_handlers": {
                "ledger_field": "uow_handlers",
                "facts": [{"kind": "ROLLBACK", "line": 42, "verb": "SYNCPOINT"}],
                "field_testing": {"ledger_matches": 0, "verified_on": [], "status": "untested"},
                "tested_on_public": 1,
                "tested_on_private": 0,
            }
        },
    }
    (room / "06_skeleton" / f"{key}_skeleton.json").write_text(json.dumps(skeleton), encoding="utf-8")
    return room


def test_traceability_json_generated(clean_room):
    with patch.object(sys, "argv", ["cobol_to_java_controller.py", str(clean_room), "--header", "no-such-header"]):
        java_controller.main()

    java = clean_room.parent / clean_room.name.replace("clean", "java_spring")
    traceability_file = java / "traceability.json"

    assert traceability_file.exists()
    data = json.loads(traceability_file.read_text(encoding="utf-8"))

    assert "generated_from" in data
    assert "artifacts" in data
    assert len(data["artifacts"]) > 0
