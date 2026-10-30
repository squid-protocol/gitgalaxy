"""The CodeQL results a PR adds: new means not on main, and only in a file the PR changed."""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import codeql_new_alerts as cna


def _result(rule, path, line=3, digest="h1", **kw):
    return {"ruleId": rule, "partialFingerprints": {cna.HASH: digest},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": path}, "region": {"startLine": line}}}], **kw}


def _sarif(*res, rules=()):
    return {"runs": [{"tool": {"driver": {"rules": []}, "extensions": [{"rules": list(rules)}]}, "results": list(res)}]}


def _write(tmp_path, name, *res, rules=()):
    p = tmp_path / name
    p.write_text(json.dumps(_sarif(*res, rules=rules)), encoding="utf-8")
    return p


def test_a_result_on_main_is_not_new_even_when_its_line_moved():
    main = cna.results(_sarif(_result("py/unused-import", "a.py", line=3)))
    pr = cna.results(_sarif(_result("py/unused-import", "a.py", line=90)))  # same line content, same hash
    assert cna.new_results(pr, main, ["a.py"]) == []


def test_a_new_rule_hash_or_file_is_new_but_only_in_changed_files():
    main = cna.results(_sarif(_result("r1", "a.py")))
    pr = cna.results(_sarif(_result("r2", "a.py"), _result("r1", "a.py", digest="h2"), _result("r1", "b.py")))
    assert [r["path"] for r in cna.new_results(pr, main, None)] == ["a.py", "a.py", "b.py"]
    assert [r["rule"] for r in cna.new_results(pr, main, ["a.py"])] == ["r2", "r1"]  # b.py isn't this PR's
    assert cna.new_results(pr, main, []) == []


def test_a_suppressed_result_does_not_count():
    assert cna.results(_sarif(_result("r1", "a.py", suppressions=[{"kind": "inSource"}]))) == []


def test_the_level_comes_from_the_rule_in_the_extensions_when_the_result_has_none():
    rules = [{"id": "r1", "defaultConfiguration": {"level": "note"}}]
    assert cna.results(_sarif(_result("r1", "a.py"), rules=rules))[0]["level"] == "note"
    assert cna.results(_sarif(_result("r1", "a.py", level="error"), rules=rules))[0]["level"] == "error"


def test_report_only_never_fails_and_enforce_does(tmp_path, capsys):
    pr, base = _write(tmp_path, "pr.sarif", _result("r1", "a.py")), _write(tmp_path, "main.sarif")
    args = ["--sarif", str(pr), "--baseline", str(base), "--files", "a.py"]
    assert cna.main(args) == 0
    assert "1 new result(s) (report only)" in capsys.readouterr().out
    assert cna.main([*args, "--enforce"]) == 1
    assert "(fails this PR)" in capsys.readouterr().out


def test_a_directory_reads_every_sarif_and_the_summary_is_appended(tmp_path, capsys):
    d = tmp_path / "out"
    d.mkdir()
    _write(d, "python.sarif", _result("r1", "a.py"))
    _write(d, "other.sarif", _result("r2", "b.py"))
    summary = tmp_path / "summary.md"
    base = _write(tmp_path, "main.sarif")
    assert cna.main(["--sarif", str(d), "--baseline", str(base), "--summary", str(summary)]) == 0
    capsys.readouterr()
    assert "`r1`: 1" in summary.read_text(encoding="utf-8") and "`r2`: 1" in summary.read_text(encoding="utf-8")


def test_an_empty_pr_analysis_says_it_saw_nothing(tmp_path, capsys):
    pr, base = _write(tmp_path, "pr.sarif"), _write(tmp_path, "main.sarif", _result("r1", "a.py"))
    assert cna.main(["--sarif", str(pr), "--baseline", str(base)]) == 0
    assert "this check saw nothing" in capsys.readouterr().out  # 0 is not "clean" when the scan returned nothing
