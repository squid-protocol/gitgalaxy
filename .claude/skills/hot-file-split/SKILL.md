---
name: hot-file-split
description: Split a file that serializes agent work into family modules without changing behaviour -- pick the seam from the commits, move the text by script, turn an edit-every-time chain into a registry, prove nothing changed with a check that can fail, and clear the filename-keyed gates a split breaks. Use for the weekly conflict job (#7444) or any "split this hot file" work.
---

churn's plan holds are per file, so two slices that edit one file run one at a time even when their lines are far apart.
A split only helps if the next slice no longer edits the host. #5274 is the worked example: #7436 (harness), #7439 (det
translator), #7441 (C stub), #7443 (tests).

## 1. Pick the seam from the commits

`churn rsi conflicts` gives holds, commits and the functions that took the edits. Read what those commits did.

- **Moving text nobody edits helps nobody.** Move what slices edit.
- **A chain every slice edits needs a registry, not a shorter chain.** `_translate_command` was an `if` per command, so
  moving bodies out would still have edited it each time. Each family now answers through its own function, or `None`
  for "not mine", and the host is a loop.
- **File-level holds mean a nearby function still collides.** Plan features that are not command families (a new
  `case.json` option) need their own seam.
- **Say so if a split will not help.** Holds on docs and data files are a scheduling problem.

## 2. Move by script, never by hand

Extract from the AST in the original order, so code moves verbatim and the only rewrites are helper prefixes. Print each
block's assigned family and read the list before writing: a substring rule put HANDLE (whose test mentions `"ABEND"`) in
the wrong family. Snapshot the old tree first with `git archive origin/main <dir>`.

**Order is behaviour.** A chain's order decides which rule refuses a command naming two forms. Keep the old order, find
the overlaps, and say which matter in a comment and a test. A catch-all (`if "COUNTER" in opts: raise`) must stay ahead
of every family it covers.

Use the repo's patterns: `ec.<helper>` late binding for harness modules (a family imports the host), `det/cics_common.py`
for det shared helpers (no import back from `cics.py`). Give each mixin a uniquely named method: a shared name is
CodeQL's `py/conflicting-attributes`. Keep public names reachable through the host's alias table.

## 3. Prove it, with a control

Pick the strongest proof the file allows, and put the numbers in the PR body.

| File kind | Proof |
|---|---|
| C in one translation unit | Cut contiguous runs in place, leaving an `#include` where each sat; `gcc -E -P` before and after is byte-identical |
| Translator or generator | Old against new on all real inputs plus generated malformed and option-clashing ones, comparing output and the refusal's type and message |
| Translator output | `det_survey.py --no-compile` on both trees; every port byte-identical |
| Test file | Collected test ids identical before and after |

**A proof that cannot fail proves nothing.** Break it on purpose (move a family in the registry) and report how many
differences that gives. Rerun the proof after every later edit: lint fixes come last and are where mistakes land. Then run
a real case (`cics_crucible.py --offline --cases <case> --sides cobol-stub`), because Docker's GnuCOBOL is on the box even
though `cobc` is not on the path.

## 4. Clear what is keyed on the filename

A split breaks things that name the old file. Each of these went wrong once:

- **Path filters.** `cics-crucible.yml` named only `equivalence_cics.py`, so a family-only edit skipped the gate. Grep
  `.github/` for the file and use a glob. Pin it with a test.
- **Evidence and trial inputs.** `tests/tools/evidence.py` (`HARNESS`, `COMPONENTS`), `tests/tools/trial.py`, and the
  pairs in `test_evidence_components.py`. A module missing here does not mark proofs stale when it changes.
- **Allowed-importer lists.** `tests/core_engine/test_cics_spec.py::IMPORTERS`.
- **Timing keys.** `tests/equivalence_e2e_durations.json` is keyed by test id. Rename the keys when tests move.
- **Tests and tools that read source as text.** Grep for `read_text` and `getsource`; splice the family files back in
  rather than weakening the check. `capability_ledger.py` reads det sources too.
- **Prose.** The register entries and skills that cite the file.
- **The pre-gate's entropy check.** It reads the first 8 KB of each file. A format string that sat deep in a big file
  lands in that window in a small one, and a literal scoring over 4.8 blocks CI. Shorten the literal with a local.
  Do not allowlist it.

## 5. Tooling traps

- Run `ruff` on the files you changed, never a directory or a broad glob: it edited unrelated files twice.
- Rename before removing unused imports, or the fixer drops the import you are about to need.
- `F821` is the check that catches a lost import. The old-against-new proof catches the rest.
- `mypy` needs a `TYPE_CHECKING` declaration in a mixin; give a stub a docstring body, as `...` is CodeQL's
  `py/ineffectual-statement`.
- Do not end two PRs by appending to the same test file: put a new test beside its family.
- A failed check on a cancelled run is not a test failure. Read the run's conclusion first.

## 6. The PR

Read `docs/factory_bottlenecks.md` first, and add an entry when the PR lands.

One file per PR, behaviour-preserving, no golden or evidence changes. In the body: why (holds, commits), what moved, the
proof and its control, and what was not run locally.
