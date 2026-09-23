"""
#3356: csd_resource_data -- every CSD `DEFINE <type>(<name>)` record in the master DB.

These pin the properties the design turns on:
  1. Resources ride on each deck's own `csd_resources` payload (a per-file fact),
     and every DEFINE becomes a row with its join attributes lifted into columns.
  2. transaction_data is unchanged: the same deck still writes its transaction
     map there, beside (not instead of) its resource rows.
  3. The table cascade-deletes with file_data, so a re-record of the same
     snapshot does not accumulate duplicate rows.
  4. A delta scan restores an unchanged deck's resources byte-identically, and a
     baseline written before the table existed restores nothing (no error).
"""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "csd3356", "latest_commit_date": "2026-09-23T00:00:00Z"},
}


def _res(resource_type, name, line, **kw):
    row = {
        "resource_type": resource_type,
        "name": name,
        "group": "CARDDEMO",
        "dsname": None,
        "ddname": None,
        "record_format": None,
        "key_length": None,
        "record_size": None,
        "queue_type": None,
        "plan": None,
        "db2_entry": None,
        "transid": None,
        "program": None,
        "attributes": "GROUP(CARDDEMO)",
        "line": line,
    }
    row.update(kw)
    return row


# carddemo's CARDDEMO.CSD / CRDDEMOD.csd shapes, as the extractor emits them.
RESOURCES = [
    _res("FILE", "ACCTDAT", 1, dsname="AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS", record_format="V", key_length=11),
    _res("TDQUEUE", "JOBS", 499, ddname="INREADER", record_format="FIXED", record_size=80, queue_type="EXTRA"),
    _res("DB2ENTRY", "CARDDEMO", 520, plan="CARDDEMO"),
    _res("DB2TRAN", "CTLITRAN", 526, db2_entry="CARDDEMO", transid="CTLI"),
    _res("TRANSACTION", "CTLI", 530, transid="CTLI", program="COTRTLIC"),
]

UNIVERSE = [
    {
        "path": "app/csd/CARDDEMO.CSD",
        "lang_id": "csd",
        "raw_imports": [],
        "csd_resources": RESOURCES,
        "transaction_defs": [
            {"transid": "CTLI", "program": "COTRTLIC", "group": "CARDDEMO", "profile": None, "line": 530}
        ],
    },
    {"path": "app/cbl/COTRTLIC.cbl", "lang_id": "cobol", "raw_imports": []},
]
TRANSACTIONS = [
    {
        "src_path": "app/csd/CARDDEMO.CSD",
        "transid": "CTLI",
        "program": "COTRTLIC",
        "group": "CARDDEMO",
        "profile": None,
        "resolved_path": "app/cbl/COTRTLIC.cbl",
        "line": 530,
    }
]

SELECT = (
    "SELECT f.file_path, resource_type, resource_name, group_name, dsname, ddname, record_format, key_length, "
    "record_size, queue_type, plan, db2_entry, transid, program, attributes, line_number "
    "FROM csd_resource_data r JOIN file_data f ON r.file_id = f.id ORDER BY 1, line_number"
)


def _record(db, universe=UNIVERSE):
    RecordKeeper().record_mission(
        [dict(f) for f in universe], [], {}, SESSION, str(db), transactions=[dict(t) for t in TRANSACTIONS]
    )
    return db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_every_define_becomes_a_row_with_its_join_attributes(tmp_path):
    rows = _rows(_record(tmp_path / "m.db"), SELECT)
    deck = "app/csd/CARDDEMO.CSD"
    assert rows == [
        (deck, "FILE", "ACCTDAT", "CARDDEMO", "AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS", None, "V", 11, None, None, None,
         None, None, None, "GROUP(CARDDEMO)", 1),
        (deck, "TDQUEUE", "JOBS", "CARDDEMO", None, "INREADER", "FIXED", None, 80, "EXTRA", None, None, None, None,
         "GROUP(CARDDEMO)", 499),
        (deck, "DB2ENTRY", "CARDDEMO", "CARDDEMO", None, None, None, None, None, None, "CARDDEMO", None, None, None,
         "GROUP(CARDDEMO)", 520),
        (deck, "DB2TRAN", "CTLITRAN", "CARDDEMO", None, None, None, None, None, None, None, "CARDDEMO", "CTLI", None,
         "GROUP(CARDDEMO)", 526),
        (deck, "TRANSACTION", "CTLI", "CARDDEMO", None, None, None, None, None, None, None, None, "CTLI", "COTRTLIC",
         "GROUP(CARDDEMO)", 530),
    ]  # fmt: skip


def test_transaction_data_is_written_exactly_as_before(tmp_path):
    db = _record(tmp_path / "m.db")
    assert _rows(db, "SELECT transid, program, group_name, line_number FROM transaction_data") == [
        ("CTLI", "COTRTLIC", "CARDDEMO", 530)
    ]


def test_a_file_with_no_deck_records_none(tmp_path):
    db = _record(tmp_path / "m.db")
    (count,) = _rows(
        db,
        "SELECT COUNT(*) FROM csd_resource_data r JOIN file_data f ON r.file_id = f.id "
        "WHERE f.file_path = 'app/cbl/COTRTLIC.cbl'",
    )[0]
    assert count == 0


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "m.db"
    _record(db)
    _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM csd_resource_data")[0][0] == len(RESOURCES)


def test_an_unchanged_deck_keeps_its_resources_through_a_delta_scan(tmp_path):
    """Restored payload == extracted payload, so a full and an incremental scan write
    the same csd_resource_data rows (the fact-channel byte-identical rule)."""
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["app/csd/CARDDEMO.CSD"]["csd_resources"] == RESOURCES
    assert cache["app/cbl/COTRTLIC.cbl"]["csd_resources"] == []

    delta_db = tmp_path / "delta.db"
    restored = [dict(node, path=path) for path, node in cache.items()]
    _record(delta_db, restored)
    assert _rows(delta_db, SELECT) == _rows(db, SELECT)


def test_a_pre_3356_baseline_rehydrates_with_no_resources(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE csd_resource_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["app/csd/CARDDEMO.CSD"]["csd_resources"] == []
