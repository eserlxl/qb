# Analyzer Coverage

QB's default offline registry is built in `shared/scripts/audit_runner.py` by
`build_default_registry()`. It currently registers:

- `SecretHygieneAnalyzer`
- `CommandInjectionAnalyzer`
- `QualityAnalyzer`
- `DependencyAnalyzer`
- `LicenseAnalyzer`
- `ConfigHygieneAnalyzer`

Those producers emit findings in the frozen categories from
`shared/scripts/finding_schema.py`: `secret`, `injection`, `path-traversal`,
`dependency`, `quality`, `correctness`, `license`, and `config`.

## Impact-ranked coverage gaps

1. **CI and automation dependency pinning (`dependency`, `config`)**
   - Current coverage: no default analyzer reads `.github/workflows/*.yml` or
     other CI workflow files.
   - Gap: workflow actions and setup steps can drift when pinned only to broad
     tags, and QB will not report that supply-chain risk.
   - First new offline analyzer: a stdlib-only workflow analyzer that scans
     GitHub Actions `uses:` entries and reports broad tag or branch refs as
     dependency findings.

2. **Project manifests beyond `requirements.txt` and basic `package.json`
   lockfile presence (`dependency`)**
   - Current coverage: `DependencyAnalyzer` parses `requirements.txt` for exact
     Python pins and checks that `package.json` has one recognized lockfile.
   - Gap: `pyproject.toml`, `poetry.lock`, `Pipfile.lock`, `go.mod`, `Cargo.toml`,
     and richer npm dependency sections are not inventoried.
   - Candidate follow-up: extend existing dependency parsing before adding
     networked advisory enrichment.

3. **Runtime/container configuration (`config`, `security-adjacent`)**
   - Current coverage: `ConfigHygieneAnalyzer` flags committed dotenv files.
   - Gap: Dockerfiles, compose files, and Kubernetes manifests are not checked
     for high-risk defaults such as privileged containers, broad host mounts,
     or missing non-root execution.
   - Candidate follow-up: a bounded config analyzer for deterministic text
     patterns in container manifests.

4. **Language-specific correctness without optional tools (`correctness`,
   `quality`)**
   - Current coverage: `QualityAnalyzer` uses local `ruff` and `pyflakes` only
     when already installed.
   - Gap: JavaScript/TypeScript, Go, Rust, and shell correctness rely on no
     built-in stdlib analyzer, and absent optional tools yield no diagnostics.
   - Candidate follow-up: keep optional adapters for deep tool output, but add
     narrow stdlib checks only where false-positive risk stays low.

5. **License metadata inside package manifests (`license`)**
   - Current coverage: `LicenseAnalyzer` checks repository-root license files.
   - Gap: package-level license declarations in `package.json`, `pyproject.toml`,
     Cargo manifests, and generated distributions are not compared to the root
     license state.
   - Candidate follow-up: manifest-level license consistency after the broader
     dependency inventory exists.

6. **Config templates and generated examples (`config`, `secret`)**
   - Current coverage: committed real `.env` files are flagged and secret-shaped
     values are detected.
   - Gap: unsafe defaults inside example config files are not distinguished from
     acceptable templates, so QB does not yet guide users toward safer examples.
   - Candidate follow-up: template-specific config checks with explicit false
     positive controls.

The first breadth investment should be the CI workflow action analyzer because
it adds a new ecosystem without changing the finding schema, uses only local
text parsing, and produces a measurable dependency finding that can be covered
by the precision corpus.
