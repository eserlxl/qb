---
contract_version: 1
---

# Step 3 Handoff Prompt

Single source for the Step 3 (sub-plan QA and coverage audit) Antigravity task handoff.
After Step 2 is complete and the user agrees to continue, tell the user to copy the block
below, open a new Antigravity task, and send it.

## Copy Block

```text
Use the qb skill. Run Step 3 according to references/third-planner.md.

Audit .qb/main-planning.md, .qb/sub-planning-index.md, .qb/phase-*-plans/*.md, and any supporting .qb/assessment.md, .qb/project-ontology.md, or .qb/planning-ledger.md. Analyze main-phase coverage, file naming, sequencing, required section structure, index consistency, content quality, scope drift, readiness realism, ontology consistency, planning-history continuity, security/governance, vibecoding slice quality, and Step 4 readiness. Do not fix any plan files; produce only .qb/sub-planning-audit.md. Do not stop until all phases and sub-plans have been reviewed.
```
