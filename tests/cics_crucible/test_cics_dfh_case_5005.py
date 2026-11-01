"""#5005 (register X42): a hand-traced cics-crucible case logs what IBM documents, and IBM names no CICS-defined
read-only container or channel, so the DFH-name dispositions (refused by name) have no crucible log. What a case can
prove is the other side: its channel and container names are ordinary, so neither runtime refuses it.

This test reads every `ca-channel-*` case in the crucible checkout (`CICS_CRUCIBLE_PATH`, else beside the repo) and fails
on a quoted literal beginning DFH in any of its COBOL sources: such a name would be refused by name (X42), not run."""

import os
import re
from pathlib import Path

import pytest

_DFH_LITERAL = re.compile(r"""(['"])\s*DFH[^'"]*\1""", re.IGNORECASE)


def dfh_literals(cobol: str) -> list[str]:
    """Quoted DFH literals in the code area of fixed-format COBOL (comment lines, column 7 `*`, are skipped)."""
    found = []
    for line in cobol.splitlines():
        if len(line) > 6 and line[6] in "*/":
            continue
        found += [m.group(0) for m in _DFH_LITERAL.finditer(line[:72])]
    return found


def _crucible_root() -> Path | None:
    env = os.environ.get("CICS_CRUCIBLE_PATH")
    root = Path(env) if env else Path(__file__).resolve().parents[3] / "cics-crucible"
    return root if (root / "cases").is_dir() else None


def _channel_case_sources() -> list[Path]:
    root = _crucible_root()
    if root is None:
        return []
    return sorted(root.glob("cases/*/ca-channel-*/src/*.cbl"))


def test_a_dfh_literal_is_found_and_an_ordinary_name_is_not():
    bad = "           EXEC CICS PUT CONTAINER('DFHXYZ') CHANNEL('ABC')\n"
    assert dfh_literals(bad) == ["'DFHXYZ'"]
    assert dfh_literals("           EXEC CICS MOVE CONTAINER('ALPHA') AS('BETA') CHANNEL(WS-CH)\n") == []
    assert dfh_literals("      * a comment about 'DFHTRANSACTION'\n") == []
    assert dfh_literals("           EXEC CICS DELETE CHANNEL(\"dfhevent\")\n") == ['"dfhevent"']
    # DFHRESP / DFHCOMMAREA are not quoted names
    assert dfh_literals("           IF EIBRESP = DFHRESP(NORMAL) MOVE DFHCOMMAREA TO X\n") == []


def test_the_channel_cases_name_no_dfh_channel_or_container():
    sources = _channel_case_sources()
    if not sources:
        pytest.skip("no ca-channel-* case in the cics-crucible checkout (CICS_CRUCIBLE_PATH)")
    offenders = {str(p): dfh_literals(p.read_text(encoding="utf-8")) for p in sources}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, f"a crucible channel case names a DFH literal (refused by name, X42): {offenders}"
