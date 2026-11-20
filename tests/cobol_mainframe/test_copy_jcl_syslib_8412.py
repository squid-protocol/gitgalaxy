"""#8412: a compile job's `//SYSLIB DD` concatenation names which library wins when two hold the same member. With no
`--copy-libraries`, an unqualified COPY resolves in the compile JCL's order (a library is the directory named after a
dataset's last qualifier). Authored fixtures (invented names): the reader over the class (EXEC PGM= and IGYW* procs,
qualified step DD names, continuation DDs, unreadable entries, conflicting jobs) and real scans for the order."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gitgalaxy.core.copy_libraries import _compile_steps, _jcl_compiles, jcl_syslib_orders
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


# --- JCLLIB ORDER=: a compile step that calls a cataloged proc found along the PROCLIB order ---

PROC = (
    "//FAKECOB  PROC MEMBER=\n"
    "//COB      EXEC PGM=IGYCRCTL,PARM='LIB'\n"
    "//SYSLIB   DD DSN=FAKE.PROD.COPYB,DISP=SHR\n"
    "//         DD DSN=FAKE.PROD.COPYA,DISP=SHR\n"
    "//FAKECOB  PEND\n"
)


def call_job(*dds: str, jcllib: str = "FAKE.PROCLIB1,FAKE.PROCLIB2", step: str = "COB", member: str = "MAINPG") -> str:
    return (
        "//FAKEJOB  JOB (ACCT),'FAKE'\n"
        f"//PROCS    JCLLIB ORDER=({jcllib})\n"
        "//BUILD    EXEC FAKECOB\n"
        f"//{step}.SYSIN DD DSN=FAKE.SRC.COBOL({member}),DISP=SHR\n" + "".join(dds)
    )


def test_a_proc_found_along_jcllib_supplies_the_syslib(tmp_path):
    write(tmp_path, "proclib/PROCLIB1/FAKECOB.prc", PROC)
    write(tmp_path, "jcl/BUILD.jcl", call_job())
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB", "COPYA"]}


def test_the_first_jcllib_library_holding_the_proc_wins(tmp_path):
    write(tmp_path, "pl/PROCLIB1/FAKECOB.prc", PROC)
    write(tmp_path, "pl/PROCLIB2/FAKECOB.prc", PROC.replace("COPYB", "COPYZ"))
    write(tmp_path, "jcl/BUILD.jcl", call_job())
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB", "COPYA"]}
    write(tmp_path, "jcl/BUILD.jcl", call_job(jcllib="FAKE.PROCLIB2,FAKE.PROCLIB1"))
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYZ", "COPYA"]}


def test_a_call_override_replaces_the_whole_concatenation(tmp_path):
    write(tmp_path, "pl/PROCLIB1/FAKECOB.prc", PROC)
    write(tmp_path, "jcl/BUILD.jcl", call_job(syslib("FAKE.OWN.COPYQ", name="COB.SYSLIB")))
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYQ"]}


@pytest.mark.parametrize(
    "jcllib",
    ["FAKE.OTHERLIB", ""],
    ids=["proc-library-not-listed", "no-jcllib"],
)
def test_a_proc_outside_the_jcllib_order_declares_nothing(tmp_path, jcllib):
    write(tmp_path, "pl/PROCLIB1/FAKECOB.prc", PROC)
    text = (
        call_job(jcllib=jcllib)
        if jcllib
        else call_job().replace("//PROCS    JCLLIB ORDER=(FAKE.PROCLIB1,FAKE.PROCLIB2)\n", "")
    )
    write(tmp_path, "jcl/BUILD.jcl", text)
    assert jcl_syslib_orders(str(tmp_path)) == {}


def test_a_proc_with_a_symbolic_library_declares_nothing(tmp_path):
    write(tmp_path, "pl/PROCLIB1/FAKECOB.prc", PROC.replace("FAKE.PROD.COPYB", "&HLQ..COPYB"))
    write(tmp_path, "jcl/BUILD.jcl", call_job())
    assert jcl_syslib_orders(str(tmp_path)) == {}


def test_the_jcllib_order_decides_which_same_name_member_a_copy_reads(tmp_path):
    repo = tmp_path / "fakeestate"
    write(repo, "apps/MAINPG.cbl", PROGRAM)
    write(repo, "q/COPYB/REC1.cpy", ITEM_B)
    write(repo, "p/COPYA/REC1.cpy", ITEM_A)
    write(repo, "pl/PROCLIB1/FAKECOB.prc", PROC)
    write(repo, "jcl/BUILD.jcl", call_job())
    assert edges_of(repo, tmp_path) == {"q/COPYB/REC1.cpy"}


# --- symbolic SYSLIB datasets: PROC defaults, SET, and the call's keyword symbols ---

SYMPROC = PROC.replace("PROC MEMBER=", "PROC HLQ=FAKE.PROD,MEMBER=").replace("FAKE.PROD.COPYB", "&HLQ..COPYB")


def sym_job(*, set_line: str = "", params: str = "", dds: str = "") -> str:
    return call_job(dds).replace("//BUILD    EXEC FAKECOB\n", set_line + f"//BUILD    EXEC FAKECOB{params}\n")


def sym_orders(tmp_path: Path, job_text: str, proc: str = SYMPROC) -> dict[str, list[str]]:
    write(tmp_path, "pl/PROCLIB1/FAKECOB.prc", proc)
    write(tmp_path, "jcl/BUILD.jcl", job_text)
    return jcl_syslib_orders(str(tmp_path))


def test_a_proc_default_resolves_a_symbolic_library(tmp_path):
    assert sym_orders(tmp_path, sym_job()) == {"MAINPG": ["COPYB", "COPYA"]}


def test_the_call_keyword_symbol_overrides_the_proc_default(tmp_path):
    proc = SYMPROC.replace("&HLQ..COPYB", "&HLQ..&LIBN.")
    job_text = sym_job(params=",HLQ=FAKE.TEST,LIBN=COPYT")
    assert sym_orders(tmp_path, job_text, proc) == {"MAINPG": ["COPYT", "COPYA"]}


def test_a_set_symbol_fills_a_name_the_proc_does_not_default(tmp_path):
    proc = SYMPROC.replace("HLQ=FAKE.PROD,", "")
    assert sym_orders(tmp_path, sym_job(set_line="//         SET HLQ='FAKE.SET'\n"), proc) == {
        "MAINPG": ["COPYB", "COPYA"]
    }


def test_a_set_that_clashes_with_a_proc_default_is_unresolved(tmp_path):
    assert sym_orders(tmp_path, sym_job(set_line="//         SET HLQ=FAKE.OTHER\n")) == {}


def test_a_call_keyword_symbol_settles_that_clash(tmp_path):
    job_text = sym_job(set_line="//         SET HLQ=FAKE.OTHER\n", params=",HLQ=FAKE.MINE")
    assert sym_orders(tmp_path, job_text) == {"MAINPG": ["COPYB", "COPYA"]}


def test_a_symbol_nothing_assigns_stays_unresolved(tmp_path):
    assert sym_orders(tmp_path, sym_job(), SYMPROC.replace("HLQ=FAKE.PROD,", "")) == {}


def test_a_symbolic_library_in_a_direct_compile_step_reads_the_jobs_set():
    text = "//         SET HLQ=FAKE.PROD\n" + job(syslib("&HLQ..COPYB", "FAKE.PROD.COPYA"))
    assert _jcl_compiles(text.replace("//         SET", "//S1       SET")) == [("MAINPG", ["COPYB", "COPYA"])]


# --- an in-stream PROC .. PEND (searched before the libraries) and INCLUDE groups spliced in place ---


def instream_job(
    call: str = "//BUILD    EXEC FAKECOB\n", proc: str = PROC, pre: str = "", member: str = "MAINPG"
) -> str:
    return (
        "//FAKEJOB  JOB (ACCT),'FAKE'\n" + pre + proc + call + f"//COB.SYSIN DD DSN=FAKE.SRC.COBOL({member}),DISP=SHR\n"
    )


def test_an_instream_proc_call_reads_the_procs_syslib(tmp_path):
    assert sym_orders(tmp_path, instream_job(), PROC) == {"MAINPG": ["COPYB", "COPYA"]}
    # the job alone holds it: no proc library is needed
    (tmp_path / "pl/PROCLIB1/FAKECOB.prc").unlink()
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB", "COPYA"]}


def test_an_instream_proc_wins_over_a_library_member_of_the_same_name(tmp_path):
    write(tmp_path, "pl/PROCLIB1/FAKECOB.prc", PROC.replace("COPYB", "COPYZ"))
    write(tmp_path, "jcl/BUILD.jcl", instream_job(pre="//PROCS    JCLLIB ORDER=(FAKE.PROCLIB1)\n"))
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB", "COPYA"]}


def test_an_instream_proc_that_is_never_called_still_declares_nothing_twice(tmp_path):
    # no call: the template's own literal SYSIN is read as a direct compile, as for a library member
    proc = PROC.replace("//SYSLIB", "//SYSIN    DD DSN=FAKE.SRC.COBOL(OWNPG),DISP=SHR\n//SYSLIB")
    write(tmp_path, "jcl/BUILD.jcl", "//FAKEJOB  JOB (ACCT),'FAKE'\n" + proc)
    assert jcl_syslib_orders(str(tmp_path)) == {"OWNPG": ["COPYB", "COPYA"]}


def test_a_called_instream_template_declares_through_its_call_only(tmp_path):
    proc = PROC.replace("//SYSLIB", "//SYSIN    DD DSN=FAKE.SRC.COBOL(OWNPG),DISP=SHR\n//SYSLIB")
    write(tmp_path, "jcl/BUILD.jcl", instream_job(proc=proc))
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB", "COPYA"]}  # the call's SYSIN names the program


def test_an_instream_proc_default_does_not_leak_to_a_later_step():
    text = instream_job(proc=SYMPROC) + "//S2       EXEC PGM=IGYCRCTL\n" + syslib("&HLQ..COPYQ") + "\n"
    steps = _compile_steps(text)
    assert [s["libs"] for s in steps] == [["COPYB", "COPYA"], [], None]


def test_the_call_symbol_settles_an_instream_proc_with_a_job_set(tmp_path):
    job_text = instream_job(
        proc=SYMPROC, call="//BUILD    EXEC FAKECOB,HLQ=FAKE.TEST\n", pre="//         SET HLQ=FAKE.SET\n"
    )
    write(tmp_path, "jcl/BUILD.jcl", job_text)
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB", "COPYA"]}


def test_a_job_set_beside_an_instream_default_is_unresolved(tmp_path):
    write(tmp_path, "jcl/BUILD.jcl", instream_job(proc=SYMPROC, pre="//         SET HLQ=FAKE.SET\n"))
    assert jcl_syslib_orders(str(tmp_path)) == {}


def test_an_instream_proc_with_two_compile_steps_is_not_guessed(tmp_path):
    proc = PROC.replace(
        "//FAKECOB  PEND", "//COB2     EXEC PGM=IGYCRCTL\n//SYSLIB   DD DSN=FAKE.OTHER.COPYC,DISP=SHR\n//FAKECOB  PEND"
    )
    write(tmp_path, "jcl/BUILD.jcl", instream_job(proc=proc))
    assert jcl_syslib_orders(str(tmp_path)) == {}


GROUP = "//COPYSL   DD DSN=FAKE.PROD.COPYB,DISP=SHR\n//         DD DSN=FAKE.PROD.COPYA,DISP=SHR\n"


def include_job(order: str = "FAKE.INCLIB", include: str = "SYSLG") -> str:
    return (
        "//FAKEJOB  JOB (ACCT),'FAKE'\n"
        f"//PROCS    JCLLIB ORDER=({order})\n"
        "//COB      EXEC PGM=IGYCRCTL\n"
        "//SYSIN    DD DSN=FAKE.SRC.COBOL(MAINPG),DISP=SHR\n"
        f"//         INCLUDE MEMBER={include}\n"
    )


def test_an_include_group_supplies_the_syslib_dd(tmp_path):
    write(
        tmp_path,
        "inc/INCLIB/SYSLG.jcl",
        "//SYSLIB   DD DSN=FAKE.PROD.COPYB,DISP=SHR\n//         DD DSN=FAKE.PROD.COPYA\n",
    )
    write(tmp_path, "jcl/BUILD.jcl", include_job())
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB", "COPYA"]}


def test_an_include_group_nests_and_follows_the_jcllib_order(tmp_path):
    write(tmp_path, "inc/INCLIB/SYSLG.jcl", "//         INCLUDE MEMBER=SYSLH\n")
    write(tmp_path, "inc/INCLIB/SYSLH.jcl", "//SYSLIB   DD DSN=FAKE.PROD.COPYB,DISP=SHR\n")
    write(tmp_path, "inc/OTHER/SYSLH.jcl", "//SYSLIB   DD DSN=FAKE.PROD.COPYZ,DISP=SHR\n")
    write(tmp_path, "jcl/BUILD.jcl", include_job(order="FAKE.INCLIB,FAKE.OTHER"))
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB"]}


def test_an_include_group_set_resolves_a_symbolic_library(tmp_path):
    write(tmp_path, "inc/INCLIB/SYSLG.jcl", "//         SET HLQ=FAKE.PROD\n")
    text = include_job().replace("//COB      EXEC", "//         INCLUDE MEMBER=SYSLG\n//COB      EXEC", 1)
    text = text.rsplit("//         INCLUDE", 1)[0] + syslib(
        "&HLQ..COPYB"
    )  # the group ahead of the step, SYSLIB after it
    write(tmp_path, "jcl/BUILD.jcl", text)
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB"]}


@pytest.mark.parametrize(
    ("order", "files"),
    [
        ("FAKE.INCLIB", {}),  # the group is in no library
        ("", {"inc/INCLIB/SYSLG.jcl": GROUP}),  # no JCLLIB: nothing says where to look
        ("FAKE.INCLIB", {"inc/INCLIB/SYSLG.jcl": "//STEPN    EXEC PGM=IEWL\n//JOB2     JOB\n"}),  # a JOB inside a group
    ],
    ids=["missing", "no-jcllib", "invalid-group"],
)
def test_an_include_group_that_cannot_be_read_leaves_the_order_unknown(tmp_path, order, files):
    for rel, body in files.items():
        write(tmp_path, rel, body)
    text = include_job(order=order) + syslib("FAKE.PROD.COPYB")
    write(tmp_path, "jcl/BUILD.jcl", text)
    assert jcl_syslib_orders(str(tmp_path)) == {}


def test_an_include_inside_an_instream_proc_is_spliced_in_the_proc(tmp_path):
    proc = "//FAKECOB  PROC\n//COB      EXEC PGM=IGYCRCTL\n//         INCLUDE MEMBER=SYSLG\n//FAKECOB  PEND\n"
    write(tmp_path, "inc/INCLIB/SYSLG.jcl", "//SYSLIB   DD DSN=FAKE.PROD.COPYB,DISP=SHR\n")
    text = instream_job(proc=proc, pre="//PROCS    JCLLIB ORDER=(FAKE.INCLIB)\n")
    write(tmp_path, "jcl/BUILD.jcl", text)
    assert jcl_syslib_orders(str(tmp_path)) == {"MAINPG": ["COPYB"]}
