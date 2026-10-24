"""#4507: the CBSA CRECUST case on generated Db2 rows is committed, and what it does not prove is named.

CRECUST's only Db2 statement is INSERT INTO PROCTRAN: it reads no ACCOUNT, CUSTOMER or CONTROL row, so PROCTRAN is
the one table with rows to generate. These checks need no corpus and no Docker; the proof is
`det_port.py run cbsa-crecust-generated` (16 scenarios, 13/37 paragraphs, recorded in det_sweep_coverage/).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import equivalence_db2 as db2  # noqa: E402

CASE_DIR = ROOT / "tests/equivalence/cbsa-crecust-generated"
SCRATCH_DDL = """
CREATE TABLE IBMUSER.PROCTRAN (
    PROCTRAN_EYECATCHER CHAR(4) NOT NULL,
    PROCTRAN_SORTCODE CHAR(6) NOT NULL,
    PROCTRAN_NUMBER CHAR(8) NOT NULL,
    PROCTRAN_DATE DATE,
    PROCTRAN_AMOUNT DECIMAL(12, 2)
);
"""


def _case() -> dict:
    return json.loads((CASE_DIR / "case.json").read_text(encoding="utf-8"))


def test_the_case_generates_only_proctran_rows_and_keeps_the_five_children():
    case = _case()
    assert case["program"] == "CRECUST" and case["db2"]["seed"] == "@generate"
    assert list(case["db2"]["generate"]["tables"]) == ["IBMUSER.PROCTRAN"]
    assert case["db2"]["compare"] == ["IBMUSER.PROCTRAN"] and case["db2"]["compare_sql"] is True
    assert case["child_programs"] == {f"OCR{n}": f"CRDTAGY{n}" for n in range(1, 6)}
    assert case["port_from"] == "cbsa-crecust" and not case["scenarios"]
    for f in ("customer.txt", "abndfile.bin", "LICENSE", "NOTICE"):
        assert (CASE_DIR / f).is_file()


def test_generated_dates_of_birth_all_stop_before_ceedays():
    # a date of birth from 1601 on reaches CEEDAYS's 10-over-8-byte picture (L1): the oracle refuses the whole case
    gen = _case()["scenario_generate"]
    dobs = gen["commarea"]["SUBPGM-DATE-OF-BIRTH"]["values"]
    assert dobs and all(len(d) == 8 and d.isdigit() and int(d[4:]) < 1601 for d in dobs)
    # the name and address rules reach one byte and a full field
    assert min(map(len, gen["commarea"]["SUBPGM-NAME"]["values"])) == 1
    assert len(gen["commarea"]["SUBPGM-NAME"]["values"]) > 1 and gen["count"] >= len(dobs)


def test_proctran_rows_are_generated_the_same_each_time():
    tables = db2.parse_tables(SCRATCH_DDL)
    case = {"db2": {"ddl": [], "seed": "@generate", "compare": [],
                    "generate": {"seed": 4507, "tables": {"IBMUSER.PROCTRAN": {"rows": 12}}}}}  # fmt: skip
    rows, _ = db2.generate_rows(case, Path("."), tables)
    assert len(rows) == 12 and {t for t, _ in rows} == {"IBMUSER.PROCTRAN"}
    assert any(r["PROCTRAN_DATE"] is None for _, r in rows)  # a NULL in the nullable column
    assert db2.generate_rows(case, Path("."), tables)[0] == rows


def test_notes_name_every_hole_and_forbid_recording():
    notes = _case()["notes"]
    for word in ("L1", "X18", "ASSUMED", "a partial reach"):
        assert word in notes
    assert "NOT PROVABLE" not in notes
