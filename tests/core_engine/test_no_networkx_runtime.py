"""
#3041: networkx is not a runtime dependency. With networkx made unimportable,
the engine still imports, computes every graph metric, and does not treat the
missing package as Zero-Dependency Mode. Run in a subprocess so blocking the
import cannot leak into the rest of the test session, where the parity harness
uses networkx as its oracle.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

# `python -c` puts the working directory first on sys.path, so the probe runs
# from this checkout's root -- otherwise a different gitgalaxy checkout in the
# caller's cwd would be the one imported.
REPO_ROOT = Path(__file__).resolve().parents[2]

PROBE = textwrap.dedent(
    """
    import sys

    sys.modules["networkx"] = None  # any `import networkx` now raises ImportError

    import gitgalaxy.galaxyscope as galaxyscope
    from gitgalaxy.core import network_risk_sensor
    from gitgalaxy.security.security_auditor import SecurityAuditor

    assert not hasattr(galaxyscope, "HAS_NETWORKX"), "networkx must not decide the scan mode"
    assert not hasattr(network_risk_sensor, "HAS_NETWORKX")

    files = [
        {"path": "a.py", "lang_id": "python", "raw_imports": ["b.py"]},
        {"path": "b.py", "lang_id": "python", "raw_imports": ["c.py", "a.py"]},  # a <-> b: a cycle
        {"path": "c.py", "lang_id": "python", "raw_imports": ["d.py"]},
        {"path": "d.py", "lang_id": "python", "raw_imports": []},
    ]
    files, macro = network_risk_sensor.NetworkRiskSensor().build_dependency_graph(files)
    assert all(value is not None for value in macro.values()), macro
    for f in files:
        metrics = f["telemetry"]["network_metrics"]
        for key in ("pagerank_score", "betweenness_score", "closeness_score"):
            assert metrics[key] is not None, (f["path"], key)

    reach = SecurityAuditor()._resolve_dependency_graph(files)[0]["dependency_network"]
    assert (reach["total_upstream"], reach["total_downstream"]) == (3, 1), reach
    print("OK")
    """
)


def test_the_engine_needs_no_networkx():
    result = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)
    assert result.returncode == 0 and result.stdout.strip().endswith("OK"), result.stdout + result.stderr
