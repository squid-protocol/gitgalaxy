"""#8889: Windows has no system IANA zone database, so a `zoneinfo` consumer needs the `tzdata` wheel in the CI env.

Without it the Windows legs of the full suite failed (`ZoneInfoNotFoundError` in the progress report, and
`java_target._known_zone` silently checking shape only), while Linux and macOS stayed green.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQ = ROOT / "ci" / "requirements"
# a tz-database consumer found by name; a line that only mentions the word in prose is not one
CONSUMER = re.compile(r"^\s*(?:from zoneinfo import|import zoneinfo)", re.M)
KNOWN_CONSUMERS = {
    "gitgalaxy/tools/cobol_to_java/java_target.py",
    "tests/tools/progress_report.py",
}
WIN32_TZDATA = re.compile(r"^tzdata\b[^\n]*;\s*sys_platform\s*==\s*['\"]win32['\"]", re.M)


def test_the_test_requirements_pin_tzdata_for_windows():
    for name in ("pytest.in", "pytest.txt", "test.txt"):
        text = (REQ / name).read_text(encoding="utf-8")
        assert WIN32_TZDATA.search(text), f"ci/requirements/{name} must list tzdata for sys_platform == 'win32'"


def test_every_zoneinfo_consumer_is_known():
    found = set()
    for top in ("gitgalaxy", "tests"):
        for path in (ROOT / top).rglob("*.py"):
            if path.name == Path(__file__).name:
                continue
            if CONSUMER.search(path.read_text(encoding="utf-8")):
                found.add(path.relative_to(ROOT).as_posix())
    assert found == KNOWN_CONSUMERS, (
        f"a zoneinfo consumer was added or removed: {sorted(found ^ KNOWN_CONSUMERS)}; "
        "check it works on Windows with only the tzdata pin, then update KNOWN_CONSUMERS"
    )
