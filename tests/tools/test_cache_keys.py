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
