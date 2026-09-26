"""The call-graph comparison tooling (epic #3772): the reference-adapter contract
and its cache (#3773), triage (#3774), the one-command check (#3775) and the
single-link explainer (#3776).

The end-to-end tests scan a tiny git repo with THIS checkout's engine and score
it against a registered fake reference, so they need neither node nor pyan3."""

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import call_graph_resolution as cgr
import callgraph_check
import callgraph_refs
import callgraph_triage
import explain_call

MAIN_TS = (
    "export function helper(x: number) {\n"  # 1
    "  return x;\n"
    "}\n"
    "export function fmt(n: number) {\n"  # 4
    "  return String(n);\n"
    "}\n"
    "export function run() {\n"  # 7
    "  helper(1);\n"  # 8
    "  const s = `${fmt(2)}`;\n"  # 9: a call inside a template literal
    "  return s;\n"
    "}\n"
)


def _git_repo(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text)
    for cmd in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c"],
    ):
        subprocess.run(["git", "-C", str(root), *cmd], check=True)
    return root


def _fake_ref(contract: dict, adapter: Path, calls: list) -> callgraph_refs.Reference:
    def build(_repo):
        calls.append(1)
        return dict(contract)

    return callgraph_refs.Reference(
        lang="typescript",
        tool="fake",
        version="1.0",
        corpus="import_graph",
        build=build,
        installed=lambda: "1.0",
        adapter_files=(adapter,),
        reports_external=True,
        install_hint="n/a",
    )


CONTRACT = {
    "defs": [["main.ts", "helper", 1], ["main.ts", "fmt", 4], ["main.ts", "run", 7]],
    "edges": [[["main.ts", "run", 7], ["main.ts", "helper", 1], 8], [["main.ts", "run", 7], ["main.ts", "fmt", 4], 9]],
    "external": [],
}


# ----------------------------------------------------------------------------- contract + cache (#3773)


def test_load_contract_reads_optional_call_sites_and_external():
    g = callgraph_refs.load_contract(
        {
            "defs": [["a.ts", "f", 1], ["a.ts", "g", 5]],
            "edges": [[["a.ts", "f", 1], ["a.ts", "g", 5], 3], [["a.ts", "g", 5], ["a.ts", "f", 1]]],
            "external": [[["a.ts", "f", 1], "trim"]],
        }
    )
    assert g.defs[("a.ts", "f")] == [1]
    assert (("a.ts", "f", 1), ("a.ts", "g", 5)) in g.edges
    assert g.by_name[(("a.ts", "f", 1), "g")] == {("a.ts", "g", 5)}
    assert g.sites == {(("a.ts", "f", 1), ("a.ts", "g", 5)): [3]}  # the second edge has no site
    assert g.external == {(("a.ts", "f", 1), "trim")}


