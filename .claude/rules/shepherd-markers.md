# Shepherd markers are the shepherd's (#6694)

* **To queue a PR, add the `shepherd:merge` label and nothing else.** Never post a `<!-- shepherd:approved sha=... by=... -->`,
  `<!-- shepherd-update ... -->`, `<!-- shepherd-main-merge ... -->` or `<!-- shepherd-digest ... -->` comment by hand, from an
  agent, a skill, a brief or a workflow step. The shepherd writes them from the labelled event (`docs/ci.md`, "A label is
  bound to the head it was approved on"); a hand-written one is a forged approval for a head nobody reviewed.
* A missing marker means the labelled run was dropped: remove and re-add the label, don't write the marker.
* No skill or brief may tell an agent to post a marker. `evidence-refresh.yml` used to (removed in #6694).
