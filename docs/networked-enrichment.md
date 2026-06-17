# Networked Enrichment Analyzer Contract

QB's default audit path is offline. A networked enrichment analyzer is allowed
only as an optional extension whose absence or unavailability never prevents the
offline audit from completing.

## Required shape

- A networked analyzer descriptor must set `offline=False`.
- The analyzer must be registered through `AnalyzerRegistry.register_optional`,
  not unconditional default registration.
- `register_optional gates each networked analyzer` so import, configuration, or
  construction failures are recorded in `AnalyzerRegistry.skipped` and the audit
  continues.
- `AnalyzerRegistry.enabled(allow_networked)` is the runtime gate. With
  `allow_networked=False`, networked analyzers are excluded and `run_audit`
  records each one in `analyzers_skipped` with reason `networked-disabled`.
- With `allow_networked=True`, the analyzer may run, but it still must fail
  closed when its source is unavailable: record a skip reason and emit no
  fabricated findings.

## Graceful absence

Optional enrichment dependencies must not become core dependencies. If a loader
cannot import or configure an analyzer, `register_optional` records
`(analyzer_id, reason)` and returns `None`. The default registry remains usable,
and the summary exposes the skipped analyzer instead of hiding it.

## Fail-closed behavior

An enabled enrichment analyzer must distinguish "no data" from "safe." If an
advisory source is unreachable, malformed, missing credentials, or otherwise
unavailable, the analyzer records a skip and returns zero enrichment findings for
that source. It must not synthesize vulnerability, dependency, or quality
findings from stale or partial network data.

## Offline core boundary

The existing `DependencyAnalyzer` keeps its base descriptor offline because its
manifest and lockfile checks run without the network; its advisory source is an
internal opt-in tier guarded by `AnalyzerConfig.allow_networked`. A future
standalone networked analyzer should instead expose `offline=False`, use
`register_optional`, and rely on the registry's `enabled(allow_networked)` filter
for the outer gate.
