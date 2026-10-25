"""#5543: the ground-truth scan-cache key hashes what a scan reads, and leaves the COBOL-to-Java translator out.

A translator commit must not invalidate the saved scans, and a file the scan imports or reads must never drop out of the key.
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "mainframe-ground-truth.yml"
FIXED_INPUTS = ("tests/tools/mainframe_corpus.py", "pyproject.toml", "ci/requirements/*.txt")


def _patterns():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["plan"]["steps"]
    (step,) = [s for s in steps if s.get("name") == "Key the scans by engine state"]
    args = re.search(r"hashFiles\(([^)]*)\)", step["env"]["ENGINE"]).group(1)
    return re.findall(r"'([^']+)'", args)


def _glob(pattern):
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def _hashed(path, patterns):
    """Included by a positive pattern and by no `!` pattern (the test never relies on pattern order)."""
    inc = [p for p in patterns if not p.startswith("!")]
    exc = [p[1:] for p in patterns if p.startswith("!")]
    return any(_glob(p).match(path) for p in inc) and not any(_glob(p).match(path) for p in exc)


def _is_tool_readme(path):
    return path.startswith("gitgalaxy/tools/") and path.endswith("/README.md")


def _tracked():
    out = subprocess.run(["git", "ls-files", "gitgalaxy"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def _import_closure(entry="gitgalaxy.galaxyscope"):
    def path_of(mod):
        base = ROOT / mod.replace(".", "/")
        for cand in (base / "__init__.py", base.with_suffix(".py")):
            if cand.exists():
                return cand
        return None

    seen, todo = {}, [entry]
    while todo:
        mod = todo.pop()
        p = path_of(mod)
        if mod in seen or p is None:
            continue
        seen[mod] = p
        parts = mod.split(".")
        todo += [".".join(parts[:i]) for i in range(1, len(parts))]
        pkg = parts if p.name == "__init__.py" else parts[:-1]
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                todo += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                base = (
                    ".".join(pkg[: len(pkg) - (n.level - 1)] + ([n.module] if n.module else []))
                    if n.level
                    else n.module
                )
                if base:
                    todo += [base] + [f"{base}.{a.name}" for a in n.names]
    return {p.relative_to(ROOT).as_posix() for m, p in seen.items() if m.startswith("gitgalaxy")}


def test_every_file_the_scan_imports_is_hashed():
    patterns = _patterns()
    closure = _import_closure()
    assert len(closure) > 50, "the import walk found almost nothing"
    dropped = sorted(f for f in closure if not _hashed(f, patterns))
    assert not dropped, f"imported by a scan but outside the scan-cache key: {dropped}"


def test_the_stand_in_copybooks_the_scan_reads_are_hashed():
    patterns = _patterns()
    cpys = [f for f in _tracked() if f.startswith("gitgalaxy/tools/cobol_to_java/det/copy/")]
    assert cpys, "copy_libraries.STAND_IN_DIR moved: update this test and the key"
    assert all(_hashed(f, patterns) for f in cpys)


def test_non_python_engine_data_is_hashed():
    patterns = _patterns()
    standalone = ("/tools/cobol_to_java/", "/tools/cobol_to_cobol/", "/tools/terabyte_log_scanning/")
    data = [
        f
        for f in _tracked()
        if not f.endswith(".py") and not any(d in f for d in standalone) and not _is_tool_readme(f)
    ]
    assert data and all(_hashed(f, patterns) for f in data)


def test_the_fixed_inputs_stay_in_the_key():
    patterns = _patterns()
    assert "gitgalaxy/**" in patterns
    for p in FIXED_INPUTS:
        assert p in patterns


def test_each_exclusion_leaves_out_tracked_files():
    patterns = _patterns()
    exc = [p[1:] for p in patterns if p.startswith("!")]
    assert exc, "the key no longer narrows anything"
    tracked = _tracked()
    for p in exc:
        assert any(_glob(p).match(f) for f in tracked), f"exclusion {p} matches no tracked file (dead pattern)"
    assert not _hashed("gitgalaxy/tools/cobol_to_java/det/stmt.py", patterns)


def test_the_standalone_tools_are_left_out_but_what_a_scan_imports_is_not():
    """#5543: the cobol_to_cobol forges and terabyte_log_scanning are not scan inputs; galaxy_ir and pli_mapping are."""
    patterns = _patterns()
    tracked = _tracked()
    left_out = [
        f
        for f in tracked
        if f.startswith(("gitgalaxy/tools/terabyte_log_scanning/", "gitgalaxy/tools/cobol_to_cobol/"))
    ]
    kept = {"gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py", "gitgalaxy/tools/cobol_to_cobol/pli_mapping.py"}
    assert kept <= set(tracked)
    for f in left_out:
        assert _hashed(f, patterns) == (f in kept), f
    assert _hashed("gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py", patterns) is False


def test_network_readiness_and_supply_chain_dirs_are_hashed_exactly_when_the_scan_imports_them():
    """#5543: every tracked file of the three tool dirs is in the key iff the scan imports it; READMEs never are."""
    patterns = _patterns()
    closure = _import_closure()
    dirs = ("network_auditing", "readiness", "supply_chain_security")
    files = [f for f in _tracked() if any(f.startswith(f"gitgalaxy/tools/{d}/") for d in dirs)]
    assert {f for f in files if f.endswith(".py")} & closure, "the closure reaches none of the three dirs"
    for f in files:
        assert _hashed(f, patterns) == (f in closure), f
    kept = {
        "gitgalaxy/tools/network_auditing/full_api_network_map.py",
        "gitgalaxy/tools/readiness/__init__.py",
        "gitgalaxy/tools/readiness/offline.py",
        "gitgalaxy/tools/supply_chain_security/binary_anomaly_detector.py",
        "gitgalaxy/tools/supply_chain_security/supply_chain_firewall.py",
    }
    assert all(_hashed(f, patterns) for f in kept)
    assert not _hashed("gitgalaxy/tools/supply_chain_security/vault_sentinel.py", patterns)
