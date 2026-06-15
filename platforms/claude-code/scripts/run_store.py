"""QB run-state & evidence store (Phase 5.1).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
The authoritative execution truth for a single audit-and-harden run: given only
the store directory, a reader can reconstruct what was found, what changed, why,
and how to undo it -- with no reliance on chat scrollback or external trackers.

Fixed-name layout under the run output directory (working name ``QB-Audit/``,
mirroring the ``.qb/`` convention):
  findings.jsonl          -- the graded findings inventory (one Finding per line)
  evidence/<id>.json      -- per-fix evidence: verify command, before/after result,
                             keep/revert outcome, and a git reversal handle
  run-log.jsonl           -- append-only orchestration events (seq-ordered)
  summary.json            -- run summary (counts, stop reason)

Redaction is mandatory: no secret value is ever persisted (the existing
length-bounded SECRET_PATTERNS are applied before write). Overwrite is opt-in: a
new run never silently clobbers a prior run's directory unless ``overwrite=True``.
"""

from __future__ import annotations

import json
import shutil
import sys
from importlib import util as _import_util
from pathlib import Path

OUTPUT_DIR_NAME = "QB-Audit"
FINDINGS_FILENAME = "findings.jsonl"
EVIDENCE_DIRNAME = "evidence"
RUN_LOG_FILENAME = "run-log.jsonl"
SUMMARY_FILENAME = "summary.json"
REQUIRED_SUBPATHS = (FINDINGS_FILENAME, EVIDENCE_DIRNAME, RUN_LOG_FILENAME, SUMMARY_FILENAME)


def _load_sibling(module_name: str, filename: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parent / filename
    spec = _import_util.spec_from_file_location(module_name, path)
    module = _import_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_fs = _load_sibling("qb_finding_schema", "finding_schema.py")
_core = _load_sibling("qb_analyzer_core", "analyzer_core.py")
serialize_finding = _fs.serialize_finding


def redact(value):
    """Redact secret-shaped substrings in any string (recursing into containers)."""
    if isinstance(value, str):
        out = value
        for _name, pattern in _core.SECRET_PATTERNS:
            out = pattern.sub("<redacted>", out)
        return out
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class RunStoreError(Exception):
    pass


class RunStore:
    def __init__(self, output_dir):
        self.root = Path(output_dir)
        self.evidence_dir = self.root / EVIDENCE_DIRNAME
        self._log_seq = 0

    def open(self, overwrite: bool = False) -> "RunStore":
        if self.root.exists() and any(self.root.iterdir()) and not overwrite:
            raise RunStoreError(f"run store already exists (use overwrite=True): {self.root}")
        # overwrite=True means a fresh run: clear stale per-fix evidence too, so a
        # re-run does not trip record_evidence's clobber guard on a leftover file.
        if overwrite and self.evidence_dir.exists():
            shutil.rmtree(self.evidence_dir, ignore_errors=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        # start an append-only run log
        (self.root / RUN_LOG_FILENAME).write_text("", encoding="utf-8")
        self._log_seq = 0
        return self

    def write_findings(self, findings) -> None:
        # Redaction is mandatory on EVERY persisted artifact (see module docstring):
        # redact each finding's on-disk mapping before serialization, mirroring the
        # record_evidence / append_log / write_summary writers. A finding's rationale
        # or suggested_fix can quote secret-shaped material, so the findings file is
        # not exempt from the no-secret-value invariant.
        ordered = sorted(findings, key=lambda f: f.id)
        text = "".join(serialize_finding(redact(f.to_dict())) + "\n" for f in ordered)
        (self.root / FINDINGS_FILENAME).write_text(text, encoding="utf-8")

    def record_evidence(self, evidence: dict) -> None:
        record = redact(dict(evidence))
        finding_id = record.get("finding_id")
        # Per-fix evidence is keyed by finding_id; a missing/empty id would write to a
        # shared 'unknown.json' and silently clobber another record. Require it.
        if not isinstance(finding_id, str) or not finding_id.strip():
            raise RunStoreError("evidence record requires a non-empty finding_id")
        target = self.evidence_dir / f"{finding_id}.json"
        if target.exists():
            raise RunStoreError(f"evidence already recorded for {finding_id} (refusing to clobber)")
        # A kept fix MUST carry a reversal handle, else it is not recoverable.
        if record.get("outcome") == "kept" and not record.get("rollback_handle"):
            record["outcome"] = "not-kept"
            record["reason"] = "missing-rollback-handle"
        target.write_text(
            json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def append_log(self, event: dict) -> None:
        self._log_seq += 1
        entry = redact({"seq": self._log_seq, **event})
        with (self.root / RUN_LOG_FILENAME).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def write_summary(self, summary: dict) -> None:
        (self.root / SUMMARY_FILENAME).write_text(
            json.dumps(redact(dict(summary)), sort_keys=True, indent=2) + "\n", encoding="utf-8")

    # -- read side (consumed by Phase 5.2 reporting) -----------------------
    def read_findings(self) -> list:
        path = self.root / FINDINGS_FILENAME
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def read_evidence(self) -> list:
        if not self.evidence_dir.is_dir():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.evidence_dir.glob("*.json"))]

    def read_summary(self) -> dict:
        path = self.root / SUMMARY_FILENAME
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def validate_store_layout(output_dir) -> list:
    """Identifier check: the required subpaths exist with the fixed names."""
    errors = []
    root = Path(output_dir)
    if root.name != OUTPUT_DIR_NAME:
        errors.append(f"invalid_store_dir_name={root.name}")
    for sub in REQUIRED_SUBPATHS:
        if not (root / sub).exists():
            errors.append(f"missing_store_path={sub}")
    return errors
