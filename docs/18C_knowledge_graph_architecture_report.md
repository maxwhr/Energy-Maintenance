# 18C Knowledge Graph Architecture Report

## Scope

Task 18C adds a PostgreSQL-backed knowledge graph foundation for the first-version Energy-Maintenance scope:

- Huawei and Sungrow PV inverter maintenance.
- PostgreSQL tables only.
- Rule-based extraction candidates only.
- No Neo4j, pgvector, embedding, OCR, or real LLM integration.

## Tables

The migration `20260601_0003_add_knowledge_graph_tables.py` adds:

- `kg_nodes`
- `kg_edges`
- `kg_node_aliases`
- `kg_evidence_links`
- `kg_extraction_runs`
- `kg_candidates`

## Model Design

`kg_nodes` stores normalized graph entities such as manufacturer, product series, fault, alarm, component, cause, action, tool, safety risk, knowledge document, and knowledge chunk.

`kg_edges` stores typed relations such as `BELONGS_TO`, `HAS_ALARM`, `CAUSED_BY`, `CHECK_BY`, `RESOLVED_BY`, `USES_TOOL`, `HAS_SAFETY_RISK`, `MENTIONED_IN`, and `DERIVED_FROM`.

`kg_evidence_links` connects nodes or edges to source records. Evidence can point to knowledge documents, chunks, contributions, diagnosis records, maintenance tasks, maintenance records, or media.

`kg_extraction_runs` records each extraction source and result state.

`kg_candidates` stores rule-extracted node, edge, and alias candidates before expert/admin approval.

## Backend Flow

The public API prefix is `/api/kg`.

Layering follows:

```text
api/routes/knowledge_graph.py
  -> services/knowledge_graph_service.py
  -> repositories/knowledge_graph_repository.py
  -> models/knowledge_graph.py
```

Rule extraction lives in:

```text
services/kg_rule_extractor.py
services/kg_extraction_service.py
services/kg_candidate_service.py
services/kg_evidence_service.py
```

Extraction creates pending candidates. It does not directly write formal graph nodes or edges except through expert/admin approval.

## Permissions

- `viewer`: read-only graph overview, nodes, edges, evidence, neighborhood, and path.
- `engineer`: read graph and trigger extraction from own approved/converted contributions.
- `expert`: manage nodes/edges, trigger extraction, approve/reject candidates.
- `admin`: full graph access.

## Frontend

The frontend adds a `知识图谱` page with:

- overview cards
- node list and manual node creation
- edge list and manual edge creation
- document extraction trigger
- pending candidate approval/rejection
- extraction runs and evidence links
- node neighborhood lookup

The page is intentionally a management view, not a full graph visualization canvas.

## Scripts

- `backend/scripts/seed_demo_knowledge_graph.py`
  - idempotently seeds demo graph nodes, edges, and evidence from approved parsed demo documents.
- `backend/scripts/check_knowledge_graph_flow.py`
  - checks login, overview, extraction, candidate approval, node/edge/evidence visibility, neighborhood, and viewer permission denial.

## Deferred

- interactive graph visualization canvas
- embedding / pgvector retrieval
- real LLM graph extraction
- OCR-based graph extraction
- graph-enhanced retrieval answer generation
- graph-enhanced diagnosis and SOP generation

---

## Task 18D Follow-up Status

Task 18D implements the first business integration layer on top of the Task 18C PostgreSQL graph foundation.

Implemented in Task 18D:

- active graph visualization endpoint: `GET /api/kg/graph`.
- active graph search endpoint: `GET /api/kg/search`.
- business graph context endpoint: `GET /api/kg/business-context`.
- graph-enhanced retrieval response fields and prompt context.
- graph-enhanced diagnosis response fields and prompt context.
- graph-enhanced SOP response fields and prompt context.
- record-center graph context summaries.
- frontend lightweight graph visualization, evidence lookup, neighborhood expansion, and path query.
- frontend graph context panels in retrieval, diagnosis, SOP, and record detail views.
- smoke script `backend/scripts/check_kg_business_integration.py`.

Still deferred after Task 18D:

- external graph database.
- graph embedding, pgvector, and semantic vector retrieval.
- real LLM graph extraction.
- OCR-based graph extraction.
- large-scale graph layout optimization.

Task 18D does not add or modify Alembic migrations. The schema head remains `20260601_0003`.
