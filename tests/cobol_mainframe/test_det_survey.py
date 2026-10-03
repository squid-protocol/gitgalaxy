"""#4172: det_survey keys work directories by the program's path in its corpus (no race between same-named members
under --jobs) and takes javac's classpath from the estate's declared dependencies, not every ~/.m2 jar."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import det_survey as ds  # noqa: E402


def test_same_named_members_in_different_folders_get_different_work_dirs():
    a, b = ds.work_key("samples/a/SAM1.cbl"), ds.work_key("samples/b/SAM1.cbl")
    assert a != b and "/" not in a and "/" not in b


def test_the_classpath_comes_from_the_estate_not_every_m2_jar(tmp_path, monkeypatch):
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "survey-classpath.txt").write_text("/m2/spring-core.jar:/m2/lombok.jar\n", encoding="utf-8")
    cp = ds.classpath(tmp_path)
    assert cp == f"{tmp_path / 'target/classes'}:/m2/spring-core.jar:/m2/lombok.jar"
