# Analyzer Coverage

QB's default offline registry is built in `shared/scripts/audit_runner.py` by
`build_default_registry()`. It currently registers:

- `SecretHygieneAnalyzer`
- `CommandInjectionAnalyzer`
- `QualityAnalyzer`
- `DependencyAnalyzer`
- `LicenseAnalyzer`
- `ConfigHygieneAnalyzer`
- `ContainerConfigAnalyzer`
- `WorkflowActionAnalyzer`

Those producers emit findings in the frozen categories from
`shared/scripts/finding_schema.py`: `secret`, `injection`, `path-traversal`,
`dependency`, `quality`, `correctness`, `license`, and `config`.

## Precision-to-gate feed

For analyzer coverage evaluation runs, measured precision populates the precision_estimate telemetry field consumed by `release_gate.precision_gate`.
The value is derived by `telemetry.precision_estimate` as `kept / (kept +
reverted)` and compared against `release_gate.PRECISION_FLOOR`; when no fixes
were attempted, the telemetry field remains `None` and the gate fails closed.

## Current coverage statement

- `SecretHygieneAnalyzer` covers secret-shaped values in the `secret` category.
- `CommandInjectionAnalyzer` covers shell-string execution, dynamic eval, and
  traversal sinks in the `injection` and `path-traversal` categories.
- `DependencyAnalyzer` covers unpinned `requirements.txt` dependencies,
  unpinned `pyproject.toml` dependencies across `[project]`,
  `[project.optional-dependencies]`, PEP 735 `[dependency-groups]`, and
  `[tool.poetry.dependencies]`, unpinned
  `package.json` `dependencies` / `devDependencies` / `optionalDependencies`,
  unpinned `Cargo.toml` `dependencies` / `dev-dependencies` / `build-dependencies`
  (Cargo semantics: a bare/caret/wildcard spec is unpinned, only `=X.Y.Z` is an
  exact pin), missing npm lockfiles, a dependency-declaring `pyproject.toml`
  shipping none of `poetry.lock` / `pdm.lock` / `uv.lock` / `Pipfile.lock`, a
  `Cargo.toml` present without a `Cargo.lock`, and a `go.mod` declaring module
  requirements without a `go.sum`, in the `dependency` category
  (`manifest-hygiene` rule kind, medium confidence, offline).
- `WorkflowActionAnalyzer` covers missing, branch, and broad major-version
  GitHub Actions `uses:` refs in workflow files in the `dependency` category
  (`github-action-broad-ref`, medium confidence, offline); explicit full semver
  tags and 40-character commit SHAs are treated as clean. It also flags a
  `permissions: write-all` over-grant (`github-action-broad-permissions`, medium
  confidence, offline) in the `dependency` category; a narrow per-scope grant
  such as `contents: read` is treated as clean.
- `LicenseAnalyzer` covers missing or placeholder repository-root license files
  in the `license` category, and -- when the root is licensed -- a package
  manifest (`package.json` / `pyproject.toml` / `Cargo.toml`) that declares a
  package but omits its own license declaration.
- `ConfigHygieneAnalyzer` covers committed dotenv files and credential-bearing
  `.npmrc` keys in the `config` category.
- `ContainerConfigAnalyzer` covers high-risk defaults in Docker Compose and
  Kubernetes manifests — privileged containers, host network/PID/IPC namespaces,
  `allowPrivilegeEscalation: true`, and host Docker-socket mounts — in the
  `config` category. It is deterministic and offline, and scans only files it
  positively identifies as container manifests, so unrelated YAML is never read.
- `QualityAnalyzer` is environment-conditional: the `ruff` adapter can emit
  `quality` findings only when `ruff` is already installed, and the `pyflakes`
  adapter can emit `correctness` findings only when `pyflakes` is already
  installed.

## Run-level capability report

Because some coverage is environment-dependent (the `ruff` / `pyflakes` adapters
run only when their tool is installed), each audit run records a deterministic
**capability report** so coverage is observable rather than silently variable.

- **Artifact.** `run_audit` writes it into the audit output directory as the
  `capability_report` field of `summary.json` (alongside `findings.jsonl`), keyed
  by analyzer id: `{ "<analyzer-id>": { "ran": [<adapter>, ...], "skipped":
  [{ "adapter": "<name>", "reason": "tool-unavailable" }, ...] } }`. Ordering is
  stable (`json.dumps(..., sort_keys=True)`), so two runs on the same host are
  byte-identical.
