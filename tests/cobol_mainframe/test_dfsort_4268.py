"""A JCL SORT step (DFSORT control statements) lowered to a COBOL SORT program (det/dfsort.py, #4268): the parser and
its refusals, and the step proven byte for byte -- GnuCOBOL runs the lowered program (the oracle), the det port's
Java runs its translation -- on the burned estate's SORT steps (CardDemo TRANREPT, SORTTEST, COMBTRAN)."""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run
from test_det_programs import PKG, _batch_package, _cobol, _java, _runtime_classes

from gitgalaxy.tools.cobol_to_java.det import dfsort as D

# CardDemo app/proc/TRANREPT.prc STEP05R (the JCL's symbols and cards, verbatim)
TRANREPT_SYM = """TRAN-CARD-NUM,263,16,ZD
TRAN-PROC-DT,305,10,CH
PARM-START-DATE,C'2022-01-01' //Date format yyyy-mm-dd
PARM-END-DATE,C'2022-07-06' //Date format yyyy-mm-dd
"""
TRANREPT_SYSIN = """ SORT FIELDS=(TRAN-CARD-NUM,A)
 INCLUDE COND=(TRAN-PROC-DT,GE,PARM-START-DATE,AND,
    TRAN-PROC-DT,LE,PARM-END-DATE)
"""
# CardDemo samples/jcl/SORTTEST.jcl
SORTTEST_SYM = """TRAN-CARD-NUM,263,16,ZD
TRAN-PROC-DT,305,10,CH
PARM-DATE,C'2022-07-18'
"""
SORTTEST_SYSIN = """ SORT FIELDS=(TRAN-CARD-NUM,A)
 INCLUDE COND=(TRAN-PROC-DT,EQ,PARM-DATE)
"""
# CardDemo app/jcl/COMBTRAN.jcl STEP05R: SORTIN is two datasets concatenated
COMBTRAN_SYM = "TRAN-ID,1,16,CH\n"
COMBTRAN_SYSIN = " SORT FIELDS=(TRAN-ID,A)\n"
RECLEN = 350  # CVTRA05Y TRAN-RECORD


def test_tranrept_cards_parse_to_the_model():
    c = D.parse(TRANREPT_SYSIN, TRANREPT_SYM)
    dt = D.Field(305, 10, "CH")
    assert c.verb == "SORT" and not c.equals and not c.omit
    assert c.keys == (D.Key(D.Field(263, 16, "ZD"), False),)
    assert c.cond == D.Logic("AND", D.Cmp(dt, "GE", D.Const("C", "2022-01-01")),
                             D.Cmp(dt, "LE", D.Const("C", "2022-07-06")))  # fmt: skip


def test_and_binds_tighter_than_or_and_parentheses_group():
    c = D.parse(" SORT FIELDS=(1,2,CH,A,3,4,BI,D),EQUALS\n OMIT COND=(1,1,CH,EQ,C'A',OR,2,1,CH,EQ,C'B',&,"
                "3,2,PD,GT,-5)\n")  # fmt: skip
    a = D.Cmp(D.Field(1, 1, "CH"), "EQ", D.Const("C", "A"))
    b = D.Cmp(D.Field(2, 1, "CH"), "EQ", D.Const("C", "B"))
    p = D.Cmp(D.Field(3, 2, "PD"), "GT", D.Const("N", "-5"))
    assert c.equals and c.omit and c.cond == D.Logic("OR", a, D.Logic("AND", b, p))
    assert c.keys[1] == D.Key(D.Field(3, 4, "BI"), True)
    g = D.parse(" SORT FIELDS=(1,2,A),FORMAT=CH\n INCLUDE COND=((1,1,CH,EQ,C'A',OR,2,1,CH,EQ,C'B'),AND,"
                "3,1,CH,NE,4,1,CH)\n").cond  # fmt: skip
    assert isinstance(g, D.Logic) and g.op == "AND" and isinstance(g.left, D.Logic) and g.left.op == "OR"


def test_outrec_items_are_parsed_in_order():
    c = D.parse(" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(1:3,4,5X,2Z,C'a''b',X'f1f2')\n")
    assert c.outrec == (D.Field(3, 4, "CH"), D.Fill(5, False), D.Fill(2, True), D.Const("C", "a'b"), D.Const("X", "F1F2"))


