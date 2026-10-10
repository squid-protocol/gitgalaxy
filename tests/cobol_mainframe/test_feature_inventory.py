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


SNIPPETS = {
    "statements": "       ID DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01 X PIC 9.\n       PROCEDURE DIVISION.\n           ADD 1 TO X.\n           GOBACK.\n",
    "data_types": """       ID DIVISION.
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
""",
    "cics_commands_and_options": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS SEND TEXT FROM(V1) END-EXEC.
           GOBACK.
""",
    "sql_forms": """       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           EXEC SQL DECLARE C1 CURSOR FOR SELECT * FROM T1 END-EXEC.
           EXEC SQL WHENEVER NOT FOUND GO TO ERR END-EXEC.
           EXEC SQL PREPARE S1 FROM :SQL-STMT END-EXEC.
           GOBACK.
""",
    "intrinsic_functions": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC X(20).
       PROCEDURE DIVISION.
           MOVE FUNCTION CURRENT-DATE TO V1.
           GOBACK.
""",
    "compile_options": """CBL NUMPROC(PFD)
       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           GOBACK.
""",
    "copybook_gap": """       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           COPY MISSING.
           GOBACK.
""",
    "fallback": """       ID DIVISION.
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
""",
}  # one program per feature category, all scanned together ONCE (a full engine scan is 18-33 s)


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    """(estate dir, db dir, inventory) for the combined synthetic estate; tmp_path_factory keeps it xdist-safe."""
    base = tmp_path_factory.mktemp("feature_inventory")
    d = base / "estate"
    d.mkdir()
    for name, code in SNIPPETS.items():
        (d / f"{name}.cbl").write_text(code)
    db_dir = base / "db"
    db_dir.mkdir()
    return d, db_dir, scan_estate(d, db_dir)


def has(inv, category, key, snippet):
    """The feature `key` was reported in `category` by the program of that snippet (not by a sibling's)."""
    return key in inv[category] and f"{snippet}.cbl" in inv[category][key]["programs"]


def test_determinism(synthetic):
    d, db_dir, inv1 = synthetic
    inv2 = scan_estate(d, db_dir)
    assert json.dumps(inv1, sort_keys=True) == json.dumps(inv2, sort_keys=True)  # noqa: S101


def test_statements(synthetic):
    inv = synthetic[2]
    assert has(inv, "statements", "ARITH", "statements")  # noqa: S101
    assert has(inv, "statements", "GOBACK", "statements")  # noqa: S101


def test_data_types(synthetic):
    inv = synthetic[2]
    assert has(inv, "data_types", "PACKED", "data_types")  # noqa: S101
    assert has(inv, "data_types", "P-SCALED", "data_types")  # noqa: S101
    assert has(inv, "data_types", "EDITED", "data_types")  # noqa: S101
    assert has(inv, "data_types", "COMP-1", "data_types")  # noqa: S101
    assert has(inv, "data_types", "COMP-2", "data_types")  # noqa: S101
    assert has(inv, "data_types", "NATIONAL", "data_types")  # noqa: S101


def test_cics_commands_and_options(synthetic):
    inv = synthetic[2]
    assert has(inv, "cics_commands", "SEND TEXT", "cics_commands_and_options")  # noqa: S101
    assert has(inv, "cics_options", "SEND TEXT: FROM", "cics_commands_and_options")  # noqa: S101


def test_sql_forms(synthetic):
    inv = synthetic[2]
    assert has(inv, "sql_forms", "DECLARE CURSOR", "sql_forms")  # noqa: S101
    assert has(inv, "sql_forms", "WHENEVER", "sql_forms")  # noqa: S101
    assert has(inv, "sql_forms", "DYNAMIC", "sql_forms")  # noqa: S101


def test_intrinsic_functions(synthetic):
    inv = synthetic[2]
    assert has(inv, "intrinsic_functions", "CURRENT-DATE", "intrinsic_functions")  # noqa: S101


def test_compile_options(synthetic):
    inv = synthetic[2]
    assert any(
        "NUMPROC: PFD" in k and "compile_options.cbl" in v["programs"] for k, v in inv["compile_options"].items()
    )  # noqa: S101


def test_copybook_gap(synthetic):
    inv = synthetic[2]
    assert any(
        "COPY MISSING" in k and "copybook_gap.cbl" in v["programs"] for k, v in inv["copybook_resolution_gaps"].items()
    )  # noqa: S101


def test_fallback(synthetic):
    inv = synthetic[2]
    assert any(x["program"] == "fallback.cbl" for x in inv["unparsed_programs"])  # noqa: S101
    assert has(inv, "cics_commands", "READ", "fallback")  # noqa: S101
    assert has(inv, "sql_forms", "DYNAMIC", "fallback")  # noqa: S101
    assert has(inv, "statements", "MOVE", "fallback")  # noqa: S101
    assert has(inv, "statements", "GOBACK", "fallback")  # noqa: S101


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


@pytest.mark.nightly
@pytest.mark.skipif(
    not os.environ.get("GITGALAXY_NIGHTLY"), reason="nightly (~170 s, all estates): set GITGALAXY_NIGHTLY=1"
)
@pytest.mark.skipif(not (CORPORA / "cics-genapp").is_dir(), reason="no mainframe corpora (mainframe_corpus.py fetch)")
def test_feature_inventory_cli_check():
    res = subprocess.run([sys.executable, str(TOOLS / "feature_inventory.py"), "--all-burned", "--check"],  # noqa: S603
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert res.returncode == 0  # noqa: S101
