"""#5401: billpay pays an account's whole balance: COBIL00C MOVEs ACCT-CURR-BAL (S9(10)V99) into TRAN-AMT (S9(9)V99) and
REWRITEs balance minus amount. Every CardDemo account is below 1,000,000.00, so no scenario showed a wide amount, and no
scenario showed the 10th integer digit that the MOVE drops. Two synthetic accounts (appended to the case's own dataset) state
a balance above one million and a balance of ten integer digits, each with its card xref row. Pure JSON/text, no Java."""

import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-billpay"
OVERPUNCH = {c: str(i) for i, c in enumerate("{ABCDEFGHI")}  # positive signed digit -> its last digit
# account -> (scenario, balance in cents)
WIDE = {
    "00000099998": ("pay-balance-over-one-million", 123456789),
    "00000099997": ("pay-balance-ten-integer-digits", 123456789012),
}


def _rows(name, width):
    rows = (CASE / name).read_text(encoding="utf-8").split("\n")
    rows = [r for r in rows if r]
    assert rows and all(len(r) == width for r in rows), name
    return rows


def _cents(field):
    assert len(field) == 12 and field[:-1].isdigit() and field[-1] in OVERPUNCH
    return int(field[:-1] + OVERPUNCH[field[-1]])


def test_the_wide_accounts_hold_the_stated_balances():
    accounts = {r[:11]: r for r in _rows("acctdata-5401.txt", 300)}
    assert set(accounts) == set(WIDE)
    for acct, (_scenario, cents) in WIDE.items():
        assert accounts[acct][11] == "Y"
        assert _cents(accounts[acct][12:24]) == cents
    assert WIDE["00000099997"][1] >= 10**11  # 10 integer digits, one more than TRAN-AMT keeps
    assert WIDE["00000099998"][1] >= 100_000_000  # 1,000,000.00 or more


def test_each_wide_account_has_a_card_xref_row():
    xref = {r[25:36]: r for r in _rows("cardxref-5401.txt", 36)}
    assert set(xref) == set(WIDE)
    assert len({r[:16] for r in xref.values()}) == len(xref)


def test_the_case_appends_both_files_and_pays_each_account():
    case = json.loads((CASE / "case.json").read_text(encoding="utf-8"))
    sets = case["datasets"]
    assert sets["AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS"]["append"] == "@case/acctdata-5401.txt"
    assert sets["AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS"]["append"] == "@case/cardxref-5401.txt"
    by_name = {s["name"]: s for s in case["scenarios"]}
    assert len(by_name) == len(case["scenarios"])
    for acct, (scenario, _cents) in WIDE.items():
        screen = by_name[scenario]["receive"]["COBIL0A"]
        assert screen == {"ACTIDINI": acct, "CONFIRMI": "Y"}
        assert "#5401" in by_name[scenario]["why"]
