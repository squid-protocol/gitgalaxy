"""#6501: the accuracy-audit plan -- a language-file diff runs the call-graph / detection audit only when it can move it.

Both directions: an input the audit reads is never skipped (shared engine files, the tool, the baseline, any
unplaceable hunk, a new file, a failed git call), and a comment, a `_meta` edit or a key nothing reads skips it.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))
import accuracy_audit_plan as aap  # noqa: E402

CALL, DET, TREE, HIST = aap.CALL, aap.DETECTION, aap.TREE, aap.HISTORY
LANGS = aap.tree_sitter_languages()
LANG = aap.LANG_DIR
BASELINE = aap.baseline_languages()
WORKFLOWS = ROOT / ".github" / "workflows"

SAMPLE = """# header
from typing import Any

DEFINITION: dict[str, Any] = {
    "_meta": {
        "status": "production",
    },
    # a comment
    "extensions": [".x", ".y"],
    "case_insensitive_imports": True,
    "rules": {
        "calls_out": re.compile(
            r"\\b(a)"
            + r"b"
        ),
        "_args_arrow": {1, 2},
    },
}
OTHER = {
    "extensions": [".z"],
}
"""


def place(lineno):
    return aap.locate(SAMPLE.splitlines(), lineno)


@pytest.mark.parametrize(
    ("lineno", "expected"),
    [
        (6, ("_meta", None)),
        (9, ("extensions", None)),
        (10, ("case_insensitive_imports", None)),
        (12, ("rules", "calls_out")),
        (14, ("rules", "calls_out")),  # a continuation line of a multi-line rule
        (16, ("rules", "_args_arrow")),
        (4, None),  # the DEFINITION line itself
        (19, None),  # after DEFINITION closed: another module-level object
        (1, None),
    ],
)
def test_locate_places_a_line(lineno, expected):
    assert place(lineno) == expected


def _git_diff(tmp_path, old, new):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_text(old, encoding="utf-8")
    b.write_text(new, encoding="utf-8")
    proc = subprocess.run(
        ["git", "diff", "--no-index", "-U0", str(a), str(b)], capture_output=True, text=True, check=False
    )  # noqa: S603, S607
    return proc.stdout


@pytest.mark.parametrize(
    ("old", "new", "detection", "call_graph"),
    [
        ("# header\n", "# header, reworded\n", False, False),  # a comment
        ('        "status": "production",\n', '        "status": "beta",\n', False, False),  # _meta
        ('    "extensions": [".x", ".y"],\n', '    "extensions": [".x", ".y", ".q"],\n', True, True),
        ('    "case_insensitive_imports": True,\n', '    "case_insensitive_imports": False,\n', False, True),
        ('            + r"b"\n', '            + r"c"\n', True, True),  # a rule body
        ('        "_args_arrow": {1, 2},\n', '        "_args_arrow": {1, 2, 3},\n', False, True),
        ("OTHER = {\n", "OTHER = {  # x\n", True, True),  # outside DEFINITION: unplaceable
    ],
)
def test_a_diff_is_placed_and_judged(tmp_path, old, new, detection, call_graph):
    old_text = SAMPLE
    new_text = SAMPLE.replace(old, new)
    assert new_text != old_text
    found = aap.touched(old_text, new_text, _git_diff(tmp_path, old_text, new_text))
    assert found or (detection, call_graph) == (False, False)
    assert any(aap.moves_detection(p) for p in found) is detection
    assert any(aap.moves_call_graph(p) for p in found) is call_graph


def test_a_pure_addition_and_a_pure_removal_are_both_read(tmp_path):
    added = SAMPLE.replace(
        '    "extensions": [".x", ".y"],\n', '    "extensions": [".x", ".y"],\n    "shebangs": ["x"],\n'
    )
    found = aap.touched(SAMPLE, added, _git_diff(tmp_path, SAMPLE, added))
    assert found == [("shebangs", None)]
    removed = aap.touched(added, SAMPLE, _git_diff(tmp_path, added, SAMPLE))
    assert removed == [("shebangs", None)] and any(aap.moves_detection(p) for p in removed)


def test_blank_and_comment_lines_are_inert(tmp_path):
    new = SAMPLE.replace("    # a comment\n", "    # a comment\n\n    # another\n")
    assert aap.touched(SAMPLE, new, _git_diff(tmp_path, SAMPLE, new)) == []


def _definition_nodes(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = [node.target] if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [])
        if any(getattr(t, "id", "") == "DEFINITION" for t in targets) and isinstance(node.value, ast.Dict):
            return node.value
    return None


def test_locate_agrees_with_the_ast_on_every_language_file():
    """Whole class: for every real language file, every code line of every DEFINITION key (and every `rules` entry) is
    placed on that key by the indentation reader, or left unplaceable (which runs the audit) -- never on another key."""
    checked = placed = 0
    for path in sorted((ROOT / LANG).glob("*.py")):
        node = _definition_nodes(path)
        if node is None:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for k, v in zip(node.keys, node.values, strict=True):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            spans = [(k.value, None, k.lineno, v.end_lineno)]
            if k.value == "rules" and isinstance(v, ast.Dict):
                spans = [
                    ("rules", rk.value, rk.lineno, rv.end_lineno)
                    for rk, rv in zip(v.keys, v.values, strict=True)
                    if isinstance(rk, ast.Constant) and isinstance(rk.value, str)
                ]
            for top, rule, first, last in spans:
                for n in range(first, last + 1):
                    text = lines[n - 1].strip()
                    if not text or text.startswith("#"):
                        continue
                    checked += 1
                    got = aap.locate(lines, n)
                    if got is not None:
                        placed += 1
                        assert got == (top, rule), f"{path.name}:{n}"
    assert checked > 5000
    assert placed / checked > 0.9  # the reader places nearly every line; the rest run the audit


def test_detection_keys_cover_every_key_the_lens_reads():
    """The set is pinned: a top-level DEFINITION key quoted by the lens, the registry or the overrides must be in it."""
    keys = set()
    for path in (ROOT / LANG).glob("*.py"):
        keys |= set(re.findall(r'^    "([^"\n]+)"\s*:', path.read_text(encoding="utf-8"), re.M))
    readers = [
        ROOT / "gitgalaxy/standards/language_lens.py",
        ROOT / "gitgalaxy/standards/gitgalaxy_config.py",
        *(ROOT / "gitgalaxy/standards/language_standards").glob("*.py"),
    ]
    quoted = set()
    for path in readers:
        quoted |= set(re.findall(r'["\']([^"\'\n]+)["\']', path.read_text(encoding="utf-8")))
    read = keys & quoted - {"rules", "_meta"}
    assert read <= aap.DETECTION_KEYS, sorted(read - aap.DETECTION_KEYS)


def plan_with(files, audit, found, event=None):
    event = event or aap.EVENTS[audit]

    def places(_path):
        if isinstance(found, Exception):
            raise found
        return found

    return aap.plan(files, event, audit, places, BASELINE, LANGS)


@pytest.mark.parametrize("audit", [CALL, DET])
def test_every_shared_input_runs_the_audit(audit):
    for path in aap.EVERYTHING[audit]:
        assert plan_with([path], audit, [])["run"], path


@pytest.mark.parametrize("audit", [CALL, DET])
@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/standards/language_standards/identifiers.py",
        "gitgalaxy/standards/language_standards/_shared_patterns.py",
        "gitgalaxy/standards/language_standards/_overrides.py",
        "gitgalaxy/standards/language_standards/languages/__init__.py",
        "gitgalaxy/standards/language_standards/new_registry.json",
    ],
)
def test_a_shared_language_standards_file_runs_the_audit(audit, path):
    assert plan_with([path], audit, [])["run"]


@pytest.mark.parametrize("audit", [CALL, DET, TREE, HIST])
@pytest.mark.parametrize("event", ["push", "pull_request", "schedule", "workflow_dispatch"])
def test_other_events_and_an_empty_diff_run_it(audit, event):
    if event != aap.EVENTS[audit]:
        assert plan_with(["README.md"], audit, [], event=event)["run"]
    assert plan_with([], audit, [])["run"]


@pytest.mark.parametrize("audit", [CALL, DET])
@pytest.mark.parametrize(
    "path",
    ["docs/graph_accuracy.md", "README.md", ".claude/rules/x.md", "tests/tools/test_foo.py", "gitgalaxy/tools/x.py"],
)
def test_a_file_the_audit_does_not_read_skips_it(audit, path):
    p = plan_with([path], audit, [])
    assert p["run"] is False and p["inputs"] == []


@pytest.mark.parametrize("audit", [CALL, DET])
def test_an_unplaceable_new_or_unreadable_language_file_runs_the_audit(audit):
    for lang in ("haskell", "cobol"):
        assert plan_with([f"{LANG}{lang}.py"], audit, [None])["run"]
        assert plan_with([f"{LANG}{lang}.py"], audit, RuntimeError("no such path in base"))["run"]


@pytest.mark.parametrize("lang", ["haskell", "dart", "swift", "powershell", "python", "cpp"])
def test_a_baseline_language_runs_call_graph_on_any_code_but_not_on_meta(lang):
    assert lang in BASELINE
    f = [f"{LANG}{lang}.py"]
    assert plan_with(f, CALL, [("rules", "_args_arrow")])["run"]
    assert plan_with(f, CALL, [("case_insensitive_imports", None)])["run"]
    assert plan_with(f, CALL, [("rules", "calls_out")])["run"]
    assert plan_with(f, CALL, [("_meta", None)])["run"] is False
    assert plan_with(f, CALL, [])["run"] is False  # comments and blank lines only


@pytest.mark.parametrize("lang", ["cobol", "pli", "jcl", "abap", "markdown"])
def test_a_language_outside_the_baseline_runs_call_graph_only_when_detection_moves(lang):
    assert aap._norm(lang) not in BASELINE
    f = [f"{LANG}{lang}.py"]
    assert plan_with(f, CALL, [("rules", "calls_out")])["run"]  # a rule can change which language a file is read as
    assert plan_with(f, CALL, [("extensions", None)])["run"]
    assert plan_with(f, CALL, [("rules", "_args_arrow")])["run"] is False
    assert plan_with(f, CALL, [("case_insensitive_imports", None)])["run"] is False
    assert plan_with(f, CALL, [("_meta", None)])["run"] is False


@pytest.mark.parametrize("lang", ["haskell", "cobol", "powershell"])
def test_detection_runs_on_a_rule_or_a_read_key_and_skips_the_rest(lang):
    f = [f"{LANG}{lang}.py"]
    for key in sorted(aap.DETECTION_KEYS):
        assert plan_with(f, DET, [(key, None)])["run"], key
    assert plan_with(f, DET, [("rules", "func_start")])["run"]
    assert plan_with(f, DET, [("rules", None)])["run"]
    assert plan_with(f, DET, [("rules", "_args_arrow")])["run"] is False
    assert plan_with(f, DET, [("calls_out_arities", None)])["run"] is False
    assert plan_with(f, DET, [("_meta", None)])["run"] is False


def test_a_mixed_change_is_the_union():
    files = [f"{LANG}cobol.py", "README.md", aap.T + "detection_accuracy_audit.py"]
    assert plan_with(files, CALL, [("_meta", None)])["run"] is False
    assert plan_with(files, DET, [("_meta", None)])["run"] is True  # the tool itself


def test_the_real_git_path_end_to_end(tmp_path, monkeypatch):
    """git_places on a real two-commit repo: a comment skips both audits, a rule edit runs detection."""
    lang_dir = tmp_path / LANG
    lang_dir.mkdir(parents=True)
    target = lang_dir / "cobol.py"
    target.write_text(SAMPLE, encoding="utf-8")

    def git(*a):
        subprocess.run(
            ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *a],
            check=True,
            capture_output=True,
        )  # noqa: S603, S607

    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "base")
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()  # noqa: S603, S607
    monkeypatch.setattr(aap, "REPO_ROOT", tmp_path)
    path = f"{LANG}cobol.py"

    target.write_text(SAMPLE.replace("# header", "# header again"), encoding="utf-8")
    git("commit", "-qam", "comment")
    head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()  # noqa: S603, S607
    assert aap.git_places(path, base, head) == []

    target.write_text(SAMPLE.replace('+ r"b"', '+ r"c"'), encoding="utf-8")
    git("commit", "-qam", "rule")
    head2 = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()  # noqa: S603, S607
    assert aap.git_places(path, base, head2) == [("rules", "calls_out"), ("rules", "calls_out")]
    assert aap.language_moves(DET, path, BASELINE, lambda p: aap.git_places(p, base, head2))

    with pytest.raises(RuntimeError):  # a file absent from the base: the planner treats it as "run"
        aap.git_places(f"{LANG}new.py", base, head2)
    assert aap.language_moves(DET, f"{LANG}new.py", BASELINE, lambda p: aap.git_places(p, base, head2))


def test_replay_counts_before_and_after(monkeypatch):
    monkeypatch.setattr(aap, "git_places", lambda path, base, head: [("_meta", None)])
    prs = [
        {"number": 1, "files": [{"path": "README.md"}], "mergeCommit": {"oid": "a"}},  # never started
        {"number": 2, "files": [{"path": f"{LANG}cobol.py"}], "mergeCommit": {"oid": "b"}},  # started, now skipped
        {"number": 3, "files": [{"path": aap.T + "call_graph_accuracy.py"}], "mergeCommit": {"oid": "c"}},  # still runs
        {"number": 4, "files": [{"path": f"f{i}.md"} for i in range(100)], "mergeCommit": {"oid": "d"}},  # cut list
    ]
    r = aap.replay(prs, CALL, BASELINE)
    assert (r["prs"], r["ran_before"], r["runs_now"]) == (
        4,
        3,
        2,
    )  # PR 4: gh cut the file list, so it counts as running
    assert r["prs_that_still_run"] == [3, 4]


@pytest.mark.parametrize("audit", [CALL, DET])
def test_the_workflow_keeps_its_check_name_and_gates_every_step_on_the_plan(audit):
    name = aap.WORKFLOWS[audit]
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    job = name.removesuffix(".yml")
    assert re.search(rf"^  {job}:\n    needs: \[plan\]\n    if: \$\{{\{{ always\(\) && ", text, re.M)
    assert "\n  plan:\n" in text
    body = text.split(f"\n  {job}:\n", 1)[1]
    steps = re.split(r"^      - name: ", body, flags=re.M)[1:]
    assert steps
    for step in steps:
        assert "needs.plan.outputs.run != 'false'" in step, step.splitlines()[0]
    for p in (
        "tests/tools/accuracy_audit_plan.py",
        "tests/tools/graph_accuracy_plan.py",
        "tests/tools/change_classifier.py",
    ):
        assert f'"{p}"' in text
    assert f"--audit {audit}" in text


@pytest.mark.parametrize("audit", [CALL, DET])
def test_every_path_the_workflow_filters_on_is_planned(audit):
    """A path in the workflow's `paths:` that the planner would skip is a trigger that never runs the audit: only the
    language_standards glob (judged per file) and files nothing reads may be among them."""
    for path in aap.workflow_paths(audit):
        if "*" in path:
            assert path.startswith(aap.LANG_STANDARDS), path
        else:
            assert path in aap.EVERYTHING[audit], path


# ---- tree-sitter (and its push-to-main history) -----------------------------------------------------------------------

TS = [TREE, HIST]


def test_every_baseline_file_names_a_language_and_the_set_is_not_empty():
    assert len(LANGS) > 20
    assert LANGS["objectivec"] == "objective-c"
    for norm, name in LANGS.items():
        assert aap._norm(name) == norm
        assert (ROOT / f"{aap.TREE_BASELINE}{name}.json").exists()


@pytest.mark.parametrize("audit", TS)
def test_every_shared_tree_sitter_input_runs_all_languages(audit):
    for path in aap.EVERYTHING[audit]:
        p = plan_with([path], audit, [])
        assert p["run"] and p["langs"] == aap.ALL_LANGS, path


@pytest.mark.parametrize("audit", TS)
@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/standards/language_standards/identifiers.py",
        "gitgalaxy/standards/language_standards/__init__.py",
        "gitgalaxy/standards/language_standards/_shared_patterns.py",
        f"{LANG}__init__.py",
    ],
)
def test_a_shared_language_standards_file_runs_all_languages(audit, path):
    p = plan_with([path], audit, [])
    assert p["run"] and p["langs"] == aap.ALL_LANGS


@pytest.mark.parametrize("audit", TS)
@pytest.mark.parametrize("lang", ["python", "go", "objective-c", "typescript", "c", "zig"])
def test_a_baseline_file_selects_its_language_only(audit, lang):
    p = plan_with([f"{aap.TREE_BASELINE}{lang}.json"], audit, [])
    assert p["run"] and p["langs"] == lang


@pytest.mark.parametrize("audit", TS)
@pytest.mark.parametrize("stem", ["python", "go", "objective_c", "typescript", "cpp", "powershell"])
def test_a_language_rule_selects_that_language_and_an_underscore_rule_too(audit, stem):
    f = [f"{LANG}{stem}.py"]
    name = LANGS[aap._norm(stem)]
    for found in (
        [("rules", "func_start")],
        [("rules", "_dependency_capture")],  # the audit reads it: unlike detection, an underscore rule counts
        [("rules", "_args_arrow")],
        [("case_insensitive_imports", None)],
        [("rules", "func_start"), ("_meta", None)],
    ):
        p = plan_with(f, audit, found)
        assert p["run"] and p["langs"] == name, found


@pytest.mark.parametrize("audit", TS)
@pytest.mark.parametrize("stem", ["python", "cobol"])
def test_comments_and_meta_skip_every_language(audit, stem):
    for found in ([], [("_meta", None)]):
        p = plan_with([f"{LANG}{stem}.py"], audit, found)
        assert p["run"] is False and p["langs"] == "" and p["inputs"] == []


@pytest.mark.parametrize("audit", TS)
def test_a_language_without_a_baseline_selects_nothing_unless_the_lens_reads_the_change(audit):
    stem = "cobol"
    assert aap._norm(stem) not in LANGS
    f = [f"{LANG}{stem}.py"]
    assert plan_with(f, audit, [("rules", "func_start")])["run"] is False
    for key in sorted(aap.DETECTION_KEYS):
        p = plan_with(f, audit, [(key, None)])
        assert p["run"] and p["langs"] == aap.ALL_LANGS, key


@pytest.mark.parametrize("audit", TS)
@pytest.mark.parametrize("stem", ["python", "haskell"])
def test_a_key_the_lens_reads_can_reclassify_any_language_so_it_selects_all(audit, stem):
    f = [f"{LANG}{stem}.py"]
    for key in sorted(aap.DETECTION_KEYS):
        p = plan_with(f, audit, [("rules", "func_start"), (key, None)])
        assert p["run"] and p["langs"] == aap.ALL_LANGS, key


@pytest.mark.parametrize("audit", TS)
def test_an_unplaceable_new_helper_or_unreadable_language_file_selects_all(audit):
    for stem in ("python", "cobol"):
        for found in ([None], RuntimeError("no such path in base")):
            p = plan_with([f"{LANG}{stem}.py"], audit, found)
            assert p["run"] and p["langs"] == aap.ALL_LANGS
    assert plan_with([f"{LANG}_helper.py"], audit, [])["langs"] == aap.ALL_LANGS


@pytest.mark.parametrize("audit", TS)
def test_a_mixed_change_selects_the_union_and_all_beats_a_list(audit):
    files = [f"{LANG}python.py", f"{LANG}go.py", f"{aap.TREE_BASELINE}rust.json", "README.md"]
    assert plan_with(files, audit, [("rules", "func_start")])["langs"] == "go,python,rust"
    p = plan_with([*files, aap.T + "tree_sitter_accuracy_audit.py"], audit, [("rules", "func_start")])
    assert p["langs"] == aap.ALL_LANGS


@pytest.mark.parametrize("audit", TS)
@pytest.mark.parametrize(
    "path",
    [
        "docs/graph_accuracy.md",
        "README.md",
        "tests/tools/test_foo.py",
        "gitgalaxy/recorders/x.py",
        "gitgalaxy/tools/x.py",
    ],
)
def test_a_file_the_tree_sitter_audit_does_not_read_skips_it(audit, path):
    p = plan_with([path], audit, [])
    assert p["run"] is False and p["langs"] == ""


def test_the_history_plans_a_push_and_the_audit_a_pull_request():
    assert aap.EVENTS[TREE] == "pull_request" and aap.EVENTS[HIST] == "push"
    assert plan_with(["README.md"], HIST, [])["run"] is False
    assert plan_with(["README.md"], HIST, [], event="pull_request")["run"]  # not its event: always
    assert plan_with(["README.md"], HIST, [], event="workflow_dispatch")["langs"] == aap.ALL_LANGS


def test_a_push_diff_is_read_from_the_base_commit_and_an_unknown_base_runs(tmp_path, monkeypatch):
    def git(*a):
        return subprocess.run(
            ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *a],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()  # noqa: S603, S607

    lang_dir = tmp_path / LANG
    lang_dir.mkdir(parents=True)
    target = lang_dir / "python.py"
    target.write_text(SAMPLE, encoding="utf-8")
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    monkeypatch.setattr(aap, "REPO_ROOT", tmp_path)

    target.write_text(SAMPLE.replace("# header", "# header again"), encoding="utf-8")
    git("commit", "-qam", "comment")
    assert aap.changed_files(base, "push") == [f"{LANG}python.py"]
    places = aap.pr_places(base, "push")
    assert aap.plan([f"{LANG}python.py"], "push", HIST, places, BASELINE, LANGS)["run"] is False

    target.write_text(SAMPLE.replace('+ r"b"', '+ r"c"'), encoding="utf-8")
    git("commit", "-qam", "rule")
    p = aap.plan(aap.changed_files(base, "push"), "push", HIST, aap.pr_places(base, "push"), BASELINE, LANGS)
    assert p["run"] and p["langs"] == "python"  # the comment and the rule edit since `base` are one diff

    with pytest.raises(RuntimeError):  # a commit that is gone (a force push): main() catches it and runs everything
        aap.changed_files("0" * 40, "push")


def test_main_runs_everything_when_the_diff_cannot_be_read(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys, "argv", ["x", "--audit", HIST, "--event", "push", "--base", "0" * 40, "--github-output", str(out)]
    )
    assert aap.main() == 0
    assert out.read_text(encoding="utf-8") == f"run=true\nlangs={aap.ALL_LANGS}\n"
    assert "cannot plan" in capsys.readouterr().out


@pytest.mark.parametrize("audit", TS)
def test_the_tree_sitter_workflow_gates_every_step_on_the_plan(audit):
    name = aap.WORKFLOWS[audit]
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    job = name.removesuffix(".yml")
    assert re.search(rf"^  {job}:\n    needs: \[plan\]\n    if: \$\{{\{{ always\(\)", text, re.M)
    assert "\n  plan:\n" in text
    body = text.split(f"\n  {job}:\n", 1)[1]
    steps = re.split(r"^      - name: ", body, flags=re.M)[1:]
    assert steps
    for step in steps:
        assert "needs.plan.outputs.run != 'false'" in step, step.splitlines()[0]
    assert f"--audit {audit}" in text
    plan_job = text.split("\n  plan:\n", 1)[1].split(f"\n  {job}:\n", 1)[0]
    assert "persist-credentials: false" in plan_job and "contents: write" not in plan_job


def test_the_audit_runs_the_selected_languages_from_the_environment_and_the_history_plans_from_the_last_success():
    audit = (WORKFLOWS / aap.WORKFLOWS[TREE]).read_text(encoding="utf-8")
    assert "LANGS: ${{ needs.plan.outputs.langs }}" in audit
    assert 'langs="${{' not in audit  # a changed file name is never spliced into the script
    assert '--lang "$lang" --ci' in audit and "--all --ci" in audit
    for p in ("accuracy_audit_plan.py", "graph_accuracy_plan.py", "change_classifier.py"):
        assert f'"tests/tools/{p}"' in audit
    hist = (WORKFLOWS / aap.WORKFLOWS[HIST]).read_text(encoding="utf-8")
    assert "--status success" in hist and "${{ github.event.before }}" not in hist


@pytest.mark.parametrize("audit", TS)
def test_every_path_the_tree_sitter_workflow_filters_on_is_planned(audit):
    for path in aap.workflow_paths(audit):
        if "*" in path:
            assert path.startswith((aap.LANG_STANDARDS, aap.TREE_BASELINE)), path
        else:
            assert path in aap.EVERYTHING[audit], path


def test_replay_counts_tree_sitter_runs(monkeypatch):
    monkeypatch.setattr(aap, "git_places", lambda path, base, head: [("_meta", None)])
    prs = [
        {"number": 1, "files": [{"path": f"{LANG}cobol.py"}], "mergeCommit": {"oid": "a"}},
        {"number": 2, "files": [{"path": f"{aap.TREE_BASELINE}go.json"}], "mergeCommit": {"oid": "b"}},
    ]
    r = aap.replay(prs, TREE, BASELINE)
    assert (r["prs"], r["ran_before"], r["runs_now"]) == (2, 2, 1)
    assert r["prs_that_still_run"] == [2]
    assert r["language_corpora_before"] == 2 * len(LANGS) and r["language_corpora_now"] == 1  # PR 2: one baseline file


# ---- tri-comparison (+ history) and the graph-comparison history ------------------------------------------------------

TRI_LANGS = aap.tree_sitter_languages(baseline=aap.TRI_BASELINE)
GRAPH_LANGS = aap.scored_languages(aap.GRAPH_HISTORY)
NEW = [aap.TRI, aap.TRI_HISTORY, aap.GRAPH_HISTORY]


def new_plan(files, audit, found, event=None):
    event = event or aap.EVENTS[audit]

    def places(_path):
        if isinstance(found, Exception):
            raise found
        return found

    langs = TRI_LANGS if audit == aap.TRI else None
    return aap.plan(files, event, audit, places, GRAPH_LANGS if audit == aap.GRAPH_HISTORY else BASELINE, langs)


def test_the_tri_baseline_set_is_read_from_its_own_files():
    assert {"javascript", "typescript", "zig"} <= set(TRI_LANGS)
    for norm, name in TRI_LANGS.items():
        assert aap._norm(name) == norm and (ROOT / f"{aap.TRI_BASELINE}{name}.json").exists()
    assert GRAPH_LANGS >= BASELINE and "python" in GRAPH_LANGS  # call baseline + import corpus


@pytest.mark.parametrize("audit", NEW)
def test_every_shared_input_of_the_new_audits_runs_them(audit):
    for path in aap.EVERYTHING[audit]:
        path = path.replace("*", "x")  # a glob entry: any file it names
        p = new_plan([path], audit, [])
        assert p["run"], path
        if audit == aap.TRI:
            assert p["langs"] == aap.ALL_LANGS


@pytest.mark.parametrize("audit", NEW)
@pytest.mark.parametrize("event", ["push", "pull_request", "schedule", "workflow_dispatch"])
def test_new_audits_run_on_other_events_an_empty_diff_and_shared_standards(audit, event):
    if event != aap.EVENTS[audit]:
        assert new_plan(["README.md"], audit, [], event=event)["run"]
    assert new_plan([], audit, [])["run"]
    assert new_plan(["gitgalaxy/standards/language_standards/identifiers.py"], audit, [])["run"]
    assert new_plan([f"{LANG}__init__.py"], audit, [])["run"]


@pytest.mark.parametrize("audit", NEW)
@pytest.mark.parametrize(
    "path", ["docs/graph_accuracy.md", "README.md", "tests/tools/test_foo.py", "gitgalaxy/recorders/x.py"]
)
def test_a_file_the_new_audits_do_not_read_skips_them(audit, path):
    p = new_plan([path], audit, [])
    assert p["run"] is False and p["inputs"] == []


@pytest.mark.parametrize("audit", NEW)
def test_an_unplaceable_new_or_unreadable_language_file_runs_the_new_audits(audit):
    for stem in ("zig", "cobol"):
        for found in ([None], RuntimeError("no such path in base")):
            assert new_plan([f"{LANG}{stem}.py"], audit, found)["run"]


def test_a_haskell_only_change_runs_no_tri_gate_and_a_zig_change_runs_only_zig():
    assert aap._norm("haskell") not in TRI_LANGS
    f = [f"{LANG}haskell.py"]
    p = new_plan(f, aap.TRI, [("rules", "func_start")])
    assert p["run"] is False and p["langs"] == ""
    p = new_plan([f"{LANG}zig.py"], aap.TRI, [("rules", "_dependency_capture")])
    assert p["run"] and p["langs"] == TRI_LANGS["zig"]
    assert new_plan([f"{LANG}zig.py"], aap.TRI, [("_meta", None)])["run"] is False
    assert new_plan([f"{LANG}zig.py"], aap.TRI, [])["run"] is False  # comments only


def test_tri_selection_unions_baseline_files_and_a_lens_key_selects_all():
    files = [f"{LANG}zig.py", f"{aap.TRI_BASELINE}typescript.json", f"{LANG}haskell.py"]
    assert new_plan(files, aap.TRI, [("rules", "func_start")])["langs"] == "typescript,zig"
    for key in sorted(aap.DETECTION_KEYS):
        p = new_plan([f"{LANG}haskell.py"], aap.TRI, [(key, None)])
        assert p["run"] and p["langs"] == aap.ALL_LANGS, key
    assert new_plan([f"{aap.TRI_BASELINE}zig.json"], aap.TRI, [])["langs"] == "zig"


def test_a_tri_baseline_file_runs_the_tri_history_but_not_the_graph_history():
    path = f"{aap.TRI_BASELINE}zig.json"
    assert new_plan([path], aap.TRI_HISTORY, [])["run"]
    assert new_plan([path], aap.GRAPH_HISTORY, [])["run"] is False


@pytest.mark.parametrize("stem", ["zig", "haskell", "cobol"])
def test_the_tri_history_runs_on_any_rule_edit_but_not_on_comments_or_meta(stem):
    f = [f"{LANG}{stem}.py"]
    for found in ([("rules", "func_start")], [("rules", "_args_arrow")], [("case_insensitive_imports", None)]):
        assert new_plan(f, aap.TRI_HISTORY, found)["run"], found
    for found in ([], [("_meta", None)]):
        assert new_plan(f, aap.TRI_HISTORY, found)["run"] is False, found


def test_the_graph_history_judges_call_baseline_and_import_corpus_languages_strictly():
    corpus_only = sorted(aap.corpus_languages() - BASELINE)
    assert corpus_only, "the import corpus pins a language the call baseline lacks"
    neither = "cobol"
    assert aap._norm(neither) not in GRAPH_LANGS
    for stem in (sorted(BASELINE)[0], corpus_only[0]):
        f = [f"{LANG}{stem}.py"]
        assert new_plan(f, aap.GRAPH_HISTORY, [("rules", "_args_arrow")])["run"], stem
        assert new_plan(f, aap.GRAPH_HISTORY, [("case_insensitive_imports", None)])["run"], stem
        assert new_plan(f, aap.GRAPH_HISTORY, [("_meta", None)])["run"] is False, stem
    f = [f"{LANG}{neither}.py"]  # any other language: only what the lens reads can move it
    assert new_plan(f, aap.GRAPH_HISTORY, [("rules", "_args_arrow")])["run"] is False
    assert new_plan(f, aap.GRAPH_HISTORY, [("rules", "func_start")])["run"]
    assert new_plan(f, aap.GRAPH_HISTORY, [("extensions", None)])["run"]


def test_a_graph_resolution_baseline_matches_the_glob_entry():
    assert new_plan(["tests/call_graph_resolution_rust_baseline.json"], aap.GRAPH_HISTORY, [])["run"]
    assert new_plan(["tests/call_graph_resolution_baseline.json"], aap.GRAPH_HISTORY, [])["run"]


@pytest.mark.parametrize("audit", NEW)
def test_the_new_workflow_gates_every_step_on_the_plan_and_keeps_its_check_name(audit):
    name = aap.WORKFLOWS[audit]
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    job = name.removesuffix(".yml")
    assert re.search(rf"^  {job}:\n    needs: \[plan\]\n    if: \$\{{\{{ always\(\)", text, re.M)
    assert "\n  plan:\n" in text
    body = text.split(f"\n  {job}:\n", 1)[1]
    steps = re.split(r"^      - name: ", body, flags=re.M)[1:]
    assert steps
    for step in steps:
        assert "needs.plan.outputs.run != 'false'" in step, step.splitlines()[0]
    assert f"--audit {audit}" in text
    plan_job = text.split("\n  plan:\n", 1)[1].split(f"\n  {job}:\n", 1)[0]
    assert "persist-credentials: false" in plan_job and "contents: write" not in plan_job
    if aap.EVENTS[audit] == "push":
        assert "--status success" in text and "${{ github.event.before }}" not in text
        assert "needs.plan.outputs.run != 'false' && github.ref == 'refs/heads/main'" in text  # the publish step
    else:
        assert "github.event.pull_request.draft == false" in text.split("\n  plan:\n", 1)[1]


def test_the_tri_audit_reads_the_selected_languages_from_the_environment_and_lists_its_planner_inputs():
    text = (WORKFLOWS / aap.WORKFLOWS[aap.TRI]).read_text(encoding="utf-8")
    assert "LANGS: ${{ needs.plan.outputs.langs }}" in text and 'langs="${{' not in text
    assert '--languages "$LANGS" --ci' in text and "--all --ci" in text
    for p in ("accuracy_audit_plan.py", "graph_accuracy_plan.py", "change_classifier.py"):
        assert f'"tests/tools/{p}"' in text


@pytest.mark.parametrize("audit", NEW)
def test_every_path_a_new_workflow_filters_on_is_planned(audit):
    for path in aap.workflow_paths(audit):
        if path.startswith((aap.LANG_STANDARDS, aap.TRI_BASELINE)):  # judged per file / per language
            assert "*" in path
        else:
            assert aap._glob(path, list(aap.EVERYTHING[audit])) or path in aap.EVERYTHING[audit], path


def test_replay_counts_the_new_audits(monkeypatch):
    monkeypatch.setattr(aap, "git_places", lambda path, base, head: [("_meta", None)])
    prs = [
        {"number": 1, "files": [{"path": f"{LANG}cobol.py"}], "mergeCommit": {"oid": "a"}},
        {"number": 2, "files": [{"path": f"{aap.TRI_BASELINE}zig.json"}], "mergeCommit": {"oid": "b"}},
    ]
    r = aap.replay(prs, aap.TRI, BASELINE)
    assert (r["prs"], r["ran_before"], r["runs_now"]) == (2, 2, 1) and r["prs_that_still_run"] == [2]
    assert r["language_corpora_before"] == 2 * len(TRI_LANGS) and r["language_corpora_now"] == 1
    r = aap.replay(prs, aap.TRI_HISTORY, BASELINE)
    assert (r["ran_before"], r["runs_now"]) == (2, 1)
