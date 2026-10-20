# Fresh batch estates: blind candidate list and draw method

**Status: awaiting owner approval (see [`estate_batch_preregistration.md`](estate_batch_preregistration.md), section 0). No crawl has run; there are no candidates, no target round and no draw.**

> **Candidate repos must not be opened by anyone until the trial ends.** When a list exists, this file holds metadata only.

Rules: the CICS rules in [`estate4_candidates.md`](estate4_candidates.md) with rule 4 replaced by batch evidence (`.jcl`, `.proc`, `.prc`, or a `jcl/` folder; file names only).

Once the owner approves, `python tests/tools/estate4_draw.py build --kind batch --approved-by-owner` writes `estate_batch_candidates.json` and `estate_batch_candidates_requests.json`; this page is then completed by hand with the filter counts, the target round and the table, in the same PR as the JSON, before the draw. The draw is `python tests/tools/estate4_draw.py draw --kind batch --round R`.
