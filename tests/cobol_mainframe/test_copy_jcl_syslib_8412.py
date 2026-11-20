"""#8412: a compile job's `//SYSLIB DD` concatenation names which library wins when two hold the same member. With no
`--copy-libraries`, an unqualified COPY resolves in the compile JCL's order (a library is the directory named after a
dataset's last qualifier). Authored fixtures (invented names): the reader over the class (EXEC PGM= and IGYW* procs,
qualified step DD names, continuation DDs, unreadable entries, conflicting jobs) and real scans for the order."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gitgalaxy.core.copy_libraries import _jcl_compiles, jcl_syslib_orders
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

ITEM_A = "           05  FAKE-A  PIC X(1).\n"
ITEM_B = "           05  FAKE-B  PIC X(2).\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. MAINPG.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n           COPY REC1.\n       PROCEDURE DIVISION.\n"
    "           GOBACK.\n"
)


def job(*dds: str, exec_line: str = "//COB      EXEC PGM=IGYCRCTL,PARM='LIB'", member: str = "MAINPG") -> str:
    return (
        "//FAKEJOB  JOB (ACCT),'FAKE'\n"
        + exec_line
        + "\n"
        + "//SYSIN    DD DSN=FAKE.SRC.COBOL("
        + member
        + "),DISP=SHR\n"
        + "".join(dds)
    )


def syslib(*dsns: str, name: str = "SYSLIB") -> str:
    return "".join(
        (f"//{name:<8} DD " if i == 0 else "//         DD ") + f"DSN={d},DISP=SHR\n" for i, d in enumerate(dsns)
    )


def test_a_concatenation_is_read_in_written_order_by_last_qualifier():
    text = job(syslib("FAKE.PROD.COPYB", "FAKE.PROD.COPYA"))
    assert _jcl_compiles(text) == [("MAINPG", ["COPYB", "COPYA"])]


def test_a_proc_call_reads_its_qualified_step_dds():
    text = job(syslib("FAKE.COPYB", name="COBOL.SYSLIB"), exec_line="//COBOL    EXEC IGYWC").replace(
        "//SYSIN ", "//COBOL.SYSIN "
    )
    assert _jcl_compiles(text) == [("MAINPG", ["COPYB"])]


def test_a_library_named_twice_counts_once():
    assert _jcl_compiles(job(syslib("A.LIBX", "B.LIBY", "C.LIBX"))) == [("MAINPG", ["LIBX", "LIBY"])]


@pytest.mark.parametrize(
    "text",
    [
        job(syslib("FAKE.COPYB", "&HLQ..COPYA")),  # a symbolic library: the order is unknown
        job(syslib("FAKE.COPYB(MEM)")),  # a member-qualified dataset
        job(syslib("FAKE.COPYB"), member="&MEMBER"),  # SYSIN is not a literal member
        job("//STEPLIB  DD DSN=FAKE.LOAD,DISP=SHR\n"),  # no SYSLIB at all
        job(syslib("FAKE.COPYB"), exec_line="//LKED     EXEC PGM=IEWL"),  # not a compile step
        "garbage\n",
    ],
    ids=["symbolic", "member", "sysin-symbolic", "no-syslib", "not-a-compile", "not-jcl"],
)
def test_entries_that_name_no_readable_order_declare_nothing(text):
    assert _jcl_compiles(text) == []


def test_a_following_dd_is_not_part_of_the_concatenation():
    text = job(syslib("FAKE.COPYB"), "//SYSPRINT DD SYSOUT=*\n//SYSUT1   DD DSN=FAKE.WORK,DISP=SHR\n")
    assert _jcl_compiles(text) == [("MAINPG", ["COPYB"])]


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_two_jobs_that_disagree_declare_nothing_for_that_program(tmp_path):
    write(tmp_path, "jcl/A.jcl", job(syslib("X.LIBA", "X.LIBB")))
    write(tmp_path, "jcl/B.jcl", job(syslib("X.LIBB", "X.LIBA")))
    write(tmp_path, "jcl/C.jcl", job(syslib("X.LIBA"), member="OTHERPG"))
    assert jcl_syslib_orders(str(tmp_path)) == {"OTHERPG": ["LIBA"]}


def test_two_jobs_that_agree_declare_the_order(tmp_path):
    write(tmp_path, "jcl/A.jcl", job(syslib("X.LIBA", "X.LIBB")))
    write(tmp_path, "proc/B.prc", job(syslib("Y.LIBA", "Y.LIBB")))
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["LIBA", "LIBB"]}


def estate(tmp_path: Path, order: list[str]) -> Path:
    repo = tmp_path / "fakeestate"
    write(repo, "apps/MAINPG.cbl", PROGRAM)
    write(repo, "q/LIBQ/REC1.cpy", ITEM_B)
    write(repo, "p/LIBP/REC1.cpy", ITEM_A)
    write(repo, "jcl/BUILD.jcl", job(syslib(*[f"FAKE.PROD.{n}" for n in order])))
    return repo


def edges_of(repo: Path, tmp: Path) -> set[str]:
    ir = load_galaxy_ir(scan_to_db(repo, tmp / "out"))
    return set(ir.copy_resolution("apps/MAINPG.cbl")["edges"].get("apps/MAINPG.cbl", ()))


@pytest.mark.parametrize(
    ("order", "winner"),
    [(["LIBQ", "LIBP"], "q/LIBQ/REC1.cpy"), (["LIBP", "LIBQ"], "p/LIBP/REC1.cpy")],
    ids=["q-first", "p-first"],
)
def test_the_compile_jcl_order_decides_which_same_name_member_a_copy_reads(tmp_path, order, winner):
    assert edges_of(estate(tmp_path, order), tmp_path) == {winner}
