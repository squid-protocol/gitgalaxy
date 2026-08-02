#!/usr/bin/env python3
"""
The ONLY sanctioned way to update tests/golden_master_audit.json or
tests/golden_master_zero_dep_audit.json (#330).

golden_diff.py failing means GitGalaxy's output actually changed. That's
either a bug (fix the engine, don't touch this file) or an intentional
improvement (regenerate the fixture -- but deliberately, not by reflexively
copying new output over the old baseline). This script exists so that
second case always goes through one clearly-named, auditable path instead
of `cp new_output.json golden_master.json`, and so the person running it
sees exactly what they're about to bless before it happens.

Usage:
    python tests/tools/update_golden_master.py [--yes]

Requires the language-crucible corpus checked out locally (same resolution
as tests/test_golden_crucible.py): set LANGUAGE_CRUCIBLE_PATH, or have it
as a sibling directory of this repo checkout.

Updates whichever fixture matches the CURRENT environment (full-precision
if networkx/tiktoken/pandas/xgboost are installed, zero-dependency-mode
otherwise) -- run it once per mode if both fixtures need updating.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import golden_diff

from gitgalaxy.galaxyscope import HAS_NETWORKX, HAS_PYYAML, HAS_TIKTOKEN
from gitgalaxy.security.security_auditor import ML_AVAILABLE

REPO_ROOT = Path(__file__).parent.parent.parent
CRUCIBLE_DATA_PATH = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible")) / "data"


def zero_dependency_mode() -> bool:
    return not (HAS_NETWORKX and HAS_TIKTOKEN and ML_AVAILABLE and HAS_PYYAML)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt (the diff summary is still printed either way).",
    )
    args = parser.parse_args()

    if not CRUCIBLE_DATA_PATH.exists():
        print(f"❌ language-crucible corpus not found at {CRUCIBLE_DATA_PATH}.")
        print("   Clone squid-protocol/language-crucible (pinned to v1.0) as a sibling directory,")
        print("   or set LANGUAGE_CRUCIBLE_PATH, then re-run.")
        sys.exit(1)

    zero_dep = zero_dependency_mode()
    mode_name = "zero-dependency" if zero_dep else "full-precision"
    golden_master_path = REPO_ROOT / (
        "tests/golden_master_zero_dep_audit.json" if zero_dep else "tests/golden_master_audit.json"
    )

    print(f"=== Regenerating {golden_master_path.name} ({mode_name} mode) ===\n")

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "telemetry_out"
        output_dir.mkdir()

        print(f"Running galaxyscope against {CRUCIBLE_DATA_PATH}...")
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

        new_output_path = output_dir / "data_galaxy_audit.json"
        if not new_output_path.exists():
            print(f"❌ galaxyscope did not produce the expected artifact at {new_output_path}")
            sys.exit(1)

        old_data = golden_diff.load_and_sanitize(str(golden_master_path)) if golden_master_path.exists() else {}
        new_data = golden_diff.load_and_sanitize(str(new_output_path))

        if golden_master_path.exists() and golden_diff.generate_deterministic_hash(
            old_data
        ) == golden_diff.generate_deterministic_hash(new_data):
            print(f"\n✅ No drift detected -- {golden_master_path.name} already matches current output. Nothing to do.")
            return

        diffs = golden_diff.deep_compare(old_data, new_data)
        print(f"\n--- {len(diffs)} difference(s) about to be baked into {golden_master_path.name} ---\n")
        for diff in diffs[:50]:
            print(diff)
        if len(diffs) > 50:
            print(f"... and {len(diffs) - 50} more.")

        if not args.yes:
            answer = input(
                f"\nBless this as the new {mode_name} golden master? This will overwrite "
                f"{golden_master_path.relative_to(REPO_ROOT)}. [y/N] "
            )
            if answer.strip().lower() != "y":
                print("Aborted -- golden master left unchanged.")
                sys.exit(1)

        golden_master_path.write_bytes(new_output_path.read_bytes())

    print(f"\n✅ Updated {golden_master_path.relative_to(REPO_ROOT)}.")
    print("   Commit it as part of this PR, and explain in the PR description WHY the output")
    print('   changed (e.g. "improved X parser, now correctly detects Y") -- see CONTRIBUTING.md.')


if __name__ == "__main__":
    main()
