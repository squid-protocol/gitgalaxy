"""#8423: refuse new tests that judge elapsed wall-clock time via time.time() / time.perf_counter() / time.monotonic().

Loaded CI runners stall wall-clock timers and cause spurious red-main failures. New speed/linearity tests must use
the shared CPU-clock helper (or JVM ThreadMXBean CPU time for cobolrt) instead of raw wall-clock differences.
Existing offenders are listed in WALL_CLOCK_OFFENDERS (shrink-only: adding a new one or leaving a fixed one fails).
"""

from __future__ import annotations

import re
from pathlib import Path

from gitgalaxy.core.source_text import read_source

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "tests"

WALL_CLOCK_CALL = re.compile(r"\btime\.(?:time|perf_counter|monotonic)(?:_ns)?\(\)")

# Existing test files that take >= 2 wall-clock timestamps (a difference). Shrink-only (#8423).
WALL_CLOCK_OFFENDERS: frozenset[str] = frozenset({
    "tests/cobol_mainframe/test_pic_run_lengths_7169.py",
    "tests/cobol_mainframe/test_translator_pic_runs_7169.py",
    "tests/core_engine/test_api_db_sink_probe_4108.py",
    "tests/core_engine/test_cics_macro_level.py",
    "tests/core_engine/test_dense_source_7501.py",
    "tests/core_engine/test_dense_source_7504.py",
    "tests/core_engine/test_embedded_credentials_probe_4108.py",
    "tests/core_engine/test_global_env_mutation_probe_4108.py",
    "tests/core_engine/test_prefetch.py",
    "tests/core_engine/test_stego_imports_probe_4108.py",
    "tests/core_engine/test_vectorized_math_probe_4108.py",
    "tests/extraction/languages/test_c_kernel_vocab_8016.py",
    "tests/extraction/languages/test_calls_out_haskell_juxtaposition_6454.py",
    "tests/extraction/languages/test_calls_out_rust_matches_depth_6454.py",
    "tests/extraction/languages/test_calls_out_rust_select_arms_6454.py",
    "tests/extraction/languages/test_csharp_strict.py",
    "tests/extraction/languages/test_elixir_heredoc_imports_6572.py",
    "tests/extraction/languages/test_elixir_sigil_imports_6572.py",
    "tests/extraction/languages/test_elixir_string_imports_6572.py",
    "tests/extraction/languages/test_go_raw_string_imports_6572.py",
    "tests/extraction/languages/test_go_semicolon_imports_6572.py",
    "tests/extraction/languages/test_hlasm_macro_uses.py",
    "tests/extraction/languages/test_hlasm_strict.py",
    "tests/extraction/languages/test_perl_heredoc_imports_6572.py",
    "tests/security_auditing/test_redos_poison.py",
    "tests/security_auditing/test_secrets_shunt_4987.py",
    "tests/security_auditing/test_tls_bypass_dotnet_ps_wget_6239.py",
    "tests/security_auditing/test_tls_bypass_java_6239.py",
})


def _find_wall_clock_diff_tests() -> set[str]:
    found: set[str] = set()
    for path in TESTS.rglob("test_*.py"):
        if path == Path(__file__).resolve():
            continue
        text = read_source(path).text
        if len(WALL_CLOCK_CALL.findall(text)) >= 2:
            found.add(path.relative_to(REPO).as_posix())
    return found


def test_no_new_raw_wall_clock_timing_tests():
    actual = _find_wall_clock_diff_tests()
    unexpected = sorted(actual - WALL_CLOCK_OFFENDERS)
    if unexpected:
        raise AssertionError(
            "New test(s) take wall-clock time differences (use CPU time / shared helper instead, #8423):\n"
            + "\n".join(f"  - {p}" for p in unexpected)
        )
    stale = sorted(WALL_CLOCK_OFFENDERS - actual)
    if stale:
        raise AssertionError(
            "Fixed/removed wall-clock offender(s) still listed in WALL_CLOCK_OFFENDERS (shrink the list, #8423):\n"
            + "\n".join(f"  - {p}" for p in stale)
        )
