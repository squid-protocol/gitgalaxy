"""#8886 remaining slice 3: the forge's generated `DatasetResolver` resolves a GDG relative number once per job.

On z/OS a relative generation number ((+1), (0), (-n)) is resolved ONCE per job, when the job first names the base. The
runtime class the forge writes keeps a per-job snapshot of each base's newest generation (`enter(jobId)` starts a new
job's snapshot). The nightly run exercises it end to end (COMBTRAN STEP05R writes (+1), STEP10 reads it); this compiles
the real generated `Dd` + `DatasetResolver` source (the forge's `_RUNTIME` text, not a copy) and drives the resolver
directly, so the three behaviours a Spring run cannot isolate are each pinned:

* inside one job, (+1) is the same generation before and after the step writes it, and (0) stays the generation the job
  started with even once a newer one exists on disk;
* the next job (a new `enter`) re-snapshots and sees the generation the last job wrote;
* a caller that never enters a job (a service run alone) counts the generations live, and a base with no generation yet
  starts at G0001V00.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))
import equivalence_forged_spring as efs  # noqa: E402

from gitgalaxy.tools.cobol_to_java import cobol_to_java_batch_forge as forge  # noqa: E402

PKG = "gg.resolver"

DRIVE = """package gg.resolver;

import java.nio.file.Files;
import java.nio.file.Path;

public final class Drive {
    static void show(String label, DatasetResolver r, String dsn, String gen) {
        Path p = r.path(new Dd("DD", dsn, "SHR", "KEEP", gen));
        System.out.println(label + "=" + (p == null ? "null" : root.relativize(p).toString()));
    }

    static Path root;

    public static void main(String[] a) throws Exception {
        root = Path.of(a[0]);
        Files.createDirectories(root.resolve("A.B"));
        Files.writeString(root.resolve("A.B").resolve("G0001V00"), "one");
        Files.writeString(root.resolve("A.B").resolve("G0002V00"), "two");
        DatasetResolver r = new DatasetResolver(a[0]);
        r.enter(1);
        show("job1 plus1", r, "A.B", "+1");
        Files.writeString(root.resolve("A.B").resolve("G0003V00"), "three");  // the step writes the generation
        show("job1 zero after the write", r, "A.B", "0");
        show("job1 plus1 after the write", r, "A.B", "+1");
        show("job1 minus1 after the write", r, "A.B", "-1");
        r.enter(1);  // a later step of the same job: no new snapshot
        show("job1 zero in a later step", r, "A.B", "0");
        show("job1 new base plus1", r, "C.D", "+1");
        Files.createDirectories(root.resolve("C.D"));
        Files.writeString(root.resolve("C.D").resolve("G0001V00"), "new");
        show("job1 new base zero after the write", r, "C.D", "0");
        r.enter(2);  // the next job re-snapshots
        show("job2 zero", r, "A.B", "0");
        show("job2 plus1", r, "A.B", "+1");
        show("job2 new base zero", r, "C.D", "0");
        DatasetResolver live = new DatasetResolver(a[0]);  // never entered a job: counted live
        show("live zero", live, "A.B", "0");
        Files.writeString(root.resolve("A.B").resolve("G0004V00"), "four");
        show("live zero after a write", live, "A.B", "0");
        show("plain dsn", live, "A.B", null);
        show("no dsn", live, null, null);
    }
}
"""

pytestmark = [
    pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK"),
    pytest.mark.skipif(efs.classpath() is None, reason="no Spring jars in the local Maven repository"),
]


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> dict[str, str]:
    work = tmp_path_factory.mktemp("resolver")
    src = work / "src" / "gg" / "resolver"
    src.mkdir(parents=True)
    for name in ("Dd", "DatasetResolver"):
        (src / f"{name}.java").write_text(forge._RUNTIME[name].replace("{pkg}", PKG), encoding="utf-8")
    (src / "Drive.java").write_text(DRIVE, encoding="utf-8")
    cp = ":".join(str(j) for j in efs.classpath() or [])
    classes = work / "classes"
    classes.mkdir()
    javac = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-cp", cp, "-d", str(classes), *map(str, src.glob("*.java"))],
        capture_output=True, encoding="utf-8", check=False,
    )  # fmt: skip
    assert javac.returncode == 0, javac.stderr
    datasets = work / "datasets"
    datasets.mkdir()
    out = subprocess.run(
        ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", f"{classes}:{cp}", f"{PKG}.Drive", str(datasets)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )  # fmt: skip
    assert out.returncode == 0, out.stderr
    return dict(line.split("=", 1) for line in out.stdout.splitlines())


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("job1 plus1", "A.B/G0003V00"),
        ("job1 plus1 after the write", "A.B/G0003V00"),  # the same generation the step wrote
        ("job1 zero after the write", "A.B/G0002V00"),  # (0) stays what the job started with
        ("job1 minus1 after the write", "A.B/G0001V00"),
        ("job1 zero in a later step", "A.B/G0002V00"),  # `enter` of the same job keeps the snapshot
    ],
)
def test_a_relative_number_is_resolved_once_per_job(run, label, expected):
    assert Path(run[label]).as_posix() == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("job2 zero", "A.B/G0003V00"),  # the next job sees the generation the last one wrote
        ("job2 plus1", "A.B/G0004V00"),
        ("job1 new base plus1", "C.D/G0001V00"),  # no generation yet: the first one
        ("job1 new base zero after the write", "C.D/G0001V00"),
        ("job2 new base zero", "C.D/G0001V00"),
    ],
)
def test_a_new_job_takes_a_new_snapshot_and_a_new_base_starts_at_one(run, label, expected):
    assert Path(run[label]).as_posix() == expected


def test_a_caller_that_never_enters_a_job_counts_the_generations_live(run):
    assert Path(run["live zero"]).as_posix() == "A.B/G0003V00"
    assert Path(run["live zero after a write"]).as_posix() == "A.B/G0004V00"
    assert Path(run["plain dsn"]).as_posix() == "A.B"
    assert run["no dsn"] == "null"
