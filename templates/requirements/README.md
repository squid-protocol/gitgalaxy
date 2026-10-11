# Hash-pinned install sets for the shipped CI surface (#4918)

`core.txt` (gitgalaxy only), `yaml.txt` (`gitgalaxy[yaml]`), `full.txt` (`gitgalaxy[full]`: tiktoken,
xgboost, pandas, numpy). Each is a `uv pip compile --universal --generate-hashes` lockfile, valid on every
OS and Python >= 3.10, installed with `pip install --require-hashes -r`.

- `action.yml` reads them from `${GITHUB_ACTION_PATH}`; the default `version: latest` means "the pinned
  release this action ships with". An explicit `version` is exact-pinned but not hash-verified.
- The CI templates under `templates/` expect this directory at `templates/requirements/` in the consumer's
  repo: copy it with the template (like `bitbucket_insights.py`).
- Bump: edit the version in `*.in`, run `tests/tools/pin_shipped_requirements.sh`.
