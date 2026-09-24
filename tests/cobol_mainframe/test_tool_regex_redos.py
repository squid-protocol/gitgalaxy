"""#3214: the ReDoS scaling sweep over the refraction tools' regexes.

A failure in test_no_new_offenders names the pattern, the payload that slows it
and the measured cost. Bound the pattern (see #3205's fix in cobol_jcl_forge.py);
baseline it with `python tests/tools/tool_regex_redos.py --update-baseline` only
with a note saying why its real input is short.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tool_regex_redos as tr  # noqa: E402


def test_catches_the_3205_pattern():
    """The pre-fix cobol_jcl_forge.py pattern the sweep exists to catch."""
    verdict = tr.measure(r"EXEC\s+CICS.*?END-EXEC\.", re.IGNORECASE, "findall")
    assert verdict["offender"], verdict
    assert verdict["unit"].upper().startswith("EXEC CICS")


def test_catches_a_mild_quadratic_by_growth():
    """Under the slow threshold at 40k chars, but ~16x for 4x the input."""
    pattern = r"SELECT\s+([A-Z0-9\-]+)\s+ASSIGN\s+(?:TO\s+)?([A-Z0-9\-]+)[^.]*\."
    verdict = tr.measure(pattern, re.IGNORECASE, "findall")
    assert verdict["offender"], verdict


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


def test_no_new_offenders():
    """Every pattern outside the baseline stays linear. Baselined offenders are not
    re-measured here (the CLI does that, and reports any that stopped reproducing)."""
    baseline = {tr._bkey(b) for b in tr.load_baseline()}
    sites, _ = tr.collect()
    rows = tr.sweep([s for s in sites if s.key not in baseline])
    new = [f"{r['module']}:{r['lines']} {r['pattern']!r}: {r['reason']} ({r['unit']!r})" for r in rows if r["offender"]]
    assert not new, "new ReDoS offenders in the refraction tools:\n" + "\n".join(new)


def test_baseline_entries_carry_a_note():
    for entry in tr.load_baseline():
        assert entry.get("note"), entry["pattern"]
