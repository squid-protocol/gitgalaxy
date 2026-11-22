"""#8880: an IDCAMS step between program steps in a job case (`tests/tools/equivalence_job.py`, `idcams_job.py`).

The IDCAMS step runs through the oracle model (det/idcams_model.py) and the real Java runtime (cobolrt/job/Idcams.java,
JDK 17 needed: the Java tests skip without one) on authored decks; the program steps are stubbed as in
test_equivalence_job_4268.py (the GnuCOBOL + port run is the job case's own `equivalence.py run`)."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_job as ej_job
import idcams_job as idc
from javac_server import jdk_bin

needs_jdk = pytest.mark.skipif(jdk_bin() is None, reason="no JDK (JDK_17 / JAVA_HOME)")

DEFINE = (
    " DEFINE CLUSTER (NAME(APP.KS) INDEXED KEYS(4 0) -\n    RECORDSIZE(10 10) VOLUMES(V1))\n"  # SYSIN ends at column 72
)
LOAD = " REPRO INFILE(IN) OUTDATASET(APP.KS)\n"
UNLOAD = " REPRO INDATASET(APP.KS) OUTFILE(OUT)\n"


def _prog(reclen=10, **ds):
    return {"corpus": "c", "program": "P", "datasets": {"IN": {"organization": "sequential", "reclen": reclen},
                                                          "OUT": {"organization": "sequential", "reclen": reclen,
                                                                  "compare": True}, **ds}}  # fmt: skip


def _idc(name="ix", sysin="ix.txt", **dds):
    return {"idcams": name, "sysin": sysin, "dds": dds or {"IN": {"lrecl": 10, "feed": {"step": "a", "dd": "OUT"}},
                                                            "OUT": {"lrecl": 10}}}  # fmt: skip


def _job(*mid, tail=True):
    steps = [{"case": "a"}, *mid]
    if tail:
        steps.append({"case": "b", "feeds": {"IN": {"step": mid[-1]["idcams"], "dd": "OUT"}}})
    return {"name": "j", "kind": "job", "job": "J", "steps": steps}


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(ej_job, "JOBS", tmp_path)
    (tmp_path / "ix.txt").write_text(DEFINE + LOAD + UNLOAD, encoding="utf-8")
    return tmp_path


def _cases():
    return {"a": {**_prog(), "program": "PA"}, "b": {**_prog(), "program": "PB"}}


class _Api(types.SimpleNamespace):
    def load_case(self, name):
        return json.loads(json.dumps(self.cases[name]))

    def data_encoding(self, case):
        return "latin-1"

    def build_image(self):
        pass

    def run_cobol(self, case, corpus, work):
        self.seen.append((case["program"], dict(case["datasets"])))
        return dict(self.cobol[case["program"]])

    def compare_run(self, case, corpus, cobol, java):
        return {"ok": True, "return_code": {"cobol": "0", "java": "0"}, "abend": {"cobol": None, "java": None},
                "outputs": {"OUT": {"equal": 1, "records": 1, "diffs": []}}}  # fmt: skip


@pytest.fixture
def api(monkeypatch):
    import equivalence_java as ej
    import mainframe_corpus as mc

    monkeypatch.setattr(ej, "run_java_environments", lambda *a, **k: {"default": {"RETURN-CODE": b"0"}})
    monkeypatch.setattr(mc, "select", lambda names: [names[0]])
    monkeypatch.setattr(mc, "require_clone", lambda entry: Path("/corpus"))
    cobol = {"PA": {"OUT": b"0001AAAAAA0002BBBBBB", "RETURN-CODE": b"0"}, "PB": {"OUT": b"x" * 10, "RETURN-CODE": b"0"}}
    return _Api(seen=[], cases=_cases(), cobol=cobol)


def _report(work):
    return json.loads((work / "report.json").read_text(encoding="utf-8"))


@needs_jdk
def test_an_idcams_step_between_program_steps_is_fed_and_feeds_like_a_program_step(base, api, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert ej_job.run_case(api, _job(_idc()), work) == 0
    fed = Path(api.seen[1][1]["IN"]["input"])
    assert fed.read_bytes() == b"0001AAAAAA\n0002BBBBBB\n"  # a.OUT -> the DEFINEd KSDS -> OUT -> b.IN, key order
    rep = _report(work)
    assert rep["proven"] and [s["case"] for s in rep["steps"]] == ["a", "ix", "b"]
    ix = rep["steps"][1]
    assert ix["kind"] == "idcams" and ix["fed"] == {"IN": "a.OUT (2 records)"}
    assert ix["condition_codes"] == {"model": [0, 0, 0], "java": [0, 0, 0]}
    assert ix["outputs"]["OUT"] == {"records": 2, "equal": 2, "diffs": []}
    assert rep["steps"][2]["fed"] == {"IN": "ix.OUT (2 records)"}


@needs_jdk
@pytest.mark.parametrize(
    ("deck", "codes"),
    [(" DELETE APP.GONE CLUSTER\n", [8, 8, 8]),  # an entry not found: IBM code 8, the step ends with 8
     (" DELETE APP.GONE CLUSTER\n SET MAXCC = 0\n", [0, 8, 0]),  # the idiom: MAXCC reset, LASTCC stays 8
     (" DELETE APP.GONE CLUSTER\n IF LASTCC = 8 THEN SET MAXCC = 0\n", [0, 8, 0]),
     (DEFINE + DEFINE, [12, 12, 12])],  # a duplicate name: code 12, catalog unchanged
)  # fmt: skip
def test_the_condition_code_is_compared_whatever_it_is(base, api, tmp_path, deck, codes):
    (base / "ix.txt").write_text(deck, encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    assert ej_job.run_case(api, _job(_idc()), work) == 0  # a failing step does not stop the job (no COND is modelled)
    ix = _report(work)["steps"][1]
    assert ix["ok"] and ix["condition_codes"] == {"model": codes, "java": codes}


@needs_jdk
def test_the_catalog_carries_from_one_idcams_step_to_the_next(base, api, tmp_path):
    (base / "ix.txt").write_text(DEFINE + LOAD + UNLOAD, encoding="utf-8")
    (base / "ix2.txt").write_text(" DELETE APP.KS CLUSTER\n DEFINE CLUSTER (NAME(APP.KS) NONINDEXED RECORDSIZE(10 10))\n"
                                  " REPRO INFILE(IN) OUTDATASET(APP.KS)\n REPRO INDATASET(APP.KS) OUTFILE(OUT)\n",
                                  encoding="utf-8")  # fmt: skip
    job = _job(_idc(), _idc("ix2", "ix2.txt", IN={"lrecl": 10, "feed": {"step": "ix", "dd": "OUT"}}, OUT={"lrecl": 10}))
    work = tmp_path / "work"
    work.mkdir()
    assert ej_job.run_case(api, job, work) == 0
    steps = _report(work)["steps"]
    assert steps[2]["condition_codes"]["model"] == [0, 0, 0]  # APP.KS existed for the second step's DELETE
    assert steps[2]["outputs"]["OUT"]["records"] == 2


@needs_jdk
def test_a_step_given_an_input_file_beside_the_job_case(base, api, tmp_path):
    (base / "seed.txt").write_text("0003CCCCCC\n0004DDDDDD\n", encoding="utf-8")
    step = _idc(IN={"lrecl": 10, "input": "seed.txt"}, OUT={"lrecl": 10})
    work = tmp_path / "work"
    work.mkdir()
    assert ej_job.run_case(api, _job(step), work) == 0
    assert Path(api.seen[1][1]["IN"]["input"]).read_bytes() == b"0003CCCCCC\n0004DDDDDD\n"


@needs_jdk
def test_a_step_the_model_refuses_stops_the_job_by_name(base, api, tmp_path):
    (base / "ix.txt").write_text(" PRINT INFILE(IN)\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    assert ej_job.run_case(api, _job(_idc()), work) == 1
    rep = _report(work)
    ix = rep["steps"][1]
    assert not rep["proven"] and len(api.seen) == 1 and "refuses the step by name" in ix["stopped"]
    assert ix["java_refused"] is True  # the Java refuses with the same text


@needs_jdk
def test_a_java_side_that_differs_leaves_the_job_unproven(base, api, tmp_path, monkeypatch):
    real = idc.JavaSide.run

    def wrong(self, dds, sysin, commit):
        return [ln.replace("RC 0 0 0", "RC 4 0 4") for ln in real(self, dds, sysin, commit)]

    monkeypatch.setattr(idc.JavaSide, "run", wrong)
    work = tmp_path / "work"
    work.mkdir()
    assert ej_job.run_case(api, _job(_idc()), work) == 1
    ix = _report(work)["steps"][1]
    assert ix["ok"] is False and "RC 0 0 0" in ix["diffs"][0] and ix["return_code"] == {"model": 0, "java": 4}


def test_an_idcams_step_that_is_fed_from_nothing_it_has_stops_by_name(base, api, tmp_path, monkeypatch):
    api.cobol["PA"] = {"OUT": b"", "ABEND": b"U0016"}
    work = tmp_path / "work"
    work.mkdir()
    assert ej_job.run_case(api, _job(_idc()), work) == 1  # the abended step ends the job before the deck runs
    assert [s["case"] for s in _report(work)["steps"]] == ["a"]


@pytest.mark.parametrize(
    ("mutate", "why"),
    [
        (lambda s: s.update(extra=1), "unknown key"),
        (lambda s: s.update(sysin="nope.txt"), "no sysin file"),
        (lambda s: s.update(dds=[]), "mapping"),
        (lambda s: s["dds"].update(X={"lrecl": 10, "bogus": 1}), "unknown key"),
        (lambda s: s["dds"].update(X={"vsam": "A", "lrecl": 10}), "only the cluster name"),
        (lambda s: s["dds"].update(X={}), "positive lrecl"),
        (lambda s: s["dds"].update(X={"lrecl": 10, "feed": {"step": "a", "dd": "OUT"}, "input": "ix.txt"}), "both fed"),
        (lambda s: s["dds"].update(X={"lrecl": 10, "input": "gone.txt"}), "no file gone.txt"),
        (lambda s: s["dds"]["IN"]["feed"].update(step="zz"), "not an earlier step"),
        (lambda s: s["dds"]["IN"]["feed"].update(dd="IN"), "does not compare"),
        (lambda s: s["dds"]["IN"].update(lrecl=20), "record length"),
        (lambda s: s.update(case="zz"), "both a case and an IDCAMS"),
    ],
)  # fmt: skip
def test_every_refusal_is_by_name(base, mutate, why):
    step = _idc()
    mutate(step)
    with pytest.raises(ej_job.Unsupported, match=why):
        ej_job.check_job(_job(step), _cases())


def test_a_feed_from_an_indexed_dataset_is_refused_by_name(base):
    cases = _cases()
    cases["a"]["datasets"]["OUT"] = {"organization": "indexed", "reclen": 10, "compare": True,
                                     "keys": [{"offset": 0, "length": 4}]}  # fmt: skip
    with pytest.raises(ej_job.Unsupported, match="REPRO the cluster to a sequential DD"):
        ej_job.check_job(_job(_idc()), cases)


def test_a_program_step_may_feed_from_an_idcams_dd_and_a_name_may_not_repeat(base):
    ej_job.check_job(_job(_idc()), _cases())
    with pytest.raises(ej_job.Unsupported, match="appears twice"):
        ej_job.check_job(_job(_idc("a")), _cases())  # a feed names its source step by name
    with pytest.raises(ej_job.Unsupported, match="does not compare"):  # an IDCAMS vsam DD is no dataset to feed from
        ej_job.check_job(_job(_idc(KS={"vsam": "APP.KS"}, OUT={"lrecl": 10}), tail=False)
                         | {"steps": [{"case": "a"}, _idc(KS={"vsam": "APP.KS"}),
                                      {"case": "b", "feeds": {"IN": {"step": "ix", "dd": "KS"}}}]}, _cases())  # fmt: skip
