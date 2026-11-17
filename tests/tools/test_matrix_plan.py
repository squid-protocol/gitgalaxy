"""matrix_plan (#8425): which PRs the shepherd runs through the all-OS matrix before merge."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matrix_plan as mp  # noqa: E402


def f(patch, name="tests/tools/test_x.py", status="added"):
    return {"filename": name, "status": status, "patch": patch}


@pytest.mark.parametrize("word", ["Closes", "fixes", "Resolved", "Part of"])
def test_a_closing_keyword_on_a_red_main_issue_selects(word):
    assert mp.select_for([], f"{word} #8165", {8165})
    assert not mp.select_for([], f"{word} #8165", set())
    assert not mp.select_for([], f"Depends on #8165", {8165})


@pytest.mark.parametrize("tool", mp.TOOLS.split("|"))
def test_every_platform_tool_in_a_subprocess_call_selects(tool):
    assert mp.select_for([f(f'+    subprocess.run(["{tool}", "x"], check=True)')], "")


def test_a_platform_guard_in_the_added_lines_deselects_the_tool_and_link_reasons():
    guard = '+@pytest.mark.skipif(sys.platform != "linux", reason="rsync")\n+    subprocess.run(["rsync"])'
    assert not mp.select_for([f(guard)], "")
    assert mp.select_for([f("+    p.symlink_to(q)")], "")
    assert not mp.select_for([f("+    shutil.which('x')\n+    p.symlink_to(q)")], "")


def test_case_colliding_fixture_names_select():
    patch = '+    (tmp_path / "Prog").mkdir()\n+    (tmp_path / "prog").mkdir()'
    assert mp.select_for([f(patch)], "")
    assert not mp.select_for([f('+    (tmp_path / "prog").mkdir()\n+    (tmp_path / "other").mkdir()')], "")
    assert mp.select_for([f('+    p.write_text("x")\n+    assert a.casefold() == b')], "")


def test_ordinary_docs_engine_and_removed_files_select_nothing():
    assert not mp.select_for([f("+x = 1", name="gitgalaxy/core/prism.py")], "")
    assert not mp.select_for([f('+subprocess.run(["sed"])', name="docs/x.md")], "")
    assert not mp.select_for([f('+subprocess.run(["sed"])', status="removed")], "")
    assert not mp.select_for([f('+subprocess.run(["sed"])', name="tests/data/x.txt")], "")


def test_unreadable_or_truncated_file_lists_select_nothing_but_keep_the_red_main_reason():
    assert mp.select_for(None, "") == []
    assert mp.select_for([f('+subprocess.run(["sed"])')] * 300, "") == []
    assert len(mp.select_for(None, "Fixes #5", {5})) == 1


def test_plan_pr_survives_failed_reads():
    def api(path):
        raise SystemExit("down")

    assert mp.plan_pr(api, 7, "Fixes #5") == []

    def api2(path):
        if "/issues/" in path:
            return {"labels": [{"name": "ci-red-main"}]}
        raise SystemExit("down")

    assert mp.plan_pr(api2, 7, "Fixes #5")
