"""#5882: a project whose pom Maven built once is built with javac on the recorded classpath and runs direct; anything
unsure leaves it to Maven, with nothing left behind."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import equivalence_java as ej  # noqa: E402
import java_target_matrix as jtm  # noqa: E402

JAVA_HOME = jtm._jdk(17) or os.environ.get("JAVA_HOME", "")
pytestmark = pytest.mark.skipif(not (Path(JAVA_HOME) / "bin" / "javac").is_file(), reason="no JDK (javac)")


def _project(tmp: Path, body: str = "public int one() { return 1; }") -> Path:
    p = tmp / "java_h2"
    main = p / "src/main/java" / ej.PKG_DIR
    main.mkdir(parents=True)
    (main / "Svc.java").write_text(f"package {ej.PKG};\npublic class Svc {{ {body} }}\n", encoding="utf-8")
    test = p / ej.TEST_FILE
    test.parent.mkdir(parents=True)
    test.write_text(f"package {ej.PKG};\npublic class EquivalenceRunTest {{ int x = new Svc().one(); }}\n", encoding="utf-8")
    (p / "src/main/resources").mkdir(parents=True)
    (p / "src/main/resources/application.yml").write_text("spring:\n  main:\n    banner-mode: off\n", encoding="utf-8")
    (p / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    return p


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ej, "CLASSPATH_CACHE", tmp_path / "cache")
    monkeypatch.delenv(ej.MAVEN_ONLY_ENV, raising=False)
    return tmp_path / "cache"


def _shell():
    return dict(os.environ, JAVA_HOME=JAVA_HOME)


def test_a_recorded_pom_builds_with_javac_and_is_marked_for_a_direct_run(tmp_path, cache):
    p = _project(tmp_path)
    ej._save_classpath(p, [str(p / "target/test-classes"), str(p / "target/classes")])  # (no jars: the JDK alone)
    assert ej._javac_build(p, _shell())
    assert (p / "target/classes" / ej.PKG_DIR / "Svc.class").is_file()
    assert (p / "target/test-classes" / ej.PKG_DIR / "EquivalenceRunTest.class").is_file()
    assert (p / "target/classes/application.yml").is_file()
    assert (p / ej.PRECOMPILED).is_file() and (p / ej.TEST_SOURCE).read_bytes() == (p / ej.TEST_FILE).read_bytes()
    assert (p / ej.TEST_CLASSPATH).read_text().split(os.pathsep)[:2] == [str(p / "target/test-classes"),
                                                                          str(p / "target/classes")]  # fmt: skip


def test_the_record_keeps_only_the_dependencies_not_the_projects_own_classes(tmp_path, cache):
    p = _project(tmp_path)
    jar = tmp_path / "dep.jar"
    jar.write_bytes(b"")
    ej._save_classpath(p, [str(p / "target/test-classes"), str(p / "target/classes"), str(jar)])
    assert (cache / f"{ej._pom_key(p)}.txt").read_text().split() == [str(jar)]


@pytest.mark.parametrize("why", ["no record", "jar gone", "filtered resource", "compile error", "maven only"])
def test_anything_unsure_is_left_to_maven_with_nothing_built(tmp_path, cache, monkeypatch, why):
    p = _project(tmp_path, body="public int one() { return nope; }" if why == "compile error" else "public int one() { return 1; }")
    if why != "no record":
        ej._save_classpath(p, [str(tmp_path / "gone.jar")] if why == "jar gone" else [])
    if why == "filtered resource":
        (p / "src/main/resources/application.yml").write_text("info:\n  version: @project.version@\n", encoding="utf-8")
    if why == "maven only":
        monkeypatch.setenv(ej.MAVEN_ONLY_ENV, "1")
    assert not ej._javac_build(p, _shell())
    assert not (p / ej.PRECOMPILED).exists() and not (p / "target/classes").exists()


def test_two_corpora_share_a_record_their_names_aside(tmp_path, cache):
    a, b = _project(tmp_path / "a"), _project(tmp_path / "b")
    pom = "<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent><artifactId>{}</artifactId>" \
          "<name>{}</name><dependencies><dependency><artifactId>x</artifactId></dependency></dependencies></project>"
    (a / "pom.xml").write_text(pom.format("cics-genapp", "cics-genapp"), encoding="utf-8")
    (b / "pom.xml").write_text(pom.format("cics-cbsa", "cics-cbsa"), encoding="utf-8")
    assert ej._pom_key(a) == ej._pom_key(b)
    (b / "pom.xml").write_text(pom.format("cics-cbsa", "cics-cbsa").replace("<artifactId>x<", "<artifactId>y<"))
    assert ej._pom_key(a) != ej._pom_key(b)  # a dependency of its own: its own record


def test_a_different_pom_is_a_different_record(tmp_path, cache):
    p = _project(tmp_path)
    key = ej._pom_key(p)
    (p / "pom.xml").write_text("<project><dependencies/></project>\n", encoding="utf-8")  # e.g. Db2's driver patched in
    assert ej._pom_key(p) != key
    shutil.rmtree(p)
