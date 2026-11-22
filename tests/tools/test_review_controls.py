"""#7155 part 3: each hidden review-layer defect is really there, passes every mechanical gate, and is blind to the reviewer."""

import ast
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import review_controls as rc  # noqa: E402

DEFECTIVE = [c for c in rc.CONTROLS if c.cls]
CLASSES = {"swallowed-exception", "test-that-cannot-fail", "green-by-skipping"}


def test_the_shipped_catalog_is_safe_blind_and_paired():
    assert rc.problems() == []
    assert {c.cls for c in DEFECTIVE} == CLASSES
    assert all(c.twin in rc.BY_KEY and not rc.BY_KEY[c.twin].cls for c in DEFECTIVE)


def test_each_unsafe_or_leaky_shape_is_named():
    c = rc.BY_KEY["swallow"]
    bad = (
        replace(c, key="wf", module=".github/workflows/x.yml"),
        replace(c, key="up", module="../outside.py"),
        replace(c, key="exists", module="tests/tools/review_controls.py"),
        replace(c, key="net", module_src="import socket\n"),
        replace(c, key="leak", title="A canary change"),
        replace(c, key="leakfile", module_src='"""A planted defect."""\n'),
        replace(c, key="notwin", twin="nobody"),
        replace(c, key="nowhere", where="no such line"),
        replace(rc.BY_KEY["swallow-clean"], key="orphan"),
        replace(c, key="lonely", twin="", cls="x"),
    )
    out = rc.problems(bad)
    for key, word in (
        ("wf:", "workflow"),
        ("up:", "leaves"),
        ("exists:", "already exists"),
        ("net:", "must not"),
        ("leak:", "names the experiment"),
        ("leakfile:", "names the experiment"),
        ("notwin:", "missing"),
        ("nowhere:", "names no line"),
        ("orphan:", "orphan"),
        ("lonely:", "no clean twin"),
    ):
        assert any(p.startswith(key) and word in p for p in out), (key, out)
    assert any("shipped twice" in p for p in rc.problems((c, c)))


def test_a_twin_that_drifts_from_its_defect_is_named():
    c = rc.BY_KEY["swallow"]
    twin = replace(rc.BY_KEY[c.twin], title="Another title")
    assert any("does not share" in p for p in rc.problems((c, twin)))


@pytest.mark.parametrize("c", rc.CONTROLS, ids=lambda c: c.key)
def test_every_file_parses_and_is_new_only(c):
    for path, src in c.files.items():
        ast.parse(src)
        assert path.startswith("tests/tools/")
        assert src.endswith("\n") and "\r" not in src


def test_the_packet_shows_only_title_body_and_diff():
    for c in rc.CONTROLS:
        packet = rc.reviewer_packet(c)
        assert set(packet) == {"title", "body", "diff"}
        text = " ".join(packet.values())
        assert not rc.LEAKY.search(text), c.key
        assert c.what not in text and c.key not in text.replace(c.module, "")
        assert not c.cls or c.cls not in text
        assert c.where in packet["diff"] or not c.cls
    pair = (rc.reviewer_packet(rc.BY_KEY["swallow"]), rc.reviewer_packet(rc.BY_KEY["swallow-clean"]))
    assert pair[0]["title"] == pair[1]["title"] and pair[0]["body"] == pair[1]["body"]


def test_the_answer_key_points_at_a_real_changed_line():
    for c in DEFECTIVE:
        key = rc.answer_key(c)
        assert key["defective"] and key["class"] in CLASSES and key["file"]
        assert any(key["where"] in ln for ln in c.files[key["file"]].splitlines())
        assert rc.answer_key(rc.BY_KEY[c.twin])["defective"] is False


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
@pytest.mark.parametrize("c", rc.CONTROLS, ids=lambda c: c.key)
def test_the_diff_applies_as_new_files(c, tmp_path):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, env=env)
    patch = tmp_path / "p.diff"
    patch.write_text(rc.diff(c), encoding="utf-8", newline="\n")
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=tmp_path, check=True, env=env)


@pytest.mark.parametrize("c", [c for c in rc.CONTROLS if c.key.startswith("swallow")], ids=lambda c: c.key)
def test_the_swallowed_exception_is_swallowed_and_the_twin_raises(c):
    ns: dict = {}
    exec(compile(c.module_src, c.module, "exec"), ns)  # the catalog's own inert source
    if c.cls:
        assert ns["parse_budget"]("three") == 0
    else:
        with pytest.raises(ValueError):
            ns["parse_budget"]("three")


def _run(root: Path, c, *, broken: bool = False) -> dict[str, str]:
    """Write one control's files under root, optionally breaking its feature, run its tests: {test name: outcome}."""
    src = c.module_src.replace(*c.mutation) if broken else c.module_src
    for path, text in ((c.module, src), (c.test, c.test_src)):
        (root / Path(path).name).write_text(text, encoding="utf-8", newline="\n")
    out = root / "r.xml"
    env = {k: v for k, v in os.environ.items() if k != "LINE_COUNT_FIXTURES"}
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={out}", str(root)],
        cwd=root, env=env, check=False, capture_output=True,
    )  # fmt: skip
    result = {}
    for case in ET.parse(out).getroot().iter("testcase"):
        skipped, failed = case.find("skipped") is not None, case.find("failure") is not None
        result[case.get("name") or ""] = "skipped" if skipped else "failed" if failed else "passed"
    return result


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory):
    """Every runnable control, as shipped and with its feature broken, run in parallel (one pytest each)."""
    jobs = {(c.key, broken): c for c in rc.CONTROLS if c.mutation[0] for broken in (False, True)}

    def go(item):
        (key, broken), c = item
        return (key, broken), _run(tmp_path_factory.mktemp(f"{key}{int(broken)}"), c, broken=broken)

    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(go, jobs.items()))


def test_every_shipped_suite_is_green_or_skipped_so_no_gate_can_object(outcomes):
    for (key, broken), states in outcomes.items():
        if not broken:
            assert states and "failed" not in states.values(), key


def test_the_test_that_cannot_fail_stays_green_when_the_code_is_broken(outcomes):
    assert set(outcomes["vacuous", True].values()) == {"passed"}
    assert "failed" in outcomes["vacuous-clean", True].values()


def test_the_green_by_skipping_check_is_skipped_and_its_twin_catches_a_break(outcomes):
    assert "skipped" in outcomes["skipped", False].values()
    assert "failed" not in outcomes["skipped", True].values()  # still green with the rule broken
    assert set(outcomes["skipped-clean", False].values()) == {"passed"}
    assert "failed" in outcomes["skipped-clean", True].values()


@pytest.mark.skipif(shutil.which("ruff") is None, reason="needs ruff")
def test_no_mechanical_gate_can_object(tmp_path):
    """Lint and format the files with the repo's own formatter config."""
    shutil.copy(rc.REPO / "pyproject.toml", tmp_path / "pyproject.toml")
    for c in rc.CONTROLS:
        d = tmp_path / "tests" / "tools" / c.key
        d.mkdir(parents=True)
        for path, src in c.files.items():
            (d / Path(path).name).write_text(src, encoding="utf-8", newline="\n")
    # tests/ is held to syntax errors, the formatter and (here, stricter) pyflakes and bugbear; not to bandit or isort
    for sub, extra in (("check", ["--select", "E,W,F,B", "--ignore", "E501"]), ("format", ["--check"])):
        proc = subprocess.run(["ruff", sub, *extra, "."], cwd=tmp_path, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
