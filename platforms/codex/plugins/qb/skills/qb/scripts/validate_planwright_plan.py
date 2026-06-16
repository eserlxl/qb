#!/usr/bin/env python3
"""Validate the QB-exported planwright plan (the generated .qb/plan.md).

QB's planning run projects its hierarchical .qb/ sub-plans into a single flat
checkbox plan, .qb/plan.md, in the exact item format an external planwright
executor consumes (see shared/planners/export-planner.md). This helper is the
read-only structural gate for that file: it mirrors the *machine-checkable
subset* of planwright's own plan linter, so a plan that passes here passes
planwright's Stage-10 gate when handed off with `planwright execute`.

It is intentionally read-only and dependency-free (Python standard library only,
preserving QB's zero-setup property). It checks structure; it never edits or
normalizes the plan, and it does not need planwright to be installed.

It also secret-scans the plan with the same length-bounded patterns the rest of
QB uses (the single source in analyzer_core.py): .qb/plan.md is generated AFTER
validate_planner_docs.py's .qb/ scan has run, so without this the export would
be the one planning artifact no gate scans for committed credentials. A secret
match is always a failure; if analyzer_core cannot be loaded the structural gate
still runs and the missing scan is reported as an advisory.

Checked invariants (the structural subset; semantic judgement stays the agent's job):
  * every pending item carries all required fields (Mode, Rationale, Evidence,
    Surfaces, Development, Acceptance, Verification; New Surfaces optional), non-empty;
  * Mode is one of develop|improve|repair|docs|reorganize;
  * Evidence never cites graph memory (graph.json / digest.md — routing, never proof);
  * a `repair` item's Evidence carries a file:line anchor to an existing file;
  * Surfaces are existing, repo-relative files (not absolute, no `..`, not a directory,
    never under .qb/ or .planwright/); New Surfaces do not already exist; no path is in both;
  * Verification is present, non-empty, and not a bare placeholder / prose;
  * no two pending items share a title.

Exit code: non-zero when any pending item violates a hard rule (0 when the plan is
clean or empty). With --strict, advisory notes are promoted to failures too.

    python3 validate_planwright_plan.py [--root DIR] [--plan PATH] [--strict] [--all]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

# --- Plan-format constants (mirror planwright's plan_parse.py / lint-plan.py) ----
REQUIRED_FIELDS = ("Mode", "Rationale", "Evidence", "Surfaces",
                   "Development", "Acceptance", "Verification")
VALID_MODES = {"develop", "improve", "repair", "docs", "reorganize"}
KNOWN_FIELDS = frozenset(set(REQUIRED_FIELDS) |
                         {"New Surfaces", "Status", "Rejection", "Commit"})
# Graph-memory artifacts that are routing only, never proof — barred from Evidence.
GRAPH_MEMORY = (".planwright/graph.json", ".planwright/digest.md",
                "graph.json", "digest.md")
# Bare Verification values that are never a runnable command.
PLACEHOLDER_VERIFICATION = {
    "todo", "tbd", "n/a", "na", "none", "manual", "manually",
    "pending", "fixme", "xxx", "?", "...", "tba",
}
# Characters that signal a runnable command (path / operator / quoting) anywhere.
_CMD_SIGNAL = set("/|&;<>$(){}=*\"'`-.")
# Characters a program/runner name commonly carries but a plain English word does not.
_PROGRAM_NAME_CHARS = set("_-.")
_KNOWN_EXEC = {
    "python", "python3", "py", "bash", "sh", "zsh", "ctest", "cmake", "make",
    "pytest", "unittest", "npm", "npx", "yarn", "pnpm", "cargo", "go", "node",
    "grep", "rg", "git", "ninja", "gradle", "mvn", "dotnet", "ruby", "rake",
    "tox", "deno", "bun", "test", "./",
    "docker", "docker-compose", "podman", "kubectl", "helm", "terraform",
    "bazel", "buck", "just", "task", "sbt", "meson", "scons",
    "php", "composer", "phpunit", "perl", "java", "javac", "scala", "mix",
    "swift", "dart", "flutter", "clang", "clang++", "gcc", "g++", "cc", "c++",
    "mypy", "ruff", "flake8", "pylint", "black", "isort", "shellcheck",
    "eslint", "tsc", "prettier",
    "vitest", "jest", "mocha", "ava", "jasmine", "cypress", "playwright", "tap",
}

_HEAD_RE = re.compile(r"^- \[([ xX])\]\s*(.*)$")
_FIELD_RE = re.compile(r"^\s+([A-Z][A-Za-z ]*?)\s*:\s*(.*)$")

# An Evidence file:line anchor: a repo-relative path then a line reference (":N",
# ":N-M", or " (line N)"). Mirrors planwright's _EVIDENCE_ANCHOR_RE so the repair
# grounding rule is recognised identically on both sides.
_EVIDENCE_ANCHOR_RE = re.compile(
    r"(?<![\w./-])"
    r"((?:\.{1,2}/)?"
    r"(?:\.?[A-Za-z0-9_][A-Za-z0-9_-]*/)*"
    r"(?:[A-Za-z0-9_][A-Za-z0-9_.-]*\.[A-Za-z][A-Za-z0-9]*"
    r"|(?:GNUmakefile|[Mm]akefile|Dockerfile|Containerfile|Jenkinsfile|Justfile"
    r"|Vagrantfile|Gemfile|Rakefile|Procfile|Kconfig|BUILD|WORKSPACE)"
    r"|\.[A-Za-z][A-Za-z0-9_.-]{2,}))"
    r"(?::(\d+)(?:-\d+)?|\s*\(line\s+(\d+)\))")


def parse_items(text, known_fields=KNOWN_FIELDS):
    """Parse plan-format markdown into item dicts:
    {checked: bool, title: str, line: int (1-based), fields: {name: value}}.
    A `- [ ]`/`- [x]` head opens an item; indented `Field: value` lines (labels in
    `known_fields`) attach to it, and a following non-blank indented line wraps the
    current field's value. A blank line ends the open field. A later occurrence of a
    field overwrites the earlier one. Mirrors planwright's plan_parse.parse_items
    (without the lifecycle `span`, which only the executor needs)."""
    lines = text if isinstance(text, list) else text.splitlines()
    items = []
    cur = None
    field = None
    for i, raw in enumerate(lines, 1):
        raw = raw.rstrip("\n")
        head = _HEAD_RE.match(raw)
        if head:
            cur = {"checked": head.group(1).lower() == "x",
                   "title": head.group(2).strip(), "line": i, "fields": {}}
            items.append(cur)
            field = None
            continue
        if cur is None:
            continue
        m = _FIELD_RE.match(raw)
        if m and m.group(1).strip() in known_fields:
            field = m.group(1).strip()
            cur["fields"][field] = m.group(2).strip()
        elif field is not None and raw.strip():
            cur["fields"][field] = (cur["fields"][field] + " " + raw.strip()).strip()
        elif not raw.strip():
            field = None
    return items


def is_prose_verification(norm):
    """True when a normalized Verification reads as prose, not a command: two or more
    words, no command-signal character, and a first token that is neither a known
    executable nor program-name-shaped. Conservative by design (mirrors planwright)."""
    tokens = norm.split()
    if len(tokens) < 2:
        return False
    if any(ch in _CMD_SIGNAL for ch in norm):
        return False
    if any(ch in _PROGRAM_NAME_CHARS for ch in tokens[0]):
        return False
    return tokens[0] not in _KNOWN_EXEC


def split_paths(value):
    out = []
    for p in value.split(","):
        p = p.strip().strip("`")
        if p and p.lower() != "none":
            out.append(p)
    return out


def unsafe_surface(p, root):
    """Return a reason string if surface path `p` is not a safe repo-relative path
    under `root`, else None. Rejects absolute paths, `..` traversal, and any path whose
    normalized realpath join escapes `root` (mirrors planwright's unsafe_surface)."""
    np = p.replace("\\", "/")
    if np.startswith("/") or (len(np) >= 2 and np[1] == ":"):
        return "absolute path (Surfaces must be repo-relative)"
    if ".." in np.split("/"):
        return "parent-directory traversal '..' (Surfaces must stay within the repo)"
    full = os.path.realpath(os.path.join(root, np))
    rootn = os.path.realpath(root)
    try:
        contained = full == rootn or os.path.commonpath([full, rootn]) == rootn
    except ValueError:
        contained = False
    if not contained:
        return "resolves outside the repo root"
    return None


def lint_item(item, root):
    """Return a list of hard-violation strings for one pending item."""
    v = []
    f = item["fields"]
    if not item["title"]:
        v.append("empty title")
    for req in REQUIRED_FIELDS:
        if req not in f:
            v.append(f"missing required field '{req}:'")
        elif not f[req]:
            v.append(f"empty field '{req}:'")

    mode = f.get("Mode", "")
    if mode and mode not in VALID_MODES:
        v.append(f"invalid Mode '{mode}' (use {'|'.join(sorted(VALID_MODES))})")

    ev = f.get("Evidence", "")
    for g in GRAPH_MEMORY:
        if g in ev:
            v.append(f"Evidence cites graph memory '{g}' (routing only, never proof)")
            break
    if mode == "repair" and ev and not (
            _EVIDENCE_ANCHOR_RE.search(ev)
            or re.search(r"\blines?\s+\d+", ev, re.IGNORECASE)):
        v.append("repair Evidence lacks a file:line anchor "
                 "(cite the wrong call site, not just structural absence)")

    verif = f.get("Verification", "")
    if verif:
        base = verif.strip().strip("`").strip().lower()
        norm = base.rstrip(".").strip()
        if norm in PLACEHOLDER_VERIFICATION or norm == "":
            v.append(f"Verification '{verif}' is a placeholder, not a runnable command")
        else:
            tokens = base.split()
            if tokens and any(c != "." for c in tokens[-1]):
                tokens[-1] = tokens[-1].rstrip(".")
            elif tokens and len(tokens[-1]) >= 3:
                tokens.pop()
            if is_prose_verification(" ".join(t for t in tokens if t)):
                v.append(f"Verification '{verif}' reads as prose, not a runnable command")

    surfaces = split_paths(f.get("Surfaces", ""))
    new_surfaces = split_paths(f.get("New Surfaces", ""))
    if not surfaces and not new_surfaces:
        v.append("no Surfaces and no New Surfaces (item changes nothing)")
    for p in surfaces:
        if os.path.basename(p) == "CMakeLists":
            v.append(f"Surface '{p}' must be spelled CMakeLists.txt")
            continue
        reason = unsafe_surface(p, root)
        if reason:
            v.append(f"Surface '{p}' is not a safe repo-relative path: {reason}")
        elif not os.path.exists(os.path.join(root, p)):
            v.append(f"Surface '{p}' does not exist under root")
        elif os.path.isdir(os.path.join(root, p)):
            v.append(f"Surface '{p}' is a directory; name the specific file(s) that change")
    for p in new_surfaces:
        if os.path.basename(p) == "CMakeLists":
            v.append(f"New Surface '{p}' must be spelled CMakeLists.txt")
            continue
        reason = unsafe_surface(p, root)
        if reason:
            v.append(f"New Surface '{p}' is not a safe repo-relative path: {reason}")
        elif os.path.exists(os.path.join(root, p)):
            v.append(f"New Surface '{p}' already exists (move it to Surfaces:)")
    overlap = sorted(set(surfaces) & set(new_surfaces))
    if overlap:
        v.append(f"path(s) in both Surfaces and New Surfaces: {', '.join(overlap)}")
    for p in surfaces + new_surfaces:
        np = p.replace("\\", "/")
        if np == ".planwright" or np.startswith(".planwright/"):
            v.append(f"'{p}' is tool-owned planwright state (.planwright/), not an editable Surface")
        if np == ".qb" or np.startswith(".qb/"):
            v.append(f"'{p}' is QB planning state (.qb/), not an executable item Surface")
    return v


def evidence_anchor_issues(ev, root):
    """Verify every repo-relative `path:N` anchor the Evidence cites. Returns a list of
    (path, kind, detail): kind 'missing' when the cited file does not exist, 'escape'
    when it resolves outside the repo, 'out-of-range' when the cited line exceeds the
    file's length. Mirrors planwright's evidence_anchor_issues; severity is the caller's
    call (keyed on Mode)."""
    issues = []
    if not ev:
        return issues
    seen = set()
    for m in _EVIDENCE_ANCHOR_RE.finditer(ev):
        cand = m.group(1)
        if unsafe_surface(cand, root):
            if (cand, "escape") not in seen:
                seen.add((cand, "escape"))
                issues.append((cand, "escape", "resolves outside the repo root"))
            continue
        full = os.path.join(root, cand)
        if not os.path.exists(full):
            if (cand, "missing") not in seen:
                seen.add((cand, "missing"))
                issues.append((cand, "missing", ""))
            continue
        line_s = m.group(2) or m.group(3)
        if not os.path.isfile(full) or not line_s:
            continue
        try:
            with open(full, "rb") as fh:
                n_lines = sum(1 for _ in fh)
        except OSError:
            continue
        cited = int(line_s)
        if cited > n_lines and (cand, cited) not in seen:
            seen.add((cand, cited))
            issues.append((cand, "out-of-range",
                           f"cites line {cited}, but the file has {n_lines} lines"))
    return issues


def validate_plan(text, root):
    """Return (errors, advisories) for the plan text. Pending items only."""
    errors = []
    advisories = []
    items = [it for it in parse_items(text) if not it["checked"]]

    for idx, item in enumerate(items, 1):
        where = f"item {idx} (line {item['line']}) '{item['title'] or '<untitled>'}'"
        for msg in lint_item(item, root):
            errors.append(f"{where}: {msg}")
        mode = item["fields"].get("Mode", "")
        for path, kind, detail in evidence_anchor_issues(
                item["fields"].get("Evidence", ""), root):
            if kind == "escape":
                errors.append(f"{where}: Evidence anchor '{path}' {detail} (must stay within the repo)")
            elif kind == "missing" and mode == "repair":
                errors.append(f"{where}: repair Evidence cites '{path}', which does not exist")
            elif kind == "missing":
                advisories.append(f"{where}: Evidence cites '{path}', which does not exist")
            else:
                advisories.append(f"{where}: Evidence anchor '{path}' {detail} (re-read the cited surface)")

    seen, dups = set(), []
    for it in items:
        t = it["title"]
        if t and t in seen and t not in dups:
            dups.append(t)
        seen.add(t)
    for t in dups:
        errors.append(f"duplicate pending title: '{t}'")

    return errors, advisories, len(items)


def _load_analyzer_core():
    """Load the co-located analyzer_core for the single-source secret patterns.

    Returns the module, or None if it cannot be loaded — the structural gate must
    still run, so a missing/uninstallable core degrades to a reported advisory
    rather than crashing the validator. analyzer_core.py is materialized next to
    this file on every platform by scripts/sync.sh (alongside its own siblings)."""
    if "qb_analyzer_core" in sys.modules:
        return sys.modules["qb_analyzer_core"]
    path = Path(__file__).resolve().parent / "analyzer_core.py"
    try:
        spec = importlib.util.spec_from_file_location("qb_analyzer_core", path)
        module = importlib.util.module_from_spec(spec)
        # Register BEFORE exec: analyzer_core's @dataclass type resolution looks up
        # sys.modules[cls.__module__], so the module must be present while it executes
        # (mirrors validate_planner_docs._load_analyzer_core). On any failure, drop the
        # half-initialized entry and degrade to None — the structural gate still runs.
        sys.modules["qb_analyzer_core"] = module
        spec.loader.exec_module(module)
    except (OSError, ImportError, AttributeError, ValueError, KeyError, TypeError):
        sys.modules.pop("qb_analyzer_core", None)
        return None
    return module


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Validate the QB-exported planwright plan (.qb/plan.md).")
    parser.add_argument("--root", default=".",
                        help="Project root containing .qb/; default: current directory.")
    parser.add_argument("--plan", default=None,
                        help="Plan file to validate (default: <root>/.qb/plan.md).")
    parser.add_argument("--strict", action="store_true",
                        help="Promote advisory notes to failures.")
    parser.add_argument("--all", action="store_true",
                        help="Reserved; pending items are always checked.")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    root = os.path.abspath(args.root)
    plan_path = args.plan or os.path.join(root, ".qb", "plan.md")

    errors = []
    advisories = []
    item_count = 0
    secret_findings = 0

    if not os.path.exists(plan_path):
        errors.append(f"missing_plan_file={plan_path}")
    else:
        try:
            with open(plan_path, encoding="utf-8") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            errors.append(f"non_utf8_plan_file={plan_path}")
            text = None
        except OSError as exc:
            errors.append(f"read_error={plan_path}:{exc}")
            text = None
        if text is not None:
            errors, advisories, item_count = validate_plan(text, root)
            # Secret scan: plan.md is generated after validate_planner_docs.py's
            # .qb/ scan, so it must be scanned here or not at all. A match is
            # always a failure (value redacted — only pattern name + line).
            core = _load_analyzer_core()
            if core is None:
                advisories.append(
                    "secret scan unavailable (analyzer_core not loadable); structural "
                    "checks ran but plan.md was not scanned for committed credentials")
            else:
                for name, line in core.scan_text_for_secrets(text):
                    secret_findings += 1
                    errors.append(f"secret_pattern={name}::{plan_path}:{line}")

    if args.strict:
        errors = errors + [f"strict_note={a}" for a in advisories]

    status = "failed" if errors else "passed"
    print(f"planwright_plan_validation={status}")
    print(f"plan_path={plan_path}")
    print(f"pending_item_count={item_count}")
    print(f"secret_findings={secret_findings}")
    print(f"violation_count={len(errors)}")
    print(f"advisory_count={len(advisories)}")
    for note in advisories:
        print(f"note={note}")
    for err in errors:
        print(f"error={err}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
