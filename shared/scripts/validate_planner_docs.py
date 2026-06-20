#!/usr/bin/env python3
"""Validate QB plan outputs (the generated .qb/ tree).

This helper is intentionally read-only. It checks the planning documents that
QB generates without editing or normalizing them.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


def _load_analyzer_core():
    """Load the co-located reusable analysis primitives (single source of truth).

    Resolved by path so it works both when this file is run as a CLI and when a
    test loads it via importlib; the module is materialized next to this one on
    every platform by scripts/sync.sh.
    """
    if "qb_analyzer_core" in sys.modules:
        return sys.modules["qb_analyzer_core"]
    path = Path(__file__).resolve().parent / "analyzer_core.py"
    spec = importlib.util.spec_from_file_location("qb_analyzer_core", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["qb_analyzer_core"] = module
    spec.loader.exec_module(module)
    return module


_core = _load_analyzer_core()


STEP1_HEADINGS = [
    "# Main Planning",
    "## 1. Executive Summary",
    "## 2. Project Vision",
    "## 3. Current State Analysis",
    "## 4. Target End State",
    "## 5. Architectural Direction and Key Decisions",
    "## 6. Phased Master Roadmap",
    "## 7. Critical Risks and Gaps",
    "## 8. Prioritized Next Steps",
    "## 9. Preparation Notes for Step 2",
    "## 10. Repository Inspection Notes",
]

ASSESSMENT_HEADINGS = [
    "# Project Assessment",
    "## 1. Executive Summary",
    "## 2. Inspected Sources",
    "## 3. Project Areas and Responsibility Boundaries",
    "## 4. Feature Inventory",
    "## 5. Placeholder, Stub, and Skeleton Analysis",
    "## 6. Technical Debt and Maintenance Risks",
    "## 7. Broken or Missing Integrations",
    "## 8. Test, CI, and Validation Gaps",
    "## 9. Security, Secret, and Governance Findings",
    "## 10. Operational Readiness and Observability",
    "## 11. Alignment with the Main Plan",
    "## 12. Assessment Feedback for Step 2",
    "## 13. Prioritized Remediation and Planning Signals",
]

INDEX_HEADINGS = [
    "# Sub-Planning Index",
    "## 1. Purpose",
    "## 2. Source Master Plan",
    "## 3. Phase and Sub-Plan Map",
    "## 4. Prioritized Elaboration Order",
    "## 5. Out-of-Scope or Deferred Topics",
    "## 6. Coverage Check",
    "## 7. Repository Inspection Notes",
]

SUBPLAN_HEADINGS = [
    "## 1. Context",
    "## 2. Goal",
    "## 3. Description",
    "## 4. Scope",
    "## 5. Out of Scope",
    "## 6. Current Repository Evidence",
    "## 7. Planned Work Breakdown",
    "## 8. Acceptance Criteria",
    "## 9. Validation and Test Approach",
    "## 10. Dependencies and Sequencing",
    "## 11. Risks and Mitigations",
    "## 12. Desired End State",
    "## 13. Transition Criteria to the Next Sub-Phase",
]

AUDIT_HEADINGS = [
    "# Sub-Planning Audit",
    "## 1. Audit Summary",
    "## 2. Inspected Sources",
    "## 3. Main Phase Coverage Analysis",
    "## 4. Sub-Plan File Inventory",
    "## 5. Naming and Ordering Check",
    "## 6. Index Consistency Check",
    "## 7. Required Section Structure Check",
    "## 8. Content Quality and Actionability Analysis",
    "## 9. Scope Drift and Architectural Consistency Analysis",
    "## 10. Readiness Realism",
    "## 11. Security and Governance Findings",
    "## 12. Step 4 Readiness Assessment",
    "## 13. Prioritized Fix List",
    "## 14. Recommended Next Command / Prompt",
    "## 15. Audit Result",
]

FIX_LIST_HEADING = "## 13. Prioritized Fix List"

# --- Evidence-engine vocabulary (optional comprehension/ontology/readiness gates) ---
# The generated `.qb/project-comprehension.md` artifact follows this heading order;
# see shared/references/project-comprehension-methods.md for the methodology.
COMPREHENSION_HEADINGS = [
    "# Project Comprehension",
    "## 1. Understanding Goals and Competency Questions",
    "## 2. Evidence Register and Confidence",
    "## 3. Domain-to-Code Trace Map",
    "## 4. Structure, Data, and Runtime Flow Model",
    "## 5. Intended vs Implemented Architecture",
    "## 6. Change History, Hotspots, and Ownership Signals",
    "## 7. Quality Attribute Scenarios and Tradeoffs",
    "## 8. Open Hypotheses and Validation Probes",
]
ALLOWED_EVIDENCE_TYPES = {
    "source",
    "test",
    "runtime",
    "history",
    "configuration",
    "documentation",
    "user-confirmed",
}
ALLOWED_CONFIDENCE_VALUES = {"confirmed", "probable", "tentative", "contradicted"}
ALLOWED_CLAIM_TYPES = {
    "structural",
    "behavioral",
    "historical",
    "configuration",
    "user_intent",
    "architectural",
}
ALLOWED_ARCHITECTURE_STATUSES = {"convergent", "divergent", "absent", "unmodeled", "uncertain"}
ALLOWED_ONTOLOGY_QUESTION_STATUSES = {"answered", "partially_answered", "open", "contradicted"}
EVIDENCE_OPEN_FINDING_STATUSES = {"open", "accepted"}
ALLOWED_READINESS_STATUSES = {
    "READY",
    "READY_WITH_WARNINGS",
    "NEEDS_REPAIR",
    "BLOCKED",
    "COMPLETE",
    "SUPERSEDED",
    "DEFERRED",
}
READY_READINESS_STATUSES = {"READY", "READY_WITH_WARNINGS"}
COMPLETED_READINESS_STATUSES = {"COMPLETE", "SUPERSEDED", "DEFERRED"}
ALLOWED_DEPENDENCY_STATES = {"satisfied", "independent", "blocked", "unknown"}
READINESS_HEADERS = [
    "Sub-Plan Path",
    "Status",
    "Finding IDs",
    "Dependency State",
    "Reason",
    "Required Repair",
]
READINESS_HEADING = "## 12. Step 4 Readiness Assessment"
NOT_APPLICABLE_PREFIX = "NOT_APPLICABLE:"
NO_UNRESOLVED_HYPOTHESES_PREFIX = "NO_UNRESOLVED_HYPOTHESES:"
UNKNOWN_PREFIX = "UNKNOWN:"
UNKNOWN_CELL_VALUES = {"", "-", "n/a", "na", "none", "unknown", "unclear", "not found", "not evidenced"}

FOLDER_RE = re.compile(r"^phase-(\d+)-plans$")
SUBPLAN_RE = re.compile(r"^phase-(\d+)\.(\d+)-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
INDEX_REF_RE = re.compile(
    r"(?:\./)?(?:\.qb/)?phase-\d+-plans/phase-\d+\.\d+-[a-z0-9]+(?:-[a-z0-9]+)*\.md"
)
MAIN_PHASE_RE = re.compile(r"\bPhase\s*-?\s*(\d+)\b", re.IGNORECASE)
ROADMAP_HEADING = "## 6. Phased Master Roadmap"
ROADMAP_TABLE_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|", re.MULTILINE)
ROADMAP_HEADING_PHASE_RE = re.compile(r"^#{3,6}\s*Phase\s*-?\s*(\d+)\b", re.MULTILINE | re.IGNORECASE)
H1_SUBPLAN_RE = re.compile(r"^# Phase\s+(\d+)\.(\d+)\s+[—-]\s+.+$", re.MULTILINE)
SECTION_RE = re.compile(r"^(##\s+\d+\.\s+.+)$", re.MULTILINE)
AUDIT_FIX_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\|?\s*(AUDIT-FIX-\d+)\s*(?:\||:|—|–|-)\s*(P0|P1|P2|P3)\b",
    re.MULTILINE,
)

# Optional per-finding lifecycle status carried on a fix-list row as the pipe-
# delimited field immediately after the severity: "AUDIT-FIX-NN | PX | <status> |
# <title>". Only OPEN and ACCEPTED findings block the Step 4 gate; RESOLVED and
# NOT_APPLICABLE are recorded but do not gate. A row with no recognized status field
# defaults to OPEN, so legacy audits keep their original status-unaware blocking
# behavior. ACCEPTED means a risk is knowingly carried forward and stays visible.
FINDING_STATUSES = ("open", "accepted", "resolved", "not_applicable")
BLOCKING_FINDING_STATUSES = ("open", "accepted")

# Single source of the length-bounded secret patterns lives in analyzer_core;
# the planning validator is now a caller, not the owner (Phase 1.3 refactor).
SECRET_PATTERNS = _core.SECRET_PATTERNS

PLACEHOLDER_PATTERNS = [
    ("todo", re.compile(r"\bTODO\b", re.IGNORECASE)),
    ("tbd", re.compile(r"\bTBD\b", re.IGNORECASE)),
    ("fixme", re.compile(r"\bFIXME\b", re.IGNORECASE)),
    ("lorem_ipsum", re.compile(r"\blorem ipsum\b", re.IGNORECASE)),
    ("angle_placeholder", re.compile(r"<(?:TODO|TBD|PLACEHOLDER)[^>]*>", re.IGNORECASE)),
    ("brace_placeholder", re.compile(r"\{\{[^{}]*(?:TODO|TBD|PLACEHOLDER)[^{}]*\}\}", re.IGNORECASE)),
]

REPEATED_SENTENCE_MIN_COUNT = 5
REPEATED_SENTENCE_MIN_LENGTH = 80
ALLOWED_REPEATED_SENTENCE_FRAGMENTS = (
    "secret",
    "token",
    "credential",
    "private key",
    "local env",
    "source code",
    "config, test",
    "plan file",
    "plan files",
    "real secret",
)


@dataclass
class ValidationState:
    root: Path
    mode: str
    strict: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, int | str] = field(default_factory=dict)

    @property
    def planner_docs(self) -> Path:
        return self.root / ".qb"

    def rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def read_text(path: Path, state: ValidationState) -> str | None:
    if not path.exists():
        state.error(f"missing_file={state.rel(path)}")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        state.error(f"non_utf8_file={state.rel(path)}")
    except OSError as exc:
        state.error(f"read_error={state.rel(path)}:{exc}")
    return None


def _mask_fenced_regions(text: str) -> str:
    """Blank the visible content of fenced code blocks, preserving offsets.

    Returns a string of identical length where every character inside a ``` or ~~~
    fenced block (including the fence-marker lines) is replaced by a space, while
    newlines are kept. Heading detection runs over the masked text so a heading-like
    line such as ``## 13. ...`` quoted inside a code fence is not mistaken for a real
    document heading; bodies are still sliced from the original text by the same
    offsets.

    Only *balanced* fences are masked: an opening marker's region is masked only once
    a matching closing marker is found. A fence that opens and never closes (malformed
    markdown) is left literal rather than masking the rest of the document, so a
    dangling fence cannot hide a real heading or fix-list finding from the Step 4 gate
    (which would otherwise fail open).
    """

    def _mask(line: str) -> str:
        return "".join(ch if ch in "\r\n" else " " for ch in line)

    out: list[str] = []
    pending: list[str] = []  # lines buffered inside an as-yet-unclosed fence
    in_fence = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        is_marker = stripped.startswith("```") or stripped.startswith("~~~")
        if not in_fence:
            if is_marker:
                in_fence = True
                pending = [line]
            else:
                out.append(line)
        else:
            pending.append(line)
            if is_marker:
                # closing marker: the region is balanced -> mask the whole block
                out.extend(_mask(buf) for buf in pending)
                pending = []
                in_fence = False
    if in_fence:
        # unterminated fence: keep the buffered remainder visible, do not mask to EOF
        out.extend(pending)
    return "".join(out)


