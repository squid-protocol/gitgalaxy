"""Regression tests for #5091 / #5109: java/javac subprocess calls must use UTF-8.

On Windows, java/javac default to the platform locale charset (e.g. cp1252), causing
source compilation errors on non-ASCII characters and reader thread failures
(stdout=None or UnicodeDecodeError) when subprocess.run captures with text=True.
The pattern from PR #5108:
  - `javac -encoding UTF-8`
  - `java -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8`
  - capture bytes and `.decode("utf-8")`
"""

from __future__ import annotations

import ast
from pathlib import Path
import shutil
import subprocess

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# The class of test files running bare `javac` / `java` on PATH in CI
JAVA_SUBPROCESS_TEST_FILES = [
    "tests/cics_crucible/test_cics_runtimes.py",
    "tests/cobol_mainframe/test_bidi_layout.py",
    "tests/cobol_mainframe/test_cobol_compare.py",
    "tests/cobol_mainframe/test_cobol_records_digits.py",
    "tests/cobol_mainframe/test_dbcs_widths.py",
    "tests/cobol_mainframe/test_facade_layout_4449.py",
    "tests/cobol_mainframe/test_floating_insertion.py",
    "tests/cobol_mainframe/test_runtimes_always.py",
    "tests/cobol_mainframe/test_time_zones.py",
]


@pytest.mark.parametrize("rel_path", JAVA_SUBPROCESS_TEST_FILES)
def test_java_subprocess_helpers_specify_utf8_flags(rel_path: str):
    """Ensure all test helpers invoking java/javac specify UTF-8 encoding flags."""
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Missing test file: {path}"
    content = path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # match subprocess.run(...)
        is_subp_run = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        )
        if not is_subp_run or not node.args:
            continue

        first_arg = node.args[0]
        if not isinstance(first_arg, (ast.List, ast.Tuple)):
            continue

        cmd_strings = []
        for elt in first_arg.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                cmd_strings.append(elt.value)
            elif isinstance(elt, ast.Name):
                cmd_strings.append(elt.id)

        # check javac calls
        if any("javac" in s for s in cmd_strings[:1]):
            assert "-encoding" in cmd_strings, f"{rel_path}:{node.lineno}: javac missing '-encoding'"
            enc_idx = cmd_strings.index("-encoding")
            assert enc_idx + 1 < len(cmd_strings) and cmd_strings[enc_idx + 1].upper() == "UTF-8", (
                f"{rel_path}:{node.lineno}: javac encoding must be UTF-8"
            )

        # check java calls (excluding python/git/docker/etc)
        if any("java" in s for s in cmd_strings[:1]) and not any("javac" in s for s in cmd_strings[:1]):
            has_utf8_flag = any("-Dfile.encoding=UTF-8" in s or "-Dstdout.encoding=UTF-8" in s for s in cmd_strings)
            assert has_utf8_flag, (
                f"{rel_path}:{node.lineno}: java missing -Dfile.encoding=UTF-8 / -Dstdout.encoding=UTF-8"
            )

            # Check keyword arguments for text=True without explicit encoding
            kw_dict = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            if "text" in kw_dict and isinstance(kw_dict["text"], ast.Constant) and kw_dict["text"].value is True:
                # If text=True, must specify explicit encoding="utf-8"
                assert "encoding" in kw_dict, (
                    f"{rel_path}:{node.lineno}: java subprocess uses text=True without explicit encoding='utf-8'; "
                    "capture bytes and .decode('utf-8') or pass encoding='utf-8'"
                )


@pytest.mark.skipif(not shutil.which("javac") or not shutil.which("java"), reason="needs JDK (javac + java)")
def test_utf8_javac_and_java_roundtrip_not_sign_and_multibyte(tmp_path: Path):
    """Verify UTF-8 java execution round-trips the '¬' not-sign (#5091) and multibyte characters."""
    pkg = tmp_path / "t" / "probe"
    pkg.mkdir(parents=True)
    probe_src = (
        "package t.probe;\n\n"
        "public class Utf8Probe {\n"
        "    public static void main(String[] args) {\n"
        '        System.out.println("TEST_START");\n'
        '        System.out.println("not_sign: \u00ac");\n'
        '        System.out.println("multibyte: \u4e16\u754c \u00d8 \u00a7 \u20ac");\n'
        '        System.out.println("TEST_END");\n'
        "    }\n"
        "}\n"
    )
    (pkg / "Utf8Probe.java").write_text(probe_src, encoding="utf-8")
    classes = tmp_path / "classes"

    built = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(classes), str(pkg / "Utf8Probe.java")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr

    # Pattern from PR #5108: -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8, capture bytes, decode UTF-8
    proc = subprocess.run(
        [
            "java",
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-cp",
            str(classes),
            "t.probe.Utf8Probe",
        ],
        capture_output=True,
        check=True,
    )
    lines = proc.stdout.decode("utf-8").splitlines()
    assert lines == [
        "TEST_START",
        "not_sign: ¬",
        "multibyte: 世界 Ø § €",
        "TEST_END",
    ]
