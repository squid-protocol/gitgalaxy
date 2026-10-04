# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""The scan-DB slice of the golden master (#4109)."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden_db_snapshot as gds  # noqa: E402
import golden_diff  # noqa: E402


def _db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE file_data (id INTEGER PRIMARY KEY, file_path TEXT);
        CREATE TABLE function_data (id INTEGER PRIMARY KEY, file_id INT, func_name TEXT, start_line INT,
            func_archetype TEXT, func_z_score REAL, calls_out_to TEXT, func_fan_in INT, func_fan_out INT,
            func_pagerank REAL, usage_status INT, token_mass INT);
        CREATE TABLE edge_data (id INTEGER PRIMARY KEY, src_file_id INT, dst_file_id INT, edge_kind TEXT);
        INSERT INTO file_data VALUES (1, 'src/a.py'), (2, 'src/b.py'), (3, 'docs/x.md');
        INSERT INTO function_data VALUES
            (1, 1, 'run', 10, 'Compute Cores', 0.1234567, '["helper"]', 0, 1, 0.0123456789, 0, 99),
            (2, 1, 'helper', 20, 'Defensive Guards', -1.0, '[]', 1, 0, 0.5, 0, 7),
            (3, 1, 'helper', 20, 'Defensive Guards', -1.0, '[]', 0, 0, 0.5, 1, 7);
        INSERT INTO edge_data VALUES (1, 1, 2, 'import');
        """
    )
    conn.commit()
    conn.close()


def _audit():
    return {
        gds.PARSED: {
            "src": {"Files": {"src/a.py": {}, "src/b.py": {}}},
            "docs": {"Files": {"docs/x.md": {}}},
        }
    }


def test_attach_folds_function_rows_and_edges(tmp_path):
    db = tmp_path / "data_galaxy_master.db"
    _db(db)
    audit = gds.attach(_audit(), db)
    files = audit[gds.PARSED]["src"]["Files"]
    a = files["src/a.py"][gds.SECTION]
    assert a["Function Archetype"] == {
        "run@10": "Compute Cores",
        "helper@20": "Defensive Guards",
        "helper@20#2": "Defensive Guards",  # exact name+line collision keeps both rows
    }
    assert a["Calls Out To"]["run@10"] == ["helper"]
    assert a["PageRank"]["run@10"] == 0.012346  # rounded: summation-order noise is not drift
    assert a["Import Edges"] == ["import:src/b.py"]
    assert "Token Mass" not in a  # mode-dependent, left out
    assert gds.SECTION not in files["src/b.py"]  # no functions, no outgoing edges
    assert gds.SECTION not in audit[gds.PARSED]["docs"]["Files"]["docs/x.md"]


def test_db_for_audit(tmp_path):
    audit = tmp_path / "data_galaxy_audit.json"
    audit.write_text("{}", encoding="utf-8")
    assert gds.db_for_audit(audit) is None
    _db(tmp_path / "data_galaxy_master.db")
    assert gds.db_for_audit(audit) == tmp_path / "data_galaxy_master.db"
    assert gds.db_for_audit(tmp_path) is None  # a fixture directory never gets it


def test_load_and_sanitize_attaches_for_a_fresh_scan(tmp_path):
    audit_path = tmp_path / "data_galaxy_audit.json"
    audit_path.write_text(json.dumps(_audit()), encoding="utf-8")
    _db(tmp_path / "data_galaxy_master.db")
    data = golden_diff.load_and_sanitize(str(audit_path))
    assert gds.SECTION in data[gds.PARSED]["src"]["Files"]["src/a.py"]
