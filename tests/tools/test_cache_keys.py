"""#4847: every workflow that caches pip keys it on file hashes only, so branches and PRs share one cache.

`setup-python`'s `cache: pip` builds the key `setup-python-<os>-<arch>-python-<version>-pip-<hashFiles(path)>`. Only the
`cache-dependency-path` is ours to vary, and a PR can only restore a cache saved by main (or itself) under the SAME key:
a different path list per workflow, or a run/sha/date in the key, makes a new ~450 MB cache per workflow or per PR
(10.6 GB / 208 caches on 2026-10-12). The canonical value hashes pyproject.toml and ci/requirements/*.txt (the files
that decide what pip installs); a job that checks the repo out into `gitgalaxy/` prefixes both, and the hash is the same
because hashFiles hashes contents, not paths.
"""

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
CANON = ("pyproject.toml", "ci/requirements/*.txt")
# workflow -> why it is not on the canonical path list yet (each is a sibling gap, not a design)
EXEMPT = {
    "mainframe-ground-truth.yml": "owner-protected (#4935): hashes gitgalaxy/pyproject.toml alone",
    "smoke-test.yml": "owner-protected (#4935): hashes pyproject.toml alone",
}
VOLATILE = re.compile(r"github\.(sha|run_id|run_number|run_attempt|ref|head_ref|event)|\bdate\b|\bnow\b|runner\.temp")


def _pip_caches():
    """(workflow, line number, the cache-dependency-path lines, whether the job checks out into gitgalaxy/)."""
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        lines = wf.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"(\s+)cache:\s*[\"']?pip[\"']?\s*(#.*)?$", line)
            if not m:
                continue
            job = i
            while job > 0 and not re.match(r"  [\w-]+:\s*$", lines[job]):
                job -= 1
            subdir = any(re.match(r"\s+path:\s*gitgalaxy\s*$", x) for x in lines[job:i])
            indent = len(m.group(1))
            dep: list[str] = []
            if i + 1 < len(lines) and re.match(rf"\s{{{indent}}}cache-dependency-path:", lines[i + 1]):
                head = lines[i + 1].split(":", 1)[1].strip()
                if head in ("|", ">", "|-", ">-", ""):
                    j = i + 2
                    while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
                        dep.append(lines[j].strip())
                        j += 1
                else:
                    dep = [head]
            yield wf.name, i + 1, dep, subdir


CASES = list(_pip_caches())


def test_the_sweep_sees_the_workflows():
    assert len(CASES) >= 30, "expected every `cache: pip` workflow; the parser found only %d" % len(CASES)


@pytest.mark.parametrize(("wf", "line", "dep", "subdir"), CASES, ids=[f"{c[0]}:{c[1]}" for c in CASES])
def test_pip_cache_key_is_the_shared_hash_only_shape(wf, line, dep, subdir):
    if wf in EXEMPT:
        pytest.skip(EXEMPT[wf])
    prefix = "gitgalaxy/" if subdir else ""
    want = [prefix + p for p in CANON]
    assert dep == want, f"{wf}:{line}: cache-dependency-path must be {want} (got {dep}) so branches share the pip cache"
    assert not any("${{" in d for d in dep), f"{wf}:{line}: no expressions in the pip cache key"


def test_exemptions_are_still_needed():
    """An exempt workflow that now matches the canonical shape drops off the list."""
    for wf in EXEMPT:
        found = [c for c in CASES if c[0] == wf]
        assert found, f"{wf} has no `cache: pip` any more; remove it from EXEMPT"
        assert all(c[2] != [("gitgalaxy/" if c[3] else "") + p for p in CANON] for c in found)


def test_explicit_pip_caches_key_on_hashes_only():
    """Any actions/cache step that caches pip's own cache dir must not put a run, sha, ref or date in its key."""
    bad = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        for step in re.split(r"\n\s+- (?=name:|uses:)", text):
            if "actions/cache" in step and re.search(r"path:.*(\.cache/pip|pip-cache|pip cache)", step):
                key = re.search(r"\bkey:\s*(.+)", step)
                if not key or VOLATILE.search(key.group(1)) or "hashFiles" not in key.group(1):
                    bad.append(wf.name)
    assert not bad, f"pip caches in {bad} must be keyed on hashFiles(...) only"


# --- #4968: every cache step (not just pip) -----------------------------------------------------------------------------
CACHE_USES = re.compile(r"uses:\s*actions/cache(/restore|/save)?@")
# the one place a commit sha belongs in a key: the same-base generation, saved at main's sha and restored at a PR's base sha
SHA_OK = re.compile(r"github\.sha|pull_request\.base\.sha")


