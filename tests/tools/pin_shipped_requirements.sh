#!/usr/bin/env bash
# Regenerate templates/requirements/*.txt (hash-pinned, #4918) from the .in files beside them.
# Bump the gitgalaxy pin in the .in files to the new release first. Needs `uv`.
# --universal + --python-version 3.10: one lockfile valid on every OS and every Python >= 3.10
# (action.yml's floor), so the same files serve GitHub, GitLab, Azure and Bitbucket.
set -euo pipefail
cd "$(dirname "$0")/../../templates/requirements"
for v in core yaml full; do
  { echo "# Hash-pinned install set for the shipped GitGalaxy CI surface (#4918). Do not edit by hand."
    echo "# Regenerate: tests/tools/pin_shipped_requirements.sh  (source: $v.in)"
    uv pip compile "$v.in" --generate-hashes --universal --python-version 3.10 --no-header -q
  } > "$v.txt.tmp"
  mv "$v.txt.tmp" "$v.txt"
done
echo "Lockfiles regenerated. Commit templates/requirements, then run: python tests/tools/stamp_template_pins.py"
echo "(stamps that commit + each file's sha256 into every template), and commit the stamped templates."
