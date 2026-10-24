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

CALL, DET = aap.CALL, aap.DETECTION
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


def plan_with(files, audit, found, event="pull_request"):
    def places(_path):
        if isinstance(found, Exception):
            raise found
        return found

    return aap.plan(files, event, audit, places, BASELINE)


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


@pytest.mark.parametrize("audit", [CALL, DET])
@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_other_events_and_an_empty_diff_run_it(audit, event):
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
