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

### The high / medium / low doctrine

The band reflects how much QB vouches for the finding, not its severity:

- **`high`** — a deterministic, low-ambiguity offline detection where the match
  itself is the defect: a committed secret pattern (`secret-pattern`), a
  shell-string execution sink (`shell-string-subprocess`, `system-shell-call`,
  `node-shell-exec`), or a missing license (`missing-license`). A reviewer is
  expected to act on these directly.
- **`medium`** — a real but context-dependent or heuristic signal a reviewer
  must judge: unpinned manifests (`manifest-hygiene`), broad CI surfaces
  (`broad-action-ref`, `broad-permissions`), the `dynamic-eval` / `path-traversal`
  heuristics, and **all tool-derived diagnostics** (`tool-diagnostic`).
- **`low`** — a weak or advisory signal kept for visibility only.

**Why tool-derived findings stay at `medium` (never `high`).** The `quality`
(`ruff`) and `correctness` (`pyflakes`) adapters are environment-dependent —
their availability and active ruleset vary by machine, and they can over-report.
QB therefore does not vouch for an external tool's diagnostic at the highest
band; `tool-diagnostic` is fixed at `medium` so the confidence field stays a
calibrated QB signal rather than an inherited third-party verdict.
