# False-Positive Controls

QB false-positive controls must be deterministic and auditable: a finding may be
withheld or downgraded only by a documented rule that records why it happened.

## Command-Safety Suppressions

The command-safety analyzer supports a source marker for known false positives:

```python
# qb-ignore: system-shell-call fixture exercises a documented false-positive control
os.system(cmd)
```

The marker applies only to the same line or the immediately following line. It
must name either the exact rule key or `*`, and it must include a human-readable
reason. A marker without a matching rule key or without a reason is ignored, not
recorded as a suppression, so the analyzer emits the finding normally.

When a marker suppresses a finding, `CommandInjectionAnalyzer` records a
suppression entry with the rule, evidence location, and reason in
`last_suppression_report`. Normal audit runs copy those entries into
`.qb/audit/summary.json` under `analyzers_suppressed`, so suppressions are visible
even though no finding is written to `findings.jsonl`.

## Confidence Downgrades

Confidence downgrades use `analyzer_core.CONFIDENCE_POLICY`. Each producer rule
kind maps to a reviewed `high`, `medium`, or `low` band; new rule kinds must be
added there before they can emit findings. This keeps uncertain findings at
`medium` or `low` by policy instead of by scattered literals.
