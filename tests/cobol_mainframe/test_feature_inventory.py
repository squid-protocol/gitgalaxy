"""#4723 feature inventory: per-category synthetic snippets, determinism, the schema, and the committed fixtures."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det parser; the ground-truth CI job has no translator extra

from tests.tools.feature_inventory import SCHEMA_FILE, TOOLS, scan_estate  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", TOOLS.parents[1] / ".mainframe_corpora"))


def run_snippet(tmp_path, code):
    d = tmp_path / "estate"
    d.mkdir(parents=True, exist_ok=True)
    (d / "prog.cbl").write_text(code)
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return scan_estate(d, db_dir)


def test_determinism(tmp_path):
    code = "       ID DIVISION.\n       PROGRAM-ID. PROG.\n       PROCEDURE DIVISION.\n           GOBACK.\n"
    d = tmp_path / "estate"
    d.mkdir(parents=True, exist_ok=True)
    (d / "prog.cbl").write_text(code)
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    inv1 = scan_estate(d, db_dir)
    inv2 = scan_estate(d, db_dir)
    assert json.dumps(inv1, sort_keys=True) == json.dumps(inv2, sort_keys=True)  # noqa: S101


def test_statements(tmp_path):
    code = "       ID DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01 X PIC 9.\n       PROCEDURE DIVISION.\n           ADD 1 TO X.\n           GOBACK.\n"
    inv = run_snippet(tmp_path, code)
    assert "ARITH" in inv["statements"]  # noqa: S101
    assert "GOBACK" in inv["statements"]  # noqa: S101


def test_data_types(tmp_path):
    code = """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC S9(4) COMP-3.
       01 V2 PIC 99PP.
       01 V3 PIC $$$,$$$.99.
       01 V4 USAGE COMP-1.
       01 V5 USAGE COMP-2.
       01 V6 PIC N(10) USAGE NATIONAL.
       PROCEDURE DIVISION.
           GOBACK.
"""
    inv = run_snippet(tmp_path, code)
    assert "PACKED" in inv["data_types"]  # noqa: S101
    assert "P-SCALED" in inv["data_types"]  # noqa: S101
    assert "EDITED" in inv["data_types"]  # noqa: S101
    assert "COMP-1" in inv["data_types"]  # noqa: S101
    assert "COMP-2" in inv["data_types"]  # noqa: S101
    assert "NATIONAL" in inv["data_types"]  # noqa: S101


def test_cics_commands_and_options(tmp_path):
    code = """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS SEND TEXT FROM(V1) END-EXEC.
           GOBACK.
"""
    inv = run_snippet(tmp_path, code)
    assert "SEND TEXT" in inv["cics_commands"]  # noqa: S101
    assert "SEND TEXT: FROM" in inv["cics_options"]  # noqa: S101


def test_sql_forms(tmp_path):
    code = """       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           EXEC SQL DECLARE C1 CURSOR FOR SELECT * FROM T1 END-EXEC.
           EXEC SQL WHENEVER NOT FOUND GO TO ERR END-EXEC.
           EXEC SQL PREPARE S1 FROM :SQL-STMT END-EXEC.
           GOBACK.
"""
    inv = run_snippet(tmp_path, code)
    assert "DECLARE CURSOR" in inv["sql_forms"]  # noqa: S101
    assert "WHENEVER" in inv["sql_forms"]  # noqa: S101
    assert "DYNAMIC" in inv["sql_forms"]  # noqa: S101


def test_intrinsic_functions(tmp_path):
    code = """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC X(20).
       PROCEDURE DIVISION.
           MOVE FUNCTION CURRENT-DATE TO V1.
           GOBACK.
"""
    inv = run_snippet(tmp_path, code)
    assert "CURRENT-DATE" in inv["intrinsic_functions"]  # noqa: S101


def test_compile_options(tmp_path):
    code = """CBL NUMPROC(PFD)
       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           GOBACK.
"""
    inv = run_snippet(tmp_path, code)
    assert any("NUMPROC: PFD" in k for k in inv["compile_options"])  # noqa: S101


def test_copybook_gap(tmp_path):
    code = """       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           COPY MISSING.
           GOBACK.
"""
    inv = run_snippet(tmp_path, code)
    assert any("COPY MISSING" in k for k in inv["copybook_resolution_gaps"])  # noqa: S101


def test_fallback(tmp_path):
    code = """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC 99.
       PROCEDURE DIVISION.
           COPY MISSING.
           EXEC CICS READ FILE('bogus') END-EXEC.
           EXEC SQL EXECUTE S1 END-EXEC.
           MOVE 1 TO V1.
           GOBACK.
"""
    inv = run_snippet(tmp_path, code)
    assert any(x["program"] == "prog.cbl" for x in inv["unparsed_programs"])  # noqa: S101
    assert "READ" in inv["cics_commands"]  # noqa: S101
    assert "DYNAMIC" in inv["sql_forms"]  # noqa: S101
    assert "MOVE" in inv["statements"]  # noqa: S101
    assert "GOBACK" in inv["statements"]  # noqa: S101


TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}


def check_schema(data, node, root, where="$"):
    """The keywords feature_inventory.schema.json uses ($ref, type, required, properties, additionalProperties, items,
    minimum), checked without the jsonschema package (not installed in every venv / CI job)."""
    if "$ref" in node:
        node = root["$defs"][node["$ref"].split("/")[-1]]
    t = node.get("type")
    if t:
        assert isinstance(data, TYPES[t]) and not (t == "integer" and isinstance(data, bool)), f"{where}: not {t}"  # noqa: S101
    if "minimum" in node:
        assert data >= node["minimum"], f"{where}: below {node['minimum']}"  # noqa: S101
    if isinstance(data, dict):
        for k in node.get("required", []):
            assert k in data, f"{where}: missing {k}"  # noqa: S101
        props = node.get("properties", {})
        extra = node.get("additionalProperties", True)
        for k, v in data.items():
            if k in props:
                check_schema(v, props[k], root, f"{where}.{k}")
            elif isinstance(extra, dict):
                check_schema(v, extra, root, f"{where}.{k}")
            else:
                assert extra is not False, f"{where}: unexpected key {k}"  # noqa: S101
    if isinstance(data, list) and "items" in node:
        for i, v in enumerate(data):
            check_schema(v, node["items"], root, f"{where}[{i}]")


def test_schema_over_fixtures():
    schema = json.loads(SCHEMA_FILE.read_text())
    fixtures = sorted((TOOLS.parent / "fixtures" / "feature_inventory").glob("*.json"))
    assert len(fixtures) == 6  # noqa: S101 -- one per burned estate
    for f in fixtures:
        check_schema(json.loads(f.read_text()), schema, schema, f.name)
    with pytest.raises(AssertionError):
        check_schema({"statements": "not an object"}, schema, schema)


@pytest.mark.skipif(not (CORPORA / "cics-genapp").is_dir(), reason="no mainframe corpora (mainframe_corpus.py fetch)")
def test_feature_inventory_cli_check():
    res = subprocess.run([sys.executable, str(TOOLS / "feature_inventory.py"), "--all-burned", "--check"],  # noqa: S603
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert res.returncode == 0  # noqa: S101
