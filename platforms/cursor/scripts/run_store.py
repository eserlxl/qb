"""QB run-state & evidence store (Phase 5.1).

Canonical host-neutral QB IP under ``shared/`` (Python standard library only).
The authoritative execution truth for a single audit-and-harden run: given only
the store directory, a reader can reconstruct what was found, what changed, why,
and how to undo it -- with no reliance on chat scrollback or external trackers.

Fixed-name layout under the run output directory (default ``.qb/audit/``,
alongside the other ``.qb/`` planning artifacts):
  findings.jsonl          -- the graded findings inventory (one Finding per line)
  evidence/<id>.json      -- per-fix evidence: verify command, before/after result,
                             keep/revert outcome, and a git reversal handle
  run-log.jsonl           -- append-only orchestration events (seq-ordered)
  summary.json            -- run summary (counts, stop reason)
  telemetry.json          -- schema-versioned quality/autonomy telemetry
  telemetry-aggregate.json -- schema-versioned multi-run telemetry series

Redaction is mandatory: no secret value is ever persisted (the existing
length-bounded SECRET_PATTERNS are applied before write). Overwrite is opt-in: a
new run never silently clobbers a prior run's directory unless ``overwrite=True``.

Prior-run telemetry convention: callers that want earned autonomy across runs
pass the previous run-store directory itself (the directory containing
``telemetry.json``) to ``load_prior_telemetry``. Missing, corrupt, or stale-schema
telemetry fails closed to ``{}``.
"""

from __future__ import annotations

import json
import shutil
import sys
from importlib import util as _import_util
from pathlib import Path

OUTPUT_DIR_NAME = ".qb/audit"  # store path relative to the work/repo root
FINDINGS_FILENAME = "findings.jsonl"
EVIDENCE_DIRNAME = "evidence"
RUN_LOG_FILENAME = "run-log.jsonl"
SUMMARY_FILENAME = "summary.json"
SELF_AUDIT_FILENAME = "self-audit.json"
PRODUCTION_GATE_FILENAME = "production-gate.json"


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
_telemetry = _load_sibling("qb_telemetry", "telemetry.py")
_telemetry_aggregate = _load_sibling("qb_telemetry_aggregate", "telemetry_aggregate.py")
serialize_finding = _fs.serialize_finding
TELEMETRY_FILENAME = _telemetry.TELEMETRY_FILENAME
AGGREGATE_TELEMETRY_FILENAME = _telemetry_aggregate.AGGREGATE_TELEMETRY_FILENAME
# telemetry.json is required for a completed run: even report-only A0 emits
# quality/autonomy telemetry, and a missing file should be visible to layout
# validation instead of silently pinning later runs to cold-start behavior.
REQUIRED_SUBPATHS = (
    FINDINGS_FILENAME,
    EVIDENCE_DIRNAME,
    RUN_LOG_FILENAME,
    SUMMARY_FILENAME,
    TELEMETRY_FILENAME,
    AGGREGATE_TELEMETRY_FILENAME,
)


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

    def write_telemetry(self, record: dict) -> None:
        data = redact(dict(record))
        if "schema_version" not in data:
            raise RunStoreError("telemetry record requires schema_version")
        (self.root / TELEMETRY_FILENAME).write_text(
            json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def write_self_audit(self, record: dict):
        """Persist a redacted self-audit evidence record (the QB-audits-QB
        reconciliation result: clean flag, accepted count, unaccepted ids)
        deterministically (sorted keys). No secret value is ever emitted (redacted
        via the same length-bounded SECRET_PATTERNS as every other artifact).
        Returns the written path."""
        data = redact(dict(record))
        path = self.root / SELF_AUDIT_FILENAME
        path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return path

    def write_production_gate(self, record: dict):
        """Persist a redacted production-gate evidence record (the composite gate's
        checks/failures/passed/a3_enabled_by_default) deterministically (sorted
        keys); no secret value is ever emitted. A passing gate still records A3 as
        explicit opt-in (``a3_enabled_by_default`` False). Returns the written path."""
        data = redact(dict(record))
        path = self.root / PRODUCTION_GATE_FILENAME
        path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return path

    # -- read side (consumed by Phase 5.2 reporting) -----------------------
    def read_self_audit(self) -> dict:
        path = self.root / SELF_AUDIT_FILENAME
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def read_production_gate(self) -> dict:
        path = self.root / PRODUCTION_GATE_FILENAME
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
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

    def read_telemetry(self) -> dict:
        path = self.root / TELEMETRY_FILENAME
        if not path.is_file():
            return {}
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if record.get("schema_version") != _telemetry.TELEMETRY_SCHEMA_VERSION:
            return {}
        return record


def validate_store_layout(output_dir) -> list:
    """Identifier check: the required subpaths exist with the fixed names."""
    errors = []
    root = Path(output_dir)
    if root.name != Path(OUTPUT_DIR_NAME).name:
        errors.append(f"invalid_store_dir_name={root.name}")
    for sub in REQUIRED_SUBPATHS:
        if not (root / sub).exists():
            errors.append(f"missing_store_path={sub}")
    return errors


def load_prior_telemetry(prior_store_dir) -> dict:
    """Load the prior run-store telemetry record, failing closed to ``{}``.

    ``prior_store_dir`` is the previous run store root, conventionally the
    ``.qb/audit/`` directory containing ``telemetry.json``. The caller owns
    locating that directory; this helper only performs version-guarded loading.
    """
    if prior_store_dir in (None, ""):
        return {}
    return RunStore(prior_store_dir).read_telemetry()
