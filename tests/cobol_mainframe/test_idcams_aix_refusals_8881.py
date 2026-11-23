"""#8881 [c:f2434ba0]: every IDCAMS alternate-index / path / BLDINDEX shape the oracle does not model is refused by name.

One table of decks, each with the catalog it runs against and the words its refusal must carry. Three checks over it:
the model refuses each by name (never a code, never a silent accept), the Java step (cobolrt/job/Idcams.java) says the
same text (needs a JDK), and a source scan of idcams_model.py fails when a `Refused(...)` site about an alternate index,
a path or BLDINDEX has no table row that would match its message, so a new refusal cannot land untested."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_idcams_java as eij

from gitgalaxy.tools.cobol_to_java.det import idcams_model as M
from gitgalaxy.tools.cobol_to_java.det.dfsort import Refused

BASE, AIX, PATH = "APP.TRAN.KSDS", "APP.TRAN.KSDS.AIX", "APP.TRAN.KSDS.AIX.PATH"
ROWS = [b"0001BBBB..", b"0002AAAA..", b"0003BBBB..", b"0004CCCC..", b"0005AAAA.."]
DEF_AIX = f" DEFINE ALTERNATEINDEX (NAME({AIX}) RELATE({BASE}) -\n KEYS(4 4) RECORDSIZE(40 40))\n"
DEF_PATH = f" DEFINE PATH (NAME({PATH}) PATHENTRY({AIX}))\n"
BLD = f" BLDINDEX INDATASET({BASE}) OUTDATASET({AIX})\n"


def _base(rows=ROWS) -> dict:
    return {BASE: M.Cluster(BASE, True, 4, 0, 10, 10, sorted(rows))}


OTHER = "APP.OTHER.KSDS"
UNIQ = f" DEFINE ALTERNATEINDEX (NAME({AIX}) RELATE({BASE}) -\n KEYS(4 4) UNIQUEKEY RECORDSIZE(40 40))\n"
SMALL = (
    f" DEFINE ALTERNATEINDEX (NAME({AIX}) RELATE({BASE}) -\n KEYS(4 4) RECORDSIZE(16 16))\n"  # a 2-record key needs 17
)


def _setup(state: str) -> tuple[str, dict]:
    """The commands that bring the catalog to `state`, run in the same deck (the Java step starts from clusters only)."""
    cat = _base([] if state == "empty" else ROWS)
    if state == "two":
        cat[OTHER] = M.Cluster(OTHER, True, 4, 0, 10, 10, [b"0001XXXX.."])
    text = {"base": "", "empty": DEF_AIX, "two": DEF_AIX, "unique": UNIQ, "small": SMALL,
            "defined": DEF_AIX + DEF_PATH, "built": DEF_AIX + DEF_PATH + BLD}[state]  # fmt: skip
    return text, cat


def _aix(extra: str = "", keys: str = "KEYS(4 4)", relate: str = BASE, name: str = AIX) -> str:
    return f" DEFINE ALTERNATEINDEX (NAME({name}) -\n RELATE({relate}) -\n {keys} RECORDSIZE(40 40) {extra})\n"


# (deck, catalog state, the words the refusal carries): one row per shape the oracle does not model
CASES = [
    # DEFINE ALTERNATEINDEX
    (_aix("NOUPGRADE"), "base", "NOUPGRADE"),
    (_aix("UNIQUEKEY NONUNIQUEKEY"), "base", "stated twice"),
    (_aix("REUSE"), "base", "ALTERNATEINDEX REUSE parameter"),
    (_aix(keys=""), "base", "ALTERNATEINDEX without KEYS"),
    (_aix(keys="KEYS(8 4)"), "base", "not inside the base's shortest record"),
    (_aix(relate="APP.GONE"), "base", "is not in the catalog"),
    (_aix(relate=PATH, name="A.NEW"), "defined", "is not a cluster"),
    (_aix().rstrip() + f" INDEX(NAME({BASE}))\n", "base", "component name is already an entry"),
    (" DEFINE NONVSAM (NAME(A.B))\n", "base", "only DEFINE CLUSTER, ALTERNATEINDEX and PATH"),
    (" DEFINE ALTERNATEINDEX (NAME(A.N) KEYS(4 4) RECORDSIZE(40 40))\n", "base", "without a single RELATE"),
    (f" DEFINE ALTERNATEINDEX (NAME(A.N) RELATE({BASE}) -\n KEYS(4 4))\n", "base", "without RECORDSIZE"),
    (_aix().rstrip() + " DATA(NAME(A.D) KEYS(1 0))\n", "base", "DATA component operand"),
    (_aix().rstrip() + " DATA(NAME(A.D)) DATA(NAME(A.E))\n", "base", "component stated twice"),
    # DEFINE PATH
    (" DEFINE PATH (NAME(A.P) PATHENTRY(NOPE.AIX))\n", "base", "is not in the catalog"),
    (f" DEFINE PATH (NAME(A.P) PATHENTRY({BASE}))\n", "base", "is not an alternate index"),
    (f" DEFINE PATH (NAME(A.P) PATHENTRY({PATH}))\n", "defined", "is not an alternate index"),
    (f" DEFINE PATH (NAME(A.P) PATHENTRY({AIX}) CYLINDERS(1 1))\n", "defined", "PATH CYLINDERS parameter"),
    (" DEFINE PATH (PATHENTRY(A))\n", "base", "without a single NAME"),
    (" DEFINE PATH (NAME(A.P))\n", "defined", "without a single PATHENTRY"),
    (f" DEFINE PATH (NAME(A.P) PATHENTRY({AIX})) -\n DATA(NAME(A.D))\n", "defined", "outside PATH"),
    # BLDINDEX
    (" BLDINDEX INFILE(IN) OUTFILE(OUT)\n", "defined", "the DD form is not modelled"),
    (f" BLDINDEX INDATASET({BASE})\n", "defined", "both INDATASET and OUTDATASET"),
    (f" BLDINDEX INDATASET({BASE}) -\n OUTDATASET({AIX}) EXTERNALSORT\n", "defined", "BLDINDEX EXTERNALSORT parameter"),
    (f" BLDINDEX IDS({BASE}) -\n INDATASET({BASE}) ODS({AIX})\n", "defined", "names its INDATASET twice"),
    (f" BLDINDEX INDATASET({BASE} PW) OUTDATASET({AIX})\n", "defined", "one name, no password"),
    (f" BLDINDEX INDATASET({BASE}/PW) OUTDATASET({AIX})\n", "defined", "plain data set name"),
    (f" BLDINDEX INDATASET(APP.GONE) OUTDATASET({AIX})\n", "defined", "not a cluster in the catalog"),
    (f" BLDINDEX INDATASET({BASE}) OUTDATASET({PATH})\n", "defined", "not an alternate index"),
    (f" BLDINDEX INDATASET({BASE}) OUTDATASET({AIX})\n", "empty", "empty base cluster"),
    (BLD, "built", "already built"),
    (f" BLDINDEX INDATASET({OTHER}) OUTDATASET({AIX})\n", "two", "which it is not related to"),
    (BLD, "unique", "UNIQUEKEY alternate index over duplicate keys"),
    (BLD, "small", "over RECORDSIZE maximum"),
    # REPRO through a path / index, DELETE of a dependent
    (f" REPRO INFILE(IN) OUTDATASET({PATH})\n", "built", "writes through a path"),
    (f" REPRO INFILE(IN) OUTDATASET({AIX})\n", "built", "is an alternate index"),
    (f" REPRO INFILE(IN) OUTDATASET({BASE})\n", "built", "base cluster with an alternate index"),
    (f" REPRO INDATASET({PATH}) OUTFILE(OUT)\n", "defined", "BLDINDEX has not built"),
    (f" REPRO INDATASET({AIX}) OUTFILE(OUT)\n", "built", "is an alternate index"),
    (f" DELETE {AIX}\n", "built", "alternate index or path"),
    (f" DELETE {PATH}\n", "built", "alternate index or path"),
    (f" DELETE {AIX} ALTERNATEINDEX\n", "built", "an entry in the catalog (only an absent one"),  # #8885
    (f" DELETE {BASE}\n", "built", "alternate index related to it"),
]
IDS = [f"{i:02d}-{c[2][:28]}" for i, c in enumerate(CASES)]
_DDS = {"IN": M.Sequential(10, [b"0099ZZZZ.."]), "OUT": M.Sequential(10)}


def _dds() -> dict:
    return {k: M.Sequential(v.lrecl, list(v.records)) for k, v in _DDS.items()}


@pytest.mark.parametrize(("deck", "state", "why"), CASES, ids=IDS)
def test_the_model_refuses_it_by_name(deck, state, why):
    setup, cat = _setup(state)
    assert M.run(setup, cat, _dds()).rc == 0 if setup else True  # the set-up alone is accepted
    with pytest.raises(Refused, match=re.escape(why)):
        M.run(setup + deck, cat, _dds())


@pytest.mark.skipif(eij.jdk_bin() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
@pytest.mark.parametrize(("deck", "state", "why"), CASES, ids=IDS)
def test_the_java_step_refuses_it_with_the_same_words(deck, state, why):
    setup, cat = _setup(state)
    got = eij.compare(setup + deck, cat, _dds())
    assert got is not None and got["equal"], got
    first = eij.model_lines(setup + deck, cat, _dds())[0]
    assert first.startswith("REFUSED") and why in first, first


SLOT = chr(0)
_SCOPE = re.compile(r"ALTERNATEINDEX|\bPATH\b|BLDINDEX|alternate index|\bpath\b")


def _refusal_texts() -> list[tuple[int, str]]:
    """Each `Refused(...)` raise in the model with its message: literal parts as written, a formatted field as a slot."""
    tree = ast.parse(Path(M.__file__).read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Refused" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.JoinedStr):  # the top-level pieces only: a ternary inside a field is one slot
                parts = [v.value if isinstance(v, ast.Constant) else SLOT for v in arg.values]
            elif isinstance(arg, ast.Constant):
                parts = [arg.value]
            else:
                continue
            out.append((node.lineno, "".join(parts)))
    return out


def _messages() -> list[str]:
    """What the model says for each table row, and for the two path readers that no deck reaches."""
    out = []
    for deck, state, _ in CASES:
        setup, cat = _setup(state)
        with pytest.raises(Refused) as e:
            M.run(setup + deck, cat, _dds())
        out.append(str(e.value))
    for name, cat in (
        (BASE, _base()),  # not a path
        (PATH, {**_base(), PATH: M.Path(PATH, BASE, True)}),  # a path that leads to a cluster
    ):
        with pytest.raises(Refused) as e:
            M.path_records(cat, name)
        out.append(str(e.value))
    return out


def test_every_aix_refusal_site_has_a_row_in_the_table():
    sites = [(n, t) for n, t in _refusal_texts() if _SCOPE.search(t.replace(SLOT, ""))]
    assert len(sites) >= 30, sites  # the scan finds the sites, it is not vacuous
    said = _messages()
    pats = {n: re.compile(".*".join(re.escape(p) for p in t.split(SLOT)), re.S) for n, t in sites}
    missing = [(n, t) for n, t in sites if not any(pats[n].fullmatch(m) for m in said)]
    assert not missing, f"a refusal about an alternate index / path / BLDINDEX no row in CASES reaches: {missing}"
