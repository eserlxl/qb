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
      "analyzer_id": "command-injection",
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
- **`analyzer_id`** — optional owner for categories emitted by multiple
  analyzers. When present, per-analyzer metrics count the label only for that
  analyzer; aggregate and per-category metrics still use the normal join key.
- A fixture with **no** issues has `"expected_findings": []` (a known-clean case).

The `example-case` fixture demonstrates a mixed positive/clean dependency
manifest: an unpinned `express` range is labelled as a dependency finding while
an exact-pinned `lodash` entry and committed `package-lock.json` remain clean.

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

## The precision gate (`make precision`)

`make precision` runs the harness over the corpus and evaluates the built report
against the project's threshold bars, exiting **non-zero if any bar is unmet** and
**0 when all are met** (fail-closed). The JSON report is written to stdout and a
deterministic `{"gate": "PASS"|"FAIL", "failures": [...]}` summary to stderr,
naming each failing `scope`/`metric`/`threshold`/`actual`.

**Bars** live in [`tests/fixtures/precision-thresholds.json`](../tests/fixtures/precision-thresholds.json):

- **`min_recall: 1.0`** (overall) — every labelled defect must be found.
- **Per-analyzer `min_precision: 1.0` + `min_recall: 1.0`** for the four
  fully-labelled deterministic analyzers (`command-injection`, `dependency-audit`,
  `secret-hygiene`, `workflow-actions`).

**Why totals precision is not gated.** The full default registry also runs the
`license`/`config` analyzers, which emit findings (e.g. `missing-license` on the
LICENSE-less fixtures) that the corpus does not label — so the overall *precision*
number is not a meaningful bar. Recall (all labelled defects found) and the
per-analyzer precision/recall of the labelled analyzers are.

**Capability-aware.** An analyzer whose only adapters are absent optional tools
(e.g. `ruff`/`pyflakes` not installed) is recorded as `capability_skipped` and is
**not scored** — a not-run analyzer never fails the gate, distinct from a
below-threshold one.

The raw routine is also callable directly:
`python3 shared/scripts/precision_harness.py --corpus <dir> --thresholds <file>`,
or with the `--min-precision` / `--min-recall` overall flags.
