"""#3753 follow-up: mutation testing of the proven ports (tests/tools/mutation.py). The pure parts: which sites are
mutated (never a comment, a log call, an import or an annotation), what each operator writes, the sample, which of
a proof's runs killed a mutant, and the score."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_common as common
import equivalence_java as ej
import mutation as mu

JAVA = """package com.gitgalaxy.modernized.service;

import java.math.BigDecimal;

@Service
public class XService {
    private static final Logger log = LoggerFactory.getLogger(XService.class);

    int run(int a, List<String> xs) {
        log.info("never mutated: {} < {}", a, 1);
        // a < b in a comment is not code
        if (a >= 10 && a != 0x09CB) {
            total = total.add(new BigDecimal("1.00")).setScale(2, RoundingMode.HALF_UP);
            count++;
        }
        doIt(a);
        return a * 2;
    }
}
"""


def _by_op(ms):
    out = {}
    for m in ms:
        out.setdefault(m.op, []).append(m.after)
    return out


def test_every_operator_mutates_code_and_nothing_else():
    ms = mu.mutants_of("service/XService.java", JAVA, set(mu.OPERATORS))
    ops = _by_op(ms)
    assert "if (a > 10 && a != 0x09CB) {" in ops["ROR"] and "if (a >= 10 && a == 0x09CB) {" in ops["ROR"]
    assert "if (a >= 10 || a != 0x09CB) {" in ops["COR"]
    assert "if (!(a >= 10 && a != 0x09CB)) {" in ops["NEG"]
    assert "return a / 2;" in ops["AOR"] and "count--;" in ops["AOR"]
    assert any(".subtract(" in x for x in ops["BDM"]) and any("RoundingMode.DOWN" in x for x in ops["BDM"])
    assert "if (a >= 11 && a != 0x09CB) {" in ops["CON"] and "if (a >= 10 && a != 0x09CC) {" in ops["CON"]
    assert any('new BigDecimal("X.00")' in x for x in ops["LIT"])
    assert "/* doIt(a); */" in ops["DEL"] and "/* count++; */" in ops["DEL"]
    lines = {m.line for m in ms}
    assert not lines & {1, 3, 5, 7, 10, 11}  # package, import, annotation, the logger, a log call, a comment
    assert not any("List<" in m.after and m.op == "ROR" for m in ms)  # a generic is not a comparison


def test_a_mutant_is_the_port_with_one_change(tmp_path):
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / "XService.java").write_text(JAVA, encoding="utf-8")
    (port / "provenance.json").write_text("{}", encoding="utf-8")
    (m,) = [x for x in mu.all_mutants(port, {"AOR"}) if x.after == "return a / 2;"]
    out = mu.write_mutant(port, m, tmp_path / "mutant")
    text = (out / "service" / "XService.java").read_text(encoding="utf-8")
    assert text == JAVA.replace("return a * 2;", "return a / 2;") and not (out / "provenance.json").exists()
    assert (port / "service" / "XService.java").read_text(encoding="utf-8") == JAVA  # the port is untouched


def test_the_sample_spreads_over_the_operators_and_is_repeatable():
    ms = mu.mutants_of("x.java", JAVA, set(mu.OPERATORS))
    picked = mu.sample(ms, 8, seed=3)
    assert len(picked) == 8 and len({m.op for m in picked}) == 8
    assert [m.id for m in picked] == [m.id for m in mu.sample(ms, 8, seed=3)]
    assert mu.sample(ms, None, 0) == ms


def test_the_runs_that_killed_a_mutant_are_named_for_each_kind():
    batch = {"environments": [{"ok": True}], "faults": [{"name": "dup", "ok": False}, {"name": "eof", "ok": True}]}
    assert mu.killers(batch) == ["dup"]  # only a fault run saw it
    assert mu.killers({**batch, "environments": [{"ok": False}]}) == ["main", "dup"]
    cics = {"kind": "cics", "outputs": {"a": {"equal": 3, "records": 3, "diffs": []},
                                        "b": {"equal": 2, "records": 3, "diffs": [{}]},
                                        "c": {"equal": 1, "records": 1, "diffs": [],
                                              "fired": {"cobol": ["x"], "java": []}}}}  # fmt: skip
    assert mu.killers(cics) == ["b", "c"]
    assert mu.killers({"kind": "call", "outputs": {"CALLS": {"diffs": [{"record": 4}]}}}) == ["call 4"]
    assert mu.killers({"java_failed": True}) == ["java"]


def test_the_score_counts_timeouts_as_caught_and_stillborn_as_nothing():
    rs = [{"id": str(i), "op": "ROR", "file": "f", "line": i, "before": "a", "after": "b", "verdict": v,
           "killed_by": k} for i, (v, k) in enumerate([("killed", ["main"]), ("killed", ["dup"]), ("timeout", []),
                                                       ("survived", []), ("stillborn", [])])]  # fmt: skip
    md = mu.mutation_md({"case": "c", "program": "P", "mutants": 9, "chosen": 5, "seed": 0, "seconds": 1,
                         "coverage": "proven on 2 runs", "results": rs})  # fmt: skip
    assert "**Score: 3/4 caught (75%)**" in md and "stillborn (javac) 1" in md
    assert "Killed only by fault runs: 1" in md and "- `3` ROR f:3" in md


# ---- --reuse: an earlier run's COBOL side and generated project (the fast mode) ------------------------------
@pytest.fixture
def earlier(tmp_path):
    """An earlier run's --keep directory: a COBOL step and a generated project with a one-file overlay."""
    e = tmp_path / "earlier"
    (e / "cobol").mkdir(parents=True)
    (e / "cobol" / "run.sh").write_text("cobc ...\n", encoding="ascii")
    (e / "cobol" / "OUT.out").write_bytes(b"RECORD")
    project = e / "java" / "java_h2"
    (project / "target" / "classes").mkdir(parents=True)
    (project / ej.OVERLAY_FILE).write_text('["service/XService.java"]\n', encoding="utf-8")
    (e / "report.json").write_text("{}", encoding="utf-8")
    yield e
    common._REUSE = None


def test_a_reused_cobol_step_must_be_the_same_step(tmp_path, earlier):
    work = tmp_path / "now"
    common.reuse(work, earlier)
    (work / "cobol").mkdir(parents=True)
    (work / "cobol" / "run.sh").write_text("cobc ...\n", encoding="ascii")
    assert common.run_cobol_step(work / "cobol").returncode == 0
    assert (work / "cobol" / "OUT.out").read_bytes() == b"RECORD"  # the earlier step's output, not a new run
    (work / "cobol" / "run.sh").write_text("cobc -DOTHER ...\n", encoding="ascii")
    with pytest.raises(RuntimeError, match=r"run\.sh differs"):
        common.run_cobol_step(work / "cobol")


def test_a_reused_project_must_be_overlaid_with_the_same_files(tmp_path, earlier):
    work = tmp_path / "now" / "java"
    project = ej._reused_project(earlier / "java", work, ["service/XService.java"])
    assert project == work / "java_h2" and (project / "target" / "classes").is_dir()
    with pytest.raises(RuntimeError, match="not the earlier run's"):
        ej._reused_project(earlier / "java", work, [])  # the generated stub, where the earlier had a port
    with pytest.raises(SystemExit):
        common.reuse(work, tmp_path / "nowhere")  # not a finished run
