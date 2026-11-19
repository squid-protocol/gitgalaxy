"""#8625: mainframe credential shapes through the real Vault Sentinel (nothing mocked), planted case and near-miss each.

Every value is invented. Members carry no file extension, as on a PDS export.
"""

import sys

import pytest

import gitgalaxy.tools.supply_chain_security.vault_sentinel as sentinel
from gitgalaxy.security.mainframe_secrets import mainframe_secret_hits

PW = "PASS" + "WORD"  # split so no scanner reads this file as a leak
DD_FTP = "//INPUT    DD *\n"

PLANTED = {
    "jcl job card": f"//PAYJOB   JOB (ACCT),'PAY',CLASS=A,{'PASSWORD'}=S3CR3T1,\n//STEP1 EXEC PGM=IEFBR14\n",
    "jcl job card new password": "//PAYJOB   JOB (ACCT),'PAY',PASSWORD=(OLDPW123,NEWPW456)\n",
    "jcl exec parm": f"//STEP1 EXEC PGM=LOADER,PARM='USER=BATCH1 {PW}=Xy7pq2'\n",
    "ftp in-stream user": "//FTPSTEP  EXEC PGM=FTP\n" + DD_FTP + "10.1.2.3\nUSER BATCH1 Xy7pq2\nPUT A B\n/*\n",
    "ftp in-stream login": "//FTPSTEP  EXEC PGM=FTP\n" + DD_FTP + "10.1.2.3\nBATCH1\nPASS Xy7pq2\n/*\n",
    "db2 connect rexx": '/* REXX */\naddress tso\n"db2 connect to PRODDB user batch1 using Xy7pq2"\n',
    "db2 connect embedded sql": "       EXEC SQL CONNECT TO PRODDB USER BATCH1 USING 'Xy7pq2' END-EXEC.\n",
    "db2 connect wrapped over lines": "       EXEC SQL CONNECT TO PRODDB\n           USER BATCH1\n           USING 'Xy7pq2'\n       END-EXEC.\n",
    "rexx literal next to user": "/* REXX */\nuserid = 'BATCH1'\npw = 'Xy7pq2'\n",
    "clist literal next to user": "PROC 0\nSET &USERID = BATCH1\nSET &PW = Xy7pq2\n",
}

NEAR_MISS = {
    "jcl symbolic": "//PAYJOB   JOB (ACCT),'PAY',PASSWORD=&PW\n",
    "jcl exec symbolic parm": f"//STEP1 EXEC PGM=LOADER,PARM='USER=BATCH1 {PW}=&PW'\n",
    "jcl comment": f"//* SET {PW}=XXXXXXX BEFORE SUBMIT, FROM THE VAULT\n",
    "ftp symbolic": "//FTPSTEP  EXEC PGM=FTP\n" + DD_FTP + "10.1.2.3\nUSER BATCH1 &FTPPW\n/*\n",
    "ftp user only": "//FTPSTEP  EXEC PGM=FTP\n" + DD_FTP + "10.1.2.3\nUSER BATCH1\n/*\n",
    "ftp lines outside a data card": "USER BATCH1 Xy7pq2\nPASS Xy7pq2\n",
    "db2 host variable": "       EXEC SQL CONNECT TO :LOC USER :UID USING :PWD END-EXEC.\n",
    "db2 wrapped host variable": "       EXEC SQL CONNECT TO :LOC\n           USER :UID\n           USING :PWD\n       END-EXEC.\n",
    "db2 connect prose then unrelated lines": "The CONNECT TO step is manual.\nUSER guide pages follow.\nUSING the vault is required.\n",
    "db2 comment": "      * EXEC SQL CONNECT TO PRODDB USER BATCH1 USING 'Xy7pq2' END-EXEC.\n",
    "rexx comment": "/* REXX\n userid = 'BATCH1'\n pw = 'Xy7pq2'\n*/\nsay 'done'\n",
    "rexx empty and computed": "userid = 'BATCH1'\npw = ''\npw2 = value('PWENV')\n",
    "rexx literal with no user": "pw = 'Xy7pq2'\n",
    "clist symbolic": "SET &USERID = BATCH1\nSET &PW = &SYSPW\n",
    "racf doc member": f"# Resetting a user\nALTUSER BATCH1 {'PASSWORD'}(NEWPW01) NOEXPIRED\nThe {PW} operand sets a temporary value.\n",
}


@pytest.mark.parametrize("kind", PLANTED)
def test_a_planted_shape_is_counted(kind):
    assert mainframe_secret_hits(PLANTED[kind]) >= 1


@pytest.mark.parametrize("kind", NEAR_MISS)
def test_a_near_miss_is_not_counted(kind):
    assert mainframe_secret_hits(NEAR_MISS[kind]) == 0


def _scan(tmp_path, monkeypatch, files: dict) -> int:
    root = tmp_path / "planted"
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    monkeypatch.setattr(sys, "argv", ["vault_sentinel.py", str(root)])
    try:
        sentinel.main()
    except SystemExit as e:
        return int(e.code or 0)
    return 0


@pytest.mark.parametrize("kind", PLANTED)
@pytest.mark.parametrize("rel", ["jcl/PAYJOB", "proclib/PAYPROC.jcl", "exec/BATCHX.rexx", "clist/BATCHC"])
def test_a_real_scan_fails_ci_on_a_planted_shape(kind, rel, tmp_path, monkeypatch, capsys):
    assert _scan(tmp_path, monkeypatch, {rel: PLANTED[kind]}) == 1
    out = capsys.readouterr().out
    assert "CONTENT BREACH" in out and rel in out
    assert "Xy7pq2" not in out and "S3CR3T1" not in out, "a detected secret must never be logged"


@pytest.mark.parametrize("kind", NEAR_MISS)
def test_a_real_scan_passes_a_near_miss(kind, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {"jcl/PAYJOB": NEAR_MISS[kind]}) == 0


def test_a_clean_jcl_member_passes(tmp_path, monkeypatch):
    jcl = "//PAYJOB   JOB (ACCT),'PAY',CLASS=A\n//STEP1 EXEC PGM=IEFBR14\n//SYSPRINT DD SYSOUT=*\n"
    assert _scan(tmp_path, monkeypatch, {"jcl/PAYJOB": jcl}) == 0
