"""#8883: GDG generations across a job case. The catalog rules (relative numbers resolved once per job, (+1)
catalogued at step end, a base read newest first), every refusal by name, and an authored two-job chain run with the
COBOL / Java sides stubbed (both sides read the same generation bytes). Real GnuCOBOL runs need Docker: not here."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_gdg as gdg
import equivalence_job as ej_job

BASE = "CARD.TRAN.BKUP"
RL = 4


def _ds(**kw):
    return {"organization": "sequential", "reclen": RL, **kw}


def _case(program):
    return {"corpus": "c", "program": program, "datasets": {"IN": _ds(), "OUT": _ds(compare=True)}}


def _cases():
    return {"w1": _case("W1"), "r1": _case("R1"), "w2": _case("W2"), "r2": _case("R2")}


def _decl(**kw):
    return {BASE: {"limit": 3, "reclen": RL, **kw}}


def _job(steps, gdgs=None):
    return {"name": "j", "kind": "job", "job": "TRANBKP", "gdgs": gdgs or _decl(), "steps": steps}


OUT = {"gdg_out": {"OUT": BASE}}


def _in(gen, base=BASE):
    return {"gdg_in": {"IN": {"base": base, "gen": gen}}}


def _check(steps, gdgs=None, cases=None):
    ej_job.check_job(_job(steps, gdgs), cases or _cases())


def test_two_jobs_write_then_read_back_are_accepted():
    _check([{"case": "w1", **OUT}, {"case": "r1", "job": "NEXT", **_in("0")}])


def test_the_same_job_reads_its_own_new_generation_as_plus_one():
    _check([{"case": "w1", **OUT}, {"case": "r1", **_in("+1")}])


@pytest.mark.parametrize(
    ("steps", "gdgs", "why"),
    [
        ([{"case": "w1"}, {"case": "r1", **_in("0")}], None, "held 0 generation"),  # empty base at job start
        (
            [{"case": "w1", **OUT}, {"case": "r1", **_in("0")}],
            None,
            "held 0 generation",
        ),  # (0) is resolved at job start
        ([{"case": "w1", **_in("+1")}, {"case": "r1"}], None, "read before a step of this job wrote it"),
        ([{"case": "w1", **OUT}, {"case": "r1", **_in("+2")}], None, r"\+2 and further"),
        ([{"case": "w1", **OUT}, {"case": "w2", **OUT}], None, "second step of one job"),
        ([{"case": "w1", **OUT}, {"case": "r1", "job": "N", **_in("-1")}], None, "held 1 generation"),
        ([{"case": "w1", **OUT}, {"case": "r1", **_in("0", base="OTHER.BASE")}], None, "defines itself"),
        ([{"case": "w1", "gdg_out": {"OUT": "OTHER.BASE"}}, {"case": "r1"}], None, "defines itself"),
        ([{"case": "w1", **OUT}, {"case": "r1"}], _decl(generations=["a", "b", "c"]), "LIMIT 3"),
        ([{"case": "w1", **OUT}, {"case": "r1"}], _decl(scratch=True), "roll-off with SCRATCH"),
        ([{"case": "w1", **OUT}, {"case": "r1"}], _decl(empty=True), "not modelled"),
        ([{"case": "w1", **OUT}, {"case": "r1"}], _decl(bogus=1), "unknown key"),
        ([{"case": "w1", **OUT}, {"case": "r1"}], {BASE: {"limit": 0, "reclen": RL}}, "LIMIT must be"),
        ([{"case": "w1", **OUT}, {"case": "r1"}], {BASE: {"limit": 3, "reclen": 0}}, "reclen must be"),
        ([{"case": "w1", "gdg_out": {"NOPE": BASE}}, {"case": "r1"}], None, "not one of its datasets"),
        ([{"case": "w1", "gdg_out": {"IN": BASE}}, {"case": "r1"}], None, "not a dataset the case compares"),
        ([{"case": "w1", **OUT, "gdg_in": {"OUT": {"base": BASE, "gen": "0"}}}, {"case": "r1"}], None, "both reads"),
        ([{"case": "w1", **OUT}, {"case": "r1", "gdg_in": {"IN": {"base": BASE}}}], None, "must be"),
        ([{"case": "w1", **OUT}, {"case": "r1", "gdg_in": {"IN": {"base": BASE, "gen": "x"}}}], None, "not 0, -n"),
        (
            [{"case": "w1", **OUT}, {"case": "r1", "feeds": {"IN": {"step": "w1", "dd": "OUT"}}, **_in("+1")}],
            None,
            "also fed",
        ),
    ],
)
def test_every_refusal_is_by_name(steps, gdgs, why):
    with pytest.raises(ej_job.Unsupported, match=why):
        _check(steps, gdgs)


def test_a_generation_dataset_that_does_not_line_up_is_refused():
    cases = _cases()
    cases["r1"]["datasets"]["IN"]["reclen"] = 8
    with pytest.raises(ej_job.Unsupported, match="record length 8"):
        _check([{"case": "w1", **OUT}, {"case": "r1", **_in("+1")}], cases=cases)
    cases["r1"]["datasets"]["IN"] = {"organization": "indexed", "reclen": RL}
    with pytest.raises(ej_job.Unsupported, match="not sequential"):
        _check([{"case": "w1", **OUT}, {"case": "r1", **_in("+1")}], cases=cases)


def test_a_declared_generation_file_must_exist_beside_the_case():
    with pytest.raises(ej_job.Unsupported, match="no generation file missing-gen.txt"):
        _check([{"case": "w1", **OUT}, {"case": "r1"}], _decl(generations=["missing-gen.txt"]))


def test_a_limit_roll_off_is_refused_when_the_base_is_full():
    cat = gdg.Catalog(_decl(limit=2, generations=["a", "b"]), {BASE: [b"AAAA", b"BBBB"]})
    cat.begin_step("J")
    with pytest.raises(gdg.Unsupported, match="roll-off"):
        cat.create(BASE, b"CCCC")


def test_relative_numbers_are_resolved_at_job_start_and_a_base_reads_newest_first():
    cat = gdg.Catalog(_decl(limit=5, generations=["a", "b"]), {BASE: [b"AAAA", b"BBBB"]})
    cat.begin_step("J1")
    assert cat.read(BASE, "0") == (f"{BASE}.G0002V00", [b"BBBB"])
    assert cat.read(BASE, "-1")[1] == [b"AAAA"]
    assert cat.create(BASE, b"CCCC") == f"{BASE}.G0003V00"
    assert cat.read(BASE, "0")[1] == [b"BBBB"]  # (0) did not move for the job that created (+1)
    assert cat.read(BASE, "+1")[1] == [b"CCCC"]
    assert cat.read(BASE, "all")[1] == [b"CCCC", b"BBBB", b"AAAA"]
    cat.begin_step("J1")  # the same job: no new resolution
    assert cat.read(BASE, "0")[1] == [b"BBBB"]
    cat.begin_step("J2")
    assert cat.read(BASE, "0")[1] == [b"CCCC"]
    assert cat.read(BASE, "-2")[1] == [b"AAAA"]


def test_the_job_names_default_to_the_previous_steps():
    job = _job([{"case": "w1"}, {"case": "r1", "job": "NEXT"}, {"case": "w2"}])
    assert gdg.job_names(job) == ["TRANBKP", "NEXT", "NEXT"]


class _Api(types.SimpleNamespace):
    def __init__(self, cobol):
        super().__init__(seen=[], cases=_cases(), cobol=cobol)

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
def stub(monkeypatch):
    import equivalence_java as ej
    import mainframe_corpus as mc

    monkeypatch.setattr(ej, "run_java_environments", lambda *a, **k: {"default": {"RETURN-CODE": b"0"}})
    monkeypatch.setattr(mc, "select", lambda names: [names[0]])
    monkeypatch.setattr(mc, "require_clone", lambda entry: Path("/corpus"))


def _out(data, **kw):
    return {"OUT": data, "RETURN-CODE": b"0", **kw}


def _fed(api, i):
    return Path(api.seen[i][1]["IN"]["input"]).read_bytes()


def test_a_two_job_chain_reads_the_generation_the_first_job_catalogued(stub, tmp_path):
    api = _Api({"W1": _out(b"AAAABBBB"), "R1": _out(b"x" * 4), "W2": _out(b"CCCC"), "R2": _out(b"y" * 4)})
    steps = [{"case": "w1", **OUT},  # job TRANBKP writes (+1)
             {"case": "r1", **_in("+1")},  # the same job reads its own new generation back
             {"case": "w2", "job": "NIGHTLY", **OUT},  # job NIGHTLY: (0) is TRANBKP's generation, writes a newer one
             {"case": "r2", **_in("0")},  # (0) is resolved at NIGHTLY's start: still TRANBKP's, not w2's
             ]  # fmt: skip
    job = _job(steps)
    assert ej_job.run_case(api, job, tmp_path) == 0
    assert _fed(api, 1) == b"AAAA\nBBBB\n"
    assert _fed(api, 3) == b"AAAA\nBBBB\n"
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] and report["steps"][0]["fed"] == {"OUT (out)": f"{BASE}.G0001V00"}
    assert report["steps"][2]["fed"] == {"OUT (out)": f"{BASE}.G0002V00"}
    assert report["steps"][3]["fed"] == {"IN": f"{BASE}.G0001V00 (2 records)"}


def test_a_base_reference_reads_every_generation_newest_first(stub, tmp_path, monkeypatch):
    gen = tmp_path / "gens"
    gen.mkdir()
    (gen / "g1.txt").write_bytes(b"OLD1\nOLD2\n")
    monkeypatch.setattr(ej_job, "JOBS", gen)
    api = _Api({"W1": _out(b"NEW1"), "R1": _out(b"x" * 4)})
    job = _job([{"case": "w1", **OUT}, {"case": "r1", "job": "NEXT", **_in("all")}], _decl(generations=["g1.txt"]))
    assert ej_job.run_case(api, job, tmp_path / "work") == 0
    assert _fed(api, 1) == b"NEW1\nOLD1\nOLD2\n"  # generation 2, then generation 1 (its records in order)
    assert api.seen[0][1]["IN"].get("input") is None


def test_an_abended_step_catalogues_nothing(stub, tmp_path):
    api = _Api({"W1": _out(b"", ABEND=b"U0016"), "R1": _out(b"x" * 4)})
    job = _job([{"case": "w1", **OUT}, {"case": "r1", "job": "NEXT", **_in("0")}])
    assert ej_job.run_case(api, job, tmp_path) == 1
    assert len(api.seen) == 1  # the job stops at the abend; the generation was never catalogued
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert "abended" in report["steps"][0]["stopped"] and "OUT (out)" not in report["steps"][0]["fed"]
