# 18D Knowledge Graph Business Integration Report

## Scope

Task 18D connects the PostgreSQL-backed knowledge graph to first-version Huawei and Sungrow PV inverter maintenance workflows.

The task does not add a database migration and does not introduce Neo4j, NebulaGraph, JanusGraph, MongoDB, Elasticsearch, pgvector, embedding, OCR, Docker, SQLite, or a mandatory real model dependency.

## Backend Integration

New or enhanced graph read capabilities:

- `GET /api/kg/graph`
- `GET /api/kg/search`
- `GET /api/kg/business-context`

Business APIs enhanced with optional `enable_kg_enhancement`:

- `POST /api/retrieval/query`
- `POST /api/diagnosis/analyze`
- `POST /api/sop/generate`

Record-center detail responses can expose graph context summaries and real evidence links for traceability.

## Knowledge Graph Business Context

The graph business context is built only from active PostgreSQL graph data:

- active graph nodes.
- active graph edges.
- real evidence links.
- active source records already stored in PostgreSQL.

Returned context may include:

- matched nodes.
- related faults and alarms.
- related causes.
- inspection items.
- recommended actions.
- safety risks.
- SOP-related nodes.
- tools and parts.
- evidence.
- graph paths.
- node and edge summaries.

If no relevant graph context is found, the system returns empty graph fields rather than fabricated graph facts.

## Retrieval Enhancement

Retrieval keeps approved knowledge chunks as the primary evidence source. When graph enhancement is enabled and relevant graph context exists, the response adds graph context, graph evidence, graph paths, graph nodes, and graph edges.

The answer generator may add a short graph note and graph-informed suggested steps, but it must not overwrite real chunk references or fabricate sources.

## Diagnosis Enhancement

Diagnosis keeps the existing rule-based PV inverter diagnostic flow. When graph enhancement is enabled, active graph context may supplement:

- possible causes.
- inspection steps.
- recommended actions.
- safety risks.
- evidence summaries.

Safety notes remain mandatory and graph content does not replace field-engineer judgment.

## SOP Enhancement

SOP generation keeps templates and rule-based structure as the mainline. When graph enhancement is enabled, active graph context may supplement:

- tools.
- parts.
- safety risks.
- graph-related steps.
- evidence summaries.

Graph context must not remove required SOP safety or acceptance steps.

## Frontend Visualization

The `/knowledge/graph` page now includes:

- graph visualization tab.
- manufacturer, product series, fault type, node type, and keyword filters.
- node detail and evidence lookup.
- edge detail and evidence lookup.
- neighborhood expansion.
- path query tab.
- graph legend.

The visualization is implemented with existing frontend stack only and no new visualization dependency.

## Business Page Display

Graph context is displayed in:

- retrieval assistant.
- fault diagnosis.
- SOP generation.
- record-center detail.

Frontend pages display only backend-returned graph context and do not fabricate graph evidence.

## Verification Summary

Executed checks:

- `uv run python -m compileall app scripts`: passed.
- `uv run python -m alembic -c alembic.ini current`: passed, current revision `20260601_0003 (head)`.
- `npm.cmd run build`: passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1`: passed.
- `uv run python scripts/seed_demo_knowledge_graph.py`: passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1`: passed, 23 total, 0 failed.
- `uv run python scripts/check_knowledge_graph_flow.py`: passed.
- `uv run python scripts/check_kg_business_integration.py`: passed.

Runtime evidence from the integration script:

- graph response returned active nodes and edges.
- business-context response returned matched nodes and evidence.
- retrieval returned a persisted QA trace with graph context.
- diagnosis returned a persisted diagnosis trace with graph context.
- SOP generation returned graph-enhanced context.
- viewer role could read graph data but was denied graph write access.

## Deferred Capabilities

- external graph database.
- graph embedding and pgvector retrieval.
- real LLM graph extraction.
- OCR-based graph extraction.
- large-scale graph layout optimization.
- advanced visual analytics.

## Task 18E Cloud Model Context

Task 18E may pass approved active knowledge graph context into model prompts through the existing `ModelPromptBuilder`.

Safety boundary:

- graph context is a compact summary of active PostgreSQL graph nodes, edges, paths, and evidence.
- graph context remains supplemental and must not override traceable document references or SOP templates.
- prompt rules explicitly prohibit invented graph facts, invented references, local file paths, and binary media content.
- if cloud credentials are absent, graph-context model enhancement must be reported as blocked/fallback rather than real cloud success.

## Known Issues

- Manual browser inspection is still recommended for graph readability at different screen sizes.
- The graph layout is intentionally lightweight and may need future tuning for large graphs.
- Model gateway providers remain configuration-dependent; Task 18D does not claim real cloud or local model availability.
