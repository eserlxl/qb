# Analyzer Coverage

QB's default offline registry is built in `shared/scripts/audit_runner.py` by
`build_default_registry()`. It currently registers:

- `SecretHygieneAnalyzer`
- `CommandInjectionAnalyzer`
- `QualityAnalyzer`
- `DependencyAnalyzer`
- `LicenseAnalyzer`
- `ConfigHygieneAnalyzer`
- `WorkflowActionAnalyzer`

Those producers emit findings in the frozen categories from
`shared/scripts/finding_schema.py`: `secret`, `injection`, `path-traversal`,
`dependency`, `quality`, `correctness`, `license`, and `config`.

## Current coverage statement

- `SecretHygieneAnalyzer` covers secret-shaped values in the `secret` category.
- `CommandInjectionAnalyzer` covers shell-string execution, dynamic eval, and
  traversal sinks in the `injection` and `path-traversal` categories.
- `DependencyAnalyzer` covers unpinned `requirements.txt` dependencies,
  unpinned `pyproject.toml` project/Poetry dependencies, and missing npm
  lockfiles in the `dependency` category.
- `WorkflowActionAnalyzer` covers broad GitHub Actions `uses:` refs in workflow
  files in the `dependency` category.
- `LicenseAnalyzer` covers missing or placeholder repository-root license files
  in the `license` category.
- `ConfigHygieneAnalyzer` covers committed dotenv files and credential-bearing
  `.npmrc` keys in the `config` category.
- `QualityAnalyzer` is environment-conditional: the `ruff` adapter can emit
  `quality` findings only when `ruff` is already installed, and the `pyflakes`
  adapter can emit `correctness` findings only when `pyflakes` is already
  installed.

## Impact-ranked coverage gaps

1. **Project manifests beyond `requirements.txt`, `pyproject.toml`, and basic `package.json`
   lockfile presence (`dependency`)**
   - Current coverage: `DependencyAnalyzer` parses `requirements.txt` and
     `pyproject.toml` dependency declarations for exact Python pins and checks
     that `package.json` has one recognized lockfile.
   - Gap: `poetry.lock`, `Pipfile.lock`, `go.mod`, `Cargo.toml`, and richer npm
     dependency sections are not inventoried.
   - Candidate follow-up: extend existing dependency parsing before adding
     networked advisory enrichment.

2. **Runtime/container configuration (`config`, `security-adjacent`)**
   - Current coverage: `ConfigHygieneAnalyzer` flags committed dotenv files and
     credential-bearing `.npmrc` files.
   - Gap: Dockerfiles, compose files, and Kubernetes manifests are not checked
     for high-risk defaults such as privileged containers, broad host mounts,
     or missing non-root execution.
   - Candidate follow-up: a bounded config analyzer for deterministic text
     patterns in container manifests.

3. **Language-specific correctness without optional tools (`correctness`,
   `quality`)**
   - Current coverage: `QualityAnalyzer` uses local `ruff` and `pyflakes` only
     when already installed.
   - Gap: JavaScript/TypeScript, Go, Rust, and shell correctness rely on no
     built-in stdlib analyzer, and absent optional tools yield no diagnostics.
   - Candidate follow-up: keep optional adapters for deep tool output, but add
     narrow stdlib checks only where false-positive risk stays low.

4. **License metadata inside package manifests (`license`)**
   - Current coverage: `LicenseAnalyzer` checks repository-root license files.
   - Gap: package-level license declarations in `package.json`, `pyproject.toml`,
     Cargo manifests, and generated distributions are not compared to the root
     license state.
   - Candidate follow-up: manifest-level license consistency after the broader
     dependency inventory exists.

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
