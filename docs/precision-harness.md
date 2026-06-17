# Precision Harness

QB measures per-analyzer precision before adding breadth. A labelled fixture
corpus pairs each fixture repo with a ground-truth manifest of the findings it
should produce; the harness runs the offline audit over each fixture, joins
emitted findings to the labels, and computes precision/recall per analyzer and
per category. The result feeds the earned-autonomy ceiling
(`release_gate.precision_gate`).

## Label manifest schema

Each fixture carries a `labels.json` manifest. It is **stdlib-parseable JSON**,
keyed on the same identity inputs `finding_schema` uses to compute a finding id —
`(category, evidence locator, rule_key)` — so a label joins to an emitted finding
without guessing:

```json
{
  "fixture": "example-case",
  "expected_findings": [
    {
      "category": "injection",
      "evidence": "app.py:2",
      "rule_key": "system-shell-call"
    }
  ]
}
```

Field rules:

- **`category`** — one of the frozen `finding_schema.CATEGORIES`.
- **`evidence`** — the locator, either `path:line` or `path:start-end`, matching
  the `evidence` string an analyzer emits.
- **`rule_key`** — the analyzer rule that should fire (e.g. `system-shell-call`,
  `shell-string-subprocess`, `path-traversal-sink`).
- A fixture with **no** issues has `"expected_findings": []` (a known-clean case).

**No secret values** appear in any fixture or manifest — true-positive secret
cases use placeholder/synthetic tokens only.

## Join key

The harness joins an emitted finding to a label on the triple
`(category, evidence, rule_key)` — the same inputs `compute_finding_id` hashes.
A label with a matching emitted finding is a **true positive**; an emitted finding
with no matching label is a **false positive**; a label with no matching emitted
finding is a **false negative**. Precision is `TP / (TP + FP)`; recall is
`TP / (TP + FN)`, computed per analyzer and per category.

## Telemetry feed design

The harness output populates the precision_estimate telemetry field consumed by
`release_gate.precision_gate`. For an analyzer-coverage evaluation run, derive
the value from the report's `per_analyzer` precision values by taking the lowest
non-null precision among the analyzers that are in scope for the release gate;
if no in-scope analyzer has a measured precision value, leave the telemetry value
as `null` so the existing gate fails closed. This keeps the feed conservative:
one weak analyzer lowers the earned-autonomy ceiling instead of being hidden by a
high aggregate average.

This feed changes only the producer of telemetry for analyzer-coverage
evaluation runs. `precision_gate` and the `PRECISION_FLOOR` threshold stay
unchanged: the gate still reads the numeric `quality.precision_estimate` value
and denies auto-apply when it is absent, malformed, or below the floor.

## Corpus layout

```
tests/fixtures/precision-corpus/
  <case-name>/
    labels.json          # the ground-truth manifest
    <fixture source files>
```

Each case is either a **positive** case (≥1 expected finding) or a **known-clean**
case (`expected_findings: []`), so both precision and recall are measurable.
