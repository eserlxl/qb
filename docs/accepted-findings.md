# Accepted findings register

The committed register of QB self-audit findings that are **explicitly accepted**
— a deliberate, reviewed decision *not* to fix a finding QB raised about its own
repository. "Accepted" is recorded here, in version control, rather than in chat
scrollback, so the decision stays auditable and reproducible.

`shared/scripts/accepted_findings.py` parses this register into the `accepted_ids`
set consumed by `production_gate.self_audit_clean` / `unaccepted_findings`: a
self-audit is *clean* only when every finding is either fixed or listed here. An
absent or empty register accepts nothing (fail-closed), so an unreviewed finding
can never silently pass the production gate's `self_audit_clean` conjunct.

## Format

Each accepted finding is one list item under the `## Accepted` heading below, in
the form:

    - `<finding-id>` — <rationale> (reviewer: <marker>)

The loader reads only the backtick-wrapped leading id of each such list item, so
rationale prose and other sections never leak in. Record **no secret value** here.

Example (illustrative only; it lives outside the `## Accepted` section and is not
parsed):

    - `QBF-EXAMPLE-0001` — known false positive in a vendored test fixture (reviewer: maintainer)

## Accepted

<!--
No findings are accepted yet: every current QB self-audit finding is tracked for a
fix, not waived. Add an entry above only after a reviewer deliberately accepts a
specific finding id, with a rationale and a reviewer marker.
-->
