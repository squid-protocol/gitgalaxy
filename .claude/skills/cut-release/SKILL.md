---
name: cut-release
description: Cut and publish a GitGalaxy release (a vX.Y.Z tag -> PyPI + GitLab / Bitbucket / Azure mirrors). Covers the version source (the tag; there is no version file), what a tag push starts, the preflight that must pass BEFORE tagging (the evidence report must be current at the tagged commit, or publish.yml stops before PyPI), checking that the evidence-refresh bot PR is not stuck, the safe order (tag, watch PyPI, then publish the release page), drafting the note cheaply on a large release, and what to do when publish fails. Use when the owner says "release", "version bump", "cut vX.Y.Z", "publish to PyPI", or a publish.yml run failed.
---

Release notes' tone and template: the `release-notes` skill and `docs/how_to_write_release_notes.md`. This skill is
the mechanics. Learned on v2.12.0 (2026-11-04): its GitHub release went public, but publish.yml stopped at its first
job, so the package never reached PyPI. Preflight step 1 below would have caught it.

## How a release works

- **The version is the tag.** `pyproject.toml` has `dynamic = ["version"]` with `[tool.setuptools_scm]`, so there is
  no file to bump. Pushing `vX.Y.Z` on a main commit is the release.
- **A `v*` tag push starts three workflows:**
  - `.github/workflows/publish.yml`: `evidence-report-current` runs
    `python tests/tools/evidence_report.py --check --live`, and only if it passes does the rest run: `pypi-publish`
    (refuses a tag that is not on main) and then the GitLab, Bitbucket and Azure syncs, which force-push main and
    prune tags.
  - `.github/workflows/full-suite-gate.yml`
  - `.github/workflows/os-smoke-grid.yml`
- **What can be undone:** a PyPI version can never be re-uploaded or replaced. A tag that never reached PyPI or the
  mirrors (publish failed at its first job) affects nothing but the GitHub page.
- **The PyPI summary** is `pyproject.toml`'s `description`, and it changes only with a release. The GitHub About
  line and topics are separate (`gh repo edit`).

## Preflight: before tagging

1. **The evidence report must be current at the commit you will tag.** Run publish's own check there, in a clean
   worktree of that commit: `python tests/tools/evidence_report.py --check --live`.
   - It fails with `stale level: ... L4*` and `not current: docs/language_status/evidence_report/...` when a
     harness or oracle change landed after the last refresh merged.
   - If it fails, do not tag. Go to step 2.
2. **The evidence-refresh bot PR must not be stuck.** The refresh reaches main only through the bot PR on branch
   `auto/evidence-refresh-full` (auto-merge on):
   `gh pr list --state all --search "head:auto/evidence-refresh-full" -L 5`
   - Normally one merges a day. One open for more than a day means its refresh is not landing, however green the
     Evidence Refresh runs look: read the bot PR's failing checks, not the refresh run's conclusion.
   - **Known failure (fixed in #7718):** the `det` / `detmut` check printing
     `det mutation: <case>: this run judged N mutants and replaces one that judged M`.
     That was the stale-check guard refusing ledgers that only lost mutants the moved port no longer has. If it
     comes back, compare the two entries
     (`git show origin/main:tests/equivalence/det_mutation/<case>.json` against the bot branch): a lost mutant still
     in the new entry's `every` is a narrower run, which is a real regression. One that is gone from `every` is not.
   - After a fix merges, the bot PR needs a new merge commit for its checks to run the new code
     (`gh pr update-branch <n>`, or the next refresh run). Re-running its old checks reuses the old merge commit.
3. **Main is healthy:** the last smoke-test run on main that was not cancelled passed, and so did the last nightly
   full-suite-gate: `gh run list -w smoke-test.yml -b main -L 5` and `gh run list -w full-suite-gate.yml -L 3`.
4. **Pick the commit:** the evidence bot PR's merge commit, or a main commit soon after it with no harness or oracle
   change in between. Main moves dozens of times a day, and the next harness change makes the report stale again.

## Order: tag first, release page last

1. Draft the note (below). Keep it as a GitHub draft release, or as a file:
   `gh release create vX.Y.Z --draft --target <sha> --notes-file notes.md`. A draft creates no tag and starts
   nothing.
2. Push the tag yourself: `git tag -a vX.Y.Z <sha> -m vX.Y.Z && git push origin vX.Y.Z`.
3. Watch `gh run list -w publish.yml -L 1` until `pypi-publish` succeeds. Check that PyPI lists the version:
   `curl -s https://pypi.org/pypi/gitgalaxy/json`, the `info.version` field.
4. Only then publish the GitHub release (`gh release edit vX.Y.Z --draft=false`). Publishing the draft first
   creates the tag and starts the same run, but the release page is then public before anyone knows whether PyPI
   will get the package.

GitHub gives a draft a new `untagged-...` URL on every edit. Check there is only one draft with
`gh api repos/squid-protocol/gitgalaxy/releases --jq '.[]|select(.draft)|.html_url'`.

## When publish fails

- **At `evidence-report-current`:** PyPI and the mirrors were skipped, so nothing went out and nothing needs
  retracting.
  - Re-running the workflow does not help: it checks the tagged commit, whose report is fixed.
  - Fix the refresh (preflight step 2), then release the next patch version from a commit where step 1 passes.
  - If the release page is already public, add one line to it saying which version brings the PyPI package.
  - Never skip or edit out the check: it is the rule that no package ships with evidence the repo marks out of
    date (#4703).
- **At `pypi-publish` or a mirror sync:** read that job's log before anything else. A version PyPI accepted cannot
  be uploaded again: fix forward with the next patch version.

## Drafting the note on a large release

- **Do not read the whole log on a big release.** v2.11.0 to v2.12.0 was about 2,870 commits; reading them burns
  tokens for little gain. Start from the themes the owner names, then ground each one cheaply:
  `git log <prev>..origin/main --oneline -i -E --grep=<theme>` gives counts and PR numbers.
- **Numbers come from generated files, not from memory:**
  - `git show origin/generated:docs/language_status/progress.md` for the ladder by estate (L0-L5 counts, "L4+")
    and the capability ledger (CICS commands modelled and refused, options, Db2, LE).
  - `docs/language_status/evidence_report/<estate>/report.json` on `generated` for per-program levels, via
    `programs[].level` and `programs[].program`.
  - The previous release's note for the before-and-after.
- **Study links** come from `mkdocs.yml` (`site_url` plus the Museum of Code nav entries). Check each link returns
  200 before publishing.
- **Upgrading section:** diff `pyproject.toml` against the previous tag
  (`git diff <prev> origin/main -- pyproject.toml`) for `requires-python`, the extras and `[project.scripts]`. Say
  plainly what was not checked, such as removed CLI flags or output-schema changes.
- **Wording:** report evidence levels with counts, never "verified" or "proven"
  (`.claude/rules/mainframe-evidence-policy.md`). Keep the limitations beat: the oracle is GnuCOBOL plus IBM-doc
  models, not z/OS; L5 audit status; and the burned estates were used to develop the translator.
- **Top of the note:** a plain-language "In short", then one line on the release's size and why. Put readable
  material (studies) before specialist detail (CICS counts). Fold long program lists into `<details>`.

## Cadence

Release every week or two, so each note can be written from the real change list. Five weeks without a release
made v2.12.0 a 2,870-commit note, and its stuck evidence refresh was found only at publish time.
