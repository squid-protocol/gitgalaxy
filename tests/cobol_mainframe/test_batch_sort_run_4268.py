"""#4268: a lowered DFSORT step is run by the generated Spring Batch job: the forge det-translates the COBOL SORT /
MERGE program (test_dfsort_4268.py proves that translation against GnuCOBOL), emits it as a service with the det
runtime it needs, and the step calls its `runBatch` on the step's DDs. A translation that fails stays a named
utility step -- never a silent success."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run
from test_batch_sort_lowering_4268 import FB80, _forge, _sort_in, _step
from test_det_programs import PKG, _java, _runtime_classes

from gitgalaxy.tools.cobol_to_java import cobol_to_java_batch_forge as BF

MERGE_DDS = [
    {"dd": "SORTIN01", "dsn": "A", **FB80},
    {"dd": "SORTIN02", "dsn": "B"},
    {"dd": "SORTOUT", "dsn": "C"},
]
# every shape of the class: one SORTIN, SORT with INCLUDE / OUTREC / EQUALS, COPY, and a MERGE of two inputs
CASES = [
    (_sort_in(**FB80), " SORT FIELDS=(1,4,CH,A)\n"),
    (_sort_in(**FB80), " SORT FIELDS=COPY\n"),
    (_sort_in(**FB80), " OPTION EQUALS\n SORT FIELDS=(1,4,CH,D)\n INCLUDE COND=(5,2,CH,EQ,C'AB')\n"),
    (_sort_in(**FB80), " SORT FIELDS=(1,4,CH,A)\n OUTREC FIELDS=(1,4,2X,C'|')\n"),
    (MERGE_DDS, " MERGE FIELDS=(1,4,CH,A),EQUALS\n"),
]
IDS = ["sort", "copy", "equals-include", "outrec", "merge"]


def _cfg(forge) -> str:
    return next(t for k, t in forge.sources()[("base_pkg", "batch")].items() if k.endswith("JobConfig"))


@pytest.mark.parametrize(("dds", "sysin"), CASES, ids=IDS)
def test_a_lowered_step_is_a_program_step_over_its_det_service(dds, sysin):
    f = _forge(dds, sysin)
    st = _step(f)
    assert st.not_ported == "" and st.sort_service.startswith("DfsortStep") and st.sort_service.endswith("Service")
    cfg = _cfg(f)
    var = st.sort_service[0].lower() + st.sort_service[1:]
    assert f"{var}.runBatch(DDS_SRT, null)" in cfg and f"{st.sort_service} {var}" in cfg
    assert "steps.utility" not in cfg
    svc = f.sources()[("base_pkg", "service")][st.sort_service]
    assert f"class {st.sort_service}" in svc and "public int runBatch(List<Dd> dds, String parm)" in svc
    # every statement translated; the by-name stop on an unhandled I/O error (IBM abends, #4268) is a runtime guard,
    # not an untranslated statement
    assert "Hole(" not in "\n".join(ln for ln in svc.splitlines() if "IBM abends (not modelled)" not in ln)
    assert "0 utility steps to port" in f.audit_line()


def test_the_det_runtime_the_service_runs_on_is_emitted_without_cics_and_sql():
    src = _forge(_sort_in(**FB80)).sources()
    assert "Sort" in src[("base_pkg", "cobolrt")] and "Cobol" in src[("base_pkg", "cobolrt")]
    assert not any("cics" in k[1] or "sql" in k[1] for k in src if k[0] == "base_pkg" and k[1].startswith("cobolrt/"))


def test_two_sort_steps_get_two_services():
    f = _forge(_sort_in(**FB80))
    names = {st.sort_service for j in f.applications for st in j.steps if st.sort_service}
    assert len(names) == 1
    assert len({BF.zlib.crc32(b"a/SRT"), BF.zlib.crc32(b"b/SRT")}) == 2  # the program id is per job and step


def test_a_job_without_a_lowered_step_emits_no_det_runtime():
    src = _forge(_sort_in(), " SORT FIELDS=(1,4,CH,A)\n").sources()  # no stated length: refused, not lowered
    assert ("base_pkg", "service") not in src and not any(k[1].startswith("cobolrt") for k in src if k[0] == "base_pkg")


def test_a_failed_translation_keeps_a_named_utility_step(monkeypatch):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    def boom(*_a, **_k):
        raise ValueError("no tree-sitter")

    monkeypatch.setattr(P, "translate", boom)
    f = _forge(_sort_in(**FB80))
    st = _step(f)
    assert st.lowered and not st.sort_service and "ValueError: no tree-sitter" in st.not_ported
    cfg = _cfg(f)
    assert 'steps.utility("SRT"' in cfg and "the det translation failed" in cfg
    assert "1 utility steps to port" in f.audit_line() and ("base_pkg", "service") not in f.sources()


def test_a_translation_with_holes_is_not_run(monkeypatch):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    real = P.translate

    def holey(*a, **k):
        r = real(*a, **k)
        r.stats["holes"] = ["line 3: SORT"]
        return r

    monkeypatch.setattr(P, "translate", holey)
    f = _forge(_sort_in(**FB80))
    assert "1 hole(s)" in _step(f).not_ported and 'steps.utility("SRT"' in _cfg(f)


@pytest.mark.slow(reason="javac of the batch runtime (the first java test of a CI split part pays it)")
@pytest.mark.skipif(_java() is None, reason="needs JDK_17 / JAVA_HOME")
def test_the_forge_emitted_service_sorts_the_datasets_it_is_given(tmp_path):
    """The service the forge emits (not the one test_dfsort_4268.py builds) compiles on the det batch runtime and
    sorts its SORTIN into SORTOUT: records of 80 bytes, ascending on bytes 1-4."""
    svc = _forge(_sort_in(**FB80)).sources()[("base_pkg", "service")]
    ((name, text),) = svc.items()
    text = text.replace("com.gitgalaxy", PKG).replace("import org.springframework.stereotype.Service;\n", "")
    text = text.replace("@Service\n", "")
    rt = _runtime_classes(True, "ISO-8859-1")
    java = tmp_path / "java"
    (java / PKG / "service").mkdir(parents=True)
    (java / PKG / "service" / f"{name}.java").write_text(text)
    data = tmp_path / "data"
    data.mkdir()
    keys = ["DDDD", "AAAA", "CCCC", "BBBB"]
    (data / "APP.IN").write_bytes(b"".join(k.encode().ljust(80) for k in keys))
    b = f"{PKG}.batch"
    (java / "Main.java").write_text(
        f"public class Main {{ public static void main(String[] a) {{ new {PKG}.service.{name}("
        f'new {b}.DatasetResolver("{data}"), new {b}.CobolFiles("", ""), new {b}.MainframeClock("", "UTC"))'
        f'.runBatch(java.util.List.of(new {b}.Dd("SORTIN", "APP.IN", "SHR", null, null), '
        f'new {b}.Dd("SORTOUT", "APP.OUT", "NEW", "CATLG", null)), null); }} }}\n'
    )
    jdk = _java()
    classes = tmp_path / "classes"
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-cp", str(rt), "-d", str(classes),
               *map(str, java.rglob("*.java"))], check=True)  # fmt: skip
    cp = os.pathsep.join([str(classes), str(rt)])
    subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", cp, "Main"],
                   capture_output=True, encoding="utf-8", check=True)  # fmt: skip
    assert (data / "APP.OUT").read_bytes() == b"".join(k.encode().ljust(80) for k in sorted(keys))
