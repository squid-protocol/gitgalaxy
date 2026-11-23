# Review-layer controls: Sonnet vs Opus (#7155, part 3)

Status: **live run not made.** It calls models, so it goes through the experiment lane (Opus design, owner OK,
cost-vs-reward gate). Everything else is in place.

## Method
- Set: `tests/tools/review_controls.py`. Three hidden defects (a swallowed exception, a test that cannot fail, a
  green-by-skipping check), each with a clean twin that has the same paths, title and body.
- The reviewer sees only the title, description and diff (`review_experiment.py prompt KEY`), through `claude -p` with no tools.
- Scoring is deterministic, with no model in the loop. A hit names the defect's file and quotes its line. Any stray
  finding, or a blocked clean twin, is a false alarm. Unusable JSON from a call that answered is a miss. A call that
  produced no review is `errored` and is left out of every rate.
- Size (dry run): 6 diffs x 2 models x 3 repeats = 36 reviews, about 13.6k input tokens, short JSON output.

## To run (owner's OK required)
```
python tests/tools/review_experiment.py run --models sonnet,opus --repeats 3 --owner-ok --max-reviews 36 --out /tmp/gitgalaxy-scratch/claude/results.json
python tests/tools/review_experiment.py report /tmp/gitgalaxy-scratch/claude/results.json --markdown
```
Paste the table below. Keep the raw reviews outside the repo.

## Results
Not yet measured.

## Reading it
Three defects means every rate is a count with its n, not a percentage, and no verdict follows from it. The delta
between models is a prompt for a larger set, not a ranking. Repeats of the same diff measure a reviewer's variance, not
extra defects.
