"""#3188: the Tier 4 data-shape fast-exit (wordlist / dictionary / bare-token data).

A file with almost no structural punctuation, made of single-token lines, is data. The fast-exit returns the
same `("undeterminable", 0.0)` the discovery scan would, without running it. These tests pin both sides: the
data shapes that skip the scan, and the near-misses (code, prose, short files) that must still reach it.
"""

import re
from typing import Any

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector

UNDETERMINABLE = ("undeterminable", 0.0)


class _Heuristics(dict):
    """lexical_heuristics that counts how often the discovery funnel asks for its families."""

    reads = 0

    def get(self, key: Any, default: Any = None) -> Any:
        if key == "lexical_families":
            self.reads += 1
        return super().get(key, default)


def _detector() -> LanguageDetector:
    langs = {
        "c": {
            "extensions": [".c"],
            "lexical_family": "standard_block",
            "rules": {"main": re.compile(r"int\s+main")},
        },
    }
    det = LanguageDetector(langs, {})
    det.thresholds = {"TIER_4_MIN_LINES": 20, "TIER_4_OUTLIER_MARGIN": 1.10, "PROSE_BASELINE_SIGNAL": 3.0}
    det.DISQUALIFIERS = {}
    det.lexical_heuristics = _Heuristics({"lexical_families": {"standard_block": {"delimiters": ["//", "/*"]}}})
    return det


def _run(content: str) -> tuple[tuple[str, float], int]:
    det = _detector()
    loc = len([ln for ln in content.splitlines() if ln.strip()])
    result = det._tier_4_heuristic_discovery(content, loc)
    return result, det.lexical_heuristics.reads


def _words(n: int, shape: str) -> list[str]:
    stems = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
    out = []
    for i in range(n):
        w = stems[i % len(stems)] + str(i)
        out.append(
            {"upper": w.upper(), "lower": w, "mixed": w.capitalize(), "apos": w + "'s", "hyphen": w + "-ed"}[shape]
        )
    return out


@pytest.mark.parametrize("shape", ["upper", "lower", "mixed", "apos", "hyphen"])
def test_wordlist_skips_the_discovery_scan(shape: str) -> None:
    result, reads = _run("\n".join(_words(400, shape)) + "\n")
    assert result == UNDETERMINABLE
    assert reads == 0


def test_crlf_wordlist_skips_the_discovery_scan() -> None:
    result, reads = _run("\r\n".join(_words(400, "lower")) + "\r\n")
    assert result == UNDETERMINABLE
    assert reads == 0


def test_min_lines_boundary() -> None:
    # Under the floor the funnel aborts before the data check (plaintext); at the floor the fast-exit answers.
    short, short_reads = _run("\n".join(_words(19, "lower")) + "\n")
    assert short == ("plaintext", 0.40)
    assert short_reads == 0
    at_floor, at_reads = _run("\n".join(_words(20, "lower")) + "\n")
    assert at_floor == UNDETERMINABLE
    assert at_reads == 0


def test_code_punctuation_density_reaches_the_funnel() -> None:
    # One structural character per single-token line is far above 1/50: this is not a wordlist.
    lines = [f"v{i}=f({i});" for i in range(100)]
    _, reads = _run("\n".join(lines) + "\n")
    assert reads == 1


def test_sparse_punctuation_still_counts_as_data() -> None:
    # Two structural characters in 200 lines is within the 1/50 allowance.
    lines = _words(200, "lower")
    lines[10] = "odd(word"
    result, reads = _run("\n".join(lines) + "\n")
    assert result == UNDETERMINABLE
    assert reads == 0


def test_multi_token_lines_reach_the_funnel() -> None:
    # Definition-list / prose lines: fewer than 85% of lines are a single token.
    lines = [f"word{i} means a thing" for i in range(100)]
    _, reads = _run("\n".join(lines) + "\n")
    assert reads == 1


def test_mostly_single_token_threshold() -> None:
    words = _words(100, "lower")
    # 85 single-token lines of 100 keeps the fast-exit; 80 of 100 does not.
    keep = words[:85] + [f"w{i} x" for i in range(15)]
    drop = words[:80] + [f"w{i} x" for i in range(20)]
    assert _run("\n".join(keep) + "\n")[1] == 0
    assert _run("\n".join(drop) + "\n")[1] == 1


def test_real_code_is_classified_as_before() -> None:
    code = "\n".join(f"// note {i}\nint main_{i}(void) {{ return {i}; }}" for i in range(30)) + "\n"
    result, reads = _run(code)
    assert reads == 1
    assert result[0] != "plaintext"