def validate_heading_order(text: str, headings: list[str], path: Path, state: ValidationState) -> None:
    masked = _mask_fenced_regions(text)
    target_headings = set(headings)
    heading_positions: dict[str, list[int]] = {heading: [] for heading in target_headings}
    offset = 0
    for line in masked.splitlines(keepends=True):
        stripped = line.strip()
        if stripped in heading_positions:
            heading_positions[stripped].append(offset + line.find(stripped))
        offset += len(line)

    last_pos = -1
    for heading in headings:
        positions = heading_positions[heading]
        if not positions:
            state.error(f"missing_heading={state.rel(path)}::{heading}")
            continue
        if len(positions) > 1:
            state.error(f"duplicate_heading={state.rel(path)}::{heading}::{len(positions)}")
        pos = positions[0]
        if pos < last_pos:
            state.error(f"heading_out_of_order={state.rel(path)}::{heading}")
        last_pos = pos


def markdown_section(text: str, heading: str) -> str:
    masked = _mask_fenced_regions(text)
    start = masked.find(heading)
    if start == -1:
        return ""
    body_start = start + len(heading)
    next_match = re.search(r"^##\s+\d+\.\s+", masked[body_start:], flags=re.MULTILINE)
    body_end = body_start + next_match.start() if next_match else len(text)
    return text[body_start:body_end].strip()