def _cache_steps():
    """(workflow, kind, step text) for every actions/cache step: kind is 'both', 'restore' or 'save'."""
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for step in re.split(r"\n\s+- (?=name:|uses:)", wf.read_text(encoding="utf-8")):
            m = CACHE_USES.search(step)
            if m:
                yield wf.name, (m.group(1) or "both").lstrip("/"), step


def _key(step):
    m = re.search(r"\bkey:\s*(.+)", step)
    return m.group(1) if m else ""


def test_the_sweep_sees_the_cache_steps():
    steps = list(_cache_steps())
    assert len(steps) >= 5, "expected the actions/cache steps; the parser found %d" % len(steps)
    assert {k for _, k, _ in steps} >= {"restore", "save"}


def test_no_java_compile_cache_key_has_a_run_ref_or_date_component():
    """The `*-durations-<run_id>` keys (det-sweep, smoke-test) are deliberate (#4847: restore-keys takes the newest)."""
    bad = [
        (wf, _key(s))
        for wf, _, s in _cache_steps()
        if wf == "java-compile.yml"
        and re.search(r"github\.(run_id|run_number|run_attempt|ref|head_ref)\b|\bdate\b|\bnow\b", _key(s))
    ]
    assert not bad, f"cache keys must not vary per run: {bad}"


def test_a_sha_in_a_cache_key_is_only_the_same_base_generation():
    bad = [(wf, _key(s)) for wf, _, s in _cache_steps() if SHA_OK.search(_key(s)) and "java-same-base-" not in _key(s)]
    assert not bad, f"only java-same-base-* may be keyed on a commit: {bad}"


def _hashed_inputs(key):
    """The hashFiles(...) argument list of a cache key, with the checkout prefix (`base/` or `gitgalaxy/`) stripped."""
    return [re.sub(r"^(base|gitgalaxy)/", "", a) for a in re.findall(r"'([^']+)'", key) if "/" in a]


def test_same_base_cache_is_restored_by_java_compile_and_seeded_by_its_own_workflow():
    """A PR's cache scope is its own ref, so java-compile only restores. #5142: the save lives in
    java-base-generation.yml, because java-compile's push run is cancelled (#4825) or tested-tree-skipped before it saves."""
    steps = [(wf, k, s) for wf, k, s in _cache_steps() if "java-same-base-" in _key(s)]
    assert sorted((wf, k) for wf, k, _ in steps) == [
        ("java-base-generation.yml", "restore"),
        ("java-base-generation.yml", "save"),
        ("java-compile.yml", "restore"),
    ], steps
    restore = next(s for wf, k, s in steps if wf == "java-compile.yml")
    lookup = next(s for wf, k, s in steps if wf == "java-base-generation.yml" and k == "restore")
    save = next(s for wf, k, s in steps if wf == "java-base-generation.yml" and k == "save")
    # content-keyed (the generation inputs of the PR's base checkout / main's own), not the base commit's sha
    assert "base/gitgalaxy/" in _key(restore) and "gitgalaxy/gitgalaxy/" in _key(restore)
    assert "gitgalaxy/gitgalaxy/" in _key(save) and "base/" not in _key(save), "the save key hashes main's own checkout"
    assert _hashed_inputs(_key(save)) == _hashed_inputs(_key(lookup))
    # on a push the restore hashes main's own checkout: the same inputs the seeding workflow hashes
    on_push = _key(restore).split("||")[-1]
    assert _hashed_inputs(on_push) == _hashed_inputs(_key(save)), "restore and seeding key hash different inputs"
    pr_side = _key(restore).split("||")[0]
    assert _hashed_inputs(pr_side) == _hashed_inputs(_key(save)), "a PR would look up a key nothing writes"
    assert "lookup-only: true" in lookup, "a push whose content key exists must not regenerate"


def _scan_inputs(expr):
    """The hashFiles patterns of an expression, `!` kept and the checkout prefix (`base/` or `gitgalaxy/`) stripped."""
    return [re.sub(r"^(!?)(base|gitgalaxy)/", r"\1", a) for a in re.findall(r"'([^']+)'", expr)]


