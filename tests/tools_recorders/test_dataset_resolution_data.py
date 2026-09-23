"""
#3345: the resolved-DSN columns on dataset_data -- write path, schema heal,
delta-scan restore, the IR reader, and the forensic report.

`dsn` stays the DSN as written; `dsn_resolved`/`dsn_resolution` ride beside it.
Each back-compat edge is pinned: a dataset_data table created before #3345 heals
on the next record, and a baseline or master DB without the columns still
rehydrates and loads (the keys simply absent / None).
"""

import copy
import sqlite3

import pytest

from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "JclRepo",
    "git_audit": {"commit_hash": "cb3345", "latest_commit_date": "2026-09-23T00:00:00Z"},
}

UNIVERSE = [
    {
        "path": "COBOL/SAM1.cbl",
        "lang_id": "cobol",
        "raw_imports": [],
        "dataset_bindings": [
            {
                "internal_name": "CUSTOMER-FILE",
                "assign_name": "CUSTFILE",
                "dd_name": "CUSTFILE",
                "modes": ["INPUT"],
                "dsn": None,
                "step_name": None,
                "line": 40,
            }
        ],
    },
    {
        "path": "JCL/RUN.jcl",
        "lang_id": "jcl",
        "raw_imports": [],
        "dataset_bindings": [
            {
                "internal_name": None,
                "assign_name": None,
                "dd_name": "CUSTFILE",
                "modes": [],
                "dsn": "&HLQ..SAMPLE.CUSTFILE",
                "step_name": "SAM1",
                "line": 154,
                "dsn_resolved": "IBMUSER.SAMPLE.CUSTFILE",
                "dsn_resolution": "resolved",
            },
            {
                "internal_name": None,
                "assign_name": None,
                "dd_name": "REPORT",
                "modes": [],
                "dsn": "&SYSUID..REPORT",
                "step_name": "SAM1",
                "line": 160,
                "dsn_resolved": None,
                "dsn_resolution": "unresolved",
            },
            {
                "internal_name": None,
                "assign_name": None,
                "dd_name": "STEPLIB",
                "modes": [],
                "dsn": "SYS1.LINKLIB",
                "step_name": "SAM1",
                "line": 150,
                "dsn_resolved": "SYS1.LINKLIB",
                "dsn_resolution": "literal",
            },
        ],
    },
]

UNIVERSE_LANG = {f["path"]: f["lang_id"] for f in UNIVERSE}

ROWS = [
    ("COBOL/SAM1.cbl", "CUSTFILE", None, None, None),
    ("JCL/RUN.jcl", "CUSTFILE", "&HLQ..SAMPLE.CUSTFILE", "IBMUSER.SAMPLE.CUSTFILE", "resolved"),
    ("JCL/RUN.jcl", "REPORT", "&SYSUID..REPORT", None, "unresolved"),
    ("JCL/RUN.jcl", "STEPLIB", "SYS1.LINKLIB", "SYS1.LINKLIB", "literal"),
]
SELECT_ROWS = """
    SELECT f.file_path, d.dd_name, d.dsn, d.dsn_resolved, d.dsn_resolution
    FROM dataset_data d JOIN file_data f ON d.file_id = f.id ORDER BY f.file_path, d.dd_name
"""


def _record(db, universe=UNIVERSE):
    RecordKeeper().record_mission(copy.deepcopy(universe), [], {}, SESSION, str(db))


def _rows(db, sql=SELECT_ROWS):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@pytest.fixture
def recorded(tmp_path):
    db = tmp_path / "jcl.db"
    _record(db)
    return db


def test_the_resolved_dsn_persists_beside_the_raw_one(recorded):
    assert _rows(recorded) == ROWS


def test_re_recording_the_same_snapshot_does_not_duplicate(recorded):
    _record(recorded)
    assert _rows(recorded) == ROWS


