"""#4172: det_survey keys work directories by the program's path in its corpus (no race between same-named members
under --jobs) and takes javac's classpath from the estate's declared dependencies, not every ~/.m2 jar."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import det_survey as ds  # noqa: E402


def test_same_named_members_in_different_folders_get_different_work_dirs():
    a, b = ds.work_key("samples/a/SAM1.cbl"), ds.work_key("samples/b/SAM1.cbl")
    assert a != b and "/" not in a and "/" not in b


def test_the_classpath_comes_from_the_estate_not_every_m2_jar(tmp_path, monkeypatch):
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "survey-classpath.txt").write_text(
        f"/m2/spring-core.jar{os.pathsep}/m2/lombok.jar\n", encoding="utf-8"
    )
    cp = ds.classpath(tmp_path)
    assert cp == f"{tmp_path / 'target/classes'}{os.pathsep}/m2/spring-core.jar{os.pathsep}/m2/lombok.jar"


def test_the_survey_translates_on_the_engine_layouts_unless_told_not_to(tmp_path, monkeypatch):
    """#5649: survey_program asks for the engine's layouts in the mode it is given (check by default: a difference is
    the row's error) and hands them to translate(); layouts=None never asks; the row says how many records the
    engine laid out."""
    import equivalence_common

    from gitgalaxy.tools.cobol_to_java.det import program as P

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "TOY.cbl").write_text("       PROCEDURE DIVISION.\n           STOP RUN.\n", encoding="utf-8")
    project = tmp_path / "estate" / "project"
    project.mkdir(parents=True)
    asked: list = []
    handed: list = []

    class _Res:
        service, java = "ToyService", "class ToyService {}\n"
        stats = {"statements": 1, "translated": 1, "holes": [], "engine_layouts": {"engine": 2, "own": 1}}

    monkeypatch.setattr(equivalence_common, "engine_layouts", lambda proj, corp, rel, mode: asked.append((rel, mode)) or mode)
    monkeypatch.setattr(P, "translate", lambda *a, **kw: handed.append(kw.get("layouts")) or _Res)
    for mode in ("check", "engine", None):
        row = ds.survey_program(corpus / "TOY.cbl", corpus, project, [corpus], tmp_path / "work", None, mode)
        assert row["engine_layouts"] == {"engine": 2, "own": 1}
    assert asked == [("TOY.cbl", "check"), ("TOY.cbl", "engine")]
    assert handed == ["check", "engine", None]
