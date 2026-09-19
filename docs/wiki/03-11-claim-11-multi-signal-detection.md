# Claim 11: Multi-Signal Language Detection (Inference With Provenance, Not a Waterfall)

Most language detectors answer one question — *"what language is this file?"* — and return one thing: a label. GitGalaxy answers a different question — *"what language is this file, how do we know, and how much should you trust that?"* — and returns three things: a language, a **trust tier**, and a human-readable **proof of how it was reached**.

The premise is that a file extension is an **assertion, not evidence**. `payload.json` can be a shell script; `notes.txt` can be a PowerShell payload with a `.txt` coat on. Treating the extension as ground truth is how a scanner gets lied to. So detection here is a multi-signal inference that weighs several independent, zero-dependency signals against each other and attaches an explicit confidence to the verdict — never a single waterfall that falls through to a bare guess.

This page argues the design. For the mechanical tier-by-tier reference, see **[Language Lens](02-05-language-lens.md)**.

---

## 1. The signals actually combined

All of these are computed with **no trained model and no sample corpus** — pure structure, resolvable on an air-gapped box:

* **Exact filename anchors** — `Makefile`, `Dockerfile`, `setup.py`, `SConstruct` are their language regardless of extension.
* **Extension**, with multi-suffix unwrapping for wrapper extensions — `script.sh.template` resolves through `.template` to `.sh`, but only when the inner suffix is a known safe wrapper (so `malware.exe.txt` is *not* unwrapped into an executable).
* **Shebang**, matched on the interpreter basename as a token — never an unanchored substring (the #3116 fix: a canonical `#!/usr/bin/tclsh` is no longer defeated by, nor confused with, an unrelated line that merely contains those characters).
* **Prose anchors** — README / LICENSE / CONTRIBUTING-family files, with affix matching.
* **Sibling anchors** — `foo.h` resolves to C when `foo.c` is in the directory tally, C++ when `foo.cpp` is, Objective-C when `foo.m` is.
* **Ecosystem gravity** — a directory-local census combined with per-language discriminators and disqualifiers, gated on `ECOSYSTEM_DOMINANCE_MIN` (0.70). For a *same-extension* collision — where counting extensions is information-free because both rivals share the extension — gravity now weighs what the neighbours **actually classified as by their own content**, not merely their filenames (the #3137 sibling-classification vote).
* **`internal_discriminator` content regexes** — consulted *only* for registry-declared collision extensions, never as global scanners (an Objective-C `@implementation` pattern must not be free to hijack an unrelated `.m` MATLAB file).
* **A full lexical scan** that scores the file against each candidate language's own structural-signature rules.
* **A discovery funnel** for extensionless files that isolates the comment family first, then requires a 1.5× margin over the runner-up before it will name a language.
* **Caller-supplied context priors** from upstream metadata.

---

## 2. The three genuinely differentiated properties

This is the honest core of the claim — the part with no obvious counterpart in Linguist, enry, guesslang, Pygments, or libmagic.

* **Agreement-based tiering with provenance.** Two independent signals concurring (extension *and* shebang, say) lock **Tier 0** at 0.999; a single indicator lands **Tier 2** at 0.91. Every result carries a numeric `lock_tier` and a human-readable `source_proof` string — `"Absolute Consensus (Ext + Shebang)"`, `"Sibling Anchor (.c)"`, `"Collision Resolved (.py -> embedded_python)"`. The engine reports not just the answer but *how it was reached and how much to trust it*. Mainstream detectors return a label and keep their reasoning to themselves.

* **Identity conflict as a refusal — and as a security signal.** When the extension and the shebang name two different languages, the file is **not** resolved to a best guess. It drops to **Tier 5, "Absolute Distrust"**: `undeterminable`, intensity `0.0`, with an `Identity Masking` anomaly flag raised for the security engine. The contradiction *is* the finding — a `.txt` that re-execs a shell is more interesting *because* it lies about itself than any confident label could ever be. A generic-shell launcher that re-execs an interpreter its own extension already claims (a portable `.tcl` trampoline) is explicitly cleared, so the refusal fires on masquerade, not on legitimate bootstrapping.

* **Repo-context inference.** Gravity and sibling anchors classify a file using its **neighbours** — something a stateless, file-by-file classifier structurally cannot express. This is what makes the mainframe family tractable: an EQU-only copybook is HLASM *because it sits beside JCL and COBOL*, and a telemetry `.py` with no hardware imports is MicroPython *because every resolvable file around it resolved to MicroPython by content*. A per-file oracle has no vocabulary for "because of where it lives."

---

## 3. Where it is convergent, not novel

Stating this plainly makes the claim *stronger*, not weaker.

The collision-registry-plus-content-discriminator mechanism is, functionally, what GitHub Linguist does in `heuristics.yml`. The per-language lexical self-scoring is, architecturally, what Pygments does with `analyse_text()`. We did not invent disambiguation-by-content or scoring-by-structural-fingerprint.

Arriving independently at the same disambiguation structure as the tool calibrated against millions of repositories is a **validation** of the design — not an embarrassment, and not something to dress up as invention. A writeup that claimed novelty for those two parts would be falsifiable in five minutes by anyone who knows the field, and would discredit the three real claims above by association.

The honest framing: *GitGalaxy independently arrived at the field's disambiguation architecture — with no dependencies and no training data — and then added provenance tiering, identity-conflict refusal, and repo-context inference on top of it.*

---

## 4. Honest limits

Mirroring Claim 10's own §3, because that section is what makes it credible.

**The lexical scan's scoring constants are hand-tuned and uncalibrated.** In `_tier_3_lexical_scan` the score is assembled from: per-rule-hit weights; a comment-delimiter bonus of `+= 15.0` awarded on a plain substring test (`if d in content`); two `1.25×` boosts (one for the gravity winner, one for the extension-tier claimed language); a hardcoded `0.4×` handicap for exactly three broad-ruleset languages (`if lid in ("abap", "fortran", "cobol")`); log-normalisation by lines of code (`raw_score / math.log1p(loc)`); and a final confidence derived by dividing the top signal by 50 (`min(top_signal / 50.0, 1.0)`). These numbers work on the corpus we have. None of them is calibrated against a probabilistic model, and that is the next real piece of work here, not a solved problem.

**The design catches its own defects — and this section is the receipt.** The [#3117 detection-accuracy harness](02-05-language-lens.md) exists precisely so that a stably-wrong classification cannot hide behind green golden-master tests. On its first runs it surfaced, and the engine has since closed, four real defects: an EQU-only copybook misclassified via gravity (#3110); canonical shebangs forced to a false Tier 5 conflict by unanchored substring matching (#3116); silent tie-breaking by registry order on contested extensions (#3118); and gravity's structural blindness to same-extension collisions, which resolved by pinning to a discriminator self-reference until the sibling-classification vote replaced it (#3132 / #3137). A detector whose own harness finds real bugs and whose maintainers fix rather than relabel them is the honest kind.

---

## 5. The number

A claims page that asserts architectural superiority with no measured accuracy is the weakest possible form of this document. So here is the measurement, from the #3117 harness against the pinned 51-language `language-crucible` corpus (3,531 files):

* **Determinable accuracy: 3,231 / 3,231 = 1.0** — every file with a single defensible language got that language.
* **Ambiguous rejection: 1 / 1 = 1.0** — every file with *no* single defensible language was declined (`undeterminable`), not guessed. This objective is scored *inverted*: a refusal passes, a confident verdict fails. Driving one objective up by guessing harder drives the other down, so the two cannot be gamed the same way.
* **Confusion matrix: empty.**

The honest caveat travels with the figure. Most of the corpus is auto-labelled *by extension*, and extension is also the detector's primary signal — so on that subset the oracle and the system under test share an input, and a high score there is partly tautological. The number that actually measures disambiguation is the **hand-labelled contested subset** (files on shared extensions, where content and context must decide): **509 / 509 = 1.0**. And 1.0 on a finite, pinned corpus is a **generalisation estimate**, not a proof of universal perfection — its value is as evidence that the two failure modes are both driven to target on independent ground truth, not as a guarantee about all code everywhere.

---

**See also:** [Language Lens](02-05-language-lens.md) — the mechanical tier-by-tier reference for the engine this claim argues for.

**[⬅️ Back to Master Index](index.md)**