def test_engine_scan_cache_is_restored_by_java_compile_and_seeded_by_its_own_workflow():
    """#5142: the dsf engine scan (~90 s a side) is kept across runs. Same split as the same-base generation: java-compile
    only restores (#4968), java-base-generation.yml saves. The key is a coarse content hash; the tool's scan_key is exact."""
    compile_text = (WORKFLOWS / "java-compile.yml").read_text(encoding="utf-8")
    seed_text = (WORKFLOWS / "java-base-generation.yml").read_text(encoding="utf-8")
    steps = [(wf, k, s) for wf, k, s in _cache_steps() if "java-scan-" in _key(s) or "java_scan_cache" in s]
    assert sorted((wf, k) for wf, k, _ in steps) == [
        ("java-base-generation.yml", "restore"),
        ("java-base-generation.yml", "save"),
        ("java-compile.yml", "restore"),
    ], steps
    lookup = next(s for wf, k, s in steps if wf == "java-base-generation.yml" and k == "restore")
    save = next(s for wf, k, s in steps if wf == "java-base-generation.yml" and k == "save")
    assert "lookup-only: true" in lookup and _key(lookup) == _key(save)
    seeded = _scan_inputs(_key(save))
    # the compile side computes the same key from the base checkout on a PR and from its own on a push
    (keyed,) = re.findall(r'echo "key=(java-scan-[^"]*)"', compile_text)
    parts = re.findall(r"pull_request' && hashFiles\(([^)]*)\) \|\| hashFiles\(([^)]*)\)", keyed)
    assert len(parts) == 3, keyed
    for side in (0, 1):
        got = [a for p in parts for a in _scan_inputs(p[side])]
        assert got == seeded, "the compile-side scan key hashes different inputs than the seeding"
    assert any(a.startswith("!") for a in seeded) and "!gitgalaxy/cobol_to_java_controller.py" in seeded
    assert seeded[0] == "gitgalaxy/**" and "tests/tools/java_target_matrix.py" in seeded
    # the key must change whenever the tool's exact key can: the files the scan reads from the otherwise-left-out translator
    assert "gitgalaxy/tools/cobol_to_java/det/copy/**" in seeded
    assert "gitgalaxy/tools/cobol_to_java/cics_task_containers.py" in seeded
    for text in (compile_text, seed_text):
        assert '--scan-cache "$RUNNER_TEMP/java_scan_cache"' in text
    assert compile_text.count('--scan-cache "$RUNNER_TEMP/java_scan_cache"') == 2, "the check and the scan build"


def test_the_seeding_workflow_is_never_cancelled_or_gated_and_never_runs_on_a_pull_request():
    text = (WORKFLOWS / "java-base-generation.yml").read_text(encoding="utf-8")
    assert "cancel-in-progress: false" in text and "github.sha" in text.split("concurrency:")[1].split("jobs:")[0]
    assert not re.search(r"^\s+needs:", text, re.M), "a gate job could skip the seeding"
    assert "pull_request" not in text.split("jobs:")[0].split("on:")[1], "a PR's cache scope is its own ref"


def test_the_seeding_run_passes_the_only_configs_it_builds():
    text = (WORKFLOWS / "java-base-generation.yml").read_text(encoding="utf-8")
    assert "ONLY=(--only $CONFIGS)" in text
    assert '"${ONLY[@]}"' in text, "ONLY is built but never passed to java_target_matrix.py"


def test_every_java_compile_cache_save_skips_pull_requests():
    bad = [
        wf
        for wf, k, s in _cache_steps()
        if wf == "java-compile.yml" and k == "save" and "github.event_name != 'pull_request'" not in s
    ]
    assert not bad, f"actions/cache/save steps must not run on pull requests: {bad}"


def test_java_compile_gradle_cache_is_hash_keyed_not_setup_gradles_own():
    text = (WORKFLOWS / "java-compile.yml").read_text(encoding="utf-8")
    step = next(s for s in re.split(r"\n\s+- (?=name:|uses:)", text) if "gradle/actions/setup-gradle" in s)
    assert re.search(r"cache-disabled:\s*true", step), (
        "setup-gradle's own cache key ends in the run's sha (gradle-home-v2)"
    )
    deps = [s for wf, _, s in _cache_steps() if wf == "java-compile.yml" and ".gradle/caches" in s]
    assert deps, "the gradle cache moved out of java-compile.yml"
    for s in deps:
        assert "hashFiles" in _key(s) and not SHA_OK.search(_key(s)), _key(s)


# --- #5024: the pinned-corpora cache (mainframe-corpora-<hash>) ----------------------------------------------------------
# Same mechanism as #4968: a combined actions/cache step saves under the PR's own ref, so a PR that edits corpora.json left
# a copy per PR that nothing else could read. On a pull_request workflow it must be a restore plus a main-only save.
CORPORA_KEY = "mainframe-corpora-"
# workflow -> why its combined step may stay (never triggered by a pull_request, so no per-PR copies)
CORPORA_EXEMPT = {
    "blocker-baseline.yml": "workflow_dispatch only",
    "evidence-refresh.yml": "nightly schedule + workflow_dispatch only",
}


def _triggers(wf):
    import yaml

    doc = yaml.safe_load((WORKFLOWS / wf).read_text(encoding="utf-8"))
    return set(doc.get(True) or doc.get("on") or {})  # PyYAML reads the bare key `on` as True


def _corpora_steps():
    return [(wf, k, s) for wf, k, s in _cache_steps() if CORPORA_KEY in _key(s)]


