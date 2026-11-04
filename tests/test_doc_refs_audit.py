"""doc_refs_audit.py: each check fires on a stale reference and stays quiet on a live one, and --ci gates on the
baseline (new findings fail, fixed ones only print). The repo-wide run is the small-audits.yml step, on every PR."""

import json
from collections import Counter

import doc_refs_audit as dra
import pytest

FILES = [
    "tests/tools/real_tool.py",
    "tests/tools/arg_helper.py",
    "docs/guide.md",
    "docs/wiki/page.md",
    "gitgalaxy/core/README.md",
    "gitgalaxy/core/detector.py",
    "gitgalaxy/core/prism.py",
    "gitgalaxy/core/_private.py",
    "gitgalaxy/core/__init__.py",
    "gitgalaxy/shiny/cli.py",
    ".claude/skills/real-skill/SKILL.md",
]
SOURCES = {
    "tests/tools/real_tool.py": 'ap.add_argument("--write")\nap.add_argument("--update-baseline")\n',
    "tests/tools/arg_helper.py": 'def add(ap):\n    ap.add_argument("--shared")\n',
    "gitgalaxy/shiny/cli.py": 'ap.add_argument("--mode")\n',
    "docs/ecosystem.md": "| other-repo | `sibling-skill` |\n",
}


@pytest.fixture
def repo(tmp_path):
    r = dra.Repo(root=tmp_path, files=FILES)
    r._text.update(SOURCES)
    r._ignored = {}
    r.ignored = lambda path: path.startswith("out/")  # no git in tmp_path
    return r


def _run(repo, text, doc="docs/guide.md"):
    repo._text[doc] = text
    return [(f.check, f.target) for f in dra.audit_doc(repo, doc, dra._skills(repo))]


def test_live_references_are_clean(repo):
    text = (
        "See `tests/tools/real_tool.py --write` and `gitgalaxy/core/` and [page](wiki/page.md).\n"
        "Run `python -m gitgalaxy.shiny.cli --mode x` with the `real-skill` skill or the `sibling-skill` skill.\n"
        "```bash\npython tests/tools/real_tool.py --shared --update-baseline\n```\n"
        "Bare `detector.py`, and [site](https://example.com), and `<lang>.py`, and `tests/tools/*.py`.\n"
    )
    assert _run(repo, text) == []


def test_moved_path_is_found_and_needs_its_folder_here(repo):
    found = _run(repo, "`tests/tools/old_tool.py` and `tests/http/test_ws.py`\n")
    assert found == [("path", "tests/tools/old_tool.py")]  # tests/http/ is another project's tree


def test_dead_relative_link_and_dead_github_url(repo):
    text = "[a](wiki/gone.md) and https://github.com/squid-protocol/gitgalaxy/blob/main/docs/gone.md\n"
    assert _run(repo, text) == [("link", "docs/wiki/gone.md"), ("link", "docs/gone.md")]


def test_a_link_inside_a_code_span_is_an_example(repo):
    assert _run(repo, "the syntax `[text](missing.md)` is a link\n") == []


def test_frontmatter_is_skipped(repo):
    assert _run(repo, "---\ndescription: [cut](gitgalaxy/t...\n---\nbody\n") == []


def test_removed_flag_is_found_but_a_longer_flag_does_not_cover_a_prefix(repo):
    found = _run(repo, "`python tests/tools/real_tool.py --gone` then `tests/tools/real_tool.py --update`\n")
    assert found == [("flag", "tests/tools/real_tool.py --gone"), ("flag", "tests/tools/real_tool.py --update")]


def test_a_flag_after_a_pipe_belongs_to_the_next_command(repo):
    assert _run(repo, "```\npython tests/tools/real_tool.py --write | grep --count x\n```\n") == []


def test_bare_python_name_with_no_file_and_skills(repo):
    found = _run(repo, "edit `language_standards.py`; use the `ghost-skill` skill\n")
    assert sorted(found) == [("name", "language_standards.py"), ("skill", "ghost-skill")]


def test_sibling_repo_lines_and_write_ups_about_other_projects_skip_names(repo):
    assert _run(repo, "keyword-rosetta's `tools/bias_report.py` and `screen_plant.py`\n") == []
    assert _run(repo, "NVDA's `braille.py`\n", doc="docs/wiki/museum-of-code/teardown.md") == []
    wrapped = "Per keyword-rosetta's gating rules,\nadd a row to its `docs/GATING.md`.\n\nOurs: `docs/GATING.md`\n"
    assert _run(repo, wrapped) == [("path", "docs/GATING.md")]  # the paragraph names the repo; the next one does not


def test_ignored_and_generated_branch_paths_exist(repo):
    assert _run(repo, "`docs/language_status/oracle_assumptions.md` `docs/gitgalaxy_architecture_brief.md`\n") == []


def test_package_readme_must_name_each_public_module(repo):
    repo._text["gitgalaxy/core/README.md"] = "The `detector.py` stage.\n"
    found = dra.audit_modules(repo, "gitgalaxy/core/README.md")
    assert [f.target for f in found] == ["gitgalaxy/core/prism.py"]  # _private and __init__ are not public


def test_generated_and_foreign_docs_are_out_of_scope(repo):
    repo.files |= {"docs/language_status/progress.md", "docs/wiki/agents/x_agents.md", "tests/fixtures/a/README.md"}
    scope = dra.docs_in_scope(repo)
    assert "docs/guide.md" in scope
    assert not {"docs/language_status/progress.md", "docs/wiki/agents/x_agents.md", "tests/fixtures/a/README.md"} & set(
        scope
    )


def test_ci_fails_only_beyond_the_baseline_and_reports_fixed_keys():
    a = dra.Finding("path", "d.md", 3, "x/y.py")
    b = dra.Finding("path", "d.md", 9, "x/y.py")
    c = dra.Finding("link", "e.md", 1, "z.md")
    new, fixed = dra.new_findings([a, b], Counter({a.key: 1, c.key: 1}))
    assert new == [b]  # a second copy of a baselined key is new
    assert fixed == [c.key]


def test_baseline_round_trip_has_no_line_numbers(tmp_path):
    path = tmp_path / "b.json"
    f = dra.Finding("path", "d.md", 3, "x/y.py")
    dra.write_baseline([f, f], path)
    assert json.loads(path.read_text()) == {"path | d.md | x/y.py": 2}
    assert dra.load_baseline(path) == Counter({"path | d.md | x/y.py": 2})
