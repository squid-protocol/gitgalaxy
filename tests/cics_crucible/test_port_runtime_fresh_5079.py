"""#5079: a committed crucible port carries the det runtime it compiles with (cobolrt/**, the package filled in). A copy
left behind predates what the live runtime models (ADDRESS COMMAREA's addressCommarea, the pointer lane, ...), so the
port compiles against a runtime the translator no longer targets. Each committed copy must equal the live source."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
PORTS = REPO / "tests" / "cics_crucible" / "ports"
PKG = "com.gitgalaxy.modernized"
# Refresh with: python -c "from gitgalaxy.tools.cobol_to_java.det import program as P" over runtime_files(PKG, False)
# written into each overlay's cobolrt/ (the batch adapters are left out: a CICS-only estate has none).


def _tracked_runtime_overlays():
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files", "tests/cics_crucible/ports"],  # noqa: S607
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()  # fmt: skip
    trees = {}
    for rel in out:
        if "/overlay/cobolrt/" in rel and rel.endswith(".java"):
            overlay = rel.split("/overlay/", 1)[0] + "/overlay"
            trees.setdefault(overlay, []).append(rel.split("/overlay/", 1)[1])
    return trees


def test_every_committed_port_runtime_is_the_live_runtime():
    from gitgalaxy.tools.cobol_to_java.det import program as P

    live = P.runtime_files(PKG, False)
    trees = _tracked_runtime_overlays()
    assert trees, "no port carries a runtime copy: the guard has nothing to check"
    for overlay, files in trees.items():
        assert sorted(files) == sorted(live), f"{overlay}: file set differs from the live runtime"
        stale = [rel for rel in live if (REPO / overlay / rel).read_text(encoding="utf-8") != live[rel]]
        assert not stale, f"{overlay}: stale copies of {stale}"