def test_the_corpora_sweep_sees_every_step():
    steps = _corpora_steps()
    assert len(steps) >= 19, "expected restore+save pairs and the exempt steps; found %d" % len(steps)
    assert {wf for wf, _, _ in steps} >= {"java-compile.yml", "det-sweep.yml", *CORPORA_EXEMPT}


def test_corpora_exemptions_are_real_and_never_pull_request_triggered():
    in_use = {wf for wf, _, _ in _corpora_steps()}
    for wf, why in CORPORA_EXEMPT.items():
        assert wf in in_use, f"{wf} no longer caches the corpora; remove it from CORPORA_EXEMPT ({why})"
        assert "pull_request" not in _triggers(wf), f"{wf} is pull_request-triggered now; split its cache ({why})"


def test_pull_request_workflows_never_use_a_combined_corpora_cache():
    bad = [wf for wf, k, _ in _corpora_steps() if k == "both" and wf not in CORPORA_EXEMPT]
    assert not bad, f"{sorted(set(bad))}: use actions/cache/restore + a main-only actions/cache/save (#5024)"


def test_every_corpora_save_skips_pull_requests_and_pairs_with_a_restore():
    steps = [(wf, k, s) for wf, k, s in _corpora_steps() if wf not in CORPORA_EXEMPT]
    saves = [(wf, s) for wf, k, s in steps if k == "save"]
    restores = [(wf, s) for wf, k, s in steps if k == "restore"]
    assert saves and len(saves) == len(restores), (len(saves), len(restores))
    for wf, s in saves:
        assert "github.event_name != 'pull_request'" in s, f"{wf}: the corpora save must not run on a pull request"
        assert "steps.corpora.outputs.cache-hit != 'true'" in s, f"{wf}: save only on a miss (a hit already exists)"
        assert "continue-on-error: true" in s, f"{wf}: a lost save race must not fail the job"
    for wf, s in restores:
        assert re.search(r"\bid:\s*corpora\b", s), f"{wf}: the corpora restore needs `id: corpora` for the save's guard"
    # each restore's key is saved again verbatim, in the same workflow (det-sweep has three such jobs)
    assert sorted((wf, _key(s).strip()) for wf, s in saves) == sorted((wf, _key(s).strip()) for wf, s in restores)
    for wf, s in saves:
        assert re.search(r"path:\s*\.mainframe_corpora\s*$", s, re.M), f"{wf}: save path"


# --- #6675: every cache, not just the corpora ---------------------------------------------------------------------------
# 2026-10-25: 10.69 GB / 127 caches, the oldest last read 10.6 h earlier: GitHub evicts past 10 GB, so main's caches
# lived half a day. Combined actions/cache steps on pull_request workflows had saved 2.18 GB of scip-java (graph-accuracy
# never ran on main, so no PR could read another's) and 9 PR copies of db2-odbc-cli (main's had been evicted).
def _pr_workflows():
    return sorted(wf.name for wf in WORKFLOWS.glob("*.yml") if "pull_request" in _triggers(wf.name))


def test_no_pull_request_workflow_has_a_combined_cache_step():
    pr = set(_pr_workflows())
    bad = sorted({wf for wf, k, _ in _cache_steps() if k == "both" and wf in pr})
    assert not bad, f"{bad}: use actions/cache/restore + a save that skips pull requests (#6675, as #5024)"


NON_PR_GUARD = re.compile(r"github\.event_name\s*(?:!=\s*'pull_request'|==\s*'(?:schedule|workflow_dispatch|push)')")


def test_every_cache_save_on_a_pull_request_workflow_skips_pull_requests():
    """`!= 'pull_request'`, or an `==` that pins a non-PR event (det-sweep's nightly / dispatch durations saves)."""
    pr = set(_pr_workflows())
    bad = [
        (wf, _key(s).strip()) for wf, k, s in _cache_steps() if k == "save" and wf in pr and not NON_PR_GUARD.search(s)
    ]
    assert not bad, f"a save on a PR is scoped to that PR's ref, which nothing else reads (#6675): {bad}"


def test_setup_go_does_not_cache_on_a_pull_request():
    """setup-go's built-in cache restores and saves in one step, so on a PR it is off (#6675)."""
    for wf in _pr_workflows():
        text = (WORKFLOWS / wf).read_text(encoding="utf-8")
        for step in re.split(r"\n\s+- (?=name:|uses:)", text):
            if "actions/setup-go@" in step:
                assert "cache: ${{ github.event_name != 'pull_request' }}" in step, wf


def test_graph_accuracy_seeds_its_caches_on_main():
    """The only run that can save scip-java / cargo / Go for every PR is one on main: the nightly (#6675)."""
    assert {"schedule", "workflow_dispatch"} <= _triggers("graph-accuracy-audit.yml")
