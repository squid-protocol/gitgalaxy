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
