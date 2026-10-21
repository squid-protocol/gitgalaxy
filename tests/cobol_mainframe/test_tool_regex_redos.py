"""#3214: the ReDoS scaling sweep over the refraction tools' regexes.

A failure in test_no_new_offenders names the pattern, the payload that slows it
and the measured cost. Bound the pattern (see #3205's fix in cobol_jcl_forge.py);
baseline it with `python tests/tools/tool_regex_redos.py --update-baseline` only
with a note saying why its real input is short.
"""

import re
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tool_regex_redos as tr  # noqa: E402


WINDOWS_TIMER = pytest.mark.skipif(
    sys.platform == "win32",
    reason="growth-ratio verdicts near the threshold need a fine CPU timer; Windows' is coarse (#4836). Regex "
    "complexity is the same CPython engine on every OS, so Linux/macOS measure it",
)


def _measure_catching(pattern, flags, method, attempts=3):
    """The first offending verdict in `attempts` measurements, else the last one.

    Timing noise (a descheduled or throttled runner) only ever lowers a pattern's measured growth below the
    threshold, never raises a linear one above it, so retrying the measurement cannot turn a clean pattern
    into an offender; the assertion on the verdict is unchanged (#5166)."""
    for _ in range(attempts):
        verdict = tr.measure(pattern, flags, method)
        if verdict["offender"]:
            break
    return verdict


@pytest.mark.slow(reason="times a regex against a growing payload (13.0s on a CI runner, limit 15s)")
def test_catches_the_3205_pattern():
    """The pre-fix cobol_jcl_forge.py pattern the sweep exists to catch."""
    verdict = _measure_catching(r"EXEC\s+CICS.*?END-EXEC\.", re.IGNORECASE, "findall")
    assert verdict["offender"], verdict
    assert verdict["unit"].upper().startswith("EXEC CICS")


@WINDOWS_TIMER
def test_catches_a_mild_quadratic_by_growth():
    """Under the slow threshold at 40k chars, but ~16x for 4x the input."""
    pattern = r"SELECT\s+([A-Z0-9\-]+)\s+ASSIGN\s+(?:TO\s+)?([A-Z0-9\-]+)[^.]*\."
    verdict = tr.measure(pattern, re.IGNORECASE, "findall")
    assert verdict["offender"], verdict


@WINDOWS_TIMER
def test_bounded_heavy_linear_pattern_is_not_an_offender():
    """The shipped CICS HANDLE scan: `.{0,600}?` is costly per start but linear."""
    pattern = r"\bEXEC\s+CICS\s+HANDLE\s+(?:ABEND|CONDITION|AID)\b(.{0,600}?)\bEND-EXEC"
    assert not tr.measure(pattern, re.S, "findall")["offender"]


def test_match_is_measured_at_position_zero_only():
    """`\\s*X` is quadratic under findall over blanks but linear under match."""
    assert not tr.measure(r"\s*X", 0, "match")["offender"]


def test_a_hung_pattern_times_out_as_an_offender():
    rows = tr.sweep([tr.Site("demo.py", r"(A+)+B", 0, [1], {"findall"})], timeout=3.0)
    assert rows[0]["offender"] and rows[0]["reason"].startswith("timeout")


def test_a_sharded_sweep_returns_the_serial_rows_in_order():
    """#5166: `workers` only changes how the sites are dealt out, never a row or its place."""
    sites = [tr.Site("demo.py", pat, 0, [i], {"match"}) for i, pat in enumerate((r"A", r"B+", r"\s*X", r"C|D", r"E"))]
    serial = tr.sweep(sites)
    for workers in (2, 3, 9):
        sharded = tr.sweep(sites, workers=workers)
        assert [(r["lines"], r["pattern"], r["offender"]) for r in sharded] == [
            (r["lines"], r["pattern"], r["offender"]) for r in serial
        ]
    assert [r["pattern"] for r in serial] == [s.pattern for s in sites]


def test_payload_units_include_keyword_prefixes():
    units = tr.payload_units(r"EXEC\s+CICS\s+[A-Z]+\s+END-EXEC", 0)
    assert "EXEC CICS " in units and "EXEC X CICS X " in units


def test_collects_calls_compiled_globals_and_fstrings():
    sites, skipped = tr.collect()
    by_module = {}
    for s in sites:
        by_module.setdefault(s.module.rsplit("/", 1)[-1], []).append(s)
    # a literal re.finditer call, measured with its own method
    # (#3420: the OPEN anchor starts with the hyphen-aware `(?<![A-Z0-9\-])` guard)
    dag = [s for s in by_module["cobol_dag_architect.py"] if r"OPEN\s+(?=" in s.pattern]
    assert dag and dag[0].method == "finditer"
    # module-level compiled patterns built from f-strings over module constants
    assert any("SECTION" in s.pattern for s in by_module["cobol_graveyard_finder.py"])
    assert len(sites) >= 50
    assert all(s["why"] for s in skipped)


@WINDOWS_TIMER
def test_no_new_offenders():
    """Every pattern outside the baseline stays linear. Baselined offenders are not
    re-measured here (the CLI does that, and reports any that stopped reproducing)."""
    baseline = {tr._bkey(b) for b in tr.load_baseline()}
    sites, _ = tr.collect()
    rows = tr.sweep([s for s in sites if s.key not in baseline], workers=4)  # #5166
    new = [f"{r['module']}:{r['lines']} {r['pattern']!r}: {r['reason']} ({r['unit']!r})" for r in rows if r["offender"]]
    assert not new, "new ReDoS offenders in the refraction tools:\n" + "\n".join(new)


def test_baseline_entries_carry_a_note():
    for entry in tr.load_baseline():
        assert entry.get("note"), entry["pattern"]
