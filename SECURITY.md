# Security Policy

## Supported Versions

QB is versioned by the root [`VERSION`](VERSION) file under
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Only the **latest
released version** receives security fixes; there are no maintained backport
branches. Check `VERSION` for the current release.

| Version | Supported |
|---|---|
| Latest release (current `VERSION`) | ✅ |
| Any older version | ❌ — upgrade to the latest |

## Reporting a Vulnerability

QB is an open project with no private security mailbox. Report a suspected
vulnerability through the **public** issue tracker:

- Open an issue at <https://github.com/eserlxl/qb/issues>

Because the channel is public, do **not** paste secret values, credentials,
private keys, customer data, sensitive exploit payloads, or step-by-step exploit
details into the report. Redact values, use synthetic examples, and describe the
impact plus affected surface. If a useful report cannot be shared safely in public,
open a minimal issue naming the affected surface and ask a maintainer to coordinate
before sharing sensitive material. Please allow a reasonable window for a fix to
ship before disclosing further details publicly.

## Trusted-code precondition

Full execution sandboxing of analyzed code is **not yet shipped** (a roadmap
item). QB currently provides disposable **write isolation** (a throwaway git
worktree) and command-level **process confinement** for verification, but it does
**not** provide filesystem, network, syscall, or container isolation for
arbitrary analyzed code. The apply-verified (A2) and deliver (A3) autonomy levels
are safe only against **trusted code** until full execution sandboxing lands. Do
not rely on QB to contain untrusted code. This mirrors the README and BASELINE
caveats and does not remove them.
