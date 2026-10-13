## Keeping this page true

- **A new model** (a stub, a shim, an LE service) adds its entry here in the same PR, with its status.
- **A refusal or a declared difference** found in the code (`not modelled`, `Unsupported`, `UnsupportedOption`) has
  an entry here.
- **A change of status** (a z/OS run, a new flag) edits the entry and its date. The summary table follows (it is generated from the entries' front matter).
- **How.** This page is generated; do not edit it. Each entry is one file, `docs/language_status/register/<ID>.md`
  (front matter: id, family, status, title, area, summary, reached; then the entry text). Take a new ID with
  `python tests/tools/register.py next <family>` when the issue is filed, so parallel PRs never pick the same number
  (`new <ID>` writes a skeleton). Prose sections live in `register/_parts/`, the page order in `register/_layout.json`.
  Commit the entry file only: this page is not committed (#5057). A PR's CI renders it (it must render, the same way
  twice) and shows the diff; after merge it is published to the `generated` branch. `python tests/tools/register.py
  render` writes a local copy to read.
