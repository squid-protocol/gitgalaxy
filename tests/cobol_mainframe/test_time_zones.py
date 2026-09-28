import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import generate_application_yml
from gitgalaxy.tools.cobol_to_java.cobol_to_java_db2_forge import sql_java_type
from gitgalaxy.tools.cobol_to_java.java_target import load_target

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "tools"))
import equivalence as eq
from equivalence_java import equivalence_test


def get_forge(target):
    return BatchForge(
        {"P": {"program": {"file": "f", "program_ids": ["PROG"]}}},
        {
            "sections": {
                "job_steps": {"facts": [{"file": "f", "steps": [{"step": "s", "ordinal": 1, "program": "PROG"}]}]}
            }
        },
        "com.gitgalaxy",
        target,
    )


def test_mainframe_clock_generation():
    target = load_target(None)
    target.culture.zone = "Asia/Kolkata"
    forge = get_forge(target)
    src = forge.sources()[("base_pkg", "batch")]["MainframeClock"]
    assert "${gitgalaxy.zone:${gitgalaxy.culture.zone:Asia/Kolkata}}" in src  # #3934
    assert "ZonedDateTime zonedNow()" in src
    assert "String currentDate()" in src


def test_mainframe_clock_default_zone():
    target = load_target(None)
    forge = get_forge(target)
    src = forge.sources()[("base_pkg", "batch")]["MainframeClock"]
    assert "${gitgalaxy.zone:${gitgalaxy.culture.zone:UTC}}" in src


def test_db2_timestamp_types():
    assert sql_java_type("TIMESTAMP WITH TIME ZONE") == "OffsetDateTime"
    assert sql_java_type("TIMESTAMP") == "LocalDateTime"


def test_equivalence_harness_zone_plumbing(tmp_path, monkeypatch):
    case_with_zone = {
        "name": "c",
        "program": "P",
        "datasets": {},
        "clock": "2022/01/01 12:00:00.00",
        "zone": "Europe/Berlin",
    }
    case_no_zone = {"name": "c", "program": "P", "datasets": {}, "clock": "2022/01/01 12:00:00.00"}

    java_src = equivalence_test(case_with_zone)
    assert '"gitgalaxy.zone=Europe/Berlin"' in java_src

    java_src_no = equivalence_test(case_no_zone)
    assert '"gitgalaxy.zone=UTC"' in java_src_no

    def fake_run(*args, **kwargs):
        # the volume is f"{work}:/work"; cut at the last colon, as a Windows path has a drive letter
        work_dir = args[0][4].rpartition(":")[0]
        (Path(work_dir) / "RETURN-CODE").write_text("0")

        class Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return Proc()

    monkeypatch.setattr(eq.subprocess, "run", fake_run)

    case_with_zone["program_source"] = "P.cbl"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "P.cbl").write_text(" ")

    work = tmp_path / "work"
    eq.run_cobol(case_with_zone, corpus, work)
    script = (work / "run.sh").read_text()
    assert "TZ='Europe/Berlin'" in script

    work2 = tmp_path / "work2"
    case_no_zone["program_source"] = "P.cbl"
    eq.run_cobol(case_no_zone, corpus, work2)
    script2 = (work2 / "run.sh").read_text()
    assert "TZ=" not in script2


@pytest.mark.skipif(not shutil.which("javac"), reason="No JDK")
def test_mainframe_clock_compilation_and_run(tmp_path):
    target = load_target(None)
    target.culture.zone = "Asia/Kolkata"
    forge = get_forge(target)
    src = forge.sources()[("base_pkg", "batch")]["MainframeClock"]

    src = src.replace("@Component", "")
    src = src.replace('@Value("${gitgalaxy.clock:}")', "")
    src = src.replace('@Value("${gitgalaxy.zone:${gitgalaxy.culture.zone:Asia/Kolkata}}")', "")
    src = src.replace("import org.springframework.beans.factory.annotation.Value;", "")
    src = src.replace("import org.springframework.stereotype.Component;", "")

    main = """
    public static void main(String[] args) {
        MainframeClock clock = new MainframeClock("2022-07-18T10:30:15.00", "Asia/Kolkata");
        System.out.println(clock.currentDate());
    }
    """
    src = src.replace("public class MainframeClock {", "public class MainframeClock {" + main)

    pkg_dir = tmp_path / "com" / "gitgalaxy" / "batch"
    pkg_dir.mkdir(parents=True)
    java_file = pkg_dir / "MainframeClock.java"
    java_file.write_text(src)

    subprocess.run(["javac", str(java_file)], check=True)
    res = subprocess.run(
        ["java", "-cp", str(tmp_path), "com.gitgalaxy.batch.MainframeClock"], capture_output=True, text=True, check=True
    )
    assert res.stdout.strip() == "2022071810301500+0530"


# ---- #3934: the zone the generated application.yml writes is the zone the clock reads ----------------
_VALUE = re.compile(r'@Value\("(\$\{gitgalaxy\.zone:.*?\})"\) String zoneId')


def _flatten(tree, prefix=""):
    out = {}
    for key, value in (tree or {}).items():
        name = f"{prefix}{key}"
        out.update(_flatten(value, name + ".") if isinstance(value, dict) else {name: str(value)})
    return out


def _resolve(expr, props):
    """Spring's `${key:default}` placeholder, the default itself resolved (nested), innermost first."""
    while "${" in expr:
        start = expr.rindex("${")
        end = expr.index("}", start)
        key, _, default = expr[start + 2 : end].partition(":")
        expr = expr[:start] + props.get(key, default) + expr[end + 1 :]
    return expr


def _clock_zone(target, props):
    src = get_forge(target).sources()[("base_pkg", "batch")]["MainframeClock"]
    return _resolve(_VALUE.search(src).group(1), props)


def test_the_yml_zone_is_the_zone_the_clock_reads():
    """The application.yml of a culture.zone: Asia/Kolkata migration names the clock's zone, and editing that
    key there -- as the file invites -- moves the clock. gitgalaxy.zone (the equivalence harness pins it per
    case) still wins; with neither set, the zone baked in at generation stands."""
    yaml = pytest.importorskip("yaml")
    target = load_target(None)
    target.culture.zone = "Asia/Kolkata"
    props = _flatten(yaml.safe_load(generate_application_yml("demo", target)))
    assert props["gitgalaxy.culture.zone"] == "Asia/Kolkata"
    assert _clock_zone(target, props) == "Asia/Kolkata"
    assert _clock_zone(target, {**props, "gitgalaxy.culture.zone": "Europe/Berlin"}) == "Europe/Berlin"
    assert _clock_zone(target, {**props, "gitgalaxy.zone": "UTC"}) == "UTC"
    assert _clock_zone(target, {}) == "Asia/Kolkata"


def test_the_yml_says_which_culture_keys_are_read_at_run_time():
    target = load_target(None)
    target.culture.zone = "Asia/Kolkata"
    yml = generate_application_yml("demo", target)
    assert "zone is read at run time" in yml and "regenerate" in yml
    assert "gitgalaxy" not in generate_application_yml("demo", load_target(None))  # the default file is unchanged
