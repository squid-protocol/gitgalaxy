#!/usr/bin/env bash
# Regenerate ci/requirements/*.txt (hash-pinned, #4918 step 2) from the .in files beside them.
# These are the installs our OWN workflows and bitbucket-pipelines.yml use (the shipped templates have
# their own set in templates/requirements/, see pin_shipped_requirements.sh). Dependabot (pip, directory
# /ci/requirements) proposes bumps. Needs `uv`. --universal --python-version 3.11: one lockfile valid on
# every OS and every Python >= 3.11 in our matrices (pytest needs colorama on Windows only).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" "$HERE/pin_requirements.py" --target ci "$@"
