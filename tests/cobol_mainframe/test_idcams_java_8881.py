"""The IDCAMS step in Java (cobolrt/job/Idcams.java, #8881 / #8880) against its oracle model (det/idcams_model.py).

GnuCOBOL has no IDCAMS, so the model is the oracle and the Java is a second implementation of the same rules
(IBM z/OS DFSMS Access Method Services Commands, SC23-6846-60): every deck below runs through both, and the return
codes, the log, the catalog, the sequential datasets, the records read through each path and the text of every
refusal must agree byte for byte. One JVM runs every scenario (one javac, one java).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gitgalaxy.tools.cobol_to_java.det import idcams_model as M  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.dfsort import Refused  # noqa: E402
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up
from javac_server import jdk_bin  # noqa: E402

JOB_RT = ROOT / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt" / "job"
BASE, AIX, PATH = "APP.TRAN.KSDS", "APP.TRAN.KSDS.AIX", "APP.TRAN.KSDS.AIX.PATH"

STEP20 = f"""   DEFINE ALTERNATEINDEX (NAME({AIX})-
   RELATE({BASE})                    -
   KEYS(4 4)                         -
   NONUNIQUEKEY                      -
   UPGRADE                           -
   RECORDSIZE(40,40)                 -
   VOLUMES(VOL001)                   -
   CYLINDERS(5,1))                   -
   DATA (NAME({AIX}.DATA))           -
   INDEX (NAME({AIX}.INDEX))