- **Human-readable.** The text run report carries a `coverage:` line listing how
  many analyzers ran, which were skipped (with reason), and any `tool-unavailable`
  adapter.
- **Reading a caveat.** An adapter under `skipped` with reason `tool-unavailable`
  means its optional tool was absent on the run host — a recorded coverage caveat,
  **not** a failure. An absent optional tool never changes the engine exit code,
  so two hosts with different optional-tool availability produce visibly different,
  explainable capability reports rather than indistinguishable green output.

## Impact-ranked coverage gaps

1. **Manifest breadth beyond the parsed declarations across `requirements.txt`,
   `pyproject.toml`, `package.json`, `Cargo.toml`, and `go.mod` (`dependency`)**
   - Current coverage: `DependencyAnalyzer` parses `requirements.txt` and
     `pyproject.toml` dependency declarations (`[project]`,
     `[project.optional-dependencies]`, PEP 735 `[dependency-groups]`, and
     `[tool.poetry.dependencies]`) for exact Python pins, parses
     `package.json` `dependencies` / `devDependencies` / `optionalDependencies`
     with the stdlib JSON parser for exact npm pins, and checks lockfile
     **presence**: that `package.json` has one recognized lockfile, that a
     dependency-declaring `pyproject.toml` ships one of
     `poetry.lock` / `pdm.lock` / `uv.lock` / `Pipfile.lock`, that a `Cargo.toml`
     is accompanied by a `Cargo.lock`, and that a `go.mod` declaring module
     requirements is accompanied by a `go.sum`.
   - Gap: `peerDependencies`, npm alias/workspace/file specs, and lockfile
     *contents* (only lockfile presence is checked, not the versions pinned
     inside a lockfile) are not inventoried.
   - Candidate follow-up: extend existing dependency parsing before adding
     networked advisory enrichment.

2. **Runtime/container configuration (`config`, `security-adjacent`)**
   - Current coverage: `ConfigHygieneAnalyzer` flags committed dotenv files and
     credential-bearing `.npmrc` files; `ContainerConfigAnalyzer` flags
     deterministic high-risk defaults in Docker Compose and Kubernetes
     manifests — privileged containers, host network/PID/IPC namespaces,
     `allowPrivilegeEscalation: true`, and a mounted host Docker socket.
   - Remaining gap: Dockerfile-level hardening (e.g. missing non-root `USER`)
     is intentionally deferred — that signal is high false-positive without
     build-stage analysis, and the analyzer's bounded-precision contract scopes
     it to unambiguous manifest tokens for now.
   - Candidate follow-up: a low-false-positive Dockerfile pass that distinguishes
     final-stage from build-stage images before flagging a missing `USER`.

3. **Language-specific correctness without optional tools (`correctness`,
   `quality`)**
   - Current coverage: `QualityAnalyzer` uses local `ruff` and `pyflakes` only
     when already installed.
   - Gap: JavaScript/TypeScript, Go, Rust, and shell correctness rely on no
     built-in stdlib analyzer, and absent optional tools yield no diagnostics.
   - Candidate follow-up: keep optional adapters for deep tool output, but add
     narrow stdlib checks only where false-positive risk stays low.

4. **License metadata inside package manifests (`license`)**
   - Current coverage: `LicenseAnalyzer` checks repository-root license files and,
     when the root is licensed, flags a `package.json` / `pyproject.toml` /
     `Cargo.toml` that declares a package but omits its own license declaration
     (deterministic, offline; private/unpublished/sample manifests and every
     declared license form -- SPDX string, table, classifier, file reference,
     workspace inheritance -- are suppressed).
   - Remaining gap: a manifest declaring an SPDX license that *contradicts* a
     sibling manifest's is not yet flagged -- a cross-manifest SPDX-expression
     comparison whose false-positive epicenter is SPDX normalization, so it is
     deferred until normalization can be done without eroding precision.
   - Candidate follow-up: same-directory SPDX-contradiction detection with a
     reviewed deprecated-id/alias table and operand-set parsing.

5. **Config templates and generated examples (`config`, `secret`)**
   - Current coverage: committed real `.env` files are flagged and secret-shaped
     values are detected.
   - Gap: unsafe defaults inside example config files are not distinguished from
     acceptable templates, so QB does not yet guide users toward safer examples.
   - Candidate follow-up: template-specific config checks with explicit false
     positive controls.

The first breadth investment, `WorkflowActionAnalyzer`, is now implemented and
covered by the precision corpus. The next breadth investment should extend
manifest parsing where a stdlib parser can keep false-positive risk low.
