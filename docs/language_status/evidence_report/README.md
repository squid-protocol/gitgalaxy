# Evidence reports (published on the `generated` branch)

The per-estate evidence report (a level per program, L0-L5) is derived output. It is **not committed on main**: the
Evidence Refresh workflow (`.github/workflows/evidence-refresh.yml`) re-renders it on every push to main and nightly and
publishes it to the `generated` branch, so one copy exists and it is the latest (#5206, after #4963).

- Read it: <https://github.com/squid-protocol/gitgalaxy/tree/generated/docs/language_status/evidence_report>
- From a checkout: `python tests/tools/generated_branch.py show docs/language_status/evidence_report/README.md` (the
  index), or `.../<estate>/report.md` / `report.json`.
- Tools that need the files on disk (`evidence_report.py --check|--refresh|--deltas`, `support_matrix.py`) fetch the
  published copy into this directory, which git ignores.
- Do not link a file in this directory from a doc on main: `tests/tools/test_evidence_report_single_source.py` fails on it.
  Link this README or the `generated` URL.
- The release gate (`evidence_report.py --check --live`, `publish.yml`) still requires every level to be current.
- Tests run on a frozen snapshot, `tests/fixtures/evidence_report/` (never quote it as current levels).

The estate roll-up (`tests/tools/estate_evidence.py`, #4054: the E0-E4 level of each evidence record, coverage and mutation
score, open survivors, lines) is published the same way, at `docs/language_status/estate_evidence/` on `generated`:
`python tests/tools/generated_branch.py show docs/language_status/estate_evidence/report.md` (or `report.json`).
