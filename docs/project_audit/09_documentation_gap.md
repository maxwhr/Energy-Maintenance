# Documentation Gap Audit

## Summary

The repository contains extensive requirements, implementation reports and acceptance records. The weakness is not lack of documentation; it is that historical task snapshots, current instructions and future/blocked claims are mixed together. A reader can easily mistake an older passed result for the current runtime state.

## Confirmed Mismatches

### DOC-001 - Root Product Scope Is Too Broad

- Documentation: `README.md:3` describes renewable equipment across photovoltaic, storage and power equipment.
- Baseline/code rule: `AGENTS.md:9-34` restricts v1 to Huawei/Sungrow PV inverters.
- Impact: delivery scope and test expectations drift.
- Recommended correction: state v1 scope first; mark storage/transformer/power expansion as future-only.

### DOC-002 - Root README Mixes Historical Phases With Current Operations

- Documentation: `README.md:247-336` appends multiple task-era RAG/provider/KG statuses.
- Current truth: some external flags are enabled, but this audit did not revalidate external availability; KG grounding is currently insufficient.
- Impact: no single current capability table.
- Recommended correction: create one dated capability matrix and move task histories to linked reports.

### DOC-003 - Backend README Contains Stale Phase Instructions

- Documentation: `backend/README.md:79` says an upgrade was intentionally not executed in Task 02B, while the live database is currently at migration 0015.
- Impact: operators may follow obsolete phase-specific guidance.
- Recommended correction: separate current bootstrap/runbook from historical task notes.

### DOC-004 - Package/Product Naming Is Inconsistent

- Documentation/product: Energy-Maintenance.
- Source metadata: frontend package is `cupproject`.
- Legacy path: `frontend_legacy_before_cupProject_20260611_185550/`.
- Impact: build/package ownership ambiguity.

### DOC-005 - Current Code/Migrations Are Not In Git

- Documentation/reports describe Tasks 25B-25G as implemented.
- Git HEAD lacks current migrations 0009-0015 and many corresponding services/tests/deployment files.
- Impact: documentation claims cannot be reproduced from the repository commit.

### DOC-006 - API Success Convention Is Described As Unified But Uses 0 And 200

- Documentation: `AGENTS.md:499-518`, README claim a unified response.
- Code: authentication/devices use 0; shared helper uses 200; frontend accepts both.
- Impact: external integrators cannot rely on one success code.

### DOC-007 - Historical Real-call Passes Are Not Current Availability Proof

- Documentation: README/backend README and Task 24C/25B reports contain earlier real-call pass statements.
- Current audit: no external call permitted; current Cloud/Embedding/DashVector availability is `BLOCKED`.
- Impact: provider capability can be overstated if historical reports are quoted without date/config hash.
- Recommended correction: label snapshots with time, environment fingerprint and expiry/revalidation rule.

### DOC-008 - LoongArch Preparation Is Sometimes Read As Deployment Completion

- Positive evidence: deployment docs repeatedly warn that Windows/static checks are not physical acceptance.
- Remaining risk: the volume of deployment artifacts can be mistaken for a completed installation.
- Current truth: `REAL_MACHINE_ACCEPTANCE_CHECKLIST.md` is unexecuted.

## Old API/Mock Scan

- Current frontend calls all use matched `/api` routes.
- One `/api/v1` text hit in current documentation is a prohibition/example, not an active call.
- Historical docs contain mock/dry-run terminology. Most correctly label test-only behavior, but these sections should remain historical and not be copied into current capability claims.
- No active frontend mock/fake-success path was found by the integration checker.

## Documentation That Matches Reality Well

- `deploy/loongarch/README.md` clearly states source-level preparation and non-Docker native deployment.
- `deploy/loongarch/REAL_MACHINE_ACCEPTANCE_CHECKLIST.md` prevents false physical-acceptance claims.
- `docs/25G_R2_current_chinese_knowledge_graph_grounding_report.md` honestly records insufficient graph grounding.
- Vector services explicitly label fake in-memory mode as test-only.
- Provider documentation generally prohibits secret logging and distinguishes blocked/mock/real call states.

## Recommended Documentation Structure

1. Root README: current product scope, supported stack, quick start and a dated capability boundary table only.
2. Backend README: current install/migrate/run/test operations only.
3. `docs/history/`: immutable task reports and historical acceptance evidence.
4. `docs/current_status.md`: generated from Git commit, migration head, OpenAPI and current controlled acceptance.
5. Release checklist: clean Git baseline, test DB isolation, external-provider status and LoongArch physical acceptance.

## Truthful Current Capability Statement

The current working tree runs a PostgreSQL-backed Huawei/Sungrow PV-inverter maintenance application with a matched Vue/FastAPI API surface and broad persisted business modules. Read-side core smoke, schema alignment and frontend build pass. Write workflows, full regression, external AI/vector availability and physical LoongArch deployment were not reverified in this audit; knowledge-graph production grounding remains insufficient.

