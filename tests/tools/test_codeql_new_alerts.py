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


def test_a_new_rule_or_file_is_new_but_only_in_changed_files():
    main = cna.results(_sarif(_result("r1", "a.py")))
    pr = cna.results(_sarif(_result("r2", "a.py", digest="h2"), _result("r1", "b.py", digest="h3")))
    assert [r["path"] for r in cna.new_results(pr, main, None)] == ["a.py", "b.py"]
    assert [r["rule"] for r in cna.new_results(pr, main, ["a.py"])] == ["r2"]  # b.py isn't this PR's
    assert cna.new_results(pr, main, []) == []


def test_a_suppressed_result_does_not_count():
    assert cna.results(_sarif(_result("r1", "a.py", suppressions=[{"kind": "inSource"}]))) == []


def test_the_level_comes_from_the_rule_in_the_extensions_when_the_result_has_none():
    rules = [{"id": "r1", "defaultConfiguration": {"level": "note"}}]
    assert cna.results(_sarif(_result("r1", "a.py"), rules=rules))[0]["level"] == "note"
    assert cna.results(_sarif(_result("r1", "a.py", level="error"), rules=rules))[0]["level"] == "error"


def test_code_moved_to_another_file_is_not_new():
    main = cna.results(_sarif(_result("r1", "old.py", digest="same")))
    pr = cna.results(_sarif(_result("r1", "new.py", digest="same")))
    assert cna.new_results(pr, main, None) == []


def test_a_changed_hash_is_new_only_when_the_file_has_more_of_that_rule():
    main = cna.results(_sarif(_result("r1", "a.py", digest="old")))
    churned = cna.results(_sarif(_result("r1", "a.py", digest="shifted")))
    assert cna.new_results(churned, main, ["a.py"]) == []  # a neighbouring line moved the hash: still one
    more = cna.results(_sarif(_result("r1", "a.py", digest="shifted"), _result("r1", "a.py", digest="h3")))
    assert len(cna.new_results(more, main, ["a.py"])) == 1


def test_only_errors_and_warnings_outside_the_advisory_rules_block():
    new = [{"rule": "r", "level": level} for level in ("error", "warning", "note")]
    new.append({"rule": "py/ineffectual-statement", "level": "warning"})
    new.append({"rule": "py/regex/unmatchable-dollar", "level": "error"})
    assert [r["level"] for r in cna.blocking(new)] == ["error", "warning"]


def test_a_new_note_is_reported_but_never_fails_an_enforced_run(tmp_path, capsys):
    pr, base = _write(tmp_path, "pr.sarif", _result("r1", "a.py", level="note")), _write(tmp_path, "main.sarif")
    assert cna.main(["--sarif", str(pr), "--baseline", str(base), "--enforce"]) == 0
    assert "1 new result(s), 0 blocking (reported, nothing blocks)" in capsys.readouterr().out


def test_report_only_never_fails_and_enforce_does(tmp_path, capsys):
    pr = _write(tmp_path, "pr.sarif", _result("r1", "a.py", level="warning"))
    base = _write(tmp_path, "main.sarif")
    args = ["--sarif", str(pr), "--baseline", str(base), "--files", "a.py"]
    assert cna.main(args) == 0
    assert "1 new result(s), 1 blocking" in capsys.readouterr().out
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


def test_a_blind_scan_fails_an_enforced_run_even_with_nothing_new(tmp_path, capsys):
    pr = _write(tmp_path, "pr.sarif")
    base = _write(tmp_path, "main.sarif", *[_result("r1", "a.py", digest=f"h{i}") for i in range(4)])
    args = ["--sarif", str(pr), "--baseline", str(base)]
    assert cna.main(args) == 0  # report only: it says so, and passes
    assert "This scan looks blind: 0 results against main's 4" in capsys.readouterr().out
    assert cna.main([*args, "--enforce"]) == 1  # the #7153 failure: "no new results" from a scan that saw nothing
    assert "(fails this PR)" in capsys.readouterr().out


def test_a_partly_blind_scan_fails_but_a_normal_one_does_not():
    assert cna.blind(0, 405) and cna.blind(202, 405)
    assert not cna.blind(203, 405) and not cna.blind(425, 405)
    assert not cna.blind(0, 0), "a repo with no results on main has nothing to compare with"
