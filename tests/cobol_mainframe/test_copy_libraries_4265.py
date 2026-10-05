"""#4265 (estate-crucible H-0034): COPY library resolution in the wild.

A z/OS COPY is found by the program's SYSLIB concatenation, first library holding the member wins;
`COPY X IN LIB` searches LIB only. Without a declaration the scan cannot know either, so nothing
changes; with `galaxyscope --copy-libraries FILE` the import edges, and the record layouts built on
them, follow the declared libraries, and a member found in several libraries of a program's search
order is reported.
"""

import json
import sqlite3

import pytest

from gitgalaxy.core.copy_libraries import CopyLibraryError, parse_copy_libraries
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

PAYMAIN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYMAIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-LOCAL-DATE.
           COPY DATEWS.
       01  WS-SHARED-DATE.
           COPY DATEWS IN SHRCPY.
       PROCEDURE DIVISION.
           GOBACK.
"""
ACCTPOST = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTPOST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DATE-AREA.
           COPY DATEWS.
       PROCEDURE DIVISION.
           GOBACK.
"""
PAYR_DATEWS = "           05  WS-CURR-DATE   PIC X(10).\n           05  WS-CURR-TIME   PIC X(8).\n"  # 18 bytes
SHARED_DATEWS = "           05  WS-CURR-DATE   PIC X(8).\n           05  WS-CURR-TIME   PIC X(8).\n"  # 16 bytes

DECLARATION = {
    "libraries": {"PAYRCPY": ["apps/PAYR/copybook"], "ACCTCPY": "apps/ACCT/copybook", "SHRCPY": ["shared/copylib"]},
    "syslib": [
        {"programs": "apps/PAYR/*", "order": ["PAYRCPY", "SHRCPY"]},
        {"programs": "apps/ACCT/*", "order": ["ACCTCPY", "SHRCPY"]},
    ],
}


def _estate(base):
    repo = base / "estate"
    for rel, text in {
        "apps/PAYR/cobol/PAYMAIN.cbl": PAYMAIN,
        "apps/PAYR/copybook/DATEWS.cpy": PAYR_DATEWS,
        "apps/ACCT/cobol/ACCTPOST.cbl": ACCTPOST,
        "shared/copylib/DATEWS.cpy": SHARED_DATEWS,
    }.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo


@pytest.fixture(scope="module")
def declared(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy_libraries")
    spec = base / "libraries.json"
    spec.write_text(json.dumps(DECLARATION), encoding="utf-8")
    return scan_to_db(_estate(base), base / "scan", extra_args=["--copy-libraries", str(spec)])


@pytest.fixture(scope="module")
def undeclared(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy_libraries_default")
    return scan_to_db(_estate(base), base / "scan")


def _bytes(ir, path, record):
    ef = ir.files[path]
    root = next(r for r in ef.records if r.name == record)
    return ir.record_layout(ef, root)["bytes"]


def test_the_extractor_records_each_copys_library():
    rows = {r["name"]: r for r in extract_boundary("cobol", PAYMAIN)["records"]}
    assert rows["WS-SHARED-DATE"]["copy_libraries"] == "SHRCPY"
    assert "copy_libraries" not in rows["WS-LOCAL-DATE"]  # presence-keyed: no library named


def test_syslib_order_and_in_library_pick_their_own_member(declared):
    ir = load_galaxy_ir(declared)
    assert sorted(ir.files["apps/PAYR/cobol/PAYMAIN.cbl"].copy_deps) == [
        "apps/PAYR/copybook/DATEWS.cpy",  # COPY DATEWS: PAYRCPY is first in PAYR's SYSLIB
        "shared/copylib/DATEWS.cpy",  # COPY DATEWS IN SHRCPY
    ]
    assert _bytes(ir, "apps/PAYR/cobol/PAYMAIN.cbl", "WS-LOCAL-DATE") == 18
    assert _bytes(ir, "apps/PAYR/cobol/PAYMAIN.cbl", "WS-SHARED-DATE") == 16
    # ACCT's SYSLIB has no PAYRCPY: the shared member, not the nearest same-named file
    assert ir.files["apps/ACCT/cobol/ACCTPOST.cbl"].copy_deps == ["shared/copylib/DATEWS.cpy"]
    assert _bytes(ir, "apps/ACCT/cobol/ACCTPOST.cbl", "WS-DATE-AREA") == 16


def test_the_edge_records_the_copy_forms_that_reached_it(declared):
    conn = sqlite3.connect(declared)
    rows = dict(
        conn.execute(
            "SELECT d.file_path, e.copy_libraries FROM edge_data e JOIN file_data s ON s.id = e.src_file_id "
            "JOIN file_data d ON d.id = e.dst_file_id WHERE s.file_path = 'apps/PAYR/cobol/PAYMAIN.cbl'"
        )
    )
    assert rows == {"apps/PAYR/copybook/DATEWS.cpy": '[""]', "shared/copylib/DATEWS.cpy": '["SHRCPY"]'}


def test_without_a_declaration_nothing_changes(undeclared):
    conn = sqlite3.connect(undeclared)
    assert conn.execute("SELECT COUNT(*) FROM edge_data WHERE copy_libraries IS NOT NULL").fetchone() == (0,)


def test_a_member_in_several_libraries_is_reported(tmp_path):
    from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor

    sensor = NetworkRiskSensor()
    sensor.copy_libraries = parse_copy_libraries(DECLARATION)
    files = [
        {"path": "apps/PAYR/cobol/PAYMAIN.cbl", "lang_id": "cobol", "raw_imports": ["DATEWS"], "classes": [{}]},
        {"path": "apps/PAYR/copybook/DATEWS.cpy", "lang_id": "cobol", "raw_imports": []},
        {"path": "shared/copylib/DATEWS.cpy", "lang_id": "cobol", "raw_imports": []},
    ]
    edges = sensor._resolve_edges(files)
    assert list(edges) == [("apps/PAYR/cobol/PAYMAIN.cbl", "apps/PAYR/copybook/DATEWS.cpy")]
    assert sensor.copy_collisions == [
        {
            "importer": "apps/PAYR/cobol/PAYMAIN.cbl",
            "member": "DATEWS",
            "resolved": "apps/PAYR/copybook/DATEWS.cpy",
            "library": "PAYRCPY",
            "shadowed": [{"library": "SHRCPY", "paths": ["shared/copylib/DATEWS.cpy"]}],
        }
    ]


def test_a_named_library_that_lacks_the_member_draws_no_edge():
    from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor

    sensor = NetworkRiskSensor()
    sensor.copy_libraries = parse_copy_libraries(DECLARATION)
    files = [
        {"path": "apps/PAYR/cobol/P.cbl", "lang_id": "cobol", "raw_imports": ["ONLYPAYR"],
         "import_libraries": {"ONLYPAYR": ["SHRCPY"]}, "classes": [{}]},
        {"path": "apps/PAYR/copybook/ONLYPAYR.cpy", "lang_id": "cobol", "raw_imports": []},
    ]  # fmt: skip
    assert sensor._resolve_edges(files) == {}


def test_a_bad_declaration_is_rejected():
    with pytest.raises(CopyLibraryError):
        parse_copy_libraries({"libraries": {"A": ["x"]}, "syslib": [{"programs": "*", "order": ["B"]}]})