def test_a_dataset_table_from_before_3345_heals_on_the_next_record(tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE dataset_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, repo_name TEXT, commit_hash TEXT, file_id INTEGER,
            step_name TEXT, internal_name TEXT, assign_name TEXT, dd_name TEXT, access_modes TEXT,
            dsn TEXT, line_number INTEGER)"""
    )
    conn.commit()
    conn.close()
    _record(db)
    assert _rows(db) == ROWS


def _drop_resolution_columns(db):
    conn = sqlite3.connect(db)
    conn.execute("ALTER TABLE dataset_data DROP COLUMN dsn_resolved")
    conn.execute("ALTER TABLE dataset_data DROP COLUMN dsn_resolution")
    conn.commit()
    conn.close()


# ------------------------------------------------------------------------------
# DELTA MODE
# ------------------------------------------------------------------------------
def test_an_unchanged_jcl_file_keeps_its_resolution_through_a_delta_scan(recorded, tmp_path):
    """Full then incremental: the restored payload re-records byte-identical rows."""
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    cache = StateRehydrator(str(recorded)).load_state("JclRepo")["ram_cache"]
    jcl = cache["JCL/RUN.jcl"]["dataset_bindings"]
    assert [(d["dd_name"], d["dsn_resolved"], d["dsn_resolution"]) for d in jcl] == [
        ("CUSTFILE", "IBMUSER.SAMPLE.CUSTFILE", "resolved"),
        ("REPORT", None, "unresolved"),
        ("STEPLIB", "SYS1.LINKLIB", "literal"),
    ]
    # A COBOL row comes back in the extractor's own shape: no resolution keys.
    assert "dsn_resolution" not in cache["COBOL/SAM1.cbl"]["dataset_bindings"][0]

    rehydrated = [
        {"path": path, "lang_id": UNIVERSE_LANG[path], "raw_imports": [], "dataset_bindings": node["dataset_bindings"]}
        for path, node in cache.items()
        if path in UNIVERSE_LANG
    ]
    again = tmp_path / "again.db"
    _record(again, rehydrated)
    assert _rows(again) == _rows(recorded)


def test_a_baseline_without_the_columns_still_rehydrates(recorded):
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    _drop_resolution_columns(recorded)
    cache = StateRehydrator(str(recorded)).load_state("JclRepo")["ram_cache"]
    jcl = cache["JCL/RUN.jcl"]["dataset_bindings"]
    assert [d["dsn"] for d in jcl] == ["&HLQ..SAMPLE.CUSTFILE", "&SYSUID..REPORT", "SYS1.LINKLIB"]
    assert all("dsn_resolution" not in d for d in jcl)


# ------------------------------------------------------------------------------
# IR READER
# ------------------------------------------------------------------------------
def test_the_ir_reader_carries_the_resolution(recorded):
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    ir = load_galaxy_ir(recorded)
    by_dd = {d.dd_name: d for d in ir.files["JCL/RUN.jcl"].datasets}
    assert (by_dd["CUSTFILE"].dsn, by_dd["CUSTFILE"].dsn_resolved, by_dd["CUSTFILE"].dsn_resolution) == (
        "&HLQ..SAMPLE.CUSTFILE",
        "IBMUSER.SAMPLE.CUSTFILE",
        "resolved",
    )
    assert by_dd["REPORT"].dsn_resolved is None and by_dd["REPORT"].dsn_resolution == "unresolved"
    (cobol,) = ir.files["COBOL/SAM1.cbl"].datasets
    assert cobol.dsn_resolved is None and cobol.dsn_resolution is None


def test_the_ir_reader_loads_a_db_written_before_3345(recorded):
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    _drop_resolution_columns(recorded)
    ir = load_galaxy_ir(recorded)
    datasets = ir.files["JCL/RUN.jcl"].datasets
    assert [d.dsn for d in datasets] == ["SYS1.LINKLIB", "&HLQ..SAMPLE.CUSTFILE", "&SYSUID..REPORT"]  # line order
    assert all(d.dsn_resolved is None and d.dsn_resolution is None for d in datasets)


# ------------------------------------------------------------------------------
# FORENSIC REPORT
# ------------------------------------------------------------------------------
def test_the_audit_block_adds_the_resolution_only_where_a_symbol_was_named():
    block = AuditRecorder._mainframe_facts_block(None, UNIVERSE[1])
    by_dd = {b["DD Name"]: b for b in block["Dataset Bindings"]}
    assert by_dd["CUSTFILE"]["Resolved DSN"] == "IBMUSER.SAMPLE.CUSTFILE"
    assert by_dd["CUSTFILE"]["DSN Resolution"] == "resolved"
    assert by_dd["REPORT"]["Resolved DSN"] is None and by_dd["REPORT"]["DSN Resolution"] == "unresolved"
    # A literal DSN and a COBOL SELECT are unchanged from the pre-#3345 report.
    assert "Resolved DSN" not in by_dd["STEPLIB"]
    cobol = AuditRecorder._mainframe_facts_block(None, UNIVERSE[0])["Dataset Bindings"][0]
    assert "Resolved DSN" not in cobol and "DSN Resolution" not in cobol


# ------------------------------------------------------------------------------
# LINEAGE JOINS ON THE RESOLVED NAME
# ------------------------------------------------------------------------------
def _dd(dd, dsn, step, line, resolved=None, resolution=None, modes=None, internal=None):
    return {
        "internal_name": internal,
        "assign_name": dd if internal else None,
        "dd_name": dd,
        "modes": modes or [],
        "dsn": dsn,
        "step_name": step,
        "line": line,
        **({"dsn_resolved": resolved, "dsn_resolution": resolution} if resolution else {}),
    }


# carddemo's shape: one job writes the daily file through `&HLQ..` under a SET,
# another job reads it by its literal name. Only the resolution makes them one.
FLOW_UNIVERSE = [
    {
        "path": "cbl/WRITER.cbl",
        "lang_id": "cobol",
        "raw_imports": [],
        "classes": [{"name": "WRITER"}],
        "dataset_bindings": [_dd("OUTFILE", None, None, 20, modes=["OUTPUT"], internal="OUT-FILE")],
    },
    {
        "path": "cbl/READER.cbl",
        "lang_id": "cobol",
        "raw_imports": [],
        "classes": [{"name": "READER"}],
        "dataset_bindings": [_dd("INFILE", None, None, 20, modes=["INPUT"], internal="IN-FILE")],
    },
    {
        "path": "jcl/WRITE.jcl",
        "lang_id": "jcl",
        "raw_imports": [],
        "call_sites": [{"verb": "EXEC PGM", "form": "literal", "operand": "WRITER", "target": "WRITER", "line": 3}],
        "dataset_bindings": [_dd("OUTFILE", "&HLQ..DAILY(+1)", "STEP1", 4, "PROD.DAILY(+1)", "resolved")],
    },
    {
        "path": "jcl/READ.jcl",
        "lang_id": "jcl",
        "raw_imports": [],
        "call_sites": [{"verb": "EXEC PGM", "form": "literal", "operand": "READER", "target": "READER", "line": 3}],
        "dataset_bindings": [_dd("INFILE", "PROD.DAILY(0)", "STEP1", 4, "PROD.DAILY(0)", "literal")],
    },
    {
        "path": "jcl/OTHER.jcl",
        "lang_id": "jcl",
        "raw_imports": [],
        "dataset_bindings": [_dd("INFILE", "&SYSUID..DAILY", "STEP1", 4, None, "unresolved")],
    },
]


@pytest.fixture
def flow_db(tmp_path):
    from gitgalaxy.core.invocation_resolver import resolve_invocations
    from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor

    sensor = NetworkRiskSensor()
    files, _ = sensor.build_dependency_graph(copy.deepcopy(FLOW_UNIVERSE))
    call_sites, invocation_edges = resolve_invocations(files)
    db = tmp_path / "flow.db"
    RecordKeeper().record_mission(
        files,
        [],
        {},
        SESSION,
        str(db),
        dependency_edges=sensor.dependency_edges,
        call_sites=call_sites,
        invocation_edges=invocation_edges,
    )
    return db


def test_two_jobs_on_one_resolved_dataset_link_their_programs(flow_db):
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    ir = load_galaxy_ir(flow_db)
    assert ir.dataset_flows() == [
        {
            "dataset": "PROD.DAILY",
            "writer": "cbl/WRITER.cbl",
            "writer_job": "jcl/WRITE.jcl",
            "reader": "cbl/READER.cbl",
            "reader_job": "jcl/READ.jcl",
        }
    ]
    # The unresolved `&SYSUID..DAILY` binding is not guessed into the group.
    assert {k: sorted(b["job"] for b in v) for k, v in ir.shared_datasets().items()} == {
        "PROD.DAILY": ["jcl/READ.jcl", "jcl/WRITE.jcl"]
    }
    (entry,) = [e for e in ir.dataset_lineage() if e["program"] == "cbl/WRITER.cbl"]
    assert (entry["dsn"], entry["dsn_resolved"], entry["dataset"]) == (
        "&HLQ..DAILY(+1)",
        "PROD.DAILY(+1)",
        "PROD.DAILY(+1)",
    )


def test_without_the_resolution_the_flow_is_invisible(flow_db):
    """The same DB written before #3345: the writer's DSN is a template, so the two
    programs share nothing -- exactly the gap the resolution closes."""
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    _drop_resolution_columns(flow_db)
    ir = load_galaxy_ir(flow_db)
    assert ir.dataset_flows() == []
    assert ir.shared_datasets() == {}
