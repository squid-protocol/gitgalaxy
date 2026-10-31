"""#4268: a lowered DFSORT step in a whole forged estate (SkeletonForges, not a stub): it exists only in an
application job, so the estate always has a skeleton and therefore the CobolRecords the emitted service imports; and
the files the forge emits (real CobolRecords, service, det runtime) compile and sort a dataset."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run
from test_batch_sort_lowering_4268 import FB80, FILE, _sort_in
from test_det_programs import PKG, _batch_package, _java

from gitgalaxy.tools.cobol_to_java.cobol_to_java_skeleton_forges import SkeletonForges
from gitgalaxy.tools.cobol_to_java.java_target import load_target

MERGE_DDS = [{"dd": "SORTIN01", "dsn": "A", **FB80}, {"dd": "SORTIN02", "dsn": "B"}, {"dd": "SORTOUT", "dsn": "C"}]
CASES = [
    (_sort_in(**FB80), " SORT FIELDS=(1,4,CH,A)\n"),
    (_sort_in(**FB80), " SORT FIELDS=COPY\n"),
    (MERGE_DDS, " MERGE FIELDS=(1,4,CH,A),EQUALS\n"),
]
IDS = ["sort", "copy", "merge"]


def _estate(tmp_path: Path, dds: list[dict], sysin: str, with_program: bool = True) -> SkeletonForges:
    steps = [{"step": "SRT", "ordinal": 2, "line": 4, "program": "SORT"}]
    if with_program:
        steps.insert(0, {"step": "PRE", "ordinal": 1, "line": 2, "program": "POSTIT"})
        skel = {"program": {"program_ids": ["POSTIT"], "file": "cbl/POSTIT.cbl"}, "sections": {}}
        (tmp_path / "POSTIT_skeleton.json").write_text(json.dumps(skel), encoding="utf-8")
    facts = [{"file": FILE, "ordinal": 2, "proc_step": None, **d} for d in dds]
    sections = {
        "job_steps": {"facts": [{"file": FILE, "job": "SRTJOB", "steps": steps}]},
        "job_dds": {"facts": facts},
        "job_sysin": {"facts": [{"file": FILE, "ordinal": 2, "proc_step": None, "dd": "SYSIN", "body": sysin}]},
    }
    (tmp_path / "estate.json").write_text(json.dumps({"sections": sections}), encoding="utf-8")
    return SkeletonForges(tmp_path, PKG, load_target(None))


@pytest.mark.parametrize(("dds", "sysin"), CASES, ids=IDS)
def test_a_lowered_step_comes_with_the_cobolrecords_its_service_imports(tmp_path, dds, sysin):
    forges = _estate(tmp_path, dds, sysin)
    assert forges.skeletons and forges.batch.applications
    src = forges.sources()
    (svc,) = src[("base_pkg", "service")].values()
    assert f"import {PKG}.entity.vsam.CobolRecords;" in svc
    assert "class CobolRecords" in src[("entity", "vsam")]["CobolRecords"]


def test_a_job_of_utility_steps_only_is_no_application_and_emits_no_service(tmp_path):
    forges = _estate(tmp_path, *CASES[0], with_program=False)
    assert not forges.skeletons and not forges.batch.applications
    src = forges.sources()
    assert ("base_pkg", "service") not in src and "CobolRecords" not in src[("entity", "vsam")]


@pytest.mark.slow(reason="javac of the forged batch runtime (the first java test of a CI split part pays it)")
@pytest.mark.skipif(_java() is None, reason="needs JDK_17 / JAVA_HOME")
@pytest.mark.parametrize(("dds", "sysin", "inputs", "want"), [
    (CASES[0][0], CASES[0][1], {"APP.IN": ["DDDD", "AAAA", "CCCC", "BBBB"]}, ["AAAA", "BBBB", "CCCC", "DDDD"]),
    (CASES[1][0], CASES[1][1], {"APP.IN": ["DDDD", "AAAA", "CCCC"]}, ["DDDD", "AAAA", "CCCC"]),
    (CASES[2][0], CASES[2][1], {"A": ["AAAA", "CCCC"], "B": ["BBBB", "DDDD"]}, ["AAAA", "BBBB", "CCCC", "DDDD"]),
], ids=IDS)  # fmt: skip
def test_the_forged_files_compile_with_the_real_cobolrecords_and_run(tmp_path, dds, sysin, inputs, want):
    (tmp_path / "estate").mkdir()
    forges = _estate(tmp_path / "estate", dds, sysin)
    java = tmp_path / "java"
    srcs = forges.sources()
    pkg_dir = java / PKG.replace(".", "/")
    # the forge's own files, but for the Spring batch package (_batch_package writes it without Spring)
    for (base, sub), files in srcs.items():
        if (base, sub) != ("entity", "vsam") and not (
            base == "base_pkg" and sub.split("/")[0] in ("service", "cobolrt")
        ):
            continue
        out = pkg_dir / ("entity" if base == "entity" else "") / sub
        out.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            if base != "entity" or name == "CobolRecords":
                text = text.replace("@Service\n", "").replace("import org.springframework.stereotype.Service;\n", "")
                (out / f"{name}.java").write_text(text)
    _batch_package(java, "ISO-8859-1")
    data = tmp_path / "data"
    data.mkdir()
    for dsn, keys in inputs.items():
        (data / dsn).write_bytes(b"".join(k.encode().ljust(80) for k in keys))
    ((name, _),) = srcs[("base_pkg", "service")].items()
    b = f"{PKG}.batch"
    in_dds = ", ".join(f'new {b}.Dd("{d["dd"]}", "{d["dsn"]}", "SHR", null, null)' for d in dds if d["dd"] != "SORTOUT")
    out_dsn = next(d["dsn"] for d in dds if d["dd"] == "SORTOUT")
    (java / "Main.java").write_text(
        f"public class Main {{ public static void main(String[] a) {{ new {PKG}.service.{name}("
        f'new {b}.DatasetResolver("{data}"), new {b}.CobolFiles("", ""), new {b}.MainframeClock("", "UTC"))'
        f'.runBatch(java.util.List.of({in_dds}, new {b}.Dd("SORTOUT", "{out_dsn}", "NEW", "CATLG", null)), null); }} }}\n'
    )
    jdk = _java()
    classes = tmp_path / "classes"
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(classes), *map(str, java.rglob("*.java"))], check=True)  # fmt: skip
    subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(classes), "Main"],
                   capture_output=True, encoding="utf-8", check=True)  # fmt: skip
    assert (data / out_dsn).read_bytes() == b"".join(k.encode().ljust(80) for k in want)
