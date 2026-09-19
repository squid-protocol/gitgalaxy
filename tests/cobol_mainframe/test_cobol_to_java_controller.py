"""#3221: the Java tree must hold one class per clean-room output key.

The clean room keys its outputs per path -- a program's stem when unique, else
the flattened path (#3218). The Java forges used to re-derive their names from
the IR's `metadata.file_name` and a schema's `title`, neither of which is
unique, so same-stemmed programs (and every CICS program's DFHCOMMAREA) wrote
the same file and the later one silently won.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import (
    java_class_base,
    java_url_segment,
    output_key,
)

# Two programs that share the stem SAM2, plus one that does not -- the
# zopeneditor-sample layout, reduced.
KEYS = ("COBOL__SAM2", "multiroot__sam__SAM2", "SAM1LIB")


def _ir(key: str) -> dict:
    return {
        "metadata": {"file_name": f"{key.split('__')[-1]}.cbl"},
        "analysis": {
            "lineage": {"inputs": ["DDIN"], "outputs": [], "unresolved_calls": []},
            "base_intent": {"files_requested": [{"internal": "F-IN", "dd_name": "DDIN"}], "is_cics": False},
        },
    }


def _schema(title: str) -> dict:
    return {"title": title, "properties": {"CUST-ID": {"type": "string", "description": "PIC X(8)"}}}


@pytest.fixture
def clean_room(tmp_path):
    """A staging directory holding one IR dump and one schema per key. Every
    schema carries the SAME title, which is what CICS repositories look like."""
    room = tmp_path / "sample_gitgalaxy_clean_20260919"
    (room / "04_ir_state_dumps").mkdir(parents=True)
    (room / "02_cloud_schemas").mkdir(parents=True)
    (room / "05_microservice_slices").mkdir(parents=True)
    for key in KEYS:
        (room / "04_ir_state_dumps" / f"{key}_ir.json").write_text(json.dumps(_ir(key)), encoding="utf-8")
        (room / "02_cloud_schemas" / f"{key}_schema.json").write_text(
            json.dumps(_schema("DFHCOMMAREA")), encoding="utf-8"
        )
        (room / "05_microservice_slices" / f"{key}_slice.json").write_text(
            json.dumps({"program_id": key, "paragraphs": []}), encoding="utf-8"
        )
    return room


def _run(clean_room):
    with patch.object(sys, "argv", ["cobol_to_java_controller.py", str(clean_room), "--header", "no-such-header"]):
        java_controller.main()
    return clean_room.parent / clean_room.name.replace("clean", "java_spring")


def test_same_name_programs_get_their_own_service_and_controller(clean_room):
    java = _run(clean_room)
    pkg = java / "src/main/java/com/gitgalaxy/modernized"

    services = sorted(p.name for p in (pkg / "service").glob("*.java"))
    controllers = sorted(p.name for p in (pkg / "controller").glob("*.java"))

    assert services == ["CobolSam2Service.java", "MultirootSamSam2Service.java", "Sam1libService.java"]
    assert controllers == ["CobolSam2Controller.java", "MultirootSamSam2Controller.java", "Sam1libController.java"]


def test_each_controller_gets_its_own_request_mapping(clean_room):
    """Spring refuses to start on an ambiguous mapping, so the URL is keyed too."""
    java = _run(clean_room)
    ctrl_dir = java / "src/main/java/com/gitgalaxy/modernized/controller"

    mappings = sorted(
        line.strip()
        for p in ctrl_dir.glob("*.java")
        for line in p.read_text(encoding="utf-8").splitlines()
        if "@RequestMapping" in line
    )

    assert mappings == [
        '@RequestMapping("/api/v1/cobol-sam2")',
        '@RequestMapping("/api/v1/multiroot-sam-sam2")',
        '@RequestMapping("/api/v1/sam1lib")',
    ]


def test_one_entity_per_schema_even_when_every_title_is_dfhcommarea(clean_room):
    """CBSA has 29 schemas and three distinct titles; before this, three entities."""
    java = _run(clean_room)
    entity_dir = java / "src/main/java/com/gitgalaxy/modernized/entity"

    assert sorted(p.name for p in entity_dir.glob("*.java")) == [
        "CobolSam2Dfhcommarea.java",
        "MultirootSamSam2Dfhcommarea.java",
        "Sam1libDfhcommarea.java",
    ]
    # The class is disambiguated; the legacy record it maps is not renamed.
    for path in entity_dir.glob("*.java"):
        assert '@Table(name = "DFHCOMMAREA")' in path.read_text(encoding="utf-8")


def test_agent_job_keys_survive_a_flattened_key(clean_room):
    """`slice_file.name.split("_")[0]` returned COBOL for COBOL__SAM2_slice.json,
    so two programs shared one job file and neither resolved its IR."""
    java = _run(clean_room)

    assert sorted(p.name for p in (java / "ai_agent_jobs").glob("*.json")) == [
        "COBOL__SAM2_java_service_job.json",
        "SAM1LIB_java_service_job.json",
        "multiroot__sam__SAM2_java_service_job.json",
    ]


@pytest.mark.parametrize(
    "key, expected_class, expected_url",
    [
        ("SAM1LIB", "Sam1lib", "sam1lib"),
        ("BNK1CAC", "Bnk1cac", "bnk1cac"),
        ("COBOL__SAM2", "CobolSam2", "cobol-sam2"),
        ("multiroot__sam__SAM2", "MultirootSamSam2", "multiroot-sam-sam2"),
        ("PAYROLL-PROCESSOR", "PayrollProcessor", "payroll-processor"),
    ],
)
def test_a_plain_stem_keeps_the_name_it_already_had(key, expected_class, expected_url):
    """Only a genuinely colliding program is renamed: for a unique stem the key IS
    the stem, and the derivation matches the old `word.capitalize()` join."""
    assert java_class_base(key) == expected_class
    assert java_url_segment(key) == expected_url


@pytest.mark.parametrize(
    "name, suffix, expected",
    [
        ("COBOL__SAM2_ir.json", "_ir", "COBOL__SAM2"),
        ("SAM1LIB_schema.json", "_schema", "SAM1LIB"),
        ("BNK1CAC_schema.sql", "_schema", "BNK1CAC"),
        ("multiroot__sam__SAM2_slice.json", "_slice", "multiroot__sam__SAM2"),
    ],
)
def test_output_key_strips_the_artifact_tag_not_the_first_underscore(name, suffix, expected):
    assert output_key(Path(name), suffix) == expected