def test_outrec_takes_symbols_and_build_and_continues_lines():
    c = D.parse(" SORT FIELDS=(1,2,CH,A)\n OUTREC BUILD=(ACCT,K,\n 2X,ACCT,CH)\n", "ACCT,5,3\nK,C'-'\n")
    assert c.outrec == (D.Field(5, 3, "CH"), D.Const("C", "-"), D.Fill(2, False), D.Field(5, 3, "CH"))


def test_option_equals_and_copy_and_comments():
    c = D.parse("* a comment\n OPTION EQUALS\n SORT FIELDS=COPY\n END\n SORT FIELDS=(1,1,CH,A)\n")
    assert (c.verb, c.keys, c.equals) == ("COPY", (), True)


@pytest.mark.parametrize(
    ("sysin", "why"),
    [
        (" SORT FIELDS=(1,2,CH,A)\n INREC FIELDS=(1,2)\n", "the INREC statement"),
        (" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(2:3,2)\n", "OUTREC position 2: with the next free byte at 1"),
        (" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(1,2,5:1,1)\n", "OUTREC position 5: with the next free byte at 3"),
        (" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(1,2,ZD)\n", "OUTREC a ZD field"),
        (" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(1,2,C'')\n", "only non-empty"),
        (" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(1,2,7)\n", "a field of 7"),
        (" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(1,2),OVERLAY=(3:C'A')\n", "OUTREC operands OVERLAY"),
        (" SORT FIELDS=(1,2,CH,A)\n OUTREC FIELDS=(1,2)\n OUTREC FIELDS=(1,2)\n", "a second OUTREC"),
        (" SORT FIELDS=(1,2,CH,A)\n SUM FIELDS=NONE\n", "the SUM statement"),
        (" SORT FIELDS=(1,4,FI,A)\n", "format FI"),
        (" SORT FIELDS=(1,2,CH,A)\n OPTION VLSHRT\n", "OPTION VLSHRT"),
        (" SORT FIELDS=(1,2,CH,A)\n INCLUDE COND=(1,2,CH,EQ,3,3,CH)\n", "CH 2 bytes against CH 3 bytes"),
        (" SORT FIELDS=(1,2,CH,A)\n INCLUDE COND=(1,2,ZD,EQ,C'12')\n", "a ZD field against a C constant"),
        (" SORT FIELDS=(1,2,CH,A)\n INCLUDE COND=(1,2,CH,EQ,12)\n", "a CH field against a decimal constant"),
        (" SORT FIELDS=(1,2,CH,A),SKIPREC=5\n", "SORT operands SKIPREC"),
        ("LBL SORT FIELDS=(1,2,CH,A)\n", "a control statement label"),
        (" INCLUDE COND=(1,2,CH,EQ,C'AB')\n", "no SORT or MERGE statement"),
    ],
)
def test_what_the_model_does_not_cover_is_refused_by_name(sysin, why):
    with pytest.raises(D.Refused, match=why):
        D.parse(sysin)


def test_lowering_refuses_what_cobol_would_answer_differently():
    with pytest.raises(D.Refused, match="MERGE without EQUALS"):
        D.cobol_program(D.parse(" MERGE FIELDS=(1,2,CH,A)\n"), 80, ["SORTIN01", "SORTIN02"])
    with pytest.raises(D.Refused, match="outside the 80-byte record"):
        D.cobol_program(D.parse(" SORT FIELDS=(79,4,CH,A)\n"), 80, ["SORTIN"])
    with pytest.raises(D.Refused, match="19 digits"):
        D.cobol_program(D.parse(" SORT FIELDS=(1,10,PD,A)\n"), 80, ["SORTIN"])


