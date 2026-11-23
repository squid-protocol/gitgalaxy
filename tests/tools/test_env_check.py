"""env_check.py (tests/tools/box): the pure parts of the machine-setup check (2026-11-23)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "box"))
import env_check as ec


def test_jdk_major_reads_java_version_text_and_jvm_dir_names():
    assert ec.jdk_major('openjdk version "17.0.9" 2023-10-17') == 17
    assert ec.jdk_major('openjdk version "21.0.13.1" 2026-11-17') == 21
    assert ec.jdk_major('java version "1.8.0_392"') == 8
    assert ec.jdk_major("java-21-openjdk-amd64") == 21
    assert ec.jdk_major("java-1.17.0-openjdk-amd64") == 17
    assert ec.jdk_major("default-java") is None


def test_pick_jdk_prefers_17_then_the_lowest_newer_and_needs_a_javac():
    dirs = [
        "/usr/lib/jvm/java-21-openjdk-amd64",
        "/usr/lib/jvm/java-17-openjdk-amd64",
        "/usr/lib/jvm/java-11-openjdk-amd64",
    ]
    assert ec.pick_jdk(dirs, lambda _d: True).endswith("java-17-openjdk-amd64")
    assert ec.pick_jdk(dirs, lambda d: "17" not in d).endswith("java-21-openjdk-amd64")  # no 17 javac: the newer one
    assert ec.pick_jdk(dirs, lambda d: "11" in d) is None  # only a too-old JDK
    assert ec.pick_jdk(dirs, lambda _d: False) is None  # a JRE-only box


def test_corpora_needed_reads_case_files_and_drops_the_sibling_crucibles(tmp_path):
    for name, corpus in (
        ("a", "cics-genapp"),
        ("b", "cics-genapp"),
        ("c", "cics-crucible"),
        ("d", "zecs"),
        ("e", None),
    ):
        (tmp_path / name).mkdir()
        (tmp_path / name / "case.json").write_text(json.dumps({"corpus": corpus} if corpus else {}), encoding="utf-8")
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "case.json").write_text("{not json", encoding="utf-8")
    assert ec.corpora_needed(tmp_path) == ["cics-genapp", "zecs"]


def test_ref_matches_accepts_a_short_manifest_sha_and_rejects_empty_or_different():
    assert ec.ref_matches("417334533178abcdef", "4173345331")
    assert ec.ref_matches("4173345331", "417334533178abcdef")
    assert not ec.ref_matches("deadbeef", "4173345331")
    assert not ec.ref_matches("", "4173345331") and not ec.ref_matches("abc", "")


def test_the_table_prints_a_fix_line_only_for_gaps_and_marks_optional():
    out = ec.render_table(
        [
            ec.Item("docker", True, "server 27"),
            ec.Item("maven", False, "not on PATH", "apt install maven"),
            ec.Item("extra", False, "no", required=False),
        ]
    )
    assert "PASS" in out and "MISSING" in out and "optional" in out
    assert out.count("fix:") == 1 and "apt install maven" in out


def test_export_lines_quote_and_skip_empty_values():
    out = ec.export_lines({"JAVA_HOME": "/usr/lib/jvm/java-17", "X": "", "Y": "has space"})
    assert out == "export JAVA_HOME=/usr/lib/jvm/java-17\nexport Y='has space'"
