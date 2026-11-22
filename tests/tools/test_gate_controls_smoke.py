"""#7155: negative control for the os-smoke-grid gate. Its smoke steps run `python -m MODULE --help` and must exit 0.

The workflow's own smoke commands are read from the file, so a new step is covered without editing this test. The
runner below is the gate's decision (a non-zero exit fails the step): a module that is gone, or one that raises on
import, must turn it red. This proves the check, not the OS x Python grid around it.
"""

import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "os-smoke-grid.yml"
SMOKE = re.compile(r"^\s*run:\s*python -m (?P<module>[\w.]+) --help\s*$", re.MULTILINE)


def _smoke_modules() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    return SMOKE.findall(text)


def _run_help(module: str, extra_path: Path | None = None) -> int:
    env = None
    if extra_path is not None:
        import os

        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(extra_path), os.environ.get("PYTHONPATH", "")])}
    return subprocess.run(
        [sys.executable, "-m", module, "--help"], cwd=REPO, env=env, capture_output=True, timeout=120, check=False
    ).returncode


def test_the_workflow_has_smoke_steps_to_read():
    modules = _smoke_modules()
    assert len(modules) >= 5 and "gitgalaxy.galaxyscope" in modules, modules


def test_every_smoke_entry_point_exits_zero():
    """Positive control: the clean tree stays green."""
    modules = _smoke_modules()
    with ThreadPoolExecutor(max_workers=len(modules)) as pool:
        codes = dict(zip(modules, pool.map(_run_help, modules), strict=True))
    assert all(c == 0 for c in codes.values()), codes


def test_a_missing_or_import_broken_entry_point_goes_red(tmp_path):
    """Negative control: the same runner fails on a module that is gone and on one that raises at import."""
    assert _run_help("gitgalaxy.no_such_entry_point_7155") != 0
    (tmp_path / "broken_entry_7155.py").write_text("raise ImportError('planted')\n", encoding="utf-8")
    assert _run_help("broken_entry_7155", extra_path=tmp_path) != 0
