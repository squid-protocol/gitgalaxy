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


SUBPROCESS_FUNCS = {"run", "Popen", "check_output", "check_call"}
JAVA_NAMES = {"java", "javac", "java_bin", "javac_bin", "JAVA_BIN", "_JDK"}


def _launcher_kind(node: ast.expr) -> str | None:
    """ "java" / "javac" when `node` names the launcher: the bare "java", `str(jdk / "java")`,
    `jdk / "bin" / "javac"`, or a variable called java / javac (#5128: the resolved-JDK forms)."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and node.args:
        return _launcher_kind(node.args[0])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "tool":
        last = node.args[-1] if node.args else None  # dp.tool(None, "java")
        return _launcher_kind(last) if last is not None else None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        name = node.value.replace("\\", "/").rsplit("/", 1)[-1]
        return name if name in ("java", "javac") else None
    if isinstance(node, ast.Name):
        return node.id if node.id in ("java", "javac") else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _launcher_kind(node.right)
    return None


def _is_tool_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "tool"


def _java_calls(source: str) -> list[tuple[ast.expr, str, list[str]]]:
    """Every subprocess call in `source` that starts a java/javac: (call, kind, the constant argv strings)."""
    found = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr in SUBPROCESS_FUNCS
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            continue
        argv = node.args[0]
        if not isinstance(argv, (ast.List, ast.Tuple)) or not argv.elts:
            continue
        kind = _launcher_kind(argv.elts[0])
        if kind:
            strings = [e.value for e in argv.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            found.append((node, kind, strings))
    # argv built into a variable and handed to a wrapper: `argv = [dp.tool(None, "java"), ...]; dp.run(argv)`
    for node in ast.walk(tree):
        if isinstance(node, ast.List) and node.elts and _is_tool_call(node.elts[0]):
            kind = _launcher_kind(node.elts[0])
            if kind and not any(c is node for c, _, _ in found):
                strings = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                found.append((node, kind, strings))
    return found


def _violations(source: str, label: str) -> list[str]:
    bad = []
    for node, kind, strings in _java_calls(source):
        where = f"{label}:{node.lineno}"
        if kind == "javac":
            if "-encoding" not in strings or strings[
                strings.index("-encoding") + 1 : strings.index("-encoding") + 2
            ] != ["UTF-8"]:
                bad.append(f"{where}: javac missing '-encoding UTF-8'")
        else:
            for flag in ("-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8"):
                if flag not in strings:
                    bad.append(f"{where}: java missing {flag}")
        kw = {k.arg: k.value for k in getattr(node, "keywords", []) if k.arg}
        text = kw.get("text")
        if text is not None and "encoding" not in kw and not (isinstance(text, ast.Constant) and text.value is False):
            bad.append(
                f"{where}: java/javac uses text= without encoding='utf-8'; capture bytes and decode, or pass encoding"
            )
    return bad


MVN_UTF8_FLAGS = ("-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8")


def _is_maven_launcher(node: ast.expr) -> bool:
    """#5161: argv[0] is Maven: `mvn_executable(...)`, a literal "mvn"/"mvn.cmd", `shutil.which("mvn")`, or a `mvn` name."""
    if isinstance(node, ast.Call):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name == "mvn_executable":
            return True
        return name == "which" and bool(node.args) and _is_maven_launcher(node.args[0])
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.replace("\\", "/").rsplit("/", 1)[-1] in ("mvn", "mvn.cmd")
    return isinstance(node, ast.Name) and node.id in ("mvn", "mvn_bin")


def _maven_calls(source: str) -> list[ast.Call]:
    """Every `subprocess.run/Popen/...` whose argv is a list starting with Maven (the `[mvn, *flags]` form too).
    Byte-capturing wrappers (`dp.run`) and file-redirecting callers are not matched: they never decode with the locale."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr in SUBPROCESS_FUNCS
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            continue
        argv = node.args[0]
        if isinstance(argv, (ast.List, ast.Tuple)) and argv.elts and _is_maven_launcher(argv.elts[0]):
            found.append(node)
    return found


def _maven_violations(source: str, label: str) -> list[str]:
    """A Maven subprocess that captures text must name its charset (`encoding=`), and a `-DargLine=` literal must carry
    the JVM's UTF-8 flags (a non-literal argLine is checked where the variable is built)."""
    bad = []
    for node in _maven_calls(source):
        where = f"{label}:{node.lineno}"
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        text = kw.get("text")
        if text is not None and "encoding" not in kw and not (isinstance(text, ast.Constant) and text.value is False):
            bad.append(f"{where}: mvn uses text= without encoding='utf-8'")
        for sub in ast.walk(node.args[0]):
            is_argline = (
                isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value.startswith("-DargLine=")
            )
            if is_argline and not all(f in sub.value for f in MVN_UTF8_FLAGS):
                bad.append(f"{where}: mvn -DargLine lacks {' '.join(MVN_UTF8_FLAGS)}")
    return bad


