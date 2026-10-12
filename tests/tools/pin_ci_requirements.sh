#!/usr/bin/env bash
# Regenerate ci/requirements/*.txt (hash-pinned, #4918 step 2) from the .in files beside them.
# These are the installs our OWN workflows and bitbucket-pipelines.yml use (the shipped templates have
# their own set in templates/requirements/, see pin_shipped_requirements.sh). Dependabot (pip, directory
# /ci/requirements) proposes bumps. Needs `uv`. --universal --python-version 3.10: one lockfile valid on
# every OS and every Python >= 3.10 in our matrices (pytest needs colorama on Windows only).
set -euo pipefail
cd "$(dirname "$0")/../../ci/requirements"
for f in *.in; do
  v="${f%.in}"
  { echo "# Hash-pinned install set for GitGalaxy's own CI (#4918). Do not edit by hand."
    echo "# Regenerate: tests/tools/pin_ci_requirements.sh  (source: $v.in)"
    uv pip compile "$v.in" --generate-hashes --universal --python-version 3.10 --no-header -q
  } > "$v.txt.tmp"
  mv "$v.txt.tmp" "$v.txt"
done
