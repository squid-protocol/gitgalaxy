"""
#3477: IMS PSB / DBD generation macros (core/ims_gen.py) through `extract_boundary`
as hlasm -- CardDemo DLIGSAMP / DBPAUTP0 shapes: labeled and unlabeled PCBs, SENSEG
ownership, a column-72 continuation, SEGM BYTES / PARENT=((X,)), FIELD SEQ, LCHILD
pairing -- and JCL DFSRRC00 region steps through the jcl dialect.
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary


def _rows(dialect: str, src: str) -> list[dict]:
    return [{k: v for k, v in r.items() if v and k != "attributes"} for r in extract_boundary(dialect, src)["ims_gen"]]


def _cont(first: str, *more: str) -> str:
    """A statement continued at column 72, each following line resuming at column 16."""
    lines = [first.ljust(71) + "X"] + [" " * 15 + m for m in more[:-1]]
    lines = [lines[0]] + [ln.ljust(71) + "X" for ln in lines[1:]] + [" " * 15 + more[-1]]
    return "\n".join(lines)


def test_psb_pcbs_and_their_sensegs():
    src = "\n".join(
        [
            "* a comment line with PCB in it",
            "         PRINT NOGEN",
            "PAUTBPCB PCB   TYPE=DB,DBDNAME=DBPAUTP0,PROCOPT=GOTP,KEYLEN=14",
            "         SENSEG  NAME=PAUTSUM0,PARENT=0",
            "         SENSEG  NAME=PAUTDTL1,PARENT=PAUTSUM0,PROCOPT=G",
            "         PCB   TYPE=GSAM,DBDNAME=PASFLDBD,PROCOPT=LS",
            "         PSBGEN  LANG=COBOL,PSBNAME=DLIGSAMP,CMPAT=NO",
            "         END",
        ]
    )
    assert _rows("hlasm", src) == [
        {"kind": "PCB", "name": "PAUTBPCB", "dbd_name": "DBPAUTP0", "procopt": "GOTP", "pcb_type": "DB", "line": 3},
        {"kind": "SENSEG", "name": "PAUTSUM0", "parent": "0", "owner": "PAUTBPCB", "line": 4},
        {"kind": "SENSEG", "name": "PAUTDTL1", "parent": "PAUTSUM0", "owner": "PAUTBPCB", "procopt": "G", "line": 5},
        {"kind": "PCB", "name": "PCB@6", "dbd_name": "PASFLDBD", "procopt": "LS", "pcb_type": "GSAM", "line": 6},
        {"kind": "PSBGEN", "name": "DLIGSAMP", "line": 7},
    ]


def test_dbd_segments_fields_and_a_continuation():
    src = "\n".join(
        [
            _cont("       DBD     NAME=DBPAUTP0,ACCESS=(HIDAM,VSAM),PASSWD=NO,", "VERSION="),
            "DSG001 DATASET DD1=DDPAUTP0,SIZE=(4096),SCAN=3",
            _cont("       SEGM    NAME=PAUTSUM0,PARENT=0,BYTES=100,RULES=(,HERE),", "POINTER=(TWINBWD)"),
            "       FIELD   NAME=(ACCNTID,SEQ,U),START=1,BYTES=6,TYPE=P",
            _cont("       LCHILD  NAME=(PAUTINDX,DBPAUTX0),", "POINTER=INDX"),
            "       SEGM    NAME=PAUTDTL1,PARENT=((PAUTSUM0,)),BYTES=200",
            "       FIELD   NAME=CTS,START=9,BYTES=8",
            "       DBDGEN",
        ]
    )
    assert _rows("hlasm", src) == [
        {"kind": "DBD", "name": "DBPAUTP0", "access": "HIDAM", "line": 1},
        {"kind": "DATASET", "name": "DDPAUTP0", "owner": "DBPAUTP0", "line": 3},
        {"kind": "SEGM", "name": "PAUTSUM0", "parent": "0", "owner": "DBPAUTP0", "bytes": 100, "line": 4},
        {"kind": "FIELD", "name": "ACCNTID", "parent": "PAUTSUM0", "owner": "DBPAUTP0", "access": "SEQ",
         "start": 1, "bytes": 6, "line": 6},
        {"kind": "LCHILD", "name": "PAUTINDX", "parent": "PAUTSUM0", "owner": "DBPAUTP0", "dbd_name": "DBPAUTX0",
         "line": 7},
        {"kind": "SEGM", "name": "PAUTDTL1", "parent": "PAUTSUM0", "owner": "DBPAUTP0", "bytes": 200, "line": 9},
        {"kind": "FIELD", "name": "CTS", "parent": "PAUTDTL1", "owner": "DBPAUTP0", "start": 9, "bytes": 8,
         "line": 10},
    ]  # fmt: skip


def test_jcl_ims_region_steps():
    src = "\n".join(
        [
            "//IMSJOB   JOB (1),'X'",
            "//STEP01   EXEC PGM=DFSRRC00,",
            "//             PARM='BMP,PAUDBUNL,PAUTBUNL,,,,,'",
            "//STEP02   EXEC PGM=IEFBR14",
            "//STEP03   EXEC PGM=DFSRRC00,PARM=(DLI,DBUNLDGS,DLIGSAMP)",
        ]
    )
    assert _rows("jcl", src) == [
        {"kind": "REGION", "name": "PAUDBUNL", "access": "BMP", "psb_name": "PAUTBUNL", "program": "PAUDBUNL",
         "line": 2},
        {"kind": "REGION", "name": "DBUNLDGS", "access": "DLI", "psb_name": "DLIGSAMP", "program": "DBUNLDGS",
         "line": 5},
    ]  # fmt: skip


def test_plain_assembler_draws_nothing():
    assert extract_boundary("hlasm", "MAIN     CSECT\n         LA    1,PCB\n         BR    14\n")["ims_gen"] == []
