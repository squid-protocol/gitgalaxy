"""#4420 / #4421: --copy-libraries, the members no declared library holds and the persisted report.

#4420: with the importer's SYSLIB declared, an unqualified COPY none of its libraries holds draws no
edge (the compiler would fail too) -- the default resolver used to link it to a same-named PROGRAM
source -- and is recorded as a gap. A runtime-supplied member (SQLCA, DFHAID) stays unresolved with no
fallback and no gap; an importer no SYSLIB entry covers keeps today's behaviour.
#4421: copy_member_collisions (and the gaps) are in the master DB, so a --db-only scan keeps them.
"""

import json
import sqlite3

from gitgalaxy.core.copy_libraries import parse_copy_libraries
from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

DECLARATION = {
    "libraries": {"PAYRCPY": ["apps/PAYR/copybook"], "SHRCPY": ["shared/copylib"]},
    "syslib": [{"programs": "apps/PAYR/*", "order": ["PAYRCPY", "SHRCPY"]}],
}
MAIN = "apps/PAYR/cobol/PAYMAIN.cbl"


def _file(path, imports=()):
    return {"path": path, "lang_id": "cobol", "raw_imports": list(imports), "classes": [{}]}


def _sensor():
    sensor = NetworkRiskSensor()
    sensor.copy_libraries = parse_copy_libraries(DECLARATION)
    return sensor


def test_a_member_no_declared_library_holds_draws_no_edge_and_is_a_gap():
    sensor = _sensor()
    files = [_file(MAIN, ["ORDPRICE"]), _file("apps/ORDR/cobol/ORDPRICE.cbl")]  # a PROGRAM of that name
    assert sensor._resolve_edges(files) == {}
    assert sensor.copy_gaps == [{"importer": MAIN, "member": "ORDPRICE", "searched": ["PAYRCPY", "SHRCPY"]}]


def test_a_runtime_supplied_member_stays_unresolved_without_a_gap():
    sensor = _sensor()
    files = [_file(MAIN, ["SQLCA", "DFHAID"]), _file("apps/ORDR/cobol/SQLCA.cbl"), _file("x/DFHAID.cbl")]
    assert sensor._resolve_edges(files) == {}
    assert sensor.copy_gaps == []


def test_an_undeclared_importer_keeps_the_default_resolver():
    sensor = _sensor()
    other = "apps/OTHER/cobol/OTHMAIN.cbl"  # no syslib entry matches it
    files = [_file(other, ["ORDPRICE"]), _file("apps/OTHER/cobol/ORDPRICE.cbl")]
    sensor_edges = sensor._resolve_edges(files)
    assert list(sensor_edges) == [(other, "apps/OTHER/cobol/ORDPRICE.cbl")]
    assert sensor.copy_gaps == []
    plain = NetworkRiskSensor()  # no declaration at all
    assert list(plain._resolve_edges(files)) == [(other, "apps/OTHER/cobol/ORDPRICE.cbl")]


def test_a_member_a_declared_library_holds_still_resolves():
    sensor = _sensor()
    files = [_file(MAIN, ["DATEWS"]), _file("apps/PAYR/copybook/DATEWS.cpy")]
    assert list(sensor._resolve_edges(files)) == [(MAIN, "apps/PAYR/copybook/DATEWS.cpy")]
    assert sensor.copy_gaps == []


PAYMAIN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYMAIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DATE.
           COPY DATEWS.
       01  WS-PRICE.
           COPY ORDPRICE.
       PROCEDURE DIVISION.
           GOBACK.
"""
ORDPRICE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ORDPRICE.
       PROCEDURE DIVISION.
           GOBACK.
"""
DATEWS = "           05  WS-CURR-DATE   PIC X(10).\n"


def _scan(tmp_path):
    repo = tmp_path / "estate"
    for rel, text in {
        MAIN: PAYMAIN,
        "apps/PAYR/copybook/DATEWS.cpy": DATEWS,
        "shared/copylib/DATEWS.cpy": DATEWS,
        "apps/ORDR/cobol/ORDPRICE.cbl": ORDPRICE,
    }.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    spec = tmp_path / "libraries.json"
    spec.write_text(json.dumps(DECLARATION), encoding="utf-8")
    return scan_to_db(repo, tmp_path / "scan", extra_args=["--copy-libraries", str(spec)])


def test_a_db_only_scan_persists_collisions_and_gaps_and_the_ir_exposes_them(tmp_path):
    db = _scan(tmp_path)
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT kind, importer, member, library, resolved_path, shadowed, searched "
            "FROM copy_library_finding_data ORDER BY kind"
        ).fetchall()
        dsts = [
            r[0] for r in conn.execute("SELECT d.file_path FROM edge_data e JOIN file_data d ON d.id = e.dst_file_id")
        ]
    finally:
        conn.close()
    assert "apps/ORDR/cobol/ORDPRICE.cbl" not in dsts  # the program source is not a copybook
    assert rows == [
        (
            "collision",
            MAIN,
            "DATEWS",
            "PAYRCPY",
            "apps/PAYR/copybook/DATEWS.cpy",
            '[{"library": "SHRCPY", "paths": ["shared/copylib/DATEWS.cpy"]}]',
            None,
        ),
        ("gap", MAIN, "ORDPRICE", None, None, None, '["PAYRCPY", "SHRCPY"]'),
    ]
    ir = load_galaxy_ir(db)
    assert [c["member"] for c in ir.copy_member_collisions()] == ["DATEWS"]
    assert ir.copy_member_collisions()[0]["shadowed"] == [{"library": "SHRCPY", "paths": ["shared/copylib/DATEWS.cpy"]}]
    assert ir.copy_member_gaps() == [
        {"kind": "gap", "importer": MAIN, "member": "ORDPRICE", "searched": ["PAYRCPY", "SHRCPY"]}
    ]


def test_a_scan_without_a_declaration_records_nothing(tmp_path):
    repo = tmp_path / "estate"
    (repo / "cobol").mkdir(parents=True)
    (repo / "cobol/PAYMAIN.cbl").write_text(PAYMAIN, encoding="utf-8")
    db = scan_to_db(repo, tmp_path / "scan")
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM copy_library_finding_data").fetchone() == (0,)
    finally:
        conn.close()
    assert load_galaxy_ir(db).copy_findings == []
