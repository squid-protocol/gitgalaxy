"""Suite-wide pytest hooks.

Long string parameters get short test IDs. pytest puts every test's node ID in the
PYTEST_CURRENT_TEST environment variable, and Windows caps one environment
variable at 32,767 characters. A ReDoS test that parametrizes on its own
pathological payload (e.g. `"COMMAREA " * 5000`) therefore fails on Windows during
setup with "the environment variable is longer than 32767 characters", before the
test body runs, while Linux and macOS pass. That surfaced first on the labelled
full-suite Windows jobs for #3404, from test_commarea_contract.py (#3369).

A string longer than _MAX_ID_CHARS becomes its first characters plus a length and
a short content hash. The ID stays readable, stays stable across runs, and stays
distinct for payloads that share a prefix.

Under pytest-xdist every scan a test runs gets one extraction worker
(GALAXYSCOPE_MAX_WORKERS=1, #3913): xdist already puts a test on every core, and a
scan's own worker pool on top of that only oversubscribes them -- on Windows and macOS,
where each pool worker re-imports GitGalaxy, it was most of the suite's run time.

Test-time ratchet (#5166, tests/tools/time_ratchet.py): a test marked `slow` must say why (`reason=`), and when
GITGALAXY_TEST_TIMES names a file the run writes each test's seconds (setup + call + teardown, as pytest-split counts
them) and the reasons of the slow-marked ones there.

ReDoS sweeps (#5166): a test under tests/extraction/ whose name has `redos` or `linear_on_pathological` is marked
`redos_sweep`, so a pull request that changes no sweep input deselects them (tests/tools/sweep_plan.py, smoke-test.yml).
The hook is tryfirst: pytest's own `-m` deselection and pytest-split's slicing must both see the marker.
"""

import functools
import hashlib
import json
import os

import pytest

_MAX_ID_CHARS = 64


def pytest_make_parametrize_id(val):
    if isinstance(val, str) and len(val) > _MAX_ID_CHARS:
        digest = hashlib.sha256(val.encode("utf-8", "surrogatepass")).hexdigest()[:8]
        return f"{val[:40]!r}...len{len(val)}-{digest}"
    return None


def pytest_configure(config):
    if hasattr(config, "workerinput"):  # an xdist worker (the scans it runs inherit this)
        os.environ.setdefault("GALAXYSCOPE_MAX_WORKERS", "1")


def _slow_reason(item):
    marker = item.get_closest_marker("slow")
    if marker is None:
        return None
    return marker.kwargs.get("reason") or (marker.args[0] if marker.args else "")


@functools.cache
def _under_extraction(path, root):
    """Once per test file, not per test (#5882: per item it was ~18% of collecting the suite)."""
    try:
        return path.relative_to(root).parts[:2] == ("tests", "extraction")
    except ValueError:
        return False


def _is_redos_sweep(item):
    name = item.originalname or item.name
    return ("redos" in name or "linear_on_pathological" in name) and _under_extraction(item.path, item.config.rootpath)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        if _is_redos_sweep(item):
            item.add_marker(pytest.mark.redos_sweep)
        reason = _slow_reason(item)
        if reason is not None and not str(reason).strip():
            raise pytest.UsageError(
                f"{item.nodeid}: @pytest.mark.slow needs a reason, e.g. slow(reason='scans 40 repos')"
            )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    reason = _slow_reason(item)
    if reason is not None:
        outcome.get_result().user_properties.append(("slow", str(reason)))


_times: dict[str, float] = {}
_slow: dict[str, str] = {}


def pytest_runtest_logreport(report):
    if os.environ.get("GITGALAXY_TEST_TIMES"):
        _times[report.nodeid] = _times.get(report.nodeid, 0.0) + report.duration
        for key, value in report.user_properties:
            if key == "slow":
                _slow[report.nodeid] = value


def pytest_sessionfinish(session):
    path = os.environ.get("GITGALAXY_TEST_TIMES")
    if path and not hasattr(session.config, "workerinput"):  # the xdist controller (or a plain run) holds every report
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"seconds": _times, "slow": _slow}, fh, sort_keys=True)
