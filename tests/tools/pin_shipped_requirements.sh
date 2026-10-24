#!/usr/bin/env bash
# Regenerate templates/requirements/*.txt (hash-pinned, #4918) from the .in files beside them.
# Bump the gitgalaxy pin in the .in files to the new release first. Needs `uv`.
# --universal + --python-version 3.11: one lockfile valid on every OS and every Python >= 3.11
# (action.yml's floor), so the same files serve GitHub, GitLab, Azure and Bitbucket.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$HERE/pin_requirements.py" --target templates "$@"
echo "Lockfiles regenerated. Commit templates/requirements, then run: python tests/tools/stamp_template_pins.py"
echo "(stamps that commit + each file's sha256 into every template), and commit the stamped templates."