def _tran(rng: random.Random, card: int, day: str) -> bytes:
    """A CVTRA05Y-shaped record: TRAN-ID 1-16, TRAN-CARD-NUM 263-278 (ZD), TRAN-PROC-TS 305-330."""
    rec = bytearray(rng.choice(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789") for _ in range(RECLEN))
    rec[0:16] = f"{rng.randrange(10**16):016d}".encode()
    rec[262:278] = f"{card:016d}".encode()
    rec[304:314] = day.encode()
    return bytes(rec)


def _days(rng: random.Random) -> str:
    return rng.choice(["2021-12-31", "2022-01-01", "2022-03-15", "2022-07-06", "2022-07-07", "2022-07-18"])


def _java_step(src: str, work: Path, inputs: dict[str, bytes], output: str) -> bytes:
    """The det port of the lowered step on the batch runtime: each input DD a SHR dataset of its name, the output a
    new one; returns the output dataset's bytes."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / "DFSORTST.cbl").write_text(src)
    project = work / "project"
    _batch_package(project / "src/main/java")
    r = P.translate(work / "DFSORTST.cbl", [], "public class DfsortstService {\n}\n", PKG, None, project)
    assert not r.stats["holes"], r.stats["holes"]
    rt_classes = _runtime_classes(True, "ISO-8859-1")
    srcdir = work / "java"
    svc = srcdir / PKG / f"service/{r.service}.java"
    svc.parent.mkdir(parents=True, exist_ok=True)
    svc.write_text(r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", ""))
    data = work / "datasets"
    data.mkdir()
    for dd, body in inputs.items():
        (data / dd).write_bytes(body)
    b = f"{PKG}.batch"
    dds = [f'new {b}.Dd("{d}", "{d}", "SHR", null, null)' for d in inputs]
    dds.append(f'new {b}.Dd("{output}", "{output}", "NEW", "CATLG", null)')
    main_java = srcdir / "Main.java"
    main_java.write_text(
        f"public class Main {{ public static void main(String[] a) {{ new {PKG}.service.{r.service}("
        f'new {b}.DatasetResolver("{data}"), new {b}.CobolFiles("", ""), new {b}.MainframeClock("", "UTC"))'
        f".runBatch(java.util.List.of({', '.join(dds)}), null); }} }}\n"
    )
    jdk = _java()
    classes = work / "classes"
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-cp", str(rt_classes), "-d", str(classes),
               str(svc), str(main_java)], check=True)  # fmt: skip
    cp = os.pathsep.join([str(classes), str(rt_classes)])
    subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", cp, "Main"],
                   capture_output=True, encoding="utf-8", check=True)  # fmt: skip
    return (data / output).read_bytes()


def _steps() -> dict[str, tuple[str, dict[str, bytes]]]:
    """Each burned SORT step's lowered program and synthetic input: distinct card numbers / TRAN-IDs (the steps run
    without EQUALS, so equal keys are left to test_equal_keys_without_equals_stop_the_port_by_name)."""
    rng = random.Random(4268)
    cards = rng.sample(range(10**15, 10**16), 60)
    tran = b"".join(_tran(rng, c, _days(rng)) for c in cards)
    test = b"".join(_tran(rng, c, rng.choice(["2022-07-18", "2022-07-17"])) for c in cards[:30])
    comb = [b"".join(_tran(rng, c, _days(rng)) for c in cards[i::2]) for i in (0, 1)]
    return {
        "TRANREPT": (D.cobol_program(D.parse(TRANREPT_SYSIN, TRANREPT_SYM), RECLEN, ["SORTIN"]), {"SORTIN": tran}),
        "SORTTEST": (D.cobol_program(D.parse(SORTTEST_SYSIN, SORTTEST_SYM), RECLEN, ["SORTIN"]), {"SORTIN": test}),
        "COMBTRAN": (D.cobol_program(D.parse(COMBTRAN_SYSIN, COMBTRAN_SYM), RECLEN, ["SORTIN1", "SORTIN2"]),
                     {"SORTIN1": comb[0], "SORTIN2": comb[1]}),
        # the other forms, on synthetic records: COPY with OMIT; EQUALS with a descending PD key and a BI key
        # (ties kept in input order); MERGE with an INCLUDE on the merged records
        "COPYOMIT": (D.cobol_program(D.parse(" SORT FIELDS=COPY\n OMIT COND=(305,10,CH,LT,C'2022-03',OR,1,1,CH,EQ,"
                                             "X'35')\n"), RECLEN, ["SORTIN"]), {"SORTIN": tran}),
        "EQUALSPD": (D.cobol_program(D.parse(" OPTION EQUALS\n SORT FIELDS=(20,3,PD,D,23,1,BI,A)\n"), RECLEN,
                                     ["SORTIN"]), {"SORTIN": _packed(rng)}),
        # OUTREC: the three writers (GIVING-less SORT, COPY with OMIT, MERGE with INCLUDE) and a carried ZD key
        "OUTRECSORT": (D.cobol_program(D.parse(" SORT FIELDS=(1,16,CH,A)\n OUTREC FIELDS=(1,16,2X,305,10,C'|',X'C1',3Z)\n"),
                                       RECLEN, ["SORTIN"]), {"SORTIN": tran}),
        "OUTRECCOPY": (D.cobol_program(D.parse(" SORT FIELDS=COPY\n OMIT COND=(305,10,CH,LT,C'2022-03')\n"
                                               " OUTREC FIELDS=(305,10,1,16)\n"), RECLEN, ["SORTIN"]),
                       {"SORTIN": tran}),
        "OUTRECMERGE": (D.cobol_program(D.parse(" MERGE FIELDS=(1,16,CH,A),EQUALS\n INCLUDE COND=(305,10,CH,GE,"
                                                "C'2022-03-01')\n OUTREC FIELDS=(305,10,1,16)\n"), RECLEN,
                                        ["SORTIN01", "SORTIN02"]),
                        {"SORTIN01": _by_id(comb[0]), "SORTIN02": _by_id(comb[1])}),
        "OUTRECZD": (D.cobol_program(D.parse(TRANREPT_SYSIN.split("\n", 1)[0] + "\n OUTREC FIELDS=(263,16,1,16)\n",
                                             TRANREPT_SYM), RECLEN, ["SORTIN"]), {"SORTIN": tran}),
        "MERGEINC": (D.cobol_program(D.parse(" MERGE FIELDS=(1,16,CH,A),EQUALS\n INCLUDE COND=(305,10,CH,GE,"
                                             "C'2022-03-01')\n"), RECLEN, ["SORTIN01", "SORTIN02"]),
                     {"SORTIN01": _by_id(comb[0]), "SORTIN02": _by_id(comb[1])}),
    }  # fmt: skip


def _packed(rng: random.Random) -> bytes:
    """Records whose 20-22 is a packed S9(5) (sign C, D or F) from a few values, so keys tie; 23 a byte of 0-3."""
    out = []
    for _ in range(80):
        rec = bytearray(_tran(rng, rng.randrange(10**16), "2022-01-01"))
        v = rng.choice([0, 7, 123, 99999])
        rec[19:22] = bytes.fromhex(f"{v:05d}" + rng.choice("CDF"))
        rec[22] = rng.randrange(4)
        out.append(bytes(rec))
    return b"".join(out)


def _by_id(data: bytes) -> bytes:
    """A MERGE input: its records in TRAN-ID order."""
    return b"".join(sorted(data[i : i + RECLEN] for i in range(0, len(data), RECLEN)))


def _need_java() -> None:
    pytest.importorskip("tree_sitter_language_pack")
    if _java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")


@pytest.mark.slow(reason="javac of the batch runtime and a GnuCOBOL container per step")
@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs EQUIVALENCE_E2E=1 and Docker")  # fmt: skip
@pytest.mark.parametrize("step", ["TRANREPT", "SORTTEST", "COMBTRAN", "COPYOMIT", "EQUALSPD", "MERGEINC",
                                  "OUTRECSORT", "OUTRECCOPY", "OUTRECMERGE", "OUTRECZD"])
def test_sort_step_output_is_gnucobols_byte_for_byte(step, tmp_path):
    _need_java()
    src, inputs = _steps()[step]
    cob = tmp_path / "cobol"
    cob.mkdir()
    for dd, body in inputs.items():
        (cob / dd).write_bytes(body)
    _cobol(src, cob)
    want = (cob / "SORTOUT").read_bytes()
    (tmp_path / "port").mkdir()
    got = _java_step(src, tmp_path / "port", inputs, "SORTOUT")
    out_len = {"OUTRECSORT": 16 + 2 + 10 + 1 + 1 + 3, "OUTRECCOPY": 26, "OUTRECMERGE": 26, "OUTRECZD": 32}.get(step, RECLEN)
    assert len(want) % out_len == 0 and want, "the oracle kept no record"
    assert got == want
    if step in ("TRANREPT", "SORTTEST", "COPYOMIT"):  # the INCLUDE / OMIT kept some records and dropped others
        assert len(want) < len(inputs["SORTIN"])


@pytest.mark.slow(reason="javac of the batch runtime")
def test_equal_keys_without_equals_stop_the_port_by_name(tmp_path):
    """DFSORT's shipped default is EQUALS=NO: the order of records with equal keys is not defined, so two that tie
    and differ stop the run by name instead of taking GnuCOBOL's order as IBM's."""
    _need_java()
    rng = random.Random(1)
    data = b"".join(_tran(rng, 4000123412341234, "2022-03-15") for _ in range(2))
    src = D.cobol_program(D.parse(TRANREPT_SYSIN, TRANREPT_SYM), RECLEN, ["SORTIN"])
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_step(src, tmp_path, {"SORTIN": data}, "SORTOUT")
    assert "without DUPLICATES: records with equal keys" in e.value.stderr
