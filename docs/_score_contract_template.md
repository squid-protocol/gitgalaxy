# The `risk_<metric>` score contract (#<N>)

<!-- Template (#2916): the score-layer twin of a rule-contract doc, mirroring
docs/risk_documentation_contract.md (#2908). One file per gated metric; every
section below is load-bearing -- delete none, mark n/a explicitly. -->

Phase 4 of the contract roadmap (`docs/contract_roadmap.md`, epic #2812): the
score row `risk_<metric>` goes from formula-by-accretion to a stated equation
contract. Decomposition evidence: `tests/tools/audit_score_inputs.py <metric>`
(#2916) reproduces every recorded score from its recorded inputs (0 residuals
on <date>, <n> corpus files).

## 1. The equation

> **<one sentence: what the score MEANS, stated without reference to any
> language or to the current implementation.>**

```
risk_<metric> = <the equation, in input names -- not code>
```

Inputs, each with the kind/unit from `signal_contracts.py`, so the sum adds
like to like (the commensurability audit's question):

| input | source (file_data column / constant) | kind/unit | role |
|---|---|---|---|
| | | | |

## 2. What the current formula measures, and why it is replaced

<The audit_score_inputs CLUSTER + SENSITIVITY digest: which input dominates,
points-per-unit, the open-defect cells the bias report pins on this metric,
the length leak or granularity mismatch if any.>

## 3. What leaves the equation, and why

<Each term removed, with the corollary-style one-liner: where it moved, or why
it was never this metric's to carry.>

## 4. Decisions (approve on #<N> before Phase 2)

- **D1 -- <name>**: <the judgment the equation forces>. Recommendation: <x>.
  Alternative: <y>. <consequence of each>.
- **D2 -- ...**

## 5. Expected values (acceptance)

Hand-computed from the contract BEFORE implementation; asserted afterward in
`tests/metrics/test_<metric>_contract.py`.

| corpus file | inputs | expected `risk_<metric>` | note |
|---|---|---|---|
| | | | |

## 6. Consumers

<Every reader of `risk_<metric>` / `_calc_<metric>`: score aggregates,
security_auditor features (note the #96 retrain if a trained input shifts),
recorders, report sections -- one line each with the file:line.>

## 7. Phase map

<Which phase of the parent epic each piece lands in; the engine/corpus PR
pair; merge order (engine first); the bless scope expected
(`bless_scope --from-head --summary` leaf keys = this metric + section 6's
consumers, nothing else).>
