"""QB accepted-findings register loader (Phase 7.3).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
Parses the committed accepted-findings register (``docs/accepted-findings.md``)
into the ``accepted_ids`` set consumed by ``production_gate.self_audit_clean`` /
``unaccepted_findings``. The register maps each explicitly-accepted self-audit
finding id to a rationale and a reviewer marker; "accepted" means a deliberate,
reviewed decision *not* to fix, recorded in version control rather than in chat.

Format (one accepted entry per list item under the ``## Accepted`` heading):

    - `<finding-id>` -- <rationale> (reviewer: <marker>)

Only a well-formed list item with a backtick-wrapped leading token, rationale,
and reviewer marker is read as an accepted id, so surrounding prose, malformed
entries, and other sections never leak in. An absent or empty register accepts
nothing (fail-closed), so an unreviewed finding can never silently satisfy the
production gate's ``self_audit_clean`` conjunct. No secret value may appear in
the register (the no-committed-secrets guard holds over it like every other
tracked file).
"""

from __future__ import annotations

import re
from pathlib import Path

REGISTER_RELATIVE_PATH = "docs/accepted-findings.md"

_ACCEPTED_HEADING = re.compile(r"^##\s+Accepted\s*$")
_NEXT_HEADING = re.compile(r"^##\s+")
# A list item (no leading indent) with id, rationale, and explicit reviewer marker.
_ACCEPTED_ENTRY = re.compile(
    r"^-\s+`([^`]+)`\s+(?:--|\u2014)\s+.+\(\s*reviewer:\s*[^)]+\s*\)\s*$"
)


def parse_accepted_ids(text: str) -> set:
    """Parse the register text into the set of accepted finding ids.

    Only well-formed list items under the ``## Accepted`` heading are read;
    everything else (prose, malformed entries, indented examples, other sections)
    is ignored, so the register cannot accidentally accept an id merely named in
    passing or waived without a rationale and reviewer marker.
    """
    accepted: set = set()
    in_section = False
    for line in text.splitlines():
        if _ACCEPTED_HEADING.match(line):
            in_section = True
            continue
        if in_section and _NEXT_HEADING.match(line):
            break
        if in_section:
            match = _ACCEPTED_ENTRY.match(line)
            if match:
                finding_id = match.group(1).strip()
                if finding_id:
                    accepted.add(finding_id)
    return accepted


def load_accepted_ids(repo_root) -> set:
    """Load the accepted-findings register relative to ``repo_root``.

    An absent register yields an empty set (fail-closed: nothing is accepted by
    default), so a missing register never opens the self-audit conjunct.
    """
    path = Path(repo_root) / REGISTER_RELATIVE_PATH
    if not path.is_file():
        return set()
    return parse_accepted_ids(path.read_text(encoding="utf-8"))
