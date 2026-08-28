"""
Golden Crucible regression test (#329).

Pytest-native replacement for what used to be a bare CI shell invocation of
golden_diff.py. Runs the real `galaxyscope` CLI entry point against the
language-crucible corpus and diffs the result against the committed golden
master fixture that matches whatever engines happen to be installed in the
current environment (full-precision vs Zero-Dependency Mode).

Opt-in via the `golden_crucible` marker (excluded from the default
`pytest tests/` run, see pyproject.toml's addopts) because it needs the
language-crucible corpus checked out locally and takes real wall-clock time
-- CI invokes it explicitly with `pytest -m golden_crucible`.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.galaxyscope import HAS_NETWORKX, HAS_PYYAML, HAS_TIKTOKEN
from gitgalaxy.security.security_auditor import ML_AVAILABLE

sys.path.insert(0, str(Path(__file__).parent))
import golden_diff
from _crucible_pin import PINNED_TAG

pytestmark = pytest.mark.golden_crucible

REPO_ROOT = Path(__file__).parent.parent
CRUCIBLE_DATA_PATH = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible")) / "data"


def _zero_dependency_mode() -> bool:
    # Same condition galaxyscope.py itself uses to decide which mode it ran in.
    return not (HAS_NETWORKX and HAS_TIKTOKEN and ML_AVAILABLE and HAS_PYYAML)


@pytest.mark.skipif(
    not CRUCIBLE_DATA_PATH.exists(),
    reason=(
        f"language-crucible corpus not found at {CRUCIBLE_DATA_PATH} -- clone "
        f"squid-protocol/language-crucible (pinned to {PINNED_TAG}) as a sibling directory, "
        "or set LANGUAGE_CRUCIBLE_PATH, to run this test."
    ),
)
def test_golden_crucible_matches_baseline(tmp_path):
    zero_dep = _zero_dependency_mode()
    golden_master_path = REPO_ROOT / (
        "tests/golden_master_zero_dep_audit.json" if zero_dep else "tests/golden_master_audit.json"
    )

    output_dir = tmp_path / "telemetry_out"
    output_dir.mkdir()

    subprocess.run(
        [
            "galaxyscope",
            str(CRUCIBLE_DATA_PATH),
            "--output",
            str(output_dir) + os.sep,
            "--file-speed",
            "--splicing-speed",
        ],
        check=True,
        timeout=180,
        env={**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"},
    )

    actual_path = output_dir / "data_galaxy_audit.json"
    assert actual_path.exists(), f"galaxyscope did not produce the expected artifact at {actual_path}"

    golden_data = golden_diff.load_and_sanitize(str(golden_master_path))
    actual_data = golden_diff.load_and_sanitize(str(actual_path))

    if golden_diff.generate_deterministic_hash(golden_data) == golden_diff.generate_deterministic_hash(actual_data):
        return

    diffs = golden_diff.deep_compare(golden_data, actual_data)
    if not diffs:
        # Hash mismatched but every leaf compared equal under tolerance --
        # e.g. sub-epsilon float noise the hash-time rounding didn't fully absorb.
        return

    message = (
        f"Structural drift detected against {golden_master_path.name} "
        f"({len(diffs)} difference{'s' if len(diffs) != 1 else ''}):\n"
    )
    message += "\n".join(diffs[:50])
    if len(diffs) > 50:
        message += f"\n... and {len(diffs) - 50} more."
    message += "\n\nIf this change is intentional (e.g. you improved a parser), regenerate the golden master."
    pytest.fail(message, pytrace=False)