def extract_main_phase_numbers(text: str) -> list[int]:
    roadmap = markdown_section(text, ROADMAP_HEADING)
    if roadmap:
        table_numbers = sorted({int(match.group(1)) for match in ROADMAP_TABLE_ROW_RE.finditer(roadmap)})
        if table_numbers:
            return table_numbers

        heading_numbers = sorted({int(match.group(1)) for match in ROADMAP_HEADING_PHASE_RE.finditer(roadmap)})
        if heading_numbers:
            return heading_numbers

        return sorted({int(match.group(1)) for match in MAIN_PHASE_RE.finditer(roadmap)})

    return []


def collect_phase_folders(state: ValidationState) -> dict[int, Path]:
    folders: dict[int, Path] = {}
    if not state.planner_docs.exists():
        state.error("missing_directory=.qb")
        return folders

    for folder in sorted(state.planner_docs.glob("phase-*-plans")):
        if not folder.is_dir():
            continue
        match = FOLDER_RE.match(folder.name)
        if not match:
            state.error(f"invalid_phase_folder={state.rel(folder)}")
            continue
        phase = int(match.group(1))
        if phase in folders:
            state.error(f"duplicate_phase_folder=phase-{phase}-plans")
        folders[phase] = folder
    return folders


def collect_subplans(state: ValidationState) -> list[tuple[int | None, int | None, Path]]:
    result: list[tuple[int | None, int | None, Path]] = []
    for folder in sorted(state.planner_docs.glob("phase-*-plans")):
        if not folder.is_dir():
            continue
        folder_match = FOLDER_RE.match(folder.name)
        folder_phase = int(folder_match.group(1)) if folder_match else None
        for path in sorted(folder.glob("*.md")):
            match = SUBPLAN_RE.match(path.name)
            if not match:
                state.error(f"invalid_subplan_filename={state.rel(path)}")
                result.append((folder_phase, None, path))
                continue
            file_phase = int(match.group(1))
            subphase = int(match.group(2))
            if folder_phase is not None and file_phase != folder_phase:
                state.error(
                    f"folder_file_phase_mismatch={state.rel(path)}::folder={folder_phase}::file={file_phase}"
                )
            result.append((file_phase, subphase, path))
    return result


def section_body(text: str, heading: str) -> str:
    return markdown_section(text, heading)


