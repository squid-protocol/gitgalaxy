"""batch strict structural-signature coverage."""

import sys
from pathlib import Path

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune


def test_batch_calls_out_strict():
    batch = LANGUAGE_DEFINITIONS["batch"]
    calls_out = batch["rules"]["calls_out"]

    # 1. Positives
    assert calls_out.findall("call :label") == ["label"]
    assert calls_out.findall("  call prog") == ["prog"]
    assert calls_out.findall("call :my-sub.routine") == ["my-sub.routine"]

    # 2. Negatives
    assert calls_out.findall("goto :label") == []
    assert calls_out.findall("echo call me") == []

    # 3. Capture groups
    assert calls_out.groups == 1

    # 4. ReDoS immunity
    payload1 = "call " + "a" * 100000
    payload2 = "\n" * 100000 + "call"
    assert_redos_immune(calls_out, payload1)
    assert_redos_immune(calls_out, payload2)


# --- #3338: func_start -- a `:label` that `call :label` reaches -------------

from gitgalaxy.core.detector import StructuralExtractor  # noqa: E402

# buildrelease.bat's shape (language-crucible v1.4.0, cpython/Tools/msi),
# trimmed: an option-parsing loop label, fall-through sections, one called
# subroutine that ends `exit /B 0`, and a goto-reached help block.
BUILDRELEASE = """@setlocal
:CheckOpts
if "%1" EQU "-h" goto Help
if "%1" EQU "-x64" (set BUILDX64=1) && shift && goto CheckOpts
:builddoc
if "%SKIPDOC%" EQU "1" goto skipdoc
:skipdoc
if defined BUILDX86 (
    call :build x86
    if errorlevel 1 exit /B %ERRORLEVEL%
)
if defined BUILDX64 call :BUILD x64
exit /B 0

:build
@setlocal
set BUILD=%Py_OutDir%%1\\
:inner
if not exist "%BUILD%" goto inner
exit /B 0

:Help
echo buildrelease.bat [--out DIR]
"""


def _splice(code):
    return StructuralExtractor("batch", LANGUAGE_DEFINITIONS).splice(code, "")


def test_batch_func_start_regex_strict():
    fs = LANGUAGE_DEFINITIONS["batch"]["rules"]["func_start"]
    assert [m.group(1) for m in fs.finditer(":build\n  :my-sub.v2\n")] == ["build", "my-sub.v2"]
    # `::` is the comment idiom; goto/call sites and drive letters are not labels.
    assert [m.group(1) for m in fs.finditer(":: comment\ngoto :build\ncall :build\nC:\\x\n")] == []
    assert fs.groups == 1
    assert_redos_immune(fs, ":" + "a" * 100000)
    assert_redos_immune(fs, " " * 100000 + ":")


def test_only_called_labels_are_units():
    """Scope decision: goto-only labels (loop heads, fall-through sections, a
    goto-reached help block) are jump targets, not subroutines."""
    result = _splice(BUILDRELEASE)
    assert [f["name"] for f in result["functions"]] == ["build"]
    # The count and the unit list are filtered alike (#2753/#3197 trap).
    assert result["equations"].get("func_start", 0) == 1


def test_called_subroutine_body_spans_internal_labels_and_stops_at_exit():
    """A subroutine's internal goto label (`:inner`) stays inside it, and the
    body is cut back to its last line-start `exit /B`, so `:Help` is not
    swallowed."""
    (unit,) = _splice(BUILDRELEASE)["functions"]
    lines = BUILDRELEASE.splitlines()
    first = lines.index(":build")
    last = lines.index(":Help") - 2  # the `exit /B 0` before the blank line
    assert lines[last] == "exit /B 0"
    assert unit["start_line"] == first + 1
    assert unit["loc"] == last - first + 1


def test_call_target_is_case_insensitive_and_needs_the_colon():
    assert [f["name"] for f in _splice("call :SUB\nexit /b\n:sub\necho x\nexit /b\n")["functions"]] == ["sub"]
    # `call sub.bat` runs another script; it does not reach `:sub`.
    assert _splice("call sub.bat\nexit /b\n:sub\necho x\n")["functions"] == []


def test_a_script_with_no_call_has_no_units():
    """cpython/Tools/msi/build.bat: two labels, both goto targets."""
    code = ':CheckOpts\nif "%~1" EQU "-h" goto Help\nshift && goto CheckOpts\nexit /B 0\n:Help\necho usage\n'
    assert _splice(code)["functions"] == []


def test_a_differently_cased_call_references_the_subroutine():
    """#3198 lexicon: `call :BUILD` names `:build`, so the unit is not an
    unreferenced_by_name orphan."""
    code = "call :BUILD x64\nexit /b 0\n:build\necho building %1\nexit /b 0\n"
    result = _splice(code)
    (unit,) = result["functions"]
    assert unit["name"] == "build"
    # A case-sensitive reading marks it an orphan (usage_status 1); verified.
    assert unit["usage_status"] == 0
    assert result["equations"].get("unreferenced_by_name", 0) == 0