def _scanned_files() -> list[Path]:
    return sorted(p for p in (REPO_ROOT / "tests").rglob("*.py") if p.name != Path(__file__).name)


@pytest.mark.parametrize("rel_path", JAVA_SUBPROCESS_TEST_FILES)
def test_java_subprocess_helpers_specify_utf8_flags(rel_path: str):
    """The files named in the list above run java/javac, and every call is UTF-8 safe."""
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Missing test file: {path}"
    source = path.read_text(encoding="utf-8")
    assert _java_calls(source), f"{rel_path}: no java/javac subprocess call found (guard went blind)"
    assert not _violations(source, rel_path)


def test_no_java_subprocess_in_tests_decodes_with_locale_charset():
    """Whole class (#5128): bare, `str(jdk / "java")`, `jdk / "bin" / "java"`, `_JDK`, `java_bin` and variable forms."""
    bad = []
    for path in _scanned_files():
        bad += _violations(path.read_text(encoding="utf-8"), path.relative_to(REPO_ROOT).as_posix())
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize(
    "source",
    [
        'subprocess.run([str(jdk / "javac"), "-d", "out", "A.java"])',
        'subprocess.run([str(_JDK / "java"), "-cp", "out", "A"], capture_output=True, text=True, encoding="utf-8")',
        'subprocess.run([str(jdk / "bin" / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "A"], text=True)',
        'subprocess.run([java_bin / "java", "-Dfile.encoding=UTF-8", "A"])',
        'subprocess.run([javac, "-d", "out"])',
        'argv = [dp.tool(None, "java"), "-cp", "x"]',
        'subprocess.run(["javac", "-encoding", "ISO-8859-1", "A.java"])',
    ],
)
def test_guard_flags_resolved_path_forms(source: str):
    """The guard is not vacuous: each resolved-path form it exists for is caught when the flags are missing."""
    assert _violations(source, "synthetic")


@pytest.mark.parametrize(
    "source",
    [
        'subprocess.run([str(jdk / "javac"), "-encoding", "UTF-8", "-d", "out"], check=True)',
        'subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "A"], capture_output=True, text=True, encoding="utf-8")',
        'subprocess.run(["git", "log"], text=True)',
    ],
)
def test_guard_accepts_the_pattern(source: str):
    assert not _violations(source, "synthetic")


def test_no_maven_subprocess_in_tests_decodes_with_locale_charset():
    """#5161: Maven starts JVMs too (its own, surefire's fork); every `mvn` subprocess in tests/ names its charset."""
    bad = []
    for path in _scanned_files():
        bad += _maven_violations(path.read_text(encoding="utf-8"), path.relative_to(REPO_ROOT).as_posix())
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("rel_path", ["tests/tools/mutation.py"])
def test_maven_guard_is_not_blind(rel_path: str):
    assert _maven_calls((REPO_ROOT / rel_path).read_text(encoding="utf-8")), f"{rel_path}: no mvn call found"


def test_run_maven_argline_carries_the_utf8_flags():
    """The argLine `run_maven` builds is a variable, so the guard cannot see it: pin it at the source."""
    source = (REPO_ROOT / "tests/tools/equivalence_java.py").read_text(encoding="utf-8")
    assert 'f"{JVM_UTF8_FLAGS} {argline}"' in source
    assert "-DargLine={maven_argline}" in source
    assert 'encoding="utf-8"' in source[source.index("env=maven_utf8_env(shell)") :][:200]


@pytest.mark.parametrize(
    "source",
    [
        'subprocess.run([mvn_executable(), "-q"], capture_output=True, text=True)',
        'subprocess.run([shutil.which("mvn"), "-q"], text=True)',
        'subprocess.run(["mvn", "-q"], text=True)',
        'subprocess.run([mvn, "test", "-DargLine=-Dx=1"], capture_output=True)',
    ],
)
def test_maven_guard_flags_locale_decoding(source: str):
    assert _maven_violations(source, "synthetic")


@pytest.mark.parametrize(
    "source",
    [
        'subprocess.run([mvn_executable(), "-q"], capture_output=True, text=True, encoding="utf-8")',
        'subprocess.run([mvn_executable(), "-q"], capture_output=True)',
        'subprocess.run([mvn, "test", "-DargLine=-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dx=1"])',
        'subprocess.run(["git", "log"], text=True)',
    ],
)
def test_maven_guard_accepts_the_pattern(source: str):
    assert not _maven_violations(source, "synthetic")


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