def normalized_body(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def split_sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", compact) if item.strip()]


def is_allowed_repeated_sentence(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(fragment in lowered for fragment in ALLOWED_REPEATED_SENTENCE_FRAGMENTS)


def add_repeated_sentence_candidates(
    state: ValidationState,
    path: Path,
    text: str,
    repeated_sentences: dict[str, list[str]],
) -> None:
    for sentence in split_sentences(text):
        if len(sentence) < REPEATED_SENTENCE_MIN_LENGTH:
            continue
        if is_allowed_repeated_sentence(sentence):
            continue
        repeated_sentences[sentence].append(state.rel(path))


def validate_step1(state: ValidationState) -> list[int]:
    main_path = state.planner_docs / "main-planning.md"
    text = read_text(main_path, state)
    if text is None:
        state.metrics["main_phase_count"] = 0
        return []

    validate_heading_order(text, STEP1_HEADINGS, main_path, state)
    phases = extract_main_phase_numbers(text)
    state.metrics["main_phase_count"] = len(phases)
    if not phases:
        state.error("main_plan_has_no_detected_phases=.qb/main-planning.md")
    return phases


def validate_assessment_optional(state: ValidationState) -> None:
    assessment_path = state.planner_docs / "assessment.md"
    state.metrics["assessment_exists"] = "true" if assessment_path.exists() else "false"
    if not assessment_path.exists():
        return

    text = read_text(assessment_path, state)
    if text is None:
        return

    validate_heading_order(text, ASSESSMENT_HEADINGS, assessment_path, state)


def validate_index(state: ValidationState) -> set[str]:
    index_path = state.planner_docs / "sub-planning-index.md"
    text = read_text(index_path, state)
    if text is None:
        state.metrics["index_reference_count"] = 0
        return set()

    validate_heading_order(text, INDEX_HEADINGS, index_path, state)
    refs = set()
    for match in INDEX_REF_RE.finditer(text):
        ref = match.group(0)
        if ref.startswith("./"):
            ref = ref[2:]
        if not ref.startswith(".qb/"):
            ref = f".qb/{ref}"
        refs.add(ref)
    state.metrics["index_reference_count"] = len(refs)
    return refs


def validate_subplan_structure(
    state: ValidationState,
    phase: int | None,
    subphase: int | None,
    path: Path,
    repeated_bodies: dict[str, list[str]],
    repeated_sentences: dict[str, list[str]],
) -> None:
    text = read_text(path, state)
    if text is None:
        return

    h1_match = H1_SUBPLAN_RE.search(text)
    if not h1_match:
        state.error(f"missing_or_invalid_h1={state.rel(path)}")
    else:
        h1_phase = int(h1_match.group(1))
        h1_subphase = int(h1_match.group(2))
        if phase is not None and h1_phase != phase:
            state.error(f"h1_phase_mismatch={state.rel(path)}::h1={h1_phase}::file={phase}")
        if subphase is not None and h1_subphase != subphase:
            state.error(f"h1_subphase_mismatch={state.rel(path)}::h1={h1_subphase}::file={subphase}")

    validate_heading_order(text, SUBPLAN_HEADINGS, path, state)

    for required in SUBPLAN_HEADINGS:
        body = section_body(text, required)
        if required in text and len(body) < 20:
            state.error(f"empty_or_too_short_section={state.rel(path)}::{required}")
        for pattern_name, pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(body):
                state.warning(f"placeholder_text={state.rel(path)}::{required}::pattern={pattern_name}")

    for heading in ("## 3. Description", "## 7. Planned Work Breakdown"):
        body = normalized_body(section_body(text, heading))
        if len(body) >= 160:
            repeated_bodies[f"{heading}:{body}"].append(state.rel(path))

    for heading in ("## 3. Description", "## 6. Current Repository Evidence", "## 8. Acceptance Criteria", "## 11. Risks and Mitigations"):
        add_repeated_sentence_candidates(state, path, section_body(text, heading), repeated_sentences)


def validate_step2(state: ValidationState) -> None:
    main_phases = validate_step1(state)
    validate_assessment_optional(state)
    index_refs = validate_index(state)
    folders = collect_phase_folders(state)
    subplans = collect_subplans(state)

    state.metrics["phase_folder_count"] = len(folders)
    state.metrics["subplan_count"] = len([item for item in subplans if item[1] is not None])

    if main_phases:
        for phase in main_phases:
            if phase not in folders:
                state.error(f"missing_phase_folder=.qb/phase-{phase}-plans")
        for phase in sorted(folders):
            if phase not in main_phases:
                state.warning(f"extra_phase_folder_without_main_phase=.qb/phase-{phase}-plans")

    actual_refs = {state.rel(path) for _, subphase, path in subplans if subphase is not None}
    for ref in sorted(actual_refs - index_refs):
        state.error(f"unindexed_subplan={ref}")
    for ref in sorted(index_refs - actual_refs):
        state.error(f"missing_index_target={ref}")

    seen: set[tuple[int, int]] = set()
    per_phase: dict[int, list[int]] = defaultdict(list)
    repeated_bodies: dict[str, list[str]] = defaultdict(list)
    repeated_sentences: dict[str, list[str]] = defaultdict(list)

    for phase, subphase, path in subplans:
        if phase is None or subphase is None:
            continue
        key = (phase, subphase)
        if key in seen:
            state.error(f"duplicate_subplan_number=phase-{phase}.{subphase}")
        seen.add(key)
        per_phase[phase].append(subphase)
        validate_subplan_structure(state, phase, subphase, path, repeated_bodies, repeated_sentences)

    for phase, folder in sorted(folders.items()):
        numbers = sorted(per_phase.get(phase, []))
        if not numbers:
            state.error(f"phase_has_no_subplans={state.rel(folder)}")
            continue
        expected = list(range(1, max(numbers) + 1))
        if numbers != expected:
            state.error(f"subplan_numbering_gap=phase-{phase}::expected={expected}::actual={numbers}")

    for key, paths in sorted(repeated_bodies.items()):
        if len(paths) >= 3:
            heading = key.split(":", 1)[0]
            joined = ",".join(paths)
            state.warning(f"repeated_section_body={heading}::files={joined}")

    for sentence, paths in sorted(repeated_sentences.items()):
        if len(paths) >= REPEATED_SENTENCE_MIN_COUNT:
            preview = sentence[:120].replace("=", "-")
            joined = ",".join(paths[:10])
            state.warning(f"repeated_boilerplate_sentence=count:{len(paths)}::text={preview}::files={joined}")


def validate_step3_preflight(state: ValidationState) -> None:
    validate_step2(state)
    audit_path = state.planner_docs / "sub-planning-audit.md"
    state.metrics["audit_exists"] = "true" if audit_path.exists() else "false"
    if state.mode == "all" and not audit_path.exists():
        state.error("missing_file=.qb/sub-planning-audit.md")
    if audit_path.exists():
        text = read_text(audit_path, state)
        if text is not None:
            validate_heading_order(text, AUDIT_HEADINGS, audit_path, state)
            validate_audit_section_depth(text, audit_path, state)


def extract_audit_status(text: str) -> str | None:
    masked = _mask_fenced_regions(text)
    status_pattern = re.compile(
        r"(?:overall audit status|audit status|final status|status)"
        r"\s*[:：-]\s*(PASS_WITH_WARNINGS|BLOCKED|PASS)\b",
        re.IGNORECASE,
    )
    match = status_pattern.search(masked)
    if match:
        return match.group(1).upper()

    for line in masked.splitlines():
        stripped = line.strip(" -*`|:")
        if stripped in {"PASS", "PASS_WITH_WARNINGS", "BLOCKED"}:
            return stripped
    return None


def count_audit_severities(text: str) -> dict[str, int]:
    fix_section = markdown_section(text, FIX_LIST_HEADING)
    severities = [severity for _, severity in AUDIT_FIX_RE.findall(fix_section)]
    return _core.count_severities(severities)


def _normalize_finding_status(row_remainder: str) -> str:
    """Read the lifecycle status from the field right after a fix-list row's severity.

    The status, when present, is the pipe-delimited field immediately following the
    severity ("... | PX | <status> | <title>"). It is read as a status only when a
    title field follows it: a legacy 3-field row ("... | PX | <title>") has no trailing
    field, so its single field is the title -- a title that happens to equal a status
    keyword must not silently un-block a real finding (the Step 4 gate must never fail
    open). A status word appearing later inside the free-text title never reclassifies a
    finding either. Absent or unrecognized -> 'open' (legacy status-unaware behavior).
    """
    rest = row_remainder.lstrip()
    if not rest.startswith("|"):
        return "open"
    parts = rest[1:].split("|")
    if len(parts) < 2:
        # Only a single field after the severity: it is the title, not a status.
        return "open"
    field = parts[0].strip().lower().replace(" ", "_")
    if field in FINDING_STATUSES:
        return field
    if field in ("n/a", "na"):
        return "not_applicable"
    return "open"


def parse_audit_findings(text: str) -> list[tuple[str, str, str]]:
    """Parse the fix-list section into (id, severity, status) triples.

    Severity *counting* stays in count_audit_severities (status-unaware, all
    findings); this adds the optional per-finding lifecycle status consumed only by
    the Step 4 readiness gate.
    """
    fix_section = markdown_section(text, FIX_LIST_HEADING)
    findings: list[tuple[str, str, str]] = []
    for line in fix_section.splitlines():
        match = AUDIT_FIX_RE.match(line)
        if not match:
            continue
        fid = match.group(1)
        severity = match.group(2).upper()
        status = _normalize_finding_status(line[match.end():])
        findings.append((fid, severity, status))
    return findings


def validate_step4_readiness(state: ValidationState) -> None:
    validate_step3_preflight(state)
    audit_path = state.planner_docs / "sub-planning-audit.md"
    text = read_text(audit_path, state)
    if text is None:
        state.metrics["audit_status"] = "missing"
        return

    status = extract_audit_status(text)
    state.metrics["audit_status"] = status or "unknown"
    if status is None:
        state.error("audit_status_missing=.qb/sub-planning-audit.md")
    elif status == "BLOCKED":
        state.error("step4_blocked_by_audit_status=BLOCKED")

    # Total severity counts (every finding, status-unaware) -- reporting metrics.
    severity_counts = count_audit_severities(text)
    for severity, count in severity_counts.items():
        state.metrics[f"{severity.lower()}_findings"] = count

    # Status-aware gate: only OPEN/ACCEPTED findings gate Step 4. RESOLVED and
    # NOT_APPLICABLE findings are recorded but do not block, so a remediated P0 no
    # longer forces the gate shut. Rows with no status default to OPEN, preserving
    # legacy blocking behavior exactly.
    findings = parse_audit_findings(text)
    status_tally: dict[str, int] = defaultdict(int)
    for _fid, _severity, finding_status in findings:
        status_tally[finding_status] += 1
    for finding_status, count in sorted(status_tally.items()):
        state.metrics[f"finding_status_{finding_status}"] = count

    blocking = _core.count_severities(
        [severity for _fid, severity, finding_status in findings
         if finding_status in BLOCKING_FINDING_STATUSES]
    )
    state.metrics["blocking_p0_findings"] = blocking["P0"]
    state.metrics["blocking_p1_findings"] = blocking["P1"]
    if blocking["P0"] or blocking["P1"]:
        state.metrics["execution_queue_state"] = "blocked"
    elif blocking["P2"] or blocking["P3"]:
        state.metrics["execution_queue_state"] = "warnings"
    else:
        state.metrics["execution_queue_state"] = "clear"

    if blocking["P0"] or blocking["P1"]:
        state.error(
            f"step4_blocked_by_high_severity_findings=P0:{blocking['P0']},P1:{blocking['P1']}"
        )
    if status == "PASS_WITH_WARNINGS" and (blocking["P2"] or blocking["P3"]):
        state.warning(
            f"step4_has_nonblocking_warnings=P2:{blocking['P2']},P3:{blocking['P3']}"
        )

    # Optional Step-4 readiness-row gate: only runs when the audit carries a
    # `## 12. Step 4 Readiness Assessment` table with the READINESS_HEADERS shape.
    readiness_rows = parse_readiness_rows(text)
    validate_readiness_rows(readiness_rows, audit_path, state, findings)


# --- Evidence engine: markdown-table parser + evidence-quality helpers ---------------
# Ported (under qb vocabulary) so the optional comprehension/ontology/readiness gates
# below can read tabular evidence. Routing/parsing only -- the gates emit warnings.


def markdown_tables(section: str) -> list[tuple[list[str], list[dict[str, str]]]]:
    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    lines = section.splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        block: list[str] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            block.append(lines[index].strip())
            index += 1
        if len(block) < 2:
            continue
        headers = [cell.strip() for cell in block[0].strip("|").split("|")]
        separator = [cell.strip() for cell in block[1].strip("|").split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
            continue
        rows: list[dict[str, str]] = []
        for line in block[2:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            rows.append(dict(zip(headers, cells)))
        tables.append((headers, rows))
    return tables


def canonical_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def headers_match(headers: list[str], required: list[str]) -> bool:
    return [canonical_header(item) for item in headers[: len(required)]] == [
        canonical_header(item) for item in required
    ]


def row_value(row: dict[str, str], *names: str) -> str:
    canonical = {canonical_header(key): value for key, value in row.items()}
    for name in names:
        value = canonical.get(canonical_header(name))
        if value is not None:
            return value.strip()
    return ""


def split_cell_values(value: str | None) -> list[str]:
    if value is None:
        return []
    items = re.split(r"[,;/]+|\band\b", value, flags=re.IGNORECASE)
    return [item.strip().lower() for item in items if item.strip()]


def normalized_cell(value: str | None) -> str:
    return (value or "").strip().strip("`").lower()


def cell_has_evidence(value: str | None) -> bool:
    return normalized_cell(value) not in UNKNOWN_CELL_VALUES


def section_has_table(section: str) -> bool:
    return any(rows for _, rows in markdown_tables(section))


def marker_reason(value: str, prefix: str) -> str | None:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def valid_marker_reason(value: str, prefix: str) -> bool:
    reason = marker_reason(value, prefix)
    return reason is not None and cell_has_evidence(reason) and len(reason) >= 8


def unknown_marker_has_next_probe(value: str) -> bool:
    reason = marker_reason(value, UNKNOWN_PREFIX)
    if reason is None or not cell_has_evidence(reason):
        return False
    return "next probe" in reason.lower() and len(reason) >= 12


def evidence_is_direct_for_claim(claim_type: str, evidence_type: str, evidence_source: str) -> bool:
    if not cell_has_evidence(evidence_source):
        return False
    if claim_type == "structural":
        return evidence_type == "source"
    if claim_type == "configuration":
        return evidence_type == "configuration"
    return False


def has_independent_evidence(evidence_type: str, evidence_source: str) -> bool:
    evidence_types = {item for item in split_cell_values(evidence_type) if item in ALLOWED_EVIDENCE_TYPES}
    locators = {item for item in split_cell_values(evidence_source) if cell_has_evidence(item)}
    return len(evidence_types) >= 2 and len(locators) >= 2


# --- Optional comprehension doc gate (`.qb/project-comprehension.md`) -----------------
# Dormant unless the artifact exists; all findings are warnings (errors under --strict).


def validate_optional_comprehension_doc(state: ValidationState) -> None:
    path = state.planner_docs / "project-comprehension.md"
    state.metrics["comprehension_exists"] = "true" if path.exists() else "false"
    if not path.exists():
        return

    text = read_text(path, state)
    if text is None:
        return

    validate_heading_order(text, COMPREHENSION_HEADINGS, path, state)

    question_section = markdown_section(text, "## 1. Understanding Goals and Competency Questions")
    if "CQ-" not in question_section and "question id" not in question_section.lower():
        state.warning(f"comprehension_missing_question={state.rel(path)}")

    evidence_section = markdown_section(text, "## 2. Evidence Register and Confidence")
    evidence_rows: list[dict[str, str]] = []
    for _, rows in markdown_tables(evidence_section):
        evidence_rows.extend(rows)
        for row in rows:
            evidence_id = row.get("Evidence ID") or row.get("ID") or "unknown"
            evidence_type = normalized_cell(row_value(row, "Evidence type", "Evidence Type"))
            evidence_source = row_value(row, "Evidence source", "Evidence Source")
            confidence = normalized_cell(row.get("Confidence"))
            claim_type = normalized_cell(row_value(row, "Claim Type", "Type")) or "structural"
            if claim_type not in ALLOWED_CLAIM_TYPES:
                state.warning(f"invalid_claim_type={state.rel(path)}::{claim_type}")
            if evidence_type and evidence_type not in ALLOWED_EVIDENCE_TYPES:
                state.warning(f"invalid_evidence_type={state.rel(path)}::{evidence_type}")
            if confidence and confidence not in ALLOWED_CONFIDENCE_VALUES:
                state.warning(f"invalid_confidence={state.rel(path)}::{confidence}")
            if confidence == "confirmed" and not cell_has_evidence(evidence_source):
                state.warning(f"high_confidence_without_evidence={state.rel(path)}::{evidence_id}")
            if confidence == "confirmed" and cell_has_evidence(evidence_source):
                if claim_type == "behavioral" and evidence_type not in {"test", "runtime"}:
                    if not has_independent_evidence(evidence_type, evidence_source):
                        state.warning(
                            f"confirmed_behavioral_claim_needs_test_or_runtime={state.rel(path)}::{evidence_id}"
                        )
                elif claim_type == "historical" and evidence_type != "history":
                    state.warning(f"historical_claim_requires_history_evidence={state.rel(path)}::{evidence_id}")
                elif claim_type == "user_intent" and evidence_type != "user-confirmed":
                    state.warning(f"user_intent_claim_requires_user_confirmed_evidence={state.rel(path)}::{evidence_id}")
                elif claim_type == "architectural":
                    if evidence_type not in {"source", "configuration"} and not has_independent_evidence(
                        evidence_type, evidence_source
                    ):
                        state.warning(f"architectural_claim_needs_relation_evidence={state.rel(path)}::{evidence_id}")
                elif claim_type in {"structural", "configuration"}:
                    if not evidence_is_direct_for_claim(claim_type, evidence_type, evidence_source):
                        if not has_independent_evidence(evidence_type, evidence_source):
                            state.warning(f"confirmed_{claim_type}_claim_needs_direct_evidence={state.rel(path)}::{evidence_id}")
    if not evidence_rows:
        state.warning(f"comprehension_missing_evidence_row={state.rel(path)}")

    trace_section = markdown_section(text, "## 3. Domain-to-Code Trace Map")
    trace_has_rows = False
    if marker_reason(trace_section, NOT_APPLICABLE_PREFIX) is not None and not valid_marker_reason(
        trace_section, NOT_APPLICABLE_PREFIX
    ):
        state.warning(f"invalid_not_applicable_marker={state.rel(path)}::## 3. Domain-to-Code Trace Map")
    if marker_reason(trace_section, UNKNOWN_PREFIX) is not None and not unknown_marker_has_next_probe(trace_section):
        state.warning(f"unknown_marker_missing_next_probe={state.rel(path)}::## 3. Domain-to-Code Trace Map")
    for _, rows in markdown_tables(trace_section):
        trace_has_rows = trace_has_rows or bool(rows)
        for row in rows:
            trace_id = row.get("Trace ID") or row.get("ID") or "unknown"
            confidence = normalized_cell(row.get("Confidence"))
            if confidence and confidence not in ALLOWED_CONFIDENCE_VALUES:
                state.warning(f"invalid_confidence={state.rel(path)}::{confidence}")
            has_code_anchor = cell_has_evidence(row.get("Entry points")) or cell_has_evidence(row.get("Core implementation"))
            has_test_anchor = cell_has_evidence(row.get("Tests"))
            if not has_code_anchor and not has_test_anchor:
                state.warning(f"trace_missing_code_or_test_anchor={state.rel(path)}::{trace_id}")
    if not trace_has_rows and not valid_marker_reason(trace_section, NOT_APPLICABLE_PREFIX):
        state.warning(f"comprehension_missing_trace={state.rel(path)}")

    architecture_section = markdown_section(text, "## 5. Intended vs Implemented Architecture")
    architecture_has_rows = False
    if marker_reason(architecture_section, NOT_APPLICABLE_PREFIX) is not None and not valid_marker_reason(
        architecture_section, NOT_APPLICABLE_PREFIX
    ):
        state.warning(f"invalid_not_applicable_marker={state.rel(path)}::## 5. Intended vs Implemented Architecture")
    if marker_reason(architecture_section, UNKNOWN_PREFIX) is not None and not unknown_marker_has_next_probe(
        architecture_section
    ):
        state.warning(
            f"unknown_marker_missing_next_probe={state.rel(path)}::## 5. Intended vs Implemented Architecture"
        )
    for _, rows in markdown_tables(architecture_section):
        architecture_has_rows = architecture_has_rows or bool(rows)
        for row in rows:
            status = normalized_cell(row.get("Status"))
            if status and status not in ALLOWED_ARCHITECTURE_STATUSES:
                state.warning(f"invalid_architecture_status={state.rel(path)}::{status}")
    if not architecture_has_rows and not valid_marker_reason(architecture_section, NOT_APPLICABLE_PREFIX):
        state.warning(f"comprehension_missing_architecture={state.rel(path)}")

    hypothesis_section = markdown_section(text, "## 8. Open Hypotheses and Validation Probes")
    hypothesis_has_rows = False
    if marker_reason(hypothesis_section, NO_UNRESOLVED_HYPOTHESES_PREFIX) is not None and not valid_marker_reason(
        hypothesis_section, NO_UNRESOLVED_HYPOTHESES_PREFIX
    ):
        state.warning(f"invalid_no_unresolved_hypotheses_marker={state.rel(path)}")
    if marker_reason(hypothesis_section, UNKNOWN_PREFIX) is not None and not unknown_marker_has_next_probe(
        hypothesis_section
    ):
        state.warning(
            f"unknown_marker_missing_next_probe={state.rel(path)}::## 8. Open Hypotheses and Validation Probes"
        )
    for _, rows in markdown_tables(hypothesis_section):
        hypothesis_has_rows = hypothesis_has_rows or bool(rows)
        for row in rows:
            hypothesis_id = row.get("Hypothesis ID") or row.get("ID") or "unknown"
            confidence = normalized_cell(row.get("Confidence"))
            if confidence and confidence not in ALLOWED_CONFIDENCE_VALUES:
                state.warning(f"invalid_confidence={state.rel(path)}::{confidence}")
            if not cell_has_evidence(row.get("Next probe")):
                state.warning(f"open_hypothesis_missing_next_probe={state.rel(path)}::{hypothesis_id}")
    if not hypothesis_has_rows and not valid_marker_reason(hypothesis_section, NO_UNRESOLVED_HYPOTHESES_PREFIX):
        state.warning(f"comprehension_missing_hypothesis_or_marker={state.rel(path)}")


# --- Optional ontology competency-question gate (`.qb/project-ontology.md`) -----------


def validate_ontology_competency_questions(text: str, path: Path, state: ValidationState) -> None:
    heading = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#") and "competency question" in stripped.lower():
            heading = line.strip()
            break
    if heading is None:
        return
    question_section = markdown_section(text, heading)
    for _, rows in markdown_tables(question_section):
        for row in rows:
            status = normalized_cell(row.get("Status"))
            question_id = row.get("Question ID") or row.get("ID") or row.get("Question") or "unknown"
            if status and status not in ALLOWED_ONTOLOGY_QUESTION_STATUSES:
                state.warning(f"invalid_ontology_question_status={state.rel(path)}::{status}")
            if status in {"answered", "partially_answered"} and not cell_has_evidence(row.get("Evidence")):
                state.warning(f"ontology_question_missing_evidence={state.rel(path)}::{question_id}")


def validate_optional_ontology_doc(state: ValidationState) -> None:
    path = state.planner_docs / "project-ontology.md"
    state.metrics["ontology_exists"] = "true" if path.exists() else "false"
    if not path.exists():
        return
    text = read_text(path, state)
    if text is None:
        return
    validate_ontology_competency_questions(text, path, state)


# --- Audit-section-depth + Step-4 readiness-row gates (optional, additive) ------------


def validate_audit_section_depth(text: str, path: Path, state: ValidationState) -> None:
    """Warn when an audit section is headings-only (no real content).

    A warning (not an error) so it never regresses a non-strict ``make check``; under
    ``--strict`` it becomes a failure, which is the "reject headings-only audits" gate.
    """
    for heading in AUDIT_HEADINGS:
        if not heading.startswith("## "):
            continue  # skip the H1 document title
        body = markdown_section(text, heading)
        if len(body.strip()) < 20:
            state.warning(f"empty_or_too_short_audit_section={state.rel(path)}::{heading}")


def parse_readiness_rows(text: str) -> list[dict[str, str]]:
    """Return the rows of the Step-4 readiness table, or [] when it is absent.

    Optional/additive: a missing readiness table is NOT an error, so existing audit
    docs without the table are unaffected.
    """
    section = markdown_section(text, READINESS_HEADING)
    for headers, rows in markdown_tables(section):
        if headers_match(headers, READINESS_HEADERS):
            return rows
    return []


def validate_readiness_rows(
    rows: list[dict[str, str]],
    path: Path,
    state: ValidationState,
    findings: list[tuple[str, str, str]],
) -> None:
    by_id = {fid: (severity, status) for fid, severity, status in findings}
    seen: dict[str, str] = {}
    ready_count = 0
    terminal_count = 0

    if not rows:
        return

    for row in rows:
        subplan = row_value(row, "Sub-Plan Path", "Sub-plan Path", "Subplan Path")
        status = row_value(row, "Status").upper()
        finding_ids = row_value(row, "Finding IDs", "Finding ID")
        dependency = normalized_cell(row_value(row, "Dependency State"))

        if status not in ALLOWED_READINESS_STATUSES:
            state.warning(f"invalid_readiness_status={state.rel(path)}::{status or 'missing'}")
        if dependency not in ALLOWED_DEPENDENCY_STATES:
            state.warning(f"invalid_dependency_state={state.rel(path)}::{dependency or 'missing'}")

        key = subplan or "unknown"
        previous = seen.get(key)
        if previous and previous != status:
            state.warning(f"conflicting_readiness_status={key}::{previous},{status}")
        seen[key] = status

        if status in READY_READINESS_STATUSES:
            ready_count += 1
            if dependency not in {"satisfied", "independent"}:
                state.warning(f"ready_row_has_blocked_dependency={key}::{dependency or 'missing'}")
        elif status in COMPLETED_READINESS_STATUSES:
            terminal_count += 1

        ids = [item.strip() for item in re.split(r"[,; ]+", finding_ids) if item.strip() and item.strip().lower() != "none"]
        if status == "READY_WITH_WARNINGS":
            for finding_id in ids:
                entry = by_id.get(finding_id)
                if entry and entry[1] in EVIDENCE_OPEN_FINDING_STATUSES and entry[0] in {"P0", "P1"}:
                    state.warning(f"ready_with_warnings_references_blocking_finding={key}::{finding_id}")

    if ready_count:
        state.metrics["readiness_queue_state"] = "READY"
    elif terminal_count == len(rows):
        state.metrics["readiness_queue_state"] = "NO_ACTION_REQUIRED"
    else:
        state.metrics["readiness_queue_state"] = "BLOCKED"


def scan_secrets(state: ValidationState) -> None:
    secret_findings = 0
    root = state.planner_docs if state.planner_docs.exists() else state.root
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, line in _core.scan_text_for_secrets(text):
            secret_findings += 1
            state.error(f"secret_pattern={name}::{state.rel(path)}:{line}")
    state.metrics["secret_findings"] = secret_findings


def finalize(state: ValidationState) -> int:
    if state.strict:
        for warning in state.warnings:
            state.errors.append(f"strict_warning={warning}")

    state.metrics["warning_count"] = len(state.warnings)
    state.metrics["error_count"] = len(state.errors)

    status = "failed" if state.errors else "passed"
    print(f"planner_docs_validation={status}")
    print(f"mode={state.mode}")
    print(f"root={state.root}")
    for key in sorted(state.metrics):
        print(f"{key}={state.metrics[key]}")
    for warning in sorted(state.warnings):
        print(f"warning={warning}")
    for error in sorted(state.errors):
        print(f"error={error}")
    return 1 if state.errors else 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate QB plan outputs (the generated .qb/ tree).")
    parser.add_argument("--root", default=".", help="Project root containing .qb/; default: current directory.")
    parser.add_argument(
        "--mode",
        choices=("step1", "step2", "step3", "step4", "all"),
        default="all",
        help="Validation scope.",
    )
    parser.add_argument("--strict", action="store_true", help="Treat quality warnings as failures.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    state = ValidationState(root=Path(args.root).resolve(), mode=args.mode, strict=args.strict)

    if state.mode == "step1":
        validate_step1(state)
    elif state.mode == "step2":
        validate_step2(state)
    elif state.mode in {"step3", "all"}:
        validate_step3_preflight(state)
    elif state.mode == "step4":
        validate_step4_readiness(state)
    else:
        state.error(f"unknown_mode={state.mode}")

    # Optional evidence-backed artifacts, validated when present (dormant otherwise).
    if state.mode in {"step2", "step3", "step4", "all"}:
        validate_optional_comprehension_doc(state)
        validate_optional_ontology_doc(state)

    scan_secrets(state)
    return finalize(state)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