"""
STEP25 = f"   DEFINE PATH (NAME({PATH}) -\n    PATHENTRY({AIX}))\n"
STEP30 = f"   BLDINDEX INDATASET({BASE}) -\n   OUTDATASET({AIX})\n"
DEFINE = " DEFINE CLUSTER (NAME(APP.TRAN.VSAM) INDEXED KEYS(4 0) RECORDSIZE(8 8) CYLINDERS(1 1) VOLUMES(VOL001))\n"


def rec(pk: str, ak: str, tail: str = "..") -> bytes:
    return (pk + ak + tail).encode()


ROWS = [rec("0001", "BBBB"), rec("0002", "AAAA"), rec("0003", "BBBB"), rec("0004", "CCCC"), rec("0005", "AAAA")]


def base(indexed: bool = True, rows=ROWS) -> dict:
    if indexed:
        return {BASE: M.Cluster(BASE, True, 4, 0, 10, 10, sorted(rows))}
    return {BASE: M.Cluster(BASE, False, 0, 0, 10, 10, list(rows))}


def seq(*records: bytes, lrecl: int = 10, disp: str = "OLD") -> M.Sequential:
    return M.Sequential(lrecl, list(records), disp)


SCENARIOS: dict[str, tuple[dict, dict, list[str]]] = {
    "job-ksds": (base(), {}, [STEP20, STEP25, STEP30]),
    "job-esds": (base(False), {}, [STEP20, STEP25, STEP30]),
    "path-read": (
        base(),
        {"OUT": seq(), "P": M.Vsam(BASE)},
        [STEP20, STEP25, STEP30, f" REPRO INDATASET({PATH}) OUTFILE(OUT)\n"],
    ),
    "repro-out": (
        {"APP.TRAN.VSAM": M.Cluster("APP.TRAN.VSAM", True, 4, 0, 8, 8, [b"0001xxxx", b"0009xxxx"])},
        {"IN": M.Vsam("APP.TRAN.VSAM"), "OUT": M.Sequential(8, [b"old!old!"])},
        [" REPRO INFILE(IN) OUTFILE(OUT)\n"],
    ),
    "repro-load": (
        {"APP.TRAN.VSAM": M.Cluster("APP.TRAN.VSAM", True, 4, 0, 8, 8)},
        {"IN": M.Sequential(8, [b"0003aaaa", b"0005bbbb"])},
        [" REPRO INFILE(IN) OUTDATASET(APP.TRAN.VSAM)\n"],
    ),
    "repro-out-of-order": (
        {"K": M.Cluster("K", True, 4, 0, 8, 8)},
        {"IN": M.Sequential(8, [b"0002aaaa", b"0001bbbb"])},
        [" REPRO INFILE(IN) OUTDATASET(K)\n"],
    ),
    "delete-missing-set-maxcc": (
        {},
        {},
        [" DELETE APP.GONE CLUSTER PURGE\n SET MAXCC = 0\n", " DELETE APP.GONE\n IF LASTCC = 8 THEN SET MAXCC = 4\n"],
    ),
    "define-then-duplicate": ({}, {}, [DEFINE, DEFINE + " IF MAXCC > 8 THEN DO\n SET MAXCC = 12\n END\n"]),
    "if-else": (
        {},
        {},
        [
            DEFINE
            + " IF LASTCC EQ 0 THEN SET MAXCC = 3\n ELSE SET MAXCC = 9\n DELETE NO.SUCH\n IF MAXCC GE 3 THEN -\n DELETE NO.SUCH2\n"
        ],
    ),
    "comma-and-comment": (
        base(),
        {},
        [f"/* build it */\n DEFINE AIX (NAME({AIX}), RELATE({BASE}), KEYS(4, 4), RECSZ(40 40) )\n"],
    ),
    "dup-aix": (base(), {}, [STEP20, STEP20]),
    "unique-over-dups": (base(), {}, [STEP20.replace("NONUNIQUEKEY", "UNIQUEKEY"), STEP25, STEP30]),
    "unique-over-distinct": (
        base(rows=[rec("0001", "AAAA"), rec("0002", "BBBB")]),
        {},
        [STEP20.replace("NONUNIQUEKEY", "UNIQUEKEY"), STEP25, STEP30],
    ),
    "busiest-key-too-big": (base(), {}, [STEP20.replace("RECORDSIZE(40,40)", "RECORDSIZE(20,20)"), STEP25, STEP30]),
    "path-before-build": (base(), {"OUT": seq()}, [STEP20, STEP25, f" REPRO INDATASET({PATH}) OUTFILE(OUT)\n"]),
    "stale-dd": (
        {"APP.TRAN.VSAM": M.Cluster("APP.TRAN.VSAM", True, 4, 0, 8, 8, [b"0001xxxx"])},
        {"IN": M.Vsam("APP.TRAN.VSAM"), "OUT": M.Sequential(8)},
        [
            " DELETE APP.TRAN.VSAM\n DEFINE CLUSTER (NAME(APP.TRAN.VSAM) INDEXED KEYS(4 0) RECORDSIZE(8 8))\n"
            " REPRO INFILE(IN) OUTFILE(OUT)\n"
        ],
    ),
    "missing-dd-cluster": ({}, {"IN": M.Vsam("NOPE")}, [" DELETE X\n"]),
}

REFUSED_DECKS = {
    "quoted": " DELETE 'APP.X'\n",
    "unterminated-comment": " DELETE A /* oops\n",
    "print": " PRINT INFILE(IN)\n",
    "listcat": " LISTCAT ENTRIES(A)\n",
    "else-alone": " ELSE DELETE A\n",
    "if-no-then": " IF LASTCC = 0 DELETE A\n",
    "if-bad-cond": " IF FOO = 0 THEN DELETE A\n",
    "set-lastcc": " SET LASTCC = 0\n",
    "set-big": " SET MAXCC = 99\n",
    "set-nan": " SET MAXCC = X\n",
    "do-no-end": " IF LASTCC = 0 THEN DO\n DELETE A\n",
    "empty": " /* nothing */\n",
    "unbalanced": " DELETE (A\n",
    "noname": " DELETE\n",
    "nouniq": f" DEFINE ALTERNATEINDEX (NAME(A.NEW) RELATE({BASE}) KEYS(4 4) RECORDSIZE(40 40) NOUPGRADE)\n",
    "unique-twice": f" DEFINE ALTERNATEINDEX (NAME(A.NEW) RELATE({BASE}) KEYS(4 4) RECORDSIZE(40 40) UNIQUEKEY NONUNIQUEKEY)\n",
    "keys-outside": f" DEFINE ALTERNATEINDEX (NAME(A.NEW) RELATE({BASE}) KEYS(8 4) RECORDSIZE(40 40))\n",
    "relate-gone": " DEFINE ALTERNATEINDEX (NAME(A.NEW) RELATE(APP.GONE) KEYS(4 4) RECORDSIZE(40 40))\n",
    "no-recordsize": f" DEFINE ALTERNATEINDEX (NAME(A.NEW) RELATE({BASE}) KEYS(4 4))\n",
    "data-twice": f" DEFINE ALTERNATEINDEX (NAME(A.NEW) RELATE({BASE}) KEYS(4 4) RECORDSIZE(40 40)) DATA(NAME(A.D)) DATA(NAME(A.E))\n",
    "path-over-base": f" DEFINE PATH (NAME(A.P) PATHENTRY({BASE}))\n",
    "path-gone": " DEFINE PATH (NAME(A.P) PATHENTRY(NOPE.AIX))\n",
    "path-cyl": f" DEFINE PATH (NAME(A.P) PATHENTRY({AIX}) CYLINDERS(1 1))\n",
    "cluster-nokeys": " DEFINE CLUSTER (NAME(A.C) INDEXED RECORDSIZE(8 8))\n",
    "cluster-bad-keys": " DEFINE CLUSTER (NAME(A.C) INDEXED KEYS(9 0) RECORDSIZE(8 8))\n",
    "cluster-nonindexed-keys": " DEFINE CLUSTER (NAME(A.C) NONINDEXED KEYS(4 0) RECORDSIZE(8 8))\n",
    "bld-infile": " BLDINDEX INFILE(IN) OUTFILE(OUT)\n",
    "bld-one": f" BLDINDEX INDATASET({BASE})\n",
    "bld-twice": f" BLDINDEX IDS({BASE}) INDATASET({BASE}) ODS({AIX})\n",
    "bld-pw": f" BLDINDEX INDATASET({BASE}/PW) OUTDATASET({AIX})\n",
    "repro-zero": " REPRO INFILE(IN) OUTFILE(OUT)\n",
    "repro-self": " REPRO INFILE(OUT) OUTFILE(OUT)\n",
    "repro-lrecl": " REPRO INFILE(IN) OUTFILE(OUT)\n",
    "repro-no-dd": " REPRO INFILE(NOPE) OUTFILE(OUT)\n",
    "repro-one": " REPRO INFILE(IN)\n",
}


def py_render(catalog: dict, dds: dict, decks: list[str]) -> list[str]:
    """The model's side of the driver's output for one scenario."""
    out: list[str] = []
    for sysin in decks:
        try:
            r = M.run(sysin, catalog, dds)
        except Refused as e:
            out.append(f"REFUSED {e}")
            continue
        out.append(f"RC {r.rc} {r.lastcc} {r.maxcc}")
        out += [f"LOG {line}" for line in r.log]
        for e in r.catalog.values():
            out.append("CAT " + describe(e))
        out += [f"DS {k} {hexes(v.records)}" for k, v in r.datasets.items()]
        for e in r.catalog.values():
            if isinstance(e, M.Path):
                try:
                    v = hexes(M.path_records(r.catalog, e.name))
                except Refused as x:
                    v = f"REFUSED {x}"
                out.append(f"PATH {e.name} {v}")
        catalog = r.catalog
    return out


def hexes(recs: list[bytes]) -> str:
    return ",".join(r.hex() for r in recs) or "-"


def jbool(v: bool) -> str:
    return "true" if v else "false"


def describe(e) -> str:
    if isinstance(e, M.Cluster):
        return f"CLUSTER {e.name} {jbool(e.indexed)} {e.key_len} {e.key_off} {e.avg} {e.max} {hexes(e.records)}"
    if isinstance(e, M.Aix):
        return (
            f"AIX {e.name} {e.relate} {e.key_len} {e.key_off} {e.avg} {e.max} {jbool(e.unique)} "
            f"{jbool(e.upgrade)} {jbool(e.built)}"
        )
    return f"PATH {e.name} {e.aix} {jbool(e.update)}"


def spec_lines(catalog: dict, dds: dict, deck_files: list[Path]) -> list[str]:
    lines = ["RESET"]
    for c in catalog.values():
        lines.append(f"CLUSTER {c.name} {int(c.indexed)} {c.key_len} {c.key_off} {c.avg} {c.max} {hexes(c.records)}")
    for name, d in dds.items():
        if isinstance(d, M.Vsam):
            lines.append(f"VSAM {name} {d.name}")
        else:
            lines.append(f"SEQ {name} {d.lrecl} {d.disp} {hexes(d.records)}")
    lines += [f"STEP {f}" for f in deck_files]
    return lines


def all_scenarios() -> dict[str, tuple[dict, dict, list[str]]]:
    out = dict(SCENARIOS)
    plain = base()
    for name, deck in REFUSED_DECKS.items():
        cat = {"APP.TRAN.VSAM": M.Cluster("APP.TRAN.VSAM", True, 4, 0, 8, 8)} if name == "repro-lrecl" else plain
        dds = {"IN": seq(rec("0099", "ZZZZ")), "OUT": seq()}
        if name == "repro-zero":
            dds["IN"] = seq()
        if name == "repro-lrecl":
            dds = {"IN": M.Sequential(7, [b"abcdefg"]), "OUT": M.Vsam("APP.TRAN.VSAM")}
        out["refused-" + name] = (cat, dds, [deck])
    return out


@pytest.fixture(scope="module")
def java_output(tmp_path_factory) -> dict[str, list[str]]:
    bin_dir = jdk_bin()
    if bin_dir is None:
        pytest.skip("no JDK (JDK_17 / JAVA_HOME)")
    work = tmp_path_factory.mktemp("idcams")
    src = work / "src" / "p" / "cobolrt" / "job"
    src.mkdir(parents=True)
    (src / "Idcams.java").write_text(
        (JOB_RT / "Idcams.java").read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8"
    )
    javac_run(
        [
            str(bin_dir / "javac"),
            "-encoding",
            "UTF-8",
            "-nowarn",
            "-d",
            str(work / "classes"),
            str(src / "Idcams.java"),
        ],
        check=True,
    )  # noqa: S603
    spec: list[str] = []
    for i, (name, (cat, dds, decks)) in enumerate(all_scenarios().items()):
        files = []
        for j, deck in enumerate(decks):
            f = work / f"deck{i}_{j}.txt"
            f.write_text(deck, encoding="utf-8")
            files.append(f)
        spec.append(f"# {name}")  # a comment: skipped below
        spec += spec_lines(cat, dds, files)
    spec_file = work / "spec.txt"
    spec_file.write_text("\n".join(x for x in spec if not x.startswith("#")) + "\n", encoding="utf-8")
    got = subprocess.run(  # noqa: S603
        [
            str(bin_dir / "java"),
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-cp",
            str(work / "classes"),
            "p.cobolrt.job.Idcams",
            str(spec_file),
        ],
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout
    chunks = got.split("--\n")[1:]  # one chunk per scenario, in order
    names = list(all_scenarios())
    assert len(chunks) == len(names)
    return {n: c.splitlines() for n, c in zip(names, chunks, strict=True)}


@pytest.mark.parametrize("name", list(all_scenarios()))
def test_the_java_step_agrees_with_the_model(name, java_output):
    cat, dds, decks = all_scenarios()[name]
    want = py_render(cat, dds, decks)
    assert java_output[name] == want


def test_the_model_decks_do_what_they_are_named_for():
    """The comparison above would pass if both sides refused everything: pin the outcomes the scenarios rely on."""
    jobs = py_render(*all_scenarios()["job-ksds"])
    assert [x for x in jobs if x.startswith("RC")] == ["RC 0 0 0"] * 3
    assert any(x.startswith("PATH ") and "REFUSED" not in x for x in jobs)
    assert all(
        x.startswith("REFUSED") for n, c in all_scenarios().items() if n.startswith("refused-") for x in py_render(*c)
    )
    assert py_render(*all_scenarios()["delete-missing-set-maxcc"])[0] == "RC 0 8 0"
