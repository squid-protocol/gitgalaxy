# Bumping the keyword-rosetta pin (KEYWORD_ROSETTA_REF)

The `rosetta-audit` CI check (`.github/workflows/rosetta-audit.yml`, issue #2557) runs the
[keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta) control corpus's verifier —
all 46 language folders plus its baseline-gated n/a review audit — against every PR that touches
engine code, with the corpus checked out at the **`KEYWORD_ROSETTA_REF`** GitHub Actions
variable (a commit SHA or tag; falls back to `main` if unset). This is the cross-language
*consistency* twin of the crucible pin (`docs/self_scan/BUMPING_THE_CRUCIBLE_PIN.md`), and the
same principle applies: the pin makes the gate deterministic, and bumping it is a deliberate,
reviewed act — never a way to make a red check go away.

## When rosetta-audit fails on your PR

That is the gate working: your change shifts what the engine observes on the planted corpus
(or removes a signal rule nobody has ledgered). Decide which of these you are in:

1. **Unintentional regression** — fix the engine change. Do not touch the pin.
2. **Intentional, corpus-visible improvement** (a rule fix/addition, a stripper change): the
   expected values live in the corpus repo, so re-baseline there, then bump the pin here:

   1. In keyword-rosetta, open the re-baseline PR per its `docs/GATING.md`: manifest edits +
      a validated `deviation_ledger.json` entry (or `still_reproduces` flip) justifying every
      changed number — with the committed **`ENGINE_REF`** file set to `pull/<N>/head` for
      YOUR engine PR `N`, so its gates run against your unmerged build and go green now.
   3. Restore `ENGINE_REF` to `main` and merge the corpus PR (once your engine PR is approved).
   4. In your engine PR: update `KEYWORD_ROSETTA_REF` to the corpus repo's new main SHA —
      `gh api -X PATCH repos/squid-protocol/gitgalaxy/actions/variables/KEYWORD_ROSETTA_REF -f value=<sha>`
      (needs repo admin; in a review, request the maintainer do it) — and note the bump + the
      companion corpus PR in the PR body's **Cross-repo** section.
   5. `rosetta-audit` reruns green → merge.

3. **A new rule absence** (you nulled/removed a rule): `na_check --ci` fails until the corpus
   PR ships a validated ledger entry naming the language and signal — absence is either real
   morphology (ledger it) or a gap (don't ship it). Never regenerate `docs/na_baseline.json`
   to absorb an unreviewed cell.

## Invariants

- The variable always points at a keyword-rosetta commit whose gates pass against the engine
  `main` that existed when it was set (the brief corpus-ahead-of-engine window during step 2
  is covered by this gate's own pin).
- Never bump the pin and engine behavior in *unrelated* PRs simultaneously; the bump belongs
  to the PR whose behavior change it validates.
- The corpus repo's independence is the point: expected values and their audit trail
  (`deviation_ledger.json`) live there, under its gating rules — this repo only pins which
  snapshot it holds itself accountable to.
