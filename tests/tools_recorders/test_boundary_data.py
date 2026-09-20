"""
#3200/#3201: call_site_data, dataset_data, and the 'call'/'exec' edge kinds.

These pin the two properties the design turns on:

  1. EVERY call site is persisted, including the ones that resolved to nothing.
     "Unresolved targets are recorded nowhere" was half of #3200, so a row that
     names a target it could not reach is the feature, not a gap.
  2. The call graph does NOT enter the dependency graph. edge_data grows, but
     every degree, pagerank input and reconciliation that reads it stays scoped
     to edge_kind='import'.
"""

import sqlite3

import pytest

from gitgalaxy.core.invocation_resolver import resolve_invocations
from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "cb0101", "latest_commit_date": "2026-09-20T00:00:00Z"},
}

# Two COBOL programs sharing one PROGRAM-ID in different directories (the real
# IBM/zopeneditor-sample #3218 layout), the caller beside one of them, a JCL job
# that runs it, and a copybook the caller COPYs.
UNIVERSE = [
    {
        "path": "COBOL/SAM1.cbl",
        "lang_id": "cobol",
        "raw_imports": ["CUSTCOPY"],
        "classes": [{"name": "SAM1"}],
        "call_sites": [
            {"verb": "CALL", "form": "identifier", "operand": "SAM2", "target": "SAM2", "line": 304},
            {"verb": "CALL", "form": "literal", "operand": "CEEGMT", "target": "CEEGMT", "line": 400},
            {"verb": "CALL", "form": "identifier", "operand": "WS-FROM-COPYBOOK", "target": None, "line": 410},
        ],
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
    {"path": "COBOL/SAM2.cbl", "lang_id": "cobol", "raw_imports": [], "classes": [{"name": "SAM2"}]},
    {"path": "multiroot/sam/SAM2.cbl", "lang_id": "cobol", "raw_imports": [], "classes": [{"name": "SAM2"}]},
    {"path": "COPYBOOK/CUSTCOPY.cpy", "lang_id": "cobol", "raw_imports": []},
    {
        "path": "JCL/RUN.jcl",
        "lang_id": "jcl",
        "raw_imports": [],
        "call_sites": [
            {"verb": "EXEC PGM", "form": "literal", "operand": "SAM1", "target": "SAM1", "line": 147},
            {"verb": "EXEC PGM", "form": "literal", "operand": "IEFBR14", "target": "IEFBR14", "line": 135},
        ],
        "dataset_bindings": [
            {
                "internal_name": None,
                "assign_name": None,
                "dd_name": "CUSTFILE",
                "modes": [],
                "dsn": "SAMPLE.CUSTFILE",
                "step_name": "SAM1",
                "line": 154,
            }
        ],
    },
]


@pytest.fixture
def recorded(tmp_path):
    """One scan's worth of state, through the sensor, the resolver and the recorder."""
    import copy

    sensor = NetworkRiskSensor()
    files, _ = sensor.build_dependency_graph(copy.deepcopy(UNIVERSE))
    call_sites, invocation_edges = resolve_invocations(files)
    db = tmp_path / "mainframe.db"
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


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


# ==============================================================================
# RESOLUTION
# ==============================================================================
def test_a_shared_program_id_resolves_to_the_nearest_declaration():
    """COBOL/SAM1.cbl's `CALL SAM2` is COBOL/SAM2.cbl, not multiroot/sam/SAM2.cbl.

    The import resolver would disqualify both -- each declares PROGRAM-ID SAM2,
    and a copybook is never a program (#3199). A CALL wants exactly that file,
    and is chosen by library concatenation order, so nearest-wins is the
    reading the answer key records.
    """
    sites, _ = resolve_invocations(UNIVERSE)
    by_operand = {s["operand"]: s for s in sites if s["src_path"] == "COBOL/SAM1.cbl"}
    assert by_operand["SAM2"]["resolved_path"] == "COBOL/SAM2.cbl"


def test_nearest_resolves_identically_on_windows_native_paths():
    """The engine stores OS-native separators, so resolution must normalise them.

    The shallower-path tiebreak only applies when two candidates share the same
    prefix depth with the caller. `zz/P.cbl` (depth 1) and `aa/bb/P.cbl`
    (depth 2) is that case, and the two rules disagree: depth picks `zz`,
    alphabetical picks `aa`. With an un-normalised `count("/")` every Windows
    path scores 0, so the tiebreak silently degrades to alphabetical and Windows
    resolves the call to a DIFFERENT file than Linux for the same repository
    (#3223 went red on this class of thing).
    """
    universe = [
        {
            "path": "JCL/RUN.jcl",
            "lang_id": "jcl",
            "raw_imports": [],
            "call_sites": [{"verb": "EXEC PGM", "form": "literal", "operand": "P", "target": "P", "line": 1}],
        },
        {"path": "zz/P.cbl", "lang_id": "cobol", "raw_imports": [], "classes": [{"name": "P"}]},
        {"path": "aa/bb/P.cbl", "lang_id": "cobol", "raw_imports": [], "classes": [{"name": "P"}]},
    ]
    windows = [{**f, "path": f["path"].replace("/", "\\")} for f in universe]

    (posix_site,) = resolve_invocations(universe)[0]
    (windows_site,) = resolve_invocations(windows)[0]

    assert posix_site["resolved_path"] == "zz/P.cbl", "the SHALLOWER path wins, not the alphabetical one"
    assert windows_site["resolved_path"] == "zz\\P.cbl", "Windows must reach the same decision"


def test_nearest_is_deterministic_regardless_of_scan_order():
    """A repository scanned on two machines must produce the same edge."""
    import copy

    forward = resolve_invocations(copy.deepcopy(UNIVERSE))[1]
    reversed_scan = resolve_invocations(list(reversed(copy.deepcopy(UNIVERSE))))[1]
    assert forward == reversed_scan


# ==============================================================================
# #3200: EVERY SITE IS A ROW, RESOLVED OR NOT
# ==============================================================================
def test_unresolved_targets_are_rows_not_silence(recorded):
    """The three levels of failure stay distinguishable in the table."""
    rows = _rows(
        recorded,
        """
        SELECT c.verb, c.form, c.operand, c.target, c.dst_file_id
        FROM call_site_data c JOIN file_data f ON c.src_file_id = f.id
        WHERE f.file_path = 'COBOL/SAM1.cbl' ORDER BY c.line_number
        """,
    )
    # The dst_file_id of the one resolved row is an id, so compare it separately
    # from the fixed columns rather than pinning whatever id it happened to get.
    assert [r[:4] for r in rows] == [
        # resolved: a target that IS a program in this repository
        ("CALL", "identifier", "SAM2", "SAM2"),
        # named, but external (a Language Environment service)
        ("CALL", "literal", "CEEGMT", "CEEGMT"),
        # the name itself was unreadable -- the VALUE clause is in a copybook
        ("CALL", "identifier", "WS-FROM-COPYBOOK", None),
    ]
    assert rows[0][4] is not None, "a resolved target must carry its destination file id"
    assert [r[4] for r in rows[1:]] == [None, None]


def test_a_jcl_step_links_to_the_program_it_runs(recorded):
    """`EXEC PGM=SAM1` is the job -> program edge that never existed before #3200."""
    assert _rows(
        recorded,
        """
        SELECT s.file_path, d.file_path, c.verb
        FROM call_site_data c
        JOIN file_data s ON c.src_file_id = s.id
        JOIN file_data d ON c.dst_file_id = d.id
        WHERE s.file_path = 'JCL/RUN.jcl'
        """,
    ) == [("JCL/RUN.jcl", "COBOL/SAM1.cbl", "EXEC PGM")]


def test_a_system_utility_is_kept_as_an_unresolved_row(recorded):
    """`EXEC PGM=IEFBR14` names a real program that is simply not in this repo."""
    assert _rows(
        recorded,
        "SELECT target, dst_file_id FROM call_site_data WHERE operand = 'IEFBR14'",
    ) == [("IEFBR14", None)]


# ==============================================================================
# THE CALL GRAPH IS NOT THE DEPENDENCY GRAPH
# ==============================================================================
def test_call_edges_use_their_own_kind_and_leave_import_degrees_alone(recorded):
    kinds = dict(_rows(recorded, "SELECT edge_kind, COUNT(*) FROM edge_data GROUP BY edge_kind"))
    assert kinds == {"import": 1, "call": 1, "exec": 1}

    # #2992's reconciliation, scoped to imports, still holds exactly.
    for path, links, popularity, out_rows, in_rows in _rows(
        recorded,
        """
        SELECT f.file_path, f.internal_dependency_links, f.popularity,
               (SELECT COUNT(*) FROM edge_data e WHERE e.src_file_id = f.id AND e.edge_kind = 'import'),
               (SELECT COUNT(*) FROM edge_data e WHERE e.dst_file_id = f.id AND e.edge_kind = 'import')
        FROM file_data f
        """,
    ):
        assert (links, popularity) == (out_rows, in_rows), path


def test_a_called_program_gains_no_popularity(recorded):
    """COBOL/SAM2.cbl is CALLed but imported by nobody: popularity stays 0.

    If this ever fails, call edges have entered the DiGraph and every mainframe
    repo's pagerank, blast radius and archetypes have silently moved.
    """
    assert _rows(
        recorded, "SELECT popularity, internal_dependency_links FROM file_data WHERE file_path = 'COBOL/SAM2.cbl'"
    ) == [(0, 0)]


# ==============================================================================
# #3201: THE DATASET BOUNDARY, BOTH HALVES
# ==============================================================================
def test_both_halves_of_the_dataset_boundary_persist(recorded):
    assert _rows(
        recorded,
        """
        SELECT f.file_path, d.step_name, d.internal_name, d.dd_name, d.access_modes, d.dsn
        FROM dataset_data d JOIN file_data f ON d.file_id = f.id ORDER BY f.file_path
        """,
    ) == [
        ("COBOL/SAM1.cbl", None, "CUSTOMER-FILE", "CUSTFILE", "INPUT", None),
        ("JCL/RUN.jcl", "SAM1", None, "CUSTFILE", None, "SAMPLE.CUSTFILE"),
    ]


def test_the_lineage_join_is_answerable_in_sql(recorded):
    """#3201's question: "program P reads DD X, job J binds DD X to dataset D"."""
    assert _rows(
        recorded,
        """
        SELECT pf.file_path, p.dd_name, p.access_modes, jf.file_path, j.step_name, j.dsn
        FROM dataset_data p
        JOIN file_data pf ON p.file_id = pf.id
        JOIN call_site_data c ON c.dst_file_id = pf.id AND c.verb = 'EXEC PGM'
        JOIN file_data jf ON c.src_file_id = jf.id
        JOIN dataset_data j ON j.file_id = jf.id AND j.dd_name = p.dd_name
        WHERE p.dsn IS NULL
        """,
    ) == [("COBOL/SAM1.cbl", "CUSTFILE", "INPUT", "JCL/RUN.jcl", "SAM1", "SAMPLE.CUSTFILE")]


# ==============================================================================
# DELTA MODE
# ==============================================================================
def test_an_unchanged_file_keeps_its_boundary_rows_through_a_delta_scan(recorded):
    """The rehydrator must restore call sites and dataset bindings (#3220's rule).

    An incremental scan never re-parses an unchanged file, so without this the
    DB would end up describing only the files that happened to change in the
    last commit -- every other program's call graph and dataset lineage silently
    dropped out on the second scan. Verified end to end as well: a full then an
    incremental scan of IBM/zopeneditor-sample produce byte-identical
    call_site_data and dataset_data for the newest snapshot.
    """
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    state = StateRehydrator(str(recorded)).load_state("MainframeRepo")
    assert state is not None
    cache = state["ram_cache"]

    assert [
        (c["verb"], c["form"], c["operand"], c["target"], c["line"]) for c in cache["COBOL/SAM1.cbl"]["call_sites"]
    ] == [
        ("CALL", "identifier", "SAM2", "SAM2", 304),
        ("CALL", "literal", "CEEGMT", "CEEGMT", 400),
        ("CALL", "identifier", "WS-FROM-COPYBOOK", None, 410),
    ]
    assert [(d["internal_name"], d["dd_name"], d["modes"]) for d in cache["COBOL/SAM1.cbl"]["dataset_bindings"]] == [
        ("CUSTOMER-FILE", "CUSTFILE", ["INPUT"])
    ]
    assert [(d["step_name"], d["dd_name"], d["dsn"]) for d in cache["JCL/RUN.jcl"]["dataset_bindings"]] == [
        ("SAM1", "CUSTFILE", "SAMPLE.CUSTFILE")
    ]


def test_a_rehydrated_call_site_carries_no_stale_resolution(recorded):
    """Resolution is repo-wide, so it is redone every scan and never restored.

    A file added or deleted in this commit can change what an UNCHANGED file's
    `CALL` resolves to, so carrying a previous scan's `resolved_path` forward
    would pin an edge to a file that may no longer be the nearest match.
    """
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    cache = StateRehydrator(str(recorded)).load_state("MainframeRepo")["ram_cache"]
    for site in cache["COBOL/SAM1.cbl"]["call_sites"]:
        assert "resolved_path" not in site
        assert "dst_file_id" not in site


def test_a_baseline_written_before_3200_still_rehydrates(recorded):
    """A DB with no boundary tables is a normal baseline, not a failure."""
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    conn = sqlite3.connect(recorded)
    conn.execute("DROP TABLE call_site_data")
    conn.execute("DROP TABLE dataset_data")
    conn.commit()
    conn.close()

    cache = StateRehydrator(str(recorded)).load_state("MainframeRepo")["ram_cache"]
    assert cache["COBOL/SAM1.cbl"]["call_sites"] == []
    assert cache["COBOL/SAM1.cbl"]["dataset_bindings"] == []


# ==============================================================================
# BACKWARD COMPATIBILITY
# ==============================================================================
def test_a_caller_predating_3200_writes_no_boundary_rows(tmp_path):
    """The new arguments default to None, so an older caller still records a scan."""
    import copy

    sensor = NetworkRiskSensor()
    files, _ = sensor.build_dependency_graph(copy.deepcopy(UNIVERSE))
    db = tmp_path / "legacy.db"
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges)
    assert _rows(db, "SELECT COUNT(*) FROM call_site_data") == [(0,)]
    assert _rows(db, "SELECT COUNT(*) FROM edge_data WHERE edge_kind <> 'import'") == [(0,)]
