"""#3477: ims_gen_data -- IMS PSB / DBD macros and JCL region steps in the master
DB, byte-identical delta restore, and a pre-#3477 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "ims3477", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
_BLANK = {"kind": None, "name": None, "parent": None, "owner": None, "dbd_name": None, "procopt": None,
          "pcb_type": None, "access": None, "bytes": None, "start": None, "psb_name": None, "program": None,
          "attributes": None, "line": 0}  # fmt: skip
PSB = [
    dict(_BLANK, kind="PCB", name="PAUTBPCB", dbd_name="DBPAUTP0", procopt="AP", pcb_type="DB",
         attributes="TYPE=DB,DBDNAME=DBPAUTP0,PROCOPT=AP", line=17),
    dict(_BLANK, kind="SENSEG", name="PAUTSUM0", parent="0", owner="PAUTBPCB", attributes="NAME=PAUTSUM0,PARENT=0",
         line=18),
    dict(_BLANK, kind="PSBGEN", name="PSBPAUTB", attributes="LANG=COBOL,PSBNAME=PSBPAUTB", line=20),
]  # fmt: skip
DBD = [dict(_BLANK, kind="FIELD", name="ACCNTID", parent="PAUTSUM0", owner="DBPAUTP0", access="SEQ", start=1, bytes=6,
            line=7)]  # fmt: skip
JCL = [dict(_BLANK, kind="REGION", name="CBPAUP0C", access="BMP", psb_name="PSBPAUTB", program="CBPAUP0C", line=4)]
UNIVERSE = [
    {"path": "ims/PSBPAUTB.psb", "lang_id": "hlasm", "raw_imports": [], "ims_gen": PSB},
    {"path": "ims/DBPAUTP0.dbd", "lang_id": "hlasm", "raw_imports": [], "ims_gen": DBD},
    {"path": "jcl/CBPAUP0J.jcl", "lang_id": "jcl", "raw_imports": [], "ims_gen": JCL},
]


def _record(db):
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def test_rows_are_recorded_and_restored(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    try:
        got = conn.execute(
            "SELECT kind, name, owner, procopt, start_pos, psb_name FROM ims_gen_data ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert got == [
        ("PCB", "PAUTBPCB", None, "AP", None, None),
        ("SENSEG", "PAUTSUM0", "PAUTBPCB", None, None, None),
        ("PSBGEN", "PSBPAUTB", None, None, None, None),
        ("FIELD", "ACCNTID", "DBPAUTP0", None, 1, None),
        ("REGION", "CBPAUP0C", None, None, None, "PSBPAUTB"),
    ]
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["ims/PSBPAUTB.psb"]["ims_gen"] == PSB
    assert cache["ims/DBPAUTP0.dbd"]["ims_gen"] == DBD
    assert cache["jcl/CBPAUP0J.jcl"]["ims_gen"] == JCL


def test_a_pre_3477_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE ims_gen_data")
    conn.commit()
    conn.close()
    assert StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["ims/PSBPAUTB.psb"]["ims_gen"] == []
