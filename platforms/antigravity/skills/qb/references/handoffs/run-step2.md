---
contract_version: 1
---

# Step 2 Handoff Prompt

Single source for the Step 2 (phase sub-planning) Antigravity task handoff. After Step 1
feedback is handled and the user agrees to continue, tell the user to copy the block below,
open a new Antigravity task, and send it.

## Copy Block

```text
Use the qb skill. Run Step 2 according to references/second-planner.md.

Read all main phases in .qb/main-planning.md. If .qb/assessment.md, .qb/project-ontology.md, or .qb/planning-ledger.md exists, read it fully as supporting evidence and account for it in the sub-phase plans. Plan in a vibecoding-first style: small reversible slices, fast validation signals, explicit deferrals, security boundaries, and Antigravity task readiness. For each phase, create phase-<n>-plans folders and detailed phase-<n>.<m>-*.md sub-plan files under .qb. Do not stop until all phases are covered. Modify only .qb.
```
