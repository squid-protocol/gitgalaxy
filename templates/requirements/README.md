# Hash-pinned install sets for the shipped CI surface (#4918)

`core.txt` (gitgalaxy only), `yaml.txt` (`gitgalaxy[yaml]`), `full.txt` (`gitgalaxy[full]`: tiktoken,
xgboost, pandas, numpy). Each is a `uv pip compile --universal --generate-hashes` lockfile, valid on every
OS and Python >= 3.11, installed with `pip install --require-hashes -r`.

- `action.yml` reads them from `${GITHUB_ACTION_PATH}`; the default `version: latest` means "the pinned
  release this action ships with". An explicit `version` is exact-pinned but not hash-verified.
- The CI templates do NOT read this directory from the consumer's repo (it isn't there, and a remote GitLab
  component never has it). Each install step downloads `<set>.txt` from
  `raw.githubusercontent.com/squid-protocol/gitgalaxy/<GG_REF>/templates/requirements/`, verifies its sha256
  (`GG_SHA256`), then runs `pip install --require-hashes -r` on the verified file. `GG_REF` is a commit SHA,
  never a branch or tag.
- Bump: edit the version in `*.in`, run `tests/tools/pin_shipped_requirements.sh`, commit the lockfiles,
  then `python tests/tools/stamp_template_pins.py` (stamps that commit + sha256 into every template's
  `# gg-pin:<set>` marker line) and commit the templates. `test_shipped_pip_pins.py` fails on a stale marker.
