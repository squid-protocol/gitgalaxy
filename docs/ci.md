# CI: labels that merge a pull request

For maintainers. A label on a pull request tells the CI shepherd what to do with it. You set a **request** label; the
bot sets the **status** labels and posts at most one digest comment per head. Nothing merges unless the required
checks on `main` are green.

## Request labels (maintainers with write access set these)

| Label | What it does |
|---|---|
| `shepherd:merge` | Marks the PR ready and turns on auto-merge (squash). GitHub merges it when the required checks pass. |
| `shepherd:hold` | Never auto-merge. Wins over `shepherd:merge`. |
| `shepherd:matrix` | Runs the full OS x Python matrix (`full-suite-gate.yml`) on the PR's head. Auto-merge stays off until a green run exists for that head. Same-repo branches only; for a fork, run the matrix by hand. |
| `shepherd:full` | The det sweep plans a full sweep instead of narrowing it to the changed cases: the shepherd reruns the latest sweep, which reads the label when it plans. (Label changes do not start the det sweep by themselves.) |

A label added by someone without write access is removed by the bot, with a comment.

**A label is bound to the head it was approved on.** When a maintainer with write access adds `shepherd:merge`, the
bot's own account writes an approval marker naming the head that was labelled (from the event). Only the bot's
markers count; anyone can post a comment. If the head later moves (new commits, a force-push), the label is removed,
whatever noticed. The one exception is the bot's own `gh pr update-branch` (behind main): the bot leaves a marker pair
before and after it, and the approval carries over only through that pair and a first-parent check. With no approval
marker yet (the labelled run did not happen, or was dropped), the bot does nothing and says so in its log: re-add the
label.

A label added by someone without write access is removed by the bot, with a comment.

**A label is bound to the head it was added on.** GitHub's timeline records who added `shepherd:merge` and on
which commit. If the head has moved since (new commits, a force-push), the label is removed, whatever event noticed:
push, then re-add the label. The one exception is the bot's own `gh pr update-branch` (behind main): the bot leaves a
marker pair before and after it, and the label carries over only through that pair.

A label added by someone without write access is removed too, on any pass (the timeline names the labeler).

## Status labels (the bot sets and clears these)

| Label | Meaning | What you do |
|---|---|---|
| `shepherd:needs-fix` | A real failure, a merge conflict or a red matrix on this head. One digest comment says what failed and the local command that reproduces it. | Fix it, push. |
| `shepherd:waiting-on-main` | The failing check fails on `main` too. | Nothing on this PR; main's owner fixes it. |
| `shepherd:retrying` | An infra or flake failure is being rerun (up to 3 times, 15 minutes apart). | Nothing; wait. |

Status labels are cleared when no request label is left.

## Other rules

- **Depends on #N.** A PR whose body says `Depends on #N` does not auto-merge until #N is merged.
- **Behind main.** A labelled PR that is behind and green gets `gh pr update-branch` from the bot.
- **Infra reruns.** Only a failed job of an infra or flake kind is rerun, and only three times per run.
- **Permissions.** The request labels are honoured only from collaborators with `write`, `maintain` or `admin`.

## Where the logic runs

- `.github/workflows/shepherd-event.yml`: a label added or removed, or new commits (`pull_request_target`).
- `.github/workflows/shepherd-reconcile.yml`: after PR CI finishes, every 20 minutes, or by hand.
- `tests/tools/shepherd_gh.py`: the rules (`decide()` is pure and tested in `tests/tools/test_shepherd_gh.py`).
- Triage and the digest: `tests/tools/ci_digest.py`. Readiness: `tests/tools/pr_check.py`.

Both workflows check out `main` only and never run pull-request code. They use the `AUTOMATION_PAT` secret
(fine-grained, this repository only: contents, pull requests, issues, actions).

To create or refresh the label set (idempotent), run the reconcile workflow by hand with `ensure_labels: true`.

## Fallback

The local shepherd still works from a maintainer's checkout:
`python tests/tools/box/ci_shepherd.py add N` (see its docstring). Use it if the workflows are down.

## Main is red (main-watch)

`.github/workflows/main-watch.yml` opens one `ci-red-main` issue per workflow that fails on main and closes it when
the workflow next succeeds. Rules live in `tests/tools/main_watch.py` (`decide()` is pure, tested in
`tests/tools/test_main_watch.py`). A run created with the repo `GITHUB_TOKEN` raises no `workflow_run` event (#4859),
so `post-merge.yml` dispatches the Full Suite Gate with `AUTOMATION_PAT` (needs `actions: write`), and an hourly
`reconcile` job reads the latest completed non-cancelled run of each open issue's workflow and comments or closes, so
a dropped event is picked up within the hour. A failure caused only by cancelled legs says so in the comment.
