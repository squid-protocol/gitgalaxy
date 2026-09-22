# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#3247: the forge-side independent CICS transaction reader (the `old` side of the
refraction differential's transaction datum)."""

from pathlib import Path

from gitgalaxy.tools.cobol_to_cobol.cics_transaction_reader import _deck_transactions, extract_transactions

# A CEDA/DFHCSDUP EXTRACT dump: a leading blank column, DEFINE, then KEYWORD(value)
# operands with audit trailers and paren-nested values that a flat reader truncates.
CEDA_DUMP = """\
 DEFINE TRANSACTION(OCRA) GROUP(BANK) PROGRAM(BNK1CRA)
        PROFILE(DFHCICST) WAITTIME(0,0,0) STATUS(ENABLED)
        DEFINETIME(22/05/13 12:56:44) DESCRIPTION(CREDIT ACCOUNT)
 DEFINE TRANSACTION(OTFN) GROUP(BANK) PROGRAM(BNK1TFN)
"""

# A hand-written DFHCSDUP SYSIN member: `*` column-1 comments, DELETE GROUP, and a
# DEFINE DB2TRAN whose TRANSID(...) is a DB2 attribute, not a transaction.
SYSIN_MEMBER = """\
*
* Copyright IBM Corp. 2023
*
 DELETE GROUP(BANK)
 DEFINE TRANSACTION(OCCS) GROUP(BANK)
 DESCRIPTION('BANK Online Credit/Debit')
        PROGRAM(BNK1CCS)
 DEFINE DB2TRAN(DB2T) GROUP(BANK) TRANSID(XXXX) ENTRY(BANKENT)
"""

# An autoinstall pairing declared from the program's side, plus inline JCL framing.
INLINE_JCL = """\
//CSDUP    EXEC PGM=DFHCSDUP,REGION=0M
//SYSIN    DD *
 DEFINE PROGRAM(COSGN00C) GROUP(CARDDEMO) TRANSID(CC00)
* DEFINE PROGRAM(COMMENTED) GROUP(CARDDEMO) TRANSID(ZZZZ)
 DEFINE TRANSACTION(CAUP) GROUP(CARDDEMO) PROGRAM(COACTUPC)
/*
"""


def test_ceda_dump_transaction_program():
    assert _deck_transactions(CEDA_DUMP) == [("OCRA", "BNK1CRA"), ("OTFN", "BNK1TFN")]


def test_sysin_member_and_db2tran_excluded():
    # The multi-line DEFINE TRANSACTION(OCCS) ... PROGRAM(BNK1CCS) is one record;
    # DEFINE DB2TRAN's TRANSID(XXXX) is a DB2 attribute and must not appear.
    assert _deck_transactions(SYSIN_MEMBER) == [("OCCS", "BNK1CCS")]


def test_inline_jcl_autoinstall_pairing_and_comment_skipped():
    pairs = _deck_transactions(INLINE_JCL)
    assert ("CC00", "COSGN00C") in pairs  # DEFINE PROGRAM ... TRANSID autoinstall
    assert ("CAUP", "COACTUPC") in pairs
    assert not any(t == "ZZZZ" for t, _ in pairs)  # `*`-commented DEFINE skipped


def test_extract_transactions_over_a_repo(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "BANK.csd").write_text(CEDA_DUMP + SYSIN_MEMBER, encoding="utf-8")
    (tmp_path / "install.jcl").write_text(INLINE_JCL, encoding="utf-8")
    # A JCL that does not run DFHCSDUP is not a CSD deck and yields nothing.
    (tmp_path / "compile.jcl").write_text(
        "//STEP EXEC PGM=IGYCRCTL\n DEFINE TRANSACTION(NOPE) PROGRAM(X)\n", encoding="utf-8"
    )

    by_program = extract_transactions(tmp_path)
    assert by_program["BNK1CRA"] == {"OCRA"}
    assert by_program["BNK1CCS"] == {"OCCS"}
    assert by_program["COSGN00C"] == {"CC00"}
    assert by_program["COACTUPC"] == {"CAUP"}
    assert "X" not in by_program  # the non-DFHCSDUP JCL contributed nothing
