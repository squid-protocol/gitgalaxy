"""#5882: tests/tools importable from every module here, so a scan takes `from scan_server import scan_to_db`
(galaxy_ir.scan_to_db with the engine imported once a process, not once a scan). Appended, so it shadows nothing."""

import sys
from pathlib import Path

_TOOLS = str(Path(__file__).resolve().parents[1] / "tools")
if _TOOLS not in sys.path:
    sys.path.append(_TOOLS)


def pytest_sessionstart(session):
    """#5606: warm the javac server and the JDK in this process (each xdist worker runs this), outside any test's timing,
    so the first javac test a worker draws does not pay the cold start and trip the per-test time ratchet."""
    import javac_server

    javac_server.warm()
