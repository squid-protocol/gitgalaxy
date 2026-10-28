"""#6861: a Java side that fails prints its reason, not only the path of a report CI does not keep."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_common as common

MAVEN_LOG = """[INFO] Compiling 40 source files
[ERROR] /work/java/src/main/java/X.java:[12,5] cannot find symbol
[ERROR] Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin
[ERROR] Re-run Maven using the -X switch to enable full debug logging.
"""
CASE = {"name": "c", "program": "P"}


def test_the_reason_follows_the_report_path(tmp_path, capsys):
    (tmp_path / "java").mkdir()
    (tmp_path / "java" / "maven.log").write_text(MAVEN_LOG, encoding="utf-8")
    failed = common.write_java_failure(CASE, tmp_path, "")
    out = capsys.readouterr().out
    assert (tmp_path / "report.json").is_file() and failed["java_failed"]
    assert out.splitlines()[0] == f"P: the Java side failed -- see {tmp_path / 'report.json'}"
    assert "X.java:[12,5] cannot find symbol" in out and "Re-run Maven" not in out and "```" not in out


def test_the_error_text_is_shown_when_there_is_no_maven_log(tmp_path, capsys):
    common.write_java_failure(CASE, tmp_path, "javac timed out after 300s compiling EquivalenceMain")
    assert "javac timed out after 300s" in capsys.readouterr().out


def test_a_long_reason_is_capped_and_its_head_survives(tmp_path, capsys):
    (tmp_path / "java").mkdir()
    (tmp_path / "java" / "maven.log").write_text(
        "".join(f"[ERROR] Y.java:[{n},1] error number {n}\n" for n in range(1, 40)), encoding="utf-8"
    )
    common.write_java_failure(CASE, tmp_path, "")
    reason = capsys.readouterr().out.split("\n", 1)[1]
    assert len(reason) <= common.JAVA_FAILURE_SHOWN + 1 and "error number 1\n" in reason


def test_the_three_harnesses_use_the_helper():
    here = Path(__file__).resolve().parent
    for name in ("equivalence.py", "equivalence_cics.py", "equivalence_call.py"):
        text = (here / name).read_text(encoding="utf-8")
        assert re.search(r"write_java_failure\(case, work, str\(e\)\)", text), name
        assert "the Java side failed" not in text, name  # one print site: the helper
