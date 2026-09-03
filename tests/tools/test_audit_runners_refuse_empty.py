"""#2682: every corpus-backed audit runner must refuse to report success when it checked nothing.

Three runners used to (or could) print "all OK" with exit 0 after skipping every language --
tri_comparison_chart.py did exactly that when galaxyscope was off PATH. These tests pin the
refuse-to-no-op behaviour of each, plus rosetta_audit.py's pure classification.

Sibling-module import pattern per CLAUDE.md "Testing conventions" (no tests/__init__.py).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import rosetta_audit  # noqa: E402


# --- rosetta_audit.classify -----------------------------------------------------------------


def test_classify_pass_is_clean_and_error_is_broken():
    verdicts = rosetta_audit.classify({"go": rosetta_audit.PASS, "lua": rosetta_audit.ERROR}, None)
    assert verdicts == {"go": rosetta_audit.CLEAN, "lua": rosetta_audit.BROKEN}


def test_classify_without_baseline_reports_failures_as_moved():
    verdicts = rosetta_audit.classify({"go": rosetta_audit.FAIL}, None)
    assert verdicts == {"go": rosetta_audit.MOVED}


def test_classify_against_baseline_splits_regression_from_pre_existing_drift():
    current = {"go": rosetta_audit.FAIL, "yaml": rosetta_audit.FAIL, "tcl": rosetta_audit.FAIL, "c": rosetta_audit.PASS}
    baseline = {"go": rosetta_audit.PASS, "yaml": rosetta_audit.FAIL, "tcl": rosetta_audit.ERROR}
    verdicts = rosetta_audit.classify(current, baseline)
    assert verdicts["go"] == rosetta_audit.REGRESSION  # fails here, passed on main: this build moved it
    assert verdicts["yaml"] == rosetta_audit.PRE_EXISTING  # fails on both: corpus is behind main
    assert verdicts["tcl"] == rosetta_audit.BROKEN  # the baseline run itself crashed
    assert verdicts["c"] == rosetta_audit.CLEAN


# --- rosetta_audit.main refuses to run on nothing --------------------------------------------


def test_rosetta_audit_exits_2_without_a_corpus(tmp_path):
    assert rosetta_audit.main(["--corpus", str(tmp_path)]) == 2


def test_rosetta_audit_exits_2_with_zero_language_folders(tmp_path, monkeypatch):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "verify_language.py").write_text("raise SystemExit(0)\n")
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("GALAXYSCOPE_BIN", sys.executable)  # any existing file; never reached
    assert rosetta_audit.main(["--corpus", str(tmp_path)]) == 2


def test_rosetta_audit_exits_2_without_galaxyscope(tmp_path, monkeypatch):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "verify_language.py").write_text("raise SystemExit(0)\n")
    (tmp_path / "data" / "go").mkdir(parents=True)
    (tmp_path / "data" / "go" / "expected_signals.json").write_text("{}")
    monkeypatch.delenv("GALAXYSCOPE_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))  # nothing on it
    assert rosetta_audit.main(["--corpus", str(tmp_path)]) == 2


def _fake_corpus(tmp_path: Path, script: str, languages=("go",)) -> Path:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "verify_language.py").write_text(script)
    for lang in languages:
        (tmp_path / "data" / lang).mkdir(parents=True)
        (tmp_path / "data" / lang / "expected_signals.json").write_text("{}")
    return tmp_path


def test_rosetta_audit_verifier_crash_is_broken_not_fail(tmp_path, monkeypatch):
    # Nonzero exit with no PASS/FAIL line = infrastructure, never "corpus drift".
    corpus = _fake_corpus(tmp_path, "import sys; print('Traceback: boom'); sys.exit(1)\n")
    monkeypatch.setenv("GALAXYSCOPE_BIN", sys.executable)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert rosetta_audit.main(["--corpus", str(corpus)]) == 2


def test_rosetta_audit_fail_without_baseline_exits_1_and_allow_flag_exits_0(tmp_path, monkeypatch):
    corpus = _fake_corpus(tmp_path, "import sys; print(f'FAIL {sys.argv[1]}: 1 mismatch(es)'); sys.exit(1)\n")
    monkeypatch.setenv("GALAXYSCOPE_BIN", sys.executable)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert rosetta_audit.main(["--corpus", str(corpus)]) == 1
    assert rosetta_audit.main(["--corpus", str(corpus), "--allow-regressions"]) == 0


def test_rosetta_audit_pre_existing_drift_exits_0(tmp_path, monkeypatch):
    # The fake verifier fails under the "current" binary and ALSO under the baseline binary:
    # the corpus is behind engine main, which is not this build's doing.
    script = "import os, sys; print(f'FAIL {sys.argv[1]}: 1 mismatch(es)'); sys.exit(1)\n"
    corpus = _fake_corpus(tmp_path, script)
    monkeypatch.setenv("GALAXYSCOPE_BIN", sys.executable)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert rosetta_audit.main(["--corpus", str(corpus), "--baseline-bin", sys.executable]) == 0


def test_rosetta_audit_regression_against_baseline_exits_1(tmp_path, monkeypatch):
    # Passes when GALAXYSCOPE_BIN is the baseline marker, fails otherwise.
    baseline_marker = tmp_path / "baseline-galaxyscope"
    baseline_marker.write_text("")
    script = (
        "import os, sys\n"
        "lang = sys.argv[1]\n"
        f"if os.environ['GALAXYSCOPE_BIN'] == {str(baseline_marker)!r}:\n"
        "    print(f'PASS {lang}: 1 assertions across 1 files'); sys.exit(0)\n"
        "print(f'FAIL {lang}: 1 mismatch(es)'); sys.exit(1)\n"
    )
    corpus = _fake_corpus(tmp_path, script)
    monkeypatch.setenv("GALAXYSCOPE_BIN", sys.executable)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert rosetta_audit.main(["--corpus", str(corpus), "--baseline-bin", str(baseline_marker)]) == 1


def test_rosetta_audit_writes_step_summary(tmp_path, monkeypatch):
    corpus = _fake_corpus(tmp_path, "import sys; print(f'PASS {sys.argv[1]}: 1 assertions across 1 files')\n")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GALAXYSCOPE_BIN", sys.executable)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert rosetta_audit.main(["--corpus", str(corpus)]) == 0
    assert "1 languages checked" in summary.read_text()


# --- the two baseline-gated accuracy runners ------------------------------------------------


def test_tri_comparison_all_ci_refuses_zero_languages():
    import tri_comparison_chart

    assert tri_comparison_chart.run_all_baseline_mode([], lambda lang, verbose: 0) == 1


def test_tri_comparison_ci_fails_closed_when_a_baselined_language_has_no_data(monkeypatch):
    import tri_comparison_chart

    class NoData:
        has_data = False
        awaiting_note = "gather failed: galaxyscope not found on PATH"

    monkeypatch.setattr(tri_comparison_chart, "run_pipeline", lambda langs, verbose=True: {langs[0]: NoData()})
    assert tri_comparison_chart.run_ci_check("python", verbose=False) == 1


@pytest.mark.skipif(
    subprocess.run(
        [sys.executable, "-c", "import tree_sitter_language_pack"], capture_output=True, env=os.environ
    ).returncode
    != 0,
    reason="tree_sitter_language_pack not installed in this interpreter",
)
def test_tree_sitter_all_refuses_zero_languages(monkeypatch):
    import tree_sitter_accuracy_audit

    monkeypatch.setattr(tree_sitter_accuracy_audit, "_all_baseline_langs", lambda: [])
    assert tree_sitter_accuracy_audit.run_all(lambda lang: 0) == 1