def test_reference_graph_is_cached_and_rebuilt_when_the_adapter_changes(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo", {"main.ts": MAIN_TS})
    adapter = tmp_path / "adapter.js"
    adapter.write_text("v1")
    calls: list = []
    monkeypatch.setattr(callgraph_refs, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setitem(callgraph_refs.REFERENCES, "typescript", _fake_ref(CONTRACT, adapter, calls))

    raw, cached = callgraph_refs.reference_contract("typescript", repo)
    assert (cached, len(calls), raw["version"], raw["tool"]) == (False, 1, "1.0", "fake")
    _, cached = callgraph_refs.reference_contract("typescript", repo)
    assert (cached, len(calls)) == (True, 1)  # served from the cache, not rebuilt
    adapter.write_text("v2")  # an adapter edit invalidates its cache
    _, cached = callgraph_refs.reference_contract("typescript", repo)
    assert (cached, len(calls)) == (False, 2)
    _, cached = callgraph_refs.reference_contract("typescript", repo, use_cache=False)
    assert (cached, len(calls)) == (False, 3)


def test_content_id_is_the_git_tree_for_a_clean_checkout_and_a_file_hash_otherwise(tmp_path):
    repo = _git_repo(tmp_path / "repo", {"main.ts": MAIN_TS})
    tree = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD:"], capture_output=True, text=True).stdout
    assert callgraph_refs.content_id(repo) == f"git-{tree.strip()}"
    (repo / "main.ts").write_text(MAIN_TS + "// edited\n")  # dirty: git's tree no longer says what is there
    assert callgraph_refs.content_id(repo).startswith("files-")


def test_a_missing_reference_tool_stops_the_run(tmp_path, monkeypatch):
    ref = dataclasses.replace(_fake_ref(CONTRACT, tmp_path / "a.js", []), installed=lambda: None)
    monkeypatch.setitem(callgraph_refs.REFERENCES, "typescript", ref)
    with pytest.raises(SystemExit, match="not installed"):
        callgraph_refs.reference_contract("typescript", tmp_path)


# ----------------------------------------------------------------------------- triage (#3774)


@pytest.mark.parametrize(
    ("line", "name", "inside"),
    [
        ("const s = `${fmt(2)}`;", "fmt", True),
        ('log("call helper(1) later");', "helper", True),
        ("helper(1);", "helper", False),
        ('helper(1); log("helper(2)")', "helper", False),  # one plain-code call is enough
        ("x.fmt(2)", "fmt", False),
        ("no call here", "fmt", False),
    ],
)
def test_in_string_only_when_every_occurrence_is_quoted(line, name, inside):
    assert callgraph_triage._in_string(line, name) is inside


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    """A tiny TS repo, scanned once with this checkout's engine."""
    repo = _git_repo(tmp_path_factory.mktemp("cg") / "repo", {"main.ts": MAIN_TS})
    return repo, cgr._scan(repo)


def test_triage_buckets_account_for_the_whole_recall_gap(scanned, tmp_path, monkeypatch):
    repo, db = scanned
    monkeypatch.setattr(callgraph_refs, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setitem(callgraph_refs.REFERENCES, "typescript", _fake_ref(CONTRACT, tmp_path / "a.js", []))
    (tmp_path / "a.js").write_text("x")
    monkeypatch.setattr(callgraph_triage, "reference_graph", callgraph_refs.reference_graph)
    monkeypatch.setattr(cgr, "_scan", lambda _repo: db)

    result = callgraph_triage.triage_repo("typescript", "tiny", repo)
    assert (result["reference_edges"], result["linked"]) == (2, 1)  # run -> helper is linked
    assert {b: len(v) for b, v in result["recall"].items()} == {"not_extracted/in_string": 1}
    assert result["recall"]["not_extracted/in_string"][0]["site"] == 9
    assert [len(v) for k, v in result["precision"].items() if k == "agree"] == [1]


# ----------------------------------------------------------------------------- explain (#3776)


def test_explain_re_runs_the_resolver_and_matches_the_scan(scanned):
    _repo, db = scanned
    text = explain_call.explain(db, "main.ts:run", "helper")
    assert "re-run matches the scan's recorded rows" in text
    assert "helper: file (scoped) -> main.ts:helper@1" in text
    assert "shape=binding" in text and "reach=bare" in text


def test_explain_needs_an_unambiguous_caller(scanned):
    _repo, db = scanned
    with pytest.raises(SystemExit, match="matches 0 files"):
        explain_call.explain(db, "nope.ts:run")


# ----------------------------------------------------------------------------- check (#3775)


def test_check_reports_a_missing_reference_tool_as_a_failure(monkeypatch, capsys, tmp_path):
    ref = dataclasses.replace(callgraph_refs.REFERENCES["typescript"], installed=lambda: None)
    monkeypatch.setitem(callgraph_check.REFERENCES, "typescript", ref)
    rc = callgraph_check.main(
        ["--langs", "typescript", "--skip", "tests,crucible,tree-sitter,lint", "--log-dir", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "MISSING  gate:typescript" in out and "FAILED" in out


def test_check_gate_detail_quotes_the_run_and_the_baseline():
    out = "| typescript | tsc | 99.9% (1520 judged) | 32.1% | 57.1% | 73.7% |\n"
    detail = callgraph_check._gate_detail("typescript")(out)
    assert detail.startswith("precision 99.9% (1520) recall 57.1% resolution 73.7%")
    assert "[baseline" in detail


def test_check_rejects_a_language_with_no_reference():
    with pytest.raises(SystemExit):
        callgraph_check.main(["--langs", "cobol"])
