"""#4268: a multi-step job case (`"kind": "job"`) in the equivalence harness. The whole input class of the chain:
the feed rules (every refusal by name), the records-to-lines staging a fed dataset is read from, and the run loop
with the COBOL / Java sides stubbed (what each step is given, a differing step, an abended step, --cobol-only).
The real GnuCOBOL + port run needs Docker and a JDK and is the job case's own `equivalence.py run`."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_common as common
import equivalence_job as ej_job


def _step(reclen=10, **ds):
    return {"corpus": "c", "program": "P", "datasets": {"IN": {"organization": "sequential", "reclen": reclen},
                                                          "OUT": {"organization": "sequential", "reclen": reclen,
                                                                  "compare": True}, **ds}}  # fmt: skip


def _job(**feeds):
    return {"name": "j", "kind": "job", "job": "J",
            "steps": [{"case": "a"}, {"case": "b", "feeds": feeds or {"IN": {"step": "a", "dd": "OUT"}}}]}  # fmt: skip


def _check(job, **cases):
    cases = cases or {"a": _step(), "b": _step()}
    ej_job.check_job(job, cases)


def test_a_sequential_feed_between_batch_steps_is_accepted():
    _check(_job())


@pytest.mark.parametrize(
    ("job", "cases", "why"),
    [
        ({"steps": [{"case": "a"}]}, None, "at least two"),
        ({"steps": [{"case": "a"}, {"case": "a"}]}, None, "twice"),
        ({"steps": [{"case": "a"}, {"case": "zz"}]}, None, "no case 'zz'"),
        (_job(IN={"step": "b", "dd": "OUT"}), None, "not an earlier step"),
        (_job(NOPE={"step": "a", "dd": "OUT"}), None, "not one of its datasets"),
        (_job(IN={"step": "a", "dd": "IN"}), None, "does not compare"),
        (_job(IN={"step": "a", "dd": "GONE"}), None, "does not compare"),
        (_job(), {"a": _step(), "b": {**_step(), "db2": {}}}, "db2 step"),
        (_job(), {"a": {**_step(), "ims": {}}, "b": _step()}, "ims step"),
        (_job(), {"a": {**_step(), "kind": "cics"}, "b": _step()}, "cics step"),
        (_job(), {"a": {**_step(), "kind": "call"}, "b": _step()}, "call step"),
        (_job(), {"a": _step(), "b": _step(reclen=20)}, "record length"),
        (_job(), {"a": _step(), "b": {"datasets": {"IN": {"organization": "indexed", "reclen": 10}}}}, "indexed"),
        ({**_job(), "steps": [{"case": "a", "x": 1}, {"case": "b"}]}, None, "unknown step key"),
    ],
)
def test_every_refusal_is_by_name(job, cases, why):
    with pytest.raises(ej_job.Unsupported, match=why):
        _check(job, **({} if cases is None else cases))


K = [{"offset": 0, "length": 4}]


def _ix(reclen=10, keys=K, compare=True):
    return {"organization": "indexed", "reclen": reclen, "keys": keys, **({"compare": True} if compare else {})}


def _ix_cases(a=None, b=None):
    return {"a": {"datasets": {"OUT": a or _ix()}}, "b": {"datasets": {"IN": b or _ix(compare=False)}}}


def test_an_indexed_feed_between_batch_steps_is_accepted():  # a KSDS the earlier step opens I-O, fed on
    _check(_job(), **_ix_cases())


@pytest.mark.parametrize(
    ("cases", "why"),
    [
        (_ix_cases(b={"organization": "sequential", "reclen": 10}), "both sides"),
        (_ix_cases(a={"organization": "sequential", "reclen": 10, "compare": True}), "both sides"),
        (_ix_cases(b=_ix(keys=[{"offset": 1, "length": 4}], compare=False)), "is keyed"),
        (_ix_cases(b=_ix(keys=[*K, {"offset": 5, "length": 2, "duplicates": True}], compare=False)), "is keyed"),
        (_ix_cases(b=_ix(reclen=12, compare=False)), "record length"),
    ],
)
def test_an_indexed_feed_that_does_not_line_up_is_refused_by_name(cases, why):
    with pytest.raises(ej_job.Unsupported, match=why):
        _check(_job(), **cases)


def test_an_indexed_feed_is_the_cobol_unload_staged_as_the_keyed_loader_reads_it(stub, tmp_path):
    cases = {"a": {**_step(), "program": "PA", "datasets": {"OUT": _ix()}},
             "b": {**_step(), "program": "PB", "datasets": {"IN": _ix(compare=False)}}}  # fmt: skip
    api = _Api(cases, {"PA": {"OUT": b"0001AAAAAA0002BBBBBB", "RETURN-CODE": b"0"}, "PB": {"RETURN-CODE": b"0"}})
    assert ej_job.run_case(api, _job(), tmp_path) == 0
    fed = api.seen[1][1]["IN"]
    assert Path(fed["input"]).read_bytes() == b"0001AAAAAA\n0002BBBBBB\n"
    assert fed["organization"] == "indexed" and fed["keys"] == K  # keyed as the next step declares


def test_a_corpus_input_override_is_passed_as_the_corpus_relative_path(stub, tmp_path):
    api = _api()
    job = _job()
    job["steps"][1]["inputs"] = {"OTHER": ej_job.CORPUS_PREFIX + "app/data/x.txt"}
    api.cases["b"]["datasets"]["OTHER"] = {"organization": "sequential", "reclen": 10}
    ej_job.check_job(job, api.cases)
    assert ej_job.run_case(api, job, tmp_path) == 0
    assert api.seen[1][1]["OTHER"]["input"] == "app/data/x.txt"


@pytest.mark.parametrize("enc", ["latin-1", "utf-8", "cp037", "cp500"])
def test_records_become_lines_the_input_reader_returns_whole(tmp_path, enc):
    sp = " ".encode(enc)
    recs = [b"AB".ljust(6, sp), sp * 6, b"ZZ".ljust(6, sp)]  # a trailing-space record and an all-space record
    data = b"".join(recs)
    f = tmp_path / "feed.txt"
    f.write_bytes(ej_job.records_as_lines(data, 6, enc))
    if common.ascii_compatible(enc):  # an EBCDIC page's NEL / newline split is _fixed's own, tested there
        assert common._fixed(f, 6, enc) == data


def test_a_partial_record_is_refused():
    with pytest.raises(ej_job.Unsupported, match="whole records"):
        ej_job.records_as_lines(b"abcde", 4, "latin-1")


class _Api(types.SimpleNamespace):
    def __init__(self, cases, cobol, java_equal=True):
        super().__init__(seen=[], cases=cases, cobol=cobol, java_equal=java_equal)

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
        ok = self.java_equal
        return {"ok": ok, "return_code": {"cobol": "0", "java": "0"}, "abend": {"cobol": None, "java": None},
                "outputs": {"OUT": {"equal": 1 if ok else 0, "records": 1, "diffs": []}}}  # fmt: skip


@pytest.fixture
def stub(monkeypatch):
    import equivalence_java as ej
    import mainframe_corpus as mc

    monkeypatch.setattr(ej, "run_java_environments", lambda *a, **k: {"default": {"RETURN-CODE": b"0"}})
    monkeypatch.setattr(mc, "select", lambda names: [names[0]])
    monkeypatch.setattr(mc, "require_clone", lambda entry: Path("/corpus"))


def _api(java_equal=True, **cobol):
    cases = {"a": {**_step(), "program": "PA"}, "b": {**_step(), "program": "PB"}}
    out = {"PA": {"OUT": b"CCCCCCCCCCAAAAAAAAAA", "RETURN-CODE": b"0"}, "PB": {"OUT": b"x" * 10, "RETURN-CODE": b"0"}}
    out.update(cobol)
    return _Api(cases, out, java_equal)


def test_the_next_step_reads_the_cobol_output_of_the_earlier_one(stub, tmp_path):
    api = _api()
    assert ej_job.run_case(api, _job(), tmp_path) == 0
    fed = Path(api.seen[1][1]["IN"]["input"])
    assert fed.is_absolute() and fed.read_bytes() == b"CCCCCCCCCC\nAAAAAAAAAA\n"
    assert "input" not in api.seen[0][1]["IN"]  # the first step keeps its own input
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] and [s["case"] for s in report["steps"]] == ["a", "b"]
    assert report["steps"][1]["fed"] == {"IN": "a.OUT (2 records)"}


def test_a_step_whose_java_differs_leaves_the_job_unproven(stub, tmp_path):
    assert ej_job.run_case(_api(java_equal=False), _job(), tmp_path) == 1
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["proven"] is False


def test_an_abended_step_stops_the_job(stub, tmp_path):
    api = _api(PA={"OUT": b"", "ABEND": b"U0016"})
    assert ej_job.run_case(api, _job(), tmp_path) == 1
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert len(api.seen) == 1 and "abended" in report["steps"][0]["stopped"] and not report["proven"]


def test_cobol_only_runs_every_step_and_proves_nothing(stub, tmp_path):
    api = _api()
    assert ej_job.run_case(api, _job(), tmp_path, cobol_only=True) == 0  # like a batch --cobol-only
    assert len(api.seen) == 2
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["proven"] is False  # nothing compared


def test_an_unrunnable_job_exits_by_name(stub, tmp_path):
    api = _api()
    with pytest.raises(SystemExit, match="not runnable faithfully"):
        ej_job.run_case(api, {"name": "j", "steps": [{"case": "a"}]}, tmp_path)


def test_a_step_with_subprograms_is_accepted_and_run_whole(stub, tmp_path):  # #8884: CBSTM03A CALLs CBSTM03B
    api = _api()
    api.cases["b"]["subprograms"] = ["app/cbl/SUBB.CBL"]
    ej_job.check_job(_job(), api.cases)
    assert ej_job.run_case(api, _job(), tmp_path) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["steps"][1]["subprograms"] == ["app/cbl/SUBB.CBL"] and "subprograms" not in report["steps"][0]


@pytest.mark.parametrize(
    ("subs", "why"),
    [("x.cbl", "list of corpus-relative"), ([""], "list of corpus-relative"), ([1], "list of corpus-relative"),
     (["a/S.cbl", "b/s.CBL"], "appears twice"), (["app/PB.cbl"], "step's own program")],
)  # fmt: skip
def test_a_malformed_subprograms_list_is_refused_by_name(subs, why):
    cases = {"a": {**_step(), "program": "PA"}, "b": {**_step(), "program": "PB", "subprograms": subs}}
    with pytest.raises(ej_job.Unsupported, match=why):
        ej_job.check_job(_job(), cases)


# -- an IDCAMS step (#8884): the model is the oracle, the chain around it is the harness's ---------------------------

REPRO = " REPRO INFILE(INFILE) OUTFILE(OUTFILE)\n"


def _idcams(deck="step.idc", reclen=10, **extra):
    dds = {"INFILE": {"reclen": reclen},
           "OUTFILE": {"cluster": "A.B.KSDS", "reclen": reclen, "keys": [{"offset": 0, "length": 4}]}}  # fmt: skip
    return {"case": "idc", "idcams": {"deck": deck, "dds": dds}, "feeds": {"INFILE": {"step": "a", "dd": "OUT"}},
            **extra}  # fmt: skip


def _idcams_job(step=None):
    return {"name": "j", "kind": "job", "job": "J",
            "steps": [{"case": "a"}, step or _idcams(),
                      {"case": "b", "feeds": {"IN": {"step": "idc", "dd": "OUTFILE"}}}]}  # fmt: skip


def _idcams_api(deck=REPRO, a_out=b"AAAA000001BBBB000002", tmp_path=None, monkeypatch=None):
    (tmp_path / "step.idc").write_text(deck, encoding="utf-8")
    monkeypatch.setattr(ej_job, "JOBS", tmp_path)
    api = _api(PA={"OUT": a_out, "RETURN-CODE": b"0"})
    b = api.cases["b"]
    b["datasets"]["IN"] = {"organization": "indexed", "reclen": 10, "keys": [{"offset": 0, "length": 4}]}
    return api


def _steps(job, api):
    return ej_job.load_steps(job, api.load_case)


def test_an_idcams_step_between_program_steps_runs_in_jcl_order_and_is_never_proven(stub, tmp_path, monkeypatch):
    api = _idcams_api(tmp_path=tmp_path, monkeypatch=monkeypatch)
    ej_job.check_job(_idcams_job(), _steps(_idcams_job(), api))
    assert ej_job.run_case(api, _idcams_job(), tmp_path / "w") == 1  # the Java side of IDCAMS is not compared
    assert [p for p, _ in api.seen] == ["PA", "PB"]
    assert Path(api.seen[1][1]["IN"]["input"]).read_bytes() == b"AAAA000001\nBBBB000002\n"
    report = json.loads((tmp_path / "w" / "report.json").read_text(encoding="utf-8"))
    assert [s["case"] for s in report["steps"]] == ["a", "idc", "b"]
    idc = report["steps"][1]
    assert idc["model_only"] and idc["ok"] and idc["rc"] == 0 and idc["fed"] == {"INFILE": "a.OUT (2 records)"}
    assert report["steps"][2]["fed"] == {"IN": "idc.OUTFILE (2 records)"}
    assert report["proven"] is False and all(s["ok"] for s in report["steps"])


def test_a_model_refusal_stops_the_job_by_name(stub, tmp_path, monkeypatch):  # a source out of key order
    api = _idcams_api(a_out=b"BBBB000002AAAA000001", tmp_path=tmp_path, monkeypatch=monkeypatch)
    assert ej_job.run_case(api, _idcams_job(), tmp_path / "w") == 1
    report = json.loads((tmp_path / "w" / "report.json").read_text(encoding="utf-8"))
    assert "the IDCAMS model refuses" in report["steps"][1]["stopped"] and len(api.seen) == 1


def test_a_nonzero_condition_code_bypasses_the_later_steps(stub, tmp_path, monkeypatch):
    api = _idcams_api(deck=" DELETE NO.SUCH.CLUSTER\n", tmp_path=tmp_path, monkeypatch=monkeypatch)
    assert ej_job.run_case(api, _idcams_job(), tmp_path / "w") == 1
    report = json.loads((tmp_path / "w" / "report.json").read_text(encoding="utf-8"))
    assert report["steps"][1]["rc"] is None or "condition code" in report["steps"][1]["stopped"]
    assert len(api.seen) == 1 and len(report["steps"]) == 2


@pytest.mark.parametrize(
    ("step", "why"),
    [(_idcams(deck="gone.idc"), "no such file beside the job case"),
     (_idcams(inputs={"INFILE": "x"}), "inputs on an IDCAMS step"),
     (_idcams(gdg_in={"INFILE": {}}), "gdg_in on an IDCAMS step"),
     (_idcams(reclen=0), "needs a record length"),
     (_idcams(reclen=20), "record length"),  # the feed rule reads the DD spec like a program step's
     ({**_idcams(), "idcams": {"deck": "step.idc", "dds": {"INFILE": {"reclen": 10}}}}, "no output dataset"),
     ({**_idcams(), "idcams": {"deck": "step.idc", "dds": {"OUTFILE": {"cluster": "X", "reclen": 10}}}}, "one key"),
     ({**_idcams(), "idcams": {"deck": "step.idc"}}, "idcams needs")],
)  # fmt: skip
def test_every_idcams_refusal_is_by_name(step, why, tmp_path, monkeypatch):
    api = _idcams_api(tmp_path=tmp_path, monkeypatch=monkeypatch)
    with pytest.raises(ej_job.Unsupported, match=why):
        ej_job.check_job(_idcams_job(step), _steps(_idcams_job(step), api))
